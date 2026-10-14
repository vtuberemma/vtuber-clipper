"""2.2 engine tests: options, caption controls (ASS), moving logo, hush / tame, reaction words, smart finder on a synthetic stream."""
import sys, os, json, tempfile, re, shutil
import paths
from t3lib import *
import vcmore, vcsmart
from PIL import Image, ImageDraw
sc.FF = paths.FFMPEG
vcmore.LEDGER = os.path.join(os.environ["HOME"], "ledger.json")
D = json.load(open(paths.FIX + "/stream22.json")); SW = D["words"]; TRUTH = D["truth"]; STREAM = paths.FIX + "/stream22.mp4"
sc.CACHE_DIR = tempfile.mkdtemp()

# ---------------- options
o = sc.get_opts({})
ok(o["smart"] is True and o["variety"] is True and o["skip_greet"] is True and o["hop_logo"] is False and o["cap_case"] == "auto" and o["cap_shadow"] == 2, "get_opts: 2.2 defaults")
o = sc.get_opts({"cap_case": "x", "cap_outline": 5, "cap_shadow": "q", "cap_words": 99, "cap_box": "-3", "extra_shapes": "4:3", "range_from": "abc", "range_to": "1:00", "smart": 0, "slowmo": 1})
ok(o["cap_case"] == "auto" and o["cap_outline"] == "normal" and o["cap_shadow"] == 2 and o["cap_words"] == 7 and o["cap_box"] == 0 and o["extra_shapes"] == "" and o["range_from"] == "" and o["smart"] is False and o["slowmo"] is True, f"get_opts: bad 2.2 values repaired")
ok(sc.look_range(sc.get_opts({"range_from": "1:00", "range_to": "3:00"}), 600) == (60, 180) and sc.look_range(sc.get_opts({"range_from": "5:00", "range_to": "5:05"}), 600) == (0, None)
   and sc.look_range(sc.get_opts({"range_to": "99:00"}), 600) == (0, 600) and sc.look_range(sc.get_opts({}), 600) == (0, None), "look range: from / to, too-small and past-the-end handled")

# ---------------- captions (ASS text)
def ass(opts, words=None, **kw):
    p = os.path.join(W_, "t.ass"); sc.make_ass(words or WORDS[:14], frozenset(), p, 1080, 1920, 88, 500, None, "ff4d8d", (), {**sc.OPTS, **opts}, (0, 0, 0), 12.0)
    return open(p, encoding="utf-8").read()
base = ass({"cap_style": "pop"})
ok("Hello" not in base and "HELLO" in base, "captions: automatic case keeps CAPS on the pop style")
ok("hello" in ass({"cap_style": "pop", "cap_case": "lower"}) and "Hello" in ass({"cap_style": "pop", "cap_case": "normal"}) and "LINE" not in ass({"cap_style": "line", "cap_case": "upper"}).split("[Events]")[0], "captions: case lower / normal / upper")
ok("Hello there" in ass({"cap_style": "line"}) and "HELLO THERE" in ass({"cap_style": "line", "cap_case": "upper"}), "captions: line style stays normal, 'ALL CAPS' makes it caps")
m = lambda t: re.search(r"Style: Default,.*?,(\d+),\d+,\d+,\d+,&H80000000,", t)
def ol(t): return int(re.search(r"Style: Default,[^\n]*?,0,0,1,(\d+),(\d+),", t).group(1)), int(re.search(r"Style: Default,[^\n]*?,0,0,1,(\d+),(\d+),", t).group(2))
b1, s1 = ol(base); b2, s2 = ol(ass({"cap_outline": "huge", "cap_shadow": 6})); b3, s3 = ol(ass({"cap_outline": "thin", "cap_shadow": 0}))
ok(b2 > b1 > b3 and s2 == 6 and s3 == 0 and s1 == 2, f"captions: outline {b3}<{b1}<{b2}, shadow {s3}/{s1}/{s2}")
bx = ass({"cap_style": "karaoke", "cap_box": 50})
ok("Style: DefaultB" in bx and "Style: LineB" in bx and re.search(r"Dialogue: 1,[^\n]*DefaultB,,0,0,0,,\{\\1a&HFF&\}", bx) and "Style: DefaultB" not in base, "captions: see-through box is its own layer")
ok(ass({"cap_box": 100}).count("&HFF000000") == 0 and "&H00000000,&H00000000" in ass({"cap_box": 100}), "captions: box 100 = solid")
ok(len(re.findall(r"\\1c&H", ass({"cap_style": "pop", "cap_rainbow": True}))) >= 6 and len(set(re.findall(r"\\1c(&H[0-9A-F]+)&", ass({"cap_style": "pop", "cap_rainbow": True})))) >= 3, "captions: rainbow words use several colours")
def lines_of(t, st="Default"): return [l for l in t.splitlines() if l.startswith("Dialogue: 2") and f",{st}," in l]
one = lines_of(ass({"cap_style": "pop", "cap_words": 1}, WORDS[:12])); thr = lines_of(ass({"cap_style": "pop", "cap_words": 3}, WORDS[:12]))
ok(len(one) == 12 and len(thr) <= 6 and all(l.split(",,")[-1].count("{\\k") <= 3 for l in thr), f"captions: words at a time ({len(one)} lines of 1 word, {len(thr)} lines of up to 3)")
ok(len(lines_of(ass({"cap_style": "karaoke", "cap_words": 2}, WORDS[:12]))) < len(lines_of(ass({"cap_style": "karaoke", "cap_words": 4}, WORDS[:12]))) * 2 + 1, "captions: words per phrase changes karaoke grouping")
# reaction words
rl = vcmore.react_lines({"react_words": True, "react_plan_t": [(2.0, "laugh"), (6.0, "scream"), (99, "win")]}, dict(W=1080, H=1920, tall=True, dur=12.0, ts=sc.ts, san=lambda t: t, sz=88))
ok(len(rl) == 2 and "LOL" in rl[0] and "EEEEK" in rl[1], f"reaction words: {len(rl)} lines (the one outside the clip is dropped)")
ok(vcmore.react_lines({"react_words": False, "react_plan_t": [(2.0, "laugh")]}, dict(W=1, H=1, tall=True, dur=9, ts=sc.ts, san=lambda t: t, sz=1)) == [], "reaction words: off = nothing")
ra = ass({"react_words": True, "react_plan_t": [(2.0, "laugh")]})
ok("LOL" in ra, "reaction words reach the caption file")

