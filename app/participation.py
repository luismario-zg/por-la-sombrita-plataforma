"""Participación invitada moderada y permisos editoriales independientes."""
import hashlib
import re

from flask import Blueprint, abort, current_app, jsonify, render_template, request

from .core import db, drive_snapshot, field, limited, now, sections, short_sentence, user

bp=Blueprint('participation',__name__)
PROTECTED_DOCUMENTS={'bases','directrices','mision','vision','valores','objetivos'}
BUILTIN_TARGETS={'document','drive','thread'}


def _flag(account,name):
    if not account:return False
    try:return bool(account[name])
    except (IndexError,KeyError):return False


def editor_allowed(account,slug=None):
    """El permiso editor es independiente; el núcleo además exige admin/owner."""
    if not _flag(account,'editor_access'):return False
    return slug not in PROTECTED_DOCUMENTS or account['role'] in {'owner','admin'}


def moderator_allowed(account):return _flag(account,'moderator_access')


def dictation_allowed(account,capability='developer'):
    """El dictado nunca sustituye la membresía oficial decidida por la comunidad."""
    if not account or account['membership']!='official':return False
    permission={'developer':'developer_access','editor':'editor_access','moderator':'moderator_access'}.get(capability)
    return bool(permission and _flag(account,permission))


def require_moderator():
    account=user()
    if not account:abort(401,description='Inicia sesión para moderar aportaciones.')
    if account['must_change']:abort(403,description='Cambia tu contraseña provisional antes de moderar.')
    if not moderator_allowed(account):abort(403,description='Esta sección requiere el permiso de Moderador de contenido.')
    return account


def register_guest_target(app,target_type,validate,publish):
    """Registra un destino externo sin acoplar participación a su módulo.

    validate(connection,target_id) devuelve label, snapshot y version opcional.
    publish(connection,submission,moderator_id,stamp) devuelve target_type,
    target_id y url del comentario ya creado.
    """
    if target_type in BUILTIN_TARGETS:raise ValueError('El tipo está reservado por participación.')
    targets=app.extensions.setdefault('pls_guest_targets',{})
    if target_type in targets:raise ValueError(f'El destino invitado {target_type} ya está registrado.')
    targets[target_type]={'validate':validate,'publish':publish}


def register_participation(app):
    app.extensions.setdefault('pls_guest_targets',{})
    app.register_blueprint(bp)


def _text(data,key,limit,required=False):
    value=data.get(key,'')
    if not isinstance(value,str):abort(400,description=f'El campo {key} debe ser texto.')
    value=value.strip()
    if len(value)>limit or (required and not value):abort(400,description=f'Revisa el campo {key} (máximo {limit} caracteres).')
    return value


def _contacts(data):
    contact={
        'contact_name':_text(data,'contact_name',160),
        'contact_organization':_text(data,'contact_organization',200),
        'contact_phone':_text(data,'contact_phone',60),
        'contact_email':_text(data,'contact_email',254),
    }
    if contact['contact_email'] and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',contact['contact_email']):
        abort(400,description='Revisa el correo de contacto o déjalo vacío.')
    if contact['contact_phone'] and not re.fullmatch(r'[0-9+().\-\s]{5,60}',contact['contact_phone']):
        abort(400,description='Revisa el teléfono de contacto o déjalo vacío.')
    return contact


def _integer(value,label):
    try:result=int(value)
    except (TypeError,ValueError):abort(400,description=f'Revisa {label}.')
    if result<1:abort(400,description=f'Revisa {label}.')
    return result


def _identifier(value,label='el destino'):
    if isinstance(value,int) and not isinstance(value,bool) and value>0:return str(value)
    if isinstance(value,str) and 0<len(value.strip())<=100:return value.strip()
    abort(400,description=f'Revisa {label}.')


