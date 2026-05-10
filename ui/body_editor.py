"""
ui/body_editor.py
BodyEditor: unified body/source editor with view-mode switcher.

Architecture
============
One QTextEdit for all editing modes.  Mode is controlled by:
  - [📝 Editar | 👁 Markdown] toggle (edit vs preview)
  - [☐ Mostrar YAML] checkbox (show/hide frontmatter in edit mode)

Ctrl+Z / Ctrl+Y are intercepted and routed through NoteFile.undo().
The editor uses a 800ms debounce timer: while the user is typing,
body changes are written to NoteFile silently (no undo point).
After 800ms of inactivity a checkpoint() is pushed = one undo step
per "burst" of typing, not per keystroke.

Toolbar is built with EditorToolbar (declarative, easy to extend).
Conectar Nodos panel is shown only in edit mode.

Sync modes:
  When "Sincronizar vista" is ON (managed by MainWindow),
  switching mode in one panel mirrors the other.
"""

from __future__ import annotations
from typing import TYPE_CHECKING
import re

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame,
    QTextEdit, QPushButton, QLabel, QSpinBox, QCheckBox,
    QListWidget, QListWidgetItem, QAbstractItemView,
    QMenu, QSizePolicy, QButtonGroup
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import (
    QContextMenuEvent, QCursor, QColor,
    QTextOption, QTextCursor, QKeySequence, QKeyEvent
)

from ui.editor_toolbar import EditorToolbar
from ui.highlighter import MdHighlighter
from core.node_dict import NodeDictionary

if TYPE_CHECKING:
    from ui.main_window import MainWindow
    from ui.props_panel import PropsPanel

# ── Shared NodeDictionary ─────────────────────────────────────────────────────
_NODE_DICT: NodeDictionary | None = None

def get_node_dict() -> NodeDictionary:
    global _NODE_DICT
    if _NODE_DICT is None:
        _NODE_DICT = NodeDictionary()
    return _NODE_DICT

# ── Colours for word list ─────────────────────────────────────────────────────
_C_DICT   = QColor("#cba6f7")
_C_PHRASE = QColor("#89dceb")
_C_WORD   = QColor("#cdd6f4")
_C_HDR    = QColor("#585b70")

# ── Debounce delay (ms) ───────────────────────────────────────────────────────
_DEBOUNCE_MS = 800


