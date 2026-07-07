"""Tests des deux recherches (globale et onglet Opérations) sur les montants.

Régression signalée le 2026-07-07 : « dans la recherche quand je rentre un
montant il ne trouve rien » — l'onglet Opérations ne cherchait pas dans les
montants, et la Recherche globale échouait sur la forme affichée (« -45,30 € »).
"""
import pytest

from comptesbudget.database import Database


def _tx(**kw):
    base = {
        "id": "x", "date": "2026-06-01", "date_valeur": "2026-06-01",
        "libelle": "OP", "libelle_op": "OP", "reference": "", "type": "",
        "categorie": "Non classé", "sous_cat": "", "info": "",
        "montant": -10.0, "pointee": 0,
    }
    base.update(kw)
    return base


@pytest.fixture
def db(tmp_path):
    d = Database(str(tmp_path / "s.db"))
    d.insert_tx(_tx(id="a", libelle="GARAGE DU CENTRE", libelle_op="GARAGE DU CENTRE",
                    montant=-300.50))
    d.insert_tx(_tx(id="b", libelle="CAFE", libelle_op="CAFE", montant=-2.5))
    return d


def test_recherche_globale_trouve_les_montants(qapp, db):
    from comptesbudget.ui.search import GlobalSearchDialog
    dlg = GlobalSearchDialog(None, db)
    # Virgule, point, et surtout la forme affichée à l'écran (signe + €).
    for saisie in ("300,50", "300.50", "-300,50 €", "300,50 €"):
        dlg.edit.setText(saisie)
        assert dlg.model.rowCount() == 1, f"échec pour {saisie!r}"


def test_recherche_operations_trouve_montants_et_dates(qapp, db):
    from comptesbudget.ui.views.operations import OperationsView
    v = OperationsView(db)
    v.period = "all"
    v.reload_from_db()

    v.search.setText("-300,50 €")
    assert len(v.filtered) == 1
    v.search.setText("2,50")
    assert len(v.filtered) == 1
    v.search.setText("01/06/2026")          # date au format français
    assert len(v.filtered) == 2
    v.search.setText("garage centre")       # plusieurs mots : tous requis
    assert len(v.filtered) == 1
    v.search.setText("")                    # champ vide : tout s'affiche
    assert len(v.filtered) == 2
