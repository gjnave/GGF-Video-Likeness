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

class CoreTests(unittest.TestCase):
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
