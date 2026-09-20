# Por la Sombrita · plataforma comunitaria

Prototipo de lectura pública y deliberación sobre los documentos de Por la Sombrita. Sitio: **https://plsmty.bespokem.mx/**.

La plataforma es independiente del bot de rutas térmicas. Conserva la identidad gráfica y los documentos públicos del proyecto, sin convertir propuestas en acuerdos ni cuentas en membresías oficiales.

## Qué permite

- Leer documentos, versiones, discusiones e historial sin cuenta.
- Entrar con usuario y contraseña; cambiar la contraseña provisional en el primer acceso.
- Seleccionar una frase o comentar una sección completa; conservar cita, contexto y versión de origen.
- Reconocer citas en el documento actual mediante resaltado cuando todavía coinciden; conservar siempre la versión original si el texto cambia.
- Comentar con nombre y fecha; conservar los mensajes sin edición ni borrado en esta primera versión.
- Elaborar una ficha por hilo: tema en una frase, pregunta concreta, contexto, redacción actual, redacción propuesta, resumen, coincidencias, desacuerdos, pendientes y mensajes de respaldo.
- Pedir una ficha con Luna en `high` mediante la sesión local de Codex; corregirla y aprobarla como base de deliberación. Nuevos mensajes o cambios del documento vuelven obsoleta la ficha.
- Proponer cierre y archivar con resumen del consenso, con edición vinculada o sin cambios. Reabrir con motivo, conservando cierres y fichas anteriores.
- Editar documentos con control de versión y motivo; marcar oficial solo al registrar la referencia de aprobación.
- Administrar permisos y accesos; registrar membresía oficial de forma independiente.
- Navegar en modo público y de solo lectura todas las carpetas y archivos del espacio compartido `Por La Sombrita MTY General` en Proton Drive.
- Abrir una discusión sobre una carpeta o un archivo completo desde cualquier nivel del árbol. Los documentos nativos que no se pueden descargar muestran su ruta y el acceso convencional a Proton.
- Consultar la planeación de desarrollo, guardar respuestas con historial y mantener visibles preguntas pendientes, trabajo en proceso e implementaciones terminadas.
- Dictar una respuesta desde el micrófono para obtener un borrador editable; el audio no se conserva y la transcripción nunca se guarda automáticamente.

No hay votaciones automáticas ni inferencia de consenso por IA. Los resúmenes son propuestas revisables. El administrador general inicial es Luis Mario; las otras ocho cuentas iniciales son participantes. Las credenciales se generan localmente y nunca están incluidas en este repositorio.

## Ejecutar localmente

Python 3.12 recomendado. SQLite es parte de Python. No se necesita Node para ejecutar la aplicación.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/inicializar.py
.venv/bin/gunicorn 'app:create_app()' --bind 127.0.0.1:8876 --workers 2 --threads 2
```

La configuración predeterminada usa `https://plsmty.bespokem.mx`, cookies Secure y una carpeta privada de datos fuera del repositorio. Para un ensayo exclusivamente local:

```bash
PLS_DATA_DIR=/tmp/pls-demo PLS_BASE_URL=http://127.0.0.1:8877 .venv/bin/python scripts/inicializar.py
PLS_DATA_DIR=/tmp/pls-demo PLS_BASE_URL=http://127.0.0.1:8877 .venv/bin/gunicorn 'app:create_app({"COOKIE_SECURE": False, "COOKIE_NAME": "pls-demo"})' --bind 127.0.0.1:8877
```

Nunca desactivar cookies Secure en el sitio publicado. `inicializar.py` es idempotente: importa únicamente los documentos que no existen y crea solamente cuentas faltantes, sin restablecer las existentes. Entrega una ruta a un archivo privado de contraseñas provisionales, no sus valores.

## Configuración

| Variable | Uso |
|---|---|
| `PLS_DATA_DIR` | Carpeta privada de SQLite y respaldos; por defecto `~/.local/share/pls-plataforma` |
| `PLS_BASE_URL` | Origen exacto para canónicas y validación CSRF |
| `PLS_AI_ENABLED` | `1` habilita solicitar fichas al consumidor dedicado; `0` conserva el modo manual |
| `PLS_CODEX_BIN` | Ruta al binario de Codex CLI en el servidor confiable |
| `PLS_PROTON_MIRROR` | Espejo local de la carpeta pública; por defecto apunta a `Por La Sombrita MTY General` |
| `PLS_DEVELOPMENT_REPORT` | HTML autocontenido que se consulta dentro de la sección de planeación |
| `PLS_DEVELOPMENT_INDEX` | Índice inicial de preguntas; por defecto `contenido/planeacion-desarrollo.json` |
| `TRANSCRIBE_API_KEY` | Credencial privada del proveedor de transcripción; nunca llega al navegador |
| `TRANSCRIBE_BASE_URL` | Base de la API compatible; por defecto `https://api.openai.com/v1` |
| `TRANSCRIBE_MODEL` | Modelo de transcripción; por defecto `gpt-transcribe` |
| `TRANSCRIBE_LANGUAGES` | Idiomas esperados separados por comas; por defecto `es,en` |

Con IA habilitada, ejecutar además `.venv/bin/python scripts/worker.py` como servicio dedicado. Solo debe existir un consumidor de la cola. No se exponen comandos, modelos arbitrarios ni credenciales a participantes.

Para actualizar el catálogo público después de sincronizar el espejo:

```bash
PLS_DATA_DIR=/ruta/privada .venv/bin/python scripts/indexar_proton.py
```

El indexador solo acepta elementos bajo `Por La Sombrita MTY General`. Excluye rutas privadas, accesos, contraseñas, credenciales, tokens, archivos ocultos y formatos reservados; también examina archivos de texto pequeños para detectar patrones sensibles. Nunca publica la carpeta de promotores. Los elementos retirados se desactivan sin borrar sus conversaciones.

## Datos y código público

`contenido/inicial/` contiene ocho HTML previamente públicos usados para iniciar una base vacía. Son una fotografía histórica del sitio anterior, no la configuración de la aplicación ni su estado actual. El contenido vigente y sus revisiones se conservan en la base privada de ejecución. Las discusiones reales nunca se exportan al repositorio Git.

- [Operación y respaldos](docs/OPERACION.md).
- [Modelo de permisos y seguridad](SECURITY.md).
- [Resúmenes temporales y migración a modelo local](docs/RESUMENES.md).
- [Desarrollo futuro](docs/ROADMAP.md).
- [Procedencia de contenido y diseño](docs/FUENTES.md).

## Comprobar

```bash
.venv/bin/python -m pytest -q
```

Las pruebas usan una base temporal y mensajes ficticios. La CI nunca recibe la sesión de Codex ni una clave OpenAI: el adaptador de IA se simula en pruebas. Las comprobaciones reales de Luna se hacen manualmente en el servidor autorizado con ejemplos ficticios.

## Licencias

El código nuevo de la plataforma se distribuye bajo [MIT](LICENSE). Los documentos comunitarios importados conservan su procedencia y no cambian de licencia por estar incluidos aquí; revisar las fuentes y atribuciones antes de redistribuirlos. Barlow Condensed conserva su licencia OFL en `app/static/OFL-Barlow.txt`.
