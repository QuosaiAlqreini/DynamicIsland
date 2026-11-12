"""Follow AI coding agents (Claude Code, Codex) from the island.

Claude Code posts its hook events to a small server on 127.0.0.1 (HTTP hooks
in ~/.claude/settings.json). From those we show live activity, let the user
answer permission requests (Allow / Deny), and announce when work is done.

Safety: the server only listens on this PC, every request must carry a secret
token, and a permission is only ever granted by the user clicking Allow. With
no answer (or the island closed) Claude Code falls back to its own prompt.
"""
import json
import os
import secrets
import shutil
import sys
import threading
import time
import uuid
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from config import ConfigManager

HOOK_EVENTS = ["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUseFailure",
               "PermissionRequest", "Notification", "Stop", "SessionEnd"]
PERMISSION_WAIT_S = 110          # how long the island holds a permission request open
MARKER = "X-Island-Token"        # identifies the hooks this app installed


def _short(text, limit=70):
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _name(path):
    return os.path.basename(str(path or "").replace("\\", "/").rstrip("/")) or str(path or "")


def describe_tool(tool, tool_input):
    """Human line for a tool call: ('📖', 'Reading app.py')."""
    ti = tool_input if isinstance(tool_input, dict) else {}
    if tool == "Read":
        return "📖", f"Reading {_name(ti.get('file_path'))}"
    if tool in ("Edit", "MultiEdit", "NotebookEdit"):
        return "✏️", f"Editing {_name(ti.get('file_path') or ti.get('notebook_path'))}"
    if tool == "Write":
        return "📝", f"Writing {_name(ti.get('file_path'))}"
    if tool == "Bash":
        return "▶", _short(ti.get("command"), 60)
    if tool in ("Grep", "Glob"):
        return "🔎", f"Searching {_short(ti.get('pattern'), 40)}"
    if tool in ("WebFetch", "WebSearch"):
        return "🌐", _short(ti.get("url") or ti.get("query"), 50)
    if tool in ("Task", "Agent"):
        return "🤖", f"Helper: {_short(ti.get('description'), 45)}"
    if tool == "TodoWrite":
        return "📋", "Updating the plan"
    if tool and tool.startswith("mcp__"):
        return "🔌", tool.split("__", 2)[-1].replace("_", " ")
    return "🔧", tool or "Working"


def claude_hook_entries(port, token):
    """The hooks block this app adds to ~/.claude/settings.json."""
    out = {}
    for event in HOOK_EVENTS:
        hook = {"type": "http", "url": f"http://127.0.0.1:{port}/hook",
                "headers": {MARKER: token},
                "timeout": PERMISSION_WAIT_S + 10 if event == "PermissionRequest" else 5}
        out[event] = [{"hooks": [hook]}]
    return out


def _is_ours(group):
    return any(MARKER in (h.get("headers") or {}) for h in group.get("hooks", []) if isinstance(h, dict))


def merge_claude_settings(settings, port, token):
    """Return settings with our hooks added (replacing older copies of ours only)."""
    settings = dict(settings or {})
    hooks = dict(settings.get("hooks") or {})
    for event, groups in claude_hook_entries(port, token).items():
        existing = [g for g in hooks.get(event, []) if isinstance(g, dict) and not _is_ours(g)]
        hooks[event] = existing + groups
    settings["hooks"] = hooks
    return settings


def strip_claude_settings(settings):
    """Return settings with only our hooks removed."""
    settings = dict(settings or {})
    hooks = {}
    for event, groups in (settings.get("hooks") or {}).items():
        kept = [g for g in groups if not (isinstance(g, dict) and _is_ours(g))]
        if kept:
            hooks[event] = kept
    if hooks:
        settings["hooks"] = hooks
    else:
        settings.pop("hooks", None)
    return settings


