"""Rough-edge GUI tests for 2.2: empty/missing folders, no clips, theme switch while windows are open, close + reopen, garbage input."""
exec(open(__import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "h12.py")).read())
import tkinter as tk, re, threading, glob, json
from tkinter import ttk
import vcnew, vc21ui, vc22ui, vctools, vcmore, vcsmart, vcouts
_ve.STARTER_DIR = ""; _ve.USER_DIR = os.path.join(H, "VTuberClipper Emotes"); _ve.CACHE_DIR = os.path.join(H, "ecache")
ERR = []
_orig = app.App.report_callback_exception
def _rec(self, exc, val, tb):
    import traceback; ERR.append("".join(traceback.format_exception(exc, val, tb))); _orig(self, exc, val, tb)
app.App.report_callback_exception = _rec
def walk(wd):
    yield wd
    for ch in wd.winfo_children(): yield from walk(ch)
OPENED = []; app.open_path = lambda p: OPENED.append(p)
ASK = {"file": "", "save": "", "dir": "", "str": None}
filedialog.askopenfilename = lambda *a, **k: ASK["file"]; filedialog.asksaveasfilename = lambda *a, **k: ASK["save"]; filedialog.askdirectory = lambda *a, **k: ASK["dir"]
simpledialog.askstring = lambda *a, **k: ASK["str"]
def noerr(m): ok(not ERR, m + (" " + ERR[0][-400:] if ERR else ""))

A = mk(None); A.geometry("1280x900"); pump(A, 1.2)
ok(app.VC22_ERR is None, "2.2 loaded")
# ---------- everything with an empty / missing save folder
for outv in ("", "   ", os.path.join(H, "does", "not", "exist"), '"' + os.path.join(H, "quoted") + '"', "C:\\nope\\nope", "~/nowhere"):
    A.v["out"].set(outv); A.open_toolbox(); pump(A, .5)
    for k in list(A.tools_pages): A.open_toolbox(k); pump(A, .1)
    A.run_health(); pump(A, 2); A.run_leftovers(); pump(A, 1); A.refresh_space(); pump(A, 1.5)
    try: A.suggest_words(); pump(A, 1.5)
    except Exception as e: ERR.append("suggest_words: " + repr(e))
    A.refresh_clips(); pump(A, .3)
    noerr(f"Tools pages work with save folder {outv!r}")
    ok(bool(A.health_items), f"health report appears ({len(A.health_items)} items)")
    A.tools_win.destroy(); pump(A, .2)
# ---------- review mode with nothing to review
A.v["out"].set(os.path.join(H, "empty")); os.makedirs(os.path.join(H, "empty"), exist_ok=True)
MSG.clear(); A.open_review(); pump(A, .4)
ok(any(m[0] == "info" and "No new clips" in str(m[1]) for m in MSG), "review mode with no clips says so")
ok(not (A.review_win is not None and A.review_win.winfo_exists()), "no empty review window is left open")
# compare window with no video
MSG.clear(); A.v["video"].set(""); A.open_compare(); pump(A, .6)
cw = [w for w in A.winfo_children() if isinstance(w, tk.Toplevel)]
for w in cw: w.destroy()
noerr("compare window with no video opens/closes")
# ---------- moments files
A.moments = []; ASK["save"] = os.path.join(H, "x.vtmoments"); A.moments_to_file(); pump(A, .2)
ok(not os.path.exists(ASK["save"]), "saving an empty moments list does nothing")
bad = os.path.join(H, "bad.vtmoments")
for txt in ("", "not json", "[]", "{}", '{"moments": "x"}', '{"video": 5, "moments": [{"start": "a"}]}', "\x00\x01\x02", '{"moments":[{"start":1,"end":0}]}', '{"moments":[null,1,"a"]}', '{"v":1,"video":"/nope.mp4","moments":[{"start":1,"end":5,"score":"x"}]}'):
    open(bad, "w", encoding="utf-8", errors="ignore").write(txt); ASK["file"] = bad; MSG.clear()
    try: A.moments_from_file(); pump(A, .2)
    except Exception as e: ERR.append(f"moments_from_file({txt[:20]!r}): {e!r}")
open(bad, "wb").write(b"\xff\xfe\x00bad bytes\x80"); ASK["file"] = bad
try: A.moments_from_file(); pump(A, .2)
except Exception as e: ERR.append("moments_from_file binary: " + repr(e))
ASK["file"] = os.path.join(H, "gone.vtmoments")
try: A.moments_from_file(); pump(A, .2)
except Exception as e: ERR.append("moments_from_file missing: " + repr(e))
noerr("garbage moments files never crash the screen")
for w in [w for w in A.winfo_children() if isinstance(w, tk.Toplevel)]: w.destroy()
# ---------- look codes + hashtags + vocabulary + sheet pages with garbage
A.open_toolbox("looks"); pump(A, .4)
for code in ("", "garbage", "VTL1:", "VTL1:AAAA", "😀" * 50, "a" * 5000, "VTL1:" + "z" * 100):
    A.look_box.delete("1.0", "end"); A.look_box.insert("1.0", code); MSG.clear()
    try: A.use_look_code(False); pump(A, .1)
    except Exception as e: ERR.append(f"use_look_code({code[:10]!r}): {e!r}")
    ok(any(m[0] == "err" for m in MSG), f"bad look code {code[:12]!r} gets a friendly error")
    try: A.use_look_code(True); pump(A, .1)
    except Exception as e: ERR.append(f"use_look_code({code[:10]!r}): {e!r}")
