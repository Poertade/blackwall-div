"""A trilha: os três loops do primeiro jogo (o projeto-netrunner), um para cada clima.

    desktop  o esconderijo         desktop_loop.wav      (o apartamento às 3 da manhã, com chuva)
    net      as ondas              malfunction_loop.wav  (a rede "com defeito")
    danger   os chefes e os alvos  danger_loop.wav       (a perseguição a 128 BPM)

A troca de clima é em fade: a trilha atual some em meio segundo e a nova entra em um segundo.
Sem som no computador (ou sem os arquivos), o jogo segue mudo.
"""

import pygame

from blackwall.paths import ASSETS

TRACKS = {"desktop": "desktop_loop.wav", "net": "malfunction_loop.wav", "danger": "danger_loop.wav"}
FADE_OUT = 0.5
FADE_IN = 1.0


class Music:
    def __init__(self, volume: float = 0.35):
        self.volume = volume
        self.current = None      # o clima tocando
        self.target = None       # o clima pedido
        self.fade = 0.0
        self.ok = bool(pygame.mixer.get_init())

    def set_mood(self, mood: str | None):
        if mood in TRACKS or mood is None:
            self.target = mood

    def _start(self, mood):
        self.current = mood
        self.fade = 0.0
        if mood is None:
            pygame.mixer.music.stop()
            return
        try:
            pygame.mixer.music.load(str(ASSETS / "music" / TRACKS[mood]))
            pygame.mixer.music.set_volume(0.0)
            pygame.mixer.music.play(-1)
        except pygame.error:
            self.ok = False

    def update(self, dt: float):
        if not self.ok:
            return
        if self.target != self.current:
            if self.current is None or self.fade <= 0:
                self._start(self.target)
            else:
                self.fade = max(0.0, self.fade - dt / FADE_OUT)
        else:
            self.fade = min(1.0, self.fade + dt / FADE_IN)
        try:
            pygame.mixer.music.set_volume(self.volume * self.fade)
        except pygame.error:
            self.ok = False

    def stop(self):
        if self.ok:
            try:
                pygame.mixer.music.stop()
            except pygame.error:
                pass
