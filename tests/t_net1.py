"""2.3 downloads and updates (vcnet): download options (checked against a real yt-dlp run on a local HLS stream when yt-dlp is installed), update checker with a fake GitHub,
the safe updater: inspection, backup, rollback after a failure, undo, pruning."""
from t3lib import *
import functools, hashlib, http.server, json, threading, time, zipfile, vcnet

FF = paths.FFMPEG
_n, _ok = [0], ok
def ok(c, m):
    if not c: _n[0] += 1
    _ok(bool(c), m)


# ---------------------------------------------------------------- 37 speed limit text
for txt, want in (("2M", "2M"), ("2 MB/s", "2M"), ("500k", "500K"), ("1.5m", "1.5M"), (" 750 KB/s ", "750K"), ("2mib/s", "2M"), ("", ""), ("fast", ""), ("10", ""), ("10K", ""), ("5000M", ""), ("-3M", ""), ("2M; rm -rf /", ""), (None, "")):
    ok(vcnet.parse_rate(txt) == want, f"speed limit {txt!r} -> {vcnet.parse_rate(txt)!r}")

# ---------------------------------------------------------------- 36 range
r = vcnet.parse_range("1:02:30", "1:10:00"); ok(r == (3750.0, 4200.0, ""), f"range both sides {r}")
r = vcnet.parse_range("", "10:00"); ok(r == (None, 600.0, ""), "range: only the end")
r = vcnet.parse_range("1h2m", ""); ok(r == (3720.0, None, ""), "range: only the start")
ok(vcnet.parse_range("", "") == (None, None, "") and vcnet.parse_range(None, None) == (None, None, ""), "range: nothing asked")
r = vcnet.parse_range("20:00", "10:00"); ok(r[0] is None and "later" in r[2], "range: end before start is explained")
r = vcnet.parse_range("abc", "10:00"); ok(r[0] is None and "From" in r[2], "range: nonsense start is explained")
r = vcnet.parse_range("5:00", "x"); ok(r[0] is None and "To" in r[2], "range: nonsense end is explained")
ok(vcnet.parse_range("5:00", "5:00")[2] != "", "range: empty range is refused")

# ---------------------------------------------------------------- 38 cookies file
cd = tempfile.mkdtemp(); good = os.path.join(cd, "cookies.txt")
open(good, "w").write("# Netscape HTTP Cookie File\n.kick.com\tTRUE\t/\tTRUE\t0\tname\tvalue\n")
ok(vcnet.cookie_file_ok(good)[0] is True, "cookies file: Netscape format accepted")
open(os.path.join(cd, "notes.txt"), "w").write("my shopping list: milk")
ok(vcnet.cookie_file_ok(os.path.join(cd, "notes.txt"))[0] is False, "cookies file: an ordinary text file is refused")
open(os.path.join(cd, "huge.txt"), "wb").write(b"# Netscape HTTP Cookie File\n" + b"x" * 5_100_000)
ok(vcnet.cookie_file_ok(os.path.join(cd, "huge.txt"))[0] is False and vcnet.cookie_file_ok(os.path.join(cd, "none.txt"))[0] is False and vcnet.cookie_file_ok("") == (False, "") and vcnet.cookie_file_ok(cd)[0] is False, "cookies file: huge / missing / empty / a folder are refused")
ok(vcnet.cookie_file_ok('"' + good + '"')[0] is True, "cookies file: pasted path in quotes works")
ok("value" not in vcnet.cookie_file_ok(good)[1], "cookies file: contents are never part of a message")

