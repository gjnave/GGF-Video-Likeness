"""Source-only updater. Verified staging, backups, three mirrors, no deletions."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
import uuid
import zipfile
from pathlib import Path
import requests
from packaging.version import Version

ROOT = Path(__file__).resolve().parent
DRIVE_ID = '1G_h82Vp0eqnGwQdTj6vMXI6dd8QvT2IL'
MIRRORS = [
    ('Codeberg','https://codeberg.org/Cognibuild/GGF-Video-Likeness/raw/branch/main/GGF-Video-Likeness-source.zip'),
    ('GitHub','https://github.com/gjnave/GGF-Video-Likeness/archive/refs/heads/main.zip'),
]
VERSIONS = [
    'https://codeberg.org/Cognibuild/GGF-Video-Likeness/raw/branch/main/VERSION',
    'https://raw.githubusercontent.com/gjnave/GGF-Video-Likeness/main/VERSION',
]
PRIVATE = {'models','outputs','jobs','logs','.venv','.git','local_settings.json','network_settings.json','app.lock'}

def latest_version():
    versions=[]
    for url in VERSIONS:
        try:
            response=requests.get(url,timeout=8,headers={'Cache-Control':'no-cache'})
            response.raise_for_status()
            latest=response.text.strip()
            versions.append(Version(latest))
        except Exception:
            pass
    return max(versions) if versions else None

def check_update():
    current = (ROOT/'VERSION').read_text().strip()
    latest=latest_version()
    if latest is None:
        return 'Update servers could not be reached. Nothing changed; try again later.'
    if latest>Version(current):
        return f'**Update available: {latest}.** Close the app and run **UPDATE.bat**. Your models, settings and videos will be kept.'
    return f'You are up to date: {current}.'

def safe_name(value):
    path=Path(value)
    return bool(value) and not path.is_absolute() and '..' not in path.parts and ':' not in value and not value.startswith(('\\','/')) and not any(part in PRIVATE for part in path.parts)

def stage_archive(archive, stage):
    with zipfile.ZipFile(archive) as z:
        manifests=[n for n in z.namelist() if n.endswith('release-manifest.json') and n.count('/')<=1]
        if len(manifests)!=1:
            raise ValueError('Archive does not contain exactly one release manifest.')
        manifest_name=manifests[0]
        prefix=manifest_name[:-len('release-manifest.json')]
        manifest=json.loads(z.read(manifest_name))
        files=manifest['files']
        if not {'app.py','VERSION','worker.py','requirements.txt','update_app.py'}.issubset(files):
            raise ValueError('Source archive is incomplete.')
        for name,digest in files.items():
            if not safe_name(name):
                raise ValueError('Unsafe or private path in source archive.')
            data=z.read(prefix+name)
            if hashlib.sha256(data).hexdigest()!=digest:
                raise ValueError('Source checksum mismatch: '+name)
            target=stage/name
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(data)
        (stage/'release-manifest.json').write_text(json.dumps(manifest,indent=2))
        return manifest

def update(archive=None):
    lock=ROOT/'app.lock'
    if lock.exists():
        import psutil
        try:
            pid=int(lock.read_text())
            process=psutil.Process(pid)
            if any(str(ROOT).lower() in s.lower() for s in process.cmdline()):
                raise RuntimeError('Close this app before running UPDATE.bat.')
        except (psutil.NoSuchProcess,ValueError):
            pass
    work=ROOT.parent/'update-cache'/uuid.uuid4().hex
    work.mkdir(parents=True)
    choices=[('Local archive',str(archive))] if archive else MIRRORS + ([('Google Drive',f'https://drive.usercontent.google.com/download?id={DRIVE_ID}&export=download&confirm=t')] if DRIVE_ID else [])
    expected=latest_version() if not archive else None
    failures=[]
    for source,url in choices:
        try:
            candidate=Path(url) if archive else work/(source.replace(' ','-')+'.zip')
            if not archive:
                subprocess.run(['curl.exe','-fL','--connect-timeout','15','--max-time','240','--retry','2','-o',str(candidate),url],check=True)
            stage=work/source.replace(' ','-')
            manifest=stage_archive(candidate,stage)
            current=Version((ROOT/'VERSION').read_text().strip()) if (ROOT/'VERSION').exists() else Version('0')
            incoming=Version((stage/'VERSION').read_text().strip())
            if incoming<current:
                raise ValueError('Mirror is older than your installed version; refusing downgrade.')
            if expected is not None and incoming<expected:
                raise ValueError('Mirror is behind another published source; trying the next source.')
            break
        except Exception as error:
            failures.append(f'{source}: {error}')
    else:
        raise RuntimeError('No usable source mirror. Existing app preserved.\n'+'\n'.join(failures))
    backup=ROOT.parent/'app-backups'/time.strftime('%Y%m%d-%H%M%S')
    for name in list(manifest['files'])+['release-manifest.json']:
        target=ROOT/name
        if target.exists():
            saved=backup/name
            saved.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(target,saved)
    for name in list(manifest['files'])+['release-manifest.json']:
        target=ROOT/name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(stage/name,target)
    print(f'Updated from {source} to {incoming}. Existing source backup: {backup}')
    return str(incoming)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--archive',type=Path)
    p.add_argument('--check',action='store_true')
    args=p.parse_args()
    if args.check:
        print(check_update())
    else:
        update(args.archive)
