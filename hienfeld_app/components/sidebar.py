"""Sidebar component with settings for Hienfeld VB Converter."""
import reflex as rx
from ..state import HienfeldState
from ..styles import (
    sidebar_section_style,
    input_style,
    checkbox_style,
    alert_info_style,
    DEEP_SEA,
    ULTRA_MARINE,
    TEXT_MUTED,
)


def settings_section() -> rx.Component:
    """Render the settings section."""
    return rx.vstack(
        rx.text(
            "Pas de gevoeligheid van het algoritme aan.",
            style={"color": TEXT_MUTED, "font_size": "0.85rem"},
        ),
        
        # Strictness slider
        rx.vstack(
            rx.hstack(
                rx.text("Cluster Nauwkeurigheid", weight="medium"),
                rx.text(
                    HienfeldState.strictness_display,
                    style={"color": ULTRA_MARINE, "font_weight": "600"},
                ),
                justify="between",
                width="100%",
            ),
            rx.slider(
                default_value=[90],
                min=80,
                max=100,
                step=1,
                on_value_commit=lambda v: HienfeldState.set_strictness(v[0]),
                style={"width": "100%"},
            ),
            rx.text(
                "Hoe streng moet de matching zijn? Hoger = minder, maar zuiverdere clusters.",
                style={"color": TEXT_MUTED, "font_size": "0.8rem"},
            ),
            width="100%",
            spacing="1",
        ),
        
        # Min frequency
        rx.vstack(
            rx.text("Min. Frequentie voor Standaardisatie", weight="medium"),
            rx.input(
                default_value="20",
                type="number",
                min="1",
                on_blur=lambda v: HienfeldState.set_min_frequency(v),
                style=input_style,
            ),
            rx.text(
                "Vanaf hoe vaak moet een tekst als 'standaard' worden gezien?",
                style={"color": TEXT_MUTED, "font_size": "0.8rem"},
            ),
            width="100%",
            spacing="1",
        ),
        
        style=sidebar_section_style,
        align_items="start",
        width="100%",
        spacing="4",
    )




def advanced_section() -> rx.Component:
    """Render advanced settings section with clustering options."""
    return rx.vstack(
        rx.divider(),
        rx.accordion.root(
            rx.accordion.item(
                header=rx.text("Geavanceerde Instellingen", weight="medium"),
                content=rx.vstack(
                    # Clustering section
                    rx.text("Clustering", weight="medium", style={"color": DEEP_SEA}),
                    rx.hstack(
                        rx.checkbox(
                            "Gebruik Window Size limiet",
                            default_checked=True,
                            on_change=HienfeldState.toggle_window_limit,
                            style=checkbox_style,
                        ),
                        width="100%",
                    ),
                    rx.cond(
                        HienfeldState.use_window_limit,
                        rx.vstack(
                            rx.text("Window Size", weight="medium", style={"font_size": "0.85rem"}),
                            rx.input(
                                default_value="100",
                                type="number",
                                min="10",
                                max="1000",
                                on_blur=lambda v: HienfeldState.set_window_size(v),
                                style=input_style,
                            ),
                            rx.text(
                                "Tegen hoeveel clusters wordt vergeleken. Hoger = nauwkeuriger maar trager.",
                                style={"color": TEXT_MUTED, "font_size": "0.75rem"},
                            ),
                            width="100%",
                            spacing="1",
                        ),
                        rx.box(
                            rx.text(
                                "Geen limiet: vergelijkt tegen ALLE clusters (kan trager zijn)",
                                style={"font_size": "0.8rem"},
                            ),
                            style=alert_info_style,
                        ),
                    ),
                    
                    rx.divider(style={"margin": "0.75rem 0"}),
                    
                    # AI section
                    rx.text("AI Analyse", weight="medium", style={"color": DEEP_SEA}),
                    rx.checkbox(
                        "AI Analyse (experimenteel)",
                        default_checked=False,
                        on_change=HienfeldState.toggle_ai,
                        style=checkbox_style,
                    ),
                    rx.text(
                        "Gebruik AI voor geavanceerde analyse (vereist configuratie)",
                        style={"color": TEXT_MUTED, "font_size": "0.75rem"},
                    ),
                    align_items="start",
                    spacing="2",
                    width="100%",
                ),
            ),
            type="single",
            collapsible=True,
            width="100%",
        ),
        width="100%",
        spacing="2",
    )


def support_section() -> rx.Component:
    """Render support section."""
    return rx.vstack(
        rx.divider(),
        rx.text("Support", weight="bold", style={"color": DEEP_SEA}),
        rx.text(
            "Neem bij vragen contact op met de systeembeheerder.",
            style={"color": TEXT_MUTED, "font_size": "0.85rem"},
        ),
        width="100%",
        spacing="2",
        margin_top="auto",
    )


def sidebar() -> rx.Component:
    """Render the complete sidebar content (for use in drawer)."""
    return rx.vstack(
        settings_section(),
        advanced_section(),
        support_section(),
        width="100%",
        spacing="2",
        padding="0.5rem",
    )