# ---------------------------------------------------------------- yt-dlp arguments
a, n = vcnet.ytdlp_args({})
ok(a == ["--concurrent-fragments", "4"] and n == [], "download args: defaults only ask for 4 parallel pieces")
a, n = vcnet.ytdlp_args(dict(dl_from="1:00:00", dl_to="1:10:00", dl_rate="2M", dl_frags=8, dl_cookie_file=good))
ok(a == ["--download-sections", "*1:00:00-1:10:00", "--limit-rate", "2M", "--concurrent-fragments", "8", "--cookies", good] and len(n) == 2, f"download args: everything set ({a})")
a, _ = vcnet.ytdlp_args(dict(dl_from="30:00")); ok(a[:2] == ["--download-sections", "*0:30:00-inf"], "download args: from here to the end")
a, _ = vcnet.ytdlp_args(dict(dl_to="15:00")); ok(a[:2] == ["--download-sections", "*0:00:00-0:15:00"], "download args: from the start to here")
a, n = vcnet.ytdlp_args(dict(dl_from="9:00", dl_to="5:00", dl_rate="turbo", dl_cookie_file=os.path.join(cd, "none.txt")))
ok("--download-sections" not in a and "--limit-rate" not in a and "--cookies" not in a and len(n) == 3, f"download args: unusable values are left out and explained ({n})")
ok(vcnet.ytdlp_args(dict(dl_frags=99))[0][-1] == "16" and vcnet.ytdlp_args(dict(dl_frags=-3))[0][-1] == "1" and vcnet.ytdlp_args(dict(dl_frags=0))[0][-1] == "4" and vcnet.ytdlp_args(dict(dl_frags="x"))[0][-1] == "4", "download args: parallel pieces kept between 1 and 16")
base = ["yt-dlp", "--no-playlist", "-f", "best", "--concurrent-fragments", "4", "--newline", "--cookies-from-browser", "firefox"]
c1, _ = vcnet.apply_download_options(base, dict(dl_frags=6, dl_cookie_file=good))
ok(c1.count("--concurrent-fragments") == 1 and c1[c1.index("--concurrent-fragments") + 1] == "6" and "--cookies-from-browser" not in c1 and c1[-2:] == ["--cookies", good] and "firefox" not in c1, f"apply options: old fragments replaced, cookies file replaces the browser ({c1})")
c2, _ = vcnet.apply_download_options(base, dict(dl_cookie_file=""))
ok("--cookies-from-browser" in c2 and "firefox" in c2 and "--cookies" not in c2, "apply options: without a cookies file the browser setting stays")
ok(base[5] == "4", "apply options: the original command is not changed")

# ---------------------------------------------------------------- 36 / 37 against a real yt-dlp on a local HLS stream
def have_ytdlp():
    try: return subprocess.run([sys.executable, "-m", "yt_dlp", "--version"], capture_output=True, timeout=60).returncode == 0
    except Exception: return False
if have_ytdlp():
    hd = tempfile.mkdtemp(prefix="hls_")
    subprocess.run([FF, "-y", "-v", "error", "-i", SRC, "-t", "60", "-vf", "scale=320:-2", "-c:v", "libx264", "-preset", "ultrafast", "-b:v", "250k", "-g", "50", "-c:a", "aac", "-b:a", "32k",
                    "-f", "hls", "-hls_time", "4", "-hls_playlist_type", "vod", os.path.join(hd, "vod.m3u8")], check=True, capture_output=True)
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a, **k): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=hd))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/vod.m3u8"
    def dl(extra_opts):
        out = tempfile.mkdtemp(prefix="dl_")
        cmd, notes = vcnet.apply_download_options([sys.executable, "-m", "yt_dlp", "--no-playlist", "-o", os.path.join(out, "%(title)s.%(ext)s"), "--merge-output-format", "mp4", "--quiet", "--no-progress", "--no-colors"], extra_opts)
        cmd = vcnet.name_part(cmd)
        t0 = time.time(); r = subprocess.run(cmd + [url], capture_output=True, text=True, timeout=300)
        files = [os.path.join(out, f) for f in os.listdir(out)]
        d = 0.0
        if files:
            q = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", files[0]], capture_output=True, text=True).stdout.strip()
            d = float(q) if q else 0.0
        return r.returncode, d, time.time() - t0, files
    rc, d_full, t_full, files = dl({})
    ok(rc == 0 and 55 < d_full < 65, f"real yt-dlp: whole stream downloaded ({d_full:.1f} s in {t_full:.1f} s)")
    rc, d_part, _, files = dl(dict(dl_from="0:20", dl_to="0:32"))
    ok(rc == 0 and 10 < d_part < 14.5, f"real yt-dlp: only 0:20-0:32 downloaded ({d_part:.1f} s)")
    ok(len(files) == 1 and "part 0.00.20-0.00.32" in os.path.basename(files[0]), f"real yt-dlp: the part is named in the file name ({[os.path.basename(f) for f in files]})")
    rc, d_tail, _, _ = dl(dict(dl_from="0:50"))
    ok(rc == 0 and 6 < d_tail < 14, f"real yt-dlp: from 0:50 to the end ({d_tail:.1f} s)")
    sz = sum(os.path.getsize(os.path.join(hd, f)) for f in os.listdir(hd))
    lim_k = max(50, int(sz / 1024 / 12))                     # a limit that should make the download take roughly 6 seconds (yt-dlp lets the first moments through)
    rc, d_lim, t_lim, _ = dl(dict(dl_rate=f"{lim_k}K"))
    ok(rc == 0 and t_lim > t_full + 2.5 and t_lim < 40, f"real yt-dlp: a {lim_k}K/s limit slows the download ({t_full:.1f} s -> {t_lim:.1f} s, about {sz / t_lim / 1024:.0f} K/s)")
    srv.shutdown()
