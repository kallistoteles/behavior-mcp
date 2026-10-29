#!/usr/bin/env python3
"""Verify the off-disk backup parts, bundle, and optionally an extracted repository."""
import argparse
import hashlib
import json
import os
import stat
from pathlib import Path

base=Path(__file__).resolve().parent
manifest=json.loads((base/'MANIFEST.json').read_text())
parser=argparse.ArgumentParser()
parser.add_argument('--restored',type=Path,help='Extracted behavior-mcp repository directory, before Git refreshes its index')
args=parser.parse_args()
def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
whole=hashlib.sha256();total=0
for part in manifest['archive']['parts']:
    path=base/part['name']
    assert path.stat().st_size==part['bytes'],path
    assert digest(path)==part['sha256'],path
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            whole.update(block);total+=len(block)
assert total==manifest['archive']['bytes']
assert whole.hexdigest()==manifest['archive']['sha256']
bundle=manifest['git_bundle'];assert digest(base/bundle['name'])==bundle['sha256']
if args.restored:
    for rel,entry in manifest['entries'].items():
        path=args.restored/rel;metadata=path.lstat()
        assert stat.S_IMODE(metadata.st_mode)==entry['mode'],('mode',rel)
        assert metadata.st_mtime_ns==entry['mtime_ns'],('mtime',rel)
        if entry['kind']=='file':assert path.is_file() and digest(path)==entry['sha256'],rel
        elif entry['kind']=='symlink':assert path.is_symlink() and os.readlink(path)==entry['target'],rel
        else:assert path.is_dir() and not path.is_symlink(),rel
    found=set()
    for current,dirs,files in os.walk(args.restored,followlinks=False):
        found.update((Path(current)/name).relative_to(args.restored).as_posix() for name in dirs+files)
    assert found==set(manifest['entries']),'Restored entry set differs'
print('PASS: every archive part, combined archive checksum and Git bundle'+('; every restored file, directory, symlink, mode and modification time' if args.restored else ''))
