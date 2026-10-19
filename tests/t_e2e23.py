"""2.3 end to end on the synthetic stream: whole clip runs with the new options on. Privacy slips in the speech (warn / bleep / off), private words, every new extra file, chat commands,
Maybe folder, day folder, disk guard, reports. Each claim is measured on the files that come out."""
import sys, os, json, tempfile, argparse, glob, time, re, subprocess, io, contextlib, urllib.parse
import paths; S = paths.ROOT
H = tempfile.mkdtemp(); os.environ["HOME"] = H; os.environ["USERPROFILE"] = H
sys.path.insert(0, paths.APP); import streamclip as sc, vcmore, vcsafe, vcshare, vcmedia, vcpipe
import numpy as np
sc.FF = paths.FFMPEG; sc.HW = dict(cores=8, cpu="x", ram=8, gpus=[], enc="libx264", cuda_ok=False)
sc.OUT.update(mbps=4, res=360, fps=24); sc.CACHE_DIR = tempfile.mkdtemp()
vcmore.LEDGER = os.path.join(H, "ledger.json")
D = json.load(open(paths.FIX + "/stream22.json")); WORDS = [dict(w) for w in D["words"]]

# put privacy slips into the story part of the stream (word times stay as they were)
def inject(i, texts):
    for k, t in enumerate(texts): WORDS[i + k]["w"] = t
inject(170, ["my", "number", "is", "555", "123", "4567."])
inject(186, ["email", "me", "at", "mia", "at", "gmail", "dot", "com."])
inject(200, ["Kiki"])
PHONE = [WORDS[i] for i in range(173, 176)]; MAIL = [WORDS[i] for i in range(189, 194)]; KIKI = WORDS[200]
sc.transcribe = lambda *a, **k: [dict(w) for w in WORDS]
SRC_DIR = tempfile.mkdtemp(); VID = os.path.join(SRC_DIR, "stream22.mp4"); import shutil; shutil.copy(paths.FIX + "/stream22.mp4", VID)
FX = {k: 0 for k in sc.FX["gameplay"]}; FX.update(intensity=1.0, accent="ff4d8d", sfx=0, zoom=0, hook=1, bar=0)
R = []
def ck(m, c, detail=""):
    R.append(bool(c)); print(("PASS " if c else "FAIL ") + m + ("" if c or not detail else "   -> " + str(detail)[:300]), flush=True)
FF = paths.FFMPEG


def run(name, opts, windows=((150.0, 195.0),), n=1, **kw):
    out = os.path.join(H, "out_" + name)
    o = dict(post_kit=True, fresh=False, cover=True, srt=True, transcript=True, auto_look=False, cap_emoji=False, cap_style="line", vod_folder=True, **opts)
    a = argparse.Namespace(video=VID, model="tiny", device="cpu", censor=None, gap=1.5, style="mix", opts=o, fx=FX, n=n, len_min=kw.get("lo", 15), len_max=kw.get("hi", 30), layout="blur", cam=None,
                           no_silence=False, no_captions=False, out=out, windows=list(windows) if windows else None)
    buf = io.StringIO(); err = None
    with contextlib.redirect_stdout(buf):
        try: sc.cmd_shorts(a)
        except Exception as e: err = e
    return out, buf.getvalue(), err


def clips(out): return sorted(glob.glob(os.path.join(out, "Shorts", "**", "*.mp4"), recursive=True))
def audio(mp4):
    r = subprocess.run([FF, "-v", "error", "-i", mp4, "-f", "f32le", "-ac", "1", "-ar", "48000", "-"], capture_output=True); return np.frombuffer(r.stdout, dtype=np.float32)
def rms(a, t0, t1, sr=48000):
    x = a[int(t0 * sr):int(t1 * sr)]; return float(np.sqrt(np.mean(x ** 2))) if len(x) else 0.0
