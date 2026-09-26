"""Utilitaires : horodatage, sauvegarde, formatage et normalisation."""
import os
import re
import shutil
import unicodedata
from calendar import monthrange
from collections import Counter
from datetime import date, datetime, timezone
from typing import Optional

from .constants import (
    _app_dir,  # noqa: F401 - réexporté : app.py l'importe d'ici (icône)
    _data_dir,
    DB_PATH,
    CANONICAL_CATS,
    CATEGORY_COLORS,
    _HARMONIZE_COMPILED,
)

def _now_iso() -> str:
    """Horodatage UTC ISO 8601 (comparable lexicalement)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# Nom d'une sauvegarde AUTOMATIQUE : « comptes-AAAA-MM-JJ.db ». Les copies
# faites à la main (« comptes-avant-tel-changement.db ») n'entrent jamais
# dans la rotation : elles sont conservées telles quelles.
_EST_SAUVEGARDE_AUTO = re.compile(r"^comptes-\d{4}-\d{2}-\d{2}\.db$").match


class SauvegardeImpossible(OSError):
    """La copie de sécurité du jour n'a pas pu être faite (disque plein,
    droits refusés…). Le message porte la cause, à montrer à l'utilisateur."""


def sauvegardes_a_garder(noms: list[str], keep: int = 10,
                         mois: int = 12) -> set[str]:
    """Parmi les noms de sauvegardes automatiques (comptes-AAAA-MM-JJ.db),
    celles que la rotation conserve : les `keep` plus récentes, plus la
    PREMIÈRE copie de chacun des `mois` derniers mois (celui de la copie la
    plus récente compris).

    Dix copies quotidiennes ne couvraient que dix jours d'ouverture : une
    erreur découverte trois semaines plus tard n'avait plus de copie saine
    (audit du 23/09/2026). Une copie par mois donne un an de recul pour
    quelques mégaoctets."""
    tries = sorted(noms)
    if not tries:
        return set()
    garder = set(tries[-keep:]) if keep > 0 else set()
    # « comptes-AAAA-MM-JJ.db » : l'année et le mois sont aux positions 8-15.
    an, mo = int(tries[-1][8:12]), int(tries[-1][13:15])
    mois_gardes = set()
    for _ in range(mois):
        mois_gardes.add(f"{an:04d}-{mo:02d}")
        an, mo = (an - 1, 12) if mo == 1 else (an, mo - 1)
    vus = set()
    for nom in tries:                    # du plus ancien au plus récent
        cle = nom[8:15]
        if cle in mois_gardes and cle not in vus:
            vus.add(cle)
            garder.add(nom)
    return garder


def backup_db(path: str = DB_PATH, keep: int = 10) -> Optional[str]:
    """Copie de sécurité QUOTIDIENNE de la base dans « sauvegardes/ ».

    Appelée au lancement, AVANT l'ouverture de la base : même une migration
    ratée ne peut donc pas abîmer la copie. Une seule copie par jour (les
    relances du même jour ne réécrivent pas), rotation selon
    `sauvegardes_a_garder`. Retourne le chemin de la sauvegarde du jour, ou
    None s'il n'y a pas encore de base ; lève SauvegardeImpossible si la copie
    échoue — l'échec était muet (audit du 23/09/2026)."""
    if not os.path.exists(path):
        return None
    # Les sauvegardes suivent la base : même dossier qu'elle, jamais celui du
    # programme, qui est remplacé à chaque mise à jour.
    bdir = os.path.join(_data_dir(), "sauvegardes")
    try:
        os.makedirs(bdir, exist_ok=True)
        dest = os.path.join(bdir, f"comptes-{date.today().isoformat()}.db")
        if not os.path.exists(dest):
            shutil.copy2(path, dest)
        # Rotation : UNIQUEMENT les sauvegardes automatiques, reconnues à leur
        # nom daté (comptes-AAAA-MM-JJ.db), triables lexicalement.
        #
        # Le filtre était « commence par comptes- » : une copie manuelle
        # nommée « comptes-avant-quelque-chose.db » entrait donc dans la
        # rotation, et comme « a » vient après « 2 », elle se classait APRÈS
        # les sauvegardes datées. Dix copies de ce genre suffisaient à faire
        # supprimer, à chaque lancement, la sauvegarde du jour qui venait
        # d'être créée : plus aucune sauvegarde automatique, sans un mot.
        # Constaté le 08/09/2026 sur l'installation d'André.
        baks = [f for f in os.listdir(bdir) if _EST_SAUVEGARDE_AUTO(f)]
        garder = sauvegardes_a_garder(baks, keep)
        for old in baks:
            if old in garder:
                continue
            try:
                os.remove(os.path.join(bdir, old))
            except OSError:
                pass
        return dest
    except OSError as e:
        # Disque plein, droits… : on le dit, sans bloquer le lancement (c'est
        # l'appelant qui prévient l'utilisateur, puis continue).
        raise SauvegardeImpossible(e.strerror or str(e)) from e


