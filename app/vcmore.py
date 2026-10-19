"""VTuber Clipper 2.2 - picture, sound and caption extras, and the clip ledger (a small diary of every clip that was made).
Everything returns plain strings / numbers (filter pieces, subtitle lines) or does one small ffmpeg job on a FINISHED clip; the engine decides when to use it.
A helper that cannot run returns "" / False instead of raising, so an extra can never stop the video itself."""
import json, os, re, shutil, subprocess, tempfile, threading, time

# ================================================================ options
CAP_CASES = {"auto": "Automatic", "upper": "ALL CAPS", "normal": "Normal (Like This)", "lower": "all lowercase"}
CAP_OUTLINES = {"thin": ("Thin", .55), "normal": ("Normal", 1.0), "thick": ("Thick", 1.5), "huge": ("Extra thick", 2.1)}
EXTRA_SHAPES = {"": "No extra copies", "1:1": "A square copy (1:1)", "16:9": "A landscape copy (16:9)", "1:1,16:9": "Square and landscape copies"}
DEFAULTS = dict(smart=True, auto_look=False, smart_len=False, variety=True, skip_greet=True, tight_end=False, use_taste=False, chat_file="", range_from="", range_to="",
                hop_logo=False, ready_dir="", slowmo=False, freeze=False, teaser=False, react_words=False, tame=False, hush=False, extra_shapes="",
                cap_case="auto", cap_outline="normal", cap_shadow=2, cap_words=0, cap_box=0, cap_rainbow=False)
BOOLS = ("smart", "auto_look", "smart_len", "variety", "skip_greet", "tight_end", "use_taste", "hop_logo", "slowmo", "freeze", "teaser", "react_words", "tame", "hush", "cap_rainbow")


def parse_time(s):
    """'1:23:45', '83:20', '90', '1h2m3s' -> seconds, or None when empty / not a time."""
    s = str(s or "").strip().lower()
    if not s: return None
    if re.fullmatch(r"\d+(?:\.\d+)?", s): return float(s)
    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+(?:\.\d+)?)s)?", s)
    if m and any(m.groups()):
        h, mi, se = m.groups(); return int(h or 0) * 3600 + int(mi or 0) * 60 + float(se or 0)
    parts = s.split(":")
    if 2 <= len(parts) <= 3 and all(re.fullmatch(r"\d+(?:\.\d+)?", p) for p in parts):
        t = 0.0
        for x in parts: t = t * 60 + float(x)
        return t
    return None


def clean_opts(d):
    """Check the 2.2 options of an options dict (in place) so a bad saved value can never reach the engine."""
    for k in BOOLS:
        v = d.get(k, DEFAULTS[k])
        d[k] = (v.strip().lower() not in ("", "0", "false", "no", "off", "none")) if isinstance(v, str) else bool(v)
    d["cap_case"] = d.get("cap_case") if d.get("cap_case") in CAP_CASES else "auto"
    d["cap_outline"] = d.get("cap_outline") if d.get("cap_outline") in CAP_OUTLINES else "normal"
    d["extra_shapes"] = d.get("extra_shapes") if d.get("extra_shapes") in EXTRA_SHAPES else ""
    for k, lo, hi in (("cap_shadow", 0, 8), ("cap_words", 0, 7), ("cap_box", 0, 100)):
        try: d[k] = min(hi, max(lo, int(float(d.get(k, DEFAULTS[k])))))
        except (TypeError, ValueError, OverflowError): d[k] = DEFAULTS[k]
    d["chat_file"] = str(d.get("chat_file") or "").strip()
    d["ready_dir"] = str(d.get("ready_dir") or "").strip()
    for k in ("range_from", "range_to"):
        v = str(d.get(k) or "").strip(); d[k] = v if parse_time(v) is not None else ""
    a, b = parse_time(d["range_from"]), parse_time(d["range_to"])
    if a is not None and b is not None and b <= a: d["range_from"] = d["range_to"] = ""
    return d


# ================================================================ captions
def apply_case(text, case, default_upper):
    """Caption text in the chosen case. 'auto' keeps what each style always did (CAPS on the pop styles, normal on subtitles)."""
    if case == "upper": return text.upper()
    if case == "lower": return text.lower()
    if case == "normal": return text
    return text.upper() if default_upper else text


def outline_size(base, name):
    return max(1, round(base * CAP_OUTLINES.get(name, CAP_OUTLINES["normal"])[1]))


def rainbow_colors(hi, text):
    """Colours that big words cycle through: the highlight colour, then two companions (ASS &HBBGGRR& strings)."""
    return [hi, "&H00FFE04D", "&H0070FF9A", "&H004DB8FF"]