def tone_share(a, t0, t1, sr=48000):
    """How much of the sound between t0 and t1 is the 1 kHz bleep tone (0..1). Speech is spread over many frequencies, the bleep is one note."""
    x = a[int(t0 * sr):int(t1 * sr)]
    if len(x) < 200: return 0.0
    sp = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2; fr = np.fft.rfftfreq(len(x), 1 / sr)
    return float(sp[(fr >= 940) & (fr <= 1060)].sum() / max(sp.sum(), 1e-12))
def probe(path, entries="stream=codec_type,codec_name"):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", entries, "-of", "json", path], capture_output=True, text=True); return json.loads(r.stdout or "{}").get("streams", [])
def read(p): return open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else ""
SEGS = sc.keep_segments(150.0, 195.0, WORDS, 1.5)
tm = lambda t: sc.tmap(SEGS, t)

# ================================================================ A: warn mode, private words, every extra file
ALL = dict(privacy="warn", private_words="Kiki", soft_subs=True, scrub_meta=True, meta_tags=True, audio_copy=True, gif_clip=True, cover_alts=True, cover_sharp=True, platform_texts=True, alt_text=True,
           report_html=True, stamps_file=True, community_msg=True, day_folder=True, preflight=True, channel="MiaVT", game="Horror Game", handle="@miavt")
outA, logA, errA = run("A", ALL)
fa = clips(outA)
ck(f"A: the run finished without an error ({errA})", errA is None and len(fa) == 1)
clip = fa[0] if fa else ""; stem = os.path.splitext(clip)[0]
ck("A: the clip sits in a folder for today, then one for the VOD", time.strftime("%Y-%m-%d") in clip.split(os.sep) and "stream22" in clip.split(os.sep), clip)
ck("A: the log tells about the privacy guard", "Privacy guard:" in logA and "phone number" in logA and "e-mail address" in logA and "one of your private words" in logA)
srt = read(stem + ".srt"); tr = read(stem + "_transcript.txt")
ck("A: the private word is starred in the subtitles and the transcript", "Kiki" not in srt and "Kiki" not in tr and "****" in srt)
ck("A (warn): phone and e-mail are only reported, so the words are still in the subtitles", "555" in srt and "gmail" in srt)
chk = read(stem + "_check.txt")
ck("A: the clip check lists what was NOT bleeped", "NOT bleeped" in chk and "phone number" in chk and "e-mail" in chk, chk[:300])
au = audio(clip)
tk0, tk1 = tm(KIKI["start"]), tm(KIKI["end"])
ck("A: the private word is covered by the bleep in the sound", tk0 is not None and tone_share(au, tk0 + .03, tk1 - .03) > .8 and tone_share(au, tk0 - .7, tk0 - .1) < .3, f"{tone_share(au, tk0 + .03, tk1 - .03):.2f} vs {tone_share(au, tk0 - .7, tk0 - .1):.2f}")
tp0, tp1 = tm(PHONE[0]["start"]), tm(PHONE[-1]["end"])
ck("A (warn): the phone number is not bleeped (it is only reported)", tp0 is not None and tone_share(au, tp0 + .05, tp1 - .05) < .5, f"{tone_share(au, tp0 + .05, tp1 - .05):.2f}")
posts = read(stem + "_posts.txt"); alt = read(stem + "_alt.txt"); kit_txt = read(stem + ".txt")
ck("A: post kit, platform texts and alt text carry no private word, number or e-mail", all(x not in (posts + alt + kit_txt) for x in ("Kiki", "555", "gmail", "4567")))
ck("A: platform texts and alt text files were written", "YOUTUBE SHORTS" in posts and "TIKTOK" in posts and "ALT TEXT (short)" in alt)
ck("A: the file has soft subtitles", any(s["codec_type"] == "subtitle" for s in probe(clip)))
tags = vcmedia.file_tags(clip, FF, None)
ck(f"A: file info has the channel and the game, nothing else hidden ({sorted(tags)})", tags.get("artist") == "MiaVT" and tags.get("genre") == "Horror Game" and "encoder" not in tags and "creation_time" not in tags)
ck("A: sound file and GIF were made", (os.path.isfile(stem + ".mp3") or os.path.isfile(stem + ".m4a")) and os.path.isfile(stem + ".gif") and os.path.getsize(stem + ".gif") < 8e6)
ck("A: the cover and the two extra covers were made", os.path.isfile(stem + "_cover.jpg") and os.path.isfile(stem + "_cover_b.jpg"), glob.glob(stem + "_cover*"))
ck("A: the extra covers differ from the first one", os.path.isfile(stem + "_cover_b.jpg") and open(stem + "_cover.jpg", "rb").read() != open(stem + "_cover_b.jpg", "rb").read())
rep = glob.glob(os.path.join(os.path.dirname(clip), "*_highlights.html"))
ck("A: highlights report written next to the clips and links to the clip", len(rep) == 1 and urllib.parse.quote(os.path.basename(clip)) in read(rep[0]))
com = glob.glob(os.path.join(os.path.dirname(clip), "*_community.txt"))
ck("A: community message written", len(com) == 1 and "DISCORD" in read(com[0]) and "X THREAD" in read(com[0]))
ck("A: one clip is too few for VOD timestamps, and the log says so", not glob.glob(os.path.join(os.path.dirname(clip), "*_timestamps.txt")) and "timestamps need at least two clips" in logA)
led = [e for e in vcmore.ledger_all() if e["path"] == os.path.abspath(clip)]
ck("A: the diary has the title ideas and the privacy notes", len(led) == 1 and led[0].get("titles") and any("phone" in x for x in led[0].get("notes", [])), led[:1])
ck("A: nothing leaked into the diary", "Kiki" not in json.dumps(led) and "555" not in json.dumps(led))
ck("A: no temporary files are left in the clip folder", not [f for f in os.listdir(os.path.dirname(clip)) if f.endswith((".tmp", ".new", ".ss.mp4", ".mt.mp4", ".sc.mp4", ".softsubs.srt"))], os.listdir(os.path.dirname(clip)))
ck("A: the finished clip plays through", subprocess.run([FF, "-v", "error", "-i", clip, "-f", "null", "-"], capture_output=True, text=True).stderr.strip() == "")

