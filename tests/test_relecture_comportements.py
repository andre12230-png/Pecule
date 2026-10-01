"""Comportements (relecture de design du 30/09/2026).

Chacun de ces tests a été écrit avant la correction et vu en échec.
"""
from datetime import date

import pytest
from PySide6.QtCore import Qt

from comptesbudget.database import Database


def _tx(**kw):
    base = {"id": "x", "date": "2026-06-01", "date_valeur": "2026-06-01",
            "libelle": "OP", "libelle_op": "OP", "reference": "", "type": "",
            "categorie": "Non classé", "sous_cat": "", "info": "",
            "montant": -10.0, "pointee": 1}
    base.update(kw)
    return base


@pytest.fixture
def db(tmp_path):
    d = Database(str(tmp_path / "comportements.db"))
    d.set_setting("initial_balance", "1000")
    d.set_setting("initial_date", "2020-01-01")
    jour = date.today().replace(day=1).isoformat()
    d.insert_tx(_tx(id="a", date=jour, date_valeur=jour, categorie="Alimentation",
                    sous_cat="Courses", libelle="Courses", montant=-50.0))
    return d


# ── Sélecteur de période ────────────────────────────────────────────────

SANS_PERIODE = ("subs_view", "rules_view", "prev_view")


def test_periode_grisee_la_ou_elle_ne_sert_pas(qapp, db):
    """Charte : « Un onglet où la période n'a pas de sens grise le sélecteur
    avec une infobulle qui le dit. » Sous-catégories affichait les totaux de
    tout l'historique sous « Septembre 2026 »."""
    from comptesbudget.ui.main_window import MainWindow
    w = MainWindow(db)
    barre = w.period_bar
    for nom in SANS_PERIODE:
        w.tabs.setCurrentWidget(getattr(w, nom))
        assert not barre.annee_combo.isEnabled(), nom
        assert not barre.prev_btn.isEnabled(), nom
        assert "pas d'effet" in barre.annee_combo.toolTip(), nom
        # Les raccourcis ne changent pas la période en douce.
        avant = barre.current_period()
        barre._decaler(-1)
        assert barre.current_period() == avant, nom
    w.tabs.setCurrentWidget(w.ops_view)
    assert barre.annee_combo.isEnabled()
    assert "pas d'effet" not in barre.annee_combo.toolTip()


def test_choix_de_la_date_grise_sur_le_budget(qapp, db):
    """Le Budget compte toujours à la date d'achat : le menu « Date » n'y a
    pas d'effet, il le dit."""
    from comptesbudget.ui.main_window import MainWindow
    w = MainWindow(db)
    w.tabs.setCurrentWidget(w.budget_view)
    assert w.period_bar.annee_combo.isEnabled()
    assert not w.period_bar.date_mode_combo.isEnabled()
    assert "date d'achat" in w.period_bar.date_mode_combo.toolTip()
    w.tabs.setCurrentWidget(w.bilan_view)
    assert w.period_bar.date_mode_combo.isEnabled()


# ── États vides ─────────────────────────────────────────────────────────

def _phrases_visibles(vue):
    from PySide6.QtWidgets import QLabel
    return [lbl.text() for lbl in vue.findChildren(QLabel, "etatVide")
            if not lbl.isHidden() and lbl.text()]


def _vues_rafraichies(base):
    from comptesbudget.ui.views.bilan import BilanView
    from comptesbudget.ui.views.budget import BudgetView
    from comptesbudget.ui.views.categories import CategoriesView
    from comptesbudget.ui.views.operations import OperationsView
    from comptesbudget.ui.views.previsionnel import PrevisionnelView
    from comptesbudget.ui.views.rules_view import RulesView
    from comptesbudget.ui.views.subcategories import SubcategoriesView
    vues = {"Bilan": BilanView(base), "Opérations": OperationsView(base),
            "Budget": BudgetView(base), "Catégories": CategoriesView(base),
            "Sous-catégories": SubcategoriesView(base),
            "Règles auto": RulesView(base), "Prévisionnel": PrevisionnelView(base)}
    for vue in vues.values():
        (vue.reload_from_db if hasattr(vue, "reload_from_db") else vue.refresh)()
    return vues


def test_etats_vides_disent_pourquoi_et_comment_commencer(qapp, tmp_path):
    """Charte : « un tableau ou une page sans données affiche une phrase
    centrée, en gris discret, qui dit pourquoi » ; le plugin Design ajoute :
    et comment commencer. Les onglets montraient des grilles vides et des
    graphiques aux axes « … »."""
    vues = _vues_rafraichies(Database(str(tmp_path / "vide.db")))
    for nom, vue in vues.items():
        assert _phrases_visibles(vue), f"{nom} : grille vide sans phrase"
    assert any("Importez" in p for p in _phrases_visibles(vues["Opérations"]))
    assert any("Pré-remplir" in p for p in _phrases_visibles(vues["Prévisionnel"]))


