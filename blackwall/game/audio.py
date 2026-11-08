"""Os sons, sintetizados na hora (sem arquivos): bipes, choques, explosões e um zumbido de fundo.

Se o computador não tiver som (ou o mixer falhar), o jogo segue mudo."""

import math
import random
import time
from array import array

import pygame

RATE = 22050


def _env(i, n, attack=0.01, release=0.6):
    t = i / n
    if t < attack:
        return t / attack
    return max(0.0, 1 - (t - attack) / max(1e-6, 1 - attack)) ** (1 / max(0.05, release))


def _tone(seconds, f0, f1=None, wave="sine", noise=0.0, volume=0.5, release=0.6, seed=1):
    rng = random.Random(seed)
    n = int(RATE * seconds)
    f1 = f0 if f1 is None else f1
    buf = array("h")
    phase = 0.0
    for i in range(n):
        t = i / n
        f = f0 + (f1 - f0) * t
        phase += f / RATE
        x = phase % 1.0
        if wave == "sine":
            v = math.sin(math.tau * x)
        elif wave == "square":
            v = 1.0 if x < 0.5 else -1.0
        elif wave == "saw":
            v = 2 * x - 1
        else:
            v = 1 - 4 * abs(x - 0.5)
        if noise:
            v = v * (1 - noise) + rng.uniform(-1, 1) * noise
        buf.append(int(v * _env(i, n, release=release) * volume * 32767))
    return buf


def _mix(*bufs):
    n = max(len(b) for b in bufs)
    out = array("h", [0] * n)
    for b in bufs:
        for i, v in enumerate(b):
            out[i] = max(-32767, min(32767, out[i] + v))
    return out


RECIPES = {
    "cast": lambda: _tone(0.08, 900, 1500, "square", volume=0.18, release=0.4),
    "zap": lambda: _tone(0.12, 1800, 500, "saw", noise=0.5, volume=0.18, release=0.5),
    "hit": lambda: _tone(0.05, 300, 120, "triangle", noise=0.4, volume=0.25),
    "kill": lambda: _tone(0.14, 600, 90, "square", noise=0.3, volume=0.18),
    "hurt": lambda: _tone(0.22, 180, 60, "saw", noise=0.5, volume=0.35),
    "pickup": lambda: _tone(0.07, 1400, 2100, "sine", volume=0.15, release=0.3),
    "denied": lambda: _tone(0.12, 140, 120, "square", volume=0.15),
    "drained": lambda: _tone(0.4, 900, 120, "saw", noise=0.2, volume=0.25),
    "wave": lambda: _mix(_tone(0.35, 440, 440, "square", volume=0.12), _tone(0.35, 660, 660, "square", volume=0.08)),
    "clear": lambda: _mix(_tone(0.25, 660, 990, "triangle", volume=0.2), _tone(0.4, 990, 1320, "sine", volume=0.15)),
    "boss": lambda: _tone(1.0, 70, 45, "saw", noise=0.15, volume=0.4, release=0.9),
    "blast": lambda: _tone(0.5, 120, 30, "triangle", noise=0.8, volume=0.45, release=0.8),
    "up": lambda: _tone(0.18, 700, 1400, "sine", volume=0.25),
    "flatline": lambda: _tone(1.4, 1000, 1000, "sine", volume=0.25, release=0.95),
    "victory": lambda: _mix(_tone(0.6, 523, 523, "triangle", volume=0.2), _tone(0.6, 659, 659, "triangle", volume=0.15),
                            _tone(0.8, 784, 1046, "sine", volume=0.15)),
    "execute": lambda: _tone(0.2, 2000, 200, "square", volume=0.15),
    "click": lambda: _tone(0.04, 1200, 900, "square", volume=0.12),
    "buy": lambda: _mix(_tone(0.1, 900, 900, "square", volume=0.1), _tone(0.2, 1350, 1800, "sine", volume=0.15)),
}


# Estes tomam o canal de um som mais velho se todos estiverem ocupados
IMPORTANT = {"cast", "hurt", "boss", "wave", "clear", "victory", "flatline", "denied", "drained", "up", "blast"}


class Audio:
    def __init__(self, volume=0.7):
        global RATE
        self.volume = volume
        self.sounds = {}
        self.ok = False
        self.cooldown = {}
        self.channels = 1
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(RATE, -16, 1, 512)
            # 8 canais (o padrão) acabam no meio de uma onda cheia e os efeitos somem por um tempo
            pygame.mixer.set_num_channels(32)
            freq, _fmt, channels = pygame.mixer.get_init()
            RATE = freq
            self.channels = channels
            self.ok = True
        except (pygame.error, TypeError):
            self.ok = False

    def _get(self, name):
        if name not in self.sounds:
            try:
                buf = RECIPES[name]()
                if self.channels > 1:
                    wide = array("h")
                    for v in buf:
                        wide.extend([v] * self.channels)
                    buf = wide
                self.sounds[name] = pygame.mixer.Sound(buffer=buf.tobytes())
            except (pygame.error, KeyError):
                self.sounds[name] = None
        return self.sounds[name]

    def play(self, name, now=None):
        """Toca um efeito. O intervalo mínimo entre dois iguais usa um relógio que nunca volta.

        (Antes usava o relógio da tela, que zera a cada mergulho: os sons que tinham tocado no mergulho
        anterior ficavam mudos até o relógio novo passar do antigo. O `now` fica só por compatibilidade.)"""
        if not self.ok or self.volume <= 0:
            return False
        now = time.monotonic()
        if now - self.cooldown.get(name, -1.0) < 0.04:
            return False
        self.cooldown[name] = now
        sound = self._get(name)
        if sound is not None:
            sound.set_volume(self.volume)
            channel = pygame.mixer.find_channel(name in IMPORTANT)
            if channel is not None:
                channel.play(sound)
                return True
        return False
