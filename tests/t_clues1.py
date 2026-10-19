"""2.3 finding clues (features 1-11): the pure functions with made-up words and arrays, then the clip chooser (smart_plan) on the synthetic stream."""
import sys, os, json, tempfile
import paths
H = tempfile.mkdtemp(); os.environ["HOME"] = H; os.environ["USERPROFILE"] = H
sys.path.insert(0, paths.APP)
import numpy as np
import vcclues as C, vcsmart, vc23
bad = 0
def ok(name, cond, extra=""):
    global bad
    print(("PASS " if cond else "FAIL ") + name, extra if not cond else "", flush=True)
    if not cond: bad += 1

def W(text, t0, step=.4):
    return [dict(w=w, start=round(t0 + i * step, 2), end=round(t0 + i * step + step * .8, 2)) for i, w in enumerate(text.split())]

# ---- 1 chat commands
for m, want in [("!clip", True), ("!CLIP now", True), ("! marker", True), ("!highlight", True), ("clip that", True), ("Clip it!", True), ("clip!", True), ("please clip that", True),
                ("that clip was funny", False), ("I love the clipping sound", False), ("clipboard", False), ("", False), (None, False), ("!clips are great", False), ("someone clip it", True),
                ("!hl", True), ("lol !clip", False)]:
    ok(f"is_clip_command({m!r})", C.is_clip_command(m) is want, C.is_clip_command(m))
msgs = [(100, "!clip"), (102, "clip that"), (105, "!clip"), (30, "hello"), (300, "!marker"), (500.5, "nice"), (301, "pog")]
ok("chat_command_times", C.chat_command_times(msgs) == [100.0, 102.0, 105.0, 300.0], C.chat_command_times(msgs))
mo = C.command_moments(msgs)
ok("command_moments cluster + delay", len(mo) == 2 and mo[0][1] == 3 and abs(mo[0][0] - 92) < 1.01 and mo[1][1] == 1 and abs(mo[1][0] - 290) < .01, mo)
cv = C.cmd_curve(msgs, 400)
ok("cmd_curve strong near 92, half near 290", cv[92] >= .95 and .4 <= cv[290] <= .55 and cv[200] == 0 and cv[10] == 0 and cv.max() <= 1.0, (cv[92], cv[290]))
ok("cmd_curve empty / zero length", C.cmd_curve([], 50).sum() == 0 and len(C.cmd_curve([(5, "!clip")], 0)) == 0 and C.cmd_curve([(9999, "!clip")], 50).sum() == 0)
ok("command_moments none", C.command_moments([(1, "hi")]) == [] and C.command_moments([]) == [])
p = os.path.join(H, "chat.txt"); open(p, "w", encoding="utf-8").write("\n".join(f"[0:{i // 60:02d}:{i % 60:02d}] user{i}: {'!clip' if i in (70, 71) else 'hello there'}" for i in range(0, 300, 3) if True) + "\n[0:01:10] a: !clip\n")
m1 = C.chat_messages(p); ok("chat_messages reads a text log", len(m1) > 50 and any(C.is_clip_command(m) for _, m in m1), len(m1))
ok("chat_messages is cached", C.chat_messages(p) is m1)
ok("chat_messages missing file / None", C.chat_messages(os.path.join(H, "none.txt")) == [] and C.chat_messages(None) == [])

