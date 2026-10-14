"""Post-kit writer for VTuber Clipper (no internet, no AI service): reads what was SAID in a clip and writes
titles, platform-tuned hashtags (YouTube Shorts / TikTok / Instagram Reels / X), a YouTube description, a TikTok / Reels
caption and click-bait-style posts for X (Twitter).

Everything is rule based and deterministic for a given seed ("Another idea" just changes the seed).
Hashtag counts follow what the platforms recommend (checked Oct 2026):
  YouTube Shorts 3-5 incl. #Shorts (the first three show above the title) / TikTok 3-5 / Instagram Reels 3-5 (IG now caps a post at 5) / X 1-3.
"""
import re, random, hashlib

# ------------------------------------------------------------------ games: aliases -> (display name, hashtags)
GAMES = [
    (r"black ?ops ?3|bo3", "Black Ops 3 Zombies", ["BlackOps3", "Zombies", "CallOfDuty"]),
    (r"black ?ops ?6|bo6", "Black Ops 6", ["BlackOps6", "Zombies", "CallOfDuty"]),
    (r"black ?ops ?7|bo7", "Black Ops 7", ["BlackOps7", "Zombies", "CallOfDuty"]),
    (r"black ?ops ?2|bo2", "Black Ops 2", ["BlackOps2", "Zombies", "CallOfDuty"]),
    (r"black ?ops", "Black Ops Zombies", ["BlackOps", "Zombies", "CallOfDuty"]),
    (r"warzone", "Warzone", ["Warzone", "CallOfDuty", "CoD"]),
    (r"call of duty|\bcod\b", "Call of Duty", ["CallOfDuty", "CoD"]),
    (r"minecraft", "Minecraft", ["Minecraft", "MinecraftClips"]),
    (r"valorant", "Valorant", ["Valorant", "ValorantClips"]),
    (r"league of legends|\blol\b game|\bleague\b", "League of Legends", ["LeagueOfLegends", "LoL"]),
    (r"fortnite", "Fortnite", ["Fortnite", "FortniteClips"]),
    (r"apex legends|\bapex\b", "Apex Legends", ["ApexLegends", "Apex"]),
    (r"overwatch", "Overwatch 2", ["Overwatch2", "Overwatch"]),
    (r"marvel rivals", "Marvel Rivals", ["MarvelRivals"]),
    (r"counter.?strike|\bcs2\b|\bcsgo\b", "Counter-Strike 2", ["CS2", "CounterStrike"]),
    (r"genshin", "Genshin Impact", ["GenshinImpact", "Genshin"]),
    (r"honkai|star rail", "Honkai: Star Rail", ["HonkaiStarRail", "HSR"]),
    (r"zenless", "Zenless Zone Zero", ["ZenlessZoneZero", "ZZZ"]),
    (r"elden ring", "Elden Ring", ["EldenRing", "Soulslike"]),
    (r"dark souls|sekiro|bloodborne", "Soulslike", ["Soulslike", "DarkSouls"]),
    (r"resident evil", "Resident Evil", ["ResidentEvil", "HorrorGaming"]),
    (r"phasmophobia", "Phasmophobia", ["Phasmophobia", "HorrorGaming"]),
    (r"lethal company", "Lethal Company", ["LethalCompany"]),
    (r"content warning", "Content Warning", ["ContentWarning"]),
    (r"repo\b", "R.E.P.O.", ["REPO", "HorrorGaming"]),
    (r"five nights|fnaf", "Five Nights at Freddy's", ["FNAF", "HorrorGaming"]),
    (r"poppy playtime", "Poppy Playtime", ["PoppyPlaytime", "HorrorGaming"]),
    (r"outlast", "Outlast", ["Outlast", "HorrorGaming"]),
    (r"dead by daylight|\bdbd\b", "Dead by Daylight", ["DeadByDaylight", "DBD"]),
    (r"among us", "Among Us", ["AmongUs"]),
    (r"fall guys", "Fall Guys", ["FallGuys"]),
    (r"roblox", "Roblox", ["Roblox"]),
    (r"gta|grand theft auto", "GTA", ["GTA", "GTA5"]),
    (r"rocket league", "Rocket League", ["RocketLeague"]),
    (r"rainbow six|siege", "Rainbow Six Siege", ["RainbowSixSiege", "R6"]),
    (r"destiny", "Destiny 2", ["Destiny2"]),
    (r"helldivers", "Helldivers 2", ["Helldivers2"]),
    (r"palworld", "Palworld", ["Palworld"]),
    (r"stardew", "Stardew Valley", ["StardewValley", "CozyGaming"]),
    (r"animal crossing", "Animal Crossing", ["AnimalCrossing", "CozyGaming"]),
    (r"mario kart", "Mario Kart", ["MarioKart"]),
    (r"smash", "Smash Bros", ["SmashBros"]),
    (r"pok[eé]mon", "Pokémon", ["Pokemon"]),
    (r"hollow knight|silksong", "Hollow Knight", ["HollowKnight"]),
    (r"cyberpunk", "Cyberpunk 2077", ["Cyberpunk2077"]),
    (r"baldur", "Baldur's Gate 3", ["BaldursGate3", "BG3"]),
    (r"skyrim", "Skyrim", ["Skyrim"]),
    (r"final fantasy", "Final Fantasy", ["FinalFantasy"]),
    (r"persona", "Persona", ["Persona"]),
    (r"monster hunter", "Monster Hunter", ["MonsterHunter"]),
    (r"subnautica", "Subnautica", ["Subnautica"]),
    (r"terraria", "Terraria", ["Terraria"]),
    (r"rust\b", "Rust", ["RustGame"]),
    (r"tarkov", "Escape from Tarkov", ["Tarkov"]),
    (r"pubg", "PUBG", ["PUBG"]),
    (r"diablo", "Diablo", ["Diablo4"]),
    (r"world of warcraft|\bwow\b", "World of Warcraft", ["WorldOfWarcraft", "WoW"]),
    (r"ark\b", "ARK", ["ARK"]),
    (r"valheim", "Valheim", ["Valheim"]),
    (r"sea of thieves", "Sea of Thieves", ["SeaOfThieves"]),
    (r"dota", "Dota 2", ["Dota2"]),
    (r"balatro", "Balatro", ["Balatro"]),
    (r"hades", "Hades", ["Hades"]),
    (r"celeste", "Celeste", ["Celeste"]),
    (r"mario", "Mario", ["Mario", "Nintendo"]),
    (r"zelda", "Zelda", ["Zelda", "Nintendo"]),
    (r"just chatting|irl\b", "Just Chatting", ["JustChatting"]),
    (r"karaoke|singing stream", "Karaoke", ["Karaoke", "VTuberSinger"]),
]

