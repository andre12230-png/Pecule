"""Audit du 14/10/2026, lot 4 : l'affichage.

A10 — le texte d'exemple du champ de recherche (onglet Opérations) était
      coupé : 275 pixels de texte pour un champ de 260. Il tient désormais
      dans le champ, et le détail est dans une infobulle.

A09 (axes du Bilan superposés après plusieurs changements de période) n'est
pas couvert ici : il ne se reproduit pas avec la vraie boucle d'événements
de Qt, même en changeant de période toutes les 60 ms ; la superposition vue
par l'audit venait de sa façon de piloter Qt (voir JOURNAL.md, 14/10/2026).
"""

from comptesbudget.database import Database


def test_le_texte_d_exemple_de_la_recherche_tient(qapp, tmp_path):
    """Les tests tournent sans les polices de Windows (Qt « offscreen ») :
    une largeur en pixels n'y veut rien dire. On borne donc le nombre de
    caractères. Mesuré avec la vraie police le 14/10/2026 : 44 caractères
    faisaient 275 px (coupé), « Libellé, montant (45,30), date… » (31
    caractères) en fait 189, dans un champ de 260 px."""
    from comptesbudget.ui.views.operations import OperationsView
    vue = OperationsView(Database(str(tmp_path / "comptes.db")))
    assert len(vue.search.placeholderText()) <= 34
    assert vue.search.width() == 260


def test_la_recherche_explique_ce_qu_elle_cherche(qapp, tmp_path):
    from comptesbudget.ui.views.operations import OperationsView
    vue = OperationsView(Database(str(tmp_path / "comptes.db")))
    bulle = vue.search.toolTip()
    assert "12/05/2026" in bulle and "45,30" in bulle and "Ctrl+F" in bulle
