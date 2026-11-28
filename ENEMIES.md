# LYCANTROPE — Enemy Ideas

The game is named for its monsters, so this is the bestiary wish list. Every entry is a classic fantasy-trope enemy with a twist in how it fights. The idea tracker reads this file, so you can approve or deny each one. Approved enemies get a JSON file in `data/enemies/`, a Meshy model (see OBJECTS.md for the pipeline), and barks in `data/lines.csv`.

---

## How to read an entry

`- [MON-01] **Name** — Lv · where · archetype · how it fights · weakness · voice · rig. (sources)`

- **Lv** is the base level (STA-10: regions have fixed levels).
- **Archetype** is the shared behavior it's built from (ENM-24: melee-basic, pack-circler, ranged-kiter, caster-support, flyer, ambusher, brute, regenerator, phaser, armored-weakpoint). A few entries need a **new archetype**, which is noted, because it costs more code.
- **Rig:**
  - **humanoid** means Meshy auto-rig plus its animation library (ART-03), which is cheap.
  - **procedural** means it's animated in code (ART-04), which takes more work for unusual bodies.
- **Voice** is either an ElevenLabs designed voice with words, or **SFX** (ElevenLabs Sound Effects only).
- Sources are limited to the ten inspiration games (see IDEAS.md). **NEW** means an original twist on the trope.

---

## Already approved (in IDEAS.md, counted here, not repeated)

These 20 are decided and stay in IDEAS.md under their `ENM` IDs:

- ENM-01 Giant Rat (Lv 1) · ENM-02 Grey Wolf (2) · ENM-03 Goblin Cutthroat (2) · ENM-04 Bandit Brigand (3)
- ENM-05 Bog Ooze (3) · ENM-06 Bandit Crossbowman (4) · ENM-07 Goblin Hexer (4) · ENM-08 Skeleton Warrior (5)
- ENM-09 Giant Spider (5) · ENM-10 Drowned Thrall (6) · ENM-12 Lizardfolk Spearman (7) · ENM-13 Orc Berserker (8)
- ENM-14 Bog Troll (10) · ENM-15 Wraith (11) · ENM-16 Frost Yeti (12) · ENM-17 Ogre Brute (13)
- ENM-18 Werewolf (14) · ENM-19 Dread Knight (15) · ENM-21 Mimic Chest · ENM-22 Necromancer

You denied the Harpy (ENM-11) and the Runestone Golem (ENM-20), so neither returns here under another name.

**20 approved + 47 below = 67 enemies to choose from.**

---

## 1. Tier 1: Levels 1–5 (MON)

- [MON-01] **Kobold Trapper** — Lv 2 · Brackenvale, crypt entrances · ranged-kiter · Small dog-faced scavenger that throws pebbles, then runs back toward the snare traps it has hidden in the grass. Snares hold you for a second; spotting them (they glint) and baiting the kobold through its own trap is the trick. · Weak to everything once caught · *Voice: yips and squeaky taunts ("Step there! No, there!")* · humanoid *(OoT, SK, NEW)*
- [MON-02] **Mischief Sprite** — Lv 2 · Brackenvale meadows · flyer (swarm of 3–5) · Tiny glowing fae that zip around, tug your scarf, and steal one consumable before fleeing. Catch the one carrying it to get it back. Barely any HP. · One hit kills · *Voice: giggling whispers* · procedural *(OoT, MM)*
- [MON-03] **Cave Bat Swarm** — Lv 2 · Crypts, caves, Wolfwood at night · flyer (swarm) · Erratic flocks that flutter in and nip. Hard to lock on, so a wide swing or charged spin (CMB-11) is the answer. Torchlight and Awakening scatter them. · Spin attacks, light · *Voice: screeches (SFX)* · procedural *(OoT, TP, SK)*
- [MON-04] **Bog Leech** — Lv 3 · Blackmire shallows · ambusher · Waits unseen in murky water and latches onto your leg, draining HP until you roll to shake it off. Fat, slow and harmless on dry land. · Fire, salt (throwables) · *Voice: wet squelch (SFX)* · procedural *(NEW)*
- [MON-05] **Wild Boar** — Lv 3 · Brackenvale, Wolfwood · new archetype: charger · Paws the ground, then charges in a straight line and knocks you down. Turns slowly, so sidestep and hit its flank. · Flanks, spears · *Voice: snorts and squeals (SFX)* · procedural *(SK, OB, TP)*
- [MON-06] **Bramble Spitter** — Lv 4 · Wolfwood, overgrown ruins · ambusher · Disguised as a bush; pops up to spit thorn darts, then ducks back down. Parry a dart back at it (CMB-08) or circle round behind it. · Reflected projectiles, fire · *Voice: rustling hiss (SFX)* · procedural *(OoT, MM)*
- [MON-07] **Giant Crab** — Lv 4 · Blackmire shores, lakes · armored-weakpoint · Scuttles sideways, blocks with its huge claws. A heavy hit flips it onto its back for a critical. · Strike damage, kicks (CMB-31) · *Voice: clicking and bubbling (SFX)* · procedural *(SK, MW, OB)*
- [MON-08] **Imp** — Lv 4 · Ashen Reach, Duskhold · caster-support · Little winged fire demon that blinks short distances, throws fireballs and cackles. Fragile but slippery. · Frost, crossbow · *Voice: high-pitched cackling taunts* · humanoid *(OB, SK)*
- [MON-09] **Skeleton Archer** — Lv 5 · Crypts, ruins · ranged-kiter · The archer counterpart to the Skeleton Warrior; shares its rig and reassembly rule. Hangs back on ledges with volleys. · Blunt, radiant · *Voice: bone rattle (SFX)* · humanoid (reuses ENM-08) *(OoT, DS1, SK)*
- [MON-10] **Bandit Bruiser** — Lv 5 · Roads, bandit camps · brute · The big one in the gang: a two-handed maul, overhead slams that crack the ground, and a shoulder barge. Slow recovery, so it's punishable. · Dodge-then-punish · *Voice: gruff boasts ("I'll flatten you, hero!")* · humanoid (reuses bandit voices) *(SK, DS)*
- [MON-11] **Giant Toad** — Lv 5 · Blackmire · ranged-kiter · Tongue lash from range pulls you in for a bite; belly-flops if you get close. The tongue can be cut while extended. · Cutting the tongue, fire · *Voice: deep croaks (SFX)* · procedural *(OoT, TP, NEW)*

