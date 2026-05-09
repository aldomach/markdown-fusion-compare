"""
ui/body_editor.py
BodyEditor: unified body editor with view-mode switcher.

View modes (toolbar buttons, no separate tabs):
  📝 Cuerpo   — plain text, body only (no YAML)
  🗒 Fuente   — full file (YAML + body), plain text
  👁 Markdown — rendered HTML preview (read-only)

Toolbar extras:
  ¶           — toggle show/hide invisible characters
  🔍          — open Find & Replace dialog
  ≡ Líneas    — line operations menu
  🔗 Nodos    — Conectar Nodos collapsible panel

Right-click on editor: copy selection to other panel (3 positions).
"""

from __future__ import annotations
from typing import TYPE_CHECKING
import re

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame,
    QTextEdit, QPushButton, QLabel, QSpinBox, QCheckBox,
    QListWidget, QListWidgetItem, QAbstractItemView,
    QMenu, QSizePolicy, QToolButton, QButtonGroup
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QContextMenuEvent, QCursor, QColor,
    QTextOption, QTextCursor
)

from ui.highlighter import MdHighlighter
from core.node_dict import NodeDictionary

if TYPE_CHECKING:
    from ui.main_window import MainWindow

# ── Shared NodeDictionary ─────────────────────────────────────────────────────
_NODE_DICT: NodeDictionary | None = None

def get_node_dict() -> NodeDictionary:
    global _NODE_DICT
    if _NODE_DICT is None:
        _NODE_DICT = NodeDictionary()
    return _NODE_DICT

# ── Colour constants ──────────────────────────────────────────────────────────
_COLOUR_DICT   = QColor("#cba6f7")
_COLOUR_PHRASE = QColor("#89dceb")
_COLOUR_WORD   = QColor("#cdd6f4")
_COLOUR_HEADER = QColor("#585b70")

# ── View mode constants ───────────────────────────────────────────────────────
MODE_BODY     = "body"
MODE_SOURCE   = "source"
MODE_MARKDOWN = "markdown"


