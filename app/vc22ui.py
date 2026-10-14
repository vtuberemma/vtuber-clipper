"""VTuber Clipper 2.2 - the new screens of the app window:
the Smart finding tab, the extra caption / sound / picture rows in the existing tabs, the Tools window (watch folder, health check, clean-up, free up space,
share a look, compare looks, hashtag bank, my words, post sheet), and the extra My clips and Best moments actions (search, tags, review mode, remake a clip,
where is this from, save / open a list of moments), "try just one first", resuming an interrupted run and filling the post planner.

streamclip_app.py calls install(App, module) once; every function below becomes a method of the App window.
The work itself lives in vcsmart.py / vcsense.py / vcmore.py (finding and extras) and vctools.py (helpers); there are no screens in those."""
import datetime, glob, json, os, re, shutil, subprocess, sys, tempfile, threading, time, traceback
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

import vcmore, vcsmart, vctools, vcnew

A = None                    # the app module (streamclip_app), set by install()
METHODS, WRAPS = {}, {}

# --- the new options (the app's OPT_STR / OPT_BOOL lists get these added)
NEW_STR = ("chat_file", "range_from", "range_to", "extra_shapes", "cap_case", "cap_outline", "cap_shadow", "cap_words", "cap_box", "ready_dir")
NEW_BOOL = ("smart", "auto_look", "smart_len", "variety", "skip_greet", "tight_end", "use_taste", "hop_logo", "slowmo", "freeze", "teaser", "react_words", "tame", "hush", "cap_rainbow")
SMART_KEYS = ("smart", "variety", "skip_greet", "smart_len", "tight_end", "auto_look", "use_taste", "chat_file", "range_from", "range_to")
CAP22 = ("cap_case", "cap_outline", "cap_shadow", "cap_words", "cap_box", "cap_rainbow", "react_words")
POLISH22 = ("tame", "hush", "slowmo", "freeze", "teaser")
POST22 = ("extra_shapes", "ready_dir")
PLAT_OF = {"any": "tiktok", "tiktok": "tiktok", "shorts": "youtube", "reels": "instagram"}
SKIP_PREVIEW = ("music", "intro", "outro", "lang", "translate", "hint", "fixes", "post_kit", "srt", "channel", "game", "tags", "ready_dir", "chat_file", "range_from", "range_to")
GOOD, WARN, BAD = "#2e9e5b", "#d98a00", "#d23b4a"
VOCAB_LABELS = {"laugh": "😂 Means she is laughing", "scream": "😱 Means a scream or squeal", "fail": "💀 Means something went wrong", "win": "🏆 Means a win or a clutch",
                "rage": "😤 Means she is annoyed", "scare": "👻 Means she is scared", "cute": "🥰 Means something is cute", "hype": "🔥 General excitement", "chaos": "🌀 Means chaos"}


def method(fn):
    METHODS[fn.__name__] = fn; return fn


def wraps(name):
    def deco(factory): WRAPS[name] = factory; return factory
    return deco


def install(App, module):
    global A
    A = module
    for k, fn in METHODS.items(): setattr(App, k, fn)
    for name, factory in WRAPS.items(): setattr(App, name, factory(getattr(App, name, None)))
    import vc20ui
    r = vc20ui.RESET
    r["smart"] = dict(o=SMART_KEYS, v={})
    r["captions"]["o"] = tuple(r["captions"]["o"]) + CAP22
    r["polish"]["o"] = tuple(r["polish"]["o"]) + POLISH22
    r["extras"]["o"] = tuple(r["extras"]["o"]) + ("hop_logo",)
    r["post"]["o"] = tuple(r["post"]["o"]) + POST22
    r["quick"]["o"] = tuple(r["quick"]["o"]) + ("smart",)


def sc_(): return A.sc


def log_err(): A.log_error(traceback.format_exc())


# ================================================================ set-up / saving
@method
def init22(self, cfg):
    """Called from __init__: the state the 2.2 features keep."""
    c = cfg.get("v22") if isinstance(cfg.get("v22"), dict) else {}
    self.watch_dir = tk.StringVar(value=str(c.get("watch_dir", "") or ""))
    self.watch_on, self.watch_auto = tk.BooleanVar(value=bool(c.get("watch_on", False))), tk.BooleanVar(value=bool(c.get("watch_auto", False)))
    self.plan_offer = tk.BooleanVar(value=bool(c.get("plan_offer", False)))
    self.watch_note, self.taste_note, self.range_note = tk.StringVar(), tk.StringVar(), tk.StringVar()
    self.clip_q = tk.StringVar(value="")
    self.tools_win, self.tools_nb, self.tools_pages = None, None, {}
    self.try22, self.run22, self.watch_job, self.q_job = None, dict(before=set()), None, None
    self.review_win = self.cmp_win = None


@method
def cfg22(self):
    return dict(v22=dict(watch_dir=self.watch_dir.get().strip(), watch_on=bool(self.watch_on.get()), watch_auto=bool(self.watch_auto.get()), plan_offer=bool(self.plan_offer.get())))


@method
def start22(self):
    """Called once the window is built."""
    try:
        self.clip_q.trace_add("write", lambda *a: self.clip_q_changed())
        self.o["game"].trace_add("write", lambda *a: self.cam_fill())
        for k in ("range_from", "range_to"): self.o[k].trace_add("write", lambda *a: self.range_refresh())
        self.watch_on.trace_add("write", lambda *a: self.watch_toggle()); self.watch_dir.trace_add("write", lambda *a: self.watch_toggle(True))
        self.watch_auto.trace_add("write", lambda *a: self.save())
        self.range_refresh(); self.taste_refresh()
        self.watch_job = self.after(45000, self.watch_tick)
        if not os.environ.get("VTC_TEST"): self.after(3500, self.resume_check)
        marks = self.marks
        threading.Thread(target=lambda: vcmore.ledger_mark(list(marks["fav"]), list(marks["posted"])), daemon=True).start()
    except Exception: log_err()


@method
def hook22(self, what, *a):
    """The app calls this when a job starts and when it ends. Nothing in here may ever stop a job."""
    try:
        if what == "start":
            kind = a[0] if a else ""
            if kind in A.RENDER_JOBS:
                vctools.run_start(dict(mode=kind, video=self.v["video"].get().strip().strip('"'), batch=list(self.batch)[:30]))
                try: self.run22["before"] = set(self.clip_files())
                except Exception: self.run22["before"] = set()
                self.cam_remember()
        elif what == "finish":
            bad = bool(a[0]) if a else False
            vctools.run_end()
            self.finish22(bad)
    except Exception: log_err()


# ================================================================ Smart finding tab
@method
def build_smart(self, x):
    o = self.o; x.columnconfigure(0, weight=1); r = [-1]

    def head(t): r[0] += 1; self.head(x, t, r[0])

    def note(t, var=None):
        r[0] += 1; l = ttk.Label(x, text=t, textvariable=var, style="Mute.TLabel", wraplength=660, justify="left") if var is not None else ttk.Label(x, text=t, style="Mute.TLabel", wraplength=660, justify="left")
        l.grid(row=r[0], column=0, sticky="w", pady=(0, 2))

    def check(key, text, tip):
        r[0] += 1; c = ttk.Checkbutton(x, text=text, variable=o[key]); c.grid(row=r[0], column=0, sticky="w", pady=2); self.tip(c, tip)

    head("🧠 Smart clip finding")
    note("I listen for laughs, screams, singing and the shape of a story, and read the words, then pick the best moments of every kind. "
         "Switch it off to find clips the way the older versions did.")
    check("smart", "🧠 Smart finding (recommended)", "Tells gameplay, reactions, talking, stories and singing apart. Every clip is labelled, and the title-ideas file says why it was picked.")
    check("variety", "🎲 Mix different kinds, not five of the same", "Mixes a laugh, a scream and a story instead of the same kind of moment over and over.")
    check("skip_greet", "👋 Skip “hey guys, welcome back” openings", "Clips start on the first real line, not the greeting. (The first 3 seconds decide if people keep watching.)")
    check("smart_len", "📏 Pick the length for each kind of moment", "Reactions run short, stories run longer. Stays near the min - max length you chose.")
    check("tight_end", "✂ End right after the punchline", "Cuts the tail after the laugh or the payoff.")
    check("auto_look", "🎨 Match the captions to the kind of moment", "Gameplay gets pop-in words, stories get line captions, singing gets karaoke.")
    check("use_taste", "💗 Learn from the clips I keep", "Clips you star or mark as posted teach me which kinds and lengths you like.")
    r[0] += 1; tf = ttk.Frame(x); tf.grid(row=r[0], column=0, sticky="w")
    ttk.Label(tf, textvariable=self.taste_note, style="Mute.TLabel", wraplength=560, justify="left").pack(side="left")
    ttk.Button(tf, text="↻", width=3, command=self.taste_refresh).pack(side="left", padx=8)

    head("💬 Chat helps find moments")
    note("Optional. If you saved your stream chat (a .json, .csv or .txt chat log), moments where chat goes wild count for more. "
         "A chat file with the same name next to the video is found by itself.")
    r[0] += 1; cf = ttk.Frame(x); cf.grid(row=r[0], column=0, sticky="we"); cf.columnconfigure(0, weight=1)
    ttk.Entry(cf, textvariable=o["chat_file"]).grid(row=0, column=0, sticky="we")
    ttk.Button(cf, text="Browse", command=lambda: self.browse_chat()).grid(row=0, column=1, padx=6)
    ttk.Button(cf, text="✖", width=3, command=lambda: o["chat_file"].set("")).grid(row=0, column=2)

    head("🎯 Only look between")
    r[0] += 1; rf = ttk.Frame(x); rf.grid(row=r[0], column=0, sticky="w")
    ttk.Label(rf, text="from").pack(side="left"); ttk.Entry(rf, textvariable=o["range_from"], width=10).pack(side="left", padx=6)
    ttk.Label(rf, text="to").pack(side="left"); ttk.Entry(rf, textvariable=o["range_to"], width=10).pack(side="left", padx=6)
    ttk.Label(rf, text="like 1:20:00  -  empty = the whole video", style="Mute.TLabel").pack(side="left", padx=8)
    note("", self.range_note)

    head("🏷 The kinds of moments I look for")
    for k in vcsmart.TYPES:
        ti = vcsmart.TYPE_INFO[k]; r[0] += 1
        ttk.Label(x, text=f"{ti['icon']}  {ti['label']}  -  {ti['hint']}  (about {ti['lo']} - {ti['hi']} s)", wraplength=660, justify="left").grid(row=r[0], column=0, sticky="w", pady=1)
    head("📚 Your own words")
    note("Teach me the slang your chat uses (a catch-phrase, “bonk”, “sheesh”…). Words you add count when I look for laughs, screams, wins and fails.")
    r[0] += 1; ttk.Button(x, text="📚 My words…", command=lambda: self.open_toolbox("vocab")).grid(row=r[0], column=0, sticky="w", pady=(2, 0))


