"""Las consultas privadas y el seguimiento público mantienen límites distintos."""
import json
from app.core import connect,now
from app.assistant import process_assistant_job,public_context
from app.improvements import process_github_job
from test_platform import app,client,post

def test_assistant_private_session_and_public_sources_only(app,monkeypatch):
    first=client(app);second=client(app)
    job=post(first,'/api/assistant/questions',{'question':'¿Cómo se revisa el plan?'});assert job.status_code==202
    ident=job.json['id'];assert second.get(f'/api/assistant/questions/{ident}').status_code==404
    with connect(app.config['DATABASE']) as c:
        c.execute("INSERT INTO documents(slug,title,version,html,updated,hidden) VALUES('privado','SECRETO',1,'No debe salir',?,1)",(now(),))
        c.execute("INSERT INTO assistant_sources VALUES('https://wiki.labnuevoleon.mx/index.php?title=Wiki_LABNL','LABNL','Metodología de revisión del plan comunitario.',?)",(now(),))
        data=public_context(c,'plan comunitario',app.config['BASE_URL'])
        assert 'SECRETO' not in json.dumps(data) and 'password' not in json.dumps(data)
    seen=[]
    monkeypatch.setattr('app.assistant.run_luna_json',lambda p,s:(seen.append(p) or {'answer':'Es una propuesta revisable.','sources':[1],'uncertain':False}))
    assert process_assistant_job(app.config['DATABASE'],app.config['BASE_URL'])
    result=first.get(f'/api/assistant/questions/{ident}').json
    assert result['state']=='done' and result['result']['sources']
    assert 'No debe salir' not in seen[0]

def test_assistant_rejects_invalid_citations_and_cleans_expired_questions(app,monkeypatch):
    c=client(app);job=post(c,'/api/assistant/questions',{'question':'Revisión'})
    with connect(app.config['DATABASE']) as connection:connection.execute("INSERT INTO assistant_jobs(session_hash,question,created) VALUES('old','Dato vencido','2020-01-01T00:00:00+00:00')")
    monkeypatch.setattr('app.assistant.run_luna_json',lambda p,s:{'answer':'Inventado','sources':[999],'uncertain':False})
    assert process_assistant_job(app.config['DATABASE'],app.config['BASE_URL'])
    assert c.get('/api/assistant/questions/'+str(job.json['id'])).json['state']=='failed'
    with connect(app.config['DATABASE']) as connection:assert not connection.execute("SELECT 1 FROM assistant_jobs WHERE session_hash='old'").fetchone()

def test_github_publication_requires_developer_and_explicit_review(app,monkeypatch):
    member=client(app,'member');owner=client(app,'owner')
    created=post(member,'/api/improvements',{'title':'Error del menú','body':'El menú no permite navegar con teclado.'});assert created.status_code==201
    url='/api/improvements/'+str(created.json['id'])
    assert post(member,url,{'action':'publish','public_confirmed':True}).status_code==403
    assert post(owner,url,{'action':'publish'}).status_code==400
    assert post(owner,url,{'action':'publish','public_confirmed':True}).status_code==200
    calls=[]
    def fake(args,payload=None):
        calls.append((args,payload))
        if 'search/issues' in args:return {'items':[]}
        if args[1].endswith('/comments?per_page=100'):return []
        return {'number':31,'state':'closed'}
    monkeypatch.setattr('app.improvements.github',fake)
    assert process_github_job(app.config['DATABASE'],app.config['BASE_URL'])
    with connect(app.config['DATABASE']) as c:
        row=c.execute('SELECT * FROM improvements').fetchone()
        assert row['issue_number']==31 and row['status']=='review' and row['sync_state']=='idle'
    assert not any('development_responses' in str(call) for call in calls)
    assert post(owner,url,{'action':'status','status':'implemented','version':2,'note':'Terminado'}).status_code==400
    assert post(owner,url,{'action':'status','status':'implemented','version':2,'note':'Probado','verification':'Prueba de teclado satisfactoria, cambio abc.'}).status_code==200


