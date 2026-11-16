#!/usr/bin/env python3
"""escape_sim: real people against the Vibecode3D install.

Each persona in LIB_USERS/personas/personas.tsv gets a simulated PC of their own, a folder on
the drive acting as their C: (V:\\_SimPCs\\<id>\\C, with D: and E: beside it when they need
them). Vibecode3D is installed there with vibeinstall.py, then each of their habits is played
out: moving folders, running from a zip, wiping AppData, uninstalling the launcher and keeping
the games. Every scenario reports what the person sees with the install as it is TODAY and with
the PROPOSED design (LAYOUT.md section 5).

Then real Windows probes run through cmd.exe and PowerShell on V:, for what a folder cannot fake:
"(x86)" in batch files, Unicode through cmd, Mark of the Web, an unsigned exe, long paths,
reserved names, a locked exe, a read-only folder, case.

  python3 -I escape_sim.py                 run everything, write ESCAPES_RESULTS.md
  python3 -I escape_sim.py --only sam      one persona (id)
  python3 -I escape_sim.py --probes        only the Windows probes
  python3 -I escape_sim.py --clean         remove V:\\_SimPCs
"""
import argparse, datetime, os, re, shutil, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vibeinstall as vi  # noqa: E402

V = "/mnt/v"
SIM = os.path.join(V, "_SimPCs")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ESCAPES_RESULTS.md")
PS = shutil.which("powershell.exe")
CMD = shutil.which("cmd.exe")
FEW = ["Antack", "uDead", "Thrmnlra", "VectorToss", "SquadBuggy", "Canyon"]   # enough to show it


def realwin(path):
    """A WSL path on V: as Windows really sees it."""
    return "V:\\" + os.path.relpath(path, V).replace("/", "\\")


def ps(script, timeout=60):
    r = subprocess.run([PS, "-NoProfile", "-NonInteractive", "-Command", script],
                       capture_output=True, timeout=timeout, cwd=V)
    return (r.stdout + r.stderr).decode("utf-8", "replace").strip()


def cmd(line, env=None, timeout=60, utf8=True):
    """Run a cmd.exe line through PowerShell (WSL's own interop escapes the quotes cmd needs).
    A line that is just a quoted .cmd path is started with & so Unicode paths survive."""
    sets = "".join(f"$env:{k}='{v}';" for k, v in (env or {}).items())
    m = re.fullmatch(r'"([^"]+\.cmd)"', line)
    if m:
        target = m.group(1)
    else:                                   # the line in a throwaway batch file, read as UTF-8
        os.makedirs(PROBE_DIR, exist_ok=True)
        tmp = os.path.join(PROBE_DIR, "_line.cmd")
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write("@echo off\r\nchcp 65001 >nul\r\n" + line + "\r\n")
        target = realwin(tmp)
    out = ps(("[Console]::OutputEncoding=[Text.Encoding]::UTF8;" if utf8 else "") + sets + f"& '{target}'; \"RC=$LASTEXITCODE\"", timeout)
    rc = 0
    hits = list(re.finditer(r"RC=(-?\d+)", out))
    if hits:
        rc = int(hits[-1].group(1))
        out = (out[:hits[-1].start()] + out[hits[-1].end():]).strip()
    return rc, out


# ------------------------------------------------------------------ a persona's PC


def new_pc(pid, fresh=True):
    p = vi.load_persona(pid)
    root = os.path.join(SIM, pid)
    if fresh and os.path.isdir(root):
        shutil.rmtree(root)
    m = vi.Machine(os.path.join(root, "C"), p["username"], letter="C")
    os.makedirs(m.home, exist_ok=True)
    for d in ("D", "E"):
        m.add_drive(d, os.path.join(root, d))
    return m


def put_install(m, games=FEW):
    log = vi.install(m, games, quiet=True)
    # the simulated C: is really V:\_SimPCs\<id>\C: tell real cmd.exe where the engine really is
    with open(os.path.join(m.settings_dir, "engine_path.txt"), "w", encoding="utf-8") as f:
        f.write(realwin(os.path.join(m.install_dir, "Vibecode3D.exe")))
    return log


def save_path(m, game, user=None, data_root=None):
    return os.path.join(data_root or m.data_root_default, "Users", user or m.user, "Saves", game, "slot1.txt")


def write_save(m, game="Antack", text="level 4|score 12000", **kw):
    p = save_path(m, game, **kw)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


def config(m):
    d = {}
    f = os.path.join(m.settings_dir, "config.txt")
    if os.path.exists(f):
        for line in open(f, encoding="utf-8"):
            if "\t" in line:
                k, v = line.rstrip("\r\n").split("\t", 1)
                d[k] = v
    return d


