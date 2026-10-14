"""VTuber Clipper 2.2 - audio sense: cheap per-second detectors for laughter, screams, singing and "quiet beat, then boom".
Only numpy. The engine feeds this the 16 kHz audio of a video in whole-second chunks (while it already decodes it for the loudness analysis),
and later turns the saved features into one score curve per detector. These are rules of thumb tuned on test sounds - they nudge the
clip finder, they are not a trained model, and every curve is 0..1 so a wrong guess can only move a moment up or down a little."""
import numpy as np

SR = 16000
FR = 640                    # 40 ms pitch frames -> 25 per second
FPS_F = SR // FR
LAG_LO, LAG_HI = 16, 267    # 1000 Hz ... 60 Hz
MIN_RMS = 120.0             # pitch frames quieter than this (int16 scale) count as unvoiced


# ================================================================ features of a chunk of audio
def pitch_frames(fr):
    """(N, 640) float frames -> f0 in Hz for every 40 ms frame, 0 where there is no clear pitch."""
    fr = np.asarray(fr, np.float32)
    N, L = fr.shape
    if N == 0: return np.zeros(0, np.float32)
    x = fr - fr.mean(1, keepdims=True)
    e = (x * x).sum(1) + 1e-9
    nfft = 2 * L
    X = np.fft.rfft(x, nfft, axis=1)
    ac = np.fft.irfft(X * np.conj(X), nfft, axis=1)[:, :L]
    nac = ac / e[:, None] * (L / (L - np.arange(L)))[None, :]
    seg = nac[:, LAG_LO:LAG_HI]
    ar = np.arange(N)
    k = seg.argmax(1); m = seg[ar, k]; lag = k + LAG_LO
    half = np.round(lag / 2.0).astype(int)                 # a pitch an octave too low is a very common mistake: prefer the half lag when it is nearly as strong
    ok = half >= LAG_LO
    hv = np.where(ok, nac[ar, np.where(ok, half, LAG_LO)], -1.0)
    use = ok & (hv >= .88 * m)
    lag = np.where(use, half, lag); m = np.where(use, hv, m)
    li = np.clip(lag, LAG_LO + 1, LAG_HI - 2)
    y0, y1, y2 = nac[ar, li - 1], nac[ar, li], nac[ar, li + 1]
    den = y0 - 2 * y1 + y2
    off = np.where(den < -1e-9, .5 * (y0 - y2) / np.where(den < -1e-9, den, -1.0), 0.0)
    f0 = SR / (li + np.clip(off, -1, 1))
    rms = np.sqrt(e / L)
    return np.where((m > .55) & (rms > MIN_RMS), f0, 0.0).astype(np.float32)


def chunk_feats(a):
    """a = float32 audio (int16 scale, mono, 16 kHz), a whole number of seconds -> (cent, hi, lo, f0)
    cent = brightness (spectral centroid, Hz) per second, hi = share of the energy at 1.5-6 kHz, lo = share below 300 Hz, f0 = pitch per 40 ms frame."""
    s = len(a) // SR
    if s == 0: z = np.zeros(0, np.float32); return z, z, z, z
    a = np.asarray(a[:s * SR], np.float32)
    x = a.reshape(s, SR)
    sp = np.abs(np.fft.rfft(x * np.hanning(SR).astype(np.float32), axis=1)).astype(np.float32) ** 2
    fr = np.fft.rfftfreq(SR, 1.0 / SR).astype(np.float32)
    tot = sp.sum(1) + 1e-9
    cent = (sp * fr).sum(1) / tot
    hi = sp[:, (fr >= 1500) & (fr < 6000)].sum(1) / tot
    lo = sp[:, fr < 300].sum(1) / tot
    f0 = pitch_frames(a.reshape(s * FPS_F, FR))
    return cent.astype(np.float32), hi.astype(np.float32), lo.astype(np.float32), f0


# ================================================================ small helpers
def _box(v, n):
    v = np.asarray(v, np.float32)
    if n <= 1 or len(v) == 0: return v
    k = np.ones(n, np.float32) / n
    return np.convolve(v, k, "same")


def _win(v, n):
    """Sliding windows of n samples (padded with zeros at the end so the result has len(v) rows)."""
    v = np.asarray(v, np.float32)
    p = np.concatenate([v, np.zeros(n - 1, np.float32)])
    from numpy.lib.stride_tricks import sliding_window_view
    return sliding_window_view(p, n)


