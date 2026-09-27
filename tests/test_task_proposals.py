"""Filtros de /trabajo y tareas propuestas por personas sin cuenta con moderación previa."""
import pytest
from test_community import app, client, post, create_open
from app.core import connect


def proposal(**changes):
    data={'title':'Medir sombra en la plaza','description':'Registrar sombra a las 14:00.','category':'research','display_name':'Vecina del Obispado','contact_email':'vecina@example.org'}
    data.update(changes);return data


def test_guest_proposal_waits_for_moderation_and_keeps_contact_private(app):
    guest=client(app);response=post(guest,'/api/community/task-proposals',proposal())
    assert response.status_code==202
    public=client(app).get('/trabajo').data.decode()
    assert 'Medir sombra en la plaza' not in public and 'vecina@example.org' not in public
    owner=client(app,'owner')
    assert '1 tarea propuesta sin cuenta por revisar' in owner.get('/trabajo').data.decode()
    queue=owner.get('/moderacion/aportaciones').data.decode()
    assert 'Medir sombra en la plaza' in queue and 'vecina@example.org' in queue
    ident=response.json['id']
    approved=post(owner,f'/api/community/task-proposals/{ident}/moderate',{'action':'approve'})
    assert approved.status_code==200 and approved.json['url'].startswith('/trabajo?tarea=')
    page=client(app).get('/trabajo').data.decode()
    assert 'Medir sombra en la plaza' in page and 'Vecina del Obispado' in page and 'Propuso' in page
    assert 'vecina@example.org' not in page
    with connect(app.config['DATABASE']) as db:
        task=db.execute('SELECT state,priority,category FROM community_tasks').fetchone()
        assert tuple(task)==('open','normal','research')
        assert db.execute("SELECT COUNT(*) FROM community_task_events WHERE kind='created' AND detail LIKE '%Vecina del Obispado%'").fetchone()[0]==1
    assert post(owner,f'/api/community/task-proposals/{ident}/moderate',{'action':'approve'}).status_code==409


def test_rejection_requires_reason_and_publishes_nothing(app):
    ident=post(client(app),'/api/community/task-proposals',proposal()).json['id'];owner=client(app,'owner')
    assert post(owner,f'/api/community/task-proposals/{ident}/moderate',{'action':'reject'}).status_code==400
    assert post(owner,f'/api/community/task-proposals/{ident}/moderate',{'action':'reject','reason':'Duplicada'}).status_code==200
    with connect(app.config['DATABASE']) as db:
        assert db.execute('SELECT COUNT(*) FROM community_tasks').fetchone()[0]==0
        assert db.execute('SELECT status,moderation_reason FROM community_task_proposals').fetchone()[:]==('rejected','Duplicada')


def test_proposal_permissions_and_validation(app):
    ident=post(client(app),'/api/community/task-proposals',proposal()).json['id'];url=f'/api/community/task-proposals/{ident}/moderate'
    assert post(client(app),url,{'action':'approve'}).status_code==401
    assert post(client(app,'ana'),url,{'action':'approve'}).status_code==403
    assert post(client(app,'ana'),'/api/community/task-proposals',proposal()).status_code==409
    assert client(app).post('/api/community/task-proposals',json=proposal(),headers={'Origin':'http://localhost'}).status_code==403
    for bad in [{'title':''},{'display_name':''},{'category':'inventada'},{'contact_email':'no-es-correo'}]:
        assert post(client(app),'/api/community/task-proposals',proposal(**bad)).status_code==400


def test_filters_by_category_priority_and_take_state(app):
    c=client(app,'ana')
    create_open(c,title='Cartel urgente',category='communication',priority='urgent')
    create_open(c,title='Minuta normal',category='governance',priority='normal')
    taken=create_open(c,title='Mapa tomado',category='research',priority='high').json['id']
    assert post(c,f'/api/community/tasks/{taken}/take',{'due_date':'2099-01-01'}).status_code==200
    def titles(query):
        page=client(app).get('/trabajo'+query).data.decode()
        return {t for t in ['Cartel urgente','Minuta normal','Mapa tomado'] if f'<h3>{t}</h3>' in page}
    assert titles('')=={'Cartel urgente','Minuta normal','Mapa tomado'}
    assert titles('?categoria=governance')=={'Minuta normal'}
    assert titles('?prioridad=urgent')=={'Cartel urgente'}
    assert titles('?toma=tomadas')=={'Mapa tomado'}
    assert titles('?toma=por-tomar')=={'Cartel urgente','Minuta normal'}
    assert titles('?toma=por-tomar&prioridad=normal')=={'Minuta normal'}
    assert titles('?categoria=inventada&toma=x')==titles('')
    page=client(app).get('/trabajo?toma=por-tomar&prioridad=normal').data.decode()
    assert '1 de 3 tareas con estos filtros.' in page and 'Quitar filtros' in page
    assert 'href="/trabajo?toma=por-tomar&amp;prioridad=urgent"' in page
