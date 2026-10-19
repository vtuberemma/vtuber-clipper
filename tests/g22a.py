"""GUI tests for 2.2: Smart finding tab, extra rows, Tools window, My clips additions, Best moments file, try-one-first, resume, watch folder."""
exec(open(__import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "h12.py")).read())
import tkinter as tk, re, types, threading, glob, datetime, json
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
def texts(wd): return [w.cget("text") for w in walk(wd) if w.winfo_class() in ("TCheckbutton", "TButton", "TLabel", "Label", "TMenubutton") and str(w.cget("text"))]
OPENED = []; app.open_path = lambda p: OPENED.append(p)
import webbrowser; WEB = []; webbrowser.open = lambda u, *a, **k: WEB.append(u)
OUT = os.path.join(H, "clips"); os.makedirs(OUT + "/Shorts", exist_ok=True)
def mkclip(n, d=5, kit=True, ledger=True, kind="reaction", vod=None, start=100.0):
    p = f"{OUT}/Shorts/{n}.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc=s=360x640:r=25:d={d}", "-f", "lavfi", "-i", f"sine=f=440:d={d}", "-shortest", "-pix_fmt", "yuv420p", p], check=True)
    if kit: open(f"{OUT}/Shorts/{n}.txt", "w", encoding="utf-8").write(f"HYPE SCORE  77/100\n\nTITLE IDEAS\n  1. {n} the funniest title 😂\n  2. other\n\nDESCRIPTION\ndesc of {n}\n\nHASHTAGS\n#vtuber #{n}\n")
    if ledger: vcmore.ledger_add(dict(path=p, vod=vod or "", start=start, end=start + d, kind=kind, conf=.8, hype=77, dur=float(d), reasons=["a big laugh at the end"], look={}, extras=[], tags=[], note=""))
    return p
VOD = paths.FIX + "/stream22.mp4"
CL = {n: mkclip(n, kind=k, vod=VOD, start=st) for n, k, st in (("alpha", "reaction", 31.0), ("bravo", "story", 80.0), ("charlie", "gameplay", 140.0), ("delta", "singing", 200.0))}
gone = mkclip("nokit", kit=False, ledger=False)

# ================================================================ start-up
A = mk(None); A.geometry("1280x900"); A.v["out"].set(OUT); pump(A, 1.5)
ok(app.VC22_ERR is None and app.VC21_ERR is None, "the 2.2 modules loaded without error (%s)" % (app.VC22_ERR or "")[-200:])
ok(app.VERSION >= "2.2", "version is 2.2 or newer")
ok([k for k, _ in A.subbar.items] == ["quick", "smart", "text", "captions", "extras", "safe"], f"simple view: Quick setup, Smart finding, Words & buttons, Captions, Logo & music, Privacy & checks ({[k for k, _ in A.subbar.items]})")
ok(set(dict(app.SUBTABS)) == set(A.subs) and all(k in vc21ui.TAB_HELP for k, _ in app.SUBTABS), "every tab has a page and a description")
ok(not ERR, "no errors so far " + (ERR[0][-300:] if ERR else ""))
# the options exist and reach the engine
for k in vc22ui.NEW_STR + vc22ui.NEW_BOOL: assert k in A.o, k
ok(all(k in A.o for k in vc22ui.NEW_STR + vc22ui.NEW_BOOL), "all 25 new options have a variable")
d = A.opts_dict(); ok(d["smart"] is True and d["cap_case"] == "auto" and d["cap_shadow"] == 2 and d["ready_dir"] == "" and d["range_from"] == "", f"defaults reach the engine {d['smart']} {d['cap_case']}")
# ---------------- Smart finding tab
A.sub.set("smart"); pump(A, .5)
ok(A.subs["smart"].winfo_ismapped() and A.tab_help.get().startswith("How I find"), "Smart finding tab opens with its description")
tx = texts(A.subs["smart"])
for need in ("🧠 Smart finding (recommended)", "🎲 Mix different kinds, not five of the same", "👋 Skip “hey guys, welcome back” openings", "📏 Pick the length for each kind of moment", "✂ End right after the punchline",
             "🎨 Match the captions to the kind of moment", "💗 Learn from the clips I keep", "📚 My words…"):
    ok(need in tx, f"Smart tab has: {need}")
