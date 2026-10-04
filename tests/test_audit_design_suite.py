"""Suite de l'audit de design du 04/10/2026 : les écarts de second rang.

Chacun de ces tests a été écrit avant la correction et vu en échec.
"""
from datetime import date

import pytest
from PySide6.QtCore import Qt

from comptesbudget.database import Database


def _tx(**kw):
    jour = date.today().replace(day=1).isoformat()
    base = {"id": "x", "date": jour, "date_valeur": jour,
            "libelle": "OP", "libelle_op": "OP", "reference": "", "type": "",
            "categorie": "Alimentation", "sous_cat": "", "info": "",
            "montant": -10.0, "pointee": 1}
    base.update(kw)
    return base


@pytest.fixture
def db(tmp_path):
    d = Database(str(tmp_path / "suite.db"))
    d.set_setting("initial_balance", "1000")
    d.set_setting("initial_date", "2020-01-01")
    return d


def test_regles_categorie_avec_pastille(qapp, db):
    """Partout ailleurs, une catégorie a sa pastille de couleur ; la fenêtre
    des Règles automatiques écrivait le nom seul."""
    from comptesbudget.ui.views.rules_view import RulesView
    db.insert_rule({"id": "g1", "pattern": "courses", "amount": None,
                    "categorie": "Alimentation", "sous_cat": "",
                    "no_overwrite": 0, "created_at": "2026-01-01"})
    vue = RulesView(db)
    vue.refresh()
    entetes = [vue.model.headerData(c, Qt.Horizontal)
               for c in range(vue.model.columnCount())]
    cellule = vue.model.item(0, entetes.index("Catégorie"))
    assert cellule.text() == "Alimentation"
    assert not cellule.icon().isNull()


def test_rapport_un_zero_sans_couleur(db):
    """Charte : un bilan nul s'écrit sans couleur. Le Rapport mensuel écrivait
    « 0 % » en vert gras pour un budget pas encore entamé."""
    import re
    from comptesbudget.ui.report import build_monthly_report_html
    mois = date.today().strftime("%Y-%m")
    db.insert_tx(_tx(id="a", categorie="Alimentation", montant=-50.0))
    db.set_budget("Alimentation", 100.0)
    db.set_budget("Transports", 80.0)          # rien de dépensé
    html = build_monthly_report_html(db, mois)
    ligne = re.search(r"<tr[^>]*><td>Transports</td>.*?</tr>", html).group(0)
    assert "0&nbsp;%" in ligne
    assert "#18733A" not in ligne                # ni le % ni le reste en vert
    # Un budget entamé garde son repère de couleur.
    ligne = re.search(r"<tr[^>]*><td>Alimentation</td>.*?</tr>", html).group(0)
    assert "50&nbsp;%" in ligne


def test_case_de_montant_separe_les_milliers(qapp):
    """« 1850,00 € » dans la case, « 1 850,00 € » partout ailleurs."""
    import re
    from comptesbudget.ui.widgets import MontantSpinBox
    champ = MontantSpinBox()
    champ.setRange(0, 1_000_000)
    champ.setDecimals(2)
    champ.setValue(1850.0)
    assert re.fullmatch(r"1\s850,00", champ.cleanText()), champ.cleanText()
    # La saisie reste libre : avec ou sans espace, le montant est compris.
    for tape in ("1850,00", "1 850,00", "1 850,00", "1.850,00"):
        assert champ.valueFromText(tape) == 1850.0, tape


def test_categories_sans_grand_vide(qapp, db):
    """Les deux tableaux s'arrêtaient à mi-hauteur et la note sur la date,
    posée tout en bas, en restait séparée par un grand vide : la place libre
    allait à la note au lieu des tableaux."""
    from comptesbudget.ui.views.categories import CategoriesView
    db.insert_tx(_tx(id="a"))
    vue = CategoriesView(db)
    vue.setAttribute(Qt.WA_DontShowOnScreen, True)
    vue.resize(1100, 800)
    vue.show()
    vue.refresh()
    for _ in range(5):
        qapp.processEvents()
    note = vue.info_date
    # La note ne prend que la hauteur de son texte…
    assert note.height() <= note.heightForWidth(note.width()) + 12
    # … et les tableaux tout le reste.
    assert vue.cats_table.height() >= 800 * 0.7


