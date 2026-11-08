"""Tira fotos das telas sem abrir janela (para conferir o visual e para o README).

    python tools/capturas.py [pasta]      (padrão: docs/capturas)

Um robô simples joga alguns segundos de cada situação: o esconderijo, uma onda, a escolha de
ups, um chefe e o fim do mergulho.
"""

import math
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

from blackwall.game.app import App  # noqa: E402
from blackwall.game.scene_dive import DiveScene  # noqa: E402
from blackwall.game.scene_hideout import HideoutScene  # noqa: E402
from blackwall.meta import profile as pf  # noqa: E402
from blackwall.sim.dive import DiveInput  # noqa: E402


def bot_input(dive, t):
    """Anda em círculos longe dos ICE e lança o que estiver pronto no mais perto (o slot 0 é o Andar)."""
    p = dive.player
    near = [e for e in dive.enemies if (e.x - p.x) ** 2 + (e.y - p.y) ** 2 < 220 ** 2]
    move = (dive.W / 2 + math.cos(t * 0.6) * 380, dive.H / 2 + math.sin(t * 0.6) * 180)
    if near:
        cx = sum(e.x for e in near) / len(near)
        cy = sum(e.y for e in near) / len(near)
        dx, dy = p.x - cx, p.y - cy
        n = math.hypot(dx, dy) or 1
        move = (p.x + dx / n * 100, p.y + dy / n * 100)
    target = min(dive.enemies, key=lambda e: (e.x - p.x) ** 2 + (e.y - p.y) ** 2, default=None)
    cast = ()
    if target and int(t * 10) % 3 == 0:
        for i, s in enumerate(dive.slots):
            if s.hack and dive.c.hacks[s.hack]["kind"] != "movimento" and s.cooldown <= 0 \
                    and p.ram >= dive.slot_cost(i, target):
                cast = (i,)
                break
    if cast:
        return DiveInput(aim=(target.x, target.y), cast=cast)
    return DiveInput(aim=move, held=(0,))


def play(app, scene, seconds, mouse=None):
    dive = scene.dive
    t = 0.0
    step = 1 / 60
    while t < seconds and dive.phase == "wave":
        inp = bot_input(dive, t)
        dive.step(step, inp)
        for name in scene.fx.handle(dive.take_events(), dive, app.content):
            pass
        scene.fx.update(step)
        scene.bg.update(step)
        scene.t += step
        t += step
    if mouse:
        pygame.mouse.set_pos(mouse)


def shot(app, path):
    app.glow.begin()
    app.scene.draw(app.screen, app.glow)
    app.glow.apply(app.screen)
    pygame.image.save(app.screen, str(path))
    print(path)


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "docs" / "capturas")
    out.mkdir(parents=True, exist_ok=True)
    app = App(save_dir=tempfile.mkdtemp())
    c = app.content
    p = app.profile
    p.ed = 2450
    p.layers_cleared = 1
    p.tree = {"dano": 3, "integridade": 4, "ram": 2, "critico": 1, "coleta": 2}
    p.hacks += ["overheat", "contagion", "synapse_burnout", "cripple_movement", "sonic_shock"]
    p.decks += ["biotech", "raven"]
    pf.set_deck(p, c, "raven")
    p.hacks += ["kerenzikov"]
    p.loadout = ["andar", "short_circuit", "contagion", "overheat", "sonic_shock"]
    p.hack_trees = {"contagion": {"mutacao": 2, "carga_viral": 1}, "short_circuit": {"arco_extra": 1}}
    from blackwall.meta import story
    p.quest["read"] = []
    app.switch(HideoutScene(app, tab="historia"))
    pygame.mouse.set_pos((900, 360))
    shot(app, out / "historia-encruzilhada.png")
    pf.choose_path(p, c, "equipe")
    story.quest(p)["team"]["ruido"] = 2
    for tab in ("mergulho", "historia", "deck", "loja", "arvore"):
        app.switch(HideoutScene(app, tab=tab))
        pygame.mouse.set_pos((300, 200) if tab != "arvore" else (240, 260))
        shot(app, out / f"esconderijo-{tab}.png")
    scene = HideoutScene(app, tab="arvore")
    scene.tree_sel = "contagion"
    app.switch(scene)
    pygame.mouse.set_pos((360, 300))
    shot(app, out / "arvore-contagion.png")
    scene = HideoutScene(app, tab="historia")
    app.switch(scene)
    scene.open_channel("_team")
    shot(app, out / "historia-equipe.png")
    # uma missão da equipe: o download
    scene = DiveScene(app, pf.dive_config(p, c, "mission", seed=5, mission=c.mission("equipe_1")),
                      c.mission("equipe_1")["name"])
    app.switch(scene)
    scene.dive.start_wave(3)
    play(app, scene, 14)
    shot(app, out / "missao-download.png")
    # uma onda no meio
    scene = DiveScene(app, pf.dive_config(p, c, "layer", 0, seed=11), c.layers[0]["name"])
    app.switch(scene)
    scene.dive.taken.update({"virulencia": 2, "carga_toxica": 1, "condutividade": 1})
    scene.dive.recompute()
    scene.dive.start_wave(5)
    play(app, scene, 16)
    e = scene.dive.enemies[0] if scene.dive.enemies else None
    if e:
        pygame.mouse.set_pos((int(e.x + scene.ox), int(e.y + scene.oy)))
    shot(app, out / "mergulho-onda.png")
    # a escolha de ups
    play(app, scene, 60)
    if scene.dive.phase == "choice":
        pygame.mouse.set_pos((640, 300))
        shot(app, out / "mergulho-ups.png")
    # o chefe
    scene = DiveScene(app, pf.dive_config(p, c, "layer", 1, seed=4), c.layers[1]["name"])
    app.switch(scene)
    scene.dive.taken.update({"capacitor": 2, "pico_tensao": 1, "amplificador": 1})
    scene.dive.recompute()
    scene.dive.start_wave(10)
    play(app, scene, 9)
    shot(app, out / "mergulho-chefe.png")
    # o fim
    scene.dive.ed = 380
    scene.dive.abort()
    scene.update(0.016)
    shot(app, out / "mergulho-fim.png")
    pygame.quit()


if __name__ == "__main__":
    main()
