import sys, time
import paths
import numpy as np, synth as S, vcsense as V
# timeline: label, audio
parts = [("game", S.game(20)), ("speech", S.speech(24)), ("laugh", S.laugh(4)), ("speech2", S.speech(10, f0=300)), ("scream", S.mix(S.game(4, booms=False), S.scream(1.3))),
         ("game2", S.game(12)), ("quiet+scream", np.concatenate([S.quiet(1.8), S.scream(1.2)])), ("sing", S.mix(S.sing(14), S.game(14, 400, False))),
         ("speech3", S.speech(12, f0=220)), ("sing-high", S.sing(10, low=False)), ("laugh2+speech", S.mix(S.laugh(5), S.speech(5, 280, 2500)))]
a = np.concatenate([S.whole_seconds(p) for _, p in parts]); n = len(a) // S.SR
bounds, t = [], 0
for name, p in parts:
    d = len(S.whole_seconds(p)) // S.SR; bounds.append((name, t, t + d)); t += d
t0 = time.time()
cent, hi, lo, f0 = V.chunk_feats(a)
print("feats %.2fs" % (time.time() - t0), len(cent), len(f0))
x = np.abs(a).reshape(n, S.SR); rms = np.sqrt((x ** 2).mean(1)); r50 = np.sqrt((a.reshape(-1, 800) ** 2).mean(1))
rz = (rms - rms.mean()) / (rms.std() + 1e-6)
prev = np.concatenate([[0.0], np.convolve(r50, np.ones(10) / 10, "full")[:len(r50) - 1]])
st = (r50 - prev) / ((r50 - prev).std() + 1e-6); lm = st.copy()
for s in range(1, 7): lm = np.maximum(lm, np.maximum(np.roll(st, s), np.roll(st, -s)))
idx = np.where((st >= lm) & (st > 2.5) & (r50 > np.median(r50) * 1.5))[0]
ons = [(float(i * .05), float(st[i])) for i in idx]
c = V.curves(r50, rz, ons, f0, cent, n, hi)
print("%-14s %5s %5s | laugh scream  sing  setup | voiced" % ("part", "from", "to"))
for name, a0, b0 in bounds:
    print("%-14s %5d %5d | %.2f/%.2f  %.2f/%.2f  %.2f/%.2f  %.2f | %.2f" % (name, a0, b0, c["laugh"][a0:b0].max(), c["laugh"][a0:b0].mean(), c["scream"][a0:b0].max(), c["scream"][a0:b0].mean(),
          c["sing"][a0:b0].max(), c["sing"][a0:b0].mean(), c["setup"][a0:b0].max(), c["voiced"][a0:b0].mean()))
print("---- fraction of seconds above 0.5")
for name,a0,b0 in bounds: print("%-14s laugh %.2f scream %.2f sing %.2f setup %.2f"%(name,(c["laugh"][a0:b0]>.5).mean(),(c["scream"][a0:b0]>.2).mean(),(c["sing"][a0:b0]>.5).mean(),(c["setup"][a0:b0]>.3).mean()))
print("---- raw features per part: cent hi lo rmsz(max)")
for name, a0, b0 in bounds:
    print("%-14s cent %6.0f hi %.2f lo %.2f rz %.1f voiced %.2f" % (name, cent[a0:b0].mean(), hi[a0:b0].mean(), lo[a0:b0].mean(), rz[a0:b0].max(), c["voiced"][a0:b0].mean()))
