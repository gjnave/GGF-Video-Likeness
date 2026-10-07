"""Git source updates; no manually maintained source ZIP."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent
MIRRORS = [
    ('Codeberg', 'https://codeberg.org/Cognibuild/Headliner-Animate.git'),
    ('GitHub', 'https://github.com/gjnave/Headliner-Animate.git'),
]
PRIVATE = {'models', 'outputs', 'jobs', 'logs', '.venv', '.git',
           'local_settings.json', 'network_settings.json', 'app.lock'}

def git(root, *args):
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='never')
    result = subprocess.run(['git', '-C', str(root), *args], env=env,
                            capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'Git command failed.')
    return result.stdout.strip()

def safe_name(value):
    parts = value.replace('\\', '/').split('/')
    return bool(value) and not value.startswith(('/', '\\')) and ':' not in value and not any(p in PRIVATE or p == '..' for p in parts)

def remote_head(root=ROOT):
    errors = []
    for name, url in MIRRORS:
        try:
            result = git(root, 'ls-remote', url, 'refs/heads/main')
            if not result:
                raise RuntimeError('No main branch found.')
            return name, url, result.split()[0]
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
            errors.append(f'{name}: {error}')
    raise RuntimeError('Cannot reach the source repositories. Nothing changed. ' + '; '.join(errors))

def check_update(root=ROOT):
    try:
        if not (root / '.git').exists():
            remote_head(root)
            return 'Git updates are available. Click Update and restart to connect this installation; models and settings are kept.'
        current = git(root, 'rev-parse', 'HEAD')
        errors = []
        for name, url in MIRRORS:
            try:
                git(root, 'fetch', '--no-tags', url, 'main')
                commit = git(root, 'rev-parse', 'FETCH_HEAD')
                if current == commit:
                    return f'You are up to date ({current[:8]}, {name}).'
                git(root, 'merge-base', '--is-ancestor', current, commit)
                return f'**Update available ({commit[:8]}, {name}).** Click Update and restart. Models, settings and videos are kept.'
            except Exception as error:
                errors.append(f'{name}: {error}')
        return 'No compatible newer revision could be verified. Your local branch may be ahead or diverged, or the mirrors may be unavailable. Nothing changed. ' + '; '.join(errors)
    except Exception as error:
        return str(error)

def update(root=ROOT):
    root = Path(root).resolve()
    if (root / '.git').exists():
        if git(root, 'status', '--porcelain', '--untracked-files=no'):
            raise RuntimeError('Local source changes exist. Commit or back them up before updating; nothing was overwritten.')
        if git(root, 'branch', '--show-current') != 'main':
            raise RuntimeError('Automatic updates require the main branch. Your checkout was not changed.')
        errors = []
        for name, url in MIRRORS:
            try:
                git(root, 'fetch', '--no-tags', url, 'main')
                target = git(root, 'rev-parse', 'FETCH_HEAD')
                git(root, 'merge-base', '--is-ancestor', 'HEAD', target)
                break
            except Exception as error:
                errors.append(f'{name}: {error}')
        else:
            raise RuntimeError('No compatible update found. Local source preserved. ' + '; '.join(errors))
        if git(root, 'rev-parse', 'HEAD') == target:
            return target
        backup = root.parent / 'app-backups' / time.strftime('%Y%m%d-%H%M%S')
        backup.mkdir(parents=True, exist_ok=True)
        git(root, 'bundle', 'create', str(backup / 'source.bundle'), '--all')
        git(root, 'merge', '--ff-only', target)
        return target
    # One-time migration of old installed copies to a normal Git checkout.
    stage = Path(tempfile.mkdtemp(prefix='headliner-git-'))
    errors = []
    for index, (name, url) in enumerate(MIRRORS):
        candidate = stage / str(index)
        try:
            git(stage, 'clone', '--branch', 'main', '--single-branch', url, str(candidate))
            files = [item for item in git(candidate, 'ls-files', '-z').split('\0') if item]
            if not {'app.py', 'update_app.py', 'requirements.txt', 'worker.py'}.issubset(files):
                raise RuntimeError('Repository does not contain the full app source.')
            if any(not safe_name(item) or (candidate / item).is_symlink() for item in files):
                raise RuntimeError('Repository contains a protected or unsafe path.')
            break
        except Exception as error:
            errors.append(f'{name}: {error}')
    else:
        raise RuntimeError('No usable source repository. Existing files preserved. ' + '; '.join(errors))
    backup = root.parent / 'app-backups' / time.strftime('%Y%m%d-%H%M%S')
    for item in files:
        target = root / item
        if target.exists():
            saved = backup / item
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
    for item in files:
        target = root / item
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(candidate / item, target)
    shutil.copytree(candidate / '.git', root / '.git')
    return git(root, 'rev-parse', 'HEAD')

def start_restart(root=ROOT):
    """Copy helper outside the source tree so updating cannot disrupt it."""
    import psutil
    remote_head(root)  # Fail before closing the original app.
    folder = Path(tempfile.mkdtemp(prefix='headliner-restart-'))
    helper = folder / 'update_app.py'
    shutil.copy2(Path(__file__), helper)
    log = root / 'logs' / 'update.log'
    log.parent.mkdir(exist_ok=True)
    command = [sys.executable, str(helper), '--root', str(root), '--restart',
               str(os.getpid()), str(psutil.Process().create_time())]
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    with log.open('a', encoding='utf-8') as stream:
        subprocess.Popen(command, cwd=root, stdin=subprocess.DEVNULL,
                         stdout=stream, stderr=stream, creationflags=flags)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--restart', nargs=2, metavar=('PID', 'CREATED'))
    args = parser.parse_args()
    root = args.root.resolve()
    if args.check:
        print(check_update(root))
        return
    import psutil
    if args.restart:
        pid, created = int(args.restart[0]), float(args.restart[1])
        deadline = time.monotonic() + 45
        while psutil.pid_exists(pid):
            try:
                if psutil.Process(pid).create_time() != created:
                    break
            except psutil.NoSuchProcess:
                break
            if time.monotonic() > deadline:
                raise RuntimeError('App did not close; update cancelled.')
            time.sleep(.5)
    else:
        lock = root / 'app.lock'
        if lock.exists():
            try:
                process = psutil.Process(int(lock.read_text()))
                if any(str(root).lower() in arg.lower() for arg in process.cmdline()):
                    raise RuntimeError('Close this app first, or use Update and restart in Settings.')
            except (ValueError, psutil.NoSuchProcess):
                pass
    try:
        before = (root / 'requirements.txt').read_bytes()
        commit = update(root)
        if before != (root / 'requirements.txt').read_bytes():
            subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', str(root / 'requirements.txt')], check=True)
        print('Updated to ' + commit, flush=True)
    finally:
        if args.restart:
            flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            with (root / 'logs' / 'restart.log').open('a', encoding='utf-8') as stream:
                subprocess.Popen([sys.executable, str(root / 'app.py')], cwd=root,
                                 stdin=subprocess.DEVNULL, stdout=stream, stderr=stream,
                                 creationflags=flags)

if __name__ == '__main__':
    main()
