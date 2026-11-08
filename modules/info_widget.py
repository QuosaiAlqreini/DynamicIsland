"""Info tab: cards for every info item the user added in Customize Island."""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QFrame
)

from services.info_service import INFO_TYPE_LABELS
from styles import badge_style, small_button_style

COLUMNS = 3
MAX_CARDS = 6


class InfoWidget(QWidget):
    customize_requested = pyqtSignal()

    def __init__(self, theme, info_service, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.info = info_service
        self.cards = {}  # item id -> value QLabel
        self._signature = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 6)
        lay.setSpacing(6)
        head = QHBoxLayout()
        self.badge = QLabel("ℹ️ MY INFO")
        head.addWidget(self.badge)
        head.addStretch()
        self.btn = QPushButton("🎨 Customize")
        self.btn.clicked.connect(self.customize_requested)
        head.addWidget(self.btn)
        lay.addLayout(head)
        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(6)
        lay.addWidget(self.grid_host, 1)

        self.info.values_changed.connect(self.refresh)
        self._apply_styles()
        self.refresh()

    def _apply_styles(self):
        self.badge.setStyleSheet(badge_style(self.theme))
        self.btn.setStyleSheet(small_button_style(self.theme))

    def update_theme(self, theme):
        self.theme = theme
        self._apply_styles()
        self._signature = None
        self.refresh()

    def _rebuild(self, items):
        while self.grid.count():
            it = self.grid.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.cards = {}
        t = self.theme
        if not items:
            empty = QLabel("Add world clocks, countdowns, notes-to-self or command output "
                           "(weather, server status…) with 🎨 Customize → Info.\n"
                           "You can also put any of them in the pill itself.")
            empty.setWordWrap(True)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f"color: {t['text_secondary']}; font-size: 10px;")
            self.grid.addWidget(empty, 0, 0)
            return
        for i, item in enumerate(items[:MAX_CARDS]):
            card = QFrame()
            card.setStyleSheet(f"QFrame {{ background: {t['card_bg']}; border: 1px solid {t['border_color']};"
                               f" border-radius: 10px; }} QLabel {{ border: none; background: transparent; }}")
            v = QVBoxLayout(card)
            v.setContentsMargins(10, 6, 10, 6)
            v.setSpacing(0)
            title = QLabel((item.get("label") or INFO_TYPE_LABELS.get(item.get("type"), "")).upper())
            title.setStyleSheet(f"color: {t['text_secondary']}; font-size: 9px; font-weight: 700;")
            value = QLabel("…")
            value.setStyleSheet(f"color: {t['text_primary']}; font-size: 15px; font-weight: 700;")
            value.setWordWrap(True)
            v.addWidget(title)
            v.addWidget(value)
            v.addStretch()
            self.grid.addWidget(card, i // COLUMNS, i % COLUMNS)
            self.cards[item["id"]] = value

    def refresh(self):
        items = self.info.items
        signature = tuple((i["id"], i.get("label"), i.get("type")) for i in items)
        if signature != self._signature:
            self._signature = signature
            self._rebuild(items)
        for iid, label in self.cards.items():
            label.setText(self.info.values.get(iid, "…") or "—")
