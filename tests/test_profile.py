import json

import pytest

from blackwall.meta import profile as pf
from blackwall.meta import save
from blackwall.sim.dive import Dive


def test_new_profile_starts_with_two_hacks_in_a_two_slot_deck(content):
    p = pf.new_profile(content)
    assert p.deck == "paraline"
    assert sorted(p.loadout) == ["ping", "short_circuit"]
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
    assert p.loadout[2] is None
    assert pf.buy_hack(p, content, "overheat")
    assert p.loadout[2] == "overheat"
    assert not pf.buy_hack(p, content, "overheat")


def test_buying_a_bigger_deck_equips_it(content):
    p = pf.new_profile(content)
    p.ed = 1000
    p.hacks.append("contagion")
    assert pf.buy_deck(p, content, "biotech")
    assert p.deck == "biotech" and len(p.loadout) == 3
    assert "contagion" in p.loadout


def test_locked_decks_are_not_in_the_shop(content):
    p = pf.new_profile(content)
    decks = pf.shop(p, content)["decks"]
    assert "biotech" in decks and "arasaka" not in decks and "netdriver" not in decks
    p.layers_cleared = 3
    assert "arasaka" in pf.shop(p, content)["decks"]


def test_set_slot_swaps_a_hack_already_equipped(content):
    p = pf.new_profile(content)
    first, second = p.loadout
    pf.set_slot(p, 0, second)
    assert p.loadout == [second, first]


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
    data["loadout"] = ["hack_que_nao_existe", "ping"]
    data["tree"] = {"no_que_sumiu": 4, "dano": 1}
    (tmp_path / "save.json").write_text(json.dumps(data), encoding="utf-8")
    p = save.load(content, tmp_path)
    assert "hack_que_nao_existe" not in p.hacks
    assert p.loadout == [None, "ping"]
    assert p.tree == {"dano": 1}
