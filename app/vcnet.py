"""VTuber Clipper 2.3 - downloads and updates (features 36-38, 48, 49).
 36 download only a part of a VOD        37 download speed limit and parallel pieces       38 cookies file for sub-only VODs
 48 update checker (GitHub releases)     49 safe in-app updater with a backup and an undo

Nothing here talks to the network by itself: the functions that need it take a `fetch` function, so they can be tested with a fake one and the app passes the real one.
The updater only ever writes into the app folder, only accepts the kinds of file an update zip holds, checks that every .py file compiles before it touches anything,
keeps a copy of every file it replaces, and can put everything back."""
import hashlib, json, os, re, shutil, time, urllib.parse, urllib.request, zipfile

import vcmore

# ================================================================ 36-38  download options
RATE_RX = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([kKmM]?)(?:i?[bB](?:/?s(?:ec)?)?)?\s*$")


def parse_rate(text):
    """'2M', '2 MB/s', '500k', '1.5m' -> '2M' / '500K' / '1.5M' (the form yt-dlp wants), or '' for none / not understood / outside 50 KB/s .. 1 GB/s."""
    m = RATE_RX.match(str(text or ""))
    if not m: return ""
    num, unit = float(m.group(1)), (m.group(2) or "").upper()
    bytes_ = num * {"": 1, "K": 1024, "M": 1024 * 1024}[unit]
    if not (50 * 1024 <= bytes_ <= 1024 ** 3): return ""
    s = f"{num:g}"
    return s + (unit or "")


def parse_range(a, b):
    """('1:02:30', '1:10:00') -> (3750.0, 4200.0, '') ; one side may be empty ('from here to the end'). Third value = a plain note when the input was unusable, else ''."""
    ta, tb = vcmore.parse_time(a), vcmore.parse_time(b)
    if str(a or "").strip() and ta is None: return None, None, "“From” is not a time (try 1:02:30 or 90)."
    if str(b or "").strip() and tb is None: return None, None, "“To” is not a time (try 1:10:00 or 4200)."
    if ta is None and tb is None: return None, None, ""
    if ta is not None and tb is not None and tb <= ta + 1: return None, None, "“To” must be later than “From”."
    return ta, tb, ""


def _hms(t):
    t = int(t); return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}"


def cookie_file_ok(path):
    """-> (ok, plain message). A cookies file for yt-dlp is a small text file (the 'Netscape' format that browser extensions export). Its contents are never shown or logged."""
    p = str(path or "").strip().strip('"')
    if not p: return False, ""
    if not os.path.isfile(p): return False, "That cookies file was not found."
    try:
        if os.path.getsize(p) > 5_000_000: return False, "That file is too big to be a cookies file."
        with open(p, "r", encoding="utf-8", errors="replace") as fh: head = fh.read(400)
    except OSError: return False, "That cookies file cannot be read."
    if "Cookie File" not in head and "\t" not in head: return False, "That does not look like a cookies file (the Netscape text format)."
    return True, "Cookies file found."


def ytdlp_args(o):
    """-> (extra yt-dlp arguments, notes). o keys: dl_from, dl_to (times), dl_rate ('2M'), dl_frags (1-16), dl_cookie_file (path). Anything unusable is left out and explained in `notes`."""
    args, notes = [], []
    ta, tb, note = parse_range(o.get("dl_from"), o.get("dl_to"))
    if note: notes.append(note)
    elif ta is not None or tb is not None:
        args += ["--download-sections", f"*{_hms(ta or 0)}-{_hms(tb) if tb is not None else 'inf'}"]
        notes.append(f"Downloading only {_hms(ta or 0)} to {_hms(tb) if tb is not None else 'the end'}.")
    if str(o.get("dl_rate") or "").strip():
        r = parse_rate(o.get("dl_rate"))
        if r: args += ["--limit-rate", r]; notes.append(f"Speed limit {r}/s.")
        else: notes.append("The speed limit was not understood (try 2M or 500K) - no limit is used.")
    try: fr = int(float(o.get("dl_frags") or 4))
    except (TypeError, ValueError, OverflowError): fr = 4
    args += ["--concurrent-fragments", str(min(16, max(1, fr)))]
    ck = str(o.get("dl_cookie_file") or "").strip().strip('"')
    if ck:
        good, msg = cookie_file_ok(ck)
        if good: args += ["--cookies", ck]
        else: notes.append(msg)
    return args, notes


