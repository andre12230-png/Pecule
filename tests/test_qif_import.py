"""Tests de l'import des fichiers QIF (lecture + bout en bout)."""
import pytest

from comptesbudget.database import Database
from comptesbudget.qif_import import (
    import_qif, import_qif_text, jour_en_premier, lire_qif,
    parse_montant_qif, _composantes_date,
)


# ── Montants ────────────────────────────────────────────────────────────────

def test_montant_separateur_decimal_francais():
    assert parse_montant_qif("-45,30") == -45.30
    assert parse_montant_qif("2000,00") == 2000.0


def test_montant_separateur_decimal_americain():
    assert parse_montant_qif("-45.30") == -45.30
    assert parse_montant_qif("1,234.56") == 1234.56


def test_montant_avec_separateur_de_milliers_des_deux_cotes():
    # Le DERNIER séparateur est toujours le séparateur décimal.
    assert parse_montant_qif("1.234,56") == 1234.56
    assert parse_montant_qif("-12.345.678,90") == -12345678.90


def test_montant_un_seul_separateur_suivi_de_trois_chiffres():
    # « 1,234 » : trois chiffres derrière, donc des milliers — aucun relevé
    # bancaire n'a trois décimales.
    assert parse_montant_qif("1,234") == 1234.0
    assert parse_montant_qif("1.234") == 1234.0


def test_montant_parentheses_et_signes():
    assert parse_montant_qif("(45,30)") == -45.30
    assert parse_montant_qif("+50,00") == 50.0


def test_montant_illisible():
    assert parse_montant_qif("") is None
    assert parse_montant_qif("abc") is None
    assert parse_montant_qif(None) is None


# ── Dates ───────────────────────────────────────────────────────────────────

def test_ordre_jour_mois_deduit_du_fichier():
    # 23 ne peut pas être un mois → le fichier est en jour/mois.
    assert jour_en_premier([_composantes_date("23/06/2026")]) is True
    # 06/23 : le SECOND nombre dépasse 12 → mois/jour (fichier américain).
    assert jour_en_premier([_composantes_date("06/23/2026")]) is False
    # Aucun indice : on retient l'usage français.
    assert jour_en_premier([_composantes_date("05/06/2026")]) is True


def test_annees_sur_deux_chiffres():
    # L'apostrophe de Quicken/Money marque les années 2000.
    assert _composantes_date("12/08'26")[2] == 2026
    assert _composantes_date("12/08/98")[2] == 1998
    assert _composantes_date("12/08/06")[2] == 2006


def test_date_iso_acceptee_sans_ambiguite():
    assert _composantes_date("2026-06-23") == (23, 6, 2026, False)


# ── Lecture d'un fichier ────────────────────────────────────────────────────

_QIF = """!Type:Bank
D23/06/2026
T-45,30
PHYPERMARCHE MARKET
MCourses de la semaine
LAlimentation:Supermarché
N001234
C*
^
D22/06/2026
T2000,00
PSALAIRE JUIN
LRevenus
^
"""


def test_lecture_des_champs():
    operations, comptes, illisibles = lire_qif(_QIF)
    assert (len(operations), comptes, illisibles) == (2, [], 0)
    op = operations[0]
    assert op.date == "23/06/2026"
    assert op.montant == -45.30
    assert op.libelle == "HYPERMARCHE MARKET"
    assert op.memo == "Courses de la semaine"
    assert op.reference == "001234"
    assert (op.categorie, op.sous_cat) == ("Alimentation", "Supermarché")
    assert op.pointee is True
    assert operations[1].pointee is False


def test_operation_sans_libelle_reprend_le_memo():
    operations, _, _ = lire_qif("!Type:Bank\nD01/07/2026\nT-10,00\nMRetrait\n^\n")
    assert operations[0].libelle == "Retrait"


def test_virement_note_au_lieu_d_une_fausse_categorie():
    operations, _, _ = lire_qif(
        "!Type:Bank\nD01/07/2026\nT-100,00\nPEpargne\nL[Livret A]\n^\n")
    op = operations[0]
    assert op.categorie == ""          # pas de catégorie inventée
    assert "Livret A" in op.memo


def test_classe_quicken_ignoree():
    operations, _, _ = lire_qif(
        "!Type:Bank\nD01/07/2026\nT-10,00\nPX\nLLoisirs:Cinéma/Vacances\n^\n")
    assert (operations[0].categorie, operations[0].sous_cat) == ("Loisirs", "Cinéma")


def test_ventilation_ramenee_au_total_et_premiere_categorie():
    # Opération de 100 € ventilée en deux : Pécule ne découpe pas, il garde
    # le montant total et la première catégorie.
    operations, _, _ = lire_qif(
        "!Type:Bank\nD01/07/2026\nT-100,00\nPMAGASIN\n"
        "LAlimentation\nS Alimentation\n$-60,00\nSLoisirs\n$-40,00\n^\n")
    assert len(operations) == 1
    assert operations[0].montant == -100.0
    assert operations[0].categorie == "Alimentation"