@method
def browse_chat(self):
    p = filedialog.askopenfilename(parent=self, title="Choose a chat log", filetypes=[("Chat logs", "*.json *.csv *.txt *.log"), ("All files", "*.*")])
    if p: self.o["chat_file"].set(p)


@method
def range_refresh(self):
    a, b = vcmore.parse_time(self.o["range_from"].get()), vcmore.parse_time(self.o["range_to"].get())
    ra, rb = str(self.o["range_from"].get()).strip(), str(self.o["range_to"].get()).strip()
    if (ra and a is None) or (rb and b is None): t = "I can't read one of those times. Use 1:20:00, 80:00 or 1h20m."
    elif a is not None and b is not None and b <= a: t = "The end has to be after the start."
    elif a is None and b is None: t = ""
    else: t = "Looking " + (f"from {vctools.hms(a)} " if a is not None else "from the start ") + (f"until {vctools.hms(b)}." if b is not None else "until the end.")
    self.range_note.set(t)


@method
def taste_refresh(self):
    try: t = vcsmart.taste(vcmore.ledger_all())
    except Exception: t = None
    self.taste_note.set(vcsmart.taste_text(t))


# ================================================================ extra rows in the existing tabs
def _box(self, tab, title):
    f = ttk.Frame(tab)
    if tab.pack_slaves(): f.pack(fill="x", anchor="w", pady=(12, 0))
    else: f.grid(row=tab.grid_size()[1], column=0, columnspan=4, sticky="we", pady=(12, 0))
    h = ttk.Label(f, text=title, font=(A.FONT, 10, "bold"), foreground=self.t["accent"]); h.pack(anchor="w", pady=(0, 3)); self.fxheads.append(h)
    g = ttk.Frame(f); g.pack(fill="x", anchor="w"); g.columnconfigure(1, weight=1)
    return g


def _check(self, g, row, key, text, tip):
    c = ttk.Checkbutton(g, text=text, variable=self.o[key]); c.grid(row=row, column=0, columnspan=3, sticky="w", pady=2); self.tip(c, tip); return c


@method
def build22_rows(self):
    """Called once, after every tab is built: adds the 2.2 rows at the bottom of the tabs they belong to."""
    o, subs = self.o, self.subs
    g = _box(self, subs["captions"], "✨ More caption styling")
    rows = (("Letters", self.pick(g, o["cap_case"], vcmore.CAP_CASES, 22), "ALL CAPS, normal, lower case - or what the style always did."),
            ("Outline", self.pick(g, o["cap_outline"], {k: v[0] for k, v in vcmore.CAP_OUTLINES.items()}, 22), "How thick the dark edge around the words is."),
            ("Shadow", self.spin(g, o["cap_shadow"], 0, 8, 1, 5), "0 = none. A soft dark shadow under the words."),
            ("Words at a time", self.spin(g, o["cap_words"], 0, 7, 1, 5), "0 = the style decides. 1-3 gives fast, punchy captions."),
            ("Box behind the words", self.spin(g, o["cap_box"], 0, 100, 10, 5), "0 = no box. Higher = a darker box (helps on busy pictures)."))
    for i, (lab, w, tp) in enumerate(rows):
        ttk.Label(g, text=lab).grid(row=i, column=0, sticky="w", pady=3); w.grid(row=i, column=1, sticky="w", padx=8); self.tip(w, tp)
    _check(self, g, len(rows), "cap_rainbow", "🌈 Rainbow words", "The big words cycle through your highlight colour and two friends.")
    _check(self, g, len(rows) + 1, "react_words", "💥 Big reaction words on laughs, screams, fails and wins (LOL, EEEEK!, OOF, LET'S GO!)", "Pops a big word in the middle of the clip at the moment it happens.")

    g = _box(self, subs["polish"], "🔊 Calm the sound")
    _check(self, g, 0, "tame", "🔉 Tame loud screams", "Lets the scream through but stops it from blowing out your viewers' ears.")
    _check(self, g, 1, "hush", "🌬 Hush the background hiss", "Takes out steady noise like a fan or a mic hiss.")
    g = _box(self, subs["polish"], "🎞 Dramatic beats")
    _check(self, g, 0, "slowmo", "🐌 Slow-mo on the biggest moment", "The biggest moment plays slowly for a second, then goes back to normal speed.")
    _check(self, g, 1, "freeze", "⏸ Freeze-frame beat on a second moment", "The picture stops for a heartbeat on a big moment.")
    _check(self, g, 2, "teaser", "🎬 Teaser first: show the best moment for 2 seconds, then start", "Puts a flash of the best moment at the very start so people keep watching.")

    g = _box(self, subs["extras"], "🧷 Logo")
    _check(self, g, 0, "hop_logo", "🦘 Move my logo to a new corner every few seconds", "Makes it hard to crop your logo out of a stolen clip.")

    g = _box(self, subs["post"], "📦 More files")
    ttk.Label(g, text="Extra copies").grid(row=0, column=0, sticky="w", pady=3)
    w = self.pick(g, o["extra_shapes"], vcmore.EXTRA_SHAPES, 30); w.grid(row=0, column=1, sticky="w", padx=8); self.tip(w, "Makes a square or landscape version next to the tall one (for X, Facebook, YouTube).")
    ttk.Label(g, text="Ready-to-post folder").grid(row=1, column=0, sticky="w", pady=3)
    ef = ttk.Frame(g); ef.grid(row=1, column=1, columnspan=2, sticky="we", padx=8); ef.columnconfigure(0, weight=1)
    ttk.Entry(ef, textvariable=o["ready_dir"]).grid(row=0, column=0, sticky="we")
    ttk.Button(ef, text="Browse", command=lambda: o["ready_dir"].set(filedialog.askdirectory(parent=self) or o["ready_dir"].get())).grid(row=0, column=1, padx=6)
    ttk.Button(ef, text="✖", width=3, command=lambda: o["ready_dir"].set("")).grid(row=0, column=2)
    self.tip(ef, "Each finished clip (with its title ideas, subtitles and cover) is also copied here. Empty = off.")
    pc = ttk.Checkbutton(g, text="🗓 Offer to put new clips in the post planner when a run is finished", variable=self.plan_offer, command=self.save)
    pc.grid(row=2, column=0, columnspan=3, sticky="w", pady=2); self.tip(pc, "After a run, I can add the new clips to the planner at good times for your platform.")
    bf = ttk.Frame(g); bf.grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))
    ttk.Button(bf, text="# Hashtag bank…", command=lambda: self.open_toolbox("tags")).pack(side="left")
    ttk.Button(bf, text="📄 Post sheet (CSV)…", command=lambda: self.open_toolbox("sheet")).pack(side="left", padx=8)
    ttk.Label(g, text="File names can use {type} {score} {len} as well: {date} {type} {score} clip {n}", style="Mute.TLabel").grid(row=4, column=0, columnspan=3, sticky="w", pady=(4, 0))


