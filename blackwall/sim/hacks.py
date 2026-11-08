"""O que cada quickhack faz quando o upload termina.

Cada função recebe o mergulho (dive), o id e os dados do hack, o alvo (um Enemy ou None),
o ponto (x, y) e o multiplicador de dano já calculado (build, árvore, overclock, 5º hack...).
"""

BOSS_CONTROL = 0.3   # chefes resistem: os controles duram 30% do normal


def _control(dive, enemy, effect, seconds, value=1.0):
    """Aplica um controle (root, stun, blind...) respeitando a resistência dos chefes."""
    seconds = dive.stats.control_time(seconds)
    if enemy.boss:
        if effect in ("confused", "berserk", "blind"):
            dive.emit("immune", enemy.x, enemy.y)
            return False
        seconds *= BOSS_CONTROL
    dive.apply_effect(enemy, effect, seconds, value)
    dive.check_execute(enemy, from_control=True)
    return True


def short_circuit(dive, hid, h, target, point, mult):
    dive.chain(hid, h, target, h["damage"] * mult, dive.stats.jumps_of(hid, h), h["jump_range"],
               h.get("falloff", 1.0), "cyan", shock=True)


def ping(dive, hid, h, target, point, mult):
    x, y = point
    radius = dive.stats.radius_of(hid, h)
    seconds = dive.stats.effect_time(h["duration"])
    for e in dive.enemies_near(x, y, radius):
        dive.apply_effect(e, "marked", seconds, h["vuln"])
    dive.emit("ring", x, y, radius, "white")


def overheat(dive, hid, h, target, point, mult):
    dive.hurt(target, h["damage"] * mult, hid, h["tags"], color="orange")
    if target.dead:
        return
    seconds = dive.stats.dot_time(dive.stats.duration_of(hid, h))
    dive.apply_dot(target, "burn", h["dps"] * mult, seconds)
    if dive.stats.flag("paciente_zero"):
        dive.apply_dot(target, "poison", h["dps"] * mult, seconds)


def contagion(dive, hid, h, target, point, mult):
    dps = h["dps"] * mult
    seconds = dive.stats.dot_time(dive.stats.duration_of(hid, h))
    dive.apply_dot(target, "poison", dps, seconds)
    spread = dive.stats.spread_of(hid, h)
    if spread <= 0:
        return
    near = [e for e in dive.enemies_near(target.x, target.y, h["spread_range"]) if e is not target]
    near.sort(key=lambda e: (e.has("poison"), (e.x - target.x) ** 2 + (e.y - target.y) ** 2))
    points = [(target.x, target.y)]
    for e in near[:spread]:
        dive.apply_dot(e, "poison", dps, seconds)
        dive.emit("link", target.x, target.y, e.x, e.y, "green")
        points.append((e.x, e.y))


def synapse_burnout(dive, hid, h, target, point, mult):
    missing = 1 - target.hp / target.max_hp
    damage = h["damage"] * mult * (1 + h.get("execute", 0) * missing)
    dive.hurt(target, damage, hid, h["tags"], color="yellow", heavy=True)
    dive.emit("bolt", target.x, target.y, "yellow")


def cripple_movement(dive, hid, h, target, point, mult):
    dive.hurt(target, h["damage"] * mult, hid, h["tags"], color="violet")
    if not target.dead:
        _control(dive, target, "root", dive.stats.duration_of(hid, h))


def reboot_optics(dive, hid, h, target, point, mult):
    radius = dive.stats.radius_of(hid, h)
    victims = [target] + ([e for e in dive.enemies_near(target.x, target.y, radius) if e is not target]
                          if radius > 0 else [])
    for e in victims:
        _control(dive, e, "blind", dive.stats.duration_of(hid, h))
    if radius > 0:
        dive.emit("ring", target.x, target.y, radius, "violet")


def sonic_shock(dive, hid, h, target, point, mult):
    radius = dive.stats.radius_of(hid, h)
    for e in dive.enemies_near(target.x, target.y, radius):
        dive.hurt(e, h["damage"] * mult, hid, h["tags"], color="violet")
        if not e.dead:
            _control(dive, e, "stun", dive.stats.duration_of(hid, h))
    dive.emit("ring", target.x, target.y, radius, "violet")


def weapon_glitch(dive, hid, h, target, point, mult):
    radius = dive.stats.radius_of(hid, h)
    seconds = dive.stats.effect_time(dive.stats.duration_of(hid, h))
    for e in dive.enemies_near(target.x, target.y, max(radius, target.radius)):
        dive.apply_effect(e, "weaken", seconds, h["weaken"])
    dive.emit("ring", target.x, target.y, radius, "violet")


def memory_wipe(dive, hid, h, target, point, mult):
    _control(dive, target, "confused", dive.stats.duration_of(hid, h))


def cyberpsychosis(dive, hid, h, target, point, mult):
    if not _control(dive, target, "berserk", dive.stats.duration_of(hid, h), h["damage"] * mult):
        dive.refund(dive.stats.ram_cost(hid, h) * 0.5)


def detonate_grenade(dive, hid, h, target, point, mult):
    radius = dive.stats.radius_of(hid, h)
    x, y = target.x, target.y
    for e in dive.enemies_near(x, y, radius):
        dive.hurt(e, h["damage"] * mult, hid, h["tags"], color="orange", heavy=True)
    dive.emit("blast", x, y, radius, "orange")
    dive.emit("shake", 8)


def system_reset(dive, hid, h, target, point, mult):
    if target.boss:
        seconds = dive.stats.control_time(h["stun"] + dive.stats.hack_mod(hid, "duration"))
        dive.apply_effect(target, "stun", seconds, 1)
        dive.hurt(target, target.max_hp * h["boss_damage"], hid, h["tags"], can_crit=False, color="white")
    else:
        dive.emit("reset", target.x, target.y)
        dive.kill(target)


def blackwall_gateway(dive, hid, h, target, point, mult):
    dive.chain(hid, h, target, h["damage"] * mult, dive.stats.jumps_of(hid, h), h["jump_range"],
               h.get("falloff", 1.0), "red", shock=True)
    dive.emit("shake", 6)


def system_collapse(dive, hid, h, target, point, mult):
    x, y = target.x, target.y
    if target.boss:
        dive.hurt(target, target.max_hp * h["boss_damage"] * min(mult, 2.0), hid, h["tags"], can_crit=False,
                  color="red", heavy=True)
    else:
        dive.emit("reset", x, y)
        dive.kill(target)
    radius = dive.stats.radius_of(hid, h)
    for e in dive.enemies_near(x, y, radius):
        if e is not target:
            dive.hurt(e, h["damage"] * mult, hid, h["tags"], color="red")
    dive.emit("blast", x, y, radius, "red")
    dive.emit("shake", 10)


EFFECTS = {
    "short_circuit": short_circuit,
    "ping": ping,
    "overheat": overheat,
    "contagion": contagion,
    "synapse_burnout": synapse_burnout,
    "cripple_movement": cripple_movement,
    "reboot_optics": reboot_optics,
    "sonic_shock": sonic_shock,
    "weapon_glitch": weapon_glitch,
    "memory_wipe": memory_wipe,
    "cyberpsychosis": cyberpsychosis,
    "detonate_grenade": detonate_grenade,
    "system_reset": system_reset,
    "blackwall_gateway": blackwall_gateway,
    "system_collapse": system_collapse,
}
