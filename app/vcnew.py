"""VTuber Clipper 2.1 - the engine side of the new tools:
text on screen, social callouts (Like / Follow / Subscribe...), custom layouts, a voice for your texts, trimming and tidying a finished clip,
a montage of several clips, and the post planner.

Everything here only builds ffmpeg filter text / ASS caption lines or runs ffmpeg itself - no extra programs, no internet.
Every helper is safe to call with an empty or wrong setting (it then does nothing), so a typo in one box can never stop a video."""
import datetime, json, os, re, shutil, subprocess, sys, tempfile

# ================================================================ text on screen
TEXT_POS = {"top": "Near the top", "mid": "In the middle", "low": "Lower third"}
TEXT_STYLES = {"pill": "Colour pill", "outline": "Big outlined letters", "plain": "Small plain text"}
MAX_TEXTS = 3
MAX_TEXT_LEN = 90


def _num(v, d, lo, hi):
    try: x = float(str(v).strip().replace(",", "."))
    except (TypeError, ValueError): return d
    return d if x != x else max(lo, min(hi, x))


def parse_texts(raw):
    """A settings string (JSON list) -> up to 3 clean boxes: [dict(t, at, for, pos, style, say)]. Anything unreadable gives []."""
    try: data = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError): return []
    out = []
    for d in data if isinstance(data, list) else []:
        if not isinstance(d, dict): continue
        t = re.sub(r"\s+", " ", re.sub(r"[{}\\\r\n]", " ", str(d.get("t", "")))).strip()[:MAX_TEXT_LEN]
        if not t: continue
        out.append(dict(t=t, at=_num(d.get("at"), 0.0, -3600, 3600), **{"for": _num(d.get("for"), 3.0, .5, 30)},
                        pos=d.get("pos") if d.get("pos") in TEXT_POS else "mid", style=d.get("style") if d.get("style") in TEXT_STYLES else "pill", say=bool(d.get("say"))))
        if len(out) >= MAX_TEXTS: break
    return out


def texts_json(items):
    items = parse_texts(items)
    return json.dumps(items, ensure_ascii=False, separators=(",", ":")) if items else ""


def text_window(b, dur):
    """(start, end) of a text box inside a clip of `dur` seconds, or None when it does not fit. A negative start counts from the end."""
    a = b["at"] if b["at"] >= 0 else dur + b["at"]
    a = max(0.0, a); e = min(dur, a + b["for"])
    return (a, e) if e - a >= .4 and a < dur - .3 else None


def text_lines(o, g):
    """ASS lines for the text boxes. g: dict(W, H, tall, K, dur, safe, sz, ts, san)."""
    out, W, H, dur, ts, san, sz = [], g["W"], g["H"], g["dur"], g["ts"], g["san"], g["sz"]
    st = g["safe"][2]; tall = g["tall"]
    ys = {"top": max(H * (.11 if tall else .10), H * (st + .035)), "mid": H * (.38 if tall else .38), "low": H * (.58 if tall else .70)}
    for b in parse_texts(o.get("text_boxes")):
        win = text_window(b, dur)
        if not win: continue
        a, e = win; y = int(ys[b["pos"]]); x = W // 2
        txt = san(b["t"])
        pop = "\\fad(160,220)\\fscx62\\fscy62\\t(0,230,\\fscx108\\fscy108)\\t(230,380,\\fscx100\\fscy100)"
        if b["style"] == "pill":
            out.append(f"Dialogue: 6,{ts(a)},{ts(e)},Box,,0,0,0,,{{\\an5\\pos({x},{y})\\fs{max(22, int(sz * .6))}{pop}}}{txt}")
        elif b["style"] == "outline":
            out.append(f"Dialogue: 6,{ts(a)},{ts(e)},Default,,0,0,0,,{{\\an5\\pos({x},{y})\\fs{max(24, int(sz * .95))}{pop}}}{txt}")
        else:
            out.append(f"Dialogue: 6,{ts(a)},{ts(e)},Line,,0,0,0,,{{\\an5\\pos({x},{y})\\fs{max(18, int(sz * .5))}\\fad(160,220)}}{txt}")
    return out


