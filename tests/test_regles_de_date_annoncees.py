"""Les regles de date annoncees disent ce que fait l'appli (audit du
08/10/2026).

Depuis le 26/09/2026, l'import lit « 5/1/2026 » et « 05/01/26 ». La page
d'aide du site, et le message de l'appli quand les dates sont illisibles,
disaient encore que « 5/1/2026 » etait refuse : un utilisateur dans ce cas
se croyait bloque.

    py -m pytest tests/test_regles_de_date_annoncees.py
"""
from pathlib import Path

from comptesbudget.csv_import import parse_french_date

RACINE = Path(__file__).resolve().parent.parent


def test_l_appli_lit_bien_ces_dates():
    assert parse_french_date("5/1/2026") == "2026-01-05"
    assert parse_french_date("05/01/26") == "2026-01-05"
    assert parse_french_date("2026-01-05") is None


def test_les_textes_ne_disent_plus_le_contraire():
    fautes = []
    for p in [RACINE / "comptesbudget" / "csv_import.py",
              RACINE / "docs" / "import-csv.html",
              RACINE / "docs" / "import-csv-problemes.html"]:
        texte = p.read_text(encoding="utf-8")
        for interdit in ("jour et mois sur deux chiffres",
                         "<code>5/1/2026</code> et <code>2026-01-05</code> sont refusés",
                         "y compris\n  <code>5/1/2026</code>"):
            if interdit in texte:
                fautes.append(f"{p.name} : « {interdit[:40]} »")
    assert not fautes, fautes
