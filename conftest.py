"""Configuration pytest partagée.

Force le backend Qt « offscreen » : les widgets peuvent être construits sans
serveur d'affichage (tests UI exécutables en headless / intégration continue).
La variable doit être posée avant toute création de QApplication."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="session")
def qapp():
    """QApplication unique pour toute la session (une seule par processus)."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
