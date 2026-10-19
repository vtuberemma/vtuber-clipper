"""VTuber Clipper 2.3 - picture, sound and file extras (features 12-26).
Pieces of ffmpeg filter text for the renderer, and small jobs done to a FINISHED clip (soft subtitles, file info, a GIF, an MP3, cover pictures).
Like vcmore.py, a helper that cannot run returns "" / 0 / False instead of raising, so an extra can never stop the video itself."""
import os, re, shutil, subprocess, tempfile

import numpy as np

import vcmore, vcsmart, vc23

_run, _probe, _kw, _swap = vcmore._run, vcmore._probe, vcmore._kw, vcmore._swap


# ================================================================ 12  background blur strength     13  background brightness
def blur_params(name, W, H):
    """(width, height, box radius, passes) of the tiny copy that is blurred and stretched back as the background. 'normal' is exactly what 2.2 did."""
    f = vc23.BG_BLURS.get(name, vc23.BG_BLURS["normal"])[1]
    sw = max(2, int(W // 10 * 2 / f) // 2 * 2); sh = max(2, int(H // 10 * 2 / f) // 2 * 2)
    rad, pas = {.5: (3, 1), 1.0: (5, 2), 1.8: (8, 3), 3.0: (12, 3)}.get(f, (5, 2))
    rad = max(1, min(rad, min(sw, sh) // 4))              # ffmpeg refuses a radius bigger than a quarter of the small picture (its colour planes are half size)
    return sw, sh, rad, pas


def dim_filter(pct):
    """Filter text that darkens (-50..-1) or brightens (1..50) the background; '' for 0."""
    try: p = max(-50, min(50, int(float(pct))))
    except (TypeError, ValueError, OverflowError): p = 0
    if not p: return ""
    return f"lutyuv=y='clip(val*{1 + p / 100.0:.2f},16,235)'"


def blur_chain(name, W, H, dim=0):
    """The whole background chain after the cropped copy: scale down, blur, (dim), scale up."""
    sw, sh, rad, pas = blur_params(name, W, H); d = dim_filter(dim)
    return f"scale={sw}:{sh},boxblur={rad}:{pas}" + (f",{d}" if d else "") + f",scale={W}:{H}"


# ================================================================ 14  noise gate     15  de-esser
_FILT, _ENC = {}, {}


def _listing(ff, what, nowin):
    key = (ff, what)
    if key not in _FILT:
        try: _FILT[key] = subprocess.run([ff, "-hide_banner", "-v", "error", what], capture_output=True, errors="replace", timeout=60, **_kw(nowin)).stdout or ""
        except Exception: _FILT[key] = ""
    return _FILT[key]


def have_filter(ff, name, nowin=None):
    return bool(re.search(r"^\s*[TSC.]{2,3}\s+" + re.escape(name) + r"\s", _listing(ff, "-filters", nowin), re.M))


def have_encoder(ff, name, nowin=None):
    return bool(re.search(r"^\s*[VAS.][A-Z.]{5}\s+" + re.escape(name) + r"\s", _listing(ff, "-encoders", nowin), re.M))


GATE = "agate=threshold=0.015:ratio=4:attack=8:release=180:range=0.06"
DEESS = "deesser=i=0.45:m=0.55:f=0.5"
DEESS_FALLBACK = "equalizer=f=7500:t=q:w=2:g=-4"


def audio_gate(o, ff=None, nowin=None):
    """Filter text (starts with a comma, or empty) for the noise gate and the de-esser. The de-esser filter is missing from very old ffmpeg builds; then a gentle dip around 7.5 kHz does the job."""
    out = ""
    if o.get("gate"): out += "," + GATE
    if o.get("deess"): out += "," + (DEESS if (ff is None or have_filter(ff, "deesser", nowin)) else DEESS_FALLBACK)
    return out


# ================================================================ 16  progress bar: edge and thickness
def bar_geometry(H, RH, pos="bottom", thick=14):
    """(y, height) in pixels of the progress bar on a picture H pixels tall, whose caption reference canvas is RH tall."""
    h = max(6, round(float(thick) * H / RH)); h = min(h, max(6, H // 8))
    return (0 if pos == "top" else H - h), h


# ================================================================ 17  colour the feeling words in the captions
FEEL_COLORS = dict(laugh="FFD54D", scream="FF3D5A", fail="B0B0B0", win="6BE06B", scare="9B59FF", cute="FF8AD8", rage="FF6B3D", hype="FFA500", chaos="E040FB")


def feeling_of(tok):
    """Which feeling a cleaned word carries ('laugh', 'scream', 'fail', 'win', 'scare', 'cute', 'rage', 'hype', 'chaos') or ''."""
    t = vcsmart.clean(tok)
    if not t: return ""
    if vcsmart.is_laugh(t): return "laugh"
    if vcsmart.is_scream(t): return "scream"
    try: uv = vcsmart.user_vocab()
    except Exception: uv = {}
    for k, ws in (("fail", vcsmart.FAIL_W), ("win", vcsmart.WIN_W), ("scare", vcsmart.SCARE_W), ("cute", vcsmart.CUTE_W), ("rage", vcsmart.RAGE_W), ("hype", vcsmart.HYPE_PLUS), ("chaos", vcsmart.CHAOS_W)):
        if t in ws or t in uv.get(k, ()): return k
    for k in ("laugh", "scream"):
        if t in uv.get(k, ()): return k
    return ""


def dominant_feeling(words, min_hits=2):
    """The feeling that most words of a clip carry ('' when fewer than `min_hits` words carry any). Used to pick music by mood."""
    cnt = {}
    for w in words or []:
        k = feeling_of(str(w.get("w", "")))
        if k: cnt[k] = cnt.get(k, 0) + 1
    if not cnt: return ""
    k, n = max(cnt.items(), key=lambda x: (x[1], x[0]))
    return k if n >= min_hits else ""


def feel_wrap(word_text, tok):
    """The word with an ASS colour change around it when it carries a feeling, else the word as it was."""
    k = feeling_of(tok)
    if not k: return word_text
    c = FEEL_COLORS[k]; bgr = c[4:6] + c[2:4] + c[0:2]
    return "{\\1c&H" + bgr + "&}" + word_text + "{\\1c}"


# ================================================================ 18  logo see-through level
def logo_alpha_filter(pct):
    try: p = max(20, min(100, int(float(pct))))
    except (TypeError, ValueError, OverflowError): p = 92
    return f"colorchannelmixer=aa={p / 100:.2f}"


# ================================================================ 19  music by mood
MOODS = {"gameplay": ("hype", "action", "energetic", "intense", "gaming"), "reaction": ("funny", "hype", "chaos", "comedy"), "talking": ("chill", "calm", "relax", "lofi"),
         "story": ("chill", "calm", "story", "sad", "emotional"), "singing": ()}
FEELING_MOODS = {"scare": ("spooky", "scary", "horror", "tense"), "cute": ("cute", "happy", "kawaii", "sweet"), "win": ("hype", "epic", "victory")}


def mood_folders(spec):
    """{lower case folder name: path} of the sub-folders of a music folder."""
    try:
        if not os.path.isdir(spec): return {}
        return {d.lower(): os.path.join(spec, d) for d in sorted(os.listdir(spec)) if os.path.isdir(os.path.join(spec, d))}
    except OSError: return {}


def mood_pick(spec, kind, pick_fn, feeling="", exclude=()):
    """Choose a track by the kind of moment. Returns None (no mood folder fits: pick as usual), "" (no music on purpose: a song is already playing) or a track path.
    A music folder can hold sub-folders named hype, funny, chill, sad, spooky, cute ... ; the clip kind (and a scare / cute / win feeling) picks the sub-folder."""
    if kind == "singing": return ""
    sub = mood_folders(str(spec or ""))
    if not sub: return None
    for name in (FEELING_MOODS.get(feeling, ()) + MOODS.get(kind, ())):
        if name in sub:
            t = pick_fn(sub[name], exclude)
            if t: return t
    return None


# ================================================================ 20-24  jobs on a finished clip
def _tmp_for(path, suffix):
    return path + suffix


def add_soft_subs(mp4, srt, ff, nowin, lang="eng"):
    """20: put the subtitles INSIDE the mp4 as a switchable track (viewers and uploaders can turn them on or off). True when done."""
    if not (os.path.isfile(mp4) and os.path.isfile(srt)) or os.path.getsize(srt) < 10: return False
    tmp = _tmp_for(mp4, ".ss.mp4")
    ok, _ = _run(ff, ["-i", os.path.abspath(mp4), "-i", os.path.abspath(srt), "-map", "0:v", "-map", "0:a?", "-map", "1:0", "-c:v", "copy", "-c:a", "copy", "-c:s", "mov_text",
                      f"-metadata:s:s:0", f"language={lang}", "-movflags", "+faststart", tmp], nowin)
    if not ok or not os.path.isfile(tmp):
        try: os.remove(tmp)
        except OSError: pass
        return False
    return _swap(tmp, mp4)


def _clean_meta(v, n=200):
    return re.sub(r"[\r\n\x00]+", " ", str(v or "")).strip()[:n]


def write_tags(mp4, tags, ff, nowin):
    """21: title, artist (your channel), comment and genre (the game) in the file's own info. `tags` = {title, artist, comment, genre, date}. True when done."""
    if not os.path.isfile(mp4): return False
    keys = [(k, _clean_meta(tags.get(k))) for k in ("title", "artist", "comment", "genre", "date") if _clean_meta(tags.get(k))]
    if not keys: return False
    tmp = _tmp_for(mp4, ".mt.mp4")
    args = ["-i", os.path.abspath(mp4), "-map", "0", "-c", "copy", "-fflags", "+bitexact", "-flags:v", "+bitexact", "-flags:a", "+bitexact"]      # bitexact: ffmpeg does not add its own 'encoder' note
    for k, v in keys: args += ["-metadata", f"{k}={v}"]
    ok, _ = _run(ff, args + ["-movflags", "+faststart", tmp], nowin)
    if not ok or not os.path.isfile(tmp):
        try: os.remove(tmp)
        except OSError: pass
        return False
    return _swap(tmp, mp4)


def scrub(mp4, ff, nowin):
    """22: remove every piece of hidden info (the title of the stream, the software name, chapters, creation time...) from the file. True when done."""
    if not os.path.isfile(mp4): return False
    tmp = _tmp_for(mp4, ".sc.mp4")
    ok, _ = _run(ff, ["-i", os.path.abspath(mp4), "-map", "0", "-map_metadata", "-1", "-map_chapters", "-1", "-c", "copy", "-fflags", "+bitexact", "-flags:v", "+bitexact",
                      "-flags:a", "+bitexact", "-movflags", "+faststart+use_metadata_tags", tmp], nowin)
    if not ok or not os.path.isfile(tmp):
        try: os.remove(tmp)
        except OSError: pass
        return False
    return _swap(tmp, mp4)


def file_tags(mp4, ff, nowin):
    """{lower-case key: value} of the global info of a file (used by the tests and the privacy check)."""
    try:
        r = subprocess.run([ff, "-hide_banner", "-i", mp4], capture_output=True, errors="replace", timeout=60, **_kw(nowin)).stderr or ""
    except Exception: return {}
    head = r.split("Duration:")[0]
    out = {}
    for m in re.finditer(r"^\s{4}([A-Za-z_]+)\s*:\s*(.*)$", head, re.M): out[m.group(1).lower()] = m.group(2).strip()
    return out


def export_audio(mp4, ff, nowin, dest=None):
    """23: the sound of a clip as an MP3 (or an M4A when this ffmpeg has no MP3 encoder). Returns the new path or ''."""
    if not os.path.isfile(mp4): return ""
    mp3 = have_encoder(ff, "libmp3lame", nowin)
    dest = dest or (os.path.splitext(mp4)[0] + (".mp3" if mp3 else ".m4a"))
    if not _probe(ff, mp4, nowin)["audio"]: return ""
    args = ["-i", os.path.abspath(mp4), "-vn", "-map", "0:a:0"] + (["-c:a", "libmp3lame", "-q:a", "2"] if mp3 else ["-c:a", "aac", "-b:a", "192k"])
    ok, _ = _run(ff, args + [os.path.abspath(dest)], nowin)
    if not ok or not os.path.isfile(dest):
        try: os.remove(dest)
        except OSError: pass
        return ""
    return dest


def make_gif(mp4, t, ff, nowin, dest=None, secs=5.0, width=0, fps=12, max_mb=8.0):
    """24: a looping GIF of `secs` seconds around the biggest moment (second `t`). It is made smaller until it is under `max_mb`. Returns the path or ''."""
    inf = _probe(ff, mp4, nowin)
    if not os.path.isfile(mp4) or inf["dur"] < 1.5: return ""
    dest = dest or (os.path.splitext(mp4)[0] + ".gif")
    secs = min(float(secs), inf["dur"]); a = max(0.0, min(float(t) - secs * .4, inf["dur"] - secs))
    tall = inf["h"] > inf["w"]; width = int(width) or (360 if tall else 480)
    for _ in range(4):
        fc = (f"[0:v]fps={fps},scale={width}:-2:flags=lanczos,split[x][y];[x]palettegen=stats_mode=diff[p];[y][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle[o]")
        ok, _ = _run(ff, ["-ss", f"{a:.2f}", "-t", f"{secs:.2f}", "-i", os.path.abspath(mp4), "-filter_complex", fc, "-map", "[o]", "-loop", "0", os.path.abspath(dest)], nowin, 600)
        if not ok or not os.path.isfile(dest): break
        if os.path.getsize(dest) <= max_mb * 1e6 or width <= 200: return dest
        width = max(200, int(width * .75) // 2 * 2)
    try: os.remove(dest)
    except OSError: pass
    return ""


# ================================================================ 25  three cover choices     26  sharpest-frame covers
def sharpness(gray):
    """How much fine detail a grey picture (2-D array) has: the variance of its Laplacian. Blurred, faded or mid-transition frames score low."""
    g = np.asarray(gray, np.float32)
    if g.ndim != 2 or min(g.shape) < 5: return 0.0
    lap = 4 * g[1:-1, 1:-1] - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:]
    return float(lap.var())


def gray_frames(mp4, a, b, ff, nowin, fps=5.0, size=(192, 108)):
    """[(time, 2-D grey array)] sampled between seconds a and b (small, for measuring only)."""
    w, h = size
    try:
        r = subprocess.run([ff, "-v", "error", "-ss", f"{max(0.0, a):.3f}", "-t", f"{max(.2, b - a):.3f}", "-i", os.path.abspath(mp4), "-vf", f"fps={fps},scale={w}:{h},format=gray",
                            "-f", "rawvideo", "-"], capture_output=True, timeout=300, **_kw(nowin))
    except Exception: return []
    buf = r.stdout or b""; k = w * h; n = len(buf) // k
    return [(max(0.0, a) + i / fps, np.frombuffer(buf[i * k:(i + 1) * k], np.uint8).reshape(h, w)) for i in range(n)]


def best_time(mp4, t, ff, nowin, span=1.0):
    """The second near `t` (within +-span) whose frame is sharpest. Falls back to `t` when the frames cannot be read."""
    inf = _probe(ff, mp4, nowin); D = inf["dur"]
    if D <= 0: return float(t)
    size = (108, 192) if inf["h"] > inf["w"] else (192, 108)
    fr = gray_frames(mp4, max(0.0, t - span), min(D - .1, t + span), ff, nowin, 8.0, size)
    if not fr: return float(t)
    return float(max(fr, key=lambda x: (round(sharpness(x[1]), 1), -abs(x[0] - t)))[0])          # on a tie (a flat picture) the frame closest to the moment wins


def cover_candidates(mp4, times, ff, nowin, n=3, min_gap=1.5):
    """Up to `n` second marks for cover pictures: the sharpest frame near each of the given moments, then evenly spread seconds to fill up. Best first, at least `min_gap` apart."""
    inf = _probe(ff, mp4, nowin); D = inf["dur"]
    if D < 2: return []
    out, seen = [], []
    for t in list(times) + [D * .25, D * .5, D * .75, D * .15, D * .9]:
        if len(out) >= n: break
        if not (.4 <= t <= D - .4): continue
        bt = min(max(best_time(mp4, t, ff, nowin, min(1.0, D / 6)), .2), D - .2)
        if all(abs(bt - x) >= min_gap for x in out): out.append(round(bt, 2))
    return out
