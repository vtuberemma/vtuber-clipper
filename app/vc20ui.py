"""VTuber Clipper 2.0 - the new screens and helpers of the app window:
the Polish tab (looks, overlays, voice), extra-file options (file names, transcript),
settings backup / restore, "reset this tab", paste a link, start later, save the log, favourites + posted marks, your numbers,
keyboard shortcuts and the mascot's tips.

streamclip_app.py calls install(App, module) once; every function below becomes a method of the App window."""
import datetime, glob, json, os, re, shutil, subprocess, sys, tempfile, threading, time, zipfile
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import vcfx, vcouts

A = None                    # the app module (streamclip_app), set by install()
METHODS = {}

# --- the new options (the app's OPT_STR / OPT_BOOL lists get these added)
NEW_STR = ("color_look", "crisp", "fade", "hide_box", "hide_style", "lower_name", "lower_sub", "follow_text", "buddy_feeling", "buddy_pos", "buddy_size",
           "voice_fx", "voice_eq", "bleep_sound", "loudness", "name_pattern")
NEW_BOOL = ("auto_light", "auto_crop", "vignette", "part_badge", "buddy", "emote_fx", "emote_sound", "transcript", "vod_folder")
POLISH_KEYS = ("color_look", "crisp", "fade", "hide_box", "hide_style", "lower_name", "lower_sub", "follow_text", "buddy_feeling", "buddy_pos", "buddy_size", "voice_fx", "voice_eq",
               "bleep_sound", "loudness", "auto_light", "auto_crop", "vignette", "part_badge", "buddy", "emote_fx", "emote_sound")
OUTPUT_KEYS = ("transcript", "name_pattern", "vod_folder")
# what "Reset this tab" puts back, per tab: options (self.o), plain fields (self.v) and a note for the user
RESET = {
    "basics": dict(o=("platform", "bg_style", "bg_color", "bg_image", "filler", "fresh"), v=dict(n="8", lmin="25", lmax="45", gap="1.5", style="mix", layout="stack", aspect="9:16")),
    "fx": dict(o=("sfx_pack",), v={}),
    "captions": dict(o=("cap_style", "cap_font", "cap_size", "cap_pos", "cap_text", "cap_hi", "cap_edge", "cap_emph", "cap_emoji", "review", "hook_mode", "hook_text"), v={}),
    "emotes": dict(o=("emotes", "emote_level", "emote_size", "emote_pos", "emote_burst", "emote_recap", "emote_cover", "emote_review"), v={}),
    "polish": dict(o=POLISH_KEYS, v={}),
    "extras": dict(o=("logo", "logo_pos", "logo_size", "handle", "handle_pos", "intro", "outro", "cta", "stickers", "sticker_size", "music", "music_vol", "duck", "voice_clean", "fix_lag", "swears"), v=dict(words="")),
    "post": dict(o=("post_kit", "srt", "cover", "channel", "game", "tags") + OUTPUT_KEYS, v={}),
}
POSTED_WHERE = ("YouTube", "TikTok", "Instagram", "X", "Somewhere else")
TIPS_MAX = 46               # the mascot's speech bubble is small: tips must be short


def method(fn):
    METHODS[fn.__name__] = fn; return fn


def install(App, module):
    global A
    A = module
    for k, fn in METHODS.items(): setattr(App, k, fn)


def sc_(): return A.sc


# ================================================================ set-up / saving
@method
def init20(self, cfg):
    """Called from __init__: the state the 2.0 features keep."""
    m = cfg.get("marks") if isinstance(cfg.get("marks"), dict) else {}
    fav = m.get("fav") if isinstance(m.get("fav"), list) else []
    posted = m.get("posted") if isinstance(m.get("posted"), dict) else {}
    self.marks = dict(fav=[str(x) for x in fav if isinstance(x, str)][:2000],
                      posted={str(k): [str(w) for w in v if isinstance(w, str)] for k, v in list(posted.items())[:2000] if isinstance(v, list)})
    self.tips_on = tk.BooleanVar(value=bool(cfg.get("tips", True)))
    self.clip_fav_only, self.clip_hide_posted = tk.BooleanVar(value=False), tk.BooleanVar(value=False)
    self.later_id, self.later_at, self.later_tries = None, 0.0, 0


@method
def cfg20(self):
    return dict(marks=self.marks, tips=bool(self.tips_on.get()))


@method
def bind20(self):
    """Keyboard shortcuts. The ones that would clash with typing (Ctrl+O, Ctrl+T, Ctrl+L) do nothing while a text box has the cursor."""
    def typing():
        try: return isinstance(self.focus_get(), (tk.Entry, tk.Text, ttk.Entry, ttk.Combobox, ttk.Spinbox))
        except Exception: return False

    def key(seq, fn, guard=True):
        def h(e=None):
            if guard and typing(): return None
            fn(); return "break"
        self.bind_all(seq, h)
    key("<Control-o>", self.browse_video); key("<Control-l>", self.toggle_log); key("<Control-t>", self.later_clicked)
    key("<Control-comma>", self.open_settings, False); key("<Control-Shift-V>", self.paste_link, False); key("<Control-Shift-v>", self.paste_link, False)
    for i, (k, _) in enumerate(A.MODES[:9], 1): key(f"<Control-Key-{i}>", lambda k=k: self.mode.set(k), False)


