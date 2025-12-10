"""Progress indicator component for Hienfeld VB Converter."""
import reflex as rx
from ..state import HienfeldState
from ..styles import (
    card_style,
    progress_container_style,
    progress_bar_style,
    alert_error_style,
    alert_success_style,
    DEEP_SEA,
    ULTRA_MARINE,
    TEXT_MUTED,
)


def progress_section() -> rx.Component:
    """Render the progress section during analysis."""
    return rx.cond(
        HienfeldState.is_analyzing,
        rx.box(
            rx.vstack(
                rx.heading("Analyse Voortgang", size="4", style={"color": DEEP_SEA, "font_weight": "600"}),
                
                # Progress bar
                rx.box(
                    rx.box(
                        style={
                            **progress_bar_style,
                            "width": f"{HienfeldState.analysis_progress}%",
                        },
                    ),
                    style=progress_container_style,
                ),
                
                # Progress percentage and status
                rx.hstack(
                    rx.text(
                        f"{HienfeldState.analysis_progress}%",
                        style={"color": ULTRA_MARINE, "font_weight": "600"},
                    ),
                    rx.text(
                        HienfeldState.analysis_status,
                        style={"color": TEXT_MUTED},
                    ),
                    justify="between",
                    width="100%",
                ),
                
                # Spinner
                rx.center(
                    rx.spinner(size="3", color=ULTRA_MARINE),
                    padding="1rem",
                ),
                
                align_items="stretch",
                width="100%",
                spacing="3",
            ),
            style=card_style,
        ),
    )


def error_section() -> rx.Component:
    """Render error message if analysis failed."""
    return rx.cond(
        HienfeldState.analysis_error != "",
        rx.box(
            rx.hstack(
                rx.icon("circle-alert", size=20, color="#dc3545"),
                rx.text(HienfeldState.analysis_error),
                spacing="2",
            ),
            style=alert_error_style,
        ),
    )


def completion_banner() -> rx.Component:
    """Render completion banner when analysis is done."""
    return rx.cond(
        HienfeldState.results_ready,
        rx.box(
            rx.hstack(
                rx.icon("circle-check", size=20, color="#28a745"),
                rx.text("✅ Analyse succesvol afgerond!", weight="medium"),
                spacing="2",
            ),
            style=alert_success_style,
        ),
    )

