# Changelog

The long, plain-language version of every release is in [docs/USER_GUIDE.txt](docs/USER_GUIDE.txt). This file is the short list.

## 2.3 beta

**Finding the moment** (on by default; untick Smart finding for the old way)
- New clues: `!clip` / `!highlight` in a saved chat log, firsts and milestones, reading or answering chat, switching between two languages, rapid excited talking, panic repeats ("no no no no"), build-up to a peak.
- Open on the action, clean ending, spread the clips over the whole stream (off), skip BRB / intermission / goodbye parts.

**Privacy and checks** (a new "Privacy & checks" tab)
- Privacy guard for e-mail addresses, phone numbers, street addresses, links and "my real name is…" slips (warn by default, or bleep and star), and **My private words** (always bleeped; never put in a shared look code, titles, hashtags or file names). A pattern check on the speech-to-text, English phrases only.
- Clip check (length for the app, tall picture, loudness, a very loud moment, silent or black start), flash safety check, disk-space guard, Tools → Clip check and Tools → Privacy (scan a transcript).

**Picture, sound and files** (off until switched on)
- Background blur strength and brightness, noise gate, de-esser, progress bar edge and thickness, feeling colours in captions, logo see-through level, music by mood.
- Switchable subtitles inside the mp4, file info tags, hidden-info removal, MP3 of the sound, GIF of the best second, three cover choices, sharpest-frame covers.

**Reports, texts and files**
- Highlights page (HTML), VOD timestamps, community message (Discord / X thread), post texts per app within its limits, alt-text file, folder per day, "Maybe" folder, remembered clip count / length / style per game.
- Tools: Duplicates, Rename with preview, Reports, Chapters, Snapshots of your settings (one is kept each time a run starts), Games. The Tools window now has four groups of pages.

**Downloads and updates**
- Download only a part of a VOD, a speed limit, pieces at once, a cookies file for subscriber-only VODs.
- Update checker (Settings → About, optional once a day) and a safe installer with a backup and an undo (Tools → Updates; also installs an update zip you already have).

**Fixes**
- A damaged settings or profile file (for example the word "maybe" in a true / false switch) could stop the app from opening; it is now skipped.
- Found by the tests in the new code before release: very strong background blur crashed the render; the "very loud moment" warning never fired; the loudness and silent-start checks did nothing in the real app (a keyword clash); the privacy guard covered too many words around a phone number and flagged "at the polka dot co-op"; the report broke on a clip with no time; two snapshots made in one second were listed in the wrong order; a cover frame could be asked for past the end of a short clip.
- Tested with every new option on 14 awkward videos, hundreds of randomly broken settings, a fake GitHub for the update checker and a real yt-dlp for part downloads.

## 2.2 beta

**Smarter finding (on by default)**
- Five kinds of moment (gameplay, reaction, talking, story, singing); laughs, screams and singing are heard in the sound, not only read in the words.
- Skip greeting openings, mix kinds, length per kind, end right after the punchline, setup → payoff, story shape, chat-log help, "why this moment" notes, learn from the clips you keep, kind-specific title ideas, a much bigger vocabulary (plus laugh words in Japanese, Korean, Spanish, Portuguese, French).

**Picture, sound and captions** (off until switched on)
- Hopping logo, slow-mo, freeze-frame beat, teaser of the best moment first, big reaction words (LOL, EEEEK!, OOF…), tame loud screams, hush hiss.
- Caption letter case, outline, shadow, words at a time, see-through box, rainbow words; square and landscape copies of every clip.

**Tools and workflow**
- Tools window: watch a folder, health check, clean-up, free space, share / paste a look, compare 3 looks, hashtag bank, your own words, CSV post sheet.
- My clips: search + tags, review mode, "make this moment again", "where is this from?", ready-to-post folder, fill the post planner in one click.
- Try one clip first, resume an interrupted run, cam box remembered per game, `{type}` `{score}` `{len}` in file names, save / open Best-moments lists, "only look between" times.

**Fixes**
- A damaged settings file (a list where a number belongs, `inf`, the word "false" for a switch) could crash a render (affected 2.1 and older).
- "Compare 3 looks" crashed if the Tools window had been opened and closed before.
- Open windows kept the old colours after a theme change.
- Leaving the simple view now lands on Clips & layout.
- Plain speech was sometimes heard as singing.
- Tested with every new feature on over 15 awkward videos, text full of quotes / emoji / Japanese, and hundreds of randomly broken settings.

## 2.1 beta
- Simple view with a Quick setup tab ("Show all options" for the rest); plain tab names with a one-line description.
- The built-in chibi pictures were removed; "My emotes" stays so you can add your own.
- Words and buttons on the video (Like / Follow / Subscribe…), typewriter captions, more layouts and "Design my own…", read-it-out-loud, trim / tidy, montage with transitions, post planner with reminders.

## 2.0 beta
- The Polish tab (colour looks, crisp picture, fades, brighten dark videos, cut black bars, hide a spot, voice effects, loudness), extra files and naming patterns, little helpers.

## 1.9 – 1.2
- 1.9 chibi emotes for story time and eight more themes; 1.8 your own background music, more sound packs, profiles, recent videos, safer long jobs; 1.7 chibi mascot and costumes; 1.6 bleeping, skip moments already made, hook title modes; 1.5 emoji captions, caption check, cover pictures, share a style; 1.4 audio/picture sync fix, Post helper, X tab, Recap parts and games; 1.3 new layout.
