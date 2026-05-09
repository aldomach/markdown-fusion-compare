"""
ui/main_window.py
MainWindow: top-level window.
- Two PropsPanel side by side in a QSplitter
- Compact bottom bar (body copy, recompare, save template)
- No toolbar (all actions live in the panels or bottom bar)
- Auto-compare when both panels have a file loaded
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFrame, QLabel, QPushButton, QSplitter,
    QFileDialog, QMessageBox, QDialog
)
from PySide6.QtCore import Qt

from core.utils import merge_body
from core.yaml_parser import serialize_frontmatter
from ui.props_panel import PropsPanel
from ui.dialogs import BodyCopyDialog, TemplateSaveDialog


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Obsidian Markdown Comparator")
        self.setMinimumSize(1100, 700)
        self._build_ui()
        self.statusBar().showMessage("Abre dos archivos Markdown para comenzar.")

    # ── Build ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Splitter
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setObjectName("MainSplitter")
        self.splitter.setHandleWidth(5)

        self.left_panel  = PropsPanel("left",  self)
        self.right_panel = PropsPanel("right", self)

        self.left_panel.file_loaded.connect(self._on_file_loaded)
        self.right_panel.file_loaded.connect(self._on_file_loaded)

        self.splitter.addWidget(self.left_panel)
        self.splitter.addWidget(self.right_panel)
        self.splitter.setSizes([500, 500])

        root.addWidget(self.splitter, stretch=1)
        root.addWidget(self._build_bottom_bar(), stretch=0)

    def _build_bottom_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("BottomBar")
        bar.setFixedHeight(42)

        bl = QHBoxLayout(bar)
        bl.setContentsMargins(10, 0, 10, 0)
        bl.setSpacing(8)

        lbl = QLabel("Cuerpo:")
        lbl.setObjectName("BarLabel")
        bl.addWidget(lbl)

        btn_lr = QPushButton("→ Cuerpo a derecha")
        btn_lr.setObjectName("BodyBtn")
        btn_lr.setFixedHeight(28)
        btn_lr.clicked.connect(lambda: self._copy_body("left", "right"))
        bl.addWidget(btn_lr)

        btn_rl = QPushButton("← Cuerpo a izquierda")
        btn_rl.setObjectName("BodyBtn")
        btn_rl.setFixedHeight(28)
        btn_rl.clicked.connect(lambda: self._copy_body("right", "left"))
        bl.addWidget(btn_rl)

        bl.addStretch()

        btn_recompare = QPushButton("🔄 Volver a comparar")
        btn_recompare.setObjectName("RecompareBtn")
        btn_recompare.setFixedHeight(28)
        btn_recompare.clicked.connect(self._recompare)
        bl.addWidget(btn_recompare)

        btn_template = QPushButton("💾 Guardar plantilla")
        btn_template.setObjectName("TemplateBtn")
        btn_template.setFixedHeight(28)
        btn_template.clicked.connect(self._save_template)
        bl.addWidget(btn_template)

        return bar

    # ── Auto-compare ──────────────────────────────────────────────────────

    def _on_file_loaded(self, side: str):
        """Auto-compare when both panels have content."""
        left_has  = bool(self.left_panel.note.props  or self.left_panel.note.body)
        right_has = bool(self.right_panel.note.props or self.right_panel.note.body)
        if left_has and right_has:
            self._recompare(silent=True)
            self.statusBar().showMessage("Archivos cargados — comparación automática lista.")
        else:
            panel_name = "izquierdo" if side == "left" else "derecho"
            self.statusBar().showMessage(f"Archivo {panel_name} cargado.")

    # ── Recompare ─────────────────────────────────────────────────────────

    def _recompare(self, silent: bool = False):
        left_keys  = set(self.left_panel.note.props.keys())
        right_keys = set(self.right_panel.note.props.keys())
        self.left_panel.rebuild_rows(other_keys=right_keys)
        self.right_panel.rebuild_rows(other_keys=left_keys)
        if not silent:
            self.statusBar().showMessage("Comparación actualizada.")

    # ── Body copy ─────────────────────────────────────────────────────────

    def _copy_body(self, src_side: str, dst_side: str):
        src_panel = self.left_panel  if src_side == "left" else self.right_panel
        dst_panel = self.right_panel if dst_side == "right" else self.left_panel

        src_body  = src_panel.body_edit.toPlainText()
        dst_body  = dst_panel.body_edit.toPlainText()
        direction = "→ Derecha" if dst_side == "right" else "← Izquierda"

        dlg = BodyCopyDialog(src_body, dst_body, direction, self)
        if dlg.exec() != QDialog.Accepted:
            return
        if not dlg.new_lines:
            QMessageBox.information(self, "Sin cambios", "No hay líneas nuevas para agregar.")
            return

        pos         = dlg.get_position()
        new_content = merge_body(src_body, dst_body, pos)
        dst_panel.body_edit.setPlainText(new_content)
        dst_panel.note.set_body(new_content)
        self.statusBar().showMessage("Cuerpo copiado.")

    # ── Template ──────────────────────────────────────────────────────────

    def _save_template(self):
        all_keys = (
            set(self.left_panel.note.props.keys()) |
            set(self.right_panel.note.props.keys())
        )
        if not all_keys:
            QMessageBox.warning(self, "Sin propiedades",
                                "No hay propiedades para generar plantilla.")
            return

        dlg = TemplateSaveDialog(
            self.left_panel.note.props,
            self.right_panel.note.props,
            self,
        )
        if dlg.exec() != QDialog.Accepted:
            return

        template_props = dlg.get_template_props()
        if not template_props:
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar plantilla", "", "Markdown (*.md)"
        )
        if not path:
            return

        sorted_props = dict(sorted(template_props.items(), key=lambda x: x[0].lower()))
        content      = serialize_frontmatter(sorted_props, "")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        QMessageBox.information(self, "Plantilla guardada",
                                f"Plantilla guardada en:\n{path}")
        self.statusBar().showMessage(f"Plantilla guardada: {Path(path).name}")
