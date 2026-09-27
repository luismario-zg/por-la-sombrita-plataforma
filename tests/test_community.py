"""Pruebas del módulo independiente de operación comunitaria."""
import hashlib
import json
import struct
import threading
import zlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.community import bp, init_community_schema, validate_guest_target
from app.core import connect, now


PASS="Clave-comunitaria-de-prueba-123"


@pytest.fixture
def app(tmp_path):
    index=tmp_path/"plan.json";index.write_text(json.dumps({"items":[]}))
    application=create_app({"TESTING":True,"DATABASE":str(tmp_path/"community.sqlite3"),"BASE_URL":"http://localhost","COOKIE_NAME":"community-test","COOKIE_SECURE":False,"DEVELOPMENT_INDEX":str(index),"COMMUNITY_MEDIA_DIR":str(tmp_path/"media")})
    with connect(application.config["DATABASE"]) as connection:
        init_community_schema(connection)
        for name,role in [("owner","owner"),("admin","admin"),("ana","member"),("beto","member"),("reader","reader")]:
            connection.execute("INSERT INTO users(username,name,password_hash,role,must_change,created) VALUES(?,?,?,?,0,?)",(name,name.title(),generate_password_hash(PASS),role,now()))
        connection.execute("UPDATE users SET moderator_access=1 WHERE username='owner'")
    if "community" not in application.blueprints:application.register_blueprint(bp)
    return application


def client(app,name=None):
    result=app.test_client()
    if name:
        response=post(result,"/api/login",{"username":name,"password":PASS});assert response.status_code==200
    return result


def post(browser,path,payload):
    session=browser.get("/api/session").get_json()
    return browser.post(path,json=payload,headers={"Origin":"http://localhost","X-CSRF-Token":session["csrf"]})


def race_posts(*requests):
    """Dispara POST reales a la vez, con una sesión y conexión por solicitud."""
    prepared=[]
    for browser,path,payload in requests:
        csrf=browser.get("/api/session").get_json()["csrf"]
        prepared.append((browser,path,payload,csrf))
    barrier=threading.Barrier(len(prepared))
    def send(item):
        browser,path,payload,csrf=item;barrier.wait(timeout=5)
        return browser.post(path,json=payload,headers={"Origin":"http://localhost","X-CSRF-Token":csrf})
    with ThreadPoolExecutor(max_workers=len(prepared)) as pool:
        return list(pool.map(send,prepared))


def due(days=2):
    return (datetime.now(ZoneInfo("America/Monterrey"))+timedelta(days=days)).date().isoformat()


def create_open(browser,**extra):
    payload={"title":"Mapear sombra","description":"Documentar sombra en la banqueta.","priority":"normal"};payload.update(extra)
    return post(browser,"/api/community/tasks",payload)


def png(width=64,height=64,noisy=False):
    def chunk(kind,data):
        return struct.pack(">I",len(data))+kind+data+struct.pack(">I",zlib.crc32(kind+data)&0xffffffff)
    ihdr=struct.pack(">IIBBBBB",width,height,8,2,0,0,0)
    if noisy:
        raw=hashlib.shake_256(b"imagen de prueba").digest(width*height*3)
        pixels=b"".join(b"\x00"+raw[row*width*3:(row+1)*width*3] for row in range(height))
    else:pixels=b"".join(b"\x00"+b"\xef\xb7\x13"*width for _ in range(height))
    return b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",ihdr)+chunk(b"IDAT",zlib.compress(pixels))+chunk(b"IEND",b"")


def test_public_pages_and_authenticated_mutations(app):
    anonymous=client(app)
    for path in ["/trabajo","/actividades","/convocatorias","/rolitas"]:assert anonymous.get(path).status_code==200
    assert create_open(anonymous).status_code==401
    assert create_open(client(app,"reader")).status_code==403
    response=create_open(client(app,"ana"));assert response.status_code==201 and response.get_json()["state"]=="open"


def test_assignment_requires_acceptance_and_date(app):
    ana=client(app,"ana");beto=client(app,"beto")
    response=create_open(ana,assignee_id=4);assert response.status_code==201 and response.get_json()["state"]=="pending_acceptance"
    with connect(app.config["DATABASE"]) as connection:
        task=connection.execute("SELECT * FROM community_tasks").fetchone();assert task["assignee"]==4 and task["due_date"] is None
        assert connection.execute("SELECT COUNT(*) FROM community_notifications WHERE user_id=4").fetchone()[0]==1
    assert post(ana,"/api/community/tasks/1/assignment",{"decision":"accept","due_date":due()}).status_code==403
    assert post(beto,"/api/community/tasks/1/assignment",{"decision":"accept","due_date":""}).status_code==400
    assert post(beto,"/api/community/tasks/1/assignment",{"decision":"accept","due_date":due()}).status_code==200
    with connect(app.config["DATABASE"]) as connection:
        task=connection.execute("SELECT * FROM community_tasks").fetchone();assert task["state"]=="in_progress" and task["due_date"]==due()


