"""VTuber Clipper 2.2 - helpers for the Tools window and the extra My clips actions: a watched folder, a post sheet (CSV), a hashtag bank, a health check,
clean-up and free space, look codes you can paste to a friend, the cam box remembered per game, the words you teach the app, a run that can be resumed,
and a file that holds a list of best moments.
No screens in here. Every function takes plain data and returns plain data, and none of them raises on a bad file or a bad value (they return an empty result)."""
import base64, csv, datetime, glob, json, os, re, shutil, subprocess, sys, tempfile, threading, time, zlib

HOME = os.path.expanduser("~")
STORE = os.path.join(HOME, ".vtuberclipper_tools.json")
RUNFILE = os.path.join(HOME, ".vtuberclipper_run.json")
VIDEO_EXT = (".mp4", ".mkv", ".mov", ".webm", ".ts", ".flv", ".avi", ".m4v")
_LOCK = threading.Lock()


# ================================================================ a small settings store (one JSON file)
def _read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f: d = json.load(f)
        return d if isinstance(d, type(default)) else default
    except Exception: return default


def _write_json(path, data):
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, path); return True
    except OSError: return False


def store_get(key, default=None):
    with _LOCK: return _read_json(STORE, {}).get(key, default)


def store_put(key, value):
    with _LOCK:
        d = _read_json(STORE, {}); d[key] = value; return _write_json(STORE, d)


def _norm(p): return os.path.normpath(str(p))


# ================================================================ 30. a watched folder
def scan_watch(folder, seen=(), min_age=25.0, now=None, min_bytes=200_000):
    """New videos in `folder` that are finished: not in `seen`, not changed for `min_age` seconds (so a recording that is still being written is left alone). Oldest first."""
    out, now = [], (time.time() if now is None else now)
    folder = str(folder or "").strip().strip('"')
    if not folder: return out
    have = {_norm(s) for s in seen}
    try: names = os.listdir(folder)
    except OSError: return out
    for n in names:
        low = n.lower()
        if n.startswith(".") or not low.endswith(VIDEO_EXT) or ".part" in low or ".tmp" in low: continue
        p = os.path.join(folder, n)
        try:
            st = os.stat(p)
            if not os.path.isfile(p) or st.st_size < min_bytes or now - st.st_mtime < min_age: continue
        except OSError: continue
        if _norm(p) not in have: out.append((st.st_mtime, p))
    return [p for _, p in sorted(out)]


def remember_seen(seen, paths, cap=600):
    s = [_norm(x) for x in seen if isinstance(x, str)]
    for p in paths:
        if _norm(p) not in s: s.append(_norm(p))
    return s[-cap:]


# ================================================================ the title ideas file next to a clip
def parse_kit(text):
    """Pull the useful parts out of the post-kit .txt: title, description, hashtags, hype score, kind of clip."""
    text = text or ""
    m = re.search(r"1\.\s+(.+)", text)
    d = re.search(r"DESCRIPTION\n(.*?)\n\nHASHTAGS\n(.*)", text, re.S)
    h = re.search(r"HYPE SCORE\s+(\d+)", text)
    k = re.search(r"Kind of clip:\s*(.+)", text)
    return dict(title=m.group(1).strip() if m else "", desc=d.group(1).strip() if d else "", tags=d.group(2).strip().splitlines()[0].strip() if d and d.group(2).strip() else "",
                hype=int(h.group(1)) if h else None, kind=k.group(1).strip() if k else "")


_KITS = {}


def read_kit(mp4):
    """parse_kit() of the .txt next to a clip. Remembered until the file changes, so searching a long list of clips stays quick."""
    p = os.path.splitext(str(mp4))[0] + ".txt"
    try:
        st = os.stat(p); key = (st.st_mtime_ns, st.st_size)
        hit = _KITS.get(p)
        if hit and hit[0] == key: return hit[1]
        with open(p, encoding="utf-8") as f: k = parse_kit(f.read())
        if len(_KITS) > 3000: _KITS.clear()
        _KITS[p] = (key, k); return k
    except OSError: return parse_kit("")


# ================================================================ 33. the post sheet (CSV for Excel / Google Sheets)
CSV_COLUMNS = ["Clip file", "Made", "Kind", "Length (s)", "Hype", "Title", "Description", "Hashtags", "Posted to", "Favourite", "My tags", "Source video", "Starts at"]


