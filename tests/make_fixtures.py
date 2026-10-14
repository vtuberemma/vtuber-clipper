"""Makes the test media into tests/_fixtures/ (git-ignored). Needs ffmpeg on your PATH, numpy; no downloads, no real videos.

    python tests/make_fixtures.py            # everything
    python tests/make_fixtures.py stream     # only the 4-minute synthetic stream (used by most tests)
    python tests/make_fixtures.py odd        # only the awkward little videos (no sound, 10-bit, portrait, variable frame rate, ...)
"""
import os, sys, json, subprocess, runpy
import paths

ODD = os.path.join(paths.FIX, "odd")


def words_for(dur):
    """Fake speech: a word every third of a second, an "OMG" now and then. The tests hand these to the app as an already-made transcript."""
    ws, t, i = [], 1.0, 0
    while t + .25 < dur - .5:
        ws.append(dict(w="OMG" if i and i % 10 == 0 else f"word{i}", start=round(t, 2), end=round(t + .25, 2))); t += .33; i += 1
    return ws


def ff(*args):
    r = subprocess.run([paths.FFMPEG, "-y", "-v", "error", *args], capture_output=True, text=True)
    if r.returncode: sys.exit("ffmpeg failed: " + r.stderr[-400:])


SOUND = "aevalsrc='0.3*sin(2*PI*(200+100*sin(2*PI*0.2*t))*t)':s=44100:d={d}"


def make_odd():
    os.makedirs(ODD, exist_ok=True)
    # name: (seconds, video size/rate, extra video args, audio kind, container)
    spec = {
        "odd":      (40, "640x360", 25, [], "stereo", "mp4"),
        "fps24":    (40, "640x360", 24, [], "stereo", "mp4"),
        "fps60":    (40, "640x360", 60, [], "stereo", "mp4"),
        "mono22":   (40, "640x360", 25, [], "mono", "mp4"),
        "noaudio":  (40, "640x360", 25, [], None, "mp4"),
        "silent":   (40, "640x360", 25, [], "silence", "mp4"),
        "portrait": (40, "360x640", 25, [], "stereo", "mp4"),
        "p43":      (40, "640x480", 25, [], "stereo", "mp4"),
        "tenbit":   (40, "640x360", 25, ["-pix_fmt", "yuv420p10le"], "stereo", "mp4"),
        "vfr":      (40, "640x360", 30, ["-vf", "select='gt(random(1),0.3)'", "-fps_mode", "vfr"], "stereo", "mp4"),
        "surround": (40, "640x360", 25, [], "surround", "mp4"),
        "mkvopus":  (40, "640x360", 25, [], "stereo-opus", "mkv"),
        "short12":  (12, "640x360", 25, [], "stereo", "mp4"),
        "short6":   (6, "640x360", 25, [], "stereo", "mp4"),
    }
    for name, (d, size, fps, vargs, audio, ext) in spec.items():
        out = os.path.join(ODD, f"{name}.{ext}")
        if os.path.exists(out) and os.path.exists(out + ".words.json"): continue
        a = ["-f", "lavfi", "-i", SOUND.format(d=d)]
        if audio is None: a = []
        elif audio == "silence": a = ["-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={d}"]
        acodec = {"stereo": ["-ac", "2", "-c:a", "aac"], "mono": ["-ac", "1", "-c:a", "aac"], "silence": ["-c:a", "aac"], "surround": ["-ac", "6", "-c:a", "aac"],
                  "stereo-opus": ["-ac", "2", "-c:a", "libopus"], None: []}[audio]
        vcodec = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "30"]
        if "-pix_fmt" not in vargs: vcodec += ["-pix_fmt", "yuv420p"]
        ff("-f", "lavfi", "-i", f"testsrc2=s={size}:r={fps}:d={d}", *a, *vcodec, *vargs, *acodec, "-shortest", out)
        json.dump({"v": 2, "words": words_for(d)}, open(out + ".words.json", "w"))
        print("made", out)


def make_stream():
    os.makedirs(paths.FIX, exist_ok=True)
    if all(os.path.exists(os.path.join(paths.FIX, f"stream22.{e}")) for e in ("mp4", "json")): return
    runpy.run_path(os.path.join(paths.HERE, "mkstream.py"), run_name="__main__")


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("all", "stream"): make_stream()
    if what in ("all", "odd"): make_odd()
    print("fixtures ready in", paths.FIX)
