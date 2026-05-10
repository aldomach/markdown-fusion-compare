# Changelog — Obsidian Markdown Comparator

## [0.7.0] — Editor unificado + Undo corregido + Nodos mejorado

### Nuevas funciones
- **Sincronizar vista** — checkbox en la barra inferior: al cambiar
  Editar/Markdown en un panel, el otro panel espeja el mismo modo
- **Checkbox "Mostrar YAML"** en el editor de cuerpo — muestra u oculta
  el bloque frontmatter en el mismo editor (reemplaza los modos
  Cuerpo/Fuente separados)
- **Checkbox "Solo palabras completas"** en Conectar Nodos (activo por
  defecto) — cada token se valida individualmente por largo mínimo
- **`EditorToolbar`** (`ui/editor_toolbar.py`) — barra de botones
  declarativa y reutilizable; agregar un botón nuevo es una línea

### Correcciones
- **Ctrl+Z / Deshacer** corregido — el QTextEdit interno ya no maneja
  su propio historial (`setUndoRedoEnabled=False`); todas las operaciones
  (tipeo, propiedades, Conectar Nodos) pasan por `NoteFile`
- **Debounce de 800ms** — mientras el usuario tipea, el modelo se
  actualiza silenciosamente; el punto de undo se registra solo después
  de una pausa, evitando un punto por cada tecla
- **Conectar Nodos** — frases como "de la nota" ya no aparecen: `min_len`
  ahora cuenta caracteres alfanuméricos por token (sin espacios); frases
  que empiezan o terminan con stop-word son rechazadas
- **Layout duplicado** eliminado — el editor de cuerpo ya no está
  envuelto en un QTabWidget adicional; vive directamente bajo el panel
  de propiedades

### Cambios internos
- `NoteFile.set_body_silent()` — actualiza el body sin crear punto de undo
- `NoteFile.checkpoint()` — registra explícitamente un punto de undo
  (llamado por el debounce timer del editor)
- `_extract_phrases()` — validación a nivel de token, rechaza frases
  con stop-words en los extremos
- `_undo()` en `PropsPanel` delega a `BodyEditor.undo()` para mantener
  UI y modelo sincronizados

## [0.6.0] — Refactor modular + motor de nodos
### Nuevas funciones
- **Diccionario de Nodos** (`core/node_dict.py`): persistencia en `data/nodes.json` y `data/blacklist.json`
- Detección de frases **multi-palabra** (2–4 tokens) comunes entre ambos cuerpos
- Lista negra de palabras/frases que nunca se convierten a WikiLink
- Diálogo **📚 Diccionario** para gestionar nodos y lista negra (mover entre listas, limpiar)
- Menú contextual por ítem en la lista de Conectar Nodos: aceptar → dict, ignorar → blacklist
- Botón "💾 Guardar en diccionario" en el panel Conectar Nodos
- Stop-words en español e inglés con toggle "Ignorar conectores"

### Mejoras
- `apply_node_connections` reemplaza frases largas antes que palabras cortas (evita `[[[[Juan]]]] Carlos]]`)
- Resultados de búsqueda agrupados y color-codificados: 🟣 diccionario, 🔵 frases, ⚪ palabras

---

## [0.5.0] — Editor unificado + Buscar y Reemplazar
### Nuevas funciones
- **Modo de vista unificado** en el tab Cuerpo: botones 📝 Cuerpo / 🗒 Fuente / 👁 Markdown (reemplaza tres tabs separados)
- Modo **Fuente**: muestra YAML + cuerpo completo con syntax highlighting
- Modo **Markdown**: render HTML con soporte de tablas, headings, bold, italic, WikiLinks, listas, blockquotes, código
- **¶ Pilcrow**: botón para mostrar/ocultar caracteres invisibles (tabs, espacios, saltos de línea)
- **🔍 Buscar y Reemplazar** (`ui/find_replace_dialog.py`): no-modal, modos Normal / Extendido / Regex, opciones mayúsculas y palabra completa, scope todo el doc o solo selección
- **≡ Líneas**: menú con operaciones — eliminar duplicadas, eliminar duplicadas consecutivas, ordenar A→Z / Z→A (todas o selección)

