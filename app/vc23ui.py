"""VTuber Clipper 2.3 - the new screens of the app window:
the Privacy & checks tab, the extra rows in the Smart finding / Picture & voice / Captions / Logo & music / Posting & files tabs, nine new pages in the Tools window
(privacy scan, clip check, duplicates, bulk rename, snapshots, reports, chapters, game memory, updates), the download options in Settings, the update buttons in Settings -> About,
and the pieces that make "remember per game" and "auto snapshot" work.

streamclip_app.py calls install(App, module) once; every function below becomes a method of the App window.
The work itself lives in vc23.py (options), vcclues / vcmedia / vcsafe / vcshare / vcnet / vcpipe (finding, files, checks, sharing, downloads and updates); there are no screens in those."""
import os, re, tempfile, threading, time, traceback
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import vc22ui, vc23, vcmore, vcnet, vcouts, vcsafe, vcshare, vctools

A = None                    # the app module (streamclip_app), set by install()
METHODS, WRAPS = {}, {}
GOOD, WARN, BAD = vc22ui.GOOD, vc22ui.WARN, vc22ui.BAD

SMART23 = ("chat_cmds", "clue_milestone", "clue_chat", "clue_bilingual", "clue_fast", "clue_repeat", "clue_buildup", "lead_trim", "tail_trim", "spread", "skip_dead")
POLISH23 = ("bg_blur", "bg_dim", "gate", "deess", "bar_pos", "bar_thick")
CAP23 = ("cap_feel",)
EXTRAS23 = ("logo_alpha", "music_mood")
POST23 = ("soft_subs", "meta_tags", "scrub_meta", "audio_copy", "gif_clip", "cover_alts", "cover_sharp", "report_html", "stamps_file", "platform_texts", "alt_text",
          "community_msg", "day_folder", "maybe_folder", "maybe_below", "game_memory")
SAFE23 = ("privacy", "flash_check", "preflight", "disk_guard")                   # "Reset this tab" keeps the private words: they are yours, not a setting
SNAP_SKIP = ("private_words", "chat_file", "range_from", "range_to")             # a snapshot never stores or brings back these
DL_KEYS = ("dl_rate", "dl_frags", "dl_cookie_file")                              # kept between runs; dl_from / dl_to are for the next download only
TAB_HELP23 = {"safe": "The privacy guard, the words you never want in a clip, and the checks that run on every finished clip.",
              "smart": "How I find the best moments: I tell laughs, screams, singing, stories and gameplay apart, listen for more clues, skip greetings and dead air, vary the picks and can learn from the clips you keep."}


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
    module.OPT_STR = tuple(module.OPT_STR) + tuple(k for k in vc23.STR_KEYS if k not in module.OPT_STR)
    module.OPT_BOOL = tuple(module.OPT_BOOL) + tuple(k for k in vc23.BOOL_KEYS if k not in module.OPT_BOOL)
    import vc20ui, vc21ui
    r = vc20ui.RESET
    r["smart"]["o"] = tuple(r["smart"]["o"]) + SMART23
    r["polish"]["o"] = tuple(r["polish"]["o"]) + POLISH23
    r["captions"]["o"] = tuple(r["captions"]["o"]) + CAP23
    r["extras"]["o"] = tuple(r["extras"]["o"]) + EXTRAS23
    r["post"]["o"] = tuple(r["post"]["o"]) + POST23
    r["safe"] = dict(o=SAFE23, v={})
    vc21ui.TAB_HELP.update(TAB_HELP23)
    vc22ui.TOOL_GROUPS.extend([
        ("clips", "🎬 Clips", [("check", "✅ Clip check", _tp_check), ("dupes", "👯 Duplicates", _tp_dupes), ("rename", "✏ Rename", _tp_rename),
                               ("report", "📑 Reports", _tp_report), ("chapters", "🔖 Chapters", _tp_chapters)]),
        ("safety", "🛡 Safety & updates", [("privacy", "🔒 Privacy", _tp_privacy), ("snaps", "📸 Snapshots", _tp_snaps), ("games", "🎮 Games", _tp_games), ("updates", "🔄 Updates", _tp_updates)])])


def log_err(): A.log_error(traceback.format_exc())


def _flat(d, prefix=""):
    out = {}
    for k, v in (d or {}).items():
        if isinstance(v, dict): out.update(_flat(v, f"{prefix}{k}."))
        else: out[f"{prefix}{k}"] = v
    return out


# ================================================================ set-up / saving
@method
def init23(self, cfg):
    """Called from __init__: the state the 2.3 features keep."""
    c = cfg.get("v23") if isinstance(cfg.get("v23"), dict) else {}
    self.dl = {k: tk.StringVar(value=str(c.get(k, d) or d)[:400]) for k, d in (("dl_rate", ""), ("dl_frags", "4"), ("dl_cookie_file", ""))}
    self.dl["dl_from"], self.dl["dl_to"] = tk.StringVar(), tk.StringVar()
    self.dl_note, self.upd_note = tk.StringVar(), tk.StringVar()
    self.upd_last = str(c.get("upd_last", ""))[:10]
    self.upd_info, self.upd_busy, self.game_job = None, False, None
    self.pw_text = None


@method
def cfg23(self):
    d = {k: self.dl[k].get().strip() for k in DL_KEYS}
    d["upd_last"] = self.upd_last
    return dict(v23=d)


@method
def start23(self):
    """Called once the window is built."""
    try:
        for k in self.dl: self.dl[k].trace_add("write", lambda *a: (self.dl_refresh(), self.save()))
        self.dl_refresh()
        self.o["game"].trace_add("write", lambda *a: self.game_changed())
        self.o["private_words"].trace_add("write", lambda *a: self.pw_pull())
        self.o["update_check"].trace_add("write", lambda *a: self.save())
        if not os.environ.get("VTC_TEST") and self.o["update_check"].get(): self.after(9000, self.upd_auto)
    except Exception: log_err()


@wraps("hook22")
def _w_hook(orig):
    def hook22(self, what, *a):
        orig(self, what, *a)
        try:
            if what == "start" and a and a[0] in A.RENDER_JOBS: self.snap_auto()
        except Exception: log_err()
    return hook22


@wraps("apply_theme")
def _w_theme(orig):
    def apply_theme(self):
        orig(self)
        try:
            w = getattr(self, "pw_text", None)
            if w is not None and w.winfo_exists(): w.configure(bg=self.t["entry"], fg=self.t["fg"], insertbackground=self.t["fg"])
        except Exception: log_err()
    return apply_theme


# ================================================================ rows in the existing tabs
def _box(self, tab, title): return vc22ui._box(self, tab, title)


def _check(self, g, row, key, text, tip): return vc22ui._check(self, g, row, key, text, tip)


def _row(self, g, row, label, widget, tip):
    ttk.Label(g, text=label).grid(row=row, column=0, sticky="w", pady=3); widget.grid(row=row, column=1, sticky="w", padx=8); self.tip(widget, tip)