## 2. Tier 2: Levels 6–10 (MON)

- [MON-12] **Will-o'-Wisp** — Lv 6 · Blackmire at night · phaser · A floating light that drifts away as you follow, leading you toward deep water and leeches. It's only solid while it pulses; it bursts when killed. · Crossbow during the pulse, radiant · *Voice: faint chimes and a child-like hum* · procedural *(TP, SK, NEW)*
- [MON-13] **Cockatrice** — Lv 6 · Brackenvale farms · melee-basic · A furious rooster-lizard. Its pecks build up a **stone** status that slows you to a stop if it fills. Funny until it isn't. · Kill it fast, or get distance to let the status drain · *Voice: crowing shrieks (SFX)* · procedural *(OoT, NEW)*
- [MON-14] **Gnoll Raider** — Lv 6 · Roads, Ashen Reach · pack-circler · Hyena-headed raiders in packs that laugh to coordinate and throw javelins before closing in. Kill the leader and the others hesitate. · Isolate them one by one · *Voice: hyena cackles and broken words* · humanoid *(NEW)*
- [MON-15] **Brown Bear** — Lv 6 · Wolfwood, Brackenvale edges · brute · Rears up and roars (telegraph), then two-paw slams and a maul that grabs. Neutral until you get close. · Interrupt the rear-up with a crossbow bolt · *Voice: growls and roars (SFX)* · procedural *(SK, OB)*
- [MON-16] **Sporeling** — Lv 6 · Wolfwood, Crypts · melee-basic (group) · Waddling mushroom folk that puff poison spores when hit and burst into a poison cloud when they die. Fight them at range or roll through the cloud. · Fire, range · *Voice: muffled squeaks (SFX)* · humanoid (small) *(NEW)*
- [MON-17] **Hobgoblin Captain** — Lv 7 · Goblin camps · caster-support · Armored goblin leader with a shield and war horn. While it lives, nearby goblins fight better and don't flee; blowing the horn calls more. Silence the horn first. · Guard break, crossbow at the horn · *Voice: barked orders ("Hold the line, maggots!")* · humanoid *(SK, OB)*
- [MON-18] **Crypt Ghoul** — Lv 7 · Crypts, graveyards · pack-circler · Fast, hunched corpse-eaters that scuttle on all fours. Their claws build **numbing**, which slows your stamina regeneration. Different from the slow Drowned Thrall. · Radiant, holy water · *Voice: hissing and snarling* · humanoid *(SK, DS1)*
- [MON-19] **Poltergeist** — Lv 7 · Burned village at night, Crypts · phaser · An invisible spirit that hurls nearby barrels, pots and tools at you. Hitting the floating object it's holding makes it visible for a moment. · Radiant, the Seer's Lens (VAL-06) · *Voice: whispers, slamming doors (SFX)* · procedural *(TP, MM)*
- [MON-20] **Animated Armor** — Lv 8 · Crypts, Duskhold halls · armored-weakpoint · Empty suit of armor that stands still like decoration until you pass. Heavy and parryable; knocking off the helm drops it in a heap. · Parry, strike damage · *Voice: metal scraping and hollow echoes (SFX)* · humanoid *(OoT, DS, OB)*
- [MON-21] **Giant Scorpion** — Lv 8 · Ashen Reach · armored-weakpoint · Pincer grab, then a poison tail sting while you're held. Its tail is the weak point; cut it off and it only has pincers. · Severing the tail · *Voice: chittering clicks (SFX)* · procedural *(OB, SK, NEW)*
- [MON-22] **Wolf Rider** — Lv 9 · Roads, Brackenvale · new archetype: mounted · Goblin riding a huge wolf, making charging passes with a spear. Knock the rider off and you face a wolf and a furious goblin. · Crossbow at the rider, tripwires · *Voice: goblin war whoops plus wolf growls* · procedural (wolf) + humanoid (rider) *(TP, NEW)*
- [MON-23] **Centaur Outrider** — Lv 9 · Brackenvale plains · ranged-kiter · Circles at a gallop firing arrows and closes in to trample if you turn your back. Hard to catch; corner it against walls or rough ground. · Terrain, crossbow · *Voice: proud, formal challenges ("Turn and face me!")* · procedural (horse body) + humanoid torso *(NEW)*
- [MON-24] **Barrow Wight** — Lv 9 · Crypts, tombs · melee-basic · Ancient warrior rising from its sarcophagus in rusted finery. Its frost blade lowers your max stamina for the fight. · Fire, radiant · *Voice: deep, slow, archaic ("You disturb the honored dead.")* · humanoid *(SK, DS1, NEW)*
- [MON-25] **Dark Acolyte** — Lv 9 · Duskhold, cult camps · caster-support · Robed cultist of the Dark Lord: shadow bolts, a barrier on allies, and a self-sacrifice that empowers the nearest monster. Kill it before it finishes the ritual. · Interrupts, crossbow · *Voice: chanting and zealous whispers ("For the Undying!")* · humanoid *(SK, OB)*
- [MON-26] **Fire Salamander** — Lv 9 · Ashen Reach lava fields · ranged-kiter · Glowing lizard that swims through lava cracks, spits fire and leaves burning trails. · Frost, holy water · *Voice: hisses and crackling (SFX)* · procedural *(OoT, NEW)*
- [MON-27] **Hellhound** — Lv 10 · Ashen Reach, Duskhold · pack-circler · Black fire-breathing hounds in packs of 2–3; flaming bites cause burns. Like wolves, but punishing if you stand still. · Frost, water (stand in shallows) · *Voice: growls and fiery snorts (SFX)* · procedural (reuses the wolf animation code) *(SK, OB, DS)*
- [MON-28] **Siren** — Lv 10 · Blackmire lakes, Frostfang tarns · caster-support · Sings from the water, slowly pulling you toward the shore; fights with a trident when you're close. Interrupting the song breaks the pull. · Crossbow, earplugs (item) · *Voice: wordless haunting song, then hissing* · humanoid *(NEW)*

