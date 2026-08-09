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
    imported, skipped, bad, _, _, _ = import_csv(csv_path, db)
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
    imported, skipped, _, _, _, _ = import_csv(csv_path, db)
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
    assert import_csv(a, db) == (2, 0, 0, 0, 0, 0)
    # Le relevé B chevauche février : seul mars (nouveau) doit entrer.
    imported, skipped, _, _, _, _ = import_csv(b, db)
    assert (imported, skipped) == (1, 1)
    assert len(list(db.list_tx())) == 3


def test_import_csv_garde_vrais_doublons_du_meme_jour(tmp_path):
    # Deux opérations réellement identiques le même jour doivent toutes deux
    # être conservées (compteur d'occurrence), pas fusionnées en une seule.
    db = Database(str(tmp_path / "t.db"))
    csv_path = _write(tmp_path, "c.csv",
                      "Date;Libelle;Montant\n05/01/2026;Cafe;-2,50\n05/01/2026;Cafe;-2,50\n")
    assert import_csv(csv_path, db) == (2, 0, 0, 0, 0, 0)
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
    assert import_csv(p, db) == (0, 1, 0, 0, 0, 0)
    assert len(list(db.list_tx())) == 1


def test_import_csv_dedup_saisie_manuelle_libelle_different(tmp_path):
    # Incident du 14/07/2026 : saisie manuelle « Omnishop », relevé « CREDIPLUS »
    # (même opération, libellés incomparables). Face à une saisie manuelle,
    # même date + même montant suffisent — et le « x » de la banque pointe
    # la saisie manuelle.
    db = Database(str(tmp_path / "t.db"))
    db.insert_tx({
        "id": "uuid-manuel", "date": "2026-07-03", "date_valeur": "2026-07-03",
        "libelle": "Omnishop", "libelle_op": "Omnishop", "reference": "",
        "type": "Carte bancaire", "categorie": "Shopping", "sous_cat": "",
        "info": "", "montant": -20.00, "pointee": 0,
    })
    p = _write(tmp_path, "r.csv",
               "Date;Libelle;Montant;Pointage operation\n"
               "03/07/2026;CREDIPLUS;-20,00;x\n")
    assert import_csv(p, db) == (0, 1, 0, 1, 0, 0)
    rows = [dict(r) for r in db.list_tx()]
    assert len(rows) == 1
    assert rows[0]["libelle"] == "Omnishop"    # la saisie de l'utilisateur reste
    assert rows[0]["pointee"] == 1           # ...et la banque l'a confirmée


def test_import_csv_date_montant_ne_vaut_que_pour_les_saisies_manuelles(tmp_path):
    # Deux opérations IMPORTÉES distinctes, même jour et même montant mais
    # libellés différents, restent deux opérations : la règle date+montant
    # ne s'applique que face aux saisies manuelles.
    db = Database(str(tmp_path / "t.db"))
    a = _write(tmp_path, "a.csv",
               "Date;Libelle;Montant\n05/01/2026;CAFE DU PORT;-2,50\n")
    b = _write(tmp_path, "b.csv",
               "Date;Libelle;Montant\n05/01/2026;BOULANGERIE SUD;-2,50\n")
    assert import_csv(a, db) == (1, 0, 0, 0, 0, 0)
    assert import_csv(b, db) == (1, 0, 0, 0, 0, 0)
    assert len(list(db.list_tx())) == 2


def test_import_csv_saisie_manuelle_ambigue_n_ecarte_aucune_ligne(tmp_path):
    # Une saisie manuelle face à PLUSIEURS lignes du relevé au même jour et au
    # même montant : impossible de savoir laquelle elle représente. On importe
    # alors tout — perdre une vraie dépense du relevé serait pire qu'afficher
    # un doublon, que l'outil « Doublons » sait traiter.
    db = Database(str(tmp_path / "t.db"))
    db.insert_tx({
        "id": "uuid-manuel", "date": "2026-07-10", "date_valeur": "2026-07-10",
        "libelle": "Café", "libelle_op": "Café", "reference": "",
        "type": "", "categorie": "Alimentation", "sous_cat": "",
        "info": "", "montant": -4.50, "pointee": 0,
    })
    p = _write(tmp_path, "r.csv",
               "Date;Libelle;Reference;Montant\n"
               "10/07/2026;BOULANGERIE DUPONT;REF001;-4,50\n"
               "10/07/2026;PARKING CENTRE;REF002;-4,50\n")
    assert import_csv(p, db) == (2, 0, 0, 0, 0, 0)
    libelles = sorted(dict(r)["libelle"] for r in db.list_tx())
    assert libelles == ["BOULANGERIE DUPONT", "Café", "PARKING CENTRE"]


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
    assert import_csv(a, db) == (1, 0, 0, 0, 0, 0)
    assert import_csv(b, db) == (0, 1, 0, 0, 0, 0)
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
    assert import_csv(p, db) == (2, 0, 0, 0, 0, 0)
    cats = {dict(r)["categorie"] for r in db.list_tx()}
    assert cats == {"Revenus", "Non classé"}


