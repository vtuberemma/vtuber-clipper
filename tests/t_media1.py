"""2.3 picture / sound / file extras (vcmedia): background blur and brightness, noise gate, de-esser, progress bar, feeling colours, logo opacity, music by mood,
soft subtitles, file info, hidden-info removal, MP3, GIF, sharpest-frame covers. Each one is measured on real rendered frames / sound / files."""
from t3lib import *
import json, vcmedia, vc23

FF = paths.FFMPEG
_n, _ok = [0], ok
def ok(c, m):
    if not c: _n[0] += 1
    _ok(bool(c), m)


def sh(args, timeout=120):
    return subprocess.run([FF, "-y", "-v", "error"] + args, capture_output=True, timeout=timeout)


def probe(path, entries="stream=codec_type,codec_name,width,height,duration:stream_tags=language"):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", entries, "-of", "json", path], capture_output=True, text=True)
    return json.loads(r.stdout or "{}").get("streams", [])


# ---------------------------------------------------------------- 12 / 13 blur and brightness: filter text
ok(vcmedia.blur_chain("normal", 1080, 1920, 0) == "scale=216:384,boxblur=5:2,scale=1080:1920", "background blur 'normal' is exactly what 2.2 did")
sizes = [vcmedia.blur_params(n, 1080, 1920)[0] for n in ("soft", "normal", "strong", "extreme")]
rads = [vcmedia.blur_params(n, 1080, 1920)[2] for n in ("soft", "normal", "strong", "extreme")]
ok(sizes == sorted(sizes, reverse=True) and len(set(sizes)) == 4 and rads == sorted(rads) and len(set(rads)) == 4, f"blur levels get blurrier step by step ({sizes} / {rads})")
ok(vcmedia.blur_params("nonsense", 1080, 1920) == vcmedia.blur_params("normal", 1080, 1920), "unknown blur name falls back to normal")
ok(vcmedia.blur_chain("normal", 1080, 1920, 0).count("lutyuv") == 0 and "lutyuv" in vcmedia.blur_chain("normal", 1080, 1920, -30), "dim 0 adds no filter, dim -30 adds one")
ok(vcmedia.dim_filter("x") == "" and vcmedia.dim_filter(None) == "" and "0.50" in vcmedia.dim_filter(-999) and "1.50" in vcmedia.dim_filter(999), "dim is clamped to -50..50 and ignores junk")
tiny = vcmedia.blur_params("extreme", 100, 50)
ok(min(tiny[:2]) >= 2, "blur copy never gets smaller than 2 px, even on tiny pictures")

# ---------------------------------------------------------------- 12 / 13 rendered: the background really changes
STRIP = (0.0, 0.0, 1.0, 0.07)                       # the blurred background above the picture
def edge_steepness(im):
    """The steepest step between neighbouring pixels along the yellow -> blue edge in the blurred background (a sharp edge is steep, a blurred one is gentle)."""
    w, h = im.size; a = np.asarray(im.convert("RGB"))[:, :, 2].astype(float)             # blue channel: 0 on yellow, 255 on blue
    return float(np.mean([np.abs(np.diff(a[int(h * y), :])).max() for y in (.01, .03, .05)]))
fr = {}
for name in ("soft", "normal", "strong", "extreme"):
    mp4, _ = R("blur_" + name, layout="blur", opts={"bg_blur": name, "cap_style": "line"}, segs=((0, 6),))
    fr[name] = frame(mp4, 3.0)
ew = [edge_steepness(fr[n]) for n in ("soft", "normal", "strong", "extreme")]
ok(ew[0] > ew[1] > ew[2] > ew[3] and ew[0] > ew[3] * 3, f"rendered background: the colour edge gets gentler soft > normal > strong > extreme ({', '.join(f'{x:.0f}' for x in ew)})")
mp4_n, _ = R("dim0", layout="blur", opts={"cap_style": "line"}, segs=((0, 6),))
mp4_d, _ = R("dimdark", layout="blur", opts={"bg_dim": -40, "cap_style": "line"}, segs=((0, 6),))
mp4_b, _ = R("dimbright", layout="blur", opts={"bg_dim": 30, "cap_style": "line"}, segs=((0, 6),))
ln, ld, lb = (luma(frame(m, 3.0), STRIP) for m in (mp4_n, mp4_d, mp4_b))
ok(ld < ln * .8 and lb > ln * 1.1, f"background brightness: dark {ld:.0f} < normal {ln:.0f} < bright {lb:.0f}")
cen = (0.1, 0.4, 0.9, 0.6)
ok(abs(luma(frame(mp4_d, 3.0), cen) - luma(frame(mp4_n, 3.0), cen)) < 6, "dimming the background leaves the main picture alone")

