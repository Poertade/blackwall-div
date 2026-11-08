import pytest

from blackwall.meta import profile as pf
from blackwall.meta import story
from blackwall.sim.dive import Dive
from helpers import put, run


def cleared(content, layers=1):
    p = pf.new_profile(content)
    p.layers_cleared = layers
    return p


def mission_dive(content, profile, mission_id, seed=3):
    cfg = pf.dive_config(profile, content, "mission", seed=seed, mission=content.mission(mission_id))
    return Dive(content, cfg)


# --- falas e caminho -----------------------------------------------------------
def test_first_message_is_rhymes_and_the_crossroads_comes_after_layer_one(content):
    p = pf.new_profile(content)
    ids = [b["id"] for b in story.beats(p, content)]
    assert ids[0] == "inicio" and "encruzilhada" not in ids
    p.layers_cleared = 1
    assert "encruzilhada" in [b["id"] for b in story.unread(p, content)]
    story.mark_read(p, content)
    assert story.unread(p, content) == []


def test_the_path_is_chosen_once_and_forever(content):
    p = cleared(content)
    assert story.needs_path_choice(p)
    assert pf.choose_path(p, content, "equipe")
    assert p.path == "equipe"
    assert story.quest(p)["team"] == {"juno": 1}
    assert not pf.choose_path(p, content, "netwatch")
    assert p.path == "equipe"


def test_no_path_before_layer_one(content):
    p = pf.new_profile(content)
    assert not pf.choose_path(p, content, "solo")


def test_netwatch_gets_the_netdriver_and_varga(content):
    p = cleared(content)
    pf.choose_path(p, content, "netwatch")
    assert p.deck == "netdriver" and len(p.loadout) == 6
    assert story.allies_for_dive(p, content) == [("varga", 1)]


def test_solo_has_no_allies_and_four_choices(content):
    p = cleared(content)
    pf.choose_path(p, content, "solo")
    cfg = pf.dive_config(p, content)
    assert cfg.allies == [] and cfg.choices == 4


def test_path_message_arrives_after_choosing(content):
    p = cleared(content)
    pf.choose_path(p, content, "netwatch")
    ids = [b["id"] for b in story.beats(p, content)]
    assert "escolheu_netwatch" in ids and "escolheu_solo" not in ids


# --- missões ----------------------------------------------------------------
def test_missions_follow_the_path_and_the_layers(content):
    p = cleared(content)
    pf.choose_path(p, content, "solo")
    status = {m["id"]: s for m, s in story.missions(p, content)}
    assert status == {"solo_1": "open", "solo_2": "locked", "solo_3": "locked"}


def test_survive_mission_wins_after_its_waves(content):
    p = cleared(content)
    pf.choose_path(p, content, "solo")
    dive = mission_dive(content, p, "solo_1")
    dive.plan.pool = {}
    waves = content.mission("solo_1")["waves"]
    for _ in range(waves):
        run(dive, dive.plan.duration + 0.1)
        if dive.phase == "choice":
            dive.choose(0)
            dive.plan.pool = {}
    assert dive.phase == "over" and dive.result == "victory"
    summary = pf.apply_result(p, content, dive)
    assert summary["reward_hack"] == "detonate_grenade"
    assert "solo_1" in story.quest(p)["done"]
    # a recompensa só vem uma vez
    again = story.mission_reward(p, content, content.mission("solo_1"))
    assert again["ed"] == 0


def test_download_fails_if_the_node_falls_and_keeps_the_ed(content):
    p = cleared(content)
    pf.choose_path(p, content, "equipe")
    dive = mission_dive(content, p, "equipe_1")
    dive.plan.pool = {}
    dive.allies.clear()
    node = dive.node
    assert node is not None and node.hp == content.mission("equipe_1")["objective"]["hp"]
    for i in range(6):
        put(dive, "hellhound", node.x + 30 * (i - 3), node.y - 40)
    dive.ed = 50
    run(dive, 25)
    assert dive.result == "failed"
    assert dive.ed_final == 50


def test_ice_goes_after_the_node_when_it_is_closer(content):
    p = cleared(content)
    pf.choose_path(p, content, "equipe")
    dive = mission_dive(content, p, "equipe_1")
    dive.plan.pool = {}
    dive.allies.clear()
    node = dive.node
    e = put(dive, "hellhound", node.x - 200, node.y - 10)
    before = abs(e.x - node.x)
    run(dive, 0.5)
    assert abs(e.x - node.x) < before