class BodyEditor(QWidget):
    """
    Unified body editor widget.
    Exposes self.editor (QTextEdit) for external access to body text.
    """

    def __init__(self, side: str, parent=None):
        super().__init__(parent)
        self.side = side
        self._mode = MODE_BODY
        self._pilcrow_on = False
        self._find_dlg = None
        self._build_ui()

    # ── Build ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        root.addWidget(self._build_toolbar())

        # Editor (plain text modes)
        self.editor = _BodyTextEdit(self.side, self)
        self.editor.setObjectName("BodyEdit")
        self.editor.setPlaceholderText("Cuerpo de la nota…")
        self._highlighter = MdHighlighter(self.editor.document(), body_only=True)
        root.addWidget(self.editor, stretch=1)

        # Markdown preview (shown only in markdown mode)
        from ui.markdown_view import MarkdownView
        self._md_view = MarkdownView(None)
        self._md_view.setVisible(False)
        root.addWidget(self._md_view, stretch=1)

        root.addWidget(self._build_nodos_container())

    def _build_toolbar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("BodyToolbar")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(4)

        # ── View mode buttons ─────────────────────────────────────────────
        self._btn_body   = self._mode_btn("📝 Cuerpo",   MODE_BODY)
        self._btn_source = self._mode_btn("🗒 Fuente",   MODE_SOURCE)
        self._btn_md     = self._mode_btn("👁 Markdown", MODE_MARKDOWN)

        self._mode_group = QButtonGroup(self)
        for btn in (self._btn_body, self._btn_source, self._btn_md):
            self._mode_group.addButton(btn)
            bl.addWidget(btn)
        self._btn_body.setChecked(True)

        bl.addSpacing(8)

        # ── Pilcrow ───────────────────────────────────────────────────────
        self._pilcrow_btn = QPushButton("¶")
        self._pilcrow_btn.setObjectName("PilcrowBtn")
        self._pilcrow_btn.setFixedSize(26, 24)
        self._pilcrow_btn.setCheckable(True)
        self._pilcrow_btn.setToolTip("Mostrar/ocultar caracteres invisibles")
        self._pilcrow_btn.toggled.connect(self._toggle_pilcrow)
        bl.addWidget(self._pilcrow_btn)

        # ── Find & Replace ────────────────────────────────────────────────
        find_btn = QPushButton("🔍")
        find_btn.setObjectName("SearchIconBtn")
        find_btn.setFixedSize(26, 24)
        find_btn.setToolTip("Buscar y Reemplazar")
        find_btn.clicked.connect(self._open_find_replace)
        bl.addWidget(find_btn)

        # ── Lines menu ────────────────────────────────────────────────────
        lines_btn = QPushButton("≡ Líneas ▾")
        lines_btn.setObjectName("NodosToggleBtn")
        lines_btn.setFixedHeight(24)
        lines_btn.clicked.connect(self._show_lines_menu)
        bl.addWidget(lines_btn)

        bl.addStretch()
        return bar

    def _mode_btn(self, label: str, mode: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setObjectName("ModeBtn")
        btn.setFixedHeight(24)
        btn.setCheckable(True)
        btn.clicked.connect(lambda: self._set_mode(mode))
        return btn

    # ── View modes ────────────────────────────────────────────────────────

    def _set_mode(self, mode: str):
        self._mode = mode
        is_md = (mode == MODE_MARKDOWN)
        self.editor.setVisible(not is_md)
        self._md_view.setVisible(is_md)

        if mode == MODE_MARKDOWN:
            self._md_view.refresh_from_text(self.editor.toPlainText())
            return

        # For BODY and SOURCE: update editor content
        self._refresh_editor_content()

        # Highlighting: body_only=True for BODY, False for SOURCE
        self._highlighter.setDocument(None)
        self._highlighter = MdHighlighter(
            self.editor.document(),
            body_only=(mode == MODE_BODY)
        )

    def _refresh_editor_content(self):
        """Fill editor with correct content for current mode."""
        panel = self._props_panel()
        if panel is None:
            return
        if self._mode == MODE_SOURCE:
            # Full file: YAML frontmatter + body
            content = panel.note.to_markdown()
        else:
            # Body only
            content = panel.note.body
        # Block signals to avoid triggering model updates while loading
        self.editor.blockSignals(True)
        self.editor.setPlainText(content)
        self.editor.blockSignals(False)

    def _props_panel(self):
        """Return the PropsPanel ancestor."""
        from ui.props_panel import PropsPanel
        w = self
        while w:
            if isinstance(w, PropsPanel):
                return w
            w = w.parent()
        return None

    # ── Pilcrow ───────────────────────────────────────────────────────────

    def _toggle_pilcrow(self, on: bool):
        self._pilcrow_on = on
        opt = self.editor.document().defaultTextOption()
        if on:
            opt.setFlags(
                opt.flags() |
                QTextOption.ShowTabsAndSpaces |
                QTextOption.ShowLineAndParagraphSeparators
            )
        else:
            opt.setFlags(
                opt.flags() &
                ~QTextOption.ShowTabsAndSpaces &
                ~QTextOption.ShowLineAndParagraphSeparators
            )
        self.editor.document().setDefaultTextOption(opt)

    # ── Find & Replace ────────────────────────────────────────────────────

    def _open_find_replace(self):
        from ui.find_replace_dialog import FindReplaceDialog
        if self._find_dlg is None or not self._find_dlg.isVisible():
            self._find_dlg = FindReplaceDialog(self.editor, self)
        self._find_dlg.show()
        self._find_dlg.raise_()
        self._find_dlg.activateWindow()

    # ── Lines menu ────────────────────────────────────────────────────────

    def _show_lines_menu(self):
        menu = QMenu(self)

        menu.addAction("Eliminar líneas duplicadas").triggered.connect(
            lambda: self._lines_op("dedup_all"))
        menu.addAction("Eliminar líneas duplicadas consecutivas").triggered.connect(
            lambda: self._lines_op("dedup_consecutive"))
        menu.addSeparator()
        menu.addAction("Ordenar A → Z  (todas)").triggered.connect(
            lambda: self._lines_op("sort_az_all"))
        menu.addAction("Ordenar Z → A  (todas)").triggered.connect(
            lambda: self._lines_op("sort_za_all"))
        menu.addSeparator()
        menu.addAction("Ordenar A → Z  (selección)").triggered.connect(
            lambda: self._lines_op("sort_az_sel"))
        menu.addAction("Ordenar Z → A  (selección)").triggered.connect(
            lambda: self._lines_op("sort_za_sel"))

        menu.exec(QCursor.pos())

    def _lines_op(self, op: str):
        cursor  = self.editor.textCursor()
        has_sel = cursor.hasSelection()

        if op in ("sort_az_sel", "sort_za_sel") and has_sel:
            text   = cursor.selectedText().replace("\u2029", "\n")
            lines  = text.splitlines()
            lines  = sorted(lines, reverse=(op == "sort_za_sel"))
            cursor.insertText("\n".join(lines))
            return

        # Whole-document operations
        full = self.editor.toPlainText()
        lines = full.splitlines()

        if op == "dedup_all":
            seen: set[str] = set()
            new_lines = []
            for l in lines:
                if l not in seen:
                    seen.add(l)
                    new_lines.append(l)
            lines = new_lines

        elif op == "dedup_consecutive":
            new_lines = []
            prev = object()
            for l in lines:
                if l != prev:
                    new_lines.append(l)
                prev = l
            lines = new_lines

        elif op == "sort_az_all":
            lines = sorted(lines)
        elif op == "sort_za_all":
            lines = sorted(lines, reverse=True)

        pos = cursor.position()
        self.editor.setPlainText("\n".join(lines))
        c = self.editor.textCursor()
        c.setPosition(min(pos, len("\n".join(lines))))
        self.editor.setTextCursor(c)

    # ── Public API (backward-compat with props_panel) ─────────────────────

    def toPlainText(self) -> str:
        return self.editor.toPlainText()

    def setPlainText(self, text: str):
        self.editor.setPlainText(text)
        if self._mode == MODE_MARKDOWN:
            self._md_view.refresh_from_text(text)

    # ── Nodos container ───────────────────────────────────────────────────

    def _build_nodos_container(self) -> QFrame:
        container = QFrame()
        container.setObjectName("NodosContainer")
        cl = QVBoxLayout(container)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)

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

        ctrl = QHBoxLayout()
        ctrl.setSpacing(6)
        ctrl.addWidget(QLabel("Mín. letras:"))

        self.min_len_spin = QSpinBox()
        self.min_len_spin.setMinimum(2)
        self.min_len_spin.setMaximum(50)
        self.min_len_spin.setValue(4)
        self.min_len_spin.setFixedWidth(58)
        ctrl.addWidget(self.min_len_spin)

        self.stopwords_cb = QCheckBox("Ignorar conectores")
        self.stopwords_cb.setChecked(True)
        ctrl.addWidget(self.stopwords_cb)

        self.search_btn = QPushButton("🔍 Buscar")
        self.search_btn.setObjectName("NodosSearchBtn")
        self.search_btn.setFixedHeight(26)
        self.search_btn.clicked.connect(self._on_nodos_search)
        ctrl.addWidget(self.search_btn)
        ctrl.addStretch()

        self.sel_all_btn = QPushButton("Sel. todo")
        self.sel_all_btn.setObjectName("BulkApplyBtn")
        self.sel_all_btn.setFixedHeight(24)
        self.sel_all_btn.clicked.connect(self._select_all_words)
        ctrl.addWidget(self.sel_all_btn)
        pl.addLayout(ctrl)

        self.word_list = QListWidget()
        self.word_list.setObjectName("NodosWordList")
        self.word_list.setFixedHeight(130)
        self.word_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.word_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.word_list.customContextMenuRequested.connect(self._word_ctx_menu)
        pl.addWidget(self.word_list)

        act_row = QHBoxLayout()
        act_row.setSpacing(6)

        apply_btn = QPushButton("🔗 Convertir seleccionadas a WikiLink")
        apply_btn.setObjectName("NodosApplyBtn")
        apply_btn.setFixedHeight(28)
        apply_btn.clicked.connect(self._on_nodos_apply)
        act_row.addWidget(apply_btn)

        save_btn = QPushButton("💾 Guardar en diccionario")
        save_btn.setObjectName("NodosSearchBtn")
        save_btn.setFixedHeight(28)
        save_btn.clicked.connect(self._save_selected_to_dict)
        act_row.addWidget(save_btn)
        pl.addLayout(act_row)

        return panel

    def _toggle_nodos_panel(self):
        self._nodos_visible = not self._nodos_visible
        self._nodos_panel.setVisible(self._nodos_visible)
        arrow = "▾" if self._nodos_visible else "▸"
        self._toggle_btn.setText(f"🔗 Conectar Nodos {arrow}")

    def _open_dict_dialog(self):
        from ui.node_dict_dialog import NodeDictDialog
        NodeDictDialog(get_node_dict(), self).exec()

    def _on_nodos_search(self):
        mw = self._main_window()
        if not mw:
            return
        left_body  = mw.left_panel.body_edit.toPlainText()
        right_body = mw.right_panel.body_edit.toPlainText()
        nd         = get_node_dict()
        result     = nd.find_candidates(
            left_body, right_body,
            self.min_len_spin.value(),
            self.stopwords_cb.isChecked()
        )
        self.word_list.clear()
        total = 0

        def add_header(label):
            item = QListWidgetItem(f"── {label} ──")
            item.setFlags(Qt.NoItemFlags)
            item.setForeground(_COLOUR_HEADER)
            self.word_list.addItem(item)

        def add_word(text, colour):
            nonlocal total
            item = QListWidgetItem(text)
            item.setCheckState(Qt.Checked)
            item.setForeground(colour)
            self.word_list.addItem(item)
            total += 1

        if result.from_dict:
            add_header("Del diccionario")
            for w in result.from_dict: add_word(w, _COLOUR_DICT)
        if result.multi_phrases:
            add_header("Frases en común")
            for w in result.multi_phrases: add_word(w, _COLOUR_PHRASE)
        if result.single_words:
            add_header("Palabras en común")
            for w in result.single_words: add_word(w, _COLOUR_WORD)

        if total == 0:
            item = QListWidgetItem("(sin coincidencias)")
            item.setFlags(Qt.NoItemFlags)
            item.setForeground(_COLOUR_HEADER)
            self.word_list.addItem(item)

        if mw:
            mw.statusBar().showMessage(
                f"Conectar Nodos: {total} candidato(s) — "
                f"{len(result.from_dict)} diccionario, "
                f"{len(result.multi_phrases)} frases, "
                f"{len(result.single_words)} palabras."
            )

    def _select_all_words(self):
        for i in range(self.word_list.count()):
            item = self.word_list.item(i)
            if item.flags() & Qt.ItemIsUserCheckable:
                item.setCheckState(Qt.Checked)

    def _get_checked_words(self) -> list[str]:
        return [
            self.word_list.item(i).text()
            for i in range(self.word_list.count())
            if (self.word_list.item(i).flags() & Qt.ItemIsUserCheckable
                and self.word_list.item(i).checkState() == Qt.Checked)
        ]

    def _on_nodos_apply(self):
        selected = self._get_checked_words()
        if selected:
            mw = self._main_window()
            if mw: mw.apply_node_connections(selected)

    def _save_selected_to_dict(self):
        selected = self._get_checked_words()
        added = get_node_dict().add_nodes(selected)
        mw = self._main_window()
        if mw:
            mw.statusBar().showMessage(f"{added} nodo(s) guardado(s) en el diccionario.")
        self._on_nodos_search()

    def _word_ctx_menu(self, pos):
        item = self.word_list.itemAt(pos)
        if not item or not (item.flags() & Qt.ItemIsUserCheckable):
            return
        word = item.text()
        menu = QMenu(self)
        menu.addAction("✔ Aceptar → guardar en diccionario").triggered.connect(
            lambda: self._item_accept(word))
        menu.addAction("🚫 Ignorar → lista negra").triggered.connect(
            lambda: self._item_blacklist(word))
        menu.addSeparator()
        menu.addAction("🔗 Convertir a WikiLink ahora").triggered.connect(
            lambda: self._apply_single(word))
        menu.exec(self.word_list.viewport().mapToGlobal(pos))

    def _item_accept(self, word):
        get_node_dict().add_node(word)
        mw = self._main_window()
        if mw: mw.statusBar().showMessage(f"'{word}' guardado en el diccionario.")
        self._on_nodos_search()

    def _item_blacklist(self, word):
        get_node_dict().add_blacklist(word)
        for i in range(self.word_list.count()):
            if self.word_list.item(i).text() == word:
                self.word_list.takeItem(i)
                break
        mw = self._main_window()
        if mw: mw.statusBar().showMessage(f"'{word}' agregado a la lista negra.")

    def _apply_single(self, word):
        mw = self._main_window()
        if mw: mw.apply_node_connections([word])

    def _main_window(self) -> "MainWindow | None":
        from ui.main_window import MainWindow
        w = self
        while w:
            if isinstance(w, MainWindow): return w
            w = w.parent()
        return None


