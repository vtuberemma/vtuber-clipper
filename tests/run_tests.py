"""Runs the test scripts and says plainly what passed.

    python tests/run_tests.py quick     # engine + helper tests (about 10 minutes)
    python tests/run_tests.py odd       # every new feature on awkward videos (about 8 minutes)
    python tests/run_tests.py gui       # the windows, under a virtual display on Linux (about 20 minutes; needs Tk)
    python tests/run_tests.py all

Needs ffmpeg on your PATH and  numpy pillow  installed. Test videos are made on first use (tests/make_fixtures.py).
On Linux the GUI tests need xvfb:  xvfb-run -a python tests/run_tests.py gui
"""
import os, re, subprocess, sys, tempfile, time
import paths

QUICK = ["t_fuzz1", "t_tools1", "t_smart1", "t_sense2", "t_more1", "t_eng1", "t_clues1", "t_media1", "t_safe1", "t_share1", "t_net1", "t_e2e22", "t_e2e23", "t_pack23", "t_uni22"]
GUI = ["g22a", "g22b", "g23a"]
# awkward videos: the three that must be refused politely, and what the message has to say
REFUSED = {"noaudio": "no audio track", "short6": "too short"}
EITHER = {"short12": "shorter than one clip"}          # a 12-second video may be cut into one short or refused politely; both are fine, a crash or a broken file is not
ODD = ["odd", "fps24", "fps60", "mono22", "noaudio", "silent", "portrait", "p43", "tenbit", "vfr", "surround", "mkvopus", "short12", "short6"]


def run(cmd, timeout):
    t = time.time()
    try: r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=tempfile.gettempdir(), encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired: return None, "timed out", time.time() - t
    return r.returncode, r.stdout + "\n" + r.stderr, time.time() - t


def judge(out, code):
    """(ok, summary) from a test's output: no 'FAIL' lines, no 'FAILS: n' with n > 0, no traceback, exit code 0."""
    npass = len(re.findall(r"^PASS", out, re.M)); nfail = len(re.findall(r"^FAIL ", out, re.M))
    summ = re.findall(r"^FAILS:? *(\d+)", out, re.M)
    bad = nfail or any(int(x) for x in summ) or code not in (0, None) or "Traceback" in out
    return not bad, f"{npass} passed, {nfail} failed"


def main(groups):
    results = []
    def report(name, ok, text, secs):
        results.append(ok); print(("ok    " if ok else "FAIL  ") + f"{name:<22} {text}  ({secs:.0f}s)", flush=True)
    if "quick" in groups:
        for t in QUICK:
            code, out, secs = run([sys.executable, os.path.join(paths.HERE, t + ".py")], 1800)
            ok, text = judge(out, code) if code is not None else (False, out)
            if t == "t_uni22": m = re.search(r"^RESULT .*", out, re.M); ok = ok and bool(m) and " OK " in m.group(0) and "broken=[]" in m.group(0); text = m.group(0)[7:] if m else "no result"
            if not ok: print(out[-1500:])
            report(t, ok, text, secs)
    if "odd" in groups:
        for f in ODD:
            path = next((os.path.join(paths.FIX, "odd", f + e) for e in (".mp4", ".mkv") if os.path.exists(os.path.join(paths.FIX, "odd", f + e))), None)
            if not path: report("odd/" + f, False, "test video missing - run tests/make_fixtures.py", 0); continue
            code, out, secs = run([sys.executable, os.path.join(paths.HERE, "t_odd22.py"), path, "all"], 900)
            m = re.search(r"^RESULT .*", out or "", re.M); line = m.group(0) if m else "no result"
            good = bool(m) and " OK " in line and "broken=[]" in line
            if f in REFUSED: ok = bool(m) and " ERR " in line and REFUSED[f] in line
            elif f in EITHER: ok = good or (bool(m) and " ERR " in line and EITHER[f] in line)
            else: ok = good
            if not ok: print(out[-1500:])
            report("odd/" + f, ok, ("refused politely: " + (REFUSED.get(f) or EITHER[f])) if (ok and (f in REFUSED or (f in EITHER and " ERR " in line))) else line[7:150], secs)
    if "gui" in groups:
        for t in GUI:
            code, out, secs = run([sys.executable, os.path.join(paths.HERE, t + ".py")], 3000)
            ok, text = judge(out, code) if code is not None else (False, out)
            if not ok: print(out[-1500:])
            report(t, ok, text, secs)
    print(f"\n{sum(results)} of {len(results)} groups passed")
    return 0 if results and all(results) else 1


if __name__ == "__main__":
    args = sys.argv[1:] or ["quick"]
    groups = {"quick", "odd", "gui"} if "all" in args else set(args)
    if not groups <= {"quick", "odd", "gui"}: sys.exit(__doc__)
    paths.need(os.path.join(paths.FIX, "stream22.mp4"))
    sys.exit(main(groups))
