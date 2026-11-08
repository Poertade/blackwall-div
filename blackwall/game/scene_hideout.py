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
    mood = "desktop"     # a trilha do apartamento

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
        if event.type == pygame.MOUSEWHEEL and self.tab == "historia":
            self.chat_scroll = max(0, getattr(self, "chat_scroll", 0) + event.y * 40)
            return
        if event.type == pygame.KEYDOWN and self.tab == "historia" and not event.mod & pygame.KMOD_CTRL:
            numbers = {pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2, pygame.K_4: 3}
            if event.key in numbers:
                chans = {c[0]: c for c in self.channels()}
                current = chans.get(getattr(self, "channel", None))
                if current:
                    acts = self.actions(current[0], current[4])
                    if numbers[event.key] < len(acts):
                        acts[numbers[event.key]][1]()
                        self.app.audio.play("click")
                return
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
            gfx.text(surf, "Libera depois de vencer a primeira camada.", (rect.x + 20, rect.y + 50), 16, T.FAINT)
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
        gfx.text(surf, "O botão esquerdo usa o hack de movimento · teclas 1 a 7 lançam os hacks no ICE sob o cursor · "
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
    def draw_arvore(self, surf, glow, mouse):
        """A árvore da netrunner (Netrunner) e a de cada quickhack que você tem, escolhidas na coluna da esquerda."""
        p = self.p
        sel = getattr(self, "tree_sel", None)
        if sel is not None and sel not in p.hacks:
            sel = self.tree_sel = None
        # o seletor
        y = 100
        options = [(None, "NETRUNNER", T.YELLOW)] + [(h, self.c.hacks[h]["name"], T.color(self.c.hacks[h]["color"]))
                                                      for h in p.hacks if h in self.c.hack_trees]
        for key, label, col in options:
            rect = pygame.Rect(30, y, 230, 30)
            active = key == sel
            hover = rect.collidepoint(mouse)
            pygame.draw.rect(surf, T.scale(col, 0.18) if active else (T.PANEL_2 if hover else T.PANEL), rect)
            pygame.draw.rect(surf, col if active or hover else T.LINE, rect, 1)
            gfx.text(surf, label, (rect.x + 10, rect.y + 5), 16, col if active else T.TEXT, "bold")
            self.clicks.add(rect, lambda key=key: setattr(self, "tree_sel", key))
            y += 34
        # os nós
        if sel is None:
            nodes = self.c.tree
            level_of = lambda n: pf.tree_level(p, n)
            status = lambda n: pf.tree_status(p, self.c, n)
            cost = lambda n: pf.tree_cost(self.c, n, level_of(n))
            buy = self.buy_node
            title, note = "NETRUNNER", "Só números: cada nível vale para todos os mergulhos."
        else:
            nodes = self.c.hack_trees[sel]
            level_of = lambda n: pf.hack_level(p, sel, n)
            status = lambda n: pf.hack_node_status(p, self.c, sel, n)
            cost = lambda n: pf.hack_node_cost(self.c, sel, n, level_of(n))
            buy = lambda n: self.buy_hack_node(sel, n)
            title, note = self.c.hacks[sel]["name"].upper(), "Os efeitos especiais deste quickhack, para todos os mergulhos."
        gfx.text(surf, title, (290, 96), 20, T.DIM, "bold")
        rects = {}
        for node, n in nodes.items():
            if pf.visible(level_of, nodes, node):
                col, row = n["pos"]
                rects[node] = pygame.Rect(290 + col * 140, 126 + row * 122, 130, 104)
        for node, rect in rects.items():
            req = nodes[node].get("requires")
            if req in rects:
                pygame.draw.line(surf, T.CYAN, rects[req].center, rect.center, 2)
        hovered = None
        for node, rect in rects.items():
            n = nodes[node]
            level = level_of(node)
            ok, why = status(node)
            hover = rect.collidepoint(mouse)
            if hover:
                hovered = node
            maxed = level >= n["max"]
            col = T.YELLOW if maxed else (T.CYAN if ok else (T.TEXT if level else T.DIM))
            gfx.panel(surf, rect, col, T.PANEL_2 if hover else T.PANEL, cut=10, width=2 if hover else 1,
                      glow=glow if hover and ok else None)
            name = n["name"]
            size = 16 if T.font(16, "bold").size(name)[0] <= rect.w - 16 else 13
            gfx.text(surf, name, (rect.x + 8, rect.y + 8), size, T.TEXT, "bold")
            gfx.text(surf, f"nível {level}/{n['max']}", (rect.x + 8, rect.y + 32), 13, col, "mono")
            gfx.bar(surf, (rect.x + 8, rect.y + 52, rect.w - 16, 5), level / n["max"], col, back=T.LINE)
            if maxed:
                gfx.text(surf, "MÁXIMO", (rect.x + 8, rect.y + 70), 15, T.YELLOW, "bold")
            else:
                c = cost(node)
                gfx.text(surf, f"{gfx.fmt(c)} Ed", (rect.x + 8, rect.y + 70), 15,
                         T.YELLOW if p.ed >= c else T.DIM, "mono")
            self.clicks.add(rect, lambda node=node: buy(node))
        hidden = len(nodes) - len(rects)
        if hidden:
            gfx.text(surf, f"+{hidden} {'melhoria oculta' if hidden == 1 else 'melhorias ocultas'}: compre o nó "
                           "de cima para revelar", (290, T.H - 140), 15, T.DIM)
        if hovered:
            n = nodes[hovered]
            ok, why = status(hovered)
            rect = pygame.Rect(290, T.H - 110, 760, 70)
            gfx.panel(surf, rect, T.LINE, T.PANEL, cut=10)
            gfx.text(surf, f"{n['name']}: {n['desc']}", (rect.x + 16, rect.y + 10), 19, T.TEXT, "bold")
            gfx.text(surf, "clique para comprar" if ok else why, (rect.x + 16, rect.y + 40), 15,
                     T.CYAN if ok else T.DIM)
        gfx.text(surf, note, (T.W - 30, T.H - 30), 15, T.DIM, anchor="topright")

    def buy_hack_node(self, hack, node):
        if pf.buy_hack_node(self.p, self.c, hack, node):
            self.app.audio.play("buy")
            self.app.save()
        else:
            self.app.audio.play("denied")

    # --- HISTÓRIA ------------------------------------------------------------
    # --- HISTÓRIA: o Mensageiro (como no primeiro jogo) ---------------------------
    def channels(self) -> list:
        """As conversas: [(id, nome, papel, cor, itens)], na ordem dos contatos. Itens: (tipo, dado)."""
        p, st = self.p, self.c.story
        items = {}
        for beat in story.beats(p, self.c):
            items.setdefault(beat["from"], []).append(("beat", beat))
        for m, status in story.missions(p, self.c):
            if status != "locked":
                items.setdefault(m["from"], []).append(("mission", (m, status)))
        end = story.ending(p, self.c)
        if end and p.path:
            items.setdefault(st["paths"][p.path]["who"], []).append(("ending", end))
        result = []
        for cid, ch in st["characters"].items():
            if cid in items:
                result.append((cid, ch["name"], ch["role"], T.color(ch["color"]), items[cid]))
        if p.path in ("equipe", "netwatch") and story.quest(p)["team"]:
            name = "Equipe" if p.path == "equipe" else "Agente Varga"
            role = "os runners que mergulham com você" if p.path == "equipe" else "o seu parceiro na Netwatch"
            result.append(("_team", name, role, T.COLORS["green"], [("team", None)]))
        return result

    def unread_in(self, items) -> int:
        read = set(story.quest(self.p)["read"])
        return sum(1 for kind, data in items if kind == "beat" and data["id"] not in read)

    def open_channel(self, cid):
        self.channel = cid
        self.chat_scroll = 0
        self.armed = None

    def draw_historia(self, surf, glow, mouse):
        p = self.p
        chans = self.channels()
        frame = pygame.Rect(40, 96, T.W - 80, T.H - 120)
        accent = T.RED
        pygame.draw.rect(surf, (10, 11, 16), frame)
        gfx.panel(surf, frame, accent, (10, 11, 16), cut=14)
        pygame.draw.line(surf, accent, (frame.x, frame.y + 30), (frame.right, frame.y + 30))
        pygame.draw.rect(surf, T.YELLOW, (frame.x + 16, frame.y + 10, 4, 12))
        gfx.text(surf, "MENSAGEIRO", (frame.x + 28, frame.y + 7), 15, accent, "bold")
        if not chans:
            return
        ids = [c[0] for c in chans]
        current = getattr(self, "channel", None)
        if current not in ids:
            unread = [c[0] for c in chans if self.unread_in(c[4])]
            current = self.channel = (unread[0] if unread else ids[0])
        # a lista de conversas
        list_rect = pygame.Rect(frame.x + 1, frame.y + 31, 300, frame.h - 32)
        pygame.draw.line(surf, T.LINE, (list_rect.right, list_rect.y), (list_rect.right, list_rect.bottom))
        y = list_rect.y
        for cid, name, role, col, items in chans:
            row = pygame.Rect(list_rect.x, y, list_rect.w, 62)
            active = cid == current
            if active:
                pygame.draw.rect(surf, (40, 18, 22), row)
                pygame.draw.rect(surf, accent, (row.x, row.y, 3, row.h))
            elif row.collidepoint(mouse):
                pygame.draw.rect(surf, T.PANEL_2, row)
            self.avatar(surf, name, col, (row.x + 14, row.y + 13), 36)
            gfx.text(surf, name.upper(), (row.x + 60, row.y + 10), 15, T.TEXT, "bold")
            preview = self.preview(items)
            gfx.text(surf, preview, (row.x + 60, row.y + 34), 13, T.DIM)
            unread = self.unread_in(items)
            if unread and not active:
                badge = pygame.Rect(row.right - 34, row.y + 10, 22, 20)
                pygame.draw.rect(surf, accent, badge)
                gfx.text(surf, str(unread), badge.center, 13, (10, 10, 14), "bold", anchor="center")
            self.clicks.add(row, lambda cid=cid: self.open_channel(cid))
            y += 64
        cid, name, role, col, items = next(c for c in chans if c[0] == current)
        # a conversa
        chat = pygame.Rect(list_rect.right + 1, list_rect.y, frame.right - list_rect.right - 2, list_rect.h)
        self.avatar(surf, name, col, (chat.x + 16, chat.y + 14), 36)
        gfx.text(surf, name, (chat.x + 64, chat.y + 12), 19, T.TEXT, "bold")
        gfx.text(surf, role, (chat.x + 64, chat.y + 36), 14, T.scale(accent, 0.8))
        pygame.draw.line(surf, accent, (chat.x, chat.y + 64), (chat.right, chat.y + 64))
        actions = self.actions(cid, items)
        actions_h = sum(a[2] for a in actions) + (16 if actions else 0)
        area = pygame.Rect(chat.x + 14, chat.y + 74, chat.w - 28, chat.h - 84 - actions_h)
        if cid == "_team":
            self.draw_team(surf, mouse, area)
        else:
            self.draw_bubbles(surf, items, area)
        # as respostas / ações (como as opções de resposta do Mensageiro)
        if actions:
            y = area.bottom + 8
            pygame.draw.line(surf, accent, (chat.x, y - 2), (chat.right, y - 2))
            y += 6
            for label, action, h, col2 in actions:
                rect = pygame.Rect(chat.x + 14, y, chat.w - 28, h - 6)
                hover = rect.collidepoint(mouse)
                pygame.draw.rect(surf, T.scale(col2, 0.16) if hover else (12, 13, 18), rect)
                pygame.draw.rect(surf, col2 if hover else T.scale(col2, 0.6), rect, 1)
                gfx.text(surf, label, (rect.x + 12, rect.centery), 16, col2, "ui", anchor="midleft")
                self.clicks.add(rect, action)
                y += h
        story.quest(p)  # garante o estado
        q = story.quest(p)
        for kind, data in items:
            if kind == "beat" and data["id"] not in q["read"]:
                q["read"].append(data["id"])

    def avatar(self, surf, name, col, pos, size):
        rect = pygame.Rect(pos[0], pos[1], size, size)
        pygame.draw.rect(surf, (10, 11, 16), rect)
        pygame.draw.rect(surf, col, rect, 1)
        pygame.draw.rect(surf, col, (rect.x, rect.bottom - 3, rect.w, 3))
        gfx.text(surf, name[:1].upper(), rect.center, 18, col, "bold", anchor="center")

    def preview(self, items) -> str:
        kind, data = items[-1]
        if kind == "beat":
            text = data["text"].strip().splitlines()[-1]
        elif kind == "mission":
            text = f"Serviço: {data[0]['name']}"
        elif kind == "ending":
            text = data["title"]
        else:
            text = f"rende {gfx.fmt(story.income_rate(self.p, self.c))} Ed por hora"
        return text if len(text) < 30 else text[:29] + "…"

    def bubbles(self, items, width):
        """Cada fala vira balões (um por linha do texto); os serviços e o final ganham balões próprios."""
        result = []   # (linhas, cor da barra, título)
        for kind, data in items:
            if kind == "beat":
                for line in data["text"].strip().splitlines():
                    if line.strip():
                        result.append((gfx.wrap(line.strip(), 16, width - 30), T.CYAN, None))
            elif kind == "mission":
                m, status = data
                body = f"{m['brief']}  Recompensa: {self.reward_text(m)}."
                title = f"SERVIÇO · {m['name']}" + ("  ·  FEITO" if status == "done" else "")
                result.append((gfx.wrap(body, 16, width - 30), T.COLORS["green"] if status == "done" else T.YELLOW,
                               title))
            elif kind == "ending":
                result.append((gfx.wrap(data["text"].strip().replace("\n", " "), 16, width - 30), T.YELLOW,
                               data["title"].upper()))
        return result

    def draw_bubbles(self, surf, items, area):
        width = int(area.w * 0.78)
        bubbles = self.bubbles(items, width)
        line_h = 21
        heights = [len(lines) * line_h + 22 + (22 if title else 0) for lines, _c, title in bubbles]
        total = sum(heights) + 10 * len(heights)
        scroll = max(0, min(getattr(self, "chat_scroll", 0), total - area.h))
        self.chat_scroll = scroll
        y = area.bottom - total + scroll if total > area.h else area.y
        clip = surf.get_clip()
        surf.set_clip(area)
        for (lines, col, title), h in zip(bubbles, heights):
            if y + h >= area.y and y <= area.bottom:
                w = max(T.font(16).size(row)[0] for row in lines) + 30 if lines else 200
                if title:
                    w = max(w, T.font(14, "bold").size(title)[0] + 30)
                rect = pygame.Rect(area.x, y, min(width, w), h)
                pygame.draw.rect(surf, (14, 18, 24), rect)
                pygame.draw.rect(surf, T.scale(col, 0.55), rect, 1)
                pygame.draw.rect(surf, col, (rect.x, rect.y, 3, rect.h))
                yy = rect.y + 10
                if title:
                    gfx.text(surf, title, (rect.x + 14, yy), 14, col, "bold")
                    yy += 22
                for row in lines:
                    gfx.text(surf, row, (rect.x + 14, yy), 16, T.TEXT)
                    yy += line_h
            y += h + 10
        surf.set_clip(clip)
        if total > area.h:
            gfx.text(surf, "role o mouse para ver as mais antigas", (area.right, area.y - 6), 12, T.FAINT,
                     anchor="topright")

    def actions(self, cid, items) -> list:
        """As opções de resposta: a escolha do caminho, os serviços abertos. [(texto, ação, altura, cor)]."""
        p, st = self.p, self.c.story
        result = []
        if cid == "rhyme" and story.needs_path_choice(p):
            labels = {"solo": "Seguir sozinha", "equipe": "Aceitar o convite da Juno",
                      "netwatch": "Aceitar a oferta da Netwatch"}
            for i, path in enumerate(("solo", "equipe", "netwatch")):
                d = st["paths"][path]
                if self.armed == path:
                    text = f"{i + 1}.  CONFIRMAR: {d['name']}. É para sempre."
                    col = T.RED
                else:
                    text = f"{i + 1}.  {labels[path]} ({d['name']}): {d['desc']}"
                    col = T.YELLOW
                if T.font(16).size(text)[0] > 820:
                    text = text[:110] + "…"
                result.append((text, lambda path=path: self.pick_path(path), 46, col))
        for kind, data in items:
            if kind == "mission" and data[1] == "open":
                m = data[0]
                text = f"{len(result) + 1}.  ACEITAR SERVIÇO: {m['name']} ({m['waves']} ondas)"
                result.append((text, lambda m=m: self.start_mission(m), 46, T.YELLOW))
        return result

    def draw_team(self, surf, mouse, area):
        p, st = self.p, self.c.story
        team = story.quest(p)["team"]
        y = area.y
        rate = story.income_rate(p, self.c)
        gfx.text(surf, f"Fora do mergulho (até com o jogo fechado) a {'equipe' if p.path == 'equipe' else 'Netwatch'}"
                       f" rende {gfx.fmt(rate)} Ed por hora.", (area.x, y), 16, T.YELLOW)
        y += 34
        for ally, level in team.items():
            a = st["allies"][ally]
            col = T.color(a["color"])
            rect = pygame.Rect(area.x, y, area.w, 70)
            pygame.draw.rect(surf, (14, 18, 24), rect)
            pygame.draw.rect(surf, T.scale(col, 0.55), rect, 1)
            pygame.draw.rect(surf, col, (rect.x, rect.y, 3, rect.h))
            self.avatar(surf, a["name"].replace('"', ""), col, (rect.x + 14, rect.y + 16), 36)
            gfx.text(surf, f"{a['name']}  ·  nível {level}", (rect.x + 62, rect.y + 12), 17, col, "bold")
            gfx.text(surf, a["desc"], (rect.x + 62, rect.y + 40), 14, T.DIM)
            ok, why = story.train_status(p, self.c, ally)
            maxed = level >= st["ally_level"]["max"]
            label = "MÁXIMO" if maxed else f"TREINAR {gfx.fmt(story.ally_cost(self.c, level))} Ed"
            ui.button(surf, self.clicks, (rect.right - 210, rect.y + 16, 196, 38), label,
                      lambda ally=ally: self.train(ally), mouse, enabled=ok, col=T.YELLOW, size=15)
            y += 80
        missing = [a for a in ("ruido", "mira") if p.path == "equipe" and a not in team]
        for a in missing:
            gfx.text(surf, f"{st['allies'][a]['name']} entra pelas missões da Juno.", (area.x, y), 15, T.FAINT)
            y += 24

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
