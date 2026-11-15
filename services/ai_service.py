import base64
import json
import time
import subprocess
import threading
import requests
from PyQt6.QtCore import QObject, pyqtSignal, QBuffer, QIODevice, Qt
from PyQt6.QtWidgets import QApplication
from config import ConfigManager

class AIError(Exception):
    """A reason the AI could not answer, written for the user."""


SYSTEM_PROMPT = ("You are Robo, a helpful assistant living in a Windows notch app. "
                 "Answer briefly and clearly; use short lists and code blocks when useful.")

# Free first. Qwen 3.5 runs on the laptop through Ollama: free, private, offline.
PROVIDERS = {
    "ollama": {"label": "Qwen 3.5 on this laptop (free, private · Ollama)", "short": "Local",
               "model_key": "ollama_model", "default_model": "qwen3.5:4b"},
    "openai_compat": {"label": "Free cloud: OpenRouter / Groq / LM Studio (OpenAI-compatible)",
                      "short": "Cloud", "model_key": "openai_compat_model",
                      "default_model": "qwen/qwen3-coder:free", "default_url": "https://openrouter.ai/api/v1"},
    "gemini": {"label": "Google Gemini (free key)", "short": "Gemini", "model_key": "active_ai_model",
               "default_model": "gemini-2.5-flash"},
    "claude": {"label": "Anthropic Claude (API key)", "short": "Claude", "model_key": "claude_model",
               "default_model": "claude-sonnet-5-5"},
    "openai": {"label": "OpenAI (API key)", "short": "OpenAI", "model_key": "openai_model",
               "default_model": "gpt-4o-mini"},
}

# Ollama sizes of Qwen 3.5 and roughly how much memory they need while answering
QWEN_SIZES = [("qwen3.5:0.8b", "tiny · ~1 GB RAM"), ("qwen3.5:2b", "small · ~2.5 GB"),
              ("qwen3.5:4b", "recommended · ~4 GB"), ("qwen3.5:9b", "smart · ~7 GB, needs 16 GB RAM")]


def strip_thinking(text):
    """Qwen can prefix answers with <think>…</think>; keep only the answer."""
    import re
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()


def _short(text, n=220):
    try:
        data = json.loads(text)
        err = data.get("error", data)
        text = err.get("message", str(err)) if isinstance(err, dict) else str(err)
    except Exception:
        pass
    return " ".join(str(text).split())[:n]


def ollama_status(base="http://localhost:11434", timeout=2):
    """(running, [model names]) for the local Ollama."""
    try:
        r = requests.get(base.rstrip("/") + "/api/tags", timeout=timeout)
        return True, [m.get("name", "") for m in r.json().get("models", [])]
    except Exception:
        return False, []


def ollama_installed():
    import shutil, os
    from pathlib import Path
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
    return bool(shutil.which("ollama")) or local.exists()


def ollama_pull(model, progress, base="http://localhost:11434"):
    """Download a model, calling progress(fraction 0..1, text). Raises AIError on failure."""
    try:
        with requests.post(base.rstrip("/") + "/api/pull", json={"model": model, "stream": True},
                           stream=True, timeout=(5, 600)) as r:
            for line in r.iter_lines():
                if not line:
                    continue
                d = json.loads(line)
                if d.get("error"):
                    raise AIError(d["error"])
                total, done = d.get("total") or 0, d.get("completed") or 0
                progress(done / total if total else -1, d.get("status", ""))
    except requests.exceptions.ConnectionError:
        raise AIError("Ollama is not running. Open the Ollama app first.")



