"""VTuber Clipper 2.3 - reports, texts and file housekeeping (features 33-35, 40-47, 50).
 33 highlights report (HTML)       34 VOD timestamps for the description     35 chapters from the video file       40 folder per day
 41 duplicate-clip finder          42 bulk rename with preview               43 settings snapshots                 44 post texts for each platform
 45 alt-text file                  46 community message draft                47 "Maybe" folder for weak clips      50 remember length / style / count per game
Everything here works on plain dicts and strings (clips are described by the same entries the clip ledger keeps), so it is easy to test."""
import datetime, html, json, os, re, shutil, subprocess, time, urllib.parse

import vcmore, vcouts, vcsmart, vctools

# ================================================================ small helpers
def hms(t):
    try: t = int(max(0, float(t)))
    except (TypeError, ValueError, OverflowError): t = 0
    h, m, s = t // 3600, t % 3600 // 60, t % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def entry_title(e):
    """The best short title for a clip entry: the first title idea, else the kind and the time."""
    t = (e.get("titles") or [""])[0] if isinstance(e.get("titles"), list) else ""
    if t: return re.sub(r"\s+", " ", str(t)).strip()
    k = vcsmart.type_label(e.get("kind", "")) if e.get("kind") else "Moment"
    return f"{k or 'Moment'} at {hms(e.get('start', 0))}"


# ================================================================ 33  highlights report (HTML)
def _rel(path, base):
    """A web link to a file, relative to the folder the report sits in (a clip moved to the Maybe folder is still found)."""
    try: r = os.path.relpath(path, base) if base else os.path.basename(path)
    except ValueError: r = os.path.basename(path)
    return urllib.parse.quote(r.replace("\\", "/"))


def report_html(entries, vod_name="", channel="", game="", made=None, base_dir=None):
    """One self-contained web page about a run: every clip with its place in the VOD, kind, hype, length, why it was picked, title ideas and a link to the file and cover."""
    esc = lambda x: html.escape(str(x if x is not None else ""), quote=True)
    made = made or time.strftime("%Y-%m-%d %H:%M")
    ents = sorted(entries, key=lambda e: float(e.get("start", 0) or 0))
    total = sum(float(e.get("dur", 0) or 0) for e in ents)
    kinds = {}
    for e in ents: kinds[e.get("kind") or "clip"] = kinds.get(e.get("kind") or "clip", 0) + 1
    ksum = ", ".join(f"{n} {vcsmart.type_label(k).lower() or k}" for k, n in sorted(kinds.items(), key=lambda x: -x[1]))
    rows = []
    for i, e in enumerate(ents, 1):
        p = str(e.get("path", "")); base = os.path.basename(p); stem = os.path.splitext(base)[0]
        cover = _rel(os.path.join(os.path.dirname(p), stem + "_cover.jpg"), base_dir)
        why = "".join(f"<li>{esc(w)}</li>" for w in (e.get("reasons") or e.get("why") or [])[:5])
        tit = "".join(f"<li>{esc(t)}</li>" for t in (e.get("titles") or [])[:3])
        warn = "".join(f"<li class=warn>{esc(w)}</li>" for w in (e.get("notes") or [])[:4])
        img = f'<img src="{esc(cover)}" alt="Cover picture of clip {i}" loading=lazy onerror="this.style.display=\'none\'">' if os.path.splitext(base)[1] else ""
        rows.append(
            f'<article><div class=pic>{img}</div><div class=body><h2>{i}. {esc(entry_title(e))}</h2>'
            f'<p class=meta><b>{esc(hms(e.get("start", 0)))}</b> in the VOD &middot; {esc(vcsmart.type_label(e.get("kind", "")) or "clip")} &middot; hype {esc(e.get("hype", "-"))} &middot; {float(e.get("dur", 0) or 0):.0f} s</p>'
            + (f"<ul class=why>{why}</ul>" if why else "") + (f"<details><summary>Title ideas</summary><ul>{tit}</ul></details>" if tit else "")
            + (f"<ul class=notes>{warn}</ul>" if warn else "")
            + f'<p><a href="{esc(_rel(p, base_dir))}">{esc(base)}</a></p></div></article>')
    return ("<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>Highlights - {esc(vod_name or 'stream')}</title><style>"
            ":root{--bg:#fbf8fc;--fg:#2a2233;--mute:#6f6479;--card:#fff;--line:#e6dcee;--acc:#d6336c}@media(prefers-color-scheme:dark){:root{--bg:#17121c;--fg:#f2ecf7;--mute:#a99bb8;--card:#211a29;--line:#352b40;--acc:#ff7aa8}}"
            "body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,Segoe UI,sans-serif}main{max-width:860px;margin:0 auto;padding:24px 16px 48px}"
            "h1{font-size:1.6rem;margin:.2em 0}.sub{color:var(--mute);margin:0 0 20px}article{display:flex;gap:16px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;margin:0 0 14px}"
            ".pic{flex:0 0 120px}.pic img{width:120px;border-radius:8px;display:block}.body{flex:1;min-width:0}h2{font-size:1.05rem;margin:0 0 4px}.meta{color:var(--mute);margin:0 0 6px;font-size:.9rem}"
            "ul{margin:4px 0 6px 18px;padding:0}a{color:var(--acc);word-break:break-all}.warn{color:#b8860b}summary{cursor:pointer;color:var(--mute)}@media(max-width:560px){article{flex-direction:column}.pic{flex-basis:auto}}"
            "</style></head><body><main>"
            f"<h1>Highlights from {esc(vod_name or 'your stream')}</h1><p class=sub>{len(ents)} clip{'s' if len(ents) != 1 else ''}, {hms(total)} in all"
            + (f" &middot; {esc(ksum)}" if ksum else "") + (f" &middot; {esc(channel)}" if channel else "") + (f" &middot; {esc(game)}" if game else "") + f" &middot; made {esc(made)}</p>"
            + "".join(rows) + "</main></body></html>")


