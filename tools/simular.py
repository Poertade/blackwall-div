"""O robô de balanceamento: joga uma carreira inteira e mede o ritmo.

    python tools/simular.py [carreiras] [--detalhes] [--caminho=solo|equipe|netwatch]

Cada carreira começa do zero. O robô mergulha na camada mais funda que ainda não venceu, joga com uma
estratégia simples (foge do ICE mais perto, lança o hack pronto no melhor alvo), volta, gasta o Ed
(deck maior, hacks novos, a árvore) e mergulha de novo. No fim mostra quantos mergulhos e quantos
minutos de jogo cada camada levou. Uma pessoa costuma ir melhor que o robô nas builds e pior na mira.
"""

import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from blackwall.content import load  # noqa: E402
from blackwall.meta import profile as pf  # noqa: E402
from blackwall.meta import story  # noqa: E402
from blackwall.sim.dive import Dive, DiveInput  # noqa: E402

STEP = 1 / 30
AREA = {"ping", "sonic_shock", "detonate_grenade", "weapon_glitch", "contagion", "blackwall_gateway"}
BIG = {"synapse_burnout", "system_collapse", "system_reset", "cyberpsychosis"}


def neighbours(dive, e, radius=120):
    r2 = radius * radius
    return sum(1 for o in dive.enemies if (o.x - e.x) ** 2 + (o.y - e.y) ** 2 <= r2)


def choose_target(dive, hid):
    p = dive.player
    alive = [e for e in dive.enemies if not e.dead]
    if not alive:
        return None
    if hid in AREA:
        return max(alive, key=lambda e: neighbours(dive, e) - ((e.x - p.x) ** 2 + (e.y - p.y) ** 2) / 4e5)
    if hid in BIG:
        return max(alive, key=lambda e: e.hp)
    return min(alive, key=lambda e: (e.x - p.x) ** 2 + (e.y - p.y) ** 2)


def bot_input(dive, t, rng):
    p = dive.player
    # foge: soma dos empurrões de cada ameaça perto (ICE e tiros)
    fx, fy = 0.0, 0.0
    for e in dive.enemies:
        dx, dy = p.x - e.x, p.y - e.y
        d2 = dx * dx + dy * dy + 1
        if d2 < 260 ** 2:
            w = (3.0 if e.boss else 1.0) / d2
            fx += dx * w
            fy += dy * w
    for b in dive.bullets:
        dx, dy = p.x - b.x, p.y - b.y
        d2 = dx * dx + dy * dy + 1
        if d2 < 120 ** 2:
            fx += dx * 2 / d2
            fy += dy * 2 / d2
    for z in dive.zones:
        if z.kind == "puddle":
            dx, dy = p.x - z.x, p.y - z.y
            d2 = dx * dx + dy * dy + 1
            if d2 < (z.radius + 40) ** 2:
                fx += dx * 2 / d2
                fy += dy * 2 / d2
    # puxa de leve para o centro e para o Ed
    cx, cy = dive.W / 2 - p.x, dive.H / 2 - p.y
    fx += cx * 2e-6
    fy += cy * 2e-6
    if dive.pickups and (fx * fx + fy * fy) < 1e-5:
        pk = min(dive.pickups, key=lambda k: (k.x - p.x) ** 2 + (k.y - p.y) ** 2)
        fx += (pk.x - p.x) * 1e-5
        fy += (pk.y - p.y) * 1e-5
    n = math.hypot(fx, fy)
    move = (p.x + fx / n * 80, p.y + fy / n * 80) if n > 1e-7 else None
    cast = ()
    aim = (p.x, p.y)
    for i, slot in enumerate(dive.slots):
        if not slot.hack or slot.cooldown > 0 or dive.c.hacks[slot.hack]["kind"] == "movimento":
            continue
        target = choose_target(dive, slot.hack)
        if target is None:
            break
        if p.ram < dive.slot_cost(i, target):
            continue
        h = dive.c.hacks[slot.hack]
        if h["kind"] == "supremo" and len(dive.enemies) < 6 and not target.boss:
            continue
        if slot.hack == "ping" and neighbours(dive, target, 200) < 3:
            continue
        cast = (i,)
        aim = (target.x + rng.uniform(-6, 6), target.y + rng.uniform(-6, 6))
        break
    if cast:
        return DiveInput(aim=aim, cast=cast)       # mira e lança (parada neste passo)
    walk = dive.move_slot()
    if move is None or walk is None:
        return DiveInput(aim=aim)
    return DiveInput(aim=move, held=(walk,))      # anda segurando o Andar


