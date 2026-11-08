"""O esconderijo: o que fica de um mergulho para o outro (Ed, árvore, hacks, decks, camadas, caminho).

Sem tela: a interface chama estas funções, e os testes também. O salvamento está em meta/save.py.
"""

import time
from dataclasses import dataclass, field

from blackwall.meta import story
from blackwall.sim.dive import DiveConfig
from blackwall.sim.stats import Mods

START_DECK = "paraline"


@dataclass
class Profile:
    ed: int = 0
    tree: dict = field(default_factory=dict)          # nó -> nível
    hack_trees: dict = field(default_factory=dict)    # hack -> {nó -> nível}
    hacks: list = field(default_factory=list)         # os quickhacks que você tem
    decks: list = field(default_factory=lambda: [START_DECK])
    deck: str = START_DECK
    loadout: list = field(default_factory=list)       # o hack de cada slot (None = vazio)
    layers_cleared: int = 0
    best_infinite: int = 0
    path: str | None = None                           # solo, equipe ou netwatch (a quest line)
    quest: dict = field(default_factory=dict)
    stats: dict = field(default_factory=lambda: {"dives": 0, "kills": 0, "ed_total": 0, "flatlines": 0,
                                                  "victories": 0})
    last_seen: float = field(default_factory=time.time)
    settings: dict = field(default_factory=lambda: {"volume": 0.7, "music": 0.35, "fullscreen": False,
                                                     "shake": True})


def new_profile(content) -> Profile:
    starting = [h for h, d in content.hacks.items() if d["price"] == 0]
    starting.sort(key=lambda h: content.hacks[h]["kind"] != "movimento")   # o movimento no slot 1
    slots = content.decks[START_DECK]["slots"]
    loadout = (starting + [None] * slots)[:slots]
    return Profile(hacks=list(starting), loadout=loadout)


# --- a árvore --------------------------------------------------------------
def tree_cost(content, node: str, level: int) -> int:
    n = content.tree[node]
    return int(round(n["cost"] * n["growth"] ** level))


def tree_level(profile: Profile, node: str) -> int:
    return profile.tree.get(node, 0)


def tree_status(profile: Profile, content, node: str) -> tuple:
    """(pode comprar?, motivo). O motivo aparece na tela quando não pode."""
    n = content.tree[node]
    level = tree_level(profile, node)
    if level >= n["max"]:
        return False, "no máximo"
    req = n.get("requires")
    if req and tree_level(profile, req) < 1:
        return False, f"precisa de {content.tree[req]['name']}"
    cost = tree_cost(content, node, level)
    if profile.ed < cost:
        return False, f"faltam {cost - profile.ed} Ed"
    return True, ""


def buy_tree(profile: Profile, content, node: str) -> bool:
    ok, _ = tree_status(profile, content, node)
    if not ok:
        return False
    profile.ed -= tree_cost(content, node, tree_level(profile, node))
    profile.tree[node] = tree_level(profile, node) + 1
    return True


# --- as árvores dos quickhacks -------------------------------------------------
def visible(level_of, nodes: dict, node: str) -> bool:
    """Um nó só aparece quando o nó que ele pede já tem nível (os outros ficam ocultos)."""
    req = nodes[node].get("requires")
    return not req or level_of(req) > 0


def hack_level(profile: Profile, hack: str, node: str) -> int:
    return profile.hack_trees.get(hack, {}).get(node, 0)


def hack_node_cost(content, hack: str, node: str, level: int) -> int:
    n = content.hack_trees[hack][node]
    return int(round(n["cost"] * n.get("growth", 1.8) ** level))


def hack_node_status(profile: Profile, content, hack: str, node: str) -> tuple:
    if hack not in profile.hacks:
        return False, "você não tem esse quickhack"
    n = content.hack_trees[hack][node]
    level = hack_level(profile, hack, node)
    if level >= n["max"]:
        return False, "no máximo"
    req = n.get("requires")
    if req and hack_level(profile, hack, req) < 1:
        return False, f"precisa de {content.hack_trees[hack][req]['name']}"
    cost = hack_node_cost(content, hack, node, level)
    if profile.ed < cost:
        return False, f"faltam {cost - profile.ed} Ed"
    return True, ""


