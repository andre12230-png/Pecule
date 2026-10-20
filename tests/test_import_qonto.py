"""Import de l'export des opérations de la banque Qonto (constat du
20/10/2026, avec la version 1.41.26).

Pécule refusait le fichier : aucune colonne ne contient « libellé » (Qonto
met le nom du marchand ou de l'émetteur dans « Nom de la contrepartie »).
Autres pièges de ce fichier :

- « Date de la valeur » est VIDE pour les opérations « En cours » : la date
  à prendre est « Date de l'opération (local) » ;
- les dates portent une heure (« 2026-09-05 14:32:10 ») ;
- « Statut » vaut « Exécuté » ou « En cours » : les premières sont passées
  en banque (pointées), les secondes entrent non pointées (choix d'André du
  20/10/2026) et seront pointées au prochain import, une fois exécutées ;
- le montant est « Montant total (TTC) », signé, à ne pas confondre avec
  les colonnes de TVA, « Débit », « Crédit » ou « Solde ».

La page d'aide de Qonto décrit les mêmes colonnes avec des titres anglais
(« Counterparty name », « Operation date (local) »…) : les deux sont lus.

Fichiers fabriqués, valeurs inventées.

    py -m pytest tests/test_import_qonto.py
"""
import pytest

from comptesbudget.csv_import import import_csv
from comptesbudget.database import Database

# En-tête complet de l'export Qonto en français (titres seulement).
ENTETE_FR = (
    "Statut;Date de la valeur (UTC);Date de la valeur (local);"
    "Date de l'opération (UTC);Date de l'opération (local);"
    "Montant total (TTC);Débit;Crédit;Solde;Devise;"
    "Montant total (TTC) (local);Devise (local);Montant total de la TVA;"
    "Montant total (HT);Montant de la TVA (20.0 %);Montant (20.0 % HT);"
    "Nom du compte;IBAN du compte;Nom de la contrepartie;"
    "IBAN de la contrepartie;Méthode de paiement;Nom de la carte;Initiateur;"
    "Identifiant de transaction;Référence;Note;"
    "Catégorie de trésorerie;Sous-catégorie de trésorerie\n")


def _ligne_fr(statut, valeur, operation, montant, contrepartie,
              methode="Carte", reference="", note="", tva=""):
    debit = montant.lstrip("-") if montant.startswith("-") else ""
    credit = "" if montant.startswith("-") else montant
    return ";".join([
        statut, valeur, valeur, operation, operation,
        montant, debit, credit, "1000.0", "EUR",
        montant, "EUR", tva, montant, tva, "",
        "Compte principal", "FR0000000000000000000000000", contrepartie,
        "", methode, "Carte exemple", "Titulaire Exemple",
        "00000000-0000-0000-0000-000000000000", reference, note,
        "Divers", ""]) + "\n"


EXPORT_FR = (
    ENTETE_FR
    + _ligne_fr("En cours", "", "2026-09-28 10:15:00", "-12.5",
                "BOULANGERIE EXEMPLE")
    + _ligne_fr("Exécuté", "2026-09-06 00:00:00", "2026-09-05 14:32:10",
                "-40.0", "SUPERMARCHE EXEMPLE", tva="6.67")
    + _ligne_fr("Exécuté", "2026-09-02 00:00:00", "2026-09-02 09:00:00",
                "500.0", "CLIENT EXEMPLE", methode="Virement",
                reference="FACTURE 100", note="acompte")
)


def _importer(tmp_path, contenu: str, nom="qonto-export.csv", db=None,
              encodage="utf-8"):
    p = tmp_path / nom
    p.write_bytes(contenu.encode(encodage))
    db = db or Database(str(tmp_path / "t.db"))
    resultat = import_csv(str(p), db)
    ops = {t["libelle"].upper(): dict(t) for t in db.list_tx_avec_archives()}
    return resultat, ops, db


def test_les_trois_operations_sont_importees(tmp_path):
    resultat, ops, _ = _importer(tmp_path, EXPORT_FR)
    assert resultat.importees == 3
    assert resultat.illisibles == 0
    assert len(ops) == 3


def test_libelle_pris_dans_le_nom_de_la_contrepartie(tmp_path):
    _, ops, _ = _importer(tmp_path, EXPORT_FR)
    libelles = " | ".join(ops)
    assert "BOULANGERIE EXEMPLE" in libelles
    assert "SUPERMARCHE EXEMPLE" in libelles
    assert "CLIENT EXEMPLE" in libelles


def test_montant_ttc_signe_et_non_la_tva_ni_le_solde(tmp_path):
    _, ops, _ = _importer(tmp_path, EXPORT_FR)
    montants = sorted(round(t["montant"], 2) for t in ops.values())
    assert montants == [-40.0, -12.5, 500.0]