ok(any("Gameplay" in t and "about 18" in t for t in tx) and any("Singing" in t for t in tx), "the five kinds are listed with their usual lengths")
ok(A.taste_note.get().startswith("I need at least 3"), f"taste note says it needs data: {A.taste_note.get()[:50]}")
A.o["range_from"].set("1:20:00"); A.o["range_to"].set("2:00:00"); pump(A, .2); ok("1:20:00" in A.range_note.get() and "2:00:00" in A.range_note.get(), f"range note: {A.range_note.get()}")
A.o["range_to"].set("1:00:00"); pump(A, .2); ok("after the start" in A.range_note.get(), "end before start is explained")
A.o["range_from"].set("abc"); pump(A, .2); ok("can't read" in A.range_note.get(), "bad time is explained")
A.o["range_from"].set(""); A.o["range_to"].set(""); pump(A, .2); ok(A.range_note.get() == "", "no range = no note")
shot(A, "g22_smart")
# a tab reset puts the smart options back
A.o["smart"].set(False); A.o["variety"].set(False); A.o["chat_file"].set("x.json"); A.reset_tab(); pump(A, .3)
ok(A.o["smart"].get() and A.o["variety"].get() and A.o["chat_file"].get() == "", "Reset tab restores the Smart finding options")
# quick tab has the smart check
A.sub.set("quick"); pump(A, .3); ok("🧠 Smart finding" in texts(A.subs["quick"]), "Quick setup has the Smart finding check")

# ---------------- extra rows
A.simple.set(False); pump(A, .4)
ok([k for k, _ in A.subbar.items] == ["smart", "basics", "text", "fx", "captions", "emotes", "polish", "extras", "safe", "post"], "all options: ten tabs")
A.sub.set("captions"); pump(A, .5)
tx = texts(A.subs["captions"])
for need in ("✨ More caption styling", "Letters", "Outline", "Shadow", "Words at a time", "Box behind the words", "🌈 Rainbow words"):
    ok(need in tx, f"Captions tab has: {need}")
