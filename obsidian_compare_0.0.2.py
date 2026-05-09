#!/usr/bin/env python3
"""
Obsidian Markdown Comparator
Compares two Obsidian markdown files, allows copying YAML properties
bidirectionally, editing content, and saving as templates.
"""

import sys
import os
import copy
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QSplitter, QScrollArea,
    QFrame, QTextEdit, QDialog, QDialogButtonBox, QCheckBox,
    QMessageBox, QMenu, QToolBar, QSizePolicy, QComboBox,
    QTabWidget, QListWidget, QListWidgetItem, QAbstractItemView,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QAction, QCursor


# ─── YAML Helpers ─────────────────────────────────────────────────────────────

def parse_frontmatter(text: str) -> tuple[dict, str]:
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
            if val == "":
                items = []
                i += 1
                while i < len(lines) and (lines[i].startswith("  ") or lines[i].startswith("- ")):
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
    val = value.strip().strip('"').strip("'").strip("[]")
    return f'[[{val}]]'


def is_wikilink(value: str) -> bool:
    v = value.strip()
    return v.startswith("[[") and v.endswith("]]")


def is_empty_value(value) -> bool:
    if isinstance(value, list):
        return len(value) == 0
    return str(value).strip() == ""


def body_lines_set(body: str) -> set:
    return set(l.rstrip() for l in body.splitlines() if l.strip())


# ─── Property Row ─────────────────────────────────────────────────────────────

class PropRow(QFrame):
    action_requested = Signal(str, str, object)

    def __init__(self, key: str, value, side: str, paired: bool = True, parent=None):
        super().__init__(parent)
        self.key = key
        self.value = value
        self.side = side
        self.paired = paired
        self._build_ui()

    def _build_ui(self):
        self.setObjectName("PropRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(6)

        self.key_lbl = QLabel(self.key)
        self.key_lbl.setFixedWidth(130)
        self.key_lbl.setObjectName("PropKey")
        self.key_lbl.setToolTip(self.key)
        layout.addWidget(self.key_lbl)

        display_val = self._display_value(self.value)
        self.val_lbl = QLabel(display_val)
        self.val_lbl.setObjectName("PropVal")
        self.val_lbl.setToolTip(display_val)
        self.val_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self.val_lbl)

        self.btn = QPushButton("···")
        self.btn.setObjectName("PropBtn")
        self.btn.setFixedSize(28, 22)
        self.btn.clicked.connect(self._show_menu)
        layout.addWidget(self.btn)

    def _display_value(self, val) -> str:
        if isinstance(val, list):
            if not val:
                return "(lista vacía)"
            return " | ".join(str(v) for v in val[:4]) + (" …" if len(val) > 4 else "")
        return str(val) if str(val).strip() != "" else "(vacío)"

    def refresh(self, value):
        self.value = value
        dv = self._display_value(value)
        self.val_lbl.setText(dv)
        self.val_lbl.setToolTip(dv)

    def _show_menu(self):
        menu = QMenu(self)
        menu.setObjectName("PropMenu")

        other = "derecha" if self.side == "left" else "izquierda"
        arrow = "→" if self.side == "left" else "←"

        menu.addAction(f"{arrow} Copiar a {other}").triggered.connect(
            lambda: self.action_requested.emit("copy", self.side, self))
        menu.addAction(f"{arrow} Agregar como ítem de lista a {other}").triggered.connect(
            lambda: self.action_requested.emit("add_list", self.side, self))

        menu.addSeparator()

        menu.addAction(f"{arrow} Copiar como WikiLink a {other}").triggered.connect(
            lambda: self.action_requested.emit("copy_wiki", self.side, self))

        # Convert to wikilink only if value is non-empty and not already wikilink
        val_str = str(self.value) if not isinstance(self.value, list) else ""
        if not is_empty_value(self.value) and not is_wikilink(val_str):
            menu.addAction("⟳ Convertir a WikiLink (aquí)").triggered.connect(
                lambda: self.action_requested.emit("convert_wiki", self.side, self))

        menu.addSeparator()

        menu.addAction("🗑 Eliminar propiedad").triggered.connect(
            lambda: self.action_requested.emit("delete", self.side, self))

        menu.exec(QCursor.pos())


# ─── Properties Panel ─────────────────────────────────────────────────────────

