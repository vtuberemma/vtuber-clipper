"""2.3 packaging: build the REAL update zip with tools/make_update_zip.py and prove the in-app updater can install it: every file passes the inspection, nothing the creator owns
(fonts, presets) is in it, it is small enough for the updater, it installs into a copy of an older app folder, the installed program imports, and undo puts the old files back."""
from t3lib import *
import hashlib, importlib, json, py_compile, runpy, shutil, subprocess, sys, time, zipfile
import vcnet

_n, _ok = [0], ok
def ok(c, m):
    if not c: _n[0] += 1
    _ok(bool(c), m)

ROOT = paths.ROOT
APP = paths.APP
out = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_update_zip.py")], capture_output=True, text=True, timeout=600)
ok(out.returncode == 0 and "wrote" in out.stdout, f"make_update_zip.py runs ({out.stdout.strip()[-100:]}{out.stderr.strip()[-200:]})")
ZIP = out.stdout.split("wrote", 1)[1].strip().split(" (")[0].strip() if "wrote" in out.stdout else ""
ok(os.path.isfile(ZIP) and os.path.basename(ZIP).startswith("VTuberClipper_update_") and "update" in os.path.basename(ZIP).lower(), f"the file name has 'update' in it, so the update checker picks it ({os.path.basename(ZIP)})")
src = open(os.path.join(APP, "streamclip_app.py"), encoding="utf-8").read()
ver = re.search(r'^VERSION = "([^"]+)"', src, re.M).group(1)
ok(ver == "2.3" and os.path.basename(ZIP) == "VTuberClipper_update_2.3_beta.zip", f"named for the version ({ver})")

info = vcnet.inspect_update(ZIP)
ok(info["ok"] and info["version"] == ver and info["beta"] is True, f"the updater accepts the real zip: version {info['version']}, problems {info['problems'][:2]}")
names = [n for n, _ in info["files"]]
ok(os.path.getsize(ZIP) < vcnet.MAX_UPDATE_MB * 1e6, f"small enough for the updater ({os.path.getsize(ZIP) / 1e6:.1f} MB < {vcnet.MAX_UPDATE_MB} MB)")
ok(not [n for n in names if n.startswith(("app/fonts/", "app/presets/"))], "no fonts or presets in the update")
ok("README.txt" in names and "HOW_TO_UPDATE.txt" in names and "app/streamclip_app.py" in names and "app/vc23ui.py" in names and "app/vcnet.py" in names, "README, instructions and the new modules are in it")
with zipfile.ZipFile(ZIP) as z:
    allnames = [i.filename for i in z.infolist() if not i.is_dir()]
    how = z.read("HOW_TO_UPDATE.txt").decode("utf-8")
ok(len(allnames) == len(names), f"every file in the zip is one the updater would install ({len(allnames)} files)")
ok("2.3" in how and "Tools -> Updates" in how, "the instructions are the 2.3 ones")
py_in_app = sorted(f for f in os.listdir(APP) if f.endswith(".py"))
ok(all("app/" + f in names for f in py_in_app), f"every program file of the app is in the zip ({len(py_in_app)} modules)")

# ---- install into a copy of an "older" app folder
root = tempfile.mkdtemp(prefix="inst_"); os.makedirs(root + "/app/fonts"); os.makedirs(root + "/app/presets")
for f in py_in_app: shutil.copy(os.path.join(APP, f), root + "/app/" + f)
for f in os.listdir(os.path.join(APP, "fonts"))[:2]: shutil.copy(os.path.join(APP, "fonts", f), root + "/app/fonts/" + f)
for f in os.listdir(os.path.join(APP, "presets"))[:2]: shutil.copy(os.path.join(APP, "presets", f), root + "/app/presets/" + f)
for f in ("vc23ui.py", "vc23.py", "vcclues.py", "vcmedia.py", "vcnet.py", "vcpipe.py", "vcsafe.py", "vcshare.py"): os.remove(root + "/app/" + f)         # a 2.2 install has none of these
old = open(root + "/app/streamclip_app.py", encoding="utf-8").read().replace('VERSION = "2.3"', 'VERSION = "2.2"'); open(root + "/app/streamclip_app.py", "w", encoding="utf-8").write(old)
open(root + "/app/vcsmart.py", "a").write("\n# changed by hand\n")
def tree(r):
    d = {}
    for dp, _, fs in os.walk(r):
        if "update_backups" in dp or "__pycache__" in dp: continue
        for f in fs: d[os.path.relpath(os.path.join(dp, f), r).replace(os.sep, "/")] = hashlib.md5(open(os.path.join(dp, f), "rb").read()).hexdigest()
    return d
