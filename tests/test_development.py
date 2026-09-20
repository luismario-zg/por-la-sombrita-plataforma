"""Continuidad del plan de desarrollo entre respuestas, ejecuciones y reinicios."""
import json
from app.core import connect,init_db
from app.development import TranscriptionError,sync_plan_items,transcribe_audio

def test_index_refresh_preserves_status_and_new_questions(tmp_path):
    database=tmp_path/'plan.sqlite3';index=tmp_path/'items.json';init_db(database)
    item={'key':'D01','title':'Título inicial','question':'¿Qué se decide?','classification':'Directrices','origin':'Audio'}
    index.write_text(json.dumps({'items':[item]}))
    with connect(database) as connection:
        assert sync_plan_items(connection,index,'2026-09-20T00:00:00+00:00')==1
        connection.execute("UPDATE development_items SET status='needs_clarification' WHERE key='D01'")
        connection.execute("INSERT INTO development_items VALUES('P01','Nueva duda','¿Qué falta?','Seguimiento','Ejecución',2,'pending','a','a')")
    item['title']='Título corregido';index.write_text(json.dumps({'items':[item]}))
    with connect(database) as connection:
        sync_plan_items(connection,index,'2026-09-20T01:00:00+00:00')
        rows={row['key']:dict(row) for row in connection.execute('SELECT * FROM development_items')}
        assert rows['D01']['title']=='Título corregido' and rows['D01']['status']=='needs_clarification'
        assert rows['P01']['question']=='¿Qué falta?' and rows['P01']['status']=='pending'

def test_transcription_rejects_invalid_or_tiny_audio_before_provider():
    config={'TRANSCRIBE_API_KEY':'synthetic','TRANSCRIBE_MAX_BYTES':12*1024*1024}
    for payload,mimetype,status in [(b'a'*2000,'audio/ogg',415),(b'a'*100,'audio/webm',400)]:
        try:transcribe_audio(payload,mimetype,config)
        except TranscriptionError as error:assert error.status==status
        else:raise AssertionError('Se esperaba rechazo antes de llamar al proveedor.')
