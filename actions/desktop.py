# actions/desktop.py
import os
import shutil
import ctypes
import requests
import subprocess
from pathlib import Path
from datetime import datetime
from core.voice import speak

TRIGGERS = (
    "wallpaper", "desktop", "organize desktop",
    "clean desktop", "sort desktop", "change background",
    "set wallpaper", "change wallpaper"
)

DESKTOP = Path.home() / "Desktop"

FILE_CATEGORIES = {
    "Images":    [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".ico"],
    "Videos":    [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv"],
    "Audio":     [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"],
    "Documents": [".pdf", ".doc", ".docx", ".txt", ".pptx", ".xlsx", ".csv"],
    "Code":      [".py", ".js", ".html", ".css", ".json", ".ts", ".cpp", ".java"],
    "Archives":  [".zip", ".rar", ".7z", ".tar", ".gz"],
    "Others":    [],
}

def _ext_to_category(ext: str) -> str:
    for cat, exts in FILE_CATEGORIES.items():
        if ext.lower() in exts:
            return cat
    return "Others"

def handle_desktop(command: str) -> bool:
    c = command.lower().strip()
    if not any(t in c for t in TRIGGERS):
        return False

    # ── Change Wallpaper (local file) ──
    if any(k in c for k in ("wallpaper", "change background", "set background",
                             "change wallpaper", "set wallpaper")):
        # Check if a file path or name was mentioned
        fname = c
        for filler in sorted([
            "change wallpaper to", "set wallpaper to",
            "change background to", "set background to",
            "change the wallpaper to", "set the wallpaper to",
            "change wallpaper", "set wallpaper",
            "change background", "set background", "wallpaper"
        ], key=len, reverse=True):
            fname = fname.replace(filler, "")
        fname = fname.strip()

        if fname:
            # Try to find the image on desktop or pictures
            search_dirs = [DESKTOP, Path.home() / "Pictures"]
            found_path  = None
            for d in search_dirs:
                for ext in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]:
                    candidate = d / (fname + ext)
                    if candidate.exists():
                        found_path = candidate
                        break
                    # Try exact name
                    candidate2 = d / fname
                    if candidate2.exists():
                        found_path = candidate2
                        break
                if found_path:
                    break

            if found_path:
                try:
                    ctypes.windll.user32.SystemParametersInfoW(
                        20, 0, str(found_path.resolve()), 3
                    )
                    speak(f"Wallpaper changed to {found_path.name}.")
                except Exception as e:
                    print(f"[Wallpaper Error] {e}")
                    speak("Couldn't change the wallpaper.")
            else:
                speak(f"Couldn't find an image called {fname} on your desktop or pictures folder.")
        else:
            speak(
                "Please say a file name. For example: "
                "set wallpaper to sunset, or change wallpaper to my photo."
            )
        return True

    # ── List Desktop files ──
    if any(k in c for k in ("show desktop", "list desktop", "what's on my desktop",
                             "what is on my desktop")):
        try:
            items = list(DESKTOP.iterdir())
            if not items:
                speak("Your desktop is empty.")
                return True
            files = [i.name for i in items if i.is_file()]
            dirs  = [i.name for i in items if i.is_dir()]
            parts = []
            if files:
                parts.append(f"{len(files)} file{'s' if len(files) != 1 else ''}")
            if dirs:
                parts.append(f"{len(dirs)} folder{'s' if len(dirs) != 1 else ''}")
            speak(f"Your desktop has {' and '.join(parts)}.")
            if files[:5]:
                speak(f"Files include: {', '.join(files[:5])}.")
        except Exception as e:
            print(f"[Desktop List Error] {e}")
            speak("Couldn't read your desktop.")
        return True

    # ── Organize Desktop ──
    if any(k in c for k in ("organize desktop", "organise desktop",
                             "clean desktop", "sort desktop", "tidy desktop")):
        try:
            items = [i for i in DESKTOP.iterdir() if i.is_file()]
            if not items:
                speak("Your desktop is already clean.")
                return True

            moved = 0
            for item in items:
                # Skip shortcuts and system files
                if item.suffix.lower() in (".lnk", ".url", ".ini"):
                    continue
                cat     = _ext_to_category(item.suffix)
                cat_dir = DESKTOP / cat
                cat_dir.mkdir(exist_ok=True)
                dest = cat_dir / item.name
                # Avoid overwriting
                if dest.exists():
                    stem = item.stem
                    dest = cat_dir / f"{stem}_{datetime.now().strftime('%H%M%S')}{item.suffix}"
                shutil.move(str(item), str(dest))
                moved += 1

            speak(
                f"Done. I've organised {moved} file{'s' if moved != 1 else ''} "
                f"on your desktop into folders by type."
            )
        except Exception as e:
            print(f"[Organize Desktop Error] {e}")
            speak("Couldn't organise the desktop.")
        return True

    return False