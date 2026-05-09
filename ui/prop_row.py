"""
ui/prop_row.py
PropRow: one row in the YAML properties list.
Responsibilities:
  - Display key + value
  - Inline editing (double-click or edit button)
  - Context menu (···) with all actions
  - Row highlight while menu is open
  - Emits action_requested(action_name, side, row) signal
"""

from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QSizePolicy, QMenu
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor

from core.utils import display_value, is_empty_value, is_wikilink


# Actions emitted via action_requested signal
# Keep in sync with BULK_ACTIONS list in props_panel.py
ACTION_COPY          = "copy"
ACTION_COPY_EMPTY    = "copy_empty"
ACTION_ADD_LIST      = "add_list"
ACTION_COPY_WIKI     = "copy_wiki"
ACTION_CONVERT_WIKI  = "convert_wiki"
ACTION_DELETE        = "delete"


class PropRow(QFrame):
    """Single property row widget."""

    action_requested = Signal(str, str, object)   # (action, side, self)
    edit_committed   = Signal(str, str, str, object)  # (old_key, new_key, new_val, self)

    def __init__(self, key: str, value, side: str, paired: bool = True, parent=None):
        super().__init__(parent)
        self.key    = key
        self.value  = value
        self.side   = side   # 'left' | 'right'
        self.paired = paired
        self._editing = False
        self._build_ui()
        self._set_base_style()

    # ── Build ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 1, 4, 1)
        layout.setSpacing(4)

        # ── Key label / edit ──────────────────────────────────────────────
        self.key_lbl = QLabel(self.key)
        self.key_lbl.setFixedWidth(130)
        self.key_lbl.setObjectName("PropKey")
        self.key_lbl.setToolTip(self.key)
        layout.addWidget(self.key_lbl)

        self.key_edit = QLineEdit(self.key)
        self.key_edit.setObjectName("PropKeyEdit")
        self.key_edit.setFixedWidth(130)
        self.key_edit.setVisible(False)
        layout.addWidget(self.key_edit)

        # ── Value label / edit ────────────────────────────────────────────
        dv = display_value(self.value)
        self.val_lbl = QLabel(dv)
        self.val_lbl.setObjectName("PropVal")
        self.val_lbl.setToolTip(dv)
        self.val_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self.val_lbl)

        self.val_edit = QLineEdit(self._value_for_edit(self.value))
        self.val_edit.setObjectName("PropValEdit")
        self.val_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.val_edit.setVisible(False)
        self.val_edit.returnPressed.connect(self._commit_edit)
        layout.addWidget(self.val_edit)

        # ── Edit button ───────────────────────────────────────────────────
        self.edit_btn = QPushButton("✎")
        self.edit_btn.setObjectName("PropEditBtn")
        self.edit_btn.setFixedSize(22, 22)
        self.edit_btn.setToolTip("Editar propiedad")
        self.edit_btn.clicked.connect(self._toggle_edit)
        layout.addWidget(self.edit_btn)

        # ── Action menu button ────────────────────────────────────────────
        self.menu_btn = QPushButton("···")
        self.menu_btn.setObjectName("PropBtn")
        self.menu_btn.setFixedSize(28, 22)
        self.menu_btn.clicked.connect(self._show_menu)
        layout.addWidget(self.menu_btn)

        # Double-click on value label also opens edit mode
        self.val_lbl.mouseDoubleClickEvent = lambda _e: self._toggle_edit()

    # ── Display helpers ───────────────────────────────────────────────────

    def _value_for_edit(self, value) -> str:
        """Flatten value to editable string. Lists become comma-separated."""
        if isinstance(value, list):
            return ", ".join(str(v) for v in value)
        return str(value)

    def _parse_edit_value(self, text: str):
        """Parse edited string back. If it contains commas → list."""
        text = text.strip()
        if "," in text:
            return [v.strip() for v in text.split(",") if v.strip()]
        return text

    def refresh(self, value):
        self.value = value
        dv = display_value(value)
        self.val_lbl.setText(dv)
        self.val_lbl.setToolTip(dv)
        if not self._editing:
            self.val_edit.setText(self._value_for_edit(value))

    def refresh_key(self, new_key: str):
        self.key = new_key
        self.key_lbl.setText(new_key)
        self.key_lbl.setToolTip(new_key)
        self.key_edit.setText(new_key)

    # ── Style helpers ─────────────────────────────────────────────────────

    def _set_base_style(self):
        name = "RowContainerUnpaired" if not self.paired else "RowContainer"
        if self.parent():
            self.parent().setObjectName(name)
            self.parent().style().unpolish(self.parent())
            self.parent().style().polish(self.parent())

    def _set_active_style(self, active: bool):
        container = self.parent()
        if not container:
            return
        if active:
            container.setObjectName("RowContainerActive")
        else:
            self._set_base_style()
        container.style().unpolish(container)
        container.style().polish(container)

    # ── Inline edit ───────────────────────────────────────────────────────

    def _toggle_edit(self):
        if self._editing:
            self._commit_edit()
        else:
            self._start_edit()

    def _start_edit(self):
        self._editing = True
        self.key_lbl.setVisible(False)
        self.key_edit.setVisible(True)
        self.key_edit.setText(self.key)

        self.val_lbl.setVisible(False)
        self.val_edit.setVisible(True)
        self.val_edit.setText(self._value_for_edit(self.value))
        self.val_edit.setFocus()
        self.val_edit.selectAll()

        self.edit_btn.setText("✔")
        self.edit_btn.setToolTip("Confirmar edición")

    def _commit_edit(self):
        new_key = self.key_edit.text().strip()
        new_val_text = self.val_edit.text()
        new_val = self._parse_edit_value(new_val_text)

        self._editing = False
        self.key_lbl.setVisible(True)
        self.key_edit.setVisible(False)
        self.val_lbl.setVisible(True)
        self.val_edit.setVisible(False)
        self.edit_btn.setText("✎")
        self.edit_btn.setToolTip("Editar propiedad")

        old_key = self.key
        self.edit_committed.emit(old_key, new_key, new_val_text, self)

        # Update local display
        self.key = new_key
        self.key_lbl.setText(new_key)
        self.key_lbl.setToolTip(new_key)
        self.refresh(new_val)

    # ── Context menu ──────────────────────────────────────────────────────

    def _show_menu(self):
        self._set_active_style(True)
        menu = QMenu(self)

        other = "derecha" if self.side == "left" else "izquierda"
        arr   = "→" if self.side == "left" else "←"

        _add = menu.addAction
        _add(f"{arr} Copiar a {other}").triggered.connect(
            lambda: self.action_requested.emit(ACTION_COPY, self.side, self))
        _add(f"{arr} Copiar vacía a {other}").triggered.connect(
            lambda: self.action_requested.emit(ACTION_COPY_EMPTY, self.side, self))
        _add(f"{arr} Agregar como ítem de lista a {other}").triggered.connect(
            lambda: self.action_requested.emit(ACTION_ADD_LIST, self.side, self))

        menu.addSeparator()

        _add(f"{arr} Copiar como WikiLink a {other}").triggered.connect(
            lambda: self.action_requested.emit(ACTION_COPY_WIKI, self.side, self))

        val_str = str(self.value) if not isinstance(self.value, list) else ""
        if not is_empty_value(self.value) and not is_wikilink(val_str):
            _add("⟳ Convertir a WikiLink (aquí)").triggered.connect(
                lambda: self.action_requested.emit(ACTION_CONVERT_WIKI, self.side, self))

        menu.addSeparator()
        _add("🗑 Eliminar propiedad").triggered.connect(
            lambda: self.action_requested.emit(ACTION_DELETE, self.side, self))

        menu.aboutToHide.connect(lambda: self._set_active_style(False))
        menu.exec(QCursor.pos())
