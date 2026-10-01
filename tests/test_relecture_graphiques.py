"""Graphiques du Bilan (relecture de design du 30/09/2026).

Écrits avant la correction et vus en échec.
"""
from datetime import date, timedelta

import pytest

from comptesbudget.database import Database


@pytest.mark.parametrize("bas, haut, attendu", [
    (0, 2618, [0, 1000, 2000, 3000]),
    (2000, 12000, [2000, 4000, 6000, 8000, 10000, 12000]),
    (-350, 900, [-500, 0, 500, 1000]),
    (0, 100, [0, 20, 40, 60, 80, 100]),
])
def test_graduations_rondes(bas, haut, attendu):
    """L'axe des montants tombait sur 654, 1309, 1963, 2618."""
    from comptesbudget.ui.views.bilan import graduations_euros
    valeurs = [v for v, _t in graduations_euros(bas, haut)]
    assert valeurs == attendu


def test_graduations_en_euros_milliers_separes():
    from comptesbudget.ui.views.bilan import graduations_euros
    assert graduations_euros(0, 100)[0][1] == "0\xa0€"
    textes = [t for _v, t in graduations_euros(2000, 12000)]
    assert "12\xa0000\xa0€" in textes


def _tx(**kw):
    base = {"id": "x", "date": "2026-06-01", "date_valeur": "2026-06-01",
            "libelle": "OP", "libelle_op": "OP", "reference": "", "type": "",
            "categorie": "Non classé", "sous_cat": "", "info": "",
            "montant": -10.0, "pointee": 1}
    base.update(kw)
    return base


@pytest.fixture
def bilan(qapp, tmp_path):
    from comptesbudget.ui.views.bilan import BilanView
    d = Database(str(tmp_path / "graphiques.db"))
    d.set_setting("initial_balance", "1000")
    d.set_setting("initial_date", "2020-01-01")
    jour = date.today().replace(day=1)
    cats = ["Alimentation", "Transports", "Loisirs", "Santé", "Shopping",
            "Abonnements", "Famille", "Impôts et taxes", "Cadeaux et dons"]
    for i in range(12):
        j = (jour - timedelta(days=31 * i)).replace(day=2).isoformat()
        d.insert_tx(_tx(id=f"r{i}", date=j, date_valeur=j, categorie="Revenus",
                        montant=2618.0))
        for k, c in enumerate(cats):
            d.insert_tx(_tx(id=f"d{i}-{k}", date=j, date_valeur=j, categorie=c,
                            montant=-(50.0 + 10 * k)))
    vue = BilanView(d)
    vue.period = jour.strftime("%Y-%m")
    vue.refresh()
    return vue


def test_axes_des_montants_en_euros(bilan):
    from PySide6.QtCharts import QCategoryAxis
    from PySide6.QtCore import Qt
    for graphique in (bilan.bar_chart, bilan.solde_chart):
        axes = graphique.axes(Qt.Vertical)
        assert axes and isinstance(axes[0], QCategoryAxis), graphique
        assert all(t.endswith("\xa0€") for t in axes[0].categoriesLabels())
        # Qt remplaçait les étiquettes par « … » dès que le graphique
        # manquait un peu de hauteur.
        assert not axes[0].truncateLabels()


def test_legende_du_camembert_a_la_hauteur_de_ses_lignes(bilan):
    """Neuf catégories : la dernière ligne de la légende était rognée."""
    from PySide6.QtGui import QFontMetrics
    legende = bilan.pie_chart.legend()
    n = len(legende.markers())
    assert n == 9
    # Une ligne de légende : le texte, plus son espacement (marqueur, marges).
    ligne = QFontMetrics(legende.font()).height() + 10
    assert bilan.pie_view.minimumHeight() >= n * ligne + 60


def test_mois_de_l_axe_en_8_points(bilan):
    """Les mois se coupaient (« N… », « A… ») ; charte : jamais sous 8 pt."""
    from PySide6.QtCore import Qt
    axe_x = bilan.bar_chart.axes(Qt.Horizontal)[0]
    assert axe_x.labelsFont().pointSize() == 8