else:
    print("PASS (skipped) real yt-dlp checks: yt-dlp is not installed here - pip install yt-dlp to run them")

# ---------------------------------------------------------------- 36 the part goes into the file name
np_ = vcnet.name_part
c0 = ["yt-dlp", "-o", "/x/%(title).80s [%(id)s].%(ext)s", "--download-sections", "*1:02:30-1:10:00"]
ok(np_(c0)[2] == "/x/%(title).80s [%(id)s] part 1.02.30-1.10.00.%(ext)s" and c0[2].endswith("[%(id)s].%(ext)s"), "part naming: the part is in the file name, the input list is not changed")
ok(np_(["yt-dlp", "-o", "/x/%(title)s.%(ext)s", "--download-sections", "*0:20-inf"])[2] == "/x/%(title)s part 0.20-inf.%(ext)s", "part naming: 'to the end' is named too")
ok(np_(["yt-dlp", "-o", "/x/%(title)s.%(ext)s"]) == ["yt-dlp", "-o", "/x/%(title)s.%(ext)s"], "part naming: a whole-VOD command is unchanged")
ok(np_(["yt-dlp", "--download-sections", "*a-b"]) == ["yt-dlp", "--download-sections", "*a-b"] and np_(["yt-dlp", "-o", "x.mp4", "--download-sections", "*1:00-2:00"])[2] == "x.mp4" and np_([]) == [] and np_(["-o"]) == ["-o"], "part naming: odd commands are left alone, nothing raises")

# ---------------------------------------------------------------- 48 version words
pv = vcnet.parse_version
ok(pv("v0.2.3-beta") == ((2, 3, 0), True) and pv("2.3 beta") == ((2, 3, 0), True) and pv("2.3") == ((2, 3, 0), False) and pv("v2.3.1") == ((2, 3, 1), False) and pv("v0.2.2") == ((2, 2, 0), False), "versions: repository tags and app versions read the same way")
ok(pv("no number") == (None, False) and pv("") == (None, False) and pv(None) == (None, False), "versions: no number -> None")
vk = vcnet.version_key
ok(vk("2.3 beta") > vk("2.2") and vk("2.3") > vk("2.3 beta") and vk("v0.2.4-beta") > vk("2.3") and vk("2.3.1") > vk("2.3") and vk("v0.2.2-beta") == vk("2.2 beta") and vk("x") is None, "versions: ordering (a finished 2.3 beats its beta)")

# ---------------------------------------------------------------- 48 update checker with a fake GitHub
def release(tag="v0.2.3-beta", name="VTuber Clipper 2.3 beta", pre=True, assets=None, body="Notes here"):
    return json.dumps(dict(tag_name=tag, name=name, prerelease=pre, body=body, html_url="https://github.com/vtuberemma/vtuber-clipper/releases/tag/" + tag,
                           assets=assets if assets is not None else [dict(name="VTuberClipper_update_2.3_beta.zip", browser_download_url="https://github.com/vtuberemma/vtuber-clipper/releases/download/x/VTuberClipper_update_2.3_beta.zip", size=5_500_000)])).encode()
