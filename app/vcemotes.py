"""Chibi emotes for story time.

The program READS what is being said, finds the feeling of every sentence ("and I just started crying" -> cry,
"I was NOT scared" -> nothing, "hahaha" -> laughing, a long silence -> blank stare ...) and shows the matching picture of
your model for as long as you talk about that feeling. Nothing is sent anywhere: it is all done on your PC with word and
phrase lists you can extend, and you can check / change the plan before a video is made.

The pictures are YOURS: they live in the folder "VTuberClipper Emotes" in your user folder, where "Add pictures..." copies them.
The app ships with no chibi pictures of its own. (STARTER_DIR below is a switch for tests only: it is empty in the real app, so old
pictures left in app/emotes by an earlier update are never used.)"""
import json, math, os, random, re, shutil, subprocess, threading

HOME = os.path.expanduser("~")
APP = os.path.dirname(os.path.abspath(__file__))
STARTER_DIR = ""            # no starter pictures any more (kept so tests can point it at a folder of fixtures)
USER_DIR = os.path.join(HOME, "VTuberClipper Emotes")
CACHE_DIR = os.path.join(HOME, ".vtuberclipper_cache", "emotes")
META = "emotes.json"
EXT = (".png", ".webp", ".gif")
LEVELS = {  # how many pictures: per minute of video, the shortest gap between two (seconds), and how sure the program must be (score)
    "few": dict(label="Only the big moments", rate=3.0, gap=5.0, thr=3.0),
    "normal": dict(label="Balanced", rate=6.0, gap=3.2, thr=2.0),
    "lots": dict(label="Lots of reactions", rate=10.0, gap=2.2, thr=1.4)}
POSITIONS = {"auto": "Left and right, taking turns", "left": "Always on the left", "right": "Always on the right", "top": "Above the picture's middle (top)"}
REACTIONS = ("shocked", "laughing", "celebrating", "fear", "dead", "cool", "angry")   # used for loud moments when nothing was said that fits

