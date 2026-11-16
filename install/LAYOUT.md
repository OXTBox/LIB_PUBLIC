# Where Vibecode3D goes on a Windows PC

Sunday, November 15, 2026. Draft 1 (Claude, Opus 5.5), from the owner's request: "set up a
standalone installation of vibecode3d like steam and its assortment of games, follow the whole
common folder pattern". `vibeinstall.py` builds exactly this on V:, which stands in for an
ordinary PC's C: drive. The owner decides; nothing here is in the engine yet.

## 1. The pattern, side by side

| What | Steam | Vibecode3D (this install) | Windows' rule |
|---|---|---|---|
| The program | `C:\Program Files (x86)\Steam\steam.exe` | `Program Files (x86)\Vibecode3D\Vibecode3D.exe` + `Externals\`, `revsecurity.dll` | Program Files is read-only for normal users after install |
| The library | `Steam\steamapps\` | `Vibecode3D\vibeapps\` | |
| One folder per game | `steamapps\common\<Game>\` | `vibeapps\common\<Game>\`: the play script, its data, `game.txt`, `Play <Game>.cmd` | |
| What is installed | `steamapps\appmanifest_<appid>.acf` | `vibeapps\appmanifest_<appid>.txt` (same KeyValues look) | |
| More libraries | `steamapps\libraryfolders.vdf`, `D:\SteamLibrary\steamapps\` | `vibeapps\libraryfolders.txt`, `D:\...\vibeapps\` | |
| Shared runtimes | "Steamworks Common Redistributables" (appid 228980) | `common\Vibecode3D Common\` (appid 1000): Sequencer, LIB_BIT, LIB_MAP, LIB_MOCAP, LIB_GENERICA, LIB_MCP assets | |
| Mods | `steamapps\workshop\content\<appid>\` | `vibeapps\workshop\content\<appid>\` (made, unused yet) | |
| Downloads in progress | `steamapps\downloading\`, `temp\` | the same names | |
| Per-user settings | `Steam\userdata\<id>\` and `Steam\config\` (in Program Files) | `%APPDATA%\Vibecode3D\` (`config.txt`, `engine_path.txt`, `data_root.txt`) | Roaming AppData: settings that follow the user |
| Logs, crash dumps, cache | `Steam\logs\`, `Steam\dumps\` | `%LOCALAPPDATA%\Vibecode3D\logs`, `crashdumps` | Local AppData: this machine only, safe to lose |
| Saves | each game picks: `Documents\My Games\`, `Saved Games\`, `AppData\LocalLow\<Studio>\`, `userdata\<id>\<appid>\remote\` | `Documents\Data\Users\<user>\Saves\<Game>\` (LIB_DATA's Data folder) | Documents: the user's own, backed up, visible |
| Tell the AI (the vibe) | none | in any game, ` or F2 opens the note box; each note is `Documents\Data\Games\<Game>\LIB_LLM\tell_<YYYY-MM-DD_HHMMSS>.txt` (game, when, the game's state, the note), for the player's own AI to read | Documents: the player's, survives a wiped AppData and an uninstall |
| Start a game from outside | `steam://rungameid/<id>`, a desktop `.url` | `vibecode3d://run/<appid>` (written in `_simulated_registry.reg`, not registered), `Play <Game>.cmd`, `-game <folder>` | |
| Shortcuts | Desktop + Start Menu | Desktop `.lnk` + `ProgramData\Microsoft\Windows\Start Menu\Programs\Vibecode3D\` | |
| Uninstall | registry `Uninstall\Steam`, deletes `steamapps` with it | `uninstall.log` lists every file; settings and saves are left (as real uninstallers do) | |

Where we differ from Steam, on purpose: Steam keeps settings and cloud saves inside Program
Files and makes its own folder writable to get away with it. Vibecode3D follows Windows'
rules instead (settings in AppData, saves in Documents), so a non-admin PC still works.

## 2. On V: now

```
V:\Program Files (x86)\Vibecode3D\
    Vibecode3D.exe  Externals\  revsecurity.dll       the engine (the standalone build of Vibecode3D)
    install.txt  uninstall.log  _simulated_registry.reg
    vibeapps\
        libraryfolders.txt  appmanifest_1000.txt ... appmanifest_1500.txt
        common\
            Vibecode3D Common\   Sequencer\  LIB_BIT\  LIB_MAP\  LIB_MOCAP\  LIB_GENERICA\  LIB_MCP\
            Antack\              Vibecode3D_Play_Antack.livecodescript  Antack\antack_data.txt
                                 game.txt  Play Antack.cmd
            ... 50 titles (catalog.tsv): 29 public games from LIB_GAMES main, 16 betas from
                spark-roadtrip and vector-toss (Steam's "betas"), 5 tools
        downloading\  temp\  workshop\content\
V:\AppData\Roaming\Vibecode3D\    config.txt  engine_path.txt
V:\AppData\Local\Vibecode3D\      logs\install.log  crashdumps\
V:\Documents\Data\                ROOT.md  Users\default\Saves\<Game>\  Games\<key>\LIB_LLM\tell_*.txt
V:\Desktop\Vibecode3D.lnk
V:\ProgramData\Microsoft\Windows\Start Menu\Programs\Vibecode3D\Vibecode3D.lnk
V:\_SimPCs\<persona>\C\ D\ E\      one simulated PC per persona (escape_sim.py)
```

The owner's own folders on V: (`Documents\Best_of_BILLS_TTRPG` and the rest, `APPS\`,
`Screenshots\`) are not touched.

## 3. game.txt: every game folder says what it is

```
appid   1020
name    Antack
kind    game            (game, tool, redist)
script  Vibecode3D_Play_Antack.livecodescript
data    Antack
branch  public          (public, beta)
ref     main            (the LIB_GAMES branch it came from)
engine  0.1.0-sim
```

A loose copy of the folder (on a USB stick, in a backup, sent to a friend) still says what it
is, so the launcher never has to trust an appmanifest over the folder.

## 4. What the simulation found (details: ESCAPES_RESULTS.md)

1. **The games find their data only on the owner's PC.** Antack, uDead, Thrmnlra, Vector Toss,
   Face, Genetic Anomaly, Amazing Couple and the iGame3D Editor look for
   `LIB_GAMES/Vibecode3D_Games/...` up to six folders above the engine and then in
   `//wsl$/Ubuntu/home/igame3d/projects/`. Installed anywhere else, that fails.
2. Moving the library, a new USB drive letter, a wiped AppData and running from inside the zip
   each break something that the design below fixes.
3. Real Windows: see the probe table in ESCAPES_RESULTS.md ("(x86)" in batch files, Unicode
   through cmd, Mark of the Web and the unsigned exe, long paths, a running exe, read-only
   Program Files).

## 5. The proposed design (what escape_sim.py models as PROPOSED)

1. **`Game.FindFile`**, one shared handler in the engine: the game's own folder first
   (`LIB_GAMES/Vibecode3D_Games/Antack/x` becomes `<game folder>/Antack/x`), then
   `Vibecode3D Common`, then the walk up, never a fixed path to one PC.
2. **The launcher finds libraries** beside the exe, in `libraryfolders.txt`, in `config.txt`,
   and by scanning each drive's top two levels for `vibeapps\common` or loose game folders.
   Library paths on the exe's own drive are written relative to it.
3. **Manifests are a cache.** `game.txt` in the folder is the truth; manifests are rebuilt from it.
4. **Portable mode:** `portable.txt` beside the exe keeps settings and the Data folder beside it.
5. **Run from a zip:** the engine notices `Temp\Temp1_*.zip` or a missing `Externals` and says
   "Extract all first" or "make a shortcut instead".
6. **Settings are disposable.** When the Data folder moves, a forwarding note stays in
   `Documents\Data\ROOT.md`; the engine can find a Data folder by its `ROOT.md`.
7. **Saves** are listed, not named: every `slot*.txt`, with dates; OneDrive conflict copies are
   shown, not ignored; writes go to a temp name and are renamed.
8. **Mods** live in `workshop\content\<appid>\` or `Documents\Data\Games\<Game>\` and load after
   the game; "verify files" keeps a dated copy of anything it would overwrite.
9. **Installers:** a per-user installer (`%LOCALAPPDATA%\Programs\Vibecode3D`, no admin) and a
   plain zip, both writing `engine_path.txt` on first run. Sign the exe before release.
10. **Uninstall asks** before deleting game folders and saves.

## 6. Questions for the owner

- Saves: `Documents\Data\Users\<user>\Saves\<Game>\` (LIB_DATA's Data folder, chosen here) or
  Windows' own `Saved Games\Vibecode3D\` folder?
- Ship `LIB_MOCAP/library` in Vibecode3D Common? It holds Animazoo-derived clips (rights
  unsettled): fine on V:, a release blocker for a public build.
- The 16 spark-roadtrip and Vector Toss games are installed as betas. Should beta games show in
  the launcher by default, or behind an opt-in like Steam's?
