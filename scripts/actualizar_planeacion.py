#!/usr/bin/env python3
"""Actualiza estados o añade dudas después de una ejecución revisada."""
import argparse
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core import connect, now
from app.development import PLAN_STATUSES

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--database',default='')
sub=parser.add_subparsers(dest='command',required=True)
status=sub.add_parser('estado');status.add_argument('--item',required=True);status.add_argument('--status',required=True,choices=PLAN_STATUSES);status.add_argument('--nota',required=True)
add=sub.add_parser('agregar');add.add_argument('--item',required=True);add.add_argument('--titulo',required=True);add.add_argument('--pregunta',required=True);add.add_argument('--clasificacion',required=True);add.add_argument('--origen',default='Seguimiento de implementación')
args=parser.parse_args()
data=Path(os.environ.get('PLS_DATA_DIR',str(Path.home()/'.local/share/pls-plataforma')))
database=args.database or os.environ.get('PLS_DATABASE',str(data/'plataforma.sqlite3'))
stamp=now()
with connect(database) as connection:
    connection.execute('BEGIN IMMEDIATE')
    if args.command=='estado':
        exists=connection.execute('SELECT 1 FROM development_items WHERE key=?',(args.item,)).fetchone()
        if not exists:parser.error('El item no existe.')
        connection.execute('UPDATE development_items SET status=?,updated=? WHERE key=?',(args.status,stamp,args.item))
        connection.execute("INSERT INTO development_events(item_key,actor,kind,detail,created) VALUES(?,NULL,'status_changed',?,?)",(args.item,args.nota.strip(),stamp))
    else:
        if len(args.item)>30 or not args.item.replace('-','').isalnum():parser.error('El identificador no es válido.')
        order=connection.execute('SELECT COALESCE(MAX(sort_order),0)+1 FROM development_items').fetchone()[0]
        connection.execute("INSERT INTO development_items(key,title,question,classification,origin,sort_order,status,created,updated) VALUES(?,?,?,?,?,?,'pending',?,?)",(args.item,args.titulo.strip(),args.pregunta.strip(),args.clasificacion.strip(),args.origen.strip(),order,stamp,stamp))
        connection.execute("INSERT INTO development_events(item_key,actor,kind,detail,created) VALUES(?,NULL,'created','Se añadió una duda pendiente después de revisar la implementación.',?)",(args.item,stamp))
print('Planeación actualizada:',args.item)
