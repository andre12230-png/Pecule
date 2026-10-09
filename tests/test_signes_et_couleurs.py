"""Signe « + » et couleurs des montants (choix de l'auteur du 08/10/2026).

- Un mouvement ou un reste positif porte son « + » : la couleur ne porte
  jamais seule le sens (charte). Pas les soldes, qui ne sont pas des
  mouvements.
- « Reste à pointer » est neutre : un reste à faire n'est pas un gain.
Données inventées.
"""
from datetime import date

from comptesbudget.database import Database
from comptesbudget.utils import fmt_euro_signe


def test_fmt_euro_signe():
    assert fmt_euro_signe(1234.5) == "+1\xa0234,50\xa0€"
    assert fmt_euro_signe(-12.5) == "-12,50\xa0€"
    assert fmt_euro_signe(0.001) == "0,00\xa0€"
    assert fmt_euro_signe(-0.001) == "0,00\xa0€"


def _tx(**kw):
    base = {"id": "x", "date": "2026-06-01", "date_valeur": "2026-06-01",
            "libelle": "OP", "libelle_op": "OP", "reference": "", "type": "",
            "categorie": "Non classé", "sous_cat": "", "info": "",
            "montant": -10.0, "pointee": 1}
    base.update(kw)
    return base


def test_bilan_mouvement_signe_et_reste_a_pointer_neutre(qapp, tmp_path):
    from comptesbudget.ui.views.bilan import BilanView
    d = Database(str(tmp_path / "s.db"))
    d.set_setting("initial_balance", "1000")
    d.set_setting("initial_date", "2020-01-01")
    jour = date.today().replace(day=1).isoformat()
    d.insert_tx(_tx(id="a", date=jour, date_valeur=jour, montant=500.0,
                    categorie="Revenus", pointee=0))
    vue = BilanView(d)
    vue.refresh()
    assert vue.kpis["net"]._value.text().startswith("+")
    assert vue.kpis["pointe"]._value.text().startswith("+")
    style = vue.kpis["pointe"]._value.styleSheet()
    assert "#18733A" not in style.upper() and "#BC3729" not in style.upper()
