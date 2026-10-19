"""GUI tests for 2.3: the Privacy & checks tab, the new rows in the old tabs, the nine new Tools pages, snapshots, game memory, download options and the update screens."""
exec(open(__import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "h12.py")).read())
import tkinter as tk, re, types, threading, glob, datetime, json, zipfile, shutil
from tkinter import ttk
import vc20ui, vc21ui, vc22ui, vc23, vc23ui, vcnet, vcsafe, vcshare, vctools, vcmore, vcsmart, vcouts
_ve.STARTER_DIR = ""; _ve.USER_DIR = os.path.join(H, "VTuberClipper Emotes"); _ve.CACHE_DIR = os.path.join(H, "ecache")
ERR = []
_orig = app.App.report_callback_exception
def _rec(self, exc, val, tb):
    import traceback; ERR.append("".join(traceback.format_exception(exc, val, tb))); _orig(self, exc, val, tb)
app.App.report_callback_exception = _rec
FAILS = [0]
_ok = ok
def ok(c, m):
    if not c: FAILS[0] += 1
    _ok(c, m)
def walk(wd):
    yield wd
    for ch in wd.winfo_children(): yield from walk(ch)
def texts(wd): return [w.cget("text") for w in walk(wd) if w.winfo_class() in ("TCheckbutton", "TButton", "TLabel", "Label", "TMenubutton") and str(w.cget("text"))]
def has(wd, *parts): return any(all(p in t for p in parts) for t in texts(wd))
OPENED = []; app.open_path = lambda p: OPENED.append(p)
import webbrowser; WEB = []; webbrowser.open = lambda u, *a, **k: WEB.append(u)
ASK = {"file": "", "save": "", "dir": ""}
filedialog.askopenfilename = lambda *a, **k: ASK["file"]; filedialog.asksaveasfilename = lambda *a, **k: ASK["save"]; filedialog.askdirectory = lambda *a, **k: ASK["dir"]
OUT = os.path.join(H, "clips"); os.makedirs(OUT + "/Shorts", exist_ok=True)
def mkclip(n, d=5, kit=True, ledger=True, kind="reaction", vod=None, start=100.0, hype=77, sub="Shorts"):
    os.makedirs(f"{OUT}/{sub}", exist_ok=True)
    p = f"{OUT}/{sub}/{n}.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc=s=360x640:r=25:d={d}", "-f", "lavfi", "-i", f"sine=f=440:d={d}", "-shortest", "-pix_fmt", "yuv420p", p], check=True)
    if kit: open(f"{OUT}/{sub}/{n}.txt", "w", encoding="utf-8").write(f"HYPE SCORE  {hype}/100\n\nTITLE IDEAS\n  1. {n} the funniest title\n  2. other\n\nDESCRIPTION\ndesc of {n}\n\nHASHTAGS\n#vtuber #{n}\n")
    if ledger: vcmore.ledger_add(dict(path=p, vod=vod or "", start=start, end=start + d, kind=kind, conf=.8, hype=hype, dur=float(d), reasons=["a big laugh at the end"], titles=[f"{n} the funniest title"], look={}, extras=[], tags=[], note="", game="Minecraft", channel="MiaVT"))
    return p
VOD = paths.FIX + "/stream22.mp4"
CL = {n: mkclip(n, kind=k, vod=VOD, start=st, hype=h) for n, k, st, h in (("alpha", "reaction", 31.0, 90), ("alpha2", "reaction", 32.0, 60), ("bravo", "story", 80.0, 77), ("charlie", "gameplay", 140.0, 70))}

# ================================================================ start-up
A = mk(None); A.geometry("1280x900"); A.v["out"].set(OUT); pump(A, 1.5)
ok(app.VC23_ERR is None and app.VC22_ERR is None, "the 2.3 modules loaded without error (%s)" % (app.VC23_ERR or "")[-200:])
ok(app.VERSION == "2.3", "version 2.3")
ok(set(dict(app.SUBTABS)) == set(A.subs) == set(dict(vc21ui.SUBTABS)) and all(k in vc21ui.TAB_HELP for k, _ in app.SUBTABS), "every tab has a page and a description")
ok("safe" in dict(app.SUBTABS) and dict(app.SUBTABS)["safe"] == "Privacy & checks", "the tab is called Privacy & checks")
for k in vc23.DEFAULTS: assert k in A.o, k
ok(all(k in A.o for k in vc23.DEFAULTS), f"all {len(vc23.DEFAULTS)} new options have a variable")
d = A.opts_dict()
ok(d["privacy"] == "warn" and d["bg_blur"] == "normal" and d["bar_thick"] == 14 and d["logo_alpha"] == 92 and d["private_words"] == "" and d["flash_check"] is True and d["update_check"] is False, "defaults reach the engine")
ok(not ERR, "no errors so far " + (ERR[0][-300:] if ERR else ""))

# the 50 things: every one resolves and has a place in the window
import importlib
bad = []
for num, grp, key, title, fn in vc23.FEATURES:
    mod, _, name = fn.partition(".")
    try:
        if not callable(getattr(importlib.import_module(mod), name)): bad.append(num)
    except Exception: bad.append(num)
    if key is not None and key not in vc23.DEFAULTS: bad.append(f"{num}:{key}")
ok(len(vc23.FEATURES) == 50 and [f[0] for f in vc23.FEATURES] == list(range(1, 51)) and not bad, f"all 50 features are numbered 1-50 and each one's code can be found ({bad})")
# each true/false option has a check box somewhere in the window (main tabs or Settings)
A.open_settings(); pump(A, .6)
vars_seen = set()
for root in (A.subs, A.sw):
    for tab in (root.values() if isinstance(root, dict) else [root]):
        for w in walk(tab):
            if w.winfo_class() == "TCheckbutton":
                try: vars_seen.add(str(w.cget("variable")))
                except tk.TclError: pass
