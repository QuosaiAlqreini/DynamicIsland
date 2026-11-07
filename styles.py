THEMES = {
    "obsidian": {
        "name": "Obsidian Dark",
        "bg_color": "#0b0c10",
        "bg_secondary": "#151821",
        "border_color": "#232733",
        "text_primary": "#f8fafc",
        "text_secondary": "#94a3b8",
        "accent": "#00f0ff",
        "accent_secondary": "#a855f7",
        "accent_glow": "rgba(0, 240, 255, 0.35)",
        "danger": "#ef4444",
        "warning": "#f59e0b",
        "success": "#10b981",
        "pill_gradient_start": "#0e1017",
        "pill_gradient_end": "#08090c",
        "card_bg": "#12151e"
    },
    "cyberpunk": {
        "name": "Cyberpunk Neon",
        "bg_color": "#090414",
        "bg_secondary": "#160b2e",
        "border_color": "#ff007f",
        "text_primary": "#ffffff",
        "text_secondary": "#c084fc",
        "accent": "#ff007f",
        "accent_secondary": "#00f5d4",
        "accent_glow": "rgba(255, 0, 127, 0.4)",
        "danger": "#ff0055",
        "warning": "#ffe600",
        "success": "#00f5d4",
        "pill_gradient_start": "#130628",
        "pill_gradient_end": "#080312",
        "card_bg": "#190d33"
    },
    "nord": {
        "name": "Nord Arctic",
        "bg_color": "#242933",
        "bg_secondary": "#2e3440",
        "border_color": "#434c5e",
        "text_primary": "#eceff4",
        "text_secondary": "#d8dee9",
        "accent": "#88c0d0",
        "accent_secondary": "#81a1c1",
        "accent_glow": "rgba(136, 192, 208, 0.3)",
        "danger": "#bf616a",
        "warning": "#ebcb8b",
        "success": "#a3be8c",
        "pill_gradient_start": "#2b313d",
        "pill_gradient_end": "#1e222b",
        "card_bg": "#2e3440"
    },
    "glassmorphic": {
        "name": "Glassmorphism",
        "bg_color": "#0f172a",
        "bg_secondary": "#1e293b",
        "border_color": "#334155",
        "text_primary": "#f8fafc",
        "text_secondary": "#94a3b8",
        "accent": "#38bdf8",
        "accent_secondary": "#6366f1",
        "accent_glow": "rgba(56, 189, 248, 0.35)",
        "danger": "#f87171",
        "warning": "#fbbf24",
        "success": "#34d399",
        "pill_gradient_start": "#1e293b",
        "pill_gradient_end": "#0f172a",
        "card_bg": "#1a2234"
    },
    "porcelain": {
        "name": "Porcelain Light",
        "bg_color": "#f8fafc",
        "bg_secondary": "#ffffff",
        "border_color": "#cbd5e1",
        "text_primary": "#0f172a",
        "text_secondary": "#64748b",
        "accent": "#2563eb",
        "accent_secondary": "#7c3aed",
        "accent_glow": "rgba(37, 99, 235, 0.2)",
        "danger": "#dc2626",
        "warning": "#d97706",
        "success": "#059669",
        "pill_gradient_start": "#ffffff",
        "pill_gradient_end": "#f1f5f9",
        "card_bg": "#f1f5f9"
    }
}

def get_theme(theme_name="obsidian"):
    return THEMES.get(theme_name, THEMES["obsidian"])