# ================================================================ B: bleep mode
outB, logB, errB = run("B", dict(privacy="bleep", private_words="Kiki", preflight=True))
fb = clips(outB); cb = fb[0] if fb else ""; sb = os.path.splitext(cb)[0]
srtB = read(sb + ".srt"); trB = read(sb + "_transcript.txt")
ck("B (bleep): number, e-mail and private word are all starred in subtitles and transcript", errB is None and cb and all(x not in srtB + trB for x in ("555", "4567", "gmail", "Kiki")) and srtB.count("*") > 12)
auB = audio(cb)
shares = [tone_share(auB, tm(w["start"]) + .03, tm(w["end"]) - .03) for w in PHONE + MAIL]
ck("B (bleep): number and e-mail are covered by the bleep in the sound", min(shares) > .8 and tone_share(auB, tm(PHONE[0]["start"]) - .8, tm(PHONE[0]["start"]) - .2) < .3, [round(x, 2) for x in shares])
ck("B (bleep): nothing is left to warn about", "NOT bleeped" not in read(sb + "_check.txt"))
ck("B: the title idea file has no private text either", all(x not in read(sb + ".txt") for x in ("555", "gmail", "Kiki")))

# ================================================================ C: guard off
outC, logC, errC = run("C", dict(privacy="off", private_words="Kiki"))
fc = clips(outC); sc_ = os.path.splitext(fc[0])[0] if fc else ""
srtC = read(sc_ + ".srt")
ck("C (off): nothing is changed - number, e-mail and the name stay as they were said", errC is None and "555" in srtC and "gmail" in srtC and "Kiki" in srtC and "Privacy guard" not in logC)
ck("C (off): no check file about privacy", "NOT bleeped" not in read(sc_ + "_check.txt"))