@method
def left22(self, mk):
    """Under the big Make button: 'try just one first'."""
    row = ttk.Frame(mk.master); row.pack(fill="x", after=mk, pady=(2, 0))
    b = ttk.Button(row, text="👀 Try just one first", command=self.try_one_first); b.pack(side="left")
    self.tip(b, "Makes only the first clip, so you can check how the look works. Then I ask if I should make the rest.")
    self.try_btn = b


# ================================================================ try one first / finish / resume
@method
def try_one_first(self):
    if self.busy: return messagebox.showinfo("VTuber Clipper", "I'm busy right now~ try again when this finishes.")
    if self.mode.get() != "shorts": self.mode.set("shorts")
    try: n = int(float(self.v["n"].get()))
    except ValueError: n = 8
    if n < 2: return self.make()
    self.try22 = dict(n=n, fresh=bool(self.o["fresh"].get()), stage=1)
    self.v["n"].set("1"); self.make()
    if not self.busy: self.try_restore()


@method
def try_restore(self):
    t = self.try22
    if t:
        self.v["n"].set(str(t["n"])); self.o["fresh"].set(t["fresh"])
    self.try22 = None


@method
def finish22(self, bad):
    """After a job: the second half of 'try one first', the planner offer and the next watched video."""
    t = self.try22
    if t:
        if t["stage"] == 1:
            self.v["n"].set(str(t["n"]))
            if bad: self.try22 = None
            else:
                rest = t["n"] - 1
                if messagebox.askyesno("Try one first", f"Your first clip is ready (see 🖼 My clips).\n\nDo you like it? Then I make the other {rest} with the same settings.\nIf not, change the look and press Try one first again."):
                    t["stage"] = 2; self.o["fresh"].set(True); self.v["n"].set(str(rest))
                    self.after(300, self.try_second)
                else: self.try_restore()
        else: self.try_restore()
    elif not bad and getattr(self, "job_mode", "") == "shorts" and self.plan_offer.get():
        try:
            new = [f for f in self.clip_files() if f not in self.run22["before"] and not f.lower().endswith(("_1x1.mp4", "_16x9.mp4"))]
            if new and messagebox.askyesno("Post planner", f"Put the {len(new)} new clip{'s' if len(new) != 1 else ''} in the post planner at good times?"): self.plan_autofill(new)
        except Exception: log_err()
    self.taste_refresh()


@method
def try_second(self):
    if self.busy or not self.try22: return
    self.make()
    if not self.busy: self.try_restore()


@method
def resume_check(self):
    d = vctools.run_left()
    if not d: return
    vctools.run_end()
    if self.busy or not os.path.isfile(str(d.get("video", ""))): return
    names = {"shorts": "Shorts", "long": "a recap", "twitter": "an X video"}
    if not messagebox.askyesno("Pick up where I left off?", f"Last time {names.get(d['mode'], 'a job')} for “{os.path.basename(d['video'])}” didn't finish (started {d.get('started', '')}).\n\n"
                                                              "Pick it up again? Clips that were already made are skipped, and the analysis is remembered, so it goes faster."): return
    batch = [p for p in d.get("batch", []) if isinstance(p, str) and os.path.isfile(p)]
    self.batch = batch if len(batch) > 1 else []
    self.v["video"].set(d["video"])
    if d["mode"] in ("shorts", "long", "twitter"): self.mode.set(d["mode"])
    if d["mode"] == "shorts": self.o["fresh"].set(True)
    self.after(400, self.make)


# ================================================================ cam memory
@method
def cam_size(self):
    p = self.v["video"].get().strip().strip('"')
    try:
        if self.vinfo.get("path") == p and self.vinfo.get("w"): return f"{self.vinfo['w']}x{self.vinfo['h']}"
    except Exception: pass
    return ""


@method
def cam_fill(self):
    """A game is named and no cam box is set: use the one remembered for that game (if the video has the same size)."""
    try:
        if self.v["cam"].get().strip(): return
        g = self.o["game"].get().strip()
        if not g: return
        cam = vctools.cam_get(g, self.cam_size())
        if cam: self.v["cam"].set(cam); self.status.set(f"Used the cam box I remembered for {g} ♡")
    except Exception: log_err()


@method
def cam_remember(self):
    g, cam = self.o["game"].get().strip(), self.v["cam"].get().strip()
    if g and cam: vctools.cam_put(g, cam, self.cam_size())


@wraps("make")
def _w_make(orig):
    def make(self):
        self.cam_fill()
        return orig(self)
    return make


# ================================================================ planner
@method
def plan_autofill(self, files):
    plat = PLAT_OF.get(self.o["platform"].get(), "tiktok")
    files = list(reversed(list(files)))                        # the oldest clip goes first
    times = vctools.spread_times(vcnew.BEST_TIMES[plat][1], len(files))
    for f, t in zip(files, times): self.plan = vcnew.plan_add(self.plan, f, plat, t, os.path.basename(f))
    self.plan_save(); self.status.set(f"Added {len(times)} clip{'s' if len(times) != 1 else ''} to the post planner ♡")


@method
def plan_new_clips(self):
    planned = {os.path.normpath(d["clip"]) for d in self.plan}
    files = [f for f in self.clip_files()[:60] if not self.marks["posted"].get(os.path.normpath(f)) and os.path.normpath(f) not in planned
             and not f.lower().endswith(("_1x1.mp4", "_16x9.mp4"))][:12]
    if not files: return messagebox.showinfo("VTuber Clipper", "Every recent clip is posted or already in the planner ♡")
    if messagebox.askyesno("Post planner", f"Add your {len(files)} newest unplanned clips to the post planner, one per good time slot?"): self.plan_autofill(files)


# ================================================================ watch folder
@method
def watch_toggle(self, folder_changed=False):
    try:
        self.save()
        if not self.watch_on.get():
            self.watch_note.set("Not watching."); return
        folder = self.watch_dir.get().strip().strip('"')
        if not os.path.isdir(folder): self.watch_note.set("Choose a folder that exists first."); return
        if vctools.store_get("watch_base", "") != folder:             # a new folder: the videos that are already there don't count as new
            old = vctools.scan_watch(folder, [], min_age=0, min_bytes=0)
            vctools.store_put("watch_seen", vctools.remember_seen([], old)); vctools.store_put("watch_base", folder)
            self.watch_note.set(f"Watching “{folder}”. The {len(old)} video{'s' if len(old) != 1 else ''} already in there are ignored.")
        else: self.watch_note.set(f"Watching “{folder}”.")
    except Exception: log_err()


@method
def watch_tick(self):
    try:
        if self.watch_on.get(): self.watch_check()
    except Exception: log_err()
    try: self.watch_job = self.after(60000, self.watch_tick)
    except tk.TclError: pass


@method
def watch_check(self, manual=False):
    folder = self.watch_dir.get().strip().strip('"')
    if not os.path.isdir(folder): self.watch_note.set("That folder doesn't exist."); return
    if self.busy:
        if manual: self.watch_note.set("I'm busy making something - checking again later.")
        return
    seen = vctools.store_get("watch_seen", [])
    new = vctools.scan_watch(folder, seen)
    stamp = time.strftime("%H:%M")
    if not new: self.watch_note.set(f"Nothing new in the folder (checked {stamp})."); return
    vctools.store_put("watch_seen", vctools.remember_seen(seen, new))
    names = ", ".join(os.path.basename(p) for p in new[:3]) + (" …" if len(new) > 3 else "")
    self.watch_note.set(f"New: {names}  ({stamp})")
    if self.watch_auto.get():
        self.batch = list(new) if len(new) > 1 else []
        self.v["video"].set(new[0]); self.mode.set("shorts"); self.status.set("New video in your watched folder: making Shorts ♡")
        self.after(1500, lambda: None if self.busy else self.make())
    else:
        self.chime()
        if messagebox.askyesno("New video", f"A new video is in your watched folder:\n{names}\n\nLoad it now?"):
            self.batch = list(new) if len(new) > 1 else []
            self.v["video"].set(new[0])


# ================================================================ Tools window
@method
def open_toolbox(self, tab=None):
    w = self.tools_win
    try:
        if w is not None and w.winfo_exists():
            w.lift()
            if tab in self.tools_pages: self.tools_nb.select(self.tools_pages[tab])
            return
    except tk.TclError: pass
    w = self.tools_win = tk.Toplevel(self); w.title("Tools 🧰"); w.configure(bg=self.t["bg"]); w.transient(self)
    A.center_over(w, self, 800, min(660, max(480, self.winfo_height() - 60))); w.minsize(700, 460)
    nb = self.tools_nb = ttk.Notebook(w); nb.pack(fill="both", expand=True, padx=10, pady=10)
    self.tools_pages = {}
    for key, title, fn in (("watch", "👀 Watch folder", _tp_watch), ("health", "🩺 Health", _tp_health), ("clean", "🧹 Clean up", _tp_clean), ("space", "💾 Space", _tp_space),
                           ("looks", "🎨 Looks", _tp_looks), ("tags", "# Hashtags", _tp_tags), ("vocab", "📚 My words", _tp_vocab), ("sheet", "📄 Post sheet", _tp_sheet)):
        f = ttk.Frame(nb, padding=16); nb.add(f, text=title); self.tools_pages[key] = f
        try: fn(self, f)
        except Exception:
            log_err(); ttk.Label(f, text="This page could not be built - see the log file.", style="Mute.TLabel").pack(anchor="w")
    if tab in self.tools_pages: nb.select(self.tools_pages[tab])