missing = [k for k in vc23.BOOLS if str(A.o[k]) not in vars_seen]
ok(not missing, f"every true/false 2.3 option has a check box ({missing})")
A.close_settings(); pump(A, .3)

# ================================================================ rows in the old tabs
A.simple.set(False); pump(A, .4)
ok([k for k, _ in A.subbar.items] == ["smart", "basics", "text", "fx", "captions", "emotes", "polish", "extras", "safe", "post"], "all options: ten tabs, Privacy & checks next to Posting & files")
A.sub.set("smart"); pump(A, .5); tx = texts(A.subs["smart"])
for need in ("🔎 More clues I listen for", "✂ Where a clip starts and ends"): ok(need in tx, f"Smart finding has: {need}")
for t_ in ("!clip and !highlight", "Firsts and milestones", "reads or answers chat", "Switching between two languages", "Rapid, excited", "Panic repeats", "Build-up", "Open on the action", "Clean ending", "Spread the clips", "Skip BRB"):
    ok(any(t_ in t for t in tx), f"Smart finding row: {t_}")
A.sub.set("polish"); pump(A, .4); tx = texts(A.subs["polish"])
for need in ("🌫 Background behind the game", "Blur", "Brightness", "🎙 Voice clean-up", "▬ Progress bar", "Edge", "Thickness"): ok(need in tx, f"Picture & voice has: {need}")
ok(any("Noise gate" in t for t in tx) and any("De-esser" in t for t in tx), "Picture & voice has the noise gate and the de-esser")
cb = [w.get() for w in walk(A.subs["polish"]) if w.winfo_class() == "TCombobox"]
ok("Normal" in cb and "Bottom edge" in cb, f"the drop-downs show friendly names ({cb[-4:]})")
A.sub.set("captions"); pump(A, .4); ok(has(A.subs["captions"], "Colour the feeling words"), "Captions has the feeling colours")
A.sub.set("extras"); pump(A, .4); tx = texts(A.subs["extras"]); ok("Logo opacity" in tx and any("Pick the song by the kind of moment" in t for t in tx), "Logo & music has the opacity and music by mood")
A.sub.set("post"); pump(A, .4); tx = texts(A.subs["post"])
for need in ("🎞 More in each clip file", "📝 Texts and pages", "🗂 Folders and memory", "Maybe if hype is under", "📑 Reports…", "✏ Rename clips…", "👯 Find duplicates…"): ok(need in tx, f"Posting & files has: {need}")
A.o["bg_blur"].set("strong"); A.o["bg_dim"].set("-20"); A.o["bar_pos"].set("top"); A.o["bar_thick"].set("20"); A.o["logo_alpha"].set("50"); A.o["maybe_below"].set("40")
for k in ("chat_cmds", "gate", "deess", "cap_feel", "soft_subs", "gif_clip", "report_html", "day_folder", "maybe_folder", "game_memory"): A.o[k].set(not vc23.DEFAULTS[k])
d = A.opts_dict()
ok((d["bg_blur"], d["bg_dim"], d["bar_pos"], d["bar_thick"], d["logo_alpha"], d["maybe_below"]) == ("strong", -20, "top", 20, 50, 40), "typed values reach the engine as numbers")
ok(d["gate"] and d["deess"] and d["cap_feel"] and d["soft_subs"] and d["gif_clip"] and d["report_html"] and d["day_folder"] and d["maybe_folder"] and d["game_memory"] and not d["chat_cmds"], "check boxes reach the engine")
A.o["bg_dim"].set("999"); A.o["bar_thick"].set("0"); A.o["logo_alpha"].set("5"); A.o["maybe_below"].set("500"); A.o["bg_blur"].set("nonsense"); A.o["bar_pos"].set("sideways"); d = A.opts_dict()
ok((d["bg_dim"], d["bar_thick"], d["logo_alpha"], d["maybe_below"], d["bg_blur"], d["bar_pos"]) == (50, 4, 20, 100, "normal", "bottom"), f"silly values are cleaned ({d['bg_dim']},{d['bar_thick']},{d['logo_alpha']},{d['maybe_below']},{d['bg_blur']},{d['bar_pos']})")
A.o["bg_dim"].set("abc"); ok(A.opts_dict()["bg_dim"] == 0, "text instead of a number falls back to the default")
# each tab's Reset puts its own 2.3 options back
for tab, keys in (("smart", vc23ui.SMART23), ("polish", vc23ui.POLISH23), ("captions", vc23ui.CAP23), ("extras", vc23ui.EXTRAS23), ("post", vc23ui.POST23)):
    for k in keys: A.o[k].set(("7" if k in vc23.INTS else not vc23.DEFAULTS[k]) if k not in ("bg_blur", "bar_pos") else ("extreme" if k == "bg_blur" else "top"))
    A.sub.set(tab); pump(A, .2); A.reset_tab(); pump(A, .3)
    left = [k for k in keys if str(A.o[k].get()) != str(vc23.DEFAULTS[k]) and A.o[k].get() != vc23.DEFAULTS[k]]
    ok(not left, f"Reset tab ({tab}) puts the 2.3 options back {left}")