def hms(t):
    t = int(max(0, t or 0)); return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}"


def post_rows(files, posted=None, fav=(), ledger=None, tags=None):
    """One row per clip. posted = {path: [where]}, fav = list of paths, ledger = function(path) -> entry or None, tags = function(path) -> [tags]."""
    posted, fav, rows = posted or {}, {_norm(x) for x in fav}, []
    for f in files:
        k = read_kit(f); e = (ledger(f) if ledger else None) or {}
        try: made = datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d %H:%M")
        except OSError: made = e.get("made", "")
        dur = e.get("dur") or ""
        rows.append({"Clip file": os.path.basename(str(f)), "Made": made, "Kind": e.get("kind", "") or k["kind"], "Length (s)": dur,
                     "Hype": k["hype"] if k["hype"] is not None else e.get("hype", "") or "", "Title": k["title"], "Description": k["desc"], "Hashtags": k["tags"],
                     "Posted to": ", ".join(posted.get(_norm(f), [])), "Favourite": "yes" if _norm(f) in fav else "",
                     "My tags": ", ".join(tags(f)) if tags else "", "Source video": os.path.basename(str(e.get("vod", ""))),
                     "Starts at": hms(e["start"]) if isinstance(e.get("start"), (int, float)) else ""})
    return rows


def write_csv(path, rows):
    """Save the sheet. utf-8 with a BOM so Excel shows emoji and accents right. Returns the number of rows written (0 on failure)."""
    try:
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore"); w.writeheader()
            for r in rows: w.writerow({k: _csv_safe(r.get(k, "")) for k in CSV_COLUMNS})
        return len(rows)
    except OSError: return 0


def _csv_safe(v):
    """A cell that starts with = + - @ would be run as a formula by Excel; put an apostrophe in front."""
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "@") or (s[:1] == "-" and not re.fullmatch(r"-?\d+(\.\d+)?", s)) else s


# ================================================================ 32. my own tags on clips + search
def clip_tags(path): return list(store_get("clip_tags", {}).get(_norm(path), []))


def set_clip_tags(path, tags):
    with _LOCK:
        d = _read_json(STORE, {}); m = d.setdefault("clip_tags", {})
        t = split_words(tags)
        if t: m[_norm(path)] = t
        else: m.pop(_norm(path), None)
        return _write_json(STORE, d)


def split_words(text, limit=12):
    """'funny, boss fight' -> ['funny', 'boss fight']. Commas, semicolons or new lines separate the tags; with none of them, every word is a tag."""
    if isinstance(text, (list, tuple)): items = [str(x) for x in text]
    else:
        text = str(text or "")
        items = re.split(r"[,;\n]+", text) if re.search(r"[,;\n]", text) else re.split(r"\s+", text.strip())
    out = []
    for x in items:
        x = re.sub(r"\s+", " ", x).strip().lstrip("#").strip()
        if x and len(x) <= 30 and x.lower() not in [y.lower() for y in out]: out.append(x)
    return out[:limit]


def clip_matches(query, path, kit=None, tags=(), kind="", posted=""):
    """True when every word of `query` is found in the clip's file name, title, hashtags, kind, posted marks or my tags."""
    q = [w for w in re.split(r"\s+", str(query or "").lower().strip()) if w]
    if not q: return True
    kit = kit if kit is not None else read_kit(path)
    hay = " ".join([os.path.basename(str(path)), kit.get("title", ""), kit.get("tags", ""), kit.get("kind", ""), kind, posted, " ".join(tags)]).lower()
    return all(w in hay for w in q)


# ================================================================ 34. hashtag bank
BANK_FILE = os.path.join(HOME, ".vtuberclipper_tags.json")


def split_tags(text):
    """'#cute funny, #Minecraft' -> ['cute', 'funny', 'Minecraft'] (no # sign, no repeats, each up to 30 letters)."""
    out = []
    for t in re.split(r"[\s,;]+", str(text or "")):
        t = re.sub(r"[^\w]", "", t.lstrip("#"), flags=re.U)
        if t and len(t) <= 30 and t.lower() not in [x.lower() for x in out]: out.append(t)
    return out[:30]


def bank_load():
    d = _read_json(BANK_FILE, {})
    b = dict(always=split_tags(" ".join(d.get("always", []))) if isinstance(d.get("always"), list) else [], games={}, kinds={})
    for sec in ("games", "kinds"):
        v = d.get(sec)
        if isinstance(v, dict):
            for k, lst in v.items():
                if isinstance(k, str) and isinstance(lst, list) and k.strip():
                    t = split_tags(" ".join(str(x) for x in lst))
                    if t: b[sec][k.strip().lower()] = t
    return b


