from contextlib import contextmanager


def sort_sections(sections):
    """Return unique sections sorted by global hierarchy order."""
    return sorted(set(sections), key=lambda section: section.value)


@contextmanager
def acquire_section_locks(mutex_sections, sections):
    """Acquire section locks in hierarchy order and release them in reverse order."""
    ordered_sections = sort_sections(sections)
    acquired_sections = []

    try:
        for section in ordered_sections:
            mutex_sections[section].acquire()
            acquired_sections.append(section)

        yield ordered_sections
    finally:
        for section in reversed(acquired_sections):
            mutex_sections[section].release()