# ================================================================ Privacy & checks tab
A.sub.set("safe"); pump(A, .5)
ok(A.subs["safe"].winfo_ismapped() and A.tab_help.get().startswith("The privacy guard"), "Privacy & checks opens with its description")
tx = texts(A.subs["safe"])
for need in ("🔒 Privacy guard", "🙈 My private words", "✅ Checks on every finished clip", "🔍 Scan a transcript…", "✅ Check a clip now…", "📸 Settings snapshots…"): ok(need in tx, f"Privacy & checks has: {need}")
ok(has(A.subs["safe"], "pattern check") and has(A.subs["safe"], "only read English"), "it says plainly that the guard is a pattern check for English phrases")
ok(any("Warn me" in w.get() for w in walk(A.subs["safe"]) if w.winfo_class() == "TCombobox"), "the privacy mode shows its friendly name")
ok(A.pw_note.get() == "No private words yet.", "no private words at first")
A.pw_text.insert("1.0", "Mia Tanaka, Sakura Town\nsunrise high"); A.pw_push(); pump(A, .2)
ok(A.o["private_words"].get() == "Mia Tanaka, Sakura Town\nsunrise high" and A.pw_note.get() == "3 private words saved", f"typing in the box sets the option ({A.pw_note.get()})")
ok(A.opts_dict()["private_words"] == "mia tanaka\nsakura town\nsunrise high", "the engine gets them cleaned, one per line, lower case")
A.o["private_words"].set("only this one"); pump(A, .2); ok(A.pw_text.get("1.0", "end").strip() == "only this one" and A.pw_note.get() == "1 private word saved", "changing the option from elsewhere updates the box")
A.o["private_words"].set("Mia Tanaka\nSakura Town"); A.o["privacy"].set("bleep"); A.o["flash_check"].set(False); A.o["preflight"].set(False); A.o["disk_guard"].set(False)
A.reset_tab(); pump(A, .3)
ok(A.o["privacy"].get() == "warn" and A.o["flash_check"].get() and A.o["preflight"].get() and A.o["disk_guard"].get() and A.o["private_words"].get() == "Mia Tanaka\nSakura Town", "Reset tab puts the checks back but keeps your private words")
# private words never travel in a look code or into a profile-less snapshot
A.copy_look_code(); code = A.clipboard_get(); nm, look = vctools.look_from_code(code)
ok("private_words" not in look["opts"] and "Mia Tanaka" not in code and "mia tanaka" not in json.dumps(look).lower(), "a shared look code does not hold the private words")
ok("private_words" not in A.snap_state()["opts"] and "chat_file" not in A.snap_state()["opts"], "snapshots do not store private words or per-video fields")
shot(A, "g23_safe")

# ================================================================ settings survive a restart
A.o["privacy"].set("bleep"); A.o["bg_blur"].set("soft"); A.o["gif_clip"].set(True); A.o["update_check"].set(True)
A.dl["dl_rate"].set("2M"); A.dl["dl_frags"].set("8"); A.dl["dl_cookie_file"].set(os.path.join(H, "cookies.txt")); A.dl["dl_from"].set("1:00:00"); A.dl["dl_to"].set("1:10:00"); A.save()
cfg = json.load(open(app.CFG))
ok(cfg["opts"]["privacy"] == "bleep" and cfg["opts"]["gif_clip"] is True and cfg["v23"]["dl_rate"] == "2M" and cfg["v23"]["dl_frags"] == "8", "2.3 options and download options are in the settings file")
ok("dl_from" not in cfg["v23"] and "dl_to" not in cfg["v23"], "the part-of-a-VOD times are not remembered (next download only)")
A.destroy(); A = mk(open(app.CFG).read()); A.geometry("1280x900"); A.v["out"].set(OUT); pump(A, 1.5)
ok(A.o["privacy"].get() == "bleep" and A.o["bg_blur"].get() == "soft" and A.o["gif_clip"].get() and A.o["update_check"].get() and A.dl["dl_rate"].get() == "2M" and A.dl["dl_frags"].get() == "8" and A.dl["dl_from"].get() == "", "the next start remembers them")
A.o["privacy"].set("warn"); A.o["bg_blur"].set("normal"); A.o["gif_clip"].set(False); A.o["update_check"].set(False); A.dl["dl_rate"].set(""); A.dl["dl_frags"].set("4"); A.dl["dl_cookie_file"].set(""); A.dl["dl_to"].set("")
A.o["private_words"].set(""); pump(A, .2)
# a settings file from 2.2 (without any of the new keys) loads with the defaults
old = json.load(open(app.CFG)); old["opts"] = {k: v for k, v in old["opts"].items() if k not in vc23.DEFAULTS}; old.pop("v23", None)
A.destroy(); A = mk(json.dumps(old)); A.geometry("1280x900"); A.v["out"].set(OUT); pump(A, 1.2)
d = A.opts_dict(); ok(d["privacy"] == "warn" and d["bg_blur"] == "normal" and A.dl["dl_frags"].get() == "4", "a 2.2 settings file loads with the new defaults")
# damaged values
dam = json.load(open(app.CFG)); dam["opts"].update(privacy=["x"], bg_dim={"a": 1}, bar_thick="wide", private_words=12345, gate="maybe"); dam["v23"] = {"dl_frags": [1], "dl_rate": {"x": 1}, "upd_last": 5}
A.destroy(); A = mk(json.dumps(dam)); A.geometry("1280x900"); A.v["out"].set(OUT); pump(A, 1.2)
d = A.opts_dict(); ok(d["privacy"] == "warn" and d["bg_dim"] == 0 and d["bar_thick"] == 14 and isinstance(d["private_words"], str), f"damaged values in the settings file are cleaned ({d['privacy']},{d['bg_dim']},{d['bar_thick']})")
A.o["private_words"].set(""); A.o["bar_thick"].set("14"); pump(A, .2)

# ================================================================ Tools window
A.open_toolbox(); pump(A, 1.0)
ok(list(A.tools_pages) == ["watch", "health", "clean", "space", "looks", "tags", "vocab", "sheet", "check", "dupes", "rename", "report", "chapters", "privacy", "snaps", "games", "updates"], f"Tools has seventeen pages {list(A.tools_pages)}")
ok(len(A.tools_groups) == 4 and len(A.tools_nb.tabs()) == 4, "in four groups, so the tab row fits")
fits = all(inner.winfo_reqwidth() < 820 for _, inner in A.tools_groups.values())
ok(fits, "each group's tab row is narrower than the window")
for k in A.tools_pages:
    A.open_toolbox(k); pump(A, .1)
    gk = next(g for g, t, pg in vc22ui.TOOL_GROUPS if any(p[0] == k for p in pg))
    ok(A.tools_nb.select() == str(A.tools_groups[gk][0]) and A.tools_groups[gk][1].select() == str(A.tools_pages[k]), f"page {k} can be opened by name")