# ================================================================ social callouts
CALLOUTS = {   # key: (what the button says, colour as RRGGBB)
    "like": ("LIKE", "1877F2"), "follow": ("FOLLOW", "9146FF"), "subscribe": ("SUBSCRIBE", "E01B1B"), "share": ("SHARE", "1FA855"), "comment": ("COMMENT", "F09A00")}
CALLOUT_NAMES = {k: v[0].title() for k, v in CALLOUTS.items()}


def parse_callouts(raw):
    """'follow,like' -> ['follow', 'like'] (only known ones, no repeats, in the order given)."""
    out = []
    for k in re.split(r"[\s,;|]+", str(raw or "").lower()):
        if k in CALLOUTS and k not in out: out.append(k)
    return out


def callout_times(n, dur, end_card=False):
    """Start seconds for n callouts, one at a time (2.2 s each, spread over the clip, never touching the end card). A short clip shows fewer."""
    L = 2.2; last = dur - (3.0 if end_card else .9)
    if n <= 0 or dur < 5.0 or last - 1.8 < L: return []
    first = max(1.8, min(dur * .25, last - L))
    n = max(1, min(n, int((last - L - first) // (L + 1.0)) + 1))
    if n == 1: return [round(first, 2)]
    step = min(9.0, (last - L - first) / (n - 1))
    return [round(first + i * step, 2) for i in range(n)]


def callout_lines(o, g):
    out, W, H, dur, ts = [], g["W"], g["H"], g["dur"], g["ts"]
    keys = parse_callouts(o.get("callouts")); tall = g["tall"]
    if not keys: return out
    cy = int(H * (.50 if tall else .56)); fs = max(26, int(g["sz"] * .62))
    for k, t0 in zip(keys, callout_times(len(keys), dur, bool(o.get("cta")) and dur > 3.2)):
        label, col = CALLOUTS[k]
        bgr = col[4:6] + col[2:4] + col[0:2]
        out.append(f"Dialogue: 6,{ts(t0)},{ts(t0 + 2.2)},Box,,0,0,0,,{{\\an5\\pos({W // 2},{cy})\\fs{fs}\\1c&HFFFFFF&\\3c&H{bgr}&\\fad(160,200)\\fscx55\\fscy55"
                   f"\\t(0,230,\\fscx112\\fscy112)\\t(230,380,\\fscx100\\fscy100)\\t(1200,1380,\\fscx107\\fscy107)\\t(1380,1560,\\fscx100\\fscy100)}}{label}")
    return out


def ass_extras21(o, g):
    """All the caption-canvas lines of the 2.1 tools. Each block is checked on its own."""
    out = []
    for fn in (text_lines, callout_lines):
        try: out += fn(o, g)
        except Exception: pass
    return out


# ================================================================ layouts
LAYOUT_SPECS = {                      # layouts that are just two boxes (x, y, w, h as fractions of the finished video)
    "stackb": "game=0,0,1,.667;cam=0,.667,1,.333",
    "side": "cam=0,0,.4,1;game=.4,0,.6,1",
}
LAYOUT_PRESETS = [                    # what the layout designer offers to start from
    ("Cam on top", "cam=0,0,1,.333;game=0,.333,1,.667"),
    ("Cam at the bottom", "game=0,0,1,.667;cam=0,.667,1,.333"),
    ("Side by side", "cam=0,0,.4,1;game=.4,0,.6,1"),
    ("Big cam, small game", "cam=0,0,1,.58;game=.04,.62,.92,.34,fit"),
    ("Game with a cam in the corner", "game=0,0,1,1;cam=.60,.04,.36,.20"),
    ("Whole game + round cam", "game=0,.22,1,.56,fit;cam=.30,.02,.40,.20,round"),
]
MIN_BOX = .06


def _box(parts):
    try:
        x, y, w, h = (float(p.replace(",", ".")) for p in parts[:4])
    except (ValueError, IndexError): return None
    if not all(v == v for v in (x, y, w, h)): return None
    w = max(MIN_BOX, min(1.0, w)); h = max(MIN_BOX, min(1.0, h)); x = max(0.0, min(1.0 - w, x)); y = max(0.0, min(1.0 - h, y))
    flags = {p.strip().lower() for p in parts[4:]}
    return dict(x=x, y=y, w=w, h=h, fit="fit" in flags, round="round" in flags)


def parse_layout(spec):
    """'game=0,0,1,.667;cam=0,.667,1,.333;bg=blur' -> dict(game=box|None, cam=box|None, bg='blur'|'color'|'black'). Boxes are fractions of the frame."""
    res = dict(game=None, cam=None, bg="")
    for part in str(spec or "").split(";"):
        if "=" not in part: continue
        k, v = part.split("=", 1); k = k.strip().lower(); v = v.strip()
        if k in ("game", "cam"): res[k] = _box([p for p in v.split(",")])
        elif k == "bg" and v.lower() in ("blur", "color", "black"): res["bg"] = v.lower()
    return res


def layout_spec(layout, o=None):
    return LAYOUT_SPECS.get(layout) or ((o or {}).get("custom_layout") if layout == "custom" else "")


def layout_valid(spec):
    p = parse_layout(spec); return bool(p["game"] or p["cam"])


def layout_needs_cam(layout, o=None):
    if layout in ("stack", "pip", "camfull", "stackb", "side"): return True
    return layout == "custom" and bool(parse_layout(layout_spec(layout, o))["cam"])


def make_spec(game=None, cam=None, bg=""):
    """boxes -> the settings string (the layout designer writes this)."""
    def one(name, b):
        if not b: return ""
        f = ",".join(f"{b[k]:.3f}".rstrip("0").rstrip(".") or "0" for k in ("x", "y", "w", "h")) + (",fit" if b.get("fit") else "") + (",round" if b.get("round") else "")
        return f"{name}={f}"
    return ";".join(x for x in (one("game", game), one("cam", cam), f"bg={bg}" if bg in ("blur", "color", "black") else "") if x)


def box_graph(spec, cam, W, H, fps, o=None, disc_mask=None, bg_color="1b1230"):
    """Filter text: input [v], output [vv] at exactly W x H. The game and the cam are each cut to fill their box (or, with 'fit', shown whole);
    the cam is drawn over the game. `cam` is the cam crop 'w:h:x:y'. Boxes of something that is missing (no cam picked) are left out."""
    p = parse_layout(spec); has_cam = bool(p["cam"] and cam); gm = p["game"]
    if not gm and not has_cam: gm = dict(x=0, y=0, w=1, h=1, fit=False, round=False)
    ev = lambda v: max(2, int(round(v / 2.0)) * 2)
    uses = ["g"] * bool(gm) + ["c"] * has_cam
    o = o or {}; bg = p["bg"] or (o.get("bg_style") if o.get("bg_style") in ("blur", "color") else "blur")
    blur_bg = bg == "blur" and not (gm and not gm["fit"] and gm["w"] >= .99 and gm["h"] >= .99)
    srcs = (["b"] if blur_bg else []) + uses
    g = []
    if len(srcs) == 1: g.append(f"[v]null[{srcs[0]}]")
    else: g.append("[v]split=" + str(len(srcs)) + "".join(f"[{s}]" for s in srcs))
    if blur_bg:
        sw, sh = max(2, W // 10 * 2), max(2, H // 10 * 2)
        g.append(f"[b]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},scale={sw}:{sh},boxblur=5:2,scale={W}:{H}[bg]")
    elif bg == "color": g.append(f"color=c=0x{bg_color}:s={W}x{H}:r={fps}[bg]")
    else: g.append(f"color=c=black:s={W}x{H}:r={fps}[bg]")
    cur = "bg"
    for name, box, crop in (("g", gm, ""), ("c", p["cam"] if has_cam else None, f"crop={cam},")):
        if not box: continue
        bw, bh = ev(box["w"] * W), ev(box["h"] * H); bx, by = int(round(box["x"] * W)), int(round(box["y"] * H))
        bx, by = max(0, min(W - bw, bx)), max(0, min(H - bh, by)); bw, bh = min(bw, W - bx), min(bh, H - by)
        tag = f"{name}b"
        if name == "c" and box["round"] and disc_mask:
            D = ev(min(bw, bh)); bx += (bw - D) // 2; by += (bh - D) // 2
            g.append(f"[c]{crop}scale={D}:{D}:force_original_aspect_ratio=increase,crop={D}:{D},setsar=1,format=yuv420p[cs];{disc_mask(D, 'cm', fps)};[cs][cm]alphamerge[{tag}]")
            ox = f"{bx}"; oy = f"{by}"
        elif box["fit"]:
            g.append(f"[{name}]{crop}scale={bw}:{bh}:force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1[{tag}]")
            ox = f"{bx}+({bw}-w)/2"; oy = f"{by}+({bh}-h)/2"
        else:
            g.append(f"[{name}]{crop}scale={bw}:{bh}:force_original_aspect_ratio=increase,crop={bw}:{bh},setsar=1[{tag}]")
            ox = f"{bx}"; oy = f"{by}"
        nxt = f"o{len(g)}"
        g.append(f"[{cur}][{tag}]overlay=x='{ox}':y='{oy}':format=auto:shortest=1[{nxt}]"); cur = nxt
    g.append(f"[{cur}]scale={W}:{H},setsar=1[vv]")
    return ";".join(g)


# ================================================================ a voice for your texts
_VOICES = {}


def _ps_run(args, timeout=60, nowin=None):
    try: return subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass"] + args, capture_output=True, text=True,
                              errors="replace", timeout=timeout, **(nowin or {}))
    except Exception: return None


def _ffmpeg_has(ff, name, nowin=None):
    try:
        r = subprocess.run([ff, "-hide_banner", "-filters"], capture_output=True, text=True, errors="replace", timeout=30, **(nowin or {}))
        return bool(re.search(r"\b" + re.escape(name) + r"\b", r.stdout or ""))
    except Exception: return False


def tts_voices(ff="ffmpeg", nowin=None):
    """Names of the voices that can read your text: the Windows voices, or ffmpeg's own test voice elsewhere. [] when there is none."""
    key = (sys.platform, ff)
    if key in _VOICES: return _VOICES[key]
    names = []
    if sys.platform == "win32":
        r = _ps_run(["-Command", "Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).GetInstalledVoices() | "
                                 "Where-Object { $_.Enabled } | ForEach-Object { $_.VoiceInfo.Name }"], 40, nowin)
        names = [x.strip() for x in (r.stdout if r else "").splitlines() if x.strip()][:30]
    elif _ffmpeg_has(ff, "flite", nowin): names = ["Test voice"]
    _VOICES[key] = names
    return names


def tts_make(text, dest, voice="", rate=0, ff="ffmpeg", nowin=None):
    """Read `text` out loud into a .wav file. True when the file exists afterwards. Never raises."""
    text = re.sub(r"\s+", " ", str(text or "")).strip()[:300]
    if not text: return False
    dest = os.path.abspath(str(dest))
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tf = os.path.join(tmp, "t.txt")
            with open(tf, "w", encoding="utf-8") as f: f.write(text)
            if sys.platform == "win32":
                ps1 = os.path.join(tmp, "s.ps1")
                with open(ps1, "w", encoding="utf-8-sig") as f:
                    f.write('param([string]$txt,[string]$out,[string]$voice,[int]$rate)\n'
                            'Add-Type -AssemblyName System.Speech\n$s = New-Object System.Speech.Synthesis.SpeechSynthesizer\n'
                            'if ($voice) { try { $s.SelectVoice($voice) } catch {} }\n$s.Rate = $rate\n$s.SetOutputToWaveFile($out)\n'
                            '$s.Speak([System.IO.File]::ReadAllText($txt, [System.Text.Encoding]::UTF8))\n$s.Dispose()\n')
                _ps_run(["-File", ps1, "-txt", tf, "-out", dest, "-voice", str(voice or ""), "-rate", str(int(max(-5, min(5, rate))))], 90, nowin)
            elif _ffmpeg_has(ff, "flite", nowin):
                subprocess.run([ff, "-y", "-v", "error", "-f", "lavfi", "-i", f"flite=textfile={tf.replace(chr(92), '/').replace(':', chr(92) + ':')}:voice=kal", "-ar", "44100", dest],
                               capture_output=True, text=True, errors="replace", timeout=90, **(nowin or {}))
    except Exception: return False
    return os.path.isfile(dest) and os.path.getsize(dest) > 400


def voiceover_items(o, dur):
    """The texts that should be read out loud: [(text, start second)] - only boxes with 'say' that fit in the clip."""
    out = []
    for b in parse_texts(o.get("text_boxes")):
        win = text_window(b, dur) if b["say"] else None
        if win: out.append((b["t"], win[0]))
    return out


# ================================================================ trim / tidy a finished clip
def probe(ff, path, nowin=None):
    """dict(dur, w, h, audio) of a video, from ffmpeg's own banner."""
    try: t = subprocess.run([ff, "-hide_banner", "-i", str(path)], capture_output=True, text=True, errors="replace", timeout=60, **(nowin or {})).stderr
    except Exception: t = ""
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", t); r = re.search(r"Video:.*?[, ](\d{2,5})x(\d{2,5})", t)
    return dict(dur=int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else 0.0, w=int(r[1]) if r else 0, h=int(r[2]) if r else 0, audio="Audio:" in t)


def find_quiet(path, ff, nowin=None, min_len=.9, db=-32, timeout=120):
    """[(start, end)] of stretches where nobody talks (silence for at least min_len seconds), from ffmpeg's silencedetect."""
    try: r = subprocess.run([ff, "-hide_banner", "-nostats", "-i", str(path), "-vn", "-af", f"silencedetect=noise={db}dB:d={min_len}", "-f", "null", "-"],
                            capture_output=True, text=True, errors="replace", timeout=timeout, **(nowin or {}))
    except Exception: return []
    out, start = [], None
    for line in (r.stderr or "").splitlines():
        m = re.search(r"silence_start: (-?[\d.]+)", line)
        if m: start = max(0.0, float(m[1])); continue
        m = re.search(r"silence_end: (-?[\d.]+)", line)
        if m and start is not None: out.append((start, float(m[1]))); start = None
    return out


def keep_parts(start, end, quiet, pad=.25, min_keep=.4):
    """The pieces of [start, end] that stay when the quiet stretches are cut out (each quiet stretch keeps `pad` seconds of breathing room on both sides)."""
    cuts = sorted((max(start, a + pad), min(end, b - pad)) for a, b in quiet if b - a > 2 * pad + .1)
    cuts = [(a, b) for a, b in cuts if b - a > .1]
    parts, cur = [], start
    for a, b in cuts:
        if a - cur >= min_keep: parts.append((cur, a))
        cur = max(cur, b)
    if end - cur >= min_keep or not parts: parts.append((cur, end))
    return parts


def trim_clip(src, dest, start, end, ff, nowin, venc, cut_quiet=False, fade=0.0, cb=None, run=None):
    """Save [start, end] of a finished clip as a new file (picture and sound re-encoded so the cut is exact). cut_quiet removes the silent stretches,
    fade adds a fade in / out of that many seconds. -> (True, seconds) or (False, reason). `run(args, total, cb, cwd)` runs ffmpeg (the engine's, so Stop works)."""
    info = probe(ff, src, nowin)
    if not info["dur"] or not info["w"]: return False, "I couldn't read that video."
    start = max(0.0, float(start)); end = min(info["dur"], float(end))
    if end - start < .5: return False, "The part you picked is too short."
    parts = [(start, end)]
    if cut_quiet and info["audio"]:
        parts = keep_parts(start, end, find_quiet(src, ff, nowin, .9), .25)
    total = sum(b - a for a, b in parts)
    g = []
    for i, (a, b) in enumerate(parts):
        g.append(f"[0:v]trim={a:.3f}:{b:.3f},setpts=PTS-STARTPTS[v{i}]")
        if info["audio"]: g.append(f"[0:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS,aresample=48000[a{i}]")
    n = len(parts)
    if n > 1: g.append("".join(f"[v{i}]" + (f"[a{i}]" if info["audio"] else "") for i in range(n)) + f"concat=n={n}:v=1:a={1 if info['audio'] else 0}[vc]" + ("[ac]" if info["audio"] else ""))
    else: g.append("[v0]null[vc]"); info["audio"] and g.append("[a0]anull[ac]")
    f = min(float(fade or 0), total / 4)
    g.append("[vc]" + (f"fade=t=in:st=0:d={f:.2f},fade=t=out:st={max(0, total - f):.3f}:d={f:.2f}" if f > 0 else "null") + "[vf]")
    if info["audio"]: g.append("[ac]" + (f"afade=t=in:st=0:d={f:.2f},afade=t=out:st={max(0, total - f):.3f}:d={f:.2f}" if f > 0 else "anull") + "[af]")
    dest = str(dest)
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "g.txt"), "w") as fh: fh.write(";\n".join(g))
        args = ["-i", os.path.abspath(str(src)), _fc_flag(ff, nowin), "g.txt", "-map", "[vf]"] + (["-map", "[af]"] if info["audio"] else []) + \
               list(venc) + ["-pix_fmt", "yuv420p"] + (["-c:a", "aac", "-b:a", "192k"] if info["audio"] else []) + ["-movflags", "+faststart", os.path.abspath(dest)]
        try:
            if run: run(args, total, cb, tmp)
            else: subprocess.run([ff, "-y", "-v", "error"] + args, cwd=tmp, check=True, capture_output=True, errors="replace", timeout=1800, **(nowin or {}))
        except BaseException as e:
            try: os.remove(dest)
            except OSError: pass
            if "Cancelled" in str(e): raise
            return False, "ffmpeg could not make the new clip (" + str(e)[-160:] + ")"
    return (True, total) if os.path.isfile(dest) else (False, "The new clip was not written.")


_FC = {}


def _fc_flag(ff, nowin=None):
    """Newer ffmpeg uses -/filter_complex FILE, older builds -filter_complex_script."""
    if ff in _FC: return _FC[ff]
    try:
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "t.txt"), "w") as f: f.write("[0:v]null[o]")
            r = subprocess.run([ff, "-v", "error", "-f", "lavfi", "-i", "color=d=0.1", "-/filter_complex", "t.txt", "-map", "[o]", "-f", "null", "-"],
                               capture_output=True, cwd=d, timeout=30, **(nowin or {}))
            _FC[ff] = "-/filter_complex" if r.returncode == 0 else "-filter_complex_script"
    except Exception: _FC[ff] = "-filter_complex_script"
    return _FC[ff]