# ---------------------------------------------------------------- the feelings and the words that show them
# key: (label, strong cues (3 points) | normal cues (2) | mild cues (1)). Cues are words or phrases (no apostrophes needed), separated by commas.
# A mild cue alone is never enough on "Balanced"; two of them in one sentence are. The first feeling that lists a cue keeps it.
EMO = {
    "fear": ("Fear", """terrified, terrifying, petrified, jumpscare, jumpscared, jump scare, freaking out, freaked out, freaks me out, scared to death, scared me,
        so scared, im so scared, oh no, oh god, nightmare, im not okay, heart stopped, heart dropped, help me, scream, screamed, screaming, shrieked|
        scared, scary, afraid, fear, horror, creepy, creeped out, panic, panicking, panicked, spooked, spooky, haunted, yikes, eek, uh oh, trembling, shaking, shivering,
        sweating, anxiety, anxious, nervous, terror, trapped, danger, dangerous, monster, behind me, footsteps, followed me, heart pounding, heart was pounding, heart racing|
        worried, worry, worrying, uneasy, creepy, alone, midnight, noise, careful, hide, run, dark"""),
    "angry": ("Angry", """furious, rage quit, ragequit, raging, so mad, so angry, livid, how dare, pissed off, fed up, shut up, i hate this, i hate it, losing my mind, lost my temper,
        infuriating, so annoying, enraged, outraged|
        angry, mad, rage, hate, hated, hates, pissed, annoyed, annoying, irritated, irritating, triggered, tilted, salty, toxic, yelled, yelling, cursed, cursing, argued, argument,
        stop it, unacceptable, furiously, grr, ugh, frustrated, frustrating, frustration, rude, betrayed, betrayal, fuming, seething|
        damn, dammit, crap, hell, bullshit, bs, unfair, upset, bothered, grumpy, cranky, complain, complaining, scolded, shouted, shout, fight, fought, im done"""),
    "celebrating": ("Celebrating", """lets go, lets gooo, lets goooo, we did it, i did it, we won, i won, first place, victory royale, new record, personal best, congratulations, congrats,
        celebrate, celebrating, celebration, yay, yayyy, woohoo, hooray, yippee, finally did it, birthday, party time, pog, poggers, hit the jackpot|
        win, won, winner, winning, victory, champion, champions, achievement, achieved, accomplished, milestone, level up, promoted, promotion, passed, graduated, graduation,
        party, cheers, confetti, success, successful, jackpot, prize, trophy, record, number one, excited, excitement, hyped|
        finally, happy, proud, thank you so much, thanks everyone, thank you all, yes, yess"""),
    "laughing": ("Laughing", """haha, hahaha, hahahaha, ha ha ha, hehe, lol, lmao, lmfao, rofl, kekw, lul, lulw, cracking up, cracked up, crying laughing, dying laughing,
        cant stop laughing, couldnt stop laughing, died laughing, rolling on the floor, wheezing, im wheezing, hilarious, so funny, too funny, thats funny, funniest,
        laughed so hard, laughing so hard, i was laughing, cant breathe laughing|
        funny, laugh, laughing, laughed, laughs, giggle, giggled, giggling, giggles, joke, jokes, joking, comedy, comedic, humor, humour, amusing, goofy, snort, snorted, chuckle,
        chuckled, ahaha, ahahaha, bahaha, ha ha|
        prank, pranked, meme, memes, roast, roasted, teasing, teased, cackle, cackled"""),
    "cry": ("Crying", """crying, cried, bawling, sobbing, sobbed, ugly cry, burst into tears, in tears, tears came, broke down, broke my heart, breaks my heart, heartbroken,
        devastated, cant stop crying, couldnt stop crying, cried myself, started crying, almost cried, nearly cried, tears|
        cry, cries, sob, sobs, sad, sadly, saddest, depressed, depressing, depression, grief, grieving, mourning, mourn, lonely, loneliness, miss him, miss her, miss them, i miss,
        heartbreak, heartbreaking, tragic, tragedy, sniff, sniffle, weeping, wept, waah, boohoo, painful, it hurt, hurt me, passed away, funeral, goodbye forever|
        sorry, unhappy, hurt, hurting, disappointed, disappointing, miss, missing, ouch, poor, unfortunately, sadness, tear, teary, emotional, moved, lost my"""),
    "dead": ("Dead", """im dead, im literally dead, i died, i literally died, kill me, killed me, that killed me, i want to die, wanna die, i could die, im deceased, deceased,
        rest in peace, rip, dead inside, bury me, send help, unalive, ded, im ded, skull, dying inside, i am dead, soul left my body, im gone, i cant even|
        dead, died, dies, dying, death, die, ghost, ghosts, ghosted, haunt, grave, coffin, passed out, fainted, faint, lifeless, tombstone, corpse, buried, bury, funeral|
        gone, finished, cant breathe, cant even, killed, over for me"""),
    "cool": ("Cool", """so cool, thats cool, thats so cool, like a boss, no big deal, deal with it, easy peasy, i am him, im him, im the goat, im that guy, smooth operator, looked so cool,
        felt so cool, looking cool, badass, bad ass, swagger, nailed it, i nailed it|
        cool, awesome, sick, epic, legend, legendary, goat, goated, smooth, chill, chilled, drip, swag, stylish, slick, flex, flexing, handled, clutch, effortless, effortlessly,
        killer, sunglasses, shades, hero, heroic, mvp, skilled, skillful, pro|
        nice, great, impressive, impressed, smart, clever, perfect, perfectly, smoothly, calm, calmly, confident, confidently"""),
    "clown": ("Clown", """clown, clowns, clowned, clowning, clown moment, clown behavior, clown behaviour, im a clown, i felt like a clown, made a fool, fool of myself, bozo, circus,
        honk, honk honk, jokes on me, joke is on me, embarrassed myself, i embarrassed myself, humiliated, humiliating|
        fool, foolish, embarrassing, embarrassed, cringe, cringey, awkward, fiasco, shenanigans, ridiculous, absurd, nonsense, tomfoolery, whole circus|
        silly, goofy, weird, awkwardly, blunder, failure, red flag"""),
    "dumb": ("Dumb", """so dumb, so stupid, im an idiot, im so dumb, im stupid, i forgot, i totally forgot, my brain, brain rot, braindead, brain dead, no brain, what was i thinking,
        i didnt think, derp, doofus, brain cells, one brain cell, zero brain cells, cant read, i cant read, skill issue, my bad, face palm, facepalm|
        dumb, stupid, idiot, idiotic, dummy, dumbass, silly, moron, moronic, brainless, clueless, oblivious, forgot, forget, forgetting, mistake, oops, whoops, mess up, messed up,
        screwed up, derpy, duh, didnt notice, didnt realize, didnt see, accidentally, accident, by accident, misread, mixed up, wrong button, wrong one|
        mistaken, tripped, fell, tripped over, forgetful"""),
    "gaming": ("Gaming", """gaming, gamer, gamers, speedrun, speedrunning, speedrunner, one more game, just one more, ranked, matchmaking, game over, respawn, boss fight, final boss,
        play games, playing games, video game, video games, controller, gamepad, game night, gameplay, tryhard, noob|
        lobby, quest, quests, grind, grinding, loot, steam, console, playstation, xbox, nintendo, minecraft, fortnite, valorant, roblox, apex, zelda, mario, pokemon, rpg, fps, mmo,
        dungeon, raid, raids, esports, queue, queued, level, levels|
        game, games, play, played, playing, player, players, boss, bosses, win, lose, score, points, skill, mission, missions, tutorial, patch, update, server, servers, lag, laggy,
        lagging, ping, stream"""),
    "gun": ("Gun", """shoot you, shot me, headshot, head shot, point a gun, pointed a gun, hands up, stick up, stickup, pew pew, bang bang, sniped, sniper, pistol, rifle, shotgun,
        machine gun, locked and loaded, gunfire, gunshot, with a gun, my gun, his gun, her gun|
        gun, guns, shoot, shoots, shooting, shot, shots, bang, pew, weapon, weapons, ammo, reload, reloading, trigger, bullet, bullets, armed, aim, aimed, aiming, aimbot, sniping, snipe,
        camper, camping, spraying, grenade, killing spree, killstreak, awp, deagle, glock, bounty|
        kill, kills, killing, war, battle, enemy, enemies, target"""),
    "yandere": ("Yandere / knife", """knife, knives, stab, stabbed, stabbing, stabs, yandere, psycho, psychopath, murder, murdered, murderer, murderous, kill you, ill kill you, i will kill you,
        ill find you, i will find you, love you to death, obsessed with you, mine forever, youre mine, you are mine, only mine, stalker, stalking, stalked, cut you, slice, slashing,
        bloody, blood, evil smile, creepy smile, crazy ex, jealous|
        obsessed, obsession, obsessive, jealousy, possessive, stalk, unhinged, lunatic, sinister, evil, villain, scheme, scheming, revenge, vengeance, backstab, backstabbed,
        backstabbing, knifed, blade, dagger, sword, sharp|
        mine, only me, never let go, watching you, always watching, follow you, followed you, darkness, madness, cant live without"""),
    "shocked": ("Shocked", """oh my god, oh my gosh, oh my goodness, omg, omfg, no way, no freaking way, no fucking way, what the, what the hell, what the heck, what the fuck, wtf, wth, wait what,
        cant believe, i cant believe, i couldnt believe, couldnt believe, unbelievable, mind blown, mindblown, jaw dropped, jaw drop, speechless, shocked, shocking, gasped, gasp,
        plot twist, out of nowhere, all of a sudden, are you kidding, are you serious, you cant be serious|
        wow, whoa, woah, whoaa, surprised, surprise, surprising, suddenly, unexpected, unexpectedly, insane, crazy, unreal, incredible, impossible, turns out, turned out, guess what,
        shook, stunned, astonished, amazed, bruh, what happened, what is happening, whats happening|
        what, really, seriously, for real, no, wait, hold on, dude, sudden, amazing, nooo, noo"""),
    "fine": ("This is fine", """this is fine, its fine, its all fine, everything is fine, everythings fine, im fine, i am fine, im totally fine, im okay, all good, its all good, all is well,
        no problem, nothing to see here, under control, everything is under control, its okay, its not that bad, could be worse, dumpster fire, on fire, house on fire,
        everything is on fire, burning down, burned down, falling apart, total chaos, coping, cope, copium, in denial, denial|
        chaos, chaotic, disaster, catastrophe, mess, trainwreck, train wreck, doomed, hopeless, collapse, collapsing, burning, burnt, flames, smoke|
        fine, okay, alright, whatever, nevermind, never mind, fire, burn, burned, crashed, crash, exploded, explosion"""),
    "tired": ("Tired", """so tired, im tired, im exhausted, im so tired, exhausted, exhausting, sleep deprived, no sleep, didnt sleep, havent slept, couldnt sleep, cant sleep, stayed up,
        stay up, all night, all nighter, pulled an all nighter, burnt out, burned out, burnout, need coffee, need a nap, need sleep, need a break, so sleepy, falling asleep,
        fell asleep, 3am, 4am, 5am, insomnia, overworked, zzz, yawn, yawning, yawned, crunch time|
        tired, sleepy, sleep, sleeping, slept, nap, napping, napped, drained, drowsy, weary, worn out, wiped out, caffeine, coffee, espresso, energy drink, late night, late nights,
        homework, laptop, deadline, deadlines, overtime, studying, exam, exams, finals|
        work, working, worked, job, office, meeting, meetings, morning, mornings, early, late, school, class, project, assignment, study, wake up, woke up"""),
    "trash": ("Trash", """im trash, im garbage, i am trash, i suck, im so bad, im terrible, im the worst, im useless, im worthless, total trash, complete trash, absolute garbage,
        pure garbage, thrown away, throw it away, threw it away, throw away, in the trash, trash can, garbage can, trashcan, take out the trash, took out the trash, worthless,
        useless, im a loser, i lost again, lost again, i keep losing, cant do anything right, im bad at, so bad at, i give up|
        trash, garbage, rubbish, terrible, awful, horrible, worst, suck, sucks, sucked, sucking, scrub, failure, fail, failed, failing, fails, loser, pathetic, pitiful, waste, wasted,
        dumpster, disgusting|
        bad, badly, lost, lose, losing, lame, gross, junk, bin, litter, newbie"""),
    "confused": ("Confused", """i dont understand, i dont get it, i dont know what, no idea what, makes no sense, doesnt make sense, doesnt make any sense, what do you mean, what is going on,
        whats going on, im so confused, im confused, im lost, i have no idea, no clue|
        confused, confusing, confusion, confuse, huh, puzzled, puzzling, perplexed, baffled, bewildered, unclear, no idea, idk, i dunno, not sure, mysterious, mystery|
        why, how, weird, strange, odd, lost, unsure, dont know, whats"""),
    "thinking": ("Thinking", """let me think, lets think, let me see, lets see, hmm, hmmm, hmmmm, hm, thinking about it, thinking about this, i wonder, i was wondering, what if, think about it,
        big brain, galaxy brain, let me remember, trying to remember, thinking, ponder, pondering, contemplating, brainstorm|
        wonder, wondering, theory, theories, consider, considering, figure out, figuring out, puzzle, riddle, strategy, remember, curious, hypothesis, calculating, calculate|
        think, thought, maybe, perhaps, probably, possibly, guess, idea, plan, planning"""),
    "blank": ("Blank stare", """blank stare, blankly, stared blankly, just stared, i just stood there, just standing there, brain froze, brain stopped, no words, lost for words,
        at a loss for words, nothing came out, i had nothing, numb, felt nothing, feel nothing, staring into space, spaced out, zoned out, zoning out, dissociating, dissociated,
        awkward silence|
        blank, stare, stared, staring, stares, froze, i froze, silence, silent, no response, no reaction, ignored, ignoring, unbothered, expressionless, emotionless, deadpan, poker face, straight face,
        unamused, unimpressed, meh, bored, boring, empty, void|
        nothing, quiet, still, blink, blinked, stood, standing, waiting, waited"""),
    # feelings below have no starter picture - add yours and the program starts using them
    "love": ("In love", """i love you, love you, in love, so in love, my heart, heart eyes, my crush, crush on, falling in love, fell in love, adore, adorable, so cute, too cute, soulmate|
        love, loved, loves, loving, cute, crush, kiss, kisses, kissed, hug, hugs, hugged, cuddle, cuddles, romantic, romance, wholesome, sweet, aww, awww, darling, babe|
        heart, hearts, valentine, date, dating, boyfriend, girlfriend, together"""),
    "hungry": ("Hungry", """so hungry, im hungry, im starving, starving, so good i cried, delicious, yummy, tasty, mouth watering, snack time, food coma|
        hungry, hunger, eat, ate, eating, eats, food, foods, pizza, ramen, sushi, burger, burgers, cake, dessert, snack, snacks, breakfast, lunch, dinner, cook, cooked, cooking, bake, baked, noodles|
        fries, chicken, rice, tea, chocolate, candy, sweet, sweets, meal"""),
    "sus": ("Suspicious", """sus, so sus, very sus, kinda sus, suspicious, suspect, fishy, something is off, something was off, something felt off, im watching you, i dont trust, dont trust,
        sketchy, shady, impostor, imposter, among us|
        weird, odd, strange, lying, lied, liar, lies, sneaky, secret, secrets, hiding, hid, hidden, spy, spying, detective|
        maybe, hmm, perhaps, doubt, doubtful, really"""),
    "shy": ("Shy / blushing", """so embarrassed, im embarrassed, im so embarrassed, blushing, i blushed, face turned red, turned red, red face, im shy, so shy, shy, bashful, flustered, flushed,
        butterflies, my face is hot|
        blush, embarrassment, awkward, awkwardly, nervous, cringe, shyly, compliment, complimented, confession, confess, confessed|
        cute, sweet, kind, nice"""),
    "hello": ("Hello", """hello everyone, hi everyone, hey everyone, hello chat, hi chat, hey chat, welcome back, welcome to the stream, welcome in, good morning, good evening, good afternoon,
        hello hello|
        hello, hi, hey, hiya, heya, greetings, welcome, howdy|
        morning, evening, afternoon"""),
    "bye": ("Goodbye", """goodbye everyone, bye everyone, see you next time, see you tomorrow, see you later, see you guys, until next time, thanks for watching, thank you for watching,
        thats all for today, thats it for today, good night everyone, goodnight everyone, signing off, ending the stream, end of the stream, gotta go, got to go|
        bye, goodbye, goodnight, farewell, later, ciao, byebye, byebyes, adios|
        night, leaving, leave, end"""),
    "thanks": ("Thank you", """thank you so much, thanks so much, thank you everyone, thanks everyone, thank you all, thanks guys, thank you guys, thank you chat, thanks chat,
        i appreciate you, i appreciate it, so grateful, im so grateful, much appreciated, big thanks|
        thank you, thanks, thx, ty, thankful, grateful, gratitude, appreciate, appreciated, appreciation, blessed, blessing|
        subs, subscribers, followers, donation, donations, gifted, gift, support, supporting, supporter, supporters"""),
    "smug": ("Smug / evil", """mwahaha, muahaha, bwahaha, evil laugh, evil plan, my evil plan, as planned, according to plan, exactly as planned, gotcha, got you, i win, you fell for it,
        fell for it, trapped you, got them, got em, caught you, outsmarted, ha got you|
        smirk, smirking, smug, scheme, schemed, plot, plotting, sneaky, trick, tricked, trolled, troll, trolling, revenge, villain, evil|
        heh, hehe, ehe, ehehe, clever, devious, mischief, mischievous, sly"""),
}
CORE = ("fear", "angry", "confused", "blank", "thinking", "cool", "dead", "cry", "dumb", "gun", "gaming", "laughing", "shocked", "tired", "celebrating", "clown",
        "fine", "trash", "yandere")          # the ones the app promises; everything else in EMO is a bonus feeling
