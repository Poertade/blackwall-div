"""Botões e áreas clicáveis (a tela é redesenhada a cada quadro e registra o que dá para clicar)."""

import pygame

from blackwall.game import gfx
from blackwall.game import theme as T


class Clicks:
    def __init__(self):
        self.items = []

    def reset(self):
        self.items = []

    def add(self, rect, action, enabled=True, tip=None):
        self.items.append((pygame.Rect(rect), action, enabled, tip))

    def hovered(self, pos):
        for rect, action, enabled, tip in reversed(self.items):
            if rect.collidepoint(pos):
                return rect, action, enabled, tip
        return None

    def click(self, pos) -> bool:
        item = self.hovered(pos)
        if item and item[2]:
            item[1]()
            return True
        return False


def button(surf, clicks, rect, label, action, mouse, enabled=True, col=T.CYAN, size=20, glow=None, sub=None):
    rect = pygame.Rect(rect)
    hover = enabled and rect.collidepoint(mouse)
    border = col if enabled else T.FAINT
    fill = T.scale(col, 0.18) if hover else T.PANEL_2
    gfx.panel(surf, rect, border, fill, cut=8, width=2 if hover else 1, glow=glow if hover else None)
    tcol = T.TEXT if enabled else T.FAINT
    if sub:
        gfx.text(surf, label, (rect.centerx, rect.centery - 9), size, tcol, "bold", anchor="center")
        gfx.text(surf, sub, (rect.centerx, rect.centery + 12), 14, col if enabled else T.FAINT, "ui", anchor="center")
    else:
        gfx.text(surf, label, rect.center, size, tcol, "bold", anchor="center")
    clicks.add(rect, action, enabled)
    return hover


def chip(surf, pos, label, col, size=14, filled=False):
    f = T.font(size, "bold")
    w = f.size(label)[0] + 14
    rect = pygame.Rect(pos[0], pos[1], w, size + 6)
    pygame.draw.rect(surf, T.scale(col, 0.25) if filled else T.PANEL_2, rect)
    pygame.draw.rect(surf, col, rect, 1)
    gfx.text(surf, label, rect.center, size, col, "bold", anchor="center")
    return rect