ok(len([w for w in A.winfo_children() if isinstance(w, tk.Toplevel) and w.title().startswith("Tools")]) == 1, "still only one Tools window")
ok(not [w for w in A.tools_pages.values() if has(w, "could not be built")], "no page failed to build")
shot(A, "g23_tools")

# ---------------- privacy
srt = os.path.join(H, "talk.srt")
open(srt, "w", encoding="utf-8").write("1\n00:00:01,000 --> 00:00:04,000\nso my email is mia at example dot com ok\n\n2\n00:00:05,000 --> 00:00:08,000\nand I live in Sakura Town you know\n\n3\n00:00:09,000 --> 00:00:11,000\nthis boss is so hard\n")
A.o["private_words"].set("sakura town"); A.open_toolbox("privacy"); pump(A, .3)
A.pv_file.set(srt); A.pv_scan(); pump(A, .3); t = A.pv_out.get("1.0", "end")
ok("possible privacy hit" in t and "e-mail" in t.lower() and "0:00:02" in t and "private word" in t.lower(), f"the scan lists e-mail and the private word with times: {t[:160]!r}")
ok("boss is so hard" not in t, "and leaves normal talk alone")
open(srt + ".txt", "w").write("[0:00:05] we went shopping and it was great\n")
A.pv_file.set(srt + ".txt"); A.pv_scan(); pump(A, .2); ok("Nothing personal-looking" in A.pv_out.get("1.0", "end"), "a clean text file says nothing was found")
A.pv_file.set(os.path.join(H, "nope.srt")); A.pv_scan(); ok("can't find that file" in A.pv_out.get("1.0", "end"), "a missing file is explained")
open(srt + ".bad", "w").write("just some words without any times"); A.pv_file.set(srt + ".bad"); A.pv_scan(); ok("no timed words" in A.pv_out.get("1.0", "end"), "a file without times is explained")
A.pv_try.set("my email is mia at example dot com"); A.pv_test(); ok("***" in A.pv_res.get() and "Would become" in A.pv_res.get(), f"sentence test: {A.pv_res.get()}")
A.pv_try.set("I love this game so much"); A.pv_test(); ok(A.pv_res.get().startswith("Nothing private found"), "a normal sentence is left alone")
A.o["privacy"].set("off"); A.pv_try.set("my email is mia at example dot com"); A.pv_test(); ok("Would become" in A.pv_res.get(), "even with the guard off, the test page still shows what it would catch")
A.o["privacy"].set("warn")
# newest clip's subtitles
open(os.path.splitext(CL["alpha"])[0] + ".srt", "w").write("1\n00:00:00,000 --> 00:00:02,000\nhello\n")
os.utime(CL["alpha"], None); A.pv_file.set(""); A.pv_newest(); ok(A.pv_file.get().endswith(".srt"), "the newest clip's subtitle file can be picked")
A.sub.set("basics"); A.pv_words(); pump(A, .4); ok(A.sub.get() == "safe" and A.mode.get() == "shorts", "My private words button takes you to the tab")

# ---------------- clip check
A.open_toolbox("check"); pump(A, .3)
A.ck_newest(); ok(A.ck_path.get().endswith(".mp4") and os.path.isfile(A.ck_path.get()), "the newest clip can be picked")
A.ck_path.set(CL["bravo"]); A.ck_run([A.ck_path.get()]); t0 = time.time()
while A.ck_busy and time.time() - t0 < 120: pump(A, .3)
pump(A, .4); t = A.ck_out.get("1.0", "end")
ok("bravo.mp4" in t and "Length" in t and "Loudness" in t, f"the clip check shows its lines: {t[:200]!r}")
ok("failed" not in t, "and none of the checks failed to run")
A.ck_run([os.path.join(H, "missing.mp4")]); t0 = time.time()
while A.ck_busy and time.time() - t0 < 60: pump(A, .3)
pump(A, .3); ok("missing" in A.ck_out.get("1.0", "end"), "a missing file is reported")
A.ck_run([]); ok("Choose a clip first" in A.ck_out.get("1.0", "end"), "nothing chosen is explained")

# ---------------- duplicates
A.open_toolbox("dupes"); pump(A, .3); A.dp_run(); pump(A, .3)
items = A.dp_list.get(0, "end")
ok(any("Same moment #1" in i for i in items) and any("keep" in i and "alpha.mp4" in i for i in items) and any("weaker" in i and "alpha2.mp4" in i for i in items), f"duplicates are grouped, the better one is kept: {items}")
ok(not any("bravo" in i or "charlie" in i for i in items), "different moments are left out")
ok(A.dp_list.curselection() == (items.index([i for i in items if "alpha2" in i][0]),), "only the weaker clip is selected")
A.dp_move(); pump(A, .5)
moved = os.path.join(OUT, "Shorts", "Duplicates", "alpha2.mp4")
ok(os.path.isfile(moved) and os.path.isfile(moved[:-4] + ".txt") and not os.path.exists(CL["alpha2"]) and os.path.isfile(CL["alpha"]), "the weaker clip (and its title file) moved to a Duplicates folder, the better one stayed")
ok((vcmore.ledger_find(moved) or {}).get("hype") == 60, "the clip ledger follows the move")
A.dp_run(); ok("No duplicates" in A.dp_sum.get(), "and now there are none")
A.dp_move(); ok("Select the clips" in A.dp_sum.get(), "moving with nothing selected is explained")