# ================================================================ D: the default options change nothing that was there in 2.2
outD, logD, errD = run("D", dict())
fd = clips(outD)
ck("D: with default options a normal run makes the clip and the usual files only", errD is None and len(fd) == 1 and os.path.isfile(os.path.splitext(fd[0])[0] + ".srt") and os.path.isfile(os.path.splitext(fd[0])[0] + "_cover.jpg")
   and not glob.glob(os.path.splitext(fd[0])[0] + "*.gif") and not glob.glob(os.path.splitext(fd[0])[0] + "*.mp3") and not glob.glob(os.path.splitext(fd[0])[0] + "_cover_b*")
   and not glob.glob(os.path.dirname(fd[0]) + "/*.html") and not glob.glob(os.path.dirname(fd[0]) + "/*_community.txt") and time.strftime("%Y-%m-%d") not in fd[0].split(os.sep))
ck("D: by default the privacy guard only warns, and the clip check ran", "finished: clip check" in logD and "NOT bleeped" in logD and "skipped" not in logD and "NOT bleeped" in read(os.path.splitext(fd[0])[0] + "_check.txt"), [l for l in logD.splitlines() if "check" in l or "skipped" in l])

# ================================================================ E: Maybe folder
outE, logE, errE = run("E", dict(maybe_folder=True, maybe_below=101, report_html=True, platform_texts=True, alt_text=True, gif_clip=True))
fe = clips(outE)
ck("E: a clip under the limit goes to the Maybe folder with all its files", errE is None and len(fe) == 1 and os.sep + "Maybe" + os.sep in fe[0] and os.path.isfile(os.path.splitext(fe[0])[0] + "_posts.txt")
   and os.path.isfile(os.path.splitext(fe[0])[0] + ".gif") and os.path.isfile(os.path.splitext(fe[0])[0] + "_cover.jpg"), fe)
ck("E: nothing of it stays behind in the VOD folder", not [f for f in glob.glob(os.path.join(outE, "Shorts", "stream22", "*")) if not f.endswith(".html")], glob.glob(os.path.join(outE, "Shorts", "**", "*"), recursive=True)[:6])
ck("E: the diary points at the new place", any(e["path"] == os.path.abspath(fe[0]) for e in vcmore.ledger_all()))
rep = glob.glob(os.path.join(outE, "Shorts", "stream22", "*_highlights.html"))
ck("E: the highlights report links into the Maybe folder", len(rep) == 1 and "Maybe/" in read(rep[0]))
ck("E: the log says it was moved", "Maybe folder" in logE)
outE2, logE2, _ = run("E2", dict(maybe_folder=True, maybe_below=40), windows=((86.0, 100.0),))
hy = [e["hype"] for e in vcmore.ledger_all() if e["path"] == os.path.abspath(clips(outE2)[0])] if clips(outE2) else []
ck("E: a clip over the limit (the laugh, hype 91 against a limit of 40) stays in the main folder", clips(outE2) and hy and hy[0] >= 40 and os.sep + "Maybe" + os.sep not in clips(outE2)[0], (hy, clips(outE2)))

# ================================================================ F: disk guard
real = vcsafe.disk_check
vcsafe.disk_check = lambda folder, need: ("stop", "There is only 0.1 GB free on that drive and this run needs about 2.0 GB.", 100.0)
outF, logF, errF = run("F", dict(disk_guard=True))
ck("F: a full drive stops the run before anything is rendered, with a plain message", errF is not None and "free" in str(errF) and not clips(outF), str(errF)[:100])
outF2, logF2, errF2 = run("F2", dict(disk_guard=False))
ck("F: the guard can be switched off", errF2 is None and len(clips(outF2)) == 1)
vcsafe.disk_check = lambda folder, need: ("warn", "Free space is getting low: 3.0 GB left.", 3000.0)
outF3, logF3, errF3 = run("F3", dict(disk_guard=True))
ck("F: low space only warns", errF3 is None and "Free space is getting low" in logF3 and len(clips(outF3)) == 1)
vcsafe.disk_check = real