### Correcciones
- Fix `AttributeError: 'body_edit'` al activar modo Markdown desde BodyEditor
- Fix tablas Markdown no renderizadas (`| col |` → `<table>`)
- Fix `setOpenExternalLinks` en QTextEdit (reemplazado por QTextBrowser)

---

## [0.4.0] — Comparación visual + Fuente + Conectar Nodos
### Nuevas funciones
- **Colores de estado** por fila de propiedad (7 estados): igual 🟢, diferente 🟡, WikiLink-diff 🔵, lista parcial 🟣, solo izquierda 🔴, solo derecha 💙, vacío ⚫
- **Zebra striping**: filas alternadas dentro de cada grupo de estado
- **Tooltip enriquecido**: muestra valor del panel actual Y del panel opuesto al pasar el mouse
- **Clic derecho en toda la fila** abre el menú contextual (no solo el botón ···)
- **🔗 Conectar Nodos**: busca palabras en común entre ambos cuerpos, lista checkeable, convierte a WikiLink en ambos paneles
- **Tab Fuente**: editor de texto plano con syntax highlighting YAML+Markdown, botón Aplicar
- **Clic derecho en cuerpo**: copiar selección al otro panel en 3 posiciones (cursor / principio / final)
- **Barra de búsqueda** en el panel de propiedades: buscar en cuerpo, agregar como propiedad, agregar a tags
- Módulo `core/compare.py` con lógica pura de comparación
- Módulo `ui/highlighter.py` compartido entre Fuente y Cuerpo

### Mejoras
- Botones ✎ y ··· movidos al lado izquierdo de cada fila

---

## [0.3.0] — Refactor modular
### Arquitectura
- Proyecto separado en módulos: `core/` (lógica pura) y `ui/` (widgets)
- `core/yaml_parser.py` — parseo y serialización de frontmatter
- `core/utils.py` — WikiLinks, timestamps, merge de cuerpo
- `core/models.py` — `NoteFile` con historial de undo (hasta 50 pasos)
- `ui/styles.py` — todo el QSS en un solo archivo (paleta Catppuccin Mocha)
- `ui/prop_row.py` — fila de propiedad individual
- `ui/props_panel.py` — panel completo con bulk bar y scroll
- `ui/dialogs.py` — diálogos de cuerpo y plantilla
- `ui/main_window.py` — ventana principal

### Nuevas funciones
- **↩ Deshacer** por panel (hasta 50 pasos)
- **Nuevo archivo** en blanco editable, se guarda solo cuando el usuario decide
- **Checkbox `updated`**: agrega/actualiza la propiedad `updated: YYYY-MM-DDTHH:MM` al guardar
- **Auto-comparar** al abrir el segundo archivo
- **Edición inline** de propiedades (doble clic o botón ✎), soporta renombrar clave y editar valor
- **Resaltado de fila** al abrir el menú ···
- **Acciones en lote** con combo desplegable (mismas opciones que menú ···)
- **Opción "Copiar vacía"** en menú y en lote
- **Eliminar propiedad** desde el menú ··· y en lote

### Correcciones
- Toolbar eliminada (duplicaba botones de los paneles)
- BottomBar compacta (altura fija 42px)

---

## [0.2.0] — Funciones principales
### Nuevas funciones
- Dos paneles verticales con propiedades YAML ordenadas alfabéticamente
- Propiedades sin par marcadas con borde rojo
- Menú contextual ··· con: copiar →/←, agregar como lista, copiar como WikiLink, convertir a WikiLink
- Conversión a WikiLink en lote para propiedades seleccionadas
- Copia bidireccional del cuerpo de la nota con deduplicación de líneas
- Selector inicio/final al copiar cuerpo
- **Guardar como plantilla**: genera `.md` con propiedades seleccionadas (con valor o vacías)
- Tab separado para editar el cuerpo de cada nota
- Barra inferior compacta con acciones globales

---

## [0.1.0] — Versión inicial
- Comparador básico de dos archivos Markdown con frontmatter YAML
- Parseo y serialización de propiedades (strings y listas)
- Apertura y guardado de archivos
- Interfaz PySide6 con tema oscuro