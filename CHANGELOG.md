# Changelog

All notable changes to this project will be documented in this file.

## [0.0.3] - 2026-05-09

### Changed (breaking)
- Proyecto refactorizado a arquitectura modular: el monolito `obsidian_compare_0.0.2.py`
  fue reemplazado por paquetes separados `core/` y `ui/`, con `main.py` como entry point

### Structure
markdown-fusion-compare/
├── core/
│   ├── init.py
│   ├── models.py        # NoteFile: modelo de datos con historial de undo
│   ├── utils.py         # Helpers puros: wikilinks, body merge, timestamps
│   └── yaml_parser.py   # Parser/serializer de frontmatter YAML
├── ui/
│   ├── init.py
│   ├── dialogs.py       # BodyCopyDialog, TemplateSaveDialog
│   ├── main_window.py   # MainWindow
│   ├── prop_row.py      # PropRow widget con edición inline
│   ├── props_panel.py   # PropsPanel con NoteFile integrado
│   └── styles.py        # QSS Catppuccin Mocha (centralizado)
└── main.py

### Added
- `NoteFile` (core/models.py): modelo de datos con pila de undo (hasta 50 estados),
  flag `dirty`, y métodos `rename_prop`, `set_prop_empty`, `convert_prop_to_wikilink`
- Undo por panel: botón "↩ Deshacer" en el header de cada panel
- Edición inline de propiedades: botón "✎" y doble clic en el valor
- Renombrado de clave desde la edición inline
- Nuevo botón "Nuevo" para crear un archivo en blanco sin abrir el selector
- Auto-comparación al cargar ambos archivos (señal `file_loaded`)
- Acción "→ Copiar vacía a otro panel" en el menú contextual y en bulk
- Bulk bar rediseñada: combo desplegable con todas las acciones + botón "Aplicar"
- Checkbox "updated" en la bulk bar: al guardar, escribe la timestamp actual en la
  propiedad `updated` del frontmatter
- Resaltado de fila activa (`RowContainerActive`) mientras el menú contextual está abierto
- `merge_body` y `new_lines_preview` extraídos a `core/utils.py`
- `now_timestamp()` en `core/utils.py` para timestamps compatibles con Obsidian
- QSS centralizado en `ui/styles.py`, aplicado a `QApplication` en lugar de `MainWindow`
- `display_value` y `value_to_str` extraídos a `core/utils.py`

### Removed
- `obsidian_compare_0.0.2.py` (monolito)
- QToolBar eliminada de `MainWindow` (las acciones viven en los paneles y la bottom bar)

## [0.0.2] - 2026-05-09

### Added
- Opción "🗑 Eliminar propiedad" en el menú contextual de cada fila de propiedades
- Botón "🗑 Eliminar sel." en la bulk bar para eliminar múltiples propiedades seleccionadas
- Botón "→ Copiar sel." en la bulk bar para copiar propiedades seleccionadas al panel opuesto
- Función helper `is_empty_value()` para detectar valores vacíos en strings y listas

### Changed
- `TemplateSaveDialog` refactorizado para usar `QTableWidget` en lugar de lista simple
- Menú contextual: "Convertir a WikiLink" ahora se oculta si el valor es vacío (usa `is_empty_value`)
- Parámetro `paired_key_exists` renombrado a `paired` en `PropRow`
- Compactación de `_show_menu`: sintaxis más concisa al agregar acciones al menú

### Removed
- Imports no utilizados eliminados: `re`, `QTimer`, `QMimeData`, `QFont`, `QColor`, `QPalette`,
  `QSyntaxHighlighter`, `QTextCharFormat`, `QFontDatabase`, `QKeySequence`, `QStatusBar`,
  `QGroupBox`, `QLineEdit`, `QIcon`

### Fixed
- Parser YAML: eliminado chequeo redundante `or val is None` en detección de valores vacíos

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