# ---------------------------------------------------------------- 14 / 15 noise gate and de-esser on real sound
NOISE_TONE = os.path.join(W_, "noise_tone.wav")
sh(["-f", "lavfi", "-i", "anoisesrc=d=2:c=white:a=0.012:r=48000", "-f", "lavfi", "-i", "sine=f=440:d=2:r=48000", "-f", "lavfi", "-i", "anoisesrc=d=2:c=white:a=0.012:r=48000",
    "-filter_complex", "[1]volume=0.4[t];[t][2]amix=inputs=2:duration=first:normalize=0[v];[0][v]concat=n=2:v=0:a=1[o]", "-map", "[o]", "-ac", "1", NOISE_TONE])
def through(af, src=NOISE_TONE):
    out = os.path.join(W_, "af_%d.wav" % abs(hash(af)))
    sh(["-i", src, "-af", af.lstrip(","), "-ac", "1", "-ar", "48000", out]); return audio(out)
a0 = audio(NOISE_TONE)
ag = vcmedia.audio_gate(dict(gate=True))
ok(ag.startswith(",") and "agate" in ag and vcmedia.audio_gate({}) == "", "audio_gate: filter text starts with a comma / empty when nothing is on")
a1 = through(ag)
n0, n1 = rms(a0, .3, 1.7), rms(a1, .3, 1.7); t0, t1 = rms(a0, 2.3, 3.7), rms(a1, 2.3, 3.7)
ok(n1 < n0 * .5 and t1 > t0 * .8, f"noise gate: background hiss {n0:.4f} -> {n1:.4f}, voice {t0:.3f} -> {t1:.3f} stays")
SIB = os.path.join(W_, "sib.wav")              # a low voice tone under hissy 'sss' noise (5-10 kHz), like a sibilant: the de-esser is made for that, not for a pure whistle
sh(["-f", "lavfi", "-i", "anoisesrc=d=3:c=white:a=0.5:r=48000,highpass=f=5000,lowpass=f=10000", "-f", "lavfi", "-i", "sine=f=200:d=3:r=48000", "-filter_complex",
    "[1]volume=0.1[b];[0][b]amix=inputs=2:normalize=0[o]", "-map", "[o]", "-ac", "1", SIB])
s0 = audio(SIB)
for label, f, lo_hi, need in (("de-esser", vcmedia.DEESS, (5000, 10000), 3.0), ("fallback dip", vcmedia.DEESS_FALLBACK, (7000, 8000), 2.0)):
    s1 = through(f, SIB)
    hi0, hi1, lo0, lo1 = band(s0, .5, 2.5, *lo_hi), band(s1, .5, 2.5, *lo_hi), band(s0, .5, 2.5, 150, 300), band(s1, .5, 2.5, 150, 300)
    red = 10 * np.log10(max(hi0, 1e-12) / max(hi1, 1e-12))
    ok(red > need and lo1 > lo0 * .5, f"{label}: harsh 'sss' band down {red:.1f} dB, low voice kept ({10 * np.log10(lo1 / lo0):.1f} dB)")
ok(vcmedia.have_filter(FF, "deesser") in (True, False) and not vcmedia.have_filter(FF, "no_such_filter_xyz"), "filter probe answers yes / no without crashing")
ok("equalizer" in vcmedia.audio_gate(dict(deess=True), "ffmpeg_that_does_not_exist"), "no working de-esser filter -> the gentle dip is used instead")