ok(any(t.startswith("💥 Big reaction words") for t in tx), "Captions tab has the reaction words check")
A.o["cap_case"].set("upper"); A.o["cap_outline"].set("thick"); A.o["cap_shadow"].set("4"); A.o["cap_words"].set("2"); A.o["cap_box"].set("60"); A.o["cap_rainbow"].set(True); A.o["react_words"].set(True)
d = A.opts_dict(); ok((d["cap_case"], d["cap_outline"], d["cap_shadow"], d["cap_words"], d["cap_box"], d["cap_rainbow"], d["react_words"]) == ("upper", "thick", 4, 2, 60, True, True), "caption options reach the engine as typed values")
A.o["cap_shadow"].set("99"); A.o["cap_box"].set("-5"); A.o["cap_words"].set("abc"); d = A.opts_dict(); ok((d["cap_shadow"], d["cap_box"], d["cap_words"]) == (8, 0, 0), f"silly numbers are clamped ({d['cap_shadow']},{d['cap_box']},{d['cap_words']})")
cb = [w for w in walk(A.subs["captions"]) if w.winfo_class() == "TCombobox"]
ok(any(c.get() == "ALL CAPS" for c in cb) and any(c.get() == "Thick" for c in cb), "the drop-downs show friendly names")
A.sub.set("polish"); pump(A, .4); tx = texts(A.subs["polish"])
for need in ("🔊 Calm the sound", "🔉 Tame loud screams", "🌬 Hush the background hiss", "🎞 Dramatic beats", "🐌 Slow-mo on the biggest moment", "⏸ Freeze-frame beat on a second moment"): ok(need in tx, f"Picture & voice has: {need}")
ok(any(t.startswith("🎬 Teaser first") for t in tx), "Picture & voice has the teaser")
A.sub.set("extras"); pump(A, .4); ok(any(t.startswith("🦘 Move my logo") for t in texts(A.subs["extras"])), "Logo & music has the hopping logo")
A.sub.set("post"); pump(A, .4); tx = texts(A.subs["post"])
for need in ("📦 More files", "Extra copies", "Ready-to-post folder", "# Hashtag bank…", "📄 Post sheet (CSV)…"): ok(need in tx, f"Posting & files has: {need}")
ok(any(t.startswith("🗓 Offer to put new clips") for t in tx), "Posting & files has the planner offer")
A.o["extra_shapes"].set("1:1,16:9"); A.o["ready_dir"].set(os.path.join(H, "ready")); d = A.opts_dict(); ok(d["extra_shapes"] == "1:1,16:9" and d["ready_dir"].endswith("ready"), "extra shapes + ready folder reach the engine")
A.o["extra_shapes"].set("9:99"); ok(A.opts_dict()["extra_shapes"] == "", "an unknown shape is dropped")
A.o["extra_shapes"].set("")
# name pattern preview knows the new tokens
A.o["name_pattern"].set("{date} {type} {score} {len} clip {n}"); A.name_preview(); pump(A, .2); ok("reaction 87 34s" in A.name_prev.get(), f"file name example: {A.name_prev.get()}")
A.o["name_pattern"].set("{video}_short{n}")
# looks include the new caption options
L = A.get_look(); ok("cap_rainbow" in L["opts"] and "cap_case" in L["opts"], "a look (style) now holds the caption extras")
A.o["cap_rainbow"].set(True); A.o["cap_case"].set("lower"); A.choose_preset(A.all_presets()[0]["id"]); pump(A, .3)
ok(not A.o["cap_rainbow"].get() and A.o["cap_case"].get() == "auto", "choosing a built-in style resets the caption extras to normal")
A.o["cap_shadow"].set("2"); A.o["cap_box"].set("0"); A.o["cap_words"].set("0")
# settings survive a restart
A.o["slowmo"].set(True); A.o["hop_logo"].set(True); A.o["range_from"].set("10:00"); A.o["chat_file"].set("C:/chat.json"); A.watch_dir.set(OUT); A.plan_offer.set(True); A.save()
cfg = json.load(open(app.CFG)); ok(cfg["opts"]["slowmo"] is True and cfg["opts"]["range_from"] == "10:00" and cfg["v22"]["plan_offer"] is True and cfg["v22"]["watch_dir"] == OUT, "new options + 2.2 state are in the settings file")
A.destroy(); A = mk(open(app.CFG).read()); A.geometry("1280x900"); A.v["out"].set(OUT); pump(A, 1.2)
ok(A.o["slowmo"].get() and A.o["hop_logo"].get() and A.o["range_from"].get() == "10:00" and A.plan_offer.get() and A.watch_dir.get() == OUT, "the next start remembers them")
A.o["slowmo"].set(False); A.o["hop_logo"].set(False); A.o["range_from"].set(""); A.o["chat_file"].set(""); A.plan_offer.set(False); A.watch_dir.set("")

# ================================================================ Tools window
ok(A.toolbtn.winfo_ismapped(), "the Tools button is in the banner")
A.open_toolbox(); pump(A, .8)
ok(A.tools_win.winfo_exists() and list(A.tools_pages)[:8] == ["watch", "health", "clean", "space", "looks", "tags", "vocab", "sheet"], f"Tools window still has the eight 2.2 pages first {list(A.tools_pages)}")
A.open_toolbox("looks"); pump(A, .3); ok(A.tools_nb.select() == str(A.tools_groups["looks"][0]) and A.tools_groups["looks"][1].select() == str(A.tools_pages["looks"]), "asking for a page selects it and its group (and does not open a second window)")
ok(len([w for w in A.winfo_children() if isinstance(w, tk.Toplevel) and w.title().startswith("Tools")]) == 1, "only one Tools window")
shot(A, "g22_tools")
# watch
wd = os.path.join(H, "watch"); os.makedirs(wd)
def vid(n, age=100):
    p = os.path.join(wd, n); open(p, "wb").write(b"0" * 300000); t = time.time() - age; os.utime(p, (t, t)); return p
