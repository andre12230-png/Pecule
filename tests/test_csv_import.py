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
    imported, skipped, bad, _ = import_csv(csv_path, db)
    assert (imported, skipped, bad) == (2, 0, 0)
    rows = [dict(r) for r in db.list_tx()]
    assert len(rows) == 2
    montants = sorted(r["montant"] for r in rows)
    assert montants == [-45.30, 2000.00]


def test_import_csv_dedup_reimport(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    csv_path = _write_csv(tmp_path)
    import_csv(csv_path, db)
    # Réimport du même fichier : tout doit être ignoré comme doublon.
    imported, skipped, _, _ = import_csv(csv_path, db)
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
    assert import_csv(a, db) == (2, 0, 0, 0)
    # Le relevé B chevauche février : seul mars (nouveau) doit entrer.
    imported, skipped, _, _ = import_csv(b, db)
    assert (imported, skipped) == (1, 1)
    assert len(list(db.list_tx())) == 3


def test_import_csv_garde_vrais_doublons_du_meme_jour(tmp_path):
    # Deux opérations réellement identiques le même jour doivent toutes deux
    # être conservées (compteur d'occurrence), pas fusionnées en une seule.
    db = Database(str(tmp_path / "t.db"))
    csv_path = _write(tmp_path, "c.csv",
                      "Date;Libelle;Montant\n05/01/2026;Cafe;-2,50\n05/01/2026;Cafe;-2,50\n")
    assert import_csv(csv_path, db) == (2, 0, 0, 0)
    assert len(list(db.list_tx())) == 2


def test_import_csv_dedup_saisie_manuelle_sans_reference(tmp_path):
    # Régression (incident du 11/07/2026) : une opération saisie À LA MAIN
    # (sans référence bancaire, libellé harmonisé « Caisse Comp ») doit être
    # reconnue comme doublon quand le relevé apporte la même opération avec
    # une référence et un libellé brut « CAISSE COMP ».
    db = Database(str(tmp_path / "t.db"))
    db.insert_tx({
        "id": "uuid-manuel", "date": "2026-06-01", "date_valeur": "2026-06-01",
        "libelle": "Caisse Comp", "libelle_op": "Caisse Comp", "reference": "",
        "type": "Virement", "categorie": "Revenus", "sous_cat": "", "info": "",
        "montant": 300.00, "pointee": 1,
    })
    p = _write(tmp_path, "r.csv",
               "Date;Libelle;Reference;Montant\n"
               "01/06/2026;CAISSE COMP;1234567A00000000;300,00\n")
    assert import_csv(p, db) == (0, 1, 0, 0)
    assert len(list(db.list_tx())) == 1


def test_import_csv_dedup_reference_changee_entre_exports(tmp_path):
    # Certaines banques changent la référence d'un export à l'autre : le
    # libellé nettoyé doit suffire à reconnaître le doublon.
    db = Database(str(tmp_path / "t.db"))
    a = _write(tmp_path, "a.csv",
               "Date;Libelle;Reference;Montant\n"
               "08/06/2026;ALPHATEL;REF-EXPORT-1;-43,00\n")
    b = _write(tmp_path, "b.csv",
               "Date;Libelle;Reference;Montant\n"
               "08/06/2026;ALPHATEL;REF-EXPORT-2;-43,00\n")
    assert import_csv(a, db) == (1, 0, 0, 0)
    assert import_csv(b, db) == (0, 1, 0, 0)
    assert len(list(db.list_tx())) == 1


def test_import_csv_categories_banque_ramenees_au_canon(tmp_path):
    # Les catégories des exports BPCE ne doivent plus créer de catégories
    # parasites : « A categoriser… » → Non classé, « Revenus et rentrees
    # d'argent » → Revenus.
    db = Database(str(tmp_path / "t.db"))
    p = _write(tmp_path, "c.csv",
               "Date;Libelle;Categorie;Montant\n"
               "01/06/2026;VIR RECU X;Revenus et rentrees d'argent;100,00\n"
               "02/06/2026;PRLV Y;A categoriser - sortie d'argent;-10,00\n")
    assert import_csv(p, db) == (2, 0, 0, 0)
    cats = {dict(r)["categorie"] for r in db.list_tx()}
    assert cats == {"Revenus", "Non classé"}


def test_import_csv_utf8_accents(tmp_path):
    # Régression : un fichier UTF-8 était lu en Windows-1252 → « CRÃ‰DIT ».
    p = tmp_path / "utf8.csv"
    p.write_bytes("Date;Libelle;Montant\n23/06/2026;CRÉDIT CAFÉ;-2,50\n".encode("utf-8"))
    db = Database(str(tmp_path / "t.db"))
    assert import_csv(str(p), db) == (1, 0, 0, 0)
    rows = [dict(r) for r in db.list_tx()]
    assert rows[0]["libelle"] == "CRÉDIT CAFÉ"


def test_import_csv_cp1252_accents(tmp_path):
    # L'encodage habituel des banques françaises doit continuer de fonctionner.
    p = tmp_path / "cp1252.csv"
    p.write_bytes("Date;Libelle;Montant\n23/06/2026;CRÉDIT CAFÉ;-2,50\n".encode("cp1252"))
    db = Database(str(tmp_path / "t.db"))
    assert import_csv(str(p), db) == (1, 0, 0, 0)
    rows = [dict(r) for r in db.list_tx()]
    assert rows[0]["libelle"] == "CRÉDIT CAFÉ"


def test_import_csv_pointage_automatique(tmp_path):
    # La colonne « Pointage operation » de la banque (« x » = passée en
    # banque) pointe automatiquement les nouvelles opérations.
    db = Database(str(tmp_path / "t.db"))
    p = _write(tmp_path, "p.csv",
               "Date;Libelle;Montant;Pointage operation\n"
               "01/06/2026;ALPHATEL;-43,00;x\n"
               "09/06/2026;PISCINE;-24,80;0\n")
    assert import_csv(p, db) == (2, 0, 0, 0)
    par_lib = {dict(r)["libelle"]: dict(r)["pointee"] for r in db.list_tx()}
    assert par_lib == {"ALPHATEL": 1, "PISCINE": 0}


def test_import_csv_pointage_confirme_les_existantes(tmp_path):
    # Une opération déjà en base (non pointée) que la banque marque « x »
    # est pointée automatiquement lors de l'import (jamais dépointée).
    db = Database(str(tmp_path / "t.db"))
    db.insert_tx({
        "id": "uuid-1", "date": "2026-06-01", "date_valeur": "2026-06-01",
        "libelle": "Alphatel", "libelle_op": "Alphatel", "reference": "",
        "type": "", "categorie": "Logement - maison", "sous_cat": "", "info": "",
        "montant": -43.00, "pointee": 0,
    })
    db.insert_tx({
        "id": "uuid-2", "date": "2026-06-02", "date_valeur": "2026-06-02",
        "libelle": "SERVICE DES EAUX", "libelle_op": "SERVICE DES EAUX", "reference": "",
        "type": "", "categorie": "Logement - maison", "sous_cat": "", "info": "",
        "montant": -22.50, "pointee": 1,
    })
    p = _write(tmp_path, "p.csv",
               "Date;Libelle;Montant;Pointage operation\n"
               "01/06/2026;ALPHATEL;-43,00;x\n"
               "02/06/2026;SAUR;-22,50;0\n")
    # 0 importée, 2 doublons, 1 pointée automatiquement (Orange)
    assert import_csv(p, db) == (0, 2, 0, 1)
    etats = {dict(r)["libelle"]: dict(r)["pointee"] for r in db.list_tx()}
    assert etats["Alphatel"] == 1     # confirmée par le relevé
    assert etats["SERVICE DES EAUX"] == 1       # « 0 » banque ne dépointe JAMAIS


def test_import_csv_montant_illisible_signale(tmp_path):
    # Un montant illisible ne doit PAS entrer en base à 0 € : la ligne est
    # écartée et comptée dans le 3e élément du résultat.
    db = Database(str(tmp_path / "t.db"))
    csv_path = _write(tmp_path, "bad.csv",
                      "Date;Libelle;Montant\n05/01/2026;Loyer;-800,00\n06/01/2026;Bizarre;1.234,56\n")
    assert import_csv(csv_path, db) == (1, 0, 1, 0)
    assert len(list(db.list_tx())) == 1
