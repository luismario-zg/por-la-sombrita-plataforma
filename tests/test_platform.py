"""Pruebas de autorización, integridad del historial y seguridad del prototipo."""
import io,json,hashlib,time
import pytest
from werkzeug.security import generate_password_hash
from app import create_app
from app.core import connect,now,REVIEW_FIELDS

PASS='Clave-solo-para-pruebas-123'
CONTENT='<h2 id="sombra">Una sección</h2><p>La revisión será semanal.</p>'

@pytest.fixture
def app(tmp_path):
    mirror=tmp_path/'mirror';mirror.mkdir();(mirror/'guia.txt').write_text('Contenido público de prueba.')
    report=tmp_path/'reporte-temporal.html';report.write_text('<!doctype html><title>Reporte temporal</title><style>body{color:#111}</style><p>Revisión comunitaria.</p>')
    index=tmp_path/'planeacion.json';index.write_text(json.dumps({'version':1,'items':[
        {'key':'D01','title':'Participación anónima','question':'¿Cómo se participa?','classification':'Directrices y valores','origin':'Prueba'},
        {'key':'D25','title':'Playlist colectiva','question':'¿Quién la administra?','classification':'Desarrollo','origin':'Prueba'},
    ]}))
    a=create_app({'TESTING':True,'DATABASE':str(tmp_path/'prueba.sqlite3'),'BASE_URL':'http://localhost','COOKIE_NAME':'pls-test','COOKIE_SECURE':False,'AI_ENABLED':True,'PROTON_MIRROR':str(mirror),'DEVELOPMENT_REPORT':str(report),'DEVELOPMENT_INDEX':str(index),'TRANSCRIBE_API_KEY':'test-key'})
    with connect(a.config['DATABASE']) as c:
        for name,role in [('owner','owner'),('member','member'),('reviewer','reviewer'),('reader','reader'),('temporary','member')]:
            c.execute('INSERT INTO users(username,name,password_hash,role,must_change,created) VALUES(?,?,?,?,?,?)',(name,name,generate_password_hash(PASS),role,int(name=='temporary'),now()))
        c.execute('INSERT INTO documents(slug,title,version,html,updated) VALUES(?,?,1,?,?)',('plan','Plan',CONTENT,now()))
        c.execute('INSERT INTO revisions(document,version,html,status,reason,created) VALUES(?,1,?,?,?,?)',('plan',CONTENT,'proposal','Inicial',now()))
        c.execute("INSERT INTO documents(slug,title,version,html,updated,hidden) VALUES('archivo-proton','Archivo Proton',1,'<h2 id=\"resource\">Recurso</h2>',?,1)",(now(),))
        c.execute("INSERT INTO drive_items(path,parent_path,name,kind,source_revision,version,active,indexed) VALUES('','','Por La Sombrita MTY General','folder','raiz',1,1,?)",(now(),))
        c.execute("INSERT INTO drive_items(path,parent_path,name,kind,media_type,size,local_rel,source_revision,version,active,indexed) VALUES('guia.txt','','guia.txt','file','text/plain',28,'guia.txt','r1',1,1,?)",(now(),))
    return a

def client(app,name=None):
    c=app.test_client()
    if name:
        r=post(c,'/api/login',{'username':name,'password':PASS});assert r.status_code==200,r.json
    return c

def post(c,url,data,**headers):
    s=c.get('/api/session').json
    h={'Origin':'http://localhost','X-CSRF-Token':s['csrf']};h.update(headers)
    return c.post(url,json=data,headers=h)

def create_thread(c,**fields):
    d={'document':'plan','version':1,'section':'sombra','title':'Frecuencia de revisión','body':'Propongo revisión quincenal.','quote':'La revisión será semanal.','prefix':'','suffix':''};d.update(fields)
    return post(c,'/api/threads',d)

def review_payload():
    r={k:'' for k in REVIEW_FIELDS};r.update(topic='Frecuencia de revisión del plan.',question='¿Semanal o quincenal?',summary='Se comparó la frecuencia de revisión.',current_text='La revisión será semanal.',proposed_text='La revisión será quincenal.',evidence='#1');return r

def save_review(c,tid=1,count=1,version=1):
    return post(c,f'/api/threads/{tid}/review',{'review':review_payload(),'comment_count':count,'document_version':version})

def approve(app,c,tid=1):
    with connect(app.config['DATABASE']) as db:rid=db.execute('SELECT MAX(id) FROM reviews WHERE thread_id=?',(tid,)).fetchone()[0]
    return post(c,f'/api/threads/{tid}/approve-review',{'review_id':rid})