# ---------------------------------------------------------------- 16 progress bar edge and thickness
yb, hb = vcmedia.bar_geometry(1920, 1920, "bottom", 14); yt, ht = vcmedia.bar_geometry(1920, 1920, "top", 14)
ok(yt == 0 and yb == 1920 - hb and hb == ht == 14, f"progress bar: top edge y=0, bottom edge y={yb}, {hb}px")
y2, h2 = vcmedia.bar_geometry(960, 1920, "bottom", 14)
ok(h2 == 7 and y2 == 960 - 7, "progress bar thickness follows the picture size")
ok(vcmedia.bar_geometry(100, 1920, "top", 40)[1] <= 12 and vcmedia.bar_geometry(1920, 1920, "top", 1)[1] >= 6, "progress bar never vanishes and never covers the picture")
nb, _ = R("bar_none", layout="fill", opts={"cap_style": "line"}, fx={"bar": False}, segs=((0, 8),))
bt, _ = R("bar_top", layout="fill", opts={"cap_style": "line", "bar_pos": "top", "bar_thick": 24}, fx={"bar": True}, segs=((0, 8),))
bb, _ = R("bar_bot", layout="fill", opts={"cap_style": "line", "bar_pos": "bottom", "bar_thick": 24}, fx={"bar": True}, segs=((0, 8),))
TOP, BOT = (0, 0, 1, .03), (0, .97, 1, 1)
dt = (diff(frame(bt, 6.0), frame(nb, 6.0), TOP), diff(frame(bt, 6.0), frame(nb, 6.0), BOT))
db = (diff(frame(bb, 6.0), frame(nb, 6.0), TOP), diff(frame(bb, 6.0), frame(nb, 6.0), BOT))
ok(dt[0] > 8 and dt[1] < 2.5, f"progress bar drawn at the top edge, not the bottom ({dt[0]:.0f}/{dt[1]:.1f})")
ok(db[1] > 8 and db[0] < 2.5, f"progress bar drawn at the bottom edge, not the top ({db[1]:.0f}/{db[0]:.1f})")
w_t = lambda mp4, t: np.asarray(frame(mp4, t).convert("RGB"))[1, :, :].astype(int)
fill = lambda a_, b_: float(np.mean(np.abs(a_ - b_).sum(1) > 60))
f2, f6 = fill(w_t(bt, 2.0), w_t(nb, 2.0)), fill(w_t(bt, 6.0), w_t(nb, 6.0))
ok(f6 > f2 + .2, f"progress bar grows with the clip ({f2 * 100:.0f}% -> {f6 * 100:.0f}% filled)")

# ---------------------------------------------------------------- 17 feeling colours in the captions
ok(vcmedia.feeling_of("hahaha") == "laugh" and vcmedia.feeling_of("lol") == "laugh" and vcmedia.feeling_of("table") == "" and vcmedia.feeling_of("") == "", "feeling_of: laugh / nothing")
ok(vcmedia.feeling_of("aaaah") == "scream" and vcmedia.feeling_of("nooo") == "", "feeling_of: a long scream is a scream")
w1 = vcmedia.feel_wrap("HAHA", "haha"); w2 = vcmedia.feel_wrap("TABLE", "table")
ok("\\1c&H" in w1 and w1.startswith("{") and w1.endswith("{\\1c}") and w2 == "TABLE", f"feel_wrap colours a laugh and leaves a plain word ({w1})")
ok(vcmedia.dominant_feeling(mk("haha lol that was so funny hahaha")) == "laugh" and vcmedia.dominant_feeling(mk("a plain sentence about tables")) == "" and vcmedia.dominant_feeling([]) == "", "dominant_feeling picks the main mood of a clip")
ass_p = os.path.join(W_, "feel.ass")
sc.make_ass(mk("so funny haha lol then calm words here"), frozenset(), ass_p, 1080, 1920, 88, 300, None, "ff4d8d", (), {"cap_feel": True, "cap_style": "pop"})
ass_on = open(ass_p, encoding="utf-8").read()
sc.make_ass(mk("so funny haha lol then calm words here"), frozenset(), ass_p, 1080, 1920, 88, 300, None, "ff4d8d", (), {"cap_feel": False, "cap_style": "pop"})
ass_off = open(ass_p, encoding="utf-8").read()
ok("\\1c&H" + "4DD5FF" in ass_on.upper().replace("\\1C&H", "\\1c&H") and "4DD5FF" not in ass_off.upper(), "captions: laugh words are coloured only when the option is on")
ass_p2 = os.path.join(W_, "feel2.ass")
sc.make_ass(mk("so funny haha lol"), frozenset({"haha"}), ass_p2, 1080, 1920, 88, 300, None, "ff4d8d", (), {"cap_feel": True, "cap_style": "pop"})
ok("****" in open(ass_p2, encoding="utf-8").read(), "a bleeped word is not coloured, it stays starred")

