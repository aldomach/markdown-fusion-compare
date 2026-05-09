"""
ui/dialogs.py
Modal dialogs:
  - BodyCopyDialog   : preview + position selector for body merge
  - TemplateSaveDialog: table to configure which props go into template
"""

from __future__ import annotations
import copy

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QTextEdit, QDialogButtonBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QCheckBox, QWidget, QAbstractItemView
)
from PySide6.QtCore import Qt

from core.utils import new_lines_preview, value_to_str, is_empty_value


class BodyCopyDialog(QDialog):
    """
    Shows a preview of lines that will be added to the destination body,
    and lets the user choose whether to insert at start or end.
    """

    def __init__(self, src_body: str, dst_body: str, direction: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Copiar cuerpo de la nota")
        self.setMinimumWidth(520)
        self.new_lines = new_lines_preview(src_body, dst_body)
        self._build(direction)

    def _build(self, direction: str):
        layout = QVBoxLayout(self)

        info = QLabel(f"Copiar cuerpo  {direction}")
        info.setObjectName("DialogInfo")
        layout.addWidget(info)

        self.pos_combo = QComboBox()
        self.pos_combo.addItems([
            "Al final del archivo destino",
            "Al principio del archivo destino",
        ])
        layout.addWidget(self.pos_combo)

        layout.addWidget(QLabel(f"Líneas nuevas a agregar ({len(self.new_lines)}):"))

        preview = QTextEdit()
        preview.setPlainText("\n".join(self.new_lines))
        preview.setReadOnly(True)
        preview.setMaximumHeight(200)
        preview.setObjectName("BodyEdit")
        layout.addWidget(preview)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_position(self) -> str:
        return "end" if self.pos_combo.currentIndex() == 0 else "start"


class TemplateSaveDialog(QDialog):
    """
    Table with columns:
      [✓ propiedad | valor izquierdo | valor derecho | ¿Con valor?]
    Per row the user selects: Vacía / Izquierdo / Derecho.
    """

    def __init__(self, left_props: dict, right_props: dict, parent=None):
        super().__init__(parent)
        self.left_props  = left_props
        self.right_props = right_props
        self.setWindowTitle("Guardar como plantilla")
        self.setMinimumWidth(660)
        self.setMinimumHeight(460)
        self._keys: list[str] = sorted(
            set(left_props.keys()) | set(right_props.keys()),
            key=str.lower,
        )
        self._row_include:     dict[int, QCheckBox] = {}
        self._row_val_combo:   dict[int, QComboBox] = {}
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Configura las propiedades a incluir en la plantilla:"))

        self.table = QTableWidget(len(self._keys), 4)
        self.table.setHorizontalHeaderLabels(
            ["Propiedad", "Valor izquierdo", "Valor derecho", "¿Con valor?"]
        )
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setDefaultSectionSize(26)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)

        for i, key in enumerate(self._keys):
            lval = self.left_props.get(key, "")
            rval = self.right_props.get(key, "")

            # Col 0 — checkbox + key name
            cell = QWidget()
            cl   = QHBoxLayout(cell)
            cl.setContentsMargins(4, 0, 4, 0)
            cb = QCheckBox(key)
            cb.setChecked(True)
            cl.addWidget(cb)
            self._row_include[i] = cb
            self.table.setCellWidget(i, 0, cell)

            # Col 1 & 2 — read-only values
            for col, val in [(1, lval), (2, rval)]:
                item = QTableWidgetItem(value_to_str(val))
                item.setFlags(Qt.ItemIsEnabled)
                self.table.setItem(i, col, item)

            # Col 3 — with-value combo
            combo = QComboBox()
            combo.addItems(["Vacía", "Izquierdo", "Derecho"])
            if not is_empty_value(lval):
                combo.setCurrentIndex(1)
            elif not is_empty_value(rval):
                combo.setCurrentIndex(2)
            else:
                combo.setCurrentIndex(0)
            self._row_val_combo[i] = combo
            self.table.setCellWidget(i, 3, combo)

        layout.addWidget(self.table)

        # Select-all / none row
        btn_row = QHBoxLayout()
        sel_all = QPushButton("Seleccionar todo")
        sel_all.clicked.connect(
            lambda: [cb.setChecked(True) for cb in self._row_include.values()]
        )
        sel_none = QPushButton("Ninguno")
        sel_none.clicked.connect(
            lambda: [cb.setChecked(False) for cb in self._row_include.values()]
        )
        btn_row.addWidget(sel_all)
        btn_row.addWidget(sel_none)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_template_props(self) -> dict:
        """Return {key: chosen_value} for every checked row."""
        result: dict = {}
        for i, key in enumerate(self._keys):
            if not self._row_include[i].isChecked():
                continue
            choice = self._row_val_combo[i].currentIndex()
            if choice == 0:
                result[key] = ""
            elif choice == 1:
                result[key] = copy.deepcopy(self.left_props.get(key, ""))
            else:
                result[key] = copy.deepcopy(self.right_props.get(key, ""))
        return result
