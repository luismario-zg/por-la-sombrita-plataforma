#!/usr/bin/env python3
"""Indexa en modo público la carpeta compartida de Proton, sin copiar secretos."""
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import sys
import unicodedata
from pathlib import Path, PurePosixPath

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core import connect, init_db, now

PUBLIC_ROOT='Por La Sombrita MTY General'
DEFAULT_MIRROR=Path('/home/claude/projects/pls_proton/espejo')/PUBLIC_ROOT
DEFAULT_MANIFEST=Path('/home/claude/projects/pls_proton/control/sync-state/manifiesto-remoto.json')
DEFAULT_NATIVE=Path('/home/claude/projects/pls_proton/control/sync-state/documentos-proton-no-descargables.json')
PROTON_PUBLIC_URL='https://drive.proton.me/urls/YDN71HHPW8#exZbmfOdOazj'

DENIED_WORDS={
    'promotor','promotora','promotores','promotoras','privado','privada','private',
    'secreto','secretos','secret','secrets','password','passwords','contrasena',
    'contrasenas','credencial','credenciales','credential','credentials','token',
    'tokens','acceso','accesos','recovery','recuperacion','respaldo-credenciales',
}
DENIED_SUFFIXES={'.env','.pem','.key','.p12','.pfx','.kdbx','.sqlite','.sqlite3','.db','.log'}
TEXT_SUFFIXES={'.txt','.md','.html','.htm','.json','.jsonl','.yaml','.yml','.xml','.csv','.py','.js','.css','.sh','.service','.toml','.ini','.cfg'}
NATIVE_TYPES={'application/vnd.proton.doc','application/vnd.proton.sheet'}
SECRET_PATTERNS=[
    re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',re.I),
    re.compile(r'\b(?:password|contrasena|contraseña)\s*[:=]\s*[^\s<{][^\r\n]{5,}',re.I),
    re.compile(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{30,}'),
    re.compile(r'\bgh[pousr]_[A-Za-z0-9]{30,}'),
]

def normalized(value:str)->str:
    return ''.join(c for c in unicodedata.normalize('NFKD',value.casefold()) if not unicodedata.combining(c))

def denied_path(relative:str)->str|None:
    parts=PurePosixPath(relative).parts
    for part in parts:
        if part.startswith('.'):
            return 'ruta oculta'
        words={w for w in re.split(r'[^a-z0-9]+',normalized(part)) if w}
        if words & DENIED_WORDS:
            return 'ruta reservada por nombre'
    if PurePosixPath(relative).suffix.lower() in DENIED_SUFFIXES:
        return 'formato reservado'
    return None

def safe_local(mirror:Path,relative:str)->Path|None:
    target=mirror/Path(relative)
    try:
        resolved=target.resolve(strict=True)
        resolved.relative_to(mirror.resolve(strict=True))
    except (OSError,ValueError):
        return None
    if target.is_symlink() or not resolved.is_file():
        return None
    return resolved

def contains_secret(path:Path)->bool:
    if path.suffix.lower() not in TEXT_SUFFIXES or path.stat().st_size>5*1024*1024:
        return False
    try:text=path.read_text(encoding='utf-8',errors='replace')
    except OSError:return True
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)

def hash_file(path:Path)->str:
    digest=hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda:source.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()

def relative_from_public(path:str)->str|None:
    if path==PUBLIC_ROOT:return ''
    prefix=PUBLIC_ROOT+'/'
    return path[len(prefix):] if path.startswith(prefix) else None

def parent(path:str)->str|None:
    if not path:return None
    p=PurePosixPath(path).parent.as_posix()
    return '' if p=='.' else p

def fingerprint_folder(path:str,entries:list[dict])->str:
    prefix=path+'/' if path else ''
    material=[]
    for item in entries:
        item_path=item['path']
        if item_path.startswith(prefix) and item_path!=path:
            material.append(item_path+'\0'+item['source_revision'])
    return hashlib.sha256('\n'.join(sorted(material)).encode()).hexdigest()

