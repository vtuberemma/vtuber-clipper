#!/usr/bin/env python3
"""VTuber Clipper - kawaii desktop app for turning stream VODs into shorts and long-form recaps."""
import argparse, contextlib, glob, hashlib, json, math, os, queue, random, re, shutil, subprocess, sys, tempfile, threading, time, traceback, webbrowser
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox, colorchooser, simpledialog

sc = None          # the engine; imported in main() so a broken install shows a message instead of silently not opening
vp = vv = vpost = None     # presets + preview + post-writer modules (imported in main() too)
ve = None                  # the chibi-emotes module (imported the first time it is needed, see EM())
VERSION = "2.2"
BETA = True                  # shown in the banner, the title bar, Settings and the README
VER_LABEL = f"v{VERSION}" + (" beta" if BETA else "")
HOME = os.path.expanduser("~")
CFG = os.path.join(HOME, ".vtuberclipper.json")
GIF_DIR = os.path.join(HOME, ".vtuberclipper_previews")
LOGF = os.path.join(HOME, "VTuberClipper_log.txt")
T = lambda bg, panel, fg, mute, a, a2, entry, on="#ffffff", m="plain": dict(bg=bg, panel=panel, fg=fg, mute=mute, accent=a, accent2=a2, entry=entry, on=on, mascot=m)
THEMES = {
    "Sakura Pop": T("#fff0f6", "#ffffff", "#5a3550", "#a87a98", "#ff6fae", "#c7a6ff", "#ffe0ee"),
    "Lavender Dream": T("#f3eeff", "#ffffff", "#3f3566", "#8d82b5", "#9b7bff", "#ff9ed2", "#e4d9ff", m="bunny"),
    "Mint Cream": T("#ecfbf5", "#ffffff", "#2f5a4d", "#74a898", "#17b58a", "#7cc7ff", "#d0f1e4", m="cat"),
    "Peach Soda": T("#fff3ea", "#ffffff", "#6a4331", "#b58a74", "#ff8a5c", "#ffc15e", "#ffe0cc", m="fox"),
    "Cotton Candy": T("#f0f6ff", "#ffffff", "#41507a", "#8a97bf", "#ff7eb6", "#7ec8ff", "#dbe8ff", m="bunny"),
    "Matcha Latte": T("#f4f7ea", "#ffffff", "#4a5a33", "#8a9a6a", "#69a82b", "#f6b26b", "#e3ecca"),
    "Starry Night": T("#17142b", "#221d3d", "#f1ecff", "#a79cd1", "#ff7ac6", "#8f7bff", "#2c2650"),
    "Bubblegum Dark": T("#2a1626", "#3a2034", "#ffe8f3", "#d09ab8", "#ff5fa8", "#b98cff", "#43263c", m="cat"),
    # in her own colours (crimson, black, white and pink)
    "Crimson Heart": T("#1a0b10", "#27121a", "#fff0f3", "#c99aa6", "#e0143c", "#ff9ec4", "#34181f", "#ffffff", "plain"),
    "Snow Rose": T("#fff5f7", "#ffffff", "#3a2330", "#a8808e", "#d81e48", "#ffb3cc", "#ffe3ea", "#ffffff", "plain"),
    # VTuber-style themes (each comes with its own mascot)
    "Neon Cyber": T("#0f1226", "#181c3a", "#e6f1ff", "#8d9bd6", "#00c8e6", "#ff3df0", "#1f2447", "#071018", "robot"),
    "Witchy Moon": T("#1b1230", "#261a40", "#f1e8ff", "#a99bd0", "#b57cff", "#ffd166", "#30214f", "#ffffff", "witch"),
    "Angel Cloud": T("#f4f9ff", "#ffffff", "#3d4c6b", "#8fa0c4", "#5aa9f5", "#ffcf6e", "#e1efff", "#ffffff", "angel"),
    "Devil Imp": T("#1a0f14", "#2a1620", "#ffe8ee", "#d19aa9", "#ff3b5c", "#9b5cff", "#36202a", "#ffffff", "devil"),
    "Kitsune Fox": T("#fff4e8", "#ffffff", "#5f3b2a", "#b58c70", "#ff8a3d", "#ffd27a", "#ffe3c9", "#ffffff", "fox"),
    "Bunny Strawberry": T("#fff1f3", "#ffffff", "#6a3040", "#c08a98", "#ff5c7a", "#ffb3c1", "#ffdde4", "#ffffff", "bunny"),
    "Ocean Pearl": T("#e8fbff", "#ffffff", "#1f4a5a", "#6aa3b5", "#1fb6d4", "#7fe0c4", "#cdf1f8", m="cat"),
    "Pumpkin Ghost": T("#1f1410", "#2e1d16", "#ffeedd", "#c9a58c", "#ff8c1a", "#8a5cff", "#3a2519", "#1f1410", "ghost"),
    # chibi themes: the mascot is your model acting out her emotes (gaming while she waits, tired while she works, celebrating when it is done...)
    "Clown Party": T("#fff8e8", "#ffffff", "#4a2f55", "#a58bb0", "#ff4f8b", "#34c6ff", "#ffeccc", "#ffffff", "chibi_clown"),
    "Cool Shades": T("#0e1722", "#162434", "#e8f4ff", "#8fb0c9", "#35c8ff", "#ffd23f", "#1d3045", "#071018", "chibi_cool"),
    "Gamer Night": T("#120d24", "#1d1538", "#efe9ff", "#a79bd6", "#6ee85a", "#b04dff", "#281c4a", "#0b1a07", "chibi_gamer"),
    "Cozy Coffee": T("#f6ede3", "#fffaf4", "#5a3d2b", "#a88b75", "#b5651d", "#7fb069", "#ead9c6", "#ffffff", "chibi_cozy"),
    "This Is Fine": T("#2a1209", "#3b1b0f", "#ffe9d0", "#d9a37a", "#ff7a1a", "#ffd23f", "#4a2314", "#2a1209", "chibi_chaos"),
    "Trash Panda": T("#e9eef0", "#ffffff", "#2b3a42", "#7f949e", "#2f9e9b", "#ff9f43", "#d5e0e4", "#ffffff", "chibi_trash"),
    "Yandere Rose": T("#120a16", "#1e1226", "#f7e8ff", "#b894c9", "#e0245e", "#9b5cff", "#2a1a35", "#ffffff", "chibi_yandere"),
    "Midnight Ghost": T("#101420", "#192033", "#e9eefc", "#97a3c7", "#7f9cff", "#c8b6ff", "#222b45", "#0b1020", "chibi_spooky"),
}
DEFAULT_THEME = "Sakura Pop"
MASCOT_KIND = {"Match theme": "match", "Just me": "plain", "Cat ears": "cat", "Bunny ears": "bunny", "Fox ears": "fox", "Witch hat": "witch",
               "Angel": "angel", "Devil": "devil", "Robot": "robot", "Ghost": "ghost", "Classic mascot": "classic",
               "Chibi: gamer": "chibi_gamer", "Chibi: cool": "chibi_cool", "Chibi: chaos": "chibi_chaos", "Chibi: spooky": "chibi_spooky", "Chibi: clown": "chibi_clown",
               "Chibi: trash": "chibi_trash", "Chibi: cozy": "chibi_cozy", "Chibi: yandere": "chibi_yandere", "Chibi: my emotes": "mine"}
MY_MASCOT = {"idle": ("cool", "gaming", "laughing", "fine"), "work": ("tired", "gaming", "thinking", "cool"), "happy": ("celebrating", "laughing", "cool", "clown"),
             "oops": ("cry", "fear", "shocked", "dead", "angry", "dumb")}       # the banner mascot made from the user's own emotes: which feeling shows for each mood
MASCOTS = list(MASCOT_KIND)
MASCOT_OLD = {"cat": "Cat ears", "bunny": "Bunny ears", "fox": "Fox ears", "witch": "Witch hat", "angel": "Angel", "devil": "Devil", "robot": "Robot", "ghost": "Ghost"}   # names saved by 1.6 and older
MOODS = ("idle", "blink", "work", "happy", "oops")
MUSIC_OWN = "A song or folder from somewhere else…"
MUSIC_FOLDER = "VTuberClipper Music"          # the "My music" folder in the user folder
WHATS_NEW = [
    ("🧠 Smarter clip finding", "A new Smart finding tab. I now tell gameplay, reactions, talking, stories and singing apart - laughing, screaming and singing are heard in the sound, not only read in the words. "
                               "I skip “hey guys, welcome back” openings, mix different kinds of moments, pick a length for each kind, can end right after the punchline, use your saved chat log "
                               "and learn from the clips you keep. Every clip is labelled, and its title-ideas file says why it was picked. These are rules of thumb tuned on test sounds and on published "
                               "advice about short videos, not a trained model - check what it picks."),
    ("💥 Captions, sound and picture", "Captions: letter case, outline, shadow, words at a time, a box behind the words, rainbow words and big reaction words (LOL, EEEEK!, OOF, LET'S GO!). "
                                       "Sound: tame loud screams, hush hiss. Picture: slow-mo on the biggest moment, a freeze-frame beat, a teaser of the best moment first, a logo that hops to a new corner, "
                                       "square and landscape copies, and a ready-to-post folder. File names can use {type} {score} {len}."),
    ("🧰 Tools (the button in the top corner)", "Watch a folder for new recordings, a health check, clean up leftovers, free up space, copy and paste a look as one line of text, compare three looks side by side, "
                                               "your own hashtag bank, teach me your chat's slang, and save a spreadsheet (CSV) of your clips."),
    ("🖼 My clips and Best moments", "Search your clips by title, hashtag, kind or your own tags. Review mode goes through new clips: keep, delete or later. “Make this moment again” and “Where is this from?” "
                                     "are in ⋯ More. Fill the post planner with your newest clips in one click. Best moments lists can be saved to a file and opened another day."),
    ("👀 Easier runs", "“Try just one first” makes one clip so you can check the look before making the rest. If the app was closed in the middle of a run, it offers to pick it up again. "
                       "It remembers your cam box for each game."),
    ("🐞 Fixes", "A damaged settings file can no longer crash a render, windows that are open follow a theme change, “Compare 3 looks” no longer crashes after Tools was closed, "
              "and every new feature was tried on 15 awkward videos (no sound, 10-bit, portrait, very short…). The full list is at the top of the README."),
    ("✨ Also", "Everything from 2.1 (Quick setup, Words & buttons, the layout designer, trim and montage, the post planner), 2.0 (the Polish tab, overlays, voice effects, extra files, little helpers) "
                "and before (chibi emotes for story time, 26 themes, your own music, profiles, 11 sound packs) is still here."),
    ("🧪 This is a beta", "VTuber Clipper is still being finished. It works and is tested, but new things can have rough edges. If something looks wrong, open "
                          "Settings → About (or press F1) and use “Copy info for a bug report”."),
]
QUIPS = ["Hehe, that tickles! ♡", "Hi hi! (ﾉ◕ヮ◕)ﾉ", "Boop! ✧", "Need a hand? Pick a VOD~", "You are doing great! ♡"]
GNOTE_IDLE = "Press “Find the games” - I look through the whole video for where one game or chapter ends and the next begins. You can fix the list afterwards."
SPLIT_NAMES = {"none": "One video", "count": "A series of parts", "games": "One video per game / chapter"}
SENS_NAMES = {}                  # filled in from the engine when the app starts
STYLE_NAMES = {"gameplay": "Action & reactions", "story": "Talking & stories", "mix": "A mix of both"}
LAYOUT_NAMES = {"stack": "Cam on top + game below", "blur": "Whole screen on a background", "fill": "Fill the frame (centre crop)",
                "pip": "Game full-screen + round cam bubble", "camfull": "Cam / model only", "filler": "Cam on top + my own video below",
                "stackb": "Game on top + cam below", "side": "Cam on the left + game on the right", "custom": "My own layout (drag it myself)"}
PLATFORM_NAMES = {k: v["label"] for k, v in {"any": dict(label="Anywhere"), "tiktok": dict(label="TikTok"), "shorts": dict(label="YouTube Shorts"), "reels": dict(label="Instagram Reels")}.items()}
BG_NAMES = {"blur": "Blurred copy of the game", "color": "One colour", "image": "My own picture"}
SPEED_NAMES = {"fast": "Fast", "balanced": "Balanced", "best": "Most accurate"}
MODES = [("shorts", "✂  Shorts"), ("long", "🎞  Recap"), ("moments", "🔎  Best moments"), ("post", "📝  Post helper"), ("twitter", "🐦  Twitter"), ("clips", "🖼  My clips")]
PSUBS = [("titles", "Titles"), ("yt", "YouTube"), ("tt", "TikTok"), ("ig", "Reels"), ("x", "X")]
X_SHAPES = {"Auto (recommended)": "auto", "Square 1:1": "1:1", "Portrait 4:5": "4:5", "Landscape 16:9": "16:9", "Tall 9:16": "9:16"}
SUBTABS = [("quick", "Quick setup"), ("smart", "Smart finding"), ("basics", "Clips & layout"), ("text", "Words & buttons"), ("fx", "Effects"), ("captions", "Captions"),
           ("emotes", "Chibi emotes"), ("polish", "Picture & voice"), ("extras", "Logo & music"), ("post", "Posting & files")]
LEFT_W, THUMB_W, THUMB_H, BANNER_H = 318, 286, 161, 88
RECENT_MAX = 12
ASPECT_NAMES = {"9:16": "9:16  vertical (Shorts, TikTok, Reels)", "4:5": "4:5  portrait (Instagram feed)", "1:1": "1:1  square", "16:9": "16:9  landscape"}
HOOK_NAMES = {"smart": "Smart: the punchiest line", "words": "The first words said", "mine": "My own text"}
DONE_NAMES = {"nothing": "Do nothing", "sound": "Play a chime", "folder": "Chime and open the folder", "sleep": "Put the PC to sleep", "shutdown": "Shut the PC down"}
POWER_ACTS = ("sleep", "shutdown")                 # never remembered: they apply to one run only
RENDER_JOBS = ("shorts", "long", "twitter")        # jobs that make videos
POS_NAMES = {"low": "Lower third", "mid": "Middle", "high": "Upper"}
CORNER_NAMES = {"tl": "Top left", "tr": "Top right", "bl": "Bottom left", "br": "Bottom right"}
OPT_STR = ("cap_style", "cap_font", "cap_size", "cap_pos", "cap_text", "cap_hi", "cap_edge", "sfx_pack", "pip_pos", "logo", "logo_pos", "logo_size",
           "handle", "handle_pos", "music", "music_vol", "hint", "fixes", "channel", "game", "tags",
           "platform", "intro", "outro", "cta", "stickers", "sticker_size", "filler", "bg_style", "bg_color", "bg_image", "hook_mode", "hook_text",
           "emote_level", "emote_size", "emote_pos",
           "color_look", "crisp", "fade", "hide_box", "hide_style", "lower_name", "lower_sub", "follow_text", "buddy_feeling", "buddy_pos", "buddy_size",
           "voice_fx", "voice_eq", "bleep_sound", "loudness", "name_pattern",
           "text_boxes", "callouts", "custom_layout", "tts_voice", "tts_rate",
           "chat_file", "range_from", "range_to", "extra_shapes", "cap_case", "cap_outline", "cap_shadow", "cap_words", "cap_box", "ready_dir")
OPT_BOOL = ("cap_emph", "cap_emoji", "review", "cover", "swears", "fresh", "duck", "post_kit", "srt", "translate", "voice_clean", "fix_lag",
            "emotes", "emote_burst", "emote_recap", "emote_cover", "emote_review",
            "auto_light", "auto_crop", "vignette", "part_badge", "buddy", "emote_fx", "emote_sound", "transcript", "vod_folder",
            "smart", "auto_look", "smart_len", "variety", "skip_greet", "tight_end", "use_taste", "hop_logo", "slowmo", "freeze", "teaser", "react_words", "tame", "hush", "cap_rainbow")
LOOK_OPTS = ("cap_style", "cap_font", "cap_size", "cap_pos", "cap_text", "cap_hi", "cap_edge", "cap_emph", "cap_emoji", "sfx_pack", "translate", "bg_style", "bg_color",
             "cap_case", "cap_outline", "cap_shadow", "cap_words", "cap_box", "cap_rainbow")   # what a style preset controls
SW_ROW = 66                       # height of one row of theme swatches in Settings
SW_COLS, SW_STEP = 5, 128         # swatches per row and the distance from one to the next
GAL_H = 274                       # height of the style gallery
APP_DIR = os.path.dirname(os.path.abspath(__file__))
CARD_W, STATIC_IDX = 128, 26
VIDEO_EXT = (".mp4", ".mkv", ".mov", ".webm", ".ts", ".flv", ".avi", ".m4v")      # gallery card width; which preview frame is shown while a card is still
SITES = {"kick": ("Kick", "#53fc18"), "twitch": ("Twitch", "#9146ff"), "youtube": ("YouTube", "#ff0033")}
QUALITY = {"Best": "bv*+ba/b", "1080p": "bv*[height<=1080]+ba/b[height<=1080]",
           "720p": "bv*[height<=720]+ba/b[height<=720]", "480p": "bv*[height<=480]+ba/b[height<=480]"}
EFFECT_GROUPS = [
    ("🎥 Camera moves", [("zoom", "🔍 Punch zoom"), ("shake", "📳 Impact shake"), ("pan", "🎥 Pan / drift"), ("pushin", "🐾 Slow push-in"),
                         ("tilt", "🌀 Tilt on hits"), ("zoomout", "🔭 Opening zoom-out"), ("cutzoom", "🎬 Jump-cut zoom"), ("blur", "🌫 Blur cuts")]),
    ("💥 Hit effects", [("flash", "⚡ Flash on hits"), ("sfx", "🔊 Boom sound"), ("glitch", "📺 Glitch on hits"), ("bw", "🖤 B&W flash"),
                        ("lines", "💢 Anime speed lines"), ("ring", "🔵 Shockwave ring"), ("hearts", "💖 Heart & star burst"), ("whoosh", "💨 Whoosh on cuts"),
                        ("marks", "❗ Manga reaction marks"), ("confetti", "🎉 Confetti burst")]),
    ("🎀 Look & style", [("pop", "🎨 Color pop"), ("glow", "🌸 Dreamy glow"), ("vhs", "📼 Retro VHS"), ("frame", "🖼 Pink frame"),
                         ("sparkle", "✨ Twinkling sparkles"), ("petals", "🌸 Sakura petals"), ("bar", "📊 Progress bar"), ("hook", "🪝 Hook title")]),
]
EFFECTS = [e for _, g in EFFECT_GROUPS for e in g]
HOVER_DELAY = 2000          # ms the pointer rests on an effect before its description appears
# What every effect does, in plain words. "Big moment" = a loud burst, a laugh or a hype word like OMG / WTF that the app found in the clip.
EFFECT_HELP = {
    "zoom": "On every big moment the picture quickly punches in about 10% and eases back out.",
    "shake": "The punch zoom also jolts the picture sideways and up and down for a split second. Needs Punch zoom to be on.",
    "pan": "The picture is slightly enlarged and slowly sways left and right the whole clip, so it never feels static.",
    "pushin": "The camera creeps closer, very slowly, from the first second to the last. Nice for calm story parts.",
    "tilt": "On a big moment the picture twists a few degrees and snaps back. The direction alternates each time.",
    "zoomout": "The clip opens zoomed in tight and eases out to the full picture during the first second. Good at stopping the scroll.",
    "cutzoom": "Where a silence was cut out, every second piece is zoomed in a little, so the cuts look like a real editor's jump cuts.",
    "blur": "A quick blur passes over each cut to hide the jump between two pieces.",
    "flash": "The picture brightens for a split second on every big moment.",
    "sfx": "Plays an impact sound on every big moment. Pick the sound pack (boom, cute, anime, retro 8-bit) below.",
    "glitch": "The red and blue colours split apart for about a fifth of a second on every big moment, like a broken TV.",
    "bw": "The colour drains out for a split second on every big moment.",
    "lines": "Manga-style speed lines flicker around the picture for a third of a second on every big moment.",
    "ring": "A ring expands outward from the middle of the picture on every big moment, in your effects colour.",
    "hearts": "Hearts and stars pop out of the picture on every big moment.",
    "whoosh": "A short swoosh sound at the cuts (at most 6 per clip, never closer than 2.5 seconds apart).",
    "marks": "Manga reaction marks such as !, a sweat drop, an anger mark or a music note appear on the big moments.",
    "confetti": "Party confetti falls from the top of the picture after the first big moments.",
    "pop": "Colours get more vivid (a little more saturation and contrast) so gameplay and models stand out.",
    "glow": "A soft dreamy bloom over the whole picture, like a pastel filter.",
    "vhs": "Old-tape look: film grain, slight colour fringing, a softer picture and thin scan lines.",
    "frame": "A photo-booth border in your effects colour with a thin white line inside it.",
    "sparkle": "Small stars twinkle over the picture for the whole clip.",
    "petals": "Pink sakura petals drift down over the picture for the whole clip.",
    "bar": "A thin bar along the bottom fills up as the clip plays. It keeps people watching until the end.",
    "hook": "A big title shown at the top for the first 3 seconds, to grab attention. By default it is the punchiest line of the clip; change what it says in the Captions tab.",
}
RECIPE_CARDS = [("highlight", "Highlights", "Only the strongest moments, short and punchy."),
                ("story", "Story", "The whole stream in order, start to finish."),
                ("gameplay", "Gameplay", "Long action stretches, quiet gameplay kept."),
                ("mix", "Story + gameplay", "Talking and play mixed, in stream order.")]
GLYPHS = "♥✦✿★♪✧☁"
GREETINGS = ["Hi hi! Pick a VOD and let's make clips~ ♡", "I'm still a beta - tell me if something looks off! ♡", "Ready when you are! (ﾉ◕ヮ◕)ﾉ*:･ﾟ✧", "Let's find your best moments! ✿"]
FONT = "Segoe UI"


def mix(a, b, f):
    pa, pb = [int(a[i:i + 2], 16) for i in (1, 3, 5)], [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(x + (y - x) * f) for x, y in zip(pa, pb))


deep = lambda c: mix(c, "#000000", .28)


def rrect(c, x1, y1, x2, y2, r, **k):
    r = min(r, (x2 - x1) / 2, (y2 - y1) / 2)
    p = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return c.create_polygon(p, smooth=True, **k)


def fmt(s):
    s = int(max(0, s))
    return f"{s // 3600}h {s % 3600 // 60}m" if s >= 3600 else f"{s // 60}m {s % 60:02d}s" if s >= 60 else f"{s}s"


def fmt_size(mb):
    return f"{mb / 1024:.1f} GB" if mb >= 1024 else f"{mb:.0f} MB"


def site(url):
    u = url.lower()
    return "kick" if "kick.com" in u else "twitch" if "twitch.tv" in u else "youtube" if ("youtu.be" in u or "youtube.com" in u) else None


def open_path(p):
    try:
        if sys.platform.startswith("win"): os.startfile(p)
        else: subprocess.Popen(["xdg-open", p])
    except Exception: pass


def log_error(msg):
    try:
        with open(LOGF, "a", encoding="utf-8") as f: f.write(time.strftime("%Y-%m-%d %H:%M:%S  ") + msg + "\n")
    except Exception: pass


