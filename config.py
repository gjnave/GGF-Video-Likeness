import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CORE = ROOT / 'vendor' / 'comfy_core'

def settings():
    result = dict(video_models=str(ROOT / 'models'), image_models=str(ROOT / 'models'),
                  image_loras=str(ROOT / 'models' / 'loras'), python=sys.executable)
    path = ROOT / 'local_settings.json'
    if path.exists():
        result.update(json.loads(path.read_text(encoding='utf-8')))
    return result

def model_status():
    manifest = json.loads((ROOT / 'model_manifest.json').read_text())
    cfg = settings()
    lines = []
    for group, items in manifest.items():
        for item in items:
            rel = item.get('destination', item['file'])
            root = Path(cfg['video_models' if group == 'video' else 'image_models'])
            path = (Path(cfg['image_loras']) / Path(rel).name
                    if group == 'image' and rel.startswith('loras/') else root / rel)
            valid = path.is_file() and path.stat().st_size == item['size']
            lines.append(f"{'Ready' if valid else 'Missing/incomplete'}: {path.name}")
    return '\n'.join(lines)
