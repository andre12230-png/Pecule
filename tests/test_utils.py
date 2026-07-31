"""Tests des utilitaires (formatage, normalisation, périodes)."""
from comptesbudget.utils import (
    canonical_cat, cat_color, date_debit_differe, deaccent, fmt_date_fr,
    fmt_euro, in_period, list_periods, period_label, suggest_category,
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


def test_list_periods_suit_le_mode_date():
    # Achat carte du 28/07 débité le 04/08 : en mode « date de valeur », le
    # mois d'août doit être proposé — sinon l'opération n'est visible dans
    # aucun mois. En mode « date d'opération », c'est juillet qui compte.
    txs = [{"date": "2026-07-28", "date_valeur": "2026-08-04"}]
    op = list_periods(txs, "operation")
    val = list_periods(txs, "valeur")
    assert "2026-07" in op and "2026-08" not in op
    assert "2026-08" in val and "2026-07" not in val


def test_date_debit_differe():
    # Achats du mois M → prélevés le 4 du mois M+1
    assert date_debit_differe("2026-07-15") == "2026-08-04"
    assert date_debit_differe("2026-07-01") == "2026-08-04"
    assert date_debit_differe("2026-08-02") == "2026-09-04"   # début de mois : M+1, pas le 04/08
    assert date_debit_differe("2026-12-20") == "2027-01-04"   # passage d'année
    # Jour personnalisé, y compris au-delà du dernier jour du mois
    assert date_debit_differe("2026-01-10", jour=6) == "2026-02-06"
    assert date_debit_differe("2026-01-10", jour=31) == "2026-02-28"
    # Entrée illisible → renvoyée telle quelle, jamais d'exception
    assert date_debit_differe("") == ""
    assert date_debit_differe("pas une date") == "pas une date"


def test_suggest_category():
    assert suggest_category("EDF facture electricite") == "Logement - maison"
    assert suggest_category("CARREFOUR MARKET") == "Alimentation"
    assert suggest_category("libellé sans motif connu") is None


def test_suggest_category_motifs_ambigus():
    # Corrections des motifs qui se chevauchaient (audit du 31/07/2026)
    assert suggest_category("TOTALENERGIES SA") == "Logement - maison"
    assert suggest_category("TOTAL ACCESS") == "Transports"
    assert suggest_category("BOULANGERIE DUPONT") == "Alimentation"
    assert suggest_category("BOULANGER 4521") == "Shopping"   # l'enseigne
    # « remboursement » ne bascule plus en Revenus : la convention est de le
    # classer dans la catégorie de la dépense d'origine.
    assert suggest_category("REMBOURSEMENT SAMSE") is None
    # « BP » (2 lettres) n'attrape plus la Banque Populaire
    assert suggest_category("BANQUE BP") is None