# ------------------------------------------------------------------ what the clip is about (angles)
ANGLE_WORDS = {
    "funny": "haha hahaha lol lmao lmfao funny dying crying bruh hilarious joke giggle laughing laugh lmaooo hehe cant breathe stop it".split(),
    "shock": "wtf omg wait what holy unreal insane crazy huh excuse seriously unbelievable bro".split(),
    "scream": "ahh aah scream screaming jumpscare scared scary creepy help nope aaah ahhh".split(),
    "rage": "rage angry mad hate stupid ridiculous annoying trash garbage unplayable cheating bullshit damn".split(),
    "clutch": "clutch gg ez easy won win winning victory finally ace carry wiped pog poggers".split(),
    "fail": "fail died die dead lost lose oops whoops misclick mistake dumb fell wrong missed crashed bug glitch".split(),
    "wholesome": "thank thanks love cute aww sweet happy appreciate wholesome hug proud adorable".split(),
    "story": "basically story remember yesterday swear happened school mom dad boyfriend girlfriend date".split(),
    "hype": "lets pog poggers yes yeah yay woo woohoo hype".split(),
    "cozy": "cozy chill relax vibe vibes calm peaceful rain tea comfy".split(),
}
PHRASE_ANGLE = [("funny", r"can'?t breathe|that'?s so funny|i'?m dying|i'?m crying"), ("shock", r"what the|no way|oh my god|are you serious|did that just|what is happening|how did"),
                ("hype", r"let'?s go+|lets go+|let'?s fucking go"), ("clutch", r"we did it|one shot|last one|we won|i won"), ("scream", r"jump ?scare|oh no no|no no no"),
                ("fail", r"i died|i'?m dead|oh no|why did i|what did i do"), ("wholesome", r"thank you|love you|so cute|means a lot")]
EMOJI = {"funny": "😭", "shock": "😳", "scream": "😱", "rage": "😤", "clutch": "🔥", "fail": "💀", "wholesome": "🥹", "story": "👀", "hype": "🔥", "cozy": "☁️", "chaos": "😵"}

