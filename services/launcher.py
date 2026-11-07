"""Small cross-platform helpers to open files, folders, apps and URLs."""
import os
import subprocess
import sys

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices


def resolve(target):
    return os.path.expandvars(os.path.expanduser(str(target).strip()))


def open_target(target):
    """Open an app, file, folder, URL or URI scheme (ms-settings:, https://...)."""
    target = resolve(target)
    if not target:
        return False
    try:
        if sys.platform == "win32":
            os.startfile(target)  # handles exe, lnk, folders, files, URI schemes
            return True
        if "://" in target or (":" in target and not os.path.exists(target)):
            return QDesktopServices.openUrl(QUrl(target))
        return QDesktopServices.openUrl(QUrl.fromLocalFile(target))
    except OSError as e:
        print(f"[launcher] Could not open {target}: {e}")
        return False


def reveal_in_folder(path):
    """Show a file selected in Explorer (or open its folder elsewhere)."""
    path = resolve(path)
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
            return True
        folder = path if os.path.isdir(path) else os.path.dirname(path)
        return QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
    except OSError as e:
        print(f"[launcher] Could not reveal {path}: {e}")
        return False