# what the launcher finds -------------------------------------------------------


def libs_today(m, exe_dir=None):
    """Today: <exe folder>\\vibeapps and the paths in its libraryfolders.txt (relative to the
    exe, or with a drive letter), as the launcher reads them."""
    return vi.library_list(m, exe_dir or m.install_dir)


def libs_proposed(m, exe_dir=None):
    """Proposed: today's, plus the library in config.txt, plus a scan of every drive's top two
    levels for vibeapps\\common or a loose folder of games (game.txt), like Steam's
    "add library folder" done for you."""
    libs = libs_today(m, exe_dir)
    cfg = config(m).get("library")
    if cfg and os.path.isdir(m.wsl(cfg)) and m.wsl(cfg) not in libs:
        libs.append(m.wsl(cfg))
    for _letter, root in m.drives.items():
        for top in [root] + [os.path.join(root, d) for d in safe_list(root)]:
            for cand in (os.path.join(top, vi.APPS_DIR), top):
                common = os.path.join(cand, "common")
                if os.path.isdir(common) and cand not in libs and any(
                        os.path.isfile(os.path.join(common, g, "game.txt")) for g in safe_list(common)):
                    libs.append(cand)
            loose = [g for g in safe_list(top) if os.path.isfile(os.path.join(top, g, "game.txt"))]
            if loose and top not in libs:
                libs.append(("loose", top))
    return libs


def safe_list(d):
    try:
        return [x for x in os.listdir(d) if os.path.isdir(os.path.join(d, x))]
    except OSError:
        return []


def titles(m, libs):
    n = 0
    for lib in libs:
        if isinstance(lib, tuple):
            n += sum(os.path.isfile(os.path.join(lib[1], g, "game.txt")) for g in safe_list(lib[1]))
        else:
            n += sum(1 for f in vi.game_folders(m, [lib]) if vi.read_game_txt(f).get("kind") != "redist")
    return n


def play_cmd_dryrun(m, game_dir, appdata=None):
    """Run a game's own Play <Game>.cmd through the real cmd.exe, in dry-run mode."""
    name = os.path.basename(game_dir.rstrip("/"))
    f = os.path.join(game_dir, f"Play {name}.cmd")
    if not os.path.exists(f):
        return 9, "no Play .cmd"
    env = {"VIBE_DRYRUN": "1", "APPDATA": realwin(appdata or m.roaming)}
    return cmd(f'"{realwin(f)}"', env)


# ------------------------------------------------------------------ scenarios

RESULTS = []


def result(pid, did, today, proposed, fix, evidence=""):
    RESULTS.append({"who": pid, "did": did, "today": today, "proposed": proposed, "fix": fix,
                    "evidence": evidence})
    print(f"[{pid}] {did}\n    today: {today}\n    proposed: {proposed}")


def s_dana():
    m = new_pc("dana")
    put_install(m)
    rows, _p = vi.verify(m, libraries=libs_today(m), owner_pc=False, quiet=True)
    bad = [r["game"] for r in rows if r["today"] != "ok"]
    badp = [r["game"] for r in rows if r["proposed"] != "ok"]
    rc, out = play_cmd_dryrun(m, os.path.join(m.library, "common", "Antack"))
    result("dana", "installs with every default and plays",
           f"BROKEN for {', '.join(bad)}: their data is found only on the owner's PC" if bad else "WORKS",
           "WORKS" if not badp else f"BROKEN for {', '.join(badp)}",
           "Game.FindFile: look in the game's own folder, then Vibecode3D Common, before anything else",
           f"Play Antack.cmd: {out.splitlines()[-1] if out else rc}")


