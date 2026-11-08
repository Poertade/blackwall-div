"""Carrega o conteúdo do jogo (data/*.yaml) e confere se tudo se encaixa."""

from dataclasses import dataclass
from pathlib import Path

import yaml

from blackwall.paths import DATA
from blackwall.sim.stats import FLAG_KEYS, HACK_KEYS, STAT_KEYS, TAGS

AIS = {"chase", "swarm", "ranged", "charger", "dropper", "paralyzer", "hacker"}
BOSS_ATTACKS = {"radial", "volley", "spiral", "summon", "charge", "drain", "revive"}
KINDS = {"combate", "controle", "furtivo", "supremo"}
RARITIES = {"comum", "raro", "epico"}
COLORS = {"cyan", "red", "yellow", "violet", "green", "orange", "pink", "white", "blue"}
PATHS = {"solo", "equipe", "netwatch"}


class ContentError(Exception):
    pass


@dataclass
class Content:
    balance: dict
    hacks: dict
    ups: dict
    builds: dict
    enemies: dict
    bosses: dict
    layers: list
    decks: dict
    tree: dict

    def layer_index(self, layer_id: str) -> int:
        for i, layer in enumerate(self.layers):
            if layer["id"] == layer_id:
                return i
        raise KeyError(layer_id)


def _read(path: Path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load(data_dir: Path = DATA) -> Content:
    enemies = _read(data_dir / "enemies.yaml")
    content = Content(
        balance=_read(data_dir / "balance.yaml"),
        hacks=_read(data_dir / "hacks.yaml"),
        ups=_read(data_dir / "ups.yaml"),
        builds=_read(data_dir / "builds.yaml"),
        enemies=enemies["enemies"],
        bosses=enemies["bosses"],
        layers=_read(data_dir / "layers.yaml"),
        decks=_read(data_dir / "decks.yaml"),
        tree=_read(data_dir / "tree.yaml"),
    )
    errors = validate(content)
    if errors:
        raise ContentError("conteúdo com problemas:\n- " + "\n- ".join(errors))
    return content


def _check_mods(where: str, spec: dict, content: Content, errors: list):
    for key in spec.get("stats") or {}:
        if key not in STAT_KEYS:
            errors.append(f"{where}: stat desconhecido '{key}'")
    for key in spec.get("tag_damage") or {}:
        if key not in TAGS:
            errors.append(f"{where}: tag desconhecida '{key}'")
    for hack, values in (spec.get("hacks") or {}).items():
        if hack not in content.hacks:
            errors.append(f"{where}: hack desconhecido '{hack}'")
        for key in values:
            if key not in HACK_KEYS:
                errors.append(f"{where}: chave de hack desconhecida '{key}'")
    for key in spec.get("flags") or {}:
        if key not in FLAG_KEYS:
            errors.append(f"{where}: flag desconhecida '{key}'")


def validate(c: Content) -> list:
    errors = []
    for hid, h in c.hacks.items():
        for key in ("name", "kind", "tags", "color", "ram", "cooldown", "upload", "target", "price", "desc"):
            if key not in h:
                errors.append(f"hack {hid}: falta '{key}'")
        if h.get("kind") not in KINDS:
            errors.append(f"hack {hid}: kind '{h.get('kind')}'")
        if h.get("target") not in ("enemy", "point"):
            errors.append(f"hack {hid}: target '{h.get('target')}'")
        if h.get("color") not in COLORS:
            errors.append(f"hack {hid}: cor '{h.get('color')}'")
        for tag in h.get("tags", []):
            if tag not in TAGS:
                errors.append(f"hack {hid}: tag '{tag}'")
    for uid, u in c.ups.items():
        for key in ("name", "tags", "rarity", "max", "desc"):
            if key not in u:
                errors.append(f"up {uid}: falta '{key}'")
        if u.get("rarity") not in RARITIES:
            errors.append(f"up {uid}: raridade '{u.get('rarity')}'")
        for tag in u.get("tags", []):
            if tag not in TAGS:
                errors.append(f"up {uid}: tag '{tag}'")
        if u.get("requires_hack") and u["requires_hack"] not in c.hacks:
            errors.append(f"up {uid}: requires_hack '{u['requires_hack']}'")
        _check_mods(f"up {uid}", u, c, errors)
    for tag in TAGS:
        if tag not in c.builds:
            errors.append(f"build '{tag}' faltando")
    for tag, b in c.builds.items():
        for key in ("name", "short", "color", "desc", "auto", "bonuses"):
            if key not in b:
                errors.append(f"build {tag}: falta '{key}'")
        for n in c.balance["build"]["thresholds"]:
            if n not in b.get("bonuses", {}):
                errors.append(f"build {tag}: falta o bônus de {n}")
            else:
                _check_mods(f"build {tag} {n}", b["bonuses"][n], c, errors)
    for eid, e in c.enemies.items():
        if e.get("ai") not in AIS:
            errors.append(f"inimigo {eid}: ai '{e.get('ai')}'")
        for key in ("name", "hp", "speed", "radius", "damage", "ed", "cost", "pack", "shape", "color", "kind"):
            if key not in e:
                errors.append(f"inimigo {eid}: falta '{key}'")
        if e.get("color") not in COLORS:
            errors.append(f"inimigo {eid}: cor '{e.get('color')}'")
    for bid, b in c.bosses.items():
        for key in ("name", "title", "hp", "speed", "radius", "damage", "ed", "shape", "color", "attacks", "kind"):
            if key not in b:
                errors.append(f"chefe {bid}: falta '{key}'")
        for attack in b.get("attacks", []):
            if attack.get("type") not in BOSS_ATTACKS:
                errors.append(f"chefe {bid}: ataque '{attack.get('type')}'")
            if attack.get("type") == "summon" and attack.get("enemy") not in c.enemies:
                errors.append(f"chefe {bid}: invoca '{attack.get('enemy')}'")
    for i, layer in enumerate(c.layers):
        where = f"camada {i + 1} ({layer.get('id')})"
        for enemy in layer.get("pool", {}):
            if enemy not in c.enemies:
                errors.append(f"{where}: inimigo '{enemy}'")
        if layer.get("boss") not in c.bosses:
            errors.append(f"{where}: chefe '{layer.get('boss')}'")
        reward = layer.get("reward", {})
        if reward.get("hack") and reward["hack"] not in c.hacks:
            errors.append(f"{where}: recompensa '{reward['hack']}'")
    for did, d in c.decks.items():
        if not 1 <= d.get("slots", 0) <= 6:
            errors.append(f"deck {did}: slots {d.get('slots')}")
        if d.get("path") and d["path"] not in PATHS:
            errors.append(f"deck {did}: caminho '{d['path']}'")
        _check_mods(f"deck {did}", d.get("mods") or {}, c, errors)
    for nid, n in c.tree.items():
        _check_mods(f"árvore {nid}", {"stats": n.get("per_level", {})}, c, errors)
        if n.get("requires") and n["requires"] not in c.tree:
            errors.append(f"árvore {nid}: requires '{n['requires']}'")
    starting = [h for h, d in c.hacks.items() if d.get("price") == 0]
    if len(starting) < 2:
        errors.append("é preciso pelo menos 2 hacks iniciais (price 0)")
    return errors
