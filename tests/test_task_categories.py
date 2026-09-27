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
