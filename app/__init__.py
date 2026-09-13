"""Plataforma pública de documentación y deliberación de Por la Sombrita."""
import hashlib, hmac, json, os, secrets, time
from pathlib import Path
from flask import Flask, render_template, request, jsonify, g, abort, redirect, make_response, send_from_directory, send_file
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash
from .core import *

def create_app(config=None):
    app=Flask(__name__)
    data=Path(os.environ.get('PLS_DATA_DIR',str(Path.home()/'.local/share/pls-plataforma')))
    app.config.update(
        DATABASE=str(data/'plataforma.sqlite3'),
        BASE_URL=os.environ.get('PLS_BASE_URL','https://plsmty.bespokem.mx'),
        COOKIE_NAME='__Host-pls',COOKIE_SECURE=True,MAX_CONTENT_LENGTH=262144,
        AI_ENABLED=os.environ.get('PLS_AI_ENABLED','0')=='1',
        PROTON_MIRROR=os.environ.get('PLS_PROTON_MIRROR','/home/claude/projects/pls_proton/espejo/Por La Sombrita MTY General'),
        PROTON_PUBLIC_URL='https://drive.proton.me/urls/YDN71HHPW8#exZbmfOdOazj',
    )
    if config:app.config.update(config)
    init_db(app.config['DATABASE'])
    app.config['DUMMY_HASH']=generate_password_hash(secrets.token_urlsafe(16))

    @app.teardown_appcontext
    def close_db(error):
        conn=g.pop('db',None)
        if conn:conn.close()

    @app.before_request
    def protect():
        g.nonce=secrets.token_urlsafe(18)
        if app.config['BASE_URL'].startswith('https://') and request.headers.get('X-Forwarded-Proto')=='http':
            return redirect(app.config['BASE_URL']+request.full_path.rstrip('?'),code=301)
        if request.method in {'POST','PUT','PATCH','DELETE'}:
            if request.headers.get('Origin')!=app.config['BASE_URL']:abort(403,description='Origen de solicitud no permitido.')
            if not request.is_json:abort(415,description='Se requiere una solicitud JSON.')
            user()
            if not g.session or not hmac.compare_digest(request.headers.get('X-CSRF-Token',''),g.session['csrf']):abort(403,description='La sesión de formulario expiró. Recarga la página.')

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options']='nosniff';response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
        response.headers['Cache-Control']='no-store'
        if request.endpoint=='drive_content':
            response.headers['Content-Security-Policy']="sandbox; default-src 'none'; frame-ancestors 'self'"
            response.headers['X-Frame-Options']='SAMEORIGIN'
            response.headers['X-Robots-Tag']='noindex, nofollow'
        else:
            response.headers['Content-Security-Policy']=f"default-src 'self'; script-src 'self' 'nonce-{g.nonce}'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-src 'self'; object-src 'self'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        if request.path.startswith('/api/') or request.path in ['/cuenta','/administracion']:response.headers['X-Robots-Tag']='noindex, nofollow'
        return response

    @app.errorhandler(HTTPException)
    def error(e):
        if request.path.startswith('/api/'):return jsonify(error=e.description),e.code
        return render_template('error.html',title='No se pudo abrir la página',code=e.code,message=e.description),e.code

    @app.context_processor
    def context():return dict(me=user(),roles=ROLES,states=STATES,base_url=app.config['BASE_URL'],nonce=g.nonce)

    @app.template_filter('filesize')
    def filesize(value):
        size=float(value or 0)
        for unit in ['B','KB','MB','GB']:
            if size<1024 or unit=='GB':return f'{size:.0f} {unit}' if unit=='B' else f'{size:.1f} {unit}'
            size/=1024

    def new_session(uid=None):
        token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
        old=request.cookies.get(app.config['COOKIE_NAME'],'')
        c=db();c.execute('DELETE FROM sessions WHERE expires<? OR token_hash=?',(int(time.time()),hashlib.sha256(old.encode()).hexdigest()))
        c.execute('INSERT INTO sessions VALUES(?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),uid,csrf,int(time.time())+(28800 if uid else 3600)));c.commit()
        return token,csrf

    def set_cookie(response,token):
        response.set_cookie(app.config['COOKIE_NAME'],token,max_age=28800,secure=app.config['COOKIE_SECURE'],httponly=True,samesite='Lax',path='/')
        return response

    def body():
        x=request.get_json()
        if not isinstance(x,dict):abort(400,description='Solicitud inválida.')
        return x

    @app.get('/')
    def home():
        docs=db().execute('SELECT slug,title,intro,status,version FROM documents WHERE hidden=0 ORDER BY rowid').fetchall()
        threads=db().execute(THREAD_SELECT+' ORDER BY t.updated DESC,t.id DESC LIMIT 4').fetchall()
        return render_template('home.html',title='Una ciudad más caminable',docs=docs,threads=threads)

    @app.get('/<slug>.html')
    def document(slug):
        if slug=='index':return redirect('/')
        if slug=='participa':return redirect('/participa')
        if slug=='404':abort(404)
        doc=db().execute('SELECT * FROM documents WHERE slug=?',(slug,)).fetchone()
        if not doc or doc['hidden']:abort(404)
        groups=db().execute('SELECT section,COUNT(*) AS total FROM threads WHERE document=? GROUP BY section',(slug,)).fetchall()
        counts={r['section']:r['total'] for r in groups}
        annotations=[dict(r) for r in db().execute("SELECT id,section,quote,prefix,suffix,title,state,version FROM threads WHERE document=? ORDER BY id",(slug,))]
        return render_template('document.html',title=doc['title'],doc=doc,sections=sections(doc['html']),counts=counts,annotations=annotations)

    @app.get('/documentos/<slug>/versiones')
    def versions(slug):
        doc=db().execute('SELECT * FROM documents WHERE slug=?',(slug,)).fetchone()
        if not doc or doc['hidden']:abort(404)
        revs=db().execute('SELECT r.*,u.name FROM revisions r LEFT JOIN users u ON u.id=r.author WHERE document=? ORDER BY version DESC',(slug,)).fetchall()
        return render_template('versions.html',title='Historial de '+doc['title'],doc=doc,revisions=revs)

    @app.get('/documentos/<slug>/versiones/<int:version>')
    def revision(slug,version):
        r=db().execute('SELECT r.*,d.title,u.name FROM revisions r JOIN documents d ON d.slug=r.document LEFT JOIN users u ON u.id=r.author WHERE document=? AND r.version=?',(slug,version)).fetchone()
        if not r or r['document']=='archivo-proton':abort(404)
        return render_template('revision.html',title=f"Versión {version} · {r['title']}",revision=r)

    @app.get('/discusiones')
    def discussions():
        state=request.args.get('estado','active');doc=request.args.get('documento','');section=request.args.get('seccion','');drive_id=request.args.get('archivo','')
        conditions=[];params=[]
        if state=='history':conditions.append("(t.state='archived' OR EXISTS(SELECT 1 FROM events e WHERE e.thread_id=t.id AND e.kind='archived'))")
        elif state=='all':pass
        else:conditions.append("t.state<>'archived'")
        if doc:conditions.append('t.document=?');params.append(doc)
        if section:conditions.append('t.section=?');params.append(section)
        if drive_id.isdigit():conditions.append('t.drive_item_id=?');params.append(int(drive_id))
        q=THREAD_SELECT
        if conditions:q+=' WHERE '+' AND '.join(conditions)
        q+=' ORDER BY t.updated DESC,t.id DESC'
        return render_template('threads.html',title='Historial de discusiones' if state=='history' else 'Discusiones',threads=db().execute(q,params).fetchall(),state=state)

    @app.get('/discusiones/<int:ident>')
    def discussion(ident):
        t,comments,review=thread_data(ident)
        payload=json.loads(review['payload']) if review else None
        stale=review and (review['comment_count']!=len(comments) or review['document_version']!=t['current_version'])
        events=db().execute('SELECT e.*,u.name FROM events e LEFT JOIN users u ON u.id=e.actor WHERE thread_id=? ORDER BY e.id',(ident,)).fetchall()
        job=db().execute('SELECT id,state,error FROM ai_jobs WHERE thread_id=? ORDER BY id DESC LIMIT 1',(ident,)).fetchone()
        return render_template('thread.html',title=t['title'],thread=t,comments=comments,review=review,payload=payload,stale=stale,events=events,job=job)

    @app.get('/discusiones/<int:ident>/fichas')
    def review_history(ident):
        t,comments,r=thread_data(ident)
        rows=db().execute('SELECT r.*,u.name FROM reviews r JOIN users u ON u.id=r.author WHERE thread_id=? ORDER BY r.id DESC',(ident,)).fetchall()
        versions=[{**dict(x),'fields':json.loads(x['payload'])} for x in rows]
        return render_template('review_history.html',title='Historial de fichas',thread=t,versions=versions)

    @app.get('/revision')
    def review_queue():
        query=THREAD_SELECT.replace('FROM threads',", (SELECT COUNT(*) FROM comments WHERE thread_id=t.id) AS comment_count FROM threads")
        threads=db().execute(query+" WHERE t.state<>'archived' ORDER BY CASE WHEN t.state='closing' THEN 0 ELSE 1 END,t.updated DESC").fetchall()
        return render_template('review_queue.html',title='Mesa de revisión y aprobación',threads=threads)

    def drive_row(ident):
        row=db().execute('SELECT * FROM drive_items WHERE id=?',(ident,)).fetchone()
        if not row:abort(404)
        return row

    def drive_breadcrumbs(item):
        result=[];path=item['path']
        while path is not None:
            row=db().execute('SELECT id,name,path FROM drive_items WHERE path=?',(path,)).fetchone()
            if not row:break
            result.append(row)
            path=None if row['path']=='' else ('/'.join(row['path'].split('/')[:-1]) if '/' in row['path'] else '')
        return list(reversed(result))

    def drive_file_path(item):
        if item['kind']!='file' or not item['active'] or not item['local_rel']:return None
        try:
            root=Path(app.config['PROTON_MIRROR']).resolve(strict=True)
            candidate=Path(app.config['PROTON_MIRROR'])/Path(item['local_rel'])
            resolved=candidate.resolve(strict=True);resolved.relative_to(root)
        except (OSError,ValueError):return None
        return None if candidate.is_symlink() or not resolved.is_file() else resolved

    @app.get('/archivo-proton')
    def drive_library():
        query=request.args.get('q','').strip()[:100]
        root=db().execute("SELECT * FROM drive_items WHERE path='' AND active=1").fetchone()
        results=[]
        if query:
            escaped=query.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
            results=db().execute("SELECT * FROM drive_items WHERE active=1 AND path<>'' AND (name LIKE ? ESCAPE '\\' OR path LIKE ? ESCAPE '\\') ORDER BY kind='folder' DESC,path LIMIT 100",(f'%{escaped}%',f'%{escaped}%')).fetchall()
        children=db().execute("SELECT * FROM drive_items WHERE active=1 AND parent_path='' ORDER BY kind<>'folder',name COLLATE NOCASE").fetchall() if root and not query else []
        threads=db().execute(THREAD_SELECT+' WHERE t.drive_item_id=? ORDER BY t.updated DESC',(root['id'],)).fetchall() if root else []
        return render_template('drive.html',title='Archivo público de Proton',item=root,children=children,crumbs=[root] if root else [],results=results,query=query,threads=threads,proton_url=app.config['PROTON_PUBLIC_URL'])

    @app.get('/archivo-proton/<int:ident>')
    def drive_item(ident):
        item=drive_row(ident)
        children=db().execute("SELECT * FROM drive_items WHERE active=1 AND parent_path=? ORDER BY kind<>'folder',name COLLATE NOCASE",(item['path'],)).fetchall() if item['kind']=='folder' and item['active'] else []
        threads=db().execute(THREAD_SELECT+' WHERE t.drive_item_id=? ORDER BY t.updated DESC',(ident,)).fetchall()
        preview=None;text_preview=None
        if item['kind']=='file' and item['active']:
            media=item['media_type'].split(';',1)[0].lower()
            if media=='application/pdf':preview='pdf'
            elif media in {'image/jpeg','image/png','image/gif','image/webp','image/avif'}:preview='image'
            elif media in {'video/mp4','video/webm'}:preview='video'
            elif media in {'audio/mpeg','audio/ogg','audio/wav','audio/webm'}:preview='audio'
            elif item['size']<=300000 and (media.startswith('text/') or Path(item['name']).suffix.lower() in {'.md','.json','.xml','.csv','.py','.js','.css','.sh','.yml','.yaml'}):
                path=drive_file_path(item)
                if path:text_preview=path.read_text(encoding='utf-8',errors='replace')
        return render_template('drive.html',title=item['name'],item=item,children=children,crumbs=drive_breadcrumbs(item),results=[],query='',threads=threads,preview=preview,text_preview=text_preview,proton_url=app.config['PROTON_PUBLIC_URL'])

    @app.get('/archivo-proton/contenido/<int:ident>')
    def drive_content(ident):
        item=drive_row(ident);path=drive_file_path(item)
        if not path:abort(404)
        media=item['media_type'].split(';',1)[0].lower()
        inline=request.args.get('vista')=='1' and media in {'application/pdf','image/jpeg','image/png','image/gif','image/webp','image/avif','video/mp4','video/webm','audio/mpeg','audio/ogg','audio/wav','audio/webm'}
        return send_file(path,mimetype=media or 'application/octet-stream',as_attachment=not inline,download_name=item['name'],conditional=True,max_age=0)

    @app.post('/api/archive/threads')
    def new_drive_thread():
        u=require('owner','admin','reviewer','member');data=body();limited('thread:'+str(u['id']),20,3600)
        item_id=number(data,'drive_item_id');title=field(data,'title',160);message=field(data,'body',10000)
        c=db();c.execute('BEGIN IMMEDIATE');item=c.execute('SELECT * FROM drive_items WHERE id=? AND active=1',(item_id,)).fetchone()
        if not item:abort(404)
        label=('Carpeta' if item['kind']=='folder' else 'Archivo')+': '+item['name'];snapshot=drive_snapshot(item);stamp=now()
        cur=c.execute("INSERT INTO threads(document,version,section,section_title,section_snapshot,title,topic,author,created,updated,target_type,drive_item_id) VALUES('archivo-proton',?,'resource',?,?,?,?,?,?,?,'drive',?)",(item['version'],label,snapshot,title,short_sentence(message),u['id'],stamp,stamp,item_id));tid=cur.lastrowid
        c.execute('INSERT INTO comments(thread_id,author,body,created) VALUES(?,?,?,?)',(tid,u['id'],message,stamp));event(c,u['id'],'opened','Se inició una discusión sobre un elemento del archivo público de Proton.',tid);c.commit()
        return jsonify(id=tid),201

    @app.get('/miembros')
    def members():
        rows=db().execute('SELECT id,name,role,membership,membership_reference FROM users WHERE active=1 ORDER BY name').fetchall()
        return render_template('members.html',title='Comunidad y membresía',members=rows)

    @app.get('/cuenta')
    def account():return render_template('account.html',title='Tu cuenta')

    @app.get('/administracion')
    def admin():
        require('owner')
        rows=db().execute('SELECT id,username,name,role,active,membership,membership_reference FROM users ORDER BY id').fetchall()
        return render_template('admin.html',title='Administrar cuentas y permisos',users=rows)

    @app.get('/participa')
    def participate():return render_template('participate.html',title='Participar en Por la Sombrita')

    @app.get('/api/session')
    def session():
        u=user();token=None
        if not g.session:
            limited('anon:'+hashlib.sha256(request.headers.get('CF-Connecting-IP',request.remote_addr or '').encode()).hexdigest(),180,3600)
            token,csrf=new_session()
        else:csrf=g.session['csrf']
        response=jsonify(csrf=csrf,user=dict(id=u['id'],name=u['name'],role=u['role'],must_change=bool(u['must_change'])) if u else None)
        return set_cookie(response,token) if token else response

    @app.post('/api/login')
    def login():
        data=body();name=field(data,'username',80).lower();password=field(data,'password',256)
        ip=request.headers.get('CF-Connecting-IP',request.remote_addr or '')
        limited('login-ip:'+hashlib.sha256(ip.encode()).hexdigest(),30,900)
        limited('login-user:'+hashlib.sha256(name.encode()).hexdigest(),10,900)
        u=db().execute('SELECT * FROM users WHERE username=?',(name,)).fetchone()
        ok=check_password_hash(u['password_hash'] if u else app.config['DUMMY_HASH'],password)
        if not ok or not u or not u['active']:abort(401,description='Usuario o contraseña incorrectos.')
        token,csrf=new_session(u['id'])
        return set_cookie(jsonify(ok=True,must_change=bool(u['must_change']),csrf=csrf),token)

    @app.post('/api/logout')
    def logout():
        require(password=False);token,csrf=new_session()
        return set_cookie(jsonify(ok=True,csrf=csrf),token)

    @app.post('/api/password')
    def password():
        u=require(password=False);data=body();old=field(data,'current',256);new=field(data,'password',256)
        limited('password:'+str(u['id']),10,900)
        if not check_password_hash(u['password_hash'],old):abort(400,description='La contraseña actual no coincide.')
        if len(new)<12 or old==new:abort(400,description='Usa una contraseña diferente de al menos 12 caracteres.')
        c=db();c.execute('UPDATE users SET password_hash=?,must_change=0 WHERE id=?',(generate_password_hash(new),u['id']));c.execute('DELETE FROM sessions WHERE user_id=?',(u['id'],));c.commit()
        token,csrf=new_session(u['id']);return set_cookie(jsonify(ok=True,csrf=csrf),token)

    @app.post('/api/threads')
    def new_thread():
        u=require('owner','admin','reviewer','member');data=body();limited('thread:'+str(u['id']),20,3600)
        slug=field(data,'document',100);version=number(data,'version');section=field(data,'section',150)
        title=field(data,'title',160);message=field(data,'body',10000);quote=field(data,'quote',6000,False);prefix=field(data,'prefix',150,False);suffix=field(data,'suffix',150,False)
        c=db();c.execute('BEGIN IMMEDIATE')
        doc=c.execute('SELECT * FROM documents WHERE slug=?',(slug,)).fetchone()
        if not doc:abort(404)
        if version!=doc['version']:abort(409,description='El documento cambió. Recarga y vuelve a seleccionar el texto.')
        sec=next((s for s in sections(doc['html']) if s['id']==section),None)
        if not sec:abort(400,description='La sección no existe.')
        if quote and quote not in sec['text']:abort(400,description='El fragmento no coincide. Selecciónalo de nuevo o comenta la sección completa.')
        cur=c.execute('INSERT INTO threads(document,version,section,section_title,section_snapshot,quote,prefix,suffix,title,topic,author,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(slug,version,section,sec['title'],sec['text'],quote,prefix,suffix,title,short_sentence(message),u['id'],now(),now()));tid=cur.lastrowid
        c.execute('INSERT INTO comments(thread_id,author,body,created) VALUES(?,?,?,?)',(tid,u['id'],message,now()));event(c,u['id'],'opened','Se inició la discusión.',tid);c.commit()
        return jsonify(id=tid),201

    @app.post('/api/threads/<int:ident>/comments')
    def comment(ident):
        u=require('owner','admin','reviewer','member');message=field(body(),'body',10000);limited('comment:'+str(u['id']),60,3600)
        c=db();c.execute('BEGIN IMMEDIATE');t,comments,r=thread_data(ident)
        if t['state']=='archived':abort(409,description='La discusión está archivada. Un administrador puede reabrirla.')
        c.execute('INSERT INTO comments(thread_id,author,body,created) VALUES(?,?,?,?)',(ident,u['id'],message,now()));c.execute('UPDATE threads SET updated=? WHERE id=?',(now(),ident));c.commit();return jsonify(ok=True)

    @app.post('/api/threads/<int:ident>/review')
    def save_review(ident):
        u=require('owner','admin','reviewer');data=body()
        try:payload=valid_review(data.get('review'))
        except ValueError as e:abort(400,description=str(e))
        count=number(data,'comment_count');version=number(data,'document_version')
        c=db();c.execute('BEGIN IMMEDIATE');t,comments,r=thread_data(ident)
        if t['state']=='archived':abort(409,description='Reabre la discusión antes de revisar su ficha.')
        if count!=len(comments) or version!=t['current_version']:abort(409,description='Hay mensajes o una versión documental nuevos. Recarga y revisa el contexto.')
        c.execute('INSERT INTO reviews(thread_id,payload,source,comment_count,document_version,author,created) VALUES(?,?,?,?,?,?,?)',(ident,json.dumps(payload,ensure_ascii=False),'human',count,version,u['id'],now()))
        c.execute('UPDATE threads SET topic=?,updated=? WHERE id=?',(payload['topic'],now(),ident));event(c,u['id'],'reviewed','Se guardó una versión humana de la ficha de revisión.',ident);c.commit();return jsonify(ok=True)

    @app.post('/api/threads/<int:ident>/approve-review')
    def approve_review(ident):
        u=require('owner','admin');rid=number(body(),'review_id');c=db();c.execute('BEGIN IMMEDIATE');t,comments,r=thread_data(ident)
        if t['state']=='archived' or not r or r['id']!=rid or r['comment_count']!=len(comments) or r['document_version']!=t['current_version']:abort(409,description='La ficha debe estar vigente y revisada antes de aprobarla.')
        c.execute('UPDATE reviews SET approved=1 WHERE id=?',(rid,));c.execute('UPDATE threads SET topic=?,updated=? WHERE id=?',(json.loads(r['payload'])['topic'],now(),ident));event(c,u['id'],'review_approved','Se aprobó la ficha como base de deliberación; no equivale a consenso comunitario.',ident);c.commit();return jsonify(ok=True)

    @app.post('/api/threads/<int:ident>/ai')
    def request_ai(ident):
        u=require('owner','admin','reviewer')
        if not app.config['AI_ENABLED']:abort(503,description='La generación asistida no está configurada. Puedes elaborar la ficha manualmente.')
        limited('ai:'+str(u['id']),20,86400);c=db();c.execute('BEGIN IMMEDIATE');t,comments,r=thread_data(ident)
        if t['state']=='archived':abort(409,description='La discusión está archivada.')
        if c.execute("SELECT 1 FROM ai_jobs WHERE thread_id=? AND state IN ('queued','running')",(ident,)).fetchone():abort(409,description='Ya hay una generación pendiente para este hilo.')
        cur=c.execute('INSERT INTO ai_jobs(thread_id,actor,created) VALUES(?,?,?)',(ident,u['id'],now()));c.commit();return jsonify(id=cur.lastrowid),202

    @app.post('/api/threads/<int:ident>/state')
    def thread_state(ident):
        u=require('owner','admin');data=body();action=field(data,'action',30);summary=field(data,'summary',5000)
        c=db();c.execute('BEGIN IMMEDIATE');t,comments,r=thread_data(ident)
        if action=='reopen':
            if t['state']=='open':abort(409,description='La discusión ya está abierta.')
            c.execute("UPDATE threads SET state='open',updated=? WHERE id=?",(now(),ident));event(c,u['id'],'reopened',summary,ident)
        elif action=='propose_close':
            if t['state']!='open':abort(409,description='El hilo debe estar abierto para proponer su cierre.')
            c.execute("UPDATE threads SET state='closing',updated=? WHERE id=?",(now(),ident));event(c,u['id'],'closing',summary,ident)
        elif action=='archive':
            if t['state']!='closing':abort(409,description='Propón el cierre antes de archivarlo.')
            if not r or not r['approved'] or r['comment_count']!=len(comments) or r['document_version']!=t['current_version']:abort(409,description='Revisa y aprueba una ficha vigente antes de archivar.')
            outcome=field(data,'outcome',30);rid=None
            if outcome not in ['edited','unchanged']:abort(400,description='Indica si terminó con edición o sin cambios.')
            if t['target_type']=='drive' and outcome!='unchanged':abort(400,description='El archivo de Proton es de solo lectura; registra el cierre sin una edición vinculada.')
            if outcome=='edited':
                rid=number(data,'revision_id');rev=c.execute('SELECT * FROM revisions WHERE id=? AND document=? AND source_thread=?',(rid,t['document'],ident)).fetchone()
                if not rev or rev['version']<=t['version']:abort(400,description='Vincula una edición real derivada de este hilo.')
            if data.get('consensus_confirmed') is not True:abort(400,description='Confirma que se registró el consenso; el sistema no lo infiere.')
            c.execute("UPDATE threads SET state='archived',summary=?,outcome=?,revision_id=?,updated=? WHERE id=?",(summary,outcome,rid,now(),ident));event(c,u['id'],'archived',summary,ident)
        else:abort(400,description='Acción desconocida.')
        c.commit();return jsonify(ok=True)

    @app.get('/editar/<slug>')
    def editor(slug):
        require('owner','admin');doc=db().execute('SELECT * FROM documents WHERE slug=?',(slug,)).fetchone()
        if not doc or doc['hidden']:abort(404)
        return render_template('editor.html',title='Editar '+doc['title'],doc=doc,source_thread=request.args.get('hilo',''))

    @app.post('/api/documents/<slug>')
    def edit_document(slug):
        u=require('owner','admin');data=body();version=number(data,'version');reason=field(data,'reason',2000);status=field(data,'status',20);ref=field(data,'reference',1000,False);content=field(data,'html',180000)
        if status not in ['proposal','official']:abort(400,description='Estado documental inválido.')
        if status=='official' and not ref:abort(400,description='Indica el acta o referencia que respalda la aprobación oficial.')
        cleaned=clean_html(content)
        if not sections(cleaned):abort(400,description='El documento necesita al menos una sección.')
        c=db();c.execute('BEGIN IMMEDIATE');doc=c.execute('SELECT * FROM documents WHERE slug=?',(slug,)).fetchone()
        if not doc:abort(404)
        if doc['version']!=version:abort(409,description='Otra persona editó este documento. Recarga antes de guardar.')
        thread_id=data.get('source_thread') or None
        if thread_id:
            if not isinstance(thread_id,int) or not c.execute("SELECT 1 FROM threads WHERE id=? AND document=? AND state<>'archived'",(thread_id,slug)).fetchone():abort(400,description='El hilo de origen no corresponde a este documento o está archivado.')
        c.execute('UPDATE documents SET html=?,version=?,status=?,reference=?,updated=? WHERE slug=?',(cleaned,version+1,status,ref,now(),slug))
        cur=c.execute('INSERT INTO revisions(document,version,html,status,reason,reference,author,source_thread,created) VALUES(?,?,?,?,?,?,?,?,?)',(slug,version+1,cleaned,status,reason,ref,u['id'],thread_id,now()))
        event(c,u['id'],'document_edited',f"Documento {slug}: versión {version+1}. {reason}",thread_id);c.commit();return jsonify(ok=True,revision_id=cur.lastrowid,version=version+1)

    @app.post('/api/users/<int:ident>')
    def permissions(ident):
        u=require('owner');data=body();role=field(data,'role',20);membership=field(data,'membership',20);ref=field(data,'reference',1000,False);active=data.get('active')
        if role not in ROLES or membership not in ['pending','official'] or not isinstance(active,bool):abort(400,description='Permisos inválidos.')
        if membership=='official' and not ref:abort(400,description='Registra la referencia de aprobación de membresía.')
        c=db();c.execute('BEGIN IMMEDIATE');target=c.execute('SELECT * FROM users WHERE id=?',(ident,)).fetchone()
        if not target:abort(404)
        if target['role']=='owner' and target['active'] and (role!='owner' or not active) and c.execute("SELECT COUNT(*) FROM users WHERE role='owner' AND active=1").fetchone()[0]<=1:abort(409,description='Debe quedar al menos un administrador general activo.')
        c.execute('UPDATE users SET role=?,membership=?,membership_reference=?,active=? WHERE id=?',(role,membership,ref,int(active),ident));c.execute('DELETE FROM sessions WHERE user_id=?',(ident,));event(c,u['id'],'permissions',f"Permisos actualizados para la cuenta {ident}.");c.commit();return jsonify(ok=True)

    @app.post('/api/users/<int:ident>/reset-password')
    def reset_password(ident):
        u=require('owner');c=db();target=c.execute('SELECT id FROM users WHERE id=?',(ident,)).fetchone()
        if not target:abort(404)
        provisional=secrets.token_urlsafe(12)
        c.execute('UPDATE users SET password_hash=?,must_change=1 WHERE id=?',(generate_password_hash(provisional),ident));c.execute('DELETE FROM sessions WHERE user_id=?',(ident,));event(c,u['id'],'password_reset',f'Se restableció el acceso de la cuenta {ident}; sin guardar la contraseña en el historial.');c.commit()
        return jsonify(password=provisional)

    @app.get('/robots.txt')
    def robots():return app.response_class('User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /administracion\nDisallow: /cuenta\nDisallow: /editar/\nDisallow: /archivo-proton/contenido/\nSitemap: '+app.config['BASE_URL']+'/sitemap.xml\n',mimetype='text/plain')

    @app.get('/sitemap.xml')
    def sitemap():
        from xml.sax.saxutils import escape
        paths=['/','/archivo-proton','/discusiones','/revision','/miembros','/participa']+[f"/{d['slug']}.html" for d in db().execute('SELECT slug FROM documents WHERE hidden=0')]+[f"/archivo-proton/{i['id']}" for i in db().execute("SELECT id FROM drive_items WHERE active=1 AND path<>''")]+[f"/discusiones/{t['id']}" for t in db().execute('SELECT id FROM threads')]
        return app.response_class('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+escape(app.config['BASE_URL']+p)+'</loc></url>' for p in paths)+'</urlset>',mimetype='application/xml')

    @app.get('/llms.txt')
    def llms():return app.response_class('# Por la Sombrita\n\nPrototipo de documentación y deliberación ciudadana. La lectura es pública. Cada documento indica si es propuesta u oficial y su referencia de aprobación. El archivo público de Proton es una biblioteca de solo lectura. Los resúmenes IA son borradores; no inferir consenso ni membresía.\n\n- [Documentos]('+app.config['BASE_URL']+'/)\n- [Archivo público de Proton]('+app.config['BASE_URL']+'/archivo-proton)\n- [Discusiones]('+app.config['BASE_URL']+'/discusiones)\n- [Historial]('+app.config['BASE_URL']+'/discusiones?estado=history)\n',mimetype='text/plain')

    @app.get('/assets/<path:filename>')
    def previous_assets(filename):
        return send_from_directory(app.static_folder,filename)

    @app.get('/descargas/<slug>.md')
    def download_text(slug):
        doc=db().execute('SELECT * FROM documents WHERE slug=?',(slug,)).fetchone()
        if not doc or doc['hidden']:abort(404)
        text='# '+doc['title']+'\n\nVersión '+str(doc['version'])+' · '+('Oficial' if doc['status']=='official' else 'Propuesta')+'\n\n'
        for sec in sections(doc['html']):text+='## '+sec['title']+'\n\n'+sec['text']+'\n\n'
        response=app.response_class(text,mimetype='text/markdown')
        response.headers['Content-Disposition']='attachment; filename="'+slug+'.md"'
        return response

    @app.get('/healthz')
    def health():db().execute('SELECT 1');return jsonify(ok=True)

    return app