# ================================================================ singing
def stable_runs(f0, win=8, max_range=1.8):
    """True for every frame that sits inside a stretch of `win` voiced frames (320 ms) whose pitch stays within `max_range` semitones - a held note
    (vibrato included). Speech glides and stops all the time, so it hardly ever has one."""
    f0 = np.asarray(f0, np.float32); n = len(f0)
    if n < win: return np.zeros(n, bool)
    voiced = f0 > 0
    semi = np.zeros(n, np.float32); semi[voiced] = 12 * np.log2(f0[voiced] / 110.0)
    from numpy.lib.stride_tricks import sliding_window_view
    sw = sliding_window_view(semi, win); vw = sliding_window_view(voiced, win)
    good = vw.all(1) & ((sw.max(1) - sw.min(1)) < max_range)            # one flag per window
    cover = np.convolve(good.astype(np.int32), np.ones(win, np.int32), "full")[:n] > 0
    return cover & voiced


def pitch_spread(f0, mask, n, reach=3):
    """Per second: how far apart (in semitones) the held notes within +-`reach` seconds are. A tune steps from note to note; a hum, a drone or a monotone
    voice stays on one pitch."""
    from numpy.lib.stride_tricks import sliding_window_view
    f0 = np.asarray(f0, np.float32)
    semi = np.where(f0 > 0, 12 * np.log2(np.maximum(f0, 1.0) / 110.0), 0.0)
    lo = np.full(n, np.inf, np.float32); hi = np.full(n, -np.inf, np.float32)
    d = np.diff(np.concatenate([[0], np.asarray(mask, np.int8), [0]]))
    for a, b in zip(np.where(d == 1)[0], np.where(d == -1)[0]):
        med = float(np.median(semi[a:b])); s0, s1 = a // FPS_F, min(n - 1, (b - 1) // FPS_F)
        lo[s0:s1 + 1] = np.minimum(lo[s0:s1 + 1], med); hi[s0:s1 + 1] = np.maximum(hi[s0:s1 + 1], med)
    k = 2 * reach + 1
    wl = sliding_window_view(np.concatenate([np.full(reach, np.inf, np.float32), lo, np.full(reach, np.inf, np.float32)]), k).min(1)
    wh = sliding_window_view(np.concatenate([np.full(reach, -np.inf, np.float32), hi, np.full(reach, -np.inf, np.float32)]), k).max(1)
    return np.where(np.isfinite(wl) & np.isfinite(wh), wh - wl, 0.0).astype(np.float32)


def sing_curve(f0, n):
    """0..1 per second: how much of the last / next few seconds is a held, sung note - and the notes change (a melody). n = seconds."""
    f0 = np.asarray(f0, np.float32)
    need = n * FPS_F
    if len(f0) < need: f0 = np.concatenate([f0, np.zeros(need - len(f0), np.float32)])
    f0 = f0[:need]
    mask = stable_runs(f0)
    st = mask.reshape(n, FPS_F).mean(1)
    vo = (f0 > 0).reshape(n, FPS_F).mean(1)
    st4, vo4 = _box(st, 5), _box(vo, 5)
    tune = np.clip((pitch_spread(f0, mask, n) - .8) / 1.2, .2, 1.0)
    return (np.clip((st4 - .12) / .30, 0, 1) * (vo4 > .35) * tune).astype(np.float32), vo.astype(np.float32)