STOP = set("""a about above after again all also am an and any are aren't as at be because been before being below between both but by can can't cannot could couldn't did didn't do does doesn't doing don't down during each few for from further get got had hadn't has hasn't have haven't having he her here hers herself him himself his how i i'd i'll i'm i've if in into is isn't it it's its itself just let's like me more most my myself no nor not of off on once only or other ought our ours out over own same she should shouldn't so some such than that that's the their theirs them then there there's these they they'd they'll they're they've this those through to too under until up very was wasn't we we'd we'll we're we've were weren't what what's when where which while who whom why with won't would wouldn't you you'd you'll you're you've your yours yourself yeah yes okay oh um uh gonna wanna really right know think going one two thing things guys dude bro man okay ok well now see look back come want need say said says actually literally basically maybe still even much many something anything everything left chat stream game games time people little kind sort first last never always another again every because pretty sure play playing played make made makes take took give gave tell told call called feel felt keep kept mean means thought let lets didnt dont cant wont doesnt isnt wasnt""".split())
PROFANE = re.compile(r"\b(\w*fuck\w*|\w*shit\w*|bitch\w*|dick\w*|cunt\w*|nigg\w*|fag\w*|retard\w*|slut\w*|whore\w*|asshole\w*|bastard\w*|pussy|pussies|cock|cocks|cocksucker\w*|twat\w*|wank\w*)\b", re.I)
# whole words the video bleeps when "Bleep common swear words" is on (English). Matched word by word, so names and normal words stay untouched.
SWEARS = frozenset("""fuck fucks fucked fucker fuckers fucking fuckin fuckface fuckhead fuckwit fucktard fck fuk fuking motherfucker motherfuckers motherfucking motherfuckin mf mfer mfers
shit shits shitty shitting shithead shitheads shitshow bullshit bullshitting horseshit dipshit shite bitch bitches bitchy bitching bitched bastard bastards cunt cunts
dick dicks dickhead dickheads cock cocks cocksucker cocksuckers pussy pussies twat twats wanker wankers slut sluts slutty whore whores
ass asses asshole assholes jackass dumbass smartass nigger niggers nigga niggas faggot faggots fag fags retard retards retarded tranny trannies chink chinks spic spics kike kikes""".split())
BAD_TAG_WORDS = PROFANE


def _rng(seed, *parts):
    return random.Random(int(hashlib.md5(("|".join(map(str, (seed,) + parts))).encode()).hexdigest()[:12], 16))


def mask(text):
    """f*** the strongest words: titles with swear words get limited ads / reach on YouTube and TikTok."""
    return PROFANE.sub(lambda m: m.group(0)[0] + "*" * (len(m.group(0)) - 1), text)


def camel(tag):
    tag = re.sub(r"[^0-9A-Za-z]+", " ", tag).strip()
    return "".join(p if (p[:1].isupper() and not p.islower()) else p[:1].upper() + p[1:] for p in tag.split())


def tokens(text):
    return [t.lower() for t in re.findall(r"[A-Za-z][A-Za-z']+", text)]


def is_cjk(text):
    return any(0x3040 <= ord(c) <= 0x30FF or 0x3400 <= ord(c) <= 0x9FFF or 0xAC00 <= ord(c) <= 0xD7AF for c in text)


WEAK = {"Smash Bros", "Persona", "Destiny 2", "Hades", "League of Legends", "Rainbow Six Siege", "Rust", "R.E.P.O.", "Mario", "Zelda", "Just Chatting", "ARK", "Celeste"}   # common words: only trusted in the game / file name


def find_game(*texts, strong_only=False):
    blob = " ".join(t for t in texts if t).lower()
    blob = re.sub(r"[_\-.]+", " ", blob)
    for pat, name, tags in GAMES:
        if strong_only and name in WEAK: continue
        if re.search(r"(?<![a-z0-9])(?:" + pat + r")(?![a-z0-9])", blob): return name, list(tags)
    return "", []


def game_votes(text, strong_only=False):
    """How often each known game is mentioned in `text` -> {name: count}. A longer name wins over a shorter one for the same words."""
    blob = re.sub(r"[_\-.]+", " ", (text or "").lower()); votes = {}
    for pat, name, tags in GAMES:
        if strong_only and name in WEAK: continue
        rx = re.compile(r"(?<![a-z0-9])(?:" + pat + r")(?![a-z0-9])")
        n = len(rx.findall(blob))
        if n:
            votes[name] = votes.get(name, 0) + n; blob = rx.sub(" ", blob)
    return votes


