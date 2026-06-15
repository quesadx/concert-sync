"""Visual state constants and color mapping for PySide6 seat map rendering.

Defines the five display states used in the seat map grid and the five event log
categories, each with their corresponding QColor or hex color value.

Color palette: GNOME Adwaita-inspired design — blue accent, dark_3/dark_4 backgrounds.
"""

from PySide6.QtGui import QColor

import frontend_pyside6.resources.gnome_palette as palette

# ── Display state identifiers ─────────────────────────────────────────────────
# Subset is server-side (AVAILABLE, RESERVED, SOLD); others are client-side
# overlays (OWN_RESERVED for "my" reservations, PENDING for pre-reserve selection).
VISUAL_STATES = ("AVAILABLE", "OWN_RESERVED", "RESERVED", "SOLD", "PENDING")

# ── Seat Map Cell Colors ──────────────────────────────────────────────────────
# GNOME Adwaita palette with unmistakable distinction for each state.
# Colors sourced from frontend_pyside6.resources.gnome_palette.
SEAT_COLORS = {
    "AVAILABLE": QColor(palette.SEAT_AVAILABLE),    # Green — available for selection
    "OWN_RESERVED": QColor(palette.SEAT_OWN),        # Blue — YOUR reservation
    "RESERVED": QColor(palette.SEAT_RESERVED),      # Orange — reserved by another user
    "SOLD": QColor(palette.SEAT_SOLD),              # Red — confirmed / permanently sold
    "PENDING": QColor(palette.SEAT_PENDING),        # Purple — locally selected, not yet reserved
}

# ── Seat Map Cell Border Styles ───────────────────────────────────────────────
# CSS-style border declarations for visual distinction (applied in seat_map_widget).
SEAT_BORDERS = {
    "AVAILABLE": palette.BORDER_AVAILABLE,
    "OWN_RESERVED": palette.BORDER_OWN,         # Bold blue border for YOUR seats
    "RESERVED": palette.BORDER_RESERVED,
    "SOLD": palette.BORDER_SOLD,
    "PENDING": palette.BORDER_PENDING,          # Dashed blue border for pending
}

# ── Event Log Category Colors ─────────────────────────────────────────────────
# GNOME Adwaita colors for timestamped log entries.
CATEGORY_COLORS = {
    "LOCAL": palette.CAT_LOCAL,     # Green — actions initiated by this user
    "REMOTE": palette.CAT_REMOTE,   # Orange — actions by other users
    "ERROR": palette.CAT_ERROR,     # Red — protocol errors, connection failures
    "SERVER": palette.CAT_SERVER,   # Grey — server lifecycle events
    "EXPIRE": palette.CAT_EXPIRE,   # Brown — TTL expiration events
    "NOTIFICATION": palette.CAT_NOTIFICATION,  # Purple — push notifications
}
