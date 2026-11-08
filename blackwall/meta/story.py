"""A quest line no esconderijo: as falas, a escolha do caminho, as missões, a equipe e a renda.

O estado fica em profile.quest:
    read    as falas já lidas
    done    as missões cumpridas
    team    os aliados e o nível de cada um
    ending  o caminho do final, quando a 5ª camada cai
    income  a fração de Ed da renda que ainda não virou Ed inteiro
"""

import time

PATHS = ("solo", "equipe", "netwatch")


def quest(profile) -> dict:
    q = profile.quest
    q.setdefault("read", [])
    q.setdefault("done", [])
    q.setdefault("team", {})
    q.setdefault("ending", None)
    q.setdefault("income", 0.0)
    return q


# --- as falas ----------------------------------------------------------------
def beat_ok(profile, beat) -> bool:
    when = beat.get("when", {})
    q = quest(profile)
    if "layers" in when and profile.layers_cleared < when["layers"]:
        return False
    if "dives" in when and profile.stats.get("dives", 0) < when["dives"]:
        return False
    if "path" in when and profile.path != when["path"]:
        return False
    if "mission" in when and when["mission"] not in q["done"]:
        return False
    if "prestige" in when and profile.prestige.get("count", 0) < when["prestige"]:
        return False
    return True


def beats(profile, content) -> list:
    """As falas que já chegaram, na ordem em que aparecem no story.yaml."""
    return [b for b in content.story["beats"] if beat_ok(profile, b)]


def unread(profile, content) -> list:
    read = set(quest(profile)["read"])
    return [b for b in beats(profile, content) if b["id"] not in read]


def mark_read(profile, content):
    q = quest(profile)
    for b in beats(profile, content):
        if b["id"] not in q["read"]:
            q["read"].append(b["id"])


# --- o caminho ---------------------------------------------------------------
def needs_path_choice(profile) -> bool:
    return profile.layers_cleared >= 1 and profile.path is None


def choose_path(profile, content, path: str) -> bool:
    """A escolha dos três caminhos: uma vez por salvamento, para sempre."""
    if not needs_path_choice(profile) or path not in PATHS:
        return False
    profile.path = path
    q = quest(profile)
    for ally in content.story.get("team", {}).get(path, []):
        q["team"].setdefault(ally, 1)
    return True


# --- as missões --------------------------------------------------------------
def missions(profile, content) -> list:
    """[(missão, situação)] do caminho escolhido. situação: done, open ou locked."""
    q = quest(profile)
    result = []
    for m in content.story["missions"]:
        if m["path"] != profile.path:
            continue
        if m["id"] in q["done"]:
            status = "done"
        elif profile.layers_cleared >= m.get("requires", {}).get("layers", 0):
            status = "open"
        else:
            status = "locked"
        result.append((m, status))
    return result


def open_missions(profile, content) -> list:
    return [m for m, status in missions(profile, content) if status == "open"]


def mission_reward(profile, content, mission) -> dict:
    """Marca a missão como cumprida e entrega a recompensa (só na primeira vez)."""
    q = quest(profile)
    summary = {"ed": 0, "hack": None, "deck": None, "ally": None}
    if mission["id"] in q["done"]:
        return summary
    q["done"].append(mission["id"])
    reward = mission.get("reward", {})
    summary["ed"] = reward.get("ed", 0)
    profile.ed += summary["ed"]
    hack = reward.get("hack")
    if hack:
        if hack in profile.hacks:
            bonus = content.hacks[hack]["price"] // 2
            profile.ed += bonus
            summary["ed"] += bonus
        else:
            profile.hacks.append(hack)
            if None in profile.loadout:
                profile.loadout[profile.loadout.index(None)] = hack
            summary["hack"] = hack
    deck = reward.get("deck")
    if deck and deck not in profile.decks:
        profile.decks.append(deck)
        summary["deck"] = deck
    ally = reward.get("ally")
    if ally and ally not in q["team"]:
        q["team"][ally] = 1
        summary["ally"] = ally
    return summary


# --- a equipe ----------------------------------------------------------------
def ally_cost(content, level: int) -> int:
    """O preço para subir do nível `level` para o seguinte."""
    cfg = content.story["ally_level"]
    return int(round(cfg["cost"] * cfg["growth"] ** (level - 1)))


def train_status(profile, content, ally: str) -> tuple:
    q = quest(profile)
    level = q["team"].get(ally)
    if level is None:
        return False, "fora da equipe"
    if level >= content.story["ally_level"]["max"]:
        return False, "no máximo"
    cost = ally_cost(content, level)
    if profile.ed < cost:
        return False, f"faltam {cost - profile.ed} Ed"
    return True, ""


def train_ally(profile, content, ally: str) -> bool:
    ok, _ = train_status(profile, content, ally)
    if not ok:
        return False
    q = quest(profile)
    profile.ed -= ally_cost(content, q["team"][ally])
    q["team"][ally] += 1
    return True


def allies_for_dive(profile, content) -> list:
    if profile.path not in ("equipe", "netwatch"):
        return []
    return [(ally, level) for ally, level in quest(profile)["team"].items()]


# --- a renda -----------------------------------------------------------------
def income_rate(profile, content) -> float:
    """Ed por hora enquanto você não está mergulhando (inclusive com o jogo fechado)."""
    cfg = content.story["income"].get(profile.path or "", None)
    if not isinstance(cfg, dict):
        return 0.0
    levels = sum(quest(profile)["team"].values())
    return cfg["per_hour"] * (1 + cfg["per_ally_level"] * levels)


def accrue(profile, content, seconds: float) -> int:
    """Soma a renda de `seconds` segundos. Devolve quantos Ed inteiros entraram."""
    rate = income_rate(profile, content)
    if rate <= 0 or seconds <= 0:
        return 0
    q = quest(profile)
    q["income"] += rate * seconds / 3600
    whole = int(q["income"])
    q["income"] -= whole
    profile.ed += whole
    return whole


def offline_income(profile, content, now: float | None = None) -> int:
    """A renda do tempo em que o jogo ficou fechado (até o limite de horas do caminho)."""
    cfg = content.story["income"].get(profile.path or "", None)
    if not isinstance(cfg, dict):
        return 0
    now = time.time() if now is None else now
    seconds = max(0.0, min(now - profile.last_seen, cfg["cap_hours"] * 3600))
    return accrue(profile, content, seconds)


# --- o fim -------------------------------------------------------------------
def ending(profile, content) -> dict | None:
    path = quest(profile)["ending"]
    return content.story["endings"].get(path) if path else None
