"""
ui/editor_toolbar.py
EditorToolbar: declarative, reusable toolbar builder.

To add a new button to any editor toolbar, just append an entry to the
TOOLBAR_BUTTONS list or call EditorToolbar.add_button() at runtime.

Each button definition is a dict:
  {
    "id":        str,            # unique id, used to get/enable/disable the button
    "label":     str,            # button text (can include emoji)
    "tooltip":   str,            # tooltip text
    "checkable": bool,           # True for toggle buttons (default False)
    "style":     str,            # QSS objectName (default "ToolbarBtn")
    "width":     int | None,     # fixed width (None = auto)
    "height":    int,            # fixed height (default 24)
    "separator_before": bool,    # add a separator line before this button
  }

Usage:
    tb = EditorToolbar(parent)
    tb.add_button(id="pilcrow", label="¶", tooltip="Mostrar invisibles",
                  checkable=True, style="PilcrowBtn")
    tb.button("pilcrow").toggled.connect(my_slot)
    layout.addWidget(tb)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable

from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QLabel, QCheckBox
from PySide6.QtCore import Qt


@dataclass
class ButtonDef:
    id:               str
    label:            str
    tooltip:          str         = ""
    checkable:        bool        = False
    style:            str         = "ToolbarBtn"
    width:            int | None  = None
    height:           int         = 24
    separator_before: bool        = False


class EditorToolbar(QFrame):
    """
    A horizontal toolbar that builds itself from a list of ButtonDef.
    Buttons are accessible by id via toolbar.button(id).

    Extras (not buttons):
      add_stretch()               — insert a stretcher
      add_label(text, object_name)— insert a QLabel
      add_checkbox(id, text, tooltip) — insert a QCheckBox; accessible via checkbox(id)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("EditorToolbar")
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(4, 2, 4, 2)
        self._layout.setSpacing(3)
        self._buttons:   dict[str, QPushButton] = {}
        self._checkboxes: dict[str, QCheckBox]  = {}

    # ── Button management ─────────────────────────────────────────────────

    def add_button(
        self,
        id:               str,
        label:            str,
        tooltip:          str        = "",
        checkable:        bool       = False,
        style:            str        = "ToolbarBtn",
        width:            int | None = None,
        height:           int        = 24,
        separator_before: bool       = False,
        slot:             Callable | None = None,
    ) -> QPushButton:
        """Add a button and return it."""
        if separator_before:
            sep = QFrame()
            sep.setFrameShape(QFrame.VLine)
            sep.setStyleSheet("color: #313244; margin: 2px 3px;")
            self._layout.addWidget(sep)

        btn = QPushButton(label)
        btn.setObjectName(style)
        btn.setToolTip(tooltip)
        btn.setCheckable(checkable)
        btn.setFixedHeight(height)
        if width:
            btn.setFixedWidth(width)

        if slot:
            if checkable:
                btn.toggled.connect(slot)
            else:
                btn.clicked.connect(slot)

        self._layout.addWidget(btn)
        self._buttons[id] = btn
        return btn

    def button(self, id: str) -> QPushButton | None:
        return self._buttons.get(id)

    def set_enabled(self, id: str, enabled: bool):
        btn = self._buttons.get(id)
        if btn:
            btn.setEnabled(enabled)

    def set_visible(self, id: str, visible: bool):
        btn = self._buttons.get(id)
        if btn:
            btn.setVisible(visible)

    # ── Checkbox management ───────────────────────────────────────────────

    def add_checkbox(
        self,
        id:      str,
        text:    str,
        tooltip: str  = "",
        checked: bool = False,
        slot:    Callable | None = None,
    ) -> QCheckBox:
        cb = QCheckBox(text)
        cb.setToolTip(tooltip)
        cb.setChecked(checked)
        if slot:
            cb.stateChanged.connect(slot)
        self._layout.addWidget(cb)
        self._checkboxes[id] = cb
        return cb

    def checkbox(self, id: str) -> QCheckBox | None:
        return self._checkboxes.get(id)

    # ── Layout helpers ────────────────────────────────────────────────────

    def add_stretch(self):
        self._layout.addStretch()

    def add_label(self, text: str, object_name: str = "") -> QLabel:
        lbl = QLabel(text)
        if object_name:
            lbl.setObjectName(object_name)
        self._layout.addWidget(lbl)
        return lbl

    def add_separator(self):
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #313244; margin: 2px 3px;")
        self._layout.addWidget(sep)