# ---- 2 milestones   3 chat talk
w = W("okay so this is my first time ever doing this", 10) + W("we hit five thousand followers today", 30) + W("we hit 1000 subs", 50) + W("just a normal sentence about the weather", 70) + W("happy birthday to me", 90) + W("level up", 110)
mk = C.milestone_marks(w, 200)
ok("milestone: first time ever", mk[12] >= 1 and mk[10:12].sum() == 0 and mk[14:20].sum() == 0, mk[10:20])
ok("milestone: thousand followers", mk[30:36].sum() >= 1.0, mk[30:36])
ok("milestone: 1000 subs", mk[50:54].sum() >= 1.0, mk[50:54])
ok("milestone: normal talk adds nothing", mk[70:76].sum() == 0)
ok("milestone: birthday word and level up", mk[90:94].sum() >= .6 and mk[110:112].sum() >= 1, (mk[90:94].sum(), mk[110:112].sum()))
ok("milestone: the word 'subs' alone is not a milestone", C.milestone_marks(W("thanks for the subs", 5), 30).sum() == 0)
ct = C.chat_talk_marks(W("chat says I should do it", 5) + W("someone in chat asked about my cat", 20) + W("chat is cool", 40) + W("let me read this one", 60), 100)
ok("chat talk phrases", ct[5] >= 1 and ct[20:23].sum() >= 1 and ct[60:62].sum() >= 1, ct.nonzero())
ok("chat talk: 'chat is cool' is not a reading moment", ct[40:44].sum() == 0)

# ---- 4 bilingual
mix = W("this is so funny ありがとう みんな thank you everyone いくよ lets go", 20, .45)
bl = C.bilingual_marks(mix, 60)
ok("bilingual: English <-> Japanese alternation", bl[20:30].sum() >= 1, bl[18:32])
ok("bilingual: only English", C.bilingual_marks(W("this is all just english words nothing else here at all", 5), 30).sum() == 0)
ok("bilingual: only Japanese", C.bilingual_marks(W("ありがとう みんな いくよ これは すごい ですね", 5), 30).sum() == 0)
ok("bilingual: one switch only is not a mix", C.bilingual_marks(W("hello there my friends ありがとう みんな", 5, .4), 30).sum() == 0)
ok("bilingual: a word with both scripts", C.token_scripts("ありがとうgg") == ["cjk", "latin"] and C.token_scripts("hello") == ["latin"] and C.token_scripts("123") == [] and C.token_scripts("안녕") == ["ko"])
ok("bilingual: Korean + English", C.bilingual_marks(W("hey guys 안녕 여러분 okay so 오늘은 let us go", 10, .4), 40).sum() >= 1)

# ---- 5 rapid fire   6 panic repeats
slow = [dict(w=f"w{i}", start=i * .5, end=i * .5 + .3) for i in range(160)]            # 2 words a second for 80 s
fast = [dict(w=f"f{i}", start=40 + i * .18, end=40 + i * .18 + .15) for i in range(60)]  # ~5.5 words a second for 11 s inside it
words = sorted([x for x in slow if not 40 <= x["start"] < 51] + fast, key=lambda x: x["start"])
fs = C.fast_speech(words, 90)
ok("fast speech detected in the burst", fs[42:50].max() > .5, fs[38:52])
ok("fast speech quiet elsewhere", fs[5:30].max() == 0 and fs[60:85].max() == 0)
ok("fast speech: empty transcript", C.fast_speech([], 40).sum() == 0)
rr = C.repeat_runs(W("no no no no I can not do it", 5) + W("wait wait wait what", 20) + W("ha ha ha ha ha", 30) + W("the the the", 40) + W("1 1 1 1", 50) + W("go go", 60))
ok("repeat runs: no x4 and wait x3", [(t, x, c) for t, x, c in rr if x in ("no", "wait")] == [(5.0, "no", 4), (20.0, "wait", 3)], rr)
ok("repeat runs: laughter, stop-words, digits and pairs are not panic", not any(x in ("ha", "the", "1", "go") for _, x, _ in rr), rr)
rm = C.repeat_marks(W("no no no no", 5) + W("run run run", 12), 30)
ok("repeat marks: longer run is stronger", rm[5] > rm[12] > 0 and rm.max() <= 1.0, (rm[5], rm[12]))

