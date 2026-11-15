"""Use your own AI account (Claude Pro/Max, ChatGPT Plus/Pro, a Google account for Gemini)
instead of an API key or a local model.

It works through each company's official command-line app, which signs in with your account
in your browser once and then answers questions. Robo sends the question on stdin (never on
the command line) and reads the answer back. Nothing is stored by this app: the sign-in lives
in the official tool."""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

TOOLS = {
    "claude": {"label": "Claude (Pro / Max account)", "exe": "claude", "name": "Claude",
               "package": "@anthropic-ai/claude-code", "login": "claude",
               "login_hint": "In the window that opens, follow the steps to sign in, then type /exit."},
    "codex": {"label": "ChatGPT (Plus / Pro account, via Codex)", "exe": "codex", "name": "ChatGPT",
              "package": "@openai/codex", "login": "codex login",
              "login_hint": "Your browser opens: sign in with your ChatGPT account."},
    "gemini": {"label": "Gemini (free with a Google account)", "exe": "gemini", "name": "Gemini",
               "package": "@google/gemini-cli", "login": "gemini",
               "login_hint": "Choose “Login with Google”, sign in, then type /quit."},
}
NO_WINDOW = 0x08000000 if os.name == "nt" else 0          # CREATE_NO_WINDOW
NEW_CONSOLE = 0x00000010 if os.name == "nt" else 0         # CREATE_NEW_CONSOLE


class AccountError(Exception):
    pass


def find(tool):
    """Full path of the tool's program, or None. Also looks where npm puts global tools,
    because apps started at login may not have that folder on PATH."""
    exe = TOOLS[tool]["exe"]
    found = shutil.which(exe)
    if found:
        return found
    extra = [Path(os.environ.get("APPDATA", "")) / "npm", Path.home() / ".local" / "bin",
             Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / exe]
    for folder in extra:
        for name in (exe + ".cmd", exe + ".exe", exe):
            p = folder / name
            if p.is_file():
                return str(p)
    return None


def npm_available():
    return bool(shutil.which("npm"))


def build_command(tool, exe, image_path=None, out_file=None):
    """Arguments for one non-interactive question (the question itself goes on stdin)."""
    if tool == "claude":
        cmd = [exe, "-p", "--output-format", "text"]
        if image_path:
            cmd += ["--allowedTools", "Read"]
        return cmd
    if tool == "codex":
        cmd = [exe, "exec", "--skip-git-repo-check", "--sandbox", "read-only", "--color", "never"]
        if out_file:
            cmd += ["--output-last-message", out_file]
        if image_path:
            cmd += ["--image", image_path]
        return cmd + ["-"]
    if tool == "gemini":
        return [exe]
    raise AccountError(f"Unknown account type: {tool}")


def build_prompt(tool, prompt, history=None, image_path=None, system=""):
    lines = [system] if system else []
    if history:
        lines.append("Earlier in this chat:")
        for m in history[-8:]:
            who = "You" if m["role"] == "assistant" else "User"
            lines.append(f"{who}: {m['content']}")
        lines.append("")
    if image_path:
        lines.append(f"@{image_path}" if tool == "gemini" else
                     f"The screenshot is the image file {image_path} (look at it to answer).")
    lines.append(prompt)
    return "\n".join(lines)


def ask(tool, prompt, history=None, image_b64=None, system="", timeout=180, runner=subprocess.run):
    """Ask through the signed-in tool and return the answer. Raises AccountError."""
    exe = find(tool)
    if not exe:
        raise AccountError(f"{TOOLS[tool]['name']} is not set up yet. In AI settings press "
                           f"“1 · Install” and then “2 · Sign in”.")
    with tempfile.TemporaryDirectory(prefix="island-ai-") as work:
        image_path = None
        if image_b64:
            import base64
            image_path = os.path.join(work, "screen.jpg")
            with open(image_path, "wb") as f:
                f.write(base64.b64decode(image_b64))
        out_file = os.path.join(work, "answer.txt") if tool == "codex" else None
        text = build_prompt(tool, prompt, history, image_path, system)
        try:
            r = runner(build_command(tool, exe, image_path, out_file), input=text, cwd=work,
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout, creationflags=NO_WINDOW)
        except subprocess.TimeoutExpired:
            raise AccountError(f"{TOOLS[tool]['name']} took too long to answer.")
        except OSError as e:
            raise AccountError(f"Could not start {TOOLS[tool]['name']}: {e}")
        answer = ""
        if out_file and os.path.exists(out_file):
            answer = Path(out_file).read_text(encoding="utf-8", errors="replace")
        answer = (answer or r.stdout or "").strip()
        if r.returncode != 0 or not answer:
            err = " ".join((r.stderr or r.stdout or "").split())[-300:]
            low = err.lower()
            if any(w in low for w in ("login", "log in", "sign in", "auth", "unauthorized", "401")):
                raise AccountError(f"{TOOLS[tool]['name']} needs you to sign in: press “2 · Sign in” "
                                   f"in AI settings.")
            raise AccountError(f"{TOOLS[tool]['name']} did not answer: {err or 'no output'}")
        return answer


def open_terminal(command_line, title="Dynamic Island"):
    """Open a visible console window running command_line (for installing / signing in)."""
    if os.name == "nt":
        return subprocess.Popen(["cmd.exe", "/k", command_line], creationflags=NEW_CONSOLE)
    for term in ("x-terminal-emulator", "gnome-terminal", "konsole", "xterm"):
        if shutil.which(term):
            return subprocess.Popen([term, "-e", command_line])
    raise AccountError("No terminal window found.")


def install_command(tool):
    return f"npm install -g {TOOLS[tool]['package']}"


def login_command(tool):
    exe = find(tool)
    base = TOOLS[tool]["login"]
    if exe and " " in exe:
        exe = f'"{exe}"'
    return base.replace(TOOLS[tool]["exe"], exe, 1) if exe else base
