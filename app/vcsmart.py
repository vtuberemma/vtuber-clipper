"""VTuber Clipper 2.2 - smart clip finding. No model, no internet: word lists and rules of thumb about what makes a VTuber moment work,
collected from published short-video advice (hook in the first 3 seconds, no greetings, length by kind of clip, a beat every few seconds,
end right after the payoff) and from the kinds of moments that become VTuber clips (gameplay fails and clutches, chaotic reactions,
laughing fits, jump-scare screams, storytime, karaoke). They only nudge the clip finder; the user's own picks (taste) nudge it further.
Every function here works on the transcript (list of {w, start, end}) and plain numbers, so it is easy to test."""
import bisect, json, math, os, re, time

clean = lambda w: re.sub(r"[^\w']", "", str(w).lower().replace("_", ""))

# ================================================================ word groups
_RE_LAUGH = re.compile(r"^(?:(?:ha|he|ah|eh|hi){2,}h?|bwa(?:ha)+|mu(?:ha)+h?|ja(?:ja)+j?a?|k{3,}|ㅋ+|ㅎ{2,}|w{2,}|rsrs+|lol+|lmao+|lmfao+|rofl|kekw+|lulw?|omegalul|pfft+|heh+|www+)$")
_RE_SCREAM = re.compile(r"^(?:a{3,}h*|ah{3,}|aa+h+|eek+|eep+|ky?a{2,}h*|gah+|argh+|waa+h*|noo{3,}|no{4,}|ahh+|aah+|ugh+|yaa+h*|iyaa+h*)$")
LAUGH_PLAIN = {"laughing", "giggle", "giggling", "cackle", "cackling", "笑", "草", "笑った", "爆笑", "わろた", "ワロタ", "ㅋㅋ", "ㅎㅎ", "jajaja", "kkkk", "mdr", "ptdr"}
SCREAM_PLAIN = {"きゃー", "ぎゃー", "きゃあ", "ぎゃあ", "ひぃ", "うわー", "うわああ", "아악", "꺄악", "으악", "scream", "screaming", "jumpscare", "jumpscared"}
FAIL_W = set("died die dies dying dead rip oof oop oops whoops fail failed fails lost lose losing wasted noob trash misclick missed fell crashed glitch bug stuck bruh yikes cooked".split())
WIN_W = set("clutch won win winner winning victory ace gg ggs ez poggers pog pogchamp finally goated carried carry insane yay woo woohoo yass slay nice flawless perfect".split())
RAGE_W = set("stupid annoying seriously unbelievable hate rage ridiculous cheater cheating cheats unplayable garbage bullshit damn dumb idiot".split())
SCARE_W = set("scary scared creepy jumpscare ghost monster behind help nope terrified terrifying hiding dark horror spooky nightmare".split())
CUTE_W = set("cute aww awww uwu owo nya nyaa kawaii adorable hug pat headpat soft tiny fluffy smol precious sweet".split())
CHAOS_W = set("chaos chaotic unhinged feral cursed wtf bruh stop insane crazy bonk bonked".split())
SING_W = set("sing singing sang song songs karaoke chorus verse lyrics cover melody note notes".split())
# extra single words that count as hype when the clip finder is in smart mode (the original list stays as it was)
HYPE_PLUS = set("cooked goated slay sheesh yikes bonk bonked oop oops whoops unhinged feral cursed rizz yass woo woohoo yay noo noooo nooooo ahhh ahhhh aaaah eek eeek "
                "kyaa kya gahh cmon clutch ace flawless ez poggers pogchamp kekw omegalul lulw monkaS monkas pepega sadge copium hopium nani eeeh ehh".lower().split())
HYPE_PHRASES = [("no", "way"), ("no", "shot"), ("oh", "my", "god"), ("oh", "no"), ("are", "you", "serious"), ("what", "the"), ("let's", "go"), ("lets", "go"),
                ("let's", "gooo"), ("i'm", "dead"), ("im", "dead"), ("i", "can't"), ("cant", "breathe"), ("skill", "issue"), ("what", "is", "happening"), ("did", "that", "just"),
                ("holy", "shit"), ("holy", "cow"), ("hold", "on"), ("wait", "what"), ("are", "you", "kidding"), ("you", "did", "not"), ("i'm", "so", "cooked"), ("we", "did", "it")]
