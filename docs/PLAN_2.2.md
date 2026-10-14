# 2.2 plan (written 2026-10-13 ~19:40) - the 50 features
Constraints: no picture-making tools, no direct posting/analytics, no ML model (rules + user's own picks), keep Simple view small.
Modules: vcsense.py (audio detectors), vcsmart.py (lexicons, types, picking, titles, taste, chat, hashtags), vcmore.py (post-process, audio chains, caption helpers), vc22ui.py (GUI). Tests in S/v22.
A smarter finding: 1 moment types; 2 auto look; 3 laugh; 4 scream; 5 singing(+lyric captions); 6 setup->punchline; 7 story shape snap; 8 greeting skip;
 9 bigger vocab; 10 variety picker; 11 smart length; 12 end on payoff; 13 chat activity; 14 why notes in post kit; 15 my taste; 16 hook/title templates by type
B picture/sound: 17 hopping watermark; 18 slow-mo; 19 freeze beat; 20 teaser first; 21 reaction word pops; 22 tame screams; 23 hush hiss;
 24 caption case; 25 outline+shadow; 26 words per phrase; 27 caption box; 28 rainbow words; 29 extra shapes (square/landscape copy)
C workflow: 30 watch folder; 31 review mode; 32 tags+search; 33 CSV post sheet; 34 hashtag bank; 35 health check; 36 clean-up; 37 free up space;
 38 share a look; 39 compare 3 looks; 40 remake clip; 41 where is this from; 42 ready folder; 43 learn my vocabulary; 44 cam memory per game;
 45 resume interrupted run; 46 try one first; 47 auto-fill planner; 48 name tokens {type}{score}{len}; 49 moments file; 50 only look between from/to
Already existed (dont redo): progress bar (fx bar), batch of VODs, fix_pairs learning, favourites/posted, profiles, planner suggest times.
Research facts used (author claims, unverified): first 3s = 50-60% of dropoffs, open on most compelling moment; length: entertainment 18-28s, story 30-50s,
 general 15-30s; new beat every 2-7s; no greetings; captions centre third; cut right after payoff; VTuber viral types: singing/karaoke, chaotic reactions, rivalries/collabs, bilingual jokes, milestone reactions.
