"""El índice publica solo el árbol autorizado y filtra rutas o textos sensibles."""
import json
from pathlib import Path
from app.core import connect
from scripts.indexar_proton import index, PUBLIC_ROOT

def entry(path,kind='file',media='text/plain',revision='r1',size=10):
    result={'path':PUBLIC_ROOT+'/'+path,'remote_path':'/my-files/'+PUBLIC_ROOT+'/'+path,'type':kind}
    if kind=='file':result.update(media_type=media,size=size,revision_uid=revision,mtime='2026-09-13T00:00:00Z')
    return result

def test_index_filters_and_preserves_versions(tmp_path):
    mirror=tmp_path/'mirror';mirror.mkdir()
    for folder in ['Publica','Accesos','Promotores Privado']:(mirror/folder).mkdir()
    (mirror/'Publica'/'visible.txt').write_text('Un texto completamente público.')
    (mirror/'Publica'/'secreto.txt').write_text('Contraseña: valor-que-no-debe-publicarse')
    (mirror/'Accesos'/'lista.txt').write_text('incluso sin secreto visible')
    (mirror/'Promotores Privado'/'nota.txt').write_text('interno')
    manifest={'entries':[entry('Publica','folder'),entry('Publica/visible.txt'),entry('Publica/secreto.txt'),entry('Accesos','folder'),entry('Accesos/lista.txt'),entry('Promotores Privado','folder'),entry('Promotores Privado/nota.txt')]}
    native={'entries':[{'path':PUBLIC_ROOT+'/Publica/Documento nativo','remote_path':'/my-files/'+PUBLIC_ROOT+'/Publica/Documento nativo','media_type':'application/vnd.proton.doc','revision_uid':'n1','mtime':'2026-09-13T00:00:00Z'}]}
    mp=tmp_path/'manifest.json';np=tmp_path/'native.json';mp.write_text(json.dumps(manifest));np.write_text(json.dumps(native));database=tmp_path/'db.sqlite3'
    result=index(database,mirror,mp,np);assert result=={**result,'indexed':4,'folders':2,'files':1,'native':1,'excluded':5}
    with connect(database) as c:
        paths={r['path']:dict(r) for r in c.execute('SELECT * FROM drive_items WHERE active=1')}
        assert set(paths)=={'','Publica','Publica/visible.txt','Publica/Documento nativo'}
        assert paths['Publica/visible.txt']['version']==1
        assert c.execute("SELECT hidden FROM documents WHERE slug='archivo-proton'").fetchone()[0]==1
    manifest['entries'][1]['revision_uid']='r2';mp.write_text(json.dumps(manifest));index(database,mirror,mp,np)
    with connect(database) as c:assert c.execute("SELECT version FROM drive_items WHERE path='Publica/visible.txt'").fetchone()[0]==2
    manifest['entries']=[];mp.write_text(json.dumps(manifest));index(database,mirror,mp,np)
    with connect(database) as c:
        assert c.execute("SELECT active FROM drive_items WHERE path='Publica/visible.txt'").fetchone()[0]==0
