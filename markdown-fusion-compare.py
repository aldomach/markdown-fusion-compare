#!/usr/bin/env python3
"""
Obsidian Markdown Comparator
Compares two Obsidian markdown files, allows copying YAML properties
bidirectionally, editing content, and saving as templates.
"""

import sys
import re
import os
import copy
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QSplitter, QScrollArea,
    QFrame, QTextEdit, QDialog, QDialogButtonBox, QCheckBox,
    QMessageBox, QMenu, QToolBar, QStatusBar, QGroupBox,
    QSizePolicy, QLineEdit, QComboBox, QTabWidget, QListWidget,
    QListWidgetItem, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal, QSize, QTimer, QMimeData
from PySide6.QtGui import (
    QFont, QColor, QPalette, QAction, QIcon, QTextCharFormat,
    QSyntaxHighlighter, QTextDocument, QFontDatabase, QCursor,
    QKeySequence
)


# ─── YAML Parser ──────────────────────────────────────────────────────────────

def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown. Returns (props_dict, body)."""
    props = {}
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            yaml_block = text[3:end].strip()
            body = text[end + 4:].lstrip("\n")
            props = parse_yaml_simple(yaml_block)
    return props, body


def parse_yaml_simple(yaml_text: str) -> dict:
    """Simple YAML parser that handles strings, lists, and nested lists."""
    result = {}
    lines = yaml_text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue
        if ":" in line and not line.startswith(" ") and not line.startswith("-"):
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            if val == "" or val is None:
                # Possibly a list follows
                items = []
                i += 1
                while i < len(lines) and lines[i].startswith("  ") or (i < len(lines) and lines[i].startswith("- ")):
                    item_line = lines[i].strip()
                    if item_line.startswith("- "):
                        items.append(item_line[2:].strip())
                    i += 1
                result[key] = items if items else ""
                continue
            else:
                result[key] = val
        i += 1
    return result


def serialize_frontmatter(props: dict, body: str) -> str:
    """Serialize properties and body back to markdown."""
    if not props and not body.strip():
        return ""
    lines = ["---"]
    for key, val in props.items():
        if isinstance(val, list):
            lines.append(f"{key}:")
            for item in val:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{key}: {val}")
    lines.append("---")
    if body.strip():
        lines.append("")
        lines.append(body.rstrip())
    return "\n".join(lines) + "\n"


def to_wikilink(value: str) -> str:
    """Convert a value to wikilink format."""
    val = value.strip().strip('"').strip("'")
    # Remove existing wikilink brackets if present
    val = val.strip("[]")
    return f'[[{val}]]'


def is_wikilink(value: str) -> bool:
    return value.strip().startswith("[[") and value.strip().endswith("]]")


def body_lines_set(body: str) -> set:
    """Return non-empty lines of body as a set for dedup."""
    return set(l.rstrip() for l in body.splitlines() if l.strip())


# ─── Property Row Widget ───────────────────────────────────────────────────────

class PropRow(QFrame):
    """A row showing one property (key + value) with action buttons."""

    action_requested = Signal(str, str, object)  # action, side, row_widget

    def __init__(self, key: str, value, side: str, paired_key_exists: bool = True, parent=None):
        super().__init__(parent)
        self.key = key
        self.value = value
        self.side = side  # 'left' or 'right'
        self.paired_key_exists = paired_key_exists
        self._build_ui()

    def _build_ui(self):
        self.setObjectName("PropRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(6)

        # Key label
        self.key_lbl = QLabel(self.key)
        self.key_lbl.setFixedWidth(130)
        self.key_lbl.setObjectName("PropKey")
        self.key_lbl.setToolTip(self.key)
        layout.addWidget(self.key_lbl)

        # Value label
        display_val = self._display_value(self.value)
        self.val_lbl = QLabel(display_val)
        self.val_lbl.setObjectName("PropVal")
        self.val_lbl.setToolTip(display_val)
        self.val_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self.val_lbl)

        # Action button (▶ or ◀)
        self.btn = QPushButton("···")
        self.btn.setObjectName("PropBtn")
        self.btn.setFixedSize(28, 24)
        self.btn.clicked.connect(self._show_menu)
        layout.addWidget(self.btn)

    def _display_value(self, val) -> str:
        if isinstance(val, list):
            if not val:
                return "(lista vacía)"
            return " | ".join(str(v) for v in val[:4]) + (" …" if len(val) > 4 else "")
        return str(val) if val != "" else "(vacío)"

    def refresh(self, value):
        self.value = value
        display_val = self._display_value(value)
        self.val_lbl.setText(display_val)
        self.val_lbl.setToolTip(display_val)

    def _show_menu(self):
        menu = QMenu(self)
        menu.setObjectName("PropMenu")

        other = "derecha" if self.side == "left" else "izquierda"
        arrow = "→" if self.side == "left" else "←"

        a_copy = menu.addAction(f"{arrow} Copiar a {other}")
        a_copy.triggered.connect(lambda: self.action_requested.emit("copy", self.side, self))

        a_add = menu.addAction(f"{arrow} Agregar como ítem de lista a {other}")
        a_add.triggered.connect(lambda: self.action_requested.emit("add_list", self.side, self))

        menu.addSeparator()

        a_wiki = menu.addAction(f"{arrow} Copiar como WikiLink a {other}")
        a_wiki.triggered.connect(lambda: self.action_requested.emit("copy_wiki", self.side, self))

        if not is_wikilink(str(self.value)):
            a_conv = menu.addAction("⟳ Convertir a WikiLink (aquí)")
            a_conv.triggered.connect(lambda: self.action_requested.emit("convert_wiki", self.side, self))

        menu.exec(QCursor.pos())


# ─── Properties Panel ──────────────────────────────────────────────────────────

class PropsPanel(QWidget):
    """Panel that shows file path, YAML properties, and body editor."""

    def __init__(self, side: str, parent=None):
        super().__init__(parent)
        self.side = side
        self.filepath: Optional[str] = None
        self.props: dict = {}
        self.body: str = ""
        self.prop_rows: dict[str, PropRow] = {}  # key -> PropRow
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header bar
        header = QFrame()
        header.setObjectName("PanelHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 8, 10, 8)

        title = "📄 Archivo Izquierdo" if self.side == "left" else "📄 Archivo Derecho"
        self.title_lbl = QLabel(title)
        self.title_lbl.setObjectName("PanelTitle")
        header_layout.addWidget(self.title_lbl)
        header_layout.addStretch()

        self.open_btn = QPushButton("Abrir…")
        self.open_btn.setObjectName("OpenBtn")
        self.open_btn.clicked.connect(self.open_file)
        header_layout.addWidget(self.open_btn)

        self.save_btn = QPushButton("Guardar")
        self.save_btn.setObjectName("SaveBtn")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save_file)
        header_layout.addWidget(self.save_btn)

        layout.addWidget(header)

        # ── File path label
        self.path_lbl = QLabel("Sin archivo")
        self.path_lbl.setObjectName("PathLabel")
        self.path_lbl.setContentsMargins(10, 4, 10, 4)
        layout.addWidget(self.path_lbl)

        # ── Tabs: Props / Body
        self.tabs = QTabWidget()
        self.tabs.setObjectName("PanelTabs")
        layout.addWidget(self.tabs)

        # Props tab
        props_tab = QWidget()
        props_layout = QVBoxLayout(props_tab)
        props_layout.setContentsMargins(0, 0, 0, 0)
        props_layout.setSpacing(0)

        # Toolbar for bulk actions
        bulk_bar = QFrame()
        bulk_bar.setObjectName("BulkBar")
        bulk_layout = QHBoxLayout(bulk_bar)
        bulk_layout.setContentsMargins(8, 4, 8, 4)
        bulk_layout.setSpacing(6)

        self.select_all_cb = QCheckBox("Todo")
        self.select_all_cb.stateChanged.connect(self._toggle_all)
        bulk_layout.addWidget(self.select_all_cb)

        self.bulk_wiki_btn = QPushButton("⟳ WikiLink seleccionados")
        self.bulk_wiki_btn.setObjectName("BulkBtn")
        self.bulk_wiki_btn.clicked.connect(self._bulk_to_wikilink)
        bulk_layout.addWidget(self.bulk_wiki_btn)

        bulk_layout.addStretch()
        props_layout.addWidget(bulk_bar)

        # Scroll area for property rows
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setObjectName("PropsScroll")

        self.props_container = QWidget()
        self.props_layout = QVBoxLayout(self.props_container)
        self.props_layout.setContentsMargins(0, 0, 0, 0)
        self.props_layout.setSpacing(1)
        self.props_layout.addStretch()

        self.scroll.setWidget(self.props_container)
        props_layout.addWidget(self.scroll)

        self.tabs.addTab(props_tab, "Propiedades YAML")

        # Body tab
        body_tab = QWidget()
        body_layout = QVBoxLayout(body_tab)
        body_layout.setContentsMargins(6, 6, 6, 6)

        self.body_edit = QTextEdit()
        self.body_edit.setObjectName("BodyEdit")
        self.body_edit.setPlaceholderText("Cuerpo de la nota…")
        body_layout.addWidget(self.body_edit)

        self.tabs.addTab(body_tab, "Cuerpo")

        # ── Checkboxes for rows (kept in dict)
        self.row_checks: dict[str, QCheckBox] = {}

    # ── File I/O ────────────────────────────────────────────────────────────

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir archivo Markdown", "", "Markdown (*.md);;Todos (*)"
        )
        if path:
            self.load_file(path)

    def load_file(self, path: str):
        self.filepath = path
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.props, self.body = parse_frontmatter(content)
        self.path_lbl.setText(Path(path).name)
        self.path_lbl.setToolTip(path)
        self.body_edit.setPlainText(self.body)
        self.save_btn.setEnabled(True)
        self.rebuild_rows()

    def save_file(self):
        if not self.filepath:
            path, _ = QFileDialog.getSaveFileName(
                self, "Guardar", "", "Markdown (*.md)"
            )
            if not path:
                return
            self.filepath = path
        # Sync body from editor
        self.body = self.body_edit.toPlainText()
        content = serialize_frontmatter(self.props, self.body)
        with open(self.filepath, "w", encoding="utf-8") as f:
            f.write(content)
        QMessageBox.information(self, "Guardado", f"Archivo guardado:\n{self.filepath}")

    def get_content(self) -> str:
        self.body = self.body_edit.toPlainText()
        return serialize_frontmatter(self.props, self.body)

    # ── Row management ──────────────────────────────────────────────────────

    def rebuild_rows(self, other_keys: set = None):
        """Rebuild property rows sorted alphabetically."""
        # Clear existing
        while self.props_layout.count() > 1:
            item = self.props_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.prop_rows.clear()
        self.row_checks.clear()

        sorted_keys = sorted(self.props.keys(), key=str.lower)

        for key in sorted_keys:
            val = self.props[key]
            paired = (other_keys is None) or (key in other_keys)
            self._add_row(key, val, paired)

        self.props_layout.update()

    def _add_row(self, key: str, val, paired: bool = True):
        container = QFrame()
        container.setObjectName("RowContainer")
        row_layout = QHBoxLayout(container)
        row_layout.setContentsMargins(4, 0, 4, 0)
        row_layout.setSpacing(4)

        cb = QCheckBox()
        cb.setFixedWidth(20)
        row_layout.addWidget(cb)
        self.row_checks[key] = cb

        row = PropRow(key, val, self.side, paired)
        row.action_requested.connect(self._on_action)
        row_layout.addWidget(row)

        if not paired:
            container.setObjectName("RowContainerUnpaired")

        # Insert before the stretch
        self.props_layout.insertWidget(self.props_layout.count() - 1, container)
        self.prop_rows[key] = row

    def set_prop(self, key: str, value):
        """Set or update a property."""
        self.props[key] = value
        if key in self.prop_rows:
            self.prop_rows[key].refresh(value)
        else:
            self._add_row(key, value)

    def add_to_list_prop(self, key: str, value):
        """Add value to a list property (or convert to list)."""
        current = self.props.get(key, [])
        if isinstance(current, list):
            if value not in current:
                current.append(value)
        else:
            if current == "":
                current = [value]
            else:
                current = [current, value] if current != value else [current]
        self.props[key] = current
        if key in self.prop_rows:
            self.prop_rows[key].refresh(current)
        else:
            self._add_row(key, current)

    def convert_to_wikilink(self, key: str):
        """Convert property value(s) to wikilink format."""
        val = self.props.get(key)
        if val is None:
            return
        if isinstance(val, list):
            self.props[key] = [
                to_wikilink(v) if not is_wikilink(v) else v for v in val
            ]
        else:
            if not is_wikilink(str(val)):
                self.props[key] = to_wikilink(str(val))
        if key in self.prop_rows:
            self.prop_rows[key].refresh(self.props[key])

    def _toggle_all(self, state):
        for cb in self.row_checks.values():
            cb.setChecked(bool(state))

    def _bulk_to_wikilink(self):
        for key, cb in self.row_checks.items():
            if cb.isChecked():
                self.convert_to_wikilink(key)

    def get_selected_keys(self) -> list[str]:
        return [k for k, cb in self.row_checks.items() if cb.isChecked()]

    def _on_action(self, action: str, side: str, row: PropRow):
        """Forward action to main window via parent chain."""
        w = self
        while w and not isinstance(w, MainWindow):
            w = w.parent()
        if w:
            w.handle_prop_action(action, side, row)


# ─── Body Copy Dialog ──────────────────────────────────────────────────────────

class BodyCopyDialog(QDialog):
    def __init__(self, src_body: str, dst_body: str, direction: str, parent=None):
        super().__init__(parent)
        self.src_body = src_body
        self.dst_body = dst_body
        self.direction = direction
        self.setWindowTitle("Copiar cuerpo de la nota")
        self.setMinimumWidth(500)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)

        info = QLabel(f"Copiar cuerpo {self.direction}")
        info.setObjectName("DialogInfo")
        layout.addWidget(info)

        self.pos_combo = QComboBox()
        self.pos_combo.addItems(["Al final del archivo destino", "Al principio del archivo destino"])
        layout.addWidget(self.pos_combo)

        # Preview of lines to add (dedup)
        dst_set = body_lines_set(self.dst_body)
        src_lines = [l for l in self.src_body.splitlines() if l.strip() and l.rstrip() not in dst_set]
        
        preview_lbl = QLabel(f"Líneas nuevas a agregar ({len(src_lines)}):")
        layout.addWidget(preview_lbl)

        self.preview = QTextEdit()
        self.preview.setPlainText("\n".join(src_lines))
        self.preview.setReadOnly(True)
        self.preview.setMaximumHeight(200)
        layout.addWidget(self.preview)

        self.new_lines = src_lines

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_position(self) -> str:
        return "end" if self.pos_combo.currentIndex() == 0 else "start"


# ─── Template Save Dialog ──────────────────────────────────────────────────────

class TemplateSaveDialog(QDialog):
    def __init__(self, all_keys: set, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Guardar como plantilla")
        self.setMinimumWidth(400)
        self.all_keys = sorted(all_keys, key=str.lower)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Selecciona las propiedades a incluir en la plantilla:"))

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.MultiSelection)
        for key in self.all_keys:
            item = QListWidgetItem(key)
            item.setCheckState(Qt.Checked)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_selected_keys(self) -> list[str]:
        result = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.Checked:
                result.append(item.text())
        return result


# ─── Main Window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Obsidian Markdown Comparator")
        self.setMinimumSize(1100, 750)
        self._apply_styles()
        self._build_ui()
        self._build_toolbar()
        self.statusBar().showMessage("Abre dos archivos Markdown para comenzar.")

    # ── UI Build ────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Splitter with two panels
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setObjectName("MainSplitter")
        self.splitter.setHandleWidth(6)

        self.left_panel = PropsPanel("left", self)
        self.right_panel = PropsPanel("right", self)

        self.splitter.addWidget(self.left_panel)
        self.splitter.addWidget(self.right_panel)
        self.splitter.setSizes([500, 500])

        main_layout.addWidget(self.splitter)

        # Bottom action bar
        bottom = QFrame()
        bottom.setObjectName("BottomBar")
        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(12, 8, 12, 8)
        bottom_layout.setSpacing(10)

        # Body copy buttons
        body_lbl = QLabel("Cuerpo:")
        body_lbl.setObjectName("BarLabel")
        bottom_layout.addWidget(body_lbl)

        self.copy_body_lr = QPushButton("Cuerpo → Derecha")
        self.copy_body_lr.setObjectName("BodyBtn")
        self.copy_body_lr.clicked.connect(lambda: self._copy_body("left", "right"))
        bottom_layout.addWidget(self.copy_body_lr)

        self.copy_body_rl = QPushButton("Cuerpo ← Izquierda")
        self.copy_body_rl.setObjectName("BodyBtn")
        self.copy_body_rl.clicked.connect(lambda: self._copy_body("right", "left"))
        bottom_layout.addWidget(self.copy_body_rl)

        bottom_layout.addStretch()

        self.recompare_btn = QPushButton("🔄 Volver a comparar")
        self.recompare_btn.setObjectName("RecompareBtn")
        self.recompare_btn.clicked.connect(self._recompare)
        bottom_layout.addWidget(self.recompare_btn)

        self.template_btn = QPushButton("💾 Guardar plantilla")
        self.template_btn.setObjectName("TemplateBtn")
        self.template_btn.clicked.connect(self._save_template)
        bottom_layout.addWidget(self.template_btn)

        main_layout.addWidget(bottom)

    def _build_toolbar(self):
        tb = QToolBar("Principal")
        tb.setMovable(False)
        tb.setObjectName("MainToolbar")
        tb.setIconSize(QSize(16, 16))
        self.addToolBar(tb)

        act_open_l = QAction("📂 Abrir izquierdo", self)
        act_open_l.triggered.connect(self.left_panel.open_file)
        tb.addAction(act_open_l)

        act_open_r = QAction("📂 Abrir derecho", self)
        act_open_r.triggered.connect(self.right_panel.open_file)
        tb.addAction(act_open_r)

        tb.addSeparator()

        act_save_l = QAction("💾 Guardar izquierdo", self)
        act_save_l.triggered.connect(self.left_panel.save_file)
        tb.addAction(act_save_l)

        act_save_r = QAction("💾 Guardar derecho", self)
        act_save_r.triggered.connect(self.right_panel.save_file)
        tb.addAction(act_save_r)

        tb.addSeparator()

        act_recompare = QAction("🔄 Comparar", self)
        act_recompare.triggered.connect(self._recompare)
        tb.addAction(act_recompare)

        tb.addSeparator()

        act_template = QAction("📋 Plantilla", self)
        act_template.triggered.connect(self._save_template)
        tb.addAction(act_template)

    # ── Actions ─────────────────────────────────────────────────────────────

    def handle_prop_action(self, action: str, side: str, row: PropRow):
        """Handle actions from property rows."""
        key = row.key
        value = row.value

        if side == "left":
            src_panel = self.left_panel
            dst_panel = self.right_panel
        else:
            src_panel = self.right_panel
            dst_panel = self.left_panel

        if action == "copy":
            dst_panel.set_prop(key, copy.deepcopy(value))
            self.statusBar().showMessage(f"Propiedad '{key}' copiada.")

        elif action == "add_list":
            if isinstance(value, list):
                for v in value:
                    dst_panel.add_to_list_prop(key, v)
            else:
                dst_panel.add_to_list_prop(key, value)
            self.statusBar().showMessage(f"Propiedad '{key}' agregada como ítem de lista.")

        elif action == "copy_wiki":
            if isinstance(value, list):
                wiki_val = [to_wikilink(v) if not is_wikilink(v) else v for v in value]
            else:
                wiki_val = to_wikilink(str(value)) if not is_wikilink(str(value)) else str(value)
            dst_panel.set_prop(key, wiki_val)
            self.statusBar().showMessage(f"Propiedad '{key}' copiada como WikiLink.")

        elif action == "convert_wiki":
            src_panel.convert_to_wikilink(key)
            self.statusBar().showMessage(f"Propiedad '{key}' convertida a WikiLink.")

        self._recompare(silent=True)

    def _copy_body(self, src_side: str, dst_side: str):
        src_panel = self.left_panel if src_side == "left" else self.right_panel
        dst_panel = self.right_panel if dst_side == "right" else self.left_panel

        src_body = src_panel.body_edit.toPlainText()
        dst_body = dst_panel.body_edit.toPlainText()

        direction = "→ Derecha" if dst_side == "right" else "← Izquierda"
        dlg = BodyCopyDialog(src_body, dst_body, direction, self)
        if dlg.exec() == QDialog.Accepted:
            new_lines = dlg.new_lines
            if not new_lines:
                QMessageBox.information(self, "Sin cambios", "No hay líneas nuevas para agregar.")
                return
            added_text = "\n".join(new_lines)
            pos = dlg.get_position()
            current = dst_panel.body_edit.toPlainText()
            if pos == "end":
                new_content = (current.rstrip() + "\n\n" + added_text).lstrip()
            else:
                new_content = (added_text + "\n\n" + current.lstrip()).rstrip()
            dst_panel.body_edit.setPlainText(new_content)
            dst_panel.body = new_content
            self.statusBar().showMessage(f"Cuerpo copiado al {dst_side}.")

    def _recompare(self, silent: bool = False):
        """Refresh both panels to show aligned properties."""
        # Sync bodies from editors
        self.left_panel.body = self.left_panel.body_edit.toPlainText()
        self.right_panel.body = self.right_panel.body_edit.toPlainText()

        left_keys = set(self.left_panel.props.keys())
        right_keys = set(self.right_panel.props.keys())

        self.left_panel.rebuild_rows(other_keys=right_keys)
        self.right_panel.rebuild_rows(other_keys=left_keys)

        if not silent:
            self.statusBar().showMessage("Comparación actualizada.")

    def _save_template(self):
        all_keys = set(self.left_panel.props.keys()) | set(self.right_panel.props.keys())
        if not all_keys:
            QMessageBox.warning(self, "Sin propiedades", "No hay propiedades para generar plantilla.")
            return

        dlg = TemplateSaveDialog(all_keys, self)
        if dlg.exec() == QDialog.Accepted:
            selected = dlg.get_selected_keys()
            if not selected:
                return
            path, _ = QFileDialog.getSaveFileName(
                self, "Guardar plantilla", "", "Markdown (*.md)"
            )
            if not path:
                return
            template_props = {k: "" for k in sorted(selected, key=str.lower)}
            content = serialize_frontmatter(template_props, "")
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            QMessageBox.information(self, "Plantilla guardada", f"Plantilla guardada en:\n{path}")
            self.statusBar().showMessage(f"Plantilla guardada: {Path(path).name}")

    # ── Styling ─────────────────────────────────────────────────────────────

    def _apply_styles(self):
        self.setStyleSheet("""
        /* ── Paleta oscura tipo Obsidian ── */
        QMainWindow, QWidget {
            background-color: #1e1e2e;
            color: #cdd6f4;
            font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
            font-size: 13px;
        }

        /* ── Toolbar ── */
        QToolBar#MainToolbar {
            background: #181825;
            border-bottom: 1px solid #313244;
            padding: 4px 8px;
            spacing: 4px;
        }
        QToolBar QToolButton {
            background: transparent;
            border: none;
            border-radius: 4px;
            padding: 4px 10px;
            color: #a6adc8;
        }
        QToolBar QToolButton:hover {
            background: #313244;
            color: #cdd6f4;
        }

        /* ── Panel header ── */
        QFrame#PanelHeader {
            background: #181825;
            border-bottom: 1px solid #313244;
        }
        QLabel#PanelTitle {
            font-size: 13px;
            font-weight: bold;
            color: #89b4fa;
        }
        QLabel#PathLabel {
            font-size: 11px;
            color: #6c7086;
            background: #1e1e2e;
            border-bottom: 1px solid #313244;
            padding: 2px 10px;
        }

        /* ── Buttons ── */
        QPushButton#OpenBtn {
            background: #313244;
            border: 1px solid #45475a;
            border-radius: 4px;
            padding: 4px 12px;
            color: #89b4fa;
        }
        QPushButton#OpenBtn:hover { background: #45475a; }

        QPushButton#SaveBtn {
            background: #1e6b4a;
            border: 1px solid #40a070;
            border-radius: 4px;
            padding: 4px 12px;
            color: #a6e3a1;
        }
        QPushButton#SaveBtn:hover { background: #2a8060; }
        QPushButton#SaveBtn:disabled { background: #2a2a3e; color: #585b70; border-color: #45475a; }

        QPushButton#PropBtn {
            background: #313244;
            border: 1px solid #45475a;
            border-radius: 3px;
            color: #cba6f7;
            font-size: 11px;
        }
        QPushButton#PropBtn:hover { background: #45475a; color: #f5c2e7; }

        QPushButton#BulkBtn {
            background: #2a1f3d;
            border: 1px solid #6c4a8a;
            border-radius: 4px;
            padding: 3px 10px;
            color: #cba6f7;
            font-size: 11px;
        }
        QPushButton#BulkBtn:hover { background: #3d2d5a; }

        QPushButton#BodyBtn {
            background: #1f2d3d;
            border: 1px solid #3d6a8a;
            border-radius: 4px;
            padding: 5px 14px;
            color: #89dceb;
        }
        QPushButton#BodyBtn:hover { background: #2a3d50; }

        QPushButton#RecompareBtn {
            background: #2d3020;
            border: 1px solid #8a9a40;
            border-radius: 4px;
            padding: 5px 14px;
            color: #a6e3a1;
        }
        QPushButton#RecompareBtn:hover { background: #3a4030; }

        QPushButton#TemplateBtn {
            background: #2d1f20;
            border: 1px solid #8a4040;
            border-radius: 4px;
            padding: 5px 14px;
            color: #f38ba8;
        }
        QPushButton#TemplateBtn:hover { background: #3a2a2a; }

        /* ── Tabs ── */
        QTabWidget#PanelTabs::pane {
            border: none;
            background: #1e1e2e;
        }
        QTabBar::tab {
            background: #181825;
            color: #6c7086;
            border: 1px solid #313244;
            border-bottom: none;
            padding: 6px 16px;
            border-radius: 4px 4px 0 0;
            margin-right: 2px;
        }
        QTabBar::tab:selected {
            background: #1e1e2e;
            color: #cdd6f4;
            border-bottom: 2px solid #89b4fa;
        }
        QTabBar::tab:hover:!selected { background: #24243e; color: #a6adc8; }

        /* ── Property Rows ── */
        QScrollArea#PropsScroll {
            border: none;
            background: #1e1e2e;
        }
        QFrame#RowContainer {
            background: #1e1e2e;
            border-bottom: 1px solid #2a2a3e;
        }
        QFrame#RowContainer:hover { background: #24243e; }
        QFrame#RowContainerUnpaired {
            background: #1e1e2e;
            border-bottom: 1px dashed #3a2a2a;
            border-left: 3px solid #f38ba8;
        }
        QFrame#RowContainerUnpaired:hover { background: #2a1e1e; }

        QLabel#PropKey {
            color: #89b4fa;
            font-weight: bold;
            font-size: 12px;
        }
        QLabel#PropVal {
            color: #cdd6f4;
            font-size: 12px;
        }

        /* ── Body editor ── */
        QTextEdit#BodyEdit {
            background: #181825;
            color: #cdd6f4;
            border: 1px solid #313244;
            border-radius: 4px;
            padding: 8px;
            selection-background-color: #45475a;
            font-family: 'JetBrains Mono', monospace;
            font-size: 13px;
        }

        /* ── Bulk bar ── */
        QFrame#BulkBar {
            background: #181825;
            border-bottom: 1px solid #313244;
        }

        /* ── Bottom bar ── */
        QFrame#BottomBar {
            background: #181825;
            border-top: 1px solid #313244;
        }
        QLabel#BarLabel {
            color: #6c7086;
            font-size: 12px;
        }

        /* ── Splitter ── */
        QSplitter#MainSplitter::handle {
            background: #313244;
            width: 4px;
        }
        QSplitter#MainSplitter::handle:hover { background: #89b4fa; }

        /* ── Status bar ── */
        QStatusBar {
            background: #181825;
            color: #6c7086;
            border-top: 1px solid #313244;
            font-size: 11px;
        }

        /* ── Menus ── */
        QMenu#PropMenu {
            background: #24243e;
            border: 1px solid #45475a;
            border-radius: 6px;
            padding: 4px;
        }
        QMenu#PropMenu::item {
            padding: 6px 20px;
            border-radius: 4px;
            color: #cdd6f4;
        }
        QMenu#PropMenu::item:selected { background: #313244; color: #89b4fa; }
        QMenu#PropMenu::separator { background: #45475a; height: 1px; margin: 4px 8px; }

        /* ── Dialogs ── */
        QDialog {
            background: #1e1e2e;
            color: #cdd6f4;
        }
        QComboBox {
            background: #313244;
            border: 1px solid #45475a;
            border-radius: 4px;
            padding: 4px 8px;
            color: #cdd6f4;
        }
        QComboBox::drop-down { border: none; }
        QComboBox QAbstractItemView {
            background: #24243e;
            border: 1px solid #45475a;
            selection-background-color: #45475a;
        }

        /* ── List widget ── */
        QListWidget {
            background: #181825;
            border: 1px solid #313244;
            border-radius: 4px;
            color: #cdd6f4;
        }
        QListWidget::item:selected { background: #313244; }
        QListWidget::item:hover { background: #24243e; }

        /* ── ScrollBar ── */
        QScrollBar:vertical {
            background: #181825;
            width: 8px;
            border-radius: 4px;
        }
        QScrollBar::handle:vertical {
            background: #45475a;
            border-radius: 4px;
            min-height: 20px;
        }
        QScrollBar::handle:vertical:hover { background: #585b70; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

        QCheckBox { spacing: 4px; }
        QCheckBox::indicator {
            width: 14px; height: 14px;
            border: 1px solid #45475a;
            border-radius: 3px;
            background: #313244;
        }
        QCheckBox::indicator:checked {
            background: #89b4fa;
            border-color: #89b4fa;
        }

        QDialogButtonBox QPushButton {
            background: #313244;
            border: 1px solid #45475a;
            border-radius: 4px;
            padding: 5px 16px;
            color: #cdd6f4;
        }
        QDialogButtonBox QPushButton:hover { background: #45475a; }

        QLabel#DialogInfo {
            color: #a6adc8;
            font-size: 13px;
            padding: 4px 0;
        }
        """)


# ─── Entry Point ───────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Obsidian Markdown Comparator")
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    # Optional: load files from command line args
    args = sys.argv[1:]
    if len(args) >= 1 and os.path.isfile(args[0]):
        window.left_panel.load_file(args[0])
    if len(args) >= 2 and os.path.isfile(args[1]):
        window.right_panel.load_file(args[1])
    if len(args) >= 2:
        window._recompare(silent=True)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
