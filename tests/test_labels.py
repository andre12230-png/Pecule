"""Tests du nettoyage et du profilage des libellés."""
import pytest

from comptesbudget.labels import build_libelle_profiles, charger_alias, clean_libelle


@pytest.fixture
def alias():
    """Installe des correspondances le temps d'un test, puis les retire :
    `charger_alias` agit sur un état global du module."""
    def _installer(mapping):
        charger_alias(mapping)
    yield _installer
    charger_alias({})


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


def test_alias_remplace_la_raison_sociale_par_l_enseigne(alias):
    # Le relevé porte la raison sociale, on veut voir l'enseigne.
    alias({"SODIVAL": "SUPERETTE"})
    assert clean_libelle("SODIVAL") == "Superette"
    # Les numéros de magasin sont retirés avant la correspondance.
    assert clean_libelle("SODIVAL 3193") == "Superette"


def test_alias_insensible_a_la_casse_et_aux_accents(alias):
    alias({"boucherie centrale": "Chez Paul"})
    assert clean_libelle("BOUCHERIE CENTRALE") == "Chez Paul"


def test_alias_donne_la_meme_cle_que_le_nom_deja_enregistre(alias):
    # Point important pour l'import : une opération déjà en base sous le
    # nouveau nom et la même ligne du relevé sous l'ancien doivent produire
    # le même libellé, sinon l'opération serait réimportée en double.
    alias({"SODIVAL": "SUPERETTE"})
    assert clean_libelle("SODIVAL") == clean_libelle("Superette")


def test_sans_alias_le_nettoyage_est_inchange(alias):
    alias({})
    assert clean_libelle("SODIVAL") == "Sodival"
