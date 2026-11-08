"""A interface roda sem janela (SDL dummy): as telas desenham, as teclas e os cliques funcionam."""

import pygame
import pytest

from blackwall.game import theme as T
from blackwall.game.app import App
from blackwall.game.scene_dive import DiveScene
from blackwall.game.scene_hideout import TABS, HideoutScene
from blackwall.meta import profile as pf


@pytest.fixture
def app(tmp_path):
    a = App(save_dir=tmp_path)
    yield a
    pygame.quit()


def frames(app, n=5, dt=1 / 60):
    for _ in range(n):
        app.frame(dt)


def key(app, k):
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0))


def click(app, pos, button=1):
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=button))
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=button))


def test_first_launch_opens_on_rhymes_message(app):
    assert app.scene.tab == "historia"


def test_every_hideout_tab_draws(app):
    for tab, _label in TABS:
        app.switch(HideoutScene(app, tab=tab))
        frames(app, 3)


def test_clicking_a_layer_card_starts_a_dive(app):
    app.switch(HideoutScene(app))
    frames(app, 2)
    scene = app.scene
    rect = scene.clicks.items[len(TABS)][0]  # as abas vêm primeiro; depois, o card da 1ª camada
    click(app, rect.center)
    frames(app, 2)
    assert isinstance(app.scene, DiveScene)


def test_a_dive_plays_offers_ups_and_returns_to_the_hideout(app):
    cfg = pf.dive_config(app.profile, app.content, "layer", 0, seed=3)
    scene = DiveScene(app, cfg, "teste")
    app.switch(scene)
    target = None
    for i in range(240):
        if scene.dive.enemies:
            target = scene.dive.enemies[0]
            pygame.mouse.set_pos((int(target.x + scene.ox), int(target.y + scene.oy)))
            key(app, pygame.K_2)      # o slot 1 é o Andar; o 2 é o Short Circuit
        frames(app, 1)
    assert scene.dive.casts > 0
    # pula para o fim da onda e escolhe um up com a tecla
    scene.dive.queue.clear()
    scene.dive.enemies.clear()
    scene.dive.spawns.clear()
    frames(app, 2)
    assert scene.dive.phase == "choice"
    key(app, pygame.K_1)              # cedo demais: os ups ainda não apareceram
    frames(app, 2)
    assert scene.dive.phase == "choice" and not scene.choice_ready()
    frames(app, 35)                   # passou meio segundo
    key(app, pygame.K_1)
    frames(app, 2)
    assert scene.dive.wave == 2 and sum(scene.dive.taken.values()) == 1
    # pausa e corta a conexão
    key(app, pygame.K_ESCAPE)
    frames(app, 2)
    assert scene.paused
    scene.abort()
    frames(app, 2)
    assert scene.dive.phase == "over" and scene.summary is not None
    key(app, pygame.K_RETURN)
    frames(app, 2)
    assert isinstance(app.scene, HideoutScene)
    assert app.profile.stats["dives"] == 1


def test_boss_wave_draws(app):
    for layer in range(len(app.content.layers)):
        cfg = pf.dive_config(app.profile, app.content, "layer", layer, seed=layer)
        scene = DiveScene(app, cfg, "chefe")
        app.switch(scene)
        scene.dive.start_wave(10)
        frames(app, 150)
        assert scene.dive.boss is not None


def test_quitting_mid_dive_counts_as_cut_connection_and_saves(app, tmp_path):
    cfg = pf.dive_config(app.profile, app.content, "layer", 0, seed=3)
    scene = DiveScene(app, cfg, "teste")
    app.switch(scene)
    scene.dive.ed = 40
    frames(app, 2)
    app.quit()
    assert scene.dive.result == "aborted"
    assert (tmp_path / "save.json").exists()
    assert app.profile.ed == 30


def test_choosing_a_path_is_a_reply_to_rhyme_and_takes_two_presses(app):
    from blackwall.meta import story
    app.profile.layers_cleared = 1
    app.switch(HideoutScene(app, tab="historia"))
    frames(app, 2)
    scene = app.scene
    assert scene.channel == "rhyme"
    key(app, pygame.K_2)
    frames(app, 2)
    assert app.profile.path is None and scene.armed == "equipe"
    key(app, pygame.K_2)
    frames(app, 2)
    assert app.profile.path == "equipe"
    assert story.quest(app.profile)["team"] == {"juno": 1}
    # depois da escolha, a Juno manda o primeiro serviço e a equipe aparece na lista
    frames(app, 2)
    ids = [c[0] for c in scene.channels()]
    assert "juno" in ids and "_team" in ids
    scene.open_channel("juno")
    frames(app, 2)
    key(app, pygame.K_1)          # ACEITAR SERVIÇO
    frames(app, 2)
    assert isinstance(app.scene, DiveScene) and app.scene.dive.mission["id"] == "equipe_1"