# ---- 7 build-up
t = np.arange(120)
z = np.random.RandomState(1).randn(120) * .2
z[50:62] += np.linspace(0, 3.0, 12); z[62] += 3.4; z[63:] += .2
bu = C.buildup_curve(z)
ok("build-up peaks at the top of the climb", 55 <= int(np.argmax(bu)) <= 66 and bu.max() > .5, (int(np.argmax(bu)), bu.max()))
ok("build-up: nothing in flat noise", C.buildup_curve(np.random.RandomState(2).randn(120) * .2).max() < .15)
dz = np.linspace(3, 0, 60); ok("build-up: a falling line is no build-up", C.buildup_curve(dz).max() == 0)
ok("build-up: a sudden jump without a climb is weak", C.buildup_curve(np.concatenate([np.zeros(50), [3.0], np.zeros(20)])).max() < .5)
ok("build-up: too short", len(C.buildup_curve([1, 2, 3])) == 3 and C.buildup_curve([1, 2, 3]).sum() == 0)

# ---- 11 dead zones
quiet = np.zeros(300, bool); quiet[100:140] = True; quiet[200:210] = True
dw = W("okay I will be right back guys", 150) + W("thanks for watching see you next time", 250)
zs = C.dead_zones(dw + [dict(w="x", start=5, end=6)], quiet, 300)
ok("dead zones: BRB phrase", any(a <= 150 <= b for a, b in zs), zs)
ok("dead zones: goodbye phrase", any(a <= 250 <= b for a, b in zs), zs)
ok("dead zones: 40 quiet seconds without speech", any(a <= 100 and b >= 140 for a, b in zs), zs)
ok("dead zones: 10 quiet seconds are just a pause", not any(a <= 205 <= b for a, b in zs), zs)
spoken = [dict(w=f"w{i}", start=100 + i, end=100.8 + i) for i in range(40)]
ok("dead zones: quiet seconds with speech are not dead", not C.dead_zones(spoken, quiet, 300))
ok("dead zones merge", len(C.dead_zones(W("brb brb", 10, 3) + W("be right back", 12), None, 100)) == 1)
ok("zones_overlap", abs(C.zones_overlap(10, 30, [(20, 40)]) - .5) < 1e-9 and C.zones_overlap(10, 30, []) == 0 and C.zones_overlap(10, 10, [(0, 99)]) == 0 and C.zones_overlap(0, 10, [(0, 99)]) == 1)

# ---- compute + options
n = 300; rmsz = np.random.RandomState(3).randn(n) * .1
allon = {k: True for k in C.CLUE_OPT.values()}
cl = C.compute(dw + W("first time ever", 60), rmsz, n, allon, msgs, quiet)
ok("compute: parts present", {"cmd", "milestone", "chat_talk", "bilingual", "fast", "repeat", "buildup"} <= set(cl["parts"]) and cl["zones"] and len(cl["boost"]) == n, list(cl["parts"]))
ok("compute: command boost is positive, dead zones negative", cl["boost"][92] > 1.5 and cl["boost"][150] < 0, (cl["boost"][92], cl["boost"][150]))
off = {k: False for k in C.CLUE_OPT.values()}
cl0 = C.compute(dw, rmsz, n, off, msgs, quiet)
ok("compute: everything off adds nothing", not cl0["parts"] and not cl0["zones"] and float(np.abs(cl0["boost"]).sum()) == 0 and not cl0["cmds"])
one = dict(off, chat_cmds=True); cl1 = C.compute(dw, rmsz, n, one, msgs, quiet)
ok("compute: one clue on", list(cl1["parts"]) == ["cmd"] and cl1["cmds"])
ok("compute: no chat means no command clue", "cmd" not in C.compute(dw, rmsz, n, allon, [], quiet)["parts"])
ok("compute: no words / no loudness do not crash", C.compute([], None, 50, allon, None, None)["boost"].shape == (50,))
rs = C.reasons(cl["parts"], 80, 110)
ok("reasons: chat command", "Viewers typed !clip around here" in rs, rs)
ok("reasons: empty / quiet window", C.reasons({}, 0, 10) == [] and C.reasons(None, 0, 10) == [] and C.reasons(cl["parts"], 200, 215) == [], C.reasons(cl["parts"], 200, 215))

