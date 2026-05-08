# markdown-fusion-compare

Herramienta de escritorio para comparar y fusionar dos notas Markdown de Obsidian. Permite copiar propiedades YAML y contenido de forma bidireccional, con previsualización de cambios antes de guardar.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![PySide6](https://img.shields.io/badge/PySide6-6.x-green) ![Version](https://img.shields.io/badge/version-0.0.1-orange)

---

## Características

### Propiedades YAML
- Visualización lado a lado de las propiedades de ambos archivos, ordenadas alfabéticamente para facilitar la comparación visual
- Las propiedades que solo existen en uno de los archivos se resaltan con borde de color
- Por cada propiedad se puede elegir entre:
  - Copiar al otro archivo (reemplaza el valor)
  - Agregar como ítem de lista (no reemplaza, suma al array)
  - Copiar convertido a WikiLink (`[[enlace]]`)
  - Convertir a WikiLink en el mismo panel
- Conversión por lote: seleccioná múltiples propiedades con checkboxes y convertí todas a WikiLink de una vez

### Cuerpo de la nota
- Pestaña dedicada con editor de texto para cada archivo
- Copia del cuerpo en dirección izquierda→derecha o derecha→izquierda
- Elección de posición: al principio o al final del archivo destino
- Deduplicación automática: no agrega líneas que ya existen en el destino
- Vista previa de las líneas nuevas antes de confirmar

### Edición y flujo de trabajo
- Edición directa en cualquiera de los dos paneles sin necesidad de cerrar la app
- Botón **Volver a comparar** para refrescar la vista después de editar manualmente
- Los cambios se simulan en memoria; no se escribe nada en disco hasta que el usuario haga clic en **Guardar**
- Soporte de argumentos por línea de comandos para abrir los dos archivos directamente al lanzar la app

### Plantillas
- Guarda un archivo `.md` con el frontmatter YAML en blanco a partir de las propiedades de ambos archivos
- Selección granular de qué propiedades incluir en la plantilla

---

## Requisitos

- Python 3.10 o superior
- PySide6

```
pip install PySide6
```

---

## Instalación

```bash
git clone https://github.com/aldomach/markdown-fusion-compare.git
cd markdown-fusion-compare
pip install -r requirements.txt
```

---

## Uso

**Interfaz gráfica:**
```bash
python obsidian_compare_0.0.1.py
```

**Abriendo archivos directamente desde la terminal:**
```bash
python obsidian_compare_0.0.1.py nota_a.md nota_b.md
```

Una vez abierta la app:

1. Usá los botones **Abrir…** o la barra de herramientas para cargar los archivos
2. Navegá por las pestañas **Propiedades YAML** y **Cuerpo** en cada panel
3. Hacé clic en `···` sobre cualquier propiedad para ver las opciones de copia
4. Cuando estés conforme con los cambios, hacé clic en **Guardar** en el panel correspondiente

---

## Estructura del proyecto

```
markdown-fusion-compare/
├── prompts/
│   └── markdown-fusion-compare-0.0.1.md   # Prompt original de generación
├── CHANGELOG.md
├── markdown-fusion-compare.py               # Aplicación principal
├── README.md
└── requirements.txt
```

---

## Changelog

Ver [CHANGELOG.md](CHANGELOG.md) para el historial de versiones y los prompts asociados a cada cambio.

---

## Licencia

MIT
