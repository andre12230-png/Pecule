# -*- coding: utf-8 -*-
"""Audit des opérations récurrentes : confronte ce qui est déclaré à ce qui
passe réellement en banque.

Une récurrence fausse ne se voit pas : le prévisionnel reste plausible. Un
montant revalorisé, un contrat résilié ou une échéance dont la date a glissé
ne remontent jamais d'eux-mêmes. Seule la confrontation aux relevés les
débusque — c'est ce que fait cet outil, dans les deux sens :

  * chaque récurrence est comparée aux opérations réelles des douze derniers
    mois : montant du DERNIER passage, jour médian des TROIS derniers,
    régularité et date du dernier passage sur l'année ;
  * puis la recherche inverse, avec `detect_recurring_candidates` : les
    opérations mensuelles qu'AUCUNE récurrence ne couvre
    (`candidats_non_couverts`, le filtre du bouton « Pré-remplir »).

Le rapprochement utilise `_recurring_norm_label`, la clé de l'application
elle-même, pour raisonner exactement comme elle.

Quatre pièges à connaître avant de conclure — l'outil signale, il ne juge pas :

  1. La médiane sur douze mois garde l'ANCIEN montant (ou l'ancien jour)
     quand il vient de changer : elle signale un faux écart, ou en cache un
     vrai. C'est pourquoi l'outil juge montant et jour sur les derniers
     passages, un par mois (le plus proche du montant prévu).
  2. Un même libellé bancaire peut couvrir plusieurs contrats (un assureur qui
     prélève l'auto, l'habitation et la protection juridique sous un seul nom).
     « Montant instable » ne veut alors rien dire : c'est la sous-catégorie qui
     sépare les contrats.
  3. « N mois sur 12 » ne dit rien sans regarder si ces N mois sont
     CONSÉCUTIFS : six mois d'affilée, c'est un abonnement récent, pas une
     dépense sporadique.
  4. Une récurrence délibérément placée dans le futur (une tranche d'échéances
     à venir) n'a par construction aucune contrepartie dans le passé.

Usage :
    py outils/audit_recurrences.py [chemin/vers/comptes.db] [compte_id]

Sans argument, la base du dossier courant est utilisée et l'audit porte sur le
premier compte. Aucune donnée n'est modifiée : l'outil lit, il n'écrit pas.
"""
import os
import statistics
import sys
from collections import defaultdict
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from comptesbudget.database import Database
from comptesbudget.recurring import (_recurring_norm_label, candidats_non_couverts,
                                     detect_recurring_candidates)

MOIS_HISTORIQUE = 12

# Nombre de passages récents sur lesquels se jugent montant et jour. Impair
# exprès : avec quatre passages dont deux avant un changement de date (28,
# 28, 10, 10), la médiane tombait entre les deux, sur un jour qui n'existe pas.
PASSAGES_RECENTS = 3


def passages_mensuels(r: dict, ops: list[dict]) -> list[dict]:
    """Les passages réels d'une récurrence, un par mois, du plus ancien au
    plus récent.

    `ops` : les opérations qui portent le même libellé normalisé. On n'en
    garde que :
      * celles du même sens — un remboursement n'est pas un prélèvement ;
      * celles de la même sous-catégorie, quand la récurrence en a une et que
        des opérations la portent : un même libellé peut couvrir plusieurs
        contrats, et c'est la sous-catégorie qui les sépare (piège n° 2) ;
      * dans chaque mois, celle dont le montant est le plus proche du montant
        prévu — un petit complément versé sous le même nom ne doit fausser ni
        le montant ni le jour."""
    prevu = r["montant"]
    ops = [t for t in ops if (t["montant"] >= 0) == (prevu >= 0)]
    sc = (r.get("sous_cat") or "").strip().lower()
    if sc:
        memes = [t for t in ops if (t.get("sous_cat") or "").strip().lower() == sc]
        if memes:
            ops = memes
    par_mois: dict[str, dict] = {}
    for t in ops:
        mois = t["date"][:7]
        garde = par_mois.get(mois)
        if garde is None or (abs(abs(t["montant"]) - abs(prevu))
                             < abs(abs(garde["montant"]) - abs(prevu))):
            par_mois[mois] = t
    return [par_mois[m] for m in sorted(par_mois)]


def _ecart_jours(a: int, b: int) -> int:
    """Écart entre deux jours du mois, en tenant compte du passage d'un mois
    à l'autre : une échéance du 1er payée le 30 n'a qu'un ou deux jours
    d'écart, pas 29."""
    ecart = abs(a - b)
    return min(ecart, 31 - ecart)


