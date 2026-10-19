"""2.3 privacy and safety (vcsafe): the privacy guard (patterns + private words, both directions: it must catch real slips and leave normal talk alone), word marking and bleeping,
text scrubbing, the privacy scan, flash safety on real strobing video, the clip check on real files, the disk guard."""
from t3lib import *
import vcsafe, vcmedia, vcmore

FF = paths.FFMPEG
_n, _ok = [0], ok
def ok(c, m):
    if not c: _n[0] += 1
    _ok(bool(c), m)


def sh(args, timeout=180):
    return subprocess.run([FF, "-y", "-v", "error"] + args, capture_output=True, timeout=timeout)


def toks(text):
    return text.split()


def hit_text(text):
    t = toks(text); hs = vcsafe.privacy_hits(t)
    return [(k, " ".join(t[a:b + 1])) for a, b, k in hs]


def kinds(text):
    return [k for k, _ in hit_text(text)]


# ---------------------------------------------------------------- 29 privacy guard: things that must be caught
cases = [
    ("email", "you can email me at mia at gmail dot com thanks", "mia at gmail dot com"),
    ("email", "reach me at hello@mia.gg for business", "hello@mia.gg"),
    ("email", "send it to mia dot v at example dot net please", "mia dot v at example dot net"),
    ("email", "my email is mia at gmail", "mia at gmail"),
    ("email", "it is john at outlook dot co dot uk right", "john at outlook dot co dot uk"),
    ("link", "check out www.mia.gg/links later", "www.mia.gg/links"),
    ("link", "find me on twitch dot tv slash mia", "twitch dot tv"),
    ("phone", "call me at five five five one two three four", "five five five one two three four"),
    ("phone", "my number is 555 123 4567 okay", "555 123 4567"),
    ("phone", "it is 555-123-4567 really", "555-123-4567"),
    ("phone", "text me at 5 5 5 1 2 3 4 5 6 7 now", "5 5 5 1 2 3 4 5 6 7"),
    ("address", "I live at 123 Main Street in town", "123 Main Street"),
    ("address", "my address is 42 Oak Lane Springfield and more", "42 Oak Lane Springfield"),
    ("address", "send mail to 9 Cherry Blossom Road please", "9 Cherry Blossom Road"),
    ("name", "my real name is Jane Doe and I stream", "Jane Doe"),
    ("name", "my real name is Jane.", "Jane."),
    ("name", "okay so my legal name is Taro Yamada ok", "Taro Yamada"),
]
for kind, text, expect in cases:
    h = hit_text(text)
    ok(any(k == kind and expect in t or (k == kind and t in expect and len(t) >= len(expect) - 2) for k, t in h), f"privacy guard catches {kind}: “{text}” -> {h}")

# ---------------------------------------------------------------- ... and normal talk it must leave alone
clean_talk = [
    "I got 100 subs and 2000 views today and hit level 50",
    "the countdown was five four three two one go",
    "my number one fan is chat",
    "my number is one thing I always say",
    "I live at the end of the road",
    "my email is in the description below",
    "my real name is a secret",
    "my real name is not important",
    "oh oh oh oh oh oh oh oh",
    "one one one one one one one one",
    "I was at the polka dot co op yesterday",
    "we raised 1000000 for charity",
    "look at this dot com bubble",
    "no way no way no way that actually happened to me",
    "the boss has 5000 health and does 300 damage",
    "round 3 of the match at the street fighter tournament",
    "I live in a tiny house",
    "you can reach the secret room at the end",
]
for text in clean_talk:
    ok(hit_text(text) == [], f"privacy guard leaves alone: “{text}” {hit_text(text)}")