class PropsPanel(QWidget):
    def __init__(self, side: str, parent=None):
        super().__init__(parent)
        self.side = side
        self.filepath: Optional[str] = None
        self.props: dict = {}
        self.body: str = ""
        self.prop_rows: dict[str, PropRow] = {}
        self.row_checks: dict[str, QCheckBox] = {}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setObjectName("PanelHeader")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(10, 7, 10, 7)
        title = "📄 Archivo Izquierdo" if self.side == "left" else "📄 Archivo Derecho"
        self.title_lbl = QLabel(title)
        self.title_lbl.setObjectName("PanelTitle")
        hl.addWidget(self.title_lbl)
        hl.addStretch()
        self.open_btn = QPushButton("Abrir…")
        self.open_btn.setObjectName("OpenBtn")
        self.open_btn.clicked.connect(self.open_file)
        hl.addWidget(self.open_btn)
        self.save_btn = QPushButton("Guardar")
        self.save_btn.setObjectName("SaveBtn")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save_file)
        hl.addWidget(self.save_btn)
        layout.addWidget(header)

        self.path_lbl = QLabel("Sin archivo")
        self.path_lbl.setObjectName("PathLabel")
        self.path_lbl.setContentsMargins(10, 3, 10, 3)
        layout.addWidget(self.path_lbl)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setObjectName("PanelTabs")
        layout.addWidget(self.tabs)

        # Props tab
        props_tab = QWidget()
        ptl = QVBoxLayout(props_tab)
        ptl.setContentsMargins(0, 0, 0, 0)
        ptl.setSpacing(0)

        bulk_bar = QFrame()
        bulk_bar.setObjectName("BulkBar")
        bbl = QHBoxLayout(bulk_bar)
        bbl.setContentsMargins(8, 3, 8, 3)
        bbl.setSpacing(6)

        self.select_all_cb = QCheckBox("Todo")
        self.select_all_cb.stateChanged.connect(self._toggle_all)
        bbl.addWidget(self.select_all_cb)

        self.bulk_wiki_btn = QPushButton("⟳ WikiLink sel.")
        self.bulk_wiki_btn.setObjectName("BulkBtn")
        self.bulk_wiki_btn.clicked.connect(self._bulk_to_wikilink)
        bbl.addWidget(self.bulk_wiki_btn)

        self.bulk_copy_btn = QPushButton("→ Copiar sel.")
        self.bulk_copy_btn.setObjectName("BulkBtn")
        self.bulk_copy_btn.clicked.connect(self._bulk_copy)
        bbl.addWidget(self.bulk_copy_btn)

        self.bulk_del_btn = QPushButton("🗑 Eliminar sel.")
        self.bulk_del_btn.setObjectName("BulkDelBtn")
        self.bulk_del_btn.clicked.connect(self._bulk_delete)
        bbl.addWidget(self.bulk_del_btn)

        bbl.addStretch()
        ptl.addWidget(bulk_bar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setObjectName("PropsScroll")
        self.props_container = QWidget()
        self.props_layout = QVBoxLayout(self.props_container)
        self.props_layout.setContentsMargins(0, 0, 0, 0)
        self.props_layout.setSpacing(1)
        self.props_layout.addStretch()
        self.scroll.setWidget(self.props_container)
        ptl.addWidget(self.scroll)
        self.tabs.addTab(props_tab, "Propiedades YAML")

        # Body tab
        body_tab = QWidget()
        btl = QVBoxLayout(body_tab)
        btl.setContentsMargins(6, 6, 6, 6)
        self.body_edit = QTextEdit()
        self.body_edit.setObjectName("BodyEdit")
        self.body_edit.setPlaceholderText("Cuerpo de la nota…")
        btl.addWidget(self.body_edit)
        self.tabs.addTab(body_tab, "Cuerpo")

    # ── File I/O ──────────────────────────────────────────────────────────────

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
            path, _ = QFileDialog.getSaveFileName(self, "Guardar", "", "Markdown (*.md)")
            if not path:
                return
            self.filepath = path
        self.body = self.body_edit.toPlainText()
        content = serialize_frontmatter(self.props, self.body)
        with open(self.filepath, "w", encoding="utf-8") as f:
            f.write(content)
        QMessageBox.information(self, "Guardado", f"Archivo guardado:\n{self.filepath}")

    # ── Row management ────────────────────────────────────────────────────────

    def rebuild_rows(self, other_keys: set = None):
        while self.props_layout.count() > 1:
            item = self.props_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.prop_rows.clear()
        self.row_checks.clear()
        for key in sorted(self.props.keys(), key=str.lower):
            paired = (other_keys is None) or (key in other_keys)
            self._add_row(key, self.props[key], paired)

    def _add_row(self, key: str, val, paired: bool = True):
        container = QFrame()
        container.setObjectName("RowContainerUnpaired" if not paired else "RowContainer")
        rl = QHBoxLayout(container)
        rl.setContentsMargins(4, 0, 4, 0)
        rl.setSpacing(4)

        cb = QCheckBox()
        cb.setFixedWidth(20)
        rl.addWidget(cb)
        self.row_checks[key] = cb

        row = PropRow(key, val, self.side, paired)
        row.action_requested.connect(self._on_action)
        rl.addWidget(row)

        self.props_layout.insertWidget(self.props_layout.count() - 1, container)
        self.prop_rows[key] = row

    def set_prop(self, key: str, value):
        self.props[key] = value
        if key in self.prop_rows:
            self.prop_rows[key].refresh(value)
        else:
            self._add_row(key, value)

    def add_to_list_prop(self, key: str, value):
        current = self.props.get(key, [])
        if isinstance(current, list):
            if value not in current:
                current.append(value)
        else:
            current = [value] if current == "" else ([current, value] if current != value else [current])
        self.props[key] = current
        if key in self.prop_rows:
            self.prop_rows[key].refresh(current)
        else:
            self._add_row(key, current)

    def delete_prop(self, key: str):
        if key in self.props:
            del self.props[key]
        if key in self.prop_rows:
            row = self.prop_rows.pop(key)
            container = row.parent()
            if container:
                self.props_layout.removeWidget(container)
                container.deleteLater()
        if key in self.row_checks:
            del self.row_checks[key]

    def convert_to_wikilink(self, key: str):
        """Convert only non-empty values to wikilink."""
        val = self.props.get(key)
        if val is None or is_empty_value(val):
            return
        if isinstance(val, list):
            self.props[key] = [
                to_wikilink(v) if (v.strip() and not is_wikilink(v)) else v
                for v in val
            ]
        else:
            sv = str(val).strip()
            if sv and not is_wikilink(sv):
                self.props[key] = to_wikilink(sv)
        if key in self.prop_rows:
            self.prop_rows[key].refresh(self.props[key])

    def _toggle_all(self, state):
        for cb in self.row_checks.values():
            cb.setChecked(bool(state))

    def _bulk_to_wikilink(self):
        for key, cb in self.row_checks.items():
            if cb.isChecked():
                self.convert_to_wikilink(key)  # skips empty automatically

    def _bulk_copy(self):
        mw = self._main_window()
        if not mw:
            return
        dst = mw.right_panel if self.side == "left" else mw.left_panel
        keys = [k for k, cb in self.row_checks.items() if cb.isChecked()]
        for key in keys:
            dst.set_prop(key, copy.deepcopy(self.props[key]))
        if keys:
            mw.statusBar().showMessage(f"{len(keys)} propiedad(es) copiada(s).")
            mw._recompare(silent=True)

    def _bulk_delete(self):
        keys = [k for k, cb in self.row_checks.items() if cb.isChecked()]
        if not keys:
            return
        reply = QMessageBox.question(
            self, "Eliminar propiedades",
            f"¿Eliminar {len(keys)} propiedad(es) seleccionada(s)?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            for key in keys:
                self.delete_prop(key)
            mw = self._main_window()
            if mw:
                mw.statusBar().showMessage(f"{len(keys)} propiedad(es) eliminada(s).")
                mw._recompare(silent=True)

    def get_selected_keys(self) -> list[str]:
        return [k for k, cb in self.row_checks.items() if cb.isChecked()]

    def _main_window(self):
        w = self
        while w and not isinstance(w, MainWindow):
            w = w.parent()
        return w

    def _on_action(self, action: str, side: str, row: PropRow):
        mw = self._main_window()
        if mw:
            mw.handle_prop_action(action, side, row)


# ─── Body Copy Dialog ─────────────────────────────────────────────────────────

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

        dst_set = body_lines_set(self.dst_body)
        src_lines = [l for l in self.src_body.splitlines() if l.strip() and l.rstrip() not in dst_set]
        layout.addWidget(QLabel(f"Líneas nuevas a agregar ({len(src_lines)}):"))

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


# ─── Template Save Dialog ─────────────────────────────────────────────────────

class TemplateSaveDialog(QDialog):
    """
    Table: [✓ propiedad | valor izquierdo | valor derecho | ¿con valor?]
    Per row the user chooses: vacía / izquierdo / derecho
    """
    def __init__(self, left_props: dict, right_props: dict, parent=None):
        super().__init__(parent)
        self.left_props = left_props
        self.right_props = right_props
        self.setWindowTitle("Guardar como plantilla")
        self.setMinimumWidth(640)
        self.setMinimumHeight(440)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Configura qué propiedades incluir en la plantilla:"))

        all_keys = sorted(
            set(self.left_props.keys()) | set(self.right_props.keys()),
            key=str.lower
        )
        self._keys = all_keys

        self.table = QTableWidget(len(all_keys), 4)
        self.table.setHorizontalHeaderLabels(["Propiedad", "Valor izquierdo", "Valor derecho", "¿Con valor?"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setDefaultSectionSize(26)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)

        self._row_include: dict[int, QCheckBox] = {}
        self._row_value_combo: dict[int, QComboBox] = {}

        for i, key in enumerate(all_keys):
            lval = self.left_props.get(key, "")
            rval = self.right_props.get(key, "")

            # Col 0: checkbox + key label
            cell_w = QWidget()
            cell_l = QHBoxLayout(cell_w)
            cell_l.setContentsMargins(4, 0, 4, 0)
            cb = QCheckBox(key)
            cb.setChecked(True)
            cell_l.addWidget(cb)
            self._row_include[i] = cb
            self.table.setCellWidget(i, 0, cell_w)

            # Col 1 & 2: read-only value display
            for col, val in [(1, lval), (2, rval)]:
                item = QTableWidgetItem(self._val_str(val))
                item.setFlags(Qt.ItemIsEnabled)
                self.table.setItem(i, col, item)

            # Col 3: with-value combo
            combo = QComboBox()
            combo.addItems(["Vacía", "Izquierdo", "Derecho"])
            if not is_empty_value(lval):
                combo.setCurrentIndex(1)
            elif not is_empty_value(rval):
                combo.setCurrentIndex(2)
            else:
                combo.setCurrentIndex(0)
            self._row_value_combo[i] = combo
            self.table.setCellWidget(i, 3, combo)

        layout.addWidget(self.table)

        # Select all / none
        btn_row = QHBoxLayout()
        sel_all = QPushButton("Seleccionar todo")
        sel_all.clicked.connect(lambda: [cb.setChecked(True) for cb in self._row_include.values()])
        sel_none = QPushButton("Ninguno")
        sel_none.clicked.connect(lambda: [cb.setChecked(False) for cb in self._row_include.values()])
        btn_row.addWidget(sel_all)
        btn_row.addWidget(sel_none)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _val_str(self, val) -> str:
        if isinstance(val, list):
            return " | ".join(str(v) for v in val) if val else "(vacío)"
        return str(val) if str(val).strip() else "(vacío)"

    def get_template_props(self) -> dict:
        result = {}
        for i, key in enumerate(self._keys):
            if not self._row_include[i].isChecked():
                continue
            choice = self._row_value_combo[i].currentIndex()
            if choice == 0:
                result[key] = ""
            elif choice == 1:
                result[key] = copy.deepcopy(self.left_props.get(key, ""))
            else:
                result[key] = copy.deepcopy(self.right_props.get(key, ""))
        return result


# ─── Main Window ──────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Obsidian Markdown Comparator")
        self.setMinimumSize(1100, 700)
        self._apply_styles()
        self._build_ui()
        self._build_toolbar()
        self.statusBar().showMessage("Abre dos archivos Markdown para comenzar.")

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Splitter takes all available space
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setObjectName("MainSplitter")
        self.splitter.setHandleWidth(5)
        self.left_panel = PropsPanel("left", self)
        self.right_panel = PropsPanel("right", self)
        self.splitter.addWidget(self.left_panel)
        self.splitter.addWidget(self.right_panel)
        self.splitter.setSizes([500, 500])
        main_layout.addWidget(self.splitter, stretch=1)

        # ── Bottom bar — compact fixed height ─────────────────────────────
        bottom = QFrame()
        bottom.setObjectName("BottomBar")
        bottom.setFixedHeight(42)
        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(10, 0, 10, 0)
        bottom_layout.setSpacing(8)

        body_lbl = QLabel("Cuerpo:")
        body_lbl.setObjectName("BarLabel")
        bottom_layout.addWidget(body_lbl)

        self.copy_body_lr = QPushButton("→ Cuerpo a derecha")
        self.copy_body_lr.setObjectName("BodyBtn")
        self.copy_body_lr.setFixedHeight(28)
        self.copy_body_lr.clicked.connect(lambda: self._copy_body("left", "right"))
        bottom_layout.addWidget(self.copy_body_lr)

        self.copy_body_rl = QPushButton("← Cuerpo a izquierda")
        self.copy_body_rl.setObjectName("BodyBtn")
        self.copy_body_rl.setFixedHeight(28)
        self.copy_body_rl.clicked.connect(lambda: self._copy_body("right", "left"))
        bottom_layout.addWidget(self.copy_body_rl)

        bottom_layout.addStretch()

        self.recompare_btn = QPushButton("🔄 Volver a comparar")
        self.recompare_btn.setObjectName("RecompareBtn")
        self.recompare_btn.setFixedHeight(28)
        self.recompare_btn.clicked.connect(self._recompare)
        bottom_layout.addWidget(self.recompare_btn)

        self.template_btn = QPushButton("💾 Guardar plantilla")
        self.template_btn.setObjectName("TemplateBtn")
        self.template_btn.setFixedHeight(28)
        self.template_btn.clicked.connect(self._save_template)
        bottom_layout.addWidget(self.template_btn)

        main_layout.addWidget(bottom, stretch=0)

    def _build_toolbar(self):
        tb = QToolBar("Principal")
        tb.setMovable(False)
        tb.setObjectName("MainToolbar")
        tb.setIconSize(QSize(14, 14))
        self.addToolBar(tb)
        for label, slot in [
            ("📂 Abrir izquierdo", self.left_panel.open_file),
            ("📂 Abrir derecho", self.right_panel.open_file),
            (None, None),
            ("💾 Guardar izquierdo", self.left_panel.save_file),
            ("💾 Guardar derecho", self.right_panel.save_file),
            (None, None),
            ("🔄 Comparar", self._recompare),
            (None, None),
            ("📋 Plantilla", self._save_template),
        ]:
            if label is None:
                tb.addSeparator()
            else:
                a = QAction(label, self)
                a.triggered.connect(slot)
                tb.addAction(a)

    # ── Actions ───────────────────────────────────────────────────────────────

    def handle_prop_action(self, action: str, side: str, row: PropRow):
        key = row.key
        value = row.value
        src_panel = self.left_panel if side == "left" else self.right_panel
        dst_panel = self.right_panel if side == "left" else self.left_panel

        if action == "copy":
            dst_panel.set_prop(key, copy.deepcopy(value))
            self.statusBar().showMessage(f"'{key}' copiada.")

        elif action == "add_list":
            items = value if isinstance(value, list) else [value]
            for v in items:
                dst_panel.add_to_list_prop(key, v)
            self.statusBar().showMessage(f"'{key}' agregada como lista.")

        elif action == "copy_wiki":
            if isinstance(value, list):
                wiki_val = [to_wikilink(v) if (v.strip() and not is_wikilink(v)) else v for v in value]
            else:
                sv = str(value).strip()
                wiki_val = to_wikilink(sv) if (sv and not is_wikilink(sv)) else sv
            dst_panel.set_prop(key, wiki_val)
            self.statusBar().showMessage(f"'{key}' copiada como WikiLink.")

        elif action == "convert_wiki":
            src_panel.convert_to_wikilink(key)
            self.statusBar().showMessage(f"'{key}' convertida a WikiLink.")

        elif action == "delete":
            reply = QMessageBox.question(
                self, "Eliminar propiedad",
                f"¿Eliminar la propiedad '{key}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                src_panel.delete_prop(key)
                self.statusBar().showMessage(f"'{key}' eliminada.")

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
            self.statusBar().showMessage("Cuerpo copiado.")

    def _recompare(self, silent: bool = False):
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
        dlg = TemplateSaveDialog(self.left_panel.props, self.right_panel.props, self)
        if dlg.exec() == QDialog.Accepted:
            template_props = dlg.get_template_props()
            if not template_props:
                return
            path, _ = QFileDialog.getSaveFileName(self, "Guardar plantilla", "", "Markdown (*.md)")
            if not path:
                return
            sorted_props = dict(sorted(template_props.items(), key=lambda x: x[0].lower()))
            content = serialize_frontmatter(sorted_props, "")
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            QMessageBox.information(self, "Plantilla guardada", f"Plantilla guardada en:\n{path}")
            self.statusBar().showMessage(f"Plantilla guardada: {Path(path).name}")

    # ── Styles ────────────────────────────────────────────────────────────────

    def _apply_styles(self):
        self.setStyleSheet("""
        QMainWindow, QWidget {
            background-color: #1e1e2e;
            color: #cdd6f4;
            font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
            font-size: 13px;
        }
        QToolBar#MainToolbar {
            background: #181825; border-bottom: 1px solid #313244;
            padding: 3px 8px; spacing: 3px;
        }
        QToolBar QToolButton {
            background: transparent; border: none; border-radius: 4px;
            padding: 3px 9px; color: #a6adc8;
        }
        QToolBar QToolButton:hover { background: #313244; color: #cdd6f4; }

        QFrame#PanelHeader { background: #181825; border-bottom: 1px solid #313244; }
        QLabel#PanelTitle { font-size: 13px; font-weight: bold; color: #89b4fa; }
        QLabel#PathLabel {
            font-size: 11px; color: #6c7086; background: #1e1e2e;
            border-bottom: 1px solid #2a2a3e; padding: 2px 10px;
        }

        QPushButton#OpenBtn {
            background: #313244; border: 1px solid #45475a;
            border-radius: 4px; padding: 3px 11px; color: #89b4fa;
        }
        QPushButton#OpenBtn:hover { background: #45475a; }

        QPushButton#SaveBtn {
            background: #1e6b4a; border: 1px solid #40a070;
            border-radius: 4px; padding: 3px 11px; color: #a6e3a1;
        }
        QPushButton#SaveBtn:hover { background: #2a8060; }
        QPushButton#SaveBtn:disabled { background: #2a2a3e; color: #585b70; border-color: #45475a; }

        QPushButton#PropBtn {
            background: #313244; border: 1px solid #45475a;
            border-radius: 3px; color: #cba6f7; font-size: 11px;
        }
        QPushButton#PropBtn:hover { background: #45475a; color: #f5c2e7; }

        QPushButton#BulkBtn {
            background: #2a1f3d; border: 1px solid #6c4a8a;
            border-radius: 4px; padding: 2px 9px; color: #cba6f7; font-size: 11px;
        }
        QPushButton#BulkBtn:hover { background: #3d2d5a; }

        QPushButton#BulkDelBtn {
            background: #2d1515; border: 1px solid #7a3030;
            border-radius: 4px; padding: 2px 9px; color: #f38ba8; font-size: 11px;
        }
        QPushButton#BulkDelBtn:hover { background: #3d2020; }

        QPushButton#BodyBtn {
            background: #1f2d3d; border: 1px solid #3d6a8a;
            border-radius: 4px; padding: 3px 12px; color: #89dceb;
        }
        QPushButton#BodyBtn:hover { background: #2a3d50; }

        QPushButton#RecompareBtn {
            background: #2d3020; border: 1px solid #8a9a40;
            border-radius: 4px; padding: 3px 12px; color: #a6e3a1;
        }
        QPushButton#RecompareBtn:hover { background: #3a4030; }

        QPushButton#TemplateBtn {
            background: #2d1f20; border: 1px solid #8a4040;
            border-radius: 4px; padding: 3px 12px; color: #f38ba8;
        }
        QPushButton#TemplateBtn:hover { background: #3a2a2a; }

        QTabWidget#PanelTabs::pane { border: none; background: #1e1e2e; }
        QTabBar::tab {
            background: #181825; color: #6c7086; border: 1px solid #313244;
            border-bottom: none; padding: 5px 14px;
            border-radius: 4px 4px 0 0; margin-right: 2px;
        }
        QTabBar::tab:selected { background: #1e1e2e; color: #cdd6f4; border-bottom: 2px solid #89b4fa; }
        QTabBar::tab:hover:!selected { background: #24243e; color: #a6adc8; }

        QScrollArea#PropsScroll { border: none; background: #1e1e2e; }
        QFrame#RowContainer { background: #1e1e2e; border-bottom: 1px solid #2a2a3e; }
        QFrame#RowContainer:hover { background: #24243e; }
        QFrame#RowContainerUnpaired {
            background: #1e1e2e; border-bottom: 1px dashed #3a2a2a;
            border-left: 3px solid #f38ba8;
        }
        QFrame#RowContainerUnpaired:hover { background: #2a1e1e; }

        QLabel#PropKey { color: #89b4fa; font-weight: bold; font-size: 12px; }
        QLabel#PropVal { color: #cdd6f4; font-size: 12px; }

        QTextEdit#BodyEdit {
            background: #181825; color: #cdd6f4;
            border: 1px solid #313244; border-radius: 4px;
            padding: 8px; selection-background-color: #45475a;
            font-family: 'JetBrains Mono', monospace; font-size: 13px;
        }

        QFrame#BulkBar { background: #181825; border-bottom: 1px solid #313244; }

        QFrame#BottomBar { background: #181825; border-top: 1px solid #313244; }
        QLabel#BarLabel { color: #6c7086; font-size: 12px; }

        QSplitter#MainSplitter::handle { background: #313244; }
        QSplitter#MainSplitter::handle:hover { background: #89b4fa; }

        QStatusBar {
            background: #181825; color: #6c7086;
            border-top: 1px solid #313244; font-size: 11px;
        }

        QMenu#PropMenu {
            background: #24243e; border: 1px solid #45475a;
            border-radius: 6px; padding: 4px;
        }
        QMenu#PropMenu::item { padding: 5px 18px; border-radius: 4px; color: #cdd6f4; }
        QMenu#PropMenu::item:selected { background: #313244; color: #89b4fa; }
        QMenu#PropMenu::separator { background: #45475a; height: 1px; margin: 3px 8px; }

        QDialog { background: #1e1e2e; color: #cdd6f4; }
        QComboBox {
            background: #313244; border: 1px solid #45475a;
            border-radius: 4px; padding: 3px 8px; color: #cdd6f4;
        }
        QComboBox::drop-down { border: none; }
        QComboBox QAbstractItemView {
            background: #24243e; border: 1px solid #45475a;
            selection-background-color: #45475a; color: #cdd6f4;
        }

        QTableWidget {
            background: #181825; color: #cdd6f4;
            border: 1px solid #313244; gridline-color: #2a2a3e;
        }
        QHeaderView::section {
            background: #24243e; color: #89b4fa;
            border: none; border-bottom: 1px solid #313244;
            padding: 4px 6px; font-size: 12px;
        }
        QTableWidget::item { padding: 2px 6px; }
        QTableWidget::item:selected { background: #313244; }

        QScrollBar:vertical {
            background: #181825; width: 7px; border-radius: 3px;
        }
        QScrollBar::handle:vertical {
            background: #45475a; border-radius: 3px; min-height: 20px;
        }
        QScrollBar::handle:vertical:hover { background: #585b70; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

        QCheckBox { spacing: 4px; color: #cdd6f4; }
        QCheckBox::indicator {
            width: 13px; height: 13px;
            border: 1px solid #45475a; border-radius: 3px; background: #313244;
        }
        QCheckBox::indicator:checked { background: #89b4fa; border-color: #89b4fa; }

        QDialogButtonBox QPushButton {
            background: #313244; border: 1px solid #45475a;
            border-radius: 4px; padding: 4px 14px; color: #cdd6f4;
        }
        QDialogButtonBox QPushButton:hover { background: #45475a; }
        QLabel#DialogInfo { color: #a6adc8; font-size: 13px; padding: 3px 0; }
        """)


# ─── Entry Point ──────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Obsidian Markdown Comparator")
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
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