vid("old1.mp4", 900); vid("old2.mkv", 900)
A.watch_dir.set(wd); A.watch_on.set(True); pump(A, .4)
ok("2 videos already in there are ignored" in A.watch_note.get(), f"turning the watch on ignores what is already there: {A.watch_note.get()}")
A.watch_check(True); ok("Nothing new" in A.watch_note.get(), "nothing new yet")
new1 = vid("stream_today.mp4", 90); MSG.clear()
A.watch_check(True); pump(A, .3)
ok("stream_today.mp4" in A.watch_note.get() and any(m[0] == "ask" and "stream_today" in str(m[1]) for m in MSG) and A.v["video"].get() == new1, f"a new video is announced and loaded: {A.watch_note.get()}")
A.watch_check(True); ok("Nothing new" in A.watch_note.get(), "and only announced once")
vid("still_writing.mp4", 2); A.watch_check(True); ok("Nothing new" in A.watch_note.get(), "a file that is still being written is left alone")
# auto start
A.watch_auto.set(True); MADE = []; A.make = lambda: MADE.append(A.v["video"].get())
n2 = vid("auto_1.mp4", 200); n3 = vid("auto_2.mp4", 200); A.watch_check(True); pump(A, 2.2)
ok(MADE == [n2] and A.batch == [n2, n3] and A.mode.get() == "shorts", f"auto mode loads the videos as a queue and presses Make once {MADE} {A.batch}")
A.watch_auto.set(False); A.watch_on.set(False); pump(A, .2); ok(A.watch_note.get() == "Not watching.", "switching it off")
A.batch = []; del A.make
# health
A.open_toolbox("health"); A.run_health(); pump(A, 6)
ok(A.health_items and "ffmpeg" in A.health_text.get("1.0", "end") and A.health_sum.get() != "", f"health check lists things: {A.health_sum.get()}")
A.clipboard_clear(); A.copy_health(); ok("VTuber Clipper health check" in A.clipboard_get(), "report can be copied")
# clean up
lo_ = os.path.join(OUT, ".vclip_dead"); os.makedirs(lo_); open(lo_ + "/g.txt", "w").write("x" * 500); open(OUT + "/Shorts/orphan_cover.jpg", "wb").write(b"x" * 100)
A.run_leftovers(); pump(A, 1.5)
ok(A.clean_list.size() == 2 and "2 leftovers" in A.clean_sum.get(), f"leftovers listed: {A.clean_sum.get()} / {A.clean_list.get(0, 'end')}")
A.clean_list.selection_set(0, "end"); A.remove_leftovers(); pump(A, 1.5)
ok(not os.path.exists(lo_) and not os.path.exists(OUT + "/Shorts/orphan_cover.jpg") and os.path.isfile(CL["alpha"]) and A.clean_list.size() == 0, "selected leftovers are removed, clips untouched")
# space
os.makedirs(OUT + "/VODs", exist_ok=True); open(OUT + "/VODs/big_stream.mp4", "wb").write(b"x" * 20000)
os.makedirs(app.sc.CACHE_DIR, exist_ok=True); open(os.path.join(app.sc.CACHE_DIR, "an3_zz.npz"), "wb").write(b"x" * 4000)
A.refresh_space(); pump(A, 1.5)
ok(A.vod_list.size() == 1 and "big_stream.mp4" in A.vod_list.get(0), "downloaded videos are listed")
ok(any("Sound analysis" in t for t in texts(A.space_box)), "cache sizes are listed")
A.empty_cache("an"); pump(A, 1.2); ok(not os.path.exists(os.path.join(app.sc.CACHE_DIR, "an3_zz.npz")), "emptying the analysis cache works")
A.vod_list.selection_set(0); A.delete_vods(); pump(A, 1.2); ok(not os.path.exists(OUT + "/VODs/big_stream.mp4"), "a selected downloaded video can be deleted")
# looks: copy + paste
A.clipboard_clear(); A.copy_look_code(); code = A.clipboard_get(); ok(code.startswith("VTLOOK1:"), "look code copied")
A.o["cap_style"].set("karaoke"); A.apply_look(dict(A.get_look(), lmin=17, lmax=23)); A.look_box.delete("1.0", "end"); A.look_box.insert("1.0", "here: " + code)
A.use_look_code(False); pump(A, .3); ok(A.v["lmin"].get() == str(A.get_look()["lmin"]) and A.sel_preset.get() == "", "using a look code applies it")
n_before = len(A.upresets); A.use_look_code(True); pump(A, .3); ok(len(A.upresets) == n_before + 1, "a look code can be saved as my style")
MSG.clear(); A.look_box.delete("1.0", "end"); A.look_box.insert("1.0", "nonsense"); A.use_look_code(False); ok(MSG and MSG[-1][0] == "err" and "look code" in str(MSG[-1][1]), "a bad code gives a plain message")
# hashtags
A.bank_always.set("#vtuber #envtuber"); A.bank_games.delete("1.0", "end"); A.bank_games.insert("1.0", "Minecraft: #minecraft #mc\nbad line\n: #x"); A.bank_kinds["reaction"].set("#reaction")
A.save_bank(); b = vctools.bank_load(); ok(b["always"] == ["vtuber", "envtuber"] and b["games"] == {"minecraft": ["minecraft", "mc"]} and b["kinds"] == {"reaction": ["reaction"]}, f"hashtag bank saved {b}")
# vocabulary
A.vocab_vars["laugh"].set("KEK, heh, two words"); A.vocab_vars["hype"].set("clipit"); A.save_vocab()
ok(A.vocab_vars["laugh"].get() == "kek, heh" and vctools.vocab_load()["hype"] == ["clipit"], "my words saved and tidied")
A.suggest_words(); pump(A, .5); ok("at least 3" in A.vocab_note.get(), "suggestions explain what they need")
# sheet
sheet = os.path.join(H, "sheet.csv"); filedialog.asksaveasfilename = lambda *a, **k: sheet
A.save_sheet(); import csv; rows = list(csv.DictReader(open(sheet, encoding="utf-8-sig")))
ok(len(rows) == 5 and {r["Clip file"] for r in rows} >= {"alpha.mp4", "delta.mp4"} and [r for r in rows if r["Clip file"] == "bravo.mp4"][0]["Kind"] == "story", f"post sheet written ({len(rows)} rows)")
A.sheet_fav.set(True); A.save_sheet(); ok(MSG[-1][0] == "info", "no favourites -> a friendly message")
A.sheet_fav.set(False)
A.tools_win.destroy(); pump(A, .3)

