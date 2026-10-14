"""VTuber Clipper 2.1 - the new screens of the app window:
the Quick setup page and the Simple / All options switch, the Words & buttons tab (text on screen, Like / Follow buttons, a voice that reads your words),
the layout designer, trimming and tidying a finished clip, joining clips into a montage, and the post planner.

streamclip_app.py calls install(App, module) once; every function below becomes a method of the App window.
The video work itself lives in vcnew.py (no screens there)."""
import datetime, glob, json, os, re, subprocess, sys, tempfile, threading, time, webbrowser
import tkinter as tk
from tkinter import ttk, messagebox

import vcnew

A = None                    # the app module (streamclip_app), set by install()
METHODS = {}

# --- the new options (the app's OPT_STR list gets these)
NEW_STR = ("text_boxes", "callouts", "custom_layout", "tts_voice", "tts_rate")
# plain names for the tabs of the Shorts page. Simple view shows four of them, "All options" shows every tab except Quick setup.
SUBTABS = [("quick", "Quick setup"), ("smart", "Smart finding"), ("basics", "Clips & layout"), ("text", "Words & buttons"), ("fx", "Effects"), ("captions", "Captions"),
           ("emotes", "Chibi emotes"), ("polish", "Picture & voice"), ("extras", "Logo & music"), ("post", "Posting & files")]
SIMPLE_TABS = ("quick", "smart", "text", "captions", "extras")
TAB_HELP = {
    "quick": "The few things most people change. Pick your look above, then check these. Everything else is under “Show all options”.",
    "smart": "How I find the best moments: I tell laughs, screams, singing, stories and gameplay apart, skip greetings, vary the picks and can learn from the clips you keep.",
    "basics": "How many clips to make, how long they are, what they look like (layout, shape, background) and where your cam is.",
    "text": "Put your own words on a clip, show Like / Follow / Subscribe buttons, and let a voice read your words out loud.",
    "fx": "Zooms, shakes, flashes, sounds on the big moments and other effects. The look you picked above already chose these for you.",
    "captions": "The words that appear while you speak: style, font, colours, language and the title at the start.",
    "emotes": "Pictures of your own model that act out the feeling of what you say. You add the pictures yourself.",
    "polish": "Colour looks, a sharper picture, hiding a spot, a name tag, and effects for your voice.",
    "extras": "Your logo and @name, intro and outro, stickers, background music, bleeps and video fixes.",
    "post": "Title ideas, hashtags, subtitles, a cover picture and how your files are named.",
}
RESET21 = {
    "quick": dict(o=("platform", "fresh", "cap_emoji", "voice_clean", "handle", "cta", "emotes", "post_kit", "cover", "callouts"), v=dict(n="8", lmin="25", lmax="45", style="mix", layout="stack", aspect="9:16")),
    "text": dict(o=("text_boxes", "callouts", "tts_voice", "tts_rate"), v={}),
}
TTS_TEST = "Hi! This is how I will read your words."
DEFAULT_VOICE = "Default voice"


def method(fn):
    METHODS[fn.__name__] = fn; return fn


def install(App, module):
    global A
    A = module
    for k, fn in METHODS.items(): setattr(App, k, fn)
    import vc20ui
    vc20ui.RESET.update(RESET21)


def sc_(): return A.sc


# ================================================================ set-up / saving
@method
def init21(self, cfg):
    """Called from __init__: the state the 2.1 features keep."""
    self.simple = tk.BooleanVar(value=bool(cfg.get("simple", True)))
    self.gal_open = tk.BooleanVar(value=bool(cfg.get("gal_open", True)))
    self.plan = vcnew.clean_plan(cfg.get("plan"))
    self.plan_win, self.plan_job, self.tb, self.tb_busy, self.co_busy = None, None, [], False, False
    self.tab_help, self.tb_note, self.voice_note = tk.StringVar(), tk.StringVar(), tk.StringVar()
    self.co_vars = {k: tk.BooleanVar(value=False) for k in vcnew.CALLOUTS}
    self.sub.set("quick" if self.simple.get() else "basics")


@method
def cfg21(self):
    return dict(simple=bool(self.simple.get()), gal_open=bool(self.gal_open.get()), plan=list(self.plan))


@method
def sub_items(self):
    """The tabs that are showing: four in the simple view, all but Quick setup otherwise."""
    return [(k, n) for k, n in SUBTABS if (k in SIMPLE_TABS if self.simple.get() else k != "quick")]


@method
def view_changed(self, *a):
    """The Simple view / All options button was pressed (or a tip sent you to a tab that only the full view has)."""
    self.view_apply(); self.save()


@method
def view_apply(self):
    keys = [k for k, _ in self.sub_items()]
    self.subbar.items = self.sub_items()
    if self.sub.get() not in keys: self.sub.set("basics" if "basics" in keys else keys[0])          # leaving the simple view lands on Clips & layout
    self.subbar.draw()
    try:
        self.view_btn.configure(text="⚙ Show all options" if self.simple.get() else "✨ Simple view")
        self.update_idletasks(); self.subbar.maxw = None
        self.subbar.fit(self.subbar.master.winfo_width() - 8)
    except tk.TclError: pass
    self.show_sub()


@method
def sync_view(self):
    """Called by show_sub: a tab that the simple view hides was asked for (a shortcut, a tip) - switch to the full view instead of showing nothing."""
    if self.simple.get() and self.sub.get() not in SIMPLE_TABS: self.simple.set(False)
    elif not self.simple.get() and self.sub.get() == "quick": self.simple.set(True)
    self.tab_help.set(TAB_HELP.get(self.sub.get(), ""))


@method
def layout_cell(self, parent):
    """The Layout drop-down with the “design my own” button next to it."""
    f = ttk.Frame(parent); self.pick(f, self.v["layout"], A.LAYOUT_NAMES, 34).pack(side="left")
    self.tip(ttk.Button(f, text="🧩 Design my own…", command=self.open_designer), "Drag the game and the cam where you want them.").pack(side="left", padx=8)
    return f


@method
def scroll_to_tabs(self):
    """After a click on a tab the page jumps so that the tab bar is at the top: the settings show at once, the gallery of looks is just above."""
    try:
        if not getattr(self, "tabs_ready", False) or not self.gal_open.get(): return
        self.update_idletasks(); bb = self.scroll.bbox("all"); total = (bb[3] - bb[1]) if bb else 0
        if total <= self.scroll.winfo_height(): return
        y = self.subbar.master.winfo_rooty() - self.pbody.winfo_rooty() - 6
        self.scroll.yview_moveto(max(0.0, min(1.0, y / total)))
    except tk.TclError: pass


@method
def gallery_toggle(self, *a):
    self.gallery_apply(); self.save()


@method
def gallery_apply(self):
    """Hide / show the gallery of looks (it is tall; a creator who has her look can fold it away)."""
    on = bool(self.gal_open.get())
    if on: self.gal_wrap.pack(fill="x", after=self.pinfo_lbl)
    else: self.gal_wrap.pack_forget()
    try: self.gal_btn.configure(text="▴ Hide looks" if on else "▾ Show looks")
    except tk.TclError: pass
    try: self.update_idletasks(); self.scroll.configure(scrollregion=self.scroll.bbox("all")); self.scroll.yview_moveto(0)
    except tk.TclError: pass