def _validate_document(connection,data):
    slug=_text(data,'target_id',100,True)
    if slug in PROTECTED_DOCUMENTS:abort(403,description='El núcleo de bases requiere una cuenta habilitada para participar.')
    document=connection.execute('SELECT * FROM documents WHERE slug=? AND hidden=0',(slug,)).fetchone()
    if not document:abort(404)
    version=_integer(data.get('target_version'),'la versión del documento')
    if version!=document['version']:abort(409,description='El documento cambió. Recarga y vuelve a seleccionar el texto.')
    section_id=_text(data,'section',150,True)
    section=next((part for part in sections(document['html']) if part['id']==section_id),None)
    if not section:abort(400,description='La sección no existe.')
    quote=_text(data,'quote',6000);prefix=_text(data,'prefix',150);suffix=_text(data,'suffix',150)
    if quote and quote not in section['text']:abort(400,description='El fragmento no coincide. Selecciónalo de nuevo o comenta la sección completa.')
    return dict(target_id=slug,target_version=version,target_label=f'{document["title"]} · {section["title"]}',
        target_snapshot=section['text'],section=section_id,section_title=section['title'],quote=quote,prefix=prefix,suffix=suffix)


def _validate_drive(connection,data):
    ident=_integer(data.get('target_id'),'el elemento del archivo')
    item=connection.execute('SELECT * FROM drive_items WHERE id=? AND active=1',(ident,)).fetchone()
    if not item:abort(404)
    return dict(target_id=str(ident),target_version=item['version'],
        target_label=('Carpeta' if item['kind']=='folder' else 'Archivo')+': '+item['name'],target_snapshot=drive_snapshot(item),
        section='resource',section_title=('Carpeta' if item['kind']=='folder' else 'Archivo')+': '+item['name'],quote='',prefix='',suffix='')


def _validate_thread(connection,data):
    ident=_integer(data.get('target_id'),'la discusión')
    thread=connection.execute('''SELECT t.*,d.hidden,COALESCE(di.active,0) AS drive_active
        FROM threads t JOIN documents d ON d.slug=t.document
        LEFT JOIN drive_items di ON di.id=t.drive_item_id WHERE t.id=?''',(ident,)).fetchone()
    if not thread:abort(404)
    if thread['target_type']=='drive':
        if not thread['drive_active']:abort(404)
    elif thread['hidden']:abort(404)
    if thread['document'] in PROTECTED_DOCUMENTS:abort(403,description='El núcleo de bases requiere una cuenta habilitada para participar.')
    if thread['state']=='archived':abort(409,description='La discusión está archivada.')
    return dict(target_id=str(ident),target_version=thread['version'],target_label='Discusión: '+thread['title'],
        target_snapshot='',section='',section_title='',quote='',prefix='',suffix='')


def _validate_external(connection,target_type,data):
    adapter=current_app.extensions.get('pls_guest_targets',{}).get(target_type)
    if not adapter:abort(400,description='El destino de la aportación no está disponible.')
    target_id=_identifier(data.get('target_id'))
    result=adapter['validate'](connection,target_id)
    if not isinstance(result,dict) or not result.get('label'):raise RuntimeError('El adaptador invitado no devolvió un destino válido.')
    version=result.get('version')
    if version is not None and (isinstance(version,bool) or not isinstance(version,int)):raise RuntimeError('La versión del destino invitado es inválida.')
    return dict(target_id=target_id,target_version=version,target_label=str(result['label'])[:300],
        target_snapshot=str(result.get('snapshot',''))[:12000],section='',section_title='',quote='',prefix='',suffix='')