def buy_hack_node(profile: Profile, content, hack: str, node: str) -> bool:
    ok, _ = hack_node_status(profile, content, hack, node)
    if not ok:
        return False
    level = hack_level(profile, hack, node)
    profile.ed -= hack_node_cost(content, hack, node, level)
    profile.hack_trees.setdefault(hack, {})[node] = level + 1
    return True


# --- a loja ----------------------------------------------------------------
def deck_available(profile: Profile, content, deck_id: str) -> bool:
    d = content.decks[deck_id]
    if d.get("path"):
        return profile.path == d["path"]
    return profile.layers_cleared >= d.get("requires_layer", 0)


def shop(profile: Profile, content) -> dict:
    """O que a loja oferece agora: {'hacks': [...], 'decks': [...]}, do mais barato ao mais caro."""
    hacks = sorted((h for h, d in content.hacks.items() if h not in profile.hacks),
                   key=lambda h: content.hacks[h]["price"])
    decks = sorted((d for d in content.decks if d not in profile.decks and deck_available(profile, content, d)
                    and not content.decks[d].get("path")),
                   key=lambda d: content.decks[d]["price"])
    return {"hacks": hacks, "decks": decks}


def buy_hack(profile: Profile, content, hack_id: str) -> bool:
    if hack_id in profile.hacks:
        return False
    price = content.hacks[hack_id]["price"]
    if profile.ed < price:
        return False
    profile.ed -= price
    profile.hacks.append(hack_id)
    _fill_empty_slot(profile, hack_id)
    return True


def buy_deck(profile: Profile, content, deck_id: str) -> bool:
    if deck_id in profile.decks or not deck_available(profile, content, deck_id):
        return False
    price = content.decks[deck_id]["price"]
    if profile.ed < price:
        return False
    profile.ed -= price
    profile.decks.append(deck_id)
    if content.decks[deck_id]["slots"] > content.decks[profile.deck]["slots"]:
        set_deck(profile, content, deck_id)
    return True


# --- o deck e os slots ------------------------------------------------------
def set_deck(profile: Profile, content, deck_id: str) -> bool:
    if deck_id not in profile.decks:
        return False
    slots = content.decks[deck_id]["slots"]
    current = [h for h in profile.loadout if h]
    extra = [h for h in profile.hacks if h not in current]
    profile.deck = deck_id
    profile.loadout = (current + extra + [None] * slots)[:slots]
    return True


def set_slot(profile: Profile, index: int, hack_id: str | None) -> bool:
    if not 0 <= index < len(profile.loadout):
        return False
    if hack_id is not None and hack_id not in profile.hacks:
        return False
    if hack_id in profile.loadout:
        other = profile.loadout.index(hack_id)
        profile.loadout[other] = profile.loadout[index]
    profile.loadout[index] = hack_id
    return True


def _fill_empty_slot(profile: Profile, hack_id: str):
    if None in profile.loadout:
        profile.loadout[profile.loadout.index(None)] = hack_id


# --- o mergulho -------------------------------------------------------------
PATH_MODS = {
    "solo": {"stats": {"damage": 0.25, "hp": 20}, "flags": {"lone_wolf": 0.05}},
    "equipe": {"stats": {"damage": 0.05, "hp": 5}},
    "netwatch": {"stats": {"damage": 0.12, "hp": 10}},
}


def permanent_mods(profile: Profile, content) -> Mods:
    """A árvore, o deck e o caminho da história, somados."""
    mods = Mods()
    for node, level in profile.tree.items():
        if node in content.tree and level > 0:
            mods.add({"stats": content.tree[node]["per_level"]}, level)
    for hack, nodes in profile.hack_trees.items():
        for node, level in nodes.items():
            if hack in content.hack_trees and node in content.hack_trees[hack] and level > 0:
                mods.add(content.hack_trees[hack][node]["effect"], level)
    mods.add(content.decks[profile.deck].get("mods") or {})
    if profile.path in PATH_MODS:
        mods.add(PATH_MODS[profile.path])
    return mods