def auditer(chemin_db: str = None, compte_id: str = None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:      # Python < 3.7, ou flux redirigé
        pass

    db = Database(chemin_db) if chemin_db else Database()
    if compte_id:
        db.compte_id = compte_id
    aujourdhui = date.today()
    debut = (aujourdhui - timedelta(days=365)).isoformat()

    recs = [dict(r) for r in db.list_recurring()]
    txs = [dict(r) for r in db.conn.execute(
        "SELECT * FROM transactions WHERE compte_id = ? AND prevue = 0 "
        "AND date >= ? ORDER BY date", (db.compte_id, debut))]

    if not recs:
        print("Aucune récurrence déclarée sur ce compte : le prévisionnel est "
              "vide. Les candidates ci-dessous sont donc toutes à créer.")

    # Opérations réelles regroupées par libellé normalisé — la même clé que
    # celle qui sert au rapprochement dans l'application.
    reel = defaultdict(list)
    for t in txs:
        cle = _recurring_norm_label(t["libelle"])
        if cle:
            reel[cle].append(t)

    print(f"\n=== Les {len(recs)} récurrences face à {MOIS_HISTORIQUE} mois de "
          f"relevés ===")
    print(f"{'RÉCURRENCE':32} {'PRÉVU':>10} {'RÉEL réc.':>10} {'jour':>5} "
          f"{'mois':>5}  ÉTAT")
    print("-" * 104)

    for r in sorted(recs, key=lambda r: r["libelle"].lower()):
        cle = _recurring_norm_label(r["libelle"])
        prevu = r["montant"]
        # Tranche délibérément placée dans le futur (piège n° 4) : rien à
        # comparer au présent. Sous le même libellé que la tranche en cours,
        # elle récolterait sinon une fausse alerte de montant.
        if (r.get("start_date") or "") > aujourdhui.isoformat():
            print(f"{r['libelle'][:32]:32} {prevu:10.2f} {'—':>10} {'—':>5} "
                  f"{'—':>5}  tranche à venir, à partir du "
                  f"{r['start_date'][8:10]}/{r['start_date'][5:7]}/"
                  f"{r['start_date'][:4]}")
            continue
        ops = passages_mensuels(r, reel.get(cle, []))
        if not ops:
            print(f"{r['libelle'][:32]:32} {prevu:10.2f} {'—':>10} {'—':>5} "
                  f"{0:5}  aucune opération sur la période")
            continue

        # Montant et jour se jugent sur les DERNIERS passages : une médiane
        # sur douze mois garde l'ancien chiffre quand il vient de changer
        # (piège n° 1). Le 23/09/2026, deux versements passés du 7 au 3
        # depuis quatre mois n'avaient pas été signalés : la médiane des
        # douze mois restait au 7.
        recents = ops[-PASSAGES_RECENTS:]
        montants = [t["montant"] for t in ops]
        med = statistics.median(t["montant"] for t in recents)
        jour = int(statistics.median(int(t["date"][8:10]) for t in recents))
        dernier = recents[-1]
        mois = sorted({t["date"][:7] for t in ops})
        derniere = dernier["date"]
        # Consécutifs ? Une couverture partielle mais continue est un contrat
        # récent, pas une dépense sporadique (piège n° 3).
        continus = all(
            (int(b[:4]) - int(a[:4])) * 12 + int(b[5:]) - int(a[5:]) == 1
            for a, b in zip(mois, mois[1:]))

        alertes = []
        # Le montant se compare au DERNIER passage : une revalorisation se
        # voit dès le premier mois où elle s'applique.
        m_der = dernier["montant"]
        if abs(abs(m_der) - abs(prevu)) > max(1.0, 0.02 * abs(prevu)):
            alertes.append(f"MONTANT prévu {prevu:.2f} vs dernier passage "
                           f"{m_der:.2f} le {dernier['date'][8:10]}/"
                           f"{dernier['date'][5:7]} ({m_der - prevu:+.2f})")
        if (r["frequency"] == "monthly" and r["day_of_month"]
                and _ecart_jours(jour, r["day_of_month"]) > 3):
            alertes.append(f"JOUR prévu le {r['day_of_month']} vs réel le "
                           f"{jour} (derniers passages)")
        limite = (aujourdhui - timedelta(days=60)).isoformat()
        if derniere < limite:
            alertes.append(f"plus rien depuis {derniere} — contrat résilié ?")
        if r["frequency"] == "monthly" and len(mois) < 9 and not continus:
            alertes.append(f"IRRÉGULIER : {len(mois)} mois non consécutifs")
        if max(montants) - min(montants) > max(5.0, 0.25 * abs(med)):
            alertes.append(f"variable de {min(montants):.2f} à "
                           f"{max(montants):.2f} — facture ou plusieurs "
                           f"contrats sous ce libellé ?")

        print(f"{r['libelle'][:32]:32} {prevu:10.2f} {med:10.2f} {jour:5} "
              f"{len(mois):5}  {' | '.join(alertes) if alertes else 'ok'}")

    # ── Recherche inverse ────────────────────────────────────────────
    # Même filtre que le bouton « Pré-remplir » : une récurrence couvre aussi
    # l'ancien libellé d'une opération renommée (même montant, même jour).
    manquantes = [c for c in candidats_non_couverts(
                      detect_recurring_candidates(txs, min_months=5), recs)
                  if c["frequency"] == "monthly"]

    print(f"\n=== Opérations mensuelles qu'aucune récurrence ne déclare ===")
    if not manquantes:
        print("Aucune : tout ce qui revient chaque mois est déclaré.")
        return
    print(f"{'LIBELLÉ':32} {'récent':>10} {'mois':>5} {'jour':>5}  fourchette")
    print("-" * 88)
    for c in manquantes:
        stable = "  (stable)" if c["_stable"] else ""
        print(f"{c['libelle'][:32]:32} {c['montant']:10.2f} {c['_months']:5} "
              f"{c['day_of_month']:5}  {c['_min']:.2f} à {c['_max']:.2f}"
              f"{stable}  [{c['categorie']}]")


if __name__ == "__main__":
    auditer(*sys.argv[1:3])