def depense_nette_par_categorie(txs: list[dict]) -> dict[str, float]:
    """Ce que chaque catégorie a coûté sur les opérations données : achats
    MOINS remboursements, en positif. Une catégorie qui a reçu autant ou plus
    qu'elle n'a dépensé n'apparaît pas (elle compte pour 0, jamais moins).

    C'est le « dépensé » de tout ce qui se compare à un budget : l'onglet
    Budget, les budgets du rapport mensuel, le bandeau « Budget dépassé ».
    Les remboursements se classent dans la catégorie de l'achat ; ils
    étaient ignorés, et un achat de 60 € remboursé 30 € faisait dépasser un
    budget de 50 € (choix d'André après l'audit du 23/09/2026). Les
    opérations en « Transaction exclue » ne comptent pas."""
    net: dict[str, float] = {}
    for t in txs:
        c = t.get("categorie") or "Non classé"
        if c == "Transaction exclue":
            continue
        net[c] = net.get(c, 0.0) + (t.get("montant") or 0.0)
    return {c: round(-v, 2) for c, v in net.items() if v < -0.005}


def suggest_category(libelle: str, sous_cat: str = "",
                     montant: Optional[float] = None) -> Optional[str]:
    """Retourne la catégorie suggérée d'après libellé/sous-cat, ou None.

    `montant`, quand il est connu, écarte « Revenus » pour une dépense : une
    pension ou un salaire VERSÉS ne sont pas des revenus."""
    blob = deaccent(f"{libelle} {sous_cat}")
    for rx, cat in _HARMONIZE_COMPILED:
        if cat == "Revenus" and montant is not None and montant < 0:
            continue
        if rx.search(blob):
            return cat
    return None


# ── Périodes ────────────────────────────────────────────────────────────────

def in_period(date_iso: str, period: str) -> bool:
    """Période : 'all', 'YYYY', 'YYYY-MM'."""
    if not date_iso:
        return False
    if period == "all":
        return True
    return date_iso.startswith(period)


def list_periods(transactions: list[dict], date_mode: str = "operation") -> list[str]:
    """Retourne la liste triée des périodes présentes : « toutes périodes »,
    puis chaque année de la plus récente à la plus ancienne, **suivie de ses
    propres mois**. Ranger toutes les années d'abord et tous les mois ensuite
    donnait une liste illisible dès qu'on suivait plusieurs années : quatre
    lignes d'années, puis quarante-cinq mois à la file.

    `date_mode` doit être le mode d'affichage choisi dans la barre du haut
    (« operation » ou « valeur »), car les vues filtrent sur cette date-là.
    Sans cela, un achat par carte du 28/07 débité le 04/08 n'apparaîtrait
    dans AUCUN mois en mode « date de valeur » : août ne serait pas proposé
    tant qu'aucune opération n'aurait le 4 août comme date d'opération."""
    years = set()
    months = set()
    for t in transactions:
        if date_mode == "valeur":
            d = t.get("date_valeur") or t.get("date", "")
        else:
            d = t.get("date", "")
        if len(d) >= 7:
            years.add(d[:4])
            months.add(d[:7])
    out = ["all"]
    for annee in sorted(years, reverse=True):
        out.append(annee)
        out += sorted((m for m in months if m[:4] == annee), reverse=True)
    return out


