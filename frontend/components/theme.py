import html
from typing import Any, Dict, NamedTuple, Tuple
import plotly.graph_objects as go
import plotly.io as pio

# --- Four-Colour Palette & Neutrals ---
COLOR_NAVY = "#1B2A41"
COLOR_TEAL = "#1F9E9E"
COLOR_AMBER = "#F2A93B"
COLOR_CORAL = "#E4572E"

# Neutrals
COLOR_WHITE = "#FFFFFF"
COLOR_BG_LIGHT = "#F5F7FA"
COLOR_MUTED_GREY = "#6B7785"
COLOR_BORDER_GREY = "#E2E8F0"

# Four-colour tints (fills & scales only)
COLOR_TEAL_LIGHT = "#E6F5F5"
COLOR_TEAL_MID = "#80CECE"
COLOR_AMBER_LIGHT = "#FEF6E9"
COLOR_CORAL_LIGHT = "#FCEEEA"


class StatusDisplay(NamedTuple):
    symbol: str
    label: str
    color: str
    bg_color: str
    text_color: str  # High-contrast text on badge background


# Mapping for Reliability & Monitoring States
STATUS_MAP: Dict[str, StatusDisplay] = {
    "NORMAL": StatusDisplay(
        symbol="●",
        label="Normal – no drift or confirmed degradation",
        color=COLOR_TEAL,
        bg_color="#E6F5F5",
        text_color=COLOR_NAVY,
    ),
    "DRIFT_DETECTED": StatusDisplay(
        symbol="▲",
        label="Drift detected – performance impact not confirmed",
        color=COLOR_AMBER,
        bg_color="#FEF6E9",
        text_color=COLOR_NAVY,
    ),
    "DRIFT_DETECTED_WITHIN_TOLERANCE": StatusDisplay(
        symbol="▲",
        label="Drift detected – performance within tolerance",
        color=COLOR_AMBER,
        bg_color="#FEF6E9",
        text_color=COLOR_NAVY,
    ),
    "PERFORMANCE_DEGRADATION": StatusDisplay(
        symbol="✖",
        label="Performance degradation confirmed",
        color=COLOR_CORAL,
        bg_color="#FCEEEA",
        text_color=COLOR_NAVY,
    ),
    "DRIFT_AND_PERFORMANCE_DEGRADATION": StatusDisplay(
        symbol="✖",
        label="Drift and performance degradation",
        color=COLOR_CORAL,
        bg_color="#FCEEEA",
        text_color=COLOR_NAVY,
    ),
    "INSUFFICIENT_DATA": StatusDisplay(
        symbol="◌",
        label="Insufficient data – no conclusion",
        color=COLOR_AMBER,
        bg_color="#FEF6E9",
        text_color=COLOR_NAVY,
    ),
    "MONITORING_ERROR": StatusDisplay(
        symbol="✖",
        label="Monitoring error – no conclusion",
        color=COLOR_CORAL,
        bg_color="#FCEEEA",
        text_color=COLOR_NAVY,
    ),
}

# Alert Severity Map
ALERT_SEVERITY_MAP: Dict[str, StatusDisplay] = {
    "info": StatusDisplay(
        symbol="ℹ",
        label="Info",
        color=COLOR_TEAL,
        bg_color="#E6F5F5",
        text_color=COLOR_NAVY,
    ),
    "warning": StatusDisplay(
        symbol="▲",
        label="Warning",
        color=COLOR_AMBER,
        bg_color="#FEF6E9",
        text_color=COLOR_NAVY,
    ),
    "critical": StatusDisplay(
        symbol="✖",
        label="Critical",
        color=COLOR_CORAL,
        bg_color="#FCEEEA",
        text_color=COLOR_NAVY,
    ),
}


def get_status_display(status: str, has_labels: bool = False, degraded: bool = False) -> StatusDisplay:
    """Return StatusDisplay for a given status key, gracefully handling unknowns."""
    if not status:
        return StatusDisplay(symbol="◌", label="No status", color=COLOR_MUTED_GREY, bg_color=COLOR_BG_LIGHT, text_color=COLOR_NAVY)
    
    clean_status = str(status).strip()
    if clean_status == "DRIFT_DETECTED":
        if has_labels and not degraded:
            return STATUS_MAP["DRIFT_DETECTED_WITHIN_TOLERANCE"]
        return STATUS_MAP["DRIFT_DETECTED"]

    if clean_status in STATUS_MAP:
        return STATUS_MAP[clean_status]

    # Fallback for unknown statuses - honest display
    return StatusDisplay(
        symbol="■",
        label=f"Status: {clean_status}",
        color=COLOR_MUTED_GREY,
        bg_color=COLOR_BG_LIGHT,
        text_color=COLOR_NAVY,
    )


def get_severity_display(severity: str) -> StatusDisplay:
    """Return StatusDisplay for alert severity."""
    clean = str(severity or "").lower().strip()
    if clean in ALERT_SEVERITY_MAP:
        return ALERT_SEVERITY_MAP[clean]
    return StatusDisplay(symbol="•", label=clean or "Unknown", color=COLOR_MUTED_GREY, bg_color=COLOR_BG_LIGHT, text_color=COLOR_NAVY)


def escape_markdown_text(text: Any) -> str:
    """Escape markdown special characters to prevent rendering injection."""
    if text is None:
        return ""
    s = str(text)
    # Characters special in Markdown: _ * ` [ ] ( ) # + - . ! { } |
    chars_to_escape = ["\\", "`", "*", "_", "{", "}", "[", "]", "(", ")", "#", "+", "-", "!", "|"]
    for char in chars_to_escape:
        s = s.replace(char, f"\\{char}")
    return s


# --- Plotly Four-Colour Template ---
omnivex_template = go.layout.Template()
omnivex_template.layout = go.Layout(
    paper_bgcolor=COLOR_WHITE,
    plot_bgcolor=COLOR_BG_LIGHT,
    font=dict(family="sans serif", color=COLOR_NAVY, size=12),
    title=dict(font=dict(color=COLOR_NAVY, size=15, family="sans serif")),
    xaxis=dict(
        gridcolor=COLOR_BORDER_GREY,
        zerolinecolor=COLOR_BORDER_GREY,
        linecolor=COLOR_BORDER_GREY,
        tickfont=dict(color=COLOR_NAVY),
        title_font=dict(color=COLOR_NAVY),
    ),
    yaxis=dict(
        gridcolor=COLOR_BORDER_GREY,
        zerolinecolor=COLOR_BORDER_GREY,
        linecolor=COLOR_BORDER_GREY,
        tickfont=dict(color=COLOR_NAVY),
        title_font=dict(color=COLOR_NAVY),
    ),
    colorway=[COLOR_TEAL, COLOR_NAVY, COLOR_AMBER, COLOR_CORAL],
)
pio.templates["omnivex_four_colour"] = omnivex_template
pio.templates.default = "omnivex_four_colour"
