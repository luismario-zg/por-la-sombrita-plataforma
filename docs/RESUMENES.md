# Fichas de revisión y resúmenes

El prototipo usa **gpt-5.6-luna** con esfuerzo **high**, mediante `codex exec` y la sesión ChatGPT/Codex ya configurada en el servidor por el operador. Se verificó una generación real con contenido ficticio. No se usa ni requiere una clave de API en el repositorio y no se cambian modelos silenciosamente si el acceso falla.

La suscripción y sus límites corresponden al operador. Se permite solicitar generaciones solo a revisores y administradores, con cola persistente, un consumidor y límite por cuenta. La plataforma no revende ni entrega el acceso a Codex a usuarios finales.

## Contrato de la ficha

`topic`, `question`, `context`, `current_text`, `proposed_text`, `summary`, `agreements`, `disagreements`, `pending` y `evidence`, todos como texto. Se manda el hilo completo dentro del límite del prototipo, el fragmento y sección originales, la sección actual, versiones y contexto de las bases. Si supera el límite, se solicita revisión manual; no se recortan mensajes silenciosamente.

El modelo solo produce un borrador. Se validan campos y tamaño. Se conservan número de mensajes y versión del documento contemplados; si cambia alguno, la interfaz marca la ficha como desactualizada. Si otra persona modificó la ficha durante la generación, se conserva esa revisión y se descarta el resultado tardío.

La ficha se puede corregir a mano y aprobar para deliberar. Su aprobación no equivale a aprobar el documento ni a declarar consenso. Cerrar requiere proponer cierre y luego registrar explícitamente consenso, resumen y resultado. Si hubo edición, se exige una revisión documental real vinculada al hilo. Las versiones de fichas se conservan públicamente.

## Ejecución segura del proveedor temporal

`app/ai.py` fija modelo y esfuerzo, deshabilita herramientas de ejecución/navegación/aplicaciones/plugins/multiagente, ignora configuración de usuario para evitar conectores accidentales y usa un directorio temporal fuera del repositorio. La autenticación guardada se utiliza por el CLI; nunca se extrae, imprime ni incorpora a datos de la plataforma. Se valida salida contra un esquema JSON y se limita cada proceso a 180 segundos. Un error no modifica documentos o acuerdos; se muestra estado y opción manual.

No ejecutar la autenticación de suscripción en CI pública o jobs de PRs. La integración solo corre como consumidor revisado en el servidor confiable del operador. Los tests automatizados simulan el proveedor. El adaptador será reemplazable por un modelo pequeño local en una fase posterior.

Referencias oficiales consultadas el 13 de septiembre de 2026:

- https://developers.openai.com/codex/noninteractive — uso no interactivo, autenticación existente, salidas estructuradas y ejecución efímera.
- https://learn.chatgpt.com/docs/config-file/config-reference — modelo/esfuerzo y controles de herramientas.

Las capacidades concretas de Luna se comprobaron en esta instalación; la documentación general no garantiza acceso, disponibilidad ni cuotas de una cuenta particular.