def test_etats_vides_disparaissent_avec_les_donnees(qapp, db):
    vues = _vues_rafraichies(db)
    for nom in ("Opérations", "Sous-catégories"):
        assert not _phrases_visibles(vues[nom]), nom


# ── Cases à cocher des assistants ───────────────────────────────────────

def _assistants(db):
    from comptesbudget.ui.assistants import (
        DuplicatesDialog, GenererEcheancesDialog, HarmonizeDialog,
        HarmonizeLabelsDialog, PrefillRecurringDialog,
    )
    txs = [dict(r) for r in db.list_tx()]
    candidat = {"libelle": "Loyer", "categorie": "Logement - maison",
                "montant": -800.0, "frequency": "monthly", "day_of_month": 5,
                "_months": 6, "_min": -800.0, "_max": -800.0, "_stable": True,
                "_default": True, "sous_cat": "", "type": ""}
    echeance = {"date": date.today().isoformat(), "libelle": "Loyer",
                "montant": -800.0, "categorie": "Logement - maison",
                "sous_cat": "", "type": "", "_deja": False, "_default": True,
                "_passee": False}
    libelle = {"old": "COURSES 123", "new": "Courses", "n": 1,
               "tx_ids": ["a"], "rec_ids": []}
    mois = date.today().strftime("%Y-%m")
    return {
        "Suggérer catégories": HarmonizeDialog(None, [(txs[0], "Shopping")]),
        "Doublons": DuplicatesDialog(None, txs),
        "Pré-remplir": PrefillRecurringDialog(None, [candidat]),
        "Échéances": GenererEcheancesDialog(None, lambda _m: [echeance], mois, [mois]),
        "Harmoniser libellés": HarmonizeLabelsDialog(None, [libelle]),
    }


def test_assistants_ont_de_vraies_cases_a_cocher(qapp, db):
    """Un ✔ écrit dans une cellule, et une cellule vide une fois décochée :
    rien ne montrait qu'on pouvait cliquer, et le clavier ne cochait rien.
    Ce sont maintenant des cases de Qt (clic, barre d'espace)."""
    from PySide6.QtTest import QTest
    for nom, dlg in _assistants(db).items():
        it = dlg.model.item(0, 0)
        assert it.isCheckable(), nom
        assert it.text() != "✔", nom
        assert it.checkState() == Qt.Checked, nom
        assert dlg.selected(), nom
        # Au clavier : la barre d'espace décoche la ligne courante.
        dlg.table.setCurrentIndex(dlg.model.index(0, 0))
        QTest.keyClick(dlg.table, Qt.Key_Space)
        assert it.checkState() == Qt.Unchecked, f"{nom} : Espace sans effet"
        assert not dlg.selected(), nom
        dlg._set_all(True)
        assert dlg.selected(), nom


def _pixels_de_contour(widget) -> int:
    """Nombre de pixels de la couleur de contour de la charte (#6F7885)
    dans le rendu du widget."""
    from PySide6.QtGui import QColor
    img = widget.grab().toImage()
    cible = QColor("#6F7885")
    n = 0
    for x in range(img.width()):
        for y in range(img.height()):
            c = img.pixelColor(x, y)
            if (abs(c.red() - cible.red()) < 12 and abs(c.green() - cible.green()) < 12
                    and abs(c.blue() - cible.blue()) < 12):
                n += 1
    return n


def test_case_decochee_a_un_contour_visible(qapp):
    """Sous le style Fusion, une case décochée n'avait qu'un contour pâle,
    invisible dans les listes. Charte : ce qu'on clique tient 3 pour 1 —
    contour #6F7885."""
    from PySide6.QtWidgets import QCheckBox, QRadioButton
    from comptesbudget.app import appliquer_theme_clair
    appliquer_theme_clair(qapp)
    for widget in (QCheckBox(), QRadioButton()):
        widget.resize(20, 20)
        assert _pixels_de_contour(widget) >= 12, type(widget).__name__


# ── Un nom par chose ────────────────────────────────────────────────────

def test_operations_parlent_de_mouvement_pas_de_solde(qapp, db):
    """Le compteur des Opérations appelait « solde » la somme des opérations
    affichées, que le Bilan appelle « mouvement »."""
    from comptesbudget.ui.views.operations import OperationsView
    vue = OperationsView(db)
    vue.reload_from_db()
    texte = vue.lbl_count.text()
    assert "solde" not in texte.lower(), texte
    assert "mouvement" in texte.lower(), texte


def test_rapport_dit_a_quelle_date_il_compte(qapp, db):
    """Le Rapport compte à la date d'achat, le Bilan à la date de valeur :
    deux « mouvements » différents pour le même mois, sans explication."""
    from comptesbudget.ui.report import build_monthly_report_html
    html = build_monthly_report_html(db, date.today().strftime("%Y-%m"))
    assert "date d'achat" in html
    assert "Mouvement du mois" in html
    assert "Mouvement net" not in html
