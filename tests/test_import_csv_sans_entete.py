"""Import d'un relevé CSV SANS ligne de titres (signalé par un utilisateur
de LCL le 16/10/2026, avec la version 1.41.2).

LCL exporte un fichier « T_cpte_<guichet>_<compte>_du_…_au_….csv »
dont aucune ligne ne nomme les colonnes. Leur ordre est fixe :

    date ; montant ; type ; compte ; libellé débit ; libellé crédit ; code ; catégorie

La première et la dernière ligne ne sont pas des opérations mais le solde du
compte au début et à la fin de la période (seule la case « compte » y est
remplie). Pécule refusait le fichier : « Aucune ligne de ce fichier ne nomme
les colonnes ».

Fichier fabriqué, valeurs inventées.

    py -m pytest tests/test_import_csv_sans_entete.py
"""
import pytest

from comptesbudget.csv_import import import_csv
from comptesbudget.database import Database

RELEVE = (
    "01/09/2026;1000;;00000 0000000X;;;;\n"
    "02/09/2026;500;Virement;;;VIREMENT CAISSE DE RETRAITE;;\n"
    "05/09/2026;-40,50;Virement;;PRLV SEPA ASSUREUR EXEMPLE;;;\n"
    "08/09/2026;-25,10;Carte;;SUPERMARCHE EXEMPLE VILLE;;5411;Alimentation:Epicerie\n"
    "10/09/2026;-100;Retrait DAB;;;CB  RETRAIT DU  09/09;;Liquide\n"
    "30/09/2026;1334,40;;00000 0000000X;;;;\n"
)


def _importer(tmp_path, contenu: str):
    p = tmp_path / "T_cpte_00000_0000000X_du_01-09-2026_au_30-09-2026.csv"
    p.write_bytes(contenu.encode("cp1252"))
    db = Database(str(tmp_path / "t.db"))
    resultat = import_csv(str(p), db)
    ops = {t["libelle"].upper(): dict(t) for t in db.list_tx_avec_archives()}
    return resultat, ops


def test_les_quatre_operations_sont_importees(tmp_path):
    resultat, ops = _importer(tmp_path, RELEVE)
    assert resultat.importees == 4
    assert resultat.illisibles == 0


def test_les_lignes_de_solde_ne_sont_pas_des_operations(tmp_path):
    _, ops = _importer(tmp_path, RELEVE)
    montants = sorted(round(t["montant"], 2) for t in ops.values())
    # Ni 1000 ni 1334,40 : ce sont les soldes, pas des opérations.
    assert montants == [-100.0, -40.5, -25.1, 500.0]


def test_libelle_pris_dans_l_une_ou_l_autre_colonne(tmp_path):
    _, ops = _importer(tmp_path, RELEVE)
    libelles = " | ".join(ops)
    # Libellé de débit (5e colonne) comme de crédit (6e colonne).
    assert "ASSUREUR EXEMPLE" in libelles
    assert "CAISSE DE RETRAITE" in libelles
    assert "RETRAIT" in libelles


def test_type_et_categorie_de_la_banque_gardes(tmp_path):
    _, ops = _importer(tmp_path, RELEVE)
    achat = next(t for k, t in ops.items() if "SUPERMARCHE" in k)
    assert achat["montant"] == pytest.approx(-25.10)
    assert achat["type"] == "Carte"
    assert achat["categorie"] == "Alimentation"
    assert achat["sous_cat"] == "Epicerie"


def test_toutes_les_operations_sont_pointees(tmp_path):
    # Comme tout relevé sans colonne de pointage : déjà passées en banque.
    _, ops = _importer(tmp_path, RELEVE)
    assert all(t["pointee"] for t in ops.values())


def test_reimport_sans_doublon(tmp_path):
    p = tmp_path / "releve.csv"
    p.write_bytes(RELEVE.encode("cp1252"))
    db = Database(str(tmp_path / "t.db"))
    import_csv(str(p), db)
    second = import_csv(str(p), db)
    assert second.importees == 0
    assert second.doublons == 4


def test_un_fichier_sans_titres_d_une_autre_forme_reste_refuse(tmp_path):
    # Trois colonnes seulement : rien ne dit laquelle est le libellé. Le
    # message d'aide habituel doit rester.
    p = tmp_path / "autre.csv"
    p.write_bytes(b"05/09/2026;LOYER;-650,00\n06/09/2026;PAIN;-1,20\n")
    db = Database(str(tmp_path / "t.db"))
    with pytest.raises(ValueError, match="ne nomme les colonnes"):
        import_csv(str(p), db)
