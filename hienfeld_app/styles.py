"""
Hienfeld Design System - Reflex Styles

Brand Colors:
- Deep Sea: #0A0466 (headers, primary text)
- Ultra Marine: #10069F (buttons, accents, progress)
- Light Blue: #7CC2FE (hover states, highlights)

Typography:
- Font: Graphik, Open Sans, Segoe UI, sans-serif
- Modern rounded corners (border-radius: 12px for cards, 8px for buttons)
"""
import reflex as rx

# =============================================================================
# BRAND COLORS
# =============================================================================
DEEP_SEA = "#0A0466"
ULTRA_MARINE = "#10069F"
LIGHT_BLUE = "#7CC2FE"
HIENFELD_GRAY = "#F5F5F5"
HIENFELD_BORDER = "#E0E0E0"
WHITE = "#FFFFFF"
TEXT_DARK = "#333333"
TEXT_MUTED = "#666666"

# Advice colors
ADVICE_COLORS = {
    "verwijderen": "#dc3545",
    "splitsen": "#ffc107",
    "standaardiseren": "#17a2b8",
    "opschonen": "#6f42c1",
    "aanvullen": "#fd7e14",
    "verlopen": "#6c757d",
    "leeg": "#adb5bd",
    "onleesbaar": "#343a40",
    "behouden": "#28a745",
    "handmatig": "#6c757d",
}

# =============================================================================
# FONT STACK
# =============================================================================
FONT_FAMILY = "Graphik, 'Open Sans', 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif"

# =============================================================================
# BASE STYLES
# =============================================================================
base_style = {
    "font_family": FONT_FAMILY,
    "background_color": WHITE,
    "color": TEXT_DARK,
}

# =============================================================================
# COMPONENT STYLES
# =============================================================================

# Header styles
header_style = {
    "width": "100%",
    "padding": "1rem 2rem",
    "background_color": WHITE,
}

header_title_style = {
    "color": DEEP_SEA,
    "font_weight": "700",
    "font_size": "2rem",
    "margin": "0",
}

header_subtitle_style = {
    "color": TEXT_MUTED,
    "font_size": "1rem",
    "margin_top": "0.25rem",
}

header_line_style = {
    "height": "4px",
    "width": "100%",
    "background": f"linear-gradient(90deg, {DEEP_SEA} 0%, {ULTRA_MARINE} 50%, {LIGHT_BLUE} 100%)",
    "margin_bottom": "1.5rem",
}

help_badge_style = {
    "display": "inline-flex",
    "align_items": "center",
    "justify_content": "center",
    "width": "26px",
    "height": "26px",
    "border_radius": "50%",
    "background_color": ULTRA_MARINE,
    "color": WHITE,
    "font_size": "16px",
    "font_weight": "700",
    "cursor": "pointer",
}

# Button styles
button_style = {
    "background_color": ULTRA_MARINE,
    "color": WHITE,
    "border_radius": "8px",
    "border": "none",
    "padding": "0.5rem 1.25rem",
    "font_family": FONT_FAMILY,
    "font_weight": "600",
    "text_transform": "uppercase",
    "letter_spacing": "0.5px",
    "cursor": "pointer",
    "transition": "all 0.3s ease",
    "_hover": {
        "background_color": LIGHT_BLUE,
        "color": DEEP_SEA,
        "box_shadow": "0 4px 12px rgba(0,0,0,0.15)",
    },
}

button_disabled_style = {
    **button_style,
    "background_color": "#cccccc",
    "cursor": "not-allowed",
    "_hover": {
        "background_color": "#cccccc",
    },
}

# Sidebar styles
sidebar_style = {
    "width": "260px",
    "min_width": "260px",
    "height": "100vh",
    "background_color": HIENFELD_GRAY,
    "padding": "1.25rem",
    "border_right": f"1px solid {HIENFELD_BORDER}",
    "overflow_y": "auto",
}

sidebar_header_style = {
    "color": DEEP_SEA,
    "font_weight": "700",
    "font_size": "1.1rem",
    "margin_bottom": "0.5rem",
}

sidebar_section_style = {
    "margin_bottom": "1.5rem",
}

# Card styles
card_style = {
    "background_color": WHITE,
    "padding": "0.75rem",
    "border_radius": "12px",
    "border": f"1px solid {HIENFELD_BORDER}",
    "box_shadow": "0 2px 8px rgba(0,0,0,0.06)",
    "height": "100%",
}

card_title_style = {
    "color": DEEP_SEA,
    "font_weight": "600",
    "font_size": "0.95rem",
    "margin_bottom": "0.5rem",
}

# File uploader styles
file_upload_zone_style = {
    "border": f"1px dashed {HIENFELD_BORDER}",
    "padding": "0.4rem",
    "background_color": HIENFELD_GRAY,
    "border_radius": "8px",
    "text_align": "center",
    "cursor": "pointer",
    "transition": "all 0.3s ease",
    "_hover": {
        "border_color": LIGHT_BLUE,
        "background_color": "#f0f4f8",
    },
}

# Metric card styles
metric_card_style = {
    "background_color": WHITE,
    "border": f"1px solid {HIENFELD_BORDER}",
    "border_radius": "10px",
    "padding": "0.875rem",
    "text_align": "center",
    "box_shadow": "0 2px 8px rgba(0,0,0,0.06)",
    "min_width": "100px",
}

