#!/usr/bin/env python3
"""Asigna el permiso de desarrollador sin cambiar el rol general de la cuenta."""
import argparse
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core import connect,now

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('username');parser.add_argument('--exclusive',action='store_true',help='Retira el permiso a las demás cuentas.')
args=parser.parse_args()
data=Path(os.environ.get('PLS_DATA_DIR',str(Path.home()/'.local/share/pls-plataforma')))
database=os.environ.get('PLS_DATABASE',str(data/'plataforma.sqlite3'))
with connect(database) as connection:
    connection.execute('BEGIN IMMEDIATE')
    target=connection.execute('SELECT id FROM users WHERE username=? AND active=1',(args.username,)).fetchone()
    if not target:raise SystemExit('No existe una cuenta activa con ese usuario.')
    if args.exclusive:connection.execute('UPDATE users SET developer_access=0')
    connection.execute('UPDATE users SET developer_access=1 WHERE id=?',(target['id'],))
    connection.execute("INSERT INTO events(thread_id,actor,kind,detail,created) VALUES(NULL,NULL,'developer_access',?,?)",(f'Se asignó el permiso de desarrollador a la cuenta {target["id"]}; exclusivo={int(args.exclusive)}.',now()))
print('Permiso de desarrollador asignado a:',args.username)