# ---------------- rename
A.open_toolbox("rename"); pump(A, .3)
ok(A.rn_list.size() >= 3, f"the clips are listed ({A.rn_list.size()})")
A.rn_pat.set("{date} {type} {score} clip {n}"); A.rn_list.selection_set(0, "end"); A.rn_preview(); pump(A, .2)
ok(A.rn_plan and "would be renamed" in A.rn_sum.get() and "→" in A.rn_prev.get("1.0", "end"), f"the preview shows old and new names: {A.rn_sum.get()}")
today = datetime.date.today().isoformat()
A.rn_apply(); pump(A, .5)
ok(all(os.path.exists(new) and not os.path.exists(old) for old, new in []) and "Renamed" in A.rn_sum.get(), f"renamed: {A.rn_sum.get()}")
names = sorted(os.path.basename(f) for f in glob.glob(OUT + "/Shorts/*.mp4"))
ok(names and all(n.startswith(today) for n in names), f"new names follow the pattern {names}")
ok(all(os.path.isfile(f[:-4] + ".txt") for f in glob.glob(OUT + "/Shorts/*.mp4")), "the title files were renamed with their clips")
ok(all(os.path.isfile(e["path"]) for e in vcmore.ledger_all() if e["path"].startswith(OUT) and not e.get("deleted")), "the clip ledger points at the new names")
A.rn_pat.set("{date} {type} {score} clip {n}"); A.rn_preview(); ok("stay as they are" in A.rn_sum.get() or "would be renamed" in A.rn_sum.get(), "running it again does not break anything")
A.rn_pat.set("???"); A.rn_files = []; A.rn_list.delete(0, "end"); A.rn_preview(); ok("no clips" in A.rn_sum.get(), "no clips is explained")
A.v["out"].set(OUT)

# ---------------- reports
CL = {}
for f in glob.glob(OUT + "/Shorts/*.mp4"):
    e = vcmore.ledger_find(f); CL[os.path.basename(f)] = f
A.open_toolbox("report"); A.rp_refresh(); pump(A, .3)
ok(len(A.rp_vods) == 1 and A.rp_vod.get().startswith("stream22.mp4"), f"the streams with clips are listed: {list(A.rp_vods)}")
A.rp_html(); pump(A, .3)
rep = glob.glob(OUT + "/*_highlights.html")
ok(rep and OPENED and OPENED[-1] == rep[0], "the highlights page is written and opened")
html = open(rep[0], encoding="utf-8").read(); ok("<h1>Highlights from stream22" in html and html.count("<article>") == len(A.rp_vods[A.rp_vod.get()]) and "Shorts/" in html, "it lists the clips with links relative to the save folder")
A.rp_text("stamps"); t = A.rp_out.get("1.0", "end"); ok(re.match(r"\s*0:00 ", t) and len(t.strip().splitlines()) >= 2, f"timestamps start at 0:00: {t[:80]!r}")
A.rp_text("discord"); ok("**Clips from stream22" in A.rp_out.get("1.0", "end"), "Discord message")
A.rp_text("x"); t = A.rp_out.get("1.0", "end"); ok("1/" in t and all(len(x) <= 280 for x in t.split("\n\n")), "X thread, each post within 280")
A.clipboard_clear(); A.rp_copy(); ok(A.clipboard_get().strip() == A.rp_out.get("1.0", "end").strip(), "the text can be copied")
A.rp_vod.set(""); A.rp_text("stamps"); ok("Pick a stream first" in A.rp_out.get("1.0", "end"), "no stream chosen is explained")

# ---------------- chapters
meta = os.path.join(H, "chap.txt")
open(meta, "w").write(";FFMETADATA1\ntitle=x\n[CHAPTER]\nTIMEBASE=1/1000\nSTART=0\nEND=2000\ntitle=Intro\n[CHAPTER]\nTIMEBASE=1/1000\nSTART=2000\nEND=4800\ntitle=Boss fight\n")
CHV = os.path.join(H, "withchapters.mp4")
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", CL[sorted(CL)[0]], "-i", meta, "-map", "0", "-map_metadata", "1", "-map_chapters", "1", "-c", "copy", CHV], check=True)
A.open_toolbox("chapters"); pump(A, .3)
A.v["video"].set(""); A.ch_read(); ok("Choose a video" in A.ch_sum.get(), "no video loaded is explained")
A.v["video"].set(CHV); A.ch_read(); t0 = time.time()
while len(A.ch_rows) < 2 and time.time() - t0 < 30: pump(A, .3)
pump(A, .3); ok(len(A.ch_rows) == 2 and "2 chapters found" in A.ch_sum.get() and "Boss fight" in A.ch_list.get(1), f"chapters are read from the file: {A.ch_list.get(0, 'end')}")
A.ch_list.selection_set(1); A.ch_use(); ok(A.o["range_from"].get() == "0:02" and A.o["range_to"].get() == "0:04", f"a chapter sets the time range ({A.o['range_from'].get()}-{A.o['range_to'].get()})")
pump(A, .2); ok("Looking" in A.range_note.get(), "and the Smart finding tab explains the range")
A.o["range_from"].set(""); A.o["range_to"].set("")
A.ch_list.selection_clear(0, "end"); A.ch_use(); ok("Select a chapter" in A.ch_sum.get(), "using with nothing selected is explained")
A.clipboard_clear(); A.ch_copy(); ok("0:00 Intro" in A.clipboard_get() and "0:02 Boss fight" in A.clipboard_get(), "chapters copy as timestamps")
A.v["video"].set(CL[sorted(CL)[0]]); A.ch_read(); t0 = time.time()
while "Reading" in A.ch_sum.get() and time.time() - t0 < 30: pump(A, .3)
pump(A, .3); ok("no chapters" in A.ch_sum.get(), "a video without chapters is explained")
A.v["video"].set("")

