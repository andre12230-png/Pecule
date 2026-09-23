"""Prochain découvert : les échéances du mois du milieu (audit du 23/09/2026).

La fenêtre du bandeau « reste positif jusqu'au… » dure 45 jours : passé le
17 environ, elle couvre TROIS mois. Seuls le premier et le dernier étaient
consultés : le 23/09, une taxe foncière de 900 € prévue le 15/10 était
ignorée, et le bandeau annonçait un compte positif jusqu'au 07/11 alors qu'il
passait à −440 € le 15 octobre.
"""
from datetime import date, timedelta

from comptesbudget.database import Database


def _mois_suivant(d: date, n: int = 1) -> date:
    """Le 1er du n-ième mois après celui de `d`."""
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


def test_echeance_du_mois_du_milieu_est_vue(qapp, tmp_path):
    from comptesbudget.ui.views.bilan import BilanView, HORIZON_DECOUVERT
    db = Database(str(tmp_path / "t.db"))
    db.set_solde_initial(460.0, date.today().isoformat())
    db.insert_recurring({
        "id": "taxe", "libelle": "TAXE FONCIERE", "montant": -900.0,
        "categorie": "Impôts et taxes", "sous_cat": "", "type": "",
        "frequency": "monthly", "day_of_month": 15,
        "start_date": date.today().isoformat(), "end_date": None, "actif": 1})
    # Une fenêtre qui part le 28 du mois prochain enjambe forcément un mois
    # entier : 28 + 45 jours tombe au plus tard le 14 du mois d'après.
    depuis = _mois_suivant(date.today()).replace(day=28)
    jusqua = depuis + timedelta(days=HORIZON_DECOUVERT)
    milieu = _mois_suivant(depuis)

    vue = BilanView(db)
    echeances = vue._echeances_non_couvertes([], depuis, jusqua)
    assert [e["date"] for e in echeances] == [
        milieu.replace(day=15).isoformat()]