SHORTCUTS = ("Ctrl + Enter   make the videos\nCtrl + O   choose a video\nCtrl + Shift + V   paste a link and download it\nCtrl + 1 … 6   switch between Shorts, Recap, Best moments… My clips\n"
             "Ctrl + T   start later (a timer)\nCtrl + L   show / hide the Details log\nCtrl + ,   Settings\nF1   Settings → About\nEsc   cancel a sleep / shut-down countdown\n"
             "Hover an effect for 2 seconds   what it does\nClick the mascot   she says hi")


# ================================================================ Polish tab
@method
def build_polish(self, x):
    o = self.o; x.columnconfigure(1, weight=1); sc = sc_(); ve_ = A.EM()
    r = [0]

    def row(label, w, tip=None):
        r[0] += 1; ttk.Label(x, text=label).grid(row=r[0], column=0, sticky="w", pady=3); w.grid(row=r[0], column=1, columnspan=2, sticky="w", padx=8)
        if tip: self.tip(w, tip)
        return w

    def note(txt):
        r[0] += 1; ttk.Label(x, text=txt, style="Mute.TLabel", wraplength=500, justify="left").grid(row=r[0], column=1, columnspan=2, sticky="w", padx=8, pady=(0, 2))

    def check(key, txt, tip=None):
        r[0] += 1; c = ttk.Checkbutton(x, text=txt, variable=o[key]); c.grid(row=r[0], column=1, columnspan=2, sticky="w", padx=8)
        if tip: self.tip(c, tip)
        return c

    def head(txt):
        r[0] += 1; self.head(x, txt, r[0])

    head("🎨 Picture")
    row("Colour look", self.pick(x, o["color_look"], vcfx.LOOK_NAMES, 28), "A colour filter over the whole video: warm sunset, cool moonlight, vintage film, noir black & white, pastel, neon or cinematic.")
    row("Crisp picture", self.pick(x, o["crisp"], vcfx.CRISP_NAMES, 12), "Smooths a little grain and sharpens edges. Good for soft or blocky stream quality. Slower to render.")
    row("Fade in and out", self.pick(x, o["fade"], vcfx.FADE_NAMES, 18), "The clip fades in from black at the start and out to black at the end, picture and sound together.")
    check("auto_light", "☀ Brighten dark videos automatically", "The app measures how bright the picture is and lifts the shadows only when it is really dark. Normal videos are left alone.")
    check("vignette", "🖼 Soft dark corners (vignette)", "Gently darkens the corners so the middle of the picture stands out.")
    check("auto_crop", "✂ Cut away black bars around the picture", "Finds black bars (letterbox / pillarbox) in the video and crops them away, so the game fills the frame. Only real, solid black bars are cut.")
    hb = ttk.Frame(x); ttk.Entry(hb, textvariable=o["hide_box"], width=17).pack(side="left")
    ttk.Button(hb, text="🎯 Choose on the picture…", command=self.hide_pick).pack(side="left", padx=6)
    self.pick(hb, o["hide_style"], vcfx.HIDE_STYLES, 12).pack(side="left"); ttk.Button(hb, text="✖", width=3, command=lambda: o["hide_box"].set("")).pack(side="left", padx=4)
    row("🙈 Hide a spot", hb, "Covers one spot of the original picture for the whole clip: a private message, an address, a donation name. Draw the box on a frame of your video.")
    note("Cover a spot (chat names, an address, a notification) with a blur, pixels or a black box.")
    head("🏷 Overlays")
    ln = ttk.Frame(x); ttk.Entry(ln, textvariable=o["lower_name"], width=22).pack(side="left"); ttk.Label(ln, text="  line under it").pack(side="left"); ttk.Entry(ln, textvariable=o["lower_sub"], width=26).pack(side="left", padx=6)
    row("Name tag (lower third)", ln, "Your name slides in from the side for about 3 seconds, with a small line under it, for example “MiaVT” and “Variety streamer”. Empty = none.")
    row("Follow reminder", ttk.Entry(x, textvariable=o["follow_text"], width=30), "A short pill that pops up in the middle of clips longer than 8 seconds, for example “Follow for more ♡”. Empty = none.")
    check("part_badge", "🔢 “PART 2/5” badge on every clip of a run", "Each clip made in one go gets a small PART n/total badge at the top, handy for a series.")
    names = {k: lab for k, lab, _ in ve_.all_feelings()} or {"cool": "Cool"}
    cb = ttk.Frame(x); ttk.Checkbutton(cb, text="Show my chibi in a corner", variable=o["buddy"]).pack(side="left")
    self.pick(cb, o["buddy_feeling"], names, 10).pack(side="left", padx=6); self.pick(cb, o["buddy_pos"], A.CORNER_NAMES, 10).pack(side="left")
    ttk.Label(cb, text=" size %").pack(side="left", padx=(8, 2)); self.spin(cb, o["buddy_size"], 8, 45, 1, 4).pack(side="left")
    row("🐾 Chibi buddy", cb, "A picture of your model sits in a corner and hops while you talk, then rests when you are quiet.")
    check("emote_fx", "💥 The picture reacts to a chibi emote", "Scary / angry pictures split the colours for a moment, happy ones flash, sad ones drain the colour. Needs “Chibi emotes” (Chibi emotes tab).")
    check("emote_sound", "🔔 A soft pop sound when a chibi emote appears", "A rising pop for happy feelings, a falling one for sad or scary ones. Needs “Chibi emotes” (Chibi emotes tab).")
    head("🎙 Sound")
    vf = ttk.Frame(x); self.pick(vf, o["voice_fx"], vcfx.VOICE_FX_NAMES, 18).pack(side="left")
    self.tip(ttk.Button(vf, text="▶ Hear it", command=self.hear_voice), "Plays 6 seconds of your video with this voice, so you can check it before making clips.").pack(side="left", padx=6)
    ttk.Button(vf, text="■", width=3, command=self.stop_sound).pack(side="left")
    row("Voice effect", vf, "Make your voice deeper, higher, a chipmunk, a robot, an echo, an old telephone, a megaphone or underwater. The speed stays the same.")
    row("Voice sound", self.pick(x, o["voice_eq"], vcfx.VOICE_EQ_NAMES, 22), "Warm and soft, crisp and clear, or podcast / radio. Applies together with the voice effect and “Clean up my voice”.")
    bf = ttk.Frame(x); self.pick(bf, o["bleep_sound"], vcfx.BLEEP_NAMES, 18).pack(side="left")
    ttk.Button(bf, text="▶ Hear it", command=self.hear_bleep).pack(side="left", padx=6)
    row("Bleep sound", bf, "What plays over a bleeped word (see Logo & music → Bleep words): the classic beep, silence, a cartoon boing, a ding, a duck or a laser.")
    row("Loudness", self.pick(x, o["loudness"], vcfx.LOUDNESS, 44), "How loud the finished clip is. -14 is right for TikTok, Shorts and Reels.")
    self.polish_note = tk.StringVar()
    r[0] += 1; ttk.Label(x, textvariable=self.polish_note, style="Mute.TLabel", wraplength=500, justify="left").grid(row=r[0], column=1, columnspan=2, sticky="w", padx=8, pady=(6, 0))


