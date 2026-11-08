"""A tela do mergulho: a arena, os ICE, os hacks, o HUD, a escolha dos ups e o fim."""

import math

import pygame

from blackwall.game import gfx, ui
from blackwall.game import theme as T
from blackwall.game.fx import FX
from blackwall.meta import profile as pf
from blackwall.sim import build
from blackwall.sim.dive import Dive, DiveInput

STEP = 1 / 60
KEYS = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5, pygame.K_6]
KEYPAD = [pygame.K_KP1, pygame.K_KP2, pygame.K_KP3, pygame.K_KP4, pygame.K_KP5, pygame.K_KP6]
RESULTS = {
    "failed": ("MISSÃO FALHOU", T.RED),
    "victory": ("CAMADA VENCIDA", T.YELLOW),
    "flatline": ("FLATLINE", T.RED),
    "extracted": ("DESCONECTADA", T.CYAN),
    "aborted": ("CONEXÃO CORTADA", T.RED),
}
EFFECT_COLORS = {"poison": "green", "burn": "orange", "stun": "yellow", "root": "violet", "blind": "violet",
                 "marked": "white", "confused": "pink", "berserk": "red", "weaken": "blue", "slow": "blue"}


class DiveScene:
    def __init__(self, app, config, title: str):
        self.app = app
        self.c = app.content
        self.dive = Dive(self.c, config)
        self.title = title
        self.fx = FX()
        self.fx.shake_enabled = app.profile.settings.get("shake", True)
        layer = self.c.layers[self.dive.plan.layer]
        self.bg = gfx.Background((self.dive.W, self.dive.H), T.color(layer["color"]))
        self.ox, self.oy = T.ARENA_X, T.ARENA_Y
        self.acc = 0.0
        self.paused = False
        self.show_build = False
        self.moving = False
        self.queue = []
        self.summary = None
        self.clicks = ui.Clicks()
        self.t = 0.0
        self.trail_t = 0.0
        pygame.mouse.set_visible(False)

    # --- entrada -------------------------------------------------------------
    def arena_mouse(self):
        mx, my = self.app.mouse()
        return mx - self.ox, my - self.oy

    def handle(self, event):
        d = self.dive
        if event.type == pygame.KEYDOWN:
            key = event.key
            if d.phase == "over":
                if key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
                    self.leave()
                return
            if self.paused:
                if key == pygame.K_ESCAPE:
                    self.paused = False
                return
            if key == pygame.K_ESCAPE:
                self.paused = True
                self.moving = False
                return
            if key == pygame.K_TAB:
                self.show_build = not self.show_build
                return
            index = KEYS.index(key) if key in KEYS else (KEYPAD.index(key) if key in KEYPAD else None)
            if d.phase == "wave" and index is not None:
                self.queue.append(index)
            elif d.phase == "choice":
                if index is not None and index < len(d.offer):
                    self.pick(index)
                elif key == pygame.K_r:
                    self.reroll()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.paused or d.phase != "wave":
                if self.clicks.click(self.app.logical(event.pos)):
                    self.app.audio.play("click")
            else:
                self.moving = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.moving = False
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3 and d.phase == "wave" and not self.paused:
            self.queue.append(0)

    def pick(self, index):
        self.dive.choose(index)
        self.moving = False
        self.app.audio.play("up")

    def reroll(self):
        if self.dive.reroll():
            self.app.audio.play("click")
        else:
            self.app.audio.play("denied")

    def leave(self):
        self.finish()
        pygame.mouse.set_visible(True)
        from blackwall.game.scene_hideout import HideoutScene
        s = self.summary or {}
        story_news = s.get("ending") or s.get("reward_ally") or s.get("mission") or (
            self.dive.cfg.mode == "layer" and s.get("result") == "victory" and self.app.profile.layers_cleared == 1)
        self.app.switch(HideoutScene(self.app, last=self.summary, tab="historia" if story_news else "mergulho"))

    def finish(self):
        if self.summary is None:
            self.summary = pf.apply_result(self.app.profile, self.c, self.dive)
            self.app.save()

    # --- tempo ---------------------------------------------------------------
    def update(self, dt):
        self.t += dt
        d = self.dive
        self.fx.update(dt)
        self.bg.update(dt)
        pygame.mouse.set_visible(self.paused or d.phase != "wave")
        if self.paused or d.phase != "wave":
            self.acc = 0.0
            if d.phase == "over" and self.summary is None:
                self.finish()
            return
        if not pygame.mouse.get_pressed()[0]:
            self.moving = False
        self.acc = min(self.acc + dt, 0.1)
        while self.acc >= STEP and d.phase == "wave":
            aim = self.arena_mouse()
            inp = DiveInput(move=aim if self.moving else None, aim=aim, cast=tuple(self.queue))
            self.queue.clear()
            d.step(STEP, inp)
            self.acc -= STEP
        for name in self.fx.handle(d.take_events(), d, self.c):
            self.app.audio.play(name, self.t)
        p = d.player
        if p.moving:
            self.trail_t += dt
            if self.trail_t > 0.03:
                self.trail_t = 0
                self.fx.trail(p.x, p.y, T.CYAN)
        if d.phase == "over":
            self.finish()

    # --- desenho -------------------------------------------------------------
    def draw(self, surf, glow):
        d = self.dive
        self.clicks.reset()
        sx, sy = self.fx.offset()
        ox, oy = self.ox + sx, self.oy + sy
        surf.fill(T.BG)
        self.bg.draw(surf, (ox, oy))
        pygame.draw.rect(surf, T.scale(self.bg.col, 0.5), (ox - 1, oy - 1, d.W + 2, d.H + 2), 1)
        self.draw_zones(surf, ox, oy)
        self.draw_spawns(surf, glow, ox, oy)
        self.draw_pickups(surf, glow, ox, oy)
        self.draw_uploads(surf, glow, ox, oy)
        self.draw_objective(surf, glow, ox, oy)
        for e in d.enemies:
            self.draw_enemy(surf, glow, e, ox, oy)
        self.draw_allies(surf, glow, ox, oy)
        self.draw_player(surf, glow, ox, oy)
        for b in d.bullets:
            c = T.color(b.color)
            gfx.circle(surf, glow, c, (int(b.x + ox), int(b.y + oy)), b.radius)
            pygame.draw.circle(surf, (255, 255, 255), (int(b.x + ox), int(b.y + oy)), max(1, int(b.radius) - 3))
        self.fx.draw_world(surf, glow, ox, oy)
        self.fx.draw_texts(surf, ox, oy)
        if self.fx.hurt_flash > 0:
            v = pygame.Surface((T.W, T.H), pygame.SRCALPHA)
            a = int(110 * self.fx.hurt_flash / 0.35)
            pygame.draw.rect(v, (255, 40, 40, a), (0, 0, T.W, T.H), 18)
            surf.blit(v, (0, 0))
        self.draw_hud(surf, glow)
        if d.phase == "wave" and not self.paused:
            self.draw_cursor(surf, glow)
        if self.show_build and d.phase == "wave":
            self.draw_build(surf, glow, (T.W - 470, 70))
        if d.phase == "choice":
            self.draw_choice(surf, glow)
        elif d.phase == "over":
            self.draw_over(surf, glow)
        elif self.paused:
            self.draw_pause(surf, glow)

    def draw_zones(self, surf, ox, oy):
        for z in self.dive.zones:
            a = 70 * min(1.0, z.life / 0.6)
            col = (60, 220, 120) if z.kind == "trail" else (110, 255, 120)
            gfx.alpha_circle(surf, col, (z.x + ox, z.y + oy), z.radius, a * (0.6 if z.kind == "trail" else 1))
            if z.kind == "puddle":
                pygame.draw.circle(surf, (90, 200, 110), (int(z.x + ox), int(z.y + oy)), int(z.radius), 1)

    def draw_spawns(self, surf, glow, ox, oy):
        for s in self.dive.spawns:
            k = s.t / s.total
            col = T.RED if not s.boss else T.YELLOW
            r = (1 - k) * (60 if s.boss else 22) + 6
            x, y = int(s.x + ox), int(s.y + oy)
            if int(self.t * 12) % 2 == 0 or s.boss:
                gfx.line(surf, glow, col, (x - 7, y - 7), (x + 7, y + 7), 2)
                gfx.line(surf, glow, col, (x - 7, y + 7), (x + 7, y - 7), 2)
            pygame.draw.circle(surf, col, (x, y), int(r), 1)

    def draw_pickups(self, surf, glow, ox, oy):
        for pk in self.dive.pickups:
            x, y = pk.x + ox, pk.y + oy
            r = 4 + min(4, pk.value / 6)
            a = self.t * 4 + pk.x
            pts = [(x + math.cos(a + i * math.pi / 2) * r, y + math.sin(a + i * math.pi / 2) * r) for i in range(4)]
            gfx.poly(surf, glow, T.YELLOW, pts)

    def draw_uploads(self, surf, glow, ox, oy):
        p = self.dive.player
        for u in self.dive.uploads:
            h = self.c.hacks[u.hack]
            col = T.color(h["color"])
            k = u.t / u.total
            x0, y0 = p.x + ox, p.y + oy
            x1, y1 = u.point[0] + ox, u.point[1] + oy
            n = 14
            for i in range(n):
                if i % 2:
                    continue
                a, b = i / n, (i + 1) / n
                pygame.draw.line(surf, T.scale(col, 0.6), (x0 + (x1 - x0) * a, y0 + (y1 - y0) * a),
                                 (x0 + (x1 - x0) * b, y0 + (y1 - y0) * b), 1)
            px, py = x0 + (x1 - x0) * k, y0 + (y1 - y0) * k
            gfx.circle(surf, glow, col, (int(px), int(py)), 4)
            rad = 20
            rect = pygame.Rect(x1 - rad, y1 - rad, rad * 2, rad * 2)
            pygame.draw.arc(surf, col, rect, math.pi / 2, math.pi / 2 + math.tau * k, 3)
            pygame.draw.arc(glow.surface, col, rect, math.pi / 2, math.pi / 2 + math.tau * k, 5)

    def draw_objective(self, surf, glow, ox, oy):
        node = self.dive.node
        if node is None:
            return
        x, y = node.x + ox, node.y + oy
        col = T.COLORS["green"] if node.hp > node.max_hp * 0.35 else T.RED
        if node.moving:
            pts = [(x + 26, y), (x - 14, y - 18), (x - 6, y), (x - 14, y + 18)]
            gfx.poly(surf, glow, col, pts, 2, fill=T.scale(col, 0.2))
            label = "PROGRAMA"
        else:
            gfx.poly(surf, glow, col, gfx.regular((x, y), node.radius, 6, self.t * 0.4), 2, fill=T.scale(col, 0.2))
            k = self.dive.mission_progress()
            rect = pygame.Rect(x - 34, y - 34, 68, 68)
            pygame.draw.arc(surf, T.CYAN, rect, math.pi / 2, math.pi / 2 + math.tau * k, 3)
            pygame.draw.arc(glow.surface, T.CYAN, rect, math.pi / 2, math.pi / 2 + math.tau * k, 5)
            label = f"DOWNLOAD {int(k * 100)}%"
        gfx.bar(surf, (x - 30, y - 50, 60, 5), node.hp / node.max_hp, col, back=(40, 20, 25))
        gfx.text(surf, label, (x, y + 30), 13, col, "bold", anchor="midtop")

    def draw_allies(self, surf, glow, ox, oy):
        for a in self.dive.allies:
            x, y = a.x + ox, a.y + oy
            col = T.color(a.d["color"])
            gfx.poly(surf, glow, col, gfx.regular((x, y), 9, 4, self.t * 2 + a.slot), 2, fill=T.scale(col, 0.25))
            gfx.text(surf, a.d["name"].replace('"', "").split()[0][0], (x, y - 1), 12, T.TEXT, "bold", anchor="center")
            if a.flash > 0:
                pygame.draw.circle(surf, col, (int(x), int(y)), int(14 + (0.3 - a.flash) * 40), 1)

    def draw_player(self, surf, glow, ox, oy):
        d = self.dive
        p = d.player
        x, y = p.x + ox, p.y + oy
        if p.invulnerable > 0 and int(self.t * 20) % 2 == 0:
            return
        r = d.stats.radius
        col = T.CYAN
        a = self.t * 2
        gfx.circle(surf, glow, T.scale(col, 0.5), (int(x), int(y)), r + 7, 1)
        for i in range(3):
            ang = a + i * math.tau / 3
            pygame.draw.arc(surf, col, (x - r - 7, y - r - 7, (r + 7) * 2, (r + 7) * 2), ang, ang + 0.6, 2)
        pts = gfx.regular((x, y), r, 4, p.facing)
        gfx.poly(surf, glow, col, pts, 2, fill=(10, 40, 50))
        tip = (x + math.cos(p.facing) * (r + 4), y + math.sin(p.facing) * (r + 4))
        gfx.circle(surf, glow, T.YELLOW, (int(tip[0]), int(tip[1])), 3)
        gfx.circle(surf, glow, (255, 255, 255), (int(x), int(y)), 4)
        if p.rooted > 0:
            gfx.circle(surf, glow, T.YELLOW, (int(x), int(y)), r + 12, 2)
        if d.auto == "controle":
            radius = self.c.builds["controle"]["auto"]["radius"]
            gfx.alpha_circle(surf, T.COLORS["violet"], (x, y), radius, 18)
            pygame.draw.circle(surf, T.scale(T.COLORS["violet"], 0.5), (int(x), int(y)), radius, 1)
        pr = d.stats.pickup
        pygame.draw.circle(surf, T.scale(T.YELLOW, 0.12), (int(x), int(y)), int(pr), 1)

    def draw_enemy(self, surf, glow, e, ox, oy):
        x, y = e.x + ox, e.y + oy
        col = T.color(e.d["color"])
        if e.flash > 0:
            col = (255, 255, 255)
        if "confused" in e.fx or "berserk" in e.fx:
            col = T.mix(col, T.COLORS["pink"], 0.6)
        r = e.radius
        shape = e.d["shape"]
        ang = e.angle
        fill = T.scale(col, 0.18)
        if e.invulnerable:
            col = T.scale(col, 0.4 + 0.3 * math.sin(self.t * 10))
        if shape == "triangle":
            gfx.poly(surf, glow, col, gfx.regular((x, y), r, 3, ang), 2, fill)
        elif shape == "arrow":
            pts = [(x + math.cos(ang) * r * 1.4, y + math.sin(ang) * r * 1.4),
                   (x + math.cos(ang + 2.5) * r, y + math.sin(ang + 2.5) * r),
                   (x + math.cos(ang + math.pi) * r * 0.3, y + math.sin(ang + math.pi) * r * 0.3),
                   (x + math.cos(ang - 2.5) * r, y + math.sin(ang - 2.5) * r)]
            gfx.poly(surf, glow, col, pts, 2, fill)
        elif shape == "diamond":
            gfx.poly(surf, glow, col, gfx.regular((x, y), r * 1.2, 4, self.t), 2, fill)
        elif shape == "square":
            gfx.poly(surf, glow, col, gfx.regular((x, y), r * 1.25, 4, ang + math.pi / 4), 2, fill)
            pygame.draw.circle(surf, col, (int(x), int(y)), int(r * 0.35), 2)
        elif shape == "hex":
            gfx.poly(surf, glow, col, gfx.regular((x, y), r, 6, self.t * 0.5), 2, fill)
        elif shape == "star":
            gfx.poly(surf, glow, col, gfx.star((x, y), r * 1.3, r * 0.55, 4, ang), 2, fill)
        elif shape == "node":
            gfx.poly(surf, glow, col, gfx.regular((x, y), r * 1.3, 4, math.pi / 4), 2, fill)
            pygame.draw.arc(surf, col, (x - r - 8, y - r - 8, (r + 8) * 2, (r + 8) * 2), -self.t * 2, -self.t * 2 + 3, 2)
            gfx.circle(surf, glow, col, (int(x), int(y)), 4 + 2 * math.sin(self.t * 5))
        elif shape == "ring":
            gfx.circle(surf, glow, col, (int(x), int(y)), r, 2)
            gfx.circle(surf, glow, col, (int(x), int(y)), r * 0.4)
            pygame.draw.arc(surf, col, (x - r - 6, y - r - 6, (r + 6) * 2, (r + 6) * 2), self.t * 3, self.t * 3 + 2, 2)
        else:
            self.draw_boss_shape(surf, glow, e, x, y, col, fill)
        # avisos de ataque
        if e.state == "windup":
            dx, dy = e.dir
            if int(self.t * 16) % 2 == 0:
                gfx.line(surf, glow, T.RED, (x, y), (x + dx * 320, y + dy * 320), 2)
        if e.state == "upload" or (e.boss and "drain" in e.mem):
            p = self.dive.player
            c = T.COLORS["blue"]
            gfx.line(surf, glow, c, (x, y), (p.x + ox, p.y + oy), 1 + int(self.t * 8) % 2)
            gfx.text(surf, "HACKEANDO", (x, y - r - 22), 13, c, "bold", anchor="center")
        # efeitos
        k = 0
        for name in ("poison", "burn", "stun", "root", "blind", "marked", "confused", "berserk", "weaken"):
            if name in e.fx:
                c = T.color(EFFECT_COLORS[name])
                if name == "marked":
                    s = r + 7
                    for qx, qy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                        pygame.draw.line(surf, c, (x + qx * s, y + qy * s), (x + qx * (s - 5), y + qy * s), 2)
                        pygame.draw.line(surf, c, (x + qx * s, y + qy * s), (x + qx * s, y + qy * (s - 5)), 2)
                elif name == "stun":
                    for i in range(3):
                        a = self.t * 6 + i * math.tau / 3
                        pygame.draw.circle(surf, c, (int(x + math.cos(a) * (r + 5)), int(y - r - 6 + math.sin(a) * 3)), 2)
                else:
                    pygame.draw.circle(surf, c, (int(x - r + k * 7), int(y + r + 6)), 3)
                    k += 1
        if not e.boss and e.hp < e.max_hp:
            w = r * 2 + 6
            gfx.bar(surf, (x - w / 2, y - r - 9, w, 3), e.hp / e.max_hp, col, back=(40, 20, 25))

    def draw_boss_shape(self, surf, glow, e, x, y, col, fill):
        r = e.radius
        t = self.t
        shape = e.d["shape"]
        if shape == "kraken":
            for i in range(8):
                a = i * math.tau / 8 + math.sin(t + i) * 0.2
                pts = []
                for k in range(6):
                    rr = r + k * 9
                    aa = a + math.sin(t * 2 + k * 0.7 + i) * 0.25
                    pts.append((x + math.cos(aa) * rr, y + math.sin(aa) * rr))
                gfx.lines(surf, glow, col, pts, 2)
            gfx.circle(surf, glow, col, (int(x), int(y)), r, 3)
            pygame.draw.circle(surf, fill, (int(x), int(y)), r - 3)
            gfx.circle(surf, glow, T.YELLOW, (int(x), int(y)), r * 0.25)
        elif shape == "agent":
            gfx.poly(surf, glow, col, gfx.regular((x, y), r, 6, t * 0.3), 3, fill)
            gfx.poly(surf, glow, col, gfx.regular((x, y), r * 0.6, 6, -t * 0.6), 2)
            gfx.circle(surf, glow, (255, 255, 255), (int(x), int(y)), 6)
        elif shape == "liche":
            gfx.poly(surf, glow, col, gfx.regular((x, y), r, 3, -math.pi / 2), 3, fill)
            for dx in (-0.35, 0.35):
                gfx.circle(surf, glow, col, (int(x + r * dx), int(y - r * 0.1)), r * 0.16, 2)
            for i in range(5):
                a = t + i * math.tau / 5
                gfx.circle(surf, glow, col, (int(x + math.cos(a) * (r + 16)), int(y + math.sin(a) * (r + 16))), 4)
        elif shape == "giant":
            gfx.poly(surf, glow, col, gfx.regular((x, y), r, 8, math.pi / 8), 4, fill)
            gfx.poly(surf, glow, col, gfx.regular((x, y), r * 0.55, 4, t * 0.4), 2)
        else:  # a IA renegada
            for i, k in enumerate((1.0, 0.75, 0.5)):
                gfx.poly(surf, glow, T.mix(col, T.YELLOW, i * 0.3),
                         gfx.regular((x, y), r * k, 5 + i, t * (0.6 if i % 2 else -0.8)), 2)
            gfx.circle(surf, glow, (255, 255, 255), (int(x), int(y)), 5 + 2 * math.sin(t * 6))

    def draw_cursor(self, surf, glow):
        mx, my = self.app.mouse()
        ax, ay = mx - self.ox, my - self.oy
        target = self.dive.target_at(ax, ay)
        col = T.YELLOW if target else T.TEXT
        pygame.draw.circle(surf, col, (int(mx), int(my)), 9, 1)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            pygame.draw.line(surf, col, (mx + dx * 5, my + dy * 5), (mx + dx * 14, my + dy * 14), 2)
        if target:
            x, y = target.x + self.ox, target.y + self.oy
            s = target.radius + 10
            for qx, qy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                gfx.line(surf, glow, T.YELLOW, (x + qx * s, y + qy * s), (x + qx * (s - 8), y + qy * s), 2)
                gfx.line(surf, glow, T.YELLOW, (x + qx * s, y + qy * s), (x + qx * s, y + qy * (s - 8)), 2)
            name = self.c.bosses[target.type]["name"] if target.boss else self.c.enemies[target.type]["name"]
            gfx.text(surf, name, (x, y + s + 4), 14, T.YELLOW, "bold", anchor="midtop")

    # --- HUD -----------------------------------------------------------------
    def draw_hud(self, surf, glow):
        d = self.dive
        st = d.stats
        p = d.player
        layer = self.c.layers[d.plan.layer]
        # topo
        gfx.text(surf, self.title.upper(), (20, 10), 22, T.color(layer["color"]), "title")
        gfx.text(surf, self.objective_text() or layer["sub"], (20, 34), 15, T.YELLOW if d.mission else T.DIM)
        if d.cfg.mode == "infinite":
            wave = f"ONDA {d.wave}"
        elif d.mission:
            wave = f"ONDA {d.wave}/{d.mission['waves']}"
        else:
            wave = f"ONDA {d.plan.in_layer}/{self.c.balance['waves']['per_layer']}"
        gfx.text(surf, wave, (T.W / 2, 6), 30, T.TEXT, "title", anchor="midtop", glow=glow)
        if d.plan.duration:
            left = d.wave_left()
            gfx.text(surf, f"{int(left) // 60}:{int(left) % 60:02d}", (T.W / 2, 38), 17,
                     T.RED if left < 5 else T.DIM, "mono", anchor="midtop")
        elif d.boss and not d.boss.dead:
            b = d.boss
            w = 420
            x = T.W / 2 - w / 2
            gfx.text(surf, self.c.bosses[b.type]["name"].upper(), (x, 40), 14, T.RED, "bold")
            gfx.bar(surf, (x + 120, 44, w - 120, 9), b.hp / b.max_hp, T.RED, glow=glow)
        # Ed e builds
        edc = T.YELLOW if self.fx.ed_pulse <= 0 else (255, 255, 200)
        gfx.text(surf, f"{gfx.fmt(d.ed)} Ed", (T.W - 20, 6), 24, edc, "title", anchor="topright", glow=glow)
        x = T.W - 20
        for tag in reversed(("contagio", "sobrecarga", "cadeia", "controle")):
            n = d.counts[tag]
            col = T.TAG_COLORS[tag] if n else T.FAINT
            label = f"{self.c.builds[tag]['short'].upper()} {n}"
            w = T.font(13, "bold").size(label)[0] + 14
            x -= w + 4
            ui.chip(surf, (x, 36), label, col, 13, filled=d.auto == tag)
        gfx.text(surf, "TAB: build", (x - 8, 38), 13, T.FAINT, anchor="topright")
        # banner
        if self.fx.banner:
            text, col, t, total = self.fx.banner
            k = min(1.0, t / 0.3, (total - t) / 0.2 + 0.2)
            gfx.text(surf, text, (T.W / 2, 150), 46, T.scale(col, max(0.2, k)), "title", anchor="center", glow=glow)
        # base: Integridade e RAM
        base_y = T.ARENA_Y + d.H + 8
        gfx.panel(surf, (20, base_y, 380, T.H - base_y - 8), T.LINE, T.PANEL, cut=10)
        gfx.text(surf, "INTEGRIDADE", (34, base_y + 8), 14, T.DIM, "bold")
        gfx.text(surf, f"{int(max(0, p.hp))}/{int(st.max_hp)}", (386, base_y + 6), 16, T.TEXT, "mono",
                 anchor="topright")
        gfx.bar(surf, (34, base_y + 28, 352, 12), p.hp / st.max_hp, T.RED, (50, 22, 26), glow)
        gfx.text(surf, "RAM", (34, base_y + 48), 14, T.DIM, "bold")
        gfx.text(surf, f"{gfx.fmt_ram(p.ram)}/{gfx.fmt_ram(st.max_ram)}", (386, base_y + 46), 16, T.TEXT, "mono",
                 anchor="topright")
        blocks = max(1, int(round(st.max_ram)))
        bw = min(28, (352 - (blocks - 1) * 3) / blocks)
        col = T.CYAN if self.fx.drain_flash <= 0 else T.COLORS["blue"]
        for i in range(blocks):
            fill = max(0.0, min(1.0, p.ram - i))
            rect = (34 + i * (bw + 3), base_y + 68, bw, 12)
            pygame.draw.rect(surf, (20, 40, 48), rect)
            if fill > 0:
                pygame.draw.rect(surf, T.scale(col, 0.45 + 0.55 * fill), (rect[0], rect[1], bw * fill, 12))
                if fill >= 1:
                    pygame.draw.rect(glow.surface, col, rect)
        # os slots
        self.draw_slots(surf, glow, base_y)

    def objective_text(self):
        d = self.dive
        if not d.mission:
            return None
        kind = d.objective["type"]
        if kind == "download":
            return f"Proteja o download: {int(d.mission_progress() * 100)}%"
        if kind == "escort":
            return f"Escolte o programa: {int(d.mission_progress() * 100)}%"
        if kind == "nodes":
            return f"Destrua os nós: {d.nodes_left()} restando"
        if kind == "hunt":
            name = self.c.bosses[d.objective["target"]]["name"]
            return f"Cace {name}: ele aparece na onda {d.mission['waves']}"
        return f"Aguente até a extração: onda {d.wave} de {d.mission['waves']}"

    def draw_slots(self, surf, glow, base_y):
        d = self.dive
        n = len(d.slots)
        w, gap = 138, 8
        x0 = 420
        h = T.H - base_y - 8
        mx, my = self.arena_mouse()
        target = d.target_at(mx, my)
        for i, slot in enumerate(d.slots):
            rect = pygame.Rect(x0 + i * (w + gap), base_y, w, h)
            if not slot.hack:
                gfx.panel(surf, rect, T.FAINT, T.PANEL, cut=8)
                gfx.text(surf, f"{i + 1}  vazio", (rect.x + 10, rect.y + 8), 15, T.FAINT, "bold")
                continue
            hd = self.c.hacks[slot.hack]
            col = T.color(hd["color"])
            cost = d.slot_cost(i, target)
            ready = slot.cooldown <= 0
            afford = d.player.ram + 1e-9 >= cost
            border = T.RED if i in self.fx.denied else (col if ready and afford else T.scale(col, 0.4))
            gfx.panel(surf, rect, border, T.PANEL_2 if ready and afford else T.PANEL, cut=8,
                      width=2 if ready and afford else 1, glow=glow if ready and afford else None)
            if not ready:
                k = slot.cooldown / max(0.01, slot.total)
                pygame.draw.rect(surf, (4, 5, 8), (rect.x + 2, rect.y + 2, rect.w - 4, (rect.h - 4) * k))
            key = T.font(22, "title").render(str(i + 1), True, T.YELLOW if ready and afford else T.FAINT)
            surf.blit(key, (rect.x + 10, rect.y + 6))
            gfx.text(surf, hd["name"], (rect.x + 32, rect.y + 9), 16 if len(hd["name"]) < 16 else 14,
                     T.TEXT if ready and afford else T.DIM, "bold")
            gfx.text(surf, f"{gfx.fmt_ram(cost)} RAM", (rect.x + 10, rect.bottom - 26), 14,
                     T.CYAN if afford else T.RED, "mono")
            if not ready:
                gfx.text(surf, f"{slot.cooldown:.1f}s", (rect.right - 10, rect.bottom - 26), 14, T.DIM, "mono",
                         anchor="topright")
            elif hd["kind"] == "supremo":
                gfx.text(surf, "SUPREMO", (rect.right - 10, rect.bottom - 26), 12, T.YELLOW, "bold",
                         anchor="topright")
            for u in d.uploads:
                if u.slot == i:
                    pygame.draw.rect(surf, col, (rect.x + 8, rect.y + 34, (rect.w - 16) * u.t / u.total, 3))

    def draw_build(self, surf, glow, pos):
        d = self.dive
        x, y = pos
        h = 4 * 96 + 50
        gfx.panel(surf, (x, y, 450, h), T.LINE, T.PANEL, alpha=235)
        gfx.text(surf, "A BUILD", (x + 16, y + 10), 22, T.TEXT, "title")
        if d.auto:
            gfx.text(surf, f"automático: {self.c.builds[d.auto]['auto']['name']}", (x + 434, y + 16), 14,
                     T.TAG_COLORS[d.auto], "bold", anchor="topright")
        yy = y + 44
        for tag in ("contagio", "sobrecarga", "cadeia", "controle"):
            b = self.c.builds[tag]
            col = T.TAG_COLORS[tag]
            n = d.counts[tag]
            gfx.text(surf, f"{b['name']}  {n}", (x + 16, yy), 17, col if n else T.DIM, "bold")
            yy += 22
            for th in self.c.balance["build"]["thresholds"]:
                on = n >= th
                gfx.text(surf, f"{th}: {b['bonuses'][th]['desc']}", (x + 26, yy), 14, T.TEXT if on else T.FAINT)
                yy += 18
            yy += 12

    # --- os overlays ---------------------------------------------------------
    def _dim(self, surf, alpha=170, glow=None):
        if glow is not None:
            glow.dim(0.15)
        v = pygame.Surface((T.W, T.H), pygame.SRCALPHA)
        v.fill((3, 4, 8, alpha))
        surf.blit(v, (0, 0))

    def draw_choice(self, surf, glow):
        d = self.dive
        self._dim(surf, glow=glow)
        mouse = self.app.mouse()
        title = f"ONDA {d.plan.in_layer if d.cfg.mode != 'infinite' else d.wave} LIMPA"
        gfx.text(surf, title, (T.W / 2, 70), 40, T.CYAN, "title", anchor="center", glow=glow)
        gfx.text(surf, "Escolha um upgrade (tecla 1 a 4 ou clique)", (T.W / 2, 104), 17, T.DIM, anchor="center")
        n = len(d.offer)
        w, h, gap = 262, 300, 18
        x0 = T.W / 2 - (n * w + (n - 1) * gap) / 2
        for i, up_id in enumerate(d.offer):
            up = self.c.ups[up_id]
            rect = pygame.Rect(x0 + i * (w + gap), 140, w, h)
            hover = rect.collidepoint(mouse)
            rcol = T.RARITY_COLORS[up["rarity"]]
            tags = up.get("tags", [])
            main = T.TAG_COLORS[tags[0]] if tags else rcol
            gfx.panel(surf, rect, main if hover else T.scale(main, 0.6), T.scale(main, 0.12) if hover else T.PANEL,
                      cut=14, width=2, glow=glow if hover else None)
            gfx.text(surf, str(i + 1), (rect.x + 14, rect.y + 10), 26, T.YELLOW, "title")
            gfx.text(surf, T.RARITY_NAMES[up["rarity"]], (rect.right - 14, rect.y + 16), 13, rcol, "bold",
                     anchor="topright")
            gfx.text(surf, up["name"], (rect.x + 16, rect.y + 48), 26 if len(up["name"]) < 16 else 21, T.TEXT, "title")
            cx = rect.x + 16
            for tag in tags:
                r = ui.chip(surf, (cx, rect.y + 86), self.c.builds[tag]["short"], T.TAG_COLORS[tag], 13)
                cx = r.right + 6
            if not tags:
                ui.chip(surf, (cx, rect.y + 86), "qualquer build", T.DIM, 13)
            gfx.text_block(surf, up["desc"], (rect.x + 16, rect.y + 120), w - 32, 17, T.TEXT)
            have = d.taken[up_id]
            gfx.text(surf, f"{have}/{up['max']}", (rect.x + 16, rect.bottom - 30), 14, T.DIM, "mono")
            # o que este up liga
            for tag in tags:
                nxt = d.counts[tag] + 1
                for th in self.c.balance["build"]["thresholds"]:
                    if nxt == th:
                        gfx.text(surf, f"liga o bônus {th} de {self.c.builds[tag]['short']}",
                                 (rect.right - 14, rect.bottom - 30), 13, T.TAG_COLORS[tag], "bold", anchor="topright")
                if nxt == self.c.balance["build"]["auto_at"] and d.auto is None:
                    gfx.text(surf, "liga o ataque automático", (rect.right - 14, rect.bottom - 48), 13,
                             T.TAG_COLORS[tag], "bold", anchor="topright")
            self.clicks.add(rect, lambda i=i: self.pick(i))
        y = 140 + h + 26
        cost = d.reroll_cost()
        ui.button(surf, self.clicks, (T.W / 2 - 330, y, 300, 52), "TROCAR OFERTAS (R)", self.reroll, mouse,
                  enabled=d.ed >= cost, col=T.YELLOW, size=18, sub=f"{cost} Ed")
        ui.button(surf, self.clicks, (T.W / 2 + 30, y, 300, 52), "DESCONECTAR", self.extract, mouse,
                  col=T.CYAN, size=18, sub=f"voltar com {gfx.fmt(d.ed)} Ed")
        # o resumo da build embaixo
        yy = y + 74
        x = T.W / 2 - 300
        for tag in ("contagio", "sobrecarga", "cadeia", "controle"):
            n = d.counts[tag]
            col = T.TAG_COLORS[tag] if n else T.FAINT
            gfx.text(surf, f"{self.c.builds[tag]['short']} {n}", (x, yy), 16, col, "bold")
            x += 150

    def extract(self):
        self.dive.extract()

    def draw_pause(self, surf, glow):
        self._dim(surf, 190, glow)
        mouse = self.app.mouse()
        gfx.text(surf, "PAUSA", (T.W / 2, 200), 56, T.CYAN, "title", anchor="center", glow=glow)
        ui.button(surf, self.clicks, (T.W / 2 - 160, 280, 320, 56), "CONTINUAR (ESC)", self.resume, mouse)
        loss = int(self.dive.ed * self.c.balance["flatline_ed_loss"])
        ui.button(surf, self.clicks, (T.W / 2 - 160, 350, 320, 56), "CORTAR A CONEXÃO", self.abort, mouse,
                  col=T.RED, size=18, sub=f"perde {gfx.fmt(loss)} Ed")
        gfx.text(surf, "Segure o botão esquerdo para andar. Teclas 1-6 lançam os hacks no ICE sob o cursor.",
                 (T.W / 2, 450), 16, T.DIM, anchor="center")
        gfx.text(surf, "TAB mostra a build. F11 alterna a tela cheia.", (T.W / 2, 474), 16, T.DIM, anchor="center")

    def resume(self):
        self.paused = False

    def abort(self):
        self.dive.abort()
        self.paused = False

    def draw_over(self, surf, glow):
        d = self.dive
        s = self.summary or {}
        self._dim(surf, 200, glow)
        mouse = self.app.mouse()
        title, col = RESULTS.get(d.result, ("FIM", T.TEXT))
        if d.mission and d.result == "victory":
            title = "MISSÃO CUMPRIDA"
        gfx.text(surf, title, (T.W / 2, 150), 64, col, "title", anchor="center", glow=glow)
        lines = []
        if d.cfg.mode == "infinite":
            lines.append(f"Ondas vencidas: {d.waves_cleared}" + ("   (novo recorde!)" if s.get("record") else ""))
        elif d.mission:
            lines.append(f"{d.mission['name']}: {d.waves_cleared} de {d.mission['waves']} ondas")
        else:
            lines.append(f"Ondas vencidas: {d.waves_cleared} de {self.c.balance['waves']['per_layer']}")
        lines.append(f"ICE derrubados: {gfx.fmt(d.kills)}")
        ed = f"Ed trazido: {gfx.fmt(s.get('ed', 0))}"
        if s.get("lost"):
            ed += f"   (perdeu {gfx.fmt(s['lost'])})"
        lines.append(ed)
        if s.get("reward_ed"):
            what = "da missão" if d.mission else "da camada"
            lines.append(f"Pagamento {what}: {gfx.fmt(s['reward_ed'])} Ed")
        if s.get("reward_deck"):
            lines.append(f"Cyberdeck novo: {self.c.decks[s['reward_deck']]['name']}")
        if s.get("reward_ally"):
            lines.append(f"{self.c.story['allies'][s['reward_ally']]['name']} entrou para a equipe")
        if s.get("ending"):
            lines.append("A Blackwall caiu. O final está na aba HISTÓRIA.")
        if s.get("reward_hack"):
            lines.append(f"Quickhack novo: {self.c.hacks[s['reward_hack']]['name']}")
        for u in s.get("unlocked", []):
            lines.append(f"Liberado: {u}")
        y = 230
        for row in lines:
            gfx.text(surf, row, (T.W / 2, y), 22, T.TEXT, anchor="center")
            y += 34
        ui.button(surf, self.clicks, (T.W / 2 - 170, y + 30, 340, 58), "VOLTAR AO ESCONDERIJO", self.leave, mouse,
                  col=col)
