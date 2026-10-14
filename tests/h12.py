import sys, os, json, time, subprocess, tempfile, shutil
os.environ["VTC_TEST"] = "1"
import paths; S = paths.ROOT
H = tempfile.mkdtemp(); os.environ["HOME"] = H
sys.path.insert(0, paths.APP)
import streamclip as engine, streamclip_app as app, vcpresets, vcpreview, vcpost
import vcemotes as _ve; _ve.STARTER_DIR = ""                    # the app ships no chibi pictures; users add their own
app.sc = engine; app.vp = vcpresets; app.vv = vcpreview; app.vpost = vcpost; app.SENS_NAMES.update({k: x["label"] for k, x in engine.GAME_SENS.items()})
from tkinter import messagebox, filedialog, simpledialog, colorchooser
MSG = []
messagebox.showerror = lambda *a, **k: MSG.append(("err", a)); messagebox.showinfo = lambda *a, **k: MSG.append(("info", a))
messagebox.askyesno = lambda *a, **k: (MSG.append(("ask", a)), True)[1]
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m, file=sys.__stdout__, flush=True)
def mk(cfgtxt=None):
    cf = os.path.join(H, ".vtuberclipper.json")
    if cfgtxt is None:
        if os.path.exists(cf): os.remove(cf)
    else: open(cf, "w").write(cfgtxt)
    app.CFG = cf; app.HOME = H; app.GIF_DIR = os.path.join(H, "prev"); vcpresets.USER_FILE = os.path.join(H, "presets.json")
    return app.App()
def pump(A, sec):
    t = time.time()
    while time.time() - t < sec: A.update(); time.sleep(.03)
def shot(A, name):
    pump(A, .5)
    try: os.makedirs(paths.SHOTS, exist_ok=True); subprocess.run(["import", "-window", "root", os.path.join(paths.SHOTS, name + ".png")], check=True)      # needs ImageMagick; skipped when it is missing
    except Exception: pass
def waitjob(A, maxs=400):
    t = time.time()
    while (A.busy or time.time() - t < 1.2) and time.time() - t < maxs: pump(A, .3)
    pump(A, .6)
