"""Confirmations : jamais « Oui » par défaut devant une action sans retour.

Relecture du 30/09/2026 : « Supprimer cette règle ? », « Supprimer cette
opération récurrente ? » et sept autres questions laissaient Qt choisir le
bouton par défaut — c'est alors « Oui » : un appui sur Entrée par réflexe
supprimait ou réécrivait des opérations, sans annulation possible. Et la
question ne disait pas QUELLE règle partait.

Règle (charte des applis, « Ce qu'on dit à l'utilisateur ») : bouton par
défaut sur « Garder » / « Annuler », boutons qui disent l'action.
"""
import ast
from pathlib import Path

import pytest

import comptesbudget

RACINE = Path(comptesbudget.__file__).parent


def test_aucune_question_ne_laisse_qt_choisir_le_bouton_par_defaut():
    """Chaque QMessageBox.question() nomme son bouton par défaut (5e
    argument) : un choix fait exprès, jamais celui de Qt. Les confirmations
    d'actions sans retour passent par widgets.confirmer()."""
    fautives = []
    for fichier in RACINE.rglob("*.py"):
        arbre = ast.parse(fichier.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if (isinstance(noeud, ast.Call)
                    and isinstance(noeud.func, ast.Attribute)
                    and noeud.func.attr == "question"
                    and isinstance(noeud.func.value, ast.Name)
                    and noeud.func.value.id == "QMessageBox"):
                explicite = (len(noeud.args) >= 5 or any(
                    k.arg == "defaultButton" for k in noeud.keywords))
                if not explicite:
                    fautives.append(f"{fichier.relative_to(RACINE)}:{noeud.lineno}")
    assert not fautives, "Bouton par défaut laissé à Qt (« Oui ») : " + ", ".join(fautives)


def test_boite_de_confirmation_garde_par_defaut(qapp):
    """Entrée et Échap choisissent tous deux « Garder » ; le bouton d'action
    dit ce qu'il fait ; une suppression montre l'icône d'avertissement."""
    from PySide6.QtWidgets import QMessageBox
    from comptesbudget.ui.widgets import boite_de_confirmation

    boite, bouton_action = boite_de_confirmation(
        None, "Supprimer la règle", "Supprimer la règle « carrefour » ?",
        action="Supprimer la règle", garder="Garder", danger=True)
    assert bouton_action.text() == "Supprimer la règle"
    assert boite.defaultButton().text() == "Garder"
    assert boite.escapeButton() is boite.defaultButton()
    assert boite.icon() == QMessageBox.Warning


@pytest.fixture
def db(tmp_path):
    from comptesbudget.database import Database
    d = Database(str(tmp_path / "confirmations.db"))
    d.insert_rule({"id": "r1", "pattern": "carrefour", "amount": None,
                   "categorie": "Alimentation", "sous_cat": "",
                   "no_overwrite": 0, "created_at": "2026-01-01"})
    d.insert_recurring({"id": "rec1", "libelle": "Loyer", "montant": -800.0,
                        "categorie": "Logement - maison", "sous_cat": "",
                        "type": "Prélèvement", "frequency": "monthly",
                        "day_of_month": 5, "start_date": "2026-01-05",
                        "end_date": None, "actif": 1})
    return d


def _espionner(monkeypatch, module, reponse=False):
    """Remplace confirmer() dans `module` par un espion qui répond `reponse`,
    et interdit la question nue de Qt (qui bloquerait le test)."""
    from PySide6.QtWidgets import QMessageBox
    appels = []

    def espion(parent, titre, question, action, garder="Annuler", danger=False):
        appels.append({"titre": titre, "question": question,
                       "action": action, "danger": danger})
        return reponse

    def interdite(*_a, **_k):
        raise AssertionError("QMessageBox.question() nue : passer par confirmer()")

    monkeypatch.setattr(module, "confirmer", espion, raising=False)
    monkeypatch.setattr(QMessageBox, "question", interdite)
    return appels


def test_supprimer_une_regle_la_nomme_et_se_garde(qapp, db, monkeypatch):
    from comptesbudget.ui.views import rules_view
    appels = _espionner(monkeypatch, rules_view)
    vue = rules_view.RulesView(db)
    vue.refresh()
    vue.table.setCurrentIndex(vue.model.index(0, 0))
    vue.delete_selected()
    assert len(appels) == 1
    assert "« carrefour »" in appels[0]["question"]
    assert appels[0]["action"] == "Supprimer la règle" and appels[0]["danger"]
    assert [r["id"] for r in db.list_rules()] == ["r1"]      # rien n'est parti


def test_supprimer_une_recurrence_la_nomme_et_se_garde(qapp, db, monkeypatch):
    from comptesbudget.ui.views import previsionnel
    appels = _espionner(monkeypatch, previsionnel)
    vue = previsionnel.PrevisionnelView(db)
    vue.refresh()
    vue.table.setCurrentIndex(vue.model.index(0, 0))
    vue._delete()
    assert len(appels) == 1
    assert "« Loyer »" in appels[0]["question"]
    assert appels[0]["danger"]
    assert [r["id"] for r in db.list_recurring()] == ["rec1"]
