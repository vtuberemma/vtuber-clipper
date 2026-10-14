"""VTuber Clipper 2.0 - picture, sound and overlay helpers (colour looks, crisp picture, auto brightness, black bars, hide a spot,
voice effects, voice EQ, bleep sounds, chibi buddy, lower third / part badge / follow reminder lines).

Everything here only builds ffmpeg filter text or measures a video with ffmpeg - no extra programs, no internet.
streamclip.py calls these from render(); each helper is safe to call with an empty / unknown setting (it then does nothing)."""
import math, re, subprocess

# ---------------------------------------------------------------- picture looks
COLOR_LOOKS = {
    "none": ("Natural (no change)", ""),
    "warm": ("Warm sunset", "eq=saturation=1.08:contrast=1.03,colorbalance=rs=.07:gs=.015:bs=-.08:rm=.05:bm=-.05:rh=.04:bh=-.05"),
    "cool": ("Cool moonlight", "eq=saturation=.95,colorbalance=rs=-.06:bs=.09:rm=-.04:bm=.06:rh=-.03:bh=.05"),
    "vintage": ("Vintage film", "curves=preset=vintage,eq=saturation=.92:contrast=1.04,noise=alls=5:allf=t"),
    "noir": ("Noir black & white", "hue=s=0,eq=contrast=1.22:brightness=-.02"),
    "pastel": ("Pastel dream", "eq=saturation=.88:brightness=.05:contrast=.92:gamma=1.1,colorbalance=rm=.03:bm=.04:gm=-.01"),
    "neon": ("Neon pop", "eq=saturation=1.55:contrast=1.14,colorbalance=rs=.05:bs=.08:bh=.05:rh=.03"),
    "cine": ("Cinematic teal & orange", "colorbalance=rs=-.07:bs=.10:rm=-.02:bm=.04:rh=.10:bh=-.09,eq=contrast=1.08:saturation=1.05"),
}
LOOK_NAMES = {k: v[0] for k, v in COLOR_LOOKS.items()}
CRISP = {"off": ("Off", ""),
         "light": ("Light", "hqdn3d=1.8:1.4:3:3,unsharp=5:5:0.6:5:5:0.0"),
         "strong": ("Strong", "hqdn3d=3.5:2.5:5:5,unsharp=5:5:1.0:5:5:0.35")}
CRISP_NAMES = {k: v[0] for k, v in CRISP.items()}
FADES = {"off": ("Off", 0.0), "quick": ("Quick (0.4 s)", 0.4), "smooth": ("Smooth (0.9 s)", 0.9)}
FADE_NAMES = {k: v[0] for k, v in FADES.items()}
HIDE_STYLES = {"blur": "Blur it", "pixel": "Pixelate it", "black": "Black box"}
VIGNETTE = "vignette=a=PI/4.5"


def look_filter(name): return COLOR_LOOKS.get(name, COLOR_LOOKS["none"])[1]
def crisp_filter(level): return CRISP.get(level, CRISP["off"])[1]


def fade_seconds(name, dur):
    s = FADES.get(name, FADES["off"])[1]
    return min(s, max(0.0, dur / 4.0)) if s else 0.0


# ---------------------------------------------------------------- measuring a video (ffmpeg only)
def _run(ff, args, nowin, timeout=60):
    try: return subprocess.run([ff, "-hide_banner"] + args, capture_output=True, text=True, errors="replace", timeout=timeout, **nowin)
    except Exception: return None


def measure_luma(src, t0, t1, ff, nowin, n=4):
    """Average brightness (0-255) of the video between t0 and t1, from n single frames. None when it can't be measured."""
    vals = []
    for i in range(n):
        t = t0 + (t1 - t0) * (i + .5) / n
        r = _run(ff, ["-v", "error", "-ss", f"{max(0, t):.2f}", "-i", src, "-frames:v", "1", "-vf",
                      "scale=320:-2,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-", "-f", "null", "-"], nowin)
        m = re.search(r"YAVG=([\d.]+)", (r.stdout if r else "") or "")
        if m: vals.append(float(m.group(1)))
    return sum(vals) / len(vals) if vals else None


