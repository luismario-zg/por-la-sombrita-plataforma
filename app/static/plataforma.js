/* Interacciones de la plataforma. Toda autorización se verifica también en el servidor. */
let sessionPromise=null;
let selectionData=null;
const getSession=()=>sessionPromise??=(fetch('/api/session',{credentials:'same-origin',cache:'no-store'}).then(r=>{if(!r.ok)throw new Error('No se pudo preparar la sesión. Recarga la página.');return r.json();}).catch(e=>{sessionPromise=null;throw e;}));
const notify=message=>{const el=document.getElementById('notificacion');el.textContent=message;};
function value(form){
 const data={};
 for(const el of form.elements){
  if(!el.name||el.disabled||['submit','button'].includes(el.type))continue;
  let v=el.type==='checkbox'?el.checked:el.hasAttribute('data-number')?(el.value?Number(el.value):null):el.value;
  if(el.name.startsWith('review.')){data.review??={};data.review[el.name.slice(7)]=v;}else data[el.name]=v;
 }
 return data;
}
document.querySelectorAll('form[data-api]').forEach(form=>{
 form.addEventListener('input',()=>form.dataset.dirty='true');
 form.addEventListener('submit',async event=>{
  event.preventDefault();const error=form.querySelector('.form-error');error.textContent='';
  const button=event.submitter;const data=value(form);if(button?.name)data[button.name]=button.value;
  const buttons=[...form.querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);
  try{
   const sess=await getSession();
   const response=await fetch(form.dataset.api,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':sess.csrf},body:JSON.stringify(data)});
   const result=await response.json();if(!response.ok)throw new Error(result.error||'No se pudo completar la acción.');
   form.dataset.dirty='false';sessionPromise=null;
   if(form.dataset.success==='thread'){location.assign('/discusiones/'+result.id);return;}
   if(form.dataset.success==='guest-submission'){form.reset();if(form.closest('dialog'))form.closest('dialog').close();notify(result.message||'Recibimos tu aportación para moderación.');return;}
   if(form.dataset.success==='moderation'){if(result.url)notify('Aportación publicada.');location.reload();return;}
   if(form.dataset.success==='secret'){const out=form.querySelector('[data-secret]');out.hidden=false;out.textContent='Contraseña provisional (entrega privada): '+result.password;notify('Contraseña restablecida. Entrega este acceso de forma individual.');return;}
   if(form.dataset.success==='revision'){const out=form.querySelector('[data-result]');out.textContent='Guardada la versión '+result.version+'. ID de revisión: '+result.revision_id+'. Si deriva de un hilo, revisa su ficha actualizada antes de cerrar.';form.querySelector('[name=version]').value=result.version;notify('Nueva versión guardada.');return;}
   location.reload();
  }catch(e){error.textContent=e.message;error.tabIndex=-1;error.focus();}
  finally{buttons.forEach(b=>b.disabled=false);}
 });
});
document.querySelectorAll('[data-print]').forEach(b=>b.addEventListener('click',()=>window.print()));
const dialog=document.getElementById('new-thread');
const selectionButton=document.getElementById('discuss-selection');
function openDiscussion(section,selection){
 if(!dialog)return;
 const form=dialog.querySelector('form');
 if(form){
  form.elements.section.value=section.dataset.section;form.elements.quote.value=selection?.quote??'';form.elements.prefix.value=selection?.prefix??'';form.elements.suffix.value=selection?.suffix??'';
  dialog.querySelector('#thread-context').textContent='Sección: '+section.dataset.title;
  const quote=dialog.querySelector('#selected-quote');quote.hidden=!selection;quote.textContent=selection?.quote??'';
 }
 dialog.showModal();selectionButton.hidden=true;
}
document.querySelectorAll('[data-discuss-section]').forEach(button=>button.addEventListener('click',()=>openDiscussion(button.closest('.doc-section'),null)));
document.querySelectorAll('[data-close-dialog]').forEach(button=>button.addEventListener('click',()=>dialog.close()));
if(selectionButton){
 document.addEventListener('selectionchange',()=>{
  const selection=window.getSelection();
  if(!selection||selection.isCollapsed||!selection.rangeCount){selectionButton.hidden=true;return;}
  const range=selection.getRangeAt(0);const start=(range.startContainer.nodeType===1?range.startContainer:range.startContainer.parentElement)?.closest('.section-body');
  const end=(range.endContainer.nodeType===1?range.endContainer:range.endContainer.parentElement)?.closest('.section-body');
  if(!start||start!==end){selectionButton.hidden=true;return;}
  const quote=range.toString();if(!quote.trim()||quote.length>6000){selectionButton.hidden=true;return;}
  const before=range.cloneRange();before.selectNodeContents(start);before.setEnd(range.startContainer,range.startOffset);
  const after=range.cloneRange();after.selectNodeContents(start);after.setStart(range.endContainer,range.endOffset);
  selectionData={section:start.closest('.doc-section'),quote,prefix:before.toString().slice(-150),suffix:after.toString().slice(0,150)};
  selectionButton.hidden=false;
 });
 selectionButton.addEventListener('pointerdown',e=>e.preventDefault());
 selectionButton.addEventListener('click',()=>{if(selectionData)openDiscussion(selectionData.section,selectionData);});
}
if(document.querySelector('[data-job-pending]'))setTimeout(()=>{if(!document.querySelector('form[data-dirty=true]'))location.reload();else notify('Hay una generación en curso. Guarda tu borrador antes de actualizar la página.');},15000);
/* Las anclas conservan la cita y contexto; no dependen solo del desplazamiento. */
const annotationNode=document.getElementById('document-annotations');
if(annotationNode&&window.CSS?.highlights&&window.Highlight){
 const annotations=JSON.parse(annotationNode.textContent);const wanted=new URLSearchParams(location.search).get('hilo');const ranges=[];let chosen=null;
 for(const a of annotations){
  if(!a.quote)continue;
  const section=[...document.querySelectorAll('.doc-section')].find(s=>s.dataset.section===a.section);const body=section?.querySelector('.section-body');if(!body)continue;
  const full=body.textContent;let index=full.indexOf(a.quote);if(index<0)continue;
  if(full.indexOf(a.quote,index+1)!==-1){
   let found=-1;for(let at=index;at>=0;at=full.indexOf(a.quote,at+1))if((!a.prefix||full.slice(Math.max(0,at-150),at).trim()===a.prefix)&&(!a.suffix||full.slice(at+a.quote.length,at+a.quote.length+150).trim()===a.suffix)){found=at;break;}
   if(found<0)continue;index=found;
  }
  const walker=document.createTreeWalker(body,NodeFilter.SHOW_TEXT);let n,offset=0,start=null,end=null;
  while(n=walker.nextNode()){
   const next=offset+n.length;if(!start&&index>=offset&&index<next)start=[n,index-offset];
   const finish=index+a.quote.length;if(finish>offset&&finish<=next){end=[n,finish-offset];break;}offset=next;
  }
  if(start&&end){const range=document.createRange();range.setStart(...start);range.setEnd(...end);ranges.push(range);if(String(a.id)===wanted)chosen=range;}
 }
 CSS.highlights.set('debates',new Highlight(...ranges));
 if(chosen){CSS.highlights.set('debate-elegido',new Highlight(chosen));chosen.startContainer.parentElement.scrollIntoView({block:'center'});}
}