# ================================================================ 34  VOD timestamps for the description
def timestamps_text(entries, min_gap=10.0, intro="Intro", limit=40):
    """A list for the description of the full VOD upload, in the format YouTube turns into chapters: the first line is 0:00, every line is at least `min_gap` seconds after the last.
    Returns '' when there are fewer than 2 moments (YouTube needs at least three lines in all)."""
    ents = sorted([e for e in entries if e.get("start") is not None], key=lambda e: float(e["start"]))
    lines, last = [], -1e9
    for e in ents:
        t = int(float(e["start"]))
        if t - last < min_gap: continue
        lines.append((t, entry_title(e))); last = t
        if len(lines) >= limit: break
    if len(lines) < 2: return ""
    if lines[0][0] >= min_gap: lines.insert(0, (0, intro))
    elif lines[0][0] != 0: lines[0] = (0, lines[0][1])
    wide = any(t >= 3600 for t, _ in lines)
    return "\n".join((f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if wide else f"{t // 60}:{t % 60:02d}") + f" {re.sub(chr(10), ' ', n)[:80]}" for t, n in lines) + "\n"


# ================================================================ 35  chapters from the video file
def read_chapters(path, ff="ffmpeg", nowin=None):
    """[(start, end, title)] seconds of the chapters stored in a video file (or in the yt-dlp '.info.json' next to it). [] when there are none."""
    out = []
    try:
        r = subprocess.run([ff, "-v", "error", "-i", path, "-f", "ffmetadata", "-"], capture_output=True, errors="replace", timeout=120, **vcmore._kw(nowin))
        txt = r.stdout or ""
    except Exception: txt = ""
    for blk in re.split(r"\[CHAPTER\]", txt)[1:]:
        tb = re.search(r"TIMEBASE=(\d+)/(\d+)", blk); a = re.search(r"START=(-?\d+)", blk); b = re.search(r"END=(-?\d+)", blk); t = re.search(r"^title=(.*)$", blk, re.M)
        if tb and a and b:
            f = int(tb.group(1)) / max(1, int(tb.group(2)))
            out.append((float(a.group(1)) * f, float(b.group(1)) * f, (t.group(1).strip() if t else "") or f"Chapter {len(out) + 1}"))
    if not out:
        for cand in (os.path.splitext(path)[0] + ".info.json", path + ".info.json"):
            try:
                with open(cand, encoding="utf-8") as fh: d = json.load(fh)
                for c in d.get("chapters") or []:
                    out.append((float(c["start_time"]), float(c["end_time"]), str(c.get("title") or f"Chapter {len(out) + 1}")))
                if out: break
            except Exception: continue
    return [c for c in out if c[1] > c[0]]