@bp.post('/api/participation/submissions')
def create_submission():
    if user():abort(409,description='Tu sesión ya está identificada. Usa el formulario de tu cuenta para participar.')
    data=request.get_json()
    if not isinstance(data,dict):abort(400,description='Solicitud inválida.')
    submission_type=_text(data,'submission_type',20,True)
    target_type=_text(data,'target_type',40,True)
    if submission_type not in {'thread','comment'}:abort(400,description='Tipo de aportación inválido.')
    if submission_type=='thread' and target_type not in {'document','drive'}:abort(400,description='Ese destino no admite una discusión invitada.')
    if submission_type=='comment' and target_type=='document':abort(400,description='Selecciona una discusión para comentar.')
    display_name=_text(data,'display_name',120,True);message=_text(data,'body',10000,True)
    title=_text(data,'title',160,submission_type=='thread')
    contacts=_contacts(data)
    address=request.headers.get('CF-Connecting-IP',request.remote_addr or '')
    limited('guest-submission:'+hashlib.sha256(address.encode()).hexdigest(),10,3600)
    connection=db()
    if target_type=='document':target=_validate_document(connection,data)
    elif target_type=='drive':target=_validate_drive(connection,data)
    elif target_type=='thread':target=_validate_thread(connection,data)
    else:target=_validate_external(connection,target_type,data)
    stamp=now();connection.execute('BEGIN IMMEDIATE')
    values=(submission_type,target_type,target['target_id'],target['target_version'],target['target_label'],target['target_snapshot'],
        target['section'],target['section_title'],target['quote'],target['prefix'],target['suffix'],title,message,display_name,
        contacts['contact_name'],contacts['contact_organization'],contacts['contact_phone'],contacts['contact_email'],stamp)
    cursor=connection.execute('''INSERT INTO guest_submissions(submission_type,target_type,target_id,target_version,target_label,target_snapshot,
        section,section_title,quote,prefix,suffix,title,body,display_name,contact_name,contact_organization,contact_phone,contact_email,created)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',values)
    submission_id=cursor.lastrowid
    connection.execute("INSERT INTO guest_submission_events(submission_id,kind,detail,created) VALUES(?,'submitted','Aportación recibida para moderación.',?)",(submission_id,stamp))
    connection.commit()
    return jsonify(id=submission_id,message='Recibimos tu aportación. Una persona moderadora la revisará antes de publicarla.'),202


@bp.get('/moderacion/aportaciones')
def moderation_queue():
    require_moderator()
    rows=db().execute("SELECT * FROM guest_submissions WHERE status='pending' ORDER BY id").fetchall()
    return render_template('participation/queue.html',title='Moderación de aportaciones',submissions=rows)


def _attribution(connection,submission,target_type,target_id,stamp):
    connection.execute('INSERT INTO guest_attributions(submission_id,target_type,target_id,display_name,created) VALUES(?,?,?,?,?)',
        (submission['id'],target_type,target_id,submission['display_name'],stamp))


def _publish_thread(connection,submission,moderator_id,stamp):
    if submission['target_type']=='document':
        document=connection.execute('SELECT * FROM documents WHERE slug=? AND hidden=0',(submission['target_id'],)).fetchone()
        if not document:abort(404)
        if document['slug'] in PROTECTED_DOCUMENTS:abort(403,description='El núcleo de bases no admite aportaciones invitadas.')
        cursor=connection.execute('''INSERT INTO threads(document,version,section,section_title,section_snapshot,quote,prefix,suffix,title,topic,author,created,updated)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(submission['target_id'],submission['target_version'],submission['section'],submission['section_title'],
            submission['target_snapshot'],submission['quote'],submission['prefix'],submission['suffix'],submission['title'],short_sentence(submission['body']),moderator_id,stamp,stamp))
    else:
        item=connection.execute('SELECT * FROM drive_items WHERE id=? AND active=1',(_integer(submission['target_id'],'el elemento del archivo'),)).fetchone()
        if not item:abort(409,description='El elemento ya no está disponible en el archivo público.')
        cursor=connection.execute("""INSERT INTO threads(document,version,section,section_title,section_snapshot,title,topic,author,created,updated,target_type,drive_item_id)
            VALUES('archivo-proton',?,'resource',?,?,?,?,?,?,?,'drive',?)""",(submission['target_version'],submission['section_title'],submission['target_snapshot'],
            submission['title'],short_sentence(submission['body']),moderator_id,stamp,stamp,item['id']))
    thread_id=cursor.lastrowid
    comment=connection.execute('INSERT INTO comments(thread_id,author,body,created) VALUES(?,?,?,?)',(thread_id,moderator_id,submission['body'],stamp))
    _attribution(connection,submission,'thread',thread_id,stamp);_attribution(connection,submission,'comment',comment.lastrowid,stamp)
    connection.execute("INSERT INTO events(thread_id,actor,kind,detail,created) VALUES(?,NULL,'opened','Se aprobó y publicó una aportación de una persona invitada.',?)",(thread_id,stamp))
    return {'target_type':'thread','target_id':thread_id,'url':f'/discusiones/{thread_id}'}