def test_improvements_reject_non_object_json(app):
    member=client(app,'member');session=member.get('/api/session').json
    headers={'Origin':'http://localhost','X-CSRF-Token':session['csrf']}
    assert member.post('/api/improvements',data='null',content_type='application/json',headers=headers).status_code==400
    assert member.post('/api/improvements',json=[],headers=headers).status_code==400


def test_github_sync_pages_all_comments_pushes_outbox_and_preserves_local_progress(app,monkeypatch):
    member=client(app,'member')
    created=post(member,'/api/improvements',{'title':'Mejora enlazada','body':'Descripción pública.'})
    ident=created.json['id'];url=f'/api/improvements/{ident}'
    with connect(app.config['DATABASE']) as connection:
        connection.execute("UPDATE improvements SET issue_number=31,github_state='closed',status='in_progress' WHERE id=?",(ident,))
    assert post(member,url+'/comments',{'body':'Primer avance local.'}).status_code==200
    assert post(member,url+'/comments',{'body':'Segundo avance local.'}).status_code==200
    with connect(app.config['DATABASE']) as connection:
        row=connection.execute('SELECT sync_state FROM improvements WHERE id=?',(ident,)).fetchone()
        assert row['sync_state']=='pull'
        assert connection.execute('SELECT COUNT(*) FROM improvement_outbox').fetchone()[0]==2
    calls=[]
    def fake(args,payload=None):
        calls.append((args,payload))
        if args[1].endswith('/comments?per_page=100'):
            assert '--paginate' in args and '--slurp' not in args
            return [[{'id':901,'body':'Comentario remoto uno','user':{'login':'uno'},'created_at':'2026-09-21T00:00:00Z'}],
                [{'id':902,'body':'Comentario remoto dos','user':{'login':'dos'},'created_at':'2026-09-21T00:01:00Z'}]]
        if args[1].endswith('/comments') and '--method' in args:return {'id':999}
        if args[1].endswith('/issues/31'):return {'number':31,'state':'open'}
        raise AssertionError(args)
    monkeypatch.setattr('app.improvements.github',fake)
    assert process_github_job(app.config['DATABASE'],app.config['BASE_URL'])
    posted=[payload['body'] for args,payload in calls if args[1].endswith('/comments') and payload]
    assert len(posted)==2 and '<!-- pls-event:' in posted[0] and '<!-- pls-event:' in posted[1]
    with connect(app.config['DATABASE']) as connection:
        row=connection.execute('SELECT status,sync_state FROM improvements WHERE id=?',(ident,)).fetchone()
        assert tuple(row)==('in_progress','idle')
        assert connection.execute('SELECT COUNT(*) FROM improvement_outbox').fetchone()[0]==0
        assert connection.execute("SELECT COUNT(*) FROM improvement_events WHERE source='github'").fetchone()[0]==3 # reapertura + dos comentarios


def test_existing_github_marker_clears_outbox_without_duplicate_comment(app,monkeypatch):
    member=client(app,'member');created=post(member,'/api/improvements',{'title':'Dedupe','body':'Seguimiento.'});ident=created.json['id']
    with connect(app.config['DATABASE']) as connection:
        connection.execute("UPDATE improvements SET issue_number=44,github_state='open' WHERE id=?",(ident,))
    assert post(member,f'/api/improvements/{ident}/comments',{'body':'Ya enviado antes del corte.'}).status_code==200
    with connect(app.config['DATABASE']) as connection:event_id=connection.execute('SELECT event FROM improvement_outbox').fetchone()[0]
    calls=[]
    def fake(args,payload=None):
        calls.append((args,payload))
        if args[1].endswith('/comments?per_page=100'):return [[{'id':950,'body':f'Ya enviado\n<!-- pls-event:{event_id} -->','user':{'login':'local'},'created_at':'2026-09-21T00:00:00Z'}]]
        if args[1].endswith('/issues/44'):return {'number':44,'state':'open'}
        raise AssertionError(args)
    monkeypatch.setattr('app.improvements.github',fake)
    assert process_github_job(app.config['DATABASE'],app.config['BASE_URL'])
    assert not any(args[1].endswith('/comments') for args,payload in calls)
    with connect(app.config['DATABASE']) as connection:assert connection.execute('SELECT COUNT(*) FROM improvement_outbox').fetchone()[0]==0