## 3. Tier 3: Levels 11–15 (MON)

- [MON-29] **Battlemage** — Lv 11 · Roads, Duskhold · caster-support · A sword-and-spell soldier who shields itself with a ward, throws fireballs, and switches to blade when you close in. Breaking the ward staggers it. · Guard-break the ward, then rush · *Voice: arrogant scholar ("Your sword is no match for study.")* · humanoid *(OB, SK, MW)*
- [MON-30] **Blightwood Treant** — Lv 11 · Wolfwood · brute · Looks like one of the trees until it moves. Root spikes erupt beneath you; it sweeps with branch-arms and regrows bark armor unless burned. · Fire, axes · *Voice: creaking groan, slow ancient words* · procedural *(OoT, TP, SK)*
- [MON-31] **Shadow Assassin** — Lv 12 · Roads at night, Duskhold · ambusher · Approaches invisible, attacks from behind, drops a smoke bomb and vanishes when hurt. Footstep sounds and the Seer's Lens give it away. · Turning around in time, Seer's Lens · *Voice: cold whispers ("Nothing personal.")* · humanoid *(OB, SK)*
- [MON-32] **Banshee** — Lv 12 · Crypts, graveyards at night · phaser · A weeping spirit whose scream is a cone that drains stamina and causes fear (Rowan staggers back). Hides behind gravestones between screams. · Radiant, attack after the scream · *Voice: weeping, then a piercing wail* · humanoid *(SK, TP)*
- [MON-33] **Ash Burrower** — Lv 12 · Ashen Reach · ambusher · A giant worm moving under the ash. The ground ripples before it erupts beneath you; it's vulnerable for a few seconds while it's out of the ground. · Hit it while surfaced; explosive barrels · *Voice: rumbling roar (SFX)* · procedural *(OoT, TP, NEW)*
- [MON-34] **Ember Elemental** — Lv 12 · Ashen Reach, Cinder Forge · regenerator · A walking bonfire that heals while standing in lava or fire, and explodes in a burst at low HP. Lure it away from fire. · Frost, water · *Voice: roaring flames (SFX)* · procedural *(OB, SK)*
- [MON-35] **Frost Elemental** — Lv 12 · Frostfang · armored-weakpoint · A crystalline ice body that shatters into shards and reforms once. Freezing breath builds frost (slow). · Fire, strike damage · *Voice: grinding ice, howling wind (SFX)* · procedural *(OB, SK)*
- [MON-36] **Gargoyle** — Lv 13 · Duskhold walls, ruins · flyer · Perches as a statue (indistinguishable until it moves), swoops down, and lands to fight. Stone skin shrugs off slash damage. · Strike damage, interrupt the dive with a crossbow bolt · *Voice: grinding stone screech (SFX)* · procedural *(DS1, OB)*
- [MON-37] **Mire Lurker** — Lv 13 · Blackmire deep pools · new archetype: stationary · A lake monster you only ever see as tentacles bursting from the water to grab and drag. Hack the tentacles until the head surfaces for a few hits. · Cutting tentacles, fire on the head · *Voice: deep bubbling roar (SFX)* · procedural *(OoT, DS, NEW)*
- [MON-38] **Minotaur** — Lv 14 · Crypt labyrinths, Ashen Reach · new archetype: charger · Bull-headed brute with a great axe. Charges blindly and stuns itself if it hits a wall; that's your opening. · Dodge so it hits a wall · *Voice: bellowing roars and a few rough words* · humanoid *(DS, NEW)*
- [MON-39] **Shadow Stalker** — Lv 14 · Duskhold, deep Crypts · phaser · A creature of living darkness, visible only inside light (torches, the Dawnblade's glow, VAL-08). In darkness it can't be hit at all. · Light, Awakening · *Voice: layered breathing and a whisper of your name* · humanoid *(TP, NEW)*
- [MON-40] **Basilisk** — Lv 15 · Ashen Reach caves · armored-weakpoint · A huge serpent-lizard whose gaze builds **stone** if you keep looking at it (keep the camera turned away or behind cover). Bite and tail sweep in close. · Attacking from behind, smoke bombs · *Voice: deep hiss (SFX)* · procedural *(OoT, NEW)*
- [MON-41] **Shadow Double** — Lv 15 · Duskhold citadel (a set-piece room) · new archetype: mirror · A dark copy of Rowan that uses your own moveset and reacts to your inputs. Mirroring it doesn't work; you have to do something it doesn't expect. · Unusual tools: throwables, Rites · *Voice: Rowan's own lines, distorted* · humanoid (reuses Rowan's rig) *(OoT, NEW)*