HIGH = frozenset(("angry", "shocked", "fear", "celebrating", "laughing", "dead", "cool"))   # feelings that are louder when shouted
COOL = {"gaming": 30.0, "fine": 14.0, "trash": 14.0, "cool": 14.0, "hello": 40.0, "bye": 40.0, "thanks": 20.0, "thinking": 12.0, "confused": 12.0}   # the same feeling is not shown again within this many seconds (default 9)
MOTION = {"angry": "shake", "fear": "shake", "shocked": "jump", "laughing": "bounce", "celebrating": "bounce", "dead": "sink", "cry": "sway", "tired": "sway", "blank": "still",
          "cool": "slide", "yandere": "creep", "fine": "sway", "thinking": "sway", "smug": "slide"}   # how the picture moves (the engine animates it)
ALIAS = {"sad": "cry", "crying": "cry", "tears": "cry", "mad": "angry", "rage": "angry", "scared": "fear", "scary": "fear", "afraid": "fear", "terrified": "fear", "surprised": "shocked",
         "surprise": "shocked", "shock": "shocked", "wow": "shocked", "omg": "shocked", "laugh": "laughing", "haha": "laughing", "lol": "laughing", "lmao": "laughing", "happy": "celebrating",
         "party": "celebrating", "win": "celebrating", "celebrate": "celebrating", "yay": "celebrating", "sleepy": "tired", "sleep": "tired", "coffee": "tired", "game": "gaming", "gamer": "gaming",
         "controller": "gaming", "think": "thinking", "hmm": "thinking", "confusion": "confused", "huh": "confused", "question": "confused", "stare": "blank", "blankstare": "blank", "speechless": "blank",
         "ghost": "dead", "skull": "dead", "rip": "dead", "death": "dead", "idiot": "dumb", "stupid": "dumb", "derp": "dumb", "dum": "dumb", "knife": "yandere", "stab": "yandere", "psycho": "yandere",
         "shades": "cool", "sunglasses": "cool", "garbage": "trash", "bin": "trash", "pistol": "gun", "shoot": "gun", "isfine": "fine", "thisisfine": "fine", "fire": "fine", "okay": "fine",
         "clowns": "clown", "circus": "clown", "heart": "love", "kiss": "love", "food": "hungry", "eat": "hungry", "suspicious": "sus", "blush": "shy", "embarrassed": "shy", "wave": "hello",
         "hi": "hello", "goodbye": "bye", "thank": "thanks", "thankyou": "thanks", "evil": "smug", "smirk": "smug"}
