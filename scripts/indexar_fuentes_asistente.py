#!/usr/bin/env python3
"""Actualiza copias de fuentes públicas concretas; no sigue enlaces arbitrarios."""
import argparse
import os
import sys
import subprocess
import urllib.request
from pathlib import Path
from urllib.parse import urlparse
from bs4 import BeautifulSoup
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core import connect,now
from app.assistant import SCHEMA_SQL

WIKI='https://wiki.labnuevoleon.mx/index.php?title='
SOURCES=[
    ('Comunidad Por la Sombrita',WIKI+'Por_la_sombrita'),
    ('Por la Sombrita: dispositivos interactivos para confort peatonal',WIKI+'Por_la_sombrita:_dispositivos_interactivos_para_confort_peatonal'),
    ('Wiki LABNL',WIKI+'Wiki_LABNL'),
    ('Guía para Comunidades LABNL',WIKI+'Gu%C3%ADa_para_Comunidades_LABNL'),
]
for repository,paths in [
    ('por-la-sombrita-plataforma',['README.md','docs/OPERACION.md','docs/ROADMAP.md','docs/RESUMENES.md','SECURITY.md','app/core.py','app/__init__.py','app/community.py','app/participation.py']),
    ('por-la-sombrita-mty',['README.md']),
]:
    for path in paths:SOURCES.append((f'{repository} · {path}',f'https://raw.githubusercontent.com/luismario-zg/{repository}/HEAD/{path}'))

class SameHostRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        if urlparse(newurl).scheme!='https' or urlparse(newurl).netloc!=urlparse(req.full_url).netloc:
            raise ValueError('Redirección fuera de la fuente autorizada.')
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def refresh(database):
    opener=urllib.request.build_opener(SameHostRedirect());success=0;failed=[]
    # El código consultado corresponde a la revisión desplegada, no a otra rama.
    revision=subprocess.run(['git','rev-parse','HEAD'],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,check=True).stdout.strip()
    with connect(database) as c:c.executescript(SCHEMA_SQL)
    for title,url in SOURCES:
        if '/por-la-sombrita-plataforma/HEAD/' in url:url=url.replace('/HEAD/','/'+revision+'/')
        try:
            with opener.open(urllib.request.Request(url,headers={'User-Agent':'PorLaSombrita/1.0 (public-documentation-index)'}),timeout=18) as response:
                raw=response.read(1024*1024+1);content_type=response.headers.get('Content-Type','')
            if len(raw)>1024*1024:raise ValueError('Fuente demasiado grande.')
            text=raw.decode('utf-8')
            if 'html' in content_type:
                soup=BeautifulSoup(text,'html.parser')
                for node in soup(['script','style','nav','footer']):node.decompose()
                body=soup.select_one('.mw-parser-output') or soup.select_one('main') or soup
                text=body.get_text(' ',strip=True)
                if 'Actualmente no hay texto en esta página' in text:raise ValueError('Página sin contenido.')
            if len(text.strip())<100:raise ValueError('Fuente sin contenido suficiente.')
            if 'raw.githubusercontent.com' in url:
                owner,repository,ref,file_path=urlparse(url).path.strip('/').split('/',3)
                public_url=f'https://github.com/{owner}/{repository}/blob/{ref}/{file_path}'
            else:public_url=url
            with connect(database) as c:
                c.execute('INSERT INTO assistant_sources(url,title,body,fetched) VALUES(?,?,?,?) ON CONFLICT(url) DO UPDATE SET title=excluded.title,body=excluded.body,fetched=excluded.fetched',(public_url,title,text[:100000],now()))
                c.execute('DELETE FROM assistant_sources WHERE title=? AND url<>?',(title,public_url))
            success+=1
        except Exception:failed.append(title)
    print(f'Fuentes actualizadas: {success}; pendientes: {len(failed)}.')
    for title in failed:print('No disponible:',title)
    return success

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--database',default=str(Path(os.environ.get('PLS_DATA_DIR',str(Path.home()/'.local/share/pls-plataforma')))/'plataforma.sqlite3'))
    refresh(parser.parse_args().database)
