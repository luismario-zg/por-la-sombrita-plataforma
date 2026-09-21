"""Participación invitada moderada y permisos independientes."""
import pytest
from werkzeug.security import generate_password_hash

from app.core import connect,init_db,now
from app.participation import dictation_allowed,editor_allowed,register_guest_target,register_participation
from app.improvements import publish_guest_improvement,validate_guest_improvement
from test_platform import PASS,app,client,post


@pytest.fixture
def participation_app(app):
    if 'participation' not in app.blueprints:register_participation(app)
    with connect(app.config['DATABASE']) as connection:
        connection.execute("UPDATE users SET moderator_access=1,membership='official',membership_reference='Prueba' WHERE username='owner'")
        connection.execute("INSERT INTO documents(slug,title,version,html,updated) VALUES('bases','Bases',1,'<h2 id=\"nucleo\">Núcleo</h2><p>Texto protegido.</p>',?)",(now(),))
        connection.execute("INSERT INTO revisions(document,version,html,status,reason,created) VALUES('bases',1,'<h2 id=\"nucleo\">Núcleo</h2><p>Texto protegido.</p>','proposal','Inicial',?)",(now(),))
    return app


def guest_thread_payload(**changes):
    payload={'submission_type':'thread','target_type':'document','target_id':'plan','target_version':1,
        'section':'sombra','quote':'La revisión será semanal.','prefix':'','suffix':'','title':'Otra frecuencia',
        'body':'Propongo revisar el plan cada dos semanas.','display_name':'Visitante del centro',
        'contact_name':'Nombre privado','contact_organization':'Colectivo privado','contact_phone':'+52 81 1234 5678','contact_email':'privado@example.test'}
    payload.update(changes);return payload


def test_existing_roles_keep_editor_access_and_new_insert_uses_legacy_default(tmp_path):
    database=tmp_path/'anterior.sqlite3'
    with connect(database) as connection:
        connection.executescript("""CREATE TABLE users(id INTEGER PRIMARY KEY,username TEXT UNIQUE NOT NULL,name TEXT NOT NULL,password_hash TEXT NOT NULL,role TEXT NOT NULL,must_change INTEGER NOT NULL DEFAULT 1,active INTEGER NOT NULL DEFAULT 1,membership TEXT NOT NULL DEFAULT 'pending',membership_reference TEXT NOT NULL DEFAULT '',developer_access INTEGER NOT NULL DEFAULT 0,created TEXT NOT NULL);
            INSERT INTO users(username,name,password_hash,role,created) VALUES('o','O','x','owner','a'),('a','A','x','admin','a'),('r','R','x','reviewer','a'),('m','M','x','member','a');""")
    init_db(database)
    with connect(database) as connection:
        flags={row['username']:row['editor_access'] for row in connection.execute('SELECT username,editor_access FROM users')}
        assert flags=={'o':1,'a':1,'r':0,'m':0}
        connection.execute("INSERT INTO users(username,name,password_hash,role,created) VALUES('nuevo','Nuevo','x','owner','a')")
        assert connection.execute("SELECT editor_access FROM users WHERE username='nuevo'").fetchone()[0]==1


def test_permission_helpers_keep_editor_moderator_and_membership_separate():
    editor={'role':'member','editor_access':1,'moderator_access':0,'developer_access':0,'membership':'pending'}
    assert editor_allowed(editor,'plan') and not editor_allowed(editor,'bases')
    assert not dictation_allowed(editor,'editor')
    editor['membership']='official';assert dictation_allowed(editor,'editor')
    admin={**editor,'role':'admin'};assert editor_allowed(admin,'bases')


def test_owner_assigns_independent_permissions_and_editor_cannot_change_core(participation_app):
    owner=client(participation_app,'owner')
    changed=post(owner,'/api/users/2',{'role':'member','membership':'pending','reference':'','active':True,
        'developer_access':False,'editor_access':True,'moderator_access':True})
    assert changed.status_code==200
    member=client(participation_app,'member')
    assert member.get('/editar/plan').status_code==200
    assert member.get('/editar/bases').status_code==403
    assert member.get('/moderacion/aportaciones').status_code==200
    page=owner.get('/administracion')
    assert b'Editor: puede editar documentos' in page.data and b'Moderador de contenido' in page.data


def test_legacy_permission_request_preserves_new_independent_flags(participation_app):
    with connect(participation_app.config['DATABASE']) as connection:
        connection.execute("UPDATE users SET editor_access=1,moderator_access=1 WHERE username='member'")
    owner=client(participation_app,'owner')
    response=post(owner,'/api/users/2',{'role':'member','membership':'pending','reference':'','active':True,'developer_access':False})
    assert response.status_code==200
    with connect(participation_app.config['DATABASE']) as connection:
        row=connection.execute("SELECT editor_access,moderator_access FROM users WHERE username='member'").fetchone()
        assert tuple(row)==(1,1)


