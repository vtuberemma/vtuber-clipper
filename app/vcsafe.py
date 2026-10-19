"""VTuber Clipper 2.3 - privacy and safety checks (features 27-32 and 39).
 27 flash safety check          28 clip check before you post        29 privacy guard (patterns in the speech)    30 my private words
 31 privacy scan report         32 private words kept out of file names, titles and hashtags       39 disk-space guard

The privacy guard finds PATTERNS in the speech-to-text (e-mail addresses, phone numbers, street addresses, links, "my real name is ...") and the words the creator listed.
It cannot hear what the transcript got wrong, so it is a safety net, not a guarantee. Everything works on lists of words / plain strings and is easy to test."""
import math, os, re, shutil, subprocess

import numpy as np

import vcsmart, vc23, vcmore, vcmedia
_kw = vcmore._kw

clean = vcsmart.clean

# ================================================================ 29  privacy guard
NUM_WORDS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "oh": 0}
JOIN_WORDS = {"dash", "hyphen", "plus", "-", "and"}
TLDS = {"com", "net", "org", "io", "gg", "tv", "me", "co", "jp", "uk", "de", "fr", "app", "dev", "xyz", "edu", "info", "ca", "au"}
MAIL_HOSTS = {"gmail", "hotmail", "yahoo", "outlook", "icloud", "protonmail", "proton", "live", "aol", "msn", "yahoo.co.jp", "docomo", "softbank"}
STREET_SUFFIX = {"street", "st", "avenue", "ave", "road", "rd", "drive", "dr", "boulevard", "blvd", "lane", "ln", "court", "ct", "place", "pl", "way", "terrace", "circle", "highway", "hwy"}
TRIGGERS = [  # (phrase, kind, how many words after it to cover)
    (("my", "real", "name"), "name", 4), (("real", "name", "is"), "name", 3), (("irl", "name", "is"), "name", 3), (("my", "legal", "name"), "name", 4), (("my", "birth", "name"), "name", 4),
    (("my", "irl", "name"), "name", 4), (("my", "government", "name"), "name", 4),
    (("my", "address", "is"), "address", 10), (("my", "home", "address"), "address", 10), (("i", "live", "at"), "address", 8), (("i", "live", "on"), "address", 8), (("my", "street", "is"), "address", 6),
    (("my", "zip", "code"), "address", 4), (("my", "postal", "code"), "address", 4),
    (("my", "phone", "number"), "phone", 10), (("my", "number", "is"), "phone", 10), (("call", "me", "at"), "phone", 10), (("text", "me", "at"), "phone", 10),
    (("my", "email", "is"), "email", 8), (("my", "e-mail", "is"), "email", 8), (("email", "me", "at"), "email", 8), (("my", "email", "address"), "email", 8)]
KIND_LABEL = {"email": "an e-mail address", "phone": "a phone number", "address": "a street address", "link": "a link", "name": "a real-name slip", "private": "one of your private words"}
_EMAIL_RX = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")
_URL_RX = re.compile(r"(?:https?://|www\.)\S+|\b[\w\-]+\.(?:com|net|org|io|gg|tv|me|co|jp|app|dev|xyz)(?:/\S*)?\b", re.I)


SURE_HOSTS = {"gmail", "hotmail", "yahoo", "outlook", "icloud", "protonmail", "aol", "docomo", "softbank"}
NOT_DOMAIN = {"this", "that", "the", "a", "an", "my", "your", "our", "their", "some", "any", "one", "it", "here", "there", "these", "those"}
FILLER = {"is", "was", "be", "are", "gonna", "will"}
STOP_NAME = {"a", "an", "the", "not", "none", "secret", "private", "classified", "nothing", "something", "going", "just", "kinda", "too", "also", "and", "but", "so", "always", "never"}
NAME_END = {"and", "but", "so", "because", "if", "then", "or", "the", "i", "is", "was", "which", "who", "that", "you", "we", "my", "no", "not"}


def _user_start(tk, j):
    """First token of the user name before an 'at': 'mia dot v' -> the 'mia' (a name can be joined with dot / underscore / dash)."""
    while j - 2 >= 0 and tk[j - 1][0] in ("dot", "underscore", "dash", "hyphen"): j -= 2
    return max(0, j)