def sentences(words, gap=0.7):
    """Split word list [{'w','start','end'}] into spoken sentences: end punctuation, or a pause."""
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        t = w["w"].strip()
        nxt = words[i + 1]["start"] - w["end"] if i + 1 < len(words) else 9
        if re.search(r"[.!?…。！？]$", t) or nxt > gap or len(cur) >= 16:
            out.append(cur); cur = []
    if cur: out.append(cur)
    return [dict(text=" ".join(x["w"] for x in s).strip(), start=s[0]["start"], end=s[-1]["end"], n=len(s)) for s in out]


def analyze(words, game="", hint="", name_hint=""):
    """What is this clip about? -> dict(text, angles[(angle, score)], keywords, quote, game, gtags, sents, cjk)"""
    text = " ".join(w["w"] for w in words).strip()
    cjk = is_cjk(text)
    toks = tokens(text)
    low = " " + text.lower() + " "
    sc = {}
    for ang, lex in ANGLE_WORDS.items():
        n = sum(1 for t in toks if t in lex)
        sc[ang] = float(n)
    for ang, pat in PHRASE_ANGLE: sc[ang] = sc.get(ang, 0) + 1.5 * len(re.findall(pat, low))
    ex, qs = text.count("!"), text.count("?")
    sc["hype"] += ex * .35; sc["shock"] += qs * .25 + ex * .1
    caps = sum(1 for w in words if len(w["w"]) > 2 and w["w"].isupper()); sc["rage"] += caps * .3; sc["scream"] += caps * .15
    sc["chaos"] = 0.0
    angles = [(a, round(v, 2)) for a, v in sorted(sc.items(), key=lambda kv: -kv[1]) if v >= 1.0]
    sents = sentences(words)
    g, gt = find_game(game, hint, name_hint)
    if not g: g, gt = find_game(text, strong_only=True)
    if game and not g: g, gt = game.strip(), [camel(game)]
    # keywords: repeated content words and Capitalised words in the middle of a sentence
    freq, caps_mid = {}, {}
    for s in sents:
        ws = s["text"].split()
        for j, w in enumerate(ws):
            c = re.sub(r"[^A-Za-z']", "", w)
            if len(c) < 4 or c.lower() in STOP or PROFANE.search(c): continue
            freq[c.lower()] = freq.get(c.lower(), 0) + 1
            if j > 0 and c[:1].isupper() and not c.isupper(): caps_mid[c.lower()] = caps_mid.get(c.lower(), 0) + 1
    kws = sorted(freq, key=lambda k: -(freq[k] + 2 * caps_mid.get(k, 0) + .01 * len(k)))
    kws = [k for k in kws if freq[k] >= 3 or caps_mid.get(k)][:6]
    # quote: the punchiest short sentence
    best, bs = None, -1
    try: import vcsmart as _vs
    except Exception: _vs = None
    for s in sents:
        n = s["n"]
        if n < 3 or n > 12 or is_cjk(s["text"]): continue
        if _vs:                                                   # 2.2: "hahaha hahaha hahaha" or "AAAAH" is not a quote
            tk_ = [_vs.clean(x) for x in s["text"].split()]
            if tk_ and sum(1 for x in tk_ if _vs.is_laugh(x) or _vs.is_scream(x)) / len(tk_) >= .5: continue
        st = tokens(s["text"]); v = sum(1 for t in st if any(t in l for l in ANGLE_WORDS.values())) * 1.2
        v += 1.5 * s["text"].count("!") + .8 * s["text"].count("?") + (1 if 4 <= n <= 8 else 0) + 0.5 * sum(1 for t in st if t not in STOP) / max(1, len(st))
        if PROFANE.search(s["text"]): v -= 1.0
        if re.match(r"^(and|but|so|um|uh|like)\b", s["text"].lower()): v -= .6
        if v > bs: best, bs = s, v
    quote = tidy_quote(best["text"]) if best else ""
    return dict(text=text, angles=angles, keywords=kws, quote=quote, game=g, gtags=gt, sents=sents, cjk=cjk, caps=caps, exclaim=ex)


def tidy_quote(q, limit=48):
    q = re.sub(r"\s+", " ", q).strip(" ,;:-")
    q = re.sub(r"^(and|but|so|um|uh|like|well|okay|ok)\s+", "", q, flags=re.I)
    if len(q) > limit:
        cut = q[:limit].rsplit(" ", 1)[0]
        q = cut.rstrip(",;:-") + "…"
    q = q[:1].upper() + q[1:]
    return mask(q.rstrip(".,"))