# ---------------- snapshots
shutil.rmtree(vcshare.SNAP_DIR, ignore_errors=True)
A.open_toolbox("snaps"); pump(A, .3); ok("No snapshots yet" in A.sn_sum.get(), "no snapshots at first")
first = A.o["bg_blur"].get(); A.o["bg_blur"].set("strong"); A.o["private_words"].set("secret one")
A.sn_label.set("strong blur"); A.sn_save(); pump(A, .2); ok(len(A.sn_rows) == 1 and A.sn_rows[0]["label"] == "strong blur", "a snapshot is saved by hand")
A.sn_save(); ok("same as the newest" in A.sn_sum.get() and len(A.sn_rows) == 1, "an identical one is not saved twice")
A.o["bg_blur"].set("soft"); A.o["bar_thick"].set("30"); A.o["private_words"].set("another secret")
A.sn_list.selection_set(0); A.sn_show(); t = A.sn_diff.get("1.0", "end")
ok("2 settings would change" in t and "bg_blur" in t and "bar_thick" in t and "private" not in t.lower(), f"the difference is listed: {t[:200]!r}")
A.sn_restore(); pump(A, .5)
ok(A.o["bg_blur"].get() == "strong" and A.o["bar_thick"].get() == "14" and A.o["private_words"].get() == "another secret", "going back restores the settings but not the private words")
ok(len(A.sn_rows) == 2 and A.sn_rows[0]["label"] == "Before going back", "the settings from before are kept first, so going back can be undone")
n0 = len(vcshare.snapshot_list()); A.o["bg_blur"].set("extreme"); A.hook22("start", "shorts"); ok(len(vcshare.snapshot_list()) == n0 + 1, "a snapshot is kept every time a job starts")
A.hook22("start", "shorts"); ok(len(vcshare.snapshot_list()) == n0 + 1, "but not again when nothing changed")
A.hook22("start", "download"); A.o["bg_blur"].set("soft"); A.hook22("start", "moments"); ok(len(vcshare.snapshot_list()) == n0 + 1, "and not for jobs that make no videos")
for i in range(15): A.o["bar_thick"].set(str(10 + i)); A.snap_auto()
ok(len(vcshare.snapshot_list()) <= 12, "no more than 12 are kept")
A.sn_refresh(); A.sn_list.selection_set(0); A.sn_delete(); pump(A, .2); ok(len(A.sn_rows) == len(vcshare.snapshot_list()), "a snapshot can be removed")
A.o["bg_blur"].set("normal"); A.o["bar_thick"].set("14"); A.o["private_words"].set("")
A.busy = True; A.sn_list.selection_set(0); A.sn_restore(); ok("busy" in A.sn_sum.get(), "no going back while a job runs"); A.busy = False
with open(os.path.join(vcshare.SNAP_DIR, "20990101-000000.json"), "w") as fh: fh.write("{ not json")
A.sn_refresh(); ok(True, "a damaged snapshot file does not break the list")

# ---------------- games
shutil.rmtree(os.path.join(H, ".vtuberclipper_tools.json"), ignore_errors=True) if os.path.isdir(os.path.join(H, ".vtuberclipper_tools.json")) else None
vctools.store_put("game_prefs", {})
A.open_toolbox("games"); pump(A, .3); ok("Nothing remembered yet" in A.gm_sum.get(), "nothing remembered at first")
vcshare.game_put("Minecraft", dict(n=3, len_min=20, len_max=40, style="story", layout="stack")); vcshare.game_put("Elden Ring", dict(n=12, len_min=30, len_max=60, style="gameplay", layout="blur"))
A.gm_refresh(); ok(A.gm_list.size() == 2 and "elden ring" in A.gm_list.get(0) and "12 clips" in A.gm_list.get(0), f"remembered games are listed: {A.gm_list.get(0, 'end')}")
A.o["game_memory"].set(False); A.v["n"].set("8"); A.o["game"].set("Minecraft"); pump(A, 1.5); ok(A.v["n"].get() == "8", "with the option off nothing is filled in")
A.o["game_memory"].set(True); A.o["game"].set(""); pump(A, .2); A.o["game"].set("minecraft"); pump(A, 1.6)
ok((A.v["n"].get(), A.v["lmin"].get(), A.v["lmax"].get(), A.v["style"].get(), A.v["layout"].get()) == ("3", "20", "40", "story", "stack") and "Filled in" in A.status.get(), f"naming the game fills in what was remembered ({A.v['n'].get()}, {A.v['lmin'].get()}-{A.v['lmax'].get()}, {A.v['style'].get()}) / {A.status.get()}")
A.v["n"].set("5"); A.o["game"].set("Some New Game"); pump(A, 1.5); ok(A.v["n"].get() == "5", "an unknown game changes nothing")
A.gm_list.selection_set(0); A.gm_use(); ok(A.v["n"].get() == "12" and "Filled in" in A.gm_sum.get(), "the page can apply a game's settings now")
vctools.store_put("game_prefs", {"bad": dict(n="lots", len_min=500, len_max=1, style="nope", layout="nope")}); A.v["n"].set("5")
ok(A.game_apply(vcshare.game_get("bad"), "bad") == "" and A.v["n"].get() == "5", "damaged remembered values are ignored")
A.gm_refresh(); A.gm_list.selection_set(0); A.gm_forget(); ok(A.gm_list.size() == 0, "a game can be forgotten")
A.o["game_memory"].set(False); A.o["game"].set("")