def _intro(self, f, text):
    l = ttk.Label(f, text=text, wraplength=700, justify="left"); l.pack(anchor="w", pady=(0, 8)); return l


def _tp_watch(self, f):
    _intro(self, f, "Watch a folder, for example the one where OBS saves your recordings. When a finished video shows up there, I tell you and load it for you "
                    "(or start making Shorts by myself, if you tick that). It only works while this app is open.")
    r = ttk.Frame(f); r.pack(fill="x"); r.columnconfigure(1, weight=1)
    ttk.Label(r, text="Folder").grid(row=0, column=0, sticky="w")
    ttk.Entry(r, textvariable=self.watch_dir).grid(row=0, column=1, sticky="we", padx=8)
    ttk.Button(r, text="Browse", command=lambda: self.watch_dir.set(filedialog.askdirectory(parent=self.tools_win) or self.watch_dir.get())).grid(row=0, column=2)
    ttk.Checkbutton(f, text="👀 Watch this folder while the app is open", variable=self.watch_on).pack(anchor="w", pady=(10, 2))
    c = ttk.Checkbutton(f, text="🚀 Start making Shorts by myself when a new video appears", variable=self.watch_auto); c.pack(anchor="w", pady=2)
    self.tip(c, "Uses the look and settings that are on screen. Several new videos are made one after another. Leave it off to be asked first.")
    ttk.Button(f, text="Check now", command=lambda: self.watch_check(True)).pack(anchor="w", pady=(10, 4))
    ttk.Label(f, textvariable=self.watch_note, style="Mute.TLabel", wraplength=700, justify="left").pack(anchor="w")
    ttk.Label(f, text="A video counts as finished when it hasn't changed for half a minute. Videos that were already in the folder when you switched this on are ignored.",
              style="Mute.TLabel", wraplength=700, justify="left").pack(anchor="w", pady=(10, 0))


def _tp_health(self, f):
    _intro(self, f, "Checks that everything the app needs is in place: the video tool, the downloader, speech-to-text, fonts, free space and your save folder. Nothing is changed.")
    bar = ttk.Frame(f); bar.pack(fill="x")
    self.health_sum = tk.StringVar(value="")
    ttk.Button(bar, text="🩺 Check my app", style="Accent.TButton", command=self.run_health).pack(side="left")
    ttk.Button(bar, text="📋 Copy the report", command=self.copy_health).pack(side="left", padx=8)
    ttk.Label(bar, textvariable=self.health_sum, font=(A.FONT, 10, "bold")).pack(side="left", padx=8)
    tf = ttk.Frame(f); tf.pack(fill="both", expand=True, pady=(10, 0))
    self.health_text = tk.Text(tf, height=14, wrap="word", relief="flat", padx=10, pady=8, font=(A.FONT, 10), bg=self.t["entry"], fg=self.t["fg"])
    sb = ttk.Scrollbar(tf, orient="vertical", command=self.health_text.yview); self.health_text.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y"); self.health_text.pack(side="left", fill="both", expand=True)
    for k, col in (("ok", GOOD), ("warn", WARN), ("bad", BAD)): self.health_text.tag_configure(k, foreground=col, font=(A.FONT, 10, "bold"))
    self.health_text.tag_configure("d", foreground=self.t["mute"]); self.health_text.configure(state="disabled"); self.health_items = []


@method
def run_health(self):
    self.health_sum.set("Checking…"); out = self.v["out"].get().strip()          # Tk values are read here, not in the worker thread

    def go():
        try: items = vctools.health(A.sc, out, A.APP_DIR, A.sc.CACHE_DIR)
        except Exception: log_err(); items = [dict(level="bad", title="The check itself failed", detail=traceback.format_exc()[-200:])]
        self.ui(lambda: self.show_health(items))
    threading.Thread(target=go, daemon=True).start()


@method
def show_health(self, items):
    self.health_items = items
    try:
        t = self.health_text; t.configure(state="normal"); t.delete("1.0", "end")
        for i in items:
            t.insert("end", {"ok": "✔  ", "warn": "!  ", "bad": "✖  "}[i["level"]], i["level"]); t.insert("end", i["title"] + "\n", "")
            if i["detail"]: t.insert("end", "      " + i["detail"] + "\n", "d")
        t.configure(state="disabled"); self.health_sum.set(vctools.health_summary(items))
    except tk.TclError: pass


@method
def copy_health(self):
    if not self.health_items: return self.run_health()
    txt = "VTuber Clipper health check\n" + "\n".join(f"[{i['level'].upper()}] {i['title']}" + (f" - {i['detail']}" if i["detail"] else "") for i in self.health_items)
    self.clipboard_clear(); self.clipboard_append(txt); self.update(); self.status.set("Copied the report ♡")


def _tp_clean(self, f):
    _intro(self, f, "Looks in your save folder for things a stopped or crashed run left behind: half-finished render folders, half downloads, and title / subtitle / cover files whose video is gone. "
                    "You choose what to remove. Your finished clips are never touched.")
    bar = ttk.Frame(f); bar.pack(fill="x")
    self.clean_sum = tk.StringVar()
    ttk.Button(bar, text="🔍 Look for leftovers", style="Accent.TButton", command=self.run_leftovers).pack(side="left")
    ttk.Button(bar, text="Select all", command=lambda: self.clean_list.selection_set(0, "end")).pack(side="left", padx=8)
    ttk.Button(bar, text="🗑 Remove selected", command=self.remove_leftovers).pack(side="left")
    ttk.Label(f, textvariable=self.clean_sum, style="Mute.TLabel").pack(anchor="w", pady=6)
    lf = ttk.Frame(f); lf.pack(fill="both", expand=True)
    self.clean_list = tk.Listbox(lf, selectmode="extended", relief="flat", font=(A.FONT, 10), bg=self.t["entry"], fg=self.t["fg"], selectbackground=self.t["accent"], selectforeground=self.t["on"], activestyle="none")
    sb = ttk.Scrollbar(lf, orient="vertical", command=self.clean_list.yview); self.clean_list.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y"); self.clean_list.pack(side="left", fill="both", expand=True); self.clean_items = []


@method
def run_leftovers(self):
    self.clean_sum.set("Looking…"); out = self.v["out"].get().strip()

    def go():
        try: items = vctools.find_leftovers(out)
        except Exception: log_err(); items = []
        self.ui(lambda: self.show_leftovers(items))
    threading.Thread(target=go, daemon=True).start()


@method
def show_leftovers(self, items):
    try:
        self.clean_items = items; self.clean_list.delete(0, "end")
        for i in items:
            rel = os.path.relpath(i["path"], self.v["out"].get().strip()) if self.v["out"].get().strip() else i["path"]
            self.clean_list.insert("end", f"{rel}   -   {i['why']}   ({vctools.human(i['bytes'])})")
        tot = sum(i["bytes"] for i in items)
        self.clean_sum.set(f"{len(items)} leftover{'s' if len(items) != 1 else ''}, {vctools.human(tot)} in all." if items else "Nothing to clean up ♡")
    except tk.TclError: pass


@method
def remove_leftovers(self):
    sel = [self.clean_items[i] for i in self.clean_list.curselection() if i < len(self.clean_items)]
    if not sel: return messagebox.showinfo("VTuber Clipper", "Click the things you want to remove first (or press Select all) ♡", parent=self.tools_win)
    if not messagebox.askyesno("VTuber Clipper", f"Remove {len(sel)} leftover{'s' if len(sel) != 1 else ''} for good?", parent=self.tools_win): return
    n, freed = vctools.remove_paths([i["path"] for i in sel])
    self.run_leftovers(); self.status.set(f"Removed {n}, freed {vctools.human(freed)} ♡")


