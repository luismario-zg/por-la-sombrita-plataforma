# Validación del primer prototipo

13 de septiembre de 2026. Se probaron escenarios con cuentas y mensajes ficticios en bases temporales, separadas de producción.

- 15 pruebas automatizadas: lectura pública, autenticación y rotación de sesiones, cambio de contraseña, CSRF y Origin, límites de acceso, roles y último administrador general, anclas/versiones, obsolescencia de fichas, archivo/reapertura, edición vinculada, sanitización y escape, cola de IA, fallos del proveedor y conservación de revisiones humanas.
- Navegador Chromium: ingreso y cambio de clave provisional, selección de fragmento, creación de hilo, comentario, ficha humana, aprobación, propuesta de cierre y archivo con consenso.
- Lectura móvil a 390 px sin desbordamiento de página en inicio, documento, hilo y administración.
- axe-core: comprobación de inicio, documento, cuenta, lista de discusiones, hilo, revisión, comunidad y administración. Se corrigió el contraste del encabezado del resumen y se volvió a comprobar esa pantalla.
- Verificación de resaltado persistente de un fragmento conservado y acceso al historial de fichas.
- Resumen real mediante Luna high con la sesión local: ficha JSON válida y diferencia de posturas preservada. Consumidor real probado sobre un hilo ficticio: almacena borrador, no aprueba y mantiene abierto el hilo.
- Auditoría de dependencias fijadas con pip-audit: sin vulnerabilidades conocidas reportadas en la consulta.
- Revisión previa de archivos Git: sin base de datos, registros, accesos reales ni patrones conocidos de credenciales. Las contraseñas provisionales quedaron fuera del repositorio.

Estas comprobaciones no equivalen a una auditoría completa ni a validación de la gobernanza de la comunidad. Las funciones futuras indicadas en ROADMAP.md no están implementadas.