## 4. Tier 4: Levels 16–20 (MON)

- [MON-42] **Vampire** — Lv 17 · Crypts, Duskhold at night · phaser · An aristocratic predator: drains HP to heal, dodges as a swarm of bats, and charms you briefly (your controls drift toward it). Daylight or radiant damage stops the healing. · Radiant, holy water · *Voice: silky, menacing ("Such vigorous blood.")* · humanoid *(SK, OB)*
- [MON-43] **Manticore** — Lv 17 · Ashen Reach · ranged-kiter · Lion-bodied, bat-winged and scorpion-tailed, it fires tail-spike volleys, leaps over your head, and roars to make you flinch. · Rolling under the leap; spears · *Voice: roaring with an unsettling human edge* · procedural *(NEW)*
- [MON-44] **Hill Giant** — Lv 18 · Frostfang foothills · brute · Neutral and placid until provoked, then devastating: kicks that launch you into the air, stomps and a tree-trunk club. Huge HP; a test of patience. · Hitting its heels, staying behind it · *Voice: deep, slow rumbles; few words* · humanoid (scaled up) *(SK, DS)*
- [MON-45] **Swamp Hydra** — Lv 18 · Blackmire's heart · regenerator · Three heads that each attack separately; a severed head grows back as two unless the stump is burned. Could also be an optional mini-boss. · Fire on the stumps · *Voice: three-way hissing (SFX)* · procedural *(NEW)*
- [MON-46] **Ash Drake** — Lv 19 · Ashen Reach, Frostfang skies · flyer · A lesser dragon, smaller than the Frostfang Wyvern (BOS-04): strafing fire breath, tail sweeps on landing, and it takes off again at half HP. · Crossbow at the wings, fighting under cover · *Voice: roars (SFX)* · procedural (reuses the BOS-04 rig) *(SK, DS)*
- [MON-47] **Lich** — Lv 20 · Duskhold depths, the Crypts' deepest vault · caster-support · An undying sorcerer who raises skeletons, teleports and casts frost storms. It can't die until its **phylactery** (hidden in the room) is smashed, so the fight is part search. · Find and break the phylactery · *Voice: echoing and imperious ("I have outlived kings.")* · humanoid *(SK, DS1, OB)*
