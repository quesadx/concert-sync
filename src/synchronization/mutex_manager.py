from contextlib import contextmanager

from src.synchronization.lock_hierarcky import acquire_section_locks


class MutexManager:
	"""Centralized lock orchestration for transactional server operations."""

	def __init__(self, seat_matrix, reservation_table):
		self.seat_matrix = seat_matrix
		self.reservation_table = reservation_table

	@contextmanager
	def table(self):
		table_lock = self.reservation_table.mutex_table
		table_lock.acquire()
		try:
			yield
		finally:
			table_lock.release()

	@contextmanager
	def sections(self, sections):
		with acquire_section_locks(self.seat_matrix.mutex_sections, sections) as ordered_sections:
			yield ordered_sections

	@contextmanager
	def table_and_sections(self, sections):
		with self.table():
			with self.sections(sections) as ordered_sections:
				yield ordered_sections