def _lignes_du_formulaire(dlg):
    """Les intitulés du formulaire, dans l'ordre de l'écran."""
    from PySide6.QtWidgets import QFormLayout, QLabel
    form = dlg.findChild(QFormLayout)
    textes = []
    for i in range(form.rowCount()):
        item = form.itemAt(i, QFormLayout.LabelRole)
        if item and isinstance(item.widget(), QLabel) and item.widget().text():
            textes.append(item.widget().text())
    return textes


def test_saisie_recurrente_alignee_sur_la_saisie_d_operation(qapp):
    """Les deux fenêtres se ressemblaient sans être pareilles : Sous-catégorie
    était une liste d'un côté et une case libre de l'autre, Type venait avant
    ou après la catégorie, et le sens se disait « Débit (sortie) » ou
    « Débit »."""
    from PySide6.QtWidgets import QComboBox
    from comptesbudget.ui.dialogs import RecurringDialog, TxDialog
    historique = [_tx(id="a", categorie="Alimentation", sous_cat="Courses"),
                  _tx(id="b", categorie="Transports", sous_cat="Carburant")]
    op = TxDialog(None, None, ["Alimentation", "Transports"], historique)
    rec = RecurringDialog(None, None, ["Alimentation", "Transports"], historique)

    assert rec.rb_debit.text() == op.rb_debit.text()
    assert rec.rb_credit.text() == op.rb_credit.text()

    def ordre(dlg):
        lignes = _lignes_du_formulaire(dlg)
        return [l for l in lignes if l in ("Type :", "Catégorie :", "Sous-catégorie :")]
    assert ordre(rec) == ordre(op) == ["Type :", "Catégorie :", "Sous-catégorie :"]

    # Sous-catégorie : une liste, filtrée par la catégorie choisie.
    assert isinstance(rec.sous_cat, QComboBox)
    rec.cat.setCurrentText("Transports")
    proposees = [rec.sous_cat.itemText(i) for i in range(rec.sous_cat.count())]
    assert proposees == ["Carburant"]
    rec.sous_cat.setCurrentText("Péage")       # texte libre toujours permis
    rec.libelle.setText("Autoroute")
    assert rec.values()["sous_cat"] == "Péage"


def test_libelle_lisible_a_la_largeur_minimale(qapp, db):
    """À la largeur minimale de la fenêtre (1082 px), le Libellé tombait à
    32 px (« St… ») : Catégorie, Sous-catégorie et Type gardaient 170, 140 et
    150 px fixés à la main, bien plus que leur contenu."""
    from comptesbudget.ui.views.operations import OperationsView
    db.insert_tx(_tx(id="a", libelle="Station Total", categorie="Transports",
                     sous_cat="Carburant", type="Carte bancaire"))
    vue = OperationsView(db)
    vue.period = "all"
    vue.setAttribute(Qt.WA_DontShowOnScreen, True)
    vue.resize(1082 - 184, 700)           # la fenêtre moins le menu de gauche
    vue.show()
    vue.reload_from_db()
    for _ in range(5):
        qapp.processEvents()
    t = vue.table
    h = t.horizontalHeader()
    noms = [t.model().headerData(c, Qt.Horizontal) for c in range(h.count())]
    assert h.sectionSize(noms.index("Libellé")) >= 100
    # Aucune autre colonne n'est coupée pour autant.
    for nom in ("Catégorie", "Sous-catégorie", "Type", "Débit", "Crédit"):
        c = noms.index(nom)
        assert h.sectionSize(c) >= t.sizeHintForColumn(c), nom