# ================================================================ My clips
A.mode.set("clips"); pump(A, 1.0); A.refresh_clips(); pump(A, 2.0)
ok(len(A.clip_cards) == 5, f"five clips listed ({len(A.clip_cards)})")
labs = texts(A.pages["clips"])
for need in ("🗂 Review mode", "🗓 Plan new clips", "📄 Post sheet"): ok(need in labs, f"My clips has: {need}")
A.clip_q.set("bravo"); pump(A, 1.2); ok(set(A.clip_cards) == {CL["bravo"]}, "search finds by file name")
A.clip_q.set("funniest delta"); pump(A, 1.2); ok(set(A.clip_cards) == {CL["delta"]}, "search finds by title words")
A.clip_q.set("singing"); pump(A, 1.2); ok(set(A.clip_cards) == {CL["delta"]}, "search finds by kind")
A.clip_q.set("#vtuber"); pump(A, 1.2); ok(len(A.clip_cards) == 4, f"search finds by hashtag ({len(A.clip_cards)})")
A.clip_q.set("zzz nothing"); pump(A, 1.2); ok(not A.clip_cards and "Nothing matches" in A.clips_note.get(), "no match gives a note")
simpledialog.askstring = lambda *a, **k: "funny, boss fight"
A.clip_q.set(""); pump(A, 1.0); A.edit_tags(CL["alpha"]); pump(A, 1.5)
ok(vctools.clip_tags(CL["alpha"]) == ["funny", "boss fight"], "tags saved"); A.clip_q.set("boss"); pump(A, 1.2); ok(set(A.clip_cards) == {CL["alpha"]}, "search finds my own tags")
A.clip_q.set(""); pump(A, 1.0)
# fav / posted / delete update the diary
A.toggle_fav(CL["alpha"]); ok(vcmore.ledger_find(CL["alpha"])["fav"] is True, "starring updates the clip diary")
A.toggle_fav(CL["alpha"]); ok(vcmore.ledger_find(CL["alpha"])["fav"] is False, "un-starring too")
A.mark_posted(CL["alpha"], "TikTok"); ok(vcmore.ledger_find(CL["alpha"])["posted"] is True, "marking as posted updates the diary")
A.clear_posted(CL["alpha"]); ok(vcmore.ledger_find(CL["alpha"])["posted"] is False, "un-marking too")
# taste learns after 3 stars
for n in ("alpha", "bravo", "charlie"): A.toggle_fav(CL[n])
pump(A, .3); ok("From 3 clips you kept" in A.taste_note.get(), f"taste note after 3 stars: {A.taste_note.get()}")
for n in ("alpha", "bravo", "charlie"): A.toggle_fav(CL[n])
# where from
ok(True, "-")
A.where_from(CL["bravo"]); pump(A, .4)
wt = [w for w in A.winfo_children() if isinstance(w, tk.Toplevel) and w.title().startswith("Where")][0]
ok(any("1:20" in str(x) for x in texts(wt)) and any("a big laugh" in str(x) for x in texts(wt)), "where-from shows the time in the VOD and why it was picked"); wt.destroy()
A.where_from(gone); pump(A, .3); wt = [w for w in A.winfo_children() if isinstance(w, tk.Toplevel) and w.title().startswith("Where")][0]
ok(any("don't know" in str(x) for x in texts(wt)), "an old clip without diary entry says so"); wt.destroy()
# remake
RUN = []; A.run_shorts = lambda windows=None: RUN.append(windows)
A.remake_clip(CL["bravo"]); ok(RUN == [[(80.0, 85.0)]] and A.v["video"].get() == VOD, f"remake asks the engine for exactly that moment {RUN}")
MSG.clear(); A.remake_clip(gone); ok(MSG[-1][0] == "info" and "don't know" in str(MSG[-1][1]), "remake of an unknown clip explains")
vcmore.ledger_add(dict(path=CL["delta"], vod=os.path.join(H, "missing.mp4"), start=3, end=9, kind="singing", dur=6.0)); MSG.clear(); A.remake_clip(CL["delta"]); ok("not on this PC" in str(MSG[-1][1]), "remake with the VOD gone explains")
del A.run_shorts
# review mode
n_before = len(A.marks["fav"]); A.open_review(); pump(A, 1.5)
rw = A.review_win; ok(rw.winfo_exists() and any("Clip 1 of" in str(x) for x in texts(rw)), f"review mode opens {[x for x in texts(rw)][:2]}")
btn = {b.cget("text"): b for b in walk(rw) if b.winfo_class() == "TButton"}
btn["👍 Keep (star it)"].invoke(); pump(A, .5); ok(len(A.marks["fav"]) == n_before + 1, "keep stars the clip")
btn["⏭ Later"].invoke(); pump(A, .3)
before_files = set(A.clip_files()); btn["👎 Delete"].invoke(); pump(A, .5)
gone_now = before_files - set(A.clip_files()); ok(len(gone_now) == 1 and vcmore.ledger_find(list(gone_now)[0])["deleted"] is True, "delete removes the clip and tells the diary")
while "All done" not in [x for x in texts(rw) if "All done" in str(x)][:1].__str__() and rw.winfo_exists():
    try: ba = {b.cget("text"): b for b in walk(rw) if b.winfo_class() == "TButton"}; ba["⏭ Later"].invoke(); pump(A, .1)
    except Exception: break
    if any("All done" in str(x) for x in texts(rw)): break
