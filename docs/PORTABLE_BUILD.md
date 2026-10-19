# The Windows portable build

The build people download is one folder that runs from anywhere, with no installer:

```
VTuberClipper\
  VTuberClipper.exe      tiny launcher (see below)
  README.txt             = docs/USER_GUIDE.txt
  app\                   = this repo's app\ folder
  bin\                   ffmpeg.exe, yt-dlp.exe, deno.exe
  python\                Python 3.11 for Windows with Tcl/Tk (python.exe, pythonw.exe, python311.dll, DLLs\, Lib\, tcl\)
                         and Lib\site-packages with the packages from requirements-runtime.txt
```

## Putting it together

1. Copy `app/` from this repo.
2. `bin\`: a recent Windows `ffmpeg.exe` build that includes libass (captions are burned in with the `ass` filter), `yt-dlp.exe` (VOD links) and `deno.exe` (the JavaScript runtime yt-dlp uses for YouTube).
3. `python\`: a Python 3.11 for Windows that includes Tcl/Tk (the "embeddable" zip on python.org does **not**; the full installer or a copy of an installed Python does). Install the packages into it, for example  
   `python\python.exe -m pip install -r requirements-runtime.txt`  
   (faster-whisper brings ctranslate2, av, onnxruntime, tokenizers and huggingface_hub with it).
4. Copy `docs/USER_GUIDE.txt` to `README.txt`.
5. The app finds its tools because it puts `..\bin` (next to `app\`) first on its PATH when it starts.

## Making the zip

```
python tools/make_portable_zip.py --runtime C:\path\to\a\previous\VTuberClipper
```

`--runtime` is an existing portable folder that has `python\`, `bin\` and `VTuberClipper.exe` (take it from the last release; those are not in git). The script writes `dist/VTuberClipper_<version>[_beta].zip` with `app\` and `README.txt` taken from this checkout, so the zip always matches what is in git. The version in the name comes from `app/streamclip_app.py`.

## The launcher

`VTuberClipper.exe` is a small Windows program (about 220 KB, built with MinGW) that starts `python\pythonw.exe app\streamclip_app.py` from its own folder and shows *"Could not start. Keep the python, app and bin folders next to this exe."* if one of them is missing. **Its source was not kept, so it is not in this repo.** Until it is rebuilt, take it from a release, or use `run_windows.bat`, which does the same thing.

## Updating an existing install

`python tools/make_update_zip.py` makes a zip that holds only `app\` (code, pictures, sounds, emoji), a README and a HOW_TO_UPDATE; users drag its `app` folder over their own. Settings, saved styles, music, emotes and clips live in the user folder and are not touched.

## Parts for upload limits

If a place only accepts small files, `python tools/split_zip.py dist/VTuberClipper_<version>_beta.zip --out dist/VTuberClipper_<version>_beta_in_parts` cuts the full zip into 28 MiB parts (`.001`, `.002` …) and writes `join_parts.bat`, which glues them back together on Windows and prints the SHA-256 the joined file must have.