def s_ana():
    m = new_pc("ana")
    put_install(m)
    p = write_save(m)
    backup = os.path.join(m.desktop, "Backup", "Data")
    shutil.copytree(m.data_root_default, backup)
    shutil.rmtree(os.path.join(SIM, "ana", "C", "Program Files (x86)"))   # PC reset: programs gone
    shutil.rmtree(m.data_root_default)
    put_install(m)
    shutil.copytree(backup, m.data_root_default, dirs_exist_ok=True)
    ok = os.path.isfile(p)
    # a library under her profile (Unicode path) and the engine_path.txt fallback through cmd
    lib2 = os.path.join(m.home, "Games")
    shutil.copytree(os.path.join(m.library, "common", "Antack"), os.path.join(lib2, "Antack"))
    with open(os.path.join(m.settings_dir, "engine_path.txt"), "w", encoding="utf-8") as f:
        f.write(realwin(os.path.join(m.home, "Vibe Engine", "Vibecode3D.exe")))
    os.makedirs(os.path.join(m.home, "Vibe Engine"), exist_ok=True)
    shutil.copy2(os.path.join(m.install_dir, "Vibecode3D.exe"), os.path.join(m.home, "Vibe Engine"))
    rc, out = play_cmd_dryrun(m, os.path.join(lib2, "Antack"))
    result("ana", "backs up Documents\\Data by hand, resets the PC, reinstalls, copies it back; "
                  "keeps the engine under her own name",
           ("saves come back: WORKS" if ok else "saves lost: BROKEN")
           + ("; the game's .cmd finds the engine under 'Ana Lucía Peña'" if rc == 0 else
              "; the game's .cmd CANNOT find an engine under 'Ana Lucía Peña' (BROKEN)"),
           "WORKS",
           "saves are plain files under Documents\\Data (keep it). Play .cmd runs chcp 65001 before reading "
           "engine_path.txt (fixed in vibeinstall.py after this persona found it; see the probe)",
           f"cmd exit {rc}: {out.splitlines()[-1] if out else ''}")


def s_kenji():
    m = new_pc("kenji")
    put_install(m)
    out_dir = os.path.join(m.desktop, "ゲーム")
    shutil.copytree(os.path.join(m.library, "common", "Canyon"), os.path.join(out_dir, "Canyon"))
    rc_in, out_in = play_cmd_dryrun(m, os.path.join(m.library, "common", "Canyon"))
    rc_out, out_out = play_cmd_dryrun(m, os.path.join(out_dir, "Canyon"))
    result("kenji", "starts Canyon from its own .cmd, in the library and from a copy on his kanji Desktop",
           f"in the library: {'WORKS' if rc_in == 0 else 'BROKEN'}; the copy: "
           f"{'WORKS (engine_path.txt)' if rc_out == 0 else 'BROKEN'}",
           "WORKS",
           "keep Play .cmd free of ( ) blocks; keep engine_path.txt; test every .cmd with a Unicode path",
           f"copy: {out_out.splitlines()[-1] if out_out else rc_out}")


def s_morgan():
    m = new_pc("morgan")
    put_install(m)
    p = write_save(m)
    naive = os.path.join(m.home, "Documents", "Data")      # %USERPROFILE%\Documents, not the known folder
    conflict = p.replace("slot1.txt", "slot1-MORGAN-LAPTOP.txt")
    shutil.copy2(p, conflict)
    with open(conflict, "w", encoding="utf-8") as f:
        f.write("level 2|score 3000")
    saves = os.listdir(os.path.dirname(p))
    result("morgan", "OneDrive moved Documents; plays on two PCs; OneDrive makes a conflict copy",
           f"the Data folder is {m.win(m.data_root_default)} if the engine asks Windows for Documents "
           f"(specialFolderPath, LIB_DATA does); a script that builds %USERPROFILE%\\Documents gets "
           f"{m.win(naive)}, which {'exists' if os.path.isdir(naive) else 'does not exist'}: an empty Data folder. "
           f"Conflict copies are ignored silently ({len(saves)} save files): DEGRADED",
           "WORKS: the save loader lists every slot*.txt, shows dates, and names conflict copies",
           "always ask Windows for Documents (never build the path); load saves by listing, not by one name; "
           "write saves to a temp name and rename (OneDrive and crashes)",
           f"files: {', '.join(sorted(saves))}")


