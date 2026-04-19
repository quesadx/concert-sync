from src.utils.enums import Section


SECTION_CONFIG = {
    Section.VIP: {"rows": 5, "cols": 10},
    Section.PREFERENTIAL: {"rows": 10, "cols": 15},
    Section.GENERAL: {"rows": 20, "cols": 20}
}

RESERVATION_TTL = 300

SERVER_PORT = 9999