"""GGF Video Likeness — capture, preview, animate in one purpose-built UI."""
import base64
import copy
import json
import math
import os
import uuid
from pathlib import Path
import gradio as gr
from PIL import Image, ImageDraw, ImageOps
from config import ROOT, model_status, settings
from media import capture_frame, inspect_video
from runtime import generate, cancel, job_directory
from network_settings import (read_settings, save_settings, verify_login,
                              launch_access_servers, install_upload_disconnect_handling)

VERSION = (ROOT/'VERSION').read_text().strip()
REVISIONS = {}
CSS = (ROOT/'style.css').read_text()
LOGO = base64.b64encode((ROOT/'assets'/'ggf-brain-logo.png').read_bytes()).decode()
HEADER = f'''<div class="ggf-hero"><div><div class="ggf-eyebrow">GET GOING FAST · LOCAL AI</div>
<h1>GGF Video Likeness</h1><p>A new look. The same performance.</p>
<div class="ggf-links"><a href="https://getgoingfast.pro" target="_blank">GetGoingFast.pro ↗</a>
<a href="https://youtube.com/@TheAIHobbyGuy" target="_blank">The AI Hobby Guy ↗</a></div></div>
<img src="data:image/png;base64,{LOGO}" alt="Get Going Fast"></div>'''

def fresh_state():
    return {'owner':uuid.uuid4().hex, 'video':None, 'frame':None, 'point':None, 'box':None, 'preview':None}

def signature(reference, prompt, scope, width, height):
    if not reference:
        return None
    info = Path(reference).stat()
    return [str(reference), info.st_size, info.st_mtime_ns, prompt, scope, width, height]

def frame_for(path, time, state):
    if not path:
        raise gr.Error('Upload your video first and wait for its preview.')
    state = copy.deepcopy(state)
    folder = job_directory()
    frame, timestamp, meta = capture_frame(path, time, folder/'frame.png')
    state.update(video=path, frame=frame, time=timestamp, meta=meta, point=None, box=None, preview=None)
    REVISIONS[state['owner']] = REVISIONS.get(state['owner'],0)+1
    return state, frame, timestamp, None, False, f'Frame captured at {timestamp:.2f}s. Click the person’s face below, then add the replacement photo.'

def upload_video(path, state):
    if not path:
        REVISIONS[state['owner']] = REVISIONS.get(state['owner'],0)+1
        reset=fresh_state()
        reset['owner']=state['owner']
        return reset, None, 0, None, False, 'Upload a video to begin.'
    return frame_for(path, 0, state)