def test_self_assignment_take_reject_prioritize_and_close(app):
    ana=client(app,"ana");beto=client(app,"beto")
    assert create_open(ana,assignee_id=3).status_code==400
    response=create_open(ana,assignee_id=3,due_date=due());assert response.get_json()["state"]=="in_progress"
    assert post(beto,"/api/community/tasks/1/priority",{"priority":"urgent"}).status_code==200
    assert post(beto,"/api/community/tasks/1/close",{"note":"Se resolvió en colectivo."}).status_code==200
    create_open(ana,assignee_id=4)
    assert post(beto,"/api/community/tasks/2/assignment",{"decision":"reject","reason":"No tengo disponibilidad."}).status_code==200
    assert post(beto,"/api/community/tasks/2/take",{"due_date":due(3)}).status_code==200
    assert post(ana,"/api/community/tasks/2/take",{"due_date":due(4)}).status_code==409


def test_concurrent_task_mutations_serialize_state_and_history(app):
    owner=client(app,"owner");ana=client(app,"ana");beto=client(app,"beto")
    create_open(owner)
    taking,proposing=race_posts(
        (ana,"/api/community/tasks/1/take",{"due_date":due(2)}),
        (owner,"/api/community/tasks/1/propose",{"assignee_id":4}),
    )
    assert sorted([taking.status_code,proposing.status_code])==[200,409]
    with connect(app.config["DATABASE"]) as connection:
        task=connection.execute("SELECT state,assignee FROM community_tasks WHERE id=1").fetchone()
        assert (task["state"],task["assignee"]) in {("in_progress",3),("pending_acceptance",4)}
        assert connection.execute("SELECT COUNT(*) FROM community_task_events WHERE task_id=1 AND kind IN ('taken','assignment_proposed')").fetchone()[0]==1

    create_open(owner,assignee_id=4)
    beto_second=client(app,"beto")
    accepted=race_posts(
        (beto,"/api/community/tasks/2/assignment",{"decision":"accept","due_date":due(3)}),
        (beto_second,"/api/community/tasks/2/assignment",{"decision":"accept","due_date":due(4)}),
    )
    assert sorted(response.status_code for response in accepted)==[200,403]
    with connect(app.config["DATABASE"]) as connection:
        assert connection.execute("SELECT COUNT(*) FROM community_task_events WHERE task_id=2 AND kind='assignment_accepted'").fetchone()[0]==1

    create_open(owner)
    closed=race_posts(
        (ana,"/api/community/tasks/3/close",{"note":"Cierre de Ana."}),
        (beto,"/api/community/tasks/3/close",{"note":"Cierre de Beto."}),
    )
    assert sorted(response.status_code for response in closed)==[200,409]
    with connect(app.config["DATABASE"]) as connection:
        assert connection.execute("SELECT COUNT(*) FROM community_task_events WHERE task_id=3 AND kind='closed'").fetchone()[0]==1

    create_open(ana,assignee_id=3,due_date=due())
    ana_second=client(app,"ana")
    delivered=race_posts(
        (ana,"/api/community/tasks/4/deliverable",{"body":"Primera entrega concurrente."}),
        (ana_second,"/api/community/tasks/4/deliverable",{"body":"Segunda entrega concurrente."}),
    )
    assert [response.status_code for response in delivered]==[200,200]
    assert sorted(response.get_json()["version"] for response in delivered)==[1,2]
    with connect(app.config["DATABASE"]) as connection:
        task=connection.execute("SELECT state,deliverable_version FROM community_tasks WHERE id=4").fetchone()
        assert dict(task)=={"state":"review","deliverable_version":2}
        assert connection.execute("SELECT COUNT(*) FROM community_task_events WHERE task_id=4 AND kind='deliverable_submitted'").fetchone()[0]==2


def test_concurrent_schema_initialization_serializes_creator_migration(tmp_path):
    database=tmp_path/"legacy.sqlite3"
    with connect(database) as connection:
        connection.execute("CREATE TABLE users(id INTEGER PRIMARY KEY)")
        connection.execute("CREATE TABLE community_calls(id INTEGER PRIMARY KEY,publish_at TEXT,updated_by INTEGER)")
    barrier=threading.Barrier(2)
    def initialize(_):
        connection=connect(database)
        try:barrier.wait(timeout=5);init_community_schema(connection)
        finally:connection.close()
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(initialize,range(2)))
    with connect(database) as connection:
        columns=[row["name"] for row in connection.execute("PRAGMA table_info(community_calls)")]
        assert columns.count("creator")==1


