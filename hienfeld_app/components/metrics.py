"""Metrics display component for Hienfeld VB Converter."""
import reflex as rx
from ..state import HienfeldState
from ..styles import (
    metric_card_style,
    metric_value_style,
    metric_label_style,
    alert_info_style,
    DEEP_SEA,
    ULTRA_MARINE,
)


def metric_card(value: rx.Var, label: str, color: str = DEEP_SEA) -> rx.Component:
    """Render a single metric card."""
    return rx.box(
        rx.vstack(
            rx.text(
                value,
                style={**metric_value_style, "color": color},
            ),
            rx.text(
                label,
                style=metric_label_style,
            ),
            spacing="1",
        ),
        style=metric_card_style,
    )


def metrics_section() -> rx.Component:
    """Render the metrics section after analysis."""
    return rx.cond(
        HienfeldState.results_ready,
        rx.vstack(
            # Mode indicator for internal analysis
            rx.cond(
                HienfeldState.stats_analysis_mode == "internal_only",
                rx.box(
                    rx.text(
                        "Modus: Interne analyse - Geen voorwaarden gebruikt",
                        weight="medium",
                    ),
                    style=alert_info_style,
                ),
            ),
            
            # Metrics grid
            rx.hstack(
                metric_card(
                    HienfeldState.stats_total_rows,
                    "Polisregels",
                ),
                metric_card(
                    HienfeldState.stats_unique_clusters,
                    "Unieke Clusters",
                ),
                metric_card(
                    HienfeldState.stats_reduction_percentage.to_string() + "%",
                    "Reductie",
                ),
                metric_card(
                    HienfeldState.stats_multi_clause_count,
                    "Te Splitsen",
                    color="#ffc107",
                ),
                wrap="wrap",
                spacing="4",
                justify="start",
                width="100%",
            ),
            
            align_items="stretch",
            width="100%",
            spacing="3",
        ),
    )


def advice_bar(item: dict) -> rx.Component:
    """Render a single advice bar."""
    return rx.hstack(
        rx.text(
            item["advice"],
            style={"width": "200px", "font_size": "0.85rem"},
        ),
        rx.box(
            style={
                "width": "100px",
                "height": "24px",
                "background_color": ULTRA_MARINE,
                "border_radius": "0px",
            },
        ),
        rx.text(
            item["count"],
            style={"font_weight": "600", "margin_left": "0.5rem"},
        ),
        spacing="2",
        align="center",
    )


def advice_distribution_chart() -> rx.Component:
    """Render the advice distribution as a simple bar visualization."""
    return rx.cond(
        HienfeldState.results_ready,
        rx.vstack(
            rx.heading("Advies Verdeling", size="4", style={"color": DEEP_SEA, "font_weight": "600"}),
            
            # Simple bar representation - using fixed width since we can't compute in styles
            rx.foreach(
                HienfeldState.advice_distribution_items,
                advice_bar,
            ),
            
            align_items="start",
            width="100%",
            spacing="2",
            padding="1rem 0",
        ),
    )