def test_date_de_l_operation_et_date_de_valeur(tmp_path):
    _, ops, _ = _importer(tmp_path, EXPORT_FR)
    achat = next(t for k, t in ops.items() if "SUPERMARCHE" in k)
    assert achat["date"] == "2026-09-05"
    assert achat["date_valeur"] == "2026-09-06"
    # « En cours » : pas de date de valeur, mais la date de l'opération.
    en_cours = next(t for k, t in ops.items() if "BOULANGERIE" in k)
    assert en_cours["date"] == "2026-09-28"


def test_executees_pointees_en_cours_non_pointees(tmp_path):
    _, ops, _ = _importer(tmp_path, EXPORT_FR)
    assert all(t["pointee"] for k, t in ops.items() if "BOULANGERIE" not in k)
    en_cours = next(t for k, t in ops.items() if "BOULANGERIE" in k)
    assert not en_cours["pointee"]


def test_moyen_de_paiement_reference_et_note_gardes(tmp_path):
    _, ops, _ = _importer(tmp_path, EXPORT_FR)
    virement = next(t for k, t in ops.items() if "CLIENT" in k)
    assert virement["type"] == "Virement"
    assert "FACTURE 100" in virement["info"]
    assert "acompte" in virement["info"]


def test_en_cours_pointee_au_prochain_import_sans_doublon(tmp_path):
    _, _, db = _importer(tmp_path, EXPORT_FR, nom="septembre.csv")
    # Export suivant : la boulangerie est désormais exécutée.
    suivant = EXPORT_FR.replace(
        _ligne_fr("En cours", "", "2026-09-28 10:15:00", "-12.5",
                  "BOULANGERIE EXEMPLE"),
        _ligne_fr("Exécuté", "2026-09-29 00:00:00", "2026-09-28 10:15:00",
                  "-12.5", "BOULANGERIE EXEMPLE"))
    resultat, ops, _ = _importer(tmp_path, suivant, nom="octobre.csv", db=db)
    assert resultat.importees == 0
    assert len(ops) == 3
    assert ops["BOULANGERIE EXEMPLE"]["pointee"]


def test_export_aux_titres_anglais_separe_par_des_virgules(tmp_path):
    # Titres de la page d'aide de Qonto ; séparateur et format de date du
    # CSV produit par Qonto non documentés : virgule et date ISO acceptées.
    export = (
        "Status,Transaction ID,Operation date (UTC),Operation date (local),"
        "Settlement date (UTC),Settlement date (local),Counterparty name,"
        "Payment method,Initiator,Category,Reference,Note,"
        "Total amount (incl. VAT),Currency,Total amount (incl. VAT) (local),"
        "Currency (local),Total VAT amount\n"
        "settled,0000-1,2026-09-05 12:00:00,2026-09-05 14:00:00,"
        "2026-09-06 12:00:00,2026-09-06 14:00:00,PHARMACIE EXEMPLE,card,"
        "Titulaire Exemple,,,,-20.00,EUR,-20.00,EUR,0.00\n"
        "processing,0000-2,2026-09-07 08:00:00,2026-09-07 10:00:00,,,"
        "GARAGE EXEMPLE,card,Titulaire Exemple,,,,-150.00,EUR,-150.00,EUR,"
        "25.00\n")
    resultat, ops, _ = _importer(tmp_path, export)
    assert resultat.importees == 2
    assert ops["PHARMACIE EXEMPLE"]["montant"] == pytest.approx(-20.0)
    assert ops["PHARMACIE EXEMPLE"]["date"] == "2026-09-05"
    assert ops["PHARMACIE EXEMPLE"]["pointee"]
    assert ops["GARAGE EXEMPLE"]["date"] == "2026-09-07"
    assert not ops["GARAGE EXEMPLE"]["pointee"]


def test_export_converti_par_excel_dates_a_la_francaise(tmp_path):
    # Le fichier .xlsx de Qonto réenregistré en « CSV (point-virgule) » par
    # Excel : dates « 05/09/2026 14:32 », fichier en Windows-1252.
    export = (ENTETE_FR
              + _ligne_fr("Exécuté", "06/09/2026 00:00", "05/09/2026 14:32",
                          "-40", "SUPERMARCHE EXEMPLE"))
    resultat, ops, _ = _importer(tmp_path, export, encodage="cp1252")
    assert resultat.importees == 1
    assert ops["SUPERMARCHE EXEMPLE"]["date"] == "2026-09-05"
    assert ops["SUPERMARCHE EXEMPLE"]["date_valeur"] == "2026-09-06"