ok(any("All done" in str(x) for x in texts(rw)), "review ends with a summary"); rw.destroy()
# plan new clips
A.plan = []; A.plan_new_clips(); pump(A, .5)
ok(len(A.plan) >= 1 and all(d["platform"] == "tiktok" for d in A.plan), f"planner filled ({len(A.plan)} clips)")
times = [d["when"] for d in A.plan]; ok(times == sorted(times) and len(set(times)) == len(times), "one clip per time slot, in order")
A.plan = []

# ================================================================ Best moments file
A.mode.set("moments"); pump(A, .5)
ok("💾 Save list…" in texts(A.pages["moments"]) and "📂 Open list…" in texts(A.pages["moments"]), "Best moments has Save list / Open list")
A.v["video"].set(VOD); pump(A, .5); A.moments = [dict(start=10.0, end=40.0, score=88, peak=20.0, text="hello", tags=["Laugh"]), dict(start=100.0, end=130.0, score=60, peak=100.0, text="", tags=[])]; A.mom_video = VOD; A.fill_moments()
mf = os.path.join(H, "list.vtmoments"); filedialog.asksaveasfilename = lambda *a, **k: mf; A.moments_to_file(); ok(os.path.isfile(mf) and "Saved 2 moments" in A.mnote.get(), "moments list saved")
A.moments = []; A.fill_moments(); filedialog.askopenfilename = lambda *a, **k: mf; A.moments_from_file(); pump(A, .3)
ok(len(A.moments) == 2 and A.mview[0]["start"] == 10.0 and "Opened 2" in A.mnote.get(), "moments list opened again")
filedialog.askopenfilename = lambda *a, **k: os.path.join(H, "nonexistent"); MSG.clear(); A.moments_from_file(); ok(MSG and MSG[-1][0] == "info", "a missing file gives a message")

