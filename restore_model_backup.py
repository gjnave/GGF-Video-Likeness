"""Reassemble private Drive backup parts and verify every byte against SHA-256."""
import argparse
import hashlib
import json
from pathlib import Path

def restore(folder,destination):
    manifest=json.loads((folder/'backup-manifest.json').read_text())
    for entry in manifest:
        relative=Path(entry['file'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unsafe model path in manifest.')
        target=destination/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():
            with target.open('rb') as f:
                if hashlib.file_digest(f,'sha256').hexdigest()==entry['sha256']:
                    print('Already verified:',target)
                    continue
            raise ValueError('Existing file does not match; preserved: '+str(target))
        partial=target.with_suffix('.restore-partial')
        if partial.exists():
            raise ValueError('An earlier incomplete restoration exists; move it aside first: '+str(partial))
        complete=hashlib.sha256()
        with partial.open('xb') as output:
            for part in entry['parts']:
                name=Path(part['name'])
                if name.name!=part['name']:
                    raise ValueError('Unsafe part name.')
                digest=hashlib.sha256()
                with (folder/name).open('rb') as source:
                    while block:=source.read(8*1024*1024):
                        digest.update(block)
                        complete.update(block)
                        output.write(block)
                if digest.hexdigest()!=part['sha256']:
                    raise ValueError('Backup part checksum mismatch: '+str(name))
        if partial.stat().st_size!=entry['size'] or complete.hexdigest()!=entry['sha256']:
            raise ValueError('Restored model checksum mismatch: '+str(target))
        partial.rename(target)
        print('Restored and verified:',target)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('backup_folder',type=Path)
    parser.add_argument('model_destination',type=Path)
    args=parser.parse_args()
    restore(args.backup_folder,args.model_destination)