def available_layers(profile: Profile, content) -> int:
    """Quantas camadas dá para mergulhar (as vencidas e a próxima).

    Depois da 1ª camada, a 2ª só abre quando você escolhe o caminho (aba HISTÓRIA)."""
    if profile.path is None:
        return 1
    return min(len(content.layers), profile.layers_cleared + 1)


def choose_path(profile: Profile, content, path: str) -> bool:
    if not story.choose_path(profile, content, path):
        return False
    deck = content.story.get("path_decks", {}).get(path)
    if deck and deck not in profile.decks:
        profile.decks.append(deck)
        set_deck(profile, content, deck)
    return True


def infinite_unlocked(profile: Profile) -> bool:
    return profile.layers_cleared >= 1


def dive_config(profile: Profile, content, mode: str = "layer", layer: int = 0, seed: int | None = None,
                mission: dict | None = None):
    return DiveConfig(
        mode=mode,
        layer=mission["layer"] if mission else layer,
        loadout=list(profile.loadout),
        deck=profile.deck,
        mods=permanent_mods(profile, content),
        seed=seed if seed is not None else int(time.time() * 1000) % 2_000_000_000,
        choices=4 if profile.path == "solo" else 0,
        mission=mission,
        allies=story.allies_for_dive(profile, content),
        ally_pickup=content.story["income"]["pickup"] if profile.path == "equipe" else 0.0,
    )


def apply_result(profile: Profile, content, dive) -> dict:
    """Leva o resultado do mergulho para o esconderijo. Devolve o resumo para a tela."""
    gained = dive.ed_final
    summary = {"result": dive.result, "ed": gained, "lost": int(dive.ed) - gained, "wave": dive.wave,
               "kills": dive.kills, "unlocked": [], "reward_ed": 0, "reward_hack": None, "record": False,
               "reward_deck": None, "reward_ally": None, "ending": None, "mission": None}
    profile.ed += gained
    profile.stats["dives"] += 1
    profile.stats["kills"] += dive.kills
    profile.stats["ed_total"] += gained
    if dive.result == "flatline":
        profile.stats["flatlines"] += 1
    cfg = dive.cfg
    if cfg.mode == "mission":
        summary["mission"] = cfg.mission["id"]
        if dive.result == "victory":
            reward = story.mission_reward(profile, content, cfg.mission)
            summary["reward_ed"] = reward["ed"]
            summary["reward_hack"] = reward["hack"]
            summary["reward_deck"] = reward["deck"]
            summary["reward_ally"] = reward["ally"]
    elif cfg.mode == "infinite":
        reached = dive.waves_cleared
        if reached > profile.best_infinite:
            profile.best_infinite = reached
            summary["record"] = True
    elif dive.result == "victory":
        profile.stats["victories"] += 1
        layer = content.layers[cfg.layer]
        if cfg.layer == profile.layers_cleared:
            profile.layers_cleared += 1
            reward = layer.get("reward", {})
            bonus = reward.get("ed", 0)
            hack = reward.get("hack")
            if hack and hack in profile.hacks:
                bonus += content.hacks[hack]["price"] // 2
                hack = None
            if hack:
                profile.hacks.append(hack)
                _fill_empty_slot(profile, hack)
                summary["reward_hack"] = hack
            profile.ed += bonus
            summary["reward_ed"] = bonus
            if profile.layers_cleared < len(content.layers):
                summary["unlocked"].append(content.layers[profile.layers_cleared]["name"])
            if profile.layers_cleared == 1:
                summary["unlocked"].append("Ondas infinitas")
                summary["unlocked"].append("A escolha do caminho (aba HISTÓRIA)")
            if profile.layers_cleared == len(content.layers) and profile.path:
                story.quest(profile)["ending"] = profile.path
                summary["ending"] = profile.path
    return summary
