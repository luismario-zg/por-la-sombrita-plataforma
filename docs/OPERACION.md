# Operación de la plataforma

## Separación de datos

Código en su propio repositorio. Por defecto, SQLite y los archivos de entrega de contraseñas están en `~/.local/share/pls-plataforma`, con permisos privados. No copiar esa carpeta a GitHub o a la raíz servida. Los archivos estáticos publicados son únicamente `app/static/`; documentos, comentarios y versiones se sirven mediante rutas controladas.

## Servicios

El despliegue utiliza Gunicorn con dos procesos y dos hilos por proceso, enlazado a loopback, detrás del túnel Cloudflare ya existente para `plsmty.bespokem.mx`. El servicio `pls-web.service` ejecuta la plataforma; `pls-platform-ai.service` consume la cola de fichas. `pls-web-tunnel.service` conserva el túnel dedicado, sin cambios de DNS.

El consumidor de IA procesa tres colas de una en una: fichas de discusiones, consultas
del asistente y sincronización de mejoras con GitHub. No ejecutar dos consumidores.

El espejo de Proton permanece a cargo de `pls-proton-pull.timer`. Un complemento de su servicio ejecuta `scripts/indexar_proton.py` después de cada sincronización correcta. La aplicación nunca recibe credenciales de Proton ni consulta Proton durante una visita pública: sirve únicamente elementos aprobados por el índice local.

Estado:

```bash
systemctl --user is-active pls-web.service pls-web-tunnel.service pls-platform-ai.service
systemctl --user is-active pls-proton-pull.timer
systemctl --user is-active pls-assistant-sources.timer
systemctl --user list-timers pls-proton-pull.timer pls-assistant-sources.timer
```

`pls-assistant-sources.timer` es la unidad diaria prevista para refrescar la caché
allowlisted del asistente. Si todavía no está instalada, el segundo comando lo hará
visible como ausente; usar mientras tanto la actualización manual descrita abajo.

Las cuentas se crean una vez mediante `scripts/inicializar.py`. El administrador general puede cambiar permisos, desactivar cuentas y restablecer contraseñas desde `/administracion`. Una cuenta inicial no se marca automáticamente como miembro oficial.

Los permisos de Editor, Moderador y Desarrollador son independientes del rol general y
de la membresía. Editor habilita edición documental; bases, misión, visión, valores,
objetivos y directrices exigen además administración. Moderador abre la cola privada de
aportaciones. Desarrollador habilita planeación y sincronización técnica.

## Fuentes y consultas del asistente

Actualizar manualmente las copias permitidas de LABNL y GitHub:

```bash
PLS_DATA_DIR=/home/claude/.local/share/pls-plataforma \
  .venv/bin/python scripts/indexar_fuentes_asistente.py
```

El script no descubre URLs ni sigue redirecciones a otro host. Mantiene como caché el
texto público y la fecha de consulta. Un fallo conserva la copia anterior y se reporta
en la salida; revisar el conteo de fuentes actualizadas y pendientes. El timer diario
debe ejecutar el mismo comando con el entorno privado del servicio.

Las preguntas y respuestas del asistente se vinculan al hash de la sesión anónima o
autenticada que las creó. Solo esa sesión puede consultar el resultado. El consumidor
elimina registros con más de 24 horas al recorrer la cola; si el consumidor está
detenido, la limpieza se reanuda al volver a ejecutarse. Esta eliminación local no
controla la retención del proveedor de IA.

El asistente recibe como contexto documentos públicos visibles y la caché allowlisted.
No tiene herramientas, no consulta la planeación privada ni el Proton privado y valida
que toda cita corresponda a una fuente entregada.

## Participación invitada y moderación

Una persona sin cuenta puede enviar una conversación o comentario a destinos
permitidos. La aportación queda pendiente y no aparece en rutas públicas hasta que una
cuenta con permiso de Moderador la atienda en `/moderacion/aportaciones`.

- el nombre o seudónimo elegido puede publicarse como atribución;
- nombre de contacto, organización, teléfono y correo son opcionales y permanecen en la
  cola privada;
- aprobar publica mediante la cuenta moderadora pero conserva la atribución invitada;
- descartar exige un motivo; aprobar admite una nota interna opcional;
- bases, misión, visión, valores, objetivos y directrices no aceptan aportaciones
  invitadas;
- no existe todavía eliminación automática ni apelación de la moderación.

No copiar contactos a comentarios, tickets o documentos públicos. Una solicitud de
revisión o eliminación requiere atención administrativa hasta que exista un flujo
específico.

## Operación comunitaria

