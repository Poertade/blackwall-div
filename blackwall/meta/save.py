"""O salvamento em JSON, na pasta do usuário (veja paths.save_dir)."""

import json
import os
import time
from dataclasses import asdict, fields
from pathlib import Path

from blackwall.meta.profile import Profile, new_profile
from blackwall.paths import save_dir

VERSION = 1
FILE = "save.json"


def to_dict(profile: Profile) -> dict:
    data = asdict(profile)
    data["version"] = VERSION
    return data


def from_dict(content, data: dict) -> Profile:
    profile = new_profile(content)
    known = {f.name for f in fields(Profile)}
    for key, value in data.items():
        if key in known:
            setattr(profile, key, value)
    # o que o conteúdo não tem mais (um hack ou deck renomeado) sai sem quebrar o salvamento
    profile.hacks = [h for h in profile.hacks if h in content.hacks]
    profile.decks = [d for d in profile.decks if d in content.decks] or [new_profile(content).deck]
    if profile.deck not in profile.decks:
        profile.deck = profile.decks[0]
    slots = content.decks[profile.deck]["slots"]
    loadout = [h if h in profile.hacks else None for h in profile.loadout]
    profile.loadout = (loadout + [None] * slots)[:slots]
    profile.tree = {k: int(v) for k, v in profile.tree.items() if k in content.tree}
    defaults = Profile()
    for key, value in defaults.stats.items():
        profile.stats.setdefault(key, value)
    for key, value in defaults.settings.items():
        profile.settings.setdefault(key, value)
    return profile


def save(profile: Profile, folder: Path | None = None) -> Path:
    folder = Path(folder or save_dir())
    folder.mkdir(parents=True, exist_ok=True)
    profile.last_seen = time.time()
    path = folder / FILE
    tmp = folder / (FILE + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(to_dict(profile), f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
    return path


def load(content, folder: Path | None = None) -> Profile:
    """Lê o salvamento. Se não existir, começa do zero; se estiver estragado, guarda uma cópia e começa do zero."""
    folder = Path(folder or save_dir())
    path = folder / FILE
    if not path.exists():
        return new_profile(content)
    try:
        with open(path, encoding="utf-8") as f:
            return from_dict(content, json.load(f))
    except (OSError, ValueError, TypeError, KeyError):
        try:
            os.replace(path, folder / f"save-estragado-{int(time.time())}.json")
        except OSError:
            pass
        return new_profile(content)
