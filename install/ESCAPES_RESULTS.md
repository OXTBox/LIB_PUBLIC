# Escape simulation: results

Sunday, November 15, 2026 20:20. Made by `escape_sim.py`; the scenarios are explained in `README.md`, the personas in `LIB_USERS/personas/PERSONAS.md`. TODAY is the install as built; PROPOSED is the design in `LAYOUT.md` section 5, modelled here, not yet in the engine.

## Personas

| Who | Did | Today | Proposed | Fix |
|---|---|---|---|---|
| dana | installs with every default and plays | BROKEN for Antack, Thrmnlra, Vector Toss, uDead: their data is found only on the owner's PC | WORKS | Game.FindFile: look in the game's own folder, then Vibecode3D Common, before anything else |
| ana | backs up Documents\Data by hand, resets the PC, reinstalls, copies it back; keeps the engine under her own name | saves come back: WORKS; the game's .cmd finds the engine under 'Ana Lucía Peña' | WORKS | saves are plain files under Documents\Data (keep it). Play .cmd runs chcp 65001 before reading engine_path.txt (fixed in vibeinstall.py after this persona found it; see the probe) |
| kenji | starts Canyon from its own .cmd, in the library and from a copy on his kanji Desktop | in the library: WORKS; the copy: WORKS (engine_path.txt) | WORKS | keep Play .cmd free of ( ) blocks; keep engine_path.txt; test every .cmd with a Unicode path |
| morgan | OneDrive moved Documents; plays on two PCs; OneDrive makes a conflict copy | the Data folder is C:\Users\Morgan\OneDrive\Documents\Data if the engine asks Windows for Documents (specialFolderPath, LIB_DATA does); a script that builds %USERPROFILE%\Documents gets C:\Users\Morgan\Documents\Data, which does not exist: an empty Data folder. Conflict copies are ignored silently (2 save files): DEGRADED | WORKS: the save loader lists every slot*.txt, shows dates, and names conflict copies | always ask Windows for Documents (never build the path); load saves by listing, not by one name; write saves to a temp name and rename (OneDrive and crashes) |
| sam | carries the engine and games on a USB stick; at a friend's PC it is F: not E: | 3 titles at home, 2 at the friend's (the second library was written as E:\...): DEGRADED. Settings go to the friend's AppData (there); portable.txt does nothing yet | 5 titles: libraries written relative to the exe when on the same drive, and a drive scan | write library paths relative to the exe when they share a drive; honour portable.txt (settings and Data beside the exe); FAT32 sticks lose Mark of the Web and file times to 2 s |
| riley | drags vibeapps\common to D:\Games to free the small SSD | 0 titles; 7 appmanifests now point at nothing (Steam shows them as 'needs update' and offers to download again): BROKEN | 6 titles: the scan finds D:\Games\vibeapps; manifests are rebuilt from each game.txt | a 'Move install folder' command in the launcher; rebuild appmanifests from game.txt; never trust a manifest over the folder |
| jordan | school PC, not an admin: double-clicks the exe inside the downloaded zip; Program Files is read-only; Defender guards Documents | the engine starts from Temp with 0 games and no Externals (Explorer extracts only the exe): BROKEN. Writing beside the exe in Program Files: refused: access denied. Controlled Folder Access would block the unknown exe writing Documents\Data (simulated; it cannot be turned on here) | 6 titles if Vibecode3D is already installed (config.txt); otherwise the engine says 'unzip me first' when its folder holds no vibeapps or Externals | detect running from Temp\Temp1_*.zip and say 'Extract all first'; offer a per-user install (%LOCALAPPDATA%\Programs\Vibecode3D) that needs no admin; if a Documents write fails, say why and offer another Data folder |
| pat | copies two game folders to D:\MyGames, uninstalls Vibecode3D, double-clicks Play Antack.cmd | uninstall leaves 4 files (settings, saves, logs). The .cmd says 'Vibecode3D is not installed on this PC, or was moved' (clear, but the game cannot run without the engine): DEGRADED | the game folder stands alone with a portable engine zip: unzip the engine anywhere, run it once, and every .cmd finds it through engine_path.txt; the engine scans for loose game folders | publish the engine as a zip as well as an installer; on first run, write engine_path.txt; the uninstaller asks before deleting game folders and saves (Steam deletes steamapps); names match their files exactly (Linux-safe) |
| alex | edits Antack's script in the game folder, then the launcher 'verifies files' | the mod is overwritten without a word: BROKEN for modders | WORKS: mods live in vibeapps\workshop\content\<appid>\ or Documents\Data\Games\<Game>\, loaded after the game's own script; verify never touches them | a mods folder per game; before repairing, compare and keep a copy of any changed file (Antack.livecodescript.modified-<date>) |
| chris | chose D:\VibeData as the Data folder, then a cleaner wiped AppData | games still listed (6); but data_root.txt was in AppData, so the engine goes back to Documents\Data and the saves on D: look gone: BROKEN (saves are safe on D:, just not found) | WORKS: a second copy of the choice lives in the default Data folder (Documents\Data\ROOT.md says 'moved to D:\VibeData'), and the engine offers to find a Data folder by its ROOT.md | keep only disposable things in AppData; leave a forwarding note in Documents\Data when the Data folder moves (LIB_DATA: Data.SetRoot) |
| lee | installed it; the second Windows account starts it from the Start Menu | 6 titles (the library is per machine); no settings yet (the launcher must make them); no Desktop shortcut (it went to the installer’s Desktop only); saves are per account (separate): WORKS with notes | WORKS: shortcuts in Public Desktop and the shared Start Menu; settings made on first run | make settings on first run, never at install; put the Desktop shortcut in C:\Users\Public\Desktop |
| taylor | downloads the zip, runs the exe inside it, then copies Vibecode3D.exe to the Desktop | from the Desktop copy: 0 games, no Externals beside it: BROKEN. Downloaded: the zip carries Mark of the Web (ZoneId=3); the exe is NOT signed, so SmartScreen will stop it ('Windows protected your PC', More info > Run anyway) | 6 games through config.txt; the engine warns 'I was copied out of my folder: make a shortcut instead' when Externals is missing | sign the exe (or expect SmartScreen's 'Windows protected your PC' on every download); find the library through config.txt when the exe is alone |

## Windows probes (real cmd.exe and PowerShell on V:)

| Probe | What | Outcome |
|---|---|---|
| read-only Program Files | write a file where a non-admin cannot (deny-write ACL, then removed) | refused: access denied |
| Mark of the Web | a downloaded zip (ZoneId=3), unzipped with PowerShell; the exe's signature | zip: [ZoneTransfer] ZoneId=3 / inside after Expand-Archive: not marked exe signature: NotSigned |
| ( ) in batch files | a .cmd with an if ( ) block echoes a path under Program Files (x86) | BREAKS: the ')' of (x86) ends the block |
| Unicode through set /p | cmd reads a UTF-8 path with 'í' and 'ñ' from a file | NOT FOUND in code page 437, this PC's console default; FOUND after chcp 65001 |
| long paths | a file at 284 characters, read by cmd.exe (LongPathsEnabled=1 on this PC) | cmd reads it, but only because LongPathsEnabled=1 here; Windows ships with 0 |
| reserved names | a folder named CON; and every game's folder name checked | refused: The directory specified, 'CON', is not a subdirectory of 'V:\_SimPCs\_probes'.; game names that would break: none |
| a running exe | the updater replaces Vibecode3D.exe while it runs (file held open) | refused: The process cannot access the file 'V:\_SimPCs\_probes\locked\Vibecode3D.exe' because it is being used by another process. |
| case | Save.txt and save.txt made from Linux (WSL) in one folder; what Windows lists | Linux sees 1 file(s); Windows lists: Save.txt |

## Evidence

- **dana**: `Play Antack.cmd: RUN "V:\_SimPCs\dana\C\Program Files (x86)\Vibecode3D\vibeapps\common\Antack\..\..\..\Vibecode3D.exe" -game "V:\_SimPCs\dana\C\Program Files (x86)\Vibecode3D\vibeapps\common\Antack\"`
- **ana**: `cmd exit 0: RUN "V:\_SimPCs\ana\C\Users\Ana Lucía Peña\Vibe Engine\Vibecode3D.exe" -game "V:\_SimPCs\ana\C\Users\Ana Lucía Peña\Games\Antack\"`
- **kenji**: `copy: RUN "V:\_SimPCs\kenji\C\Program Files (x86)\Vibecode3D\Vibecode3D.exe" -game "V:\_SimPCs\kenji\C\Users\健二\Desktop\ゲーム\Canyon\"`
- **morgan**: `files: slot1-MORGAN-LAPTOP.txt, slot1.txt`
- **sam**: `home 3 / friend 2 / proposed 5`
- **riley**: `saves untouched: True`
- **jordan**: `refused: access denied`
- **pat**: `Vibecode3D is not installed on this PC, or was moved.`
- **chris**: `save still on disk at D:\VibeData\Users\Chris\Saves\Antack\slot1.txt: True`
