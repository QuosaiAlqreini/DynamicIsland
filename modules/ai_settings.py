"""AI settings: which AI Robo uses.

Free first: Qwen 3.5 running on this laptop through Ollama (no account, private, works
offline). Or a free cloud (OpenRouter / Groq / LM Studio, any OpenAI-compatible API),
or your own Gemini / Claude / OpenAI key."""
import threading
import webbrowser

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QProgressBar, QCheckBox, QWidget
)

from config import ConfigManager
from services.ai_service import (PROVIDERS, QWEN_SIZES, AIError, ollama_status, ollama_installed,
                                 ollama_pull)
from styles import dialog_style

KEY_FIELDS = {"openai_compat": "openai_compat_key", "gemini": "gemini_api_key",
              "claude": "claude_api_key", "openai": "openai_api_key"}
KEY_LINKS = {"openai_compat": "https://openrouter.ai/keys", "gemini": "https://aistudio.google.com/app/apikey",
             "claude": "https://console.anthropic.com/", "openai": "https://platform.openai.com/api-keys"}
CLOUD_PRESETS = [("OpenRouter (free models)", "https://openrouter.ai/api/v1", "qwen/qwen3-coder:free"),
                 ("Groq (free tier, very fast)", "https://api.groq.com/openai/v1", "qwen/qwen3-32b"),
                 ("LM Studio on this laptop", "http://localhost:1234/v1", "")]


