"""VTuber Clipper 2.3 - more clues for finding the right moment, and cleaner clip edges.
Like vcsmart.py this is rules of thumb, not a trained model: word lists, a few numbers about the sound and plain arithmetic. Everything works on the transcript
(list of {w, start, end}) and per-second arrays, so every function can be tested without a video.

  1 !clip commands in the chat log     2 milestones and firsts         3 chat-reading moments       4 bilingual switch
  5 rapid-fire excitement              6 panic repeats                 7 build-up -> peak           8 open on action
  9 clean ending                      10 spread over the stream       11 skip BRB / intermission / goodbye parts"""
import math, os, re

import numpy as np

import vcsmart

clean = vcsmart.clean

# ---------------------------------------------------------------- how much each clue adds to a second's score (compare vcsmart / streamclip.SMART_W)
CLUE_W = dict(cmd=2.5, milestone=1.0, chat_talk=.5, bilingual=.8, fast=.9, repeat=1.0, buildup=1.2, dead=-3.0)
# option key that switches each clue on or off
CLUE_OPT = dict(cmd="chat_cmds", milestone="clue_milestone", chat_talk="clue_chat", bilingual="clue_bilingual", fast="clue_fast", repeat="clue_repeat", buildup="clue_buildup", dead="skip_dead")


# ================================================================ 1  !clip commands in the chat log
_CMD_RX = re.compile(r"^\s*!\s*(?:clip|clipit|clipthat|marker|mark|highlight|hl|moment|keepthis)\b", re.I)
_NAT_RX = re.compile(r"^\W*(?:please\s+)?(?:someone\s+)?clip\s+(?:that|it|this)\W*$|^\W*clip\W*$|^\W*clip\s+clip\W*$", re.I)


_NAME_RX = re.compile(r"^\s*[\w.\-\[\]<>@]{1,30}:\s+")          # text logs write "viewer_name: the message"


def is_clip_command(msg):
    """True for "!clip", "!marker", "!highlight" ... and for the short plain ones viewers type ("clip that", "clip it!", "clip!").
    A leading "name:" (plain-text chat logs) is ignored."""
    m = str(msg or "")
    for t in (m, _NAME_RX.sub("", m, count=1)):
        if bool(_CMD_RX.match(t)) or (len(t) <= 24 and bool(_NAT_RX.match(t))): return True
    return False


def chat_command_times(msgs):
    """Seconds (of the video) at which somebody in chat asked for a clip."""
    return sorted(float(t) for t, m in msgs if is_clip_command(m))


def command_moments(msgs, merge=20.0, delay=10.0):
    """[(estimated second of the moment, number of requests)]. Viewers type the command a few seconds AFTER the moment, so the moment is `delay` seconds before the
    middle of a burst of commands (commands less than `merge` seconds apart belong to the same moment)."""
    ts = chat_command_times(msgs); out = []
    group = []
    for t in ts:
        if group and t - group[-1] > merge:
            out.append((max(0.0, float(np.median(group)) - delay), len(group))); group = []
        group.append(t)
    if group: out.append((max(0.0, float(np.median(group)) - delay), len(group)))
    return out


def cmd_curve(msgs, n):
    """0..1 per second: 'viewers asked for a clip here'. One request is a half-strength hint, three or more is full strength."""
    v = np.zeros(max(0, int(n)), np.float32)
    for t, c in command_moments(msgs):
        strength = min(1.0, .5 + .25 * (c - 1))
        for k in range(-10, 11):                               # a triangle around the moment
            i = int(round(t)) + k
            if 0 <= i < len(v): v[i] = max(v[i], strength * (1 - abs(k) / 11.0))
    return v


_CHAT_CACHE = {}


def chat_messages(path):
    """The messages [(seconds, text)] of a chat log (read once per file version)."""
    try:
        st = os.stat(path); key = (os.path.abspath(path), st.st_mtime_ns, st.st_size)
    except (OSError, TypeError, ValueError): return []
    if key in _CHAT_CACHE: return _CHAT_CACHE[key]
    try:
        with open(path, encoding="utf-8", errors="replace") as f: txt = f.read(60_000_000)
        msgs = vcsmart.parse_chat(txt, os.path.splitext(path)[1])
    except Exception: msgs = []
    if len(_CHAT_CACHE) > 4: _CHAT_CACHE.clear()
    _CHAT_CACHE[key] = msgs
    return msgs


