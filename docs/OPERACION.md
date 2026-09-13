# Operación de la plataforma

## Separación de datos

Código en su propio repositorio. Por defecto, SQLite y los archivos de entrega de contraseñas están en `~/.local/share/pls-plataforma`, con permisos privados. No copiar esa carpeta a GitHub o a la raíz servida. Los archivos estáticos publicados son únicamente `app/static/`; documentos, comentarios y versiones se sirven mediante rutas controladas.

## Servicios

El despliegue utiliza Gunicorn con dos procesos y dos hilos por proceso, enlazado a loopback, detrás del túnel Cloudflare ya existente para `plsmty.bespokem.mx`. El servicio `pls-web.service` ejecuta la plataforma; `pls-platform-ai.service` consume la cola de fichas. `pls-web-tunnel.service` conserva el túnel dedicado, sin cambios de DNS.

El espejo de Proton permanece a cargo de `pls-proton-pull.timer`. Un complemento de su servicio ejecuta `scripts/indexar_proton.py` después de cada sincronización correcta. La aplicación nunca recibe credenciales de Proton ni consulta Proton durante una visita pública: sirve únicamente elementos aprobados por el índice local.

Estado:

```bash
systemctl --user is-active pls-web.service pls-web-tunnel.service pls-platform-ai.service
systemctl --user is-active pls-proton-pull.timer
```

Las cuentas se crean una vez mediante `scripts/inicializar.py`. El administrador general puede cambiar permisos, desactivar cuentas y restablecer contraseñas desde `/administracion`. Una cuenta inicial no se marca automáticamente como miembro oficial.

## Cambiar código

Comprobar pruebas, preparar respaldo coherente con SQLite y revisar cambios. No desplegar código no revisado procedente de un fork o PR. Reiniciar únicamente servicios de la plataforma después de actualizar; no hace falta reiniciar el túnel por cambios de aplicación. Esta primera versión crea tablas si no existen; futuros cambios de esquema deberán incluir migraciones explícitas y reversibles cuando sea posible.

## Respaldos y restauración

Ejecutar `.venv/bin/python scripts/respaldar.py`. Usa la API de backup de SQLite para incluir de forma consistente el estado WAL y guarda la copia 0600 en la carpeta privada `backups/`.

Para restaurar, detener primero web y consumidor de IA, conservar una copia del estado actual, restaurar el archivo validado y retirar únicamente los WAL/SHM residuales que correspondan a la base detenida. Comprobar `PRAGMA integrity_check` y permisos antes de arrancar. No usar `cp` de una base activa como sustituto de la API de backup.

El respaldo local no protege frente a pérdida del host. El respaldo cifrado fuera del host y la política de retención quedan para la siguiente etapa del prototipo.

## Reversión del despliegue inicial

Antes de sustituir el sitio estático, guardar fuera del repositorio la unidad previa de `pls-web.service` y su estado. Si falla la verificación, restablecer esa unidad, recargar el gestor de servicios de usuario y reiniciar únicamente `pls-web.service`. Conservar la base nueva y detener su consumidor; no borrar aportaciones recibidas. El túnel y DNS permanecen apuntando al mismo puerto.

## Límites de la integración de resúmenes

Un solo consumidor atiende la cola. Al reiniciarlo, los trabajos que quedaron en curso se marcan fallidos; un revisor puede solicitarlos de nuevo. No se ejecutan reintentos infinitos ni se omiten fallos. Los borradores no cambian estados de discusiones, permisos o documentos.

## Archivo público de Proton

`scripts/indexar_proton.py` lee el manifiesto del espejo unidireccional existente. La raíz permitida está fijada a `Por La Sombrita MTY General`; cualquier otra carpeta de `/my-files`, incluida la de promotores, queda fuera incluso si cambia la navegación del sitio.

La publicación se decide antes de insertar cada elemento. Se rechazan nombres o componentes asociados con privacidad, accesos, contraseñas, credenciales, tokens y recuperación, además de archivos ocultos y formatos típicos de secretos. Los textos pequeños se examinan por patrones de claves o contraseñas. El índice solo guarda rutas relativas públicas; no muestra rutas del servidor ni las exclusiones.

Los archivos descargables se sirven desde una ruta controlada que vuelve a comprobar que sean archivos regulares dentro del espejo. HTML, SVG y formatos no incluidos en la lista segura se descargan como adjuntos; no se ejecutan dentro del origen autenticado. La vista integrada se limita a PDF, imágenes raster, audio, video y texto escapado. Los documentos nativos de Proton no tienen copia local: la ficha muestra su ruta y el enlace público convencional.

Cada elemento tiene una versión indexada. Los archivos cambian de versión cuando cambia su revisión remota; las carpetas, cuando cambia su subárbol público. Las fichas de discusión se marcan desactualizadas si el elemento cambia. Si desaparece, su descarga se bloquea, pero su ficha y las conversaciones permanecen en el historial.
