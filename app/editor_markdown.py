"""Conversión segura entre el HTML almacenado y Markdown para edición humana."""
import re
from bs4 import BeautifulSoup, NavigableString, Tag
from markdown import markdown
from .core import clean_html, sections


class MarkdownError(ValueError):
    pass


def _escape(value):
    return re.sub(r'([\\`*_\[\]#])',r'\\\1',re.sub(r'\s+',' ',value))


def _inline(node):
    if isinstance(node,NavigableString):return _escape(str(node))
    if not isinstance(node,Tag):return ''
    content=''.join(_inline(child) for child in node.children)
    if node.name in {'strong','b'}:return f'**{content.strip()}**'
    if node.name in {'em','i'}:return f'*{content.strip()}*'
    if node.name=='code':return f'`{node.get_text().replace("`","\\\\`")}`'
    if node.name=='a':
        href=node.get('href','');title=node.get('title','');suffix=f' "{title}"' if title else ''
        return f'[{content.strip()}]({href}{suffix})' if href else content
    if node.name=='br':return '\n'
    return content


def _list(tag,depth=0):
    lines=[];ordered=tag.name=='ol'
    for position,item in enumerate(tag.find_all('li',recursive=False),1):
        nested=item.find_all(['ul','ol'],recursive=False)
        body=''.join(_inline(child) for child in item.contents if child not in nested).strip()
        lines.append('  '*depth+(f'{position}. ' if ordered else '- ')+body)
        for child in nested:lines.extend(_list(child,depth+1).splitlines())
    return '\n'.join(lines)


def _table(tag):
    rows=[];header_index=None
    for row in tag.find_all('tr'):
        cells=row.find_all(['th','td'],recursive=False)
        if not cells:continue
        if header_index is None and any(cell.name=='th' for cell in cells):header_index=len(rows)
        rows.append([re.sub(r'\s+',' ',''.join(_inline(child) for child in cell.children).strip()).replace('|','\\|') for cell in cells])
    if not rows:return ''
    width=max(len(row) for row in rows);rows=[row+['']*(width-len(row)) for row in rows]
    if header_index is None:header=['']*width;body=rows
    else:header=rows[header_index];body=rows[:header_index]+rows[header_index+1:]
    line=lambda row:'| '+' | '.join(row)+' |'
    return '\n'.join([line(header),line(['---']*width),*(line(row) for row in body)])


def _block(node):
    if isinstance(node,NavigableString):return str(node).strip()
    if not isinstance(node,Tag):return ''
    if node.name in {'h2','h3','h4'}:
        level=int(node.name[1]);ident=node.get('id','');anchor=f' {{#{ident}}}' if ident else ''
        return '#'*level+' '+_escape(node.get_text(' ',strip=True))+anchor
    if node.name=='p':return _inline(node).strip()
    if node.name in {'ul','ol'}:return _list(node)
    if node.name=='blockquote':
        value='\n\n'.join(filter(None,(_block(child) for child in node.children)))
        return '\n'.join('> '+line if line else '>' for line in value.splitlines())
    if node.name=='pre':return '```\n'+node.get_text().strip('\n')+'\n```'
    if node.name=='table':return _table(node)
    if node.name=='hr':return '---'
    parts=[]
    for child in node.children:
        rendered=_block(child)
        if rendered:parts.append(rendered)
    return '\n\n'.join(parts)


def html_to_markdown(value):
    """Convierte el subconjunto editorial y conserva las anclas de encabezados."""
    soup=BeautifulSoup(value,'html.parser')
    result='\n\n'.join(filter(None,(_block(child) for child in soup.contents)))
    return re.sub(r'\n{3,}','\n\n',result).strip()+'\n'


def markdown_to_html(value):
    if not isinstance(value,str):raise MarkdownError('El contenido Markdown debe ser texto.')
    if len(value)>180000:raise MarkdownError('El contenido supera el máximo de 180000 caracteres.')
    rendered=markdown(value,extensions=['extra','sane_lists','attr_list'],output_format='html5')
    soup=BeautifulSoup(rendered,'html.parser')
    if soup.find('h1'):raise MarkdownError('Usa ## para los títulos de sección; el título principal ya aparece fuera del documento.')
    for table in list(soup.find_all('table')):
        wrapper=soup.new_tag('div');wrapper['class']=['tabla-scroll'];wrapper['tabindex']='0';wrapper['role']='region';wrapper['aria-label']='Tabla: desplazar horizontalmente si es necesario';table.wrap(wrapper)
    cleaned=clean_html(str(soup))
    if not sections(cleaned):raise MarkdownError('El documento necesita al menos una sección que empiece con ##.')
    return cleaned
