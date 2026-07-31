"""Tests des règles d'auto-catégorisation."""
from comptesbudget.rules import apply_rules_to_tx, matches_rule


def _rule(**kw):
    base = {"pattern": "", "amount": None, "categorie": "", "sous_cat": "",
            "no_overwrite": 0, "sens": ""}
    base.update(kw)
    return base


def test_matches_pattern():
    tx = {"libelle": "OMNISHOP EU SARL", "montant": -20.0}
    assert matches_rule(tx, _rule(pattern="omnishop")) is True
    assert matches_rule(tx, _rule(pattern="livrestore")) is False
    assert matches_rule(tx, _rule(pattern="")) is False   # motif vide → jamais


def test_matches_sens_debit_credit():
    dep = {"libelle": "OMNISHOP", "montant": -20.0}
    rem = {"libelle": "OMNISHOP", "montant": 20.0}
    assert matches_rule(dep, _rule(pattern="omnishop", sens="debit")) is True
    assert matches_rule(rem, _rule(pattern="omnishop", sens="debit")) is False
    assert matches_rule(rem, _rule(pattern="omnishop", sens="credit")) is True
    assert matches_rule(dep, _rule(pattern="omnishop", sens="credit")) is False


def test_matches_amount_tolerance():
    tx = {"libelle": "STREAMFLIX", "montant": -13.00}
    assert matches_rule(tx, _rule(pattern="streamflix", amount=13.00)) is True
    assert matches_rule(tx, _rule(pattern="streamflix", amount=16.00)) is False


def test_apply_simple():
    rules = [_rule(pattern="omnishop", categorie="Shopping")]
    tx = {"libelle": "OMNISHOP", "montant": -10.0, "categorie": "Non classé"}
    modified, fields = apply_rules_to_tx(tx, rules)
    assert modified is True
    assert fields["categorie"] == "Shopping"


def test_apply_no_overwrite():
    rules = [_rule(pattern="omnishop", categorie="Shopping", no_overwrite=1)]
    tx = {"libelle": "OMNISHOP", "montant": -10.0, "categorie": "Alimentation"}
    modified, _ = apply_rules_to_tx(tx, rules)
    assert modified is False   # catégorie déjà posée → on ne touche pas


def test_apply_priorite_montant():
    # Deux règles matchent ; celle qui porte un montant l'emporte.
    rules = [
        _rule(pattern="railexpress", categorie="Transports"),
        _rule(pattern="railexpress", categorie="Loisirs", amount=50.0),
    ]
    tx = {"libelle": "RAILEXPRESS", "montant": -50.0, "categorie": "Non classé"}
    _, fields = apply_rules_to_tx(tx, rules)
    assert fields["categorie"] == "Loisirs"


def test_matches_rule_ignore_les_accents():
    # Les relevés bancaires sont souvent sans accents : une règle « Café »
    # doit reconnaître « CAFE », et inversement.
    tx = {"libelle": "CAFE DE LA GARE", "montant": -12.0}
    assert matches_rule(tx, {"pattern": "café", "sens": "debit"})
    assert matches_rule(tx, {"pattern": "cafe", "sens": "debit"})
    accentue = {"libelle": "Café de la Gare", "montant": -12.0}
    assert matches_rule(accentue, {"pattern": "cafe", "sens": "debit"})
    assert matches_rule(accentue, {"pattern": "café", "sens": "debit"})