GREET = [re.compile(p) for p in (
    r"^(?:hey|hi|hello|yo|sup|good (?:morning|evening|afternoon|night))\b[^.!?]{0,40}\b(?:guys|everyone|everybody|chat|friends|all|stream|y'?all)\b",
    r"^welcome (?:back|in|to)\b[^.!?]{0,40}", r"^what'?s up\b[^.!?]{0,30}", r"^how(?:'?s| is| are) (?:everyone|everybody|you all|you guys|chat)\b[^.!?]{0,30}",
    r"^thanks? (?:for|to everyone)\b[^.!?]{0,40}", r"^before we (?:start|begin|get started)\b[^.!?]{0,40}", r"^(?:so )?today (?:we(?:'re| are)|i'?m|i am) (?:going|gonna)\b[^.!?]{0,40}",
    r"^(?:okay|ok|alright|all right)(?: so)?,? (?:guys|chat|everyone)\b[^.!?]{0,30}", r"^(?:hello|hi|hey) (?:and )?welcome\b[^.!?]{0,40}")]
FILLER_START = {"um", "uh", "uhm", "erm", "er", "hmm", "mm", "uhh", "umm"}
STORY_OPEN = [("so", "one", "time"), ("one", "time"), ("so", "there", "was", "this", "time"), ("okay", "so"), ("ok", "so"), ("so", "basically"), ("story", "time"), ("storytime",),
              ("let", "me", "tell", "you"), ("you", "guys", "won't", "believe"), ("you", "won't", "believe"), ("so", "yesterday"), ("so", "the", "other", "day"), ("so", "when", "i", "was"),
              ("back", "when"), ("so", "i", "was"), ("so", "this", "happened"), ("so", "something", "happened"), ("i", "have", "a", "story"), ("this", "one", "time"), ("so", "last", "week")]
STORY_CLOSE = [("and", "that's", "why"), ("and", "thats", "why"), ("and", "that", "is", "why"), ("anyway",), ("anyways",), ("and", "that", "was", "it"), ("the", "end",),
               ("long", "story", "short"), ("and", "that's", "how"), ("and", "thats", "how"), ("that's", "the", "story"), ("thats", "the", "story"), ("and", "yeah",),
               ("so", "yeah",), ("and", "that's", "the", "story"), ("needless", "to", "say"), ("to", "this", "day"), ("never", "again")]
NARRATIVE = set("then suddenly apparently turns turned anyway basically literally because after before yesterday remember ago once finally eventually meanwhile".split())
PAST = set("was were had went said told thought knew saw felt got came did asked looked walked ran heard found took gave made called happened decided wanted started stopped".split())
FIRST = {"i", "me", "my", "we", "our", "i'm", "i've", "i'd", "i'll", "mine", "myself"}
GAME_W = set("kill killed killing enemy enemies boss level health hp loot respawn team teammate teammates round defuse lobby queue rank ranked damage heal healing jump dodge parry "
             "ammo reload shoot shot sniper spawn push rotate flank wipe ult ultimate cooldown quest dungeon raid build craft mine creeper zombie drop checkpoint restart "
             "speedrun crouch sprint aim headshot grenade rocket weapon gun sword shield armor potion map spawn camper campers lag ping fps".split())
TALK_W = set("think opinion honestly actually personally unpopular tbh imo believe feel agree disagree reason problem thing people everyone always never maybe probably "
             "important question answer idea understand mean really".split())
QUESTION_OPEN = {"what", "why", "how", "who", "did", "have", "can", "could", "would", "guess", "wait", "is", "are", "do", "does", "should"}

# ================================================================ kinds of moments
TYPES = ("gameplay", "reaction", "talking", "story", "singing")
TYPE_INFO = {
    "gameplay": dict(label="Gameplay", icon="🎮", style="gameplay", cap="pop", gap=1.5, lo=18, hi=35, hint="Action, fails and clutches"),
    "reaction": dict(label="Reaction", icon="😱", style="gameplay", cap="pop", gap=1.2, lo=12, hi=28, hint="Screams, laughs and big reactions"),
    "talking": dict(label="Talking", icon="💬", style="mix", cap="karaoke", gap=1.3, lo=22, hi=45, hint="Opinions, chat and funny talk"),
    "story": dict(label="Story", icon="📖", style="story", cap="line", gap=1.2, lo=35, hi=60, hint="A story with a start and an ending"),
    "singing": dict(label="Singing", icon="🎤", style="story", cap="karaoke", gap=None, lo=25, hi=55, hint="Karaoke and singing"),
}
STYLE_OF = {k: v["style"] for k, v in TYPE_INFO.items()}


def type_label(t): return TYPE_INFO.get(t, {}).get("label", "")
def type_icon(t): return TYPE_INFO.get(t, {}).get("icon", "")


# ================================================================ reading the words
_IDX = {"key": None, "starts": [], "sorted": True}


