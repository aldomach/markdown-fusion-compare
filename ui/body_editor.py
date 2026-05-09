"""
ui/body_editor.py
BodyEditor: editor + Conectar Nodos panel with NodeDictionary integration.

Features:
  - Syntax highlighting (Markdown, body-only mode)
  - Right-click: copy selection to other panel at cursor / start / end
  - Conectar Nodos panel:
      · Min-length spinbox
      · Stop-words toggle checkbox
      · Search → finds single words + multi-word phrases in common
      · Results grouped by: Diccionario / Frases / Palabras
      · Per-item: accept → saves to dict | ignore → saves to blacklist
      · Bulk: select-all, convert selected to WikiLink in both panels
      · Button to open NodeDictDialog (manage dict + blacklist)
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame,
    QTextEdit, QPushButton, QLabel, QSpinBox, QCheckBox,
    QListWidget, QListWidgetItem, QAbstractItemView,
    QMenu, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QContextMenuEvent, QCursor, QColor

from ui.highlighter import MdHighlighter
from core.node_dict import NodeDictionary

if TYPE_CHECKING:
    from ui.main_window import MainWindow

# Shared NodeDictionary instance (one per application run)
_NODE_DICT: NodeDictionary | None = None


def get_node_dict() -> NodeDictionary:
    global _NODE_DICT
    if _NODE_DICT is None:
        _NODE_DICT = NodeDictionary()
    return _NODE_DICT


# ── Section colours in word list ─────────────────────────────────────────────
_COLOUR_DICT    = QColor("#cba6f7")   # purple  — from dictionary
_COLOUR_PHRASE  = QColor("#89dceb")   # cyan    — multi-word phrase
_COLOUR_WORD    = QColor("#cdd6f4")   # default — single word
_COLOUR_HEADER  = QColor("#585b70")   # grey    — section header


class BodyEditor(QWidget):
    """Full body-tab widget: editor + Conectar Nodos panel."""

    def __init__(self, side: str, parent=None):
        super().__init__(parent)
        self.side = side
        self._build_ui()

    # ── Build ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        self.editor = _BodyTextEdit(self.side, self)
        self.editor.setObjectName("BodyEdit")
        self.editor.setPlaceholderText("Cuerpo de la nota…")
        self._highlighter = MdHighlighter(self.editor.document(), body_only=True)
        root.addWidget(self.editor, stretch=1)

        root.addWidget(self._build_nodos_container())

    def _build_nodos_container(self) -> QFrame:
        container = QFrame()
        container.setObjectName("NodosContainer")
        cl = QVBoxLayout(container)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)

        # Toggle bar
        bar = QFrame()
        bar.setObjectName("NodosBar")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(0, 2, 0, 2)
        bl.setSpacing(6)

        self._nodos_visible = False
        self._toggle_btn = QPushButton("🔗 Conectar Nodos ▸")
        self._toggle_btn.setObjectName("NodosToggleBtn")
        self._toggle_btn.setFixedHeight(26)
        self._toggle_btn.clicked.connect(self._toggle_nodos_panel)
        bl.addWidget(self._toggle_btn)
        bl.addStretch()

        dict_btn = QPushButton("📚 Diccionario")
        dict_btn.setObjectName("NodosSearchBtn")
        dict_btn.setFixedHeight(24)
        dict_btn.setToolTip("Abrir el diccionario de nodos y lista negra")
        dict_btn.clicked.connect(self._open_dict_dialog)
        bl.addWidget(dict_btn)

        cl.addWidget(bar)

        self._nodos_panel = self._build_nodos_panel()
        self._nodos_panel.setVisible(False)
        cl.addWidget(self._nodos_panel)

        return container

    def _build_nodos_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("NodosPanelInner")
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(4, 4, 4, 4)
        pl.setSpacing(6)

        # ── Controls row ──────────────────────────────────────────────────
        ctrl = QHBoxLayout()
        ctrl.setSpacing(6)

        ctrl.addWidget(QLabel("Mín. letras:"))

        self.min_len_spin = QSpinBox()
        self.min_len_spin.setMinimum(2)
        self.min_len_spin.setMaximum(50)
        self.min_len_spin.setValue(4)
        self.min_len_spin.setFixedWidth(58)
        self.min_len_spin.setToolTip("Largo mínimo de palabra individual")
        ctrl.addWidget(self.min_len_spin)

        self.stopwords_cb = QCheckBox("Ignorar conectores")
        self.stopwords_cb.setChecked(True)
        self.stopwords_cb.setToolTip(
            "Excluye preposiciones y conectores comunes (de, en, con, the, and…)"
        )
        ctrl.addWidget(self.stopwords_cb)

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

        # ── Word list ─────────────────────────────────────────────────────
        self.word_list = QListWidget()
        self.word_list.setObjectName("NodosWordList")
        self.word_list.setFixedHeight(130)
        self.word_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.word_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.word_list.customContextMenuRequested.connect(self._word_list_context_menu)
        pl.addWidget(self.word_list)

        # ── Action buttons ────────────────────────────────────────────────
        act_row = QHBoxLayout()
        act_row.setSpacing(6)

        self.apply_btn = QPushButton("🔗 Convertir seleccionadas a WikiLink")
        self.apply_btn.setObjectName("NodosApplyBtn")
        self.apply_btn.setFixedHeight(28)
        self.apply_btn.clicked.connect(self._on_apply)
        act_row.addWidget(self.apply_btn)

        save_dict_btn = QPushButton("💾 Guardar en diccionario")
        save_dict_btn.setObjectName("NodosSearchBtn")
        save_dict_btn.setFixedHeight(28)
        save_dict_btn.setToolTip("Guarda los ítems seleccionados en el diccionario de nodos")
        save_dict_btn.clicked.connect(self._save_selected_to_dict)
        act_row.addWidget(save_dict_btn)

        pl.addLayout(act_row)

        return panel

    # ── Toggle ────────────────────────────────────────────────────────────

    def _toggle_nodos_panel(self):
        self._nodos_visible = not self._nodos_visible
        self._nodos_panel.setVisible(self._nodos_visible)
        arrow = "▾" if self._nodos_visible else "▸"
        self._toggle_btn.setText(f"🔗 Conectar Nodos {arrow}")

    def _open_dict_dialog(self):
        from ui.node_dict_dialog import NodeDictDialog
        dlg = NodeDictDialog(get_node_dict(), self)
        dlg.exec()

    # ── Search ────────────────────────────────────────────────────────────

    def _on_search(self):
        mw = self._main_window()
        if not mw:
            return

        left_body  = mw.left_panel.body_edit.toPlainText()
        right_body = mw.right_panel.body_edit.toPlainText()
        min_len    = self.min_len_spin.value()
        use_sw     = self.stopwords_cb.isChecked()

        nd      = get_node_dict()
        result  = nd.find_candidates(left_body, right_body, min_len, use_sw)

        self.word_list.clear()
        total = 0

        def add_header(label: str):
            item = QListWidgetItem(f"── {label} ──")
            item.setFlags(Qt.NoItemFlags)
            item.setForeground(_COLOUR_HEADER)
            self.word_list.addItem(item)

        def add_word(text: str, colour: QColor):
            nonlocal total
            item = QListWidgetItem(text)
            item.setCheckState(Qt.Checked)
            item.setForeground(colour)
            self.word_list.addItem(item)
            total += 1

        if result.from_dict:
            add_header("Del diccionario")
            for w in result.from_dict:
                add_word(w, _COLOUR_DICT)

        if result.multi_phrases:
            add_header("Frases en común")
            for w in result.multi_phrases:
                add_word(w, _COLOUR_PHRASE)

        if result.single_words:
            add_header("Palabras en común")
            for w in result.single_words:
                add_word(w, _COLOUR_WORD)

        if total == 0:
            item = QListWidgetItem("(sin coincidencias)")
            item.setFlags(Qt.NoItemFlags)
            item.setForeground(_COLOUR_HEADER)
            self.word_list.addItem(item)

        if mw:
            mw.statusBar().showMessage(
                f"Conectar Nodos: {total} candidato(s) encontrado(s) "
                f"({len(result.from_dict)} del diccionario, "
                f"{len(result.multi_phrases)} frases, "
                f"{len(result.single_words)} palabras)."
            )

    # ── Select all ────────────────────────────────────────────────────────

    def _select_all_words(self):
        for i in range(self.word_list.count()):
            item = self.word_list.item(i)
            if item.flags() & Qt.ItemIsUserCheckable:
                item.setCheckState(Qt.Checked)

    def _get_checked_words(self) -> list[str]:
        result = []
        for i in range(self.word_list.count()):
            item = self.word_list.item(i)
            if (item.flags() & Qt.ItemIsUserCheckable
                    and item.checkState() == Qt.Checked):
                result.append(item.text())
        return result

    # ── Apply WikiLinks ───────────────────────────────────────────────────

    def _on_apply(self):
        selected = self._get_checked_words()
        if not selected:
            return
        mw = self._main_window()
        if mw:
            mw.apply_node_connections(selected)

    # ── Save to dictionary ────────────────────────────────────────────────

    def _save_selected_to_dict(self):
        selected = self._get_checked_words()
        if not selected:
            return
        nd = get_node_dict()
        added = nd.add_nodes(selected)
        mw = self._main_window()
        if mw:
            mw.statusBar().showMessage(
                f"{added} nodo(s) guardado(s) en el diccionario."
            )
        # Refresh colours — dict entries get purple
        self._on_search()

    # ── Per-item context menu ─────────────────────────────────────────────

    def _word_list_context_menu(self, pos):
        item = self.word_list.itemAt(pos)
        if not item or not (item.flags() & Qt.ItemIsUserCheckable):
            return
        word = item.text()
        nd   = get_node_dict()
        menu = QMenu(self)

        menu.addAction("✔ Aceptar → guardar en diccionario").triggered.connect(
            lambda: self._item_accept(word)
        )
        menu.addAction("🚫 Ignorar → agregar a lista negra").triggered.connect(
            lambda: self._item_blacklist(word)
        )
        menu.addSeparator()
        menu.addAction("🔗 Convertir a WikiLink en ambos ahora").triggered.connect(
            lambda: self._apply_single(word)
        )
        menu.exec(self.word_list.viewport().mapToGlobal(pos))

    def _item_accept(self, word: str):
        get_node_dict().add_node(word)
        mw = self._main_window()
        if mw:
            mw.statusBar().showMessage(f"'{word}' guardado en el diccionario.")
        self._on_search()  # refresh to show updated colours

    def _item_blacklist(self, word: str):
        get_node_dict().add_blacklist(word)
        # Remove from list
        for i in range(self.word_list.count()):
            if self.word_list.item(i).text() == word:
                self.word_list.takeItem(i)
                break
        mw = self._main_window()
        if mw:
            mw.statusBar().showMessage(f"'{word}' agregado a la lista negra.")

    def _apply_single(self, word: str):
        mw = self._main_window()
        if mw:
            mw.apply_node_connections([word])

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
    """QTextEdit with right-click menu for copy-to-other-panel."""

    def __init__(self, side: str, parent: BodyEditor):
        super().__init__(parent)
        self.side = side

    def contextMenuEvent(self, event: QContextMenuEvent):
        menu = self.createStandardContextMenu()
        cursor        = self.textCursor()
        selected_text = cursor.selectedText().strip()

        if selected_text:
            menu.addSeparator()
            other = "derecha"   if self.side == "left" else "izquierda"
            arr   = "→"         if self.side == "left" else "←"
            for label, pos in [
                (f"{arr} Copiar al panel {other} — en posición del cursor", "cursor"),
                (f"{arr} Copiar al panel {other} — al principio",           "start"),
                (f"{arr} Copiar al panel {other} — al final",               "end"),
            ]:
                menu.addAction(label).triggered.connect(
                    lambda checked=False, p=pos:
                        self._copy_selection_to_other(selected_text, p)
                )

        menu.exec(event.globalPos())

    def _copy_selection_to_other(self, text: str, position: str):
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
        elif position == "start":
            new_body = (text + "\n\n" + dst_body.lstrip()).rstrip() if dst_body.strip() else text
            dst_edit.setPlainText(new_body)
        else:
            new_body = (dst_body.rstrip() + "\n\n" + text).lstrip() if dst_body.strip() else text
            dst_edit.setPlainText(new_body)

        dst_panel.note.set_body(dst_edit.toPlainText())
        side_name = "derecho" if self.side == "left" else "izquierdo"
        pos_name  = "posición del cursor" if position == "cursor" else position
        mw.statusBar().showMessage(f"Selección copiada al panel {side_name} ({pos_name}).")



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
        # Syntax highlighting (body-only mode: skip YAML frontmatter detection)
        self._highlighter = MdHighlighter(self.editor.document(), body_only=True)
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
