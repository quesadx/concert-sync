"""GNOME Adwaita color palette — single source of truth for all UI colors.

Based on the official GNOME HIG palette (libadwaita 1.x).
Maps conceptual roles (bg-primary, accent, etc.) to Adwaita named colors.
"""

# ── Backgrounds ────────────────────────────────────────────────────────
BG_PRIMARY      = "#241f31"   # Adwaita dark_4 — main window background
BG_SECONDARY    = "#3d3846"   # Adwaita dark_3 — panel/card background
SURFACE         = "#3d3846"   # Adwaita dark_3 — widget surface
SURFACE_HOVER   = "#4a4556"   # Custom: 10% lighter than dark_3

# ── Accent ─────────────────────────────────────────────────────────────
ACCENT          = "#3584e4"   # Adwaita blue_3 — GNOME default accent
ACCENT_WARM     = "#62a0ea"   # Adwaita blue_2 — hover/soft accent
ACCENT_SOFT     = "rgba(53, 132, 228, 0.15)"  # blue_3 at 15% opacity

# ── Semantic ───────────────────────────────────────────────────────────
ERROR           = "#e01b24"   # Adwaita red_3
SUCCESS         = "#2ec27e"   # Adwaita green_4
INFO            = "#62a0ea"   # Adwaita blue_2
WARNING         = "#f5c211"   # Adwaita yellow_4

# ── Text ───────────────────────────────────────────────────────────────
TEXT_PRIMARY    = "#ffffff"   # White
TEXT_SECONDARY  = "#c0bfbc"   # Adwaita light_4
TEXT_MUTED      = "#77767b"   # Adwaita dark_1

# ── Borders ────────────────────────────────────────────────────────────
BORDER          = "#5e5c64"   # Adwaita dark_2
BORDER_FOCUS    = "#3584e4"   # blue_3 (accent for focused elements)

# ── Seat Map Cell Colors ───────────────────────────────────────────────
SEAT_AVAILABLE  = "#2ec27e"   # Adwaita green_4
SEAT_OWN        = "#3584e4"   # Adwaita blue_3 — YOUR reservation
SEAT_RESERVED   = "#e66100"   # Adwaita orange_4 — reserved by another user
SEAT_SOLD       = "#e01b24"   # Adwaita red_3 — confirmed/sold
SEAT_PENDING    = "#9141ac"   # Adwaita purple_3 — local pre-reserve

# ── Seat Map Cell Borders ──────────────────────────────────────────────
BORDER_AVAILABLE  = "1px solid #5e5c64"
BORDER_OWN        = "2px solid #3584e4"
BORDER_RESERVED   = "1px solid #5e5c64"
BORDER_SOLD       = "1px solid #5e5c64"
BORDER_PENDING    = "2px dashed #62a0ea"

# ── Event Log Category Colors ──────────────────────────────────────────
CAT_LOCAL         = "#2ec27e"   # green_4 — user's own actions
CAT_REMOTE        = "#e66100"   # orange_4 — other users' actions
CAT_ERROR         = "#e01b24"   # red_3 — protocol errors
CAT_SERVER        = "#77767b"   # dark_1 — server lifecycle
CAT_EXPIRE        = "#986a44"   # Adwaita brown_3 — TTL expiration
