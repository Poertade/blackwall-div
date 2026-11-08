"""Empacota o jogo num executável com o PyInstaller (sem precisar de Python instalado).

    pip install -r requirements-build.txt
    python tools/empacotar.py

Gera dist/blackwall-dive/ (o executável e o que ele precisa) e um zip pronto para copiar para outro
computador: dist/blackwall-dive-<sistema>.zip. No Windows, o jogo abre com dois cliques em
blackwall-dive.exe. O salvamento fica na pasta do usuário (%APPDATA%\\BlackwallDive no Windows).
"""

import os
import platform
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

NAME = "blackwall-dive"
BUILD = ROOT / "build"
DIST = ROOT / "dist"


def system_name() -> str:
    return {"Windows": "windows", "Darwin": "macos"}.get(platform.system(), "linux")


def make_icon() -> Path:
    """O ícone (o losango desenhado em código) salvo como PNG; o PyInstaller converte com o Pillow."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from blackwall.game.app import make_icon as draw_icon
    pygame.init()
    path = BUILD / "icone.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(pygame.transform.smoothscale(draw_icon(), (256, 256)), str(path))
    pygame.quit()
    return path


def main():
    import PyInstaller.__main__

    sep = os.pathsep
    icon = make_icon()
    args = [
        str(ROOT / "main.py"),
        "--name", NAME,
        "--noconfirm",
        "--clean",
        "--windowed",
        "--distpath", str(DIST),
        "--workpath", str(BUILD),
        "--specpath", str(BUILD),
        "--add-data", f"{ROOT / 'data'}{sep}data",
        "--add-data", f"{ROOT / 'assets'}{sep}assets",
        "--exclude-module", "tkinter",
        "--exclude-module", "pytest",
        "--exclude-module", "numpy",
        "--icon", str(icon),
    ]
    PyInstaller.__main__.run(args)
    folder = DIST / NAME
    for doc in ("README.md",):
        shutil.copy(ROOT / doc, folder / doc)
    archive = shutil.make_archive(str(DIST / f"{NAME}-{system_name()}"), "zip", DIST, NAME)
    print(f"pronto: {folder}")
    print(f"zip: {archive}")


if __name__ == "__main__":
    main()