def test_status_outbox_retries_original_close_after_provider_failure(app,monkeypatch):
    member=client(app,'member');owner=client(app,'owner')
    created=post(member,'/api/improvements',{'title':'Cierre durable','body':'Debe conservar la intención local.'});ident=created.json['id'];url=f'/api/improvements/{ident}'
    with connect(app.config['DATABASE']) as connection:connection.execute("UPDATE improvements SET issue_number=77,github_state='open' WHERE id=?",(ident,))
    update={'action':'status','status':'implemented','version':1,'note':'Terminado','verification':'Prueba satisfactoria, cambio def.'}
    assert post(owner,url,update).status_code==200
    def fail_patch(args,payload=None):raise RuntimeError('Proveedor no disponible')
    monkeypatch.setattr('app.improvements.github',fail_patch)
    assert process_github_job(app.config['DATABASE'],app.config['BASE_URL'])
    with connect(app.config['DATABASE']) as connection:
        row=connection.execute('SELECT status,sync_state FROM improvements WHERE id=?',(ident,)).fetchone()
        assert tuple(row)==('implemented','error')
        assert connection.execute("SELECT COUNT(*) FROM improvement_outbox o JOIN improvement_events e ON e.id=o.event WHERE e.source='status'").fetchone()[0]==1
    assert post(owner,url,{'action':'pull'}).status_code==200
    calls=[]
    def retry(args,payload=None):
        calls.append((args,payload))
        if args[1].endswith('/comments?per_page=100'):return []
        if args[1].endswith('/comments') and payload:return {'id':1001}
        if args[1].endswith('/issues/77') and '--method' in args:return {'number':77,'state':payload['state']}
        if args[1].endswith('/issues/77'):return {'number':77,'state':'closed'}
        raise AssertionError(args)
    monkeypatch.setattr('app.improvements.github',retry)
    assert process_github_job(app.config['DATABASE'],app.config['BASE_URL'])
    patches=[payload for args,payload in calls if args[1].endswith('/issues/77') and '--method' in args]
    assert patches==[{'state':'closed'}]
    with connect(app.config['DATABASE']) as connection:
        row=connection.execute('SELECT status,sync_state,github_state FROM improvements WHERE id=?',(ident,)).fetchone()
        assert tuple(row)==('implemented','idle','closed')
        assert connection.execute('SELECT COUNT(*) FROM improvement_outbox').fetchone()[0]==0

def test_completed_questions_leave_pending_list_but_keep_history(app):
    c=client(app,'owner');post(c,'/api/development/items/D01/responses',{'body':'Respuesta para resolver.'})
    with connect(app.config['DATABASE']) as connection:connection.execute("UPDATE development_items SET status='implemented' WHERE key='D01'")
    assert 'Respuesta para resolver.' not in c.get('/planeacion-desarrollo-plataforma').text
    assert 'Respuesta para resolver.' in c.get('/planeacion-desarrollo-plataforma?vista=historial').text
    assert client(app,'member').get('/planeacion-desarrollo-plataforma?vista=historial').status_code==403

def test_voice_requires_verified_membership(app,monkeypatch):
    import io
    monkeypatch.setattr('app.transcribe_audio',lambda *a:'Borrador')
    c=client(app,'member');session=c.get('/api/session').json
    def send():return c.post('/api/voice/transcribe',data={'audio':(io.BytesIO(b'a'*1500),'dictado.webm')},headers={'Origin':'http://localhost','X-CSRF-Token':session['csrf']})
    assert send().status_code==403
    with connect(app.config['DATABASE']) as connection:connection.execute("UPDATE users SET membership='official' WHERE username='member'")
    assert send().status_code==200

def test_github_pagination_supports_installed_cli_without_slurp(monkeypatch):
    from types import SimpleNamespace
    from app.improvements import github_paginated
    monkeypatch.setattr('app.improvements.subprocess.run',lambda *a,**kw:SimpleNamespace(returncode=0,stdout='[{"id":1}]\n[{"id":2}]\n'))
    assert github_paginated(['api','repos/example/example/issues/1/comments'])==[{'id':1},{'id':2}]
