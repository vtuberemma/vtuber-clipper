"""Fuzz the option parser: every option gets silly values; get_opts must never raise and must hand the engine clean types."""
import os, sys, random, math, json
import paths
import streamclip as sc, vcmore
F = [0]
def ck(n, c, e=""):
    if not c: F[0] += 1
    print(("PASS " if c else "FAIL ") + n + ((" - " + str(e)) if (e and not c) else ""))
random.seed(5)
JUNK = [None, "", " ", "abc", "0", "-1", "999999999999", "1e400", "nan", "inf", float("nan"), float("inf"), -1e9, 1e9, True, False, [], [1, 2], {}, {"a": 1}, "\x00", "ñé日本語🙂", "a" * 5000, "\n\r\t", "{}", "%s%d", "../../etc/passwd", "C:\\x\\y", "#fff", 7, -3, 3.7]
bad = 0
for key, default in sc.OPTS.items():
    for v in JUNK:
        d = dict(sc.OPTS); d[key] = v
        try: r = sc.get_opts(d)
        except Exception as e: bad += 1; print("RAISED", key, repr(v)[:30], type(e).__name__, str(e)[:80]); continue
        if set(r) != set(sc.OPTS): bad += 1; print("KEYS", key, set(r) ^ set(sc.OPTS))
        if isinstance(default, bool) and not isinstance(r[key], bool): bad += 1; print("BOOL", key, repr(v)[:20], repr(r[key])[:20])
        if isinstance(default, (int, float)) and not isinstance(default, bool) and (not isinstance(r[key], (int, float)) or (isinstance(r[key], float) and not math.isfinite(r[key]))): bad += 1; print("NUM", key, repr(v)[:20], repr(r[key]))
        if isinstance(default, str) and not isinstance(r[key], str): bad += 1; print("STR", key, repr(v)[:20], repr(r[key])[:30])
ck("every option survives silly values (%d options x %d values)" % (len(sc.OPTS), len(JUNK)), bad == 0, bad)
# whole dict of random junk
bad = 0
for i in range(300):
    d = {k: random.choice(JUNK) for k in sc.OPTS}
    try: r = sc.get_opts(d); json.dumps(r)
    except Exception as e: bad += 1; print("RAISED", type(e).__name__, str(e)[:100])
ck("300 fully random option dicts", bad == 0, bad)
# missing keys / extra keys / not a dict
ck("empty / extra keys", sc.get_opts({}) == sc.get_opts(dict(sc.OPTS)) and sc.get_opts({"zzz": 1}).get("zzz") == 1 and sc.get_opts({"react_plan_t": [(1.0, "laugh")]})["react_plan_t"] == [(1.0, "laugh")])
for junk in (None, [], "x", 5):
    try: sc.get_opts(junk); ok = True
    except Exception: ok = False
    print(("PASS" if ok else "NOTE") + f" get_opts({junk!r}) {'ok' if ok else 'raises (callers always pass a dict)'}")
# 2.2 options are in the engine defaults and typed right
for k in vcmore.DEFAULTS: ck(f"engine knows option {k}", k in sc.OPTS)
d = sc.get_opts(dict(range_from="1:00:00", range_to="0:30:00")); ck("range with end before start is dropped", d["range_from"] == "" and d["range_to"] == "")
d = sc.get_opts(dict(cap_case="shout", cap_outline="huge!", extra_shapes="2:3")); ck("unknown names fall back", d["cap_case"] == "auto" and d["cap_outline"] == "normal" and d["extra_shapes"] == "")
# 2.3 options: in the engine defaults, typed right, cleaned
import vc23
for k in vc23.DEFAULTS: ck(f"engine knows 2.3 option {k}", k in sc.OPTS and type(sc.OPTS[k]) is type(vc23.DEFAULTS[k]))
d = sc.get_opts(dict(bg_dim=9999, bar_thick=-4, logo_alpha=1, maybe_below=1e9, bg_blur="x", bar_pos="x", privacy="x"))
ck("2.3 numbers are clamped and unknown names fall back", (d["bg_dim"], d["bar_thick"], d["logo_alpha"], d["maybe_below"], d["bg_blur"], d["bar_pos"], d["privacy"]) == (50, 4, 20, 100, "normal", "bottom", "warn"), d)
d = sc.get_opts(dict(private_words="  Mia Tanaka ,, SAKURA town;mia tanaka\n\nx\n" + "y" * 100)); ck("private words are split, lower-cased, de-duplicated and length-limited", d["private_words"] == "mia tanaka\nsakura town", repr(d["private_words"]))
d = sc.get_opts(dict(gate="off", deess="0", cap_feel="no", soft_subs="False", gif_clip="yes")); ck("true / false words are understood", (d["gate"], d["deess"], d["cap_feel"], d["soft_subs"], d["gif_clip"]) == (False, False, False, False, True), d)
# the download options never raise, whatever they hold
import vcnet
bad = 0
for a_ in JUNK:
    for b_ in JUNK[:12]:
        try:
            args, notes = vcnet.ytdlp_args(dict(dl_from=a_, dl_to=b_, dl_rate=a_, dl_frags=b_, dl_cookie_file=a_))
            cmd, _n = vcnet.apply_download_options(["yt-dlp", "--concurrent-fragments", "4", "-o", "x.%(ext)s"], dict(dl_from=a_, dl_to=b_, dl_rate=a_, dl_frags=b_)); vcnet.name_part(cmd)
            assert all(isinstance(x, str) for x in args) and all(isinstance(x, str) for x in notes)
        except Exception as e: bad += 1; print("RAISED", repr(a_)[:20], repr(b_)[:20], type(e).__name__, str(e)[:80])
ck(f"download options survive {len(JUNK) * 12} silly combinations", bad == 0, bad)
# parse_time fuzz
bad = 0
for s_ in JUNK + ["1:2:3:4", "99:99:99", "-5", "1h", "m", "1:-3", "00:00:00", "0", "1,5", "１２:３０"]:
    try: r = vcmore.parse_time(s_)
    except Exception as e: bad += 1; print("RAISED", repr(s_)[:30], e); continue
    if r is not None and (not isinstance(r, float) or r < 0 or not math.isfinite(r)): bad += 1; print("BAD", repr(s_)[:30], r)
ck("parse_time never raises and never returns negative / NaN", bad == 0)
print("FAILS:", F[0]); sys.exit(1 if F[0] else 0)