def test_deliverable_keeps_versions_and_community_review(app):
    ana=client(app,"ana");beto=client(app,"beto");create_open(ana,assignee_id=3,due_date=due())
    assert post(ana,"/api/community/tasks/1/deliverable",{"body":"Mapa y notas de campo."}).status_code==200
    assert post(ana,"/api/community/tasks/1/reviews",{"decision":"approve","comment":"Yo apruebo."}).status_code==403
    assert post(beto,"/api/community/tasks/1/reviews",{"decision":"changes","comment":"Falta señalar la hora."}).status_code==200
    assert post(ana,"/api/community/tasks/1/deliverable",{"body":"Mapa, notas y hora de observación."}).get_json()["version"]==2
    assert post(beto,"/api/community/tasks/1/reviews",{"decision":"approve","comment":"Quedó verificable."}).status_code==200
    with connect(app.config["DATABASE"]) as connection:
        assert connection.execute("SELECT COUNT(*) FROM community_task_reviews").fetchone()[0]==2


def test_overdue_notifications_are_idempotent_for_assignee_and_admins(app):
    ana=client(app,"ana");create_open(ana,assignee_id=3,due_date=due())
    with connect(app.config["DATABASE"]) as connection:connection.execute("UPDATE community_tasks SET due_date='2020-01-01'")
    ana.get("/trabajo");ana.get("/trabajo")
    with connect(app.config["DATABASE"]) as connection:
        notices=connection.execute("SELECT user_id,COUNT(*) total FROM community_notifications WHERE kind='overdue' GROUP BY user_id ORDER BY user_id").fetchall()
        assert [(x["user_id"],x["total"]) for x in notices]==[(1,1),(2,1),(3,1)]


def test_only_admins_edit_activities_and_times_use_monterrey(app):
    payload={"activity_type":"evento","title":"Actividad del 15 de septiembre","description":"Ficha por completar.","starts_at":"2026-09-15T12:00","ends_at":"","location":"","status":"completed","pending_details":"Confirmar lugar.","reference":"D14"}
    assert post(client(app,"ana"),"/api/community/activities",payload).status_code==403
    owner=client(app,"owner");response=post(owner,"/api/community/activities",payload);assert response.status_code==201
    with connect(app.config["DATABASE"]) as connection:assert connection.execute("SELECT starts_at FROM community_activities").fetchone()[0]=="2026-09-15T18:00:00+00:00"
    assert "Confirmar lugar." in owner.get("/actividades").text


def test_calls_schedule_visibility_and_safe_internal_image(app):
    owner=client(app,"owner");raw=png(400,300,True);assert len(raw)>262144
    encoded="data:image/png;base64,"+__import__("base64").b64encode(raw).decode()
    upload=post(owner,"/api/community/media",{"data":encoded});assert upload.status_code==201
    image_path=upload.get_json()["path"];assert owner.get(image_path).status_code==200
    assert post(owner,"/api/community/media",{"data":"data:image/png;base64,"+__import__("base64").b64encode(b"<svg>malicioso</svg>"*10).decode()}).status_code==400
    future=(datetime.now(ZoneInfo("America/Monterrey"))+timedelta(days=3)).strftime("%Y-%m-%dT%H:%M")
    start=(datetime.now(ZoneInfo("America/Monterrey"))+timedelta(days=5)).strftime("%Y-%m-%dT%H:%M")
    valid=(datetime.now(ZoneInfo("America/Monterrey"))+timedelta(days=8)).strftime("%Y-%m-%dT%H:%M")
    payload={"title":"Caminata","copy":"Súmate a documentar sombra.","reference":"D15","image_path":image_path,"exclusive_channel":"Instagram","publish_at":future,"starts_at":start,"valid_until":valid,"permanent":False}
    assert post(owner,"/api/community/calls",payload).status_code==201
    assert "Caminata" in owner.get("/convocatorias").text
    assert 'alt="Cartel de la convocatoria: Caminata"' in owner.get("/convocatorias").text
    assert "Caminata" not in client(app).get("/convocatorias").text
    with app.test_request_context(),connect(app.config["DATABASE"]) as connection:
        with pytest.raises(Exception) as error:validate_guest_target(connection,"call",1)
        assert getattr(error.value,"code",None)==404
    payload.update(title="Enlace remoto",image_path="https://example.test/image.png")
    assert post(owner,"/api/community/calls",payload).status_code==400


