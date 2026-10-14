"""Run the shorts pipeline with every 2.2 feature switched on over the odd media of the old bug hunts (no audio, mono, 24/60 fps, portrait, 4:3, 10-bit, VFR, very short...).
usage: t_odd22.py <file> [mode]   - mode 'all' (default) = everything on, 'plain' = defaults"""
import sys, os, json, tempfile, argparse, glob, time, shutil, subprocess
import paths; S = paths.ROOT
src = sys.argv[1]; mode = sys.argv[2] if len(sys.argv) > 2 else "all"
H = tempfile.mkdtemp(); os.environ["HOME"] = H
sys.path.insert(0, paths.APP); import streamclip as sc, vcmore
sc.FF = paths.FFMPEG; sc.HW = dict(cores=8, cpu="x", ram=8, gpus=[], enc="libx264", cuda_ok=False)
sc.OUT.update(mbps=4, res=360, fps=24); sc.CACHE_DIR = tempfile.mkdtemp()
vcmore.LEDGER = os.path.join(H, "ledger.json")
W = tempfile.mkdtemp(prefix="odd_"); base = os.path.basename(src)
shutil.copy(src, W + "/" + base)
for g in glob.glob(src + ".words*.json"): shutil.copy(g, W + "/" + os.path.basename(g))
vid = W + "/" + base
fx = {k: 0 for k in sc.FX["gameplay"]}; fx.update(intensity=1.0, accent="ff4d8d", sfx=1, zoom=1, hook=1, bar=1, cutzoom=1)
from PIL import Image, ImageDraw
LOGO = os.path.join(H, "logo.png"); im = Image.new("RGBA", (200, 200), (0, 0, 0, 0)); ImageDraw.Draw(im).ellipse((10, 10, 190, 190), fill=(255, 40, 160, 255)); im.save(LOGO)
o = dict(post_kit=True, fresh=False, cover=True, srt=True, transcript=True)
if mode == "all":
    o.update(auto_look=True, smart_len=True, tight_end=True, use_taste=True, react_words=True, slowmo=True, freeze=True, teaser=True, extra_shapes="1:1", hop_logo=True, logo=LOGO, hush=True, tame=True,
             cap_case="upper", cap_outline="thick", cap_shadow=4, cap_words=2, cap_box=50, cap_rainbow=True, cap_style="karaoke", ready_dir=os.path.join(H, "ready"),
             name_pattern="{date} {type} {score} {len} clip {n}", range_from="0:01", handle="@tëst", cta="Follow ♡")
out = os.path.join(H, "out")
a = argparse.Namespace(video=vid, model="tiny", device="cpu", censor=None, gap=1.5, style="mix", opts=o, fx=fx, n=2, len_min=8, len_max=20, layout="blur", cam=None, no_silence=False, no_captions=False, out=out, windows=None)
t = time.time()
try: sc.cmd_shorts(a); res = "OK"
except Exception as e:
    import traceback; traceback.print_exc(); res = "ERR " + str(e)[:160]
fs = sorted(glob.glob(out + "/Shorts/**/*.mp4", recursive=True)); bad = []
for f in fs:
    try:
        r = subprocess.run([sc.FF, "-v", "error", "-i", f, "-f", "null", "-"], capture_output=True, text=True, timeout=120)
        if r.returncode or r.stderr.strip(): bad.append((os.path.basename(f), r.stderr.strip()[:80]))
    except Exception as e: bad.append((os.path.basename(f), str(e)[:60]))
rd = glob.glob(os.path.join(H, "ready", "*")) if mode == "all" else []
print(f"RESULT {base} [{mode}] {res} clips={len(fs)} broken={bad} ready_files={len(rd)} {time.time() - t:.0f}s")
shutil.rmtree(H, ignore_errors=True); shutil.rmtree(W, ignore_errors=True)
