# Vibecode3D Library (the launcher)

The library app for an installed PC (`install/LAYOUT.md`): Steam's library window for the
Vibecode3D install on V:, made in OXT-Beyond. Draft 1, Opus, 15 Nov 2026.

- `vibe_launcher.livecodescript` is the whole app: the stack script makes its window
  the first time it opens.
- `Vibecode3D_Launcher.livecode` is the stack saved with that script, which is what gets built.
- `build/Vibecode3D Library/Vibecode3D Library.exe` is the standalone (64-bit only: Windows 32-bit off in the
  standalone settings, so there is no `Windows x86-64` folder; owner, 23 Nov). `install/vibeinstall.py`
  copies it to `Program Files (x86)\Vibecode3D\` beside `Vibecode3D.exe`.

## What it does

| Started | It shows |
|---|---|
| with no arguments | the library: every title in every library folder (`vibeapps\` beside the exe, then `libraryfolders.txt`), filtered by All, Games, Betas or Tools, with the game's header text and its app id, size and folder |
| `"Vibecode3D Library.exe" -game <folder>` (or just `<folder>`) | that game in its own window; closing the window ends the program |

- **Play** (or Enter, or a double-click) starts a second copy of the program with the game's
  folder. That's one game per program, because the engine keeps its state in globals.
  Closing the library leaves games running.
- **Show Folder** opens the game's folder in Explorer.
- **Verify Files** checks every folder: game.txt, the script, the data folders, the manifest
  and the engine in Vibecode3D Common.

`game.txt` in each folder is the truth; the appmanifests only give the date and size.

## What it loads to play

It loads everything from `vibeapps\common\Vibecode3D Common\Engine\`, which the installer
fills from the projects:

- `vibe_engine_xt3d.livecodescript`
- `game_player.livecodescript`: the installed copy logs errors to `the uErrorFile` the launcher
  sets, `%LOCALAPPDATA%\Vibecode3D\logs\game_errors.txt`, instead of the owner's inbox
- `GameNotes.livecodescript`

It never uses a path to the owner's PC, but the games' own data lookups still do
(LAYOUT.md finding 1, the `Game.FindFile` fix). Skins aren't loaded.

## Build (OXT-Beyond)

The stack's `cRevStandaloneSettings` are: name `Vibecode3D Library`, Windows only, inclusions
searched. Run `revSaveAsStandalone "Vibecode3D_Launcher", <LIB_PUBLIC/launcher/build>`, then
`python3 -I install/vibeinstall.py install` to put it on V:.

Test: `OXT-BEYOND/tests/t27_vibe_launcher.txt` runs headless on the V: install: 50 titles,
the filters, Verify, and Bounce Rally opened and drawn from the installed engine.
