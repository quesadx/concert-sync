"""Light mode color palette — clean, modern, high-contrast design.

Transitioned from GNOME Adwaita dark to an Apple-inspired light palette.
All UI colors are defined here as the single source of truth.
"""

# ── Backgrounds ────────────────────────────────────────────────────────
BG_PRIMARY      = "#f5f5f7"   # Very light gray — main window background
BG_SECONDARY    = "#ffffff"   # White — panel/card background
SURFACE         = "#ffffff"   # White — widget surface
SURFACE_HOVER   = "#f0f0f2"   # Light — hover state

# ── Accent ─────────────────────────────────────────────────────────────
ACCENT          = "#2563eb"   # Blue-600 — primary accent
ACCENT_WARM     = "#3b82f6"   # Blue-500 — hover/soft accent
ACCENT_SOFT     = "rgba(37, 99, 235, 0.08)"  # Blue-600 at 8% opacity

# ── Semantic ───────────────────────────────────────────────────────────
ERROR           = "#dc2626"   # Red-600
SUCCESS         = "#16a34a"   # Green-600
INFO            = "#3b82f6"   # Blue-500
WARNING         = "#d97706"   # Amber-600

# ── Text ───────────────────────────────────────────────────────────────
TEXT_PRIMARY    = "#1d1d1f"   # Near-black
TEXT_SECONDARY  = "#6e6e73"   # Medium gray
TEXT_MUTED      = "#86868b"   # Light gray

# ── Borders ────────────────────────────────────────────────────────────
BORDER          = "#d2d2d7"   # Light border
BORDER_FOCUS    = "#2563eb"   # Blue-600 (accent for focused elements)

# ── Seat Map Cell Colors ───────────────────────────────────────────────
SEAT_AVAILABLE  = "#16a34a"   # Green-600
SEAT_OWN        = "#2563eb"   # Blue-600 — YOUR reservation
SEAT_RESERVED   = "#ea580c"   # Orange-600 — reserved by another user
SEAT_SOLD       = "#dc2626"   # Red-600 — confirmed/sold by another user
SEAT_OWN_SOLD   = "#4338ca"   # Indigo-600 — YOUR purchased seat
SEAT_PENDING    = "#9333ea"   # Purple-600 — local pre-reserve

# ── Seat Map Cell Borders ──────────────────────────────────────────────
BORDER_AVAILABLE  = "1px solid #16a34a"
BORDER_OWN        = "2px solid #2563eb"
BORDER_RESERVED   = "1px solid #ea580c"
BORDER_SOLD       = "1px solid #dc2626"
BORDER_OWN_SOLD   = "1px solid #4338ca"
BORDER_PENDING    = "2px dashed #9333ea"

# ── Event Log Category Colors ──────────────────────────────────────────
CAT_LOCAL         = "#16a34a"   # Green-600 — user's own actions
CAT_REMOTE        = "#ea580c"   # Orange-600 — other users' actions
CAT_ERROR         = "#dc2626"   # Red-600 — protocol errors
CAT_SERVER        = "#6e6e73"   # Gray — server lifecycle
CAT_EXPIRE        = "#b45309"   # Amber-700 — TTL expiration
CAT_NOTIFICATION  = "#9333ea"   # Purple-600 — push notifications
