# core/alerts.py
"""
Proactive system monitor. Runs in background, speaks alerts when
critical thresholds are crossed. Only fires while NOVA is ACTIVE
(not in sleep mode). 10-minute cooldown per alert type.
"""
import time
import threading
import psutil
from core.logger import log

# ── Thresholds ─────────────────────────────────────────────────
THRESHOLDS = {
    "battery_low":      15,    # % — warn
    "battery_critical":  5,    # % — urgent
    "ram_high":         90,    # % — warn
    "disk_low_gb":       5,    # GB free on C:\ — warn
    "temp_high":        85,    # °C — warn
    "cpu_sustained":    95,    # % for sustained period — warn
}

_COOLDOWN_SECS = 600          # 10 minutes between same alert
_CHECK_INTERVAL = 60          # check every 60 seconds

# ── State ──────────────────────────────────────────────────────
_last_alert: dict  = {}       # alert_type → timestamp of last fire
_running:    bool  = False
_cpu_high_since: float = 0.0


def _on_cooldown(alert_type: str) -> bool:
    last = _last_alert.get(alert_type, 0)
    return time.time() - last < _COOLDOWN_SECS


def _fire_alert(alert_type: str, message: str) -> None:
    """Speak alert and record timestamp."""
    from core.voice import speak, get_nova_state
    from core.voice import NovaState

    # Only alert when NOVA is actively listening
    try:
        if get_nova_state() != NovaState.ACTIVE:
            return
    except Exception:
        return

    if _on_cooldown(alert_type):
        return

    _last_alert[alert_type] = time.time()
    log.info(f"[Alert] {alert_type}: {message}")
    speak(message)


def _check() -> None:
    """Run one cycle of all system checks."""
    global _cpu_high_since

    # ── Battery ────────────────────────────────────────────────
    try:
        bat = psutil.sensors_battery()
        if bat and not bat.power_plugged:
            pct = int(bat.percent)
            if pct <= THRESHOLDS["battery_critical"]:
                _fire_alert(
                    "battery_critical",
                    f"Critical warning: battery at {pct} percent. Plug in your charger immediately."
                )
            elif pct <= THRESHOLDS["battery_low"]:
                _fire_alert(
                    "battery_low",
                    f"Battery at {pct} percent. You should plug in your charger soon."
                )
    except Exception:
        pass

    # ── RAM ────────────────────────────────────────────────────
    try:
        ram = psutil.virtual_memory().percent
        if ram >= THRESHOLDS["ram_high"]:
            used_gb = psutil.virtual_memory().used / (1024 ** 3)
            _fire_alert(
                "ram_high",
                f"Memory usage is at {int(ram)} percent — {used_gb:.1f} GB used. "
                f"Consider closing some applications."
            )
    except Exception:
        pass

    # ── Disk space ─────────────────────────────────────────────
    try:
        disk    = psutil.disk_usage("C:\\")
        free_gb = disk.free / (1024 ** 3)
        if free_gb < THRESHOLDS["disk_low_gb"]:
            _fire_alert(
                "disk_low",
                f"Your C drive has only {free_gb:.1f} gigabytes remaining. "
                f"Consider freeing up some space."
            )
    except Exception:
        pass

    # ── CPU sustained high ─────────────────────────────────────
    try:
        cpu = psutil.cpu_percent(interval=None)
        if cpu >= THRESHOLDS["cpu_sustained"]:
            if _cpu_high_since == 0:
                _cpu_high_since = time.time()
            elif time.time() - _cpu_high_since > 30:
                _fire_alert(
                    "cpu_sustained",
                    f"CPU has been at {int(cpu)} percent for over 30 seconds. "
                    f"A process may be stuck."
                )
                _cpu_high_since = 0
        else:
            _cpu_high_since = 0
    except Exception:
        pass

    # ── Temperature ────────────────────────────────────────────
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for sensor_list in temps.values():
                for reading in sensor_list:
                    if reading.current >= THRESHOLDS["temp_high"]:
                        _fire_alert(
                            "temp_high",
                            f"System temperature is {reading.current:.0f} degrees Celsius. "
                            f"Make sure your vents are clear."
                        )
                        break
    except Exception:
        pass


def _monitor_loop() -> None:
    global _running
    log.info("[Alerts] System monitor started.")
    while _running:
        try:
            _check()
        except Exception as e:
            log.debug(f"[Alerts] Check error: {e}")
        time.sleep(_CHECK_INTERVAL)


def start_alerts() -> None:
    """Start the background system monitor. Call once at startup."""
    global _running
    if _running:
        return
    _running = True
    threading.Thread(
        target=_monitor_loop, daemon=True, name="SysAlerts"
    ).start()


def stop_alerts() -> None:
    global _running
    _running = False


def set_threshold(key: str, value: float) -> None:
    """Update a threshold at runtime."""
    if key in THRESHOLDS:
        THRESHOLDS[key] = value
        log.info(f"[Alerts] Threshold updated: {key} = {value}")