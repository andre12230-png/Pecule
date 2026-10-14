"""Audit du 14/10/2026, vérification après corrections : A02 reste ouvert.

Un export bien formé mais dont une opération porte un montant « invalide »
(du texte au lieu d'un nombre) était accepté : SQLite l'enregistrait comme
texte, puis le calcul des revenus et des dépenses échouait. Les montants et
les dates de chaque enregistrement sont désormais vérifiés avant la première
écriture. Données inventées.
"""
import sqlite3
from pathlib import Path

import pytest

from comptesbudget.database import Database
from comptesbudget.sync import db_snapshot, merge_remote_into_db, verifier_export


def _op(**kw):
    base = {"id": "x", "date": "2026-06-01", "date_valeur": "2026-06-01",
            "libelle": "OP", "libelle_op": "OP", "reference": "", "type": "",
            "categorie": "Non classé", "sous_cat": "", "info": "",
            "montant": -10.0, "pointee": 1}
    base.update(kw)
    return base


@pytest.fixture
def base(tmp_path):
    db = Database(str(tmp_path / "comptes.db"))
    db.set_setting("initial_date", "2026-01-01")
    db.set_setting("initial_balance", "100.0")
    db.insert_tx(_op(id="a", libelle_op="MAGASIN"))
    return db


def _export(db) -> dict:
    return db_snapshot(db)


# ─────────────────────── Ce qui doit être refusé ───────────────────────────

def _avec_operation(db, **kw):
    donnees = _export(db)
    donnees["transactions"].append(_op(id="n1", **kw))
    return donnees


@pytest.mark.parametrize("champs", [
    {"montant": "invalide"},
    {"montant": None},
    {"montant": True},
    {"montant": float("nan")},
    {"montant": float("inf")},
    {"montant": "12,5"},        # la base le garderait comme texte
    {"montant": "1_000"},       # idem (trouvé à la contre-vérification)
    {"date": "pas une date"},
    {"date": "2026-13-45"},
    {"date": None},
    {"date_valeur": "demain"},
])
def test_une_operation_aux_valeurs_fausses_est_refusee(base, champs):
    assert verifier_export(_avec_operation(base, **champs))


@pytest.mark.parametrize("modifier", [
    lambda d: d["recurring"].append({"id": "r1", "libelle": "LOYER",
                                     "montant": "beaucoup",
                                     "frequency": "monthly",
                                     "start_date": "2026-01-01"}),
    lambda d: d["recurring"].append({"id": "r1", "libelle": "LOYER",
                                     "montant": -50.0, "frequency": "monthly",
                                     "start_date": "bientôt"}),
    lambda d: d["rules"].append({"id": "g1", "pattern": "MAGASIN",
                                 "amount": "dix"}),
    lambda d: d["comptes"][0].update(solde_initial="cent"),
    lambda d: d["comptes"][0].update(date_initiale="hier"),
    lambda d: d.update(budgets={"Alimentation": "trop"}),
    lambda d: d.update(budgets_par_compte={"c1": {"Loisirs": "trop"}}),
    lambda d: d.update(budgets_par_compte={"c1": "pas un objet"}),
])
def test_les_autres_parties_sont_verifiees(base, modifier):
    donnees = _export(base)
    modifier(donnees)
    assert verifier_export(donnees)


def test_le_message_dit_quoi_et_ou(base):
    raison = verifier_export(_avec_operation(base, montant="invalide"))
    assert "montant" in raison
    assert "invalide" in raison


def test_la_fusion_d_un_montant_invalide_ne_touche_a_rien(base):
    """Le scénario exact du rapport : la fusion refuse, la base reste
    intacte et les calculs du budget marchent encore."""
    avant = Path(base.path).read_bytes()
    with pytest.raises(ValueError):
        merge_remote_into_db(base, _avec_operation(base, montant="invalide"))
    base.set_setting("_essai", "1")      # écriture ordinaire juste après
    relue = sqlite3.connect(base.path)
    try:
        types = [r[0] for r in relue.execute(
            "SELECT typeof(montant) FROM transactions")]
    finally:
        relue.close()
    assert types == ["real"]
    assert avant  # la base existait bien avant la tentative


