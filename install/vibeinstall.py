#!/usr/bin/env python3
"""vibeinstall: lay out a Steam-style install of Vibecode3D and its games on a drive, and check it.

The drive (default V:, /mnt/v in WSL) is treated as an ordinary Windows PC. This program does
what an installer would do, writes down every file it made (uninstall.log, like NSIS), and
models the lookups the launcher and each game make, so escape_sim.py can break the install the
way real people do and see what still works.

  python3 -I vibeinstall.py install   [--drive /mnt/v] [--user NAME]
  python3 -I vibeinstall.py verify    [--drive /mnt/v] [--user NAME]
  python3 -I vibeinstall.py status    [--drive /mnt/v]
  python3 -I vibeinstall.py uninstall [--drive /mnt/v] [--purge]
  python3 -I vibeinstall.py catalog                       (rebuild catalog.tsv from LIB_GAMES)

--user NAME: a persona from LIB_USERS/personas/personas.tsv, whose profile is V:\\Users\\NAME.
Without it the profile is the drive root itself (V:\\AppData, V:\\Documents), as the owner set up.
Nothing is written to the real Windows registry; what would be is in _simulated_registry.reg.
"""
import argparse, csv, datetime, io, os, re, shutil, subprocess, sys, tarfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECTS = os.path.abspath(os.path.join(HERE, "..", ".."))
GAMES_REPO = os.path.join(PROJECTS, "LIB_GAMES")
ENGINE_BUILD = os.path.join(PROJECTS, "Vibecode3D", "standalone", "VibeCode3D", "Windows x86-64")
PERSONAS = os.path.join(PROJECTS, "LIB_USERS", "personas", "personas.tsv")
CATALOG = os.path.join(HERE, "catalog.tsv")

PRODUCT = "Vibecode3D"
VERSION = "0.1.0-sim"
APPS_DIR = "vibeapps"                       # Steam: steamapps
COMMON_ID = 1000                            # Steam: 228980 "Steamworks Common Redistributables"
DEV_PREFIX = "LIB_GAMES/Vibecode3D_Games/"  # where the games' FindFile looks today
REPO_PREFIX = "Vibecode3D_Games/"         # the same folder inside the LIB_GAMES repo
OWNER_ONLY = "//wsl$/Ubuntu/home/igame3d/projects/"   # their last fallback: the owner's PC only

# ---------------------------------------------------------------- paths


class Machine:
    """A Windows PC whose system drive is a folder in WSL (default /mnt/v = V:)."""

    def __init__(self, drive="/mnt/v", user=None, letter=None):
        self.drive = drive.rstrip("/")
        self.letter = letter or ("V" if self.drive == "/mnt/v" else "V")
        self.user = user
        self.drives = {self.letter: self.drive}     # other letters: add_drive
        self.persona = load_persona(user) if user else {}
        home = self.drive if not user else os.path.join(self.drive, "Users", user)
        self.home = home
        self.roaming = os.path.join(home, "AppData", "Roaming")
        self.local = os.path.join(home, "AppData", "Local")
        self.locallow = os.path.join(home, "AppData", "LocalLow")
        redirect = self.persona.get("documents", "")
        self.documents = os.path.join(home, *redirect.split("\\")) if redirect else os.path.join(home, "Documents")
        self.desktop = os.path.join(home, "Desktop")
        self.downloads = os.path.join(home, "Downloads")
        self.program_files = os.path.join(self.drive, "Program Files (x86)")
        self.start_menu = os.path.join(self.drive, "ProgramData", "Microsoft", "Windows", "Start Menu", "Programs")

    # where things go
    @property
    def install_dir(self):
        return os.path.join(self.program_files, PRODUCT)

    @property
    def library(self):
        return os.path.join(self.install_dir, APPS_DIR)

    @property
    def settings_dir(self):           # per-user settings, roams with the profile
        return os.path.join(self.roaming, PRODUCT)

    @property
    def cache_dir(self):              # this machine only: logs, crash dumps, cache
        return os.path.join(self.local, PRODUCT)

    @property
    def data_root_default(self):      # LIB_DATA: Documents/Data
        return os.path.join(self.documents, "Data")

    def add_drive(self, letter, path):
        os.makedirs(path, exist_ok=True)
        self.drives[letter.upper()] = path.rstrip("/")

    def win(self, path):
        """WSL path -> Windows path, on whichever simulated drive holds it."""
        for letter, root in sorted(self.drives.items(), key=lambda kv: -len(kv[1])):
            if path == root or path.startswith(root + "/"):
                rel = os.path.relpath(path, root)
                return letter + ":\\" + ("" if rel == "." else rel.replace("/", "\\"))
        return path

    def wsl(self, winpath):
        p = winpath.replace("\\", "/")
        root = self.drive
        if re.match(r"^[A-Za-z]:", p):
            root = self.drives.get(p[0].upper(), "/nonexistent-drive-" + p[0].upper())
            p = p[2:]
        return root + "/" + p.lstrip("/")