# ------------------------------------------------------------------ hashtag banks
COMMUNITY = ["VTuber", "VTubers", "VTuberClips", "ENVtuber", "VTuberEN"]
STREAMER = ["Streamer", "StreamerClips", "TwitchClips", "KickStreamer", "Clips"]
CONTENT = {
    "funny": ["Funny", "FunnyMoments", "Comedy", "Lol"], "shock": ["Reaction", "Shocked", "Unexpected"], "scream": ["Scream", "Jumpscare", "Reaction"],
    "rage": ["Rage", "GamingFails", "Relatable"], "clutch": ["Clutch", "GamingClips", "Highlights"], "fail": ["Fail", "GamingFails", "Funny"],
    "wholesome": ["Wholesome", "Cute", "Cozy"], "story": ["Storytime", "Storytelling"], "hype": ["Hype", "GamingClips", "Highlights"], "cozy": ["CozyGaming", "Chill", "Cozy"],
    "chaos": ["Chaos", "GamingClips"],
}
GENERIC_CONTENT = ["GamingClips", "StreamHighlights", "Funny"]


def hashtags(platform, ctx, n=None, reach=False, extra=()):
    """The best few hashtags for one platform. ctx = analyze() result (+ 'vtuber': bool, 'channel': str)."""
    cap = dict(shorts=4, tiktok=5, reels=5, twitter=3).get(platform, 5)
    n = max(1, min(n or cap, cap if platform in ("reels", "twitter") else 8))
    pool = []
    pool += [(t, 5) for t in extra]
    pool += [(t, 4.5 - .2 * i) for i, t in enumerate(ctx.get("gtags", [])[:1 if platform == "twitter" else 2])]
    for rank, (a, _) in enumerate(ctx.get("angles", [])[:2]):
        pool += [(t, 3.6 - .5 * i - .4 * rank) for i, t in enumerate(CONTENT.get(a, [])[:3])]
    pool += [(t, 1.8 - .3 * i) for i, t in enumerate(GENERIC_CONTENT)]
    if ctx.get("vtuber", True): pool += [("VTuber", 4.2), ("VTuberClips", 2.6), ("VTubers", 2.0)]
    if platform == "shorts": pool += [("Shorts", 4.0)]
    if platform == "tiktok": pool += [("TwitchClips", 1.5), ("Streamer", 1.4)]
    if platform == "reels": pool += [("Streamer", 1.6), ("TwitchClips", 1.4), ("GamingClips", 1.5)]
    if platform == "twitter": pool += [("Clips", .5)]
    if reach and platform == "tiktok": pool += [("fyp", 2.0)]
    ch = re.sub(r"[^0-9A-Za-z]", "", ctx.get("channel", "") or "")
    if ch and platform != "twitter": pool += [(ch, 2.3)]
    seen, out = set(), []
    for t, _ in sorted(pool, key=lambda x: -x[1]):
        t = camel(t) if not t.isupper() else t
        if not t or BAD_TAG_WORDS.search(t) or t.lower() in seen: continue
        seen.add(t.lower()); out.append("#" + t)
    out = out[:n]
    if platform == "shorts" and "#shorts" not in [x.lower() for x in out]:
        out = out[:max(1, n - 1)] + ["#Shorts"]
    if platform == "shorts":                                  # YouTube shows the first three above the title - #Shorts goes last
        out = [x for x in out if x.lower() != "#shorts"] + ["#Shorts"]
    return out[:cap]


