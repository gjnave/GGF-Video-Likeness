"""Start the app's own Python; development overrides stay in private config."""
import subprocess
import sys
from pathlib import Path
from config import ROOT, settings
if __name__ == '__main__':
    local=ROOT/'.venv'/'Scripts'/'python.exe'
    configured=Path(settings()['python'])
    python=local if local.is_file() else configured
    if python.resolve()==Path(sys.executable).resolve() and not local.exists() and not (ROOT/'local_settings.json').exists():
        raise SystemExit('Run INSTALL.bat first to create the private environment.')
    raise SystemExit(subprocess.call([str(python),str(ROOT/'app.py'),*sys.argv[1:]],cwd=ROOT))