class AgentService(QObject):
    changed = pyqtSignal()
    permission_requested = pyqtSignal(dict)
    finished = pyqtSignal(dict)        # {"agent", "project", "answer"}
    needs_attention = pyqtSignal(str)  # agent is waiting for the user
    _event = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = ConfigManager()
        self.sessions = {}                 # session id -> state dict
        self.feed = deque(maxlen=60)       # newest first: {"t", "icon", "text", "project", "agent"}
        self.pending = []                  # permission requests waiting for the user
        self._waiters = {}                 # request id -> (threading.Event, result holder)
        self.server = None
        self.error = ""
        self._event.connect(self._handle_event)
        self._idle_timer = QTimer(self)
        self._idle_timer.setInterval(30000)
        self._idle_timer.timeout.connect(self._expire_sessions)
        self._idle_timer.start()

    # ------------------------------------------------------------ config
    @property
    def port(self):
        return int(self.config.get("agent_port", 47821))

    @property
    def token(self):
        token = self.config.get("agent_token", "")
        if not token:
            token = secrets.token_urlsafe(24)
            self.config.set("agent_token", token)
        return token

    # ------------------------------------------------------------ server
    def start(self):
        if self.server is not None:
            return True
        service, token = self, self.token

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _reply(self, code, body=b""):
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if body:
                    self.wfile.write(body)

            def do_POST(self):
                try:
                    if self.headers.get(MARKER) != token:
                        return self._reply(403)
                    length = min(int(self.headers.get("Content-Length") or 0), 2_000_000)
                    data = json.loads(self.rfile.read(length) or b"{}")
                    if not isinstance(data, dict):
                        return self._reply(400)
                    if self.path.startswith("/codex"):
                        data = {"hook_event_name": "CodexNotify", "payload": data}
                    if data.get("hook_event_name") == "PermissionRequest":
                        decision = service._wait_for_decision(data)
                        return self._reply(200, json.dumps(decision).encode() if decision else b"")
                    service._event.emit(data)
                    self._reply(200)
                except Exception:
                    try:
                        self._reply(200)     # never break the agent because of the island
                    except Exception:
                        pass

        try:
            self.server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        except OSError as e:
            self.error = f"Port {self.port} is in use ({e.__class__.__name__})"
            self.server = None
            return False
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, name="agent-hooks", daemon=True).start()
        self.error = ""
        return True

    def stop(self):
        if self.server is not None:
            for event, holder in list(self._waiters.values()):
                event.set()
            server, self.server = self.server, None
            threading.Thread(target=server.shutdown, daemon=True).start()

    # ------------------------------------------------- permission requests
    def _wait_for_decision(self, data):
        """Runs on a server thread: ask the UI, wait for Allow / Deny."""
        req_id = uuid.uuid4().hex[:10]
        event, holder = threading.Event(), {}
        self._waiters[req_id] = (event, holder)
        data = dict(data, _request_id=req_id)
        self._event.emit(data)
        event.wait(PERMISSION_WAIT_S)
        self._waiters.pop(req_id, None)
        self._event.emit({"hook_event_name": "_PermissionClosed", "_request_id": req_id})
        behavior = holder.get("behavior")
        if behavior not in ("allow", "deny"):
            return None                      # no answer: Claude Code asks in the terminal instead
        decision = {"behavior": behavior}
        if behavior == "deny":
            decision["message"] = holder.get("message") or "Denied from Dynamic Island"
        return {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": decision}}

    def decide(self, request_id, allow, message=""):
        waiter = self._waiters.get(request_id)
        if waiter:
            event, holder = waiter
            holder["behavior"] = "allow" if allow else "deny"
            holder["message"] = message
            event.set()
        for req in self.pending:
            if req["id"] == request_id and req["session"] in self.sessions:
                s = self.sessions[req["session"]]
                s["status"] = "working"
                s["activity"] = "Allowed, continuing" if allow else "Denied"
                self._log(s, "✓" if allow else "✕", f"{'Allowed' if allow else 'Denied'}: {req['summary']}")
        self.pending = [p for p in self.pending if p["id"] != request_id]
        self.changed.emit()

    # -------------------------------------------------------------- events
    def _session(self, data, agent="Claude Code"):
        sid = data.get("session_id") or "default"
        s = self.sessions.get(sid)
        if s is None:
            s = self.sessions[sid] = {"id": sid, "agent": agent, "project": "", "status": "idle",
                                      "activity": "", "answer": "", "updated": time.time()}
        if data.get("cwd"):
            s["project"] = _name(data["cwd"])
        s["updated"] = time.time()
        return s

    def _log(self, session, icon, text):
        self.feed.appendleft({"t": time.time(), "icon": icon, "text": text,
                              "project": session["project"], "agent": session["agent"]})

    def _handle_event(self, data):
        kind = data.get("hook_event_name", "")
        if kind == "_PermissionClosed":
            self.pending = [p for p in self.pending if p["id"] != data.get("_request_id")]
            self.changed.emit()
            return
        if kind == "CodexNotify":
            return self._handle_codex(data.get("payload") or {})
        s = self._session(data)
        if kind == "SessionStart":
            s["status"] = "idle"
            self._log(s, "👋", "Session started")
        elif kind == "UserPromptSubmit":
            s["status"], s["activity"] = "working", "Thinking…"
            self._log(s, "💬", _short(data.get("prompt"), 80))
        elif kind == "PreToolUse":
            icon, text = describe_tool(data.get("tool_name"), data.get("tool_input"))
            s["status"], s["activity"] = "working", f"{icon} {text}"
            self._log(s, icon, text)
        elif kind == "PostToolUseFailure":
            self._log(s, "⚠️", f"{data.get('tool_name', 'Tool')} failed")
        elif kind == "PermissionRequest":
            icon, text = describe_tool(data.get("tool_name"), data.get("tool_input"))
            ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
            detail = ti.get("command") or ti.get("file_path") or ti.get("url") or json.dumps(ti)[:400]
            req = {"id": data.get("_request_id"), "session": s["id"], "agent": s["agent"],
                   "project": s["project"], "tool": data.get("tool_name", ""), "icon": icon,
                   "summary": text, "detail": str(detail)[:600]}
            self.pending.append(req)
            s["status"], s["activity"] = "waiting", f"Asks: {text}"
            self._log(s, "🙋", f"Asks permission: {text}")
            self.permission_requested.emit(req)
        elif kind == "Notification":
            message = data.get("message") or "Needs your attention"
            if data.get("notification_type") in ("idle_prompt", "permission_prompt", "elicitation_dialog") \
                    or "permission" in message.lower() or "waiting" in message.lower():
                if s["status"] != "waiting":
                    s["status"], s["activity"] = "waiting", _short(message, 60)
                    self.needs_attention.emit(message)
            self._log(s, "🔔", _short(message, 80))
        elif kind == "Stop":
            answer = data.get("last_assistant_message") or ""
            s["status"], s["activity"], s["answer"] = "done", "Finished", str(answer)[:4000]
            self._log(s, "✅", "Finished")
            self.finished.emit({"agent": s["agent"], "project": s["project"], "answer": s["answer"]})
        elif kind == "SessionEnd":
            self._log(s, "👋", "Session ended")
            self.sessions.pop(s["id"], None)
        self.changed.emit()

    def _handle_codex(self, payload):
        if payload.get("type") not in (None, "agent-turn-complete"):
            return
        s = self._session({"session_id": "codex-" + str(payload.get("thread-id") or payload.get("turn-id") or ""),
                           "cwd": payload.get("cwd")}, agent="Codex")
        answer = payload.get("last-assistant-message") or ""
        s["status"], s["activity"], s["answer"] = "done", "Finished", str(answer)[:4000]
        self._log(s, "✅", "Finished")
        self.finished.emit({"agent": "Codex", "project": s["project"], "answer": s["answer"]})
        self.changed.emit()

    def _expire_sessions(self):
        now = time.time()
        changed = False
        for sid, s in list(self.sessions.items()):
            age = now - s["updated"]
            if s["status"] == "working" and age > 300:
                s["status"], s["activity"] = "idle", ""
                changed = True
            elif age > 4 * 3600:
                del self.sessions[sid]
                changed = True
        if changed:
            self.changed.emit()

    # ------------------------------------------------------------- status
    def summary(self):
        """(status, text) for the pill: waiting > working > done > idle."""
        order = {"waiting": 3, "working": 2, "done": 1, "idle": 0}
        if not self.sessions:
            return "idle", ""
        s = max(self.sessions.values(), key=lambda x: (order.get(x["status"], 0), x["updated"]))
        return s["status"], s["activity"]

    # ----------------------------------------------- connect / disconnect
    @staticmethod
    def claude_settings_path():
        return Path.home() / ".claude" / "settings.json"

    def claude_connected(self):
        try:
            data = json.loads(self.claude_settings_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        return any(_is_ours(g) for groups in (data.get("hooks") or {}).values()
                   for g in groups if isinstance(g, dict))

    def _write_claude(self, transform):
        path = self.claude_settings_path()
        try:
            text = path.read_text(encoding="utf-8") if path.exists() else "{}"
            data = json.loads(text or "{}")
            if not isinstance(data, dict):
                return False, "settings.json has an unexpected format; nothing was changed."
        except ValueError:
            return False, "Your Claude Code settings.json is not valid JSON; nothing was changed."
        except OSError as e:
            return False, f"Could not read settings.json: {e}"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                shutil.copy2(path, path.with_name("settings.json.island-backup"))
            tmp = path.with_name("settings.json.island-tmp")
            tmp.write_text(json.dumps(transform(data), indent=2) + "\n", encoding="utf-8")
            os.replace(tmp, path)
        except OSError as e:
            return False, f"Could not write settings.json: {e}"
        return True, ""

    def connect_claude(self):
        ok, err = self._write_claude(lambda d: merge_claude_settings(d, self.port, self.token))
        return ok, err or "Connected. Start a new Claude Code session (or run /hooks in an open one) to begin."

    def disconnect_claude(self):
        ok, err = self._write_claude(strip_claude_settings)
        return ok, err or "Disconnected. Your other Claude Code settings were left untouched."

    # Codex: its `notify` setting runs a program when a turn completes
    @staticmethod
    def codex_config_path():
        return Path.home() / ".codex" / "config.toml"

    def codex_notify_line(self):
        script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "hooks", "codex_notify.py"))
        exe = sys.executable.replace("pythonw.exe", "python.exe")
        return "notify = " + json.dumps([exe, script, str(self.port), self.token])

    def codex_connected(self):
        try:
            return "codex_notify.py" in self.codex_config_path().read_text(encoding="utf-8")
        except OSError:
            return False

    def connect_codex(self):
        if getattr(sys, "frozen", False):
            return False, "Codex alerts need the Python version of the island (run from source)."
        path = self.codex_config_path()
        try:
            text = path.read_text(encoding="utf-8") if path.exists() else ""
        except OSError as e:
            return False, f"Could not read config.toml: {e}"
        lines = [l for l in text.splitlines() if "codex_notify.py" not in l]
        if any(l.strip().startswith("notify") and "=" in l for l in lines):
            return False, ("Codex already has a notify program set in config.toml. "
                           "I left it alone; remove that line first if you want the island to use it.")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                shutil.copy2(path, path.with_name("config.toml.island-backup"))
            # top-level keys must come before the first [table]
            path.write_text("\n".join([self.codex_notify_line()] + lines) + "\n", encoding="utf-8")
        except OSError as e:
            return False, f"Could not write config.toml: {e}"
        return True, "Connected. Codex will tell the island when it finishes a turn."

    def disconnect_codex(self):
        path = self.codex_config_path()
        try:
            lines = [l for l in path.read_text(encoding="utf-8").splitlines() if "codex_notify.py" not in l]
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except OSError as e:
            return False, f"Could not update config.toml: {e}"
        return True, "Disconnected from Codex."