# ---- 8 + 9 trims
words = W("hello there everyone this is a story about my cat", 13, .3)               # speech from 13.0 to ~16.0
segs, a, b = C.trim_edges([(10.0, 40.0)], words, None, min_len=2.0)
ok("trim: dead air at start and end", abs(segs[0][0] - 12.65) < .01 and 15.9 < segs[0][1] < 16.6 and a > 2 and b > 20, (segs, a, b))
segs, a, b = C.trim_edges([(10.0, 40.0)], words, None, lead=False, min_len=2.0)
ok("trim: lead off", segs[0][0] == 10.0 and a == 0 and b > 0)
segs, a, b = C.trim_edges([(10.0, 40.0)], words, None, tail=False, min_len=2.0)
ok("trim: tail off", segs[0][1] == 40.0 and b == 0 and a > 0)
segs, a, b = C.trim_edges([(10.0, 18.0)], words, None, min_len=8.0)
ok("trim: never shorter than the minimum", segs == [(10.0, 18.0)] and a == 0 and b == 0, segs)
segs, a, b = C.trim_edges([(0.0, 30.0)], [], None)
ok("trim: no speech and no sound is left alone", segs == [(0.0, 30.0)] and a == b == 0)
q = np.ones(60, bool); q[11] = False
segs, a, b = C.trim_edges([(5.0, 40.0)], words, q, tail=False)
ok("trim: real sound before the first word counts as action", abs(segs[0][0] - (11 - .35)) < .01, segs)
words2 = words + W("and then the funny part happened", 30, .3)
segs, a, b = C.trim_edges([(10.0, 20.0), (25.0, 45.0)], words2, None, min_len=2.0)
ok("trim: several pieces keep their gaps", len(segs) == 2 and abs(segs[0][0] - 12.65) < .01 and segs[1][1] < 33.5 and segs[0][1] == 20.0 and segs[1][0] == 25.0, segs)
ok("trim: empty list", C.trim_edges([], words, None) == ([], 0.0, 0.0))
ok("active_span", C.active_span(words, None, 0, 50)[0] == 13.0 and C.active_span([], None, 0, 5) == (None, None))

# ---- 10 spread
ok("spread_factor: nothing chosen yet", C.spread_factor(10, 30, []) == 1.0)
ok("spread_factor: close is penalised, far is not", C.spread_factor(100, 120, [(100, 120)]) < .6 and C.spread_factor(1000, 1020, [(100, 120)]) == 1.0
   and C.spread_factor(100, 120, [(200, 220)], 180) < C.spread_factor(100, 120, [(400, 420)], 180) <= 1.0)
ok("spread_zone limits", C.spread_zone(100, 5) == 60.0 and C.spread_zone(100000, 2) == 600.0 and 60 <= C.spread_zone(3600, 5) <= 600)

# ---- the options (vc23)
d = vc23.clean_opts(dict(chat_cmds="false", bg_blur="weird", bg_dim=[1], bar_thick="999", logo_alpha="x", privacy="zzz", private_words="Mia, Tokyo;  Sunrise High\n", maybe_below=-5))
ok("vc23.clean_opts", d["chat_cmds"] is False and d["bg_blur"] == "normal" and d["bg_dim"] == 0 and d["bar_thick"] == 40 and d["logo_alpha"] == 92 and d["privacy"] == "warn"
   and d["private_words"] == "mia\ntokyo\nsunrise high" and d["maybe_below"] == 0, d)
