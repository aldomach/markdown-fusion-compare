"""
ui/props_panel.py
PropsPanel: full panel for one markdown file.
Contains: header (open/new/save/undo), path label, tabs (props / body).
Bulk bar: select-all checkbox + action combo + apply button + copy-selected button.
Delegates all data mutations through NoteFile (core/models.py).
Emits file_loaded(side) so MainWindow can trigger auto-compare.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame,
    QLabel, QPushButton, QCheckBox, QComboBox,
    QScrollArea, QTabWidget, QTextEdit, QLineEdit,
    QFileDialog, QMessageBox, QSizePolicy, QCompleter,
    QMenu
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor

from ui.body_editor import BodyEditor

from core.models import NoteFile
from core.utils import now_timestamp, is_empty_value, convert_value_to_wikilink
from core.compare import compare_props, LEFT_ONLY, RIGHT_ONLY
from ui.prop_row import (
    PropRow,
    ACTION_COPY, ACTION_COPY_EMPTY, ACTION_ADD_LIST,
    ACTION_COPY_WIKI, ACTION_CONVERT_WIKI, ACTION_DELETE,
)

if TYPE_CHECKING:
    from ui.main_window import MainWindow


# ── Bulk action definitions (label, action_id) ────────────────────────────────
# Keep action_ids in sync with ACTION_* constants in prop_row.py

BULK_ACTIONS: list[tuple[str, str]] = [
    ("→ Copiar a otro panel",              ACTION_COPY),
    ("→ Copiar vacía a otro panel",        ACTION_COPY_EMPTY),
    ("→ Agregar como ítem de lista",       ACTION_ADD_LIST),
    ("→ Copiar como WikiLink",             ACTION_COPY_WIKI),
    ("⟳ Convertir a WikiLink (aquí)",     ACTION_CONVERT_WIKI),
    ("🗑 Eliminar seleccionadas",          ACTION_DELETE),
]


class PropsPanel(QWidget):
    file_loaded = Signal(str)   # emits side when a file is loaded/created

    def __init__(self, side: str, parent: "MainWindow | None" = None):
        super().__init__(parent)
        self.side = side
        self.note = NoteFile()
        self.prop_rows:   dict[str, PropRow]   = {}
        self.row_checks:  dict[str, QCheckBox] = {}
        self._status_map: dict[str, str]       = {}   # key → compare status
        self._updated_checkbox: QCheckBox | None = None
        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())
        root.addWidget(self._build_path_label())

        # ── Props tab (QTabWidget with single tab) ────────────────────────
        self.tabs = QTabWidget()
        self.tabs.setObjectName("PanelTabs")
        self.tabs.addTab(self._build_props_tab(), "Propiedades YAML")
        root.addWidget(self.tabs, stretch=1)

        # ── Body editor — directly below, no tab wrapper ──────────────────
        self._body_editor_widget = BodyEditor(self.side, self)
        self.body_edit = self._body_editor_widget.editor
        root.addWidget(self._body_editor_widget, stretch=1)

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("PanelHeader")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(10, 6, 10, 6)
        hl.setSpacing(6)

        title_text = "📄 Archivo Izquierdo" if self.side == "left" else "📄 Archivo Derecho"
        title = QLabel(title_text)
        title.setObjectName("PanelTitle")
        hl.addWidget(title)
        hl.addStretch()

        self.new_btn = QPushButton("Nuevo")
        self.new_btn.setObjectName("NewBtn")
        self.new_btn.clicked.connect(self._new_file)
        hl.addWidget(self.new_btn)

        self.open_btn = QPushButton("Abrir…")
        self.open_btn.setObjectName("OpenBtn")
        self.open_btn.clicked.connect(self.open_file)
        hl.addWidget(self.open_btn)

        self.save_btn = QPushButton("Guardar")
        self.save_btn.setObjectName("SaveBtn")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save_file)
        hl.addWidget(self.save_btn)

        self.undo_btn = QPushButton("↩ Deshacer")
        self.undo_btn.setObjectName("UndoBtn")
        self.undo_btn.setEnabled(False)
        self.undo_btn.clicked.connect(self._undo)
        hl.addWidget(self.undo_btn)

        return header

    def _build_path_label(self) -> QLabel:
        self.path_lbl = QLabel("Sin archivo")
        self.path_lbl.setObjectName("PathLabel")
        self.path_lbl.setContentsMargins(10, 3, 10, 3)
        return self.path_lbl

    def _build_props_tab(self) -> QWidget:
        tab = QWidget()
        tl = QVBoxLayout(tab)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(0)
        tl.addWidget(self._build_bulk_bar())
        tl.addWidget(self._build_search_bar())
        tl.addWidget(self._build_props_scroll())
        return tab

    def _build_search_bar(self) -> QFrame:
        """Search + extract-to-YAML bar shown above the prop list."""
        bar = QFrame()
        bar.setObjectName("SearchBar")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(8, 3, 8, 3)
        bl.setSpacing(6)

        self._search_edit = QLineEdit()
        self._search_edit.setObjectName("SearchEdit")
        self._search_edit.setPlaceholderText("Buscar en cuerpo / agregar propiedad…")
        self._search_edit.setFixedHeight(26)
        self._search_edit.returnPressed.connect(self._search_in_body)
        bl.addWidget(self._search_edit, stretch=1)

        search_btn = QPushButton("🔍")
        search_btn.setObjectName("SearchIconBtn")
        search_btn.setFixedSize(28, 26)
        search_btn.setToolTip("Buscar en el cuerpo")
        search_btn.clicked.connect(self._search_in_body)
        bl.addWidget(search_btn)

        add_prop_btn = QPushButton("+ Agregar como propiedad")
        add_prop_btn.setObjectName("BulkApplyBtn")
        add_prop_btn.setFixedHeight(26)
        add_prop_btn.setToolTip("Agrega el texto del campo como nueva propiedad YAML")
        add_prop_btn.clicked.connect(self._add_as_prop)
        bl.addWidget(add_prop_btn)

        add_tag_btn = QPushButton("+ Agregar a tags")
        add_tag_btn.setObjectName("BulkApplyBtn")
        add_tag_btn.setFixedHeight(26)
        add_tag_btn.setToolTip("Agrega el texto a la propiedad 'tags' como ítem de lista")
        add_tag_btn.clicked.connect(self._add_as_tag)
        bl.addWidget(add_tag_btn)

        return bar

    def _build_bulk_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("BulkBar")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(8, 4, 8, 4)
        bl.setSpacing(6)

        self.select_all_cb = QCheckBox("Todo")
        self.select_all_cb.stateChanged.connect(self._toggle_all)
        bl.addWidget(self.select_all_cb)

        self.bulk_combo = QComboBox()
        self.bulk_combo.setFixedHeight(26)
        for label, _ in BULK_ACTIONS:
            self.bulk_combo.addItem(label)
        bl.addWidget(self.bulk_combo)

        apply_btn = QPushButton("Aplicar")
        apply_btn.setObjectName("BulkApplyBtn")
        apply_btn.setFixedHeight(26)
        apply_btn.clicked.connect(self._bulk_apply)
        bl.addWidget(apply_btn)

        copy_btn = QPushButton("→ Copiar sel.")
        copy_btn.setObjectName("BulkApplyBtn")
        copy_btn.setFixedHeight(26)
        copy_btn.clicked.connect(self._bulk_copy_selected)
        bl.addWidget(copy_btn)

        bl.addStretch()

        # Updated timestamp toggle
        self._updated_checkbox = QCheckBox("updated")
        self._updated_checkbox.setToolTip(
            "Al guardar, agrega/actualiza la propiedad 'updated' con la fecha y hora actual"
        )
        bl.addWidget(self._updated_checkbox)

        return bar

    def _build_props_scroll(self) -> QScrollArea:
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setObjectName("PropsScroll")

        self.props_container = QWidget()
        self.props_layout = QVBoxLayout(self.props_container)
        self.props_layout.setContentsMargins(0, 0, 0, 0)
        self.props_layout.setSpacing(1)
        self.props_layout.addStretch()

        self.scroll.setWidget(self.props_container)
        return self.scroll

    # ── File I/O ──────────────────────────────────────────────────────────

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir archivo Markdown", "", "Markdown (*.md);;Todos (*)"
        )
        if path:
            self._load_file(path)

    def _load_file(self, path: str):
        self.note.load(path)
        self._sync_ui_from_note()
        self.save_btn.setEnabled(True)
        self.file_loaded.emit(self.side)

    def _new_file(self):
        self.note.new_empty()
        self._sync_ui_from_note()
        self.save_btn.setEnabled(True)
        self.file_loaded.emit(self.side)

    def save_file(self):
        if self._updated_checkbox and self._updated_checkbox.isChecked():
            self.note.set_prop("updated", now_timestamp())
        # Sync body from editor: silent sync (no undo point for save itself)
        if not self._body_editor_widget._show_yaml:
            self.note.set_body_silent(self.body_edit.toPlainText())
        if not self.note.filepath:
            path, _ = QFileDialog.getSaveFileName(self, "Guardar", "", "Markdown (*.md)")
            if not path:
                return
        try:
            saved_path = self.note.save()
            self.path_lbl.setText(Path(saved_path).name)
            self.path_lbl.setToolTip(saved_path)
            QMessageBox.information(self, "Guardado", f"Archivo guardado:\n{saved_path}")
            self._update_undo_btn()
        except Exception as e:
            QMessageBox.critical(self, "Error al guardar", str(e))

    # ── Sync UI ↔ model ───────────────────────────────────────────────────

    def _sync_ui_from_note(self):
        """Rebuild rows and body editor from the NoteFile model."""
        display_name = Path(self.note.filepath).name if self.note.filepath else "Nuevo archivo"
        self.path_lbl.setText(display_name)
        self.path_lbl.setToolTip(self.note.filepath or "")
        self._body_editor_widget.refresh_from_note()
        self.rebuild_rows()
        self._update_undo_btn()

    def rebuild_rows(self, other_props: dict | None = None):
        """Clear and rebuild all property rows, sorted alphabetically.
        Accepts other_props dict (not just keys) to compute status colours.
        """
        if other_props is not None:
            self._status_map = compare_props(self.note.props, other_props)
        else:
            self._status_map = {}

        while self.props_layout.count() > 1:
            item = self.props_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.prop_rows.clear()
        self.row_checks.clear()

        for key in self.note.sorted_keys():
            status     = self._status_map.get(key, "")
            paired     = (other_props is None) or (key in other_props) or (
                status not in (LEFT_ONLY, RIGHT_ONLY, "")
            )
            other_val  = other_props.get(key) if other_props is not None else None
            self._insert_row(key, self.note.props[key], paired, status, other_val)

    def _insert_row(self, key: str, val, paired: bool = True,
                    status: str = "", other_val=None):
        """Create container + checkbox + PropRow and add to layout."""
        row_index = len(self.prop_rows)   # 0-based insertion order
        container = QFrame()
        container.setObjectName("RowContainer")

        rl = QHBoxLayout(container)
        rl.setContentsMargins(4, 0, 4, 0)
        rl.setSpacing(4)

        cb = QCheckBox()
        cb.setFixedWidth(20)
        rl.addWidget(cb)
        self.row_checks[key] = cb

        row = PropRow(key, val, self.side, paired,
                      row_index=row_index, parent=container)
        row.action_requested.connect(self._on_row_action)
        row.edit_committed.connect(self._on_edit_committed)
        if status:
            row.set_status(status, row_index)
        if other_val is not None:
            row.set_other_value(other_val)
        rl.addWidget(row)

        self.props_layout.insertWidget(self.props_layout.count() - 1, container)
        self.prop_rows[key] = row

    # ── Search / add-as-prop ──────────────────────────────────────────────

    def _search_in_body(self):
        """Highlight search term in body editor."""
        term = self._search_edit.text().strip()
        if not term:
            return
        body = self.body_edit.toPlainText()
        if term.lower() in body.lower():
            # Switch to body tab and let the user see the result
            self.tabs.setCurrentIndex(1)
            from PySide6.QtGui import QTextCursor, QTextDocument
            cursor = self.body_edit.document().find(term, 0, QTextDocument.FindFlag(0))
            if not cursor.isNull():
                self.body_edit.setTextCursor(cursor)
            mw = self._main_window()
            if mw:
                mw.statusBar().showMessage(f"'{term}' encontrado en el cuerpo.")
        else:
            mw = self._main_window()
            if mw:
                mw.statusBar().showMessage(f"'{term}' no encontrado en el cuerpo.")

    def _add_as_prop(self):
        """Add search field text as a new blank YAML property."""
        text = self._search_edit.text().strip()
        if not text:
            return
        # Use text as key, empty value
        self.set_prop(text, "")
        self._search_edit.clear()
        mw = self._main_window()
        if mw:
            mw._recompare(silent=True)
            mw.statusBar().showMessage(f"Propiedad '{text}' agregada.")

    def _add_as_tag(self):
        """Add search field text as an item in the 'tags' list property."""
        text = self._search_edit.text().strip()
        if not text:
            return
        self.add_to_list_prop("tags", text)
        self._search_edit.clear()
        mw = self._main_window()
        if mw:
            mw._recompare(silent=True)
            mw.statusBar().showMessage(f"'{text}' agregado a tags.")

    # ── Prop update helpers (go through NoteFile) ─────────────────────────

    def set_prop(self, key: str, value):
        self.note.set_prop(key, value)
        self._refresh_or_insert(key, value)
        self._update_undo_btn()
        self._sync_source_view()

    def set_prop_empty(self, key: str):
        self.note.set_prop_empty(key)
        self._refresh_or_insert(key, "")
        self._update_undo_btn()
        self._sync_source_view()

    def add_to_list_prop(self, key: str, value):
        self.note.add_to_list_prop(key, value)
        new_val = self.note.props[key]
        self._refresh_or_insert(key, new_val)
        self._update_undo_btn()
        self._sync_source_view()

    def delete_prop(self, key: str):
        self.note.delete_prop(key)
        if key in self.prop_rows:
            row = self.prop_rows.pop(key)
            container = row.parent()
            if container:
                self.props_layout.removeWidget(container)
                container.deleteLater()
        self.row_checks.pop(key, None)
        self._update_undo_btn()
        self._sync_source_view()

    def convert_to_wikilink(self, key: str):
        self.note.convert_prop_to_wikilink(key)
        if key in self.prop_rows:
            self.prop_rows[key].refresh(self.note.props.get(key, ""))
        self._update_undo_btn()
        self._sync_source_view()

    def _refresh_or_insert(self, key: str, value):
        if key in self.prop_rows:
            self.prop_rows[key].refresh(value)
        else:
            self._insert_row(key, value)

    def _sync_source_view(self):
        """Keep note body model in sync after prop mutations."""
        self.note._body = self.body_edit.toPlainText()

    # ── Undo ──────────────────────────────────────────────────────────────

    def _undo(self):
        """Delegate to BodyEditor which handles model + UI refresh."""
        self._body_editor_widget.undo()

    def _update_undo_btn(self):
        self.undo_btn.setEnabled(self.note.can_undo)

    # ── Bulk actions ──────────────────────────────────────────────────────

    def _toggle_all(self, state):
        for cb in self.row_checks.values():
            cb.setChecked(bool(state))

    def _selected_keys(self) -> list[str]:
        return [k for k, cb in self.row_checks.items() if cb.isChecked()]

    def _bulk_apply(self):
        idx = self.bulk_combo.currentIndex()
        if idx < 0 or idx >= len(BULK_ACTIONS):
            return
        _, action_id = BULK_ACTIONS[idx]
        keys = self._selected_keys()
        if not keys:
            return

        if action_id == ACTION_DELETE:
            reply = QMessageBox.question(
                self, "Eliminar propiedades",
                f"¿Eliminar {len(keys)} propiedad(es)?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        mw = self._main_window()
        for key in keys:
            row = self.prop_rows.get(key)
            if row:
                self._dispatch_action(action_id, self.side, row, mw)

        if mw:
            mw._recompare(silent=True)
            mw.statusBar().showMessage(f"Acción '{self.bulk_combo.currentText()}' aplicada a {len(keys)} fila(s).")

    def _bulk_copy_selected(self):
        """Quick copy of selected keys to the other panel."""
        mw = self._main_window()
        if not mw:
            return
        dst = mw.right_panel if self.side == "left" else mw.left_panel
        keys = self._selected_keys()
        import copy as _copy
        for key in keys:
            dst.set_prop(key, _copy.deepcopy(self.note.props[key]))
        if keys and mw:
            mw._recompare(silent=True)
            mw.statusBar().showMessage(f"{len(keys)} propiedad(es) copiada(s).")

    # ── Row action dispatcher (shared by single-row menu + bulk) ──────────

    def _on_row_action(self, action: str, side: str, row: PropRow):
        mw = self._main_window()
        self._dispatch_action(action, side, row, mw)
        if mw:
            mw._recompare(silent=True)

    def _dispatch_action(self, action: str, side: str, row: PropRow, mw):
        """
        Central dispatcher for all property actions.
        Used by both single-row menu and bulk apply.
        """
        import copy as _copy

        key   = row.key
        value = row.value

        src_panel: PropsPanel = self
        dst_panel: PropsPanel = (
            (mw.right_panel if side == "left" else mw.left_panel) if mw else self
        )

        if action == ACTION_COPY:
            dst_panel.set_prop(key, _copy.deepcopy(value))
            if mw: mw.statusBar().showMessage(f"'{key}' copiada.")

        elif action == ACTION_COPY_EMPTY:
            dst_panel.set_prop_empty(key)
            if mw: mw.statusBar().showMessage(f"'{key}' copiada vacía.")

        elif action == ACTION_ADD_LIST:
            items = value if isinstance(value, list) else [value]
            for v in items:
                dst_panel.add_to_list_prop(key, v)
            if mw: mw.statusBar().showMessage(f"'{key}' agregada como lista.")

        elif action == ACTION_COPY_WIKI:
            wiki_val = convert_value_to_wikilink(value) if not is_empty_value(value) else value
            dst_panel.set_prop(key, wiki_val)
            if mw: mw.statusBar().showMessage(f"'{key}' copiada como WikiLink.")

        elif action == ACTION_CONVERT_WIKI:
            src_panel.convert_to_wikilink(key)
            if mw: mw.statusBar().showMessage(f"'{key}' convertida a WikiLink.")

        elif action == ACTION_DELETE:
            if mw:
                reply = QMessageBox.question(
                    mw, "Eliminar propiedad",
                    f"¿Eliminar la propiedad '{key}'?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if reply != QMessageBox.Yes:
                    return
            src_panel.delete_prop(key)
            if mw: mw.statusBar().showMessage(f"'{key}' eliminada.")

    # ── Inline edit callback ───────────────────────────────────────────────

    def _on_edit_committed(self, old_key: str, new_key: str, new_val_text: str, row: PropRow):
        """Handle committed inline edit: rename key and/or update value."""
        # Parse value (comma-separated → list)
        new_val_text = new_val_text.strip()
        if "," in new_val_text:
            new_val = [v.strip() for v in new_val_text.split(",") if v.strip()]
        else:
            new_val = new_val_text

        if old_key != new_key:
            self.note.rename_prop(old_key, new_key)
            # Update internal dicts
            if old_key in self.prop_rows:
                self.prop_rows[new_key] = self.prop_rows.pop(old_key)
                self.prop_rows[new_key].refresh_key(new_key)
            if old_key in self.row_checks:
                self.row_checks[new_key] = self.row_checks.pop(old_key)

        self.note.set_prop(new_key, new_val)
        if new_key in self.prop_rows:
            self.prop_rows[new_key].refresh(new_val)

        self._update_undo_btn()
        mw = self._main_window()
        if mw:
            mw._recompare(silent=True)
            mw.statusBar().showMessage(f"Propiedad '{new_key}' editada.")

    # ── Helpers ───────────────────────────────────────────────────────────

    def _main_window(self) -> "MainWindow | None":
        from ui.main_window import MainWindow
        w = self
        while w:
            if isinstance(w, MainWindow):
                return w
            w = w.parent()
        return None
