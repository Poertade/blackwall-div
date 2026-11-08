"""O menu de opções (Esc no esconderijo, ou OPÇÕES na pausa do mergulho).

Volumes, tela cheia, tremor de tela, controles e ajuda, apagar o save (só no esconderijo, com dois cliques)
e sair do jogo. As escolhas ficam em profile.settings e são salvas na hora.
"""

import pygame

from blackwall.game import gfx, ui
from blackwall.game import theme as T

HELP = [
    ("CONTROLES", [
        "Botão esquerdo: o hack de movimento. Um clique marca o destino e a netrunner vai sozinha;",
        "segurar arrasta o destino. Com o Kerenzikov ou o Teleporte, o clique dá o dash ou o teleporte.",
        "Teclas 1 a 7: lançam o quickhack do slot no ICE sob o cursor (a mira pega o mais perto).",
        "Botão direito: o primeiro hack de ataque do deck.",
        "Tab: a build (tags, bônus, ataque automático).   Esc: pausa e opções.",
        "F11: tela cheia.   F2: efeitos sonoros.   F3: música.",
    ]),
    ("O MERGULHO", [
        "Cada camada tem 10 ondas e um chefe na décima. A onda acaba quando todos os ICE caem;",
        "se demorar, chegam reforços. Entre as ondas você escolhe 1 de 3 ups (só números, com tag de build).",
        "Juntar ups da mesma tag liga bônus com 2, 4 e 6, e com 3 liga o ataque automático da build.",
        "Os hacks gastam RAM; andar também. Flatline perde 25% do Ed do mergulho; desconectar entre as",
        "ondas volta com tudo.",
    ]),
    ("O ESCONDERIJO", [
        "LOJA: quickhacks e cyberdecks.   ÁRVORE: os números da netrunner e os efeitos de cada hack.",
        "HISTÓRIA: as mensagens, a escolha do caminho (Solo, Equipe, Netwatch) e os serviços.",
        "BLACKWALL: depois da terceira camada, atravesse para recomeçar mais forte com Fragmentos de Relic.",
    ]),
]