def wslice(words, a=None, b=None):
    """The words that start inside [a, b). Fast for long transcripts (it looks the start up in a sorted list instead of walking through every word)."""
    if not words: return []
    key = (id(words), len(words), words[0]["start"], words[-1]["start"])
    if _IDX["key"] != key:
        st = [float(w["start"]) for w in words]
        _IDX.update(key=key, starts=st, sorted=all(st[i] <= st[i + 1] for i in range(len(st) - 1)))
    if not _IDX["sorted"]:
        return [w for w in words if (a is None or w["start"] >= a) and (b is None or w["start"] < b)]
    st = _IDX["starts"]
    i = 0 if a is None else bisect.bisect_left(st, a)
    j = len(words) if b is None else bisect.bisect_left(st, b)
    return words[i:j]


def toks(words, a=None, b=None):
    """[(cleaned word, start, end)] of the words that start inside [a, b)."""
    return [(clean(w["w"]), float(w["start"]), float(w["end"])) for w in wslice(words, a, b) if clean(w["w"])]


def is_laugh(t): return t in LAUGH_PLAIN or bool(_RE_LAUGH.match(t))
def is_scream(t): return t in SCREAM_PLAIN or bool(_RE_SCREAM.match(t))


def phrase_times(tk, phrases):
    """Start times of every place where one of the phrases (tuples of cleaned words) is said in a row."""
    out = []; ks = [t[0] for t in tk]
    for ph in phrases:
        n = len(ph)
        for i in range(len(ks) - n + 1):
            if tuple(ks[i:i + n]) == ph: out.append(tk[i][1])
    return sorted(out)


VOCAB_FILE = os.path.join(os.path.expanduser("~"), ".vtuberclipper_vocab.json")
VOCAB_KINDS = ("laugh", "scream", "fail", "win", "rage", "scare", "cute", "hype", "chaos")
_VOC = {"stamp": "unset", "sets": {}}


def user_vocab():
    """The words the creator taught the app (her chat's own slang, a catch-phrase...): {kind: set(words)}. Re-read when the file changes, so a word added in the Tools window works on the next run."""
    try: st = os.stat(VOCAB_FILE); stamp = (st.st_mtime_ns, st.st_size)
    except OSError: stamp = None
    if stamp != _VOC["stamp"]:
        sets = {}
        try:
            if stamp is not None:
                with open(VOCAB_FILE, encoding="utf-8") as f: d = json.load(f)
                for k in VOCAB_KINDS:
                    v = d.get(k) if isinstance(d, dict) else None
                    if isinstance(v, list): sets[k] = {c for c in (clean(x) for x in v if isinstance(x, str) and len(x.strip()) <= 30) if c}
        except Exception: sets = {}
        _VOC["stamp"], _VOC["sets"] = stamp, sets
    return _VOC["sets"]


def word_marks(words, n):
    """Per-second arrays from the transcript: how many laugh / scream / fail / win / rage / scare / cute / hype-phrase / question words start in each second."""
    import numpy as np
    keys = ("laugh", "scream", "fail", "win", "rage", "scare", "cute", "hype", "chaos", "game", "talk", "sing")
    m = {k: np.zeros(n, np.float32) for k in keys}
    tk = toks(words); uv = user_vocab()
    for t, s, e in tk:
        i = int(s)
        if not 0 <= i < n: continue
        for k_, set_ in uv.items():
            if t in set_: m[k_][i] += 1
        if is_laugh(t): m["laugh"][i] += 1
        if is_scream(t): m["scream"][i] += 1
        if t in FAIL_W: m["fail"][i] += 1
        if t in WIN_W: m["win"][i] += 1
        if t in RAGE_W: m["rage"][i] += 1
        if t in SCARE_W: m["scare"][i] += 1
        if t in CUTE_W: m["cute"][i] += 1
        if t in HYPE_PLUS: m["hype"][i] += 1
        if t in CHAOS_W: m["chaos"][i] += 1
        if t in GAME_W: m["game"][i] += 1
        if t in TALK_W: m["talk"][i] += 1
        if t in SING_W: m["sing"][i] += 1
    for s in phrase_times(tk, HYPE_PHRASES):
        if 0 <= int(s) < n: m["hype"][int(s)] += 1.5
    return m