class _Spot:
    pass


@method
def hide_pick(self):
    p = self.v["video"].get().strip().strip('"')
    if not os.path.isfile(p): return self.polish_note.set("Pick a video first (Step 1), then I can show you a frame to draw on ♡")
    info = A.sc.probe_info(p)
    if not info["w"]: return self.polish_note.set("I couldn't read that video.")
    sw, sh = info["w"], info["h"]; box = vcfx.parse_box(self.o["hide_box"].get())
    init = ""
    if box: init = f"{int(sw * box[2] / 100)}:{int(sh * box[3] / 100)}:{int(sw * box[0] / 100)}:{int(sh * box[1] / 100)}"

    class SpotPicker(A.CamPicker):
        def draw(s):
            super().draw(); c = s.cv
            for i in c.find_withtag("ov"):
                if c.type(i) == "text": c.itemconfigure(i, text="🙈 hidden")

    def done(cam):
        m = re.match(r"^(\d+):(\d+):(\d+):(\d+)$", cam)
        if not m: return
        w, h, x, y = (int(g) for g in m.groups())
        self.o["hide_box"].set(f"{x / sw * 100:.1f}:{y / sh * 100:.1f}:{w / sw * 100:.1f}:{h / sh * 100:.1f}")
        self.polish_note.set("Spot saved. It is remembered as a part of the picture, so it also fits your other videos from the same game or stream.")
    pk = SpotPicker(self, p, info["dur"] or 60, sw, sh, init, done, "🙈 Drag a box over what should be hidden (a chat name, an address, a notification). Corners resize, drag inside to move.")
    pk.title("Choose the spot to hide"); pk.lock.set(False)


def _voice_text(self):
    chain = vcfx.voice_chain(self.o["voice_eq"].get(), self.o["voice_fx"].get())
    if self.o["voice_clean"].get(): chain = "," + A.sc.VOICE_CLEAN + chain
    return chain


@method
def hear_voice(self):
    p = self.v["video"].get().strip().strip('"')
    if not os.path.isfile(p): return self.polish_note.set("Pick a video first (Step 1) so you hear your own voice ♡")
    chain = _voice_text(self); sc = A.sc
    words = self.cached_words(p)                                    # reads the settings, so it is done here and not in the worker thread
    self.polish_note.set("Getting a taste of your voice…")

    def go():
        try:
            info = sc.probe_info(p); t0 = max(0.0, (info["dur"] or 60) * .2)
            if words:                                            # the busiest 6 seconds of talking
                best, bs = 0.0, -1
                for w in words[::8]:
                    n = sum(1 for x in words if w["start"] <= x["start"] < w["start"] + 6)
                    if n > bs: best, bs = w["start"], n
                t0 = best
            out = os.path.join(tempfile.gettempdir(), "vclip_voice_preview.wav")
            r = subprocess.run([sc.FF, "-y", "-v", "error", "-ss", f"{t0:.2f}", "-t", "6", "-i", p, "-vn", "-af", f"aresample=48000{chain},loudnorm=I=-16:TP=-1.5", "-ac", "2", out],
                               capture_output=True, text=True, errors="replace", timeout=120, **sc.NOWIN)
            ok = r.returncode == 0 and os.path.isfile(out)
        except Exception: ok = False; out = ""
        self.ui(lambda: (self.play_sound(out), self.polish_note.set("Playing 6 seconds of your voice ♪")) if ok else self.polish_note.set("I couldn't make a sample from that video."))
    threading.Thread(target=go, daemon=True).start()