def apply_download_options(cmd, o):
    """The base yt-dlp command (without the address) with the 2.3 options applied: its own '--concurrent-fragments N' is replaced, a valid cookies file replaces
    'cookies from browser'. -> (cmd, notes)."""
    args, notes = ytdlp_args(o)
    out, i = [], 0
    while i < len(cmd):
        if cmd[i] == "--concurrent-fragments": i += 2; continue
        out.append(cmd[i]); i += 1
    if "--cookies" in args and "--cookies-from-browser" in out:
        j = out.index("--cookies-from-browser"); del out[j:j + 2]
    return out + args, notes


def name_part(cmd):
    """When the command downloads only a part (--download-sections *A-B), put the part in the output file name ('... part 1.02.30-1.10.00.mp4') so it is never mistaken for the whole VOD
    (or skipped because a whole-VOD file with the same name is already there). Any other command is returned unchanged."""
    cmd = list(cmd)
    if "--download-sections" not in cmd or "-o" not in cmd: return cmd
    try:
        sec = cmd[cmd.index("--download-sections") + 1]; i = cmd.index("-o") + 1
        m = re.match(r"^\*([\d:.]+)-([\d:.]+|inf)$", sec)
        if not m or not cmd[i].endswith(".%(ext)s"): return cmd
        tag = " part " + m.group(1).replace(":", ".") + "-" + m.group(2).replace(":", ".")
        cmd[i] = cmd[i][:-len(".%(ext)s")] + tag + ".%(ext)s"
    except (IndexError, ValueError): pass
    return cmd


# ================================================================ 48  update checker
OWNER_REPO = "vtuberemma/vtuber-clipper"
RELEASES_URL = f"https://api.github.com/repos/{OWNER_REPO}/releases/latest"
TRUSTED_HOSTS = ("github.com", "api.github.com", "objects.githubusercontent.com", "github-releases.githubusercontent.com", "release-assets.githubusercontent.com")
MAX_UPDATE_MB = 80


def parse_version(text):
    """'v0.2.3-beta' / '2.3 beta' / '2.3' / 'v2.3.1' -> ((2, 3, 1), is_beta); (None, False) when there is no number. A leading 0 ('0.2.3') is the repository's way to write 2.3."""
    s = str(text or "")
    nums = [int(x) for x in re.findall(r"\d+", s)[:4]]
    if not nums: return None, False
    if nums[0] == 0 and len(nums) >= 3: nums = nums[1:]
    nums = (nums + [0, 0, 0])[:3] if len(nums) < 3 else nums[:3]
    return tuple(nums), bool(re.search(r"beta|alpha|rc|preview", s, re.I))


def version_key(text):
    v, beta = parse_version(text)
    return None if v is None else (v, 0 if beta else 1)           # the finished 2.3 is newer than the 2.3 beta


