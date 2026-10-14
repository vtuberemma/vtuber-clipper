"""Style presets: one click sets the moment finder, layout, effects, captions and sounds to a look that VTuber editors use.
Pure data + tiny helpers (no UI here). The app shows them as cards with an animated preview."""
import json, os, re, time
import streamclip as sc

ALL_FX = list(sc.FX["gameplay"])


SHORT = dict(kawaii="Hearts, sparkles, cute pops", clutch="Speed lines, shake, boom", story="Calm pans, phrase captions", mix="Hook + lit-word captions",
             meme="Bouncy captions, glitch", sub="Auto English subtitles", chill="Petals, glow, soft captions", retro="VHS, 8-bit, pixel text",
             karaoke="Sing-along captions", horror="Shake, B&W, red text", bubble="Round cam over gameplay", party="Confetti + hearts", clean="Captions only")


def _p(pid, name, emoji, blurb, style, lmin, lmax, gap, layout, fx, intensity="Normal", accent=None, aspect="9:16", **opts):
    return dict(id=pid, name=name, emoji=emoji, blurb=blurb, short=SHORT.get(pid, ""), builtin=True,
                look=dict(style=style, lmin=lmin, lmax=lmax, gap=gap, layout=layout, aspect=aspect, fx={k: int(k in fx.split()) for k in ALL_FX},
                          intensity=intensity, accent=accent, opts=opts))


