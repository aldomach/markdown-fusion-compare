"""
ui/body_editor.py
BodyEditor: QTextEdit subclass for the body tab of each panel.

Features:
  - Right-click context menu with "Copiar selección al otro panel"
  - Toolbar bar below the editor: "🔗 Conectar Nodos"
    · Minimum-length spin box
    · "Buscar" button → finds words common to both panels
    · Result list (checkable) → "Convertir a WikiLink en ambos" button

No logic for finding common words lives here; it calls
MainWindow.find_common_words() and MainWindow.apply_node_connections().
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame,
    QTextEdit, QPushButton, QLabel, QSpinBox,
    QListWidget, QListWidgetItem, QAbstractItemView,
    QMenu, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QContextMenuEvent, QCursor

if TYPE_CHECKING:
    from ui.main_window import MainWindow


class BodyEditor(QWidget):
    """
    Full body-tab widget: editor + Conectar Nodos panel.
    Exposed attributes:
      self.editor  — the QTextEdit
    """

    def __init__(self, side: str, parent=None):
        super().__init__(parent)
        self.side = side
        self._build_ui()

    # ── Build ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        # ── Text editor ───────────────────────────────────────────────────
        self.editor = _BodyTextEdit(self.side, self)
        self.editor.setObjectName("BodyEdit")
        self.editor.setPlaceholderText("Cuerpo de la nota…")
        root.addWidget(self.editor, stretch=1)

        # ── Conectar Nodos bar ────────────────────────────────────────────
        root.addWidget(self._build_nodos_bar())

    def _build_nodos_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("NodosBar")

        bl = QHBoxLayout(bar)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(6)

        # Collapsible toggle button
        self._nodos_visible = False
        self._toggle_btn = QPushButton("🔗 Conectar Nodos ▸")
        self._toggle_btn.setObjectName("NodosToggleBtn")
        self._toggle_btn.setFixedHeight(26)
        self._toggle_btn.clicked.connect(self._toggle_nodos_panel)
        bl.addWidget(self._toggle_btn)
        bl.addStretch()

        # Panel (hidden by default)
        self._nodos_panel = self._build_nodos_panel()
        self._nodos_panel.setVisible(False)

        # Wrap bar + panel in a vertical layout
        wrapper = QWidget()
        wl = QVBoxLayout(wrapper)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(4)
        wl.addWidget(bar)
        wl.addWidget(self._nodos_panel)

        # Replace root's last widget with wrapper — we need to return
        # a single widget, so we build a container
        container = QFrame()
        container.setObjectName("NodosContainer")
        cl = QVBoxLayout(container)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        cl.addWidget(bar)
        cl.addWidget(self._nodos_panel)
        return container

    def _build_nodos_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("NodosPanelInner")
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(0, 4, 0, 0)
        pl.setSpacing(6)

        # Controls row
        ctrl = QHBoxLayout()
        ctrl.setSpacing(6)

        ctrl.addWidget(QLabel("Mín. caracteres:"))

        self.min_len_spin = QSpinBox()
        self.min_len_spin.setMinimum(2)
        self.min_len_spin.setMaximum(50)
        self.min_len_spin.setValue(4)
        self.min_len_spin.setFixedWidth(64)
        self.min_len_spin.setToolTip("Largo mínimo de palabra para ser considerada")
        ctrl.addWidget(self.min_len_spin)

        self.search_btn = QPushButton("🔍 Buscar")
        self.search_btn.setObjectName("NodosSearchBtn")
        self.search_btn.setFixedHeight(26)
        self.search_btn.clicked.connect(self._on_search)
        ctrl.addWidget(self.search_btn)

        ctrl.addStretch()

        self.sel_all_btn = QPushButton("Sel. todo")
        self.sel_all_btn.setObjectName("BulkApplyBtn")
        self.sel_all_btn.setFixedHeight(24)
        self.sel_all_btn.clicked.connect(self._select_all_words)
        ctrl.addWidget(self.sel_all_btn)

        pl.addLayout(ctrl)

        # Word list
        self.word_list = QListWidget()
        self.word_list.setObjectName("NodosWordList")
        self.word_list.setFixedHeight(110)
        self.word_list.setSelectionMode(QAbstractItemView.NoSelection)
        pl.addWidget(self.word_list)

        # Apply button
        self.apply_btn = QPushButton("🔗 Convertir seleccionadas a WikiLink en ambos paneles")
        self.apply_btn.setObjectName("NodosApplyBtn")
        self.apply_btn.setFixedHeight(28)
        self.apply_btn.clicked.connect(self._on_apply)
        pl.addWidget(self.apply_btn)

        return panel

    # ── Toggle ────────────────────────────────────────────────────────────

    def _toggle_nodos_panel(self):
        self._nodos_visible = not self._nodos_visible
        self._nodos_panel.setVisible(self._nodos_visible)
        arrow = "▾" if self._nodos_visible else "▸"
        self._toggle_btn.setText(f"🔗 Conectar Nodos {arrow}")

    # ── Search / Apply ────────────────────────────────────────────────────

    def _on_search(self):
        mw = self._main_window()
        if not mw:
            return
        min_len = self.min_len_spin.value()
        words = mw.find_common_words(min_len)
        self.word_list.clear()
        if not words:
            item = QListWidgetItem("(sin coincidencias)")
            item.setFlags(Qt.NoItemFlags)
            self.word_list.addItem(item)
            return
        for word in sorted(words):
            item = QListWidgetItem(word)
            item.setCheckState(Qt.Checked)
            self.word_list.addItem(item)
        mw.statusBar().showMessage(f"Conectar Nodos: {len(words)} palabra(s) en común encontradas.")

    def _select_all_words(self):
        for i in range(self.word_list.count()):
            item = self.word_list.item(i)
            if item.flags() & Qt.ItemIsUserCheckable:
                item.setCheckState(Qt.Checked)

    def _on_apply(self):
        selected: list[str] = []
        for i in range(self.word_list.count()):
            item = self.word_list.item(i)
            if item.flags() & Qt.ItemIsUserCheckable and item.checkState() == Qt.Checked:
                selected.append(item.text())
        if not selected:
            return
        mw = self._main_window()
        if mw:
            mw.apply_node_connections(selected)

    # ── Convenience ───────────────────────────────────────────────────────

    def toPlainText(self) -> str:
        return self.editor.toPlainText()

    def setPlainText(self, text: str):
        self.editor.setPlainText(text)

    def _main_window(self) -> "MainWindow | None":
        from ui.main_window import MainWindow
        w = self
        while w:
            if isinstance(w, MainWindow):
                return w
            w = w.parent()
        return None


# ── Internal QTextEdit subclass ───────────────────────────────────────────────

class _BodyTextEdit(QTextEdit):
    """QTextEdit with a custom right-click menu that adds copy-to-other-panel."""

    def __init__(self, side: str, parent: BodyEditor):
        super().__init__(parent)
        self.side = side
        self._body_editor = parent   # BodyEditor reference

    def contextMenuEvent(self, event: QContextMenuEvent):
        menu = self.createStandardContextMenu()

        cursor        = self.textCursor()
        selected_text = cursor.selectedText().strip()

        if selected_text:
            menu.addSeparator()
            other  = "derecha"   if self.side == "left" else "izquierda"
            arr    = "→"         if self.side == "left" else "←"

            menu.addAction(
                f"{arr} Copiar selección al panel {other} — en posición del cursor"
            ).triggered.connect(
                lambda: self._copy_selection_to_other(selected_text, "cursor")
            )
            menu.addAction(
                f"{arr} Copiar selección al panel {other} — al principio"
            ).triggered.connect(
                lambda: self._copy_selection_to_other(selected_text, "start")
            )
            menu.addAction(
                f"{arr} Copiar selección al panel {other} — al final"
            ).triggered.connect(
                lambda: self._copy_selection_to_other(selected_text, "end")
            )

        menu.exec(event.globalPos())

    def _copy_selection_to_other(self, text: str, position: str):
        """Copy selected text to the other panel at the given position.

        position:
          'cursor' — inserted at the other panel's current cursor position
          'start'  — prepended to the body
          'end'    — appended to the body
        Deduplication: if the exact text already exists in the destination, skip.
        """
        from ui.main_window import MainWindow
        mw: MainWindow | None = None
        w = self
        while w:
            if isinstance(w, MainWindow):
                mw = w
                break
            w = w.parent()
        if not mw:
            return

        dst_panel = mw.right_panel if self.side == "left" else mw.left_panel
        dst_edit  = dst_panel.body_edit
        dst_body  = dst_edit.toPlainText()

        if text.strip() in dst_body:
            mw.statusBar().showMessage("El texto seleccionado ya existe en el otro panel.")
            return

        if position == "cursor":
            dst_cursor = dst_edit.textCursor()
            dst_cursor.insertText(("\n" if not dst_cursor.atStart() else "") + text)
            dst_edit.setTextCursor(dst_cursor)
            new_body = dst_edit.toPlainText()

        elif position == "start":
            new_body = (text + "\n\n" + dst_body.lstrip()).rstrip() if dst_body.strip() else text

        else:  # end
            new_body = (dst_body.rstrip() + "\n\n" + text).lstrip() if dst_body.strip() else text

        if position != "cursor":
            dst_edit.setPlainText(new_body)

        dst_panel.note.set_body(dst_edit.toPlainText())
        mw.statusBar().showMessage(
            f"Selección copiada al panel {'derecho' if self.side == 'left' else 'izquierdo'} "
            f"({'posición del cursor' if position == 'cursor' else position})."
        )