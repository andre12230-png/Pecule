"""Deux choix d'André après l'audit du 23/09/2026.

1. Mettre de côté n'est pas dépenser. Un virement vers le livret, classé
   « Épargne », comptait comme une dépense : il faisait BAISSER le taux
   d'épargne (50 % au lieu de 65 % ci-dessous). Il sort désormais des
   analyses (taux, graphiques, répartition) ; la tuile « Mouvement », qui dit
   ce qui a bougé sur le compte, le garde.

2. Un remboursement vient en déduction de sa catégorie dans le Budget : un
   achat de 60 € remboursé 30 € a coûté 30 €, pas 60. Jamais sous zéro : un
   mois où la catégorie a plus reçu que dépensé compte pour 0.
"""
import re
from datetime import date

from comptesbudget.database import Database
from comptesbudget.utils import depense_nette_par_categorie, fmt_euro


MOIS = date.today().strftime("%Y-%m")
JOUR = date.today().isoformat()


def _tx(id_, montant, categorie, libelle="TEST"):
    return {"id": id_, "date": JOUR, "date_valeur": JOUR, "libelle": libelle,
            "libelle_op": libelle, "reference": "", "type": "",
            "categorie": categorie, "sous_cat": "", "info": "",
            "montant": montant, "pointee": 1}


def _base_epargne(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.set_solde_initial(0.0, "2020-01-01")
    db.insert_tx(_tx("sal", 2000.0, "Revenus", "SALAIRE"))
    db.insert_tx(_tx("loy", -700.0, "Logement - maison", "LOYER"))
    db.insert_tx(_tx("liv", -300.0, "Épargne", "VIR LIVRET A"))
    return db


def _texte(label):
    return re.sub("<[^>]+>", "", label.text())


# ── 1. L'épargne n'est pas une dépense ──────────────────────────────────────

def test_bilan_taux_d_epargne_compte_le_livret_comme_epargne(qapp, tmp_path):
    from comptesbudget.ui.views.bilan import BilanView
    v = BilanView(_base_epargne(tmp_path))
    v.period = MOIS
    v.refresh()
    # (2 000 − 700) / 2 000 : les 300 € du livret sont mis de côté.
    assert v.kpis["epargne"]._value.text() == "65,0 %"
    # Le mouvement du compte, lui, garde tout ce qui est sorti.
    assert fmt_euro(1000.0) in _texte(v.kpis["net"]._sub)
    parts = [s.label() for s in v.pie_chart.series()[0].slices()]
    assert parts and not any("Épargne" in p for p in parts)


def test_rapport_taux_d_epargne_et_ligne_mis_de_cote(tmp_path):
    from comptesbudget.ui.report import build_monthly_report_html
    html = build_monthly_report_html(_base_epargne(tmp_path), MOIS)
    assert "65,0&nbsp;%" in html
    assert "Mis de côté" in html
    # Ni dans les dépenses par catégorie, ni dans les plus grosses dépenses.
    assert html.count("Épargne") == 1


# ── 2. Les remboursements viennent en déduction dans le Budget ──────────────

def test_depense_nette_par_categorie():
    txs = [_tx("a", -60.0, "Shopping"), _tx("b", 30.0, "Shopping"),
           _tx("c", -55.0, "Famille"), _tx("d", 900.0, "Famille"),
           _tx("e", -20.0, "Transaction exclue"), _tx("f", 2000.0, "Revenus")]
    assert depense_nette_par_categorie(txs) == {"Shopping": 30.0}


def test_onglet_budget_deduit_le_remboursement(qapp, tmp_path):
    from comptesbudget.ui.views.budget import BudgetView
    db = Database(str(tmp_path / "t.db"))
    db.insert_tx(_tx("a", -60.0, "Shopping", "AMAZON"))
    db.insert_tx(_tx("b", 30.0, "Shopping", "AMAZON REMBOURSEMENT"))
    db.set_budget("Shopping", 50.0)
    v = BudgetView(db)
    v.period = MOIS
    v.refresh()
    ligne = next(r for r in range(v.model.rowCount())
                 if v.model.item(r, 0).text() == "Shopping")
    assert v.model.item(ligne, 2).text() == fmt_euro(30.0)
    assert v.model.item(ligne, 4).text() == fmt_euro(20.0)


def test_rapport_budgets_du_mois_deduit_le_remboursement(tmp_path):
    from comptesbudget.ui.report import build_monthly_report_html
    db = Database(str(tmp_path / "t.db"))
    db.insert_tx(_tx("a", -60.0, "Shopping", "AMAZON"))
    db.insert_tx(_tx("b", 30.0, "Shopping", "AMAZON REMBOURSEMENT"))
    db.set_budget("Shopping", 50.0)
    html = build_monthly_report_html(db, MOIS)
    assert "60&nbsp;%" in html            # 30 / 50, et non 120 %


def test_bandeau_budget_depasse_deduit_le_remboursement(qapp, tmp_path):
    from comptesbudget.ui.views.bilan import BilanView
    db = Database(str(tmp_path / "t.db"))
    db.insert_tx(_tx("a", -60.0, "Shopping", "AMAZON"))
    db.insert_tx(_tx("b", 30.0, "Shopping", "AMAZON REMBOURSEMENT"))
    db.set_budget("Shopping", 50.0)
    v = BilanView(db)
    v.period = MOIS
    v.refresh()
    # 30 € sur 50 : ni dépassé, ni proche (85 %) — pas de bandeau.
    assert not v.budget_alert.isVisibleTo(v)
