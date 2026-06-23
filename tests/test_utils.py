"""Tests des utilitaires (formatage, normalisation, périodes)."""
from comptesbudget.utils import (
    canonical_cat, cat_color, deaccent, fmt_date_fr, fmt_euro,
    in_period, list_periods, period_label, suggest_category,
)


def test_fmt_euro_francais():
    assert fmt_euro(1234.56) == "1 234,56 €"
    assert fmt_euro(0) == "0,00 €"
    assert fmt_euro(-5) == "-5,00 €"


def test_fmt_date_fr():
    assert fmt_date_fr("2026-06-23") == "23/06/2026"
    assert fmt_date_fr("") == ""
    assert fmt_date_fr("court") == "court"   # non parsable → tel quel


def test_deaccent():
    assert deaccent("Épargne") == "epargne"
    assert deaccent("Crédit Agricole") == "credit agricole"
    assert deaccent("") == ""


def test_canonical_cat():
    assert canonical_cat("ALIMENTATION") == "Alimentation"
    assert canonical_cat("salaire") == "Revenus"
    assert canonical_cat("inconnu") is None
    assert canonical_cat("") is None


def test_cat_color_fallback():
    assert cat_color("Alimentation") == "#E67E22"
    assert cat_color("Salaire") == "#27AE60"        # via forme canonique Revenus
    assert cat_color("Catégorie inconnue") == "#8A877F"


def test_in_period():
    assert in_period("2026-06-23", "all") is True
    assert in_period("2026-06-23", "2026") is True
    assert in_period("2026-06-23", "2026-06") is True
    assert in_period("2026-06-23", "2026-05") is False
    assert in_period("", "2026") is False


def test_period_label():
    assert period_label("all") == "Toutes périodes"
    assert period_label("2026") == "Année 2026"
    assert period_label("2026-06") == "Juin 2026"
    assert period_label("2026-13") == "2026-13"      # mois invalide → tel quel


def test_list_periods():
    txs = [{"date": "2026-06-23"}, {"date": "2026-05-01"}, {"date": "2025-12-31"}]
    out = list_periods(txs)
    assert out[0] == "all"
    assert "2026" in out and "2025" in out
    assert "2026-06" in out and "2025-12" in out
    # Années avant les mois, ordre décroissant
    assert out.index("2026") < out.index("2026-06")


def test_suggest_category():
    assert suggest_category("EDF facture electricite") == "Logement - maison"
    assert suggest_category("CARREFOUR MARKET") == "Alimentation"
    assert suggest_category("libellé sans motif connu") is None
