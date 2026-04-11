import threading
import datetime

class GlobalLog:
    def __init__(self, filepath="logs/system.log"):
        self.filepath = filepath
        self.mutex_log = threading.Lock()

    def append(self, event_type, message):
        with self.mutex_log:
            timestamp = datetime.datetime.now().isoformat()
            log_entry = f"[{timestamp}] [{event_type}] {message}\n"
            with open(self.filepath, 'a') as f:
                f.write(log_entry)