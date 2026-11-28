# Lycantrope — notes for Claude

A 3D action-adventure fantasy RPG in Python (pygame-ce + moderngl). MIT, free on itch.io. Assets are generated with Meshy, Tripo3D, ElevenLabs and Python scripts. The design is in IDEAS.md and the plan is in ROADMAP.md.

## Idea tracker (the user refers to it often)
- `IDEAS.md` holds the ideas, `OBJECTS.md` the Meshy/Tripo3D props/items and `ENEMIES.md` extra enemy ideas (`MON-` IDs) and `ARMOR.md` armor sets (`HED/ARM/TRS/LEG-NN`, same number = same set, plus `ARS` rules) and `WEAPONS.md` (`ONE/TWO/SHD/MAG-NN` plus `WPR` rules); the tracker reads all five. Each entry is a bullet starting with an ID like `[CMB-04]` or `[TRE-05]`, unique across both files. **Never renumber or reuse IDs.** A new idea takes the next free number in its category.
- `ideas_status.json` is the **source of truth** for decisions. `ideas[ID].status` is `awaiting`, `approved` or `denied`, and `ideas[ID].note` holds the user's note. `ui.selected` is what the user currently has selected in the tracker window ("this one", "the selected idea"). `history` lists recent changes.
- `IDEAS_STATUS.md` is a readable digest generated from the JSON. Don't edit it.
- To check state: `python tools/idea_tracker.py summary`, or read the JSON.
- To change state when asked: `python tools/idea_tracker.py set approved CMB-01 "WLF-*"`, or `... note ID "text"`. The GUI reloads by itself.
- When the user denies an idea, remove or replace its tasks in ROADMAP.md the next time you edit it.

## Content rules
- Inspirations are limited to: Ocarina of Time, Majora's Mask, Twilight Princess, Morrowind, Oblivion, Skyrim, Dark Souls 1–3, and The Witcher 1–3. Programming ideas may come from DREAM-QUEST.md and THE_DREAMLANDS.md.
- No Lovecraftian content unless manually approved. No concepts exclusive to Morrowind. Generic fantasy tropes are fine. Use original names, not borrowed terms (Estus, bonfire, Thu'um and so on).
- The story is a **generic hero plot** (a humble chosen hero, a wise mentor, a returning Dark Lord, four Crown Shards). It is **not** about lycanthropy: the title "Lycantrope" refers to the roster of fantasy-trope monsters. Werewolves can appear only as ordinary enemies.
- No character customization for now: the hero is Rowan Fenhallow. Rowan is a farmhand who wields the Dawnblade. Player beast forms (DRM-25 Dream-Shapes) are allowed but saved for much later.
