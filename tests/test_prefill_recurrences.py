"""Tests du bouton « Pré-remplir depuis l'historique » du Prévisionnel.

Incident du 23/09/2026 : le bouton balayait tout l'historique, sur des
années, et a fait ajouter une quinzaine de récurrences fausses — des
prélèvements arrêtés depuis longtemps (abonnement résilié, crédit remboursé),
d'anciens noms de récurrences déjà déclarées sous un autre libellé, avec des
montants moyennés sur des années. Le prévisionnel en était lourdement faussé.
"""
from datetime import date

from comptesbudget.recurring import (
    candidats_non_couverts, detect_recurring_candidates,
)


def _mensuelles(libelle, montant, premier, nb, jour=5, **autres):
    """`nb` opérations mensuelles à partir du mois `premier` (« AAAA-MM »)."""
    annee, mois = map(int, premier.split("-"))
    ops = []
    for _ in range(nb):
        ops.append({"date": f"{annee:04d}-{mois:02d}-{jour:02d}",
                    "libelle": libelle, "montant": montant,
                    "categorie": "Abonnements", **autres})
        mois += 1
        if mois > 12:
            annee, mois = annee + 1, 1
    return ops


def _libelles(cands):
    return sorted(c["libelle"] for c in cands)


# ── Ce qui ne passe plus n'est pas proposé ─────────────────────────────────

def test_un_prelevement_arrete_n_est_pas_propose():
    # Un abonnement de 2019 à fin 2023, puis plus rien ; le compte vit jusqu'en 2026.
    ops = (_mensuelles("Streaming", -12.0, "2019-07", 53, jour=7)
           + _mensuelles("Loyer", -800.0, "2026-01", 9))
    assert _libelles(detect_recurring_candidates(ops)) == ["Loyer"]


def test_la_fraicheur_se_mesure_au_dernier_releve_pas_a_aujourdhui():
    # Un utilisateur qui n'a rien importé depuis six mois ne doit pas voir
    # disparaître ses vraies récurrences : on compare à la dernière opération
    # de l'historique, pas à la date du jour.
    ops = _mensuelles("Loyer", -800.0, "2020-01", 12)
    assert _libelles(detect_recurring_candidates(ops)) == ["Loyer"]


def test_une_prevision_ne_compte_pas_comme_un_passage():
    # Une échéance générée d'avance (prevue=1) n'est pas un vrai passage :
    # elle ne doit ni maintenir en vie un prélèvement arrêté, ni décaler la
    # date de référence.
    ops = (_mensuelles("Credit Auto", -300.0, "2025-01", 9, jour=25)
           + _mensuelles("Loyer", -800.0, "2026-01", 9))
    ops.append({"date": "2026-09-25", "libelle": "Credit Auto", "montant": -300.0,
                "categorie": "Transports", "prevue": 1})
    assert _libelles(detect_recurring_candidates(ops)) == ["Loyer"]


def test_un_trimestriel_recent_reste_propose():
    ops = [{"date": d, "libelle": "Eau", "montant": -60.0,
            "categorie": "Logement - maison"}
           for d in ("2025-06-10", "2025-09-10", "2025-12-10",
                     "2026-03-10", "2026-06-10")]
    ops += _mensuelles("Loyer", -800.0, "2026-01", 9)
    assert _libelles(detect_recurring_candidates(ops)) == ["Eau", "Loyer"]


# ── Montant et jour tirés des derniers passages ────────────────────────────

def test_le_montant_est_celui_des_derniers_passages():
    # Une pension revalorisée : la médiane sur trois ans garderait l'ancien
    # montant (cf. mémoire « auditer les récurrences »).
    ops = (_mensuelles("Pension", 1000.0, "2023-01", 30, jour=9)
           + _mensuelles("Pension", 1050.0, "2025-07", 6, jour=9))
    cand, = detect_recurring_candidates(ops)
    assert cand["montant"] == 1050.0


def test_le_jour_est_celui_des_derniers_passages():
    ops = (_mensuelles("Credit", -200.0, "2023-01", 24, jour=28)
           + _mensuelles("Credit", -200.0, "2025-01", 6, jour=10))
    cand, = detect_recurring_candidates(ops)
    assert cand["day_of_month"] == 10


# ── Pré-cochage réservé aux opérations régulières ──────────────────────────

def test_une_depense_occasionnelle_n_est_pas_pre_cochee():
    # Un jeu : même montant, mais à des dates sans régularité.
    ops = [{"date": d, "libelle": "Loterie", "montant": -25.0,
            "categorie": "Loisirs"}
           for d in ("2022-05-24", "2022-11-11", "2023-11-10", "2025-02-06",
                     "2025-03-25", "2025-05-24", "2026-04-17")]
    ops += _mensuelles("Loyer", -800.0, "2026-01", 9)
    jeu = [c for c in detect_recurring_candidates(ops) if c["libelle"] == "Loterie"]
    assert jeu and not jeu[0]["_default"]


def test_un_mensuel_regulier_est_pre_coche():
    cand, = detect_recurring_candidates(_mensuelles("Loyer", -800.0, "2026-01", 9))
    assert cand["_default"]


# ── Ce qu'une récurrence existante couvre déjà n'est pas re-proposé ────────

def _rec(libelle, montant, jour, actif=1):
    return {"libelle": libelle, "montant": montant, "day_of_month": jour,
            "actif": actif}


def test_meme_debut_de_nom_deja_couvert():
    # « Caisse » est le début de « Caisse Retraite », déjà déclarée.
    cands = detect_recurring_candidates(_mensuelles("CAISSE", 10.0, "2026-01", 9, jour=9))
    assert candidats_non_couverts(cands, [_rec("Caisse Retraite", 1000.0, 9)]) == []


def test_meme_montant_meme_jour_deja_couvert():
    # L'ancien nom d'un virement déjà déclaré sous un autre nom.
    cands = detect_recurring_candidates(
        _mensuelles("ANCIEN NOM", -50.0, "2026-01", 9, jour=8))
    assert candidats_non_couverts(cands, [_rec("VIREMENT EPARGNE", -50.0, 9)]) == []


def test_montant_ou_jour_differents_reste_propose():
    cands = detect_recurring_candidates(
        _mensuelles("Telephonie", -7.99, "2026-01", 9, jour=5))
    # Même montant, mais le 17 → deux abonnements distincts.
    assert _libelles(candidats_non_couverts(
        cands, [_rec("Mobile", -7.99, 17)])) == ["Telephonie"]


def test_une_recurrence_desactivee_couvre_aussi():
    # L'utilisateur l'a désactivée exprès : la re-proposer créerait un
    # doublon actif à côté d'elle.
    cands = detect_recurring_candidates(
        _mensuelles("Streaming", -12.0, "2026-01", 9, jour=7))
    assert candidats_non_couverts(
        cands, [_rec("Streaming", -12.0, 7, actif=0)]) == []


def test_signe_oppose_ne_couvre_pas():
    cands = detect_recurring_candidates(
        _mensuelles("Remboursement", 50.0, "2026-01", 9, jour=8))
    assert _libelles(candidats_non_couverts(
        cands, [_rec("VIREMENT EPARGNE", -50.0, 8)])) == ["Remboursement"]
