import math
from collections import Counter

import pytest

from blackwall.sim import build, hacks, waves
from blackwall.sim.dive import Dive, DiveConfig, DiveInput
from blackwall.sim.stats import Mods, Stats
from helpers import cast, clear_wave, hush, put, quiet_dive, run


def still(e):
    e.speed = 0
    return e


# --- conteúdo -------------------------------------------------------------------
def test_every_attack_hack_has_an_effect(content):
    attack = {h for h, d in content.hacks.items() if d["kind"] != "movimento"}
    assert attack == set(hacks.EFFECTS)


def test_starting_hacks_are_walking_short_circuit_and_ping(content):
    assert sorted(h for h, d in content.hacks.items() if d["price"] == 0) == ["andar", "ping", "short_circuit"]


# --- o movimento é um quickhack ---------------------------------------------------
def test_clicking_marks_a_point_and_she_walks_there_over_time(content):
    dive = quiet_dive(content, loadout=("andar", "short_circuit"))
    p = dive.player
    x0 = p.x
    dive.player.ram = 5
    dive.stats.ram_regen = 0          # para ver o gasto de andar
    target = (p.x + 300, p.y)
    run(dive, 1 / 60, DiveInput(aim=target, cast=(0,)))       # um clique marca o destino
    assert p.dest is not None
    run(dive, 0.5, DiveInput(aim=(0, 0)))                     # o cursor sai, ela continua indo
    assert x0 + 50 < p.x < target[0]
    assert p.ram < 5
    run(dive, 2.0, DiveInput(aim=(0, 0)))
    assert p.x == pytest.approx(target[0], abs=3) and p.dest is None  # chegou e parou


def test_holding_drags_the_destination(content):
    dive = quiet_dive(content, loadout=("andar", "short_circuit"))
    p = dive.player
    run(dive, 0.3, DiveInput(aim=(p.x + 200, p.y + 100), held=(0,)))
    assert p.dest == pytest.approx((p.x + 0, p.y + 0), abs=400)
    assert p.dest[1] > dive.H / 2


def test_dash_cancels_the_walk(content):
    dive = quiet_dive(content, loadout=("andar", "kerenzikov"))
    p = dive.player
    dive.set_destination(0, (p.x + 300, p.y))
    assert dive.cast(1, (p.x, p.y + 300))
    assert p.dest is None


def test_without_ram_andar_does_not_move(content):
    dive = quiet_dive(content, loadout=("andar", "short_circuit"))
    dive.stats.ram_regen = 0
    dive.player.ram = 0
    x0 = dive.player.x
    dive.set_destination(0, (x0 + 400, dive.player.y))
    run(dive, 0.3)
    assert dive.player.x == x0


def test_kerenzikov_dashes_and_is_invulnerable_while_dashing(content):
    dive = quiet_dive(content, loadout=("kerenzikov", "short_circuit"))
    p = dive.player
    x0, ram = p.x, p.ram
    assert dive.cast(0, (p.x + 500, p.y))
    assert p.invulnerable > 0 and p.ram < ram
    run(dive, 0.3)
    assert p.x > x0 + 150
    assert not dive.cast(0, (p.x + 500, p.y))       # recarga


def test_teleporte_blinks_pushes_ice_and_works_while_paralyzed(content):
    dive = quiet_dive(content, loadout=("teleporte", "short_circuit"))
    p = dive.player
    p.rooted = 5
    e = put(dive, "sabertooth", p.x + 250, p.y + 30)
    e.speed = 0
    ex = e.x
    assert dive.cast(0, (p.x + 250, p.y))
    assert abs(p.x - (ex - 0)) < 60 and p.rooted == 0
    assert e.hp < e.max_hp


def test_sandevistan_slows_the_world(content):
    dive = quiet_dive(content, loadout=("sandevistan", "short_circuit"))
    p = dive.player
    a = put(dive, "hellhound", 100, 100)
    y0 = a.y
    run(dive, 0.5, DiveInput(aim=(p.x + 300, p.y), held=(0,)))
    slow = abs(a.y - y0) + abs(a.x - 100)
    assert p.moving
    dive2 = quiet_dive(content, loadout=("sandevistan", "short_circuit"))
    b = put(dive2, "hellhound", 100, 100)
    run(dive2, 0.5, DiveInput(aim=(dive2.player.x + 300, dive2.player.y)))
    normal = abs(b.y - 100) + abs(b.x - 100)
    assert slow < normal * 0.6