# ================================================================ 2  milestones and firsts      3  she reads or answers chat
MILESTONE_PH = [("first", "time"), ("first", "ever"), ("new", "record"), ("personal", "best"), ("level", "up"), ("leveled", "up"), ("hit", "the", "goal"), ("hit", "my", "goal"),
                ("we", "did", "it"), ("i", "did", "it"), ("finally", "did", "it"), ("finally", "beat"), ("never", "done", "this"), ("never", "done", "that"), ("so", "proud"),
                ("thank", "you", "so", "much", "for", "everything"), ("i'm", "crying"), ("1", "year"), ("one", "year")]
MILESTONE_W = set("milestone milestones anniversary birthday achievement achievements platinum unlocked subathon congratulations congrats debut".split())
CHAT_TALK_PH = [("chat", "says"), ("chat", "said"), ("chat", "is", "saying"), ("chat", "are", "saying"), ("chat", "asked"), ("chat", "wants"), ("chat", "thinks"), ("someone", "said"),
                ("someone", "in", "chat"), ("someone", "asked"), ("reading", "chat"), ("read", "chat"), ("let", "me", "read"), ("in", "the", "chat"), ("in", "chat"), ("you", "guys", "in", "chat")]
_FOLLOW_W = {"followers", "subscribers", "subs", "follower", "subscriber", "members"}


def _bump(arr, t, w):
    i = int(t)
    if 0 <= i < len(arr): arr[i] += w


def milestone_marks(words, n):
    """Per-second count of milestone / first-time talk ("first time ever", "new record", "level up", "we did it", "1000 followers")."""
    v = np.zeros(n, np.float32); tk = vcsmart.toks(words)
    for t in vcsmart.phrase_times(tk, MILESTONE_PH): _bump(v, t, 1.0)
    for t, s, e in tk:
        if t in MILESTONE_W: _bump(v, s, .6)
    for i, (t, s, e) in enumerate(tk):                          # "five thousand followers", "1000 subs"
        if t in _FOLLOW_W:
            near = [x[0] for x in tk[max(0, i - 3):i]]
            if any(x.isdigit() and len(x) >= 3 for x in near) or any(x in ("thousand", "hundred", "million") for x in near): _bump(v, s, 1.0)
    return v


def chat_talk_marks(words, n):
    """Per-second count of 'she is reading / answering chat' phrases. Only the phrases count; the bare word 'chat' does not."""
    v = np.zeros(n, np.float32); tk = vcsmart.toks(words)
    for t in vcsmart.phrase_times(tk, CHAT_TALK_PH): _bump(v, t, 1.0)
    return v


# ================================================================ 4  bilingual switch
def script_of(ch):
    """A letter's writing system: 'latin', 'cjk' (kana, kanji, hanzi), 'ko', 'ru', 'th' or '' (not a letter)."""
    o = ord(ch)
    if 0x3040 <= o <= 0x30FF or 0x31F0 <= o <= 0x31FF or 0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF: return "cjk"
    if 0xAC00 <= o <= 0xD7AF or 0x1100 <= o <= 0x11FF: return "ko"
    if 0x0400 <= o <= 0x04FF: return "ru"
    if 0x0E00 <= o <= 0x0E7F: return "th"
    if ch.isalpha() and o < 0x250: return "latin"
    return ""


def token_scripts(tok):
    """The writing systems in a word, in order, without repeats ('ありがとうgg' -> ['cjk', 'latin'])."""
    out = []
    for ch in tok:
        s = script_of(ch)
        if s and (not out or out[-1] != s): out.append(s)
    return out