metric_value_style = {
    "font_size": "1.8rem",
    "font_weight": "700",
    "color": DEEP_SEA,
}

metric_label_style = {
    "font_size": "0.9rem",
    "color": TEXT_MUTED,
    "text_transform": "uppercase",
    "letter_spacing": "0.5px",
}

# Progress bar styles
progress_container_style = {
    "width": "100%",
    "height": "6px",
    "background_color": HIENFELD_BORDER,
    "border_radius": "3px",
    "overflow": "hidden",
}

progress_bar_style = {
    "height": "100%",
    "background_color": ULTRA_MARINE,
    "transition": "width 0.3s ease",
}

# Alert/Info box styles
alert_info_style = {
    "background_color": "#F0F7FC",
    "border_left": f"4px solid {ULTRA_MARINE}",
    "border_radius": "0 8px 8px 0",
    "color": DEEP_SEA,
    "padding": "0.75rem",
    "margin": "0.25rem 0",
    "font_size": "0.85rem",
}

alert_success_style = {
    "background_color": "#d4edda",
    "border_left": "4px solid #28a745",
    "border_radius": "0 8px 8px 0",
    "color": "#155724",
    "padding": "0.75rem",
    "margin": "0.25rem 0",
    "font_size": "0.85rem",
}

alert_warning_style = {
    "background_color": "#fff3cd",
    "border_left": "4px solid #ffc107",
    "border_radius": "0 8px 8px 0",
    "color": "#856404",
    "padding": "0.75rem",
    "margin": "0.25rem 0",
    "font_size": "0.85rem",
}

alert_error_style = {
    "background_color": "#f8d7da",
    "border_left": "4px solid #dc3545",
    "border_radius": "0 8px 8px 0",
    "color": "#721c24",
    "padding": "0.75rem",
    "margin": "0.25rem 0",
    "font_size": "0.85rem",
}

# Table styles
table_style = {
    "width": "100%",
    "border_collapse": "collapse",
}

table_header_style = {
    "background_color": DEEP_SEA,
    "color": WHITE,
    "padding": "0.75rem",
    "text_align": "left",
    "font_weight": "600",
}

table_cell_style = {
    "padding": "0.75rem",
    "border_bottom": f"1px solid {HIENFELD_BORDER}",
}

table_row_hover_style = {
    "_hover": {
        "background_color": "#f8f9fa",
    },
}

# Advice badge styles
def get_advice_badge_style(advice_type: str) -> dict:
    """Get badge style based on advice type."""
    color = ADVICE_COLORS.get(advice_type.lower(), "#6c757d")
    text_color = WHITE if advice_type.lower() not in ["splitsen", "leeg"] else TEXT_DARK
    
    return {
        "background_color": color,
        "color": text_color,
        "padding": "0.2rem 0.5rem",
        "border_radius": "3px",
        "font_size": "0.85rem",
        "font_weight": "600",
        "display": "inline-block",
    }

# Expander styles
expander_style = {
    "border": f"1px solid {HIENFELD_BORDER}",
    "border_radius": "8px",
    "margin_bottom": "0.5rem",
}

expander_header_style = {
    "padding": "0.6rem 0.875rem",
    "background_color": HIENFELD_GRAY,
    "border_radius": "8px",
    "cursor": "pointer",
    "display": "flex",
    "justify_content": "space-between",
    "align_items": "center",
    "_hover": {
        "background_color": "#e8e8e8",
    },
}

expander_content_style = {
    "padding": "0.875rem",
    "border_top": f"1px solid {HIENFELD_BORDER}",
}

# Input styles
input_style = {
    "border": f"1px solid {HIENFELD_BORDER}",
    "border_radius": "8px",
    "padding": "0.5rem",
    "width": "100%",
    "font_family": FONT_FAMILY,
    "_focus": {
        "border_color": ULTRA_MARINE,
        "outline": "none",
        "box_shadow": f"0 0 0 2px {LIGHT_BLUE}40",
    },
}

slider_style = {
    "width": "100%",
    "accent_color": ULTRA_MARINE,
}

checkbox_style = {
    "accent_color": ULTRA_MARINE,
}

# Layout styles
main_container_style = {
    "display": "flex",
    "min_height": "100vh",
    "width": "100%",
}

content_area_style = {
    "flex": "1",
    "padding": "1.5rem 2rem",
    "overflow_y": "auto",
}

two_column_layout_style = {
    "display": "grid",
    "grid_template_columns": "1fr 2fr",
    "gap": "2rem",
    "width": "100%",
}

column_style = {
    "display": "flex",
    "flex_direction": "column",
    "gap": "1rem",
}

# Download button specific style
download_button_style = {
    **button_style,
    "background_color": "#28a745",
    "border_radius": "8px",
    "_hover": {
        "background_color": "#218838",
        "color": WHITE,
        "box_shadow": "0 4px 12px rgba(0,0,0,0.15)",
    },
}

# Welcome section styles
welcome_style = {
    "padding": "1.25rem",
    "background_color": HIENFELD_GRAY,
    "border": f"1px solid {HIENFELD_BORDER}",
    "border_radius": "12px",
}

welcome_title_style = {
    "color": DEEP_SEA,
    "font_weight": "700",
    "font_size": "1.5rem",
    "margin_bottom": "1rem",
}

# Divider style
divider_style = {
    "border": "none",
    "border_top": f"1px solid {HIENFELD_BORDER}",
    "margin": "1.5rem 0",
}

