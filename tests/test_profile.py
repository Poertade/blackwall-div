import json

import pytest

from blackwall.meta import profile as pf
from blackwall.meta import save
from blackwall.sim.dive import Dive


def test_new_profile_starts_with_walking_and_two_hacks_in_a_three_slot_deck(content):
    p = pf.new_profile(content)
    assert p.deck == "paraline"
    assert p.loadout == ["andar", "short_circuit", "ping"]
    assert p.ed == 0


def test_tree_costs_grow_and_respect_requirements(content):
    p = pf.new_profile(content)
    p.ed = 10_000
    ok, why = pf.tree_status(p, content, "critico")
    assert not ok and "Dano" in why
    first = pf.tree_cost(content, "dano", 0)
    assert pf.buy_tree(p, content, "dano")
    assert p.ed == 10_000 - first
    assert pf.tree_cost(content, "dano", 1) > first
    assert pf.buy_tree(p, content, "critico")


def test_tree_stops_at_max(content):
    p = pf.new_profile(content)
    p.ed = 10 ** 9
    for _ in range(content.tree["velocidade"]["max"] + 3):
        pf.buy_tree(p, content, "integridade")
        pf.buy_tree(p, content, "velocidade")
    assert p.tree["velocidade"] == content.tree["velocidade"]["max"]


def test_buying_a_hack_fills_an_empty_slot(content):
    p = pf.new_profile(content)
    p.ed = 1000
    p.decks.append("biotech")
    pf.set_deck(p, content, "biotech")
    assert p.loadout[3] is None
    assert pf.buy_hack(p, content, "overheat")
    assert p.loadout[3] == "overheat"
    assert not pf.buy_hack(p, content, "overheat")


def test_buying_a_bigger_deck_equips_it(content):
    p = pf.new_profile(content)
    p.ed = 1000
    p.hacks.append("contagion")
    assert pf.buy_deck(p, content, "biotech")
    assert p.deck == "biotech" and len(p.loadout) == 4
    assert "contagion" in p.loadout


def test_locked_decks_are_not_in_the_shop(content):
    p = pf.new_profile(content)
    decks = pf.shop(p, content)["decks"]
    assert "biotech" in decks and "arasaka" not in decks and "netdriver" not in decks
    p.layers_cleared = 3
    assert "arasaka" in pf.shop(p, content)["decks"]


def test_set_slot_swaps_a_hack_already_equipped(content):
    p = pf.new_profile(content)
    first, second, third = p.loadout
    pf.set_slot(p, 0, second)
    assert p.loadout == [second, first, third]


def test_permanent_mods_add_tree_deck_and_path(content):
    p = pf.new_profile(content)
    p.tree = {"dano": 2}
    p.decks.append("rippler")
    pf.set_deck(p, content, "rippler")
    p.path = "solo"
    mods = pf.permanent_mods(p, content)
    per_level = content.tree["dano"]["per_level"]["damage"]
    assert mods.stats["damage"] == pytest.approx(2 * per_level + 0.25)
    assert mods.stats["crit_chance"] == pytest.approx(0.1)
    assert mods.flags["lone_wolf"] == pytest.approx(0.05)
    assert pf.dive_config(p, content).choices == 4


def test_winning_layer_one_unlocks_the_next_and_gives_a_hack(content):
    p = pf.new_profile(content)
    dive = Dive(content, pf.dive_config(p, content, seed=1))
    dive.ed = 200
    dive.phase, dive.result = "over", "victory"
    summary = pf.apply_result(p, content, dive)
    assert p.layers_cleared == 1
    assert "synapse_burnout" in p.hacks
    assert summary["reward_hack"] == "synapse_burnout"
    assert p.ed == 200 + content.layers[0]["reward"]["ed"]
    assert pf.infinite_unlocked(p)
    # a 2ª camada só abre depois da escolha do caminho
    assert pf.available_layers(p, content) == 1
    assert pf.choose_path(p, content, "solo")
    assert pf.available_layers(p, content) == 2


def test_flatline_brings_back_three_quarters(content):
    p = pf.new_profile(content)
    dive = Dive(content, pf.dive_config(p, content, seed=1))
    dive.ed = 200
    dive.phase, dive.result = "over", "flatline"
    summary = pf.apply_result(p, content, dive)
    assert p.ed == 150 and summary["lost"] == 50
    assert p.layers_cleared == 0


def test_save_and_load_round_trip(content, tmp_path):
    p = pf.new_profile(content)
    p.ed = 321
    p.tree = {"dano": 3}
    p.path = "equipe"
    save.save(p, tmp_path)
    back = save.load(content, tmp_path)
    assert back.ed == 321 and back.tree == {"dano": 3} and back.path == "equipe"
    assert back.loadout == p.loadout


def test_broken_save_is_kept_aside_and_the_game_starts_fresh(content, tmp_path):
    (tmp_path / "save.json").write_text("{isto não é json", encoding="utf-8")
    p = save.load(content, tmp_path)
    assert p.ed == 0
    assert list(tmp_path.glob("save-estragado-*.json"))


def test_unknown_content_in_a_save_is_dropped(content, tmp_path):
    data = save.to_dict(pf.new_profile(content))
    data["hacks"].append("hack_que_nao_existe")
    data["loadout"] = ["hack_que_nao_existe", "ping", "andar"]
    data["tree"] = {"no_que_sumiu": 4, "dano": 1}
    (tmp_path / "save.json").write_text(json.dumps(data), encoding="utf-8")
    p = save.load(content, tmp_path)
    assert "hack_que_nao_existe" not in p.hacks
    assert p.loadout == [None, "ping", "andar"]
    assert p.tree == {"dano": 1}


def test_old_saves_get_walking_in_the_first_slot(content, tmp_path):
    data = save.to_dict(pf.new_profile(content))
    data["hacks"] = ["short_circuit", "ping"]
    data["loadout"] = ["short_circuit", "ping"]
    (tmp_path / "save.json").write_text(json.dumps(data), encoding="utf-8")
    p = save.load(content, tmp_path)
    assert p.loadout == ["andar", "short_circuit", "ping"]


def test_hack_tree_nodes_cost_ed_and_need_the_hack(content):
    p = pf.new_profile(content)
    p.ed = 100_000
    ok, why = pf.hack_node_status(p, content, "contagion", "mutacao")
    assert not ok and "não tem" in why
    p.hacks.append("contagion")
    assert pf.buy_hack_node(p, content, "contagion", "mutacao")
    assert pf.permanent_mods(p, content).hacks["contagion"]["spread"] == 1


def test_locked_hack_nodes_are_hidden_until_the_previous_one(content):
    nodes = content.hack_trees["contagion"]
    p = pf.new_profile(content)
    p.hacks.append("contagion")
    level = lambda n: pf.hack_level(p, "contagion", n)
    assert not pf.visible(level, nodes, "epidemia")
    p.ed = 10_000
    pf.buy_hack_node(p, content, "contagion", "mutacao")
    assert pf.visible(level, nodes, "epidemia")