# words that make a feeling stronger / cancel it
INTENS = frozenset("so very really literally absolutely completely super extremely totally fully genuinely truly incredibly insanely soo sooo too such".split())
NEG = frozenset("not no never dont didnt wasnt isnt cant cannot wont wouldnt couldnt arent werent aint hardly barely nobody nothing without neither nor doesnt havent hasnt hadnt shouldnt".split())
LAUGH_RE = re.compile(r"^(?:a?ha){2,}h?$|^(?:he){2,}h?$|^l+o+l+$|^(?:lo){2,}l*$|^lm+a+o+$|^k+e+k+w*$|^(?:ah){2,}h?$")

_lock = threading.Lock()
_used = {}                               # picture path -> how many times it was shown in this run, so several pictures of one feeling take turns


def reset_rotation():
    with _lock: _used.clear()


# ---------------------------------------------------------------- reading the story
def tok(w):
    """One spoken word -> lower case letters/numbers only, no apostrophes or punctuation ("I'm" -> "im")."""
    return re.sub(r"[^\w]", "", str(w).lower().replace("’", "").replace("'", "").replace("_", ""))


def _norm_phrase(p):
    return tuple(t for t in (tok(x) for x in str(p).replace("\n", " ").split()) if t)


def parse_cues(text):
    """'a b, c, d' -> [('a','b'), ('c',), ('d',)] (also splits on ; and new lines)."""
    return [t for t in (_norm_phrase(x) for x in re.split(r"[,;\n]+", str(text or ""))) if t]