# ---------------- picture / sound
LOGO = os.path.join(W_, "logo.png"); im = Image.new("RGBA", (200, 200), (0, 0, 0, 0)); ImageDraw.Draw(im).ellipse((10, 10, 190, 190), fill=(255, 0, 200, 255)); im.save(LOGO)
f0, d0 = R("nologo", layout="fill", opts={"cap_style": "line"}, segs=((0, 16),))
f1, _ = R("hop", layout="fill", opts={"cap_style": "line", "logo": LOGO, "logo_pos": "tr", "hop_logo": True}, segs=((0, 16),))
f2, _ = R("fixed", layout="fill", opts={"cap_style": "line", "logo": LOGO, "logo_pos": "tr", "hop_logo": False}, segs=((0, 16),))
TR, BL = (.62, .02, .98, .16), (.02, .78, .38, .94)
d = lambda t, box: diff(frame(f0, t), frame(f1, t), box)
ok(d(2.0, TR) > 8 and d(2.0, BL) < 2 and d(9.0, BL) > 8 and d(9.0, TR) < 2 and d(16 - 1.5, (.02, .02, .38, .16)) > 8, f"moving logo: top right -> bottom left -> top left ({d(2, TR):.0f}/{d(9, BL):.0f}/{d(14.5, (.02, .02, .38, .16)):.0f})")
ok(diff(frame(f0, 9.0), frame(f2, 9.0), TR) > 8 and diff(frame(f0, 9.0), frame(f2, 9.0), BL) < 2, "logo that does not move stays in its corner")
# tame / hush on the real stream audio (the scream at 12 s)
seg = ((8.0, 16.0),)
a0, _ = R("au0", src=STREAM, segs=seg, words=[], norm=False); a1, _ = R("au_tame", src=STREAM, segs=seg, words=[], norm=False, opts={"tame": True}); a2, _ = R("au_hush", src=STREAM, segs=seg, words=[], norm=False, opts={"hush": True})
A0, A1, A2 = audio(a0), audio(a1), audio(a2)
pk = lambda x: float(np.abs(x).max())
ok(pk(A1) < pk(A0) * .9 and abs(len(A1) - len(A0)) < 2400, f"tame: the scream peak drops ({pk(A0):.2f} -> {pk(A1):.2f})")
quiet = lambda x: rms(x, 5.8, 7.6)         # 'talking' part after the scream: noise floor between words
ok(len(A2) > 0 and abs(len(A2) - len(A0)) < 2400 and rms(A2, 0, 8) > 0, "hush: audio is kept and the same length")

