"""
ui/prop_row.py
PropRow: one row in the YAML properties list.

Layout (left to right): [✎][···][●][key][value…]
- Buttons ✎ and ··· on the LEFT for unambiguous row identification
- Rich tooltip showing values from BOTH panels
- Right-click anywhere on the row opens the full context menu
- Status colour applied via direct setStyleSheet (reliable across platforms)
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
ACTION_COPY         = "copy"
ACTION_COPY_EMPTY   = "copy_empty"
ACTION_ADD_LIST     = "add_list"
ACTION_COPY_WIKI    = "copy_wiki"
ACTION_CONVERT_WIKI = "convert_wiki"
ACTION_DELETE       = "delete"


# ── Status → (dot_colour, left_border_colour, bg_even, bg_odd, status_tip) ───
# bg_even / bg_odd provide zebra striping within each status group
_STATUS_META: dict[str, tuple[str, str, str, str, str]] = {
    EQUAL:        ("#a6e3a1", "#a6e3a1", "#1a2e1a", "#1d321d",
                   "Igual en ambos paneles"),
    DIFF:         ("#f9e2af", "#f9e2af", "#2e2a1a", "#32301e",
                   "Existe en ambos pero con valores diferentes"),
    WIKI_DIFF:    ("#89dceb", "#89dceb", "#1a2a2e", "#1e2e32",
                   "Mismo texto pero uno es WikiLink"),
    LIST_PARTIAL: ("#cba6f7", "#cba6f7", "#251a2e", "#291e32",
                   "Lista con ítems parcialmente coincidentes"),
    LEFT_ONLY:    ("#f38ba8", "#f38ba8", "#2e1a1a", "#321e1e",
                   "Solo existe en el panel izquierdo"),
    RIGHT_ONLY:   ("#b4befe", "#b4befe", "#1a1a2e", "#1e1e32",
                   "Solo existe en el panel derecho"),
    EMPTY_DIFF:   ("#585b70", "#585b70", "#222228", "#26262c",
                   "Uno o ambos lados están vacíos"),
}
# Neutral zebra (no status yet)
_NEUTRAL_EVEN = "#1e1e2e"
_NEUTRAL_ODD  = "#222236"
_ACTIVE_BG    = "#2a2a4e"
_ACTIVE_BORDER = "#89b4fa"


def _row_stylesheet(bg: str, border_colour: str, active: bool = False) -> str:
    bg_use     = _ACTIVE_BG     if active else bg
    bdr_colour = _ACTIVE_BORDER if active else border_colour
    return (
        f"QFrame {{ background: {bg_use}; "
        f"border-left: 3px solid {bdr_colour}; "
        f"border-bottom: 1px solid #2a2a3e; }}"
    )


class PropRow(QFrame):
    """Single property row widget."""

    action_requested = Signal(str, str, object)       # (action, side, self)
    edit_committed   = Signal(str, str, str, object)  # (old_key, new_key, new_val_text, self)

    def __init__(self, key: str, value, side: str, paired: bool = True,
                 row_index: int = 0, parent=None):
        super().__init__(parent)
        self.key         = key
        self.value       = value
        self.side        = side
        self.paired      = paired
        self.row_index   = row_index   # 0-based; used for zebra striping
        self._status     = ""
        self._editing    = False
        self._other_value = None
        self._build_ui()
        self._apply_style()

    # ── Build ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 1, 4, 1)
        layout.setSpacing(3)

        # Edit button (left)
        self.edit_btn = QPushButton("✎")
        self.edit_btn.setObjectName("PropEditBtn")
        self.edit_btn.setFixedSize(22, 22)
        self.edit_btn.setToolTip("Editar propiedad")
        self.edit_btn.clicked.connect(self._toggle_edit)
        layout.addWidget(self.edit_btn)

        # Menu button (left)
        self.menu_btn = QPushButton("···")
        self.menu_btn.setObjectName("PropBtn")
        self.menu_btn.setFixedSize(28, 22)
        self.menu_btn.clicked.connect(self._show_menu)
        layout.addWidget(self.menu_btn)

        # Status dot
        self.status_dot = QLabel("●")
        self.status_dot.setFixedWidth(14)
        self.status_dot.setObjectName("StatusDot")
        self.status_dot.setStyleSheet("color: #45475a; background: transparent;")
        layout.addWidget(self.status_dot)

        # Key label / edit
        self.key_lbl = QLabel(self.key)
        self.key_lbl.setFixedWidth(120)
        self.key_lbl.setObjectName("PropKey")
        layout.addWidget(self.key_lbl)

        self.key_edit = QLineEdit(self.key)
        self.key_edit.setObjectName("PropKeyEdit")
        self.key_edit.setFixedWidth(120)
        self.key_edit.setVisible(False)
        layout.addWidget(self.key_edit)

        # Value label / edit
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

        self.val_lbl.mouseDoubleClickEvent = lambda _e: self._toggle_edit()
        self._update_tooltip()

    # ── Style (colour + zebra) ────────────────────────────────────────────

    def _apply_style(self, active: bool = False):
        is_odd = (self.row_index % 2 == 1)
        if self._status and self._status in _STATUS_META:
            dot_c, border_c, bg_even, bg_odd, _ = _STATUS_META[self._status]
            bg = bg_odd if is_odd else bg_even
            self.status_dot.setStyleSheet(f"color: {dot_c}; background: transparent;")
        else:
            border_c = "#313244"
            bg = _NEUTRAL_ODD if is_odd else _NEUTRAL_EVEN
            self.status_dot.setStyleSheet("color: #45475a; background: transparent;")

        self.setStyleSheet(_row_stylesheet(bg, border_c, active))

    def set_status(self, status: str, row_index: int | None = None):
        if row_index is not None:
            self.row_index = row_index
        self._status = status
        if status in _STATUS_META:
            _, _, _, _, tip = _STATUS_META[status]
            self.status_dot.setToolTip(tip)
        self._apply_style()

    def set_row_index(self, index: int):
        self.row_index = index
        self._apply_style()

    # ── Tooltip ───────────────────────────────────────────────────────────

    def set_other_value(self, other_value):
        self._other_value = other_value
        self._update_tooltip()

    def _update_tooltip(self):
        this_label  = "Izquierdo" if self.side == "left" else "Derecho"
        other_label = "Derecho"   if self.side == "left" else "Izquierdo"
        this_str    = value_to_str(self.value)
        other_str   = value_to_str(self._other_value) if self._other_value is not None \
                      else "(no existe en el otro panel)"
        tip = (
            f"<b>{this_label}:</b>  {this_str}<br>"
            f"<b>{other_label}:</b> {other_str}"
        )
        self.setToolTip(tip)
        self.val_lbl.setToolTip(tip)
        self.key_lbl.setToolTip(tip)

    # ── Right-click anywhere ──────────────────────────────────────────────

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
        self._apply_style(active=True)
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

        menu.aboutToHide.connect(lambda: self._apply_style(active=False))
        menu.exec(QCursor.pos())