# ================================================================ sound
HUSH = "afftdn=nr=14:nf=-38:tn=1"
TAME = "acompressor=threshold=0.09:ratio=4:attack=4:release=140:makeup=1.5,alimiter=limit=0.8:attack=2:release=35:level=disabled"


def audio_extras(o):
    """Filter text for 'hush the background hiss' and 'tame loud screams', to go in the voice chain (starts with a comma, or empty)."""
    out = ""
    if o.get("hush"): out += "," + HUSH
    if o.get("tame"): out += "," + TAME
    return out


# ================================================================ moving watermark
def hop_xy(W, H, w_expr, h_expr, pad, top_pad, bot_pad, right_pad, period=7.0):
    """x / y overlay expressions that move a logo to the next corner every `period` seconds (top right, bottom left, top left, bottom right ...)."""
    xs = [f"W-{w_expr}-{right_pad}", f"{pad}", f"{pad}", f"W-{w_expr}-{right_pad}"]
    ys = [f"{top_pad}", f"H-{h_expr}-{bot_pad}", f"{top_pad}", f"H-{h_expr}-{bot_pad}"]
    P = float(period); cyc = 4 * P
    def pick(vals):
        m = f"mod(t,{cyc:.2f})"
        return f"if(lt({m},{P:.2f}),{vals[0]},if(lt({m},{2 * P:.2f}),{vals[1]},if(lt({m},{3 * P:.2f}),{vals[2]},{vals[3]})))"
    return pick(xs), pick(ys)


# ================================================================ reaction words (subtitle lines)
REACT_COLORS = {"laugh": "00D5FF", "scream": "3D3DFF", "fail": "BFBFBF", "win": "6BE06B", "scare": "9B59FF", "cute": "C879FF", "rage": "3D6BFF", "setup": "FFFFFF", "hype": "00A5FF"}   # RRGGBB reversed below


def react_lines(o, g):
    """Big words that pop up on laughs / screams / fails / wins ("LOL", "EEEEK!", "OOF", "LET'S GO!"). o['react_plan_t'] = [(second in the clip, kind)]."""
    plan = o.get("react_plan_t") or []
    if not plan or not o.get("react_words"): return []
    try: import vcsmart
    except Exception: return []
    W, H, tall, dur, ts, san = g["W"], g["H"], g["tall"], g["dur"], g["ts"], g["san"]
    out, used = [], {}
    fs = max(40, int(g["sz"] * 1.25)); cy = int(H * (.36 if tall else .30))
    for t0, kind in plan[:6]:
        if not (.4 <= t0 <= dur - .5): continue
        words = vcsmart.REACT_WORDS.get(kind) or vcsmart.REACT_WORDS["hype"]
        i = used.get(kind, 0); used[kind] = i + 1
        word = words[i % len(words)]
        col = REACT_COLORS.get(kind, "FFFFFF"); bgr = col[4:6] + col[2:4] + col[0:2]
        ang = (-6, 5, -4, 7)[len(out) % 4]
        cx = int(W * (.5 + (.12 if len(out) % 2 else -.12)))
        out.append(f"Dialogue: 5,{ts(t0)},{ts(min(dur, t0 + 1.25))},Box,,0,0,0,,{{\\an5\\pos({cx},{cy})\\frz{ang}\\fs{fs}\\1c&HFFFFFF&\\3c&H{bgr}&\\fad(70,220)\\fscx40\\fscy40"
                   f"\\t(0,160,\\fscx125\\fscy125)\\t(160,300,\\fscx100\\fscy100)\\t(700,1000,\\fscx108\\fscy108)}}{san(word)}")
    return out


# ================================================================ things done to a finished clip
def _kw(nowin):
    """subprocess options: never wait for keyboard input, no console window on Windows (the engine passes NOWIN, which may already hold stdin)."""
    d = dict(stdin=subprocess.DEVNULL); d.update(nowin or {}); return d


def _run(ff, args, nowin, timeout=1800):
    try:
        r = subprocess.run([ff, "-y", "-v", "error"] + args, capture_output=True, errors="replace", timeout=timeout, **_kw(nowin))
        return r.returncode == 0, (r.stderr or "")[-300:]
    except Exception as e: return False, str(e)[:200]


