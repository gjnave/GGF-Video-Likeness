"""App-owned inference process. Direct core imports; no ComfyUI server."""
import json
import random
import sys
import time
import traceback
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROTOCOL = sys.stdout

def progress(message):
    PROTOCOL.write('__GGF__' + json.dumps({'progress': str(message)}) + '\n')
    PROTOCOL.flush()

def run(request):
    import numpy as np
    import torch
    from PIL import Image, ImageDraw, ImageFilter
    from config import CORE
    from headliner_worker import Engine, load_image_tensor
    started = time.perf_counter()
    if not torch.cuda.is_available():
        raise RuntimeError('NVIDIA CUDA is unavailable. Install the CUDA PyTorch build and a compatible NVIDIA driver before generating.')
    torch.cuda.reset_peak_memory_stats()
    seed = int(request.get('seed', -1))
    if seed < 0:
        seed = random.randrange(2**63)
    job = Path(request['job'])
    sys.argv = [sys.argv[0], '--models-directory', request['video_models'], '--reserve-vram', str(request.get('reserve_vram', 3.0))]
    if request['mode'] == 'image':
        source = Image.open(request['frame']).convert('RGB')
        box = request.get('box')
        if box:
            x0, y0, x1, y1 = box
            cx, cy = (x0+x1)/2, (y0+y1)/2
            w, h = x1-x0, y1-y0
            context = (max(0, int(cx-w*1.2)), max(0, int(cy-h*1.2)),
                       min(source.width, int(cx+w*1.2)), min(source.height, int(cy+h*1.2)))
            body = source.crop(context)
        else:
            context = (0, 0, source.width, source.height)
            body = source
        body.save(job / 'working-frame.png')
        progress('Loading Headliner likeness engine')
        engine = Engine(CORE, Path(request['image_models']), Path(request['image_loras']))
        progress('Making the likeness preview — six sampling steps')
        result = engine.generate(dict(body_path=str(job/'working-frame.png'), head_path=request['reference'],
                                      output_dir=str(job), steps=6, resolution=request.get('image_resolution', 768),
                                      upscale=1, seed=seed, extra_prompt=request.get('prompt', '')))
        generated = Image.open(result['output']).convert('RGB').resize(body.size, Image.Resampling.LANCZOS)
        if box:
            # Overlay color never enters either model. Only the clean crop is edited.
            from image_ops import composite_selection
            result_image = composite_selection(source,generated,box,context)
        else:
            result_image = generated
        output = job / 'likeness-preview.png'
        result_image.save(output)
        return dict(output=str(output), seed=seed, seconds=round(time.perf_counter()-started,2),peak_vram_gib=round(torch.cuda.max_memory_allocated()/2**30,2))

    sys.path.insert(0, str(CORE))
    import nodes
    import folder_paths
    import comfy.samplers
    from comfy_extras.nodes_minimax_h3 import MiniMaxH3SigmaShift
    from comfy_extras.nodes_custom_sampler import BasicGuider
    from vendor.viggle import nodes as viggle
    from media import prepare_clip, load_frames, save_video
    viggle.PROGRESS_CALLBACK = progress
    root = Path(request['video_models'])
    for kind in ('diffusion_models', 'vae', 'loras', 'text_cond'):
        folder_paths.add_model_folder_path(kind, str(root/kind), is_default=True)
    progress('Preparing your selected video range at 24 fps')
    width, height, length = prepare_clip(request['video'], request['start'], request['duration'],
                                         request['short_edge'], job/'driving.mkv')
    frames = torch.from_numpy(load_frames(job/'driving.mkv')).float().div_(255)
    reference = load_image_tensor(request['preview'])
    progress('Loading Viggle Animate and its three-step accelerator')
    model = nodes.UNETLoader().load_unet('minimax_h3_ref2va_viggle_pruned_int8_convrot.safetensors', 'default')[0]
    model = nodes.LoraLoaderModelOnly().load_lora_model_only(model, 'viggle_animate_dmd_lora_r64.safetensors', 1.0)[0]
    model = MiniMaxH3SigmaShift.execute(model, 3.0, 3.0)[0]
    vae = nodes.VAELoader().load_vae('minimax_h3_video_vae_int8_convrot.safetensors')[0]
    text = viggle.ViggleTextCondLoader().load('fixed_embed_fwd_anyframe.safetensors')[0]
    progress('Encoding the video and approved reference frame')
    with torch.no_grad():
        cond_set, positive = viggle.ViggleAnimateConditioningWindowed().build(
            frames, reference, text, vae, width, height, int(request['chunk_frames']), 22, 'five_frame_anchor')
        del frames, reference
        guider = BasicGuider.execute(model, positive)[0]
        sampler = comfy.samplers.sampler_object('euler')
        sigmas = torch.tensor([1., 6/7, .6, 0.])
        result, chunk_map = viggle.ViggleChunkedSampler().sample(guider, sampler, sigmas, cond_set, vae, seed, 0, 0)
    progress('Saving the result and restoring original audio')
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    output = job / f'Floyd-Headliner-Animate-{stamp}-{uuid.uuid4().hex[:6]}.mp4'
    save_video(result.cpu().numpy(), output, request['video'], request['start'], length, job/'silent.mp4')
    return dict(output=str(output), seed=seed, seconds=round(time.perf_counter()-started,2),
                width=width, height=height, chunk_map=chunk_map,peak_vram_gib=round(torch.cuda.max_memory_allocated()/2**30,2))

if __name__ == '__main__':
    request = json.loads(Path(sys.argv[1]).read_text())
    sys.stdout = sys.stderr
    try:
        result = {'ok': True, **run(request)}
    except Exception as error:
        traceback.print_exc()
        message = str(error)
        if 'out of memory' in message.lower():
            message = 'GPU memory ran out. Try a smaller output size or shorter sampling windows. Your inputs and previous results are preserved.'
        result = {'ok': False, 'error': message}
    PROTOCOL.write('__GGF__' + json.dumps(result) + '\n')
    PROTOCOL.flush()
