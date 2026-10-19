"""VTuber Clipper 2.3 - the options of the 2.3 features, the checking of those options, and the list of the 50 new things.
streamclip.py merges DEFAULTS into its own OPTS and calls clean_opts() on every run, so a damaged settings file can never reach a render."""
import re

# ================================================================ options
BG_BLURS = {"soft": ("Soft", .5), "normal": ("Normal", 1.0), "strong": ("Strong", 1.8), "extreme": ("Very strong", 3.0)}
BAR_POS = {"bottom": "Bottom edge", "top": "Top edge"}
PRIVACY = {"off": "Off", "warn": "Warn me (default)", "bleep": "Bleep it and star it in the captions"}

DEFAULTS = dict(
    # A. finding
    chat_cmds=True, clue_milestone=True, clue_chat=True, clue_bilingual=True, clue_fast=True, clue_repeat=True, clue_buildup=True,
    lead_trim=True, tail_trim=True, spread=False, skip_dead=True,
    # B. picture, sound, files
    bg_blur="normal", bg_dim=0, gate=False, deess=False, bar_pos="bottom", bar_thick=14, cap_feel=False, logo_alpha=92, music_mood=False,
    soft_subs=False, meta_tags=False, scrub_meta=False, audio_copy=False, gif_clip=False, cover_alts=False, cover_sharp=True,
    # C. checks
    flash_check=True, preflight=True,
    # D. privacy
    privacy="warn", private_words="",
    # E. workflow
    report_html=False, stamps_file=False, disk_guard=True, day_folder=False, maybe_folder=False, maybe_below=30,
    platform_texts=False, alt_text=False, community_msg=False, game_memory=False, update_check=False)

BOOLS = ("chat_cmds", "clue_milestone", "clue_chat", "clue_bilingual", "clue_fast", "clue_repeat", "clue_buildup", "lead_trim", "tail_trim", "spread", "skip_dead",
         "gate", "deess", "cap_feel", "music_mood", "soft_subs", "meta_tags", "scrub_meta", "audio_copy", "gif_clip", "cover_alts", "cover_sharp",
         "flash_check", "preflight", "report_html", "stamps_file", "disk_guard", "day_folder", "maybe_folder", "platform_texts", "alt_text", "community_msg", "game_memory", "update_check")
INTS = dict(bg_dim=(-50, 50), bar_thick=(4, 40), logo_alpha=(20, 100), maybe_below=(0, 100))
# options that belong to the new tabs / rows of the window (streamclip_app adds these to OPT_STR / OPT_BOOL)
STR_KEYS = ("bg_blur", "bg_dim", "bar_pos", "bar_thick", "logo_alpha", "privacy", "private_words", "maybe_below")
BOOL_KEYS = BOOLS
PRIVATE_KEYS = ("private_words",)                      # never travel inside a shared look code


def split_words(text, limit=60):
    """'Mia, Tokyo; Sunrise High\nmy street' -> ['mia', 'tokyo', 'sunrise high', 'my street'] (lower case, no duplicates, at most `limit`)."""
    out = []
    for p in re.split(r"[,;\n\r|]+", str(text or "")):
        p = re.sub(r"\s+", " ", p).strip().lower()
        if 2 <= len(p) <= 40 and p not in out: out.append(p)
    return out[:limit]


def clean_opts(d):
    """Check the 2.3 options of an options dict (in place): a bad saved value is replaced by the default."""
    for k in BOOLS:
        v = d.get(k, DEFAULTS[k])
        d[k] = (v.strip().lower() not in ("", "0", "false", "no", "off", "none")) if isinstance(v, str) else bool(v)
    d["bg_blur"] = d.get("bg_blur") if d.get("bg_blur") in BG_BLURS else "normal"
    d["bar_pos"] = d.get("bar_pos") if d.get("bar_pos") in BAR_POS else "bottom"
    d["privacy"] = d.get("privacy") if d.get("privacy") in PRIVACY else "warn"
    for k, (lo, hi) in INTS.items():
        try: d[k] = min(hi, max(lo, int(float(d.get(k, DEFAULTS[k])))))
        except (TypeError, ValueError, OverflowError): d[k] = DEFAULTS[k]
    d["private_words"] = "\n".join(split_words(d.get("private_words")))
    return d