def _rgba(hex_color, alpha):
    """Convert '#rrggbb' into a CSS rgba() string with the given alpha (0-1)."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return hex_color
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


def badge_style(theme):
    return f"""
        color: {theme['accent']};
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1px;
        background: {_rgba(theme['accent'], 0.12)};
        padding: 2px 8px;
        border-radius: 6px;
    """


def small_button_style(theme):
    return f"""
        QPushButton {{
            background: {theme['card_bg']};
            color: {theme['text_primary']};
            border: 1px solid {theme['border_color']};
            border-radius: 6px;
            font-size: 10px;
            font-weight: 600;
            padding: 3px 8px;
        }}
        QPushButton:hover {{
            color: {theme['accent']};
            border-color: {theme['accent']};
        }}
        QPushButton:checked {{
            background: {theme['accent']};
            color: {theme['bg_color']};
            border-color: {theme['accent']};
        }}
        QPushButton:disabled {{
            color: {theme['text_secondary']};
        }}
    """


def list_style(theme):
    return f"""
        QListWidget {{
            background: {theme['card_bg']};
            color: {theme['text_primary']};
            border: 1px solid {theme['border_color']};
            border-radius: 8px;
            font-size: 10px;
            padding: 2px;
            outline: none;
        }}
        QListWidget::item {{
            padding: 3px 4px;
            border-radius: 4px;
        }}
        QListWidget::item:selected {{
            background: {_rgba(theme['accent'], 0.18)};
            color: {theme['text_primary']};
        }}
        QListWidget::item:hover {{
            background: {theme['bg_secondary']};
        }}
    """


def input_style(theme):
    return f"""
        background: {theme['card_bg']};
        color: {theme['text_primary']};
        border: 1px solid {theme['border_color']};
        border-radius: 8px;
        font-size: 11px;
        padding: 4px 6px;
    """


def dialog_style(theme):
    """Shared look for preference-style dialogs (tabs, inputs, tables)."""
    return f"""
        QDialog {{
            background-color: {theme['bg_color']};
            color: {theme['text_primary']};
            font-family: 'Segoe UI', sans-serif;
        }}
        QTabWidget::pane {{
            border: 1px solid {theme['border_color']};
            background: {theme['bg_secondary']};
            border-radius: 8px;
        }}
        QTabBar::tab {{
            background: {theme['bg_color']};
            color: {theme['text_secondary']};
            padding: 8px 16px;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            font-weight: 600;
            font-size: 11px;
        }}
        QTabBar::tab:selected {{
            background: {theme['bg_secondary']};
            color: {theme['accent']};
            border: 1px solid {theme['border_color']};
            border-bottom: none;
        }}
        QLabel {{ color: {theme['text_primary']}; font-size: 11px; }}
        QLineEdit, QComboBox, QPlainTextEdit {{
            background: {theme['card_bg']};
            color: {theme['text_primary']};
            border: 1px solid {theme['border_color']};
            border-radius: 6px;
            padding: 5px 8px;
            font-size: 11px;
        }}
        QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {{ border-color: {theme['accent']}; }}
        QComboBox QAbstractItemView {{
            background: {theme['card_bg']};
            color: {theme['text_primary']};
            selection-background-color: {_rgba(theme['accent'], 0.25)};
        }}
        QPushButton {{
            background: {theme['card_bg']};
            color: {theme['text_primary']};
            border: 1px solid {theme['border_color']};
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 11px;
            font-weight: 600;
        }}
        QPushButton:hover {{ border-color: {theme['accent']}; color: {theme['accent']}; }}
        QPushButton:checked {{ background: {theme['accent']}; color: {theme['bg_color']}; }}
        QCheckBox {{ color: {theme['text_primary']}; font-size: 11px; }}
        QTableWidget {{
            background: {theme['card_bg']};
            color: {theme['text_primary']};
            gridline-color: {theme['border_color']};
            border: 1px solid {theme['border_color']};
            border-radius: 6px;
            font-size: 11px;
            selection-background-color: {_rgba(theme['accent'], 0.25)};
            selection-color: {theme['text_primary']};
        }}
        QHeaderView::section {{
            background: {theme['bg_color']};
            color: {theme['text_secondary']};
            border: none;
            border-bottom: 1px solid {theme['border_color']};
            padding: 4px;
            font-size: 10px;
            font-weight: 700;
        }}
    """
