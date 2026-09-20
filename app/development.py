"""Planeación del desarrollo y transcripción efímera de respuestas."""
import json
import io
import secrets
import urllib.error
import urllib.request
from pathlib import Path
from flask import Request

PLAN_STATUSES={
    'pending':'Pendiente de respuesta',
    'answered':'Respuesta guardada',
    'needs_clarification':'Falta aclarar',
    'in_progress':'En implementación',
    'implemented':'Implementado',
    'deferred':'Aplazado',
    'closed':'Cerrado',
}
ALLOWED_AUDIO_TYPES={
    'audio/webm':'webm',
    'audio/mp4':'m4a',
    'audio/mpeg':'mp3',
    'audio/mp3':'mp3',
    'audio/wav':'wav',
    'audio/x-wav':'wav',
}

class MemoryUploadRequest(Request):
    """Mantiene los dictados acotados en memoria y no crea archivos de audio."""
    def _get_file_stream(self,total_content_length,content_type,filename=None,content_length=None):
        return io.BytesIO()

class TranscriptionError(Exception):
    def __init__(self,status,message):
        super().__init__(message);self.status=status

def sync_plan_items(connection,index_path,stamp):
    """Actualiza metadatos publicados sin tocar estados ni respuestas."""
    path=Path(index_path)
    if not path.is_file():return 0
    try:data=json.loads(path.read_text())
    except (OSError,json.JSONDecodeError) as error:raise RuntimeError('El índice privado de planeación no es válido.') from error
    rows=data.get('items') if isinstance(data,dict) else None
    if not isinstance(rows,list):raise RuntimeError('El índice privado de planeación no contiene items.')
    seen=set()
    for position,row in enumerate(rows,1):
        if not isinstance(row,dict):raise RuntimeError('Hay un registro de planeación inválido.')
        key=row.get('key','')
        if not isinstance(key,str) or not key or len(key)>30 or key in seen:raise RuntimeError('Hay un identificador de planeación inválido o duplicado.')
        seen.add(key)
        values=[]
        for field,limit in [('title',180),('question',3000),('classification',120),('origin',500)]:
            value=row.get(field,'')
            if not isinstance(value,str) or not value.strip() or len(value)>limit:raise RuntimeError(f'El campo {field} del índice de planeación no es válido.')
            values.append(value.strip())
        connection.execute('''INSERT INTO development_items(key,title,question,classification,origin,sort_order,status,created,updated)
            VALUES(?,?,?,?,?,?,\'pending\',?,?) ON CONFLICT(key) DO UPDATE SET
            title=excluded.title,question=excluded.question,classification=excluded.classification,
            origin=excluded.origin,sort_order=excluded.sort_order,updated=CASE WHEN
            development_items.title<>excluded.title OR development_items.question<>excluded.question OR
            development_items.classification<>excluded.classification OR development_items.origin<>excluded.origin OR
            development_items.sort_order<>excluded.sort_order THEN excluded.updated ELSE development_items.updated END''',
            (key,*values,position,stamp,stamp))
    return len(rows)

def multipart_body(fields,file_field,filename,mimetype,payload):
    boundary='----pls-'+secrets.token_hex(18)
    chunks=[]
    for key,value in fields:
        chunks.extend([f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()])
    safe_name='respuesta.'+ALLOWED_AUDIO_TYPES.get(mimetype,'webm')
    chunks.extend([
        f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{safe_name}"\r\nContent-Type: {mimetype}\r\n\r\n'.encode(),
        payload,b'\r\n',f'--{boundary}--\r\n'.encode(),
    ])
    return boundary,b''.join(chunks)

def transcribe_audio(payload,mimetype,config):
    """Envía audio terminado al proveedor; nunca lo escribe a disco."""
    if not config.get('TRANSCRIBE_API_KEY'):raise TranscriptionError(503,'La transcripción de voz todavía no está configurada.')
    if mimetype not in ALLOWED_AUDIO_TYPES:raise TranscriptionError(415,'Este navegador produjo un formato de audio no compatible.')
    if len(payload)<1000:raise TranscriptionError(400,'La grabación es demasiado corta. Intenta dictar de nuevo.')
    if len(payload)>config.get('TRANSCRIBE_MAX_BYTES',12*1024*1024):raise TranscriptionError(413,'La grabación excede el tamaño permitido.')
    model=config.get('TRANSCRIBE_MODEL','gpt-transcribe')
    fields=[('model',model),('response_format','json'),('prompt','Respuesta para la planeación de desarrollo de la plataforma comunitaria Por la Sombrita, LABNL, Monterrey.')]
    languages=config.get('TRANSCRIBE_LANGUAGES',('es','en'))
    if model=='gpt-transcribe':
        fields.extend(('languages[]',language) for language in languages)
        fields.extend(('keywords[]',keyword) for keyword in ['Por la Sombrita','LABNL','Monterrey','Proton Drive','Spotify'])
    elif languages:fields.append(('language',languages[0]))
    boundary,body=multipart_body(fields,'file','respuesta',mimetype,payload)
    base=config.get('TRANSCRIBE_BASE_URL','https://api.openai.com/v1').rstrip('/')
    request=urllib.request.Request(base+'/audio/transcriptions',data=body,method='POST',headers={
        'Authorization':'Bearer '+config['TRANSCRIBE_API_KEY'],
        'Content-Type':'multipart/form-data; boundary='+boundary,
        'Accept':'application/json',
    })
    try:
        with urllib.request.urlopen(request,timeout=60) as response:
            raw=response.read(1024*1024+1)
    except urllib.error.HTTPError as error:
        raise TranscriptionError(502,f'La transcripción falló (HTTP {error.code}).') from error
    except (urllib.error.URLError,TimeoutError) as error:
        raise TranscriptionError(504,'No se pudo completar la transcripción a tiempo.') from error
    if len(raw)>1024*1024:raise TranscriptionError(502,'La respuesta de transcripción es demasiado grande.')
    try:data=json.loads(raw)
    except json.JSONDecodeError as error:raise TranscriptionError(502,'La respuesta de transcripción no es válida.') from error
    text=data.get('text') if isinstance(data,dict) else None
    if not isinstance(text,str):raise TranscriptionError(502,'La transcripción no devolvió texto válido.')
    if not text.strip():raise TranscriptionError(422,'No se detectó voz en la grabación.')
    return text.strip()
