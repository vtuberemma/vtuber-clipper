# Working on VTuber Clipper

## Ground rules that keep the Windows build working

- **Python 3.11, Tk, no Pillow at run time.** The shipped runtime has numpy and faster-whisper only. `PIL` is allowed in `tests/` and `tools/`, never in `app/`.
- **Python 3.11 f-strings:** no backslashes inside `{}` expressions (3.12 allows it, 3.11 does not). Check with `python -m compileall -q app` on 3.11 (CI does).
- **Tk variables are read on the UI thread.** Read `self.v[...]` / `self.o[...]` *before* starting a worker thread and hand the values in; reading them from a thread raises "main thread is not in main loop".
- **Options flow:** `streamclip.OPTS` (+ `vcmore.DEFAULTS`) → `get_opts()` → engine. The window keeps Tk variables in `OPT_STR` / `OPT_BOOL`, saves them in `save()` and sends them in `opts_dict()`. A new option has to be added in all of those, and to `vcpresets.LOOK_KEYS` / `LOOK_OPTS` if a look should carry it. `get_opts()` must never raise on a bad saved value (see `tests/t_fuzz1.py`).
- **The window is built from modules** (`vc20ui.py`, `vc21ui.py`, `vc22ui.py`) that install methods onto the `App` class (`@method`, and `@wraps("name")` to wrap an existing method). Anything they do must never stop a render: wrap it and log the error.
- Everything new is **off by default** unless there is a strong reason; say so in the changelog when it isn't.
- Be honest in the UI and README about what a feature is. Smart finding is rules of thumb, not a trained model.

## Tests

See the README. New behaviour needs a test in `tests/`: engine / helper tests print `PASS` / `FAIL` lines (the runner fails on any `FAIL`); window tests use the harness in `tests/h12.py`. Please run `python tests/run_tests.py quick odd` before opening a pull request, and the GUI tests if you touched a window.

## Releases

1. Bump `VERSION` (and `BETA`) in `app/streamclip_app.py`, add the `WHATS_NEW` entries, write `docs/HOW_TO_UPDATE_<version>.txt`, update `docs/USER_GUIDE.txt` and `CHANGELOG.md`.
2. `python tools/make_update_zip.py` makes `dist/VTuberClipper_update_<version>.zip`.
3. The full portable zip is assembled as described in `docs/PORTABLE_BUILD.md`. Attach both to a GitHub Release.
