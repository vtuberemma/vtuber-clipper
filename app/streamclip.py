#!/usr/bin/env python3
"""streamclip engine: transcription, highlight detection, effects, rendering, hardware/ETA."""
import ctypes, hashlib, json, math, os, platform, random, re, shutil, subprocess, tempfile, threading
from pathlib import Path
import numpy as np

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
FF = "ffmpeg"
CANCEL, PROCS = threading.Event(), set()
PROGRESS = lambda frac, label="": None          # the app replaces this
PLAN, HW, USE_GPU_ENC, GPU_ENC_FAILED = {}, None, True, False
# output settings (Settings -> Output). The app writes into OUT before every job.
QUALITY_MBPS = {"Extreme": 135, "High": 80, "Medium": 50, "Low": 25}
RESOLUTIONS = {"720p": 720, "1080p": 1080, "1440p": 1440, "4K": 2160}
FRAMERATES = (25, 30, 60)
OUT = dict(mbps=80, res=1080, fps=30)
HYPE = {"wtf", "omg", "omfg", "insane", "crazy", "bruh", "bro", "nah", "dude", "yooo", "ahh", "nooo", "noo", "pog", "eep",
        "holy", "gg", "clutch", "dying", "help", "screaming",
        "やばい", "やばっ", "うわ", "うわー", "えー", "まじ", "まじで", "すごい", "うそ", "嘘", "やった", "きゃー", "ぎゃー", "最高",     # Japanese
        "대박", "헐", "미쳤다",                                                                                                  # Korean
        "dios", "increible", "wow"}
END_P = ".?!。！？"                                  # characters that end a sentence (English + Japanese / Chinese full-width)
APP_DIR = os.path.dirname(os.path.abspath(__file__))
NOWIN = dict(stdin=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
PROFILES = {
    "gameplay": dict(w_loud=1.0, w_peak=.5, w_onset=.9, w_excl=.7, dead=.3, w_speech=.3, w_hype=2.5, gap=1.5, short_min=25, short_max=45, layout="stack"),
    "story": dict(w_loud=.3, w_peak=.1, w_onset=.3, w_excl=1.0, dead=1.0, w_speech=1.2, w_hype=1.0, gap=1.2, short_min=40, short_max=75, layout="fill"),
    # a mix of both: talking that builds into a reaction (the most common VTuber clip)
    "mix": dict(w_loud=.65, w_peak=.3, w_onset=.65, w_excl=.9, dead=.65, w_speech=.8, w_hype=1.8, gap=1.3, short_min=30, short_max=55, layout="stack"),
}
# long-form recap styles: how moments are scored, how long each one is (final length after trimming), and how they are chosen
RECIPES = {
    "highlight": dict(title="Highlight video", w_loud=1.0, w_peak=.7, w_onset=1.0, w_excl=.8, dead=.4, w_speech=.2, w_hype=2.5,
                      lo=15, hi=35, spread=False, snap=False, gap_floor=None, fx=dict(pan=0, cutzoom=1)),
    "story": dict(title="Story video", w_loud=.3, w_peak=.1, w_onset=.3, w_excl=1.0, dead=1.0, w_speech=1.2, w_hype=1.0,
                  lo=45, hi=100, spread=True, snap=True, gap_floor=None, fx=dict(pan=1, cutzoom=0)),
    "gameplay": dict(title="Gameplay video", w_loud=1.0, w_peak=.6, w_onset=1.0, w_excl=.3, dead=0.0, w_speech=0.0, w_hype=1.0,
                     lo=30, hi=70, spread=False, snap=False, gap_floor=3.0, fx=dict(pan=0, cutzoom=1)),
    "mix": dict(title="Mixed recap", w_loud=.65, w_peak=.4, w_onset=.7, w_excl=.8, dead=.5, w_speech=.7, w_hype=1.8,
                lo=30, hi=80, spread=True, snap=True, gap_floor=2.0, fx=dict(pan=1, cutzoom=1)),
}
# profile used by the Best Moments scanner (a balance of gameplay and talking)
MOMENTS = dict(w_loud=1.0, w_peak=.6, w_onset=.9, w_excl=.8, dead=.5, w_speech=.5, w_hype=2.5)
# default shorts-effect sets per style (the app lets the user toggle each one)
_NEW_OFF = dict(lines=0, ring=0, hearts=0, sparkle=0, tilt=0, glow=0, vhs=0, frame=0, pushin=0, bw=0, marks=0, confetti=0, petals=0)
FX = {
    "gameplay": dict(zoom=1, shake=1, flash=1, sfx=1, blur=1, pan=0, pop=1, bar=1, hook=1, cutzoom=1, glitch=1, whoosh=1, zoomout=1,
                     **{**_NEW_OFF, "lines": 1, "ring": 1, "tilt": 1}),
    "story": dict(zoom=1, shake=0, flash=0, sfx=0, blur=0, pan=1, pop=1, bar=1, hook=1, cutzoom=1, glitch=0, whoosh=0, zoomout=1,
                  **{**_NEW_OFF, "hearts": 1, "sparkle": 1, "glow": 1, "pushin": 1}),
}
FX["mix"] = dict(FX["gameplay"], shake=0, flash=0, glitch=0, whoosh=0, ring=0, lines=0, tilt=0, hearts=1, sparkle=1, pan=1)
clean = lambda w: re.sub(r"[^\w']", "", w.lower().replace("_", ""))
ends_in = lambda w, chars: bool(w) and w[-1] in chars


# ---------------- v1.2 options ----------------
# aspect ratio -> (ratio w, ratio h); the Resolution setting is the SHORT side (1080p: 1080x1920, 1080x1350, 1080x1080, 1920x1080)
ASPECTS = {"9:16": (9, 16), "4:5": (4, 5), "1:1": (1, 1), "16:9": (16, 9)}
REF = {"9:16": (1080, 1920), "4:5": (1080, 1350), "1:1": (1080, 1080), "16:9": (1920, 1080)}   # caption/overlay reference canvas per aspect
LOW_MARGIN = {"9:16": .29, "4:5": .17, "1:1": .12, "16:9": .085}                                  # bottom caption margin (fraction of height)
HIGH_MARGIN = {"9:16": .27, "4:5": .22, "1:1": .20, "16:9": .12}
# caption fonts: label -> (family name as libass sees it, file in app/fonts or None for a Windows font, size multiplier, faux-bold)
FONTS = {
    "Arial Black": ("Arial Black", None, 1.0, 1), "Impact": ("Impact", None, 1.08, 0), "Comic Sans": ("Comic Sans MS", None, .95, 1),
    "Bangers": ("Bangers", "Bangers-Regular.ttf", 1.2, 0), "Chewy": ("Chewy", "Chewy-Regular.ttf", 1.1, 0),
    "Titan One": ("Titan One", "TitanOne-Regular.ttf", .95, 0), "Luckiest Guy": ("Luckiest Guy", "LuckiestGuy-Regular.ttf", 1.0, 0),
    "Sniglet": ("Sniglet ExtraBold", "Sniglet-ExtraBold.ttf", 1.0, 0), "Poppins": ("Poppins ExtraBold", "Poppins-ExtraBold.ttf", .95, 0),
    "Mochiy Pop (JP)": ("Mochiy Pop One", "MochiyPopOne-Regular.ttf", .92, 0), "Pacifico": ("Pacifico", "Pacifico-Regular.ttf", 1.0, 0),
    "Pixel (retro)": ("Press Start 2P", "PressStart2P-Regular.ttf", .6, 0), "Creepy": ("Creepster", "Creepster-Regular.ttf", 1.15, 0),
}
CAPTION_STYLES = {"pop": "Pop — one word at a time", "karaoke": "Karaoke — phrase, active word lit", "box": "Sticker — words on a colour box",
                  "bounce": "Bounce — wobbly one-by-one", "line": "Subtitle — calm full lines", "type": "Typewriter — letters type out"}
CAP_POS = ("low", "mid", "high")
SFX_DIR = os.path.join(APP_DIR, "sfx")
AUDIO_EXT = (".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac", ".opus")


def _load_json(p):
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except Exception: return {}


# sound packs made from real recordings (app/sfx, CC0); a pack whose files are missing is simply not offered
SFX_FILE_PACKS = {k: v for k, v in (_load_json(os.path.join(SFX_DIR, "index.json")).get("packs") or {}).items()
                  if isinstance(v, dict) and v.get("hits") and all(os.path.isfile(os.path.join(SFX_DIR, h["file"])) for h in v["hits"])}
SFX_PACKS = ("boom", "cute", "anime", "retro") + tuple(SFX_FILE_PACKS)
SFX_ABOUT = {"boom": ("Boom", "deep bass boom"), "cute": ("Cute", "bright pop and sparkle"), "anime": ("Anime", "boom with a shiny ring"),
             "retro": ("Retro 8-bit", "game-console arpeggio")}
# speech language shown in the app -> faster-whisper code ("" = detect automatically)
LANGS = {"Auto-detect": "", "English": "en", "Japanese": "ja", "Korean": "ko", "Spanish": "es", "Portuguese": "pt", "French": "fr", "German": "de",
         "Indonesian": "id", "Filipino": "tl", "Russian": "ru", "Chinese": "zh", "Italian": "it", "Thai": "th", "Vietnamese": "vi"}
# where each app covers the picture on a phone (fractions of the screen): keep logos, @names and the cam bubble out of them
PLATFORMS = {"any": dict(label="Anywhere (no safe zone)", bottom=0.0, right=0.0, top=0.0),
             "tiktok": dict(label="TikTok", bottom=.21, right=.13, top=.08),
             "shorts": dict(label="YouTube Shorts", bottom=.19, right=.12, top=.08),
             "reels": dict(label="Instagram Reels", bottom=.23, right=.12, top=.12)}
BG_STYLES = {"blur": "Blurred copy of the game", "color": "One colour", "image": "My own image"}
SPEECH_SPEEDS = {"fast": "Fast", "balanced": "Balanced", "best": "Most accurate"}
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".vtuberclipper_cache")
SPEECH_SPEED, PARALLEL = "balanced", 0          # set by the app (Settings -> Performance); PARALLEL 0 = choose automatically
HOOK_MODES = ("smart", "words", "mine")      # how the title shown over the first seconds of a short is made
OPTS = dict(
    cap_style="pop", cap_font="Arial Black", cap_size=100, cap_pos="low", cap_text="ffffff", cap_hi="ff3d9a", cap_edge="000000", cap_emph=False, cap_emoji=False, review=False, cover=True, swears=False, fresh=True, hook_mode="smart", hook_text="",
    aspect="9:16", sfx_pack="boom", pip_pos="br",
    logo="", logo_pos="tr", logo_size=16, handle="", handle_pos="bl",
    music="", music_vol=12, duck=True,
    lang="", translate=False, hint="", fixes="",
    post_kit=True, srt=False, channel="", game="", tags="",
    platform="any", voice_clean=False, fix_lag=True, intro="", outro="", cta="", stickers="", sticker_size=18, filler="",
    bg_style="blur", bg_color="1b1230", bg_image="",
    emotes=False, emote_level="normal", emote_size=32, emote_pos="auto", emote_burst=False, emote_recap=True, emote_cover=False, emote_review=False,
    # 2.0: picture, overlays, voice, extra files
    color_look="none", crisp="off", auto_light=False, auto_crop=False, vignette=False, fade="off", hide_box="", hide_style="blur",
    lower_name="", lower_sub="", part_badge=False, follow_text="", buddy=False, buddy_feeling="cool", buddy_pos="tl", buddy_size=22,
    emote_fx=False, emote_sound=False, voice_fx="none", voice_eq="natural", bleep_sound="beep", loudness="-14",
    transcript=False, name_pattern="{video}_short{n}", vod_folder=False,
    # 2.1: words on screen, Like / Follow buttons, your own layout, a voice that reads your words
    text_boxes="", callouts="", custom_layout="", tts_voice="", tts_rate=0)
try:                                                        # 2.2: smarter finding, picture / sound / caption extras (see vcmore.DEFAULTS)
    import vcmore as _vm
    OPTS.update(_vm.DEFAULTS)
except Exception: _vm = None
try:                                                        # 2.3: more clues, clean edges, privacy, checks, files (see vc23.DEFAULTS)
    import vc23 as _v23
    OPTS.update(_v23.DEFAULTS)
except Exception: _v23 = None


# 2.0 "Polish" options: they shape one finished video (picture, overlays, voice). X videos get them; Recaps get the picture and voice ones only.
POLISH_KEYS = ("color_look", "crisp", "fade", "auto_light", "auto_crop", "vignette", "hide_box", "hide_style", "lower_name", "lower_sub", "follow_text",
               "buddy", "buddy_feeling", "buddy_pos", "buddy_size", "voice_fx", "voice_eq", "bleep_sound", "loudness")
RECAP_OFF = dict(lower_name="", lower_sub="", follow_text="", part_badge=False, fade="off", text_boxes="", callouts="")       # these belong to ONE clip: not repeated on every moment of a recap


def _truthy(v):
    """A yes / no from anything (a tick box, the text 'false', 0, None)."""
    if isinstance(v, str): return v.strip().lower() not in ("", "0", "false", "no", "off", "none", "nan")
    try: return bool(v) and v == v
    except Exception: return False


def get_opts(o=None):
    """Defaults + caller's options, with every value checked so a bad setting can never crash a render."""
    d = dict(OPTS)
    for k_, v_ in (o if isinstance(o, dict) else {}).items():
        if k_ not in OPTS: d[k_] = v_                                                                      # extra keys the engine hands to itself (plans, times...) pass through
        elif v_ is None or isinstance(v_, (str, int, float, bool)): d[k_] = v_                            # a real option never holds a list / dict / object
    d["cap_style"] = d["cap_style"] if d["cap_style"] in CAPTION_STYLES else "pop"
    d["cap_font"] = d["cap_font"] if d["cap_font"] in FONTS else "Arial Black"
    d["cap_pos"] = d["cap_pos"] if d["cap_pos"] in CAP_POS else "low"
    d["aspect"] = d["aspect"] if d["aspect"] in ASPECTS else "9:16"
    d["sfx_pack"] = d["sfx_pack"] if d["sfx_pack"] in SFX_PACKS else "boom"
    d["platform"] = d["platform"] if d["platform"] in PLATFORMS else "any"
    d["bg_style"] = d["bg_style"] if d["bg_style"] in BG_STYLES else "blur"
    d["voice_clean"] = bool(d["voice_clean"]); d["fix_lag"] = bool(d["fix_lag"]); d["cap_emoji"] = bool(d["cap_emoji"]); d["review"] = bool(d["review"]); d["cover"] = bool(d["cover"]); d["swears"] = bool(d["swears"]); d["fresh"] = bool(d["fresh"])
    for k in ("emotes", "emote_burst", "emote_recap", "emote_cover", "emote_review"): d[k] = bool(d[k])
    d["emote_level"] = d["emote_level"] if d["emote_level"] in ("few", "normal", "lots") else "normal"
    d["emote_pos"] = d["emote_pos"] if d["emote_pos"] in ("auto", "left", "right", "top") else "auto"
    try:
        import vcfx
        d["color_look"] = d["color_look"] if d["color_look"] in vcfx.COLOR_LOOKS else "none"
        d["crisp"] = d["crisp"] if d["crisp"] in vcfx.CRISP else "off"
        d["fade"] = d["fade"] if d["fade"] in vcfx.FADES else "off"
        d["hide_style"] = d["hide_style"] if d["hide_style"] in vcfx.HIDE_STYLES else "blur"
        d["voice_fx"] = d["voice_fx"] if d["voice_fx"] in vcfx.VOICE_FX else "none"
        d["voice_eq"] = d["voice_eq"] if d["voice_eq"] in vcfx.VOICE_EQ else "natural"
        d["bleep_sound"] = d["bleep_sound"] if d["bleep_sound"] in vcfx.BLEEPS else "beep"
        d["loudness"] = str(d["loudness"]) if str(d["loudness"]) in vcfx.LOUDNESS else "-14"
        d["hide_box"] = str(d["hide_box"] or "").strip() if vcfx.parse_box(d["hide_box"]) else ""
    except Exception:
        for k in ("color_look", "crisp", "fade", "hide_style", "voice_fx", "voice_eq", "bleep_sound", "loudness", "hide_box"): d[k] = OPTS[k]
    for k in ("auto_light", "auto_crop", "vignette", "part_badge", "buddy", "emote_fx", "emote_sound", "transcript", "vod_folder"): d[k] = bool(d[k])
    d["buddy_pos"] = d["buddy_pos"] if d["buddy_pos"] in ("tl", "tr", "bl", "br") else "tl"
    d["buddy_feeling"] = re.sub(r"[^a-z0-9_]", "", str(d["buddy_feeling"] or "").lower()) or "cool"
    for k in ("lower_name", "lower_sub", "follow_text"): d[k] = re.sub(r"\s+", " ", str(d[k] or "")).strip()
    try:
        import vcnew
        d["text_boxes"] = vcnew.texts_json(d["text_boxes"])
        d["callouts"] = ",".join(vcnew.parse_callouts(d["callouts"]))
        d["custom_layout"] = str(d["custom_layout"] or "").strip() if vcnew.layout_valid(d["custom_layout"]) else ""
    except Exception:
        d["text_boxes"] = d["callouts"] = d["custom_layout"] = ""
    d["tts_voice"] = re.sub(r"[\r\n]", " ", str(d["tts_voice"] or "")).strip()[:80]
    try: d["tts_rate"] = max(-5, min(5, int(float(d["tts_rate"]))))
    except (TypeError, ValueError, OverflowError): d["tts_rate"] = 0
    d["name_pattern"] = str(d["name_pattern"] or "").strip() or OPTS["name_pattern"]
    d["hook_mode"] = d["hook_mode"] if d["hook_mode"] in HOOK_MODES else "smart"
    d["hook_text"] = str(d["hook_text"] or "").strip()[:300]
    for k in ("cap_text", "cap_hi", "cap_edge", "bg_color"):
        v = str(d[k]).lstrip("#").lower()
        d[k] = v if re.fullmatch(r"[0-9a-f]{6}", v) else OPTS[k]
    for k, lo, hi in (("cap_size", 50, 160), ("logo_size", 5, 40), ("music_vol", 1, 100), ("sticker_size", 6, 40), ("emote_size", 12, 60), ("buddy_size", 8, 45)):
        try: d[k] = min(hi, max(lo, int(float(d[k]))))
        except (TypeError, ValueError, OverflowError): d[k] = OPTS[k]
    for k in ("logo_pos", "handle_pos", "pip_pos"):
        d[k] = d[k] if d[k] in ("tl", "tr", "bl", "br") else OPTS[k]
    for k in ("logo", "music", "handle", "hint", "fixes", "channel", "game", "tags", "lang", "intro", "outro", "cta", "stickers", "filler", "bg_image"):
        d[k] = str(d[k] or "").strip()
    d["cta"] = d["cta"][:40]; d["lower_name"] = d["lower_name"][:40]; d["lower_sub"] = d["lower_sub"][:50]; d["follow_text"] = d["follow_text"][:40]
    d["translate"] = _truthy(d["translate"]) and d["lang"] != "en"
    for k, dv in OPTS.items():
        if isinstance(dv, bool) and not isinstance(d[k], bool): d[k] = _truthy(d[k])
    if _vm:
        try: _vm.clean_opts(d)
        except Exception: d.update(_vm.DEFAULTS)
    if _v23:
        try: _v23.clean_opts(d)
        except Exception: d.update(_v23.DEFAULTS)
    return d


# ---------------- progress / plan ----------------
def set_plan(est):
    tot, acc = sum(est.values()) or 1, 0.0
    PLAN.clear()
    for k, v in est.items():
        PLAN[k] = (acc / tot, v / tot); acc += v


def report(stage, f, label=None):
    s, w = PLAN.get(stage, (0.0, 1.0))
    PROGRESS(s + w * min(1.0, max(0.0, f)), label or stage)


def check_cancel():
    if CANCEL.is_set(): raise RuntimeError("Cancelled")


def kill_all():
    for p in list(PROCS):
        try: p.kill()
        except Exception: pass


def run_ff(args, total, cb=None, cwd=None):
    p = subprocess.Popen([FF, "-y", "-v", "error", "-progress", "pipe:1", "-nostats"] + args, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, errors="replace", cwd=cwd, **NOWIN)
    PROCS.add(p); tail = []
    try:
        for line in p.stdout:
            if CANCEL.is_set(): p.kill(); break
            line = line.strip()
            if line.startswith("out_time_us="):
                try:
                    if cb: cb(min(1.0, int(line.split("=")[1]) / 1e6 / max(total, .1)))
                except ValueError: pass
            elif line and not re.match(r"^\w+=", line): tail.append(line)
        rc = p.wait()
    finally: PROCS.discard(p)
    check_cancel()
    if rc: raise RuntimeError("ffmpeg failed: " + " | ".join(tail[-6:]))


def probe_info(src):
    t = subprocess.run([FF, "-hide_banner", "-i", src], capture_output=True, text=True, errors="replace", **NOWIN).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", t)
    r = re.search(r"Video:.*?[, ](\d{2,5})x(\d{2,5})", t)
    f = re.search(r"Video:.*?[, ](\d+(?:\.\d+)?) fps", t)
    return dict(dur=int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else 0.0,
                w=int(r[1]) if r else 0, h=int(r[2]) if r else 0, audio="Audio:" in t, fps=float(f[1]) if f else 30.0)


def probe(src):
    i = probe_info(src)
    return i["dur"], i["w"] or 1920, i["h"] or 1080


def check_video(src):
    i = probe_info(src)
    if not i["w"]: raise RuntimeError("Couldn't read this video file. Is the download complete?")
    if not i["audio"]: raise RuntimeError("This video has no audio track, so there is nothing to transcribe.")
    return i


def out_dims(aspect="9:16"):
    """Output size for an aspect ratio. The Resolution setting is the short side (1080p: 1080x1920 / 1080x1350 / 1080x1080 / 1920x1080).
    True / False still mean vertical / landscape (older callers)."""
    if aspect is True: aspect = "9:16"
    elif aspect is False: aspect = "16:9"
    rw, rh = ASPECTS.get(aspect, (9, 16)); r = OUT["res"]
    if rw <= rh: return r, int(round(r * rh / rw / 2)) * 2
    return int(round(r * rw / rh / 2)) * 2, r


def est_size_mb(seconds): return seconds * OUT["mbps"] / 8


def unique_path(p):
    p = Path(p)
    if not p.exists(): return p
    for i in range(2, 1000):
        q = p.with_name(f"{p.stem} ({i}){p.suffix}")
        if not q.exists(): return q
    return p


def safe_stem(video): return re.sub(r'[<>:"/\\|?*]', "_", Path(video).stem)[:60]


def valid_cam(cam, sw, sh):
    m = re.match(r"^(\d+):(\d+):(\d+):(\d+)$", cam or "")
    if not m: return False
    w, h, x, y = (int(g) for g in m.groups())
    return w >= 16 and h >= 16 and x + w <= sw and y + h <= sh


# ---------------- hardware + ETA ----------------
def _out(cmd, t=15):
    try: return subprocess.run(cmd, capture_output=True, text=True, timeout=t, errors="replace", **NOWIN).stdout
    except Exception: return ""


def _enc_ok(enc):
    try:
        return subprocess.run([FF, "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.2", "-c:v", enc, "-f", "null", "-"],
                              capture_output=True, timeout=25, **NOWIN).returncode == 0
    except Exception: return False


def cuda_dir():
    """Folder with the NVIDIA CUDA 12 / cuDNN 9 DLLs (VTuberClipper\\cuda). Only counts once the install finished."""
    d = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cuda"))
    return d if os.path.exists(os.path.join(d, "installed.ok")) else None


def _dll_ok(*names):
    d = cuda_dir()
    try:
        for n in names: ctypes.WinDLL(os.path.join(d, n) if d else n)
        return True
    except Exception: return False


def detect_hw():
    hw = dict(cores=os.cpu_count() or 4, cpu=platform.processor() or "CPU", ram=0.0, gpus=[], enc="libx264", cuda_ok=False)
    a, _, b = _out(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor | Select -First 1).Name; '---'; "
                    "(Get-CimInstance Win32_VideoController).Name"]).partition("---")
    if a.strip(): hw["cpu"] = " ".join(a.split())
    hw["gpus"] = [x.strip() for x in b.splitlines() if x.strip()]
    try:
        class MS(ctypes.Structure):
            _fields_ = [("l", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [(n, ctypes.c_ulonglong) for n in ("tp", "ap", "tpf", "apf", "tv", "av", "ae")]
        m = MS(); m.l = ctypes.sizeof(m); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)); hw["ram"] = m.tp / 2 ** 30
    except Exception: pass
    d = cuda_dir()
    if d:                                   # make the CUDA libraries visible to ctranslate2
        os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
        try: os.add_dll_directory(d)
        except Exception: pass
    names = " ".join(hw["gpus"]).lower()
    for enc, keys in (("h264_nvenc", ("nvidia",)), ("h264_amf", ("amd", "radeon")), ("h264_qsv", ("intel",))):
        if any(k in names for k in keys) and _enc_ok(enc): hw["enc"] = enc; break
    hw["cuda_ok"] = "nvidia" in names and _dll_ok("cublas64_12.dll", "cudnn64_9.dll")
    return hw


_FC = None


def fc_args(name):
    """Newer ffmpeg removed -filter_complex_script (use -/filter_complex FILE); older builds only know the old one."""
    global _FC
    if _FC is None:
        with tempfile.TemporaryDirectory() as d:
            Path(d, "t.txt").write_text("[0:v]null[o]")
            r = subprocess.run([FF, "-v", "error", "-f", "lavfi", "-i", "color=d=0.1", "-/filter_complex", "t.txt", "-map", "[o]", "-f", "null", "-"],
                               capture_output=True, cwd=d, **NOWIN)
            _FC = "-/filter_complex" if r.returncode == 0 else "-filter_complex_script"
    return [_FC, name]


def get_hw():
    global HW
    if HW is None: HW = detect_hw()
    return HW


def gpu_enc_active():
    return USE_GPU_ENC and not GPU_ENC_FAILED and get_hw()["enc"] != "libx264"


def venc():
    """Video encoder arguments for the chosen quality (Mbps). GPU encoder when it works, otherwise x264."""
    m = OUT["mbps"]; mx, bs = f"{m * 1.15:.0f}M", f"{m * 2}M"
    enc = get_hw()["enc"] if gpu_enc_active() else "libx264"
    if enc == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p5", "-tune", "hq", "-rc", "vbr", "-b:v", f"{m}M", "-maxrate", mx, "-bufsize", bs, "-profile:v", "high"]
    if enc == "h264_amf":
        return ["-c:v", "h264_amf", "-quality", "balanced", "-rc", "vbr_peak", "-b:v", f"{m}M", "-maxrate", mx, "-bufsize", bs]
    if enc == "h264_qsv":
        return ["-c:v", "h264_qsv", "-b:v", f"{m}M", "-maxrate", mx, "-bufsize", bs]
    return ["-c:v", "libx264", "-preset", "veryfast", "-b:v", f"{m}M", "-maxrate", mx, "-bufsize", bs, "-profile:v", "high"]


def auto_workers(n_jobs, aspect="9:16"):
    """How many clips are rendered at the same time. One ffmpeg already uses several cores, so small PCs stay on 1."""
    if PARALLEL: w = int(PARALLEL)
    else:
        c = get_hw()["cores"]; w = 1 if c < 6 else 2 if c < 12 else 3
        if gpu_enc_active(): w = min(w, 2)                          # video-encoder chips handle only a few jobs at once
        if max(out_dims(aspect)) >= 3000: w = min(w, 2)             # 4K clips are memory hungry
    return max(1, min(w, max(1, n_jobs), 4))


def estimate(vod_s, mode, n, clip_len, minutes, model, device, cached, an_cached=False, workers=None, vhs=False):
    """Seconds per stage, from detected hardware and the chosen output size. The app multiplies by a learned factor."""
    hw = get_hw(); c = min(hw["cores"], 16)
    gpu = device == "cuda" or (device == "auto" and hw["cuda_ok"])
    rt = {"tiny": 60, "base": 40, "small": 25, "medium": 12}[model] if gpu else c * {"tiny": 3.0, "base": 1.8, "small": .7, "medium": .25}[model]
    rt *= {"fast": 1.9, "balanced": 1.25}.get(SPEECH_SPEED, 1.0)
    base = {"Transcribing": 1.0 if cached else vod_s / rt + 15, "Analyzing": 1.0 + vod_s / 20000 if an_cached else vod_s / 120 + 4}
    if mode in ("moments", "post"): return base                 # scanning / listening only: nothing is rendered
    if mode == "games": return {**base, "Scanning": vod_s / 250 + 3}      # + a look at one picture every 10 s
    if mode == "cut": return {"Rendering": vod_s / 400 + 2}     # just cutting the file into parts: no re-encode, no speech model
    out_s = n * clip_len if mode in ("shorts", "twitter") else minutes * 60
    W, H = out_dims(mode in ("shorts", "twitter"))
    px = (W * H * OUT["fps"]) / (1920 * 1080 * 30)             # work relative to 1080p30
    enc = 1.5 if gpu_enc_active() else 1.0 / (1 + OUT["mbps"] / 300)
    speed = .45 * c ** .8 * enc * (1.0 if mode == "shorts" else 1.6) / px ** .9
    if mode == "shorts":
        w = workers or auto_workers(n)
        speed *= {1: 1.0, 2: 1.3, 3: 1.5, 4: 1.6}.get(w, 1.0)       # several clips at once keep every core busy
    if vhs: speed /= 2.0                                        # film grain is very hard on the video encoder
    parts = n if mode == "shorts" else max(1, int(minutes * 3))
    base["Rendering"] = out_s / speed + 2.5 * parts + (0 if mode == "shorts" else out_s / 30)
    return base


# ---------------- analysis ----------------
def cache_path(src, lang="", translate=False, hint=""):
    """Saved-transcript file. The default (auto language, no hint) keeps the v1.0 name so old transcripts still work."""
    tag = (lang or "") + ("-en" if translate and lang != "en" else "")
    if (hint or "").strip(): tag += ("-" if tag else "") + hashlib.md5(hint.strip().lower().encode("utf-8")).hexdigest()[:6]
    return Path(src + (f".words.{tag}.json" if tag else ".words.json"))


def clean_words(words):
    """Only usable words, in time order: text present, finite numbers, end never before start."""
    out = []
    for w in words if isinstance(words, list) else []:
        try:
            t, a, b = str(w["w"]).strip(), float(w["start"]), float(w["end"])
        except (KeyError, TypeError, ValueError): continue
        if not t or not (math.isfinite(a) and math.isfinite(b)) or a < 0: continue
        out.append({"w": t, "start": a, "end": max(b, a + .05)})
    return sorted(out, key=lambda w: w["start"])


def parse_fixes(text):
    """'wrong = right' pairs, one per line or comma separated -> [(["wrong", "words"], "Right")]."""
    out = []
    for part in re.split(r"[\n,;]+", text or ""):
        if "=" not in part: continue
        a, _, b = part.partition("=")
        k = [clean(x) for x in a.split() if clean(x)]
        if k and b.strip(): out.append((k, b.strip()))
    return sorted(out, key=lambda f: -len(f[0]))


def apply_fixes(words, fixes):
    """Correct names / terms the speech model gets wrong. A fix can span several words ('kit ten = Kitten')."""
    fx = parse_fixes(fixes) if isinstance(fixes, str) else fixes
    if not fx: return words
    out, i, n = [], 0, len(words)
    while i < n:
        for k, right in fx:
            m = len(k)
            if i + m <= n and all(clean(words[i + j]["w"]) == k[j] for j in range(m)):
                tail = re.search(r"[^\w']+$", words[i + m - 1]["w"])
                out.append({"w": right + (tail.group(0) if tail and not re.search(r"[^\w']+$", right) else ""),
                            "start": words[i]["start"], "end": words[i + m - 1]["end"]})
                i += m; break
        else:
            out.append(words[i]); i += 1
    return out