fake = lambda payload: (lambda url, timeout=8: payload)
r = vcnet.check_update("2.2", True, fetch=fake(release()))
ok(r["status"] == "newer" and r["latest"] == "v0.2.3-beta" and r["asset_name"].startswith("VTuberClipper_update") and r["asset_size"] == 5_500_000 and "newer version" in r["message"] and r["notes"] == "Notes here", f"update check: newer version found ({r['message']})")
ok(vcnet.check_update("2.3", True, fetch=fake(release()))["status"] == "same", "update check: same version")
ok(vcnet.check_update("2.4", False, fetch=fake(release()))["status"] == "older", "update check: you are ahead of the release")
ok(vcnet.check_update("2.3", True, fetch=fake(release("v0.2.3", "VTuber Clipper 2.3", False)))["status"] == "newer", "update check: the finished 2.3 is newer than your 2.3 beta")
ok(vcnet.check_update("2.2", True, fetch=fake(release("v0.2.2-beta", "x")))["status"] == "same", "update check: tag v0.2.2-beta is your 2.2 beta")
ok(vcnet.check_update("2.2", False, fetch=fake(release("v0.2.2-beta", "x")))["status"] == "older", "update check: the beta of 2.2 is older than the finished 2.2")
r = vcnet.check_update("2.2", True, fetch=fake(release(assets=[])))
ok(r["status"] == "newer" and r["asset_url"] == "" and "no update zip" in r["message"], "update check: a release without a zip says so")
bad_assets = [dict(name="update.zip", browser_download_url="http://github.com/x/update.zip"), dict(name="update.zip", browser_download_url="https://evil.example.com/update.zip"),
              dict(name="update.zip", browser_download_url="https://github.com.evil.com/update.zip"), dict(name="notes.txt", browser_download_url="https://github.com/x/notes.txt"),
              dict(name="VTuberClipper_full.zip", browser_download_url="https://github.com/x/full.zip", size=240_000_000)]
r = vcnet.check_update("2.2", True, fetch=fake(release(assets=bad_assets)))
ok(r["asset_url"] == "" and r["status"] == "newer", "update check: zips from untrusted addresses, plain http, text files and the full download are never offered as the update")
good_asset = dict(name="VTuberClipper_update_2.3_beta.zip", browser_download_url="https://github.com/o/r/releases/download/x/u.zip", size=100, digest="sha256:" + "ab" * 32)
r = vcnet.check_update("2.2", True, fetch=fake(release(assets=[good_asset])))
ok(r["sha256"] == "ab" * 32, "update check: checksum taken from the release asset")
r = vcnet.check_update("2.2", True, fetch=fake(release(body="Checksums\nSHA-256: " + "cd" * 32, assets=[dict(good_asset, digest=None)])))
ok(r["sha256"] == "cd" * 32, "update check: checksum taken from the release notes")
for label, f in (("not json", fake(b"<html>rate limited</html>")), ("empty", fake(b"")), ("no tag", fake(b'{"message": "Not Found"}')), ("a list", fake(b"[1,2]"))):
    r = vcnet.check_update("2.2", True, fetch=f); ok(r["status"] == "error" and "Could not check" in r["message"], f"update check: {label} -> a plain message, no crash")
def boom(url, timeout=8): raise OSError("name resolution failed")
r = vcnet.check_update("2.2", True, fetch=boom); ok(r["status"] == "error" and "Could not check" in r["message"] and "name resolution" in r["message"], "update check: no connection -> a plain message")
r = vcnet.check_update("2.2", True, fetch=fake(release("latest", "nightly", False, [])))
ok(r["status"] == "error" and "version number" in r["message"], "update check: a release without a version number")
r = vcnet.check_update("2.2", True, fetch=fake(release("nightly", "VTuber Clipper 2.4 beta", True, [])))
ok(r["status"] == "newer", "update check: version read from the release title when the tag has none")
r = vcnet.check_update("2.2", True, fetch=fake(release(body="x" * 5000)))
ok(len(r["notes"]) <= 1500, "update check: very long release notes are cut")
for url in ("http://api.github.com/x", "https://evil.com/api.github.com", "https://github.com.evil.com/x", "file:///etc/passwd", "ftp://github.com/x", "https://api.github.com.attacker.net/"):
    try: vcnet.default_fetch(url); refused = False
    except ValueError: refused = True
    except Exception: refused = False
    ok(refused, f"fetch refuses {url}")