def chapters_to_moments(chapters, hi=60.0, lo=12.0, per=1):
    """Best-moments style windows [(start, end, label)] from chapters: each chapter gives `per` windows of at most `hi` seconds from its start."""
    out = []
    for a, b, t in chapters:
        if b - a < lo: continue
        for k in range(per):
            s = a + k * hi
            if s + lo > b: break
            out.append((s, min(b, s + hi), t))
    return out


# ================================================================ 40  folder per day
def day_folder(today=None):
    return (today or datetime.date.today()).isoformat()


# ================================================================ 41  duplicate-clip finder
def _iou(a0, a1, b0, b1):
    inter = max(0.0, min(a1, b1) - max(a0, b0)); uni = max(a1, b1) - min(a0, b0)
    return inter / uni if uni > 0 else 0.0


def find_duplicates(entries, need=.5, near=3.0):
    """Groups of clips cut from (nearly) the same moment of the same video: they overlap by at least `need` of their length, or start within `near` seconds of each other.
    -> [[entry, entry...]] with the highest hype first in every group. Clips that were deleted are ignored."""
    ents = [e for e in entries if not e.get("deleted") and e.get("vod") and e.get("start") is not None and e.get("end") is not None]
    ents.sort(key=lambda e: (str(e["vod"]), float(e["start"])))
    groups, used = [], set()
    for i, a in enumerate(ents):
        if i in used: continue
        grp = [a]; used.add(i)
        for j in range(i + 1, len(ents)):
            b = ents[j]
            if j in used or b["vod"] != a["vod"]: continue
            if any(_iou(float(g["start"]), float(g["end"]), float(b["start"]), float(b["end"])) >= need or abs(float(g["start"]) - float(b["start"])) <= near for g in grp):
                grp.append(b); used.add(j)
        if len(grp) > 1: groups.append(sorted(grp, key=lambda e: -float(e.get("hype") or 0)))
    return groups


# ================================================================ 42  bulk rename with preview
def rename_plan(files, pattern, info=None, today=None):
    """-> [(old path, new path)] for renaming clips by a pattern like '{date} {game} clip {n}'. `info` = function(path) -> ledger entry or None. The new names never clash with each
    other or with a file that is already there (a number is added: 'name (2)'). A clip that would keep its name is left out."""
    plan, taken = [], set()
    for n, f in enumerate(files, 1):
        e = (info(f) if info else None) or {}
        folder, ext = os.path.dirname(f), os.path.splitext(f)[1]
        base = vcouts.clip_name(pattern, os.path.splitext(os.path.basename(e.get("vod", "") or f))[0], n, os.path.splitext(os.path.basename(f))[0].split("_short")[0] if not e else "",
                                e.get("game", "") or "", e.get("channel", "") or "", float(e.get("start", 0) or 0), today, kind=e.get("kind", ""), score=e.get("hype"), length=e.get("dur"))
        new = os.path.join(folder, base + ext); k = 2
        while (os.path.exists(new) and os.path.abspath(new) != os.path.abspath(f)) or os.path.abspath(new).lower() in taken:
            if os.path.abspath(new) == os.path.abspath(f): break
            new = os.path.join(folder, f"{base} ({k}){ext}"); k += 1
        taken.add(os.path.abspath(new).lower())
        if os.path.abspath(new) != os.path.abspath(f): plan.append((f, new))
    return plan