# ---------------------------------------------------------------- 18 logo opacity
ok(vcmedia.logo_alpha_filter(92) == "colorchannelmixer=aa=0.92" and vcmedia.logo_alpha_filter(5) == "colorchannelmixer=aa=0.20" and vcmedia.logo_alpha_filter("zzz") == "colorchannelmixer=aa=0.92", "logo opacity: 92 / clamped to 20 / junk -> default")
LOGO = os.path.join(W_, "logo_a.png"); im = Image.new("RGBA", (200, 200), (255, 0, 200, 255)); im.save(LOGO)
l0, _ = R("logo_none", layout="fill", opts={"cap_style": "line"}, segs=((0, 5),))
l1, _ = R("logo_full", layout="fill", opts={"cap_style": "line", "logo": LOGO, "logo_pos": "tr", "logo_alpha": 100}, segs=((0, 5),))
l2, _ = R("logo_soft", layout="fill", opts={"cap_style": "line", "logo": LOGO, "logo_pos": "tr", "logo_alpha": 40}, segs=((0, 5),))
TR = (.78, .02, .98, .12)
dfull, dsoft = diff(frame(l0, 2.0), frame(l1, 2.0), TR), diff(frame(l0, 2.0), frame(l2, 2.0), TR)
ok(dfull > 15 and 3 < dsoft < dfull * .7, f"logo opacity: 100% differs from no logo by {dfull:.0f}, 40% by {dsoft:.0f}")

# ---------------------------------------------------------------- 19 music by mood
base = tempfile.mkdtemp(prefix="mood_")
for d in ("hype", "chill", "spooky", "funny", "cute"):
    os.makedirs(os.path.join(base, d)); open(os.path.join(base, d, d + ".mp3"), "wb").write(b"x")
pick = lambda folder, ex=(): next((os.path.join(folder, f) for f in sorted(os.listdir(folder)) if f.endswith(".mp3")), None)
mp = lambda kind, feel="": vcmedia.mood_pick(base, kind, pick, feel)
ok(os.path.basename(mp("gameplay")) == "hype.mp3", "mood: gameplay -> hype folder")
ok(os.path.basename(mp("reaction")) == "funny.mp3", "mood: reaction -> funny folder")
ok(os.path.basename(mp("talking")) == "chill.mp3", "mood: talking -> chill folder")
ok(os.path.basename(mp("reaction", "scare")) == "spooky.mp3" and os.path.basename(mp("gameplay", "cute")) == "cute.mp3", "mood: a scare / cute feeling beats the kind of clip")
ok(mp("singing") == "", "mood: a singing clip gets no extra music")
ok(vcmedia.mood_pick(tempfile.mkdtemp(), "gameplay", pick) is None and vcmedia.mood_pick("/no/such/dir", "gameplay", pick) is None, "mood: no mood folders -> use the normal pick")
ok(vcmedia.mood_pick(base, "story", pick) is not None and os.path.basename(vcmedia.mood_pick(base, "story", pick)) == "chill.mp3", "mood: story falls back to the next folder name that exists")

# ---------------------------------------------------------------- 20 soft subtitles, 21 file info, 22 hidden info removed
clip, dur_clip = R("fin1", layout="fill", opts={"cap_style": "line"}, segs=((0, 8),))
srt = os.path.join(W_, "fin1.srt")
sc.write_srt(mk("hello there this is a test of the soft subtitles"), srt)
n_before = len(probe(clip))
ok(vcmedia.add_soft_subs(clip, srt, FF, None) is True, "soft subtitles: added")
st = probe(clip); kinds = [s["codec_type"] for s in st]
ok("subtitle" in kinds and n_before == len(st) - 1 and any(s.get("codec_name") == "mov_text" for s in st), f"soft subtitles: a switchable text track appeared ({kinds})")
vs = [s for s in st if s["codec_type"] == "video"][0]
ok(float(vs.get("duration") or 0) > 7.5, "soft subtitles: the picture is untouched and still plays")
ok(sh(["-i", clip, "-f", "null", "-"]).returncode == 0, "soft subtitles: the file decodes cleanly")
ok(vcmedia.add_soft_subs(clip, os.path.join(W_, "missing.srt"), FF, None) is False and vcmedia.add_soft_subs(os.path.join(W_, "nope.mp4"), srt, FF, None) is False, "soft subtitles: missing files -> False, no crash")
empty = os.path.join(W_, "empty.srt"); open(empty, "w").write("")
ok(vcmedia.add_soft_subs(clip, empty, FF, None) is False, "soft subtitles: empty subtitle file -> nothing done")
ok(not os.path.exists(clip + ".ss.mp4"), "soft subtitles: no temporary file left behind")

