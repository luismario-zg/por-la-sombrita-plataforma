# Mapa de contenido para la evolución comunitaria

Preparado el 21 de septiembre de 2026. Los documentos son **borradores para
revisión**, con autoría declarada como «Codex con guía de Luis Mario y conocimiento
comunitario al 20 de septiembre de 2026». No contienen respuestas literales de la
planeación ni convierten una respuesta individual en ratificación comunitaria.

## Entregables

| Archivo | Ruta prevista | Propósito |
|---|---|---|
| `contenido/evolucion/directrices.html` | `/directrices.html` | Fichas de principio, intención, ejemplo, alcance y estado, precedidas por el aviso para interpretar el espíritu sin alterar texto ni decisiones. |
| `contenido/evolucion/conocimiento.html` | `/conocimiento.html` | Entrada única dividida en **Comunidades Abiertas** y **Comunidad PLS**, con historia, fuentes, archivo público y estado técnico documentado. |
| `contenido/evolucion/manual.html` | `/manual.html` | Versión ampliada del manual. Conserva anclas históricas y añade decisiones, conflictos, convivencia, horizontalidad, comités, redes, arte, estándares y réplica. |
| `scripts/importar_evolucion.py` | Operación local | Valida, muestra cambios y, solo con opciones explícitas, crea nuevas revisiones o documentos. Puede crear el hilo autorizado de D07 y emitir el seed D14. |

La aplicación ya resuelve cualquier documento visible mediante `/<slug>.html`; por
eso el importador no necesita una ruta especial. La navegación de la plataforma ya
incluye Asistente y el grupo Participar con Trabajo, Actividades, Convocatorias,
Rolitas, Mejoras y la cola de moderación cuando corresponde. La incorporación de
Directrices y Conocimiento al menú y a metadatos públicos se coordina con la entrega de
navegación/SEO; no requiere cambiar estos borradores.

## Trazabilidad de decisiones

| Decisión | Salida preparada | Estado conservado |
|---|---|---|
| D03 | `directrices.html`, aviso y fichas | Primera versión propuesta; interpretación humana sin veto interpretativo unilateral. |
| D04 | `conocimiento.html` con dos ramas | Estructura aceptada para preparar; mantenimiento manual y responsables aún por aceptar. |
| D05 | Autoría declarada, versiones y pendientes editoriales | Los permisos independientes de Editor ya existen; el contenido protegido exige además administración. La convocatoria editorial sigue pendiente de operación. |
| D06 | Capítulos de decisiones y conflictos en el manual | Base para cuestionar, discutir y adaptar; reglas de voto siguen abiertas. |
| D07 | Capítulo de redes marcado como asunto abierto | El script ofrece crear el hilo autorizado de Luis Mario; no aprueba la orientación. |
| D08 | Criterios mínimos, motivo cuando no se publica pronto y falta de capacidad visible | Moderador y Editor ya son permisos independientes; constituir el comité y aceptar responsabilidades sigue siendo una decisión comunitaria. |
| D09 | Revisión proporcional, categorías y obligación de motivar una negativa | No se publican acusaciones sobre organizaciones. Reforestación Extrema aparece solo como asunto que exige cotejo y votación. |
| D10 | Convivencia, escucha, desacuerdo y reparación | Propuesta basada en fuentes públicas verificadas; no código de conducta ratificado. |
| D13 | Arte y memoria visual en el capítulo de redes | No se afirma que existan galería, destacada o permisos sobre piezas. |
| D14 | Seed coordinado del evento y obligaciones de contraste | El módulo de Actividades ya admite evento/dinámica, estado e información faltante; importar el seed y completar la ficha sigue siendo operación revisable. |
| D17 | Réplica visual con verificación pieza por pieza | Sin respuesta registrada; licencias y kit permanecen pendientes. |
| D18 | Estándares para materiales, actividades y proyectos, no para personas | El único ejemplo concreto es Instagram y sigue como formulación de trabajo. |
| D21 | Fork/adaptación autogestionada y manual posterior | No habrá servicio multicomunidad ni obligación de plantilla vacía en este alcance; manual detallado queda pendiente. |
| D23 | Trabajo paralelo, responsabilidades aceptadas y revisión distribuida | Trabajo ya distingue propuesta, aceptación, plazo, entrega y revisión; no asigna compromisos sin respuesta. |