# ================================================================ downloads
A.open_settings("downloads"); pump(A, .6)
tx = texts(A.sw)
for need in ("More download options", "Speed limit", "Pieces at once", "Cookies file", "Only this part"): ok(need in tx, f"Settings -> Downloads has: {need}")
A.dl["dl_from"].set("1:00:00"); A.dl["dl_to"].set("1:10:00"); A.dl["dl_rate"].set("2M"); pump(A, .2)
ok("Downloading only 1:00:00 to 1:10:00" in A.dl_note.get() and "Speed limit 2M" in A.dl_note.get(), f"the options are explained as you type: {A.dl_note.get()}")
A.dl["dl_rate"].set("fast"); A.dl["dl_to"].set("0:30:00"); pump(A, .2); ok("not understood" in A.dl_note.get() and "later" in A.dl_note.get(), f"mistakes are explained: {A.dl_note.get()}")
A.close_settings()
CMD = []
A.run_cmd = lambda cmd: (CMD.append(list(cmd)), (0, "ok"))[1]
dl = dict(dl_from="1:02:30", dl_to="1:10:00", dl_rate="2M", dl_frags="8", dl_cookie_file="")
okk, _ = A.try_download("https://kick.com/x/videos/1", "kick", OUT, "bv*+ba/b", "chrome", dl); c = CMD[0]
ok(okk and c[c.index("--download-sections") + 1] == "*1:02:30-1:10:00" and c[c.index("--limit-rate") + 1] == "2M" and c[c.index("--concurrent-fragments") + 1] == "8" and c.count("--concurrent-fragments") == 1, f"part, speed limit and pieces reach yt-dlp: {c[8:]}")
ok("part 1.02.30-1.10.00.%(ext)s" in c[c.index("-o") + 1] and "--cookies-from-browser" in c and "--impersonate" in c, "the file name says which part it is; the browser cookies are still used")
ck = os.path.join(H, "cookies.txt"); open(ck, "w").write("# Netscape HTTP Cookie File\n.kick.com\tTRUE\t/\tTRUE\t0\tname\tvalue\n")
CMD.clear(); A.try_download("https://www.twitch.tv/videos/1", "twitch", OUT, "bv*+ba/b", "chrome", dict(dl_cookie_file=ck, dl_frags="4")); c = CMD[0]
ok("--cookies" in c and "--cookies-from-browser" not in c and "--download-sections" not in c and "part" not in c[c.index("-o") + 1], "a cookies file replaces the browser cookies; no part = a normal file name")
CMD.clear(); A.try_download("https://www.twitch.tv/videos/1", "twitch", OUT, "bv*+ba/b", "none", None); c = CMD[0]
ok("--concurrent-fragments" in c and c[c.index("--concurrent-fragments") + 1] == "4" and "--limit-rate" not in c, "with no extra options the command is the 2.2 one")
CMD.clear(); A.try_download("https://www.twitch.tv/videos/1", "twitch", OUT, "bv*+ba/b", "none", dict(dl_from="abc", dl_to="", dl_rate="junk", dl_frags="99", dl_cookie_file="/nope/x.txt")); c = CMD[0]
ok("--download-sections" not in c and "--limit-rate" not in c and c[c.index("--concurrent-fragments") + 1] == "16" and "--cookies" not in c, "unusable options are left out, not passed on")
# a part is for one download only: it is cleared once the file arrived
os.makedirs(OUT + "/VODs", exist_ok=True); open(OUT + "/VODs/got.mp4", "wb").write(b"x" * 100)
A.try_download = lambda *a, **k: (True, "")
A.v["url"].set("https://kick.com/x/videos/1"); A.dl["dl_from"].set("5:00"); A.dl["dl_to"].set("6:00"); A.download(); t0 = time.time()
while (A.busy or time.time() - t0 < 1.0) and time.time() - t0 < 30: pump(A, .3)
pump(A, .5); ok(A.dl["dl_from"].get() == "" and A.dl["dl_to"].get() == "" and A.v["video"].get().endswith("got.mp4"), "after the download the from / to boxes are empty again and the video is loaded")
del A.try_download
A.dl_part_dialog(); pump(A, .4)
dlg = [w for w in A.winfo_children() if isinstance(w, tk.Toplevel) and w.title().startswith("Download only a part")]
ok(len(dlg) == 1, "the scissors button opens the 'only a part' box"); dlg[0].destroy()
ok(any(w.winfo_class() == "TButton" and w.cget("text") == "✂" for w in walk(A)), "there is a scissors button next to the download button")

# ================================================================ updates
FAKE = {"tag_name": "v0.2.4-beta", "name": "VTuber Clipper 2.4 beta", "prerelease": True, "html_url": "https://github.com/vtuberemma/vtuber-clipper/releases/tag/v0.2.4-beta", "body": "Bigger things.",
        "assets": [{"name": "VTuberClipper_update_2.4_beta.zip", "browser_download_url": "https://github.com/vtuberemma/vtuber-clipper/releases/download/v0.2.4-beta/VTuberClipper_update_2.4_beta.zip", "size": 1234}]}
CALLS = []
def fake_fetch(url, timeout=8):
    CALLS.append(url); return json.dumps(FAKE).encode()
