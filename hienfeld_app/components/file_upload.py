"""File upload components for Hienfeld VB Converter."""
import reflex as rx
from ..state import HienfeldState
from ..styles import (
    card_style,
    file_upload_zone_style,
    button_style,
    checkbox_style,
    DEEP_SEA,
    ULTRA_MARINE,
    TEXT_MUTED,
)


def file_upload_section() -> rx.Component:
    """Render the policy file upload section."""
    return rx.box(
        rx.vstack(
            rx.text("1. Data Input", weight="bold", style={"color": DEEP_SEA, "font_size": "0.85rem"}),
            
            # Upload zone - compact
            rx.upload(
                rx.hstack(
                    rx.icon("upload", size=16, color=ULTRA_MARINE),
                    rx.text(
                        "Sleep Polisbestand (CSV/Excel)",
                        style={"color": DEEP_SEA, "font_size": "0.75rem"},
                    ),
                    align="center",
                    spacing="2",
                    justify="center",
                ),
                id="policy_upload",
                accept={
                    "text/csv": [".csv"],
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
                    "application/vnd.ms-excel": [".xls"],
                },
                max_files=1,
                on_drop=HienfeldState.handle_policy_upload(
                    rx.upload_files(upload_id="policy_upload")
                ),
                style=file_upload_zone_style,
            ),
            
            # Status message
            rx.cond(
                HienfeldState.policy_file_status != "",
                rx.hstack(
                    rx.icon("check-circle", size=14, color="#28a745"),
                    rx.text(HienfeldState.policy_file_status, style={"font_size": "0.75rem", "color": "#155724"}),
                    rx.button(
                        "X",
                        on_click=HienfeldState.clear_policy_file,
                        variant="ghost",
                        size="1",
                        style={"color": TEXT_MUTED, "font_size": "0.7rem", "padding": "0 0.25rem", "min_width": "auto"},
                    ),
                    align="center",
                    spacing="1",
                    width="100%",
                    style={"background_color": "#d4edda", "padding": "0.35rem 0.5rem", "border_radius": "6px"},
                ),
            ),
            
            align_items="stretch",
            width="100%",
            spacing="2",
            height="100%",
        ),
        style=card_style,
    )


def conditions_upload_section() -> rx.Component:
    """Render the conditions file upload section."""
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.text("2. Voorwaarden", weight="bold", style={"color": DEEP_SEA, "font_size": "0.85rem"}),
                rx.checkbox(
                    "",
                    default_checked=True,
                    on_change=HienfeldState.toggle_conditions,
                    style=checkbox_style,
                ),
                justify="between",
                align="center",
                width="100%",
            ),
            
            # Conditional content based on mode
            rx.cond(
                HienfeldState.use_conditions,
                # WITH conditions mode
                rx.vstack(
                    # Upload zone - compact
                    rx.upload(
                        rx.hstack(
                            rx.icon("file-text", size=16, color=ULTRA_MARINE),
                            rx.text(
                                "Sleep voorwaarden (PDF/DOCX/TXT)",
                                style={"color": DEEP_SEA, "font_size": "0.75rem"},
                            ),
                            align="center",
                            spacing="2",
                            justify="center",
                        ),
                        id="conditions_upload",
                        accept={
                            "application/pdf": [".pdf"],
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
                            "text/plain": [".txt"],
                        },
                        multiple=True,
                        on_drop=HienfeldState.handle_conditions_upload(
                            rx.upload_files(upload_id="conditions_upload")
                        ),
                        style=file_upload_zone_style,
                    ),
                    
                    # Status
                    rx.cond(
                        HienfeldState.conditions_status != "",
                        rx.hstack(
                            rx.icon("check-circle", size=14, color="#28a745"),
                            rx.text(HienfeldState.conditions_status, style={"font_size": "0.75rem", "color": "#155724"}),
                            rx.button(
                                "X",
                                on_click=HienfeldState.clear_condition_files,
                                variant="ghost",
                                size="1",
                                style={"color": TEXT_MUTED, "font_size": "0.7rem", "padding": "0 0.25rem", "min_width": "auto"},
                            ),
                            align="center",
                            spacing="1",
                            width="100%",
                            style={"background_color": "#d4edda", "padding": "0.35rem 0.5rem", "border_radius": "6px"},
                        ),
                    ),
                    
                    align_items="stretch",
                    width="100%",
                    spacing="2",
                ),
                # WITHOUT conditions mode
                rx.box(
                    rx.text(
                        "Uitgeschakeld",
                        style={"color": TEXT_MUTED, "font_size": "0.75rem", "font_style": "italic", "text_align": "center"},
                    ),
                    style={"padding": "1rem", "background_color": "#f8f9fa", "border_radius": "8px"},
                ),
            ),
            
            align_items="stretch",
            width="100%",
            spacing="2",
            height="100%",
        ),
        style=card_style,
    )


