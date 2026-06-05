"""Numeric-only login dialog for ConcertSync user identification.

Presents a modal QDialog at startup that accepts only digits (1+ digits).
The entered value becomes the user_id for all subsequent server requests.
Login is mandatory — dismiss or empty input is not allowed.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)


class LoginDialog(QDialog):
    """Modal dialog that collects a numeric user ID before connecting.

    The user must enter at least one digit. The OK button is disabled
    until valid input is present. Reject (Esc / close button) is blocked
    — the user must provide a valid numeric ID.

    Attributes:
        user_id: The validated numeric user ID string entered by the user.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the login dialog with a numeric-only input field.

        Args:
            parent: Optional parent widget for modal behavior.
        """
        super().__init__(parent)
        self.setWindowTitle("ConcertSync — Login")
        self.setMinimumWidth(320)
        self.setModal(True)
        # Prevent dismissal via Esc or close button — login is mandatory
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ── Header ──────────────────────────────────────────────────────────
        header = QLabel("Welcome to ConcertSync")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #9ad4d6;")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        subheader = QLabel("Enter your numeric user ID to begin:")
        subheader.setStyleSheet("font-size: 12px; color: #d8e6f5;")
        subheader.setAlignment(Qt.AlignCenter)
        layout.addWidget(subheader)

        # ── Numeric-only input ──────────────────────────────────────────────
        self._input = QLineEdit()
        self._input.setPlaceholderText("e.g. 1001")
        self._input.setAlignment(Qt.AlignCenter)
        self._input.setMaxLength(20)
        # Accept only positive integers (1+ digits)
        validator = QIntValidator(1, 999999999, self)
        self._input.setValidator(validator)
        self._input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._input)

        # ── Error label (hidden until needed) ───────────────────────────────
        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: #F44336; font-size: 11px;")
        self._error_label.setAlignment(Qt.AlignCenter)
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

        # ── OK button ───────────────────────────────────────────────────────
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(self._try_accept)
        self._ok_button = button_box.button(QDialogButtonBox.Ok)
        if self._ok_button:
            self._ok_button.setEnabled(False)
        layout.addWidget(button_box)

        self._input.setFocus()

    def _on_text_changed(self, text: str) -> None:
        """Enable OK button when input is a valid positive integer.

        Args:
            text: Current text content of the input field.
        """
        text = text.strip()
        is_valid = bool(text and text.isdigit() and int(text) > 0)
        if self._ok_button:
            self._ok_button.setEnabled(is_valid)
        if is_valid:
            self._error_label.setVisible(False)

    def _try_accept(self) -> None:
        """Validate input and accept the dialog if valid.

        Shows an error message if the input is empty or non-numeric,
        blocking dialog dismissal until valid input is provided.
        """
        text = self._input.text().strip()
        if not text:
            self._error_label.setText("Please enter a numeric user ID.")
            self._error_label.setVisible(True)
            self._input.setFocus()
            return
        if not text.isdigit():
            self._error_label.setText("User ID must contain only digits.")
            self._error_label.setVisible(True)
            self._input.setFocus()
            return
        if int(text) <= 0:
            self._error_label.setText("User ID must be a positive number.")
            self._error_label.setVisible(True)
            self._input.setFocus()
            return
        self.accept()

    @property
    def user_id(self) -> str:
        """The validated numeric user ID string.

        Returns:
            The trimmed text content of the input field.
        """
        return self._input.text().strip()