# ================================================================ Quick setup
@method
def build_quick(self, q):
    v, o = self.v, self.o; q.columnconfigure(1, weight=1); r = [-1]

    def head(txt):
        r[0] += 1; self.head(q, txt, r[0])

    def row(label, w, tip=None, span=2):
        r[0] += 1; ttk.Label(q, text=label).grid(row=r[0], column=0, sticky="w", pady=3); w.grid(row=r[0], column=1, columnspan=span, sticky="w", padx=8)
        if tip: self.tip(w, tip)
        return w

    head("🎬 What to make")
    row("How many clips", self.spin(q, v["n"], 1, 30))
    lf = ttk.Frame(q); self.spin(lf, v["lmin"], 10, 120).pack(side="left"); ttk.Label(lf, text="  to  ").pack(side="left"); self.spin(lf, v["lmax"], 10, 120).pack(side="left")
    ttk.Label(lf, text="  seconds", style="Mute.TLabel").pack(side="left")
    row("Clip length", lf)
    row("Find moments that are", self.pick(q, v["style"], A.STYLE_NAMES, 22))
    row("Shape", self.pick(q, v["aspect"], A.ASPECT_NAMES, 38))
    row("Post on", self.pick(q, o["platform"], A.PLATFORM_NAMES, 22), "Keeps your @name, logo, round cam and the end card away from the buttons and text that TikTok / Shorts / Reels draw on top of vertical video.")
    head("🖼 Layout")
    row("Layout", self.layout_cell(q))
    row("Model / cam area", self.cam_row(q))
    head("✨ Switch on")
    r[0] += 1; g = ttk.Frame(q); g.grid(row=r[0], column=0, columnspan=3, sticky="w")
    checks = [("🧠 Smart finding", o["smart"], "Tells laughs, screams, singing, stories and gameplay apart and picks the best of each. More under Smart finding."),
              ("💬 Animated captions", self.caps, "The words appear while you speak."), ("✂ Remove long silences", self.silence, "Cuts out the quiet parts, but keeps a little breathing room."),
              ("🪝 Title at the start", self.fx["hook"], "A big teaser title for the first seconds."), ("🎭 Chibi emotes for story time", o["emotes"], "Your own chibi pictures act out what you say. Add them in the Chibi emotes tab."),
              ("🧼 Clean up my voice", o["voice_clean"], "Less hiss and hum, steadier volume."), ("😂 Emoji on captions", o["cap_emoji"], "A few little emoji pop up on words like lol, love, dead, fire."),
              ("🆕 Skip moments I already made", o["fresh"], "Next time the app picks different moments instead of the same top ones."), ("📝 Save title ideas + hashtags", o["post_kit"], "A .txt file next to each clip, ready to paste."),
              ("🖼 Save a cover picture", o["cover"], "A still from the best moment with the title on top.")]
    for i, (txt, var, tp) in enumerate(checks):
        c = ttk.Checkbutton(g, text=txt, variable=var); c.grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 28), pady=2); self.tip(c, tp)
    self.qe_note = tk.StringVar()
    r[0] += 1; ttk.Label(q, textvariable=self.qe_note, style="Mute.TLabel", wraplength=640, justify="left").grid(row=r[0], column=0, columnspan=3, sticky="w", pady=(2, 0))
    head("🏷 Your name on it")
    row("@name on the video", ttk.Entry(q, textvariable=o["handle"], width=26), "Shown in a corner of every clip.")
    row("End card text", ttk.Entry(q, textvariable=o["cta"], width=26), "A pill that pops up for the last 2.5 seconds, for example “Follow for more ♡”. Empty = none.")
    head("🔔 Buttons & words")
    r[0] += 1; cf = ttk.Frame(q); cf.grid(row=r[0], column=0, columnspan=3, sticky="w")
    for k, (lab, _c) in vcnew.CALLOUTS.items(): ttk.Checkbutton(cf, text=lab.title(), variable=self.co_vars[k]).pack(side="left", padx=(0, 14))
    ttk.Label(cf, text="pop up one after another", style="Mute.TLabel").pack(side="left")
    r[0] += 1; bf = ttk.Frame(q); bf.grid(row=r[0], column=0, columnspan=3, sticky="w", pady=(6, 0))
    ttk.Button(bf, text="📝 Add words on screen…", command=lambda: self.sub.set("text")).pack(side="left")
    ttk.Button(bf, text="⚙ Show all options", command=lambda: self.simple.set(False)).pack(side="left", padx=8)
    r[0] += 1; ttk.Label(q, text="All options = effects, colour looks, voice effects, intro / outro, stickers, music and the posting files.", style="Mute.TLabel",
                         wraplength=640, justify="left").grid(row=r[0], column=0, columnspan=3, sticky="w", pady=(6, 0))


# ================================================================ Words & buttons
@method
def build_text(self, x):
    o = self.o; x.columnconfigure(0, weight=1); sc = sc_(); r = [-1]
    r[0] += 1; self.head(x, "📝 Words on screen", r[0])
    r[0] += 1; ttk.Label(x, text="Up to three texts. Each shows for a few seconds at the time you choose. Leave a text empty to switch it off.", style="Mute.TLabel",
                         wraplength=660, justify="left").grid(row=r[0], column=0, sticky="w", pady=(0, 4))
    self.tb = []
    for i in range(vcnew.MAX_TEXTS):
        r[0] += 1; box = ttk.Frame(x, padding=(0, 4, 0, 6)); box.grid(row=r[0], column=0, sticky="we"); box.columnconfigure(1, weight=1)
        row = dict(t=tk.StringVar(), at=tk.StringVar(value="2"), end=tk.BooleanVar(value=False), dur=tk.StringVar(value="3"), pos=tk.StringVar(value="mid"), style=tk.StringVar(value="pill"), say=tk.BooleanVar(value=False))
        ttk.Label(box, text=f"Text {i + 1}", font=(A.FONT, 9, "bold")).grid(row=0, column=0, sticky="w", padx=(0, 10))
        en = ttk.Entry(box, textvariable=row["t"]); en.grid(row=0, column=1, sticky="we"); self.tip(en, "What to write. Short is best: “WAIT FOR IT”, “NO WAY”, “day 3 of the challenge”.")
        l2 = ttk.Frame(box); l2.grid(row=1, column=1, sticky="w", pady=(4, 0))
        ttk.Label(l2, text="Appears at").pack(side="left"); self.spin(l2, row["at"], 0, 600, .5, 5).pack(side="left", padx=(5, 2)); ttk.Label(l2, text="s").pack(side="left")
        ce = ttk.Checkbutton(l2, text="from the end", variable=row["end"]); ce.pack(side="left", padx=(8, 0)); self.tip(ce, "Count the seconds from the end of the clip instead: “appears at 3 s from the end” shows in the last seconds.")
        ttk.Label(l2, text="   stays").pack(side="left"); self.spin(l2, row["dur"], .5, 30, .5, 5).pack(side="left", padx=(5, 2)); ttk.Label(l2, text="s").pack(side="left")
        l3 = ttk.Frame(box); l3.grid(row=2, column=1, sticky="w", pady=(4, 0))
        self.pick(l3, row["pos"], vcnew.TEXT_POS, 14).pack(side="left"); self.pick(l3, row["style"], vcnew.TEXT_STYLES, 22).pack(side="left", padx=8)
        cs = ttk.Checkbutton(l3, text="🔊 Read it out loud", variable=row["say"]); cs.pack(side="left", padx=4); self.tip(cs, "A voice says this text while it shows. The game sound dips while it speaks.")
        for k in ("t", "at", "end", "dur", "pos", "style", "say"): row[k].trace_add("write", self.tb_push)
        self.tb.append(row)
    r[0] += 1; ttk.Label(x, textvariable=self.tb_note, style="Mute.TLabel", wraplength=660, justify="left").grid(row=r[0], column=0, sticky="w")
    r[0] += 1; self.head(x, "🔊 The voice that reads your words", r[0])
    r[0] += 1; vf = ttk.Frame(x); vf.grid(row=r[0], column=0, sticky="w")
    self.voice_disp = tk.StringVar(value=DEFAULT_VOICE)
    self.voice_combo = self.combo(vf, self.voice_disp, [DEFAULT_VOICE], 30); self.voice_combo.pack(side="left")
    self.voice_combo.bind("<<ComboboxSelected>>", lambda e: o["tts_voice"].set("" if self.voice_disp.get() == DEFAULT_VOICE else self.voice_disp.get()))
    o["tts_voice"].trace_add("write", lambda *a: self.voice_disp.set(o["tts_voice"].get() or DEFAULT_VOICE))
    ttk.Label(vf, text="  speed").pack(side="left"); sp = self.spin(vf, o["tts_rate"], -5, 5, 1, 4); sp.pack(side="left", padx=(5, 0)); self.tip(sp, "0 = normal, -5 = slowest, 5 = fastest.")
    self.tip(ttk.Button(vf, text="▶ Hear it", command=self.hear_tts), "Plays a short sample with this voice.").pack(side="left", padx=8)
    r[0] += 1; ttk.Label(x, textvariable=self.voice_note, style="Mute.TLabel", wraplength=660, justify="left").grid(row=r[0], column=0, sticky="w", pady=(2, 0))
    r[0] += 1; self.head(x, "🔔 Like / Follow / Subscribe buttons", r[0])
    r[0] += 1; cf = ttk.Frame(x); cf.grid(row=r[0], column=0, sticky="w")
    for k, (lab, _c) in vcnew.CALLOUTS.items(): ttk.Checkbutton(cf, text=lab.title(), variable=self.co_vars[k]).pack(side="left", padx=(0, 16))
    r[0] += 1; ttk.Label(x, text="A coloured button pops up for about two seconds, one after another, spread over the clip. They stay clear of the end card. "
                                 "Use ▶ Preview at the top to see how it looks.", style="Mute.TLabel", wraplength=660, justify="left").grid(row=r[0], column=0, sticky="w", pady=(4, 0))
    for k, var in self.co_vars.items(): var.trace_add("write", self.co_push)
    o["text_boxes"].trace_add("write", self.tb_pull); o["callouts"].trace_add("write", self.co_pull)
    self.tb_pull(); self.co_pull(); self.voice_disp.set(o["tts_voice"].get() or DEFAULT_VOICE)
    threading.Thread(target=self.load_voices, daemon=True).start()