def bilingual_marks(words, n, span=6.0, min_each=2, min_switch=2):
    """Per-second 1.0 where two writing systems alternate inside `span` seconds (an English sentence with a Japanese word in it and back).
    Needs the transcript to contain both scripts - speech-to-text set to a single language writes only that one."""
    v = np.zeros(n, np.float32)
    seq = []                                                     # (time, script) in order
    for t, s, e in vcsmart.toks(words):
        for sc_ in token_scripts(t): seq.append((s, sc_))
    j = 0
    for i in range(len(seq)):
        while seq[i][0] - seq[j][0] > span: j += 1
        win = seq[j:i + 1]
        kinds = {}
        for _, sc_ in win: kinds[sc_] = kinds.get(sc_, 0) + 1
        if len(kinds) >= 2 and sum(1 for c in kinds.values() if c >= min_each) >= 2:
            sw = sum(1 for a, b in zip(win, win[1:]) if a[1] != b[1])
            if sw >= min_switch: _bump(v, seq[i][0], 1.0)
    return v


# ================================================================ 5  rapid-fire excitement   6  panic repeats
def fast_speech(words, n, win=4.0):
    """0..1 per second: how much faster than her usual pace she is talking (needs at least 3.5 words a second to count)."""
    st = np.zeros(n, np.float32)
    for w in words:
        i = int(w["start"])
        if 0 <= i < n: st[i] += 1
    k = int(win)
    wps = np.convolve(st, np.ones(k, np.float32) / win, "same")
    talk = wps[wps > .3]
    base = float(np.median(talk)) if len(talk) else 1.0
    base = max(1.0, base)
    v = np.clip((wps - 1.5 * base) / (1.0 * base), 0, 1)
    v[wps < 3.5] = 0
    return v.astype(np.float32)


_REPEAT_SKIP = {"the", "and", "a", "to", "of", "um", "uh", "like", "so", "i", "you", "it", "is", "in", "that", "this",
                "ha", "hah", "he", "hee", "heh", "hi", "ho", "hoo", "ah", "eh", "mm", "hm", "hmm"}          # filler words and the single syllables of a laugh


def repeat_runs(words, min_run=3, within=4.0):
    """[(start second, word, how many times)] where the same word is said at least `min_run` times in a row ("no no no no", "wait wait wait")."""
    tk = vcsmart.toks(words); out = []; i = 0
    while i < len(tk):
        j = i
        while j + 1 < len(tk) and tk[j + 1][0] == tk[i][0] and tk[j + 1][1] - tk[i][1] <= within: j += 1
        c = j - i + 1
        t = tk[i][0]
        if c >= min_run and len(t) >= 2 and t not in _REPEAT_SKIP and not vcsmart.is_laugh(t) and not t.isdigit(): out.append((tk[i][1], t, c))
        i = j + 1
    return out


def repeat_marks(words, n):
    v = np.zeros(n, np.float32)
    for t, w, c in repeat_runs(words): _bump(v, t, min(1.0, .4 + .2 * (c - 2)))
    return v


# ================================================================ 7  build-up -> peak
def buildup_curve(z, span=10):
    """0..1 per second, at the top of a climb: the loudness has been rising for `span` seconds and this second is a peak. `z` = per-second loudness (any scale)."""
    z = np.asarray(z, np.float64); n = len(z)
    if n < span + 3: return np.zeros(n, np.float32)
    x = np.arange(span) - (span - 1) / 2.0
    slope = np.convolve(z, x[::-1], "full")[:n] / float((x ** 2).sum())
    slope[:span - 1] = 0
    slope = np.concatenate([np.zeros(2), slope[:-2]])                 # the climb up to two seconds BEFORE the top, so a sudden single spike is not a build-up
    pk = np.zeros(n, bool)
    for t in range(2, n - 2):
        pk[t] = z[t] >= z[t - 2:t + 3].max() and z[t] > .6
    v = np.clip(slope / .30, 0, 1) * pk
    return np.maximum(v, np.maximum(np.roll(v, 1), np.roll(v, -1))).astype(np.float32)          # spread one second to each side, so the windows around the peak notice it


