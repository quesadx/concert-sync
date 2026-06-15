import threading
from src.utils.config import SECTION_CONFIG
from src.utils.enums import Section

class SemaphoreManager:
    def __init__(self):
        self.s_sections = {}
        self._initialize_semaphores()

    def _initialize_semaphores(self):
        for section in Section:
            capacity = (SECTION_CONFIG[section]["rows"] *
                       SECTION_CONFIG[section]["cols"])
            self.s_sections[section] = threading.Semaphore(capacity)

    def acquire(self, section, blocking=True):
        return self.s_sections[section].acquire(blocking=blocking)

    def release(self, section):
        self.s_sections[section].release()

    def release_multiple(self, section, count):
        for _ in range(count):
            try:
                self.s_sections[section].release()
            except ValueError:
                pass