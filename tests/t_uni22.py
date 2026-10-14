"""Tricky text everywhere: captions with quotes/braces/backslashes/emoji/CJK, odd folder + file names, hashtags, name pattern.
usage: t_uni22.py [shape]  (no argument = everything on)"""
import sys, os, json, tempfile, argparse, glob, time, shutil, subprocess, re
import paths; S = paths.ROOT
H = tempfile.mkdtemp(); os.environ["HOME"] = H
sys.path.insert(0, paths.APP); import streamclip as sc, vcmore
sc.FF = paths.FFMPEG; sc.HW = dict(cores=8, cpu="x", ram=8, gpus=[], enc="libx264", cuda_ok=False)
sc.OUT.update(mbps=4, res=360, fps=24); sc.CACHE_DIR = tempfile.mkdtemp()
vcmore.LEDGER = os.path.join(H, "ledger.json")
W = os.path.join(tempfile.mkdtemp(prefix="uni_"), "Mé ’vod’ [01] & {x} 日本語 😀 100%;")
os.makedirs(W); vid = os.path.join(W, "stréam 'one' {b} [x] 日本 😀 50%.mp4")
shutil.copy(paths.FIX + "/odd/odd.mp4", vid)
words = json.load(open(paths.FIX + "/odd/odd.mp4.words.json"))
weird = ['"quoted"', "it's", "{\\b1}bold", "back\\slash", "\\N", "100%", "a:b,c;d", "😀", "日本語", "ça", "ünï", "OMG", "[tag]", "<b>x</b>", "x=1", "$(rm)", "`tick`", "&amp;", "'", '"', "{", "}", "\\"]
for i, w in enumerate(words["words"]):
    if i % 3 == 1: w["w"] = weird[(i // 3) % len(weird)]
json.dump(words, open(vid + ".words.json", "w"), ensure_ascii=False)
fx = {k: 0 for k in sc.FX["gameplay"]}; fx.update(intensity=1.0, accent="ff4d8d", sfx=1, zoom=1, hook=1, bar=1, cutzoom=1)
rd = os.path.join(H, "Ready ’to’ post 日本 {x}")
o = dict(post_kit=True, fresh=False, cover=True, srt=True, transcript=True, auto_look=True, smart_len=True, use_taste=True, react_words=True, extra_shapes="1:1", ready_dir=rd,
         cap_case="upper", cap_outline="thick", cap_shadow=4, cap_words=2, cap_box=50, cap_rainbow=True, cap_style="karaoke",
         name_pattern="{date} {type} 日本 'q' {n} [{score}]", handle="@t{ë}st\\n'\"", cta="Follow ♡ 'now' {x}\\N", game="Ünïcode 'Gäme' {1}", hashtags="#日本 #vtuber #ça",
         range_from="0:01")
out = os.path.join(H, "Üut ’dir’ 日本 [1] & {x}")
a = argparse.Namespace(video=vid, model="tiny", device="cpu", censor=None, gap=1.5, style="mix", opts=o, fx=fx, n=2, len_min=8, len_max=20, layout="blur", cam=None, no_silence=False, no_captions=False, out=out, windows=None)
t = time.time()
try: sc.cmd_shorts(a); res = "OK"
except Exception as e:
    import traceback; traceback.print_exc(); res = "ERR " + str(e)[:200]
fs = sorted(glob.glob(glob.escape(out) + "/Shorts/**/*.mp4", recursive=True)); bad = []
for f in fs:
    r = subprocess.run([sc.FF, "-v", "error", "-i", f, "-f", "null", "-"], capture_output=True, text=True, timeout=120)
    if r.returncode or r.stderr.strip(): bad.append((os.path.basename(f), r.stderr.strip()[:80]))
rdf = os.listdir(rd) if os.path.isdir(rd) else []
print("FILES", [os.path.basename(f) for f in fs]); print("READY", rdf)
txt = [f for f in glob.glob(glob.escape(out) + "/**/*.txt", recursive=True)][:2]
for f in txt: print("TXT", os.path.basename(f), open(f, encoding="utf-8").read()[:300].replace("\n", " | "))
print(f"RESULT uni {res} clips={len(fs)} broken={bad} ready={len(rdf)} {time.time() - t:.0f}s")
