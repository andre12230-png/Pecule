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


@pytest.fixture(autouse=True)
def detruire_les_fenetres():
    """Après chaque test, détruit les fenêtres qu'il a laissées ouvertes.

    `close()` les cache sans les libérer : elles restaient en vie toute la
    session, avec leurs appels programmés (charte des applis, section 7 —
    voir aussi detruire() du Photovoltaïque). La destruction passe par
    sendPostedEvents(DeferredDelete), qui ne fait tourner aucun autre
    événement : rien d'autre ne se déclenche au passage."""
    yield
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        return
    for fenetre in app.topLevelWidgets():
        fenetre.close()
        fenetre.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