def test_aim_assist_picks_the_enemy_nearest_the_cursor(content):
    dive = quiet_dive(content)
    a = still(put(dive, "wisp", 100, 100))
    still(put(dive, "wisp", 300, 100))
    assert dive.target_at(130, 110) is a
    assert dive.target_at(700, 500) is None


def test_casting_without_a_target_spends_nothing(content):
    dive = quiet_dive(content)
    ram = dive.player.ram
    assert not dive.cast(0, (10, 10))
    assert dive.player.ram == ram
    assert dive.slots[0].cooldown == 0


# --- quickhacks ----------------------------------------------------------------
def test_short_circuit_spends_ram_starts_cooldown_and_hits_after_upload(content):
    dive = quiet_dive(content)
    e = still(put(dive, "hellhound", 200, 150))
    ram = dive.player.ram
    assert dive.cast(0, (e.x, e.y))
    assert dive.player.ram == pytest.approx(ram - 2)
    assert dive.slots[0].cooldown > 0
    assert e.hp == e.max_hp          # o upload ainda não chegou
    run(dive, 0.3)
    assert e.hp < e.max_hp


def test_cooldown_blocks_a_second_cast(content):
    dive = quiet_dive(content)
    e = still(put(dive, "sabertooth", 200, 150))
    assert dive.cast(0, (e.x, e.y))
    assert not dive.cast(0, (e.x, e.y))


def test_short_circuit_jumps_with_its_tree_and_the_cadeia_bonus(content):
    # o Arco extra da árvore do Short Circuit (permanente) dá +1 salto
    dive = quiet_dive(content, mods=Mods().add(content.hack_trees["short_circuit"]["arco_extra"]["effect"]))
    targets = [still(put(dive, "sabertooth", 200 + 60 * i, 120)) for i in range(5)]
    cast(dive, 0, targets[0], settle=0.4)
    assert len([e for e in targets if e.hp < e.max_hp]) == 2
    # com 2 ups de Cadeia, o bônus de conjunto dá mais um salto
    dive.taken["condutividade"] = 2
    dive.recompute()
    for e in targets:
        e.hp = e.max_hp
    dive.slots[0].cooldown = 0
    cast(dive, 0, targets[0], settle=0.4)
    assert len([e for e in targets if e.hp < e.max_hp]) == 3      # o alvo + 1 salto da árvore + 1 do bônus


def test_ping_marks_enemies_and_they_take_more_damage(content):
    dive = quiet_dive(content)
    e = still(put(dive, "sabertooth", 200, 150))
    dive.stats.crit_chance = 0
    before = e.hp
    dive.hurt(e, 10)
    plain = before - e.hp
    cast(dive, 1, e, settle=0.3)
    assert e.has("marked")
    before = e.hp
    dive.hurt(e, 10)
    assert before - e.hp == pytest.approx(plain * 1.25)


def test_contagion_poisons_and_spreads_to_two_neighbours(content):
    dive = quiet_dive(content, loadout=("contagion", "ping"))
    a = still(put(dive, "sabertooth", 200, 150))
    b = still(put(dive, "sabertooth", 260, 150))
    c = still(put(dive, "sabertooth", 200, 210))
    far = still(put(dive, "sabertooth", 900, 500))
    cast(dive, 0, a, settle=0.4)
    assert a.has("poison") and b.has("poison") and c.has("poison")
    assert not far.has("poison")
    hp = a.hp
    run(dive, 1.0)
    assert a.hp < hp


def test_sonic_shock_stuns_an_area_and_bosses_resist(content):
    dive = quiet_dive(content, loadout=("sonic_shock", "ping"))
    a = still(put(dive, "sabertooth", 200, 150))
    b = still(put(dive, "sabertooth", 250, 160))
    cast(dive, 0, a, settle=0.35)
    assert a.has("stun") and b.has("stun")
    normal = a.fx["stun"][0]
    boss = still(put(dive, "kraken", 700, 300, boss=True))
    dive.slots[0].cooldown = 0
    dive.player.ram = dive.stats.max_ram
    cast(dive, 0, boss, settle=0.35)
    assert boss.fx["stun"][0] < normal * 0.5


