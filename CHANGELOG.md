# Changelog

## [0.0.6] - 2026-05-09

### Added
- **Barra de búsqueda / extracción** encima de la lista de propiedades:
  - Campo de texto con placeholder "Buscar en cuerpo / agregar propiedad…"
  - Botón "🔍" busca el término en el cuerpo, cambia a la pestaña Cuerpo
    y posiciona el cursor en la primera coincidencia
  - Botón "+ Agregar como propiedad" crea una nueva clave YAML vacía con el texto del campo
  - Botón "+ Agregar a tags" agrega el texto como ítem de lista en la propiedad `tags`
- **Tooltip enriquecido por fila**: al pasar el cursor sobre cualquier parte de una fila
  se muestra el valor del panel propio y del panel opuesto (HTML con `<b>Izquierdo/Derecho</b>`)
- **Clic derecho en cualquier parte de la fila** abre el menú contextual
  (antes solo funcionaba en el botón `···`)
- Pestaña **Fuente** integrada en `PropsPanel` (conectada desde `props_panel.py`,
  se refresca automáticamente al seleccionarla sincronizando el cuerpo desde el editor)

### Changed
- **Botones ✎ y `···` movidos a la izquierda** del dot de estado y la clave,
  para que las acciones sean accesibles sin llegar al extremo derecho de la fila
- `rebuild_rows()` ahora recibe `other_props: dict` en lugar de `other_keys: set`,
  pasa los valores al lado opuesto para el tooltip y el estado de comparación
- `_insert_row()` recibe `status` y `other_val` y los aplica al `PropRow` inmediatamente
- `PropRow.set_other_value(other_value)`: nuevo método para inyectar el valor opuesto
  y reconstruir el tooltip
- `PropRow.refresh()` y `refresh_key()` actualizan el tooltip automáticamente
- `PropRow._update_tooltip()`: construye el tooltip HTML combinado y lo aplica
  al frame, `val_lbl` y `key_lbl`
- `_recompare()` en `MainWindow` pasa los dicts completos (`other_props`) en lugar
  de solo los conjuntos de claves
- `PropsPanel` añade `_status_map: dict[str, str]` para persistir el estado de
  comparación entre rebuilds

### Fixed
- Al cerrar el menú contextual, el highlight activo restaura el color del estado
  de comparación correctamente en todos los casos (no solo `RowContainerUnpaired`)
- `PropRow.refresh()`: eliminado `setToolTip` redundante sobre `val_lbl`
  (el tooltip ahora vive en el frame completo)

## [0.0.5] - 2026-05-09

### Added
- **Sistema de comparación semántica de propiedades** (`core/compare.py`):
  nuevo módulo puro con 7 estados de comparación por propiedad:
  - `equal` — valores idénticos en ambos paneles
  - `diff` — ambos existen pero con valores distintos
  - `wiki_diff` — mismo texto pero uno es WikiLink y el otro no
  - `list_partial` — listas con ítems parcialmente coincidentes
  - `left_only` — clave solo en el panel izquierdo
  - `right_only` — clave solo en el panel derecho
  - `empty_diff` — uno o ambos lados están vacíos
- **Dot de estado por fila**: cada `PropRow` muestra un círculo "●" coloreado
  con tooltip explicativo según el estado de comparación
- **Colores de fondo por estado** en `ui/styles.py`: cada estado tiene su propio
  `QFrame#Row<Status>` con color de borde izquierdo y fondo diferenciado (Catppuccin)
- **Vista Fuente** (`ui/source_view.py`): nueva pestaña "Fuente" en cada panel
  con editor de texto completo del archivo (YAML + cuerpo):
  - Syntax highlighting propio (`_MdHighlighter`): claves YAML, valores, listas,
    encabezados Markdown, WikiLinks y negrita
  - Botón "✔ Aplicar cambios" re-parsea el contenido y actualiza el modelo y los paneles
  - Se recarga automáticamente al cambiar a esta pestaña

### Changed
- `PropRow.set_status(status)`: nuevo método público para aplicar el estado de
  comparación desde `PropsPanel.rebuild_rows()`
- `PropRow._set_active_style()`: al cerrar el menú contextual restaura el color
  del estado de comparación en lugar del color base genérico
- `PropRow._apply_container_name()`: reemplaza `_set_base_style()`, reutilizado
  por `set_status()` y el highlight activo
- Menú contextual de `PropRow`: refactorizado con función `add()` local, más legible
- `ui/styles.py`: QSS ampliado con estilos para `SearchBar`, `SearchEdit`,
  `SourceEdit`, `SourceApplyBtn`, `SourceInfoLabel` y la leyenda de dots de estado

## [0.0.4] - 2026-05-09

### Added
- **Conectar Nodos**: nueva funcionalidad para enlazar palabras en común entre ambos cuerpos
  - Busca palabras que aparecen en los dos paneles, filtrando stop-words (español + inglés)
    y palabras ya convertidas a WikiLink
  - Spinner de longitud mínima (default: 4 caracteres, rango: 2–50)
  - Lista de resultados con checkboxes para selección granular
  - Botón "Sel. todo" para marcar todas las coincidencias
  - Botón "🔗 Convertir seleccionadas a WikiLink en ambos paneles" aplica el reemplazo
    en ambos cuerpos simultáneamente (case-insensitive, respeta puntuación circundante)
  - Panel colapsable con botón toggle "🔗 Conectar Nodos ▸/▾" en cada pestaña Cuerpo
- **Copiar selección al otro panel**: menú contextual en el editor de cuerpo
  (clic derecho sobre texto seleccionado) con opción "→/← Copiar selección al panel derecho/izquierdo"
  — agrega el fragmento al final del panel destino si no existe ya
- Nuevo archivo `ui/body_editor.py`: widget `BodyEditor` que encapsula el editor de
  texto + panel Conectar Nodos; `PropsPanel.body_edit` sigue apuntando al `QTextEdit` interno
  para compatibilidad con el resto del código

### Changed
- `PropsPanel._build_body_tab()` ahora devuelve un `BodyEditor` en lugar de un `QWidget` plano
- `MainWindow` expone `find_common_words(min_len)` y `apply_node_connections(words)`
  como métodos públicos (llamados desde `BodyEditor`)

### Added (core)
- `core/utils.py`: funciones `tokenise_body`, `find_common_words`, `apply_wikilinks_to_body`
- `_STOP_WO

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