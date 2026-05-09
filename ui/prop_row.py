"""
ui/prop_row.py
PropRow: one row in the YAML properties list.

Changes in this version:
  - Buttons ✎ and ··· moved to LEFT of key label
  - Rich tooltip showing value from BOTH panels
  - Right-click anywhere on the row opens the full context menu
"""

from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QSizePolicy, QMenu
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor, QMouseEvent

from core.utils import display_value, is_empty_value, is_wikilink, value_to_str
from core.compare import (
    EQUAL, DIFF, WIKI_DIFF, LIST_PARTIAL,
    LEFT_ONLY, RIGHT_ONLY, EMPTY_DIFF,
)


# ── Action constants ──────────────────────────────────────────────────────────
# Keep in sync with BULK_ACTIONS in props_panel.py
ACTION_COPY         = "copy"
ACTION_COPY_EMPTY   = "copy_empty"
ACTION_ADD_LIST     = "add_list"
ACTION_COPY_WIKI    = "copy_wiki"
ACTION_CONVERT_WIKI = "convert_wiki"
ACTION_DELETE       = "delete"


# ── Status metadata ───────────────────────────────────────────────────────────
# status → (dot_colour, status_tooltip, container_objectName)
_STATUS_META: dict[str, tuple[str, str, str]] = {
    EQUAL:        ("#a6e3a1", "Igual en ambos paneles",                      "RowEqual"),
    DIFF:         ("#f9e2af", "Existe en ambos pero con valores diferentes", "RowDiff"),
    WIKI_DIFF:    ("#89dceb", "Mismo texto pero uno es WikiLink",             "RowWikiDiff"),
    LIST_PARTIAL: ("#cba6f7", "Lista con ítems parcialmente coincidentes",   "RowListPartial"),
    LEFT_ONLY:    ("#f38ba8", "Solo existe en el panel izquierdo",           "RowLeftOnly"),
    RIGHT_ONLY:   ("#b4befe", "Solo existe en el panel derecho",             "RowRightOnly"),
    EMPTY_DIFF:   ("#585b70", "Uno o ambos lados están vacíos",              "RowEmptyDiff"),
}
_DEFAULT_META = ("#45475a", "", "RowContainer")


