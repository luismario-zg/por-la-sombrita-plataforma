"""Dictado de comentarios con permisos de participación, sin publicar borradores."""
import io
import pytest
from bs4 import BeautifulSoup
from test_platform import app,client
from app.core import connect


def transcribe(c,headers=None,payload=b'a'*1500):
    session=c.get('/api/session').json
    return c.post('/api/threads/transcribe',data={'audio':(io.BytesIO(payload),'comentario.webm','audio/webm')},
                  headers=headers if headers is not None else {'Origin':'http://localhost','X-CSRF-Token':session['csrf']})


@pytest.mark.parametrize('name',['member','reviewer','owner'])
def test_participants_can_dictate_without_official_membership(app,monkeypatch,name):
    calls=[]
    def provider(payload,mimetype,config):
        calls.append((len(payload),mimetype));return 'Comentario transcrito para revisar.'
    monkeypatch.setattr('app.transcribe_audio',provider)
    c=client(app,name)
    page=c.get('/plan.html');soup=BeautifulSoup(page.data,'html.parser')
    form=soup.select_one('#new-thread form')
    assert form['data-transcribe-url']=='/api/threads/transcribe' and 'voice-enabled' in form['class']
    assert form.select_one('.voice-button') and form.select_one('[name=quote]')
    assert soup.select_one('script[src$="development-plan.js"]')
    assert 'microphone=(self)' in page.headers['Permissions-Policy']
    result=transcribe(c)
    assert result.status_code==200 and result.json=={'text':'Comentario transcrito para revisar.'}
    assert calls==[(1500,'audio/webm')]
    with connect(app.config['DATABASE']) as db:
        assert db.execute('SELECT COUNT(*) FROM threads').fetchone()[0]==0
        assert db.execute('SELECT COUNT(*) FROM improvements').fetchone()[0]==0
        assert db.execute('SELECT membership FROM users WHERE username=?',(name,)).fetchone()[0]=='pending'


@pytest.mark.parametrize('name,status',[(None,401),('reader',403),('temporary',403)])
def test_comment_voice_rejects_accounts_without_participation(app,monkeypatch,name,status):
    def forbidden(*args):raise AssertionError('No debe llamar al proveedor')
    monkeypatch.setattr('app.transcribe_audio',forbidden)
    c=client(app,name)
    assert transcribe(c).status_code==status
    assert not BeautifulSoup(c.get('/plan.html').data,'html.parser').select_one('#new-thread .voice-button')


def test_comment_voice_csrf_origin_limits_and_other_voice_permissions(app,monkeypatch):
    c=client(app,'member');csrf=c.get('/api/session').json['csrf']
    assert transcribe(c,headers={'Origin':'http://localhost'}).status_code==403
    assert transcribe(c,headers={'Origin':'https://otro.example','X-CSRF-Token':csrf}).status_code==403
    assert transcribe(c,payload=b'a'*100).status_code==400
    app.config['TRANSCRIBE_MAX_BYTES']=2000
    assert transcribe(c,payload=b'a'*3000).status_code==413
    response=c.post('/api/voice/transcribe',data={'audio':(io.BytesIO(b'a'*1500),'comentario.webm','audio/webm')},headers={'Origin':'http://localhost','X-CSRF-Token':csrf})
    assert response.status_code==403
    monkeypatch.setattr('app.transcribe_audio',lambda *args:'Borrador.')
    with connect(app.config['DATABASE']) as db:
        user_id=db.execute("SELECT id FROM users WHERE username='member'").fetchone()[0]
        # Las comprobaciones inválidas también consumen cuota: completar el límite existente.
        db.execute("DELETE FROM limits WHERE key=?",('development-transcribe:'+str(user_id),))
    for _ in range(30):assert transcribe(c).status_code==200
    assert transcribe(c).status_code==429
