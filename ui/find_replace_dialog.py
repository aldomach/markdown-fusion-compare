"""
ui/find_replace_dialog.py
FindReplaceDialog: non-modal find & replace panel.

Modes:  Normal | Extendido (\\n \\t escapes) | Expresiones regulares
Options: Coincidir mayúsculas · Palabra completa · En todo el doc / solo selección
Actions: Buscar siguiente · Buscar anterior · Reemplazar · Reemplazar todo
"""

from __future__ import annotations
import re
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QCheckBox,
    QComboBox, QRadioButton, QFrame, QMessageBox
)
from PySide6.QtGui import QTextCursor
from PySide6.QtCore import Qt

if TYPE_CHECKING:
    from PySide6.QtWidgets import QTextEdit


class FindReplaceDialog(QDialog):
    """Non-modal find & replace dialog attached to a QTextEdit."""

    def __init__(self, editor: "QTextEdit", parent=None):
        super().__init__(parent)
        self.editor = editor
        self.setWindowTitle("Buscar y Reemplazar")
        self.setWindowFlags(
            Qt.Window | Qt.WindowCloseButtonHint | Qt.WindowStaysOnTopHint
        )
        self.setMinimumWidth(500)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)

        # ── Search / Replace fields ───────────────────────────────────────
        grid = QGridLayout()
        grid.setSpacing(6)

        grid.addWidget(QLabel("Buscar:"), 0, 0)
        self._find_edit = QLineEdit()
        self._find_edit.setObjectName("SearchEdit")
        self._find_edit.setPlaceholderText("Texto a buscar…")
        self._find_edit.returnPressed.connect(self._find_next)
        grid.addWidget(self._find_edit, 0, 1)

        grid.addWidget(QLabel("Reemplazar:"), 1, 0)
        self._repl_edit = QLineEdit()
        self._repl_edit.setObjectName("SearchEdit")
        self._repl_edit.setPlaceholderText("Texto de reemplazo…")
        grid.addWidget(self._repl_edit, 1, 1)
        root.addLayout(grid)

        # ── Mode ─────────────────────────────────────────────────────────
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Modo:"))
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["Normal", "Extendido (\\n \\t)", "Expresión regular"])
        self._mode_combo.setFixedWidth(210)
        mode_row.addWidget(self._mode_combo)
        mode_row.addStretch()
        root.addLayout(mode_row)

        # ── Options ───────────────────────────────────────────────────────
        opt_row = QHBoxLayout()
        self._case_cb = QCheckBox("Coincidir mayúsculas")
        self._word_cb = QCheckBox("Palabra completa")
        opt_row.addWidget(self._case_cb)
        opt_row.addWidget(self._word_cb)
        opt_row.addStretch()
        root.addLayout(opt_row)

        # ── Scope ─────────────────────────────────────────────────────────
        scope_row = QHBoxLayout()
        self._scope_all = QRadioButton("Todo el documento")
        self._scope_sel = QRadioButton("Solo en selección")
        self._scope_all.setChecked(True)
        scope_row.addWidget(self._scope_all)
        scope_row.addWidget(self._scope_sel)
        scope_row.addStretch()
        root.addLayout(scope_row)

        # ── Buttons ───────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #313244;")
        root.addWidget(sep)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        for label, slot in [
            ("↑ Anterior",      self._find_prev),
            ("↓ Siguiente",     self._find_next),
            ("Reemplazar",      self._replace_one),
            ("Reemplazar todo", self._replace_all),
        ]:
            btn = QPushButton(label)
            btn.setObjectName("BulkApplyBtn")
            btn.setFixedHeight(28)
            btn.clicked.connect(slot)
            btn_row.addWidget(btn)

        close_btn = QPushButton("Cerrar")
        close_btn.setObjectName("OpenBtn")
        close_btn.setFixedHeight(28)
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("SourceInfoLabel")
        root.addWidget(self._status_lbl)

    # ── Pattern ───────────────────────────────────────────────────────────

    def _build_pattern(self) -> "re.Pattern | None":
        text = self._find_edit.text()
        if not text:
            return None
        mode = self._mode_combo.currentIndex()
        if mode == 0:   # Normal
            text = re.escape(text)
        elif mode == 1: # Extended
            text = text.replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r")
            text = re.escape(text)
        # mode 2: regex as-is
        if self._word_cb.isChecked():
            text = r'\b' + text + r'\b'
        flags = 0 if self._case_cb.isChecked() else re.IGNORECASE
        try:
            return re.compile(text, flags)
        except re.error as e:
            self._status_lbl.setText(f"Regex inválida: {e}")
            return None

    # ── Scope ─────────────────────────────────────────────────────────────

    def _get_scope(self) -> tuple[str, int, int | None]:
        """Returns (text, start_offset, end_offset_or_None)."""
        cursor = self.editor.textCursor()
        if self._scope_sel.isChecked() and cursor.hasSelection():
            sel_text = cursor.selectedText().replace("\u2029", "\n")
            return sel_text, cursor.selectionStart(), cursor.selectionEnd()
        return self.editor.toPlainText(), 0, None

    # ── Find ──────────────────────────────────────────────────────────────

    def _find_next(self): self._find(forward=True)
    def _find_prev(self): self._find(forward=False)

    def _find(self, forward: bool):
        pattern = self._build_pattern()
        if not pattern:
            return
        text, offset, _ = self._get_scope()
        cur_pos = self.editor.textCursor().position() - offset
        matches = list(pattern.finditer(text))
        if not matches:
            self._status_lbl.setText("Sin coincidencias.")
            return
        if forward:
            target = next((m for m in matches if m.start() > cur_pos), matches[0])
        else:
            before = [m for m in matches if m.start() < cur_pos]
            target = before[-1] if before else matches[-1]
        self._select(target.start() + offset, target.end() + offset)
        idx = matches.index(target)
        self._status_lbl.setText(f"Coincidencia {idx+1} de {len(matches)}")

    def _select(self, start: int, end: int):
        c = self.editor.textCursor()
        c.setPosition(start)
        c.setPosition(end, QTextCursor.KeepAnchor)
        self.editor.setTextCursor(c)
        self.editor.ensureCursorVisible()

    # ── Replace ───────────────────────────────────────────────────────────

    def _replace_one(self):
        pattern = self._build_pattern()
        if not pattern:
            return
        cursor = self.editor.textCursor()
        sel = cursor.selectedText().replace("\u2029", "\n")
        if sel and pattern.fullmatch(sel):
            cursor.insertText(self._make_replacement(sel, pattern))
            self._status_lbl.setText("Reemplazado.")
        else:
            self._find_next()

    def _replace_all(self):
        pattern = self._build_pattern()
        if not pattern:
            return
        text, offset, end_offset = self._get_scope()
        repl = self._repl_text()
        count    = len(pattern.findall(text))
        new_text = pattern.sub(repl, text)
        if self._scope_sel.isChecked() and self.editor.textCursor().hasSelection():
            self.editor.textCursor().insertText(new_text)
        else:
            pos = self.editor.textCursor().position()
            self.editor.setPlainText(new_text)
            c = self.editor.textCursor()
            c.setPosition(min(pos, len(new_text)))
            self.editor.setTextCursor(c)
        self._status_lbl.setText(f"{count} reemplazo(s) realizado(s).")

    def _repl_text(self) -> str:
        t = self._repl_edit.text()
        if self._mode_combo.currentIndex() in (1, 2):
            t = t.replace("\\n", "\n").replace("\\t", "\t")
        return t

    def _make_replacement(self, matched: str, pattern: "re.Pattern") -> str:
        repl = self._repl_text()
        if self._mode_combo.currentIndex() == 2:
            try:
                return pattern.sub(repl, matched)
            except Exception:
                pass
        return repl

    # ── Show ──────────────────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            sel = cursor.selectedText().replace("\u2029", "\n")
            if "\n" not in sel:
                self._find_edit.setText(sel)
        self._find_edit.setFocus()
        self._find_edit.selectAll()