# ── _BodyTextEdit ─────────────────────────────────────────────────────────────

class _BodyTextEdit(QTextEdit):
    """QTextEdit with right-click copy-to-other-panel menu."""

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
                # capture pos in closure correctly
                menu.addAction(label).triggered.connect(
                    lambda checked=False, p=pos:
                        self._copy_to_other(selected_text, p)
                )
        menu.exec(event.globalPos())

    def _copy_to_other(self, text: str, position: str):
        from ui.main_window import MainWindow
        mw: MainWindow | None = None
        w = self
        while w:
            if isinstance(w, MainWindow): mw = w; break
            w = w.parent()
        if not mw:
            return
        dst_panel = mw.right_panel if self.side == "left" else mw.left_panel
        dst_edit  = dst_panel.body_edit
        dst_body  = dst_edit.toPlainText()
        if text.strip() in dst_body:
            mw.statusBar().showMessage("El texto ya existe en el otro panel.")
            return
        if position == "cursor":
            c = dst_edit.textCursor()
            c.insertText(("\n" if not c.atStart() else "") + text)
            dst_edit.setTextCursor(c)
        elif position == "start":
            dst_edit.setPlainText(
                (text + "\n\n" + dst_body.lstrip()).rstrip() if dst_body.strip() else text
            )
        else:
            dst_edit.setPlainText(
                (dst_body.rstrip() + "\n\n" + text).lstrip() if dst_body.strip() else text
            )
        dst_panel.note.set_body(dst_edit.toPlainText())
        side_name = "derecho" if self.side == "left" else "izquierdo"
        mw.statusBar().showMessage(
            f"Selección copiada al panel {side_name} ({position})."
        )
