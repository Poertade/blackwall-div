"""As cores e as fontes (as do projeto-netrunner: Rajdhani e IBM Plex Mono)."""

import pygame

from blackwall.paths import ASSETS

W, H = 1280, 720            # a tela lógica (a janela escala mantendo a proporção)
ARENA_X, ARENA_Y = 20, 64   # onde a arena do mergulho começa na tela

BG = (6, 7, 10)
PANEL = (12, 14, 22)
PANEL_2 = (18, 21, 32)
LINE = (40, 46, 66)
TEXT = (226, 232, 245)
DIM = (130, 138, 160)
FAINT = (70, 76, 96)

COLORS = {
    "cyan": (94, 246, 255),
    "red": (255, 95, 87),
    "yellow": (252, 238, 10),
    "violet": (180, 140, 255),
    "green": (90, 255, 150),
    "orange": (255, 150, 60),
    "pink": (255, 80, 190),
    "white": (230, 240, 255),
    "blue": (90, 150, 255),
}
YELLOW = COLORS["yellow"]
CYAN = COLORS["cyan"]
RED = COLORS["red"]

TAG_COLORS = {"contagio": COLORS["green"], "sobrecarga": COLORS["orange"], "cadeia": COLORS["cyan"],
              "controle": COLORS["violet"]}
RARITY_COLORS = {"comum": (170, 180, 200), "raro": COLORS["cyan"], "epico": COLORS["yellow"]}
RARITY_NAMES = {"comum": "COMUM", "raro": "RARO", "epico": "ÉPICO"}
KIND_NAMES = {"combate": "combate", "controle": "controle", "furtivo": "furtivo", "supremo": "supremo"}


def color(name) -> tuple:
    if isinstance(name, tuple):
        return name
    return COLORS.get(name, COLORS["white"])


def mix(a, b, t) -> tuple:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def scale(c, k) -> tuple:
    return tuple(max(0, min(255, int(v * k))) for v in c)


_FONTS = {}
_FILES = {
    "title": "Rajdhani-Bold.ttf",
    "ui": "Rajdhani-Medium.ttf",
    "bold": "Rajdhani-Bold.ttf",
    "mono": "IBMPlexMono-Regular.ttf",
    "mono_bold": "IBMPlexMono-Bold.ttf",
}


def reset_fonts():
    """Esquece as fontes carregadas (depois de um pygame.quit elas não valem mais)."""
    _FONTS.clear()


def font(size: int, kind: str = "ui") -> pygame.font.Font:
    key = (kind, size)
    if key not in _FONTS:
        path = ASSETS / "fonts" / _FILES[kind]
        try:
            _FONTS[key] = pygame.font.Font(str(path), size)
        except (OSError, FileNotFoundError):
            _FONTS[key] = pygame.font.Font(None, size)
    return _FONTS[key]