# ---------------------------------------------------------------- partial / odd inputs
ok(vcsafe.privacy_hits([]) == [] and vcsafe.privacy_hits(["my", "real", "name", "is"]) == [] and vcsafe.privacy_hits(["call", "me", "at"]) == [], "privacy guard: empty or cut-off sentences")
dw = [dict(w=x, start=i * .3, end=i * .3 + .25) for i, x in enumerate(toks("so my number is 555 123 4567 call me"))]
ok(vcsafe.privacy_hits(dw) == vcsafe.privacy_hits([d["w"] for d in dw]), "privacy guard: works on word dicts and on plain strings the same")
ok(all(isinstance(a, int) and isinstance(b, int) and a <= b for a, b, _ in vcsafe.privacy_hits(toks("email me at a at b dot com or 555 123 4567 or www.x.com")))
   and [h for h in vcsafe.privacy_hits(toks("email me at a at b dot com or 555 123 4567 or www.x.com"))] == sorted(vcsafe.privacy_hits(toks("email me at a at b dot com or 555 123 4567 or www.x.com"))), "privacy guard: hits are ordered and never overlap")
long_text = toks("my real name is " * 3 + "x " * 3000)
ok(isinstance(vcsafe.privacy_hits(long_text), list), "privacy guard: a very long transcript is handled")

# ---------------------------------------------------------------- 30 my private words
W = lambda s: [dict(w=x, start=i * .3, end=i * .3 + .25) for i, x in enumerate(toks(s))]
ok(vcsafe.private_hits(W("my dog Kiki is great"), ["kiki"]) == [(2, 2, "private")], "private word found (any capitals)")
ok(vcsafe.private_hits(W("Kiki's toys and Kikis bowl"), ["kiki"]) == [(0, 0, "private")], "private word: 's counts, a different word does not")
ok(vcsafe.private_hits(W("we went to the blue house on elm"), ["blue house"]) == [(4, 5, "private")], "private phrase of two words")
ok(vcsafe.private_hits(W("a blue car and a house"), ["blue house"]) == [], "private phrase only when said in a row")
ok(vcsafe.private_hits(W("hello there"), []) == [] and vcsafe.private_hits(W("hello there"), [""]) == [] and vcsafe.private_hits([], ["x"]) == [], "no private words / nothing said")
ok(vcsafe.private_hits(W("鈴木さんが来ました"), ["鈴木"]) == [(0, 0, "private")], "private word inside Japanese text (no spaces between words)")
ok(vcsafe.private_hits(W("Kiki, Kiki! kiki."), ["Kiki"]) == [(0, 0, "private"), (1, 1, "private"), (2, 2, "private")], "private word with punctuation")

# ---------------------------------------------------------------- word marking and modes
spoken = W("so my number is 555 123 4567 and my dog Kiki is cute")
for mode, expect_pat, expect_priv in (("off", False, False), ("warn", "pwarn", "priv"), ("bleep", "priv", "priv")):
    out, rep = vcsafe.mark_words(spoken, dict(privacy=mode, private_words="Kiki"))
    phone_flag = [next((k for k in ("priv", "pwarn") if w.get(k)), None) for w in out[4:7]]
    kiki_flag = next((k for k in ("priv", "pwarn") if out[10].get(k)), None)
    if mode == "off":
        ok(out is spoken and rep == [], "privacy off: nothing marked, nothing reported")
    else:
        ok(phone_flag == [expect_pat] * 3 and kiki_flag == expect_priv, f"privacy {mode}: number -> {expect_pat}, private word -> {expect_priv} ({phone_flag}, {kiki_flag})")
        ok(len(rep) == 2 and {r["kind"] for r in rep} == {"phone", "private"} and all(r["end"] > r["start"] for r in rep), f"privacy {mode}: report lists the two spots")
        ok(all(not any(k in out[i] for k in ("priv", "pwarn")) for i in (0, 1, 2, 3, 7, 8, 9, 11, 12)), f"privacy {mode}: words around the hit are not marked")
        ok(not any(("priv" in w or "pwarn" in w) for w in spoken), f"privacy {mode}: the original word list is not changed")
        ok(next(r for r in rep if r["kind"] == "private")["bleep"] is True and next(r for r in rep if r["kind"] == "phone")["bleep"] is (mode == "bleep"), f"privacy {mode}: report says what is bleeped")
ok(vcsafe.mark_words([], dict(privacy="bleep"))[1] == [] and vcsafe.mark_words(W("hello world"), dict(privacy="bleep"))[0] == W("hello world"), "marking: empty / harmless talk")
ok(vcsafe.mark_words(W("hello"), {})[1] == [] and vcsafe.mark_words(W("call me at 555 123 4567"), {})[1][0]["kind"] == "phone", "marking: missing options mean the default (warn)")