@method
def hear_bleep(self):
    sc = A.sc; tone = vcfx.bleep_tone(self.o["bleep_sound"].get())
    out = os.path.join(tempfile.gettempdir(), "vclip_bleep_preview.wav")

    def go():
        try:
            r = subprocess.run([sc.FF, "-y", "-v", "error", "-f", "lavfi", "-i", f"aevalsrc='{tone}':d=1.2:s=48000", "-ac", "2", out], capture_output=True, errors="replace", timeout=60, **sc.NOWIN)
            ok = r.returncode == 0 and os.path.isfile(out)
        except Exception: ok = False
        if ok: self.ui(lambda: self.play_sound(out))
    threading.Thread(target=go, daemon=True).start()


# ================================================================ extra files (Posting tab)
@method
def build_outputs(self, x, row0):
    o = self.o
    self.head(x, "📎 Extra files and names", row0)
    items = (("transcript", "📜 A transcript (.txt) and web subtitles (.vtt)", "What was said, with times. Great for descriptions, blogs and accessibility."),)
    for i, (k, txt, tip) in enumerate(items, 1):
        c = ttk.Checkbutton(x, text=txt, variable=o[k]); c.grid(row=row0 + i, column=0, columnspan=3, sticky="w"); self.tip(c, tip)
    r = row0 + len(items) + 1
    ttk.Label(x, text="File names").grid(row=r, column=0, sticky="w", pady=(8, 3))
    ne = ttk.Entry(x, textvariable=o["name_pattern"]); ne.grid(row=r, column=1, sticky="we", padx=8, pady=(8, 3))
    self.tip(ne, "How each clip is named. Use {video} {n} {hook} {date} {game} {time} {channel} {type} {score} {len}. Example: {date} {game} {type} {score} clip {n}")
    ttk.Button(x, text="Reset", command=lambda: o["name_pattern"].set(A.sc.OPTS["name_pattern"])).grid(row=r, column=2, sticky="w", pady=(8, 3))
    self.name_prev = tk.StringVar()
    ttk.Label(x, textvariable=self.name_prev, style="Mute.TLabel", wraplength=640, justify="left").grid(row=r + 1, column=1, columnspan=2, sticky="w", padx=8)
    o["name_pattern"].trace_add("write", lambda *a: self.name_preview()); o["game"].trace_add("write", lambda *a: self.name_preview()); o["channel"].trace_add("write", lambda *a: self.name_preview())
    self.name_preview()
    fc = ttk.Checkbutton(x, text="📁 Put each VOD's clips in their own folder", variable=o["vod_folder"]); fc.grid(row=r + 2, column=0, columnspan=3, sticky="w", pady=(4, 0))
    self.tip(fc, "Clips go to Shorts / <name of the video> / … instead of all together, which keeps big back-catalogues tidy.")


@method
def name_preview(self):
    try:
        v = self.v["video"].get().strip().strip('"'); stem = re.sub(r'[<>:"/\\|?*]', "_", os.path.splitext(os.path.basename(v))[0])[:60] if v else "MyStream"
        self.name_prev.set("Example: " + vcouts.pattern_preview(self.o["name_pattern"].get(), stem or "MyStream", 1, "so yesterday I was", self.o["game"].get() or "Minecraft", self.o["channel"].get() or "MiaVT"))
    except Exception: pass


# ================================================================ reset this tab
@method
def reset_tab(self):
    k = self.sub.get(); spec = RESET.get(k)
    if not spec: return
    name = dict(A.SUBTABS).get(k, k)
    if not messagebox.askyesno("VTuber Clipper", f"Put every setting of the “{name}” tab back to how it was when you first opened the app?\n\n(Your videos and other tabs are not touched.)"): return
    sc = A.sc
    for key in spec["o"]:
        if key in self.o and key in sc.OPTS:
            d = sc.OPTS[key]; self.o[key].set(bool(d) if isinstance(self.o[key], tk.BooleanVar) else str(d))
    for key, val in spec["v"].items():
        if key in self.v: self.v[key].set(val)
    if k in ("basics", "quick"): self.silence.set(True); self.caps.set(True)
    if k in ("text", "quick") and hasattr(self, "tb_pull"): self.tb_pull(); self.co_pull()
    if k == "fx":
        for key, val in sc.FX["gameplay"].items():
            if key in self.fx: self.fx[key].set(bool(val))
        self.intensity.set("Normal"); self.accent.set("")
    if k == "captions" and hasattr(self, "cap_sample"): self.draw_sample()
    if k == "emotes": self.emote_summary()
    self.refresh_eta(); self.save(); self.status.set(f"The “{name}” tab is back to normal ✿")


# ================================================================ paste a link
@method
def paste_link(self):
    try: txt = self.clipboard_get().strip()
    except tk.TclError: txt = ""
    m = re.search(r"https?://\S+", txt)
    if not m or not A.site(m.group(0)):
        return self.status.set("The clipboard has no Kick / Twitch / YouTube link - copy one first ♡")
    self.v["url"].set(m.group(0).rstrip(".,;)")); self.status.set("Link pasted - downloading…")
    if not self.busy: self.download()


