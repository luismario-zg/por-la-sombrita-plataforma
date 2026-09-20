"""Persistencia, contenido y controles compartidos del prototipo."""
from pathlib import Path
import hashlib, re, secrets, sqlite3, time
from datetime import datetime, timezone
from bs4 import BeautifulSoup
import bleach
from flask import current_app, g, abort, request

ROLES={'owner':'Administrador general','admin':'Administrador','reviewer':'Revisor','member':'Participante','reader':'Solo lectura'}
STATES={'open':'Abierta','closing':'Cierre propuesto','archived':'Archivada'}
THREAD_SELECT='''SELECT t.*, u.name AS author_name, d.title AS base_document_title,
CASE WHEN t.target_type='drive' THEN di.name ELSE d.title END AS document_title,
CASE WHEN t.target_type='drive' THEN di.version ELSE d.version END AS current_version,
CASE WHEN t.target_type='drive' THEN di.kind ELSE 'document' END AS target_kind,
CASE WHEN t.target_type='drive' THEN di.path ELSE '' END AS resource_path,
CASE WHEN t.target_type='drive' THEN di.active ELSE 1 END AS resource_active,
CASE WHEN t.target_type='drive' THEN '/archivo-proton/' || di.id ELSE '/' || t.document || '.html?hilo=' || t.id || '#' || t.section END AS target_url
FROM threads t JOIN users u ON u.id=t.author JOIN documents d ON d.slug=t.document
LEFT JOIN drive_items di ON di.id=t.drive_item_id'''

def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')

def connect(path):
    c=sqlite3.connect(path,timeout=15); c.row_factory=sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON');c.execute('PRAGMA busy_timeout=15000');c.execute('PRAGMA journal_mode=WAL')
    return c

def db():
    if 'db' not in g:g.db=connect(current_app.config['DATABASE'])
    return g.db

def init_db(path):
    Path(path).parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    with connect(path) as c:
        c.executescript((Path(__file__).parent/'schema.sql').read_text())
        # Gunicorn crea la aplicación en cada worker. Serializar la inspección y
        # las migraciones evita que dos procesos intenten añadir la misma columna.
        c.execute('BEGIN IMMEDIATE')
        # Migraciones aditivas para instalaciones creadas por versiones anteriores.
        document_columns={r['name'] for r in c.execute('PRAGMA table_info(documents)')}
        if 'hidden' not in document_columns:
            c.execute('ALTER TABLE documents ADD COLUMN hidden INTEGER NOT NULL DEFAULT 0')
        thread_columns={r['name'] for r in c.execute('PRAGMA table_info(threads)')}
        if 'target_type' not in thread_columns:
            c.execute("ALTER TABLE threads ADD COLUMN target_type TEXT NOT NULL DEFAULT 'document'")
        if 'drive_item_id' not in thread_columns:
            c.execute('ALTER TABLE threads ADD COLUMN drive_item_id INTEGER REFERENCES drive_items(id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_threads_drive ON threads(drive_item_id,id)')
        development_columns={r['name'] for r in c.execute('PRAGMA table_info(development_items)')}
        for name in ['dimensions','analysis','next_step','proposal','alternatives','resolver','timing','related_items']:
            if name not in development_columns:c.execute(f"ALTER TABLE development_items ADD COLUMN {name} TEXT NOT NULL DEFAULT ''")
    Path(path).chmod(0o600)

def user():
    if 'current_user' not in g:
        token=request.cookies.get(current_app.config['COOKIE_NAME'],'')
        s=db().execute('SELECT * FROM sessions WHERE token_hash=? AND expires>?',(hashlib.sha256(token.encode()).hexdigest(),int(time.time()))).fetchone() if token else None
        g.session=s
        g.current_user=db().execute('SELECT * FROM users WHERE id=? AND active=1',(s['user_id'],)).fetchone() if s and s['user_id'] else None
    return g.current_user

def require(*roles, password=True):
    u=user()
    if not u:abort(401,description='Inicia sesión para participar.')
    if password and u['must_change']:abort(403,description='Cambia tu contraseña provisional antes de participar.')
    if roles and u['role'] not in roles:abort(403,description='Tu cuenta no tiene permiso para esta acción.')
    return u

def field(data,key,limit=1000,required=True):
    v=data.get(key,'')
    if not isinstance(v,str):abort(400,description=f'El campo {key} debe ser texto.')
    v=v.strip()
    if len(v)>limit or (required and not v):abort(400,description=f'Revisa el campo {key} (máximo {limit} caracteres).')
    return v

def number(data,key):
    v=data.get(key)
    if isinstance(v,bool) or not isinstance(v,int) or v<1:abort(400,description=f'Revisa {key}.')
    return v

