"""As coisas que existem dentro de um mergulho: a netrunner, os ICE, os tiros, as poças, o Ed."""

import math


def dist2(ax, ay, bx, by) -> float:
    return (ax - bx) ** 2 + (ay - by) ** 2


def dist(ax, ay, bx, by) -> float:
    return math.hypot(ax - bx, ay - by)


class Player:
    __slots__ = ("x", "y", "hp", "ram", "invulnerable", "rooted", "root_immune", "moving", "facing")

    def __init__(self, x, y, hp, ram):
        self.x = x
        self.y = y
        self.hp = hp
        self.ram = ram
        self.invulnerable = 0.0
        self.rooted = 0.0        # o Scorpion prende
        self.root_immune = 0.0
        self.moving = False
        self.facing = 0.0


class Slot:
    __slots__ = ("hack", "cooldown", "total")

    def __init__(self, hack):
        self.hack = hack
        self.cooldown = 0.0
        self.total = 1.0         # a recarga cheia (para desenhar o arco)


class Enemy:
    """Um ICE (ou um chefe). fx guarda os efeitos: nome -> [segundos, valor]."""

    __slots__ = ("uid", "type", "d", "boss", "x", "y", "hp", "max_hp", "radius", "speed", "damage", "ed",
                 "kind", "fx", "dead", "timer", "state", "state_t", "dir", "phase", "flash", "dot_acc",
                 "dot_t", "attack_t", "revived", "invulnerable", "angle", "hack_t", "wander", "spiral", "mem")

    def __init__(self, uid, type_id, d, boss, x, y, hp_mult, dmg_mult):
        self.uid = uid
        self.type = type_id
        self.d = d
        self.boss = boss
        self.x = x
        self.y = y
        self.max_hp = d["hp"] * hp_mult
        self.hp = self.max_hp
        self.radius = d["radius"]
        self.speed = d["speed"]
        self.damage = d["damage"] * dmg_mult
        self.ed = d["ed"]
        self.kind = d.get("kind", "ice")
        self.fx = {}
        self.dead = False
        self.timer = 0.0         # o relógio do ataque principal
        self.state = "walk"      # walk, windup, dash, upload, rebuild
        self.state_t = 0.0
        self.dir = (0.0, 0.0)
        self.phase = 0.0         # para o balanço do enxame
        self.flash = 0.0
        self.dot_acc = 0.0
        self.dot_t = 0.0
        self.attack_t = []       # os relógios de cada ataque do chefe
        self.revived = False
        self.invulnerable = False
        self.angle = 0.0
        self.hack_t = 0.0
        self.wander = 0.0
        self.spiral = 0.0        # segundos restantes da espiral
        self.mem = {}            # o que mais o comportamento precisar lembrar

    def has(self, effect: str) -> bool:
        return effect in self.fx

    def effect(self, effect: str) -> float:
        entry = self.fx.get(effect)
        return entry[1] if entry else 0.0

    def controlled(self) -> bool:
        fx = self.fx
        return "root" in fx or "stun" in fx or "blind" in fx or "confused" in fx or "berserk" in fx


class Bullet:
    __slots__ = ("x", "y", "vx", "vy", "radius", "damage", "life", "color")

    def __init__(self, x, y, vx, vy, damage, color, radius=5.0, life=6.0):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.radius = radius
        self.damage = damage
        self.life = life
        self.color = color


class Zone:
    """Uma área no chão: a poça do Asp (machuca você) ou o rastro de veneno (machuca os ICE)."""

    __slots__ = ("x", "y", "radius", "life", "total", "kind", "value")

    def __init__(self, x, y, radius, life, kind, value):
        self.x = x
        self.y = y
        self.radius = radius
        self.life = life
        self.total = life
        self.kind = kind
        self.value = value


class Pickup:
    __slots__ = ("x", "y", "value", "pulled", "vx", "vy")

    def __init__(self, x, y, value, vx=0.0, vy=0.0):
        self.x = x
        self.y = y
        self.value = value
        self.pulled = False
        self.vx = vx
        self.vy = vy


class Upload:
    """Um quickhack a caminho do alvo."""

    __slots__ = ("hack", "slot", "target", "point", "t", "total", "cost", "mult")

    def __init__(self, hack, slot, target, point, total, cost, mult):
        self.hack = hack
        self.slot = slot
        self.target = target
        self.point = point
        self.t = 0.0
        self.total = max(0.01, total)
        self.cost = cost
        self.mult = mult


class Spawn:
    """O aviso no chão antes de um ICE aparecer."""

    __slots__ = ("x", "y", "type", "t", "total", "boss")

    def __init__(self, x, y, type_id, total, boss=False):
        self.x = x
        self.y = y
        self.type = type_id
        self.t = 0.0
        self.total = total
        self.boss = boss


class ObjectiveNode:
    """O nó do download (parado) ou o programa da escolta (andando): os ICE tentam derrubá-lo."""

    __slots__ = ("x", "y", "hp", "max_hp", "radius", "speed", "moving")

    def __init__(self, x, y, hp, speed=0.0):
        self.x = x
        self.y = y
        self.hp = hp
        self.max_hp = hp
        self.radius = 22.0
        self.speed = speed
        self.moving = speed > 0


class Ally:
    """Um runner da equipe (ou o agente da Netwatch) mergulhando junto."""

    __slots__ = ("id", "d", "level", "x", "y", "timer", "slot", "flash")

    def __init__(self, ally_id, d, level, x, y, slot):
        self.id = ally_id
        self.d = d
        self.level = level
        self.x = x
        self.y = y
        self.timer = d["every"] * 0.5
        self.slot = slot
        self.flash = 0.0
