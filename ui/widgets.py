# ui/widgets.py
import math
import random
import psutil
import time
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QProgressBar
from PyQt6.QtCore    import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui     import (
    QPainter, QColor, QPen, QBrush, QFont,
    QRadialGradient, QPainterPath
)
from config.settings import C_NOVA, C_SORA, C_DIM, C_DIM_TXT

def _hex(c): return QColor(c)

# ═══════════════════════════════════════════════════════════
# CIRCULAR VISUALIZER  (Mark-XXXIX style)
# ═══════════════════════════════════════════════════════════
class CircularVisualizer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(520, 520)
        self._state     = "idle"
        self._assistant = "nova"
        self._phase     = 0.0
        self._bars      = [0.0] * 72
        self._rings = [
        {"r": 210, "speed": 0.4,  "w": 1.0, "alpha": 55,  "dash": 6,  "gap": 4},
        {"r": 190, "speed": -0.6, "w": 1.0, "alpha": 40,  "dash": 3,  "gap": 8},
        {"r": 170, "speed": 0.8,  "w": 0.8, "alpha": 30,  "dash": 2,  "gap": 12},
        {"r": 155, "speed": -0.3, "w": 1.2, "alpha": 70,  "dash": 8,  "gap": 3},
        {"r": 235, "speed": 0.2,  "w": 0.8, "alpha": 25,  "dash": 12, "gap": 8},
        {"r": 250, "speed": -0.15,"w": 0.6, "alpha": 15,  "dash": 4,  "gap": 20},
        ]
        self._ring_angles = [0.0] * len(self._rings)
        self._dots = [
            {"angle": i * 51.4, "r": 215, "phase": i * 0.9, "size": 3}
            for i in range(7)
        ]
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)

    def set_state(self, s): self._state = s
    def set_assistant(self, a): self._assistant = a.lower()

    def _color(self):
        return _hex(C_NOVA if self._assistant == "nova" else C_SORA)

    def _tick(self):
        self._phase += 0.035
        for i in range(len(self._rings)):
            self._ring_angles[i] = (self._ring_angles[i] + self._rings[i]["speed"]) % 360

        for i in range(len(self._bars)):
            if self._state == "listening":
                w = math.sin(self._phase * 2.8 + i * 0.28) * 0.5 + 0.5
                t = w * 0.75 + random.uniform(0, 0.25)
            elif self._state == "speaking":
                w = math.sin(self._phase * 3.5 + i * 0.22) * 0.5 + 0.5
                t = w * 0.6 + random.uniform(0, 0.15)
            elif self._state == "thinking":
                w = math.sin(self._phase * 1.2 + i * 0.5) * 0.5 + 0.5
                t = w * 0.3
            else:
                t = random.uniform(0.01, 0.05)
            self._bars[i] += (t - self._bars[i]) * 0.22

        for d in self._dots:
            spd = 1.2 if self._state in ("listening","speaking") else 0.4 if self._state == "thinking" else 0.12
            d["angle"] = (d["angle"] + spd + math.sin(self._phase + d["phase"]) * 0.3) % 360

        self.update()

    def paintEvent(self, event):
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        col = self._color()

        # ── Background glow ──
        if self._state != "idle":
            g = QRadialGradient(cx, cy, 230)
            gc = QColor(col); gc.setAlpha(20 if self._state == "thinking" else 35)
            g.setColorAt(0, gc); g.setColorAt(1, QColor(0,0,0,0))
            p.setBrush(QBrush(g)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(cx-240, cy-240, 480, 480))

        # ── Outer square bracket corners ──
        bc = QColor(col); bc.setAlpha(60)
        p.setPen(QPen(bc, 1)); p.setBrush(Qt.BrushStyle.NoBrush)
        for ox, oy in [(-260,-260),(260,-260),(-260,260),(260,260)]:
            bx, by = cx+ox, cy+oy
            sl, dx, dy = 22, (-1 if ox>0 else 1), (-1 if oy>0 else 1)
            p.drawLine(int(bx), int(by), int(bx+sl*dx), int(by))
            p.drawLine(int(bx), int(by), int(bx), int(by+sl*dy))

        # ── Crosshairs ──
        cc = QColor(col); cc.setAlpha(20)
        p.setPen(QPen(cc, 1))
        p.drawLine(int(cx-270), int(cy), int(cx+270), int(cy))
        p.drawLine(int(cx), int(cy-270), int(cx), int(cy+270))

        # ── Tick marks on outermost ring ──
        for i in range(72):
            ang = math.radians(i * 5)
            r1, r2 = 245, 250 if i % 3 == 0 else 247
            x1 = cx + math.cos(ang) * r1; y1 = cy + math.sin(ang) * r1
            x2 = cx + math.cos(ang) * r2; y2 = cy + math.sin(ang) * r2
            tc = QColor(col); tc.setAlpha(40 if i % 3 == 0 else 20)
            p.setPen(QPen(tc, 1))
            p.drawLine(int(x1), int(y1), int(x2), int(y2))

        # ── Rotating dashed rings ──
        for i, ring in enumerate(self._rings):
            rc = QColor(col)
            rc.setAlpha(ring["alpha"] if self._state != "idle" else ring["alpha"] // 3)
            pen = QPen(rc, ring["w"])
            pen.setStyle(Qt.PenStyle.DashLine)
            pen.setDashPattern([ring["dash"], ring["gap"]])
            pen.setDashOffset(self._ring_angles[i])
            p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
            r = ring["r"]
            p.drawEllipse(QRectF(cx-r, cy-r, r*2, r*2))

        # ── Radial bars ──
        N = len(self._bars); IR = 105; MH = 60
        for i, val in enumerate(self._bars):
            ang = math.radians((360 / N) * i - 90)
            hl  = val * MH
            x1 = cx + math.cos(ang) * IR;  y1 = cy + math.sin(ang) * IR
            x2 = cx + math.cos(ang) * (IR+hl); y2 = cy + math.sin(ang) * (IR+hl)
            bc2 = QColor(col); bc2.setAlpha(int(60 + val * 195))
            p.setPen(QPen(bc2, 1.5))
            p.drawLine(int(x1), int(y1), int(x2), int(y2))

        # ── Inner filled circle ──
        g2 = QRadialGradient(cx, cy, 100)
        bg = QColor("#010810")
        g2.setColorAt(0, bg); g2.setColorAt(0.75, bg)
        rc2 = QColor(col); rc2.setAlpha(40); g2.setColorAt(1, rc2)
        p.setBrush(QBrush(g2))
        rc3 = QColor(col); rc3.setAlpha(100)
        p.setPen(QPen(rc3, 1))
        p.drawEllipse(QRectF(cx-100, cy-100, 200, 200))

        # ── Inner ring detail ──
        for i in range(36):
            ang = math.radians(i * 10 + self._phase * 5)
            r1, r2 = 90, 95
            x1 = cx + math.cos(ang)*r1; y1 = cy + math.sin(ang)*r1
            x2 = cx + math.cos(ang)*r2; y2 = cy + math.sin(ang)*r2
            ic = QColor(col); ic.setAlpha(50 if i % 2 == 0 else 20)
            p.setPen(QPen(ic, 1))
            p.drawLine(int(x1), int(y1), int(x2), int(y2))

        # ── Assistant name ──
        name = "N.O.V.A" if self._assistant == "nova" else "S.O.R.A"
        font = QFont("Courier New", 15, QFont.Weight.Bold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 7)
        p.setFont(font)
        nc = QColor(col); nc.setAlpha(220)
        p.setPen(nc)
        p.drawText(QRectF(cx-90, cy-14, 180, 28), Qt.AlignmentFlag.AlignCenter, name)

        # ── Orbiting dots ──
        for d in self._dots:
            ang = math.radians(d["angle"])
            dx  = cx + math.cos(ang) * d["r"]
            dy  = cy + math.sin(ang) * d["r"]
            pulse = math.sin(self._phase * 2.5 + d["phase"]) * 0.5 + 0.5
            dc = QColor(col); dc.setAlpha(int(50 + pulse * 170))
            dr = d["size"] + pulse * 2
            p.setBrush(QBrush(dc)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(dx, dy), dr, dr)
            # Dot trail
            for t in range(3):
                ta = math.radians(d["angle"] - (t+1) * 4)
                tx = cx + math.cos(ta) * d["r"]
                ty = cy + math.sin(ta) * d["r"]
                tc2 = QColor(col); tc2.setAlpha(int((3-t) * 20 * pulse))
                p.setBrush(QBrush(tc2))
                p.drawEllipse(QPointF(tx, ty), dr * 0.5, dr * 0.5)

        p.end()


# ═══════════════════════════════════════════════════════════
# WAVEFORM BAR
# ═══════════════════════════════════════════════════════════
class WaveformBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(45)
        self._state     = "idle"
        self._assistant = "nova"
        self._phase     = 0.0
        self._bars      = [0.0] * 48
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(35)

    def set_state(self, s): self._state = s
    def set_assistant(self, a): self._assistant = a.lower()

    def _tick(self):
        self._phase += 0.10
        for i in range(len(self._bars)):
            if self._state == "listening":
                t = math.sin(self._phase + i * 0.38) * 0.5 + 0.5
                t = t * 0.85 + random.uniform(0, 0.15)
            elif self._state == "speaking":
                t = math.sin(self._phase * 1.4 + i * 0.32) * 0.5 + 0.5
                t = t * 0.65 + random.uniform(0, 0.1)
            elif self._state == "thinking":
                t = math.sin(self._phase * 0.5 + i * 0.55) * 0.3 + 0.3
            else:
                t = random.uniform(0.01, 0.06)
            self._bars[i] += (t - self._bars[i]) * 0.28
        self.update()

    def paintEvent(self, event):
        w, h = self.width(), self.height()
        mid  = h / 2
        p    = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        col  = _hex(C_NOVA if self._assistant == "nova" else C_SORA)
        n    = len(self._bars)
        bw   = max(2, (w - n) // n)
        gap  = 2
        tw   = n * (bw + gap)
        ox   = (w - tw) // 2
        for i, val in enumerate(self._bars):
            bh = max(1, int(val * (mid - 3)))
            x  = ox + i * (bw + gap)
            col.setAlpha(int(70 + val * 185))
            p.setBrush(QBrush(col)); p.setPen(Qt.PenStyle.NoPen)
            p.drawRect(x, int(mid - bh), bw, bh * 2)
        p.end()


# ═══════════════════════════════════════════════════════════
# SYSTEM MONITOR
# ═══════════════════════════════════════════════════════════
class SystemMonitor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(5)
        self._bars  = {}
        self._vals  = {}
        self._start = time.time()

        stats = [
            ("CPU", "#00c8ff", "%"),
            ("MEM", "#f0a500", "%"),
            ("NET", "#00ff88", "KB/s"),
            ("GPU", "#ff6b35", "%"),
        ]
        for name, color, unit in stats:
            row = QWidget()
            rl  = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(4)
            nl = QLabel(name)
            nl.setStyleSheet(f"color: #2a4a5e; font-size: 8px; letter-spacing: 2px;")
            nl.setFixedWidth(28)
            vl = QLabel(f"0{unit}")
            vl.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: bold;")
            vl.setFixedWidth(52)
            vl.setAlignment(Qt.AlignmentFlag.AlignRight)
            bar = QProgressBar()
            bar.setRange(0, 100); bar.setValue(0)
            bar.setTextVisible(False); bar.setFixedHeight(3)
            bar.setStyleSheet(
                f"QProgressBar{{background:#0d2535;border:none;border-radius:1px;}}"
                f"QProgressBar::chunk{{background:{color};border-radius:1px;}}"
            )
            rl.addWidget(nl); rl.addWidget(bar, 1); rl.addWidget(vl)
            self._bars[name] = bar
            self._vals[name] = (vl, unit)
            self._layout.addWidget(row)

        self._extra = {}
        for key, color in [("TMP","#ff3355"),("UP","#00ff88"),("PROC","#a0cfe0"),("OS","#a0cfe0")]:
            row = QWidget()
            rl  = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(4)
            kl = QLabel(key)
            kl.setStyleSheet("color: #2a4a5e; font-size: 8px; letter-spacing: 2px;")
            kl.setFixedWidth(28)
            vl = QLabel("—")
            vl.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: bold;")
            rl.addWidget(kl); rl.addWidget(vl)
            self._extra[key] = vl
            self._layout.addWidget(row)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update)
        self._timer.start(1500)
        self._update()

    def _update(self):
        try:
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory().percent
            gpu = 0
            try:
                import subprocess
                r = subprocess.run(
                    ["nvidia-smi","--query-gpu=utilization.gpu","--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=1)
                if r.returncode == 0: gpu = int(r.stdout.strip())
            except: pass

            self._bars["CPU"].setValue(int(cpu))
            self._bars["MEM"].setValue(int(mem))
            self._bars["GPU"].setValue(int(gpu))
            self._vals["CPU"][0].setText(f"{int(cpu)}%")
            self._vals["MEM"][0].setText(f"{int(mem)}%")
            self._vals["GPU"][0].setText(f"{int(gpu)}%")

            net2 = psutil.net_io_counters()
            skb  = round(net2.bytes_sent / 1024, 1)
            self._vals["NET"][0].setText(f"{skb}KB/s")
            self._bars["NET"].setValue(min(100, int(skb / 5)))

            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    t = list(temps.values())[0][0].current
                    self._extra["TMP"].setText(f"{t:.0f}°C")
                else:
                    self._extra["TMP"].setText("N/A")
            except: self._extra["TMP"].setText("N/A")

            up = int(time.time() - self._start)
            h, m, s = up//3600, (up%3600)//60, up%60
            self._extra["UP"].setText(f"{h:02d}:{m:02d}:{s:02d}")
            self._extra["PROC"].setText(str(len(list(psutil.process_iter()))))
            import platform
            self._extra["OS"].setText(platform.system().upper()[:3])
        except Exception as e:
            print(f"[SysMonitor] {e}")