@method
def build23_rows(self):
    """Called once, after every tab is built: adds the 2.3 rows at the bottom of the tabs they belong to."""
    o, subs = self.o, self.subs
    g = _box(self, subs["smart"], "🔎 More clues I listen for")
    for i, (k, t, tp) in enumerate((
            ("chat_cmds", "💬 !clip and !highlight in the chat log mark a moment", "If you saved the chat log, every time viewers typed !clip, !highlight or !hype near a moment, I look at that moment first."),
            ("clue_milestone", "🏁 Firsts and milestones (first win, level up, new record)", "Words like “first time”, “finally”, “new record” and “level up” make a moment count for more."),
            ("clue_chat", "🗨 Moments where she reads or answers chat", "“Chat says…”, “someone asked…” - talking with chat is often a good clip."),
            ("clue_bilingual", "🌐 Switching between two languages in one sentence", "A sentence that jumps between English and Japanese (or another language) is usually a fun moment."),
            ("clue_fast", "⚡ Rapid, excited talking", "Lots of words in a very short time is a sign of excitement."),
            ("clue_repeat", "🔁 Panic repeats (“no no no no”)", "The same word said again and again in a row."),
            ("clue_buildup", "📈 Build-up to a peak (quiet, louder, burst)", "A moment that grows into a scream or a laugh makes a better clip than a sudden noise."))):
        _check(self, g, i, k, t, tp)
    g = _box(self, subs["smart"], "✂ Where a clip starts and ends")
    for i, (k, t, tp) in enumerate((
            ("lead_trim", "▶ Open on the action: cut quiet seconds at the start", "Starts the clip on the first real words instead of a few seconds of nothing."),
            ("tail_trim", "⏹ Clean ending: cut quiet seconds after the last word", "Ends the clip right after the last word."),
            ("spread", "🗺 Spread the clips over the whole stream", "Stops all clips coming from one hot minute. The best moment of each part of the stream gets a chance."),
            ("skip_dead", "💤 Skip BRB, intermission and goodbye parts", "Parts where she says she is stepping away, or is saying goodbye, are not used."))):
        _check(self, g, i, k, t, tp)

    g = _box(self, subs["polish"], "🌫 Background behind the game")
    _row(self, g, 0, "Blur", self.pick(g, o["bg_blur"], {k: v[0] for k, v in vc23.BG_BLURS.items()}, 16), "How blurry the copy of the game behind your clip is.")
    _row(self, g, 1, "Brightness", self.spin(g, o["bg_dim"], -50, 50, 5, 5), "0 = as it is. Below 0 is darker (makes the game stand out), above 0 is lighter.")
    g = _box(self, subs["polish"], "🎙 Voice clean-up")
    _check(self, g, 0, "gate", "🔇 Noise gate (keyboard and mouse clicks between words)", "Quiets the sound between words. Switch it off if your voice sounds chopped.")
    _check(self, g, 1, "deess", "🐍 De-esser (soften harsh S sounds)", "Makes sharp “sss” sounds gentler.")
    g = _box(self, subs["polish"], "▬ Progress bar")
    _row(self, g, 0, "Edge", self.pick(g, o["bar_pos"], vc23.BAR_POS, 16), "Which edge of the picture the progress bar sits on.")
    _row(self, g, 1, "Thickness", self.spin(g, o["bar_thick"], 4, 40, 2, 5), "In pixels of the 1080 tall picture.")

    _check(self, _box(self, subs["captions"], "🎨 Feeling colours"), 0, "cap_feel", "Colour the feeling words (yay, scary, hype…)", "Words that show a feeling get their own colour in the captions.")

    g = _box(self, subs["extras"], "🧷 Logo see-through")
    _row(self, g, 0, "Logo opacity", self.spin(g, o["logo_alpha"], 20, 100, 5, 5), "100 = solid. Lower values let the picture show through.")
    g = _box(self, subs["extras"], "🎵 Music by mood")
    _check(self, g, 0, "music_mood", "Pick the song by the kind of moment", "Put songs in sub-folders called hype, funny, chill, sad, spooky or cute inside your music folder. A funny moment gets a song from funny.")

    g = _box(self, subs["post"], "🎞 More in each clip file")
    for i, (k, t, tp) in enumerate((
            ("soft_subs", "💬 Subtitles that can be switched on and off inside the mp4", "Viewers and uploaders can turn them on. (The burned-in captions stay as they are.)"),
            ("meta_tags", "🏷 Title, channel and game in the file's info", "Written into the file, so it is labelled when you upload it."),
            ("scrub_meta", "🧽 Remove hidden info from the file", "Takes out information such as the program that made it."),
            ("audio_copy", "🎧 Also save the sound as an MP3", "A sound-only copy next to the clip."),
            ("gif_clip", "🖼 Also make a GIF of the best second", "A short looping GIF for chats and social posts."),
            ("cover_alts", "🌄 Make three cover choices", "Three different cover pictures per clip so you can pick one."),
            ("cover_sharp", "🔍 Choose the sharpest frame for covers", "Skips blurry frames when picking a cover."))):
        _check(self, g, i, k, t, tp)
    g = _box(self, subs["post"], "📝 Texts and pages")
    for i, (k, t, tp) in enumerate((
            ("platform_texts", "📱 Post texts for each app, within its limits", "TikTok, YouTube Shorts, Instagram and X each get a text of the right length. (Limits are as far as I know; apps change them.)"),
            ("alt_text", "♿ Alt-text file for each clip", "A short description of the clip for people who cannot see it."),
            ("community_msg", "📣 Community message draft", "A ready message listing the best clips of a run, for Discord or an X thread."),
            ("report_html", "📑 Highlights page (HTML) after a run", "One web page with every clip, its time in the VOD and why it was picked."),
            ("stamps_file", "🕒 VOD timestamps for the description", "A list of times for the long video's description (YouTube turns it into chapters)."))):
        _check(self, g, i, k, t, tp)
    g = _box(self, subs["post"], "🗂 Folders and memory")
    _check(self, g, 0, "day_folder", "📅 A folder for each day", "Clips go into a folder named after today's date.")
    _check(self, g, 1, "maybe_folder", "🤔 Put weaker clips in a “Maybe” folder", "Clips under the hype score below go to a Maybe folder instead, so the good ones stand out.")
    _row(self, g, 2, "Maybe if hype is under", self.spin(g, o["maybe_below"], 0, 100, 5, 5), "0 = never. A clip with a lower hype score goes to the Maybe folder.")
    _check(self, g, 3, "game_memory", "🎮 Remember the number, length and style for each game", "When you name a game, I fill in the settings you used last time for it. See Tools -> Games.")
    bf = ttk.Frame(g); bf.grid(row=4, column=0, columnspan=3, sticky="w", pady=(6, 0))
    ttk.Button(bf, text="📑 Reports…", command=lambda: self.open_toolbox("report")).pack(side="left")
    ttk.Button(bf, text="✏ Rename clips…", command=lambda: self.open_toolbox("rename")).pack(side="left", padx=8)
    ttk.Button(bf, text="👯 Find duplicates…", command=lambda: self.open_toolbox("dupes")).pack(side="left")


# ================================================================ the Privacy & checks tab
@method
def build_safe(self, x):
    o = self.o; x.columnconfigure(0, weight=1); r = [-1]

    def head(t): r[0] += 1; self.head(x, t, r[0])

    def note(t, **kw):
        r[0] += 1; ttk.Label(x, text=t, style="Mute.TLabel", wraplength=660, justify="left", **kw).grid(row=r[0], column=0, sticky="w", pady=(0, 2))

    head("🔒 Privacy guard")
    note("I look at the words of every clip for things you would not want online: e-mail addresses, phone numbers, street addresses, links, and slips like “my real name is…”. "
         "It is a pattern check on the speech-to-text, so it can miss things (and it can only read English phrases) - always give a clip a quick listen.")
    r[0] += 1; mf = ttk.Frame(x); mf.grid(row=r[0], column=0, sticky="w", pady=4)
    ttk.Label(mf, text="When I find something").pack(side="left")
    w = self.pick(mf, o["privacy"], vc23.PRIVACY, 34); w.pack(side="left", padx=8)
    self.tip(w, "Off = no check. Warn = I list what I found in the clip's check file, and bleep only your private words. Bleep = I also bleep and star everything I found.")
    head("🙈 My private words")
    note("Words that must never be heard or read in a clip: your real name, your town, school, street, your pet's full name… One per line, or separated by commas. "
         "They are bleeped in the sound, starred in the captions and kept out of titles, hashtags and file names. They stay on this PC and are never put into a shared look code.")
    r[0] += 1; tf = ttk.Frame(x); tf.grid(row=r[0], column=0, sticky="we"); tf.columnconfigure(0, weight=1)
    self.pw_text = tk.Text(tf, height=5, wrap="word", relief="flat", padx=8, pady=6, font=(A.FONT, 10), bg=self.t["entry"], fg=self.t["fg"], insertbackground=self.t["fg"])
    self.pw_text.grid(row=0, column=0, sticky="we")
    self.pw_text.insert("1.0", o["private_words"].get())
    for ev in ("<KeyRelease>", "<FocusOut>"): self.pw_text.bind(ev, lambda e: self.pw_push(), add="+")
    self.pw_text.bind("<MouseWheel>", lambda e: (self.on_wheel(e), "break")[1])
    r[0] += 1; ttk.Label(x, textvariable=self.pw_note_var(), style="Mute.TLabel").grid(row=r[0], column=0, sticky="w")
    r[0] += 1; bf = ttk.Frame(x); bf.grid(row=r[0], column=0, sticky="w", pady=(2, 0))
    ttk.Button(bf, text="🔍 Scan a transcript…", command=lambda: self.open_toolbox("privacy")).pack(side="left")

    head("✅ Checks on every finished clip")
    for k, t, tp in (("preflight", "✅ Check each clip before I post it (length, shape, loudness, silent or black start)", "Writes a short _check.txt next to a clip when something is worth a look."),
                     ("flash_check", "⚡ Flash safety check (fast flashing can harm some viewers)", "Looks at the finished picture for flashing faster than three times a second. It is a guide, not a medical test."),
                     ("disk_guard", "💾 Stop before a run if the drive is too full", "Stops early with a clear message instead of failing half way through.")):
        r[0] += 1; c = ttk.Checkbutton(x, text=t, variable=o[k]); c.grid(row=r[0], column=0, sticky="w", pady=2); self.tip(c, tp)
    r[0] += 1; bf = ttk.Frame(x); bf.grid(row=r[0], column=0, sticky="w", pady=(6, 0))
    ttk.Button(bf, text="✅ Check a clip now…", command=lambda: self.open_toolbox("check")).pack(side="left")
    ttk.Button(bf, text="📸 Settings snapshots…", command=lambda: self.open_toolbox("snaps")).pack(side="left", padx=8)