# ---------------------------------------------------------------- 32 text scrubbing
o_warn = dict(privacy="warn", private_words="Kiki, blue house")
ok(vcsafe.scrub_text("Call me at 555 123 4567 now", o_warn) == "Call me at *** *** **** now", "scrub_text: phone number starred, same length")
ok(vcsafe.scrub_text("Kiki steals the show", o_warn) == "**** steals the show", "scrub_text: private word starred")
ok(vcsafe.scrub_text("#Kiki #funny", o_warn) == "#**** #funny", "scrub_text: hashtag keeps its #")
ok(vcsafe.scrub_text("Kiki steals the show", o_warn, repl="") == "steals the show", "scrub_text: can remove instead of star")
ok(vcsafe.scrub_text("Call me at 555 123 4567 now", dict(privacy="off")) == "Call me at 555 123 4567 now", "scrub_text: privacy off leaves text alone")
ok(vcsafe.scrub_text("", o_warn) == "" and vcsafe.scrub_text(None, o_warn) is None, "scrub_text: empty / None")
ok(vcsafe.scrub_text("A normal title about the best clutch ever", o_warn) == "A normal title about the best clutch ever", "scrub_text: a normal title is unchanged")
ok(vcsafe.scrub_name("Kiki_clip_3", o_warn) == "clip 3" and vcsafe.scrub_name("Kiki", o_warn) == "clip", "scrub_name: private part left out of a file name; empty -> 'clip'")
ok("Kiki" not in vcsafe.scrub_text("the dog Kiki and Kiki's bowl", o_warn), "scrub_text: possessive form is scrubbed too")

# ---------------------------------------------------------------- 31 privacy scan: transcripts and subtitles
txt = "[0:14] so call me at 555 123 4567\n[1:02] and my email is mia at gmail dot com\n[1:30] nothing private here at all"
tw = vcsafe.words_from_text(txt)
ok(len(tw) > 10 and abs(tw[0]["start"] - 14) < .01 and all(tw[i]["start"] <= tw[i + 1]["start"] for i in range(len(tw) - 1)), "words_from_text: transcript lines with [m:ss] times")
rep = vcsafe.scan_report(tw, dict(privacy="warn"))
ok([r["kind"] for r in rep] == ["phone", "email"] and abs(rep[0]["start"] - 14.8) < 3 and 62 <= rep[1]["start"] <= 66, f"scan: phone and email found at the right time ({[(r['kind'], round(r['start'])) for r in rep]})")
srt = "1\n00:00:01,000 --> 00:00:04,000\nhello everyone\n\n2\n00:01:00,500 --> 00:01:03,500\nmy email is mia at gmail dot com\n"
sw = vcsafe.words_from_text(srt)
ok(sw and abs(sw[0]["start"] - 1.0) < .01 and any(abs(w["start"] - 60.5) < .6 for w in sw), "words_from_text: .srt cues")
ok([r["kind"] for r in vcsafe.scan_report(sw, dict(privacy="off"))] == ["email"], "scan: runs even when the guard is switched off (you asked for the scan)")
ok(vcsafe.words_from_text("") == [] and vcsafe.words_from_text("just some text without times") == [], "words_from_text: nothing to read -> no words")
rt = vcsafe.report_text(rep, "stream.srt")
ok("2 possible privacy hits" in rt and "stream.srt" in rt and "0:00:15" in rt and "(only reported)" in rt, "report_text: readable list with times")
ok(vcsafe.report_text([], "x").startswith("Nothing personal-looking"), "report_text: nothing found")

# ---------------------------------------------------------------- 27 flash safety on real video
def make_video(path, vf, dur=6, size="160x90", rate=25, extra=()):
    sh(["-f", "lavfi", "-i", f"color=c=black:s={size}:d={dur}:r={rate}", "-vf", vf, "-pix_fmt", "yuv420p", *extra, path])
    return path
