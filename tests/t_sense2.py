import sys
import paths
import numpy as np, synth as S, vcsense as V
bad = 0
def ok(n, c, x=""):
    global bad
    print(("PASS " if c else "FAIL ") + n, "" if c else x)
    bad += (not c)
t = np.arange(20 * S.SR) / S.SR
drone = (4000 * np.sin(2 * np.pi * 100 * t)).astype(np.float32)
hum = (4000 * np.sin(2 * np.pi * 220 * t) + 1500 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
song = S.sing(20)[:20 * S.SR]
def mean_sing(a):
    c, h, l, f0 = V.chunk_feats(S.whole_seconds(a)); n = len(c)
    return float(V.sing_curve(f0, n)[0][3:-3].mean())
d, h, s = mean_sing(drone), mean_sing(hum), mean_sing(song)
ok(f"a 100 Hz drone is not singing ({d:.2f})", d < .35)
ok(f"a steady hum on one pitch is not singing ({h:.2f})", h < .35)
ok(f"a tune with changing notes is singing ({s:.2f})", s > .6)
print("FAILS", bad); sys.exit(bad > 0)
