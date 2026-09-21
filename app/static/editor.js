/* Editor Markdown guiado. La conversión y sanitización definitivas ocurren en el servidor. */
const markdownForm=document.querySelector('.markdown-document-form');
const markdownSource=document.getElementById('markdown-source');
const markdownPreview=document.getElementById('markdown-preview');
const markdownStatus=document.querySelector('.markdown-preview-status');
const markdownCount=document.querySelector('[data-md-count]');
let markdownTimer=null;let markdownRequest=null;

function markdownReplace(before,after,placeholder){
 const start=markdownSource.selectionStart;const end=markdownSource.selectionEnd;const selected=markdownSource.value.slice(start,end)||placeholder;
 markdownSource.setRangeText(before+selected+after,start,end,'end');markdownSource.focus();markdownSource.dispatchEvent(new Event('input',{bubbles:true}));
}
function markdownLines(prefix,ordered=false){
 const start=markdownSource.selectionStart;const end=markdownSource.selectionEnd;const value=markdownSource.value;const lineStart=value.lastIndexOf('\n',Math.max(0,start-1))+1;const next=value.indexOf('\n',end);const lineEnd=next<0?value.length:next;
 const lines=value.slice(lineStart,lineEnd).split('\n');const changed=lines.map((line,index)=>(ordered?`${index+1}. `:prefix)+line).join('\n');
 markdownSource.setRangeText(changed,lineStart,lineEnd,'end');markdownSource.focus();markdownSource.dispatchEvent(new Event('input',{bubbles:true}));
}
document.querySelectorAll('[data-md]').forEach(button=>button.addEventListener('click',()=>{
 const action=button.dataset.md;
 if(action==='bold')markdownReplace('**','**','texto en negritas');else if(action==='italic')markdownReplace('*','*','texto en cursivas');else if(action==='link')markdownReplace('[','](https://)','nombre del enlace');else if(action==='h2')markdownLines('## ');else if(action==='h3')markdownLines('### ');else if(action==='ul')markdownLines('- ');else if(action==='ol')markdownLines('',true);else if(action==='quote')markdownLines('> ');
}));

async function updateMarkdownPreview(){
 clearTimeout(markdownTimer);markdownRequest?.abort();markdownRequest=new AbortController();markdownStatus.textContent='Actualizando vista previa…';
 try{
  const session=await getSession();const response=await fetch(markdownForm.dataset.api+'/preview-markdown',{method:'POST',credentials:'same-origin',signal:markdownRequest.signal,headers:{'Content-Type':'application/json','X-CSRF-Token':session.csrf},body:JSON.stringify({markdown:markdownSource.value})});
  const result=await response.json();if(!response.ok)throw new Error(result.error||'No se pudo generar la vista previa.');markdownPreview.innerHTML=result.html;markdownStatus.textContent='Vista previa actualizada.';
 }catch(error){if(error.name!=='AbortError')markdownStatus.textContent='Revisa el formato: '+error.message;}
}
markdownSource?.addEventListener('input',()=>{markdownCount.textContent=markdownSource.value.length;markdownStatus.textContent='Cambios pendientes de previsualizar.';clearTimeout(markdownTimer);markdownTimer=setTimeout(updateMarkdownPreview,700);});
document.querySelector('[data-md-preview]')?.addEventListener('click',updateMarkdownPreview);
window.addEventListener('beforeunload',event=>{if(markdownForm?.dataset.dirty==='true'){event.preventDefault();event.returnValue='';}});
