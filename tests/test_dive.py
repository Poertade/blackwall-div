from collections import Counter

import pytest

from blackwall.sim import build, hacks, waves
from blackwall.sim.dive import Dive, DiveConfig, DiveInput
from blackwall.sim.stats import Mods, Stats
from helpers import cast, put, quiet_dive, run


def still(e):
    e.speed = 0
    return e


# --- conteúdo -------------------------------------------------------------------
def test_every_hack_has_an_effect(content):
    assert set(content.hacks) == set(hacks.EFFECTS)


def test_starting_hacks_are_short_circuit_and_ping(content):
    assert sorted(h for h, d in content.hacks.items() if d["price"] == 0) == ["ping", "short_circuit"]


# --- andar e mirar -------------------------------------------------------------
def test_holding_the_button_walks_toward_the_cursor_and_releasing_stops(content):
    dive = quiet_dive(content)
    p = dive.player
    x0 = p.x
    run(dive, 0.5, DiveInput(move=(p.x + 400, p.y)))
    assert p.x > x0 + 100
    x1 = p.x
    run(dive, 0.5, DiveInput(move=None))
    assert p.x == x1


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


def test_short_circuit_jumps_with_arco_extra(content):
    dive = quiet_dive(content)
    dive.taken["arco_extra"] = 1
    dive.recompute()
    targets = [still(put(dive, "sabertooth", 200 + 60 * i, 120)) for i in range(5)]
    cast(dive, 0, targets[0], settle=0.4)
    assert len([e for e in targets if e.hp < e.max_hp]) == 2
    # com 2 ups de Cadeia, o bônus de conjunto dá mais um salto
    dive.taken["arco_extra"] = 2
    dive.recompute()
    for e in targets:
        e.hp = e.max_hp
    dive.slots[0].cooldown = 0
    cast(dive, 0, targets[0], settle=0.4)
    assert len([e for e in targets if e.hp < e.max_hp]) == 4


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


def test_overclock_doubles_ram_cost(content):
    dive = quiet_dive(content)
    cost = dive.stats.ram_cost("short_circuit", content.hacks["short_circuit"])
    dive.taken["overclock"] = 1
    dive.recompute()
    assert dive.stats.ram_cost("short_circuit", content.hacks["short_circuit"]) == pytest.approx(cost * 2)


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
    run(dive, dive.plan.duration + 0.1)
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
    run(dive, dive.plan.duration + 0.1)
    assert len(dive.offer) == 4


def test_wave_10_brings_the_layer_boss_and_killing_it_wins(content):
    dive = quiet_dive(content)
    dive.start_wave(10)
    assert dive.plan.boss == "kraken"
    assert dive.spawns and dive.spawns[0].boss
    dive.plan.pool = {}
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
    run(dive, dive.plan.duration + 0.1)
    dive.extract()
    assert dive.result == "extracted" and dive.ed_final == 100


def test_same_seed_same_dive(content):
    def play(seed):
        dive = Dive(content, DiveConfig(seed=seed))
        for i in range(60 * 20):
            target = dive.enemies[0] if dive.enemies else None
            aim = (target.x, target.y) if target else (0, 0)
            dive.step(1 / 60, DiveInput(move=(200, 200), aim=aim, cast=(0,) if i % 30 == 0 else ()))
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
    dive.taken["mutacao"] = 1
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
    run(dive, dive.plan.duration + 0.1)
    assert dive.lone_wolf == pytest.approx(0.05)
