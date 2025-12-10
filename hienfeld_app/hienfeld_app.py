"""
Hienfeld VB Converter - Reflex Application

Main application entry point. Assembles all components into the complete UI.

Architecture:
    - State (HienfeldState): Manages application state and background tasks
    - Components: Modular UI components (header, sidebar, uploads, etc.)
    - Styles: Hienfeld Design System (brand colors, typography)

Usage:
    reflex run
"""
import reflex as rx

from .state import HienfeldState
from .styles import (
    base_style,
    content_area_style,
    column_style,
    FONT_FAMILY,
    DEEP_SEA,
    ULTRA_MARINE,
    LIGHT_BLUE,
    WHITE,
    TEXT_MUTED,
    card_style,
    progress_container_style,
    progress_bar_style,
    button_style,
)
from .components import (
    header,
    sidebar,
    file_upload_section,
    conditions_upload_section,
    clause_library_upload_section,
    metrics_section,
    results_table,
)
from .components.file_upload import extra_instruction_section, start_button
from .components.progress import error_section, completion_banner
from .components.metrics import advice_distribution_chart


def upload_sections_row() -> rx.Component:
    """Render the three upload sections horizontally with equal sizing."""
    return rx.box(
        file_upload_section(),
        conditions_upload_section(),
        clause_library_upload_section(),
        style={
            "display": "grid",
            "grid_template_columns": "repeat(3, 1fr)",
            "gap": "1rem",
            "width": "100%",
            "align_items": "stretch",
        },
    )


def input_view() -> rx.Component:
    """Render the input view with file uploads and start button."""
    return rx.vstack(
        upload_sections_row(),
        extra_instruction_section(),
        start_button(),
        style={**column_style, "gap": "0.75rem", "max_width": "900px", "margin": "0 auto"},
        width="100%",
    )


def loading_overlay() -> rx.Component:
    """Full-screen loading overlay with blur background."""
    return rx.cond(
        HienfeldState.is_analyzing,
        rx.box(
            # Backdrop with blur
            rx.box(
                style={
                    "position": "fixed",
                    "top": "0",
                    "left": "0",
                    "right": "0",
                    "bottom": "0",
                    "background_color": "rgba(255, 255, 255, 0.85)",
                    "backdrop_filter": "blur(8px)",
                    "-webkit-backdrop-filter": "blur(8px)",
                    "z_index": "998",
                },
            ),
            # Loading card
            rx.box(
                rx.vstack(
                    # Close button
                    rx.box(
                        rx.icon(
                            "x",
                            size=24,
                            style={"cursor": "pointer", "color": TEXT_MUTED},
                            on_click=HienfeldState.cancel_analysis,
                        ),
                        style={
                            "position": "absolute",
                            "top": "1rem",
                            "right": "1rem",
                        },
                    ),
                    
                    # Title
                    rx.heading(
                        "Analyse Voortgang",
                        size="5",
                        style={"color": DEEP_SEA, "font_weight": "700", "margin_bottom": "1.5rem"},
                    ),
                    
                    # Progress bar
                    rx.box(
                        rx.box(
                            style={
                                **progress_bar_style,
                                "width": f"{HienfeldState.analysis_progress}%",
                            },
                        ),
                        style={
                            **progress_container_style,
                            "height": "10px",
                            "border_radius": "5px",
                            "margin_bottom": "1rem",
                        },
                    ),
                    
                    # Progress percentage and status
                    rx.hstack(
                        rx.text(
                            f"{HienfeldState.analysis_progress}%",
                            style={"color": ULTRA_MARINE, "font_weight": "700", "font_size": "1.5rem"},
                        ),
                        rx.text(
                            HienfeldState.analysis_status,
                            style={"color": TEXT_MUTED, "font_size": "1rem"},
                        ),
                        justify="between",
                        align="center",
                        width="100%",
                        style={"margin_bottom": "1.5rem"},
                    ),
                    
                    # Spinner
                    rx.center(
                        rx.spinner(size="3", color=ULTRA_MARINE),
                        padding="1rem",
                    ),
                    
                    # Cancel hint
                    rx.text(
                        "Klik op X om te annuleren",
                        style={"color": TEXT_MUTED, "font_size": "0.85rem", "margin_top": "1rem"},
                    ),
                    
                    align_items="stretch",
                    width="100%",
                    spacing="2",
                ),
                style={
                    "position": "fixed",
                    "top": "50%",
                    "left": "50%",
                    "transform": "translate(-50%, -50%)",
                    "background_color": WHITE,
                    "padding": "2.5rem",
                    "border_radius": "16px",
                    "box_shadow": "0 25px 50px -12px rgba(0, 0, 0, 0.25)",
                    "width": "90%",
                    "max_width": "500px",
                    "z_index": "999",
                },
            ),
        ),
    )


