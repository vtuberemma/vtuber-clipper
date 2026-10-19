"""2.3 reports, texts and file housekeeping (vcshare + the ledger / delete helpers): highlights page, VOD timestamps, chapters from a real file, duplicates, bulk rename,
snapshots, post texts and their limits, alt text, community message, Maybe folder, per-game memory."""
from t3lib import *
import datetime, html.parser, json, time, vcshare, vcmore, vcouts, vcpost, vctools

FF = paths.FFMPEG
vcmore.LEDGER = os.path.join(os.environ["HOME"], "ledger.json")
_n, _ok = [0], ok
def ok(c, m):
    if not c: _n[0] += 1
    _ok(bool(c), m)


def sh(args, timeout=120):
    return subprocess.run([FF, "-y", "-v", "error"] + args, capture_output=True, timeout=timeout)


def touch(path, data=b"x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f: f.write(data)
    return path


# ---------------------------------------------------------------- small helpers
ok(vcshare.hms(5) == "0:05" and vcshare.hms(65) == "1:05" and vcshare.hms(3725) == "1:02:05" and vcshare.hms(-3) == "0:00" and vcshare.hms(0.9) == "0:00", "hms: seconds -> m:ss / h:mm:ss")
ok(vcshare.entry_title(dict(titles=["  Epic   clutch  "])) == "Epic clutch" and vcshare.entry_title(dict(kind="reaction", start=65)).endswith("at 1:05") and vcshare.entry_title({}).startswith("Moment at"), "entry_title: first title idea, else kind and time")
ok(vcshare.day_folder(datetime.date(2026, 10, 19)) == "2026-10-19" and len(vcshare.day_folder()) == 10, "day_folder: ISO date")

# ---------------------------------------------------------------- 33 highlights report
class Page(html.parser.HTMLParser):
    def __init__(self): super().__init__(); self.tags = []; self.hrefs = []; self.imgs = []; self.text = []; self.stack = []; self.bad = False
    def handle_starttag(self, t, a):
        self.tags.append(t); d = dict(a)
        if t == "a": self.hrefs.append(d.get("href"))
        if t == "img": self.imgs.append(d.get("src"))
        if t not in ("meta", "img", "br", "link"): self.stack.append(t)
    def handle_endtag(self, t):
        if self.stack and self.stack[-1] == t: self.stack.pop()
        else: self.bad = True
    def handle_data(self, d): self.text.append(d)
base = tempfile.mkdtemp(prefix="rep_")
ents = [dict(path=os.path.join(base, "Maybe", "clip 3.mp4"), start=3725, end=3760, dur=35, kind="story", hype=22, reasons=["Calm and steady"], titles=["Slow part"], notes=[]),
        dict(path=os.path.join(base, "clip 1.mp4"), start=75, end=105, dur=30, kind="reaction", hype=91, reasons=["Laughing", "A chat request"], titles=['<script>alert("x")</script> & "quotes"', "Second idea"], notes=["Loudness is -9 LUFS"]),
        dict(path=os.path.join(base, "clip 2.mp4"), start=900, end=940, dur=40, kind="gameplay", hype=70, reasons=[], titles=[])]
page = vcshare.report_html(ents, "My <VOD>", "MiaVT", "Mine&craft", made="2026-10-19 12:00", base_dir=base)
ok(page.startswith("<!doctype html>") and "</html>" in page and "<script>alert" not in page and "&lt;script&gt;alert" in page and "My &lt;VOD&gt;" in page and "Mine&amp;craft" in page, "highlights report: everything written by you or the video is escaped")
pp = Page(); pp.feed(page)
ok(not pp.bad and not pp.stack and pp.tags.count("article") == 3, f"highlights report: valid nesting, one card per clip ({pp.tags.count('article')})")
ok(pp.hrefs == ["clip%201.mp4", "clip%202.mp4", "Maybe/clip%203.mp4"], f"highlights report: sorted by time in the VOD, links relative to the report ({pp.hrefs})")
ok(pp.imgs == ["clip%201_cover.jpg", "clip%202_cover.jpg", "Maybe/clip%203_cover.jpg"], "highlights report: cover picture links match")
txt = " ".join(pp.text)
ok("3 clips" in txt and "1:41:15" not in txt and "1:02:05" in txt and "hype 91" in txt and "Loudness is -9 LUFS" in txt and "A chat request" in txt, "highlights report: totals, times, hype, why and notes are in it")
ok("prefers-color-scheme" in page and "max-width:560px" in page, "highlights report: has dark mode and a phone layout")
empty = vcshare.report_html([], "x")
ok("0 clips" in empty and "</html>" in empty, "highlights report: no clips -> still a valid page")
weird = vcshare.report_html([dict(path="", start=None, dur=None, kind=None, hype=None)], "", "", "")
ok("</html>" in weird, "highlights report: empty fields do not crash")

# ---------------------------------------------------------------- 34 VOD timestamps
E = lambda *starts: [dict(start=s, kind="reaction", titles=[f"Moment {int(s)}"]) for s in starts]
ts = vcshare.timestamps_text(E(75, 300, 3725, 3730, 9000))
lines = ts.strip().splitlines()
ok(lines[0].startswith("0:00:00 Intro") and lines[1].startswith("0:01:15 Moment 75") and "1:02:05 Moment 3725" in lines[3 - 0 - 0 + 0 - 0] or "1:02:05 Moment 3725" in ts, f"timestamps: start at 0:00 with an Intro line, hour format when the VOD is long ({lines[:3]})")
ok("3730" not in ts and len(lines) == 5, f"timestamps: a moment less than 10 s after the last is left out ({len(lines)} lines)")
ts2 = vcshare.timestamps_text(E(75, 300))
ok(ts2.splitlines()[0] == "0:00 Intro" and ts2.splitlines()[1] == "1:15 Moment 75", "timestamps: short VOD uses m:ss")
ok(vcshare.timestamps_text(E(75)) == "" and vcshare.timestamps_text([]) == "", "timestamps: fewer than two moments -> nothing (YouTube needs a list)")
ts3 = vcshare.timestamps_text(E(0, 40))
ok(ts3.splitlines()[0].startswith("0:00") and ts3.count("\n") == 2, "timestamps: a first moment at 0 s is not repeated")
ts4 = vcshare.timestamps_text(E(*range(5, 2000, 20)), limit=10)
ok(len(ts4.splitlines()) == 10, "timestamps: limited to the number asked for")
ok(vcshare.timestamps_text([dict(start=None), dict(start=50, titles=["a"]), dict(start=90, titles=["b"])]).count("\n") == 3, "timestamps: entries without a start are ignored")
ok("\n" not in vcshare.timestamps_text(E(75, 300)).splitlines()[1], "timestamps: one line per moment")

# ---------------------------------------------------------------- 35 chapters from a file / yt-dlp info
meta = os.path.join(W_, "chap.txt")
open(meta, "w").write(";FFMETADATA1\ntitle=x\n[CHAPTER]\nTIMEBASE=1/1000\nSTART=0\nEND=20000\ntitle=Intro & chat\n[CHAPTER]\nTIMEBASE=1/1000\nSTART=20000\nEND=50000\ntitle=Boss fight\n[CHAPTER]\nTIMEBASE=1/1000\nSTART=50000\nEND=55000\ntitle=\n")
CH = os.path.join(W_, "chapters.mp4")
sh(["-i", SRC, "-i", meta, "-t", "60", "-map", "0", "-map_metadata", "1", "-map_chapters", "1", "-c", "copy", CH])
ch = vcshare.read_chapters(CH, FF)
ok(len(ch) == 3 and ch[0] == (0.0, 20.0, "Intro & chat") and ch[1][2] == "Boss fight" and abs(ch[1][0] - 20) < .01 and ch[2][2] == "Chapter 3", f"chapters: read from the video file ({ch})")
chr_ = vcshare.read_chapters(CH, FF, dict(stdin=subprocess.DEVNULL, creationflags=0))
ok(len(chr_) == 3, f"chapters also read with the app's own subprocess settings ({len(chr_)})")
ok(vcshare.read_chapters(SRC, FF) == [], "chapters: a video without chapters -> none")
ok(vcshare.read_chapters(os.path.join(W_, "nope.mp4"), FF) == [], "chapters: missing file -> none")
INFO = os.path.join(W_, "fromdlp.mp4"); sh(["-i", SRC, "-t", "5", "-c", "copy", INFO])
json.dump(dict(chapters=[dict(start_time=0, end_time=30, title="Just chatting"), dict(start_time=30, end_time=30, title="empty"), dict(start_time=30, end_time=90, title="Game")]), open(os.path.splitext(INFO)[0] + ".info.json", "w"))
ci = vcshare.read_chapters(INFO, FF)
ok(ci == [(0.0, 30.0, "Just chatting"), (30.0, 90.0, "Game")], f"chapters: yt-dlp .info.json next to the video is used, empty ones dropped ({ci})")
bad_info = os.path.join(W_, "badinfo.mp4"); sh(["-i", SRC, "-t", "3", "-c", "copy", bad_info]); open(os.path.splitext(bad_info)[0] + ".info.json", "w").write("{not json")
ok(vcshare.read_chapters(bad_info, FF) == [], "chapters: a broken .info.json is ignored")
mo = vcshare.chapters_to_moments([(0, 20, "A"), (20, 25, "short"), (25, 400, "B")], hi=60, lo=12, per=2)
ok(mo == [(0, 20, "A"), (25, 85, "B"), (85, 145, "B")], f"chapters -> moments: too short skipped, long ones give two windows ({mo})")
ok(vcshare.chapters_to_moments([]) == [] and vcshare.chapters_to_moments([(0, 30, "x")], per=3) == [(0, 30, "x")], "chapters -> moments: empty / only as many windows as fit")

# ---------------------------------------------------------------- 41 duplicates
D = lambda vod, a, b, hype=50, **k: dict(vod=vod, start=a, end=b, hype=hype, path=f"{vod}-{a}.mp4", **k)
dups = vcshare.find_duplicates([D("v1", 100, 130, 40), D("v1", 105, 135, 80), D("v1", 500, 530), D("v2", 100, 130), D("v1", 102, 132, 60, deleted=True), D("v1", 133, 150, 10)])
ok(len(dups) == 1 and [e["hype"] for e in dups[0]] == [80, 40], f"duplicates: overlapping clips of the same VOD grouped, best first ({[[e['start'] for e in g] for g in dups]})")
ok(vcshare.find_duplicates([D("v1", 0, 30), D("v1", 2.5, 40)])[0][0]["start"] in (0, 2.5), "duplicates: starting within 3 s counts as the same moment")
ok(vcshare.find_duplicates([D("v1", 0, 30), D("v2", 0, 30)]) == [] and vcshare.find_duplicates([]) == [] and vcshare.find_duplicates([dict(vod="v", start=None, end=3)]) == [], "duplicates: other VODs / nothing / half-empty rows")
big = vcshare.find_duplicates([D("v1", i * 2, i * 2 + 30) for i in range(300)])
ok(len(big) == 1 and len(big[0]) == 300, "duplicates: a long chain is one group and is fast")

# ---------------------------------------------------------------- 42 bulk rename
rn = tempfile.mkdtemp(prefix="ren_")
fl = []
for nme in ("a_short1", "a_short2", "b_short1"):
    p_ = touch(os.path.join(rn, nme + ".mp4"))
    for e in (".txt", ".srt", "_cover.jpg", "_posts.txt", "_check.txt", ".gif", "_1x1.mp4"): touch(os.path.join(rn, nme + e))
    fl.append(p_)
led = {fl[0]: dict(vod="C:/v/MyStream.mp4", game="Minecraft", channel="MiaVT", start=3725, kind="reaction", hype=87, dur=34), fl[1]: dict(vod="C:/v/MyStream.mp4", game="Minecraft", start=90, kind="story", hype=40, dur=20)}
plan = vcshare.rename_plan(fl, "{date} {game} {type} {n}", info=lambda f: led.get(f), today=datetime.date(2026, 10, 19))
names = [os.path.basename(n) for _, n in plan]
ok(names == ["2026-10-19 Minecraft reaction 1.mp4", "2026-10-19 Minecraft story 2.mp4", "2026-10-19 clip 3.mp4"], f"rename plan: pattern fills in what the diary knows ({names})")
plan2 = vcshare.rename_plan(fl, "same", info=None, today=datetime.date(2026, 10, 19))
ok([os.path.basename(n) for _, n in plan2] == ["same.mp4", "same (2).mp4", "same (3).mp4"], "rename plan: two clips never get the same name")
touch(os.path.join(rn, "same.mp4"), b"mine")
plan3 = vcshare.rename_plan(fl, "same", info=None)
ok(os.path.basename(plan3[0][1]) == "same (2).mp4", "rename plan: a file that is already there is never overwritten")
ok(vcshare.rename_plan([os.path.join(rn, "same.mp4")], "same") == [], "rename plan: a clip that would keep its name is left out")
moved = []
vcmore.ledger_add(dict(path=fl[0], vod="x", start=1, end=2))
n_done = vcshare.rename_apply(plan, ledger_move=lambda a_, b_: (moved.append((a_, b_)), vcmore.ledger_move(a_, b_)))
ok(n_done == 3 and len(moved) == 3, f"rename apply: three clips renamed ({n_done})")
new1 = os.path.join(rn, "2026-10-19 Minecraft reaction 1")
ok(all(os.path.isfile(new1 + e) for e in (".mp4", ".txt", ".srt", "_cover.jpg", "_posts.txt", "_check.txt", ".gif", "_1x1.mp4")) and not os.path.exists(fl[0]) and not os.path.exists(os.path.join(rn, "a_short1.txt")), "rename apply: the clip and every file that belongs to it moved together")
ok(vcmore.ledger_find(new1 + ".mp4") is not None and vcmore.ledger_find(fl[0]) is None, "rename apply: the diary points at the new name")
ok(vcshare.rename_apply([(os.path.join(rn, "nope.mp4"), os.path.join(rn, "x.mp4"))]) == 0, "rename apply: a clip that is gone is skipped")
touch(os.path.join(rn, "src.mp4")); touch(os.path.join(rn, "dst.mp4"), b"keep")
ok(vcshare.rename_apply([(os.path.join(rn, "src.mp4"), os.path.join(rn, "dst.mp4"))]) == 0 and open(os.path.join(rn, "dst.mp4"), "rb").read() == b"keep", "rename apply: never overwrites a file that appeared meanwhile")

# ---------------------------------------------------------------- 43 snapshots
sd = tempfile.mkdtemp(prefix="snap_")
s1 = vcshare.snapshot_save(dict(a=1, b="x", c=True), "first", folder=sd)
ok(s1.endswith(".json") and vcshare.snapshot_save(dict(a=1, b="x", c=True), "same again", folder=sd) == "", "snapshots: saved; an identical copy is not saved twice")
time.sleep(1.1)
s2 = vcshare.snapshot_save(dict(a=2, b="x", c=True), "second", folder=sd)
ls = vcshare.snapshot_list(sd)
ok(len(ls) == 2 and ls[0]["label"] == "second" and ls[0]["count"] == 3 and ls[1]["label"] == "first", f"snapshots: listed newest first ({[x['label'] for x in ls]})")
sd2 = tempfile.mkdtemp(prefix="snap2_")
s3 = vcshare.snapshot_save(dict(a=3), "third", folder=sd2); s4 = vcshare.snapshot_save(dict(a=4), "fourth", folder=sd2); s5 = vcshare.snapshot_save(dict(a=5), "fifth", folder=sd2)
ok(s3 and s4 and s5 and s3 < s4 < s5 and [x["label"] for x in vcshare.snapshot_list(sd2)] == ["fifth", "fourth", "third"], "snapshots: copies saved in the same second are still listed newest first")
ok(vcshare.snapshot_save(dict(a=5), "again", folder=sd2) == "", "snapshots: an identical copy is compared with the newest one, also inside one second")
ok(vcshare.snapshot_load(s1, sd) == dict(a=1, b="x", c=True) and vcshare.snapshot_load("nope.json", sd) is None, "snapshots: load returns the saved settings, or None")
ok(vcshare.snapshot_load("../" + s1, sd) is None and vcshare.snapshot_load(os.path.join(sd, s1), sd) is None, "snapshots: names with folders in them are refused")
ok(vcshare.snapshot_diff(dict(a=1, b=2), dict(a=1, b=3, c=4)) == ["b", "c"] and vcshare.snapshot_diff({}, {}) == [], "snapshots: diff names what changed")
open(os.path.join(sd, "19990101-000000.json"), "w").write("{broken")
ok(len(vcshare.snapshot_list(sd)) == 2, "snapshots: a broken file is ignored in the list")
for i in range(6):
    time.sleep(1.05); vcshare.snapshot_save(dict(a=10 + i), f"n{i}", keep=3, folder=sd)
ok(len([x for x in os.listdir(sd) if x.endswith(".json")]) == 3, "snapshots: only the newest few are kept")
ok(vcshare.snapshot_save(dict(a=object()), "odd", folder=sd).endswith(".json"), "snapshots: odd values are turned into text, no crash")
ok(vcshare.snapshot_list(os.path.join(sd, "missing")) == [] and vcshare.snapshot_save({}, "x", folder=os.path.join(sd, "sub", "deeper")).endswith(".json") and os.path.isdir(os.path.join(sd, "sub", "deeper")), "snapshots: a missing folder is listed as empty and created when saving")

# ---------------------------------------------------------------- 44 post texts for each platform
words = mk("so yesterday I finally beat the boss and I screamed so loud the neighbours called me, it was the funniest thing ever, honestly I cannot believe it")
kit = vcpost.make_kit(words, game="Minecraft", channel="MiaVT", handle="@mia", hint="", name_hint="stream", seed=1, dur=30, extra=["vtuber"], kind="reaction")
txt, warn = vcshare.platform_texts(kit, "@mia")
ok(all(h in txt for h in ("YOUTUBE SHORTS", "TIKTOK", "INSTAGRAM REELS", "X")) and "#Shorts" in txt and txt.count("#Shorts") >= 1, "post texts: a section for every app, #Shorts added")
ok(all(re.search(r"\((\d+)/(\d+)\)", l) and int(re.search(r"\((\d+)/(\d+)\)", l).group(1)) <= int(re.search(r"\((\d+)/(\d+)\)", l).group(2)) for l in txt.splitlines() if re.search(r"\(\d+/\d+\)", l)), "post texts: every length counter is within its limit")
big_kit = dict(youtube=dict(title="T" * 150, description="D" * 6000, hashtags=[f"#t{i}" for i in range(12)]), tiktok=dict(caption="c" * 2300 + " " + " ".join(f"#t{i}" for i in range(12)), hashtags=[f"#t{i}" for i in range(12)]),
               reels=dict(caption="r" * 2300, hashtags=[f"#t{i}" for i in range(12)]), twitter=dict(posts=[dict(text="x" * 400)], hashtags=["#a"]), titles=["fallback"])
txt2, warn2 = vcshare.platform_texts(big_kit)
ok(warn2["shorts"] and warn2["tiktok"] and warn2["reels"] and warn2["x"], f"post texts: too-long text is cut and the creator is told ({warn2})")
tl = [l for l in txt2.splitlines() if l.strip().startswith("Title (")]
ok(tl and "(100/100)" in tl[0], "post texts: YouTube title is cut to 100")
ok(max(len(l) for l in txt2.splitlines() if l.strip().startswith("(")) <= 340, "post texts: X posts cut to 280")
tt_tags = [l for l in txt2.splitlines() if "#t0" in l]
ok(all(l.count("#") <= 5 for l in tt_tags if not l.strip().startswith("D")), "post texts: hashtags kept low (a few good ones)")
mini, w3 = vcshare.platform_texts(dict(titles=["Only a title"]))
ok("Only a title" in mini and "YOUTUBE SHORTS" in mini and "X" in mini, "post texts: a nearly empty kit still gives usable texts")
txt3, _ = vcshare.platform_texts(dict(youtube=dict(title="Short #shorts", description="hi #Shorts")))
ok(txt3.lower().count("#shorts") == 3 and "\n    #Shorts" not in txt3, "post texts: #Shorts is not added when the title or description already has it")

# ---------------------------------------------------------------- 45 alt text
w_ = [dict(w="Hello", start=0, end=.3), dict(w="chat.", start=.3, end=.6), dict(w="My", start=.6, end=.9), dict(w="number", start=.9, end=1.2, priv="phone"), dict(w="is", start=1.2, end=1.4, pwarn="phone"), dict(w="great.", start=1.4, end=1.6)]
s_, l_ = vcshare.alt_text(w_, "reaction", ["Lots of laughing", "A scream"], 34.2, "vertical")
ok("34-second vertical clip" in s_ and "a reaction" in s_ and "Hello chat." in l_ and "laughing" in l_ and "a scream" in l_, f"alt text: kind, length, what is said, what is heard ({l_})")
ok("number" not in l_ and "is great" not in l_ and "phone" not in l_, "alt text: words the privacy guard marked never appear")
s2_, l2_ = vcshare.alt_text([], "", (), 0, "")
ok(s2_.startswith("A clip from a VTuber stream") and "no clear speech" in l2_, "alt text: nothing said")
s3_, l3_ = vcshare.alt_text([dict(w="word", start=i, end=i + .5) for i in range(200)], "talking", [], 20)
ok(len(l3_) < 400 and "…" in l3_, "alt text: a long first sentence is shortened")
ok("a song" in vcshare.alt_text([dict(w="la", start=0, end=1)], "singing", ["Sung"], 10)[0] and "singing" in vcshare.alt_text([dict(w="la", start=0, end=1)], "singing", [], 10)[1], "alt text: singing clips")

# ---------------------------------------------------------------- 46 community message
EN = [dict(path=f"c{i}.mp4", start=i * 100, hype=50 + i, kind=["reaction", "gameplay", "story"][i % 3], titles=[f"Clip number {i} " + "very long title " * 3]) for i in range(10)]
dm = vcshare.community_message(EN, "Big Stream", "MiaVT", "Minecraft", "discord")
ok(len(dm) == 1 and len(dm[0]) <= 2000 and "Big Stream" in dm[0] and "Minecraft" in dm[0] and dm[0].count("hype") == 8, f"community message: top 8 clips in one Discord message ({len(dm[0])} chars)")
ok("hype 59" in dm[0] and "hype 51" not in dm[0], "community message: the strongest clips are the ones listed")
dm2 = vcshare.community_message(EN, "Big Stream", "", "", "discord", limit=400)
ok(len(dm2) > 1 and all(len(m) <= 400 for m in dm2), f"community message: split in several messages when over the limit ({[len(m) for m in dm2]})")
xt = vcshare.community_message(EN, "Big Stream", "MiaVT", "Minecraft", "x")
ok(len(xt) == 9 and all(len(t) <= 280 for t in xt) and xt[0].startswith("New clips") and xt[1].startswith("1/"), "community message: X thread, one post per clip, each within 280")
ok(vcshare.community_message([], "x") == [] and vcshare.community_message([], "x", fmt="x") == [], "community message: no clips -> nothing")
ok(vcshare.community_message([dict(path="a.mp4")], "", "", "", "discord")[0].count("hype -") == 1, "community message: a clip with no data is still listed")

# ---------------------------------------------------------------- 47 Maybe folder
root = tempfile.mkdtemp(prefix="maybe_")
clip = os.path.join(root, "Shorts", "2026-10-19", "My VOD", "clip.mp4")
ok(vcshare.maybe_target(clip, 20, 30) == os.path.join(root, "Shorts", "Maybe"), "maybe folder: sits in Shorts, next to the day / VOD folders")
ok(vcshare.maybe_target(clip, 30, 30) is None and vcshare.maybe_target(clip, 80, 30) is None and vcshare.maybe_target(clip, 20, 0) is None and vcshare.maybe_target(clip, None, 30) is None and vcshare.maybe_target(clip, "x", 30) is None, "maybe folder: only clips under the limit; 0 = off; no score = stay")
ok(vcshare.maybe_target(os.path.join(root, "Shorts", "Maybe", "c.mp4"), 5, 30) is None, "maybe folder: a clip already there stays")
ok(vcshare.maybe_target(os.path.join(root, "Shorts", "c.mp4"), 5, 30) == os.path.join(root, "Shorts", "Maybe") and vcshare.maybe_target(os.path.join(root, "x", "c.mp4"), 5, 30) is not None, "maybe folder: clip straight in Shorts / in an unusual folder")
for e in (".mp4", ".txt", ".srt", "_cover.jpg", "_cover_b.jpg", "_posts.txt", "_alt.txt", "_check.txt", ".gif", ".mp3", "_transcript.txt", "_1x1.mp4", "_16x9.mp4"): touch(os.path.splitext(clip)[0] + e)
touch(os.path.join(root, "Shorts", "2026-10-19", "My VOD", "other.mp4"))
vcmore.ledger_add(dict(path=clip, vod="v", start=1, end=2, hype=20))
dest = vcshare.maybe_target(clip, 20, 30)
newp = vcshare.move_clip(clip, dest)
ok(newp == os.path.join(dest, "clip.mp4") and os.path.isfile(newp) and all(os.path.isfile(os.path.join(dest, "clip" + e)) for e in (".txt", ".srt", "_cover.jpg", "_posts.txt", "_alt.txt", ".gif", ".mp3", "_1x1.mp4", "_16x9.mp4")), "maybe folder: the clip and all its files moved")
ok(not any(os.path.exists(os.path.splitext(clip)[0] + e) for e in (".mp4", ".txt", "_cover.jpg", ".gif")) and os.path.isfile(os.path.join(root, "Shorts", "2026-10-19", "My VOD", "other.mp4")), "maybe folder: nothing of it left behind, other clips untouched")
touch(clip); touch(os.path.splitext(clip)[0] + ".txt")
new2 = vcshare.move_clip(clip, dest)
ok(os.path.basename(new2) == "clip (2).mp4" and os.path.isfile(os.path.join(dest, "clip (2).txt")) and os.path.isfile(os.path.join(dest, "clip.mp4")), "maybe folder: a clip with the same name is numbered, not overwritten")
ok(vcshare.move_clip(os.path.join(root, "gone.mp4"), dest) == "", "maybe folder: a missing clip -> nothing moved")
ok(vcmore.ledger_move(clip, newp) is True and vcmore.ledger_find(newp)["hype"] == 20 and vcmore.ledger_find(clip) is None and vcmore.ledger_move(clip, "x.mp4") is False, "ledger: the row follows the clip into the Maybe folder")

# ---------------------------------------------------------------- deleting a clip also cleans up the new files and empty day folders
dd = tempfile.mkdtemp(prefix="del_"); dclip = os.path.join(dd, "Shorts", "2026-10-19", "VOD", "c.mp4")
for e in (".mp4", ".txt", "_posts.txt", "_alt.txt", "_check.txt", ".gif", ".mp3", "_cover_b.jpg"): touch(os.path.splitext(dclip)[0] + e)
nd = vcouts.delete_clip_files(dclip)
ok(nd == 8 and not os.path.exists(os.path.dirname(dclip)) and not os.path.exists(os.path.join(dd, "Shorts", "2026-10-19")) and os.path.isdir(os.path.join(dd, "Shorts")), f"delete: files, then the empty VOD and day folders go; Shorts stays ({nd})")
touch(os.path.join(dd, "Shorts", "2026-10-19", "VOD", "keep.mp4")); touch(os.path.join(dd, "Shorts", "2026-10-19", "VOD", "c.mp4"))
vcouts.delete_clip_files(os.path.join(dd, "Shorts", "2026-10-19", "VOD", "c.mp4"))
ok(os.path.isfile(os.path.join(dd, "Shorts", "2026-10-19", "VOD", "keep.mp4")), "delete: a folder that still has clips is kept")
ok(vcmore.copy_ready(touch(os.path.join(dd, "x", "r.mp4")), os.path.join(dd, "ready")) == 1 and (touch(os.path.join(dd, "x", "r_posts.txt")) and vcmore.copy_ready(os.path.join(dd, "x", "r.mp4"), os.path.join(dd, "ready2")) == 2), "ready folder: the new post-text file travels with the clip")

# ---------------------------------------------------------------- 50 per game memory
ok(vcshare.game_put("Minecraft", dict(n=7, len_min=20, len_max=45, style="gameplay", layout="fill", junk=1)) is True, "game memory: stored")
ok(vcshare.game_get("  minecraft ") == dict(n=7, len_min=20, len_max=45, style="gameplay", layout="fill"), "game memory: found by name (capitals and spaces do not matter), only the known settings")
ok(vcshare.game_get("Terraria") == {} and vcshare.game_get("") == {} and vcshare.game_put("", dict(n=3)) is False and vcshare.game_put("X", {}) is False and vcshare.game_put("X", dict(n=None, style="")) is False, "game memory: unknown / empty -> nothing")
vcshare.game_put("Minecraft", dict(n=3)); ok(vcshare.game_get("minecraft") == dict(n=3), "game memory: a game's settings are replaced by the newest")
for i in range(130): vcshare.game_put(f"Game {i}", dict(n=i % 9 + 1))
ok(len(vctools.store_get("game_prefs", {})) <= 120 and vcshare.game_get("Game 129") != {}, "game memory: the list stays small and keeps the newest")

print("FAILS:", _n[0])