# ================================================================ 11  BRB / intermission / goodbye parts
DEAD_PH = [("be", "right", "back"), ("right", "back"), ("brb",), ("starting", "soon"), ("stream", "starting"), ("technical", "difficulties"), ("intermission",),
           ("thanks", "for", "watching"), ("thank", "you", "for", "watching"), ("see", "you", "next", "time"), ("see", "you", "tomorrow"), ("see", "you", "guys", "next"),
           ("good", "night", "everyone"), ("goodnight", "everyone"), ("goodnight",), ("that's", "the", "stream"), ("that's", "it", "for", "today"), ("that's", "all", "for", "today"),
           ("end", "of", "stream"), ("end", "the", "stream"), ("ending", "the", "stream"), ("signing", "off"), ("let's", "raid"), ("raiding",), ("grab", "some", "water"), ("bathroom",)]


def dead_zones(words, quiet, n, quiet_min=25):
    """[(from, to)] seconds to leave out: around a "be right back" / "starting soon" / "thanks for watching" phrase, and any stretch of at least `quiet_min` seconds
    with no speech and no sound (a muted BRB screen). `quiet` = per-second flags (True = quiet)."""
    zones = []
    tk = vcsmart.toks(words)
    for t in vcsmart.phrase_times(tk, DEAD_PH): zones.append((max(0.0, t - 4.0), min(float(n), t + 20.0)))
    if quiet is not None and len(quiet):
        q = np.asarray(quiet, bool)[:n]; cov = np.zeros(len(q), bool)
        for w in words:
            a, b = int(w["start"]), int(math.ceil(w["end"]))
            cov[max(0, a):max(0, min(len(q), b + 1))] = True
        dead = q & ~cov; i = 0
        while i < len(dead):
            if dead[i]:
                j = i
                while j + 1 < len(dead) and dead[j + 1]: j += 1
                if j - i + 1 >= quiet_min: zones.append((float(i), float(j + 1)))
                i = j + 1
            else: i += 1
    zones.sort(); merged = []
    for a, b in zones:
        if merged and a <= merged[-1][1] + 1: merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else: merged.append((a, b))
    return merged


def zones_overlap(a, b, zones):
    """How much of [a, b) lies inside the zones, 0..1."""
    if b <= a: return 0.0
    return min(1.0, sum(max(0.0, min(b, y) - max(a, x)) for x, y in zones) / (b - a))


def zone_curve(zones, n):
    v = np.zeros(n, np.float32)
    for a, b in zones: v[max(0, int(a)):max(0, min(n, int(math.ceil(b))))] = 1.0
    return v


# ================================================================ putting it together
def compute(words, rmsz, n, o, msgs=None, quiet=None):
    """-> dict(parts={name: array}, boost=array (the extra score per second), zones=[...], cmds=[(second, count)]). A clue that is switched off adds nothing."""
    o = o or {}
    on = lambda k: bool(o.get(CLUE_OPT[k], True))
    parts = {}
    if on("cmd") and msgs: parts["cmd"] = cmd_curve(msgs, n)
    if on("milestone"): parts["milestone"] = np.minimum(1.5, milestone_marks(words, n))
    if on("chat_talk"): parts["chat_talk"] = np.minimum(1.5, chat_talk_marks(words, n))
    if on("bilingual"): parts["bilingual"] = bilingual_marks(words, n)
    if on("fast"): parts["fast"] = fast_speech(words, n)
    if on("repeat"): parts["repeat"] = repeat_marks(words, n)
    if on("buildup") and rmsz is not None and len(rmsz) >= n: parts["buildup"] = buildup_curve(np.asarray(rmsz)[:n])
    zones = dead_zones(words, quiet, n) if on("dead") else []
    boost = np.zeros(n, np.float32)
    for k, arr in parts.items(): boost += CLUE_W[k] * arr[:n]
    if zones: boost += CLUE_W["dead"] * zone_curve(zones, n)
    return dict(parts=parts, boost=boost, zones=zones, cmds=command_moments(msgs) if (msgs and on("cmd")) else [])


def _t(sec):
    sec = int(max(0, sec)); return f"{sec // 60}:{sec % 60:02d}"