@method
def pw_note_var(self):
    if not hasattr(self, "pw_note"): self.pw_note = tk.StringVar()
    self.pw_count_refresh(); return self.pw_note


@method
def pw_count_refresh(self):
    n = len(vc23.split_words(self.o["private_words"].get()))
    self.pw_note.set(f"{n} private word{'s' if n != 1 else ''} saved" if n else "No private words yet.")


@method
def pw_push(self):
    """The text box changed: keep the option in step."""
    try:
        t = self.pw_text.get("1.0", "end").strip()
        if t != self.o["private_words"].get().strip(): self.o["private_words"].set(t)
        self.pw_count_refresh()
    except (tk.TclError, AttributeError): pass


@method
def pw_pull(self):
    """The option changed from somewhere else (reset, a snapshot, a profile): show it in the text box."""
    try:
        w = self.pw_text
        if w is None or not w.winfo_exists(): return
        cur = w.get("1.0", "end").strip()
        if cur != self.o["private_words"].get().strip(): w.delete("1.0", "end"); w.insert("1.0", self.o["private_words"].get())
        self.pw_count_refresh()
    except (tk.TclError, AttributeError): pass


# ================================================================ small widget helpers for the Tools pages
def _textbox(self, f, height=12, pady=(8, 0)):
    tf = ttk.Frame(f); tf.pack(fill="both", expand=True, pady=pady)
    t = tk.Text(tf, height=height, wrap="word", relief="flat", padx=10, pady=8, font=(A.FONT, 10), bg=self.t["entry"], fg=self.t["fg"], insertbackground=self.t["fg"])
    sb = ttk.Scrollbar(tf, orient="vertical", command=t.yview); t.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y"); t.pack(side="left", fill="both", expand=True)
    for k, col in (("ok", GOOD), ("warn", WARN), ("bad", BAD)): t.tag_configure(k, foreground=col, font=(A.FONT, 10, "bold"))
    t.tag_configure("h", font=(A.FONT, 10, "bold"), foreground=self.t["accent"]); t.tag_configure("d", foreground=self.t["mute"])
    t.configure(state="disabled"); return t


def _put(t, parts):
    """Fill a read-only text box with [(text, tag), ...]."""
    try:
        t.configure(state="normal"); t.delete("1.0", "end")
        for s, tag in parts: t.insert("end", s, tag or ())
        t.configure(state="disabled")
    except tk.TclError: pass


def _listbox(self, f, height=10, mode="extended"):
    lf = ttk.Frame(f); lf.pack(fill="both", expand=True, pady=(6, 0))
    lb = tk.Listbox(lf, selectmode=mode, height=height, exportselection=False, relief="flat", font=(A.FONT, 10), bg=self.t["entry"], fg=self.t["fg"],
                    selectbackground=self.t["accent"], selectforeground=self.t["on"], activestyle="none")
    sb = ttk.Scrollbar(lf, orient="vertical", command=lb.yview); lb.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y"); lb.pack(side="left", fill="both", expand=True); return lb


def _file_row(self, f, var, kinds, title, extra=None):
    r = ttk.Frame(f); r.pack(fill="x", pady=(0, 4)); r.columnconfigure(0, weight=1)
    ttk.Entry(r, textvariable=var).grid(row=0, column=0, sticky="we")
    ttk.Button(r, text="Browse", command=lambda: var.set(filedialog.askopenfilename(parent=self.tools_win, title=title, filetypes=kinds) or var.get())).grid(row=0, column=1, padx=6)
    if extra: ttk.Button(r, text=extra[0], command=extra[1]).grid(row=0, column=2)
    return r


def _clips_now(self, limit=40):
    """The clips of My clips, newest first, without the square / landscape copies."""
    try: fs = [f for f in self.clip_files() if not f.lower().endswith(("_1x1.mp4", "_16x9.mp4", "_4x5.mp4"))]
    except Exception: fs = []
    return fs[:limit] if limit else fs


def _say(self, text):
    try: self.status.set(text)
    except Exception: pass


# ================================================================ Tools: privacy scan
def _tp_privacy(self, f):
    vc22ui._intro(self, f, "Reads a transcript or subtitle file (.srt, .vtt, or a text file with lines like [1:02:30] words) and lists everything that looks private, with the time it was said. "
                           "It is a pattern check: it cannot hear what the speech-to-text got wrong, so listen to the clip too.")
    self.pv_file, self.pv_try = tk.StringVar(), tk.StringVar()
    _file_row(self, f, self.pv_file, [("Transcripts and subtitles", "*.srt *.vtt *.txt"), ("All files", "*.*")], "Choose a transcript or subtitles", ("Newest clip's subtitles", self.pv_newest))
    bar = ttk.Frame(f); bar.pack(fill="x")
    ttk.Button(bar, text="🔍 Scan", style="Accent.TButton", command=self.pv_scan).pack(side="left")
    ttk.Button(bar, text="🙈 My private words…", command=self.pv_words).pack(side="left", padx=8)
    self.pv_out = _textbox(self, f, 9)
    _put(self.pv_out, [("Choose a file and press Scan.", "d")])
    ttk.Label(f, text="Try a sentence", font=(A.FONT, 10, "bold"), foreground=self.t["accent"]).pack(anchor="w", pady=(10, 2))
    r = ttk.Frame(f); r.pack(fill="x"); r.columnconfigure(0, weight=1)
    e = ttk.Entry(r, textvariable=self.pv_try); e.grid(row=0, column=0, sticky="we"); e.bind("<Return>", lambda ev: self.pv_test())
    ttk.Button(r, text="Check", command=self.pv_test).grid(row=0, column=1, padx=6)
    self.pv_res = tk.StringVar(value="Type a sentence, like  my email is mia at example dot com  - and see what would be starred.")
    ttk.Label(f, textvariable=self.pv_res, style="Mute.TLabel", wraplength=700, justify="left").pack(anchor="w", pady=(4, 0))


@method
def pv_newest(self):
    for c in _clips_now(self, 12):
        s = os.path.splitext(c)[0] + ".srt"
        if os.path.isfile(s): self.pv_file.set(s); return
    _say(self, "None of your newest clips has a subtitle file (turn on “Save subtitles” in Posting & files).")


@method
def pv_words(self):
    self.mode.set("shorts"); self.sub.set("safe"); self.focus_force()
    try: self.after(150, lambda: self.pw_text.focus_set())
    except Exception: pass


