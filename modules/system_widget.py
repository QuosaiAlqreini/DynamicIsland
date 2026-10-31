from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush

class CircularGauge(QWidget):
    def __init__(self, title, unit="%", parent=None):
        super().__init__(parent)
        self.title = title
        self.unit = unit
        self.value = 0.0
        self.color = QColor("#00f0ff")
        self.bg_color = QColor("#1e293b")
        self.text_color = QColor("#ffffff")
        self.subtext = ""
        self.setFixedSize(96, 96)

    def set_value(self, val, subtext=""):
        self.value = max(0.0, min(100.0, float(val)))
        self.subtext = subtext
        self.update()

    def set_colors(self, gauge_color, bg_color, text_color):
        self.color = QColor(gauge_color)
        self.bg_color = QColor(bg_color)
        self.text_color = QColor(text_color)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        cx, cy = self.width() / 2, self.height() / 2
        radius = 34
        rect = self.rect().adjusted(10, 10, -10, -10)

        # Background track arc
        pen_bg = QPen(self.bg_color, 6)
        pen_bg.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_bg)
        painter.drawArc(rect, 0, 360 * 16)

        # Value active arc
        pen_val = QPen(self.color, 6)
        pen_val.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_val)
        
        # Start at 90 deg (top), draw clockwise
        start_angle = 90 * 16
        span_angle = -int((self.value / 100.0) * 360 * 16)
        painter.drawArc(rect, start_angle, span_angle)

        # Draw Center Value
        painter.setPen(self.text_color)
        font = QFont("Segoe UI", 11, QFont.Weight.Bold)
        painter.setFont(font)
        val_str = f"{int(self.value)}{self.unit}"
        painter.drawText(self.rect().adjusted(0, -6, 0, 0), Qt.AlignmentFlag.AlignCenter, val_str)

        # Draw Title below value
        font_sub = QFont("Segoe UI", 8, QFont.Weight.DemiBold)
        painter.setFont(font_sub)
        painter.setPen(QColor(self.text_color.red(), self.text_color.green(), self.text_color.blue(), 160))
        painter.drawText(self.rect().adjusted(0, 18, 0, 0), Qt.AlignmentFlag.AlignCenter, self.title)

class SystemWidget(QWidget):
    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.sys_data = {
            "cpu_percent": 0.0,
            "mem_percent": 0.0,
            "mem_used_gb": 0.0,
            "mem_total_gb": 0.0,
            "battery_percent": 100,
            "battery_plugged": True,
            "uptime": "0h 0m"
        }
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Header Row
        header_row = QHBoxLayout()
        title_badge = QLabel("⚡ SYSTEM TELEMETRY")
        title_badge.setStyleSheet(f"""
            color: {self.theme['accent']};
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 1px;
            background: rgba(0, 240, 255, 0.12);
            padding: 2px 8px;
            border-radius: 6px;
        """)
        header_row.addWidget(title_badge)
        header_row.addStretch()

        self.uptime_label = QLabel(f"Up: {self.sys_data['uptime']}")
        self.uptime_label.setStyleSheet(f"""
            color: {self.theme['text_secondary']};
            font-size: 10px;
            font-weight: 600;
        """)
        header_row.addWidget(self.uptime_label)
        layout.addLayout(header_row)

        # Gauges Row: CPU, RAM, Battery
        gauges_row = QHBoxLayout()
        gauges_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gauges_row.setSpacing(24)

        self.cpu_gauge = CircularGauge("CPU", "%")
        self.cpu_gauge.set_colors(self.theme["accent"], self.theme["bg_secondary"], self.theme["text_primary"])
        gauges_row.addWidget(self.cpu_gauge)

        self.ram_gauge = CircularGauge("RAM", "%")
        self.ram_gauge.set_colors(self.theme["accent_secondary"], self.theme["bg_secondary"], self.theme["text_primary"])
        gauges_row.addWidget(self.ram_gauge)

        self.bat_gauge = CircularGauge("BATTERY", "%")
        self.bat_gauge.set_colors(self.theme["success"], self.theme["bg_secondary"], self.theme["text_primary"])
        gauges_row.addWidget(self.bat_gauge)

        layout.addLayout(gauges_row)

        # Footer Metrics text
        self.footer_label = QLabel("RAM: 0.0 / 0.0 GB | Power: AC Connected")
        self.footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.footer_label.setStyleSheet(f"""
            color: {self.theme['text_secondary']};
            font-size: 10px;
            font-weight: 500;
        """)
        layout.addWidget(self.footer_label)

    def update_system(self, stats):
        self.sys_data = stats
        self.cpu_gauge.set_value(stats["cpu_percent"])
        self.ram_gauge.set_value(stats["mem_percent"])
        self.bat_gauge.set_value(stats["battery_percent"])
        self.uptime_label.setText(f"Up: {stats['uptime']}")

        power_str = "🔌 Plugged In" if stats["battery_plugged"] else "🔋 On Battery"
        self.footer_label.setText(f"RAM: {stats['mem_used_gb']} / {stats['mem_total_gb']} GB • {power_str}")

    def update_theme(self, theme):
        self.theme = theme
        self.cpu_gauge.set_colors(self.theme["accent"], self.theme["bg_secondary"], self.theme["text_primary"])
        self.ram_gauge.set_colors(self.theme["accent_secondary"], self.theme["bg_secondary"], self.theme["text_primary"])
        self.bat_gauge.set_colors(self.theme["success"], self.theme["bg_secondary"], self.theme["text_primary"])
