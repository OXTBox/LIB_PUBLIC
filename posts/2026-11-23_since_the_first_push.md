# OXTBox: what's new since our first push (20 - 23 Nov 2026)

Everything here is plain xTalk (the HyperCard family of languages), running in OXT-Beyond, and it
all lives at github.com/OXTBox.

**New games**
- **Corridor Lab**: a first-person corridor shooter drawn by our new raycaster. Three looks: solid
  walls, see-through Vibecode3D "glass", or lines only. It runs at about 30 fps.
  Dedicated to the memory of **Scott McDonald** (The LiveCode Lab). Level 1 is his own map.
- **Meadow Marsh**: the first playable step of a "make your own RPG/MMO" tutorial. Command a horde
  across rolling hills and cast spells with mana.
- **Lantern and Ladders**: climb a dark tower by torchlight.
- **Eagle Dive**: dive over wire hills and lakes for fish.
- **Cone Probe 3D**: Probe vs Cone in third person, with a power bar.
- **Spell Splat**: an energy-weapons duel (PROMPT vs GLAZE).
- **Dot Maze**, rebuilt "lean": from 7 fps to 30 fps.

**Better games**
- **Squad Buggy**: a wider view, and grenades that dig into the land ahead or behind you.
- **Big Ball of Vectors**: hazards now rain onto the board.
- **Bounce Rally**: hit cars spin out.
- **Deep Dive**: a preferences panel.
- **Interceptor Run**: a helicopter with a turret.
- **Grid Sprint**: an open grid.
- **Stack Down**: a gently swaying well.
- **Tabletop Racers**: a 3-2-1-GO grid start.
- **Crater Crawler**: wheels that roll the right way.
- **Shaft Descent**: a run key.
- **Photon Ball**: difficulty set per match.
- Arrow keys and Tab can no longer knock a game off its card.

**Engine and tools**
- **LIB_RAYCAST**: a grid raycaster in xTalk. Rays that hit one wall become one polygon (Scott's
  idea), corners are exact, monsters hide behind walls, and you slide along walls.
- **Loading screen + level reveal**: every game's level change now goes through a short "burn"
  transition. The player appears first, then the level grows in around them.
- **Lean style**: turns a rough level built from cubes into a clean outline, with about 60% fewer
  lines.
- **Console**: type commands into the iGame3D XT editor and the xRay games bench.
- **LIB_EMITTERS + LIB_POWERBAR**: an energy-weapons editor and a paged power bar.
- **City Editor**: a huge block city from a height map.
- **TTRPG Studio**: a World panel.
- **Vibecode3D Library**: numbered titles.
- **Play reports**: a small tester pack that gathers what was played.
- **xTalk to Python** (xtalk_py): 335 of 335 test cases now give the same answers in both.

**Thanks**
- To our first outside play tester, whose notes drove most of this week's fixes.
- To Seth Morrow for OXT-Beyond.
