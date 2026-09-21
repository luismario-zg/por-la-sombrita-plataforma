"""Operación comunitaria: tareas, actividades, convocatorias y avisos internos."""
import base64
import binascii
import hashlib
import re
import sqlite3
import zlib
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Blueprint, abort, current_app, jsonify, render_template, request, send_from_directory

from .core import db, field, limited, now, require, user


bp = Blueprint("community", __name__)
MONTERREY = ZoneInfo("America/Monterrey")
PARTICIPANT_ROLES = ("owner", "admin", "reviewer", "member")
ADMIN_ROLES = ("owner", "admin")
PRIORITIES = {"low": "Baja", "normal": "Normal", "high": "Alta", "urgent": "Urgente"}
TASK_STATES = {
    "open": "Abierta",
    "pending_acceptance": "Responsabilidad propuesta",
    "in_progress": "En curso",
    "review": "Entregable en revisión",
    "closed": "Cerrada",
}


def init_community_schema(connection):
    """Instala de forma idempotente las tablas propias del módulo."""
    connection.executescript((Path(__file__).parent / "community-schema.sql").read_text())
    connection.execute("BEGIN IMMEDIATE")
    try:
        columns={row["name"] for row in connection.execute("PRAGMA table_info(community_calls)")}
        if "creator" not in columns:
            connection.execute("ALTER TABLE community_calls ADD COLUMN creator INTEGER REFERENCES users(id)")
            connection.execute("UPDATE community_calls SET creator=updated_by WHERE creator IS NULL")
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def _json_body():
    payload = request.get_json()
    if not isinstance(payload, dict):
        abort(400, description="Solicitud inválida.")
    return payload


def _optional_text(payload, key, limit):
    return field(payload, key, limit, required=False)


def _boolean(payload, key, default=False):
    value = payload.get(key, default)
    if not isinstance(value, bool):
        abort(400, description=f"El campo {key} debe ser verdadero o falso.")
    return value


def _identifier(payload, key, required=False):
    value = payload.get(key)
    if value in (None, "") and not required:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        abort(400, description=f"Revisa {key}.")
    return value


def _local_datetime(value, key, required=False):
    if value in (None, "") and not required:
        return None
    if not isinstance(value, str):
        abort(400, description=f"Revisa el campo {key}.")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        abort(400, description=f"Revisa la fecha de {key}.")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=MONTERREY)
    else:
        parsed = parsed.astimezone(MONTERREY)
    if parsed.year < 2020 or parsed.year > 2100:
        abort(400, description=f"Revisa la fecha de {key}.")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")