PRESETS = [
    _p("kawaii", "Kawaii Hype", "🎀", "The classic VTuber short: cam on top, pop-in captions, hearts, sparkles and cute pops on every reaction.",
       "mix", 25, 45, 1.4, "stack", "zoom pop hook bar hearts sparkle glow sfx whoosh cutzoom zoomout flash", "Normal", "ff6fae",
       cap_style="pop", cap_font="Chewy", cap_text="ffffff", cap_hi="ff5fa8", cap_edge="5a1f3c", cap_emoji=True, sfx_pack="cute"),
    _p("clutch", "Gameplay Clutch", "🎮", "Fast and loud: speed lines, shockwaves, screen shake and a boom on every big play. Highlight word in yellow.",
       "gameplay", 20, 35, 2.0, "stack", "zoom shake flash sfx blur pop bar hook cutzoom glitch whoosh zoomout lines ring tilt", "Hype", "ff5a36",
       cap_style="karaoke", cap_font="Poppins", cap_text="ffffff", cap_hi="ffe14d", cap_edge="000000", sfx_pack="boom"),
    _p("story", "Story Time", "📖", "Talking and storytelling: the model fills the frame, calm pans and push-ins, readable phrase captions.",
       "story", 45, 75, 1.2, "fill", "pan pushin glow pop bar hook cutzoom sparkle zoomout", "Subtle", "c7a6ff",
       cap_style="karaoke", cap_font="Poppins", cap_text="ffffff", cap_hi="ff9ed2", cap_edge="2a1c45", sfx_pack="cute"),
    _p("mix", "Pro Mix (Opus-style)", "🎭", "What most editors make: a hook, bold phrase captions with the spoken word lit, tight punch-ins. Works for story + gameplay.",
       "mix", 30, 55, 1.3, "stack", "zoom pop hook bar cutzoom whoosh zoomout sfx pan", "Normal", "ff7ab8",
       cap_style="karaoke", cap_font="Poppins", cap_text="ffffff", cap_hi="ffe14d", cap_edge="000000", cap_emoji=True, sfx_pack="cute"),
    _p("meme", "Meme Clip", "😂", "Short and chaotic: bouncing comic captions, glitch + B&W flashes, reaction marks and an anime impact sound.",
       "mix", 12, 25, 1.2, "fill", "zoom shake flash sfx glitch bw lines marks pop hook zoomout cutzoom whoosh", "Hype", "ffd23f",
       cap_style="bounce", cap_font="Bangers", cap_text="ffffff", cap_hi="ffe14d", cap_edge="000000", cap_emoji=True, sfx_pack="anime"),
    _p("sub", "Subtitled (Translate)", "🌍", "Speaks Japanese or another language? Gets English subtitles automatically in clean, calm lines.",
       "story", 30, 60, 1.3, "stack", "pan pushin pop bar hook zoom", "Subtle", "7ec8ff",
       cap_style="line", cap_font="Poppins", cap_text="ffffff", cap_hi="7ec8ff", cap_edge="000000", sfx_pack="cute", translate=True),
    _p("chill", "Chill & Cozy", "☁️", "Soft and relaxed: drifting sakura petals, dreamy glow, slow push-in and gentle subtitle-style captions.",
       "story", 40, 70, 1.6, "fill", "pan pushin glow sparkle petals pop bar", "Subtle", "b8a1ff",
       cap_style="line", cap_font="Sniglet", cap_text="ffffff", cap_hi="b8a1ff", cap_edge="3b2a66", sfx_pack="cute"),
    _p("retro", "Retro Anime", "📼", "90s anime vibes: VHS grain, glitch cuts, photo frame, speed lines and 8-bit sounds with pixel captions.",
       "mix", 20, 40, 1.5, "stack", "zoom flash sfx vhs frame glitch lines pop bar hook whoosh bw zoomout", "Normal", "ff77e9",
       cap_style="box", cap_font="Pixel (retro)", cap_text="ffe14d", cap_hi="6a2ea0", cap_edge="000000", sfx_pack="retro"),
    _p("karaoke", "Karaoke Night", "🎤", "Singing streams: big sing-along captions with the current word lit, sparkles, glow and slow camera drift.",
       "mix", 30, 60, 1.6, "fill", "pan pushin glow sparkle hearts pop bar hook", "Normal", "ff4d8d",
       cap_style="karaoke", cap_font="Titan One", cap_text="ffffff", cap_hi="ff4d8d", cap_edge="3a1230", sfx_pack="cute"),
    _p("horror", "Horror / Scream", "👻", "Jump-scare energy: shaking camera, B&W flashes, glitching VHS, red sticker captions and a heavy boom.",
       "gameplay", 20, 40, 2.0, "stack", "zoom shake flash sfx bw glitch vhs tilt blur pop bar hook whoosh zoomout", "Hype", "d11a3a",
       cap_style="pop", cap_font="Creepy", cap_text="ffffff", cap_hi="e0183c", cap_edge="000000", sfx_pack="boom"),
    _p("bubble", "Cam Bubble", "🫧", "Gameplay fills the screen and the model floats in a round bubble. Ring pulses, reaction marks and cute pops.",
       "gameplay", 25, 45, 1.8, "pip", "zoom shake flash sfx pop bar hook ring marks sparkle cutzoom whoosh zoomout", "Normal", "6be0ff",
       cap_style="pop", cap_font="Titan One", cap_text="ffffff", cap_hi="6be0ff", cap_edge="123a5a", sfx_pack="cute"),
    _p("party", "Win Party", "🎉", "Celebrate the win: confetti, hearts, reaction marks and bouncy captions with a sparkly pop sound.",
       "mix", 15, 30, 1.4, "stack", "zoom flash sfx confetti hearts ring marks pop bar hook cutzoom whoosh zoomout", "Hype", "ffb347",
       cap_style="bounce", cap_font="Luckiest Guy", cap_text="ffffff", cap_hi="ff4d8d", cap_edge="2b1840", cap_emoji=True, sfx_pack="cute"),
    _p("clean", "Minimal Clean", "⚪", "Just the content: simple white captions, a gentle punch-in on big moments and nothing else.",
       "mix", 25, 50, 1.4, "stack", "zoom pop", "Subtle", "ffffff",
       cap_style="pop", cap_font="Poppins", cap_text="ffffff", cap_hi="ffffff", cap_edge="000000", sfx_pack="cute"),
]
BY_ID = {p["id"]: p for p in PRESETS}
USER_FILE = os.path.join(os.path.expanduser("~"), ".vtuberclipper_presets.json")


def full_look(look):
    """A look with every field present (so applying it never leaves a half-set UI)."""
    L = dict(style="mix", lmin=25, lmax=45, gap=1.5, layout="stack", aspect="9:16", intensity="Normal", accent=None)
    L.update({k: v for k, v in (look or {}).items() if k in L})
    L["fx"] = {k: int(bool((look or {}).get("fx", {}).get(k, 0))) for k in ALL_FX}
    L["opts"] = {k: v for k, v in ((look or {}).get("opts") or {}).items() if k in sc.OPTS}
    return L


