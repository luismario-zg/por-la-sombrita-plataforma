"""Regreso seguro a la página de origen después del acceso."""
from urllib.parse import urlencode
import pytest
from bs4 import BeautifulSoup
from test_platform import app, client, post, PASS
from app import safe_return_path


@pytest.mark.parametrize('target',['https://otro.example','//otro.example','/\\otro.example','/%2f%2fotro.example','/%255c%255cotro.example','/\n/otro.example','/cuenta?next=/plan.html','/api/session',None,{}])
def test_return_rejects_external_or_reserved_paths(target):
    assert safe_return_path(target)=='/'


def test_login_returns_to_document_query_and_fragment(app):
    c=client(app);target='/plan.html?origen=prueba#sombra'
    page=c.get('/cuenta?'+urlencode({'next':target}))
    form=BeautifulSoup(page.data,'html.parser').select_one('form[data-api="/api/login"]')
    assert form['data-success']=='return' and form.select_one('[name=next]')['value']==target
    result=post(c,'/api/login',{'username':'member','password':PASS,'next':target})
    assert result.status_code==200 and result.json['redirect']==target and not result.json['must_change']


def test_temporary_password_keeps_destination_until_changed(app):
    c=client(app);target='/trabajo#tarea-4'
    result=post(c,'/api/login',{'username':'temporary','password':PASS,'next':target})
    assert result.json['redirect']=='/cuenta?'+urlencode({'next':target})
    page=c.get(result.json['redirect'])
    form=BeautifulSoup(page.data,'html.parser').select_one('form[data-api="/api/password"]')
    assert form.select_one('[name=next]')['value']==target
    result=post(c,'/api/password',{'current':PASS,'password':'Otra-clave-segura-prueba-456','next':target})
    assert result.status_code==200 and result.json['redirect']==target
    assert not c.get('/api/session').json['user']['must_change']


def test_login_rejects_external_destination_and_link_keeps_query(app):
    c=client(app)
    page=BeautifulSoup(c.get('/discusiones?estado=all').data,'html.parser')
    assert 'next=%2Fdiscusiones%3Festado%3Dall' in page.select_one('.nav-participa')['href'] or 'next=/discusiones?estado%3Dall' in page.select_one('.nav-participa')['href']
    result=post(c,'/api/login',{'username':'member','password':PASS,'next':'//otro.example'})
    assert result.json['redirect']=='/'
