"""Logic behind the command bar: calculator, text tools and the app index."""
import ast
import base64
import json
import math
import operator
import os
import sys
import threading
import urllib.parse

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
        ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos}
_FUNCS = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan, "log": math.log10,
          "ln": math.log, "abs": abs, "round": round, "floor": math.floor, "ceil": math.ceil}
_CONSTS = {"pi": math.pi, "e": math.e}


def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and (abs(right) > 200 or abs(left) > 1e6):
            raise ValueError("too large")
        return _OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Name) and node.id in _CONSTS:
        return _CONSTS[node.id]
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in _FUNCS and not node.keywords):
        return _FUNCS[node.func.id](*[_eval(a) for a in node.args])
    raise ValueError("unsupported")


def calculate(text):
    """'2*(3+4)' -> '14'. Returns None when the text is not a calculation."""
    expr = text.strip().lstrip("=").replace("^", "**").replace("×", "*").replace("÷", "/").replace(",", "")
    if not expr or not any(c.isdigit() for c in expr) or expr.replace(".", "", 1).isdigit():
        return None
    if "%" in expr and "% " not in expr:
        expr = expr.replace("%", "/100")       # 15% of 80 style: 80*15%
    try:
        value = _eval(ast.parse(expr, mode="eval").body)
    except Exception:
        return None
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        value = round(value, 10)
        if value == int(value) and abs(value) < 1e15:
            value = int(value)
    return f"{value:,}" if isinstance(value, int) else f"{value:,.10g}"


def _pretty_json(s):
    return json.dumps(json.loads(s), indent=2, ensure_ascii=False)


# name -> (description, function applied to the clipboard text)
TEXT_TOOLS = {
    "upper": ("UPPERCASE the clipboard", str.upper),
    "lower": ("lowercase the clipboard", str.lower),
    "title": ("Title Case the clipboard", str.title),
    "trim": ("Trim spaces and blank lines", lambda s: "\n".join(l.strip() for l in s.strip().splitlines() if l.strip())),
    "base64": ("Encode clipboard as Base64", lambda s: base64.b64encode(s.encode()).decode()),
    "unbase64": ("Decode Base64 in clipboard", lambda s: base64.b64decode(s.strip() + "=" * (-len(s.strip()) % 4)).decode("utf-8", "replace")),
    "urlencode": ("URL-encode the clipboard", lambda s: urllib.parse.quote(s, safe="")),
    "urldecode": ("URL-decode the clipboard", urllib.parse.unquote),
    "json": ("Pretty-print JSON in clipboard", _pretty_json),
    "count": ("Count characters / words / lines", lambda s: f"{len(s)} chars, {len(s.split())} words, {len(s.splitlines())} lines"),
}


def run_text_tool(name, text):
    try:
        return TEXT_TOOLS[name][1](text)
    except Exception as e:
        return f"Could not apply {name}: {e}"


class AppIndex:
    """Start Menu shortcuts, indexed once on a background thread."""

    def __init__(self):
        self.apps = []   # (lowercase name, display name, path)
        self.ready = False

    def start(self):
        threading.Thread(target=self._scan, name="app-index", daemon=True).start()

    def _scan(self):
        roots = []
        if sys.platform == "win32":
            roots = [os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), r"Microsoft\Windows\Start Menu\Programs"),
                     os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
                     os.path.join(os.environ.get("USERPROFILE", ""), "Desktop")]
        found = {}
        for root in roots:
            for dirpath, _dirs, files in os.walk(root):
                for f in files:
                    name, ext = os.path.splitext(f)
                    if ext.lower() in (".lnk", ".url", ".appref-ms") and "uninstall" not in name.lower():
                        found.setdefault(name.lower(), (name.lower(), name, os.path.join(dirpath, f)))
        self.apps = sorted(found.values())
        self.ready = True

    def search(self, query, limit=6):
        q = query.strip().lower()
        if not q:
            return []
        scored = []
        for low, name, path in self.apps:
            if low.startswith(q):
                rank = 0
            elif any(w.startswith(q) for w in low.split()):
                rank = 1
            elif q in low:
                rank = 2
            else:
                continue
            scored.append((rank, len(low), name, path))
        return [(name, path) for _r, _l, name, path in sorted(scored)[:limit]]