def _tp_space(self, f):
    _intro(self, f, "The app keeps some helper files so it is faster the next time. They are safe to empty - they are made again when needed. "
                    "Below that: the videos you downloaded, which are usually the biggest thing on your drive.")
    self.space_box = ttk.Frame(f); self.space_box.pack(fill="x")
    ttk.Label(f, text="Downloaded videos (save folder → VODs)", font=(A.FONT, 10, "bold"), foreground=self.t["accent"]).pack(anchor="w", pady=(12, 4))
    bar = ttk.Frame(f); bar.pack(fill="x")
    ttk.Button(bar, text="↻ Refresh", command=self.refresh_space).pack(side="left")
    ttk.Button(bar, text="🗑 Delete selected videos", command=self.delete_vods).pack(side="left", padx=8)
    self.space_sum = tk.StringVar(); ttk.Label(bar, textvariable=self.space_sum, style="Mute.TLabel").pack(side="left", padx=8)
    lf = ttk.Frame(f); lf.pack(fill="both", expand=True, pady=(6, 0))
    self.vod_list = tk.Listbox(lf, selectmode="extended", relief="flat", font=(A.FONT, 10), bg=self.t["entry"], fg=self.t["fg"], selectbackground=self.t["accent"], selectforeground=self.t["on"], activestyle="none", height=6)
    sb = ttk.Scrollbar(lf, orient="vertical", command=self.vod_list.yview); self.vod_list.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y"); self.vod_list.pack(side="left", fill="both", expand=True); self.vod_items = []
    self.refresh_space()


@method
def refresh_space(self):
    out = self.v["out"].get().strip()

    def go():
        try:
            rep = vctools.cache_report(A.sc.CACHE_DIR, A.GIF_DIR); vods = vctools.vod_files(out)
        except Exception: log_err(); rep, vods = [], []
        self.ui(lambda: self.show_space(rep, vods))
    threading.Thread(target=go, daemon=True).start()


@method
def show_space(self, rep, vods):
    try:
        for w in self.space_box.winfo_children(): w.destroy()
        self.space_box.columnconfigure(1, weight=1)
        for i, r in enumerate(rep):
            ttk.Label(self.space_box, text=r["label"]).grid(row=i, column=0, sticky="w", pady=3)
            ttk.Label(self.space_box, text=f"{vctools.human(r['bytes'])}  ({r['count']} file{'s' if r['count'] != 1 else ''})", style="Mute.TLabel").grid(row=i, column=1, sticky="w", padx=12)
            b = ttk.Button(self.space_box, text="Empty", command=lambda k=r["key"]: self.empty_cache(k)); b.grid(row=i, column=2, sticky="e")
            if not r["bytes"]: b.state(["disabled"])
            self.tip(b, r["note"])
        self.vod_items = vods; self.vod_list.delete(0, "end")
        for p, b, age in vods: self.vod_list.insert("end", f"{os.path.basename(p)}   -   {vctools.human(b)}   ({age} day{'s' if age != 1 else ''} old)")
        self.space_sum.set(f"{len(vods)} video{'s' if len(vods) != 1 else ''}, {vctools.human(sum(v[1] for v in vods))}" if vods else "No downloaded videos found.")
    except tk.TclError: pass


@method
def empty_cache(self, key):
    freed = vctools.cache_clear(A.sc.CACHE_DIR, key, A.GIF_DIR)
    self.status.set(f"Freed {vctools.human(freed)} ♡"); self.refresh_space()


@method
def delete_vods(self):
    sel = [self.vod_items[i] for i in self.vod_list.curselection() if i < len(self.vod_items)]
    if not sel: return messagebox.showinfo("VTuber Clipper", "Click the videos you want to delete first ♡", parent=self.tools_win)
    if not messagebox.askyesno("VTuber Clipper", f"Delete {len(sel)} downloaded video{'s' if len(sel) != 1 else ''} ({vctools.human(sum(s[1] for s in sel))}) for good?\n\n"
                                                  "Your finished clips stay. You can download the VOD again if it is still online.", parent=self.tools_win): return
    n, freed = vctools.remove_paths([s[0] for s in sel])
    for p in [s[0] for s in sel]:
        for ext in (".words.json",):
            for g in glob.glob(glob.escape(p) + ".words*.json"):
                try: os.remove(g)
                except OSError: pass
    self.status.set(f"Deleted {n} video{'s' if n != 1 else ''}, freed {vctools.human(freed)} ♡"); self.refresh_space()


def _tp_looks(self, f):
    _intro(self, f, "Share the look you have on screen as one line of text and paste a friend's. A look code holds the style, layout, captions and effects - not your logo, name, music or any file.")
    ttk.Label(f, text="Share my look", font=(A.FONT, 10, "bold"), foreground=self.t["accent"]).pack(anchor="w", pady=(4, 2))
    ttk.Button(f, text="📋 Copy my look code", style="Accent.TButton", command=self.copy_look_code).pack(anchor="w")
    ttk.Label(f, text="Use a friend's look", font=(A.FONT, 10, "bold"), foreground=self.t["accent"]).pack(anchor="w", pady=(16, 2))
    self.look_box = tk.Text(f, height=4, wrap="char", relief="flat", padx=8, pady=6, font=("Consolas", 9), bg=self.t["entry"], fg=self.t["fg"], insertbackground=self.t["fg"]); self.look_box.pack(fill="x")
    bf = ttk.Frame(f); bf.pack(anchor="w", pady=6)
    ttk.Button(bf, text="✨ Use this look", command=lambda: self.use_look_code(False)).pack(side="left")
    ttk.Button(bf, text="💾 Save it as my style", command=lambda: self.use_look_code(True)).pack(side="left", padx=8)
    ttk.Label(f, text="Compare looks", font=(A.FONT, 10, "bold"), foreground=self.t["accent"]).pack(anchor="w", pady=(16, 2))
    ttk.Label(f, text="Renders the same few seconds with three looks side by side, so you can pick the one you like.", style="Mute.TLabel", wraplength=700).pack(anchor="w")
    ttk.Button(f, text="🆚 Compare 3 looks…", command=self.open_compare).pack(anchor="w", pady=6)


@method
def copy_look_code(self):
    name = (self.pinfo.get().split(" — ")[0] if self.sel_preset.get() else "My look")[:40]
    code = vctools.look_code(self.get_look(), name)
    self.clipboard_clear(); self.clipboard_append(code); self.update(); self.status.set("Copied your look code - paste it to a friend ♡")


@method
def use_look_code(self, save):
    try:
        name, look = vctools.look_from_code(self.look_box.get("1.0", "end"))
        L = A.vp.safe_look(look)
    except ValueError as e: return messagebox.showerror("VTuber Clipper", str(e), parent=self.tools_win)
    if save:
        p = A.vp.new_user_preset(name or "Shared look", L, self.all_presets()); self.add_user_preset(p)
        self.status.set(f"Saved the look “{p['name']}” as one of your styles ♡")
    else:
        self.sel_preset.set(""); self.apply_look(L); self.update_pinfo(); self.draw_gallery(); self.refresh_eta(); self.save()
        self.status.set("Using the look from the code ♡  (press 💾 Save as my style to keep it)")


def _tp_tags(self, f):
    _intro(self, f, "Your own hashtags, added to the post ideas of every clip. “Always” goes on every clip, the game list on clips for that game, and the kind list on that kind of moment.")
    b = vctools.bank_load()
    ttk.Label(f, text="Always add").pack(anchor="w")
    self.bank_always = tk.StringVar(value=" ".join("#" + t for t in b["always"])); ttk.Entry(f, textvariable=self.bank_always).pack(fill="x", pady=(0, 8))
    ttk.Label(f, text="Per game - one game per line, like  Minecraft: #minecraft #cozygames").pack(anchor="w")
    self.bank_games = tk.Text(f, height=4, wrap="word", relief="flat", padx=8, pady=6, font=(A.FONT, 10), bg=self.t["entry"], fg=self.t["fg"], insertbackground=self.t["fg"])
    self.bank_games.pack(fill="x", pady=(0, 8)); self.bank_games.insert("1.0", "\n".join(f"{g}: " + " ".join("#" + t for t in tags) for g, tags in b["games"].items()))
    ttk.Label(f, text="Per kind of moment").pack(anchor="w")
    kf = ttk.Frame(f); kf.pack(fill="x"); kf.columnconfigure(1, weight=1); self.bank_kinds = {}
    for i, k in enumerate(vcsmart.TYPES):
        ti = vcsmart.TYPE_INFO[k]; ttk.Label(kf, text=f"{ti['icon']} {ti['label']}").grid(row=i, column=0, sticky="w", pady=2)
        var = tk.StringVar(value=" ".join("#" + t for t in b["kinds"].get(k, []))); ttk.Entry(kf, textvariable=var).grid(row=i, column=1, sticky="we", padx=8); self.bank_kinds[k] = var
    ttk.Button(f, text="💾 Save my hashtags", style="Accent.TButton", command=self.save_bank).pack(anchor="w", pady=12)


@method
def save_bank(self):
    games = {}
    for line in self.bank_games.get("1.0", "end").splitlines():
        if ":" in line:
            g, _, t = line.partition(":"); g = g.strip().lower(); tags = vctools.split_tags(t)
            if g and tags: games[g] = tags
    b = dict(always=vctools.split_tags(self.bank_always.get()), games=games, kinds={k: vctools.split_tags(v.get()) for k, v in self.bank_kinds.items() if vctools.split_tags(v.get())})
    ok = vctools.bank_save(b)
    self.status.set("Saved your hashtags ♡" if ok else "I couldn't save the hashtags (is your user folder writable?)")