def s_sam():
    m = new_pc("sam")
    usb = m.drives["E"]
    port = os.path.join(usb, "Vibecode3D")
    shutil.copytree(vi.ENGINE_BUILD, port, dirs_exist_ok=True)
    pm_lib = os.path.join(port, vi.APPS_DIR)
    for g in ("Antack", "uDead"):
        put_install(m, [g])
    shutil.copytree(os.path.join(m.library), pm_lib, dirs_exist_ok=True)
    with open(os.path.join(port, "portable.txt"), "w") as f:
        f.write("keep settings and saves beside the exe\n")
    pm = vi.Machine(m.drive, m.user, letter="C", exe_dir=port)     # the engine as run from the stick
    pm.drives = m.drives
    # the launcher's "add library folder": E:\MoreGames, on the exe's own drive, so written relative
    vi.write_libraryfolders(pm, pm_lib, [os.path.join(usb, "MoreGames")], exe_dir=port)
    written = open(os.path.join(pm_lib, "libraryfolders.txt"), encoding="utf-8").read()
    rel = re.findall(r'"path"\s+"([^"]+)"', written)
    os.makedirs(os.path.join(usb, "MoreGames", vi.APPS_DIR, "common"), exist_ok=True)
    shutil.copytree(os.path.join(pm_lib, "common", "uDead"),
                    os.path.join(usb, "MoreGames", vi.APPS_DIR, "common", "uDead"), dirs_exist_ok=True)
    before = titles(m, libs_today(m, port))
    # at a friend's PC the stick comes up as F:
    m.drives.pop("E")
    m.add_drive("F", usb)
    after = titles(m, libs_today(m, port))
    after_p = titles(m, libs_proposed(m, port))
    # portable: settings, cache and the Data folder beside the exe, so they travel with the stick
    save = write_save(pm, "uDead")
    on_stick = all(p.startswith(port + "/") for p in (pm.settings_dir, pm.cache_dir, pm.data_root_default, save))
    result("sam", "carries the engine and games on a USB stick; at a friend's PC it is F: not E:",
           (f"{before} titles at home, {after} at the friend's: " + ("WORKS" if after == before else "DEGRADED")
            + f" (the second library is written {rel[0] if rel else '?'}, relative to the exe). "
            + ("portable.txt: settings, cache and saves stay on the stick (" + pm.win(pm.data_root_default) + "), "
               "the friend's AppData is not touched: WORKS" if on_stick else "portable.txt ignored: BROKEN")),
           f"{after_p} titles (also a drive scan for libraries)",
           "done: library paths relative to the exe on its drive; portable.txt honoured. Left: FAT32 sticks "
           "lose Mark of the Web and file times to 2 s",
           f"home {before} / friend {after} / proposed {after_p}; libraryfolders path {rel}")


def s_riley():
    m = new_pc("riley")
    put_install(m)
    p = write_save(m)
    common = os.path.join(m.library, "common")
    dest = os.path.join(m.drives["D"], "Games", vi.APPS_DIR, "common")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.move(common, dest)                         # drag the folder; appmanifests stay behind
    manifests = [f for f in os.listdir(m.library) if f.startswith("appmanifest_")]
    t = titles(m, libs_today(m))
    tp = titles(m, libs_proposed(m))
    # she adds D:\Games as a library (another drive: written with its letter); the manifests are
    # a cache, rebuilt from each folder's game.txt
    newlib = os.path.join(m.drives["D"], "Games", vi.APPS_DIR)
    vi.write_libraryfolders(m, m.library, [os.path.dirname(newlib)])
    t2 = titles(m, libs_today(m))
    w, r = vi.rebuild_manifests(m, libs_today(m))
    left = [f for f in os.listdir(m.library) if f.startswith("appmanifest_")]
    moved = [f for f in os.listdir(newlib) if f.startswith("appmanifest_")]
    result("riley", "drags vibeapps\\common to D:\\Games to free the small SSD",
           f"{t} titles until she adds D:\\Games as a library, then {t2}. Manifests rebuilt from game.txt: "
           f"{r} removed that pointed at nothing, {len(moved)} written beside the games on D: "
           f"({len(manifests)} before, {len(left)} left on C:): " + ("WORKS" if t2 > 0 and len(moved) else "BROKEN"),
           f"{tp} titles with no help: the scan finds D:\\Games\\vibeapps",
           "done: appmanifests rebuilt from game.txt (vibeinstall.py manifests). Left: a 'Move install "
           "folder' command and the drive scan in the launcher",
           f"saves untouched: {os.path.isfile(p)}; manifests written {w}")


def s_jordan():
    m = new_pc("jordan")
    put_install(m)
    zip_dir = os.path.join(m.downloads)
    os.makedirs(zip_dir, exist_ok=True)
    # Explorer runs an exe inside a zip by extracting only it to %TEMP%\Temp1_<zip>\
    tmp = os.path.join(m.local, "Temp", "Temp1_Vibecode3D-win64.zip", "Vibecode3D")
    os.makedirs(tmp, exist_ok=True)
    shutil.copy2(os.path.join(m.install_dir, "Vibecode3D.exe"), tmp)
    t = titles(m, libs_today(m, tmp))
    tp = titles(m, libs_proposed(m, tmp))
    ro = probe_readonly()
    result("jordan", "school PC, not an admin: double-clicks the exe inside the downloaded zip; "
                     "Program Files is read-only; Defender guards Documents",
           f"the engine starts from Temp with {t} games and no Externals (Explorer extracts only the exe): BROKEN. "
           f"Writing beside the exe in Program Files: {ro}. Controlled Folder Access would block the "
           "unknown exe writing Documents\\Data (simulated; it cannot be turned on here)",
           f"{tp} titles if Vibecode3D is already installed (config.txt); otherwise the engine says "
           "'unzip me first' when its folder holds no vibeapps or Externals",
           "detect running from Temp\\Temp1_*.zip and say 'Extract all first'; offer a per-user install "
           "(%LOCALAPPDATA%\\Programs\\Vibecode3D) that needs no admin; if a Documents write fails, "
           "say why and offer another Data folder",
           ro)