def test_guest_submission_requires_csrf_and_blocks_core_or_identified_session(participation_app):
    anonymous=client(participation_app)
    assert anonymous.post('/api/participation/submissions',json=guest_thread_payload(),headers={'Origin':'http://localhost'}).status_code==403
    protected=guest_thread_payload(target_id='bases',section='nucleo',quote='Texto protegido.')
    assert post(anonymous,'/api/participation/submissions',protected).status_code==403
    member=client(participation_app,'member')
    assert post(member,'/api/participation/submissions',guest_thread_payload()).status_code==409


def test_moderation_publishes_guest_attribution_without_contacts(participation_app):
    anonymous=client(participation_app)
    received=post(anonymous,'/api/participation/submissions',guest_thread_payload())
    assert received.status_code==202 and received.json['id']==1
    assert anonymous.get('/moderacion/aportaciones').status_code==401
    assert client(participation_app,'member').get('/moderacion/aportaciones').status_code==403
    moderator=client(participation_app,'owner');queue=moderator.get('/moderacion/aportaciones')
    assert queue.status_code==200 and b'Visitante del centro' in queue.data and b'privado@example.test' in queue.data
    approved=post(moderator,'/api/participation/submissions/1/moderate',{'action':'approve','reason':'Cumple los criterios.'})
    assert approved.status_code==200 and approved.json['url']=='/discusiones/1'
    public=anonymous.get('/discusiones/1')
    assert public.status_code==200 and b'Visitante del centro' in public.data and b'Persona invitada' in public.data
    assert b'Propongo revisar el plan cada dos semanas.' in public.data
    assert b'privado@example.test' not in public.data and b'Colectivo privado' not in public.data and b'Nombre privado' not in public.data
    with connect(participation_app.config['DATABASE']) as connection:
        submission=connection.execute('SELECT * FROM guest_submissions WHERE id=1').fetchone()
        assert submission['status']=='approved' and submission['contact_email']=='privado@example.test'
        assert connection.execute('SELECT COUNT(*) FROM guest_attributions WHERE submission_id=1').fetchone()[0]==2
        assert connection.execute('SELECT author FROM threads WHERE id=1').fetchone()[0]==1


def test_rejection_requires_reason_and_never_reaches_public_history(participation_app):
    anonymous=client(participation_app)
    payload=guest_thread_payload(title='Contenido rechazado',body='Mensaje que no debe publicarse.',display_name='Nombre descartado',contact_email='rechazo@example.test')
    assert post(anonymous,'/api/participation/submissions',payload).status_code==202
    moderator=client(participation_app,'owner')
    assert post(moderator,'/api/participation/submissions/1/moderate',{'action':'reject','reason':''}).status_code==400
    assert post(moderator,'/api/participation/submissions/1/moderate',{'action':'reject','reason':'No corresponde al asunto.'}).status_code==200
    assert b'Nombre descartado' not in anonymous.get('/discusiones').data
    assert b'Mensaje que no debe publicarse.' not in anonymous.get('/discusiones?estado=history').data
    assert b'rechazo@example.test' not in anonymous.get('/').data
    assert b'No hay aportaciones pendientes' in moderator.get('/moderacion/aportaciones').data
    with connect(participation_app.config['DATABASE']) as connection:
        row=connection.execute('SELECT status,moderation_reason,published_id FROM guest_submissions WHERE id=1').fetchone()
        assert tuple(row)==('rejected','No corresponde al asunto.',None)


def test_guest_comment_is_escaped_and_keeps_original_thread_author(participation_app):
    owner=client(participation_app,'owner')
    thread=post(owner,'/api/threads',{'document':'plan','version':1,'section':'sombra','title':'Hilo existente','body':'Mensaje inicial.','quote':'','prefix':'','suffix':''})
    assert thread.status_code==201
    anonymous=client(participation_app)
    submission={'submission_type':'comment','target_type':'thread','target_id':thread.json['id'],'display_name':'<img src=x onerror=alert(1)>','body':'<script>window.pwned=1</script> comentario','contact_name':'','contact_organization':'','contact_phone':'','contact_email':''}
    assert post(anonymous,'/api/participation/submissions',submission).status_code==202
    assert post(owner,'/api/participation/submissions/1/moderate',{'action':'approve','reason':''}).status_code==200
    page=anonymous.get('/discusiones/1')
    assert b'&lt;img src=x onerror=alert(1)&gt;' in page.data and b'<img src=x onerror=alert(1)>' not in page.data
    assert b'&lt;script&gt;window.pwned=1&lt;/script&gt;' in page.data and b'<script>window.pwned' not in page.data