def load_persona(name):
    if not os.path.exists(PERSONAS):
        return {}
    with open(PERSONAS, encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row["username"] == name or row["id"] == name:
                return row
    return {}          # someone not in the list: an ordinary profile


# ---------------------------------------------------------------- the catalog

TOOLS = {"Simple_Test1", "Simple_Test2", "Ig3dEditor", "Face", "demo"}
# what the games load from other LIBs, shipped in Vibecode3D Common as <LIB>/<path>
# (LIB_MOCAP/library holds Animazoo-derived clips: rights unsettled, fine on this drive, a
#  release blocker for a public build)
COMMON_LIBS = [("LIB_BIT", "main", "livecode"), ("LIB_MAP", "main", "livecode"),
               ("LIB_MOCAP", "main", "library"), ("LIB_MOCAP", "anim-list", "livecode"),
               ("LIB_GENERICA", "main", "sets"), ("LIB_MCP", "main", "assets")]
DATA_DIRS = {"Antack": ["Antack"], "Thrmnlra": ["Thrmnlra"], "uDead": ["uDead"],
             "VectorToss": ["VectorToss", "Animations"]}
REFS = ["main", "spark-roadtrip", "vector-toss"]      # main = public, the others = betas


def git(*args, cwd=GAMES_REPO, binary=False):
    out = subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)
    return out.stdout if binary else out.stdout.decode("utf-8")


def pretty(key):
    special = {"uDead": "uDead", "Ig3dEditor": "iGame3D Editor", "VectorPong3D": "Vector Pong 3D"}
    if key in special:
        return special[key]
    s = key.replace("_", " ")
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", s)
    return s[:1].upper() + s[1:]


def blob_id(ref, path):
    return git("rev-parse", f"{ref}:{path}").strip()