def rename_apply(plan, ledger_move=None):
    """Do the renames of rename_plan() - the clip and the files that belong to it. Returns how many clips were renamed. Never overwrites."""
    done = 0
    for old, new in plan:
        if not os.path.isfile(old) or os.path.exists(new): continue
        so, sn = os.path.splitext(old)[0], os.path.splitext(new)[0]
        moved = []
        try:
            os.rename(old, new); moved.append((old, new))
            for e in vcouts.SIDE_ENDINGS:
                if os.path.isfile(so + e) and not os.path.exists(sn + e): os.rename(so + e, sn + e); moved.append((so + e, sn + e))
            for e in ("_1x1.mp4", "_16x9.mp4", "_4x5.mp4"):
                if os.path.isfile(so + e) and not os.path.exists(sn + e): os.rename(so + e, sn + e); moved.append((so + e, sn + e))
        except OSError:
            for a, b in reversed(moved):                  # undo a half-done rename
                try: os.rename(b, a)
                except OSError: pass
            continue
        done += 1
        if ledger_move:
            try: ledger_move(old, new)
            except Exception: pass
    return done


# ================================================================ 43  settings snapshots
SNAP_DIR = os.path.join(os.path.expanduser("~"), ".vtuberclipper_snapshots")


def _snap_dir(folder=None):
    d = folder or SNAP_DIR
    os.makedirs(d, exist_ok=True); return d


def snapshot_save(state, label="", keep=12, folder=None):
    """Keep a copy of the current settings (a plain dict of text / numbers / true-false). A copy identical to the newest one is not stored twice. Returns the file name or ''."""
    try:
        d = _snap_dir(folder); state = json.loads(json.dumps(state, default=str))
        names = sorted(n for n in os.listdir(d) if n.endswith(".json"))
        if names:
            try:
                with open(os.path.join(d, names[-1]), encoding="utf-8") as fh: last = json.load(fh)
                if last.get("state") == state: return ""
            except Exception: pass
        stamp = time.strftime("%Y%m%d-%H%M%S"); k = 0
        name = f"{stamp}-{k:02d}.json"
        while os.path.exists(os.path.join(d, name)): k += 1; name = f"{stamp}-{k:02d}.json"           # two copies in one second still sort in the order they were made
        with open(os.path.join(d, name), "w", encoding="utf-8") as fh: json.dump(dict(label=str(label)[:60], made=time.strftime("%Y-%m-%d %H:%M"), state=state), fh, ensure_ascii=False)
        names = sorted(n for n in os.listdir(d) if n.endswith(".json"))
        for old in names[:-max(1, keep)]:
            try: os.remove(os.path.join(d, old))
            except OSError: pass
        return name
    except Exception: return ""


def snapshot_list(folder=None):
    """[dict(id, label, made, count)] newest first."""
    out = []
    try:
        d = folder or SNAP_DIR
        for n in sorted((x for x in os.listdir(d) if x.endswith(".json")), reverse=True):
            try:
                with open(os.path.join(d, n), encoding="utf-8") as fh: s = json.load(fh)
                out.append(dict(id=n, label=s.get("label", ""), made=s.get("made", ""), count=len(s.get("state") or {})))
            except Exception: continue
    except OSError: pass
    return out


def snapshot_load(sid, folder=None):
    """The settings dict stored in a snapshot, or None."""
    try:
        if os.path.basename(sid) != sid: return None
        with open(os.path.join(folder or SNAP_DIR, sid), encoding="utf-8") as fh: s = json.load(fh)
        return s.get("state") if isinstance(s.get("state"), dict) else None
    except Exception: return None


def snapshot_diff(old, new):
    """Names of the settings that differ between two snapshots (for the 'what changed' line)."""
    return sorted(k for k in set(old) | set(new) if old.get(k) != new.get(k))


# ================================================================ 44  post texts for each platform, with the limits
LIMITS = {"tiktok": dict(name="TikTok", caption=2200, tags=5), "shorts": dict(name="YouTube Shorts", title=100, desc=5000, tags=3), "reels": dict(name="Instagram Reels", caption=2200, tags=5),
          "x": dict(name="X", post=280, tags=2)}                    # as far as I know in 2025; the apps change these now and then


def _trim(s, n):
    s = str(s)
    return s if len(s) <= n else s[:max(0, n - 1)].rstrip() + "…"


