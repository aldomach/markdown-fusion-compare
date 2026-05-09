"""
ui/styles.py
All QSS stylesheet definitions.  Import STYLESHEET and apply to QApplication.
Edit only this file to change colours / spacing / fonts globally.
"""

STYLESHEET = """
/* ── Base ── */
QMainWindow, QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
    font-size: 13px;
}

/* ── Panel header ── */
QFrame#PanelHeader { background: #181825; border-bottom: 1px solid #313244; }
QLabel#PanelTitle  { font-size: 13px; font-weight: bold; color: #89b4fa; }
QLabel#PathLabel   {
    font-size: 11px; color: #6c7086; background: #1e1e2e;
    border-bottom: 1px solid #2a2a3e; padding: 2px 10px;
}

/* ── Generic buttons ── */
QPushButton {
    background: #313244; border: 1px solid #45475a;
    border-radius: 4px; padding: 3px 10px; color: #cdd6f4;
}
QPushButton:hover   { background: #45475a; }
QPushButton:disabled{ background: #2a2a3e; color: #585b70; border-color: #45475a; }

/* ── Named buttons ── */
QPushButton#OpenBtn  { color: #89b4fa; }
QPushButton#NewBtn   { color: #94e2d5; background: #1a2d2d; border-color: #3a6060; }
QPushButton#NewBtn:hover { background: #22393a; }
QPushButton#SaveBtn  { background: #1e6b4a; border-color: #40a070; color: #a6e3a1; }
QPushButton#SaveBtn:hover { background: #2a8060; }
QPushButton#UndoBtn  { background: #252535; border-color: #4a4a6a; color: #b4b8f0; }
QPushButton#UndoBtn:hover { background: #30305a; }

QPushButton#PropBtn  {
    background: #313244; border: 1px solid #45475a;
    border-radius: 3px; color: #cba6f7; font-size: 11px;
    padding: 1px 6px;
}
QPushButton#PropBtn:hover  { background: #45475a; color: #f5c2e7; }
QPushButton#PropEditBtn {
    background: #1f2535; border: 1px solid #3a4a6a;
    border-radius: 3px; color: #89b4fa; font-size: 10px;
    padding: 1px 5px;
}
QPushButton#PropEditBtn:hover { background: #2a3550; }

QPushButton#BulkApplyBtn {
    background: #2a1f3d; border: 1px solid #6c4a8a;
    border-radius: 4px; padding: 2px 10px; color: #cba6f7; font-size: 11px;
}
QPushButton#BulkApplyBtn:hover { background: #3d2d5a; }

QPushButton#BodyBtn {
    background: #1f2d3d; border: 1px solid #3d6a8a;
    border-radius: 4px; padding: 3px 12px; color: #89dceb;
}
QPushButton#BodyBtn:hover { background: #2a3d50; }

QPushButton#RecompareBtn {
    background: #2d3020; border: 1px solid #8a9a40;
    border-radius: 4px; padding: 3px 12px; color: #a6e3a1;
}
QPushButton#RecompareBtn:hover { background: #3a4030; }

QPushButton#TemplateBtn {
    background: #2d1f20; border: 1px solid #8a4040;
    border-radius: 4px; padding: 3px 12px; color: #f38ba8;
}
QPushButton#TemplateBtn:hover { background: #3a2a2a; }

/* ── Tabs ── */
QTabWidget#PanelTabs::pane { border: none; background: #1e1e2e; }
QTabBar::tab {
    background: #181825; color: #6c7086; border: 1px solid #313244;
    border-bottom: none; padding: 5px 14px;
    border-radius: 4px 4px 0 0; margin-right: 2px;
}
QTabBar::tab:selected    { background: #1e1e2e; color: #cdd6f4; border-bottom: 2px solid #89b4fa; }
QTabBar::tab:hover:!selected { background: #24243e; color: #a6adc8; }

/* ── Property rows ── */
QScrollArea#PropsScroll   { border: none; background: #1e1e2e; }
QFrame#RowContainer       { background: #1e1e2e; border-bottom: 1px solid #2a2a3e; }
QFrame#RowContainer:hover { background: #24243e; }
QFrame#RowContainerActive { background: #2a2a4e; border-bottom: 1px solid #4a4a7e; border-left: 3px solid #89b4fa; }
QFrame#RowContainerUnpaired       { background: #1e1e2e; border-bottom: 1px dashed #3a2a2a; border-left: 3px solid #f38ba8; }
QFrame#RowContainerUnpaired:hover { background: #2a1e1e; }

QLabel#PropKey { color: #89b4fa; font-weight: bold; font-size: 12px; }
QLabel#PropVal { color: #cdd6f4; font-size: 12px; }

/* ── Inline edit fields ── */
QLineEdit#PropKeyEdit, QLineEdit#PropValEdit {
    background: #24243e; border: 1px solid #89b4fa;
    border-radius: 3px; padding: 1px 5px;
    color: #cdd6f4; font-size: 12px;
    selection-background-color: #45475a;
}

/* ── Bulk bar ── */
QFrame#BulkBar { background: #181825; border-bottom: 1px solid #313244; }

/* ── Bottom bar ── */
QFrame#BottomBar { background: #181825; border-top: 1px solid #313244; }
QLabel#BarLabel  { color: #6c7086; font-size: 12px; }

/* ── Body editor ── */
QTextEdit#BodyEdit {
    background: #181825; color: #cdd6f4;
    border: 1px solid #313244; border-radius: 4px;
    padding: 8px; selection-background-color: #45475a;
    font-family: 'JetBrains Mono', monospace; font-size: 13px;
}

/* ── Splitter ── */
QSplitter#MainSplitter::handle       { background: #313244; }
QSplitter#MainSplitter::handle:hover { background: #89b4fa; }

/* ── Status bar ── */
QStatusBar {
    background: #181825; color: #6c7086;
    border-top: 1px solid #313244; font-size: 11px;
}

/* ── Context menu ── */
QMenu {
    background: #24243e; border: 1px solid #45475a;
    border-radius: 6px; padding: 4px;
}
QMenu::item          { padding: 5px 18px; border-radius: 4px; color: #cdd6f4; }
QMenu::item:selected { background: #313244; color: #89b4fa; }
QMenu::separator     { background: #45475a; height: 1px; margin: 3px 8px; }

/* ── Dialogs ── */
QDialog { background: #1e1e2e; color: #cdd6f4; }
QLabel#DialogInfo { color: #a6adc8; font-size: 13px; padding: 3px 0; }

/* ── Combo boxes ── */
QComboBox {
    background: #313244; border: 1px solid #45475a;
    border-radius: 4px; padding: 3px 8px; color: #cdd6f4;
}
QComboBox::drop-down { border: none; width: 18px; }
QComboBox QAbstractItemView {
    background: #24243e; border: 1px solid #45475a;
    selection-background-color: #45475a; color: #cdd6f4;
    outline: none;
}

/* ── Table (template dialog) ── */
QTableWidget {
    background: #181825; color: #cdd6f4;
    border: 1px solid #313244; gridline-color: #2a2a3e;
}
QHeaderView::section {
    background: #24243e; color: #89b4fa;
    border: none; border-bottom: 1px solid #313244;
    padding: 4px 6px; font-size: 12px;
}
QTableWidget::item          { padding: 2px 6px; }
QTableWidget::item:selected { background: #313244; }

/* ── List widget ── */
QListWidget {
    background: #181825; border: 1px solid #313244;
    border-radius: 4px; color: #cdd6f4;
}
QListWidget::item:selected { background: #313244; }
QListWidget::item:hover    { background: #24243e; }

/* ── Scrollbars ── */
QScrollBar:vertical {
    background: #181825; width: 7px; border-radius: 3px;
}
QScrollBar::handle:vertical {
    background: #45475a; border-radius: 3px; min-height: 20px;
}
QScrollBar::handle:vertical:hover          { background: #585b70; }
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical              { height: 0; }

/* ── Checkboxes ── */
QCheckBox              { spacing: 4px; color: #cdd6f4; }
QCheckBox::indicator   {
    width: 13px; height: 13px;
    border: 1px solid #45475a; border-radius: 3px; background: #313244;
}
QCheckBox::indicator:checked { background: #89b4fa; border-color: #89b4fa; }

/* ── Dialog button box ── */
QDialogButtonBox QPushButton {
    background: #313244; border: 1px solid #45475a;
    border-radius: 4px; padding: 4px 14px; color: #cdd6f4;
}
QDialogButtonBox QPushButton:hover { background: #45475a; }

/* ── Property row status colours ── */
QFrame#RowEqual        { background: #1a2e1a; border-bottom: 1px solid #2a3e2a; border-left: 3px solid #a6e3a1; }
QFrame#RowEqual:hover  { background: #203820; }
QFrame#RowDiff         { background: #2e2a1a; border-bottom: 1px solid #3e3a2a; border-left: 3px solid #f9e2af; }
QFrame#RowDiff:hover   { background: #383220; }
QFrame#RowWikiDiff     { background: #1a2a2e; border-bottom: 1px solid #2a3a3e; border-left: 3px solid #89dceb; }
QFrame#RowWikiDiff:hover { background: #203238; }
QFrame#RowListPartial  { background: #251a2e; border-bottom: 1px solid #352a3e; border-left: 3px solid #cba6f7; }
QFrame#RowListPartial:hover { background: #302038; }
QFrame#RowLeftOnly     { background: #2e1a1a; border-bottom: 1px dashed #3e2a2a; border-left: 3px solid #f38ba8; }
QFrame#RowLeftOnly:hover  { background: #382020; }
QFrame#RowRightOnly    { background: #1a1a2e; border-bottom: 1px dashed #2a2a3e; border-left: 3px solid #b4befe; }
QFrame#RowRightOnly:hover { background: #202038; }
QFrame#RowEmptyDiff    { background: #222228; border-bottom: 1px solid #313244; border-left: 3px solid #585b70; }
QFrame#RowEmptyDiff:hover { background: #282830; }
QFrame#RowContainerActive { background: #2a2a4e; border-bottom: 1px solid #4a4a7e; border-left: 3px solid #89b4fa; }

/* ── Status dot ── */
QLabel#StatusDot { font-size: 10px; }

/* ── Search bar ── */
QFrame#SearchBar { background: #181825; border-bottom: 1px solid #313244; }
QLineEdit#SearchEdit {
    background: #24243e; border: 1px solid #45475a; border-radius: 4px;
    padding: 2px 8px; color: #cdd6f4; font-size: 12px;
}
QLineEdit#SearchEdit:focus { border-color: #89b4fa; }
QPushButton#SearchIconBtn {
    background: #313244; border: 1px solid #45475a; border-radius: 4px; color: #89b4fa;
}
QPushButton#SearchIconBtn:hover { background: #45475a; }

/* ── Source view ── */
QTextEdit#SourceEdit {
    background: #13131f; color: #cdd6f4;
    border: 1px solid #313244; border-radius: 4px;
    padding: 8px; font-family: 'JetBrains Mono', 'Fira Code', monospace; font-size: 12px;
    selection-background-color: #45475a;
}
QLabel#SourceInfoLabel { color: #6c7086; font-size: 11px; }
QPushButton#SourceApplyBtn {
    background: #1e6b4a; border: 1px solid #40a070;
    border-radius: 4px; padding: 2px 12px; color: #a6e3a1;
}
QPushButton#SourceApplyBtn:hover { background: #2a8060; }

/* ── Legend (status dot colours reference) ── */
QFrame#NodosContainer  { background: #1e1e2e; }
QFrame#NodosPanelInner {
    background: #181825; border: 1px solid #313244;
    border-radius: 4px; padding: 4px;
}
QPushButton#NodosToggleBtn {
    background: #1a2535; border: 1px solid #3a5a8a;
    border-radius: 4px; padding: 2px 12px; color: #89dceb; font-size: 12px;
}
QPushButton#NodosToggleBtn:hover { background: #243550; }
QPushButton#NodosSearchBtn {
    background: #1f2d3d; border: 1px solid #3d6a8a;
    border-radius: 4px; padding: 2px 12px; color: #89dceb;
}
QPushButton#NodosSearchBtn:hover { background: #2a3d50; }
QPushButton#NodosApplyBtn {
    background: #1a2d1a; border: 1px solid #3a7a3a;
    border-radius: 4px; padding: 3px 12px; color: #a6e3a1;
}
QPushButton#NodosApplyBtn:hover { background: #253d25; }
QListWidget#NodosWordList {
    background: #181825; border: 1px solid #313244;
    border-radius: 4px; color: #cdd6f4; font-size: 12px;
}
QListWidget#NodosWordList::item:hover { background: #24243e; }
QSpinBox {
    background: #313244; border: 1px solid #45475a;
    border-radius: 4px; padding: 2px 6px; color: #cdd6f4;
}
"""
