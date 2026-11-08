"""Um mergulho: as ondas, a netrunner, os ICE e os quickhacks.

Sem tela: a interface (blackwall/game) só lê o estado e os eventos, e os testes e o robô de
balanceamento rodam o mesmo código. Tudo é sorteado por um Random com semente (dá para repetir).

Fases: "wave" (a onda rolando), "choice" (escolher 1 dos ups) e "over" (acabou: result diz como).
"""

import math
from collections import Counter
from dataclasses import dataclass, field
from random import Random

from blackwall.sim import build, hacks, waves
from blackwall.sim.entities import (Ally, Bullet, Enemy, ObjectiveNode, Pickup, Player, Slot, Spawn, Upload, Zone,
                                    dist2)
from blackwall.sim.stats import Mods, Stats

TAU = math.tau


@dataclass
class DiveConfig:
    mode: str = "layer"                 # layer (uma camada, 10 ondas) ou infinite
    layer: int = 0                      # o índice da camada
    loadout: list = field(default_factory=lambda: ["short_circuit", "ping"])
    deck: str = "paraline"
    mods: Mods = field(default_factory=Mods)   # árvore + deck + caminho da história
    seed: int = 1
    choices: int = 0                    # quantos ups por escolha (0 = o do balance.yaml)
    mission: dict | None = None         # mode "mission": a missão da história (data/story.yaml)
    allies: list = field(default_factory=list)   # [(id do aliado, nível)]
    ally_pickup: float = 0.0            # a equipe recolhe o Ed que cai perto de cada aliado


@dataclass
class DiveInput:
    aim: tuple = (0.0, 0.0)             # onde está o cursor (o alvo dos hacks e o destino do movimento)
    cast: tuple = ()                    # os slots apertados neste passo
    held: tuple = ()                    # os slots segurados (os hacks de movimento que andam enquanto seguram)


