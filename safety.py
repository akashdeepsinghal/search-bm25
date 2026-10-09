"""Keyword heuristic that flags adult content, used for the `adult` field and SafeSearch.

Each term has a weight; repeats count up to MAX_REPEATS times. A document is flagged when its
total score reaches THRESHOLD. It is deliberately simple: it catches blatant pages and can be
tuned without re-downloading data (re-run it and partial-update the `adult` field).
"""

import re

STRONG = {  # weight 3
    "porn", "porno", "pornography", "pornographic", "xxx", "hentai", "sexting", "nsfw",
    "blowjob", "handjob", "cumshot", "creampie", "gangbang", "threesome", "milf", "camgirl",
    "camgirls", "onlyfans", "pussy", "dildo", "orgasm", "masturbate", "masturbation",
    "erotic", "bdsm", "fetish", "fetishes", "nude", "nudes", "slut", "whore", "horny",
}
WEAK = {  # weight 1
    "sex", "sexy", "naughty", "kinky", "kinks", "naked", "escort", "escorts", "boobs",
    "tits", "cock", "dick", "anal", "cum", "bondage", "stripper",
}
URL_STRONG = ("porn", "xxx", "hentai", "nsfw", "camgirl", "sexcam", "xvideos", "xnxx", "stripchat", "chaturbate")
URL_WEAK = ("escort", "onlyfans", "erotic", "sexy", "livejasmin")  # ambiguous (e.g. Ford Escort), so a smaller bonus

STRONG_WEIGHT, WEAK_WEIGHT = 3, 1
MAX_REPEATS = 3
THRESHOLD = 12
URL_STRONG_BONUS = THRESHOLD  # a blatant URL flags the page on its own
URL_WEAK_BONUS = 4

_WORD = re.compile(r"[a-z]+")


def adult_score(text: str, url: str = "") -> int:
    counts: dict[str, int] = {}
    for w in _WORD.findall(text.lower()):
        if w in STRONG or w in WEAK:
            counts[w] = counts.get(w, 0) + 1
    score = sum(
        min(n, MAX_REPEATS) * (STRONG_WEIGHT if w in STRONG else WEAK_WEIGHT)
        for w, n in counts.items()
    )
    u = url.lower()
    if any(h in u for h in URL_STRONG):
        score += URL_STRONG_BONUS
    elif any(h in u for h in URL_WEAK):
        score += URL_WEAK_BONUS
    return score


def is_adult(text: str, url: str = "") -> bool:
    return adult_score(text, url) >= THRESHOLD
