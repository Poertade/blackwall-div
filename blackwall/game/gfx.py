"""O desenho em neon: formas com brilho, painéis de canto cortado, texto e o fundo do ciberespaço."""

import math

import pygame

from blackwall.game import theme as T


class Glow:
    """Uma segunda camada onde as formas brilhantes também são desenhadas.

    No fim do quadro ela é borrada em baixa resolução e somada à tela (BLEND_ADD): o brilho do neon."""

    def __init__(self, size, factor=2):
        self.size = size
        self.factor = factor
        self.surface = pygame.Surface(size)
        self.small = pygame.Surface((size[0] // factor, size[1] // factor))
        self.enabled = True

    def begin(self):
        self.surface.fill((0, 0, 0))

    def dim(self, k):
        """Escurece o que já brilhou (para os painéis por cima do mergulho)."""
        v = int(255 * k)
        self.surface.fill((v, v, v), special_flags=pygame.BLEND_MULT)

    def apply(self, target, strength=2):
        if not self.enabled:
            return
        pygame.transform.smoothscale(self.surface, self.small.get_size(), self.small)
        try:
            blurred = pygame.transform.box_blur(self.small, 4)
        except (AttributeError, ValueError):
            blurred = self.small
        big = pygame.transform.smoothscale(blurred, self.size)
        for _ in range(strength):
            target.blit(big, (0, 0), special_flags=pygame.BLEND_ADD)


# --- formas -----------------------------------------------------------------
def line(surf, glow, col, a, b, width=2, glow_width=None):
    pygame.draw.line(surf, col, a, b, width)
    if glow is not None:
        pygame.draw.line(glow.surface, col, a, b, glow_width or width + 3)


def lines(surf, glow, col, points, width=2, closed=False):
    if len(points) < 2:
        return
    pygame.draw.lines(surf, col, closed, points, width)
    if glow is not None:
        pygame.draw.lines(glow.surface, col, closed, points, width + 3)


def circle(surf, glow, col, center, radius, width=0, glow_extra=4):
    radius = max(1, int(radius))
    pygame.draw.circle(surf, col, center, radius, width)
    if glow is not None:
        pygame.draw.circle(glow.surface, col, center, radius + glow_extra // 2, width + glow_extra if width else 0)


def poly(surf, glow, col, points, width=0, fill=None):
    if fill is not None:
        pygame.draw.polygon(surf, fill, points)
    pygame.draw.polygon(surf, col, points, width)
    if glow is not None:
        pygame.draw.polygon(glow.surface, col, points, width + 3 if width else 0)


def regular(center, radius, sides, angle=0.0):
    cx, cy = center
    return [(cx + math.cos(angle + math.tau * i / sides) * radius,
             cy + math.sin(angle + math.tau * i / sides) * radius) for i in range(sides)]


def star(center, r_out, r_in, points, angle=0.0):
    cx, cy = center
    result = []
    for i in range(points * 2):
        r = r_out if i % 2 == 0 else r_in
        a = angle + math.pi * i / points
        result.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    return result


def alpha_circle(surf, col, center, radius, alpha):
    radius = max(1, int(radius))
    s = pygame.Surface((radius * 2 + 2, radius * 2 + 2), pygame.SRCALPHA)
    pygame.draw.circle(s, (*col, int(alpha)), (radius + 1, radius + 1), radius)
    surf.blit(s, (center[0] - radius - 1, center[1] - radius - 1))


def chamfer(rect, cut=10):
    """Os cantos cortados dos painéis (o jeito Cyberpunk)."""
    x, y, w, h = rect
    return [(x + cut, y), (x + w, y), (x + w, y + h - cut), (x + w - cut, y + h), (x, y + h), (x, y + cut)]


def panel(surf, rect, border=T.LINE, fill=T.PANEL, cut=10, width=1, glow=None, alpha=None):
    pts = chamfer(rect, cut)
    if alpha is not None:
        s = pygame.Surface((rect[2] + 2, rect[3] + 2), pygame.SRCALPHA)
        local = [(px - rect[0], py - rect[1]) for px, py in pts]
        pygame.draw.polygon(s, (*fill, alpha), local)
        surf.blit(s, (rect[0], rect[1]))
    else:
        pygame.draw.polygon(surf, fill, pts)
    pygame.draw.polygon(surf, border, pts, width)
    if glow is not None:
        pygame.draw.polygon(glow.surface, border, pts, width + 2)


def bar(surf, rect, frac, col, back=(30, 30, 40), glow=None):
    x, y, w, h = rect
    pygame.draw.rect(surf, back, rect)
    fw = int(w * max(0.0, min(1.0, frac)))
    if fw > 0:
        pygame.draw.rect(surf, col, (x, y, fw, h))
        if glow is not None:
            pygame.draw.rect(glow.surface, col, (x, y, fw, h))


# --- texto ------------------------------------------------------------------
def text(surf, s, pos, size=18, col=T.TEXT, kind="ui", anchor="topleft", glow=None):
    img = T.font(size, kind).render(str(s), True, col)
    rect = img.get_rect(**{anchor: pos})
    surf.blit(img, rect)
    if glow is not None:
        glow.surface.blit(T.font(size, kind).render(str(s), True, T.scale(col, 0.45)), rect)
    return rect


def wrap(s, size, width, kind="ui"):
    """Quebra o texto em linhas que cabem na largura."""
    f = T.font(size, kind)
    result = []
    for paragraph in str(s).split("\n"):
        words = paragraph.split(" ")
        current = ""
        for word in words:
            attempt = (current + " " + word).strip()
            if f.size(attempt)[0] <= width or not current:
                current = attempt
            else:
                result.append(current)
                current = word
        result.append(current)
    return result


def text_block(surf, s, pos, width, size=16, col=T.TEXT, kind="ui", spacing=2):
    x, y = pos
    line_h = T.font(size, kind).get_linesize() + spacing - 4
    for row in wrap(s, size, width, kind):
        text(surf, row, (x, y), size, col, kind)
        y += line_h
    return y


def fmt(n) -> str:
    """Números com ponto de milhar (1.234)."""
    return f"{int(n):,}".replace(",", ".")


def fmt_ram(n) -> str:
    return f"{n:.0f}" if abs(n - round(n)) < 0.05 else f"{n:.1f}".replace(".", ",")


# --- o fundo -----------------------------------------------------------------
class Background:
    """A grade do ciberespaço, com brilho leve e partículas de dado passando."""

    def __init__(self, size, col=T.CYAN, seed=1):
        self.size = size
        self.col = col
        self.t = 0.0
        import random
        rng = random.Random(seed)
        self.motes = [[rng.uniform(0, size[0]), rng.uniform(0, size[1]), rng.uniform(8, 30), rng.uniform(0.3, 1.0)]
                      for _ in range(70)]
        self.base = self._render()

    def set_color(self, col):
        if col != self.col:
            self.col = col
            self.base = self._render()

    def _render(self):
        w, h = self.size
        s = pygame.Surface(self.size)
        s.fill(T.BG)
        grid = T.scale(self.col, 0.13)
        major = T.scale(self.col, 0.24)
        for x in range(0, w, 40):
            pygame.draw.line(s, major if x % 200 == 0 else grid, (x, 0), (x, h))
        for y in range(0, h, 40):
            pygame.draw.line(s, major if y % 200 == 0 else grid, (0, y), (w, y))
        # vinheta
        v = pygame.Surface(self.size, pygame.SRCALPHA)
        for i in range(12):
            a = int(10 + i * 6)
            pygame.draw.rect(v, (0, 0, 0, a), (i * 8, i * 8, w - i * 16, h - i * 16), 8)
        s.blit(v, (0, 0))
        return s

    def update(self, dt):
        self.t += dt
        h = self.size[1]
        for m in self.motes:
            m[1] += m[2] * dt
            if m[1] > h:
                m[1] -= h

    def draw(self, surf, offset=(0, 0)):
        surf.blit(self.base, offset)
        col = T.scale(self.col, 0.5)
        for x, y, _speed, a in self.motes:
            c = T.scale(col, a)
            pygame.draw.line(surf, c, (offset[0] + x, offset[1] + y), (offset[0] + x, offset[1] + y + 6))
