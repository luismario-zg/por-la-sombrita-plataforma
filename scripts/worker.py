#!/usr/bin/env python3
"""Procesa una ficha por vez; solo guarda borradores, nunca acuerdos."""
import json,os,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core import connect, now, sections, event
from app.ai import summarize, SummaryError

path=Path(os.environ.get('PLS_DATA_DIR',str(Path.home()/'.local/share/pls-plataforma')))/'plataforma.sqlite3'

def process_one():
    with connect(path) as c:
        c.execute('BEGIN IMMEDIATE')
        job=c.execute("SELECT * FROM ai_jobs WHERE state='queued' ORDER BY id LIMIT 1").fetchone()
        if not job:return False
        actor=c.execute("SELECT 1 FROM users WHERE id=? AND active=1 AND role IN ('owner','admin','reviewer')",(job['actor'],)).fetchone()
        if not actor:
            c.execute("UPDATE ai_jobs SET state='failed',error=?,finished=? WHERE id=?",('La cuenta solicitante ya no tiene permiso de revisión.',now(),job['id']));return True
        c.execute("UPDATE ai_jobs SET state='running',started=? WHERE id=?",(now(),job['id']))
        t=c.execute('SELECT * FROM threads WHERE id=?',(job['thread_id'],)).fetchone()
        doc=c.execute('SELECT * FROM documents WHERE slug=?',(t['document'],)).fetchone()
        base_review=c.execute('SELECT COALESCE(MAX(id),0) FROM reviews WHERE thread_id=?',(t['id'],)).fetchone()[0]
        comments=[dict(x) for x in c.execute('SELECT c.id,u.name AS author,c.body,c.created FROM comments c JOIN users u ON u.id=c.author WHERE thread_id=? ORDER BY c.id',(t['id'],))]
        section=next((s for s in sections(doc['html']) if s['id']==t['section']),None)
        bases=c.execute("SELECT html FROM documents WHERE slug='bases'").fetchone()
        context='\n'.join(s['text'] for s in sections(bases['html']))[:12000] if bases else ''
        payload={'project_context':context,'title':t['title'],'document':doc['title'],'document_status':doc['status'],'original_version':t['version'],'current_version':doc['version'],'section_title':t['section_title'],'original_section':t['section_snapshot'],'selected_quote':t['quote'],'current_section':section['text'] if section else 'La sección original ya no existe; revisar versiones.','comments':comments}
    try:
        result=summarize(payload)
        with connect(path) as c:
            c.execute('BEGIN IMMEDIATE')
            live=c.execute('SELECT state FROM threads WHERE id=?',(t['id'],)).fetchone()
            if c.execute('SELECT COALESCE(MAX(id),0) FROM reviews WHERE thread_id=?',(t['id'],)).fetchone()[0]!=base_review:raise SummaryError('La ficha cambió durante la generación. Se conservó la revisión más reciente.')
            if live['state']=='archived':raise SummaryError('El hilo fue archivado durante la generación. No se reemplazó su ficha.')
            c.execute('INSERT INTO reviews(thread_id,payload,source,comment_count,document_version,author,created) VALUES(?,?,?,?,?,?,?)',(t['id'],json.dumps(result,ensure_ascii=False),'luna-high',len(comments),doc['version'],job['actor'],now()))
            # El tema visible conserva la última formulación humana hasta que se revise el borrador.
            event(c,job['actor'],'ai_draft','Se generó un borrador de ficha con Luna high; requiere revisión humana.',t['id'])
            c.execute("UPDATE ai_jobs SET state='done',finished=? WHERE id=?",(now(),job['id']))
    except Exception as e:
        message=str(e) if isinstance(e,SummaryError) else 'La generación no terminó. Revisar la integración; la conversación se conserva.'
        with connect(path) as c:c.execute("UPDATE ai_jobs SET state='failed',error=?,finished=? WHERE id=?",(message,now(),job['id']))
    return True

if __name__=='__main__':
    # Un servicio dedicado ejecuta un único consumidor. Recuperación explícita al reiniciar.
    with connect(path) as c:c.execute("UPDATE ai_jobs SET state='failed',error='El servicio se reinició durante la generación. Puedes solicitarla nuevamente.',finished=? WHERE state='running'",(now(),))
    while True:
        if not process_one():time.sleep(3)
