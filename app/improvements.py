"""La plataforma conserva el seguimiento; GitHub es el espacio técnico vinculado."""
import json
import os
import subprocess
import tempfile
from pathlib import Path
from flask import Blueprint,abort,current_app,jsonify,render_template,request
from .core import connect,db,field,limited,now,require,user

improvements=Blueprint('improvements',__name__)
REPO='luismario-zg/por-la-sombrita-plataforma'
STATUSES={'proposed':'Propuesta','in_progress':'En desarrollo','review':'Pendiente de verificar','implemented':'Implementada','deferred':'Aplazada','closed':'Cerrada sin implementación'}
SCHEMA_SQL='''
CREATE TABLE IF NOT EXISTS improvements(id INTEGER PRIMARY KEY,title TEXT NOT NULL,body TEXT NOT NULL,author INTEGER NOT NULL REFERENCES users(id),status TEXT NOT NULL DEFAULT 'proposed',version INTEGER NOT NULL DEFAULT 1,issue_number INTEGER UNIQUE,github_state TEXT NOT NULL DEFAULT '',sync_state TEXT NOT NULL DEFAULT 'idle',sync_error TEXT NOT NULL DEFAULT '',synced TEXT,created TEXT NOT NULL,updated TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS improvement_events(id INTEGER PRIMARY KEY,improvement INTEGER NOT NULL REFERENCES improvements(id),actor INTEGER REFERENCES users(id),body TEXT NOT NULL,source TEXT NOT NULL DEFAULT 'platform',external_id TEXT UNIQUE,created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS improvement_outbox(event INTEGER PRIMARY KEY REFERENCES improvement_events(id) ON DELETE CASCADE,created TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_improvements_sync ON improvements(sync_state,id);
'''

def developer():
    u=require()
    if not u['developer_access']:abort(403,description='Solo desarrolladores pueden revisar cambios de la plataforma.')
    return u


def body():
    data=request.get_json()
    if not isinstance(data,dict):abort(400,description='Solicitud inválida.')
    return data

@improvements.get('/mejoras')
def page():
    rows=db().execute('SELECT i.*,u.name AS author_name FROM improvements i JOIN users u ON u.id=i.author ORDER BY i.id DESC').fetchall()
    return render_template('improvements.html',title='Mejoras de la plataforma',items=rows,statuses=STATUSES)

@improvements.get('/mejoras/<int:ident>')
def detail(ident):
    row=db().execute('SELECT i.*,u.name AS author_name FROM improvements i JOIN users u ON u.id=i.author WHERE i.id=?',(ident,)).fetchone()
    if not row:abort(404)
    events=db().execute('''SELECT e.*,COALESCE(ga.display_name,u.name) AS author_name,
        CASE WHEN ga.id IS NULL THEN 0 ELSE 1 END AS guest_author
        FROM improvement_events e LEFT JOIN users u ON u.id=e.actor
        LEFT JOIN guest_attributions ga ON ga.target_type='improvement_event' AND ga.target_id=e.id
        WHERE improvement=? ORDER BY e.id''',(ident,)).fetchall()
    return render_template('improvement.html',title=row['title'],item=row,events=events,statuses=STATUSES,repo=REPO)

@improvements.post('/api/improvements')
def create():
    u=require('owner','admin','reviewer','member');data=body();title=field(data,'title',160);description=field(data,'body',10000)
    limited('improvement:'+str(u['id']),20,3600);stamp=now()
    with db() as c:
        ident=c.execute('INSERT INTO improvements(title,body,author,created,updated) VALUES(?,?,?,?,?)',(title,description,u['id'],stamp,stamp)).lastrowid
        c.execute('INSERT INTO improvement_events(improvement,actor,body,created) VALUES(?,?,?,?)',(ident,u['id'],'Se registró la propuesta en la plataforma.',stamp))
    return jsonify(id=ident,url=f'/mejoras/{ident}'),201

