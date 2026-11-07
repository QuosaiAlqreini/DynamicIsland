"""Shelf tab: a drop-anything file tray plus clipboard history.

Drag files onto the island from anywhere: they land here and can be dragged
back out into any app (mail, chat, browser upload, another folder) later.
"""
import os

from PyQt6.QtCore import Qt, QMimeData, QUrl, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QAbstractItemView, QFileIconProvider
)
from PyQt6.QtCore import QFileInfo

from config import ConfigManager
from services.launcher import open_target, reveal_in_folder
from styles import badge_style, small_button_style, list_style

PATH_ROLE = Qt.ItemDataRole.UserRole
TEXT_ROLE = Qt.ItemDataRole.UserRole + 1


class FileShelfList(QListWidget):
    """List whose items can be dragged out of the island as real files."""
    drag_started = pyqtSignal()
    drag_finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)

    def mimeData(self, items):
        mime = QMimeData()
        paths = [i.data(PATH_ROLE) for i in items if i.data(PATH_ROLE)]
        mime.setUrls([QUrl.fromLocalFile(p) for p in paths])
        mime.setText("\n".join(paths))
        return mime

    def supportedDropActions(self):
        return Qt.DropAction.CopyAction | Qt.DropAction.MoveAction

    def startDrag(self, actions):
        self.drag_started.emit()
        try:
            super().startDrag(Qt.DropAction.CopyAction)
        finally:
            self.drag_finished.emit()


