/* Dictado para respuestas: grabar → transcribir → borrador editable. Nunca guarda automáticamente. */
let activeVoice=null;
let transcribingForm=null;
const voiceMime=()=>{
  if(!window.MediaRecorder)return '';
  for(const type of ['audio/webm;codecs=opus','audio/webm','audio/mp4'])if(MediaRecorder.isTypeSupported(type))return type;
  return '';
};
const voiceMessage=(form,message)=>{form.querySelector('.voice-status').textContent=message;};
function stopTracks(stream){stream?.getTracks().forEach(track=>track.stop());}
function resetVoice(state){
  clearInterval(state.interval);stopTracks(state.stream);
  state.form.querySelector('.voice-button').classList.remove('recording');
  state.form.querySelector('.voice-button').textContent='🎙️ Dictar';
  state.form.querySelector('.voice-cancel').hidden=true;
  state.form.querySelector('.voice-timer').hidden=true;
  state.form.querySelector('.voice-timer').textContent='0:00';
  if(activeVoice===state)activeVoice=null;
}
async function transcribe(state,blob){
  const form=state.form;const input=form.querySelector('textarea');const original=input.value;
  transcribingForm=form;form.querySelector('[type=submit]').disabled=true;voiceMessage(form,'Transcribiendo…');
  try{
    const session=await fetch('/api/session',{credentials:'same-origin',cache:'no-store'}).then(async r=>{const body=await r.json();if(!r.ok)throw new Error(body.error||'No se pudo preparar la sesión.');return body;});
    const data=new FormData();const extension=blob.type.includes('mp4')?'m4a':'webm';data.append('audio',blob,'respuesta.'+extension);
    const response=await fetch('/api/development/transcribe',{method:'POST',credentials:'same-origin',headers:{'X-CSRF-Token':session.csrf},body:data});
    const result=await response.json();if(!response.ok)throw new Error(result.error||'No se pudo transcribir la grabación.');
    const draftUnchanged=input.value===original;input.value=input.value?input.value.trimEnd()+' '+result.text:result.text;
    input.dispatchEvent(new Event('input',{bubbles:true}));input.focus();input.setSelectionRange(input.value.length,input.value.length);
    voiceMessage(form,draftUnchanged?'Transcripción lista para revisar.':'Transcripción añadida al borrador que cambió mientras se procesaba; revísala antes de guardar.');
  }catch(error){voiceMessage(form,'Transcripción falló: '+error.message);}
  finally{transcribingForm=null;form.querySelector('[type=submit]').disabled=false;}
}
async function startVoice(form){
  if(activeVoice||transcribingForm){voiceMessage(form,'Termina la grabación o transcripción actual.');return;}
  if(!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder){voiceMessage(form,'Este navegador no permite grabar audio. Verifica que uses HTTPS.');return;}
  const mimetype=voiceMime();if(!mimetype){voiceMessage(form,'Este navegador no ofrece un formato de audio compatible.');return;}
  let stream;
  try{
    if(navigator.permissions?.query){try{const permission=await navigator.permissions.query({name:'microphone'});if(permission.state==='denied'){voiceMessage(form,'Permiso de micrófono denegado. Habilítalo en la configuración del sitio.');return;}}catch{}}
    stream=await navigator.mediaDevices.getUserMedia({audio:true});
    const recorder=new MediaRecorder(stream,{mimeType:mimetype});
    const state={form,stream,recorder,chunks:[],cancelled:false,started:Date.now(),interval:null};activeVoice=state;
    recorder.ondataavailable=event=>{if(event.data.size)state.chunks.push(event.data);};
    recorder.onstop=async()=>{
      const blob=new Blob(state.chunks,{type:recorder.mimeType||mimetype});const cancelled=state.cancelled;resetVoice(state);
      if(cancelled){voiceMessage(form,'Grabación descartada.');return;}
      if(blob.size<1000){voiceMessage(form,'Grabación demasiado corta. Intenta dictar de nuevo.');return;}
      await transcribe(state,blob);
    };
    recorder.start(500);form.querySelector('.voice-button').classList.add('recording');form.querySelector('.voice-button').textContent='■ Detener';
    form.querySelector('.voice-cancel').hidden=false;const timer=form.querySelector('.voice-timer');timer.hidden=false;voiceMessage(form,'Grabando…');
    state.interval=setInterval(()=>{const seconds=Math.floor((Date.now()-state.started)/1000);timer.textContent=Math.floor(seconds/60)+':'+String(seconds%60).padStart(2,'0');if(seconds>=180&&recorder.state==='recording')recorder.stop();},500);
  }catch(error){stopTracks(stream);activeVoice=null;voiceMessage(form,error.name==='NotAllowedError'?'Permiso de micrófono denegado. Habilítalo desde el candado del navegador.':error.name==='NotFoundError'?'No se encontró un micrófono.':'No se pudo iniciar el micrófono: '+error.message);}
}
document.querySelectorAll('.plan-response-form').forEach(form=>{
  form.querySelector('.voice-button')?.addEventListener('click',()=>{
    if(activeVoice?.form===form&&activeVoice.recorder.state==='recording')activeVoice.recorder.stop();else void startVoice(form);
  });
  form.querySelector('.voice-cancel')?.addEventListener('click',()=>{
    if(activeVoice?.form===form&&activeVoice.recorder.state==='recording'){activeVoice.cancelled=true;activeVoice.recorder.stop();}
  });
});
document.addEventListener('submit',event=>{
  if(event.target.matches('.plan-response-form')&&(activeVoice||transcribingForm)){event.preventDefault();event.stopImmediatePropagation();voiceMessage(event.target,'Termina la grabación o transcripción antes de guardar.');}
},true);

const planTabs=[...document.querySelectorAll('.plan-category-tabs [role=tab]')];
function selectPlanTab(tab,focus=false){
  for(const candidate of planTabs){
    const active=candidate===tab;candidate.setAttribute('aria-selected',String(active));candidate.tabIndex=active?0:-1;
    const panel=document.getElementById(candidate.getAttribute('aria-controls'));if(panel)panel.hidden=!active;
  }
  if(focus)tab.focus();history.replaceState(null,'','#'+tab.getAttribute('aria-controls'));
}
for(const [index,tab] of planTabs.entries()){
  tab.addEventListener('click',()=>selectPlanTab(tab));
  tab.addEventListener('keydown',event=>{
    if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();
    const next=event.key==='Home'?0:event.key==='End'?planTabs.length-1:(index+(event.key==='ArrowRight'?1:-1)+planTabs.length)%planTabs.length;
    selectPlanTab(planTabs[next],true);
  });
}
const requested=location.hash.startsWith('#panel-')?document.querySelector(`.plan-category-tabs [aria-controls="${CSS.escape(location.hash.slice(1))}"]`):null;
if(requested)selectPlanTab(requested);