# ================================================================ try one first / resume
MADE = []
def fake_make():
    MADE.append((A.v["n"].get(), A.o["fresh"].get())); A.busy = True
A.make = fake_make; A.mode.set("shorts"); A.v["n"].set("6"); A.o["fresh"].set(False)
A.try_one_first(); ok(MADE == [("1", False)] and A.try22["stage"] == 1, f"try one first makes just one {MADE}")
A.busy = False; A.job_mode = "shorts"; A.failed = A.cancelled = False; MSG.clear(); A.finish22(False); pump(A, .8)
ok(any(m[0] == "ask" and "other 5" in str(m[1]) for m in MSG) and A.try22 and A.try22["stage"] == 2, "after it, I ask if the other 5 should be made")
ok(MADE[-1] == ("5", True), f"the rest is made with 'skip moments already made' on {MADE[-1]}")
A.busy = False; A.finish22(False); ok(A.v["n"].get() == "6" and A.o["fresh"].get() is False and A.try22 is None, "after the rest, the settings are put back")
A.try_one_first(); A.busy = False; A.finish22(True); ok(A.v["n"].get() == "6" and A.try22 is None, "a failed first clip puts the settings back and asks nothing")
A.v["n"].set("1"); MADE.clear(); A.try_one_first(); ok(MADE == [("1", False)] and A.try22 is None, "with one clip the button just makes it"); A.busy = False
del A.make
# resume
vctools.run_start(dict(mode="shorts", video=VOD, batch=[])); MADE = []; A.make = lambda: MADE.append(A.v["video"].get())
A.v["video"].set(""); MSG.clear(); A.resume_check(); pump(A, 1.0)
ok(any("Pick it up again" in str(m[1]) for m in MSG if m[0] == "ask") and MADE == [VOD] and A.o["fresh"].get() and vctools.run_left() is None, f"an unfinished run is offered again {MADE}")
A.resume_check(); ok(len(MADE) == 1, "and only once")
del A.make
# run notes
A.hook22("start", "shorts"); ok(vctools.run_left() and vctools.run_left()["mode"] == "shorts", "starting a job writes the resume note")
A.hook22("finish", False); ok(vctools.run_left() is None, "finishing removes it")
A.hook22("start", "tidy"); ok(vctools.run_left() is None, "jobs that make no videos do not write one")
# cam memory
A.o["game"].set("Minecraft"); A.v["cam"].set("480:270:40:40"); A.cam_remember(); A.v["cam"].set(""); A.o["game"].set(""); A.o["game"].set("Minecraft"); pump(A, .2)
ok(A.v["cam"].get() == "480:270:40:40", "the cam box comes back when the game is named")
A.v["cam"].set("1:1:1:1"); A.o["game"].set("Other"); A.o["game"].set("Minecraft"); ok(A.v["cam"].get() == "1:1:1:1", "a cam box that is set is never overwritten")
A.v["cam"].set(""); A.o["game"].set("")

ok(not ERR, "no uncaught errors in the whole run: " + (ERR[0][-600:] if ERR else ""))
A.destroy()
