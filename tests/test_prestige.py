import pytest

from blackwall.meta import prestige
from blackwall.meta import profile as pf
from blackwall.meta import save, story


def advanced(content):
    p = pf.new_profile(content)
    p.layers_cleared = 3
    p.path = "equipe"
    story.quest(p)["team"] = {"juno": 3}
    p.ed = 5000
    p.tree = {"dano": 10}
    p.hacks += ["contagion", "overheat"]
    p.hack_trees = {"contagion": {"mutacao": 2}}
    p.decks.append("biotech")
    p.prestige["life_ed"] = 50_000
    p.prestige["life_best"] = 12
    p.best_infinite = 12
    return p


def test_prestige_opens_after_the_third_layer(content):
    p = pf.new_profile(content)
    p.layers_cleared = 2
    assert not prestige.unlocked(p, content)
    p.layers_cleared = 3
    assert prestige.unlocked(p, content)


def test_fragments_grow_with_layers_ed_and_infinite_waves(content):
    p = advanced(content)
    total, parts = prestige.fragments_for(p, content)
    assert parts == {"camadas": 9, "ed": 10, "infinitas": 2}
    assert total == 21


def test_crossing_resets_almost_everything_and_keeps_the_fragments(content):
    p = advanced(content)
    gained = prestige.cross(p, content)
    assert gained == 21
    assert p.prestige["fragments"] == 21 and p.prestige["total"] == 21 and p.prestige["count"] == 1
    assert p.ed == 0 and p.tree == {} and p.hack_trees == {} and p.layers_cleared == 0
    assert p.path is None and story.quest(p)["team"] == {}
    assert sorted(p.hacks) == ["andar", "ping", "short_circuit"] and p.decks == ["paraline"]
    assert p.best_infinite == 12                       # o recorde fica
    assert p.prestige["life_ed"] == 0


def test_each_fragment_ever_earned_is_a_permanent_bonus(content):
    p = advanced(content)
    prestige.cross(p, content)
    mods = pf.permanent_mods(p, content)
    assert mods.stats["damage"] == pytest.approx(21 * 0.05)
    assert mods.stats["ed"] == pytest.approx(21 * 0.05)
    prestige.buy(p, content, "integridade_relic")      # gastar não tira o bônus
    assert pf.permanent_mods(p, content).stats["damage"] == pytest.approx(21 * 0.05)


def test_the_prestige_shop_shapes_the_next_life(content):
    p = advanced(content)
    prestige.cross(p, content)
    p.prestige["fragments"] = 100
    for item in ("memoria_residual", "arsenal", "arsenal", "deck_reserva", "atalho"):
        assert prestige.buy(p, content, item), item
    p.layers_cleared = 3
    prestige.cross(p, content)
    assert p.ed >= 400 + content.layers[0]["reward"]["ed"]
    assert "overheat" in p.hacks and "contagion" in p.hacks
    assert p.deck == "biotech"
    assert p.layers_cleared == 1 and content.layers[0]["reward"]["hack"] in p.hacks


def test_rhyme_notices_the_new_face(content):
    p = advanced(content)
    prestige.cross(p, content)
    ids = [b["id"] for b in story.beats(p, content)]
    assert "rosto_novo" in ids


def test_the_ed_of_a_life_is_counted(content):
    from blackwall.sim.dive import Dive
    p = pf.new_profile(content)
    dive = Dive(content, pf.dive_config(p, content, seed=1))
    dive.ed = 300
    dive.phase, dive.result = "over", "extracted"
    pf.apply_result(p, content, dive)
    assert p.prestige["life_ed"] == 300


def test_prestige_survives_saving(content, tmp_path):
    p = advanced(content)
    prestige.cross(p, content)
    prestige.buy(p, content, "ram_fantasma")
    save.save(p, tmp_path)
    back = save.load(content, tmp_path)
    assert back.prestige["total"] == 21 and back.prestige["shop"] == {"ram_fantasma": 1}


def test_resetting_the_save_keeps_a_copy_and_the_options(content, tmp_path):
    p = advanced(content)
    p.settings["volume"] = 0.2
    save.save(p, tmp_path)
    fresh = save.reset(content, tmp_path, settings=p.settings)
    assert fresh.ed == 0 and fresh.layers_cleared == 0 and fresh.prestige["total"] == 0
    assert fresh.settings["volume"] == 0.2
    assert list(tmp_path.glob("save-apagado-*.json"))
    assert save.load(content, tmp_path).ed == 0