# ================================================================ start later
@method
def later_clicked(self):
    if self.later_id is not None: return self.later_cancel()
    if self.busy: return messagebox.showinfo("VTuber Clipper", "I'm busy right now. Set the timer after this job is finished ♡")
    w = tk.Toplevel(self); w.title("Start later ⏰"); w.configure(bg=self.t["bg"]); w.transient(self); A.center_over(w, self, 420, 230)
    ttk.Label(w, text="When should I start making this?", font=(A.FONT, 11, "bold")).pack(anchor="w", padx=16, pady=(14, 4))
    ttk.Label(w, text="Type minutes from now (for example 90), or a clock time like 23:30. I'll start by myself - leave this PC on (it won't go to sleep while waiting).",
              style="Mute.TLabel", wraplength=380, justify="left").pack(anchor="w", padx=16)
    sv = tk.StringVar(value="30"); e = ttk.Entry(w, textvariable=sv, width=12); e.pack(anchor="w", padx=16, pady=8); e.focus_set(); e.select_range(0, "end")
    note = tk.StringVar(); ttk.Label(w, textvariable=note, style="Mute.TLabel").pack(anchor="w", padx=16)

    def ok():
        s = parse_when(sv.get())
        if s is None: return note.set("I didn't understand that. Try 45 or 23:30.")
        w.destroy(); self.later_start(s)
    bf = ttk.Frame(w); bf.pack(anchor="w", padx=16, pady=10)
    ttk.Button(bf, text="⏰ Start then", style="Accent.TButton", command=ok).pack(side="left"); ttk.Button(bf, text="Cancel", command=w.destroy).pack(side="left", padx=8)
    w.bind("<Return>", lambda ev: ok()); w.bind("<Escape>", lambda ev: w.destroy())


def parse_when(txt, now=None):
    """'45' / '1.5h' / '90m' (minutes from now) or '23:30' / '9pm' (the next time the clock shows it) -> seconds from now; None when not understood."""
    s = str(txt or "").strip().lower().replace(" ", "")
    if not s: return None
    now = now or datetime.datetime.now()
    m = re.fullmatch(r"(\d+(?:\.\d+)?)(m|min|h|hr)?", s)
    if m:
        v = float(m.group(1)); v = v * 60 if m.group(2) in ("h", "hr") else v
        return int(v * 60) if 0 < v <= 24 * 60 else None
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?(am|pm)?", s)
    if m and (m.group(2) or m.group(3)):
        h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)
        if ap and not 1 <= h <= 12: return None
        if ap == "pm" and h < 12: h += 12
        if ap == "am" and h == 12: h = 0
        if h > 23 or mi > 59: return None
        t = now.replace(hour=h, minute=mi, second=0, microsecond=0)
        if t <= now: t += datetime.timedelta(days=1)
        return max(1, int((t - now).total_seconds()))
    return None


@method
def later_label(self, text=""):
    """The ⏰ button: just the clock when idle, the time that is left while a timer runs."""
    self.later_btn.configure(text="⏰" + (" " + text if text else ""), width=0 if text else 3)


@method
def later_start(self, secs):
    self.later_at = time.time() + secs; self.later_tries = 0
    self.set_awake_later(True)
    self.later_label(A.fmt(secs))
    self.later_tick()


@method
def set_awake_later(self, on):
    try: self.set_awake(on)
    except Exception: pass


@method
def later_tick(self):
    left = self.later_at - time.time()
    if left > 0:
        self.later_label(A.fmt(left)); self.status.set(f"Will start in {A.fmt(left)} - press the ⏰ button to cancel ✿")
        self.later_id = self.after(1000, self.later_tick); return
    if self.busy:
        self.later_tries += 1
        if self.later_tries > 120: return self.later_cancel()
        self.status.set("Waiting for the current job to finish before starting…"); self.later_id = self.after(5000, self.later_tick); return
    self.later_id = None; self.later_label(); self.set_awake_later(False)
    self.status.set("Starting now ✿"); self.make()


@method
def later_cancel(self):
    if self.later_id is not None:
        try: self.after_cancel(self.later_id)
        except Exception: pass
    self.later_id = None; self.later_label(); self.set_awake_later(False); self.status.set("Timer cancelled ✿")


# ================================================================ the Details log
@method
def log_save(self):
    p = filedialog.asksaveasfilename(title="Save the log", defaultextension=".txt", initialfile=f"VTuberClipper_log_{datetime.date.today().isoformat()}.txt", filetypes=[("Text", "*.txt")])
    if not p: return
    try:
        with open(p, "w", encoding="utf-8") as f: f.write(self.log.get("1.0", "end"))
        self.status.set("Log saved ✿")
    except OSError as e: messagebox.showerror("VTuber Clipper", f"I couldn't save the log: {e}")


@method
def log_copy(self):
    try: self.clipboard_clear(); self.clipboard_append(self.log.get("1.0", "end")); self.update(); self.status.set("Log copied - paste it into your message ✿")
    except tk.TclError: self.status.set("I couldn't reach the clipboard.")


