# actions/code_helper.py
import os
import subprocess
from pathlib import Path
from core.voice import speak
from core.engine import query
from core.logger import log

TRIGGERS = (
    "write code", "write a code", "create code", "generate code",
    "run code", "run the code", "execute code", "run script",
    "explain code", "explain the code", "what does this code",
    "fix code", "fix the code", "debug code",
    "write a script", "write script", "code a"
)

def handle_code(command: str) -> bool:
    c = command.lower().strip()
    if not any(t in c for t in TRIGGERS):
        return False

    # ── Write code ──
    if any(k in c for k in ("write code", "write a code", "generate code",
                             "create code", "write a script", "write script", "code a")):
        task = c
        for filler in sorted([
            "write me a code to", "write a code to", "write code to",
            "generate code to", "create code to", "write a script to",
            "write script to", "write code for", "write a code for",
            "code a", "write code", "write a code", "generate code",
            "create code", "write script"
        ], key=len, reverse=True):
            task = task.replace(filler, "")
        task = task.strip()

        if not task:
            speak("What would you like me to code?")
            return True

        speak(f"Writing code for {task}. One moment.")
        try:
            code = query(
                f"Write clean, well-commented Python code to: {task}\n"
                f"Return ONLY the code. No explanations, no markdown backticks.",
                skip_history=True
            )
            # Detect language and set extension
            ext      = ".py"
            filename = f"nova_code_{task[:20].replace(' ', '_')}{ext}"
            desktop  = Path.home() / "Desktop"
            fpath    = desktop / filename

            fpath.write_text(code, encoding="utf-8")
            speak(f"Done. I've written the code and saved it as {filename} on your desktop.")
        except Exception as e:
            log.error(f"[Code Write Error] {e}")
            speak("Sorry, I couldn't write that code.")
        return True

    # ── Run code ──
    if any(k in c for k in ("run code", "run the code", "execute code",
                             "run script", "execute script")):
        fname = c
        for filler in sorted(["run the code in", "run the code", "run code in",
                               "execute the code", "run script", "run code",
                               "execute"], key=len, reverse=True):
            fname = fname.replace(filler, "")
        fname = fname.strip()

        if not fname:
            # Try running the last nova_code file on desktop
            desktop = Path.home() / "Desktop"
            py_files = sorted(desktop.glob("nova_code_*.py"), key=os.path.getmtime, reverse=True)
            if py_files:
                fname = str(py_files[0])
                speak(f"Running {py_files[0].name}.")
            else:
                speak("Which file should I run?")
                return True
        else:
            desktop = Path.home() / "Desktop"
            fpath   = desktop / fname
            if not fpath.exists():
                fpath = Path(fname)
            if not fpath.exists():
                speak(f"Couldn't find {fname}.")
                return True
            speak(f"Running {fname}.")
            fname = str(fpath)

        try:
            result = subprocess.run(
                ["python", fname],
                capture_output=True, text=True, timeout=30
            )
            output = result.stdout.strip() or result.stderr.strip()
            if output:
                if len(output) > 300:
                    speak(f"Script ran. Output starts with: {output[:300]}")
                else:
                    speak(f"Script ran. Output: {output}")
            else:
                speak("Script ran successfully with no output.")
        except subprocess.TimeoutExpired:
            speak("The script took too long and was stopped.")
        except Exception as e:
            log.error(f"[Run Code Error] {e}")
            speak("Couldn't run that script.")
        return True

    # ── Explain code ──
    if any(k in c for k in ("explain code", "explain the code", "what does this code")):
        fname = c
        for filler in sorted(["explain the code in", "explain the code",
                               "what does this code do", "explain code in",
                               "explain code"], key=len, reverse=True):
            fname = fname.replace(filler, "")
        fname = fname.strip()

        if not fname:
            # Try most recent nova_code file
            desktop  = Path.home() / "Desktop"
            py_files = sorted(desktop.glob("nova_code_*.py"), key=os.path.getmtime, reverse=True)
            if py_files:
                content = py_files[0].read_text(encoding="utf-8")
                fname   = py_files[0].name
            else:
                speak("Which file should I explain?")
                return True
        else:
            desktop = Path.home() / "Desktop"
            fpath   = desktop / fname
            if not fpath.exists():
                speak(f"Couldn't find {fname}.")
                return True
            content = fpath.read_text(encoding="utf-8", errors="ignore")

        speak(f"Let me explain that code.")
        try:
            explanation = query(
                f"Explain this code in 3-4 simple spoken sentences. "
                f"No markdown, no bullet points:\n\n{content[:2000]}",
                skip_history=True
            )
            speak(explanation)
        except Exception as e:
            log.error(f"[Explain Code Error] {e}")
            speak("Couldn't explain that code.")
        return True

    # ── Fix / Debug code ──
    if any(k in c for k in ("fix code", "fix the code", "debug code", "debug the code")):
        desktop  = Path.home() / "Desktop"
        py_files = sorted(desktop.glob("nova_code_*.py"), key=os.path.getmtime, reverse=True)
        if not py_files:
            speak("I couldn't find any code file to fix.")
            return True

        fpath   = py_files[0]
        content = fpath.read_text(encoding="utf-8")
        speak(f"Let me fix {fpath.name}.")
        try:
            fixed = query(
                f"Fix any bugs in this Python code. "
                f"Return ONLY the corrected code. No markdown, no explanations:\n\n{content}",
                skip_history=True
            )
            fpath.write_text(fixed, encoding="utf-8")
            speak(f"Done. I've fixed the code and saved it back to {fpath.name}.")
        except Exception as e:
            log.error(f"[Fix Code Error] {e}")
            speak("Couldn't fix that code.")
        return True

    return False