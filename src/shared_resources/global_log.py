import threading
import datetime
from pathlib import Path

class GlobalLog:
    def __init__(self, filepath="logs/system.log"):
        self.filepath = Path(filepath)
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self.mutex_log = threading.Lock()

    def append(self, event_type, message):
        with self.mutex_log:
            timestamp = datetime.datetime.now().isoformat()
            tid = threading.get_ident()
            log_entry = f"[{timestamp}] [{event_type}] [TID:{tid}] {message}\n"
            with self.filepath.open("a", encoding="utf-8") as f:
                f.write(log_entry)