class Dive:
    def __init__(self, content, config: DiveConfig):
        self.c = content
        self.cfg = config
        self.rng = Random(config.seed)
        self.bal = content.balance
        self.W = self.bal["arena"]["width"]
        self.H = self.bal["arena"]["height"]
        self.taken = Counter()
        self.auto = None
        self.stats = None
        self.recompute()
        self.player = Player(self.W / 2, self.H / 2, self.stats.max_hp, self.stats.max_ram)
        self.slots = [Slot(h) for h in config.loadout]
        self.enemies: list[Enemy] = []
        self.bullets: list[Bullet] = []
        self.zones: list[Zone] = []
        self.pickups: list[Pickup] = []
        self.uploads: list[Upload] = []
        self.spawns: list[Spawn] = []
        self.events = []
        self.uid = 0
        self.time = 0.0
        self.wave = 0
        self.wave_time = 0.0
        self.plan = None
        self.phase = "wave"
        self.result = None
        self.offer = []
        self.rerolls = 0
        self.ed = 0.0
        self.kills = 0
        self.damage_dealt = 0.0
        self.damage_taken = 0.0
        self.casts = 0
        self.lone_wolf = 0.0
        self.hit_this_wave = False
        self.budget_acc = 0.0
        self.next_type = None
        self.boss = None
        self.auto_t = 0.0
        self.spread_t = 0.0
        self.trail_from = (self.player.x, self.player.y)
        self.lifesteal_left = 0.0
        self.waves_cleared = 0
        self.queue = []
        self.wave_total = 0
        self.reinforcements = True       # os testes desligam para controlar a arena
        self.reinforce_t = 0.0
        self.reinforcing = False
        # a missão da história
        self.mission = config.mission
        self.objective = (config.mission or {}).get("objective", {})
        self.node = None
        self.nodes_warned = False
        self.mission_time = 0.0
        self.mission_total = 0.0
        if self.mission:
            self.mission_total = sum(waves.plan(content, "mission", 0, n, self.mission).duration
                                     for n in range(1, self.mission["waves"] + 1))
            kind = self.objective["type"]
            if kind == "download":
                self.node = ObjectiveNode(self.W / 2, self.H / 2, self.objective["hp"])
                self.player.y = self.H / 2 + 90
            elif kind == "escort":
                speed = (self.W - 140) / max(1.0, self.mission_total)
                self.node = ObjectiveNode(70, self.H / 2, self.objective["hp"], speed)
        # os aliados
        allies_data = content.story.get("allies", {})
        self.allies = []
        for i, (ally_id, level) in enumerate(config.allies):
            angle = TAU * i / max(1, len(config.allies))
            self.allies.append(Ally(ally_id, allies_data[ally_id], level, self.player.x + math.cos(angle) * 50,
                                    self.player.y + math.sin(angle) * 50, i))
        self.start_wave(1)

    # --- números e eventos ---------------------------------------------------
    def recompute(self):
        old_max = self.stats.max_hp if self.stats else None
        self.mods = self.cfg.mods.copy().merge(build.ups_mods(self.c, self.taken))
        self.stats = Stats(self.bal, self.mods)
        self.counts = build.tag_counts(self.c, self.taken)
        self.auto = build.auto_tag(self.c, self.counts, self.auto)
        if old_max is not None:
            p = self.player
            p.hp = min(self.stats.max_hp, p.hp + max(0.0, self.stats.max_hp - old_max))
            p.ram = min(self.stats.max_ram, p.ram)

    def emit(self, *event):
        self.events.append(event)
        if len(self.events) > 600:
            del self.events[:200]

    def take_events(self) -> list:
        events, self.events = self.events, []
        return events

    @property
    def choices(self) -> int:
        return self.cfg.choices or self.bal["ups"]["choices"]

    @property
    def ed_final(self) -> int:
        """O Ed que volta para o esconderijo (o flatline perde uma parte)."""
        if self.result in ("flatline", "aborted"):
            return int(self.ed * (1 - self.bal["flatline_ed_loss"]))
        # "failed": a missão falhou (o nó caiu), mas você não: volta com tudo
        return int(self.ed)

    # --- as ondas ------------------------------------------------------------
    def start_wave(self, number: int):
        self.wave = number
        self.plan = waves.plan(self.c, self.cfg.mode, self.cfg.layer, number, self.mission)
        self.wave_time = 0.0
        self.budget_acc = 0.0
        self.next_type = None
        self.phase = "wave"
        self.hit_this_wave = False
        self.boss = None
        if self.plan.boss:
            x, y = self._far_point(min_distance=320)
            self.spawns.append(Spawn(x, y, self.plan.boss, 1.6, boss=True))
        if self.objective.get("type") == "nodes":
            for _ in range(self.objective.get("per_wave", 2)):
                x, y = self._far_point(min_distance=200)
                self.spawns.append(Spawn(x, y, "node", 1.0))
        self._plan_queue()
        self.reinforce_t = 0.0
        self.reinforcing = False
        self.emit("wave", number, self.plan.boss)

    def _pick_type(self):
        pool = self.plan.pool
        total = sum(v["weight"] for v in pool.values())
        pick = self.rng.random() * total
        for type_id, v in pool.items():
            pick -= v["weight"]
            if pick <= 0:
                return type_id
        return type_id

    def _plan_queue(self):
        """Sorteia, no começo da onda, todos os ICE dela: [segundo em que chegam, tipo, quantos].

        O total é fixo: a onda acaba quando todos chegaram e caíram (o chefe tem o próprio fim)."""
        plan = self.plan
        self.queue = []
        if plan.boss or not plan.pool:
            self.wave_total = 0
            return
        t, acc, step, nxt = 0.0, 0.0, 0.25, None
        while t < plan.duration:
            acc = min(acc + plan.budget * step, 18.0)
            nxt = nxt or self._pick_type()
            d = self.c.enemies[nxt]
            if acc >= d["cost"]:
                count = self.rng.randint(*d["pack"])
                acc -= d["cost"] * count
                self.queue.append([t, nxt, count])
                nxt = None
            t += step
        self.wave_total = sum(q[2] for q in self.queue)

    def remaining(self) -> int:
        """Quantos ICE ainda faltam derrubar nesta onda (os que vão chegar e os que estão na arena)."""
        return sum(q[2] for q in self.queue) + len(self.enemies) + len(self.spawns)

    def reinforce_in(self) -> float:
        """Segundos até começarem os reforços (0 = já estão chegando)."""
        w = self.bal["waves"]
        return max(0.0, self.plan.duration + w["reinforce_after"] - self.wave_time)

    def _release(self, type_id, count):
        x, y = self._far_point()
        telegraph = self.bal["waves"]["telegraph"]
        for _ in range(count):
            sx = min(self.W - 20, max(20, x + self.rng.uniform(-40, 40)))
            sy = min(self.H - 20, max(20, y + self.rng.uniform(-40, 40)))
            self.spawns.append(Spawn(sx, sy, type_id, telegraph))

    def _end_wave(self):
        for e in self.enemies:
            self.emit("dissolve", e.x, e.y, e.d["color"], e.radius)
        self.enemies.clear()
        self.spawns.clear()
        self.bullets.clear()
        self.zones.clear()
        for u in self.uploads:
            self.refund(u.cost)
        self.uploads.clear()
        for pk in self.pickups:
            self.ed += pk.value
        self.pickups.clear()
        lone = self.stats.flag("lone_wolf")
        if lone and not self.hit_this_wave:
            self.lone_wolf += lone
            self.emit("lone_wolf", self.lone_wolf)
        p = self.player
        p.hp = min(self.stats.max_hp, p.hp + self.stats.max_hp * self.bal["waves"]["heal_between"])
        p.ram = self.stats.max_ram
        p.rooted = 0.0
        for s in self.slots:
            s.cooldown = 0.0
        self.waves_cleared += 1
        self.emit("wave_clear", self.wave)

    def _to_choice(self):
        self.phase = "choice"
        self.rerolls = 0
        self.offer = build.roll_offer(self.c, self.rng, self.taken, self.cfg.loadout, self.wave, self.choices)

    def choose(self, index: int):
        if self.phase != "choice" or not 0 <= index < len(self.offer):
            return
        up_id = self.offer[index]
        self.taken[up_id] += 1
        self.recompute()
        self.emit("up", up_id)
        self.start_wave(self.wave + 1)

    def reroll_cost(self) -> int:
        b = self.bal["ups"]
        return int(b["reroll_base"] + b["reroll_step"] * self.rerolls)

    def reroll(self) -> bool:
        cost = self.reroll_cost()
        if self.phase != "choice" or self.ed < cost:
            return False
        self.ed -= cost
        self.rerolls += 1
        self.offer = build.roll_offer(self.c, self.rng, self.taken, self.cfg.loadout, self.wave, self.choices)
        return True

    def extract(self):
        """Desconectar entre as ondas: volta com todo o Ed, sem vencer a camada."""
        if self.phase == "choice":
            self.phase = "over"
            self.result = "extracted"

    def abort(self):
        """Desconectar no meio da onda: é como um flatline (perde parte do Ed)."""
        if self.phase in ("wave", "choice"):
            self.phase = "over"
            self.result = "aborted"

    def nodes_left(self) -> int:
        return (sum(1 for e in self.enemies if e.type == "node" and not e.dead)
                + sum(1 for sp in self.spawns if sp.type == "node"))

    def _after_wave(self):
        """Depois de uma onda: a escolha de ups, ou o fim da missão."""
        if self.mission and self.wave >= self.mission["waves"]:
            self.phase = "over"
            self.result = "victory"
            self.emit("mission_done")
        else:
            self._to_choice()

    def _director(self, dt):
        plan = self.plan
        if not plan.boss:
            limit = self.bal["waves"]["max_alive"]
            while self.queue and self.queue[0][0] <= self.wave_time:
                alive = len(self.enemies) + len(self.spawns)
                if alive >= limit:
                    break
                _t, type_id, count = self.queue.pop(0)
                self._release(type_id, min(count, limit - alive))
            if not self.queue and not self.enemies and not self.spawns:
                self._end_wave()
                self._after_wave()
                return
            # demorou demais: chegam reforços até a onda acabar
            if self.reinforcements and plan.pool and self.reinforce_in() <= 0:
                if not self.reinforcing:
                    self.reinforcing = True
                    self.emit("objective", "REFORÇOS")
                self.reinforce_t -= dt
                if self.reinforce_t <= 0 and len(self.enemies) + len(self.spawns) < limit:
                    self.reinforce_t = self.bal["waves"]["reinforce_every"]
                    type_id = self._pick_type()
                    self._release(type_id, self.rng.randint(*self.c.enemies[type_id]["pack"]))
            return
        if not plan.pool:
            return
        self.budget_acc = min(self.budget_acc + plan.budget * dt, 18.0)
        alive = len(self.enemies) + len(self.spawns)
        limit = self.bal["waves"]["max_alive"]
        if alive >= limit:
            return
        if self.next_type is None:
            total = sum(v["weight"] for v in plan.pool.values())
            pick = self.rng.random() * total
            for type_id, v in plan.pool.items():
                pick -= v["weight"]
                if pick <= 0:
                    break
            self.next_type = type_id
        d = self.c.enemies[self.next_type]
        if self.budget_acc < d["cost"]:
            return
        count = min(self.rng.randint(*d["pack"]), limit - alive)
        self.budget_acc -= d["cost"] * count
        x, y = self._far_point()
        telegraph = self.bal["waves"]["telegraph"]
        for _ in range(count):
            sx = min(self.W - 20, max(20, x + self.rng.uniform(-40, 40)))
            sy = min(self.H - 20, max(20, y + self.rng.uniform(-40, 40)))
            self.spawns.append(Spawn(sx, sy, self.next_type, telegraph))
        self.next_type = None

    def _far_point(self, min_distance=None):
        p = self.player
        need = (min_distance or self.bal["waves"]["spawn_min_distance"]) ** 2
        best, best_d = (40.0, 40.0), -1.0
        for _ in range(24):
            x = self.rng.uniform(40, self.W - 40)
            y = self.rng.uniform(40, self.H - 40)
            d = dist2(x, y, p.x, p.y)
            if d >= need:
                return x, y
            if d > best_d:
                best, best_d = (x, y), d
        return best

    def _spawn_enemy(self, type_id, x, y, boss=False):
        self.uid += 1
        d = self.c.bosses[type_id] if boss else self.c.enemies[type_id]
        e = Enemy(self.uid, type_id, d, boss, x, y, self.plan.hp, self.plan.damage)
        e.phase = self.rng.random() * TAU
        e.timer = self.rng.uniform(0.6, 1.0) * d.get("fire_every", d.get("charge_every", d.get("drop_every", 2)))
        e.hack_t = d.get("hack_every", 5) * self.rng.uniform(0.5, 1.0)
        if boss:
            e.attack_t = [a.get("every", 1) * 0.5 for a in d["attacks"]]
            self.boss = e
            self.emit("boss", type_id)
        self.enemies.append(e)
        return e

    # --- o passo -------------------------------------------------------------
    def step(self, dt: float, inp: DiveInput | None = None):
        if self.phase != "wave":
            return
        inp = inp or DiveInput()
        self.time += dt
        self.wave_time += dt
        st = self.stats
        p = self.player
        # a netrunner
        p.hp = min(st.max_hp, p.hp + st.hp_regen * dt)
        p.ram = min(st.max_ram, p.ram + st.ram_regen * dt)
        cap = self.bal["limits"]["lifesteal_per_second"] * st.max_hp
        self.lifesteal_left = min(cap, self.lifesteal_left + cap * dt)
        p.invulnerable = max(0.0, p.invulnerable - dt)
        p.root_immune = max(0.0, p.root_immune - dt)
        p.moving = False
        p.slowmo = False
        if p.rooted > 0:
            p.rooted -= dt
        if p.dash_t > 0:
            p.dash_t -= dt
            p.x += p.dash_v[0] * dt
            p.y += p.dash_v[1] * dt
            p.moving = True
        elif p.rooted <= 0:
            self._walk(inp, dt)
        r = st.radius
        p.x = min(self.W - r, max(r, p.x))
        p.y = min(self.H - r, max(r, p.y))
        for s in self.slots:
            s.cooldown = max(0.0, s.cooldown - dt)
        for slot in inp.cast:
            self.cast(slot, inp.aim)
        self._update_uploads(dt)
        # com o Sandevistan, o mundo anda devagar (a netrunner, os hacks e a RAM não)
        wdt = dt * (1 - self._slowmo_factor()) if p.slowmo else dt
        self._update_spawns(wdt)
        self._director(wdt)
        if self.phase != "wave":
            return
        self._update_auto(dt)
        self._update_objective(wdt)
        self._update_allies(dt)
        if self.phase != "wave":
            return
        for e in self.enemies:
            if not e.dead:
                self._update_enemy(e, wdt)
        self.enemies = [e for e in self.enemies if not e.dead]
        self._separate()
        self._update_bullets(wdt)
        self._update_zones(wdt)
        self._update_pickups(dt)
        if p.hp <= 0 and self.phase == "wave":
            self.phase = "over"
            self.result = "flatline"
            self.emit("flatline")

    # --- os quickhacks -------------------------------------------------------
    def target_at(self, x, y, radius=None):
        """O inimigo mais perto do ponto, dentro do raio da mira assistida."""
        radius = radius if radius is not None else self.bal["aim_radius"]
        best, best_d = None, None
        for e in self.enemies:
            if e.dead:
                continue
            d = dist2(e.x, e.y, x, y) - e.radius ** 2
            if d <= radius ** 2 and (best_d is None or d < best_d):
                best, best_d = e, d
        return best

    def slot_cost(self, index: int, target=None) -> float:
        hid = self.slots[index].hack
        h = self.c.hacks[hid]
        if h.get("mode") in ("walk", "sandevistan"):
            return self.move_cost(hid)
        if hid == "contagion" and self.stats.flag("free_contagion") and target is not None and target.has("poison"):
            return 0.0
        return self.stats.ram_cost(hid, h)

    # --- o movimento (também é quickhack) ---------------------------------------
    def move_slot(self) -> int | None:
        """O primeiro hack de movimento do deck (o do botão esquerdo)."""
        for i, s in enumerate(self.slots):
            if s.hack and self.c.hacks[s.hack]["kind"] == "movimento":
                return i
        return None

    def move_cost(self, hid) -> float:
        """A RAM por segundo dos movimentos de segurar (Andar, Sandevistan)."""
        h = self.c.hacks[hid]
        cost = (h["ram"] + self.stats.hack_mod(hid, "ram")) * (1 - min(0.6, self.mods.stats["ram_cost_pct"]))
        return max(0.05, cost)

    def _slowmo_factor(self) -> float:
        for s in self.slots:
            if s.hack and self.c.hacks[s.hack].get("mode") == "sandevistan":
                h = self.c.hacks[s.hack]
                return min(0.85, h["slow"] + self.stats.hack_mod(s.hack, "slow"))
        return 0.0

    def _walk(self, inp, dt):
        p = self.player
        for index in inp.held:
            if not 0 <= index < len(self.slots) or not self.slots[index].hack:
                continue
            hid = self.slots[index].hack
            h = self.c.hacks[hid]
            if h.get("mode") not in ("walk", "sandevistan"):
                continue
            dx, dy = inp.aim[0] - p.x, inp.aim[1] - p.y
            d = math.hypot(dx, dy)
            if d <= 2:
                return
            cost = self.move_cost(hid) * dt
            if p.ram < cost:
                self.emit("denied", index, "sem RAM")
                return
            p.ram -= cost
            speed = self.stats.speed * h.get("speed", 1.0) * (1 + self.stats.hack_mod(hid, "speed"))
            step = min(d, speed * dt)
            p.x += dx / d * step
            p.y += dy / d * step
            p.facing = math.atan2(dy, dx)
            p.moving = True
            p.slowmo = h["mode"] == "sandevistan"
            return

    def _move_hack(self, index, hid, h, aim) -> bool:
        """Os movimentos de clique: o Kerenzikov (arrancada) e o Teleporte."""
        p = self.player
        mode = h["mode"]
        if mode in ("walk", "sandevistan"):
            return False
        if mode == "dash" and p.rooted > 0:
            self.emit("denied", index, "paralisada")
            return False
        cost = self.stats.ram_cost(hid, h)
        if p.ram + 1e-9 < cost:
            self.emit("denied", index, "sem RAM")
            return False
        p.ram -= cost
        slot = self.slots[index]
        slot.total = self.stats.cooldown_of(hid, h)
        slot.cooldown = slot.total
        dx, dy = aim[0] - p.x, aim[1] - p.y
        d = math.hypot(dx, dy) or 1.0
        if mode == "dash":
            distance = h["distance"] * (1 + self.stats.hack_mod(hid, "range"))
            speed = distance / h["time"]
            p.dash_v = (dx / d * speed, dy / d * speed)
            p.dash_t = h["time"]
            p.invulnerable = max(p.invulnerable, h["time"] + 0.08)
            p.facing = math.atan2(dy, dx)
            if self.stats.hack_mod(hid, "damage"):
                self._dash_strike(hid, h, aim)
            self.emit("dash", p.x, p.y, p.x + dx / d * distance, p.y + dy / d * distance)
        else:
            reach = h["range"] * (1 + self.stats.hack_mod(hid, "range"))
            step = min(d, reach)
            x0, y0 = p.x, p.y
            r = self.stats.radius
            p.x = min(self.W - r, max(r, p.x + dx / d * step))
            p.y = min(self.H - r, max(r, p.y + dy / d * step))
            p.rooted = 0.0
            radius = h["radius"] + self.stats.hack_mod(hid, "radius")
            dmg = h["damage"] * (1 + self.stats.hack_mod(hid, "damage")) * self.stats.damage_mult(None, ())
            for e in self.enemies_near(p.x, p.y, radius):
                ex, ey = e.x - p.x, e.y - p.y
                ed = math.hypot(ex, ey) or 1.0
                if not e.boss:
                    e.x = min(self.W - e.radius, max(e.radius, e.x + ex / ed * h["push"]))
                    e.y = min(self.H - e.radius, max(e.radius, e.y + ey / ed * h["push"]))
                self.hurt(e, dmg, hid, (), can_crit=False, color="violet")
            self.emit("blink", x0, y0, p.x, p.y, radius)
        self.emit("cast", index, hid, False)
        return True

    def _dash_strike(self, hid, h, aim):
        """Árvore do Kerenzikov: quem estiver no caminho da arrancada toma dano."""
        p = self.player
        dx, dy = p.dash_v
        length = math.hypot(dx, dy) * h["time"] or 1.0
        ux, uy = dx / (length / h["time"]), dy / (length / h["time"])
        dmg = 20 * self.stats.hack_mod(hid, "damage") * self.stats.damage_mult(None, ())
        for e in self.enemies:
            ex, ey = e.x - p.x, e.y - p.y
            along = ex * ux + ey * uy
            if 0 <= along <= length and abs(ex * uy - ey * ux) <= e.radius + 18:
                self.hurt(e, dmg, hid, (), color="yellow")

    def cast(self, index: int, aim) -> bool:
        if not 0 <= index < len(self.slots) or not self.slots[index].hack:
            return False
        slot = self.slots[index]
        hid = slot.hack
        h = self.c.hacks[hid]
        if h["kind"] == "movimento":
            if slot.cooldown > 0 and h["mode"] in ("dash", "blink"):
                self.emit("denied", index, "recarga")
                return False
            return self._move_hack(index, hid, h, aim)
        if slot.cooldown > 0:
            self.emit("denied", index, "recarga")
            return False
        target = None
        if h["target"] == "enemy":
            target = self.target_at(*aim)
            if target is None:
                self.emit("denied", index, "sem alvo")
                return False
        cost = self.slot_cost(index, target)
        if self.player.ram + 1e-9 < cost:
            self.emit("denied", index, "sem RAM")
            return False
        self.player.ram -= cost
        slot.total = self.stats.cooldown_of(hid, h)
        slot.cooldown = slot.total
        self.casts += 1
        mult = 1.0
        if self.stats.flag("fifth_triple") and self.casts % 5 == 0:
            mult = 3.0
        point = (target.x, target.y) if target else (aim[0], aim[1])
        self.uploads.append(Upload(hid, index, target, point, self.stats.upload_of(hid, h), cost, mult))
        self.emit("cast", index, hid, mult > 1)
        return True

    def refund(self, ram: float):
        self.player.ram = min(self.stats.max_ram, self.player.ram + ram)

    def _update_uploads(self, dt):
        keep = []
        for u in self.uploads:
            if u.target is not None and u.target.dead:
                self.refund(u.cost)
                self.emit("fizzle", u.point[0], u.point[1])
                continue
            if u.target is not None:
                u.point = (u.target.x, u.target.y)
            u.t += dt
            if u.t < u.total:
                keep.append(u)
                continue
            h = self.c.hacks[u.hack]
            mult = self.stats.damage_mult(u.hack, h["tags"]) * u.mult
            hacks.EFFECTS[u.hack](self, u.hack, h, u.target, u.point, mult)
            self.emit("landed", u.hack, u.point[0], u.point[1], h["color"], u.mult > 1)
        self.uploads = keep

    def enemies_near(self, x, y, radius):
        r2 = radius * radius
        return [e for e in self.enemies if not e.dead and dist2(e.x, e.y, x, y) <= r2 + e.radius * e.radius]

    def apply_effect(self, e, name, seconds, value=1.0):
        if e.dead or seconds <= 0:
            return
        old = e.fx.get(name)
        if old:
            old[0] = max(old[0], seconds)
            old[1] = max(old[1], value)
        else:
            e.fx[name] = [seconds, value]
        if name in ("root", "stun") and e.state in ("windup", "dash", "upload"):
            e.state = "walk"
            e.state_t = 0.0

    def apply_dot(self, e, kind, dps, seconds):
        self.apply_effect(e, kind, seconds, dps)

    def chain(self, hid, h, first, damage, jumps, jump_range, falloff, color, shock=False, origin=None, crit=True):
        tags = h.get("tags", ["cadeia"]) if h else ["cadeia"]
        st = self.stats
        no_falloff = st.flag("no_falloff")
        refund = st.flag("jump_refund")
        fagulha = shock and st.flag("fagulha")
        hit = [first]
        points = [origin or (self.player.x, self.player.y), (first.x, first.y)]
        self.hurt(first, damage, hid, tags, can_crit=crit, color=color)
        if fagulha and not first.dead:
            self.apply_dot(first, "burn", 6 * st.damage_mult(None, ["cadeia"]), st.dot_time(3))
        current = first
        r2 = jump_range * jump_range
        for _ in range(jumps):
            best, best_d = None, None
            for e in self.enemies:
                if e.dead or e in hit:
                    continue
                d = dist2(e.x, e.y, current.x, current.y)
                if d <= r2 and (best_d is None or d < best_d):
                    best, best_d = e, d
            if best is None:
                break
            if not no_falloff:
                damage *= falloff
            self.hurt(best, damage, hid, tags, can_crit=crit, color=color)
            if fagulha and not best.dead:
                self.apply_dot(best, "burn", 6 * st.damage_mult(None, ["cadeia"]), st.dot_time(3))
            if refund:
                self.refund(refund)
            hit.append(best)
            points.append((best.x, best.y))
            current = best
        self.emit("chain", points, color)
        return hit

    # --- dano ----------------------------------------------------------------
    def hurt(self, e, amount, hack_id=None, tags=(), can_crit=True, color="white", heavy=False, source="hack"):
        """Dano num ICE. source: hack (pode critar), dot (veneno/fogo) ou minion (ICE confuso batendo)."""
        if e.dead or e.invulnerable or amount <= 0:
            return 0.0
        st = self.stats
        fx = e.fx
        mult = 1.0
        if "marked" in fx:
            mult += fx["marked"][1]
        imuno = st.flag("imuno")
        if imuno and "poison" in fx:
            mult += imuno
        vuln = st.flag("vuln_control")
        if vuln and e.controlled():
            mult += vuln
        if st.damage_ai and e.kind in ("ai", "netrunner"):
            mult += st.damage_ai
        execute = st.flag("execute")
        if execute:
            mult += execute * (1 - e.hp / e.max_hp)
        mult += self.lone_wolf
        if source == "dot":
            mult *= 1 + st.dot
        crit = False
        if can_crit and source == "hack" and self.rng.random() < st.crit_chance:
            crit = True
            amount *= st.crit_mult
        dmg = amount * mult
        e.hp -= dmg
        e.flash = 0.08
        self.damage_dealt += dmg
        if st.lifesteal > 0 and source != "minion" and self.lifesteal_left > 0:
            heal = min(dmg * st.lifesteal, self.lifesteal_left)
            self.lifesteal_left -= heal
            self.player.hp = min(st.max_hp, self.player.hp + heal)
        if source == "hack":
            self.emit("hit", e.x, e.y - e.radius, dmg, crit, color, heavy)
        else:
            e.dot_acc += dmg
        if e.hp <= 0:
            self.kill(e)
        else:
            stun = st.flag("crit_stun")
            if crit and stun:
                self.apply_effect(e, "stun", stun * (hacks.BOSS_CONTROL if e.boss else 1.0), 1)
            self.check_execute(e)
        return dmg

    def check_execute(self, e, from_control=False):
        if e.dead or e.boss:
            return
        frac = e.hp / e.max_hp
        st = self.stats
        limit = st.flag("control_execute") if e.controlled() else 0.0
        if from_control:
            limit = max(limit, st.flag("execucao"))
        if limit and frac < limit:
            self.emit("execute", e.x, e.y)
            self.kill(e)

    def kill(self, e):
        if e.dead:
            return
        if e.boss and not e.revived and any(a["type"] == "revive" for a in e.d["attacks"]):
            revive = next(a for a in e.d["attacks"] if a["type"] == "revive")
            e.revived = True
            e.state = "rebuild"
            e.state_t = revive["time"]
            e.mem["revive_hp"] = revive["hp"]
            e.invulnerable = True
            e.hp = 1.0
            e.fx.clear()
            self.emit("rebuild", e.x, e.y)
            return
        e.dead = True
        self.kills += 1
        value = e.ed * self.plan.ed * (1 + self.stats.ed)
        orbs = 1 if value < 6 else min(10, int(value / 4))
        for _ in range(orbs):
            angle = self.rng.random() * TAU
            speed = self.rng.uniform(30, 120) if orbs > 1 else 0.0
            self.pickups.append(Pickup(e.x, e.y, value / orbs, math.cos(angle) * speed, math.sin(angle) * speed))
        self.emit("kill", e.x, e.y, e.d["color"], e.radius, e.boss)
        st = self.stats
        if "poison" in e.fx and st.flag("epidemia"):
            dps = e.fx["poison"][1]
            for o in self.enemies_near(e.x, e.y, 130):
                if o is not e:
                    self.apply_dot(o, "poison", dps, st.dot_time(3))
            self.emit("ring", e.x, e.y, 130, "green")
        refund = st.flag("control_refund")
        if refund and e.controlled():
            self.refund(refund)
        if e.boss:
            self._boss_down(e)

    def _boss_down(self, e):
        self.emit("boss_down", e.type)
        self._end_wave()
        if self.cfg.mode == "layer":
            self.phase = "over"
            self.result = "victory"
        else:
            self._after_wave()

    def hurt_player(self, amount, ignore_invulnerable=False):
        p = self.player
        if amount <= 0 or self.phase != "wave":
            return
        if p.invulnerable > 0 and not ignore_invulnerable:
            return
        dmg = amount * self.stats.armor_factor()
        p.hp -= dmg
        self.damage_taken += dmg
        self.hit_this_wave = True
        if not ignore_invulnerable:
            p.invulnerable = self.stats.invulnerable
            self.emit("hurt", dmg)

    def drain_player(self, ram, delay):
        p = self.player
        p.ram = max(0.0, p.ram - ram)
        for s in self.slots:
            if s.hack:
                s.cooldown += delay
                s.total = max(s.total, s.cooldown)
        self.emit("drained", ram)

    # --- os ICE --------------------------------------------------------------
    def _update_spawns(self, dt):
        keep = []
        for s in self.spawns:
            s.t += dt
            if s.t >= s.total:
                self._spawn_enemy(s.type, s.x, s.y, s.boss)
            else:
                keep.append(s)
        self.spawns = keep

    def _move(self, e, tx, ty, speed, dt, away=False):
        dx, dy = tx - e.x, ty - e.y
        d = math.hypot(dx, dy)
        if d < 1e-6:
            return
        if away:
            dx, dy = -dx, -dy
        e.x += dx / d * speed * dt
        e.y += dy / d * speed * dt
        e.angle = math.atan2(dy, dx)
        r = e.radius
        e.x = min(self.W - r, max(r, e.x))
        e.y = min(self.H - r, max(r, e.y))

    def _nearest_other(self, e):
        best, best_d = None, None
        for o in self.enemies:
            if o is e or o.dead:
                continue
            d = dist2(o.x, o.y, e.x, e.y)
            if best_d is None or d < best_d:
                best, best_d = o, d
        return best

    def _shoot(self, x, y, angle, speed, damage, color, radius=5.0):
        self.bullets.append(Bullet(x, y, math.cos(angle) * speed, math.sin(angle) * speed, damage, color, radius))

    def _update_enemy(self, e, dt):
        e.flash = max(0.0, e.flash - dt)
        # os efeitos
        for name in list(e.fx):
            entry = e.fx.get(name)
            if entry is None:      # o dano anterior pode ter limpado os efeitos (o Liche se reconstruindo)
                continue
            entry[0] -= dt
            if name == "burn" or name == "poison":
                self.hurt(e, entry[1] * dt, None, (), can_crit=False, source="dot")
                if e.dead:
                    return
            if entry[0] <= 0:
                e.fx.pop(name, None)
        e.dot_t += dt
        if e.dot_t >= 0.45:
            if e.dot_acc >= 0.5:
                self.emit("dot", e.x, e.y - e.radius, e.dot_acc)
            e.dot_acc = 0.0
            e.dot_t = 0.0
        if e.boss:
            self._update_boss(e, dt)
            return
        fx = e.fx
        p = self.player
        stunned = "stun" in fx
        rooted = stunned or "root" in fx
        mad = "confused" in fx or "berserk" in fx
        blind = "blind" in fx
        speed = e.speed * (1 - min(0.8, e.effect("slow")))
        if "berserk" in fx:
            speed *= 1.3
        d = e.d
        ai = d["ai"]
        dpx, dpy = p.x - e.x, p.y - e.y
        dp = math.hypot(dpx, dpy)
        if ai == "node":
            e.timer -= dt
            if e.timer <= 0:
                e.timer = d["spawn_every"]
                if len(self.enemies) + len(self.spawns) < self.bal["waves"]["max_alive"]:
                    self.spawns.append(Spawn(e.x + self.rng.uniform(-30, 30), e.y + self.rng.uniform(-30, 30),
                                             d["spawn"], 0.6))
            return
        tx, ty = p.x, p.y
        node = self.node
        if node is not None and node.hp > 0 and ai in ("chase", "swarm", "paralyzer", "dropper", "charger"):
            if dist2(e.x, e.y, node.x, node.y) < dp * dp:
                tx, ty = node.x, node.y
            if dist2(e.x, e.y, node.x, node.y) <= (e.radius + node.radius) ** 2 and "stun" not in fx:
                node.hp -= e.damage * (1 - e.effect("weaken")) * 1.5 * dt
                if node.hp <= 0:
                    self._node_down()
                    return
        # para onde ir
        if mad:
            other = self._nearest_other(e)
            if other and not rooted:
                self._move(e, other.x, other.y, speed, dt)
            if other and dist2(other.x, other.y, e.x, e.y) <= (other.radius + e.radius + 4) ** 2:
                factor = fx["berserk"][1] if "berserk" in fx else 2.0
                self.hurt(other, e.damage * factor * dt, None, (), can_crit=False, source="minion")
            return
        if stunned:
            e.state = "walk"
            return
        if blind and ai not in ("ranged", "hacker"):
            e.wander -= dt
            if e.wander <= 0:
                e.wander = self.rng.uniform(0.6, 1.4)
                e.angle = self.rng.random() * TAU
            if not rooted:
                self._move(e, e.x + math.cos(e.angle) * 50, e.y + math.sin(e.angle) * 50, speed * 0.6, dt)
            return
        if ai in ("chase", "paralyzer", "dropper"):
            if not rooted:
                self._move(e, tx, ty, speed, dt)
            if ai == "dropper":
                e.timer -= dt
                if e.timer <= 0:
                    e.timer = d["drop_every"]
                    self.zones.append(Zone(e.x, e.y, d["puddle_radius"], d["puddle_life"], "puddle",
                                           d["puddle_dps"] * self.plan.damage))
        elif ai == "swarm":
            if not rooted:
                e.phase += dt * 4
                wob = math.sin(e.phase) * 0.6
                ang = math.atan2(ty - e.y, tx - e.x) + wob
                self._move(e, e.x + math.cos(ang) * 50, e.y + math.sin(ang) * 50, speed, dt)
        elif ai == "ranged" or ai == "hacker":
            want = d["range"]
            if not rooted:
                if dp > want + 30:
                    self._move(e, p.x, p.y, speed, dt)
                elif dp < want - 50:
                    self._move(e, p.x, p.y, speed * 0.8, dt, away=True)
                else:
                    ang = math.atan2(dpy, dpx) + math.pi / 2 * (1 if e.uid % 2 else -1)
                    self._move(e, e.x + math.cos(ang) * 50, e.y + math.sin(ang) * 50, speed * 0.4, dt)
            if ai == "ranged":
                e.timer -= dt
                if e.timer <= 0:
                    e.timer = d["fire_every"]
                    ang = math.atan2(dpy, dpx)
                    if blind:
                        ang += self.rng.uniform(-0.9, 0.9) + (0.5 if self.rng.random() < 0.5 else -0.5)
                    dmg = d["bullet_damage"] * self.plan.damage * (1 - e.effect("weaken"))
                    self._shoot(e.x, e.y, ang, d["bullet_speed"], dmg, d["color"])
            else:
                self._update_hacker(e, dt, dp, blind)
        elif ai == "charger":
            self._update_charger(e, dt, d["charge_every"], d["windup"], d["charge_speed"], d["charge_time"], speed,
                                 rooted, (tx, ty))
        # encostar machuca
        if dp <= e.radius + self.stats.radius:
            dmg = e.damage * (1 - e.effect("weaken"))
            if p.invulnerable <= 0:
                self.hurt_player(dmg)
                if ai == "paralyzer" and p.root_immune <= 0:
                    p.rooted = d["paralyze"]
                    p.root_immune = d["paralyze"] + 1.0
                    self.emit("paralyzed")

    def _update_charger(self, e, dt, every, windup, dash_speed, dash_time, speed, rooted, target=None):
        p = self.player
        tx, ty = target if target else (p.x, p.y)
        if e.state == "windup":
            e.state_t -= dt
            if e.state_t <= 0:
                e.state = "dash"
                e.state_t = dash_time
            return
        if e.state == "dash":
            e.state_t -= dt
            if not rooted:
                e.x += e.dir[0] * dash_speed * dt
                e.y += e.dir[1] * dash_speed * dt
                r = e.radius
                e.x = min(self.W - r, max(r, e.x))
                e.y = min(self.H - r, max(r, e.y))
            if e.state_t <= 0:
                e.state = "walk"
                e.timer = every
            return
        if not rooted:
            self._move(e, tx, ty, speed, dt)
        e.timer -= dt
        if e.timer <= 0 and dist2(e.x, e.y, tx, ty) < 480 ** 2:
            dx, dy = tx - e.x, ty - e.y
            d = math.hypot(dx, dy) or 1.0
            e.dir = (dx / d, dy / d)
            e.angle = math.atan2(dy, dx)
            e.state = "windup"
            e.state_t = windup
            self.emit("windup", e.uid)

    def _update_hacker(self, e, dt, dp, blind):
        d = e.d
        if e.state == "upload":
            if blind:
                e.state = "walk"
                e.hack_t = d["hack_every"]
                return
            e.state_t -= dt
            if e.state_t <= 0:
                e.state = "walk"
                e.hack_t = d["hack_every"]
                self.drain_player(d["drain"], d["delay"])
            return
        e.hack_t -= dt
        if e.hack_t <= 0 and dp < 650 and not blind:
            e.state = "upload"
            e.state_t = d["hack_upload"]
            self.emit("hacking", e.uid)

    def _update_boss(self, e, dt):
        p = self.player
        d = e.d
        if e.state == "rebuild":
            e.state_t -= dt
            if e.state_t <= 0:
                e.state = "walk"
                e.invulnerable = False
                e.hp = e.max_hp * e.mem.get("revive_hp", 0.5)
                self.emit("revived", e.x, e.y)
            return
        if "stun" in e.fx:
            if e.state in ("windup", "dash"):
                e.state = "walk"
            return
        rooted = "root" in e.fx
        speed = e.speed * (1 - min(0.6, e.effect("slow")))
        dx, dy = p.x - e.x, p.y - e.y
        dp = math.hypot(dx, dy) or 1.0
        aim = math.atan2(dy, dx)
        phase2 = d.get("phase2", 1.0) if e.hp < e.max_hp * 0.5 else 1.0
        weak = 1 - e.effect("weaken")
        # a carga (ataque 'charge') usa o mesmo estado do Sabertooth
        if e.state in ("windup", "dash"):
            charge = e.mem["charge"]
            self._update_charger(e, dt, charge["every"], charge["windup"], charge["speed"], charge["time"], speed,
                                 rooted)
            if e.state == "walk":
                e.timer = 999.0
        elif not rooted:
            if dp > 260:
                self._move(e, p.x, p.y, speed, dt)
            elif dp < 170:
                self._move(e, p.x, p.y, speed * 0.7, dt, away=True)
            else:
                ang = aim + math.pi / 2
                self._move(e, e.x + math.cos(ang) * 50, e.y + math.sin(ang) * 50, speed * 0.5, dt)
        # a espiral em andamento
        if e.spiral > 0:
            spiral = e.mem["spiral"]
            e.spiral -= dt
            e.mem["spiral_t"] = e.mem.get("spiral_t", 0.0) - dt
            while e.mem["spiral_t"] <= 0:
                e.mem["spiral_t"] += spiral["rate"]
                e.mem["spiral_angle"] = e.mem.get("spiral_angle", 0.0) + math.radians(spiral["turn"])
                for arm in (0, math.pi):
                    self._shoot(e.x, e.y, e.mem["spiral_angle"] + arm, spiral["speed"],
                                spiral["damage"] * self.plan.damage * weak, d["color"])
        # o roubo de RAM em andamento
        drain = e.mem.get("drain")
        if drain:
            drain[0] -= dt
            if drain[0] <= 0:
                del e.mem["drain"]
                if "blind" not in e.fx:
                    self.drain_player(drain[1], drain[2])
        # os ataques
        for i, a in enumerate(d["attacks"]):
            kind = a["type"]
            if kind == "revive":
                continue
            e.attack_t[i] -= dt / phase2
            if e.attack_t[i] > 0:
                continue
            e.attack_t[i] = a["every"]
            dmg = a.get("damage", 0) * self.plan.damage * weak
            if kind == "radial":
                n = a["bullets"]
                offset = e.mem.get("radial", 0.0)
                e.mem["radial"] = offset + math.pi / n
                for k in range(n):
                    self._shoot(e.x, e.y, offset + TAU * k / n, a["speed"], dmg, d["color"], 6.0)
            elif kind == "volley":
                n = a["bullets"]
                spread = math.radians(a["spread"])
                for k in range(n):
                    t = (k / (n - 1) - 0.5) if n > 1 else 0.0
                    self._shoot(e.x, e.y, aim + spread * t, a["speed"], dmg, d["color"])
            elif kind == "spiral":
                e.spiral = a["time"]
                e.mem["spiral"] = a
                e.mem["spiral_t"] = 0.0
            elif kind == "summon":
                alive = len(self.enemies) + len(self.spawns)
                count = min(a["count"], self.bal["waves"]["max_alive"] - alive)
                for k in range(count):
                    ang = TAU * k / max(1, count) + self.rng.random()
                    sx = min(self.W - 20, max(20, e.x + math.cos(ang) * (e.radius + 30)))
                    sy = min(self.H - 20, max(20, e.y + math.sin(ang) * (e.radius + 30)))
                    self.spawns.append(Spawn(sx, sy, a["enemy"], 0.5))
                self.emit("summon", e.x, e.y)
            elif kind == "charge" and e.state == "walk" and not rooted:
                e.mem["charge"] = a
                e.dir = (dx / dp, dy / dp)
                e.state = "windup"
                e.state_t = a["windup"]
                self.emit("windup", e.uid)
            elif kind == "drain" and "drain" not in e.mem:
                e.mem["drain"] = [1.0, a["drain"], a["delay"]]
                self.emit("hacking", e.uid)
        if dp <= e.radius + self.stats.radius and p.invulnerable <= 0:
            self.hurt_player(e.damage * weak)

    def _separate(self):
        es = self.enemies
        n = len(es)
        for i in range(n):
            a = es[i]
            for j in range(i + 1, n):
                b = es[j]
                rr = a.radius + b.radius
                dx = b.x - a.x
                if dx > rr or dx < -rr:
                    continue
                dy = b.y - a.y
                if dy > rr or dy < -rr:
                    continue
                d2 = dx * dx + dy * dy
                if d2 >= rr * rr or d2 < 1e-9:
                    continue
                d = math.sqrt(d2)
                push = (rr - d) / d * 0.5
                if a.boss:
                    b.x += dx * push * 2
                    b.y += dy * push * 2
                elif b.boss:
                    a.x -= dx * push * 2
                    a.y -= dy * push * 2
                else:
                    a.x -= dx * push
                    a.y -= dy * push
                    b.x += dx * push
                    b.y += dy * push

    def _update_bullets(self, dt):
        p = self.player
        pr = self.stats.radius
        keep = []
        for b in self.bullets:
            b.x += b.vx * dt
            b.y += b.vy * dt
            b.life -= dt
            if b.life <= 0 or b.x < -20 or b.y < -20 or b.x > self.W + 20 or b.y > self.H + 20:
                continue
            if p.invulnerable <= 0 and dist2(b.x, b.y, p.x, p.y) <= (b.radius + pr) ** 2:
                self.hurt_player(b.damage)
                continue
            keep.append(b)
        self.bullets = keep

    def _update_zones(self, dt):
        p = self.player
        keep = []
        for z in self.zones:
            z.life -= dt
            if z.life <= 0:
                continue
            keep.append(z)
            if z.kind == "puddle":
                if dist2(z.x, z.y, p.x, p.y) <= (z.radius + self.stats.radius * 0.5) ** 2:
                    self.hurt_player(z.value * dt, ignore_invulnerable=True)
            else:
                for e in self.enemies_near(z.x, z.y, z.radius):
                    self.apply_dot(e, "poison", z.value, 1.2)
        self.zones = keep

    def _update_pickups(self, dt):
        p = self.player
        reach2 = self.stats.pickup ** 2
        grab2 = (self.stats.radius + 8) ** 2
        keep = []
        for pk in self.pickups:
            if pk.vx or pk.vy:
                pk.x += pk.vx * dt
                pk.y += pk.vy * dt
                pk.vx *= 0.9
                pk.vy *= 0.9
                if abs(pk.vx) < 2 and abs(pk.vy) < 2:
                    pk.vx = pk.vy = 0.0
            d2 = dist2(pk.x, pk.y, p.x, p.y)
            if d2 <= reach2:
                pk.pulled = True
            if pk.pulled:
                d = math.sqrt(d2) or 1.0
                speed = 520 * dt
                pk.x += (p.x - pk.x) / d * min(d, speed)
                pk.y += (p.y - pk.y) / d * min(d, speed)
                d2 = dist2(pk.x, pk.y, p.x, p.y)
            if d2 <= grab2:
                self.ed += pk.value
                self.emit("pickup", pk.value)
                continue
            keep.append(pk)
        self.pickups = keep

    # --- o ataque automático da build ---------------------------------------
    def _update_auto(self, dt):
        tag = self.auto
        st = self.stats
        if tag is None:
            return
        auto = self.c.builds[tag]["auto"]
        p = self.player
        mult = st.damage_mult(None, [tag]) * (1 + 0.1 * self.counts[tag])
        if tag == "controle":
            for e in self.enemies_near(p.x, p.y, auto["radius"]):
                self.apply_effect(e, "slow", 0.15, auto["slow"])
            return
        self.auto_t += dt
        if tag == "contagio":
            if self.auto_t >= auto["every"]:
                self.auto_t = 0.0
                if dist2(p.x, p.y, *self.trail_from) > 100:
                    self.trail_from = (p.x, p.y)
                    self.zones.append(Zone(p.x, p.y, auto["radius"], auto["life"], "trail", auto["dps"] * mult))
            spread = st.flag("auto_spread")
            if spread:
                self.spread_t += dt
                if self.spread_t >= 2.0:
                    self.spread_t = 0.0
                    self._auto_spread()
            return
        if self.auto_t < auto["every"]:
            return
        self.auto_t = 0.0
        if tag == "sobrecarga":
            near = self.enemies_near(p.x, p.y, auto["range"])
            if near:
                target = max(near, key=lambda e: e.hp)
                self.emit("bolt_from", p.x, p.y, target.x, target.y, "orange")
                self.hurt(target, auto["damage"] * mult, None, ["sobrecarga"], color="orange", heavy=True)
        elif tag == "cadeia":
            target = None
            best = auto["range"] ** 2
            for e in self.enemies:
                d = dist2(e.x, e.y, p.x, p.y)
                if d <= best:
                    target, best = e, d
            if target:
                jumps = auto["targets"] - 1 + int(st.flag("extra_jump"))
                self.chain(None, None, target, auto["damage"] * mult, jumps, 170, 0.85, "cyan", shock=True)

    def _auto_spread(self):
        poisoned = [e for e in self.enemies if "poison" in e.fx and not e.dead]
        self.rng.shuffle(poisoned)
        for e in poisoned[:3]:
            best, best_d = None, 150 ** 2
            for o in self.enemies:
                if o is e or o.dead or "poison" in o.fx:
                    continue
                d = dist2(o.x, o.y, e.x, e.y)
                if d < best_d:
                    best, best_d = o, d
            if best:
                dps = e.fx["poison"][1]
                self.apply_dot(best, "poison", dps, self.stats.dot_time(3))
                self.emit("link", e.x, e.y, best.x, best.y, "green")

    # --- o objetivo da missão ------------------------------------------------
    def _update_objective(self, dt):
        if not self.mission:
            return
        self.mission_time += dt
        node = self.node
        if node is not None and node.moving:
            # o programa anda conforme a missão avança (as ondas vencidas e os ICE derrubados)
            target = 70 + (self.W - 140) * self.mission_progress()
            step = 60 * dt
            node.x += max(-step, min(step, target - node.x))

    def mission_progress(self) -> float:
        """Quanto da missão já foi: as ondas vencidas mais a parte derrubada da onda atual."""
        if not self.mission:
            return 0.0
        frac = 0.0
        if self.phase == "wave" and self.wave_total:
            frac = 1 - min(1.0, self.remaining() / self.wave_total)
        return min(1.0, (self.waves_cleared + frac) / self.mission["waves"])

    def _node_down(self):
        self.emit("node_down")
        self.phase = "over"
        self.result = "failed"

    # --- os aliados ----------------------------------------------------------
    def _update_allies(self, dt):
        if not self.allies:
            return
        p = self.player
        st = self.stats
        cfg = self.c.story["ally_level"]
        n = len(self.allies)
        for a in self.allies:
            a.flash = max(0.0, a.flash - dt)
            angle = TAU * a.slot / n + self.time * 0.4
            gx = p.x + math.cos(angle) * 56
            gy = p.y + math.sin(angle) * 56
            a.x += (gx - a.x) * min(1.0, dt * 4)
            a.y += (gy - a.y) * min(1.0, dt * 4)
            if self.cfg.ally_pickup:
                r2 = self.cfg.ally_pickup ** 2
                for pk in self.pickups:
                    if dist2(pk.x, pk.y, a.x, a.y) <= r2:
                        pk.pulled = True
            a.timer -= dt
            if a.timer > 0:
                continue
            a.timer = a.d["every"]
            power = (1 + cfg["bonus"] * (a.level - 1)) * st.damage_mult(None, ())
            role = a.d["role"]
            color = a.d["color"]
            if role == "suporte":
                p.hp = min(st.max_hp, p.hp + st.max_hp * a.d["heal"] * (1 + cfg["bonus"] * (a.level - 1)))
                self.refund(a.d.get("ram", 0) * (1 + cfg["bonus"] * (a.level - 1)))
                self.emit("ally_heal", a.x, a.y, p.x, p.y, color)
                a.flash = 0.3
                continue
            near = self.enemies_near(a.x, a.y, 380)
            if not near:
                a.timer = 0.3
                continue
            if role == "controle":
                target = max(near, key=lambda e: len(self.enemies_near(e.x, e.y, a.d["radius"])))
                for e in self.enemies_near(target.x, target.y, a.d["radius"]):
                    self.hurt(e, a.d["damage"] * power, None, (), can_crit=False, color=color)
                    if not e.dead:
                        self.apply_effect(e, "stun", a.d["stun"] * (0.3 if e.boss else 1.0), 1)
                self.emit("ring", target.x, target.y, a.d["radius"], color)
            elif a.d.get("jumps", 0) > 0:
                target = min(near, key=lambda e: dist2(e.x, e.y, a.x, a.y))
                self.chain(None, None, target, a.d["damage"] * power, a.d["jumps"], 170, 0.85, color, origin=(a.x, a.y),
                           crit=False)
            else:
                target = max(near, key=lambda e: e.hp)
                self.emit("bolt_from", a.x, a.y, target.x, target.y, color)
                self.hurt(target, a.d["damage"] * power, None, (), can_crit=False, color=color, heavy=True)
                if not target.dead and a.d.get("stun"):
                    self.apply_effect(target, "stun", a.d["stun"] * (0.3 if target.boss else 1.0), 1)
            a.flash = 0.25
