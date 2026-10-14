"""Tests for vctools.py (the Tools window helpers). Uses a throw-away HOME so nothing real is touched."""
import os, sys, tempfile, time, json, csv, shutil
TMP = tempfile.mkdtemp(prefix="t_tools_")
os.environ["HOME"] = TMP; os.environ["USERPROFILE"] = TMP
import paths
import vctools as T, vcsmart, vcmore
F = [0]
def ck(name, cond, extra=""):
    if not cond: F[0] += 1
    print(("PASS " if cond else "FAIL ") + name + ((" - " + str(extra)) if (extra and not cond) else ""))

# --- watch folder
w = os.path.join(TMP, "watch"); os.makedirs(w)
def mk(n, size=300_000, age=100):
    p = os.path.join(w, n); open(p, "wb").write(b"0" * size); t = time.time() - age; os.utime(p, (t, t)); return p
a = mk("old.mp4", age=500); b = mk("new.mkv", age=60); c = mk("writing.mp4", age=3); d = mk("tiny.mp4", size=100); e = mk("x.mp4.part", age=500); f = mk("notes.txt"); g = mk(".hidden.mp4")
r = T.scan_watch(w, [])
ck("watch: finished videos only, oldest first", r == [a, b], r)
ck("watch: seen skipped", T.scan_watch(w, [a]) == [b])
ck("watch: seen with different spelling of the path", T.scan_watch(w, [os.path.join(w, ".", "old.mp4")]) == [b])
ck("watch: bad folder", T.scan_watch(os.path.join(TMP, "nope"), []) == [] and T.scan_watch("", []) == [])
ck("watch: remember", T.remember_seen(["x"], [a, a]) == [os.path.normpath("x"), os.path.normpath(a)] or len(T.remember_seen(["x"], [a, a])) == 2)
ck("watch: cap", len(T.remember_seen([str(i) for i in range(700)], [a])) == 600)

# --- kit parsing, CSV
outd = os.path.join(TMP, "out", "Shorts"); os.makedirs(outd)
clip = os.path.join(outd, "a_short1.mp4"); open(clip, "wb").write(b"x")
open(os.path.join(outd, "a_short1.txt"), "w", encoding="utf-8").write("HYPE SCORE  87/100\n\nWHY THIS MOMENT\n  Kind of clip: 😂 Reaction\n  - big laugh\n\nTITLE IDEAS\n  1. =HYPERLINK(\"x\") she DIED 💀\n  2. other\n\nDESCRIPTION\nline one\n\nline two\n\nHASHTAGS\n#vtuber #funny\n")
k = T.read_kit(clip)
ck("kit: parse", k["title"].startswith("=HYPERLINK") and k["hype"] == 87 and k["tags"] == "#vtuber #funny" and "line two" in k["desc"] and k["kind"].endswith("Reaction"), k)
ck("kit: missing file", T.read_kit(os.path.join(outd, "nope.mp4"))["title"] == "")
rows = T.post_rows([clip], posted={os.path.normpath(clip): ["TikTok", "YouTube"]}, fav=[clip], ledger=lambda p: dict(vod="/v/stream.mp4", start=3725, dur=34.2, kind="reaction"), tags=lambda p: ["funny", "boss"])
ck("csv: row", rows[0]["Posted to"] == "TikTok, YouTube" and rows[0]["Favourite"] == "yes" and rows[0]["Starts at"] == "1:02:05" and rows[0]["Source video"] == "stream.mp4", rows[0])
cp = os.path.join(TMP, "sheet.csv"); n = T.write_csv(cp, rows)
back = list(csv.DictReader(open(cp, encoding="utf-8-sig")))
ck("csv: written and readable", n == 1 and back[0]["Title"].startswith("'=HYPERLINK") and back[0]["Description"].count("\n") >= 2 and back[0]["My tags"] == "funny, boss", back)
ck("csv: bad path", T.write_csv(os.path.join(TMP, "no", "dir", "x.csv"), rows) == 0)
ck("csv: negative numbers kept", T._csv_safe("-5") == "-5" and T._csv_safe("-x") == "'-x" and T._csv_safe(None) == "")

