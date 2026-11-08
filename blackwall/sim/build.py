"""As builds: as tags dos ups, os bônus de conjunto, o ataque automático e as ofertas guiadas."""

from collections import Counter

from blackwall.sim.stats import TAGS, Mods


def tag_counts(content, taken: Counter) -> Counter:
    """Quantos ups de cada tag você pegou (um up com duas tags conta para as duas)."""
    counts = Counter({tag: 0 for tag in TAGS})
    for up_id, n in taken.items():
        for tag in content.ups[up_id].get("tags", []):
            counts[tag] += n
    return counts


def active_bonuses(content, counts: Counter) -> list:
    """Os bônus de conjunto ligados: [(tag, limiar, bloco)]."""
    result = []
    for tag in TAGS:
        for n in content.balance["build"]["thresholds"]:
            if counts[tag] >= n:
                result.append((tag, n, content.builds[tag]["bonuses"][n]))
    return result


def ups_mods(content, taken: Counter) -> Mods:
    """A soma dos ups pegos mais os bônus de conjunto que eles ligam."""
    mods = Mods()
    for up_id, n in taken.items():
        mods.add(content.ups[up_id], n)
    for _tag, _n, block in active_bonuses(content, tag_counts(content, taken)):
        mods.add(block)
    return mods


def auto_tag(content, counts: Counter, current: str | None) -> str | None:
    """A tag do ataque automático: a mais pegada, com pelo menos auto_at ups.

    Em caso de empate fica a que já estava ligada (o automático não troca à toa)."""
    need = content.balance["build"]["auto_at"]
    best = current if current and counts[current] >= need else None
    for tag in TAGS:
        if counts[tag] < need:
            continue
        if best is None or counts[tag] > counts[best]:
            best = tag
    return best


def offer_weights(content, taken: Counter, loadout, wave: int) -> dict:
    """O peso de cada up que ainda pode aparecer. As tags que você já pegou pesam mais (o guia da build)."""
    bal = content.balance["ups"]
    counts = tag_counts(content, taken)
    weights = {}
    hacks = set(h for h in loadout if h)
    deck_tags = set(t for h in hacks for t in content.hacks[h]["tags"])
    for up_id, up in content.ups.items():
        if taken[up_id] >= up["max"]:
            continue
        if up.get("requires_hack") and up["requires_hack"] not in hacks:
            continue
        # um up de build só aparece se algum hack do deck for dessa build (o deck escolhe as builds possíveis)
        if up.get("tags") and not deck_tags.intersection(up["tags"]):
            continue
        rarity = up["rarity"]
        w = bal["rarity"][rarity]
        if rarity != "comum":
            w *= 1 + bal["rarity_growth"] * (wave - 1)
        tags = up.get("tags", [])
        if tags:
            w *= 1 + bal["tag_weight"] * max(counts[t] for t in tags)
        weights[up_id] = w
    return weights


def roll_offer(content, rng, taken: Counter, loadout, wave: int, n: int) -> list:
    """Sorteia n ups diferentes, pelos pesos."""
    weights = offer_weights(content, taken, loadout, wave)
    offer = []
    pool = dict(weights)
    while pool and len(offer) < n:
        total = sum(pool.values())
        pick = rng.random() * total
        for up_id, w in pool.items():
            pick -= w
            if pick <= 0:
                break
        offer.append(up_id)
        del pool[up_id]
    return offer