vcnet.default_fetch = fake_fetch
A.open_toolbox("updates"); pump(A, .3)
ok(has(A.tools_pages["updates"], "Check now") and has(A.tools_pages["updates"], "Undo the last update") and has(A.tools_pages["updates"], "Install a zip I have"), "the Updates page has check, install-from-zip and undo")
ok("disabled" in A.upd_install_btn.state(), "Download and install is greyed out until a check finds something")
A.upd_check(True); t0 = time.time()
while A.upd_busy and time.time() - t0 < 20: pump(A, .2)
pump(A, .3); ok(A.upd_info and A.upd_info["status"] == "newer" and "newer version" in A.upd_note.get() and CALLS and "api.github.com" in CALLS[0], f"a newer version is found: {A.upd_note.get()}")
ok("disabled" not in A.upd_install_btn.state(), "and the install button is now available")
ok("Bigger things." in A.upd_out.get("1.0", "end"), "the release notes are shown")
ok(A.upd_last == datetime.date.today().isoformat(), "the day of the check is remembered")
FAKE["tag_name"] = "v0.2.3-beta"; FAKE["name"] = "VTuber Clipper 2.3 beta"; A.upd_check(True); t0 = time.time()
while A.upd_busy and time.time() - t0 < 20: pump(A, .2)
pump(A, .3); ok(A.upd_info["status"] == "same" and "newest version" in A.upd_note.get() and "disabled" in A.upd_install_btn.state(), f"the same version says so: {A.upd_note.get()}")
vcnet.default_fetch = lambda url, timeout=8: (_ for _ in ()).throw(OSError("no connection"))
A.upd_check(True); t0 = time.time()
while A.upd_busy and time.time() - t0 < 20: pump(A, .2)
pump(A, .3); ok(A.upd_info["status"] == "error" and "Could not check" in A.upd_note.get(), "no connection is explained, nothing crashes")
# the daily check
vcnet.default_fetch = fake_fetch; FAKE["tag_name"] = "v0.2.4-beta"; FAKE["name"] = "VTuber Clipper 2.4 beta"; CALLS.clear()
A.o["update_check"].set(False); A.upd_last = ""; A.upd_auto(); pump(A, .5); ok(not CALLS, "the daily check does nothing when it is switched off")
A.o["update_check"].set(True); A.upd_auto(); t0 = time.time()
while (A.upd_busy or not CALLS) and time.time() - t0 < 20: pump(A, .2)
pump(A, .5); ok(len(CALLS) == 1 and "newer" in A.upd_note.get() and "newer version is out" in A.status.get(), "switched on, it checks once and says so in the status line")
A.upd_auto(); pump(A, .5); ok(len(CALLS) == 1, "and not a second time the same day")
A.o["update_check"].set(False)
# install into a pretend install folder
INST = os.path.join(H, "inst"); os.makedirs(INST + "/app/fonts"); open(INST + "/app/streamclip_app.py", "w").write('VERSION = "2.3"\nBETA = True\n'); open(INST + "/app/old.py", "w").write("x = 1\n"); open(INST + "/app/fonts/mine.ttf", "w").write("font")
vc23ui._install_root = lambda: INST
ZIP = os.path.join(H, "upd24.zip")
with zipfile.ZipFile(ZIP, "w") as z:
    z.writestr("app/streamclip_app.py", 'VERSION = "2.4"\nBETA = True\n'); z.writestr("app/new.py", "y = 2\n"); z.writestr("README.txt", "hi")
vcnet.download_update = lambda info, dest, **k: ZIP
MSG.clear(); A.upd_install(); t0 = time.time()
while A.upd_busy and time.time() - t0 < 30: pump(A, .2)
pump(A, .5)
ok(open(INST + "/app/streamclip_app.py").read().startswith('VERSION = "2.4"') and os.path.isfile(INST + "/app/new.py") and open(INST + "/app/fonts/mine.ttf").read() == "font" and "Updated to 2.4" in A.upd_note.get(), f"the update is installed, your fonts are untouched: {A.upd_note.get()}")
ok(any(m[0] == "info" and "Updated" in str(m[1]) for m in MSG), "and you are told to restart")
ok(vcnet.list_backups(INST) and "update to 2.4" in A.upd_out.get("1.0", "end"), "the backup is listed on the page")
A.upd_undo(); pump(A, .3)
ok(open(INST + "/app/streamclip_app.py").read().startswith('VERSION = "2.3"') and not os.path.exists(INST + "/app/new.py") and "Went back" in A.upd_note.get(), f"undo puts the old files back: {A.upd_note.get()}")
A.upd_undo(); ok("no update to undo" in A.upd_note.get().lower(), "undoing twice is explained")
ASK["file"] = ZIP; A.upd_from_zip(); t0 = time.time()
while A.upd_busy and time.time() - t0 < 30: pump(A, .2)
pump(A, .4); ok(open(INST + "/app/streamclip_app.py").read().startswith('VERSION = "2.4"'), "an update zip you already have can be installed")
A.upd_undo()
bad = os.path.join(H, "bad.zip")
with zipfile.ZipFile(bad, "w") as z: z.writestr("app/streamclip_app.py", 'VERSION = "9"\n'); z.writestr("../evil.py", "x"); z.writestr("app/boom.py", "def (:\n")
ASK["file"] = bad; A.upd_from_zip(); pump(A, .3); ok("can't be installed" in A.upd_note.get() and not os.path.exists(os.path.join(H, "evil.py")), f"a bad zip is refused: {A.upd_note.get()[:90]}")
ASK["file"] = os.path.join(H, "nothing.zip"); A.upd_from_zip(); ok("can't be installed" in A.upd_note.get() or "not a readable" in A.upd_note.get().lower(), "a missing zip is refused")
A.busy = True; A.upd_install(); ok("busy" in A.upd_note.get(), "no installing while a job runs"); A.busy = False
A.upd_info = None; A.upd_install(); ok("Check now first" in A.upd_note.get(), "installing before checking is explained")
A.upd_page(); ok(WEB and WEB[-1].startswith("https://github.com/vtuberemma/vtuber-clipper/releases"), "the release page button opens GitHub")
A.open_settings("about"); pump(A, .5)
ok(has(A.sw, "Check for updates") and has(A.sw, "Install or undo an update") and has(A.sw, "Check once a day"), "Settings -> About has the update buttons")
A.close_settings()

# ================================================================ themes and odd moments
A.open_toolbox("dupes"); pump(A, .3); lb = A.dp_list
th = [k for k in app.THEMES if k != A.v["theme"].get()][0]; A.v["theme"].set(th); A.apply_theme(); pump(A, .4)
ok(lb.cget("bg") == A.t["entry"], "a theme change reaches the lists in open Tools pages")
ok(A.pw_text.cget("bg") == A.t["entry"], "and the private-words box in the main window")
A.tools_win.destroy(); pump(A, .2); A.open_toolbox("games"); pump(A, .3); ok(A.tools_win.winfo_exists(), "Tools can be closed and opened again")
for k in list(A.tools_pages): A.open_toolbox(k); pump(A, .05)
A.v["out"].set(os.path.join(H, "does", "not", "exist")); A.open_toolbox("rename"); A.open_toolbox("report"); A.open_toolbox("dupes"); A.dp_run(); A.rp_refresh(); pump(A, .5)
A.v["out"].set(OUT)
ok(not ERR, "no error was raised in any window callback " + (ERR[0][-500:] if ERR else ""))
print(f"FAILS: {FAILS[0]}")
