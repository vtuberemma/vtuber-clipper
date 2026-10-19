# VTuber Clipper ♡

A Windows desktop app that turns long Kick, Twitch and YouTube streams (VODs) into vertical shorts, recaps, best-moments lists, post kits and X videos. It is made for VTubers: it finds the funny, loud and cute parts, adds captions and effects, and writes the titles and hashtags. Everything runs on your own PC.

**Status: 2.3 beta.** It works and is tested a lot, but only on a Linux test machine so far, not on every Windows PC. The window title, banner and Settings footer say "beta".

## What it does

- **Shorts** (9:16, 4:5, 1:1, 16:9): finds the best moments, cuts out the silences, adds animated captions, a title hook, sound effects, a cover picture and a post kit (titles, description, hashtags per app).
- **Smart finding** (2.2, with more clues in 2.3: `!clip` in a chat log, milestones, reading chat, bilingual switches, rapid talking, panic repeats, build-ups): tells gameplay, reactions, talking, stories and singing apart. It *hears* laughs, screams and singing in the sound, skips "hey guys, welcome back" openings, mixes kinds, picks a length per kind, and learns from the clips you keep.
- **Recap** videos with chapters, parts, or one video per game. **Best moments** lists you can save and reopen. **Post helper** and **X (Twitter)** tabs.
- **Privacy & checks** (new in 2.3): a privacy guard for e-mails, phone numbers, addresses, links and "my real name is…" slips, **My private words** that are always bleeped, a clip check, a flash safety check and a disk-space guard. It is a pattern check on the speech-to-text, not a guarantee.
- **My clips**: search, tags, review mode, trim, montage, a post planner with reminders, a ready-to-post folder.
- **Tools**: watch a folder for new recordings, health check, clean-up, free space, share a look as text, compare looks, hashtag bank, your own slang words; since 2.3 also clip check, duplicates, rename with preview, reports (highlights page, timestamps, community message), chapters, privacy scan, snapshots of your settings, remembered settings per game and updates.
- **Downloads and updates** (2.3): download only a part of a VOD, a speed limit, a cookies file; an update checker and an installer that keeps a backup and can undo.
- Everything new in a version is **off** until you switch it on, except Smart finding and its clues (untick it to get the old way back) and the checks that only protect you (flash check, clip check, disk-space guard, the privacy guard in "warn" mode).

The full list of features and the history of every version is in [docs/USER_GUIDE.txt](docs/USER_GUIDE.txt) (the README that ships with the app) and [CHANGELOG.md](CHANGELOG.md).

### What it deliberately does not do

It does not post for you, show followers or analytics, track your face, or make pictures from scratch. TikTok / YouTube / Instagram / X only allow posting and analytics with your own login and developer keys, which a portable program can't safely carry. The planner reminds you; you press upload.

### About "trained"

Smart finding is **not a neural network and was not trained on real VTuber clips.** It is a set of rules: word lists, sound detectors and clip lengths, tuned on sounds the test tools synthesise and on published advice about short videos (sources in [app/CREDITS.txt](app/CREDITS.txt); their claims are unverified). The one thing that *learns* is "Learn from the clips I keep", which uses your own stars and keep / delete choices. Please check what it picks and report what it gets wrong.

## Get it running

**Windows, no installation (the way most people use it):** download the portable build (`VTuberClipper_<version>.zip`, e.g. `VTuberClipper_2.3_beta.zip`) from the Releases page, unzip the whole folder anywhere, double-click `VTuberClipper.exe`. SmartScreen: *More info → Run anyway*. To update, unzip `VTuberClipper_update_<version>.zip` and drag its `app` folder over your own (see [docs/HOW_TO_UPDATE_2.3.txt](docs/HOW_TO_UPDATE_2.3.txt)). The portable build bundles Python, ffmpeg and yt-dlp (about 600 MB) so it is not stored in git; how it is put together is in [docs/PORTABLE_BUILD.md](docs/PORTABLE_BUILD.md).

**From source:**

```
python -m venv .venv && .venv\Scripts\activate        # Windows (use source .venv/bin/activate on Linux)
pip install -r requirements-runtime.txt
# put ffmpeg(.exe) and yt-dlp(.exe) in a folder called bin\ next to app\, or have them on your PATH
python app/streamclip_app.py                          # or double-click run_windows.bat
```

Python 3.11 with Tk is what the Windows build uses. Speech-to-text (faster-whisper) downloads its model the first time you use it.

## Layout

| Folder | What is in it |
| --- | --- |
| `app/` | The program: the engine (`streamclip.py`), the window (`streamclip_app.py` + `vc20ui.py`, `vc21ui.py`, `vc22ui.py`, `vc23ui.py`), the finder (`vcsense.py` sound detectors, `vcsmart.py` rules / lexicons / picking, `vcclues.py` the 2.3 clues), the 2.3 options (`vc23.py`), checks and privacy (`vcsafe.py`), picture / sound / file extras (`vcmedia.py`), reports, renaming and snapshots (`vcshare.py`), downloads and updates (`vcnet.py`), the finishing steps of a clip and of a run (`vcpipe.py`), helpers (`vcmore.py`, `vctools.py`, `vcnew.py`, `vcfx.py`, `vcpost.py`, `vcouts.py`, `vcpresets.py`, `vcpreview.py`, `vcemoji.py`, `vcemotes.py`) and its pictures, sounds, fonts and presets. |
| `tests/` | Engine, helper, end-to-end and window tests. They make their own test videos; nothing is downloaded. |
| `tools/` | `make_update_zip.py` builds the update zip, `make_portable_zip.py` the full download. |
| `docs/` | The user guide, update instructions, the 2.2 and 2.3 plans, how the portable build is assembled. |

## Tests

```
pip install -r requirements-dev.txt        # numpy + pillow + yt-dlp; ffmpeg must be on your PATH
python tests/make_fixtures.py              # makes a 4-minute synthetic stream and 14 awkward little videos (no sound, 10-bit, portrait, ...)
python tests/run_tests.py quick            # engine + helpers, ~10 min
python tests/run_tests.py odd              # every feature on the awkward videos
xvfb-run -a python tests/run_tests.py gui  # the windows (Linux; on Windows run without xvfb-run)
```

GitHub Actions runs the same on every push (`.github/workflows/tests.yml`). See [CONTRIBUTING.md](CONTRIBUTING.md) before changing code.

## Credits and licences

Sounds are CC0, fonts are under their own open licences (see `app/font_licenses/`), emoji pictures are Twemoji (CC-BY 4.0, `app/emoji/LICENSE-twemoji.txt`). Details in [app/CREDITS.txt](app/CREDITS.txt). **There is no licence for the code yet**, which means all rights are reserved. Add a `LICENSE` file to choose one (for example MIT) if you want others to be able to use it.
