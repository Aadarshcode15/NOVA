# config/autostart.py
"""Windows startup registry management for NOVA."""
import winreg
from pathlib import Path
from core.logger import log

_REG_KEY   = r"Software\Microsoft\Windows\CurrentVersion\Run"
_REG_NAME  = "NOVA"


def _bat_path() -> str:
    bat = Path(__file__).resolve().parent.parent / "Start_NOVA.bat"
    return str(bat)


def is_enabled() -> bool:
    """Check if NOVA is registered to start with Windows."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY) as key:
            winreg.QueryValueEx(key, _REG_NAME)
            return True
    except FileNotFoundError:
        return False
    except Exception:
        return False


def enable() -> bool:
    """Register NOVA to launch with Windows."""
    try:
        cmd = f'"{_bat_path()}"'
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, _REG_NAME, 0, winreg.REG_SZ, cmd)
        log.info(f"[Autostart] Enabled: {cmd}")
        return True
    except Exception as e:
        log.error(f"[Autostart] Failed to enable: {e}")
        return False


def disable() -> bool:
    """Remove NOVA from Windows startup."""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_ALL_ACCESS
        ) as key:
            winreg.DeleteValue(key, _REG_NAME)
        log.info("[Autostart] Disabled.")
        return True
    except FileNotFoundError:
        return True   # already not registered
    except Exception as e:
        log.error(f"[Autostart] Failed to disable: {e}")
        return False