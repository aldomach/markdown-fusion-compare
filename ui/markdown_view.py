"""
ui/markdown_view.py
MarkdownView: renders the note body as formatted HTML inside a QTextEdit
(read-only).  No external libraries required — uses a lightweight
Markdown → HTML converter built with regex.

Supported syntax:
  # H1  ## H2  ### H3  #### H4
  **bold**  *italic*  ~~strikethrough~~
  `inline code`
  ```code blocks```
  - / * / + unordered lists
  1. ordered lists
  > blockquotes
  [[WikiLink]]  →  styled pill
  [text](url)   →  clickable link
  ---  horizontal rule
  blank line    →  paragraph break
"""

from __future__ import annotations
import re
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTextBrowser
)
from PySide6.QtCore import Qt

if TYPE_CHECKING:
    from ui.props_panel import PropsPanel


# ── Markdown → HTML ───────────────────────────────────────────────────────────

def md_to_html(text: str) -> str:
    """Convert a markdown string to an HTML fragment."""
    lines   = text.split("\n")
    out     = []
    in_code = False
    in_list_ul = False
    in_list_ol = False
    in_blockquote = False

    def close_lists():
        nonlocal in_list_ul, in_list_ol
        if in_list_ul:
            out.append("</ul>")
            in_list_ul = False
        if in_list_ol:
            out.append("</ol>")
            in_list_ol = False

    def close_blockquote():
        nonlocal in_blockquote
        if in_blockquote:
            out.append("</blockquote>")
            in_blockquote = False

    for line in lines:
        # ── Code fence
        if line.strip().startswith("```"):
            if in_code:
                out.append("</code></pre>")
                in_code = False
            else:
                close_lists()
                close_blockquote()
                out.append('<pre><code>')
                in_code = True
            continue

        if in_code:
            out.append(_esc(line))
            continue

        # ── Headings
        hm = re.match(r'^(#{1,4})\s+(.*)', line)
        if hm:
            close_lists()
            close_blockquote()
            level = len(hm.group(1))
            out.append(f"<h{level}>{_inline(hm.group(2))}</h{level}>")
            continue

        # ── Horizontal rule
        if re.match(r'^[-*_]{3,}\s*$', line):
            close_lists()
            close_blockquote()
            out.append("<hr/>")
            continue

        # ── Blockquote
        bq = re.match(r'^>\s?(.*)', line)
        if bq:
            close_lists()
            if not in_blockquote:
                out.append("<blockquote>")
                in_blockquote = True
            out.append(f"<p>{_inline(bq.group(1))}</p>")
            continue
        else:
            close_blockquote()

        # ── Unordered list
        ul = re.match(r'^[\-\*\+]\s+(.*)', line)
        if ul:
            if in_list_ol:
                out.append("</ol>")
                in_list_ol = False
            if not in_list_ul:
                out.append("<ul>")
                in_list_ul = True
            out.append(f"<li>{_inline(ul.group(1))}</li>")
            continue

        # ── Ordered list
        ol = re.match(r'^\d+\.\s+(.*)', line)
        if ol:
            if in_list_ul:
                out.append("</ul>")
                in_list_ul = False
            if not in_list_ol:
                out.append("<ol>")
                in_list_ol = True
            out.append(f"<li>{_inline(ol.group(1))}</li>")
            continue

        # ── Close open lists on non-list line
        close_lists()

        # ── Blank line → paragraph break
        if not line.strip():
            out.append("<br/>")
            continue

        # ── Normal paragraph line
        out.append(f"<p>{_inline(line)}</p>")

    close_lists()
    close_blockquote()
    if in_code:
        out.append("</code></pre>")

    return "\n".join(out)


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline(text: str) -> str:
    """Apply inline markdown formatting."""
    # WikiLinks  [[target|alias]] or [[target]]
    def wiki_replace(m):
        inner = m.group(1)
        if "|" in inner:
            target, alias = inner.split("|", 1)
        else:
            target = alias = inner
        return (
            f'<span style="'
            f'background:#2a1f3d;color:#cba6f7;'
            f'border:1px solid #6c4a8a;border-radius:4px;'
            f'padding:1px 6px;font-size:0.9em;">'
            f'[[{alias}]]</span>'
        )
    text = re.sub(r'\[\[([^\]]+)\]\]', wiki_replace, text)

    # Markdown links [text](url)
    text = re.sub(
        r'\[([^\]]+)\]\(([^)]+)\)',
        r'<a href="\2" style="color:#89b4fa;">\1</a>',
        text
    )

    # Inline code `code`
    text = re.sub(
        r'`([^`]+)`',
        r'<code style="background:#313244;color:#a6e3a1;'
        r'border-radius:3px;padding:1px 5px;">\1</code>',
        text
    )

    # Bold+italic ***text***
    text = re.sub(r'\*{3}(.+?)\*{3}',
                  r'<strong><em>\1</em></strong>', text)
    # Bold **text**
    text = re.sub(r'\*{2}(.+?)\*{2}',
                  r'<strong>\1</strong>', text)
    # Italic *text*
    text = re.sub(r'\*(.+?)\*',
                  r'<em>\1</em>', text)
    # Strikethrough ~~text~~
    text = re.sub(r'~~(.+?)~~',
                  r'<del>\1</del>', text)
    # Tags  #tag
    text = re.sub(
        r'(?<!\[)#(\w+)',
        r'<span style="color:#89b4fa;">#\1</span>',
        text
    )

    return text