def _probe(ff, path, nowin):
    try:
        r = subprocess.run([ff, "-hide_banner", "-i", path], capture_output=True, errors="replace", timeout=60, **_kw(nowin))
        txt = r.stderr or ""
    except Exception: return dict(dur=0.0, fps=30.0, audio=False, w=0, h=0)
    d = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", txt); dur = int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3)) if d else 0.0
    f = re.search(r"(\d+(?:\.\d+)?) fps", txt); fps = float(f.group(1)) if f else 30.0
    wh = re.search(r"Video:.*?,\s*(\d{2,5})x(\d{2,5})", txt)
    return dict(dur=dur, fps=fps, audio="Audio:" in txt, w=int(wh.group(1)) if wh else 0, h=int(wh.group(2)) if wh else 0)


_FCF = {}


def _fcflag(ff, nowin):
    """Newer ffmpeg builds take the filter graph from a file with -/filter_complex, older ones with -filter_complex_script."""
    if ff not in _FCF:
        try:
            with tempfile.TemporaryDirectory() as d:
                p = os.path.join(d, "t.txt"); open(p, "w").write("[0:v]null[o]")
                r = subprocess.run([ff, "-v", "error", "-f", "lavfi", "-i", "color=d=0.1", "-/filter_complex", p, "-map", "[o]", "-f", "null", "-"], capture_output=True, timeout=60, **_kw(nowin))
                _FCF[ff] = "-/filter_complex" if r.returncode == 0 else "-filter_complex_script"
        except Exception: _FCF[ff] = "-filter_complex_script"
    return _FCF[ff]


def _swap(tmp, path):
    try: os.replace(tmp, path); return True
    except OSError:
        try: os.remove(tmp)
        except OSError: pass
        return False


def slowmo(path, t, ff, nowin, venc, factor=.5, span=1.2):
    """Slow the clip down to `factor` speed for `span` seconds starting at second `t` (the sound slows with it). Returns the new length or 0."""
    inf = _probe(ff, path, nowin); D = inf["dur"]
    if D < 4 or t < .3 or t + span > D - .2: return 0.0
    f = max(.5, min(1.0, float(factor))); fps = inf["fps"] or 30.0; t1 = t + span
    g = [f"[0:v]split=3[v0][v1][v2]", f"[v0]trim=0:{t:.3f},setpts=PTS-STARTPTS[a]", f"[v1]trim={t:.3f}:{t1:.3f},setpts=(PTS-STARTPTS)/{f:.3f},fps={fps:.3f}[b]",
         f"[v2]trim=start={t1:.3f},setpts=PTS-STARTPTS[c]", "[a][b][c]concat=n=3:v=1:a=0[vo]"]
    if inf["audio"]:
        g += [f"[0:a]asplit=3[a0][a1][a2]", f"[a0]atrim=0:{t:.3f},asetpts=PTS-STARTPTS[x]", f"[a1]atrim={t:.3f}:{t1:.3f},asetpts=PTS-STARTPTS,atempo={f:.3f}[y]",
              f"[a2]atrim=start={t1:.3f},asetpts=PTS-STARTPTS[z]", "[x][y][z]concat=n=3:v=0:a=1[ao]"]
    tmp = path + ".slow.mp4"
    with tempfile.TemporaryDirectory() as td:
        open(os.path.join(td, "g.txt"), "w").write(";\n".join(g))
        args = ["-i", os.path.abspath(path), _fcflag(ff, nowin), os.path.join(td, "g.txt"), "-map", "[vo]"] + (["-map", "[ao]"] if inf["audio"] else []) + \
               list(venc) + ["-pix_fmt", "yuv420p"] + (["-c:a", "aac", "-b:a", "192k"] if inf["audio"] else []) + ["-movflags", "+faststart", tmp]
        ok, err = _run(ff, args, nowin)
    if not ok or not os.path.isfile(tmp):
        try: os.remove(tmp)
        except OSError: pass
        return 0.0
    return _probe(ff, path, nowin)["dur"] if _swap(tmp, path) else 0.0


