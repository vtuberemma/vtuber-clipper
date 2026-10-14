import sys, json, os, tempfile
import paths
import numpy as np, vcsmart as M
P = F = 0
def ok(c, m):
    global P, F
    if c: P += 1; print("PASS", m)
    else: F += 1; print("FAIL", m)
def words(text, t0=0.0, wps=2.6, pause=.5):
    out, t = [], t0
    for w in text.split():
        d = 1.0 / wps; out.append(dict(w=w, start=round(t, 3), end=round(t + d * .85, 3))); t += d
        if w[-1] in ".!?": t += pause
    return out
def curves(n, **kw):
    c = {k: np.zeros(n, np.float32) for k in ("laugh", "scream", "sing", "setup", "voiced")}
    for k, (a, b, v) in kw.items(): c[k][a:b] = v
    return c
STORY = ("So one time when I was in school I told my mom that I was sick. Then suddenly she came into my room and saw me eating a whole pizza. "
         "I thought she was going to be so mad but she just sat down and said she skipped school too. Anyway that's why I never lie to my mom anymore.")
GAME = ("Okay push left enemy on the roof reload reload I'm low health heal heal. Dodge the boss ammo is low. Respawn timer is long and the team is dead. "
        "Wipe! Oh no I died to the checkpoint again. Skill issue.")
REACT = "AHHHH! No way! What the! Hahaha oh my god I'm dead! Hahahaha stop! Nooooo!"
TALK = ("Honestly I think this is a weird opinion but personally I believe people always overthink it. Maybe that's just me. Actually the real problem is the question itself "
        "and I don't think anyone really understands the reason, you know, because everyone has a different idea about what is important.")
SING = "la la la la hold the note tonight la la la la"
def run(text, cur=None, n=60, t0=2.0, wps=2.6):
    w = words(text, t0, wps); end = w[-1]["end"]
    marks = M.word_marks(w, n)
    t, conf, st = M.type_for(w, 0, min(n, end + 2), marks, cur or curves(n))
    return t, conf, st, w, marks