class BodyEditor(QWidget):
    """
    Unified editor widget placed directly below the YAML props panel.
    Exposes:
      self.editor      — the QTextEdit (always present)
      self.body_edit   — alias for self.editor (backward compat)
    Signals:
      mode_changed(str) — emitted when edit/markdown mode changes
    """

    mode_changed = Signal(str)   # "edit" or "markdown"

    def __init__(self, side: str, parent: "PropsPanel | None" = None):
        super().__init__(parent)
        self.side        = side
        self._show_yaml  = False   # checkbox state
        self._in_md_mode = False   # True = markdown preview
        self._syncing    = False   # prevents recursive content reload

        # Debounce timer for undo checkpoints
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(_DEBOUNCE_MS)
        self._debounce.timeout.connect(self._on_debounce_timeout)

        self._find_dlg = None
        self._build_ui()

    # ── Build ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 4, 0, 0)
        root.setSpacing(4)

        # ── Toolbar ───────────────────────────────────────────────────────
        self.toolbar = EditorToolbar(self)

        # Edit / Markdown toggle group
        self._btn_edit = self.toolbar.add_button(
            "edit", "📝 Editar", "Modo edición", checkable=True, style="ModeBtn")
        self._btn_md = self.toolbar.add_button(
            "markdown", "👁 Markdown", "Vista previa", checkable=True, style="ModeBtn")

        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self._btn_edit)
        self._mode_group.addButton(self._btn_md)
        self._btn_edit.setChecked(True)

        self._btn_edit.clicked.connect(lambda: self._set_mode("edit"))
        self._btn_md.clicked.connect(lambda: self._set_mode("markdown"))

        self.toolbar.add_separator()

        # Show YAML checkbox
        self._yaml_cb = self.toolbar.add_checkbox(
            "show_yaml", "Mostrar YAML",
            tooltip="Muestra el bloque YAML al inicio del editor",
            checked=False,
            slot=self._on_yaml_toggle,
        )

        self.toolbar.add_separator()

        # Pilcrow
        self.toolbar.add_button(
            "pilcrow", "¶", "Mostrar/ocultar caracteres invisibles",
            checkable=True, style="PilcrowBtn", width=26,
            slot=self._toggle_pilcrow,
        )

        # Find & Replace
        self.toolbar.add_button(
            "find", "🔍", "Buscar y Reemplazar",
            style="SearchIconBtn", width=26,
            slot=self._open_find_replace,
        )

        # Lines menu
        self.toolbar.add_button(
            "lines", "≡ Líneas ▾", "Operaciones sobre líneas",
            style="NodosToggleBtn",
            slot=self._show_lines_menu,
        )

        self.toolbar.add_stretch()
        root.addWidget(self.toolbar)

        # ── Editor ────────────────────────────────────────────────────────
        self.editor = _BodyTextEdit(self.side, self)
        self.editor.setObjectName("BodyEdit")
        self.editor.setPlaceholderText("Cuerpo de la nota…")
        self.editor.setUndoRedoEnabled(False)  # we handle undo ourselves
        self._highlighter = MdHighlighter(self.editor.document(), body_only=True)

        # Connect text changes to debounce
        self.editor.textChanged.connect(self._on_text_changed)

        root.addWidget(self.editor, stretch=1)

        # ── Markdown preview (hidden until md mode) ───────────────────────
        from ui.markdown_view import MarkdownView
        self._md_view = MarkdownView(None)
        self._md_view.setVisible(False)
        root.addWidget(self._md_view, stretch=1)

        # ── Conectar Nodos ────────────────────────────────────────────────
        self._nodos_container = self._build_nodos_container()
        root.addWidget(self._nodos_container)

        # Backward compat alias
        self.body_edit = self.editor

    # ── Mode switching ────────────────────────────────────────────────────

    def _set_mode(self, mode: str):
        """Switch between 'edit' and 'markdown'."""
        self._in_md_mode = (mode == "markdown")
        self.editor.setVisible(not self._in_md_mode)
        self._md_view.setVisible(self._in_md_mode)
        self._nodos_container.setVisible(not self._in_md_mode)
        self.toolbar.set_enabled("pilcrow", not self._in_md_mode)
        self.toolbar.set_enabled("find",    not self._in_md_mode)
        self.toolbar.set_enabled("lines",   not self._in_md_mode)
        self.toolbar.set_enabled("show_yaml", not self._in_md_mode)

        if self._in_md_mode:
            # Render body only (never include YAML in markdown preview)
            body = self._get_body_only()
            self._md_view.refresh_from_text(body)

        self.mode_changed.emit(mode)

    def get_mode(self) -> str:
        return "markdown" if self._in_md_mode else "edit"

    def set_mode_external(self, mode: str):
        """Called by MainWindow when sync-view is on."""
        if mode == "markdown":
            self._btn_md.setChecked(True)
        else:
            self._btn_edit.setChecked(True)
        self._set_mode(mode)

    # ── YAML toggle ───────────────────────────────────────────────────────

    def _on_yaml_toggle(self, state: int):
        self._show_yaml = bool(state)
        self._reload_editor_content()
        # Update highlighter mode
        self._highlighter.setDocument(None)
        self._highlighter = MdHighlighter(
            self.editor.document(),
            body_only=not self._show_yaml
        )

    def _reload_editor_content(self):
        """Fill editor with correct content (body only or full file)."""
        if self._syncing:
            return
        panel = self._props_panel()
        if panel is None:
            return
        if self._show_yaml:
            content = panel.note.to_markdown()
        else:
            content = panel.note.body
        self._syncing = True
        cursor_pos = self.editor.textCursor().position()
        self.editor.setPlainText(content)
        # Restore cursor
        cursor = self.editor.textCursor()
        cursor.setPosition(min(cursor_pos, len(content)))
        self.editor.setTextCursor(cursor)
        self._syncing = False

    def _get_body_only(self) -> str:
        """Return body text regardless of YAML visibility."""
        panel = self._props_panel()
        if panel:
            return panel.note.body
        return self.editor.toPlainText()

    # ── Debounce / undo ───────────────────────────────────────────────────

    def _on_text_changed(self):
        """Called on every keystroke. Silently syncs model, starts debounce."""
        if self._syncing or self._in_md_mode:
            return
        panel = self._props_panel()
        if panel is None:
            return
        text = self.editor.toPlainText()
        if self._show_yaml:
            # Parse the full source and update both props and body
            from core.yaml_parser import parse_frontmatter
            props, body = parse_frontmatter(text)
            panel.note._props = props
            panel.note._body  = body
        else:
            panel.note.set_body_silent(text)
        # Update undo button state
        panel._update_undo_btn()
        # Restart debounce
        self._debounce.start()

    def _on_debounce_timeout(self):
        """After inactivity: push a real undo checkpoint."""
        panel = self._props_panel()
        if panel:
            panel.note.checkpoint()
            panel._update_undo_btn()

    def undo(self):
        """Undo through NoteFile history."""
        panel = self._props_panel()
        if panel and panel.note.undo():
            self._reload_editor_content()
            panel._update_undo_btn()
            panel.rebuild_rows()
            mw = self._main_window()
            if mw:
                mw._recompare(silent=True)
                mw.statusBar().showMessage("Deshacer.")

    def redo(self):
        """Placeholder — NoteFile doesn't implement redo yet."""
        pass

    # ── Pilcrow ───────────────────────────────────────────────────────────

    def _toggle_pilcrow(self, on: bool):
        opt = self.editor.document().defaultTextOption()
        flag = (QTextOption.ShowTabsAndSpaces |
                QTextOption.ShowLineAndParagraphSeparators)
        if on:
            opt.setFlags(opt.flags() | flag)
        else:
            opt.setFlags(opt.flags() & ~flag)
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
        for label, op in [
            ("Eliminar líneas duplicadas",              "dedup_all"),
            ("Eliminar duplicadas consecutivas",        "dedup_consecutive"),
            (None, None),
            ("Ordenar A → Z  (todas)",                 "sort_az_all"),
            ("Ordenar Z → A  (todas)",                 "sort_za_all"),
            (None, None),
            ("Ordenar A → Z  (selección)",             "sort_az_sel"),
            ("Ordenar Z → A  (selección)",             "sort_za_sel"),
        ]:
            if label is None:
                menu.addSeparator()
            else:
                menu.addAction(label).triggered.connect(
                    lambda checked=False, o=op: self._lines_op(o)
                )
        menu.exec(QCursor.pos())

    def _lines_op(self, op: str):
        panel  = self._props_panel()
        cursor = self.editor.textCursor()

        if op in ("sort_az_sel", "sort_za_sel") and cursor.hasSelection():
            text  = cursor.selectedText().replace("\u2029", "\n")
            lines = sorted(text.splitlines(), reverse=(op == "sort_za_sel"))
            if panel:
                panel.note._push_history()
            cursor.insertText("\n".join(lines))
            return

        full  = self.editor.toPlainText()
        lines = full.splitlines()

        if op == "dedup_all":
            seen: set[str] = set()
            lines = [l for l in lines if not (l in seen or seen.add(l))]  # type: ignore
        elif op == "dedup_consecutive":
            new, prev = [], object()
            for l in lines:
                if l != prev: new.append(l)
                prev = l
            lines = new
        elif op == "sort_az_all":
            lines = sorted(lines)
        elif op == "sort_za_all":
            lines = sorted(lines, reverse=True)

        if panel:
            panel.note._push_history()
        pos = cursor.position()
        self.editor.setPlainText("\n".join(lines))
        c = self.editor.textCursor()
        c.setPosition(min(pos, len("\n".join(lines))))
        self.editor.setTextCursor(c)

    # ── Public API ────────────────────────────────────────────────────────

    def toPlainText(self) -> str:
        return self.editor.toPlainText()

    def setPlainText(self, text: str):
        """Called from outside (load file, undo, etc.)."""
        self._syncing = True
        self.editor.setPlainText(text)
        self._syncing = False
        if self._in_md_mode:
            self._md_view.refresh_from_text(text)

    def refresh_from_note(self):
        """Re-fill editor from the current NoteFile state."""
        self._reload_editor_content()

    # ── Nodos panel ───────────────────────────────────────────────────────

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
        self.min_len_spin.setToolTip("Largo mínimo por palabra individual")
        ctrl.addWidget(self.min_len_spin)

        self.stopwords_cb = QCheckBox("Ignorar conectores")
        self.stopwords_cb.setChecked(True)
        self.stopwords_cb.setToolTip(
            "Excluye preposiciones y conectores. "
            "Las palabras excluidas se pueden agregar a la lista negra."
        )
        ctrl.addWidget(self.stopwords_cb)

        self.whole_word_cb = QCheckBox("Solo palabras completas")
        self.whole_word_cb.setChecked(True)
        self.whole_word_cb.setToolTip(
            "Cada token debe cumplir min. letras por sí solo (sin contar espacios)"
        )
        ctrl.addWidget(self.whole_word_cb)

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
            self.stopwords_cb.isChecked(),
            whole_word=self.whole_word_cb.isChecked(),
        )
        self.word_list.clear()
        total = 0

        def add_header(label):
            item = QListWidgetItem(f"── {label} ──")
            item.setFlags(Qt.NoItemFlags)
            item.setForeground(_C_HDR)
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
            for w in result.from_dict: add_word(w, _C_DICT)
        if result.multi_phrases:
            add_header("Frases en común")
            for w in result.multi_phrases: add_word(w, _C_PHRASE)
        if result.single_words:
            add_header("Palabras en común")
            for w in result.single_words: add_word(w, _C_WORD)

        if total == 0:
            item = QListWidgetItem("(sin coincidencias)")
            item.setFlags(Qt.NoItemFlags)
            item.setForeground(_C_HDR)
            self.word_list.addItem(item)

        if mw:
            mw.statusBar().showMessage(
                f"Conectar Nodos: {total} candidato(s) — "
                f"{len(result.from_dict)} dict, "
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
            mw.statusBar().showMessage(f"{added} nodo(s) guardado(s).")
        self._on_nodos_search()

    def _word_ctx_menu(self, pos):
        item = self.word_list.itemAt(pos)
        if not item or not (item.flags() & Qt.ItemIsUserCheckable):
            return
        word = item.text()
        menu = QMenu(self)
        menu.addAction("✔ Aceptar → diccionario").triggered.connect(
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
        if mw: mw.statusBar().showMessage(f"'{word}' guardado.")
        self._on_nodos_search()

    def _item_blacklist(self, word):
        get_node_dict().add_blacklist(word)
        for i in range(self.word_list.count()):
            if self.word_list.item(i).text() == word:
                self.word_list.takeItem(i); break
        mw = self._main_window()
        if mw: mw.statusBar().showMessage(f"'{word}' en lista negra.")

    def _apply_single(self, word):
        mw = self._main_window()
        if mw: mw.apply_node_connections([word])

    # ── Helpers ───────────────────────────────────────────────────────────

    def _props_panel(self) -> "PropsPanel | None":
        from ui.props_panel import PropsPanel
        w = self
        while w:
            if isinstance(w, PropsPanel): return w
            w = w.parent()
        return None

    def _main_window(self) -> "MainWindow | None":
        from ui.main_window import MainWindow
        w = self
        while w:
            if isinstance(w, MainWindow): return w
            w = w.parent()
        return None


# ── _BodyTextEdit ─────────────────────────────────────────────────────────────

class _BodyTextEdit(QTextEdit):
    """QTextEdit with Ctrl+Z routed to NoteFile and right-click copy menu."""

    def __init__(self, side: str, parent: BodyEditor):
        super().__init__(parent)
        self.side         = side
        self._body_editor = parent
        self._body_editor = parent

    def keyPressEvent(self, event: QKeyEvent):
        # Intercept Ctrl+Z → NoteFile undo
        if event.matches(QKeySequence.Undo):
            self._body_editor.undo()
            return
        # Intercept Ctrl+Y / Ctrl+Shift+Z → redo (placeholder)
        if event.matches(QKeySequence.Redo):
            self._body_editor.redo()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent):
        menu = self.createStandardContextMenu()
        cursor        = self.textCursor()
        selected_text = cursor.selectedText().strip()

        if selected_text:
            menu.addSeparator()
            other = "derecha"   if self.side == "left" else "izquierda"
            arr   = "→"         if self.side == "left" else "←"

            # WikiLink conversion
            from core.utils import is_wikilink, to_wikilink
            if not is_wikilink(selected_text):
                menu.addAction("⟳ Convertir selección a WikiLink").triggered.connect(
                    lambda: self._convert_selection_to_wikilink()
                )
                menu.addSeparator()

            for label, pos in [
                (f"{arr} Copiar al panel {other} — en posición del cursor", "cursor"),
                (f"{arr} Copiar al panel {other} — al principio",           "start"),
                (f"{arr} Copiar al panel {other} — al final",               "end"),
            ]:
                menu.addAction(label).triggered.connect(
                    lambda checked=False, p=pos:
                        self._copy_to_other(selected_text, p)
                )
        menu.exec(event.globalPos())

    def _convert_selection_to_wikilink(self):
        """Wrap the current selection as [[selection]]."""
        from core.utils import to_wikilink
        cursor = self.textCursor()
        if not cursor.hasSelection():
            return
        text = cursor.selectedText().strip()
        wiki = to_wikilink(text)
        cursor.insertText(wiki)
        # Update model silently
        be = self._body_editor
        panel = be._props_panel()
        if panel:
            panel.note.set_body_silent(self.toPlainText())

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
        mw.statusBar().showMessage(
            f"Selección copiada al panel {'derecho' if self.side=='left' else 'izquierdo'} ({position})."
        )
