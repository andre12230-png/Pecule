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