MOIS_FR = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
           "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]


def period_label(p: str) -> str:
    if p == "all":
        return "Toutes périodes"
    if len(p) == 4:
        return f"Année {p}"
    if len(p) == 7:
        try:
            return f"{MOIS_FR[int(p[5:7]) - 1]} {p[:4]}"
        except (ValueError, IndexError):
            return p
    return p


# ── Sélecteur de période en deux menus (année, puis mois) ───────────────────
# Une seule liste finissait par mélanger les années et leurs mois : pour
# atteindre « Mars 2024 » il fallait d'abord choisir l'année, puis rouvrir la
# liste. Coupée en deux et encadrée de deux flèches, elle tient en quelques
# entrées et le geste le plus fréquent — le mois d'avant — se fait en un clic.
# Les valeurs restent celles que in_period a toujours comprises (« all »,
# « 2026 », « 2026-09 ») : les vues ne voient aucune différence.

MOIS_TOUS = "*"      # entrée « Toute l'année » du menu des mois


def nom_mois_fr(period: str) -> str:
    """Nom du mois seul d'une période « 2026-09 » → « Septembre ».

    Le menu des mois n'a pas à répéter l'année : elle est dans le menu d'à
    côté. Retourne la période telle quelle si ce n'en est pas une."""
    if len(period) == 7:
        try:
            return MOIS_FR[int(period[5:7]) - 1]
        except (ValueError, IndexError):
            pass
    return period


def annee_de_periode(period: str) -> Optional[str]:
    """Année portée par une période (« 2026 », « 2026-09 »), ou None pour
    « toutes périodes », qui est à cheval sur toutes les années."""
    if len(period) >= 4 and period[:4].isdigit():
        return period[:4]
    return None


def _mois_des_transactions(transactions: list[dict],
                           date_mode: str = "operation") -> list[str]:
    """Mois « AAAA-MM » présents dans les données, du plus ancien au plus
    récent. Comme list_periods, on lit la date qui sert réellement à filtrer
    (date d'opération ou date de valeur)."""
    mois = set()
    for t in transactions:
        if date_mode == "valeur":
            d = t.get("date_valeur") or t.get("date", "")
        else:
            d = t.get("date", "")
        if len(d) >= 7:
            mois.add(d[:7])
    return sorted(mois)


def annees_disponibles(transactions: list[dict],
                       date_mode: str = "operation") -> list[str]:
    """Contenu du menu de gauche : « all », puis les années de la plus
    récente à la plus ancienne.

    L'année en cours y figure toujours, même sans aucune opération : sinon
    l'application ne pourrait pas s'ouvrir dessus en début d'année."""
    annees = {m[:4] for m in _mois_des_transactions(transactions, date_mode)}
    annees.add(date.today().strftime("%Y"))
    return ["all"] + sorted(annees, reverse=True)


def mois_disponibles(transactions: list[dict], annee: str,
                     date_mode: str = "operation") -> list[str]:
    """Contenu du menu de droite pour une année : « toute l'année », puis les
    mois qui portent des opérations, du plus récent au plus ancien.

    Le mois en cours est toujours proposé, même vide : c'est celui sur lequel
    l'application s'ouvre, et « aucune opération ce mois-ci » est une
    réponse."""
    mois = {m for m in _mois_des_transactions(transactions, date_mode)
            if m[:4] == annee}
    courant = date.today().strftime("%Y-%m")
    if annee == courant[:4]:
        mois.add(courant)
    return [MOIS_TOUS] + sorted(mois, reverse=True)


