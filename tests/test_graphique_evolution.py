"""Graphique « Évolution sur 12 mois » du Bilan (audit du 08/10/2026).

- Chiffres en blanc sur le vert des revenus : 3,65 pour 1, sous le seuil de
  4,5. Noir sur le vert (5,75), blanc sur le rouge (5,65).
- Série « Dépenses » au rouge des dépenses (#BC3729), et non un brun-orange
  hors palette (choix de l'auteur).
- Le mois en cours n'est pas terminé : QtCharts ne sait pas hachurer une
  seule barre ; il est marqué d'un astérisque sur l'axe, et une note le dit.
Données inventées.
"""
from datetime import date

from PySide6.QtCharts import QBarCategoryAxis

from comptesbudget.database import Database


def _vue(tmp_path, mois_en_cours=True):
    from comptesbudget.ui.views.bilan import BilanView
    d = Database(str(tmp_path / "g.db"))
    d.set_setting("initial_balance", "1000")
    d.set_setting("initial_date", "2020-01-01")
    jour = date.today().replace(day=1).isoformat()
    if mois_en_cours:
        d.insert_tx({"id": "a", "date": jour, "date_valeur": jour,
                     "libelle": "SALAIRE", "libelle_op": "SALAIRE",
                     "reference": "", "type": "Virement",
                     "categorie": "Revenus", "sous_cat": "", "info": "",
                     "montant": 2000.0, "pointee": 1})
    vue = BilanView(d)
    vue.refresh()
    return vue


def test_couleurs_et_chiffres_lisibles(qapp, tmp_path):
    vue = _vue(tmp_path)
    rev, dep = vue.bar_chart.series()[0].barSets()
    assert dep.color().name().upper() == "#BC3729"
    assert rev.labelColor().name().upper() == "#000000"
    assert dep.labelColor().name().upper() == "#FFFFFF"


def test_le_mois_en_cours_est_signale(qapp, tmp_path):
    vue = _vue(tmp_path)
    axe = next(a for a in vue.bar_chart.axes()
               if isinstance(a, QBarCategoryAxis))
    assert axe.categories()[-1].endswith("*")
    assert vue.bar_note.isVisibleTo(vue)
    assert "n'est pas terminé" in vue.bar_note.text()
