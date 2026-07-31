"""Tests du nettoyage et du profilage des libellés."""
from comptesbudget.labels import build_libelle_profiles, clean_libelle


def test_clean_fusionne_variantes_numerotees():
    # Deux magasins du même enseigne doivent converger vers la même forme.
    assert clean_libelle("SUPERETTE 3193") == clean_libelle("superette 3852") == "Superette"


def test_clean_retire_suffixe_web():
    assert clean_libelle("OMNISHOP.FR") == "Omnishop"


def test_clean_conserve_sigles():
    assert clean_libelle("SFR MOBILE") == "SFR Mobile"


def test_clean_ne_vide_jamais():
    # Un libellé entièrement numérique ne doit pas devenir vide.
    assert clean_libelle("123456") == "123456"


def test_build_profiles_categorie_et_montant():
    txs = [
        {"libelle": "Superette", "categorie": "Alimentation", "sous_cat": "Courses",
         "type": "Carte bancaire", "montant": -30.0},
        {"libelle": "Superette", "categorie": "Alimentation", "sous_cat": "Courses",
         "type": "Carte bancaire", "montant": -40.0},
        {"libelle": "Superette", "categorie": "Loisirs", "sous_cat": "",
         "type": "Carte bancaire", "montant": -50.0},
    ]
    profiles = build_libelle_profiles(txs)
    p = profiles["Superette"]
    assert p["categorie"] == "Alimentation"   # catégorie majoritaire
    assert p["sous_cat"] == "Courses"
    assert p["montant"] == -40.0              # montant médian


def test_clean_libelle_conserve_les_libelles_sans_commercant():
    # « VIR 123456 » se réduisait à « Vir » : deux virements sans rapport
    # devenaient le même libellé (et donc des doublons à l'import).
    assert clean_libelle("VIR 123456") == "Vir 123456"
    assert clean_libelle("VIR 123456") != clean_libelle("VIR 789012")
    # Les enseignes continuent de fusionner normalement
    assert clean_libelle("SUPERETTE 3193") == clean_libelle("superette 3852") == "Superette"
    assert clean_libelle("PRLV SEPA 20260715 EDF") == "Prlv Sepa EDF"