_lex_cache = {}


def lexicon(extra_words=None, custom=None):
    """-> (table {first token: [(phrase tuple, emotion, weight)] longest first}, labels {key: label}).
    extra_words {key: 'my words, more'} adds your own cues (worth 3 points each); custom {key: {'label':..., 'words':...}} adds your own feelings."""
    ck = json.dumps([extra_words or {}, custom or {}], sort_keys=True)
    if ck in _lex_cache: return _lex_cache[ck]
    entries, labels = [], {}                                     # (priority, phrase, feeling, points)
    for k, (lab, groups) in EMO.items():
        labels[k] = lab
        for pts, part in zip((3, 2, 1), groups.split("|")):
            for ph in parse_cues(part): entries.append((pts, ph, k, pts))
    for k, c in (custom or {}).items():
        labels[k] = str(c.get("label") or k)
    for k, txt in list((extra_words or {}).items()) + [(k, c.get("words", "")) for k, c in (custom or {}).items()]:
        if k in labels:
            for ph in parse_cues(txt): entries.append((9, ph, k, 3))     # your own words come first and count as strong
    seen = {}
    for pr, ph, k, pts in sorted(entries, key=lambda e: -e[0]):          # a cue belongs to the feeling that gives it the most points (a tie: the one listed first)
        if ph not in seen: seen[ph] = (k, pts)
    table = {}
    for ph, (k, pts) in seen.items(): table.setdefault(ph[0], []).append((ph, k, pts))
    for lst in table.values(): lst.sort(key=lambda e: -len(e[0]))
    _lex_cache[ck] = (table, labels)
    if len(_lex_cache) > 8: _lex_cache.pop(next(iter(_lex_cache)))
    return table, labels


def _forms(t):
    """The word and the plain forms of it ('laughs' -> 'laugh', 'crying' -> 'cry', 'hated' -> 'hate')."""
    yield t
    if len(t) < 5: return
    if t.endswith("ing"):
        yield t[:-3]; yield t[:-3] + "e"
        if len(t) > 6 and t[-4] == t[-5]: yield t[:-4]
    elif t.endswith("ied"): yield t[:-3] + "y"
    elif t.endswith("ed"): yield t[:-2]; yield t[:-1]
    elif t.endswith("ies"): yield t[:-3] + "y"
    elif t.endswith("es"): yield t[:-2]; yield t[:-1]
    elif t.endswith("s") and not t.endswith("ss"): yield t[:-1]


def split_sentences(words):
    """Index groups. A sentence ends at . ! ? (also … 。！？), after a pause of 0.8 s or more, or after 28 words."""
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(i)
        txt = str(w["w"]).rstrip("\"')]”’ ")
        stop = txt.endswith((".", "!", "?", "…", "。", "！", "？")) and not re.search(r"\b(mr|mrs|ms|dr|vs|st)\.$", txt.lower())
        gap = (words[i + 1]["start"] - w["end"]) if i + 1 < len(words) else 99
        if stop or gap >= .8 or len(cur) >= 28: out.append(cur); cur = []
    if cur: out.append(cur)
    return out


