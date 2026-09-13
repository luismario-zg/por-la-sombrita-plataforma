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

## Verificación después de publicar

El prototipo quedó activo en https://plsmty.bespokem.mx/. Se verificaron las rutas públicas, rechazo de administración anónima y rutas de datos inexistentes. Se comprobó el ingreso real del administrador general con su contraseña provisional y el cierre de sesión; no se cambiaron claves ni se crearon mensajes de ensayo en producción. Las nueve cuentas conservan cambio de clave obligatorio. La CI de GitHub terminó correctamente.

## Archivo público de Proton

Se añadieron pruebas para el índice allowlisted, exclusión por ruta y contenido sensible, documentos nativos, cambios de versión y desactivación sin borrado. El conjunto completo quedó en 18 pruebas automatizadas.

En una base temporal se indexó el espejo real: 53 carpetas contando la raíz, 236 archivos descargables y 10 documentos nativos de Proton. Se excluyó un único archivo oculto; la carpeta de promotores nunca entró en el conjunto permitido. Se probaron navegación, búsqueda, previsualización de texto, acceso convencional a un documento nativo, conversación sobre carpeta, aparición en el historial global y cierre sin edición del archivo.

Chromium no encontró errores de ejecución ni desbordamiento a 390 px en la raíz del archivo, una carpeta, un archivo textual, un documento nativo y una discusión. axe-core no reportó incidencias WCAG A/AA después de hacer enfocable la región desplazable de texto. La auditoría de dependencias volvió a reportar que no conoce vulnerabilidades en las versiones fijadas.