# ================================================================ what kind of moment is it
def window_stats(words, a, b, marks=None, curves=None, sc=None):
    """Numbers about the window [a, b) that decide its kind. marks = word_marks(), curves = vcsense curves, sc = the per-second score (for loudness variety)."""
    import numpy as np
    d = max(1.0, b - a); ia, ib = int(a), max(int(a) + 1, int(math.ceil(b)))
    tk = toks(words, a, b); n = len(tk)
    st = dict(dur=d, n=n, wps=n / d)
    st["past"] = sum(1 for t, _, _ in tk if t in PAST) / max(1, n)
    st["narr"] = sum(1 for t, _, _ in tk if t in NARRATIVE) / max(1, n)
    st["first"] = sum(1 for t, _, _ in tk if t in FIRST) / max(1, n)
    st["opens"] = len(phrase_times(tk, STORY_OPEN)); st["closes"] = len(phrase_times(tk, STORY_CLOSE))
    ws = wslice(words, a, b)
    st["excl"] = sum(1 for w in ws if w["w"].rstrip()[-1:] in "!！") / max(1, len(ws)); st["ques"] = sum(1 for w in ws if w["w"].rstrip()[-1:] in "?？") / max(1, len(ws))
    sents, cur = [], 0
    for w in ws:
        cur += 1
        if w["w"].rstrip()[-1:] in ".!?。！？": sents.append(cur); cur = 0
    if cur: sents.append(cur)
    st["sent"] = sum(sents) / max(1, len(sents)) if sents else 0.0
    cov = 0.0
    if ws:
        cov = min(1.0, sum(min(w["end"], b) - max(w["start"], a) for w in ws) / d)
    st["cover"] = cov
    for k in ("laugh", "scream", "fail", "win", "rage", "scare", "cute", "hype", "chaos", "game", "talk", "sing"):
        v = marks.get(k) if marks else None
        st["w_" + k] = float(np.sum(v[ia:ib])) / d if v is not None and len(v[ia:ib]) else 0.0
    for k in ("laugh", "scream", "sing", "setup", "voiced"):
        v = curves.get(k) if curves else None
        st["c_" + k] = float(np.mean(v[ia:ib])) if v is not None and len(v[ia:ib]) else 0.0
        st["m_" + k] = float(np.max(v[ia:ib])) if v is not None and len(v[ia:ib]) else 0.0
    st["var"] = float(np.std(sc[ia:ib])) if sc is not None and len(sc[ia:ib]) > 2 else 0.0
    return st


def classify(st):
    """-> (type, confidence 0..1, {type: score}). Rules of thumb, not a trained model; they can be wrong, so the app shows the result and lets you override."""
    sing = max(0.0, (st["c_sing"] - .20) * 3.2) + (.35 if st["w_sing"] > .05 else 0.0) * (st["c_sing"] > .1)
    sing *= 1.0 if st["c_voiced"] > .35 else .3
    story = (8.0 * max(0.0, st["past"] + .8 * st["narr"] - .10) + .8 * st["first"] + .55 * min(2, st["opens"]) + .5 * min(2, st["closes"])
             + .3 * max(0.0, min(1.0, (st["sent"] - 6) / 10))) * (1.0 if st["cover"] > .55 else .5)
    gameplay = 6.0 * st["w_game"] + 2.0 * st["w_fail"] + 1.5 * st["w_win"] + 1.2 * st["w_scare"] + .6 * max(0.0, .6 - st["cover"]) + .4 * min(1.0, st["var"] / 1.5) + 1.0 * st["w_rage"]
    reaction = (2.4 * st["m_scream"] + 1.8 * st["c_laugh"] * 2 + 1.0 * st["m_laugh"] + 2.5 * st["w_laugh"] + 2.5 * st["w_scream"] + 2.0 * st["excl"] + 1.2 * st["w_hype"] + 1.0 * st["m_setup"]
                + .7 * st["w_chaos"] + .5 * st["ques"])
    talking = .35 + 1.4 * st["w_talk"] + .5 * max(0.0, st["cover"] - .6) + (.25 if st["wps"] > 1.6 else 0.0) + .35 * max(0.0, 1.0 - st["var"] / 1.5)
    s = dict(gameplay=gameplay, reaction=reaction, talking=talking, story=story, singing=sing)
    if st["n"] < 3 and st["c_sing"] < .3: s["talking"] += .2
    order = sorted(s, key=lambda k: -s[k]); top, sec = s[order[0]], s[order[1]]
    return order[0], float(max(0.0, min(1.0, (top - sec) / (abs(top) + 1e-6)))), s


def type_for(words, a, b, marks=None, curves=None, sc=None):
    st = window_stats(words, a, b, marks, curves, sc)
    t, conf, sc_ = classify(st)
    return t, conf, st


# ================================================================ reasons ("why this moment")
def _t(sec):
    sec = int(max(0, sec)); return f"{sec // 60}:{sec % 60:02d}"