@method
def log_clear(self):
    self.log.delete("1.0", "end")


# ================================================================ favourites + posted marks
def _norm(f): return os.path.normpath(str(f))


@method
def is_fav(self, f): return _norm(f) in self.marks["fav"]


@method
def toggle_fav(self, f):
    f = _norm(f); fv = self.marks["fav"]
    if f in fv: fv.remove(f)
    else: fv.append(f)
    self.save(); self.refresh_clips()


@method
def mark_posted(self, f, where):
    lst = self.marks["posted"].setdefault(_norm(f), [])
    if where not in lst: lst.append(where)
    self.save(); self.refresh_clips(); self.status.set(f"Marked as posted to {where} ✿")


@method
def clear_posted(self, f):
    self.marks["posted"].pop(_norm(f), None); self.save(); self.refresh_clips()


@method
def mark_text(self, f):
    p = self.marks["posted"].get(_norm(f))
    return ("✓ posted: " + ", ".join(p)) if p else ""


@method
def clip_files_shown(self):
    files = self.clip_files()
    if self.clip_fav_only.get(): files = [f for f in files if self.is_fav(f)]
    if self.clip_hide_posted.get(): files = [f for f in files if not self.marks["posted"].get(_norm(f))]
    return files


@method
def extra_files(self, f):
    """The extra files that exist next to a clip: [(label, path)]."""
    stem = os.path.splitext(f)[0]; names = (("_cover.jpg", "🖼 Cover picture"), ("_cover_b.jpg", "🖼 Cover picture B"), ("_cover_c.jpg", "🖼 Cover picture C"), (".gif", "🎞 GIF of the best moment"), (".mp3", "🎧 Sound only (MP3)"), (".m4a", "🎧 Sound only (M4A)"),
                                  ("_transcript.txt", "📜 Transcript"), (".vtt", "📜 Web subtitles (.vtt)"), (".srt", "📜 Subtitles (.srt)"), ("_posts.txt", "📝 Post texts for each platform"), ("_alt.txt", "♿ Alt text"), ("_check.txt", "✅ Clip check"), (".txt", "📝 Title ideas"))
    return [(lab, stem + e) for e, lab in names if os.path.isfile(stem + e)]


@method
def card_menu_extras(self, mn, f, t):
    """Added to the ⋯ More menu of a clip in My clips."""
    mn.add_separator()
    mn.add_command(label=("★  Remove from favourites" if self.is_fav(f) else "☆  Add to favourites"), command=lambda f=f: self.toggle_fav(f))
    pm = tk.Menu(mn, tearoff=0, bg=t["panel"], fg=t["fg"], activebackground=t["accent"], activeforeground=t["on"])
    for nm in POSTED_WHERE: pm.add_command(label=nm, command=lambda f=f, nm=nm: self.mark_posted(f, nm))
    pm.add_separator(); pm.add_command(label="Not posted yet", command=lambda f=f: self.clear_posted(f))
    mn.add_cascade(label="✓  Mark as posted to…", menu=pm)
    xs = [(lab, p) for lab, p in self.extra_files(f) if not lab.startswith(("📝",))]
    if xs:
        em = tk.Menu(mn, tearoff=0, bg=t["panel"], fg=t["fg"], activebackground=t["accent"], activeforeground=t["on"])
        for lab, p in xs: em.add_command(label=lab, command=lambda p=p: A.open_path(p))
        mn.add_cascade(label="📎  Open an extra file", menu=em)
    try: self.card_menu_extras21(mn, f, t)
    except Exception: pass


@method
def clip_filter_bar(self, hr):
    """Filters at the top of the My clips page."""
    fb = ttk.Frame(hr); fb.pack(side="left", padx=(14, 0))
    ttk.Checkbutton(fb, text="★ Favourites only", variable=self.clip_fav_only, command=self.refresh_clips).pack(side="left")
    ttk.Checkbutton(fb, text="Hide posted", variable=self.clip_hide_posted, command=self.refresh_clips).pack(side="left", padx=(8, 0))
    ttk.Button(fb, text="📊 Your numbers", command=self.show_stats).pack(side="left", padx=(10, 0))


