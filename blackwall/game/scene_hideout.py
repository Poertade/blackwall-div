"""O esconderijo: escolher o mergulho, montar o cyberdeck, a loja e a árvore."""

import pygame

from blackwall.game import gfx, ui
from blackwall.game import theme as T
from blackwall.meta import profile as pf

TABS = [("mergulho", "MERGULHO"), ("deck", "CYBERDECK"), ("loja", "LOJA"), ("arvore", "ÁRVORE")]


class HideoutScene:
    def __init__(self, app, last=None, tab="mergulho"):
        self.app = app
        self.c = app.content
        self.tab = tab
        self.last = last
        self.clicks = ui.Clicks()
        self.slot = 0
        self.hover_hack = None
        self.hover_node = None
        self.message = None      # (texto, cor, segundos)
        self.bg = gfx.Background((T.W, T.H), T.scale(T.CYAN, 0.7), seed=4)
        pygame.mouse.set_visible(True)

    @property
    def p(self):
        return self.app.profile

    def handle(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.clicks.click(self.app.logical(event.pos)):
                self.app.audio.play("click")
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3 and self.tab == "deck":
            pos = self.app.logical(event.pos)
            for i, rect in enumerate(getattr(self, "slot_rects", [])):
                if rect.collidepoint(pos):
                    pf.set_slot(self.p, i, None)
                    self.app.save()
        elif event.type == pygame.KEYDOWN:
            keys = {pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2, pygame.K_4: 3}
            if event.key in keys and event.mod & pygame.KMOD_CTRL:
                self.tab = TABS[keys[event.key]][0]

    def update(self, dt):
        self.bg.update(dt)
        if self.message:
            text, col, t = self.message
            self.message = (text, col, t - dt) if t - dt > 0 else None

    def say(self, text, col=T.CYAN):
        self.message = (text, col, 2.5)

    # --- ações ---------------------------------------------------------------
    def set_tab(self, tab):
        self.tab = tab

    def start(self, mode, layer=0):
        from blackwall.game.scene_dive import DiveScene
        cfg = pf.dive_config(self.p, self.c, mode, layer)
        if not any(cfg.loadout):
            self.say("Coloque pelo menos um quickhack no deck.", T.RED)
            return
        title = "Ondas infinitas" if mode == "infinite" else self.c.layers[layer]["name"]
        self.app.switch(DiveScene(self.app, cfg, title))

    def buy_hack(self, hid):
        if pf.buy_hack(self.p, self.c, hid):
            self.app.audio.play("buy")
            self.say(f"{self.c.hacks[hid]['name']} instalado.")
            self.app.save()

    def buy_deck(self, did):
        if pf.buy_deck(self.p, self.c, did):
            self.app.audio.play("buy")
            self.say(f"{self.c.decks[did]['name']} instalado.")
            self.app.save()

    def buy_node(self, node):
        if pf.buy_tree(self.p, self.c, node):
            self.app.audio.play("buy")
            self.app.save()
        else:
            self.app.audio.play("denied")

    def equip_deck(self, did):
        pf.set_deck(self.p, self.c, did)
        self.slot = min(self.slot, len(self.p.loadout) - 1)
        self.app.save()

    def put_hack(self, hid):
        pf.set_slot(self.p, self.slot, hid)
        self.slot = (self.slot + 1) % len(self.p.loadout)
        self.app.save()

    # --- desenho -------------------------------------------------------------
    def draw(self, surf, glow):
        self.clicks.reset()
        mouse = self.app.mouse()
        self.bg.draw(surf)
        gfx.text(surf, "BLACKWALL DIVE", (34, 14), 40, T.YELLOW, "title", glow=glow)
        gfx.text(surf, "o esconderijo", (38, 54), 16, T.DIM)
        gfx.text(surf, f"{gfx.fmt(self.p.ed)} Ed", (T.W - 34, 16), 34, T.YELLOW, "title", anchor="topright",
                 glow=glow)
        x = 330
        for key, label in TABS:
            active = self.tab == key
            rect = pygame.Rect(x, 24, 150, 40)
            ui.button(surf, self.clicks, rect, label, lambda k=key: self.set_tab(k), mouse,
                      col=T.YELLOW if active else T.CYAN, size=19, glow=glow if active else None)
            if active:
                pygame.draw.line(surf, T.YELLOW, (rect.x + 8, rect.bottom + 4), (rect.right - 8, rect.bottom + 4), 3)
            x += 160
        pygame.draw.line(surf, T.LINE, (20, 84), (T.W - 20, 84))
        getattr(self, f"draw_{self.tab}")(surf, glow, mouse)
        if self.message:
            text, col, t = self.message
            gfx.text(surf, text, (T.W / 2, T.H - 24), 18, col, "bold", anchor="center")

    # --- MERGULHO ------------------------------------------------------------
    def draw_mergulho(self, surf, glow, mouse):
        p = self.p
        open_layers = pf.available_layers(p, self.c)
        w, h, gap = 232, 270, 14
        x0 = (T.W - (5 * w + 4 * gap)) / 2
        y = 104
        for i, layer in enumerate(self.c.layers):
            rect = pygame.Rect(x0 + i * (w + gap), y, w, h)
            col = T.color(layer["color"])
            unlocked = i < open_layers
            cleared = i < p.layers_cleared
            hover = unlocked and rect.collidepoint(mouse)
            gfx.panel(surf, rect, col if unlocked else T.FAINT, T.scale(col, 0.14) if hover else T.PANEL, cut=14,
                      width=2 if hover else 1, glow=glow if hover else None)
            gfx.text(surf, f"CAMADA {i + 1}", (rect.x + 16, rect.y + 12), 15, col if unlocked else T.FAINT, "bold")
            gfx.text_block(surf, layer["name"], (rect.x + 16, rect.y + 34), w - 32, 24,
                           T.TEXT if unlocked else T.FAINT, "title")
            gfx.text(surf, layer["sub"], (rect.x + 16, rect.y + 96), 15, T.DIM if unlocked else T.FAINT)
            boss = self.c.bosses[layer["boss"]]["name"]
            gfx.text(surf, "10 ondas", (rect.x + 16, rect.y + 132), 15, T.DIM if unlocked else T.FAINT)
            gfx.text(surf, f"chefe: {boss if unlocked else '???'}", (rect.x + 16, rect.y + 152), 15,
                     T.DIM if unlocked else T.FAINT)
            reward = layer.get("reward", {})
            if unlocked and not cleared:
                rtxt = f"paga {gfx.fmt(reward.get('ed', 0))} Ed"
                gfx.text(surf, rtxt, (rect.x + 16, rect.y + 182), 15, T.YELLOW)
                if reward.get("hack"):
                    gfx.text(surf, f"+ {self.c.hacks[reward['hack']]['name']}", (rect.x + 16, rect.y + 202), 15,
                             T.YELLOW)
            status = "VENCIDA" if cleared else ("MERGULHAR" if unlocked else "BLOQUEADA")
            scol = T.COLORS["green"] if cleared else (T.YELLOW if unlocked else T.FAINT)
            gfx.text(surf, status, (rect.centerx, rect.bottom - 26), 18, scol, "bold", anchor="center")
            if unlocked:
                self.clicks.add(rect, lambda i=i: self.start("layer", i))
        # ondas infinitas
        rect = pygame.Rect(x0, y + h + 16, 5 * w + 4 * gap, 84)
        unlocked = pf.infinite_unlocked(p)
        hover = unlocked and rect.collidepoint(mouse)
        col = T.COLORS["pink"]
        gfx.panel(surf, rect, col if unlocked else T.FAINT, T.scale(col, 0.12) if hover else T.PANEL, cut=14,
                  width=2 if hover else 1, glow=glow if hover else None)
        gfx.text(surf, "ONDAS INFINITAS", (rect.x + 20, rect.y + 14), 28, col if unlocked else T.FAINT, "title")
        if unlocked:
            gfx.text(surf, "O mais fundo que você aguentar. Um chefe a cada 10 ondas; o Ed cresce com a profundidade.",
                     (rect.x + 20, rect.y + 50), 16, T.DIM)
            gfx.text(surf, f"recorde: {p.best_infinite} ondas", (rect.right - 20, rect.y + 20), 20, T.TEXT, "bold",
                     anchor="topright")
            self.clicks.add(rect, lambda: self.start("infinite"))
        else:
            gfx.text(surf, "Libera depois de vencer a 1ª camada.", (rect.x + 20, rect.y + 50), 16, T.FAINT)
        # o deck que vai junto
        yy = rect.bottom + 22
        deck = self.c.decks[p.deck]
        gfx.text(surf, f"Deck: {deck['name']}", (x0, yy), 18, T.TEXT, "bold")
        xx = x0
        for i, hid in enumerate(p.loadout):
            label = f"{i + 1} {self.c.hacks[hid]['name']}" if hid else f"{i + 1} vazio"
            col = T.color(self.c.hacks[hid]["color"]) if hid else T.FAINT
            r = ui.chip(surf, (xx, yy + 28), label, col, 15)
            xx = r.right + 8
        gfx.text(surf, "Segure o botão esquerdo para andar · teclas 1 a 6 lançam os hacks no ICE sob o cursor · "
                       "Esc pausa · Tab mostra a build", (x0, yy + 64), 15, T.DIM)

    # --- CYBERDECK -----------------------------------------------------------
    def draw_deck(self, surf, glow, mouse):
        p = self.p
        gfx.text(surf, "CYBERDECKS", (40, 100), 20, T.DIM, "bold")
        y = 130
        for did in p.decks:
            d = self.c.decks[did]
            rect = pygame.Rect(40, y, 330, 70)
            active = did == p.deck
            hover = rect.collidepoint(mouse)
            gfx.panel(surf, rect, T.YELLOW if active else (T.CYAN if hover else T.LINE),
                      T.PANEL_2 if hover or active else T.PANEL, cut=10, width=2 if active else 1)
            gfx.text(surf, d["name"], (rect.x + 14, rect.y + 8), 19, T.TEXT, "bold")
            gfx.text(surf, f"{d['slots']} slots", (rect.right - 14, rect.y + 10), 16, T.YELLOW, "mono",
                     anchor="topright")
            gfx.text(surf, d["desc"], (rect.x + 14, rect.y + 38), 14, T.DIM)
            self.clicks.add(rect, lambda did=did: self.equip_deck(did))
            y += 78
        # os slots
        gfx.text(surf, "SLOTS", (400, 100), 20, T.DIM, "bold")
        y = 130
        self.slot_rects = []
        for i, hid in enumerate(p.loadout):
            rect = pygame.Rect(400, y, 360, 62)
            self.slot_rects.append(rect)
            sel = i == self.slot
            col = T.color(self.c.hacks[hid]["color"]) if hid else T.FAINT
            gfx.panel(surf, rect, T.YELLOW if sel else col, T.PANEL_2 if sel else T.PANEL, cut=10,
                      width=2 if sel else 1, glow=glow if sel else None)
            gfx.text(surf, str(i + 1), (rect.x + 14, rect.y + 12), 30, T.YELLOW, "title")
            if hid:
                h = self.c.hacks[hid]
                gfx.text(surf, h["name"], (rect.x + 50, rect.y + 8), 20, T.TEXT, "bold")
                gfx.text(surf, f"{h['kind']} · {h['ram']} RAM · recarga {h['cooldown']}s", (rect.x + 50, rect.y + 34),
                         14, T.DIM)
            else:
                gfx.text(surf, "vazio", (rect.x + 50, rect.y + 18), 18, T.FAINT)
            self.clicks.add(rect, lambda i=i: setattr(self, "slot", i))
            y += 70
        gfx.text_block(surf, "Clique num slot e depois num quickhack da direita. O botão direito esvazia o slot.",
                       (400, y), 360, 15, T.DIM)
        y += 44
        tags = sorted({t for h in p.loadout if h for t in self.c.hacks[h]["tags"]})
        names = ", ".join(self.c.builds[t]["short"] for t in tags) or "nenhuma (só ups sem tag)"
        y += 6
        gfx.text(surf, "Builds possíveis com estes hacks:", (400, y), 15, T.DIM)
        gfx.text_block(surf, names, (400, y + 20), 360, 16, T.TEXT)
        # os quickhacks
        gfx.text(surf, "SEUS QUICKHACKS", (790, 100), 20, T.DIM, "bold")
        y = 130
        self.hover_hack = None
        for hid in p.hacks:
            h = self.c.hacks[hid]
            rect = pygame.Rect(790, y, 450, 34)
            hover = rect.collidepoint(mouse)
            if hover:
                self.hover_hack = hid
            col = T.color(h["color"])
            equipped = hid in p.loadout
            pygame.draw.rect(surf, T.PANEL_2 if hover else T.PANEL, rect)
            pygame.draw.rect(surf, col if hover else T.LINE, rect, 1)
            gfx.text(surf, h["name"], (rect.x + 10, rect.y + 6), 17, T.TEXT if not equipped else col, "bold")
            gfx.text(surf, f"{h['ram']} RAM", (rect.x + 230, rect.y + 8), 14, T.CYAN, "mono")
            tx = rect.x + 300
            for t in h["tags"]:
                r = ui.chip(surf, (tx, rect.y + 7), self.c.builds[t]["short"], T.TAG_COLORS[t], 12)
                tx = r.right + 4
            self.clicks.add(rect, lambda hid=hid: self.put_hack(hid))
            y += 38
        if self.hover_hack:
            self.draw_hack_details(surf, self.hover_hack, (790, max(y + 10, 560)))

    def draw_hack_details(self, surf, hid, pos):
        h = self.c.hacks[hid]
        x, y = pos
        rect = pygame.Rect(x, y, 450, 120)
        gfx.panel(surf, rect, T.color(h["color"]), T.PANEL, cut=10)
        gfx.text(surf, f"{h['name']}  ({h['kind']})", (x + 14, y + 8), 18, T.TEXT, "bold")
        gfx.text_block(surf, h["desc"], (x + 14, y + 36), 420, 15, T.TEXT)
        gfx.text(surf, f"RAM {h['ram']} · recarga {h['cooldown']}s · upload {h['upload']}s", (x + 14, y + 92), 14,
                 T.DIM, "mono")

    # --- LOJA ----------------------------------------------------------------
    def draw_loja(self, surf, glow, mouse):
        p = self.p
        items = pf.shop(p, self.c)
        gfx.text(surf, "QUICKHACKS", (40, 100), 20, T.DIM, "bold")
        y = 128
        for hid in items["hacks"]:
            h = self.c.hacks[hid]
            rect = pygame.Rect(40, y, 640, 50)
            col = T.color(h["color"])
            pygame.draw.rect(surf, T.PANEL, rect)
            pygame.draw.rect(surf, T.LINE, rect, 1)
            pygame.draw.rect(surf, col, (rect.x, rect.y, 4, rect.h))
            gfx.text(surf, h["name"], (rect.x + 14, rect.y + 4), 18, T.TEXT, "bold")
            gfx.text(surf, f"{h['kind']} · {h['ram']} RAM", (rect.x + 200, rect.y + 7), 14, T.DIM)
            gfx.text(surf, h["desc"], (rect.x + 14, rect.y + 27), 14, T.DIM)
            afford = p.ed >= h["price"]
            ui.button(surf, self.clicks, (rect.right - 130, rect.y + 8, 120, 34), f"{gfx.fmt(h['price'])} Ed",
                      lambda hid=hid: self.buy_hack(hid), mouse, enabled=afford, col=T.YELLOW, size=16)
            y += 55
        if not items["hacks"]:
            gfx.text(surf, "Você já tem todos os quickhacks.", (40, y), 17, T.DIM)
        gfx.text(surf, "CYBERDECKS", (720, 100), 20, T.DIM, "bold")
        y = 128
        for did in items["decks"]:
            d = self.c.decks[did]
            rect = pygame.Rect(720, y, 520, 64)
            pygame.draw.rect(surf, T.PANEL, rect)
            pygame.draw.rect(surf, T.LINE, rect, 1)
            gfx.text(surf, d["name"], (rect.x + 14, rect.y + 6), 18, T.TEXT, "bold")
            gfx.text(surf, f"{d['slots']} slots", (rect.x + 14, rect.y + 34), 15, T.YELLOW, "mono")
            gfx.text(surf, d["desc"], (rect.x + 100, rect.y + 36), 14, T.DIM)
            ui.button(surf, self.clicks, (rect.right - 130, rect.y + 14, 120, 36), f"{gfx.fmt(d['price'])} Ed",
                      lambda did=did: self.buy_deck(did), mouse, enabled=p.ed >= d["price"], col=T.YELLOW, size=16)
            y += 70
        locked = [did for did, d in self.c.decks.items() if did not in p.decks and not d.get("path")
                  and not pf.deck_available(p, self.c, did)]
        for did in locked:
            d = self.c.decks[did]
            gfx.text(surf, f"{d['name']} ({d['slots']} slots): depois da camada {d.get('requires_layer', 0)}",
                     (720, y + 4), 15, T.FAINT)
            y += 24
        if not items["decks"] and not locked:
            gfx.text(surf, "Nada novo por enquanto.", (720, y), 17, T.DIM)

    # --- ÁRVORE --------------------------------------------------------------
    def node_rect(self, node):
        col, row = self.c.tree[node]["pos"]
        return pygame.Rect(70 + col * 168, 110 + row * 130, 150, 96)

    def draw_arvore(self, surf, glow, mouse):
        p = self.p
        for node, n in self.c.tree.items():
            req = n.get("requires")
            if req:
                a, b = self.node_rect(req), self.node_rect(node)
                col = T.CYAN if pf.tree_level(p, req) else T.FAINT
                pygame.draw.line(surf, col, a.center, b.center, 2)
        self.hover_node = None
        for node, n in self.c.tree.items():
            rect = self.node_rect(node)
            level = pf.tree_level(p, node)
            ok, why = pf.tree_status(p, self.c, node)
            hover = rect.collidepoint(mouse)
            if hover:
                self.hover_node = node
            maxed = level >= n["max"]
            col = T.YELLOW if maxed else (T.CYAN if ok else (T.DIM if level else T.FAINT))
            gfx.panel(surf, rect, col, T.PANEL_2 if hover else T.PANEL, cut=10, width=2 if hover else 1,
                      glow=glow if hover and ok else None)
            gfx.text(surf, n["name"], (rect.x + 10, rect.y + 8), 17, T.TEXT, "bold")
            gfx.text(surf, f"{level}/{n['max']}", (rect.right - 10, rect.y + 10), 14, col, "mono", anchor="topright")
            for k in range(n["max"]):
                pygame.draw.rect(surf, col if k < level else T.LINE,
                                 (rect.x + 10 + k * ((rect.w - 20) / n["max"]), rect.y + 36,
                                  (rect.w - 20) / n["max"] - 2, 6))
            if maxed:
                gfx.text(surf, "MÁXIMO", (rect.x + 10, rect.y + 56), 15, T.YELLOW, "bold")
            else:
                cost = pf.tree_cost(self.c, node, level)
                gfx.text(surf, f"{gfx.fmt(cost)} Ed", (rect.x + 10, rect.y + 56), 16,
                         T.YELLOW if p.ed >= cost else T.DIM, "mono")
            self.clicks.add(rect, lambda node=node: self.buy_node(node))
        node = self.hover_node
        if node:
            n = self.c.tree[node]
            ok, why = pf.tree_status(p, self.c, node)
            rect = pygame.Rect(70, T.H - 110, 760, 70)
            gfx.panel(surf, rect, T.LINE, T.PANEL, cut=10)
            gfx.text(surf, f"{n['name']}: {n['desc']}", (rect.x + 16, rect.y + 10), 19, T.TEXT, "bold")
            gfx.text(surf, "clique para comprar" if ok else why, (rect.x + 16, rect.y + 40), 15,
                     T.CYAN if ok else T.DIM)
        gfx.text(surf, "Só números: cada nível vale para todos os mergulhos.", (T.W - 40, T.H - 70), 15, T.DIM,
                 anchor="topright")
