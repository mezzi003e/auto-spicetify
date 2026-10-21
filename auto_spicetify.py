"""
Auto Spicetify
==============
Keeps Spicetify applied across Spotify updates on Windows.

Usage
-----
  auto_spicetify.exe              Double-click once: installs itself, adds a
                                  Startup shortcut and starts watching.
  auto_spicetify.exe --uninstall  Removes the Startup shortcut and the app.
  auto_spicetify.exe --monitor    Run the watcher directly (used by Startup).

How it works
------------
Spotify applies updates when it is relaunched, so the watcher waits for
Spotify to start, compares Spotify's version with the last version it applied
Spicetify to, and runs `spicetify backup apply` (as the Spicetify docs
recommend) whenever the version changed.
"""

import ctypes
import os
import shutil
import subprocess
import sys
import time

# --------------------------------------------------------------------------
# Paths / settings
# --------------------------------------------------------------------------
APP_NAME = "Auto Spicetify"
EXE_NAME = "auto_spicetify.exe"

INSTALL_DIR = os.path.expandvars(r"%LOCALAPPDATA%\AutoSpicetify")
TARGET_EXE = os.path.join(INSTALL_DIR, EXE_NAME)
STATE_FILE = os.path.join(INSTALL_DIR, "state.txt")
LOG_FILE = os.path.join(INSTALL_DIR, "auto_spicetify.log")

STARTUP_FOLDER = os.path.expandvars(
    r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
)
SHORTCUT_PATH = os.path.join(STARTUP_FOLDER, "AutoSpicetify.lnk")

SPICETIFY_EXE = os.path.expandvars(r"%LOCALAPPDATA%\spicetify\spicetify.exe")
SPOTIFY_CANDIDATES = [
    os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"),
    os.path.expandvars(r"%LOCALAPPDATA%\Spotify\Spotify.exe"),
]
SPICETIFY_INSTALL_CMD = (
    "iwr -useb https://raw.githubusercontent.com/spicetify/cli/main/install.ps1 | iex"
)

CHECK_INTERVAL = 5      # seconds between "is Spotify running?" checks
SETTLE_DELAY = 10       # seconds to wait after Spotify starts before applying
RETRY_AFTER = 3600      # seconds between retries after a failed apply
MAX_LOG_BYTES = 1_000_000

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
DETACHED = getattr(subprocess, "DETACHED_PROCESS", 0)

_mutex_handle = None  # keeps the single-instance mutex alive


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def log(message):
    try:
        os.makedirs(INSTALL_DIR, exist_ok=True)
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > MAX_LOG_BYTES:
            os.replace(LOG_FILE, LOG_FILE + ".old")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {message}\n")
    except OSError:
        pass


def msgbox(text):
    """Show a message box (works even in a windowless build)."""
    try:
        ctypes.windll.user32.MessageBoxW(0, text, APP_NAME, 0x40)
    except Exception:
        print(text)


def ps_quote(value):
    """Escape a string for use inside single quotes in PowerShell."""
    return value.replace("'", "''")


def same_path(a, b):
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def kill_other_instances():
    subprocess.run(
        ["taskkill", "/F", "/IM", EXE_NAME, "/FI", f"PID ne {os.getpid()}"],
        capture_output=True,
        creationflags=NO_WINDOW,
    )


def single_instance():
    """Return False if another copy of the watcher is already running."""
    global _mutex_handle
    kernel32 = ctypes.windll.kernel32
    _mutex_handle = kernel32.CreateMutexW(None, False, "AutoSpicetifySingleton")
    return kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS


# --------------------------------------------------------------------------
# Spotify / Spicetify
# --------------------------------------------------------------------------
def find_spotify():
    for path in SPOTIFY_CANDIDATES:
        if os.path.exists(path):
            return path
    return None


def is_spotify_running():
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", "IMAGENAME eq Spotify.exe", "/NH"],
            creationflags=NO_WINDOW,
        ).decode(errors="ignore")
        return "spotify.exe" in out.lower()
    except Exception:
        return False


def spotify_version(spotify_path):
    try:
        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                f"(Get-Item '{ps_quote(spotify_path)}').VersionInfo.ProductVersion",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=NO_WINDOW,
        )
        return result.stdout.strip()
    except Exception as e:
        log(f"Could not read Spotify version: {e}")
        return ""


def spicetify_path():
    if os.path.exists(SPICETIFY_EXE):
        return SPICETIFY_EXE
    return shutil.which("spicetify")