def build_catalog():
    old = {}
    if os.path.exists(CATALOG):
        with open(CATALOG, encoding="utf-8") as f:
            old = {r["key"]: r for r in csv.DictReader(f, delimiter="\t")}
    found = {}
    for ref in REFS:
        for name in git("ls-tree", "--name-only", ref, REPO_PREFIX).split():
            m = re.match(r".*/Vibecode3D_Play_(.+)\.livecodescript$", name)
            if m:
                found.setdefault(m.group(1), []).append((ref, blob_id(ref, name)))
    rows, next_id = [], max([int(r["appid"]) for r in old.values()] + [COMMON_ID]) + 10
    for key in sorted(found, key=str.lower):
        main_blob = dict(found[key]).get("main")
        refs = [r for r, b in found[key] if r == "main" or b != main_blob]   # a beta only if it differs
        if key in old:
            appid = old[key]["appid"]
        else:
            appid, next_id = str(next_id), next_id + 10
        rows.append({"appid": appid, "key": key, "name": pretty(key),
                     "kind": "tool" if key in TOOLS else "game",
                     "branch": "public" if "main" in refs else "beta",
                     "ref": "main" if "main" in refs else refs[0],
                     "betas": ",".join(r for r in refs if r != "main"),
                     "data": ",".join(DATA_DIRS.get(key, []))})
    with open(CATALOG, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return rows


def read_catalog():
    if not os.path.exists(CATALOG):
        return build_catalog()
    with open(CATALOG, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


# ---------------------------------------------------------------- install


class Log:
    def __init__(self, m):
        self.m, self.lines = m, []

    def made(self, path):
        self.lines.append(self.m.win(path))
        return path


def write(log, path, text, newline="\r\n"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline=newline) as f:
        f.write(text)
    log.made(path)


def kv(d):
    """Valve's KeyValues look, kept simple: "key"<TAB><TAB>"value"."""
    return "".join(f'\t"{k}"\t\t"{v}"\n' for k, v in d.items())


def extract(ref, gitpath, dest, log, repo=GAMES_REPO):
    """Copy a folder of a LIB repo at ref into dest (no checkout, the owner's copy untouched)."""
    data = git("archive", "--format=tar", ref, gitpath, binary=True, cwd=repo)
    with tarfile.open(fileobj=io.BytesIO(data)) as t:
        for mem in t.getmembers():
            if not mem.isfile():
                continue
            rel = mem.name[len(gitpath):].lstrip("/")
            out = os.path.join(dest, rel)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, "wb") as f:
                f.write(t.extractfile(mem).read())
            log.made(out)


# what the launcher loads to play a game, from the owner's projects (working copies)
ENGINE_FILES = [
    ("xt3D_Raylib_Livecode_Bridge/testbench/vibe_engine_xt3d.livecodescript", "vibe_engine_xt3d.livecodescript"),
    ("LIB_DEV/livecode/game_player.livecodescript", "game_player.livecodescript"),
    ("LIB_GAMES/tools/GameNotes.livecodescript", "GameNotes.livecodescript"),
]
# the launcher standalone, saved by OXT-Beyond (LIB_PUBLIC/launcher/README.md)
LAUNCHER_DIR = os.path.join(HERE, "..", "launcher", "build", "Vibecode3D Library", "Windows x86-64")
# the player logs to the owner's inbox; installed, it logs to the uErrorFile the launcher sets
PLAYER_LOG_OLD = 'GL.Projects() & "/LIB_LLMIN/LIB_DEV/GAME_PLAYER_ERRORS.txt"'
PLAYER_LOG_NEW = 'the uErrorFile of me'


def install_engine_files(dest, log, say=print):
    os.makedirs(dest, exist_ok=True)
    for rel, name in ENGINE_FILES:
        src = os.path.join(PROJECTS, rel)
        if not os.path.exists(src):
            say(f"  (Engine: no {rel})")
            continue
        text = open(src, encoding="utf-8").read()
        if name == "game_player.livecodescript":
            if PLAYER_LOG_OLD not in text:
                say("  (Engine: game_player's error log line changed; errors go to the owner's inbox)")
            text = text.replace(PLAYER_LOG_OLD, PLAYER_LOG_NEW)
        dst = os.path.join(dest, name)
        open(dst, "w", encoding="utf-8", newline="").write(text)
        log.made(dst)


def play_cmd(game_dir_name):
    """Play <Game>.cmd: start this game without the launcher. Robust on purpose: no ( ) blocks,
    since "Program Files (x86)" closes them (the naive version is tried in escape_sim)."""
    return (
        "@echo off\r\n"
        "rem Play this game without the launcher. The engine is three folders up when installed;\r\n"
        "rem otherwise the path the launcher remembered in %APPDATA%\\Vibecode3D\\engine_path.txt.\r\n"
        "setlocal\r\n"
        "set \"GAME=%~dp0\"\r\n"
        "set \"ENGINE=%~dp0..\\..\\..\\Vibecode3D.exe\"\r\n"
        "if exist \"%ENGINE%\" goto run\r\n"
        "set \"ENGINE=\"\r\n"
        "rem engine_path.txt is UTF-8: without this, an accented or kanji path is not found\r\n"
        "chcp 65001 >nul\r\n"
        "if exist \"%APPDATA%\\Vibecode3D\\engine_path.txt\" set /p ENGINE=<\"%APPDATA%\\Vibecode3D\\engine_path.txt\"\r\n"
        "if not defined ENGINE goto none\r\n"
        "if exist \"%ENGINE%\" goto run\r\n"
        ":none\r\n"
        "echo Vibecode3D is not installed on this PC, or was moved.\r\n"
        "echo Get it from the Vibecode3D page, then run this file again.\r\n"
        "exit /b 2\r\n"
        ":run\r\n"
        "if defined VIBE_DRYRUN echo RUN \"%ENGINE%\" -game \"%GAME%\"& exit /b 0\r\n"
        "start \"\" \"%ENGINE%\" -game \"%GAME%\"\r\n")


def install(m, games=None, with_engine=True, quiet=False):
    log = Log(m)
    cat = [g for g in read_catalog() if not games or g["key"] in games]
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    say = (lambda *a: None) if quiet else print

    # 1. the program (read-only after install, like any Program Files app)
    os.makedirs(m.install_dir, exist_ok=True)
    if with_engine and os.path.isdir(ENGINE_BUILD):
        for root, _dirs, files in os.walk(ENGINE_BUILD):
            for fn in files:
                src = os.path.join(root, fn)
                rel = os.path.relpath(src, ENGINE_BUILD)
                dst = os.path.join(m.install_dir, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                if not (os.path.exists(dst) and os.path.getsize(dst) == os.path.getsize(src)):
                    shutil.copy2(src, dst)
                log.made(dst)
        exe = os.path.join(m.install_dir, "VibeCode3D.exe")
        if os.path.exists(exe):
            os.replace(exe, os.path.join(m.install_dir, "Vibecode3D.exe"))
            log.lines[log.lines.index(m.win(exe))] = m.win(os.path.join(m.install_dir, "Vibecode3D.exe"))
    write(log, os.path.join(m.install_dir, "install.txt"),
          f"product\t{PRODUCT}\nversion\t{VERSION}\ninstalled\t{now}\n"
          f"library\t{m.win(m.library)}\n", "\r\n")
    write(log, os.path.join(m.install_dir, "_simulated_registry.reg"),
          "Windows Registry Editor Version 5.00\r\n\r\n"
          "; what a real installer writes; this simulation never imports it\r\n"
          "[HKEY_LOCAL_MACHINE\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Vibecode3D]\r\n"
          f"\"DisplayName\"=\"{PRODUCT}\"\r\n\"DisplayVersion\"=\"{VERSION}\"\r\n"
          f"\"InstallLocation\"=\"{m.win(m.install_dir).replace(chr(92), chr(92) * 2)}\"\r\n"
          "\"UninstallString\"=\"(simulated: vibeinstall.py uninstall)\"\r\n\r\n"
          "[HKEY_CLASSES_ROOT\\vibecode3d]\r\n\"URL Protocol\"=\"\"\r\n"
          "; vibecode3d://run/<appid> starts a game, as steam://rungameid/<id> does\r\n")

    # 2. the library: vibeapps\common\<Game>, one appmanifest each (Steam's steamapps)
    common = os.path.join(m.library, "common")
    for sub in ("downloading", "temp", os.path.join("workshop", "content")):
        os.makedirs(os.path.join(m.library, sub), exist_ok=True)
    write(log, os.path.join(m.library, "libraryfolders.txt"),
          '"libraryfolders"\n{\n\t"0"\n\t{\n' + kv({"path": m.win(m.install_dir)}).replace("\t\"", "\t\t\"")
          + "\t}\n}\n")
    # shared scripts every game may load: Steam's Common Redistributables
    redist = os.path.join(common, "Vibecode3D Common")
    extract("main", REPO_PREFIX + "Sequencer", os.path.join(redist, "Sequencer"), log)
    for repo, ref, sub in COMMON_LIBS:
        try:
            extract(ref, sub, os.path.join(redist, repo, sub), log, repo=os.path.join(PROJECTS, repo))
        except subprocess.CalledProcessError:
            say(f"  (Common: no {repo}/{sub} on {ref})")
    # the engine the launcher plays games with (LIB_PUBLIC/launcher): Vibecode3D Common\Engine
    install_engine_files(os.path.join(redist, "Engine"), log, say)
    if with_engine and os.path.isdir(LAUNCHER_DIR):        # the exe and its Externals, beside Vibecode3D.exe
        for root, _dirs, files in os.walk(LAUNCHER_DIR):
            for fn in files:
                src = os.path.join(root, fn)
                dst = os.path.join(m.install_dir, os.path.relpath(src, LAUNCHER_DIR))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                log.made(dst)
    write(log, os.path.join(redist, "game.txt"),
          f"appid\t{COMMON_ID}\nname\tVibecode3D Common\nkind\tredist\nscript\t\n")
    write(log, os.path.join(m.library, f"appmanifest_{COMMON_ID}.txt"),
          '"AppState"\n{\n' + kv({"appid": COMMON_ID, "name": "Vibecode3D Common", "installdir": "Vibecode3D Common",
                                  "StateFlags": 4, "LastUpdated": now}) + "}\n")
    for g in cat:
        folder = os.path.join(common, g["name"])
        script = f"Vibecode3D_Play_{g['key']}.livecodescript"
        blob = git("show", f"{g['ref']}:{REPO_PREFIX}{script}", binary=True)
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, script), "wb") as f:
            f.write(blob)
        log.made(os.path.join(folder, script))
        for d in filter(None, g["data"].split(",")):
            ref = g["ref"] if d in git("ls-tree", "--name-only", g["ref"], REPO_PREFIX) else (g["betas"].split(",")[0] or "main")
            try:
                extract(ref, REPO_PREFIX + d, os.path.join(folder, d), log)
            except subprocess.CalledProcessError:
                say(f"  ({g['name']}: no {d} on {ref})")
        # self-describing: a loose copy of this folder still says what it is
        write(log, os.path.join(folder, "game.txt"),
              f"appid\t{g['appid']}\nname\t{g['name']}\nkind\t{g['kind']}\nscript\t{script}\n"
              f"data\t{g['data']}\nbranch\t{g['branch']}\nref\t{g['ref']}\nengine\t{VERSION}\n")
        write(log, os.path.join(folder, f"Play {g['name']}.cmd"), play_cmd(g["name"]), "")
        write(log, os.path.join(m.library, f"appmanifest_{g['appid']}.txt"),
              '"AppState"\n{\n' + kv({"appid": g["appid"], "name": g["name"], "installdir": g["name"],
                                      "StateFlags": 4, "LastUpdated": now, "SizeOnDisk": len(blob),
                                      "BetaKey": g["betas"] if g["branch"] == "beta" else ""}) + "}\n")

    # 3. per-user: settings (Roaming), machine cache and logs (Local), the Data folder (Documents)
    write(log, os.path.join(m.settings_dir, "config.txt"),
          f"user\t{m.user or 'default'}\nlibrary\t{m.win(m.library)}\nlanguage\tenglish\n")
    write(log, os.path.join(m.settings_dir, "engine_path.txt"), m.win(os.path.join(m.install_dir, "Vibecode3D.exe")), "")
    os.makedirs(os.path.join(m.cache_dir, "logs"), exist_ok=True)
    os.makedirs(os.path.join(m.cache_dir, "crashdumps"), exist_ok=True)
    write(log, os.path.join(m.cache_dir, "logs", "install.log"), f"{now} installed {len(cat)} titles\n")
    data = m.data_root_default
    if not os.path.exists(os.path.join(data, "ROOT.md")):
        write(log, os.path.join(data, "ROOT.md"),
              "# The Data folder\n\nWhere Vibecode3D keeps what you make and your saves "
              "(LIB_DATA). Saves: Users/<you>/Saves/<Game>/. Work/ is safe to empty.\n")
    for g in cat:
        os.makedirs(os.path.join(data, "Users", m.user or "default", "Saves", g["name"]), exist_ok=True)

    # 4. shortcuts (real .lnk files when PowerShell is there)
    shortcut(m, log, os.path.join(m.desktop, "Vibecode3D.lnk"), os.path.join(m.install_dir, "Vibecode3D.exe"))
    shortcut(m, log, os.path.join(m.start_menu, "Vibecode3D", "Vibecode3D.lnk"), os.path.join(m.install_dir, "Vibecode3D.exe"))

    write(log, os.path.join(m.install_dir, "uninstall.log"), "\r\n".join(log.lines) + "\r\n", "")
    say(f"installed {len(cat)} titles + common into {m.win(m.install_dir)}; {len(log.lines)} files logged")
    return log