def index(database:Path,mirror:Path=DEFAULT_MIRROR,manifest:Path=DEFAULT_MANIFEST,native_manifest:Path=DEFAULT_NATIVE)->dict:
    init_db(database)
    remote=json.loads(manifest.read_text())
    native=json.loads(native_manifest.read_text()) if native_manifest.is_file() else {'entries':[]}
    candidates=[];excluded=[]

    candidates.append({'path':'','parent_path':None,'name':PUBLIC_ROOT,'kind':'folder','media_type':'','size':0,'local_rel':'','remote_path':'/my-files/'+PUBLIC_ROOT,'source_revision':'','mtime':''})
    for raw in remote.get('entries',[]):
        relative=relative_from_public(raw.get('path',''))
        if relative is None or relative=='':continue
        reason=denied_path(relative)
        if reason:
            excluded.append((relative,reason));continue
        if raw.get('type')=='folder':
            candidates.append({'path':relative,'parent_path':parent(relative),'name':PurePosixPath(relative).name,'kind':'folder','media_type':'','size':0,'local_rel':'','remote_path':raw.get('remote_path',''),'source_revision':'','mtime':''})
            continue
        if raw.get('media_type') in NATIVE_TYPES:
            # Se incorporan más abajo desde el inventario específico, sin exigir copia local.
            continue
        local=safe_local(mirror,relative)
        if not local:
            excluded.append((relative,'archivo local ausente o no regular'));continue
        if contains_secret(local):
            excluded.append((relative,'patrón de secreto en contenido de texto'));continue
        media=raw.get('media_type') or mimetypes.guess_type(relative)[0] or 'application/octet-stream'
        revision=raw.get('revision_uid') or raw.get('sha1') or hash_file(local)
        candidates.append({'path':relative,'parent_path':parent(relative),'name':PurePosixPath(relative).name,'kind':'file','media_type':media,'size':int(raw.get('size') or local.stat().st_size),'local_rel':relative,'remote_path':raw.get('remote_path',''),'source_revision':revision,'mtime':raw.get('mtime') or ''})

    existing={x['path'] for x in candidates}
    for raw in native.get('entries',[]):
        relative=relative_from_public(raw.get('path',''))
        if relative is None or relative in existing:continue
        reason=denied_path(relative)
        if reason:
            excluded.append((relative,reason));continue
        # Si un documento nativo existe, sus carpetas ya deben proceder del manifiesto.
        if parent(relative) not in existing:
            excluded.append((relative,'carpeta padre no publicada'));continue
        candidates.append({'path':relative,'parent_path':parent(relative),'name':PurePosixPath(relative).name,'kind':'native','media_type':raw.get('media_type') or 'application/vnd.proton.doc','size':int(raw.get('size') or 0),'local_rel':'','remote_path':raw.get('remote_path',''),'source_revision':raw.get('revision_uid') or 'native','mtime':raw.get('mtime') or ''})
        existing.add(relative)

    # Una carpeta cambia de versión cuando cambia cualquier elemento público de su subárbol.
    for item in candidates:
        if item['kind']=='folder':item['source_revision']=fingerprint_folder(item['path'],candidates)

    stamp=now()
    with connect(database) as c:
        c.execute('BEGIN IMMEDIATE')
        c.execute("INSERT INTO documents(slug,title,intro,version,status,html,updated,hidden) VALUES('archivo-proton','Archivo público de Proton','Contexto técnico para discusiones del archivo',1,'proposal','<h2 id=\"resource\">Elemento del archivo público de Proton</h2><p>Esta ficha representa una carpeta o archivo de solo lectura.</p>',?,1) ON CONFLICT(slug) DO UPDATE SET hidden=1",(stamp,))
        c.execute('UPDATE drive_items SET active=0,indexed=?',(stamp,))
        for item in candidates:
            previous=c.execute('SELECT source_revision,version FROM drive_items WHERE path=?',(item['path'],)).fetchone()
            version=(previous['version']+1 if previous and previous['source_revision']!=item['source_revision'] else previous['version']) if previous else 1
            c.execute('''INSERT INTO drive_items(path,parent_path,name,kind,media_type,size,local_rel,remote_path,source_revision,mtime,version,active,indexed)
            VALUES(:path,:parent_path,:name,:kind,:media_type,:size,:local_rel,:remote_path,:source_revision,:mtime,:version,1,:indexed)
            ON CONFLICT(path) DO UPDATE SET parent_path=excluded.parent_path,name=excluded.name,kind=excluded.kind,media_type=excluded.media_type,size=excluded.size,local_rel=excluded.local_rel,remote_path=excluded.remote_path,source_revision=excluded.source_revision,mtime=excluded.mtime,version=excluded.version,active=1,indexed=excluded.indexed''',{**item,'version':version,'indexed':stamp})
    result={'indexed':len(candidates),'folders':sum(x['kind']=='folder' for x in candidates),'files':sum(x['kind']=='file' for x in candidates),'native':sum(x['kind']=='native' for x in candidates),'excluded':len(excluded),'at':stamp}
    # No registrar públicamente las rutas excluidas; el detalle queda solo en stdout administrativo.
    print(json.dumps(result,ensure_ascii=False))
    if excluded:
        print('Exclusiones privadas:',len(excluded),file=sys.stderr)
    return result

if __name__=='__main__':
    data=Path(os.environ.get('PLS_DATA_DIR',str(Path.home()/'.local/share/pls-plataforma')))
    index(data/'plataforma.sqlite3')