# ================================================================ montage of several clips
TRANSITIONS = {"cut": "Straight cuts", "fade": "Crossfade", "fadeblack": "Fade through black", "slideleft": "Slide", "wipeleft": "Wipe", "circleopen": "Circle open", "dissolve": "Dissolve"}
MAX_MONTAGE = 20


def montage_plan(durs, td):
    """Transition length that fits the shortest clip, and the xfade offsets: -> (td, [offset of each transition], total seconds)."""
    if not durs: return 0.0, [], 0.0
    td = max(0.0, min(td, min(durs) / 3.0)) if len(durs) > 1 else 0.0
    offs, acc = [], 0.0
    for d in durs[:-1]:
        acc += d - td; offs.append(acc)
    return td, offs, sum(durs) - td * (len(durs) - 1)


def make_montage(clips, dest, ff, nowin, venc, transition="fade", td=.5, title="", font_file="", cb=None, run=None, fps=30):
    """Join finished clips into one video, with a transition between them and an optional title for the first 2.5 seconds. Clips of another shape
    are fitted into the first clip's frame (with black bars). -> (True, seconds) or (False, reason)."""
    clips = [str(c) for c in clips if os.path.isfile(str(c))][:MAX_MONTAGE]
    if len(clips) < 2: return False, "Pick at least two clips."
    infos = [probe(ff, c, nowin) for c in clips]
    if any(not i["dur"] or not i["w"] for i in infos): return False, "One of the clips couldn't be read."
    W, H = infos[0]["w"] // 2 * 2, infos[0]["h"] // 2 * 2
    durs = [i["dur"] for i in infos]
    cut = transition not in TRANSITIONS or transition == "cut"
    td, offs, total = montage_plan(durs, 0.0 if cut else td)
    g, FM = [], "aformat=sample_rates=48000:sample_fmts=fltp:channel_layouts=stereo"
    for i, (c, inf) in enumerate(zip(clips, infos)):
        g.append(f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps={fps},format=yuv420p,setpts=PTS-STARTPTS[v{i}]")
        if inf["audio"]: g.append(f"[{i}:a]aresample=48000,{FM},asetpts=PTS-STARTPTS[a{i}]")
        else: g.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={inf['dur']:.3f},asetpts=PTS-STARTPTS,{FM}[a{i}]")
    n = len(clips)
    if cut:
        g.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[vm][am]")
    else:
        vcur, acur = "v0", "a0"
        for i in range(1, n):
            g.append(f"[{vcur}][v{i}]xfade=transition={transition}:duration={td:.3f}:offset={offs[i - 1]:.3f}[xv{i}]"); vcur = f"xv{i}"
            g.append(f"[{acur}][a{i}]acrossfade=d={td:.3f}:c1=tri:c2=tri[xa{i}]"); acur = f"xa{i}"
        g.append(f"[{vcur}]null[vm]"); g.append(f"[{acur}]anull[am]")
    title = re.sub(r"\s+", " ", re.sub(r"[\r\n]", " ", str(title or ""))).strip()[:60]
    with tempfile.TemporaryDirectory() as tmp:
        if title and font_file and os.path.isfile(font_file):
            shutil.copy(font_file, os.path.join(tmp, "f.ttf"))
            with open(os.path.join(tmp, "t.txt"), "w", encoding="utf-8") as f: f.write(title)
            fs = max(28, int(min(W, H) * .075))
            g.append(f"[vm]drawtext=fontfile=f.ttf:textfile=t.txt:expansion=none:fontsize={fs}:fontcolor=white:borderw={max(2, fs // 14)}:bordercolor=black@0.7:"
                     f"x=(w-text_w)/2:y=h*.12:alpha='if(lt(t,2.1),1,max(0,1-(t-2.1)/0.4))':enable='lt(t,2.5)'[vo]")
        else: g.append("[vm]null[vo]")
        with open(os.path.join(tmp, "g.txt"), "w") as fh: fh.write(";\n".join(g))
        args = [x for c in clips for x in ("-i", os.path.abspath(c))] + [_fc_flag(ff, nowin), "g.txt", "-map", "[vo]", "-map", "[am]", "-r", str(fps)] + list(venc) + \
               ["-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", os.path.abspath(str(dest))]
        try:
            if run: run(args, total, cb, tmp)
            else: subprocess.run([ff, "-y", "-v", "error"] + args, cwd=tmp, check=True, capture_output=True, errors="replace", timeout=3600, **(nowin or {}))
        except BaseException as e:
            try: os.remove(str(dest))
            except OSError: pass
            if "Cancelled" in str(e): raise
            return False, "ffmpeg could not join the clips (" + str(e)[-160:] + ")"
    return (True, total) if os.path.isfile(str(dest)) else (False, "The montage was not written.")


# ================================================================ post planner
PLAN_PLATFORMS = {
    "tiktok": ("TikTok", "https://www.tiktok.com/upload"),
    "youtube": ("YouTube Shorts", "https://studio.youtube.com/"),
    "instagram": ("Instagram Reels", "https://www.instagram.com/"),
    "x": ("X", "https://x.com/compose/post"),
}
# Evergreen suggestions (local time of your audience) - general habits of short-video viewers, NOT live data from the apps.
BEST_TIMES = {
    "tiktok": ("Weekdays 6 - 10 PM and weekend afternoons", [(19, 0), (21, 0), (15, 0)]),
    "youtube": ("Weekdays 3 - 6 PM, weekends 9 AM - noon", [(16, 0), (17, 0), (10, 0)]),
    "instagram": ("Weekdays 11 AM - 1 PM and 7 - 9 PM", [(12, 0), (19, 30), (20, 30)]),
    "x": ("Weekdays 8 - 10 AM and 6 - 9 PM", [(9, 0), (18, 30), (20, 0)]),
}
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def parse_clock(s):
    """'7pm', '19:30', '7:30 pm' -> (hour, minute) or None."""
    m = re.fullmatch(r"\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm|a|p)?\s*", str(s).lower())
    if not m: return None
    h, mi, ap = int(m[1]), int(m[2] or 0), m[3]
    if mi > 59: return None
    if ap:
        if not 1 <= h <= 12: return None
        h = h % 12 + (12 if ap.startswith("p") else 0)
    elif h > 23: return None
    return h, mi


def parse_when(text, now=None):
    """When to post: '2026-10-14 19:30', 'tomorrow 7pm', 'fri 8pm', 'today 21:00', '19:30' (today, or tomorrow when that time has passed). -> datetime or None."""
    now = now or datetime.datetime.now()
    s = re.sub(r"\s+", " ", str(text or "").strip().lower())
    if not s: return None
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})[ t]+(.+)", s)
    if m:
        c = parse_clock(m[4])
        try: return datetime.datetime(int(m[1]), int(m[2]), int(m[3]), c[0], c[1]) if c else None
        except ValueError: return None
    m = re.fullmatch(r"(today|tomorrow|tmr|mon|tue|wed|thu|fri|sat|sun)[a-z]*\s+(.+)", s)
    if m:
        c = parse_clock(m[2])
        if not c: return None
        word = m[1]
        if word == "today": day = now.date()
        elif word in ("tomorrow", "tmr"): day = now.date() + datetime.timedelta(days=1)
        else:
            ahead = (WEEKDAYS.index(word) - now.weekday()) % 7
            day = now.date() + datetime.timedelta(days=ahead)
        t = datetime.datetime(day.year, day.month, day.day, c[0], c[1])
        if t <= now and word in WEEKDAYS: t += datetime.timedelta(days=7)
        return t
    c = parse_clock(s)
    if c:
        t = now.replace(hour=c[0], minute=c[1], second=0, microsecond=0)
        return t if t > now else t + datetime.timedelta(days=1)
    return None


