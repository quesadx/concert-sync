"""Visual state constants and color mapping for PySide6 seat map rendering.

Defines the five display states used in the seat map grid and the five event log
categories, each with their corresponding QColor or hex color value.
"""

from PySide6.QtGui import QColor

# ── Display state identifiers ─────────────────────────────────────────────────
# Subset is server-side (AVAILABLE, RESERVED, SOLD); others are client-side
# overlays (OWN_RESERVED for "my" reservations, PENDING for pre-reserve selection).
VISUAL_STATES = ("AVAILABLE", "OWN_RESERVED", "RESERVED", "SOLD", "PENDING")

# ── Seat Map Cell Colors ──────────────────────────────────────────────────────
# Mirrors TUI _seat_cell() styles at frontend_tui/app.py lines 1001-1013,
# adapted to the richer color palette specified in UI-SPEC §Seat Map State Colors.
SEAT_COLORS = {
    "AVAILABLE": QColor("#4CAF50"),       # Green — available for selection
    "OWN_RESERVED": QColor("#2196F3"),    # Blue — reserved by current user
    "RESERVED": QColor("#FF9800"),        # Orange — reserved by another user
    "SOLD": QColor("#F44336"),            # Red — confirmed / permanently sold
    "PENDING": QColor("#9C27B0"),         # Purple — locally selected, not yet reserved
}

# ── Event Log Category Colors ─────────────────────────────────────────────────
# Colors for timestamped log entries per UI-SPEC §Event Log Category Colors.
CATEGORY_COLORS = {
    "LOCAL": "#4CAF50",     # Green — actions initiated by this user
    "REMOTE": "#FF9800",    # Orange — actions by other users
    "ERROR": "#F44336",     # Red — protocol errors, connection failures
    "SERVER": "#9E9E9E",    # Grey — server lifecycle events
    "EXPIRE": "#795548",    # Brown — TTL expiration events
}
