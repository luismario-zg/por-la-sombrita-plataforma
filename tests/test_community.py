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
