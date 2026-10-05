"""Installer model setup; reuse explicitly configured image weights read-only."""
import json
from pathlib import Path
from config import ROOT, settings
from download_models import download,sha256

def main():
    cfg=settings()
    manifest=json.loads((ROOT/'model_manifest.json').read_text())
    existing=Path(cfg['image_models'])!=ROOT/'models'
    if existing:
        for item in manifest['image']:
            rel=item.get('destination',item['file'])
            path=(Path(cfg['image_loras'])/Path(rel).name if rel.startswith('loras/') else Path(cfg['image_models'])/rel)
            if not path.is_file() or path.stat().st_size!=item['size'] or sha256(path)!=item['sha256']:
                raise RuntimeError(f'Configured Headliner model is missing or does not match: {path}. Original installation was not changed.')
            print('Reusing verified model:',path,flush=True)
    else:
        download('image',cfg['image_models'])
    download('video',cfg['video_models'])

if __name__=='__main__':
    main()
