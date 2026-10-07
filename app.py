"""Floyd Headliner Animate — capture, preview, animate in one purpose-built UI."""
import base64
import copy
import json
import math
import os
import uuid
import hashlib
import html
import time
import runtime
import workspace
from pathlib import Path
import gradio as gr
from PIL import Image, ImageDraw, ImageOps
from config import ROOT, model_status, settings
from media import capture_frame, inspect_video, output_canvas, SHAPES
from runtime import generate, cancel, job_directory
from network_settings import (read_settings, save_settings, verify_login,
                              launch_access_servers, install_upload_disconnect_handling)

VERSION = (ROOT/'VERSION').read_text().strip()
REVISIONS = {}
CSS = (ROOT/'style.css').read_text()
SEEK_PLAYER = """(seconds) => {
    const player = document.querySelector('#source-video video');
    if (!player) return [];
    player.pause();
    player.dataset.ggfSeek = String(Math.max(0, Number(seconds) || 0));
    const seek = () => {
        const target = Number(player.dataset.ggfSeek);
        player.currentTime = Number.isFinite(player.duration)
            ? Math.min(target, player.duration) : target;
    };
    if (player.readyState >= 1) seek();
    else player.addEventListener('loadedmetadata', seek, {once:true});
    return [];
}"""
LOGO = base64.b64encode((ROOT/'assets'/'ggf-brain-logo.png').read_bytes()).decode()
HEADER = f'''<div class="ggf-hero"><div><div class="ggf-eyebrow">GET GOING FAST · LOCAL AI</div>
<h1>Floyd Headliner Animate</h1><p>A new look. The same performance.</p>
<div class="ggf-links"><a href="https://getgoingfast.pro" target="_blank">GetGoingFast.pro ↗</a>
<a href="https://youtube.com/@TheAIHobbyGuy" target="_blank">The AI Hobby Guy ↗</a></div></div>
<img src="data:image/png;base64,{LOGO}" alt="Get Going Fast"></div>'''

def fresh_state():
    return {'owner':uuid.uuid4().hex, 'video':None, 'frame':None, 'point':None, 'box':None, 'preview':None}

def signature(reference, prompt, scope, width, height):
    if not reference:
        return None
    return [hashlib.sha256(Path(reference).read_bytes()).hexdigest(), prompt, scope, width, height]

def frame_for(path, time, state):
    if not path:
        raise gr.Error('Upload your video first and wait for its preview.')
    state = copy.deepcopy(state)
    path = workspace.keep_file(state['owner'], path)
    folder = job_directory()
    frame, timestamp, meta = capture_frame(path, time, folder/'frame.png')
    state.update(video=path, frame=frame, time=timestamp, meta=meta, point=None, box=None, preview=None)
    REVISIONS[state['owner']] = REVISIONS.get(state['owner'],0)+1
    workspace.save(state['owner'], state=state, approved=False)
    return state, frame, timestamp, None, False, f'Frame captured at {timestamp:.2f}s. Click the person’s face below, then add the replacement photo.'

