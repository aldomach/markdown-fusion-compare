"""
ui/node_dict_dialog.py
NodeDictDialog: modal dialog to manage the node dictionary and blacklist.

Tabs:
  1. Diccionario — list of accepted nodes, add/remove manually
  2. Lista negra — blacklisted words/phrases, add/remove manually
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QListWidget, QListWidgetItem, QPushButton, QLineEdit,
    QLabel, QDialogButtonBox, QMessageBox, QAbstractItemView
)
from PySide6.QtCore import Qt

from core.node_dict import NodeDictionary


class NodeDictDialog(QDialog):
    def __init__(self, node_dict: NodeDictionary, parent=None):
        super().__init__(parent)
        self.nd = node_dict
        self.setWindowTitle("Diccionario de Nodos")
        self.setMinimumSize(480, 460)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)

        tabs = QTabWidget()
        tabs.addTab(self._build_nodes_tab(),     "📚 Diccionario")
        tabs.addTab(self._build_blacklist_tab(),  "🚫 Lista negra")
        root.addWidget(tabs)

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.accept)
        root.addWidget(btns)

    # ── Nodes tab ─────────────────────────────────────────────────────────

    def _build_nodes_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        layout.addWidget(QLabel(
            "Nodos aceptados — se usarán con prioridad en Conectar Nodos:"
        ))

        self._nodes_list = QListWidget()
        self._nodes_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._nodes_list.setObjectName("NodosWordList")
        self._refresh_nodes_list()
        layout.addWidget(self._nodes_list)

        # Add row
        add_row = QHBoxLayout()
        self._node_input = QLineEdit()
        self._node_input.setObjectName("SearchEdit")
        self._node_input.setPlaceholderText("Nuevo nodo (puede ser multi-palabra)…")
        self._node_input.returnPressed.connect(self._add_node)
        add_row.addWidget(self._node_input)

        add_btn = QPushButton("+ Agregar")
        add_btn.setObjectName("BulkApplyBtn")
        add_btn.clicked.connect(self._add_node)
        add_row.addWidget(add_btn)
        layout.addLayout(add_row)

        # Action buttons
        btn_row = QHBoxLayout()
        del_btn = QPushButton("🗑 Eliminar seleccionados")
        del_btn.setObjectName("BulkDelBtn")
        del_btn.clicked.connect(self._remove_nodes)
        btn_row.addWidget(del_btn)

        to_bl_btn = QPushButton("→ Mover a lista negra")
        to_bl_btn.setObjectName("BulkApplyBtn")
        to_bl_btn.clicked.connect(self._move_to_blacklist)
        btn_row.addWidget(to_bl_btn)

        clear_btn = QPushButton("Limpiar todo")
        clear_btn.setObjectName("TemplateBtn")
        clear_btn.clicked.connect(self._clear_nodes)
        btn_row.addWidget(clear_btn)
        layout.addLayout(btn_row)

        return tab

    def _refresh_nodes_list(self):
        self._nodes_list.clear()
        for node in self.nd.nodes:
            self._nodes_list.addItem(QListWidgetItem(node))

    def _add_node(self):
        text = self._node_input.text().strip()
        if not text:
            return
        if self.nd.add_node(text):
            self._refresh_nodes_list()
            self._node_input.clear()
        else:
            QMessageBox.information(self, "Ya existe", f"'{text}' ya está en el diccionario.")

    def _remove_nodes(self):
        selected = [item.text() for item in self._nodes_list.selectedItems()]
        for node in selected:
            self.nd.remove_node(node)
        self._refresh_nodes_list()

    def _move_to_blacklist(self):
        selected = [item.text() for item in self._nodes_list.selectedItems()]
        for node in selected:
            self.nd.remove_node(node)
            self.nd.add_blacklist(node)
        self._refresh_nodes_list()
        self._refresh_blacklist_list()

    def _clear_nodes(self):
        reply = QMessageBox.question(
            self, "Limpiar diccionario",
            "¿Eliminar todos los nodos del diccionario?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.nd.clear_nodes()
            self._refresh_nodes_list()

    # ── Blacklist tab ─────────────────────────────────────────────────────

    def _build_blacklist_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        layout.addWidget(QLabel(
            "Palabras/frases que NUNCA se convertirán a WikiLink:"
        ))

        self._bl_list = QListWidget()
        self._bl_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._bl_list.setObjectName("NodosWordList")
        self._refresh_blacklist_list()
        layout.addWidget(self._bl_list)

        add_row = QHBoxLayout()
        self._bl_input = QLineEdit()
        self._bl_input.setObjectName("SearchEdit")
        self._bl_input.setPlaceholderText("Palabra o frase a bloquear…")
        self._bl_input.returnPressed.connect(self._add_blacklist)
        add_row.addWidget(self._bl_input)

        add_btn = QPushButton("+ Agregar")
        add_btn.setObjectName("BulkApplyBtn")
        add_btn.clicked.connect(self._add_blacklist)
        add_row.addWidget(add_btn)
        layout.addLayout(add_row)

        btn_row = QHBoxLayout()
        del_btn = QPushButton("🗑 Eliminar seleccionados")
        del_btn.setObjectName("BulkDelBtn")
        del_btn.clicked.connect(self._remove_blacklist)
        btn_row.addWidget(del_btn)

        to_nd_btn = QPushButton("→ Mover al diccionario")
        to_nd_btn.setObjectName("BulkApplyBtn")
        to_nd_btn.clicked.connect(self._move_to_nodes)
        btn_row.addWidget(to_nd_btn)

        clear_btn = QPushButton("Limpiar todo")
        clear_btn.setObjectName("TemplateBtn")
        clear_btn.clicked.connect(self._clear_blacklist)
        btn_row.addWidget(clear_btn)
        layout.addLayout(btn_row)

        return tab

    def _refresh_blacklist_list(self):
        self._bl_list.clear()
        for word in self.nd.blacklist:
            self._bl_list.addItem(QListWidgetItem(word))

    def _add_blacklist(self):
        text = self._bl_input.text().strip()
        if not text:
            return
        if self.nd.add_blacklist(text):
            self._refresh_blacklist_list()
            self._bl_input.clear()
        else:
            QMessageBox.information(self, "Ya existe", f"'{text}' ya está en la lista negra.")

    def _remove_blacklist(self):
        selected = [item.text() for item in self._bl_list.selectedItems()]
        for word in selected:
            self.nd.remove_blacklist(word)
        self._refresh_blacklist_list()

    def _move_to_nodes(self):
        selected = [item.text() for item in self._bl_list.selectedItems()]
        for word in selected:
            self.nd.remove_blacklist(word)
            self.nd.add_node(word)
        self._refresh_blacklist_list()
        self._refresh_nodes_list()

    def _clear_blacklist(self):
        reply = QMessageBox.question(
            self, "Limpiar lista negra",
            "¿Eliminar todas las entradas de la lista negra?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.nd.clear_blacklist()
            self._refresh_blacklist_list()
