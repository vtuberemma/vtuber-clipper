"""VTuber Clipper 2.3 - what happens to a clip after it was rendered, and what is written once a run is finished.
The engine hands over plain facts (the finished file, the options, the words) and gets plain facts back: what was done and what the creator should look at.
Every step is wrapped, so one extra that cannot run never stops a clip, and a cancelled run stops between steps."""
import os, re, time

import vcmedia, vcmore, vcsafe, vcshare, vcsmart


def _step(name, fn, done, notes, log):
    try:
        r = fn()
        if r: done.append(name)
        return r
    except Exception as e:
        log(f"   ({name} skipped: {str(e)[:80]})"); return None


def finish_clip(out, ctx):
    """Soft subtitles, GIF, MP3, clip check, post texts, alt text, then the file info (scrub / tags). `ctx` keys:
    o (options), ff, nowin, words (the words of this clip, in clip time), write_srt(words, path), censor, hits (seconds where big things happen, strongest first), kit_fn() -> post kit,
    kind, why, dur, platform, cancelled() -> bool, log(text).
    Returns dict(done=[names], notes=[plain sentences for the creator], check=[items], files=[paths made])."""
    o, ff, nowin, log = ctx["o"], ctx["ff"], ctx.get("nowin"), ctx.get("log") or (lambda *a: None)
    cancelled = ctx.get("cancelled") or (lambda: False)
    out = str(out); done, notes, files, check = [], [], [], []
    stem = os.path.splitext(out)[0]
    words = ctx.get("words") or []
    if not os.path.isfile(out): return dict(done=done, notes=notes, files=files, check=check)

    if o.get("soft_subs") and words and not cancelled():
        def subs():
            tmp = stem + ".softsubs.srt"
            ctx["write_srt"](words, tmp, ctx.get("censor") or frozenset())
            try: return vcmedia.add_soft_subs(out, tmp, ff, nowin)
            finally:
                try: os.remove(tmp)
                except OSError: pass
        _step("soft subtitles", subs, done, notes, log)
    if o.get("gif_clip") and not cancelled():
        def gif():
            hits = ctx.get("hits") or []
            p = vcmedia.make_gif(out, hits[0] if hits else ctx.get("dur", 6) * .4, ff, nowin)
            if p: files.append(p)
            return bool(p)
        _step("GIF", gif, done, notes, log)
    if o.get("audio_copy") and not cancelled():
        def mp3():
            p = vcmedia.export_audio(out, ff, nowin)
            if p: files.append(p)
            return bool(p)
        _step("sound file", mp3, done, notes, log)
    if (o.get("preflight", True) or o.get("flash_check", True)) and not cancelled():
        def chk():
            nonlocal check
            check = vcsafe.clip_check(out, ff, nowin, o, ctx.get("platform", "")) if o.get("preflight", True) else []
            if not o.get("preflight", True) and o.get("flash_check", True):
                fl = vcsafe.flash_report(out, ff, nowin)
                if fl["checked"]: check = [dict(level="ok" if fl["ok"] else "bad", text=fl["notes"])]
            return True
        _step("clip check", chk, done, notes, log)
    check = list(check) + list(ctx.get("extra_check") or [])                  # e.g. words the privacy guard only reported
    bad = [c for c in check if c["level"] != "ok"]
    if bad:
        for c in bad: notes.append(c["text"])
        try:
            with open(stem + "_check.txt", "w", encoding="utf-8") as fh: fh.write(vcsafe.check_text(check, os.path.basename(out)))
            files.append(stem + "_check.txt")
        except OSError as e: log(f"   (check note not saved: {str(e)[:60]})")
    if check:
        lv = vcsafe.worst_level(check)
        log(f"   check: {'all fine' if lv == 'ok' else str(len(bad)) + ' thing(s) to look at - see ' + os.path.basename(stem) + '_check.txt'}")
    kit = None
    if (o.get("platform_texts") or o.get("alt_text")) and not cancelled():
        if o.get("platform_texts"):
            def posts():
                kit = ctx["kit_fn"]()
                txt, warn = vcshare.platform_texts(kit, o.get("handle", ""))
                with open(stem + "_posts.txt", "w", encoding="utf-8") as fh: fh.write(txt)
                files.append(stem + "_posts.txt"); return True
            _step("post texts", posts, done, notes, log)
        if o.get("alt_text"):
            def alt():
                s, l = vcshare.alt_text(words, ctx.get("kind", ""), ctx.get("why") or [], ctx.get("dur", 0.0), "vertical" if o.get("aspect", "9:16") in ("9:16", "4:5") else "")
                with open(stem + "_alt.txt", "w", encoding="utf-8") as fh: fh.write("ALT TEXT (short)\n" + s + "\n\nALT TEXT (long)\n" + l + "\n")
                files.append(stem + "_alt.txt"); return True
            _step("alt text", alt, done, notes, log)
    if o.get("scrub_meta") and not cancelled():
        _step("hidden info removed", lambda: vcmedia.scrub(out, ff, nowin), done, notes, log)
    if o.get("meta_tags") and not cancelled():
        t = ctx.get("title") or ""
        _step("file info", lambda: vcmedia.write_tags(out, dict(title=t, artist=o.get("channel", ""), genre=o.get("game", ""), comment=("VTuber Clipper - " + (ctx.get("kind") or "clip")),
                                                                 date=time.strftime("%Y")), ff, nowin), done, notes, log)
    return dict(done=done, notes=notes, files=files, check=check)


