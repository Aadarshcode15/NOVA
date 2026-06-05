# actions/system_control.py
import os
import re
import subprocess
import datetime
import psutil
import pyautogui
import pyperclip
import time
import screen_brightness_control as sbc
from core.voice import speak
from core.logger import log

# ── App registry ───────────────────────────────────────────
# exe       = direct executable (must be in PATH)
# start X   = Windows shell "start" command (works for Chrome etc.)
# ms-X:     = Windows URI scheme
# search    = Windows Start-menu search (most reliable fallback)

APPS = {
    # Always-available Windows built-ins
    "notepad":             "notepad.exe",
    "calculator":          "calc.exe",
    "paint":               "mspaint.exe",
    "task manager":        "taskmgr.exe",
    "file explorer":       "search",       # special handler below
    "camera":              "microsoft.windows.camera:",
    "settings":            "ms-settings:",

    # Office — not in PATH on most machines, use Start search
    "word":                "search",
    "microsoft word":      "search",
    "excel":               "search",
    "microsoft excel":     "search",
    "powerpoint":          "search",
    "microsoft powerpoint":"search",

    # Dev tools
    "vs code":             "code",
    "visual studio code":  "code",

    # Browsers
    "chrome":              "start chrome",   # Chrome registers itself with shell
    "brave":               "search",         # not reliably in PATH
    "edge":                "start msedge",

    # Communication / Media — use search (installation paths vary per user)
    "discord":             "search",
    "spotify":             "search",
    "whatsapp":            "search",
    "telegram":            "search",
    "zoom":                "search",
    "teams":               "search",
    "microsoft teams":     "search",
    "slack":               "search",
    "vlc":                 "search",
    "chat gpt":             "search",

}


# ── Windows Start-menu search (universal opener) ───────────
def _open_via_windows_search(app_name: str) -> None:
    """
    Opens any app by name using the Windows Start menu.
    Works for any installed app regardless of PATH.
    """
    pyautogui.hotkey("win")
    time.sleep(0.8)
    pyautogui.write(app_name, interval=0.06)
    time.sleep(1.2)
    pyautogui.press("enter")
    time.sleep(0.4)


