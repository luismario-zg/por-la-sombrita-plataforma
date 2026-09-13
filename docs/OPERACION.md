# Operación de la plataforma

## Separación de datos

Código en su propio repositorio. Por defecto, SQLite y los archivos de entrega de contraseñas están en `~/.local/share/pls-plataforma`, con permisos privados. No copiar esa carpeta a GitHub o a la raíz servida. Los archivos estáticos publicados son únicamente `app/static/`; documentos, comentarios y versiones se sirven mediante rutas controladas.

## Servicios

El despliegue utiliza Gunicorn con dos procesos y dos hilos por proceso, enlazado a loopback, detrás del túnel Cloudflare ya existente para `plsmty.bespokem.mx`. El servicio `pls-web.service` ejecuta la plataforma; `pls-platform-ai.service` consume la cola de fichas. `pls-web-tunnel.service` conserva el túnel dedicado, sin cambios de DNS.

Estado:

```bash
systemctl --user is-active pls-web.service pls-web-tunnel.service pls-platform-ai.service
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