def read_story(words, loud=(), extra_words=None, custom=None, dur=None, pauses=True):
    """The spoken words of a clip (each {'w','start','end'}, in clip time) -> the feelings found, in time order:
    [{'t', 'end', 'emo', 'score', 'cue', 'text', 'src'}]. At most one per sentence (two for a long one). Nothing is decided about pictures here."""
    table, labels = lexicon(extra_words, custom)
    words = [w for w in (words or []) if str(w.get("w", "")).strip()]
    out = []
    for idx in split_sentences(words):
        ws = [words[i] for i in idx]; T = [tok(w["w"]) for w in ws]; n = len(T)
        used = [False] * n; cues = []
        i = 0
        while i < n:                                            # longest phrase first; its words are used up
            hit = None
            for ph, k, pts in table.get(T[i], ()):
                if tuple(T[i:i + len(ph)]) == ph: hit = (ph, k, pts); break
            if hit is None and T[i] and LAUGH_RE.match(T[i]) and len(T[i]) >= 3: hit = ((T[i],), "laughing", 3)
            if hit is None:
                for f in _forms(T[i]):
                    if f != T[i]:
                        for ph, k, pts in table.get(f, ()):
                            if len(ph) == 1 and ph[0] == f: hit = ((T[i],), k, pts); break
                    if hit: break
            if hit:
                ph, k, pts = hit
                for j in range(i, i + len(ph)): used[j] = True
                cues.append([i, len(ph), k, float(pts)]); i += len(ph)
            else: i += 1
        if not cues: continue
        for c in cues:                                          # negation / intensifiers (single words only; phrases carry their own meaning)
            i0, ln, k, pts = c
            if ln == 1:
                if any(T[j] in NEG and not used[j] for j in range(max(0, i0 - 3), i0)) and k not in ("blank", "confused"): c[3] = 0.0; continue
                if any(T[j] in INTENS for j in range(max(0, i0 - 2), i0)): c[3] = pts * 1.4
        txt = ws[-1]["w"].rstrip("\"')]”’ ")
        shout = txt.endswith(("!", "！"))
        t0, t1 = ws[0]["start"], ws[-1]["end"]
        near_loud = any(t0 - .3 <= e <= t1 + .3 for e in loud)
        score = {}
        for i0, ln, k, pts in cues:
            if pts <= 0: continue
            m = 1.0
            if k in HIGH: m *= (1.25 if shout else 1.0) * (1.3 if near_loud else 1.0)
            score.setdefault(k, []).append((pts * m, i0, ln))
        if n <= 5 and txt.endswith(("?", "？")) and any(t in ("what", "why", "how", "huh", "who", "which") for t in T):
            score.setdefault("confused", []).append((1.6, 0, 1))
        ranked = sorted(((sum(p for p, _, _ in v), k, v) for k, v in score.items()), key=lambda r: (-r[0], r[1]))
        picked = []
        for tot, k, v in ranked:
            first = min(v, key=lambda x: x[1])
            ts = ws[first[1]]["start"]
            if all(abs(ts - p["t"]) >= 1.2 for p in picked) and len(picked) < 3:
                best = max(v, key=lambda x: x[0])
                picked.append(dict(t=ts, end=t1, emo=k, score=round(tot, 2), cue=" ".join(T[best[1]:best[1] + best[2]]), text=" ".join(w["w"] for w in ws), src="words"))
        out += picked
    if pauses:                                                   # a long silence in the middle of the talking = blank stare
        for a, b in zip(words, words[1:]):
            g = b["start"] - a["end"]
            if g >= 1.4: out.append(dict(t=a["end"] + .15, end=b["start"], emo="blank", score=2.0 + min(1.0, (g - 1.4) / 2), cue="(silence)", text="…", src="pause"))
    return sorted(out, key=lambda m: m["t"])


# ---------------------------------------------------------------- pictures
def infer_tags(name):
    """'my_cry_2.png' -> ['cry']; 'Clown-Face.webp' -> ['clown']; unknown names -> []."""
    base = os.path.splitext(os.path.basename(str(name)))[0].lower()
    parts = [p for p in re.split(r"[^a-z]+", base) if p]
    keys = []
    for cand in parts + ["".join(parts)] + [" ".join(parts[i:i + 2]) for i in range(len(parts) - 1)]:
        c = cand.replace(" ", "")
        k = c if c in EMO else ALIAS.get(c) or ALIAS.get(cand)
        if not k:
            for kk, (lab, _) in EMO.items():
                if re.sub(r"[^a-z]", "", lab.lower()) == c: k = kk; break
        if k and k not in keys: keys.append(k)
    return keys


class Emote:
    """One picture. id is 's:file' (starter) or 'u:file' (yours)."""
    def __init__(self, id, path, name, tags, starter, hidden):
        self.id, self.path, self.name, self.tags, self.starter, self.hidden = id, path, name, list(tags), starter, hidden

    def __repr__(self): return f"<Emote {self.id} {self.tags}{' hidden' if self.hidden else ''}>"


def meta_path(): return os.path.join(USER_DIR, META)


def read_meta():
    try:
        with open(meta_path(), encoding="utf-8") as f: m = json.load(f)
        if not isinstance(m, dict): raise ValueError
    except (OSError, ValueError): m = {}
    for k, d in (("items", {}), ("words", {}), ("custom", {})):
        if not isinstance(m.get(k), dict): m[k] = d
    return m


def write_meta(m):
    os.makedirs(USER_DIR, exist_ok=True)
    tmp = meta_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(m, f, ensure_ascii=False, indent=1)
    os.replace(tmp, meta_path())


def _starter_index():
    if not STARTER_DIR: return {}
    try:
        with open(os.path.join(STARTER_DIR, "index.json"), encoding="utf-8") as f: return json.load(f)
    except (OSError, ValueError): return {}


def label_of(key, meta=None):
    m = meta or read_meta()
    if key in m["custom"]: return str(m["custom"][key].get("label") or key)
    return EMO[key][0] if key in EMO else str(key)


def all_feelings(meta=None):
    """[(key, label, is_custom)] - the feelings the program knows: the built-in ones, then yours."""
    m = meta or read_meta()
    return [(k, v[0], False) for k, v in EMO.items()] + [(k, str(c.get("label") or k), True) for k, c in m["custom"].items() if k not in EMO]


def feeling_key(text, meta=None):
    """What someone typed ('Crying', 'sad', 'my facepalm') -> a feeling key (existing, or None)."""
    m = meta or read_meta()
    s = re.sub(r"[^a-z0-9]", "", str(text).lower())
    if not s: return None
    for k, lab, _ in all_feelings(m):
        if s in (re.sub(r"[^a-z0-9]", "", k.lower()), re.sub(r"[^a-z0-9]", "", lab.lower())): return k
    return ALIAS.get(s)