def _digits_in(tok):
    return len(re.sub(r"\D", "", tok))


def _toks(words):
    """[(cleaned word, raw word)] from a transcript (list of dicts) or from plain strings."""
    out = []
    for w in words:
        raw = str(w["w"] if isinstance(w, dict) else w)
        out.append((clean(raw), raw))
    return out


def privacy_hits(words):
    """[(first index, last index (inclusive), kind)] of personal-looking patterns in a list of words (dicts with 'w' or plain strings). kinds: email, phone, address, link, name."""
    tk = _toks(words); n = len(tk); hits = []
    # e-mail spelled with an @ or "dot com"
    for i, (c, raw) in enumerate(tk):
        if _EMAIL_RX.search(raw) or ("@" in raw and re.search(r"@\w", raw)): hits.append((i, i, "email"))
        elif _URL_RX.search(raw) and not _EMAIL_RX.search(raw): hits.append((i, i, "link"))
    for i, (c, raw) in enumerate(tk):                          # "john at gmail dot com", "mia dot v at example dot net"
        if c == "at" and i >= 1 and i + 1 < n and tk[i + 1][0] in SURE_HOSTS:          # "mia at gmail" (the dot com was not said)
            hits.append((_user_start(tk, i - 1), i + 1, "email"))
        if c == "dot" and i + 1 < n and tk[i + 1][0] in TLDS:
            at = i - 2 if (i >= 2 and tk[i - 2][0] == "at" and tk[i - 1][0] not in NOT_DOMAIN) else None
            end = i + 1
            while end + 2 < n and tk[end + 1][0] == "dot" and tk[end + 2][0] in TLDS: end += 2                  # "gmail dot co dot uk"
            if at is not None and at >= 1: hits.append((_user_start(tk, at - 1), end, "email"))
            elif i > 0 and tk[i - 1][0] in MAIL_HOSTS: hits.append((i - 1, end, "email"))
            elif i >= 1 and tk[i - 1][0] == "www" or (i >= 2 and tk[i - 2][0] == "www"): hits.append((max(0, i - 3), end, "link"))
            elif i >= 1 and re.fullmatch(r"[a-z0-9\-]{3,}", tk[i - 1][0] or "") and tk[i - 1][0] not in NOT_DOMAIN and tk[i + 1][0] in ("com", "gg", "tv", "io", "me"): hits.append((i - 1, end, "link"))
    # phone numbers: a run of at least 7 spoken or written digits
    i = 0
    while i < n:
        c = tk[i][0]
        if c.isdigit() or c in NUM_WORDS or _digits_in(tk[i][1]) >= 7 and re.fullmatch(r"[\d\s()+\-.]+", tk[i][1].strip(" ,.!?")):
            j = i; cnt = 0; last_digit = i
            while j < n:
                cj, rj = tk[j]
                if cj.isdigit() or re.fullmatch(r"[\d()+\-.]+", rj.strip(" ,!?")) and _digits_in(rj):
                    cnt += max(1, _digits_in(rj)); last_digit = j
                elif cj in NUM_WORDS: cnt += 1; last_digit = j
                elif cj in JOIN_WORDS and j + 1 < n and (tk[j + 1][0].isdigit() or tk[j + 1][0] in NUM_WORDS): pass
                else: break
                j += 1
            if cnt >= 7 and len({d for q in range(i, last_digit + 1) for d in (re.sub(r"\D", "", tk[q][1]) or str(NUM_WORDS.get(tk[q][0], "")))}) >= 3: hits.append((i, last_digit, "phone"))
            i = max(j, i + 1)
        else: i += 1
    # a street address: 123 Main Street (the street and its name are written with capital letters in the transcript)
    for i, (c, raw) in enumerate(tk):
        if c.isdigit() and 1 <= len(c) <= 5:
            for k in range(1, 5):
                if i + k >= n: break
                cs, rs = tk[i + k]
                if cs in STREET_SUFFIX and rs[:1].isupper() and any(tk[m][1][:1].isupper() for m in range(i + 1, i + k)) and all(tk[m][1][:1].isalpha() for m in range(i + 1, i + k)):
                    hits.append((i, i + k, "address")); break
    ks = [c for c, _ in tk]
    for ph, kind, span in TRIGGERS:                          # "my real name is ...", "my address is ...", "my number is ..."
        m = len(ph)
        for i in range(n - m + 1):
            if tuple(ks[i:i + m]) == ph:
                sp = _trigger_span(kind, tk, i + m, span)
                if sp: hits.append((sp[0], sp[1], kind))
    return _merge(hits)