_HTML_TEMPLATE = """
<html><head><style>
  body  {{ background:#1e1e2e; color:#cdd6f4;
           font-family:'JetBrains Mono','Fira Code',monospace;
           font-size:13px; margin:12px; }}
  h1    {{ color:#cba6f7; font-size:1.6em; border-bottom:1px solid #313244; padding-bottom:4px; }}
  h2    {{ color:#89b4fa; font-size:1.35em; }}
  h3    {{ color:#74c7ec; font-size:1.15em; }}
  h4    {{ color:#94e2d5; font-size:1.05em; }}
  p     {{ margin:4px 0; line-height:1.6; }}
  hr    {{ border:none; border-top:1px solid #45475a; margin:12px 0; }}
  ul,ol {{ padding-left:20px; margin:4px 0; }}
  li    {{ margin:2px 0; line-height:1.5; }}
  pre   {{ background:#181825; border:1px solid #313244; border-radius:6px;
           padding:10px; overflow-x:auto; }}
  code  {{ font-family:'JetBrains Mono',monospace; }}
  blockquote {{ border-left:3px solid #585b70; margin:4px 0;
                padding-left:12px; color:#a6adc8; }}
  a     {{ color:#89b4fa; text-decoration:none; }}
  del   {{ color:#6c7086; }}
</style></head><body>{body}</body></html>
"""


# ── Widget ────────────────────────────────────────────────────────────────────

class MarkdownView(QWidget):
    """Read-only rendered markdown preview, placed as a tab in PropsPanel."""

    def __init__(self, panel: "PropsPanel", parent=None):
        super().__init__(parent)
        self._panel = panel
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        # Top bar
        top = QHBoxLayout()
        from PySide6.QtWidgets import QLabel
        lbl = QLabel("Vista previa Markdown — solo lectura")
        lbl.setObjectName("SourceInfoLabel")
        top.addWidget(lbl)
        top.addStretch()
        refresh_btn = QPushButton("🔄 Actualizar")
        refresh_btn.setObjectName("SourceApplyBtn")
        refresh_btn.setFixedHeight(26)
        refresh_btn.clicked.connect(self.refresh)
        top.addWidget(refresh_btn)
        root.addLayout(top)

        self.view = QTextBrowser()
        self.view.setObjectName("MarkdownView")
        self.view.setOpenExternalLinks(True)
        self.view.setOpenLinks(True)
        root.addWidget(self.view)

    def refresh(self):
        """Re-render body from the model."""
        body = self._panel.body_edit.toPlainText()
        html = _HTML_TEMPLATE.format(body=md_to_html(body))
        self.view.setHtml(html)
