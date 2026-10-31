from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

class AIAgentWidget(QWidget):
    ask_prompt_submitted = pyqtSignal(str)
    clipboard_action_requested = pyqtSignal(str) # 'explain' or 'fix'
    coderabbit_requested = pyqtSignal()
    ralph_requested = pyqtSignal()

    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.status_text = "IDLE (READY)"
        self.status_color = "#10b981"
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(8)

        # Header: AI Status & Persona
        header_row = QHBoxLayout()
        self.status_badge = QLabel(f"🤖 {self.status_text}")
        self.status_badge.setStyleSheet(f"""
            color: {self.status_color};
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.5px;
            background: rgba(16, 185, 129, 0.15);
            padding: 2px 8px;
            border-radius: 6px;
        """)
        header_row.addWidget(self.status_badge)
        header_row.addStretch()

        self.model_label = QLabel("Antigravity & Claude")
        self.model_label.setStyleSheet(f"""
            color: {self.theme['text_secondary']};
            font-size: 10px;
            font-weight: 600;
        """)
        header_row.addWidget(self.model_label)
        layout.addLayout(header_row)

        # Prompt Input Bar
        input_row = QHBoxLayout()
        input_row.setSpacing(6)

        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Ask AI or type command (Enter to send)...")
        self.prompt_input.setStyleSheet(f"""
            QLineEdit {{
                background: {self.theme['bg_secondary']};
                color: {self.theme['text_primary']};
                border: 1px solid {self.theme['border_color']};
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 11px;
            }}
            QLineEdit:focus {{
                border: 1px solid {self.theme['accent']};
            }}
        """)
        self.prompt_input.returnPressed.connect(self._submit_prompt)
        input_row.addWidget(self.prompt_input)

        self.send_btn = QPushButton("⚡")
        self.send_btn.setFixedSize(28, 28)
        self.send_btn.setStyleSheet(f"""
            QPushButton {{
                background: {self.theme['accent']};
                color: {self.theme['bg_color']};
                font-weight: bold;
                border-radius: 6px;
                border: none;
            }}
            QPushButton:hover {{
                background: {self.theme['text_primary']};
            }}
        """)
        self.send_btn.clicked.connect(self._submit_prompt)
        input_row.addWidget(self.send_btn)

        layout.addLayout(input_row)

        # Quick Action Buttons Row
        action_row = QHBoxLayout()
        action_row.setSpacing(6)

        btn_style = f"""
            QPushButton {{
                background: {self.theme['card_bg']};
                color: {self.theme['text_primary']};
                font-size: 9px;
                font-weight: 600;
                border: 1px solid {self.theme['border_color']};
                padding: 4px 6px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                border-color: {self.theme['accent']};
                color: {self.theme['accent']};
                background: rgba(0, 240, 255, 0.08);
            }}
        """

        self.btn_explain = QPushButton("📋 Explain Clip")
        self.btn_explain.setStyleSheet(btn_style)
        self.btn_explain.clicked.connect(lambda: self.clipboard_action_requested.emit("explain"))
        action_row.addWidget(self.btn_explain)

        self.btn_fix = QPushButton("🛠️ Fix Clip")
        self.btn_fix.setStyleSheet(btn_style)
        self.btn_fix.clicked.connect(lambda: self.clipboard_action_requested.emit("fix"))
        action_row.addWidget(self.btn_fix)

        self.btn_cr = QPushButton("🐰 CodeRabbit")
        self.btn_cr.setStyleSheet(btn_style)
        self.btn_cr.clicked.connect(self.coderabbit_requested.emit)
        action_row.addWidget(self.btn_cr)

        self.btn_ralph = QPushButton("🔄 Ralph Loop")
        self.btn_ralph.setStyleSheet(btn_style)
        self.btn_ralph.clicked.connect(self.ralph_requested.emit)
        action_row.addWidget(self.btn_ralph)

        layout.addLayout(action_row)

        # Response Output Box
        self.output_box = QTextEdit()
        self.output_box.setReadOnly(True)
        self.output_box.setFixedHeight(48)
        self.output_box.setPlaceholderText("AI responses and tool output will appear here...")
        self.output_box.setStyleSheet(f"""
            QTextEdit {{
                background: {self.theme['bg_secondary']};
                color: {self.theme['text_secondary']};
                border: 1px solid {self.theme['border_color']};
                border-radius: 6px;
                padding: 4px 6px;
                font-size: 10px;
                font-family: Consolas, 'Courier New', monospace;
            }}
        """)
        layout.addWidget(self.output_box)

    def _submit_prompt(self):
        text = self.prompt_input.text()
        if text.strip():
            self.output_box.setText(f"Asking: '{text}'...")
            self.ask_prompt_submitted.emit(text)
            self.prompt_input.clear()

    def update_agent_status(self, status, color_hex):
        self.status_text = status.upper()
        self.status_color = color_hex
        self.status_badge.setText(f"🤖 {self.status_text}")
        self.status_badge.setStyleSheet(f"""
            color: {self.status_color};
            font-size: 10px;
            font-weight: 700;
            background: rgba(16, 185, 129, 0.15);
            padding: 2px 8px;
            border-radius: 6px;
        """)

    def set_output(self, title, content):
        self.output_box.setText(f"[{title}]\n{content}")

    def update_theme(self, theme):
        self.theme = theme
        self.prompt_input.setStyleSheet(f"""
            QLineEdit {{
                background: {self.theme['bg_secondary']};
                color: {self.theme['text_primary']};
                border: 1px solid {self.theme['border_color']};
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 11px;
            }}
        """)
        self.output_box.setStyleSheet(f"""
            QTextEdit {{
                background: {self.theme['bg_secondary']};
                color: {self.theme['text_secondary']};
                border: 1px solid {self.theme['border_color']};
                border-radius: 6px;
                padding: 4px 6px;
                font-size: 10px;
                font-family: Consolas, monospace;
            }}
        """)