def shortcut(m, log, lnk, target):
    os.makedirs(os.path.dirname(lnk), exist_ok=True)
    ps = shutil.which("powershell.exe")
    if ps and m.drive == "/mnt/" + m.letter.lower():     # a real drive letter: a real .lnk
        cmd = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{m.win(lnk)}');"
               f"$s.TargetPath='{m.win(target)}';$s.WorkingDirectory='{m.win(os.path.dirname(target))}';$s.Save()")
        r = subprocess.run([ps, "-NoProfile", "-Command", cmd], capture_output=True)
        if r.returncode == 0 and os.path.exists(lnk):
            log.made(lnk)
            return
    write(log, lnk[:-4] + ".url", f"[InternetShortcut]\r\nURL=file:///{m.win(target)}\r\n", "")


def uninstall(m, purge=False):
    """Do what real uninstallers do: remove the files in uninstall.log and empty folders, and
    leave settings, saves and anything added later (mods, logs) unless --purge."""
    logf = os.path.join(m.install_dir, "uninstall.log")
    left, gone = [], 0
    if os.path.exists(logf):
        with open(logf, encoding="utf-8") as f:
            for line in f.read().splitlines():
                if not line:
                    continue
                p = m.wsl(line)
                keep = not purge and (p.startswith(m.roaming) or p.startswith(m.documents) or p.startswith(m.local))
                if keep:
                    left.append(line)
                elif os.path.exists(p):
                    os.remove(p)
                    gone += 1
        if os.path.exists(logf):
            os.remove(logf)
    for top in (m.install_dir, os.path.join(m.start_menu, "Vibecode3D")) + ((m.settings_dir, m.cache_dir) if purge else ()):
        for root, dirs, files in os.walk(top, topdown=False):
            if not os.listdir(root):
                os.rmdir(root)
    stray = []
    for top in (m.install_dir, m.settings_dir, m.cache_dir, m.data_root_default):
        for root, _d, files in os.walk(top):
            stray += [m.win(os.path.join(root, fn)) for fn in files]
    print(f"removed {gone} files; left behind {len(stray)} (settings, saves, logs, anything added later)")
    return stray