# --- tags + search
ck("tags: split by space", T.split_words("funny boss  jumpscare") == ["funny", "boss", "jumpscare"])
ck("tags: split by comma", T.split_words("funny, boss fight; #Cute\nfunny") == ["funny", "boss fight", "Cute"], T.split_words("funny, boss fight; #Cute\nfunny"))
ck("tags: long dropped / limit", T.split_words("x" * 40) == [] and len(T.split_words(",".join(str(i) for i in range(30)))) == 12)
T.set_clip_tags(clip, "funny, boss fight"); ck("tags: stored", T.clip_tags(clip) == ["funny", "boss fight"])
T.set_clip_tags(clip, ""); ck("tags: removed", T.clip_tags(clip) == [])
ck("search: all words", T.clip_matches("died vtuber", clip) and T.clip_matches("short1", clip) and not T.clip_matches("minecraft", clip))
ck("search: tags and posted", T.clip_matches("boss", clip, tags=["boss fight"]) and T.clip_matches("tiktok", clip, posted="posted: TikTok") and T.clip_matches("", clip))
ck("search: kind", T.clip_matches("reaction", clip))

# --- hashtag bank
ck("bank: split", T.split_tags("#cute funny, #Minecraft; #cute 😀") == ["cute", "funny", "Minecraft"], T.split_tags("#cute funny, #Minecraft; #cute 😀"))
b = T.bank_load(); ck("bank: empty", b == dict(always=[], games={}, kinds={}))
b["always"] = T.split_tags("#vtuber #envtuber"); b["games"]["minecraft"] = T.split_tags("minecraft mc"); b["kinds"]["reaction"] = T.split_tags("reaction funny")
ck("bank: save", T.bank_save(b))
ck("bank: tags for game+kind", T.bank_tags("Minecraft", "reaction") == ["vtuber", "envtuber", "minecraft", "mc", "reaction", "funny"], T.bank_tags("Minecraft", "reaction"))
ck("bank: other game", T.bank_tags("Elden Ring", "") == ["vtuber", "envtuber"])
open(T.BANK_FILE, "w").write("{broken"); ck("bank: broken file", T.bank_load() == dict(always=[], games={}, kinds={}))
open(T.BANK_FILE, "w").write(json.dumps(dict(always="no", games=[1], kinds={"a": "b", "": ["x"]}))); ck("bank: wrong types", T.bank_load() == dict(always=[], games={}, kinds={}))

# --- look codes
look = dict(style="mix", lmin=20, lmax=40, gap=1.5, layout="stack", aspect="9:16", fx={"zoom": True, "shake": False}, intensity="Hype", accent="ff4d8d",
            opts=dict(cap_style="pop", cap_font="Arial", logo="C:/me/logo.png", handle="@me", music="C:/m.mp3", cap_emph=True, bad=[1, 2]))
code = T.look_code(look, "Mia's look")
ck("look: prefix and one line", code.startswith("VTLOOK1:") and "\n" not in code and len(code) < 1500, len(code))
nm, l2 = T.look_from_code("hey try this " + code + " !!")
ck("look: roundtrip", nm == "Mia's look" and l2["style"] == "mix" and l2["fx"] == {"zoom": True, "shake": False} and l2["opts"] == dict(cap_style="pop", cap_font="Arial", cap_emph=True), l2)
for bad in ("", "hello", "VTLOOK1:", "VTLOOK1:!!!!", "VTLOOK1:AAAA", code[:-8]):
    try: T.look_from_code(bad); ok = False
    except ValueError as ex: ok = len(str(ex)) > 10
    ck("look: rejects " + repr(bad[:14]), ok)
import zlib, base64
bomb = "VTLOOK1:" + base64.urlsafe_b64encode(zlib.compress(b'{"n":"","l":{"x":"' + b"a" * 5_000_000 + b'"}}', 9)).decode()
try: T.look_from_code(bomb); ok = False
except ValueError: ok = True
ck("look: oversize rejected", ok)

