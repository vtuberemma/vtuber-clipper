import sys, os, tempfile, shutil, subprocess
import paths; S = paths.ROOT
sys.path.insert(0, paths.APP)
import vcmore as M
FF = paths.FFMPEG
bad = 0
NW = dict(stdin=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
def ok(name, cond, extra=""):
    global bad
    print(("PASS " if cond else "FAIL ") + name, extra if not cond else "")
    if not cond: bad += 1

# parse_time
for s, v in [("", None), ("90", 90.0), ("1:23", 83.0), ("1:02:03", 3723.0), ("1h2m3s", 3723.0), ("5m", 300.0), ("45s", 45.0), ("abc", None), ("1:2:3:4", None), ("-5", None), ("1.5", 1.5), ("12:xx", None), ("2h", 7200.0)]:
    ok("parse_time(%r)" % s, M.parse_time(s) == v, M.parse_time(s))
# clean_opts
d = M.clean_opts(dict(smart="yes", cap_case="weird", cap_shadow="x", cap_words=99, cap_box=-4, extra_shapes="zz", range_from="10:00", range_to="5:00", chat_file=None))
ok("clean_opts bad values", d["smart"] is True and d["cap_case"] == "auto" and d["cap_shadow"] == 2 and d["cap_words"] == 7 and d["cap_box"] == 0 and d["extra_shapes"] == "" and d["range_from"] == "" and d["range_to"] == "" and d["chat_file"] == "", d)
d = M.clean_opts({})
ok("clean_opts empty gives defaults", all(k in d for k in M.DEFAULTS) and d["smart"] is True and d["variety"] is True and d["skip_greet"] is True and d["cap_shadow"] == 2)
d = M.clean_opts(dict(range_from="1:00", range_to="2:00"))
ok("clean_opts range ok", d["range_from"] == "1:00" and d["range_to"] == "2:00")
# apply_case
ok("apply_case", M.apply_case("Hi There", "upper", False) == "HI THERE" and M.apply_case("Hi There", "lower", True) == "hi there" and M.apply_case("Hi There", "normal", True) == "Hi There"
   and M.apply_case("Hi", "auto", True) == "HI" and M.apply_case("Hi", "auto", False) == "Hi")
ok("outline_size", M.outline_size(4, "thin") == 2 and M.outline_size(4, "huge") == 8 and M.outline_size(1, "thin") == 1 and M.outline_size(4, "nope") == 4)
ok("rainbow", len(M.rainbow_colors("&H00112233&", "x")) == 4)
ok("audio_extras", M.audio_extras({}) == "" and M.audio_extras({"hush": 1}).startswith(",afftdn") and "alimiter" in M.audio_extras({"tame": 1}))
x, y = M.hop_xy(1080, 1920, "w", "h", 20, 100, 200, 60)
ok("hop_xy", x.count("(") == x.count(")") and "mod(t,28.00)" in x and y.count("(") == y.count(")"), x)

# ffmpeg checks
td = tempfile.mkdtemp(prefix="vcmore_")
try:
    src = os.path.join(td, "src.mp4")
    r = subprocess.run([FF, "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=320x568:r=30:d=14", "-f", "lavfi", "-i", "sine=f=440:d=14:r=44100", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", src], capture_output=True, text=True)
    ok("make source", r.returncode == 0, r.stderr[-200:])
    venc = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "28"]
    p = M._probe(FF, src, NW); ok("probe", abs(p["dur"] - 14) < .3 and p["audio"] and p["w"] == 320 and p["h"] == 568 and abs(p["fps"] - 30) < .1, p)
    # hush / tame audio chains
    for name, chain in (("hush", M.HUSH), ("tame", M.TAME), ("both", M.HUSH + "," + M.TAME)):
        r = subprocess.run([FF, "-y", "-v", "error", "-i", src, "-vn", "-af", chain, "-f", "null", "-"], capture_output=True, text=True)
        ok("audio chain " + name, r.returncode == 0, r.stderr[-300:])
    for name, fn, kw in (("slowmo", M.slowmo, dict(t=5.0)), ("freeze", M.freeze, dict(t=6.0)), ("teaser", M.teaser, dict(t=7.0))):
        c = os.path.join(td, name + ".mp4"); shutil.copy(src, c)
        d0 = M._probe(FF, c, NW)["dur"]
        nd = fn(c, kw["t"], FF, NW, venc)
        pr = M._probe(FF, c, NW)
        ok(name + " returns new length", nd > 0 and abs(nd - pr["dur"]) < .05, (nd, pr))
        want = {"slowmo": d0 + 1.2, "freeze": d0 + .7, "teaser": d0 + 2.1}[name]
        ok(name + " length", abs(pr["dur"] - want) < .5, (pr["dur"], want))
        ok(name + " keeps audio+size", pr["audio"] and pr["w"] == 320 and pr["h"] == 568, pr)
        ok(name + " no temp left", not [f for f in os.listdir(td) if f.endswith((".slow.mp4", ".frz.mp4", ".tz.mp4"))])
    # refuses nonsense
    c = os.path.join(td, "x.mp4"); shutil.copy(src, c)
    ok("slowmo too early", M.slowmo(c, .1, FF, NW, venc) == 0 and M.freeze(c, .5, FF, NW, venc) == 0 and M.teaser(c, 2.0, FF, NW, venc) == 0 and M.slowmo(c, 13.5, FF, NW, venc) == 0)
    ok("missing file", M.slowmo(os.path.join(td, "none.mp4"), 5, FF, NW, venc) == 0 and M.finish_clip(os.path.join(td, "none.mp4"), {"slowmo": 1}, [5], FF, NW, venc) == [])
    c = os.path.join(td, "fin.mp4"); shutil.copy(src, c)
    done = M.finish_clip(c, dict(slowmo=True, freeze=True, teaser=True), [5.0, 9.0], FF, NW, venc)
    ok("finish_clip all three", done == ["slow-mo", "freeze frame", "teaser"], done)
    pr = M._probe(FF, c, NW); ok("finish_clip result plays", pr["dur"] > 14 + 3.5 and pr["audio"], pr)
    # silent clip (no audio)
    sil = os.path.join(td, "sil.mp4")
    subprocess.run([FF, "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=320x568:r=25:d=12", "-c:v", "libx264", "-pix_fmt", "yuv420p", sil], capture_output=True)
    ok("slowmo silent", M.slowmo(sil, 5, FF, NW, venc) > 12 and not M._probe(FF, sil, NW)["audio"])
    ok("freeze silent", M.freeze(sil, 5, FF, NW, venc) > 12)
    ok("teaser silent", M.teaser(sil, 6, FF, NW, venc) > 12)
finally:
    shutil.rmtree(td, ignore_errors=True)

# ledger
import vcmore
home = tempfile.mkdtemp(prefix="vcledger_")
vcmore.LEDGER = os.path.join(home, "l.json")
a = os.path.join(home, "a.mp4"); open(a, "w").write("x")
ok("ledger add", vcmore.ledger_add(dict(path=a, vod="v.mp4", start=10, end=40, kind="gameplay", dur=30)))
f = vcmore.ledger_find(a); ok("ledger find", f and f["kind"] == "gameplay" and f["made"])
ok("ledger set", vcmore.ledger_set(a, fav=True, tags=["x"]) and vcmore.ledger_find(a)["fav"] is True)
ok("ledger set missing", vcmore.ledger_set(os.path.join(home, "zz.mp4"), fav=True) is False)
vcmore.ledger_add(dict(path=a, kind="story", dur=44))
ok("ledger replace same path", len(vcmore.ledger_all()) == 1 and vcmore.ledger_find(a)["kind"] == "story")
vcmore.ledger_add(dict(path=os.path.join(home, "gone.mp4"), kind="x"))
ok("ledger forget missing", vcmore.ledger_forget_missing() == 1 and len(vcmore.ledger_all()) == 1)
open(vcmore.LEDGER, "w").write("{broken"); ok("ledger broken file", vcmore.ledger_all() == [] and vcmore.ledger_add(dict(path=a)))
shutil.rmtree(home, ignore_errors=True)
print("FAILS:", bad); sys.exit(1 if bad else 0)