@method
def tb_push(self, *a):
    """The text rows were edited -> the one setting string the engine reads."""
    if self.tb_busy or not self.tb: return
    items = []
    for r in self.tb:
        t = r["t"].get().strip()
        if not t: continue
        try: at = float(str(r["at"].get()).replace(",", "."))
        except ValueError: at = 0.0
        try: du = float(str(r["dur"].get()).replace(",", "."))
        except ValueError: du = 3.0
        at = -max(.5, abs(at)) if r["end"].get() else abs(at)
        items.append(dict(t=t, at=at, **{"for": du}, pos=r["pos"].get(), style=r["style"].get(), say=bool(r["say"].get())))
    self.tb_busy = True
    try: self.o["text_boxes"].set(vcnew.texts_json(items))
    finally: self.tb_busy = False
    self.tb_note_update()


@method
def tb_pull(self, *a):
    """The setting string changed somewhere else (a profile, a reset, an old config) -> fill the rows."""
    if self.tb_busy or not self.tb: return
    items = vcnew.parse_texts(self.o["text_boxes"].get())
    self.tb_busy = True
    try:
        for i, r in enumerate(self.tb):
            b = items[i] if i < len(items) else None
            r["t"].set(b["t"] if b else ""); r["end"].set(bool(b and b["at"] < 0)); r["at"].set(f"{abs(b['at']):g}" if b else "2")
            r["dur"].set(f"{b['for']:g}" if b else "3"); r["pos"].set(b["pos"] if b else "mid"); r["style"].set(b["style"] if b else "pill"); r["say"].set(bool(b and b["say"]))
    finally: self.tb_busy = False
    self.tb_note_update()


@method
def tb_note_update(self):
    items = vcnew.parse_texts(self.o["text_boxes"].get()); n, s = len(items), sum(1 for b in items if b["say"])
    self.tb_note.set("No text yet. Type something above and press ▶ Preview." if not n else
                     f"{n} text{'s' if n != 1 else ''} on screen" + (f", {s} read out loud." if s else ".") + "  A text that starts after the clip has ended is simply skipped.")


@method
def co_push(self, *a):
    if self.co_busy: return
    self.co_busy = True
    try: self.o["callouts"].set(",".join(k for k in vcnew.CALLOUTS if self.co_vars[k].get()))
    finally: self.co_busy = False


@method
def co_pull(self, *a):
    if self.co_busy: return
    keys = vcnew.parse_callouts(self.o["callouts"].get()); self.co_busy = True
    try:
        for k, var in self.co_vars.items(): var.set(k in keys)
    finally: self.co_busy = False


@method
def load_voices(self):
    names = vcnew.tts_voices(A.sc.FF, A.sc.NOWIN)
    self.ui(lambda: self.voices_ready(names))


@method
def voices_ready(self, names):
    self.voices = names
    try:
        self.voice_combo.configure(values=[DEFAULT_VOICE] + list(names))
        self.voice_note.set("" if names else "I couldn't find a voice on this computer, so “read it out loud” is skipped. (On Windows: Settings → Time & language → Speech → add a voice.)")
    except tk.TclError: pass


@method
def hear_tts(self):
    voice, rate = self.o["tts_voice"].get(), self.o["tts_rate"].get(); sc = A.sc
    self.voice_note.set("Getting a sample…")

    def go():
        try: rate_ = int(float(rate))
        except (TypeError, ValueError): rate_ = 0
        out = os.path.join(tempfile.gettempdir(), "vclip_tts_preview.wav")
        try: os.remove(out)
        except OSError: pass
        ok = vcnew.tts_make(TTS_TEST, out, voice, rate_, sc.FF, sc.NOWIN)
        self.ui(lambda: (self.play_sound(out), self.voice_note.set("Playing a sample ♪")) if ok else self.voice_note.set("I couldn't make a sample - no voice found on this computer."))
    threading.Thread(target=go, daemon=True).start()


# ================================================================ layout designer
BG_CHOICES = {"blur": "Blurred copy of the game", "color": "One colour", "black": "Black"}
GAME_FILL, CAM_FILL = "#3f6fd6", "#ff5fa8"


@method
def open_designer(self):
    w = getattr(self, "designer", None)
    if w is not None:
        try:
            if w.winfo_exists(): w.lift(); return
        except tk.TclError: pass
    self.designer = LayoutDesigner(self)


@method
def layout_custom_check(self):
    """Picking “My own layout” with nothing designed yet opens the designer; any other layout is remembered so Cancel can go back to it."""
    lay = self.v["layout"].get()
    if lay != "custom": self.last_layout = lay
    elif not self.o["custom_layout"].get():
        self.after(80, self.open_designer)