# --- cam memory
ck("cam: none", T.cam_get("Minecraft") == "")
ck("cam: bad box refused", not T.cam_put("Minecraft", "1,2,3") and not T.cam_put("", "1:2:3:4"))
ck("cam: stored", T.cam_put("Minecraft", "480:270:40:40", "1920x1080") and T.cam_get("minecraft ") == "480:270:40:40")
ck("cam: size must match", T.cam_get("Minecraft", "1920x1080") == "480:270:40:40" and T.cam_get("Minecraft", "1280x720") == "")
store = json.load(open(T.STORE)); store["cams"]["old"] = "10:10:0:0"; json.dump(store, open(T.STORE, "w"))
ck("cam: entry from an earlier beta still works", T.cam_get("old", "1280x720") == "10:10:0:0")
ck("cam: newest is kept when over the limit", all(T.cam_put(f"g{i}", "1:1:1:1") for i in range(90)) and T.cam_get("g89") and not T.cam_get("g0"))

# --- spread times
import datetime as _dt
now = _dt.datetime(2026, 10, 13, 20, 30)
ts = T.spread_times([(19, 0), (21, 0), (15, 0)], 5, now)
ck("times: next slots in order", ts == [_dt.datetime(2026, 10, 13, 21, 0), _dt.datetime(2026, 10, 14, 15, 0), _dt.datetime(2026, 10, 14, 19, 0), _dt.datetime(2026, 10, 14, 21, 0), _dt.datetime(2026, 10, 15, 15, 0)], ts)
ck("times: none asked / odd slots", T.spread_times([(19, 0)], 0, now) == [] and len(T.spread_times([], 2, now)) == 2 and len(T.spread_times([(25, 70)], 1, now)) == 1)

# --- vocabulary
ck("vocab: split", T.split_vocab("Bonk, sheesh; two words\nPOG") == ["bonk", "sheesh", "pog"])
v = T.vocab_load(); ck("vocab: empty", all(x == [] for x in v.values()) and "laugh" in v)
v["laugh"] = T.split_vocab("kek, heh"); v["hype"] = T.split_vocab("chat, clipit"); ck("vocab: save", T.vocab_save(v))
vcsmart._VOC["stamp"] = "unset"
words = [dict(w="kek", start=2.2, end=2.5), dict(w="clipit!", start=5.1, end=5.4), dict(w="hello", start=7.0, end=7.2)]
m = vcsmart.word_marks(words, 10)
ck("vocab: marks use the taught words", m["laugh"][2] == 1 and m["hype"][5] == 1 and m["laugh"].sum() == 1, (m["laugh"], m["hype"]))
os.remove(vcsmart.VOCAB_FILE); m = vcsmart.word_marks(words, 10)
ck("vocab: file gone -> back to normal", m["laugh"].sum() == 0 and m["hype"].sum() == 0)
open(vcsmart.VOCAB_FILE, "w").write("{oops"); ck("vocab: broken file ignored", vcsmart.word_marks(words, 10)["laugh"].sum() == 0)
tdir = os.path.join(TMP, "out", "Shorts")
for i in range(4):
    c_ = os.path.join(tdir, f"v{i}.mp4"); open(c_, "wb").write(b"x")
    open(os.path.join(tdir, f"v{i}_transcript.txt"), "w", encoding="utf-8").write("0:01 okay so the sheesh moment\n0:05 skibidi toilet and then the zorp happened\n0:09 the zorp again\n")
    c_ = os.path.join(tdir, f"b{i}.mp4"); open(c_, "wb").write(b"x")
    open(os.path.join(tdir, f"b{i}_transcript.txt"), "w", encoding="utf-8").write("0:01 okay so the moment happened\n0:05 chapter again and the dragon\n" + ("skibidi\n" if i == 0 else ""))
kept = [os.path.join(tdir, f"v{i}.mp4") for i in range(4)]; rest = [os.path.join(tdir, f"b{i}.mp4") for i in range(4)]
sug = T.suggest_vocab(kept, rest, known=["zorp"])
ck("vocab: suggestions = words typical for kept clips, not known, not common", [w for w, _ in sug] == ["skibidi", "toilet"] or [w for w, _ in sug] == ["toilet", "skibidi"], sug)
ck("vocab: without background, everyday words are still filtered", "okay" not in dict(T.suggest_vocab(kept)) and "again" not in dict(T.suggest_vocab(kept)) and "the" not in dict(T.suggest_vocab(kept)))
ck("vocab: too few clips -> nothing", T.suggest_vocab(kept[:2], rest) == [] and T.suggest_vocab([]) == [])

