"""Results table component for Hienfeld VB Converter."""
import reflex as rx
from ..state import HienfeldState
from ..styles import (
    card_style,
    table_style,
    table_header_style,
    table_cell_style,
    table_row_hover_style,
    download_button_style,
    expander_style,
    expander_header_style,
    expander_content_style,
    divider_style,
    DEEP_SEA,
    ULTRA_MARINE,
    LIGHT_BLUE,
    WHITE,
    TEXT_MUTED,
    ADVICE_COLORS,
)
from typing import Dict, Any


def advice_badge(advice_code: rx.Var) -> rx.Component:
    """Render an advice badge with appropriate color."""
    return rx.badge(
        advice_code,
        style={
            "background_color": ULTRA_MARINE,
            "color": WHITE,
            "padding": "0.2rem 0.5rem",
            "border_radius": "3px",
            "font_size": "0.8rem",
        },
    )


def result_row(row: Dict[str, Any]) -> rx.Component:
    """Render a single result row."""
    return rx.table.row(
        rx.table.cell(
            rx.text(row["cluster_id"], style={"font_size": "0.85rem"}),
        ),
        rx.table.cell(
            rx.text(
                row["cluster_name"],
                style={"font_size": "0.85rem"},
            ),
        ),
        rx.table.cell(
            rx.text(row["frequency"], style={"font_weight": "600"}),
        ),
        rx.table.cell(
            advice_badge(row["advice_code"]),
        ),
        rx.table.cell(
            rx.text(row["confidence"], style={"font_size": "0.85rem", "color": TEXT_MUTED}),
        ),
        rx.table.cell(
            rx.text(
                row["reason"],
                style={"font_size": "0.85rem", "color": TEXT_MUTED},
            ),
        ),
        rx.table.cell(
            rx.text(row["reference_article"], style={"font_size": "0.85rem"}),
        ),
        style=table_row_hover_style,
    )


def results_table() -> rx.Component:
    """Render the results table with download button."""
    return rx.cond(
        HienfeldState.results_ready,
        rx.vstack(
            # Download button prominently displayed
            rx.hstack(
                rx.link(
                    rx.button(
                        rx.hstack(
                            rx.icon("download", size=18),
                            rx.text("Download Rapport (Excel)"),
                            spacing="2",
                        ),
                        style=download_button_style,
                    ),
                    href=rx.Var.create(f"data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,") + HienfeldState.excel_data_base64,
                    download="Hienfeld_Analyse.xlsx",
                    is_external=True,
                ),
                justify="start",
                width="100%",
            ),
            
            rx.divider(style=divider_style),
            
            # Table header
            rx.hstack(
                rx.heading(
                    "Detailoverzicht (Voorbeeld)",
                    size="4",
                    style={"color": DEEP_SEA, "font_weight": "600"},
                ),
                rx.cond(
                    HienfeldState.total_results_count > 10,
                    rx.badge(
                        "Toont 10 van " + HienfeldState.total_results_count.to_string(),
                        color_scheme="blue",
                    ),
                ),
                justify="between",
                align="center",
                width="100%",
            ),
            
            rx.text(
                "Download het Excel-rapport voor alle data.",
                style={"color": TEXT_MUTED, "font_size": "0.9rem"},
            ),
            
            # Results table
            rx.box(
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("Cluster ID", style=table_header_style),
                            rx.table.column_header_cell("Naam", style=table_header_style),
                            rx.table.column_header_cell("Freq.", style=table_header_style),
                            rx.table.column_header_cell("Advies", style=table_header_style),
                            rx.table.column_header_cell("Vertrouwen", style=table_header_style),
                            rx.table.column_header_cell("Reden", style=table_header_style),
                            rx.table.column_header_cell("Artikel", style=table_header_style),
                        ),
                    ),
                    rx.table.body(
                        rx.foreach(
                            HienfeldState.display_results,
                            result_row,
                        ),
                    ),
                    style=table_style,
                ),
                style={"overflow_x": "auto", "width": "100%"},
            ),
            
            align_items="stretch",
            width="100%",
            spacing="3",
        ),
    )


def welcome_section() -> rx.Component:
    """Render the welcome section when no results are available."""
    return rx.cond(
        ~HienfeldState.results_ready & ~HienfeldState.is_analyzing,
        rx.box(
            rx.vstack(
                rx.text(
                    "Analyseer en standaardiseer grote hoeveelheden vrije teksten uit polisbestanden. "
                    "De tool identificeert duplicaten, vergelijkt met voorwaarden en geeft actiegericht advies.",
                    style={"color": TEXT_MUTED, "font_size": "0.9rem"},
                ),
                
                rx.divider(style={"margin": "0.75rem 0", "border_top": "1px solid #E0E0E0"}),
                
                rx.heading("Werkwijze:", size="4", style={"color": DEEP_SEA, "font_size": "1rem"}),
                rx.ordered_list(
                    rx.list_item("Upload uw polisbestand (CSV/Excel)"),
                    rx.list_item("Kies voor analyse met of zonder voorwaarden"),
                    rx.list_item("Start de analyse en download het rapport"),
                    style={"color": TEXT_MUTED, "font_size": "0.85rem"},
                ),
                
                rx.heading("Output:", size="4", style={"color": DEEP_SEA, "margin_top": "0.5rem", "font_size": "1rem"}),
                rx.text(
                    "Excel-bestand met geclusterde teksten, advies per cluster en voorgestelde acties.",
                    style={"color": TEXT_MUTED, "font_size": "0.85rem"},
                ),
                
                align_items="start",
                width="100%",
                spacing="2",
            ),
            style={
                "padding": "1.25rem",
                "background_color": "#F5F5F5",
                "border": "1px solid #E0E0E0",
                "border_radius": "12px",
            },
        ),
    )
