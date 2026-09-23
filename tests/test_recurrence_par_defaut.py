"""Nouvelle récurrence : des valeurs par défaut qui ne piègent pas.

Audit du 23/09/2026 : la fenêtre proposait « Hebdomadaire » et le jour 1.
Une taxe annuelle du 15/10 tombait ensuite le 01/10 chaque année (le jour du
mois sert aussi à l'annuelle), et un salaire réglé au 28 sans toucher au jour
était attendu le 1er.
"""
from datetime import date

from PySide6.QtCore import QDate


def _fenetre(rec=None):
    from comptesbudget.ui.dialogs import RecurringDialog
    return RecurringDialog(None, rec, categories=["Revenus"], all_tx=[])


def test_mensuelle_au_jour_d_aujourd_hui(qapp):
    v = _fenetre().values()
    assert v["frequency"] == "monthly"
    assert v["day_of_month"] == date.today().day


def test_le_jour_suit_la_date_de_debut(qapp):
    dlg = _fenetre()
    dlg.start_date.setDate(QDate(2026, 10, 15))
    assert dlg.values()["day_of_month"] == 15


def test_une_recurrence_existante_garde_son_jour(qapp):
    rec = {"libelle": "PRETIS", "montant": -600.0, "categorie": "Revenus",
           "frequency": "weekly", "day_of_month": 10,
           "start_date": "2026-01-10", "actif": 1}
    dlg = _fenetre(rec)
    dlg.start_date.setDate(QDate(2026, 3, 22))
    v = dlg.values()
    assert v["frequency"] == "weekly"
    assert v["day_of_month"] == 10
