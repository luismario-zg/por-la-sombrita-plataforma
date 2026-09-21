"""Edición amigable en Markdown sin perder permisos, anclas ni seguridad."""
from bs4 import BeautifulSoup
from app.core import connect
from app.editor_markdown import html_to_markdown,markdown_to_html,MarkdownError
from test_platform import app,client,post


def test_round_trip_preserves_structure_links_and_table():
    original='''<h2 id="inicio">Inicio y propósito</h2><p>Texto <strong>importante</strong> con <a href="https://example.org">fuente</a>.</p>
    <h3 id="pasos">Pasos</h3><ul><li>Primero</li><li>Segundo</li></ul>
    <div class="tabla-scroll"><table><thead><tr><th>Campo</th><th>Detalle</th></tr></thead><tbody><tr><td><strong>Estado</strong></td><td><a href="https://example.org/a">Abierto</a></td></tr></tbody></table></div>'''
    source=html_to_markdown(original)
    assert '## Inicio y propósito {#inicio}' in source and '### Pasos {#pasos}' in source
    result=markdown_to_html(source);soup=BeautifulSoup(result,'html.parser')
    assert soup.find('h2')['id']=='inicio' and soup.find('h3')['id']=='pasos'
    assert [a['href'] for a in soup.find_all('a')]==['https://example.org','https://example.org/a']
    assert len(soup.find_all('li'))==2 and soup.select_one('.tabla-scroll table')
    assert soup.find('strong').get_text()=='importante'


def test_markdown_rejects_page_title_and_sanitizes_html():
    try:markdown_to_html('# Título que no corresponde\n\nTexto')
    except MarkdownError as error:assert 'Usa ##' in str(error)
    else:raise AssertionError('Se esperaba rechazo de H1.')
    result=markdown_to_html('## Sección {#segura}\n\n<script>alert(1)</script> <img src=x> [enlace](javascript:alert(1))')
    assert '<script' not in result and '<img' not in result and 'javascript:' not in result and 'id="segura"' in result


def test_editor_shows_markdown_and_preview_requires_editor(app):
    owner=client(app,'owner');page=owner.get('/editar/plan')
    assert page.status_code==200 and b'name="markdown"' in page.data
    assert b'## Una secci' in page.data and b'{#sombra}' in page.data
    assert b'Gu\xc3\xada r\xc3\xa1pida de formato' in page.data and b'data-md-preview' in page.data
    member=client(app,'member')
    assert post(member,'/api/documents/plan/preview-markdown',{'markdown':'## Prueba'}).status_code==403


def test_preview_and_save_markdown_preserve_version_history(app):
    owner=client(app,'owner')
    source='''## Una sección revisada {#sombra}\n\nContenido **claro** con una [fuente](https://example.org).\n\n- Primer punto\n- Segundo punto'''
    preview=post(owner,'/api/documents/plan/preview-markdown',{'markdown':source})
    assert preview.status_code==200 and '<strong>claro</strong>' in preview.json['html']
    with connect(app.config['DATABASE']) as database:
        assert database.execute("SELECT version FROM documents WHERE slug='plan'").fetchone()[0]==1
        assert database.execute("SELECT COUNT(*) FROM revisions WHERE document='plan'").fetchone()[0]==1
    saved=post(owner,'/api/documents/plan',{'version':1,'markdown':source,'reason':'Propuesta Markdown de prueba','status':'proposal','reference':'','source_thread':None})
    assert saved.status_code==200 and saved.json['version']==2
    with connect(app.config['DATABASE']) as database:
        document=database.execute("SELECT * FROM documents WHERE slug='plan'").fetchone()
        assert document['version']==2 and 'id="sombra"' in document['html'] and '<script' not in document['html']
        assert database.execute("SELECT COUNT(*) FROM revisions WHERE document='plan'").fetchone()[0]==2