def test_guest_can_comment_active_drive_thread_but_not_removed_item(participation_app):
    owner=client(participation_app,'owner')
    thread=post(owner,'/api/archive/threads',{'drive_item_id':2,'title':'Guía pública','body':'Revisemos este archivo.'})
    assert thread.status_code==201
    anonymous=client(participation_app)
    payload={'submission_type':'comment','target_type':'thread','target_id':thread.json['id'],'display_name':'Visitante del archivo',
        'body':'La guía necesita una fecha visible.','contact_name':'','contact_organization':'','contact_phone':'','contact_email':''}
    assert post(anonymous,'/api/participation/submissions',payload).status_code==202
    assert post(owner,'/api/participation/submissions/1/moderate',{'action':'approve','reason':''}).status_code==200
    page=anonymous.get('/discusiones/1')
    assert b'Visitante del archivo' in page.data and b'La gu\xc3\xada necesita una fecha visible.' in page.data
    with connect(participation_app.config['DATABASE']) as connection:connection.execute('UPDATE drive_items SET active=0 WHERE id=2')
    assert post(anonymous,'/api/participation/submissions',payload).status_code==404


def test_external_target_adapter_creates_public_safe_attribution(participation_app):
    with connect(participation_app.config['DATABASE']) as connection:
        connection.execute('CREATE TABLE synthetic_comments(id INTEGER PRIMARY KEY,target_id TEXT NOT NULL,author INTEGER NOT NULL,body TEXT NOT NULL,created TEXT NOT NULL)')
    def validate(connection,target_id):
        if target_id!='T01':raise AssertionError('Destino inesperado')
        return {'label':'Tarea T01','snapshot':'Ficha pública','version':1}
    def publish(connection,submission,moderator_id,stamp):
        cursor=connection.execute('INSERT INTO synthetic_comments(target_id,author,body,created) VALUES(?,?,?,?)',(submission['target_id'],moderator_id,submission['body'],stamp))
        return {'target_type':'community_comment','target_id':cursor.lastrowid,'url':'/trabajo/T01#comentario-'+str(cursor.lastrowid)}
    register_guest_target(participation_app,'synthetic_task',validate,publish)
    anonymous=client(participation_app)
    payload={'submission_type':'comment','target_type':'synthetic_task','target_id':'T01','display_name':'Invitada técnica','body':'Puedo colaborar.','contact_name':'','contact_organization':'','contact_phone':'','contact_email':''}
    assert post(anonymous,'/api/participation/submissions',payload).status_code==202
    moderator=client(participation_app,'owner')
    response=post(moderator,'/api/participation/submissions/1/moderate',{'action':'approve','reason':''})
    assert response.status_code==200 and response.json['url']=='/trabajo/T01#comentario-1'
    with connect(participation_app.config['DATABASE']) as connection:
        attribution=connection.execute('SELECT target_type,target_id,display_name FROM guest_attributions').fetchone()
        assert tuple(attribution)==('community_comment',1,'Invitada técnica')


def test_guest_comment_on_improvement_uses_moderated_public_attribution(participation_app):
    if 'improvement' not in participation_app.extensions['pls_guest_targets']:
        register_guest_target(participation_app,'improvement',validate_guest_improvement,publish_guest_improvement)
    member=client(participation_app,'member')
    created=post(member,'/api/improvements',{'title':'Contraste del menú','body':'Revisar el comportamiento móvil.'})
    assert created.status_code==201
    public=client(participation_app);detail=public.get(created.json['url'])
    assert b'Aportar sin cuenta' in detail.data
    payload={'submission_type':'comment','target_type':'improvement','target_id':created.json['id'],'display_name':'Visitante UX',
        'body':'En pantalla pequeña el orden puede mejorar.','contact_name':'Contacto privado','contact_organization':'','contact_phone':'','contact_email':'ux@example.test'}
    assert post(public,'/api/participation/submissions',payload).status_code==202
    moderator=client(participation_app,'owner')
    approved=post(moderator,'/api/participation/submissions/1/moderate',{'action':'approve','reason':''})
    assert approved.status_code==200 and approved.json['url']=='/mejoras/1#evento-2'
    page=public.get('/mejoras/1')
    assert b'Visitante UX' in page.data and b'Persona invitada' in page.data and b'En pantalla peque' in page.data
    assert b'ux@example.test' not in page.data and b'Contacto privado' not in page.data
    with connect(participation_app.config['DATABASE']) as connection:
        event=connection.execute("SELECT source,actor FROM improvement_events WHERE id=2").fetchone()
        assert tuple(event)==('guest',1)
        assert connection.execute('SELECT COUNT(*) FROM improvement_outbox WHERE event=2').fetchone()[0]==1
