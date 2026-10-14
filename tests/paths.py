"""Where things are, for every test. Nothing is hard-coded, so the tests run from any folder / any checkout.

    VTC_ROOT   (optional) the repo root; by default the folder above tests/
    FFMPEG     the ffmpeg on your PATH (the tests never use the one that ships with the Windows build)
    FIX        generated test media (run  python tests/make_fixtures.py  first); it is git-ignored
"""
import os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("VTC_ROOT") or os.path.dirname(HERE)
APP = os.path.join(ROOT, "app")
FIX = os.path.join(HERE, "_fixtures")
SHOTS = os.path.join(HERE, "_shots")
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
for _p in (APP, HERE):
    if _p not in sys.path: sys.path.insert(0, _p)


def need(path, hint="python tests/make_fixtures.py"):
    """Stop with a plain message when a generated test file is missing."""
    if not os.path.exists(path):
        sys.exit(f"missing test file {path}\nrun:  {hint}")
    return path
