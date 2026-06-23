"""Tests des opérations récurrentes (occurrences et détection)."""
from datetime import date

from comptesbudget.recurring import (
    _recurring_norm_label, detect_recurring_candidates,
    generate_occurrences, next_occurrence,
)


def test_next_monthly():
    rec = {"frequency": "monthly", "day_of_month": 15}
    assert next_occurrence(rec, date(2026, 1, 15)) == date(2026, 2, 15)


def test_next_monthly_clamp_fin_de_mois():
    rec = {"frequency": "monthly", "day_of_month": 31}
    assert next_occurrence(rec, date(2026, 1, 31)) == date(2026, 2, 28)


def test_next_monthly_passage_decembre():
    rec = {"frequency": "monthly", "day_of_month": 15}
    assert next_occurrence(rec, date(2026, 12, 15)) == date(2027, 1, 15)


def test_next_weekly_biweekly():
    assert next_occurrence({"frequency": "weekly"}, date(2026, 6, 1)) == date(2026, 6, 8)
    assert next_occurrence({"frequency": "biweekly"}, date(2026, 6, 1)) == date(2026, 6, 15)


def test_next_quarterly_passe_annee():
    rec = {"frequency": "quarterly", "day_of_month": 15}
    assert next_occurrence(rec, date(2026, 11, 15)) == date(2027, 2, 15)


def test_next_yearly_bissextile():
    rec = {"frequency": "yearly"}
    # 29/02 → l'année suivante n'est pas bissextile → repli au 28
    assert next_occurrence(rec, date(2024, 2, 29)) == date(2025, 2, 28)


def test_generate_occurrences_bornes():
    rec = {"actif": 1, "frequency": "monthly", "day_of_month": 15,
           "start_date": "2026-01-15"}
    occ = generate_occurrences(rec, date(2026, 4, 30))
    assert occ == [date(2026, 1, 15), date(2026, 2, 15),
                   date(2026, 3, 15), date(2026, 4, 15)]


def test_generate_occurrences_inactif_ou_vide():
    assert generate_occurrences({"actif": 0, "start_date": "2026-01-01"}, date(2026, 6, 1)) == []
    assert generate_occurrences({"actif": 1, "start_date": None}, date(2026, 6, 1)) == []


def test_norm_label_retire_dates():
    assert _recurring_norm_label("ELECTRICITE Facture 12/03/2026") == "electricite facture"


def test_detect_candidate_mensuel():
    txs = [{"date": f"2026-0{m}-05", "libelle": "Loyer",
            "montant": -800.0, "categorie": "Logement - maison", "type": "Prelevement"}
           for m in range(1, 6)]   # 5 mois consécutifs
    cands = detect_recurring_candidates(txs, min_months=4)
    assert len(cands) == 1
    c = cands[0]
    assert c["libelle"] == "Loyer"
    assert c["frequency"] == "monthly"
    assert c["montant"] == -800.0
    assert c["categorie"] == "Logement - maison"


def test_detect_ignore_trop_court():
    txs = [{"date": f"2026-0{m}-05", "libelle": "Test", "montant": -10.0}
           for m in range(1, 3)]   # 2 mois < min_months
    assert detect_recurring_candidates(txs, min_months=4) == []
