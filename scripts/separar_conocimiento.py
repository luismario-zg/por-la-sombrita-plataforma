#!/usr/bin/env python3
"""Separa solo los tres documentos de Conocimiento conservando sus versiones."""
import argparse
import hashlib
import sqlite3
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.core import connect,event
from scripts.importar_evolucion import parse_source,compare,apply_plan

ORIGINAL_HASH='422089d46cc3a33058f0b8c0adbd40c9643c40d9c328f52b2fc72dc8ef8aee12'
SLUGS=('conocimiento','comunidades-abiertas','comunidad-pls')

def migrate(connection,apply=False):
    if apply:connection.execute('BEGIN IMMEDIATE')
    documents=[parse_source(ROOT/'contenido/evolucion'/f'{slug}.html') for slug in SLUGS]
    current=connection.execute("SELECT html FROM documents WHERE slug='conocimiento'").fetchone()
    if current and current['html']!=documents[0]['html'] and hashlib.sha256(current['html'].encode()).hexdigest()!=ORIGINAL_HASH:
        raise RuntimeError('Conocimiento fue editado después de preparar la separación. Reconciliar esa versión antes de continuar.')
    plan=compare(connection,documents)
    if not apply:return [(action,doc['slug']) for action,doc,_ in plan]
    result=apply_plan(connection,plan)
    if any(action!='sin-cambios' for action,_,_ in plan):
        event(connection,None,'knowledge_split','Conocimiento se separó en Comunidades Abiertas y Comunidad PLS. La página anterior conserva accesos y versiones.')
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',required=True,type=Path)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--backup-confirmed',action='store_true')
    args=parser.parse_args()
    if not args.database.is_file():parser.error('La base debe existir.')
    if args.apply and not args.backup_confirmed:parser.error('Confirma el respaldo con --backup-confirmed antes de aplicar.')
    connection=connect(args.database) if args.apply else sqlite3.connect(f'file:{args.database}?mode=ro',uri=True)
    connection.row_factory=sqlite3.Row
    with connection:print(migrate(connection,args.apply))
