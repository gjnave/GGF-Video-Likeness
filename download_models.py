"""Pinned, resumable downloads. Never deletes models or user files."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def sha256(path):
    with open(path, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def download(group, destination):
    manifest = json.loads((ROOT / 'model_manifest.json').read_text())
    for item in manifest[group]:
        target = Path(destination) / item.get('destination', item['file'])
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if target.stat().st_size == item['size'] and sha256(target) == item['sha256']:
                print('Verified:', target, flush=True)
                continue
            raise RuntimeError(f'Existing model does not match manifest: {target}. Preserved; move it aside before retrying.')
        partial = target.with_suffix('.partial')
        url = f"https://huggingface.co/{item['repo']}/resolve/{item['revision']}/{item['file']}"
        print('Downloading:', target.name, flush=True)
        subprocess.run(['curl.exe', '-fL', '--retry', '6', '--retry-delay', '5', '-C', '-', '-o', str(partial), url], check=True)
        if partial.stat().st_size != item['size'] or sha256(partial) != item['sha256']:
            raise RuntimeError(f'Download verification failed; preserved for inspection: {partial}')
        partial.rename(target)
        print('Verified:', target, flush=True)

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--group', choices=['image', 'video', 'all'], default='all')
    p.add_argument('--root', type=Path, default=ROOT / 'models')
    args = p.parse_args()
    for group in (['image', 'video'] if args.group == 'all' else [args.group]):
        download(group, args.root)