def pick_up(dive):
    """Escolhe o up que mais reforça a tag mais pegada (ou a do primeiro hack)."""
    c = dive.c
    counts = dive.counts
    deck_tags = [t for h in dive.cfg.loadout if h for t in c.hacks[h]["tags"]]
    best, best_score = 0, -1
    for i, up_id in enumerate(dive.offer):
        tags = c.ups[up_id]["tags"]
        score = max([counts[t] * 2 + deck_tags.count(t) for t in tags] or [1.5])
        score += {"comum": 0, "raro": 1, "epico": 2}[c.ups[up_id]["rarity"]]
        if score > best_score:
            best, best_score = i, score
    return best


def play_dive(content, profile, mode, layer, seed):
    rng = random.Random(seed)
    dive = Dive(content, pf.dive_config(profile, content, mode, layer, seed))
    t = 0.0
    while dive.phase != "over" and t < 3600:
        if dive.phase == "choice":
            dive.choose(pick_up(dive))
            continue
        dive.step(STEP, bot_input(dive, t, rng))
        dive.events.clear()
        t += STEP
    return dive, t


# A ordem em que o robô prefere os hacks (o que rende mais dano por RAM primeiro)
PREFERENCE = ["contagion", "short_circuit", "overheat", "blackwall_gateway", "synapse_burnout", "detonate_grenade",
              "sonic_shock", "system_collapse", "cripple_movement", "ping", "weapon_glitch", "cyberpsychosis",
              "reboot_optics", "system_reset", "memory_wipe"]


def arrange(profile, content):
    slots = content.decks[profile.deck]["slots"]
    owned = [h for h in PREFERENCE if h in profile.hacks]
    profile.loadout = (["andar"] + owned + [None] * slots)[:slots]


def spend(profile, content):
    """Gasta o Ed: um deck com mais slots, um hack que entraria no deck, depois a árvore (o nó mais barato)."""
    while True:
        bought = False
        shop = pf.shop(profile, content)
        slots = content.decks[profile.deck]["slots"]
        for did in shop["decks"]:
            if content.decks[did]["slots"] > slots and pf.buy_deck(profile, content, did):
                bought = True
                break
        if not bought:
            wanted = [h for h in PREFERENCE][:slots]
            for hid in wanted:
                if hid in shop["hacks"] and pf.buy_hack(profile, content, hid):
                    bought = True
                    break
        if not bought:
            options = [(pf.tree_cost(content, n, pf.tree_level(profile, n)), "tree", None, n) for n in content.tree
                       if pf.tree_status(profile, content, n)[0]]
            for h in profile.loadout:
                for n in content.hack_trees.get(h or "", {}):
                    if pf.hack_node_status(profile, content, h, n)[0]:
                        cost = pf.hack_node_cost(content, h, n, pf.hack_level(profile, h, n))
                        options.append((cost, "hack", h, n))
            if options:
                _cost, kind, h, n = min(options)
                if kind == "tree":
                    pf.buy_tree(profile, content, n)
                else:
                    pf.buy_hack_node(profile, content, h, n)
                bought = True
        if not bought:
            return


def career(content, seed, details=False, max_dives=120, path="solo"):
    profile = pf.new_profile(content)
    minutes = 0.0
    marks = []
    dives = 0
    while profile.layers_cleared < len(content.layers) and dives < max_dives:
        layer = profile.layers_cleared
        dive, t = play_dive(content, profile, "layer", layer, seed * 1000 + dives)
        dives += 1
        minutes += t / 60 + 0.5          # meio minuto no esconderijo
        summary = pf.apply_result(profile, content, dive)
        if details:
            print(f"  mergulho {dives:3d}: camada {layer + 1} {dive.result:9s} onda {dive.wave:2d} "
                  f"{t / 60:4.1f} min  +{summary['ed']} Ed  árvore {sum(profile.tree.values())}  "
                  f"deck {profile.deck} {profile.loadout}")
        if profile.layers_cleared > layer:
            marks.append((profile.layers_cleared, dives, minutes))
        if story.needs_path_choice(profile):
            pf.choose_path(profile, content, path)
        spend(profile, content)
        arrange(profile, content)
    return marks, dives, minutes


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    runs = int(args[0]) if args else 3
    details = "--detalhes" in sys.argv
    path = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--caminho=")), "solo")
    content = load()
    table = {}
    for seed in range(1, runs + 1):
        if details:
            print(f"carreira {seed}")
        marks, dives, minutes = career(content, seed, details, path=path)
        for layer, d, m in marks:
            table.setdefault(layer, []).append((d, m))
        print(f"carreira {seed}: {len(marks)} camadas em {dives} mergulhos, {minutes:.0f} min")
    print("\ncamada  mergulhos  minutos (média de quem chegou)")
    for layer in sorted(table):
        rows = table[layer]
        d = sum(r[0] for r in rows) / len(rows)
        m = sum(r[1] for r in rows) / len(rows)
        print(f"{layer:6d}  {d:9.1f}  {m:7.0f}   ({len(rows)}/{runs})")


if __name__ == "__main__":
    main()