def read_cached_words(cache, src):
    """Saved transcript -> (clean words, raw json). v1.0-1.3 files counted time from the first audio sample; they are moved onto ffmpeg's timeline once."""
    raw = json.loads(cache.read_text(encoding="utf-8"))
    old = isinstance(raw, list)
    words = clean_words(raw if old else raw.get("words", []))
    if old and words:
        lead = audio_lead(src)
        if lead: words = [{**w, "start": w["start"] + lead, "end": w["end"] + lead} for w in words]
        try: cache.write_text(json.dumps({"v": 2, "words": words}), encoding="utf-8")
        except Exception: pass
    return words, raw


def transcribe(src, model="small", device="auto", lang="", translate=False, hint="", fixes=""):
    """Word-timed transcript. lang '' = detect; translate=True turns any language into English subtitles.
    hint = names / terms to help the speech model; fixes = 'wrong = right' corrections applied afterwards."""
    cache = cache_path(src, lang, translate, hint)
    if cache.exists():
        try:
            words, raw = read_cached_words(cache, src)
            if words or (isinstance(raw, list) and not raw) or (isinstance(raw, dict) and not raw.get("words")):   # an empty list is a real answer: no speech
                report("Transcribing", 1, "Using saved transcript"); return apply_fixes(words, fixes)
        except Exception: pass
    from faster_whisper import WhisperModel
    dur = probe(src)[0] or 1.0
    dev = "cuda" if get_hw()["cuda_ok"] and device in ("cuda", "auto") else "cpu"
    if device == "cuda" and dev == "cpu":
        print("GPU speech needs the NVIDIA CUDA 12 + cuDNN 9 runtime (Settings -> Performance -> Install GPU speech pack) - using the CPU for now.")
    report("Transcribing", 0, "Loading speech model (the first run downloads it - needs internet)")
    kw = dict(word_timestamps=True, vad_filter=True)
    if SPEECH_SPEED == "fast": kw.update(beam_size=1, best_of=1, temperature=0.0, condition_on_previous_text=False)     # ~2x quicker, a few more small mistakes
    elif SPEECH_SPEED == "balanced": kw.update(beam_size=3, condition_on_previous_text=False)                         # also stops one wrong word from repeating
    if lang: kw["language"] = lang
    if translate and lang != "en": kw["task"] = "translate"
    if (hint or "").strip(): kw["initial_prompt"] = hint.strip()[:400]

    def go(d):
        mk = dict(cpu_threads=min(get_hw()["cores"], 16)) if d == "cpu" else {}
        try: m = WhisperModel(model, device=d, compute_type="float16" if d == "cuda" else "int8", **mk)
        except Exception as e:
            raise RuntimeError(f"Couldn't load the speech model '{model}'. The first run needs internet to download it once. ({str(e)[:140]})")
        out = []
        for s in m.transcribe(src, **kw)[0]:
            check_cancel()
            out += [{"w": w.word.strip(), "start": w.start, "end": w.end} for w in (s.words or []) if w.word.strip()]
            report("Transcribing", s.end / dur, f"Transcribing {int(s.end // 60)} / {int(dur // 60)} min")
        return out
    try: words = go(dev)
    except Exception as e:
        if dev == "cpu" or "Cancelled" in str(e): raise
        print(f"GPU speech failed ({str(e)[:80]}); switching to the CPU"); words = go("cpu")
    words = clean_words(words)
    lead = audio_lead(src)
    if lead: words = [{**w, "start": w["start"] + lead, "end": w["end"] + lead} for w in words]     # same clock as the cuts
    try: cache.write_text(json.dumps({"v": 2, "words": words}), encoding="utf-8")
    except Exception: pass                      # read-only folder: just skip the cache
    return apply_fixes(words, fixes)


AN = {}   # last analysis: exact audio onsets + per-second speech coverage


def _an_key(src):
    try:
        st = os.stat(src)
        return hashlib.md5(f"{os.path.abspath(src)}|{st.st_size}|{int(st.st_mtime)}".encode("utf-8", "replace")).hexdigest()[:20]
    except OSError: return ""


AX = {}   # 2.2: more audio facts about the last analysed video (brightness, high-band share, pitch every 40 ms) for the laugh / scream / singing detectors


def an_cached(src):
    """True when the audio of this video was analysed before (the slow ffmpeg decode can be skipped)."""
    k = _an_key(src)
    return bool(k) and os.path.exists(os.path.join(CACHE_DIR, f"an3_{k}.npz"))


def audio_stats(src, dur):
    """Per-second loudness (rms / peak) and 50 ms rms of the whole VOD. Saved on disk, so a second run on the same VOD skips the decode."""
    key = _an_key(src); f = os.path.join(CACHE_DIR, f"an3_{key}.npz") if key else ""
    if f and os.path.exists(f):
        try:
            z = np.load(f)
            rms, peak, r50 = z["rms"], z["peak"], z["r50"]
            if len(rms) > 0 and len(r50) > 0:
                AX.clear()
                if "f0" in z.files and len(z["cent"]) == len(rms): AX.update(cent=z["cent"], hi=z["hi"], f0=z["f0"])
                report("Analyzing", .92, "Using saved audio analysis"); return rms, peak, r50
        except Exception: pass
    report("Analyzing", .02, "Analyzing audio")
    proc = subprocess.Popen([FF, "-v", "quiet", "-i", src, "-vn", "-ac", "1", "-ar", "16000", "-af", "aresample=async=1:first_pts=0", "-f", "s16le", "-"],
                            stdout=subprocess.PIPE, **NOWIN)
    PROCS.add(proc); rms_l, peak_l, r50_l, got = [], [], [], 0
    try: import vcsense
    except Exception: vcsense = None
    cent_l, hi_l, f0_l = [], [], []
    try:
        while True:                             # stream in 5-minute chunks so even 8-hour VODs stay light on RAM
            if CANCEL.is_set(): proc.kill(); break
            buf = proc.stdout.read(16000 * 300 * 2)
            if not buf: break
            a = np.frombuffer(buf[:len(buf) // 2 * 2], np.int16).astype(np.float32)
            s = len(a) // 16000
            if s == 0: continue
            a = a[:s * 16000]; x = np.abs(a).reshape(s, 16000)
            rms_l.append(np.sqrt((x ** 2).mean(1))); peak_l.append(x.max(1))
            r50_l.append(np.sqrt((a.reshape(-1, 800) ** 2).mean(1)))
            if vcsense:
                try:
                    c_, h_, _lo, f_ = vcsense.chunk_feats(a); cent_l.append(c_); hi_l.append(h_); f0_l.append(f_)
                except Exception: vcsense = None; cent_l, hi_l, f0_l = [], [], []
            got += s; report("Analyzing", .02 + .9 * min(1, got / dur), f"Analyzing audio {got // 60} / {int(dur // 60)} min")
        proc.wait()
    finally: PROCS.discard(proc)
    check_cancel()
    if not rms_l: raise RuntimeError("This video has no audio track to analyze (or it is shorter than a second).")
    rms, peak, r50 = (np.concatenate(v).astype(np.float32) for v in (rms_l, peak_l, r50_l))
    AX.clear(); xtra = {}
    if vcsense and cent_l:
        try:
            xtra = dict(cent=np.concatenate(cent_l).astype(np.float32), hi=np.concatenate(hi_l).astype(np.float32), f0=np.concatenate(f0_l).astype(np.float32))
            if len(xtra["cent"]) != len(rms): xtra = {}
        except Exception: xtra = {}
    AX.update(xtra)
    if f and len(rms) >= 8:
        try:
            os.makedirs(CACHE_DIR, exist_ok=True); tmp = f + ".tmp.npz"
            np.savez(tmp, rms=rms, peak=peak, r50=r50, **xtra); os.replace(tmp, f)
        except Exception: pass                  # cache is only a speed-up
    return rms, peak, r50


SMART_W = dict(laugh=2.4, scream=2.0, setup=1.1, sing=1.4, chat=2.0, w_laugh=1.0, w_fail=.7, w_hype=.8)


def smart_boost(src, words, rms, r50, n, o):
    """2.2: extra score per second from the laugh / scream / singing / quiet-beat detectors, the lists of reaction words and (when there is one) the chat log.
    Also keeps the curves in AN so the clip chooser can name the kind of each moment. Returns zeros when switched off or when something is missing."""
    AN["curves"] = AN["marks"] = AN["chat"] = AN["clues"] = None
    if o is not None and not o.get("smart", True): return np.zeros(n)
    try:
        import vcsmart, vcsense
        z = lambda v: (v - v.mean()) / (v.std() + 1e-6)
        cur = {}
        if AX.get("f0") is not None and len(AX.get("cent", ())) >= n:
            cur = vcsense.curves(r50, z(rms), AN["onsets"], AX["f0"], AX["cent"], n, AX.get("hi"))
        mk = vcsmart.word_marks(words, n)
        chat, path = None, str((o or {}).get("chat_file") or "") or vcsmart.find_chat_file(src)
        if path:
            chat, cnt = vcsmart.load_chat(path, n)
            if chat is not None: print(f"Chat log found ({cnt} messages): busy chat moments score higher.")
            else: print("(couldn't use the chat file " + Path(path).name + " - it needs at least 20 messages with times)")
        b = np.zeros(n)
        for k in ("laugh", "scream", "setup", "sing"):
            if k in cur: b += SMART_W[k] * np.asarray(cur[k][:n], float)
        if chat is not None: b += SMART_W["chat"] * np.asarray(chat[:n], float)
        b += (SMART_W["w_laugh"] * np.minimum(2, mk["laugh"] + mk["scream"]) + SMART_W["w_fail"] * np.minimum(2, mk["fail"] + mk["win"] + mk["scare"])
              + SMART_W["w_hype"] * np.minimum(2, mk["hype"]))
        AN["curves"], AN["marks"], AN["chat"] = cur or None, mk, chat
        try:                                                                       # 2.3: !clip commands, milestones, chat talk, bilingual, rapid-fire, panic repeats, build-up, BRB parts
            import vcclues
            cl = vcclues.compute(words, AN.get("rmsz"), n, o, vcclues.chat_messages(path) if path else [], AN.get("quiet"))
            AN["clues"] = cl
            b = b + np.asarray(cl["boost"][:n], float)
            if cl["cmds"]: print(f"Viewers asked for a clip {sum(c for _, c in cl['cmds'])} time(s) in chat: {len(cl['cmds'])} moment(s) will be looked at first.")
            if cl["zones"]: print(f"Leaving out {len(cl['zones'])} break / goodbye part(s) of the video.")
        except Exception as e: print("(extra clues skipped:", str(e)[:100] + ")")
        return np.convolve(b, np.ones(3) / 3, "same")
    except Exception as e:
        print("(smart sound detectors skipped:", str(e)[:100] + ")"); AN["curves"] = AN["marks"] = AN["chat"] = AN["clues"] = None
        return np.zeros(n)


def features(src, words, p=None, o=None):
    """Per-second 'engagement score': loudness, peaks, sudden onsets (screams/laughs), exclamations, hype words, speech density.
    2.2: o = options; unless smart finding is switched off, laugh / scream / singing / reaction-word / chat scores are added."""
    p = p or PROFILES["gameplay"]
    dur = probe(src)[0] or 1.0
    rms, peak, r50 = audio_stats(src, dur); n, m = len(rms), len(r50)
    if n < 8: raise RuntimeError("This video is too short to find clips in.")
    prev = np.concatenate([[0.0], np.convolve(r50, np.ones(10) / 10, "full")[:m - 1]])
    st = (r50 - prev) / ((r50 - prev).std() + 1e-6)
    lm = st.copy()
    for s in range(1, 7): lm = np.maximum(lm, np.maximum(np.roll(st, s), np.roll(st, -s)))
    idx = np.where((st >= lm) & (st > 2.5) & (r50 > np.median(r50) * 1.5))[0]
    AN["onsets"] = [(float(i * .05), float(st[i])) for i in idx]
    z = lambda v: (v - v.mean()) / (v.std() + 1e-6)
    ons, wps, hype, excl, cover = (np.zeros(n) for _ in range(5))
    for t, _ in AN["onsets"]:
        if int(t) < n: ons[int(t)] += 1
    for w in words:
        i = int(w["start"])
        if i < n:
            wps[i] += 1; cover[i] = 1; hype[i] += clean(w["w"]) in HYPE
            excl[i] += ends_in(w["w"], "!?！？") or "haha" in w["w"].lower() or "笑" in w["w"] or "ㅋㅋ" in w["w"]
    AN["cover"] = np.convolve(cover, np.ones(3), "same").clip(0, 1)
    AN.update(rmsz=z(rms), hype=hype, excl=excl, wps=wps, ons=ons, quiet=(z(rms) < -.35))          # kept so the moment finder can say WHY a moment is good
    mix = (p["w_loud"] * z(rms) + p["w_peak"] * z(peak) + p["w_onset"] * z(ons) + p["w_excl"] * z(excl)
           + p["w_speech"] * z(wps) + p["w_hype"] * hype)
    mix = mix + p.get("w_smart", 1.0) * smart_boost(src, words, rms, r50, n, o)
    report("Analyzing", 1, "Analysis done")
    return np.convolve(mix, np.ones(3) / 3, "same")


def wscore(sc, i, L, dead=.5, cs=None):
    """Score of the L-second window starting at second i: average energy + best moment + a strong first 3s, minus dead air."""
    cover = AN.get("cover"); n = len(sc); i = max(0, min(int(i), n - 1)); L = max(1, min(int(L), n - i))
    w = sc[i:i + L]
    s = (float(w.sum()) if cs is None else float(cs[i + L] - cs[i])) / L + .6 * float(w.max()) + .5 * float(w[:3].mean())
    if cover is not None and len(cover) >= i + L: s -= dead * (1 - float(cover[i:i + L].mean())) * 2
    return s


# ---------------- clips already made from a video ----------------
def made_path(src):
    k = _an_key(src)
    return os.path.join(CACHE_DIR, f"made_{k}.json") if k else ""


def load_made(src):
    """[(start, end)] of the clips made from this video before (seconds of the VOD)."""
    try:
        with open(made_path(src), encoding="utf-8") as f: d = json.load(f)
        return [(float(a), float(b)) for a, b in d.get("windows", [])][-400:]
    except Exception: return []


def save_made(src, wins):
    """Remember clips that were made, so the next run can pick different moments."""
    p = made_path(src)
    if not p: return
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        allw = load_made(src) + [(float(a), float(b)) for a, b in wins]
        with open(p + ".tmp", "w", encoding="utf-8") as f: json.dump({"windows": [[round(a, 2), round(b, 2)] for a, b in allw[-400:]]}, f)
        os.replace(p + ".tmp", p)
    except OSError: pass


def forget_made(src):
    """Start over: the next run may pick any moment again. Returns how many were forgotten."""
    n = len(load_made(src)); p = made_path(src)
    try:
        if p and os.path.exists(p): os.remove(p)
    except OSError: pass
    return n


def overlaps_made(s0, e0, wins, need=3.0):
    return any(min(e0, y) - max(s0, x) > need for x, y in wins)


def top_windows(sc, L, stride, p=None, a=0, b=None):
    """Rank windows by average energy + best moment + a strong first 3s, minus dead air; then slide each so its peak
    lands ~40% in (build-up, payoff, reaction). Returns [(score, start)] best first, no two closer than L seconds.
    `a` / `b`: only look between these seconds of the VOD (one game of a long stream)."""
    n, dead = len(sc), (p or {}).get("dead", .5)
    b = n if b is None else max(2, min(n, int(b))); a = max(0, min(int(a), b - 2))
    L = max(3, min(int(L), b - a - 1))
    cs = np.concatenate([[0], np.cumsum(sc)]); cands = []
    for i in range(a, max(a + 1, b - L + 1), stride):
        cands.append((wscore(sc, i, L, dead, cs), i))
    if cands:                                   # baseline for 0-100 ratings: a typical stretch of this stream vs the best one
        allv = np.array([c[0] for c in cands]); AN["base"] = (float(np.percentile(allv, 20)), float(allv.max()))
    chosen = []
    for s, i in sorted(cands, reverse=True):
        j = int(min(max(i + int(np.argmax(sc[i:i + L])) - .4 * L, a), max(a, b - L)))
        if all(abs(j - k) >= L for _, k in chosen): chosen.append((s, j))
    return chosen


def rating(score):
    """0-100: how far above a typical stretch of this stream the moment is (100 = the best moment found)."""
    lo, hi = AN.get("base", (0.0, 1.0))
    return int(max(0, min(100, round(100 * (score - lo) / (hi - lo + 1e-6)))))


def snap(words, s, e):
    for k, w in enumerate(words):
        if s - 8 <= w["end"] <= s and ends_in(w["w"], END_P) and k + 1 < len(words):
            s = words[k + 1]["start"]; break
    for w in words:
        if e <= w["end"] <= e + 10 and ends_in(w["w"], END_P):
            e = w["end"]; break
    return s, e


def _noisy(quiet, a, b):
    """True when there is sound activity (game, music, a scream) between second a and second b: `quiet` = per-second flags of quiet seconds."""
    i, j = max(0, int(a)), min(len(quiet), int(math.ceil(b)))
    return j > i and float(np.mean(quiet[i:j])) < .6


def keep_segments(start, end, words, gap, pad=0.5, quiet=None):
    """Cut only real silence: pauses longer than `gap`, and always keep `pad` (0.5s) of breathing room before and after
    the silence so talking is never clipped. 2.2: with `quiet` (per-second flags) a pause that still has sound in it (game action, music) is kept."""
    ws = [w for w in words if w["end"] > start and w["start"] < end]
    if not ws or gap is None: return [(start, end)]
    thr = max(gap, 2 * pad + .2)
    a0 = start if (quiet is not None and ws[0]["start"] - pad > start and _noisy(quiet, start, ws[0]["start"] - pad)) else max(start, ws[0]["start"] - pad)
    segs, a, prev = [], a0, ws[0]["end"]
    for w in ws[1:]:
        if w["start"] - prev > thr and not (quiet is not None and _noisy(quiet, prev + pad, w["start"] - pad)):
            segs.append((a, min(prev + pad, end))); a = w["start"] - pad
        prev = max(prev, w["end"])
    e1 = end if (quiet is not None and end - (prev + pad) > 0 and _noisy(quiet, prev + pad, end)) else min(prev + pad, end)
    segs.append((a, e1))
    return segs


def kept_len(segs): return sum(b - a for a, b in segs)


def snap_start(words, t):
    """Move a start to the beginning of the sentence that starts within the 8s before it."""
    for k, w in enumerate(words):
        if t - 8 <= w["end"] <= t and ends_in(w["w"], END_P) and k + 1 < len(words): return words[k + 1]["start"]
    return t


def fit_clip(sc, words, i, lo, hi, gap, snap_s=False, limit=None, quiet=None):
    """A clip that starts at `i`: choose where it ends so its FINAL length (after silence removal) lands inside [lo, hi],
    stopping at a natural place (end of a sentence or a pause) once the big moment has landed.
    Returns (start, end, segments) or None when there is nothing usable."""
    n = int(limit if limit is not None else len(sc)); lo, hi = max(3.0, lo), max(lo, hi)
    s0 = float(snap_start(words, i) if snap_s else i)
    ext = int(min(n - s0, hi * 2.5 + 12)); ext2 = int(min(n - s0, hi * 6 + 30))      # ext2: only when long silences shrink the clip a lot
    if ext < 3: return None
    local = [w for w in words if s0 - 1 <= w["start"] <= s0 + ext2 + 1]
    kept = (lambda e: e - s0) if gap is None else (lambda e: kept_len(keep_segments(s0, e, local, gap, quiet=quiet)))
    mid = (lo + hi) / 2
    pk0 = int(s0); pk = pk0 + int(np.argmax(sc[pk0:max(pk0 + 1, min(len(sc), pk0 + int(mid) + 1))]))
    nat = {round(w["end"], 2) for w in local if ends_in(w["w"], END_P) and w["end"] > s0 + 1}
    for a, b in zip(local, local[1:]):
        if b["start"] - a["end"] >= .6: nat.add(round(a["end"] + min(.3, (b["start"] - a["end"]) / 2), 2))
    ends = sorted([(e, True) for e in nat if s0 + 2 < e <= s0 + ext] + [(float(s0 + t), False) for t in range(max(3, int(lo * .5)), ext + 1, 2)])
    best = None
    for e, isnat in ends:
        k = kept(e)
        if lo <= k <= hi:
            a = max(0, int(e) - 3); calm = float(sc[a:int(e) + 1].mean()) if len(sc) > a else 0.0
            cost = calm + (0 if isnat else 1.0) + (1.5 if e < pk + 3 else 0) + .01 * abs(k - mid)
            if best is None or cost < best[0]: best = (cost, e)
    if best: e = best[1]
    else:                                        # no natural stop fits: first moment (1s steps) where the clip is long enough
        e = s0 + 1
        for t in range(1, ext2 + 1):
            e = s0 + t
            if kept(e) >= lo: break
    segs = [(s0, e)] if gap is None else keep_segments(s0, e, local, gap, quiet=quiet)
    return (s0, e, segs) if kept_len(segs) >= 2 else None


def pick_events(sc, words, a, b, k, sep=6.0, strength=False):
    """Impact moments = real audio onsets (screams, laughs, sudden loud hits) and hype words, at the exact moment.
    If nothing actually happens, no impact is added. 2.2: detected screams, laughs, quiet-beat-then-boom and win / fail words count too.
    strength=True returns [(time, strength)] instead of the times."""
    ons = [(st, t) for t, st in AN.get("onsets", []) if a + 1.0 <= t <= b - .5]
    cand = list(ons)
    for w in words:
        if a + 1.0 <= w["start"] <= b - .5 and clean(w["w"]) in HYPE:
            near = [t for _, t in ons if abs(t - w["start"]) < .5]
            cand.append((6.0, near[0] if near else w["start"]))
    cur, mk = AN.get("curves") or {}, AN.get("marks") or {}
    ia, ib = int(a) + 1, int(b - .5)
    if ib > ia:
        for key, thr, wt in (("scream", .35, 8.0), ("laugh", .6, 5.5), ("setup", .5, 5.5)):
            arr = cur.get(key)
            if arr is None: continue
            seg = np.asarray(arr[ia:ib])
            for j in np.where(seg >= thr)[0]:
                if (j == 0 or seg[j] >= seg[j - 1]) and (j == len(seg) - 1 or seg[j] >= seg[j + 1]):
                    t = ia + int(j) + .5; near = [tt for _, tt in ons if abs(tt - t) < 1.0]
                    cand.append((wt * float(seg[j]) + 1.0, near[0] if near else t))
        for key, wt in (("fail", 4.5), ("win", 4.5), ("scare", 4.0)):
            arr = mk.get(key)
            if arr is None: continue
            for j in np.where(np.asarray(arr[ia:ib]) >= 1)[0]: cand.append((wt, ia + int(j) + .3))
    ev = []
    for st_, t in sorted(cand, reverse=True):
        if len(ev) >= k: break
        if all(abs(t - e[0]) >= sep for e in ev): ev.append((t, st_))
    ev.sort()
    return ev if strength else [t for t, _ in ev]


def is_cens(w, censor):
    """True when a word is bleeped / starred: it is on the bleep list, or the 2.3 privacy guard marked it ('priv')."""
    return clean(w["w"]) in censor or bool(w.get("priv"))


def first_words(words, t, n=6, censor=frozenset()):
    out = []
    for w in words:
        if w["start"] >= t:
            out.append("*" * len(w["w"]) if is_cens(w, censor) else w["w"])
            if len(out) == n: break
    return " ".join(out)


def censor_text(text, censor=frozenset()):
    """Cover the bleeped words of a piece of text with stars (same rule as the captions)."""
    if not censor: return text
    return " ".join("*" * len(w) if clean(w) in censor else w for w in text.split())


def pick_hook(words, segs, s0, k, o, censor=frozenset(), kind=None):
    """The big title that pops up over the first seconds of a short.
    smart = the punchiest line of the clip (a teaser), words = the first words said, mine = the user's own text (several lines take turns)."""
    mode = o.get("hook_mode", "smart")
    if mode == "mine":
        lines = [x.strip() for x in re.split(r"[|\n]+", str(o.get("hook_text", ""))) if x.strip()]
        if lines: return lines[k % len(lines)][:70]
        mode = "smart"
    if mode == "smart":
        try:
            import vcpost
            cw, _ = remap(words, segs)
            q = vcpost.analyze(cw)["quote"] if cw else ""
            q = vcpost.tidy_quote(q.rstrip("\u2026").rstrip(" ,;:-"), 40) if q else ""
            if len(q.split()) >= 3:
                try:
                    import vcsafe; q = vcsafe.scrub_text(q, o)                    # 2.3: no phone number / address / private word in the big title
                except Exception: pass
                return censor_text(q, censor)
        except Exception: pass
        if kind:                                   # 2.2: no good line was said, so a title that fits the kind of clip
            try:
                import vcsmart
                return vcsmart.hook_for(kind, k, o.get("game", ""))
            except Exception: pass
    return first_words(words, s0, censor=censor)


def tmap(segs, t):
    off = 0.0
    for a, b in segs:
        if a <= t <= b: return off + t - a
        off += b - a
    return None


def remap(words, segs):
    out, off = [], 0.0
    for a, b in segs:
        for w in words:
            if w["start"] >= a - .01 and w["end"] <= b + .01:
                out.append({**w, "start": off + w["start"] - a, "end": off + w["end"] - a})
        off += b - a
    return out, off


# ---------------- caption review: the corrected text -> timed words ----------------
def words_in(words, segs):
    """The transcript words a clip shows (same rule as remap), still in source time."""
    return [w for w in words if any(w["start"] >= a - .01 and w["end"] <= b + .01 for a, b in segs)]


def _norm(s):
    return re.sub(r"[^\w']", "", str(s).lower())


def _spread(tokens, t0, t1):
    """Give new words time between t0 and t1, longer words a little longer."""
    t1 = max(t1, t0 + .09 * len(tokens)); wt = [len(x) + 1.5 for x in tokens]; tot = sum(wt); out, cur = [], t0
    for x, w_ in zip(tokens, wt):
        d = (t1 - t0) * w_ / tot; out.append({"w": x, "start": cur, "end": cur + d}); cur += d
    return out


def edit_words(orig, text):
    """orig = timed words of a clip, text = the same passage after the user fixed it -> new timed words.
    Words that did not change keep their timing; a changed stretch shares the old stretch's time by word length;
    added words squeeze into the nearest gap; removed words simply go."""
    import difflib
    new = str(text or "").split()
    if not orig or not new: return []
    A, B = [_norm(w["w"]) for w in orig], [_norm(x) for x in new]
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, A, B, autojunk=False).get_opcodes():
        if tag == "equal":
            out += [{**orig[i1 + k], "w": new[j1 + k]} for k in range(i2 - i1)]
        elif tag == "delete": continue
        else:
            toks = new[j1:j2]
            if i2 > i1: t0, t1 = orig[i1]["start"], orig[i2 - 1]["end"]
            else:                                              # words added where nothing was said before
                prev_end = out[-1]["end"] if out else None
                nxt = orig[i1]["start"] if i1 < len(orig) else None
                need = .22 * len(toks)
                if prev_end is not None and nxt is not None and nxt - prev_end >= need: t0, t1 = prev_end, nxt
                elif prev_end is not None and nxt is not None:      # no gap: borrow the end of the word before
                    give = min(need, .5 * (out[-1]["end"] - out[-1]["start"])); out[-1]["end"] -= give; t0, t1 = out[-1]["end"], max(nxt, out[-1]["end"] + need)
                elif nxt is not None: t0, t1 = max(0.0, nxt - need), nxt
                else: t0, t1 = prev_end, prev_end + need
            out += _spread(toks, t0, t1)
    for a_, b_ in zip(out, out[1:]):                           # never overlap the next word
        a_["end"] = min(a_["end"], max(a_["start"] + .05, b_["start"]))
    return out


def apply_caption_edits(words, seglist, texts):
    """words = the whole transcript, seglist[k] = the pieces clip k shows, texts = {k: corrected text} -> the transcript with those clips' words replaced."""
    drop, add = set(), []
    for k, text in (texts or {}).items():
        try: segs = seglist[int(k)]
        except (IndexError, ValueError, TypeError): continue
        sw = words_in(words, segs)
        if " ".join(str(text).split()) == " ".join(w["w"] for w in sw): continue
        drop.update(id(w) for w in sw); add += edit_words(sw, text)
    if not drop: return words
    return sorted([w for w in words if id(w) not in drop] + add, key=lambda w: w["start"])


def fix_pairs(before, after):
    """Corrections worth remembering: a short run of words became a similar-sounding one ('kit ten' -> 'Kitten', 'mika' -> 'Mika') -> ['kit ten = Kitten', ...]."""
    import difflib
    a, b = str(before).split(), str(after).split(); out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, [_norm(x) for x in a], [_norm(x) for x in b], autojunk=False).get_opcodes():
        if tag != "replace" or i2 - i1 > 3 or j2 - j1 > 3: continue
        old, new = " ".join(a[i1:i2]), " ".join(b[j1:j2])
        o_, n_ = _norm(old.replace(" ", "")), _norm(new.replace(" ", ""))
        if len(o_) < 3 or len(n_) < 3 or o_ == n_ and old.lower() == new.lower(): continue
        if difflib.SequenceMatcher(None, o_, n_).ratio() >= .55:
            wrong = re.sub(r"[^\w' ]", "", old).strip(); right = new.strip(",.!?;:")
            if wrong and right: out.append(wrong + " = " + right)
    return out


# ---------------- source timeline repair (A/V sync) ----------------
_LEAD = {}


def audio_lead(src):
    """Seconds the first audio sample comes AFTER the start of ffmpeg's timeline (audio that starts later than the video, common with
    stream downloads). The transcript is counted from the first audio sample, the cuts from the timeline - this is the difference."""
    k = os.path.abspath(src)
    if k in _LEAD: return _LEAD[k]
    v = 0.0
    try:
        r = subprocess.run([FF, "-hide_banner", "-v", "info", "-t", "6", "-i", src, "-map", "0:a:0", "-af", "ashowinfo", "-frames:a", "1", "-f", "null", "-"],
                           capture_output=True, text=True, errors="replace", timeout=60, **NOWIN)
        m = re.search(r"pts_time:\s*(-?[\d.]+)", r.stderr)
        if m: v = float(m.group(1))
    except Exception: v = 0.0
    v = v if 0.04 <= v <= 30 else 0.0
    _LEAD[k] = v
    return v