@method
def pv_scan(self):
    p = self.pv_file.get().strip().strip('"')
    if not os.path.isfile(p): return _put(self.pv_out, [("I can't find that file. Choose a .srt, .vtt or .txt file first.", "warn")])
    try:
        with open(p, encoding="utf-8", errors="replace") as fh: txt = fh.read(6_000_000)
    except OSError: return _put(self.pv_out, [("I couldn't read that file.", "bad")])
    words = vcsafe.words_from_text(txt)
    if not words: return _put(self.pv_out, [("I found no timed words in that file. A subtitle file (.srt / .vtt) or a text file with lines like [1:02:30] words works.", "warn")])
    rep = vcsafe.scan_report(words, self.opts_dict())
    parts = [(vcsafe.report_text(rep, os.path.basename(p)) + "\n", "bad" if rep else "ok")]
    if rep: parts.append(("\nPrivacy guard setting: " + vc23.PRIVACY.get(self.o["privacy"].get(), "") + ".", "d"))
    _put(self.pv_out, parts)


@method
def pv_test(self):
    s = self.pv_try.get().strip()
    if not s: return
    o = self.opts_dict()
    if o.get("privacy") == "off": o["privacy"] = "warn"
    out = vcsafe.scrub_text(s, o)
    self.pv_res.set(("Nothing private found: " if out == s else "Would become: ") + out)


# ================================================================ Tools: clip check
def _tp_check(self, f):
    vc22ui._intro(self, f, "Looks at a finished clip: is it the right length for the app, a tall picture, loud enough (but not too loud), does it start with sound and a picture, and does it flash too fast. "
                           "Nothing is changed. The loudness target is the one in Logo & music.")
    self.ck_path, self.ck_busy = tk.StringVar(), False
    _file_row(self, f, self.ck_path, [("Videos", "*.mp4 *.mov *.mkv *.webm"), ("All files", "*.*")], "Choose a clip", ("Newest clip", self.ck_newest))
    bar = ttk.Frame(f); bar.pack(fill="x")
    ttk.Button(bar, text="✅ Check this clip", style="Accent.TButton", command=lambda: self.ck_run([self.ck_path.get().strip().strip('"')])).pack(side="left")
    ttk.Button(bar, text="Check the 5 newest", command=lambda: self.ck_run(_clips_now(self, 5))).pack(side="left", padx=8)
    self.ck_out = _textbox(self, f, 16)
    _put(self.ck_out, [("Choose a clip and press Check.", "d")])


@method
def ck_newest(self):
    c = _clips_now(self, 1)
    if c: self.ck_path.set(c[0])
    else: _say(self, "You have no clips yet ♡")


@method
def ck_run(self, paths):
    paths = [p for p in paths if p]
    if not paths: return _put(self.ck_out, [("Choose a clip first.", "warn")])
    if self.ck_busy: return
    self.ck_busy = True; _put(self.ck_out, [("Checking… (loudness and flashing take a few seconds per clip)", "d")])
    opts, ff, nowin = self.opts_dict(), A.sc.FF, A.sc.NOWIN                     # window values are read here, not in the worker thread

    def go():
        res = []
        for p in paths:
            try: res.append((p, vcsafe.clip_check(p, ff, nowin, opts)))
            except Exception: res.append((p, [dict(level="bad", text="The check itself failed for this file.")]))
        self.ui(lambda: self.ck_show(res))
    threading.Thread(target=go, daemon=True).start()


@method
def ck_show(self, res):
    self.ck_busy = False
    parts = []
    for p, items in res:
        parts.append((os.path.basename(p) + "\n", "h"))
        for i in items: parts.append(({"ok": "✔  ", "warn": "!  ", "bad": "✖  "}.get(i["level"], "?  "), i["level"])); parts.append((i["text"] + "\n", ""))
        parts.append(("\n", ""))
    _put(self.ck_out, parts or [("Nothing to show.", "d")])


# ================================================================ Tools: duplicates
def _tp_dupes(self, f):
    vc22ui._intro(self, f, "Finds clips that were cut from (nearly) the same moment of the same video, for example after you ran Shorts twice with different looks. The one with the highest hype score is kept; "
                           "the others can be moved out of the way into a “Duplicates” folder (nothing is deleted).")
    bar = ttk.Frame(f); bar.pack(fill="x"); self.dp_sum, self.dp_rows = tk.StringVar(), []
    ttk.Button(bar, text="🔍 Look for duplicates", style="Accent.TButton", command=self.dp_run).pack(side="left")
    ttk.Button(bar, text="↪ Move the selected to Duplicates", command=self.dp_move).pack(side="left", padx=8)
    ttk.Label(f, textvariable=self.dp_sum, style="Mute.TLabel").pack(anchor="w", pady=6)
    self.dp_list = _listbox(self, f, 12)


@method
def dp_run(self, note=""):
    ents = [e for e in vcmore.ledger_all() if os.path.isfile(str(e.get("path", ""))) and os.path.basename(os.path.dirname(str(e["path"]))).lower() != "duplicates"]
    groups = vcshare.find_duplicates(ents)
    lb = self.dp_list; lb.delete(0, "end"); self.dp_rows = []; weaker = []
    for n, grp in enumerate(groups, 1):
        lb.insert("end", f"Same moment #{n}  -  {os.path.basename(str(grp[0].get('vod', '')))[:50]}"); self.dp_rows.append(None)
        for k, e in enumerate(grp):
            tag = "keep    " if k == 0 else "weaker  "
            lb.insert("end", f"     {tag}{os.path.basename(e['path'])}   hype {e.get('hype', '-')}   {vcshare.hms(e.get('start', 0))}"); self.dp_rows.append(e["path"] if k else None)
            if k: weaker.append(lb.size() - 1)
    for i in weaker: lb.selection_set(i)
    self.dp_sum.set((note + "  " if note else "") + (f"{len(groups)} group{'s' if len(groups) != 1 else ''} of clips from the same moment; {len(weaker)} weaker clip{'s' if len(weaker) != 1 else ''} selected." if groups else "No duplicates found ♡"))


@method
def dp_move(self):
    sel = [self.dp_rows[i] for i in self.dp_list.curselection() if i < len(self.dp_rows) and self.dp_rows[i]]
    if not sel: return self.dp_sum.set("Select the clips to move first (the “weaker” lines).")
    if not messagebox.askyesno("Duplicates", f"Move {len(sel)} clip{'s' if len(sel) != 1 else ''} (with their title and subtitle files) into a “Duplicates” folder?\nNothing is deleted.", parent=self.tools_win): return
    root = os.path.join(self.v["out"].get().strip() or A.HOME, "Shorts", "Duplicates"); n = 0
    for p in sel:
        new = vcshare.move_clip(p, root)
        if new: n += 1; vcmore.ledger_move(p, new)
    self.dp_run(f"Moved {n} clip{'s' if n != 1 else ''} into {root}.")
    try: self.clip_files_refresh()
    except Exception: pass


# ================================================================ Tools: bulk rename
def _tp_rename(self, f):
    vc22ui._intro(self, f, "Gives your clips new names from a pattern, with a preview first. The clip's title, subtitle and cover files are renamed with it, and nothing is ever overwritten. "
                           "Select clips in the list (none selected = all of them).")
    pat = self.o["name_pattern"].get().strip() or "{date} {game} clip {n}"
    self.rn_pat, self.rn_sum = tk.StringVar(value=pat), tk.StringVar()
    r = ttk.Frame(f); r.pack(fill="x"); r.columnconfigure(1, weight=1)
    ttk.Label(r, text="Pattern").grid(row=0, column=0, sticky="w")
    e = ttk.Entry(r, textvariable=self.rn_pat); e.grid(row=0, column=1, sticky="we", padx=8); e.bind("<Return>", lambda ev: self.rn_preview())
    ttk.Button(r, text="👀 Preview", command=self.rn_preview).grid(row=0, column=2)
    ttk.Button(r, text="✔ Rename", style="Accent.TButton", command=self.rn_apply).grid(row=0, column=3, padx=(6, 0))
    ttk.Label(f, text="You can use " + "  ".join("{" + k + "}" for k in vcouts.NAME_TOKENS), style="Mute.TLabel", wraplength=700, justify="left").pack(anchor="w", pady=(4, 0))
    ttk.Label(f, textvariable=self.rn_sum, style="Mute.TLabel").pack(anchor="w", pady=(4, 0))
    self.rn_files = _clips_now(self, 150)
    self.rn_list = _listbox(self, f, 7)
    for c in self.rn_files: self.rn_list.insert("end", os.path.relpath(c, self.v["out"].get().strip()) if self.v["out"].get().strip() else c)
    self.rn_prev = _textbox(self, f, 7); _put(self.rn_prev, [("Press Preview to see the new names.", "d")]); self.rn_plan = []


