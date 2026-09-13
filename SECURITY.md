# Seguridad del prototipo

No publicar vulnerabilidades con contraseñas, tokens, base de datos ni información personal. Usar un aviso privado al administrador del proyecto; si GitHub permite informes privados de seguridad en este repositorio, utilizar ese mecanismo.

## Controles implementados

- Contraseñas con scrypt y sal individual, sesiones aleatorias almacenadas como SHA-256, cookies HttpOnly/Secure/SameSite y cambio obligatorio de claves provisionales.
- Rotación de sesión al entrar y cambiar contraseña; revocación de sesiones al cambiar permisos, desactivar una cuenta o restablecer su contraseña.
- Origin exacto, contenido JSON y token CSRF para cada mutación; sin CORS permisivo.
- Permisos comprobados en servidor; el último administrador general activo no puede eliminar su propio acceso privilegiado sin otro administrador general.
- Límites persistentes de intentos de acceso, comentarios, hilos y generación asistida; tamaños máximos de solicitudes y campos.
- SQL parametrizado, transacciones de escritura y control optimista de versión documental; bloqueo de comentarios en hilos archivados.
- Escape de mensajes/fichas, HTML administrativo sanitizado y política CSP. No se permiten scripts o atributos ejecutables en documentos.
- Datos, sesiones, respaldos y credenciales fuera del código público; directorio privado 0700 y base/entrega de contraseñas 0600.
- Conservación de mensajes, anclas originales, versiones y eventos administrativos; sin borrado destructivo en la interfaz del prototipo.
- IA solo por solicitud de un revisor autorizado, consumidor único y modelo fijado. Herramientas de shell, aplicaciones, MCP configurado, navegador, plugins y multiagente deshabilitados; sandbox de solo lectura, carpeta temporal, timeout y salida estructurada validada. Los comentarios son datos no confiables, no instrucciones.
- El archivo de Proton usa una raíz allowlisted y exclusión previa por ruta, tipo y patrones sensibles. La aplicación no enumera `/my-files`, no indexa carpetas de promotores ni expone rutas internas del servidor.
- Las descargas vuelven a resolver el archivo dentro del espejo, rechazan enlaces simbólicos y no renderizan HTML o SVG arbitrario en el origen autenticado. Las vistas permitidas reciben una política de contenido aislada.

## Límites explícitos

Es un prototipo, no una auditoría de seguridad completa. La autenticación y los respaldos deben revisarse antes de abrir el registro masivo. No hay todavía segundo factor, recuperación automática, moderación avanzada ni protección contra todo abuso distribuido. El proveedor perimetral aplica sus propios controles.

El consumidor temporal comparte la autenticación local del operador con Codex CLI en un servidor confiable; no debe ejecutarse desde PRs, forks o acciones de GitHub, ni montar esa autenticación en clientes. Al madurar, migrar a un modelo local o a un servicio con credenciales y límites dedicados.

## Publicación y privacidad

Los comentarios y sus nombres son públicos en el sitio, pero no se versionan en Git. Antes de una eventual exportación, consentimiento, retirada o anonimización, establecer un procedimiento que preserve el sentido del historial. No copiar logs crudos a incidencias públicas. Las contraseñas provisionales se entregan de una en una mediante un canal privado; borrar el listado de entrega cuando deje de ser necesario.