def load():
    """All your pictures, with your changes (name, feelings, hidden) applied. Hidden ones are included but flagged."""
    meta = read_meta(); idx = _starter_index(); out = []
    if STARTER_DIR and os.path.isdir(STARTER_DIR):
        for f in sorted(os.listdir(STARTER_DIR)):
            if not f.lower().endswith(EXT): continue
            d = idx.get(f, {}); eid = "s:" + f; o = meta["items"].get(eid, {})
            tags = o.get("tags", d.get("tags") or infer_tags(f))
            out.append(Emote(eid, os.path.join(STARTER_DIR, f), o.get("name") or d.get("name") or os.path.splitext(f)[0].title(), tags, True, bool(o.get("hidden"))))
    if os.path.isdir(USER_DIR):
        for f in sorted(os.listdir(USER_DIR)):
            if not f.lower().endswith(EXT) or f.startswith("."): continue
            eid = "u:" + f; o = meta["items"].get(eid, {})
            tags = o["tags"] if "tags" in o else infer_tags(f)
            out.append(Emote(eid, os.path.join(USER_DIR, f), o.get("name") or os.path.splitext(f)[0].replace("_", " ").title(), tags, False, bool(o.get("hidden"))))
    known = {k for k, _, _ in all_feelings(meta)}
    for e in out: e.tags = [t for t in e.tags if t in known]
    return out


def by_feeling(lib=None):
    """{feeling key: [pictures that are switched on]}"""
    d = {}
    for e in (lib if lib is not None else load()):
        if e.hidden: continue
        for t in e.tags: d.setdefault(t, []).append(e)
    return d


def unique_name(folder, name):
    base, ext = os.path.splitext(re.sub(r"[^\w .()-]", "_", os.path.basename(name)))
    n, cand = 1, base + ext
    while os.path.exists(os.path.join(folder, cand)) or cand.startswith("."):
        n += 1; cand = f"{base}_{n}{ext}"
    return cand


def add_files(paths, tags=None):
    """Copy pictures into your emote folder. Returns [(new id, inferred or given feelings)]. The feeling is guessed from the file name unless tags is given."""
    os.makedirs(USER_DIR, exist_ok=True); added = []
    for p in paths:
        if not os.path.isfile(p) or not p.lower().endswith(EXT): continue
        dest = unique_name(USER_DIR, p)
        shutil.copy2(p, os.path.join(USER_DIR, dest))
        eid = "u:" + dest
        tg = list(tags) if tags is not None else infer_tags(p)
        m = read_meta(); m["items"][eid] = {"tags": tg}; write_meta(m); added.append((eid, tg))
    return added


def update(eid, name=None, tags=None, hidden=None):
    m = read_meta(); o = m["items"].setdefault(eid, {})
    if name is not None: o["name"] = str(name).strip()[:40]
    if tags is not None: o["tags"] = list(dict.fromkeys(tags))
    if hidden is not None: o["hidden"] = bool(hidden)
    write_meta(m)


def remove(eid):
    """Your own picture: the file is deleted. A starter picture is only switched off (Restore brings it back)."""
    if eid.startswith("s:"): return update(eid, hidden=True)
    p = os.path.join(USER_DIR, eid[2:])
    try: os.remove(p)
    except OSError: pass
    m = read_meta(); m["items"].pop(eid, None); write_meta(m)


def restore_starters():
    m = read_meta()
    for eid in [k for k in m["items"] if k.startswith("s:")]:
        m["items"][eid].pop("hidden", None)
    write_meta(m)


def set_words(key, text):
    """Your own words for a feeling (the built-in words stay). For a feeling you made yourself these are its words."""
    m = read_meta(); text = str(text).strip()
    if key in m["custom"]: m["custom"][key]["words"] = text
    elif text: m["words"][key] = text
    else: m["words"].pop(key, None)
    write_meta(m)


def my_words(key, meta=None):
    m = meta or read_meta()
    return str(m["custom"][key].get("words", "")) if key in m["custom"] else str(m["words"].get(key, ""))


def sample_cues(key, n=14):
    """A few of the words that make the app use this feeling, strongest first (for the manager window)."""
    if key not in EMO: return [], 0
    lst = [" ".join(p) for pts in EMO[key][1].split("|")[:2] for p in parse_cues(pts)]
    return lst[:n], max(0, len(lst) - n)


def add_feeling(label, words=""):
    """A feeling of your own ('facepalm', 'my catchphrase'). Returns its key."""
    key = re.sub(r"[^a-z0-9]+", "_", str(label).lower()).strip("_")[:24] or "mine"
    m = read_meta()
    if key in EMO or key in m["custom"]:
        n = 2
        while f"{key}_{n}" in m["custom"]: n += 1
        key = f"{key}_{n}"
    m["custom"][key] = {"label": str(label).strip()[:30] or key, "words": str(words).strip()}
    write_meta(m); return key


def delete_feeling(key):
    m = read_meta(); m["custom"].pop(key, None); m["words"].pop(key, None)
    for o in m["items"].values():
        if isinstance(o.get("tags"), list): o["tags"] = [t for t in o["tags"] if t != key]
    write_meta(m)


def story_settings():
    """(extra words, custom feelings) from the user's file - what read_story needs."""
    m = read_meta(); return dict(m["words"]), dict(m["custom"])


# ---------------------------------------------------------------- picture files for ffmpeg / Tk
def _ff():
    try:
        import streamclip; return streamclip.FF
    except Exception: return "ffmpeg"


def _stamp(path):
    try: s = os.stat(path); return f"{int(s.st_mtime)}_{s.st_size}"
    except OSError: return "0"


def small_copy(path, size=512, name_tag=""):
    """A copy of a picture at most size x size px (cached) - faster to render than a 3000 px original. GIFs are used as they are."""
    if path.lower().endswith(".gif"): return path
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        import hashlib
        key = hashlib.md5(f"{os.path.abspath(path)}|{_stamp(path)}|{size}".encode()).hexdigest()[:16]
        dest = os.path.join(CACHE_DIR, f"{name_tag}{key}.png")
        if os.path.isfile(dest): return dest
        r = subprocess.run([_ff(), "-y", "-v", "error", "-i", path, "-vf", f"scale='min({size},iw)':'min({size},ih)':force_original_aspect_ratio=decrease:flags=lanczos,format=rgba",
                            "-frames:v", "1", dest], capture_output=True, stdin=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=60)
        return dest if r.returncode == 0 and os.path.isfile(dest) else path
    except Exception: return path


