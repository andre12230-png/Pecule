"""Arrondi des cartes et des tuiles : 12 px dans les trois applis.

Choix de l'auteur du 06/10/2026 : les cartes gardent l'arrondi du
Photovoltaïque (12 px) ; boutons, bandeaux et menus gardent 4 px. Écrits
avant la correction et vus en échec.
"""
import re

import pytest

from comptesbudget.database import Database


def _rayons(feuille: str, objet: str) -> list[str]:
    """Les border-radius de la règle « QFrame#<objet> { … } »."""
    regle = re.search(r"QFrame#%s\s*\{([^}]*)\}" % objet, feuille)
    assert regle, f"pas de règle QFrame#{objet}"
    return re.findall(r"border-radius:\s*(\d+)px", regle.group(1))


@pytest.fixture
def bilan(qapp, tmp_path):
    from comptesbudget.ui.views.bilan import BilanView
    d = Database(str(tmp_path / "arrondi.db"))
    d.set_setting("initial_balance", "1000")
    d.set_setting("initial_date", "2020-01-01")
    vue = BilanView(d)
    yield vue
    vue.deleteLater()


def test_cartes_du_bilan_a_12_px(bilan):
    from PySide6.QtWidgets import QFrame
    cartes = [f for f in bilan.findChildren(QFrame) if f.objectName() == "carteBilan"]
    assert cartes
    for carte in cartes:
        assert _rayons(carte.styleSheet(), "carteBilan") == ["12"]


def test_entete_de_carte_suit_l_arrondi(bilan):
    """Sans arrondi propre, le bandeau bleu du titre dépassait de la carte
    dans ses deux coins du haut."""
    from PySide6.QtWidgets import QFrame
    carte = next(f for f in bilan.findChildren(QFrame) if f.objectName() == "carteBilan")
    entete = carte._header.styleSheet()
    assert re.search(r"border-top-left-radius:\s*11px", entete)
    assert re.search(r"border-top-right-radius:\s*11px", entete)


def test_tuiles_a_12_px(bilan):
    assert bilan.kpis
    for tuile in bilan.kpis.values():
        assert _rayons(tuile.styleSheet(), "tuileKpi") == ["12"]
    # Recolorée après un calcul, la tuile garde son arrondi.
    cle = next(iter(bilan.kpis))
    bilan._colorer_kpi(cle, "#18733A")
    assert _rayons(bilan.kpis[cle].styleSheet(), "tuileKpi") == ["12"]
