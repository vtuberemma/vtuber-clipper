**VTuber Clipper 0.2.3 beta.** This is the version the program itself calls **2.3 beta** (the release number here is 0.2.3-beta).

## Downloads

| File | What it is |
| --- | --- |
| `VTuberClipper_2.3_beta.zip` (or the numbered parts `VTuberClipper_2.3_beta.zip.001`…) | The full Windows build, no installation. Unzip the **whole** folder anywhere and double-click `VTuberClipper.exe`. It includes Python, ffmpeg and yt-dlp (about 240 MB). Windows SmartScreen: *More info → Run anyway*. |
| `VTuberClipper_update_2.3_beta.zip` | For people who already have an older version: drag its `app` folder over your own and choose Replace. From 2.3 on you can also install it from inside the app (Tools → Updates). Your settings and clips are not touched. Steps are in the zip (`HOW_TO_UPDATE.txt`). |

## What's new

- **50 new things.** More clues for finding the moment (`!clip` in a chat log, firsts and milestones, reading chat, bilingual switches, rapid talking, panic repeats, build-ups), cleaner starts and endings, skipping BRB and goodbye parts.
- **Privacy & checks** (a new tab): a privacy guard for e-mails, phone numbers, addresses, links and "my real name is…" slips, **My private words** that are always bleeped, a clip check, a flash safety check and a disk-space guard.
- **Picture, sound and files:** background blur and brightness, noise gate, de-esser, progress bar, feeling colours, music by mood, MP3, GIF, three covers, switchable subtitles inside the mp4.
- **Reports and tools:** highlights page, timestamps, community message, post texts per app, duplicates, rename with preview, chapters, snapshots of your settings, a folder per day, a Maybe folder, settings remembered per game.
- **Downloads and updates:** download only a part of a VOD, a speed limit, a cookies file, an update checker and a safe in-app installer with a backup and an undo.
- **Bug fixes:** a damaged settings file could stop the app from opening, and the tests found and fixed several problems in the new code before release. Full list: [CHANGELOG.md](https://github.com/vtuberemma/vtuber-clipper/blob/main/CHANGELOG.md).

## Please read

- **It is a beta.** It was tested a lot, but only on a Linux test machine, not on real Windows PCs yet. If something looks wrong: Settings → About (or F1) → *Copy info for a bug report*, then open an issue.
- **The privacy guard is a safety net, not a guarantee.** It looks for patterns in what the speech-to-text wrote, knows only English phrases and can not hear what the speech-to-text got wrong. Listen to a clip before you post it.
- **The finders are not a trained model.** They are rules of thumb tuned on test sounds and made-up transcripts, not on real VTuber footage. Please check what they pick.
- Text limits for each app are "as far as I know in 2025". Downloading only a part of a VOD was tried on a local test stream, not on real Kick or Twitch VODs.
- It does not post for you, show analytics, track faces or make pictures from scratch.
- There is no licence for the code yet (all rights reserved).