STROBE = make_video(os.path.join(W_, "strobe.mp4"), "geq=lum='if(lt(mod(floor(T*12.5),2),1),230,10)':cb=128:cr=128")
SLOW = make_video(os.path.join(W_, "slow.mp4"), "geq=lum='if(lt(mod(floor(T*1),2),1),230,10)':cb=128:cr=128")
SUBTLE = make_video(os.path.join(W_, "subtle.mp4"), "geq=lum='if(lt(mod(floor(T*12.5),2),1),120,100)':cb=128:cr=128")
RAMP = make_video(os.path.join(W_, "ramp.mp4"), "geq=lum='255*T/6':cb=128:cr=128")
QUAD = make_video(os.path.join(W_, "quad.mp4"), "geq=lum='if(lt(X,80)*lt(Y,45)*lt(mod(floor(T*12.5),2),1),240,10)':cb=128:cr=128")
fs = vcsafe.flash_report(STROBE, FF, None)
ok(fs["checked"] and not fs["ok"] and fs["worst"] >= 5 and "Fast flashing" in fs["notes"], f"flash check: 12 flashes a second is flagged ({fs['worst']} per second)")
fl = vcsafe.flash_report(SLOW, FF, None)
ok(fl["checked"] and fl["ok"] and fl["worst"] <= 2, f"flash check: one flash a second is fine ({fl['worst']})")
fl = vcsafe.flash_report(SUBTLE, FF, None)
ok(fl["ok"], f"flash check: a faint flicker below the threshold is fine ({fl['worst']})")
fl = vcsafe.flash_report(RAMP, FF, None)
ok(fl["ok"] and fl["worst"] == 0, "flash check: a slow fade is fine")
fq = vcsafe.flash_report(QUAD, FF, None)
ok(fq["checked"] and not fq["ok"], f"flash check: strobing in one corner of the picture is caught ({fq['worst']})")
fl = vcsafe.flash_report(SRC, FF, None)
ok(fl["checked"] and fl["ok"], "flash check: the normal test stream is fine")
nf = vcsafe.flash_report(os.path.join(W_, "nope.mp4"), FF, None)
ok(nf["checked"] is False and nf["ok"] is True, "flash check: unreadable file -> 'not checked', no crash")
tiny = make_video(os.path.join(W_, "tiny1.mp4"), "null", dur=.1)
ok(vcsafe.flash_report(tiny, FF, None)["checked"] is False, "flash check: too short to judge")
a_, b_ = vcsafe.flash_counts([0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1], 12)[0], vcsafe.flash_counts([0.5] * 30, 25)[0]
ok(a_ >= 4 and b_ == 0 and vcsafe.flash_counts([], 25) == (0, 0.0) and vcsafe.flash_counts([0, 1], 25) == (0, 0.0), f"flash_counts: pure numbers ({a_} / {b_})")
ok(abs(vcsafe.luminance([0, 255])[1] - 1.0) < 1e-6 and vcsafe.luminance([0])[0] == 0, "luminance: black 0, white 1")

# ---------------------------------------------------------------- 28 clip check on real files
def levels(items):
    return {i["level"] for i in items}
def has(items, word, level=None):
    return any(word.lower() in i["text"].lower() and (level is None or i["level"] == level) for i in items)
