"""VTuber Clipper 2.0 - the extra files that can be made next to each short: file names from a pattern, a transcript (.txt) and web subtitles (.vtt).
Every helper returns False / "" instead of raising, so a full disk can never stop the video itself."""
import datetime, os, re, shutil, subprocess, tempfile

NAME_TOKENS = {"video": "the VOD's file name", "n": "clip number (1, 2, 3...)", "hook": "the first words of the clip", "date": "today's date (2026-10-13)",
               "game": "the game name from Posting", "time": "where the clip starts in the VOD (1h23m45s)", "channel": "your channel name from Posting",
               "type": "what kind of moment it is (gameplay, reaction, talking, story, singing)", "score": "hype score 0-100", "len": "length in seconds (34s)"}
DEFAULT_PATTERN = "{video}_short{n}"
# files that belong to a clip (everything that sits next to the .mp4 and shares its name). The picture endings are no longer made, but are still
# cleaned up so a clip from an earlier 2.0 beta never leaves files behind when it is deleted.
SIDE_ENDINGS = ("_cover.jpg", "_cover_b.jpg", "_cover_c.jpg", "_best.gif", "_quote.png", "_transcript.txt", "_posts.txt", "_alt.txt", "_check.txt", ".gif", ".mp3", ".m4a", ".srt", ".vtt", ".txt")


def sanitize(s, maxlen=90):
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f{}]', " ", str(s or ""))
    s = re.sub(r"\s+", " ", s).strip(" .")
    return s[:maxlen].strip(" .")


def clip_name(pattern, video, n, hook="", game="", channel="", start=0.0, today=None, kind="", score=None, length=None):
    """File name (no extension) from a pattern like '{video}_short{n}' or '{date} {game} clip {n}'. Unknown {words} are dropped; an empty result falls back to the default."""
    t = int(max(0, start or 0))
    vals = dict(video=sanitize(video, 60), n=str(n), hook=sanitize(hook, 40), game=sanitize(game, 30), channel=sanitize(channel, 30),
                date=(today or datetime.date.today()).isoformat(), time=f"{t // 3600}h{t % 3600 // 60:02d}m{t % 60:02d}s",
                type=sanitize(kind, 12) or "clip", score=("" if score is None else str(int(score))), len=("" if not length else f"{int(round(length))}s"))
    out = re.sub(r"\{(\w+)\}", lambda m: vals.get(m.group(1).lower(), ""), str(pattern or DEFAULT_PATTERN))
    out = sanitize(out, 100)
    return out or f"{vals['video'] or 'clip'}_short{n}"


def pattern_preview(pattern, video="MyStream", n=1, hook="so yesterday I was", game="Minecraft", channel="MiaVT", start=3725):
    return clip_name(pattern, video, n, hook, game, channel, start, kind="reaction", score=87, length=34) + ".mp4"


def sidecars(mp4):
    stem = os.path.splitext(str(mp4))[0]
    return [stem + e for e in SIDE_ENDINGS]


def delete_clip_files(mp4):
    """Remove a clip and everything made with it. An empty 'one folder per VOD' folder is removed too. Returns how many files were deleted."""
    n = 0
    for f in [str(mp4)] + sidecars(mp4):
        try: os.remove(f); n += 1
        except OSError: pass
    d = os.path.dirname(str(mp4))
    try:
        for _ in range(2):                                   # 'one folder per VOD' and 'one folder per day' (2.3) are removed when they are empty
            if os.path.basename(os.path.dirname(d)) in ("Shorts", "Recaps", "Twitter") or os.path.basename(os.path.dirname(os.path.dirname(d))) in ("Shorts", "Recaps", "Twitter"):
                if os.path.isdir(d) and not os.listdir(d): os.rmdir(d)
                else: break
            else: break
            d = os.path.dirname(d)
    except OSError: pass
    return n


# ---------------------------------------------------------------- transcript
def vtt_time(t):
    ms = int(round(max(0.0, t) * 1000))
    return f"{ms // 3600000:02d}:{ms % 3600000 // 60000:02d}:{ms % 60000 // 1000:02d}.{ms % 1000:03d}"


def mmss(t):
    t = int(max(0, t)); return f"{t // 60}:{t % 60:02d}"