def test_public_read_and_no_anonymous_mutation(app):
    c=client(app)
    for url in ['/','/plan.html','/archivo-proton','/archivo-proton/1','/archivo-proton/2','/miembros','/revision','/discusiones','/discusiones?estado=history','/documentos/plan/versiones','/sitemap.xml']:assert c.get(url).status_code==200
    assert create_thread(c).status_code==401
    assert c.get('/administracion').status_code==401
    assert c.get('/.env').status_code==404
    assert c.get('/api/users').status_code==404
    assert c.get('/archivo-proton.html').status_code==404
    assert c.get('/editar/archivo-proton').status_code in [401,404]

def test_development_plan_is_public_and_report_is_isolated(app):
    c=client(app)
    page=c.get('/planeacion-desarrollo-plataforma')
    assert page.status_code==200 and b'Planeaci' in page.data and b'D01' in page.data
    assert 'microphone=(self)' in page.headers['Permissions-Policy']
    report=c.get('/planeacion-desarrollo-plataforma/informe')
    assert report.status_code==200 and b'Reporte temporal' in report.data
    assert report.headers['X-Robots-Tag']=='noindex, nofollow, noarchive'
    assert report.headers['X-Frame-Options']=='SAMEORIGIN'
    policy=report.headers['Content-Security-Policy']
    assert "default-src 'none'" in policy and "media-src data:" in policy and "connect-src 'none'" in policy
    for alias in ['/reporte-temporal','/reporte_temporal']:
        response=c.get(alias);assert response.status_code==302 and response.headers['Location']=='/planeacion-desarrollo-plataforma'
    sitemap=c.get('/sitemap.xml').text
    assert '/planeacion-desarrollo-plataforma</loc>' in sitemap and '/planeacion-desarrollo-plataforma/informe' not in sitemap
    robots=c.get('/robots.txt').text
    assert 'Disallow: /planeacion-desarrollo-plataforma/informe' in robots

def test_development_responses_require_account_and_preserve_history(app):
    anonymous=client(app)
    assert post(anonymous,'/api/development/items/D01/responses',{'body':'Una respuesta.'}).status_code==401
    reader=client(app,'reader')
    assert post(reader,'/api/development/items/D01/responses',{'body':'No debe guardarse.'}).status_code==403
    member=client(app,'member')
    first=post(member,'/api/development/items/D01/responses',{'body':'Primera respuesta revisable.'})
    second=post(member,'/api/development/items/D01/responses',{'body':'Segunda respuesta con más detalle.'})
    assert first.status_code==201 and second.status_code==201
    with connect(app.config['DATABASE']) as database:
        assert database.execute("SELECT status FROM development_items WHERE key='D01'").fetchone()[0]=='answered'
        assert database.execute("SELECT COUNT(*) FROM development_responses WHERE item_key='D01'").fetchone()[0]==2
    page=anonymous.get('/planeacion-desarrollo-plataforma')
    assert b'Primera respuesta revisable.' in page.data and b'Segunda respuesta con m' in page.data

def test_voice_transcription_returns_editable_draft_without_saving(app,monkeypatch):
    monkeypatch.setattr('app.transcribe_audio',lambda payload,mimetype,config:'Texto transcrito para revisar.')
    member=client(app,'member');session=member.get('/api/session').json
    response=member.post('/api/development/transcribe',data={'audio':(io.BytesIO(b'a'*1500),'respuesta.webm')},content_type='multipart/form-data',headers={'Origin':'http://localhost','X-CSRF-Token':session['csrf']})
    assert response.status_code==200 and response.json=={'text':'Texto transcrito para revisar.'}
    with connect(app.config['DATABASE']) as database:assert database.execute('SELECT COUNT(*) FROM development_responses').fetchone()[0]==0

def test_csrf_and_origin(app):
    c=client(app,'owner');s=c.get('/api/session').json
    assert c.post('/api/threads',json={},headers={'Origin':'http://localhost'}).status_code==403
    assert c.post('/api/threads',json={},headers={'Origin':'https://otro.example','X-CSRF-Token':s['csrf']}).status_code==403
    assert c.post('/api/threads',data='{}',headers={'Origin':'http://localhost','X-CSRF-Token':s['csrf']}).status_code==415