@method
def rn_picked(self):
    sel = [self.rn_files[i] for i in self.rn_list.curselection() if i < len(self.rn_files)]
    return sel or list(self.rn_files)


@method
def rn_preview(self):
    files = self.rn_picked()
    if not files: self.rn_plan = []; return self.rn_sum.set("You have no clips yet ♡")
    self.rn_plan = vcshare.rename_plan(files, self.rn_pat.get().strip(), info=vcmore.ledger_find)
    if not self.rn_plan: _put(self.rn_prev, [("Nothing would change.", "d")]); return self.rn_sum.set("These names would stay as they are.")
    parts = []
    for old, new in self.rn_plan[:200]: parts.append((os.path.basename(old) + "\n", "d")); parts.append(("   →  " + os.path.basename(new) + "\n", ""))
    _put(self.rn_prev, parts); self.rn_sum.set(f"{len(self.rn_plan)} clip{'s' if len(self.rn_plan) != 1 else ''} would be renamed.")


@method
def rn_apply(self):
    self.rn_preview()
    if not self.rn_plan: return
    if not messagebox.askyesno("Rename", f"Rename {len(self.rn_plan)} clip{'s' if len(self.rn_plan) != 1 else ''} (and their title, subtitle and cover files)?", parent=self.tools_win): return
    n = vcshare.rename_apply(self.rn_plan, ledger_move=vcmore.ledger_move)
    self.rn_sum.set(f"Renamed {n} clip{'s' if n != 1 else ''} ♡"); _put(self.rn_prev, [(f"Done: {n} renamed.", "ok")]); self.rn_plan = []
    self.rn_files = _clips_now(self, 150); self.rn_list.delete(0, "end")
    for c in self.rn_files: self.rn_list.insert("end", os.path.relpath(c, self.v["out"].get().strip()) if self.v["out"].get().strip() else c)
    try: self.clip_files_refresh()
    except Exception: pass


@method
def clip_files_refresh(self):
    """If the My clips page is showing, draw it again."""
    if self.mode.get() == "clips": self.refresh_clips()


# ================================================================ Tools: reports
def _tp_report(self, f):
    vc22ui._intro(self, f, "Make a page or a text for one of your streams from the clips you made of it: a highlights page you can open in your browser, a list of times for the video's description, "
                           "and a message for your community.")
    self.rp_vod, self.rp_sum = tk.StringVar(), tk.StringVar()
    r = ttk.Frame(f); r.pack(fill="x"); r.columnconfigure(1, weight=1)
    ttk.Label(r, text="Stream").grid(row=0, column=0, sticky="w")
    self.rp_combo = self.combo(r, self.rp_vod, [], 50); self.rp_combo.grid(row=0, column=1, sticky="we", padx=8)
    ttk.Button(r, text="↻", width=3, command=self.rp_refresh).grid(row=0, column=2)
    bar = ttk.Frame(f); bar.pack(fill="x", pady=6)
    ttk.Button(bar, text="📑 Highlights page", style="Accent.TButton", command=self.rp_html).pack(side="left")
    ttk.Button(bar, text="🕒 Timestamps", command=lambda: self.rp_text("stamps")).pack(side="left", padx=8)
    ttk.Button(bar, text="📣 Discord message", command=lambda: self.rp_text("discord")).pack(side="left")
    ttk.Button(bar, text="🧵 X thread", command=lambda: self.rp_text("x")).pack(side="left", padx=8)
    ttk.Button(bar, text="📋 Copy", command=self.rp_copy).pack(side="left")
    ttk.Label(f, textvariable=self.rp_sum, style="Mute.TLabel", wraplength=700, justify="left").pack(anchor="w")
    self.rp_out = _textbox(self, f, 14); _put(self.rp_out, [("Pick a stream, then a button.", "d")]); self.rp_vods = {}; self.rp_last = ""
    self.rp_refresh()


@method
def rp_refresh(self):
    groups = {}
    for e in vcmore.ledger_all():
        if e.get("deleted") or not e.get("vod") or not os.path.isfile(str(e.get("path", ""))): continue
        groups.setdefault(str(e["vod"]), []).append(e)
    self.rp_vods = {f"{os.path.basename(v)}  ({len(es)} clip{'s' if len(es) != 1 else ''})": es for v, es in sorted(groups.items(), key=lambda kv: -max(float(os.path.getmtime(e["path"])) for e in kv[1]))}
    names = list(self.rp_vods); self.rp_combo.configure(values=names)
    if names and self.rp_vod.get() not in self.rp_vods: self.rp_vod.set(names[0])
    self.rp_sum.set("" if names else "No clips of a stream yet. Make some Shorts first ♡")


def _rp_entries(self):
    es = self.rp_vods.get(self.rp_vod.get())
    if not es: _put(self.rp_out, [("Pick a stream first (make some Shorts if the list is empty).", "warn")]); return None
    return es


@method
def rp_html(self):
    es = _rp_entries(self)
    if not es: return
    out = self.v["out"].get().strip() or os.path.join(A.HOME, "StreamClips")
    vod = os.path.splitext(os.path.basename(str(es[0].get("vod", ""))))[0]
    try:
        os.makedirs(out, exist_ok=True)
        html = vcshare.report_html(es, vod, self.o["channel"].get().strip(), self.o["game"].get().strip(), base_dir=out)
        path = os.path.join(out, re.sub(r'[<>:"/\\|?*]', "_", vod)[:60] + "_highlights.html")
        with open(path, "w", encoding="utf-8") as fh: fh.write(html)
    except OSError as e: return _put(self.rp_out, [(f"I couldn't write the page: {e}", "bad")])
    self.rp_last = path; _put(self.rp_out, [(f"Saved: {path}\n", "ok"), ("It opens in your browser.", "d")]); A.open_path(path)


@method
def rp_text(self, kind):
    es = _rp_entries(self)
    if not es: return
    vod = os.path.splitext(os.path.basename(str(es[0].get("vod", ""))))[0]
    if kind == "stamps":
        t = vcshare.timestamps_text(es)
        if not t: return _put(self.rp_out, [("I need at least two clips of this stream to make a list of times.", "warn")])
    else:
        msgs = vcshare.community_message(es, vod, self.o["channel"].get().strip(), self.o["game"].get().strip(), fmt=kind)
        t = ("\n\n— next message —\n\n" if kind == "discord" else "\n\n").join(msgs)
    self.rp_last = t; _put(self.rp_out, [(t, "")])


@method
def rp_copy(self):
    t = self.rp_last
    if not t: return
    self.clipboard_clear(); self.clipboard_append(t); self.update(); _say(self, "Copied ♡")


# ================================================================ Tools: chapters
def _tp_chapters(self, f):
    vc22ui._intro(self, f, "Some videos carry chapters (many YouTube videos do; Twitch and Kick files often don't). If the video you loaded has them, you can pick one and I only look for clips inside it.")
    self.ch_sum, self.ch_rows = tk.StringVar(), []
    bar = ttk.Frame(f); bar.pack(fill="x")
    ttk.Button(bar, text="🔖 Read the chapters of my video", style="Accent.TButton", command=self.ch_read).pack(side="left")
    ttk.Button(bar, text="🎯 Look only inside the selected", command=self.ch_use).pack(side="left", padx=8)
    ttk.Button(bar, text="📋 Copy as timestamps", command=self.ch_copy).pack(side="left")
    ttk.Label(f, textvariable=self.ch_sum, style="Mute.TLabel", wraplength=700, justify="left").pack(anchor="w", pady=6)
    self.ch_list = _listbox(self, f, 12, "browse")


