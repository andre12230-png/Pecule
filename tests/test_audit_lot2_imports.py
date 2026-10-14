"""Audit du 14/10/2026, lot 2 : les imports.

A03 — réimporter un relevé dont une ligne a été archivée échouait sur
      l'identifiant de l'opération archivée, et annulait tout le lot : même
      les nouvelles lignes du relevé n'étaient pas ajoutées ;
A06 — une année sur deux chiffres recevait toujours « 2000 + » : 05/09/99
      devenait le 5 septembre 2099. Le QIF suit déjà la convention
      habituelle (00 à 69 → 2000 et plus, 70 à 99 → 1900 et plus).
Données inventées.
"""
import pytest

from comptesbudget.csv_import import import_csv_text, parse_french_date
from comptesbudget.database import Database

RELEVE_1 = "Date;Libellé;Montant\n05/01/2024;BOULANGERIE;-5,00\n"
RELEVE_2 = ("Date;Libellé;Montant\n05/01/2024;BOULANGERIE;-5,00\n"
            "10/09/2026;LIBRAIRIE;-12,00\n")


@pytest.fixture
def db(tmp_path):
    base = Database(str(tmp_path / "comptes.db"))
    base.set_setting("initial_date", "2020-01-01")
    base.set_setting("initial_balance", "100.0")
    return base


def _libelles(db):
    rows = db.conn.execute(
        "SELECT libelle_op, archivee FROM transactions ORDER BY date").fetchall()
    return [(r[0], r[1]) for r in rows]


def test_reimport_apres_archivage(db):
    assert import_csv_text(RELEVE_1, db).importees == 1
    assert db.archiver("2024-12-31") == 1
    resultat = import_csv_text(RELEVE_2, db)
    # La ligne archivée est reconnue comme déjà présente, la nouvelle entre.
    assert resultat.importees == 1
    assert resultat.doublons == 1
    assert _libelles(db) == [("BOULANGERIE", 1), ("LIBRAIRIE", 0)]


def test_reimport_apres_archivage_meme_archives_visibles(db):
    import_csv_text(RELEVE_1, db)
    db.archiver("2024-12-31")
    db.set_voir_archives(True)
    resultat = import_csv_text(RELEVE_2, db)
    assert (resultat.importees, resultat.doublons) == (1, 1)


def test_l_archive_d_un_autre_compte_ne_compte_pas(db):
    """Le contrôle des doublons reste limité au compte importé."""
    import_csv_text(RELEVE_1, db)
    db.archiver("2024-12-31")
    db.set_compte_courant(db.add_compte("Livret", 0.0, "2020-01-01"))
    assert import_csv_text(RELEVE_1, db).importees == 1


@pytest.mark.parametrize("texte, attendu", [
    ("05/09/99", "1999-09-05"),
    ("05/09/70", "1970-09-05"),
    ("05/09/26", "2026-09-05"),
    ("05/09/69", "2069-09-05"),
    ("5/9/2026", "2026-09-05"),
    ("31/12/1999", "1999-12-31"),
])
def test_annees_sur_deux_chiffres(texte, attendu):
    assert parse_french_date(texte) == attendu


def test_meme_convention_que_le_qif():
    from comptesbudget.qif_import import _composantes_date
    for aa in ("99", "70", "69", "00", "26"):
        assert parse_french_date(f"05/09/{aa}")[:4] == str(
            _composantes_date(f"09/05/{aa}")[2]), aa