def light_filter(mean, target=105.0):
    """A gamma lift for a dark video (mean < 95 of 255). '' when the picture is bright enough already."""
    if mean is None or mean >= 95 or mean < 2: return ""
    g = math.log(mean / 255.0) / math.log(target / 255.0)
    g = min(2.0, max(1.0, g))
    return f"eq=gamma={g:.2f}:contrast=1.04" if g >= 1.06 else ""


def auto_light(src, t0, t1, ff, nowin):
    return light_filter(measure_luma(src, t0, t1, ff, nowin))


def detect_bars(src, t0, t1, ff, nowin, sw, sh, n=4):
    """Black bars around a video (letterbox / pillarbox): (w, h, x, y) of the picture, or None when there is nothing to crop.
    Several moments are looked at and the biggest picture wins, so a dark scene can't make the app crop real picture away."""
    boxes = []
    for i in range(n):
        t = t0 + (t1 - t0) * (i + .5) / n
        r = _run(ff, ["-ss", f"{max(0, t):.2f}", "-t", "1.2", "-i", src, "-vf", "cropdetect=limit=24:round=2:reset=0", "-f", "null", "-"], nowin)
        ms = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", (r.stderr if r else "") or "")
        if ms: boxes.append(tuple(int(x) for x in ms[-1]))
    if not boxes or not sw or not sh: return None
    x0, y0 = min(b[2] for b in boxes), min(b[3] for b in boxes)
    x1, y1 = max(b[2] + b[0] for b in boxes), max(b[3] + b[1] for b in boxes)
    x0, y0 = x0 // 2 * 2, y0 // 2 * 2
    w, h = (x1 - x0) // 2 * 2, (y1 - y0) // 2 * 2
    if w < sw * .4 or h < sh * .4: return None                        # far too small to be bars: probably just a dark video
    if w >= sw * .97 and h >= sh * .97: return None                  # nothing worth cropping
    return (min(w, sw - x0), min(h, sh - y0), x0, y0)


def shift_cam(cam, box):
    """The cam area ('w:h:x:y' in the original picture) after the picture was cropped to box = (w, h, x, y). None when it no longer fits."""
    m = re.match(r"^(\d+):(\d+):(\d+):(\d+)$", cam or "")
    if not m or not box: return cam
    w, h, x, y = (int(g) for g in m.groups()); bw, bh, bx, by = box
    x, y = x - bx, y - by
    if x < 0 or y < 0 or x + w > bw or y + h > bh: return None
    return f"{w}:{h}:{x}:{y}"


# ---------------------------------------------------------------- hide a spot
def parse_box(spec):
    """'x:y:w:h' as percent of the picture -> (x, y, w, h) floats, or None."""
    m = re.match(r"^\s*([\d.]+)\s*[:,;]\s*([\d.]+)\s*[:,;]\s*([\d.]+)\s*[:,;]\s*([\d.]+)\s*$", str(spec or ""))
    if not m: return None
    x, y, w, h = (float(g) for g in m.groups())
    if w < 1 or h < 1 or x < 0 or y < 0 or x + w > 100.5 or y + h > 100.5: return None
    return x, y, w, h