def reasons(words, a, b, marks=None, curves=None, sc=None, onsets=(), chat=None, kind=None):
    """Plain sentences about why a moment is good, in order of importance."""
    import numpy as np
    out = []; ia, ib = int(a), max(int(a) + 1, int(math.ceil(b)))
    cv = lambda k: np.asarray(curves[k][ia:ib]) if curves is not None and k in curves and len(curves[k][ia:ib]) else np.zeros(1)
    mk = lambda k: np.asarray(marks[k][ia:ib]) if marks is not None and k in marks and len(marks[k][ia:ib]) else np.zeros(1)
    if kind == "singing" or cv("sing").mean() > .4: out.append("Sung part (a held melody)")
    sung = kind == "singing"
    if (cv("laugh").max() > (.85 if sung else .6) and (not sung or mk("laugh").sum() >= 2)) or mk("laugh").sum() >= 2:
        k = ia + int(np.argmax(cv("laugh") + mk("laugh"))); out.append(f"Laughing fit around {_t(k - a)}")
    if (cv("scream").max() > .35 and not sung) or mk("scream").sum() >= 1:
        k = ia + int(np.argmax(cv("scream") + mk("scream"))); out.append(f"Scream or jump scare around {_t(k - a)}")
    if cv("setup").max() > .4: out.append("A quiet beat, then a loud hit (good timing)")
    if mk("win").sum() >= 1: out.append("A win or clutch (" + ", ".join(dict.fromkeys(t for t, s, e in toks(words, a, b) if t in WIN_W))[:30] + ")")
    if mk("fail").sum() >= 1: out.append("A fail (" + ", ".join(dict.fromkeys(t for t, s, e in toks(words, a, b) if t in FAIL_W))[:30] + ")")
    if mk("hype").sum() >= 1: out.append("Hype words (" + ", ".join(list(dict.fromkeys(t for t, s, e in toks(words, a, b) if t in HYPE_PLUS))[:3]) + ")" if any(t in HYPE_PLUS for t, _, _ in toks(words, a, b)) else "Hype phrases")
    tk = toks(words, a, b)
    if phrase_times(tk, STORY_OPEN): out.append("Story that starts clearly")
    if phrase_times(tk, STORY_CLOSE): out.append("Story that ends clearly")
    if chat is not None and len(chat[ia:ib]) and float(np.max(chat[ia:ib])) > .6: out.append("Chat went wild")
    if sc is not None and len(sc[ia:ib]) and float(np.max(sc[ia:ib])) > 2.2 and not out: out.append("Loud, energetic moment")
    return out[:5] or ["Steady energy"]


# ================================================================ clip boundaries
def greeting_end(words, a, within=7.0):
    """If the clip opens with a greeting or filler ("hey guys welcome back", "um"), the time where the real content starts, else None."""
    ws = wslice(words, a - .05, a + within)
    if not ws: return None
    txt = ""; idx = []
    for i, w in enumerate(ws[:18]):
        c = clean(w["w"])
        if not c: continue
        idx.append((len(txt), i)); txt += c + " "
    txt = txt.strip()
    best = 0
    for rx in GREET:
        m = rx.match(txt)
        if m: best = max(best, m.end())
    # a greeting ends at the end of its sentence if the transcript has punctuation there
    k = 0
    if best:
        for pos, i in idx:
            if pos < best: k = i + 1
        for j in range(k, min(len(ws), k + 4)):                      # finish the sentence ("welcome back, everyone!")
            if ws[j - 1]["w"].rstrip()[-1:] in ".!?。！？": break
            if j - k >= 2: break
            k = j + 1
    else:
        while k < len(ws) and clean(ws[k]["w"]) in FILLER_START: k += 1
        if not k: return None
    if k >= len(ws): return None
    return float(ws[k]["start"])


def story_adjust(words, s, e, lo=0.0, hi=1e9, reach=14.0):
    """For a story: start on the sentence that opens it ("so one time...") when that is just before the clip, end on the sentence that closes it ("and that's why...")."""
    tk = toks(words, s - reach, e + reach)
    ns, ne = s, e
    ops = [t for t in phrase_times(tk, STORY_OPEN) if s - reach <= t <= s + (e - s) * .35]
    if ops:
        t = ops[-1] if ops[-1] <= s else min(ops, key=lambda x: abs(x - s))
        ns = max(0.0, t - .1)
    cls = [t for t in phrase_times(tk, STORY_CLOSE) if e - (e - s) * .35 <= t <= e + 9.0]
    if cls:
        t = cls[0]
        endw = [w for w in wslice(words, t, t + 14.0) if w["w"].rstrip()[-1:] in ".!?。！？"]
        ne = float(endw[0]["end"]) + .2 if endw and endw[0]["end"] - t < 9 else t + 2.2
    if not (lo <= ne - ns <= hi):
        return s, e
    return ns, ne