def suggest_times(platform, now=None, n=3):
    """The next few good times to post on a platform (from BEST_TIMES): [datetime]."""
    now = now or datetime.datetime.now(); out = []
    slots = BEST_TIMES.get(platform, BEST_TIMES["tiktok"])[1]
    for day in range(0, 4):
        d = now.date() + datetime.timedelta(days=day)
        for h, m in slots:
            t = datetime.datetime(d.year, d.month, d.day, h, m)
            if t > now + datetime.timedelta(minutes=5): out.append(t)
    return sorted(out)[:n]


def clean_plan(raw):
    """Whatever the settings file holds -> a list of valid plan entries (at most 200)."""
    out = []
    for d in raw if isinstance(raw, list) else []:
        if not isinstance(d, dict): continue
        try: when = datetime.datetime.fromisoformat(str(d.get("when")))
        except (TypeError, ValueError): continue
        plat = d.get("platform") if d.get("platform") in PLAN_PLATFORMS else "tiktok"
        out.append(dict(id=str(d.get("id") or f"{when.timestamp():.0f}-{len(out)}")[:40], clip=str(d.get("clip", ""))[:500], platform=plat, when=when.isoformat(timespec="minutes"),
                        note=str(d.get("note", ""))[:200], done=bool(d.get("done")), shown=bool(d.get("shown"))))
        if len(out) >= 200: break
    return sorted(out, key=lambda x: x["when"])


def plan_add(plan, clip, platform, when, note=""):
    item = dict(id=f"{datetime.datetime.now().timestamp():.3f}-{len(plan)}", clip=str(clip), platform=platform if platform in PLAN_PLATFORMS else "tiktok",
                when=when.isoformat(timespec="minutes"), note=str(note)[:200], done=False, shown=False)
    return clean_plan(list(plan) + [item])


def plan_due(plan, now=None):
    """Entries whose time has come and that were not marked done or already announced."""
    now = now or datetime.datetime.now()
    return [d for d in plan if not d["done"] and not d["shown"] and datetime.datetime.fromisoformat(d["when"]) <= now]


def plan_label(d, now=None):
    now = now or datetime.datetime.now(); t = datetime.datetime.fromisoformat(d["when"])
    day = "today" if t.date() == now.date() else "tomorrow" if t.date() == now.date() + datetime.timedelta(days=1) else t.strftime("%a %d %b")
    return f"{day} {t.strftime('%H:%M')}"
