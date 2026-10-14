**VTuber Clipper 0.2.2 beta.** This is the version the program itself calls **2.2 beta** (the release number here is 0.2.2-beta).

## Downloads

| File | What it is |
| --- | --- |
| `VTuberClipper_2.2_beta.zip` | The full Windows build, no installation. Unzip the **whole** folder anywhere and double-click `VTuberClipper.exe`. It includes Python, ffmpeg and yt-dlp (about 240 MB). Windows SmartScreen: *More info → Run anyway*. |
| `VTuberClipper_update_2.2_beta.zip` | For people who already have an older version: drag its `app` folder over your own and choose Replace. Your settings and clips are not touched. Steps are in the zip (`HOW_TO_UPDATE.txt`). |

## What's new

- **Smart finding** (on by default): tells gameplay, reactions, talking, stories and singing apart. It hears laughs, screams and singing in the sound, skips "hey guys, welcome back" openings, mixes kinds, picks a length per kind and learns from the clips you keep.
- **50 new things:** a Tools window (watch a folder, health check, clean-up, free space, share and compare looks, hashtag bank, your own slang words), Review mode, search and tags, a ready-to-post folder, reaction words, slow-mo, a freeze beat, a teaser of the best moment, a hopping logo, more caption controls, square and landscape copies, "try one first", resume an interrupted run, and more. Everything except Smart finding is off until you switch it on.
- **Bug fixes:** a damaged settings file could crash a render (also in older versions), "Compare 3 looks" crashed after the Tools window had been closed, open windows kept old colours after a theme change, and more. Full list: [CHANGELOG.md](https://github.com/vtuberemma/vtuber-clipper/blob/main/CHANGELOG.md).

## Please read

- **It is a beta.** It was tested a lot, but only on a Linux test machine, not on real Windows PCs yet. If something looks wrong: Settings → About (or F1) → *Copy info for a bug report*, then open an issue.
- **Smart finding is not a trained model.** It is rules of thumb (word lists, sound detectors, clip lengths) tuned on sounds made by the test tools and on published advice about short videos, whose claims were not verified. It was not trained on real VTuber clips. Please check what it picks.
- It does not post for you, show analytics, track faces or make pictures from scratch.
- There is no licence for the code yet (all rights reserved).
