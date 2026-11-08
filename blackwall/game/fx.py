"""Os efeitos: partículas, números de dano, arcos elétricos, anéis, explosões e o tremor da tela.

Lê os eventos do mergulho (Dive.take_events) e devolve os sons a tocar."""

import math
import random

import pygame

from blackwall.game import gfx
from blackwall.game import theme as T

SOUNDS = {
    "cast": "cast", "landed": None, "hit": "hit", "kill": "kill", "hurt": "hurt", "pickup": "pickup",
    "wave": "wave", "wave_clear": "clear", "denied": "denied", "drained": "drained", "boss": "boss",
    "blast": "blast", "up": "up", "flatline": "flatline", "boss_down": "victory", "chain": "zap",
    "execute": "execute", "reset": "execute", "rebuild": "boss", "paralyzed": "drained",
}


class FX:
    def __init__(self, seed=3):
        self.rng = random.Random(seed)
        self.particles = []
        self.texts = []
        self.arcs = []
        self.rings = []
        self.bolts = []
        self.shake = 0.0
        self.hurt_flash = 0.0
        self.drain_flash = 0.0
        self.banner = None          # (texto, cor, segundos, total)
        self.denied = {}            # slot -> segundos piscando
        self.ed_pulse = 0.0
        self.shake_enabled = True

    # --- eventos -------------------------------------------------------------
    def handle(self, events, dive, content) -> list:
        sounds = []
        hits = 0
        for ev in events:
            kind = ev[0]
            name = SOUNDS.get(kind)
            if kind == "hit":
                _, x, y, dmg, crit, col, heavy = ev
                c = T.YELLOW if crit else T.color(col)
                size = 22 if crit else (18 if heavy else 15)
                self.texts.append([x + self.rng.uniform(-6, 6), y, -50, 0.7, gfx.fmt(max(1, dmg)) + ("!" if crit else ""),
                                   c, size])
                self._burst(x, y + 6, c, 5 if not heavy else 12, 120)
                hits += 1
                if heavy:
                    self.shake = max(self.shake, 4)
                if hits > 3:
                    name = None
            elif kind == "dot":
                _, x, y, amount = ev
                self.texts.append([x + self.rng.uniform(-8, 8), y, -30, 0.6, gfx.fmt(max(1, amount)),
                                   T.scale(T.COLORS["green"], 0.9), 13])
            elif kind == "kill":
                _, x, y, col, radius, boss = ev
                c = T.color(col)
                self._burst(x, y, c, 40 if boss else 14, 260 if boss else 160, size=3 if boss else 2)
                self.rings.append([x, y, radius, radius * 2.2, 0.35, 0.35, c])
                if boss:
                    self.shake = max(self.shake, 16)
            elif kind == "dissolve":
                _, x, y, col, radius = ev
                self._burst(x, y, T.color(col), 6, 60)
            elif kind == "chain":
                _, points, col = ev
                self.arcs.append([points, T.color(col), 0.18])
            elif kind == "link":
                _, x0, y0, x1, y1, col = ev
                self.arcs.append([[(x0, y0), (x1, y1)], T.color(col), 0.25])
            elif kind == "bolt_from":
                _, x0, y0, x1, y1, col = ev
                self.bolts.append([x0, y0, x1, y1, T.color(col), 0.2])
            elif kind == "bolt":
                _, x, y, col = ev
                self.bolts.append([x, y - 160, x, y, T.color(col), 0.18])
                self._burst(x, y, T.color(col), 10, 180)
            elif kind == "ring":
                _, x, y, radius, col = ev
                self.rings.append([x, y, radius * 0.3, radius, 0.4, 0.4, T.color(col)])
            elif kind == "blast":
                _, x, y, radius, col = ev
                c = T.color(col)
                self.rings.append([x, y, 10, radius, 0.45, 0.45, c])
                self.rings.append([x, y, 5, radius * 0.7, 0.3, 0.3, T.YELLOW])
                self._burst(x, y, c, 40, 340, size=3)
            elif kind == "shake":
                self.shake = max(self.shake, ev[1])
            elif kind in ("reset", "execute"):
                _, x, y = ev
                self.texts.append([x, y - 20, -40, 0.9, "RESET" if kind == "reset" else "EXECUTADO", T.COLORS["white"], 16])
                self._burst(x, y, T.COLORS["white"], 18, 200)
            elif kind == "immune":
                _, x, y = ev
                self.texts.append([x, y - 30, -30, 0.9, "IMUNE", T.DIM, 16])
            elif kind == "fizzle":
                _, x, y = ev
                self.texts.append([x, y - 10, -20, 0.5, "perdido", T.DIM, 13])
            elif kind == "hurt":
                self.hurt_flash = 0.35
                self.shake = max(self.shake, 7)
            elif kind == "drained":
                self.drain_flash = 0.6
                self.banner = ("RAM ROUBADA", T.COLORS["blue"], 1.2, 1.2)
            elif kind == "paralyzed":
                self.banner = ("PARALISADA", T.YELLOW, 0.8, 0.8)
            elif kind == "denied":
                self.denied[ev[1]] = 0.35
            elif kind == "pickup":
                self.ed_pulse = 0.25
                name = "pickup" if self.rng.random() < 0.5 else None
            elif kind == "wave":
                _, n, boss = ev
                if boss:
                    b = content.bosses[boss]
                    self.banner = (b["name"].upper(), T.RED, 2.6, 2.6)
                else:
                    self.banner = (f"ONDA {n}", T.CYAN, 1.6, 1.6)
            elif kind == "boss_down":
                self.banner = ("CHEFE DERRUBADO", T.YELLOW, 2.5, 2.5)
            elif kind == "rebuild":
                _, x, y = ev
                self.banner = ("ELE ESTÁ SE RECONSTRUINDO", T.COLORS["green"], 2.0, 2.0)
            elif kind == "lone_wolf":
                self.banner = (f"LOBO SOLITÁRIO +{int(ev[1] * 100)}%", T.YELLOW, 1.5, 1.5)
            elif kind == "dash":
                _, x0, y0, x1, y1 = ev
                self.bolts.append([x0, y0, x1, y1, T.YELLOW, 0.18])
                name = "zap"
            elif kind == "blink":
                _, x0, y0, x1, y1, radius = ev
                self.rings.append([x0, y0, 30, 4, 0.3, 0.3, T.COLORS["violet"]])
                self.rings.append([x1, y1, 10, radius, 0.35, 0.35, T.COLORS["violet"]])
                self._burst(x1, y1, T.COLORS["violet"], 16, 220)
                name = "blast"
            elif kind == "ally_heal":
                _, x0, y0, x1, y1, col = ev
                self.arcs.append([[(x0, y0), (x1, y1)], T.color(col), 0.2])
                self.texts.append([x1, y1 - 24, -30, 0.8, "+INTEGRIDADE", T.COLORS["green"], 13])
            elif kind == "objective":
                self.banner = (ev[1], T.RED, 2.0, 2.0)
            elif kind == "node_down":
                self.banner = ("O NÓ CAIU", T.RED, 2.5, 2.5)
                name = "flatline"
            elif kind == "mission_done":
                self.banner = ("MISSÃO CUMPRIDA", T.YELLOW, 2.5, 2.5)
                name = "victory"
            elif kind == "summon":
                _, x, y = ev
                self.rings.append([x, y, 20, 90, 0.4, 0.4, T.RED])
            if name:
                sounds.append(name)
        return sounds

    def _burst(self, x, y, col, n, speed, size=2):
        for _ in range(n):
            a = self.rng.random() * math.tau
            s = self.rng.uniform(0.3, 1.0) * speed
            life = self.rng.uniform(0.25, 0.6)
            self.particles.append([x, y, math.cos(a) * s, math.sin(a) * s, life, life, col, size])
        if len(self.particles) > 1500:
            del self.particles[:300]

    def trail(self, x, y, col):
        a = self.rng.random() * math.tau
        self.particles.append([x, y, math.cos(a) * 20, math.sin(a) * 20, 0.4, 0.4, col, 2])

    # --- tempo e desenho -----------------------------------------------------
    def update(self, dt):
        for p in self.particles:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[2] *= 0.92
            p[3] *= 0.92
            p[4] -= dt
        self.particles = [p for p in self.particles if p[4] > 0]
        for t in self.texts:
            t[1] += t[2] * dt
            t[2] *= 0.94
            t[3] -= dt
        self.texts = [t for t in self.texts if t[3] > 0]
        for a in self.arcs:
            a[2] -= dt
        self.arcs = [a for a in self.arcs if a[2] > 0]
        for r in self.rings:
            r[4] -= dt
        self.rings = [r for r in self.rings if r[4] > 0]
        for b in self.bolts:
            b[5] -= dt
        self.bolts = [b for b in self.bolts if b[5] > 0]
        self.shake = max(0.0, self.shake - dt * 40)
        self.hurt_flash = max(0.0, self.hurt_flash - dt)
        self.drain_flash = max(0.0, self.drain_flash - dt)
        self.ed_pulse = max(0.0, self.ed_pulse - dt)
        for k in list(self.denied):
            self.denied[k] -= dt
            if self.denied[k] <= 0:
                del self.denied[k]
        if self.banner:
            text, col, t, total = self.banner
            t -= dt
            self.banner = (text, col, t, total) if t > 0 else None

    def offset(self):
        if not self.shake_enabled or self.shake <= 0:
            return 0, 0
        return self.rng.uniform(-self.shake, self.shake), self.rng.uniform(-self.shake, self.shake)

    def _jagged(self, a, b, ox, oy):
        (x0, y0), (x1, y1) = a, b
        pts = [(x0 + ox, y0 + oy)]
        n = max(2, int(math.hypot(x1 - x0, y1 - y0) / 18))
        for i in range(1, n):
            t = i / n
            pts.append((x0 + (x1 - x0) * t + ox + self.rng.uniform(-7, 7),
                        y0 + (y1 - y0) * t + oy + self.rng.uniform(-7, 7)))
        pts.append((x1 + ox, y1 + oy))
        return pts

    def draw_world(self, surf, glow, ox, oy):
        for r in self.rings:
            x, y, r0, r1, t, total, col = r
            k = 1 - t / total
            radius = r0 + (r1 - r0) * k
            c = T.scale(col, 1 - k * 0.7)
            gfx.circle(surf, glow, c, (int(x + ox), int(y + oy)), radius, 2)
        for points, col, t in self.arcs:
            for i in range(len(points) - 1):
                pts = self._jagged(points[i], points[i + 1], ox, oy)
                gfx.lines(surf, glow, col, pts, 2)
                pygame.draw.lines(surf, (255, 255, 255), False, pts, 1)
        for x0, y0, x1, y1, col, t in self.bolts:
            pts = self._jagged((x0, y0), (x1, y1), ox, oy)
            gfx.lines(surf, glow, col, pts, 3)
            pygame.draw.lines(surf, (255, 255, 255), False, pts, 1)
        for x, y, _vx, _vy, life, total, col, size in self.particles:
            c = T.scale(col, life / total)
            pygame.draw.circle(surf, c, (int(x + ox), int(y + oy)), size)
            pygame.draw.circle(glow.surface, c, (int(x + ox), int(y + oy)), size + 1)

    def draw_texts(self, surf, ox, oy):
        for x, y, _vy, life, s, col, size in self.texts:
            c = col if life > 0.25 else T.scale(col, life / 0.25)
            gfx.text(surf, s, (x + ox, y + oy), size, c, "bold", anchor="center")
