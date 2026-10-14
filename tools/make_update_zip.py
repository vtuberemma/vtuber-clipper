"""Builds the "update" zip people drag into an existing VTuberClipper folder (the app folder + README + HOW_TO_UPDATE).

    python tools/make_update_zip.py            # writes dist/VTuberClipper_update_<version>[_beta].zip

The version comes from app/streamclip_app.py (VERSION, BETA). The instructions come from docs/HOW_TO_UPDATE_<version>.txt and
the user guide (docs/USER_GUIDE.txt) is shipped as README.txt. Only code and pictures / sounds go in; fonts, presets and the
demo video are left out because an update does not change them.
"""
import os, re, sys, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app")
KEEP_DIRS = ("emoji", "mascot", "sfx")


def read_version():
    src = open(os.path.join(APP, "streamclip_app.py"), encoding="utf-8").read()
    ver = re.search(r'^VERSION = "([^"]+)"', src, re.M).group(1)
    beta = re.search(r"^BETA = (True|False)", src, re.M)
    return ver, bool(beta and beta.group(1) == "True")


def main():
    ver, beta = read_version()
    how = os.path.join(ROOT, "docs", f"HOW_TO_UPDATE_{ver}.txt")
    guide = os.path.join(ROOT, "docs", "USER_GUIDE.txt")
    for p in (how, guide):
        if not os.path.isfile(p): sys.exit(f"missing {p}")
    os.makedirs(os.path.join(ROOT, "dist"), exist_ok=True)
    out = os.path.join(ROOT, "dist", f"VTuberClipper_update_{ver}{'_beta' if beta else ''}.zip")
    z = zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9, strict_timestamps=False)
    z.write(how, "HOW_TO_UPDATE.txt"); z.write(guide, "README.txt")
    for name in sorted(os.listdir(APP)):
        p = os.path.join(APP, name)
        if os.path.isfile(p) and name.endswith((".py", ".txt", ".wav", ".png")): z.write(p, "app/" + name)
    for d in KEEP_DIRS:
        for r, _, files in os.walk(os.path.join(APP, d)):
            for f in sorted(files): z.write(os.path.join(r, f), "app/" + os.path.relpath(os.path.join(r, f), APP).replace(os.sep, "/"))
    z.close(); print("wrote", out, f"({os.path.getsize(out) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