def test_import_csv_utf8_accents(tmp_path):
    # Régression : un fichier UTF-8 était lu en Windows-1252 → « CRÃ‰DIT ».
    p = tmp_path / "utf8.csv"
    p.write_bytes("Date;Libelle;Montant\n23/06/2026;CRÉDIT CAFÉ;-2,50\n".encode("utf-8"))
    db = Database(str(tmp_path / "t.db"))
    assert import_csv(str(p), db) == (1, 0, 0, 0, 0, 0)
    rows = [dict(r) for r in db.list_tx()]
    assert rows[0]["libelle"] == "CRÉDIT CAFÉ"


def test_import_csv_cp1252_accents(tmp_path):
    # L'encodage habituel des banques françaises doit continuer de fonctionner.
    p = tmp_path / "cp1252.csv"
    p.write_bytes("Date;Libelle;Montant\n23/06/2026;CRÉDIT CAFÉ;-2,50\n".encode("cp1252"))
    db = Database(str(tmp_path / "t.db"))
    assert import_csv(str(p), db) == (1, 0, 0, 0, 0, 0)
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
    assert import_csv(p, db) == (2, 0, 0, 0, 0, 0)
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
               "02/06/2026;SERVICE DES EAUX;-22,50;0\n")
    # 0 importée, 2 doublons, 1 pointée automatiquement (Alphatel)
    assert import_csv(p, db) == (0, 2, 0, 1, 0, 0)
    etats = {dict(r)["libelle"]: dict(r)["pointee"] for r in db.list_tx()}
    assert etats["Alphatel"] == 1     # confirmée par le relevé
    assert etats["SERVICE DES EAUX"] == 1       # « 0 » banque ne dépointe JAMAIS


def test_import_csv_montant_illisible_signale(tmp_path):
    # Un montant illisible ne doit PAS entrer en base à 0 € : la ligne est
    # écartée et comptée dans le 3e élément du résultat.
    db = Database(str(tmp_path / "t.db"))
    csv_path = _write(tmp_path, "bad.csv",
                      "Date;Libelle;Montant\n05/01/2026;Loyer;-800,00\n06/01/2026;Bizarre;1.234,56\n")
    assert import_csv(csv_path, db) == (1, 0, 1, 0, 0, 0)
    assert len(list(db.list_tx())) == 1


def test_import_csv_ecarte_le_recapitulatif_de_debit_differe(tmp_path):
    # Le relevé du compte contient, le jour du prélèvement, une ligne qui
    # totalise les achats carte du mois. Elle ne doit JAMAIS être importée :
    # les achats sont déjà détaillés (demande du 05/08/2026).
    db = Database(str(tmp_path / "t.db"))
    p = _write(tmp_path, "releve.csv",
               "Date;Libelle;Type operation;Categorie;Montant;Pointage operation\n"
               "05/08/2026;DELTAMOBILE;Prelevement;Logement;-78,50;x\n"
               "04/08/2026;DEBIT DIFFERE N° ...1234;Carte bancaire;"
               "Transaction exclue;-1016,31;x\n")
    # 1 importée, 0 doublon, 0 illisible, 0 pointée, 1 récapitulatif écarté
    assert import_csv(p, db) == (1, 0, 0, 0, 1, 0)
    libelles = [dict(r)["libelle"] for r in db.list_tx()]
    assert libelles == ["DELTAMOBILE"]


def test_import_csv_recapitulatif_reconnu_quelle_que_soit_l_ecriture(tmp_path):
    # Même écarté quand la banque écrit le libellé autrement (accents,
    # minuscules, « CUMUL DES DEBITS DIFFERES »).
    db = Database(str(tmp_path / "t.db"))
    p = _write(tmp_path, "releve.csv",
               "Date;Libelle;Montant\n"
               "04/07/2026;Débit différé carte 1234;-100,00\n"
               "04/06/2026;CUMUL DES DEBITS DIFFERES;-200,00\n")
    assert import_csv(p, db) == (0, 0, 0, 0, 2, 0)
    assert len(list(db.list_tx())) == 0


# ── Échéances saisies d'avance rattachées au relevé ──────────────────────────

def _echeance(db, **kw):
    """Insère une échéance prévue (comme « Générer les échéances du mois »)."""
    tx = {"id": "prev-1", "date": "2026-08-10", "date_valeur": "2026-08-10",
          "libelle": "PRETIS", "libelle_op": "PRETIS", "reference": "",
          "type": "Prelevement", "categorie": "Crédits & emprunts",
          "sous_cat": "", "info": "", "montant": -600.00,
          "pointee": 0, "prevue": 1}
    tx.update(kw)
    db.insert_tx(tx)
    return tx


def _releve(tmp_path, lignes: str, nom="releve.csv"):
    p = tmp_path / nom
    p.write_text("Date;Libelle;Montant;Pointage operation\n" + lignes,
                 encoding="utf-8")
    return str(p)


