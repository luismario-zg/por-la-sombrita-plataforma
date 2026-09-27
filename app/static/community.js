/* Formularios y ayudas del módulo de operación comunitaria. Los permisos se validan en el servidor. */
if(location.pathname==='/trabajo' && /^#tarea-\d+$/.test(location.hash) && !document.getElementById(location.hash.slice(1)) && !new URLSearchParams(location.search).has('tarea')){
 location.replace('/trabajo?tarea='+location.hash.slice(7)+location.hash);
}

document.querySelectorAll('[data-permanent]').forEach(box=>{
 const form=box.closest('form');const until=form?.querySelector('[data-valid-until]');
 const update=()=>{if(!until)return;until.disabled=box.checked;until.required=!box.checked;if(box.checked)until.value='';};
 box.addEventListener('change',update);update();
});

document.querySelectorAll('[data-community-image]').forEach(input=>input.addEventListener('change',async()=>{
 const form=input.closest('form');const status=form.querySelector('.image-status');const hidden=form.querySelector('[name=image_path]');const file=input.files[0];
 if(!file)return;if(!['image/png','image/jpeg'].includes(file.type)||file.size>2*1024*1024){status.textContent='Elige un PNG o JPEG de máximo 2 MB.';input.value='';return;}
 status.textContent='Subiendo imagen…';input.disabled=true;
 try{
  const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(file);});
  const session=await fetch('/api/session',{credentials:'same-origin',cache:'no-store'}).then(r=>r.json());
  const response=await fetch('/api/community/media',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':session.csrf},body:JSON.stringify({data})});
  const result=await response.json();if(!response.ok)throw new Error(result.error||'No se pudo subir la imagen.');
  hidden.value=result.path;status.textContent=`Imagen lista (${result.width} × ${result.height} px).`;
 }catch(error){status.textContent=error.message;input.value='';}finally{input.disabled=false;}
}));

// Menús de etiquetas: uno abierto a la vez; se cierran con Escape o al pulsar fuera.
const chipMenus=[...document.querySelectorAll('.chip-menu')];
chipMenus.forEach(menu=>menu.addEventListener('toggle',()=>{if(menu.open)chipMenus.forEach(other=>{if(other!==menu)other.open=false;});}));
document.addEventListener('click',event=>chipMenus.forEach(menu=>{if(menu.open&&!menu.contains(event.target))menu.open=false;}));
document.addEventListener('keydown',event=>{if(event.key!=='Escape')return;const open=chipMenus.find(menu=>menu.open);if(open){open.open=false;open.querySelector('summary').focus();}});