def _tp_vocab(self, f):
    _intro(self, f, "Teach me words your chat or you use a lot. One word each, separated by commas. They count when I look for laughs, screams, wins and fails - on the next run.")
    v = vctools.vocab_load(); self.vocab_vars = {}
    g = ttk.Frame(f); g.pack(fill="x"); g.columnconfigure(1, weight=1)
    for i, k in enumerate(vcsmart.VOCAB_KINDS):
        ttk.Label(g, text=VOCAB_LABELS.get(k, k)).grid(row=i, column=0, sticky="w", pady=2)
        var = tk.StringVar(value=", ".join(v.get(k, []))); ttk.Entry(g, textvariable=var).grid(row=i, column=1, sticky="we", padx=8); self.vocab_vars[k] = var
    bf = ttk.Frame(f); bf.pack(fill="x", pady=10)
    ttk.Button(bf, text="💾 Save my words", style="Accent.TButton", command=self.save_vocab).pack(side="left")
    ttk.Button(bf, text="💡 Suggest words from the clips I starred", command=self.suggest_words).pack(side="left", padx=8)
    self.vocab_note = tk.StringVar(); ttk.Label(f, textvariable=self.vocab_note, style="Mute.TLabel", wraplength=700, justify="left").pack(anchor="w")
    sf = ttk.Frame(f); sf.pack(fill="x", pady=4)
    self.sug_list = tk.Listbox(sf, height=5, relief="flat", font=(A.FONT, 10), bg=self.t["entry"], fg=self.t["fg"], selectbackground=self.t["accent"], selectforeground=self.t["on"], activestyle="none", exportselection=False)
    self.sug_list.pack(side="left", fill="x", expand=True)
    ab = ttk.Frame(sf); ab.pack(side="left", padx=8)
    self.sug_kind = tk.StringVar(value="hype"); self.combo(ab, self.sug_kind, list(vcsmart.VOCAB_KINDS), 10).pack()
    ttk.Button(ab, text="＋ Add to this list", command=self.add_suggested).pack(pady=4)


@method
def save_vocab(self):
    v = {k: vctools.split_vocab(var.get()) for k, var in self.vocab_vars.items()}
    if vctools.vocab_save(v):
        self.vocab_note.set("Saved. I'll use these words from the next run on ♡")
        for k, var in self.vocab_vars.items(): var.set(", ".join(v[k]))
    else: self.vocab_note.set("I couldn't save the words (is your user folder writable?).")


@method
def suggest_words(self):
    favs = [f for f in self.clip_files() if self.is_fav(f) or self.marks["posted"].get(os.path.normpath(f))]
    rest = [f for f in self.clip_files()[:200] if f not in set(favs)]
    if len(favs) < 3: self.vocab_note.set("Star at least 3 clips (My clips → ⋯ More) and turn on “A transcript” in Posting & files, then I can suggest words."); return
    self.vocab_note.set("Looking…"); known = [w for var in self.vocab_vars.values() for w in vctools.split_vocab(var.get())]

    def go():
        try: sug = vctools.suggest_vocab(favs[:80], rest[:120], known)
        except Exception: log_err(); sug = []
        self.ui(lambda: self.show_suggest(sug))
    threading.Thread(target=go, daemon=True).start()


@method
def show_suggest(self, sug):
    try:
        self.sug_list.delete(0, "end")
        for w, c in sug: self.sug_list.insert("end", f"{w}   (in {c} of your starred clips)")
        self.vocab_note.set("These come up often in your starred clips: pick one and choose a list." if sug else
                            "Nothing stands out yet. Suggestions need the transcript files (Posting & files → A transcript) next to your starred clips.")
        self.sug_words = [w for w, _ in sug]
    except tk.TclError: pass


@method
def add_suggested(self):
    sel = self.sug_list.curselection()
    if not sel or sel[0] >= len(getattr(self, "sug_words", [])): return
    k = self.sug_kind.get(); var = self.vocab_vars.get(k)
    if var is None: return
    w = self.sug_words[sel[0]]; cur = vctools.split_vocab(var.get())
    if w not in cur: cur.append(w)
    var.set(", ".join(cur)); self.vocab_note.set(f"Added “{w}” to the list - press Save my words.")


def _tp_sheet(self, f):
    _intro(self, f, "Saves a spreadsheet (.csv, opens in Excel or Google Sheets) with one row per clip: file, kind, hype, title, description, hashtags, where you posted it, your tags and where in the VOD it came from.")
    self.sheet_fav, self.sheet_unposted = tk.BooleanVar(value=False), tk.BooleanVar(value=False)
    ttk.Checkbutton(f, text="★ Only my favourites", variable=self.sheet_fav).pack(anchor="w", pady=2)
    ttk.Checkbutton(f, text="Only clips I haven't posted yet", variable=self.sheet_unposted).pack(anchor="w", pady=2)
    ttk.Button(f, text="📄 Save the sheet…", style="Accent.TButton", command=self.save_sheet).pack(anchor="w", pady=12)


@method
def save_sheet(self):
    files = self.clip_files()
    if self.sheet_fav.get(): files = [f for f in files if self.is_fav(f)]
    if self.sheet_unposted.get(): files = [f for f in files if not self.marks["posted"].get(os.path.normpath(f))]
    if not files: return messagebox.showinfo("VTuber Clipper", "No clips match yet ♡", parent=self.tools_win)
    p = filedialog.asksaveasfilename(parent=self.tools_win, title="Save the post sheet", defaultextension=".csv", initialfile="my_clips.csv", filetypes=[("Spreadsheet (CSV)", "*.csv")])
    if not p: return
    rows = vctools.post_rows(files, self.marks["posted"], self.marks["fav"], vcmore.ledger_find, vctools.clip_tags)
    n = vctools.write_csv(p, rows)
    if n: self.status.set(f"Saved {n} clip{'s' if n != 1 else ''} to {os.path.basename(p)} ♡")
    else: messagebox.showerror("VTuber Clipper", "I couldn't save that file. Is it open in Excel? Close it and try again.", parent=self.tools_win)


# ================================================================ compare looks
@method
def open_compare(self):
    if self.busy: return messagebox.showinfo("VTuber Clipper", "I'm busy right now~ try again when this finishes.")
    pres = self.all_presets()
    names = ["★ My current settings"] + [f"{p['emoji']} {p['name']}" for p in pres]
    old_ = getattr(self, "cmp_pick", None)
    try:
        if old_ is not None and old_.winfo_exists(): return old_.lift()          # one picker at a time
    except tk.TclError: pass
    w = self.cmp_pick = tk.Toplevel(self); w.title("Compare looks 🆚"); w.configure(bg=self.t["bg"]); w.transient(self)
    bx = ttk.Frame(w, padding=18); bx.pack(fill="both", expand=True)
    ttk.Label(bx, text="Pick three looks to compare", font=(A.FONT, 13, "bold"), foreground=self.t["accent"]).pack(anchor="w")
    sel_id = self.sel_preset.get(); others = [i + 1 for i, p in enumerate(pres) if p["id"] != sel_id]
    defaults = [0] + others[:2] if len(others) >= 2 else [0, 1, 2]
    vars_ = []
    for i in range(3):
        v = tk.StringVar(value=names[min(defaults[i] if i < len(defaults) else 0, len(names) - 1)]); vars_.append(v)
        self.combo(bx, v, names, 34).pack(anchor="w", pady=4)
    vod = bool(os.path.isfile(self.v["video"].get().strip().strip('"')))
    use = tk.BooleanVar(value=vod); c = ttk.Checkbutton(bx, text="Use my video (otherwise a cartoon scene)", variable=use); c.pack(anchor="w", pady=4)
    if not vod: c.state(["disabled"]); use.set(False)

    def go():
        picks = []
        for v in vars_:
            i = names.index(v.get()) if v.get() in names else 0
            picks.append((names[i], self.get_look() if i == 0 else pres[i - 1]["look"]))
        w.destroy(); self.compare_run(picks, bool(use.get()))
    bf = ttk.Frame(bx); bf.pack(anchor="w", pady=(10, 0))
    ttk.Button(bf, text="🆚 Compare", style="Accent.TButton", command=go).pack(side="left"); ttk.Button(bf, text="Cancel", command=w.destroy).pack(side="left", padx=8)
    A.center_over(w, self)