STYLE_FORMAT = "vtuberclipper-style"
LOOK_KEYS = ("cap_style", "cap_font", "cap_size", "cap_pos", "cap_text", "cap_hi", "cap_edge", "cap_emph", "cap_emoji", "sfx_pack", "translate", "bg_style", "bg_color",
             "cap_case", "cap_outline", "cap_shadow", "cap_words", "cap_box", "cap_rainbow")


def safe_look(look):
    """A look from a file somebody sent: every value checked, nothing outside the known settings (no file paths, no surprises)."""
    L = full_look(look)
    def num(v, d, lo, hi, cast):
        try: x = cast(float(v))
        except (TypeError, ValueError): x = d
        return min(hi, max(lo, x))
    L["lmin"], L["lmax"] = num(L["lmin"], 25, 5, 180, int), num(L["lmax"], 45, 5, 180, int)
    if L["lmin"] > L["lmax"]: L["lmin"], L["lmax"] = L["lmax"], L["lmin"]
    L["gap"] = num(L["gap"], 1.5, .3, 6, float)
    L["style"] = L["style"] if L["style"] in sc.PROFILES else "mix"
    L["layout"] = L["layout"] if L["layout"] in sc.LAYOUTS else "stack"
    L["aspect"] = L["aspect"] if L["aspect"] in sc.ASPECTS else "9:16"
    L["intensity"] = L["intensity"] if L["intensity"] in ("Subtle", "Normal", "Hype") else "Normal"
    acc = str(L["accent"] or "").lstrip("#").lower(); L["accent"] = acc if re.fullmatch(r"[0-9a-f]{6}", acc) else None
    given = (look or {}).get("opts") or {}
    o = sc.get_opts({k: v for k, v in given.items() if k in LOOK_KEYS} if isinstance(given, dict) else {})
    L["opts"] = {k: o[k] for k in LOOK_KEYS if isinstance(given, dict) and k in given}
    return L


def export_style(preset, path):
    """Write a style (name, emoji, look) to a small file that can be sent to another creator."""
    data = dict(format=STYLE_FORMAT, version=1, name=preset["name"], emoji=preset.get("emoji") or "⭐", blurb=preset.get("blurb") or "", look=safe_look(preset["look"]))
    with open(path, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=1)


def import_style(path, existing):
    """A style file -> a new user preset (raises ValueError with a friendly message when the file isn't one)."""
    try:
        with open(path, "r", encoding="utf-8") as f: data = json.load(f)
    except (OSError, ValueError): raise ValueError("I couldn't read that file. Is it a VTuber Clipper style file?")
    if not isinstance(data, dict) or data.get("format") != STYLE_FORMAT or not isinstance(data.get("look"), dict):
        raise ValueError("That file isn't a VTuber Clipper style.")
    pr = new_user_preset(str(data.get("name") or "Imported style"), safe_look(data["look"]), existing)
    pr["emoji"] = str(data.get("emoji") or "⭐")[:4]; pr["blurb"] = (str(data.get("blurb") or "").strip() or "A style someone shared with you.")[:160]
    return pr


def load_user(path=None):
    try:
        path = path or USER_FILE

        data = json.load(open(path, encoding="utf-8"))
        out = []
        for p in data.get("presets", []) if isinstance(data, dict) else []:
            if isinstance(p, dict) and isinstance(p.get("name"), str) and isinstance(p.get("look"), dict):
                out.append(dict(id=str(p.get("id") or "u" + str(int(time.time() * 1000))), name=p["name"][:40], emoji=p.get("emoji") or "⭐",
                                blurb=str(p.get("blurb") or "Your saved settings."), builtin=False, look=full_look(p["look"])))
        return out
    except Exception: return []


def save_user(presets, path=None):
    path = path or USER_FILE
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(dict(presets=[dict(id=p["id"], name=p["name"], emoji=p["emoji"], blurb=p["blurb"], look=p["look"]) for p in presets if not p.get("builtin")]), f)
        os.replace(tmp, path)
        return True
    except OSError: return False


def new_user_preset(name, look, existing):
    pid = "u" + re.sub(r"\W", "", name.lower())[:12] + str(int(time.time()) % 100000)
    while any(p["id"] == pid for p in existing) or pid in BY_ID: pid += "x"
    return dict(id=pid, name=name.strip()[:40] or "My style", emoji="⭐", blurb="Your saved settings.", builtin=False, look=full_look(look))
