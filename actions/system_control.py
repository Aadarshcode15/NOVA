# actions/system_control.py
import os
import subprocess
import datetime
import psutil
import pyautogui
import pyperclip
import screen_brightness_control as sbc
from core.voice import speak

APPS = {
    "notepad":            "notepad.exe",
    "calculator":         "calc.exe",
    "paint":              "mspaint.exe",
    "word":               "winword.exe",
    "excel":              "excel.exe",
    "powerpoint":         "powerpnt.exe",
    "file explorer":      "explorer.exe",
    "task manager":       "taskmgr.exe",
    "vs code":            "code",
    "visual studio code": "code",
    "camera":             "microsoft.windows.camera:",
    "settings":           "ms-settings:",
    "chrome":             "start chrome",
    "brave":              "start brave",
    "discord":            "start discord",
    "spotify":            "start spotify",
    "whatsapp":           "whatsapp",   # searched via windows start
}

def _open_app(app_name: str, exe: str) -> None:
    """Open an app, using Windows search for special apps."""
    try:
        if exe == "whatsapp":
            # Use Windows search to find and open WhatsApp
            import pyautogui, time
            pyautogui.hotkey('win')
            time.sleep(0.8)
            pyautogui.typewrite('whatsapp', interval=0.05)
            time.sleep(1.0)
            pyautogui.press('enter')
        elif exe.startswith("start "):
            subprocess.Popen(exe, shell=True)
        elif exe.endswith(":"):
            os.startfile(exe)
        else:
            subprocess.Popen(exe, shell=True)
    except Exception as e:
        print(f"[App Open Error] {e}")
        raise

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

def handle_system(command: str) -> bool:
    c = command.lower().strip()

    # ── REMOVED: Shutdown / Restart / Sleep / Lock (disabled for safety) ──

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
            print(f"[Brightness Error] {e}")
            speak("Couldn't control brightness.")
        return True

    # ── Screenshot ──
    if "screenshot" in c or "capture screen" in c:
        try:
            import ctypes, ctypes.wintypes
            buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, buf)
            desktop = buf.value if os.path.exists(buf.value) else os.path.expanduser("~/Desktop")
            fname   = f"NOVA_Screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            fpath   = os.path.join(desktop, fname)
            pyautogui.screenshot(fpath)
            speak(f"Screenshot saved to your desktop.")
        except Exception as e:
            print(f"[Screenshot Error] {e}")
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
            print(f"[Clipboard Error] {e}")
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
            print(f"[Battery Error] {e}")
            speak("Couldn't read battery status.")
        return True

    # ── Open App ──
    for app_name, exe in APPS.items():
        if app_name in c:
            speak(f"Opening {app_name}.")
            try:
                _open_app(app_name, exe)
            except Exception as e:
                speak(f"Couldn't open {app_name}.")
                print(f"[App Error] {e}")
            return True

    # ── Open Website ──
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

    return False