def freeze(path, t, ff, nowin, venc, hold=.7):
    """Stop the picture on the frame at second `t` for `hold` seconds with a little 'record scratch' sound, then go on. Returns the new length or 0."""
    inf = _probe(ff, path, nowin); D = inf["dur"]
    if D < 4 or t < 1.0 or t > D - 1.0: return 0.0
    fps = inf["fps"] or 30.0; n = max(2, int(hold * fps) + 1)
    g = [f"[0:v]split=3[v0][v1][v2]", f"[v0]trim=0:{t:.3f},setpts=PTS-STARTPTS[a]",
         f"[v1]trim=start={t:.3f}:end={t + 1.5 / fps:.3f},setpts=PTS-STARTPTS,fps={fps:.3f},loop=loop={n}:size=1,trim=duration={hold:.3f},setpts=PTS-STARTPTS[b]",
         f"[v2]trim=start={t:.3f},setpts=PTS-STARTPTS[c]", "[a][b][c]concat=n=3:v=1:a=0[vo]"]
    if inf["audio"]:
        sc = f"aevalsrc='0.35*sin(2*PI*(1500-1900*t)*t)*exp(-4*t)+0.12*random(0)*exp(-9*t)':d={hold:.3f}:s=48000,aformat=channel_layouts=stereo"
        g += [f"[0:a]aformat=sample_rates=48000:channel_layouts=stereo,asplit=2[a0][a2]", f"[a0]atrim=0:{t:.3f},asetpts=PTS-STARTPTS[x]", sc + "[y]",
              f"[a2]atrim=start={t:.3f},asetpts=PTS-STARTPTS[z]", "[x][y][z]concat=n=3:v=0:a=1[ao]"]
    tmp = path + ".frz.mp4"
    with tempfile.TemporaryDirectory() as td:
        open(os.path.join(td, "g.txt"), "w").write(";\n".join(g))
        args = ["-i", os.path.abspath(path), _fcflag(ff, nowin), os.path.join(td, "g.txt"), "-map", "[vo]"] + (["-map", "[ao]"] if inf["audio"] else []) + \
               list(venc) + ["-pix_fmt", "yuv420p"] + (["-c:a", "aac", "-b:a", "192k"] if inf["audio"] else []) + ["-movflags", "+faststart", tmp]
        ok, err = _run(ff, args, nowin)
    if not ok or not os.path.isfile(tmp):
        try: os.remove(tmp)
        except OSError: pass
        return 0.0
    return _probe(ff, path, nowin)["dur"] if _swap(tmp, path) else 0.0


def teaser(path, t, ff, nowin, venc, before=.5, after=1.6):
    """Put the best two seconds (around second `t`) at the very start, then play the whole clip from the beginning with a quick white flash in between."""
    inf = _probe(ff, path, nowin); D = inf["dur"]
    if D < 8 or t < 4.0 or t > D - .5: return 0.0
    a = max(0.0, t - before); b = min(D, t + after); fps = inf["fps"] or 30.0
    g = [f"[0:v]split=2[v0][v1]", f"[v0]trim={a:.3f}:{b:.3f},setpts=PTS-STARTPTS,fps={fps:.3f}[tv]", f"[v1]setpts=PTS-STARTPTS,fps={fps:.3f},fade=t=in:st=0:d=0.18:color=white[mv]", "[tv][mv]concat=n=2:v=1:a=0[vo]"]
    if inf["audio"]:
        FM = "aformat=sample_rates=48000:channel_layouts=stereo"
        g += [f"[0:a]{FM},asplit=2[a0][a1]", f"[a0]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS,afade=t=out:st={max(0, b - a - .12):.3f}:d=0.12[ta]", "[a1]asetpts=PTS-STARTPTS[ma]", "[ta][ma]concat=n=2:v=0:a=1[ao]"]
    tmp = path + ".tz.mp4"
    with tempfile.TemporaryDirectory() as td:
        open(os.path.join(td, "g.txt"), "w").write(";\n".join(g))
        args = ["-i", os.path.abspath(path), _fcflag(ff, nowin), os.path.join(td, "g.txt"), "-map", "[vo]"] + (["-map", "[ao]"] if inf["audio"] else []) + \
               list(venc) + ["-pix_fmt", "yuv420p"] + (["-c:a", "aac", "-b:a", "192k"] if inf["audio"] else []) + ["-movflags", "+faststart", tmp]
        ok, err = _run(ff, args, nowin)
    if not ok or not os.path.isfile(tmp):
        try: os.remove(tmp)
        except OSError: pass
        return 0.0
    return _probe(ff, path, nowin)["dur"] if _swap(tmp, path) else 0.0


def finish_clip(path, o, ev_t, ff, nowin, venc, log=print):
    """Teaser / slow-mo / freeze on a finished clip. `ev_t` = seconds inside the clip where something big happens, strongest first. Returns what was done."""
    done = []
    if not os.path.isfile(path) or not ev_t: return done
    try:
        if o.get("slowmo"):
            t = ev_t[0]
            if slowmo(path, max(.3, t - .25), ff, nowin, venc): done.append("slow-mo")
        if o.get("freeze"):
            cand = [x for x in ev_t[1:] + ev_t[:1] if x >= 1.5]
            if cand and freeze(path, cand[0] + .15, ff, nowin, venc): done.append("freeze frame")
        if o.get("teaser"):
            if teaser(path, ev_t[0] + (.25 if o.get("slowmo") else 0.0), ff, nowin, venc): done.append("teaser")
    except Exception as e: log("(an extra for this clip was skipped:", str(e)[:80] + ")")
    return done