class LayoutDesigner(tk.Toplevel):
    """Drag the game and the cam boxes on a little phone screen. Writes the 'custom_layout' setting."""
    def __init__(self, app):
        super().__init__(app)
        self.app, self.t = app, app.t; t = self.t
        self.configure(bg=t["bg"]); self.title("Design my layout ♡"); self.transient(app)
        asp = A.sc.ASPECTS.get(app.v["aspect"].get(), (9, 16)); k = min(300 / asp[0], 440 / asp[1]); self.cw, self.ch = int(asp[0] * k), int(asp[1] * k)
        p = vcnew.parse_layout(app.o["custom_layout"].get())
        base = vcnew.parse_layout(vcnew.LAYOUT_PRESETS[1][1])
        self.geo = {n: dict(p[n] or base[n] or dict(x=.1, y=.1, w=.5, h=.3, fit=False, round=False)) for n in ("game", "cam")}
        self.on = {n: tk.BooleanVar(value=bool(p[n]) if (p["game"] or p["cam"]) else True) for n in ("game", "cam")}
        self.fit, self.round = tk.BooleanVar(value=self.geo["game"]["fit"]), tk.BooleanVar(value=self.geo["cam"]["round"])
        bg = p["bg"] or (app.o["bg_style"].get() if app.o["bg_style"].get() in ("blur", "color") else "blur")
        self.bg = tk.StringVar(value=bg); self.note = tk.StringVar(); self.drag = None
        body = ttk.Frame(self, padding=(14, 12, 14, 6)); body.pack()
        left = ttk.Frame(body); left.grid(row=0, column=0, sticky="n", padx=(0, 18))
        ttk.Label(left, text=f"Your {app.v['aspect'].get()} video", style="Mute.TLabel").pack(anchor="w")
        self.cv = tk.Canvas(left, width=self.cw, height=self.ch, highlightthickness=1, highlightbackground=t["mute"], cursor="fleur"); self.cv.pack(pady=(3, 0))
        self.cv.bind("<Button-1>", self.press); self.cv.bind("<B1-Motion>", self.motion); self.cv.bind("<ButtonRelease-1>", lambda e: setattr(self, "drag", None))
        right = ttk.Frame(body); right.grid(row=0, column=1, sticky="n")
        ttk.Label(right, text="Start from…", font=(A.FONT, 10, "bold"), foreground=t["accent"]).pack(anchor="w")
        pf = ttk.Frame(right); pf.pack(anchor="w", pady=(3, 8))
        for i, (name, spec) in enumerate(vcnew.LAYOUT_PRESETS):
            ttk.Button(pf, text=name, command=lambda s=spec: self.load(s)).grid(row=i // 2, column=i % 2, sticky="we", padx=(0, 6), pady=2)
        ttk.Label(right, text="Show", font=(A.FONT, 10, "bold"), foreground=t["accent"]).pack(anchor="w")
        ttk.Checkbutton(right, text="The game (the VOD picture)", variable=self.on["game"], command=self.draw).pack(anchor="w")
        fc = ttk.Checkbutton(right, text="    the whole picture, no cropping", variable=self.fit, command=self.draw); fc.pack(anchor="w")
        A.Tip(fc, "Shows the full game picture inside its box. Empty space around it is filled by the background.")
        ttk.Checkbutton(right, text="Your cam / model", variable=self.on["cam"], command=self.draw).pack(anchor="w", pady=(4, 0))
        ttk.Checkbutton(right, text="    in a round bubble", variable=self.round, command=self.draw).pack(anchor="w")
        ttk.Label(right, text="Background", font=(A.FONT, 10, "bold"), foreground=t["accent"]).pack(anchor="w", pady=(10, 0))
        bf = ttk.Frame(right); bf.pack(anchor="w", pady=(3, 0))
        self.bgpick = app.pick(bf, self.bg, BG_CHOICES, 24); self.bgpick.pack(side="left")
        self.bgsw = tk.Button(bf, width=3, relief="flat", bd=0, cursor="hand2", command=self.pick_bg); self.bgsw.pack(side="left", padx=6)
        self.bg.trace_add("write", lambda *a: self.draw())
        ttk.Label(right, textvariable=self.note, style="Mute.TLabel", wraplength=300, justify="left").pack(anchor="w", pady=(10, 0))
        ttk.Label(right, text="Drag a box to move it. Drag the little white square in its lower right corner to resize it. The cam sits on top of the game. "
                              "Edges snap to the middle and the sides.", style="Mute.TLabel", wraplength=300, justify="left").pack(anchor="w", pady=(10, 0))
        bb = ttk.Frame(self); bb.pack(fill="x", padx=14, pady=(2, 12))
        ttk.Button(bb, text="✔  Use this layout", style="Accent.TButton", command=self.use).pack(side="left"); ttk.Button(bb, text="Cancel", command=self.cancel).pack(side="left", padx=8)
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.draw(); A.center_over(self, app)

    # ---- model
    def load(self, spec):
        p = vcnew.parse_layout(spec)
        for n in ("game", "cam"):
            self.on[n].set(bool(p[n]))
            if p[n]: self.geo[n] = dict(p[n])
        self.fit.set(bool(p["game"] and p["game"]["fit"])); self.round.set(bool(p["cam"] and p["cam"]["round"]))
        if p["bg"]: self.bg.set(p["bg"])
        self.draw()

    def pick_bg(self):
        self.app.pick_color("bg_color"); self.draw()

    def spec(self):
        g = dict(self.geo["game"], fit=bool(self.fit.get())) if self.on["game"].get() else None
        c = dict(self.geo["cam"], round=bool(self.round.get())) if self.on["cam"].get() else None
        return vcnew.make_spec(g, c, self.bg.get()) if (g or c) else ""

    def rect(self, n):
        b = self.geo[n]; return b["x"] * self.cw, b["y"] * self.ch, (b["x"] + b["w"]) * self.cw, (b["y"] + b["h"]) * self.ch

    def draw(self):
        c, o = self.cv, self.app.o; c.delete("all"); bg = self.bg.get()
        fill = "#000000" if bg == "black" else ("#" + o["bg_color"].get()) if bg == "color" else "#5b4a8f"
        c.create_rectangle(0, 0, self.cw, self.ch, fill=fill, outline="")
        if bg == "blur":
            for i in range(0, self.ch, 6): c.create_rectangle(0, i, self.cw, i + 6, fill=A.mix("#7a5fb8", "#3a2f66", i / self.ch), outline="")
        try: self.bgsw.configure(bg="#" + o["bg_color"].get(), state="normal" if bg == "color" else "disabled")
        except tk.TclError: pass
        for n in ("game", "cam"):
            if not self.on[n].get(): continue
            x1, y1, x2, y2 = self.rect(n); col = GAME_FILL if n == "game" else CAM_FILL
            if n == "cam" and self.round.get():
                d = min(x2 - x1, y2 - y1); cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                c.create_oval(cx - d / 2, cy - d / 2, cx + d / 2, cy + d / 2, fill=col, outline="white", width=2)
            elif n == "game" and self.fit.get():
                bw = min(x2 - x1, (y2 - y1) * 16 / 9); bh = bw * 9 / 16; cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                c.create_rectangle(x1, y1, x2, y2, fill=A.mix(col, "#000000", .35), outline="white", dash=(3, 3))
                c.create_rectangle(cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2, fill=col, outline="white", width=2)
            else: c.create_rectangle(x1, y1, x2, y2, fill=col, outline="white", width=2)
            c.create_text((x1 + x2) / 2, (y1 + y2) / 2, text="GAME" if n == "game" else "CAM", fill="white", font=(A.FONT, 12, "bold"))
            c.create_rectangle(x2 - 9, y2 - 9, x2 - 1, y2 - 1, fill="white", outline="#333333")
        if not (self.on["game"].get() or self.on["cam"].get()): self.note.set("Show the game, the cam, or both.")
        else: self.note.set("")

    # ---- mouse
    def press(self, e):
        for n in ("cam", "game"):
            if not self.on[n].get(): continue
            x1, y1, x2, y2 = self.rect(n)
            if x2 - 14 <= e.x <= x2 + 4 and y2 - 14 <= e.y <= y2 + 4: self.drag = (n, "size", 0, 0); return
            if x1 <= e.x <= x2 and y1 <= e.y <= y2: self.drag = (n, "move", e.x - x1, e.y - y1); return

    def snap(self, v, pts):
        for p in pts:
            if abs(v - p) < .02: return p
        return v

    def motion(self, e):
        if not self.drag: return
        n, mode, dx, dy = self.drag; b = self.geo[n]; other = self.geo["cam" if n == "game" else "game"] if self.on["cam" if n == "game" else "game"].get() else None
        if mode == "move":
            x = (e.x - dx) / self.cw; y = (e.y - dy) / self.ch
            xs = [0.0, .5 - b["w"] / 2, 1 - b["w"]] + ([other["x"], other["x"] + other["w"] - b["w"], other["x"] + other["w"]] if other else [])
            ys = [0.0, .5 - b["h"] / 2, 1 - b["h"]] + ([other["y"], other["y"] + other["h"] - b["h"], other["y"] + other["h"]] if other else [])
            b["x"] = max(0.0, min(1 - b["w"], self.snap(x, xs))); b["y"] = max(0.0, min(1 - b["h"], self.snap(y, ys)))
        else:
            r = self.snap(e.x / self.cw, [.5, 1.0] + ([other["x"], other["x"] + other["w"]] if other else [])); bt = self.snap(e.y / self.ch, [.5, 1.0] + ([other["y"], other["y"] + other["h"]] if other else []))
            b["w"] = max(vcnew.MIN_BOX, min(1 - b["x"], r - b["x"])); b["h"] = max(vcnew.MIN_BOX, min(1 - b["y"], bt - b["y"]))
        self.draw()

    # ---- finish
    def use(self):
        s = self.spec(); app = self.app
        if not s: self.note.set("Show the game, the cam, or both."); return
        app.o["custom_layout"].set(s); app.v["layout"].set("custom")
        if self.on["cam"].get() and not app.v["cam"].get().strip(): app.status.set("Layout saved. Now pick your cam area (Find it for me) so the cam box can be filled ♡")
        else: app.status.set("Your own layout is ready ✿")
        app.save(); self.destroy()

    def cancel(self):
        app = self.app
        if app.v["layout"].get() == "custom" and not app.o["custom_layout"].get(): app.v["layout"].set(getattr(app, "last_layout", "stack") or "stack")
        self.destroy()


# ================================================================ trim / tidy a finished clip
FADE_CHOICES = {"0": "No fade", "0.3": "Quick fade in and out", "0.6": "Soft fade in and out", "1.0": "Long fade in and out"}


def _clock(x):
    x = max(0.0, float(x)); m, s = int(x // 60), x - int(x // 60) * 60
    return f"{m}:{s:04.1f}"


@method
def card_menu_extras21(self, mn, f, t):
    """Added to the ⋯ More menu of a clip in My clips."""
    mn.add_separator()
    mn.add_command(label="✂  Trim / tidy this clip…", command=lambda f=f: self.open_tidy(f))
    mn.add_command(label="🎬  Add to a montage…", command=lambda f=f: self.open_montage(f))
    mn.add_command(label="🗓  Plan a post…", command=lambda f=f: self.plan_add_dialog(f))


@method
def clips_extras(self, hr):
    """Buttons at the top of the My clips page."""
    self.tip(ttk.Button(hr, text="🗓 Post planner", command=self.open_planner), "Plan when each clip goes online. The app reminds you while it is open.").pack(side="right", padx=6)
    self.tip(ttk.Button(hr, text="🎬 Montage", command=lambda: self.open_montage(None)), "Join several clips into one video with transitions.").pack(side="right")


@method
def open_tidy(self, path):
    if self.busy: return messagebox.showinfo("VTuber Clipper", "I'm busy right now~ try again when this finishes.")
    if not os.path.isfile(path): return messagebox.showinfo("VTuber Clipper", "I can't find that clip any more. Press Refresh ♡")
    ClipTidy(self, path)


@method
def run_tidy(self, src, dest, s, e, quiet, fade):
    sc = A.sc; sc.USE_GPU_ENC = self.gpu_enc.get(); self.apply_output()

    def fn():
        sc.PLAN.clear(); sc.set_plan({"Rendering": 1}); sc.report("Rendering", 0, "Trimming your clip")
        ok, res = vcnew.trim_clip(src, str(dest), s, e, sc.FF, sc.NOWIN, sc.venc(), quiet, fade, lambda f: sc.report("Rendering", f, "Trimming your clip"),
                                  run=lambda a, t, cb, cwd: sc.run_ff(a, t, cb, cwd=cwd))
        if not ok: raise RuntimeError(res)
        print(f"Saved {dest}  ({res:.1f} seconds)")
    self.work(fn, "tidy")


class ClipTidy(tk.Toplevel):
    """Keep one part of a finished clip, cut out the quiet stretches, add a fade. Saves a NEW clip next to the old one."""
    def __init__(self, app, path):
        super().__init__(app)
        self.app, self.path, self.t = app, path, app.t; t = self.t; sc = A.sc
        self.info = sc.probe_info(path); self.dur = self.info["dur"] or 0.0
        self.configure(bg=t["bg"]); self.title("Trim / tidy a clip ✂"); self.transient(app)
        self.s, self.e, self.q, self.f, self.name, self.note = (tk.StringVar(value="0:00.0"), tk.StringVar(value=_clock(self.dur)), tk.BooleanVar(value=False), tk.StringVar(value="0"),
                                                               tk.StringVar(value=os.path.splitext(os.path.basename(path))[0] + "_trim"), tk.StringVar())
        body = ttk.Frame(self, padding=(16, 14, 16, 6)); body.pack(fill="x")
        ttk.Label(body, text=os.path.basename(path), font=(A.FONT, 10, "bold"), wraplength=460).grid(row=0, column=0, columnspan=4, sticky="w")
        ttk.Label(body, text=f"{_clock(self.dur)} long", style="Mute.TLabel").grid(row=1, column=0, columnspan=4, sticky="w", pady=(0, 8))
        ttk.Label(body, text="Keep from").grid(row=2, column=0, sticky="w", pady=3); ttk.Entry(body, textvariable=self.s, width=9).grid(row=2, column=1, sticky="w", padx=6)
        ttk.Label(body, text="to").grid(row=2, column=2, sticky="w"); ttk.Entry(body, textvariable=self.e, width=9).grid(row=2, column=3, sticky="w", padx=6)
        pk = ttk.Button(body, text="🎚 Pick on the timeline…", command=self.pick); pk.grid(row=3, column=1, columnspan=3, sticky="w", padx=6, pady=(2, 6))
        if self.dur < 5: pk.state(["disabled"])
        qc = ttk.Checkbutton(body, text="🤫 Cut out the quiet parts (when nobody talks)", variable=self.q); qc.grid(row=4, column=0, columnspan=4, sticky="w", pady=2)
        A.Tip(qc, "Removes stretches of silence longer than about a second and keeps a little breathing room around speech. Good for tightening a story.")
        ttk.Label(body, text="Fade").grid(row=5, column=0, sticky="w", pady=3); app.pick(body, self.f, FADE_CHOICES, 24).grid(row=5, column=1, columnspan=3, sticky="w", padx=6)
        ttk.Label(body, text="Save as").grid(row=6, column=0, sticky="w", pady=3); ttk.Entry(body, textvariable=self.name, width=38).grid(row=6, column=1, columnspan=3, sticky="we", padx=6)
        ttk.Label(body, text="A new clip is made next to this one. The original is not touched.", style="Mute.TLabel").grid(row=7, column=0, columnspan=4, sticky="w", pady=(4, 0))
        ttk.Label(self, textvariable=self.note, foreground=t["accent"], wraplength=460, justify="left").pack(anchor="w", padx=16)
        bb = ttk.Frame(self); bb.pack(fill="x", padx=16, pady=12)
        ttk.Button(bb, text="✔  Make the new clip", style="Accent.TButton", command=self.go).pack(side="left"); ttk.Button(bb, text="Cancel", command=self.destroy).pack(side="left", padx=8)
        A.center_over(self, app)
        try: self.wait_visibility(); self.grab_set()
        except tk.TclError: pass

    def times(self):
        s, e = A.pad_time(self.s.get()), A.pad_time(self.e.get())
        if s is None or e is None: return None, "Type the times like 0:12 or 1:05.5"
        if s < 0 or e > self.dur + .3: return None, f"The clip is only {_clock(self.dur)} long."
        if e - s < .5: return None, "The part you keep must be at least half a second long."
        return (s, min(e, self.dur)), ""

    def pick(self):
        tm, _ = self.times(); s, e = tm or (0.0, self.dur)
        A.TrimDialog(self.app, self.path, self.dur, s, e, lambda s_, e_: (self.s.set(_clock(s_)), self.e.set(_clock(e_))), title="Pick the part to keep ✂")

    def go(self):
        tm, err = self.times()
        if not tm: return self.note.set(err)
        name = re.sub(r'[\\/:*?"<>|]+', " ", self.name.get()).strip().strip(".") or "clip_trim"
        try: fade = float(self.f.get())
        except ValueError: fade = 0.0
        dest = A.sc.unique_path(os.path.join(os.path.dirname(self.path), name + ".mp4"))
        self.destroy(); self.app.run_tidy(self.path, dest, tm[0], tm[1], bool(self.q.get()), fade)


# ================================================================ montage
@method
def open_montage(self, pre=None):
    if self.busy: return messagebox.showinfo("VTuber Clipper", "I'm busy right now~ try again when this finishes.")
    w = getattr(self, "montage_win", None)
    if w is not None:
        try:
            if w.winfo_exists():
                if pre: w.add_files([pre])
                return w.lift()
        except tk.TclError: pass
    self.montage_win = MontageDialog(self, pre)


@method
def run_montage(self, clips, dest, transition, td, title):
    sc = A.sc; sc.USE_GPU_ENC = self.gpu_enc.get(); self.apply_output()
    font = os.path.join(sc.APP_DIR, "fonts", "Poppins-ExtraBold.ttf")

    def fn():
        sc.PLAN.clear(); sc.set_plan({"Rendering": 1}); sc.report("Rendering", 0, "Joining your clips")
        ok, res = vcnew.make_montage(clips, str(dest), sc.FF, sc.NOWIN, sc.venc(), transition, td, title, font, lambda f: sc.report("Rendering", f, "Joining your clips"),
                                     run=lambda a, t, cb, cwd: sc.run_ff(a, t, cb, cwd=cwd), fps=int(sc.OUT.get("fps", 30)))
        if not ok: raise RuntimeError(res)
        print(f"Saved {dest}  ({res:.1f} seconds)")
    self.work(fn, "montage")


class MontageDialog(tk.Toplevel):
    """Pick clips, put them in order, choose a transition. Saves one video in the Montages folder."""
    def __init__(self, app, pre=None):
        super().__init__(app)
        self.app, self.t = app, app.t; t = self.t; sc = A.sc
        self.configure(bg=t["bg"]); self.title("Make a montage 🎬"); self.transient(app)
        self.all = app.clip_files()[:60]; self.picked, self.durs = [], {}
        self.tr, self.td, self.title_v, self.name, self.note = tk.StringVar(value="fade"), tk.StringVar(value="0.5"), tk.StringVar(), tk.StringVar(value="Montage " + time.strftime("%Y-%m-%d")), tk.StringVar()
        ttk.Label(self, text="Pick two or more clips, then put them in the order you like.", padding=(16, 12, 16, 4)).pack(anchor="w")
        body = ttk.Frame(self, padding=(16, 0, 16, 4)); body.pack()
        ttk.Label(body, text="Your newest clips", font=(A.FONT, 9, "bold")).grid(row=0, column=0, sticky="w"); ttk.Label(body, text="In the montage, in this order", font=(A.FONT, 9, "bold")).grid(row=0, column=2, sticky="w")
        self.lb_all = tk.Listbox(body, selectmode="extended", width=36, height=12, exportselection=False, bg=t["entry"], fg=t["fg"], relief="flat", highlightthickness=0, selectbackground=t["accent"], selectforeground=t["on"])
        self.lb_all.grid(row=1, column=0, sticky="n"); self.lb_all.bind("<Double-Button-1>", lambda e: self.add())
        mid = ttk.Frame(body); mid.grid(row=1, column=1, padx=8)
        ttk.Button(mid, text="Add →", command=self.add).pack(pady=2); ttk.Button(mid, text="▲", width=4, command=lambda: self.move(-1)).pack(pady=(14, 2))
        ttk.Button(mid, text="▼", width=4, command=lambda: self.move(1)).pack(pady=2); ttk.Button(mid, text="✖", width=4, command=self.remove).pack(pady=(14, 2))
        self.lb_in = tk.Listbox(body, selectmode="browse", width=36, height=12, exportselection=False, bg=t["entry"], fg=t["fg"], relief="flat", highlightthickness=0, selectbackground=t["accent"], selectforeground=t["on"])
        self.lb_in.grid(row=1, column=2, sticky="n")
        for f in self.all: self.lb_all.insert("end", os.path.basename(f))
        if not self.all: self.lb_all.insert("end", "(no clips yet - make some first)")
        opt = ttk.Frame(self, padding=(16, 8, 16, 0)); opt.pack(fill="x"); opt.columnconfigure(1, weight=1)
        ttk.Label(opt, text="Between clips").grid(row=0, column=0, sticky="w", pady=3)
        tf = ttk.Frame(opt); tf.grid(row=0, column=1, sticky="w", padx=8); app.pick(tf, self.tr, vcnew.TRANSITIONS, 22).pack(side="left")
        ttk.Label(tf, text="  for").pack(side="left"); app.spin(tf, self.td, .2, 1.5, .1, 5).pack(side="left", padx=4); ttk.Label(tf, text="seconds").pack(side="left")
        ttk.Label(opt, text="Title at the start").grid(row=1, column=0, sticky="w", pady=3); ttk.Entry(opt, textvariable=self.title_v).grid(row=1, column=1, sticky="we", padx=8)
        ttk.Label(opt, text="Save as").grid(row=2, column=0, sticky="w", pady=3); ttk.Entry(opt, textvariable=self.name).grid(row=2, column=1, sticky="we", padx=8)
        ttk.Label(self, textvariable=self.note, foreground=t["accent"], padding=(16, 6, 16, 0), wraplength=560, justify="left").pack(anchor="w")
        bb = ttk.Frame(self); bb.pack(fill="x", padx=16, pady=12)
        ttk.Button(bb, text="🎬  Make the montage", style="Accent.TButton", command=self.go).pack(side="left"); ttk.Button(bb, text="Close", command=self.destroy).pack(side="left", padx=8)
        if pre: self.add_files([pre])
        self.refresh(); A.center_over(self, app)

    def dur(self, f):
        if f not in self.durs:
            try: self.durs[f] = A.sc.probe_info(f)["dur"]
            except Exception: self.durs[f] = 0.0
        return self.durs[f]

    def add_files(self, files):
        for f in files:
            if f not in self.picked and len(self.picked) < vcnew.MAX_MONTAGE and os.path.isfile(f): self.picked.append(f)
        self.refresh()

    def add(self): self.add_files([self.all[i] for i in self.lb_all.curselection() if i < len(self.all)])

    def sel(self):
        s = self.lb_in.curselection(); return s[0] if s else None

    def move(self, d):
        i = self.sel()
        if i is None or not 0 <= i + d < len(self.picked): return
        self.picked[i], self.picked[i + d] = self.picked[i + d], self.picked[i]; self.refresh(i + d)

    def remove(self):
        i = self.sel()
        if i is not None: self.picked.pop(i); self.refresh(min(i, len(self.picked) - 1))

    def refresh(self, sel=None):
        self.lb_in.delete(0, "end")
        for k, f in enumerate(self.picked, 1): self.lb_in.insert("end", f"{k}. {os.path.basename(f)}")
        if sel is not None and sel >= 0: self.lb_in.selection_set(sel)
        n = len(self.picked)
        if n >= 2:
            ds = [self.dur(f) for f in self.picked]; _td, _o, tot = vcnew.montage_plan(ds, 0.0 if self.tr.get() == "cut" else self._td())
            self.note.set(f"{n} clips · about {_clock(tot)} long")
        else: self.note.set("Pick at least two clips." if n < 2 else "")

    def _td(self):
        try: return float(self.td.get().replace(",", "."))
        except ValueError: return .5

    def go(self):
        if len(self.picked) < 2: return self.note.set("Pick at least two clips.")
        name = re.sub(r'[\\/:*?"<>|]+', " ", self.name.get()).strip().strip(".") or "Montage"
        folder = os.path.join(self.app.v["out"].get().strip() or os.path.expanduser("~"), "Montages")
        try: os.makedirs(folder, exist_ok=True)
        except OSError as e: return self.note.set(f"I can't use that folder: {e}")
        dest = A.sc.unique_path(os.path.join(folder, name + ".mp4")); clips = list(self.picked)
        tr, td, title = self.tr.get(), self._td(), self.title_v.get()
        self.destroy(); self.app.run_montage(clips, dest, tr, td, title)


# ================================================================ post planner
@method
def open_planner(self):
    w = self.plan_win
    if w is not None:
        try:
            if w.winfo_exists(): return w.lift()
        except tk.TclError: pass
    self.plan_win = PlannerWindow(self)


@method
def plan_save(self):
    self.plan = vcnew.clean_plan(self.plan); self.save()
    w = self.plan_win
    try:
        if w is not None and w.winfo_exists(): w.fill()
    except tk.TclError: pass


@method
def plan_add_dialog(self, clip=None):
    PlanAdd(self, clip)


@method
def plan_find(self, pid):
    return next((d for d in self.plan if d["id"] == pid), None)


@method
def plan_done(self, pid, state=True):
    d = self.plan_find(pid)
    if d: d["done"] = bool(state); self.plan_save()


@method
def plan_remove(self, pid):
    self.plan = [d for d in self.plan if d["id"] != pid]; self.plan_save()


@method
def plan_snooze(self, pid, minutes=15):
    d = self.plan_find(pid)
    if d:
        d["when"] = (datetime.datetime.now() + datetime.timedelta(minutes=minutes)).isoformat(timespec="minutes"); d["shown"] = False; self.plan_save()


@method
def plan_open_page(self, d):
    """Copy the clip's title + description and open the platform's upload page."""
    name, url = vcnew.PLAN_PLATFORMS.get(d["platform"], vcnew.PLAN_PLATFORMS["tiktok"])
    if os.path.isfile(d["clip"]): self.post_to(url, d["clip"])
    else: webbrowser.open(url)


@method
def plan_tick(self):
    """Every half minute: remind about the posts whose time has come (only while the app is open)."""
    try:
        due = vcnew.plan_due(self.plan)[:3]
        for d in due:
            d["shown"] = True; self.plan_popup(d)
        if due: self.plan_save()
    except Exception: A.log_error(__import__("traceback").format_exc())
    finally:
        try: self.plan_job = self.after(30000, self.plan_tick)
        except Exception: pass


@method
def plan_popup(self, d):
    t = self.t; w = tk.Toplevel(self); w.title("Time to post ♡"); w.configure(bg=t["bg"]); w.transient(self)
    name = vcnew.PLAN_PLATFORMS.get(d["platform"], ("TikTok", ""))[0]
    ttk.Label(w, text=f"🗓 Time to post on {name}!", font=(A.FONT, 12, "bold"), padding=(18, 14, 18, 2)).pack(anchor="w")
    ttk.Label(w, text=os.path.basename(d["clip"]) or "(clip)", wraplength=380, padding=(18, 0, 18, 0)).pack(anchor="w")
    if d["note"]: ttk.Label(w, text=d["note"], style="Mute.TLabel", wraplength=380, padding=(18, 2, 18, 0)).pack(anchor="w")
    ttk.Label(w, text="planned for " + vcnew.plan_label(d), style="Mute.TLabel", padding=(18, 2, 18, 0)).pack(anchor="w")
    bb = ttk.Frame(w); bb.pack(fill="x", padx=18, pady=14)
    ttk.Button(bb, text=f"Open {name} (copies the title)", style="Accent.TButton", command=lambda: (self.plan_open_page(d), self.plan_done(d["id"]), w.destroy())).pack(side="left")
    ttk.Button(bb, text="In 15 min", command=lambda: (self.plan_snooze(d["id"], 15), w.destroy())).pack(side="left", padx=6)
    ttk.Button(bb, text="Done", command=lambda: (self.plan_done(d["id"]), w.destroy())).pack(side="left")
    A.center_over(w, self)
    try: self.chime(); w.attributes("-topmost", True); w.after(1500, lambda: w.attributes("-topmost", False) if w.winfo_exists() else None)
    except tk.TclError: pass


class PlannerWindow(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app, self.t = app, app.t; t = self.t
        self.configure(bg=t["bg"]); self.title("Post planner 🗓"); self.transient(app)
        ttk.Label(self, text="When does each clip go online?", font=(A.FONT, 11, "bold"), padding=(16, 12, 16, 0)).pack(anchor="w")
        ttk.Label(self, text="I remind you at the planned time while VTuber Clipper is open, and open the upload page with your title already copied. "
                             "I don't post for you - TikTok, YouTube and Instagram only allow that through their own logins.", style="Mute.TLabel", wraplength=640, justify="left", padding=(16, 2, 16, 8)).pack(anchor="w")
        fr = ttk.Frame(self, padding=(16, 0, 16, 0)); fr.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(fr, columns=("when", "where", "clip", "note"), show="headings", height=11, selectmode="browse")
        for k, lab, w_ in (("when", "When", 130), ("where", "Where", 120), ("clip", "Clip", 250), ("note", "Note", 160)):
            self.tree.heading(k, text=lab); self.tree.column(k, width=w_, anchor="w")
        sb = ttk.Scrollbar(fr, orient="vertical", command=self.tree.yview); self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True); sb.pack(side="left", fill="y")
        self.tree.tag_configure("done", foreground=t["mute"]); self.tree.tag_configure("late", foreground=t["accent"])
        bb = ttk.Frame(self, padding=(16, 8, 16, 12)); bb.pack(fill="x")
        ttk.Button(bb, text="➕ Plan a post…", style="Accent.TButton", command=lambda: app.plan_add_dialog(None)).pack(side="left")
        ttk.Button(bb, text="⬆ Open upload page", command=self.open_page).pack(side="left", padx=6)
        ttk.Button(bb, text="✔ Done / not done", command=self.toggle).pack(side="left"); ttk.Button(bb, text="🗑 Remove", command=self.remove).pack(side="left", padx=6)
        ttk.Button(bb, text="Close", command=self.destroy).pack(side="right")
        self.fill(); A.center_over(self, app)

    def fill(self):
        keep = self.tree.selection(); self.tree.delete(*self.tree.get_children()); now = datetime.datetime.now()
        for d in self.app.plan:
            late = not d["done"] and datetime.datetime.fromisoformat(d["when"]) <= now
            lab = ("✔ " if d["done"] else "⏰ " if late else "") + vcnew.plan_label(d)
            self.tree.insert("", "end", iid=d["id"], values=(lab, vcnew.PLAN_PLATFORMS[d["platform"]][0], os.path.basename(d["clip"]) or "—", d["note"]), tags=("done",) if d["done"] else ("late",) if late else ())
        for k in keep:
            if self.tree.exists(k): self.tree.selection_set(k)

    def cur(self):
        s = self.tree.selection(); return self.app.plan_find(s[0]) if s else None

    def open_page(self):
        d = self.cur()
        if d: self.app.plan_open_page(d)

    def toggle(self):
        d = self.cur()
        if d: self.app.plan_done(d["id"], not d["done"])

    def remove(self):
        d = self.cur()
        if d and messagebox.askyesno("VTuber Clipper", "Remove this planned post? (The clip itself is not touched.)", parent=self): self.app.plan_remove(d["id"])


class PlanAdd(tk.Toplevel):
    def __init__(self, app, clip=None):
        super().__init__(app)
        self.app, self.t = app, app.t; t = self.t
        self.configure(bg=t["bg"]); self.title("Plan a post 🗓"); self.transient(app)
        self.files = app.clip_files()[:60]
        if clip and clip not in self.files: self.files.insert(0, clip)
        self.names = [f"{os.path.basename(f)}   ({os.path.basename(os.path.dirname(f))})" for f in self.files]
        self.clip_v = tk.StringVar(value=self.names[self.files.index(clip)] if clip in self.files else (self.names[0] if self.names else ""))
        self.where = tk.StringVar(value="tiktok"); self.when = tk.StringVar(); self.note_v = tk.StringVar(); self.say = tk.StringVar()
        body = ttk.Frame(self, padding=(16, 14, 16, 6)); body.pack(fill="x"); body.columnconfigure(1, weight=1)
        ttk.Label(body, text="Clip").grid(row=0, column=0, sticky="w", pady=3); cb = app.combo(body, self.clip_v, self.names, 48); cb.grid(row=0, column=1, sticky="we", padx=8)
        ttk.Label(body, text="Where").grid(row=1, column=0, sticky="w", pady=3)
        app.pick(body, self.where, {k: v[0] for k, v in vcnew.PLAN_PLATFORMS.items()}, 22).grid(row=1, column=1, sticky="w", padx=8)
        ttk.Label(body, text="When").grid(row=2, column=0, sticky="w", pady=3)
        we = ttk.Entry(body, textvariable=self.when); we.grid(row=2, column=1, sticky="we", padx=8)
        ttk.Label(body, text="Like  tomorrow 7pm  ·  fri 20:30  ·  2026-10-20 18:00  ·  21:00", style="Mute.TLabel").grid(row=3, column=1, sticky="w", padx=8)
        self.sugg = ttk.Frame(body); self.sugg.grid(row=4, column=1, sticky="w", padx=8, pady=(4, 0))
        self.hint = tk.StringVar(); ttk.Label(body, textvariable=self.hint, style="Mute.TLabel", wraplength=420, justify="left").grid(row=5, column=1, sticky="w", padx=8, pady=(4, 0))
        ttk.Label(body, text="Note").grid(row=6, column=0, sticky="w", pady=3); ttk.Entry(body, textvariable=self.note_v).grid(row=6, column=1, sticky="we", padx=8)
        ttk.Label(self, textvariable=self.say, foreground=t["accent"], padding=(16, 0, 16, 0), wraplength=440, justify="left").pack(anchor="w")
        bb = ttk.Frame(self); bb.pack(fill="x", padx=16, pady=12)
        ttk.Button(bb, text="✔  Add to my plan", style="Accent.TButton", command=self.go).pack(side="left"); ttk.Button(bb, text="Cancel", command=self.destroy).pack(side="left", padx=8)
        self.where.trace_add("write", lambda *a: self.suggest()); self.when.trace_add("write", lambda *a: self.parse())
        self.suggest(); A.center_over(self, app)

    def suggest(self):
        for w in self.sugg.winfo_children(): w.destroy()
        plat = self.where.get(); times = vcnew.suggest_times(plat)
        ttk.Label(self.sugg, text="Good times:", style="Mute.TLabel").pack(side="left")
        for tm in times:
            ttk.Button(self.sugg, text=vcnew.plan_label(dict(when=tm.isoformat(timespec="minutes"))), command=lambda tm=tm: self.when.set(tm.strftime("%Y-%m-%d %H:%M"))).pack(side="left", padx=3)
        self.tipline = vcnew.BEST_TIMES.get(plat, ("", []))[0]; self.parse()

    def parse(self):
        txt = self.when.get().strip()
        if not txt: return self.hint.set(f"People often watch: {self.tipline}. (General habits - not live numbers from the apps.)")
        t = vcnew.parse_when(txt)
        self.hint.set(("That is " + t.strftime("%A %d %B, %H:%M")) if t else "I don't understand that time yet - try “tomorrow 7pm”.")

    def go(self):
        if not self.files: return self.say.set("Make some clips first - then you can plan them ♡")
        t = vcnew.parse_when(self.when.get())
        if not t: return self.say.set("Tell me when, for example “tomorrow 7pm”.")
        if t < datetime.datetime.now() - datetime.timedelta(minutes=1): return self.say.set("That time has already passed.")
        try: f = self.files[self.names.index(self.clip_v.get())]
        except ValueError: return self.say.set("Pick a clip.")
        self.app.plan = vcnew.plan_add(self.app.plan, f, self.where.get(), t, self.note_v.get()); self.app.plan_save()
        self.app.status.set(f"Planned for {vcnew.plan_label(dict(when=t.isoformat(timespec='minutes')))} ✿"); self.destroy()
        self.app.open_planner()