d = vc23.clean_opts({})
ok("vc23.clean_opts empty gives the defaults", all(d[k] == v for k, v in vc23.DEFAULTS.items() if k != "private_words") and d["private_words"] == "")
ok("vc23.split_words", vc23.split_words("a, Mia ;Mia\nTokyo|x") == ["mia", "tokyo"] and vc23.split_words(None) == [] and len(vc23.split_words(",".join(f"word{i}" for i in range(100)))) == 60)
ok("50 features listed once each", [f[0] for f in vc23.FEATURES] == list(range(1, 51)) and len(vc23.FEATURES) == 50)
ok("every option key is a default", all(f[2] in vc23.DEFAULTS for f in vc23.FEATURES if f[2]))

# ---- the engine (the chooser, on the synthetic stream)
import streamclip as sc
sc.FF = paths.FFMPEG; sc.CACHE_DIR = tempfile.mkdtemp()
D = json.load(open(paths.FIX + "/stream22.json")); WORDS = D["words"]
SRC = paths.FIX + "/stream22.mp4"
sc.transcribe = lambda *a, **k: WORDS
prof = sc.PROFILES["mix"]

def analyse(words, o):
    sc.AN.clear(); sc.AX.clear()
    full = sc.get_opts(o)
    scr = sc.features(SRC, words, prof, full)
    return scr, full

def plan(words, o, n=3, lo=15, hi=30, gap=1.5):
    scr, full = analyse(words, o)
    jobs, metas, sk = sc.smart_plan(scr, words, n, lo, hi, gap, "mix", prof, full, (), 0, None, None)
    return jobs, metas, scr

base, _, scr0 = plan(WORDS, {})
ok(f"baseline plan makes clips ({len(base)})", len(base) >= 2)
cl = sc.AN.get("clues") or {}
ok("clues are stored for the run", "parts" in cl and "boost" in cl and len(cl["boost"]) == len(scr0))

# 1: viewers typed !clip in a calm part of the story (about 165 s)
chat = os.path.join(H, "stream.chat.txt")
open(chat, "w", encoding="utf-8").write("\n".join(f"[{i // 3600}:{i % 3600 // 60:02d}:{i % 60:02d}] v{i}: hello" for i in range(0, 240, 4)) + "\n[0:02:55] a: !clip\n[0:02:56] b: clip that\n[0:02:58] c: !clip\n")
def covers(jobs, t): return any(s0 - 1 <= t <= e0 + 1 for s0, e0, _ in jobs)
print("baseline starts:", [(round(a), round(b)) for a, b, _ in base])
without, _, _ = plan(WORDS, {"chat_cmds": False, "chat_file": chat}, n=2)
withc, mt, _ = plan(WORDS, {"chat_file": chat}, n=2)
print("with commands:", [(round(a), round(b)) for a, b, _ in withc], "without:", [(round(a), round(b)) for a, b, _ in without])
ok("1: the moment viewers asked for is chosen when commands count", covers(withc, 166), [(round(a), round(b)) for a, b, _ in withc])
ok("1: ... and it is not just chosen anyway", not covers(without, 166) or covers(withc, 166))
sc.AN.clear()
j2, m2, _ = plan(WORDS, {"chat_file": chat}, n=2)
k = [i for i, (a, b, _) in enumerate(j2) if a - 1 <= 166 <= b + 1]
ok("1: the reason says viewers asked", bool(k) and any("!clip" in r for r in m2[k[0]].get("why", [])), m2)

# 11: a BRB right in the laugh part
brb = sorted(WORDS + W("okay guys I will be right back", 87, .5), key=lambda x: x["start"])
off_j, _, _ = plan(brb, {"skip_dead": False}, n=3)
on_j, _, _ = plan(brb, {"skip_dead": True}, n=3)
zs = (sc.AN.get("clues") or {}).get("zones")
ok(f"11: a zone was found around the BRB ({zs})", bool(zs) and any(a <= 88 <= b for a, b in zs))
def overlap(jobs, a, b): return max([min(e0, b) - max(s0, a) for s0, e0, _ in jobs] + [0])
ok(f"11: BRB part is used when the clue is off ({overlap(off_j, 87, 107):.0f}s) and avoided when on ({overlap(on_j, 87, 107):.0f}s)", overlap(on_j, 87, 107) < max(6, .4 * 25) and (overlap(off_j, 87, 107) > overlap(on_j, 87, 107) or overlap(off_j, 87, 107) < 6), (off_j, on_j))