@method
def ch_read(self):
    p = self.v["video"].get().strip().strip('"')
    if not os.path.isfile(p): return self.ch_sum.set("Choose a video on the main page first.")
    self.ch_sum.set("Reading…"); ff, nowin = A.sc.FF, A.sc.NOWIN

    def go():
        try: ch = vcshare.read_chapters(p, ff, nowin)
        except Exception: ch = []
        self.ui(lambda: self.ch_show(ch))
    threading.Thread(target=go, daemon=True).start()


@method
def ch_show(self, ch):
    try:
        self.ch_rows = ch; lb = self.ch_list; lb.delete(0, "end")
        for a, b, t in ch: lb.insert("end", f"{vcshare.hms(a)} - {vcshare.hms(b)}    {t}")
        self.ch_sum.set(f"{len(ch)} chapter{'s' if len(ch) != 1 else ''} found." if ch else "This video has no chapters I can read. (They are stored in the video file, or in a .info.json next to it.)")
    except tk.TclError: pass


@method
def ch_use(self):
    s = self.ch_list.curselection()
    if not s or s[0] >= len(self.ch_rows): return self.ch_sum.set("Select a chapter first.")
    a, b, t = self.ch_rows[s[0]]
    self.o["range_from"].set(vcshare.hms(a)); self.o["range_to"].set(vcshare.hms(b))
    self.ch_sum.set(f"I'll only look between {vcshare.hms(a)} and {vcshare.hms(b)} (“{t}”). You can change this in Smart finding."); _say(self, "Time range set from the chapter ♡")


@method
def ch_copy(self):
    if not self.ch_rows: return
    t = "\n".join(f"{vcshare.hms(a)} {n}" for a, _, n in self.ch_rows)
    self.clipboard_clear(); self.clipboard_append(t); self.update(); _say(self, "Copied ♡")


# ================================================================ Tools: snapshots
@method
def snap_state(self):
    """The settings worth going back to: the look, every option and the recap settings (not the private words or the per-video fields)."""
    s = self.snapshot()
    s["opts"] = {k: v for k, v in s["opts"].items() if k not in SNAP_SKIP}
    return s


@method
def snap_auto(self):
    """A copy of the settings every time a job starts, so a change that made the clips worse can be undone. Does nothing when nothing changed."""
    return vcshare.snapshot_save(self.snap_state(), "Before a run")


def _tp_snaps(self, f):
    vc22ui._intro(self, f, "Every time you start making videos I keep a copy of your settings (the last 12). If a change made your clips worse, go back to one. "
                           "Your private words, your logo and music files and your videos are never touched.")
    self.sn_label, self.sn_sum = tk.StringVar(), tk.StringVar()
    r = ttk.Frame(f); r.pack(fill="x"); r.columnconfigure(1, weight=1)
    ttk.Label(r, text="Name").grid(row=0, column=0, sticky="w")
    ttk.Entry(r, textvariable=self.sn_label).grid(row=0, column=1, sticky="we", padx=8)
    ttk.Button(r, text="📸 Save one now", style="Accent.TButton", command=self.sn_save).grid(row=0, column=2)
    ttk.Label(f, textvariable=self.sn_sum, style="Mute.TLabel", wraplength=700, justify="left").pack(anchor="w", pady=4)
    self.sn_list = _listbox(self, f, 7, "browse"); self.sn_rows = []
    self.sn_list.bind("<<ListboxSelect>>", lambda e: self.sn_show())
    bar = ttk.Frame(f); bar.pack(fill="x", pady=6)
    ttk.Button(bar, text="↩ Go back to the selected", command=self.sn_restore).pack(side="left")
    ttk.Button(bar, text="🗑 Remove it", command=self.sn_delete).pack(side="left", padx=8)
    self.sn_diff = _textbox(self, f, 8); self.sn_refresh()


@method
def sn_refresh(self):
    self.sn_rows = vcshare.snapshot_list(); lb = self.sn_list; lb.delete(0, "end")
    for s in self.sn_rows: lb.insert("end", f"{s['made']}    {s['label'] or 'Settings'}    ({s['count']} groups)")
    self.sn_sum.set(f"{len(self.sn_rows)} snapshot{'s' if len(self.sn_rows) != 1 else ''} kept." if self.sn_rows else "No snapshots yet. One is saved when you start making videos, or press Save one now.")
    _put(self.sn_diff, [("Select a snapshot to see what would change.", "d")])


@method
def sn_save(self):
    name = vcshare.snapshot_save(self.snap_state(), self.sn_label.get().strip() or "Saved by me")
    self.sn_label.set(""); self.sn_refresh()
    if not name: self.sn_sum.set("Your settings are the same as the newest snapshot, so nothing new was saved.")


def _sn_sel(self):
    s = self.sn_list.curselection()
    return self.sn_rows[s[0]] if s and s[0] < len(self.sn_rows) else None


@method
def sn_show(self):
    row = _sn_sel(self)
    if not row: return
    old = vcshare.snapshot_load(row["id"])
    if old is None: return _put(self.sn_diff, [("That snapshot cannot be read.", "bad")])
    names = vcshare.snapshot_diff(_flat(old), _flat(self.snap_state()))
    if not names: return _put(self.sn_diff, [("Your settings are the same as this snapshot.", "ok")])
    a, b = _flat(old), _flat(self.snap_state()); parts = [(f"{len(names)} setting{'s' if len(names) != 1 else ''} would change:\n", "h")]
    for k in names[:60]:
        parts.append((k.replace("opts.", "").replace("look.", "look: ") + ":  ", "d")); parts.append((f"{str(b.get(k))[:30]}  →  {str(a.get(k))[:30]}\n", ""))
    if len(names) > 60: parts.append((f"…and {len(names) - 60} more", "d"))
    _put(self.sn_diff, parts)


@method
def sn_restore(self):
    row = _sn_sel(self)
    if not row: return self.sn_sum.set("Select a snapshot first.")
    old = vcshare.snapshot_load(row["id"])
    if old is None: return self.sn_sum.set("That snapshot cannot be read.")
    if self.busy: return self.sn_sum.set("I'm busy right now - go back to a snapshot when the job has finished.")
    if not messagebox.askyesno("Snapshots", f"Go back to the settings from {row['made']}?\n\n(The settings you have now are saved as a snapshot first, so you can come back.)", parent=self.tools_win): return
    vcshare.snapshot_save(self.snap_state(), "Before going back")
    try:
        self.apply_snapshot(old); self.sel_preset.set(""); self.update_pinfo(); self.draw_gallery(); self.refresh_eta(); self.save()
    except Exception: log_err(); return self.sn_sum.set("I couldn't put every setting back - see the log file.")
    self.sn_refresh(); self.sn_sum.set(f"Back to the settings from {row['made']} ♡")


@method
def sn_delete(self):
    row = _sn_sel(self)
    if not row or os.path.basename(row["id"]) != row["id"]: return
    try: os.remove(os.path.join(vcshare.SNAP_DIR, row["id"]))
    except OSError: pass
    self.sn_refresh()


# ================================================================ Tools: games (remember per game)
def _tp_games(self, f):
    vc22ui._intro(self, f, "When “Remember the number, length and style for each game” is on, I keep how many clips, how long, which style and layout you used for each game, and fill them in when you name that game again.")
    c = ttk.Checkbutton(f, text="🎮 Remember the number, length and style for each game", variable=self.o["game_memory"]); c.pack(anchor="w"); self.tip(c, "Saved after a Shorts run that names a game.")
    self.gm_sum, self.gm_keys = tk.StringVar(), []
    self.gm_list = _listbox(self, f, 10, "browse")
    bar = ttk.Frame(f); bar.pack(fill="x", pady=6)
    ttk.Button(bar, text="✨ Use these settings now", command=self.gm_use).pack(side="left")
    ttk.Button(bar, text="🗑 Forget this game", command=self.gm_forget).pack(side="left", padx=8)
    ttk.Label(f, textvariable=self.gm_sum, style="Mute.TLabel", wraplength=700, justify="left").pack(anchor="w"); self.gm_refresh()