# ================================================================ your numbers
@method
def show_stats(self):
    w = tk.Toplevel(self); w.title("Your numbers 📊"); w.configure(bg=self.t["bg"]); w.transient(self); A.center_over(w, self, 620, 520)
    ttk.Label(w, text="Your numbers", font=(A.FONT, 15, "bold"), foreground=self.t["accent"]).pack(anchor="w", padx=18, pady=(14, 2))
    note = tk.StringVar(value="Counting your clips…"); ttk.Label(w, textvariable=note, style="Mute.TLabel", wraplength=560, justify="left").pack(anchor="w", padx=18)
    body = ttk.Frame(w); body.pack(fill="both", expand=True, padx=18, pady=8)
    cv = tk.Canvas(w, height=170, highlightthickness=0, bg=self.t["panel"]); cv.pack(fill="x", padx=18, pady=(0, 8))
    ttk.Button(w, text="Close", command=w.destroy).pack(pady=(0, 12))
    files = self.clip_files(); sc = A.sc; now = time.time()

    def go():
        total, mins, size, weeks, best, favs, posted = 0, 0.0, 0.0, [0] * 8, (-1, ""), 0, 0
        cap = 400
        for i, f in enumerate(files):
            try: st = os.stat(f)
            except OSError: continue
            total += 1; size += st.st_size / 2 ** 20
            wk = int((now - st.st_mtime) // (7 * 86400))
            if 0 <= wk < 8: weeks[wk] += 1
            if self.is_fav(f): favs += 1
            if self.marks["posted"].get(_norm(f)): posted += 1
            k = self.kit_of(f)
            if k.get("hype") is not None and k["hype"] > best[0]: best = (k["hype"], os.path.basename(f))
            if i < cap:
                try: mins += (sc.probe_info(f)["dur"] or 0) / 60.0
                except Exception: pass
        self.ui(lambda: show(total, mins, size, weeks, best, favs, posted, len(files) > cap))

    def show(total, mins, size, weeks, best, favs, posted, capped):
        if not w.winfo_exists(): return
        if not total: note.set(f"Nothing to count yet - make some clips first ♡  (looking in {self.v['out'].get()})"); return
        note.set("Counted from the clips in your save folder.")
        rows = [("🎬 Clips", f"{total}"), ("⏱ Length of all clips", f"{int(mins)} minutes" + (" (first 400 measured)" if capped else "")), ("💾 Space used", A.fmt_size(size)),
                ("★ Favourites", f"{favs}"), ("✓ Marked as posted", f"{posted}  ·  {total - posted} still to post"),
                ("🔥 Highest hype score", f"{best[0]}  ({best[1]})" if best[0] >= 0 else "turn on “Save title ideas” to get hype scores")]
        for i, (a, b) in enumerate(rows):
            ttk.Label(body, text=a, font=(A.FONT, 10, "bold")).grid(row=i, column=0, sticky="w", pady=3); ttk.Label(body, text=b, wraplength=380, justify="left").grid(row=i, column=1, sticky="w", padx=14)
        W_, H_ = 580, 170; mx = max(weeks) or 1; bw = W_ / 8
        cv.delete("all"); cv.create_text(10, 10, text="Clips made per week (newest on the right)", anchor="w", fill=self.t["mute"], font=(A.FONT, 9))
        for i, n in enumerate(reversed(weeks)):
            h = int((H_ - 56) * n / mx); x0 = 14 + i * bw
            A.rrect(cv, x0, H_ - 26 - h, x0 + bw - 14, H_ - 26, 6, fill=self.t["accent"] if i == 7 else self.t["accent2"], outline="")
            cv.create_text(x0 + (bw - 14) / 2, H_ - 34 - h if n else H_ - 36, text=str(n), fill=self.t["fg"], font=(A.FONT, 9, "bold"))
            cv.create_text(x0 + (bw - 14) / 2, H_ - 12, text="this wk" if i == 7 else f"{7 - i}w ago", fill=self.t["mute"], font=(A.FONT, 8))
    threading.Thread(target=go, daemon=True).start()


# ================================================================ backup / restore
@method
def backup_settings(self):
    p = filedialog.asksaveasfilename(title="Back up my settings", defaultextension=".zip", initialfile=f"VTuberClipper_backup_{datetime.date.today().isoformat()}.zip", filetypes=[("Backup", "*.zip")])
    if not p: return
    self.save(); ve_ = A.EM(); n = 0
    try:
        with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("backup.json", json.dumps(dict(app="VTuberClipper", version=A.VERSION, when=datetime.datetime.now().isoformat(timespec="seconds"))))
            for src, name in ((A.CFG, "config.json"), (self.profiles_path(), "profiles.json"), (A.vp.USER_FILE, "presets.json"), (ve_.meta_path(), "emotes_meta.json")):
                if os.path.isfile(src): z.write(src, name); n += 1
            total = 0
            if os.path.isdir(ve_.USER_DIR):
                for f in sorted(os.listdir(ve_.USER_DIR)):
                    fp = os.path.join(ve_.USER_DIR, f)
                    if os.path.isfile(fp) and f.lower().endswith(ve_.EXT) and total + os.path.getsize(fp) < 150 * 2 ** 20:
                        z.write(fp, "emotes/" + f); total += os.path.getsize(fp); n += 1
        self.backup_note(f"Saved {n} files to {p}")
    except OSError as e: messagebox.showerror("VTuber Clipper", f"I couldn't write the backup: {e}")


@method
def backup_note(self, txt):
    if getattr(self, "tools_note", None) is not None: self.tools_note.set(txt)
    self.status.set(txt[:90])


@method
def restore_settings(self):
    if self.busy: return messagebox.showinfo("VTuber Clipper", "I'm busy making something. Restore after it is finished ♡")
    p = filedialog.askopenfilename(title="Restore my settings", filetypes=[("Backup", "*.zip")])
    if not p: return
    ve_ = A.EM()
    try:
        z = zipfile.ZipFile(p)
        info = json.loads(z.read("backup.json").decode("utf-8"))
        if info.get("app") != "VTuberClipper": raise ValueError("not a backup")
    except Exception:
        return messagebox.showerror("VTuber Clipper", "That file is not a VTuber Clipper backup.")
    if not messagebox.askyesno("VTuber Clipper", "Restore this backup?\n\nYour current settings, profiles, styles and emote list are replaced by the ones in the backup. "
                               "The app closes afterwards - open it again to load everything.", parent=self.sw if self.sw and self.sw.winfo_exists() else self): return
    try:
        names = z.namelist(); n = 0
        for name, dest in (("config.json", A.CFG), ("profiles.json", self.profiles_path()), ("presets.json", A.vp.USER_FILE), ("emotes_meta.json", ve_.meta_path())):
            if name in names:
                os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
                with open(dest, "wb") as f: f.write(z.read(name)); n += 1
        os.makedirs(ve_.USER_DIR, exist_ok=True)
        for name in names:
            if name.startswith("emotes/") and not name.endswith("/") and os.path.basename(name) == name[7:]:
                with open(os.path.join(ve_.USER_DIR, os.path.basename(name)), "wb") as f: f.write(z.read(name)); n += 1
    except OSError as e: return messagebox.showerror("VTuber Clipper", f"I couldn't restore everything: {e}")
    messagebox.showinfo("VTuber Clipper", f"Restored {n} files ♡\nThe app closes now. Open it again to load your settings.")
    self.skip_save = True; self.quit_app()


@method
def build_settings_tools(self, nb):
    t = ttk.Frame(nb, padding=14); nb.add(t, text="  🧰 Tools  ")
    ttk.Label(t, text="Back up and restore", font=(A.FONT, 11, "bold")).pack(anchor="w")
    self.autowrap(ttk.Label(t, text="Saves everything you set up into one file: settings, profiles, your own styles, your emote list and your own emote pictures. "
                            "Handy before you reinstall Windows or move to a new PC.", style="Mute.TLabel", justify="left"), t, 30).pack(anchor="w", pady=(2, 6))
    bf = ttk.Frame(t); bf.pack(anchor="w")
    ttk.Button(bf, text="📦 Back up my settings…", command=self.backup_settings).pack(side="left"); ttk.Button(bf, text="📥 Restore from a backup…", command=self.restore_settings).pack(side="left", padx=8)
    self.tools_note = tk.StringVar(); self.autowrap(ttk.Label(t, textvariable=self.tools_note, style="Mute.TLabel", justify="left"), t, 30).pack(anchor="w", pady=(6, 0))
    ttk.Label(t, text="Your clips", font=(A.FONT, 11, "bold")).pack(anchor="w", pady=(16, 2))
    cf = ttk.Frame(t); cf.pack(anchor="w")
    ttk.Button(cf, text="📊 Your numbers", command=self.show_stats).pack(side="left"); ttk.Button(cf, text="🖼 Open My clips", command=lambda: (self.mode.set("clips"), self.close_settings())).pack(side="left", padx=8)
    ttk.Label(t, text="The mascot", font=(A.FONT, 11, "bold")).pack(anchor="w", pady=(16, 2))
    ttk.Checkbutton(t, text="Let the mascot give me little tips while I work", variable=self.tips_on, command=self.save).pack(anchor="w")
    ttk.Label(t, text="The Details log", font=(A.FONT, 11, "bold")).pack(anchor="w", pady=(16, 2))
    lf = ttk.Frame(t); lf.pack(anchor="w")
    ttk.Button(lf, text="💾 Save the log…", command=self.log_save).pack(side="left"); ttk.Button(lf, text="📋 Copy the log", command=self.log_copy).pack(side="left", padx=8)


# ================================================================ mascot tips
@method
def ctx_tip(self):
    """A short tip about what the person is doing right now (or None). Changes every ~40 seconds, shown for ~12 seconds."""
    if not self.tips_on.get() or self.busy: return None
    k = self.frame // 570
    if self.frame % 570 > 170: return None
    tips = self.tips_now()
    return tips[k % len(tips)] if tips else None


@method
def tips_now(self):
    o, v, out = self.o, self.v, []
    have = os.path.isfile(v["video"].get().strip().strip('"'))
    mode = self.mode.get()
    if not have and mode in ("shorts", "long", "moments", "post", "twitter"): out.append("Drop a VOD on the window to begin ♡")
    if mode == "shorts":
        if have and A.sc.needs_cam(v["layout"].get(), {"custom_layout": o["custom_layout"].get()}) and not v["cam"].get(): out.append("Press 🪄 Find it for me to set your cam!")
        if o["platform"].get() == "any" and v["aspect"].get() == "9:16": out.append("Pick TikTok / Shorts in “Post on”: safe zones!")
        if not o["handle"].get().strip(): out.append("Add your @name in Quick setup to sign your clips")
        if not o["emotes"].get(): out.append("Try chibi emotes for story time (all options)")
        if o["color_look"].get() == "none": out.append("A colour look (Picture & voice) is cute ✿")
        if not o["lower_name"].get().strip(): out.append("Picture & voice has a name tag ♡")
    if mode == "clips":
        n = sum(1 for f in self.clip_files()[:60] if not self.marks["posted"].get(_norm(f)))
        if n: out.append(f"{n} clip{'s' if n != 1 else ''} not marked as posted yet ♡")
        out.append("Star ☆ your favourite clips to find them")
    if mode == "post": out.append("Copy titles with one click, then paste!")
    out = [t for t in out if len(t) <= TIPS_MAX]
    return out