# 8 + 9: dead air before the first word and after the last word (gaps are kept in: "no_silence"), crafted loudness so the window starts in silence
sc.AN.clear()
flat = np.zeros(300); flat[115:121] = 8.0
sp_words = W("so this is the part where I tell you something really funny about my cat today and then she jumped", 110, .5)       # speech 110 s .. ~127 s
qz = np.ones(300, bool); qz[110:128] = False
sc.AN.update(marks=vcsmart.word_marks(sp_words, 300), curves=None, onsets=[], quiet=qz, clues=None, cover=np.ones(300))
o_ = sc.get_opts({"smart": True, "variety": False, "skip_greet": False})
t_on, _, _ = sc.smart_plan(flat, sp_words, 1, 15, 40, None, "mix", prof, dict(o_, lead_trim=True, tail_trim=True), (), 0, None, None)
t_off, _, _ = sc.smart_plan(flat, sp_words, 1, 15, 40, None, "mix", prof, dict(o_, lead_trim=False, tail_trim=False), (), 0, None, None)
print("trim on:", [(round(a, 1), round(b, 1)) for a, b, _ in t_on], "off:", [(round(a, 1), round(b, 1)) for a, b, _ in t_off])
ok("8: with trimming the clip opens at the first words", len(t_on) == 1 and len(t_off) == 1 and t_off[0][0] < 109 and 109 <= t_on[0][0] <= 110.1, (t_on, t_off))
ok("9: with trimming the clip ends soon after the last sound", t_off[0][1] > 129.5 and t_on[0][1] <= 128.6, (t_on, t_off))
ok("8/9: the trimmed clip is still a real clip", sum(y - x for x, y in t_on[0][2]) >= 12, t_on)
only_lead, _, _ = sc.smart_plan(flat, sp_words, 1, 15, 40, None, "mix", prof, dict(o_, lead_trim=True, tail_trim=False), (), 0, None, None)
only_tail, _, _ = sc.smart_plan(flat, sp_words, 1, 15, 40, None, "mix", prof, dict(o_, lead_trim=False, tail_trim=True), (), 0, None, None)
ok("8/9: each switch works on its own", 109 <= only_lead[0][0] <= 110.1 and only_lead[0][1] == t_off[0][1] and only_tail[0][0] == t_off[0][0] and only_tail[0][1] <= 128.6, (only_lead, only_tail))

# 10: spread
sc.AN.clear()
flat = np.zeros(400)
for c, h in ((50, 10.0), (90, 9.6), (300, 8.0)): flat[c - 3:c + 3] = h
sc.AN.update(marks=vcsmart.word_marks([], 400), curves=None, onsets=[], quiet=np.zeros(400, bool), clues=None, cover=np.ones(400))
o_ = sc.get_opts({"smart": True, "variety": False, "skip_greet": False, "lead_trim": False, "tail_trim": False})
j_off, _, _ = sc.smart_plan(flat, [], 2, 15, 25, None, "mix", prof, dict(o_, spread=False), (), 0, None, None)
j_on, _, _ = sc.smart_plan(flat, [], 2, 15, 25, None, "mix", prof, dict(o_, spread=True), (), 0, None, None)
mids = lambda js: sorted(round((a + b) / 2) for a, b, _ in js)
print("spread off:", mids(j_off), "on:", mids(j_on))
ok("10: without spreading the two best (close) moments are chosen", len(j_off) == 2 and max(mids(j_off)) < 150, mids(j_off))
ok("10: with spreading the far moment replaces the close one", len(j_on) == 2 and max(mids(j_on)) > 250, mids(j_on))

print("FAILS:", bad)
sys.exit(1 if bad else 0)