@method
def gm_refresh(self):
    store = vctools.store_get("game_prefs", {}) or {}
    self.gm_keys = sorted(k for k, v in store.items() if isinstance(v, dict)); lb = self.gm_list; lb.delete(0, "end")
    for k in self.gm_keys:
        v = store[k]; lb.insert("end", f"{k}    -    {v.get('n', '?')} clips · {v.get('len_min', '?')}-{v.get('len_max', '?')} s · {v.get('style', '?')} · {v.get('layout', '?')}")
    self.gm_sum.set("" if self.gm_keys else "Nothing remembered yet. After your next Shorts run with a game name, it shows up here.")


def _gm_sel(self):
    s = self.gm_list.curselection()
    return self.gm_keys[s[0]] if s and s[0] < len(self.gm_keys) else None


@method
def gm_use(self):
    k = _gm_sel(self)
    if not k: return self.gm_sum.set("Select a game first.")
    msg = self.game_apply(vcshare.game_get(k), k)
    self.gm_sum.set(msg or "There is nothing usable stored for that game.")


@method
def gm_forget(self):
    k = _gm_sel(self)
    if not k: return
    store = vctools.store_get("game_prefs", {}) or {}
    store.pop(k, None); vctools.store_put("game_prefs", store); self.gm_refresh()


@method
def game_apply(self, prefs, name=""):
    """Put remembered settings for a game into the window (each value is checked first). Returns a plain sentence, or '' when nothing was usable."""
    done = []
    try:
        n = int(float(prefs.get("n")))
        if 1 <= n <= 60: self.v["n"].set(str(n)); done.append(f"{n} clips")
    except (TypeError, ValueError): pass
    try:
        lo, hi = float(prefs.get("len_min")), float(prefs.get("len_max"))
        if 5 <= lo < hi <= 180: self.v["lmin"].set(str(int(lo))); self.v["lmax"].set(str(int(hi))); done.append(f"{int(lo)}-{int(hi)} s")
    except (TypeError, ValueError): pass
    if prefs.get("style") in A.STYLE_NAMES: self.v["style"].set(prefs["style"]); done.append(A.STYLE_NAMES[prefs["style"]].lower())
    if prefs.get("layout") in A.LAYOUT_NAMES: self.v["layout"].set(prefs["layout"]); done.append("layout " + str(A.LAYOUT_NAMES[prefs["layout"]]).split(" (")[0].lower())
    if not done: return ""
    self.refresh_eta()
    return f"Filled in what I remembered for {name or 'this game'}: " + ", ".join(done) + "."


@method
def game_changed(self):
    """She named a game: use what was remembered for it (only when the option is on). Waits a moment so typing does not apply half a name."""
    if self.game_job is not None:
        try: self.after_cancel(self.game_job)
        except Exception: pass
    self.game_job = self.after(900, self.game_apply_now)


@method
def game_apply_now(self):
    self.game_job = None
    try:
        if not self.o["game_memory"].get() or self.busy: return
        g = self.o["game"].get().strip(); p = vcshare.game_get(g)
        if not p: return
        msg = self.game_apply(p, g)
        if msg: _say(self, msg + " ♡")
    except Exception: log_err()


# ================================================================ downloads: settings rows, the cut-out dialog, the options for yt-dlp
@method
def dl_refresh(self):
    try:
        args, notes = vcnet.ytdlp_args({k: v.get() for k, v in self.dl.items()})
        self.dl_note.set("  ".join(notes))
    except Exception: self.dl_note.set("")


@method
def dl_options(self):
    """The download options as a plain dict (read in the window thread, used in the worker)."""
    return {k: v.get() for k, v in self.dl.items()}


@method
def dl23_rows(self, t3):
    """Rows added to Settings -> Downloads."""
    ttk.Label(t3, text="More download options", font=(A.FONT, 10, "bold"), foreground=self.t["accent"]).grid(row=3, column=0, columnspan=3, sticky="w", pady=(10, 2))
    ttk.Label(t3, text="Speed limit").grid(row=4, column=0, sticky="w", pady=3)
    f = ttk.Frame(t3); f.grid(row=4, column=1, columnspan=2, sticky="w", padx=8)
    ttk.Entry(f, textvariable=self.dl["dl_rate"], width=10).pack(side="left"); ttk.Label(f, text="like 2M or 500K per second - empty = as fast as possible", style="Mute.TLabel").pack(side="left", padx=8)
    ttk.Label(t3, text="Pieces at once").grid(row=5, column=0, sticky="w", pady=3)
    f = ttk.Frame(t3); f.grid(row=5, column=1, columnspan=2, sticky="w", padx=8)
    self.spin(f, self.dl["dl_frags"], 1, 16, 1, 5).pack(side="left"); ttk.Label(f, text="1-16 - more is faster on a good connection, fewer is gentler", style="Mute.TLabel").pack(side="left", padx=8)
    ttk.Label(t3, text="Cookies file").grid(row=6, column=0, sticky="w", pady=3)
    f = ttk.Frame(t3); f.grid(row=6, column=1, columnspan=2, sticky="we", padx=8); f.columnconfigure(0, weight=1)
    ttk.Entry(f, textvariable=self.dl["dl_cookie_file"]).grid(row=0, column=0, sticky="we")
    ttk.Button(f, text="Browse", command=lambda: self.dl["dl_cookie_file"].set(filedialog.askopenfilename(parent=self.sw, title="Choose a cookies file", filetypes=[("Text files", "*.txt"), ("All files", "*.*")]) or self.dl["dl_cookie_file"].get())).grid(row=0, column=1, padx=6)
    ttk.Button(f, text="✖", width=3, command=lambda: self.dl["dl_cookie_file"].set("")).grid(row=0, column=2)
    self.autowrap(ttk.Label(t3, text="For subscriber-only VODs when your browser can't be used: a cookies.txt exported from your browser (the Netscape text format). It replaces the browser choice above and is never shown or logged.",
                            style="Mute.TLabel", justify="left"), t3, 30).grid(row=7, column=0, columnspan=3, sticky="w")
    ttk.Label(t3, text="Only this part").grid(row=8, column=0, sticky="w", pady=(8, 3))
    f = ttk.Frame(t3); f.grid(row=8, column=1, columnspan=2, sticky="w", padx=8, pady=(8, 3))
    ttk.Label(f, text="from").pack(side="left"); ttk.Entry(f, textvariable=self.dl["dl_from"], width=10).pack(side="left", padx=6)
    ttk.Label(f, text="to").pack(side="left"); ttk.Entry(f, textvariable=self.dl["dl_to"], width=10).pack(side="left", padx=6)
    ttk.Label(f, text="like 1:20:00 - for the next download only", style="Mute.TLabel").pack(side="left", padx=8)
    self.autowrap(ttk.Label(t3, textvariable=self.dl_note, style="Mute.TLabel", justify="left"), t3, 30).grid(row=9, column=0, columnspan=3, sticky="w", pady=(4, 0))


@method
def dl_part_dialog(self):
    w = tk.Toplevel(self); w.title("Download only a part ✂"); w.configure(bg=self.t["bg"]); w.transient(self); A.center_over(w, self, 460, 230)
    ttk.Label(w, text="Download only a part of the VOD", font=(A.FONT, 11, "bold")).pack(anchor="w", padx=16, pady=(14, 4))
    ttk.Label(w, text="Saves a lot of time and space for a long stream. Leave a box empty to go to the start or the end. Used for the next download only.", style="Mute.TLabel", wraplength=420, justify="left").pack(anchor="w", padx=16)
    r = ttk.Frame(w); r.pack(anchor="w", padx=16, pady=10)
    ttk.Label(r, text="from").pack(side="left"); ttk.Entry(r, textvariable=self.dl["dl_from"], width=10).pack(side="left", padx=6)
    ttk.Label(r, text="to").pack(side="left"); ttk.Entry(r, textvariable=self.dl["dl_to"], width=10).pack(side="left", padx=6)
    ttk.Label(r, text="like 1:20:00", style="Mute.TLabel").pack(side="left", padx=8)
    ttk.Label(w, textvariable=self.dl_note, style="Mute.TLabel", wraplength=420, justify="left").pack(anchor="w", padx=16)
    bf = ttk.Frame(w); bf.pack(pady=10)
    ttk.Button(bf, text="Clear", command=lambda: (self.dl["dl_from"].set(""), self.dl["dl_to"].set(""))).pack(side="left", padx=6)
    ttk.Button(bf, text="Done", style="Accent.TButton", command=w.destroy).pack(side="left", padx=6)
    w.bind("<Escape>", lambda e: w.destroy())


