"""O plano de cada onda: quanto dura, quantos ICE vêm, quão fortes, e quando vem o chefe."""

from dataclasses import dataclass


@dataclass
class WavePlan:
    number: int          # a onda no mergulho (1, 2, 3...)
    in_layer: int        # a onda dentro da camada (1 a 10)
    layer: int           # o índice da camada (o ambiente, os ICE e o chefe)
    duration: float      # segundos (0 = até o chefe cair)
    budget: float        # pontos de ameaça por segundo
    hp: float            # multiplicador da vida
    damage: float        # multiplicador do dano
    ed: float            # multiplicador do Ed
    boss: str | None
    pool: dict


def plan(content, mode: str, layer: int, number: int) -> WavePlan:
    bal = content.balance["waves"]
    per = bal["per_layer"]
    if mode == "infinite":
        cycle = (number - 1) // per
        layer_index = cycle % len(content.layers)
        in_layer = (number - 1) % per + 1
        base = content.layers[0]
        step = content.balance["infinite"]["layer_step"]
        hp_mult = base["hp"] * step ** cycle
        dmg_mult = base["damage"] * (1 + 0.5 * cycle) ** 1.1
        ed_mult = base["ed"] * content.balance["infinite"]["ed_step"] ** cycle
        budget_mult = content.layers[layer_index]["budget"] * (1 + 0.05 * cycle)
    else:
        layer_index = layer
        in_layer = number
        data = content.layers[layer_index]
        hp_mult, dmg_mult, ed_mult, budget_mult = data["hp"], data["damage"], data["ed"], data["budget"]
    data = content.layers[layer_index]
    boss = data["boss"] if in_layer == per else None
    duration = 0.0 if boss else min(bal["duration_max"], bal["duration_first"] + bal["duration_step"] * (in_layer - 1))
    budget = bal["budget_base"] * bal["budget_growth"] ** (in_layer - 1) * budget_mult
    if boss:
        budget *= bal["boss_budget"]
    return WavePlan(
        number=number,
        in_layer=in_layer,
        layer=layer_index,
        duration=duration,
        budget=budget,
        hp=hp_mult * (1 + bal["hp_growth"] * (in_layer - 1)),
        damage=dmg_mult * (1 + bal["damage_growth"] * (in_layer - 1)),
        ed=ed_mult,
        boss=boss,
        pool={k: v for k, v in data["pool"].items() if v["from"] <= in_layer},
    )