def draw_selection(state, width, height, scope):
    state = copy.deepcopy(state)
    REVISIONS[state['owner']] = REVISIONS.get(state['owner'],0)+1
    state['preview'] = None
    if not state.get('frame'):
        return state, None, None, False
    image = Image.open(state['frame']).convert('RGB')
    if scope == 'One person / whole frame':
        state['box'] = None
    elif state.get('point'):
        x, y = state['point']
        w, h = image.width * float(width) / 100, image.height * float(height) / 100
        state['box'] = [max(0, int(x-w/2)), max(0, int(y-h/2)), min(image.width, int(x+w/2)), min(image.height, int(y+h/2))]
        ImageDraw.Draw(image).ellipse(state['box'], outline='#ffbf45', width=max(2, image.width//250))
    return state, image, None, False

def pick_person(state, width, height, scope, event: gr.SelectData):
    state = copy.deepcopy(state)
    state['point'] = list(event.index)
    return draw_selection(state, width, height, scope)

def make_preview(state, reference, prompt, scope, width, height, seed, progress=gr.Progress()):
    if not state.get('frame'):
        raise gr.Error('Capture a video frame first.')
    if not reference:
        raise gr.Error('Upload the replacement person’s photo first.')
    if scope == 'Select a person' and not state.get('box'):
        raise gr.Error('Click the target person’s face in the captured frame. Adjust the oval to cover the head and hair.')
    revision=REVISIONS.get(state['owner'],0)
    try:
        result = generate(dict(mode='image', frame=state['frame'], reference=reference, box=state['box'],
                               prompt=prompt, seed=seed), state['owner'], lambda text:progress(0,desc=text))
    except Exception as error:
        raise gr.Error(str(error)) from None
    if revision != REVISIONS.get(state['owner'],0):
        return gr.skip(), gr.skip(), False, 'Preview saved, but your frame or selection changed while it was running. Make a new preview for the current selection.'
    state = copy.deepcopy(state)
    state.update(preview=result['output'], signature=signature(reference,prompt,scope,width,height))
    return state, result['output'], False, f'Preview ready in {result["seconds"]:.1f}s. Check the face, hair and surroundings, then approve it below.'

def use_edited(path, state, reference, prompt, scope, width, height):
    if not path or not state.get('frame'):
        raise gr.Error('Capture a frame and upload its edited version first.')
    original = Image.open(state['frame'])
    edited = ImageOps.exif_transpose(Image.open(path)).convert('RGB')
    if edited.size != original.size:
        raise gr.Error(f'The edited frame must retain the original dimensions: {original.width} × {original.height}.')
    folder = job_directory()
    edited.save(folder/'approved-frame.png')
    state = copy.deepcopy(state)
    state.update(preview=str(folder/'approved-frame.png'),signature=signature(reference,prompt,scope,width,height))
    return state, state['preview'], False, 'Edited frame imported. Review and approve before animating.'

def animate(state, approved, reference, prompt, scope, width, height, start, duration, size, window, seed, progress=gr.Progress()):
    if not approved or not state.get('preview'):
        raise gr.Error('Make a likeness preview and tick “Use this preview” first.')
    if state.get('signature') != signature(reference,prompt,scope,width,height):
        raise gr.Error('The reference or selection changed. Make and approve a new preview first.')
    if not math.isfinite(float(size)) or float(size) < 32:
        raise gr.Error('Output short edge must be at least 32 pixels.')
    if not math.isfinite(float(window)) or float(window) < 22:
        raise gr.Error('Each sampling window needs at least 22 frames (about 0.9 seconds).')
    aligned = max(22, 5 + math.ceil((int(window)-5)/17)*17)
    try:
        result = generate(dict(mode='video', video=state['video'], preview=state['preview'], start=start,
                               duration=duration, short_edge=int(size), chunk_frames=aligned, seed=seed),
                          state['owner'], lambda text:progress(0,desc=text))
    except Exception as error:
        raise gr.Error(str(error)) from None
    return result['output'], f'Finished in {result["seconds"]:.1f}s · {result["width"]} × {result["height"]} · seed {result["seed"]}. Download from the video player.'

def save_access(mode, username, password):
    modes = {'This computer only':'local','Local network':'lan','Temporary public link':'public'}
    saved = save_settings(modes[mode], username, password)
    return 'Saved. Close and reopen the app to apply. Local access stays available without login. ' + ('Remote login enabled.' if saved['digest'] else 'Remote login is OFF; anyone with the link can use the app.')

def build_demo():
    with gr.Blocks(title='GGF Video Likeness') as demo:
        state = gr.State(fresh_state)
        gr.HTML(HEADER)
        with gr.Tabs():
            with gr.Tab('Create', id='create'):
                gr.Markdown('Use only videos and likenesses you have the right and consent to edit. Identify generated output as AI-generated.')
                gr.Markdown('### 1 · Find your frame')
                video = gr.Video(label='Your video · play, pause, then capture', sources=['upload'], elem_id='source-video')
                with gr.Row():
                    timestamp = gr.Number(label='Capture time (seconds)', value=0, minimum=0, precision=3)
                    capture = gr.Button('Capture paused frame', variant='secondary')
                    exact = gr.Button('Capture at entered time', variant='secondary')
                gr.Markdown('### 2 · Choose the person and their new look')
                with gr.Row(equal_height=True):
                    with gr.Column():
                        selected = gr.Image(label='Captured frame · click the target face', type='filepath', format='png', interactive=False, height=360,buttons=['download','fullscreen'])
                        scope = gr.Radio(['Select a person','One person / whole frame'], value='Select a person', label='Who changes?')
                        with gr.Row():
                            width = gr.Slider(2,100,value=18,step=1,label='Selection width (%)')
                            height = gr.Slider(2,100,value=28,step=1,label='Selection height (%)')
                        gr.Markdown('Cover the head **and hair** with the gold oval. The oval is a selection guide, never part of the generated image.')
                    with gr.Column():
                        reference = gr.Image(label='Replacement person · clear face photo',type='filepath',sources=['upload','clipboard'],height=360)
                        prompt = gr.Textbox(label='Extra direction · optional',placeholder='For example: keep the hat from the original frame.',lines=2)
                preview_button = gr.Button('Make likeness preview',variant='primary')
                preview = gr.Image(label='Review your edited frame',type='filepath',format='png',interactive=False,height=400,buttons=['download','fullscreen'])
                approved = gr.Checkbox(label='Use this preview · the right person and likeness are selected',value=False)
                with gr.Accordion('Already edited the frame in Headliner or another editor?',open=False):
                    edited = gr.Image(label='Edited full frame · keep its original dimensions',type='filepath')
                    import_edit = gr.Button('Use edited frame',variant='secondary')
                gr.Markdown('### 3 · Animate')
                with gr.Row():
                    start = gr.Number(label='Video start (seconds)',value=0,minimum=0)
                    duration = gr.Number(label='Duration (seconds) · 0 = to end',value=5,minimum=0)
                    size = gr.Dropdown([384,480,576,768],value=384,allow_custom_value=True,label='Output short edge (pixels)')
                gr.Markdown('Start with 5 seconds at fast 384p. Longer clips use overlapping windows, not a five-second total limit. Large motion, scene cuts and someone leaving/re-entering can cause drift.')
                with gr.Accordion('More control',open=False):
                    window = gr.Number(label='Frames per sampling window · fast 56 / full 124',value=56,minimum=22,precision=0)
                    seed = gr.Number(label='Seed · -1 for a new result',value=-1,precision=0)
                    gr.Markdown('Windows align upward to the model’s 17n + 5 frame grid. Larger windows use more VRAM. Long clips also need more system RAM and disk space.')
                render = gr.Button('Animate approved preview',variant='primary')
                stop = gr.Button('Stop current generation',variant='secondary')
                status = gr.Markdown('Upload a video to begin.',elem_id='job-status')
                output = gr.Video(label='Your result · original audio retained',interactive=False,format='mp4')
            with gr.Tab('Settings',id='settings'):
                gr.Markdown(f'### App and models\nBuild {VERSION} · app-local inference · no ComfyUI installation or server required')
                models = gr.Textbox(label='Installed models',value=model_status,lines=9,interactive=False)
                refresh = gr.Button('Check model files',variant='secondary')
                gr.Markdown('The installer downloads the models. Existing Headliner models can be reused by setting model paths in `local_settings.json`; the original app is never modified.')
                check = gr.Button('Check for updates',variant='secondary')
                update_notice = gr.Markdown('Updates use Codeberg first, then GitHub, then the Google Drive source backup. Close the app and run **UPDATE.bat** to install an update.')
                gr.Markdown('### Use on your phone or another computer')
                saved = read_settings()
                names={'local':'This computer only','lan':'Local network','public':'Temporary public link'}
                access = gr.Dropdown(list(names.values()),value=names[saved['mode']],label='Access mode')
                with gr.Row():
                    username=gr.Textbox(label='Username',value=saved['username'],placeholder='ggf')
                    password=gr.Textbox(label='Password · blank turns login off',type='password')
                save=gr.Button('Save access settings',variant='secondary')
                network_notice=gr.Markdown('Changes apply after restart. Your local app stays login-free. Public links are temporary and can change. A blank password allows anyone with the link to use the app.')
        gr.HTML(f'<div class="ggf-footer">Powered by Qwen Image 2.1, Headliner likeness transfer and Viggle Animate / MiniMax H3.<br>GGF · Your Time Is Limited. Get Going Fast. · {VERSION}</div>')
        captured=[state,selected,timestamp,preview,approved,status]
        video.change(upload_video,[video,state],captured,queue=False,show_progress='hidden')
        capture.click(frame_for,[video,timestamp,state],captured,queue=False,show_progress='hidden',
                      js="(v,t,s)=>{const p=document.querySelector('#source-video video');if(p)p.pause();return [v,p?.currentTime??t,s]}")
        exact.click(frame_for,[video,timestamp,state],captured,queue=False,show_progress='hidden')
        selected.select(pick_person,[state,width,height,scope],[state,selected,preview,approved],queue=False,show_progress='hidden')
        for control in [width,height]:
            control.release(draw_selection,[state,width,height,scope],[state,selected,preview,approved],queue=False,show_progress='hidden')
        scope.change(draw_selection,[state,width,height,scope],[state,selected,preview,approved],queue=False,show_progress='hidden')
        preview_button.click(make_preview,[state,reference,prompt,scope,width,height,seed],[state,preview,approved,status],
                             concurrency_id='gpu',concurrency_limit=1,trigger_mode='once',show_progress='minimal')
        import_edit.click(use_edited,[edited,state,reference,prompt,scope,width,height],[state,preview,approved,status],queue=False)
        render.click(animate,[state,approved,reference,prompt,scope,width,height,start,duration,size,window,seed],[output,status],
                     concurrency_id='gpu',concurrency_limit=1,trigger_mode='once',show_progress='minimal')
        stop.click(lambda s:cancel(s['owner']),[state],[status],queue=False)
        refresh.click(model_status,outputs=models,queue=False)
        def check_updates():
            from update_app import check_update
            return check_update()
        check.click(check_updates,outputs=update_notice,queue=False)
        save.click(save_access,[access,username,password],network_notice,queue=False)
    demo.queue(max_size=4,default_concurrency_limit=1)
    return demo

if __name__ == '__main__':
    (ROOT/'app.lock').write_text(str(os.getpid()))
    install_upload_disconnect_handling()
    saved = read_settings()
    auth = (lambda u,p:verify_login(u,p,saved)) if saved['digest'] else None
    local, remote, local_url, remote_url = launch_access_servers(
        build_demo,mode=saved['mode'],preferred_port=int(os.environ.get('GGF_VIDEO_PORT','7862')),auth=auth,
        inbrowser='--no-browser' not in os.sys.argv,css=CSS,theme=gr.themes.Base(primary_hue='amber',neutral_hue='slate'),
        allowed_paths=[str(ROOT/'jobs')],show_error=True,footer_links=[])
    local.block_thread()