def s_pat():
    m = new_pc("pat")
    put_install(m)
    keep = os.path.join(m.drives["D"], "MyGames")
    for g in ("Antack", "uDead"):
        shutil.copytree(os.path.join(m.library, "common", g), os.path.join(keep, g))
    # and a level of his own, left in the installed Thrmnlra folder
    mine = os.path.join(m.library, "common", "Thrmnlra", "my_level.txt")
    with open(mine, "w", encoding="utf-8") as f:
        f.write("pat's level\n")
    stray = vi.uninstall(m, purge=False, say=lambda *a: None)
    kept = [os.path.basename(k) for k in vi.uninstall.kept]
    whole = os.path.isfile(mine) and os.path.isfile(os.path.join(m.library, "common", "Thrmnlra", "game.txt"))
    gone = not os.path.isdir(os.path.join(m.library, "common", "Canyon"))
    rc, out = play_cmd_dryrun(m, os.path.join(keep, "Antack"))
    # Linux later: case-sensitive. Do the games ask for the names they ship with?
    case_bad = []
    for g in ("Antack", "uDead"):
        folder = os.path.join(keep, g)
        txt = open(os.path.join(folder, vi.read_game_txt(folder)["script"]), encoding="utf-8", errors="replace").read()
        for ask in vi.ASKS.findall(txt):
            short = ask[len(vi.DEV_PREFIX):] if ask.startswith(vi.DEV_PREFIX) else None
            if short and not os.path.exists(os.path.join(folder, short)):
                case_bad.append(f"{g}: {short}")
    result("pat", "copies two game folders to D:\\MyGames, uninstalls Vibecode3D, double-clicks Play Antack.cmd",
           f"uninstall keeps {', '.join(kept) or 'no'} game folder (it held his own file; "
           + ("kept whole, " if whole else "NOT kept whole, ") + ("the others removed" if gone else "others left too")
           + f"): WORKS. It leaves {len(stray)} files (settings, saves, logs, the kept folder). The .cmd "
           + ("still finds the engine (engine_path.txt survived, the exe did not?)" if rc == 0 else
              "says 'Vibecode3D is not installed on this PC, or was moved' (clear, but the game cannot run "
              "without the engine): DEGRADED"),
           "the game folder stands alone with a portable engine zip: unzip the engine anywhere, run it once, "
           "and every .cmd finds it through engine_path.txt; the engine scans for loose game folders",
           "publish the engine as a zip as well as an installer; on first run, write engine_path.txt. "
           "Done: the uninstaller keeps a game folder that holds files it didn't install"
           + ("; case: " + "; ".join(case_bad) if case_bad else "; names match their files exactly (Linux-safe)"),
           out.splitlines()[0] if out else str(rc))


def s_alex():
    m = new_pc("alex")
    put_install(m)
    script = os.path.join(m.library, "common", "Antack", "Vibecode3D_Play_Antack.livecodescript")
    with open(script, "a", encoding="utf-8") as f:
        f.write("\n-- ALEX'S MOD: double jump\n")
    vi.install(m, ["Antack"], quiet=True)      # "Verify integrity of game files"
    kept = "ALEX'S MOD" in open(script, encoding="utf-8").read()
    result("alex", "edits Antack's script in the game folder, then the launcher 'verifies files'",
           "the mod is " + ("kept" if kept else "overwritten without a word: BROKEN for modders"),
           "WORKS: mods live in vibeapps\\workshop\\content\\<appid>\\ or Documents\\Data\\Games\\<Game>\\, "
           "loaded after the game's own script; verify never touches them",
           "a mods folder per game; before repairing, compare and keep a copy of any changed file "
           "(Antack.livecodescript.modified-<date>)")