ok(vcmedia.write_tags(clip, dict(title="Epic fail!\nline two", artist="MiaVT", genre="Minecraft", comment="VTuber Clipper - reaction", date="2026"), FF, None) is True, "file info: written")
tg = vcmedia.file_tags(clip, FF, None)
ok(tg.get("title", "").startswith("Epic fail!") and "\n" not in tg.get("title", "") and tg.get("artist") == "MiaVT" and tg.get("genre") == "Minecraft", f"file info: title / artist / game are in the file ({tg.get('title')!r})")
ok("subtitle" in [s["codec_type"] for s in probe(clip)], "file info: the soft subtitle track is still there")
ok(vcmedia.write_tags(clip, {}, FF, None) is False and vcmedia.write_tags(os.path.join(W_, "nope.mp4"), dict(title="x"), FF, None) is False, "file info: nothing to write / no file -> False")
ok(vcmedia.scrub(clip, FF, None) is True, "hidden info: removed")
tg2 = vcmedia.file_tags(clip, FF, None)
ok("title" not in tg2 and "artist" not in tg2 and "genre" not in tg2 and "encoder" not in tg2 and "creation_time" not in tg2, f"hidden info: title / artist / encoder / creation time are gone ({sorted(tg2)})")
ok(sh(["-i", clip, "-f", "null", "-"]).returncode == 0 and float([s for s in probe(clip) if s["codec_type"] == "video"][0].get("duration") or 0) > 7.5, "hidden info: the video is untouched")
ok(os.path.getsize(clip) > 1000, "hidden info: file still there and not empty")

# ---------------------------------------------------------------- 23 sound file
mp3 = vcmedia.export_audio(clip, FF, None)
ok(bool(mp3) and os.path.isfile(mp3) and os.path.splitext(mp3)[1] in (".mp3", ".m4a"), f"sound file made ({os.path.basename(mp3)})")
ast = [s for s in probe(mp3) if s["codec_type"] == "audio"]
ok(len(ast) == 1 and not [s for s in probe(mp3) if s["codec_type"] == "video"] and abs(float(ast[0].get("duration") or 0) - 8.0) < .6, "sound file: only sound, same length as the clip")
noaud = os.path.join(paths.FIX, "odd", "noaudio.mp4")
ok(not os.path.isfile(noaud) or vcmedia.export_audio(noaud, FF, None) == "", "sound file: a clip without sound gives no file")
ok(vcmedia.export_audio(os.path.join(W_, "nope.mp4"), FF, None) == "", "sound file: missing clip -> ''")

# ---------------------------------------------------------------- 24 GIF
gif = vcmedia.make_gif(clip, 5.0, FF, None)
gs = probe(gif) if gif else []
ok(bool(gif) and gs and gs[0].get("codec_name") == "gif" and os.path.getsize(gif) <= 8e6, f"GIF made ({os.path.getsize(gif) / 1e6:.1f} MB)" if gif else "GIF made")
ok(gif and gs[0]["height"] > gs[0]["width"] and gs[0]["width"] <= 400, "GIF: stays tall and small enough to share")
ok(gif and 3.5 < float(gs[0].get("duration") or 5) < 5.6, f"GIF: about 5 seconds ({gs[0].get('duration')})")
tiny_clip = os.path.join(W_, "tiny.mp4"); sh(["-f", "lavfi", "-i", "testsrc=s=160x90:d=1:r=10", "-pix_fmt", "yuv420p", tiny_clip])
ok(vcmedia.make_gif(tiny_clip, .5, FF, None) == "", "GIF: a clip shorter than 1.5 s gives none")
big = vcmedia.make_gif(clip, 5.0, FF, None, dest=os.path.join(W_, "limit.gif"), max_mb=0.05)
ok(big == "" or os.path.getsize(big) <= 0.05e6 or probe(big)[0]["width"] <= 200, "GIF: shrunk to the size limit or given up, never a huge file")