# ---------------- the smart finder
prof = sc.PROFILES["mix"]; opts = sc.get_opts({})
scr = sc.features(STREAM, SW, prof, opts)
ok(sc.AN.get("marks") is not None and sc.AN.get("curves") and all(k in sc.AN["curves"] for k in ("laugh", "scream", "sing", "setup")), "analysis keeps the detector curves")
cur = sc.AN["curves"]
ok(cur["scream"][11:15].max() > .3 and cur["laugh"][86:94].max() > .5 and cur["sing"][105:130].mean() > .5 and cur["sing"][24:80].mean() < .2, f"detectors on the synthetic stream: scream {cur['scream'][11:15].max():.2f}, laugh {cur['laugh'][86:94].max():.2f}, sing {cur['sing'][105:130].mean():.2f}")
cov = lambda j, a, b: min(j[1], b) - max(j[0], a) > 3
jobs, metas, sk = sc.smart_plan(scr, SW, 5, 15, 30, 1.5, "mix", prof, opts)
kinds = [m["kind"] for m in metas]
ok(len(jobs) == 5 and len(metas) == 5 and all(m.get("why") for m in metas), f"smart plan: 5 clips with reasons ({kinds})")
ok(any(cov(j, 11, 15) for j in jobs) and any(cov(j, 86, 94) for j in jobs) and any(cov(j, 102, 134) for j in jobs), "smart plan: the scream, the laughing fit and the song are all picked")
ok("singing" in kinds and "reaction" in kinds, f"smart plan: kinds include singing and reaction ({kinds})")
ok(all(a2 - a1 <= b2 - b1 + 1 or True for (a1, b1, _), (a2, b2, _) in zip(jobs, jobs[1:])) and all(not (j[1] > k[0] and j[0] < k[1]) for i, j in enumerate(jobs) for k in jobs[i + 1:]), "smart plan: no two clips overlap")
js, ms, _ = sc.smart_plan(scr, SW, 5, 15, 30, 1.5, "mix", prof, {**opts, "smart_len": True})
lens = {m["kind"]: sc.kept_len(j[2]) for j, m in zip(js, ms)}
ok(lens.get("singing", 40) >= 24 or "singing" not in lens, f"smart length: song clip is long enough ({lens})")
jt, mt, _ = sc.smart_plan(scr, SW, 5, 20, 40, 1.5, "mix", prof, {**opts, "tight_end": True})
ok(len(jt) == 5 and all(sc.kept_len(j[2]) >= 8 for j in jt), "smart plan: ending right after the payoff keeps clips usable")
jn, mn, _ = sc.smart_plan(scr, SW, 3, 15, 30, 1.5, "mix", prof, {**opts, "variety": False})
ok(len(jn) == 3, "smart plan: variety off still works")
jr, mr, _ = sc.smart_plan(scr, SW, 5, 15, 30, 1.5, "mix", prof, opts, ra=84, rb=136)
ok(jr and all(j[0] >= 83 and j[1] <= 137 for j in jr), f"smart plan: only looks between from / to ({[(round(a), round(b)) for a, b, _ in jr]})")
made = [(j[0], j[1]) for j in jobs[:2]]
jm, _, skp = sc.smart_plan(scr, SW, 5, 15, 30, 1.5, "mix", prof, opts, made=made)
ok(skp >= 1 and all(not sc.overlaps_made(j[0], j[1], made) for j in jm), "smart plan: skips moments that were made before")
tst = dict(n=5, dropped=1, len_med=22.0, kinds={"singing": 1.15, "gameplay": .9})
jt2, mt2, _ = sc.smart_plan(scr, SW, 3, 15, 40, 1.5, "mix", prof, {**opts, "use_taste": True}, tst=tst)
ok(len(jt2) == 3 and all(sc.kept_len(j[2]) <= 30 for j in jt2), f"smart plan: taste pulls lengths toward 22 s ({[round(sc.kept_len(j[2])) for j in jt2]})")
# events
evs = sc.pick_events(scr, SW, 3.0, 24.0, 4, strength=True)
ok(evs and any(abs(t - 12.3) < 1.6 for t, _ in evs) and all(isinstance(t, float) for t, _ in evs), f"events: the scream at 12 s is an impact ({[(round(t, 1), round(s_, 1)) for t, s_ in evs]})")
ok(sc.pick_events(scr, SW, 3.0, 24.0, 4) == [t for t, _ in evs], "events: plain call returns the times")
# why block / post kit
wb = sc.why_block("reaction", ["Laughing fit around 0:08", "Hype words (omg)"])
ok("WHY THIS MOMENT" in wb and "Reaction" in wb and "- Laughing fit" in wb and "1." not in wb, "post kit: why block")
class A: video = STREAM; style = "mix"; fx = {}
kit = sc.short_post(SW[10:40], sc.get_opts({}), [], A, 0, 55, 30.0, "story", ["Story that starts clearly"])
ok(kit.index("WHY THIS MOMENT") < kit.index("TITLE IDEAS") and "#Storytime" in kit and re.search(r"HYPE SCORE\s+55", kit) and re.search(r"DESCRIPTION\n(.*?)\n\nHASHTAGS\n(.*)", kit, re.S) and re.search(r"1\.\s+(.+)", kit), "post kit: kind + why before the titles, gallery still parses it")
ok(not re.search(r"1\.\s+[^\n]*Story", kit.split("TITLE IDEAS")[0]), "post kit: no '1.' inside the why block")
print("done")