def test_system_reset_shuts_down_ice_but_only_stuns_a_boss(content):
    dive = quiet_dive(content, loadout=("system_reset", "ping"))
    e = still(put(dive, "sabertooth", 200, 150))
    cast(dive, 0, e, settle=1.0)
    assert e.dead
    boss = still(put(dive, "kraken", 700, 300, boss=True))
    dive.slots[0].cooldown = 0
    dive.player.ram = dive.stats.max_ram
    dive.cast(0, (boss.x, boss.y))
    run(dive, 0.9)
    assert not boss.dead and boss.has("stun")


def test_memory_wipe_does_not_work_on_bosses(content):
    dive = quiet_dive(content, loadout=("memory_wipe", "ping"))
    boss = still(put(dive, "kraken", 700, 300, boss=True))
    cast(dive, 0, boss, settle=0.6)
    assert not boss.has("confused")


def test_confused_ice_attacks_other_ice(content):
    dive = quiet_dive(content, loadout=("memory_wipe", "ping"))
    a = put(dive, "hellhound", 600, 120)
    b = still(put(dive, "sabertooth", 700, 120))
    cast(dive, 0, a, settle=0.55)
    assert a.has("confused")
    hp = b.hp
    run(dive, 2.0)
    assert b.hp < hp


def test_upload_fizzles_and_refunds_if_the_target_dies(content):
    dive = quiet_dive(content, loadout=("synapse_burnout", "ping"))
    e = still(put(dive, "wisp", 300, 150))
    ram = dive.player.ram
    dive.cast(0, (e.x, e.y))
    dive.kill(e)
    run(dive, 0.1)
    assert dive.player.ram == pytest.approx(ram, abs=0.5)


def test_ups_are_only_numbers(content):
    for up_id, up in content.ups.items():
        assert not up.get("hacks") and not up.get("flags"), up_id


def test_tag_cooldown_ups_speed_up_only_their_build(content):
    plain = Stats(content.balance, Mods())
    s = Stats(content.balance, Mods().merge(build.ups_mods(content, Counter({"sinapse_rapida": 2}))))
    sc = content.hacks["short_circuit"]
    burn = content.hacks["synapse_burnout"]
    assert s.cooldown_of("short_circuit", sc) < plain.cooldown_of("short_circuit", sc)
    assert s.cooldown_of("synapse_burnout", burn) == pytest.approx(plain.cooldown_of("synapse_burnout", burn))


def test_lifesteal_heals_but_is_capped_per_second(content):
    mods = Mods().add({"stats": {"lifesteal": 1.0}})
    dive = quiet_dive(content, mods=mods)
    dive.player.hp = 10
    e = still(put(dive, "sabertooth", 100, 100))
    run(dive, 1.0)
    dive.hurt(e, 80)
    cap = content.balance["limits"]["lifesteal_per_second"] * dive.stats.max_hp
    assert 10 < dive.player.hp <= 10 + cap + 1e-6


# --- as ondas ----------------------------------------------------------------
def test_wave_ends_after_its_duration_and_offers_ups(content):
    dive = quiet_dive(content)
    dive.player.hp = 5
    clear_wave(dive)
    assert dive.phase == "choice"
    assert len(dive.offer) == 3
    assert dive.player.hp == dive.stats.max_hp
    dive.choose(0)
    assert dive.phase == "wave" and dive.wave == 2


def test_waves_spawn_ice_on_their_own(content):
    dive = Dive(content, DiveConfig(seed=2))
    run(dive, 12)
    assert dive.enemies or dive.spawns


def test_solo_gets_four_choices(content):
    dive = quiet_dive(content, choices=4)
    clear_wave(dive)
    assert len(dive.offer) == 4


def test_wave_10_brings_the_layer_boss_and_killing_it_wins(content):
    dive = quiet_dive(content)
    dive.start_wave(10)
    assert dive.plan.boss == "kraken"
    assert dive.spawns and dive.spawns[0].boss
    hush(dive)
    run(dive, 2.0)
    assert dive.boss is not None
    dive.kill(dive.boss)
    assert dive.phase == "over" and dive.result == "victory"


def test_liche_rebuilds_once(content):
    dive = quiet_dive(content, layer=2)
    liche = still(put(dive, "liche", 600, 300, boss=True))
    dive.kill(liche)
    assert not liche.dead and liche.state == "rebuild"
    run(dive, 3.5)
    assert liche.hp == pytest.approx(liche.max_hp * 0.5)
    dive.kill(liche)
    assert liche.dead


