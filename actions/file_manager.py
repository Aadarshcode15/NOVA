# actions/file_manager.py — file DELETE is disabled for safety
import os
import shutil
from pathlib import Path
from core.voice import speak
from core.engine import query

TRIGGERS = (
    "file", "folder", "directory", "create file", "move file",
    "copy file", "rename file", "read file", "list files",
    "find file", "open file", "make folder", "create folder",
)

def _resolve(path_str: str) -> Path:
    p = path_str.strip().lower()
    replacements = {
        "desktop":   os.path.join(os.path.expanduser("~"), "Desktop"),
        "downloads": os.path.join(os.path.expanduser("~"), "Downloads"),
        "documents": os.path.join(os.path.expanduser("~"), "Documents"),
        "pictures":  os.path.join(os.path.expanduser("~"), "Pictures"),
        "music":     os.path.join(os.path.expanduser("~"), "Music"),
        "videos":    os.path.join(os.path.expanduser("~"), "Videos"),
    }
    for key, real in replacements.items():
        if key in p:
            p = p.replace(key, real)
    return Path(p)

def handle_files(command: str) -> bool:
    c = command.lower().strip()
    if not any(t in c for t in TRIGGERS):
        return False

    # ── BLOCKED: delete/remove file ──
    if any(k in c for k in ("delete file", "remove file", "delete the file", "remove the file")):
        speak("File deletion is disabled for safety.")
        return True

    # ── List files ──
    if any(k in c for k in ("list files", "list folder", "what's in", "show files", "show folder")):
        for loc in ("desktop", "downloads", "documents", "pictures", "music", "videos"):
            if loc in c:
                folder = _resolve(loc)
                try:
                    files = list(folder.iterdir())
                    if not files:
                        speak(f"The {loc} folder is empty.")
                        return True
                    names = [f.name for f in files[:10]]
                    speak(f"The {loc} folder has {len(files)} items. First ones: {', '.join(names)}.")
                except Exception as e:
                    speak(f"Couldn't read the {loc} folder.")
                    print(f"[Files Error] {e}")
                return True
        speak("Which folder? Try desktop, downloads, or documents.")
        return True

    # ── Find file ──
    if any(k in c for k in ("find file", "find", "search file", "where is")):
        query_str = c
        for filler in sorted(["find the file", "find file", "where is the file",
                               "where is", "find"], key=len, reverse=True):
            query_str = query_str.replace(filler, "")
        query_str = query_str.strip()
        if not query_str:
            speak("What file are you looking for?")
            return True
        speak(f"Searching for {query_str}.")
        try:
            home  = Path.home()
            found = []
            for root, dirs, files in os.walk(home):
                dirs[:] = [d for d in dirs if not d.startswith(".")
                           and d not in ("AppData", "__pycache__", "node_modules")]
                for f in files:
                    if query_str.lower() in f.lower():
                        found.append(os.path.join(root, f))
                if len(found) >= 5:
                    break
            if found:
                speak(f"Found {len(found)} match{'es' if len(found) > 1 else ''}.")
                for f in found[:3]:
                    speak(f)
            else:
                speak(f"Couldn't find any file named {query_str}.")
        except Exception as e:
            print(f"[Find File Error] {e}")
            speak("File search failed.")
        return True

    # ── Create file ──
    if any(k in c for k in ("create file", "make file", "new file")):
        fname = c
        for filler in sorted(["create a file called", "create file called",
                               "make a file called", "new file called",
                               "create file", "make file", "new file"], key=len, reverse=True):
            fname = fname.replace(filler, "")
        fname = fname.strip().strip(".,!?")
        if not fname:
            speak("What should I name the file?")
            return True
        desktop = Path.home() / "Desktop"
        fpath   = desktop / fname
        try:
            fpath.touch()
            speak(f"Created {fname} on your desktop.")
        except Exception as e:
            print(f"[Create File Error] {e}")
            speak(f"Couldn't create {fname}.")
        return True

    # ── Create folder ──
    if any(k in c for k in ("create folder", "make folder", "new folder")):
        fname = c
        for filler in sorted(["create a folder called", "create folder called",
                               "make a folder called", "new folder called",
                               "create folder", "make folder", "new folder"], key=len, reverse=True):
            fname = fname.replace(filler, "")
        fname = fname.strip().strip(".,!?")
        if not fname:
            speak("What should I name the folder?")
            return True
        desktop = Path.home() / "Desktop"
        fpath   = desktop / fname
        try:
            fpath.mkdir(parents=True, exist_ok=True)
            speak(f"Created folder {fname} on your desktop.")
        except Exception as e:
            print(f"[Create Folder Error] {e}")
            speak(f"Couldn't create folder {fname}.")
        return True

    # ── Read file ──
    if any(k in c for k in ("read file", "open file", "read the file")):
        fname = c
        for filler in sorted(["read the contents of", "read the file called",
                               "open the file called", "read file called",
                               "read the file", "read file", "open file"], key=len, reverse=True):
            fname = fname.replace(filler, "")
        fname = fname.strip().strip(".,!?")
        if not fname:
            speak("Which file would you like me to read?")
            return True
        try:
            desktop = Path.home() / "Desktop"
            fpath   = desktop / fname
            if not fpath.exists():
                fpath = Path.home() / "Documents" / fname
            if fpath.exists():
                content = fpath.read_text(encoding="utf-8", errors="ignore")
                if len(content) > 500:
                    speak(f"The file is long. Here are the first few lines.")
                    speak(content[:500])
                else:
                    speak(content)
            else:
                speak(f"Couldn't find {fname}.")
        except Exception as e:
            print(f"[Read File Error] {e}")
            speak(f"Couldn't read {fname}.")
        return True

    return False