def limited(key,maximum,seconds):
    stamp=int(time.time());c=db()
    c.execute('INSERT INTO limits(key,count,until) VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=CASE WHEN until<=? THEN 1 ELSE count+1 END, until=CASE WHEN until<=? THEN ? ELSE until END',(key,stamp+seconds,stamp,stamp,stamp+seconds));c.commit()
    r=c.execute('SELECT count FROM limits WHERE key=?',(key,)).fetchone()
    if r['count']>maximum:abort(429,description='Demasiados intentos. Espera unos minutos antes de repetir.')

def sections(body):
    soup=BeautifulSoup(body,'html.parser');out=[];part=None
    for el in list(soup.contents):
        if getattr(el,'name',None)=='h2':
            ident=el.get('id') or 'seccion-'+str(len(out)+1)
            part={'id':ident,'title':el.get_text(' ',strip=True),'html':''};out.append(part)
        elif part is None:
            if str(el).strip():part={'id':'introduccion','title':'Introducción','html':str(el)};out.append(part)
        else:part['html']+=str(el)
    for s in out:s['text']=BeautifulSoup(s['html'],'html.parser').get_text()
    return out

def clean_html(value):
    tags={'p','h2','h3','h4','strong','em','a','ul','ol','li','blockquote','table','thead','tbody','tr','th','td','div','span','br','hr','code','pre'}
    cleaned=bleach.clean(value,tags=tags,attributes={'a':['href','title'],'h2':['id'],'h3':['id'],'div':['class','tabindex','role','aria-label'],'th':['scope'],'td':['colspan']},protocols=['http','https','mailto'],strip=True)
    soup=BeautifulSoup(cleaned,'html.parser');seen=set()
    for link in soup.find_all('a',href=True):
        href=link['href']
        if re.match(r'^[a-z][a-z-]*\.html(?:[?#]|$)',href):link['href']='/'+href
    for i,h in enumerate(soup.find_all('h2'),1):
        ident=h.get('id','')
        if not re.fullmatch(r'[\w-]{1,150}',ident) or ident in seen:ident=f'seccion-{i}'
        while ident in seen:ident+='-nueva'
        h['id']=ident;seen.add(ident)
    return str(soup)

def event(c,actor,kind,detail,thread=None):
    c.execute('INSERT INTO events(thread_id,actor,kind,detail,created) VALUES(?,?,?,?,?)',(thread,actor,kind,detail,now()))

def thread_data(ident):
    t=db().execute(THREAD_SELECT+' WHERE t.id=?',(ident,)).fetchone()
    if not t:abort(404)
    comments=db().execute('SELECT c.*,u.name FROM comments c JOIN users u ON u.id=c.author WHERE c.thread_id=? ORDER BY c.id',(ident,)).fetchall()
    review=db().execute('SELECT r.*,u.name FROM reviews r JOIN users u ON u.id=r.author WHERE thread_id=? ORDER BY r.id DESC LIMIT 1',(ident,)).fetchone()
    return t,comments,review

def drive_snapshot(item):
    kind={'folder':'Carpeta','file':'Archivo','native':'Documento nativo de Proton'}[item['kind']]
    state='Disponible en el archivo público' if item['active'] else 'Ya no aparece en el archivo público actual'
    details=[f'Tipo: {kind}',f'Ruta: {item["path"] or "Raíz de Por La Sombrita MTY General"}',f'Estado: {state}',f'Versión indexada: {item["version"]}']
    if item['media_type']:details.append(f'Formato: {item["media_type"]}')
    if item['size']:details.append(f'Tamaño: {item["size"]} bytes')
    if item['mtime']:details.append(f'Última modificación informada por Proton: {item["mtime"]}')
    return '\n'.join(details)

def short_sentence(text,maxlen=180):
    text=re.sub(r'\s+',' ',text).strip()
    first=re.split(r'(?<=[.!?])\s',text,maxsplit=1)[0]
    return first if len(first)<=maxlen else first[:maxlen-1].rsplit(' ',1)[0]+'…'

REVIEW_FIELDS=['topic','question','context','current_text','proposed_text','summary','agreements','disagreements','pending','evidence']

def valid_review(payload):
    if not isinstance(payload,dict):raise ValueError('Ficha inválida.')
    result={}
    for k in REVIEW_FIELDS:
        v=payload.get(k)
        if not isinstance(v,str) or len(v)>12000:raise ValueError('La ficha debe incluir todos sus campos como texto.')
        result[k]=v.strip()
    if not result['topic'] or not result['question'] or not result['summary']:raise ValueError('Tema, pregunta y resumen son obligatorios.')
    result['topic']=short_sentence(result['topic'])
    return result