def video_holes(src, lo, hi, min_gap=0.25):
    """Stretches of the source with NO video frames (stream lag, lost pieces of the download, a picture that starts late). Reads only the
    packet timestamps - no decoding, a second or two. Returns [(t0, t1)] in source seconds; the picture is frozen on the last frame in there."""
    t0 = max(0.0, lo - 3.0)
    try:
        r = subprocess.run([FF, "-hide_banner", "-v", "error", "-ss", f"{t0:.3f}", "-t", f"{hi - t0 + 1.5:.3f}", "-i", src, "-map", "0:v:0",
                            "-c", "copy", "-f", "framecrc", "-"], capture_output=True, text=True, errors="replace", timeout=180, **NOWIN)
    except Exception: return []
    tb, pts = 1 / 90000.0, []
    for ln in r.stdout.splitlines():
        m = re.match(r"#tb 0: (\d+)/(\d+)", ln)
        if m: tb = int(m.group(1)) / max(1, int(m.group(2))); continue
        if ln.startswith("#"): continue
        f = ln.split(",")
        if len(f) >= 6:
            try: pts.append(int(f[2]) * tb + t0)
            except ValueError: pass
    if len(pts) < 3: return []
    pts.sort()
    d = sorted(b - a for a, b in zip(pts, pts[1:]) if b > a)
    med = d[len(d) // 2] if d else 1 / 30
    out = []
    if lo > 0 and pts[0] > lo + min_gap and pts[0] < hi: out.append((lo, pts[0]))              # the picture only starts later
    for a, b in zip(pts, pts[1:]):
        if b - a >= min_gap and b > lo and a < hi: out.append((a + med, b))
    return out


def heal_segments(segs, holes, words, keep=0.12, min_cut=0.2, min_piece=0.3):
    """Cut the SILENT part of every video hole out of the clip (picture and sound together), so there is no frozen picture. Holes that
    have someone speaking in them are left alone: the sound is more important than the picture."""
    if not holes: return segs
    cuts = []
    for h0, h1 in holes:
        free = [(h0, h1)]
        for w in words:
            if w["end"] + keep <= h0: continue
            if w["start"] - keep >= h1: break
            s0, s1, nf = w["start"] - keep, w["end"] + keep, []
            for f0, f1 in free:
                if s1 <= f0 or s0 >= f1: nf.append((f0, f1)); continue
                if s0 > f0: nf.append((f0, s0))
                if s1 < f1: nf.append((s1, f1))
            free = nf
        cuts += [(f0, f1) for f0, f1 in free if f1 - f0 >= min_cut]
    out = []
    for a, b in segs:
        pieces = [(a, b)]
        for c0, c1 in cuts:
            nxt = []
            for p0, p1 in pieces:
                if c1 <= p0 or c0 >= p1: nxt.append((p0, p1)); continue
                if c0 > p0: nxt.append((p0, c0))
                if c1 < p1: nxt.append((c1, p1))
            pieces = nxt
        out += [(p0, p1) for p0, p1 in pieces if p1 - p0 >= min_piece]
    return out or segs


def quant_segs(segs, fps):
    """Every segment gets a whole number of frames, so picture and sound of each piece are EXACTLY as long as each other and the
    pieces add up without drift (captions, cuts and effects are timed on the same grid)."""
    return [(a, a + max(1, int(round((b - a) * fps))) / fps) for a, b in segs]


# ---------------- captions / layout ----------------
def ts(t): return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


_bgr = lambda h: h[4:6] + h[2:4] + h[0:2]                       # rrggbb -> bbggrr (ASS colour order)
_ASC = lambda c: "&H00" + _bgr(c).upper()
is_cjk = lambda t: any(0x3040 <= ord(c) <= 0x30FF or 0x3400 <= ord(c) <= 0x9FFF or 0xAC00 <= ord(c) <= 0xD7AF for c in t)


def aspect_of(W, H):
    return next((k for k, v in REF.items() if v == (W, H)), "9:16")


def phrases(words, max_words, max_chars, brk=.45, cjk=False):
    """Split the transcript into on-screen phrases: a long pause, the end of a sentence, or a full line starts a new one."""
    out, cur = [], []
    for w in words:
        if cur:
            chars = sum(len(x["w"]) + (0 if cjk else 1) for x in cur) + len(w["w"])
            if w["start"] - cur[-1]["end"] > brk or len(cur) >= max_words or chars > max_chars or ends_in(cur[-1]["w"], END_P):
                out.append(cur); cur = []
        cur.append(w)
    if cur: out.append(cur)
    return out


def two_lines(txt, cjk=False):
    """Break a long subtitle into two balanced lines (ASS \\N)."""
    lim = 11 if cjk else 26
    if len(txt) <= lim: return txt
    if cjk: return txt[:len(txt) // 2] + "\\N" + txt[len(txt) // 2:]
    sp = [i for i, c in enumerate(txt) if c == " "]
    if not sp: return txt
    i = min(sp, key=lambda k: abs(k - len(txt) / 2))
    return txt[:i] + "\\N" + txt[i + 1:]


def make_ass(words, censor, path, W, H, size, margin, hook=None, acc="ff4d8d", extra=(), o=None, safe=(0.0, 0.0, 0.0), dur=0.0):
    """W x H is a fixed reference canvas (1080x1920 / 1080x1350 / 1080x1080 / 1920x1080); libass scales it to whatever resolution is rendered.
    o = caption look: style (pop / karaoke / box / bounce / line), font, size %, position, text / highlight / edge colours."""
    o = get_opts(o); fam, _file, mult, bold = FONTS[o["cap_font"]]
    sz = max(20, int(size * mult * o["cap_size"] / 100)); K = min(W, H) / 1080
    asp = aspect_of(W, H); tall = H > W
    al, mv = {"mid": (5, 0), "high": (8, int(H * HIGH_MARGIN[asp]))}.get(o["cap_pos"], (2, margin))
    txt_c, hi_c, edge_c = _ASC(o["cap_text"]), _ASC(o["cap_hi"]), _ASC(o["cap_edge"])
    ol = max(3, round(sz * 7 / 88)); ha = {"tl": 7, "tr": 9, "bl": 1, "br": 3}[o["handle_pos"]]
    cx = _vm is not None                                              # 2.2 caption controls: outline thickness, shadow, text case, words at a time, translucent box, rainbow words
    if cx: ol = _vm.outline_size(ol, o["cap_outline"])
    shd = o["cap_shadow"] if cx else 2
    hook_mv = int(H * (.14 if tall else .08)); hs = max(22, int(34 * K * mult))
    sb, sr, st = safe
    h_mv = int(H * (.05 if ha < 7 else .045))
    h_mv = max(h_mv, int(H * (sb + .012))) if (sb and ha < 7) else max(h_mv, int(H * (st + .012))) if (st and ha >= 7) else h_mv      # keep the @name clear of the app's buttons
    h_mr = int(40 * K) + (int(W * sr) if ha == 3 else 0)
    hook_mv = max(hook_mv, int(H * (st + .03))) if st else hook_mv
    boxes = ""
    if cx and o["cap_box"]:                                           # a see-through dark box behind the words (strength 1-100)
        al_ = 255 - round(2.55 * o["cap_box"])
        boxes = (f"Style: DefaultB,{fam},{sz},{hi_c},{txt_c},&H{al_:02X}000000,&H00000000,{bold},0,0,0,100,100,0,0,3,{max(8, int(sz * .16))},0,{al},60,60,{mv},1\n"
                 f"Style: LineB,{fam},{int(sz * .72)},{txt_c},{txt_c},&H{al_:02X}000000,&H00000000,{bold},0,0,0,100,100,0,0,3,{max(6, int(sz * .12))},0,{al},70,70,{mv},1\n")
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,{fam},{sz},{hi_c},{txt_c},{edge_c},&H80000000,{bold},0,0,0,100,100,0,0,1,{ol},{shd},{al},60,60,{mv},1
Style: Box,{fam},{sz},{txt_c},{txt_c},{hi_c},&H00000000,{bold},0,0,0,100,100,0,0,3,{max(6, int(sz * .15))},0,{al},60,60,{mv},1
Style: Line,{fam},{int(sz * .72)},{txt_c},{txt_c},{edge_c},&H80000000,{bold},0,0,0,100,100,0,0,1,{_vm.outline_size(max(3, int(sz * .05)), o["cap_outline"]) if cx else max(3, int(sz * .05))},{round(shd / 2)},{al},70,70,{mv},1
Style: Hook,{fam},{int(sz * .8)},&H00FFFFFF,&H00FFFFFF,&H00{_bgr(acc).upper()},&H80000000,{bold},0,0,0,100,100,0,0,1,10,3,8,70,70,{hook_mv},1
Style: Handle,{fam},{hs},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,{bold},0,0,0,100,100,1,0,1,3,0,{ha},{int(40 * K)},{h_mr},{h_mv},1
Style: FX,Arial,40,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
{boxes}[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    san = lambda t: re.sub(r"[{}\\\r\n]", "", t)
    lines = list(extra)
    if hook:
        lines.append("Dialogue: 3,0:00:00.00,0:00:02.80,Hook,,0,0,0,,{\\fad(100,250)\\fscx55\\fscy55\\t(0,200,\\fscx100\\fscy100)}" + san(hook.upper().replace("\n", " ")))
    if o["handle"]:
        lines.append("Dialogue: 4,0:00:00.00,9:59:59.00,Handle,,0,0,0,,{\\alpha&H30&}" + san(o["handle"]))
    if o["cta"] and dur > 3.2:                       # "Follow for more" end card: a pill that pops up for the last couple of seconds
        t0 = max(1.0, dur - 2.6); cy = int(H * (.60 if tall else .66))
        txt = san(o["cta"]); txt = txt if is_cjk(txt) else txt.upper()
        lines.append(f"Dialogue: 6,{ts(t0)},{ts(dur)},Box,,0,0,0,,{{\\an5\\pos({W // 2},{cy})\\fad(220,160)\\fscx60\\fscy60\\t(0,260,\\fscx108\\fscy108)\\t(260,420,\\fscx100\\fscy100)}}{txt}")
    try:
        import vcfx
        lines += vcfx.ass_extras(o, dict(W=W, H=H, tall=tall, K=K, dur=dur, safe=safe, sz=sz, ts=ts, san=san, upper=lambda t: t if is_cjk(t) else t.upper()))
    except Exception as e: print("Overlay lines skipped:", str(e)[:100])
    try:
        import vcnew
        lines += vcnew.ass_extras21(o, dict(W=W, H=H, tall=tall, K=K, dur=dur, safe=safe, sz=sz, ts=ts, san=san, upper=lambda t: t if is_cjk(t) else t.upper()))
    except Exception as e: print("Text boxes skipped:", str(e)[:100])
    if cx:
        try: lines += _vm.react_lines(o, dict(W=W, H=H, tall=tall, dur=dur, ts=ts, san=san, sz=sz))
        except Exception as e: print("Reaction words skipped:", str(e)[:100])
    words = [w for w in words if w["w"].strip()]
    n = len(words); style = o["cap_style"]
    cjk = n > 0 and sum(is_cjk(w["w"]) for w in words) / n > .3           # Japanese / Chinese / Korean: no spaces, whole phrases
    if cjk and style in ("pop", "bounce"): style = "karaoke"
    upper = style != "line" and not cjk
    join = "" if cjk else " "
    case = o["cap_case"] if cx else "auto"
    mask = lambda w: "*" * len(w["w"]) if is_cens(w, censor) else (_vm.apply_case(san(w["w"]), case, upper) if cx else (san(w["w"]).upper() if upper else san(w["w"])))
    if o.get("cap_feel") and style != "type":                          # 2.3: laugh words yellow, scream words red, win words green ... (not in typewriter captions: letters are counted there)
        try:
            import vcmedia
            _m0 = mask
            mask = lambda w: _m0(w) if is_cens(w, censor) else vcmedia.feel_wrap(_m0(w), w["w"])
        except Exception as e: print("Feeling colours skipped:", str(e)[:80])
    NW = o["cap_words"] if cx else 0                                   # 0 = automatic
    rb = _vm.rainbow_colors(hi_c, txt_c) if (cx and o["cap_rainbow"]) else None
    if rb: c1r = lambda i: "{\\1c" + rb[i % len(rb)].replace("&H00", "&H") + "&}"
    emph = lambda w: clean(w["w"]) in HYPE or ends_in(w["w"], "!！") or (w["w"].isupper() and len(w["w"]) > 2)
    c1 = lambda c: "{\\1c" + c.replace("&H00", "&H") + "&}"                # \1c override from an ASS colour string
    boxed = bool(boxes)
    if style in ("pop", "bounce", "box"):
        name = "Box" if style == "box" else "Default"
        i = 0
        gap_to_next = lambda k: (words[k + 1]["start"] if k + 1 < n else words[k]["end"] + .3) - words[k]["start"]
        while i < n:
            w = words[i]
            if NW == 1 or (NW == 0 and gap_to_next(i) >= .30):        # normal speed: ONE word at a time, pops in
                nxt = words[i + 1]["start"] if i + 1 < n else w["end"] + .3
                end = max(w["end"] + .06, w["start"] + .2)
                end = min(end, nxt) if nxt > w["start"] + .15 else end
                big = 138 if emph(w) else 100
                if style == "bounce":
                    pop = (f"{{\\fscx60\\fscy60\\frz-7\\t(0,90,\\fscx{big + 22}\\fscy{big + 22}\\frz5)\\t(90,190,\\fscx{big}\\fscy{big}\\frz-2)\\t(190,300,\\frz0)}}"
                           + c1(hi_c if i % 2 == 0 else txt_c))
                elif style == "box":
                    pop = f"{{\\fscx70\\fscy70\\t(0,100,\\fscx{big}\\fscy{big})}}"
                else:
                    pop = f"{{\\fscx55\\fscy55\\t(0,80,\\fscx{big + 14}\\fscy{big + 14})\\t(80,170,\\fscx{big}\\fscy{big})}}"
                    if rb: pop += c1r(i)
                    elif o["cap_emph"]: pop += c1(hi_c if emph(w) else txt_c)
                lines.append(f"Dialogue: 2,{ts(w['start'])},{ts(end)},{name},,0,0,0,,{pop}{mask(w)}")
                i += 1
            else:                            # fast speech: condense into groups of up to 3
                grp = []
                if NW >= 2:                  # the user chose how many words show at once: they stay together unless there is a real pause
                    while i < n and len(grp) < NW and (not grp or words[i]["start"] - grp[-1]["end"] < .6):
                        grp.append(words[i]); i += 1
                else:
                    while i < n and len(grp) < 3 and gap_to_next(i) < .30:
                        grp.append(words[i]); i += 1
                if style == "box":
                    body = " ".join(mask(g) for g in grp); pop = "{\\fscx90\\fscy90\\t(0,100,\\fscx100\\fscy100)}"
                else:                        # active word lit in the highlight colour
                    body = ""
                    for k, g in enumerate(grp):
                        nxt = grp[k + 1]["start"] if k + 1 < len(grp) else g["end"]
                        body += f"{{\\k{max(1, round((nxt - g['start']) * 100))}}}{mask(g)} "
                    body = body.strip(); pop = "{\\fscx118\\fscy118\\t(0,120,\\fscx100\\fscy100)}"
                lines.append(f"Dialogue: 2,{ts(grp[0]['start'])},{ts(grp[-1]['end'] + .05)},{name},,0,0,0,,{pop}{body}")
    elif style == "type":                    # typewriter: a short phrase types itself out while it is said (the unseen letters keep their place)
        for ph in phrases(words, 3 if cjk else (NW or 4), 12 if cjk else 22, cjk=cjk):
            end_ph = ph[-1]["end"] + .25
            steps = []                                                       # (time, visible letters in the phrase)
            shown = 0
            for k, w in enumerate(ph):
                txt_w = mask(w); L = len(txt_w)
                t0 = w["start"]; t1 = min(ph[k + 1]["start"] if k + 1 < len(ph) else w["end"], t0 + .55)
                t1 = max(t1, t0 + .08 * min(L, 4))
                for j in range(1, L + 1):
                    steps.append((t0 + (t1 - t0) * (j - 1) / max(1, L), shown + j))
                shown += L + (0 if cjk else 1)
            full = join.join(mask(x) for x in ph)
            for si, (t0, vis) in enumerate(steps):
                t1 = steps[si + 1][0] if si + 1 < len(steps) else end_ph
                if t1 - t0 < .02: continue
                shown_txt, hidden = full[:vis], full[vis:]
                body = shown_txt + ("{\\alpha&HFF&}" + hidden if hidden.strip() else "")
                lines.append(f"Dialogue: 2,{ts(t0)},{ts(t1)},Default,,0,0,0,,{{\\alpha&H00&}}{body}")
    elif style == "karaoke":                 # a short phrase stays on screen, the word being said is lit
        for ph in phrases(words, 3 if cjk else (NW or 4), 12 if cjk else 22, cjk=cjk):
            for k, w in enumerate(ph):
                t0 = ph[0]["start"] if k == 0 else w["start"]
                t1 = ph[k + 1]["start"] if k + 1 < len(ph) else max(w["end"] + .15, w["start"] + .3)
                body = join.join(((c1r(k) if rb else c1(hi_c)) if j == k else c1(txt_c)) + mask(x) for j, x in enumerate(ph))
                pop = "{\\fscx88\\fscy88\\t(0,110,\\fscx100\\fscy100)}" if k == 0 else ""
                lines.append(f"Dialogue: 2,{ts(t0)},{ts(t1)},Default,,0,0,0,,{pop}{body}")
    else:                                    # line: calm subtitles
        for ph in phrases(words, NW or 7, 20 if cjk else 52, cjk=cjk):
            body = two_lines(join.join(mask(x) for x in ph), cjk)
            lines.append(f"Dialogue: 2,{ts(ph[0]['start'])},{ts(ph[-1]['end'] + .25)},Line,,0,0,0,,{{\\fad(90,90)}}{body}")
    if boxed:                                  # the see-through box is its own layer under the words (one box per line, not one per colour change)
        under = []
        for ln_ in lines:
            m_ = re.match(r"(Dialogue: )2(,[^,]*,[^,]*,)(Default|Line)(,,0,0,0,,)(.*)$", ln_)
            if m_: under.append(f"{m_.group(1)}1{m_.group(2)}{m_.group(3)}B{m_.group(4)}{{\\1a&HFF&}}" + re.sub(r"\\1c&H[0-9A-Fa-f]+&|\\k\d+", "", m_.group(5)))
        lines = under + lines
    Path(path).write_text(head + "\n".join(lines), encoding="utf-8")


def _shape(pts):
    """Polygon(s) -> (ASS drawing, width, height) translated so the drawing starts at 0,0."""
    flat = [p for poly in pts for p in poly]
    x0, y0 = min(x for x, _ in flat), min(y for _, y in flat)
    path = " ".join("m " + " l ".join(f"{x - x0:.0f} {y - y0:.0f}" for x, y in poly) for poly in pts)
    return path, max(x for x, _ in flat) - x0, max(y for _, y in flat) - y0


def _heart(R):
    pts = []
    for k in range(36):
        t = 2 * math.pi * k / 36
        pts.append((16 * math.sin(t) ** 3 * R / 17, -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)) * R / 17))
    return _shape([pts])


def _star(R):
    return _shape([[((R if k % 2 == 0 else R * .26) * math.cos(math.pi * k / 4 - math.pi / 2), (R if k % 2 == 0 else R * .26) * math.sin(math.pi * k / 4 - math.pi / 2)) for k in range(8)]])


def _ring(ro, ri):
    outer = [(ro * math.cos(2 * math.pi * k / 40), ro * math.sin(2 * math.pi * k / 40)) for k in range(40)]
    inner = [(ri * math.cos(-2 * math.pi * k / 40), ri * math.sin(-2 * math.pi * k / 40)) for k in range(40)]     # opposite winding = hole
    return _shape([outer, inner])


def _circle(cx, cy, r, n=18):
    return [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def _bang(R):
    """Manga surprise mark: a tapered bar with a dot under it."""
    bar = [(-.30 * R, 0), (.30 * R, 0), (.20 * R, 1.35 * R), (-.20 * R, 1.35 * R)]
    return _shape([bar, _circle(0, 1.78 * R, .24 * R)])


def _drop(R):
    """Sweat drop (pointed at the top)."""
    pts = [(R * math.sin(t) * math.sin(t / 2), -R * math.cos(t)) for t in (2 * math.pi * k / 28 for k in range(28))]
    return _shape([pts])


def _anger(R):
    """Anger mark: four curved bars around an empty centre."""
    polys = []
    for q in range(4):
        base = math.radians(45 + 90 * q)
        a0, a1 = base - math.radians(32), base + math.radians(32)
        outer = [(R * math.cos(a0 + (a1 - a0) * k / 8), R * math.sin(a0 + (a1 - a0) * k / 8)) for k in range(9)]
        inner = [(.55 * R * math.cos(a1 - (a1 - a0) * k / 8), .55 * R * math.sin(a1 - (a1 - a0) * k / 8)) for k in range(9)]
        polys.append(outer + inner)
    return _shape(polys)


def _petal(R):
    """Sakura petal: a rounded leaf with a notch at the tip."""
    pts = []
    for k in range(20):
        t = 2 * math.pi * k / 20
        x, y = .62 * R * math.cos(t), R * math.sin(t)
        if k == 15: y *= .72                      # the notch (top of the shape)
        pts.append((x, y))
    return _shape([pts])


def _rays(rnd, cx, cy, RW, RH, n=36):
    polys = []
    for k in range(n):
        th = 2 * math.pi * (k + rnd.uniform(-.4, .4)) / n; dx, dy = math.cos(th), math.sin(th)
        tx = ((RW - cx) / dx if dx > 1e-6 else cx / -dx if dx < -1e-6 else 1e9)
        ty = ((RH - cy) / dy if dy > 1e-6 else cy / -dy if dy < -1e-6 else 1e9)
        d = min(tx, ty); rt, ro, w = d * rnd.uniform(.42, .72), d * 1.2, rnd.uniform(.012, .04)
        polys.append([(cx + dx * rt, cy + dy * rt), (cx + math.cos(th - w) * ro, cy + math.sin(th - w) * ro), (cx + math.cos(th + w) * ro, cy + math.sin(th + w) * ro)])
    return polys


def fx_ass(fx, E, dur, RW, RH, acc, I):
    """Cute / anime overlays as vector drawings (speed lines, shockwave ring, heart + sparkle burst, twinkling sparkles).
    Returns ASS Dialogue lines on the 'FX' style; nothing needs a font so they look the same on every PC."""
    out, rnd = [], random.Random(7 + len(E))
    bgr = (acc[4:6] + acc[2:4] + acc[0:2]).upper(); cx, cy = RW / 2, RH * (.44 if RH > RW else .5)
    pal = [bgr, "FFFFFF", "CFB3FF", "FFFFFF"]; K = min(RW, RH) / 1080

    def dl(t0, t1, pos, tags, shape, layer=0):
        an = "" if "\\an" in pos else "\\an7"
        bord = "" if "\\bord" in tags else "\\bord0"
        out.append(f"Dialogue: {layer},{ts(max(0, t0))},{ts(t1)},FX,,0,0,0,,{{{an}{pos}{tags}{bord}\\shad0\\p1}}{shape}")
    if fx.get("lines") and E:                      # anime focus / speed lines flickering for a third of a second
        variants = []
        for _ in range(3):
            polys = _rays(rnd, cx, cy, RW, RH)
            variants.append(" ".join("m " + " l ".join(f"{x:.0f} {y:.0f}" for x, y in poly) for poly in polys))
        for e in E:
            for j in range(6): dl(e + j * .055, e + (j + 1) * .055, "\\pos(0,0)", f"\\1c&HFFFFFF&\\1a&H{0x50 + j * 0x16:02X}&", variants[j % 3], 0)
    if fx.get("ring") and E:                       # expanding shockwave ring
        for e in E:
            for j in range(6):
                ro = (110 + j * 150) * K; ri = ro - max(10, (46 - j * 6)) * K
                shp, w, h = _ring(ro, ri)
                dl(e + j * .05, e + (j + 1) * .05, f"\\pos({cx - w / 2:.0f},{cy - h / 2:.0f})", f"\\1c&H{bgr if j % 2 else 'FFFFFF'}&\\1a&H{0x20 + j * 0x24:02X}&", shp, 0)
    if fx.get("hearts") and E:                     # hearts + stars pop out of the moment
        for e in E:
            for k in range(7 + int(2 * I)):
                heart = k % 3 != 2; R = rnd.uniform(24, 50) * K * min(1.4, .8 + I * .4)
                shp, w, h = _heart(R) if heart else _star(R * 1.1)
                th = rnd.uniform(0, 2 * math.pi); dist = rnd.uniform(260, 540) * K
                x0, y0 = cx - w / 2, cy - h / 2
                dl(e, e + .95, f"\\move({x0:.0f},{y0:.0f},{x0 + dist * math.cos(th):.0f},{y0 + dist * math.sin(th) - 90 * K:.0f},0,800)",
                   f"\\fad(60,380)\\1c&H{rnd.choice(pal)}&", shp, 1)
    if fx.get("sparkle") and dur > 1:              # gentle twinkling sparkles all the way through
        for _ in range(min(60, int(dur * 1.5 * min(I, 1.5)))):
            t0 = rnd.uniform(0, max(.1, dur - .6)); life = rnd.uniform(.7, 1.3)
            shp, w, h = _star(rnd.uniform(14, 32) * K)
            x0, y0 = rnd.uniform(.05, .93) * RW, rnd.uniform(.05, .88) * RH
            dl(t0, t0 + life, f"\\move({x0:.0f},{y0:.0f},{x0 + rnd.uniform(-30, 30):.0f},{y0 - rnd.uniform(30, 90) * K:.0f},0,{int(life * 1000)})",
               f"\\fad(230,330)\\blur1\\1c&H{rnd.choice(pal)}&", shp, 1)
    if fx.get("marks") and E:                      # manga reaction marks next to the face: !, sweat drop, anger mark, note
        kinds = [("bang", _bang, _bgr("ff4d8d").upper()), ("drop", _drop, _bgr("7fd6ff").upper()), ("anger", _anger, _bgr("ff3b4d").upper())]
        for k, e in enumerate(E):
            nm, fn, col = kinds[k % 3]
            shp, w, h = fn(70 * K * min(1.3, .8 + I * .4))
            mx, my = cx + RW * (.20 if k % 2 == 0 else -.20), RH * (.20 if RH > RW else .22)
            dl(e, e + 1.05, f"\\an5\\pos({mx:.0f},{my:.0f})\\frz{-14 if k % 2 == 0 else 14}",
               f"\\fscx0\\fscy0\\t(0,130,\\fscx135\\fscy135)\\t(130,260,\\fscx100\\fscy100)\\fad(0,260)\\1c&H{col}&\\bord{max(3, round(6 * K))}\\3c&HFFFFFF&", shp, 2)
    if fx.get("confetti") and E:                   # party confetti falls from the top after the first big moments
        for e in E[:2]:
            for _ in range(38):
                kind = rnd.random()
                shp, w, h = _shape([_circle(0, 0, rnd.uniform(8, 14) * K, 10)]) if kind < .3 else \
                    _shape([[(0, 0), (rnd.uniform(18, 30) * K, 0), (rnd.uniform(18, 30) * K, rnd.uniform(10, 17) * K), (0, rnd.uniform(10, 17) * K)]])
                x0 = rnd.uniform(.02, .98) * RW; x1 = x0 + rnd.uniform(-160, 160) * K; life = rnd.uniform(1.5, 2.6); t0 = e + rnd.uniform(0, .45)
                dl(t0, t0 + life, f"\\an5\\move({x0:.0f},{-30 * K:.0f},{x1:.0f},{RH + 30 * K:.0f},0,{int(life * 1000)})",
                   f"\\1c&H{rnd.choice(['8D4DFF', '4DD8FF', 'FFD24D', 'FF8CB3', '9EFF6B', 'FFFFFF'])}&\\t(0,{int(life * 1000)},\\frz{rnd.randint(-540, 540)})", shp, 1)
    if fx.get("petals") and dur > 1:               # sakura petals drifting down all the way through
        for _ in range(min(45, int(dur * 1.1 * min(I, 1.5)) + 3)):
            life = rnd.uniform(4.0, 6.5); t0 = rnd.uniform(-life * .6, max(.1, dur - 1))
            shp, w, h = _petal(rnd.uniform(15, 27) * K)
            x0 = rnd.uniform(.0, 1.1) * RW; x1 = x0 - rnd.uniform(120, 360) * K
            dl(max(0, t0), min(dur, t0 + life), f"\\an5\\move({x0:.0f},{-40 * K:.0f},{x1:.0f},{RH + 40 * K:.0f},0,{int(life * 1000)})",
               f"\\1c&H{rnd.choice(['D5B7FF', 'E6C8FF', 'FFFFFF', 'C9A0FF'])}&\\1a&H28&\\t(0,{int(life * 1000)},\\frz{rnd.randint(-420, 420)}\\fscx60)", shp, 1)
    return out


LAYOUTS = ("blur", "stack", "fill", "pip", "camfull", "filler", "stackb", "side", "custom")


def needs_cam(layout, o=None):
    """True for the layouts that show the cam: they fall back to the blurred layout when no cam area is picked."""
    if layout in ("stack", "pip", "camfull", "stackb", "side"): return True
    if layout != "custom": return False
    try:
        import vcnew; return vcnew.layout_needs_cam(layout, o)
    except Exception: return False
IMG_EXT = (".png", ".gif", ".webp", ".jpg", ".jpeg", ".bmp")


def safe_zone(o, aspect):
    """(bottom, right, top) fractions of the frame that TikTok / Shorts / Reels cover with their buttons and text. Only vertical video has one."""
    if aspect != "9:16": return (0.0, 0.0, 0.0)
    p = PLATFORMS.get(o.get("platform", "any"), PLATFORMS["any"]); return (p["bottom"], p["right"], p["top"])


def sticker_files(spec, limit=6):
    """'file1|folder|file2' -> existing image files (a folder contributes every image in it)."""
    out = []
    for part in str(spec or "").split("|"):
        part = part.strip()
        if not part: continue
        if os.path.isdir(part):
            try: out += sorted(os.path.join(part, f) for f in os.listdir(part) if f.lower().endswith(IMG_EXT))
            except OSError: pass
        elif os.path.isfile(part) and part.lower().endswith(IMG_EXT): out.append(part)
    return list(dict.fromkeys(out))[:limit]


def media_kind(path):
    """'image' (still card) or 'video' for an intro / outro file; None when it is not usable."""
    if not path or not os.path.isfile(path): return None
    p = path.lower()
    return "image" if p.endswith(IMG_EXT) and not p.endswith(".gif") else "video"


def pip_size(W, H):
    D = max(2, int(min(W, H) * .34) // 2 * 2)
    return D, max(4, D // 28), int(min(W, H) * .045)             # bubble size, white ring, edge gap



def _disc_mask(d, name, fps):
    """A d x d anti-aliased white disc as an endless gray stream. The shape is calculated ONCE (one frame) and then repeated - cheap."""
    return (f"color=c=black:s={d}x{d}:r={fps},trim=end_frame=1,format=gray,"
            f"geq=lum='255*clip({d}/2-hypot(X-{d}/2+.5,Y-{d}/2+.5)+.5,0,1)',loop=loop=-1:size=1:start=0,setpts=N/({fps}*TB)[{name}]")


def reframe(layout, cam, W, H, pip_pos="br", o=None, ex=None, safe=(0.0, 0.0, 0.0)):
    """Input is [v]; output is [vv] at exactly W x H.
    blur = whole game over a blurred copy (or a colour / picture), stack = cam on top + game below, fill = centre crop,
    pip = game full-screen + round cam bubble, camfull = just the cam area filling the frame, filler = cam on top + your own looping video below.
    ex = indexes of extra ffmpeg inputs ({'filler': n, 'bgimg': n}); safe = (bottom, right, top) platform keep-out fractions."""
    o, ex, FPS = o or {}, ex or {}, OUT["fps"]
    if layout == "wide":
        return f"[v]scale={W}:{H}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black[vv]"
    if layout == "fill":
        return f"[v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}[vv]"
    if layout == "camfull" and cam:
        return f"[v]crop={cam},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}[vv]"
    if layout == "stack" and cam:
        ch = round(H / 3 / 2) * 2; gh = H - ch
        return (f"[v]split[g][c];[c]crop={cam},scale={W}:{ch}:force_original_aspect_ratio=increase,crop={W}:{ch}[ct];"
                f"[g]scale={W}:{gh}:force_original_aspect_ratio=increase,crop={W}:{gh}[gb];[ct][gb]vstack[vv]")
    if layout in ("stackb", "side", "custom"):                  # 2.1: cam at the bottom, cam at the side, or the boxes you drew in the layout designer
        try:
            import vcnew
            spec = vcnew.layout_spec(layout, o)
            if spec: return vcnew.box_graph(spec, cam, W, H, FPS, o, _disc_mask, o.get("bg_color", "1b1230"))
        except Exception as e: print("Layout skipped:", str(e)[:100])
        layout = "blur"
    if layout == "filler" and ex.get("filler"):
        ch = round(H * .46 / 2) * 2; fh = H - ch
        top = f"[v]crop={cam}," if cam else "[v]"
        return (f"{top}scale={W}:{ch}:force_original_aspect_ratio=increase,crop={W}:{ch},setsar=1,format=yuv420p[ct];"
                f"[{ex['filler']}:v]fps={FPS},scale={W}:{fh}:force_original_aspect_ratio=increase,crop={W}:{fh},setsar=1,format=yuv420p[fb];"
                f"[ct][fb]vstack=shortest=1[vv]")
    if layout == "pip" and cam:
        D, ring, pad = pip_size(W, H); Dc = max(2, D - 2 * ring); sb, sr, st = safe
        x = f"{pad}" if pip_pos in ("tl", "bl") else f"W-w-{pad + int(W * sr)}"
        y = f"{int(H * max(.05, st + .01 if st else 0))}" if pip_pos in ("tl", "tr") else f"H-h-{int(H * max(.06, sb))}"
        return (f"[v]split[g][c];[g]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}[gb];"
                f"[c]crop={cam},scale={Dc}:{Dc}:force_original_aspect_ratio=increase,crop={Dc}:{Dc},format=yuv420p[cs];"
                f"{_disc_mask(Dc, 'm2', FPS)};{_disc_mask(D, 'm1', FPS)};"
                f"[cs][m2]alphamerge[cd];color=c=white:s={D}x{D}:r={FPS},format=yuv420p[ws];[ws][m1]alphamerge[wd];"
                f"[wd][cd]overlay=x={ring}:y={ring}:format=auto:shortest=1[bub];[gb][bub]overlay=x={x}:y={y}:format=auto:shortest=1[vv]")
    bg = o.get("bg_style", "blur")
    if bg == "color" or (bg == "image" and ex.get("bgimg")):
        src = (f"color=c=0x{o.get('bg_color', '1b1230')}:s={W}x{H}:r={FPS}[bg]" if bg == "color" else
               f"[{ex['bgimg']}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,format=yuv420p,loop=loop=-1:size=1:start=0,setpts=N/({FPS}*TB)[bg]")
        return (f"[v]scale={W}:{H}:force_original_aspect_ratio=decrease:force_divisible_by=2[fg];{src};"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=1[vv]")
    try:                                                       # 2.3: blur strength and brightness of the background ("normal" and 0 are exactly what 2.2 did)
        import vcmedia
        chain = vcmedia.blur_chain(o.get("bg_blur", "normal"), W, H, o.get("bg_dim", 0))
    except Exception:
        sw, sh = max(2, W // 10 * 2), max(2, H // 10 * 2)      # blur a tiny copy: fast and just as smooth
        chain = f"scale={sw}:{sh},boxblur=5:2,scale={W}:{H}"
    return (f"[v]split[b][f];[b]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},{chain}[bg];"
            f"[f]scale={W}:{H}:force_original_aspect_ratio=decrease:force_divisible_by=2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2[vv]")


def _make_sound(name, args, dur):
    p = os.path.join(tempfile.gettempdir(), name)
    if not os.path.exists(p):
        part = p[:-4] + ".part.wav"
        run_ff(args + ["-c:a", "pcm_s16le", part], dur); os.replace(part, p)
    return p


# impact sounds, synthesised with ffmpeg (nothing to download, nothing copyrighted)
SFX_EXPR = {
    "boom": ("vclip_hit.wav", "0.9*sin(2*PI*(50+140*exp(-25*t))*t)*exp(-6*t)", .7),
    "cute": ("vclip_hit_cute.wav", "0.55*sin(2*PI*(700+1600*t)*t)*exp(-9*t)+0.3*sin(2*PI*2093*t)*exp(-12*t)*gte(t,0.04)", .5),
    "anime": ("vclip_hit_anime.wav", "0.8*sin(2*PI*(55+80*exp(-30*t))*t)*exp(-8*t)+0.22*sin(2*PI*1568*t)*exp(-7*t)+0.18*sin(2*PI*2093*t)*exp(-7*t)", .8),
    "retro": ("vclip_hit_retro.wav", "0.32*sgn(sin(2*PI*if(lt(t,.06),523,if(lt(t,.12),659,if(lt(t,.18),784,1047)))*t))*exp(-3.5*t)", .45),
}


VOICE_CLEAN = ("highpass=f=75,afftdn=nr=10:nf=-38:tn=1,acompressor=threshold=0.1:ratio=3:attack=15:release=250:makeup=1.5,"
               "atrim=start=0.027,asetpts=PTS-STARTPTS,apad=pad_dur=0.027")     # the denoiser delays the sound by ~27 ms: take it back out


def hit_path(pack="boom"):
    name, expr, d = SFX_EXPR.get(pack, SFX_EXPR["boom"])
    return _make_sound(name, ["-f", "lavfi", "-i", f"aevalsrc='{expr}':d={d}:s=48000"], d)


def whoosh_path():
    return _make_sound("vclip_whoosh.wav", ["-f", "lavfi", "-i", "anoisesrc=d=0.4:c=pink:a=0.6:r=48000,highpass=f=500,afade=t=in:d=0.18,afade=t=out:st=0.18:d=0.22"], .4)


def sfx_label(pack):
    """(name, one-line description) of a sound pack, for the app."""
    if pack in SFX_FILE_PACKS: return SFX_FILE_PACKS[pack].get("label", pack), SFX_FILE_PACKS[pack].get("about", "")
    return SFX_ABOUT.get(pack, (pack, ""))


def hit_paths(pack="boom", n=1):
    """The sound files for a pack's impact hits. A pack made from recordings gives up to 3 different hits, so one clip does not repeat a single sound."""
    P = SFX_FILE_PACKS.get(pack)
    if not P: return [hit_path(pack)]
    hs = [os.path.join(SFX_DIR, h["file"]) for h in P["hits"]]
    random.shuffle(hs)
    return hs[:max(1, min(3, n))]


def whoosh_choices(pack="boom"):
    """[(file, seconds from the start of the file to its loudest point)] - the whoosh is placed so that point lands on the cut."""
    P = SFX_FILE_PACKS.get(pack)
    out = [(os.path.join(SFX_DIR, w["file"]), float(w.get("peak", .1))) for w in (P or {}).get("whoosh", []) if os.path.isfile(os.path.join(SFX_DIR, w["file"]))]
    return out or [(whoosh_path(), .12)]


def sfx_preview(pack, dest):
    """A short demo of a sound pack (three hits and a whoosh) as a .wav file. Returns dest, or "" if it could not be made."""
    try:
        hp = hit_paths(pack, 3); hp = (hp * 3)[:3]; wp = whoosh_choices(pack)[0][0]
        args, parts = [], []
        for i, p in enumerate(hp + [wp]):
            args += ["-i", p]; parts.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,volume={0.6 if i < 3 else 0.5},apad=pad_dur={0.55 if i < 3 else 0.1}[p{i}]")
        g = ";".join(parts) + ";" + "".join(f"[p{i}]" for i in range(4)) + "concat=n=4:v=0:a=1[o]"
        run_ff(args + ["-filter_complex", g, "-map", "[o]", "-c:a", "pcm_s16le", dest], 3)
        return dest if os.path.isfile(dest) else ""
    except Exception: return ""


# ---------------- background music: your own file or folder (the app brings no music of its own) ----------------
def music_choices(spec):
    """Every audio file a music setting can mean: a folder = every song in it (and its sub-folders), a file = just that file.
    Anything else (an empty setting, a missing path, the old "lib:" values of an early 1.8 beta) means no music."""
    spec = (spec or "").strip().strip('"')
    if not spec or spec.startswith("lib:"): return []
    if os.path.isdir(spec):
        out = []
        for d, dirs, files in os.walk(spec):
            dirs.sort()
            out += [os.path.join(d, f) for f in sorted(files) if f.lower().endswith(AUDIO_EXT) and not f.startswith(".")]
            if len(out) > 3000: break
        return out
    return [spec] if os.path.isfile(spec) else []


def music_count(spec): return len(music_choices(spec))


def pick_music(spec, exclude=()):
    """One readable track for the setting ("" when there is none). A folder gives a different song each time."""
    cands = music_choices(spec)
    if not cands: return ""
    pool = [c for c in cands if c not in exclude] or cands
    for _ in range(6 if len(pool) > 1 else 1):
        c = random.choice(pool)
        if probe_info(c)["dur"] >= (15 if len(pool) > 1 else 1): return c
    return ""


_LOUD = {}


def track_gain_db(path, target=-14.0):
    """How many dB a track has to change to sit at `target` LUFS, so music from different places is equally loud before the volume % is applied.
    Measured once per file and remembered. Returns 0 if it cannot be measured."""
    try: st = os.stat(path)
    except OSError: return 0.0
    key = f"{os.path.abspath(path)}|{st.st_size}|{int(st.st_mtime)}"
    if key in _LOUD: return _LOUD[key]
    cf = os.path.join(CACHE_DIR, "music_loudness.json"); disk = _load_json(cf)
    if key in disk: _LOUD[key] = float(disk[key]); return _LOUD[key]
    g = 0.0
    try:
        r = subprocess.run([FF, "-hide_banner", "-nostats", "-t", "240", "-i", path, "-vn", "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True, errors="replace", **NOWIN)
        m = re.findall(r"\bI:\s+(-?[\d.]+)\s+LUFS", r.stderr)
        if m: g = max(-18.0, min(12.0, target - float(m[-1])))
    except Exception: g = 0.0
    _LOUD[key] = g
    if g:
        try:
            disk[key] = g
            if len(disk) > 400: disk = dict(list(disk.items())[-300:])
            os.makedirs(CACHE_DIR, exist_ok=True); tmp = cf + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f: json.dump(disk, f)
            os.replace(tmp, cf)
        except Exception: pass
    return g


def music_bed(spec, dur, tmp):
    """The music for a video that lasts `dur` seconds: (file, loop_it, gain_db) or None.
    One track is looped; several (a folder) are played one after the other with cross-fades, in a new order each time."""
    cands = music_choices(spec)
    if not cands: return None
    if len(cands) == 1:
        return (cands[0], True, track_gain_db(cands[0])) if probe_info(cands[0])["dur"] > 0 else None
    order, got, total = [], [], 0.0
    pool = cands[:]; random.shuffle(pool)
    tries = 0
    while total < dur + 4 and len(order) < 14 and tries < 40:
        tries += 1
        if not pool: pool = cands[:]; random.shuffle(pool)
        c = pool.pop(); d = probe_info(c)["dur"]
        if d < 12: continue
        order.append(c); got.append(d); total += d - (3 if order[1:] else 0)
    if not order: return None
    if len(order) == 1: return (order[0], True, track_gain_db(order[0]))
    args, parts = [], []
    for i, c in enumerate(order):
        args += ["-i", os.path.abspath(c)]
        parts.append(f"[{i}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,volume={track_gain_db(c):.1f}dB[a{i}]")
    chain, last = [], "a0"
    for i in range(1, len(order)):
        chain.append(f"[{last}][a{i}]acrossfade=d=3:c1=tri:c2=tri[x{i}]"); last = f"x{i}"
    bed = os.path.join(tmp, "music_bed.m4a")
    run_ff(args + ["-filter_complex", ";".join(parts + chain), "-map", f"[{last}]", "-t", f"{dur + 2:.1f}", "-c:a", "aac", "-b:a", "192k", bed], dur)
    return (bed, False, 0.0)


def music_preview(path, dest, secs=14):
    """A short taste of a track at the loudness it will have in a video (.wav). Returns dest, or "" if it could not be made."""
    try:
        d = probe_info(path)["dur"]; start = max(0.0, min(d * .25, d - secs - 1)) if d > secs * 2 else 0.0
        run_ff(["-ss", f"{start:.1f}", "-t", str(secs), "-i", path, "-vn", "-af", f"volume={track_gain_db(path) - 4:.1f}dB,afade=t=in:d=0.4,afade=t=out:st={secs - 1.2}:d=1.2",
                "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", dest], secs)
        return dest if os.path.isfile(dest) else ""
    except Exception: return ""


# ---------------- render (one contiguous range, with effects) ----------------
# ---------------- chibi emotes (story time): the plan is made from what is said; see vcemotes.py ----------------
def vcemotes_small(path):
    try:
        import vcemotes; return vcemotes.small_copy(path, 640)
    except Exception: return path


def untmap(segs, t):
    """Clip time -> source time (the other way round from tmap)."""
    off = 0.0
    for a, b in segs:
        if t < off + (b - a) or (a, b) == segs[-1]: return a + max(0.0, min(t - off, b - a))
        off += b - a
    return segs[0][0] if segs else 0.0


def emote_clip_plan(o, words, segs, events, seed=0):
    """What the emote plan of one clip looks like (items in source time) - or None when the emotes are off or nothing fits."""
    import vcemotes
    segs = quant_segs(segs, OUT["fps"])
    ow, d = remap(words, segs)
    ev = [t for t in (tmap(segs, e) for e in (events or [])) if t is not None]
    res = vcemotes.plan(ow, d, ev, level=o["emote_level"], burst=o["emote_burst"], seed=seed)
    for it in res["items"]: it["at"] = round(untmap(segs, it["t"]), 3)
    return res


def emote_plans(o, words, clips, review=None):
    """clips = [dict(k, label, start, segs, events)] -> {k: [items]}, or None when emotes are off. `review` (the app's plan window) may change the plan."""
    if not (o["emotes"] or o["emote_cover"]): return None
    try: import vcemotes
    except Exception as e: print("Emotes skipped:", str(e)[:100]); return None
    vcemotes.reset_rotation()
    plans, shown, miss = {}, [], {}
    for i, c in enumerate(clips):
        try:
            r = emote_clip_plan(o, words, c["segs"], c.get("events"), seed=i + 1)
        except Exception as e:
            print("Emotes skipped for one clip:", str(e)[:100]); plans[c["k"]] = []; continue
        plans[c["k"]] = r["items"]
        for k_, n_ in r["missing"].items(): miss[k_] = miss.get(k_, 0) + n_
        shown.append(dict(k=c["k"], label=c.get("label") or f"Clip {i + 1}", start=c.get("start", 0.0), dur=kept_len(quant_segs(c["segs"], OUT["fps"])),
                          items=[dict(it) for it in r["items"]], heard=r["heard"], segs=c["segs"]))
    if callable(review) and shown:
        try: edited = review(shown) or {}
        except BaseException as e:
            if "Cancelled" in str(e): raise
            edited = {}; print("(emote check skipped:", str(e)[:80] + ")")
        by = {c["k"]: c for c in clips}
        for k_, items in edited.items():
            if k_ not in by: continue
            sg = quant_segs(by[k_]["segs"], OUT["fps"])
            for it in items: it["at"] = round(untmap(sg, float(it["t"])), 3)
            plans[k_] = items
    n = sum(len(v) for v in plans.values())
    labels = {k: v[0] for k, v in vcemotes.EMO.items()}
    try:
        if not vcemotes.by_feeling(): print("Chibi emotes are on, but you haven't added any chibi pictures yet - open the Chibi emotes tab, press My emotes and add yours.")
    except Exception: pass
    print(f"Emotes: {n} picture{'s' if n != 1 else ''} planned.")
    if miss:
        print("I also heard " + ", ".join(f"{m}x {labels.get(k, k)}" for k, m in sorted(miss.items(), key=lambda x: -x[1])[:4]) + " - add a picture for that feeling (Chibi emotes tab -> My emotes) to use it.")
    return plans


def emote_motion(tag, t0, W, H, side):
    """How a picture moves while it is up: (extra x, extra y, rotation in radians as a function of the picture's own time) as ffmpeg expressions."""
    import vcemotes
    u = f"max(0,t-{t0:.3f})"
    m = vcemotes.MOTION.get(tag, "bob")
    if m == "bounce": return "0", f"-{.032 * H:.1f}*abs(sin(8.5*{u}))*exp(-.35*{u})", "0.05*sin(8.5*t)"
    if m == "shake": return f"{.010 * W:.1f}*sin(58*{u})*(.4+.6*exp(-2*{u}))", "0", "0"
    if m == "jump": return "0", f"if(lt({u},.3),-{.06 * H:.1f}*sin({u}/.3*PI),{.004 * H:.1f}*sin(20*{u}))", "0"
    if m == "sink": return "0", f"{.035 * H:.1f}*min({u},2.2)/2.2", "0.02*sin(2*t)"
    if m == "slide": return f"{side * .18 * W:.1f}*pow(max(0,1-{u}/.35),2)", f"{.006 * H:.1f}*sin(4*{u})", "0"
    if m == "creep": return f"{side * .01 * W:.1f}*sin(1.5*{u})", f"{.012 * H:.1f}*sin(2.2*{u})", "0.025*sin(2*t)"
    if m == "still": return "0", "0", "0"
    if m == "sway": return "0", f"{.008 * H:.1f}*sin(4*{u})", "0.06*sin(3.2*t)"
    return "0", f"{.010 * H:.1f}*sin(6*{u})", "0.035*sin(5*t)"


def render(src, segs, words, out, layout="blur", cam=None, captions=True, censor=frozenset(), fx=None,
           events=(), hook=None, cb=None, norm=True, cz_start=0, opts=None, info=None):
    global GPU_ENC_FAILED
    fx = fx or {}; I = float(fx.get("intensity", 1.0)); acc = str(fx.get("accent", "ff4d8d")).lstrip("#")
    o = get_opts(opts)
    src, out = str(Path(src).resolve()), str(Path(out).resolve())
    FPS = OUT["fps"]
    if o["fix_lag"]:                          # frozen / missing picture in the VOD: cut the silent part out instead of showing a frozen frame
        try:
            holes = video_holes(src, min(a for a, _ in segs), max(b for _, b in segs))
            if holes:
                healed = heal_segments(segs, holes, words)
                print(f"Video lag in the source: {len(holes)} gap(s), longest {max(b - a for a, b in holes):.1f}s -> "
                      f"{'cut out the silent parts' if healed != segs else 'left in (someone is speaking there)'}")
                segs = healed
        except Exception as e: print("Lag check skipped:", str(e)[:100])
    segs = quant_segs(segs, FPS)
    owords, dur = remap(words, segs)
    aspect = "16:9" if layout == "wide" else o["aspect"]
    try: import vcfx
    except Exception: vcfx = None
    crop_box, hide_on, sw0, sh0 = None, False, 0, 0
    if vcfx and (o["auto_crop"] or o["hide_box"]):             # 2.0: cut away black bars / cover a spot of the original picture
        try:
            inf0 = probe_info(src); sw0, sh0 = inf0["w"], inf0["h"]
            hide_on = bool(o["hide_box"]) and bool(vcfx.hide_graph("a", "b", o["hide_box"], o["hide_style"], sw0, sh0))
            if o["auto_crop"]:
                crop_box = vcfx.detect_bars(src, min(a for a, _ in segs), max(b for _, b in segs), FF, NOWIN, sw0, sh0)
                if crop_box:
                    print(f"Black bars found: using {crop_box[0]}x{crop_box[1]} of the {sw0}x{sh0} picture")
                    if cam: cam = vcfx.shift_cam(cam, crop_box)
        except Exception as e:
            crop_box = None; hide_on = False; print("Picture clean-up skipped:", str(e)[:100])
    if needs_cam(layout, o) and not cam: layout = "blur"
    if layout == "custom" and not o["custom_layout"]: layout = "blur"
    filler = o["filler"] if o["filler"] and os.path.isfile(o["filler"]) else ""
    if layout == "filler" and not filler: layout = "stack" if cam else "blur"
    W, H = out_dims(aspect)
    RW, RH = REF[aspect]                                       # caption reference canvas (scaled by libass)
    safe = safe_zone(o, aspect) if layout != "wide" else (0.0, 0.0, 0.0)
    lo, hi = min(a for a, _ in segs), max(b for _, b in segs)
    E = [t for t in (tmap(segs, e) for e in events) if t is not None][:40]
    cuts, off = [], 0.0
    for a, b in segs[:-1]:
        off += b - a; cuts.append(off)
    g, inputs = [], []

    def reg(args):                            # extra ffmpeg inputs; returns the input index to use in the filter graph
        inputs.append(args); return len(inputs)
    ex = {}
    if layout == "filler":                    # your own looping video under the cam (starts somewhere different each time when it is long enough)
        fl, fd = ["-stream_loop", "-1"], probe_info(filler)["dur"]
        if fd > dur + 8: fl = ["-ss", f"{random.uniform(0, fd - dur - 3):.2f}"] + fl
        ex["filler"] = reg(fl + ["-i", os.path.abspath(filler)])
    if layout == "blur" and o["bg_style"] == "image" and o["bg_image"] and os.path.isfile(o["bg_image"]):
        ex["bgimg"] = reg(["-i", os.path.abspath(o["bg_image"])])
    for i, (a, b) in enumerate(segs):
        a, b = a - lo, b - lo; D = b - a; nf = max(1, int(round(D * FPS)))
        # picture AND sound are anchored to the REQUESTED start (not to the first frame found) and made exactly D long: missing frames in the
        # source can no longer pull the picture ahead of the sound, and every piece ends with the same length of picture and sound
        g.append(f"[0:v]trim={a:.4f}:{b:.4f},setpts=PTS-{a:.4f}/TB,fps={FPS}:start_time=0,tpad=stop_mode=clone:stop_duration={D:.4f},"
                 f"trim=end_frame={nf},setpts=PTS-STARTPTS[v{i}];"
                 f"[0:a]atrim={a:.4f}:{b:.4f},asetpts=PTS-{a:.4f}/TB,aresample=async=1:first_pts=0,apad=whole_dur={D:.4f},atrim=end={D:.4f},"
                 f"asetpts=PTS-STARTPTS,afade=t=in:d=0.03,afade=t=out:st={max(0, D - .03):.3f}:d=0.03[a{i}]")
    g.append("".join(f"[v{i}][a{i}]" for i in range(len(segs))) + f"concat=n={len(segs)}:v=1:a=1[vc][a0]")
    vin = "vc"
    if hide_on: g += vcfx.hide_graph(vin, "vh", o["hide_box"], o["hide_style"], sw0, sh0); vin = "vh"
    if crop_box: g.append(f"[{vin}]crop={crop_box[0]}:{crop_box[1]}:{crop_box[2]}:{crop_box[3]}[vcr]"); vin = "vcr"
    g.append(f"[{vin}]fps={FPS}[v]"); g.append(reframe(layout, cam, W, H, o["pip_pos"], o, ex, safe))
    cur = "vv"

    def add(f):
        nonlocal cur
        n = f"x{len(g)}"; g.append(f"[{cur}]{f}[{n}]"); cur = n
    add("setsar=1")                                                  # square pixels, whatever the layout rounded to
    if vcfx:                                                         # 2.0 picture looks: brighten dark video, crisp picture, colour look, soft corners
        try:
            lf = vcfx.auto_light(src, lo, hi, FF, NOWIN) if o["auto_light"] else ""
            if lf: add(lf); print("Dark video: brightened")
            for f_ in (vcfx.crisp_filter(o["crisp"]), vcfx.look_filter(o["color_look"]), vcfx.VIGNETTE if o["vignette"] else ""):
                if f_: add(f_)
        except Exception as e: print("Picture looks skipped:", str(e)[:100])
    T = f"(in/{FPS})"
    SC = H / RH                                                   # output pixels per caption-canvas unit
    bump = lambda k, d, tv: "+".join(f"if(between({tv},{e:.3f},{e + d:.3f}),exp(-{k}*({tv}-{e:.3f})),0)" for e in E) or "0"
    base = 0.07 if fx.get("pan") else 0.0
    zoom_on = bool(fx.get("zoom") and E)
    tilt_on = bool(fx.get("tilt") and E)
    push = .06 * I if fx.get("pushin") else 0.0
    if tilt_on:                           # quick tilt on every impact (alternating direction); the zoom below crops the corners
        ang = "+".join(f"({'-' if k % 2 else ''}{.05 * I:.4f}*if(between(t,{e:.3f},{e + .5:.3f}),exp(-7*(t-{e:.3f})),0))" for k, e in enumerate(E))
        add(f"rotate=a='{ang}':ow=iw:oh=ih:c=black")
    bnds = [0.0] + cuts + [dur]                  # segment i spans bnds[i]..bnds[i+1]; every other segment is punched in
    cz = "+".join(f"gte({T},{bnds[i]:.3f})*lt({T},{bnds[i + 1]:.3f})" for i in range(len(bnds) - 1) if (i + cz_start) % 2 == 1) if fx.get("cutzoom") else ""
    if zoom_on or base or cz or fx.get("zoomout") or tilt_on or push:    # punch zoom + shake + pan drift + jump-cut zoom + opening zoom-out + tilt crop + push-in
        czx = f"+{.08 * I:.3f}*({cz})" if cz else ""
        if tilt_on: czx += f"+{1.9 * .05 * I:.4f}*({bump(7, .5, T)})"
        if push: czx += f"+{push:.3f}*{T}/{max(dur, .1):.3f}"
        if fx.get("zoomout"):                 # start tight, ease out to full frame in ~1s
            czx += f"+{.30 * min(I, 1.3):.3f}*pow(max(0,1-{T}/1.0),2)"
        zp = f"({.10 * I:.3f}*({bump(5, .9, T)}))" if zoom_on else "0"
        sx = f"+{W * .3:.1f}*{zp}*sin(70*{T})" if fx.get("shake") and zoom_on else ""
        sy = f"+{H * .12:.1f}*{zp}*cos(63*{T})" if fx.get("shake") and zoom_on else ""
        pan = f"+{W * base * .4:.1f}*sin(0.7*{T})" if base else ""
        add(f"zoompan=z='1+{base}+{zp}{czx}':x='iw/2-(iw/zoom/2){sx}{pan}':y='ih/2-(ih/zoom/2){sy}':d=1:s={W}x{H}:fps={FPS}")
    if fx.get("glitch") and E:                # RGB-split glitch on each impact
        gw = "+".join(f"between(t,{e:.3f},{e + .22:.3f})" for e in E)
        gs = max(2, int(round(5 * I * W / 1080)))
        add(f"chromashift=crh={gs}:cbh=-{gs}:crv=-{max(1, gs // 3)}:cbv={max(1, gs // 3)}:enable='{gw}'")
    flash = f":brightness='{.28 * I:.3f}*({bump(14, .35, 't')})'" if fx.get("flash") and E else ""
    bw = bool(fx.get("bw") and E)
    if fx.get("pop") or flash or bw:          # color pop + impact flash + black & white flash
        s_, c_ = (1 + .18 * I, 1 + .04 * I) if fx.get("pop") else (1, 1)
        sat = f"'{s_:.3f}*(1-min(1,{bump(0, .16, 't')}))'" if bw else f"{s_:.3f}"
        add(f"eq=saturation={sat}:contrast={c_:.3f}{flash}" + (":eval=frame" if flash or bw else ""))
    if fx.get("glow"):                        # dreamy bloom: blurred copy screened over the picture
        n = len(g); sw_, sh_ = max(2, W // 8 // 2 * 2), max(2, H // 8 // 2 * 2)
        g.append(f"[{cur}]split[gl{n}a][gl{n}b]")
        g.append(f"[gl{n}b]scale={sw_}:{sh_},gblur=sigma=4,scale={W}:{H}[gl{n}c]")
        g.append(f"[gl{n}a][gl{n}c]blend=all_mode=screen:all_opacity={.30 * min(I, 1.3):.2f}[x{n}]"); cur = f"x{n}"
    if fx.get("vhs"):                         # retro VHS: grain, colour fringing, soft picture, scanlines
        ch_, ln_ = max(1, round(3 * SC)), max(3, round(4 * SC))
        add(f"noise=alls={int(12 * min(I, 1.5))}:allf=t,chromashift=crh={ch_}:cbh=-{ch_},gblur=sigma={max(.4, .7 * SC):.2f},"
            f"eq=saturation=1.2:contrast=1.06,drawgrid=w=0:h={ln_}:t={max(1, ln_ // 4)}:c=black@0.18")
    if fx.get("blur") and cuts:               # blur-cut transitions
        win = "+".join(f"between(t,{max(0, c - .07):.3f},{c + .10:.3f})" for c in cuts[:60])
        add(f"gblur=sigma={10 * I * H / RH:.1f}:enable='{win}'")
    if fx.get("frame"):                       # pink + white photo-booth border
        th_ = max(6, round(18 * SC))
        add(f"drawbox=x=0:y=0:w=iw:h=ih:color=0x{acc}@0.95:t={th_},drawbox=x={th_}:y={th_}:w=iw-{2 * th_}:h=ih-{2 * th_}:color=white@0.85:t={max(2, th_ // 5)}")
    with tempfile.TemporaryDirectory() as tmp:
        extra_ass = fx_ass(fx, E, dur, RW, RH, acc, I)
        hook_txt = hook if fx.get("hook") else None
        bh = max(6, round(14 * H / RH))
        stk, ev_st = sticker_files(o["stickers"]), []
        if stk:                               # emote / sticker bursts on the big moments
            last = -9.0
            for e_ in E:
                if e_ - last >= 2.2 and e_ < dur - .8 and len(ev_st) < 8: ev_st.append(e_); last = e_
        if stk and ev_st:
            szpx = max(32, int(W * o["sticker_size"] / 100) // 2 * 2); SD = 1.6
            slots = [(.24, .38), (.76, .47), (.30, .52), (.70, .36), (.50, .44)]
            uses = {}
            for n_, e_ in enumerate(ev_st): uses.setdefault(n_ % len(stk), []).append((n_, e_))
            for fi, lst in uses.items():
                path = stk[fi]; is_gif = path.lower().endswith(".gif")
                k_ = reg((["-stream_loop", "-1"] if is_gif else ["-loop", "1", "-framerate", str(FPS)]) + ["-t", f"{dur + 1:.2f}", "-i", os.path.abspath(path)])
                outs = "".join(f"[sp{fi}_{j}]" for j in range(len(lst)))
                g.append(f"[{k_}:v]format=rgba,scale={szpx}:{szpx}:force_original_aspect_ratio=decrease," + (f"split={len(lst)}{outs}" if len(lst) > 1 else f"null[sp{fi}_0]"))
                for j, (n_, e_) in enumerate(lst):
                    ang = (.12, -.10, .07, -.14, 0.0)[n_ % 5]; px, py = slots[n_ % len(slots)]
                    cx = min(W * px, W * (1 - safe[1]) - szpx / 2); cy = H * py
                    pf = "(1+2.70158*pow(t/.28-1,3)+1.70158*pow(t/.28-1,2))"           # ease-out-back: pops in with a little overshoot
                    g.append(f"[sp{fi}_{j}]trim=duration={SD},setpts=PTS-STARTPTS,rotate=a={ang}:c=none:ow=rotw({ang}):oh=roth({ang}),"
                             f"scale=w='max(8,trunc(iw*if(lt(t,.28),{pf},1)/2)*2)':h=-2:eval=frame,"
                             f"fade=t=out:st={SD - .3:.2f}:d=0.3:alpha=1,setpts=PTS+{e_:.3f}/TB[st{n_}]")
                    nn = f"x{len(g)}"
                    g.append(f"[{cur}][st{n_}]overlay=x='{cx:.1f}-w/2':y='{cy:.1f}-h/2':eof_action=pass:format=auto:enable='between(t,{e_:.3f},{e_ + SD:.3f})'[{nn}]"); cur = nn
        cap_mv = int(RH * LOW_MARGIN[aspect])
        if safe[0]:                           # captions stay above the app's own text / buttons
            cap_mv = max(cap_mv, int(RH * (safe[0] + .08)))
            if layout == "pip" and o["pip_pos"] in ("bl", "br"):
                cap_mv = max(cap_mv, int(RH * (max(.06, safe[0]) + pip_size(W, H)[0] / H + .03)))
        cta_on = bool(o["cta"]) and dur > 3.2
        x_on = bool(o["lower_name"] and dur > 3.0) or bool(o["part_badge"] and o.get("part")) or bool(o["follow_text"] and dur >= 8.0) or bool(o["text_boxes"] and dur > 1.5) or bool(o["callouts"] and dur >= 5.0)
        if (captions and owords) or extra_ass or hook_txt or o["handle"] or cta_on or x_on:
            fdir = ""
            ffile = FONTS[o["cap_font"]][1]
            if ffile and os.path.isfile(os.path.join(APP_DIR, "fonts", ffile)):       # bundled caption fonts work on every PC
                os.makedirs(os.path.join(tmp, "fonts"), exist_ok=True); shutil.copy(os.path.join(APP_DIR, "fonts", ffile), os.path.join(tmp, "fonts", ffile))
                fdir = ":fontsdir=fonts"
            make_ass(owords if captions else [], censor, Path(tmp) / "cap.ass", RW, RH, 88 if RW == 1080 else 64, cap_mv,
                     hook_txt, acc, extra_ass, o, safe, dur)
            add("ass=cap.ass" + fdir)
        eit = []
        if o["emotes"] and dur > 2:                      # chibi emotes: a picture of your model that acts out the feeling of what you are saying
            try:
                import vcemotes, zlib
                raw = o.get("emote_plan")
                if raw is None:
                    r_ = vcemotes.plan(owords, dur, E, level=o["emote_level"], burst=o["emote_burst"], seed=zlib.crc32(out.encode()) & 0xffff)
                    raw = r_["items"]
                eit = []
                for it in raw:
                    t_ = tmap(segs, it["at"]) if it.get("at") is not None else it.get("t")
                    if t_ is None or not os.path.isfile(str(it.get("path", ""))) or t_ > dur - .6: continue
                    eit.append(dict(t=max(0.0, float(t_)), hold=max(.8, min(float(it.get("hold", 2.2)), dur - t_ - .1)), tag=it.get("tag", ""), path=it["path"]))
                eit.sort(key=lambda x: x["t"])
                for a_, b_ in zip(eit, eit[1:]): a_["hold"] = max(.8, min(a_["hold"], b_["t"] - a_["t"] - .1))
            except Exception as e:
                eit = []; print("Emotes skipped:", str(e)[:100])
        if captions and o["cap_emoji"] and owords:       # little emoji pictures that pop up above the caption on strong feelings (lol, love, dead, fire...)
            try:
                import vcemoji
                ev_em = vcemoji.pick([w for w in owords if not is_cens(w, censor)], dur, I)
                if eit: ev_em = [(t_, h_) for t_, h_ in ev_em if not any(x["t"] - .3 <= t_ <= x["t"] + x["hold"] for x in eit)]       # a chibi is already showing that feeling
            except Exception as e:
                ev_em = []; print("Emojis skipped:", str(e)[:100])
            if ev_em:
                ES = max(48, int(min(W, H) * .15) // 2 * 2); ED = 1.4; SCf = H / RH
                cs_ = max(20, int((88 if RW == 1080 else 64) * FONTS[o["cap_font"]][2] * o["cap_size"] / 100))
                cbh = cs_ * 1.25 * (2 if o["cap_style"] in ("line", "karaoke", "box") else 1.35) * SCf       # height of the caption block (worst case)
                gp = .02 * H
                if o["cap_pos"] == "mid": ecy = H / 2 - cbh / 2 - gp - ES / 2
                elif o["cap_pos"] == "high": ecy = H * HIGH_MARGIN[aspect] + cbh + gp + ES / 2
                else: ecy = H - cap_mv * SCf - cbh - gp - ES / 2
                ecy = min(H - ES, max(ES / 2 + H * safe[2] + 4, ecy))
                uses_e = {}
                for n_, (t_, hx_) in enumerate(ev_em): uses_e.setdefault(hx_, []).append((n_, t_))
                for fi, (hx_, lst) in enumerate(uses_e.items()):
                    k_ = reg(["-loop", "1", "-framerate", str(FPS), "-t", f"{ED + .3:.2f}", "-i", os.path.abspath(vcemoji.path(hx_))])
                    outs = "".join(f"[em{fi}_{j}]" for j in range(len(lst)))
                    g.append(f"[{k_}:v]format=rgba,scale={ES}:{ES}," + (f"split={len(lst)}{outs}" if len(lst) > 1 else "null[em%d_0]" % fi))
                    for j, (n_, t_) in enumerate(lst):
                        pf = "(1+2.70158*pow(t/.22-1,3)+1.70158*pow(t/.22-1,2))"
                        g.append(f"[em{fi}_{j}]trim=duration={ED},setpts=PTS-STARTPTS,"
                                 f"scale=w='max(8,trunc({ES}*if(lt(t,.22),{pf},1)/2)*2)':h=-2:eval=frame,"
                                 f"fade=t=out:st={ED - .3:.2f}:d=0.3:alpha=1,setpts=PTS+{t_:.3f}/TB[emo{n_}]")
                        nn = f"x{len(g)}"
                        g.append(f"[{cur}][emo{n_}]overlay=x='{W / 2:.1f}-w/2':y='{ecy:.1f}-h/2-min(t-{t_:.3f},{ED})*{H * .02:.1f}':eof_action=pass:format=auto:"
                                 f"enable='between(t,{t_:.3f},{t_ + ED:.3f})'[{nn}]"); cur = nn
        if eit and o["emote_fx"]:              # 2.0: the picture reacts to the feeling (colour split on scary / angry, flash on happy, grey on sad)
            try:
                SHK = {"fear", "shocked", "angry", "dead", "gun", "yandere"}; FLS = {"celebrating", "laughing", "cool", "thanks", "love"}; SAD = {"cry", "tired", "blank", "dumb", "trash"}
                shk = [x["t"] for x in eit if x["tag"] in SHK][:30]
                fls = [x["t"] for x in eit if x["tag"] in FLS][:30]
                sad = [(x["t"], x["hold"]) for x in eit if x["tag"] in SAD][:30]
                if shk:
                    wn = "+".join(f"between(t,{t_:.3f},{t_ + .32:.3f})" for t_ in shk); gs2 = max(2, int(round(7 * W / 1080)))
                    add(f"chromashift=crh={gs2}:cbh=-{gs2}:crv=-{max(1, gs2 // 3)}:cbv={max(1, gs2 // 3)}:enable='{wn}'")
                if fls:
                    bf = "+".join(f"if(between(t,{t_:.3f},{t_ + .45:.3f}),exp(-9*(t-{t_:.3f})),0)" for t_ in fls)
                    add(f"eq=brightness='0.22*({bf})':eval=frame")
                if sad:
                    wn = "+".join(f"between(t,{t_ + .1:.3f},{t_ + h_:.3f})" for t_, h_ in sad)
                    add(f"eq=saturation='1-0.6*min(1,{wn})':eval=frame")
            except Exception as e: print("Emote effects skipped:", str(e)[:100])
        if eit:
            ESz = max(64, int(min(W, H) * o["emote_size"] / 100) // 2 * 2); SCf = H / RH; marg = int(W * .02)
            if o["emote_pos"] == "top": ebot = H * (safe[2] + .05) + ESz
            elif captions and o["cap_pos"] == "low" and owords:
                cs_ = max(20, int((88 if RW == 1080 else 64) * FONTS[o["cap_font"]][2] * o["cap_size"] / 100))
                cbh_ = cs_ * 1.25 * (2 if o["cap_style"] in ("line", "karaoke", "box") else 1.35) * SCf
                ebot = H - cap_mv * SCf - cbh_ - .02 * H
            else: ebot = H - H * safe[0] - .05 * H
            ecy_ = min(H - ESz / 2 - 4, max(ESz / 2 + H * safe[2] + 4, ebot - ESz / 2))
            uses_p = {}
            for n_, it in enumerate(eit): uses_p.setdefault(it["path"], []).append((n_, it))
            for fi, (pth, lst) in enumerate(uses_p.items()):
                rp = vcemotes.small_copy(pth, 512); is_gif = rp.lower().endswith(".gif"); mh = max(x["hold"] for _, x in lst) + .4
                k_ = reg((["-stream_loop", "-1"] if is_gif else ["-loop", "1", "-framerate", str(FPS)]) + ["-t", f"{mh:.2f}", "-i", os.path.abspath(rp)])
                outs = "".join(f"[ep{fi}_{j}]" for j in range(len(lst)))
                g.append(f"[{k_}:v]format=rgba,scale={ESz}:{ESz}:force_original_aspect_ratio=decrease," + (f"split={len(lst)}{outs}" if len(lst) > 1 else f"null[ep{fi}_0]"))
                for j, (n_, it) in enumerate(lst):
                    side = {"left": -1, "right": 1}.get(o["emote_pos"], -1 if n_ % 2 == 0 else 1)
                    if o["emote_pos"] == "top": cx_ = W / 2
                    elif side < 0: cx_ = marg + ESz / 2
                    else: cx_ = min(W - marg - ESz / 2, W * (1 - safe[1]) - ESz / 2)
                    dx_, dy_, ang_ = emote_motion(it["tag"], it["t"], W, H, side)
                    rot = f"rotate=a='{ang_}':c=none:ow=rotw(.07):oh=roth(.07)," if ang_ != "0" else ""
                    pf = "(1+2.70158*pow(t/.25-1,3)+1.70158*pow(t/.25-1,2))"
                    g.append(f"[ep{fi}_{j}]trim=duration={it['hold']:.2f},setpts=PTS-STARTPTS,{rot}"
                             f"scale=w='max(8,trunc(iw*if(lt(t,.25),{pf},1)/2)*2)':h=-2:eval=frame,"
                             f"fade=t=out:st={max(.1, it['hold'] - .3):.2f}:d=0.3:alpha=1,setpts=PTS+{it['t']:.3f}/TB[epo{n_}]")
                    nn = f"x{len(g)}"
                    g.append(f"[{cur}][epo{n_}]overlay=x='{cx_:.1f}-w/2+({dx_})':y='{ecy_:.1f}-h/2+({dy_})':eof_action=pass:format=auto:"
                             f"enable='between(t,{it['t']:.3f},{it['t'] + it['hold']:.3f})'[{nn}]"); cur = nn
        if o["buddy"] and dur > 2 and vcfx:                  # 2.0: a little chibi in the corner that hops while you talk
            try:
                import vcemotes
                lib = vcemotes.by_feeling(); pics = lib.get(o["buddy_feeling"]) or next(iter(lib.values()), [])
                if pics:
                    bs = max(48, int(W * o["buddy_size"] / 100) // 2 * 2); marg = int(W * .03); SCf = H / RH
                    rp = vcemotes.small_copy(pics[0].path, 512)
                    if o["buddy_pos"] in ("tl", "tr"): bot = None; top = H * (safe[2] + .05)
                    else:
                        top = None
                        if captions and o["cap_pos"] == "low" and owords:
                            cs_ = max(20, int((88 if RW == 1080 else 64) * FONTS[o["cap_font"]][2] * o["cap_size"] / 100))
                            bot = H - cap_mv * SCf - cs_ * 1.25 * (2 if o["cap_style"] in ("line", "karaoke", "box") else 1.35) * SCf - .02 * H
                        else: bot = H - H * safe[0] - .05 * H
                    bx = f"{marg}" if o["buddy_pos"] in ("tl", "bl") else f"W-w-{marg + int(W * safe[1])}"
                    base = f"{top:.1f}+h*.05" if top is not None else f"{bot:.1f}-h"
                    segs_t = vcfx.talk_segments(owords, dur)
                    k_ = reg((["-stream_loop", "-1"] if rp.lower().endswith(".gif") else ["-loop", "1", "-framerate", str(FPS)]) + ["-t", f"{dur + 1:.2f}", "-i", os.path.abspath(rp)])
                    g.append(f"[{k_}:v]format=rgba,scale={bs}:{bs}:force_original_aspect_ratio=decrease,fade=t=in:st=0.15:d=0.35:alpha=1[bdy]")
                    nn = f"x{len(g)}"
                    g.append(f"[{cur}][bdy]overlay=x='{bx}':y='{vcfx.buddy_y_expr(base, bs * .07, segs_t)}':eof_action=pass:format=auto[{nn}]"); cur = nn
            except Exception as e: print("Buddy skipped:", str(e)[:100])
        if o["logo"] and os.path.isfile(o["logo"]):          # logo / watermark in a corner
            li = reg(["-i", os.path.abspath(o["logo"])]); lw = max(16, int(W * o["logo_size"] / 100) // 2 * 2); pad = int(min(W, H) * .04)
            try: import vcmedia; la_ = vcmedia.logo_alpha_filter(o.get("logo_alpha", 92))
            except Exception: la_ = "colorchannelmixer=aa=0.92"
            g.append(f"[{li}:v]format=rgba,scale={lw}:-2,{la_}[lg]")
            lx = f"{pad}" if o["logo_pos"] in ("tl", "bl") else f"W-w-{pad + (int(W * safe[1]) if o['logo_pos'] == 'br' else 0)}"
            ly = f"{pad + int(H * safe[2])}" if o["logo_pos"] in ("tl", "tr") else f"H-h-{pad + bh + int(H * safe[0])}"
            if o.get("hop_logo") and _vm and dur > 8:                # 2.2: the logo moves to another corner every few seconds (harder to crop out, easy to spot)
                hx, hy = _vm.hop_xy(W, H, "w", "h", pad, pad + int(H * safe[2]), pad + bh + int(H * safe[0]), pad + int(W * safe[1]))
                g.append(f"[{cur}][lg]overlay=x='{hx}':y='{hy}':format=auto[xlg]")
            else: g.append(f"[{cur}][lg]overlay=x={lx}:y={ly}:format=auto[xlg]")
            cur = "xlg"
        if fx.get("bar"):                     # retention progress bar
            by_, bth_ = H - bh, bh
            try:                                                  # 2.3: top or bottom edge, own thickness
                import vcmedia
                by_, bth_ = vcmedia.bar_geometry(H, RH, o.get("bar_pos", "bottom"), o.get("bar_thick", 14))
            except Exception: pass
            g.append(f"color=c=0x{acc}:s={W}x{bth_}:r={FPS}:d={dur:.2f}[bar]")
            g.append(f"[{cur}][bar]overlay=x='-w+w*t/{dur:.3f}':y={by_}:shortest=1[xbar]"); cur = "xbar"
        FD = vcfx.fade_seconds(o["fade"], dur) if vcfx else 0.0
        g.append(f"[{cur}]" + (f"fade=t=in:st=0:d={FD:.2f},fade=t=out:st={max(0, dur - FD):.3f}:d={FD:.2f}" if FD else "null") + "[vf]")
        cens = [(w["start"], w["end"]) for w in owords if is_cens(w, censor)]
        VC = ("," + VOICE_CLEAN) if o["voice_clean"] else ""
        if vcfx: VC += vcfx.voice_chain(o["voice_eq"], o["voice_fx"])
        try:                                              # 2.3: noise gate, de-esser (before the compressor, so the compressor does not lift the noise)
            import vcmedia
            VC += vcmedia.audio_gate(o, FF, NOWIN)
        except Exception as e: print("Gate / de-esser skipped:", str(e)[:80])
        if _vm: VC += _vm.audio_extras(o)                 # 2.2: hush the background hiss / tame loud screams
        music = pick_music(o["music"])
        if o.get("music_mood") and o.get("mood_kind") and o["music"]:               # 2.3: a sub-folder of your music folder named after the mood of the clip (hype, funny, chill, sad, spooky, cute...)
            try:
                import vcmedia
                mm_ = vcmedia.mood_pick(o["music"], o["mood_kind"], lambda d_, ex_=(): pick_music(d_, ex_), o.get("mood_feel", ""))
                if mm_ is not None: music = mm_; print("Music by mood:", (os.path.basename(os.path.dirname(mm_)) + " / " + os.path.basename(mm_)) if mm_ else "none (a song is playing)")
            except Exception as e: print("Music by mood skipped:", str(e)[:80])
        if cens:
            e = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in cens)
            g.append(f"[a0]aresample=48000{VC},volume='1-min(1,{e})':eval=frame[am]")
        else: g.append(f"[a0]aresample=48000{VC}[am]")
        labels = ["[am]"]; AM = "am"
        vo = []
        if o["text_boxes"] and dur > 1.5:                 # 2.1: a voice reads the text boxes that have "read out loud" switched on; the game sound dips while it speaks
            try:
                import vcnew
                for j_, (txt_, t0_) in enumerate(vcnew.voiceover_items(o, dur)):
                    wp = os.path.join(tmp, f"vo{j_}.wav")
                    if vcnew.tts_make(txt_, wp, o["tts_voice"], o["tts_rate"], FF, NOWIN): vo.append((wp, t0_))
                    else: print("No voice available to read:", txt_[:30])
                for j_, (wp, t0_) in enumerate(vo):
                    k_ = reg(["-i", wp]); ms = int(t0_ * 1000)
                    g.append(f"[{k_}:a]aresample=48000,aformat=channel_layouts=stereo,volume={track_gain_db(wp, -15.0):.1f}dB,adelay={ms}|{ms},apad=whole_dur={dur:.3f},atrim=0:{dur:.3f},asetpts=PTS-STARTPTS[nv{j_}]")
                if vo:
                    g.append(("".join(f"[nv{j_}]" for j_ in range(len(vo))) + f"amix=inputs={len(vo)}:duration=first:normalize=0[nvm]") if len(vo) > 1 else "[nv0]anull[nvm]")
                    g.append("[nvm]asplit=2[nvx][nvs]")
                    g.append("[am][nvs]sidechaincompress=threshold=0.02:ratio=8:attack=10:release=400:makeup=1[amn]")
                    AM = "amn"; labels = ["[amn]", "[nvx]"]
            except Exception as e:
                vo = []; AM = "am"; labels = ["[am]"]; print("Voice-over skipped:", str(e)[:100])
        if cens: g.append(f"aevalsrc='({vcfx.bleep_tone(o['bleep_sound']) if vcfx else '0.2*sin(2*PI*1000*t)'})*min(1,{e})':d={dur:.3f}:s=48000[bp]"); labels.append("[bp]")
        if music:                             # background music, ducked under the voice
            mi = reg(["-stream_loop", "-1", "-i", os.path.abspath(music)])
            g.append(f"[{mi}:a]aresample=48000,volume={track_gain_db(music):.1f}dB,volume={o['music_vol'] / 100:.3f},atrim=0:{dur:.3f},asetpts=PTS-STARTPTS,"
                     f"afade=t=in:d=0.6,afade=t=out:st={max(0, dur - 1.2):.3f}:d=1.2[mus]")
            if o["duck"]:
                g.append(f"[{AM}]asplit=2[amv][ams]"); labels[0] = "[amv]"
                g.append("[mus][ams]sidechaincompress=threshold=0.03:ratio=8:attack=15:release=500[musd]"); labels.append("[musd]")
            else: labels.append("[mus]")
        if fx.get("sfx") and E:               # impact sounds on each hit (boom / cute / anime / retro)
            hp = hit_paths(o["sfx_pack"], len(E))                       # the hits take turns, so a clip does not repeat one sound
            for j, hpath in enumerate(hp):
                evs = [i for i in range(len(E)) if i % len(hp) == j]
                if not evs: continue
                hi_ = reg(["-i", hpath])
                g.append(f"[{hi_}:a]volume=0.6,asplit={len(evs)}" + "".join(f"[h{i}]" for i in evs))
                for i in evs:
                    ms = int(E[i] * 1000); g.append(f"[h{i}]adelay={ms}|{ms}[d{i}]"); labels.append(f"[d{i}]")
        if eit and o["emote_sound"]:          # 2.0: a soft pop when a chibi shows up (rising for happy, falling for sad / scary)
            try:
                DOWN = {"cry", "dead", "fear", "angry", "tired", "dumb", "trash", "fine", "blank", "confused", "sus"}
                for kind, expr, d_ in (("u", "0.30*sin(2*PI*(520+1500*t)*t)*exp(-13*t)", .30), ("d", "0.30*sin(2*PI*(720-1100*t)*t)*exp(-8*t)", .45)):
                    idx = [j for j, x in enumerate(eit) if (x["tag"] in DOWN) == (kind == "d")][:12]
                    if not idx: continue
                    g.append(f"aevalsrc='{expr}':d={d_}:s=48000,aformat=channel_layouts=mono,asplit={len(idx)}" + "".join(f"[ep{kind}{j}]" for j in idx))
                    for j in idx:
                        ms = int(eit[j]["t"] * 1000); g.append(f"[ep{kind}{j}]adelay={ms}|{ms}[epd{kind}{j}]"); labels.append(f"[epd{kind}{j}]")
            except Exception as e: print("Emote sounds skipped:", str(e)[:100])
        WC, last = [], -9.0
        if fx.get("whoosh"):                  # whoosh into jump cuts
            for c in cuts:
                if c > .3 and c - last >= 2.5 and len(WC) < 6: WC.append(c); last = c
        if WC:
            wch = whoosh_choices(o["sfx_pack"])
            for j, (wpath, wpeak) in enumerate(wch):
                cs = [i for i in range(len(WC)) if i % len(wch) == j]
                if not cs: continue
                wi = reg(["-i", wpath])
                g.append(f"[{wi}:a]volume=0.35,asplit={len(cs)}" + "".join(f"[w{i}]" for i in cs))
                for i in cs:
                    ms = max(0, int((WC[i] - wpeak) * 1000)); g.append(f"[w{i}]adelay={ms}|{ms}[e{i}]"); labels.append(f"[e{i}]")
        ln = vcfx.loudnorm_chain(o["loudness"], norm) if vcfx else ("loudnorm=I=-14:TP=-1.5,aresample=48000" if norm else "anull")
        if FD: ln += f",afade=t=in:st=0:d={FD:.2f},afade=t=out:st={max(0, dur - FD):.3f}:d={FD:.2f}"
        if len(labels) > 1: g.append("".join(labels) + f"amix=inputs={len(labels)}:duration=first:normalize=0,{ln}[af]")
        else: g.append(f"[{AM}]{ln}[af]")
        total, vmap, amap = dur, "[vf]", "[af]"
        FM = "aformat=sample_rates=48000:sample_fmts=fltp:channel_layouts=stereo"

        def side_clip(path, cap, tag):
            """Intro / outro: a video (first few seconds, with or without sound) or a still image card."""
            kind = media_kind(path)
            if not kind: return 0.0
            if kind == "image":
                L = min(cap, 2.5); has_a = False
                k_ = reg(["-loop", "1", "-framerate", str(FPS), "-t", f"{L:.2f}", "-i", os.path.abspath(path)])
            else:
                inf = probe_info(path)
                if not inf["w"]: return 0.0
                L = min(cap, inf["dur"] or cap); has_a = inf["audio"]
                if L < .3: return 0.0
                k_ = reg(["-t", f"{L:.2f}", "-i", os.path.abspath(path)])
            g.append(f"[{k_}:v]trim=duration={L:.3f},setpts=PTS-STARTPTS,fps={FPS},scale={W}:{H}:force_original_aspect_ratio=decrease:force_divisible_by=2,"
                     f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,format=yuv420p[{tag}v]")
            if has_a: g.append(f"[{k_}:a]atrim=duration={L:.3f},asetpts=PTS-STARTPTS,aresample=48000,{FM}[{tag}a]")
            else: g.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={L:.3f},asetpts=PTS-STARTPTS,{FM}[{tag}a]")
            return L
        li_ = side_clip(o["intro"], 6.0, "in") if layout != "wide" else 0.0
        lo_ = side_clip(o["outro"], 8.0, "ou") if layout != "wide" else 0.0
        if li_ or lo_:
            g.append(f"[vf]format=yuv420p[vfx];[af]{FM}[afx]")
            seq = (["[inv][ina]"] if li_ else []) + ["[vfx][afx]"] + (["[ouv][oua]"] if lo_ else [])
            g.append("".join(seq) + f"concat=n={len(seq)}:v=1:a=1[vo][ao]")
            vmap, amap, total = "[vo]", "[ao]", dur + li_ + lo_
        (Path(tmp) / "g.txt").write_text(";\n".join(g))
        if os.environ.get("VC_KEEP_GRAPH"):           # debugging aid: keep a copy of the filter graph
            try: shutil.copy(os.path.join(tmp, "g.txt"), os.environ["VC_KEEP_GRAPH"])
            except OSError: pass

        extra = [x for a_ in inputs for x in a_]

        def args():
            return ["-ss", f"{lo:.3f}", "-t", f"{hi - lo + .05:.3f}", "-i", src] + extra + fc_args("g.txt") + \
                   ["-map", vmap, "-map", amap, "-r", str(FPS)] + venc() + \
                   ["-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out]
        try:
            try: run_ff(args(), total, cb, cwd=tmp)
            except RuntimeError as e:
                if "Cancelled" in str(e) or not gpu_enc_active(): raise
                GPU_ENC_FAILED = True
                print("The GPU video encoder couldn't handle this job - switching to the CPU encoder.")
                run_ff(args(), total, cb, cwd=tmp)
        except BaseException:
            try: os.remove(out)                # never leave a half-written video behind
            except OSError: pass
            raise
        if info is not None: info.update(intro=li_, outro=lo_, total=total)
    return owords, dur


def load_censor(p, swears=False):
    """Words that get bleeped and starred out: the user's own list (a text file) plus, when asked, the built-in list of common swear words."""
    mine = frozenset(clean(x) for x in Path(p).read_text(encoding="utf-8").split()) if p else frozenset()
    if swears:
        import vcpost
        return mine | vcpost.SWEARS
    return mine


# ---------------- jobs ----------------
def hms(t):
    t = int(max(0, t)); return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}"


# ---------------- post kit + subtitles ----------------
TITLES = {
    "Loud / screaming": ["This scream is UNREAL 😭", "Nobody was ready for this 😱", "The loudest moment of the stream 🔊"],
    "Laughing": ["I can't stop laughing at this 😂", "This got EVERYONE laughing 😭", "Peak comedy right here 😂"],
    "Hype words": ["WAIT WHAT?! 😱", "Did that really just happen?! 😳", "OMG the reaction 😱"],
    "Big reactions": ["The reaction says it all 👀", "Chat was NOT ready 👀", "Reaction of the year 😳"],
    "Talking / story": ["Story time: {q}", "This story is wild 👀", "You won't believe what happened 😳"],
    "Action": ["That play was INSANE 🔥", "Clutch moment 🔥", "How did that even work?! 😱"],
    "Steady energy": ["{q}", "Cute moment from the stream 💖", "Stream highlight 💖"],
}


def post_text(owords, o, tags, style_tags=(), k=0, hype=None):
    """Title ideas, a description and hashtags for one clip - plain text, ready to paste (no AI service involved)."""
    quote = " ".join(w["w"] for w in owords[:9]).strip(" ,;")
    quote = (quote[:1].upper() + quote[1:]) if quote else "Stream highlight"
    pool = []
    for t in tags or ["Steady energy"]:
        key = next((x for x in TITLES if t.startswith(x)), None)
        if key: pool += TITLES[key]
    pool += TITLES["Steady energy"]
    titles, seen = [], set()
    for t in pool:
        t = t.replace("{q}", quote + "…")
        if t not in seen: seen.add(t); titles.append(t)
    titles = [titles[(k + i) % len(titles)] for i in range(min(3, len(titles)))] + [f"“{quote}…”"]
    if o["game"]: titles.append(f"{titles[0]} | {o['game']}")
    if o["channel"]: titles.append(f"{titles[0]} - {o['channel']}")
    tg = ["#vtuber", "#vtubers", "#shorts", "#clips"] + [t for t in style_tags]
    for raw in (o["game"], o["channel"]):
        t = re.sub(r"\W", "", raw.lower())
        if t: tg.append("#" + t)
    for t in re.split(r"[\s,]+", o["tags"]):
        if t.strip("#"): tg.append("#" + t.strip("#").lower())
    tg = list(dict.fromkeys(tg))[:12]
    desc = f"“{quote}…”\n" + (f"Streamed by {o['channel']}. " if o["channel"] else "") + "Follow for more clips! 💖"
    head = f"HYPE SCORE  {hype}/100  ({'a standout' if hype >= 80 else 'strong' if hype >= 55 else 'solid' if hype >= 30 else 'calm'})\n\n" if hype is not None else ""
    return head + "TITLE IDEAS\n" + "\n".join(f"  {i}. {t}" for i, t in enumerate(titles, 1)) + f"\n\nDESCRIPTION\n{desc}\n\nHASHTAGS\n{' '.join(tg)}\n"


def why_block(kind, why):
    """2.2: a few plain lines about what kind of moment this is and why it was picked (goes above the title ideas)."""
    try:
        import vcsmart
        if not kind and not why: return ""
        lab = (vcsmart.type_icon(kind) + " " + vcsmart.type_label(kind)).strip() if kind else ""
        bullets = [re.sub(r"(?<=\d)[.]", "", str(x)) for x in (why or [])[:5]]
        lines = ["WHY THIS MOMENT"] + ([f"  Kind of clip: {lab}"] if lab else []) + [f"  - {x}" for x in bullets]
        return "\n".join(lines) + "\n\n"
    except Exception: return ""


def short_kit(owords, o, a, k=0, dur=None, kind=None):
    """The post kit (titles, descriptions, hashtags for every app) of one short. 2.3: words the privacy guard flagged are starred first, and hashtags that name a private word are dropped."""
    import vcpost
    extra = [t.strip("#") for t in re.split(r"[\s,]+", o["tags"]) if t.strip("#")]
    if kind:
        try:
            import vcsmart
            extra += [t for t in vcsmart.EXTRA_TAGS.get(kind, []) if t.lower() not in {x.lower() for x in extra}]
        except Exception: pass
    try:                                                   # 2.2: the creator's own hashtag bank (always / per game / per kind of clip)
        import vctools
        have_ = {x.lower() for x in extra}
        extra += [t for t in vctools.bank_tags(o["game"], kind or "") if t.lower() not in have_]
    except Exception: pass
    safe_w = [({**w, "w": "*" * len(w["w"])} if (w.get("priv") or w.get("pwarn")) else w) for w in owords]
    kit = vcpost.make_kit(safe_w, game=o["game"], channel=o["channel"], handle=o["handle"], hint=o["hint"], name_hint=Path(a.video).stem, seed=k, dur=dur, extra=extra, kind=kind)
    try:
        import vcsafe
        for plat in ("youtube", "tiktok", "reels"):
            hs = kit.get(plat, {}).get("hashtags")
            if hs: kit[plat]["hashtags"] = [h for h in hs if vcsafe.scrub_text(h, o) == h]
        kit["titles"] = [vcsafe.scrub_text(t, o) for t in kit["titles"]]
    except Exception: pass
    return kit


def short_post(owords, o, tags, a, k=0, hype=None, dur=None, kind=None, why=None):
    """The text file saved next to each short: title ideas for every platform, a YouTube description, hashtags that fit each app.
    Falls back to the simple v1.2 text if the writer can't run. 2.2: also says what kind of moment it is and why it was picked."""
    try:
        import vcpost
        kit = short_kit(owords, o, a, k, dur, kind)
        txt = vcpost.kit_text(kit, hype)
    except Exception: txt = post_text(owords, o, tags, style_hashtags(a.style, a.fx), k, hype)
    blk = why_block(kind, why)
    if blk and "TITLE IDEAS" in txt: txt = txt.replace("TITLE IDEAS", blk + "TITLE IDEAS", 1)
    return txt


_EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF\u2190-\u21FF\u2300-\u23FF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D]")


def cover_lines(titles, cjk=False, per=15, maxl=3):
    """Pick the best title for a cover (short, punchy, no emoji) and break it into big lines."""
    best = ""
    for tt in titles or []:
        s = re.sub(r"\s+", " ", _EMOJI_RE.sub("", str(tt))).strip(" -:|")
        if len(s) < 4 or "{" in s: continue
        if 2 <= len(s.split()) <= 8 and len(s) <= 44: best = s; break
        best = best or s
    best = best or "Stream highlight"
    if len(best) > 44:
        cut = best[:44].rsplit(" ", 1)[0] if " " in best[:44] else best[:44]; best = cut.rstrip(",.:;-") + "..."
    if not cjk: best = best.upper()
    if cjk or " " not in best:
        n = 8 if cjk else per
        return [best[i:i + n] for i in range(0, len(best), n)][:maxl]
    lines, cur = [], ""
    for w in best.split():
        if cur and len(cur) + 1 + len(w) > per: lines.append(cur); cur = w
        else: cur = (cur + " " + w).strip()
    lines.append(cur)
    while len(lines) > maxl: lines[-2] += " " + lines.pop()
    return lines


def make_cover(video, dest, titles, o, t, acc="ff4d8d", cjk=False, emote=""):
    """A still from the finished video with its title on top -> `dest` (.jpg). Returns False when it couldn't be made (never fatal)."""
    ffile = ""
    for name in (("Mochiy Pop (JP)",) if cjk else ()) + (o["cap_font"], "Poppins"):
        f = FONTS.get(name, (0, None))[1]
        if f and os.path.isfile(os.path.join(APP_DIR, "fonts", f)): ffile = f; break
    info = probe_info(str(video)); W, H = info["w"] or 1080, info["h"] or 1920
    if not ffile or not H: return False
    lines = cover_lines(titles, cjk)
    fs = int(max(24, min(W * .115, W * .9 / (max(len(x) for x in lines) * (1.0 if cjk else .66)))) // 2 * 2); lh = int(fs * 1.18); pad = int(fs * .35)
    safe = safe_zone(o, "9:16" if H > W * 1.5 else "x")
    y0 = H * (.62 if o["cap_pos"] == "high" else max(.10, safe[2] + .05) if H > W else .08)
    y0 = int(min(y0, H - len(lines) * lh - pad * 2 - 4))
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(os.path.join(APP_DIR, "fonts", ffile), os.path.join(tmp, "f.ttf"))
        vf = [f"drawbox=x=0:y={y0 - pad}:w=iw:h={len(lines) * lh + 2 * pad}:color=black@0.38:t=fill"]
        bw = max(3, fs // 14)
        for i, ln in enumerate(lines):
            Path(tmp, f"c{i}.txt").write_text(ln, encoding="utf-8")
            col = "0x" + acc if (i == len(lines) - 1 and len(lines) > 1) else "white"
            vf.append(f"drawtext=fontfile=f.ttf:textfile=c{i}.txt:expansion=none:fontsize={fs}:fontcolor={col}:borderw={bw}:bordercolor=black:"
                      f"shadowx={max(2, bw // 2)}:shadowy={max(2, bw // 2)}:shadowcolor=black@0.55:x=(w-text_w)/2:y={y0 + i * lh}")
        src_in = ["-ss", f"{max(0.0, t):.2f}", "-i", os.path.abspath(str(video))]
        if emote and os.path.isfile(emote):                  # your chibi, showing the strongest feeling of the clip, in the lower corner
            es = int(min(W, H) * (.42 if H > W else .55)) // 2 * 2
            ex = f"W-w-{int(W * max(.04, safe[1]))}"; ey = f"H-h-{int(H * max(.12, safe[0] + .03))}"
            fc = "[0:v]" + ",".join(vf) + f"[bg];[1:v]format=rgba,scale={es}:{es}:force_original_aspect_ratio=decrease[em];[bg][em]overlay=x={ex}:y={ey}[o]"
            r = subprocess.run([FF, "-y", "-v", "error"] + src_in + ["-i", os.path.abspath(emote), "-filter_complex", fc, "-map", "[o]", "-frames:v", "1", "-q:v", "2",
                                "-update", "1", os.path.abspath(str(dest))], capture_output=True, text=True, errors="replace", cwd=tmp, **NOWIN)
            if r.returncode == 0 and os.path.isfile(str(dest)): return True
        r = subprocess.run([FF, "-y", "-v", "error"] + src_in + ["-vf", ",".join(vf), "-frames:v", "1", "-q:v", "2",
                            "-update", "1", os.path.abspath(str(dest))], capture_output=True, text=True, errors="replace", cwd=tmp, **NOWIN)
    return r.returncode == 0 and os.path.isfile(str(dest))


def srt_time(t):
    t = max(0.0, t); ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms % 3600000 // 60000:02d}:{ms % 60000 // 1000:02d},{ms % 1000:03d}"


def write_srt(owords, path, censor=frozenset()):
    """Subtitle file (.srt) for the finished clip - handy for YouTube, TikTok or other editors."""
    ws = [{**w, "w": "*" * len(w["w"]) if is_cens(w, censor) else w["w"]} for w in owords]
    cjk = bool(ws) and sum(is_cjk(w["w"]) for w in ws) / len(ws) > .3
    out = []
    phs = phrases(ws, 7, 20 if cjk else 52, cjk=cjk)
    for i, ph in enumerate(phs, 1):
        end = ph[-1]["end"] + .2
        if i < len(phs): end = min(end, phs[i][0]["start"] - .01)          # cues never overlap
        body = two_lines(("" if cjk else " ").join(w["w"] for w in ph), cjk).replace("\\N", "\n")
        out.append(f"{i}\n{srt_time(ph[0]['start'])} --> {srt_time(max(end, ph[0]['start'] + .3))}\n{body}\n")
    Path(path).write_text("\n".join(out), encoding="utf-8")


def write_transcript(ow, mp4, censor=frozenset(), dur=0.0):
    """2.0: what was said in a clip, as a readable text file with times (<name>_transcript.txt) and as a web-video subtitle file (<name>.vtt)."""
    import vcouts
    ws = [{**w, "w": "*" * len(w["w"]) if is_cens(w, censor) else w["w"]} for w in ow if str(w.get("w", "")).strip()]
    if not ws: return
    cjk = sum(is_cjk(w["w"]) for w in ws) / len(ws) > .3; join = "" if cjk else " "
    phs = phrases(ws, 12, 30 if cjk else 80, cjk=cjk)
    stem = Path(mp4).with_suffix("")
    head = f"TRANSCRIPT - {Path(mp4).stem}\n{vcouts.mmss(dur or ws[-1]['end'])} long, {len(ws)} words\n\n"
    Path(str(stem) + "_transcript.txt").write_text(head + "\n".join(f"[{vcouts.mmss(ph[0]['start'])}] " + join.join(w["w"] for w in ph) for ph in phs) + "\n", encoding="utf-8")
    cues = ["WEBVTT\n"]
    for i, ph in enumerate(phs):
        end = ph[-1]["end"] + .2
        if i + 1 < len(phs): end = min(end, phs[i + 1][0]["start"] - .01)
        cues.append(f"{vcouts.vtt_time(ph[0]['start'])} --> {vcouts.vtt_time(max(end, ph[0]['start'] + .3))}\n" + two_lines(join.join(w["w"] for w in ph), cjk).replace("\\N", "\n") + "\n")
    Path(str(stem) + ".vtt").write_text("\n".join(cues), encoding="utf-8")


def style_hashtags(style, fx):
    t = {"gameplay": ["#gaming", "#gameplay"], "story": ["#storytime"], "mix": ["#gaming", "#storytime"]}.get(style, [])
    if fx.get("hearts") or fx.get("sparkle") or fx.get("petals"): t.append("#kawaii")
    if fx.get("vhs"): t.append("#retro")
    return t


def mark_private(words, o, say=True):
    """2.3 privacy guard: words that give away an e-mail, phone number, address, link, a real name slip or one of your private words get a 'priv' flag
    (bleeped and starred everywhere) or, in 'warn' mode for patterns, a 'pwarn' flag (only reported). Old flags are cleared first, so edited captions are checked again."""
    try:
        import vcsafe
        base = [({k: v for k, v in w.items() if k not in ("priv", "pwarn")} if ("priv" in w or "pwarn" in w) else w) for w in words]
        out, rep_ = vcsafe.mark_words(base, o)
    except Exception as e:
        print("(privacy guard skipped:", str(e)[:80] + ")"); return words
    if rep_ and say:
        n_b = sum(1 for r in rep_ if r["bleep"])
        print(f"Privacy guard: {len(rep_)} spot{'s' if len(rep_) != 1 else ''} found in what was said ({n_b} bleeped, {len(rep_) - n_b} only reported).")
        for r in rep_[:6]:
            t = int(r["start"]); print(f"   {r['label']} at {t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" + (" - bleeped" if r["bleep"] else " - listen to it"))
        if len(rep_) > 6: print(f"   ... and {len(rep_) - 6} more")
    return out


def load_words(a, o):
    return mark_private(transcribe(a.video, a.model, a.device, o["lang"], o["translate"], o["hint"], o["fixes"]), o)


# ---------------- 2.2 smart clip choosing ----------------
def smart_meta(words, sc, s0, e0):
    """Kind of moment (gameplay / reaction / talking / story / singing), how sure that is, and plain reasons. Needs the analysis of features()."""
    try:
        import vcsmart
        mk, cur = AN.get("marks"), AN.get("curves")
        if mk is None: return {}
        kind, conf, _ = vcsmart.type_for(words, s0, e0, mk, cur, sc)
        why = vcsmart.reasons(words, s0, e0, mk, cur, sc, AN.get("onsets", ()), AN.get("chat"), kind)
        try:
            import vcclues
            extra = vcclues.reasons((AN.get("clues") or {}).get("parts"), s0, e0)
            if extra: why = (extra[:2] + [w_ for w_ in why if w_ != "Steady energy"])[:5]
        except Exception: pass
        return dict(kind=kind, conf=conf, why=why)
    except Exception: return {}


def look_range(o, n):
    """(from, to) seconds of the only part of the VOD to look in ("Only look between"), or (0, None) for all of it."""
    try:
        import vcmore
        a, b = vcmore.parse_time(o.get("range_from")), vcmore.parse_time(o.get("range_to"))
    except Exception: return 0, None
    a = 0 if a is None else max(0, min(int(a), max(0, n - 12)))
    b = None if b is None else min(int(n), int(b))
    if b is not None and b - a < 12: return 0, None
    return a, b


def taste_now():
    """What the clips you starred / posted / deleted say about what you like (None until at least 3 were starred or posted)."""
    try:
        import vcmore, vcsmart
        return vcsmart.taste(vcmore.ledger_all())
    except Exception: return None


def smart_plan(sc, words, n, lo, hi, gap, style, prof, o, made=(), ra=0, rb=None, tst=None):
    """Choose the moments of a Shorts run the 2.2 way. Every strong window gets a KIND, its own length (when "smart length" is on), a clean start
    (no "hey guys welcome back"), a story that starts and ends on its sentences, an end right after the payoff (when asked) - then the best ones are
    picked one by one, so the same kind of clip or the same joke does not fill the whole list. Returns (jobs [(start, end, segments)], metas, skipped)."""
    import vcsmart, vcclues
    mk, cur = AN.get("marks"), AN.get("curves")
    mid = int((lo + hi) / 2); use_len = bool(o.get("smart_len")); use_taste = bool(tst) and bool(o.get("use_taste"))
    ranked = top_windows(sc, mid, max(1, mid // 2), prof, ra, rb)
    cl = AN.get("clues") or {}
    zones = cl.get("zones") or []
    cmds = [(t_, c_) for t_, c_ in (cl.get("cmds") or []) if ra - 5 <= t_ <= (rb if rb else len(sc)) + 5]
    forced = []                                                  # 2.3: moments viewers asked for with !clip are always looked at, even when the energy score alone would not rank them
    for t_, c_ in cmds:
        i_ = int(max(ra, min(t_ - .4 * mid, (rb if rb else len(sc)) - mid - 1)))
        if i_ >= 0: forced.append((wscore(sc, i_, mid) + 1.0 + .5 * min(c_, 4), i_))

    def build(score, i):
        kind, conf, _ = vcsmart.type_for(words, i, i + mid, mk, cur, sc)
        lo_k, hi_k = vcsmart.smart_range(kind, lo, hi) if use_len else (lo, hi)
        if use_taste: lo_k, hi_k = vcsmart.taste_range(tst, lo_k, hi_k)
        gap_k = None if (kind == "singing" and gap is not None) else gap          # never cut the quiet bits out of a song
        qv = AN.get("quiet") if kind in ("gameplay", "reaction") else None        # action keeps its sound: only pauses that are really quiet are cut
        r = fit_clip(sc, words, i, lo_k, hi_k, gap_k, style == "story" or kind in ("story", "talking", "reaction"), limit=rb, quiet=qv)     # speech clips start on a sentence
        if not r: return None
        s0, e0, segs = r
        if kept_len(segs) < max(8.0, lo_k * .5): return None                      # mostly cut-away silence: not a clip
        if o.get("skip_greet", True):
            g = vcsmart.greeting_end(words, s0)
            if g is not None and s0 + .2 < g < s0 + 7.5:
                r2 = fit_clip(sc, words, g, lo_k, hi_k, gap_k, False, limit=rb, quiet=qv)
                if r2 and kept_len(r2[2]) >= lo_k * .8: s0, e0, segs = r2
        if kind == "story":
            ns, ne = vcsmart.story_adjust(words, s0, e0, lo_k * .6, hi_k * 2.2)
            if (ns, ne) != (s0, e0):
                sg = keep_segments(ns, ne, words, gap_k, quiet=qv)
                if lo_k * .8 <= kept_len(sg) <= hi_k * 1.15: s0, e0, segs = ns, ne, sg
        if o.get("tight_end"):
            ne = vcsmart.payoff_end(words, s0, e0, sc, lo_k, AN.get("onsets", ()))
            if ne < e0 - .5:
                sg = keep_segments(s0, ne, words, gap_k, quiet=qv)
                if kept_len(sg) >= max(8.0, lo_k * .8): e0, segs = ne, sg
        if zones and vcclues.zones_overlap(s0, e0, zones) > .4: return None            # 2.3: a BRB / intermission / goodbye part
        if o.get("lead_trim", True) or o.get("tail_trim", True):                       # 2.3: open on action, clean ending
            try:
                sg2, ca, cb = vcclues.trim_edges(segs, words, AN.get("quiet"), bool(o.get("lead_trim", True)), bool(o.get("tail_trim", True)), min_len=max(8.0, lo_k * .8))
                if ca or cb: segs, s0, e0 = sg2, sg2[0][0], sg2[-1][1]
            except Exception: pass
        return dict(score=score, rat=rating(score), s0=s0, e0=e0, segs=segs, kind=kind, conf=conf)
    pool, done, skipped, got, limit = [], 0, 0, [], max(14, n * 6)
    for score, i in forced:
        c = build(score, i)
        if c and not (made and overlaps_made(c["s0"], c["e0"], made)): pool.append(c)
    while True:
        while done < min(limit, len(ranked)):
            score, i = ranked[done]; done += 1
            c = build(score, i)
            if not c: continue
            if made and overlaps_made(c["s0"], c["e0"], made): skipped += 1; continue
            if not any(abs(c["s0"] - p_["s0"]) < 2 and abs(c["e0"] - p_["e0"]) < 2 for p_ in pool): pool.append(c)
        got, cnt, rest, strict = [], {}, list(pool), bool(o.get("variety", True))
        while rest and len(got) < n:
            best = None
            for c in rest:
                if any(not (c["e0"] <= g["s0"] or c["s0"] >= g["e0"]) for g in got): continue
                if strict and any(vcsmart.similar_moments(words, c["s0"], c["e0"], g["s0"], g["e0"]) for g in got): continue
                adj = (c["rat"] + 8) * (tst["kinds"].get(c["kind"], 1.0) if use_taste else 1.0) * (0.9 ** cnt.get(c["kind"], 0) if o.get("variety", True) else 1.0)
                req = sum(c_ for t_, c_ in cmds if c["s0"] - 2 <= t_ <= c["e0"])
                if req: adj *= 1 + .5 * min(req, 3)                                    # 2.3: chat asked for this moment (x1.5 for one request, x2.5 for three or more)
                if o.get("spread"): adj *= vcclues.spread_factor(c["s0"], c["e0"], [(g["s0"], g["e0"]) for g in got], vcclues.spread_zone(len(sc), n))          # 2.3: not all five in the same half hour
                if best is None or adj > best[0]: best = (adj, c)
            if not best:
                if strict: strict = False; continue            # not enough different moments: allow a repeat of a joke rather than fewer clips
                break
            got.append(best[1]); cnt[best[1]["kind"]] = cnt.get(best[1]["kind"], 0) + 1; rest.remove(best[1])
        if len(got) >= n or done >= len(ranked) or done >= 400: break
        limit *= 3
    jobs = [(g["s0"], g["e0"], g["segs"]) for g in got]
    metas = []
    for g in got:
        m = smart_meta(words, sc, g["s0"], g["e0"])
        m.update(kind=g["kind"], conf=g["conf"], rat=g["rat"]); metas.append(m)
    return jobs, metas, skipped


def cmd_shorts(a):
    o = get_opts(getattr(a, "opts", None))
    info = check_video(a.video)
    words = load_words(a, o)
    prof = PROFILES.get(a.style, PROFILES["mix"])
    sc = features(a.video, words, prof, o)
    I, gap, cens = a.fx.get("intensity", 1.0), (None if a.no_silence else a.gap), load_censor(a.censor, o["swears"])
    cam = a.cam if a.cam and valid_cam(a.cam, info["w"], info["h"]) else None
    layout = a.layout if a.layout in LAYOUTS else "blur"
    if a.cam and not cam: print("The selected model/cam area doesn't fit this video - select it again. Using the blurred layout for now.")
    if layout == "custom" and not get_opts(o)["custom_layout"]: layout = "blur"
    if needs_cam(layout, o) and not cam:
        if not a.cam: print("No model/cam area selected - using the blurred-background layout.")
        layout = "blur"
    if info["h"] and OUT["res"] > info["h"]:
        print(f"Note: this VOD is {info['h']}p, so the {OUT['res']}p output is upscaled (bigger file, same detail).")
    outdir = Path(a.out) / "Shorts"
    if o.get("day_folder"):                                                         # 2.3: one folder per day
        try: import vcshare; outdir = outdir / vcshare.day_folder()
        except Exception: pass
    if o["vod_folder"]: outdir = outdir / (safe_stem(a.video) or "VOD")            # 2.0: one folder per VOD
    outdir.mkdir(parents=True, exist_ok=True)
    lo = float(getattr(a, "len_min", None) or getattr(a, "len", None) or 35); hi = float(getattr(a, "len_max", None) or lo)
    if lo > hi: lo, hi = hi, lo
    jobs, wins, metas = [], list(getattr(a, "windows", None) or []), []
    smart = bool(o.get("smart")) and AN.get("marks") is not None
    if wins:                                       # exact moments chosen by the user (e.g. from the Best Moments list)
        for s0, e0 in wins:
            segs = keep_segments(s0, e0, words, gap)
            if kept_len(segs) >= 2:
                jobs.append((s0, e0, segs)); metas.append(smart_meta(words, sc, s0, e0) if smart else {})
    else:
        mid = int((lo + hi) / 2); made = load_made(a.video) if o["fresh"] else []
        ra, rb = look_range(o, len(sc))
        if ra or rb: print(f"Only looking between {hms(ra)} and {hms(rb if rb else len(sc))} of the video.")
        tst = taste_now() if o.get("use_taste") else None
        if o.get("use_taste"): print("Using what you like (from the clips you kept)." if tst else "Not enough kept clips to learn your taste yet (star or post at least 3).")

        def choose(made):
            got, skipped = [], 0
            for _, i in top_windows(sc, mid, max(1, mid // 2), prof, ra, rb):
                if len(got) >= a.n: break
                r = fit_clip(sc, words, i, lo, hi, gap, a.style == "story", limit=rb)
                if r and made and overlaps_made(r[0], r[1], made): skipped += 1; continue
                if r and all(r[1] <= x or r[0] >= y for x, y, _ in got): got.append(r)
            return got, skipped

        def pick(made):
            if smart: return smart_plan(sc, words, a.n, lo, hi, gap, a.style, prof, o, made, ra, rb, tst)
            j_, sk_ = choose(made); return j_, [], sk_
        jobs, metas, skipped = pick(made)
        if skipped and 0 < len(jobs) < a.n:
            print(f"Only {len(jobs)} new moment{'s' if len(jobs) != 1 else ''} left in this video - the other good parts were already made. "
                  "(Untick “Skip moments I already made” to allow repeats, or press Start over.)")
        if not jobs and made:                          # nothing new left: make the best ones again instead of stopping
            print("Every good moment of this video was made before, so I'm making the best ones again. (Press “Start over” to clear the list.)")
            jobs, metas, _ = pick([])
    if not jobs: raise RuntimeError("This VOD is shorter than one clip - try a shorter clip length.")
    if o.get("disk_guard", True):                          # 2.3: stop before rendering when the drive cannot hold the clips
        try:
            import vcsafe
            nshape = len([x for x in str(o.get("extra_shapes", "")).split(",") if x in ASPECTS and x != o["aspect"]])
            need = est_size_mb(sum(kept_len(j[2]) for j in jobs)) * (1 + nshape) * 1.3 + 25 * len(jobs)
            lvl, msg, _ = vcsafe.disk_check(outdir, need)
            if lvl == "stop": raise RuntimeError(msg)
            if lvl == "warn": print(msg)
        except RuntimeError: raise
        except Exception: pass
    plan = []                                              # everything that touches the shared analysis is decided here, before any worker starts
    try: import vcsmart
    except Exception: vcsmart = None
    for k, (s0, e0, segs) in enumerate(jobs):
        d = kept_len(segs)
        meta = dict(metas[k]) if k < len(metas) else {}
        kind = meta.get("kind")
        style_k = a.style
        if o.get("auto_look") and kind and vcsmart:               # 2.2: the look follows the kind of clip (pops for gameplay, lines for stories...)
            ti = vcsmart.TYPE_INFO[kind]; style_k = ti["style"]; meta["cap"] = ti["cap"]
            if style_k != a.style and style_k in FX: meta["fx"] = {kk: vv for kk, vv in FX[style_k].items()}
        per = {"gameplay": 6, "story": 14}.get(style_k, 9)
        evs = pick_events(sc, words, s0, e0, max(1, round(d / per * I)), strength=True)
        ev = [t for t, _ in evs]
        meta["ev_rank"] = [t for t, _ in sorted(evs, key=lambda x: -x[1])]
        if o.get("react_words") and AN.get("marks") is not None and vcsmart:
            meta["react"] = [(t_, key) for t_, key in ((tmap(segs, s0 + rel), key) for rel, key in vcsmart.reaction_events(words, s0, e0, AN["marks"], AN.get("curves"))) if t_ is not None]
        a_, b_ = int(s0), max(int(s0) + 1, int(e0))
        hype = rating(float(np.max(sc[a_:b_]))) if len(sc[a_:b_]) else None
        try:
            import vcouts
            hook_nm = first_words(words, s0, 5, cens)
            try: import vcsafe; hook_nm = vcsafe.scrub_text(hook_nm, o, repl="")             # 2.3: nothing private in a file name
            except Exception: pass
            nm = vcouts.clip_name(o["name_pattern"], safe_stem(a.video), k + 1, hook_nm, o["game"], o["channel"], s0, kind=kind or "", score=hype, length=d)
        except Exception: nm = f"{safe_stem(a.video)}_short{k + 1}"
        out = unique_path(outdir / f"{nm}.mp4")
        tags = describe(sc, words, s0, e0)["tags"] if o["post_kit"] else []
        plan.append((s0, e0, segs, d, ev, out, tags, hype, meta))
    rv = getattr(a, "review", None)
    if callable(rv) and not a.no_captions:                 # the app lets the user check / correct the captions of every clip first
        items = [dict(k=k, start=p[0], dur=p[3], text=" ".join(w["w"] for w in words_in(words, p[2]))) for k, p in enumerate(plan)]
        try: texts = rv(items) or {}
        except BaseException as e:
            if "Cancelled" in str(e): raise
            texts = {}; print("(caption check skipped:", str(e)[:80] + ")")
        if texts:
            words = mark_private(apply_caption_edits(words, [p[2] for p in plan], texts), o, say=False)           # 2.3: corrected text is checked again
            print(f"Using your corrected captions for {len(texts)} clip{'s' if len(texts) != 1 else ''}.")
    eplans = emote_plans(o, words, [dict(k=k, label=f"Clip {k + 1}", start=p[0], segs=p[2], events=p[4]) for k, p in enumerate(plan)],
                         getattr(a, "emote_review", None))
    if a.fx.get("sfx") and any(p[4] for p in plan) and o["sfx_pack"] not in SFX_FILE_PACKS: hit_path(o["sfx_pack"])          # make the sound files once, not in every worker
    if a.fx.get("whoosh") and o["sfx_pack"] not in SFX_FILE_PACKS: whoosh_path()
    workers = auto_workers(len(jobs), o["aspect"])
    prog, lock, finished = [0.0] * len(jobs), threading.Lock(), [0]
    entries = []                                           # 2.3: what was made, for the highlights report / timestamps / community message

    def upd(k, f):
        with lock:
            prog[k] = f
            lab = f"Rendering clip {min(len(jobs), finished[0] + 1)}/{len(jobs)}" if workers == 1 else f"Rendering {len(jobs)} clips - {finished[0]} done"
            report("Rendering", sum(prog) / len(jobs), lab)

    def make_one(k):
        s0, e0, segs, d, ev, out, tags, hype, meta = plan[k]
        check_cancel()
        kind = meta.get("kind")
        lab = ""
        if kind and vcsmart: lab = " " + vcsmart.type_label(kind).lower()
        print(f"[{k + 1}/{len(jobs)}] {hms(s0)} ({d:.0f}s{lab}) -> {out.name}")
        ro = dict(o)
        ro["mood_kind"] = kind or ""                                                           # 2.3: music folder by mood
        try: import vcmedia; ro["mood_feel"] = vcmedia.dominant_feeling(words_in(words, segs))
        except Exception: ro["mood_feel"] = ""
        fxk = {**a.fx, **meta["fx"]} if meta.get("fx") else a.fx
        if meta.get("cap"): ro["cap_style"] = meta["cap"]
        if meta.get("react"): ro["react_plan_t"] = meta["react"]
        rinfo = {}
        if eplans is not None: ro["emote_plan"] = eplans.get(k, [])
        if o["part_badge"] and len(jobs) > 1: ro["part"] = (k + 1, len(jobs))                # 2.0: "PART 2/5" on every clip of this run
        hook_k = pick_hook(words, segs, s0, k, o, cens, kind)
        ow, _ = render(a.video, segs, words, out, layout, cam, not a.no_captions, cens, fxk, ev, hook_k, lambda f: upd(k, f), opts=ro, info=rinfo)
        hit = [tmap(segs, e) for e in ev]; hit = [x for x in hit if x is not None and 2.5 <= x <= d - .6]
        tc = (hit[0] + .25) if hit else min(max(d * .4, 3.0 if d > 8 else .5), max(.5, d - .6))
        tc += rinfo.get("intro", 0.0)                # the cover is taken from the finished video, which starts with the intro (if any)
        acc_ = str(a.fx.get("accent") or "ff4d8d").lstrip("#"); cjk_ = bool(ow) and sum(is_cjk(w["w"]) for w in ow) / len(ow) > .3
        strongest = ""
        if eplans is not None:
            its = [x for x in eplans.get(k, []) if x.get("src") not in ("pause", "loud") and os.path.isfile(str(x.get("path", "")))]
            if its: strongest = vcemotes_small(max(its, key=lambda x: x.get("score", 0))["path"])
        shifted = [tmap(segs, e) for e in meta.get("ev_rank", [])]                    # where the big moments are inside the clip, strongest first
        shifted = [x + rinfo.get("intro", 0.0) for x in shifted if x is not None and 1.2 <= x <= d - .8]
        kit_c = []

        def kit_fn():
            if not kit_c: kit_c.append(short_kit(ow, o, a, k, d, kind))
            return kit_c[0]
        if o["cover"] and not CANCEL.is_set():       # a cover picture for the upload page (YouTube / TikTok let you choose one)
            try:
                try: kit = kit_fn()
                except Exception: kit = dict(titles=[(o["game"] + " highlight") if o["game"] else "Stream highlight"])
                em_path = strongest if o["emote_cover"] else ""
                if o.get("cover_sharp", True):                                  # 2.3: the sharpest frame near that second, not a blurry one
                    try:
                        import vcmedia; tc = vcmedia.best_time(str(out), tc, FF, NOWIN)
                    except Exception: pass
                make_cover(out, out.with_name(out.stem + "_cover.jpg"), kit["titles"], o, tc, acc_, cjk=cjk_, emote=em_path)
                if o.get("cover_alts") and not CANCEL.is_set():                 # 2.3: two more covers, other frames, other title ideas
                    import vcmedia
                    alts = [t_ for t_ in vcmedia.cover_candidates(str(out), [tc] + shifted[:3], FF, NOWIN, 3) if abs(t_ - tc) >= 1.0][:2]
                    tl = list(kit["titles"])
                    for j, t_ in enumerate(alts):
                        rot = tl[j + 1:] + tl[:j + 1] if len(tl) > 1 else tl
                        make_cover(out, out.with_name(f"{out.stem}_cover_{'bc'[j]}.jpg"), rot, o, t_, acc_, cjk=cjk_, emote=em_path)
            except Exception as e: print("(couldn't make the cover picture:", str(e)[:80] + ")")
        try:
            if o["transcript"] and ow: write_transcript(ow, out, cens, d)
            if o["srt"] and ow: write_srt(ow, out.with_suffix(".srt"), cens)
        except Exception as e: print("(couldn't write the subtitle file:", str(e)[:80] + ")")
        extras = bool(o.get("slowmo") or o.get("freeze") or o.get("teaser")) and _vm is not None and bool(shifted) and not CANCEL.is_set()
        done_x = []
        if extras:
            done_x = _vm.finish_clip(str(out), o, shifted, FF, NOWIN, venc(), print)
            if done_x:
                print("   extras:", ", ".join(done_x)); d = probe(str(out))[0] or d
        for shp in [x for x in str(o.get("extra_shapes", "")).split(",") if x in ASPECTS and x != o["aspect"]]:     # 2.2: square / landscape copies
            if CANCEL.is_set(): break
            try:
                out2 = unique_path(out.with_name(f"{out.stem}_{shp.replace(':', 'x')}.mp4"))
                render(a.video, segs, words, out2, layout, cam, not a.no_captions, cens, fxk, ev, hook_k, None, opts=dict(ro, aspect=shp))
                if extras and done_x: _vm.finish_clip(str(out2), o, shifted, FF, NOWIN, venc(), print)
                print(f"   copy {shp} -> {out2.name}")
            except BaseException as e:
                if "Cancelled" in str(e): raise
                print(f"   (couldn't make the {shp} copy:", str(e)[:80] + ")")
        try:
            if o["post_kit"]:
                out.with_suffix(".txt").write_text(short_post(ow, o, tags, a, k, hype, d, kind, meta.get("why")), encoding="utf-8")
        except Exception as e: print("(couldn't write the title file:", str(e)[:80] + ")")
        fin = dict(done=[], notes=[], files=[], check=[])
        pnotes = []
        try:
            import vcpipe
            pnotes = vcpipe.privacy_notes(ow)
            for n_ in pnotes: print("   privacy:", n_)
            title_ = ""
            if o.get("meta_tags"):
                try: title_ = kit_fn()["titles"][0]
                except Exception: title_ = ""
            fin = vcpipe.finish_clip(out, dict(o=o, ff=FF, nowin=NOWIN, words=ow, write_srt=write_srt, censor=cens, hits=shifted, kit_fn=kit_fn, kind=kind, why=meta.get("why"), dur=d,
                                               platform="", cancelled=CANCEL.is_set, log=print, title=title_,
                                               extra_check=[dict(level="warn", text=n_) for n_ in pnotes if "NOT bleeped" in n_]))
            if fin["done"]: print("   finished:", ", ".join(fin["done"]))
        except BaseException as e:
            if "Cancelled" in str(e): raise
            print("   (finishing steps skipped:", str(e)[:80] + ")")
        titles_ = []
        try: titles_ = list(kit_c[0]["titles"][:3]) if kit_c else []
        except Exception: pass
        if _vm:
            try: _vm.ledger_add(dict(path=str(out), vod=str(a.video), start=round(s0, 2), end=round(e0, 2), kind=kind or "", conf=round(float(meta.get("conf", 0) or 0), 2), hype=hype,
                                     dur=round(float(d), 1), reasons=list(meta.get("why") or [])[:5], look=dict(style=a.style, cap=ro["cap_style"], layout=layout, aspect=o["aspect"]),
                                     extras=done_x, tags=[], note="", titles=titles_, notes=list(fin["notes"])[:6] + [n_ for n_ in pnotes if n_ not in fin["notes"]][:4]))
            except Exception: pass
        if o.get("maybe_folder"):                          # 2.3: weak clips go to a "Maybe" folder, so the main folder only has the good ones
            try:
                import vcshare
                dest_ = vcshare.maybe_target(str(out), hype, o.get("maybe_below", 30))
                if dest_:
                    newp = vcshare.move_clip(str(out), dest_)
                    if newp:
                        if _vm: _vm.ledger_move(str(out), newp)
                        print(f"   hype {hype} is low - moved to the Maybe folder")
                        out = Path(newp)
            except Exception as e: print("   (couldn't use the Maybe folder:", str(e)[:80] + ")")
        with lock:
            entries.append(dict(path=str(out), start=round(s0, 2), end=round(e0, 2), dur=round(float(d), 1), kind=kind or "", hype=hype,
                                reasons=list(meta.get("why") or [])[:5], titles=titles_, notes=list(fin["notes"])[:4]))
        if _vm and o.get("ready_dir"):
            try:
                nrd = _vm.copy_ready(str(out), o["ready_dir"])
                if nrd: print(f"   copied to your ready folder ({nrd} file{'s' if nrd != 1 else ''})")
            except Exception: pass
        with lock:
            finished[0] += 1; save_made(a.video, [(s0, e0)])
        upd(k, 1.0)
    if workers == 1:
        for k in range(len(jobs)): make_one(k)
    else:
        from concurrent.futures import ThreadPoolExecutor
        print(f"Rendering {workers} clips at a time.")
        stop, errs = threading.Event(), []

        def guarded(k):
            if stop.is_set(): return
            try: make_one(k)
            except BaseException as e:
                errs.append(e); stop.set()
        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(guarded, range(len(jobs))))
        if errs:
            real = [e for e in errs if "Cancelled" not in str(e)]
            raise (real or errs)[0]
    report("Rendering", 1, "Done")
    try:
        import vcpipe
        vcpipe.finish_run(entries, dict(o=o, outdir=str(outdir), vod_name=safe_stem(a.video), unique=lambda p_: str(unique_path(p_)), log=print))
    except Exception as e: print("(run files skipped:", str(e)[:80] + ")")
    if o.get("game_memory") and not wins:
        try:
            import vcshare; vcshare.game_put(o["game"], dict(n=a.n, len_min=lo, len_max=hi, style=a.style, layout=a.layout if a.layout in LAYOUTS else layout))
        except Exception: pass
    print(f"Done: {len(jobs)} shorts in {outdir}")


def pick_recap(sc, words, target, R, gap, tmin=None, tmax=None, window=None):
    """Choose the moments of a long-form recap. Every style has its own pacing:
    highlight = the strongest short bursts, story = the best stretch from every part of the stream, gameplay = long action stretches.
    The result lands between `tmin` and `tmax` seconds when the stream has enough in it. `window` = (from, to) seconds: one game of a long stream."""
    n = len(sc); lo, hi = R["lo"], R["hi"]
    w0, w1 = (0, n) if not window else (max(0, int(window[0])), min(n, int(window[1])))
    if w1 - w0 < 8: return []
    tmin = float(tmin) if tmin else target * .88; tmax = float(tmax) if tmax else target * 1.12
    mid = max(6, min(int((lo + hi) / 2), (w1 - w0) // 2))
    lo, hi = min(lo, mid * 1.4), min(hi, max(mid * 1.6, mid + 6))
    cands = top_windows(sc, mid, max(1, mid // 3), R, w0, w1)         # best first
    fitted = {}
    def fit(i):
        if i not in fitted: fitted[i] = fit_clip(sc, words, i, lo, hi, gap, R["snap"], w1)
        return fitted[i]
    picked, total = [], 0.0
    def add(i, sco):
        nonlocal total
        r = fit(i)
        if r and all(r[1] <= x or r[0] >= y for x, y, _, _ in picked):
            picked.append((r[0], r[1], r[2], sco)); total += kept_len(r[2]); return True
        return False
    if R["spread"] and cands:                                          # story: walk through the whole stream in order
        nb = max(2, int(round(target / (.85 * mid))))
        seen = set(); span = max(1.0, (w1 - w0) / nb)
        for sco, i in cands:
            b = min(nb - 1, int((i - w0) / span))
            if b not in seen and add(i, sco): seen.add(b)
    for sco, i in cands:
        if total >= target: break
        add(i, sco)
    for sco, i in cands:                                               # still under the minimum: keep adding the next best
        if total >= tmin: break
        add(i, sco)
    guard = 0
    while total > tmax and len(picked) > 1 and guard < 80:             # over the maximum: drop the weakest one that keeps us above the minimum
        guard += 1; picked.sort(key=lambda p: p[0])
        pool = picked[1:-1] if (R["spread"] and len(picked) > 2) else picked
        ok = [p for p in pool if total - kept_len(p[2]) >= tmin]
        w = min(ok, key=lambda p: p[3]) if ok else min(pool, key=lambda p: abs(total - kept_len(p[2]) - target))
        picked.remove(w); total -= kept_len(w[2])
    def refit(k, new_lo, new_hi):
        s0, e0, ss, sco = picked[k]
        r = fit_clip(sc, words, s0, new_lo, new_hi, gap, False, w1)
        if r and all(r[1] <= x or r[0] >= y for j, (x, y, _, _) in enumerate(picked) if j != k):
            picked[k] = (r[0], r[1], r[2], sco); return True
        return False
    if total > tmax:                                                   # a little over: shorten the weakest moments to fit
        for k in sorted(range(len(picked)), key=lambda k: picked[k][3]):
            cur = kept_len(picked[k][2]); hi2 = cur - (total - tmax); lo2 = max(8.0, cur - (total - tmin))
            if hi2 >= 8 and lo2 <= hi2 and refit(k, lo2, hi2):
                total = sum(kept_len(p[2]) for p in picked)
                if total <= tmax: break
    elif total < tmin:                                                 # a little under: let the best moments run longer
        for k in sorted(range(len(picked)), key=lambda k: -picked[k][3]):
            cur = kept_len(picked[k][2]); lo2 = cur + (tmin - total); hi2 = cur + (tmax - total)
            if hi2 <= hi * 1.8 and refit(k, lo2, hi2):
                total = sum(kept_len(p[2]) for p in picked)
                if total >= tmin: break
    return sorted(picked, key=lambda p: p[0])


# ---------------- long-form recap: length range, parts, one video per game ----------------
SPLITS = ("none", "count", "length", "games")


def length_range(a):
    """(shortest, longest, aim) in SECONDS. The app gives a range in minutes; older callers give one target (about 12% either side)."""
    lo, hi = getattr(a, "min_minutes", None), getattr(a, "max_minutes", None)
    if lo or hi:
        lo = float(lo or hi); hi = float(hi or lo)
        if lo > hi: lo, hi = hi, lo
        if hi - lo < .1 * hi: lo, hi = hi * .95, hi * 1.05
    else:
        m = float(getattr(a, "minutes", 10) or 10); lo, hi = m * .88, m * 1.12
    lo, hi = max(.4, lo) * 60, max(.5, hi) * 60
    return lo, hi, (lo + hi) / 2


def split_groups(weights, n):
    """Cut an ordered list into n runs with nearly equal totals (every run has at least one item) -> [[index, ...], ...]."""
    m = len(weights); n = max(1, min(int(n), m))
    if n == 1: return [list(range(m))]
    pre = [0.0]
    for w in weights: pre.append(pre[-1] + float(w))
    avg = pre[-1] / n; INF = float("inf")
    dp = [[INF] * (m + 1) for _ in range(n + 1)]; cut = [[0] * (m + 1) for _ in range(n + 1)]; dp[0][0] = 0.0
    for j in range(1, n + 1):
        for i in range(j, m + 1):
            for k in range(j - 1, i):
                if dp[j - 1][k] == INF: continue
                c = dp[j - 1][k] + (pre[i] - pre[k] - avg) ** 2
                if c < dp[j][i]: dp[j][i], cut[j][i] = c, k
    out, i = [], m
    for j in range(n, 0, -1):
        k = cut[j][i]; out.append(list(range(k, i))); i = k
    return out[::-1]


def pause_near(rms, t, span):
    """The quietest moment (3 s) within `span` seconds of t -> seconds. Used to cut a stream in the middle of a pause, not in a sentence."""
    n = len(rms)
    if n < 10: return float(t)
    a, b = int(max(0, t - span)), int(min(n - 1, t + span))
    if b - a < 6: return float(t)
    sm = np.convolve(rms, np.ones(3) / 3, "same"); med = float(np.median(rms[rms > 0])) if (rms > 0).any() else 1.0
    cost = sm[a:b + 1] / max(med, 1e-6) + np.abs(np.arange(a, b + 1) - t) / 120.0         # a quiet spot, but not one that is far away
    return float(a + int(np.argmin(cost))) + .5


def equal_edges(dur, n, rms=None, span=240):
    """n equal parts of a VOD, every cut moved to the nearest pause -> [0, cut1, ..., dur]."""
    n = max(1, int(n)); cuts = []
    for k in range(1, n):
        t = dur * k / n
        cuts.append(pause_near(rms, t, min(span, dur / n / 4)) if rms is not None and len(rms) else t)
    return [0.0] + cuts + [float(dur)]


# ---- finding the games / chapters of a long stream ----
GAME_SENS = {
    "games": dict(label="Different games only", floor=.26, mad=5.0, min_min=15.0, win=240),
    "chapters": dict(label="Games and chapters", floor=.18, mad=4.0, min_min=10.0, win=150),
    "scenes": dict(label="Every big scene change", floor=.11, mad=3.0, min_min=4.0, win=90),
}
VIS_STEP, _VW, _VH = 10, 64, 36
_CUE_RE = re.compile(r"next game|new game|another game|different game|switch(?:ing)? (?:to|games)|let'?s (?:play|start|get into)|"
                     r"(?:chapter|mission|level|episode|stage|act) (?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)|part (?:two|three|four|2|3|4)|"
                     r"welcome back|we'?re back|be right back|\bbrb\b|that'?s the end|game over|the credits|thanks for (?:watching|coming)", re.I)


def _vis_sig(F, mask):
    """A small fingerprint of every picture (frames N x 36 x 64 x 3): average colour, brightness spread, which colours, where the light is, how busy."""
    f = F.astype(np.float32); N = len(f); m = mask; mk = m[None]; cnt = float(max(1, m.sum()))
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    lum = .299 * r + .587 * g + .114 * b
    mean_rgb = np.stack([(c * mk).sum((1, 2)) / cnt for c in (r, g, b)], 1) / 255
    mx, mn = f.max(3), f.min(3); d = mx - mn
    w = (d / (mx + 1.0)) * (mx / 255.0) * mk                        # how colourful each pixel is
    colf = w.sum((1, 2)) / cnt
    h = np.where(mx == r, ((g - b) / (d + 1e-6)) % 6, np.where(mx == g, (b - r) / (d + 1e-6) + 2, (r - g) / (d + 1e-6) + 4))
    hb = np.minimum((h * 2).astype(np.int32), 11)
    hh = np.stack([(w * (hb == k)).sum((1, 2)) for k in range(12)], 1)
    hh = hh / np.maximum(hh.sum(1, keepdims=True), 1e-6); hh[colf < .01] = 0
    lb = np.minimum((lum // 32).astype(np.int32), 7)
    lh = np.stack([((lb == k) & mk).sum((1, 2)) / cnt for k in range(8)], 1)
    lmean = (lum * mk).sum((1, 2)) / cnt
    lumf = np.where(mk, lum, lmean[:, None, None])
    grid = lumf.reshape(N, 4, _VH // 4, 4, _VW // 4).mean((2, 4)).reshape(N, 16) / 255
    edge = (np.abs(np.diff(lumf, axis=2)).mean((1, 2)) + np.abs(np.diff(lumf, axis=1)).mean((1, 2))) / 255
    V = np.concatenate([mean_rgb, colf[:, None], lh, hh, grid, edge[:, None]], 1).astype(np.float32)
    return V, lmean < 14


def vdist(a, b):
    """How different two fingerprints (or averages of many) look, 0 (same) to 1 (nothing alike)."""
    cd = np.minimum(1, 2 * np.abs(a[..., 0:3] - b[..., 0:3]).mean(-1) + np.abs(a[..., 3] - b[..., 3]))
    ld = .5 * np.abs(a[..., 4:12] - b[..., 4:12]).sum(-1)
    hd = .5 * np.abs(a[..., 12:24] - b[..., 12:24]).sum(-1)
    gd = np.minimum(1, 2 * np.abs(a[..., 24:40] - b[..., 24:40]).mean(-1))
    ed = np.minimum(1, 6 * np.abs(a[..., 40] - b[..., 40]))
    return .22 * cd + .2 * ld + .26 * hd + .22 * gd + .10 * ed


def scan_visual(src, cam=None, step=VIS_STEP, info=None):
    """One tiny picture every `step` seconds (only the key frames are decoded, so even a 10-hour VOD takes a minute or two) -> (fingerprints, dark flags).
    The streamer's cam box is left out, so it doesn't matter that the face moves. Saved on disk."""
    info = info or probe_info(src); dur = float(info["dur"]); sw, sh = info["w"], info["h"]
    key = _an_key(src); ctag = hashlib.md5((cam or "").encode()).hexdigest()[:6]
    f = os.path.join(CACHE_DIR, f"vis1_{key}_{int(step)}_{ctag}.npz") if key else ""
    if f and os.path.exists(f):
        try:
            z = np.load(f)
            if len(z["V"]) > 0: report("Scanning", 1, "Using the saved scan"); return z["V"], z["dark"]
        except Exception: pass
    mask = np.ones((_VH, _VW), bool)
    if cam and sw and sh and valid_cam(cam, sw, sh):
        cw, ch, cx, cy = (int(x) for x in cam.split(":"))
        x0, x1 = int(cx / sw * _VW), int(math.ceil((cx + cw) / sw * _VW)); y0, y1 = int(cy / sh * _VH), int(math.ceil((cy + ch) / sh * _VH))
        mask[y0:y1, x0:x1] = False
        if mask.sum() < _VW * _VH * .4: mask[:] = True
    fsz, n_exp = _VW * _VH * 3, max(1, int(dur // step) + 1)
    Vs, Ds, got = [], [], 0
    for fast in (True, False):                          # key frames only; if that gives nothing (odd file), decode everything
        pre = ["-skip_frame", "nokey"] if fast else []
        proc = subprocess.Popen([FF, "-v", "quiet"] + pre + ["-i", src, "-an", "-sn", "-vf", f"fps=1/{step},scale={_VW}:{_VH}:flags=area",
                                                             "-pix_fmt", "rgb24", "-f", "rawvideo", "-"], stdout=subprocess.PIPE, **NOWIN)
        PROCS.add(proc)
        try:
            while True:
                if CANCEL.is_set(): proc.kill(); break
                buf = proc.stdout.read(fsz * 120)
                if not buf: break
                k = len(buf) // fsz
                if k == 0: continue
                F = np.frombuffer(buf[:k * fsz], np.uint8).reshape(k, _VH, _VW, 3)
                V, dk = _vis_sig(F, mask); Vs.append(V); Ds.append(dk); got += k
                report("Scanning", min(.98, got / n_exp), f"Looking through the video {got * step // 60} / {int(dur // 60)} min")
            proc.wait()
        finally: PROCS.discard(proc)
        check_cancel()
        if got >= 3: break
        Vs, Ds, got = [], [], 0
    if got < 3: raise RuntimeError("Couldn't read enough pictures from this video to look for games.")
    V, dark = np.concatenate(Vs), np.concatenate(Ds)
    if f:
        try:
            os.makedirs(CACHE_DIR, exist_ok=True); tmp = f + ".tmp.npz"; np.savez(tmp, V=V, dark=dark); os.replace(tmp, f)
        except Exception: pass
    report("Scanning", 1, "Scan done")
    return V, dark


def _novelty(V, Wn):
    """At every picture: do the `Wn` pictures after it look like anything seen in the `Wn` pictures before (and the other way round)?
    A scene that comes back (menu, map, cutscene) counts as 'seen', a new game does not - so a new game stands out as a clear peak."""
    N = len(V); nov = np.zeros(N)
    for i in range(3, N - 2):
        w = min(Wn, i, N - i)
        if w < 3: continue
        D = vdist(V[i:i + w][:, None, :], V[i - w:i][None, :, :])
        nov[i] = .5 * (float(np.median(D.min(1))) + float(np.median(D.min(0))))
    return nov


def _runs(flags, min_len=1):
    out, i, n = [], 0, len(flags)
    while i < n:
        if flags[i]:
            j = i
            while j < n and flags[j]: j += 1
            if j - i >= min_len: out.append((i, j))
            i = j
        else: i += 1
    return out


def _quiet_runs(rms, words, min_s=5):
    """Stretches (seconds) that are quiet AND nobody is talking: a break, a loading screen, 'be right back'."""
    n = len(rms)
    if n < 30 or not (rms > 0).any(): return []
    q = rms < .3 * float(np.median(rms[rms > 0]))
    talk = np.zeros(n, bool)
    for w in words:
        a, b = int(w["start"]), int(w["end"]) + 1
        if a < n: talk[max(0, a - 1):min(n, b + 2)] = True
    return _runs(q & ~talk, min_s)


def cue_times(words):
    """Where the streamer says things like 'next game', 'chapter two', 'we're back' -> [(seconds, phrase)]."""
    import bisect
    if not words: return []
    txt, pos = "", []
    for w in words:
        pos.append(len(txt)); txt += re.sub(r"[^\w']", "", str(w["w"]).lower()) + " "
    return [(float(words[max(0, bisect.bisect_right(pos, m.start()) - 1)]["start"]), m.group(0)) for m in _CUE_RE.finditer(txt)]


def _name_part(words, a, b, k, generic):
    """Name of the game played in [a, b): the one the streamer talks about most (what is said in the first minutes counts double)."""
    try:
        import vcpost
        txt = " ".join(w["w"] for w in words if a <= w["start"] < b); head = " ".join(w["w"] for w in words if a <= w["start"] < a + 300)
        votes = vcpost.game_votes(txt)
        for nme, c in vcpost.game_votes(head).items(): votes[nme] = votes.get(nme, 0) + c
        ok = {nme: c for nme, c in votes.items() if c >= (4 if nme in vcpost.WEAK else 2)}
        if ok: return max(ok, key=ok.get)
    except Exception: pass
    return f"{generic} {k}"


def find_games(video, words, cam=None, sens="chapters", count=None, min_minutes=None, info=None):
    """Where does one game (or chapter) of a long stream end and the next begin?
    Looks at how the picture changes (colours, brightness, layout) over minutes, helped by dark loading screens, breaks (quiet, nobody talking)
    and things the streamer says ('next game', 'chapter two'). `count`: you know how many parts there are. Returns
    [{start, end, name, why}] covering the whole video, in order."""
    S = GAME_SENS.get(sens, GAME_SENS["chapters"]); info = info or probe_info(video); dur = float(info["dur"])
    min_len = max(120.0, float(min_minutes or S["min_min"]) * 60); generic = "Game" if sens == "games" else "Part"
    one = [dict(start=0.0, end=dur, name=_name_part(words, 0, dur, 1, generic), why="")]
    if dur < max(240.0, min_len * 1.6) and not count: return one
    V, dark = scan_visual(video, cam, VIS_STEP, info); N = len(V); step = float(VIS_STEP)
    Wn = max(3, int(S["win"] / step)); nov = _novelty(V, Wn)
    try: rms = audio_stats(video, dur)[0]
    except Exception: rms = np.zeros(0, np.float32)
    quiet = _quiet_runs(rms, words)
    dark_runs = _runs(dark, 1); cues = cue_times(words)
    sup = np.zeros(N)
    for a_, b_ in dark_runs: sup[max(0, a_ - 2):b_ + 2] = np.maximum(sup[max(0, a_ - 2):b_ + 2], .08)
    for a_, b_ in quiet: i0, i1 = int(a_ / step) - 3, int(b_ / step) + 3; sup[max(0, i0):max(0, i1)] += .06
    for t, _ in cues: i = int(t / step); sup[max(0, i - 6):max(0, i + 7)] += .08
    score = nov + np.minimum(sup, .16)
    med = float(np.median(nov)); mad = 1.4826 * float(np.median(np.abs(nov - med)))
    thr = 0.0 if count else max(S["floor"], min(med + S["mad"] * mad, 2 * S["floor"])); h = max(3, Wn // 2)   # a busy stream raises the bar, but only so far
    cands = []
    for i in range(2, N - 2):
        if score[i] >= thr and (count or nov[i] >= .5 * S["floor"]) and score[i] >= score[max(0, i - h):i + h + 1].max() - 1e-9:
            cands.append((float(score[i]), i))
    gap_min = min_len if not count else min(min_len, max(120.0, dur / (count * 2)))
    chosen = []
    for sco, i in sorted(cands, reverse=True):
        t = i * step
        if t < gap_min or dur - t < gap_min: continue
        if all(abs(t - x) >= gap_min for x, _, _ in chosen): chosen.append((t, sco, i))
        if count and len(chosen) >= int(count) - 1: break
    gaps = []
    if len(words) > 1:
        ws = np.array([w["start"] for w in words]); we = np.array([w["end"] for w in words]); gg = ws[1:] - we[:-1]
        gaps = ((we[:-1] + ws[1:]) / 2)[gg >= .8]
    dcent = [(a_ + b_) / 2 * step for a_, b_ in dark_runs]; qcent = [(a_ + b_) / 2 for a_, b_ in quiet]
    def snap_t(t):
        for pts, span in ((dcent, 30), (qcent, 30)):
            near = [c for c in pts if abs(c - t) <= span]
            if near: return float(min(near, key=lambda c: abs(c - t)))
        if len(gaps):
            j = int(np.argmin(np.abs(gaps - t)))
            if abs(gaps[j] - t) <= 5: return float(gaps[j])
        return float(t)
    dstep = vdist(V[:-1], V[1:]); cuts = []
    for t, sco, i in chosen:
        j0, j1 = max(0, i - 3), min(N - 2, i + 3); j = j0 + int(np.argmax(dstep[j0:j1 + 1]))
        if dstep[j] >= .5 * nov[i]: t = (j + .5) * step                  # the biggest jump next to the peak: the change happened between these two pictures
        ct = snap_t(t); why = []
        if nov[i] >= S["floor"]: why.append("new picture")
        if any(abs(c - ct) <= 30 for c in dcent): why.append("dark screen")
        if any(abs(c - ct) <= 30 for c in qcent): why.append("a break")
        near = [p for tc, p in cues if abs(tc - ct) <= 60]
        if near: why.append(f"“{near[0].lower()}”")
        cuts.append((ct, " + ".join(why) or "new picture"))
    cuts.sort(); edges = [0.0] + [c for c, _ in cuts] + [dur]; out = []
    for k in range(len(edges) - 1):
        out.append(dict(start=float(edges[k]), end=float(edges[k + 1]), name=_name_part(words, edges[k], edges[k + 1], k + 1, generic),
                        why=(cuts[k - 1][1] if k > 0 else "")))
    return out


def games_merge(games, i):
    """Join part i with the next one."""
    g = [dict(x) for x in games]
    if 0 <= i < len(g) - 1:
        g[i]["end"] = g[i + 1]["end"]; del g[i + 1]
    return g


def games_split(games, i, t):
    """Cut part i in two at second t (it has to be inside the part)."""
    g = [dict(x) for x in games]
    if 0 <= i < len(g) and g[i]["start"] + 20 < t < g[i]["end"] - 20:
        b = dict(g[i], start=float(t), name=g[i]["name"] + " (2)", why="cut by you"); g[i]["end"] = float(t); g.insert(i + 1, b)
    return g


def games_text(games):
    return "\n".join(f"{hms(g['start'])} - {hms(g['end'])}  ({(g['end'] - g['start']) / 60:.0f} min)  {g['name']}" for g in games)


def cmd_games(a):
    """Find the games / chapters of a long stream. Returns the list (the app shows it so you can fix it)."""
    o = get_opts(getattr(a, "opts", None)); info = check_video(a.video)
    words = load_words(a, o)
    cam = a.cam if getattr(a, "cam", None) and valid_cam(a.cam, info["w"], info["h"]) else None
    g = find_games(a.video, words, cam, getattr(a, "sens", "chapters"), getattr(a, "count", None), getattr(a, "min_minutes", None), info)
    report("Scanning", 1, f"Found {len(g)} parts")
    print(f"Found {len(g)} part{'s' if len(g) != 1 else ''}:\n" + games_text(g))
    return g


def cut_copy(src, a, b, out, cb=None):
    """Cut [a, b) out of the video without re-encoding (instant; the cut lands on the nearest key frame, so it can be a second or two early)."""
    run_ff(["-ss", f"{max(0, a):.3f}", "-i", src, "-t", f"{b - a:.3f}", "-map", "0:v:0", "-map", "0:a:0?", "-c", "copy",
            "-avoid_negative_ts", "make_zero", "-movflags", "+faststart", str(out)], b - a, cb)


def _tag(name): return re.sub(r"[^\w]+", "", name.replace("&", "and"))[:24] or "x"


def _series_text(items, games=False):
    out = [f"{len(items)} videos from this stream:", ""]
    for k, it in enumerate(items, 1):
        out.append(f"{k}. {it['file']}   (stream {hms(it['a'])} - {hms(it['b'])}" + (f", video {it['len'] / 60:.1f} min" if it.get("len") else "") + ")")
        out.append(f"   title idea: " + (f"{it['label']}  (video {k} of {len(items)})" if games else f"Part {k}/{len(items)}"))
    return "\n".join(out) + "\n"


def _cut_parts(a, o, out, info, split, games):
    """No highlights - the whole stream, just cut into parts (copy, no re-encode)."""
    dur = float(info["dur"])
    if split == "games": wins = [(g["start"], g["end"], g.get("name") or f"Part {k}") for k, g in enumerate(games, 1)]
    else:
        n = int(getattr(a, "part_count", 0) or 0)
        if split == "length": n = max(1, int(round(dur / (float(getattr(a, "part_minutes", 60) or 60) * 60))))
        n = max(1, min(99, n or 2))
        try: rms = audio_stats(a.video, dur)[0]
        except Exception: rms = None
        ed = equal_edges(dur, n, rms); wins = [(ed[k], ed[k + 1], f"Part {k + 1} of {n}") for k in range(n)]
    made, items, cur = [], [], None
    try:
        for k, (s0, e0, name) in enumerate(wins, 1):
            check_cancel()
            tag = f"game{k}_{_tag(name)}" if split == "games" else f"part{k}of{len(wins)}"
            p = cur = unique_path(out.with_name(f"{out.stem}_{tag}{out.suffix}"))
            cut_copy(a.video, s0, e0, p, lambda f, k=k: report("Rendering", (k - 1 + f) / len(wins), f"Cutting part {k}/{len(wins)}"))
            made.append(p); cur = None; items.append(dict(file=p.name, a=s0, b=e0, label=name))
    except BaseException:
        if cur is not None:
            try: os.remove(cur)
            except OSError: pass
        raise
    if len(items) > 1:
        try: out.with_name(out.stem + "_series.txt").write_text(_series_text(items, split == "games"), encoding="utf-8")
        except OSError: pass
    report("Rendering", 1, "Done")
    print(f"Done: {len(made)} parts -> {out.parent}")


def cmd_longform(a):
    o = get_opts(getattr(a, "opts", None))
    info = check_video(a.video)
    rid = getattr(a, "recipe", None) or ("story" if getattr(a, "style", "") == "story" else "highlight")
    R = RECIPES.get(rid, RECIPES["highlight"])
    split = getattr(a, "split", "none") or "none"
    if split not in SPLITS: split = "none"
    whole = bool(getattr(a, "whole", False)) and split != "none"
    games = [dict(g) for g in (getattr(a, "games", None) or [])] if split == "games" else []
    tmin, tmax, target = length_range(a)
    out = unique_path(Path(a.out).resolve()); out.parent.mkdir(parents=True, exist_ok=True)
    words = [] if (whole and (split != "games" or games)) else load_words(a, o)
    if split == "games" and not games:
        cam = a.cam if getattr(a, "cam", None) and valid_cam(a.cam, info["w"], info["h"]) else None
        games = find_games(a.video, words, cam, getattr(a, "sens", "chapters"), getattr(a, "game_count", None), getattr(a, "game_min_minutes", None), info)
        print(f"Found {len(games)} part{'s' if len(games) != 1 else ''}:\n" + games_text(games))
    if whole: return _cut_parts(a, o, out, info, split, games)
    sc = features(a.video, words, R, o)
    gap = a.gap if (a.gap is None or not R["gap_floor"]) else max(a.gap, R["gap_floor"])     # gameplay keeps its quiet action
    # ---- what to make: a list of videos, each with the moments it is built from ----
    vids = []
    if split == "games":
        print(f"{R['title']}: one video for each of {len(games)} parts")
        for k, g in enumerate(games, 1):
            gd = g["end"] - g["start"]
            if gd < 90: print(f"Skipping “{g['name']}” - it is shorter than 90 seconds."); continue
            f = min(1.0, .5 * gd / tmax)                                  # a short game gets a shorter video (never more than half of what was played)
            lo_g, hi_g = max(40.0, tmin * f), max(60.0, tmax * f)
            pk = pick_recap(sc, words, (lo_g + hi_g) / 2, R, gap, lo_g, hi_g, (g["start"], g["end"]))
            if pk: vids.append(dict(label=g["name"], tag=f"game{k}_{_tag(g['name'])}", picked=pk, win=(g["start"], g["end"])))
            else: print(f"Nothing usable found in “{g['name']}” - skipped.")
    else:
        print(f"{R['title']}: aiming for {tmin / 60:g} to {tmax / 60:.1f} minutes")
        pk = pick_recap(sc, words, target, R, gap, tmin, tmax)
        if pk and split in ("count", "length"):
            tot = sum(kept_len(p[2]) for p in pk)
            n = int(getattr(a, "part_count", 0) or 0) if split == "count" else int(round(tot / (float(getattr(a, "part_minutes", 10) or 10) * 60)))
            groups = split_groups([kept_len(p[2]) for p in pk], max(1, n or 2))
            for k, gi in enumerate(groups, 1):
                vids.append(dict(label=f"Part {k} of {len(groups)}", tag=f"part{k}of{len(groups)}", picked=[pk[i] for i in gi], win=(pk[gi[0]][0], pk[gi[-1]][1])))
        elif pk: vids.append(dict(label="", tag="", picked=pk, win=(pk[0][0], pk[-1][1])))
    if not vids: raise RuntimeError("No usable moments found - the VOD may be too short for this style.")
    # long-form recaps use only captions, pans and jump-cut zooms
    fx = {k: 0 for k in FX["gameplay"]}
    fx.update(pan=int(bool(a.fx.get("pan"))), cutzoom=int(bool(a.fx.get("cutzoom"))),
              intensity=a.fx.get("intensity", 1.0), accent=a.fx.get("accent", "ff4d8d"))
    cens = load_censor(a.censor, o["swears"])
    eo = {**o, "emotes": bool(o["emotes"] and o["emote_recap"])}
    eplans = emote_plans(eo, words, [dict(k=(vi, k), label=f"{vd['label'] or 'Video'} · moment {k + 1}", start=p[0], segs=p[2], events=[])
                                     for vi, vd in enumerate(vids) for k, p in enumerate(vd["picked"])], getattr(a, "emote_review", None))
    tmp = tempfile.mkdtemp(prefix=".vclip_", dir=str(out.parent))        # next to the output, where there is room
    units = sum(len(v["picked"]) for v in vids) + .5 * len(vids); done = 0.0; nseg = 0; made, items, cur = [], [], None
    try:
        for vi, vd in enumerate(vids):
            parts, ch, off, allw = [], [], 0.0, []
            pre = f"Video {vi + 1}/{len(vids)}  ·  " if len(vids) > 1 else ""
            for k, (s0, e0, ss, _) in enumerate(vd["picked"]):
                check_cancel()
                part = os.path.join(tmp, f"v{vi}_p{k:03d}.mp4")
                cb = lambda f, k=k, pre=pre, vd=vd: report("Rendering", (done + f) / units, f"{pre}Rendering moment {k + 1}/{len(vd['picked'])}")
                ow, _ = render(a.video, ss, words, part, "wide", None, a.captions, cens, fx, [], None, cb, norm=False, cz_start=nseg % 2,
                               opts={**o, **RECAP_OFF, "music": "", "cta": "", "stickers": "", "intro": "", "outro": "", "filler": "", "emotes": eo["emotes"],
                                     **({"emote_plan": eplans.get((vi, k), [])} if eplans is not None else {})})
                allw += [{**w, "start": w["start"] + off, "end": w["end"] + off} for w in ow]
                parts.append(os.path.basename(part)); nseg += len(ss); done += 1
                ch.append(f"{hms(off)} " + (first_words(words, ss[0][0], 5, cens) or f"Moment {k + 1}"))
                off += kept_len(ss)
            lst = f"list{vi}.txt"
            Path(tmp, lst).write_text("".join(f"file '{n}'\n" for n in parts))
            report("Rendering", (done + .1) / units, f"{pre}Preparing the music") if o["music"] else None
            mus = music_bed(o["music"], off + 2.5, tmp)       # a playlist (folder / library) or one looped track, all at the same loudness
            cmd = ["-f", "concat", "-safe", "0", "-i", lst]
            if mus:                                        # one continuous music bed under the whole video, ducked under the voice
                mpath, mloop, mgain = mus
                cmd += (["-stream_loop", "-1"] if mloop else []) + ["-i", os.path.abspath(mpath), "-filter_complex",
                        f"[1:a]aresample=48000,volume={mgain:.1f}dB,volume={o['music_vol'] / 100:.3f},atrim=0:{off:.2f},afade=t=out:st={max(0, off - 2):.2f}:d=2[m];"
                        "[0:a]aresample=48000:async=1:min_hard_comp=0.003:first_pts=0,asplit=2[v][s];[m][s]sidechaincompress=threshold=0.03:ratio=8:attack=15:release=500[md];"
                        "[v][md]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5,aresample=48000[af]", "-map", "0:v", "-map", "[af]"]
            else: cmd += ["-af", "aresample=async=1:min_hard_comp=0.003:first_pts=0,loudnorm=I=-14:TP=-1.5,aresample=48000"]
            fo = out if not vd["tag"] else out.with_name(f"{out.stem}_{vd['tag']}{out.suffix}")
            fo = unique_path(fo) if vd["tag"] else fo
            cur = fo
            run_ff(cmd + ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(fo)], off,
                   lambda f, pre=pre: report("Rendering", (done + f * .5) / units, f"{pre}Finishing audio"), cwd=tmp)
            done += .5; made.append(fo); cur = None
            fo.with_suffix(".chapters.txt").write_text("\n".join(ch), encoding="utf-8")
            if o["srt"] and allw: write_srt(allw, fo.with_suffix(".srt"), cens)
            items.append(dict(file=fo.name, a=vd["win"][0], b=vd["win"][1], len=off, label=vd["label"] or fo.stem))
        if len(items) > 1:
            try: out.with_name(out.stem + "_series.txt").write_text(_series_text(items, split == "games"), encoding="utf-8")
            except OSError: pass
    except BaseException:
        if cur is not None:
            try: os.remove(cur)
            except OSError: pass
        raise
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    report("Rendering", 1, "Done")
    tot = sum(i["len"] for i in items)
    print(f"Done: {tot / 60:.1f} min ({sum(len(v['picked']) for v in vids)} moments" + (f", {len(made)} videos" if len(made) > 1 else "") + f") -> {made[0] if len(made) == 1 else out.parent}")


# ---------------- Post helper + X (Twitter) ----------------
X_MAX_S = 140                                               # a free X account can post up to 2:20 (512 MB, MP4 / H.264 / AAC)


def peak_info(src, dur):
    """(late_peak, hype): is the loudest moment in the second half of the clip, and how excited does it sound (0-100)."""
    try:
        rms, peak, r50 = audio_stats(src, dur)
        sm = np.convolve(rms, np.ones(3) / 3, "same") if len(rms) >= 3 else rms
        frac = int(np.argmax(sm)) / max(1, len(sm) - 1); z = (sm.max() - sm.mean()) / (sm.std() + 1e-6)
        return bool(frac > .55 and len(sm) >= 8), int(max(0, min(100, 25 + z * 18)))
    except Exception: return False, None


def cmd_postkit(a):
    """A finished short in -> title ideas, YouTube description and hashtags for YouTube Shorts / TikTok / Instagram Reels / X. Returns the kit (dict)."""
    import vcpost
    o = get_opts(getattr(a, "opts", None)); info = check_video(a.video)
    report("Transcribing", 0, "Listening to your short")
    words = load_words(a, o)
    late, hype = peak_info(a.video, info["dur"])
    report("Analyzing", 1, "Writing your post")
    extra = [t.strip("#") for t in re.split(r"[\s,]+", o["tags"]) if t.strip("#")]
    kit = vcpost.make_kit(words, game=o["game"], channel=o["channel"], handle=o["handle"], links=getattr(a, "links", "") or "", hint=o["hint"],
                          name_hint=Path(a.video).stem, seed=int(getattr(a, "seed", 0) or 0), late_peak=late, reach=bool(getattr(a, "reach", False)), extra=extra)
    kit.update(hype=hype, words=words, late_peak=late, heard=" ".join(w["w"] for w in words)[:600])
    try:
        p = Path(a.out) / "PostKits" / f"{safe_stem(a.video)}_post.txt"; p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(vcpost.kit_text(kit, hype), encoding="utf-8"); kit["saved"] = str(p); print("Saved:", p)
    except OSError: pass
    report("Analyzing", 1, "Done")
    return kit


def x_shape(info, shape):
    """Aspect ratio for X. 'auto' keeps the picture's own shape: wide stays 16:9, tall / square become 4:5 (fills the feed best)."""
    if shape in ASPECTS: return shape
    w, h = info["w"] or 16, info["h"] or 9
    return "16:9" if w / h >= 1.2 else "4:5" if h / w >= 1.15 else "1:1"


def cmd_twitter(a):
    """One video in -> a video that is ready for X (Twitter) + post text. Burned-in captions (X autoplays muted), loudness evened out, H.264 / AAC,
    shape that fills the feed, at most 2:20 (the best part is picked when it is longer). Returns dict(out, kit, ...)."""
    import vcpost
    o = get_opts(getattr(a, "opts", None)); info = check_video(a.video)
    dur, max_len = info["dur"], float(getattr(a, "max_len", None) or X_MAX_S)
    aspect = x_shape(info, getattr(a, "shape", "auto"))
    words = load_words(a, o)
    gap = None
    if dur > max_len + 1:                                    # too long for X: pick the best stretch
        sc = features(a.video, words, PROFILES["mix"], o)
        lo, hi = min(25, max_len), min(60, max_len)
        mid = int((lo + hi) / 2); best = None
        for _, i in top_windows(sc, mid, max(1, mid // 2), PROFILES["mix"]):
            best = fit_clip(sc, words, i, lo, hi, gap, False)
            if best: break
        if not best: best = (0.0, max_len, [(0.0, max_len)])
        segs = [(max(0.0, x), min(dur, y)) for x, y in best[2]]
        print(f"The video is {hms(dur)} long - X allows {int(max_len // 60)}:{int(max_len % 60):02d}, so I picked the best part ({hms(best[0])} on).")
    else:
        t0, t1 = 0.0, dur                                    # only cut off long silent stretches at the very start / end
        if words:
            if words[0]["start"] > 2.5: t0 = max(0.0, words[0]["start"] - .5)
            if dur - words[-1]["end"] > 2.5: t1 = min(dur, words[-1]["end"] + .8)
        segs = [(t0, max(t0 + 1.0, t1))]
    tgt = min(dur, max_len)
    fps = 60 if info.get("fps", 30) >= 50 else 30
    old = dict(OUT)
    OUT.update(res=1080, fps=fps, mbps=min(old["mbps"], 14))
    try:
        outdir = Path(a.out) / "Twitter"; outdir.mkdir(parents=True, exist_ok=True)
        out = unique_path(outdir / f"{safe_stem(a.video)}_x.mp4")
        src_asp = (info["w"] or 16) / max(1, info["h"] or 9); tw, th = ASPECTS[aspect]
        layout = "fill" if abs(src_asp - tw / th) < .03 else "blur"
        keep = {k: o[k] for k in ("cap_style", "cap_font", "cap_size", "cap_pos", "cap_text", "cap_hi", "cap_edge", "cap_emph", "cap_emoji", "logo", "logo_pos", "logo_size",
                                  "handle", "handle_pos", "lang", "translate", "hint", "fixes", "fix_lag", "voice_clean", "bg_style", "bg_color", "bg_image")}
        keep.update({k: o[k] for k in POLISH_KEYS})                                       # 2.0: colour look, name tag, voice effect... also for the X video
        o2 = {**keep, "aspect": aspect, "platform": "any", "sfx_pack": o["sfx_pack"]}
        fx = {k: 0 for k in FX["gameplay"]}; fx.update(intensity=1.0, accent=str(getattr(a, "accent", "") or "ff4d8d"))
        report("Rendering", 0, "Making your X video")
        ow, d = render(a.video, segs, words, out, layout, None, bool(getattr(a, "captions", True)), load_censor(getattr(a, "censor", None), o["swears"]), fx, [], None,
                       lambda f: report("Rendering", f, "Making your X video"), norm=True, opts=o2)
    finally:
        OUT.clear(); OUT.update(old)
    size = out.stat().st_size / 2 ** 20
    late, hype = peak_info(str(out), d)
    extra = [t.strip("#") for t in re.split(r"[\s,]+", o["tags"]) if t.strip("#")]
    kit = vcpost.make_kit(ow or words, game=o["game"], channel=o["channel"], handle=o["handle"], hint=o["hint"], name_hint=Path(a.video).stem,
                          seed=int(getattr(a, "seed", 0) or 0), late_peak=late, extra=extra)
    res = dict(out=str(out), kit=kit, dur=d, size_mb=size, aspect=aspect, words=ow or words, late_peak=late)
    try:
        lines = [f"X (TWITTER) POST IDEAS for {out.name}", f"{d:.0f}s · {size:.0f} MB · {aspect}", ""]
        for p_ in kit["twitter"]["posts"]: lines.append(f"[{p_['label']}] {p_['text']}")
        lines += ["", "3 HASHTAGS (optional - X itself suggests 1-2):", " ".join(kit["twitter"]["hashtags"])]
        out.with_suffix(".txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError: pass
    report("Rendering", 1, "Done")
    print(f"Done: {d:.0f}s, {size:.0f} MB -> {out}")
    return res


# ---------------- best-moment finder ----------------
def describe(sc, words, s, e):
    """Why is this moment good? Plain-language tags + a quote from the strongest part."""
    a, b = int(s), max(int(s) + 1, int(e))
    seg = lambda k: np.asarray(AN[k][a:b]) if k in AN and len(AN[k][a:b]) else np.zeros(1)
    ws = [w for w in words if s <= w["start"] < e]
    peak = a + int(np.argmax(sc[a:b]))
    tags, loud = [], float(seg("rmsz").max())
    if loud > 2.0 or seg("ons").sum() >= 3: tags.append("Loud / screaming")
    hy = list(dict.fromkeys(clean(w["w"]) for w in ws if clean(w["w"]) in HYPE))
    if hy: tags.append("Hype words: " + ", ".join(hy[:3]))
    if sum(1 for w in ws if "haha" in w["w"].lower() or clean(w["w"]) in ("lol", "lmao", "lmfao", "hehe")) >= 1: tags.append("Laughing")
    if seg("excl").sum() >= 3: tags.append("Big reactions")
    cov = float(np.asarray(AN["cover"][a:b]).mean()) if "cover" in AN and len(AN["cover"][a:b]) else 0.0
    if cov > .75 and loud <= 2.0: tags.append("Talking / story")
    if cov < .35 and loud > 1.2: tags.append("Action")
    kind, why = None, []
    if AN.get("marks") is not None:                       # 2.2: what kind of moment is it, and why was it picked
        try:
            import vcsmart
            cur = AN.get("curves")
            if cur and float(np.max(np.asarray(cur["laugh"][a:b]))) > .6 and "Laughing" not in tags: tags.append("Laughing")
            if cur and float(np.mean(np.asarray(cur["sing"][a:b]))) > .4: tags.append("Singing")
            m_ = smart_meta(words, sc, s, e)
            kind, why = m_.get("kind"), m_.get("why", [])
            if kind: tags = [vcsmart.type_label(kind)] + tags
        except Exception: pass
    return dict(peak=float(peak), text=first_words(words, max(s, peak - 3), 12), tags=tags or ["Steady energy"], kind=kind, why=why)


CLIP_PHRASES = (("clip", "that"), ("clip", "it"), ("clip", "this"), ("クリップ",), ("클립",))      # "clip that!" said on stream marks a moment


def find_phrase(words, query):
    """Times where the words in `query` are said in a row (cleaned of punctuation / case)."""
    q = [clean(x) for x in (query or "").split() if clean(x)]
    if not q: return []
    ks = [clean(w["w"]) for w in words]
    return [words[i]["start"] for i in range(len(words) - len(q) + 1) if ks[i:i + len(q)] == q]


def find_markers(words):
    """Moments the streamer marked by saying 'clip that' (the exciting part just happened, so the clip is the lead-up)."""
    ks, out = [clean(w["w"]) for w in words], []
    for i in range(len(words)):
        if any(tuple(ks[i:i + len(ph)]) == ph for ph in CLIP_PHRASES):
            if not out or words[i]["start"] - out[-1] > 20: out.append(words[i]["start"])
    return out


def _moment(sc, words, s0, e0, dur, tag, score=None):
    s0 = max(0.0, float(s0)); e0 = min(float(dur), max(s0 + 3, float(e0)))
    d = describe(sc, words, s0, e0)
    sco = rating(wscore(sc, int(s0), max(3, int(e0 - s0)), MOMENTS["dead"])) if score is None else score
    return dict(start=s0, end=e0, score=sco, peak=d["peak"], text=d["text"], tags=[tag] + [t for t in d["tags"] if t != "Steady energy"], kind=d.get("kind"), why=d.get("why", []))


def find_moments(video, n=15, lo=20, hi=60, model="small", device="auto", opts=None, query=""):
    """Scan the whole VOD and return the best moments as [{start, end, score 0-100, peak, text, tags}], best first.
    Also lists every place the streamer said 'clip that'. With `query` it lists where those words are said instead (comma separated)."""
    o = get_opts(opts)
    check_video(video)
    words = transcribe(video, model, device, o["lang"], o["translate"], o["hint"], o["fixes"])
    sc = features(video, words, MOMENTS, o)
    lo, hi = (min(lo, hi), max(lo, hi)); mid = int((lo + hi) / 2); dur = float(len(sc))
    ra, rb = look_range(o, len(sc))
    cands = top_windows(sc, mid, max(1, mid // 3), MOMENTS, ra, rb)          # also sets the 0-100 rating baseline
    found = []
    for t in find_markers(words):                                    # 'clip that' = a lead-up of ~mid seconds ending just after the phrase
        e0 = min(dur, t + 2.5); found.append(_moment(sc, words, snap_start(words, max(0, e0 - mid)), e0, dur, "You said “clip that”", 100))
    if (query or "").strip():
        qs = [x.strip() for x in re.split(r"[,\n;]+", query) if x.strip()]
        for q in qs:
            for t in find_phrase(words, q):
                s0 = snap_start(words, max(0, t - .35 * mid)); m = _moment(sc, words, s0, s0 + mid, dur, f"Said “{q}”")
                if all(m["end"] <= x["start"] or m["start"] >= x["end"] for x in found): found.append(m)
    else:
        auto = []
        for score, i in cands:
            if len(auto) >= n: break
            r = fit_clip(sc, words, i, lo, hi, None, limit=rb)
            if not r: continue
            s0, e0, _ = r
            if all(e0 <= m["start"] or s0 >= m["end"] for m in found + auto):
                auto.append(dict(start=float(s0), end=float(e0), score=rating(score), **describe(sc, words, s0, e0)))
        found += auto
    found.sort(key=lambda m: -m["score"])
    report("Analyzing", 1, f"Found {len(found)} moments")
    print(f"Found {len(found)} moments.")
    return found


def moments_text(ms, by_time=False):
    """The list as plain text (for copying / saving): start - end, length, rating, quote and why."""
    rows = sorted(ms, key=lambda m: m["start"]) if by_time else ms
    out = []
    for k, m in enumerate(rows, 1):
        out.append(f"{hms(m['start'])} - {hms(m['end'])}  ({m['end'] - m['start']:.0f}s)  rating {m['score']}/100  " +
                   (f"\"{m['text']}\"  " if m["text"] else "") + "[" + ", ".join(m["tags"]) + "]")
    return "\n".join(out)


# ---------------- pasted timestamps ----------------
_TSRE = re.compile(r"(?<!\d)(?<!\d:)(?<!\d\.)(\d{1,2}:\d{2}:\d{2}(?:\.\d+)?|\d{1,3}:\d{2}(?:\.\d+)?|\d+h\d+m\d+s|\d+h\d+m|\d+m\d+s|\d+h|\d+m|\d+s)(?!\d)(?!:\d)(?!\.\d)", re.I)


def _to_sec(tok):
    tok = tok.lower()
    if ":" in tok:
        p = [float(x) for x in tok.split(":")]
        return p[0] * 3600 + p[1] * 60 + p[2] if len(p) == 3 else p[0] * 60 + p[1]
    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", tok)
    return int(m[1] or 0) * 3600 + int(m[2] or 0) * 60 + int(m[3] or 0)


def parse_times(text, dur, default_len=40.0, lead=8.0):
    """A pasted list of times -> [(start, end, label)]. Understands '1:23:45', '12:30', '1h2m3s', ranges ('12:30 - 13:10', '12:30 to 13:10'),
    labels after the time and YouTube-chapter style lines. A single time becomes a clip that starts a few seconds BEFORE it."""
    out = []
    for line in str(text or "").splitlines():
        line = re.sub(r"(\d)\s+([hms])\b", r"\1\2", line.strip(), flags=re.I)
        toks = list(_TSRE.finditer(line))
        if not toks: continue
        t0 = _to_sec(toks[0].group(1))
        t1 = _to_sec(toks[1].group(1)) if len(toks) > 1 else None
        if t1 is not None and t1 > t0 + 2: a, b = t0, t1
        else: a = max(0.0, t0 - lead); b = a + default_len
        if dur and a >= dur - 3: continue
        if dur: b = min(b, float(dur))
        if b - a < 3: continue
        lab = line[:toks[0].start()] + " " + line[(toks[1].end() if t1 is not None and t1 > t0 + 2 else toks[0].end()):]
        lab = re.sub(r"^[\s\-–—→>:|\[\]\(\)•*.,]+|[\s\-–—→>:|\[\]\(\)•*.,]+$", "", re.sub(r"\s+", " ", lab)).strip()
        out.append((float(a), float(b), lab[:60]))
    return out


def custom_moment(words, s0, e0, label="My moment"):
    """A moment the user picked by hand (no analysis needed) in the same shape the Best-moments list uses."""
    s0 = max(0.0, float(s0)); e0 = max(s0 + 3, float(e0))
    return dict(start=s0, end=e0, score=100, peak=s0, text=first_words(words, s0, 12) if words else "", tags=[label or "My moment"])


# ---------------- automatic cam finder ----------------
def _edge_maps(F, thr=14.0, keep=.6):
    """Cumulative sums of 'edges that stay put' (present in most sampled frames): HUD borders and cam frames stay, gameplay moves."""
    gx, gy = np.abs(np.diff(F, axis=2)), np.abs(np.diff(F, axis=1))
    PV, PH = (gx > thr).mean(0) >= keep, (gy > thr).mean(0) >= keep           # PV (GH, GW-1): vertical edges, PH (GH-1, GW): horizontal edges
    PVd, PHd = PV.copy(), PH.copy()                                              # tolerate a pixel of jitter
    PVd[:, 1:] |= PV[:, :-1]; PVd[:, :-1] |= PV[:, 1:]; PHd[1:] |= PH[:-1]; PHd[:-1] |= PH[1:]
    GH, GW = F.shape[1], F.shape[2]
    CV = np.zeros((GH + 1, GW - 1), np.float32); CV[1:] = np.cumsum(PVd, axis=0)
    CH = np.zeros((GH - 1, GW + 1), np.float32); CH[:, 1:] = np.cumsum(PHd, axis=1)
    return CV, CH


def _rect_score(maps, GW, GH, x0, y0, x1, y1):
    """Border score of rectangles (arrays, x1 / y1 exclusive): the weakest of the four sides; a side on the screen edge counts as present."""
    CV, CH = maps
    def hor(y, xa, xb, free):
        yy = np.clip(y - 1, 0, GH - 2); return np.where(free, 1.0, (CH[yy, xb] - CH[yy, xa]) / np.maximum(1, xb - xa))
    def ver(x, ya, yb, free):
        xx = np.clip(x - 1, 0, GW - 2); return np.where(free, 1.0, (CV[yb, xx] - CV[ya, xx]) / np.maximum(1, yb - ya))
    fl, ft, fr, fb = x0 <= 1, y0 <= 1, x1 >= GW - 1, y1 >= GH - 1
    sc = np.minimum.reduce([hor(y0, x0, x1, ft), hor(y1, x0, x1, fb), ver(x0, y0, y1, fl), ver(x1, y0, y1, fr)])
    touching = fl.astype(int) + ft + fr + fb
    return sc + .08 * (touching >= 2) - .25 * (touching == 0) * (sc < .85), touching


def find_cam(video, n=12, detail=False):
    """Best guess for where the streamer's facecam / model window sits on the screen, as 'w:h:x:y' (source pixels), or None when the
    picture has no cam-like box. Samples frames across the whole VOD and looks for a rectangle whose border stays put while the game moves."""
    info = probe_info(video); dur, sw, sh = info["dur"], info["w"], info["h"]
    if not sw or dur < 4: return (None, 0.0) if detail else None
    GW2 = max(96, min(960, sw) // 3 * 3); GH2 = max(54, int(round(GW2 * sh / sw)) // 3 * 3)
    times = [dur * (.05 + .9 * k / max(1, n - 1)) for k in range(n)]

    def grab(t):
        r = subprocess.run([FF, "-v", "quiet", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1", "-an", "-vf", f"scale={GW2}:{GH2}:flags=area,format=gray",
                            "-f", "rawvideo", "-"], capture_output=True, **NOWIN)
        return np.frombuffer(r.stdout, np.uint8)[:GW2 * GH2] if len(r.stdout) >= GW2 * GH2 else None
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as ex: got = [g for g in ex.map(grab, times) if g is not None]
    check_cancel()
    if len(got) < 5: return (None, 0.0) if detail else None
    F2 = np.stack([g.reshape(GH2, GW2) for g in got]).astype(np.float32)
    F1 = F2.reshape(len(got), GH2 // 3, 3, GW2 // 3, 3).mean((2, 4)); GW1, GH1 = GW2 // 3, GH2 // 3
    m1 = _edge_maps(F1, 12.0)
    best = (-9.0, None)
    for ar in (16 / 9, 4 / 3, 3 / 2, 5 / 4, 1.0, 4 / 5, 3 / 4, 9 / 16):
        for w in range(max(8, int(GW1 * .14)), int(GW1 * .46), 2):
            h = int(round(w / ar))
            if h < 8 or h > GH1 * .62 or w >= GW1 - 1 or h >= GH1 - 1: continue
            xs, ys = np.meshgrid(np.arange(0, GW1 - w + 1), np.arange(0, GH1 - h + 1))
            sc, _ = _rect_score(m1, GW1, GH1, xs, ys, xs + w, ys + h); sc = sc + .0004 * w
            i = int(np.argmax(sc))
            if sc.flat[i] > best[0]: best = (float(sc.flat[i]), (int(xs.flat[i]), int(ys.flat[i]), int(xs.flat[i]) + w, int(ys.flat[i]) + h))
    if best[1] is None or best[0] < .8: return (None, max(0.0, best[0])) if detail else None
    m2 = _edge_maps(F2, 14.0); x0, y0, x1, y1 = (v * 3 for v in best[1]); r = np.arange(-6, 7)
    A, B, C, D = np.meshgrid(r, r, r, r, indexing="ij")
    X0, Y0, X1, Y1 = np.clip(x0 + A, 0, GW2 - 1), np.clip(y0 + B, 0, GH2 - 1), np.clip(x1 + C, 2, GW2), np.clip(y1 + D, 2, GH2)
    good = (X1 - X0 >= 16) & (Y1 - Y0 >= 16)
    sc2, _ = _rect_score(m2, GW2, GH2, X0, Y0, X1, Y1)
    sc2 = np.where(good, sc2 - .002 * (np.abs(A) + np.abs(B) + np.abs(C) + np.abs(D)), -9)         # prefer the smallest move from the coarse box
    i = int(np.argmax(sc2)); bx0, by0, bx1, by1 = int(X0.flat[i]), int(Y0.flat[i]), int(X1.flat[i]), int(Y1.flat[i])
    kx, ky = sw / GW2, sh / GH2
    w_, h_ = max(2, int(round((bx1 - bx0) * kx)) // 2 * 2), max(2, int(round((by1 - by0) * ky)) // 2 * 2)
    x_, y_ = max(0, min(int(round(bx0 * kx)) // 2 * 2, sw - w_)), max(0, min(int(round(by0 * ky)) // 2 * 2, sh - h_))
    cam = f"{w_}:{h_}:{x_}:{y_}"
    if not valid_cam(cam, sw, sh): return (None, 0.0) if detail else None
    return (cam, float(sc2.flat[i])) if detail else cam


# ---------------- cam-area picker helpers (used by the app's visual selector) ----------------
def drag_rect(ax, ay, ex, ey, W, H, ratio=None):
    """Rectangle from anchor (ax,ay) to the mouse (ex,ey), clamped to W x H, optionally locked to an aspect ratio."""
    ex, ey = min(max(ex, 0), W), min(max(ey, 0), H)
    if ratio:
        sx, sy = (1 if ex >= ax else -1), (1 if ey >= ay else -1)
        w = abs(ex - ax); h = w / ratio
        h = min(h, (H - ay) if sy > 0 else ay); w = h * ratio
        w = min(w, (W - ax) if sx > 0 else ax); h = w / ratio
        ex, ey = ax + sx * w, ay + sy * h
    return min(ax, ex), min(ay, ey), max(ax, ex), max(ay, ey)


def cam_string(r, scale, sw, sh):
    """Display-space rectangle -> ffmpeg crop string w:h:x:y in source pixels."""
    x1, y1, x2, y2 = r
    w, h = max(2, int((x2 - x1) * scale) // 2 * 2), max(2, int((y2 - y1) * scale) // 2 * 2)
    return f"{w}:{h}:{max(0, min(int(x1 * scale), sw - w))}:{max(0, min(int(y1 * scale), sh - h))}"


# ---------------- optional GPU speech pack (downloaded on the user's PC from PyPI) ----------------
CUDA_PKGS = [("nvidia-cublas-cu12", "12.9.2.10"), ("nvidia-cudnn-cu12", "9.27.0.42"),
             ("nvidia-cuda-runtime-cu12", "12.9.79"), ("nvidia-cuda-nvrtc-cu12", "12.9.86")]


def install_cuda(dest=None, pkgs=None):
    import urllib.request, zipfile
    d = dest or os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cuda"))
    os.makedirs(d, exist_ok=True); pkgs = pkgs or CUDA_PKGS
    if shutil.disk_usage(d).free < 2.5 * 2 ** 30 or shutil.disk_usage(tempfile.gettempdir()).free < 1.0 * 2 ** 30:
        raise RuntimeError("Not enough free disk space for the GPU pack (needs about 3 GB free).")
    marker = os.path.join(d, "installed.ok")
    if os.path.exists(marker): os.remove(marker)
    for i, (name, ver) in enumerate(pkgs):
        check_cancel()
        meta = json.load(urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{ver}/json", timeout=30))
        url = next(u["url"] for u in meta["urls"] if u["filename"].endswith("win_amd64.whl"))
        whl = os.path.join(tempfile.gettempdir(), os.path.basename(url))
        try:
            with urllib.request.urlopen(url, timeout=60) as r, open(whl, "wb") as f:
                total, got = int(r.headers.get("Content-Length", 0)) or 1, 0
                while True:
                    check_cancel()
                    b = r.read(1 << 20)
                    if not b: break
                    f.write(b); got += len(b)
                    report("GPU pack", (i + got / total) / len(pkgs) * .97, f"Downloading {name}  {got >> 20} / {total >> 20} MB")
            with zipfile.ZipFile(whl) as z:
                for m in z.namelist():
                    if m.startswith("nvidia/") and "/bin/" in m and m.endswith(".dll") and "alt" not in m and "nvblas" not in m:
                        with z.open(m) as s, open(os.path.join(d, os.path.basename(m)), "wb") as o: shutil.copyfileobj(s, o)
        finally:
            try: os.remove(whl)
            except OSError: pass
    open(marker, "w").write("ok")
    report("GPU pack", 1, "GPU pack installed")
    print("GPU speech pack installed.")