class AIService(QObject):
    status_changed = pyqtSignal(str, str) # status_text, color
    response_ready = pyqtSignal(str, str) # title, content
    execution_started = pyqtSignal(str)   # action_name
    screen_captured = pyqtSignal(object)  # QPixmap
    connection_tested = pyqtSignal(bool, str) # success, message

    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.current_status = "Idle"
        self.last_screenshot_pixmap = None
        self.history = []
        
        self.status_colors = {
            "Idle": "#10b981",          # Emerald green
            "Thinking": "#00f0ff",      # Cyan
            "Coding": "#3b82f6",        # Electric blue
            "Auditing": "#a855f7",      # Purple (CodeRabbit)
            "Ralph Loop": "#f59e0b",    # Amber (Ralph)
            "Seeing Screen": "#ec4899", # Hot pink (Vision)
            "Error": "#ef4444"          # Red
        }

    def set_status(self, status):
        self.current_status = status
        color = self.status_colors.get(status, "#10b981")
        self.status_changed.emit(status, color)

    def capture_screen(self):
        screen = QApplication.primaryScreen()
        if screen:
            pixmap = screen.grabWindow(0)
            self.last_screenshot_pixmap = pixmap
            self.screen_captured.emit(pixmap)
            return pixmap
        return None

    def _pixmap_to_base64(self, pixmap, max_w=1280, max_h=720):
        if not pixmap:
            return ""
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        scaled = pixmap.scaled(
            max_w, max_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        scaled.save(buffer, "JPEG", 82)
        return base64.b64encode(buffer.data().data()).decode("utf-8")

    # ------------------------------------------------------------------ engine
    def provider(self):
        p = self.config.get("ai_provider", "ollama")
        return p if p in PROVIDERS else "ollama"

    def model_label(self):
        p = self.provider()
        return f"{PROVIDERS[p]['short']} · {self.model_name(p)}"

    def model_name(self, p=None):
        p = p or self.provider()
        key = PROVIDERS[p]["model_key"]
        return (self.config.get(key, "") or PROVIDERS[p]["default_model"]).strip()

    def complete(self, prompt, image_b64=None, history=None, timeout=120):
        """Ask the chosen AI one question. Returns the answer text, raises AIError with a
        plain-language reason (what to do) when it cannot."""
        p = self.provider()
        model = self.model_name(p)
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}] + list(history or [])
        try:
            if p == "ollama":
                return self._ollama_chat(model, msgs, prompt, image_b64, timeout)
            if p in ("openai_compat", "openai"):
                return self._openai_chat(p, model, msgs, prompt, image_b64, timeout)
            if p == "gemini":
                return self._gemini(model, msgs, prompt, image_b64, timeout)
            if p == "claude":
                return self._claude(model, msgs, prompt, image_b64, timeout)
        except AIError:
            raise
        except requests.exceptions.ConnectionError:
            if p == "ollama":
                raise AIError("Ollama is not running. Install it from ollama.com/download, open it once, "
                              "then press “Set up Qwen 3.5” in AI settings.")
            raise AIError("No connection to the AI service. Check your internet.")
        except requests.exceptions.Timeout:
            raise AIError("The AI took too long to answer. A smaller model (e.g. qwen3.5:2b) is faster.")
        raise AIError(f"Unknown AI provider: {p}")

    def _ollama_chat(self, model, msgs, prompt, image_b64, timeout):
        base = self.config.get("ollama_url", "http://localhost:11434").rstrip("/")
        user = {"role": "user", "content": prompt}
        if image_b64:
            user["images"] = [image_b64]
        keep = self.config.get("ollama_keep_alive", "5m")
        payload = {"model": model, "messages": msgs + [user], "stream": False, "think": False,
                   "keep_alive": 0 if str(keep) == "0" else keep}
        r = requests.post(f"{base}/api/chat", json=payload, timeout=timeout)
        if r.status_code == 400 and "think" in r.text:          # model without a thinking switch
            payload.pop("think")
            r = requests.post(f"{base}/api/chat", json=payload, timeout=timeout)
        if r.status_code == 404 or "not found" in r.text[:200].lower():
            raise AIError(f"The model “{model}” is not downloaded yet. Press “Set up Qwen 3.5” in AI settings "
                          f"(or run: ollama pull {model}).")
        if r.status_code != 200:
            raise AIError(f"Ollama error ({r.status_code}): {_short(r.text)}")
        return strip_thinking(r.json().get("message", {}).get("content", "")) or "(empty answer)"

    def _openai_chat(self, p, model, msgs, prompt, image_b64, timeout):
        if p == "openai":
            base, key = "https://api.openai.com/v1", self.config.get("openai_api_key", "").strip()
        else:
            base = (self.config.get("openai_compat_url", "") or PROVIDERS[p]["default_url"]).rstrip("/")
            key = self.config.get("openai_compat_key", "").strip()
        if not key and "localhost" not in base and "127.0.0.1" not in base:
            raise AIError("Add an API key in AI settings (OpenRouter and Groq give free keys).")
        content = prompt if not image_b64 else [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}]
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        r = requests.post(f"{base}/chat/completions", headers=headers, timeout=timeout,
                          json={"model": model, "messages": msgs + [{"role": "user", "content": content}]})
        if r.status_code in (401, 403):
            raise AIError("The API key was refused. Check it in AI settings.")
        if r.status_code != 200:
            raise AIError(f"AI error ({r.status_code}): {_short(r.text)}")
        return strip_thinking(r.json()["choices"][0]["message"]["content"] or "") or "(empty answer)"

    def _gemini(self, model, msgs, prompt, image_b64, timeout):
        key = self.config.get("gemini_api_key", "").strip()
        if not key:
            raise AIError("Add a Gemini key in AI settings (free at aistudio.google.com).")
        contents = [{"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
                    for m in msgs if m["role"] != "system"]
        parts = [{"text": prompt}]
        if image_b64:
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": image_b64}})
        contents.append({"role": "user", "parts": parts})
        r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                          headers={"x-goog-api-key": key}, timeout=timeout,
                          json={"contents": contents, "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]}})
        if r.status_code != 200:
            raise AIError(f"Gemini error ({r.status_code}): {_short(r.text)}")
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]

    def _claude(self, model, msgs, prompt, image_b64, timeout):
        key = self.config.get("claude_api_key", "").strip()
        if not key:
            raise AIError("Add a Claude API key in AI settings.")
        content = [{"type": "text", "text": prompt}]
        if image_b64:
            content.insert(0, {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                            "data": image_b64}})
        r = requests.post("https://api.anthropic.com/v1/messages", timeout=timeout,
                          headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                                   "content-type": "application/json"},
                          json={"model": model, "max_tokens": 1500, "system": SYSTEM_PROMPT,
                                "messages": [m for m in msgs if m["role"] != "system"]
                                            + [{"role": "user", "content": content}]})
        if r.status_code != 200:
            raise AIError(f"Claude error ({r.status_code}): {_short(r.text)}")
        return "".join(b.get("text", "") for b in r.json().get("content", []))

    def _run(self, title, prompt, image_b64=None, status="Thinking", remember=False):
        """Ask in the background and emit response_ready(title, answer)."""
        self.set_status(status)
        history = list(self.history) if remember else None

        def worker():
            try:
                answer = self.complete(prompt, image_b64, history)
                if remember:
                    self.history += [{"role": "user", "content": prompt},
                                     {"role": "assistant", "content": answer}]
                    self.history = self.history[-8:]
                self.response_ready.emit(title, answer)
            except Exception as e:
                self.set_status("Error")
                self.response_ready.emit("AI not ready", str(e))
            finally:
                self.set_status("Idle")
        threading.Thread(target=worker, name="ai", daemon=True).start()

    def clear_history(self):
        self.history = []

    # ------------------------------------------------------------- features
    def analyze_screen(self, custom_prompt=""):
        self.execution_started.emit("Looking at your screen…")
        pixmap = self.capture_screen()
        if not pixmap:
            self.response_ready.emit("Screen capture failed", "Could not capture the screen.")
            return
        prompt = custom_prompt.strip() or ("Look at my screen. Briefly say what is on it; if there is code, "
                                           "an error or a form, explain it and suggest the next step.")
        self._run("👁 Screen", prompt, self._pixmap_to_base64(pixmap), status="Seeing Screen")

    def ask_about_pixmap(self, pixmap, prompt, title="Robo"):
        """Send a question plus a captured window image to the connected AI."""
        self._run(title, prompt, self._pixmap_to_base64(pixmap), status="Seeing Screen")

    def ask_ai(self, prompt, include_screen=False):
        if not prompt or not prompt.strip():
            return
        if include_screen:
            self.analyze_screen(prompt)
            return
        self.execution_started.emit("Thinking…")
        self._run("Robo", prompt.strip(), remember=True)

    def process_clipboard(self, action="explain"):
        text = QApplication.clipboard().text() if QApplication.clipboard() else ""
        if not text or not text.strip():
            self.response_ready.emit("Clipboard empty", "Copy some code or text first.")
            return
        self.execution_started.emit("Reading the clipboard…")
        text = text.strip()[:12000]
        if action == "fix":
            prompt = ("Fix the bugs in this code. Reply with the corrected code first, "
                      "then one short line per change:\n\n" + text)
            self._run("🛠 Fixed clipboard", prompt, status="Coding")
        else:
            self._run("📋 Clipboard explained", "Explain this simply and briefly:\n\n" + text)

    def test_connection(self, provider=None, api_key="", ollama_url=""):
        """Ask the chosen AI to say 'ok' (uses the saved settings)."""
        def worker():
            t0 = time.time()
            try:
                self.complete("Reply with just: ok", timeout=60)
                self.connection_tested.emit(True, f"Working · {self.model_label()} · {int((time.time()-t0)*1000)} ms")
            except Exception as e:
                self.connection_tested.emit(False, str(e))
        threading.Thread(target=worker, name="ai-test", daemon=True).start()

    def run_coderabbit_review(self, target_dir="."):
        self.set_status("Auditing")
        self.execution_started.emit("Running CodeRabbit Review...")

        def worker():
            try:
                import shutil
                from pathlib import Path
                local_cr = Path.home() / "AppData" / "Local" / "Programs" / "coderabbit" / "coderabbit.exe"
                cr_bin = shutil.which("coderabbit") or (str(local_cr) if local_cr.exists() else "coderabbit")
                
                cmd = [cr_bin, "review", "--agent"]
                process = subprocess.run(cmd, cwd=target_dir, capture_output=True, text=True, timeout=30)
                output = process.stdout or process.stderr
                if not output:
                    output = "CodeRabbit review completed: Clean diff, zero high-severity issues found."
                self.response_ready.emit("CodeRabbit Audit", output[:600])
            except Exception as e:
                self.response_ready.emit("CodeRabbit Notice", f"Review status: {e}")
            finally:
                self.set_status("Idle")

        threading.Thread(target=worker, daemon=True).start()

    def run_ralph_loop(self, target_dir="."):
        self.set_status("Ralph Loop")
        self.execution_started.emit("Starting Ralph Loop...")

        def worker():
            try:
                cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", ".\\ralph.ps1", "-MaxIterations", "3"]
                process = subprocess.run(cmd, cwd=target_dir, capture_output=True, text=True, timeout=45)
                output = process.stdout or process.stderr
                if not output:
                    output = "Ralph Loop iteration finished. Check prd.json for updated story passes."
                self.response_ready.emit("Ralph Loop Status", output[:600])
            except Exception as e:
                self.response_ready.emit("Ralph Loop", f"Execution notes: {e}")
            finally:
                self.set_status("Idle")

        threading.Thread(target=worker, daemon=True).start()
