"""Header component for Hienfeld VB Converter."""
import reflex as rx
from ..state import HienfeldState
from ..styles import (
    header_style,
    header_title_style,
    header_subtitle_style,
    header_line_style,
    help_badge_style,
    DEEP_SEA,
    ULTRA_MARINE,
    WHITE,
)


def help_modal() -> rx.Component:
    """Help modal with usage instructions."""
    return rx.dialog.root(
        rx.dialog.trigger(
            rx.box(
                "?",
                style=help_badge_style,
            ),
        ),
        rx.dialog.content(
            rx.dialog.title(
                "Help - Hoe werkt deze tool?",
                style={"color": DEEP_SEA, "font_weight": "700"},
            ),
            rx.dialog.description(
                rx.vstack(
                    rx.text(
                        "De VB Converter analyseert automatisch grote hoeveelheden vrije teksten uit polisbestanden.",
                        style={"margin_bottom": "1rem"},
                    ),
                    rx.divider(),
                    rx.heading("Wat gebeurt er op de achtergrond?", size="4", style={"color": DEEP_SEA, "margin": "1rem 0 0.5rem 0"}),
                    
                    rx.text("Stap 1: Clustering", weight="bold"),
                    rx.text(
                        "De tool groepeert vergelijkbare teksten samen. Teksten die voor meer dan 90% hetzelfde zijn, worden als één cluster behandeld.",
                        style={"margin_bottom": "0.5rem"},
                    ),
                    
                    rx.text("Stap 2: Analyse", weight="bold"),
                    rx.text(
                        "Elke cluster wordt geanalyseerd via een pipeline: admin-check, clausulebibliotheek, voorwaarden-vergelijking, en keyword-analyse.",
                        style={"margin_bottom": "0.5rem"},
                    ),
                    
                    rx.text("Stap 3: Virtual Splitting", weight="bold"),
                    rx.text(
                        "Lange teksten met meerdere clausules worden automatisch gesplitst en elk deel wordt individueel geanalyseerd.",
                        style={"margin_bottom": "1rem"},
                    ),
                    
                    rx.divider(),
                    rx.heading("Wat moet u doen?", size="4", style={"color": DEEP_SEA, "margin": "1rem 0 0.5rem 0"}),
                    
                    rx.ordered_list(
                        rx.list_item("Upload uw polisbestand (CSV/Excel) met vrije teksten"),
                        rx.list_item("Kies voor analyse met of zonder voorwaarden"),
                        rx.list_item("Start de analyse en download het rapport"),
                    ),
                    
                    rx.divider(),
                    rx.heading("Output", size="4", style={"color": DEEP_SEA, "margin": "1rem 0 0.5rem 0"}),
                    rx.text(
                        "Een Excel-bestand met Cluster-ID, Frequentie, Advies (VERWIJDEREN, BEHOUDEN, STANDAARDISEREN, SPLITSEN), Reden en Artikel-referenties.",
                    ),
                    
                    align_items="start",
                    width="100%",
                    spacing="2",
                ),
            ),
            rx.dialog.close(
                rx.button(
                    "Sluiten",
                    style={
                        "background_color": ULTRA_MARINE,
                        "color": WHITE,
                        "margin_top": "1rem",
                    },
                ),
            ),
            style={"max_width": "600px", "max_height": "80vh", "overflow_y": "auto"},
        ),
    )


def settings_button() -> rx.Component:
    """Settings gear button to toggle sidebar."""
    return rx.box(
        rx.icon(
            "settings",
            size=22,
            color=ULTRA_MARINE,
            style={"cursor": "pointer"},
        ),
        on_click=HienfeldState.toggle_sidebar,
        style={
            "padding": "0.5rem",
            "border_radius": "8px",
            "cursor": "pointer",
            "_hover": {"background_color": "#f0f4f8"},
        },
    )


def header() -> rx.Component:
    """Render the application header with logo and title."""
    return rx.box(
        rx.box(
            # Settings gear (absolute left)
            rx.box(
                settings_button(),
                style={
                    "position": "absolute",
                    "left": "1rem",
                    "top": "50%",
                    "transform": "translateY(-50%)",
                },
            ),
            # Centered content: Logo + Title + Help
            rx.hstack(
                # Logo
                rx.image(
                    src="/hienfeld-logo.png",
                    width="140px",
                    alt="Hienfeld Logo",
                ),
                # Title section
                rx.vstack(
                    rx.hstack(
                        rx.heading(
                            "VB Converter",
                            style=header_title_style,
                        ),
                        help_modal(),
                        align="center",
                        spacing="3",
                    ),
                    rx.text(
                        "Automatisch vrije teksten analyseren en standaardiseren.",
                        style=header_subtitle_style,
                    ),
                    align_items="start",
                    spacing="1",
                ),
                justify="center",
                align="center",
                spacing="4",
            ),
            style={
                "position": "relative",
                "width": "100%",
                "display": "flex",
                "justify_content": "center",
                "align_items": "center",
                "padding": "0.5rem 0",
            },
        ),
        # Gradient line
        rx.box(
            style=header_line_style,
        ),
        style=header_style,
    )