# ------------------------------------------------------------------ titles
T = {
    "funny": ["I can't stop laughing at this {g} moment 😭", "{G} had me in TEARS 😭", "The funniest {g} moment you'll see today 😂", "Nobody was ready for this 😭"],
    "shock": ["I did NOT expect this in {g} 😳", "Wait… what just happened?! 😳", "This {g} moment broke my brain 🤯", "How did that even happen?! 😳"],
    "scream": ["{G} scared me so bad 😱", "I screamed so loud 😱", "This {g} jumpscare got me 💀", "My reaction says it all 😱"],
    "rage": ["{G} made me lose it 😤", "I cannot believe this happened in {g} 😤", "{G} is testing my patience 😤", "This is why I rage in {g} 😭"],
    "clutch": ["This {g} clutch was INSANE 🔥", "I can't believe that worked 🔥", "Clutch of the stream 🔥", "{G} but I actually pull it off 😤"],
    "fail": ["{G} but I fail in the most embarrassing way 💀", "Why did I do that?! 💀", "This {g} fail was SO bad 😭", "Peak {g} gameplay right here 💀"],
    "wholesome": ["This is why I love streaming 🥹", "Chat made me emotional 🥹", "The sweetest {g} moment 🥹", "Wholesome moment of the stream 🥹"],
    "story": ["Story time: {q}", "You won't believe what happened 👀", "This story is wild 👀", "Storytime that got out of hand 👀"],
    "hype": ["CHAT WAS GOING CRAZY 🔥", "This {g} moment was PURE hype 🔥", "Let's gooo!! 🔥", "The hype was real 🔥"],
    "cozy": ["Cozy {g} vibes ☁️", "Just a chill moment from the stream ☁️", "Cozy stream moment ☁️"],
    "": ["Stream moment you can't miss 👀", "Best moment of the stream 🔥", "{G} highlights that hit different 🔥"],
}


def _fill(tpl, ctx, q, name):
    """Fill {g}/{G}/{q}. Without a known game, lines that need one are dropped (None) or lose the game words."""
    game = ctx.get("game") or ""
    if not game:
        if re.search(r"\b(in|of|from|at) \{g\}|\{g\}$|\bthe \{g\}", tpl): return None
        tpl = tpl.replace("{G} ", "This stream ").replace("{g} ", "stream ")
    return tpl.replace("{q}", q or "Stream highlight").replace("{g}", game).replace("{G}", game)


def titles(ctx, seed=0, n=6, limit=70):
    rng = _rng(seed, "t", ctx.get("quote", ""))
    angs = [a for a, _ in ctx.get("angles", [])[:2]] or [""]
    pool = []
    for a in angs: pool += T.get(a, T[""])
    rng.shuffle(pool)
    pool += T[""]                                              # generic lines only fill the gaps
    q = ctx.get("quote", "")
    seen, out = set(), []
    if q: out.append(f"“{q}” {EMOJI.get(angs[0], '👀')}" if not q.endswith("…") else f"“{q}”")
    for t in pool:
        if "{q}" in t and not q: continue
        s = _fill(t, ctx, q, "")
        if not s or len(s) > limit or s in seen: continue
        seen.add(s); out.append(s)
        if len(out) >= n: break
    return out[:n]


# ------------------------------------------------------------------ X (Twitter) posts
TW = {
    "funny": [("Curiosity", "I wasn't ready for how this ended 😭"), ("Bold claim", "This might be the funniest {g} clip I've ever posted 😭"), ("Question", "Is it just me or is this hilarious? 😭"),
              ("Engage", "Rate this clip 1-10 👇😭"), ("Teaser", "Wait for the end 😭")],
    "shock": [("Curiosity", "I thought this would be easy. Then THIS happened 😳"), ("Bold claim", "Nobody saw this coming in {g} 😳"), ("Question", "Would you have survived this? 👀"),
              ("Engage", "Be honest, what would you have done? 👇"), ("Teaser", "Watch till the end, it gets worse 😳")],
    "scream": [("Curiosity", "I was NOT prepared for this 😱 (sound on)"), ("Bold claim", "My loudest scream ever, no contest 😱"), ("Question", "Would you have screamed too? 😱"),
               ("Engage", "Rate my scream 1-10 👇"), ("Teaser", "Sound on. Trust me. 😱")],
    "rage": [("Curiosity", "I lasted exactly this long before losing it 😤"), ("Bold claim", "{G} should be illegal after this 😤"), ("Question", "Is this game broken or am I just bad? 😤"),
             ("Engage", "Tell me I'm not the only one 👇😤"), ("Teaser", "Watch what happens at the end 😤")],
    "clutch": [("Curiosity", "I had a 1% chance. Watch what happens 🔥"), ("Bold claim", "Best {g} clutch of my life 🔥"), ("Question", "Did that really just work?! 👀"),
               ("Engage", "Rate this clutch 1-10 👇🔥"), ("Teaser", "Wait for it… 🔥")],
    "fail": [("Curiosity", "It was going SO well until this 💀"), ("Bold claim", "The worst play in {g} history 💀"), ("Question", "How do you even mess that up? 💀"),
             ("Engage", "Tell me you've done this too 👇💀"), ("Teaser", "Wait for the end 💀")],
    "wholesome": [("Curiosity", "I didn't expect to get emotional about this 🥹"), ("Bold claim", "Streaming moments like this are why I keep going 🥹"), ("Question", "Is this the most wholesome moment ever? 🥹"),
                  ("Engage", "Share this with someone who needs it 🥹"), ("Teaser", "Watch till the end 🥹")],
    "story": [("Curiosity", "So this actually happened to me… 👀"), ("Bold claim", "The wildest story I've told on stream 👀"), ("Question", "Would you have believed me? 👀"),
              ("Engage", "Tell me yours in the replies 👇"), ("Teaser", "Wait for the plot twist 👀")],
    "hype": [("Curiosity", "Chat went completely feral after this 🔥"), ("Bold claim", "The most hype moment of the stream, no debate 🔥"), ("Question", "Was that the best moment ever? 🔥"),
             ("Engage", "Rate the hype 1-10 👇🔥"), ("Teaser", "Watch till the end 🔥")],
    "cozy": [("Curiosity", "Just a cozy moment from tonight's stream ☁️"), ("Bold claim", "This is the vibe 100% ☁️"), ("Question", "Anyone else need a cozy night like this? ☁️"),
             ("Engage", "Tell me what you're playing tonight 👇"), ("Teaser", "Stay till the end ☁️")],
    "": [("Curiosity", "I did not expect this to happen on stream 👀"), ("Bold claim", "This is the best clip of the week, fight me 🔥"), ("Question", "What would YOU have done here? 👀"),
         ("Engage", "Rate this clip 1-10 👇"), ("Teaser", "Watch till the end 👀")],
}