def _local_date(value, key="due_date"):
    if not isinstance(value, str):
        abort(400, description=f"Revisa el campo {key}.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        abort(400, description=f"Revisa la fecha de {key}.")
    if parsed < datetime.now(MONTERREY).date():
        abort(400, description="El plazo debe ser hoy o una fecha posterior.")
    return parsed.isoformat()


def _format_local(value, date_only=False):
    if not value:
        return ""
    parsed = datetime.fromisoformat(value).astimezone(MONTERREY)
    return parsed.strftime("%d/%m/%Y" if date_only else "%d/%m/%Y · %H:%M")


def _input_local(value):
    if not value:
        return ""
    return datetime.fromisoformat(value).astimezone(MONTERREY).strftime("%Y-%m-%dT%H:%M")


def _task_from(connection,ident):
    row = connection.execute(
        """SELECT t.*,creator.name AS creator_name,assignee.name AS assignee_name
        FROM community_tasks t JOIN users creator ON creator.id=t.creator
        LEFT JOIN users assignee ON assignee.id=t.assignee WHERE t.id=?""",
        (ident,),
    ).fetchone()
    if not row:
        abort(404)
    return row


def _task(ident):
    return _task_from(db(),ident)


def _activity(ident):
    row = db().execute("SELECT * FROM community_activities WHERE id=?", (ident,)).fetchone()
    if not row:
        abort(404)
    return row


def _call(ident):
    row = db().execute("SELECT * FROM community_calls WHERE id=?", (ident,)).fetchone()
    if not row:
        abort(404)
    account=user()
    if row['publish_at']>now() and not (account and (account['role'] in ADMIN_ROLES or account['editor_access'] or row['creator']==account['id'])):
        abort(404)
    return row


def _event(connection, task_id, actor, kind, detail):
    return connection.execute(
        "INSERT INTO community_task_events(task_id,actor,kind,detail,created) VALUES(?,?,?,?,?)",
        (task_id, actor, kind, detail, now()),
    )


def _notify(connection, uid, task_id, kind, title, body, dedupe_key):
    connection.execute(
        """INSERT OR IGNORE INTO community_notifications
        (user_id,task_id,kind,title,body,href,dedupe_key,created)
        VALUES(?,?,?,?,?,?,?,?)""",
        (uid, task_id, kind, title, body, f"/trabajo#tarea-{task_id}", dedupe_key, now()),
    )


def sync_task_notifications(connection):
    """Materializa avisos vencidos una sola vez por persona y fecha prometida."""
    today = datetime.now(MONTERREY).date().isoformat()
    rows = connection.execute(
        """SELECT id,title,assignee,due_date FROM community_tasks
        WHERE assignee IS NOT NULL AND due_date<? AND state IN ('in_progress','review')""",
        (today,),
    ).fetchall()
    admins = [r["id"] for r in connection.execute(
        "SELECT id FROM users WHERE active=1 AND role IN ('owner','admin')"
    )]
    for task in rows:
        recipients = set(admins + [task["assignee"]])
        for uid in recipients:
            _notify(
                connection, uid, task["id"], "overdue", f"Plazo vencido: {task['title']}",
                f"La fecha comprometida fue {task['due_date']}. Revisen el avance y acuerden el siguiente paso.",
                f"overdue:{task['id']}:{task['due_date']}:{uid}",
            )
    connection.commit()


def _comments(target_type, target_id):
    connection=db()
    has_attributions=connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='guest_attributions'").fetchone()
    if has_attributions:
        return connection.execute(
            """SELECT c.*,CASE WHEN ga.display_name<>'' THEN ga.display_name ELSE 'Persona invitada' END AS guest_name,
            ga.submission_id IS NOT NULL AS is_guest,u.name AS author_name FROM community_comments c
            JOIN users u ON u.id=c.author LEFT JOIN guest_attributions ga
              ON ga.target_type='community_comment' AND ga.target_id=CAST(c.id AS TEXT)
            WHERE c.target_type=? AND c.target_id=? ORDER BY c.id""",(target_type,target_id)
        ).fetchall()
    return connection.execute(
        """SELECT c.*,NULL AS guest_name,0 AS is_guest,u.name AS author_name FROM community_comments c
        JOIN users u ON u.id=c.author WHERE c.target_type=? AND c.target_id=? ORDER BY c.id""",
        (target_type, target_id),
    ).fetchall()


@bp.get("/trabajo")
def work():
    current = user()
    if current:
        sync_task_notifications(db())
    tasks = db().execute(
        """SELECT t.*,creator.name AS creator_name,assignee.name AS assignee_name
        FROM community_tasks t JOIN users creator ON creator.id=t.creator
        LEFT JOIN users assignee ON assignee.id=t.assignee
        ORDER BY t.state='closed',CASE t.priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END,t.updated DESC"""
    ).fetchall()
    task_data = []
    for task in tasks:
        item = dict(task)
        item["events"] = db().execute(
            """SELECT e.*,u.name AS actor_name FROM community_task_events e
            LEFT JOIN users u ON u.id=e.actor WHERE task_id=? ORDER BY e.id""", (task["id"],)
        ).fetchall()
        item["reviews"] = db().execute(
            """SELECT r.*,u.name AS reviewer_name FROM community_task_reviews r
            JOIN users u ON u.id=r.reviewer WHERE task_id=? ORDER BY r.id""", (task["id"],)
        ).fetchall()
        item["comments"] = _comments("task", task["id"])
        task_data.append(item)
    people = db().execute(
        "SELECT id,name FROM users WHERE active=1 AND role IN ('owner','admin','reviewer','member') ORDER BY name"
    ).fetchall() if current else []
    notifications = db().execute(
        "SELECT * FROM community_notifications WHERE user_id=? ORDER BY read_at IS NULL DESC,id DESC LIMIT 30",
        (current["id"],),
    ).fetchall() if current else []
    return render_template(
        "community/work.html", title="Trabajo comunitario", tasks=task_data, people=people,
        priorities=PRIORITIES, task_states=TASK_STATES, notifications=notifications,
    )


@bp.get("/actividades")
def activities():
    rows = db().execute("SELECT * FROM community_activities ORDER BY starts_at IS NULL,starts_at DESC,id DESC").fetchall()
    items=[]
    for row in rows:
        item=dict(row);item["starts_label"]=_format_local(row["starts_at"]);item["ends_label"]=_format_local(row["ends_at"])
        item["starts_input"]=_input_local(row["starts_at"]);item["ends_input"]=_input_local(row["ends_at"])
        item["comments"]=_comments("activity",row["id"]);items.append(item)
    return render_template("community/activities.html", title="Actividades", activities=items)


@bp.get("/convocatorias")
def calls():
    current=user();can_review=bool(current and (current["role"] in ADMIN_ROLES or current['editor_access']));current_iso=now()
    query="SELECT * FROM community_calls"+("" if can_review else " WHERE publish_at<=? OR creator=?")+" ORDER BY publish_at DESC,id DESC"
    rows=db().execute(query,() if can_review else (current_iso,current['id'] if current else None)).fetchall()
    stamp = datetime.now(timezone.utc)
    items=[]
    for row in rows:
        item=dict(row);publish=datetime.fromisoformat(row["publish_at"])
        until=datetime.fromisoformat(row["valid_until"]) if row["valid_until"] else None
        item["publication_state"]="scheduled" if publish>stamp else ("expired" if until and until<stamp else "published")
        item["publish_label"]=_format_local(row["publish_at"]);item["starts_label"]=_format_local(row["starts_at"]);item["valid_label"]=_format_local(row["valid_until"])
        item["publish_input"]=_input_local(row["publish_at"]);item["starts_input"]=_input_local(row["starts_at"]);item["valid_input"]=_input_local(row["valid_until"])
        item["comments"]=_comments("call",row["id"]);items.append(item)
    return render_template("community/calls.html", title="Convocatorias", calls=items)


@bp.get("/rolitas")
def songs():
    task = db().execute("SELECT id,state FROM community_tasks WHERE reference='rolitas' ORDER BY id DESC LIMIT 1").fetchone()
    return render_template("community/songs.html", title="Rolitas", playlist_task=task,comments=_comments("rolita",1))


@bp.get("/comunidad/medios/<path:filename>")
def media(filename):
    if not re.fullmatch(r"[a-f0-9]{24}\.(?:png|jpg)", filename):
        abort(404)
    directory = _media_directory()
    return send_from_directory(directory, filename, conditional=True, max_age=86400)


@bp.post("/api/community/tasks")
def create_task():
    actor = require(*PARTICIPANT_ROLES); payload = _json_body(); limited(f"community-task:{actor['id']}", 40, 3600)
    title=field(payload,"title",160);description=field(payload,"description",6000);reference=_optional_text(payload,"reference",500)
    priority=payload.get("priority","normal")
    if priority not in PRIORITIES:abort(400,description="Revisa la prioridad.")
    assignee=_identifier(payload,"assignee_id")
    due=None
    if assignee==actor["id"]:due=_local_date(payload.get("due_date"))
    state="in_progress" if assignee==actor["id"] else ("pending_acceptance" if assignee else "open")
    stamp=now();connection=db();connection.execute("BEGIN IMMEDIATE")
    if assignee and not connection.execute("SELECT 1 FROM users WHERE id=? AND active=1 AND role IN ('owner','admin','reviewer','member')",(assignee,)).fetchone():abort(400,description="La persona responsable no está disponible.")
    cursor=connection.execute("""INSERT INTO community_tasks(title,description,reference,priority,state,creator,assignee,due_date,created,updated)
        VALUES(?,?,?,?,?,?,?,?,?,?)""",(title,description,reference,priority,state,actor["id"],assignee,due,stamp,stamp));ident=cursor.lastrowid
    detail="Se creó como tarea abierta."
    if state=="in_progress":detail=f"La persona creadora asumió la responsabilidad con plazo {due}."
    elif state=="pending_acceptance":detail="Se propuso una persona responsable; falta su respuesta y fecha comprometida."
    event_id=_event(connection,ident,actor["id"],"created",detail).lastrowid
    if state=="pending_acceptance":_notify(connection,assignee,ident,"assignment",f"Te proponen una tarea: {title}","Acepta o rechaza la responsabilidad y, al aceptar, indica tu plazo.",f"assignment:{ident}:{event_id}:{assignee}")
    connection.commit();return jsonify(id=ident,state=state),201


@bp.post("/api/community/tasks/<int:ident>/priority")
def prioritize_task(ident):
    actor=require(*PARTICIPANT_ROLES);payload=_json_body();priority=payload.get("priority")
    if priority not in PRIORITIES:abort(400,description="Revisa la prioridad.")
    connection=db();connection.execute("BEGIN IMMEDIATE");task=_task_from(connection,ident)
    if task["state"]=="closed":abort(409,description="La tarea ya está cerrada.")
    connection.execute("UPDATE community_tasks SET priority=?,updated=? WHERE id=?",(priority,now(),ident));_event(connection,ident,actor["id"],"prioritized",f"Prioridad: {PRIORITIES[priority]}.");connection.commit();return jsonify(ok=True)


@bp.post("/api/community/tasks/<int:ident>/propose")
def propose_task(ident):
    actor=require(*PARTICIPANT_ROLES);payload=_json_body();assignee=_identifier(payload,"assignee_id",True)
    if assignee==actor["id"]:abort(400,description="Para asumirla tú, usa la opción Tomar tarea e indica un plazo.")
    connection=db();connection.execute("BEGIN IMMEDIATE");task=_task_from(connection,ident)
    if task["state"]!="open":abort(409,description="Solo una tarea abierta puede proponerse a otra persona.")
    person=connection.execute("SELECT name FROM users WHERE id=? AND active=1 AND role IN ('owner','admin','reviewer','member')",(assignee,)).fetchone()
    if not person:abort(400,description="La persona responsable no está disponible.")
    connection.execute("UPDATE community_tasks SET state='pending_acceptance',assignee=?,due_date=NULL,updated=? WHERE id=?",(assignee,now(),ident))
    event_id=_event(connection,ident,actor["id"],"assignment_proposed",f"Se propuso la responsabilidad a {person['name']}.").lastrowid
    _notify(connection,assignee,ident,"assignment",f"Te proponen una tarea: {task['title']}","Acepta o rechaza la responsabilidad y, al aceptar, indica tu plazo.",f"assignment:{ident}:{event_id}:{assignee}");connection.commit();return jsonify(ok=True)


@bp.post("/api/community/tasks/<int:ident>/assignment")
def answer_assignment(ident):
    actor=require(*PARTICIPANT_ROLES);payload=_json_body();decision=payload.get("decision")
    if decision=="accept":
        due=_local_date(payload.get("due_date"));reason=None
    elif decision=="reject":
        due=None;reason=_optional_text(payload,"reason",1000)
    else:abort(400,description="Indica si aceptas o rechazas la responsabilidad.")
    connection=db();connection.execute("BEGIN IMMEDIATE");task=_task_from(connection,ident)
    if task["state"]!="pending_acceptance" or task["assignee"]!=actor["id"]:abort(403,description="Esta propuesta de responsabilidad no está dirigida a tu cuenta.")
    if decision=="accept":
        connection.execute("UPDATE community_tasks SET state='in_progress',due_date=?,updated=? WHERE id=?",(due,now(),ident));_event(connection,ident,actor["id"],"assignment_accepted",f"Responsabilidad aceptada con plazo {due}.")
    else:
        connection.execute("UPDATE community_tasks SET state='open',assignee=NULL,due_date=NULL,updated=? WHERE id=?",(now(),ident));_event(connection,ident,actor["id"],"assignment_rejected",("Responsabilidad rechazada. "+reason).strip())
    connection.commit();return jsonify(ok=True)


@bp.post("/api/community/tasks/<int:ident>/take")
def take_task(ident):
    actor=require(*PARTICIPANT_ROLES);payload=_json_body();due=_local_date(payload.get("due_date"))
    connection=db();connection.execute("BEGIN IMMEDIATE");task=_task_from(connection,ident)
    if task["state"]!="open":abort(409,description="Esta tarea ya no está abierta.")
    connection.execute("UPDATE community_tasks SET state='in_progress',assignee=?,due_date=?,updated=? WHERE id=?",(actor["id"],due,now(),ident))
    _event(connection,ident,actor["id"],"taken",f"Responsabilidad asumida con plazo {due}.");connection.commit();return jsonify(ok=True)


@bp.post("/api/community/tasks/<int:ident>/deliverable")
def submit_deliverable(ident):
    actor=require(*PARTICIPANT_ROLES);payload=_json_body();body=field(payload,"body",12000)
    connection=db();connection.execute("BEGIN IMMEDIATE");task=_task_from(connection,ident)
    if task["assignee"]!=actor["id"] or task["state"] not in ("in_progress","review"):abort(403,description="Solo la persona responsable puede entregar este resultado.")
    version=task["deliverable_version"]+1;stamp=now();connection.execute("""UPDATE community_tasks SET state='review',deliverable=?,deliverable_version=?,deliverable_submitted=?,updated=? WHERE id=?""",(body,version,stamp,stamp,ident));_event(connection,ident,actor["id"],"deliverable_submitted",f"Se presentó la versión {version} del entregable para revisión comunitaria.");connection.commit();return jsonify(ok=True,version=version)


@bp.post("/api/community/tasks/<int:ident>/reviews")
def review_deliverable(ident):
    actor=require(*PARTICIPANT_ROLES);payload=_json_body();decision=payload.get("decision")
    if decision not in ("approve","changes"):abort(400,description="Revisa la decisión.")
    comment=field(payload,"comment",3000);connection=db();connection.execute("BEGIN IMMEDIATE");task=_task_from(connection,ident)
    if task["state"]!="review":abort(409,description="Esta tarea no tiene un entregable en revisión.")
    if task["assignee"]==actor["id"]:abort(403,description="La persona responsable no revisa su propio entregable.")
    try:connection.execute("INSERT INTO community_task_reviews(task_id,deliverable_version,reviewer,decision,comment,created) VALUES(?,?,?,?,?,?)",(ident,task["deliverable_version"],actor["id"],decision,comment,now()))
    except sqlite3.IntegrityError as exc:
        if "UNIQUE constraint failed" in str(exc):abort(409,description="Ya registraste una revisión para esta versión.")
        raise
    if decision=="changes":connection.execute("UPDATE community_tasks SET state='in_progress',updated=? WHERE id=?",(now(),ident))
    _event(connection,ident,actor["id"],"reviewed","Se aprobó el entregable." if decision=="approve" else "Se solicitaron cambios al entregable.");connection.commit();return jsonify(ok=True)


@bp.post("/api/community/tasks/<int:ident>/close")
def close_task(ident):
    actor=require(*PARTICIPANT_ROLES);payload=_json_body();note=field(payload,"note",3000)
    connection=db();connection.execute("BEGIN IMMEDIATE");task=_task_from(connection,ident)
    if task["state"]=="closed":abort(409,description="La tarea ya está cerrada.")
    stamp=now();connection.execute("UPDATE community_tasks SET state='closed',closed=?,closed_by=?,close_note=?,updated=? WHERE id=?",(stamp,actor["id"],note,stamp,ident));_event(connection,ident,actor["id"],"closed",note);connection.commit();return jsonify(ok=True)


@bp.post("/api/community/notifications/<int:ident>/read")
def read_notification(ident):
    actor=require(*PARTICIPANT_ROLES);connection=db();cursor=connection.execute("UPDATE community_notifications SET read_at=COALESCE(read_at,?) WHERE id=? AND user_id=?",(now(),ident,actor["id"]));connection.commit()
    if not cursor.rowcount:abort(404)
    return jsonify(ok=True)


def _activity_values(payload):
    activity_type=payload.get("activity_type");status=payload.get("status","planned")
    if activity_type not in ("dinamica","evento"):abort(400,description="Revisa el tipo de actividad.")
    if status not in ("planned","completed","cancelled"):abort(400,description="Revisa el estado de la actividad.")
    starts=_local_datetime(payload.get("starts_at"),"starts_at");ends=_local_datetime(payload.get("ends_at"),"ends_at")
    if starts and ends and ends<starts:abort(400,description="La fecha de cierre no puede ser anterior al inicio.")
    return (activity_type,field(payload,"title",160),field(payload,"description",8000),_optional_text(payload,"reference",500),starts,ends,_optional_text(payload,"location",240),status,_optional_text(payload,"pending_details",3000))


@bp.post("/api/community/activities")
def create_activity():
    actor=require(*ADMIN_ROLES);values=_activity_values(_json_body());stamp=now();connection=db();cursor=connection.execute("""INSERT INTO community_activities(activity_type,title,description,reference,starts_at,ends_at,location,status,pending_details,created,updated,updated_by) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",(*values,stamp,stamp,actor["id"]));connection.commit();return jsonify(id=cursor.lastrowid),201


@bp.post("/api/community/activities/<int:ident>")
def edit_activity(ident):
    actor=require(*ADMIN_ROLES);_activity(ident);values=_activity_values(_json_body());connection=db();connection.execute("""UPDATE community_activities SET activity_type=?,title=?,description=?,reference=?,starts_at=?,ends_at=?,location=?,status=?,pending_details=?,updated=?,updated_by=? WHERE id=?""",(*values,now(),actor["id"],ident));connection.commit();return jsonify(ok=True)


def _call_values(payload, existing=None):
    permanent=_boolean(payload,"permanent");publish=_local_datetime(payload.get("publish_at"),"publish_at") or (existing["publish_at"] if existing else now())
    starts=_local_datetime(payload.get("starts_at"),"starts_at",required=True);valid=None if permanent else _local_datetime(payload.get("valid_until"),"valid_until",required=True)
    if starts and valid and valid<starts:abort(400,description="La vigencia no puede terminar antes de iniciar.")
    channel=_optional_text(payload,"exclusive_channel",60).lower()
    if channel and not re.fullmatch(r"[a-záéíóúüñ0-9 ._-]{2,60}",channel):abort(400,description="Revisa el canal exclusivo.")
    image_path=_optional_text(payload,"image_path",100)
    if image_path and (not re.fullmatch(r"/comunidad/medios/[a-f0-9]{24}\.(?:png|jpg)",image_path) or not (_media_directory()/Path(image_path).name).is_file()):abort(400,description="La imagen debe ser una subida interna válida.")
    return (field(payload,"title",160),field(payload,"copy",8000),_optional_text(payload,"reference",500),image_path,channel,publish,starts,valid,int(permanent))


@bp.post("/api/community/calls")
def create_call():
    actor=require(*PARTICIPANT_ROLES);values=_call_values(_json_body());stamp=now();connection=db();cursor=connection.execute("""INSERT INTO community_calls(title,copy,reference,image_path,exclusive_channel,publish_at,starts_at,valid_until,permanent,creator,created,updated,updated_by) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",(*values,actor["id"],stamp,stamp,actor["id"]));connection.commit();return jsonify(id=cursor.lastrowid),201


@bp.post("/api/community/calls/<int:ident>")
def edit_call(ident):
    actor=require()
    if not actor["editor_access"]:abort(403,description="Editar convocatorias requiere el permiso de Editor de contenido.")
    existing=_call(ident);values=_call_values(_json_body(),existing);connection=db();connection.execute("""UPDATE community_calls SET title=?,copy=?,reference=?,image_path=?,exclusive_channel=?,publish_at=?,starts_at=?,valid_until=?,permanent=?,updated=?,updated_by=? WHERE id=?""",(*values,now(),actor["id"],ident));connection.commit();return jsonify(ok=True)


def _media_directory():
    configured=current_app.config.get("COMMUNITY_MEDIA_DIR")
    path=Path(configured) if configured else Path(current_app.config["DATABASE"]).resolve().parent/"community-media"
    path.mkdir(mode=0o700,parents=True,exist_ok=True)
    return path


def _image_kind(data):
    if len(data)>=45 and data[:8]==b"\x89PNG\r\n\x1a\n":
        position=8;width=height=None;saw_idat=saw_iend=False
        while position+12<=len(data):
            length=int.from_bytes(data[position:position+4],"big");kind=data[position+4:position+8];end=position+12+length
            if length>2*1024*1024 or end>len(data):return None
            chunk=data[position+8:position+8+length];expected=int.from_bytes(data[position+8+length:end],"big")
            if zlib.crc32(kind+chunk)&0xffffffff!=expected:return None
            if position==8:
                if kind!=b"IHDR" or length!=13 or chunk[8] not in (1,2,4,8,16) or chunk[9] not in (0,2,3,4,6) or chunk[10:]!=b"\x00\x00\x00":return None
                width=int.from_bytes(chunk[:4],"big");height=int.from_bytes(chunk[4:8],"big")
            if kind==b"IEND":
                if length or end!=len(data):return None
                saw_iend=True;break
            if kind==b"IDAT":saw_idat=True
            position=end
        if saw_idat and saw_iend and width and height and width*height<=16_000_000:return "png",width,height
    if len(data)>=4 and data[:2]==b"\xff\xd8" and data[-2:]==b"\xff\xd9":
        offset=2
        while offset+9<len(data):
            if data[offset]!=0xFF:offset+=1;continue
            marker=data[offset+1];offset+=2
            if marker in (0xD8,0xD9) or 0xD0<=marker<=0xD7:continue
            if offset+2>len(data):break
            length=int.from_bytes(data[offset:offset+2],"big")
            if length<2 or offset+length>len(data):break
            if marker in {0xC0,0xC1,0xC2,0xC3,0xC5,0xC6,0xC7,0xC9,0xCA,0xCB,0xCD,0xCE,0xCF} and length>=7:
                return "jpg",int.from_bytes(data[offset+3:offset+5],"big"),int.from_bytes(data[offset+5:offset+7],"big")
            offset+=length
    return None


@bp.post("/api/community/media")
def upload_media():
    actor=require(*PARTICIPANT_ROLES);request.max_content_length=3*1024*1024;payload=_json_body();limited(f"community-media:{actor['id']}",20,3600)
    encoded=payload.get("data")
    if not isinstance(encoded,str) or len(encoded)>2_900_000:abort(400,description="La imagen es inválida o supera 2 MB.")
    encoded=re.sub(r"^data:image/(?:png|jpeg);base64,","",encoded,flags=re.I)
    try:data=base64.b64decode(encoded,validate=True)
    except (binascii.Error,ValueError):abort(400,description="La imagen no está codificada correctamente.")
    if not 100<=len(data)<=2*1024*1024:abort(400,description="La imagen debe pesar entre 100 bytes y 2 MB.")
    kind=_image_kind(data)
    if not kind:abort(400,description="Solo se aceptan imágenes PNG o JPEG válidas.")
    extension,width,height=kind
    if not 64<=width<=8000 or not 64<=height<=8000:abort(400,description="La imagen debe medir entre 64 y 8000 px por lado.")
    filename=f"{hashlib.sha256(data).hexdigest()[:24]}.{extension}";path=_media_directory()/filename
    if not path.exists():
        with path.open("xb") as handle:handle.write(data)
        path.chmod(0o600)
    return jsonify(path=f"/comunidad/medios/{filename}",width=width,height=height),201


@bp.post("/api/community/<target_type>/<int:target_id>/comments")
def add_comment(target_type,target_id):
    actor=require(*PARTICIPANT_ROLES);payload=_json_body();limited(f"community-comment:{actor['id']}",80,3600)
    if target_type=="task":_task(target_id)
    elif target_type=="activity":_activity(target_id)
    elif target_type=="call":_call(target_id)
    elif target_type=="rolita" and target_id==1:pass
    else:abort(404)
    body=field(payload,"body",5000);connection=db();cursor=connection.execute("INSERT INTO community_comments(target_type,target_id,author,body,created) VALUES(?,?,?,?,?)",(target_type,target_id,actor["id"],body,now()));connection.commit();return jsonify(id=cursor.lastrowid),201


def validate_guest_target(connection,target_type,target_id):
    """Adaptador de lectura para registrar este módulo en participation.register_guest_target."""
    try:ident=int(target_id)
    except (TypeError,ValueError):abort(404,description="Destino comunitario inválido.")
    specs={
        "task":("community_tasks","title","description","deliverable_version"),
        "activity":("community_activities","title","description","updated"),
        "call":("community_calls","title","copy","updated"),
    }
    if target_type=="rolita" and ident==1:return {"label":"Rolitas","snapshot":"Playlist colectiva en desarrollo.","version":None}
    if target_type not in specs:abort(404,description="Destino comunitario inválido.")
    table,label,snapshot,version=specs[target_type]
    suffix=" AND publish_at<=?" if target_type=="call" else ""
    params=(ident,now()) if target_type=="call" else (ident,)
    row=connection.execute(f"SELECT {label} AS label,{snapshot} AS snapshot,{version} AS version FROM {table} WHERE id=?{suffix}",params).fetchone()
    if not row:abort(404,description="Destino comunitario inexistente o todavía no publicado.")
    result=dict(row)
    if target_type in ("activity","call"):
        result["version"]=int.from_bytes(hashlib.sha256(result["version"].encode()).digest()[:7],"big")
    return result


def publish_guest_comment(connection,submission,moderator_id,stamp):
    """Publica una aportación ya moderada; la atribución invitada la conserva participation."""
    target_type=submission["target_type"];target_id=int(submission["target_id"])
    target=validate_guest_target(connection,target_type,target_id)
    if target["version"]!=submission["target_version"]:abort(409,description="El destino cambió desde que se recibió la aportación. Revísala de nuevo.")
    keys=submission.keys() if hasattr(submission,"keys") else ()
    body=submission["body"] if "body" in keys else submission["content"]
    cursor=connection.execute("INSERT INTO community_comments(target_type,target_id,author,body,created) VALUES(?,?,?,?,?)",(target_type,target_id,moderator_id,body,stamp))
    prefixes={"task":"/trabajo#tarea-","activity":"/actividades#actividad-","call":"/convocatorias#convocatoria-","rolita":"/rolitas#comentarios-"}
    return {"target_type":"community_comment","target_id":cursor.lastrowid,"url":prefixes[target_type]+str(target_id)}