Las rutas públicas `/trabajo`, `/actividades`, `/convocatorias` y `/rolitas` comparten
comentarios y aceptan aportaciones invitadas moderadas. Las tareas conservan propuesta
de responsable, aceptación/rechazo, plazo, entregable, revisión, cierre, eventos y
notificaciones. Las actividades solo las crean o editan cuentas administradoras. Las
convocatorias las puede crear una cuenta participante; editarlas requiere permiso de
Editor.

Las imágenes de convocatorias se guardan fuera del repositorio, junto a la base, con
nombre derivado del hash y permisos privados. Solo se aceptan PNG/JPEG validados, hasta
2 MiB y dimensiones acotadas. Respaldar también la carpeta `community-media`; el backup
SQLite no incluye esos archivos.

## Mejoras y sincronización con GitHub

`/mejoras` conserva el registro comunitario. Una persona con permiso de Desarrollador
puede confirmar que título y descripción son públicos y encolar la creación del issue.
El consumidor invoca `gh api` con argumentos controlados, sin shell, y usa marcadores
estables para reconciliar una interrupción sin crear el mismo issue o comentario dos
veces.

Cada cinco minutos, el consumidor marca para lectura los registros que ya tienen issue;
después trae estado y comentarios. El cierre remoto mueve una mejora no verificada a
revisión, nunca a implementada. Marcarla implementada exige comprobación y referencia
en la plataforma.

Comprobaciones operativas:

```bash
gh auth status
systemctl --user is-active pls-platform-ai.service
journalctl --user -u pls-platform-ai.service -n 100 --no-pager
```

Si la sincronización queda en error, el contenido local se conserva. Corregir conexión
o permisos y volver a solicitar publicar/traer desde la ficha; no editar directamente
la base ni repetir manualmente la creación del issue.

## Cambiar código

Comprobar pruebas, preparar respaldo coherente con SQLite y revisar cambios. No desplegar código no revisado procedente de un fork o PR. Reiniciar únicamente servicios de la plataforma después de actualizar; no hace falta reiniciar el túnel por cambios de aplicación. Esta primera versión crea tablas si no existen; futuros cambios de esquema deberán incluir migraciones explícitas y reversibles cuando sea posible.

```bash
.venv/bin/python -m pytest -q
.venv/bin/python scripts/importar_evolucion.py
git diff --check
```

La primera orden cubre el núcleo, participación invitada, operación comunitaria,
asistente, mejoras y seguridad de rutas. La segunda solo valida los borradores de
contenido; importar requiere base explícita, respaldo confirmado y `--apply`. Antes de
desplegar, revisar además que `gh auth status` corresponda a la cuenta y repositorio
esperados y que las pruebas no dependan de red ni credenciales reales.

## Edición de documentos

Las cuentas con permiso de Editor usan Markdown desde `/editar/<documento>`. El
servidor convierte el borrador, elimina HTML no permitido y guarda únicamente el HTML
sanitizado en la nueva revisión. La vista previa llama al mismo conversor y nunca
modifica el documento. Los encabezados `##` y `###` pueden incluir anclas
`{#identificador}`; conservarlas mantiene estables las secciones, enlaces e hilos.

El endpoint de guardado todavía acepta el campo HTML anterior para compatibilidad con
clientes existentes, con la misma sanitización. La interfaz publicada ya no lo expone.
Marcar una versión oficial exige una referencia; los documentos del núcleo requieren
además un rol administrativo. Una edición nunca archiva automáticamente su discusión.

## Respaldos y restauración

Ejecutar `.venv/bin/python scripts/respaldar.py`. Usa la API de backup de SQLite para incluir de forma consistente el estado WAL y guarda la copia 0600 en la carpeta privada `backups/`.

Para restaurar, detener primero web y consumidor de IA, conservar una copia del estado actual, restaurar el archivo validado y retirar únicamente los WAL/SHM residuales que correspondan a la base detenida. Comprobar `PRAGMA integrity_check` y permisos antes de arrancar. No usar `cp` de una base activa como sustituto de la API de backup.

El respaldo local no protege frente a pérdida del host. El respaldo cifrado fuera del host y la política de retención quedan para la siguiente etapa del prototipo.

## Reversión del despliegue inicial

Antes de sustituir el sitio estático, guardar fuera del repositorio la unidad previa de `pls-web.service` y su estado. Si falla la verificación, restablecer esa unidad, recargar el gestor de servicios de usuario y reiniciar únicamente `pls-web.service`. Conservar la base nueva y detener su consumidor; no borrar aportaciones recibidas. El túnel y DNS permanecen apuntando al mismo puerto.