def upload_video(path, state):
    if not path:
        REVISIONS[state['owner']] = REVISIONS.get(state['owner'],0)+1
        reset=fresh_state()
        reset['owner']=state['owner']
        workspace.save(state['owner'], state=reset, approved=False)
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
        ImageDraw.Draw(image).rounded_rectangle(state['box'], radius=max(2,int(min(w,h)*.05)), outline='#ffbf45', width=max(2, image.width//250))
    workspace.save(state['owner'], state=state, approved=False)
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
    workspace.save(state['owner'], state=state, approved=False, status='Preview ready. Click Animate preview to continue.')
    return state, result['output'], False, f'Preview ready in {result["seconds"]:.1f}s. Check the face, hair and surroundings, then click Animate preview.'

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
    workspace.save(state['owner'], state=state, approved=False)
    return state, state['preview'], False, 'Edited frame imported. Click Animate preview when ready.'

def animate(state, reference, prompt, scope, width, height, start, duration, size, window, seed, shape='Match uploaded video', progress=gr.Progress()):
    if not state.get('preview'):
        raise gr.Error('Make a likeness preview first.')
    if state.get('signature') != signature(reference,prompt,scope,width,height):
        raise gr.Error('The reference or selection changed. Make a new preview first.')
    if not math.isfinite(float(size)) or float(size) < 32:
        raise gr.Error('Output short edge must be at least 32 pixels.')
    if not math.isfinite(float(window)) or float(window) < 22:
        raise gr.Error('Each sampling window needs at least 22 frames (about 0.9 seconds).')
    aligned = max(22, 5 + math.ceil((int(window)-5)/17)*17)
    try:
        result = generate(dict(mode='video', video=state['video'], preview=state['preview'], start=start,
                               duration=duration, short_edge=int(size), chunk_frames=aligned, seed=seed, shape=shape),
                          state['owner'], lambda text:progress(0,desc=text))
    except Exception as error:
        raise gr.Error(str(error)) from None
    message = f'Finished in {result["seconds"]:.1f}s · {result["width"]} × {result["height"]} · seed {result["seed"]}. Download from the video player.'
    workspace.save(state['owner'], output=result['output'], status=message)
    state['output'] = result['output']
    return result['output'], message

FORM_KEYS = ['reference','prompt','scope','width','height','start','duration','size','window','seed','shape']
FORM_DEFAULTS = [None,'','Select a person',26,36,0,5,384,56,-1,'Match uploaded video']

def dimensions_notice(state,size,shape):
    if not state or not state.get('meta'):
        return 'Upload a video to detect its shape and output dimensions.'
    meta=state['meta']
    w,h=output_canvas(meta,float(size),shape)
    orientation='Portrait' if meta['height']>meta['width'] else 'Landscape' if meta['width']>meta['height'] else 'Square'
    return f'**Detected: {orientation} · {meta["width"]} × {meta["height"]}. Output: {w} × {h}.**' + (' Extra space is padded; the video is not cropped.' if shape in SHAPES else '')

def upload_and_size(video,state,size):
    result=browse_frame(video,0,state)
    saved=workspace.load(result[0]['owner']).get('form',{})
    saved['shape']='Match uploaded video'
    workspace.save(result[0]['owner'],form=saved)
    return [*result,'Match uploaded video',dimensions_notice(result[0],size,'Match uploaded video')]

def remember_form(state, *values):
    if not state:
        return
    form = dict(zip(FORM_KEYS, values))
    form['reference'] = workspace.keep_file(state['owner'], form['reference'])
    workspace.save(state['owner'], form=form)

def remember_approval(state, approved):
    if not state:
        return
    workspace.save(state['owner'], approved=bool(approved))

def selection_display(state):
    if not state.get('frame'):
        return None
    image = Image.open(state['frame']).convert('RGB')
    if state.get('box'):
        ImageDraw.Draw(image).rounded_rectangle(state['box'], radius=5, outline='#ffbf45', width=max(2,image.width//250))
    return image

def resume_workspace(token):
    owner = token if workspace.valid_owner(token) else uuid.uuid4().hex
    saved = workspace.load(owner)
    state = saved.get('state') or fresh_state()
    state['owner'] = owner
    state['output'] = saved.get('output')
    form = saved.get('form',{})
    maximum = max(0, state.get('meta',{}).get('duration',0)-1/state.get('meta',{}).get('fps',24))
    return [owner,state,state.get('video'),selection_display(state),state.get('time',0),
            gr.update(value=state.get('time',0),maximum=max(.001,maximum)),state.get('preview'),
            saved.get('approved',False),saved.get('output'),saved.get('status','Workspace restored.' if saved else 'Upload a video to begin.')]+[form.get(k,d) for k,d in zip(FORM_KEYS,FORM_DEFAULTS)]

def browse_frame(path, seconds, state):
    result = frame_for(path, seconds, state)
    new = result[0]
    maximum = max(.001,new['meta']['duration']-1/new['meta']['fps'])
    return [*result,gr.update(value=result[2],maximum=maximum)]

def step_frame(path, seconds, state, direction):
    fps = state.get('meta',{}).get('fps',24)
    # A small tolerance prevents floating-point roundoff skipping a frame.
    return browse_frame(path,max(0,float(seconds)+direction/fps-1e-7),state)

def poll_workspace(state):
    if not state:
        return [gr.skip()]*5
    saved = workspace.load(state['owner'])
    latest = saved.get('state',state)
    if latest.get('preview') != state.get('preview') or saved.get('output') != state.get('output'):
        latest = copy.deepcopy(latest)
        latest['output'] = saved.get('output')
        return latest,latest.get('preview'),saved.get('approved',False),saved.get('output'),saved.get('status','Workspace restored.')
    return [gr.skip()]*5

def activity_view(state):
    if not state:
        return '',gr.skip(),gr.skip()
    saved=workspace.load(state['owner'])
    activity=saved.get('activity')
    if not activity:
        return '',gr.update(interactive=True),gr.update(interactive=True)
    running=activity.get('running',False)
    if running and not runtime.LOCK.locked():
        activity.update(running=False,finished=time.time(),error=True,stage='Generation interrupted when the server stopped.')
        workspace.save(state['owner'],activity=activity)
        running=False
    elapsed=max(0,int((time.time() if running else activity.get('finished',time.time()))-activity['started']))
    clock=f'{elapsed//60}:{elapsed%60:02d}'
    title=('GENERATING VIDEO' if activity.get('mode')=='video' else 'GENERATING LIKENESS PREVIEW') if running else ('GENERATION STOPPED' if activity.get('error') else 'GENERATION COMPLETE')
    kind='running' if running else 'stopped' if activity.get('error') else 'complete'
    banner=f'<div class="generation-banner {kind}" role="status" aria-live="polite"><strong>{title} · {clock}</strong><div>{html.escape(activity["stage"])}</div></div>'
    return banner,gr.update(interactive=not running),gr.update(interactive=not running)

def save_access(mode, username, password):
    modes = {'This computer only':'local','Local network':'lan','Temporary public link':'public'}
    saved = save_settings(modes[mode], username, password)
    return 'Saved. Close and reopen the app to apply. Local access stays available without login. ' + ('Remote login enabled.' if saved['digest'] else 'Remote login is OFF; anyone with the link can use the app.')

def build_demo():
    with gr.Blocks(title='Floyd Headliner Animate') as demo:
        # Only resume_workspace initializes this: a callable State creates its own
        # competing load event, which can overwrite the restored owner/state.
        state = gr.State(None)
        browser_workspace = gr.Textbox(value='',visible=False)
        gr.HTML(HEADER)
        activity_banner=gr.HTML('',elem_id='generation-activity')
        with gr.Tabs():
            with gr.Tab('Create', id='create'):
                gr.Markdown('Use only videos and likenesses you have the right and consent to edit. Identify generated output as AI-generated.')
                gr.Markdown('### 1 · Find your frame')
                video = gr.Video(label='Your video · play, pause, then capture', sources=['upload'], elem_id='source-video')
                timeline = gr.Slider(0,.001,value=0,step=.001,label='Choose a frame · drag through your video',interactive=True)
                with gr.Row():
                    previous_frame = gr.Button('◀ Previous frame',variant='secondary')
                    next_frame = gr.Button('Next frame ▶',variant='secondary')
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
                            width = gr.Slider(2,100,value=26,step=1,label='Whole-head width (%)')
                            height = gr.Slider(2,100,value=36,step=1,label='Whole-head height (%)')
                        gr.Markdown('Click the **center of the whole head**, then cover all hair, ears and the back of the head with the gold box. Leave a little room for the new hairstyle. Click again to reposition.')
                    with gr.Column():
                        reference = gr.Image(label='Replacement person · clear face photo',type='filepath',sources=['upload','clipboard'],height=360)
                        prompt = gr.Textbox(label='Extra direction · optional',placeholder='For example: keep the hat from the original frame.',lines=2)
                preview_button = gr.Button('Make likeness preview',variant='primary')
                preview = gr.Image(label='Review your edited frame',type='filepath',format='png',interactive=False,height=400,buttons=['download','fullscreen'])
                # Retain the legacy workspace field without an approval control or generation gate.
                approved = gr.State(False)
                with gr.Accordion('Already edited the frame in Headliner or another editor?',open=False):
                    edited = gr.Image(label='Edited full frame · keep its original dimensions',type='filepath')
                    import_edit = gr.Button('Use edited frame',variant='secondary')
                gr.Markdown('### 3 · Animate')
                with gr.Row():
                    start = gr.Number(label='Video start (seconds)',value=0,minimum=0)
                    duration = gr.Number(label='Duration (seconds) · 0 = to end',value=5,minimum=0)
                    size = gr.Dropdown([384,480,576,768],value=384,allow_custom_value=True,label='Output short edge (pixels)')
                shape = gr.Dropdown(['Match uploaded video',*SHAPES],value='Match uploaded video',label='Output shape',interactive=True)
                dimensions = gr.Markdown('Upload a video to detect its shape and output dimensions.')
                gr.Markdown('Start with 5 seconds at fast 384p. Longer clips use overlapping windows, not a five-second total limit. Large motion, scene cuts and someone leaving/re-entering can cause drift.')
                with gr.Accordion('More control',open=False):
                    window = gr.Number(label='Frames per sampling window · fast 56 / full 124',value=56,minimum=22,precision=0)
                    seed = gr.Number(label='Seed · -1 for a new result',value=-1,precision=0)
                    gr.Markdown('Windows align upward to the model’s 17n + 5 frame grid. Larger windows use more VRAM. Long clips also need more system RAM and disk space.')
                render = gr.Button('Animate preview',variant='primary')
                stop = gr.Button('Stop current generation',variant='secondary')
                status = gr.Markdown('Upload a video to begin.',elem_id='job-status')
                output = gr.Video(label='Your result · original audio retained',interactive=False,format='mp4',height=560,elem_id='result-video')
                expand_output = gr.Button('Expand video / exit fullscreen',variant='secondary')
                expand_output.click(None,[],[],queue=False,js="""async()=>{
                    const box=document.querySelector('#result-video');
                    const video=box?.querySelector('video');
                    if(!video)return;
                    if(document.fullscreenElement){await document.exitFullscreen();return;}
                    if(box.classList.contains('expanded-video')){box.classList.remove('expanded-video');return;}
                    try{
                        if(video.requestFullscreen){await video.requestFullscreen();return;}
                        if(video.webkitEnterFullscreen){video.webkitEnterFullscreen();return;}
                    }catch(e){}
                    box.classList.add('expanded-video');
                    box.onclick=(e)=>{if(e.target===box)box.classList.remove('expanded-video');};
                    document.addEventListener('keydown',function exit(e){if(e.key==='Escape'){box.classList.remove('expanded-video');document.removeEventListener('keydown',exit);}});
                }""")
            with gr.Tab('Settings',id='settings'):
                gr.Markdown(f'### App and models\nBuild {VERSION} · app-local inference · no ComfyUI installation or server required')
                models = gr.Textbox(label='Installed models',value=model_status,lines=9,interactive=False)
                refresh = gr.Button('Check model files',variant='secondary')
                gr.Markdown('The installer downloads the models. Existing Headliner models can be reused by setting model paths in `local_settings.json`; the original app is never modified.')
                check = gr.Button('Check for updates',variant='secondary')
                install_update = gr.Button('Update and restart', variant='primary')
                update_notice = gr.Markdown('Check for new code, then update and restart here. Models, settings and videos are kept. Public phone links may change after restarting.')
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
        capture_outputs=[*captured,timeline]
        # Keep the visible player in sync with server-decoded frame selection.
        timestamp.change(None,[timestamp],[],js=SEEK_PLAYER,queue=False)
        timeline.input(None,[timeline],[],js=SEEK_PLAYER,queue=False)
        video.upload(upload_and_size,[video,state,size],[*capture_outputs,shape,dimensions],queue=False,show_progress='hidden')
        video.clear(upload_video,[video,state],captured,queue=False,show_progress='hidden')
        timeline.release(browse_frame,[video,timeline,state],capture_outputs,queue=False,show_progress='hidden')
        previous_frame.click(lambda v,t,s:step_frame(v,t,s,-1),[video,timestamp,state],capture_outputs,queue=False,show_progress='hidden')
        next_frame.click(lambda v,t,s:step_frame(v,t,s,1),[video,timestamp,state],capture_outputs,queue=False,show_progress='hidden')
        capture.click(browse_frame,[video,timestamp,state],capture_outputs,queue=False,show_progress='hidden',
                      js="(v,t,s)=>{const p=document.querySelector('#source-video video');if(p)p.pause();return [v,p?.currentTime??t,s]}")
        exact.click(browse_frame,[video,timestamp,state],capture_outputs,queue=False,show_progress='hidden')
        selected.select(pick_person,[state,width,height,scope],[state,selected,preview,approved],queue=False,show_progress='hidden')
        for control in [width,height]:
            control.release(draw_selection,[state,width,height,scope],[state,selected,preview,approved],queue=False,show_progress='hidden')
        scope.input(draw_selection,[state,width,height,scope],[state,selected,preview,approved],queue=False,show_progress='hidden')
        preview_button.click(make_preview,[state,reference,prompt,scope,width,height,seed],[state,preview,approved,status],
                             concurrency_id='gpu',concurrency_limit=1,trigger_mode='once',show_progress='minimal')
        import_edit.click(use_edited,[edited,state,reference,prompt,scope,width,height],[state,preview,approved,status],queue=False)
        render.click(animate,[state,reference,prompt,scope,width,height,start,duration,size,window,seed,shape],[output,status],
                     concurrency_id='gpu',concurrency_limit=1,trigger_mode='once',show_progress='minimal')
        stop.click(lambda s:cancel(s['owner']),[state],[status],queue=False)
        refresh.click(model_status,outputs=models,queue=False)
        def check_updates():
            from update_app import check_update
            return check_update()
        check.click(check_updates,outputs=update_notice,queue=False)
        def update_and_restart():
            import threading
            from update_app import start_restart
            if not runtime.LOCK.acquire(blocking=False):
                return 'Finish or stop the current generation before updating.'
            try:
                start_restart()
            except Exception as error:
                runtime.LOCK.release()
                return f'Update could not start: {error}'
            timer = threading.Timer(3, lambda: os._exit(0))
            timer.daemon = True
            timer.start()
            return 'Updating and restarting. Reopen the local app when it starts. A public phone link may change. Details are saved in logs/update.log.'
        install_update.click(update_and_restart, outputs=update_notice, queue=False)
        save.click(save_access,[access,username,password],network_notice,queue=False)
        form_controls=[reference,prompt,scope,width,height,start,duration,size,window,seed,shape]
        for control in [size,shape]:
            control.change(dimensions_notice,[state,size,shape],dimensions,queue=False,show_progress='hidden')
        for control in form_controls:
            control.input(remember_form,[state,*form_controls],[],queue=False,show_progress='hidden')
        demo.load(resume_workspace,[browser_workspace],[browser_workspace,state,video,selected,timestamp,timeline,preview,approved,output,status,*form_controls],queue=False,show_progress='hidden',
                  js="()=>{let k='ggf-video-workspace-v2',t=localStorage.getItem(k);if(!/^[0-9a-f]{32}$/.test(t||'')){t=crypto.randomUUID().replaceAll('-','');localStorage.setItem(k,t)}return [t]}").then(dimensions_notice,[state,size,shape],dimensions,queue=False,show_progress='hidden')
        refresh_timer=gr.Timer(1)
        refresh_timer.tick(poll_workspace,[state],[state,preview,approved,output,status],queue=False,show_progress='hidden')
        refresh_timer.tick(activity_view,[state],[activity_banner,render,preview_button],queue=False,show_progress='hidden')
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
