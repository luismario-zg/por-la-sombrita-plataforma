#!/usr/bin/env python3
"""Respaldo consistente de SQLite, fuera del repositorio público."""
from pathlib import Path
from datetime import datetime,timezone
import os,sqlite3,secrets
base=Path(os.environ.get('PLS_DATA_DIR',str(Path.home()/'.local/share/pls-plataforma')))
source=base/'plataforma.sqlite3'
if not source.is_file():raise SystemExit('No existe la base de datos a respaldar.')
out=base/'backups';out.mkdir(mode=0o700,exist_ok=True);out.chmod(0o700)
target=out/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+secrets.token_hex(3)+'.sqlite3')
fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
with sqlite3.connect(source) as src,sqlite3.connect(target) as dst:
    src.backup(dst)
    if dst.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise SystemExit('Falló la integridad del respaldo.')
print('Respaldo privado verificado:',target)