before = tree(root)
res = vcnet.apply_update(ZIP, root)
ok(res["ok"] and res["version"] == ver and res["added"] >= 8 and res["replaced"] >= 5, f"installed: {res['message'][:80]} (replaced {res['replaced']}, added {res['added']})")
after = tree(root)
for n in names:
    if n in ("README.txt", "HOW_TO_UPDATE.txt"): ok(n in after, f"{n} installed at the top"); continue
    with zipfile.ZipFile(ZIP) as z: want = hashlib.md5(z.read(n)).hexdigest()
    if after.get(n) != want: ok(False, f"{n} differs from the zip")
ok(all(after.get(n) == hashlib.md5(open(os.path.join(ROOT, n), "rb").read()).hexdigest() for n in names if n.startswith("app/") and n.endswith(".py")), "every installed program file is the same as the one in the repository")
ok({k: v for k, v in after.items() if k.startswith(("app/fonts/", "app/presets/"))} == {k: v for k, v in before.items() if k.startswith(("app/fonts/", "app/presets/"))}, "fonts and presets are untouched")
ok(not [f for f in after if f.endswith((".new", ".tmp"))], "no leftover temporary files")
# the installed program starts (modules import, the app module loads, the 2.3 screens are found)
code = ("import sys, os; os.environ['VTC_TEST']='1'; sys.path.insert(0, %r); import streamclip_app as a; "
        "print('VER', a.VERSION, a.BETA, 'ERRS', a.VC20_ERR, a.VC21_ERR, a.VC22_ERR, a.VC23_ERR)") % (root + "/app")
r = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=120, cwd=root, env={**os.environ, "PYTHONPATH": ""})
ok("VER 2.3 True ERRS None None None None" in r.stdout, f"the installed program imports and finds all its screens ({r.stdout.strip()[-120:]}{r.stderr.strip()[-200:]})")
r = subprocess.run([sys.executable, "-m", "compileall", "-q", root + "/app"], capture_output=True, text=True, timeout=120)
ok(r.returncode == 0, "every installed .py compiles")
# undo
u = vcnet.undo_update(root)
ok(u["ok"] and tree(root) == before, f"undo puts the old app folder back exactly ({u['message'][:50]})")
# installing twice in a row works (the second time there is nothing new)
res2 = vcnet.apply_update(ZIP, root); res3 = vcnet.apply_update(ZIP, root)
ok(res2["ok"] and res3["ok"] and res3["added"] == 0, "installing the same update again is harmless")
ok(vcnet.undo_update(root)["ok"] and vcnet.undo_update(root)["ok"], "and each install can be undone")
# an update with a wrong version line, a missing app, a bad name is refused (real zip, tampered)
bad = os.path.join(tempfile.mkdtemp(), "tampered.zip")
with zipfile.ZipFile(ZIP) as zi, zipfile.ZipFile(bad, "w") as zo:
    for it in zi.infolist():
        data = zi.read(it.filename)
        if it.filename == "app/vcnet.py": data = data + b"\ndef (:\n"
        zo.writestr(it.filename, data)
    zo.writestr("app/fonts/evil.ttf", b"x")
ri = vcnet.inspect_update(bad); ok(not ri["ok"] and any("vcnet.py" in p for p in ri["problems"]) and any("fonts" in p for p in ri["problems"]), f"a real zip with one broken module and a font slipped in is refused ({ri['problems'][:2]})")
shutil.rmtree(root, ignore_errors=True)
print("FAILS:", _n[0])
