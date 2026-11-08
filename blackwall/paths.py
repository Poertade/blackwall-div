"""Onde ficam os dados do jogo e o salvamento (no código e no executável do PyInstaller)."""

import os
import sys
from pathlib import Path


def resource_root() -> Path:
    """A pasta com data/ e assets/: a do projeto, ou a do executável empacotado."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


DATA = resource_root() / "data"
ASSETS = resource_root() / "assets"


def save_dir() -> Path:
    """A pasta do salvamento: %APPDATA%/BlackwallDive no Windows, ~/.local/share/BlackwallDive no Linux."""
    override = os.environ.get("BLACKWALL_SAVE_DIR")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "BlackwallDive"