class Options:
    def __init__(self, app, in_dive=False, on_close=None):
        self.app = app
        self.in_dive = in_dive
        self.on_close = on_close
        self.clicks = ui.Clicks()
        self.armed = False       # apagar o save pede dois cliques
        self.help = False

    @property
    def settings(self):
        return self.app.profile.settings

    def close(self):
        self.app.save()
        if self.on_close:
            self.on_close()

    def handle(self, event) -> bool:
        """Devolve True se o evento foi usado aqui."""
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.help:
                self.help = False
            else:
                self.close()
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.clicks.click(self.app.logical(event.pos)):
                self.app.audio.play("click")
            return True
        return event.type in (pygame.MOUSEBUTTONUP, pygame.KEYDOWN, pygame.MOUSEWHEEL)

    # --- ações ---------------------------------------------------------------
    def volume(self, which, delta):
        key = "volume" if which == "efeitos" else "music"
        value = round(min(1.0, max(0.0, self.settings.get(key, 0.5) + delta)), 2)
        self.settings[key] = value
        if which == "efeitos":
            self.app.audio.volume = value
        else:
            self.app.music.volume = value

    def toggle_shake(self):
        self.settings["shake"] = not self.settings.get("shake", True)
        scene = self.app.scene
        if hasattr(scene, "fx"):
            scene.fx.shake_enabled = self.settings["shake"]

    def reset(self):
        if not self.armed:
            self.armed = True
            return
        self.app.reset_save()

    # --- desenho -------------------------------------------------------------
    def draw(self, surf, glow):
        self.clicks.reset()
        mouse = self.app.mouse()
        v = pygame.Surface((T.W, T.H), pygame.SRCALPHA)
        v.fill((3, 4, 8, 215))
        surf.blit(v, (0, 0))
        glow.dim(0.1)
        if self.help:
            self.draw_help(surf, glow, mouse)
            return
        rect = pygame.Rect(T.W / 2 - 300, 80, 600, 520)
        gfx.panel(surf, rect, T.CYAN, T.PANEL, cut=16, width=2)
        gfx.text(surf, "OPÇÕES", (rect.centerx, rect.y + 34), 36, T.CYAN, "title", anchor="center", glow=glow)
        x, y = rect.x + 40, rect.y + 80
        for label, which, key in (("Efeitos sonoros", "efeitos", "volume"), ("Música", "musica", "music")):
            value = self.settings.get(key, 0.5)
            gfx.text(surf, label, (x, y + 8), 20, T.TEXT, "bold")
            ui.button(surf, self.clicks, (x + 230, y, 40, 36), "-", lambda w=which: self.volume(w, -0.1), mouse,
                      size=22)
            gfx.bar(surf, (x + 282, y + 12, 180, 12), value, T.CYAN, glow=glow)
            ui.button(surf, self.clicks, (x + 474, y, 40, 36), "+", lambda w=which: self.volume(w, 0.1), mouse,
                      size=22)
            gfx.text(surf, f"{int(value * 100)}%", (x + 282 + 90, y - 12), 14, T.DIM, "mono", anchor="center")
            y += 56
        full = self.settings.get("fullscreen", False)
        gfx.text(surf, "Tela cheia (F11)", (x, y + 8), 20, T.TEXT, "bold")
        ui.button(surf, self.clicks, (x + 330, y, 184, 36), "LIGADA" if full else "DESLIGADA",
                  self.app.toggle_fullscreen, mouse, col=T.YELLOW if full else T.CYAN, size=17)
        y += 56
        shake = self.settings.get("shake", True)
        gfx.text(surf, "Tremor de tela", (x, y + 8), 20, T.TEXT, "bold")
        ui.button(surf, self.clicks, (x + 330, y, 184, 36), "LIGADO" if shake else "DESLIGADO", self.toggle_shake,
                  mouse, col=T.YELLOW if shake else T.CYAN, size=17)
        y += 70
        ui.button(surf, self.clicks, (x, y, 514, 46), "CONTROLES E AJUDA", lambda: setattr(self, "help", True), mouse,
                  size=18)
        y += 58
        if self.in_dive:
            gfx.text(surf, "Apagar o save só no esconderijo.", (x, y + 12), 15, T.FAINT)
        else:
            label = "CONFIRMAR: APAGAR TUDO E RECOMEÇAR" if self.armed else "APAGAR O SAVE"
            ui.button(surf, self.clicks, (x, y, 514, 46), label, self.reset, mouse, col=T.RED, size=17,
                      sub="o save atual fica guardado como cópia" if self.armed else None)
        y += 58
        ui.button(surf, self.clicks, (x, y, 250, 46), "SAIR DO JOGO", self.app.quit, mouse, col=T.RED, size=17)
        ui.button(surf, self.clicks, (x + 264, y, 250, 46), "VOLTAR (ESC)", self.close, mouse, size=17)

    def draw_help(self, surf, glow, mouse):
        rect = pygame.Rect(60, 50, T.W - 120, T.H - 100)
        gfx.panel(surf, rect, T.CYAN, T.PANEL, cut=16, width=2)
        gfx.text(surf, "CONTROLES E AJUDA", (rect.x + 30, rect.y + 18), 30, T.CYAN, "title", glow=glow)
        y = rect.y + 70
        for title, lines in HELP:
            gfx.text(surf, title, (rect.x + 30, y), 18, T.YELLOW, "bold")
            y += 28
            for line in lines:
                gfx.text(surf, line, (rect.x + 40, y), 16, T.TEXT)
                y += 22
            y += 14
        ui.button(surf, self.clicks, (rect.right - 220, rect.bottom - 64, 190, 44), "VOLTAR (ESC)",
                  lambda: setattr(self, "help", False), mouse, size=17)
