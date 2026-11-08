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
