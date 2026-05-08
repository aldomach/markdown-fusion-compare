# Changelog

All notable changes to this project will be documented in this file.

## [0.0.1] - 2026-05-08

### Prompt
Ver: `prompts/markdown-fusion-compare-0.0.1.md`

### Added
- Interfaz principal con dos paneles verticales redimensionables (splitter)
- Parser YAML propio para frontmatter de Obsidian (strings, listas, listas anidadas)
- Visualización de propiedades ordenadas alfabéticamente con alineación visual entre paneles
- Resaltado de propiedades sin par en el archivo opuesto (borde rojo)
- Menú contextual por propiedad con opciones: copiar, agregar como ítem de lista, copiar como WikiLink, convertir a WikiLink
- Conversión por lote a WikiLink mediante checkboxes y botón dedicado
- Checkbox "Todo" para seleccionar/deseleccionar todas las propiedades
- Pestaña "Cuerpo" con editor de texto completo por panel
- Copia de cuerpo bidireccional con elección de posición (principio/final)
- Deduplicación automática de líneas al copiar el cuerpo
- Vista previa de líneas nuevas antes de confirmar la copia del cuerpo
- Edición directa en cualquier panel sin salir de la app
- Botón "Volver a comparar" para refrescar la vista tras edición manual
- Guardado en memoria (no escribe en disco hasta confirmar)
- Diálogo para guardar plantilla `.md` con propiedades en blanco y selección granular
- Soporte de argumentos CLI para abrir dos archivos al lanzar la app
- Barra de herramientas con acciones rápidas de apertura, guardado y comparación
- Barra de estado con mensajes de feedback por cada acción
- Tema visual oscuro completo basado en Catppuccin Mocha