def hide_graph(inl, outl, spec, style, sw, sh, tag="hs"):
    """Graph pieces that cover one spot of the picture (source pixels sw x sh): [inl] -> [outl]. [] when the setting is empty or wrong."""
    b = parse_box(spec)
    if not b or not sw or not sh: return []
    x, y = int(sw * b[0] / 100) // 2 * 2, int(sh * b[1] / 100) // 2 * 2
    w, h = max(4, int(sw * b[2] / 100) // 2 * 2), max(4, int(sh * b[3] / 100) // 2 * 2)
    w, h = min(w, sw - x), min(h, sh - y)
    w, h = w // 2 * 2, h // 2 * 2
    if w < 4 or h < 4: return []
    if style == "black":
        return [f"[{inl}]drawbox=x={x}:y={y}:w={w}:h={h}:color=black:t=fill[{outl}]"]
    if style == "pixel":
        eff = f"scale={max(2, w // 18)}:{max(2, h // 18)}:flags=area,scale={w}:{h}:flags=neighbor"
    else:
        eff = f"gblur=sigma={max(8, min(w, h) // 5)}:steps=3"
    return [f"[{inl}]split[{tag}a][{tag}b]", f"[{tag}b]crop={w}:{h}:{x}:{y},{eff}[{tag}c]", f"[{tag}a][{tag}c]overlay={x}:{y}[{outl}]"]


# ---------------------------------------------------------------- voice
def _pitch(r): return f"asetrate=48000*{r:.4f},aresample=48000,atempo={1 / r:.4f}"


VOICE_FX = {
    "none": ("Normal", ""),
    "deep": ("Deeper voice", _pitch(.80)),
    "high": ("Higher voice", _pitch(1.25)),
    "chipmunk": ("Chipmunk", _pitch(1.55)),
    "robot": ("Robot", "afftfilt=real='hypot(re,im)*cos(0)':imag='hypot(re,im)*sin(0)':win_size=512:overlap=0.75,volume=3.0,alimiter=limit=0.95"),
    "echo": ("Echo (cave)", "aecho=0.8:0.7:260|430:0.5|0.3"),
    "phone": ("Old telephone", "highpass=f=500,lowpass=f=3000,volume=1.5"),
    "megaphone": ("Megaphone", "highpass=f=600,lowpass=f=4500,acompressor=threshold=0.05:ratio=8:makeup=2"),
    "underwater": ("Underwater", "lowpass=f=800,aphaser=type=t:speed=.6:decay=.5"),
}
VOICE_FX_NAMES = {k: v[0] for k, v in VOICE_FX.items()}
VOICE_EQ = {
    "natural": ("Natural", ""),
    "warm": ("Warm and soft", "equalizer=f=120:t=q:w=1:g=3,equalizer=f=3500:t=q:w=1.2:g=-2"),
    "crisp": ("Crisp and clear", "equalizer=f=200:t=q:w=1:g=-2,equalizer=f=4500:t=q:w=1:g=3.5,equalizer=f=9000:t=q:w=.8:g=2"),
    "podcast": ("Podcast / radio", "highpass=f=80,equalizer=f=150:t=q:w=1:g=3,equalizer=f=3000:t=q:w=1:g=2.5,acompressor=threshold=0.12:ratio=3:attack=10:release=200:makeup=1.8"),
}
VOICE_EQ_NAMES = {k: v[0] for k, v in VOICE_EQ.items()}


def voice_chain(eq="natural", fx="none"):
    """',filter,filter' to put after the voice clean-up, or ''."""
    parts = [VOICE_EQ.get(eq, VOICE_EQ["natural"])[1], VOICE_FX.get(fx, VOICE_FX["none"])[1]]
    parts = [p for p in parts if p]
    return ("," + ",".join(parts)) if parts else ""


# what replaces a bleeped word (the original voice is muted under it): a tone expression for aevalsrc (t = seconds since the start of the clip)
BLEEPS = {
    "beep": ("Classic beep", "0.2*sin(2*PI*1000*t)"),
    "silence": ("Silence", "0"),
    "boing": ("Cartoon boing", "0.24*sin(2*PI*(320+520*abs(sin(6.5*t)))*t)"),
    "ding": ("Ding", "0.26*sin(2*PI*1568*t)*(.45+.55*abs(sin(5.5*t)))"),
    "duck": ("Duck quack", "0.17*sgn(sin(2*PI*(430+45*sin(34*t))*t))*(.6+.4*abs(sin(9*t)))"),
    "laser": ("Laser zap", "0.2*sin(2*PI*(2000-1700*mod(t,.22)/.22)*t)"),
}
BLEEP_NAMES = {k: v[0] for k, v in BLEEPS.items()}


def bleep_tone(name): return BLEEPS.get(name, BLEEPS["beep"])[1]


LOUDNESS = {"-14": "Loud and clear (-14 LUFS, TikTok / Shorts)", "-16": "A bit quieter (-16 LUFS, podcast style)", "-12": "Extra loud (-12 LUFS)", "off": "Leave the volume as it is"}


def loudnorm_chain(level, norm=True):
    if not norm or level == "off": return "anull"
    lufs = level if level in ("-14", "-16", "-12") else "-14"
    return f"loudnorm=I={lufs}:TP=-1.5,aresample=48000"


# ---------------------------------------------------------------- chibi buddy (bounces while you talk)
def talk_segments(owords, dur, gap=.35, pad=.05, maxn=40):
    """[(start, end)] while someone is talking. A gap shorter than `gap` seconds does not count as a pause; the list is kept short."""
    ws = sorted((w["start"], w["end"]) for w in owords or [] if w.get("end", 0) > w.get("start", 0))
    while True:
        segs = []
        for a, b in ws:
            if segs and a - segs[-1][1] <= gap: segs[-1][1] = max(segs[-1][1], b)
            else: segs.append([a, b])
        if len(segs) <= maxn or gap > 3: break
        gap *= 1.6
    return [(max(0.0, a - pad), min(dur, b + pad)) for a, b in segs if a < dur]


def talk_expr(segs, tv="t"):
    return "+".join(f"between({tv},{a:.2f},{b:.2f})" for a, b in segs) or "0"


def buddy_y_expr(base_y, amp, segs):
    """Overlay y: sits at base_y, hops while talking, breathes a little while quiet."""
    talk = talk_expr(segs)
    b = f"{base_y:.1f}" if isinstance(base_y, (int, float)) else str(base_y)
    return f"{b}-{amp:.1f}*abs(sin(11*t))*min(1,{talk})-{amp * .12:.1f}*sin(2.2*t)"


# ---------------------------------------------------------------- ASS lines: lower third, part badge, follow reminder
def ass_extras(o, g):
    """Extra caption-canvas lines for the .ass file. g: dict(W, H, tall, K, dur, safe, sz, ts, san, upper). Each block is checked on its own,
    so a wrong value in one setting never takes the others (or the captions) down."""
    out, W, H, K, dur, ts, san = [], g["W"], g["H"], g["K"], g["dur"], g["ts"], g["san"]
    sb, sr, st = g["safe"]; sz = g["sz"]; tall = g["tall"]
    up = g["upper"]
    try:
        name = san(str(o.get("lower_name") or "").strip())[:40]
        if name and dur > 3.0:                                           # lower third: your name (and a line under it) slides in from the left
            sub = san(str(o.get("lower_sub") or "").strip())[:50]
            short = dur < 8.5
            t0, t1 = (.5, min(dur - .3, 3.6)) if short else (3.0, min(dur - .3, 6.6))
            x = int(48 * K); buddy_top = bool(o.get("buddy")) and o.get("buddy_pos") in ("tl", "tr")
            y = int(H * (.30 if (short or buddy_top) else .22 if tall else .16)) + int(H * st)
            nsz, ssz = max(22, int(sz * .56)), max(18, int(sz * .36))
            out.append(f"Dialogue: 5,{ts(t0)},{ts(t1)},Box,,0,0,0,,{{\\an1\\move({-int(W * .6)},{y},{x},{y},0,300)\\fs{nsz}\\fad(0,250)}}{up(name)}")
            if sub: out.append(f"Dialogue: 5,{ts(t0 + .1)},{ts(t1)},Line,,0,0,0,,{{\\an7\\move({-int(W * .6)},{y + int(nsz * .32)},{x + int(nsz * .25)},{y + int(nsz * .32)},0,360)\\fs{ssz}\\fad(0,250)}}{sub}")
    except Exception: pass
    try:
        part = o.get("part")
        if o.get("part_badge") and part and len(part) == 2 and int(part[1]) > 1 and dur > 1.5:      # "PART 2/3" badge at the top for a series
            y = max(int(H * .035), int(H * (st + .012)))
            out.append(f"Dialogue: 6,{ts(0)},{ts(dur)},Box,,0,0,0,,{{\\an8\\pos({W // 2},{y})\\fs{max(20, int(sz * .42))}\\3a&H20&\\fad(150,150)}}PART {int(part[0])}/{int(part[1])}")
    except Exception: pass
    try:
        ft = san(str(o.get("follow_text") or "").strip())[:40]
        if ft and dur >= 8.0:                                            # a short "follow" nudge in the middle of the clip
            t0 = min(max(2.5, dur * .42), dur - 4.8); cy = int(H * (.52 if tall else .55))
            out.append(f"Dialogue: 6,{ts(t0)},{ts(t0 + 2.4)},Box,,0,0,0,,{{\\an5\\pos({W // 2},{cy})\\fad(200,200)\\fscx55\\fscy55\\t(0,240,\\fscx112\\fscy112)\\t(240,420,\\fscx100\\fscy100)\\t(1100,1300,\\fscx106\\fscy106)\\t(1300,1500,\\fscx100\\fscy100)}}{up(ft)}")
    except Exception: pass
    return out
