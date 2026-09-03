# -*- coding: utf-8 -*-
"""Audit des opérations récurrentes : confronte ce qui est déclaré à ce qui
passe réellement en banque.

Une récurrence fausse ne se voit pas : le prévisionnel reste plausible. Un
montant revalorisé, un contrat résilié ou une échéance dont la date a glissé
ne remontent jamais d'eux-mêmes. Seule la confrontation aux relevés les
débusque — c'est ce que fait cet outil, dans les deux sens :

  * chaque récurrence est comparée aux opérations réelles des douze derniers
    mois (montant médian, jour du mois, régularité, dernier passage) ;
  * puis la recherche inverse, avec `detect_recurring_candidates` : les
    opérations mensuelles qu'AUCUNE récurrence ne déclare.

Le rapprochement utilise `_recurring_norm_label`, la clé de l'application
elle-même, pour raisonner exactement comme elle.

Quatre pièges à connaître avant de conclure — l'outil signale, il ne juge pas :

  1. La médiane sur douze mois garde l'ANCIEN montant quand celui-ci vient de
     changer, et signale alors un faux écart. Regarder les trois ou quatre
     derniers passages.
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
from comptesbudget.recurring import (_recurring_norm_label,
                                     detect_recurring_candidates)

MOIS_HISTORIQUE = 12


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
    print(f"{'RÉCURRENCE':32} {'PRÉVU':>10} {'RÉEL méd.':>10} {'jour':>5} "
          f"{'mois':>5}  ÉTAT")
    print("-" * 104)

    for r in sorted(recs, key=lambda r: r["libelle"].lower()):
        cle = _recurring_norm_label(r["libelle"])
        # Même sens seulement : un remboursement n'est pas un prélèvement.
        ops = [t for t in reel.get(cle, [])
               if (t["montant"] >= 0) == (r["montant"] >= 0)]
        prevu = r["montant"]
        if not ops:
            print(f"{r['libelle'][:32]:32} {prevu:10.2f} {'—':>10} {'—':>5} "
                  f"{0:5}  aucune opération sur la période")
            continue

        montants = [t["montant"] for t in ops]
        med = statistics.median(montants)
        jour = int(statistics.median(int(t["date"][8:10]) for t in ops))
        mois = sorted({t["date"][:7] for t in ops})
        derniere = max(t["date"] for t in ops)
        # Consécutifs ? Une couverture partielle mais continue est un contrat
        # récent, pas une dépense sporadique (piège n° 3).
        continus = all(
            (int(b[:4]) - int(a[:4])) * 12 + int(b[5:]) - int(a[5:]) == 1
            for a, b in zip(mois, mois[1:]))

        alertes = []
        if abs(abs(med) - abs(prevu)) > max(1.0, 0.02 * abs(med)):
            alertes.append(f"MONTANT prévu {prevu:.2f} vs réel {med:.2f} "
                           f"({med - prevu:+.2f})")
        if (r["frequency"] == "monthly" and r["day_of_month"]
                and abs(jour - r["day_of_month"]) > 3):
            alertes.append(f"JOUR prévu le {r['day_of_month']} vs réel le {jour}")
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
    declares = {_recurring_norm_label(r["libelle"]) for r in recs}
    manquantes = [c for c in detect_recurring_candidates(txs, min_months=5)
                  if _recurring_norm_label(c["libelle"]) not in declares
                  and c["frequency"] == "monthly"]

    print(f"\n=== Opérations mensuelles qu'aucune récurrence ne déclare ===")
    if not manquantes:
        print("Aucune : tout ce qui revient chaque mois est déclaré.")
        return
    print(f"{'LIBELLÉ':32} {'médian':>10} {'mois':>5} {'jour':>5}  fourchette")
    print("-" * 88)
    for c in manquantes:
        stable = "  (stable)" if c["_stable"] else ""
        print(f"{c['libelle'][:32]:32} {c['montant']:10.2f} {c['_months']:5} "
              f"{c['day_of_month']:5}  {c['_min']:.2f} à {c['_max']:.2f}"
              f"{stable}  [{c['categorie']}]")


if __name__ == "__main__":
    auditer(*sys.argv[1:3])
