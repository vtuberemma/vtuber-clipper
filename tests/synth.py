"""Test sounds for the 2.2 detectors: speech-like, laughter, screams, singing, game noise, silence. 16 kHz mono, int16 scale float32."""
import numpy as np

SR = 16000
RNG = np.random.default_rng(7)


def _t(d): return np.arange(int(d * SR)) / SR


def _formant(h, f, bw=120.0):
    return 1.0 / (1.0 + ((h - f) / bw) ** 2)


def voiced(f0_curve, dur, formants=(700, 1200, 2600), amp=1.0, breath=0.03):
    """Harmonic voice: f0_curve(t) in Hz, shaped by formant peaks."""
    t = _t(dur); f = np.vectorize(f0_curve)(t) if callable(f0_curve) else np.full_like(t, float(f0_curve))
    ph = 2 * np.pi * np.cumsum(f) / SR
    y = np.zeros_like(t)
    for h in range(1, 40):
        fh = h * f
        w = sum(_formant(fh, F) for F in formants) + .05
        w = np.where(fh < 7000, w, 0)
        y += w * np.sin(h * ph) / (h ** .6)
    y /= (np.abs(y).max() + 1e-9)
    y += breath * RNG.standard_normal(len(t))
    return (amp * y).astype(np.float32)


def env(n, a=.01, r=.03):
    e = np.ones(n, np.float32); na, nr = int(a * SR), int(r * SR)
    if na: e[:na] = np.linspace(0, 1, na)
    if nr: e[-nr:] = np.minimum(e[-nr:], np.linspace(1, 0, nr))
    return e


def speech(dur, f0=240, amp=3500):
    """Continuous voice: syllables of 120-250 ms (the volume dips to ~35% between them, not to silence), gliding pitch, phrase pauses every 1.5-4 s."""
    n = int(dur * SR); t = _t(dur)
    f = np.zeros(n, np.float32); am = np.zeros(n, np.float32); i = 0; cur = float(f0)
    while i < n:
        d = int(RNG.uniform(1.5, 4.0) * SR)                     # one phrase
        j = i
        while j < min(n, i + d):
            L = int(RNG.uniform(.12, .25) * SR); L = min(L, n - j)
            tgt = float(f0 * RNG.uniform(.8, 1.3))
            f[j:j + L] = np.linspace(cur, tgt, L); cur = tgt
            ph = np.linspace(0, np.pi, L); am[j:j + L] = .35 + .65 * np.sin(ph) ** 1.5
            cg = int(RNG.uniform(.035, .075) * SR)                      # consonant: no voice, a bit of hiss
            if RNG.random() < .85 and j + L + cg < n:
                am[j + L:j + L + cg] = -.22; L += cg                       # (negative = unvoiced hiss, handled below)
            j += L
        gap = int(RNG.uniform(.25, .7) * SR); am[j:j + gap] = 0.0; f[j:j + gap] = cur
        i = j + gap
    f = np.maximum(f, 80)
    ph = 2 * np.pi * np.cumsum(f) / SR
    y = np.zeros(n, np.float32)
    fm = (700, 1200, 2600)
    for h in range(1, 30):
        fh = h * f; w = sum(_formant(fh, F) for F in fm) + .05
        y += (np.where(fh < 6500, w, 0) * np.sin(h * ph) / (h ** .6)).astype(np.float32)
    y /= (np.abs(y).max() + 1e-9)
    hiss = (am < 0)
    y = np.where(hiss, 0.0, y * np.maximum(am, 0)) + (.02 + .05 * (am > 0)) * RNG.standard_normal(n).astype(np.float32) * np.maximum(np.abs(am), .15) * np.where(hiss, 1.6, 1.0)
    return (amp * y).astype(np.float32)


def laugh(dur=3.0, amp=6000):
    """ha-ha-ha: bursts every ~190-230 ms, near silence between them."""
    out, t = [], 0.0
    while t < dur:
        d = .11; per = float(RNG.uniform(.19, .23))
        f0 = float(RNG.uniform(330, 470))
        seg = voiced(lambda x, f0=f0: f0 * (1 - .25 * x / d), d, (900, 1500, 2700), amp=amp, breath=.18) * env(int(d * SR), .01, .05)
        out.append(seg)
        out.append((40 * RNG.standard_normal(int((per - d) * SR))).astype(np.float32)); t += per
    return np.concatenate(out)[:int(dur * SR)]


def scream(dur=1.3, amp=14000):
    t = _t(dur)
    f = 760 + 500 * np.minimum(1, t / .5) + 25 * np.sin(2 * np.pi * 7 * t)
    ph = 2 * np.pi * np.cumsum(f) / SR
    y = sum(np.sin(h * ph) / h ** .45 for h in range(1, 12)) + .1 * RNG.standard_normal(len(t))
    y = y / (np.abs(y).max() + 1e-9) * amp
    return (y * env(len(t), .004, .12)).astype(np.float32)


def sing(dur=6.0, amp=5000, low=True):
    """Held notes (0.6-1.3 s) with vibrato."""
    notes = [262, 294, 330, 349, 392, 440, 349, 330] if low else [392, 440, 494, 523, 587, 523, 494, 440]
    out, t, k = [], 0.0, 0
    while t < dur:
        d = float(RNG.uniform(.6, 1.3)); f = notes[k % len(notes)] * 1.0; k += 1
        seg = voiced(lambda x, f=f: f * 2 ** ((.45 * np.sin(2 * np.pi * 5.5 * x)) / 12), d, (800, 1300, 2800), amp=amp, breath=.01) * env(int(d * SR), .05, .08)
        out.append(seg); t += d
    return np.concatenate(out)[:int(dur * SR)]


def game(dur, amp=1500, booms=True):
    """Noise bed + low hum + occasional explosions (loud, LOW and dull)."""
    n = int(dur * SR); t = _t(dur)
    y = amp * .5 * RNG.standard_normal(n) + amp * .6 * np.sin(2 * np.pi * 110 * t) + amp * .3 * np.sin(2 * np.pi * 165 * t)
    if booms:
        for at in np.arange(2.5, dur - 1, 6.0):
            i = int(at * SR); m = min(n - i, int(.9 * SR)); k = np.arange(m)
            y[i:i + m] += 9000 * np.exp(-k / (.2 * SR)) * (RNG.standard_normal(m) * .5 + np.sin(2 * np.pi * 70 * k / SR))
    return y.astype(np.float32)


def quiet(dur, amp=25): return (amp * RNG.standard_normal(int(dur * SR))).astype(np.float32)


def mix(*parts):
    n = max(len(p) for p in parts); y = np.zeros(n, np.float32)
    for p in parts: y[:len(p)] += p
    return y


def whole_seconds(a):
    s = len(a) // SR
    if len(a) % SR: a = np.concatenate([a, np.zeros(SR - len(a) % SR, np.float32)]); s += 1
    return a[:s * SR]
