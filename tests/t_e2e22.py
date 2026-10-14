"""End to end on the synthetic stream with everything on: the plan's extras really reach the picture (reaction words, hopping logo, case, box, rainbow)."""
import sys, os, json, tempfile, argparse, glob, time, re, subprocess
import paths; S = paths.ROOT
H = tempfile.mkdtemp(); os.environ["HOME"] = H
sys.path.insert(0, paths.APP); import streamclip as sc, vcmore
sc.FF = paths.FFMPEG; sc.HW = dict(cores=8, cpu="x", ram=8, gpus=[], enc="libx264", cuda_ok=False)
sc.OUT.update(mbps=4, res=360, fps=24); sc.CACHE_DIR = tempfile.mkdtemp()
vcmore.LEDGER = os.path.join(H, "ledger.json")
D = json.load(open(paths.FIX + "/stream22.json")); WORDS = D["words"]
sc.transcribe = lambda *a, **k: WORDS
ASS, GR = [], []
_ma = sc.make_ass
def ma(*a, **k):
    r = _ma(*a, **k)
    try: ASS.append(open(a[2], encoding="utf-8").read())
    except Exception: pass
    return r
sc.make_ass = ma
os.environ["VC_KEEP_GRAPH"] = os.path.join(H, "graph.txt")
from PIL import Image, ImageDraw
LOGO = os.path.join(H, "logo.png"); im = Image.new("RGBA", (200, 200), (0, 0, 0, 0)); ImageDraw.Draw(im).ellipse((10, 10, 190, 190), fill=(255, 40, 160, 255)); im.save(LOGO)
fx = {k: 0 for k in sc.FX["gameplay"]}; fx.update(intensity=1.0, accent="ff4d8d", sfx=1, zoom=1, hook=1, bar=1, cutzoom=1)
o = dict(post_kit=True, fresh=False, cover=False, auto_look=True, smart_len=True, tight_end=True, react_words=True, hop_logo=True, logo=LOGO, cap_case="lower", cap_box=60, cap_rainbow=True, cap_style="karaoke",
         ready_dir=os.path.join(H, "ready"), tame=True, hush=True)
out = os.path.join(H, "out")
a = argparse.Namespace(video=paths.FIX + "/stream22.mp4", model="tiny", device="cpu", censor=None, gap=1.5, style="mix", opts=o, fx=fx, n=5, len_min=15, len_max=30, layout="blur", cam=None, no_silence=False, no_captions=False, out=out, windows=None)
sc.cmd_shorts(a)
R = []
def ck(m, c): R.append(c); print(("PASS " if c else "FAIL ") + m, flush=True)
fs = sorted(glob.glob(out + "/Shorts/*.mp4"))
ck(f"clips made ({len(fs)})", len(fs) >= 3)
bad = [f for f in fs if subprocess.run([sc.FF, "-v", "error", "-i", f, "-f", "null", "-"], capture_output=True, text=True).stderr.strip()]
ck("all clips decode", not bad)
txt = "\n".join(ASS)
rl = re.findall(r"Dialogue: 5,[^\n]*", txt)
ck(f"reaction words reached the caption files ({len(rl)} lines, e.g. {[re.sub(r'.*}', '', x) for x in rl[:4]]})", len(rl) >= 1 and any(re.search(r"(LOL|EEEEK|OOF|LET|OMG|AWW|HAHA|NO|GG|WOW)", x) for x in rl))
ck("caption case 'lower' applied", bool(re.search(r"Dialogue: 2,[^\n]*\}[a-z' ,.!?]+", txt)))
ck("see-through box layer exists", "DefaultB" in txt or ",Box," in txt)
ck("rainbow words use several colours", len(set(re.findall(r"\\1c(&H[0-9A-F]{6})&", txt))) >= 3)
gr = open(os.environ["VC_KEEP_GRAPH"]).read() if os.path.exists(os.environ["VC_KEEP_GRAPH"]) else ""
ck("hopping logo expression is in the filter graph", "mod(t," in gr)
ck("tame/hush audio filters in the graph", ("acompressor" in gr or "alimiter" in gr or "compand" in gr) and ("afftdn" in gr or "highpass" in gr or "anlmdn" in gr or "arnndn" in gr))
led = vcmore.ledger_all()
ck(f"ledger labels: {[e['kind'] for e in led]}", len(led) >= 3 and all(e["kind"] for e in led))
ck("ready folder has the clips", len(glob.glob(os.path.join(H, "ready", "*.mp4"))) == len(fs))
t0 = open(sorted(glob.glob(out + "/Shorts/*.txt"))[0], encoding="utf-8").read()
ck("post kit says why", "WHY THIS MOMENT" in t0)
print("FAILS:", R.count(False))