def results_view() -> rx.Component:
    """Render the results view after analysis is complete."""
    return rx.vstack(
        # New analysis button at top
        rx.hstack(
            rx.button(
                rx.hstack(
                    rx.icon("arrow-left", size=18),
                    rx.text("Nieuwe Analyse"),
                    spacing="2",
                ),
                on_click=HienfeldState.start_new_analysis,
                style={
                    **button_style,
                    "background_color": DEEP_SEA,
                },
            ),
            justify="start",
            width="100%",
            style={"margin_bottom": "1rem"},
        ),
        
        # Completion banner
        completion_banner(),
        
        # Error section
        error_section(),
        
        # Metrics section
        metrics_section(),
        
        # Advice distribution chart
        advice_distribution_chart(),
        
        # Results table
        results_table(),
        
        style={**column_style, "max_width": "900px", "margin": "0 auto"},
        width="100%",
    )


def sidebar_drawer() -> rx.Component:
    """Sidebar as a slide-out drawer."""
    return rx.drawer.root(
        rx.drawer.trigger(rx.box()),  # Empty trigger, we control via state
        rx.drawer.overlay(
            style={"background_color": "rgba(0,0,0,0.3)"},
        ),
        rx.drawer.content(
            rx.vstack(
                rx.hstack(
                    rx.text(
                        "Instellingen",
                        weight="bold",
                        style={"color": DEEP_SEA, "font_size": "1.1rem"},
                    ),
                    rx.drawer.close(
                        rx.icon("x", size=20, style={"cursor": "pointer"}),
                    ),
                    justify="between",
                    align="center",
                    width="100%",
                ),
                sidebar(),
                spacing="4",
                width="100%",
                padding="16px",
            ),
            style={
                "background_color": "#F5F5F5",
                "width": "280px",
                "max_width": "90vw",
            },
        ),
        direction="left",
        open=HienfeldState.sidebar_open,
        on_open_change=lambda open: HienfeldState.set_sidebar_open(open),
    )


def index() -> rx.Component:
    """Main page layout with conditional views."""
    return rx.box(
        # Loading overlay (shown during analysis)
        loading_overlay(),
        
        # Sidebar drawer (hidden by default)
        sidebar_drawer(),
        
        # Main content area
        rx.box(
            rx.vstack(
                # Header (always visible)
                header(),
                
                # Conditional content based on state
                rx.cond(
                    HienfeldState.results_ready,
                    # Results view (after analysis)
                    results_view(),
                    # Input view (before analysis / new analysis)
                    rx.vstack(
                        input_view(),
                        # Welcome section
                        rx.box(
                            rx.vstack(
                                rx.text(
                                    "Analyseer en standaardiseer grote hoeveelheden vrije teksten uit polisbestanden. "
                                    "De tool identificeert duplicaten, vergelijkt met voorwaarden en geeft actiegericht advies.",
                                    style={"color": TEXT_MUTED, "text_align": "center", "max_width": "800px"},
                                ),
                                align="center",
                                width="100%",
                            ),
                            style={
                                "padding": "2rem",
                                "background_color": "#f8f9fa",
                                "border_radius": "12px",
                                "margin_top": "2rem",
                                "width": "100%",
                            },
                        ),
                        width="100%",
                        spacing="3",
                    ),
                ),
                
                width="100%",
                spacing="4",
            ),
            style=content_area_style,
        ),
        
        style=base_style,
    )


# Create the Reflex app
app = rx.App(
    style={
        "font_family": FONT_FAMILY,
    },
    stylesheets=[
        "https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700&display=swap",
    ],
)

# Add the main page
app.add_page(index, title="Hienfeld VB Converter", route="/")