def payoff_end(words, s, e, sc, lo, onsets=(), tail=1.4):
    """End shortly after the last big moment instead of letting the clip run on. Returns the new end (never shorter than `lo` seconds)."""
    import numpy as np
    a, b = int(s), max(int(s) + 2, int(e))
    seg = np.asarray(sc[a:b])
    if len(seg) < 6: return e
    thr = max(1.2, .6 * float(seg.max()))
    hot = np.where(seg >= thr)[0]
    if len(hot) == 0: return e
    last = a + int(hot[-1]) + 1.0
    for t, st in onsets:
        if s <= t <= e and st >= 4.0: last = max(last, t + .6)
    newe = last + tail
    near = wslice(words, newe - 4.0, newe + 3.0)
    cand = [w["end"] for w in near if newe - .2 <= w["end"] <= newe + 2.2 and w["w"].rstrip()[-1:] in ".!?。！？"]
    if cand: newe = min(cand) + .15
    else:                                                          # otherwise the next small pause
        for w1, w2 in zip(near, near[1:]):
            if newe <= w1["end"] <= newe + 2.0 and w2["start"] - w1["end"] >= .35: newe = w1["end"] + .15; break
    if e - newe < 3.0 or newe - s < lo: return e
    return float(newe)


# ================================================================ variety
def _sig(words, s, e):
    try:
        import vcpost
        stop = vcpost.STOP
    except Exception: stop = set()
    c = {}
    for t, _, _ in toks(words, s, e):
        if len(t) >= 4 and t not in stop and not t.isdigit(): c[t] = c.get(t, 0) + 1
    return c


def similar_moments(words, s1, e1, s2, e2, need=.45):
    """True when two moments talk about the same thing (a joke or a topic that comes back): they share almost the same rare words."""
    a, b = _sig(words, s1, e1), _sig(words, s2, e2)
    if len(a) < 5 or len(b) < 5: return False
    inter = sum(min(a[k], b[k]) for k in a if k in b); small = min(sum(a.values()), sum(b.values()))
    return small > 0 and inter / small >= need


# ================================================================ smart length
def smart_range(kind, lo_user, hi_user, mix=.75):
    """The length range for a kind of clip. The user's own range is respected as the outer limits (the clip is never shorter than 10 s or longer than 90 s)."""
    ti = TYPE_INFO.get(kind)
    if not ti: return lo_user, hi_user
    lo, hi = float(ti["lo"]), float(ti["hi"])
    return max(10.0, min(lo, hi - 4)), min(90.0, max(hi, lo + 4))


# ================================================================ reaction words (text pops on detected moments)
REACT_WORDS = {"laugh": ("LOL", "HAHA", "DYING"), "scream": ("EEEEK!", "AHHH!", "NOOO!"), "fail": ("OOF", "RIP", "NOT AGAIN"), "win": ("LET'S GO!", "CLUTCH!", "EZ"),
               "scare": ("NOPE", "WHAT WAS THAT", "NOPE NOPE"), "cute": ("AWW", "UWU", "SO CUTE"), "rage": ("NOT AGAIN", "BRUH", "SERIOUSLY?"), "setup": ("WAIT FOR IT", "HOLD ON", "WAIT"),
               "hype": ("NO WAY!", "WOW", "INSANE")}


def reaction_events(words, a, b, marks, curves, max_n=4, min_gap=3.0):
    """[(time inside the clip, key)] of moments worth a big reaction word, strongest first, spread out."""
    import numpy as np
    ia, ib = int(a), max(int(a) + 1, int(math.ceil(b))); cand = []
    def add(arr, key, thr, w=1.0):
        if arr is None or not len(arr[ia:ib]): return
        seg = np.asarray(arr[ia:ib])
        for i in np.where(seg >= thr)[0]:
            if (i == 0 or seg[i] >= seg[i - 1]) and (i == len(seg) - 1 or seg[i] >= seg[i + 1]): cand.append((float(seg[i]) * w, ia + float(i), key))
    if curves is not None:
        add(curves.get("laugh"), "laugh", .6, 1.0); add(curves.get("scream"), "scream", .4, 1.3)
    if marks is not None:
        for k, thr, w in (("fail", 1, .9), ("win", 1, .9), ("scare", 1, .8), ("cute", 1, .7), ("rage", 1, .8), ("hype", 1, .6)): add(marks.get(k), k, thr, w)
    cand.sort(reverse=True); out = []
    for sc_, t, k in cand:
        if len(out) >= max_n: break
        if t - a < 1.2 or b - t < 1.0: continue
        if all(abs(t - x) >= min_gap for x, _ in out): out.append((t, k))
    return sorted((t - a, k) for t, k in out)


