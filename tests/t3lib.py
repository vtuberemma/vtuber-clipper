"""Small shared helpers for the engine tests: a throw-away HOME (so nothing of yours is touched), the engine, PASS/FAIL printing and fake speech."""
import sys, os, tempfile, shutil, subprocess, io, re
import paths
S = paths.ROOT
os.environ["HOME"] = tempfile.mkdtemp(); os.environ["USERPROFILE"] = os.environ["HOME"]
import numpy as np
import streamclip as sc
from PIL import Image, ImageChops, ImageStat
SRC = paths.need(paths.FIX + "/stream22.mp4")                 # the synthetic stream is the default picture + sound for render tests
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m, flush=True)
W_ = tempfile.mkdtemp(prefix="t3_")
sc.OUT.update(res=540, fps=25, mbps=6)


def mk(text, t0=0.0):
    """Words with made-up times for a sentence."""
    ws, t = [], t0
    for w in text.split():
        d = .2 + .03 * min(len(w), 9); ws.append({"w": w, "start": t, "end": t + d}); t += d + .04
        if w.endswith((".", "!", "?")): t += .25
    return ws


TEXT = "Hello there everyone this is only a quiet little test sentence without any feelings at all and we keep talking for a good while longer so the clip stays full."
WORDS = mk(TEXT)


def frame(mp4, t, tag=""):
    r = subprocess.run([paths.FFMPEG, "-v", "error", "-ss", f"{t:.3f}", "-i", mp4, "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
    return Image.open(io.BytesIO(r.stdout)).convert("RGB")
def crop(im, b):   # fractions
    w, h = im.size; return im.crop((int(w * b[0]), int(h * b[1]), int(w * b[2]), int(h * b[3])))
def diff(a, b, box=None):
    if box: a, b = crop(a, box), crop(b, box)
    return sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / 3
def luma(im, box=None):
    im = crop(im, box) if box else im; return sum(ImageStat.Stat(im.convert("L")).mean)
def rgb(im, box=None):
    im = crop(im, box) if box else im; return ImageStat.Stat(im).mean
def sat(im, box=None):
    im = crop(im, box) if box else im; a = np.asarray(im.resize((80, 80))).astype(float) / 255
    mx, mn = a.max(2), a.min(2); return float(np.mean(np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)))
def R(name, src=SRC, segs=((0.0, 12.0),), words=None, opts=None, layout="blur", cam=None, censor=frozenset(), fx=None, norm=False, events=()):
    out = os.path.join(W_, name + ".mp4"); words = WORDS if words is None else words
    f = dict(intensity=1.0, accent="ff4d8d"); f.update(fx or {})
    ow, d = sc.render(src, [tuple(x) for x in segs], words, out, layout, cam, True, censor, f, list(events), None, None, norm=norm, opts={"cap_emoji": False, **(opts or {})})
    return out, d
def audio(mp4):
    r = subprocess.run([paths.FFMPEG, "-v", "error", "-i", mp4, "-f", "f32le", "-ac", "1", "-ar", "48000", "-"], capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.float32)
def rms(a, t0, t1, sr=48000):
    x = a[int(t0 * sr):int(t1 * sr)]; return float(np.sqrt(np.mean(x ** 2))) if len(x) else 0.0
def peak(a, t0, t1, lo=100, hi=3000, sr=48000):
    x = a[int(t0 * sr):int(t1 * sr)]; sp = np.abs(np.fft.rfft(x * np.hanning(len(x)))); fr = np.fft.rfftfreq(len(x), 1 / sr)
    m = (fr >= lo) & (fr <= hi); return float(fr[m][np.argmax(sp[m])])
def band(a, t0, t1, f0, f1, sr=48000):
    x = a[int(t0 * sr):int(t1 * sr)]; sp = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2; fr = np.fft.rfftfreq(len(x), 1 / sr)
    return float(sp[(fr >= f0) & (fr <= f1)].sum())
def lufs(mp4):
    r = subprocess.run([paths.FFMPEG, "-v", "info", "-nostats", "-i", mp4, "-af", "ebur128=peak=none", "-f", "null", "-"], capture_output=True, text=True)
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr); return float(m[-1]) if m else None
def db(x, y): return 10 * np.log10(max(x, 1e-12) / max(y, 1e-12))