def reasons(parts, a, b):
    """Plain sentences for the title-ideas file, for the clues that fired inside [a, b)."""
    out = []
    if not parts: return out
    ia, ib = int(a), max(int(a) + 1, int(math.ceil(b)))

    def hit(k, thr):
        v = parts.get(k)
        if v is None or not len(v[ia:ib]): return None
        m = float(np.max(v[ia:ib]))
        return ia + int(np.argmax(v[ia:ib])) if m >= thr else None
    t = hit("cmd", .3)
    if t is not None: out.append("Viewers typed !clip around here")
    t = hit("milestone", .5)
    if t is not None: out.append("A milestone or a first")
    t = hit("repeat", .5)
    if t is not None: out.append(f"Panic repeats around {_t(t - a)}")
    t = hit("fast", .5)
    if t is not None: out.append("Rapid-fire excited talking")
    t = hit("bilingual", .5)
    if t is not None: out.append("Switches between two languages")
    t = hit("buildup", .5)
    if t is not None: out.append(f"Builds up to a peak around {_t(t - a)}")
    t = hit("chat_talk", .5)
    if t is not None: out.append("Reads or answers chat")
    return out


# ================================================================ 8  open on action   9  clean ending
def active_span(words, quiet, a, b):
    """(first, last) second inside [a, b) where somebody speaks or there is real sound; (None, None) when it is dead air all the way."""
    marks = []
    for w in words:
        if w["end"] > a and w["start"] < b: marks += [max(a, float(w["start"])), min(b, float(w["end"]))]
    if quiet is not None and len(quiet):
        q = np.asarray(quiet, bool)
        for i in range(max(0, int(a)), min(len(q), int(math.ceil(b)))):
            if not q[i]: marks += [max(a, float(i)), min(b, float(i + 1))]
    if not marks: return None, None
    return min(marks), max(marks)


def trim_edges(segs, words, quiet, lead=True, tail=True, min_dead=1.0, keep_lead=.35, keep_tail=.5, min_len=8.0):
    """Cut dead air off the start and the end of a clip (given as [(from, to)] pieces). The clip never gets shorter than `min_len`, and a clip without any speech or
    sound is left alone. Returns (new pieces, seconds cut from the start, seconds cut from the end)."""
    if not segs: return segs, 0.0, 0.0
    segs = [(float(a), float(b)) for a, b in segs]
    first, last = active_span(words, quiet, segs[0][0], segs[-1][1])
    if first is None: return segs, 0.0, 0.0
    cut_a = cut_b = 0.0
    total = sum(b - a for a, b in segs)
    if lead and first - segs[0][0] >= min_dead:
        ns = first - keep_lead
        if ns > segs[0][0] + .05 and total - (ns - segs[0][0]) >= min_len:
            cut_a = ns - segs[0][0]; segs[0] = (ns, segs[0][1])
    total = sum(b - a for a, b in segs)
    if tail and segs[-1][1] - last >= min_dead:
        ne = last + keep_tail
        if ne < segs[-1][1] - .05 and total - (segs[-1][1] - ne) >= min_len and ne > segs[-1][0] + .3:
            cut_b = segs[-1][1] - ne; segs[-1] = (segs[-1][0], ne)
    return segs, cut_a, cut_b


# ================================================================ 10  spread the clips over the stream
def spread_factor(start, end, chosen, zone=180.0):
    """A number between 0.55 and 1 to multiply a candidate's score by: the closer it is to a clip that is already chosen, the lower. `chosen` = [(start, end)]."""
    if not chosen: return 1.0
    mid = (start + end) / 2.0
    d = min(abs(mid - (s + e) / 2.0) for s, e in chosen)
    return .55 + .45 * min(1.0, d / max(1.0, zone))


def spread_zone(total_seconds, n_clips, lo=60.0, hi=600.0):
    """How far apart (seconds) clips should ideally be: the stream divided by the number of clips, but at least a minute and at most ten."""
    return float(max(lo, min(hi, total_seconds / max(1, n_clips) * .6)))