def clause_library_upload_section() -> rx.Component:
    """Render the clause library upload section."""
    return rx.box(
        rx.vstack(
            rx.text("3. Clausulebibliotheek", weight="bold", style={"color": DEEP_SEA, "font_size": "0.85rem"}),
            
            # Upload zone - compact
            rx.upload(
                rx.hstack(
                    rx.icon("library", size=16, color=ULTRA_MARINE),
                    rx.text(
                        "Upload bibliotheek (CSV/Excel/PDF)",
                        style={"color": DEEP_SEA, "font_size": "0.75rem"},
                    ),
                    align="center",
                    spacing="2",
                    justify="center",
                ),
                id="clause_library_upload",
                accept={
                    "text/csv": [".csv"],
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
                    "application/vnd.ms-excel": [".xls"],
                    "application/pdf": [".pdf"],
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
                },
                max_files=1,
                on_drop=HienfeldState.handle_clause_library_upload(
                    rx.upload_files(upload_id="clause_library_upload")
                ),
                style=file_upload_zone_style,
            ),
            
            # Status
            rx.cond(
                HienfeldState.clause_library_status != "",
                rx.hstack(
                    rx.icon("check-circle", size=14, color="#28a745"),
                    rx.text(HienfeldState.clause_library_status, style={"font_size": "0.75rem", "color": "#155724"}),
                    rx.button(
                        "X",
                        on_click=HienfeldState.clear_clause_library,
                        variant="ghost",
                        size="1",
                        style={"color": TEXT_MUTED, "font_size": "0.7rem", "padding": "0 0.25rem", "min_width": "auto"},
                    ),
                    align="center",
                    spacing="1",
                    width="100%",
                    style={"background_color": "#d4edda", "padding": "0.35rem 0.5rem", "border_radius": "6px"},
                ),
            ),
            
            align_items="stretch",
            width="100%",
            spacing="2",
            height="100%",
        ),
        style=card_style,
    )


def extra_instruction_section() -> rx.Component:
    """Render extra instruction input section as a card."""
    return rx.box(
        rx.vstack(
            rx.text("Extra instructies (optioneel)", weight="bold", style={"color": DEEP_SEA, "font_size": "0.85rem"}),
            rx.text_area(
                placeholder="Bijv: 'Let extra op clausules over asbest'...",
                on_blur=HienfeldState.set_extra_instruction,
                style={
                    "width": "100%",
                    "min_height": "50px",
                    "border": "1px solid #E0E0E0",
                    "border_radius": "8px",
                    "padding": "0.5rem",
                    "font_size": "0.8rem",
                },
            ),
            align_items="stretch",
            width="100%",
            spacing="2",
        ),
        style={**card_style, "height": "auto"},
    )


def start_button() -> rx.Component:
    """Render the start analysis button."""
    return rx.cond(
        HienfeldState.can_start_analysis,
        rx.button(
            "START ANALYSE",
            on_click=HienfeldState.run_analysis,
            style={**button_style, "width": "100%", "padding": "0.75rem", "font_size": "0.9rem"},
        ),
        rx.button(
            "START ANALYSE",
            disabled=True,
            style={
                **button_style,
                "width": "100%",
                "padding": "0.75rem",
                "font_size": "0.9rem",
                "background_color": "#cccccc",
                "cursor": "not-allowed",
                "_hover": {"background_color": "#cccccc"},
            },
        ),
    )