# ─────────────────── Ce qui doit rester accepté ────────────────────────────

def test_un_export_normal_reste_accepte(base):
    assert verifier_export(_export(base)) is None


@pytest.mark.parametrize("champs", [
    {"montant": 12},            # entier
    {"montant": "-12.5"},       # nombre écrit en texte (anciens exports)
    {"date_valeur": None},      # date de valeur absente
    {"date_valeur": ""},
])
def test_les_valeurs_admises_restent_acceptees(base, champs):
    assert verifier_export(_avec_operation(base, **champs)) is None


def test_un_export_d_avant_le_multicomptes_reste_accepte(base):
    ancien = _export(base)
    ancien.pop("comptes")
    ancien.pop("budgets_par_compte")
    ancien["app"] = "comptes_budget.py"
    ancien["budgets"] = {"Alimentation": 300}
    ancien["settings"] = {"initial_balance": "100.0",
                          "initial_date": "2026-01-01"}
    assert verifier_export(ancien) is None


def test_une_regle_sans_montant_et_un_compte_sans_solde_restent_acceptes(base):
    donnees = _export(base)
    donnees["rules"].append({"id": "g1", "pattern": "MAGASIN", "amount": None})
    donnees["comptes"][0]["solde_initial"] = None
    assert verifier_export(donnees) is None


def test_un_montant_en_texte_est_enregistre_comme_nombre(base):
    """Un ancien export au montant écrit « -12.5 » se fusionne et donne
    un vrai nombre dans la base."""
    merge_remote_into_db(base, _avec_operation(base, montant="-12.5"))
    relue = sqlite3.connect(base.path)
    try:
        ligne = relue.execute("SELECT typeof(montant), montant FROM "
                              "transactions WHERE id = 'n1'").fetchone()
    finally:
        relue.close()
    assert ligne == ("real", -12.5)


@pytest.mark.parametrize("ecrit, attendu", [
    ("1e3", 1000.0), ("+12", 12.0), (".5", 0.5), (7, 7.0)])
def test_tout_montant_admis_entre_dans_la_base_comme_nombre(base, ecrit,
                                                            attendu):
    """Contre-vérification : le contrôle et la base ne lisent pas les
    nombres pareil. La fusion convertit donc elle-même chaque montant admis
    avant de l'écrire, opérations, récurrences, règles et comptes."""
    donnees = _avec_operation(base, montant=ecrit)
    donnees["recurring"].append({"id": "r1", "libelle": "LOYER",
                                 "montant": ecrit, "frequency": "monthly",
                                 "start_date": "2026-01-01"})
    donnees["rules"].append({"id": "g1", "pattern": "MAGASIN",
                             "amount": ecrit})
    donnees["comptes"][0].update(solde_initial=ecrit,
                                 updated_at="2099-01-01T00:00:00Z")
    merge_remote_into_db(base, donnees)
    relue = sqlite3.connect(base.path)
    try:
        lignes = [
            relue.execute("SELECT typeof(montant), montant FROM transactions "
                          "WHERE id = 'n1'").fetchone(),
            relue.execute("SELECT typeof(montant), montant FROM recurring "
                          "WHERE id = 'r1'").fetchone(),
            relue.execute("SELECT typeof(amount), amount FROM rules "
                          "WHERE id = 'g1'").fetchone(),
            relue.execute("SELECT typeof(solde_initial), solde_initial FROM "
                          "comptes WHERE id = ?",
                          (donnees["comptes"][0]["id"],)).fetchone(),
        ]
    finally:
        relue.close()
    assert lignes == [("real", attendu)] * 4
