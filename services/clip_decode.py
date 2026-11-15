"""Clipboard 'chips' (as in CrestIsland): recognise a JWT, a Unix time, Base64,
JSON or a link full of tracking parameters, and offer the readable version."""
import base64
import binascii
import datetime as dt
import json
import re
import urllib.parse

TRACKING = re.compile(r"^(utm_[a-z]+|fbclid|gclid|dclid|msclkid|mc_[a-z]+|igshid|si|ref_src|ref|spm|yclid|_hs[a-z]+|mkt_tok)$", re.I)


def _b64(s):
    s = s.strip().replace("-", "+").replace("_", "/")
    return base64.b64decode(s + "=" * (-len(s) % 4), validate=True)


def decode(text):
    """(label, readable text) for something recognisable on the clipboard, else None."""
    t = (text or "").strip()
    if not t or len(t) > 20000:
        return None
    # JWT: header.payload.signature
    if re.fullmatch(r"[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]*", t):
        try:
            header = json.loads(_b64(t.split(".")[0]))
            payload = json.loads(_b64(t.split(".")[1]))
            out = json.dumps({"header": header, "payload": payload}, indent=2, ensure_ascii=False)
            exp = payload.get("exp")
            if isinstance(exp, (int, float)):
                when = dt.datetime.fromtimestamp(exp)
                state = "expired" if when < dt.datetime.now() else "valid until"
                return f"JWT ({state} {when:%Y-%m-%d %H:%M})", out
            return "JWT", out
        except (ValueError, binascii.Error):
            pass
    # Unix time (seconds or milliseconds) in a sensible range
    if re.fullmatch(r"\d{10}|\d{13}", t):
        value = int(t) / (1000 if len(t) == 13 else 1)
        if 946684800 <= value <= 4102444800:
            when = dt.datetime.fromtimestamp(value)
            return "Unix time", when.strftime("%Y-%m-%d %H:%M:%S (local)")
    # JSON: pretty-print
    if t[:1] in "{[":
        try:
            return "JSON", json.dumps(json.loads(t), indent=2, ensure_ascii=False)
        except ValueError:
            pass
    # Link with tracking parameters: clean copy
    if re.match(r"https?://", t) and "?" in t:
        parts = urllib.parse.urlsplit(t)
        query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
        kept = [(k, v) for k, v in query if not TRACKING.match(k)]
        if len(kept) < len(query):
            clean = urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(kept)))
            return f"Link without {len(query) - len(kept)} tracker(s)", clean
    # Base64 that decodes to readable text
    if len(t) >= 12 and re.fullmatch(r"[A-Za-z0-9+/=_-]+", t) and not t.isdigit():
        try:
            raw = _b64(t).decode("utf-8")
            if raw.isprintable() or all(ch.isprintable() or ch in "\n\r\t" for ch in raw):
                return "Base64", raw
        except (ValueError, binascii.Error, UnicodeDecodeError):
            pass
    return None
