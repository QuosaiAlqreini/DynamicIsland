"""Called by Codex (`notify` in ~/.codex/config.toml) when a turn completes.

Usage: codex_notify.py <port> <token> <json-payload>
Forwards the payload to the Dynamic Island on this PC. Never fails loudly.
"""
import sys
import urllib.request


def main():
    if len(sys.argv) < 4:
        return
    port, token, payload = sys.argv[1], sys.argv[2], sys.argv[-1]
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{int(port)}/codex", data=payload.encode("utf-8"),
                                     headers={"Content-Type": "application/json", "X-Island-Token": token})
        urllib.request.urlopen(req, timeout=3).read()
    except Exception:
        pass


if __name__ == "__main__":
    main()