def twitter_posts(ctx, seed=0, late_peak=False, hashtags_on=True, n=5, limit=240):
    rng = _rng(seed, "x", ctx.get("quote", ""))
    angs = [a for a, _ in ctx.get("angles", [])[:2]] or [""]
    items = list(TW.get(angs[0], TW[""]))
    if len(angs) > 1 and angs[1] in TW:
        o = TW[angs[1]]; items[2] = o[2]; items[3] = o[3]
    out = []
    q = ctx.get("quote", "")
    for label, tpl in items:
        game = ctx.get("game") or ""
        if not game and "{G}" in tpl: continue
        if not game: tpl = re.sub(r"\s+(in|of|from)\s+\{g\}", "", tpl).replace("{g} ", "")
        s = tpl.replace("{g}", game).replace("{G}", game)
        if label == "Teaser" and not late_peak: s = s.replace("Wait for the end", "Watch this").replace("Watch till the end", "Watch this")
        out.append(dict(label=label, text=s))
    if q and len(q) > 8:
        out.insert(1, dict(label="Quote", text=f"“{q}” 👀" if not q.endswith("…") else f"“{q}”"))
    rng.shuffle(out)
    first = [x for x in out if x["label"] in ("Curiosity", "Bold claim")][:1]
    rest = [x for x in out if x not in first]
    out = (first + rest)[:n]
    for x in out: x["text"] = x["text"][:limit]
    return out


# ------------------------------------------------------------------ YouTube description, TikTok / Reels captions
def _cta(platform, ctx, handle=""):
    h = handle.strip()
    if h and not h.startswith("@"): h = "@" + h
    if platform == "shorts": return "🔔 Subscribe for more clips" + (f" from {ctx['channel']}" if ctx.get("channel") else "") + "!"
    if platform == "tiktok": return "Follow for more " + (f"{ctx['game']} " if ctx.get("game") else "") + "clips ♡"
    return "Follow " + (h or "for more") + " for more clips ♡"


def summary_line(ctx):
    kws = ctx.get("keywords", [])
    g = ctx.get("game")
    angs = [a for a, _ in ctx.get("angles", [])[:1]]
    what = {"funny": "a hilarious moment", "shock": "a moment nobody saw coming", "scream": "a seriously scary moment", "rage": "a rage-inducing moment", "clutch": "an unbelievable clutch",
            "fail": "a painful fail", "wholesome": "a wholesome moment", "story": "a wild story", "hype": "a hype moment", "cozy": "a cozy moment"}.get(angs[0] if angs else "", "a moment")
    s = f"Here's {what}" + (f" from my {g} stream" if g else " from my stream") + "."
    if len(kws) >= 2: s += f" Featuring: {', '.join(kws[:3])}."
    return s