def platform_texts(kit, handle="", links=""):
    """-> (text for the _posts.txt file, {platform: [warnings]}). Every platform's caption is cut to its limit and its number of hashtags is kept low (a few well-chosen tags work better than 30)."""
    warn = {k: [] for k in LIMITS}; out = []

    def tags(lst, n): return [t for t in lst if t.startswith("#")][:n]
    yt = kit.get("youtube", {}); tt = kit.get("tiktok", {}); ig = kit.get("reels", {}); tw = kit.get("twitter", {})
    title = yt.get("title") or (kit.get("titles") or ["Stream highlight"])[0]
    if len(title) > LIMITS["shorts"]["title"]: warn["shorts"].append("title was cut to 100 characters")
    title = _trim(title, LIMITS["shorts"]["title"])
    desc = yt.get("description", "")
    if "#shorts" not in desc.lower() and "#shorts" not in title.lower(): desc = (desc + "\n#Shorts").strip()
    desc = _trim(desc, LIMITS["shorts"]["desc"])
    out += ["YOUTUBE SHORTS", f"  Title ({len(title)}/{LIMITS['shorts']['title']}): {title}", "  Description:", *["    " + l for l in desc.splitlines()], ""]
    cap = tt.get("caption", "")
    body = re.sub(r"(\s*#\w+)+\s*$", "", cap).rstrip()
    cap2 = body + "\n" + " ".join(tags(tt.get("hashtags", []), LIMITS["tiktok"]["tags"]))
    if len(cap2) > LIMITS["tiktok"]["caption"]: warn["tiktok"].append("caption was cut"); cap2 = _trim(cap2, LIMITS["tiktok"]["caption"])
    out += ["TIKTOK", f"  Caption ({len(cap2)}/{LIMITS['tiktok']['caption']}):", *["    " + l for l in cap2.splitlines()], ""]
    cap = ig.get("caption", ""); body = re.sub(r"(\s*#\w+)+\s*$", "", cap).rstrip()
    cap3 = body + "\n\n" + " ".join(tags(ig.get("hashtags", []), LIMITS["reels"]["tags"]))
    if len(cap3) > LIMITS["reels"]["caption"]: warn["reels"].append("caption was cut"); cap3 = _trim(cap3, LIMITS["reels"]["caption"])
    out += ["INSTAGRAM REELS", f"  Caption ({len(cap3)}/{LIMITS['reels']['caption']}):", *["    " + l for l in cap3.splitlines()], ""]
    posts = [p.get("text", "") if isinstance(p, dict) else str(p) for p in (tw.get("posts") or [])][:2]
    out += ["X"]
    for p in posts or [title]:
        t = re.sub(r"\s+", " ", p).strip()
        if len(t) > LIMITS["x"]["post"]: warn["x"].append("a post was cut to 280 characters"); t = _trim(t, LIMITS["x"]["post"])
        out.append(f"  ({len(t)}/{LIMITS['x']['post']}) {t}")
    return "\n".join(out) + "\n\n(Limits are the ones I know of; the apps change them now and then.)\n", warn


# ================================================================ 45  alt-text file
def alt_text(words, kind="", why=(), dur=0.0, aspect="vertical"):
    """-> (short, long) plain-language descriptions for people who cannot see the video: what kind of clip it is, what is said first, and what is heard."""
    toks = [str(w["w"]) for w in words if not w.get("priv") and not w.get("pwarn") and str(w.get("w", "")).strip()][:60]
    speech = " ".join(toks).strip()
    sent = re.split(r"(?<=[.!?。！？])\s+", speech)
    said = sent[0] if sent else ""
    if len(said) > 140: said = said[:140].rsplit(" ", 1)[0] + "…"
    heard = []
    wl = " ".join(why).lower()
    if "laugh" in wl: heard.append("laughing")
    if "scream" in wl or "scare" in wl: heard.append("a scream")
    if "sung" in wl or kind == "singing": heard.append("singing")
    lab = {"gameplay": "gameplay", "reaction": "a reaction", "talking": "talking", "story": "a story", "singing": "a song"}.get(kind, "a moment")
    short = f"A {int(round(dur))}-second {aspect} clip from a VTuber stream: {lab}." if dur else f"A clip from a VTuber stream: {lab}."
    long = short + (f" The streamer says: “{said}”" if said else " There is no clear speech.") + (f" You can hear {' and '.join(heard)}." if heard else "")
    return short, long