def test_any_participant_can_create_call_but_editing_requires_editor_access(app):
    ana=client(app,"ana");start=(datetime.now(ZoneInfo("America/Monterrey"))+timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
    payload={"title":"Taller abierto","copy":"Comparte experiencias.","reference":"D05","image_path":"","exclusive_channel":"","publish_at":"","starts_at":start,"valid_until":"","permanent":True}
    created=post(ana,"/api/community/calls",payload);assert created.status_code==201
    assert post(ana,"/api/community/calls/1",payload).status_code==403
    with connect(app.config["DATABASE"]) as connection:connection.execute("UPDATE users SET editor_access=1 WHERE username='ana'")
    payload["copy"]="Comparte experiencias y propuestas."
    assert post(ana,"/api/community/calls/1",payload).status_code==200


def test_public_comments_escape_markup(app):
    ana=client(app,"ana");create_open(ana)
    assert post(ana,"/api/community/task/1/comments",{"body":"<script>alert(1)</script> Aporte"}).status_code==201
    page=client(app).get("/trabajo").text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page and "<script>alert(1)</script>" not in page


def test_guest_target_versions_are_integer_or_none(app):
    owner=client(app,"owner");create_open(owner)
    activity={"activity_type":"dinamica","title":"Recorrido","description":"Observar el trayecto.","starts_at":"","ends_at":"","location":"","status":"planned","pending_details":"","reference":""}
    post(owner,"/api/community/activities",activity)
    with app.test_request_context(),connect(app.config["DATABASE"]) as connection:
        assert isinstance(validate_guest_target(connection,"task",1)["version"],int)
        assert isinstance(validate_guest_target(connection,"activity",1)["version"],int)
        assert validate_guest_target(connection,"rolita",1)["version"] is None


def test_moderated_guest_comment_shows_guest_not_moderator(app):
    owner=client(app,"owner");create_open(owner)
    guest=client(app);submission=post(guest,"/api/participation/submissions",{"submission_type":"comment","target_type":"task","target_id":"1","display_name":"Luz","body":"La sombra cambia por la tarde.","title":"","contact_name":"","contact_organization":"","contact_phone":"","contact_email":""})
    assert submission.status_code==202
    approved=post(owner,f"/api/participation/submissions/{submission.get_json()['id']}/moderate",{"action":"approve","reason":"Aporte pertinente."});assert approved.status_code==200
    page=guest.get("/trabajo").text
    assert "Luz · Persona invitada" in page and "La sombra cambia por la tarde." in page


def test_anonymous_visitors_see_guest_comment_form(app):
    owner=client(app,"owner");create_open(owner)
    page=client(app).get("/trabajo").text
    assert "Comentar sin cuenta" in page
    assert 'data-api="/api/participation/submissions"' in page and 'name="target_type" value="task"' in page
    assert "Comentar sin cuenta" not in client(app,"ana").get("/trabajo").text


def test_home_shows_pulse_and_first_steps(app):
    page=client(app).get("/").text
    assert "EMPIEZA<br>EN TRES PASOS." in page and "Tareas por tomar" in page


def test_local_time_uses_monterrey():
    from app.core import local_time
    assert local_time("2026-09-21T02:34:00+00:00","%Y-%m-%d %H:%M")=="2026-09-20 20:34"
    assert local_time("2026-09-21","%Y-%m-%d")=="2026-09-21" and local_time(None,"%Y")is None


def test_work_page_lists_task_index_when_many(app):
    owner=client(app,"owner")
    for n in range(6):
        post(owner,"/api/community/tasks",{"title":f"Tarea {n}","description":"Descripción.","reference":"","priority":"normal"})
    page=client(app).get("/trabajo").text
    assert 'class="task-index"' in page and 'href="#tarea-6"' in page


def test_report_task_done_in_past_with_account_or_name(app):
    owner=client(app,"owner");create_open(owner)
    ana=client(app,"ana")
    with connect(app.config["DATABASE"]) as connection:
        beto=connection.execute("SELECT id FROM users WHERE username='beto'").fetchone()["id"]
    future=(datetime.now(ZoneInfo("America/Monterrey")).date()+timedelta(days=1)).isoformat()
    assert post(ana,"/api/community/tasks/1/done",{"completed_on":future,"performer_id":beto,"note":"Hecho."}).status_code==400
    assert post(ana,"/api/community/tasks/1/done",{"completed_on":"2026-09-04","performer_id":beto,"performer_name":"Otra","note":"Hecho."}).status_code==400
    assert post(ana,"/api/community/tasks/1/done",{"completed_on":"2026-09-04","performer_id":None,"performer_name":"","note":"Hecho."}).status_code==400
    assert post(client(app),"/api/community/tasks/1/done",{"completed_on":"2026-09-04","performer_id":beto,"note":"Hecho."}).status_code in (401,403)
    done=post(ana,"/api/community/tasks/1/done",{"completed_on":"2026-09-04","performer_id":beto,"performer_name":"","note":"Reunión realizada; minuta en Proton."})
    assert done.status_code==200
    with connect(app.config["DATABASE"]) as connection:
        task=connection.execute("SELECT * FROM community_tasks WHERE id=1").fetchone()
        assert (task["state"],task["completed_on"],task["completed_by"])==("closed","2026-09-04",beto)
        assert connection.execute("SELECT closed_by FROM community_tasks WHERE id=1").fetchone()[0]!=beto
        event=connection.execute("SELECT detail FROM community_task_events WHERE task_id=1 AND kind='reported_done'").fetchone()["detail"]
        assert "Ana reportó que Beto realizó la tarea el 2026-09-04" in event
    assert post(ana,"/api/community/tasks/1/done",{"completed_on":"2026-09-04","performer_id":beto,"note":"Otra vez."}).status_code==409
    page=client(app).get("/trabajo").text
    assert "Realizada por Beto el 2026-09-04." in page and "Reportó Ana." in page


def test_create_task_already_done_by_person_without_account(app):
    ana=client(app,"ana")
    created=post(ana,"/api/community/tasks",{"title":"Crear Linktree","description":"Centralizar recursos.","reference":"minuta 25-ago","priority":"normal","already_done":True,"completed_on":"2026-08-27","performer_id":None,"performer_name":"Natanael","note":"Enlace en el Linktree."})
    assert created.status_code==201 and created.get_json()["state"]=="closed"
    page=client(app).get("/trabajo").text
    assert "Realizada por Natanael el 2026-08-27." in page
    normal=post(ana,"/api/community/tasks",{"title":"Abierta","description":"Sin realizar.","reference":"","priority":"normal","already_done":False,"completed_on":"","performer_id":None,"performer_name":"","note":""})
    assert normal.status_code==201 and normal.get_json()["state"]=="open"


def test_work_pagination_and_grouped_history(app):
    with connect(app.config['DATABASE']) as connection:
        for i in range(1,33):
            stamp=f'2026-09-27T00:00:{i:02d}+00:00'
            connection.execute('INSERT INTO community_tasks(title,description,creator,created,updated) VALUES(?,?,1,?,?)',(f'Tarea {i:02d}','Descripción',stamp,stamp))
        for i in (1,2,31):
            connection.execute('UPDATE community_tasks SET deliverable=? WHERE id=?',('Resultado',i))
            connection.execute('INSERT INTO community_task_events(task_id,actor,kind,detail,created) VALUES(?,1,?,?,?)',(i,'created',f'Evento {i:02d}',now()))
            connection.execute('INSERT INTO community_task_reviews(task_id,deliverable_version,reviewer,decision,comment,created) VALUES(?,1,1,?,?,?)',(i,'approve',f'Revisión {i:02d}',now()))
            connection.execute("INSERT INTO community_comments(target_type,target_id,author,body,created) VALUES('task',?,1,?,?)",(i,f'Comentario {i:02d}',now()))
    browser=client(app)
    first=browser.get('/trabajo')
    second=browser.get('/trabajo?pagina=2')
    assert first.status_code==second.status_code==200
    assert 'Tarea 32' in first.text and 'Tarea 01' not in first.text
    assert 'Tarea 01' in second.text and 'Tarea 02' in second.text and 'Tarea 32' not in second.text
    for i in (1,2):
        assert f'Evento {i:02d}' in second.text and f'Revisión {i:02d}' in second.text and f'Comentario {i:02d}' in second.text
    assert 'Siguientes' in first.text and 'Anteriores' in second.text
    assert browser.get('/trabajo?tarea=1').headers['Location']=='/trabajo?pagina=2#tarea-1'
    for invalid in ('abc','-1'):
        assert browser.get('/trabajo?pagina='+invalid).status_code==200


def test_community_styles_load_in_head(app):
    browser=client(app)
    for path in ('/trabajo','/actividades','/rolitas','/convocatorias'):
        response=browser.get(path)
        assert response.status_code==200
        head,body=response.text.split('</head>',1)
        assert 'community.css' in head and 'community.css' not in body
        assert "style-src 'self'" in response.headers['Content-Security-Policy']