def kind_titles(kind, ctx, seed=0, limit=70):
    """2.2: title ideas that fit the kind of clip (gameplay / reaction / talking / story / singing)."""
    try: import vcsmart
    except Exception: return []
    tpl = vcsmart.TITLE_TEMPLATES.get(kind) or []
    if not tpl: return []
    g = (ctx.get("game") or "").strip(); q = (ctx.get("quote") or "").rstrip("…").strip(); out = []
    for i in range(len(tpl)):
        t = tpl[(seed + i) % len(tpl)]
        if ("{g}" in t or "{G}" in t) and not g: continue
        if "{q}" in t and len(q.split()) < 3: continue
        t = t.replace("{G}", g).replace("{g}", g).replace("{q}", q)
        if len(t) <= limit and t not in out: out.append(t)
    return out[:2]


def make_kit(words, game="", channel="", handle="", links="", hint="", name_hint="", seed=0, vtuber=True, late_peak=False, reach=False, x_tags=True, dur=None, extra=(), kind=None):
    ctx = analyze(words, game, hint, name_hint)
    ctx.update(channel=(channel or "").strip(), vtuber=vtuber)
    ts = titles(ctx, seed)
    if not ts: ts = ["Stream highlight 🔥"]
    if kind:
        kt = [t for t in kind_titles(kind, ctx, seed) if t not in ts]
        ts = ts[:1] + kt + ts[1:]
        ts = ts[:max(6, len(ts))]
    yt_tags = hashtags("shorts", ctx, extra=extra); tt_tags = hashtags("tiktok", ctx, reach=reach, extra=extra); ig_tags = hashtags("reels", ctx, extra=extra); x_tg = hashtags("twitter", ctx, n=3, extra=extra)
    quote = ctx["quote"]
    first = ts[0]
    # YouTube
    yt_title = next((t for t in ts if len(t) <= 60), ts[0])[:100]
    d = [yt_title, "", summary_line(ctx)]
    if quote and not ctx["cjk"] and quote not in yt_title: d += ["", f"“{quote}”"]
    d += ["", _cta("shorts", ctx, handle)]
    if links.strip(): d += ["", links.strip()]
    if ctx.get("game"): d += ["", f"🎮 Game: {ctx['game']}"]
    d += ["", " ".join(yt_tags)]
    yt_desc = "\n".join(d)
    # TikTok / Reels
    tt_cap = f"{ts[min(1, len(ts) - 1)]}\n\n{_cta('tiktok', ctx)}\n{' '.join(tt_tags)}"
    ig_cap = f"{ts[min(2, len(ts) - 1)]}\n\n{_cta('reels', ctx, handle)}\n\n{' '.join(ig_tags)}"
    posts = twitter_posts(ctx, seed, late_peak, x_tags)
    return dict(titles=ts, youtube=dict(title=yt_title, description=yt_desc, hashtags=yt_tags), tiktok=dict(caption=tt_cap, hashtags=tt_tags),
                reels=dict(caption=ig_cap, hashtags=ig_tags), twitter=dict(posts=posts, hashtags=x_tg),
                meta=dict(game=ctx["game"], angles=[a for a, _ in ctx["angles"][:3]], keywords=ctx["keywords"], quote=quote))


def kit_text(kit, hype=None):
    m = kit["meta"]
    lines = []
    if hype is not None: lines += [f"HYPE SCORE  {hype}/100", ""]
    lines += ["TITLE IDEAS"] + [f"  {i}. {t}" for i, t in enumerate(kit["titles"], 1)]
    lines += ["", "YOUTUBE SHORTS", f"  Title: {kit['youtube']['title']}", "  Hashtags: " + " ".join(kit["youtube"]["hashtags"]) + "   (description below)",
              "", "TIKTOK CAPTION", kit["tiktok"]["caption"], "", "INSTAGRAM REELS CAPTION", kit["reels"]["caption"], "", "X (TWITTER) POSTS"]
    for p in kit["twitter"]["posts"][:3]: lines.append(f"  - {p['text']}")
    lines += ["  hashtags: " + " ".join(kit["twitter"]["hashtags"])]
    # keep the v1.2 layout parsed by the My clips gallery: "DESCRIPTION\n...\n\nHASHTAGS\n..."
    lines += ["", "DESCRIPTION", kit["youtube"]["description"], "", "HASHTAGS", " ".join(kit["youtube"]["hashtags"])]
    return "\n".join(lines) + "\n"
