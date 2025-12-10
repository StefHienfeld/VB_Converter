"""Reflex configuration for Hienfeld VB Converter."""
import reflex as rx

config = rx.Config(
    app_name="hienfeld_app",
    title="Hienfeld VB Converter",
    description="Automatisch vrije teksten analyseren en standaardiseren",
    # Frontend settings
    frontend_port=3000,
    backend_port=8000,
    # Disable default sitemap plugin warnings
    plugins=[],
    # Tailwind for custom styling
    tailwind={
        "theme": {
            "extend": {
                "colors": {
                    "deep-sea": "#0A0466",
                    "ultra-marine": "#10069F",
                    "light-blue": "#7CC2FE",
                    "hienfeld-gray": "#F5F5F5",
                    "hienfeld-border": "#E0E0E0",
                },
                "fontFamily": {
                    "graphik": ["Graphik", "Open Sans", "Segoe UI", "Roboto", "Helvetica Neue", "sans-serif"],
                },
            }
        }
    },
)