def test_login_rotation_logout_and_password_change(app):
    c=client(app);c.get('/api/session');old=c.get_cookie('pls-test').value
    assert post(c,'/api/login',{'username':'temporary','password':PASS}).status_code==200
    assert c.get_cookie('pls-test').value!=old
    assert create_thread(c).status_code==403
    assert post(c,'/api/password',{'current':PASS,'password':'short'}).status_code==400
    assert post(c,'/api/password',{'current':PASS,'password':'Nueva-clave-larga-de-prueba'}).status_code==200
    assert create_thread(c).status_code==201
    cookie=c.get_cookie('pls-test');assert cookie.http_only and cookie.same_site=='Lax'
    assert post(c,'/api/logout',{}).status_code==200
    assert create_thread(c).status_code==401

def test_password_hash_and_failed_login_limit(app):
    with connect(app.config['DATABASE']) as db:
        h=db.execute("SELECT password_hash FROM users WHERE username='owner'").fetchone()[0];assert PASS not in h and h.startswith('scrypt:')
    c=client(app)
    for _ in range(10):assert post(c,'/api/login',{'username':'owner','password':'incorrecta'}).status_code==401
    assert post(c,'/api/login',{'username':'owner','password':PASS}).status_code==429

def test_permissions_are_enforced_and_last_owner_kept(app):
    c=client(app,'member');assert create_thread(c).status_code==201
    assert save_review(c).status_code==403
    assert post(c,'/api/threads/1/state',{'action':'archive','summary':'No'}).status_code==403
    assert post(c,'/api/users/2',{'role':'owner','active':True,'membership':'pending'}).status_code==403
    r=client(app,'reader');assert create_thread(r).status_code==403
    owner=client(app,'owner')
    assert post(owner,'/api/users/1',{'role':'member','active':True,'membership':'pending'}).status_code==409
    assert post(owner,'/api/users/2',{'role':'reader','active':True,'membership':'pending'}).status_code==200
    assert create_thread(c).status_code==401 # Sus sesiones fueron revocadas.
    assert post(owner,'/api/users/3',{'role':'reviewer','active':True,'membership':'official','reference':''}).status_code==400

def test_validates_anchor_and_document_revision(app):
    c=client(app,'member')
    assert create_thread(c,quote='Un texto que no existe').status_code==400
    assert create_thread(c,section='otra').status_code==400
    assert create_thread(c,version=5).status_code==409
    assert create_thread(c,quote='').status_code==201
    with connect(app.config['DATABASE']) as db:
        t=db.execute('SELECT * FROM threads').fetchone();assert t['section_snapshot']=='La revisión será semanal.' and t['version']==1

def test_review_is_stale_with_new_comments(app):
    owner=client(app,'owner');create_thread(owner)
    assert save_review(owner).status_code==200;assert approve(app,owner).status_code==200
    member=client(app,'member');assert post(member,'/api/threads/1/comments',{'body':'Tengo otra opinión.'}).status_code==200
    assert save_review(owner,count=1).status_code==409
    assert approve(app,owner).status_code==409
    page=owner.get('/discusiones/1');assert 'Desactualizada' in page.text

def test_archive_no_edit_reopen_keeps_history(app):
    c=client(app,'owner');create_thread(c)
    assert post(c,'/api/threads/1/state',{'action':'archive','summary':'Consenso','outcome':'unchanged','consensus_confirmed':True}).status_code==409
    save_review(c);approve(app,c)
    assert post(c,'/api/threads/1/state',{'action':'propose_close','summary':'Propongo cerrar sin cambio.'}).status_code==200
    assert post(c,'/api/threads/1/state',{'action':'archive','summary':'Consenso: mantener frecuencia.','outcome':'unchanged','consensus_confirmed':True}).status_code==200
    assert post(c,'/api/threads/1/comments',{'body':'Tarde'}).status_code==409
    assert 'Frecuencia de revisión' in c.get('/discusiones?estado=history').text
    assert post(c,'/api/threads/1/state',{'action':'reopen','summary':'Apareció evidencia nueva.'}).status_code==200
    assert 'Frecuencia de revisión' in c.get('/discusiones?estado=history').text
    assert 'Consenso: mantener frecuencia.' in c.get('/discusiones/1').text
    with connect(app.config['DATABASE']) as db:assert db.execute('SELECT COUNT(*) FROM comments').fetchone()[0]==1

