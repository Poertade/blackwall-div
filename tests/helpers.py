"""Ajudantes dos testes: um mergulho sem ondas sorteadas, com ICE postos à mão."""

from blackwall.sim.dive import Dive, DiveConfig, DiveInput


def quiet_dive(content, loadout=("short_circuit", "ping"), mods=None, mode="layer", layer=0, **kw):
    """Um mergulho em que o diretor de ondas não manda ninguém (os testes põem os ICE)."""
    cfg = DiveConfig(mode=mode, layer=layer, loadout=list(loadout), seed=kw.pop("seed", 7), **kw)
    if mods is not None:
        cfg.mods = mods
    dive = Dive(content, cfg)
    dive.plan.pool = {}
    dive.spawns.clear()
    return dive


def put(dive, type_id, x, y, boss=False):
    return dive._spawn_enemy(type_id, x, y, boss)


def run(dive, seconds, inp=None, dt=1 / 60):
    steps = int(round(seconds / dt))
    for _ in range(steps):
        dive.step(dt, inp or DiveInput())


def cast(dive, slot, target, settle=1.5):
    """Lança o hack do slot no alvo e espera o upload chegar (o alvo fica parado se tiver root)."""
    ok = dive.cast(slot, (target.x, target.y))
    run(dive, settle)
    return ok