## Conservación de anclas del manual

La importación exige conservar todas estas anclas de la versión anterior:

- `manual-de-operaciones-de-la-comunidad`
- `un-proyecto-abierto-una-responsabilidad-compartida`
- `funciones-y-relevos`
- `antes-durante-y-después-de-una-sesión`
- `decidir-sin-convertir-propuestas-en-acuerdos`
- `gestionar-tareas-y-disponibilidad`
- `investigación-y-publicación-permanente`
- `incorporación-permanencia-y-salida`
- `territorio-cuidados-e-intervención`
- `alianzas-recursos-y-cuentas`
- `documentación-pública-y-resguardo-privado`
- `revisión-del-manual`

Antes de escribir, el script compara las anclas H2 de la versión viva con el borrador.
Si la base contiene una sección que el borrador desconoce, aborta para evitar que una
edición concurrente desaparezca. Los hilos conservan su versión y snapshot originales.

## Hilo autorizado D07

Con `--crear-hilo-d07`, la importación abre una sola discusión, de forma idempotente,
sobre la cita del capítulo `redes-sociales-autonomia-y-publicacion`. La cuenta autora
debe existir y estar activa; el valor predeterminado es `luismario`. El texto autorizado
se lee desde el archivo indicado con `--comentario-d07`; ese archivo debe permanecer
fuera del repositorio y no se copia a esta documentación. El hilo queda abierto y no
aprueba la redacción.

No se crea el hilo si ya existe otro con el título estable definido en el script. La
opción no se puede usar fuera de una importación `--apply` ni sin el archivo privado.

## Seed D14 coordinado

El script conserva este objeto y lo imprime con `--imprimir-seed-d14`. No intenta crear
tablas de actividades; el agente operativo lo integrará al modelo correspondiente.

```json
{
  "activity_type": "evento",
  "title": "Actividad del 15 de septiembre",
  "description": "Actividad relatada como realizada fuera de LABNL con señalética y volantes de Por la Sombrita. La descripción detallada y sus resultados requieren contraste.",
  "starts_at": null,
  "ends_at": null,
  "location": "Fuera de LABNL",
  "status": "completed",
  "pending_details": [
    "Confirmar año y horario exacto; la fuente solo refiere el 15 de septiembre por la noche.",
    "Confirmar nombre definitivo y lugar exacto.",
    "Completar descripción, personas participantes autorizadas y evidencia.",
    "Contrastar resultados y aprendizaje antes de publicarlos como conclusión comunitaria."
  ],
  "source_reference": "A11 01:07–02:06; respuesta de planeación D14 del 21-sep-2026."
}
```

## Fuentes públicas verificadas

Se comprobaron por HTTPS el 21 de septiembre de 2026:

- [Guía para Comunidades LABNL](https://wiki.labnuevoleon.mx/index.php?title=Gu%C3%ADa_para_Comunidades_LABNL): roles, autonomía, acompañamiento y documentación.
- [W3C Process Document — Consensus](https://www.w3.org/policies/process/#Consensus): consenso, disenso y objeciones registradas.
- [RFC 7282 — On Consensus and Humming in the IETF](https://www.rfc-editor.org/rfc/rfc7282.html): atención a objeciones sustantivas sin reducir consenso a mayoría simple.
- [Mozilla Community Participation Guidelines](https://www.mozilla.org/en-US/about/governance/policies/participation/): conducta, reporte y aplicación proporcional.
- [Open Source Guides — Building Welcoming Communities](https://opensource.guide/building-community/): incorporación, expectativas y distribución de responsabilidades.
- [Creative Commons licenses](https://creativecommons.org/cc-licenses/): opciones explícitas de licencia para obras; no asignan licencia automáticamente a materiales existentes.

Estas fuentes apoyan propuestas y preguntas. No se presentan como reglamentos ya
adoptados por Por la Sombrita.

## Uso seguro del importador

Validar los HTML sin abrir una base:

```bash
.venv/bin/python scripts/importar_evolucion.py
```

Mostrar el seed D14:

```bash
.venv/bin/python scripts/importar_evolucion.py --imprimir-seed-d14
```

Comparar contra una copia de la base, sin escribir:

```bash
.venv/bin/python scripts/importar_evolucion.py --database /ruta/a/copia.sqlite3
```

Después de preparar y verificar un respaldo, importar y abrir el hilo D07:

```bash
.venv/bin/python scripts/importar_evolucion.py \
  --database /ruta/explicita/plataforma.sqlite3 \
  --apply --backup-confirmed --crear-hilo-d07 --autor-d07 luismario \
  --comentario-d07 /ruta/privada/mensaje-d07.txt
```

Crear `mensaje-d07.txt` fuera del repositorio, limitar sus permisos y retirarlo cuando
ya no sea necesario. El importador valida que contenga texto, pero no lo registra en
Git ni lo incluye en los borradores.

El script:

1. limpia HTML con las mismas reglas de la aplicación;
2. valida metadatos, secciones y anclas;
3. aborta si encuentra una versión oficial distinta o anclas vivas no reconciliadas;
4. crea documentos nuevos como `proposal` o incrementa la versión existente;
5. añade una fila de revisión y conserva versiones, hilos y mensajes anteriores;
6. no marca documentos oficiales, no ratifica decisiones y no toca cuentas;
7. no crea el hilo D07 dos veces.

## Capacidades relacionadas ya implementadas

- **Asistente:** usa documentos públicos vigentes y caché allowlisted de fuentes
  públicas; consultas privadas por sesión, eliminación local a las 24 horas, referencias
  validadas y ejecución sin herramientas. El indexador puede ejecutarse manualmente y
  mediante el timer diario de operación.
- **Participación invitada:** recibe aportaciones sin cuenta, conserva contactos
  opcionales en privado y exige moderación previa; descartar requiere motivo.
- **Permisos:** Editor, Moderador y Desarrollador son independientes del rol y la
  membresía. El núcleo de bases/directrices conserva la restricción administrativa.
- **Operación comunitaria:** Trabajo, Actividades, Convocatorias y Rolitas tienen rutas y
  datos propios. Las tareas registran aceptación, entrega, revisión y notificaciones.
- **Mejoras:** el seguimiento local se vincula con GitHub por cola; un cierre remoto se
  lleva a revisión y no acredita despliegue.

Estas capacidades no ratifican las directrices de los borradores ni completan el estado
del arte, las licencias de recursos, los comités o la verificación mensual de cuentas.

## Obligaciones que no caben en este alcance

- Importar Directrices, Conocimiento y el Manual, abrir el hilo D07 e incorporar el seed
  D14 son operaciones explícitas: requieren respaldo y ejecución separada.
- Directrices y Conocimiento deben incorporarse a navegación/SEO al publicar; Trabajo,
  Actividades, Convocatorias, Rolitas, Mejoras y Asistente ya tienen navegación propia.
- Editor y Moderador ya son permisos independientes y el núcleo documental está
  protegido. Crear comités, integrantes, facultades y relevos todavía requiere acuerdo
  y aceptación sin inventar membresía.
- Tareas, actividades y convocatorias ya tienen datos estructurados; todavía falta
  enlazar su operación con políticas ratificadas de comités, estándares y publicación.
- Publicar la destacada de arte requiere piezas, derechos y una persona con acceso al
  canal; no se inventaron hechos ni permisos.
- El kit gráfico D17 requiere inventario y comprobación de licencias.
- La investigación de sombra y comunidades abiertas necesita mantenimiento continuo;
  crear la página no completa el estado del arte.
- La réplica D21 necesita instrucciones detalladas cuando la plataforma sea más estable;
  no se construyó un servicio multicomunidad.
- El registro automático y la verificación de un mes siguen pendientes. La participación
  invitada moderada no los sustituye y las cuentas existentes requieren una transición
  compatible antes de activar plazos.
- Cambios de dominio, DNS, alojamiento o producción requieren autorización y plan de
  continuidad separados.