## Límites de la integración de resúmenes

Un solo consumidor atiende la cola. Al reiniciarlo, los trabajos que quedaron en curso se marcan fallidos; un revisor puede solicitarlos de nuevo. No se ejecutan reintentos infinitos ni se omiten fallos. Los borradores no cambian estados de discusiones, permisos o documentos.

## Ciclo de planeación del desarrollo

`/planeacion-desarrollo-plataforma` presenta el informe completo y las preguntas
estructuradas únicamente a cuentas con el permiso adicional `developer_access`.
Ese permiso no sustituye el rol general ni la membresía. Cada guardado añade una
nueva respuesta, conserva autor y fecha y mueve el item a `answered`. No se
sobrescribe el historial.

El administrador general puede cambiar el permiso desde `/administracion`. Para la
asignación inicial o una recuperación operativa:

```bash
PLS_DATA_DIR=/home/claude/.local/share/pls-plataforma \
  .venv/bin/python scripts/asignar_desarrollador.py luismario --exclusive
```

Cuando una persona avise que terminó de responder, obtener el estado para revisión:

```bash
PLS_DATA_DIR=/home/claude/.local/share/pls-plataforma \
  .venv/bin/python scripts/exportar_planeacion.py
```

Después de implementar o encontrar un bloqueo, actualizar el mismo registro:

```bash
PLS_DATA_DIR=/home/claude/.local/share/pls-plataforma \
  .venv/bin/python scripts/actualizar_planeacion.py estado \
  --item D01 --status implemented --nota "Implementación y verificación realizadas."

PLS_DATA_DIR=/home/claude/.local/share/pls-plataforma \
  .venv/bin/python scripts/actualizar_planeacion.py agregar \
  --item P01 --titulo "Aclaración nueva" --pregunta "¿Qué falta definir?" \
  --clasificacion "Pendientes surgidos durante la implementación"
```

Los estados posibles son `pending`, `answered`, `needs_clarification`,
`in_progress`, `implemented`, `deferred` y `closed`. Un cambio de estado conserva
un evento público. No marcar `implemented` antes de probar el comportamiento.

El índice inicial vive en `contenido/planeacion-desarrollo.json`; sincronizarlo al
arrancar actualiza títulos y preguntas, pero nunca estados o respuestas. Los nuevos
pendientes creados durante la ejecución permanecen en la base aunque no estén en el
índice inicial.

La transcripción recibe un archivo terminado de máximo 12 MiB y lo mantiene en
memoria. El servidor lo envía al proveedor configurado y devuelve únicamente texto;
no guarda el audio. El navegador inserta ese texto como borrador editable y nunca lo
envía automáticamente. Configurar `TRANSCRIBE_API_KEY` fuera del repositorio, junto
con `TRANSCRIBE_BASE_URL`, `TRANSCRIBE_MODEL` y `TRANSCRIBE_LANGUAGES` cuando haga
falta. La implementación usa `gpt-transcribe` por defecto.
El límite queda por debajo de los 25 MiB admitidos y usa los formatos de archivo
documentados en la [guía oficial de transcripción de OpenAI](https://developers.openai.com/api/docs/guides/speech-to-text).

## Archivo público de Proton

`scripts/indexar_proton.py` lee el manifiesto del espejo unidireccional existente. La raíz permitida está fijada a `Por La Sombrita MTY General`; cualquier otra carpeta de `/my-files`, incluida la de promotores, queda fuera incluso si cambia la navegación del sitio.

La publicación se decide antes de insertar cada elemento. Se rechazan nombres o componentes asociados con privacidad, accesos, contraseñas, credenciales, tokens y recuperación, además de archivos ocultos y formatos típicos de secretos. Los textos pequeños se examinan por patrones de claves o contraseñas. El índice solo guarda rutas relativas públicas; no muestra rutas del servidor ni las exclusiones.

Los archivos descargables se sirven desde una ruta controlada que vuelve a comprobar que sean archivos regulares dentro del espejo. HTML, SVG y formatos no incluidos en la lista segura se descargan como adjuntos; no se ejecutan dentro del origen autenticado. La vista integrada se limita a PDF, imágenes raster, audio, video y texto escapado. Los documentos nativos de Proton no tienen copia local: la ficha muestra su ruta y el enlace público convencional.

Cada elemento tiene una versión indexada. Los archivos cambian de versión cuando cambia su revisión remota; las carpetas, cuando cambia su subárbol público. Las fichas de discusión se marcan desactualizadas si el elemento cambia. Si desaparece, su descarga se bloquea, pero su ficha y las conversaciones permanecen en el historial.
