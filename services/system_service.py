import time
import psutil
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

class SystemMonitorService(QObject):
    stats_updated = pyqtSignal(dict)

    def __init__(self, interval_ms=1000):
        super().__init__()
        self.interval_ms = interval_ms
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._collect_stats)
        self._boot_time = psutil.boot_time()

    def start(self):
        self._collect_stats()
        self.timer.start(self.interval_ms)

    def stop(self):
        self.timer.stop()

    def _collect_stats(self):
        try:
            cpu_percent = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            
            # Battery info
            battery = psutil.sensors_battery()
            battery_percent = battery.percent if battery else 100
            battery_plugged = battery.power_plugged if battery else True
            
            # Uptime
            uptime_seconds = int(time.time() - self._boot_time)
            hours, remainder = divmod(uptime_seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            uptime_str = f"{hours}h {minutes}m"

            stats = {
                "cpu_percent": round(cpu_percent, 1),
                "mem_percent": round(mem.percent, 1),
                "mem_used_gb": round(mem.used / (1024 ** 3), 1),
                "mem_total_gb": round(mem.total / (1024 ** 3), 1),
                "battery_percent": int(battery_percent),
                "battery_plugged": bool(battery_plugged),
                "uptime": uptime_str
            }
            self.stats_updated.emit(stats)
        except Exception as e:
            pass