# ================================================================ updates
def _tp_updates(self, f):
    vc22ui._intro(self, f, "Check if a newer version of VTuber Clipper is out, install it, or go back to the version before. An update only replaces the program files: your settings, clips, fonts, looks and "
                           "private words are never touched, a copy of every replaced file is kept, and if anything goes wrong while installing, everything is put back.")
    c = ttk.Checkbutton(f, text="Check once a day when the app starts (it only asks GitHub for the newest release number)", variable=self.o["update_check"]); c.pack(anchor="w")
    bar = ttk.Frame(f); bar.pack(fill="x", pady=8)
    ttk.Button(bar, text="🔄 Check now", style="Accent.TButton", command=lambda: self.upd_check(True)).pack(side="left")
    self.upd_install_btn = ttk.Button(bar, text="⬇ Download and install", command=self.upd_install); self.upd_install_btn.pack(side="left", padx=8)
    i_ = self.upd_info or {}; self.upd_install_btn.state(["!disabled"] if i_.get("status") == "newer" and i_.get("asset_url") else ["disabled"])
    ttk.Button(bar, text="📦 Install a zip I have…", command=self.upd_from_zip).pack(side="left")
    ttk.Button(bar, text="↩ Undo the last update", command=self.upd_undo).pack(side="left", padx=8)
    ttk.Button(bar, text="🌐 Release page", command=self.upd_page).pack(side="left")
    ttk.Label(f, textvariable=self.upd_note, wraplength=700, justify="left").pack(anchor="w")
    self.upd_out = _textbox(self, f, 10); self.upd_refresh_view()


def _install_root(): return os.path.dirname(A.APP_DIR)


@method
def upd_refresh_view(self):
    parts = [(f"You have VTuber Clipper {A.VER_LABEL}.\n", "h")]
    info = self.upd_info
    if info and info.get("status") == "newer":
        parts.append((f"\nNewest: {info.get('name') or info.get('latest')}\n", "ok"))
        if info.get("notes"): parts.append((info["notes"][:1200] + "\n", "d"))
    bl = vcnet.list_backups(_install_root())
    if bl:
        parts.append(("\nBackups you can go back to:\n", "h"))
        for b in bl[:5]: parts.append((f"  {b['made']}   update to {b['version']}   ({b['files']} files)" + ("" if b["applied"] else "   (already undone)") + "\n", ""))
    _put(self.upd_out, parts)


@method
def upd_check(self, manual=False):
    if self.upd_busy: return
    self.upd_busy = True; self.upd_note.set("Asking GitHub…" if manual else self.upd_note.get())

    def go():
        try: info = vcnet.check_update(A.VERSION, A.BETA)
        except Exception as e: info = dict(status="error", message="Could not check (" + str(e)[:60] + ").", asset_url="")
        self.ui(lambda: self.upd_show(info, manual))
    threading.Thread(target=go, daemon=True).start()


@method
def upd_show(self, info, manual=False):
    self.upd_busy = False; self.upd_info = info
    self.upd_last = time.strftime("%Y-%m-%d")
    self.upd_note.set(info.get("message", "")); self.save()
    if info.get("status") == "newer": _say(self, "A newer version is out ♡  Settings -> About, or Tools -> Updates.")
    elif manual: _say(self, info.get("message", ""))
    try: self.upd_refresh_view()
    except (tk.TclError, AttributeError): pass
    try: self.upd_install_btn.state(["!disabled"] if info.get("status") == "newer" and info.get("asset_url") else ["disabled"])
    except (tk.TclError, AttributeError): pass


@method
def upd_auto(self):
    """The daily check when the app starts (only when switched on): quiet, in the background."""
    try:
        if self.upd_last == time.strftime("%Y-%m-%d") or not self.o["update_check"].get(): return
        self.upd_check(False)
    except Exception: log_err()


@method
def upd_page(self):
    import webbrowser
    page = (self.upd_info or {}).get("page") or vcnet.RELEASES_URL.replace("api.github.com/repos", "github.com").replace("/releases/latest", "/releases")
    webbrowser.open(page)


@method
def upd_install(self):
    info = self.upd_info
    if not info or info.get("status") != "newer" or not info.get("asset_url"): return self.upd_note.set("Press Check now first. (A release needs an update zip attached to be installed from here.)")
    if self.busy: return self.upd_note.set("I'm busy right now - install the update when the job has finished.")
    if not messagebox.askyesno("Update", f"Download and install {info.get('name')}?\n\nA copy of every file it replaces is kept, so you can go back with “Undo the last update”.", parent=self.tools_win or self): return
    self.upd_note.set("Downloading…"); self.upd_busy = True

    def go():
        try:
            tmp = tempfile.mkdtemp(prefix="vtc_upd_")
            path = vcnet.download_update(info, tmp)
            res = vcnet.apply_update(path, _install_root())
        except RuntimeError as e: res = dict(ok=False, message=str(e))
        except Exception as e: res = dict(ok=False, message="The update did not work (" + str(e)[:80] + ").")
        self.ui(lambda: self.upd_done(res))
    threading.Thread(target=go, daemon=True).start()


@method
def upd_from_zip(self):
    if self.busy: return self.upd_note.set("I'm busy right now - install the update when the job has finished.")
    p = filedialog.askopenfilename(parent=self.tools_win or self, title="Choose the update zip", filetypes=[("Update zip", "*.zip"), ("All files", "*.*")])
    if not p: return
    info = vcnet.inspect_update(p)
    if not info["ok"]: return self.upd_note.set("That zip can't be installed: " + " ".join(info["problems"][:2]))
    if not messagebox.askyesno("Update", f"Install the update to version {info['version']}{' beta' if info['beta'] else ''} from this zip?\n\n{len(info['files'])} files. A copy of every file it replaces is kept.", parent=self.tools_win or self): return
    self.upd_busy = True; self.upd_note.set("Installing…")

    def go():
        try: res = vcnet.apply_update(p, _install_root())
        except Exception as e: res = dict(ok=False, message="The update did not work (" + str(e)[:80] + ").")
        self.ui(lambda: self.upd_done(res))
    threading.Thread(target=go, daemon=True).start()


@method
def upd_done(self, res):
    self.upd_busy = False; self.upd_note.set(res.get("message", ""))
    try: self.upd_refresh_view()
    except (tk.TclError, AttributeError): pass
    if res.get("ok"): messagebox.showinfo("Update", res["message"], parent=self.tools_win or self)


@method
def upd_undo(self):
    if self.busy: return self.upd_note.set("I'm busy right now - undo when the job has finished.")
    bl = [b for b in vcnet.list_backups(_install_root()) if b["applied"]]
    if not bl: return self.upd_note.set("There is no update to undo.")
    if not messagebox.askyesno("Undo", f"Go back to the program files from before the update to {bl[0]['version']} ({bl[0]['made']})?", parent=self.tools_win or self): return
    res = vcnet.undo_update(_install_root()); self.upd_note.set(res["message"]); self.upd_refresh_view()


@method
def about23_rows(self, t):
    """Rows added to Settings -> About."""
    ttk.Label(t, text="Updates", font=(A.FONT, 10, "bold"), foreground=self.t["accent"]).pack(anchor="w", pady=(14, 2))
    bf = ttk.Frame(t); bf.pack(anchor="w")
    ttk.Button(bf, text="🔄 Check for updates", command=lambda: self.upd_check(True)).pack(side="left")
    ttk.Button(bf, text="🧰 Install or undo an update…", command=lambda: self.open_toolbox("updates")).pack(side="left", padx=8)
    self.autowrap(ttk.Label(t, textvariable=self.upd_note, style="Mute.TLabel", justify="left"), t, 30).pack(anchor="w", pady=(4, 0))
    c = ttk.Checkbutton(t, text="Check once a day when the app starts", variable=self.o["update_check"]); c.pack(anchor="w", pady=(4, 0))
    self.tip(c, "Only asks GitHub for the newest release number. Nothing is installed without you pressing the button.")