class AISettingsDialog(QDialog):
    _pull_progress = pyqtSignal(float, str)
    _pull_done = pyqtSignal(bool, str)
    _status_done = pyqtSignal(bool, bool, list)

    def __init__(self, theme, ai_service, parent=None):
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowTitle("AI settings")
        self.setStyleSheet(dialog_style(theme))
        self.setMinimumWidth(520)
        self.theme, self.ai, self.config = theme, ai_service, ConfigManager()
        c = self.config

        root = QVBoxLayout(self)
        intro = QLabel("Robo answers with the AI you pick here. <b>Qwen 3.5 on this laptop</b> is free, "
                       "private and works offline.")
        intro.setWordWrap(True)
        root.addWidget(intro)

        form = QFormLayout()
        self.provider = QComboBox()
        for key, p in PROVIDERS.items():
            self.provider.addItem(p["label"], key)
        self.provider.setCurrentIndex(max(0, self.provider.findData(self.ai.provider())))
        self.provider.currentIndexChanged.connect(self._show_fields)
        form.addRow("AI", self.provider)

        # --- local (Ollama)
        self.local_box = QWidget()
        lf = QFormLayout(self.local_box)
        lf.setContentsMargins(0, 0, 0, 0)
        self.size = QComboBox()
        self.size.setEditable(True)
        for name, note in QWEN_SIZES:
            self.size.addItem(f"{name}   ({note})", name)
        self._set_combo_text(self.size, c.get("ollama_model", "qwen3.5:4b"))
        lf.addRow("Model", self.size)
        row = QHBoxLayout()
        self.btn_setup = QPushButton("⬇ Set up Qwen 3.5")
        self.btn_setup.clicked.connect(self._setup_local)
        row.addWidget(self.btn_setup)
        self.local_state = QLabel("Checking Ollama…")
        self.local_state.setWordWrap(True)
        row.addWidget(self.local_state, 1)
        lf.addRow(row)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.hide()
        lf.addRow(self.bar)
        self.keep = QCheckBox("Free the RAM right after each answer (slower next answer)")
        self.keep.setChecked(c.get("ollama_keep_alive", "5m") == "0")
        lf.addRow(self.keep)
        form.addRow(self.local_box)

        # --- cloud / keys
        self.cloud_box = QWidget()
        cf = QFormLayout(self.cloud_box)
        cf.setContentsMargins(0, 0, 0, 0)
        self.preset = QComboBox()
        self.preset.addItem("Choose a service…", None)
        for label, url, model in CLOUD_PRESETS:
            self.preset.addItem(label, (url, model))
        self.preset.currentIndexChanged.connect(self._use_preset)
        cf.addRow("Service", self.preset)
        self.url = QLineEdit(c.get("openai_compat_url", PROVIDERS["openai_compat"]["default_url"]))
        cf.addRow("Address", self.url)
        self.url_row_label = cf.labelForField(self.url)
        form.addRow(self.cloud_box)

        self.model = QLineEdit()
        form.addRow("Model", self.model)
        self.model_label = form.labelForField(self.model)
        key_row = QHBoxLayout()
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText("Paste the API key")
        key_row.addWidget(self.key, 1)
        self.btn_key = QPushButton("Get a key")
        self.btn_key.clicked.connect(lambda: webbrowser.open(KEY_LINKS.get(self.provider.currentData(), "")))
        key_row.addWidget(self.btn_key)
        self.key_widget = QWidget()
        self.key_widget.setLayout(key_row)
        key_row.setContentsMargins(0, 0, 0, 0)
        form.addRow("Key", self.key_widget)
        self.key_label = form.labelForField(self.key_widget)
        self.vision = QCheckBox("Allow 👁 (Robo may look at the screen when you ask it to)")
        self.vision.setChecked(c.get("ai_vision_enabled", True))
        form.addRow(self.vision)
        root.addLayout(form)

        self.test_state = QLabel("")
        self.test_state.setWordWrap(True)
        root.addWidget(self.test_state)
        btns = QHBoxLayout()
        self.btn_test = QPushButton("⚡ Save && test")
        self.btn_test.clicked.connect(self._test)
        btns.addWidget(self.btn_test)
        btns.addStretch()
        done = QPushButton("Done")
        done.setDefault(True)
        done.clicked.connect(self._save_and_close)
        btns.addWidget(done)
        root.addLayout(btns)

        self._pull_progress.connect(self._on_pull_progress)
        self._pull_done.connect(self._on_pull_done)
        self._status_done.connect(self._on_status)
        self.ai.connection_tested.connect(self._on_tested)
        self._loaded_provider = None
        self._show_fields()
        self._check_local()

    # ------------------------------------------------------------ fields
    @staticmethod
    def _set_combo_text(combo, value):
        i = combo.findData(value)
        if i >= 0:
            combo.setCurrentIndex(i)
        else:
            combo.setEditText(value)

    def _local_model(self):
        text = self.size.currentText().strip()
        data = self.size.currentData()
        return data if data and text.startswith(data) else text.split()[0] if text else "qwen3.5:4b"

    def _store_fields(self, p):
        """Remember what was typed for provider p (so switching back and forth keeps it)."""
        if not p or p == "ollama":
            return
        self.config.data[PROVIDERS[p]["model_key"]] = self.model.text().strip() or PROVIDERS[p]["default_model"]
        self.config.data[KEY_FIELDS[p]] = self.key.text().strip()
        if p == "openai_compat":
            self.config.data["openai_compat_url"] = self.url.text().strip() or PROVIDERS[p]["default_url"]

    def _show_fields(self, *_):
        self._store_fields(self._loaded_provider)
        p = self.provider.currentData()
        self._loaded_provider = p
        local = p == "ollama"
        self.local_box.setVisible(local)
        self.cloud_box.setVisible(p == "openai_compat")
        for w in (self.model, self.model_label, self.key_widget, self.key_label):
            w.setVisible(not local)
        if not local:
            self.model.setText(self.config.get(PROVIDERS[p]["model_key"], "") or PROVIDERS[p]["default_model"])
            self.key.setText(self.config.get(KEY_FIELDS[p], ""))
            self.key.setPlaceholderText("Not needed for LM Studio" if p == "openai_compat" else "Paste the API key")
        self.adjustSize()

    def _use_preset(self, i):
        data = self.preset.itemData(i)
        if data:
            self.url.setText(data[0])
            if data[1]:
                self.model.setText(data[1])
            KEY_LINKS["openai_compat"] = ("https://console.groq.com/keys" if "groq" in data[0]
                                          else "https://openrouter.ai/keys")

    def _save(self):
        p = self.provider.currentData()
        self._store_fields(p)
        c = self.config
        c.data["ai_provider"] = p
        c.data["ollama_model"] = self._local_model()
        c.data["ollama_keep_alive"] = "0" if self.keep.isChecked() else "5m"
        c.data["ai_vision_enabled"] = self.vision.isChecked()
        c.save()

    def _save_and_close(self):
        self._save()
        self.accept()

    # ------------------------------------------------------------ local setup
    def _base(self):
        return self.config.get("ollama_url", "http://localhost:11434")

    def _check_local(self):
        base = self._base()
        threading.Thread(target=lambda: self._status_done.emit(ollama_installed(), *ollama_status(base)),
                         daemon=True).start()

    def _on_status(self, installed, running, models):
        want = self._local_model()
        if want in models or f"{want}:latest" in models:
            self.local_state.setText(f"✅ Ready: {want} is on this laptop.")
            self.btn_setup.setText("✓ Ready")
        elif running:
            self.local_state.setText(f"Ollama is running. Press the button to download {want} (one time).")
            self.btn_setup.setText(f"⬇ Download {want}")
        elif installed:
            self.local_state.setText("Ollama is installed but not running: open the Ollama app, then press the button.")
            self.btn_setup.setText("↻ Check again")
        else:
            self.local_state.setText("Step 1: install Ollama (free, from ollama.com). Step 2: come back and press the button.")
            self.btn_setup.setText("⬇ Get Ollama")
        self._state = (installed, running, models)

    def _setup_local(self):
        installed, running, models = getattr(self, "_state", (False, False, []))
        want = self._local_model()
        if not running:
            if not installed:
                webbrowser.open("https://ollama.com/download/windows")
            self._check_local()
            return
        if want in models or f"{want}:latest" in models:
            self._test()
            return
        self.btn_setup.setEnabled(False)
        self.bar.show()
        self.bar.setValue(0)
        base = self._base()

        def work():
            try:
                ollama_pull(want, lambda f, s: self._pull_progress.emit(f, s), base)
                self._pull_done.emit(True, f"✅ {want} downloaded. Robo is ready.")
            except AIError as e:
                self._pull_done.emit(False, f"⚠️ {e}")
            except Exception as e:
                self._pull_done.emit(False, f"⚠️ Download failed: {e}")
        threading.Thread(target=work, name="ollama-pull", daemon=True).start()

    def _on_pull_progress(self, fraction, text):
        if fraction >= 0:
            self.bar.setRange(0, 1000)
            self.bar.setValue(int(fraction * 1000))
            self.local_state.setText(f"Downloading… {int(fraction * 100)}%")
        else:
            self.bar.setRange(0, 0)
            self.local_state.setText(text.capitalize() or "Working…")

    def _on_pull_done(self, ok, text):
        self.btn_setup.setEnabled(True)
        self.bar.hide()
        self.local_state.setText(text)
        if ok:
            self.provider.setCurrentIndex(self.provider.findData("ollama"))
            self._check_local()

    # ------------------------------------------------------------ test
    def _test(self):
        self._save()
        self.test_state.setText("Asking the AI to say ok…")
        self.ai.test_connection()

    def _on_tested(self, ok, message):
        self.test_state.setText(("✅ " if ok else "⚠️ ") + message)

    def done(self, r):
        try:
            self.ai.connection_tested.disconnect(self._on_tested)
        except TypeError:
            pass
        super().done(r)