TONE = "sine=f=300:d=20:r=44100"
GOOD = os.path.join(W_, "good.mp4")
sh(["-f", "lavfi", "-i", "testsrc2=s=270x480:d=20:r=25", "-f", "lavfi", "-i", TONE, "-filter_complex", "[1]volume=0.55[a]", "-map", "0:v", "-map", "[a]", "-pix_fmt", "yuv420p", "-shortest", GOOD])
REALNOWIN = dict(stdin=subprocess.DEVNULL, creationflags=0)          # what the app really passes (streamclip.NOWIN) - it already holds a stdin entry
ldr = vcsafe.loudness(GOOD, FF, REALNOWIN)
ok(ldr and ldr.get("lufs") is not None, f"loudness also works with the app's own subprocess settings ({ldr.get('lufs')})")
ok(vcsafe.lead_silence(GOOD, FF, REALNOWIN) is False, "lead_silence also works with the app's own subprocess settings")
ld = vcsafe.loudness(GOOD, FF, None)
ok(ld and -30 < ld["lufs"] < -5 and ld["peak"] is not None and ld["peak"] < 0, f"loudness: measured {ld.get('lufs')} LUFS, peak {ld.get('peak')} dB")
loud_t = ld["lufs"]
ci = vcsafe.clip_check(GOOD, FF, None, dict(loudness=str(round(loud_t))), "shorts")
ok(not has(ci, "length", "warn") and not has(ci, "not a tall", "warn") and not has(ci, "no sound") and not has(ci, "loudness is", "warn"), f"clip check: a normal tall 20 s clip passes ({[i['text'][:40] for i in ci if i['level'] != 'ok']})")
ci = vcsafe.clip_check(GOOD, FF, None, dict(loudness="-5"), "shorts")
ok(has(ci, "Loudness is", "warn"), "clip check: loudness far from the target is flagged")
LONG = os.path.join(W_, "long.mp4")
sh(["-f", "lavfi", "-i", "testsrc2=s=270x480:d=200:r=5", "-f", "lavfi", "-i", "sine=f=300:d=200:r=22050", "-pix_fmt", "yuv420p", "-shortest", "-c:a", "aac", "-b:a", "32k", LONG], 300)
ci = vcsafe.clip_check(LONG, FF, None, {}, "shorts")
ok(has(ci, "may not accept", "warn") and not has(vcsafe.clip_check(LONG, FF, None, {}, "tiktok"), "may not accept"), "clip check: 200 s is too long for Shorts, fine for TikTok")
ok(has(vcsafe.clip_check(LONG, FF, None, dict(platform="shorts"), ""), "may not accept"), "clip check: the platform comes from your Posting platform setting")
WIDE = os.path.join(W_, "wide.mp4")
sh(["-f", "lavfi", "-i", "testsrc2=s=480x270:d=10:r=25", "-f", "lavfi", "-i", "sine=f=300:d=10:r=44100", "-pix_fmt", "yuv420p", "-shortest", WIDE])
ok(has(vcsafe.clip_check(WIDE, FF, None, {}, "tiktok"), "not a tall picture", "warn") and not has(vcsafe.clip_check(WIDE, FF, None, {}, "x"), "not a tall"), "clip check: a wide picture is flagged for tall-video apps only")
MUTE = os.path.join(W_, "mute.mp4")
sh(["-f", "lavfi", "-i", "testsrc2=s=270x480:d=10:r=25", "-pix_fmt", "yuv420p", MUTE])
ok(has(vcsafe.clip_check(MUTE, FF, None, {}, "shorts"), "no sound", "warn"), "clip check: a clip without sound is flagged")
SILENT = os.path.join(W_, "silent_start.mp4")
sh(["-f", "lavfi", "-i", "testsrc2=s=270x480:d=10:r=25", "-f", "lavfi", "-i", "sine=f=300:d=10:r=44100", "-af", "volume=enable='lt(t,2)':volume=0", "-pix_fmt", "yuv420p", "-shortest", SILENT])
ok(has(vcsafe.clip_check(SILENT, FF, None, {}, "shorts"), "first second is silent", "warn"), "clip check: a silent first second is flagged")
ok(not has(vcsafe.clip_check(GOOD, FF, None, {}, "shorts"), "first second is silent"), "clip check: sound from the start is fine")
BLACK = os.path.join(W_, "black_start.mp4")
sh(["-f", "lavfi", "-i", "color=c=black:s=270x480:d=1:r=25", "-f", "lavfi", "-i", "testsrc2=s=270x480:d=9:r=25", "-f", "lavfi", "-i", "sine=f=300:d=10:r=44100", "-filter_complex", "[0][1]concat=n=2:v=1:a=0[v]", "-map", "[v]", "-map", "2:a", "-pix_fmt", "yuv420p", "-shortest", BLACK])
ok(has(vcsafe.clip_check(BLACK, FF, None, {}, "shorts"), "black picture", "warn"), "clip check: a black first frame is flagged")
ok(not has(vcsafe.clip_check(BLACK, FF, None, dict(fade="in"), "shorts"), "black picture"), "clip check: a black start is expected when a fade-in is on")
ok(not has(vcsafe.clip_check(GOOD, FF, None, {}, "shorts"), "black picture"), "clip check: a normal start is fine")
HOT = os.path.join(W_, "hot.mp4")
sh(["-f", "lavfi", "-i", "testsrc2=s=270x480:d=6:r=25", "-f", "lavfi", "-i", "sine=f=300:d=6:r=44100", "-af", "volume=8.0", "-pix_fmt", "yuv420p", "-shortest", HOT])
ok(has(vcsafe.clip_check(HOT, FF, None, dict(loudness="off"), "shorts"), "peaks at", "warn"), "clip check: sound at full scale is flagged (may crackle)")
SCREAM = os.path.join(W_, "scream.mp4")
sh(["-f", "lavfi", "-i", "testsrc2=s=270x480:d=12:r=25", "-f", "lavfi", "-i", "sine=f=300:d=12:r=44100", "-af", "volume='if(between(t,6,7),1.0,0.05)':eval=frame", "-pix_fmt", "yuv420p", "-shortest", SCREAM])
ok(has(vcsafe.clip_check(SCREAM, FF, None, dict(loudness="off"), "shorts"), "very loud moment", "warn"), "clip check: one very loud moment among quiet talk is flagged with its time")
ok(has(vcsafe.clip_check(STROBE, FF, None, {}, "shorts"), "flashing", "bad") and vcsafe.worst_level(vcsafe.clip_check(STROBE, FF, None, {}, "shorts")) == "bad", "clip check: strobing counts as a problem to fix")
ok(not has(vcsafe.clip_check(STROBE, FF, None, dict(flash_check=False), "shorts"), "flashing"), "clip check: flash check can be left out")
ci = vcsafe.clip_check(os.path.join(W_, "nope.mp4"), FF, None, {}, "shorts")
ok(len(ci) == 1 and ci[0]["level"] == "bad" and "missing" in ci[0]["text"], "clip check: missing file")
junk = os.path.join(W_, "junk.mp4"); open(junk, "wb").write(b"not a video" * 50)
ci = vcsafe.clip_check(junk, FF, None, {}, "shorts")
ok(len(ci) == 1 and ci[0]["level"] == "bad", "clip check: a broken file is reported, not a crash")
ct = vcsafe.check_text([dict(level="ok", text="fine"), dict(level="warn", text="hmm"), dict(level="bad", text="no")], "a.mp4")
ok(ct.startswith("CLIP CHECK a.mp4") and "[OK  ] fine" in ct and "[WARN] hmm" in ct and "[FIX ] no" in ct, "check_text: plain list with OK / WARN / FIX")
ok(vcsafe.worst_level([]) == "ok" and vcsafe.worst_level([dict(level="ok"), dict(level="warn")]) == "warn" and vcsafe.worst_level([dict(level="warn"), dict(level="bad")]) == "bad", "worst_level")
ok(vcsafe.lead_silence(SILENT, FF, None) is True and vcsafe.lead_silence(GOOD, FF, None) is False and vcsafe.lead_silence(MUTE, FF, None) is False and vcsafe.lead_silence(junk, FF, None) is False, "lead_silence: silent / sound / no sound / broken")

# ---------------------------------------------------------------- 39 disk guard
lvl, msg, free = vcsafe.disk_check(tempfile.gettempdir(), 50)
ok(lvl == "ok" and msg == "" and free > 0, f"disk guard: plenty of room -> ok ({free / 1000:.0f} GB free)")
lvl, msg, _ = vcsafe.disk_check(tempfile.gettempdir(), free * 5)
ok(lvl == "stop" and "free" in msg and "Tools" in msg, "disk guard: not enough room -> stop, with advice")
lvl, msg, _ = vcsafe.disk_check(tempfile.gettempdir(), free / 1.5)
ok(lvl == "warn" and msg, "disk guard: nearly full afterwards -> warn")
lvl, msg, f2 = vcsafe.disk_check(os.path.join(tempfile.gettempdir(), "does", "not", "exist", "yet"), 10)
ok(lvl == "ok" and f2 > 0, "disk guard: a folder that does not exist yet is measured on its parent")
ok(vcsafe.disk_check("", 10)[0] in ("ok", "warn", "stop") and vcsafe.disk_check(tempfile.gettempdir(), -5)[0] == "ok", "disk guard: empty folder / negative size do not crash")

print("FAILS:", _n[0])