# ================================================================ G: the smart finder with chat commands, build-up etc.
chat = os.path.join(SRC_DIR, "stream22.chat.txt")
open(chat, "w", encoding="utf-8").write("\n".join(f"[0:{i // 60:02d}:{i % 60:02d}] v{i}: hello there" for i in range(0, 240, 3)) + "\n[0:00:46] a: !clip\n[0:00:47] b: clip that\n[0:00:49] c: !clip\n")
outG, logG, errG = run("G", dict(chat_file=chat, game="Horror Game", game_memory=True, stamps_file=True, report_html=True, spread=True, smart=True), windows=None, n=3, lo=12, hi=25)
fg = clips(outG)
ck(f"G: smart run made clips ({len(fg)})", errG is None and len(fg) >= 2, str(errG))
ck("G: the log says viewers asked for a clip", "asked for a clip" in logG)
rows = [e for e in vcmore.ledger_all() if e["path"] in {os.path.abspath(f) for f in fg}]
ck("G: the clip around the !clip messages was made, and says why", any(e["start"] - 1 <= 47 <= e["end"] + 1 and any("!clip" in r for r in e["reasons"]) for e in rows), [(e["start"], e["end"], e["reasons"][:2]) for e in rows])
ts = glob.glob(os.path.join(outG, "Shorts", "stream22", "*_timestamps.txt"))
ck("G: VOD timestamps written (2+ clips), starting at 0:00", len(ts) == 1 and read(ts[0]).startswith("0:00"), read(ts[0])[:80] if ts else "")
ck("G: highlights report lists every clip", len(glob.glob(os.path.join(outG, "Shorts", "stream22", "*_highlights.html"))) == 1 and read(glob.glob(os.path.join(outG, "Shorts", "stream22", "*_highlights.html"))[0]).count("<article>") == len(fg))
gm = vcshare.game_get("Horror Game")
ck(f"G: the length, style and count are remembered for the game ({gm})", gm.get("n") == 3 and gm.get("len_min") == 12 and gm.get("len_max") == 25 and gm.get("style") == "mix")
outG2, logG2, errG2 = run("G2", dict(chat_file=chat, game="Other Game", game_memory=True, smart=True), windows=((150.0, 195.0),))
ck("G: a run with hand-picked moments does not overwrite the game memory", vcshare.game_get("Other Game") == {})

# ================================================================ H: cancel is respected between the finishing steps
_ws = sc.write_srt
def srt_then_cancel(*a, **k):
    r = _ws(*a, **k); sc.CANCEL.set(); return r
sc.write_srt = srt_then_cancel
outH, logH, errH = run("H", ALL)
sc.write_srt = _ws; sc.CANCEL.clear()
fh = clips(outH); sh_ = os.path.splitext(fh[0])[0] if fh else ""
ck("H: after Cancel the finishing steps stop (no GIF, sound file, post texts, alt text), the clip itself is whole and nothing temporary is left",
   len(fh) == 1 and not any(os.path.isfile(sh_ + e) for e in (".gif", ".mp3", "_posts.txt", "_alt.txt")) and subprocess.run([FF, "-v", "error", "-i", fh[0], "-f", "null", "-"], capture_output=True, text=True).stderr.strip() == ""
   and not [f for f in glob.glob(os.path.join(outH, "**", "*"), recursive=True) if f.endswith((".tmp", ".new", ".ss.mp4", ".mt.mp4", ".sc.mp4", ".softsubs.srt"))], str(errH)[:80])

print("FAILS:", R.count(False))
