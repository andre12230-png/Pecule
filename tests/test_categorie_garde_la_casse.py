"""Une catégorie tapée garde ses majuscules et minuscules (signalé par un
utilisateur le 13/10/2026).

Un import QIF peut apporter des catégories en capitales (« ALIMENTATION »).
Taper « Alimentation » dans la case Catégorie puis appuyer sur Entrée
redonnait « ALIMENTATION » : la liste de suggestions de Qt cherche sans
tenir compte de la casse et remplaçait la frappe par le nom déjà connu.
Impossible, donc, de corriger l'écriture d'une catégorie.

Règle : ce que la personne a tapé en entier est gardé tel quel. Les
suggestions ne changent pas : un début de mot complété par la case
(« alim » → « ALIMENTATION ») n'est pas une frappe complète, la correction
ne le touche pas. Ce cas n'est pas vérifié ici : sans écran, Qt ne complète
pas pendant la frappe simulée.
"""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

import comptesbudget.ui.dialogs as module_dialogs
from comptesbudget.ui.dialogs import (CategorieEnMasseDialog, RecurringDialog,
                                      RuleDialog, TxDialog)


@pytest.fixture(autouse=True)
def sans_message_bloquant(monkeypatch):
    """Entrée valide aussi la fenêtre : « Libellé manquant » s'ouvrirait et
    attendrait un clic, et la fermeture demanderait « Fermer sans
    enregistrer ? ». On répond d'office pour que le test ne bloque pas."""
    monkeypatch.setattr(module_dialogs.QMessageBox, "warning",
                        staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(module_dialogs, "confirmer", lambda *a, **k: True)
    yield
    # Refermer ici, tant que les réponses d'office tiennent encore.
    from PySide6.QtWidgets import QApplication
    for fenetre in QApplication.topLevelWidgets():
        fenetre.close()

CATEGORIES = ["ALIMENTATION", "Loisirs", "Transports"]
# Une opération déjà classée, pour que la sous-catégorie en capitales soit
# proposée sous « ALIMENTATION ».
HISTORIQUE = [{"id": "1", "date": "2026-10-01", "libelle": "MAGASIN",
               "montant": -10.0, "categorie": "ALIMENTATION",
               "sous_cat": "SUPERMARCHE", "type": "Carte"}]


def _ouvrir(nom):
    if nom == "operation":
        return TxDialog(None, None, CATEGORIES, HISTORIQUE)
    if nom == "reclassement":
        return CategorieEnMasseDialog(None, 2, CATEGORIES, HISTORIQUE)
    if nom == "regle":
        return RuleDialog(None, None, CATEGORIES)
    return RecurringDialog(None, None, categories=CATEGORIES, all_tx=HISTORIQUE)


def _taper_puis_entree(qapp, combo, texte):
    """Vide la case, tape le texte comme au clavier, puis appuie sur Entrée.
    Si la liste de suggestions s'est ouverte, c'est elle qui reçoit la
    touche, comme pour un vrai clavier."""
    combo.setCurrentIndex(-1)
    combo.setEditText("")
    combo.lineEdit().setFocus()
    QTest.keyClicks(combo.lineEdit(), texte)
    qapp.processEvents()
    popup = combo.completer().popup() if combo.completer() else None
    cible = popup if popup is not None and popup.isVisible() else combo.lineEdit()
    QTest.keyClick(cible, Qt.Key_Return)
    qapp.processEvents()


@pytest.mark.parametrize("nom", ["operation", "reclassement", "regle", "recurrence"])
def test_categorie_tapee_garde_sa_casse(qapp, nom):
    dlg = _ouvrir(nom)
    dlg.show()
    _taper_puis_entree(qapp, dlg.cat, "Alimentation")
    assert dlg.cat.currentText() == "Alimentation"
    dlg.hide()


@pytest.mark.parametrize("nom", ["operation", "reclassement", "recurrence"])
def test_sous_categorie_tapee_garde_sa_casse(qapp, nom):
    dlg = _ouvrir(nom)
    dlg.show()
    dlg.cat.setCurrentText("ALIMENTATION")
    qapp.processEvents()
    assert dlg.sous_cat.findText("SUPERMARCHE") >= 0   # bien proposée
    _taper_puis_entree(qapp, dlg.sous_cat, "Supermarche")
    assert dlg.sous_cat.currentText() == "Supermarche"
    dlg.hide()


def test_le_nom_connu_tape_tel_quel_reste_tel_quel(qapp):
    """Taper exactement « ALIMENTATION » donne « ALIMENTATION »."""
    dlg = _ouvrir("operation")
    dlg.show()
    _taper_puis_entree(qapp, dlg.cat, "ALIMENTATION")
    assert dlg.cat.currentText() == "ALIMENTATION"
    dlg.hide()


def test_choisir_dans_la_liste_deroulante(qapp):
    """Choisir à la souris dans la liste, sans rien taper, reste possible."""
    dlg = _ouvrir("regle")
    dlg.cat.setCurrentIndex(dlg.cat.findText("Loisirs"))
    assert dlg.cat.currentText() == "Loisirs"
