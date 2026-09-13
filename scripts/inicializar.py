#!/usr/bin/env python3
"""Carga documentos iniciales y crea cuentas solo si aún no existen."""
import os,sys,secrets
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core import connect,init_db,now,clean_html
from bs4 import BeautifulSoup
from werkzeug.security import generate_password_hash

BASE=Path(__file__).resolve().parents[1]
DATA=Path(os.environ.get('PLS_DATA_DIR',str(Path.home()/'.local/share/pls-plataforma')))
USERS=[('jax','Jax'),('cons','Cons'),('soos','Soos'),('luismario','Luis Mario'),('juan','Juan'),('rufina','Rufina'),('leny','Leny'),('jaquie','Jaquie'),('mauricio','Mauricio')]

def initialize():
    DATA.mkdir(parents=True,exist_ok=True,mode=0o700);DATA.chmod(0o700);path=DATA/'plataforma.sqlite3';init_db(path)
    created=[]
    with connect(path) as c:
        for slug in ['plan','manual','bases','decisiones','investigacion','comunicacion','seguimiento','fuentes']:
            if c.execute('SELECT 1 FROM documents WHERE slug=?',(slug,)).fetchone():continue
            soup=BeautifulSoup((BASE/'contenido/inicial'/(slug+'.html')).read_text(),'html.parser');article=soup.select_one('.prosa')
            for el in article.select('.nota-final,.volver'):el.decompose()
            title=soup.h1.get_text(' ',strip=True);intro=soup.select_one('.entradilla').get_text(' ',strip=True)
            content=clean_html(article.decode_contents());stamp=now()
            c.execute('INSERT INTO documents(slug,title,intro,version,status,html,updated) VALUES(?,?,?,1,?,?,?)',(slug,title,intro,'proposal',content,stamp))
            c.execute('INSERT INTO revisions(document,version,html,status,reason,created) VALUES(?,1,?,?,?,?)',(slug,content,'proposal','Importación del sitio público. Conserva estado de propuesta; no implica ratificación.',stamp))
        for username,name in USERS:
            if c.execute('SELECT 1 FROM users WHERE username=?',(username,)).fetchone():continue
            password=secrets.token_urlsafe(12);role='owner' if username=='luismario' else 'member'
            c.execute('INSERT INTO users(username,name,password_hash,role,created) VALUES(?,?,?,?,?)',(username,name,generate_password_hash(password),role,now()));created.append((name,username,password))
    if created:
        file=DATA/('accesos-provisionales-'+secrets.token_hex(4)+'.txt')
        with file.open('x') as f:
            f.write('ACCESOS PRIVADOS · Por la Sombrita\nhttps://plsmty.bespokem.mx/cuenta\nEntregar individualmente. Cada persona debe cambiar su contraseña al entrar.\nNo publicar, subir a GitHub ni compartir el listado completo con participantes.\n\n')
            for name,username,password in created:f.write(f'{name}\nUsuario: {username}\nContraseña provisional: {password}\n\n')
        file.chmod(0o600);print('Cuentas creadas:',len(created));print('Archivo privado de entrega:',file)
    else:print('Las cuentas existentes se conservaron; no se restablecieron contraseñas.')

if __name__=='__main__':initialize()