@method
def compare_run(self, picks, use_vod):
    sc = A.sc; opts, cam = self.opts_dict(), self.v["cam"].get() or None
    video = self.v["video"].get().strip().strip('"'); video = video if (use_vod and os.path.isfile(video)) else None
    extra = {k: x for k, x in opts.items() if k not in SKIP_PREVIEW}
    try:
        if extra.get("text_boxes"): extra["text_boxes"] = vcnew.texts_json([{**b, "say": False} for b in vcnew.parse_texts(extra["text_boxes"])])
    except Exception: pass
    stamp = int(time.time()); outs = [os.path.join(A.GIF_DIR, f"_cmp{stamp}_{i}.gif") for i in range(len(picks))]

    def fn():
        os.makedirs(A.GIF_DIR, exist_ok=True); sc.PLAN.clear()
        for f_ in glob.glob(os.path.join(A.GIF_DIR, "_cmp*.gif")):
            try: os.remove(f_)
            except OSError: pass
        words, t0, secs = None, 0.0, 6.0
        if video:
            dur = sc.probe(video)[0]; ws = None
            try:
                cp = sc.cache_path(video, opts["lang"], opts["translate"], opts["hint"])
                if cp.exists(): ws = sc.apply_fixes(sc.read_cached_words(cp, video)[0], opts["fixes"])
            except Exception: ws = None
            t0 = A.vv.best_window(ws, dur, secs); secs = min(secs, max(3.0, dur - t0))
            words = [w for w in ws if t0 <= w["start"] < t0 + secs] if ws else None
            if not words: words = None
        for i, (label, look) in enumerate(picks):
            print(f"Preview {i + 1}/{len(picks)}: {label}")
            A.vv.make_preview(outs[i], look, video=video, cam=cam, words=words, t0=t0, secs=secs, width=190, opts=extra)
        self.ui(lambda: self.compare_show(outs, picks))
    self.work(fn)


@method
def compare_show(self, outs, picks):
    w = self.cmp_win
    try:
        if w is not None and w.winfo_exists(): w.destroy()
    except tk.TclError: pass
    for p in getattr(self, "cmp_players", []): p.stop()
    self.cmp_players = []
    w = self.cmp_win = tk.Toplevel(self); w.title("Which look? 🆚"); w.configure(bg=self.t["bg"]); w.transient(self)
    row = ttk.Frame(w, padding=14); row.pack()
    for i, ((label, look), gif) in enumerate(zip(picks, outs)):
        col = ttk.Frame(row, padding=6); col.grid(row=0, column=i)
        lab = tk.Label(col, bd=0, bg=self.t["bg"]); lab.pack()
        if os.path.isfile(gif): self.cmp_players.append(A.GifPlayer(self, lab, gif))
        ttk.Label(col, text=label, font=(A.FONT, 10, "bold"), wraplength=190, justify="center").pack(pady=4)
        b = ttk.Button(col, text="Use this look", command=lambda lk=look, w=w: (self.sel_preset.set(""), self.apply_look(lk), self.update_pinfo(), self.draw_gallery(), self.refresh_eta(), self.save(), w.destroy()))
        b.pack()
        if i == 0 and label.startswith("★"): b.state(["disabled"])
    def close():
        for p in self.cmp_players: p.stop()
        w.destroy()
    ttk.Button(w, text="Close", command=close).pack(pady=(0, 12)); w.protocol("WM_DELETE_WINDOW", close)
    A.center_over(w, self)


# ================================================================ My clips: search, tags, review, remake, where from
@wraps("apply_theme")
def _w_theme(orig):
    def apply_theme(self):
        orig(self)
        try: _retheme(self)
        except Exception: log_err()
    return apply_theme


def _retheme(self):
    """Windows that are open while the theme changes (Tools, Review, Compare...) get the new colours too."""
    t = self.t
    for top in self.winfo_children():
        if not isinstance(top, tk.Toplevel): continue
        try: top.configure(bg=t["bg"])
        except tk.TclError: continue
        stack = list(top.winfo_children())
        while stack:
            w = stack.pop()
            try:
                stack.extend(w.winfo_children())
                if w.winfo_class() == "Text": w.configure(bg=t["entry"], fg=t["fg"], insertbackground=t["fg"])
            except tk.TclError: pass


@wraps("clips_extras")
def _w_clips_extras(orig):
    def clips_extras(self, hr):
        if orig: orig(self, hr)
        sr = ttk.Frame(hr.master); sr.pack(fill="x", pady=(0, 4), after=hr)
        ttk.Label(sr, text="🔍").pack(side="left")
        e = ttk.Entry(sr, textvariable=self.clip_q, width=30); e.pack(side="left", padx=6); self.tip(e, "Search by title, hashtag, kind of clip (reaction, story…), file name, posted-to or your own tags.")
        ttk.Button(sr, text="✖", width=3, command=lambda: self.clip_q.set("")).pack(side="left")
        self.tip(ttk.Button(sr, text="🗂 Review mode", command=self.open_review), "Go through your new clips one by one: keep, delete or skip. What you keep teaches me what you like.").pack(side="left", padx=(14, 0))
        self.tip(ttk.Button(sr, text="🗓 Plan new clips", command=self.plan_new_clips), "Put your newest unposted clips in the post planner at good times.").pack(side="left", padx=6)
        self.tip(ttk.Button(sr, text="📄 Post sheet", command=lambda: self.open_toolbox("sheet")), "Save a spreadsheet of your clips with titles and hashtags.").pack(side="left")
    return clips_extras


@method
def clip_q_changed(self):
    try:
        if self.q_job: self.after_cancel(self.q_job)
    except Exception: pass
    self.q_job = self.after(350, lambda: self.refresh_clips() if hasattr(self, "clip_grid") else None)


@wraps("clip_files_shown")
def _w_files_shown(orig):
    def clip_files_shown(self):
        files = orig(self); q = self.clip_q.get().strip()
        if not q: return files
        out = []
        for f in files:
            try:
                e = vcmore.ledger_find(f) or {}
                if vctools.clip_matches(q, f, tags=vctools.clip_tags(f), kind=str(e.get("kind", "")), posted=self.mark_text(f)): out.append(f)
            except Exception: pass
        return out
    return clip_files_shown


@wraps("mark_text")
def _w_mark_text(orig):
    def mark_text(self, f):
        t = orig(self, f)
        try:
            tags = vctools.clip_tags(f)
            if tags: t = (t + "   " if t else "") + "🏷 " + ", ".join(tags[:4])
        except Exception: pass
        return t
    return mark_text


@wraps("toggle_fav")
def _w_toggle_fav(orig):
    def toggle_fav(self, f):
        orig(self, f)
        try: vcmore.ledger_set(f, fav=bool(self.is_fav(f)))
        except Exception: pass
        self.taste_refresh()
    return toggle_fav


@wraps("mark_posted")
def _w_mark_posted(orig):
    def mark_posted(self, f, where):
        orig(self, f, where)
        try: vcmore.ledger_set(f, posted=True)
        except Exception: pass
        self.taste_refresh()
    return mark_posted


@wraps("clear_posted")
def _w_clear_posted(orig):
    def clear_posted(self, f):
        orig(self, f)
        try: vcmore.ledger_set(f, posted=False)
        except Exception: pass
    return clear_posted


@wraps("delete_clip")
def _w_delete_clip(orig):
    def delete_clip(self, f):
        orig(self, f)
        try:
            if not os.path.exists(f): vcmore.ledger_set(f, deleted=True)
        except Exception: pass
    return delete_clip


@wraps("card_menu_extras21")
def _w_card_menu(orig):
    def card_menu_extras21(self, mn, f, t):
        if orig: orig(self, mn, f, t)
        try:
            mn.add_separator()
            mn.add_command(label="🏷  Tags…", command=lambda f=f: self.edit_tags(f))
            mn.add_command(label="📍  Where is this from?", command=lambda f=f: self.where_from(f))
            mn.add_command(label="🔁  Make this moment again…", command=lambda f=f: self.remake_clip(f))
        except Exception: log_err()
    return card_menu_extras21


@method
def edit_tags(self, f):
    cur = ", ".join(vctools.clip_tags(f))
    s = simpledialog.askstring("Tags", "Your own tags for this clip (separate with commas).\nSearch finds them. Leave empty to remove.", initialvalue=cur, parent=self)
    if s is None: return
    vctools.set_clip_tags(f, s); self.refresh_clips()


@method
def where_from(self, f):
    e = vcmore.ledger_find(f); src = vctools.source_of(e)
    w = tk.Toplevel(self); w.title("Where is this from? 📍"); w.configure(bg=self.t["bg"]); w.transient(self)
    bx = ttk.Frame(w, padding=18); bx.pack(fill="both", expand=True)
    ttk.Label(bx, text=os.path.basename(f), font=(A.FONT, 11, "bold"), foreground=self.t["accent"], wraplength=520).pack(anchor="w")
    ttk.Label(bx, text=vctools.source_text(src), wraplength=520, justify="left").pack(anchor="w", pady=10)
    bf = ttk.Frame(bx); bf.pack(anchor="w")
    if src:
        def use():
            if src["vod_exists"]: self.batch = []; self.v["video"].set(src["vod"]); self.status.set("Loaded the source video ♡"); w.destroy()
        b = ttk.Button(bf, text="Use this video", command=use); b.pack(side="left")
        if not src["vod_exists"]: b.state(["disabled"])
        ttk.Button(bf, text="📋 Copy start time", command=lambda: (self.clipboard_clear(), self.clipboard_append(src["when"]), self.status.set(f"Copied {src['when']} ♡"))).pack(side="left", padx=8)
        if src["vod_exists"]: ttk.Button(bf, text="📂 Show the video", command=lambda: self.show_in_folder(src["vod"])).pack(side="left")
    ttk.Button(bf, text="Close", command=w.destroy).pack(side="left", padx=8)
    A.center_over(w, self)


