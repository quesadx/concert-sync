from src.synchronization.lock_hierarchy import acquire_section_locks, sort_sections
from src.synchronization.mutex_manager import MutexManager
from src.utils.enums import Section


class RecordingLock:
    def __init__(self, name, events):
        self.name = name
        self.events = events

    def acquire(self):
        self.events.append(f"acquire:{self.name}")

    def release(self):
        self.events.append(f"release:{self.name}")


class DummySeatMatrix:
    def __init__(self, locks):
        self.mutex_sections = locks


class DummyReservationTable:
    def __init__(self, table_lock):
        self.mutex_table = table_lock


def _build_section_locks(events):
    return {
        Section.VIP: RecordingLock("VIP", events),
        Section.PREFERENTIAL: RecordingLock("PREFERENTIAL", events),
        Section.GENERAL: RecordingLock("GENERAL", events),
    }


def test_sort_sections_uses_global_hierarchy_order():
    ordered = sort_sections([Section.GENERAL, Section.VIP, Section.PREFERENTIAL])
    assert ordered == [Section.VIP, Section.PREFERENTIAL, Section.GENERAL]


def test_acquire_section_locks_orders_and_releases_in_reverse():
    events = []
    section_locks = _build_section_locks(events)

    with acquire_section_locks(section_locks, [Section.GENERAL, Section.VIP]):
        events.append("inside")

    assert events == [
        "acquire:VIP",
        "acquire:GENERAL",
        "inside",
        "release:GENERAL",
        "release:VIP",
    ]


def test_acquire_section_locks_deduplicates_sections():
    events = []
    section_locks = _build_section_locks(events)

    with acquire_section_locks(section_locks, [Section.VIP, Section.VIP, Section.GENERAL]):
        pass

    assert events == [
        "acquire:VIP",
        "acquire:GENERAL",
        "release:GENERAL",
        "release:VIP",
    ]


def test_mutex_manager_table_and_sections_uses_consistent_order():
    events = []

    section_locks = _build_section_locks(events)
    table_lock = RecordingLock("TABLE", events)

    manager = MutexManager(
        seat_matrix=DummySeatMatrix(section_locks),
        reservation_table=DummyReservationTable(table_lock),
    )

    with manager.table_and_sections([Section.GENERAL, Section.VIP]):
        events.append("inside")

    assert events == [
        "acquire:TABLE",
        "acquire:VIP",
        "acquire:GENERAL",
        "inside",
        "release:GENERAL",
        "release:VIP",
        "release:TABLE",
    ]
