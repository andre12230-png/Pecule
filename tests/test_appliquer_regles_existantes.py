"""« 🔄 Appliquer aux opérations existantes » n'écrase jamais un classement.

Constat du 20/10/2026 : le bouton de la fenêtre des règles rejouait toutes
les règles sur toute la base et remplaçait les catégories corrigées à la
main. Exemple : un achat en ligne avancé pour un proche et reclassé à la main
en « Famille » repartait dans la catégorie de la règle du marchand.

Décision : le bouton ne classe que les opérations encore « Non classé » ;
une opération qui a déjà une catégorie (choisie à la main ou non) la garde.
"""
import pytest

from comptesbudget.database import Database


def _tx(id_, libelle, categorie, montant=-50.0):
    return {
        "id": id_, "date": "2026-06-01", "date_valeur": "2026-06-01",
        "libelle": libelle, "libelle_op": libelle, "reference": "",
        "type": "", "categorie": categorie, "sous_cat": "", "info": "",
        "montant": montant, "pointee": 0,
    }


@pytest.fixture
def db(tmp_path):
    d = Database(str(tmp_path / "regles.db"))
    d.insert_rule({"id": "r1", "pattern": "boutique", "amount": None,
                   "categorie": "Shopping", "sous_cat": "",
                   "no_overwrite": 0, "created_at": "2026-01-01"})
    # Corrigée à la main : elle doit rester en « Famille ».
    d.insert_tx(_tx("main", "ACHAT BOUTIQUE EN LIGNE", "Famille"))
    # Jamais classée : la règle doit la ranger.
    d.insert_tx(_tx("vide", "ACHAT BOUTIQUE EN LIGNE", "Non classé"))
    return d


def _categories(db):
    return {r["id"]: r["categorie"] for r in db.list_tx()}


def test_appliquer_ne_remplace_pas_une_categorie_deja_choisie(qapp, db, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from comptesbudget.ui.views.rules_view import RulesView
    messages = []
    monkeypatch.setattr(QMessageBox, "information",
                        lambda parent, titre, texte, *a: messages.append(texte))
    RulesView(db).apply_all()
    assert _categories(db) == {"main": "Famille", "vide": "Shopping"}
    # Le message dit ce qui a changé et ce qui a été laissé tel quel.
    assert "1 opération" in messages[0]
    assert "déjà classée" in messages[0]
