"""
ui/source_view.py
SourceView: a QTextEdit that shows the full raw markdown (YAML + body)
and lets the user edit it directly.  On focus-out or explicit "Apply"
the panel re-parses the content and updates the model.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PySide6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor
from PySide6.QtCore import Qt
import re

# Lazy import to avoid circular deps
if TYPE_CHECKING:
    from ui.props_panel import PropsPanel


# ── Minimal Markdown/YAML syntax highlighter ─────────────────────────────────

class _MdHighlighter(QSyntaxHighlighter):
    """Highlights YAML frontmatter keys, values, and markdown headings."""

    def __init__(self, document):
        super().__init__(document)
        self._in_frontmatter = False

        def fmt(color: str, bold=False) -> QTextCharFormat:
            f = QTextCharFormat()
            f.setForeground(QColor(color))
            if bold:
                f.setFontWeight(700)
            return f

        self._fmt_delimiter = fmt("#585b70", bold=True)
        self._fmt_key       = fmt("#89b4fa", bold=True)
        self._fmt_value     = fmt("#a6e3a1")
        self._fmt_list_dash = fmt("#f38ba8")
        self._fmt_heading   = fmt("#cba6f7", bold=True)
        self._fmt_wikilink  = fmt("#fab387")
        self._fmt_bold      = fmt("#cdd6f4", bold=True)

        self._line_count    = 0   # tracked to know if we're in frontmatter

    def highlightBlock(self, text: str):
        block_num = self.currentBlock().blockNumber()

        # ── YAML delimiter lines (--- )
        if text.strip() == "---":
            self.setFormat(0, len(text), self._fmt_delimiter)
            return

        # ── Inside frontmatter: lines before second ---
        # We detect frontmatter by walking from the top
        doc   = self.document()
        first = doc.begin()
        in_fm = False
        delim = 0
        blk   = first
        while blk.isValid() and blk != self.currentBlock():
            t = blk.text().strip()
            if t == "---":
                delim += 1
                if delim == 2:
                    in_fm = False
                    break
                else:
                    in_fm = True
            blk = blk.next()

        if in_fm and delim < 2:
            # key: value
            m = re.match(r'^(\s*)([^:]+)(:)(.*)', text)
            if m and not text.startswith("  -"):
                key_start = m.start(2)
                key_end   = m.end(2)
                col_pos   = m.start(3)
                val_start = m.start(4)
                self.setFormat(key_start, key_end - key_start, self._fmt_key)
                self.setFormat(col_pos, 1, self._fmt_delimiter)
                self.setFormat(val_start, len(text) - val_start, self._fmt_value)
                return
            # list item
            if text.strip().startswith("- "):
                dash = text.index("-")
                self.setFormat(dash, 1, self._fmt_list_dash)
                self.setFormat(dash + 2, len(text) - dash - 2, self._fmt_value)
                return
            return

        # ── Markdown body
        # Headings
        if re.match(r'^#{1,6} ', text):
            self.setFormat(0, len(text), self._fmt_heading)
            return

        # WikiLinks  [[...]]
        for m in re.finditer(r'\[\[.*?\]\]', text):
            self.setFormat(m.start(), m.end() - m.start(), self._fmt_wikilink)

        # Bold  **...**
        for m in re.finditer(r'\*\*.*?\*\*', text):
            self.setFormat(m.start(), m.end() - m.start(), self._fmt_bold)


# ── SourceView widget ─────────────────────────────────────────────────────────

class SourceView(QWidget):
    """
    Full-file source editor with syntax highlighting.
    Placed as the third tab in PropsPanel.
    """

    def __init__(self, panel: "PropsPanel", parent=None):
        super().__init__(parent)
        self._panel = panel
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        # Info bar
        info_row = QHBoxLayout()
        info_lbl = QLabel("Edición directa del archivo — presioná Aplicar para actualizar los paneles.")
        info_lbl.setObjectName("SourceInfoLabel")
        info_row.addWidget(info_lbl)
        info_row.addStretch()

        apply_btn = QPushButton("✔ Aplicar cambios")
        apply_btn.setObjectName("SourceApplyBtn")
        apply_btn.setFixedHeight(26)
        apply_btn.clicked.connect(self._apply)
        info_row.addWidget(apply_btn)

        root.addLayout(info_row)

        # Editor
        from PySide6.QtWidgets import QTextEdit
        self.editor = QTextEdit()
        self.editor.setObjectName("SourceEdit")
        self.editor.setAcceptRichText(False)
        font = QFont("JetBrains Mono, Fira Code, Consolas, monospace")
        font.setPointSize(12)
        self.editor.setFont(font)
        self._highlighter = _MdHighlighter(self.editor.document())
        root.addWidget(self.editor)

    # ── Public API ────────────────────────────────────────────────────────

    def refresh(self):
        """Reload content from the model (called when switching to this tab)."""
        content = self._panel.note.to_markdown()
        # Block signals to avoid triggering document change handlers
        self.editor.blockSignals(True)
        self.editor.setPlainText(content)
        self.editor.blockSignals(False)

    def _apply(self):
        """Parse edited source and push back to the model + rebuild rows."""
        from core.yaml_parser import parse_frontmatter
        text = self.editor.toPlainText()
        props, body = parse_frontmatter(text)
        self._panel.note.set_props_and_body(props, body)
        self._panel._sync_ui_from_note()

        # Also update body_edit in case user is on body tab
        self._panel.body_edit.setPlainText(body)

        mw = self._panel._main_window()
        if mw:
            mw._recompare(silent=True)
            mw.statusBar().showMessage("Fuente aplicada — paneles actualizados.")