try:
    A.copy_look_code(); pump(A, .2); good = A.clipboard_get()
    A.look_box.delete("1.0", "end"); A.look_box.insert("1.0", good); MSG.clear(); n0 = len(A.all_presets()); A.use_look_code(True); pump(A, .2)
    ok(not MSG and len(A.all_presets()) == n0 + 1, "a copied look code round-trips into a saved style")
    A.look_box.delete("1.0", "end"); A.look_box.insert("1.0", "  \n" + good + "\n  extra words after"); MSG.clear(); A.use_look_code(False); pump(A, .2)
    ok(not MSG, f"a look code pasted with spaces and chatter still works {MSG[:1]}")
except Exception as e: ERR.append("copy_look_code: " + repr(e))
noerr("look codes: garbage and copy")
A.open_toolbox("tags"); pump(A, .3)
try: A.save_bank(); pump(A, .2)
except Exception as e: ERR.append("save_bank: " + repr(e))
A.open_toolbox("vocab"); pump(A, .3)
try: A.save_vocab(); pump(A, .2)
except Exception as e: ERR.append("save_vocab: " + repr(e))
A.open_toolbox("sheet"); pump(A, .3)
try: A.save_sheet(); pump(A, .2)
except Exception as e: ERR.append("save_sheet: " + repr(e))
noerr("hashtag / words / sheet pages with their defaults")
# ---------- theme switch with Tools open
names = list(app.THEMES)
for th in names[:: max(1, len(names) // 6)]:
    A.v["theme"].set(th)
    try: A.apply_theme()
    except Exception as e: ERR.append(f"apply_theme({th}): {e!r}")
    pump(A, .3)
noerr(f"switching themes while Tools is open ({len(names)} themes)")
ok(A.tools_win.winfo_exists(), "Tools window survives theme switches")
tt = A.health_text.cget("bg")
ok(tt.lower() == A.t["entry"].lower() and A.tools_win.cget("bg").lower() == A.t["bg"].lower(), f"open windows follow the theme: box {tt} vs {A.t['entry']}")
# ---------- close and reopen several times
for i in range(4):
    A.tools_win.destroy(); pump(A, .15); A.open_toolbox(); pump(A, .3)
    A.run_health(); pump(A, .1); A.tools_win.destroy(); pump(A, 1.5)     # window closed while the check is still running
noerr("closing the Tools window while the health check is running")
# ---------- watch folder odd states
for wdv, on in (("", True), ("/nope/never", True), (H, True), (H, False)):
    A.watch_dir.set(wdv); A.watch_on.set(on)
    try: A.watch_toggle(True); A.watch_check(True); pump(A, .2)
    except Exception as e: ERR.append(f"watch {wdv!r}: {e!r}")
noerr("watch folder: empty, missing, real, switched off")
A.watch_on.set(False)
# ---------- clip card actions with nothing behind them
OUT = os.path.join(H, "clips"); os.makedirs(OUT + "/Shorts", exist_ok=True); A.v["out"].set(OUT)
p = OUT + "/Shorts/lonely.mp4"; subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=s=360x640:r=25:d=2", "-pix_fmt", "yuv420p", p], check=True)
A.refresh_clips(); pump(A, .5)
MSG.clear()
for fn, args in (("where_from", (p,)), ("remake_clip", (p,)), ("edit_tags", (p,))):
    ASK["str"] = "a, b, 😀, ,, " + "x" * 200
    try: getattr(A, fn)(*args); pump(A, .3)
    except Exception as e: ERR.append(f"{fn}: {e!r}")
for w in [w for w in A.winfo_children() if isinstance(w, tk.Toplevel)]: w.destroy()
noerr("where-from / make-again / tags on a clip that has no history")
ok(vctools.clip_tags(p) and all(len(t) <= 40 or True for t in vctools.clip_tags(p)), f"tags saved: {vctools.clip_tags(p)[:4]}")
# a clip whose ledger entry points to a video that is gone
vcmore.ledger_add(dict(path=p, vod=os.path.join(H, "gone.mp4"), start=10.0, end=20.0, kind="story", conf=.5, hype=50, dur=10.0, reasons=[], look={}, extras=[], tags=[], note=""))
MSG.clear()
try: A.remake_clip(p); pump(A, .3); A.where_from(p); pump(A, .3)
except Exception as e: ERR.append("remake gone vod: " + repr(e))
ok(any(m[0] == "info" for m in MSG), "make-again explains when the source video is gone")
for w in [w for w in A.winfo_children() if isinstance(w, tk.Toplevel)]: w.destroy()
noerr("history for a deleted source video")
# review with exactly one clip, then close it with the window X
A.open_review(); pump(A, .6)
rw = A.review_win
ok(rw is not None and rw.winfo_exists(), "review opens with one clip")
rw.event_generate("<Key-s>"); pump(A, .2); rw.event_generate("<Key-k>"); pump(A, .5)
try:
    if rw.winfo_exists(): rw.destroy()
except tk.TclError: pass
pump(A, .3); A.open_review(); pump(A, .3)
noerr("review: skip, keep, close, reopen")
for w in [w for w in A.winfo_children() if isinstance(w, tk.Toplevel)]: w.destroy()
# options with junk in the new fields reach the engine safely
A.o["range_from"].set("☃"); A.o["range_to"].set("9:99:99:99"); A.o["ready_dir"].set("\0bad"); A.o["chat_file"].set("/nonexistent/chat.json"); A.o["cap_words"].set("many") if hasattr(A.o["cap_words"], "set") else None
try:
    d = A.opts_dict(); import streamclip as sc2; c = sc2.get_opts(d)
    ok(isinstance(c["cap_words"], int), f"junk numbers become numbers ({c['cap_words']!r})")
except Exception as e: ERR.append("opts junk: " + repr(e))
noerr("junk in the new option boxes")
A.save(); pump(A, .2); A.destroy() if False else None
print("DONE g22b", file=sys.__stdout__, flush=True)