@improvements.post('/api/improvements/<int:ident>')
def update(ident):
    u=developer();data=body();action=field(data,'action',30);c=db();c.execute('BEGIN IMMEDIATE')
    row=c.execute('SELECT * FROM improvements WHERE id=?',(ident,)).fetchone()
    if not row:abort(404)
    if action=='status':
        status=field(data,'status',30);note=field(data,'note',4000)
        if status not in STATUSES:abort(400,description='Estado inválido.')
        if data.get('version')!=row['version']:abort(409,description='El seguimiento cambió; recarga antes de actualizar.')
        if row['sync_state'] in ['publish','push','pull','running']:abort(409,description='Espera a que termine la sincronización antes de cambiar el estado.')
        if status=='implemented' and not field(data,'verification',2000,False):abort(400,description='Registra cómo comprobaste la implementación y su referencia.')
        if status=='implemented':note+='\nVerificación: '+data['verification'].strip()
        stamp=now();c.execute('UPDATE improvements SET status=?,version=version+1,updated=?,sync_state=? WHERE id=?',(status,stamp,'push' if row['issue_number'] else 'idle',ident))
        event_id=c.execute("INSERT INTO improvement_events(improvement,actor,body,source,created) VALUES(?,?,?,'status',?)",(ident,u['id'],STATUSES[status]+': '+note,stamp)).lastrowid
        c.execute('INSERT INTO improvement_outbox(event,created) VALUES(?,?)',(event_id,stamp))
    elif action in ['publish','pull']:
        if row['sync_state'] in ['publish','push','pull','running']:abort(409,description='La sincronización ya está en curso.')
        if action=='publish':
            if row['issue_number']:abort(409,description='Esta propuesta ya tiene un ticket.')
            if data.get('public_confirmed') is not True:abort(400,description='Revisa y confirma que el título y la descripción pueden publicarse en GitHub.')
        elif not row['issue_number']:abort(400,description='Primero publica el ticket.')
        c.execute('UPDATE improvements SET sync_state=?,sync_error=? WHERE id=?',(action,'',ident))
    else:abort(400,description='Acción desconocida.')
    c.commit();return jsonify(ok=True)

@improvements.post('/api/improvements/<int:ident>/comments')
def comment(ident):
    u=require('owner','admin','reviewer','member');text=field(body(),'body',4000);limited('improvement-comment:'+str(u['id']),60,3600)
    with db() as c:
        row=c.execute('SELECT issue_number,sync_state FROM improvements WHERE id=?',(ident,)).fetchone()
        if not row:abort(404)
        stamp=now();event_id=c.execute('INSERT INTO improvement_events(improvement,actor,body,created) VALUES(?,?,?,?)',(ident,u['id'],text,stamp)).lastrowid
        c.execute('INSERT INTO improvement_outbox(event,created) VALUES(?,?)',(event_id,stamp))
        if row['issue_number'] and row['sync_state'] in ['idle','error']:
            # Un comentario no debe reabrir/cerrar el issue: pull sincroniza eventos
            # y después trae el estado remoto sin empujarlo desde la plataforma.
            c.execute("UPDATE improvements SET sync_state='pull',sync_error='' WHERE id=?",(ident,))
    return jsonify(ok=True)

def github(args,payload=None):
    """Solo el consumidor invoca gh con argumentos controlados; nunca un shell."""
    command=['gh',*args]
    if payload is not None:command+=['--input','-']
    result=subprocess.run(command,input=json.dumps(payload) if payload is not None else None,capture_output=True,text=True,timeout=40)
    if result.returncode:raise RuntimeError('GitHub no pudo completar la sincronización. Revisa permisos o disponibilidad e inténtalo de nuevo.')
    raw=result.stdout.strip()
    if '--paginate' in args:
        # Versiones antiguas de gh no tienen --slurp: emiten objetos JSON
        # consecutivos. Decodificar cada página sin depender de una actualización.
        decoder=json.JSONDecoder();pages=[];position=0
        while position<len(raw):
            page,position=decoder.raw_decode(raw,position);pages.append(page)
            while position<len(raw) and raw[position].isspace():position+=1
        return pages
    return json.loads(raw) if raw else {}


def github_paginated(args):
    """Devuelve una sola lista aunque gh produzca varias páginas JSON."""
    pages=github([*args,'--paginate'])
    if not isinstance(pages,list):raise RuntimeError('GitHub devolvió una página inválida.')
    if pages and all(isinstance(page,list) for page in pages):return [item for page in pages for item in page]
    return pages


def validate_guest_improvement(connection,target_id):
    try:ident=int(target_id)
    except (TypeError,ValueError):abort(404)
    row=connection.execute('SELECT id,title,body,version FROM improvements WHERE id=?',(ident,)).fetchone()
    if not row:abort(404)
    return {'label':'Mejora: '+row['title'],'snapshot':row['title']+'\n\n'+row['body'],'version':row['version']}


def publish_guest_improvement(connection,submission,moderator_id,stamp):
    target=validate_guest_improvement(connection,submission['target_id'])
    ident=int(submission['target_id'])
    event_id=connection.execute("INSERT INTO improvement_events(improvement,actor,body,source,created) VALUES(?,?,?,'guest',?)",
        (ident,moderator_id,submission['body'],stamp)).lastrowid
    # El comentario ya es público en la plataforma. Si existe issue, la outbox lo
    # lleva a GitHub sin otorgar a la persona invitada permisos técnicos.
    connection.execute('INSERT INTO improvement_outbox(event,created) VALUES(?,?)',(event_id,stamp))
    row=connection.execute('SELECT issue_number,sync_state FROM improvements WHERE id=?',(ident,)).fetchone()
    if row['issue_number'] and row['sync_state'] in ['idle','error']:
        connection.execute("UPDATE improvements SET sync_state='pull',sync_error='' WHERE id=?",(ident,))
    return {'target_type':'improvement_event','target_id':event_id,'url':f'/mejoras/{ident}#evento-{event_id}'}

