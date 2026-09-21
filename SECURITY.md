# Seguridad del prototipo

No publicar vulnerabilidades con contraseñas, tokens, base de datos ni información personal. Usar un aviso privado al administrador del proyecto; si GitHub permite informes privados de seguridad en este repositorio, utilizar ese mecanismo.

## Controles implementados

- Contraseñas con scrypt y sal individual, sesiones aleatorias almacenadas como SHA-256, cookies HttpOnly/Secure/SameSite y cambio obligatorio de claves provisionales.
- Rotación de sesión al entrar y cambiar contraseña; revocación de sesiones al cambiar permisos, desactivar una cuenta o restablecer su contraseña.
- Origin exacto, contenido JSON y token CSRF para cada mutación; sin CORS permisivo.
- Permisos comprobados en servidor; el último administrador general activo no puede eliminar su propio acceso privilegiado sin otro administrador general.
- Editor, Moderador y Desarrollador son capacidades independientes del rol y de la membresía. Las bases y directrices exigen Editor y además rol administrativo; la cola invitada exige Moderador y la planeación técnica exige Desarrollador.
- Límites persistentes de intentos de acceso, comentarios, hilos y generación asistida; tamaños máximos de solicitudes y campos.
- SQL parametrizado, transacciones de escritura y control optimista de versión documental; bloqueo de comentarios en hilos archivados.
- Escape de mensajes/fichas, HTML administrativo sanitizado y política CSP. No se permiten scripts o atributos ejecutables en documentos.
- Datos, sesiones, respaldos y credenciales fuera del código público; directorio privado 0700 y base/entrega de contraseñas 0600.
- Conservación de mensajes, anclas originales, versiones y eventos administrativos; sin borrado destructivo en la interfaz del prototipo.
- IA solo por solicitud de un revisor autorizado, consumidor único y modelo fijado. Herramientas de shell, aplicaciones, MCP configurado, navegador, plugins y multiagente deshabilitados; sandbox de solo lectura, carpeta temporal, timeout y salida estructurada validada. Los comentarios son datos no confiables, no instrucciones.
- El asistente de consulta tampoco dispone de herramientas. Solo recibe fragmentos de documentos públicos visibles y una caché allowlisted de fuentes públicas. Valida referencias, no recibe planeación privada ni Proton privado y no puede afirmar que ejecutó acciones.
- Las consultas del asistente se vinculan al hash de la sesión que las creó; otra sesión recibe 404. El consumidor elimina registros locales con más de 24 horas al recorrer la cola. La eliminación local no controla la retención del proveedor.
- El indexador del asistente limita tamaño, exige HTTPS, bloquea redirecciones a otro host y no descubre enlaces. La actualización diaria reemplaza únicamente las fuentes enumeradas en el script.
- El dictado de planeación requiere cuenta participante y CSRF, limita tamaño y frecuencia, mantiene el audio acotado en memoria y lo envía directamente al proveedor configurado; no conserva grabaciones. La transcripción vuelve al navegador como borrador editable y solo se publica al guardar la respuesta por separado.
- La planeación de desarrollo, su informe, respuestas y dictado requieren el permiso adicional de Desarrollador. La ruta no aparece en navegación, sitemap o resultados públicos para otras cuentas; el servidor verifica el permiso en cada lectura y mutación.
- La participación sin cuenta entra a una cola privada y nunca se publica directamente. Se limita por dirección, valida destino y versión y bloquea el núcleo de bases. Solo Moderadores pueden verla; descartar exige motivo. Al aprobar se publica con atribución invitada y se mantienen privados nombre de contacto, organización, teléfono y correo opcionales.
- Las imágenes comunitarias se decodifican con validación estricta de PNG/JPEG, tamaño y dimensiones, se nombran por hash y se guardan fuera del repositorio con permisos privados. La ruta pública solo acepta el patrón generado.
- La integración de mejoras con GitHub requiere permiso de Desarrollador y confirmación explícita antes de publicar título y descripción. El consumidor llama `gh` sin shell, usa marcadores idempotentes, limita tiempo y conserva el estado local si falla. Un issue cerrado no marca una mejora como implementada.
- El archivo de Proton usa una raíz allowlisted y exclusión previa por ruta, tipo y patrones sensibles. La aplicación no enumera `/my-files`, no indexa carpetas de promotores ni expone rutas internas del servidor.
- Las descargas vuelven a resolver el archivo dentro del espejo, rechazan enlaces simbólicos y no renderizan HTML o SVG arbitrario en el origen autenticado. Las vistas permitidas reciben una política de contenido aislada.

## Límites explícitos

Es un prototipo, no una auditoría de seguridad completa. La autenticación y los respaldos deben revisarse antes de abrir el registro masivo. No hay todavía segundo factor, recuperación automática, apelación de moderación, política automática de retención de contactos ni protección contra todo abuso distribuido. El proveedor perimetral aplica sus propios controles.

El consumidor temporal comparte la autenticación local del operador con Codex CLI en un servidor confiable; no debe ejecutarse desde PRs, forks o acciones de GitHub, ni montar esa autenticación en clientes. Al madurar, migrar a un modelo local o a un servicio con credenciales y límites dedicados.

## Publicación y privacidad

Los comentarios y sus nombres elegidos son públicos en el sitio, pero no se versionan en Git. Los contactos opcionales de aportaciones invitadas permanecen en la base privada y no deben copiarse al mensaje publicado, tickets ni documentación. Antes de una eventual exportación, retirada o anonimización, establecer un procedimiento que preserve el sentido del historial. No copiar consultas del asistente, colas de moderación, logs crudos ni errores con datos a incidencias públicas. Las contraseñas provisionales se entregan de una en una mediante un canal privado; borrar el listado de entrega cuando deje de ser necesario.
