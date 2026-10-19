"""Cuts a big zip into numbered parts (for places that only take small files) and writes join_parts.bat, which glues them back
together on Windows and prints the SHA-256 so you can see the joined file is whole.

    python tools/split_zip.py dist/VTuberClipper_2.3_beta.zip --out dist/VTuberClipper_2.3_beta_in_parts [--mib 28]
"""
import argparse, hashlib, os, sys

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("zip")
    ap.add_argument("--out", required=True)
    ap.add_argument("--mib", type=int, default=28, help="size of each part in MiB (default 28)")
    a = ap.parse_args()
    if not os.path.isfile(a.zip): sys.exit(f"no such file: {a.zip}")
    size = a.mib * 1024 * 1024
    name = os.path.basename(a.zip)
    os.makedirs(a.out, exist_ok=True)
    sha = hashlib.sha256(); parts = []
    with open(a.zip, "rb") as f:
        while True:
            chunk = f.read(size)
            if not chunk: break
            sha.update(chunk)
            p = f"{name}.{len(parts) + 1:03d}"
            with open(os.path.join(a.out, p), "wb") as o: o.write(chunk)
            parts.append(p)
    if len(parts) > 999: sys.exit("too many parts - use a bigger --mib")
    nums = " ".join(f"{i + 1:03d}" for i in range(len(parts)))
    plus = "+".join(f'"{p}"' for p in parts)
    bat = [
        "@echo off",
        f"rem Joins the {len(parts)} downloaded parts into {name}.",
        f"rem Put this file and all {len(parts)} parts (.001 to .{len(parts):03d}) in the same folder, then double-click it.",
        'cd /d "%~dp0"',
        f'for %%i in ({nums}) do if not exist "{name}.%%i" (',
        f'  echo Missing part {name}.%%i - download it into this folder first.',
        "  pause", "  exit /b 1", ")",
        f'copy /b {plus} "{name}"',
        "echo.", "echo Checking the joined file...",
        f'certutil -hashfile "{name}" SHA256',
        "echo.", "echo The long code above must be exactly:", f"echo {sha.hexdigest()}",
        f"echo If it is the same, unzip {name} (right click, Extract All) and delete the parts.",
        "pause", ""]
    with open(os.path.join(a.out, "join_parts.bat"), "w", newline="") as o: o.write("\r\n".join(bat))
    print(f"wrote {len(parts)} parts + join_parts.bat in {a.out}\nsha256 {sha.hexdigest()}")

if __name__ == "__main__":
    main()
