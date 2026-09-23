"""Le rapport mensuel s'ouvre sur la période choisie dans la barre du haut.

Demande du 23/09/2026 : la barre affichait « 2026 / Janvier », mais le
rapport s'ouvrait toujours sur le mois en cours (septembre) ; il fallait
rechoisir le mois dans sa propre liste.
"""
from datetime import date

from comptesbudget.database import Database


def _base(tmp_path, *dates):
    db = Database(str(tmp_path / "t.db"))
    db.set_solde_initial(0.0, "2024-01-01")
    for i, d in enumerate(dates):
        db.insert_tx({
            "id": f"op{i}", "date": d, "date_valeur": d, "libelle": "ACHAT",
            "libelle_op": "", "reference": "", "type": "Prelevement",
            "categorie": "Alimentation", "sous_cat": "", "info": "",
            "montant": -10.0, "pointee": 1})
    return db


def _mois_ouvert(db, periode):
    from comptesbudget.ui.report import MonthlyReportDialog
    return MonthlyReportDialog(None, db, periode).current_month()


def test_un_mois_choisi(qapp, tmp_path):
    db = _base(tmp_path, "2025-03-10", "2026-01-15", "2026-02-15")
    assert _mois_ouvert(db, "2026-01") == "2026-01"


def test_une_annee_passee_ouvre_sur_son_dernier_mois(qapp, tmp_path):
    db = _base(tmp_path, "2025-03-10", "2025-11-20", "2026-01-15")
    assert _mois_ouvert(db, "2025") == "2025-11"


def test_l_annee_en_cours_ouvre_sur_le_mois_en_cours(qapp, tmp_path):
    auj = date.today()
    db = _base(tmp_path, f"{auj.year}-01-15", auj.isoformat())
    assert _mois_ouvert(db, str(auj.year)) == auj.strftime("%Y-%m")


def test_toutes_periodes_ouvre_sur_le_mois_en_cours(qapp, tmp_path):
    auj = date.today()
    db = _base(tmp_path, "2025-03-10", auj.isoformat())
    assert _mois_ouvert(db, "all") == auj.strftime("%Y-%m")


def test_sans_periode_comme_avant(qapp, tmp_path):
    auj = date.today()
    db = _base(tmp_path, "2025-03-10", auj.isoformat())
    assert _mois_ouvert(db, None) == auj.strftime("%Y-%m")


def test_un_mois_sans_operation_s_ouvre_quand_meme(qapp, tmp_path):
    # Le mois choisi en haut doit être celui du rapport, même vide : sinon
    # on lirait sans le voir le rapport d'un autre mois.
    db = _base(tmp_path, "2025-03-10", "2026-01-15")
    assert _mois_ouvert(db, "2025-07") == "2025-07"