def test_blocs_sans_operations_ignores():
    # Une liste de catégories ne doit pas produire d'opérations.
    operations, _, illisibles = lire_qif(
        "!Type:Cat\nNAlimentation\nE\n^\n" + _QIF)
    assert len(operations) == 2
    assert illisibles == 0


def test_operation_illisible_comptee_et_ecartee():
    operations, _, illisibles = lire_qif(
        "!Type:Bank\nD32/13/2026\nT-10,00\nPX\n^\n"
        "!Type:Bank\nD01/07/2026\nTabc\nPY\n^\n")
    assert (operations, illisibles) == ([], 2)


# ── Import de bout en bout ──────────────────────────────────────────────────

def test_import_qif_insere(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    assert import_qif_text(_QIF, db) == (2, 0, 0, 0, 0, 0)
    rows = [dict(r) for r in db.list_tx()]
    assert sorted(r["montant"] for r in rows) == [-45.30, 2000.00]
    achat = next(r for r in rows if r["montant"] == -45.30)
    assert achat["date"] == "2026-06-23"
    assert achat["libelle"] == "HYPERMARCHE MARKET"
    assert achat["reference"] == "001234"
    assert achat["pointee"] == 1
    assert achat["info"] == "Courses de la semaine"


def test_import_qif_dedup_au_reimport(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    import_qif_text(_QIF, db)
    # Le même fichier réimporté ne doit rien ajouter.
    assert import_qif_text(_QIF, db) == (0, 2, 0, 0, 0, 0)


def test_import_qif_dedup_avec_un_csv_deja_importe(tmp_path):
    """Une opération déjà venue du CSV ne doit pas revenir par le QIF."""
    from comptesbudget.csv_import import import_csv_text
    db = Database(str(tmp_path / "t.db"))
    csv = ("Date;Libelle;Montant\n"
           "23/06/2026;HYPERMARCHE MARKET;-45,30\n")
    assert import_csv_text(csv, db) == (1, 0, 0, 0, 0, 0)
    imported, skipped, _, _, _, _ = import_qif_text(_QIF, db)
    assert (imported, skipped) == (1, 1)


def test_import_qif_applique_les_regles(tmp_path):
    """Les règles de catégorisation valent aussi pour le QIF : c'est tout
    l'intérêt d'avoir réutilisé la mécanique de l'import CSV."""
    db = Database(str(tmp_path / "t.db"))
    db.insert_rule({"id": "r1", "pattern": "hypermarche", "amount": None,
                    "categorie": "Shopping", "sous_cat": "Courses",
                    "no_overwrite": 0, "created_at": "2026-01-01"})
    import_qif_text(_QIF, db)
    achat = next(dict(r) for r in db.list_tx() if r["montant"] == -45.30)
    assert (achat["categorie"], achat["sous_cat"]) == ("Shopping", "Courses")


def test_import_qif_fichier_multi_comptes_refuse(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    texte = ("!Account\nNCompte courant\nTBank\n^\n"
             "!Type:Bank\nD01/07/2026\nT-10,00\nPA\n^\n"
             "!Account\nNLivret A\nTBank\n^\n"
             "!Type:Bank\nD02/07/2026\nT-20,00\nPB\n^\n")
    with pytest.raises(ValueError, match="plusieurs comptes"):
        import_qif_text(texte, db)
    # Rien ne doit avoir été enregistré.
    assert list(db.list_tx()) == []


def test_import_qif_un_seul_compte_nomme_accepte(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    texte = ("!Account\nNCompte courant\nTBank\n^\n"
             "!Type:Bank\nD01/07/2026\nT-10,00\nPA\n^\n")
    assert import_qif_text(texte, db) == (1, 0, 0, 0, 0, 0)


def test_import_qif_fichier_sans_operation_refuse(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    with pytest.raises(ValueError, match="aucune opération"):
        import_qif_text("!Type:Cat\nNAlimentation\n^\n", db)


def test_import_qif_depuis_un_fichier_windows_1252(tmp_path):
    """Les exports de Money sont en Windows-1252, pas en UTF-8."""
    db = Database(str(tmp_path / "t.db"))
    p = tmp_path / "money.qif"
    p.write_bytes(_QIF.encode("cp1252"))
    assert import_qif(str(p), db) == (2, 0, 0, 0, 0, 0)
    achat = next(dict(r) for r in db.list_tx() if r["montant"] == -45.30)
    assert achat["sous_cat"] == "Supermarché"


def test_import_qif_americain(tmp_path):
    """Fichier en mois/jour et point décimal : dates et montants corrects."""
    db = Database(str(tmp_path / "t.db"))
    texte = ("!Type:Bank\nD06/23/2026\nT-1,234.56\nPSTORE\n^\n")
    assert import_qif_text(texte, db) == (1, 0, 0, 0, 0, 0)
    op = dict(next(iter(db.list_tx())))
    assert op["date"] == "2026-06-23"
    assert op["montant"] == -1234.56