# ---------------------------------------------------------------- the model: what the launcher and games find

# every quoted path into a LIB (no spaces: messages are not paths), e.g. "LIB_MAP/livecode/lib_map.livecodescript"
ASKS = re.compile(r'"(?:[^" ]*/)?(LIB_[A-Z]+/[^" ]*)"')


def game_folders(m, libraries=None):
    """Every game folder the launcher would list: each library's common\\*\\game.txt
    (self-describing, so a folder without its appmanifest is still found)."""
    out = []
    for lib in libraries or library_list(m):
        common = os.path.join(lib, "common")
        if not os.path.isdir(common):
            continue
        for name in sorted(os.listdir(common)):
            gt = os.path.join(common, name, "game.txt")
            if os.path.isfile(gt):
                out.append(os.path.join(common, name))
    return out


def library_list(m):
    """The default library beside the exe, then those in libraryfolders.txt."""
    libs = [m.library] if os.path.isdir(m.library) else []
    lf = os.path.join(m.library, "libraryfolders.txt")
    if os.path.exists(lf):
        for p in re.findall(r'"path"\s+"([^"]+)"', open(lf, encoding="utf-8").read()):
            lib = os.path.join(m.wsl(p), APPS_DIR)
            if lib not in libs and os.path.isdir(lib):
                libs.append(lib)
    return libs


