"""Os números da netrunner: a base do balance.yaml mais a soma de tudo que a melhora.

Tudo que melhora (os ups, os bônus das builds, a árvore, o deck, o caminho da história) é escrito
do mesmo jeito, com quatro chaves:

    stats:      {hp: 25, damage: 0.1, ...}       (veja STAT_KEYS)
    tag_damage: {sobrecarga: 0.4}                 (+dano dos hacks com essa tag)
    hacks:      {short_circuit: {jumps: 1}}       (veja HACK_KEYS)
    flags:      {epidemia: 1}                     (regras especiais; veja FLAG_KEYS)

A classe Mods soma esses blocos; a classe Stats transforma a soma nos números finais.
"""

from collections import defaultdict

TAGS = ("contagio", "sobrecarga", "cadeia", "controle")

# O que cada chave de stats faz
STAT_KEYS = {
    "hp": "+Integridade",
    "ram": "+RAM máxima",
    "ram_regen": "+% de RAM de volta por segundo",
    "armor": "+armadura",
    "speed": "+% de velocidade",
    "crit_chance": "+chance de crítico (0.1 = 10%)",
    "crit_mult": "+dano crítico (0.25 = +25%)",
    "pickup": "+% de alcance de coleta",
    "lifesteal": "+roubo de vida (0.04 = 4% do dano)",
    "hp_regen": "+Integridade por segundo",
    "damage": "+% de dano em tudo",
    "cooldown": "% mais rápido para recarregar (negativo = mais devagar)",
    "duration": "+% de duração dos efeitos",
    "control": "+% de duração dos controles",
    "upload": "% mais rápido para o hack chegar",
    "ram_cost": "-RAM em cada hack",
    "ram_cost_pct": "-% de RAM em cada hack",
    "ultimate_cost": "-% de RAM nos supremos",
    "dot": "+% de dano de veneno e queimadura",
    "dot_duration": "+segundos de veneno e queimadura",
    "ed": "+% de Ed",
    "damage_ai": "+% de dano em IAs e netrunners",
}

HACK_KEYS = {"damage", "ram", "cooldown", "duration", "radius", "jumps", "spread"}

FLAG_KEYS = {
    "imuno": "alvos envenenados tomam +X de dano",
    "epidemia": "quem morre envenenado contamina os vizinhos",
    "paciente_zero": "Overheat também envenena",
    "execute": "até +X de dano quanto menos vida o alvo tem",
    "overclock": "o dobro de RAM, 2,5 vezes o dano",
    "fagulha": "o choque queima",
    "vuln_control": "+X de dano em quem está sob controle",
    "execucao": "hacks de controle desligam ICE abaixo de X de vida",
    "auto_spread": "o veneno pula sozinho",
    "free_contagion": "Contagion de graça em envenenados",
    "crit_stun": "críticos atordoam por X s",
    "fifth_triple": "cada 5º hack causa o triplo",
    "extra_jump": "+X saltos",
    "no_falloff": "os saltos não perdem dano",
    "jump_refund": "cada salto devolve X de RAM",
    "control_refund": "derrubar ICE controlado devolve X de RAM",
    "control_execute": "ICE controlado abaixo de X de vida cai",
    "lone_wolf": "+X de dano a cada onda sem levar dano",
}

CONTROL_EFFECTS = ("root", "stun", "blind", "confused", "berserk")


class Mods:
    """A soma de vários blocos de melhoria."""

    def __init__(self):
        self.stats = defaultdict(float)
        self.tag_damage = defaultdict(float)
        self.hacks = defaultdict(lambda: defaultdict(float))
        self.flags = defaultdict(float)

    def add(self, spec: dict, times: int = 1) -> "Mods":
        if not spec:
            return self
        for key, value in (spec.get("stats") or {}).items():
            self.stats[key] += value * times
        for key, value in (spec.get("tag_damage") or {}).items():
            self.tag_damage[key] += value * times
        for hack, values in (spec.get("hacks") or {}).items():
            for key, value in values.items():
                self.hacks[hack][key] += value * times
        for key, value in (spec.get("flags") or {}).items():
            self.flags[key] += value * times
        return self

    def merge(self, other: "Mods") -> "Mods":
        for key, value in other.stats.items():
            self.stats[key] += value
        for key, value in other.tag_damage.items():
            self.tag_damage[key] += value
        for hack, values in other.hacks.items():
            for key, value in values.items():
                self.hacks[hack][key] += value
        for key, value in other.flags.items():
            self.flags[key] += value
        return self

    def copy(self) -> "Mods":
        return Mods().merge(self)


