# Desarrollo futuro del prototipo

Este archivo enumera trabajo pendiente. Las funciones que ya existen se describen en
README, OPERACION y SECURITY; aparecer aquí no debe usarse para declarar que una fase
está activa o ratificada.

## Registro y verificación de cuentas

- [ ] Registro automático con controles contra abuso y recuperación de acceso.
- [ ] Proceso de verificación de **un mes**, conforme a la solicitud comunitaria.
- [ ] Precisar qué acredita verificación, quién decide, fecha de inicio, mes natural
  frente a 30 días, zona horaria, avisos, prórrogas y apelación.
- [ ] Si una cuenta no logra verificarse, definir cómo archivar sus comentarios sin
  romper conversaciones ni borrar aportaciones de otras personas.
- [ ] Definir compatibilidad y transición para las cuentas administradas existentes.
- [ ] Mantener cuenta verificada, rol técnico y membresía oficial como estados distintos.

Esta fase **no está activa**. No hay temporizador que archive comentarios por edad de
cuenta. La participación invitada moderada ya permite aportar sin registro, pero no
equivale al registro automático ni al proceso de verificación mensual.

## Participación y moderación

Ya existe una cola privada para aportaciones invitadas, contactos opcionales privados,
atribución pública con nombre elegido y permisos independientes de Moderador. Falta:

- [ ] acordar política de conservación y eliminación de envíos y contactos;
- [ ] ofrecer una vía para consultar o solicitar revisión de una decisión de moderación
  sin exponer datos privados;
- [ ] definir apelación, atención de abuso distribuido y criterios comunitarios de
  moderación más allá de los controles técnicos actuales;
- [ ] evaluar anonimización o retiro de contenido publicado y su relación con el
  historial, sin borrado silencioso.

## Asistencia y fuentes

El asistente con fuentes públicas, respuestas privadas por sesión y caducidad local de
24 horas ya está implementado. La caché se actualiza manualmente y mediante un timer
diario de operación. Falta:

- [ ] probar modelos pequeños locales con el mismo contrato JSON;
- [ ] comparar fidelidad, citas, incertidumbre, español, tiempos y recursos;
- [ ] ampliar o retirar fuentes únicamente mediante revisión de la allowlist;
- [ ] definir política de conservación del proveedor externo además de la eliminación
  local de consultas;
- [ ] evaluar aislamiento, límites, versiones de modelo y respuestas extensas.

El proveedor y modelo permanecen como configuración administrativa. El asistente no
tiene herramientas ni acceso a respuestas privadas, cuentas o Proton privado.

## Trabajo comunitario

Ya existen tareas con aceptación y revisión, notificaciones, actividades,
convocatorias, comentarios y el espacio de Rolitas. Próximos pasos:

- [ ] modelar requisitos profesionales o legales por tarea sin publicar documentos
  personales;
- [ ] acordar quién puede cerrar una tarea y qué combinación de revisiones basta;
- [ ] añadir filtros por capacidad y requisitos cuando existan datos suficientes;
- [ ] enlazar tareas, actividades, convocatorias y publicaciones sin duplicar estado;
- [ ] contrastar fichas históricas antes de tratarlas como memoria oficial;
- [ ] definir archivo, licencias y flujo para arte antes de publicar una galería o kit.

## Mejoras y GitHub

La plataforma conserva propuestas locales y las sincroniza con issues mediante una cola
controlada. Falta:

- [ ] documentar y probar recuperación ante caídas prolongadas o límites de GitHub;
- [ ] decidir reapertura cuando un issue y el estado comunitario discrepan;
- [ ] mostrar la versión desplegada que verifica una mejora;
- [ ] revisar periódicamente permisos de la sesión de `gh` usada por el servicio.

## Experiencia, accesibilidad y gobernanza

- [ ] Editor visual y comparación de versiones lado a lado.
- [ ] Menciones y seguimiento de discusiones; las notificaciones actuales cubren tareas.
- [ ] Verificación formal de actas y membresías, si la comunidad acuerda un procedimiento.
- [ ] Reanclaje asistido cuando un texto se mueve; toda ambigüedad requiere revisión humana.
- [ ] Exportaciones públicas selectivas y respaldos cifrados fuera del host.
- [ ] Pruebas periódicas de restauración y continuidad.
- [ ] Evaluación de accesibilidad con personas y tecnologías de apoyo.
- [ ] Manual detallado de réplica cuando la plataforma sea estable. No se planea un
  servicio multicomunidad ni se promete una plantilla vacía.