def bank_save(b):
    return _write_json(BANK_FILE, dict(always=list(b.get("always", [])), games=dict(b.get("games", {})), kinds=dict(b.get("kinds", {}))))


def bank_tags(game="", kind="", bank=None, limit=12):
    """The tags from the bank for this clip: the 'always' ones, then the ones for the game, then for the kind of clip."""
    b = bank if bank is not None else bank_load()
    out = []
    for lst in (b.get("always", []), b.get("games", {}).get(str(game or "").strip().lower(), []), b.get("kinds", {}).get(str(kind or "").strip().lower(), [])):
        for t in lst:
            if t.lower() not in [x.lower() for x in out]: out.append(t)
    return out[:limit]


# ================================================================ 38. look codes (paste a look to a friend)
LOOK_PREFIX = "VTLOOK1:"
_LOOK_KEYS = ("style", "lmin", "lmax", "gap", "layout", "aspect", "fx", "intensity", "accent", "opts")
_SKIP_OPTS = ("logo", "music", "intro", "outro", "filler", "bg_image", "stickers", "handle", "channel", "game", "tags", "hint", "fixes", "private_words")      # personal things that never travel in a look code


def _plain(v):
    return isinstance(v, (str, int, float, bool)) or v is None


def look_code(look, name=""):
    """A short text (starts with VTLOOK1:) that holds a look. Anyone can paste it into their own app."""
    L = {k: look[k] for k in _LOOK_KEYS if k in look}
    L["opts"] = {k: v for k, v in (look.get("opts") or {}).items() if k not in _SKIP_OPTS and _plain(v)}
    L["fx"] = {k: bool(v) for k, v in (look.get("fx") or {}).items()}
    raw = json.dumps(dict(n=str(name)[:40], l=L), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return LOOK_PREFIX + base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode("ascii")


def look_from_code(text):
    """-> (name, look dict). Raises ValueError with a plain sentence when the text is not a look code."""
    m = re.search(re.escape(LOOK_PREFIX) + r"([A-Za-z0-9_\-=\s]+)", str(text or ""))
    if not m: raise ValueError("That doesn't look like a look code. It should start with VTLOOK1:")
    try:
        data = base64.urlsafe_b64decode(re.sub(r"\s+", "", m.group(1)).encode("ascii"))
        dec = zlib.decompressobj(); raw = dec.decompress(data, 200_000)
        if dec.unconsumed_tail or not dec.eof: raise ValueError("too big or cut off")
        d = json.loads(raw.decode("utf-8"))
        L = d["l"]
        if not isinstance(L, dict): raise ValueError("no look")
    except Exception: raise ValueError("That look code is damaged - ask for it again (copy the whole line).")
    look = {k: L[k] for k in _LOOK_KEYS if k in L}
    look["opts"] = {k: v for k, v in (L.get("opts") or {}).items() if _plain(v) and k not in _SKIP_OPTS} if isinstance(L.get("opts"), dict) else {}
    look["fx"] = {str(k): bool(v) for k, v in L["fx"].items()} if isinstance(L.get("fx"), dict) else {}
    return str(d.get("n", ""))[:40], look


# ================================================================ 44. the cam box remembered for each game
def cam_get(game, size=""):
    """The cam box saved for this game (as 'w:h:x:y'), or '' . When a video size ('1920x1080') is given the saved box only counts if it was saved for the same size."""
    g = str(game or "").strip().lower()
    if not g: return ""
    v = store_get("cams", {}).get(g)
    if isinstance(v, str): v = dict(cam=v, size="")              # saved by an earlier beta
    if not isinstance(v, dict): return ""
    if size and v.get("size") and v["size"] != size: return ""
    return str(v.get("cam", ""))


def cam_put(game, cam, size=""):
    g = str(game or "").strip().lower()
    if not g or not re.fullmatch(r"\d+:\d+:\d+:\d+", str(cam or "").strip()): return False
    with _LOCK:
        d = _read_json(STORE, {}); m = d.setdefault("cams", {}); m.pop(g, None); m[g] = dict(cam=str(cam).strip(), size=str(size or ""))
        while len(m) > 80: m.pop(next(iter(m)))
        return _write_json(STORE, d)


# ================================================================ 47. posting times for a whole batch of clips
def spread_times(slots, n, now=None):
    """The next `n` times from a list of daily slots [(hour, minute), ...] - one clip per slot, day after day (at least 5 minutes from now)."""
    now = now or datetime.datetime.now(); out = []
    slots = sorted({(int(h) % 24, int(m) % 60) for h, m in slots}) or [(19, 0)]
    for day in range(0, 90):
        d = now.date() + datetime.timedelta(days=day)
        for h, m in slots:
            t = datetime.datetime(d.year, d.month, d.day, h, m)
            if t > now + datetime.timedelta(minutes=5): out.append(t)
            if len(out) >= n: return out
    return out


# ================================================================ 43. the words you teach the app
def vocab_load():
    try: import vcsmart; f, kinds = vcsmart.VOCAB_FILE, vcsmart.VOCAB_KINDS
    except Exception: return {}
    d = _read_json(f, {})
    return {k: split_vocab(" ".join(d.get(k, []))) if isinstance(d.get(k), list) else [] for k in kinds}


def split_vocab(text):
    out = []
    for w in re.split(r"[,\n;]+", str(text or "")):
        w = re.sub(r"\s+", " ", w).strip().lower()
        if w and len(w) <= 30 and w not in out and " " not in w: out.append(w)         # one word each (the clip finder reads words one at a time)
    return out[:200]


def vocab_save(v):
    try: import vcsmart
    except Exception: return False
    return _write_json(vcsmart.VOCAB_FILE, {k: split_vocab(",".join(v.get(k, []))) for k in vcsmart.VOCAB_KINDS})


_COMMON = set("the a an and or but so to of in on at for with is are was were be been it its this that these those i you he she we they me my your our their him her them "
              "do does did have has had not no yes yeah okay ok oh um uh like just really very can could would should will gonna wanna got get going go going know think "
              "what when where who why how if then than there here out up down over into from about because as by all one two some any more most "
              "again happened thing things time times way back now still even also much many well too say said see look right left good bad big little little want need make made take took come came "
              "something someone anything everything nothing little guys chat stream today day night first last next other another every never always sometimes maybe actually basically literally".split())


def _doc_words(f):
    """The set of words in the transcript file next to a clip (empty when it has none)."""
    try:
        with open(os.path.splitext(str(f))[0] + "_transcript.txt", encoding="utf-8", errors="replace") as fh: txt = fh.read()
    except OSError: return None
    return {w for w in re.findall(r"[^\W\d_]{3,20}", txt.lower(), flags=re.U) if w not in _COMMON}


def suggest_vocab(files, background=(), known=(), top=12, min_count=3):
    """Words that keep showing up in the transcripts of the clips you kept (`files`) more than in your other clips (`background`), and that the clip finder does not know yet.
    -> [(word, in how many kept clips)]"""
    try: import vcsmart
    except Exception: return []
    have = set(known) | set().union(*[getattr(vcsmart, n, set()) for n in ("FAIL_W", "WIN_W", "RAGE_W", "SCARE_W", "CUTE_W", "CHAOS_W", "HYPE_PLUS", "SING_W", "GAME_W", "TALK_W")])
    docs = [d for d in (_doc_words(f) for f in files) if d]
    bg = [d for d in (_doc_words(f) for f in background) if d]
    cnt = {}
    for d in docs:
        for w in d:
            if w not in have: cnt[w] = cnt.get(w, 0) + 1
    out = []
    for w, c in cnt.items():
        if c < min_count: continue
        if bg and (sum(1 for d in bg if w in d) / len(bg)) > .5 * (c / len(docs)): continue        # said just as much in the clips you did not keep: not special
        out.append((w, c))
    return sorted(out, key=lambda x: (-x[1], x[0]))[:top]


# ================================================================ 45. a run that can be resumed
def run_start(info):
    """Write a note that a job started (removed again when it ends). If the app is closed in the middle, the note stays."""
    d = dict(info); d["started"] = time.strftime("%Y-%m-%d %H:%M"); return _write_json(RUNFILE, d)


def run_end():
    try: os.remove(RUNFILE); return True
    except OSError: return False


def run_left():
    """The job that did not finish last time, or None."""
    d = _read_json(RUNFILE, {})
    return d if d.get("video") and d.get("mode") else None


# ================================================================ 49. a file for a list of best moments
def moments_save(path, video, moments):
    keep = []
    for m in moments or []:
        try: keep.append(dict(start=float(m["start"]), end=float(m["end"]), score=int(m.get("score", 0)), peak=float(m.get("peak", m["start"])), text=str(m.get("text", ""))[:200],
                              tags=[str(t)[:40] for t in (m.get("tags") or [])][:8]))
        except (KeyError, TypeError, ValueError): continue
    return _write_json(path, dict(kind="vtc-moments", video=str(video or ""), moments=keep)) and len(keep)


def moments_load(path):
    """-> (video path, [moments]). Bad entries are skipped."""
    d = _read_json(path, {})
    out = []
    for m in d.get("moments", []) if isinstance(d.get("moments"), list) else []:
        try:
            s, e = float(m["start"]), float(m["end"])
            if not (0 <= s < e < 1e6): continue
            out.append(dict(start=s, end=e, score=max(0, min(100, int(m.get("score", 50)))), peak=float(m.get("peak", s)), text=str(m.get("text", ""))[:200],
                            tags=[str(t)[:40] for t in (m.get("tags") or [])][:8] if isinstance(m.get("tags"), list) else []))
        except (KeyError, TypeError, ValueError): continue
    return str(d.get("video", "")), out


# ================================================================ 36 / 37. clean-up and free space
LEFTOVER_ENDS = (".part", ".ytdl", ".tmp")
SIDECARS = ("_cover.jpg", "_cover_b.jpg", "_cover_c.jpg", "_transcript.txt", "_posts.txt", "_alt.txt", "_check.txt", ".gif", ".mp3", ".m4a", ".srt", ".vtt", ".txt")


def _du(path):
    n = 0
    for root, _d, files in os.walk(path):
        for f in files:
            try: n += os.path.getsize(os.path.join(root, f))
            except OSError: pass
    return n


def find_leftovers(out_dir):
    """Things a stopped or crashed run left behind: half-written render folders (.vclip_*), half downloads (.part), and title / subtitle / cover files whose video is gone.
    -> [dict(path, kind, bytes, why)]"""
    res = []
    out_dir = str(out_dir or "")
    if not os.path.isdir(out_dir): return res
    for sub in ("Shorts", "Recaps", "Twitter", "Montages", "VODs", "."):
        base = out_dir if sub == "." else os.path.join(out_dir, sub)
        if not os.path.isdir(base): continue
        depth0 = base.rstrip(os.sep).count(os.sep)
        for root, dirs, files in os.walk(base):
            if root.count(os.sep) - depth0 >= 3: dirs[:] = []
            if sub == "." and root == out_dir: dirs[:] = [d for d in dirs if d.startswith(".vclip_")]
            for d in list(dirs):
                if d.startswith(".vclip_"):
                    p = os.path.join(root, d); res.append(dict(path=p, kind="folder", bytes=_du(p), why="unfinished render")); dirs.remove(d)
            if sub == ".": continue
            low = {f.lower(): f for f in files}
            for f in files:
                p = os.path.join(root, f); lf = f.lower()
                if lf.endswith(LEFTOVER_ENDS):
                    try: res.append(dict(path=p, kind="file", bytes=os.path.getsize(p), why="unfinished download"))
                    except OSError: pass
                elif sub in ("Shorts", "Montages", "Twitter"):
                    for e in SIDECARS:
                        if lf.endswith(e) and not lf.endswith(".mp4"):
                            stem = f[:len(f) - len(e)]
                            # an "x_cover.jpg" belongs to "x.mp4"; a plain ".txt" might be anything, so only the ones written by the app (post kit) count
                            if (stem + ".mp4").lower() in low: break
                            if e == ".txt" and not _looks_like_kit(p): break
                            try: res.append(dict(path=p, kind="file", bytes=os.path.getsize(p), why="its video is gone"))
                            except OSError: pass
                            break
    seen, out = set(), []
    for r in res:
        if r["path"] not in seen: seen.add(r["path"]); out.append(r)
    return out


def _looks_like_kit(p):
    try:
        with open(p, encoding="utf-8", errors="replace") as f: head = f.read(400)
        return "TITLE IDEAS" in head or "HYPE SCORE" in head or "WHY THIS MOMENT" in head
    except OSError: return False


def remove_paths(paths):
    """Delete files and folders from a list. -> (how many removed, how many bytes freed)"""
    n, freed = 0, 0
    for p in paths:
        try:
            if os.path.isdir(p): b = _du(p); shutil.rmtree(p); n += 1; freed += b
            elif os.path.isfile(p): b = os.path.getsize(p); os.remove(p); n += 1; freed += b
        except OSError: pass
    return n, freed


def cache_report(cache_dir, preview_dir=""):
    """What the app keeps to be faster next time: [dict(key, label, bytes, count, note)]. Clearing any of it is safe (it is made again when needed)."""
    groups = [("an", "Sound analysis of your videos", ("an", "vis"), "Made again the next time you open that video (about a minute per hour of video)."),
              ("thumbs", "Small pictures for My clips", ("thumbs",), "Made again when you open My clips."),
              ("misc", "Other helpers", ("music_loudness",), "Made again when needed.")]
    out = []
    for key, label, pre, note in groups:
        n = b = 0
        try:
            for f in os.listdir(cache_dir):
                p = os.path.join(cache_dir, f)
                if any(f.startswith(x) for x in pre) and key != "thumbs":
                    if os.path.isfile(p): n += 1; b += os.path.getsize(p)
                elif key == "thumbs" and f == "thumbs" and os.path.isdir(p):
                    for r, _d, fs in os.walk(p): n += len(fs)
                    b += _du(p)
        except OSError: pass
        out.append(dict(key=key, label=label, bytes=b, count=n, note=note))
    n = b = 0
    if preview_dir and os.path.isdir(preview_dir):
        for f in glob.glob(os.path.join(preview_dir, "*")):
            try: n += 1; b += os.path.getsize(f) if os.path.isfile(f) else _du(f)
            except OSError: pass
    out.append(dict(key="previews", label="Style preview pictures", bytes=b, count=n, note="Made again when you press Preview."))
    return out


def cache_clear(cache_dir, key, preview_dir=""):
    """Empty one group of cache_report(). Never touches 'made_*.json' (the list of moments already made) or transcripts. -> bytes freed"""
    freed = 0
    try:
        if key == "previews":
            return remove_paths(glob.glob(os.path.join(preview_dir, "*")) if preview_dir else [])[1]
        pre = {"an": ("an", "vis"), "misc": ("music_loudness",)}.get(key, ())
        if key == "thumbs": return remove_paths([os.path.join(cache_dir, "thumbs")])[1]
        for f in os.listdir(cache_dir):
            if any(f.startswith(x) for x in pre) and os.path.isfile(os.path.join(cache_dir, f)): freed += remove_paths([os.path.join(cache_dir, f)])[1]
    except OSError: pass
    return freed


def vod_files(out_dir):
    """The downloaded VODs in <save folder>/VODs, biggest first: [(path, bytes, age in days)]."""
    d = os.path.join(str(out_dir or ""), "VODs"); res = []
    try:
        for f in os.listdir(d):
            p = os.path.join(d, f)
            if os.path.isfile(p) and f.lower().endswith(VIDEO_EXT):
                st = os.stat(p); res.append((p, st.st_size, max(0, int((time.time() - st.st_mtime) // 86400))))
    except OSError: pass
    return sorted(res, key=lambda x: -x[1])


def human(n):
    n = float(n)
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB": return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024


# ================================================================ 35. health check
def health(sc, out_dir="", app_dir="", cache_dir=""):
    """Look at everything the app needs. -> list of dict(level='ok'|'warn'|'bad', title, detail). Never raises."""
    res = []

    def add(level, title, detail=""): res.append(dict(level=level, title=title, detail=detail))
    nowin = getattr(sc, "NOWIN", {}) or {}
    ff = getattr(sc, "FF", "ffmpeg")
    # ffmpeg
    ver = ""
    try:
        r = subprocess.run([ff, "-hide_banner", "-version"], capture_output=True, text=True, errors="replace", timeout=20, **nowin)
        ver = (r.stdout or "").splitlines()[0] if r.returncode == 0 and r.stdout else ""
    except Exception: ver = ""
    if not ver: add("bad", "ffmpeg (the video tool) was not found", "Keep the bin folder next to the app, or reinstall it.")
    else:
        add("ok", "ffmpeg works", ver[:80])
        for what, args, needle, fix in (("Captions (libass)", ["-filters"], " ass ", "Captions need a full ffmpeg build."), ("H.264 video", ["-encoders"], "libx264", "Videos can't be saved without it.")):
            try:
                t = subprocess.run([ff, "-hide_banner"] + args, capture_output=True, text=True, errors="replace", timeout=20, **nowin).stdout or ""
                add("ok" if needle in t else "bad", what + (" is available" if needle in t else " is missing"), "" if needle in t else fix)
            except Exception: add("warn", what + " could not be checked")
    # downloader
    yt = shutil.which("yt-dlp")
    if yt:
        try:
            v = subprocess.run([yt, "--version"], capture_output=True, text=True, timeout=20, **nowin).stdout.strip()
            add("ok", "yt-dlp (the downloader) works", f"version {v}")
        except Exception: add("warn", "yt-dlp is there but did not start", "Try Settings → Downloads → update.")
    else: add("warn", "yt-dlp (the downloader) was not found", "You can still use video files from your PC. Links need it.")
    # python parts
    try:
        import numpy; add("ok", "numpy works", numpy.__version__)
    except Exception: add("bad", "numpy is missing", "Reinstall the app.")
    try:
        import importlib.util
        add("ok" if importlib.util.find_spec("faster_whisper") else "bad", "Speech-to-text " + ("is installed" if importlib.util.find_spec("faster_whisper") else "is missing"))
    except Exception: add("warn", "Speech-to-text could not be checked")
    # fonts
    fd = os.path.join(app_dir or getattr(sc, "APP_DIR", ""), "fonts")
    nf = len(glob.glob(os.path.join(fd, "*.[ot]tf"))) if os.path.isdir(fd) else 0
    add("ok" if nf else "warn", f"{nf} caption font{'s' if nf != 1 else ''} in the app folder" if nf else "No caption fonts in the app folder", "" if nf else "Captions fall back to Windows fonts.")
    # save folder + disk
    if out_dir:
        try:
            os.makedirs(out_dir, exist_ok=True)
            fd_, tp = tempfile.mkstemp(prefix=".vtc_check_", dir=out_dir); os.close(fd_); os.remove(tp)
            free = shutil.disk_usage(out_dir).free
            lvl = "ok" if free >= 10 * 2 ** 30 else "warn" if free >= 3 * 2 ** 30 else "bad"
            add("ok", "The save folder can be written to", out_dir)
            add(lvl, f"{human(free)} free on the save folder's drive", {"ok": "", "warn": "Getting low: a long recap needs several GB.", "bad": "Very low. Free up space (Tools → Clean up)."}[lvl])
        except OSError as e: add("bad", "I can't write to the save folder", f"{out_dir}  ({e})")
    else: add("warn", "No save folder chosen yet")
    # caches
    if cache_dir:
        b = _du(cache_dir) if os.path.isdir(cache_dir) else 0
        add("ok" if b < 2 * 2 ** 30 else "warn", f"The app's helper files use {human(b)}", "" if b < 2 * 2 ** 30 else "Tools → Clean up → Free up space can empty them.")
    add("ok", "Python " + sys.version.split()[0], "")
    return res


def health_summary(items):
    bad = sum(1 for i in items if i["level"] == "bad"); warn = sum(1 for i in items if i["level"] == "warn")
    return "Everything looks good ♡" if not bad and not warn else f"{bad} problem{'s' if bad != 1 else ''}, {warn} thing{'s' if warn != 1 else ''} to look at"


# ================================================================ 40 / 41. remake a clip, find where it came from
def source_of(entry):
    """What the ledger knows about a clip: dict(vod, start, end, when, vod_exists) or None."""
    if not entry or not entry.get("vod"): return None
    try: s, e = float(entry.get("start", 0)), float(entry.get("end", 0))
    except (TypeError, ValueError): return None
    return dict(vod=entry["vod"], start=s, end=e, when=hms(s), vod_exists=os.path.isfile(entry["vod"]), kind=entry.get("kind", ""), reasons=list(entry.get("reasons") or []), made=entry.get("made", ""))


def source_text(src):
    if not src: return "I don't know where this clip came from (it was made before the clip diary existed)."
    t = f"From “{os.path.basename(src['vod'])}” at {src['when']} (about {src['end'] - src['start']:.0f} seconds from there)."
    if not src["vod_exists"]: t += "\nThat video is not on this PC any more, so it can't be made again."
    if src["reasons"]: t += "\n\nWhy I picked it:\n" + "\n".join("  • " + str(r) for r in src["reasons"])
    return t
