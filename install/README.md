# install: Vibecode3D on an ordinary PC, and the people who escape it

A simulated, Steam-style installation of Vibecode3D and its games on the V: drive (which stands
in for any PC's C:), and a simulation of what real people do to it. Made 2026-11-15.

| File | What |
|---|---|
| `LAYOUT.md` | where everything goes, Steam and Windows side by side; what broke; the proposed design; questions |
| `vibeinstall.py` | the installer: `install`, `verify`, `status`, `uninstall [--purge]`, `manifests`, `catalog`. Public games come from LIB_GAMES `install-findfile` while it exists (else main) |
| `catalog.tsv` | the 50 titles with app ids, from LIB_GAMES `main` (public) and the `spark-roadtrip` and `vector-toss` branches (betas) |
| `escape_sim.py` | gives each persona a simulated PC (`V:\_SimPCs\<id>\C`, `D`, `E`), plays out their habits, then runs real Windows probes |
| `ESCAPES_RESULTS.md` | the last run: each persona TODAY and with the PROPOSED design, and the probe results |

```
cd ~/projects/LIB_PUBLIC/install
python3 -I vibeinstall.py install          # V:\Program Files (x86)\Vibecode3D + AppData + Documents\Data
python3 -I vibeinstall.py verify           # can each game start and find its files?
python3 -I escape_sim.py                   # all personas + probes (about 10 minutes), writes ESCAPES_RESULTS.md
python3 -I escape_sim.py --only riley      # one persona
python3 -I escape_sim.py --clean           # remove V:\_SimPCs
python3 -I vibeinstall.py manifests        # rebuild every appmanifest from the game folders' game.txt
python3 -I vibeinstall.py uninstall        # what a real uninstaller does: settings, saves and game folders holding your own files stay
python3 -I vibeinstall.py comfygames       # Comfy Games on its own (Program Files (x86)\Comfy Games\LIB_COMFY\Player\ComfyGames.exe), then checks it
python3 -I vibeinstall.py comfyverify      # only the check: files there, and Make a new one works for every genre
```

Games are taken from the LIB_GAMES branches with `git archive` / `git show`, so the owner's
checked-out copy is never touched. Nothing is written to the real registry (what would be is in
`_simulated_registry.reg`). The probes do touch real Windows, only inside `V:\_SimPCs\_probes`:
a deny-write ACL that is removed straight after, a file held open for a moment, a CON folder that
Windows refuses.

## The scenarios

The people are in `LIB_USERS/personas/` (PERSONAS.md, personas.tsv). In short:

| Persona | Escape or OS trouble |
|---|---|
| Dana | none: the baseline install |
| Ana Lucía Peña | backs up saves by hand across a PC reset; accented user folder |
| 健二 Kenji | starts games from their own .cmd, from a kanji folder |
| Morgan | OneDrive took Documents; a sync conflict copy of a save |
| Sam | engine and games on a USB stick; the drive letter changes |
| Riley | drags the library to D: |
| Jordan | not an admin; runs the exe inside the zip; read-only Program Files |
| Pat | uninstalls the launcher, keeps the game folders |
| Alex | mods in place, then "verify files" |
| Chris | moved the Data folder, then a cleaner wipes AppData |
| Lee | a second Windows account |
| Taylor | Mark of the Web, SmartScreen, copies the exe (not a shortcut) to the Desktop |

What is real and what is modelled: folders, files, moves, copies, uninstalls, cmd.exe and
PowerShell behaviour are real. What the launcher and the games would find is modelled in Python
from their scripts (`vibeinstall.verify`), since the engine has no "install folder" mode yet; the
engine exe is installed but not started. OneDrive, Controlled Folder Access and SmartScreen
cannot be switched on here and are described, not run.
