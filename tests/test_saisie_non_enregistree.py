"""Fenêtres de saisie : ce qui est tapé ne se perd pas sans un mot (charte ;
choix de l'auteur du 08/10/2026).

Fermer (Annuler, Échap, la croix) une fenêtre d'opération, de récurrence,
de règle ou de paramètres où des valeurs ont changé demande « Fermer sans
enregistrer » ou « Continuer la saisie », ce dernier par défaut. Sans
changement, rien n'est demandé.
"""
import pytest

import comptesbudget.ui.dialogs as module_dialogs
from comptesbudget.ui.dialogs import (RecurringDialog, RuleDialog,
                                      SettingsDialog, TxDialog)


def _ouvrir(classe):
    if classe is TxDialog:
        return TxDialog(None, None, ["Revenus"], [])
    if classe is RecurringDialog:
        return RecurringDialog(None, None, categories=["Revenus"], all_tx=[])
    if classe is RuleDialog:
        return RuleDialog(None, None, ["Revenus"])
    return SettingsDialog(None, "2026-01-01", 100.0, "Compte courant")


def _modifier(dlg):
    if isinstance(dlg, SettingsDialog):
        dlg.initial_balance.setValue(250.0)
    elif isinstance(dlg, RuleDialog):
        dlg.pattern.setText("CARREFOUR")
    else:
        dlg.libelle.setText("LOYER")


@pytest.fixture
def questions(monkeypatch):
    posees = []
    reponse = {"valeur": False}

    def espion(parent, titre, texte, action, garder="Annuler", **k):
        posees.append((titre, action, garder))
        return reponse["valeur"]
    monkeypatch.setattr(module_dialogs, "confirmer", espion)
    return posees, reponse


@pytest.mark.parametrize("classe", [TxDialog, RecurringDialog, RuleDialog,
                                    SettingsDialog])
def test_sans_changement_rien_n_est_demande(qapp, questions, classe):
    posees, _ = questions
    dlg = _ouvrir(classe)
    fermes = []
    dlg.finished.connect(fermes.append)
    dlg.reject()
    assert posees == [] and fermes == [0]


@pytest.mark.parametrize("classe", [TxDialog, RecurringDialog, RuleDialog,
                                    SettingsDialog])
def test_une_saisie_tapee_demande_avant_de_fermer(qapp, questions, classe):
    posees, reponse = questions
    dlg = _ouvrir(classe)
    fermes = []
    dlg.finished.connect(fermes.append)
    _modifier(dlg)
    dlg.reject()                           # « Continuer la saisie »
    assert posees == [("Saisie non enregistrée", "Fermer sans enregistrer",
                       "Continuer la saisie")]
    assert fermes == []
    reponse["valeur"] = True
    dlg.reject()                           # « Fermer sans enregistrer »
    assert fermes == [0]


def test_ouverte_sur_une_operation_existante_rien_n_est_demande(qapp, questions):
    """Modifier une opération puis Annuler sans rien changer : pas de question."""
    posees, _ = questions
    tx = {"id": "x", "date": "2026-06-01", "date_valeur": "2026-06-04",
          "libelle": "LOYER", "libelle_op": "LOYER", "reference": "",
          "type": "Prélèvement", "categorie": "Revenus", "sous_cat": "",
          "info": "note", "montant": -650.0, "pointee": 1}
    dlg = TxDialog(None, tx, ["Revenus"], [])
    fermes = []
    dlg.finished.connect(fermes.append)
    dlg.reject()
    assert posees == [] and fermes == [0]


def test_recurrence_existante_rien_n_est_demande(qapp, questions):
    posees, _ = questions
    rec = {"libelle": "LOYER", "montant": -650.0, "categorie": "Revenus",
           "sous_cat": "", "type": "Prélèvement", "frequency": "monthly",
           "day_of_month": 5, "start_date": "2026-01-05", "end_date": None,
           "actif": 1}
    dlg = RecurringDialog(None, rec, categories=["Revenus"], all_tx=[])
    fermes = []
    dlg.finished.connect(fermes.append)
    dlg.reject()
    assert posees == [] and fermes == [0]