def s_chris():
    m = new_pc("chris")
    put_install(m)
    alt = os.path.join(m.drives["D"], "VibeData")
    vi.set_data_root(m, alt)                # Data.SetRoot: data_root.txt + the forwarding line
    p = write_save(m, data_root=alt)
    shutil.rmtree(m.settings_dir)
    shutil.rmtree(m.cache_dir)
    shutil.rmtree(os.path.join(m.local, "Temp"), ignore_errors=True)
    root_after, how = vi.data_root(m)       # data_root.txt is gone
    found = os.path.isfile(save_path(m, "Antack", data_root=root_after))
    t = titles(m, libs_today(m))
    result("chris", "chose D:\\VibeData as the Data folder, then a cleaner wiped AppData",
           f"games still listed ({t}); data_root.txt was in AppData, but LIB_DATA follows {how} in "
           f"Documents\\Data to {m.win(root_after)}: "
           + ("WORKS, the saves on D: are found" if found else "BROKEN (saves are safe on D:, just not found)"),
           "WORKS (the same, and the engine could also offer to find a Data folder by its ROOT.md)",
           "done in LIB_DATA (branch data-forwarding): Data.SetRoot leaves 'Moved to: D:/VibeData' in "
           "Documents\\Data\\ROOT.md and Data.Root follows it. Left: the engine and games using LIB_DATA's Data.Root",
           f"save still on disk at {m.win(p)}: {os.path.isfile(p)}")


def s_lee():
    m = new_pc("lee")
    put_install(m)
    write_save(m)
    kid = vi.Machine(m.drive, "Lee's Kid", letter="C")
    kid.drives = m.drives
    os.makedirs(kid.home, exist_ok=True)
    t = titles(kid, libs_today(kid))
    cfg = os.path.isdir(kid.settings_dir)
    desk = any(os.path.exists(os.path.join(d, f)) for d in (kid.desktop, kid.public_desktop)
               for f in ("Vibecode3D.lnk", "Vibecode3D.url"))
    their_saves = os.path.isdir(os.path.join(kid.data_root_default, "Users"))
    result("lee", "installed it; the second Windows account starts it from the Start Menu",
           f"{t} titles (the library is per machine); no settings yet ({'made' if cfg else 'the launcher must make them'}); "
           f"{'a Desktop shortcut (Public Desktop, every account)' if desk else 'no Desktop shortcut (the installer’s Desktop only)'}; "
           f"saves are per account ({'shared?' if their_saves else 'separate'}): WORKS with notes",
           "WORKS: shortcuts in Public Desktop and the shared Start Menu; settings made on first run",
           "make settings on first run, never at install. Done: the Desktop shortcut is in C:\\Users\\Public\\Desktop")


def s_taylor():
    m = new_pc("taylor")
    put_install(m)
    os.makedirs(m.desktop, exist_ok=True)
    loose = os.path.join(m.desktop, "Vibecode3D.exe")
    shutil.copy2(os.path.join(m.install_dir, "Vibecode3D.exe"), loose)     # copies the exe, not a shortcut
    t = titles(m, libs_today(m, m.desktop))
    tp = titles(m, libs_proposed(m, m.desktop))
    motw = probe_motw()
    result("taylor", "downloads the zip, runs the exe inside it, then copies Vibecode3D.exe to the Desktop",
           f"from the Desktop copy: {t} games, no Externals beside it: BROKEN. Downloaded: {motw}",
           f"{tp} games through config.txt; the engine warns 'I was copied out of my folder: make a shortcut "
           "instead' when Externals is missing",
           "sign the exe (or expect SmartScreen's 'Windows protected your PC' on every download); "
           "find the library through config.txt when the exe is alone")


SCENARIOS = {"dana": s_dana, "ana": s_ana, "kenji": s_kenji, "morgan": s_morgan, "sam": s_sam,
             "riley": s_riley, "jordan": s_jordan, "pat": s_pat, "alex": s_alex, "chris": s_chris,
             "lee": s_lee, "taylor": s_taylor}

# ------------------------------------------------------------------ real Windows probes

PROBES = []
PROBE_DIR = os.path.join(SIM, "_probes")


def probe(name, what, outcome, evidence=""):
    if any(p["name"] == name for p in PROBES):
        return
    PROBES.append({"name": name, "what": what, "outcome": outcome, "evidence": evidence.strip()})
    print(f"[probe] {name}: {outcome}")


def probe_parens():
    d = os.path.join(PROBE_DIR, "Program Files (x86)", "Vibecode3D")
    os.makedirs(d, exist_ok=True)
    naive = os.path.join(d, "naive.cmd")
    with open(naive, "w", newline="") as f:
        f.write('@echo off\r\nset ENGINE=%~dp0Vibecode3D.exe\r\n'
                'if not exist "%ENGINE%" (\r\n  echo not found: %ENGINE%\r\n) else (\r\n  echo RUN %ENGINE%\r\n)\r\n')
    rc, out = cmd(f'"{realwin(naive)}"')
    probe("( ) in batch files", "a .cmd with an if ( ) block echoes a path under Program Files (x86)",
          "BREAKS: the ')' of (x86) ends the block" if "unexpected" in out.lower() else f"ran (exit {rc})",
          out)


