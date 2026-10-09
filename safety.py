"""Keyword heuristic that flags adult content, used for the `adult` field and SafeSearch.

Each term has a weight; repeats are capped (5 for unambiguous terms, 3 for the rest). A document is flagged when its
total score reaches THRESHOLD. It is deliberately simple: it catches blatant pages and can be
tuned without re-downloading data (re-run it and partial-update the `adult` field).
"""

import re

EXPLICIT = {  # weight 3, unambiguous: repeats count up to 5 times
    "porn", "porno", "pornography", "pornographic", "hentai", "sexting", "blowjob", "handjob",
    "cumshot", "creampie", "gangbang", "threesome", "milf", "camgirl", "camgirls", "dildo",
    "masturbate", "masturbation",
}
STRONG = {  # weight 3, can appear innocently (colour "nude", placeholder "xxx", "Pussy Riot"): repeats count up to 3 times
    "xxx", "nsfw", "onlyfans", "pussy", "deepthroat", "jav", "cunt", "bukkake", "orgasm", "erotic", "bdsm", "fetish", "fetishes",
    "nude", "nudes", "slut", "whore", "horny",
}
WEAK = {  # weight 1
    "sex", "sexy", "naughty", "kinky", "kinks", "naked", "escort", "boobs",
    "tits", "cock", "dick", "anal", "cum", "bondage", "stripper", "vagina", "penis", "squirting", "gonzo", "lesbo", "fuck",
}
URL_STRONG = ("porn", "xxx", "hentai", "nsfw", "camgirl", "sexcam", "xvideos", "xnxx", "stripchat", "chaturbate")
URL_WEAK = ("escort", "onlyfans", "erotic", "sexy", "livejasmin")  # ambiguous (e.g. Ford Escort), so a smaller bonus

STRONG_WEIGHT, WEAK_WEIGHT = 3, 1
MAX_REPEATS_EXPLICIT, MAX_REPEATS_OTHER = 5, 3
STUFFING = 10  # an explicit/strong term this many times AND ...
STUFFING_DENSITY = 0.01  # ... making up this share of all words is keyword stuffing and flags the page on its own
WEAK_TOTAL_CAP = 6  # weak terms can add at most this much in total (incidental words in long articles)
DENSITY = 0.02  # explicit words (uncapped, weighted) as a share of all words; at or above this the page is flagged
DENSITY_MIN_POINTS = 8  # ... but only if there are at least this many weighted hits (ignores tiny pages)
LONG_DOC_WORDS = 400  # beyond this many words the text score is scaled by sqrt(400 / words)
THRESHOLD = 12
URL_STRONG_BONUS = THRESHOLD  # a blatant URL flags the page on its own
URL_WEAK_BONUS = 4

_WORD = re.compile(r"[a-z]+")
_ALL = EXPLICIT | STRONG | WEAK


def _norm(w: str) -> str:
    """Map word variants to one term: fucking/fucked/fuckfest -> fuck, dildos -> dildo, creampies -> creampie."""
    if w.startswith("fuck"):  # one group, so swearing alone can't pile up points
        return "fuck"
    if w not in _ALL and w.endswith("s") and w[:-1] in _ALL:
        return w[:-1]
    return w


def breakdown(text: str, url: str = "") -> list[dict]:
    """Return one row per scoring item: {term, type, count, points}. The score is the sum of points."""
    tokens = [_norm(w) for w in _WORD.findall(text.lower())]
    counts: dict[str, int] = {}
    for w in tokens:
        if w in _ALL:
            counts[w] = counts.get(w, 0) + 1

    rows = []
    for w, n in sorted(counts.items()):
        if w in EXPLICIT:
            kind, pts = "explicit", min(n, MAX_REPEATS_EXPLICIT) * STRONG_WEIGHT
        elif w in STRONG:
            kind, pts = "strong", min(n, MAX_REPEATS_OTHER) * STRONG_WEIGHT
        else:
            kind, pts = "weak", min(n, MAX_REPEATS_OTHER) * WEAK_WEIGHT
        rows.append({"term": w, "type": kind, "count": n, "points": pts})

    weak = sum(r["points"] for r in rows if r["type"] == "weak")
    if weak > WEAK_TOTAL_CAP:
        rows.append({"term": "(weak terms cap)", "type": "cap", "count": 0, "points": WEAK_TOTAL_CAP - weak})

    words = len(tokens)
    if words > LONG_DOC_WORDS:  # long pages mention words incidentally; scale the text score down
        raw = sum(r["points"] for r in rows)
        scale = (LONG_DOC_WORDS / words) ** 0.5
        rows.append({"term": f"(length x{scale:.2f})", "type": "length", "count": words, "points": round(raw * scale - raw, 1)})

    # density: explicit words as a share of the page, uncapped; profanity ("fuck") does not count
    weighted = sum(
        n * (STRONG_WEIGHT if w in EXPLICIT or w in STRONG else WEAK_WEIGHT)
        for w, n in counts.items() if w != "fuck"
    )
    distinct = sum(1 for w in counts if w != "fuck")  # one repeated ambiguous word ("nude", "xxx") is not enough
    if distinct >= 2 and weighted >= DENSITY_MIN_POINTS and weighted / max(words, 1) >= DENSITY:
        rows.append({"term": f"(density {100 * weighted / words:.1f}%)", "type": "density", "count": weighted, "points": THRESHOLD})

    for w, n in sorted(counts.items()):  # unscaled: dense keyword stuffing flags the page outright
        if (w in EXPLICIT or w in STRONG) and n >= STUFFING and n / max(words, 1) >= STUFFING_DENSITY:
            rows.append({"term": f"{w} (stuffing)", "type": "stuffing", "count": n, "points": THRESHOLD})

    u = url.lower()
    if any(h in u for h in URL_STRONG):
        rows.append({"term": "(url: blatant hint)", "type": "url", "count": 1, "points": URL_STRONG_BONUS})
    elif any(h in u for h in URL_WEAK):
        rows.append({"term": "(url: weak hint)", "type": "url", "count": 1, "points": URL_WEAK_BONUS})
    return rows


def adult_score(text: str, url: str = "") -> int:
    return round(sum(r["points"] for r in breakdown(text, url)))


def is_adult(text: str, url: str = "") -> bool:
    return adult_score(text, url) >= THRESHOLD