t, c, st, w, mk = run(STORY); ok(t == "story", f"story text -> {t} ({c:.2f})")
t, c, st, w, mk = run(GAME, wps=3.0); ok(t == "gameplay", f"gameplay text -> {t} ({c:.2f})")
t, c, st, w, mk = run(REACT, curves(60, laugh=(8, 12, .8), scream=(2, 4, .7)), wps=3.2); ok(t == "reaction", f"reaction text + audio -> {t} ({c:.2f})")
t, c, st, w, mk = run(TALK); ok(t == "talking", f"talking text -> {t} ({c:.2f})")
t, c, st, w, mk = run(SING, curves(60, sing=(1, 20, .95), voiced=(0, 30, .9)), wps=1.2); ok(t == "singing", f"singing audio -> {t} ({c:.2f})")
# an explosion-heavy gameplay with little speech but no singing
t, c, st, w, mk = run("go go go there he is nice shot", curves(60), wps=2); ok(t in ("gameplay", "talking", "reaction"), f"short game chatter is not story/singing ({t})")
# word marks
w = words("hahaha lol AHHHH nooooo that was clutch and I died oof no way let's go", 1.0)
mk = M.word_marks(w, 20)
ok(mk["laugh"].sum() == 2 and mk["scream"].sum() == 2 and mk["win"].sum() >= 1 and mk["fail"].sum() >= 2 and mk["hype"].sum() >= 1, f"word marks laugh={mk['laugh'].sum()} scream={mk['scream'].sum()} win={mk['win'].sum()} fail={mk['fail'].sum()} hype={mk['hype'].sum()}")
ok(M.is_laugh("hahaha") and M.is_laugh("kekw") and M.is_laugh("ㅋㅋㅋ") and M.is_laugh("草") and not M.is_laugh("have") and not M.is_laugh("hello") and not M.is_laugh("hi"), "laugh words")
ok(M.is_scream("aaaaah") and M.is_scream("noooooo") and M.is_scream("ahhh") and not M.is_scream("no") and not M.is_scream("a") and not M.is_scream("ah"), "scream words")
# greeting skip
w = words("Hey guys welcome back to the stream. So today we are going to play the scary game and I already regret it", 10.0)
g = M.greeting_end(w, 10.0); ok(g is not None and 11.0 < g < 14.0, f"greeting skipped (content starts at {g})")
w = words("um so the thing is that the boss just dropped from the ceiling", 5.0)
g = M.greeting_end(w, 5.0); ok(g is not None and abs(g - w[1]["start"]) < .01, f"filler 'um' skipped ({g})")
w = words("The boss just dropped from the ceiling and I screamed", 5.0); ok(M.greeting_end(w, 5.0) is None, "no greeting -> unchanged")
w = words("hello there is a cat on my keyboard right now", 5.0); ok(M.greeting_end(w, 5.0) is None, "'hello there is a cat' is not a greeting")
# story adjust
w = words("blah blah blah. So one time I went to a shop and the owner chased me. Then I ran and fell. Anyway that's why I never go there. And now the next topic is something else entirely.", 0.0, 2.8)
op = next(x for x in w if x["w"] == "So")["start"]; cl = next(x for x in w if x["w"] == "Anyway")["start"]
s2, e2 = M.story_adjust(w, op + 1.0, cl - 1.0, 5, 90)
ok(abs(s2 - (op - .1)) < .7 and e2 > cl + 1.0, f"story snapped to opener {op:.1f}->{s2:.1f} and closer {cl:.1f}->{e2:.1f}")
# payoff end
sc = np.zeros(80, np.float32) + .2; sc[28] = 3.0; sc[29] = 2.5
w = words("a b c d e f g h i j k l m n o p q r. s t u v w x y z a b c d e f g h i j k l m n o p q r s t.", 5.0, 2.0)
e = M.payoff_end(w, 15.0, 60.0, sc, 12.0)
ok(30 < e < 36, f"payoff end {e:.1f} (peak at 29)")
sc2 = np.zeros(80, np.float32) + .2; sc2[56] = 3.0
ok(abs(M.payoff_end(w, 15.0, 60.0, sc2, 12.0) - 60.0) < .01, "payoff end unchanged when the peak is at the end")
# variety
a = words("the dragon boss kept spawning behind me and the dragon fire melted my armor again and again", 0) + words("my armor melted because dragon fire keeps spawning behind the boss", 6)
b = words("yesterday my neighbor adopted three kittens and one of them learned to open the fridge", 20)
ok(M.similar_moments(a + b, 0, 6, 6, 12) and not M.similar_moments(a + b, 0, 6, 20, 27), "variety: same topic similar, different topic not")
# smart length
lo, hi = M.smart_range("story", 25, 45); ok((lo, hi) == (35, 60), f"smart length story {lo}-{hi}")
lo, hi = M.smart_range("reaction", 25, 45); ok(hi <= 30 and lo >= 10, f"smart length reaction {lo}-{hi}")
# reaction events
cur = curves(40, laugh=(10, 13, .9), scream=(25, 27, .8)); mk = {k: np.zeros(40, np.float32) for k in ("fail", "win", "scare", "cute", "rage", "hype")}; mk["fail"][18] = 1
ev = M.reaction_events([], 5.0, 35.0, mk, cur)
ok(len(ev) >= 2 and all(1.0 <= t <= 29 for t, k in ev) and {"laugh", "scream"} <= {k for _, k in ev}, f"reaction events {ev}")
# reasons
rs = M.reasons(words(STORY, 1.0), 0, 20, M.word_marks(words(STORY, 1.0), 40), curves(40, laugh=(8, 10, .9)), None)
ok(any("Laughing" in r for r in rs) and any("Story" in r for r in rs), f"reasons {rs}")
# chat
tw = json.dumps({"comments": [{"content_offset_seconds": 10 + i * .1, "message": {"body": "KEKW LUL"}} for i in range(60)] + [{"content_offset_seconds": 100 + i * 5, "message": {"body": "hi"}} for i in range(10)]})
m = M.parse_chat(tw); ok(len(m) == 70 and m[0][0] == 10.0, f"twitch json chat {len(m)}")
cc = M.chat_curve(m, 200); ok(cc[10:16].max() > .8 and cc[100:120].max() < .5 and cc.max() <= 1.0, f"chat curve busy moment {cc[10:16].max():.2f} vs quiet {cc[100:120].max():.2f}")
yt = "\n".join(json.dumps({"replayChatItemAction": {"videoOffsetTimeMsec": str(30000 + i * 200), "actions": [{"addChatItemAction": {"item": {"liveChatTextMessageRenderer": {"message": {"runs": [{"text": "lol"}]}}}}}]}}) for i in range(40))
m = M.parse_chat(yt); ok(len(m) == 40 and abs(m[0][0] - 30.0) < .01, f"youtube chat jsonl {len(m)}")
txt = "\n".join(f"[0:01:{i:02d}] user{i}: nice play" for i in range(30)) + "\n[1:02:03] bob: hello\n"
m = M.parse_chat(txt); ok(len(m) == 31 and m[-1][0] == 3723, f"text chat lines {len(m)} last={m[-1][0]}")
ok(M.parse_chat("") == [] and M.parse_chat("{bad json") == [], "bad chat files give nothing")
d = tempfile.mkdtemp(); v = os.path.join(d, "vod.mp4"); open(v, "w").write("x"); open(os.path.join(d, "vod.chat.json"), "w").write(tw)
ok(M.find_chat_file(v).endswith("vod.chat.json"), "chat file found next to the video")
cv, nmsg = M.load_chat(M.find_chat_file(v), 300); ok(cv is not None and nmsg == 70, "chat loaded")
# taste
led = [dict(kind="story", dur=40, fav=True), dict(kind="story", dur=44, posted=True), dict(kind="story", dur=36, fav=True), dict(kind="gameplay", dur=22, deleted=True), dict(kind="gameplay", dur=20, deleted=True)]
t = M.taste(led); ok(t and 36 <= t["len_med"] <= 44 and t["kinds"]["story"] > 1.0 and t["kinds"]["gameplay"] < 1.0, f"taste {t}")
ok(M.taste(led[:2]) is None, "taste needs 3 kept clips")
lo, hi = M.taste_range(t, 25, 45); ok(25 < lo < 40 < hi <= 90, f"taste range {lo:.0f}-{hi:.0f}")
ok("40" in M.taste_text(t) or "36" in M.taste_text(t) or "story" in M.taste_text(t).lower(), M.taste_text(t))
ok(all(M.hook_for(k, i) for k in M.TYPES for i in range(7)), "hooks for every type")
print("PASS", P, "FAIL", F)