def read_game_txt(folder):
    d = {}
    with open(os.path.join(folder, "game.txt"), encoding="utf-8") as f:
        for line in f:
            if "\t" in line:
                k, v = line.rstrip("\r\n").split("\t", 1)
                d[k] = v
    return d


def find_today(engine_file, rel, m, owner_pc):
    """FindFile as the games have it now: up to six folders up from the engine stack's file,
    then the owner's WSL projects folder (which exists on the owner's PC only)."""
    p = engine_file
    for _ in range(6):
        p = os.path.dirname(p)
        if not p or p == os.path.dirname(p):
            break
        if os.path.exists(os.path.join(p, rel)):
            return "found"
    if owner_pc and os.path.exists(os.path.join(PROJECTS, rel)):
        return "owner-pc-only"
    return "missing"


def find_proposed(game_dir, rel, libraries):
    """Proposed Game.FindFile: the game's own folder first (LIB_GAMES/Vibecode3D_Games/X -> X),
    then Vibecode3D Common in each library."""
    short = rel[len(DEV_PREFIX):] if rel.startswith(DEV_PREFIX) else rel
    if os.path.exists(os.path.join(game_dir, short)):
        return "found"
    for lib in libraries:
        c = os.path.join(lib, "common", "Vibecode3D Common")
        if os.path.exists(os.path.join(c, rel)) or os.path.exists(os.path.join(c, short)):
            return "found"
    return "missing"


