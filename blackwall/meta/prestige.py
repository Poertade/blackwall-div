"""O prestígio: Atravessar a Blackwall.

A netrunner apaga a identidade e volta do zero, mais forte:
- **Zera:** o Ed, as árvores, os hacks e decks comprados, as camadas, o caminho da história e a equipe.
- **Fica:** os Fragmentos de Relic, a loja de prestígio, os recordes, as estatísticas e as opções.

Cada fragmento já ganho dá um bônus fixo de dano e de Ed (veja profile.permanent_mods); gastar na loja não
tira o bônus. Os números estão em data/prestige.yaml.
"""

import math

from blackwall.meta import profile as pf


def unlocked(profile, content) -> bool:
    """Dá para atravessar agora (camadas vencidas suficientes nesta vida)."""
    return profile.layers_cleared >= content.prestige["unlock_layers"]


def ever_seen(profile, content) -> bool:
    """A aba do prestígio aparece quando ele abre pela primeira vez (e não some mais)."""
    return unlocked(profile, content) or profile.prestige.get("total", 0) > 0


def fragments_for(profile, content) -> tuple:
    """(total, partes) dos fragmentos que uma travessia agora daria."""
    cfg = content.prestige
    pr = profile.prestige
    parts = {
        "camadas": cfg["per_layer"] * profile.layers_cleared,
        "ed": int(math.sqrt(max(0, pr.get("life_ed", 0)) / cfg["ed_unit"])),
        "infinitas": pr.get("life_best", 0) // cfg["per_waves"],
    }
    return sum(parts.values()), parts


def bonus(profile, content) -> dict:
    """O bônus fixo atual (de todos os fragmentos já ganhos): {damage: 0.4, ed: 0.4}."""
    total = profile.prestige.get("total", 0)
    return {k: v * total for k, v in content.prestige["bonus"].items()}


# --- a loja ----------------------------------------------------------------
def shop_level(profile, item: str) -> int:
    return profile.prestige.get("shop", {}).get(item, 0)


def shop_cost(content, item: str, level: int) -> int:
    d = content.prestige["shop"][item]
    return int(round(d["cost"] * d.get("growth", 1.5) ** level))


def shop_status(profile, content, item: str) -> tuple:
    d = content.prestige["shop"][item]
    level = shop_level(profile, item)
    if level >= d["max"]:
        return False, "no máximo"
    cost = shop_cost(content, item, level)
    if profile.prestige.get("fragments", 0) < cost:
        return False, f"faltam {cost - profile.prestige.get('fragments', 0)} fragmentos"
    return True, ""


def buy(profile, content, item: str) -> bool:
    ok, _ = shop_status(profile, content, item)
    if not ok:
        return False
    level = shop_level(profile, item)
    profile.prestige["fragments"] -= shop_cost(content, item, level)
    profile.prestige.setdefault("shop", {})[item] = level + 1
    return True


# --- a travessia -----------------------------------------------------------
def apply_start(profile, content):
    """O começo de cada vida com o que a loja de prestígio comprou (Ed, deck, hacks, camadas)."""
    for item, level in profile.prestige.get("shop", {}).items():
        d = content.prestige["shop"].get(item)
        if not d or level <= 0:
            continue
        eff = d["effect"]
        profile.ed += eff.get("start_ed", 0) * level
        if eff.get("start_deck") and eff["start_deck"] not in profile.decks:
            profile.decks.append(eff["start_deck"])
            pf.set_deck(profile, content, eff["start_deck"])
        for hack in eff.get("start_hacks", [])[:level]:
            if hack not in profile.hacks:
                profile.hacks.append(hack)
                pf._fill_empty_slot(profile, hack)
        for i in range(eff.get("start_layers", 0) * level):
            if profile.layers_cleared <= i < len(content.layers):
                reward = content.layers[i].get("reward", {})
                profile.ed += reward.get("ed", 0)
                hack = reward.get("hack")
                if hack and hack not in profile.hacks:
                    profile.hacks.append(hack)
                    pf._fill_empty_slot(profile, hack)
                profile.layers_cleared = i + 1


def cross(profile, content) -> int:
    """Atravessa a Blackwall: ganha os fragmentos e recomeça a vida. Devolve quantos fragmentos ganhou."""
    if not unlocked(profile, content):
        return 0
    gained, _parts = fragments_for(profile, content)
    pr = dict(profile.prestige)
    pr["fragments"] = pr.get("fragments", 0) + gained
    pr["total"] = pr.get("total", 0) + gained
    pr["count"] = pr.get("count", 0) + 1
    pr["life_ed"] = 0
    pr["life_best"] = 0
    fresh = pf.new_profile(content)
    fresh.prestige = pr
    fresh.best_infinite = profile.best_infinite
    fresh.stats = dict(profile.stats)
    fresh.stats["crossings"] = fresh.stats.get("crossings", 0) + 1
    fresh.settings = dict(profile.settings)
    fresh.last_seen = profile.last_seen
    apply_start(fresh, content)
    profile.__dict__.update(fresh.__dict__)
    return gained
