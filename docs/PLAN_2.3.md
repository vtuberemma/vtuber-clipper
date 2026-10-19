# 2.3 plan (written 2026-10-19) - the 50 features

Constraints (same as 2.2): no picture-making, no direct posting / analytics, no ML model (rules + the creator's own picks), keep the Simple view small.
New options are OFF unless they only add a warning or a tiny boost. Every feature has a test in `tests/`.

New modules: `vcclues.py` (finding clues), `vcsafe.py` (privacy + checks), `vcmedia.py` (picture / sound / file extras), `vcshare.py` (reports, texts, files, snapshots),
`vcnet.py` (download options, update checker + installer), `vc23.py` (the 2.3 options and the feature list), `vc23ui.py` (windows).

## A. Finding the moment (11)
 1 `!clip` / `!marker` commands in the chat log become must-consider moments
 2 Milestones and firsts (sub / follower goals, level-ups, "first time", birthday)
 3 Chat-reading moments (she reads or answers chat)
 4 Bilingual switch (English <-> Japanese / Korean / Chinese ... inside one sentence)
 5 Rapid-fire excitement (words per second spike)
 6 Panic repeats ("no no no no", "wait wait wait")
 7 Build-up -> peak shape (energy that climbs to a peak)
 8 Open on action (cut dead air at the start)
 9 Clean ending (cut dead air after the last word)
10 Spread the clips over the whole stream
11 Skip BRB, intermission, "starting soon" and goodbye parts

## B. Picture, sound, files (15)
12 Background blur strength            13 Background brightness            14 Noise gate (keyboard / mouse between words)
15 De-esser (harsh S sounds)           16 Progress bar: place and thickness 17 Colour the feeling words in captions
18 Logo see-through level              19 Music by mood (sub-folders)       20 Soft subtitles track inside the mp4
21 Title / channel / game in the file's info                                22 Strip hidden info from the file (privacy)
23 Also save the sound (MP3)           24 GIF of the best moment            25 Three cover choices
26 Sharpest-frame covers (no blurry / mid-transition frame)

## C. Checks (2)
27 Flash safety check (photosensitivity)    28 Clip check: length for the platform, loudness, quiet start, black start, loud peak

## D. Privacy for VTubers (4)
29 Privacy guard: e-mails, phone numbers, street addresses, links, "my real name is ..." -> bleep + star
30 My private words (real name, town, school...) -> bleep + star
31 Privacy scan report with times for any video (Tools)
32 Private words are kept out of file names, titles, hashtags and the post kit

## E. Workflow, reports, updates (18)
33 Highlights report (HTML) with VOD times            34 VOD timestamps for the description (chapters)   35 Import chapters from the video file
36 Download only a part of a VOD                       37 Download speed limit + parallel pieces          38 Cookies file for sub-only VODs
39 Disk-space guard before a run                       40 Folder per day                                   41 Duplicate-clip finder
42 Bulk rename with preview                            43 Settings snapshots (go back)                     44 Per-platform post texts with limits
45 Alt-text file                                       46 Community message draft (Discord / X thread)     47 "Maybe" folder for weak clips
48 Update checker                                      49 Safe in-app updater (backup + undo)             50 Remember length / style / count per game

## Honest limits
- Finding clues are rules tuned on synthetic sounds and made-up transcripts, not on real VTuber footage.
- Privacy guard finds PATTERNS in the speech-to-text; it can miss a spoken detail or flag a harmless number. It is a safety net, not a guarantee.
- Flash check measures the finished picture; it follows the common "no more than 3 flashes a second" rule of thumb, it is not a medical certificate.
- The update checker needs a published GitHub release; until one exists it says so.
