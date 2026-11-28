# LYCANTROPE — Implementation Roadmap

> Python 3.11+ · pygame-ce + moderngl · Meshy / Tripo3D (models) · ElevenLabs (voice, SFX, music) · MIT · free on itch.io

The roadmap refers to ideas by their ID in [IDEAS.md](IDEAS.md) (for example **CMB-04**). When you **deny** an idea in the tracker, the matching tasks are dropped or replaced when the roadmap is next updated. **Awaiting** ideas marked ⭐ are assumed *in* until you say otherwise, because the week can't wait for every decision.

---

## 0. Decisions needed before Day 1

These change code or assets on Day 1–2, so please decide them in the tracker first:

| Decide | Options | Why it matters now |
|---|---|---|
| Rowan's gender and voice | Decided: **HER-03**, a man | Meshy model prompt and ElevenLabs voice design run on Day 1 |
| Where you level up | Decided: **STA-02**, anywhere | Level-up UI and death loop |
| pygame or pygame-ce | **TEC-01** | Install step; pygame-ce is recommended |
| First boss | **BOS-01** Grimtooth (recommended: it shares the Werewolf enemy's rig) or another | Asset kitchen queue on Day 2 |
| Asset licence | **REL-01**, **REL-04** | What goes in the public repo |

You also need:
- **API keys** set as environment variables: `MESHY_API_KEY` and `ELEVENLABS_API_KEY`. Never paste them into files that get committed.
- **Git + Git LFS** installed, an empty GitHub repo, an itch.io project page (can be set to draft), and **ffmpeg** on your PATH (used for audio mastering).

---

## 1. Milestones

| Milestone | Target | What "done" means |
|---|---|---|
| **M0 Foundations** | Day 1 | Repo, venv, window with a GL context, fixed-step loop, terrain on screen, asset pipelines running |
| **M1 First Playable** | End of Week 1 (core) + Week 2 (full roster) | Rowan with the Dawnblade, crossbow and Rites, 4 biomes on one map, **20 approved enemies** with voiced barks at levels 1–15, XP/levels with no NPC, 6 attributes + 8 use-based skills that change combat, Waystones, one boss, save/load, Windows build on itch |
| **M2 Vertical Slice** | Weeks 3–5 | Act I opening: farm chores, the mentor, the first incursion at the burying ground with rift sealing, plus the first Crown Shard dungeon (Wolfwood) with its tool (grappling chain), the Brood Queen boss, music, bestiary, compass |
| **M3 Public Demo** | ~Week 8 | The rest of Part I (the waking world): the stone circle and the galley incursions, the Shantak Rider, the second waking-world Crown Shard (Blackmire), the Brackenvale sidequests, relic powers, polish pass, settings and accessibility, devlog push |
| **M4 Full Game** | Later | Part II (the Dreamlands): the descent through sleep, the two Dreamlands Crown Shards, fallen Serannian restored; then the return, the Crypts, Duskhold, Malgrath, the ending that hints at the unseen hand, NG+ |

**Week 1 is about proving the core.** By Sunday you should have a downloadable build in which Rowan explores four biomes, fights about 12 enemy types, levels up, casts a Rite and kills a boss. **Week 2** finishes the roster to all 20, adds the rest of the voice lines, and tunes balance. With the Meshy/Tripo3D and ElevenLabs batches running in the background all week, that is ambitious but achievable. The cut list (§6) says what to drop first if a day overruns.

---

## 2. Tech stack

| Purpose | Package | Notes |
|---|---|---|
| Window, input, audio | `pygame-ce` | `import pygame` still works; relative mouse mode; joystick support |
| Rendering | `moderngl` | OpenGL 4.3 core (compute shaders for Hi-Z occlusion culling) |
| Math | `PyGLM`, `numpy` | glm for per-object math, numpy for bulk work |
| Models | `pygltflib` (+ `trimesh` for offline tools) | GLB meshes, skins, animations |
| Images | `Pillow` | Textures, icons, the biome mask |
| HTTP | `requests` | Meshy, Tripo3D and ElevenLabs batch tools (offline only, not shipped) |
| Noise | `numpy` (own implementation) or `opensimplex` | Offline terrain generation |
| Tests | `pytest` (+ `hypothesis` later) | Formulas, data validation, saves |
| Build | `pyinstaller`, `butler` | Windows onedir build → itch.io |

---

## 3. Architecture

```
                 ┌──────────────────────────────────────────┐
                 │ main.py  — fixed 60 Hz sim, render @ vsync│
                 └───────┬──────────────────────┬───────────┘
          InputState     │                      │  read-only state + alpha
                         ▼                      ▼
┌──────────────┐  ┌──────────────────┐   ┌───────────────────────────┐
│ input/       │→ │ SIMULATION       │   │ RENDERER (moderngl)       │
│ kb/mouse/pad │  │ world, actors,   │   │ terrain chunks, instanced │
│ buffer 150ms │  │ combat, AI, rpg  │   │ props, skinned meshes,    │
└──────────────┘  │ (no GL calls)    │   │ sky, shadows, post, UI tex│
                  └───┬──────────┬───┘   └───────────────────────────┘
                 events│          │data
                      ▼          ▼
     ┌──────────────────────┐  ┌──────────────────────────────────┐
     │ EventBus → audio,    │  │ data/*.json (enemies, attacks,   │
     │ VFX, barks, HUD,     │  │ items, loot, biomes, xp) — F5    │
     │ subtitles            │  │ hot-reload in dev                │
     └──────────────────────┘  └──────────────────────────────────┘

 OFFLINE (tools/, never shipped): Meshy / Tripo3D → normalize GLB → assets/models
                                  ElevenLabs batch → ffmpeg → assets/audio
                                  worldgen → height.png + biome.png + road.png + meta.json (+ scatter.json)
```

**Rules that apply throughout** (TEC-04 to TEC-07):
1. The simulation never calls the GPU. The renderer only reads state.
2. Every attack, enemy, item and loot table is JSON. Code supplies behaviours, data supplies content.
3. Every bug fix or formula gets a pytest.
4. Offline tools are resumable and cache by content hash. Never pay twice for the same asset.

---

## 4. Project layout

```
Lycantrope/
├── IDEAS.md  ROADMAP.md  IDEAS_STATUS.md  ideas_status.json  CLAUDE.md
├── README.md  LICENSE  ASSETS-LICENSE.md  CREDITS.md
├── run_idea_tracker.bat
├── pyproject.toml  requirements.txt  requirements-tools.txt
├── src/lycantrope/
│   ├── main.py                  ← entry point, loop
│   ├── core/       config.py  events.py  input.py  rng.py  save.py  timing.py
│   ├── render/     renderer.py  camera.py  terrain.py  mesh.py  gltf.py  skinning.py
│   │               instancing.py  sky.py  shadows.py  post.py  particles.py  ui_layer.py
│   │               shaders/*.vert|*.frag
│   ├── world/      heightfield.py  biomes.py  scatter.py  collision.py  waystones.py  spawns.py
│   │               incursions.py (rifts, waves, sealing: M2)
│   ├── combat/     attacks.py  hitbox.py  damage.py  status.py  lockon.py  feel.py (hitstop/shake)
│   ├── actors/     actor.py  player.py  valor.py  enemy.py
│   │   └── ai/     fsm.py  archetypes.py  tokens.py  steering.py
│   ├── rpg/        stats.py  skills.py  leveling.py  inventory.py  loot.py
│   ├── audio/      mixer.py  voice.py  music.py
│   └── ui/         hud.py  menus.py  levelup.py  subtitles.py  fonts.py
├── data/           enemies/*.json  attacks/*.json  items.json  loot.json  biomes.json  incursions/*.json
│                   xp.json  voices.json  lines.csv  sfx.csv
├── assets/  (Git LFS)  models/  textures/  audio/{vo,sfx,music}/  fonts/  world/
├── tools/
│   ├── idea_tracker.py          ← done
│   ├── meshy/      batch.py  manifest.json  normalize.py  preview.py
│   ├── voice/      design_voices.py  generate.py  sfx.py  music.py  master.py
│   ├── worldgen/   terrain.py  noise.py  scatter.py  validate.py  textures.py
│   └── credits.py
└── tests/          test_stats.py  test_damage.py  test_data_schema.py  test_save.py ...
```

---

## 5. Current state and next steps

### 5.0 What's built (as of 2026-11-28)

| System | Status |
|---|---|
| Terrain: 4-biome map, LOD, splat textures, sky, fog, water | Done |
| Brackenvale village: 19 untextured props, fences, roads, day/night | Done |
| HD trees from Tripo3D (two oaks, birch, yew, willows, hawthorn, maples, apple; TRE-19 to TRE-22); flowers and brambles removed (ferns kept) | Done |
| Tree rendering: shorter draw distance, 8-view impostor cut-outs past 150 m, Hi-Z occlusion culling (OpenGL 4.3 compute) | Done |
| Title screen with 3 save slots; saves at Waystones; test runs never touch the slots (UIX-27, TEC-16) | Done |
| Pause menu (Inventory, Character, Settings, Game), 20-slot backpack, equip with stat preview, looting enemies and chests (UIX-07, UIX-26, WLD-17) | Done |
| Requirements: underpowered weapons, catalysts and armor still work at a penalty (WPR-03, ARS-01); roll speed by equip load (CMB-26) | Done |
| Rowan's model wears what's equipped: chainmail pieces per slot, the main-hand weapon (and on his back when sheathed), shield or Tome | Done |
| Enemies drop only the weapons and shields they carry | Done |
| World map (M), compass strip, region banners (UIX-02); debug overlay off by default | Done |
| Waystone rest and fast travel | Done |
| Poise rework: gradual regen, stagger grace for Rowan, half poise damage mid-swing (no more wolf stun-locks) | Done |
| Ward Rite with the Tome of Wards: absorb shell, Faith- and catalyst-scaled cooldown (CMB-29, CMB-34, MAG-11) | Done |
| Night-only spawns (WLD-11): cultists at Bracken Mere, a Men of Leng camp at Old Watch Beck (3 raiders + Raid-Captain) | Done |
| Tripo3D characters: cultists (DRM-37) and Men of Leng (DRM-36) rigged and animated on the Tripo website; Leng Sabre (ONE-18) held and lootable | Done |
| CODEBASE.md: how the renderer, assets and systems work | Done |
| Third-person orbit camera, lock-on, strafing | Done |
| Rowan movement: walk/run/sprint, jump, fall damage (4 m safe, 15 m lethal), stumble, landing roll | Done |
| GPU skinning with 0.15 s crossfades; Rowan's full animation set including roll | Done |
| Stat model: 6 attributes → HP, Stamina, EquipLoad, Crit, RecoverySpeed, RadiantMult, RiteCooldown | Done |
| Per-type armor (slash/strike/pierce/fire/frost/radiant) and damage formula | Done |
| Use-based skills skeleton with perk milestones | Done |
| Waystones: rest, refill flask, partial save, respawn enemies | Done |
| Day/night cycle with biome music | Done |
| Goblin, wolf, bear enemies with wander/chase/attack AI | Done |
| Meshy / Tripo3D batch tools, voice design tools, props pipeline | Done |

---

### 5.1 Core loops (todo.txt — first priority)

These are the gaps that make the game feel incomplete to any tester.

Save files, the title screen, the pause menu, inventory, equipping and looting are done (§5.0). Still open from them: quick-slot items, and models for the chests (INT-02) and for the armor sets beyond chainmail, so they show on Rowan too.

**Greetings / Talk / Dialogue / Choices / Quests** *(NPC-18, UIX-28, NPC-15, NPC-02)*
- A-press talk trigger with camera pull-in
- Branching dialogue with 1–4 choice prompts; trees in `data/dialogue/*.json`
- Quest log: add entry, track active, mark resolved; pin one entry to show compass marker on HUD (UIX-28)
- Context-aware greeting selection based on time, weather, prior interaction (NPC-15)
- Revise Brackenvale NPC lines for Aldmoor's anxious-but-holding-together tone (RPG_CLONES.md §1.2)

**Contracts** *(WLD-46, STY-22, STY-23, UIX-29; NPC-20 awaiting)*
- Notice boards in Brackenvale and the roadside inns; contracts as data (`data/contracts.json`: monster, lair, payout, optional choice)
- Taking a contract marks its area on the map and pins it in the quest log
- Contracts that end in a choice (STY-22), stored as save flags that later events check (STY-23)
- Bestiary tiers (UIX-29): read, seen, fought; each tier reveals more (lore, the Rite it fears, its opening). No oils (your note)
- Haggling over the reward (NPC-20) if you approve it

**Upgrade / Forge** *(CMB-24, NPC-07)*
- Smith NPC Gerda Vane in Brackenvale; talk trigger, then forge UI
- Weapon upgrade: spend brightstone to restore the weapon's edge (framing per RPG_CLONES.md §2.4; not "craft a better one")
- 3-tier upgrade path per weapon; show damage delta before confirming

**Shop / Shop inventory** *(NPC-19)*
- Merchant NPC with 8-slot rotating stock
- Currency: copper shards from enemy loot, gold from quest rewards
- Buy/sell interface from inventory grid

---

### 5.2 World, NPC and AI (todo.txt — second priority)

**Better NPC system: dynamic faces and outfits** *(ART-20, WLD-26, WLD-33–38)*
- Generate 3–4 alternate head meshes per body type with Meshy or Tripo3D (different jaw, nose, brow); character system picks one by NPC seed — same mesh-swap approach as armor pieces (ART-20)
- Each NPC draws its own mix of outfit pieces (hat, coat, trousers) from the WLD-26 kit on top of a tint and height variation, so a few generated parts give dozens of distinct looks
- Alternative: whole pre-dressed villager models (WLD-33–38) for the named NPCs where layering causes clipping

**NPCs going home at night** *(NPC-16)*
- Daily schedule: each NPC has 2–4 waypoints with time-of-day windows; they walk to them and idle
- NPCs return home after sunset

**NPC weapons / NPC fights / Guard AI** *(NPC-17)*
- Guards and named combat NPCs carry weapons and use the melee-basic FSM
- Guards move to assist if they hear combat within 20 m
- Killed NPCs drop the weapon they carry (enemies already do)

**Beginning plot** *(STY-21)*
- Cold open: Brackenvale already under strain — feed shortage, overdue merchant, Watch captain on no sleep
- Rowan has the sword at the start (dull, carried because it was grandfather's); it wakes when Rowan decides not to run
- The goblin raid arrives as confirmation of a fear, not a shock from nowhere (RPG_CLONES.md §1.1)

**Bandit / Goblin / Cultist camps** *(WLD-44)*
- 3–5 POI camps placed in the starting region
- Simple patrol routes, lootable chest at center, respawn after 3 Waystone rests
- Give the night camps (cultists at Bracken Mere, Men of Leng at Old Watch Beck) props: tents, a fire, a chest

**Roadside inns** *(WLD-48)*
- Small hubs on the roads between villages: a notice board, a fire to rest at, a cook and a merchant (no card table, per your note)

**Remap starting area** *(WLD-45)*
- Adjust terrain around Brackenvale: visible watchtower ruin on the ridge, road narrowing toward the Wolfwood, one clear sightline to Duskhold
- The map has no sea yet (only lakes and rivers). A coastline is needed before the Drowned Coast, the galley incursion and any coastal camps

---

### 5.3 Feel, content and performance (todo.txt — third priority)

**Colorizing / Shading** *(ART-22, WLD-41)*
- One color palette pass per biome: vale (muted green-gold), Wolfwood (deep blue-green), Frostfang (grey-white), Ashen Reach (ash and amber)
- Fix slope blend seam colors (WLD-41)

**Caves** *(WLD-07)*
- The world map, compass and region names are done. Next: one hand-placed cave entrance near Brackenvale as proof-of-concept for interior lighting
- Quest pin on the compass once the quest log exists

**Performance** *(TEC-19)*
- Tree impostors, a shorter tree draw distance and Hi-Z occlusion culling are done
- Profile skinned mesh count, terrain draw calls, and shadows at the worst-case scene
- Activation radius: enemies beyond 60 m run no AI tick; cap at 25 active skinned characters

**Controller support** *(UIX-11)*
- `pygame.joystick`: deadzone, stick-to-movement, face buttons for attack/dodge/interact
- Rumble on hit via `pygame.joystick.set_rumble`

**More tree types** *(WLD-39)*
- Brackenvale's trees are now HD Tripo3D models. Next: 2–3 HD variants for the Wolfwood (gnarled, dead-but-standing, mossy)
- Dense canopy placement to obscure enemy sightlines (addresses ART-21 silhouette goal)

**Ground cover**
- Replacements for the removed flowers and brambles that match the HD trees, and leaves on the ground

**More monsters** *(ENM roster, MON-\* enemies)*
- Build out the enemy roster toward M1's 20 with Meshy (§9.1) and Tripo3D
- Next from the Dreamlands roster: zoogs, ghasts, the Shantak Rider; then the moon-beasts that command the Men of Leng
- Prioritize biome variety: at least 3 distinct enemy types per biome
- Goblin spellcaster (ENM-07) already approved; queue with the next Meshy or Tripo3D batch
- Chickens for the farms

---

### 5.4 Improvements queued after todo.txt

These are the new ideas added 2026-11-26. Work through them once the todo.txt items above are done.

| Idea | What |
|---|---|
| WLD-42 | More house types in Brackenvale |
| NPC-15 | Context-aware greeting selection (also feeds §5.2 above) |
| UIX-23 | Closer default camera orbit distance |
| UIX-24 | Zoom cap to prevent overworld cheating |
| UIX-25 | Compact debug overlay |
| WLD-43 | Enemy species vary by zone |
| RPG_CLONES.md fixes | Brackenvale tone pass (§5.2), sigil slots rename (done), cold open STY-21 (§5.2) |
| CMB-48 | Quick Rites mid-swing: a weaker one-handed cast that cancels a light attack's recovery |
| Contracts | WLD-46, STY-22, STY-23, UIX-29 (in §5.1) and WLD-48 (in §5.2). The Witcher-inspired ideas that were denied (HER-11, CMB-46, CMB-47, STA-30, WLD-47, NPC-21) have no tasks |

---

## 6. If a day overruns: cut in this order

1. Music (use ambience only) → 2. shadows → 3. fast travel → 4. crossbow (fliers come down lower instead) → 5. a second and third Rite → 6. enemies 13–20 (move to Week 2).
**Never cut:** hit feel (CMB-14), lock-on, dodge, block and stagger, XP and leveling. Those *are* the game.

---

## 7. Starting numbers (tune them in JSON)

### 7.1 XP
```
xp_to_next(L)     = round(100 * L ** 1.5)                 # L1→2: 100, L10→11: 3162, L20→21: 8944
enemy_xp(lvl)     = round(12 * lvl ** 1.35)               # rat L1: 12, spider L5: 106, golem L16: 512
level_mult(d)     = clamp(1 + 0.12 * d, 0.25, 2.0)        # d = enemy_level - player_level
elite             = x2,   boss = x10,   Shadow Moon = x1.5
```

### 7.2 Attributes → derived stats (all attributes start at 10)
```
soft(x) = x if x <= 20 else 20 + (x-20)*0.6 if x <= 40 else 32 + (x-40)*0.25
HP          = 300 + 30 * soft(Vigor)
Stamina     = 90  + 3  * soft(Endurance)
EquipLoad   = 40  + 1.5 * Endurance
Crit chance = 5% + 0.8% * soft(Fortune)
Attack recovery = base * (1 - 0.004 * soft(Dexterity))       # up to ~15% faster recovery (STA-16)
Radiant damage mult = 1 + soft(Faith) / 40                   # Dawnblade light, holy water, blessed bolts (STA-20)
Rite cooldown = base * max(0.6, 1 - 0.01 * soft(Faith))       # CMB-34
Lifewater heal = base * (1 + soft(Faith) / 80)
```

### 7.3 Damage
```
raw   = weapon.base * motion_value * (1 + scaleMight*soft(Might)/40 + scaleDex*soft(Dexterity)/40 + scaleFaith*soft(Faith)/40)
        * (1 + skill_level/200)                                  # use-based skill bonus
after = raw * raw / (raw + target.defense)                       # flat defence falls off on big hits
final = after * (1 - target.resist[type]) * crit(2.0)
poise_damage = attack.poise * (1 + soft(Might)/60)
```

### 7.4 Skills improve by use
Each skill goes from 1 to 100. `skill_xp_needed(s) = 25 + 2.5*s`. XP per event: a hit is +1 (+2 on a crit), a successful block +1, a dodge that avoids a hit +2, a Rite that lands +2, a sprint second +0.2 (Athletics). Perk choices at 10, 20, …, 100.

---

## 8. Data shapes

**`data/enemies/bandit_brigand.json`**
```json
{
  "id": "bandit_brigand", "name": "Bandit Brigand", "archetype": "melee_basic",
  "level": 3, "biomes": ["vale", "roads"], "model": "models/bandit.glb",
  "stats": { "hp": 220, "poise": 30, "defense": 25, "stamina": 100 },
  "resist": { "slash": 0.0, "strike": 0.0, "pierce": 0.0, "fire": 0.0, "frost": 0.0, "radiant": 0.0 },
  "ai": { "aggro_range": 18, "reaction_ms": 380, "block_chance": 0.35, "flee_hp": 0.0 },
  "attacks": ["bandit_slash", "bandit_overhead", "bandit_shield_bash"],
  "barks": { "spot": "bandit_spot_*", "attack": "bandit_effort_*", "pain": "bandit_pain_*", "death": "bandit_death_*" },
  "loot": "bandit_common", "xp_mult": 1.0
}
```

**`data/attacks/rowan_ls_light1.json`** (frames at 60 Hz)
```json
{
  "id": "rowan_ls_light1", "anim": "attack_light_1", "stamina": 14,
  "windup": 9, "active": 5, "recovery": 16,
  "cancel": { "into_light": [18, 30], "into_dodge": [20, 30] },
  "hitbox": { "bone": "hand_r", "shape": "capsule", "radius": 0.12, "from": [0, 0, 0], "to": [0, 1.05, 0] },
  "damage": { "type": "slash", "motion_value": 1.0 }, "poise": 12,
  "hitstop_ms": 60, "shake": 0.15, "sfx": "swing_light"
}
```

**`assets/manifest.json` (Meshy)**
```json
{ "style": "stylized dark-fantasy, hand-painted textures, chunky readable silhouette, muted earthy palette, game-ready low-poly",
  "items": [
    { "id": "rowan_human", "kind": "character", "prompt": "...", "polycount": 25000, "rig": "humanoid",
      "animations": ["idle", "walk", "run", "roll", "attack_light_1", "..."] },
    { "id": "tree_wolfwood_pine_a", "kind": "prop", "prompt": "...", "polycount": 1500 }
  ] }
```

**`data/lines.csv` (ElevenLabs)**
```
id,speaker,text,tags,takes
rowan_levelup_01,rowan,"Stronger. Doesn't mean better.",,3
bandit_spot_01,bandit,"[shouting] Oi! Nice coat — I'll take it!",,2
bandit_pain_01,bandit,"[grunts] Argh — lucky shot!",,2
```

---

## 9. Asset budget for the First Playable

| Kind | Count | Source |
|---|---|---|
| Rowan + the Dawnblade (4 stages) | 1 rigged character + 4 sword models | Meshy or Tripo3D (image-to-3D or text-to-3D), plus rigging and animation |
| Enemies | 20 (+ Grimtooth) | Meshy or Tripo3D. Humanoids rigged by Meshy; animals and creatures animated in code (ART-04). Until 2026-12-23 there are 1,000 extra Meshy credits: see §9.1 |
| Props | ~45 ⭐ objects from [OBJECTS.md](OBJECTS.md) (145 listed in total) | Meshy or Tripo3D |
| Terrain textures, sky, color-grading LUTs | all | Python scripts and shaders (ART-08, ART-09, ART-12) |
| Effects (Rites, flames) | ~8 ⭐ meshes from OBJECTS.md §13 | Meshy or Tripo3D (ART-19) |
| Voice lines | Rowan ~40, enemy barks ~14 × 12 voiced types ≈ 170, ×2–3 takes | ElevenLabs TTS |
| SFX | ~80 | ElevenLabs Sound Effects |
| Music | 4 biome tracks + 1 combat layer + 1 boss | ElevenLabs Music (or ambience only) |

Check your Meshy, Tripo3D and ElevenLabs credit balances against this list on Day 1. Generate **previews** first and refine only the ones you keep.

**Tripo3D in practice** (see CODEBASE.md): models are generated through the Tripo MCP (HD model, T-pose for characters), downloaded and run through `gltfpack` to remove meshopt compression. Rigging and animation happen on the Tripo website (Auto Rig, then presets, then a GLB export with animations), because the MCP's retargeted clips can't be downloaded. The website's "defeat_02" preset exports as `defeat_03` (the fall to the ground).

### 9.1 Meshy budget until 2026-12-23: 1,000 credits

Credits ran out again on 2026-11-26; 1,000 extra credits are being added now to cover the gap until the monthly refill on 2026-12-23. Meshy prices (from `tools/meshy/batch.py`): preview 20, texture 10, rig 5, each animation 3. A new rigged, animated humanoid costs about **55** (preview, texture, rig and 6 animations), or about **80** with one re-roll. A new prop is about **25–30** (preview + texture, no rig).

| Priority | What | Credits |
|---|---|---|
| 1 | **Enemy roster** toward M1's 20: Skeleton Warrior, Bandit Brigand, Bandit Crossbowman, Goblin Hexer (ENM-07), Orc Berserker, Werewolf / Grimtooth (BOS-01), Giant Rat — prioritize biome variety; reuse rigs where a recolour + new stats will do | ~400 |
| 2 | **More tree types** (WLD-39): 2–3 Wolfwood variants (gnarled pine, dead-standing, mossy oak) | ~60 |
| 3 | **More house types** (WLD-42): 3–4 Brackenvale building variants to break up the village | ~90 |
| 4 | **Per-NPC face variants** (ART-20): 3–4 head variants × existing body types (previews only; texture and swap by script) | ~80 |
| 5 | **Reserve** for re-rolls, extra animations, Wolfwood props for M2 | ~370 |

Not on Meshy or Tripo3D this month: the Bog Ooze, the Wraith and the Mimic Chest can be static meshes or code-driven. Check the running total after each batch — previews first, re-roll only what's clearly wrong.

---

## 10. After Week 1

| Phase | Focus | Key ideas |
|---|---|---|
| **Week 2: Finish M1** | All 20 approved enemies plus approved MON- enemies, every bark, settings, accessibility, bug fixes. New Meshy models come from the 1,000-credit budget in §9.1; the rest of the roster reuses the rigs on hand (new colours, scale, stats and attacks) or is animated in code (ART-04) until the monthly credits return on 2026-12-23 | ENM list, ENEMIES.md, UIX-12, ART-04 |
| **Weeks 3–5: M2 Vertical slice** | The boss framework first: bosses as data with scripted moves, two phases changing at 50% HP with a beat between, one idea per boss, non-kill wins, retry at the arena door, and a debug teleport to any boss. Then Act I opening: Rowan's dream of Serannian, farm chores with the Thing in the Cellar as the tutorial boss, Aldric arrives (the horror in the jar), Mindspeak, training with Captain Thorne. Rift sealing and incursions as data. The first incursion at the burying ground, fused with the village prologue (zoogs, Men of Leng, Oswin wounded on his doorstep), and its fight, the Unwritten Gate. Then the Wolfwood Crown Shard dungeon (kit + grappling chain), Brood Queen, compass, bestiary, music layers | DRM-03, DRM-10, DRM-11, BOS-18, BOS-16, BOS-17, BOS-12, BOS-13, BOS-14, BOS-15, TOL-08, DRM-06, DRM-16, DRM-18, DRM-19, DRM-12, DRM-54, DRM-35, DRM-36, STY-14, STY-15, WLD-14, WLD-15, BOS-02, UIX-02, UIX-08, AUD-07 |
| **Weeks 6–8: M3 Demo** | Second incursion at the stone circle (ghasts and light, cultists, the Apprentice at the Stones). Third incursion, the galley from the clouds (moon-beasts), ending on the rift that can't be closed from this side, and the Shantak Rider. The Blackmire Crown Shard + Old Mother Mire. Brackenvale sidequests from the public-domain tales, with their creatures. Found documents with clues. Relic powers, Seer's Lens, perks, armor sets | DRM-13, DRM-55, DRM-37, DRM-38, DRM-14, DRM-39, DRM-15, DRM-40, BOS-03, DRM-17, DRM-48, DRM-49, DRM-50, DRM-51, DRM-52, DRM-64, DRM-26, VAL-03, VAL-06, STA-08, ARMOR.md |
| **Later: M4, Part II** | The descent through sleep (the seventy steps, the Cavern of Flame, the Gate of Deeper Slumber). Then the Enchanted Wood (the Hostage-Keeper), Ulthar and its cats, Dylath-Leen (the Factor chase), Celephaïs (Carter, Kuranes and the Silver Key), Ngranek (the night-gaunts), the Underworld (ghouls, gugs, the Gug Warlord, dholes), Leng (the High Priest, the spider). Then Serannian restored (the Wound over Serannian). The two Dreamlands Crown Shards replace two of the original dungeons: Frostfang becomes the ghouls' vault of fallen things (boss: the Vault-Wyrm), and Ashen Reach becomes Serannian (boss: the Black Marble Colossus). Optional: the Quarry of Inganok, Kuranes' Dream. | DRM-27, DRM-56, DRM-44, DRM-57, DRM-30, DRM-24, DRM-58, DRM-41, DRM-42, DRM-43, DRM-59, DRM-46, DRM-60, DRM-45, DRM-31, DRM-61, DRM-28, BOS-20, BOS-23, DRM-29, DRM-74, DRM-75 |
| **Later: M4, the end** | The return, the Drowned Coast and its Deep Ones, the Crypts, Duskhold, Malgrath as the final boss, allies who remember coming back for the finale, the Dawnblade's origin (grandfather was the fisherman who found it in his net), echoes in the blade leading to the Silver Key's last turn (play the Night of the Rising Star as the hero of old, the last knight of the Crown's order, and pass his gift into the sword), the testament frame, and the closing hints that Nyarlathotep arranged everything (never met, never named). Armor swaps, mount, Lua mods | BOS-11, DRM-53, DRM-29, DRM-07, DRM-77, DRM-78, DRM-79, DRM-80, DRM-81, DRM-82, DRM-09, DRM-08, DRM-76, HER-07, CMB-32, TEC-20 |
| **Much later** | Player beast forms: the Dream-Shapes (cat, ghoul, night-gaunt) | DRM-25 |

### 10.1 Story decisions (answered 2026-11-25)

- **The Dawnblade's origin:** grandfather was the fisherman who found it in his net, so STY-14, HER-09 and DRM-07 all hold.
- **The Apprentice is Sir Calder** (STY-19, DRM-08). His appearances are the Apprentice's fights: the Stones, the Factor chase, the High Priest of Leng.
- **Moon-beasts** get a simpler fighting style instead of swelling and shrinking: a plain heavy melee enemy that commands the Men of Leng.
- **The Dreamlands shards:** Frostfang → the ghouls' vault, Ashen Reach → Serannian. Their bosses BOS-04 and BOS-05 are replaced by the Vault-Wyrm (BOS-20) and the Black Marble Colossus (BOS-23).
- **The time loop:** no travel into the past. The Silver Key's last use lets Rowan play through the eyes of the hero of old, who passes something on to the sword. See DRM-77 to DRM-82; the hero of old is the last knight of the Crown's order (DRM-79 a). Its daily rewind (DRM-24) restores position and HP only, because Dread was denied.
- **Beast forms (DRM-25)** are allowed but saved for much later, and CLAUDE.md now says so.
- **Deep Ones (DRM-53)** stay, on the Drowned Coast.
- **No Black Tongue lesson** in Act I and no replacement (DRM-10).

**Still awaiting a decision, so not scheduled yet:** DRM-66 to DRM-70 (Grandmother Zoog, the Drum-Master's Galley, the Gug Sentinel, the Shantak Roost, the Moon-Beast Admiral). Bosses have no parry windows (your note on BOS-16).

---

## 11. Risks

| Risk | What to do |
|---|---|
| Python too slow with many skinned enemies | GPU skinning, numpy for animation sampling, activation radius, cap of about 25 active enemies. Profile before optimising (TEC-19). |
| Meshy rigs or animations don't import cleanly | Normalize every GLB in `normalize.py`. Test the import on Day 2 with Rowan before batching the rest. Fall back to procedural animation (ART-04). |
| AI models don't look like they belong together | One style suffix, shared fog and color grading (ART-02, ART-12). Re-roll the outliers. |
| Combat doesn't feel good | Tune hitstop, wind-ups and the input buffer *before* adding content. Playtest every day. |
| Only 1,000 Meshy credits until 2026-12-23 | Spend them in the order of §9.1 and check the running total after each batch. Previews first, re-roll only what's clearly wrong, and reuse rigs wherever a recolour will do. |
| Credit burn | Previews first, caching by hash, never re-generate a line whose text hasn't changed. |
| Asset terms change | Log plan and date per asset; re-read both services' terms before each public release (REL-04). |
| The Dreamlands roughly double the game | Part II is M4 work. Ship the waking-world half (M3) as a complete demo first, and reuse rigs wherever possible: rats for the rats in the walls, the goblin rig for the Lurking Fear, the Brood Queen for the Spider of Leng, one cat model for allies, Ulthar and Saturn. |
| Many new creatures need procedural rigs | Ghasts, moon-beasts, Shantaks, dholes and Things from Beyond are animated in code (ART-04). Prototype one hopper (the ghast) and one big flyer (the Shantak) early in M3, before committing to the rest. |
| Scope creep | Anything not ⭐ waits until M1 ships. Add new ideas to IDEAS.md, where they start as Awaiting. |
