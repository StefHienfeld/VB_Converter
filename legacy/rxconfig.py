"""Legacy Reflex configuratie voor de oude UI.

De actieve applicatie gebruikt nu FastAPI + React. Dit bestand blijft
alleen bestaan voor historische referentie.
"""

import reflex as rx

config = rx.Config(
    app_name="hienfeld_app",
    title="Hienfeld VB Converter",
    description="Automatisch vrije teksten analyseren en standaardiseren",
    frontend_port=3000,
    backend_port=8000,
    plugins=[],
)