def privacy_notes(words):
    """Plain sentences about the words of a clip that the privacy guard flagged: ['phone number at 0:14 (bleeped)', ...]. Words in a row with the same flag count once."""
    out, cur = [], None
    for w in words:
        k = w.get("priv") or w.get("pwarn")
        if k and cur and cur[0] == k and cur[1] == bool(w.get("priv")) and w["start"] - cur[3] < 1.2:
            cur[3] = w["end"]; continue
        if k:
            cur = [k, bool(w.get("priv")), w["start"], w["end"]]; out.append(cur)
        else: cur = None
    res = []
    for k, bleep, a, b in out:
        t = int(a)
        res.append(f"{vcsafe.KIND_LABEL.get(k, k)} said at {t // 60}:{t % 60:02d}" + (" - bleeped" if bleep else " - NOT bleeped, listen to it"))
    return res


def finish_run(entries, ctx):
    """Once all clips of a run are made: the highlights report, the VOD timestamps, the community message. ctx: o, outdir, vod_name, unique(path)->path, log.
    Returns the list of files written."""
    o, outdir, log = ctx["o"], ctx["outdir"], ctx.get("log") or (lambda *a: None)
    uniq = ctx.get("unique") or (lambda p: p)
    files = []
    if not entries: return files
    stem = re.sub(r'[<>:"/\\|?*]', "_", ctx.get("vod_name") or "stream")[:60]
    if o.get("report_html"):
        try:
            p = uniq(os.path.join(outdir, f"{stem}_highlights.html"))
            with open(p, "w", encoding="utf-8") as fh: fh.write(vcshare.report_html(entries, ctx.get("vod_name", ""), o.get("channel", ""), o.get("game", ""), base_dir=outdir))
            files.append(p); log(f"Highlights report: {os.path.basename(p)}")
        except Exception as e: log("(highlights report skipped:", str(e)[:80] + ")")
    if o.get("stamps_file"):
        try:
            t = vcshare.timestamps_text(entries)
            if t:
                p = uniq(os.path.join(outdir, f"{stem}_timestamps.txt"))
                with open(p, "w", encoding="utf-8") as fh: fh.write(t)
                files.append(p); log(f"VOD timestamps: {os.path.basename(p)}")
            else: log("(VOD timestamps need at least two clips that start more than 10 seconds apart)")
        except Exception as e: log("(timestamps skipped:", str(e)[:80] + ")")
    if o.get("community_msg"):
        try:
            d = vcshare.community_message(entries, ctx.get("vod_name", ""), o.get("channel", ""), o.get("game", ""), "discord")
            x = vcshare.community_message(entries, ctx.get("vod_name", ""), o.get("channel", ""), o.get("game", ""), "x")
            p = uniq(os.path.join(outdir, f"{stem}_community.txt"))
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("DISCORD / COMMUNITY POST\n\n" + "\n\n--- next message ---\n\n".join(d) + "\n\n\nX THREAD (one post per line)\n\n" + "\n".join(x) + "\n")
            files.append(p); log(f"Community message: {os.path.basename(p)}")
        except Exception as e: log("(community message skipped:", str(e)[:80] + ")")
    return files
