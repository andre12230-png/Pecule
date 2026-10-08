"""Imports : les cas relevés par l'audit « nouvel utilisateur » du 08/10/2026.

Fichiers fabriqués, valeurs inventées.

    py -m pytest tests/test_imports_audit_2026_10_08.py
"""
import pytest

from comptesbudget.csv_import import _decode_csv, import_csv, lire_montant
from comptesbudget.database import Database


def _write(tmp_path, nom, contenu: bytes):
    p = tmp_path / nom
    p.write_bytes(contenu)
    return str(p)


# ── Le « Texte Unicode » de Windows (UTF-16) ─────────────────────────────
# Décodé en cp1252, il passait sans erreur mais avec un octet nul entre
# chaque lettre : « Aucune ligne ne nomme les colonnes », fausse piste.

def test_utf16_avec_marque_de_tete():
    texte = "Date;Libellé;Montant\n05/09/2026;LOYER;-650,00\n"
    assert _decode_csv(texte.encode("utf-16")) == texte


def test_utf16_sans_marque_de_tete():
    texte = "Date;Libellé;Montant\n05/09/2026;LOYER;-650,00\n"
    assert _decode_csv(texte.encode("utf-16-le")) == texte


def test_import_d_un_csv_utf16(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    p = _write(tmp_path, "releve.csv",
               "Date;Libellé;Montant\n05/09/2026;LOYER;-650,00\n".encode("utf-16"))
    assert import_csv(p, db).importees == 1


# ── Signe en fin de montant, et signe moins typographique ─────────────────
# « 12,50- » (signe final de certains exports) et « −12,50 » (signe moins
# d'un tableur) étaient refusés et comptés illisibles.

@pytest.mark.parametrize("texte, attendu", [
    ("12,50-", -12.50), ("1 234,56-", -1234.56),
    ("−12,50", -12.50), ("− 1 234,56 €", -1234.56),
])
def test_signe_final_et_moins_typographique(texte, attendu):
    assert lire_montant(texte) == pytest.approx(attendu)


# ── Tout est illisible : le message dit pourquoi ──────────────────────────
# Le diagnostic du fichier (séparateur, dates) ne se faisait que si RIEN
# n'avait été lu. Des lignes comptées illisibles donnaient seulement « date
# ou montant illisible », sans la cause.

def test_tout_illisible_le_message_dit_la_cause(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from comptesbudget.ui import main_window
    vus = []
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda parent, titre, texte, *a, **k: vus.append(texte))
    monkeypatch.setattr(QMessageBox, "information",
                        lambda parent, titre, texte, *a, **k: vus.append(texte))
    db = Database(str(tmp_path / "t.db"))
    fenetre = main_window.MainWindow(db)
    p = _write(tmp_path, "iso.csv",
               "Date;Libelle;Montant\n2026-09-05;LOYER;-650,00\n"
               "2026-09-06;SALAIRE;2100,00\n".encode("utf-8"))
    fenetre._import_files([p])
    texte = "\n".join(vus)
    assert "année d'abord" in texte, texte


# ── QIF / OFX : des opérations, toutes illisibles ────────────────────────
# Le message disait « vérifiez qu'il s'agit bien d'un export de compte »,
# alors que le fichier en était un : seuls les montants étaient illisibles.

def test_qif_aux_montants_illisibles_le_dit(tmp_path):
    from comptesbudget.qif_import import import_qif_text
    db = Database(str(tmp_path / "t.db"))
    qif = ("!Type:Bank\nD05/09/2026\nTdouze euros\nPLOYER\n^\n"
           "D06/09/2026\nTn/a\nPSALAIRE\n^\n")
    with pytest.raises(ValueError) as err:
        import_qif_text(qif, db)
    assert "2 opérations" in str(err.value)
    assert "export de compte" not in str(err.value)


def test_ofx_au_montant_illisible_le_dit(tmp_path):
    from comptesbudget.ofx_import import import_ofx_text
    db = Database(str(tmp_path / "t.db"))
    ofx = ("<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>"
           "<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260905<TRNAMT>douze"
           "<FITID>1<NAME>LOYER</STMTTRN>"
           "</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>")
    with pytest.raises(ValueError) as err:
        import_ofx_text(ofx, db)
    assert "1 opération" in str(err.value)
    assert "relevé de compte" not in str(err.value)