def _publish_comment(connection,submission,moderator_id,stamp):
    thread_id=_integer(submission['target_id'],'la discusión')
    thread=connection.execute('''SELECT t.*,d.hidden,COALESCE(di.active,0) AS drive_active
        FROM threads t JOIN documents d ON d.slug=t.document
        LEFT JOIN drive_items di ON di.id=t.drive_item_id WHERE t.id=?''',(thread_id,)).fetchone()
    if not thread:abort(404)
    if thread['target_type']=='drive':
        if not thread['drive_active']:abort(409,description='El elemento ya no está disponible en el archivo público.')
    elif thread['hidden']:abort(404)
    if thread['document'] in PROTECTED_DOCUMENTS:abort(403,description='El núcleo de bases no admite aportaciones invitadas.')
    if thread['state']=='archived':abort(409,description='La discusión está archivada.')
    cursor=connection.execute('INSERT INTO comments(thread_id,author,body,created) VALUES(?,?,?,?)',(thread_id,moderator_id,submission['body'],stamp))
    _attribution(connection,submission,'comment',cursor.lastrowid,stamp)
    connection.execute('UPDATE threads SET updated=? WHERE id=?',(stamp,thread_id))
    return {'target_type':'comment','target_id':cursor.lastrowid,'url':f'/discusiones/{thread_id}#mensaje-{cursor.lastrowid}'}


@bp.post('/api/participation/submissions/<int:ident>/moderate')
def moderate_submission(ident):
    moderator=require_moderator();data=request.get_json()
    if not isinstance(data,dict):abort(400,description='Solicitud inválida.')
    action=_text(data,'action',20,True);reason=_text(data,'reason',2000)
    if action not in {'approve','reject'}:abort(400,description='Acción de moderación inválida.')
    if action=='reject' and not reason:abort(400,description='Explica por qué se descarta la aportación.')
    connection=db();connection.execute('BEGIN IMMEDIATE')
    submission=connection.execute("SELECT * FROM guest_submissions WHERE id=? AND status='pending'",(ident,)).fetchone()
    if not submission:abort(409,description='La aportación ya fue atendida o no existe.')
    stamp=now();result=None
    if action=='reject':
        connection.execute("UPDATE guest_submissions SET status='rejected',reviewed=?,moderator=?,moderation_reason=? WHERE id=?",(stamp,moderator['id'],reason,ident))
        connection.execute("INSERT INTO guest_submission_events(submission_id,actor,kind,detail,created) VALUES(?,?,'rejected',?,?)",(ident,moderator['id'],reason,stamp))
    else:
        if submission['submission_type']=='thread':result=_publish_thread(connection,submission,moderator['id'],stamp)
        elif submission['target_type']=='thread':result=_publish_comment(connection,submission,moderator['id'],stamp)
        else:
            adapter=current_app.extensions.get('pls_guest_targets',{}).get(submission['target_type'])
            if not adapter:abort(409,description='El módulo de destino no está disponible para publicar esta aportación.')
            adapter['validate'](connection,submission['target_id'])
            result=adapter['publish'](connection,submission,moderator['id'],stamp)
            if not isinstance(result,dict) or not result.get('target_type') or not result.get('target_id'):
                raise RuntimeError('El adaptador invitado no devolvió la publicación creada.')
            _attribution(connection,submission,result['target_type'],int(result['target_id']),stamp)
        connection.execute("UPDATE guest_submissions SET status='approved',reviewed=?,moderator=?,moderation_reason=?,published_type=?,published_id=? WHERE id=?",
            (stamp,moderator['id'],reason,result['target_type'],result['target_id'],ident))
        connection.execute("INSERT INTO guest_submission_events(submission_id,actor,kind,detail,created) VALUES(?,?,'approved','Aportación aprobada y publicada.',?)",(ident,moderator['id'],stamp))
    connection.commit()
    return jsonify(ok=True,url=result.get('url') if result else None)