def default_fetch(url, timeout=8):
    """Real network read (bytes). Only https to the places GitHub serves from."""
    u = urllib.parse.urlparse(url)
    if u.scheme != "https" or (u.hostname or "").lower() not in TRUSTED_HOSTS: raise ValueError("untrusted address")
    req = urllib.request.Request(url, headers={"User-Agent": "VTuberClipper-update-check", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r: return r.read(2_000_000)


def check_update(current, current_beta=False, fetch=None, url=RELEASES_URL, timeout=8):
    """Ask GitHub for the newest release. -> dict(status 'newer'|'same'|'older'|'error', current, latest, name, notes, page, asset_url, asset_name, asset_size, sha256, message).
    `fetch(url, timeout) -> bytes` can be replaced (tests). Never raises."""
    cur_txt = f"{current}{' beta' if current_beta else ''}"
    res = dict(status="error", current=cur_txt, latest="", name="", notes="", page="", asset_url="", asset_name="", asset_size=0, sha256="", message="")
    try:
        raw = (fetch or default_fetch)(url, timeout)
        d = json.loads(raw.decode("utf-8", "replace") if isinstance(raw, (bytes, bytearray)) else raw)
        if not isinstance(d, dict) or not d.get("tag_name"): raise ValueError("no release information")
    except Exception as e:
        res["message"] = "Could not check for updates (" + (str(e)[:80] or "no connection") + "). You can try again later."
        return res
    tag = str(d.get("tag_name", "")); res.update(latest=tag, name=str(d.get("name") or tag)[:120], notes=str(d.get("body") or "")[:1500], page=str(d.get("html_url") or "")[:300])
    new_txt = tag + (" beta" if d.get("prerelease") and not re.search(r"beta|alpha|rc|preview", tag + " " + str(d.get("name") or ""), re.I) else "")
    if parse_version(tag)[0] is None: new_txt = tag + " " + str(d.get("name") or "")           # no number in the tag: try the release title
    elif re.search(r"beta|alpha|rc|preview", str(d.get("name") or ""), re.I) and "beta" not in new_txt.lower(): new_txt += " beta"
    cur_k, new_k = version_key(cur_txt), version_key(new_txt)
    if new_k is None or cur_k is None:
        res["message"] = "The newest release has no version number I can read."; return res
    best = None
    for a in d.get("assets") or []:
        name = str(a.get("name") or ""); link = str(a.get("browser_download_url") or "")
        if not name.lower().endswith(".zip") or "update" not in name.lower(): continue
        if urllib.parse.urlparse(link).scheme != "https" or (urllib.parse.urlparse(link).hostname or "").lower() not in TRUSTED_HOSTS: continue
        if best is None: best = a
    if best:
        res.update(asset_url=str(best["browser_download_url"]), asset_name=str(best.get("name") or ""), asset_size=int(best.get("size") or 0))
        dg = str(best.get("digest") or ""); m = re.match(r"sha256:([0-9a-fA-F]{64})$", dg)
        if m: res["sha256"] = m.group(1).lower()
    if not res["sha256"]:
        m = re.search(r"sha-?256[^0-9a-fA-F]{0,12}([0-9a-fA-F]{64})", res["notes"], re.I)
        if m: res["sha256"] = m.group(1).lower()
    if new_k > cur_k:
        res["status"] = "newer"
        res["message"] = f"A newer version is available: {res['name']}." + ("" if res["asset_url"] else " (It has no update zip attached - open the release page to download it.)")
    elif new_k == cur_k: res["status"], res["message"] = "same", "You have the newest version."
    else: res["status"], res["message"] = "older", "You have a newer version than the latest release."
    return res


def download_update(info, dest_dir, fetch=None, timeout=120):
    """Download the update zip named in a check_update() result into `dest_dir`. Checks the size limit and, when the release gives one, the SHA-256. Returns the path; raises RuntimeError with a plain message."""
    url = info.get("asset_url") or ""
    u = urllib.parse.urlparse(url)
    if u.scheme != "https" or (u.hostname or "").lower() not in TRUSTED_HOSTS: raise RuntimeError("This release has no update zip I trust.")
    if info.get("asset_size", 0) > MAX_UPDATE_MB * 1e6: raise RuntimeError("The update zip is bigger than expected - not downloading it.")
    os.makedirs(dest_dir, exist_ok=True)
    name = re.sub(r"[^\w.\-]+", "_", info.get("asset_name") or "update.zip")[:80] or "update.zip"
    path = os.path.join(dest_dir, name)
    try:
        if fetch: data = fetch(url, timeout)
        else:
            req = urllib.request.Request(url, headers={"User-Agent": "VTuberClipper-update-check"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read(MAX_UPDATE_MB * 1_000_000 + 1)
                if r.geturl() and (urllib.parse.urlparse(r.geturl()).hostname or "").lower() not in TRUSTED_HOSTS: raise RuntimeError("The download was sent somewhere I do not trust.")
    except RuntimeError: raise
    except Exception as e: raise RuntimeError("The download failed (" + (str(e)[:80] or "no connection") + ").")
    if len(data) > MAX_UPDATE_MB * 1_000_000: raise RuntimeError("The update zip is bigger than expected - stopped.")
    want = (info.get("sha256") or "").lower()
    if want and hashlib.sha256(data).hexdigest() != want: raise RuntimeError("The downloaded file does not match the checksum of the release - not installing it.")
    with open(path, "wb") as fh: fh.write(data)
    return path


# ================================================================ 49  safe updater
ALLOWED_TOP = ("app/",)
ALLOWED_ROOT_FILES = ("README.txt", "HOW_TO_UPDATE.txt")
ALLOWED_EXT = (".py", ".txt", ".wav", ".png", ".json")
NEVER = ("app/fonts/", "app/presets/")                          # what an update must not touch (the creator's fonts / presets / settings)
MAX_FILE_MB, MAX_TOTAL_MB = 50, 200


def _safe_name(n):
    if not n or n.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", n) or "\x00" in n: return False
    parts = n.replace("\\", "/").split("/")
    return not any(p in ("..", "") for p in parts[:-1] + ([parts[-1]] if parts[-1] else []))


def inspect_update(zip_path):
    """Look at an update zip WITHOUT installing it. -> dict(ok, version, files [(zip name, size)], problems [plain sentences]). It must hold app/streamclip_app.py with a VERSION line, only the kinds of file
    an update holds, nothing outside the app folder, and every .py file has to compile."""
    res = dict(ok=False, version="", beta=False, files=[], problems=[])
    try: z = zipfile.ZipFile(zip_path)
    except (zipfile.BadZipFile, OSError):
        res["problems"].append("That is not a readable zip file."); return res
    with z:
        infos = [i for i in z.infolist() if not i.is_dir()]
        if not infos: res["problems"].append("The zip is empty."); return res
        if sum(i.file_size for i in infos) > MAX_TOTAL_MB * 1e6: res["problems"].append("The zip unpacks to far more than an update should."); return res
        bad = z.testzip()
        if bad: res["problems"].append(f"The zip is damaged ({bad})."); return res
        for i in infos:
            n = i.filename.replace("\\", "/")
            if not _safe_name(n): res["problems"].append(f"Unsafe file name in the zip: {n[:60]}"); continue
            if i.file_size > MAX_FILE_MB * 1e6: res["problems"].append(f"{n} is too big for an update file."); continue
            if n in ALLOWED_ROOT_FILES: res["files"].append((n, i.file_size)); continue
            if not n.startswith(ALLOWED_TOP) or any(n.startswith(x) for x in NEVER): res["problems"].append(f"Not an update file (left alone / not allowed): {n[:60]}"); continue
            if not n.lower().endswith(ALLOWED_EXT): res["problems"].append(f"Not an allowed kind of file: {n[:60]}"); continue
            res["files"].append((n, i.file_size))
            if n.endswith(".py"):
                try: compile(z.read(i).decode("utf-8"), n, "exec")
                except (SyntaxError, UnicodeDecodeError, ValueError) as e: res["problems"].append(f"{n} would not start ({str(e)[:50]}).")
        names = {n for n, _ in res["files"]}
        if "app/streamclip_app.py" not in names: res["problems"].append("This zip has no app/streamclip_app.py, so it is not a VTuber Clipper update.")
        else:
            src = z.read("app/streamclip_app.py").decode("utf-8", "replace")
            m = re.search(r'^VERSION = "([^"]+)"', src, re.M); b = re.search(r"^BETA = (True|False)", src, re.M)
            if m: res["version"] = m.group(1); res["beta"] = bool(b and b.group(1) == "True")
            else: res["problems"].append("The zip has no version number.")
    res["ok"] = not res["problems"]
    return res


def _backup_root(install_root):
    return os.path.join(install_root, "update_backups")


def apply_update(zip_path, install_root, keep=3, now=None):
    """Install an update zip into `install_root` (the folder that holds app/). Order: inspect -> back up every file that will be replaced -> write the new files one by one
    (each written next to its place and renamed over it) -> on any error put everything back. -> dict(ok, message, backup, replaced, added, version)."""
    info = inspect_update(zip_path)
    if not info["ok"]: return dict(ok=False, message="Not installed: " + " ".join(info["problems"][:3]), backup="", replaced=0, added=0, version=info.get("version", ""))
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now or time.time()))
    bdir = os.path.join(_backup_root(install_root), stamp)
    k = 1
    while os.path.exists(bdir): bdir = os.path.join(_backup_root(install_root), f"{stamp}-{k}"); k += 1
    replaced, added, written = [], [], []
    try:
        with zipfile.ZipFile(zip_path) as z:
            for name, _ in info["files"]:
                dest = os.path.join(install_root, *name.split("/"))
                if not os.path.abspath(dest).startswith(os.path.abspath(install_root) + os.sep): raise RuntimeError("unsafe path")
                if os.path.isfile(dest):
                    b = os.path.join(bdir, *name.split("/")); os.makedirs(os.path.dirname(b), exist_ok=True); shutil.copy2(dest, b); replaced.append(name)
                else: added.append(name)
            os.makedirs(bdir, exist_ok=True)
            with open(os.path.join(bdir, "manifest.json"), "w", encoding="utf-8") as fh: json.dump(dict(replaced=replaced, added=added, version=info["version"], made=time.strftime("%Y-%m-%d %H:%M:%S"), applied=False), fh)
            for name, _ in info["files"]:
                dest = os.path.join(install_root, *name.split("/")); os.makedirs(os.path.dirname(dest), exist_ok=True)
                tmp = dest + ".new"
                with open(tmp, "wb") as fh: fh.write(z.read(name))
                os.replace(tmp, dest); written.append(name)
    except Exception as e:
        _rollback(bdir, install_root, replaced, added)
        return dict(ok=False, message="The update could not be installed and nothing was changed (" + str(e)[:80] + ").", backup="", replaced=0, added=0, version=info["version"])
    try:
        with open(os.path.join(bdir, "manifest.json"), "w", encoding="utf-8") as fh: json.dump(dict(replaced=replaced, added=added, version=info["version"], made=time.strftime("%Y-%m-%d %H:%M:%S"), applied=True), fh)
    except OSError: pass
    _prune(install_root, keep)
    return dict(ok=True, message=f"Updated to {info['version']}{' beta' if info['beta'] else ''}. Close and open the app again to use it. (A backup is kept: Tools -> Updates -> Undo.)",
                backup=bdir, replaced=len(replaced), added=len(added), version=info["version"])


def _rollback(bdir, install_root, replaced, added):
    for name in replaced:
        b = os.path.join(bdir, *name.split("/")); dest = os.path.join(install_root, *name.split("/"))
        try:
            if os.path.isfile(b): shutil.copy2(b, dest)
        except OSError: pass
    for name in added:
        try: os.remove(os.path.join(install_root, *name.split("/")))
        except OSError: pass
    for r, _, fs in os.walk(install_root):
        for f in fs:
            if f.endswith(".new"):
                try: os.remove(os.path.join(r, f))
                except OSError: pass
    shutil.rmtree(bdir, ignore_errors=True)


def list_backups(install_root):
    """[dict(id, path, version, made, applied, files)] newest first."""
    out = []
    root = _backup_root(install_root)
    try:
        for n in sorted(os.listdir(root), reverse=True):
            try:
                with open(os.path.join(root, n, "manifest.json"), encoding="utf-8") as fh: m = json.load(fh)
                out.append(dict(id=n, path=os.path.join(root, n), version=m.get("version", ""), made=m.get("made", ""), applied=bool(m.get("applied")), files=len(m.get("replaced", [])) + len(m.get("added", []))))
            except Exception: continue
    except OSError: pass
    return out


def undo_update(install_root, backup_id=None):
    """Put back the files of the newest (or the named) backup and remove the files that update added. -> dict(ok, message)."""
    bl = [b for b in list_backups(install_root) if b["applied"] and (backup_id is None or b["id"] == backup_id)]
    if not bl: return dict(ok=False, message="There is no update to undo.")
    b = bl[0]
    try:
        with open(os.path.join(b["path"], "manifest.json"), encoding="utf-8") as fh: m = json.load(fh)
        for name in m.get("replaced", []):
            if not _safe_name(name): continue
            src = os.path.join(b["path"], *name.split("/")); dest = os.path.join(install_root, *name.split("/"))
            if os.path.isfile(src): os.makedirs(os.path.dirname(dest), exist_ok=True); shutil.copy2(src, dest)
        for name in m.get("added", []):
            if not _safe_name(name): continue
            try: os.remove(os.path.join(install_root, *name.split("/")))
            except OSError: pass
        m["applied"] = False
        with open(os.path.join(b["path"], "manifest.json"), "w", encoding="utf-8") as fh: json.dump(m, fh)
    except Exception as e: return dict(ok=False, message="The undo did not work (" + str(e)[:80] + ").")
    return dict(ok=True, message=f"Went back to the version before ({b['version']} was removed). Close and open the app again.")


def _prune(install_root, keep):
    bl = list_backups(install_root)
    for b in bl[max(1, keep):]:
        shutil.rmtree(b["path"], ignore_errors=True)