# ================================================================ laughter
def laugh_curve(r50, n):
    """0..1 per second from the 50 ms loudness: laughter is a regular row of loud bursts (about 4-6 a second) that drops almost to silence between them.
    Speech has a rhythm too, but a shallower, less regular one."""
    e = np.asarray(r50, np.float32)
    if len(e) == 0: return np.zeros(n, np.float32)
    W = 40                                                     # 2 s at 20 values a second
    wins = _win(e, W)[:len(e) - W + 1] if len(e) >= W else _win(e, W)[:1]
    srt = np.sort(wins, axis=1)
    p10, p90 = srt[:, 4], srt[:, 35]
    depth = (p90 - p10) / (p90 + 1e-6)
    d = wins - wins.mean(1, keepdims=True)
    var = (d * d).sum(1) + 1e-6
    best = np.zeros(len(wins), np.float32); second = np.zeros(len(wins), np.float32)
    for lag in (3, 4, 5, 6):                                    # 150 .. 300 ms between bursts
        ac = (d[:, :-lag] * d[:, lag:]).sum(1) / var
        ac2 = (d[:, :-2 * lag] * d[:, 2 * lag:]).sum(1) / var
        m = ac > best
        best = np.where(m, ac, best); second = np.where(m, ac2, second)
    loud = np.clip((p90 - np.median(e)) / (np.median(e) * 1.5 + 1e-6), 0, 1)
    sc = np.clip((depth - .55) / .35, 0, 1) * np.clip((best - .30) / .35, 0, 1) * np.clip((second - .05) / .30, 0, 1) * loud
    out = np.zeros(n, np.float32)
    # a window starting at second i covers i .. i+2: give its score to both seconds it mostly covers
    for i in range(min(n, len(sc) // 20 + 1)):
        a, b = i * 20, min(len(sc), i * 20 + 20)
        if b > a: out[i] = float(sc[a:b].max())
    return _box(out, 3).clip(0, 1)


# ================================================================ screams
def scream_curve(rmsz, f0, cent, n, hi=None):
    """0..1 per second: very loud AND high-pitched (above ~520 Hz) AND bright. A loud explosion in the game is loud but low and dull.
    The pitch tracker is unreliable above ~1000 Hz, so a very bright sound (lots of energy at 1.5-6 kHz) counts at 60% when no high pitch was found."""
    rz = np.zeros(n, np.float32); rz[:min(n, len(rmsz))] = np.asarray(rmsz, np.float32)[:n]
    need = n * FPS_F
    f = np.asarray(f0, np.float32)
    if len(f) < need: f = np.concatenate([f, np.zeros(need - len(f), np.float32)])
    f = f[:need]
    high = ((f > 520) & (f < 1700)).reshape(n, FPS_F).mean(1)
    br = np.zeros(n, np.float32); br[:min(n, len(cent))] = np.clip((np.asarray(cent, np.float32)[:n] - 900) / 1600, 0, 1)
    loud = np.clip((rz - .8) / 2.2, 0, 1)
    tonal = np.clip(high * 2.2, 0, 1)
    if hi is not None:
        hs = np.zeros(n, np.float32); hs[:min(n, len(hi))] = np.clip((np.asarray(hi, np.float32)[:n] - .30) / .22, 0, 1)
        tonal = np.maximum(tonal, .6 * hs)
    return _box(loud * tonal * (.4 + .6 * br), 3).clip(0, 1)


# ================================================================ quiet beat, then boom
def setup_curve(r50, onsets, n):
    """0..1 per second: a quiet stretch of at least 0.8 s right before a sudden loud moment (the pause before a punchline or a jump scare).
    `onsets` = [(time in s, strength)] from the loudness analysis."""
    e = np.asarray(r50, np.float32); out = np.zeros(n, np.float32)
    if len(e) < 40 or not onsets: return out
    ref = float(np.percentile(e, 60)) + 1e-6
    for t, st in onsets:
        i = int(t * 20)
        if i < 20 or i + 8 >= len(e) or st < 3.0: continue
        after = float(e[i:i + 8].max())
        before = e[max(0, i - 18):i - 2]                       # 0.9 s that ends 0.1 s before the hit
        if len(before) < 14: continue
        qb = float(np.median(before))
        recent = float(np.percentile(e[max(0, i - 220):i - 18], 90)) if i > 60 else 0.0       # the hit must also be louder than the talking before the pause
        if qb < .45 * ref and after > 2.2 * max(qb, .12 * ref) and after > 1.35 * recent:
            k = min(n - 1, int(t))
            out[k] = max(out[k], float(np.clip(np.log2(after / max(qb, .1 * ref)) / 3.0, .3, 1.0)))
    return _box(out, 3).clip(0, 1) * 1.4 if out.any() else out


# ================================================================ everything at once
def curves(r50, rmsz, onsets, f0, cent, n, hi=None):
    """All detector curves for a video of n seconds (every one 0..1, one value per second)."""
    sing, voiced = sing_curve(f0, n)
    return dict(laugh=laugh_curve(r50, n), scream=scream_curve(rmsz, f0, cent, n, hi), sing=sing, voiced=voiced, setup=np.clip(setup_curve(r50, onsets, n), 0, 1))