@method
def remake_clip(self, f):
    if self.busy: return messagebox.showinfo("VTuber Clipper", "I'm busy right now~ try again when this finishes.")
    src = vctools.source_of(vcmore.ledger_find(f))
    if not src: return messagebox.showinfo("VTuber Clipper", vctools.source_text(None))
    if not src["vod_exists"]: return messagebox.showinfo("VTuber Clipper", vctools.source_text(src))
    if not messagebox.askyesno("Make this moment again", f"I cut the same moment ({src['when']}, about {src['end'] - src['start']:.0f} seconds) out of the video again, "
                                                          "with the look and settings that are on screen now. The old clip stays. Go?"): return
    self.batch = []; self.v["video"].set(src["vod"])
    self.run_shorts(windows=[(src["start"], src["end"])])


@method
def open_review(self):
    w = self.review_win
    try:
        if w is not None and w.winfo_exists(): return w.lift()
    except tk.TclError: pass
    todo = []
    for f in self.clip_files()[:120]:
        e = vcmore.ledger_find(f) or {}
        if self.is_fav(f) or self.marks["posted"].get(os.path.normpath(f)) or e.get("reviewed") or f.lower().endswith(("_1x1.mp4", "_16x9.mp4")): continue
        todo.append(f)
    if not todo: return messagebox.showinfo("VTuber Clipper", "No new clips to go through - everything recent is starred, posted or already reviewed ♡")
    st = dict(i=0, asked=False, kept=0, dropped=0, img=None)
    w = self.review_win = tk.Toplevel(self); w.title("Review mode 🗂"); w.configure(bg=self.t["bg"]); w.transient(self)
    bx = ttk.Frame(w, padding=18); bx.pack(fill="both", expand=True)
    head = tk.StringVar(); ttk.Label(bx, textvariable=head, font=(A.FONT, 12, "bold"), foreground=self.t["accent"]).pack(anchor="w")
    pic = tk.Label(bx, bd=0, bg=self.t["entry"], width=40, height=12); pic.pack(pady=8)
    info = tk.StringVar(); ttk.Label(bx, textvariable=info, wraplength=480, justify="left").pack(anchor="w")
    bf = ttk.Frame(bx); bf.pack(pady=12)
    btns = {}

    def show():
        if st["i"] >= len(todo):
            head.set(f"All done ✿  kept {st['kept']}, deleted {st['dropped']}"); info.set("What you kept teaches me what you like (Smart finding → Learn from the clips I keep).")
            pic.configure(image="", text=""); [b.state(["disabled"]) for b in btns.values()]; self.taste_refresh(); self.refresh_clips(); return
        f = todo[st["i"]]; k = vctools.read_kit(f); e = vcmore.ledger_find(f) or {}
        head.set(f"Clip {st['i'] + 1} of {len(todo)}")
        bits = [os.path.basename(f)]
        if k["title"]: bits.append("“" + k["title"] + "”")
        meta = " · ".join(x for x in (e.get("kind", ""), f"{e['dur']:.0f}s" if e.get("dur") else "", f"hype {k['hype']}" if k["hype"] is not None else "") if x)
        if meta: bits.append(meta)
        info.set("\n".join(bits)); pic.configure(image="", text="…")
        threading.Thread(target=thumb, args=(f, st["i"]), daemon=True).start()

    def thumb(f, idx):
        try:
            d = os.path.join(A.sc.CACHE_DIR, "thumbs"); os.makedirs(d, exist_ok=True)
            th = os.path.join(d, "r_" + re.sub(r"\W", "_", os.path.basename(f))[:60] + f"_{int(os.path.getmtime(f))}.png")
            if not os.path.exists(th): subprocess.run([A.sc.FF, "-y", "-v", "error", "-ss", "1.0", "-i", f, "-frames:v", "1", "-vf", "scale=-2:300", th], timeout=30, **A.sc.NOWIN)
            self.ui(lambda: put(th, idx))
        except Exception: pass

    def put(th, idx):
        if idx != st["i"]: return
        try: st["img"] = tk.PhotoImage(file=th); pic.configure(image=st["img"], text="")
        except Exception: pass

    def cur(): return todo[st["i"]] if st["i"] < len(todo) else None

    def play():
        if cur(): A.open_path(cur())

    def keep():
        f = cur()
        if not f: return
        n_ = os.path.normpath(f)
        if n_ not in self.marks["fav"]: self.marks["fav"].append(n_)
        vcmore.ledger_set(f, fav=True, reviewed=True); st["kept"] += 1; st["i"] += 1; self.save(); show()

    def drop():
        f = cur()
        if not f: return
        if not st["asked"]:
            if not messagebox.askyesno("Review mode", "Delete this clip and everything made with it?\n\nI only ask this once - after that, 👎 deletes right away.", parent=w): return
            st["asked"] = True
        import vcouts
        vcmore.ledger_set(f, deleted=True, reviewed=True); vcouts.delete_clip_files(f)
        n_ = os.path.normpath(f)
        if n_ in self.marks["fav"]: self.marks["fav"].remove(n_)
        self.marks["posted"].pop(n_, None); st["dropped"] += 1; st["i"] += 1; self.save(); show()

    def skip():
        if cur(): st["i"] += 1; show()
    for key, text, fn, style in (("play", "▶ Play", play, "TButton"), ("keep", "👍 Keep (star it)", keep, "Accent.TButton"), ("drop", "👎 Delete", drop, "TButton"), ("skip", "⏭ Later", skip, "TButton")):
        b = ttk.Button(bf, text=text, command=fn, style=style); b.pack(side="left", padx=5); btns[key] = b
    ttk.Label(bx, text="Keys:  K keep   D delete   S later   Space play", style="Mute.TLabel").pack()
    for ch, fn in (("k", keep), ("d", drop), ("s", skip), ("space", play)): w.bind(f"<{ch}>", lambda e, fn=fn: fn())
    w.bind("<Escape>", lambda e: w.destroy())
    A.center_over(w, self); w.focus_set(); show()


# ================================================================ Best moments: save / open a list
@method
def moments_extras(self, mb):
    b1 = ttk.Button(mb, text="💾 Save list…", command=self.moments_to_file); b1.pack(side="left", padx=(10, 0))
    self.tip(b1, "Saves the list (with the video it belongs to) so you can open it another day.")
    self.mbtns.append(b1)
    b2 = ttk.Button(mb, text="📂 Open list…", command=self.moments_from_file); b2.pack(side="left", padx=6)
    self.tip(b2, "Opens a list you saved before.")


@method
def moments_to_file(self):
    if not self.moments: return
    base = os.path.splitext(os.path.basename(getattr(self, "mom_video", "") or "moments"))[0][:50] or "moments"
    p = filedialog.asksaveasfilename(parent=self, title="Save my moments list", defaultextension=".vtmoments", initialfile=base + ".vtmoments", filetypes=[("Moments list", "*.vtmoments"), ("All files", "*.*")])
    if not p: return
    n = vctools.moments_save(p, getattr(self, "mom_video", ""), self.moments)
    self.mnote.set(f"Saved {n} moments to {os.path.basename(p)} ♡" if n else "I couldn't save that file.")


@method
def moments_from_file(self):
    p = filedialog.askopenfilename(parent=self, title="Open a moments list", filetypes=[("Moments list", "*.vtmoments"), ("All files", "*.*")])
    if not p: return
    video, ms = vctools.moments_load(p)
    if not ms: return messagebox.showinfo("VTuber Clipper", "I couldn't find any moments in that file.")
    cur = self.v["video"].get().strip().strip('"')
    if video and os.path.isfile(video) and os.path.abspath(video) != os.path.abspath(cur or "-"):
        self.batch = []; self.v["video"].set(video); cur = video
    elif video and not os.path.isfile(video):
        messagebox.showinfo("VTuber Clipper", f"This list was made for “{os.path.basename(video)}”, which isn't on this PC. I'm showing it for the video that is selected now - the times may not fit.")
    if not os.path.isfile(cur): return messagebox.showinfo("VTuber Clipper", "Pick the video this list belongs to first (on the left) ♡")
    self.show_moments(ms, "", cur)
    self.mnote.set(f"Opened {len(ms)} moments from {os.path.basename(p)} ♡  Select some and press ‘Make Shorts from selected’.")