def _trigger_span(kind, tk, a, span):
    """(first, last) index of what follows a trigger phrase like 'my number is', or None when it does not look like the real thing
    ('my number is one thing', 'my email is in the description', 'my real name is a secret' are not hits). Only the thing itself is covered, not the words after it."""
    n = len(tk)
    if a >= n: return None
    end_p = lambda q: tk[q][1].rstrip()[-1:] in ".!?。！？"
    digitish = lambda q: tk[q][0].isdigit() or tk[q][0] in NUM_WORDS or _digits_in(tk[q][1]) > 0
    if kind == "name":
        while a < n and tk[a][0] in FILLER: a += 1
        if a >= n or tk[a][0] in STOP_NAME: return None
        b = a
        while b + 1 < n and b - a < 2 and not end_p(b) and tk[b][1].rstrip()[-1:] != "," and tk[b + 1][0] not in NAME_END: b += 1
        return (a, b)
    win = tk[a:a + 8]
    last = min(n - 1, a + span - 1)
    for e in range(a, last + 1):                              # stop at the end of the sentence
        if end_p(e): last = e; break
    if kind == "phone":
        dig = sum(1 for c, r in win if c.isdigit() or c in NUM_WORDS or _digits_in(r))
        if dig < 2 and not any(_digits_in(r) >= 3 for _, r in win): return None
        b, gap = None, 0                                       # the digits, allowing one mis-heard word in between ('won' for 'one')
        for e in range(a, last + 1):
            if digitish(e) or tk[e][0] in JOIN_WORDS:
                if digitish(e): b = e
                gap = 0
            else:
                gap += 1
                if gap > 1: break
        return (a, b) if b is not None else None
    if kind == "address":
        t0 = a
        while t0 < n and tk[t0][0] in FILLER: t0 += 1
        if tk[a - 1][0] == "code":                             # 'my zip code is 90210'
            ds = [e for e in range(t0, min(last, t0 + 3) + 1) if digitish(e)]
            return (t0, ds[-1]) if ds else None
        if not any(c.isdigit() or _digits_in(r) or (r[:1].isupper() and c != "i") for c, r in tk[t0:t0 + 5]): return None
        suf = next((e for e in range(t0, last + 1) if tk[e][0] in STREET_SUFFIX), None)
        b = suf if suf is not None else min(last, t0 + 3)
        while suf is not None and b < last and b - suf < 3 and not end_p(b) and (tk[b + 1][1][:1].isupper() or _digits_in(tk[b + 1][1])): b += 1      # city / state / zip after the street
        return (t0, b)
    if kind == "email":
        if not any(c in ("dot", "@") or "@" in r or c in MAIL_HOSTS for c, r in win): return None
        end = None
        for e in range(a, last + 1):
            if "@" in tk[e][1] or (tk[e][0] in TLDS and e > a and tk[e - 1][0] == "dot"): end = e
            elif tk[e][0] in MAIL_HOSTS and end is None: end = e
        return (a, end) if end is not None else None
    return (a, last)


def _merge(hits):
    """Overlapping hits become one (the first kind wins)."""
    out = []
    for a, b, k in sorted(hits):
        if out and a <= out[-1][1] + 0: out[-1] = (out[-1][0], max(out[-1][1], b), out[-1][2])
        else: out.append((a, b, k))
    return out


def _stem(t):
    t = t.strip("'")
    return t[:-2] if t.endswith("'s") else t