def process_github_job(path,base_url):
    with connect(path) as c:
        c.execute('BEGIN IMMEDIATE');row=c.execute("SELECT * FROM improvements WHERE sync_state IN ('publish','push','pull') ORDER BY id LIMIT 1").fetchone()
        if not row:return False
        c.execute("UPDATE improvements SET sync_state='running' WHERE id=?",(row['id'],))
    try:
        issue=row['issue_number'];state=row['sync_state'];marker=f'<!-- pls-improvement:{row["id"]} -->'
        if state=='publish':
            # Reconciliar si la API creó el issue y el proceso se interrumpió antes de guardar.
            found=github(['api','search/issues','--method','GET','-f',f'q=repo:{REPO} is:issue "pls-improvement:{row["id"]}" in:body','-f','per_page=20'])
            existing=next((item for item in found.get('items',[]) if marker in (item.get('body') or '')),None)
            issue_data=existing or github(['api',f'repos/{REPO}/issues','--method','POST'],{'title':row['title'],'body':row['body']+'\n\nSeguimiento comunitario: '+base_url+f'/mejoras/{row["id"]}\n\n'+marker})
            issue=issue_data['number']
            # Publicar el enlace en cuanto GitHub lo devuelve, antes de traer comentarios.
            with connect(path) as c:c.execute('UPDATE improvements SET issue_number=? WHERE id=?',(issue,row['id']))
        with connect(path) as c:
            pending=c.execute('''SELECT e.id,e.body,e.source,ga.display_name FROM improvement_outbox o JOIN improvement_events e ON e.id=o.event
                LEFT JOIN guest_attributions ga ON ga.target_type='improvement_event' AND ga.target_id=e.id
                WHERE e.improvement=? AND e.source IN ('platform','guest','status') AND e.actor IS NOT NULL ORDER BY e.id''',(row['id'],)).fetchall()
        # Un cambio de estado pendiente sobrevive a un error y también se empuja
        # cuando la persona reintenta con la acción genérica "pull".
        if state in ['publish','push'] or any(item['source']=='status' for item in pending):
            target='closed' if row['status'] in ['implemented','closed'] else 'open'
            github(['api',f'repos/{REPO}/issues/{issue}','--method','PATCH'],{'state':target})
        comments=github_paginated(['api',f'repos/{REPO}/issues/{issue}/comments?per_page=100'])
        existing_bodies=[comment.get('body') or '' for comment in comments]
        for item in pending:
            event_marker=f'<!-- pls-event:{item["id"]} -->'
            if not any(event_marker in body for body in existing_bodies):
                public_body=(item['display_name']+' (persona invitada):\n\n' if item['display_name'] else '')+item['body']
                github(['api',f'repos/{REPO}/issues/{issue}/comments','--method','POST'],{'body':public_body+'\n\n'+event_marker})
                existing_bodies.append(event_marker)
            with connect(path) as c:c.execute('DELETE FROM improvement_outbox WHERE event=?',(item['id'],))
        remote=github(['api',f'repos/{REPO}/issues/{issue}'])
        with connect(path) as c:
            c.execute('BEGIN IMMEDIATE');live=c.execute('SELECT * FROM improvements WHERE id=?',(row['id'],)).fetchone()
            status=live['status']
            # Cerrar un ticket nunca equivale a desplegar y verificar una mejora.
            if remote['state']=='closed' and status not in ['implemented','closed']:status='review'
            # Reabrir en GitHub no borra seguimiento local; solo saca estados terminales.
            if remote['state']=='open' and live['github_state']=='closed' and status in ['implemented','closed']:status='review'
            remaining=c.execute('''SELECT 1 FROM improvement_outbox o JOIN improvement_events e ON e.id=o.event
                WHERE e.improvement=? LIMIT 1''',(row['id'],)).fetchone()
            c.execute("UPDATE improvements SET github_state=?,sync_state=?,sync_error='',synced=?,status=?,version=version+1 WHERE id=?",
                (remote['state'],'pull' if remaining else 'idle',now(),status,row['id']))
            if live['github_state']!=remote['state']:
                c.execute("INSERT INTO improvement_events(improvement,body,source,created) VALUES(?,?,'github',?)",(row['id'],'GitHub: ticket '+('cerrado; requiere verificación en la plataforma.' if remote['state']=='closed' else 'abierto.'),now()))
            for comment in comments:
                content=comment.get('body') or ''
                if '<!-- pls-event:' in content:continue
                c.execute("INSERT OR IGNORE INTO improvement_events(improvement,body,source,external_id,created) VALUES(?,?,'github',?,?)",(row['id'],f"{comment['user']['login']} (GitHub): "+content[:10000],str(comment['id']),comment['created_at']))
    except Exception:
        with connect(path) as c:c.execute("UPDATE improvements SET sync_state='error',sync_error=? WHERE id=?",('No se completó la sincronización. El seguimiento local se conserva; un desarrollador puede reintentar.',row['id']))
    return True
