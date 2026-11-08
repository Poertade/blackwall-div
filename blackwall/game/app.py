"""A janela, o relógio e a troca de telas.

    python main.py                 joga
    python main.py --sair-apos 5   abre, roda 5 segundos e fecha (o teste de fumaça do executável)
"""

import argparse
import os
import sys

import pygame

from blackwall import content as content_mod
from blackwall.game import gfx
from blackwall.game import theme as T
from blackwall.game.audio import Audio
from blackwall.game.music import Music
from blackwall.meta import save as save_mod
from blackwall.meta import story


def make_icon() -> pygame.Surface:
    s = pygame.Surface((64, 64), pygame.SRCALPHA)
    pts = gfx.regular((32, 32), 26, 4, 0)
    pygame.draw.polygon(s, (10, 40, 50), pts)
    pygame.draw.polygon(s, T.CYAN, pts, 4)
    pygame.draw.circle(s, T.YELLOW, (32, 32), 7)
    return s


class App:
    def __init__(self, save_dir=None, windowed=True):
        # a tela lógica é 1280x720; em tela cheia o SDL escala com filtro linear (sem pixelizar)
        os.environ.setdefault("SDL_RENDER_SCALE_QUALITY", "1")
        os.environ.setdefault("SDL_HINT_RENDER_SCALE_QUALITY", "1")
        pygame.mixer.pre_init(22050, -16, 2, 512)
        pygame.init()
        T.reset_fonts()
        pygame.display.set_caption("Blackwall Dive")
        try:
            pygame.display.set_icon(make_icon())
        except pygame.error:
            pass
        self.save_dir = save_dir
        self.content = content_mod.load()
        self.profile = save_mod.load(self.content, save_dir)
        self.offline_gain = story.offline_income(self.profile, self.content)
        # SCALED: a tela lógica é 1280x720 e o SDL escala para a janela (o mouse já vem na escala lógica)
        if os.environ.get("SDL_VIDEODRIVER") == "dummy":
            self.screen = pygame.display.set_mode((T.W, T.H))
        else:
            try:
                self.screen = pygame.display.set_mode((T.W, T.H), pygame.SCALED | pygame.RESIZABLE, vsync=1)
            except pygame.error:
                self.screen = pygame.display.set_mode((T.W, T.H))
        if self.profile.settings.get("fullscreen") and not windowed:
            self.toggle_fullscreen()
        self.glow = gfx.Glow((T.W, T.H))
        self.audio = Audio(self.profile.settings.get("volume", 0.7))
        self.music = Music(self.profile.settings.get("music", 0.35))
        self.clock = pygame.time.Clock()
        self.running = True
        self.time = 0.0
        from blackwall.game.scene_hideout import HideoutScene
        # com mensagem nova (a primeira fala da Rhyme, por exemplo), o jogo abre na aba HISTÓRIA
        news = story.unread(self.profile, self.content) or story.needs_path_choice(self.profile)
        self.scene = HideoutScene(self, tab="historia" if news else "mergulho")

    # --- utilidades para as telas --------------------------------------------
    def mouse(self):
        return pygame.mouse.get_pos()

    def logical(self, pos):
        return pos

    def switch(self, scene):
        self.scene = scene

    def save(self):
        try:
            save_mod.save(self.profile, self.save_dir)
        except OSError as err:
            print(f"não deu para salvar: {err}", file=sys.stderr)

    def toggle_fullscreen(self):
        try:
            pygame.display.toggle_fullscreen()
            self.profile.settings["fullscreen"] = not self.profile.settings.get("fullscreen", False)
        except pygame.error:
            pass

    def toggle_music(self):
        self.music.volume = 0.0 if self.music.volume > 0 else 0.35
        self.profile.settings["music"] = self.music.volume

    def toggle_sound(self):
        self.audio.volume = 0.0 if self.audio.volume > 0 else 0.7
        self.profile.settings["volume"] = self.audio.volume

    # --- o laço ---------------------------------------------------------------
    def frame(self, dt):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.quit()
                return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F11 or (event.key == pygame.K_RETURN and event.mod & pygame.KMOD_ALT):
                    self.toggle_fullscreen()
                    continue
                if event.key == pygame.K_F3:
                    self.toggle_music()
                    continue
                if event.key == pygame.K_F2:
                    self.toggle_sound()
                    continue
            self.scene.handle(event)
        self.scene.update(dt)
        self.music.set_mood(getattr(self.scene, "mood", "desktop"))
        self.music.update(dt)
        self.render()

    def render(self):
        self.glow.begin()
        self.scene.draw(self.screen, self.glow)
        self.glow.apply(self.screen)
        pygame.display.flip()

    def quit(self):
        scene = self.scene
        if hasattr(scene, "dive") and scene.dive.phase != "over":
            scene.dive.abort()
            scene.finish()
        self.save()
        self.running = False

    def run(self, exit_after=None):
        while self.running:
            dt = min(0.05, self.clock.tick(60) / 1000)
            self.time += dt
            self.frame(dt)
            if exit_after is not None and self.time >= exit_after:
                self.quit()
        self.music.stop()
        pygame.quit()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Blackwall Dive")
    parser.add_argument("--sair-apos", type=float, default=None, help="fecha sozinho depois de N segundos")
    parser.add_argument("--salvamento", default=None, help="outra pasta para o salvamento")
    parser.add_argument("--tela-cheia", action="store_true", help="abre em tela cheia")
    args = parser.parse_args(argv)
    save_dir = args.salvamento or os.environ.get("BLACKWALL_SAVE_DIR")
    app = App(save_dir=save_dir, windowed=not args.tela_cheia)
    app.run(exit_after=args.sair_apos)
    return 0
