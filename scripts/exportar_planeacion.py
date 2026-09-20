#!/usr/bin/env python3
"""Exporta preguntas, respuestas y seguimiento para la siguiente ejecución de Codex."""
import json
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core import connect

data=Path(os.environ.get('PLS_DATA_DIR',str(Path.home()/'.local/share/pls-plataforma')))
database=os.environ.get('PLS_DATABASE',str(data/'plataforma.sqlite3'))
with connect(database) as connection:
    items=[dict(row) for row in connection.execute('SELECT * FROM development_items ORDER BY sort_order,key')]
    for item in items:
        item['responses']=[dict(row) for row in connection.execute('''SELECT r.id,r.body,r.created,u.name AS author
            FROM development_responses r JOIN users u ON u.id=r.author WHERE r.item_key=? ORDER BY r.id''',(item['key'],))]
        item['events']=[dict(row) for row in connection.execute('''SELECT e.id,e.kind,e.detail,e.created,u.name AS actor
            FROM development_events e LEFT JOIN users u ON u.id=e.actor WHERE e.item_key=? ORDER BY e.id''',(item['key'],))]
print(json.dumps({'items':items},ensure_ascii=False,indent=2))