def test_echeance_prevue_rattachee_malgre_le_decalage_de_date(tmp_path):
    """Le cas qui créait un doublon : l'échéance était prévue le 10, la banque
    l'a passée le 12 sous un libellé à elle."""
    db = Database(str(tmp_path / "t.db"))
    _echeance(db)
    p = _releve(tmp_path, "12/08/2026;PRLV SEPA PRETIS 1234567;-600,00;x\n")

    res = import_csv(p, db)
    assert (res.importees, res.rapprochees) == (0, 1)

    txs = [dict(t) for t in db.list_tx()]
    assert len(txs) == 1                    # une seule ligne, pas deux
    t = txs[0]
    assert t["date"] == "2026-08-12"        # date réelle de la banque
    assert t["pointee"] == 1 and t["prevue"] == 0
    assert t["libelle"] == "PRETIS"        # libellé lisible conservé
    assert t["libelle_op"] == "PRLV SEPA PRETIS 1234567"
    assert t["categorie"] == "Crédits & emprunts"   # catégorie du prévisionnel


def test_echeance_prevue_montant_variable(tmp_path):
    """Facture d'électricité : le montant diffère, mais le libellé concorde."""
    db = Database(str(tmp_path / "t.db"))
    _echeance(db, libelle="ENERGIA VERTE", montant=-110.00,
              categorie="Logement", date="2026-08-15", date_valeur="2026-08-15")
    p = _releve(tmp_path, "17/08/2026;ENERGIA VERTE SAS;-125,00;x\n")

    res = import_csv(p, db)
    assert (res.importees, res.rapprochees) == (0, 1)
    t = [dict(x) for x in db.list_tx()][0]
    assert t["montant"] == -125.00          # le montant du relevé l'emporte
    assert t["categorie"] == "Logement"


def test_echeance_prevue_date_exacte_reste_un_doublon_pointe(tmp_path):
    """Quand tout tombe juste, l'ancien filet suffit : la ligne est pointée
    et cesse d'être une prévision."""
    db = Database(str(tmp_path / "t.db"))
    _echeance(db)
    p = _releve(tmp_path, "10/08/2026;PRETIS;-600,00;x\n")

    res = import_csv(p, db)
    assert (res.importees, res.doublons, res.pointees) == (0, 1, 1)
    t = [dict(x) for x in db.list_tx()][0]
    assert t["pointee"] == 1 and t["prevue"] == 0


def test_echeance_prevue_trop_loin_dans_le_temps(tmp_path):
    """Au-delà de la tolérance, aucun rapprochement : la ligne est importée
    normalement (un doublon visible vaut mieux qu'une confusion)."""
    db = Database(str(tmp_path / "t.db"))
    _echeance(db)
    p = _releve(tmp_path, "25/08/2026;PRLV SEPA PRETIS;-600,00;x\n")

    res = import_csv(p, db)
    assert (res.importees, res.rapprochees) == (1, 0)
    assert len(db.list_tx()) == 2


def test_echeance_prevue_ne_capte_pas_une_depense_sans_rapport(tmp_path):
    """Montant et libellé différents : la dépense réelle doit être importée,
    l'échéance rester en attente."""
    db = Database(str(tmp_path / "t.db"))
    _echeance(db)
    p = _releve(tmp_path, "11/08/2026;E-MARCHE;-67,00;x\n")

    res = import_csv(p, db)
    assert (res.importees, res.rapprochees) == (1, 0)
    prevues = [dict(t) for t in db.list_tx() if t["prevue"]]
    assert len(prevues) == 1 and prevues[0]["pointee"] == 0


def test_echeance_prevue_une_seule_ligne_par_echeance(tmp_path):
    """Deux prélèvements du même montant dans la fenêtre ne doivent pas se
    rattacher à la même échéance."""
    db = Database(str(tmp_path / "t.db"))
    _echeance(db)
    _echeance(db, id="prev-2", date="2026-08-11", date_valeur="2026-08-11",
              libelle="PRETIS BIS")
    p = _releve(tmp_path,
                "12/08/2026;PRLV PRETIS;-600,00;x\n"
                "13/08/2026;PRLV PRETIS;-600,00;x\n")

    res = import_csv(p, db)
    assert (res.importees, res.rapprochees) == (0, 2)
    assert len(db.list_tx()) == 2
    assert all(dict(t)["prevue"] == 0 for t in db.list_tx())


def test_echeance_prevue_non_pointee_si_le_releve_ne_confirme_pas(tmp_path):
    """Ligne du relevé encore « en attente » (pas de « x ») : l'échéance est
    complétée mais reste non pointée."""
    db = Database(str(tmp_path / "t.db"))
    _echeance(db)
    p = _releve(tmp_path, "12/08/2026;PRLV SEPA PRETIS;-600,00;\n")

    res = import_csv(p, db)
    assert res.rapprochees == 1
    t = [dict(x) for x in db.list_tx()][0]
    assert t["pointee"] == 0 and t["prevue"] == 0 and t["date"] == "2026-08-12"