def _open_app(app_name: str, exe: str) -> None:
    try:
        if exe == "search":
            _open_via_windows_search(app_name)

        elif exe.startswith("start "):
            result = subprocess.run(exe, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                # shell "start X" failed — fall back to Windows search
                log.warning(f"[System] 'start' failed for {app_name}, trying Windows search")
                _open_via_windows_search(app_name)

        elif exe.endswith(":"):
            os.startfile(exe)

        else:
            # Direct exe — fall back to Windows search on failure
            try:
                subprocess.Popen(exe, shell=True)
            except Exception:
                log.warning(f"[System] Direct exe failed for {app_name}, trying Windows search")
                _open_via_windows_search(app_name)

    except Exception as e:
        log.error(f"[App Open Error] {app_name}: {e}")
        raise


# ── Volume helpers ─────────────────────────────────────────
def _set_volume_exact(level: int) -> None:
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        devices   = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume    = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMasterVolumeLevelScalar(level / 100, None)
    except Exception:
        pyautogui.press("volumedown", presses=50)
        if int(level / 2) > 0:
            pyautogui.press("volumeup", presses=int(level / 2))


# ── Main handler ───────────────────────────────────────────
def handle_system(command: str) -> bool:
    c = command.lower().strip()

    # ── Volume ──
    if "volume" in c or "mute" in c:
        if "unmute" in c:
            pyautogui.press("volumemute")
            speak("Unmuted.")
            return True
        if "mute" in c:
            pyautogui.press("volumemute")
            speak("Muted.")
            return True
        for w in c.split():
            if w.isdigit():
                level = max(0, min(100, int(w)))
                _set_volume_exact(level)
                speak(f"Volume set to {level}.")
                return True
        if any(k in c for k in ("up", "increase", "raise", "louder")):
            pyautogui.press("volumeup", presses=5)
            speak("Volume up.")
            return True
        if any(k in c for k in ("down", "decrease", "lower", "quieter")):
            pyautogui.press("volumedown", presses=5)
            speak("Volume down.")
            return True

    # ── Brightness ──
    if "brightness" in c:
        try:
            cur = sbc.get_brightness(display=0)[0]
            for w in c.split():
                if w.isdigit():
                    lvl = max(0, min(100, int(w)))
                    sbc.set_brightness(lvl, display=0)
                    speak(f"Brightness set to {lvl}.")
                    return True
            if any(k in c for k in ("up", "increase", "raise")):
                sbc.set_brightness(min(100, cur + 10), display=0)
                speak("Brightness increased.")
                return True
            if any(k in c for k in ("down", "decrease", "lower")):
                sbc.set_brightness(max(0, cur - 10), display=0)
                speak("Brightness decreased.")
                return True
        except Exception as e:
            log.error(f"[Brightness Error] {e}")
            speak("Couldn't control brightness.")
        return True

    # ── Screenshot ──
    if "screenshot" in c or "capture screen" in c:
        try:
            desktop = os.path.expanduser("~/Desktop")
            fname   = f"NOVA_Screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            fpath   = os.path.join(desktop, fname)
            pyautogui.screenshot(fpath)
            speak("Screenshot saved to your desktop.")
        except Exception as e:
            log.error(f"[Screenshot Error] {e}")
            speak("Couldn't take the screenshot.")
        return True

    # ── Clipboard ──
    if "clipboard" in c:
        try:
            if any(k in c for k in ("read", "what", "paste", "show")):
                content = pyperclip.paste()
                if not content.strip():
                    speak("Your clipboard is empty.")
                else:
                    snippet = content[:200] + ("..." if len(content) > 200 else "")
                    speak(f"Clipboard contains: {snippet}")
            elif "clear" in c:
                pyperclip.copy("")
                speak("Clipboard cleared.")
        except Exception as e:
            log.error(f"[Clipboard Error] {e}")
            speak("Couldn't access clipboard.")
        return True

    # ── Battery ──
    if "battery" in c:
        try:
            bat = psutil.sensors_battery()
            if bat is None:
                speak("No battery detected on this device.")
                return True
            pct = int(bat.percent)
            if bat.power_plugged:
                status = "charging" if pct < 100 else "fully charged"
            elif bat.secsleft in (psutil.POWER_TIME_UNLIMITED, psutil.POWER_TIME_UNKNOWN):
                status = "on battery"
            else:
                h, m   = bat.secsleft // 3600, (bat.secsleft % 3600) // 60
                status = f"on battery, about {h} hours {m} minutes remaining"
            speak(f"Battery is at {pct} percent, {status}.")
        except Exception as e:
            log.error(f"[Battery Error] {e}")
            speak("Couldn't read battery status.")
        return True

    # ── Open known app (APPS registry) ──
    for app_name, exe in APPS.items():
        if app_name in c:
            speak(f"Opening {app_name}.")
            try:
                _open_app(app_name, exe)
            except Exception as e:
                speak(f"Couldn't open {app_name}.")
                log.error(f"[App Error] {app_name}: {e}")
            return True

    # ── Open known website ──
    import webbrowser
    SITES = {
        "google":    "https://google.com",
        "youtube":   "https://youtube.com",
        "github":    "https://github.com",
        "facebook":  "https://facebook.com",
        "instagram": "https://instagram.com",
        "twitter":   "https://twitter.com",
        "linkedin":  "https://linkedin.com",
        "reddit":    "https://reddit.com",
        "netflix":   "https://netflix.com",
        "gmail":     "https://mail.google.com",
    }
    for site, url in SITES.items():
        if f"open {site}" in c:
            speak(f"Opening {site}.")
            webbrowser.open(url)
            return True

    # ── Open ANY app via Windows search (catch-all) ──
    # Catches "open [anything not in the lists above]"
    open_match = re.match(r"^(?:open|launch|start)\s+(.+)$", c)
    if open_match:
        app_query = open_match.group(1).strip()
        # Skip if it's a file/folder operation (handled by file_manager)
        skip_words = ("file", "folder", "document", "my ", "the ")
        if not any(app_query.startswith(w) for w in skip_words):
            speak(f"Searching for {app_query}.")
            try:
                _open_via_windows_search(app_query)
                log.info(f"[System] Opened via Windows search: {app_query}")
            except Exception as e:
                speak(f"Couldn't find {app_query}.")
                log.error(f"[System] Windows search failed for '{app_query}': {e}")
            return True

    return False