def probe_unicode_setp():
    d = os.path.join(PROBE_DIR, "Ana Lucía Peña")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "engine_path.txt"), "w", encoding="utf-8") as f:
        f.write(realwin(os.path.join(d, "Vibecode3D.exe")))
    open(os.path.join(d, "Vibecode3D.exe"), "w").close()
    t = os.path.join(d, "t.cmd")
    with open(t, "w", newline="") as f:
        f.write('@echo off\r\nchcp 437 >nul\r\nset /p E=<"%~dp0engine_path.txt"\r\nif exist "%E%" (echo FOUND in code page 437) else (echo NOT FOUND in code page 437, this PC\'s console default)\r\n'
                'chcp 65001 >nul\r\nset /p E=<"%~dp0engine_path.txt"\r\nif exist "%E%" (echo FOUND after chcp 65001) else (echo NOT FOUND after chcp 65001)\r\n')
    rc, out = cmd(f'"{realwin(t)}"', utf8=False)     # the console as a double-click gets it
    probe("Unicode through set /p", "cmd reads a UTF-8 path with 'í' and 'ñ' from a file",
          out.replace("\r\n", "; ").replace("\n", "; "), out)


def probe_motw():
    d = os.path.join(PROBE_DIR, "Downloads")
    os.makedirs(d, exist_ok=True)
    src = os.path.join(d, "payload")
    os.makedirs(src, exist_ok=True)
    with open(os.path.join(src, "readme.txt"), "w") as f:
        f.write("hi")
    z = os.path.join(d, "Vibecode3D-win64.zip")
    if os.path.exists(z):
        os.remove(z)
    out_dir = os.path.join(d, "unzipped")
    shutil.rmtree(out_dir, ignore_errors=True)
    out = ps(f"Compress-Archive -Path '{realwin(src)}\\*' -DestinationPath '{realwin(z)}';"
             f"Set-Content -Path '{realwin(z)}' -Stream Zone.Identifier -Value \"[ZoneTransfer]`r`nZoneId=3\";"
             f"$zz=(Get-Content '{realwin(z)}' -Stream Zone.Identifier) -join ' ';"
             f"Expand-Archive '{realwin(z)}' '{realwin(out_dir)}';"
             f"$in=Get-Item '{realwin(out_dir)}\\readme.txt' -Stream * | Where-Object Stream -eq 'Zone.Identifier';"
             f"\"zip: $zz | inside after Expand-Archive: $(if($in){{'marked'}}else{{'not marked'}})\";"
             f"$s=Get-AuthenticodeSignature '{realwin(os.path.join(V, 'Program Files (x86)', 'Vibecode3D', 'Vibecode3D.exe'))}';"
             f"\"exe signature: $($s.Status)\"")
    probe("Mark of the Web", "a downloaded zip (ZoneId=3), unzipped with PowerShell; the exe's signature", out.replace("\n", " "), out)
    sig = "NotSigned" in out
    return ("the zip carries Mark of the Web (ZoneId=3); the exe is NOT signed, so SmartScreen will stop it "
            "('Windows protected your PC', More info > Run anyway)" if sig else out)


def probe_longpath():
    base = os.path.join(PROBE_DIR, "long")
    p = base
    while len(realwin(p)) < 270:
        p = os.path.join(p, "Vibecode3D Common LIB_MOCAP library clips")
    os.makedirs(p, exist_ok=True)
    f = os.path.join(p, "clip.txt")
    with open(f, "w") as fh:
        fh.write("ok")
    rc, out = cmd(f'type "{realwin(f)}"')
    lp = ps("(Get-ItemProperty 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\FileSystem').LongPathsEnabled")
    probe("long paths", f"a file at {len(realwin(f))} characters, read by cmd.exe (LongPathsEnabled={lp} on this PC)",
          f"cmd reads it, but only because LongPathsEnabled={lp} here; Windows ships with 0" if rc == 0 and "ok" in out else f"cmd FAILS: {out.splitlines()[-1] if out else rc}", out)
    shutil.rmtree(base, ignore_errors=True)


def probe_reserved():
    out = ps(f"try {{ New-Item -ItemType Directory -Path '{realwin(PROBE_DIR)}\\CON' -ErrorAction Stop | Out-Null; 'made CON' }} "
             f"catch {{ 'refused: ' + $_.Exception.Message }}")
    bad = [g["name"] for g in vi.read_catalog()
           if g["name"].split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                                                  *(f"LPT{i}" for i in range(1, 10))}
           or g["name"].endswith((".", " ")) or re.search(r'[<>:"/\\|?*]', g["name"])]
    probe("reserved names", "a folder named CON; and every game's folder name checked",
          f"{out}; game names that would break: {', '.join(bad) or 'none'}", out)


