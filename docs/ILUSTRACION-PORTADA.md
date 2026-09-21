# Ilustración de portada

Actualizada el 21 de septiembre de 2026 con el personaje caricaturizado, la sombra de la sombrilla y el perfil del Cerro de la Silla.

- Activo publicado: `app/static/portada-pls-gpt25.webp` (1024 × 1024).
- Variante móvil: `app/static/portada-pls-gpt25-640.webp` (640 × 640).
- Original de generación: `output/imagegen/portada-pls-gpt25.png`, conservado localmente y excluido de Git.
- Modelo solicitado explícitamente y ejecutado mediante Image API: `gpt-image-2.5-sunburst`, calidad alta, una imagen de 1024 × 1024.
- Vía utilizada: CLI de la habilidad imagegen, operación `edit`, endpoint `/v1/images/edits`, con tres imágenes de referencia. Ejecución completada correctamente.
- Credencial: la misma configuración privada utilizada por la transcripción, con autorización expresa del usuario. La clave no se incluye en código, documentación, prompts ni archivos públicos.
- Resultado: personaje editorial plano inspirado en el cartel aportado, sombra proyectada de la sombrilla y reinterpretación del relieve local. Conserva la paleta crema, negro, amarillo y verde olivo.
- Optimización: WebP calidad 85, sin metadatos, con `srcset`. La ilustración se presenta completa, sin recorte.
- La imagen anterior y su procedencia permanecen en el historial del repositorio.

## Referencias

1. Collage de la portada anterior: referencia de composición, color y texturas.
2. Cartel aportado por el usuario: referencia del personaje dibujado, la ropa y la identidad visual.
3. [Cerro de la Silla, fotografía de Nathaniel C. Sheetz (Spangineer)](https://commons.wikimedia.org/wiki/File:Cerro_de_la_Silla.jpg), publicada en Wikimedia Commons bajo [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/). Consultada el 21 de septiembre de 2026 como referencia del perfil geográfico: se pidió reinterpretar la montaña, sin insertar los píxeles de la fotografía. La fotografía de referencia no se redistribuye en este repositorio.

La portada es una ilustración, no una fotografía documental ni cartografía exacta. Los derechos y atribuciones de las referencias se mantienen separados de la licencia del código.

El uso explícito de GPT Image 2.5 sigue la [guía oficial de generación de imágenes](https://developers.openai.com/api/docs/guides/image-generation), que identifica la variante Sunburst para trabajos de edición precisa.

## Prompt final

```text
Regenera la ilustración de portada de Por la Sombrita siguiendo estas tres referencias. Resultado final cuadrado 1024×1024, sin texto, de calidad editorial.

REFERENCIAS Y PRIORIDAD:
Imagen 1: el collage que actualmente usa la web. Conservar su composición general, texturas de papel rasgado, árbol, fragmentos de mapa, recorte arquitectónico, cruce peatonal y paleta. Cambiar de forma clara el personaje, la montaña y la sombra de la sombrilla.
Imagen 2: el cartel proporcionado por la comunidad. Es la referencia PRIORITARIA para el estilo del PERSONAJE. La figura del cartel es una caricatura editorial plana, dibujada con contornos negros, rostro de perfil reducido a una silueta negra sin detalle fotográfico, camisa crema, mochila negra, pantalón negro y tenis blancos. Reproducir ese lenguaje de ilustración. No copiar los titulares ni las palabras del cartel.
Imagen 3: fotografía de referencia geográfica del VERDADERO Cerro de la Silla, tomada desde Monterrey. Usarla para estudiar y respetar la forma de la cresta, no para pegar ni reutilizar los píxeles de la fotografía, el cielo o sus edificios. Dibujar la montaña de nuevo en la estética de papel olivo del collage.

CAMBIO 1, PERSONAJE CARICATURA: sustituir por completo a la persona de apariencia fotográfica de la imagen 1. Dibujar un personaje adulto caminando de perfil hacia la derecha, EXACTAMENTE en el lenguaje gráfico plano del personaje del cartel de la imagen 2: formas de ropa crema con borde negro definido, cabeza/perfil negro simplificado, pantalones y mochila negros, tenis blancos; articulaciones naturales, dos piernas completas, dos pies visibles, brazo doblado sujetando el mango. No rostro realista, no piel fotográfica, no modelo humano recortado, no render 3D, no caricatura infantil de cabeza enorme. Es una ilustración editorial adulta y serena, combinada con el fondo de collage fotográfico. La sombrilla amarilla debe cubrir al personaje y no cortarse.

CAMBIO 2, SOMBRA DE LA SOMBRILLA: mostrar MUY CLARAMENTE sobre el pavimento una sombra ancha de la copa de la sombrilla. La fuente de luz está arriba a la derecha; la sombra se proyecta hacia abajo a la izquierda, sobre el plano horizontal de la calle, junto al personaje y sus pies. Debe reconocerse como la proyección de una sombrilla: una forma ovalada amplia con borde suavemente lobulado como los gajos de la copa, en gris carbón translúcido, unida de manera coherente con la sombra fina del mástil y la sombra del personaje. Permitir ver todavía las franjas amarillas del cruce bajo la sombra. Dejar espacio despejado en el suelo para leer esta sombra: no confundirla con la sombra de ramas del árbol, no dibujar solo una sombra delgada del cuerpo, no hacer un segundo paraguas físico tirado en el suelo, no crear una mancha circular flotante. Debe verse incluso al reducir la ilustración a 320 píxeles de ancho.

CAMBIO 3, CERRO DE LA SILLA RECONOCIBLE: la montaña del fondo debe seguir fielmente la silueta de la imagen 3, vista desde Monterrey. Respetar la ladera larga y amplia de la izquierda, el pico más bajo con antena hacia la izquierda, la subida al pico triangular alto cerca del centro-derecha, la marcada depresión en forma de silla y el otro pico rocoso a su derecha, y la ladera descendente hacia el extremo derecho. Mantener relaciones de altura, anchura y separación de estos puntos. No dibujar una cordillera genérica, no usar tres picos triangulares repetidos ni un volcán cónico, no confundirla con el Cerro de las Mitras. La cresta principal debe quedar visible y reconocible detrás de la ciudad, sin estar tapada por la sombrilla o el árbol. Representación de la forma geográfica en papel texturizado verde olivo, no copia de la fotografía.

IDENTIDAD Y COMPOSICIÓN: collage editorial de papel recortado y rasgado, grano fino de impresión, tramas de semitono, tono ciudadano cálido. Solo crema #f4ecda, negro carbón #11110f, amarillo #efb713, verde olivo #5c5b2d y grises cálidos. Conservar los fragmentos de mapas urbanos, edificios en blanco y negro, árbol y cruce amarillo de la imagen 1. Árbol principalmente arriba a la izquierda; un poco de cielo crema despejado arriba a la derecha para una etiqueta HTML de la web. Mantener al personaje de cuerpo entero y la sombra de la sombrilla dentro del encuadre, con aire suficiente alrededor de los zapatos. No añadir personajes ni nuevos elementos que distraigan.

SIN LETRAS, SIN LOGOTIPOS, SIN NÚMEROS, SIN MARCAS DE AGUA, SIN ENCABEZADOS NI INTERFAZ. El texto de la página se añade fuera de la imagen. La anatomía, el estilo de caricatura, la sombra de la sombrilla y la silueta correcta del Cerro de la Silla son las cuatro comprobaciones principales.
```
