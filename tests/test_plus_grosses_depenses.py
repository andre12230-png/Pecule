"""« Plus grosses dépenses » : un même libellé sur une seule ligne.

Demande d'André du 10/10/2026 : deux passages au même magasin sur la période
(par exemple deux achats carte de septembre débités en octobre) prenaient
deux lignes de la liste du Bilan. Ils n'en font plus qu'une, avec leur total,
et la ligne dit « 2 fois » à la place de la date.
"""
from datetime import date

from comptesbudget.database import Database
from comptesbudget.utils import plus_grosses_depenses


MOIS = date.today().strftime("%Y-%m")
JOUR = date.today().isoformat()


def _tx(id_, montant, libelle, categorie="Courses", jour=JOUR):
    return {"id": id_, "date": jour, "date_valeur": jour, "libelle": libelle,
            "libelle_op": libelle, "reference": "", "type": "",
            "categorie": categorie, "sous_cat": "", "info": "",
            "montant": montant, "pointee": 1}


def test_meme_libelle_regroupe_avec_son_total():
    txs = [_tx("a", -100.0, "MAGASIN A"), _tx("b", -80.0, "Magasin A "),
           _tx("c", -150.0, "LOYER", "Logement"), _tx("d", 500.0, "SALAIRE")]
    top = plus_grosses_depenses(txs)
    assert [(d["libelle"], d["montant"], d["nb"]) for d in top] == [
        ("MAGASIN A", -180.0, 2), ("LOYER", -150.0, 1)]


def test_le_regroupement_change_le_classement_et_la_limite():
    # Deux petites dépenses au même endroit peuvent passer devant une
    # grosse ; la limite compte les lignes, pas les opérations.
    txs = [_tx("a", -60.0, "PETIT"), _tx("b", -60.0, "PETIT"),
           _tx("c", -100.0, "GROS"), _tx("d", -10.0, "AUTRE")]
    top = plus_grosses_depenses(txs, limite=2)
    assert [d["libelle"] for d in top] == ["PETIT", "GROS"]


def test_une_seule_operation_garde_sa_date():
    top = plus_grosses_depenses([_tx("a", -40.0, "SEUL", jour="2026-01-15")])
    assert top[0]["nb"] == 1 and top[0]["date"] == "2026-01-15"


def test_liste_du_bilan_dit_2_fois(qapp, tmp_path):
    from PySide6.QtWidgets import QLabel
    from comptesbudget.ui.views.bilan import BilanView
    db = Database(str(tmp_path / "t.db"))
    for t in (_tx("a", -100.0, "MAGASIN A"), _tx("b", -80.0, "MAGASIN A"),
              _tx("c", -150.0, "LOYER", "Logement")):
        db.insert_tx(t)
    v = BilanView(db)
    v.period = MOIS
    v.refresh()
    textes = [w.text() for w in v.list_top.findChildren(QLabel)]
    assert sum(1 for x in textes if "MAGASIN A" in x) == 1
    assert "2 fois" in textes


def test_rapport_regroupe_aussi(tmp_path):
    from comptesbudget.ui.report import build_monthly_report_html
    db = Database(str(tmp_path / "t.db"))
    for t in (_tx("a", -100.0, "MAGASIN A"), _tx("b", -80.0, "MAGASIN A")):
        db.insert_tx(t)
    html = build_monthly_report_html(db, MOIS)
    partie = html.split("Plus grosses dépenses")[1]
    assert partie.count("MAGASIN A") == 1
    assert "2 fois" in partie