def center_over(win, parent, ww=None, wh=None):
    """Open a dialog in the middle of the main window (and on screen) instead of wherever the system drops it."""
    try:
        win.update_idletasks()
        ww, wh = ww or win.winfo_reqwidth(), wh or win.winfo_reqheight()
        px, py, pw, ph = parent.winfo_rootx(), parent.winfo_rooty(), parent.winfo_width(), parent.winfo_height()
        x = max(0, min(px + (pw - ww) // 2, win.winfo_screenwidth() - ww)); y = max(0, min(py + (ph - wh) // 3, win.winfo_screenheight() - wh - 60))
        win.geometry(f"{ww}x{wh}+{int(x)}+{int(y)}")
    except tk.TclError: pass

class QWriter:
    def __init__(self, q): self.q = q
    def write(self, t): self.q.put(t)
    def flush(self): pass


class CuteBar(tk.Canvas):
    """Progress bar with a little heart riding the tip."""
    def __init__(self, master):
        super().__init__(master, height=30, highlightthickness=0); self.v, self.t = 0.0, None
        self.bind("<Configure>", lambda e: self.draw())

    def __setitem__(self, k, val):
        if k == "value": self.v = max(0.0, min(100.0, float(val))) / 100; self.draw()
        else: super().__setitem__(k, val)

    def theme(self, t): self.t = t; self.configure(bg=t["bg"]); self.draw()

    def draw(self):
        if not self.t: return
        c, t, w = self, self.t, max(self.winfo_width(), 60); c.delete("all")
        rrect(c, 3, 7, w - 3, 23, 8, fill=t["entry"], outline=t["accent2"])
        fw = (w - 14) * self.v
        if fw > 4: rrect(c, 5, 9, 5 + fw + 4, 21, 6, fill=t["accent"], outline="")
        x = min(8 + fw, w - 12)
        c.create_text(x, 15, text="♥", font=("Segoe UI Symbol", 17), fill=t["accent2"] if self.v < .02 else t["accent"])
        if self.v >= .02: c.create_text(x, 15, text="♥", font=("Segoe UI Symbol", 11), fill="#ffffff")


class GifPlayer:
    """Plays a GIF on a Label. Frames are decoded a few at a time so the window stays responsive."""
    def __init__(self, root, label, path, delay=100):
        self.root, self.label, self.path, self.delay, self.frames, self.done, self.k, self.alive = root, label, path, delay, [], False, 0, True
        self.step()

    def step(self):
        if not self.alive: return
        try:
            if not self.done:
                for _ in range(8):
                    try: self.frames.append(tk.PhotoImage(file=self.path, format=f"gif -index {len(self.frames)}"))
                    except Exception: self.done = True; break
            if self.frames:
                self.label.configure(image=self.frames[self.k % len(self.frames)]); self.k += 1
        except tk.TclError: return                      # window closed
        self.root.after(self.delay, self.step)

    def stop(self): self.alive = False


class CamPicker(tk.Toplevel):
    """Drag a box over a frame of the VOD to mark where the model / facecam is."""
    def __init__(self, app, path, dur, sw, sh, initial, done, hint=None):
        super().__init__(app)
        t = self.t = app.t
        self.path, self.done, self.sw, self.sh = path, done, sw, sh
        self.title("Select model / cam area"); self.configure(bg=t["bg"]); self.transient(app)
        self.DW = min(960, int(self.winfo_screenwidth() * .62)); self.scale = sw / self.DW; self.DH = max(2, int(sh / self.scale))
        self.ratio, self.lock, self.mode, self.img = 1080 / 640, tk.BooleanVar(value=True), None, None
        ttk.Label(self, text=hint or "🎀 Drag a box around your model / facecam.  Drag inside to move · corners to resize · or draw a new box.",
                  style="Mute.TLabel", wraplength=self.DW, justify="left").pack(anchor="w", padx=12, pady=(10, 4))
        self.cv = tk.Canvas(self, width=self.DW, height=self.DH, highlightthickness=0, bg="#000", cursor="crosshair"); self.cv.pack(padx=12)
        bar = ttk.Frame(self); bar.pack(fill="x", padx=12, pady=6)
        ttk.Label(bar, text="🎞 Frame at").pack(side="left")
        self.tv = tk.DoubleVar(value=dur * .1)
        sl = ttk.Scale(bar, from_=0, to=max(dur - 1, 1), variable=self.tv, length=300); sl.pack(side="left", padx=8)
        sl.bind("<ButtonRelease-1>", lambda e: self.load())
        self.info = tk.StringVar(); ttk.Label(bar, textvariable=self.info).pack(side="left", padx=10)
        ttk.Checkbutton(bar, text="Match layout shape", variable=self.lock).pack(side="right")
        b2 = ttk.Frame(self); b2.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(b2, text="✔  Use this area", style="Accent.TButton", command=self.ok).pack(side="left")
        ttk.Button(b2, text="Cancel", command=self.destroy).pack(side="left", padx=8)
        w0 = self.DW * .3; h0 = w0 / self.ratio
        self.r = [12, self.DH - h0 - 12, 12 + w0, self.DH - 12]
        m = re.match(r"^(\d+):(\d+):(\d+):(\d+)$", initial or "")
        if m:
            w, h, x, y = (int(g) for g in m.groups()); s = self.scale
            self.r = [x / s, y / s, (x + w) / s, (y + h) / s]
        self.cv.bind("<Button-1>", self.down); self.cv.bind("<B1-Motion>", self.drag)
        self.load(); center_over(self, app)
        try: self.wait_visibility(); self.grab_set()
        except tk.TclError: pass

    def load(self):
        out = os.path.join(tempfile.gettempdir(), "vclip_cam_frame.png")
        try: os.remove(out)
        except OSError: pass
        subprocess.run([sc.FF, "-y", "-v", "error", "-ss", f"{self.tv.get():.2f}", "-i", self.path, "-frames:v", "1",
                        "-vf", f"scale={self.DW}:{self.DH}", out], **sc.NOWIN)
        try: self.img = tk.PhotoImage(file=out)
        except Exception: self.img = None
        self.cv.delete("bg")
        if self.img: self.cv.create_image(0, 0, anchor="nw", image=self.img, tags="bg"); self.cv.tag_lower("bg")
        self.draw()

    def draw(self):
        c, a = self.cv, self.t["accent"]; c.delete("ov")
        x1, y1, x2, y2 = self.r; W, H = self.DW, self.DH
        for r in ((0, 0, W, y1), (0, y2, W, H), (0, y1, x1, y2), (x2, y1, W, y2)):
            c.create_rectangle(*r, fill="#000", stipple="gray50", outline="", tags="ov")
        c.create_rectangle(x1, y1, x2, y2, outline=a, width=3, tags="ov")
        for x, y in ((x1, y1), (x2, y1), (x1, y2), (x2, y2)):
            c.create_rectangle(x - 6, y - 6, x + 6, y + 6, fill=a, outline="#ffffff", tags="ov")
        c.create_text(x1 + 8, y1 + 6, text="🎥 model / cam", anchor="nw", fill="#ffffff", font=(FONT, 10, "bold"), tags="ov")
        w, h, x, y = sc.cam_string(self.r, self.scale, self.sw, self.sh).split(":")
        self.info.set(f"Selected: {w} × {h} at ({x}, {y})")

    def down(self, e):
        x1, y1, x2, y2 = self.r; self.mode = None
        for cx, cy, ax, ay in ((x1, y1, x2, y2), (x2, y1, x1, y2), (x1, y2, x2, y1), (x2, y2, x1, y1)):
            if abs(e.x - cx) <= 12 and abs(e.y - cy) <= 12: self.mode, self.anchor = "resize", (ax, ay); return
        if x1 < e.x < x2 and y1 < e.y < y2: self.mode, self.off = "move", (e.x - x1, e.y - y1); return
        self.mode, self.anchor = "resize", (e.x, e.y)

    def drag(self, e):
        x1, y1, x2, y2 = self.r
        if self.mode == "move":
            w, h = x2 - x1, y2 - y1
            nx, ny = min(max(e.x - self.off[0], 0), self.DW - w), min(max(e.y - self.off[1], 0), self.DH - h)
            self.r = [nx, ny, nx + w, ny + h]
        elif self.mode == "resize":
            self.r = list(sc.drag_rect(*self.anchor, e.x, e.y, self.DW, self.DH, self.ratio if self.lock.get() else None))
        self.draw()

    def ok(self):
        if self.r[2] - self.r[0] < 20 or self.r[3] - self.r[1] < 20:
            return messagebox.showinfo("VTuber Clipper", "Draw a bigger box around your model / cam.", parent=self)
        self.done(sc.cam_string(self.r, self.scale, self.sw, self.sh)); self.destroy()


class Tip:
    """A small hover hint for any widget. `delay` = milliseconds the pointer has to rest on the widget first."""
    def __init__(self, widget, text, delay=500, wrap=320):
        self.w, self.text, self.tw, self.job, self.delay, self.wrap = widget, text, None, None, delay, wrap
        widget.bind("<Enter>", self.enter, add="+"); widget.bind("<Leave>", self.leave, add="+"); widget.bind("<ButtonPress>", self.leave, add="+")

    def enter(self, e=None): self.leave(); self.job = self.w.after(self.delay, self.show)

    def show(self):
        job, self.job = self.job, None
        if job:
            try: self.w.after_cancel(job)
            except Exception: pass
        if self.tw: return
        try:
            x, y = self.w.winfo_rootx() + 14, self.w.winfo_rooty() + self.w.winfo_height() + 6
            self.tw = tw = tk.Toplevel(self.w); tw.wm_overrideredirect(True); tw.wm_geometry(f"+{x}+{y}")
            tk.Label(tw, text=self.text, justify="left", bg="#3a2f4f", fg="#ffffff", padx=9, pady=6, font=(FONT, 9), wraplength=self.wrap).pack()
            tw.update_idletasks(); ww, wh = tw.winfo_reqwidth(), tw.winfo_reqheight()
            sw, sh = tw.winfo_screenwidth(), tw.winfo_screenheight()
            if x + ww > sw - 8: x = max(0, sw - ww - 8)
            if y + wh > sh - 50: y = max(0, self.w.winfo_rooty() - wh - 6)          # no room underneath: show it above the widget
            tw.wm_geometry(f"+{x}+{y}")
        except tk.TclError: pass

    def leave(self, e=None):
        if self.job:
            try: self.w.after_cancel(self.job)
            except Exception: pass
            self.job = None
        if self.tw:
            try: self.tw.destroy()
            except Exception: pass
            self.tw = None


class Pills(tk.Canvas):
    """A row of rounded buttons where exactly one is selected - used for the mode bar and the sub-tabs."""
    def __init__(self, app, parent, var, items, size=10, h=34, pad=15, gap=6, wrap=False):
        super().__init__(parent, height=h, highlightthickness=0, bd=0)
        self.app, self.var, self.items, self.h, self.pad, self.gap, self.wrap, self.h1 = app, var, items, h, pad, gap, wrap, h
        self.rects, self.hover, self.f, self.maxw = [], None, tkfont.Font(family=FONT, size=size, weight="bold"), None
        self.bind("<Button-1>", self.click); self.bind("<Motion>", lambda e: self.set_hover(self.key_at(e.x, e.y))); self.bind("<Leave>", lambda e: self.set_hover(None))
        var.trace_add("write", lambda *a: self.draw()); self.draw()

    def draw(self):
        t = self.app.t; self.delete("all"); self.configure(bg=t["bg"]); x, self.rects = 2, []
        pad, n, y0, xmax = self.pad, len(self.items), 0, 2
        if self.maxw and not self.wrap:                                     # not enough room: the buttons get a little narrower instead of running off the window
            tw = sum(self.f.measure(l) for _, l in self.items)
            if tw + 2 * pad * n + self.gap * (n - 1) + 4 > self.maxw: pad = max(5, int((self.maxw - 4 - tw - self.gap * (n - 1)) / (2 * n)))
        for key, label in self.items:
            w = self.f.measure(label) + 2 * pad; sel = self.var.get() == key
            if self.wrap and self.maxw and x > 2 and x + w > self.maxw: x, y0 = 2, y0 + self.h1                  # a second row when the window is narrow
            fill = t["accent"] if sel else (mix(t["entry"], t["accent2"], .4) if key == self.hover else t["entry"])
            rrect(self, x, y0 + 2, x + w, y0 + self.h1 - 2, (self.h1 - 4) // 2, fill=fill, outline="")
            self.create_text(x + w / 2, y0 + self.h1 / 2, text=label, font=self.f, fill=t["on"] if sel else t["fg"])
            self.rects.append((x, x + w, key, y0)); x += w + self.gap; xmax = max(xmax, x)
        self.configure(width=xmax, height=y0 + self.h1)

    def fit(self, maxw):
        maxw = int(maxw)
        if maxw > 100 and maxw != self.maxw: self.maxw = maxw; self.draw()

    def key_at(self, px, py=None): return next((k for a, b, k, y0 in self.rects if a <= px <= b and (py is None or y0 <= py <= y0 + self.h1)), None)

    def click(self, e):
        k = self.key_at(e.x, e.y)
        if k: self.var.set(k)

    def set_hover(self, k):
        if k != self.hover: self.hover = k; self.configure(cursor="hand2" if k else ""); self.draw()


def pad_time(s):
    """'1:02:03', '2:03', '75' or '1h2m3s' -> seconds (None if it isn't a time)."""
    s = (s or "").strip()
    if not s: return None
    try: return float(s)
    except ValueError: pass
    r = sc.parse_times(s, 0, 5.0, 0.0)
    return r[0][0] if r else None


class TrimDialog(tk.Toplevel):
    """Fine-tune where a moment starts and ends: two frame previews, a zoomable timeline with draggable handles and exact time boxes."""
    def __init__(self, app, video, dur, start, end, done, title="Trim moment ✎"):
        super().__init__(app)
        self.app, self.video, self.dur, self.done = app, video, max(dur, 5.0), done
        self.t = t = app.t; self.configure(bg=t["bg"]); self.title(title); self.transient(app)
        self.s, self.e = max(0.0, min(start, self.dur - 3)), max(min(end, self.dur), start + 3)
        self.w0, self.w1 = max(0.0, self.s - 45), min(self.dur, self.e + 45)
        self.sv, self.ev, self.lv = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.imgs, self.drag, self.job, self.tok = {}, None, None, 0
        pv = ttk.Frame(self, padding=(14, 12, 14, 4)); pv.pack()
        self.cv_s = tk.Canvas(pv, width=300, height=169, highlightthickness=0, bg="#000"); self.cv_s.grid(row=1, column=0, padx=(0, 10))
        self.cv_e = tk.Canvas(pv, width=300, height=169, highlightthickness=0, bg="#000"); self.cv_e.grid(row=1, column=1)
        ttk.Label(pv, text="First frame of the clip").grid(row=0, column=0, sticky="w"); ttk.Label(pv, text="Last frame of the clip").grid(row=0, column=1, sticky="w")
        self.tl = tk.Canvas(self, width=610, height=74, highlightthickness=0, bg=t["panel"], cursor="sb_h_double_arrow"); self.tl.pack(padx=14, pady=(6, 2))
        self.tl.bind("<Button-1>", self.down); self.tl.bind("<B1-Motion>", self.move); self.tl.bind("<ButtonRelease-1>", lambda e: self.up())
        zb = ttk.Frame(self); zb.pack(fill="x", padx=14)
        for txt, fn in (("◀", lambda: self.pan(-.4)), ("▶", lambda: self.pan(.4)), ("⊖ zoom out", lambda: self.zoom(2.0)), ("⊕ zoom in", lambda: self.zoom(.5)), ("fit clip", self.fit)):
            ttk.Button(zb, text=txt, command=fn).pack(side="left", padx=(0, 5))
        ttk.Label(zb, textvariable=self.lv, style="Mute.TLabel").pack(side="right")
        fr = ttk.Frame(self); fr.pack(fill="x", padx=14, pady=(8, 0))
        for lbl, var, d_ in (("Start", self.sv, "s"), ("End", self.ev, "e")):
            ttk.Label(fr, text=lbl).pack(side="left"); en = ttk.Entry(fr, textvariable=var, width=10); en.pack(side="left", padx=(5, 3))
            en.bind("<Return>", lambda ev, d_=d_: self.typed(d_)); en.bind("<FocusOut>", lambda ev, d_=d_: self.typed(d_))
            for amt in (-1, 1): ttk.Button(fr, text=f"{amt:+d}s", width=4, command=lambda d_=d_, amt=amt: self.nudge(d_, amt)).pack(side="left", padx=1)
            ttk.Label(fr, text="   ").pack(side="left")
        ttk.Label(self, text="Drag the pink handles, or type a time like 1:02:03.", style="Mute.TLabel").pack(anchor="w", padx=14, pady=(4, 0))
        bf = ttk.Frame(self); bf.pack(fill="x", padx=14, pady=10)
        ttk.Button(bf, text="✔  Use this moment", style="Accent.TButton", command=self.ok).pack(side="left"); ttk.Button(bf, text="Cancel", command=self.destroy).pack(side="left", padx=8)
        self.refresh(); self.draw(); center_over(self, app)
        try: self.wait_visibility(); self.grab_set()
        except tk.TclError: pass

    def fmt(self, x): return sc.hms(x) + (f".{int((x % 1) * 10)}" if x % 1 > .04 else "")

    def px(self, t): return 12 + (t - self.w0) / max(.001, self.w1 - self.w0) * 586
    def tt(self, x): return self.w0 + (x - 12) / 586 * (self.w1 - self.w0)

    def draw(self):
        c, t = self.tl, self.t; c.delete("all")
        step = next((d for d in (1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 1800) if (self.w1 - self.w0) / d <= 9), 3600)
        k0 = int(self.w0 // step) * step
        for k in range(int(k0), int(self.w1) + step, step):
            if k < self.w0: continue
            x = self.px(k); c.create_line(x, 44, x, 52, fill=t["mute"]); c.create_text(x, 62, text=sc.hms(k), fill=t["mute"], font=(FONT, 8))
        xs, xe = self.px(self.s), self.px(self.e)
        c.create_rectangle(12, 24, 598, 42, fill=t["entry"], outline="")
        c.create_rectangle(max(12, xs), 24, min(598, xe), 42, fill=mix(t["accent"], t["panel"], .25), outline="")
        for x in (xs, xe):
            if 6 <= x <= 604: c.create_rectangle(x - 4, 14, x + 4, 52, fill=t["accent"], outline="#ffffff", width=2)
        self.sv.set(self.fmt(self.s)); self.ev.set(self.fmt(self.e)); self.lv.set(f"Clip length {self.e - self.s:.1f}s   ·   showing {sc.hms(self.w0)} – {sc.hms(self.w1)}")

    def down(self, e):
        xs, xe = self.px(self.s), self.px(self.e)
        self.drag = "s" if abs(e.x - xs) <= abs(e.x - xe) and abs(e.x - xs) < 18 else "e" if abs(e.x - xe) < 18 else None

    def move(self, e):
        if not self.drag: return
        t = min(self.dur, max(0.0, self.tt(e.x)))
        if self.drag == "s": self.s = min(t, self.e - 3)
        else: self.e = max(t, self.s + 3)
        self.draw(); self.later()

    def up(self): self.drag = None; self.refresh()

    def later(self):
        if self.job: self.after_cancel(self.job)
        self.job = self.after(350, self.refresh)

    def typed(self, which):
        t = pad_time((self.sv if which == "s" else self.ev).get())
        if t is not None:
            if which == "s": self.s = min(max(0.0, t), self.e - 3)
            else: self.e = min(self.dur, max(t, self.s + 3))
            self.w0, self.w1 = min(self.w0, self.s), max(self.w1, self.e)
        self.draw(); self.refresh()

    def nudge(self, which, amt):
        if which == "s": self.s = min(max(0.0, self.s + amt), self.e - 3)
        else: self.e = min(self.dur, max(self.s + 3, self.e + amt))
        self.draw(); self.later()

    def pan(self, f):
        span = self.w1 - self.w0; sh = span * f; sh = max(-self.w0, min(self.dur - self.w1, sh)); self.w0 += sh; self.w1 += sh; self.draw()

    def zoom(self, f):
        mid, span = (self.w0 + self.w1) / 2, (self.w1 - self.w0) * f; span = max(8.0, min(self.dur, span))
        self.w0 = max(0.0, min(self.dur - span, mid - span / 2)); self.w1 = self.w0 + span; self.draw()

    def fit(self): self.w0, self.w1 = max(0.0, self.s - 20), min(self.dur, self.e + 20); self.draw()

    def refresh(self):
        self.tok += 1; tok, vals = self.tok, (("s", self.s, self.cv_s), ("e", max(self.s, self.e - .5), self.cv_e))
        def go():
            for key, t, cv in vals:
                out = os.path.join(tempfile.gettempdir(), f"vclip_trim_{os.getpid()}_{key}.png")
                try:
                    try: os.remove(out)
                    except OSError: pass
                    subprocess.run([sc.FF, "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", self.video, "-frames:v", "1", "-vf", "scale=300:169:force_original_aspect_ratio=decrease", out], timeout=30, **sc.NOWIN)
                    if tok != self.tok: return
                    self.app.ui(lambda out=out, cv=cv, key=key: self.show(cv, out, key, tok))
                except Exception: pass
        threading.Thread(target=go, daemon=True).start()

    def show(self, cv, path, key, tok):
        if tok != self.tok or not self.winfo_exists(): return
        try: self.imgs[key] = tk.PhotoImage(file=path)
        except Exception: return
        cv.delete("all"); cv.create_image(150, 85, image=self.imgs[key])

    def ok(self):
        self.typed("s"); self.typed("e"); self.tok += 1
        self.done(self.s, self.e); self.destroy()


class PasteDialog(tk.Toplevel):
    """Paste a list of times (from chat, a friend or YouTube chapters) and turn each into a moment."""
    def __init__(self, app, dur, length, done):
        super().__init__(app)
        self.dur, self.done = dur, done; self.t = app.t; self.configure(bg=self.t["bg"]); self.title("Paste timestamps"); self.transient(app)
        ttk.Label(self, text="One time per line, like  1:23:45 funny part  or  12:30 - 13:10 boss fight.\nA single time makes a clip that starts a few seconds before it.",
                  justify="left").pack(anchor="w", padx=14, pady=(12, 4))
        self.tx = tk.Text(self, width=58, height=10, relief="flat", padx=8, pady=6, font=("Consolas", 10), bg=self.t["entry"], fg=self.t["fg"], insertbackground=self.t["fg"])
        self.tx.pack(padx=14); self.tx.focus_set()
        lf = ttk.Frame(self); lf.pack(fill="x", padx=14, pady=(6, 0))
        ttk.Label(lf, text="Clip length when only one time is given").pack(side="left")
        self.ln = tk.StringVar(value=str(int(length))); ttk.Spinbox(lf, from_=10, to=120, textvariable=self.ln, width=5).pack(side="left", padx=8); ttk.Label(lf, text="seconds").pack(side="left")
        self.note = tk.StringVar(); ttk.Label(self, textvariable=self.note, style="Mute.TLabel").pack(anchor="w", padx=14, pady=(4, 0))
        bf = ttk.Frame(self); bf.pack(fill="x", padx=14, pady=10)
        ttk.Button(bf, text="＋  Add these moments", style="Accent.TButton", command=self.ok).pack(side="left"); ttk.Button(bf, text="Cancel", command=self.destroy).pack(side="left", padx=8)
        try: self.clipboard_get(); self.tx.insert("1.0", self.clipboard_get()) if sc.parse_times(self.clipboard_get(), dur) else None
        except Exception: pass
        center_over(self, app)

    def ok(self):
        try: ln = max(10.0, min(120.0, float(self.ln.get())))
        except ValueError: ln = 40.0
        r = sc.parse_times(self.tx.get("1.0", "end"), self.dur, ln)
        if not r: self.note.set("I couldn't find any times (they must be inside this video). Try 1:23:45 or 12:30 - 13:10."); return
        self.done(r); self.destroy()


def parse_clock(txt):
    """'1:23:45', '45:10', '1h2m3s' -> seconds (None when it isn't a time)."""
    m = sc._TSRE.search(str(txt or ""))
    return sc._to_sec(m.group(1)) if m else None


class AskDialog(tk.Toplevel):
    """A small question box with one or more text fields. `done(values)` returns an error text to stay open, or None to close."""
    def __init__(self, app, title, text, fields, done, ok_text="OK"):
        super().__init__(app)
        self.done, self.t = done, app.t; self.configure(bg=self.t["bg"]); self.title(title); self.transient(app)
        ttk.Label(self, text=text, justify="left", wraplength=440).pack(anchor="w", padx=14, pady=(12, 6))
        self.vars, first = [], None
        for lbl, dflt in fields:
            r = ttk.Frame(self); r.pack(fill="x", padx=14, pady=3); ttk.Label(r, text=lbl, width=14).pack(side="left")
            sv = tk.StringVar(value=dflt); e = ttk.Entry(r, textvariable=sv, width=34); e.pack(side="left"); self.vars.append(sv); first = first or e
        self.note = tk.StringVar(); ttk.Label(self, textvariable=self.note, style="Mute.TLabel", wraplength=440, justify="left").pack(anchor="w", padx=14, pady=(2, 0))
        bf = ttk.Frame(self); bf.pack(fill="x", padx=14, pady=10)
        ttk.Button(bf, text=ok_text, style="Accent.TButton", command=self.ok).pack(side="left"); ttk.Button(bf, text="Cancel", command=self.destroy).pack(side="left", padx=8)
        self.bind("<Return>", lambda e: self.ok()); self.bind("<Escape>", lambda e: self.destroy())
        if first: first.focus_set(); first.select_range(0, "end")
        center_over(self, app)

    def ok(self):
        err = self.done([v.get() for v in self.vars])
        if err: self.note.set(err)
        else: self.destroy()


def EM():
    """The emotes module. Imported when first needed, so a missing file can never stop the app from opening."""
    global ve
    if ve is None:
        import vcemotes
        ve = vcemotes
    return ve


_TH = {}


def emote_photo(path, size=96):
    """A Tk picture of an emote at about size px (ffmpeg makes the small copy once and keeps it on disk). None if it can't be made."""
    k = (path, size)
    if k not in _TH:
        try: _TH[k] = tk.PhotoImage(file=EM().thumb(path, size))
        except Exception: _TH[k] = None
    return _TH[k]


def prefetch_thumbs(app, paths, done, size=96):
    """Make the small pictures in the background, then call done() on the UI thread."""
    todo = [p for p in paths if (p, size) not in _TH]
    if not todo: return done()

    def work():
        for p in todo:
            try: EM().thumb(p, size)
            except Exception: pass
        app.ui(done)
    threading.Thread(target=work, daemon=True).start()


class EmoteManager(tk.Toplevel):
    """Your chibi emotes: which picture belongs to which feeling, the words that bring each feeling up, and a box to try a sentence."""
    def __init__(self, app, start=None):
        super().__init__(app)
        self.app, self.t, self.sel, self.keys, self.lib, self.meta, self.cards = app, app.t, start, [], [], {}, []
        self.configure(bg=self.t["bg"]); self.title("My chibi emotes"); self.transient(app)
        ttk.Label(self, text="Pictures of your model that pop up while you tell a story. Every picture belongs to a feeling, and the app listens for that feeling in what you say "
                             "(“I was so scared”, “hahaha”, “I'm dead”, a long silence...). Add your own pictures – a PNG with a see-through background looks best – "
                             "and choose the feeling for each one.", wraplength=820, justify="left").pack(anchor="w", padx=14, pady=(12, 6))
        body = ttk.Frame(self); body.pack(fill="both", expand=True, padx=14)
        lf = ttk.Frame(body); lf.pack(side="left", fill="y")
        self.lb = tk.Listbox(lf, width=27, height=17, exportselection=False, relief="flat", activestyle="none", font=(FONT, 10), highlightthickness=0,
                             bg=self.t["entry"], fg=self.t["fg"], selectbackground=self.t["accent"], selectforeground=self.t["on"])
        self.lb.pack(side="left", fill="y")
        lsb = ttk.Scrollbar(lf, orient="vertical", command=self.lb.yview); lsb.pack(side="left", fill="y"); self.lb.configure(yscrollcommand=lsb.set)
        rf = ttk.Frame(body); rf.pack(side="left", fill="both", expand=True, padx=(10, 0))
        self.head = tk.StringVar(); ttk.Label(rf, textvariable=self.head, font=(FONT, 11, "bold")).pack(anchor="w")
        cw = ttk.Frame(rf); cw.pack(fill="both", expand=True, pady=(4, 0))
        self.cv = tk.Canvas(cw, height=235, highlightthickness=0, bg=self.t["panel"])
        vsb = ttk.Scrollbar(cw, orient="vertical", command=self.cv.yview); self.cv.configure(yscrollcommand=vsb.set)
        self.cv.pack(side="left", fill="both", expand=True); vsb.pack(side="left", fill="y")
        self.inner = tk.Frame(self.cv, bg=self.t["panel"]); self.cv.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.cv.configure(scrollregion=self.cv.bbox("all")))
        self.cv.bind("<MouseWheel>", lambda e: self.cv.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        self.wnote = tk.StringVar()
        ttk.Label(rf, textvariable=self.wnote, style="Mute.TLabel", wraplength=560, justify="left").pack(anchor="w", pady=(8, 0))
        wr = ttk.Frame(rf); wr.pack(fill="x", pady=(3, 0))
        self.wlabel = ttk.Label(wr, text="My own words"); self.wlabel.pack(side="left")
        self.words = tk.StringVar(); we = ttk.Entry(wr, textvariable=self.words); we.pack(side="left", fill="x", expand=True, padx=8)
        we.bind("<Return>", lambda e: self.save_words()); app.tip(we, "Words or short phrases that should bring up this feeling, separated by commas – e.g. “skill issue, big yikes”. They count as strong hints.")
        ttk.Button(wr, text="Save words", command=self.save_words).pack(side="left")
        tr = ttk.Frame(self); tr.pack(fill="x", padx=14, pady=(10, 0))
        ttk.Label(tr, text="Try a sentence", font=(FONT, 10, "bold"), foreground=self.t["accent"]).pack(anchor="w")
        trr = ttk.Frame(tr); trr.pack(fill="x")
        self.try_var = tk.StringVar(value="I was so scared when the lights went out, I almost cried!")
        te = ttk.Entry(trr, textvariable=self.try_var); te.pack(side="left", fill="x", expand=True); te.bind("<Return>", lambda e: self.try_it())
        ttk.Button(trr, text="What would it show?", command=self.try_it).pack(side="left", padx=(8, 0))
        self.try_out = tk.StringVar(value="Type something you might say in a story and see which feeling the app hears.")
        ttk.Label(tr, textvariable=self.try_out, style="Mute.TLabel", wraplength=820, justify="left").pack(anchor="w", pady=(3, 0))
        bf = ttk.Frame(self); bf.pack(fill="x", padx=14, pady=12)
        self.addb = ttk.Button(bf, text="＋ Add pictures…", style="Accent.TButton", command=self.add); self.addb.pack(side="left")
        ttk.Button(bf, text="＋ New feeling…", command=self.new_feeling).pack(side="left", padx=6)
        self.delb = ttk.Button(bf, text="Delete this feeling", command=self.delete_feeling)
        ttk.Button(bf, text="\U0001F4C1 Open my emote folder", command=self.open_folder).pack(side="left", padx=6)
        if EM().STARTER_DIR: ttk.Button(bf, text="↺ Bring back starter pictures", command=self.restore).pack(side="left", padx=6)        # (tests only: the real app has none)
        ttk.Button(bf, text="Close", command=self.close).pack(side="right")
        self.lb.bind("<<ListboxSelect>>", lambda e: self.pick())
        self.protocol("WM_DELETE_WINDOW", self.close); self.bind("<Escape>", lambda e: self.close())
        self.reload(); center_over(self, app, 880, 700); self.minsize(820, 640)
        prefetch_thumbs(app, [e.path for e in self.lib], self.later)

    def later(self):
        if self.winfo_exists(): self.show()

    def reload(self):
        ve = EM(); self.lib, self.meta = ve.load(), ve.read_meta()
        by = {}
        for e in self.lib:
            for k in e.tags:
                if not e.hidden: by[k] = by.get(k, 0) + 1
        feel = ve.all_feelings(self.meta)
        core = sorted([f for f in feel if f[0] in ve.CORE], key=lambda f: ve.CORE.index(f[0]))
        bonus = [f for f in feel if f[0] not in ve.CORE and not f[2]]; mine = [f for f in feel if f[2]]
        none = [e for e in self.lib if not e.tags]
        self.keys, rows = [], []

        def add(title, group):
            if not group: return
            self.keys.append(None); rows.append(f"── {title}")
            for k, lab, _ in group:
                self.keys.append(k); n = by.get(k, 0)
                rows.append(("✓  " if n else "＋  ") + lab + (f"   ({n})" if n else "   add one"))
        if none: self.keys.append("_none"); rows.append(f"⚠  No feeling yet   ({len(none)})")
        add("The main feelings", core); add("Bonus feelings", bonus); add("My own feelings", mine)
        self.lb.delete(0, "end")
        for r in rows: self.lb.insert("end", r)
        if self.sel not in self.keys or self.sel is None: self.sel = next((k for k in self.keys if k), None)
        if self.sel in self.keys: i = self.keys.index(self.sel); self.lb.selection_clear(0, "end"); self.lb.selection_set(i); self.lb.see(i)
        self.show()

    def pick(self):
        s = self.lb.curselection()
        if not s: return
        k = self.keys[s[0]] if s[0] < len(self.keys) else None
        if k is None:                                           # a heading: stay where we were
            if self.sel in self.keys: self.lb.selection_clear(0, "end"); self.lb.selection_set(self.keys.index(self.sel))
            return
        self.sel = k; self.show()

    def label(self, k): return "No feeling yet" if k == "_none" else EM().label_of(k, self.meta)

    def show(self):
        ve = EM(); k = self.sel
        for c in self.cards: c.destroy()
        self.cards = []
        pics = [e for e in self.lib if (not e.tags if k == "_none" else k in e.tags)]
        self.head.set(f"{self.label(k)}  –  " + (f"{len(pics)} picture{'s' if len(pics) != 1 else ''}" if pics else "no picture yet"))
        if not pics:
            msg = ("These pictures have no feeling yet. Press “Feelings…” on a picture and tick one." if k == "_none" else
                   f"Nothing here yet. Press “＋ Add pictures…” and pick your {self.label(k).lower()} picture(s).")
            l = tk.Label(self.inner, text=msg, bg=self.t["panel"], fg=self.t["mute"], font=(FONT, 10), wraplength=520, justify="left", padx=12, pady=16); l.grid(row=0, column=0); self.cards.append(l)
        for i, e in enumerate(pics): self.card(e, i // 4, i % 4)
        self.cv.yview_moveto(0)
        custom = k in self.meta.get("custom", {})
        if custom: self.delb.pack(side="left", padx=6)
        else: self.delb.pack_forget()
        self.addb.configure(state="normal")
        if k in ve.EMO:
            cues, more = ve.sample_cues(k)
            self.wnote.set("The app uses this feeling when it hears things like: " + ", ".join(cues) + (f"  …and {more} more." if more else "") + "   (“not scared” is not counted as scared.)")
            self.wlabel.configure(text="My own words")
        elif custom:
            self.wnote.set("This is a feeling you made. The words below are what bring it up."); self.wlabel.configure(text="Words")
        else: self.wnote.set("Choose a feeling on the left."); self.wlabel.configure(text="My own words")
        self.words.set(ve.my_words(k, self.meta) if k and k != "_none" else "")

    def card(self, e, r, c):
        t = self.t; f = tk.Frame(self.inner, bg=t["entry"], padx=6, pady=6); f.grid(row=r, column=c, padx=6, pady=6, sticky="n"); self.cards.append(f)
        img = emote_photo(e.path, 96)
        im = tk.Label(f, image=img, text="" if img else "…", bg=t["entry"], fg=t["mute"], width=96, height=96); im.image = img; im.pack()
        tk.Label(f, text=e.name[:20] + ("  (hidden)" if e.hidden else ""), bg=t["entry"], fg=t["fg"] if not e.hidden else t["mute"], font=(FONT, 9, "bold")).pack(pady=(3, 0))
        tg = ", ".join(self.label(x) for x in e.tags) or "no feeling"
        tk.Label(f, text=tg[:26], bg=t["entry"], fg=t["mute"], font=(FONT, 8)).pack()
        b = ttk.Frame(f); b.pack(pady=(4, 0))
        ttk.Button(b, text="Feelings…", width=9, command=lambda: self.feelings_dialog(e)).grid(row=0, column=0, padx=1, pady=1)
        ttk.Button(b, text="Rename", width=7, command=lambda: self.rename(e)).grid(row=0, column=1, padx=1, pady=1)
        ttk.Button(b, text=("Show" if e.hidden else "Hide") if e.starter else "Remove", width=9, command=lambda: self.remove(e)).grid(row=1, column=0, columnspan=2, pady=1)

    def add(self):
        ve = EM(); k = self.sel if self.sel and self.sel != "_none" else None
        files = filedialog.askopenfilenames(parent=self, title="Add my emote pictures" + (f" for “{self.label(k)}”" if k else ""),
                                            filetypes=[("Pictures", "*.png *.webp *.gif"), ("All files", "*.*")])
        if not files: return
        got = ve.add_files([str(f) for f in files], tags=[k] if k else None)
        if not got: return messagebox.showinfo("VTuber Clipper", "I can only use PNG, WebP or GIF pictures.", parent=self)
        self.reload(); prefetch_thumbs(self.app, [e.path for e in self.lib], self.later)
        self.app.emote_summary()

    def rename(self, e):
        n = simpledialog.askstring("Rename picture", "A name for this picture:", initialvalue=e.name, parent=self)
        if n and n.strip(): EM().update(e.id, name=n.strip()); self.reload()

    def remove(self, e):
        ve = EM()
        if e.starter: ve.update(e.id, hidden=not e.hidden)
        elif messagebox.askyesno("Remove picture", f"Remove “{e.name}” from my emote folder?\n(The file is deleted from the folder; your original stays where it was.)", parent=self): ve.remove(e.id)
        else: return
        self.reload(); self.app.emote_summary()

    def feelings_dialog(self, e):
        """Tick every feeling this picture is for."""
        ve = EM(); w = tk.Toplevel(self); w.title("Feelings for this picture"); w.configure(bg=self.t["bg"]); w.transient(self)
        ttk.Label(w, text=f"“{e.name}” is shown for:", font=(FONT, 10, "bold")).pack(anchor="w", padx=14, pady=(12, 4))
        host = ttk.Frame(w); host.pack(fill="both", expand=True, padx=14)
        cv = tk.Canvas(host, width=300, height=330, highlightthickness=0, bg=self.t["panel"]); sb = ttk.Scrollbar(host, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=sb.set); cv.pack(side="left", fill="both", expand=True); sb.pack(side="left", fill="y")
        fr = tk.Frame(cv, bg=self.t["panel"]); cv.create_window((0, 0), window=fr, anchor="nw"); fr.bind("<Configure>", lambda ev: cv.configure(scrollregion=cv.bbox("all")))
        cv.bind("<MouseWheel>", lambda ev: cv.yview_scroll(-1 if ev.delta > 0 else 1, "units"))
        vars_ = {}
        feel = ve.all_feelings(self.meta)
        for k, lab, _ in sorted(feel, key=lambda f: (f[0] not in ve.CORE, ve.CORE.index(f[0]) if f[0] in ve.CORE else 0)):
            vars_[k] = tk.BooleanVar(value=k in e.tags)
            tk.Checkbutton(fr, text=lab, variable=vars_[k], bg=self.t["panel"], fg=self.t["fg"], selectcolor=self.t["entry"], activebackground=self.t["panel"],
                           activeforeground=self.t["fg"], anchor="w", font=(FONT, 10)).pack(fill="x", padx=8, pady=1)

        def ok():
            ve.update(e.id, tags=[k for k, v in vars_.items() if v.get()]); w.destroy(); self.reload(); self.app.emote_summary()
        bf = ttk.Frame(w); bf.pack(fill="x", padx=14, pady=10)
        ttk.Button(bf, text="OK", style="Accent.TButton", command=ok).pack(side="left"); ttk.Button(bf, text="Cancel", command=w.destroy).pack(side="left", padx=8)
        center_over(w, self)

    def save_words(self):
        k = self.sel
        if not k or k == "_none": return
        EM().set_words(k, self.words.get()); self.meta = EM().read_meta()
        self.try_out.set("Saved. Your words count as strong hints from now on.")

    def new_feeling(self):
        n = simpledialog.askstring("New feeling", "What is the feeling called? (e.g. Facepalm, Evil laugh, Hungry)", parent=self)
        if not n or not n.strip(): return
        ve = EM(); key = ve.feeling_key(n)
        if key: self.sel = key; self.reload(); return self.try_out.set(f"I already have “{self.label(key)}” – it is selected for you.")
        w = simpledialog.askstring("New feeling", f"Words that bring up “{n.strip()}” (separate with commas) – you can leave this empty and add them later:", parent=self) or ""
        self.sel = ve.add_feeling(n, w); self.reload()

    def delete_feeling(self):
        k = self.sel
        if k in self.meta.get("custom", {}) and messagebox.askyesno("Delete feeling", f"Delete the feeling “{self.label(k)}”? Its pictures stay, but lose this feeling.", parent=self):
            EM().delete_feeling(k); self.sel = None; self.reload(); self.app.emote_summary()

    def open_folder(self):
        try: os.makedirs(EM().USER_DIR, exist_ok=True)
        except OSError: return
        open_path(EM().USER_DIR)

    def restore(self):
        EM().restore_starters(); self.reload(); self.app.emote_summary()

    def try_it(self):
        ve = EM(); res = ve.try_text(self.try_var.get(), self.app.o["emote_level"].get())
        if not res: return self.try_out.set("Nothing special heard – no picture would pop up for this one.")
        lines = []
        for r in res:
            pics = ", ".join(r["pictures"]) if r["pictures"] else "no picture yet"
            note = "" if r["enough"] else "  (too weak for your “How many” setting)"
            lines.append(f"• {r['label']}  –  because of “{r['cue']}”  →  {pics}{note}")
        self.try_out.set("\n".join(lines))

    def close(self):
        try: self.app.emote_summary()
        except Exception: pass
        self.destroy()


class EmotePlanReview(tk.Toplevel):
    """Before the videos render: which picture pops up where. Change the feeling or picture, move it, make it longer or shorter, remove it or add one."""
    def __init__(self, app, clips, finish):
        super().__init__(app)
        ve = EM(); self.app, self.clips, self.finish, self.t, self.sent, self.loading = app, clips, finish, app.t, False, False
        self.lib = ve.load(); self.pics = ve.by_feeling(self.lib); self.meta = ve.read_meta()
        self.feel = [(k, ve.label_of(k, self.meta)) for k, _, _ in ve.all_feelings(self.meta) if self.pics.get(k)]
        self.items = [[dict(it) for it in c["items"]] for c in clips]; self.orig = [[dict(it) for it in c["items"]] for c in clips]
        self.cur, self.cur_item, self.shown = None, None, None
        self.configure(bg=self.t["bg"]); self.title("Check the emotes"); self.transient(app)
        ttk.Label(self, text="This is where the app thinks a picture of your model should pop up, and why. Click a line to change the feeling or picture, move it in time, "
                             "make it stay longer, or remove it. Nothing in your VOD changes.", wraplength=820, justify="left").pack(anchor="w", padx=14, pady=(12, 6))
        body = ttk.Frame(self); body.pack(fill="both", expand=True, padx=14)
        lf = ttk.Frame(body); lf.pack(side="left", fill="y")
        self.lb = tk.Listbox(lf, width=30, height=14, exportselection=False, relief="flat", activestyle="none", font=(FONT, 10), highlightthickness=0,
                             bg=self.t["entry"], fg=self.t["fg"], selectbackground=self.t["accent"], selectforeground=self.t["on"])
        self.lb.pack(side="left", fill="y"); lsb = ttk.Scrollbar(lf, orient="vertical", command=self.lb.yview); lsb.pack(side="left", fill="y"); self.lb.configure(yscrollcommand=lsb.set)
        rf = ttk.Frame(body); rf.pack(side="left", fill="both", expand=True, padx=(10, 0))
        cols = (("t", "Time", 60), ("f", "Feeling", 110), ("p", "Picture", 130), ("s", "What was said", 330))
        tw = ttk.Frame(rf); tw.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tw, columns=[c[0] for c in cols], show="headings", height=7, selectmode="browse")
        for k, lab, w in cols: self.tree.heading(k, text=lab); self.tree.column(k, width=w, anchor="w", stretch=(k == "s"))
        tsb = ttk.Scrollbar(tw, orient="vertical", command=self.tree.yview); self.tree.configure(yscrollcommand=tsb.set)
        self.tree.pack(side="left", fill="both", expand=True); tsb.pack(side="left", fill="y")
        self.tree.tag_configure("odd", background=mix(self.t["panel"], self.t["accent2"], .10))
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.pick_item())
        ed = ttk.Frame(rf); ed.pack(fill="x", pady=(8, 0))
        self.thumb = tk.Label(ed, width=96, height=96, bg=self.t["entry"]); self.thumb.grid(row=0, column=0, rowspan=3, padx=(0, 10))
        self.fv, self.pv, self.tv, self.hv = tk.StringVar(), tk.StringVar(), tk.StringVar(), tk.StringVar()
        ttk.Label(ed, text="Feeling").grid(row=0, column=1, sticky="w")
        self.fc = ttk.Combobox(ed, textvariable=self.fv, values=[l for _, l in self.feel], width=20, state="readonly"); self.fc.grid(row=0, column=2, sticky="w", padx=6)
        ttk.Label(ed, text="Picture").grid(row=1, column=1, sticky="w")
        self.pc = ttk.Combobox(ed, textvariable=self.pv, values=[], width=24, state="readonly"); self.pc.grid(row=1, column=2, sticky="w", padx=6, pady=3)
        ttk.Label(ed, text="At (seconds)").grid(row=0, column=3, sticky="w", padx=(12, 0))
        ttk.Spinbox(ed, from_=0, to=9999, increment=.1, textvariable=self.tv, width=7).grid(row=0, column=4, sticky="w", padx=6)
        ttk.Label(ed, text="Stays (seconds)").grid(row=1, column=3, sticky="w", padx=(12, 0))
        ttk.Spinbox(ed, from_=.8, to=8, increment=.2, textvariable=self.hv, width=7).grid(row=1, column=4, sticky="w", padx=6)
        eb = ttk.Frame(ed); eb.grid(row=2, column=1, columnspan=4, sticky="w", pady=(4, 0))
        ttk.Button(eb, text="Remove this one", command=self.remove).pack(side="left"); ttk.Button(eb, text="＋ Add one", command=self.add).pack(side="left", padx=6)
        ttk.Button(eb, text="↺ Back to the app's plan", command=self.reset).pack(side="left")
        self.fc.bind("<<ComboboxSelected>>", lambda e: self.feeling_changed()); self.pc.bind("<<ComboboxSelected>>", lambda e: self.picture_changed())
        for v in (self.tv, self.hv): v.trace_add("write", lambda *a: self.times_changed())
        self.note = tk.StringVar(); ttk.Label(self, textvariable=self.note, style="Mute.TLabel", wraplength=820, justify="left").pack(anchor="w", padx=14, pady=(8, 0))
        bf = ttk.Frame(self); bf.pack(fill="x", padx=14, pady=12)
        ttk.Button(bf, text="Render with this plan", style="Accent.TButton", command=self.ok).pack(side="left")
        ttk.Button(bf, text="No emotes this time", command=self.none).pack(side="left", padx=8)
        ttk.Button(bf, text="Skip checking", command=self.skip).pack(side="left")
        ttk.Button(bf, text="Stop", command=self.stop).pack(side="right")
        self.fill_clips(); self.lb.bind("<<ListboxSelect>>", lambda e: self.pick_clip())
        self.protocol("WM_DELETE_WINDOW", self.skip); self.bind("<Escape>", lambda e: self.skip())
        self.lb.selection_set(0); self.pick_clip(); center_over(self, app, 900, 640); self.minsize(840, 600)
        prefetch_thumbs(app, [e.path for e in self.lib], lambda: self.winfo_exists() and self.pick_item())

    # ----- the list of clips -----
    def clip_line(self, i):
        c = self.clips[i]; n = len(self.items[i]); mark = "✎ " if self.changed(i) else "   "
        return f"{mark}{c['label'][:26]}  ·  {sc.hms(c['start'])}  ·  {n} ★"

    def fill_clips(self):
        self.lb.delete(0, "end")
        for i in range(len(self.clips)): self.lb.insert("end", self.clip_line(i))

    def key(self, it): return (round(float(it["t"]), 2), round(float(it["hold"]), 2), it["path"])

    def changed(self, i): return [self.key(x) for x in self.items[i]] != [self.key(x) for x in self.orig[i]]

    def pick_clip(self):
        s = self.lb.curselection()
        if not s: return
        self.cur = s[0]; self.refresh_tree(); self.show_note()
        kids = self.tree.get_children()
        if kids: self.tree.selection_set(kids[0])
        else: self.cur_item = None; self.pick_item()

    def refresh_tree(self, keep=None):
        self.items[self.cur].sort(key=lambda x: float(x["t"]))
        for k in self.tree.get_children(): self.tree.delete(k)
        for n, it in enumerate(self.items[self.cur]):
            why = "a loud moment" if it.get("src") == "loud" else "a long silence" if it.get("src") == "pause" else str(it.get("text") or "(added by you)")
            self.tree.insert("", "end", iid=str(n), values=(sc.hms(it["t"]) if it["t"] >= 60 else f"{it['t']:.1f}", it.get("label", it.get("tag", "")), it.get("name", ""), why[:80]), tags=("odd",) if n % 2 else ())
        if keep is not None and keep in self.items[self.cur]:
            self.tree.selection_set(str(self.items[self.cur].index(keep)))
        self.lb.delete(self.cur); self.lb.insert(self.cur, self.clip_line(self.cur)); self.lb.selection_set(self.cur)

    def show_note(self):
        c = self.clips[self.cur]; ve = EM(); miss, weak = {}, 0
        used = [float(x["t"]) for x in self.items[self.cur]]
        for m in c.get("heard", []):
            if any(abs(m["t"] - u) < 1.6 for u in used): continue
            if not self.pics.get(m["emo"]): miss[m["emo"]] = miss.get(m["emo"], 0) + 1
            else: weak += 1
        bits = []
        if miss: bits.append("heard " + ", ".join(f"{n}× {ve.label_of(k, self.meta)}" for k, n in sorted(miss.items(), key=lambda x: -x[1])[:4]) + " but you have no picture for that yet")
        if weak: bits.append(f"{weak} more moment{'s' if weak != 1 else ''} were too weak or too close to another picture")
        self.note.set(f"This clip is {c['dur']:.0f} s long." + ("  Also: " + "; ".join(bits) + "." if bits else ""))

    # ----- one picture -----
    def pick_item(self):
        s = self.tree.selection()
        self.loading = True
        try:
            if not s or self.cur is None or int(s[0]) >= len(self.items[self.cur]):
                self.cur_item = self.shown = None; self.thumb.configure(image="", text="no picture"); self.thumb.image = None
                for v in (self.fv, self.pv, self.tv, self.hv): v.set("")
                return
            it = self.items[self.cur][int(s[0])]; self.cur_item = it
            if it is self.shown: return                            # already on show: don't overwrite what is being typed
            self.shown = it
            self.fv.set(next((l for k, l in self.feel if k == it["tag"]), it.get("label", "")))
            self.pc.configure(values=self.pic_names(it["tag"])); self.pv.set(self.pic_name_of(it))
            self.tv.set(f"{float(it['t']):.1f}"); self.hv.set(f"{float(it['hold']):.1f}")
            img = emote_photo(it["path"], 96); self.thumb.configure(image=img or "", text="" if img else "\u2026"); self.thumb.image = img
        finally: self.loading = False

    def pic_names(self, tag):
        names, seen = [], {}
        for e in self.pics.get(tag, []):
            seen[e.name] = seen.get(e.name, 0) + 1; names.append(e.name if seen[e.name] == 1 else f"{e.name} ({seen[e.name]})")
        return names

    def pic_name_of(self, it):
        es = self.pics.get(it["tag"], []); names = self.pic_names(it["tag"])
        for e, n in zip(es, names):
            if e.path == it["path"]: return n
        return names[0] if names else ""

    def commit(self, it):
        self.refresh_tree(keep=it)
        if self.cur_item is it: self.show_note()

    def feeling_changed(self):
        it = self.cur_item
        if self.loading or not it: return
        key = next((k for k, l in self.feel if l == self.fv.get()), None)
        if not key or not self.pics.get(key): return
        e = self.pics[key][0]
        it.update(tag=key, label=self.fv.get(), path=e.path, name=e.name, id=e.id); self.shown = None; self.commit(it); self.pick_item()

    def picture_changed(self):
        it = self.cur_item
        if self.loading or not it: return
        names = self.pic_names(it["tag"]); es = self.pics.get(it["tag"], [])
        if self.pv.get() in names:
            e = es[names.index(self.pv.get())]; it.update(path=e.path, name=e.name, id=e.id); self.shown = None; self.commit(it); self.pick_item()

    def times_changed(self):
        it = self.cur_item
        if self.loading or not it: return
        try: t, h = float(self.tv.get()), float(self.hv.get())
        except ValueError: return
        dur = float(self.clips[self.cur]["dur"])
        if not (0 <= t <= max(0.0, dur - .6)) or not (.5 <= h <= 10): return
        it["t"], it["hold"] = round(t, 2), round(h, 2); self.refresh_tree(keep=it); self.show_note()

    def remove(self):
        it = self.cur_item
        if not it: return
        self.items[self.cur].remove(it); self.cur_item = None; self.refresh_tree(); self.show_note()
        kids = self.tree.get_children()
        if kids: self.tree.selection_set(kids[0])
        else: self.pick_item()

    def add(self):
        if not self.feel: return messagebox.showinfo("VTuber Clipper", "You have no emote pictures yet. Add some in “My emotes” first.", parent=self)
        dur = float(self.clips[self.cur]["dur"]); sel = self.cur_item
        t = (float(sel["t"]) + float(sel["hold"]) + .4) if sel else 1.0
        t = min(max(.5, t), max(.5, dur - 1.6))
        k, l = self.feel[0]; e = self.pics[k][0]
        it = dict(t=round(t, 2), hold=2.2, tag=k, label=l, id=e.id, path=e.path, name=e.name, text="", cue="", src="mine", score=0)
        self.items[self.cur].append(it); self.refresh_tree(keep=it); self.show_note()

    def reset(self):
        self.items[self.cur] = [dict(x) for x in self.orig[self.cur]]; self.cur_item = None; self.refresh_tree(); self.show_note()
        kids = self.tree.get_children()
        if kids: self.tree.selection_set(kids[0])
        else: self.pick_item()

    # ----- finishing -----
    def send(self, out):
        if self.sent: return
        self.sent = True; self.finish(out)
        try: self.destroy()
        except tk.TclError: pass

    def ok(self): self.send({c["k"]: [dict(x) for x in self.items[i]] for i, c in enumerate(self.clips) if self.changed(i)})
    def skip(self): self.send({})
    def none(self): self.send({c["k"]: [] for c in self.clips})
    def stop(self): self.send({}); self.app.stop()


class CaptionReview(tk.Toplevel):
    """Fix mis-heard words before the clips are rendered. `finish(texts)`: {clip index: corrected text} (empty = render as they are)."""
    def __init__(self, app, items, finish):
        super().__init__(app)
        self.app, self.items, self.finish, self.t, self.sent = app, items, finish, app.t, False
        self.cur, self.text = None, {it["k"]: it["text"] for it in items}
        self.orig = dict(self.text)
        self.configure(bg=self.t["bg"]); self.title("Check the captions"); self.transient(app)
        ttk.Label(self, text="Fix any words the speech model got wrong. You can add or remove words too, and the timing follows along. "
                             "Only the videos you are making change, never your VOD.", wraplength=700, justify="left").pack(anchor="w", padx=14, pady=(12, 6))
        body = ttk.Frame(self); body.pack(fill="both", expand=True, padx=14)
        lf = ttk.Frame(body); lf.pack(side="left", fill="y")
        self.lb = tk.Listbox(lf, width=30, height=12, exportselection=False, relief="flat", activestyle="none", font=(FONT, 10), highlightthickness=0,
                             bg=self.t["entry"], fg=self.t["fg"], selectbackground=self.t["accent"], selectforeground=self.t["on"])
        self.lb.pack(side="left", fill="y")
        lsb = ttk.Scrollbar(lf, orient="vertical", command=self.lb.yview); lsb.pack(side="left", fill="y"); self.lb.configure(yscrollcommand=lsb.set)
        rf = ttk.Frame(body); rf.pack(side="left", fill="both", expand=True, padx=(10, 0))
        self.head = tk.StringVar(); ttk.Label(rf, textvariable=self.head, style="Mute.TLabel").pack(anchor="w")
        tf = ttk.Frame(rf); tf.pack(fill="both", expand=True, pady=(3, 0))
        self.tx = tk.Text(tf, width=62, height=12, wrap="word", relief="flat", padx=10, pady=8, font=(FONT, 11), undo=True, highlightthickness=0,
                          bg=self.t["entry"], fg=self.t["fg"], insertbackground=self.t["fg"])
        tsb = ttk.Scrollbar(tf, orient="vertical", command=self.tx.yview); self.tx.configure(yscrollcommand=tsb.set)
        self.tx.pack(side="left", fill="both", expand=True); tsb.pack(side="left", fill="y")
        self.remember = tk.BooleanVar(value=True)
        ttk.Checkbutton(self, text="Remember my corrections for next time (adds them to Fix words in the Captions tab)", variable=self.remember).pack(anchor="w", padx=14, pady=(8, 0))
        bf = ttk.Frame(self); bf.pack(fill="x", padx=14, pady=10)
        self.go = ttk.Button(bf, text="Render with these captions", style="Accent.TButton", command=self.ok); self.go.pack(side="left")
        ttk.Button(bf, text="Skip checking", command=self.skip).pack(side="left", padx=8)
        ttk.Button(bf, text="Stop", command=self.stop).pack(side="right")
        for i in range(len(items)): self.lb.insert("end", self.label(i))
        self.lb.bind("<<ListboxSelect>>", lambda e: self.pick())
        self.protocol("WM_DELETE_WINDOW", self.skip); self.bind("<Escape>", lambda e: self.skip())
        self.lb.selection_set(0); self.pick()
        self.tx.focus_set(); center_over(self, app)

    def label(self, i):
        it = self.items[i]; mark = "✎ " if self.changed(it["k"]) else "   "
        return f"{mark}Clip {i + 1}  ·  {sc.hms(it['start'])}  ·  {it['dur']:.0f} s"

    def changed(self, k): return " ".join(self.text[k].split()) != " ".join(self.orig[k].split())

    def store(self):
        if self.cur is None: return
        k = self.items[self.cur]["k"]; self.text[k] = " ".join(self.tx.get("1.0", "end-1c").split())
        self.lb.delete(self.cur); self.lb.insert(self.cur, self.label(self.cur)); self.lb.selection_set(self.cur)

    def pick(self):
        sel = self.lb.curselection()
        if not sel: return
        self.store(); self.cur = sel[0]; it = self.items[self.cur]
        self.head.set(f"Clip {self.cur + 1} of {len(self.items)} · starts at {sc.hms(it['start'])} · {it['dur']:.0f} seconds · {len(self.text[it['k']].split())} words")
        self.tx.delete("1.0", "end"); self.tx.insert("1.0", self.text[it["k"]]); self.tx.edit_reset()

    def send(self, texts):
        if self.sent: return
        self.sent = True; self.finish(texts)
        try: self.destroy()
        except tk.TclError: pass

    def ok(self):
        self.store(); out = {k: v for k, v in self.text.items() if self.changed(k)}
        if out and self.remember.get(): self.app.remember_fixes([(self.orig[k], v) for k, v in out.items()])
        self.send(out)

    def skip(self): self.send({})

    def stop(self): self.send({}); self.app.stop()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"VTuber Clipper ♡  {VER_LABEL}")
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        ww, wh = min(1200, sw - 40), min(820, sh - 90)
        self.geometry(f"{ww}x{wh}+{max(0, (sw - ww) // 2)}+10"); self.minsize(min(1000, ww), min(640, wh))
        cfg = dict(theme=DEFAULT_THEME, out=os.path.join(HOME, "StreamClips"), model="small", device="auto", cookies="none",
                   quality="Best", auto_update=True, gpu_enc=True, cal=1.0, oq="High", ores="1080p", ofps="30", mascot="Match theme",
                   preset="kawaii", look=None, opts=None, speed="balanced", parallel="auto", mode="shorts", done="sound",
                   awake=True, lowprio=True, recent=[], seen="", win="", zoomed=False, music_own="")
        try:
            saved = json.load(open(CFG, encoding="utf-8"))
            if isinstance(saved, dict): cfg.update(saved)
        except Exception: pass
        if not isinstance(cfg["out"], str) or not cfg["out"].strip(): cfg["out"] = os.path.join(HOME, "StreamClips")
        cfg["mascot"] = MASCOT_OLD.get(str(cfg.get("mascot")), cfg.get("mascot"))
        self.restore_geometry(cfg.get("win"), cfg.get("zoomed"))
        for k, ok in (("theme", THEMES), ("quality", QUALITY), ("oq", sc.QUALITY_MBPS), ("ores", sc.RESOLUTIONS), ("mascot", MASCOTS),
                      ("model", ("tiny", "base", "small", "medium")), ("device", ("auto", "cuda", "cpu")),
                      ("cookies", ("none", "chrome", "firefox", "edge", "brave")), ("ofps", ("25", "30", "60")), ("speed", sc.SPEECH_SPEEDS),
                      ("parallel", ("auto", "1", "2", "3", "4")), ("mode", dict(MODES)), ("done", DONE_NAMES)):
            if str(cfg[k]) not in ok: cfg[k] = dict(theme=DEFAULT_THEME, quality="Best", oq="High", ores="1080p", model="small",
                                                    device="auto", cookies="none", ofps="30", mascot="Match theme", speed="balanced", parallel="auto", mode="shorts", done="sound")[k]
        self.v = {k: tk.StringVar(value=str(d)) for k, d in dict(
            video="", url="", words="", cam="", gap="1.5", n="8", lmin="25", lmax="45", layout="stack", aspect="9:16", rmin="10", rmax="15", split="none", psplit="count", pcount="3", pmin="10", gsens="chapters", gcount="Auto", gmin="10", style="mix",
            recipe="highlight", mn="15", mlo="20", mhi="60", msort="Best first", mq="", x_shape="Auto (recommended)", x_max="140",
            **{k: cfg[k] for k in ("theme", "out", "model", "device", "cookies", "quality", "mascot", "speed", "parallel")}).items()}
        self.mode, self.sub, self.pills = tk.StringVar(value=cfg["mode"]), tk.StringVar(value="basics"), []
        self.oq, self.ores, self.ofps = (tk.StringVar(value=str(cfg[k])) for k in ("oq", "ores", "ofps"))
        self.auto_update, self.gpu_enc = tk.BooleanVar(value=bool(cfg["auto_update"])), tk.BooleanVar(value=bool(cfg["gpu_enc"]))
        self.done_act = tk.StringVar(value="sound" if str(cfg["done"]) in POWER_ACTS else str(cfg["done"]))         # what to do when a job is finished
        self.power_win = None
        self.silence, self.caps, self.lcaps = tk.BooleanVar(value=True), tk.BooleanVar(value=True), tk.BooleanVar(value=True)
        self.lpan, self.lcut = tk.BooleanVar(value=True), tk.BooleanVar(value=True)           # long-form: captions, pans, jump-cut zooms
        self.rwhole = tk.BooleanVar(value=False)                                              # recap tab: don't shorten, only cut into parts
        self.games, self.games_video = [], ""                                                  # the parts found in the current VOD
        rc = cfg.get("recap") if isinstance(cfg.get("recap"), dict) else {}
        for k_, ok_ in (("split", tuple(SPLIT_NAMES)), ("psplit", ("count", "length")), ("gsens", tuple(sc.GAME_SENS))):
            if str(rc.get(k_)) in ok_: self.v[k_].set(str(rc[k_]))
        for k_ in ("rmin", "rmax", "pcount", "pmin", "gmin"):
            try:
                if float(rc[k_]) > 0: self.v[k_].set(str(rc[k_]))
            except (KeyError, TypeError, ValueError): pass
        self.rwhole.set(bool(rc.get("whole", False)))
        self.fx = {k: tk.BooleanVar(value=bool(x)) for k, x in sc.FX["gameplay"].items()}
        self.intensity, self.status = tk.StringVar(value="Normal"), tk.StringVar(value="Ready ✿")
        self.accent = tk.StringVar(value="")                                                  # effects colour; empty = follow the theme
        self.o = {k: tk.StringVar(value=str(sc.OPTS[k])) for k in OPT_STR}
        self.o.update({k: tk.BooleanVar(value=bool(sc.OPTS[k])) for k in OPT_BOOL})
        self.lang_name = tk.StringVar(value="Auto-detect")
        self.sel_preset, self.upresets, self.batch = tk.StringVar(value=str(cfg["preset"])), vp.load_user(), []
        self.frames, self.anim, self.hover, self.gal_imgs, self.preview_win = {}, {}, None, {}, None
        self.static, self.frame_order, self.done_load, self.animating, self.pv_player = {}, [], set(), None, None
        try:
            self.cal = float(cfg["cal"])
            self.cal = 1.0 if self.cal != self.cal else min(3.0, max(.3, self.cal))   # NaN -> 1.0
        except Exception: self.cal = 1.0
        if isinstance(cfg.get("opts"), dict):
            for k, val in cfg["opts"].items():
                if k in self.o and isinstance(val, (str, int, float, bool)): self.o[k].set(val)
            if str(cfg["opts"].get("lang_name", "")) in sc.LANGS: self.lang_name.set(cfg["opts"]["lang_name"])
        if isinstance(cfg.get("look"), dict): self.apply_look(cfg["look"])
        else: self.apply_look(vp.BY_ID.get(self.sel_preset.get(), vp.PRESETS[0])["look"])
        self.q, self.busy, self.failed, self.done, self.cancelled, self.sw = queue.Queue(), False, False, False, False, None
        self.pct, self.plabel, self.t0, self.est_total, self.vod_s, self.hw_text, self.frame = 0.0, "", 0.0, 0, 0.0, "", 0
        self.vinfo, self.vthumb_img, self.clip_imgs, self.clip_key, self.hwv = {}, None, {}, None, tk.StringVar()
        self.bi, self.bn = 0, 1                                                              # which VOD of a batch is being made
        self.parts, self.heads, self.combos, self.updated = [], [], [], False
        self.moments, self.mview, self.mom_file, self.fxheads = [], [], "", []
        self.pt, self.pl, self.texts, self.pkit, self.pargs, self.pseed = {}, {}, [], None, None, 0           # post helper / twitter results
        self.p_vtuber, self.p_reach = tk.BooleanVar(value=True), tk.BooleanVar(value=False)
        self.x_caps, self.x_tags, self.x_pick, self.xres, self.xargs, self.x_user = tk.BooleanVar(value=True), tk.BooleanVar(value=True), tk.IntVar(value=0), None, None, False
        self.pr_sub, self.x_note, self.x_info, self.x_count, self.heard_v = (tk.StringVar(value=v_) for v_ in ("titles", "", "", "", ""))
        self.greet = random.choice(GREETINGS); self.t = THEMES[self.v["theme"].get()]
        self.sprites, self.mitem, self.cheer_until, self.quip_until, self.quip = {}, None, 0, 0, ""      # the banner mascot
        self.title_font, self.sw_tab = None, None
        self.awake_v, self.lowprio_v = tk.BooleanVar(value=bool(cfg["awake"])), tk.BooleanVar(value=bool(cfg["lowprio"]))
        self.recent = [str(x) for x in cfg["recent"] if isinstance(x, str)][:RECENT_MAX] if isinstance(cfg["recent"], list) else []
        self.seen_ver, self.music_own, self.awake_on = str(cfg["seen"]), str(cfg["music_own"] or ""), False
        self.mlabel, self.mpath, self.mdesc, self.sfx_about = tk.StringVar(), tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.mcombos, self.mown_rows = [], []
        sc.PROGRESS = self.on_prog
        self.style = ttk.Style(self); self.style.theme_use("clam")
        try: self.iconphoto(True, tk.PhotoImage(file=os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.png")))
        except Exception: pass
        self.apply_perf(); self.apply_priority()
        self.skip_save = False
        self.init20(cfg)
        self.init21(cfg)
        self.init22(cfg)
        self.build()
        for k in ("n", "lmin", "lmax", "rmin", "rmax", "split", "gcount", "model", "device", "mn", "mlo", "mhi", "speed", "parallel", "aspect", "layout"): self.v[k].trace_add("write", lambda *a: self.refresh_eta())
        self.rwhole.trace_add("write", lambda *a: (self.split_changed(), self.refresh_eta()))
        self.v["split"].trace_add("write", lambda *a: self.split_changed()); self.v["gsens"].trace_add("write", self.sens_changed)
        self.fx["vhs"].trace_add("write", lambda *a: self.refresh_eta())
        for k in ("cam", "recipe"): self.v[k].trace_add("write", lambda *a: self.refresh_eta())
        self.mode.trace_add("write", lambda *a: self.refresh_eta())
        for k_ in ("x_max", "x_shape"): self.v[k_].trace_add("write", lambda *a: self.refresh_eta())
        self.x_pick.trace_add("write", lambda *a: self.x_compose()); self.x_tags.trace_add("write", lambda *a: self.x_compose())
        self.v["video"].trace_add("write", lambda *a: self.x_detect())
        self.v["video"].trace_add("write", self.vod_changed)
        self.v["video"].trace_add("write", lambda *a: self.batch_check())
        self.v["layout"].trace_add("write", self.layout_changed); self.o["bg_style"].trace_add("write", self.layout_changed)
        self.mode.trace_add("write", lambda *a: self.show_mode()); self.sub.trace_add("write", lambda *a: self.show_sub())
        self.simple.trace_add("write", self.view_changed); self.gal_open.trace_add("write", self.gallery_toggle); self.view_apply(); self.gallery_apply()
        self.apply_output(); self.update_pinfo(); self.draw_sample(); self.show_mode(); self.show_sub(); self.layout_changed(); self.draw_vthumb(); self.split_changed()
        threading.Thread(target=self.hw_scan, daemon=True).start()
        self.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.bind("<Control-Return>", lambda e: None if self.busy else self.make())      # keyboard shortcut for the big Make button
        self.bind("<F1>", lambda e: self.open_settings("about"))
        self.bind20()
        self.start22()
        self.after(1500, self.maybe_whatsnew); self.after(6000, self.plan_tick)
        self.bind_all("<MouseWheel>", self.on_wheel)
        self.apply_theme(); self.pump(); self.tick(); self.anim_tick(); self.after(600, self.enable_dnd); self.after(900, lambda: setattr(self, "tabs_ready", True))

    # ---------- small helpers ----------
    def ui(self, fn): self.q.put(fn)            # run something on the UI thread (safe to call from worker threads)

    def report_callback_exception(self, exc, val, tb):
        msg = "".join(traceback.format_exception(exc, val, tb)); log_error(msg)
        try: self.q.put("\nInternal error (saved to " + LOGF + "):\n" + msg[-700:] + "\n"); self.status.set("Something went wrong — see Details")
        except Exception: pass

    def combo(self, parent, var, values, width=8):
        cb = ttk.Combobox(parent, textvariable=var, values=values, width=width, state="readonly")
        cb.bind("<MouseWheel>", lambda e: (self.on_wheel(e), "break")[1]); self.combos.append(cb); return cb

    def spin(self, parent, var, lo, hi, inc=1, width=6):
        sp = ttk.Spinbox(parent, from_=lo, to=hi, increment=inc, textvariable=var, width=width)
        sp.bind("<MouseWheel>", lambda e: (self.on_wheel(e), "break")[1]); return sp

    def pick(self, parent, var, names, width=26):
        """Drop-down that shows friendly names but stores the short id in `var`."""
        disp = tk.StringVar(value=names.get(var.get(), ""))
        cb = self.combo(parent, disp, list(names.values()), width); inv = {v: k for k, v in names.items()}
        cb.bind("<<ComboboxSelected>>", lambda e: var.set(inv.get(disp.get(), var.get())))
        var.trace_add("write", lambda *a: disp.set(names.get(var.get(), disp.get())))
        return cb

    # ---------- looks (what a style preset sets) ----------
    def all_presets(self): return list(vp.PRESETS) + list(self.upresets)

    def get_look(self):
        def n(key, d, cast=int):
            try: return cast(float(self.v[key].get()))
            except (ValueError, TypeError): return d
        o = self.opts_dict()
        return vp.full_look(dict(style=self.v["style"].get(), lmin=n("lmin", 25), lmax=n("lmax", 45), gap=n("gap", 1.5, float), layout=self.v["layout"].get(),
                                 aspect=self.v["aspect"].get(), fx={k: x.get() for k, x in self.fx.items()}, intensity=self.intensity.get(),
                                 accent=self.accent.get() or None, opts={k: o[k] for k in LOOK_OPTS}))

    def apply_look(self, L):
        L = vp.full_look(L)
        for k in ("style", "layout", "aspect"): self.v[k].set(L[k])
        self.v["lmin"].set(str(L["lmin"])); self.v["lmax"].set(str(L["lmax"])); self.v["gap"].set(str(L["gap"]))
        for k, x in L["fx"].items():
            if k in self.fx: self.fx[k].set(bool(x))
        self.intensity.set(L["intensity"] if L["intensity"] in ("Subtle", "Normal", "Hype") else "Normal"); self.accent.set(L["accent"] or "")
        for k in LOOK_OPTS: self.o[k].set(L["opts"].get(k, sc.OPTS[k]))
        if hasattr(self, "cap_sample"): self.draw_sample()

    def opts_dict(self):
        d = {k: self.o[k].get() for k in OPT_STR}
        d.update({k: bool(self.o[k].get()) for k in OPT_BOOL})
        d["lang"] = sc.LANGS.get(self.lang_name.get(), ""); d["aspect"] = self.v["aspect"].get()
        return sc.get_opts(d)

    def accent_hex(self):
        a = self.accent.get().strip().lstrip("#")
        return a if len(a) == 6 else self.t["accent"].lstrip("#")

    def num(self, key, label, lo, hi, cast=int):
        try: x = cast(float(self.v[key].get()))
        except Exception: raise ValueError(f"'{label}' needs a number between {lo} and {hi}.")
        if not lo <= x <= hi: raise ValueError(f"'{label}' needs a number between {lo} and {hi}.")
        return x

    def on_wheel(self, e):
        try:
            if e.widget.winfo_toplevel() is not self or isinstance(e.widget, (tk.Text, tk.Listbox, ttk.Treeview)) or e.widget is self.gal: return
            c = self.scroll; bb = c.bbox("all")
            if bb and bb[3] > c.winfo_height(): c.yview_scroll(-1 if e.delta > 0 else 1, "units")
        except Exception: pass

    def step(self, parent, text):
        c = tk.Canvas(parent, width=60, height=32, highlightthickness=0); c.pack(anchor="w", pady=(6, 3))
        self.heads.append((c, text)); return c

    def tip(self, widget, text, delay=500): Tip(widget, text, delay); return widget

    def head(self, parent, text, row):
        h_ = ttk.Label(parent, text=text, font=(FONT, 10, "bold"), foreground=self.t["accent"])
        h_.grid(row=row, column=0, columnspan=4, sticky="w", pady=(12 if row else 0, 3)); self.fxheads.append(h_); return h_

    def frow(self, parent, r, label, key, kinds, extra=None, tip=None):
        """A 'label  [file box]  Browse ✖' row for one of the file options."""
        o = self.o; ttk.Label(parent, text=label).grid(row=r, column=0, sticky="w", pady=3)
        ttk.Entry(parent, textvariable=o[key]).grid(row=r, column=1, sticky="we", padx=8)
        f_ = ttk.Frame(parent); f_.grid(row=r, column=2, sticky="w")
        ttk.Button(f_, text="Browse", command=lambda: self.browse_file(key, kinds)).pack(side="left")
        ttk.Button(f_, text="✖", width=3, command=lambda: o[key].set("")).pack(side="left", padx=4)
        if extra: extra(f_)
        return f_

    # ---------- layout ----------
    def build(self):
        self.banner = tk.Canvas(self, height=BANNER_H, highlightthickness=0); self.banner.pack(fill="x")
        self.setbtn = ttk.Button(self.banner, text="⚙  Settings", width=12, command=self.open_settings)
        self.toolbtn = ttk.Button(self.banner, text="🧰  Tools", width=12, command=self.open_toolbox)
        self.banner.bind("<Configure>", lambda e: self.draw_banner()); self.banner.bind("<Button-1>", self.poke_mascot)
        self.logf = ttk.Frame(self)                                    # the Details drawer; shown at the very bottom on demand
        self.log = tk.Text(self.logf, height=9, relief="flat", padx=8, pady=6, font=("Consolas", 9))
        lbar = ttk.Frame(self.logf); lbar.pack(side="top", fill="x")
        for txt_, cmd_ in (("💾 Save log", self.log_save), ("📋 Copy", self.log_copy), ("🧹 Clear", self.log_clear)): ttk.Button(lbar, text=txt_, command=cmd_).pack(side="left", padx=(0, 6), pady=(0, 3))
        lsb = ttk.Scrollbar(self.logf, orient="vertical", command=self.log.yview); self.log.configure(yscrollcommand=lsb.set)
        lsb.pack(side="right", fill="y"); self.log.pack(side="left", fill="both", expand=True)
        self.main = main = ttk.Frame(self); main.pack(fill="both", expand=True)
        left = ttk.Frame(main, width=LEFT_W); left.pack(side="left", fill="y"); left.pack_propagate(False)
        ttk.Separator(main, orient="vertical").pack(side="left", fill="y", pady=10)
        right = ttk.Frame(main); right.pack(side="left", fill="both", expand=True)
        self.build_left(left); self.build_right(right)

    def build_left(self, L):
        v = self.v
        bot = ttk.Frame(L, padding=(14, 0, 12, 12)); bot.pack(side="bottom", fill="x")
        top = ttk.Frame(L, padding=(14, 4, 12, 0)); top.pack(side="top", fill="both", expand=True)
        wl = LEFT_W - 40
        # --- 1: the video
        self.step(top, "①  Your video")
        self.left, self.left_top, self.left_bot = L, top, bot
        self.vthumb = tk.Canvas(top, width=THUMB_W, height=THUMB_H, highlightthickness=0, cursor="hand2"); self.vthumb.pack(anchor="w")
        self.vthumb.bind("<Button-1>", lambda e: self.browse_video())
        self.tip(self.vthumb, "Click to choose a video file - or drag a file from Explorer onto this window.")
        self.vname, self.vmeta = tk.StringVar(), tk.StringVar()
        r = ttk.Frame(top); r.pack(fill="x", pady=(6, 0))
        ttk.Button(r, text="📁  Choose video…", command=self.browse_video).pack(side="left")
        self.recent_btn = self.tip(ttk.Button(r, text="🕘", width=3, command=self.show_recent), "Videos and links you used lately")
        self.recent_btn.pack(side="right")
        self.qbtn = ttk.Button(r, text="✖ Clear queue", command=self.clear_queue)
        self.batch_note = tk.StringVar(); self.batch_lbl = ttk.Label(top, textvariable=self.batch_note, style="Mute.TLabel", wraplength=wl, justify="left")
        ttk.Label(top, text="…or paste a Kick / Twitch / YouTube link", style="Mute.TLabel").pack(anchor="w", pady=(8, 1))
        lr = ttk.Frame(top); lr.pack(fill="x"); lr.columnconfigure(0, weight=1)
        ue = ttk.Entry(lr, textvariable=v["url"]); ue.grid(row=0, column=0, sticky="we"); ue.bind("<Return>", lambda e: self.download())
        self.tip(ttk.Button(lr, text="📋", width=3, command=self.paste_link), "Paste the link you copied and download it (Ctrl + Shift + V)").grid(row=0, column=1, padx=(6, 0))
        self.tip(ttk.Button(lr, text="⬇", style="Accent.TButton", width=3, command=self.download), "Download the VOD from this link").grid(row=0, column=2, padx=(4, 0))
        mr = ttk.Frame(top); mr.pack(fill="x", pady=(4, 0))
        self.badge = tk.Canvas(mr, width=96, height=26, highlightthickness=0); self.badge.pack(side="left")
        ttk.Label(mr, text="quality", style="Mute.TLabel").pack(side="left", padx=(8, 4)); self.combo(mr, v["quality"], list(QUALITY), 6).pack(side="left")
        v["url"].trace_add("write", lambda *a: self.draw_badge())
        sr = ttk.Frame(top); sr.pack(fill="x", pady=(8, 0)); sr.columnconfigure(1, weight=1)
        ttk.Label(sr, text="💾").grid(row=0, column=0, padx=(0, 4))
        ttk.Entry(sr, textvariable=v["out"]).grid(row=0, column=1, sticky="we")
        self.tip(ttk.Button(sr, text="…", width=3, command=lambda: v["out"].set(filedialog.askdirectory() or v["out"].get())), "Choose where clips are saved").grid(row=0, column=2, padx=(6, 0))
        self.tip(ttk.Button(sr, text="📂", width=3, command=self.open_out), "Open the save folder").grid(row=0, column=3, padx=(4, 0))
        L.bind("<Configure>", lambda e: self.after_idle(self.fit_left))
        # --- 3: make
        self.step(bot, "③  Make")
        self.readyv = tk.StringVar()
        ttk.Label(bot, textvariable=self.readyv, wraplength=wl, justify="left").pack(anchor="w", pady=(0, 4))
        self.etav, self.eta2 = tk.StringVar(value="Pick a video to see how long this takes ♡"), tk.StringVar()
        ttk.Label(bot, textvariable=self.etav, font=(FONT, 10, "bold"), wraplength=wl, justify="left").pack(anchor="w")
        ttk.Label(bot, textvariable=self.eta2, style="Mute.TLabel", wraplength=wl, justify="left").pack(anchor="w")
        mk = ttk.Frame(bot); mk.pack(fill="x", pady=(8, 2))
        self.make_btn = ttk.Button(mk, text="✨  Make my Shorts!", style="Big.TButton", command=self.make); self.make_btn.pack(side="left", fill="x", expand=True)
        self.stop_btn = ttk.Button(mk, text="⏹", width=3, command=self.stop, state="disabled"); self.stop_btn.pack(side="left", padx=(6, 0))
        self.later_btn = ttk.Button(mk, text="⏰", width=3, command=self.later_clicked); self.later_btn.pack(side="left", padx=(6, 0))
        self.tip(self.later_btn, "Start later: the app begins by itself after a few minutes or at a clock time (Ctrl + T). Press again to cancel.")
        self.tip(self.stop_btn, "Stop the job"); self.tip(self.make_btn, "Shortcut: Ctrl + Enter")
        self.left22(mk)
        dn = ttk.Frame(bot); dn.pack(fill="x", pady=(6, 0))
        ttk.Label(dn, text="When done").pack(side="left")
        dp = self.pick(dn, self.done_act, DONE_NAMES, 25); dp.pack(side="left", padx=(8, 0))
        self.tip(dp, "What happens when a job finishes without problems. A chime is only played after jobs that took a while. "
                     "Sleep and Shut down wait 60 seconds so you can cancel, only apply to this run, and only after videos have been made.")
        pr = ttk.Frame(bot); pr.pack(fill="x", pady=(4, 0))
        self.bar = CuteBar(pr); self.bar.pack(side="left", fill="x", expand=True)
        self.pctv = tk.StringVar(value="0%"); ttk.Label(pr, textvariable=self.pctv, width=5, font=(FONT, 11, "bold")).pack(side="left", padx=(6, 0))
        sr2 = ttk.Frame(bot); sr2.pack(fill="x")
        self.det_btn = ttk.Button(sr2, text="▸ Details", command=self.toggle_log); self.det_btn.pack(side="right")
        ttk.Label(sr2, textvariable=self.status, style="Mute.TLabel", wraplength=wl - 90, justify="left").pack(side="left")

    def build_right(self, R):
        top = ttk.Frame(R, padding=(14, 12, 14, 6)); top.pack(fill="x")
        self.mode_pills = Pills(self, top, self.mode, MODES, size=10, h=40, pad=11, gap=5); self.mode_pills.pack(side="left"); self.pills.append(self.mode_pills)
        top.bind("<Configure>", lambda e: self.mode_pills.fit(e.width - 30))
        wrap = ttk.Frame(R); wrap.pack(fill="both", expand=True)
        self.scroll = tk.Canvas(wrap, highlightthickness=0, bd=0)
        vs = ttk.Scrollbar(wrap, orient="vertical", command=self.scroll.yview); self.scroll.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y"); self.scroll.pack(side="left", fill="both", expand=True)
        inner = ttk.Frame(self.scroll); win = self.scroll.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: self.scroll.configure(scrollregion=self.scroll.bbox("all")))
        self.scroll.bind("<Configure>", lambda e: self.scroll.itemconfigure(win, width=e.width - 2))
        self.pbody = ttk.Frame(inner, padding=(14, 0, 14, 14)); self.pbody.pack(fill="both", expand=True)
        self.pages = {k: ttk.Frame(self.pbody) for k, _ in MODES}
        self.build_shorts(self.pages["shorts"]); self.build_long(self.pages["long"]); self.build_moments(self.pages["moments"]); self.build_clips(self.pages["clips"])
        self.build_posthelper(self.pages["post"]); self.build_twitter(self.pages["twitter"])
        self.tab = dict(self.subs, long=self.pages["long"], moments=self.pages["moments"], clips=self.pages["clips"], post=self.pages["post"], twitter=self.pages["twitter"])

    # ----- Shorts page -----
    def build_shorts(self, P):
        v, o = self.v, self.o
        hr = ttk.Frame(P); hr.pack(fill="x")
        self.step(hr, "②  Pick a look").pack_configure(side="left", pady=(2, 4))
        pb = ttk.Frame(hr); pb.pack(side="right")
        self.gal_btn = ttk.Button(pb, text="▴ Hide looks", command=lambda: self.gal_open.set(not self.gal_open.get())); self.gal_btn.pack(side="left", padx=(0, 6))
        self.tip(self.gal_btn, "Fold the gallery of looks away once you have picked yours - the settings below move up.")
        pvb = ttk.Button(pb, text="▶ Preview", style="Accent.TButton", command=self.open_preview); pvb.pack(side="left")
        self.tip(pvb, "Renders a few real seconds with your current settings.")
        ttk.Button(pb, text="💾 Save as my style", command=self.save_preset).pack(side="left", padx=6)
        self.tip(ttk.Button(pb, text="📤", width=3, command=self.export_style), "Save this style as a file to share with another creator.").pack(side="left")
        self.tip(ttk.Button(pb, text="📥", width=3, command=self.import_style), "Add a style file somebody sent you.").pack(side="left", padx=(4, 4))
        self.del_btn = ttk.Button(pb, text="🗑", width=3, command=self.delete_preset); self.del_btn.pack(side="left")
        self.pinfo = tk.StringVar()
        self.pinfo_lbl = ttk.Label(P, textvariable=self.pinfo, wraplength=700, justify="left"); self.pinfo_lbl.pack(anchor="w", pady=(0, 4))
        gw = self.gal_wrap = ttk.Frame(P); gw.pack(fill="x")
        self.gal = tk.Canvas(gw, height=GAL_H, highlightthickness=0); self.gal.pack(fill="x")
        self.gsb = ttk.Scrollbar(gw, orient="horizontal", command=self.gal.xview); self.gsb.pack(fill="x", pady=(2, 0))
        self.gal.configure(xscrollcommand=self.gsb.set)
        self.gal.bind("<Configure>", lambda e: self.draw_gallery()); self.gal.bind("<Button-1>", self.gal_click)
        self.gal.bind("<Motion>", self.gal_motion); self.gal.bind("<Leave>", lambda e: self.set_hover(None))
        self.gal.bind("<MouseWheel>", lambda e: self.gal.xview_scroll(-1 if e.delta > 0 else 1, "units") if self.gal.xview() != (0.0, 1.0) else None)
        for txt, side, d in (("‹", "w", -3), ("›", "e", 3)):
            b_ = ttk.Button(self.gal, text=txt, width=2, command=lambda d=d: self.gal.xview_scroll(d, "units")); b_.place(relx=0 if side == "w" else 1, rely=.40, anchor=side)
        sbf = ttk.Frame(P); sbf.pack(fill="x", pady=(12, 4))
        self.subbar = Pills(self, sbf, self.sub, self.sub_items(), size=10, h=34, pad=15, wrap=True); self.subbar.pack(side="left", anchor="n"); self.pills.append(self.subbar)
        sbf.bind("<Configure>", lambda e: self.subbar.fit(e.width - 8))
        hrow = ttk.Frame(P); hrow.pack(fill="x", pady=(0, 2))
        self.reset_btn = ttk.Button(hrow, text="↺ Reset tab", command=self.reset_tab); self.reset_btn.pack(side="right")
        self.tip(self.reset_btn, "Put every setting of the tab you are looking at back to normal. Your videos and the other tabs are not touched.")
        self.view_btn = ttk.Button(hrow, text="⚙ Show all options", command=lambda: self.simple.set(not self.simple.get())); self.view_btn.pack(side="right", padx=(0, 6))
        self.tip(self.view_btn, "Simple view shows the few settings most people change. All options shows every tab: effects, colour looks, voice effects, music, posting files and more.")
        self.tab_help_lbl = ttk.Label(hrow, textvariable=self.tab_help, style="Mute.TLabel", wraplength=480, justify="left"); self.tab_help_lbl.pack(side="left", fill="x", expand=True)
        hrow.bind("<Configure>", lambda e: self.tab_help_lbl.configure(wraplength=max(200, e.width - self.view_btn.winfo_reqwidth() - self.reset_btn.winfo_reqwidth() - 30)))
        self.subs = {k: ttk.Frame(P, padding=(2, 6, 2, 0)) for k, _ in SUBTABS}
        self.build_quick(self.subs["quick"]); self.build_smart(self.subs["smart"]); self.build_text(self.subs["text"])
        self.build_basics(self.subs["basics"]); self.build_fx(self.subs["fx"]); self.build_captions(self.subs["captions"])
        self.build_emotes(self.subs["emotes"]); self.build_polish(self.subs["polish"]); self.build_extras(self.subs["extras"]); self.build_post(self.subs["post"])
        self.build22_rows()

    def show_sub(self):
        self.sync_view()
        k = self.sub.get()
        self.after_idle(self.scroll_to_tabs)
        for name, f in self.subs.items():
            if name == k: f.pack(fill="x")
            else: f.pack_forget()
        self.scroll.configure(scrollregion=self.scroll.bbox("all"))

    def show_mode(self):
        m = self.mode.get()
        for k, f in self.pages.items():
            if k == m: f.pack(fill="both", expand=True)
            else: f.pack_forget()
        try: self.scroll.yview_moveto(0); self.update_idletasks(); self.scroll.configure(scrollregion=self.scroll.bbox("all"))
        except tk.TclError: pass
        if m == "clips": self.refresh_clips()
        self.refresh_eta()

    def build_basics(self, s):
        v, o = self.v, self.o; s.columnconfigure(1, weight=1)
        lf = ttk.Frame(s)
        self.spin(lf, v["lmin"], 10, 120).pack(side="left"); ttk.Label(lf, text="  to  ").pack(side="left"); self.spin(lf, v["lmax"], 10, 120).pack(side="left")
        ttk.Label(lf, text="  seconds (ends at a natural pause)", style="Mute.TLabel").pack(side="left")
        rows = [("How many clips", self.spin(s, v["n"], 1, 30)), ("Clip length", lf),
                ("Find moments that are", self.pick(s, v["style"], STYLE_NAMES, 22)), ("Layout", self.layout_cell(s)),
                ("Shape", self.pick(s, v["aspect"], ASPECT_NAMES, 38)), ("Post on", self.pick(s, o["platform"], PLATFORM_NAMES, 22))]
        for r, (lbl, w) in enumerate(rows):
            ttk.Label(s, text=lbl).grid(row=r, column=0, sticky="w", pady=3); w.grid(row=r, column=1, sticky="w", padx=8)
        self.tip(rows[5][1], "Keeps your @name, logo, round cam and the end card away from the buttons and text that TikTok / Shorts / Reels draw on top of vertical video.")
        ttk.Label(s, text="keeps text clear of the app's buttons (vertical only)", style="Mute.TLabel").grid(row=5, column=2, sticky="w")
        ttk.Label(s, text="Model / cam area").grid(row=6, column=0, sticky="w", pady=3); self.cam_row(s).grid(row=6, column=1, columnspan=2, sticky="w", padx=8)
        # layout-specific rows (shown only when they matter)
        self.w_filler = [ttk.Label(s, text="Filler video")]
        self.w_filler[0].grid(row=7, column=0, sticky="w", pady=3)
        fe = ttk.Entry(s, textvariable=o["filler"]); fe.grid(row=7, column=1, sticky="we", padx=8)
        ff = ttk.Frame(s); ff.grid(row=7, column=2, sticky="w")
        ttk.Button(ff, text="Browse", command=lambda: self.browse_file("filler", [("Videos", "*.mp4 *.mov *.mkv *.webm")])).pack(side="left"); ttk.Button(ff, text="✖", width=3, command=lambda: o["filler"].set("")).pack(side="left", padx=4)
        self.w_filler += [fe, ff]
        self.w_bg = [ttk.Label(s, text="Background")]; self.w_bg[0].grid(row=8, column=0, sticky="w", pady=3)
        bf = ttk.Frame(s); bf.grid(row=8, column=1, columnspan=2, sticky="w", padx=8); self.w_bg.append(bf)
        self.pick(bf, o["bg_style"], BG_NAMES, 24).pack(side="left")
        self.bg_sw = tk.Button(bf, width=4, relief="flat", bd=0, cursor="hand2", command=lambda: self.pick_color("bg_color")); self.bg_sw.pack(side="left", padx=8)
        self.bg_img_e = ttk.Entry(bf, textvariable=o["bg_image"], width=26); self.bg_img_e.pack(side="left", padx=(8, 0))
        self.bg_img_b = ttk.Button(bf, text="Browse", command=lambda: self.browse_file("bg_image", [("Images", "*.png *.jpg *.jpeg *.webp")])); self.bg_img_b.pack(side="left", padx=4)
        o["bg_color"].trace_add("write", lambda *a: self.paint_swatches())
        sf = ttk.Frame(s); sf.grid(row=9, column=0, columnspan=3, sticky="w", pady=(10, 0))
        ttk.Checkbutton(sf, text="✂ Remove silences longer than", variable=self.silence).pack(side="left")
        self.spin(sf, v["gap"], 1.2, 6, .1, 5).pack(side="left", padx=6); ttk.Label(sf, text="sec  (always keeps 0.5 s of breathing room)", style="Mute.TLabel").pack(side="left")
        ttk.Checkbutton(sf, text="💬 Animated captions", variable=self.caps).pack(side="left", padx=(24, 0))
        ff_ = ttk.Frame(s); ff_.grid(row=10, column=0, columnspan=3, sticky="w", pady=(8, 0))
        fr_ = ttk.Checkbutton(ff_, text="🆕 Skip moments I already made from this video", variable=o["fresh"]); fr_.pack(side="left")
        self.tip(fr_, "Every time you press Make, the app remembers which parts of this video became a Short. Next time it picks different moments instead of "
                      "the same top ones again.")
        ttk.Button(ff_, text="Start over", command=self.forget_made).pack(side="left", padx=8)
        self.made_note = tk.StringVar(); ttk.Label(ff_, textvariable=self.made_note, style="Mute.TLabel").pack(side="left")
        self.v["video"].trace_add("write", lambda *a: self.refresh_made())

    def refresh_made(self):
        try:
            p = self.v["video"].get().strip().strip('"'); n = len(sc.load_made(p)) if os.path.isfile(p) else 0
            self.made_note.set(f"{n} clip{'s' if n != 1 else ''} made so far from this video" if n else "")
        except Exception: pass

    def forget_made(self):
        p = self.v["video"].get().strip().strip('"')
        if not os.path.isfile(p): return messagebox.showinfo("VTuber Clipper", "Pick a video first ♡")
        n = len(sc.load_made(p))
        if not n: return messagebox.showinfo("VTuber Clipper", "Nothing to forget: no clips were made from this video yet.")
        if messagebox.askyesno("VTuber Clipper", f"Forget the {n} clip{'s' if n != 1 else ''} already made from this video?\nThe next run may pick those moments again (your saved clips are not touched)."):
            sc.forget_made(p); self.refresh_made()

    def layout_changed(self, *a):
        lay, bgs = self.v["layout"].get(), self.o["bg_style"].get()
        try: self.layout_custom_check()
        except Exception: pass
        for w in self.w_filler: w.grid() if lay == "filler" else w.grid_remove()
        for w in self.w_bg: w.grid() if lay == "blur" else w.grid_remove()
        if lay == "blur":
            for w, on in ((self.bg_sw, bgs == "color"), (self.bg_img_e, bgs == "image"), (self.bg_img_b, bgs == "image")):
                if on: w.pack(side="left", padx=8 if w is self.bg_sw else (8 if w is self.bg_img_e else 4))
                else: w.pack_forget()
        try: self.scroll.configure(scrollregion=self.scroll.bbox("all"))
        except Exception: pass

    def build_fx(self, e):
        for c in range(4): e.columnconfigure(c, weight=1)
        top = ttk.Frame(e); top.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))
        ttk.Label(top, text="✨ Intensity").pack(side="left"); self.combo(top, self.intensity, ["Subtle", "Normal", "Hype"], 8).pack(side="left", padx=(6, 18))
        ttk.Label(top, text="🎨 Effects colour").pack(side="left")
        self.accent_btn = tk.Button(top, width=4, relief="flat", bd=0, cursor="hand2", command=self.pick_accent); self.accent_btn.pack(side="left", padx=6)
        self.tip(self.accent_btn, "Colour of hearts, rings, the progress bar and the end card. 'auto' follows the app theme.")
        self.accent.trace_add("write", lambda *a: self.paint_swatches())
        r = 1; self.fx_tips = {}
        for title, group in EFFECT_GROUPS:
            hl = ttk.Label(e, text=title, font=(FONT, 10, "bold"), foreground=self.t["accent"])
            hl.grid(row=r, column=0, columnspan=4, sticky="w", padx=4, pady=(8 if r > 1 else 0, 2)); self.fxheads.append(hl); r += 1
            for i, (k, lbl) in enumerate(group):
                cb = ttk.Checkbutton(e, text=lbl, variable=self.fx[k]); cb.grid(row=r + i // 4, column=i % 4, sticky="w", padx=6, pady=1)
                self.fx_tips[k] = Tip(cb, f"{lbl}\n{EFFECT_HELP.get(k, '')}", delay=HOVER_DELAY, wrap=340)
            r += (len(group) + 3) // 4
        sf = ttk.Frame(e); sf.grid(row=r, column=0, columnspan=4, sticky="w", pady=(8, 0))
        ttk.Label(sf, text="🔊 Impact sound pack").pack(side="left")
        self.pick(sf, self.o["sfx_pack"], {p: sc.sfx_label(p)[0] for p in sc.SFX_PACKS}, 16).pack(side="left", padx=8)
        self.tip(ttk.Button(sf, text="▶ Hear it", command=self.play_sfx_preview), "Plays three hits and a whoosh from this pack.").pack(side="left")
        ttk.Label(sf, textvariable=self.sfx_about, style="Mute.TLabel").pack(side="left", padx=8)
        self.o["sfx_pack"].trace_add("write", lambda *a: self.sfx_about.set(sc.sfx_label(self.o["sfx_pack"].get())[1])); self.sfx_about.set(sc.sfx_label(self.o["sfx_pack"].get())[1])
        bf = ttk.Frame(e); bf.grid(row=r + 1, column=0, columnspan=4, sticky="w", pady=(10, 0))
        ttk.Button(bf, text="✨ All on", command=lambda: [x.set(True) for x in self.fx.values()]).pack(side="left")
        ttk.Button(bf, text="Clear all", command=lambda: [x.set(False) for x in self.fx.values()]).pack(side="left", padx=6)
        ttk.Label(bf, text="Hit effects land on the real hype moments.  Recaps only use captions, pans and jump-cut zooms.", style="Mute.TLabel").pack(side="left", padx=8)
        ttk.Label(e, text="💡 Rest the pointer on any effect for 2 seconds to see what it does.", style="Mute.TLabel").grid(row=r + 2, column=0, columnspan=4, sticky="w", padx=4, pady=(6, 0))

    def build_captions(self, c):
        o = self.o; c.columnconfigure(1, weight=1)
        r0 = ttk.Frame(c); r0.grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(r0, text="Style").pack(side="left"); self.pick(r0, o["cap_style"], sc.CAPTION_STYLES, 34).pack(side="left", padx=(6, 18))
        ttk.Label(r0, text="Font").pack(side="left"); self.combo(r0, o["cap_font"], list(sc.FONTS), 16).pack(side="left", padx=6)
        ttk.Checkbutton(r0, text="Colour the big words", variable=o["cap_emph"]).pack(side="left", padx=(14, 0))
        r1 = ttk.Frame(c); r1.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Label(r1, text="Size %").pack(side="left"); self.spin(r1, o["cap_size"], 50, 160, 5, 5).pack(side="left", padx=(6, 18))
        ttk.Label(r1, text="Position").pack(side="left"); self.pick(r1, o["cap_pos"], POS_NAMES, 12).pack(side="left", padx=(6, 18))
        ttk.Label(r1, text="Colours").pack(side="left")
        self.swatches = {}
        for key, tip in (("cap_text", "text"), ("cap_hi", "highlight"), ("cap_edge", "outline")):
            b_ = tk.Button(r1, width=4, relief="flat", bd=0, cursor="hand2", command=lambda k=key: self.pick_color(k)); b_.pack(side="left", padx=(6, 0))
            self.swatches[key] = b_; ttk.Label(r1, text=tip, style="Mute.TLabel").pack(side="left", padx=(3, 4))
            o[key].trace_add("write", lambda *a: self.paint_swatches())
        self.cap_sample = tk.Canvas(c, height=96, highlightthickness=0, bd=0, bg="#2a2540"); self.cap_sample.grid(row=2, column=0, columnspan=2, sticky="we", pady=(8, 6))
        for k in ("cap_style", "cap_font", "cap_size", "cap_text", "cap_hi", "cap_edge"): o[k].trace_add("write", lambda *a: self.draw_sample())
        self.cap_sample.bind("<Configure>", lambda e: self.draw_sample())
        ttk.Label(c, text="Language spoken").grid(row=5, column=0, sticky="w", pady=2)
        lg = ttk.Frame(c); lg.grid(row=5, column=1, sticky="w", padx=8)
        self.combo(lg, self.lang_name, list(sc.LANGS), 14).pack(side="left")
        ttk.Checkbutton(lg, text="🌍 Translate to English subtitles", variable=o["translate"]).pack(side="left", padx=14)
        ttk.Label(lg, text="(a new language / hint re-transcribes once)", style="Mute.TLabel").pack(side="left")
        ttk.Label(c, text="Names & terms").grid(row=6, column=0, sticky="w", pady=2)
        ttk.Entry(c, textvariable=o["hint"]).grid(row=6, column=1, sticky="we", padx=8)
        ttk.Label(c, text="Fix words").grid(row=7, column=0, sticky="w", pady=2)
        ttk.Entry(c, textvariable=o["fixes"]).grid(row=7, column=1, sticky="we", padx=8)
        ttk.Label(c, text="Names & terms helps the speech model hear your name, your game and in-jokes.  Fix words: wrong = right, e.g.  kit ten = Kitten, mika = Mika", style="Mute.TLabel",
                  wraplength=640, justify="left").grid(row=8, column=0, columnspan=2, sticky="w", pady=(2, 0))
        ttk.Label(c, text="Emojis").grid(row=3, column=0, sticky="w", pady=2)
        ef = ttk.Frame(c); ef.grid(row=3, column=1, sticky="w", padx=8, pady=2)
        ttk.Checkbutton(ef, text="😂 Pop up on words like lol, love, dead, fire", variable=o["cap_emoji"]).pack(side="left")
        ttk.Label(ef, text="a few per clip, never on bleeped words", style="Mute.TLabel").pack(side="left", padx=8)
        ttk.Label(c, text="Check").grid(row=4, column=0, sticky="w", pady=2)
        cf_ = ttk.Frame(c); cf_.grid(row=4, column=1, sticky="w", padx=8, pady=2)
        ttk.Checkbutton(cf_, text="✎ Let me read and fix the captions before the videos render", variable=o["review"]).pack(side="left")
        ttk.Label(cf_, text="shorts and best moments", style="Mute.TLabel").pack(side="left", padx=8)
        ttk.Label(c, text="Hook title").grid(row=9, column=0, sticky="w", pady=(10, 2))
        hf = ttk.Frame(c); hf.grid(row=9, column=1, sticky="we", padx=8, pady=(10, 2)); hf.columnconfigure(1, weight=1)
        hp = self.pick(hf, o["hook_mode"], HOOK_NAMES, 26); hp.grid(row=0, column=0, sticky="w")
        self.tip(hp, "What the big title at the start of each Short says.\nSmart: the punchiest line of the clip, as a teaser.\nThe first words said: the first few words of the clip.\n"
                     "My own text: your words on every clip.")
        self.hook_entry = ttk.Entry(hf, textvariable=o["hook_text"]); self.hook_entry.grid(row=0, column=1, sticky="we", padx=(8, 0))
        self.tip(self.hook_entry, "Your own hook. Write several lines with | between them and the clips take turns, e.g.  WAIT FOR IT | she did NOT expect this")
        o["hook_mode"].trace_add("write", lambda *a: self.hook_state()); self.hook_state()
        ttk.Label(c, text="Turn the title on or off with 🪝 Hook title in the Effects tab. For your own text, write several lines with | between them and the clips take turns.",
                  style="Mute.TLabel", wraplength=640, justify="left").grid(row=10, column=0, columnspan=2, sticky="w", pady=(2, 0))

    def hook_state(self):
        try: self.hook_entry.state(["!disabled"] if self.o["hook_mode"].get() == "mine" else ["disabled"])
        except Exception: pass

    def build_emotes(self, x):
        o = self.o; x.columnconfigure(1, weight=1); ve_ = EM()
        self.head(x, "\U0001F3AD Chibi emotes for story time", 0)
        ec = ttk.Checkbutton(x, text="Show my chibi emotes while I tell a story", variable=o["emotes"]); ec.grid(row=1, column=0, columnspan=3, sticky="w")
        self.tip(ec, "The app reads what you say, finds the feeling of each sentence and shows the matching picture of your model while you talk about it.")
        ttk.Label(x, text="The app reads what you say and finds the feeling in each sentence: \u201cI was so scared\u201d shows your scared chibi, \u201chahaha\u201d your laughing one, "
                          "a long silence your blank stare. It understands \u201cnot scared\u201d (no picture), keeps pictures from piling up, and never needs the internet. "
                          "You can check and change the plan before the video is made.", style="Mute.TLabel", wraplength=650, justify="left").grid(row=2, column=0, columnspan=3, sticky="w", pady=(3, 8))
        ttk.Label(x, text="How many").grid(row=3, column=0, sticky="w", pady=3)
        self.tip(self.pick(x, o["emote_level"], {k: v_["label"] for k, v_ in ve_.LEVELS.items()}, 24), "Only the big moments = about 3 a minute, Balanced = about 6, Lots = about 10.").grid(row=3, column=1, sticky="w", padx=8)
        ttk.Label(x, text="Size").grid(row=4, column=0, sticky="w", pady=3)
        sz = ttk.Frame(x); sz.grid(row=4, column=1, sticky="w", padx=8)
        self.spin(sz, o["emote_size"], 12, 60, 2, 5).pack(side="left"); ttk.Label(sz, text="% of the video width", style="Mute.TLabel").pack(side="left", padx=6)
        ttk.Label(x, text="Where").grid(row=5, column=0, sticky="w", pady=3)
        self.pick(x, o["emote_pos"], dict(ve_.POSITIONS), 30).grid(row=5, column=1, sticky="w", padx=8)
        cb = ttk.Checkbutton(x, text="\u270e Let me check and change the emote plan before the videos render", variable=o["emote_review"]); cb.grid(row=6, column=1, columnspan=2, sticky="w", padx=8, pady=(6, 0))
        self.tip(cb, "A window lists every picture the app plans, at which second and why. You can change the feeling or picture, move it, remove it or add one.")
        ttk.Checkbutton(x, text="Use them in Recap videos too", variable=o["emote_recap"]).grid(row=7, column=1, columnspan=2, sticky="w", padx=8)
        bc = ttk.Checkbutton(x, text="Also react to loud moments when nobody said a feeling", variable=o["emote_burst"]); bc.grid(row=8, column=1, columnspan=2, sticky="w", padx=8)
        self.tip(bc, "Good for gameplay: on a loud peak the app shows shocked, laughing, celebrating, scared or another reaction picture. Off by default for story time.")
        cc = ttk.Checkbutton(x, text="Put the clip's strongest feeling on the cover picture", variable=o["emote_cover"]); cc.grid(row=9, column=1, columnspan=2, sticky="w", padx=8)
        self.tip(cc, "The cover picture (.jpg) gets the picture of your model for the strongest feeling in that clip, next to the title.")
        self.head(x, "\U0001F5BC My pictures", 10)
        self.emote_note = tk.StringVar(); ttk.Label(x, textvariable=self.emote_note, style="Mute.TLabel", wraplength=650, justify="left").grid(row=11, column=0, columnspan=3, sticky="w")
        br = ttk.Frame(x); br.grid(row=12, column=0, columnspan=3, sticky="w", pady=(6, 0))
        ttk.Button(br, text="\U0001F3AD My emotes\u2026", style="Accent.TButton", command=self.open_emotes).pack(side="left")
        ttk.Button(br, text="\u270e Try a sentence\u2026", command=self.open_emotes).pack(side="left", padx=6)
        ttk.Button(br, text="\U0001F4C1 Open my emote folder", command=lambda: (os.makedirs(EM().USER_DIR, exist_ok=True), open_path(EM().USER_DIR))).pack(side="left")
        self.emote_summary()

    def emote_summary(self):
        try:
            ve_ = EM(); lib = ve_.load(); by = ve_.by_feeling(lib); n = sum(1 for e in lib if not e.hidden and e.tags)
            miss = [ve_.label_of(k) for k in ve_.CORE if not by.get(k)]
            if not lib: txt = "You haven't added any chibi pictures yet. Press “My emotes…” and add your own - the app shows them when your story matches a feeling."
            else: txt = (f"{n} picture{'s' if n != 1 else ''} ready, covering {len(ve_.CORE) - len(miss)} of the {len(ve_.CORE)} main feelings. "
                   + ("Without a picture yet: " + ", ".join(miss) + "." if miss else "Every main feeling has a picture!"))
        except Exception as e: txt = "I couldn't read the emote folder (" + str(e)[:60] + ")."
        if hasattr(self, "emote_note"): self.emote_note.set(txt)
        if hasattr(self, "qe_note"):
            try: self.qe_note.set("" if EM().load() else "🎭 You haven't added any chibi pictures yet. Open “Show all options” → Chibi emotes → My emotes… to add yours.")
            except Exception: self.qe_note.set("")
        sp_ = getattr(self, "sprites", None) or {}
        for k_ in [k_ for k_ in sp_ if k_[0] == "mine"]: del sp_[k_]        # the "my emotes" mascot looks at the library again
        return txt

    def open_emotes(self):
        w = getattr(self, "emote_win", None)
        if w is not None:
            try:
                if w.winfo_exists(): w.lift(); return
            except tk.TclError: pass
        self.emote_win = EmoteManager(self)

    def review_emotes(self, clips):
        """Called from the worker thread: show the Check the emotes window and wait for the answer (or for Stop)."""
        box, done = {}, threading.Event()
        def fin(out): box["t"] = out; done.set()
        win = []
        self.ui(lambda: win.append(EmotePlanReview(self, clips, fin)))
        self.q.put("\nWaiting for you to check the emotes\u2026\n"); t0 = time.time()
        while not done.wait(.25):
            if sc.CANCEL.is_set():
                self.ui(lambda: [w.destroy() for w in win if w.winfo_exists()]); break
        self.t0 += time.time() - t0
        sc.check_cancel()
        return box.get("t") or {}

    def build_extras(self, x):
        o = self.o; x.columnconfigure(1, weight=1)
        self.head(x, "🖼 Branding", 0)
        self.frow(x, 1, "Logo (PNG)", "logo", [("Images", "*.png *.jpg *.webp")],
                  lambda f_: (self.pick(f_, o["logo_pos"], CORNER_NAMES, 11).pack(side="left", padx=(6, 0)), ttk.Label(f_, text="size %").pack(side="left", padx=(8, 3)), self.spin(f_, o["logo_size"], 5, 40, 1, 4).pack(side="left")))
        ttk.Label(x, text="@name on the video").grid(row=2, column=0, sticky="w", pady=3)
        ttk.Entry(x, textvariable=o["handle"]).grid(row=2, column=1, sticky="we", padx=8)
        self.pick(x, o["handle_pos"], CORNER_NAMES, 11).grid(row=2, column=2, sticky="w")
        self.head(x, "🎬 Intro, outro & end card", 3)
        self.frow(x, 4, "Intro clip", "intro", [("Video or image", "*.mp4 *.mov *.mkv *.webm *.gif *.png *.jpg")])
        self.frow(x, 5, "Outro clip", "outro", [("Video or image", "*.mp4 *.mov *.mkv *.webm *.gif *.png *.jpg")])
        ttk.Label(x, text="End card text").grid(row=6, column=0, sticky="w", pady=3)
        ce = ttk.Entry(x, textvariable=o["cta"]); ce.grid(row=6, column=1, sticky="we", padx=8); self.tip(ce, "A pill that pops up for the last 2.5 seconds, e.g. “Follow for more ♡”. Leave empty for none.")
        ttk.Label(x, text="intro ≤ 6 s · outro ≤ 8 s · a still image shows for 2.5 s", style="Mute.TLabel").grid(row=7, column=1, sticky="w", padx=8)
        self.head(x, "😀 Stickers & emotes", 8)
        ttk.Label(x, text="Sticker images").grid(row=9, column=0, sticky="w", pady=3)
        ttk.Entry(x, textvariable=o["stickers"]).grid(row=9, column=1, sticky="we", padx=8)
        sf = ttk.Frame(x); sf.grid(row=9, column=2, sticky="w")
        ttk.Button(sf, text="Choose…", command=self.pick_stickers).pack(side="left"); ttk.Button(sf, text="📁", width=3, command=self.pick_sticker_dir).pack(side="left", padx=4)
        ttk.Button(sf, text="✖", width=3, command=lambda: o["stickers"].set("")).pack(side="left")
        ttk.Label(sf, text="size %").pack(side="left", padx=(8, 3)); self.spin(sf, o["sticker_size"], 6, 40, 1, 4).pack(side="left")
        ttk.Label(x, text="PNG / GIF emotes pop up on the big moments (transparent PNGs look best).", style="Mute.TLabel").grid(row=10, column=1, sticky="w", padx=8)
        self.head(x, "🎵 Background music", 11)
        ttk.Label(x, text="Music").grid(row=12, column=0, sticky="nw", pady=3)
        self.music_block(x).grid(row=12, column=1, columnspan=2, sticky="we", padx=8)
        ttk.Checkbutton(x, text="🎚 Lower the music when someone talks (auto-ducking)", variable=o["duck"]).grid(row=13, column=1, sticky="w", padx=8)
        o["music"].trace_add("write", self.music_refresh); self.music_refresh()
        self.head(x, "🎙 Voice & language", 14)
        vc = ttk.Checkbutton(x, text="Clean up my voice (less hiss and hum, steadier volume)", variable=o["voice_clean"]); vc.grid(row=15, column=1, sticky="w", padx=8)
        self.tip(vc, "Removes low rumble, reduces steady background noise and evens out loud and quiet parts. Great for noisy mics.")
        ttk.Label(x, text="🔇 Bleep words").grid(row=16, column=0, sticky="w", pady=3)
        ttk.Entry(x, textvariable=self.v["words"]).grid(row=16, column=1, sticky="we", padx=8); ttk.Label(x, text="comma separated", style="Mute.TLabel").grid(row=16, column=2, sticky="w")
        sw = ttk.Checkbutton(x, text="Also bleep common swear words (English), good for family-friendly channels", variable=o["swears"]); sw.grid(row=17, column=1, columnspan=2, sticky="w", padx=8)
        self.tip(sw, "Swear words are covered with a beep and shown as ****  in the captions, the hook title, the subtitles and the chapter list. "
                     "Whole words only, so names and normal words stay as they are. Your own list above is bleeped too.")
        self.head(x, "🛠 Video fixes", 18)
        fl = ttk.Checkbutton(x, text="Cut out frozen / lagging parts of the stream (keeps picture and sound in sync)", variable=o["fix_lag"]); fl.grid(row=19, column=1, sticky="w", padx=8)
        self.tip(fl, "Stream VODs sometimes have a second or two where the picture stops while the sound goes on. When that happens in a quiet spot, "
                     "the app cuts it out instead of showing a frozen picture. Where someone is talking the picture stays (the sound is kept).")

    def build_post(self, x):
        o = self.o; x.columnconfigure(1, weight=1)
        self.head(x, "📝 Posting help", 0)
        ttk.Checkbutton(x, text="Save title ideas, description & hashtags next to each Short (.txt)", variable=o["post_kit"]).grid(row=1, column=0, columnspan=3, sticky="w")
        ttk.Checkbutton(x, text="Save subtitles (.srt) next to each video", variable=o["srt"]).grid(row=2, column=0, columnspan=3, sticky="w")
        ttk.Checkbutton(x, text="Save a cover picture (.jpg) for each Short: a still from the best moment with its title on top", variable=o["cover"]).grid(row=3, column=0, columnspan=3, sticky="w")
        for r_, (lbl, key) in enumerate((("Channel / name", "channel"), ("Game", "game"), ("Extra hashtags", "tags"))):
            ttk.Label(x, text=lbl).grid(row=4 + r_, column=0, sticky="w", pady=3); ttk.Entry(x, textvariable=o[key]).grid(row=4 + r_, column=1, sticky="we", padx=8)
        ttk.Label(x, text="Each clip also gets a hype score. Find your finished clips, copy their titles and open the upload pages in 🖼 My clips.", style="Mute.TLabel",
                  wraplength=640, justify="left").grid(row=7, column=0, columnspan=3, sticky="w", pady=(10, 0))
        self.build_outputs(x, 8)

    # ----- Recap page -----
    def build_long(self, l):
        v = self.v; l.columnconfigure(0, weight=1)
        hh = ttk.Frame(l); hh.grid(row=0, column=0, columnspan=3, sticky="w"); self.step(hh, "🎞  Recap style").pack_configure(pady=(2, 4))
        self.rcards = tk.Canvas(l, height=84, highlightthickness=0); self.rcards.grid(row=1, column=0, columnspan=3, sticky="we")
        self.rcards.bind("<Configure>", lambda ev: self.draw_rcards()); self.rcards.bind("<Button-1>", self.rcard_click)
        lo = ttk.Frame(l); lo.grid(row=2, column=0, columnspan=3, sticky="w", pady=(10, 0))
        ttk.Label(lo, text="Video length").pack(side="left")
        self.tip(self.spin(lo, v["rmin"], 1, 120), "The shortest the video may be, in minutes.").pack(side="left", padx=(8, 4)); ttk.Label(lo, text="to").pack(side="left")
        self.tip(self.spin(lo, v["rmax"], 1, 180), "The longest the video may be, in minutes. I pick moments until the length lands between the two.").pack(side="left", padx=4)
        ttk.Label(lo, text="minutes").pack(side="left")
        self.rlen_note = tk.StringVar(); ttk.Label(lo, textvariable=self.rlen_note, style="Mute.TLabel").pack(side="left", padx=10)
        sp = ttk.Frame(l); sp.grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(sp, text="Make it as").pack(side="left")
        for key, lbl in SPLIT_NAMES.items(): ttk.Radiobutton(sp, text=lbl, value=key, variable=v["split"]).pack(side="left", padx=(12, 0))
        # --- a series of parts ---
        self.sp_parts = pf = ttk.Frame(l); pf.grid(row=4, column=0, columnspan=3, sticky="w", pady=(6, 0))
        ttk.Radiobutton(pf, text="Split into", value="count", variable=v["psplit"]).pack(side="left")
        self.spin(pf, v["pcount"], 2, 30, width=4).pack(side="left", padx=6); ttk.Label(pf, text="parts of similar length").pack(side="left")
        ttk.Radiobutton(pf, text="or parts of about", value="length", variable=v["psplit"]).pack(side="left", padx=(18, 0))
        self.spin(pf, v["pmin"], 1, 120, width=4).pack(side="left", padx=6); ttk.Label(pf, text="minutes").pack(side="left")
        # --- one video per game / chapter ---
        self.sp_games = gf = ttk.Frame(l); gf.grid(row=4, column=0, columnspan=3, sticky="we", pady=(6, 0)); gf.columnconfigure(0, weight=1)
        g1 = ttk.Frame(gf); g1.grid(row=0, column=0, sticky="w")
        ttk.Label(g1, text="Look for").pack(side="left")
        self.tip(self.pick(g1, v["gsens"], SENS_NAMES, 22), "How easily I decide that a new game or chapter has started. “Different games only” is the careful one; “Every big scene change” finds the most.").pack(side="left", padx=6)
        ttk.Label(g1, text="Parts").pack(side="left", padx=(10, 0))
        self.tip(self.combo(g1, v["gcount"], ["Auto"] + [str(i) for i in range(2, 13)], 6), "Know how many games or chapters there are? Say so and I pick that many of the clearest changes.").pack(side="left", padx=6)
        ttk.Label(g1, text="Shortest part").pack(side="left", padx=(10, 0)); self.spin(g1, v["gmin"], 1, 180, width=4).pack(side="left", padx=6); ttk.Label(g1, text="min").pack(side="left")
        self.find_btn = ttk.Button(g1, text="🔍  Find the games", style="Accent.TButton", command=self.run_games); self.find_btn.pack(side="left", padx=(16, 0))
        tw = ttk.Frame(gf); tw.grid(row=1, column=0, sticky="we", pady=(6, 0))
        cols = (("n", "#", 30, "center"), ("from", "From", 70, "center"), ("to", "To", 70, "center"), ("len", "Length", 70, "center"), ("name", "Name", 190, "w"), ("why", "Found because", 240, "w"))
        self.gtree = ttk.Treeview(tw, columns=[c_[0] for c_ in cols], show="headings", height=5, selectmode="browse")
        for k, h, wd, an in cols: self.gtree.heading(k, text=h); self.gtree.column(k, width=wd, anchor=an, stretch=(k in ("name", "why")))
        gsb = ttk.Scrollbar(tw, orient="vertical", command=self.gtree.yview); self.gtree.configure(yscrollcommand=gsb.set)
        self.gtree.pack(side="left", fill="x", expand=True); gsb.pack(side="right", fill="y")
        self.gtree.bind("<<TreeviewSelect>>", lambda ev: self.games_buttons()); self.gtree.bind("<Double-1>", lambda ev: self.games_rename())
        gb = ttk.Frame(gf); gb.grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.gbtns = []
        for txt, cmd, tp in (("✎ Rename", self.games_rename, "Give this part a name (it is used in the file name)."),
                             ("⇢ Join with next", self.games_merge, "Make this part and the one after it a single part."),
                             ("✂ Cut in two…", self.games_split, "Cut the selected part into two at a time you type."),
                             ("↔ Move start…", self.games_move, "Change the time where the selected part begins (the part before it ends there)."),
                             ("🗑 Remove", self.games_remove, "Leave this part out - no video is made for it.")):
            b_ = self.tip(ttk.Button(gb, text=txt, command=cmd), tp); b_.pack(side="left", padx=(0, 6)); self.gbtns.append(b_)
        self.gnote = tk.StringVar(value=GNOTE_IDLE)
        ttk.Label(gf, textvariable=self.gnote, style="Mute.TLabel", wraplength=640, justify="left").grid(row=3, column=0, sticky="w", pady=(6, 0))
        # --- cut only ---
        self.wf = ttk.Frame(l); self.wf.grid(row=5, column=0, columnspan=3, sticky="w", pady=(6, 0))
        self.tip(ttk.Checkbutton(self.wf, text="Don't make highlights - only cut the whole stream into these parts (very fast, nothing is re-encoded)", variable=self.rwhole),
                 "Good for a full playthrough: every part keeps everything, you get one file per game / chapter. Cuts land on the nearest key frame, so a part can start a second or two early.").pack(side="left")
        self.long_opts = oo = ttk.Frame(l); oo.grid(row=6, column=0, columnspan=3, sticky="w", pady=(6, 0))
        ttk.Checkbutton(oo, text="💬 Captions", variable=self.lcaps).pack(side="left", padx=(0, 22))
        ttk.Checkbutton(oo, text="🎥 Pans", variable=self.lpan).pack(side="left", padx=(0, 22))
        ttk.Checkbutton(oo, text="🎬 Jump-cut zooms", variable=self.lcut).pack(side="left", padx=(0, 22))
        ttk.Checkbutton(oo, text="✂ Trim silences", variable=self.silence).pack(side="left")
        self.rdesc = tk.StringVar(); ttk.Label(l, textvariable=self.rdesc, style="Mute.TLabel", wraplength=640, justify="left").grid(row=7, column=0, columnspan=3, sticky="w", pady=(8, 0))
        hd = ttk.Label(l, text="🎵 Background music", font=(FONT, 10, "bold"), foreground=self.t["accent"]); hd.grid(row=8, column=0, columnspan=3, sticky="w", pady=(12, 3)); self.fxheads.append(hd)
        self.music_block(l).grid(row=9, column=0, columnspan=3, sticky="we")
        ttk.Label(l, text="A recap plays your songs as a playlist with soft cross-fades and turns the music down while you talk. The @name, your logo and subtitles from the Logo & music tab apply to recaps too. "
                          "Stickers, intro / outro and the end card are for Shorts only.",
                  style="Mute.TLabel", wraplength=640, justify="left").grid(row=10, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self.rdesc_set(); self.games_buttons()

    def split_changed(self, *a):
        if not hasattr(self, "sp_parts"): return
        sp = self.v["split"].get(); whole = bool(self.rwhole.get()) and sp != "none"
        for w, show in ((self.sp_parts, sp == "count"), (self.sp_games, sp == "games"), (self.wf, sp != "none"), (self.long_opts, not whole)):
            w.grid() if show else w.grid_remove()
        self.rlen_note.set("(not used - the whole stream is kept)" if whole else
                           {"none": "(the whole video)", "count": "(all parts together)", "games": "(each video - a short game gets a shorter one)"}.get(sp, ""))
        try: self.update_idletasks(); self.scroll.configure(scrollregion=self.scroll.bbox("all"))
        except tk.TclError: pass

    def sens_changed(self, *a):
        k = self.v["gsens"].get()
        if k in sc.GAME_SENS: self.v["gmin"].set(f"{sc.GAME_SENS[k]['min_min']:g}")

    # ----- the list of games / chapters -----
    def fill_games(self, select=None):
        t = self.gtree; t.delete(*t.get_children())
        for i, g in enumerate(self.games):
            t.insert("", "end", iid=str(i), values=(i + 1, sc.hms(g["start"]), sc.hms(g["end"]), f"{(g['end'] - g['start']) / 60:.0f} min", g["name"], g.get("why") or ""),
                     tags=("odd",) if i % 2 else ())
        if select is not None and str(select) in t.get_children(): t.selection_set(str(select))
        self.games_buttons(); self.refresh_ready()

    def games_sel(self):
        s_ = self.gtree.selection()
        return int(s_[0]) if len(s_) == 1 and s_[0].isdigit() and int(s_[0]) < len(self.games) else None

    def games_buttons(self, *a):
        i = self.games_sel()
        for b_, ok in zip(self.gbtns, (i is not None, i is not None and i < len(self.games) - 1, i is not None, i is not None and i > 0, i is not None and len(self.games) > 1)):
            b_.state(["!disabled"] if ok else ["disabled"])

    def need_game(self):
        i = self.games_sel()
        if i is None: messagebox.showinfo("VTuber Clipper", "Click one part in the list first ♡")
        return i

    def games_rename(self):
        i = self.need_game()
        if i is None: return

        def done(vals):
            nm = vals[0].strip()
            if not nm: return "Type a name."
            self.games[i]["name"] = nm[:60]; self.fill_games(select=i)
        AskDialog(self, "Rename", f"Name for part {i + 1} (used in the file name and as a title idea):", [("Name", self.games[i]["name"])], done)

    def games_merge(self):
        i = self.need_game()
        if i is None: return
        if i >= len(self.games) - 1: return messagebox.showinfo("VTuber Clipper", "This is the last part - there is nothing after it to join ♡")
        self.games = sc.games_merge(self.games, i); self.fill_games(select=i)

    def games_split(self):
        i = self.need_game()
        if i is None: return
        g = self.games[i]

        def done(vals):
            t = parse_clock(vals[0])
            if t is None: return "Type a time like 1:23:45 or 45:10."
            if not (g["start"] + 20 < t < g["end"] - 20): return f"The time has to be inside this part ({sc.hms(g['start'])} – {sc.hms(g['end'])}), at least 20 seconds from each end."
            self.games = sc.games_split(self.games, i, t); self.fill_games(select=i + 1)
        AskDialog(self, "Cut in two", f"Cut “{g['name']}” into two parts at this time of the stream ({sc.hms(g['start'])} – {sc.hms(g['end'])}):",
                  [("At", sc.hms((g["start"] + g["end"]) / 2))], done, "✂  Cut")

    def games_move(self):
        i = self.need_game()
        if i is None: return
        if i == 0: return messagebox.showinfo("VTuber Clipper", "The first part always starts at the beginning. Select a later part to move where it starts ♡")
        g, prev = self.games[i], self.games[i - 1]

        def done(vals):
            t = parse_clock(vals[0])
            if t is None: return "Type a time like 1:23:45 or 45:10."
            if not (prev["start"] + 20 < t < g["end"] - 20): return f"The time has to be between {sc.hms(prev['start'] + 20)} and {sc.hms(g['end'] - 20)}."
            g["start"] = prev["end"] = float(t); self.fill_games(select=i)
        AskDialog(self, "Move start", f"Where does “{g['name']}” begin? (now {sc.hms(g['start'])})", [("Starts at", sc.hms(g["start"]))], done)

    def games_remove(self):
        i = self.need_game()
        if i is None: return
        if len(self.games) < 2: return messagebox.showinfo("VTuber Clipper", "At least one part has to stay ♡")
        del self.games[i]; self.fill_games(select=min(i, len(self.games) - 1))

    def show_games(self, g, video):
        self.games, self.games_video = g, video; self.fill_games()
        n = len(g)
        self.gnote.set(f"I found {n} parts. Check the list: rename, join, cut a part in two or move where one starts - then press the big button ♡" if n > 1 else
                       "I only found one part. Try “Every big scene change”, tell me how many parts there are, or cut it yourself with “✂ Cut in two…”.")

    # ----- Best moments page -----
    def build_moments(self, m):
        v = self.v
        hh = ttk.Frame(m); hh.pack(fill="x"); self.step(hh, "🔎  Best moments").pack_configure(pady=(2, 4))
        mc = ttk.Frame(m); mc.pack(fill="x")
        ttk.Label(mc, text="How many").pack(side="left"); self.spin(mc, v["mn"], 3, 50).pack(side="left", padx=(6, 18))
        ttk.Label(mc, text="Moment length").pack(side="left")
        self.spin(mc, v["mlo"], 10, 120).pack(side="left", padx=6); ttk.Label(mc, text="to").pack(side="left"); self.spin(mc, v["mhi"], 10, 120).pack(side="left", padx=6)
        ttk.Label(mc, text="seconds", style="Mute.TLabel").pack(side="left")
        mq = ttk.Frame(m); mq.pack(fill="x", pady=(6, 0))
        ttk.Label(mq, text="🔍 Find by words").pack(side="left"); ttk.Entry(mq, textvariable=v["mq"], width=40).pack(side="left", padx=8)
        ttk.Label(mq, text="optional, e.g. “jump scare, thank you”", style="Mute.TLabel").pack(side="left")
        ttk.Label(m, text="Saying “clip that” on stream is always found, whatever you type here.", style="Mute.TLabel").pack(anchor="w", pady=(2, 0))
        tw = ttk.Frame(m); tw.pack(fill="x", pady=(8, 0))
        cols = (("n", "#", 36, "center"), ("time", "Time", 76, "center"), ("len", "Length", 62, "center"), ("rate", "Rating", 104, "w"), ("what", "What's happening", 380, "w"))
        self.tree = ttk.Treeview(tw, columns=[c_[0] for c_ in cols], show="headings", height=8, selectmode="extended")
        for k, h, wd, an in cols: self.tree.heading(k, text=h); self.tree.column(k, width=wd, anchor=an, stretch=(k == "what"))
        tsb = ttk.Scrollbar(tw, orient="vertical", command=self.tree.yview); self.tree.configure(yscrollcommand=tsb.set)
        self.tree.pack(side="left", fill="x", expand=True); tsb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", lambda ev: self.mom_buttons()); self.tree.bind("<Double-1>", lambda ev: self.trim_selected())
        mb = ttk.Frame(m); mb.pack(fill="x", pady=(8, 0))
        self.mbtns = [ttk.Button(mb, text="📋 Copy timestamps", command=self.copy_moments), ttk.Button(mb, text="💾 Save as .txt", command=self.save_moments)]
        for b_ in self.mbtns: b_.pack(side="left", padx=(0, 6))
        ttk.Label(mb, text="Sort").pack(side="left", padx=(8, 4)); sc_ = self.combo(mb, v["msort"], ["Best first", "In stream order"], 14); sc_.pack(side="left")
        v["msort"].trace_add("write", lambda *a: self.fill_moments())
        self.moments_extras(mb)
        mb2 = ttk.Frame(m); mb2.pack(fill="x", pady=(8, 0))
        self.trim_btn = self.tip(ttk.Button(mb2, text="✎ Trim…", command=self.trim_selected), "Fine-tune where the selected moment starts and ends (double-click a row works too).")
        self.trim_btn.pack(side="left", padx=(0, 6))
        ttk.Button(mb2, text="＋ Add my own moment", command=self.add_moment).pack(side="left", padx=(0, 6))
        ttk.Button(mb2, text="📋 Paste timestamps", command=self.paste_moments).pack(side="left", padx=(0, 6))
        ttk.Button(mb2, text="🗑 Remove", command=self.remove_moments).pack(side="left")
        self.mk_btn = ttk.Button(mb2, text="🎬 Make Shorts from selected", style="Accent.TButton", command=self.make_from_moments); self.mk_btn.pack(side="right")
        self.mnote = tk.StringVar(value="I scan the whole VOD and list where the best parts are — nothing is rendered. Press “Find best moments” on the left ♡  You can also add your own moments or paste a list of times.")
        ttk.Label(m, textvariable=self.mnote, style="Mute.TLabel", wraplength=700, justify="left").pack(anchor="w", pady=(8, 0))
        self.mom_buttons()

    # ----- My clips page -----
    def build_clips(self, P):
        hr = ttk.Frame(P); hr.pack(fill="x")
        self.step(hr, "🖼  My clips").pack_configure(side="left", pady=(2, 4))
        ttk.Button(hr, text="🔄 Refresh", command=self.refresh_clips).pack(side="right")
        ttk.Button(hr, text="📂 Open folder", command=self.open_out).pack(side="right", padx=6)
        self.clip_filter_bar(hr); self.clips_extras(hr)
        self.clips_note = tk.StringVar(); ttk.Label(P, textvariable=self.clips_note, style="Mute.TLabel", wraplength=700, justify="left").pack(anchor="w", pady=(0, 6))
        self.clip_grid = ttk.Frame(P); self.clip_grid.pack(fill="x")

    def cam_row(self, p):
        f = ttk.Frame(p)
        ttk.Entry(f, textvariable=self.v["cam"], width=16, state="readonly").pack(side="left")
        self.auto_btn = ttk.Button(f, text="🪄 Find it for me", style="Accent.TButton", command=self.auto_cam); self.auto_btn.pack(side="left", padx=6)
        self.auto_btns = getattr(self, "auto_btns", []) + [self.auto_btn]
        self.tip(self.auto_btn, "Looks through the video for the box where your facecam / model sits. It's a best guess - you can check and adjust it right after.")
        sel = ttk.Button(f, text="🎯 Select area", command=self.pick_cam); sel.pack(side="left"); self.tip(sel, "Draw the cam box yourself on a frame of the video.")
        ttk.Button(f, text="✖", width=3, command=lambda: self.v["cam"].set("")).pack(side="left", padx=(6, 0))
        return f

    def auto_cam(self):
        p = self.v["video"].get().strip().strip('"')
        if not os.path.isfile(p): return messagebox.showinfo("VTuber Clipper", "Pick or download a video first, then I can look for your cam ♡")
        if getattr(self, "finding_cam", False): return
        self.finding_cam = True; self.status.set("Looking for your cam…"); [b.state(["disabled"]) for b in self.auto_btns]

        def go():
            try: cam = sc.find_cam(p)
            except Exception as e: cam = None; self.q.put(f"\n(cam finder: {str(e)[:100]})\n")
            self.ui(lambda: self.cam_found(p, cam))
        threading.Thread(target=go, daemon=True).start()

    def cam_found(self, p, cam):
        self.finding_cam = False; [b.state(["!disabled"]) for b in self.auto_btns]
        if not self.busy: self.status.set("Found something - please check the box ♡" if cam else "Ready ✿")
        info = sc.probe_info(p)
        if not info["w"]: return
        hint = ("🪄 Here's my best guess for your cam. Check it, adjust if needed (drag inside to move, corners to resize), then press “Use this area”." if cam else
                "🪄 I couldn't spot a cam box in this video. Drag a box around your model / facecam yourself.")
        CamPicker(self, p, info["dur"] or 60, info["w"], info["h"], cam or self.v["cam"].get(), self.v["cam"].set, hint)

    def toggle_log(self, show=None):
        show = (not self.logf.winfo_ismapped()) if show is None else show
        if show: self.logf.pack(side="bottom", fill="x", before=self.main)
        else: self.logf.pack_forget()
        self.det_btn.configure(text="▾ Details" if show else "▸ Details")

    def browse_video(self):
        ps = filedialog.askopenfilenames(title="Pick a VOD (select several to make clips from all of them)",
                                         filetypes=[("Videos", "*.mp4 *.mkv *.mov *.webm *.ts *.flv *.avi"), ("All files", "*.*")])
        if ps:
            self.batch = list(ps) if len(ps) > 1 else []
            self.v["video"].set(ps[0]); self.batch_check()

    def batch_check(self):
        """Keep the 'several VODs' list only while the video box still shows its first file."""
        if self.batch and self.v["video"].get().strip().strip('"') != self.batch[0]: self.batch = []
        many = len(self.batch) > 1
        self.batch_note.set(f"📚 {len(self.batch)} VODs queued — Shorts / recaps are made from each one" if many else "")
        if many: self.qbtn.pack(side="left", padx=(6, 0)); self.batch_lbl.pack(anchor="w", after=self.qbtn.master)
        else: self.qbtn.pack_forget(); self.batch_lbl.pack_forget()
        self.after_idle(self.fit_left)

    def clear_queue(self): self.batch = []; self.batch_check()

    def videos(self):
        p = self.v["video"].get().strip().strip('"')
        return [x for x in (self.batch if len(self.batch) > 1 else [p]) if os.path.isfile(x)]

    def dropped(self, paths):
        vids = [p for p in paths if os.path.isfile(p) and p.lower().endswith(VIDEO_EXT)]
        if not vids: return self.status.set("That doesn't look like a video file ♡")
        self.batch = vids if len(vids) > 1 else []
        self.v["video"].set(vids[0]); self.batch_check()

    def enable_dnd(self):
        """Drop video files onto the window (Windows only; if the last start-up with this didn't finish cleanly, it stays off)."""
        if not sys.platform.startswith("win"): return
        mark = os.path.join(HOME, ".vtuberclipper_dnd_check")
        if os.path.exists(mark): return
        try:
            open(mark, "w").close()
            import ctypes
            from ctypes import wintypes
            user32, shell32 = ctypes.windll.user32, ctypes.windll.shell32
            WM_DROPFILES, GWLP_WNDPROC, LRESULT = 0x0233, -4, ctypes.c_ssize_t
            WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
            user32.SetWindowLongPtrW.restype = ctypes.c_void_p; user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
            user32.CallWindowProcW.restype = LRESULT
            user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            shell32.DragQueryFileW.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT]; shell32.DragFinish.argtypes = [wintypes.HANDLE]
            hwnd, old = self.winfo_id(), [None]

            def proc(h, msg, wp, lp):
                try:
                    if msg == WM_DROPFILES:
                        n, paths = shell32.DragQueryFileW(wp, 0xFFFFFFFF, None, 0), []
                        for i in range(n):
                            buf = ctypes.create_unicode_buffer(1024); shell32.DragQueryFileW(wp, i, buf, 1024); paths.append(buf.value)
                        shell32.DragFinish(wp); self.q.put(lambda: self.dropped(paths)); return 0
                except Exception: pass
                return user32.CallWindowProcW(old[0], h, msg, wp, lp)
            self._dnd_proc = WNDPROC(proc)                       # keep a reference so it is not garbage collected
            old[0] = user32.SetWindowLongPtrW(hwnd, GWLP_WNDPROC, ctypes.cast(self._dnd_proc, ctypes.c_void_p))
            shell32.DragAcceptFiles(hwnd, True)
            self.after(6000, lambda: os.path.exists(mark) and os.remove(mark))
        except Exception:
            try: os.remove(mark)
            except OSError: pass

    def apply_theme(self):
        s, t = self.style, THEMES[self.v["theme"].get()]; self.t = t
        self.configure(bg=t["bg"])
        s.configure(".", background=t["bg"], foreground=t["fg"], fieldbackground=t["entry"], bordercolor=t["entry"],
                    lightcolor=t["entry"], darkcolor=t["entry"], troughcolor=t["entry"], font=(FONT, 10))
        s.configure("Mute.TLabel", foreground=t["mute"])
        s.configure("TButton", background=t["entry"], foreground=t["fg"], padding=6, borderwidth=0)
        s.map("TButton", background=[("active", t["accent2"]), ("disabled", t["bg"])], foreground=[("active", t["on"]), ("disabled", t["mute"])])
        s.configure("Accent.TButton", background=t["accent"], foreground=t["on"], padding=7, font=(FONT, 10, "bold"))
        s.map("Accent.TButton", background=[("active", deep(t["accent"]))], foreground=[("active", t["on"])])
        s.configure("Big.TButton", background=t["accent"], foreground=t["on"], padding=(22, 11), font=(FONT, 13, "bold"))
        s.map("Big.TButton", background=[("active", deep(t["accent"])), ("disabled", t["entry"])], foreground=[("disabled", t["mute"])])
        for w in ("TEntry", "TSpinbox", "TCombobox"):
            s.configure(w, fieldbackground=t["entry"], foreground=t["fg"], insertcolor=t["fg"], arrowcolor=t["fg"], background=t["entry"])
        s.map("TCombobox", fieldbackground=[("readonly", t["entry"])], foreground=[("readonly", t["fg"])], selectbackground=[("readonly", t["entry"])], selectforeground=[("readonly", t["fg"])])
        s.configure("TNotebook", background=t["bg"], borderwidth=0)
        s.configure("TNotebook.Tab", background=t["entry"], foreground=t["mute"], padding=(12, 7), font=(FONT, 10, "bold"))
        s.map("TNotebook.Tab", background=[("selected", t["accent"])], foreground=[("selected", t["on"])])
        for w in ("TCheckbutton", "TRadiobutton"):
            s.configure(w, background=t["bg"], foreground=t["fg"]); s.map(w, background=[("active", t["bg"])])
        trough = mix(t["entry"], t["accent2"], .25)
        s.configure("Horizontal.TScale", background=t["accent"], troughcolor=trough, bordercolor=trough, lightcolor=t["accent"], darkcolor=t["accent"])
        s.map("Horizontal.TScale", background=[("active", deep(t["accent"]))])
        s.configure("Vertical.TScrollbar", background=t["accent2"], troughcolor=t["entry"], arrowcolor=t["on"], bordercolor=t["entry"],
                    lightcolor=t["accent2"], darkcolor=t["accent2"])
        s.map("Vertical.TScrollbar", background=[("disabled", t["entry"]), ("active", t["accent"])], arrowcolor=[("disabled", t["entry"])],
              lightcolor=[("disabled", t["entry"])], darkcolor=[("disabled", t["entry"])])
        s.configure("Treeview", background=t["panel"], fieldbackground=t["panel"], foreground=t["fg"], rowheight=26, bordercolor=t["entry"],
                    lightcolor=t["panel"], darkcolor=t["panel"], font=(FONT, 10))
        s.map("Treeview", background=[("selected", t["accent"])], foreground=[("selected", t["on"])])
        s.configure("Treeview.Heading", background=t["accent2"], foreground="#ffffff", relief="flat", font=(FONT, 10, "bold"), padding=5, bordercolor=t["accent2"],
                    lightcolor=t["accent2"], darkcolor=t["accent2"])
        s.map("Treeview.Heading", background=[("active", deep(t["accent2"]))])
        self.tree.tag_configure("odd", background=mix(t["panel"], t["accent2"], .10)); self.gtree.tag_configure("odd", background=mix(t["panel"], t["accent2"], .10))
        for h in self.fxheads: h.configure(foreground=t["accent"])
        self.log.configure(bg=t["entry"], fg=t["fg"], insertbackground=t["fg"])
        for lb_ in getattr(self, "bg_labels", []):
            try: lb_.configure(bg=t["bg"])
            except tk.TclError: pass
        for tb in getattr(self, "texts", []):
            try: tb.configure(bg=t["entry"], fg=t["fg"], insertbackground=t["fg"])
            except tk.TclError: pass
        self.option_add("*TCombobox*Listbox.background", t["entry"]); self.option_add("*TCombobox*Listbox.foreground", t["fg"])
        self.option_add("*TCombobox*Listbox.selectBackground", t["accent"]); self.option_add("*TCombobox*Listbox.selectForeground", t["on"])
        for cb in self.combos:                      # already-created drop-downs keep their old colours unless updated directly
            try:
                lb = self.tk.call("ttk::combobox::PopdownWindow", str(cb)) + ".f.l"
                self.tk.call(lb, "configure", "-background", t["entry"], "-foreground", t["fg"], "-selectbackground", t["accent"], "-selectforeground", t["on"])
            except Exception: pass
        for c in (self.banner, self.gal, self.rcards, self.badge, self.scroll, self.vthumb) + tuple(h[0] for h in self.heads): c.configure(bg=t["bg"])
        self.bar.theme(t)
        if self.sw and self.sw.winfo_exists():
            self.sw.configure(bg=t["bg"]); self.sw_canvas.configure(bg=t["bg"]); self.draw_swatches()
        self.draw_banner(); self.draw_gallery(); self.draw_rcards(); self.draw_badge(); self.paint_swatches(); self.draw_vthumb()
        for p_ in self.pills: p_.draw()
        f = tkfont.Font(family=FONT, size=11, weight="bold")
        for c, text in self.heads:
            w = f.measure(text) + 42
            c.configure(width=w); c.delete("all"); rrect(c, 2, 2, w - 2, 30, 14, fill=deep(t["accent2"]), outline="")
            c.create_text(18, 16, text=text, anchor="w", font=(FONT, 11, "bold"), fill="#ffffff")

    # ---------- graphics ----------
    def draw_banner(self):
        c, t = self.banner, self.t; c.delete("all"); w = max(c.winfo_width(), 900); H = BANNER_H
        for i in range(0, w, 6): c.create_rectangle(i, 0, i + 6, H, fill=mix(t["accent"], t["accent2"], i / w), outline="")
        light = mix(t["accent2"], "#ffffff", .55)
        self.parts = [dict(x=random.uniform(100, w - 200), y=random.uniform(0, H), v=random.uniform(.2, .6), ph=random.uniform(0, 6)) for _ in range(12)]
        for p in self.parts:
            p["it"] = c.create_text(p["x"], p["y"], text=random.choice(GLYPHS), fill=random.choice(("#ffffff", light)), font=("Segoe UI Symbol", random.choice((9, 11, 13, 15))))
        sh = deep(t["accent"])
        self.mitem = c.create_image(8, H, anchor="sw", tags="sprite")                      # the chibi mascot; tick() swaps her picture
        c.create_text(97, 39, text="VTuber Clipper ♡", anchor="w", font=("Segoe Print", 19, "bold"), fill=sh)
        c.create_text(95, 37, text="VTuber Clipper ♡", anchor="w", font=("Segoe Print", 19, "bold"), fill="#ffffff")
        if BETA:
            if self.title_font is None: self.title_font = tkfont.Font(family="Segoe Print", size=19, weight="bold")
            bx = 95 + self.title_font.measure("VTuber Clipper ♡") + 12
            rrect(c, bx, 24, bx + 52, 46, 11, fill="#ffffff", outline=""); c.create_text(bx + 26, 35, text="BETA", font=(FONT, 9, "bold"), fill=deep(t["accent"]))
        c.create_text(97, 61, text="Kick · Twitch · YouTube  →  Shorts, Recaps & Best moments ✧", anchor="w", font=(FONT, 8, "bold"), fill="#ffffff")
        rrect(c, 470, 25, 860, 59, 15, fill="#ffffff", outline=""); c.create_polygon(470, 41, 456, 44, 472, 49, fill="#ffffff", outline="")
        self.btxt = c.create_text(486, 42, text="", anchor="w", font=(FONT, 10, "bold"), fill="#5a3550")
        c.create_window(w - 14, H // 2 - 19, window=self.setbtn, anchor="e")
        c.create_window(w - 14, H // 2 + 19, window=self.toolbtn, anchor="e")

    def mascot_kind(self):
        """Which costume she wears: the theme's own ('Match theme') or the one picked in Settings."""
        m = MASCOT_KIND.get(self.v["mascot"].get(), "match")
        return self.t.get("mascot", "plain") if m == "match" else m

    def sprite(self, kind, mood):
        """One of her pictures (assets in app/mascot/); None when the file is missing so the old drawn mascot takes over."""
        key = (kind, mood)
        if key not in self.sprites:
            img = None
            try:
                if kind == "mine": img = self.my_sprite(mood)
                else: img = tk.PhotoImage(file=os.path.join(APP_DIR, "mascot", f"{kind}_{mood}.png"))
            except Exception: img = None
            self.sprites[key] = img
        return self.sprites[key]

    def my_sprite(self, mood):
        """'Chibi: my emotes': the first feeling of this mood that has a picture in the emote library (blinking = the idle picture)."""
        ve_ = EM(); by = ve_.by_feeling()
        for f in MY_MASCOT["idle" if mood == "blink" else mood]:
            if by.get(f):
                pics = by[f]; e = pics[0] if mood != "oops" else pics[random.randrange(len(pics))]
                return tk.PhotoImage(file=ve_.thumb(e.path, 84))
        return None

    def mascot_mood(self):
        k = self.frame
        if self.busy: return "work"
        if self.failed: return "oops"
        if self.done and k < self.cheer_until or k < self.quip_until: return "happy"
        if k % 310 < 7: return "happy"                      # now and then she winks
        return "blink" if k % 55 < 3 else "idle"

    def poke_mascot(self, e):
        if e.x < 92 and not self.busy and not self.failed:
            self.quip, self.quip_until = random.choice([q for q in QUIPS if q != self.quip]), self.frame + 40

    def draw_sprite(self):
        """Her picture for the current mood. Returns False if there is no picture, so tick() draws the classic mascot instead."""
        kind, mood, k = self.mascot_kind(), self.mascot_mood(), self.frame
        if kind == "classic" or self.mitem is None: return False
        if mood == "work" and kind in ("angel", "devil") and (k // 4) % 2: mood = "work_b"        # the wings flap while she works
        img = self.sprite(kind, mood) or self.sprite(kind, "idle") or self.sprite("plain", "idle")
        if img is None: return False
        bob = 2.5 + 2.5 * math.sin(k * (.45 if self.busy else .13))
        self.banner.itemconfigure(self.mitem, image=img); self.banner.coords(self.mitem, 8, BANNER_H + bob)
        return True

    def draw_mascot(self, cx, cy, busy, blink, kind=None, tag="mascot", canvas=None):
        """The little banner VTuber. Every variant shares the same face; ears / hat / wings change with the theme."""
        c, t, k = canvas or self.banner, self.t, self.frame; c.delete(tag); kind = kind or self.mascot_kind()
        by, wg = cy + 3 * math.sin(k * .13), (3 * math.sin(k * .6) if busy else 0)
        hair, skin, a, W = t["accent2"], "#fff6f0", t["accent"], "#ffffff"
        dark, pink = "#4a3358", "#ffd1e3"
        poly = lambda pts, **kw: c.create_polygon(pts, tags=tag, **kw)
        oval = lambda x1, y1, x2, y2, **kw: c.create_oval(x1, y1, x2, y2, tags=tag, **kw)
        if kind == "angel":                                                         # little wings behind
            for s_ in (-1, 1): oval(cx + s_ * 62 - 22, by - 8 + wg, cx + s_ * 62 + 22, by + 34 + wg, fill=W, outline=pink, width=2)
        if kind == "devil":
            for s_ in (-1, 1): poly([cx + s_ * 34, by + 2, cx + s_ * 74, by - 22 + wg, cx + s_ * 58, by + 8, cx + s_ * 70, by + 30, cx + s_ * 40, by + 22], fill=deep(a), outline=W, width=2)
        if kind == "ghost":                                                         # a sheet with a wavy hem
            oval(cx - 46, by - 50, cx + 46, by + 40, fill=W, outline=pink, width=2)
            for j in range(5): oval(cx - 46 + j * 18.4, by + 26, cx - 27.6 + j * 18.4, by + 52 + (4 if j % 2 else 0), fill=W, outline=pink, width=2)
            oval(cx - 44, by + 22, cx + 44, by + 38, fill=W, outline="")
        elif kind != "robot":                                                       # twin tails
            for s_ in (-1, 1): oval(cx + s_ * 38 - 11, by + 2, cx + s_ * 38 + 11, by + 46, fill=hair, outline=W, width=2)
        if kind == "cat":
            for s_ in (-1, 1):
                poly([cx + s_ * 12, by - 28, cx + s_ * 40 + wg * s_, by - 54, cx + s_ * 38, by - 14], fill=a, outline=W, width=2)
                poly([cx + s_ * 19, by - 27, cx + s_ * 36 + wg * s_, by - 44, cx + s_ * 34, by - 18], fill=pink, outline="")
        elif kind == "bunny":
            for s_ in (-1, 1):
                poly([cx + s_ * 12, by - 24, cx + s_ * 26 + wg * s_, by - 44, cx + s_ * 34 + wg * s_, by - 78, cx + s_ * 22 + wg * s_, by - 82, cx + s_ * 8, by - 44], fill=a, outline=W, width=2, smooth=True)
                poly([cx + s_ * 15, by - 30, cx + s_ * 25 + wg * s_, by - 46, cx + s_ * 28 + wg * s_, by - 70, cx + s_ * 21 + wg * s_, by - 72, cx + s_ * 12, by - 46], fill=pink, outline="", smooth=True)
        elif kind == "fox":
            for s_ in (-1, 1):
                poly([cx + s_ * 8, by - 28, cx + s_ * 38 + wg * s_, by - 66, cx + s_ * 42, by - 12], fill=a, outline=W, width=2)
                poly([cx + s_ * 18, by - 28, cx + s_ * 37 + wg * s_, by - 52, cx + s_ * 36, by - 18], fill="#fff1dc", outline="")
                poly([cx + s_ * 30 + wg * s_, by - 56, cx + s_ * 38 + wg * s_, by - 66, cx + s_ * 40, by - 48], fill=dark, outline="")
        elif kind == "devil":
            for s_ in (-1, 1): poly([cx + s_ * 16, by - 28, cx + s_ * 34 + wg * s_, by - 62, cx + s_ * 34, by - 22], fill="#ff3b5c", outline=W, width=2)
        elif kind == "robot":
            c.create_line(cx, by - 32, cx, by - 60, width=3, fill="#9aa4c4", tags=tag); oval(cx - 6, by - 68 + wg, cx + 6, by - 56 + wg, fill=a, outline=W, width=2)
            for s_ in (-1, 1): c.create_rectangle(cx + s_ * 42 - 6, by - 6, cx + s_ * 42 + 6, by + 22, fill="#9aa4c4", outline=W, width=2, tags=tag)
        # head + hair
        oval(cx - 36, by - 32, cx + 36, by + 34, fill="#e6ebf7" if kind == "robot" else skin, outline=W, width=2)
        if kind != "ghost":
            c.create_arc(cx - 38, by - 40, cx + 38, by + 32, start=0, extent=180, fill=("#9aa4c4" if kind == "robot" else hair), outline="", tags=tag)
            for dx in (-26, -9, 9, 26): poly([cx + dx - 9, by - 8, cx + dx + 9, by - 8, cx + dx, by + 8], fill=("#9aa4c4" if kind == "robot" else hair), outline="")
        if kind == "witch":                                                         # pointed hat sitting on the head
            c.create_oval(cx - 58, by - 36, cx + 58, by - 20, fill=deep(a), outline=W, width=2, tags=tag)
            poly([cx - 34, by - 30, cx + 6 + wg, by - 92, cx + 36, by - 30], fill=deep(a), outline=W, width=2)
            c.create_rectangle(cx - 33, by - 40, cx + 34, by - 30, fill=hair, outline="", tags=tag)
            oval(cx + 6, by - 42, cx + 18, by - 30, fill="#ffd166", outline="")
        if kind == "angel": c.create_oval(cx - 26, by - 66 + wg, cx + 26, by - 46 + wg, outline="#ffd24d", width=5, tags=tag)
        for s_ in (-1, 1):
            ex = cx + s_ * 15
            if blink: c.create_line(ex - 8, by + 14, ex + 8, by + 14, width=3, fill=dark, tags=tag)
            else:
                oval(ex - 8, by + 6, ex + 8, by + 24, fill=("#2b6cff" if kind == "robot" else dark), outline="")
                oval(ex - 4, by + 8, ex + 2, by + 14, fill=W, outline=""); oval(ex + 1, by + 17, ex + 5, by + 21, fill=pink, outline="")
            oval(cx + s_ * 25 - 7, by + 22, cx + s_ * 25 + 7, by + 31, fill="#ffb3cf", outline="")
        if kind == "fox":
            for s_ in (-1, 1):
                for j in (-3, 3): c.create_line(cx + s_ * 30, by + 27 + j, cx + s_ * 44, by + 27 + j * 2, width=1, fill=dark, tags=tag)
        if busy: oval(cx - 4, by + 25, cx + 4, by + 33, fill="#ff7a9e", outline="")
        elif kind == "robot": c.create_rectangle(cx - 7, by + 25, cx + 7, by + 30, fill="#c2547c", outline="", tags=tag)
        elif kind == "devil":
            c.create_arc(cx - 7, by + 20, cx + 7, by + 32, start=200, extent=140, style="arc", outline="#c2547c", width=2, tags=tag)
            for s_ in (-1, 1): poly([cx + s_ * 5, by + 28, cx + s_ * 8, by + 28, cx + s_ * 6.5, by + 33], fill=W, outline="")
        else: c.create_arc(cx - 7, by + 20, cx + 7, by + 32, start=200, extent=140, style="arc", outline="#c2547c", width=2, tags=tag)
        if kind in ("cat", "bunny", "angel"):                                       # bow
            poly([cx - 40, by - 24, cx - 54, by - 32, cx - 54, by - 14], fill=a, outline=W); poly([cx - 40, by - 24, cx - 26, by - 32, cx - 26, by - 14], fill=a, outline=W)
            oval(cx - 44, by - 28, cx - 36, by - 20, fill=W, outline="")

    def tick(self):
        self.frame += 1; k, c = self.frame, self.banner
        if hasattr(self, "btxt"):
            if self.draw_sprite(): c.delete("mascot")
            else:                                                                           # no sprites found: the old drawn mascot
                c.itemconfigure(self.mitem, image="") if self.mitem else None
                self.draw_mascot(44, 52, self.busy, (k % 55) < 3, kind=self.t.get("mascot", "plain") if self.mascot_kind() == "classic" else self.mascot_kind()); c.scale("mascot", 44, 52, .46, .46)
            w, sp = max(c.winfo_width(), 900), (3.0 if self.busy else 1.0)
            for p in self.parts:
                p["y"] -= p["v"] * sp
                if p["y"] < -12: p["y"], p["x"] = BANNER_H + 8, random.uniform(100, w - 200)
                c.coords(p["it"], p["x"] + 8 * math.sin(k * .05 + p["ph"]), p["y"])
            c.itemconfigure(self.btxt, text=self.bubble())
        self.after(70, self.tick)

    def bubble(self):
        if self.busy: return f"Working hard~ {self.pct:.0%}  (ﾉ◕ヮ◕)ﾉ"
        if self.failed: return "Oh no… open Details to see why (╥﹏╥)"
        if self.cancelled: return "Okay, I stopped! ♡"
        if self.done: return "All done! Great job! ✧(≧◡≦)"
        if self.frame < self.quip_until: return self.quip
        try: tip_ = self.ctx_tip()
        except Exception: tip_ = None
        return tip_ or self.greet

    # ---------- style gallery ----------
    def thumb_path(self, p):
        return os.path.join(APP_DIR, "presets", p["id"] + ".gif") if p.get("builtin") else os.path.join(GIF_DIR, p["id"] + ".gif")

    def static_img(self, p):
        if p["id"] not in self.static:
            path, img = self.thumb_path(p), None
            if os.path.isfile(path):
                for idx in (STATIC_IDX, 0):
                    try: img = tk.PhotoImage(file=path, format=f"gif -index {idx}"); break
                    except Exception: img = None
            self.static[p["id"]] = img
        return self.static[p["id"]]

    def draw_gallery(self):
        c, t = self.gal, self.t; c.delete("all"); self.gal_imgs, self.animating = {}, None
        ps, sel = self.all_presets(), self.sel_preset.get()
        for i, p in enumerate(ps):
            x0 = 6 + i * (CARD_W + 10); on = p["id"] == sel; mx = x0 + CARD_W // 2
            rrect(c, x0, 4, x0 + CARD_W, GAL_H - 8, 16, fill=t["panel"], outline=t["accent"] if on else t["entry"], width=3 if on else 2)
            img = self.static_img(p)
            if img: self.gal_imgs[p["id"]] = c.create_image(mx, 14, anchor="n", image=img)
            else:
                rrect(c, mx - 50, 14, mx + 50, 192, 12, fill=mix(t["entry"], t["accent2"], .35), outline="")
                c.create_text(mx, 103, text=p["emoji"], font=("Segoe UI Emoji", 30), fill=t["accent"])
            c.create_text(mx, 200, text=f"{p['emoji']} {p['name']}", font=(FONT, 10, "bold"), fill=t["fg"], width=CARD_W - 14, anchor="n", justify="center")
            c.create_text(mx, 240, text=p.get("short") or "Your saved settings", font=(FONT, 8), fill=t["mute"], width=CARD_W - 18, anchor="n", justify="center")
            if on: c.create_text(x0 + CARD_W - 12, 18, text="✿", anchor="ne", font=("Segoe UI Symbol", 15), fill=t["accent"])
        c.configure(scrollregion=(0, 0, 6 + len(ps) * (CARD_W + 10), GAL_H))

    def card_at(self, x):
        cx = self.gal.canvasx(x) - 6; i = int(cx // (CARD_W + 10)); ps = self.all_presets()
        return ps[i] if cx >= 0 and 0 <= i < len(ps) and cx - i * (CARD_W + 10) <= CARD_W else None

    def gal_motion(self, e):
        p = self.card_at(e.x); self.set_hover(p["id"] if p else None)

    def set_hover(self, pid):
        if pid != self.hover: self.hover = pid; self.gal.configure(cursor="hand2" if pid else "")

    def gal_click(self, e):
        p = self.card_at(e.x)
        if p: self.choose_preset(p["id"])

    def choose_preset(self, pid):
        p = next((q for q in self.all_presets() if q["id"] == pid), None)
        if not p: return
        self.sel_preset.set(pid); self.apply_look(p["look"]); self.draw_gallery(); self.update_pinfo(); self.refresh_eta(); self.save()

    def update_pinfo(self):
        p = next((q for q in self.all_presets() if q["id"] == self.sel_preset.get()), None)
        self.pinfo.set(f"{p['emoji']} {p['name']} — {p['blurb']}" if p else "Custom settings — save them as your own style with the button on the right.")
        self.del_btn.state(["!disabled"] if p and not p.get("builtin") else ["disabled"])

    def anim_tick(self):
        """Only the card under the mouse (or the selected one) moves; frames are loaded a few at a time so the window never freezes."""
        try:
            pid = self.hover or self.sel_preset.get()
            if self.animating not in (None, pid) and self.animating in self.gal_imgs:
                st = self.static.get(self.animating)
                if st: self.gal.itemconfigure(self.gal_imgs[self.animating], image=st)
            self.animating = pid
            p = next((q for q in self.all_presets() if q["id"] == pid), None)
            if p and pid in self.gal_imgs:
                fr = self.frames.setdefault(pid, [])
                if pid in self.frame_order: self.frame_order.remove(pid)
                self.frame_order.append(pid)
                while len(self.frame_order) > 4:
                    old = self.frame_order.pop(0); self.frames.pop(old, None); self.done_load.discard(old)
                if pid not in self.done_load:
                    for _ in range(6):
                        try: fr.append(tk.PhotoImage(file=self.thumb_path(p), format=f"gif -index {len(fr)}"))
                        except Exception: self.done_load.add(pid); break
                if fr:
                    k = self.anim.get(pid, 0) % len(fr); self.anim[pid] = k + 1
                    self.gal.itemconfigure(self.gal_imgs[pid], image=fr[k])
        except Exception: pass
        self.after(100, self.anim_tick)

    # ---------- colours + caption sample ----------
    def pick_color(self, key):
        r = colorchooser.askcolor(color="#" + self.o[key].get().lstrip("#"), parent=self, title="Pick a colour")
        if r and r[1]: self.o[key].set(r[1].lstrip("#"))

    def pick_accent(self):
        r = colorchooser.askcolor(color="#" + self.accent_hex(), parent=self, title="Effects colour (right-click the swatch to follow the theme again)")
        if r and r[1]: self.accent.set(r[1].lstrip("#"))

    def paint_swatches(self):
        try:
            for key, b in self.swatches.items(): b.configure(bg="#" + self.o[key].get().lstrip("#"), activebackground="#" + self.o[key].get().lstrip("#"))
            self.accent_btn.configure(bg="#" + self.accent_hex(), activebackground="#" + self.accent_hex(), text="" if self.accent.get() else "auto", fg="#ffffff", font=(FONT, 8, "bold"))
            bgc = "#" + self.o["bg_color"].get().lstrip("#"); self.bg_sw.configure(bg=bgc, activebackground=bgc)
        except tk.TclError: pass

    def browse_file(self, key, types):
        p = filedialog.askopenfilename(title="Choose a file", filetypes=types + [("All files", "*.*")])
        if p: self.o[key].set(p)

    def pick_stickers(self):
        ps = filedialog.askopenfilenames(title="Choose sticker images (PNG / GIF)", filetypes=[("Images", "*.png *.gif *.webp *.jpg *.jpeg"), ("All files", "*.*")])
        if ps: self.o["stickers"].set("|".join(ps))

    def pick_sticker_dir(self):
        d = filedialog.askdirectory(title="Folder with sticker images")
        if d: self.o["stickers"].set(d)

    def draw_sample(self):
        c = self.cap_sample; c.delete("all"); w, h = max(c.winfo_width(), 400), int(c.cget("height"))
        o = self.opts_dict(); fam, _f, mult, bold = sc.FONTS[o["cap_font"]]
        size = max(10, int(34 * mult * o["cap_size"] / 100)); tc, hc, ec = "#" + o["cap_text"], "#" + o["cap_hi"], "#" + o["cap_edge"]
        for i in range(0, w, 8): c.create_rectangle(i, 0, i + 8, h, fill=mix("#3a2f66", "#8a3f8c", i / w), outline="")
        f = tkfont.Font(family=fam, size=-size, weight="bold" if bold else "normal")
        cx, cy, st = w / 2, h / 2, o["cap_style"]

        def txt(x, y, text, col, ang=0, fnt=f, anchor="center"):
            for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2), (-2, 2), (2, -2)): c.create_text(x + dx, y + dy, text=text, font=fnt, fill=ec, angle=ang, anchor=anchor)
            c.create_text(x, y, text=text, font=fnt, fill=col, angle=ang, anchor=anchor)
        if st == "karaoke":
            words, widths = ["THIS", "IS", "SO", "CUTE"], []
            widths = [f.measure(x) for x in words]; gap = f.measure(" "); x = cx - (sum(widths) + gap * 3) / 2
            for i, (wd, width) in enumerate(zip(words, widths)): txt(x, cy, wd, hc if i == 3 else tc, anchor="w"); x += width + gap
        elif st == "box":
            tw = f.measure("CUTE!"); pad = size * .3
            rrect(c, cx - tw / 2 - pad, cy - size * .75, cx + tw / 2 + pad, cy + size * .75, 4, fill=hc, outline="")
            c.create_text(cx, cy, text="CUTE!", font=f, fill=tc)
        elif st == "type":
            txt(cx, cy, "THIS IS SO CU|", tc)
        elif st == "line":
            f2 = tkfont.Font(family=fam, size=-int(size * .72), weight="bold" if bold else "normal")
            txt(cx, cy, "this is so cute!", tc, fnt=f2)
        else: txt(cx, cy, "CUTE!", hc, ang=6 if st == "bounce" else 0)
        c.create_text(8, 6, text="Preview of the caption style", anchor="nw", font=(FONT, 8), fill="#cfc4ee")

    # ---------- saving / previewing styles ----------
    def save_preset(self):
        name = simpledialog.askstring("Save my style", "Name for this style (it appears in the gallery):", parent=self)
        if not name or not name.strip(): return
        self.add_user_preset(vp.new_user_preset(name, self.get_look(), self.upresets))

    def add_user_preset(self, p):
        self.upresets.append(p)
        if not vp.save_user(self.upresets): messagebox.showinfo("VTuber Clipper", "I couldn't save your styles file, so this style will be gone when you close the app.")
        self.sel_preset.set(p["id"]); self.apply_look(p["look"]); self.draw_gallery(); self.update_pinfo(); self.save()
        self.after(150, lambda: self.gal.xview_moveto(1.0))
        if self.busy: return
        out = os.path.join(GIF_DIR, p["id"] + ".gif"); look = p["look"]

        def fn():
            os.makedirs(GIF_DIR, exist_ok=True); sc.PLAN.clear()
            vv.make_preview(out, look, width=100)
            self.ui(lambda: (self.static.pop(p["id"], None), self.frames.pop(p["id"], None), self.draw_gallery()))
        self.work(fn)

    def export_style(self):
        cur = next((q for q in self.all_presets() if q["id"] == self.sel_preset.get()), None)
        name = simpledialog.askstring("Share my style", "Name for this style:", initialvalue=(cur["name"] if cur else "My style"), parent=self)
        if not name or not name.strip(): return
        path = filedialog.asksaveasfilename(parent=self, title="Save my style", defaultextension=".vtstyle", initialfile=re.sub(r"[^\w\- ]", "", name).strip() + ".vtstyle",
                                            filetypes=[("VTuber Clipper style", "*.vtstyle"), ("All files", "*.*")])
        if not path: return
        try:
            vp.export_style(dict(name=name.strip()[:40], emoji=(cur or {}).get("emoji", "⭐"), blurb=(cur or {}).get("blurb", ""), look=self.get_look()), path)
            messagebox.showinfo("VTuber Clipper", "Saved ♡  Send that file to a friend and they can add it with 📥 Import a style.\n"
                                                  "It holds your look only: no file paths, no logo, no music.")
        except OSError as e: messagebox.showerror("VTuber Clipper", f"I couldn't save the file: {e}")

    def import_style(self):
        path = filedialog.askopenfilename(parent=self, title="Choose a style file", filetypes=[("VTuber Clipper style", "*.vtstyle *.json"), ("All files", "*.*")])
        if not path: return
        try: p = vp.import_style(path, self.all_presets())
        except ValueError as e: return messagebox.showerror("VTuber Clipper", str(e))
        self.add_user_preset(p)
        self.status.set(f"Added the style “{p['name']}” ♡")

    def delete_preset(self):
        p = next((q for q in self.upresets if q["id"] == self.sel_preset.get()), None)
        if not p or not messagebox.askyesno("VTuber Clipper", f"Delete your style “{p['name']}”?"): return
        self.upresets.remove(p); vp.save_user(self.upresets)
        try: os.remove(os.path.join(GIF_DIR, p["id"] + ".gif"))
        except OSError: pass
        self.sel_preset.set(""); self.draw_gallery(); self.update_pinfo(); self.save()

    def open_preview(self, use_vod=None):
        if self.busy: return messagebox.showinfo("VTuber Clipper", "I'm busy right now~ try again when this finishes.")
        look, opts, cam = self.get_look(), self.opts_dict(), self.v["cam"].get() or None
        video = self.v["video"].get().strip().strip('"'); video = video if os.path.isfile(video) else None
        if use_vod is False: video = None
        out = os.path.join(GIF_DIR, f"_preview{int(time.time())}.gif")
        extra = {k: x for k, x in opts.items() if k not in ("music", "intro", "outro", "lang", "translate", "hint", "fixes", "post_kit", "srt", "channel", "game", "tags")}
        note = "your VOD" if video else "the built-in cartoon scene"
        try:
            import vcnew
            if extra.get("text_boxes"): extra["text_boxes"] = vcnew.texts_json([{**b, "say": False} for b in vcnew.parse_texts(extra["text_boxes"])])   # the picture preview has no sound: no voice needed
        except Exception: pass

        def fn():
            os.makedirs(GIF_DIR, exist_ok=True); sc.PLAN.clear()
            for f_ in glob.glob(os.path.join(GIF_DIR, "_preview*.gif")):
                try: os.remove(f_)
                except OSError: pass
            words, t0, secs = None, 0.0, 7.5
            if video:
                dur = sc.probe(video)[0]
                cp = sc.cache_path(video, opts["lang"], opts["translate"], opts["hint"]); ws = None
                try:
                    if cp.exists(): ws = sc.apply_fixes(sc.read_cached_words(cp, video)[0], opts["fixes"])
                except Exception: ws = None
                t0 = vv.best_window(ws, dur, secs); secs = min(secs, max(3.0, dur - t0))
                words = [w for w in ws if t0 <= w["start"] < t0 + secs] if ws else None
                if not words: words = None
            vv.make_preview(out, look, video=video, cam=cam, words=words, t0=t0, secs=secs, width=252, opts=extra)
            self.ui(lambda: self.show_preview(out, note, bool(video), sc.needs_cam(look["layout"], opts) and not cam and bool(video), words is not None))
        self.work(fn)

    def show_preview(self, gif, note, has_vod, no_cam, real_words):
        w = self.preview_win
        fresh = w is None or not w.winfo_exists()
        if fresh:
            w = self.preview_win = tk.Toplevel(self); w.title("Style preview ♡"); w.configure(bg=self.t["bg"]); w.transient(self)
            self.pv_label = tk.Label(w, bd=0, bg=self.t["bg"]); self.pv_label.pack(padx=14, pady=(12, 4))
            self.pv_note = tk.StringVar(); ttk.Label(w, textvariable=self.pv_note, style="Mute.TLabel", wraplength=300, justify="center").pack(padx=14)
            bf = ttk.Frame(w); bf.pack(pady=10)
            ttk.Button(bf, text="🌸 Cartoon scene", command=lambda: self.open_preview(False)).pack(side="left", padx=4)
            self.pv_vod = ttk.Button(bf, text="🎬 My VOD", command=lambda: self.open_preview(True)); self.pv_vod.pack(side="left", padx=4)
            ttk.Button(bf, text="Close", command=w.destroy).pack(side="left", padx=4)
        if self.pv_player: self.pv_player.stop()
        self.pv_player = GifPlayer(self, self.pv_label, gif)
        self.pv_vod.state(["!disabled"] if has_vod or self.v["video"].get().strip() else ["disabled"])
        msg = f"This is a real render of your current settings on {note}."
        if has_vod and not real_words: msg += "  Captions are sample text until this VOD has been transcribed once."
        if no_cam: msg += "  No cam area is selected, so the layout falls back to the blurred background."
        self.pv_note.set(msg); w.lift()
        if fresh: self.after(60, lambda: center_over(w, self) if w.winfo_exists() else None)

    def draw_badge(self):
        c, t = self.badge, self.t; c.delete("all")
        name, col = SITES.get(site(self.v["url"].get()), ("no link", t["mute"]))
        rrect(c, 1, 1, 95, 25, 11, fill=t["panel"], outline=col, width=2); c.create_oval(10, 9, 18, 17, fill=col, outline="")
        c.create_text(25, 13, text=name, anchor="w", font=(FONT, 9, "bold"), fill=t["fg"])

    # ---------- settings ----------
    def open_settings(self, tab=None):
        if self.sw and self.sw.winfo_exists():
            self.sw.lift(); self.sw_tab_select(tab); return
        w = self.sw = tk.Toplevel(self); w.title("Settings ♡"); w.configure(bg=self.t["bg"]); w.transient(self)
        center_over(w, self, 740, min(680, self.winfo_screenheight() - 100)); w.minsize(600, 420)
        w.protocol("WM_DELETE_WINDOW", self.close_settings)
        nb = ttk.Notebook(w); nb.pack(fill="both", expand=True, padx=12, pady=(12, 4))
        # --- theme
        t1 = ttk.Frame(nb, padding=14); nb.add(t1, text="  🎨 Theme  ")
        ttk.Label(t1, text="Pick a look — it changes right away ♡", style="Mute.TLabel").pack(anchor="w", pady=(0, 6))
        self.sw_canvas = tk.Canvas(t1, width=6 + SW_STEP * SW_COLS, height=6 + SW_ROW * ((len(THEMES) + SW_COLS - 1) // SW_COLS), highlightthickness=0, bg=self.t["bg"]); self.sw_canvas.pack(anchor="w")
        self.sw_canvas.bind("<Button-1>", self.swatch_click); self.draw_swatches()
        mf = ttk.Frame(t1); mf.pack(anchor="w", pady=(8, 0))
        ttk.Label(mf, text="Banner mascot").pack(side="left"); self.combo(mf, self.v["mascot"], MASCOTS, 15).pack(side="left", padx=8)
        ttk.Label(mf, text="“Match theme” gives each look its own costume", style="Mute.TLabel").pack(side="left")
        # --- output
        t2 = ttk.Frame(nb, padding=14); nb.add(t2, text="  🎞 Output  ")
        h = lambda r, txt: ttk.Label(t2, text=txt, font=(FONT, 11, "bold")).grid(row=r, column=0, sticky="w", pady=(0 if r == 0 else 12, 3))
        h(0, "Video quality")
        qf = ttk.Frame(t2); qf.grid(row=1, column=0, sticky="w")
        for i, (name, mb) in enumerate(sc.QUALITY_MBPS.items()):
            ttk.Radiobutton(qf, text=f"{name}  ·  {mb} Mbps", value=name, variable=self.oq, command=self.out_changed).grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 28), pady=2)
        h(2, "Resolution")
        rf = ttk.Frame(t2); rf.grid(row=3, column=0, sticky="w")
        for i, name in enumerate(sc.RESOLUTIONS):
            ttk.Radiobutton(rf, text=name, value=name, variable=self.ores, command=self.out_changed).grid(row=0, column=i, padx=(0, 22))
        h(4, "Framerate")
        ff = ttk.Frame(t2); ff.grid(row=5, column=0, sticky="w")
        for i, n in enumerate(sc.FRAMERATES):
            ttk.Radiobutton(ff, text=f"{n} fps", value=str(n), variable=self.ofps, command=self.out_changed).grid(row=0, column=i, padx=(0, 22))
        self.out_sum = tk.StringVar(); self.autowrap(ttk.Label(t2, textvariable=self.out_sum, justify="left"), t2, 30).grid(row=6, column=0, sticky="w", pady=(16, 4))
        self.autowrap(ttk.Label(t2, text="Bitrate is a target — simple scenes may come out smaller. Higher settings take longer to render and make bigger files; "
                                "going above your VOD's own resolution just enlarges it.", style="Mute.TLabel", justify="left"), t2, 30).grid(row=7, column=0, sticky="w")
        self.out_changed(save=False)
        # --- downloads
        t3 = ttk.Frame(nb, padding=14); nb.add(t3, text="  ⬇ Downloads  ")
        ttk.Label(t3, text="Use cookies from").grid(row=0, column=0, sticky="w", pady=3)
        self.combo(t3, self.v["cookies"], ["none", "chrome", "firefox", "edge", "brave"], 10).grid(row=0, column=1, sticky="w", padx=8)
        self.autowrap(ttk.Label(t3, text="for subscriber-only VODs (be logged in in that browser)", style="Mute.TLabel", justify="left"), t3, 30).grid(row=0, column=2, sticky="w")
        ttk.Checkbutton(t3, text="Update the downloader before the first download (fixes most 404 errors)", variable=self.auto_update).grid(row=1, column=0, columnspan=3, sticky="w", pady=(10, 0))
        ttk.Button(t3, text="🔄  Update downloader now", command=lambda: self.work(self.update_ytdlp)).grid(row=2, column=0, columnspan=2, sticky="w", pady=10)
        # --- performance
        t4 = ttk.Frame(nb, padding=14); nb.add(t4, text="  ⚡ Performance  "); t4.columnconfigure(1, weight=1)
        ttk.Label(t4, text="Default save folder").grid(row=0, column=0, sticky="w", pady=3)
        ttk.Entry(t4, textvariable=self.v["out"]).grid(row=0, column=1, sticky="we", padx=8)
        ttk.Button(t4, text="Browse", command=lambda: self.v["out"].set(filedialog.askdirectory() or self.v["out"].get())).grid(row=0, column=2)
        ttk.Label(t4, text="Speech model").grid(row=1, column=0, sticky="w", pady=3)
        self.combo(t4, self.v["model"], ["tiny", "base", "small", "medium"], 10).grid(row=1, column=1, sticky="w", padx=8)
        ttk.Label(t4, text="Speech processor").grid(row=2, column=0, sticky="w", pady=3)
        self.combo(t4, self.v["device"], ["auto", "cuda", "cpu"], 10).grid(row=2, column=1, sticky="w", padx=8)
        ttk.Label(t4, text="Speech accuracy").grid(row=3, column=0, sticky="w", pady=3)
        sp = ttk.Frame(t4); sp.grid(row=3, column=1, columnspan=2, sticky="w", padx=8)
        for k_, nm in SPEED_NAMES.items(): ttk.Radiobutton(sp, text=nm, value=k_, variable=self.v["speed"], command=self.perf_changed).pack(side="left", padx=(0, 14))
        self.autowrap(ttk.Label(t4, text="Fast is about twice as quick with a few more small mistakes; Most accurate is the slowest.", style="Mute.TLabel", justify="left"), t4, 30).grid(row=4, column=1, columnspan=2, sticky="w", padx=8)
        ttk.Label(t4, text="Clips rendered at once").grid(row=5, column=0, sticky="w", pady=3)
        self.combo(t4, self.v["parallel"], ["auto", "1", "2", "3", "4"], 10).grid(row=5, column=1, sticky="w", padx=8)
        self.v["parallel"].trace_add("write", lambda *a: self.perf_changed())
        self.autowrap(ttk.Label(t4, text="Auto = 1 on small PCs, 2-3 on PCs with many cores. More at once is faster only if you have spare cores and memory.", style="Mute.TLabel", justify="left"), t4, 30).grid(row=6, column=1, columnspan=2, sticky="w", padx=8)
        ttk.Checkbutton(t4, text="Use GPU video encoding when available (NVENC / AMF / QuickSync)", variable=self.gpu_enc, command=self.refresh_eta).grid(row=7, column=0, columnspan=3, sticky="w", pady=(10, 0))
        self.autowrap(ttk.Label(t4, text=self.hw_text or "Looking at your PC…", style="Mute.TLabel", justify="left"), t4, 30).grid(row=8, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(t4, text="Time estimates learn from your PC and get better after each job.", style="Mute.TLabel").grid(row=9, column=0, columnspan=3, sticky="w")
        ttk.Button(t4, text="⬇  Install GPU speech pack  (NVIDIA only · ~1.4 GB · one time)", command=self.install_gpu).grid(row=10, column=0, columnspan=3, sticky="w", pady=10)
        ttk.Label(t4, text="While it works", font=(FONT, 10, "bold"), foreground=self.t["accent"]).grid(row=11, column=0, columnspan=3, sticky="w", pady=(8, 2))
        ttk.Checkbutton(t4, text="Keep my PC awake while it makes videos", variable=self.awake_v, command=self.save).grid(row=12, column=0, columnspan=3, sticky="w")
        ttk.Checkbutton(t4, text="Run at lower priority so my game or stream stays smooth", variable=self.lowprio_v, command=lambda: (self.apply_priority(), self.save())).grid(row=13, column=0, columnspan=3, sticky="w")
        self.autowrap(ttk.Label(t4, text="Lower priority makes the app a little slower only when something else needs the PC. Videos are made at the same quality.", style="Mute.TLabel", justify="left"), t4, 30).grid(row=14, column=0, columnspan=3, sticky="w", padx=(22, 0))
        self.build_settings_tools(nb); self.build_settings_profiles(nb); self.build_settings_about(nb)
        self.sw_nb = nb; self.sw_tab_select(tab)
        ttk.Label(w, text=f"VTuber Clipper {VER_LABEL}  ♡  made with love", style="Mute.TLabel").pack(pady=(2, 0))
        ttk.Button(w, text="Done", style="Accent.TButton", command=self.close_settings).pack(pady=8)
        self.apply_theme()

    def autowrap(self, lbl, host, margin=24):
        """Keep a long label inside its tab: it wraps to the space that is left, and again whenever the window is resized."""
        def fit(e=None):
            try:
                w = host.winfo_width() - (lbl.winfo_rootx() - host.winfo_rootx()) - margin
                if w > 120 and abs(w - int(float(str(lbl.cget("wraplength")) or 0))) > 3: lbl.configure(wraplength=w)
            except (tk.TclError, ValueError): pass
        host.bind("<Configure>", fit, add="+"); lbl.bind("<Map>", lambda e: host.after(20, fit), add="+"); host.after(80, fit)
        return lbl

    def sw_tab_select(self, tab):
        try:
            nb = self.sw_nb
            for i, tid in enumerate(nb.tabs()):
                if tab and nb.tab(tid, "text").strip().lower().endswith(tab.lower()): nb.select(tid); return
        except (tk.TclError, AttributeError): pass

    # ---------- Settings: profiles ----------
    def profiles_path(self): return os.path.join(HOME, ".vtuberclipper_profiles.json")

    def load_profiles(self):
        try:
            d = json.load(open(self.profiles_path(), encoding="utf-8"))
            return {str(k): v for k, v in d.items() if isinstance(v, dict)} if isinstance(d, dict) else {}
        except Exception: return {}

    def write_profiles(self, d):
        try:
            with open(self.profiles_path(), "w", encoding="utf-8") as f: json.dump(d, f)
            return True
        except Exception: return False

    def snapshot(self):
        """Everything a channel profile remembers: the look, every option (logo, @name, music, posting info...) and the recap settings."""
        return dict(look=self.get_look(), opts={**{k: x.get() for k, x in self.o.items()}, "lang_name": self.lang_name.get()},
                    recap={**{k: self.v[k].get() for k in ("rmin", "rmax", "split", "psplit", "pcount", "pmin", "gsens", "gmin")}, "whole": bool(self.rwhole.get())},
                    music_own=self.music_own)

    def apply_snapshot(self, d):
        if isinstance(d.get("opts"), dict):
            for k, val in d["opts"].items():
                if k in self.o and isinstance(val, (str, int, float, bool)): self.o[k].set(val)
            if str(d["opts"].get("lang_name", "")) in sc.LANGS: self.lang_name.set(d["opts"]["lang_name"])
        if isinstance(d.get("look"), dict): self.apply_look(d["look"])
        rc = d.get("recap") if isinstance(d.get("recap"), dict) else {}
        for k_, ok_ in (("split", tuple(SPLIT_NAMES)), ("psplit", ("count", "length")), ("gsens", tuple(sc.GAME_SENS))):
            if str(rc.get(k_)) in ok_: self.v[k_].set(str(rc[k_]))
        for k_ in ("rmin", "rmax", "pcount", "pmin", "gmin"):
            try:
                if float(rc[k_]) > 0: self.v[k_].set(str(rc[k_]))
            except (KeyError, TypeError, ValueError): pass
        self.rwhole.set(bool(rc.get("whole", False)))
        if isinstance(d.get("music_own"), str): self.music_own = d["music_own"]
        self.music_refresh(); self.save()

    def build_settings_profiles(self, nb):
        t = ttk.Frame(nb, padding=14); nb.add(t, text="  👤 Profiles  "); t.columnconfigure(1, weight=1)
        self.autowrap(ttk.Label(t, text="A profile remembers all your settings for one channel: the look, logo, @name, music, posting info and Recap settings. "
                                "Save one per channel and switch with a click.", style="Mute.TLabel", justify="left"), t, 30).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))
        self.prof_name, self.prof_pick = tk.StringVar(), tk.StringVar()
        ttk.Label(t, text="Save the current settings as").grid(row=1, column=0, sticky="w", pady=3)
        pe = ttk.Entry(t, textvariable=self.prof_name); pe.grid(row=1, column=1, sticky="we", padx=8); pe.bind("<Return>", lambda e: self.profile_save())
        ttk.Button(t, text="💾 Save profile", command=self.profile_save).grid(row=1, column=2, sticky="e")
        ttk.Label(t, text="My profiles").grid(row=2, column=0, sticky="w", pady=(12, 3))
        self.prof_combo = self.combo(t, self.prof_pick, sorted(self.load_profiles(), key=str.lower), 30); self.prof_combo.grid(row=2, column=1, sticky="w", padx=8, pady=(12, 3))
        bf = ttk.Frame(t); bf.grid(row=2, column=2, sticky="e", pady=(12, 3))
        ttk.Button(bf, text="Use this", style="Accent.TButton", command=self.profile_load).pack(side="left")
        ttk.Button(bf, text="Delete", command=self.profile_delete).pack(side="left", padx=(4, 0))
        self.prof_note = tk.StringVar(value="No profile yet - set everything up the way you like, give it a name above and press Save.")
        self.autowrap(ttk.Label(t, textvariable=self.prof_note, style="Mute.TLabel", justify="left"), t, 30).grid(row=3, column=0, columnspan=3, sticky="w", pady=(14, 0))
        self.profile_refresh()

    def profile_refresh(self, pick=None):
        names = sorted(self.load_profiles(), key=str.lower)
        try: self.prof_combo.configure(values=names)
        except (tk.TclError, AttributeError): pass
        if pick is not None: self.prof_pick.set(pick)
        elif self.prof_pick.get() not in names: self.prof_pick.set(names[0] if names else "")
        if names and not self.prof_note.get().startswith(("Saved", "Loaded", "Deleted")):
            self.prof_note.set(f"{len(names)} profile{'s' if len(names) != 1 else ''}. “Use this” loads the one picked above.")

    def profile_save(self):
        name = re.sub(r"\s+", " ", self.prof_name.get()).strip()[:40]
        if not name: return self.prof_note.set("Type a name for the profile first, for example the name of your channel.")
        d = self.load_profiles()
        if name not in d and len(d) >= 30: return self.prof_note.set("That is a lot of profiles! Delete one you don't use first.")
        d[name] = self.snapshot()
        if not self.write_profiles(d): return self.prof_note.set("I couldn't save the profile file. Is your user folder write-protected?")
        self.prof_note.set(f"Saved “{name}”."); self.profile_refresh(name)

    def profile_load(self):
        name, d = self.prof_pick.get(), self.load_profiles()
        if name not in d: return self.prof_note.set("Pick a profile from the list first.")
        self.apply_snapshot(d[name]); self.prof_note.set(f"Loaded “{name}”. Your look and options are now the ones saved in it.")
        self.status.set(f"Profile “{name}” loaded ✿")

    def profile_delete(self):
        name, d = self.prof_pick.get(), self.load_profiles()
        if name not in d: return
        if not messagebox.askyesno("VTuber Clipper", f"Delete the profile “{name}”?", parent=self.sw): return
        d.pop(name); self.write_profiles(d); self.prof_note.set(f"Deleted “{name}”."); self.profile_refresh()

    # ---------- Settings: about / beta ----------
    def build_settings_about(self, nb):
        t = ttk.Frame(nb, padding=14); nb.add(t, text="  ℹ About  ")
        ttk.Label(t, text=f"VTuber Clipper {VER_LABEL}", font=(FONT, 15, "bold"), foreground=self.t["accent"]).pack(anchor="w")
        self.autowrap(ttk.Label(t, text="This is a beta: it works and has been tested a lot, but new things can still have rough edges. "
                                "If something looks wrong, press “Copy info for a bug report” and send it along with a description of what happened.", justify="left"), t, 30).pack(anchor="w", pady=(6, 10))
        bf = ttk.Frame(t); bf.pack(anchor="w", fill="x")
        for i, (txt, cmd) in enumerate((("✨ What's new", self.show_whatsnew), ("📋 Copy info for a bug report", self.copy_bug_info), ("📄 Open the error log", lambda: open_path(LOGF)),
                                        ("📂 Open the save folder", self.open_out), ("🔊 Sound credits & music notes", lambda: open_path(os.path.join(APP_DIR, "CREDITS.txt"))))):
            ttk.Button(bf, text=txt, command=cmd).grid(row=i // 2, column=i % 2, sticky="we", padx=(0, 8), pady=3)
        bf.columnconfigure(0, weight=1, uniform="ab"); bf.columnconfigure(1, weight=1, uniform="ab")
        self.about_note = tk.StringVar()
        self.autowrap(ttk.Label(t, textvariable=self.about_note, style="Mute.TLabel", justify="left"), t, 30).pack(anchor="w", pady=(6, 0))
        ttk.Label(t, text="Shortcuts", font=(FONT, 10, "bold"), foreground=self.t["accent"]).pack(anchor="w", pady=(14, 2))
        import vc20ui
        self.autowrap(ttk.Label(t, text=vc20ui.SHORTCUTS, justify="left"), t, 30).pack(anchor="w")

    def bug_info(self):
        import platform
        try: ffv = subprocess.run([sc.FF, "-version"], capture_output=True, text=True, errors="replace", timeout=10, **sc.NOWIN).stdout.splitlines()[0]
        except Exception: ffv = "ffmpeg not found"
        tail = ""
        try:
            with open(LOGF, encoding="utf-8", errors="replace") as f: tail = f.read()[-2500:]
        except Exception: tail = "(no error log)"
        return (f"VTuber Clipper {VER_LABEL}\nWindows/OS: {platform.platform()}\nPython: {platform.python_version()}\n{ffv}\n"
                f"PC: {self.hw_text or 'not scanned yet'}\nTheme: {self.v['theme'].get()}   Look: {self.sel_preset.get()}   Mode: {self.mode.get()}\n"
                f"Emotes: {'on' if self.o['emotes'].get() else 'off'} ({self.o['emote_level'].get()}, {self.o['emote_pos'].get()})   Sound pack: {self.o['sfx_pack'].get()}   Music: {'none' if not self.o['music'].get().strip() else 'my music folder' if self.o['music'].get().strip() == self.music_home() else 'a song or folder of my own'}\n\nLast lines of the error log:\n{tail}")

    def copy_bug_info(self):
        try:
            self.clipboard_clear(); self.clipboard_append(self.bug_info()); self.update()
            msg = "Copied ✿ Paste it into your message."
        except tk.TclError: msg = "I couldn't reach the clipboard."
        if getattr(self, "about_note", None) is not None: self.about_note.set(msg)

    def maybe_whatsnew(self):
        if os.environ.get("VTC_TEST") or self.seen_ver == VERSION: return
        self.seen_ver = VERSION; self.save(); self.show_whatsnew()

    def show_whatsnew(self):
        w = tk.Toplevel(self); w.title(f"What's new in {VER_LABEL}"); w.configure(bg=self.t["bg"]); w.transient(self); center_over(w, self, 600, min(560, self.winfo_screenheight() - 120))
        ttk.Label(w, text=f"VTuber Clipper {VER_LABEL} ♡", font=(FONT, 15, "bold"), foreground=self.t["accent"]).pack(anchor="w", padx=18, pady=(14, 6))
        tx = tk.Text(w, wrap="word", relief="flat", padx=12, pady=10, font=(FONT, 10), bg=self.t["entry"], fg=self.t["fg"], height=18); tx.pack(fill="both", expand=True, padx=18)
        tx.tag_configure("h", font=(FONT, 10, "bold"), foreground=self.t["accent"], spacing1=8)
        for h_, body in WHATS_NEW: tx.insert("end", h_ + "\n", "h"); tx.insert("end", body + "\n")
        tx.configure(state="disabled")
        ttk.Button(w, text="Got it ♡", style="Accent.TButton", command=w.destroy).pack(pady=12); w.bind("<Escape>", lambda e: w.destroy())

    # ---------- music + sound packs ----------
    def music_home(self): return os.path.join(HOME, MUSIC_FOLDER)

    def music_block(self, parent):
        """The music picker (used on the Logo & music tab and on the Recap page; both show the same setting)."""
        f = ttk.Frame(parent); f.columnconfigure(0, weight=1)
        top = ttk.Frame(f); top.grid(row=0, column=0, sticky="we")
        mc = self.combo(top, self.mlabel, list(self.music_names().values()) + [MUSIC_OWN], 46); mc.pack(side="left"); mc.bind("<<ComboboxSelected>>", self.music_selected); self.mcombos.append(mc)
        self.tip(ttk.Button(top, text="▶ Hear it", command=self.play_music_preview), "Plays about 14 seconds at the loudness it will have in the video.").pack(side="left", padx=(8, 0))
        self.tip(ttk.Button(top, text="■", width=3, command=self.stop_sound), "Stop the sound").pack(side="left", padx=(4, 0))
        ttk.Label(top, text="volume %").pack(side="left", padx=(12, 3)); self.spin(top, self.o["music_vol"], 1, 100, 1, 4).pack(side="left")
        bar = ttk.Frame(f); bar.grid(row=1, column=0, sticky="w", pady=(5, 0))
        self.tip(ttk.Button(bar, text="➕ Add songs…", command=self.music_add), "Copies the songs you pick into your music folder, so they are always here.").pack(side="left")
        self.tip(ttk.Button(bar, text="📂 Open my music folder", command=self.music_open), "Opens the folder. You can also drop songs into it yourself.").pack(side="left", padx=6)
        ttk.Button(bar, text="✖ No music", command=lambda: self.o["music"].set("")).pack(side="left")
        own = ttk.Frame(f); own.grid(row=2, column=0, sticky="we", pady=(5, 0)); own.columnconfigure(0, weight=1); self.mown_rows.append(own)
        me = ttk.Entry(own, textvariable=self.mpath); me.grid(row=0, column=0, sticky="we")
        me.bind("<Return>", self.music_typed); me.bind("<FocusOut>", self.music_typed)
        self.tip(me, "The song or folder you chose. You can also paste a path here.")
        ob = ttk.Frame(own); ob.grid(row=0, column=1, padx=(8, 0))
        ttk.Button(ob, text="Song…", command=lambda: self.pick_music(False)).pack(side="left")
        self.tip(ttk.Button(ob, text="📁 Folder…", command=lambda: self.pick_music(True)), "Use every song in a folder: a different one for each Short, a playlist in Recaps.").pack(side="left", padx=(4, 0))
        own.grid_remove()
        dl = ttk.Label(f, textvariable=self.mdesc, style="Mute.TLabel", justify="left"); dl.grid(row=3, column=0, sticky="w", pady=(5, 0)); self.autowrap(dl, parent, 12)
        nt = ttk.Label(f, text="The app brings no music of its own. Only add songs you may use in videos: your own, ones you bought, or free-to-use ones. Game and TV soundtracks usually "
                               "get claimed on YouTube and TikTok, and some free songs ask for a credit in the description.", style="Mute.TLabel", justify="left")
        nt.grid(row=4, column=0, sticky="w", pady=(3, 0)); self.autowrap(nt, parent, 12)
        return f

    def music_names(self):
        """spec -> what the music drop-down shows: no music, your music folder, each song in it. (Songs from somewhere else show as one extra choice.)"""
        d = {"": "No music"}
        home = self.music_home(); songs = sc.music_choices(home) if os.path.isdir(home) else []
        d[home] = f"My music folder: a different song each time ({len(songs)} song{'s' if len(songs) != 1 else ''})"
        for p in songs[:150]: d[p] = "♪ " + os.path.relpath(p, home).replace(os.sep, " / ")
        return d

    def music_desc(self, raw):
        if not raw: return "No background music."
        n, s_ = sc.music_count(raw), ""
        if raw == self.music_home():
            if not n: return "Your music folder is empty. Press “Add songs…” and pick some, or drop them into the folder."
            return f"{n} song{'s' if n != 1 else ''} in your music folder: a different one for each Short, a playlist with cross-fades in Recaps."
        if not n: return "⚠ I can't find that file or folder, so there will be no music."
        if os.path.isdir(raw): return f"Folder with {n} song{'s' if n != 1 else ''}: a different one for each Short, a playlist with cross-fades in Recaps."
        return "This song plays under the whole video (it repeats if the video is longer)."

    def music_refresh(self, *a):
        try:
            raw = self.o["music"].get().strip().strip('"')
            if raw.startswith("lib:"): self.o["music"].set(""); raw = ""          # an early 1.8 beta had built-in music; it is gone now
            names = self.music_names(); own = bool(raw) and raw not in names
            vals = list(names.values()) + [MUSIC_OWN]
            for c in self.mcombos:
                try: c.configure(values=vals)
                except tk.TclError: pass
            self.mlabel.set(MUSIC_OWN if own else names.get(raw, names[""])); self.mpath.set(raw if own else "")
            if own and (os.path.isfile(raw) or os.path.isdir(raw)): self.music_own = raw
            for fr in self.mown_rows:
                try: fr.grid() if own else fr.grid_remove()
                except tk.TclError: pass
            self.mdesc.set(self.music_desc(raw))
        except (tk.TclError, KeyError): pass

    def music_selected(self, e=None):
        lab, names = self.mlabel.get(), self.music_names()
        if lab == MUSIC_OWN:
            if self.music_own and (os.path.isfile(self.music_own) or os.path.isdir(self.music_own)): self.o["music"].set(self.music_own)
            else: self.pick_music(False)
            return self.music_refresh()
        spec = {v: k for k, v in names.items()}.get(lab, "")
        if spec == self.music_home():
            try: os.makedirs(spec, exist_ok=True)
            except OSError: pass
        self.o["music"].set(spec); self.music_refresh()

    def music_typed(self, e=None):
        raw = self.mpath.get().strip().strip('"')
        if raw != self.o["music"].get().strip() and (raw or self.mlabel.get() == MUSIC_OWN): self.o["music"].set(raw)

    def pick_music(self, folder=False):
        if folder: p = filedialog.askdirectory(title="Choose the folder with your music")
        else: p = filedialog.askopenfilename(title="Choose a song", filetypes=[("Audio", "*.mp3 *.wav *.m4a *.ogg *.flac *.aac *.opus"), ("All files", "*.*")])
        if p: self.music_own = p; self.o["music"].set(p)
        self.music_refresh()

    def music_open(self):
        home = self.music_home()
        try: os.makedirs(home, exist_ok=True)
        except OSError: return self.mdesc.set("I couldn't make the music folder. Is your user folder write-protected?")
        open_path(home)

    def music_add(self):
        """Copy the songs the user picks into the music folder (a file with the same name and size is not copied twice)."""
        files = filedialog.askopenfilenames(title="Add songs to my music folder", filetypes=[("Audio", "*.mp3 *.wav *.m4a *.ogg *.flac *.aac *.opus"), ("All files", "*.*")])
        if not files: return
        home = self.music_home()
        try: os.makedirs(home, exist_ok=True)
        except OSError: return self.mdesc.set("I couldn't make the music folder. Is your user folder write-protected?")
        done = skipped = 0
        for src in files:
            src = str(src); base = os.path.basename(src); dst = os.path.join(home, base)
            if not (os.path.isfile(src) and src.lower().endswith(sc.AUDIO_EXT)) or os.path.abspath(os.path.dirname(src)) == os.path.abspath(home): skipped += 1; continue
            try:
                if os.path.exists(dst):
                    if os.path.getsize(dst) == os.path.getsize(src): skipped += 1; continue
                    stem, ext = os.path.splitext(base); k = 2
                    while os.path.exists(os.path.join(home, f"{stem} ({k}){ext}")): k += 1
                    dst = os.path.join(home, f"{stem} ({k}){ext}")
                shutil.copy2(src, dst); done += 1
            except OSError: skipped += 1
        if done and not self.o["music"].get().strip(): self.o["music"].set(home)
        self.music_refresh()
        self.mdesc.set(f"Added {done} song{'s' if done != 1 else ''}" + (f" ({skipped} left out: not a song, already there, or could not be copied)" if skipped else "") + ".  " + self.mdesc.get())

    def play_sound(self, path):
        try:
            if sys.platform.startswith("win"):
                import winsound; winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            else: self.last_played = path
        except Exception: pass

    def stop_sound(self):
        try:
            if sys.platform.startswith("win"):
                import winsound; winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception: pass

    def play_music_preview(self):
        spec = self.o["music"].get().strip()
        if not spec: return self.mdesc.set("Pick some music first ♡")
        if not sc.music_count(spec): return self.mdesc.set("There are no songs there yet. Press “Add songs…” first ♡")
        self.mdesc.set("Getting a taste of the music…")
        def go():
            p = sc.pick_music(spec); w = sc.music_preview(p, os.path.join(tempfile.gettempdir(), "vclip_music_preview.wav")) if p else ""
            self.ui(lambda: self.music_preview_ready(w, p))
        threading.Thread(target=go, daemon=True).start()

    def music_preview_ready(self, wav, src):
        if wav:
            self.play_sound(wav); self.mdesc.set(f"Playing: {os.path.splitext(os.path.basename(src))[0]}"); self.after(14500, self.music_refresh)
        else: self.mdesc.set("I couldn't play that. Is the file OK?")

    def play_sfx_preview(self):
        pack = self.o["sfx_pack"].get()
        def go():
            w = sc.sfx_preview(pack, os.path.join(tempfile.gettempdir(), f"vclip_sfx_preview_{pack}.wav"))
            if w: self.ui(lambda: self.play_sound(w))
        threading.Thread(target=go, daemon=True).start()

    # ---------- keep awake, low priority, disk space ----------
    def apply_priority(self):
        """Below-normal priority: a game or stream running at the same time keeps its frame rate. Programs started afterwards (ffmpeg) inherit it."""
        if not sys.platform.startswith("win"): return
        try:
            import ctypes
            k = ctypes.windll.kernel32; k.SetPriorityClass(k.GetCurrentProcess(), 0x4000 if self.lowprio_v.get() else 0x20)
        except Exception: pass

    def set_awake(self, on):
        """Stops Windows from going to sleep while a job runs (the 'keep awake' setting)."""
        on = bool(on and self.awake_v.get())
        if on == self.awake_on: return
        self.awake_on = on
        if not sys.platform.startswith("win"): return
        try:
            import ctypes
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000001 if on else 0x80000000)        # ES_CONTINUOUS | ES_SYSTEM_REQUIRED, or back to normal
        except Exception: pass

    def disk_ok(self, kind):
        try:
            d = self.v["out"].get().strip() or HOME
            while d and not os.path.isdir(d):
                up = os.path.dirname(d)
                if up == d: break
                d = up
            free = shutil.disk_usage(d or HOME).free
        except Exception: return True
        if free >= (4e9 if kind == "long" else 1.5e9): return True
        return bool(messagebox.askyesno("VTuber Clipper", f"Only {free / 1e9:.1f} GB is free on the drive for your save folder. Videos can need more than that, "
                                        "and a full drive stops a job half way.\n\nMake the videos anyway?"))

    # ---------- recent videos, window memory ----------
    def add_recent(self, p):
        p = str(p or "").strip().strip('"')
        if not p or len(p) > 500 or p.startswith(os.path.join(tempfile.gettempdir(), "vclip")): return
        self.recent = ([p] + [x for x in self.recent if x != p])[:RECENT_MAX]

    def recent_items(self):
        """[(menu text, value)] of the recent videos that still exist and the recent links."""
        out = []
        for p in self.recent:
            if site(p): out.append(("🔗  " + (p if len(p) < 60 else p[:57] + "…"), p))
            elif os.path.isfile(p):
                nm = os.path.basename(p); out.append(("🎬  " + (nm if len(nm) < 56 else nm[:53] + "…"), p))
        return out

    def use_recent(self, p):
        if site(p): self.v["url"].set(p)
        elif os.path.isfile(p): self.v["video"].set(p)

    def show_recent(self):
        t = self.t; m = tk.Menu(self, tearoff=0, bg=t["panel"], fg=t["fg"], activebackground=t["accent"], activeforeground=t["on"], font=(FONT, 9))
        items = self.recent_items()
        if not items: m.add_command(label="Nothing here yet - videos and links you use show up here", state="disabled")
        for txt, p in items: m.add_command(label=txt, command=lambda p=p: self.use_recent(p))
        if items: m.add_separator(); m.add_command(label="Clear this list", command=lambda: (setattr(self, "recent", []), self.save()))
        b = self.recent_btn
        try: m.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())
        finally: m.grab_release()

    def restore_geometry(self, g, zoomed=False):
        m = re.fullmatch(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)", str(g or ""))
        if not m: return
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight(); w, h, x, y = map(int, m.groups())
        w, h = min(max(w, min(1000, sw - 40)), sw), min(max(h, min(640, sh - 90)), sh - 50)
        x, y = min(max(x, 0), max(0, sw - w)), min(max(y, 0), max(0, sh - h - 40))        # always fully on the (main) screen, also after a monitor was unplugged
        self.geometry(f"{w}x{h}+{x}+{y}")
        if zoomed:
            try: self.state("zoomed")
            except tk.TclError: pass

    def close_settings(self):
        self.save()
        if self.sw and self.sw.winfo_exists(): self.sw.destroy()

    def apply_perf(self):
        sp = self.v["speed"].get(); sc.SPEECH_SPEED = sp if sp in sc.SPEECH_SPEEDS else "balanced"
        pl = self.v["parallel"].get(); sc.PARALLEL = int(pl) if pl.isdigit() else 0

    def perf_changed(self): self.apply_perf(); self.refresh_eta(); self.save()

    def apply_output(self):
        try: sc.OUT.update(mbps=sc.QUALITY_MBPS[self.oq.get()], res=sc.RESOLUTIONS[self.ores.get()], fps=int(self.ofps.get()))
        except Exception: pass

    def out_changed(self, save=True):
        self.apply_output()
        pw, ph = sc.out_dims(True); lw, lh = sc.out_dims(False)
        self.out_sum.set(f"Shorts {pw}×{ph}   ·   Long-form {lw}×{lh}   ·   {sc.OUT['fps']} fps   ·   {sc.OUT['mbps']} Mbps\n"
                         f"≈ {fmt_size(sc.est_size_mb(60))} per minute of video  (a 10-minute recap ≈ {fmt_size(sc.est_size_mb(600))})")
        self.refresh_eta()
        if save: self.save()

    def draw_swatches(self):
        c = self.sw_canvas; c.delete("all")
        for i, (name, t) in enumerate(THEMES.items()):
            x0, y0, sel = 6 + (i % SW_COLS) * SW_STEP, 6 + (i // SW_COLS) * SW_ROW, name == self.v["theme"].get()
            rrect(c, x0, y0, x0 + SW_STEP - 8, y0 + SW_ROW - 8, 14, fill=t["bg"], outline=self.t["accent"] if sel else t["mute"], width=3 if sel else 1)
            rrect(c, x0 + 8, y0 + 7, x0 + SW_STEP - 16, y0 + 31, 8, fill=t["panel"], outline="")
            rrect(c, x0 + 8, y0 + 7, x0 + 66, y0 + 31, 8, fill=t["accent"], outline=""); c.create_oval(x0 + 80, y0 + 11, x0 + 96, y0 + 27, fill=t["accent2"], outline="")
            c.create_text(x0 + (SW_STEP - 8) // 2, y0 + 44, text=name, font=(FONT, 9, "bold"), fill=t["fg"])

    def swatch_click(self, e):
        col, row = (e.x - 6) // SW_STEP, (e.y - 6) // SW_ROW; i = row * SW_COLS + col
        if 0 <= col < SW_COLS and 0 <= i < len(THEMES): self.v["theme"].set(list(THEMES)[i]); self.apply_theme(); self.save()

    def save(self):
        if self.skip_save: return
        d = {k: self.v[k].get() for k in ("theme", "out", "model", "device", "cookies", "quality", "mascot", "speed", "parallel")}
        d.update(mode=self.mode.get(), done="sound" if self.done_act.get() in POWER_ACTS else self.done_act.get(), auto_update=self.auto_update.get(), gpu_enc=self.gpu_enc.get(), cal=round(self.cal, 3),
                 oq=self.oq.get(), ores=self.ores.get(), ofps=self.ofps.get(), preset=self.sel_preset.get(), look=self.get_look(),
                 opts={**{k: x.get() for k, x in self.o.items()}, "lang_name": self.lang_name.get()},
                 recap={**{k: self.v[k].get() for k in ("rmin", "rmax", "split", "psplit", "pcount", "pmin", "gsens", "gmin")}, "whole": bool(self.rwhole.get())})
        try: d.update(self.cfg20())
        except Exception: pass
        try: d.update(self.cfg21())
        except Exception: pass
        try: d.update(self.cfg22())
        except Exception: pass
        try:
            d.update(awake=bool(self.awake_v.get()), lowprio=bool(self.lowprio_v.get()), recent=list(self.recent)[:RECENT_MAX], seen=self.seen_ver, music_own=self.music_own,
                     zoomed=self.state() == "zoomed")
            if self.state() == "normal": d["win"] = self.geometry()
        except Exception: pass
        try:
            with open(CFG, "w", encoding="utf-8") as f: json.dump(d, f)
        except Exception: pass

    def quit_app(self):
        self.save(); sc.CANCEL.set(); sc.kill_all(); self.set_awake(False); self.stop_sound(); self.destroy()

    # ---------- running jobs ----------
    def on_prog(self, f, label=""):
        bi, bn = getattr(self, "bi", 0), getattr(self, "bn", 1)
        self.pct, self.plabel = ((bi + f) / bn, f"Video {bi + 1}/{bn} · {label}") if bn > 1 else (f, label)

    def pump(self):
        try:
            while True:
                t = self.q.get_nowait()
                if callable(t):
                    try: t()
                    except Exception: log_error(traceback.format_exc())
                    continue
                self.log.insert("end", t); self.log.see("end")
                if int(self.log.index("end-1c").split(".")[0]) > 3000: self.log.delete("1.0", "1000.0")
                m = re.findall(r"\[download\]\s+(\d+(?:\.\d+)?)%", t)
                if m: self.pct, self.plabel = float(m[-1]) / 100, "Downloading"
        except queue.Empty: pass
        if self.busy:
            p, el = self.pct, time.time() - self.t0
            self.bar["value"] = p * 100; self.pctv.set(f"{p:.0%}")
            self.status.set((self.plabel or "Working…") + (f"  ·  about {fmt(el * (1 - p) / p)} left" if p > .03 else ""))
        self.after(150, self.pump)

    def work(self, fn, kind=""):
        if self.busy: return messagebox.showinfo("VTuber Clipper", "I'm already busy with something~ wait for it to finish or press Stop.")
        if kind in RENDER_JOBS and not self.disk_ok(kind): return
        sc.CANCEL.clear(); self.busy, self.failed, self.done, self.cancelled = True, False, False, False
        self.job_mode = kind; self.cancel_power(); self.set_awake(True); self.hook22("start", kind)
        self.pct, self.plabel, self.t0 = 0.0, "", time.time()
        self.make_btn.state(["disabled"]); self.stop_btn.state(["!disabled"])

        def go():
            try:
                with contextlib.redirect_stdout(QWriter(self.q)): fn()
                self.q.put("\nDone.\n")
            except Exception as e:
                if "Cancelled" in str(e): self.cancelled = True; self.q.put("\nStopped.\n")
                else: self.failed = True; self.q.put(f"\nError: {e}\n"); log_error(traceback.format_exc())
                self.est_total = 0
            self.busy = False
            if self.est_total and not (self.failed or self.cancelled): self.calibrate(time.time() - self.t0)
            self.ui(self.finish)
        threading.Thread(target=go, daemon=True).start()

    def stop(self):
        sc.CANCEL.set(); sc.kill_all(); self.status.set("Stopping…")

    def finish(self):
        self.set_awake(False)
        self.make_btn.state(["!disabled"]); self.stop_btn.state(["disabled"]); self.plabel = ""; self.bi, self.bn = 0, 1
        bad = self.failed or self.cancelled
        self.bar["value"] = 0 if bad else 100; self.pctv.set("—" if bad else "100%"); self.done = not bad
        if not bad: self.cheer_until = self.frame + 200                  # she celebrates for about 15 seconds
        self.status.set("Something went wrong — see Details" if self.failed else "Stopped" if self.cancelled else f"Finished in {fmt(time.time() - self.t0)} ✿")
        if not bad and getattr(self, "job_mode", "") == "moments" and self.moments: self.status.set(f"Found {len(self.moments)} moments in {fmt(time.time() - self.t0)} ✿")
        if not bad and getattr(self, "job_mode", "") == "games": self.status.set(f"Found {len(self.games)} part{'s' if len(self.games) != 1 else ''} in {fmt(time.time() - self.t0)} ✿  check the list")
        if self.failed: self.toggle_log(True)
        if self.mode.get() == "clips" and not bad: self.refresh_clips()
        if not bad and getattr(self, "job_mode", "") == "shorts": self.status.set(self.status.get() + "  ·  see them in 🖼 My clips")
        if not bad and getattr(self, "job_mode", "") == "post": self.status.set(f"Your post is ready in {fmt(time.time() - self.t0)} ✿  copy what you like")
        if not bad and getattr(self, "job_mode", "") == "twitter": self.status.set(f"Your X video and posts are ready in {fmt(time.time() - self.t0)} ✿")
        self.refresh_eta(); self.refresh_made()
        self.hook22("finish", bad)
        if not bad: self.after_job(time.time() - self.t0)

    # ---------- what to do when a job is finished ----------
    def chime(self):
        try:
            f = os.path.join(APP_DIR, "chime.wav")
            if sys.platform.startswith("win") and os.path.isfile(f):
                import winsound
                winsound.PlaySound(f, winsound.SND_FILENAME | winsound.SND_ASYNC)
            else: self.bell()
        except Exception:
            try: self.bell()
            except Exception: pass

    def after_job(self, secs):
        """Called when a job ended well. Short jobs stay quiet; sleep / shut down only follow jobs that made videos."""
        act, mode = self.done_act.get(), getattr(self, "job_mode", "")
        if act == "nothing" or not mode: return
        if secs >= 15 or act in POWER_ACTS and mode in RENDER_JOBS: self.chime()
        if act == "folder" and mode in RENDER_JOBS: open_path(self.v["out"].get())
        elif act in POWER_ACTS and mode in RENDER_JOBS:
            self.done_act.set("sound"); self.save()                       # applies to this run only
            self.power_countdown(act)

    def power_countdown(self, kind, secs=60):
        """A window that counts down before the PC sleeps or shuts down, with a button to cancel."""
        self.cancel_power()
        w = tk.Toplevel(self); w.title("VTuber Clipper"); w.configure(bg=self.t["bg"]); w.resizable(False, False); w.transient(self)
        try: w.attributes("-topmost", True)
        except Exception: pass
        msg = tk.StringVar(); st = dict(left=int(secs), job=None)
        bx = ttk.Frame(w, padding=(26, 20, 26, 18)); bx.pack()
        ttk.Label(bx, textvariable=msg, font=(FONT, 12, "bold"), justify="center").pack(pady=(0, 6))
        ttk.Label(bx, text="Your videos are finished and saved ♡", style="Mute.TLabel").pack()
        def stop_it(*a):
            if st["job"]:
                try: self.after_cancel(st["job"])
                except Exception: pass
                st["job"] = None
            if self.power_win is w: self.power_win = None
            try: w.destroy()
            except Exception: pass
        def tick():
            st["job"] = None
            if st["left"] <= 0:
                stop_it(); return self.run_power(kind)
            msg.set(("Shutting down" if kind == "shutdown" else "Going to sleep") + f" in {st['left']} s")
            st["left"] -= 1; st["job"] = self.after(1000, tick)
        ttk.Button(bx, text="Cancel, keep my PC on", style="Accent.TButton", command=stop_it).pack(pady=(14, 0))
        w.protocol("WM_DELETE_WINDOW", stop_it); w.bind("<Escape>", stop_it); self.power_win, self.power_stop = w, stop_it
        tick()
        try: center_over(w, self)
        except Exception: pass

    def cancel_power(self):
        w = getattr(self, "power_win", None)
        if w is not None:
            try: self.power_stop()
            except Exception: self.power_win = None

    def run_power(self, kind):
        try:
            if sys.platform.startswith("win"):
                cmd = ["shutdown", "/s", "/t", "3"] if kind == "shutdown" else ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"]
            else: cmd = ["systemctl", "poweroff" if kind == "shutdown" else "suspend"]
            subprocess.Popen(cmd, **sc.NOWIN)
        except Exception: log_error("couldn't " + kind + ": " + traceback.format_exc())

    def common(self, need_gap=True):
        p = self.v["video"].get().strip().strip('"')
        if not os.path.isfile(p): raise ValueError("Pick or download a VOD first (Step 1) ♡")
        out = self.v["out"].get().strip()
        if not out: raise ValueError("Choose a save folder first.")
        try: os.makedirs(out, exist_ok=True)
        except OSError as e: raise ValueError(f"I can't use that save folder: {e}")
        cf, words = None, [w.strip() for w in self.v["words"].get().split(",") if w.strip()]
        if words:
            cf = os.path.join(tempfile.gettempdir(), "streamclip_bleep.txt")
            with open(cf, "w", encoding="utf-8") as f: f.write("\n".join(words))
        gap = self.num("gap", "Cut silences longer than", 1.2, 6, float) if (need_gap and self.silence.get()) else None
        self.apply_output()
        return dict(video=p, model=self.v["model"].get(), device=self.v["device"].get(), censor=cf, gap=gap, style=self.v["style"].get(), opts=self.opts_dict()), out

    def space_check(self, out, secs, factor):
        need, free = sc.est_size_mb(secs) * factor, shutil.disk_usage(out).free / 2 ** 20
        if free < need: raise ValueError(f"These settings need about {fmt_size(need)} of free space, but the save folder's drive has {fmt_size(free)}. "
                                         "Lower the quality or resolution in Settings → Output, or pick another folder.")

    def make(self): {"long": self.run_long, "moments": self.run_moments, "post": self.run_post, "twitter": self.run_twitter}.get(self.cur_mode(), self.run_shorts)()

    def review_captions(self, items):
        """Called from the worker thread: show the Check captions window and wait for the answer (or for Stop)."""
        box, done = {}, threading.Event()
        def fin(texts): box["t"] = texts; done.set()
        win = []
        self.ui(lambda: win.append(CaptionReview(self, items, fin)))
        self.q.put("\nWaiting for you to check the captions…\n"); t0 = time.time()
        while not done.wait(.25):
            if sc.CANCEL.is_set():
                self.ui(lambda: [w.destroy() for w in win if w.winfo_exists()]); break
        self.t0 += time.time() - t0                              # the time you spent reading doesn't count for the estimate
        sc.check_cancel()
        return box.get("t") or {}

    def remember_fixes(self, pairs):
        """Corrected words become 'Fix words' entries, so the same mistake is fixed automatically next time."""
        have = self.o["fixes"].get(); new = []
        known = {tuple(k) for k, _ in sc.parse_fixes(have)}
        for before, after in pairs:
            for line in sc.fix_pairs(before, after):
                key = tuple(x for x in (sc.clean(w) for w in line.partition("=")[0].split()) if x)
                if key and key not in known: known.add(key); new.append(line)
        if new:
            self.o["fixes"].set((have.rstrip().rstrip(",;") + "\n" if have.strip() else "") + "\n".join(new))
            self.q.put("Remembered for next time: " + ", ".join(new) + "\n")

    def run_shorts(self, windows=None):
        try:
            c, out = self.common()
            vids = [c["video"]] if windows else (self.videos() or [c["video"]])
            n = len(windows) if windows else self.num("n", "How many clips", 1, 30)
            lo, hi = self.num("lmin", "Shortest clip", 10, 120), self.num("lmax", "Longest clip", 10, 120)
            if lo > hi: raise ValueError("The shortest clip can't be longer than the longest clip.")
            self.space_check(out, (sum(e - s for s, e in windows) if windows else n * hi) * len(vids), 1.3)
            base = dict(fx=self.fxdict(), n=n, len_min=lo, len_max=hi, layout=self.v["layout"].get(), cam=self.v["cam"].get() or None,
                        no_silence=not self.silence.get(), no_captions=not self.caps.get(), out=out, windows=windows,
                        review=self.review_captions if self.o["review"].get() else None,
                        emote_review=self.review_emotes if (self.o["emotes"].get() and self.o["emote_review"].get()) else None)
            args = [argparse.Namespace(**{**c, "video": v_}, **base) for v_ in vids]
        except Exception as e: return messagebox.showerror("VTuber Clipper", str(e))

        def fn():
            for i, a in enumerate(args):
                self.bi, self.bn = i, len(args)
                if len(args) > 1: print(f"\n=== VOD {i + 1} of {len(args)}: {os.path.basename(a.video)} ===")
                sc.cmd_shorts(a)
        self.start("shorts", fn, len(args))

    def recap_range(self):
        try: lo, hi = float(self.v["rmin"].get()), float(self.v["rmax"].get())
        except ValueError: return 10.0, 15.0
        return (lo, hi) if lo <= hi else (hi, lo)

    def recap_minutes(self):
        """About how many minutes of video the recap will be in total (for the time estimate)."""
        lo, hi = self.recap_range(); m = max(.5, (lo + hi) / 2)
        if self.v["split"].get() == "games":
            gc = self.v["gcount"].get(); n = len(self.games) if self.games else (int(gc) if gc.isdigit() else 3)
            return m * max(1, n)
        return m

    def recap_what(self):
        lo, hi = self.recap_range(); txt = f"{lo:g}–{hi:g} min" if lo != hi else f"{lo:g} min"; sp = self.v["split"].get()
        if sp == "games":
            n = len(self.games) or (int(self.v["gcount"].get()) if self.v["gcount"].get().isdigit() else 0)
            return f"{n or 'a video per game,'} videos of {txt} each" if n else f"a video per game ({txt} each)"
        return f"a {txt} recap" + (" in parts" if sp == "count" else "")

    def long_label(self):
        sp = self.v["split"].get()
        if sp != "none" and self.rwhole.get(): return "✂  Cut into parts"
        return {"none": "🎞  Build my recap", "count": "🎞  Build my recap in parts", "games": "🎞  Build a video per game"}.get(sp, "🎞  Build my recap")

    def run_games(self):
        try:
            c, out = self.common(need_gap=False)
            gc = self.v["gcount"].get(); cnt = int(gc) if gc.isdigit() else None
            gm = self.num("gmin", "Shortest part", 1, 180, float)
        except Exception as e: return messagebox.showerror("VTuber Clipper", str(e))
        a = argparse.Namespace(**c, cam=self.v["cam"].get() or None, sens=self.v["gsens"].get(), count=cnt, min_minutes=gm)
        video = c["video"]
        self.gnote.set("Looking through the video… (this can take a few minutes for a long stream)")

        def fn():
            g = sc.cmd_games(a)
            self.ui(lambda: self.show_games(g, video))
        self.start("games", fn)

    def run_long(self):
        try:
            c, out = self.common()
            vids = self.videos() or [c["video"]]
            lo, hi = self.num("rmin", "Shortest length", 1, 120, float), self.num("rmax", "Longest length", 1, 180, float)
            if lo > hi: raise ValueError("The shortest length can't be longer than the longest length.")
            split = self.v["split"].get() if self.v["split"].get() in SPLIT_NAMES else "none"
            whole = bool(self.rwhole.get()) and split != "none"
            extra = dict(split=split, whole=whole, games=None, cam=self.v["cam"].get() or None, sens=self.v["gsens"].get(),
                         emote_review=self.review_emotes if (self.o["emotes"].get() and self.o["emote_recap"].get() and self.o["emote_review"].get()) else None)
            if split == "count" and self.v["psplit"].get() == "length":
                extra.update(split="length", part_minutes=self.num("pmin", "Part length", 1, 120, float))
            elif split == "count": extra.update(part_count=self.num("pcount", "Number of parts", 2, 30))
            n_out = 1
            if split == "games":
                gc = self.v["gcount"].get(); extra.update(game_count=int(gc) if gc.isdigit() else None, game_min_minutes=self.num("gmin", "Shortest part", 1, 180, float))
                if len(vids) == 1:
                    if not self.games or os.path.abspath(self.games_video or "-") != os.path.abspath(vids[0]):
                        messagebox.showinfo("VTuber Clipper", "I haven't looked for the games in this video yet. I'll do that now - then check the list and press the big button again ♡")
                        return self.run_games()
                    extra["games"] = [dict(g) for g in self.games]; n_out = len(self.games)
                else: n_out = 3
            elif split in ("count", "length"): n_out = 1
            if whole:
                need, free = sum(os.path.getsize(v_) for v_ in vids) / 2 ** 20 * 1.05, shutil.disk_usage(out).free / 2 ** 20
                if free < need: raise ValueError(f"The parts need about {fmt_size(need)} of free space, but the save folder's drive has {fmt_size(free)}.")
            else: self.space_check(out, hi * 60 * n_out * len(vids), 2.5)
            fx = dict(pan=self.lpan.get(), cutzoom=self.lcut.get(), intensity=self.fxdict()["intensity"], accent=self.accent_hex())
            tag = "full" if whole else {"highlight": "highlights", "story": "story", "gameplay": "gameplay", "mix": "mix"}[self.v["recipe"].get()]
            args = [argparse.Namespace(**{**c, "video": v_}, **extra, fx=fx, min_minutes=lo, max_minutes=hi, captions=self.lcaps.get(), recipe=self.v["recipe"].get(),
                                       out=os.path.join(out, "Recaps", os.path.splitext(os.path.basename(v_))[0][:60] + f"_{tag}.mp4")) for v_ in vids]
        except Exception as e: return messagebox.showerror("VTuber Clipper", str(e))

        def fn():
            for i, a in enumerate(args):
                self.bi, self.bn = i, len(args)
                if len(args) > 1: print(f"\n=== VOD {i + 1} of {len(args)}: {os.path.basename(a.video)} ===")
                sc.cmd_longform(a)
        self.start("long", fn, len(args))

    def run_moments(self):
        try:
            c, out = self.common(need_gap=False)
            n, lo, hi = self.num("mn", "How many moments", 3, 50), self.num("mlo", "Shortest moment", 10, 120), self.num("mhi", "Longest moment", 10, 120)
            if lo > hi: raise ValueError("The shortest moment can't be longer than the longest moment.")
            query = self.v["mq"].get().strip()
        except Exception as e: return messagebox.showerror("VTuber Clipper", str(e))
        save = os.path.join(out, "Moments", sc.safe_stem(c["video"]) + "_moments.txt")

        def fn():
            ms = sc.find_moments(c["video"], n, lo, hi, c["model"], c["device"], opts=c["opts"], query=query)
            path = ""
            try:
                os.makedirs(os.path.dirname(save), exist_ok=True)
                with open(save, "w", encoding="utf-8") as f: f.write(sc.moments_text(ms) + "\n")
                path = save; print("Saved the list:", save)
            except OSError: pass
            self.ui(lambda: self.show_moments(ms, path, c["video"]))
        self.start("moments", fn)

    def start(self, mode, fn, n_videos=1):
        if self.busy: return self.work(fn)
        self.bi, self.bn = 0, n_videos
        sc.USE_GPU_ENC = self.gpu_enc.get(); self.apply_output()
        raw = self.estimate_now(mode)
        self.est_total = sum(raw.values()) * n_videos if raw else 0
        sc.set_plan(raw) if raw else sc.PLAN.clear()
        self.work(fn, mode)

    def calibrate(self, actual):
        self.cal = min(3.0, max(.3, .6 * self.cal + .4 * actual / max(self.est_total, 1)))
        self.est_total = 0; self.ui(self.save)

    def fxdict(self):
        d = {k: x.get() for k, x in self.fx.items()}
        d["intensity"] = {"Subtle": .5, "Normal": 1.0, "Hype": 1.6}[self.intensity.get()]
        d["accent"] = self.accent_hex()
        return d

    def cur_mode(self): return self.mode.get() if self.mode.get() in ("long", "moments", "post", "twitter") else "shorts"

    # ---------- long-form recap styles ----------
    def rdesc_set(self):
        r = sc.RECIPES[self.v["recipe"].get()]
        extra = {"highlight": "Strongest moments only — each one short and punchy.", "story": "Covers the whole stream, one best stretch from every part.",
                 "gameplay": "Keeps long stretches of action and doesn't cut quiet gameplay.",
                 "mix": "Talking and gameplay mixed: one best stretch from every part of the stream, in order."}[self.v["recipe"].get()]
        self.rdesc.set(f"{extra}  Each moment is about {r['lo']}–{r['hi']} seconds, in the order it happened, with YouTube chapters.")

    def draw_rcards(self):
        c, t = self.rcards, self.t; c.delete("all")
        w = max(c.winfo_width(), 600); n = len(RECIPE_CARDS); cw = (w - 20) // n
        for k, (key, title, sub) in enumerate(RECIPE_CARDS):
            x0, sel = 4 + k * (cw + 8), self.v["recipe"].get() == key
            rrect(c, x0, 4, x0 + cw, 80, 16, fill=t["panel"], outline=t["accent"] if sel else t["entry"], width=3 if sel else 2)
            cx, cy = x0 + 34, 42
            if key == "highlight":                                    # sparkly star
                pts = []
                for j in range(10):
                    rr = 20 if j % 2 == 0 else 8; ang = math.pi * j / 5 - math.pi / 2
                    pts += [cx + rr * math.cos(ang), cy + rr * math.sin(ang)]
                c.create_polygon(pts, fill=t["accent"], outline="")
                c.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill="#ffffff", outline="")
            elif key == "story":                                      # open book
                c.create_polygon(cx - 24, cy - 14, cx, cy - 8, cx, cy + 16, cx - 24, cy + 10, fill=t["accent2"], outline="")
                c.create_polygon(cx + 24, cy - 14, cx, cy - 8, cx, cy + 16, cx + 24, cy + 10, fill=deep(t["accent2"]), outline="")
                for j in range(3): c.create_line(cx - 18, cy - 6 + j * 5, cx - 5, cy - 3 + j * 5, fill="#ffffff", width=2)
            elif key == "gameplay":                                   # game controller
                rrect(c, cx - 24, cy - 12, cx + 24, cy + 12, 10, fill=t["accent"], outline="")
                c.create_rectangle(cx - 17, cy - 2, cx - 7, cy + 1, fill="#fff", outline=""); c.create_rectangle(cx - 13, cy - 6, cx - 10, cy + 5, fill="#fff", outline="")
                c.create_oval(cx + 5, cy - 6, cx + 11, cy, fill="#fff", outline=""); c.create_oval(cx + 11, cy - 1, cx + 17, cy + 5, fill="#fff", outline="")
            else:                                                     # a speech bubble holding a little controller
                rrect(c, cx - 24, cy - 20, cx + 24, cy + 10, 12, fill=t["accent2"], outline="")
                c.create_polygon(cx - 10, cy + 8, cx - 18, cy + 22, cx + 2, cy + 8, fill=t["accent2"], outline="")
                c.create_rectangle(cx - 14, cy - 9, cx - 6, cy - 6, fill="#fff", outline=""); c.create_rectangle(cx - 11, cy - 12, cx - 9, cy - 3, fill="#fff", outline="")
                c.create_text(cx + 9, cy - 8, text="♥", font=("Segoe UI Symbol", 14), fill="#ffffff")
            c.create_text(x0 + 64, 22, text=title, anchor="w", font=(FONT, 11, "bold"), fill=t["fg"])
            c.create_text(x0 + 64, 42, text=sub, anchor="nw", font=(FONT, 8), fill=t["mute"], width=cw - 78)
            if sel: c.create_text(x0 + cw - 10, 14, text="✿", anchor="e", font=("Segoe UI Symbol", 12), fill=t["accent"])

    def rcard_click(self, e):
        w = max(self.rcards.winfo_width(), 600); n = len(RECIPE_CARDS); k = min(n - 1, max(0, int((e.x - 4) // ((w - 20) // n + 8))))
        key = RECIPE_CARDS[k][0]; self.v["recipe"].set(key)
        for var, name in ((self.lpan, "pan"), (self.lcut, "cutzoom")): var.set(bool(sc.RECIPES[key]["fx"][name]))
        self.rdesc_set(); self.draw_rcards()

    # ---------- best moments ----------
    def mom_buttons(self):
        have = bool(self.moments); n = len(self.tree.selection()) if hasattr(self, "tree") else 0
        for b in self.mbtns: b.state(["!disabled"] if have else ["disabled"])
        self.mk_btn.state(["!disabled"] if n else ["disabled"])
        self.trim_btn.state(["!disabled"] if n == 1 else ["disabled"])

    def fill_moments(self, select=None):
        ms = sorted(self.moments, key=(lambda m: m["start"]) if self.v["msort"].get() == "In stream order" else (lambda m: -m["score"]))
        self.mview = ms; self.tree.delete(*self.tree.get_children())
        for i, m in enumerate(ms):
            stars = "★" * max(1, round(m["score"] / 20)) + "☆" * (5 - max(1, round(m["score"] / 20)))
            what = ", ".join(m["tags"]) + (f"  ·  “{m['text']}”" if m["text"] else "")
            self.tree.insert("", "end", iid=str(i), tags=("odd",) if i % 2 else (),
                             values=(i + 1, sc.hms(m["start"]), f"{m['end'] - m['start']:.0f}s", f"{stars} {m['score']}", what))
        if select is not None and select in ms:
            k = str(ms.index(select)); self.tree.selection_set(k); self.tree.see(k)
        self.mom_buttons()

    def show_moments(self, ms, saved="", video=""):
        self.moments, self.mom_file, self.mom_video = ms, saved, video; self.fill_moments()
        tail = f"  Saved as {os.path.basename(saved)} in your Moments folder." if saved else ""
        self.mnote.set(f"Found {len(ms)} moments.{tail}  Click rows (Ctrl/Shift for several), double-click to trim, then ‘Make Shorts from selected’." if ms
                       else "I couldn't find anything standing out in this VOD.")

    def mom_target(self):
        """The current video (path, duration), and the moment list reset if it belongs to another video."""
        p = self.v["video"].get().strip().strip('"')
        if not os.path.isfile(p): messagebox.showinfo("VTuber Clipper", "Pick or download a video first (on the left) ♡"); return None
        dur = self.vinfo.get("dur") if self.vinfo.get("path") == p else 0
        dur = dur or sc.probe(p)[0]
        if os.path.abspath(getattr(self, "mom_video", "") or "-") != os.path.abspath(p): self.moments, self.mom_video, self.mom_file = [], p, ""
        return p, dur

    def cached_words(self, p):
        o = self.opts_dict()
        try:
            cp = sc.cache_path(p, o["lang"], o["translate"], o["hint"])
            if cp.exists(): return sc.apply_fixes(sc.read_cached_words(cp, p)[0], o["fixes"])
        except Exception: pass
        return []

    def trim_selected(self):
        sel = self.tree.selection()
        if len(sel) != 1: return messagebox.showinfo("VTuber Clipper", "Click one moment in the list first, then press Trim ♡")
        tg = self.mom_target()
        if not tg: return
        m = self.mview[int(sel[0])]

        def done(a, b):
            m["start"], m["end"] = a, b; m["text"] = sc.first_words(self.cached_words(tg[0]), a, 12) or m["text"]
            if "Edited by you" not in m["tags"]: m["tags"] = m["tags"] + ["Edited by you"]
            self.fill_moments(select=m)
        TrimDialog(self, tg[0], tg[1], m["start"], m["end"], done)

    def add_moment(self):
        tg = self.mom_target()
        if not tg: return
        p, dur = tg
        try: ln = (float(self.v["mlo"].get()) + float(self.v["mhi"].get())) / 2
        except ValueError: ln = 40.0
        a0 = dur * .1

        def done(a, b):
            m = sc.custom_moment(self.cached_words(p), a, b, "My moment"); self.moments.append(m); self.fill_moments(select=m)
            self.mnote.set("Added. Select it and press ‘Make Shorts from selected’ ♡")
        TrimDialog(self, p, dur, a0, min(dur, a0 + ln), done, "Add my own moment ＋")

    def paste_moments(self):
        tg = self.mom_target()
        if not tg: return
        p, dur = tg
        try: ln = (float(self.v["mlo"].get()) + float(self.v["mhi"].get())) / 2
        except ValueError: ln = 40.0

        def done(items):
            w = self.cached_words(p)
            for a, b, lab in items: self.moments.append(sc.custom_moment(w, a, b, lab or "My moment"))
            self.fill_moments(); self.mnote.set(f"Added {len(items)} moment{'s' if len(items) != 1 else ''} from your list ♡  Select them and press ‘Make Shorts from selected’.")
        PasteDialog(self, dur, ln, done)

    def remove_moments(self):
        sel = [self.mview[int(i)] for i in self.tree.selection()]
        if not sel: return messagebox.showinfo("VTuber Clipper", "Click the moments you want to remove first ♡")
        self.moments = [m for m in self.moments if not any(m is x for x in sel)]; self.fill_moments()

    def moments_out(self): return sc.moments_text(self.mview) if self.mview else ""

    def copy_moments(self):
        t = self.moments_out()
        if not t: return
        self.clipboard_clear(); self.clipboard_append(t); self.update(); self.mnote.set("Copied! Paste it into your notes, a doc or a chat ♡")

    def save_moments(self):
        t = self.moments_out()
        if not t: return
        p = filedialog.asksaveasfilename(title="Save timestamps", defaultextension=".txt", initialfile="best_moments.txt", filetypes=[("Text", "*.txt")])
        if p:
            try:
                with open(p, "w", encoding="utf-8") as f: f.write(t + "\n")
                self.mnote.set(f"Saved to {p}")
            except OSError as ex: messagebox.showerror("VTuber Clipper", f"I couldn't save that file: {ex}")

    def make_from_moments(self):
        wins = [(self.mview[int(i)]["start"], self.mview[int(i)]["end"]) for i in self.tree.selection()]
        if not wins: return messagebox.showinfo("VTuber Clipper", "Click one or more moments in the list first ♡")
        if os.path.abspath(self.v["video"].get().strip().strip('"')) != os.path.abspath(getattr(self, "mom_video", "") or "-"):
            return messagebox.showinfo("VTuber Clipper", "This list is from a different VOD than the one selected in Step 1. Press “Find my best moments” again for this VOD ♡")
        self.run_shorts(windows=sorted(wins))

    def open_out(self):
        p = self.v["out"].get().strip()
        if p:
            try: os.makedirs(p, exist_ok=True)
            except OSError: return
            open_path(p)

    # ---------- hardware / estimates ----------
    def vod_changed(self, *a):
        p = self.v["video"].get().strip().strip('"')
        if self.games and os.path.abspath(self.games_video or "-") != os.path.abspath(p or "-"):
            self.games, self.games_video = [], ""; self.fill_games(); self.gnote.set(GNOTE_IDLE)
        if os.path.isfile(p):
            self.add_recent(p)
            def probe():
                info = sc.probe_info(p); self.vod_s = info["dur"]; thumb = ""
                try:
                    d = os.path.join(sc.CACHE_DIR, "thumbs"); os.makedirs(d, exist_ok=True); thumb = os.path.join(d, f"v_{sc._an_key(p)}.png")
                    if not os.path.exists(thumb) and info["w"]:
                        subprocess.run([sc.FF, "-y", "-v", "error", "-ss", f"{min(max(info['dur'] * .2, 0), 600):.1f}", "-i", p, "-frames:v", "1", "-vf",
                                        f"scale={THUMB_W}:{THUMB_H}:force_original_aspect_ratio=decrease", thumb], timeout=40, **sc.NOWIN)
                except Exception: thumb = ""
                self.ui(lambda: self.set_vinfo(p, info, thumb))
            threading.Thread(target=probe, daemon=True).start()
        else:
            self.vod_s = 0.0; self.vinfo = {}; self.vthumb_img = None; self.vname.set(""); self.vmeta.set(""); self.draw_vthumb(); self.refresh_eta()

    def set_vinfo(self, p, info, thumb):
        if p != self.v["video"].get().strip().strip('"'): return                  # the box changed while this was loading
        self.vinfo = dict(path=p, dur=info["dur"], w=info["w"], h=info["h"])
        try: self.vthumb_img = tk.PhotoImage(file=thumb) if thumb and os.path.exists(thumb) else None
        except Exception: self.vthumb_img = None
        nm = os.path.basename(p); self.vname.set(nm if len(nm) <= 44 else nm[:30] + "…" + nm[-11:])
        bits = [fmt(info["dur"]) if info["dur"] else "", f"{info['w']}×{info['h']}" if info["w"] else "unreadable?"]
        if self.cached(): bits.append("✓ transcript")
        if sc.an_cached(p): bits.append("✓ analysed")
        self.vmeta.set("  ·  ".join(b for b in bits if b)); self.draw_vthumb(); self.refresh_eta()

    def draw_vthumb(self):
        c, t = self.vthumb, self.t; c.delete("all"); w, h = THUMB_W, int(c.cget("height"))
        if self.vthumb_img:
            c.create_rectangle(0, 0, w, h, fill="#000", outline=""); c.create_image(w // 2, h // 2, image=self.vthumb_img)
            c.create_rectangle(0, h - 40, w, h, fill="#000000", stipple="gray50", outline="")
            c.create_text(9, h - 28, text=self.vname.get(), anchor="w", fill="#ffffff", font=(FONT, 9, "bold"))
            c.create_text(9, h - 11, text=self.vmeta.get(), anchor="w", fill="#ffffff", font=(FONT, 8))
        else:
            rrect(c, 2, 2, w - 2, h - 2, 16, fill=mix(t["entry"], t["bg"], .4), outline=t["accent2"], width=2, dash=(5, 4))
            c.create_text(w // 2, h // 2 - 20, text="＋", font=(FONT, 32, "bold"), fill=t["accent"])
            c.create_text(w // 2, h // 2 + 22, text="Click to choose a video\nor drop a file here", font=(FONT, 10, "bold"), fill=t["fg"], justify="center")

    def fit_left(self):
        """On short windows the video picture shrinks (it crops to the middle) so the Make button and the save folder always fit."""
        try:
            avail = self.left.winfo_height()
            if avail < 200: return
            cur = int(self.vthumb.cget("height"))
            other = self.left_top.winfo_reqheight() - cur + self.left_bot.winfo_reqheight()
            th = max(84, min(THUMB_H, avail - other - 6))
            if th != cur: self.vthumb.configure(height=th); self.draw_vthumb()
        except tk.TclError: pass

    def hw_scan(self):
        h = sc.detect_hw(); sc.HW = h
        enc = {"h264_nvenc": "NVIDIA NVENC", "h264_amf": "AMD AMF", "h264_qsv": "Intel QuickSync"}.get(h["enc"], "CPU")
        nv = "nvidia" in " ".join(h["gpus"]).lower()
        text = (f"💻 {h['cpu']} · {h['cores']} threads · {h['ram']:.0f} GB\n🎮 {', '.join(h['gpus']) or 'no GPU found'}  ·  "
                f"Video: {enc}  ·  Speech: {'GPU' if h['cuda_ok'] else 'CPU' + (' (install the GPU pack in Settings for faster)' if nv else '')}")
        def done(): self.hw_text = text; self.hwv.set(text); self.refresh_eta()
        self.ui(done)

    def cached(self):
        try:
            o = self.opts_dict(); return sc.cache_path(self.v["video"].get().strip().strip('"'), o["lang"], o["translate"], o["hint"]).exists()
        except Exception: return False

    def an_done(self):
        try: return sc.an_cached(self.v["video"].get().strip().strip('"'))
        except Exception: return False

    def estimate_now(self, mode=None):
        if not self.vod_s or not self.hw_text: return None
        sc.USE_GPU_ENC = self.gpu_enc.get(); self.apply_output(); self.apply_perf()
        try:
            if (mode or self.cur_mode()) == "twitter":
                return sc.estimate(self.vod_s, "twitter", 1, min(self.vod_s, float(self.v["x_max"].get() or 140)), 1, self.v["model"].get(), self.v["device"].get(),
                                   self.cached(), an_cached=self.an_done())
            m_ = mode or self.cur_mode()
            if m_ == "long" and self.v["split"].get() != "none" and self.rwhole.get(): m_ = "cut"
            return sc.estimate(self.vod_s, m_, int(float(self.v["n"].get())), (float(self.v["lmin"].get()) + float(self.v["lmax"].get())) / 2,
                               self.recap_minutes(), self.v["model"].get(), self.v["device"].get(), self.cached(),
                               an_cached=self.an_done(), vhs=bool(self.fx["vhs"].get()))
        except Exception: return None

    def refresh_ready(self):
        """Three-line checklist above the Make button: what is done, what still needs you."""
        if not hasattr(self, "readyv"): return
        mode, rows = self.cur_mode(), []
        have = os.path.isfile(self.v["video"].get().strip().strip('"'))
        if not have: rows.append("○  Choose or download a video (above)")
        if mode == "shorts":
            p = next((q for q in self.all_presets() if q["id"] == self.sel_preset.get()), None)
            rows.append("✓  Look: " + (p["name"] if p else "custom"))
            if sc.needs_cam(self.v["layout"].get(), {"custom_layout": self.o["custom_layout"].get()}):
                rows.append("✓  Cam area set" if self.v["cam"].get() else "○  Set the cam area (Quick setup)")
        elif mode == "long":
            rows.append("✓  Style: " + self.v["recipe"].get())
            if self.v["split"].get() == "games":
                same = self.games and os.path.abspath(self.games_video or "-") == os.path.abspath(self.v["video"].get().strip().strip('"') or "-")
                rows.append(f"✓  {len(self.games)} parts in the list" if same else "○  Press “Find the games” (Recap tab)")
        elif mode == "moments": rows.append("✓  Scans the whole video - nothing is rendered")
        elif mode == "post": rows.append("✓  I listen to the video and write the post")
        elif mode == "twitter": rows.append("✓  Captions, even loudness, at most " + (self.v["x_max"].get() or "140") + " s")
        self.readyv.set("\n".join(rows)); self.after_idle(self.fit_left)

    def refresh_eta(self):
        if not hasattr(self, "make_btn"): return
        self.refresh_ready()
        mode = self.cur_mode()
        if mode == "long": lab = self.long_label()
        elif mode == "moments": lab = "🔎  Find best moments"
        elif mode == "post": lab = "📝  Write my post"
        elif mode == "twitter": lab = "🐦  Make it for X"
        else:
            try: k = int(float(self.v["n"].get())); lab = f"✨  Make {k} Short{'s' if k != 1 else ''}"
            except Exception: lab = "✨  Make my Shorts"
        self.make_btn.configure(text=lab)
        if not self.hw_text: return
        raw = self.estimate_now()
        if not raw: self.etav.set("Pick a video to see how long this takes ♡"); self.eta2.set(""); return
        c = self.cal; vertical = mode == "shorts"
        if mode == "long" and "Transcribing" not in raw:
            self.etav.set(f"⏱ about {fmt(sum(raw.values()) * c)} to cut it into parts"); self.eta2.set("The stream is only cut - nothing is re-encoded, no speech model is needed."); return
        flags = "  " + "  ".join(x for x in ("✓ transcript saved" if self.cached() else "", "✓ analysed" if self.an_done() else "") if x)
        flags = ("\n" + flags.strip()) if flags.strip() else ""
        parts = f"transcribe {fmt(raw['Transcribing'] * c)} · analyze {fmt(raw['Analyzing'] * c)}" + (f" · render {fmt(raw['Rendering'] * c)}" if "Rendering" in raw else "")
        if mode == "moments":
            self.etav.set(f"⏱ about {fmt(sum(raw.values()) * c)} to scan the whole video"); self.eta2.set(f"Nothing is rendered — you get a list of timestamps.\n{parts}{flags}"); return
        if mode == "post":
            self.etav.set(f"⏱ about {fmt(sum(raw.values()) * c)} to listen and write"); self.eta2.set(f"Nothing is rendered — you get text to copy.{flags}"); return
        if mode == "twitter":
            self.etav.set(f"⏱ about {fmt(sum(raw.values()) * c)} for your X video"); self.eta2.set(f"💾 1080p · up to {self.v['x_max'].get()} s · H.264 / AAC\n{parts}{flags}"); return
        try:
            hi = int(float(self.v["lmax"].get()))
            secs = int(float(self.v["n"].get())) * hi if vertical else self.recap_minutes() * 60
        except Exception: secs = 0
        what = f"{self.v['n'].get()} shorts × {self.v['lmin'].get()}–{self.v['lmax'].get()}s" if vertical else self.recap_what()
        W, H = sc.out_dims(self.v["aspect"].get() if vertical else "16:9")
        wk = sc.auto_workers(int(float(self.v["n"].get() or 1)), self.v["aspect"].get()) if vertical else 1
        self.etav.set(f"⏱ about {fmt(sum(raw.values()) * c)} for {what}")
        self.eta2.set(f"💾 {W}×{H} · {sc.OUT['fps']} fps · ≈ {fmt_size(sc.est_size_mb(secs))}" + (f" · {wk} clips at once" if wk > 1 else "") + f"\n{parts}{flags}")


    # ---------- Post helper + Twitter ----------
    def textbox(self, parent, key, label, height=3):
        fr = ttk.Frame(parent); fr.pack(fill="x", pady=(8, 0))
        top = ttk.Frame(fr); top.pack(fill="x")
        lb = ttk.Label(top, text=label, font=(FONT, 10, "bold")); lb.pack(side="left"); self.pl[key] = lb
        ttk.Button(top, text="📋 Copy", command=lambda k=key: self.copy_text(self.pt[k].get("1.0", "end").strip(), "Copied")).pack(side="right")
        t = tk.Text(fr, height=height, wrap="word", relief="flat", padx=8, pady=6, font=(FONT, 10), bg=self.t["entry"], fg=self.t["fg"],
                    insertbackground=self.t["fg"], highlightthickness=0, undo=True)
        t.pack(fill="x", pady=(3, 0)); self.pt[key] = t; self.texts.append(t)
        return t

    def settext(self, key, text, label=None):
        t = self.pt[key]; t.delete("1.0", "end"); t.insert("1.0", text or "")
        if label is not None: self.pl[key].configure(text=label)

    def build_posthelper(self, P):
        o = self.o
        hh = ttk.Frame(P); hh.pack(fill="x"); self.step(hh, "📝  Post helper").pack_configure(pady=(2, 4))
        ttk.Label(P, text="Choose your finished short on the left and press “Write my post”. I listen to it, then write title ideas, a YouTube description and hashtags "
                          "that suit YouTube Shorts, TikTok, Instagram Reels and X.", style="Mute.TLabel", wraplength=680, justify="left").pack(anchor="w")
        f = ttk.Frame(P); f.pack(fill="x", pady=(10, 0)); f.columnconfigure(1, weight=1); f.columnconfigure(3, weight=1)
        for r_, (lbl, key) in enumerate((("Game", "game"), ("Channel / name", "channel"), ("@handle", "handle"), ("Your hashtags", "tags"))):
            col = (r_ % 2) * 2
            ttk.Label(f, text=lbl).grid(row=r_ // 2, column=col, sticky="w", padx=(0 if col == 0 else 16, 6), pady=3)
            ttk.Entry(f, textvariable=o[key]).grid(row=r_ // 2, column=col + 1, sticky="we")
        ttk.Label(P, text="Leave Game empty and I try to find it in the file name and in what you say. Your hashtags are always used first.", style="Mute.TLabel").pack(anchor="w", pady=(2, 0))
        ttk.Label(P, text="Links for the description (Twitch, Discord, socials - one per line)").pack(anchor="w", pady=(8, 2))
        self.links_txt = tk.Text(P, height=3, wrap="word", relief="flat", padx=8, pady=6, font=(FONT, 10), bg=self.t["entry"], fg=self.t["fg"], insertbackground=self.t["fg"], highlightthickness=0)
        self.links_txt.pack(fill="x"); self.texts.append(self.links_txt)
        cr = ttk.Frame(P); cr.pack(fill="x", pady=(6, 0))
        ttk.Checkbutton(cr, text="I'm a VTuber (adds #VTuber)", variable=self.p_vtuber).pack(side="left", padx=(0, 18))
        rc = ttk.Checkbutton(cr, text="Add #fyp on TikTok", variable=self.p_reach); rc.pack(side="left")
        self.tip(rc, "Broad tags like #fyp are crowded and most guides say they don't help reach. Off by default.")
        self.pres = ttk.Frame(P)
        ttk.Separator(self.pres, orient="horizontal").pack(fill="x", pady=(14, 8))
        ttk.Label(self.pres, textvariable=self.heard_v, style="Mute.TLabel", wraplength=680, justify="left").pack(anchor="w")
        bar = ttk.Frame(self.pres); bar.pack(fill="x", pady=(8, 4))
        pb = Pills(self, bar, self.pr_sub, PSUBS, size=10, h=34, pad=15); pb.pack(side="left"); self.pills.append(pb)
        ttk.Button(bar, text="🔄 Another idea", style="Accent.TButton", command=self.post_again).pack(side="right")
        self.pr_pages = {k: ttk.Frame(self.pres) for k, _ in PSUBS}
        for i in range(6): self.textbox(self.pr_pages["titles"], f"t{i}", f"Idea {i + 1}", 2)
        self.textbox(self.pr_pages["yt"], "yt_title", "Title (keep it under ~60 characters)", 1)
        self.textbox(self.pr_pages["yt"], "yt_desc", "Description", 11)
        self.textbox(self.pr_pages["yt"], "yt_tags", "Hashtags", 1)
        ttk.Label(self.pr_pages["yt"], text="YouTube shows the first three hashtags above the title, so the best ones come first. 3-5 is plenty.", style="Mute.TLabel").pack(anchor="w", pady=(4, 0))
        self.textbox(self.pr_pages["tt"], "tt_cap", "Caption", 5)
        self.textbox(self.pr_pages["tt"], "tt_tags", "Hashtags", 1)
        ttk.Label(self.pr_pages["tt"], text="3-5 specific hashtags beat a long list: your game, what happens, and your community.", style="Mute.TLabel").pack(anchor="w", pady=(4, 0))
        self.textbox(self.pr_pages["ig"], "ig_cap", "Caption", 5)
        self.textbox(self.pr_pages["ig"], "ig_tags", "Hashtags", 1)
        ttk.Label(self.pr_pages["ig"], text="Instagram now allows at most 5 hashtags on a post - these 5 are picked for the clip.", style="Mute.TLabel").pack(anchor="w", pady=(4, 0))
        for i in range(5): self.textbox(self.pr_pages["x"], f"px{i}", f"Post {i + 1}", 2)
        self.textbox(self.pr_pages["x"], "px_tags", "3 hashtags (X itself suggests 1-2 - drop one if you like)", 1)
        fb = ttk.Frame(self.pres); fb.pack(fill="x", pady=(12, 0))
        ttk.Button(fb, text="📂 Open the saved text file's folder", command=self.open_post_folder).pack(side="left")
        self.pr_sub.trace_add("write", lambda *a: self.show_psub())

    def show_psub(self):
        for k, f in self.pr_pages.items():
            if k == self.pr_sub.get(): f.pack(fill="x")
            else: f.pack_forget()
        self.after_idle(lambda: self.scroll.configure(scrollregion=self.scroll.bbox("all")))

    def run_post(self):
        try:
            c, out = self.common(need_gap=False)
            a = argparse.Namespace(video=c["video"], model=c["model"], device=c["device"], out=out, opts=self.opts_dict(), seed=0,
                                   links=self.links_txt.get("1.0", "end").strip(), reach=bool(self.p_reach.get()), vtuber=bool(self.p_vtuber.get()))
        except Exception as e: return messagebox.showerror("VTuber Clipper", str(e))
        self.pseed = 0

        def fn():
            kit = sc.cmd_postkit(a)
            self.ui(lambda: self.show_post(kit, a))
        self.start("post", fn)

    def post_kit_for(self, words, a, seed, late, name_hint=None, **kw):
        o = a.opts; extra = [t.strip("#") for t in re.split(r"[\s,]+", o["tags"]) if t.strip("#")]
        return vpost.make_kit(words, game=o["game"], channel=o["channel"], handle=o["handle"], links=getattr(a, "links", ""), hint=o["hint"],
                              name_hint=name_hint or os.path.splitext(os.path.basename(a.video))[0], seed=seed, late_peak=late,
                              reach=bool(getattr(a, "reach", False)), vtuber=bool(getattr(a, "vtuber", True)), extra=extra, **kw)

    def show_post(self, kit, a):
        self.pkit, self.pargs = kit, a
        self.heard_v.set("What I heard: “" + (kit.get("heard") or "(no speech found - the ideas below are general)") + "”   ·   hype " + (str(kit.get("hype")) if kit.get("hype") is not None else "?") + "/100")
        ts = kit["titles"] + [""] * 6
        for i in range(6): self.settext(f"t{i}", ts[i], f"Idea {i + 1}" if ts[i] else f"Idea {i + 1} (none)")
        yt = kit["youtube"]; self.settext("yt_title", yt["title"]); self.settext("yt_desc", yt["description"]); self.settext("yt_tags", " ".join(yt["hashtags"]))
        self.settext("tt_cap", kit["tiktok"]["caption"]); self.settext("tt_tags", " ".join(kit["tiktok"]["hashtags"]))
        self.settext("ig_cap", kit["reels"]["caption"]); self.settext("ig_tags", " ".join(kit["reels"]["hashtags"]))
        ps = kit["twitter"]["posts"] + [None] * 5
        for i in range(5): self.settext(f"px{i}", ps[i]["text"] if ps[i] else "", f"Post {i + 1}" + (f"  ({ps[i]['label']})" if ps[i] else ""))
        self.settext("px_tags", " ".join(kit["twitter"]["hashtags"]))
        self.pres.pack(fill="x"); self.show_psub()
        self.after_idle(lambda: (self.update_idletasks(), self.scroll.configure(scrollregion=self.scroll.bbox("all")), self.scroll.yview_moveto(.32)))

    def post_again(self):
        if not self.pkit or not self.pargs: return
        self.pseed += 1; a = self.pargs
        kit = self.post_kit_for(self.pkit["words"], a, self.pseed, self.pkit.get("late_peak", False))
        kit.update({k: self.pkit[k] for k in ("hype", "words", "late_peak", "heard", "saved") if k in self.pkit})
        try:
            if kit.get("saved"): open(kit["saved"], "w", encoding="utf-8").write(vpost.kit_text(kit, kit.get("hype")))
        except OSError: pass
        self.show_post(kit, a); self.status.set("Here's another take ♡")

    def open_post_folder(self):
        k = (self.pkit or {}).get("saved") or ""
        open_path(os.path.dirname(k) if k else os.path.join(self.v["out"].get().strip(), "PostKits"))

    # ----- Twitter page -----
    def build_twitter(self, P):
        v = self.v
        hh = ttk.Frame(P); hh.pack(fill="x"); self.step(hh, "🐦  X / Twitter").pack_configure(pady=(2, 4))
        ttk.Label(P, text="Choose a video on the left and press “Make it for X”. I make it ready for X - captions that work with the sound off, even loudness, the best part if it is "
                          "longer than 2:20 - and write post ideas that make people want to watch.", style="Mute.TLabel", wraplength=680, justify="left").pack(anchor="w")
        f = ttk.Frame(P); f.pack(fill="x", pady=(10, 0))
        ttk.Label(f, text="Shape").pack(side="left"); self.combo(f, v["x_shape"], list(X_SHAPES), 18).pack(side="left", padx=(6, 18))
        ttk.Label(f, text="Longest").pack(side="left"); self.spin(f, v["x_max"], 10, 600, 5, 5).pack(side="left", padx=(6, 2)); ttk.Label(f, text="s").pack(side="left", padx=(0, 18))
        cb = ttk.Checkbutton(f, text="💬 Captions", variable=self.x_caps, command=lambda: setattr(self, "x_user", True)); cb.pack(side="left", padx=(0, 18))
        self.tip(cb, "X plays videos muted at first, so captions get more people to watch. Turn off when your video already has captions.")
        ttk.Checkbutton(f, text="# Add 3 hashtags", variable=self.x_tags).pack(side="left")
        ttk.Label(P, textvariable=self.x_note, style="Mute.TLabel", wraplength=680, justify="left").pack(anchor="w", pady=(4, 0))
        ttk.Label(P, text="Free X accounts can post up to 2:20 (512 MB). If you have X Premium, raise “Longest”. Tall videos may look cropped in the feed - 4:5 or square fills it best.",
                  style="Mute.TLabel", wraplength=680, justify="left").pack(anchor="w", pady=(2, 0))
        self.xres_f = ttk.Frame(P)
        ttk.Separator(self.xres_f, orient="horizontal").pack(fill="x", pady=(14, 8))
        ttk.Label(self.xres_f, textvariable=self.x_info, font=(FONT, 10, "bold"), wraplength=680, justify="left").pack(anchor="w")
        br = ttk.Frame(self.xres_f); br.pack(fill="x", pady=(6, 4))
        ttk.Button(br, text="▶ Play it", command=lambda: self.xres and open_path(self.xres["out"])).pack(side="left")
        ttk.Button(br, text="📂 Show in folder", command=lambda: self.xres and self.show_in_folder(self.xres["out"])).pack(side="left", padx=6)
        ttk.Button(br, text="🔄 Another idea", style="Accent.TButton", command=self.x_again).pack(side="right")
        ttk.Label(self.xres_f, text="Pick the post you like - it shows below with your hashtags, ready to copy.", style="Mute.TLabel").pack(anchor="w", pady=(6, 2))
        self.x_rows = ttk.Frame(self.xres_f); self.x_rows.pack(fill="x")
        self.textbox(self.xres_f, "x_final", "Your post", 4)
        ttk.Label(self.xres_f, textvariable=self.x_count, style="Mute.TLabel").pack(anchor="w", pady=(2, 0))

    def x_detect(self):
        """A clip made by this app already has its captions burned in - don't double them (unless the user chose)."""
        p = self.v["video"].get().strip().strip('"')
        if not os.path.isfile(p) or self.x_user: return
        stem = os.path.splitext(p)[0]
        edited = bool(re.search(r"_short\d+$", stem)) or os.path.isfile(stem + ".txt") or os.path.isfile(stem + ".srt")
        self.x_caps.set(not edited)
        self.x_note.set("This clip already has captions, so I left them off. Tick “Captions” if you want them added again." if edited else "")

    def run_twitter(self):
        try:
            c, out = self.common(need_gap=False); mx = self.num("x_max", "Longest video", 10, 600)
            a = argparse.Namespace(video=c["video"], model=c["model"], device=c["device"], out=out, opts=self.opts_dict(), seed=0, shape=X_SHAPES.get(self.v["x_shape"].get(), "auto"),
                                   captions=bool(self.x_caps.get()), max_len=mx, accent=self.accent_hex(), censor=c["censor"])
            self.space_check(out, min(self.vod_s or mx, mx), 1.5)
        except Exception as e: return messagebox.showerror("VTuber Clipper", str(e))
        self.xseed = 0

        def fn():
            res = sc.cmd_twitter(a)
            self.ui(lambda: self.show_x(res, a))
        self.start("twitter", fn)

    def show_x(self, res, a):
        self.xres, self.xargs = res, a
        self.x_info.set(f"✓ {os.path.basename(res['out'])}  ·  {res['dur']:.0f} s  ·  {res['size_mb']:.0f} MB  ·  {res['aspect']}  ·  within X's limits")
        for w in self.x_rows.winfo_children(): w.destroy()
        posts = res["kit"]["twitter"]["posts"]
        for i, p_ in enumerate(posts):
            ttk.Radiobutton(self.x_rows, text=f"{p_['text']}   ·  {p_['label']}", value=i, variable=self.x_pick).pack(anchor="w", pady=2)
        self.x_pick.set(0); self.x_compose()
        self.xres_f.pack(fill="x")
        self.after_idle(lambda: (self.update_idletasks(), self.scroll.configure(scrollregion=self.scroll.bbox("all"))))

    @staticmethod
    def x_len(text):
        """Length the way X counts it: emoji and CJK count double."""
        return sum(2 if ord(ch) > 0x2E7F else 1 for ch in text)

    def x_compose(self):
        if not self.xres: return
        posts = self.xres["kit"]["twitter"]["posts"]
        if not posts: return
        i = max(0, min(self.x_pick.get(), len(posts) - 1)); txt = posts[i]["text"]
        if self.x_tags.get(): txt += "\n\n" + " ".join(self.xres["kit"]["twitter"]["hashtags"])
        self.settext("x_final", txt); n = self.x_len(txt)
        self.x_count.set(f"{n} / 280 characters" + ("   ✓" if n <= 280 else "   - too long for X, shorten it"))

    def x_again(self):
        if not self.xres or not self.xargs: return
        self.xseed = getattr(self, "xseed", 0) + 1; a = self.xargs
        kit = self.post_kit_for(self.xres["words"], a, self.xseed, self.xres.get("late_peak", False), name_hint=os.path.splitext(os.path.basename(a.video))[0])
        self.xres["kit"] = kit; self.show_x(self.xres, a); self.status.set("Here's another take ♡")

    # ---------- my clips ----------
    def clip_files(self):
        out, res = self.v["out"].get().strip(), []
        for sub in ("Shorts", "Recaps", "Twitter", "Montages"):
            for f in glob.glob(os.path.join(out, sub, "**", "*.mp4"), recursive=True):
                try: res.append((os.path.getmtime(f), f))
                except OSError: pass
        return [f for _, f in sorted(res, reverse=True)]

    def kit_of(self, f):
        """Title / description / hype score from the post-kit .txt next to a clip."""
        try: txt = open(os.path.splitext(f)[0] + ".txt", encoding="utf-8").read()
        except OSError: return {}
        m = re.search(r"1\.\s+(.+)", txt); d = re.search(r"DESCRIPTION\n(.*?)\n\nHASHTAGS\n(.*)", txt, re.S); h = re.search(r"HYPE SCORE\s+(\d+)", txt)
        return dict(title=m.group(1).strip() if m else "", desc=(d.group(1).strip() + "\n\n" + d.group(2).strip()) if d else "", hype=int(h.group(1)) if h else None)

    def copy_text(self, text, what="Copied"):
        if not text: return self.status.set("There is no title for this clip - turn on ‘Save title ideas’ in the Posting & files tab ♡")
        self.clipboard_clear(); self.clipboard_append(text); self.update(); self.status.set(f"{what} - paste it into your post ♡")

    def show_in_folder(self, f):
        try:
            if sys.platform.startswith("win"): subprocess.Popen(["explorer", "/select,", os.path.normpath(f)])
            else: open_path(os.path.dirname(f))
        except Exception: pass

    def post_to(self, url, f):
        k = self.kit_of(f); self.copy_text((k.get("title", "") + "\n\n" + k.get("desc", "")).strip(), "Copied the title and description")
        webbrowser.open(url)

    def delete_clip(self, f):
        if not messagebox.askyesno("VTuber Clipper", f"Delete “{os.path.basename(f)}” and everything made with it (subtitles, title ideas, cover picture, transcript)?"): return
        import vcouts
        vcouts.delete_clip_files(f)
        n_ = os.path.normpath(f)
        if n_ in self.marks["fav"]: self.marks["fav"].remove(n_)
        self.marks["posted"].pop(n_, None)
        self.refresh_clips()

    def refresh_clips(self):
        files = self.clip_files_shown()[:40]
        for w in self.clip_grid.winfo_children(): w.destroy()
        self.clip_imgs, self.clip_cards, self.clip_key = {}, {}, object(); key = self.clip_key; out = self.v["out"].get().strip()
        if not files:
            self.clips_note.set(("Nothing matches the filter. " if self.clip_files() else "Nothing here yet. ") + f"Clips you make show up in this gallery, newest first ♡   (looking in {out})"); return
        self.clips_note.set(f"Your {len(files)} newest clips.  Click a picture to play it.  ⋯ More has copy-title, favourites, posted marks and upload shortcuts.")
        cols = max(2, min(5, (max(self.scroll.winfo_width(), 700) - 40) // 188)); t = self.t
        for i, f in enumerate(files):
            card = ttk.Frame(self.clip_grid, padding=(4, 4)); card.grid(row=i // cols, column=i % cols, sticky="n", padx=5, pady=6)
            lab = tk.Label(card, text="…", width=21, height=11, bg=t["entry"], fg=t["mute"], cursor="hand2"); lab.pack(); lab.bind("<Button-1>", lambda e, f=f: open_path(f))
            ttk.Label(card, text=("★ " if self.is_fav(f) else "") + os.path.basename(f), wraplength=168, justify="left", font=(FONT, 9, "bold")).pack(anchor="w", pady=(4, 0))
            meta = tk.StringVar(value=""); ttk.Label(card, textvariable=meta, style="Mute.TLabel", wraplength=168, justify="left").pack(anchor="w")
            row = ttk.Frame(card); row.pack(fill="x", pady=(4, 0))
            ttk.Button(row, text="▶", width=3, command=lambda f=f: open_path(f)).pack(side="left")
            mb = ttk.Menubutton(row, text="⋯ More"); mb.pack(side="left", padx=4)
            mn = tk.Menu(mb, tearoff=0, bg=t["panel"], fg=t["fg"], activebackground=t["accent"], activeforeground=t["on"]); mb["menu"] = mn
            mn.add_command(label="▶  Play", command=lambda f=f: open_path(f)); mn.add_command(label="📂  Show in folder", command=lambda f=f: self.show_in_folder(f))
            mn.add_separator()
            mn.add_command(label="📋  Copy title", command=lambda f=f: self.copy_text(self.kit_of(f).get("title", ""), "Copied the title"))
            mn.add_command(label="📝  Copy description + hashtags", command=lambda f=f: self.copy_text(self.kit_of(f).get("desc", ""), "Copied the description"))
            mn.add_separator()
            for nm, url in (("YouTube Shorts", "https://www.youtube.com/upload"), ("TikTok", "https://www.tiktok.com/creator-center/upload"), ("Instagram", "https://www.instagram.com/")):
                mn.add_command(label=f"⬆  Open {nm} upload (copies title)", command=lambda u=url, f=f: self.post_to(u, f))
            self.card_menu_extras(mn, f, t)
            mn.add_separator(); mn.add_command(label="🗑  Delete", command=lambda f=f: self.delete_clip(f))
            self.clip_cards[f] = (lab, meta)
        threading.Thread(target=self.load_clip_info, args=(files, key), daemon=True).start()

    def load_clip_info(self, files, key):
        d = os.path.join(sc.CACHE_DIR, "thumbs")
        try: os.makedirs(d, exist_ok=True)
        except OSError: pass
        for f in files:
            if key is not self.clip_key: return
            try:
                st = os.stat(f); info = sc.probe_info(f); k = self.kit_of(f)
                th = os.path.join(d, "c_" + hashlib.md5(f"{f}|{st.st_size}|{int(st.st_mtime)}".encode("utf-8", "replace")).hexdigest()[:16] + ".png")
                if not os.path.exists(th):
                    subprocess.run([sc.FF, "-y", "-v", "error", "-ss", f"{min(1.0, info['dur'] / 2):.2f}", "-i", f, "-frames:v", "1", "-vf", "scale=-2:200", th], timeout=30, **sc.NOWIN)
                txt = f"{fmt(info['dur'])} · {fmt_size(st.st_size / 2 ** 20)}" + (f" · 🔥 hype {k['hype']}" if k.get("hype") is not None else "")
                mk_ = self.mark_text(f)
                if mk_: txt += "\n" + mk_
                self.ui(lambda f=f, th=th, txt=txt, key=key: self.set_clip_info(f, th, txt, key))
            except Exception: pass

    def set_clip_info(self, f, th, txt, key):
        if key is not self.clip_key or f not in self.clip_cards: return
        lab, meta = self.clip_cards[f]; meta.set(txt)
        try:
            img = tk.PhotoImage(file=th); self.clip_imgs[f] = img; lab.configure(image=img, text="", width=img.width(), height=img.height())
        except Exception: pass

    def install_gpu(self):
        if sc.cuda_dir(): return messagebox.showinfo("VTuber Clipper", "The GPU speech pack is already installed ♡")
        if not messagebox.askyesno("VTuber Clipper", "Download NVIDIA's CUDA libraries (about 1.4 GB, one time)?\nThis lets speech-to-text run on your NVIDIA GPU. Needs internet."): return
        def fn(): sc.PLAN.clear(); sc.install_cuda(); sc.HW = None; self.hw_scan()
        self.work(fn)

    def pick_cam(self):
        p = self.v["video"].get().strip().strip('"')
        if not os.path.isfile(p): return messagebox.showinfo("VTuber Clipper", "Pick or download a VOD first, then select the model / cam area ♡")
        info = sc.probe_info(p)
        if not info["w"]: return messagebox.showerror("VTuber Clipper", "I couldn't read that video file.")
        CamPicker(self, p, info["dur"] or 60, info["w"], info["h"], self.v["cam"].get(), self.v["cam"].set)

    # ---------- downloading ----------
    def run_cmd(self, cmd):
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", **sc.NOWIN)
        sc.PROCS.add(p); buf = []
        try:
            for line in p.stdout: print(line, end=""); buf.append(line)
            rc = p.wait()
        finally: sc.PROCS.discard(p)
        if sc.CANCEL.is_set(): raise RuntimeError("Cancelled")
        return rc, "".join(buf)

    def update_ytdlp(self):
        print("Updating the downloader...\n")
        try: self.run_cmd(["yt-dlp", "--update-to", "nightly"])
        except FileNotFoundError: print("(downloader not found)\n")
        self.updated = True

    def try_download(self, url, kind, out, fmt_sel, cookies):
        cmd = ["yt-dlp", "--no-playlist", "-f", fmt_sel, "--merge-output-format", "mp4",
               "-o", os.path.join(out, "%(title).80s [%(id)s].%(ext)s"), "--retries", "10", "--fragment-retries", "10",
               "--concurrent-fragments", "4", "--newline", "--no-colors"]
        if cookies != "none": cmd += ["--cookies-from-browser", cookies]
        text = ""
        for extra in ([["--impersonate", "chrome"], []] if kind == "kick" else [[]]):
            rc, t = self.run_cmd(cmd + extra + [url]); text += t
            if rc == 0: return True, text
            if "impersonat" not in t.lower(): break
        return False, text

    def download(self):
        url = self.v["url"].get().strip(); kind = site(url)
        if kind: self.add_recent(url)
        if not kind: return messagebox.showerror("VTuber Clipper", "Paste a Kick, Twitch or YouTube link first ♡")
        out = os.path.join(self.v["out"].get().strip() or os.path.join(HOME, "StreamClips"), "VODs")
        try: os.makedirs(out, exist_ok=True)
        except OSError as e: return messagebox.showerror("VTuber Clipper", f"I can't use that save folder: {e}")

        fmt_sel, cookies, auto = QUALITY[self.v["quality"].get()], self.v["cookies"].get(), self.auto_update.get()   # read window values here, not in the worker thread

        def fn():
            fresh = False
            if auto and not self.updated: self.update_ytdlp(); fresh = True
            before = set(glob.glob(os.path.join(out, "*")))
            try: ok, text = self.try_download(url, kind, out, fmt_sel, cookies)
            except FileNotFoundError: raise RuntimeError("The downloader (yt-dlp) is missing - keep the bin folder next to the app.")
            if not ok and not fresh:
                print("\nFailed - updating the downloader and retrying...\n"); self.update_ytdlp(); ok, text = self.try_download(url, kind, out, fmt_sel, cookies)
            if ok:
                fs = [f for f in glob.glob(os.path.join(out, "*")) if f.lower().endswith((".mp4", ".mkv", ".webm", ".ts", ".mov"))]
                new = [f for f in fs if f not in before] or fs
                if new:
                    path = max(new, key=os.path.getmtime); print("\nSaved:", path); self.ui(lambda: self.v["video"].set(path))
                return
            low = text.lower(); msg = "\nDownload failed.\n"
            if "404" in text: msg += "• HTTP 404: the VOD was deleted/expired (Kick & Twitch remove VODs after days or weeks), or the link isn't a VOD page.\n  Kick: kick.com/<channel>/videos/<id>   Twitch: twitch.tv/videos/<id>\n"
            if any(x in low for x in ("403", "sign in", "subscriber", "login", "private")): msg += "• Looks subscriber-only/private: pick your browser under Settings → Downloads → Use cookies from (while logged in there).\n"
            raise RuntimeError(msg + "• Make sure you're online, then try again.")
        self.work(fn)


def load_private_fonts():
    """Let the app itself use the bundled caption fonts (Windows only; the video renderer loads them on its own)."""
    if not sys.platform.startswith("win"): return
    try:
        import ctypes
        for f in glob.glob(os.path.join(APP_DIR, "fonts", "*.ttf")): ctypes.windll.gdi32.AddFontResourceExW(f, 0x10, 0)
    except Exception: pass


def crash(msg):
    log_error(msg)
    try:
        r = tk.Tk(); r.withdraw()
        messagebox.showerror("VTuber Clipper", "Something went wrong while starting:\n\n" + msg[-900:] + f"\n\n(saved to {LOGF})")
        r.destroy()
    except Exception: pass


try:
    import vc20ui                                  # the 2.0 screens (Picture & voice tab, tools); a partly copied update shows a clear message instead of a bare error
    vc20ui.install(App, sys.modules[__name__]); VC20_ERR = None
except Exception:
    VC20_ERR = traceback.format_exc()
try:
    import vc21ui                                  # the 2.1 screens (Quick setup, Words & buttons, layout designer, trim, montage, planner)
    vc21ui.install(App, sys.modules[__name__]); VC21_ERR = None
except Exception:
    VC21_ERR = traceback.format_exc()
try:
    import vc22ui                                  # the 2.2 screens (Smart finding, Tools window, search / review / remake in My clips)
    vc22ui.install(App, sys.modules[__name__]); VC22_ERR = None
except Exception:
    VC22_ERR = traceback.format_exc()


def main():
    global sc
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    for s in ("stdout", "stderr"):
        if getattr(sys, s) is None: setattr(sys, s, open(os.devnull, "w"))
    os.environ["PATH"] = os.path.abspath(os.path.join(base, "..", "bin")) + os.pathsep + base + os.pathsep + os.environ.get("PATH", "")
    try:
        if VC20_ERR: raise RuntimeError(VC20_ERR[-300:] + "\n\nSome files of the 2.0 update are missing or damaged (vcfx.py, vcouts.py, vc20ui.py). "
                                        "Copy the whole \"app\" folder from the update zip into your VTuberClipper folder again.")
        if VC21_ERR: raise RuntimeError(VC21_ERR[-300:] + "\n\nSome files of the 2.1 update are missing or damaged (vcnew.py, vc21ui.py). "
                                        "Copy the whole \"app\" folder from the update zip into your VTuberClipper folder again.")
        if VC22_ERR: raise RuntimeError(VC22_ERR[-300:] + "\n\nSome files of the 2.2 update are missing or damaged (vcsense.py, vcsmart.py, vcmore.py, vctools.py, vc22ui.py). "
                                        "Copy the whole \"app\" folder from the update zip into your VTuberClipper folder again.")
        global vp, vv, vpost
        import streamclip as engine; sc = engine
        import vcpresets, vcpreview, vcpost; vp, vv, vpost = vcpresets, vcpreview, vcpost
        SENS_NAMES.update({k: x["label"] for k, x in sc.GAME_SENS.items()})
        load_private_fonts()
        App().mainloop()
    except Exception:
        crash(traceback.format_exc())


if __name__ == "__main__":
    main()