# ---------------------------------------------------------------- 25 / 26 sharpest-frame covers
ok(vcmedia.sharpness(np.zeros((40, 40))) == 0.0 and vcmedia.sharpness(np.random.RandomState(1).randint(0, 255, (40, 40))) > 1000 and vcmedia.sharpness(np.zeros((3, 3))) == 0.0, "sharpness: flat 0, noise high, tiny picture safe")
g = np.random.RandomState(2).randint(0, 255, (60, 60)).astype(np.float32); blur_g = (g + np.roll(g, 1, 0) + np.roll(g, 1, 1) + np.roll(g, -1, 0) + np.roll(g, -1, 1)) / 5
ok(vcmedia.sharpness(g) > vcmedia.sharpness(blur_g) * 2, "sharpness: blurry beats sharp -> lower score")
FLASHY = os.path.join(W_, "sharp_at_4.mp4")
sh(["-f", "lavfi", "-i", "color=c=gray:s=192x108:d=8:r=10", "-f", "lavfi", "-i", "nullsrc=s=192x108:d=8:r=10,geq=lum='random(1)*255':cb=128:cr=128",
    "-filter_complex", "[0][1]overlay=enable='between(t,4.0,4.5)'", "-pix_fmt", "yuv420p", FLASHY])
bt_ = vcmedia.best_time(FLASHY, 3.4, FF, None, 1.0)
ok(3.95 <= bt_ <= 4.55, f"best_time: finds the one sharp frame near the moment ({bt_:.2f}s)")
ok(abs(vcmedia.best_time(os.path.join(W_, "nope.mp4"), 3.0, FF, None) - 3.0) < 1e-6, "best_time: unreadable file -> the second it was given")
ok(abs(vcmedia.best_time(FLASHY, 1.0, FF, None, .5) - 1.0) <= .25, "best_time: on a flat picture the second asked for is kept")
cc = vcmedia.cover_candidates(FLASHY, [4.2], FF, None, 3)
ok(len(cc) == 3 and 3.95 <= cc[0] <= 4.55 and all(abs(a - b) >= 1.5 for i, a in enumerate(cc) for b in cc[i + 1:]), f"cover_candidates: sharp moment first, others spread out ({cc})")
ok(len(vcmedia.cover_candidates(tiny_clip, [.3], FF, None, 3)) <= 3, "cover_candidates: a very short clip is handled")
ok(all(.2 <= x <= 7.8 for x in vcmedia.cover_candidates(FLASHY, [-5, 99, 4.0], FF, None, 3)), "cover_candidates: out-of-range seconds are ignored")
ok(vcmedia.cover_candidates(os.path.join(W_, "nope.mp4"), [1], FF, None, 3) == [], "cover_candidates: unreadable file -> none")

# ---------------------------------------------------------------- engine options
o = sc.get_opts({"bg_blur": "extreme", "bg_dim": -20, "bar_pos": "top", "gate": True, "deess": True, "cap_feel": True, "music_mood": True, "soft_subs": True, "gif_clip": True})
ok(o["bg_blur"] == "extreme" and o["bg_dim"] == -20 and o["bar_pos"] == "top" and o["gate"] is True and o["cap_feel"] is True, "options: media settings survive get_opts")
o = sc.get_opts({"bg_blur": "nonsense", "bg_dim": 9999, "bar_pos": "middle", "bar_thick": -5, "logo_alpha": "x"})
ok(o["bg_blur"] == "normal" and -50 <= o["bg_dim"] <= 50 and o["bar_pos"] == "bottom" and 4 <= o["bar_thick"] <= 60 and 20 <= o["logo_alpha"] <= 100, f"options: junk media settings are repaired ({o['bg_blur']}, {o['bg_dim']}, {o['bar_pos']}, {o['bar_thick']}, {o['logo_alpha']})")

print("FAILS:", _n[0])