def verify(m, engine=None, libraries=None, owner_pc=True, quiet=False):
    """One row per game: can it start, and does each file it asks for get found, today and with
    the proposed lookup. Returns (rows, problems)."""
    engine = engine or os.path.join(m.install_dir, "Vibecode3D.exe")
    libs = libraries if libraries is not None else library_list(m)
    rows = []
    for folder in game_folders(m, libs):
        g = read_game_txt(folder)
        if g.get("kind") == "redist":
            continue
        script = os.path.join(folder, g.get("script", ""))
        row = {"game": g.get("name", os.path.basename(folder)), "start": "ok", "today": "ok",
               "proposed": "ok", "needs": ""}
        if not os.path.isfile(script):
            row["start"] = "no script"
        elif not os.path.isfile(engine):
            row["start"] = "no engine"
        else:
            txt = open(script, encoding="utf-8", errors="replace").read()
            asks = sorted(set(a for hit in ASKS.findall(txt) for a in hit.split(",") if a.startswith("LIB_")))
            t = [(r, find_today(engine, r, m, owner_pc)) for r in asks]
            p = [(r, find_proposed(folder, r, libs)) for r in asks]
            if any(s == "missing" for _r, s in t):
                row["today"] = "MISSING " + str(sum(s == "missing" for _r, s in t))
            elif any(s == "owner-pc-only" for _r, s in t):
                row["today"] = "owner PC only"
            if any(s == "missing" for _r, s in p):
                row["proposed"] = "MISSING " + str(sum(s == "missing" for _r, s in p))
            row["needs"] = ", ".join(r.split("/")[0] for r, s in p if s == "missing" and not r.startswith(DEV_PREFIX))
        rows.append(row)
    problems = [r for r in rows if r["start"] != "ok" or r["today"] != "ok"]
    if not quiet:
        print(f"{len(rows)} titles in {len(libs)} libraries; engine {'found' if os.path.isfile(engine) else 'MISSING'}")
        for r in rows:
            if r["start"] != "ok" or r["today"] != "ok" or r["proposed"] != "ok":
                print(f"  {r['game']:<24} start {r['start']:<10} data today: {r['today']:<14} proposed: {r['proposed']}"
                      + (f"  (needs {r['needs']})" if r["needs"] else ""))
    return rows, problems


def status(m):
    for label, p in (("program", m.install_dir), ("library", m.library), ("settings", m.settings_dir),
                     ("cache/logs", m.cache_dir), ("Data", m.data_root_default)):
        n = sum(len(f) for _r, _d, f in os.walk(p)) if os.path.isdir(p) else 0
        print(f"  {label:<11} {m.win(p):<55} {n} files" if n else f"  {label:<11} {m.win(p):<55} (none)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["install", "verify", "status", "uninstall", "catalog"])
    ap.add_argument("--drive", default="/mnt/v")
    ap.add_argument("--user")
    ap.add_argument("--purge", action="store_true")
    ap.add_argument("--games", help="comma-separated keys (default: all)")
    a = ap.parse_args()
    if a.cmd == "catalog":
        rows = build_catalog()
        print(f"{len(rows)} titles in catalog.tsv")
        return
    m = Machine(a.drive, a.user)
    if a.cmd == "install":
        install(m, a.games.split(",") if a.games else None)
    elif a.cmd == "verify":
        verify(m)
    elif a.cmd == "status":
        status(m)
    elif a.cmd == "uninstall":
        uninstall(m, a.purge)


if __name__ == "__main__":
    main()
