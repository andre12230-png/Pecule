"""Audit du 14/10/2026, lot 3 : les calculs.

A04 — le Budget déduisait un remboursement de la catégorie de l'achat, mais
      le Bilan et le rapport le comptaient comme un revenu. Salaire 1 000 €,
      achat 200 €, remboursement 100 € : 81,8 % d'épargne affichés au lieu de
      90 %. Règle retenue, la même partout : sur la période, chaque catégorie
      fait son total ; négatif, c'est une dépense nette ; positif, un revenu
      net. Le mouvement total ne change jamais.
A05 — l'alerte de découvert partait de demain et oubliait ce qui doit encore
      passer aujourd'hui.
Données inventées.
"""
from datetime import date

import pytest

from comptesbudget.database import Database
from comptesbudget.utils import revenus_et_depenses_nets

AUJ = date.today()
MOIS = AUJ.strftime("%Y-%m")
JOUR = AUJ.replace(day=1).isoformat()


def _op(id_, montant, categorie, jour=JOUR, pointee=1, libelle=None):
    return {"id": id_, "date": jour, "date_valeur": jour,
            "libelle": libelle or id_.upper(), "libelle_op": libelle or id_.upper(),
            "reference": "", "type": "", "categorie": categorie,
            "sous_cat": "", "info": "", "montant": montant, "pointee": pointee}


EXEMPLE = [_op("salaire", 1000.0, "Revenus"),
           _op("achat", -200.0, "Alimentation"),
           _op("rembt", 100.0, "Alimentation")]


# ─────────────────────────── A04 : la règle ────────────────────────────────

def test_exemple_de_l_audit():
    assert revenus_et_depenses_nets(EXEMPLE) == (1000.0, -100.0)


def test_une_categorie_qui_recoit_plus_qu_elle_ne_depense():
    """Des apports classés dans une catégorie de dépense, plus forts que ses
    dépenses du mois : l'excédent reste un revenu, rien ne se perd."""
    ops = [_op("salaire", 1000.0, "Revenus"),
           _op("apport", 800.0, "Famille"),
           _op("cadeau", -300.0, "Famille")]
    assert revenus_et_depenses_nets(ops) == (1500.0, 0.0)


def test_le_mouvement_total_ne_change_pas():
    ops = EXEMPLE + [_op("loyer", -650.0, "Logement - maison"),
                     _op("prime", 40.0, "Santé"), _op("pharma", -15.0, "Santé")]
    rev, dep = revenus_et_depenses_nets(ops)
    assert round(rev + dep, 2) == round(sum(o["montant"] for o in ops), 2)


def test_transaction_exclue_ne_compte_pas():
    ops = EXEMPLE + [_op("recap", -999.0, "Transaction exclue")]
    assert revenus_et_depenses_nets(ops) == (1000.0, -100.0)


# ─────────────────────────── A04 : les écrans ──────────────────────────────

@pytest.fixture
def base(tmp_path):
    db = Database(str(tmp_path / "comptes.db"))
    db.set_setting("initial_date", "2020-01-01")
    db.set_setting("initial_balance", "100.0")
    for o in EXEMPLE:
        db.insert_tx(o)
    return db


def test_bilan(qapp, base):
    from comptesbudget.ui.views.bilan import BilanView
    vue = BilanView(base)
    vue.period = MOIS
    vue.refresh()
    assert vue.kpis["epargne"]._value.text().startswith("90,0")
    # Le camembert et la liste des dépenses : 100 € nets d'alimentation.
    parts = {s.label().split(" — ")[0]: s.value()
             for s in vue.pie_chart.series()[0].slices()}
    assert parts == {"Alimentation": 100.0}
    # Le graphique des douze mois : 1 000 de revenus, 100 de dépenses.
    barres = vue.bar_chart.series()[0].barSets()
    assert (barres[0].at(barres[0].count() - 1),
            barres[1].at(barres[1].count() - 1)) == (1000.0, 100.0)


def test_rapport_mensuel(base):
    from comptesbudget.ui.report import build_monthly_report_html
    html = build_monthly_report_html(base, MOIS)
    assert "90,0&nbsp;%" in html
    # Milliers séparés par une espace insécable écrite telle quelle.
    assert "1 000,00" in html and "1 100,00" not in html


# ─────────────────────────── A05 : l'échéance du jour ──────────────────────

def _bilan(tmp_path, solde: float):
    from comptesbudget.ui.views.bilan import BilanView
    db = Database(str(tmp_path / "t.db"))
    db.set_solde_initial(solde, AUJ.replace(day=1).isoformat())
    return db, BilanView(db)


def test_echeance_due_aujourd_hui(qapp, tmp_path):
    db, vue = _bilan(tmp_path, 50.0)
    db.insert_recurring({
        "id": "r1", "libelle": "ASSURANCE", "montant": -100.0,
        "categorie": "Banque et assurances", "sous_cat": "", "type": "",
        "frequency": "monthly", "day_of_month": AUJ.day,
        "start_date": AUJ.isoformat(), "end_date": None,  # date = son jour
        "actif": 1})
    info = vue._prochain_decouvert([], 50.0)
    assert info["bascule"] is not None
    assert info["bascule"][0] == AUJ.isoformat()
    assert info["bascule"][1] == -50.0


def test_operation_du_jour_pas_encore_passee(qapp, tmp_path):
    db, vue = _bilan(tmp_path, 50.0)
    op = _op("prlv", -100.0, "Banque et assurances", jour=AUJ.isoformat(),
             pointee=0)
    info = vue._prochain_decouvert([op], 50.0)
    assert info["bascule"] and info["bascule"][0] == AUJ.isoformat()


def test_operation_du_jour_deja_passee_ne_compte_pas_deux_fois(qapp, tmp_path):
    """Pointée aujourd'hui, elle est déjà dans le solde en banque."""
    db, vue = _bilan(tmp_path, 50.0)
    op = _op("prlv", -100.0, "Banque et assurances", jour=AUJ.isoformat(),
             pointee=1)
    info = vue._prochain_decouvert([op], 50.0)
    assert info["bascule"] is None