# ================================================================ hooks and titles by kind of clip
HOOKS = {
    "gameplay": ["WAIT FOR IT", "THIS WAS NOT PLANNED", "{g} IS TESTING ME", "I SHOULD NOT HAVE DONE THAT", "ONE LAST TRY", "NO WAY THIS WORKED"],
    "reaction": ["I DID NOT EXPECT THIS", "MY REACTION SAYS IT ALL", "WAIT… WHAT?!", "NOBODY WAS READY", "THE SOUND I MADE"],
    "talking": ["HOT TAKE", "I NEED TO SAY THIS", "AM I WRONG?", "THIS IS WHY CHAT LOVES ME", "UNPOPULAR OPINION"],
    "story": ["STORYTIME", "YOU WON'T BELIEVE THIS", "THIS ACTUALLY HAPPENED", "I STILL THINK ABOUT THIS", "IT GETS WORSE"],
    "singing": ["SHE CAN SING?!", "THE HIGH NOTE", "KARAOKE NIGHT", "LISTEN TO THIS PART", "WAIT FOR THE CHORUS"],
}


def hook_for(kind, k=0, game=""):
    lst = HOOKS.get(kind) or HOOKS["talking"]
    h = lst[k % len(lst)]
    return h.replace("{g}", (game or "THIS GAME").upper())


TITLE_TEMPLATES = {
    "gameplay": ["{G} but it goes terribly wrong 💀", "The {g} moment I can't live down", "Nobody told me {g} could do this 😭", "I thought I had this… 💀", "Wait for it… {g} 😭"],
    "reaction": ["My reaction says it all 😱", "I did NOT see that coming 😳", "The sound I made 😭", "Chat was NOT ready for this", "I can't believe I reacted like that"],
    "talking": ["Hot take: {q}", "This is why chat loves me", "I said what I said", "Am I wrong though? 👀", "Unpopular opinion from the stream 👀"],
    "story": ["Storytime: it gets worse 👀", "This actually happened to me 😭", "I still think about this", "You won't believe how this ended 👀", "I should NOT have told this story"],
    "singing": ["She hit the note 🎤", "Karaoke night went well 🎤", "Wait for the chorus 🎤", "Singing on stream hits different 🎶", "This part gave me chills 🎶"],
}
EXTRA_TAGS = {
    "gameplay": ["GamingClips", "GamingFails", "Highlights"], "reaction": ["Reaction", "Funny", "Unexpected"], "talking": ["JustChatting", "StreamMoments"],
    "story": ["Storytime", "Storytelling"], "singing": ["Singing", "Karaoke", "VTuberSinging", "Cover"],
}


# ================================================================ chat logs (optional: a chat file next to the VOD makes busy moments score higher)
CHAT_HYPE = set("kekw lul lulw omegalul lmao lmfao lol haha pog poggers pogchamp clip clipit wtf omg monkas monkaw ahhh insane gg ez w based sadge widepeepohappy 😂 🤣 😭 💀 🔥 😱".split())


def parse_chat(text, ext=""):
    """Chat log text -> [(seconds, message)]. Reads TwitchDownloader JSON, yt-dlp live chat (json lines) and plain "[1:02:03] name: message" lines."""
    msgs = []
    s = text.lstrip("﻿").strip()
    if not s: return msgs
    if s[0] in "{[":
        try:
            d = json.loads(s)
            cm = d.get("comments") if isinstance(d, dict) else d
            if isinstance(cm, list):
                for c in cm:
                    if not isinstance(c, dict): continue
                    t = c.get("content_offset_seconds", c.get("offset", c.get("time")))
                    m = c.get("message"); body = m.get("body") if isinstance(m, dict) else m if isinstance(m, str) else c.get("body", "")
                    if t is not None:
                        try: msgs.append((float(t), str(body or "")))
                        except (TypeError, ValueError): pass
                if msgs: return sorted(msgs)
        except ValueError: pass
    for line in s.splitlines():
        line = line.strip()
        if not line: continue
        if line[0] == "{":
            try: d = json.loads(line)
            except ValueError: continue
            rc = d.get("replayChatItemAction") or {}
            try: off = float(rc.get("videoOffsetTimeMsec", "nan")) / 1000.0
            except (TypeError, ValueError): continue
            if off != off: continue
            for act in rc.get("actions", []):
                it = ((act.get("addChatItemAction") or {}).get("item") or {}).get("liveChatTextMessageRenderer")
                if it: msgs.append((off, "".join(r.get("text", r.get("emoji", {}).get("emojiId", "")) if isinstance(r, dict) else "" for r in (it.get("message") or {}).get("runs", []))))
            continue
        m = re.match(r"^\[?\s*(?:(\d+):)?(\d{1,2}):(\d{2})(?:\.\d+)?\s*\]?[\s,;:\-]*(.*)$", line)
        if m:
            h, mi, se, rest = m.groups(); msgs.append((int(h or 0) * 3600 + int(mi) * 60 + int(se), rest))
    return sorted(msgs)