def private_hits(words, plist):
    """[(first index, last index, 'private')] where one of the creator's private words / phrases is said. A phrase is matched word by word; in Japanese / Chinese / Korean text
    (written without spaces) the entry may sit inside a longer word."""
    plist = [p for p in (plist or []) if p]
    if not plist: return []
    tk = _toks(words); n = len(tk); ks = [_stem(c) for c, _ in tk]; hits = []
    for p in plist:
        parts = [_stem(clean(x)) for x in p.split() if clean(x)]
        if not parts: continue
        m = len(parts)
        for i in range(n - m + 1):
            if ks[i:i + m] == parts: hits.append((i, i + m - 1, "private"))
        if m == 1 and any(vcsmart_cjk(ch) for ch in parts[0]):
            for i, k in enumerate(ks):
                if parts[0] in k and k != parts[0]: hits.append((i, i, "private"))
    return _merge(hits)


def vcsmart_cjk(ch):
    o = ord(ch)
    return 0x3040 <= o <= 0x30FF or 0x4E00 <= o <= 0x9FFF or 0xAC00 <= o <= 0xD7AF or 0x3400 <= o <= 0x4DBF


def mark_words(words, o):
    """-> (words, report). Words that belong to a hit get 'priv' (they are bleeped and starred) or 'pwarn' (only reported). Words without a hit are returned as they were.
    report = [dict(kind, label, start, end, text, bleep)] . Modes (o['privacy']): off | warn (patterns reported, your private words bleeped) | bleep (everything bleeped)."""
    mode = (o or {}).get("privacy", "warn")
    if mode not in ("warn", "bleep") or not words: return words, []
    plist = vc23.split_words((o or {}).get("private_words"))
    spans = [(a, b, k, True) for a, b, k in private_hits(words, plist)] + [(a, b, k, mode == "bleep") for a, b, k in privacy_hits(words)]
    if not spans: return words, []
    out = list(words); report = []
    for a, b, k, bleep in sorted(spans):
        for i in range(a, b + 1):
            w = dict(out[i]); w["priv" if bleep else "pwarn"] = k; out[i] = w
        report.append(dict(kind=k, label=KIND_LABEL.get(k, k), start=float(words[a]["start"]), end=float(words[b]["end"]), text=" ".join(str(words[i]["w"]) for i in range(a, b + 1)), bleep=bleep))
    return out, report


# ================================================================ 32  keep it out of the text that is written about the clip
def scrub_text(text, o, repl="*"):
    """The text with every pattern hit and private word replaced by stars (same length) or removed (repl=''). For titles, hooks, post texts, hashtags and file names.
    Does nothing when the privacy guard is off."""
    mode = (o or {}).get("privacy", "warn")
    if mode not in ("warn", "bleep") or not text: return text
    s = str(text)
    parts = re.split(r"(\s+)", s); idx = [i for i, p in enumerate(parts) if p and not p.isspace()]
    toks = [parts[i] for i in idx]
    spans = privacy_hits(toks) + private_hits([t.lstrip("#") for t in toks], vc23.split_words((o or {}).get("private_words")))
    for a, b, k in spans:
        for j in range(a, b + 1):
            t = parts[idx[j]]; lead = "#" if t.startswith("#") else ""
            parts[idx[j]] = (lead + "*" * max(1, len(t) - len(lead))) if repl == "*" else ""
    return re.sub(r"[ \t]{2,}", " ", "".join(parts)).strip() if repl != "*" else "".join(parts)


def scrub_name(name, o):
    """A file name without the private parts (they are left out, not starred)."""
    t = scrub_text(str(name or "").replace("_", " "), o, repl="")
    return re.sub(r"\s+", " ", t).strip() or "clip"


