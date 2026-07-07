"""Smoke tests de la couche UI.

On construit chaque vue, fenêtre et dialogue avec une base en mémoire peuplée,
puis on déclenche le rafraîchissement. But : attraper les plantages et les
erreurs de câblage (imports, signaux, calculs au refresh) sans simuler
d'interaction — rapide, headless, peu fragile.
"""
import importlib
from datetime import date, timedelta

import pytest

from comptesbudget.constants import CATEGORIES_DEFAUT
from comptesbudget.database import Database


def _tx(**kw):
    base = {
        "id": "x", "date": "2026-06-01", "date_valeur": "2026-06-01",
        "libelle": "OP", "libelle_op": "OP", "reference": "", "type": "",
        "categorie": "Non classé", "sous_cat": "", "info": "",
        "montant": -10.0, "pointee": 0,
    }
    base.update(kw)
    return base


@pytest.fixture
def db(tmp_path):
    """Base peuplée pour exercer les calculs (soldes, encours CB, alerte
    budget dépassé, graphiques, règles, récurrences)."""
    d = Database(str(tmp_path / "ui.db"))
    d.set_setting("initial_balance", "1000")     # → pas d'invite au 1er lancement
    d.set_setting("initial_date", "2026-01-01")

    today = date.today()
    first = today.replace(day=1).isoformat()
    todays = today.isoformat()
    future = (today + timedelta(days=20)).isoformat()

    d.insert_tx(_tx(id="t-sal", date=first, date_valeur=first, libelle="SALAIRE",
                    libelle_op="SALAIRE", type="Virement", categorie="Revenus",
                    montant=2000.0, pointee=1))
    d.insert_tx(_tx(id="t-cou", date=todays, date_valeur=todays, libelle="HYPERMARCHE",
                    libelle_op="HYPERMARCHE", type="Carte bancaire",
                    categorie="Alimentation", montant=-45.30, pointee=1))
    d.insert_tx(_tx(id="t-big", date=todays, date_valeur=todays, libelle="COURSES",
                    libelle_op="COURSES", type="Carte bancaire",
                    categorie="Alimentation", montant=-380.0, pointee=1))  # budget dépassé
    d.insert_tx(_tx(id="t-cb", date=todays, date_valeur=future, libelle="OMNISHOP",
                    libelle_op="OMNISHOP", type="Carte bancaire",
                    categorie="Loisirs", montant=-60.0, pointee=0))        # encours CB
    d.set_budget("Alimentation", 400.0)
    d.insert_rule({"id": "r1", "pattern": "omnishop", "amount": None,
                   "categorie": "Shopping", "sous_cat": "", "no_overwrite": 0,
                   "created_at": "2026-01-01"})
    d.insert_recurring({"id": "rec1", "libelle": "Loyer", "montant": -800.0,
                        "categorie": "Logement - maison", "sous_cat": "",
                        "type": "Prelevement", "frequency": "monthly",
                        "day_of_month": 5, "start_date": "2026-01-05",
                        "end_date": None, "actif": 1})
    return d


def test_main_window_construit(qapp, db):
    from comptesbudget.ui.main_window import MainWindow
    w = MainWindow(db)               # construit et appelle refresh_all()
    assert w.tabs.count() == 7   # la Notice n'est plus un onglet (menu de gauche)
    w.refresh_all()                  # second passage : ne doit pas lever


# (module, classe, méthode de rafraîchissement)
VIEW_SPECS = [
    ("bilan", "BilanView", "refresh"),
    ("budget", "BudgetView", "refresh"),
    ("categories", "CategoriesView", "refresh"),
    ("subcategories", "SubcategoriesView", "refresh"),
    ("operations", "OperationsView", "reload_from_db"),
    ("previsionnel", "PrevisionnelView", "refresh"),
    ("rules_view", "RulesView", "refresh"),
]


@pytest.mark.parametrize("module, cls, method", VIEW_SPECS)
def test_view_se_rafraichit(qapp, db, module, cls, method):
    mod = importlib.import_module(f"comptesbudget.ui.views.{module}")
    view = getattr(mod, cls)(db)
    getattr(view, method)()          # rafraîchissement initial — ne doit pas lever


def test_notice_view(qapp):
    from comptesbudget.ui.views.notice import NoticeView
    NoticeView()                     # vue statique : construction seule


def test_dialogs_creation_et_values(qapp, db):
    from comptesbudget.ui.dialogs import (
        RecurringDialog, RuleDialog, SettingsDialog, TxDialog,
    )
    txs = [dict(r) for r in db.list_tx()]
    cats = CATEGORIES_DEFAUT

    tx_dlg = TxDialog(None, None, categories=cats, all_transactions=txs)
    assert "montant" in tx_dlg.values()
    # Mode édition : exerce la branche de pré-remplissage
    TxDialog(None, txs[0], categories=cats, all_transactions=txs)

    assert SettingsDialog(None, "2026-01-01", 1000.0).values() == ("2026-01-01", 1000.0)
    assert "pattern" in RuleDialog(None, None, categories=cats).values()
    assert "frequency" in RecurringDialog(None, None, categories=cats, all_tx=txs).values()


def test_rapport_et_recherche(qapp, db):
    from comptesbudget.ui.report import (
        MonthlyReportDialog, build_monthly_report_html,
    )
    from comptesbudget.ui.search import GlobalSearchDialog

    month = date.today().strftime("%Y-%m")
    html = build_monthly_report_html(db, month)
    assert "<" in html and len(html) > 50

    MonthlyReportDialog(None, db)    # construction (aperçu QTextBrowser)
    GlobalSearchDialog(None, db)     # construit + indexe + recherche initiale