# ================================================================ 46  community message draft
def community_message(entries, vod_name="", channel="", game="", fmt="discord", limit=None):
    """A draft message about the clips of a run for your community. fmt 'discord' (messages of up to 2000 characters) or 'x' (a thread, 280 characters each). -> [message, ...]"""
    ents = sorted(entries, key=lambda e: -float(e.get("hype") or 0))[:8]
    if not ents: return []
    icon = lambda e: vcsmart.type_icon(e.get("kind", "")) or "🎬"
    if fmt == "x":
        out = [_trim(f"New clips from {('the ' + game + ' stream') if game else 'the stream'} 🧵👇" + (f" ({channel})" if channel else ""), 280)]
        for i, e in enumerate(ents, 1):
            out.append(_trim(f"{i}/ {icon(e)} {entry_title(e)} — {hms(e.get('start', 0))} in the VOD", 280))
        return out
    head = f"🎬 **Clips from {vod_name or 'the stream'}**" + (f" — {game}" if game else "") + "\n"
    lines = [f"{icon(e)} **{entry_title(e)}**  `{hms(e.get('start', 0))}`  ·  hype {e.get('hype', '-')}" for e in ents]
    foot = "\nWhich one is your favourite? 💖"
    lim = limit or 2000
    msgs, cur = [], head
    for l in lines:
        if len(cur) + len(l) + 1 > lim - len(foot) - 5: msgs.append(cur.rstrip()); cur = ""
        cur += l + "\n"
    msgs.append((cur + foot).rstrip())
    return msgs


# ================================================================ 47  "Maybe" folder for weak clips
def maybe_target(path, hype, below, root=None):
    """The folder a weak clip goes to ('Maybe' next to the clip folder), or None when the clip is good enough. `below` = hype score under which a clip is 'maybe' (0 = never)."""
    try: h = float(hype)
    except (TypeError, ValueError): return None
    if not below or h >= float(below): return None
    folder = os.path.dirname(os.path.abspath(path))
    if os.path.basename(folder).lower() == "maybe": return None
    top = folder
    for _ in range(3):                                           # clips may be in Shorts/<day>/<vod>/ : the Maybe folder sits in Shorts
        if os.path.basename(top) in ("Shorts", "Recaps", "Twitter"): break
        top = os.path.dirname(top)
    else: top = folder
    return os.path.join(top, "Maybe")


def move_clip(path, dest_dir):
    """Move a clip and the files that belong to it. Returns the new path of the clip, or '' when nothing was moved. Never overwrites (a number is added)."""
    if not os.path.isfile(path): return ""
    os.makedirs(dest_dir, exist_ok=True)
    stem, ext = os.path.splitext(os.path.basename(path)); new_stem = stem; k = 2
    while os.path.exists(os.path.join(dest_dir, new_stem + ext)): new_stem = f"{stem} ({k})"; k += 1
    base = os.path.splitext(path)[0]; moved = []
    try:
        for e in (ext,) + tuple(vcouts.SIDE_ENDINGS) + ("_1x1.mp4", "_16x9.mp4", "_4x5.mp4"):
            src = base + e
            if os.path.isfile(src):
                dst = os.path.join(dest_dir, new_stem + e); shutil.move(src, dst); moved.append((src, dst))
    except OSError:
        for a, b in reversed(moved):
            try: shutil.move(b, a)
            except OSError: pass
        return ""
    return os.path.join(dest_dir, new_stem + ext)


# ================================================================ 50  remember length / style / count per game
def game_key(game):
    return re.sub(r"\s+", " ", str(game or "")).strip().lower()[:60]


GAME_KEYS = ("n", "len_min", "len_max", "style", "layout")


def game_put(game, prefs):
    """Remember how many clips, which length range, which style and layout the creator used for a game. Returns True when stored."""
    k = game_key(game)
    if not k: return False
    d = {x: prefs.get(x) for x in GAME_KEYS if prefs.get(x) not in (None, "")}
    if not d: return False
    store = vctools.store_get("game_prefs", {}) or {}
    store[k] = d
    if len(store) > 120: store = dict(list(store.items())[-100:])
    vctools.store_put("game_prefs", store); return True


def game_get(game):
    k = game_key(game)
    if not k: return {}
    d = (vctools.store_get("game_prefs", {}) or {}).get(k)
    return dict(d) if isinstance(d, dict) else {}