# --- resume
ck("resume: none", T.run_left() is None)
T.run_start(dict(mode="shorts", video="/v/x.mp4")); r = T.run_left()
ck("resume: noted", r and r["video"] == "/v/x.mp4" and r["started"])
T.run_end(); ck("resume: cleared", T.run_left() is None and not T.run_end())
open(T.RUNFILE, "w").write("[1,2]"); ck("resume: junk ignored", T.run_left() is None); os.remove(T.RUNFILE)

# --- moments file
ms = [dict(start=10.5, end=40, score=88, peak=20, text="hi", tags=["Laugh"]), dict(start=5, end=1, score=1), dict(bad=1), dict(start=100, end=130, score=60, peak=100, text="", tags=[])]
mp = os.path.join(TMP, "m.vtmoments"); n = T.moments_save(mp, "/v/x.mp4", ms)
vid, back = T.moments_load(mp)
ck("moments: saved + loaded (bad skipped)", n == 3 and vid == "/v/x.mp4" and [m_["start"] for m_ in back] == [10.5, 100.0], (n, back))
open(mp, "w").write("zzz"); ck("moments: broken file", T.moments_load(mp) == ("", []))
ck("moments: missing file", T.moments_load(os.path.join(TMP, "none")) == ("", []))
open(mp, "w").write(json.dumps(dict(moments=[dict(start="a", end=2), dict(start=1, end=1e9), dict(start=3, end=9, score=900, tags="x")])))
ck("moments: odd values cleaned", T.moments_load(mp)[1] == [dict(start=3.0, end=9.0, score=100, peak=3.0, text="", tags=[])], T.moments_load(mp))

# --- leftovers + cache
out = os.path.join(TMP, "out2"); sh = os.path.join(out, "Shorts"); vo = os.path.join(out, "VODs"); os.makedirs(sh); os.makedirs(vo)
os.makedirs(os.path.join(out, ".vclip_abc")); open(os.path.join(out, ".vclip_abc", "g.txt"), "w").write("x" * 1000)
os.makedirs(os.path.join(sh, "stream", ".vclip_zzz"))
open(os.path.join(sh, "ok.mp4"), "wb").write(b"x"); open(os.path.join(sh, "ok.txt"), "w").write("TITLE IDEAS\n"); open(os.path.join(sh, "ok_cover.jpg"), "wb").write(b"x")
open(os.path.join(sh, "gone_cover.jpg"), "wb").write(b"x"); open(os.path.join(sh, "gone.srt"), "w").write("1"); open(os.path.join(sh, "gone.txt"), "w").write("HYPE SCORE 5/100\nTITLE IDEAS\n")
open(os.path.join(sh, "mynotes.txt"), "w").write("my own notes, not a kit")
open(os.path.join(vo, "big.mp4"), "wb").write(b"x" * 5000); open(os.path.join(vo, "half.mp4.part"), "wb").write(b"x" * 10)
lo = T.find_leftovers(out); paths = {os.path.relpath(x["path"], out) for x in lo}
exp = {".vclip_abc", os.path.join("Shorts", "stream", ".vclip_zzz"), os.path.join("Shorts", "gone_cover.jpg"), os.path.join("Shorts", "gone.srt"), os.path.join("Shorts", "gone.txt"), os.path.join("VODs", "half.mp4.part")}
ck("leftovers: right things found, kept things not", paths == exp, paths ^ exp)
n, freed = T.remove_paths([x["path"] for x in lo]); ck("leftovers: removed", n == len(exp) and freed >= 1000 and os.path.isfile(os.path.join(sh, "ok.mp4")) and os.path.isfile(os.path.join(sh, "mynotes.txt")) and not T.find_leftovers(out), (n, freed))
ck("leftovers: bad folder", T.find_leftovers("") == [] and T.find_leftovers(os.path.join(TMP, "none")) == [])
vf = T.vod_files(out); ck("vods: listed", len(vf) == 1 and vf[0][1] == 5000 and vf[0][2] == 0)
cd = os.path.join(TMP, "cache"); os.makedirs(os.path.join(cd, "thumbs"))
for nme, sz in (("an3_a.npz", 1000), ("an2_b.npz", 500), ("vis1_c.npz", 700), ("made_x.json", 50), ("music_loudness.json", 20), (os.path.join("thumbs", "c_1.png"), 300)):
    open(os.path.join(cd, nme), "wb").write(b"x" * sz)