def chat_curve(msgs, n):
    """0..1 per second: how busy the chat was (messages a second, and laughing / hype messages count double), smoothed, compared with the rest of the stream."""
    import numpy as np
    v = np.zeros(n, np.float32)
    for t, m in msgs:
        i = int(t)
        if 0 <= i < n:
            low = set(re.findall(r"[\w😂🤣😭💀🔥😱]+", m.lower()))
            v[i] += 2.0 if low & CHAT_HYPE else 1.0
    if not v.any(): return v
    k = np.ones(5, np.float32) / 5; v = np.convolve(v, k, "same")
    ref = max(float(np.percentile(v, 98)), .5 * float(v.max())) + 1e-6
    base = float(np.median(v))
    return np.clip((v - base) / (ref - base + 1e-6), 0, 1).astype(np.float32)


def find_chat_file(video):
    """A chat log that sits next to the video: same name + .chat.json / _chat.json / .live_chat.json / .chat.txt / .chat.csv, or the same name + .json that looks like chat."""
    base, _ = os.path.splitext(video)
    for suf in (".chat.json", "_chat.json", ".live_chat.json", ".chat.txt", "_chat.txt", ".chat.csv", ".live_chat.jsonl", ".chat.jsonl", ".chat.log"):
        if os.path.isfile(base + suf): return base + suf
    p = base + ".json"
    if os.path.isfile(p):
        try:
            with open(p, encoding="utf-8", errors="replace") as f: head = f.read(4000)
            if '"comments"' in head or "content_offset_seconds" in head: return p
        except OSError: pass
    return ""


def load_chat(path, n):
    """-> (curve of n seconds, number of messages) or (None, 0) when the file cannot be used."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f: txt = f.read(60_000_000)
    except OSError: return None, 0
    msgs = parse_chat(txt, os.path.splitext(path)[1])
    if len(msgs) < 20: return None, len(msgs)
    return chat_curve(msgs, n), len(msgs)


# ================================================================ my taste (learns from the clips the user keeps and deletes)
def taste(entries):
    """entries = ledger rows (dict with kind, dur, fav, posted, deleted). -> dict(n, len_med, kinds{kind: weight 0.9..1.15}) or None when there is too little to learn from."""
    keep = [e for e in entries if (e.get("fav") or e.get("posted")) and not e.get("deleted") and e.get("dur")]
    drop = [e for e in entries if e.get("deleted") and e.get("dur")]
    if len(keep) < 3: return None
    lens = sorted(float(e["dur"]) for e in keep)
    med = lens[len(lens) // 2]
    kinds = {}
    for k in TYPES:
        a = sum(1 for e in keep if e.get("kind") == k); b = sum(1 for e in drop if e.get("kind") == k)
        if a + b >= 2: kinds[k] = max(.9, min(1.15, 1.0 + .25 * (a - b) / (a + b + 2.0)))
    return dict(n=len(keep), dropped=len(drop), len_med=med, kinds=kinds)


def taste_text(t):
    if not t: return "I need at least 3 clips you starred or marked as posted before I can learn what you like."
    best = sorted(t["kinds"].items(), key=lambda kv: -kv[1])
    s = f"From {t['n']} clips you kept: your favourite length is about {t['len_med']:.0f} seconds."
    if best and best[0][1] > 1.03: s += f" You keep the most {type_label(best[0][0]).lower()} clips."
    return s


def taste_range(t, lo, hi):
    """Pull the length range toward the length the user keeps (never outside 10-90 s)."""
    if not t: return lo, hi
    m = float(t["len_med"]); lo2 = max(10.0, m * .78); hi2 = min(90.0, max(lo2 + 6, m * 1.25))
    return lo2, hi2