def _echelle_de_navigation(transactions: list[dict], period: str,
                           date_mode: str = "operation") -> list[str]:
    """Suite ordonnée, du plus ancien au plus récent, dans laquelle les deux
    flèches se déplacent — les mois entre eux, les années entre elles.

    Les mois traversent les années : depuis « Janvier 2026 », la flèche
    gauche mène à « Décembre 2025 »."""
    mois = _mois_des_transactions(transactions, date_mode)
    if len(period) == 7:
        courant = date.today().strftime("%Y-%m")
        return sorted(set(mois) | {courant})
    if len(period) == 4:
        annees = {m[:4] for m in mois}
        annees.add(date.today().strftime("%Y"))
        return sorted(annees)
    return []      # « toutes périodes » n'a ni précédent ni suivant


def periode_voisine(transactions: list[dict], period: str, sens: int,
                    date_mode: str = "operation") -> Optional[str]:
    """Période d'un cran plus ancienne (sens=-1) ou plus récente (sens=+1).

    None quand il n'y a plus rien de ce côté : c'est ce qui grise la flèche,
    plutôt que de la laisser cliquable sans effet."""
    echelle = _echelle_de_navigation(transactions, period, date_mode)
    if period not in echelle:
        return None
    i = echelle.index(period) + sens
    return echelle[i] if 0 <= i < len(echelle) else None


def deaccent(s: str) -> str:
    """Retire accents et passe en minuscule pour normalisation."""
    if not s:
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    ).lower().strip()


def canonical_cat(name: str) -> Optional[str]:
    if not name:
        return None
    key = deaccent(name)
    return CANONICAL_CATS.get(key)


def cat_color(name: str) -> str:
    canon = canonical_cat(name) or name
    return CATEGORY_COLORS.get(canon, "#8A877F")


def fmt_euro(value: float) -> str:
    """Formatage français : 1 234,56 €."""
    s = f"{value:,.2f}".replace(",", " ").replace(".", ",")
    return f"{s} €"


# ── Carte à débit différé ───────────────────────────────────────────────────

JOUR_DEBIT_DIFFERE = 4   # la banque prélève les achats carte le 4 du mois suivant


def est_paiement_carte(type_op: str) -> bool:
    """L'opération est-elle payée par la carte à débit différé ?

    Les imports libellent ce type « Carte bancaire », mais ni la casse ni les
    variantes ne sont garanties selon la banque : on cherche simplement le mot.
    Le Bilan et le Prévisionnel appliquent déjà ce critère pour calculer
    l'encours et la date de débit ; il sert ici à ne pas confondre la date du
    prélèvement groupé avec celle de l'achat."""
    return "carte" in (type_op or "").lower()


# Numéro de chèque tel que la banque l'écrit dans son libellé : « CHEQUE N°
# ...0132 », « CHQ 1234567 ». Les points de suspension disent que la banque a
# tronqué le numéro : on les garde, pour ne pas faire passer 0132 pour le
# numéro entier.
_RE_NUM_CHEQUE = re.compile(r"\b(?:ch[eéè]que|chq)\b[^0-9.]*(\.*\d{3,})",
                            re.IGNORECASE)


def numero_cheque(tx: dict) -> str:
    """Numéro du chèque d'une opération, ou "" si ce n'est pas un chèque.

    Il vient de la colonne « reference » quand elle est remplie (saisi dans
    le formulaire, ou importé d'un fichier QIF), sinon du libellé d'origine de
    la banque. Pour les autres types, « reference » contient un identifiant
    interne de la banque, qui n'a rien d'un numéro de chèque : on ne le montre
    pas."""
    if (tx.get("type") or "").strip() != "Cheque":
        return ""
    ref = (tx.get("reference") or "").strip()
    if ref:
        return ref
    m = _RE_NUM_CHEQUE.search(tx.get("libelle_op") or "")
    return m.group(1) if m else ""


