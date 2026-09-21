/* Consulta privada; la salida del modelo siempre se presenta como texto. */
const assistantForm=document.getElementById('assistant-form');
if(assistantForm)assistantForm.addEventListener('submit',async event=>{
  event.preventDefault();const button=assistantForm.querySelector('[type=submit]');const error=assistantForm.querySelector('.form-error');const progress=document.getElementById('assistant-progress');
  button.disabled=true;error.textContent='';document.getElementById('assistant-answer').hidden=true;
  try{
    const session=await getSession();const response=await fetch('/api/assistant/questions',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':session.csrf},body:JSON.stringify({question:assistantForm.elements.question.value})});
    const job=await response.json();if(!response.ok)throw new Error(job.error||'No se pudo enviar la consulta.');
    progress.textContent='Consultando las fuentes… Puedes esperar aquí; tarda unos momentos.';
    for(let attempt=0;attempt<150;attempt++){
      await new Promise(resolve=>setTimeout(resolve,2500));
      const poll=await fetch('/api/assistant/questions/'+job.id);const data=await poll.json();if(!poll.ok)throw new Error(data.error||'Tu sesión de consulta expiró.');
      if(data.state==='failed')throw new Error(data.error);
      if(data.state!=='done')continue;
      document.getElementById('assistant-text').textContent=data.result.answer;
      document.getElementById('assistant-caution').textContent=data.result.uncertain?'Las fuentes no permiten resolver toda la pregunta.':'';
      const list=document.getElementById('assistant-citations');list.replaceChildren();
      for(const source of data.result.sources){const li=document.createElement('li');const a=document.createElement('a');a.href=source.url;a.textContent=source.title;li.append(a,document.createTextNode(' · consulta '+source.fetched.slice(0,10)));list.append(li);}
      document.getElementById('assistant-answer').hidden=false;return;
    }
    throw new Error('La consulta sigue en cola. Espera unos minutos antes de volver a preguntar.');
  }catch(e){error.textContent=e.message;}finally{button.disabled=false;progress.textContent='';}
});