def test_a_mission_with_the_team_draws_and_plays(app):
    from blackwall.meta import profile as pf2
    app.profile.layers_cleared = 1
    pf2.choose_path(app.profile, app.content, "equipe")
    mission = app.content.mission("equipe_1")
    scene = DiveScene(app, pf2.dive_config(app.profile, app.content, "mission", seed=2, mission=mission), "missão")
    app.switch(scene)
    frames(app, 200)
    assert scene.dive.node is not None and scene.dive.allies
    assert "download" in scene.objective_text().lower()


def test_the_soundtrack_follows_the_scene(app):
    frames(app, 3)
    assert app.music.current == "desktop"
    cfg = pf.dive_config(app.profile, app.content, "layer", 0, seed=3)
    scene = DiveScene(app, cfg, "teste")
    app.switch(scene)
    frames(app, 60)
    assert app.music.current == "net"
    scene.dive.start_wave(10)
    frames(app, 60)
    assert app.music.current == "danger"


def test_f3_mutes_only_the_music(app):
    key(app, pygame.K_F3)
    frames(app, 2)
    assert app.music.volume == 0 and app.audio.volume > 0
    assert app.profile.settings["music"] == 0


def test_screen_is_the_logical_size(app):
    assert app.screen.get_size() == (T.W, T.H)


def test_sounds_are_not_muted_by_a_previous_dive(app):
    import time
    audio = app.audio
    if not audio.ok:
        return
    audio.volume = 0.5
    assert audio.play("hit", 900.0)        # um som no fim de um mergulho longo (relógio da tela em 900 s)
    time.sleep(0.05)
    assert audio.play("hit", 0.0)          # o mergulho seguinte começa com o relógio da tela em 0


def test_escape_in_the_hideout_opens_the_options_and_volume_changes(app):
    app.switch(HideoutScene(app))
    frames(app, 2)
    key(app, pygame.K_ESCAPE)
    frames(app, 2)
    opts = app.scene.options
    assert opts is not None
    before = app.profile.settings["volume"]
    opts.volume("efeitos", -0.1)
    assert app.profile.settings["volume"] == pytest.approx(before - 0.1)
    assert app.audio.volume == pytest.approx(before - 0.1)
    opts.toggle_shake()
    assert app.profile.settings["shake"] is False
    key(app, pygame.K_ESCAPE)
    frames(app, 2)
    assert app.scene.options is None


def test_resetting_the_save_takes_two_clicks(app, tmp_path):
    app.profile.ed = 999
    app.profile.layers_cleared = 2
    app.save()
    app.switch(HideoutScene(app))
    app.scene.open_options()
    opts = app.scene.options
    opts.reset()
    assert app.profile.ed == 999                 # o primeiro clique só arma
    opts.reset()
    assert app.profile.ed == 0 and app.profile.layers_cleared == 0
    assert list(tmp_path.glob("save-apagado-*.json"))
    frames(app, 2)


def test_the_blackwall_tab_appears_after_the_third_layer_and_crossing_takes_two_clicks(app):
    app.switch(HideoutScene(app))
    assert "blackwall" not in [k for k, _ in app.scene.tabs()]
    app.profile.layers_cleared = 3
    app.profile.path = "solo"
    app.profile.prestige["life_ed"] = 20_000
    scene = HideoutScene(app, tab="blackwall")
    app.switch(scene)
    frames(app, 2)
    assert "blackwall" in [k for k, _ in scene.tabs()]
    scene.cross()
    assert app.profile.prestige["count"] == 0
    scene.cross()
    assert app.profile.prestige["count"] == 1 and app.profile.prestige["total"] == 9 + 6
    assert app.profile.layers_cleared == 0 and scene.tab == "historia"
    frames(app, 2)
    scene.set_tab("blackwall")
    frames(app, 2)                               # a aba fica (o prestígio já foi visto)


def test_the_pause_has_options(app):
    cfg = pf.dive_config(app.profile, app.content, "layer", 0, seed=3)
    scene = DiveScene(app, cfg, "teste")
    app.switch(scene)
    key(app, pygame.K_ESCAPE)
    frames(app, 2)
    assert scene.paused
    scene.open_options()
    frames(app, 2)
    assert scene.options is not None and scene.options.in_dive
    key(app, pygame.K_ESCAPE)
    frames(app, 2)
    assert scene.options is None and scene.paused