# ================================================================ 31  privacy scan report
def words_from_text(text):
    """Words with times from a transcript text file ('[1:02] some words') or an .srt / .vtt subtitle file. Cues get evenly spread word times."""
    words = []
    cues = re.split(r"\n\s*\n", str(text).replace("\r", ""))
    for cue in cues:
        m = re.search(r"(\d+):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*(\d+):(\d{2}):(\d{2})[,.](\d{1,3})", cue)
        if m:
            g = m.groups(); a = int(g[0]) * 3600 + int(g[1]) * 60 + int(g[2]) + int(g[3].ljust(3, "0")) / 1000; b = int(g[4]) * 3600 + int(g[5]) * 60 + int(g[6]) + int(g[7].ljust(3, "0")) / 1000
            body = cue[m.end():]
            toks = body.split()
            for k, t in enumerate(toks): words.append(dict(w=t + ("." if k == len(toks) - 1 and t[-1:] not in ".!?。！？" else ""), start=a + (b - a) * k / max(1, len(toks)), end=a + (b - a) * (k + 1) / max(1, len(toks))))
            continue
        for line in cue.splitlines():
            m = re.match(r"^\s*\[(?:(\d+):)?(\d{1,2}):(\d{2})\]\s*(.*)$", line)
            if m:
                h, mi, se, rest = m.groups(); t0 = int(h or 0) * 3600 + int(mi) * 60 + int(se); toks = rest.split()
                for k, t in enumerate(toks): words.append(dict(w=t + ("." if k == len(toks) - 1 and t[-1:] not in ".!?。！？" else ""), start=t0 + k * .4, end=t0 + k * .4 + .3))
    return words


def scan_report(words, o):
    """The privacy scan: [dict(kind, label, start, end, text, bleep)] for every hit in `words`, whatever the mode (an 'off' setting still scans when asked)."""
    o2 = dict(o or {}); o2["privacy"] = "bleep" if o2.get("privacy", "warn") == "off" else o2.get("privacy", "warn")
    return mark_words(words, o2)[1]


def report_text(report, name=""):
    if not report: return "Nothing personal-looking was found" + (f" in {name}" if name else "") + ".\n(This is a pattern check of the speech-to-text. It cannot hear what the transcript got wrong - give the clip a quick listen.)"
    lines = [f"{len(report)} possible privacy hit{'s' if len(report) != 1 else ''}" + (f" in {name}" if name else "") + ":"]
    for r in report:
        t = int(r["start"]); lines.append(f"  {t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}  {r['label']}: “{r['text'][:60]}”" + ("  (bleeped)" if r.get("bleep") else "  (only reported)"))
    return "\n".join(lines)


# ================================================================ 27  flash safety check
def luminance(gray):
    """Relative luminance 0..1 of grey values 0..255 (gamma 2.2)."""
    return (np.asarray(gray, np.float32) / 255.0) ** 2.2


def flash_counts(series, fps, step=.10):
    """The most flashes inside any one second of a luminance series (one number per frame). A flash is a jump of at least `step` in relative luminance, followed by a jump back,
    where the darker side is below .8. Returns (flashes in the worst second, second where that second starts)."""
    L = np.asarray(series, np.float32)
    if len(L) < 3: return 0, 0.0
    d = np.diff(L); sig = []
    for i, x in enumerate(d):
        if abs(x) >= step and min(L[i], L[i + 1]) < .8: sig.append((i, 1 if x > 0 else -1))
    # opposite changes in a row make one half of a flash pair each; two of them are one flash
    pairs = []
    for (i, s), (j, t) in zip(sig, sig[1:]):
        if s != t: pairs.append(j)
    if not pairs: return 0, 0.0
    w = max(1, int(round(fps)))
    best, at = 0, 0
    for k, p in enumerate(pairs):
        c = sum(1 for q in pairs[k:] if q - p < w)
        if c > best: best, at = c, p
    return best, max(0.0, (at - 1) / fps)