def ensure_spicetify():
    if spicetify_path():
        return True
    log("Spicetify not found - running the official installer")
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", SPICETIFY_INSTALL_CMD],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=600,
            creationflags=NO_WINDOW,
        )
    except Exception as e:
        log(f"Spicetify installer failed: {e}")
    return spicetify_path() is not None


def run_spicetify(*args):
    exe = spicetify_path()
    if not exe:
        log("spicetify executable not found")
        return False
    try:
        r = subprocess.run(
            [exe, *args],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=600,
            creationflags=NO_WINDOW,
        )
    except Exception as e:
        log(f"spicetify {' '.join(args)} crashed: {e}")
        return False
    log(f"spicetify {' '.join(args)} -> exit {r.returncode}\n{r.stdout}{r.stderr}")
    return r.returncode == 0


def reapply():
    """Reapply Spicetify the way the docs recommend, with a fallback."""
    if not ensure_spicetify():
        return False
    if run_spicetify("backup", "apply"):
        return True
    log("backup apply failed - trying upgrade + restore backup apply")
    run_spicetify("upgrade")
    return run_spicetify("restore", "backup", "apply")


# --------------------------------------------------------------------------
# State
# --------------------------------------------------------------------------
def read_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def write_state(value):
    os.makedirs(INSTALL_DIR, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        f.write(value)


# --------------------------------------------------------------------------
# Watcher
# --------------------------------------------------------------------------
def monitor():
    log("Watcher started")

    spotify = None
    while not spotify:
        spotify = find_spotify()
        if not spotify:
            time.sleep(30)
    log(f"Watching {spotify}")

    last_applied = read_state()
    was_running = False
    needs_check = True
    next_try = 0.0

    while True:
        try:
            running = is_spotify_running()
            if running and not was_running:
                needs_check = True  # Spotify just (re)launched, maybe updated
            was_running = running

            if running and needs_check and time.time() >= next_try:
                time.sleep(SETTLE_DELAY)
                current = spotify_version(spotify)
                if not current or current == last_applied:
                    needs_check = False
                elif reapply():
                    last_applied = current
                    write_state(current)
                    needs_check = False
                    log(f"Spicetify applied for Spotify {current}")
                else:
                    next_try = time.time() + RETRY_AFTER
                    log(f"Apply failed for Spotify {current}; retrying later")
        except Exception as e:
            log(f"Unexpected error: {e}")
        time.sleep(CHECK_INTERVAL)


def run_monitor():
    if not single_instance():
        return
    monitor()


# --------------------------------------------------------------------------
# Install / uninstall
# --------------------------------------------------------------------------
def install():
    if not getattr(sys, "frozen", False):
        print("Build the .exe first (see build.bat), then run it to install.")
        return

    os.makedirs(INSTALL_DIR, exist_ok=True)
    kill_other_instances()
    time.sleep(1)

    if not same_path(sys.executable, TARGET_EXE):
        shutil.copy2(sys.executable, TARGET_EXE)

    ps = (
        "$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut('{ps_quote(SHORTCUT_PATH)}'); "
        f"$s.TargetPath = '{ps_quote(TARGET_EXE)}'; "
        f"$s.WorkingDirectory = '{ps_quote(INSTALL_DIR)}'; "
        f"$s.IconLocation = '{ps_quote(TARGET_EXE)},0'; "
        "$s.Save()"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps], creationflags=NO_WINDOW
    )

    subprocess.Popen([TARGET_EXE, "--monitor"], creationflags=NO_WINDOW | DETACHED)
    msgbox(
        "Installed!\n\n"
        "Auto Spicetify is now running in the background and will start "
        "with Windows. It reapplies Spicetify after Spotify updates.\n\n"
        f"Log: {LOG_FILE}"
    )


def uninstall():
    kill_other_instances()
    time.sleep(1)
    try:
        os.remove(SHORTCUT_PATH)
    except OSError:
        pass
    shutil.rmtree(INSTALL_DIR, ignore_errors=True)
    msgbox("Auto Spicetify was removed.")


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------
def main():
    if os.name != "nt":
        print("Auto Spicetify only supports Windows.")
        sys.exit(1)

    args = [a.lower() for a in sys.argv[1:]]

    if "--uninstall" in args:
        uninstall()
    elif "--install" in args:
        install()
    elif "--monitor" in args:
        run_monitor()
    elif getattr(sys, "frozen", False) and not same_path(sys.executable, TARGET_EXE):
        install()  # double-clicked from Downloads etc.
    else:
        run_monitor()  # launched from the install folder (Startup shortcut)


if __name__ == "__main__":
    main()