# Au-delà de ce décalage entre l'achat et le débit, ce n'est plus un simple
# week-end (vendredi → lundi) : c'est, le plus souvent, un prélèvement groupé.
DELAI_REPORT_JOURS = 3
# Nombre d'achats carte récents examinés : assez pour ne pas se fier à un cas
# isolé, assez peu pour suivre un changement de carte.
ACHATS_EXAMINES = 30


def _ecart_jours(t: dict) -> Optional[int]:
    """Jours entre la date d'achat et la date de valeur, ou None."""
    try:
        return (date.fromisoformat(t["date_valeur"][:10])
                - date.fromisoformat(t["date"][:10])).days
    except (KeyError, TypeError, ValueError):
        return None


def _achats_carte_reels(operations: list[dict]) -> list[dict]:
    """Achats carte (débits) venus de la banque, du plus récent au plus
    ancien. Les échéances générées par Pécule (« prevue ») sont écartées :
    ce ne sont pas des traces laissées par la banque."""
    achats = [t for t in operations
              if est_paiement_carte(t.get("type"))
              and (t.get("montant") or 0) < 0
              and not t.get("prevue")
              and _ecart_jours(t) is not None]
    return sorted(achats, key=lambda t: t["date"], reverse=True)


def carte_a_debit_differe(operations: list[dict]) -> bool:
    """La carte de ce compte est-elle à débit différé ?

    Reconnu à la trace qu'il laisse dans les données, sans réglage à saisir :
    parmi les derniers achats carte, au moins un sur trois est débité plus
    de trois jours après l'achat. Sur une carte à débit immédiat, c'est
    l'exception (un jour férié, une réservation) : moins d'un achat sur dix.
    Un décalage d'un à trois jours (week-end) arrive aussi sur une carte à
    débit immédiat, et suffisait auparavant à tout faire basculer en débit
    différé ; il ne compte plus.

    Un compte sans la moindre opération carte répond « non », ce qui efface
    les explications et les bandeaux qui n'auraient rien à montrer chez lui."""
    achats = _achats_carte_reels(operations)[:ACHATS_EXAMINES]
    if not achats:
        return False
    reportes = sum(1 for t in achats if _ecart_jours(t) > DELAI_REPORT_JOURS)
    return reportes * 3 >= len(achats)


def regle_debit_differe(operations: list[dict]):
    """Rend une fonction qui date un achat carte à débit différé.

    Chaque banque a son calendrier : le 4 du mois suivant pour l'une, le
    dernier jour ouvré du mois pour une autre (au Crédit Agricole, un achat
    du 10 part le 30 du MÊME mois, un achat du 25 le mois suivant). Plutôt
    qu'un réglage, on le lit dans l'historique du compte :

      - le JOUR du débit est le plus fréquent parmi les prélèvements groupés
        passés (un par lot : un gros lot ne pèse pas plus qu'un petit). Un
        lot repoussé au lundi par un week-end reste l'exception ; à partir du
        28, c'est « la fin du mois », bornée à la longueur de chaque mois ;
      - le DÉCALAGE en mois est le plus fréquent pour les achats faits ce
        jour-là du mois (ou le jour connu le plus proche). Un achat décalé
        d'un lot à la main reste, lui aussi, l'exception.

    Sans historique, la règle habituelle : le 4 du mois suivant."""
    reportes = [t for t in _achats_carte_reels(operations)
                if _ecart_jours(t) > DELAI_REPORT_JOURS][:400]
    if not reportes:
        return date_debit_differe

    lots = Counter(int(d[8:10]) for d in {t["date_valeur"][:10] for t in reportes})
    # À égalité, le jour le plus tôt (min sur le couple -nombre, jour).
    jour_debit = min(lots, key=lambda j: (-lots[j], j))
    fin_de_mois = jour_debit >= 28

    decalages: dict[int, Counter] = {}
    for t in reportes:
        achat = date.fromisoformat(t["date"][:10])
        debit = date.fromisoformat(t["date_valeur"][:10])
        k = (debit.year - achat.year) * 12 + debit.month - achat.month
        decalages.setdefault(achat.day, Counter())[k] += 1

    def dater(date_achat_iso: str) -> str:
        try:
            d = date.fromisoformat((date_achat_iso or "")[:10])
        except (TypeError, ValueError):
            return date_achat_iso or ""
        proche = min(decalages, key=lambda j: (abs(j - d.day), j))
        compte = decalages[proche]
        # Le décalage le plus fréquent ; à égalité, le plus court.
        k = min(compte, key=lambda x: (-compte[x], x))
        rang = d.year * 12 + d.month - 1 + k
        an, mois = rang // 12, rang % 12 + 1
        dernier = monthrange(an, mois)[1]
        jour = dernier if fin_de_mois else min(jour_debit, dernier)
        return date(an, mois, jour).isoformat()
    return dater