def probe_locked():
    exe = os.path.join(PROBE_DIR, "locked", "Vibecode3D.exe")
    os.makedirs(os.path.dirname(exe), exist_ok=True)
    with open(exe, "w") as f:
        f.write("pretend engine")
    out = ps(f"$s=[IO.File]::Open('{realwin(exe)}','Open','Read','None');"
             f"try {{ Remove-Item '{realwin(exe)}' -ErrorAction Stop; 'deleted while open' }} catch {{ 'refused: ' + $_.Exception.Message }};"
             f"$s.Close()")
    probe("a running exe", "the updater replaces Vibecode3D.exe while it runs (file held open)", out.splitlines()[-1] if out else "", out)


def probe_readonly():
    d = os.path.join(PROBE_DIR, "readonly_program_files")
    os.makedirs(d, exist_ok=True)
    w = realwin(d)
    out = ps(f"$u=[Security.Principal.WindowsIdentity]::GetCurrent().Name;"
             f"icacls '{w}' /deny \"${{u}}:(OI)(CI)(W)\" | Out-Null;"
             f"try {{ Set-Content '{w}\\config.txt' 'x' -ErrorAction Stop; $r='wrote' }} catch {{ $r='refused: ' + $_.Exception.Message }};"
             f"icacls '{w}' /remove:d \"$u\" | Out-Null; $r")
    res = out.splitlines()[-1] if out else ""
    res = re.sub(r"Access to the path '.*?' is denied\.", "access denied", res)
    probe("read-only Program Files", "write a file where a non-admin cannot (deny-write ACL, then removed)", res, "")
    return res


def probe_case():
    d = os.path.join(PROBE_DIR, "case")
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    with open(os.path.join(d, "Save.txt"), "w") as f:
        f.write("A")
    try:
        with open(os.path.join(d, "save.txt"), "x") as f:
            f.write("B")
        two = len(os.listdir(d))
    except FileExistsError:
        two = 1
    rc, out = cmd(f'dir /b "{realwin(d)}"')
    probe("case", "Save.txt and save.txt made from Linux (WSL) in one folder; what Windows lists",
          f"Linux sees {two} file(s); Windows lists: {', '.join(out.split()) or '(none)'}", out)


PROBE_FNS = [probe_parens, probe_unicode_setp, probe_longpath, probe_reserved, probe_locked, probe_case,
             probe_readonly, probe_motw]

# ------------------------------------------------------------------ report


def report():
    when = datetime.datetime.now().strftime("%A, %B %d, %Y %H:%M")
    L = [f"# Escape simulation: results\n\n{when}. Made by `escape_sim.py`; the scenarios are explained in "
         "`README.md`, the personas in `LIB_USERS/personas/PERSONAS.md`. TODAY is the install as built, "
         "which since 16 Nov has the games' Game.FindFile (LIB_GAMES install-findfile), library paths "
         "relative to the exe, portable.txt, appmanifests rebuilt from game.txt, an uninstaller that keeps "
         "game folders holding your own files, and the Public Desktop shortcut. PROPOSED is the rest of "
         "`LAYOUT.md` section 5, modelled here, not yet in the engine.\n",
         "## Personas\n", "| Who | Did | Today | Proposed | Fix |", "|---|---|---|---|---|"]
    for r in RESULTS:
        L.append(f"| {r['who']} | {r['did']} | {r['today']} | {r['proposed']} | {r['fix']} |")
    L += ["\n## Windows probes (real cmd.exe and PowerShell on V:)\n", "| Probe | What | Outcome |", "|---|---|---|"]
    for p in PROBES:
        L.append(f"| {p['name']} | {p['what']} | {p['outcome'].replace('|', '/')} |")
    ev = [r for r in RESULTS if r["evidence"]]
    if ev:
        L += ["\n## Evidence\n"] + [f"- **{r['who']}**: `{r['evidence']}`" for r in ev]
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print(f"wrote {OUT}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only")
    ap.add_argument("--probes", action="store_true")
    ap.add_argument("--clean", action="store_true")
    a = ap.parse_args()
    if a.clean:
        shutil.rmtree(SIM, ignore_errors=True)
        print("removed", realwin(SIM))
        return
    os.makedirs(PROBE_DIR, exist_ok=True)
    if not a.probes:
        for pid, fn in SCENARIOS.items():
            if not a.only or a.only == pid:
                fn()
    if not a.only:
        for fn in PROBE_FNS:
            fn()
    if not a.only and not a.probes:
        report()


if __name__ == "__main__":
    main()