class ShelfWidget(QWidget):
    drag_out_started = pyqtSignal()
    drag_out_finished = pyqtSignal()
    count_changed = pyqtSignal(int)

    def __init__(self, theme, clipboard_service, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.config = ConfigManager()
        self.clipboard_service = clipboard_service
        self.icon_provider = QFileIconProvider()
        self.paths = [p for p in self.config.get("shelf_items", []) if isinstance(p, str)]
        self._build_ui()
        self._apply_styles()
        self._refresh_files()
        self._refresh_clipboard()
        self.clipboard_service.history_changed.connect(self._refresh_clipboard)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 6)
        root.setSpacing(10)

        # Files column
        files_col = QVBoxLayout()
        files_col.setSpacing(4)
        head = QHBoxLayout()
        self.files_badge = QLabel("📥 SHELF")
        head.addWidget(self.files_badge)
        head.addStretch()
        self.files_hint = QLabel("")
        head.addWidget(self.files_hint)
        files_col.addLayout(head)

        self.file_list = FileShelfList()
        self.file_list.setToolTip("Drop files on the island to park them here.\n"
                                  "Drag them out into any app. Double-click to open.")
        self.file_list.itemDoubleClicked.connect(lambda it: open_target(it.data(PATH_ROLE)))
        self.file_list.drag_started.connect(self.drag_out_started)
        self.file_list.drag_finished.connect(self.drag_out_finished)
        files_col.addWidget(self.file_list)

        fbtns = QHBoxLayout()
        fbtns.setSpacing(4)
        self.btn_open = QPushButton("Open")
        self.btn_open.clicked.connect(self._open_selected)
        self.btn_reveal = QPushButton("Folder")
        self.btn_reveal.setToolTip("Show in Explorer")
        self.btn_reveal.clicked.connect(self._reveal_selected)
        self.btn_copy_path = QPushButton("Path")
        self.btn_copy_path.setToolTip("Copy file path(s)")
        self.btn_copy_path.clicked.connect(self._copy_paths)
        self.btn_remove = QPushButton("✕")
        self.btn_remove.setToolTip("Remove from shelf (file is not deleted)")
        self.btn_remove.clicked.connect(self._remove_selected)
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.clicked.connect(self.clear_files)
        for b in (self.btn_open, self.btn_reveal, self.btn_copy_path, self.btn_remove, self.btn_clear):
            fbtns.addWidget(b)
        files_col.addLayout(fbtns)
        root.addLayout(files_col, 1)

        # Clipboard column
        clip_col = QVBoxLayout()
        clip_col.setSpacing(4)
        chead = QHBoxLayout()
        self.clip_badge = QLabel("📋 CLIPBOARD")
        chead.addWidget(self.clip_badge)
        chead.addStretch()
        clip_col.addLayout(chead)

        self.clip_list = QListWidget()
        self.clip_list.setToolTip("Click an entry to copy it again. 📌 = pinned (kept across restarts).")
        self.clip_list.itemClicked.connect(self._copy_clip)
        clip_col.addWidget(self.clip_list)

        cbtns = QHBoxLayout()
        cbtns.setSpacing(4)
        self.btn_pin = QPushButton("📌 Pin")
        self.btn_pin.clicked.connect(self._pin_selected)
        self.btn_clip_del = QPushButton("✕")
        self.btn_clip_del.clicked.connect(self._delete_clip)
        self.btn_clip_clear = QPushButton("Clear")
        self.btn_clip_clear.setToolTip("Clear unpinned history")
        self.btn_clip_clear.clicked.connect(self.clipboard_service.clear_history)
        for b in (self.btn_pin, self.btn_clip_del, self.btn_clip_clear):
            cbtns.addWidget(b)
        clip_col.addLayout(cbtns)
        root.addLayout(clip_col, 1)

    def _apply_styles(self):
        self.files_badge.setStyleSheet(badge_style(self.theme))
        self.clip_badge.setStyleSheet(badge_style(self.theme))
        self.files_hint.setStyleSheet(f"color: {self.theme['text_secondary']}; font-size: 9px;")
        for lst in (self.file_list, self.clip_list):
            lst.setStyleSheet(list_style(self.theme))
        btn_css = small_button_style(self.theme)
        for b in self.findChildren(QPushButton):
            b.setStyleSheet(btn_css)

    def update_theme(self, theme):
        self.theme = theme
        self._apply_styles()

    # --------------------------------------------------------------- Files
    def add_paths(self, paths):
        added = 0
        for p in paths:
            p = os.path.normpath(p)
            if not p or p in self.paths:
                continue
            self.paths.insert(0, p)
            added += 1
        limit = max(1, int(self.config.get("shelf_max_items", 30)))
        del self.paths[limit:]
        if added:
            self._save()
            self._refresh_files()
        return added

    def clear_files(self):
        self.paths = []
        self._save()
        self._refresh_files()

    def _save(self):
        self.config.set("shelf_items", list(self.paths))

    def _refresh_files(self):
        self.file_list.clear()
        for p in self.paths:
            exists = os.path.exists(p)
            name = os.path.basename(p) or p
            item = QListWidgetItem(name if exists else f"{name} (missing)")
            item.setData(PATH_ROLE, p)
            item.setToolTip(p)
            if exists:
                item.setIcon(self.icon_provider.icon(QFileInfo(p)))
            else:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
            self.file_list.addItem(item)
        count = len(self.paths)
        self.files_hint.setText(f"{count} item{'s' if count != 1 else ''}" if count else "drop files here")
        self.count_changed.emit(count)

    def _selected_paths(self):
        items = self.file_list.selectedItems()
        if not items and self.file_list.currentItem():
            items = [self.file_list.currentItem()]
        return [i.data(PATH_ROLE) for i in items]

    def _open_selected(self):
        for p in self._selected_paths():
            open_target(p)

    def _reveal_selected(self):
        paths = self._selected_paths()
        if paths:
            reveal_in_folder(paths[0])

    def _copy_paths(self):
        paths = self._selected_paths()
        if paths:
            self.clipboard_service.copy("\n".join(paths))

    def _remove_selected(self):
        selected = set(self._selected_paths())
        if not selected:
            return
        self.paths = [p for p in self.paths if p not in selected]
        self._save()
        self._refresh_files()

    # ----------------------------------------------------------- Clipboard
    def _refresh_clipboard(self):
        self.clip_list.clear()
        entries = self.clipboard_service.items()
        if not entries:
            placeholder = QListWidgetItem("Copy something — it shows up here."
                                          if self.clipboard_service.enabled
                                          else "Clipboard history is off (Preferences).")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self.clip_list.addItem(placeholder)
            return
        for text, pinned in entries:
            first = " ".join(text.split())
            label = (first[:60] + "…") if len(first) > 60 else first
            item = QListWidgetItem(("📌 " if pinned else "") + label)
            item.setData(TEXT_ROLE, text)
            item.setToolTip(text[:500])
            self.clip_list.addItem(item)

    def _copy_clip(self, item):
        text = item.data(TEXT_ROLE)
        if text:
            self.clipboard_service.copy(text)

    def _pin_selected(self):
        item = self.clip_list.currentItem()
        if item and item.data(TEXT_ROLE):
            self.clipboard_service.toggle_pin(item.data(TEXT_ROLE))

    def _delete_clip(self):
        item = self.clip_list.currentItem()
        if item and item.data(TEXT_ROLE):
            self.clipboard_service.remove(item.data(TEXT_ROLE))