def test_liche_killed_by_poison_rebuilds_without_breaking(content):
    dive = quiet_dive(content, layer=2)
    liche = still(put(dive, "liche", 600, 300, boss=True))
    liche.hp = 0.5
    dive.apply_dot(liche, "poison", 50, 3)
    dive.apply_dot(liche, "burn", 50, 3)
    run(dive, 0.5)
    assert liche.state == "rebuild" and not liche.dead


def test_netwatch_netrunner_steals_ram(content):
    dive = quiet_dive(content, layer=1)
    e = still(put(dive, "netrunner", 700, 300))
    e.hack_t = 0
    run(dive, 2.0)
    assert dive.player.ram < dive.stats.max_ram - 1
    assert dive.slots[0].cooldown > 0


def test_flatline_loses_a_quarter_of_the_ed(content):
    dive = quiet_dive(content)
    dive.ed = 100
    dive.player.hp = 0.1
    e = put(dive, "hellhound", dive.player.x + 5, dive.player.y)
    run(dive, 0.2)
    assert dive.result == "flatline"
    assert dive.ed_final == 75


def test_extracting_between_waves_keeps_all_the_ed(content):
    dive = quiet_dive(content)
    dive.ed = 100
    clear_wave(dive)
    dive.extract()
    assert dive.result == "extracted" and dive.ed_final == 100


def test_same_seed_same_dive(content):
    def play(seed):
        dive = Dive(content, DiveConfig(seed=seed, loadout=["andar", "short_circuit", "ping"]))
        for i in range(60 * 20):
            target = dive.enemies[0] if dive.enemies else None
            aim = (target.x, target.y) if target else (0, 0)
            dive.step(1 / 60, DiveInput(aim=aim, cast=(1,) if i % 30 == 0 else (), held=(0,)))
        return dive.kills, round(dive.player.hp, 3), len(dive.enemies)

    assert play(5) == play(5)


def test_infinite_mode_cycles_layers_and_grows(content):
    w5 = waves.plan(content, "infinite", 0, 5)
    w15 = waves.plan(content, "infinite", 0, 15)
    assert w5.layer == 0 and w15.layer == 1
    assert w15.hp > w5.hp * 1.5
    assert waves.plan(content, "infinite", 0, 20).boss == content.layers[1]["boss"]


# --- as builds -------------------------------------------------------------------
def test_build_ups_only_appear_for_builds_the_deck_can_do(content):
    weights = build.offer_weights(content, Counter(), ["short_circuit", "ping"], 1)
    for up_id in weights:
        tags = content.ups[up_id]["tags"]
        assert not tags or set(tags) & {"sobrecarga", "cadeia"}
        assert content.ups[up_id].get("requires_hack") in (None, "short_circuit")


def test_offers_lean_toward_the_build_you_picked(content):
    loadout = ["short_circuit", "contagion", "cripple_movement"]
    plain = build.offer_weights(content, Counter(), loadout, 3)
    guided = build.offer_weights(content, Counter({"virulencia": 3}), loadout, 3)
    assert guided["incubacao"] / guided["blindagem"] > plain["incubacao"] / plain["blindagem"] * 2


def test_set_bonuses_turn_on_at_2_4_6_and_auto_at_3(content):
    dive = quiet_dive(content, loadout=("contagion", "overheat"))
    dive.taken["virulencia"] = 2
    dive.recompute()
    assert [n for tag, n, _ in build.active_bonuses(content, dive.counts) if tag == "contagio"] == [2]
    assert dive.auto is None
    dive.taken["incubacao"] = 1
    dive.recompute()
    assert dive.auto == "contagio"
    dive.taken["incubacao"] = 3
    dive.taken["carga_toxica"] = 1
    dive.recompute()
    assert [n for tag, n, _ in build.active_bonuses(content, dive.counts) if tag == "contagio"] == [2, 4, 6]
    assert dive.stats.flag("free_contagion")