def test_edit_archive_requires_linked_revision_and_fresh_review(app):
    c=client(app,'owner');create_thread(c);save_review(c);approve(app,c)
    data={'version':1,'html':'<h2 id="sombra">Una sección</h2><p>La revisión será quincenal.</p><script>alert(1)</script><a href="javascript:alert(1)">X</a>','reason':'Consenso del hilo','status':'official','reference':'Acta de prueba','source_thread':1}
    r=post(c,'/api/documents/plan',data);assert r.status_code==200,r.json;rid=r.json['revision_id']
    assert post(c,'/api/documents/plan',data).status_code==409
    assert '<script>alert(1)</script>' not in c.get('/plan.html').text and 'javascript:alert' not in c.get('/plan.html').text
    assert 'La revisión será semanal.' in c.get('/documentos/plan/versiones/1').text
    post(c,'/api/threads/1/state',{'action':'propose_close','summary':'Cerrar con edición.'})
    archive={'action':'archive','summary':'Se acordó revisión quincenal.','outcome':'edited','revision_id':rid,'consensus_confirmed':True}
    assert post(c,'/api/threads/1/state',archive).status_code==409
    assert save_review(c,version=2).status_code==200;assert approve(app,c).status_code==200
    assert post(c,'/api/threads/1/state',{**archive,'revision_id':999}).status_code==400
    assert post(c,'/api/threads/1/state',archive).status_code==200
    assert 'Terminó con edición' in c.get('/discusiones/1').text

def test_xss_and_ai_jobs_permissions(app):
    c=client(app,'member');create_thread(c,body='<script>window.pwned=1</script>',title='<img src=x onerror=alert(1)>')
    page=c.get('/discusiones/1');assert '&lt;script&gt;' in page.text and '<script>window.pwned' not in page.text
    assert post(c,'/api/threads/1/ai',{}).status_code==403
    r=client(app,'reviewer');assert post(r,'/api/threads/1/ai',{}).status_code==202
    assert post(r,'/api/threads/1/ai',{}).status_code==409
    assert 'frame-ancestors' in page.headers['Content-Security-Policy']

def test_reset_password_revokes_sessions_and_not_public(app):
    c=client(app,'owner');m=client(app,'member')
    r=post(c,'/api/users/2/reset-password',{});assert r.status_code==200 and len(r.json['password'])>=12
    assert create_thread(m).status_code==401
    assert r.json['password'] not in c.get('/miembros').text
    with connect(app.config['DATABASE']) as db:
        for e in db.execute('SELECT detail FROM events'):assert r.json['password'] not in e['detail']

def test_drive_file_is_read_only_and_discussable(app):
    public=client(app)
    page=public.get('/archivo-proton/2');assert 'Contenido público de prueba.' in page.text
    download=public.get('/archivo-proton/contenido/2');assert download.status_code==200
    assert download.headers['Content-Disposition'].startswith('attachment;')
    assert public.post('/api/archive/threads',json={}).status_code==403
    member=client(app,'member')
    response=post(member,'/api/archive/threads',{'drive_item_id':2,'title':'Conversar sobre la guía','body':'Propongo revisar su vigencia.'})
    assert response.status_code==201,response.json
    thread=member.get('/discusiones/1');assert 'Archivo: guia.txt' in thread.text and 'Propongo revisar su vigencia.' in thread.text
    assert 'Editar el documento a partir' not in thread.text
    assert 'Conversar sobre la guía' in public.get('/archivo-proton/2').text
    assert 'Conversar sobre la guía' in public.get('/discusiones').text

def test_drive_thread_stales_when_index_version_changes(app):
    owner=client(app,'owner');post(owner,'/api/archive/threads',{'drive_item_id':2,'title':'Vigencia','body':'¿Sigue vigente?'})
    assert save_review(owner).status_code==200;assert approve(app,owner).status_code==200
    with connect(app.config['DATABASE']) as database:database.execute("UPDATE drive_items SET version=2,source_revision='r2' WHERE id=2")
    assert 'Desactualizada' in owner.get('/discusiones/1').text
    assert save_review(owner,version=1).status_code==409
    assert save_review(owner,version=2).status_code==200
    assert approve(app,owner).status_code==200
    post(owner,'/api/threads/1/state',{'action':'propose_close','summary':'Cierre propuesto.'})
    assert post(owner,'/api/threads/1/state',{'action':'archive','summary':'Se acordó conservar el archivo.','outcome':'edited','revision_id':1,'consensus_confirmed':True}).status_code==400
    assert post(owner,'/api/threads/1/state',{'action':'archive','summary':'Se acordó conservar el archivo.','outcome':'unchanged','consensus_confirmed':True}).status_code==200
