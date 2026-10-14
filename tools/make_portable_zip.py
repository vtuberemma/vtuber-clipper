"""Builds the full Windows download (the portable folder people unzip and run) from this repo plus the Windows runtime.

    python tools/make_portable_zip.py --runtime C:\\path\\to\\an\\existing\\VTuberClipper
    python tools/make_portable_zip.py --runtime /path/to/VTuberClipper --out dist

--runtime is a folder that already has  python\\  (Python 3.11 + Tk + the packages), bin\\  (ffmpeg, yt-dlp, deno) and VTuberClipper.exe.
Those are not stored in git (see docs/PORTABLE_BUILD.md); you take them from the previous release. Everything the app itself is made of
(app\\, README.txt) always comes from THIS checkout, so the zip is exactly what is in git.

The zip is named VTuberClipper_<version>[_beta].zip from VERSION / BETA in app/streamclip_app.py, and unzips to a folder called VTuberClipper.
"""
import argparse, os, re, sys, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app")
TOP = "VTuberClipper"


def read_version():
    src = open(os.path.join(APP, "streamclip_app.py"), encoding="utf-8").read()
    ver = re.search(r'^VERSION = "([^"]+)"', src, re.M).group(1)
    beta = re.search(r"^BETA = (True|False)", src, re.M)
    return ver, bool(beta and beta.group(1) == "True")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runtime", required=True, help="a VTuberClipper folder that has python\\, bin\\ and VTuberClipper.exe")
    ap.add_argument("--out", default=os.path.join(ROOT, "dist"), help="where to write the zip (default: dist/)")
    a = ap.parse_args()
    rt = os.path.abspath(a.runtime)
    for need in ("python", "bin", "VTuberClipper.exe"):
        if not os.path.exists(os.path.join(rt, need)): sys.exit(f"{rt} has no {need} - point --runtime at an existing VTuberClipper folder")
    guide = os.path.join(ROOT, "docs", "USER_GUIDE.txt")
    if not os.path.isfile(guide): sys.exit("missing docs/USER_GUIDE.txt")
    ver, beta = read_version()
    if f"v{ver}" not in open(guide, encoding="utf-8").readline(): print(f"warning: the first line of docs/USER_GUIDE.txt does not say v{ver}")
    os.makedirs(a.out, exist_ok=True)
    out = os.path.join(a.out, f"VTuberClipper_{ver}{'_beta' if beta else ''}.zip")
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6, strict_timestamps=False) as z:
        z.write(os.path.join(rt, "VTuberClipper.exe"), f"{TOP}/VTuberClipper.exe"); z.write(guide, f"{TOP}/README.txt"); n += 2
        for r, dirs, files in os.walk(APP):                                  # the program: always from this checkout
            dirs[:] = sorted(d for d in dirs if d != "__pycache__")
            for f in sorted(files):
                if f.endswith(".pyc"): continue
                p = os.path.join(r, f); z.write(p, f"{TOP}/app/" + os.path.relpath(p, APP).replace(os.sep, "/")); n += 1
        for sub in ("bin", "python"):                                        # the runtime: from the folder you pointed at
            for r, dirs, files in os.walk(os.path.join(rt, sub)):
                dirs.sort()
                for f in sorted(files):
                    p = os.path.join(r, f); z.write(p, f"{TOP}/" + os.path.relpath(p, rt).replace(os.sep, "/")); n += 1
    print(f"wrote {out}  ({n} files, {os.path.getsize(out) / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
