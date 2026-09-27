"""Etiquetas persistentes con permisos y auditoría, independientes del estado."""
import pytest
from test_community import app, client, post, create_open
from app.core import connect
from app.community import init_community_schema


def test_category_creation_display_and_idempotent_changes(app):
    c=client(app,'ana');result=create_open(c,category='research');ident=result.json['id']
    assert result.status_code==201
    assert 'Investigación'.encode() in client(app).get('/trabajo').data
    with connect(app.config['DATABASE']) as db:
        db.execute("UPDATE community_tasks SET state='closed' WHERE id=?",(ident,))
        init_community_schema(db)
        assert db.execute('SELECT category FROM community_tasks WHERE id=?',(ident,)).fetchone()[0]=='research'
    for _ in range(2):assert post(c,f'/api/community/tasks/{ident}/category',{'category':'prototypes'}).status_code==200
    with connect(app.config['DATABASE']) as db:
        assert tuple(db.execute('SELECT category,state FROM community_tasks WHERE id=?',(ident,)).fetchone())==('prototypes','closed')
        assert db.execute("SELECT COUNT(*) FROM community_task_events WHERE kind='categorized'").fetchone()[0]==1


@pytest.mark.parametrize('category',['inventada','',[],None])
def test_invalid_category_rejected(app,category):
    assert create_open(client(app,'ana'),category=category).status_code==400


def test_category_requires_participant_and_csrf(app):
    c=client(app,'ana');ident=create_open(c).json['id'];url=f'/api/community/tasks/{ident}/category'
    assert post(client(app),url,{'category':'research'}).status_code==401
    assert post(client(app,'reader'),url,{'category':'research'}).status_code==403
    assert c.post(url,json={'category':'research'},headers={'Origin':'http://localhost'}).status_code==403
    assert post(c,'/api/community/tasks/999/category',{'category':'research'}).status_code==404


def test_category_migration_preserves_existing_task_and_is_repeatable(app):
    c=client(app,'ana');ident=create_open(c).json['id']
    with connect(app.config['DATABASE']) as db:
        original=dict(db.execute('SELECT * FROM community_tasks WHERE id=?',(ident,)).fetchone())
        db.execute('ALTER TABLE community_tasks DROP COLUMN category');db.commit()
        init_community_schema(db);init_community_schema(db)
        restored=dict(db.execute('SELECT * FROM community_tasks WHERE id=?',(ident,)).fetchone())
        assert restored==original


def test_task_tags_are_one_click_menus_only_for_participants(app):
    c=client(app,'ana');ident=create_open(c,category='research').json['id']
    page=c.get('/trabajo').data.decode()
    assert f'data-api="/api/community/tasks/{ident}/priority"' in page and f'data-api="/api/community/tasks/{ident}/category"' in page
    assert 'name="priority" value="urgent"' in page and 'aria-current="true" disabled' in page
    assert 'Cambiar prioridad</summary>' not in page and 'Guardar prioridad' not in page
    anonymous=client(app).get('/trabajo').data.decode()
    assert 'Investigación' in anonymous and '/api/community/tasks/' not in anonymous and 'chip-options-title">Cambiar' not in anonymous
    with connect(app.config['DATABASE']) as db:
        db.execute("UPDATE community_tasks SET state='closed' WHERE id=?",(ident,));db.commit()
    closed=c.get('/trabajo').data.decode()
    assert f'/api/community/tasks/{ident}/priority' not in closed and f'/api/community/tasks/{ident}/category' in closed


def test_listings_show_real_totals_across_pages(app):
    c=client(app,'ana')
    for _ in range(3):create_open(c)
    assert '3 tareas registradas' in client(app).get('/trabajo?pagina=2').data.decode()
    with connect(app.config['DATABASE']) as db:
        active,official=db.execute("SELECT COUNT(*),COALESCE(SUM(membership='official'),0) FROM users WHERE active=1").fetchone()
    assert f'{active} cuentas activas · {official} con membresía oficial registrada.' in client(app).get('/miembros?pagina=9').data.decode()