def test_a_build_is_stronger_but_other_hacks_still_work(content):
    plain = Stats(content.balance, Mods())
    taken = Counter({"capacitor": 3})
    s = Stats(content.balance, Mods().merge(build.ups_mods(content, taken)))
    boosted = s.damage_mult("synapse_burnout", ["sobrecarga"])
    other = s.damage_mult("cripple_movement", ["controle"])
    assert boosted > plain.damage_mult("synapse_burnout", ["sobrecarga"]) * 1.8
    assert other == pytest.approx(plain.damage_mult("cripple_movement", ["controle"]))


def test_sobrecarga_auto_attack_hits_the_toughest_ice(content):
    dive = quiet_dive(content, loadout=("synapse_burnout", "short_circuit"))
    dive.taken["capacitor"] = 3
    dive.recompute()
    assert dive.auto == "sobrecarga"
    weak = still(put(dive, "wisp", 500, 300))
    tough = still(put(dive, "sabertooth", 560, 300))
    run(dive, 3.2)
    assert tough.hp < tough.max_hp
    assert weak.hp == weak.max_hp


def test_controle_auto_attack_slows_nearby_ice(content):
    dive = quiet_dive(content, loadout=("cripple_movement", "sonic_shock"))
    dive.taken["persistencia"] = 3
    dive.recompute()
    p = dive.player
    e = put(dive, "hellhound", p.x + 100, p.y)
    run(dive, 0.1)
    assert e.has("slow")


def test_control_execute_finishes_low_controlled_ice(content):
    mods = Mods().add({"flags": {"control_execute": 0.15}})
    dive = quiet_dive(content, mods=mods)
    e = still(put(dive, "sabertooth", 600, 300))
    dive.apply_effect(e, "stun", 5)
    dive.hurt(e, e.max_hp * 0.9, can_crit=False)
    assert e.dead


def test_lone_wolf_grows_on_clean_waves(content):
    mods = Mods().add({"flags": {"lone_wolf": 0.05}})
    dive = quiet_dive(content, mods=mods)
    clear_wave(dive)
    assert dive.lone_wolf == pytest.approx(0.05)


# --- ondas com quantidade fixa -------------------------------------------------------
def test_a_wave_has_a_fixed_list_of_ice_and_ends_when_all_fall(content):
    dive = Dive(content, DiveConfig(seed=4))
    total = dive.wave_total
    assert total > 5 and dive.remaining() == total
    dive.player.invulnerable = 1e9
    for _ in range(60 * 60):
        dive.step(1 / 60)
        for e in list(dive.enemies):
            dive.kill(e)
        if dive.phase != "wave":
            break
    assert dive.phase == "choice"
    assert dive.kills == total


def test_the_wave_does_not_end_on_time_while_ice_is_alive(content):
    dive = quiet_dive(content)
    dive.queue.clear()
    e = put(dive, "sabertooth", 100, 100)
    e.speed = 0
    run(dive, dive.plan.duration + 5)
    assert dive.phase == "wave"


def test_reinforcements_arrive_if_the_wave_drags(content):
    dive = quiet_dive(content)
    dive.queue.clear()
    dive.plan.pool = content.layers[0]["pool"]
    dive.reinforcements = True
    e = put(dive, "sabertooth", 100, 100)
    e.speed = 0
    dive.player.invulnerable = 1e9
    run(dive, dive.plan.duration + content.balance["waves"]["reinforce_after"] - 1)
    assert len(dive.enemies) + len(dive.spawns) == 1
    run(dive, 2)
    assert dive.reinforcing and len(dive.enemies) + len(dive.spawns) > 1



def test_wisps_shoot_homing_bullets(content):
    dive = quiet_dive(content)
    w = put(dive, "wisp", 100, 100)
    w.speed = 0
    w.timer = 0
    run(dive, 0.05)
    assert dive.bullets and dive.bullets[0].homing > 0
    b = dive.bullets[0]
    p = dive.player
    p.y += 150                                   # ela sai do caminho; o tiro vira atrás
    angle_before = math.atan2(b.vy, b.vx)
    run(dive, 0.5)
    want = math.atan2(p.y - b.y, p.x - b.x)
    assert abs(math.atan2(b.vy, b.vx) - want) < abs(angle_before - want)


def test_no_attack_hack_recharges_in_under_a_second(content):
    for hid, h in content.hacks.items():
        if h["kind"] != "movimento":
            assert h["cooldown"] >= 1.0, hid
            assert "recarga" in content.hack_trees[hid], hid
