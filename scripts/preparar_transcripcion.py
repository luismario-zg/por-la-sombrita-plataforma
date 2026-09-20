#!/usr/bin/env python3
"""Copia solo la configuración de transcripción a un EnvironmentFile privado."""
import argparse
import os
import re
import tempfile
from pathlib import Path

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('source',type=Path);parser.add_argument('destination',type=Path)
args=parser.parse_args()
allowed={'TRANSCRIBE_BASE_URL','TRANSCRIBE_API_KEY'}
lines=[];found=set()
for line in args.source.read_text().splitlines():
    match=re.match(r'^([A-Z][A-Z0-9_]*)=(.*)$',line)
    if match and match.group(1) in allowed:
        lines.append(line);found.add(match.group(1))
if 'TRANSCRIBE_API_KEY' not in found:raise SystemExit('La fuente no contiene TRANSCRIBE_API_KEY.')
lines.extend(['TRANSCRIBE_MODEL=gpt-transcribe','TRANSCRIBE_LANGUAGES=es,en'])
args.destination.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
descriptor,temp=tempfile.mkstemp(prefix='.transcripcion-',dir=args.destination.parent,text=True)
try:
    os.fchmod(descriptor,0o600)
    with os.fdopen(descriptor,'w') as output:output.write('\n'.join(lines)+'\n')
    os.replace(temp,args.destination)
finally:
    if os.path.exists(temp):os.unlink(temp)
print('Configuración privada de transcripción preparada:',args.destination)