class PropRow(QFrame):
    """Single property row widget."""

    action_requested = Signal(str, str, object)       # (action, side, self)
    edit_committed   = Signal(str, str, str, object)  # (old_key, new_key, new_val_text, self)

    def __init__(self, key: str, value, side: str, paired: bool = True, parent=None):
        super().__init__(parent)
        self.key          = key
        self.value        = value
        self.side         = side       # 'left' | 'right'
        self.paired       = paired
        self._status      = ""
        self._editing     = False
        self._other_value = None       # value from the opposite panel (for tooltip)
        self._build_ui()
        self._apply_container_name("RowContainerUnpaired" if not paired else "RowContainer")

    # ── Build ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 1, 4, 1)
        layout.setSpacing(4)

        # ── LEFT: edit button ─────────────────────────────────────────────
        self.edit_btn = QPushButton("✎")
        self.edit_btn.setObjectName("PropEditBtn")
        self.edit_btn.setFixedSize(22, 22)
        self.edit_btn.setToolTip("Editar propiedad")
        self.edit_btn.clicked.connect(self._toggle_edit)
        layout.addWidget(self.edit_btn)

        # ── LEFT: menu button ─────────────────────────────────────────────
        self.menu_btn = QPushButton("···")
        self.menu_btn.setObjectName("PropBtn")
        self.menu_btn.setFixedSize(28, 22)
        self.menu_btn.clicked.connect(self._show_menu)
        layout.addWidget(self.menu_btn)

        # ── Status dot ────────────────────────────────────────────────────
        self.status_dot = QLabel("●")
        self.status_dot.setFixedWidth(14)
        self.status_dot.setObjectName("StatusDot")
        self.status_dot.setStyleSheet("color: #45475a;")
        layout.addWidget(self.status_dot)

        # ── Key label / edit ──────────────────────────────────────────────
        self.key_lbl = QLabel(self.key)
        self.key_lbl.setFixedWidth(120)
        self.key_lbl.setObjectName("PropKey")
        layout.addWidget(self.key_lbl)

        self.key_edit = QLineEdit(self.key)
        self.key_edit.setObjectName("PropKeyEdit")
        self.key_edit.setFixedWidth(120)
        self.key_edit.setVisible(False)
        layout.addWidget(self.key_edit)

        # ── Value label / edit ────────────────────────────────────────────
        dv = display_value(self.value)
        self.val_lbl = QLabel(dv)
        self.val_lbl.setObjectName("PropVal")
        self.val_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self.val_lbl)

        self.val_edit = QLineEdit(self._value_for_edit(self.value))
        self.val_edit.setObjectName("PropValEdit")
        self.val_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.val_edit.setVisible(False)
        self.val_edit.returnPressed.connect(self._commit_edit)
        layout.addWidget(self.val_edit)

        # Double-click on value label also opens edit
        self.val_lbl.mouseDoubleClickEvent = lambda _e: self._toggle_edit()

        # Tooltip is applied to the whole frame
        self._update_tooltip()

    # ── Tooltip ───────────────────────────────────────────────────────────

    def set_other_value(self, other_value):
        """Called by PropsPanel after rebuild to inject the opposite panel value."""
        self._other_value = other_value
        self._update_tooltip()

    def _update_tooltip(self):
        """Build a rich tooltip showing both panels' values."""
        this_label  = "Izquierdo" if self.side == "left"  else "Derecho"
        other_label = "Derecho"   if self.side == "left"  else "Izquierdo"

        this_str  = value_to_str(self.value)

        if self._other_value is None:
            other_str = "(no existe en el otro panel)"
        else:
            other_str = value_to_str(self._other_value)

        tip = (
            f"<b>{this_label}:</b>  {this_str}<br>"
            f"<b>{other_label}:</b> {other_str}"
        )
        self.setToolTip(tip)
        self.val_lbl.setToolTip(tip)
        self.key_lbl.setToolTip(tip)

    # ── Status colour ─────────────────────────────────────────────────────

    def set_status(self, status: str):
        self._status = status
        colour, status_tip, container_name = _STATUS_META.get(status, _DEFAULT_META)
        self.status_dot.setStyleSheet(f"color: {colour};")
        self.status_dot.setToolTip(status_tip)
        self._apply_container_name(container_name)

    def _apply_container_name(self, name: str):
        container = self.parent()
        if container:
            container.setObjectName(name)
            container.style().unpolish(container)
            container.style().polish(container)

    # ── Active highlight ──────────────────────────────────────────────────

    def _set_active_style(self, active: bool):
        container = self.parent()
        if not container:
            return
        if active:
            container.setObjectName("RowContainerActive")
        else:
            _, _, name = _STATUS_META.get(self._status, _DEFAULT_META)
            self._apply_container_name(name)
            return
        container.style().unpolish(container)
        container.style().polish(container)

    # ── Right-click anywhere on the row ───────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.RightButton:
            self._show_menu()
        else:
            super().mousePressEvent(event)

    # ── Display helpers ───────────────────────────────────────────────────

    def _value_for_edit(self, value) -> str:
        if isinstance(value, list):
            return ", ".join(str(v) for v in value)
        return str(value)

    def _parse_edit_value(self, text: str):
        text = text.strip()
        if "," in text:
            return [v.strip() for v in text.split(",") if v.strip()]
        return text

    def refresh(self, value):
        self.value = value
        dv = display_value(value)
        self.val_lbl.setText(dv)
        if not self._editing:
            self.val_edit.setText(self._value_for_edit(value))
        self._update_tooltip()

    def refresh_key(self, new_key: str):
        self.key = new_key
        self.key_lbl.setText(new_key)
        self.key_lbl.setToolTip("")   # cleared; full tooltip on frame
        self.key_edit.setText(new_key)
        self._update_tooltip()

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
        new_key      = self.key_edit.text().strip()
        new_val_text = self.val_edit.text()
        new_val      = self._parse_edit_value(new_val_text)
        self._editing = False
        self.key_lbl.setVisible(True)
        self.key_edit.setVisible(False)
        self.val_lbl.setVisible(True)
        self.val_edit.setVisible(False)
        self.edit_btn.setText("✎")
        self.edit_btn.setToolTip("Editar propiedad")
        old_key = self.key
        self.edit_committed.emit(old_key, new_key, new_val_text, self)
        self.key = new_key
        self.key_lbl.setText(new_key)
        self.refresh(new_val)

    # ── Context menu ──────────────────────────────────────────────────────

    def _show_menu(self):
        self._set_active_style(True)
        menu = QMenu(self)

        other = "derecha" if self.side == "left" else "izquierda"
        arr   = "→"       if self.side == "left" else "←"

        def add(label, action_id):
            menu.addAction(label).triggered.connect(
                lambda: self.action_requested.emit(action_id, self.side, self)
            )

        add(f"{arr} Copiar a {other}",                     ACTION_COPY)
        add(f"{arr} Copiar vacía a {other}",               ACTION_COPY_EMPTY)
        add(f"{arr} Agregar como ítem de lista a {other}", ACTION_ADD_LIST)
        menu.addSeparator()
        add(f"{arr} Copiar como WikiLink a {other}",       ACTION_COPY_WIKI)

        val_str = str(self.value) if not isinstance(self.value, list) else ""
        if not is_empty_value(self.value) and not is_wikilink(val_str):
            add("⟳ Convertir a WikiLink (aquí)", ACTION_CONVERT_WIKI)

        menu.addSeparator()
        add("🗑 Eliminar propiedad", ACTION_DELETE)

        menu.aboutToHide.connect(lambda: self._set_active_style(False))
        menu.exec(QCursor.pos())