# ---------------------------------------------------------------- download of the update zip (fake network)
payload = b"PK-fake-zip-bytes"
info = dict(asset_url="https://github.com/o/r/releases/download/x/u.zip", asset_name="Update 2.3 (beta).zip", asset_size=len(payload), sha256=hashlib.sha256(payload).hexdigest())
dd = tempfile.mkdtemp()
p = vcnet.download_update(info, dd, fetch=lambda u, t=0: payload)
ok(os.path.isfile(p) and open(p, "rb").read() == payload and os.path.dirname(p) == dd and " " not in os.path.basename(p) and "(" not in os.path.basename(p), f"download update: saved with a safe file name ({os.path.basename(p)})")
def raises(fn, text):
    try: fn(); return False
    except RuntimeError as e: return text in str(e)
    except Exception: return False
ok(raises(lambda: vcnet.download_update(dict(info, sha256="00" * 32), dd, fetch=lambda u, t=0: payload), "checksum"), "download update: wrong checksum -> refused")
ok(not os.path.exists(os.path.join(dd, "x_wrong.zip")) and len(os.listdir(dd)) == 1, "download update: nothing is saved when it is refused")
ok(raises(lambda: vcnet.download_update(dict(info, asset_url="http://github.com/u.zip"), dd, fetch=lambda u, t=0: payload), "trust"), "download update: plain http refused")
ok(raises(lambda: vcnet.download_update(dict(info, asset_url="https://evil.example.com/u.zip"), dd, fetch=lambda u, t=0: payload), "trust"), "download update: other hosts refused")
ok(raises(lambda: vcnet.download_update(dict(info, asset_size=500_000_000), dd, fetch=lambda u, t=0: payload), "bigger"), "download update: a huge zip is not downloaded")
ok(raises(lambda: vcnet.download_update(info, dd, fetch=lambda u, t=0: b"x" * 81_000_000), "bigger"), "download update: a download that turns out huge is stopped")
def net_down(u, t=0): raise OSError("timed out")
ok(raises(lambda: vcnet.download_update(info, dd, fetch=net_down), "failed"), "download update: a network error becomes a plain message")
ok(vcnet.download_update(dict(info, sha256=""), dd, fetch=lambda u, t=0: payload).endswith(".zip"), "download update: no checksum published -> still works (size and host are checked)")

# ---------------------------------------------------------------- 49 safe updater
APP_SRC = lambda v, extra="": f'VERSION = "{v}"\nBETA = True\n{extra}'
def mkzip(path, files, mode="w"):
    with zipfile.ZipFile(path, mode) as z:
        for n, d in files.items(): z.writestr(n, d)
    return path
def tree(root, backups=False):
    out = {}
    for r, _, fs in os.walk(root):
        for f in fs: out[os.path.relpath(os.path.join(r, f), root).replace(os.sep, "/")] = open(os.path.join(r, f), "rb").read()
    return out if backups else {k: v for k, v in out.items() if not k.startswith("update_backups/")}
def fresh_install():
    root = tempfile.mkdtemp(prefix="inst_")
    touch = lambda rel, data: (os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True), open(os.path.join(root, rel), "wb").write(data))
    touch("app/streamclip_app.py", APP_SRC("2.2").encode()); touch("app/vcmore.py", b"X = 1\n"); touch("app/fonts/Poppins.ttf", b"FONT"); touch("app/presets/mine.json", b"{}")
    touch("run_windows.bat", b"@echo off\n"); touch("bin/ffmpeg.exe", b"EXE")
    return root
GOOD = {"app/streamclip_app.py": APP_SRC("2.3"), "app/vcmore.py": "X = 2\n", "app/vcnew.py": "Y = 1\n", "app/emoji/a.png": b"PNG", "README.txt": "guide", "HOW_TO_UPDATE.txt": "how"}
z_good = mkzip(os.path.join(W_, "good_update.zip"), GOOD)
ins = vcnet.inspect_update(z_good)
ok(ins["ok"] and ins["version"] == "2.3" and ins["beta"] is True and len(ins["files"]) == 6 and ins["problems"] == [], f"inspect: a proper update is accepted ({ins['version']}, {len(ins['files'])} files)")
def bad(label, files, want, mode="w"):
    z = mkzip(os.path.join(W_, "bad_%d.zip" % abs(hash(label))), files, mode); r = vcnet.inspect_update(z)
    ok(not r["ok"] and any(want.lower() in p.lower() for p in r["problems"]), f"inspect: {label} -> refused ({r['problems'][:1]})")
