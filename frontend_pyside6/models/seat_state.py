"""Visual state constants and color mapping for PySide6 seat map rendering.

Defines the five display states used in the seat map grid and the five event log
categories, each with their corresponding QColor or hex color value.

Color palette: Modern cinema theme — warm accents with vivid seat state distinction.
"""

from PySide6.QtGui import QColor

# ── Display state identifiers ─────────────────────────────────────────────────
# Subset is server-side (AVAILABLE, RESERVED, SOLD); others are client-side
# overlays (OWN_RESERVED for "my" reservations, PENDING for pre-reserve selection).
VISUAL_STATES = ("AVAILABLE", "OWN_RESERVED", "RESERVED", "SOLD", "PENDING")

# ── Seat Map Cell Colors ──────────────────────────────────────────────────────
# Modern cinema palette with vivid, unmistakable distinction for each state.
# OWN_RESERVED gets a bright cyan/blue with bold border highlight for instant recognition.
SEAT_COLORS = {
    "AVAILABLE": QColor("#66bb6a"),    # Soft green — available for selection
    "OWN_RESERVED": QColor("#29b6f6"),  # Bright cyan/blue — YOUR reservation
    "RESERVED": QColor("#ffa726"),    # Warm orange — reserved by another user
    "SOLD": QColor("#ef5350"),        # Crimson red — confirmed / permanently sold
    "PENDING": QColor("#ab47bc"),     # Purple — locally selected, not yet reserved
}

# ── Seat Map Cell Border Styles ───────────────────────────────────────────────
# CSS-style border declarations for visual distinction (applied in seat_map_widget).
SEAT_BORDERS = {
    "AVAILABLE": "1px solid #4a4a6a",
    "OWN_RESERVED": "2px solid #f5a623",  # Bold gold border for YOUR seats
    "RESERVED": "1px solid #4a4a6a",
    "SOLD": "1px solid #4a4a6a",
    "PENDING": "2px dashed #d4a84b",      # Dashed amber border for pending
}

# ── Event Log Category Colors ─────────────────────────────────────────────────
# Warm cinema-themed colors for timestamped log entries.
CATEGORY_COLORS = {
    "LOCAL": "#66bb6a",    # Green — actions initiated by this user
    "REMOTE": "#ffa726",   # Orange — actions by other users
    "ERROR": "#ef5350",    # Red — protocol errors, connection failures
    "SERVER": "#a0a0a0",   # Grey — server lifecycle events
    "EXPIRE": "#8d6e63",   # Brown — TTL expiration events
}
