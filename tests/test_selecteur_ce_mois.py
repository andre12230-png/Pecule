"""Sélecteur de période : bouton « Ce mois-ci », raccourcis clavier, et le
même sélecteur dans le rapport mensuel (demande du 23/09/2026).

Après être allé voir un mois passé, il fallait rouvrir les deux menus pour
revenir au mois en cours. Le rapport mensuel, lui, n'avait qu'une longue
liste « Mois », sans flèches.
"""
from datetime import date

from PySide6.QtGui import QKeySequence

from comptesbudget.database import Database
from comptesbudget.utils import MOIS_TOUS


def _barre(**options):
    from comptesbudget.ui.widgets import PeriodBar
    courant = date.today().strftime("%Y-%m")
    barre = PeriodBar(**options)
    barre.update_periods([
        {"date": "2025-05-10", "date_valeur": "2025-05-10"},
        {"date": "2026-01-10", "date_valeur": "2026-01-10"},
        {"date": "2026-05-10", "date_valeur": "2026-05-10"},
        {"date": f"{courant}-01", "date_valeur": f"{courant}-01"}])
    return barre, courant


def _raccourci(barre, touches: str):
    """Le raccourci clavier de la barre qui porte ces touches."""
    return next(s for s in barre.raccourcis
                if s.key() == QKeySequence(touches))


# ── Bouton « Ce mois-ci » ──────────────────────────────────────────────────

def test_ce_mois_ci_ramene_au_mois_en_cours(qapp):
    barre, courant = _barre()
    barre._appliquer("2025-05")
    assert barre.btn_ce_mois.isEnabled()
    barre.btn_ce_mois.click()
    assert barre.current_period() == courant


def test_ce_mois_ci_depuis_toutes_periodes(qapp):
    barre, courant = _barre()
    barre._appliquer("all")
    barre.btn_ce_mois.click()
    assert barre.current_period() == courant


def test_ce_mois_ci_grise_quand_on_y_est(qapp):
    # Grisé, il dit aussi qu'on regarde bien le mois en cours.
    barre, courant = _barre()
    assert barre.current_period() == courant
    assert not barre.btn_ce_mois.isEnabled()


# ── Raccourcis clavier ─────────────────────────────────────────────────────

def test_raccourcis_mois_precedent_suivant_et_ce_mois(qapp):
    barre, courant = _barre()
    barre._appliquer("2026-05")
    _raccourci(barre, "Ctrl+Left").activated.emit()
    assert barre.current_period() == "2026-01"
    _raccourci(barre, "Ctrl+Right").activated.emit()
    assert barre.current_period() == "2026-05"
    _raccourci(barre, "Ctrl+Home").activated.emit()
    assert barre.current_period() == courant


# ── Version « mois seulement », pour le rapport mensuel ───────────────────

def test_mois_seulement_ni_toutes_periodes_ni_annee_entiere(qapp):
    barre, _ = _barre(mois_seulement=True)
    annees = [barre.annee_combo.itemData(i) for i in range(barre.annee_combo.count())]
    mois = [barre.mois_combo.itemData(i) for i in range(barre.mois_combo.count())]
    assert "all" not in annees
    assert MOIS_TOUS not in mois
    # Ni mode de date ni case d'archives : le rapport a les siens.
    assert not barre.date_mode_combo.isVisibleTo(barre)
    assert not barre.archives_check.isVisibleTo(barre)


def test_mois_seulement_changer_dannee_sans_ce_mois_la(qapp):
    # Mai 2026 → 2025 : mai existe, on le garde. Janvier 2026 → 2025 : pas de
    # janvier en 2025, on prend son mois le plus récent, jamais l'année entière.
    barre, _ = _barre(mois_seulement=True)
    barre._appliquer("2026-05")
    barre.annee_combo.setCurrentIndex(barre.annee_combo.findData("2025"))
    assert barre.current_period() == "2025-05"
    barre._appliquer("2026-01")
    barre.annee_combo.setCurrentIndex(barre.annee_combo.findData("2025"))
    assert barre.current_period() == "2025-05"


# ── Le rapport mensuel utilise ce sélecteur ────────────────────────────────

def _base(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.set_solde_initial(0.0, "2025-01-01")
    for i, d in enumerate(("2025-05-10", "2026-01-15", "2026-05-15")):
        db.insert_tx({
            "id": f"op{i}", "date": d, "date_valeur": d, "libelle": "ACHAT",
            "libelle_op": "", "reference": "", "type": "Prelevement",
            "categorie": "Alimentation", "sous_cat": "", "info": "",
            "montant": -10.0, "pointee": 1})
    return db


def test_rapport_fleches_et_ce_mois(qapp, tmp_path):
    from comptesbudget.ui.report import MonthlyReportDialog
    dlg = MonthlyReportDialog(None, _base(tmp_path), "2026-05")
    assert dlg.current_month() == "2026-05"
    dlg.periode.prev_btn.click()
    assert dlg.current_month() == "2026-01"
    assert "Janvier 2026" in dlg.browser.toPlainText()
    dlg.periode.btn_ce_mois.click()
    assert dlg.current_month() == date.today().strftime("%Y-%m")


def test_mois_seulement_se_construit_sans_erreur(qapp):
    # Choisir la date d'opération dans cette version déclenchait, avant que la
    # barre soit prête, une erreur que Qt se contentait d'afficher.
    import sys
    erreurs = []
    ancien = sys.excepthook
    sys.excepthook = lambda *e: erreurs.append(e)
    try:
        from comptesbudget.ui.widgets import PeriodBar
        barre = PeriodBar(mois_seulement=True)
    finally:
        sys.excepthook = ancien
    assert not erreurs
    assert barre.current_date_mode() == "operation"