def date_debit_differe(date_op_iso: str, jour: int = JOUR_DEBIT_DIFFERE) -> str:
    """Date de valeur d'un achat payé par carte à débit différé.

    La banque regroupe les achats d'un mois et les prélève en une fois le 4
    du mois SUIVANT : un achat du 15/07 est débité le 04/08, un achat du
    02/08 est débité le 04/09. Tant que cette date n'est pas arrivée,
    l'achat ne doit pas peser sur le solde du compte.

    Retourne la date reçue telle quelle si elle est illisible."""
    try:
        d = date.fromisoformat((date_op_iso or "")[:10])
    except (TypeError, ValueError):
        return date_op_iso or ""
    an, mois = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    # Sécurité : un mois court (février) ne va pas jusqu'au 31
    jour = min(max(jour, 1), monthrange(an, mois)[1])
    return date(an, mois, jour).isoformat()


def fmt_date_fr(iso: str) -> str:
    """ISO yyyy-mm-dd → jj/mm/aaaa. Retourne la chaîne telle quelle si non parsable."""
    if not iso or len(iso) < 10:
        return iso or ""
    y, m, d = iso[:4], iso[5:7], iso[8:10]
    return f"{d}/{m}/{y}"


# Types d'opération qui ne peuvent être qu'une rentrée d'argent. Les types
# ambigus (« Virement », « Pret », « Autre », ou vide) n'y sont pas : un
# virement peut être émis comme reçu.
TYPES_RECETTE = ("Virement recu", "Depot d'especes")


def alerte_sens_saisie(type_op: str, categorie: str,
                       montant: float) -> Optional[str]:
    """Avertissement à montrer quand une recette est saisie en dépense.

    Rend le texte de la question à poser, ou None si la saisie est cohérente.

    Incident du 17/09/2026 : un virement reçu de 80 € saisi en dépense. Le
    solde était faux de DEUX fois le montant (80 € en moins au lieu de 80 € en
    plus), et rien ne le signalait. Une recette enregistrée à l'envers est
    toujours une erreur ; on ne contrôle donc QUE ce sens-là. L'inverse — un
    type de dépense avec un montant positif — est courant et légitime
    (remboursement sur la carte, prélèvement rejeté) : avertir là ferait
    crier au loup.
    """
    if not montant or montant >= 0:
        return None
    cat = (categorie or "").strip()
    # Une opération sortie du calcul du solde n'a pas de sens à respecter.
    if cat == "Transaction exclue":
        return None
    est_recette = (type_op or "").strip() in TYPES_RECETTE or cat == "Revenus"
    if not est_recette:
        return None
    quoi = f"« {type_op} »" if (type_op or "").strip() else f"la catégorie « {cat} »"
    return (f"Cette opération ressemble à une recette ({quoi}), mais elle est "
            f"enregistrée en dépense de {fmt_euro(abs(montant))}.\n\n"
            f"Voulez-vous vraiment l'enregistrer en dépense ?")
