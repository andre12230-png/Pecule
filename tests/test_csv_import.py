"""Tests de l'import des relevés CSV (parsing + bout en bout)."""
from comptesbudget.csv_import import (
    import_csv, parse_french_amount, parse_french_date,
)
from comptesbudget.database import Database


def test_parse_french_amount():
    assert parse_french_amount("1 234,56") == 1234.56
    assert parse_french_amount("-12,00") == -12.0
    assert parse_french_amount("+50,00") == 50.0
    assert parse_french_amount("") == 0.0
    assert parse_french_amount("abc") == 0.0


def test_parse_french_date():
    assert parse_french_date("23/06/2026") == "2026-06-23"
    assert parse_french_date("") is None
    assert parse_french_date("2026-06-23") is None   # mauvais format → None


_CSV = """Date;Libelle;Montant
23/06/2026;HYPERMARCHE MARKET;-45,30
22/06/2026;SALAIRE JUIN;2000,00
"""


def _write_csv(tmp_path):
    p = tmp_path / "releve.csv"
    p.write_text(_CSV, encoding="utf-8")
    return str(p)


def test_import_csv_inserts(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    csv_path = _write_csv(tmp_path)
    imported, skipped = import_csv(csv_path, db)
    assert (imported, skipped) == (2, 0)
    rows = [dict(r) for r in db.list_tx()]
    assert len(rows) == 2
    montants = sorted(r["montant"] for r in rows)
    assert montants == [-45.30, 2000.00]


def test_import_csv_dedup_reimport(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    csv_path = _write_csv(tmp_path)
    import_csv(csv_path, db)
    # Réimport du même fichier : tout doit être ignoré comme doublon.
    imported, skipped = import_csv(csv_path, db)
    assert imported == 0
    assert skipped == 2
    assert len(list(db.list_tx())) == 2


def _write(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return str(p)


def test_import_csv_dedup_plages_qui_se_chevauchent(tmp_path):
    # Régression : avec l'ancien ID basé sur la position de ligne, une opération
    # présente dans deux relevés à des positions différentes était réimportée.
    db = Database(str(tmp_path / "t.db"))
    a = _write(tmp_path, "a.csv",
               "Date;Libelle;Montant\n05/01/2026;Loyer;-800,00\n05/02/2026;Loyer;-800,00\n")
    b = _write(tmp_path, "b.csv",
               "Date;Libelle;Montant\n05/02/2026;Loyer;-800,00\n05/03/2026;Loyer;-800,00\n")
    assert import_csv(a, db) == (2, 0)
    # Le relevé B chevauche février : seul mars (nouveau) doit entrer.
    imported, skipped = import_csv(b, db)
    assert (imported, skipped) == (1, 1)
    assert len(list(db.list_tx())) == 3


def test_import_csv_garde_vrais_doublons_du_meme_jour(tmp_path):
    # Deux opérations réellement identiques le même jour doivent toutes deux
    # être conservées (compteur d'occurrence), pas fusionnées en une seule.
    db = Database(str(tmp_path / "t.db"))
    csv_path = _write(tmp_path, "c.csv",
                      "Date;Libelle;Montant\n05/01/2026;Cafe;-2,50\n05/01/2026;Cafe;-2,50\n")
    assert import_csv(csv_path, db) == (2, 0)
    assert len(list(db.list_tx())) == 2