# ================================================================ the clip ledger (what was made, from where, and what happened to it)
LEDGER = os.path.join(os.path.expanduser("~"), ".vtuberclipper_ledger.json")
_LOCK = threading.Lock()


def _load():
    try:
        with open(LEDGER, encoding="utf-8") as f: d = json.load(f)
        return d if isinstance(d, dict) and isinstance(d.get("clips"), list) else {"clips": []}
    except Exception: return {"clips": []}


def _save(d):
    try:
        d["clips"] = d["clips"][-3000:]
        tmp = LEDGER + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f: json.dump(d, f, ensure_ascii=False)
        os.replace(tmp, LEDGER); return True
    except OSError: return False


def ledger_all():
    with _LOCK: return list(_load()["clips"])


def ledger_add(entry):
    """Remember a clip: path, vod, start, end, kind, conf, hype, dur, reasons, look, made."""
    e = dict(entry); e["path"] = os.path.abspath(str(e.get("path", ""))); e.setdefault("made", time.strftime("%Y-%m-%d %H:%M"))
    with _LOCK:
        d = _load(); d["clips"] = [c for c in d["clips"] if c.get("path") != e["path"]] + [e]
        return _save(d)


def ledger_find(path):
    p = os.path.abspath(str(path))
    with _LOCK:
        for c in reversed(_load()["clips"]):
            if c.get("path") == p: return dict(c)
    return None


def ledger_set(path, **kw):
    """Change facts about a clip (fav, posted, deleted, tags, note...). Does nothing when the clip is not in the ledger."""
    p = os.path.abspath(str(path))
    with _LOCK:
        d = _load()
        for c in d["clips"]:
            if c.get("path") == p: c.update(kw); return _save(d)
    return False


def ledger_move(old, new):
    """A clip was moved or renamed: point its ledger row at the new place. Returns True when a row was changed."""
    a, b = os.path.abspath(str(old)), os.path.abspath(str(new))
    with _LOCK:
        d = _load(); hit = False
        for c in d["clips"]:
            if c.get("path") == a: c["path"] = b; hit = True
        return _save(d) if hit else False


def ledger_forget_missing():
    """Drop entries of clips that were deleted (outside the app). Returns how many."""
    with _LOCK:
        d = _load(); n = len(d["clips"]); d["clips"] = [c for c in d["clips"] if os.path.isfile(c.get("path", "")) or c.get("deleted")]      # rows of deleted clips stay: they teach "my taste" what was not wanted
        if len(d["clips"]) != n: _save(d)
        return n - len(d["clips"])


# ================================================================ a "ready to post" folder
def copy_ready(mp4, folder, with_files=True):
    """Copy a finished clip (and its title ideas / subtitles / cover) into the creator's own "ready to post" folder. Returns how many files were copied."""
    folder = str(folder or "").strip()
    if not folder or not os.path.isfile(str(mp4)): return 0
    n = 0
    try:
        os.makedirs(folder, exist_ok=True)
        stem = os.path.splitext(str(mp4))[0]
        for f in [str(mp4)] + ([stem + e for e in (".txt", ".srt", "_cover.jpg", "_cover_b.jpg", "_cover_c.jpg", "_posts.txt", "_alt.txt", ".gif", ".mp3", ".m4a")] if with_files else []):
            if not os.path.isfile(f): continue
            dest = os.path.join(folder, os.path.basename(f))
            if os.path.abspath(dest) == os.path.abspath(f): continue
            if os.path.exists(dest):
                b, e = os.path.splitext(dest); k = 2
                while os.path.exists(f"{b} ({k}){e}"): k += 1
                dest = f"{b} ({k}){e}"
            shutil.copy2(f, dest); n += 1
    except OSError: pass
    return n


def ledger_mark(fav=(), posted=()):
    """Tell the diary which clips are favourites / posted (used once at start-up, for clips made before the diary existed). Returns how many rows changed."""
    fav = {os.path.abspath(str(p)) for p in fav}; posted = {os.path.abspath(str(p)) for p in posted}
    if not fav and not posted: return 0
    with _LOCK:
        d = _load(); n = 0
        for c in d["clips"]:
            p = c.get("path")
            if p in fav and not c.get("fav"): c["fav"] = True; n += 1
            if p in posted and not c.get("posted"): c["posted"] = True; n += 1
        if n: _save(d)
        return n
