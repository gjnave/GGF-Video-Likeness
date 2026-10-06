import hashlib
import json
import sys
import tempfile
import unittest
import subprocess
import psutil
import zipfile
from pathlib import Path
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from media import canvas
from update_app import safe_name,stage_archive
from app import fresh_state,draw_selection,signature
from image_ops import composite_selection
from runtime import stop_process_tree
from unittest.mock import patch
import workspace
from app import resume_workspace, remember_form, FORM_DEFAULTS, step_frame
import av
import numpy as np

class CoreTests(unittest.TestCase):
    def test_animate_needs_preview_not_approval(self):
        import app
        state=fresh_state()
        state.update(preview='preview.png',video='input.mp4',signature=signature(None,'','Select a person',26,36))
        result=dict(output='result.mp4',seconds=1,width=384,height=672,seed=1)
        with patch.object(app,'generate',return_value=result) as generate,patch.object(workspace,'save'):
            output,_=app.animate(state,None,'','Select a person',26,36,0,5,384,56,-1)
            self.assertEqual(output,'result.mp4')
            generate.assert_called_once()

    def test_generation_activity_clears_old_output_and_recovers_callback_disconnect(self):
        import io
        import runtime
        from app import activity_view,poll_workspace
        from unittest.mock import Mock
        folder=Path(tempfile.mkdtemp(prefix='ggf-activity-test-'))
        state=fresh_state()
        state['output']='previous.mp4'
        process=Mock()
        process.stdout=io.StringIO('__GGF__{"progress":"Creating frames 0-55: step 1 of 3"}\n__GGF__{"ok":true,"output":"new.mp4"}\n')
        process.poll.return_value=0
        def disconnected_progress(text):
            saved=workspace.load(state['owner'])
            self.assertTrue(saved['activity']['running'])
            self.assertIsNone(saved['output'])
            self.assertIsNone(poll_workspace(state)[3])
            banner,button,_=activity_view(state)
            self.assertIn('GENERATING VIDEO',banner)
            self.assertIn('step 1 of 3',banner)
            self.assertFalse(button['interactive'])
            raise ConnectionError('Browser disconnected')
        with patch.object(workspace,'BASE',folder/'workspaces'),patch.object(runtime,'job_directory',return_value=folder),patch.object(runtime.subprocess,'Popen',return_value=process):
            workspace.save(state['owner'],state=state,output='previous.mp4')
            result=runtime.generate({'mode':'video'},state['owner'],disconnected_progress)
            self.assertTrue(result['ok'])
            self.assertFalse(runtime.LOCK.locked())
            self.assertFalse(workspace.load(state['owner'])['activity']['running'])
            self.assertIn('GENERATION COMPLETE',activity_view(state)[0])
            self.assertTrue(activity_view(state)[1]['interactive'])
            process.stdout=io.StringIO('__GGF__{"ok":false,"error":"Test failure"}\n')
            with self.assertRaisesRegex(RuntimeError,'Test failure'):
                runtime.generate({'mode':'video'},state['owner'],lambda text:None)
            self.assertFalse(runtime.LOCK.locked())
            self.assertIn('GENERATION STOPPED',activity_view(state)[0])

    def test_phone_rotation_and_output_shapes(self):
        from media import ffmpeg,inspect_video,capture_frame,prepare_clip,output_canvas,load_frames
        folder=Path(tempfile.mkdtemp(prefix='ggf-portrait-test-'))
        raw=folder/'landscape.mp4'
        rotated=folder/'phone.mp4'
        subprocess.run([ffmpeg(),'-v','error','-f','lavfi','-i','testsrc2=size=96x64:rate=24:duration=1','-c:v','libx264',str(raw)],check=True)
        subprocess.run([ffmpeg(),'-v','error','-display_rotation','90','-i',str(raw),'-c','copy',str(rotated)],check=True)
        meta=inspect_video(rotated)
        self.assertEqual((meta['width'],meta['height']),(64,96))
        self.assertEqual(output_canvas(meta,64),(64,96))
        frame,_,_=capture_frame(rotated,0,folder/'frame.png')
        with Image.open(frame) as captured:
            self.assertEqual(captured.size,(64,96))
            captured_pixels=np.asarray(captured).copy()
        w,h,_=prepare_clip(rotated,0,.25,64,folder/'auto.mkv')
        self.assertEqual((w,h),(64,96))
        decoded=load_frames(folder/'auto.mkv')[0]
        self.assertLess(np.abs(decoded.astype(float)-captured_pixels.astype(float)).mean(),3)
        w,h,_=prepare_clip(rotated,0,.25,64,folder/'wide.mkv','Landscape · 16:9')
        self.assertGreater(w,h)
        self.assertEqual(load_frames(folder/'wide.mkv').shape[1:3],(h,w))

    def test_workspace_recovers_media_approval_and_result(self):
        folder=Path(tempfile.mkdtemp(prefix='ggf-resume-test-'))
        image=folder/'reference.png'
        Image.new('RGB',(80,80),'blue').save(image)
        state=fresh_state()
        state.update(frame=str(image),video=str(image),preview=str(image),time=2,meta={'duration':8,'fps':24})
        with patch.object(workspace,'BASE',folder/'workspaces'):
            values=list(FORM_DEFAULTS)
            values[0]=str(image)
            values[1]='saved direction'
            remember_form(state,*values)
            workspace.save(state['owner'],state=state,approved=True,output=str(image))
            restored=resume_workspace(state['owner'])
            self.assertEqual(restored[1]['owner'],state['owner'])
            self.assertTrue(restored[7])
            self.assertEqual(restored[8],str(image))
            self.assertEqual(restored[11],'saved direction')
            self.assertEqual(signature(restored[10],'',*FORM_DEFAULTS[2:5]),signature(str(image),'',*FORM_DEFAULTS[2:5]))
            self.assertNotEqual(resume_workspace('invalid')[0],state['owner'])

    def test_frame_selection_and_single_frame_steps(self):
        folder=Path(tempfile.mkdtemp(prefix='ggf-frame-test-'))
        clip=folder/'frames.mkv'
        with av.open(str(clip),'w') as container:
            stream=container.add_stream('ffv1',rate=24)
            stream.width=64
            stream.height=64
            stream.pix_fmt='bgr0'
            for i in range(48):
                frame=av.VideoFrame.from_ndarray(np.full((64,64,3),i*4,dtype=np.uint8),format='rgb24')
                for packet in stream.encode(frame): container.mux(packet)
            for packet in stream.encode(): container.mux(packet)
        from app import browse_frame
        first=browse_frame(str(clip),0,fresh_state())
        later=browse_frame(str(clip),1,first[0])
        self.assertNotEqual(Image.open(first[1]).tobytes(),Image.open(later[1]).tobytes())
        after=step_frame(str(clip),later[2],later[0],1)
        before=step_frame(str(clip),after[2],after[0],-1)
        self.assertAlmostEqual(after[2]-later[2],1/24,places=2)
        self.assertAlmostEqual(before[2],later[2],places=2)

    def test_cancel_stops_owned_child_python(self):
        child_code='import time; time.sleep(60)'
        parent_code=f'import subprocess,sys,time; p=subprocess.Popen([sys.executable,"-c",{child_code!r}]); print(p.pid,flush=True); time.sleep(60)'
        parent=subprocess.Popen([sys.executable,'-u','-c',parent_code],stdout=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
        child=int(parent.stdout.readline())
        stop_process_tree(parent)
        parent.wait(timeout=10)
        parent.stdout.close()
        self.assertFalse(psutil.pid_exists(child))

    def test_mask_has_no_color_or_pixels_outside_selection(self):
        source=Image.new('RGB',(256,160),'white')
        generated=Image.new('RGB',(256,160),'red')
        result=composite_selection(source,generated,[80,0,195,130],(0,0,256,160))
        self.assertEqual(source.crop((0,130,256,160)).tobytes(),result.crop((0,130,256,160)).tobytes())
        self.assertEqual(source.crop((0,0,80,160)).tobytes(),result.crop((0,0,80,160)).tobytes())
        self.assertEqual(source.crop((195,0,256,160)).tobytes(),result.crop((195,0,256,160)).tobytes())
        self.assertNotEqual(source.tobytes(),result.tobytes())

    def test_canvas_preserves_orientation_and_grid(self):
        self.assertEqual(canvas(1920,1080,480),(864,480))
        self.assertEqual(canvas(1080,1920,480),(480,864))

    def test_source_paths_cannot_touch_private_files(self):
        for value in ['../app.py','/app.py','C:/app.py','models/a','jobs/a','local_settings.json','.venv/a']:
            self.assertFalse(safe_name(value),value)
        self.assertTrue(safe_name('vendor/comfy_api/input/__init__.py'))

    def test_selection_clipped_and_old_preview_invalidated(self):
        folder=Path(tempfile.mkdtemp(prefix='ggf-selection-test-'))
        source=folder/'frame.png'
        Image.new('RGB',(400,600),'white').save(source)
        before=source.read_bytes()
        state=fresh_state()
        state.update(frame=str(source),point=[2,5],preview='previous.png')
        new,overlay,preview,approved=draw_selection(state,20,30,'Select a person')
        self.assertEqual(new['box'],[0,0,42,95])
        self.assertIsNone(new['preview'])
        self.assertFalse(approved)
        self.assertEqual(source.read_bytes(),before)
        self.assertNotEqual(overlay.tobytes(),Image.open(source).tobytes())

    def test_archive_validation(self):
        folder=Path(tempfile.mkdtemp(prefix='ggf-release-test-'))
        contents={n:b'test' for n in ['app.py','VERSION','worker.py','requirements.txt','update_app.py']}
        manifest={'files':{n:hashlib.sha256(data).hexdigest() for n,data in contents.items()}}
        archive=folder/'source.zip'
        with zipfile.ZipFile(archive,'w') as z:
            for name,data in contents.items(): z.writestr('app/'+name,data)
            z.writestr('app/release-manifest.json',json.dumps(manifest))
        stage_archive(archive,folder/'stage')
        self.assertEqual((folder/'stage/app.py').read_bytes(),b'test')
        manifest['files']['../outside.py']='invalid'
        bad=folder/'unsafe.zip'
        with zipfile.ZipFile(bad,'w') as z:
            for name,data in contents.items(): z.writestr('app/'+name,data)
            z.writestr('app/release-manifest.json',json.dumps(manifest))
        with self.assertRaises(ValueError): stage_archive(bad,folder/'rejected')

if __name__=='__main__': unittest.main()