def test_escort_program_crosses_the_arena(content):
    p = cleared(content, 2)
    pf.choose_path(p, content, "equipe")
    dive = mission_dive(content, p, "equipe_2")
    x0 = dive.node.x
    dive.plan.pool = {}
    run(dive, 10)
    assert dive.node.x > x0 + 50


def test_nodes_mission_holds_the_wave_until_the_nodes_fall(content):
    p = cleared(content)
    pf.choose_path(p, content, "netwatch")
    dive = mission_dive(content, p, "netwatch_1")
    dive.plan.pool = {}
    dive.allies.clear()
    run(dive, 1.2)
    nodes = [e for e in dive.enemies if e.type == "node"]
    assert len(nodes) == 2
    for e in nodes:
        e.hp = e.max_hp = 1e9
    dive.player.invulnerable = 1e9   # os Wisps que os nós soltam não podem derrubar a netrunner no teste
    run(dive, dive.plan.duration + 1)
    assert dive.phase == "wave"
    for e in nodes:
        dive.kill(e)
    run(dive, 0.2)
    assert dive.phase == "choice"


def test_hunt_target_appears_in_the_last_wave(content):
    p = cleared(content, 2)
    pf.choose_path(p, content, "netwatch")
    dive = mission_dive(content, p, "netwatch_2")
    dive.allies.clear()
    last = content.mission("netwatch_2")["waves"]
    dive.start_wave(last)
    dive.plan.pool = {}
    run(dive, 2.0)
    assert dive.boss is not None and dive.boss.type == "severin"
    dive.kill(dive.boss)
    assert dive.result == "victory"


# --- equipe e renda --------------------------------------------------------------
def test_juno_hacks_on_her_own(content):
    p = cleared(content)
    pf.choose_path(p, content, "equipe")
    dive = mission_dive(content, p, "equipe_1")
    dive.plan.pool = {}
    dive.node.hp = 1e9
    e = put(dive, "sabertooth", dive.player.x + 120, dive.player.y)
    e.speed = 0
    run(dive, 2.5)
    assert e.hp < e.max_hp


def test_mira_heals(content):
    p = cleared(content, 2)
    pf.choose_path(p, content, "equipe")
    story.quest(p)["team"]["mira"] = 1
    dive = Dive(content, pf.dive_config(p, content, seed=1))
    dive.plan.pool = {}
    dive.player.hp = 20
    run(dive, 4.5)
    assert dive.player.hp > 20


def test_training_an_ally_costs_more_each_level(content):
    p = cleared(content)
    pf.choose_path(p, content, "equipe")
    p.ed = 100_000
    first = story.ally_cost(content, 1)
    assert story.train_ally(p, content, "juno")
    assert story.quest(p)["team"]["juno"] == 2
    assert story.ally_cost(content, 2) > first
    assert not story.train_ally(p, content, "ruido")


def test_team_earns_while_the_game_is_closed_up_to_the_cap(content):
    p = cleared(content)
    pf.choose_path(p, content, "equipe")
    rate = story.income_rate(p, content)
    assert rate > 0
    p.last_seen = 0
    gained = story.offline_income(p, content, now=3600 * 100)
    cap = content.story["income"]["equipe"]["cap_hours"]
    assert gained == pytest.approx(rate * cap, abs=1)


def test_solo_has_no_income(content):
    p = cleared(content)
    pf.choose_path(p, content, "solo")
    p.last_seen = 0
    assert story.offline_income(p, content, now=36000) == 0


def test_netwatch_salary_is_smaller_than_the_team_income(content):
    a, b = cleared(content), cleared(content)
    pf.choose_path(a, content, "equipe")
    pf.choose_path(b, content, "netwatch")
    assert 0 < story.income_rate(b, content) < story.income_rate(a, content)


def test_beating_the_last_layer_gives_the_path_ending(content):
    p = cleared(content, 4)
    pf.choose_path(p, content, "netwatch")
    dive = Dive(content, pf.dive_config(p, content, "layer", 4, seed=1))
    dive.phase, dive.result = "over", "victory"
    summary = pf.apply_result(p, content, dive)
    assert summary["ending"] == "netwatch"
    assert story.ending(p, content)["title"]