# ================================================================ the 50 new things: (number, group, option key or None, title, "module.function" that does the work)
GROUPS = {"A": "Finding the moment", "B": "Picture, sound and files", "C": "Checks", "D": "Privacy", "E": "Workflow, reports and updates"}
FEATURES = [
    (1, "A", "chat_cmds", "!clip commands in the chat log become must-consider moments", "vcclues.command_moments"),
    (2, "A", "clue_milestone", "Milestones and firsts count for more", "vcclues.milestone_marks"),
    (3, "A", "clue_chat", "Moments where she reads or answers chat", "vcclues.chat_talk_marks"),
    (4, "A", "clue_bilingual", "Bilingual switches (English <-> Japanese ...)", "vcclues.bilingual_marks"),
    (5, "A", "clue_fast", "Rapid-fire excited talking", "vcclues.fast_speech"),
    (6, "A", "clue_repeat", "Panic repeats (\"no no no no\")", "vcclues.repeat_runs"),
    (7, "A", "clue_buildup", "Build-up to a peak", "vcclues.buildup_curve"),
    (8, "A", "lead_trim", "Open on action: cut dead air at the start", "vcclues.trim_edges"),
    (9, "A", "tail_trim", "Clean ending: cut dead air after the last word", "vcclues.trim_edges"),
    (10, "A", "spread", "Spread the clips over the whole stream", "vcclues.spread_factor"),
    (11, "A", "skip_dead", "Skip BRB, intermission and goodbye parts", "vcclues.dead_zones"),
    (12, "B", "bg_blur", "Background blur strength", "vcmedia.blur_params"),
    (13, "B", "bg_dim", "Background brightness", "vcmedia.dim_filter"),
    (14, "B", "gate", "Noise gate (keyboard / mouse between words)", "vcmedia.audio_gate"),
    (15, "B", "deess", "De-esser (soften harsh S sounds)", "vcmedia.audio_gate"),
    (16, "B", "bar_pos", "Progress bar: edge and thickness", "vcmedia.bar_geometry"),
    (17, "B", "cap_feel", "Colour the feeling words in the captions", "vcmedia.feel_wrap"),
    (18, "B", "logo_alpha", "Logo see-through level", "vcmedia.logo_alpha_filter"),
    (19, "B", "music_mood", "Music by mood (sub-folders)", "vcmedia.mood_pick"),
    (20, "B", "soft_subs", "Switchable subtitles inside the mp4", "vcmedia.add_soft_subs"),
    (21, "B", "meta_tags", "Title, channel and game in the file's info", "vcmedia.write_tags"),
    (22, "B", "scrub_meta", "Strip hidden info from the file", "vcmedia.scrub"),
    (23, "B", "audio_copy", "Also save the sound as an MP3", "vcmedia.export_audio"),
    (24, "B", "gif_clip", "A GIF of the best moment", "vcmedia.make_gif"),
    (25, "B", "cover_alts", "Three cover choices", "vcmedia.cover_candidates"),
    (26, "B", "cover_sharp", "Sharpest-frame covers", "vcmedia.sharpness"),
    (27, "C", "flash_check", "Flash safety check", "vcsafe.flash_report"),
    (28, "C", "preflight", "Clip check before you post", "vcsafe.clip_check"),
    (29, "D", "privacy", "Privacy guard: e-mails, phone numbers, addresses, links, real-name slips", "vcsafe.privacy_hits"),
    (30, "D", "private_words", "My private words", "vcsafe.private_hits"),
    (31, None, None, "Privacy scan report with times", "vcsafe.scan_report"),
    (32, "D", "private_words", "Private words kept out of file names, titles and hashtags", "vcsafe.scrub_text"),
    (33, "E", "report_html", "Highlights report (HTML)", "vcshare.report_html"),
    (34, "E", "stamps_file", "VOD timestamps for the description", "vcshare.timestamps_text"),
    (35, None, None, "Import chapters from the video file", "vcshare.read_chapters"),
    (36, None, None, "Download only a part of a VOD", "vcnet.ytdlp_args"),
    (37, None, None, "Download speed limit and parallel pieces", "vcnet.ytdlp_args"),
    (38, None, None, "Cookies file for sub-only VODs", "vcnet.ytdlp_args"),
    (39, "E", "disk_guard", "Disk-space guard before a run", "vcsafe.disk_check"),
    (40, "E", "day_folder", "Folder per day", "vcshare.day_folder"),
    (41, None, None, "Duplicate-clip finder", "vcshare.find_duplicates"),
    (42, None, None, "Bulk rename with preview", "vcshare.rename_plan"),
    (43, None, None, "Settings snapshots (go back)", "vcshare.snapshot_save"),
    (44, "E", "platform_texts", "Post texts for each platform, with its limits", "vcshare.platform_texts"),
    (45, "E", "alt_text", "Alt-text file", "vcshare.alt_text"),
    (46, "E", "community_msg", "Community message draft", "vcshare.community_message"),
    (47, "E", "maybe_folder", "\"Maybe\" folder for weak clips", "vcshare.maybe_target"),
    (48, "E", "update_check", "Update checker", "vcnet.check_update"),
    (49, None, None, "Safe in-app updater (backup + undo)", "vcnet.apply_update"),
    (50, "E", "game_memory", "Remember length / style / count per game", "vcshare.game_put"),
]
