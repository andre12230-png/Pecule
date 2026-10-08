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
