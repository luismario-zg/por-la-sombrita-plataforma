"""Pendientes administrativos con anclas verificadas y contexto preservado."""
import pytest
from bs4 import BeautifulSoup
from test_platform import app, client, post
from app.core import connect


def payload(**changes):
    return dict(document='plan', section='sombra', version=1,
                title='Mejorar lectura', body='Dar más espacio a los botones.', **changes)


@pytest.mark.parametrize('name,code',[(None,401),('member',403),('reviewer',403),('reader',403),('temporary',403)])
def test_section_comment_requires_admin(app,name,code):
    c=client(app,name)
    assert post(c,'/api/improvements/section',payload()).status_code==code
    assert b'data-develop-section' not in c.get('/plan.html').data


def test_admin_pending_preserves_source_without_creating_discussion(app):
    c=client(app,'owner')
    result=post(c,'/api/improvements/section',payload())
    assert result.status_code==201
    with connect(app.config['DATABASE']) as db:
        row=db.execute('SELECT * FROM improvement_sections').fetchone()
        assert (row['document'],row['version'],row['section'],row['section_title'])==('plan',1,'sombra','Una sección')
        assert row['section_text']=='La revisión será semanal.'
        item=db.execute('SELECT * FROM improvements').fetchone()
        assert item['status']=='proposed' and item['sync_state']=='idle' and item['issue_number'] is None
        assert db.execute('SELECT COUNT(*) FROM threads').fetchone()[0]==0
        db.execute("UPDATE documents SET version=2,html='<h2 id=\"nuevo\">Nuevo</h2><p>Otro texto</p>' WHERE slug='plan'")
    page=c.get(result.json['url'])
    assert 'Pendiente de desarrollo'.encode() in page.data
    assert 'La revisión será semanal.'.encode() in page.data
    assert b'/plan.html#sombra' in page.data
    assert b'Mejorar lectura' in c.get('/mejoras').data


@pytest.mark.parametrize('field,value,code',[('version',2,409),('version',True,400),('section','inexistente',400),('document','archivo-proton',404),('body','',400)])
def test_invalid_context_is_atomic(app,field,value,code):
    data=payload();data[field]=value
    assert post(client(app,'owner'),'/api/improvements/section',data).status_code==code
    with connect(app.config['DATABASE']) as db:
        assert db.execute('SELECT COUNT(*) FROM improvements').fetchone()[0]==0


def test_admin_form_layout_voice_and_csrf(app):
    with connect(app.config['DATABASE']) as db:
        db.execute("UPDATE users SET role='admin',membership='official',developer_access=0 WHERE username='owner'")
    c=client(app,'owner');response=c.get('/plan.html')
    soup=BeautifulSoup(response.data,'html.parser')
    heading=soup.select_one('.section-heading')
    assert heading.select_one('h2') and heading.select_one('[data-discuss-section]') and heading.select_one('[data-develop-section]')
    form=soup.select_one('#section-development form')
    assert form['data-api']=='/api/improvements/section'
    assert form['data-transcribe-url']=='/api/voice/transcribe'
    assert form.select_one('.voice-button') and soup.select_one('script[src$="development-plan.js"]')
    assert 'microphone=(self)' in response.headers['Permissions-Policy']
    assert c.post('/api/improvements/section',json=payload(),headers={'Origin':'http://localhost'}).status_code==403
    assert post(c,'/api/improvements/section',payload()).status_code==201