bad("a file outside the app folder (..)", dict(GOOD, **{"../evil.py": "x=1"}), "unsafe")
bad("an absolute path", dict(GOOD, **{"/etc/cron.d/x": "x"}), "unsafe")
bad("a Windows drive path", dict(GOOD, **{"C:/Windows/x.py": "x"}), "unsafe")
bad("a path that climbs out inside the app", dict(GOOD, **{"app/../../evil.py": "x=1"}), "unsafe")
bad("a program file", dict(GOOD, **{"app/run.exe": b"MZ"}), "allowed kind")
bad("a batch file in the app", dict(GOOD, **{"app/go.bat": "del *"}), "allowed kind")
bad("the creator's fonts", dict(GOOD, **{"app/fonts/Poppins.ttf": b"x"}), "not an update file")
bad("the creator's presets", dict(GOOD, **{"app/presets/x.json": "{}"}), "not an update file")
bad("a file next to the app folder", dict(GOOD, **{"bin/ffmpeg.exe": b"x"}), "not an update file")
bad("python code that does not compile", dict(GOOD, **{"app/vcbroken.py": "def x(:\n"}), "would not start")
bad("no streamclip_app.py", {"app/vcmore.py": "X=2\n"}, "not a vtuber clipper update")
bad("no version number", {"app/streamclip_app.py": "x = 1\n"}, "version")
r = vcnet.inspect_update(os.path.join(W_, "nope.zip")); ok(not r["ok"] and "readable" in r["problems"][0], "inspect: missing file")
open(os.path.join(W_, "notzip.zip"), "wb").write(b"this is not a zip"); r = vcnet.inspect_update(os.path.join(W_, "notzip.zip")); ok(not r["ok"], "inspect: not a zip")
open(os.path.join(W_, "empty.zip"), "wb").write(b""); ok(not vcnet.inspect_update(os.path.join(W_, "empty.zip"))["ok"], "inspect: empty file")
ok(not vcnet.inspect_update(mkzip(os.path.join(W_, "emptyzip.zip"), {}))["ok"], "inspect: a zip with nothing in it")
raw = open(z_good, "rb").read(); cut = os.path.join(W_, "cut.zip"); open(cut, "wb").write(raw[:len(raw) // 2]); ok(not vcnet.inspect_update(cut)["ok"], "inspect: a half-downloaded zip is refused")
flip = bytearray(raw); flip[60] ^= 0xFF; cor = os.path.join(W_, "cor.zip"); open(cor, "wb").write(bytes(flip)); ok(not vcnet.inspect_update(cor)["ok"], "inspect: a damaged zip is refused")
big_one = mkzip(os.path.join(W_, "bigone.zip"), dict(GOOD, **{"app/vcbig.py": "#" * (51 * 1000 * 1000)})); ok(not vcnet.inspect_update(big_one)["ok"], "inspect: one enormous file is refused")

# apply: success, backup, undo
root = fresh_install(); before = tree(root)
res = vcnet.apply_update(z_good, root, now=1000)
after = tree(root)
ok(res["ok"] and res["replaced"] == 2 and res["added"] == 4 and res["version"] == "2.3" and "Close and open" in res["message"], f"update: installed ({res['message'][:70]})")
ok(after["app/vcmore.py"] == b"X = 2\n" and after["app/vcnew.py"] == b"Y = 1\n" and after["app/emoji/a.png"] == b"PNG" and after["README.txt"] == b"guide", "update: files replaced and added")
ok(after["app/fonts/Poppins.ttf"] == b"FONT" and after["app/presets/mine.json"] == b"{}" and after["bin/ffmpeg.exe"] == b"EXE" and after["run_windows.bat"] == before["run_windows.bat"], "update: fonts, presets, tools and launcher untouched")
ok(not [k for k in after if k.endswith(".new")], "update: no temporary files left")
bl = vcnet.list_backups(root)
ok(len(bl) == 1 and bl[0]["applied"] and bl[0]["version"] == "2.3" and bl[0]["files"] == 6 and os.path.isfile(os.path.join(bl[0]["path"], "app", "vcmore.py")) and open(os.path.join(bl[0]["path"], "app", "vcmore.py"), "rb").read() == b"X = 1\n", "update: a backup of every replaced file is kept")
ud = vcnet.undo_update(root)
ok(ud["ok"] and tree(root) == before, f"undo: the folder is exactly as it was before ({ud['message'][:60]})")
ok(not vcnet.undo_update(root)["ok"] and "no update to undo" in vcnet.undo_update(root)["message"], "undo: a second undo says there is nothing to undo")
ok(vcnet.list_backups(root) and not vcnet.list_backups(root)[0]["applied"], "undo: the backup is marked as used")
res2 = vcnet.apply_update(z_good, root, now=2000)
ok(res2["ok"] and tree(root)["app/vcmore.py"] == b"X = 2\n", "update: can be installed again after an undo")

# a refused zip changes nothing
root = fresh_install(); before = tree(root)
res = vcnet.apply_update(os.path.join(W_, "bad_%d.zip" % abs(hash("python code that does not compile"))), root)
ok(not res["ok"] and "Not installed" in res["message"] and tree(root) == before and not os.path.exists(os.path.join(root, "update_backups")), "update: a refused zip changes nothing and leaves no backup folder")
res = vcnet.apply_update(os.path.join(W_, "notzip.zip"), root); ok(not res["ok"] and tree(root) == before, "update: not a zip -> nothing changed")

# a failure half way puts everything back
root = fresh_install(); before = tree(root)
os.makedirs(os.path.join(root, "app", "vcnew.py"))                        # a folder where a new file should go: writing it fails
res = vcnet.apply_update(z_good, root, now=3000)
t_after = tree(root)
ok(not res["ok"] and "nothing was changed" in res["message"], f"update: a failure is reported plainly ({res['message'][:70]})")
ok(t_after == before and os.path.isdir(os.path.join(root, "app", "vcnew.py")) and not [k for k in t_after if k.endswith(".new")], "update: after a failure every file is back as it was and no leftovers remain")
ok(not os.path.exists(os.path.join(root, "update_backups", "19700101-000003")) and vcnet.list_backups(root) == [], "update: the unfinished backup is removed")

# pruning
root = fresh_install()
for i in range(5):
    zz = mkzip(os.path.join(W_, f"u{i}.zip"), {"app/streamclip_app.py": APP_SRC(f"2.{3 + i}"), "app/vcmore.py": f"X = {i + 10}\n"})
    assert vcnet.apply_update(zz, root, keep=3, now=10_000 + i * 100)["ok"]
bl = vcnet.list_backups(root)
ok(len(bl) == 3 and [b["version"] for b in bl] == ["2.7", "2.6", "2.5"], f"update: only the newest 3 backups are kept ({[b['version'] for b in bl]})")
ud = vcnet.undo_update(root)
ok(ud["ok"] and open(os.path.join(root, "app", "vcmore.py")).read() == "X = 13\n", "undo: goes back one version at a time")
ok(vcnet.undo_update(root, backup_id="nope")["ok"] is False, "undo: unknown backup id")
ok(vcnet.list_backups(os.path.join(root, "missing")) == [], "backups: no folder -> empty list")

# manifest names are checked on undo (a tampered backup cannot delete files elsewhere)
root = fresh_install(); vcnet.apply_update(z_good, root, now=5000)
bd = vcnet.list_backups(root)[0]["path"]; mf = json.load(open(os.path.join(bd, "manifest.json"))); mf["added"].append("../victim.txt"); mf["replaced"].append("../../victim2.txt")
open(os.path.join(bd, "manifest.json"), "w").write(json.dumps(mf))
victim = os.path.join(os.path.dirname(root), "victim.txt"); open(victim, "w").write("keep me")
vcnet.undo_update(root)
ok(os.path.isfile(victim) and open(victim).read() == "keep me", "undo: names in a damaged backup file can not reach outside the app folder")
os.remove(victim)

print("FAILS:", _n[0])
