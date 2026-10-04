"""Les types d'opération s'affichent accentués (audit de design du 04/10/2026).

La base garde les valeurs sans accents (« Prelevement », « Virement recu ») :
c'est ce qu'écrivent les imports et ce que lisent les règles. Seul l'écran
les écrit en bon français — « Prélèvement », « Virement reçu ». Avant, la
colonne Type des Opérations, de la Recherche et du Prévisionnel montrait le
mot brut.

Chacun de ces tests a été écrit avant la correction et vu en échec.
"""
from datetime import date

import pytest
from PySide6.QtCore import Qt

from comptesbudget.database import Database


def _tx(**kw):
    jour = date.today().isoformat()
    base = {"id": "x", "date": jour, "date_valeur": jour,
            "libelle": "EDF", "libelle_op": "EDF", "reference": "",
            "type": "Prelevement", "categorie": "Logement - maison",
            "sous_cat": "", "info": "", "montant": -50.0, "pointee": 1}
    base.update(kw)
    return base


@pytest.fixture
def db(tmp_path):
    d = Database(str(tmp_path / "types.db"))
    d.set_setting("initial_balance", "1000")
    d.set_setting("initial_date", "2020-01-01")
    d.insert_tx(_tx(id="edf"))
    d.insert_tx(_tx(id="sal", libelle="Salaire", type="Virement recu",
                    categorie="Revenus", montant=2000.0))
    return d


def test_correspondance_des_types():
    from comptesbudget.constants import type_affiche
    assert type_affiche("Prelevement") == "Prélèvement"
    assert type_affiche("Virement recu") == "Virement reçu"
    assert type_affiche("Cheque") == "Chèque"
    assert type_affiche("Retrait d'especes") == "Retrait d'espèces"
    # Un type inconnu (venu d'un import) s'affiche tel quel.
    assert type_affiche("Remise de chèques") == "Remise de chèques"
    assert type_affiche("") == ""
    assert type_affiche(None) == ""


def test_tableau_des_operations(qapp):
    from comptesbudget.ui.models import TxTableModel
    m = TxTableModel()
    m.load([_tx(id="a"), _tx(id="b", type="Virement recu", montant=10.0)])
    col = TxTableModel.HEADERS.index("Type")
    textes = {m.item(r, col).text() for r in range(m.rowCount())}
    assert textes == {"Prélèvement", "Virement reçu"}


def test_filtre_type_des_operations(qapp, db):
    from comptesbudget.ui.views.operations import OperationsView
    vue = OperationsView(db)
    vue.period = "all"
    vue.reload_from_db()
    f = vue.optype_filter
    libelles = [f.itemText(i) for i in range(f.count())]
    assert "Prélèvement" in libelles and "Prelevement" not in libelles
    # Le filtre choisi par son libellé accentué trouve bien l'opération.
    f.setCurrentIndex(libelles.index("Prélèvement"))
    vue.refresh()
    assert vue.model.rowCount() == 1


def test_previsionnel(qapp, db):
    from comptesbudget.ui.views.previsionnel import PrevisionnelView
    db.insert_recurring({
        "id": "r1", "libelle": "EDF", "montant": -50.0,
        "categorie": "Logement - maison", "sous_cat": "", "type": "Prelevement",
        "frequency": "monthly", "day_of_month": 5,
        "start_date": "2026-01-05", "end_date": None, "actif": 1})
    vue = PrevisionnelView(db)
    vue.refresh()
    entetes = [vue.model.headerData(c, Qt.Horizontal) for c in range(vue.model.columnCount())]
    assert vue.model.item(0, entetes.index("Type")).text() == "Prélèvement"


def test_saisie_affiche_accentue_et_enregistre_brut(qapp):
    from comptesbudget.ui.dialogs import TxDialog
    d = TxDialog(None, _tx(id="a"), ["Logement - maison"], [])
    assert d.type_combo.currentText() == "Prélèvement"
    assert d.values()["type"] == "Prelevement"


def test_recurrente_affiche_accentue_et_enregistre_brut(qapp):
    from comptesbudget.ui.dialogs import RecurringDialog
    rec = {"id": "r1", "libelle": "EDF", "montant": -50.0,
           "categorie": "Logement - maison", "sous_cat": "",
           "type": "Prelevement", "frequency": "monthly", "day_of_month": 5,
           "start_date": "2026-01-05", "end_date": None, "actif": 1}
    d = RecurringDialog(None, rec, ["Logement - maison"], [])
    assert d.type_combo.currentText() == "Prélèvement"
    assert d.values()["type"] == "Prelevement"