def flash_report(mp4, ff, nowin, fps=25, size=(64, 36), max_flashes=3):
    """-> dict(ok, worst, at, notes). `worst` = most flashes in one second in any quarter of the picture. The common rule of thumb (WCAG 2.3.1, and the Ofcom / ITU broadcast guides it
    comes from) says a page or video should not flash more than three times a second. This measures the finished picture; it is not a medical test."""
    inf = vcmore._probe(ff, mp4, nowin); D = inf["dur"]
    if D <= 0: return dict(ok=True, worst=0, at=0.0, notes="Could not read the video, so it was not checked.", checked=False)
    if inf["h"] > inf["w"]: size = (size[1], size[0])
    fr = vcmedia.gray_frames(mp4, 0.0, min(D, 600.0), ff, nowin, fps, size)
    if len(fr) < 4: return dict(ok=True, worst=0, at=0.0, notes="Too short to check.", checked=False)
    w, h = size; A = np.stack([f[1] for f in fr]).astype(np.float32)
    quads = [A[:, :h // 2, :w // 2], A[:, :h // 2, w // 2:], A[:, h // 2:, :w // 2], A[:, h // 2:, w // 2:], A]
    worst, at = 0, 0.0
    for q in quads:
        c, t = flash_counts(luminance(q.reshape(len(q), -1).mean(1)), fps)
        if c > worst: worst, at = c, t
    ok = worst <= max_flashes
    return dict(ok=ok, worst=worst, at=float(at), checked=True,
                notes=("No fast flashing found." if ok else f"Fast flashing: up to {worst} flashes in one second around {int(at) // 60}:{int(at) % 60:02d}. "
                       "Some viewers (people with photosensitive epilepsy) can be harmed by that. Consider switching off the glitch / flash / B&W flash effects, or add a warning."))


# ================================================================ 28  clip check
PLATFORM_LIMITS = {"tiktok": 600, "shorts": 180, "reels": 180, "x": 140}      # seconds; these change - check each app (last looked at: 2025)
PLAT_NAME = {"tiktok": "TikTok", "shorts": "YouTube Shorts", "reels": "Instagram Reels", "x": "X"}
PLAT_FROM_OPT = {"any": "", "tiktok": "tiktok", "shorts": "shorts", "reels": "reels"}


def loudness(mp4, ff, nowin):
    """-> dict(lufs, peak (dBTP), momentary_max, at) of a clip's sound, or {} when it cannot be measured."""
    try:
        r = subprocess.run([ff, "-hide_banner", "-nostats", "-i", mp4, "-vn", "-af", "ebur128=peak=true:framelog=info", "-f", "null", "-"], capture_output=True, errors="replace", timeout=600, **_kw(nowin))
    except Exception: return {}
    txt = r.stderr or ""
    m_ = re.findall(r"t:\s*([\d.]+)\s+TARGET:.*?M:\s*(-?[\d.]+|-inf)", txt)
    mv = [(float(t), float(v)) for t, v in m_ if v not in ("-inf", "")]
    i_ = re.findall(r"\bI:\s+(-?[\d.]+)\s+LUFS", txt)
    p_ = re.findall(r"Peak:\s+(-?[\d.]+)\s+dBFS", txt)
    if not i_: return {}
    out = dict(lufs=float(i_[-1]), peak=float(p_[-1]) if p_ else None)
    if mv:
        t, v = max(mv, key=lambda x: x[1]); out.update(momentary_max=v, at=t)
        vals = sorted(x[1] for x in mv if x[1] > -60)                 # the 'usual' level of the talking: the middle of all measured moments (the integrated value ignores quiet parts)
        if vals: out["median"] = vals[len(vals) // 2]
    return out


def lead_silence(mp4, ff, nowin, secs=1.2):
    """True when the first `secs` seconds of the sound are (almost) silent."""
    try:
        r = subprocess.run([ff, "-v", "error", "-t", f"{secs}", "-i", mp4, "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"], capture_output=True, timeout=120, **_kw(nowin))
    except Exception: return False
    a = np.frombuffer(r.stdout or b"", np.int16).astype(np.float32)
    return bool(len(a) > 800 and float(np.sqrt(np.mean(a ** 2))) < 60.0)


def clip_check(mp4, ff, nowin, opts=None, platform=""):
    """-> list of dict(level 'ok'|'warn'|'bad', text) about one finished clip: length for the platform, shape, loudness and loud peaks, a silent or black start, fast flashing."""
    o = opts or {}; items = []
    add = lambda lvl, txt: items.append(dict(level=lvl, text=txt))
    if not os.path.isfile(mp4): return [dict(level="bad", text="The clip file is missing.")]
    inf = vcmore._probe(ff, mp4, nowin)
    if not inf["dur"]: return [dict(level="bad", text="This file could not be read as a video.")]
    plat = platform or PLAT_FROM_OPT.get(o.get("platform", "any"), "")
    D = inf["dur"]
    lim = PLATFORM_LIMITS.get(plat)
    if lim and D > lim: add("warn", f"{PLAT_NAME[plat]} may not accept {D:.0f} s (about {lim} s is the limit I know of; check the app).")
    elif lim: add("ok", f"Length {D:.0f} s fits {PLAT_NAME[plat]}.")
    else: add("ok", f"Length {D:.0f} s.")
    if D < 5: add("warn", "Very short: viewers may scroll past before it plays.")
    if plat in ("tiktok", "shorts", "reels") and inf["w"] and inf["h"] and inf["h"] < inf["w"] * 1.5: add("warn", f"This is not a tall picture ({inf['w']}x{inf['h']}); {PLAT_NAME[plat]} shows tall 9:16 videos best.")
    if not inf["audio"]: add("warn", "There is no sound in this clip.")
    else:
        ld = loudness(mp4, ff, nowin)
        if ld:
            tgt = o.get("loudness", "-14")
            try: tgt = float(tgt)
            except (TypeError, ValueError): tgt = None
            if tgt is not None and abs(ld["lufs"] - tgt) > 3.0: add("warn", f"Loudness is {ld['lufs']:.1f} LUFS; most apps aim for about {tgt:.0f}.")
            else: add("ok", f"Loudness {ld['lufs']:.1f} LUFS.")
            if ld.get("peak") is not None and ld["peak"] > -0.5: add("warn", f"The sound peaks at {ld['peak']:.1f} dB - it may crackle after the app re-encodes it.")
            ref = ld.get("median", ld["lufs"])
            if ld.get("momentary_max") is not None and ld["momentary_max"] - ref > 9.0:
                t = int(ld["at"]); add("warn", f"A very loud moment around {t // 60}:{t % 60:02d} ({ld['momentary_max'] - ref:.0f} LU above the rest). Try “Tame loud screams”, or warn viewers to lower the volume.")
        if lead_silence(mp4, ff, nowin): add("warn", "The first second is silent - the first seconds decide if people keep watching.")
    fr = vcmedia.gray_frames(mp4, 0.0, .3, ff, nowin, 10.0, (64, 36) if inf["w"] >= inf["h"] else (36, 64))
    fade_on = o.get("fade", "off") not in (None, "off")
    if fr and float(np.mean(fr[0][1])) < 10.0 and not fade_on: add("warn", "The clip starts on a black picture.")
    if o.get("flash_check", True):
        fl = flash_report(mp4, ff, nowin)
        if fl["checked"]: add("ok" if fl["ok"] else "bad", fl["notes"])
    return items


def check_text(items, name=""):
    mark = {"ok": "OK  ", "warn": "WARN", "bad": "FIX "}
    return (f"CLIP CHECK {name}\n" if name else "CLIP CHECK\n") + "\n".join(f"[{mark.get(i['level'], '?')}] {i['text']}" for i in items) + "\n"


def worst_level(items):
    lv = [i["level"] for i in items]
    return "bad" if "bad" in lv else "warn" if "warn" in lv else "ok"


# ================================================================ 39  disk-space guard
def disk_check(folder, need_mb):
    """-> (level 'ok'|'warn'|'stop', message, free_mb). 'stop' when the drive cannot hold the videos at all, 'warn' when it is nearly full afterwards."""
    p = os.path.abspath(str(folder or "."))
    while p and not os.path.exists(p):
        up = os.path.dirname(p)
        if up == p: break
        p = up
    try: free = shutil.disk_usage(p).free / 1e6
    except OSError: return "ok", "", 0.0
    need = max(0.0, float(need_mb))
    if free < need * 1.05 + 50: return "stop", f"There is only {free / 1000:.1f} GB free on that drive and this run needs about {need / 1000:.1f} GB. Free some space (Tools -> Space), choose another save folder, or make fewer / shorter clips.", free
    if free < need * 2 + 1000: return "warn", f"Free space is getting low: {free / 1000:.1f} GB left, this run needs about {need / 1000:.1f} GB.", free
    return "ok", "", free