pv = os.path.join(TMP, "prev"); os.makedirs(pv); open(os.path.join(pv, "_preview1.gif"), "wb").write(b"x" * 90)
rep = {r["key"]: r for r in T.cache_report(cd, pv)}
ck("cache: report", rep["an"]["bytes"] == 2200 and rep["an"]["count"] == 3 and rep["thumbs"]["bytes"] == 300 and rep["misc"]["bytes"] == 20 and rep["previews"]["bytes"] == 90, rep)
ck("cache: clear analysis keeps 'made' list", T.cache_clear(cd, "an") == 2200 and os.path.isfile(os.path.join(cd, "made_x.json")) and not os.path.exists(os.path.join(cd, "an3_a.npz")))
ck("cache: clear thumbs/previews/misc", T.cache_clear(cd, "thumbs") == 300 and T.cache_clear(cd, "previews", pv) == 90 and T.cache_clear(cd, "misc") == 20 and os.path.isfile(os.path.join(cd, "made_x.json")))
ck("cache: missing dir", all(r["bytes"] == 0 for r in T.cache_report(os.path.join(TMP, "none"))) and T.cache_clear(os.path.join(TMP, "none"), "an") == 0)
ck("human sizes", T.human(0) == "0 B" and T.human(1536) == "1.5 KB" and T.human(5 * 2 ** 30) == "5.0 GB")

# --- health (uses the real engine module for ffmpeg)
import streamclip as sc
h = T.health(sc, os.path.join(TMP, "out3"), os.path.join(TMP, "..", "src"), cd)
ck("health: runs and names ffmpeg + disk", any("ffmpeg" in i["title"] for i in h) and any("free" in i["title"] for i in h) and all(i["level"] in ("ok", "warn", "bad") for i in h), [i["title"] for i in h])
class Fake: FF = "no_such_ffmpeg_xyz"; NOWIN = {}; APP_DIR = TMP
h2 = T.health(Fake, "", "", "")
ck("health: missing ffmpeg is reported", h2[0]["level"] == "bad" and "ffmpeg" in h2[0]["title"] and "problem" in T.health_summary(h2))
h3 = T.health(sc, "/proc/nope/x", "", "")
ck("health: unwritable save folder", any(i["level"] == "bad" and "save folder" in i["title"] for i in h3), [i["title"] for i in h3])
ck("health: summary ok", T.health_summary([dict(level="ok")]).startswith("Everything"))

# --- source
e = dict(vod=os.path.join(w, "old.mp4"), start=3725, end=3760, reasons=["a laugh", "a scream"], kind="reaction", made="2026-10-13 20:00")
s = T.source_of(e)
ck("source: info", s["when"] == "1:02:05" and s["vod_exists"] and "a laugh" in T.source_text(s) and "1:02:05" in T.source_text(s), T.source_text(s))
ck("source: missing vod text", "not on this PC" in T.source_text(T.source_of(dict(e, vod="/x/none.mp4"))))
ck("source: unknown", T.source_of(None) is None and "don't know" in T.source_text(None) and T.source_of(dict(vod="a", start="zz")) is None)

# --- ledger: deleted entries are kept for taste
vcmore.ledger_add(dict(path=os.path.join(TMP, "gone1.mp4"), vod="v", start=1, end=9, kind="story", dur=30)); vcmore.ledger_set(os.path.join(TMP, "gone1.mp4"), deleted=True)
vcmore.ledger_add(dict(path=os.path.join(TMP, "gone2.mp4"), vod="v", start=1, end=9, kind="story", dur=30))
n = vcmore.ledger_forget_missing()
ck("ledger: forget_missing keeps deleted-flag rows (for taste), drops other missing", n == 1 and len(vcmore.ledger_all()) == 1 and vcmore.ledger_all()[0].get("deleted"), (n, vcmore.ledger_all()))
print("FAILS:", F[0]); shutil.rmtree(TMP, ignore_errors=True); sys.exit(1 if F[0] else 0)
