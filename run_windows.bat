@echo off
rem Starts VTuber Clipper straight from this folder.
rem Needs Python 3.11 with Tk, the packages in requirements-runtime.txt, and ffmpeg + yt-dlp in the bin folder (or on your PATH).
cd /d "%~dp0"
if exist "python\pythonw.exe" (
  start "" "python\pythonw.exe" "app\streamclip_app.py"
) else (
  start "" pythonw "app\streamclip_app.py"
)
