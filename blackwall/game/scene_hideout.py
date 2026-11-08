"""O esconderijo: escolher o mergulho, montar o cyberdeck, a loja e a árvore."""

import pygame

from blackwall.game import gfx, ui
from blackwall.game import theme as T
from blackwall.meta import profile as pf
from blackwall.meta import story

TABS = [("mergulho", "MERGULHO"), ("historia", "HISTÓRIA"), ("deck", "CYBERDECK"), ("loja", "LOJA"),
        ("arvore", "ÁRVORE")]
OBJECTIVES = {
    "survive": "Aguente até a extração",
    "download": "Proteja o nó do download",
    "escort": "Escolte o programa até o outro lado",
    "nodes": "Destrua os nós de cada onda",
    "hunt": "Cace o alvo da última onda",
}


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
        self.armed = None        # o caminho clicado uma vez (o segundo clique confirma)
        self.save_t = 0.0
        gain = getattr(app, "offline_gain", 0)
        if gain:
            who = "a equipe rendeu" if self.p.path == "equipe" else "o salário da Netwatch rendeu"
            self.say(f"Enquanto você esteve fora, {who} {gfx.fmt(gain)} Ed.", T.YELLOW)
            app.offline_gain = 0
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
            keys = {pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2, pygame.K_4: 3, pygame.K_5: 4}
            if event.key in keys and event.mod & pygame.KMOD_CTRL:
                self.tab = TABS[keys[event.key]][0]

    def update(self, dt):
        self.bg.update(dt)
        # a renda da equipe (ou o salário) corre enquanto você está no esconderijo
        if story.accrue(self.p, self.c, dt):
            self.save_t += dt
        if self.save_t > 30:
            self.save_t = 0.0
            self.app.save()
        if self.message:
            text, col, t = self.message
            self.message = (text, col, t - dt) if t - dt > 0 else None

    def say(self, text, col=T.CYAN):
        self.message = (text, col, 2.5)

    # --- ações ---------------------------------------------------------------
    def set_tab(self, tab):
        self.tab = tab
        self.armed = None

    def start_mission(self, mission):
        from blackwall.game.scene_dive import DiveScene
        cfg = pf.dive_config(self.p, self.c, "mission", mission=mission)
        if not any(cfg.loadout):
            self.say("Coloque pelo menos um quickhack no deck.", T.RED)
            return
        self.app.switch(DiveScene(self.app, cfg, mission["name"]))

    def pick_path(self, path):
        if self.armed != path:
            self.armed = path
            self.app.audio.play("click")
            return
        if pf.choose_path(self.p, self.c, path):
            self.armed = None
            self.app.audio.play("victory")
            self.say(f"Caminho escolhido: {self.c.story['paths'][path]['name']}.", T.YELLOW)
            self.app.save()

    def train(self, ally):
        if story.train_ally(self.p, self.c, ally):
            self.app.audio.play("buy")
            self.app.save()
        else:
            self.app.audio.play("denied")

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
        x = 318
        news = bool(story.unread(self.p, self.c)) or story.needs_path_choice(self.p)
        for key, label in TABS:
            active = self.tab == key
            rect = pygame.Rect(x, 24, 138, 40)
            ui.button(surf, self.clicks, rect, label, lambda k=key: self.set_tab(k), mouse,
                      col=T.YELLOW if active else T.CYAN, size=18, glow=glow if active else None)
            if active:
                pygame.draw.line(surf, T.YELLOW, (rect.x + 8, rect.bottom + 4), (rect.right - 8, rect.bottom + 4), 3)
            if key == "historia" and news and not active:
                gfx.circle(surf, glow, T.RED, (rect.right - 10, rect.y + 9), 5)
            x += 146
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
            if not unlocked and i == p.layers_cleared and story.needs_path_choice(p):
                status = "ESCOLHA O CAMINHO"
                scol = T.RED
                gfx.text(surf, "na aba HISTÓRIA", (rect.centerx, rect.bottom - 52), 15, T.RED, anchor="center")
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

    # --- HISTÓRIA ------------------------------------------------------------
    def draw_historia(self, surf, glow, mouse):
        p = self.p
        st = self.c.story
        # as mensagens, da mais nova para a mais velha
        x, y, w = 40, 100, 590
        gfx.text(surf, "MENSAGENS", (x, y), 20, T.DIM, "bold")
        y += 30
        end = story.ending(p, self.c)
        if end:
            rect = pygame.Rect(x, y, w, 10)
            lines = gfx.wrap(end["text"].strip(), 16, w - 28)
            rect.h = 46 + len(lines) * 20
            gfx.panel(surf, rect, T.YELLOW, T.PANEL_2, cut=10, glow=glow)
            gfx.text(surf, end["title"].upper(), (x + 14, y + 10), 20, T.YELLOW, "title")
            gfx.text_block(surf, end["text"].strip(), (x + 14, y + 38), w - 28, 16, T.TEXT)
            y = rect.bottom + 12
        for beat in reversed(story.beats(p, self.c)):
            ch = st["characters"][beat["from"]]
            col = T.color(ch["color"])
            lines = gfx.wrap(beat["text"].strip().replace("\n", " "), 16, w - 28)
            h = 40 + len(lines) * 20
            if y + h > T.H - 40:
                break
            rect = pygame.Rect(x, y, w, h)
            gfx.panel(surf, rect, T.scale(col, 0.7), T.PANEL, cut=8)
            gfx.text(surf, ch["name"], (x + 14, y + 8), 18, col, "bold")
            gfx.text(surf, ch["role"], (x + 20 + T.font(18, "bold").size(ch["name"])[0], y + 11), 14, T.DIM)
            gfx.text_block(surf, beat["text"].strip().replace("\n", " "), (x + 14, y + 32), w - 28, 16, T.TEXT)
            y += h + 10
        story.mark_read(p, self.c)
        # à direita: a escolha, ou as missões e a equipe
        x, y, w = 660, 100, 580
        if story.needs_path_choice(p):
            gfx.text(surf, "A ENCRUZILHADA", (x, y), 20, T.RED, "bold")
            gfx.text(surf, "Uma escolha por salvamento. Não dá para voltar atrás.", (x, y + 26), 15, T.DIM)
            y += 56
            for path in ("solo", "equipe", "netwatch"):
                d = st["paths"][path]
                col = T.color(d["color"])
                rect = pygame.Rect(x, y, w, 150)
                armed = self.armed == path
                gfx.panel(surf, rect, T.RED if armed else col, T.PANEL_2 if armed else T.PANEL, cut=12,
                          width=2 if armed else 1, glow=glow if armed else None)
                who = st["characters"][d["who"]]["name"]
                gfx.text(surf, d["name"].upper(), (x + 16, y + 12), 26, col, "title")
                gfx.text(surf, f"com {who}" if path != "solo" else "recusar os dois convites", (x + 18, y + 44), 15,
                         T.DIM)
                gfx.text_block(surf, d["desc"], (x + 16, y + 68), w - 210, 15, T.TEXT)
                label = "CONFIRMAR" if armed else "ESCOLHER"
                ui.button(surf, self.clicks, (rect.right - 180, y + 50, 164, 50), label,
                          lambda path=path: self.pick_path(path), mouse, col=T.RED if armed else col, size=18,
                          sub="é para sempre" if armed else None)
                y += 162
            return
        if p.path is None:
            gfx.text(surf, "Vença a 1ª camada. A Rhyme vai ter notícias.", (x, y), 18, T.DIM)
            return
        d = st["paths"][p.path]
        gfx.text(surf, f"CAMINHO: {d['name'].upper()}", (x, y), 20, T.color(d["color"]), "bold")
        y += 30
        for m, status in story.missions(p, self.c):
            rect = pygame.Rect(x, y, w, 104)
            open_ = status == "open"
            hover = open_ and rect.collidepoint(mouse)
            col = T.COLORS["green"] if status == "done" else (T.YELLOW if open_ else T.FAINT)
            gfx.panel(surf, rect, col, T.PANEL_2 if hover else T.PANEL, cut=10, width=2 if hover else 1,
                      glow=glow if hover else None)
            gfx.text(surf, m["name"], (x + 14, y + 8), 20, T.TEXT if status != "locked" else T.FAINT, "bold")
            who = st["characters"][m["from"]]["name"]
            gfx.text(surf, f"{who} · {m['waves']} ondas · {OBJECTIVES[m['objective']['type']]}", (x + 14, y + 34),
                     14, T.DIM)
            if status == "locked":
                gfx.text(surf, f"depois da camada {m['requires']['layers']}", (x + 14, y + 58), 15, T.FAINT)
            else:
                gfx.text_block(surf, m["brief"], (x + 14, y + 54), w - 160, 14, T.TEXT)
            gfx.text(surf, self.reward_text(m), (rect.right - 14, y + 10), 14, T.YELLOW, "bold", anchor="topright")
            label = {"done": "FEITA", "open": "MERGULHAR", "locked": "BLOQUEADA"}[status]
            gfx.text(surf, label, (rect.right - 14, rect.bottom - 28), 17, col, "bold", anchor="topright")
            if open_:
                self.clicks.add(rect, lambda m=m: self.start_mission(m))
            y += 112
        team = story.quest(p)["team"]
        if p.path in ("equipe", "netwatch") and team:
            y += 6
            rate = story.income_rate(p, self.c)
            title = "A EQUIPE" if p.path == "equipe" else "O PARCEIRO"
            gfx.text(surf, title, (x, y), 18, T.DIM, "bold")
            gfx.text(surf, f"rende {gfx.fmt(rate)} Ed por hora fora do mergulho", (x + w, y + 2), 15, T.YELLOW,
                     anchor="topright")
            y += 26
            for ally, level in team.items():
                a = st["allies"][ally]
                col = T.color(a["color"])
                gfx.text(surf, f"{a['name']}  nv {level}", (x, y + 4), 17, col, "bold")
                gfx.text(surf, a["desc"], (x, y + 26), 13, T.DIM)
                ok, why = story.train_status(p, self.c, ally)
                maxed = level >= st["ally_level"]["max"]
                label = "MÁXIMO" if maxed else f"TREINAR {gfx.fmt(story.ally_cost(self.c, level))} Ed"
                ui.button(surf, self.clicks, (x + w - 190, y + 4, 190, 36), label, lambda ally=ally: self.train(ally),
                          mouse, enabled=ok, col=T.YELLOW, size=15)
                y += 48

    def reward_text(self, m) -> str:
        r = m.get("reward", {})
        parts = []
        if r.get("ed"):
            parts.append(f"{gfx.fmt(r['ed'])} Ed")
        if r.get("hack"):
            parts.append(self.c.hacks[r["hack"]]["name"])
        if r.get("deck"):
            parts.append(self.c.decks[r["deck"]]["name"])
        if r.get("ally"):
            parts.append(self.c.story["allies"][r["ally"]]["name"].split('"')[0].strip())
        return " + ".join(parts)
