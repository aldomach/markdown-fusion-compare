"""
ui/highlighter.py
Shared syntax highlighter for Markdown + YAML frontmatter.
Used by both SourceView (full file) and BodyEditor (body only).

Highlights:
  - YAML frontmatter: delimiters, keys, values, list dashes
  - Markdown: headings, WikiLinks, bold, inline code, blockquotes, tags
"""

import re
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor


def _fmt(color: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if bold:
        f.setFontWeight(700)
    if italic:
        f.setFontItalic(True)
    return f


class MdHighlighter(QSyntaxHighlighter):
    """
    Syntax highlighter for a QTextEdit containing Markdown (with optional
    YAML frontmatter).

    Parameters
    ----------
    document       : QTextDocument to attach to
    body_only      : if True, skip frontmatter detection and always apply
                     Markdown rules (use for the body editor tab)
    """

    def __init__(self, document, body_only: bool = False):
        super().__init__(document)
        self._body_only = body_only

        # ── Format palette (Catppuccin Mocha) ────────────────────────────
        self._fmt_delimiter  = _fmt("#585b70", bold=True)
        self._fmt_key        = _fmt("#89b4fa", bold=True)
        self._fmt_value      = _fmt("#a6e3a1")
        self._fmt_list_dash  = _fmt("#f38ba8")
        self._fmt_heading    = _fmt("#cba6f7", bold=True)
        self._fmt_wikilink   = _fmt("#fab387")
        self._fmt_bold       = _fmt("#cdd6f4", bold=True)
        self._fmt_italic     = _fmt("#cdd6f4", italic=True)
        self._fmt_code       = _fmt("#a6e3a1")
        self._fmt_blockquote = _fmt("#6c7086", italic=True)
        self._fmt_tag        = _fmt("#89b4fa")
        self._fmt_link       = _fmt("#89dceb")
        self._fmt_hr         = _fmt("#45475a")

    def highlightBlock(self, text: str):
        if self._body_only:
            self._highlight_markdown(text)
            return

        # ── Detect position relative to frontmatter ───────────────────
        doc   = self.document()
        delim = 0
        blk   = doc.begin()
        cur   = self.currentBlock()

        while blk.isValid() and blk != cur:
            if blk.text().strip() == "---":
                delim += 1
                if delim >= 2:
                    break
            blk = blk.next()

        in_fm = (delim == 1)  # between first and second ---

        if text.strip() == "---":
            self.setFormat(0, len(text), self._fmt_delimiter)
            return

        if in_fm:
            self._highlight_yaml(text)
        else:
            self._highlight_markdown(text)

    # ── YAML rules ────────────────────────────────────────────────────────

    def _highlight_yaml(self, text: str):
        # List item:  - value
        if re.match(r'^\s*-\s', text):
            dash_pos = text.index("-")
            self.setFormat(dash_pos, 1, self._fmt_list_dash)
            self.setFormat(dash_pos + 2, len(text) - dash_pos - 2, self._fmt_value)
            return

        # key: value
        m = re.match(r'^([^:]+)(:)(.*)', text)
        if m:
            self.setFormat(m.start(1), len(m.group(1)), self._fmt_key)
            self.setFormat(m.start(2), 1,               self._fmt_delimiter)
            val_start = m.start(3)
            self.setFormat(val_start, len(text) - val_start, self._fmt_value)

    # ── Markdown rules ────────────────────────────────────────────────────

    def _highlight_markdown(self, text: str):
        # Headings
        hm = re.match(r'^(#{1,6})\s', text)
        if hm:
            self.setFormat(0, len(text), self._fmt_heading)
            return

        # Horizontal rule
        if re.match(r'^[-*_]{3,}\s*$', text):
            self.setFormat(0, len(text), self._fmt_hr)
            return

        # Blockquote
        if text.startswith(">"):
            self.setFormat(0, len(text), self._fmt_blockquote)
            return

        # Inline patterns (applied in order, may overlap — later wins)
        patterns = [
            # WikiLinks  [[...]]
            (r'\[\[.*?\]\]',           self._fmt_wikilink),
            # Markdown links [text](url)
            (r'\[.*?\]\(.*?\)',        self._fmt_link),
            # Inline code  `...`
            (r'`[^`]+`',               self._fmt_code),
            # Bold+italic  ***...***
            (r'\*{3}.+?\*{3}',         self._fmt_bold),
            # Bold  **...**
            (r'\*{2}.+?\*{2}',         self._fmt_bold),
            # Italic  *...*
            (r'\*[^*]+\*',             self._fmt_italic),
            # Tags  #word
            (r'(?<!\[)#\w+',           self._fmt_tag),
        ]
        for pattern, fmt in patterns:
            for m in re.finditer(pattern, text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)