def thumb(path, size=96):
    """A small PNG a Tk window can show (Tk has no resize): cached, made with ffmpeg. """
    pre = os.path.join(STARTER_DIR, "thumbs", str(size), os.path.basename(path)) if STARTER_DIR else ""
    if pre and os.path.isfile(pre) and os.path.abspath(os.path.dirname(path)) == os.path.abspath(STARTER_DIR): return pre
    return small_copy(path, size, f"t{size}_")


# ---------------------------------------------------------------- deciding
def _limit(dur, rate): return max(1, int(math.ceil(rate * max(dur, 1) / 60.0 + .15)))


def plan(words, dur, loud=(), lib=None, level="normal", burst=False, seed=0, first=.4, extra_words=None, custom=None, pauses=True, limit=None):
    """Which picture, when. -> dict(items=[...], heard=[all feelings found], missing={feeling: how many moments had no picture}).
    Each item: t, hold (seconds), tag, label, id, path, name, score, cue, text, src. Items never overlap and keep a gap, so the pictures are never spammed."""
    lv = LEVELS.get(level, LEVELS["normal"]); lib = load() if lib is None else lib
    if extra_words is None and custom is None: extra_words, custom = story_settings()
    pics = by_feeling(lib); _, labels = lexicon(extra_words, custom)
    heard = read_story(words, loud, extra_words, custom, dur, pauses)
    rng = random.Random(seed)
    missing, cand = {}, []
    for m in heard:
        if m["score"] < lv["thr"] or not (first <= m["t"] <= dur - 1.0): continue
        if not pics.get(m["emo"]): missing[m["emo"]] = missing.get(m["emo"], 0) + 1; continue
        cand.append(m)
    limit, chosen = limit or _limit(dur, lv["rate"]), []
    for m in sorted(cand, key=lambda m: (-m["score"], m["t"])):
        if len(chosen) >= limit: break
        if any(abs(m["t"] - c["t"]) < lv["gap"] for c in chosen): continue
        cd = COOL.get(m["emo"], 9.0)
        if m["score"] < 5 and any(c["emo"] == m["emo"] and abs(c["t"] - m["t"]) < cd for c in chosen): continue
        chosen.append(m)
    if burst and loud:                                           # loud moment, nobody said a feeling: a reaction still fits
        avail = [r for r in REACTIONS if pics.get(r)]; turn = 0
        for e in loud:
            if len(chosen) >= limit or not avail or not (first <= e <= dur - 1.0): continue
            if any(abs(e - c["t"]) < lv["gap"] for c in chosen): continue
            last = chosen[-1]["emo"] if chosen else ""
            em = [r for r in avail if r != last] or avail
            emo = em[(turn + rng.randrange(len(em))) % len(em)]; turn += 1
            chosen.append(dict(t=e, end=e + 1.8, emo=emo, score=1.0, cue="(loud moment)", text="", src="loud"))
    chosen.sort(key=lambda m: m["t"])
    items = []
    for i, m in enumerate(chosen):
        nxt = chosen[i + 1]["t"] if i + 1 < len(chosen) else dur
        hold = min(max(1.8, m["end"] - m["t"] + .5), 3.8, nxt - m["t"] - .12, dur - m["t"] - .15)
        if hold < 1.0: hold = max(1.0, min(1.4, dur - m["t"] - .1))
        e = pick_picture(pics[m["emo"]], rng)
        items.append(dict(t=round(max(0.0, m["t"] - .1), 2), hold=round(hold, 2), tag=m["emo"], label=labels.get(m["emo"], m["emo"]), id=e.id, path=e.path, name=e.name,
                          score=m["score"], cue=m["cue"], text=m["text"], src=m["src"]))
    return dict(items=items, heard=heard, missing=missing)


def pick_picture(entries, rng=None):
    """The least used picture of a feeling (a random one among equals), so a clip with two crying scenes does not show the same one twice."""
    rng = rng or random
    with _lock:
        low = min(_used.get(e.path, 0) for e in entries)
        e = rng.choice([x for x in entries if _used.get(x.path, 0) == low])
        _used[e.path] = _used.get(e.path, 0) + 1
    return e


def describe(item, hms=None):
    """One plain line for the plan window / log."""
    t = item["t"]; ts = f"{int(t // 60)}:{int(t % 60):02d}"
    why = "loud moment" if item.get("src") == "loud" else "silence" if item.get("src") == "pause" else f'"{item.get("cue", "")}"'
    return f"{ts}  {item.get('label', item.get('tag'))}  ({why})  {str(item.get('text', ''))[:70]}"


def try_text(text, level="normal", lib=None):
    """The 'Try a sentence' tester: typed text -> what the program would see. Words get 0.34 s each."""
    ws, t = [], 0.0
    for w in str(text or "").split():
        d = .22 + .03 * min(len(w), 10); ws.append({"w": w, "start": t, "end": t + d}); t += d + .06
    dur = max(6.0, t + 2)
    lv = LEVELS.get(level, LEVELS["normal"]); lib = load() if lib is None else lib
    extra, custom = story_settings(); pics = by_feeling(lib); _, labels = lexicon(extra, custom)
    heard = read_story(ws, (), extra, custom, dur, False)
    return [dict(emo=m["emo"], label=labels.get(m["emo"], m["emo"]), score=m["score"], cue=m["cue"], enough=m["score"] >= lv["thr"],
                 pictures=[e.name for e in pics.get(m["emo"], [])]) for m in heard]
