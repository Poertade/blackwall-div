"""A interface roda sem janela (SDL dummy): as telas desenham, as teclas e os cliques funcionam."""

import pygame
import pytest

from blackwall.game import theme as T
from blackwall.game.app import App
from blackwall.game.scene_dive import DiveScene
from blackwall.game.scene_hideout import HideoutScene
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


def test_every_hideout_tab_draws(app):
    for tab in ("mergulho", "deck", "loja", "arvore"):
        app.switch(HideoutScene(app, tab=tab))
        frames(app, 3)


def test_clicking_a_layer_card_starts_a_dive(app):
    app.switch(HideoutScene(app))
    frames(app, 2)
    scene = app.scene
    rect = scene.clicks.items[4][0]  # as 4 abas vêm primeiro; depois, o card da 1ª camada
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
            key(app, pygame.K_1)
        frames(app, 1)
    assert scene.dive.casts > 0
    # pula para o fim da onda e escolhe um up com a tecla
    scene.dive.wave_time = scene.dive.plan.duration
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


def test_screen_is_the_logical_size(app):
    assert app.screen.get_size() == (T.W, T.H)