class Stats:
    """Os números finais, a partir da base (balance.yaml) e de uma soma de Mods."""

    def __init__(self, balance: dict, mods: Mods):
        self.base = balance["player"]
        self.limits = balance["limits"]
        self.mods = mods
        s = mods.stats
        self.max_hp = max(1.0, self.base["hp"] + s["hp"])
        self.max_ram = max(1.0, self.base["ram"] + s["ram"])
        self.ram_regen = self.base["ram_regen"] * (1 + s["ram_regen"])
        self.armor = self.base["armor"] + s["armor"]
        self.speed = self.base["speed"] * (1 + s["speed"])
        self.crit_chance = min(1.0, self.base["crit_chance"] + s["crit_chance"])
        self.crit_mult = self.base["crit_mult"] + s["crit_mult"]
        self.pickup = self.base["pickup"] * (1 + s["pickup"])
        self.lifesteal = self.base["lifesteal"] + s["lifesteal"]
        self.hp_regen = self.base["hp_regen"] + s["hp_regen"]
        self.damage = s["damage"]
        self.cooldown = min(self.limits["cooldown"], s["cooldown"])
        self.upload = min(self.limits["upload"], s["upload"])
        self.duration = s["duration"]
        self.control = s["control"]
        self.dot = s["dot"]
        self.dot_duration = s["dot_duration"]
        self.ed = s["ed"]
        self.damage_ai = s["damage_ai"]
        self.invulnerable = self.base["invulnerable"]
        self.radius = self.base["radius"]

    def flag(self, name: str) -> float:
        return self.mods.flags.get(name, 0.0)

    def armor_factor(self) -> float:
        """Quanto do dano passa pela armadura (armadura negativa aumenta o dano)."""
        armor = self.armor
        if armor >= 0:
            return 100 / (100 + armor)
        return 2 - 100 / (100 - armor)

    # --- os números de um quickhack -------------------------------------------
    def hack_mod(self, hack_id: str, key: str) -> float:
        return self.mods.hacks.get(hack_id, {}).get(key, 0.0)

    def ram_cost(self, hack_id: str, hack: dict) -> float:
        cost = hack["ram"] + self.hack_mod(hack_id, "ram")
        s = self.mods.stats
        cost *= 1 - min(0.6, s["ram_cost_pct"])
        if hack["kind"] == "supremo":
            cost *= 1 - min(0.6, s["ultimate_cost"])
        cost -= s["ram_cost"]
        cost = max(1.0, cost)
        if self.flag("overclock"):
            cost *= 2
        return round(cost, 1)

    def cooldown_of(self, hack_id: str, hack: dict) -> float:
        reduction = min(self.limits["cooldown"], self.cooldown + self.hack_mod(hack_id, "cooldown"))
        return hack["cooldown"] * (1 - reduction)

    def upload_of(self, hack_id: str, hack: dict) -> float:
        return hack["upload"] * (1 - self.upload)

    def damage_mult(self, hack_id: str | None, tags) -> float:
        mult = 1 + self.damage
        for tag in tags:
            mult += self.mods.tag_damage.get(tag, 0.0)
        if hack_id:
            mult += self.hack_mod(hack_id, "damage")
        if self.flag("overclock") and hack_id:
            mult *= 2.5
        return max(0.1, mult)

    def control_time(self, seconds: float) -> float:
        return seconds * (1 + self.duration + self.control)

    def effect_time(self, seconds: float) -> float:
        return seconds * (1 + self.duration)

    def dot_time(self, seconds: float) -> float:
        return (seconds + self.dot_duration) * (1 + self.duration)

    def radius_of(self, hack_id: str, hack: dict) -> float:
        return hack.get("radius", 0) + self.hack_mod(hack_id, "radius")

    def jumps_of(self, hack_id: str, hack: dict) -> int:
        base = hack.get("jumps", 0) + self.hack_mod(hack_id, "jumps")
        if "jumps" in hack:
            base += self.flag("extra_jump")
        return int(base)

    def spread_of(self, hack_id: str, hack: dict) -> int:
        return int(hack.get("spread", 0) + self.hack_mod(hack_id, "spread"))

    def duration_of(self, hack_id: str, hack: dict) -> float:
        return hack.get("duration", 0) + self.hack_mod(hack_id, "duration")
