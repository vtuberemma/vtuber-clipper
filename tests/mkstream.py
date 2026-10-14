"""Builds a 4-minute synthetic stream with known moments for the 2.2 tests: greeting+scream, gameplay, laugh, singing, storytime. Words are written by hand (no speech-to-text)."""
import sys, os, json, subprocess, wave
import paths
import numpy as np, synth as Y
SR = Y.SR
def place(track, seg, t0):
    i = int(t0 * SR); n = min(len(seg), len(track) - i); track[i:i + n] += seg[:n]
dur = 240
a = np.zeros(dur * SR, np.float32)
words = []
def say(text, t0, t1):
    toks = text.split(); step = (t1 - t0) / max(1, len(toks))
    for k, w in enumerate(toks):
        words.append(dict(w=w, start=round(t0 + k * step, 2), end=round(t0 + k * step + min(.45, step * .85), 2)))
TRUTH = {}
# 0-24: loud greeting, small talk, then a scream at 12
place(a, Y.speech(24, 240, 4200), 0)
say("Hey guys welcome back everyone to the stream.", 0.5, 4.5)
say("Today we are going to try this horror game and it looks really scary.", 5, 11)
place(a, Y.scream(1.4, 16000), 12.0); say("AAAAAAH no way what was that!", 12.1, 14.0)
say("I told you it was scary I am never playing this again.", 14.5, 20)
TRUTH["scream"] = 12.0
# 24-80 gameplay noise with booms, few words
place(a, Y.game(56, 1800), 24)
say("okay push left push left oh no he is behind me I died.", 40, 46); say("clutch clutch we did it gg.", 62, 66)
TRUTH["game"] = (24, 80)
# 80-100 laugh fit
place(a, Y.speech(20, 250, 3000), 80); place(a, Y.laugh(8, 7000), 86)
say("That was so funny I can not breathe.", 82, 85.5)
for k in range(10): words.append(dict(w="hahaha", start=round(86 + k * .7, 2), end=round(86.5 + k * .7, 2)))
TRUTH["laugh"] = (86, 94)
# 100-135 singing
place(a, Y.sing(35, 5500, low=False), 100); place(a, Y.game(35, 300, False), 100)
for k in range(60): words.append(dict(w=["la", "la", "love", "you", "tonight"][k % 5], start=round(100.5 + k * .55, 2), end=round(100.9 + k * .55, 2)))
TRUTH["sing"] = (100, 135)
# 140-200 storytime (calm speech)
place(a, Y.speech(60, 210, 3200), 140)
story = ("So one time I was walking home and I saw a huge dog. It was following me and I thought it wanted to eat me. Then suddenly it ran past me and grabbed my bag. "
         "I told my friend and she laughed so hard. I was so angry because I had my keys in there. We went back and found the bag in the park. "
         "The dog was just sitting there with it. Apparently it belonged to a neighbor who found it funny. And that's why I never walk home alone.")
say(story, 141, 197)
TRUTH["story"] = (140, 200)
# 200-240 more gameplay
place(a, Y.game(40, 1500), 200); say("wow this level is so hard I keep falling.", 210, 214)
a = np.clip(a, -30000, 30000).astype(np.int16)
w = wave.open(paths.FIX + "/stream22.wav", "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(a.tobytes()); w.close()
subprocess.run([paths.FFMPEG, "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc2=s=640x360:r=24:d={dur}", "-i", paths.FIX + "/stream22.wav", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-shortest", paths.FIX + "/stream22.mp4"], check=True)
words.sort(key=lambda w: w["start"])
json.dump(dict(words=words, truth=TRUTH), open(paths.FIX + "/stream22.json", "w"))
print("ok", len(words), "words")
