"""Animated style previews. Renders a few seconds with the real engine (same captions, effects and sounds as a finished clip),
at low resolution, and turns it into a GIF. Uses the built-in cartoon scene when no VOD is given, or a few seconds of your VOD."""
import os, shutil, tempfile
import streamclip as sc

DEMO_CAM = "480:270:40:40"
DEMO_EVENTS = (2.4, 5.4)
DEMO_HOOK = "okay so chat watch this"
_W = [("okay", .3, .5), ("so", .65, .85), ("chat", .95, 1.2), ("watch", 1.3, 1.55), ("this...", 1.65, 2.1), ("WTF!", 2.35, 2.9), ("no", 3.0, 3.25), ("way", 3.35, 3.7),
      ("i", 4.0, 4.15), ("cant", 4.2, 4.35), ("believe", 4.4, 4.6), ("it", 4.65, 4.8), ("again", 4.85, 5.05), ("OMG", 5.4, 5.85), ("that", 6.0, 6.2), ("was", 6.25, 6.45),
      ("so", 6.5, 6.7), ("cute!", 6.75, 7.2)]
DEMO_WORDS = [dict(w=w, start=a, end=b) for w, a, b in _W]
_S = [("honestly", .3, .7), ("i", .8, .95), ("was", 1.0, 1.15), ("so", 1.2, 1.35), ("scared!", 1.4, 1.95), ("hahaha", 2.4, 3.0), ("im", 3.4, 3.55), ("dead.", 3.6, 4.0),
      ("i", 4.4, 4.5), ("almost", 4.55, 4.85), ("cried.", 4.9, 5.4), ("we", 5.9, 6.0), ("won,", 6.05, 6.35), ("lets", 6.45, 6.7), ("go!", 6.75, 7.2)]
DEMO_STORY = [dict(w=w, start=a, end=b) for w, a, b in _S]          # what the preview says when the chibi emotes are on: a few feelings in a row


def demo_path():
    p = os.path.join(sc.APP_DIR, "demo_scene.mp4")
    return p if os.path.isfile(p) else None


def make_preview(out_gif, look, video=None, cam=None, words=None, t0=0.0, secs=7.5, width=126, fps=10, opts=None, cb=None):
    """look = a preset's look (see vcpresets.full_look). video=None -> the cartoon scene. opts = extra options (e.g. logo / handle) to show too.
    Returns out_gif. Sizes: width 126 for cards, 252 for the big preview."""
    src = video or demo_path()
    if src is None: raise RuntimeError("The preview scene is missing (demo_scene.mp4) - reinstall the app.")
    demo = video is None
    if demo: cam, t0 = DEMO_CAM, 0.0
    if words is None:
        words = [dict(w=w["w"], start=w["start"] + t0, end=w["end"] + t0) for w in (DEMO_STORY if (demo and (opts or {}).get("emotes")) else DEMO_WORDS)]
    events = [t0 + e for e in DEMO_EVENTS if e < secs]
    fx = dict(look["fx"]); fx.update(intensity={"Subtle": .5, "Normal": 1.0, "Hype": 1.6}.get(look.get("intensity"), 1.0),
                                     accent=(look.get("accent") or "ff4d8d").lstrip("#"))
    o = {**look.get("opts", {}), **(opts or {})}
    o["aspect"] = look.get("aspect", "9:16"); o["intro"] = o["outro"] = ""          # previews are a few seconds: no intro / outro
    layout = look.get("layout", "stack")
    if sc.needs_cam(layout, o) and not cam: layout = "blur"
    if o.get("emotes") and demo:                                                   # the demo shows three pictures, one after the other
        try:
            import vcemotes
            r = vcemotes.plan(words, secs, (), level="lots", limit=3, seed=2)
            if r["items"]: o["emote_plan"] = [{**it, "at": it["t"]} for it in r["items"]]
        except Exception: pass
    save_out, save_gpu = dict(sc.OUT), sc.USE_GPU_ENC
    tmp = tempfile.mkdtemp(prefix="vclip_prev_")
    try:
        sc.USE_GPU_ENC = False
        sc.OUT.update(mbps=6, res=width * 2, fps=20)
        mp4 = os.path.join(tmp, "p.mp4")
        sc.render(src, [(t0, t0 + secs)], words, mp4, layout, cam, True, frozenset(), fx, events, DEMO_HOOK if demo else sc.first_words(words, t0), None, norm=False, opts=o)
        os.makedirs(os.path.dirname(os.path.abspath(out_gif)), exist_ok=True)
        part = os.path.join(tmp, "p.gif")
        sc.run_ff(["-i", mp4, "-vf", f"fps={fps},scale={width}:-2:flags=lanczos,split[a][b];[a]palettegen=max_colors=96:stats_mode=full[p];[b][p]paletteuse=dither=bayer:bayer_scale=5",
                   "-gifflags", "-offsetting-transdiff", "-loop", "0", part], secs, cb)
        shutil.move(part, out_gif)
    finally:
        sc.OUT.clear(); sc.OUT.update(save_out); sc.USE_GPU_ENC = save_gpu
        shutil.rmtree(tmp, ignore_errors=True)
    return out_gif


def best_window(words, dur, secs=7.5):
    """Where to take the preview from a VOD: the stretch with the most reactions (hype words, !, ?), or about a third of the way in."""
    last = max(0.0, dur - secs - .5)
    if not words: return min(last, dur * .35)
    best, bt = -1.0, min(last, dur * .35)
    for w in words[::3]:
        t = max(0.0, w["start"] - 1.5)
        if t > last: continue
        sub = [x for x in words if t <= x["start"] < t + secs]
        sc_ = sum(3 * (sc.clean(x["w"]) in sc.HYPE) + sc.ends_in(x["w"], "!?！？") for x in sub) + min(len(sub), 2 * secs) * .3
        if sc_ > best: best, bt = sc_, t
    return bt
