"""Emoji for captions: spoken words -> a small emoji picture that pops up above the caption (Twemoji graphics, CC-BY 4.0, bundled in app/emoji)."""
import os, re

# (file name = Unicode code point(s) in hex, priority 1-3, words that trigger it). Strong feelings get a higher priority than everyday words.
TABLE = [
    ("1f602", 3, "haha hahaha hahahaha lol lmao lmfao rofl funny hilarious laugh laughing laughed joke jokes giggle giggling"),
    ("1f970", 2, "cute aww awww adorable sweet precious"),
    ("2764", 2, "love loved loves luv lovely heart hearts adore"),
    ("1f618", 2, "kiss kisses mwah"),
    ("1f917", 2, "hug hugs cuddle"),
    ("1f525", 3, "fire lit hot clutch cracked goated sweaty"),
    ("1f92f", 3, "insane crazy mindblown unreal wild unbelievable"),
    ("1f633", 3, "wtf wth embarrassing embarrassed shy blush"),
    ("1f631", 3, "omg omfg scream screams screaming screamed jumpscare"),
    ("1f628", 2, "scary scared afraid terrified creepy"),
    ("1f47b", 2, "ghost ghosts spooky haunted"),
    ("1f62e", 2, "wow whoa woah pog poggers"),
    ("1f928", 2, "sus suspicious"),
    ("1f914", 1, "hmm thinking think"),
    ("1f4a1", 1, "idea"),
    ("1f440", 2, "eyes watching staring"),
    ("1f622", 2, "sad unhappy"),
    ("1f62d", 3, "cry crying cried tears sob sobbing"),
    ("1f97a", 2, "sorry please pls"),
    ("1f480", 3, "dead dying died die death skull"),
    ("1f621", 2, "angry mad furious"),
    ("1f92c", 3, "rage raging"),
    ("1f620", 2, "hate hated"),
    ("1f624", 1, "annoying annoyed"),
    ("1f3c6", 3, "win won winner winning victory champion champ trophy"),
    ("1f44f", 2, "gg clap clapping applause"),
    ("1f389", 3, "congrats congratulations party yay celebrate celebration"),
    ("1f382", 2, "birthday"),
    ("1f947", 2, "gold"),
    ("1f64f", 2, "thanks thank ty appreciate grateful"),
    ("1f4b0", 2, "money rich"),
    ("1f4b5", 1, "cash dollars"),
    ("1f4b8", 1, "expensive broke"),
    ("1f381", 2, "gift gifted"),
    ("1f355", 2, "pizza"),
    ("1f354", 2, "burger food"),
    ("1f924", 2, "hungry yummy delicious"),
    ("2615", 2, "coffee"),
    ("1f375", 1, "tea"),
    ("1f370", 2, "cake"),
    ("1f366", 2, "icecream"),
    ("1f35c", 2, "ramen noodles"),
    ("1f363", 2, "sushi"),
    ("1f431", 2, "cat cats kitty kitten"),
    ("1f436", 2, "dog puppy doggo"),
    ("1f430", 2, "bunny rabbit"),
    ("1f98a", 2, "fox"),
    ("1f426", 1, "bird"),
    ("1f41f", 1, "fish"),
    ("1f988", 2, "shark"),
    ("1f438", 2, "frog"),
    ("1f427", 2, "penguin"),
    ("1f43b", 1, "bear"),
    ("1f984", 2, "unicorn"),
    ("1f409", 2, "dragon"),
    ("1f40d", 2, "snake"),
    ("1f634", 2, "sleep sleepy tired nap"),
    ("1f971", 1, "yawn"),
    ("1f3ae", 1, "game gaming gamer controller"),
    ("1f3b6", 2, "music song songs"),
    ("1f3a4", 2, "sing singing karaoke"),
    ("1f483", 2, "dance dancing"),
    ("2600", 1, "sun sunny"),
    ("1f319", 1, "moon"),
    ("2b50", 2, "star"),
    ("2728", 2, "sparkle sparkles magic magical"),
    ("1f308", 2, "rainbow"),
    ("2744", 1, "snow"),
    ("1f680", 2, "rocket space"),
    ("1f47d", 2, "alien aliens"),
    ("1f9df", 3, "zombie zombies"),
    ("1f47e", 2, "monster monsters"),
    ("1f916", 2, "robot"),
    ("1f608", 2, "demon devil"),
    ("1f607", 2, "angel"),
    ("1f9db", 2, "vampire"),
    ("1f9d9", 2, "witch wizard"),
    ("1f921", 2, "clown"),
    ("1f4a3", 2, "bomb"),
    ("1f4a5", 3, "boom explosion explode exploded"),
    ("1f44d", 1, "nice good great"),
    ("1f4af", 2, "perfect hundred"),
    ("1f60e", 2, "cool"),
    ("1f929", 2, "awesome amazing best wonderful fantastic"),
    ("1f60d", 2, "beautiful pretty gorgeous"),
    ("1f44b", 1, "hello hi hey bye goodbye welcome"),
    ("1f648", 2, "oops whoops"),
    ("1f926", 2, "bruh facepalm"),
    ("1f644", 1, "whatever"),
    ("1f4aa", 2, "strong muscle"),
    ("26a1", 2, "power lightning"),
    ("1f4a8", 1, "speed fast"),
    ("1f340", 2, "lucky luck"),
    ("1f451", 2, "king queen crown"),
    ("1f48e", 2, "diamond diamonds gem"),
]
MAP = {}
for _hx, _pr, _ws in TABLE:
    for _w in _ws.split():
        MAP.setdefault(_w, (_hx, _pr))
DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "emoji")
_clean = lambda w: re.sub(r"[^a-z]", "", str(w).lower())


def path(hx):
    p = os.path.join(DIR, hx + ".png")
    return p if os.path.isfile(p) else ""


def pick(owords, dur, intensity=1.0, first=.5):
    """Words in a finished clip (clip timeline) -> [(seconds, hex)]: the strongest feelings, spread out, never the same emoji twice in a row close together."""
    limit, gap = (4, 3.6) if intensity < .8 else (11, 1.8) if intensity > 1.3 else (7, 2.5)
    limit = int(limit * max(1.0, dur / 60.0))                  # a long recap gets proportionally more than a 45 s short
    cands = []
    for w in owords or []:
        hit = MAP.get(_clean(w["w"]))
        if hit and path(hit[0]) and first <= w["start"] <= dur - .8: cands.append((hit[1], -w["start"], hit[0]))
    chosen = []
    for pr, nt, hx in sorted(cands, reverse=True):
        t = -nt
        if len(chosen) >= limit: break
        if all(abs(t - u) >= gap for u, _ in chosen) and all(not (h == hx and abs(t - u) < 6) for u, h in chosen): chosen.append((t, hx))
    return sorted(chosen)
