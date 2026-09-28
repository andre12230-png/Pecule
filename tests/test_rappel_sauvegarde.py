"""Rappel de sauvegarde externe (28/09/2026), commun aux trois applications.

La date de la dernière sauvegarde externe réussie est retenue dans la base
(réglage « _meta_ », hors synchronisation) ; le Bilan affiche un bandeau
au-delà de 30 jours, avec un lien qui lance la sauvegarde. Sans sauvegarde
jamais faite, on compte depuis la première utilisation (réglage d'avis.py).
Le texte vient de sauvegarde_externe.rappel_sauvegarde_externe.
"""
from datetime import date, timedelta

import pytest

from comptesbudget.database import Database
from comptesbudget.ui.avis import CLE_PREMIERE_UTILISATION
from comptesbudget.ui.views.bilan import CLE_DERNIERE_SAUVEGARDE


@pytest.fixture
def fenetre(qapp, tmp_path):
    from comptesbudget.ui.main_window import MainWindow
    # Les donnees dans un sous-dossier : la « cle USB » du test est a cote,
    # jamais dedans (Pecule refuse, a juste titre, de sauvegarder dans le
    # dossier de ses donnees, et sa boite d'avertissement attendrait un clic).
    (tmp_path / "donnees").mkdir()
    db = Database(str(tmp_path / "donnees" / "rappel.db"))
    db.set_setting("initial_balance", "0")
    f = MainWindow(db)
    yield f
    f.deleteLater()


def _il_y_a(jours: int) -> str:
    return (date.today() - timedelta(days=jours)).isoformat()


def test_la_cle_reste_hors_synchronisation():
    assert CLE_DERNIERE_SAUVEGARDE.startswith("_meta_")


def test_le_bandeau_du_bilan(fenetre):
    bilan, db = fenetre.bilan_view, fenetre.db
    db.set_setting(CLE_PREMIERE_UTILISATION, _il_y_a(5))
    bilan.refresh()
    assert not bilan.sauvegarde_alert.isVisibleTo(bilan)
    db.set_setting(CLE_PREMIERE_UTILISATION, _il_y_a(45))
    bilan.refresh()
    assert bilan.sauvegarde_alert.isVisibleTo(bilan)
    assert "jamais" in bilan.sauvegarde_alert.text()
    db.set_setting(CLE_DERNIERE_SAUVEGARDE, _il_y_a(2))
    bilan.refresh()
    assert not bilan.sauvegarde_alert.isVisibleTo(bilan)
    db.set_setting(CLE_DERNIERE_SAUVEGARDE, _il_y_a(35))
    bilan.refresh()
    assert "depuis 35 jours" in bilan.sauvegarde_alert.text()


def test_le_bouton_retient_la_date(fenetre, monkeypatch, tmp_path):
    from comptesbudget.ui import main_window
    cle = tmp_path / "cle"
    cle.mkdir()
    monkeypatch.setattr(main_window.QFileDialog, "getExistingDirectory",
                        lambda *a: str(cle))
    messages = []
    monkeypatch.setattr(main_window.QMessageBox, "information",
                        lambda *a: messages.append("info"))
    monkeypatch.setattr(main_window.QMessageBox, "warning",
                        lambda *a: messages.append(("alerte", a[-1])))
    fenetre.action_sauvegarde_externe()
    assert messages == ["info"], messages
    assert list(cle.iterdir())                       # la copie est faite
    assert fenetre.db.get_setting(CLE_DERNIERE_SAUVEGARDE) == \
        date.today().isoformat()


def test_le_lien_du_bandeau_lance_la_sauvegarde(fenetre, monkeypatch):
    appels = []
    monkeypatch.setattr(type(fenetre), "action_sauvegarde_externe",
                        lambda self: appels.append(1))
    fenetre.bilan_view.sauvegarde_alert.linkActivated.emit("#")
    assert appels == [1]
