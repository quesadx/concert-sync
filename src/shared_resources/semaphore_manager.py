import threading

class SemaphoreManager:
    def __init__(self):
        self.s_sections = {}
        self._initialize_semaphores()

    def _initialize_semaphores(self):
        for section in Section:
            capacity = (SECTION_CONFIG[section]["rows"] *
                       SECTION_CONFIG[section]["cols"])
            self.s_sections[section] = threading.Semaphore(capacity)

    def acquire(self, section):
        self.s_sections[section].acquire()

    def release(self, section):
        self.s_sections[section].release()