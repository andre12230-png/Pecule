"""Import des relevés au format QIF (Quicken Interchange Format).

Le QIF est le format d'échange historique des logiciels de comptes
personnels : Microsoft Money, Quicken, Banktivity, GnuCash… savent tous
l'exporter. C'est un simple fichier texte : une ligne par information,
une lettre en tête de ligne qui dit de quoi il s'agit, et un « ^ » seul
qui marque la fin d'une opération.

    !Type:Bank
    D12/08/2026
    T-45,30
    PCARREFOUR MARKET
    MCourses de la semaine
    LAlimentation:Supermarché
    N001234
    C*
    ^

Plutôt que de refaire tout le travail d'import (détection des doublons,
application des règles, pointage automatique, rattachement des échéances
saisies d'avance), ce module se contente de TRADUIRE le QIF en lignes de
relevé bancaire, puis confie le résultat à l'import CSV existant. Il n'y
a donc qu'une seule mécanique d'import à maintenir, et le QIF profite
automatiquement de toutes ses corrections passées et futures.
"""
import csv
import io
import re
from datetime import date
from typing import NamedTuple, Optional

# L'import CSV fournit le décodage de fichier (UTF-8 / Windows-1252) et le
# moteur d'import proprement dit : le QIF s'appuie sur les deux.
from .csv_import import ResultatImport, _decode_csv, import_csv_text
from .database import Database


# Types de blocs QIF qui contiennent des opérations de compte. Les autres
# (« !Type:Cat » liste des catégories, « !Type:Memorized » opérations types,
# « !Type:Prices » cours de bourse…) sont ignorés : ils n'ont ni date ni
# montant et n'ont rien à faire dans un relevé.
TYPES_OPERATIONS = {
    "bank", "banque",      # compte courant
    "cash", "espèces", "especes",
    "ccard",               # carte de crédit
    "oth a", "otha",       # autre actif
    "oth l", "othl",       # autre passif
}


class OperationQif(NamedTuple):
    """Une opération lue dans le fichier QIF, avant traduction en relevé."""
    date: str          # jj/mm/aaaa
    montant: float
    libelle: str
    memo: str
    reference: str
    categorie: str
    sous_cat: str
    pointee: bool
    compte: str        # nom du compte QIF, ou "" si le fichier n'en dit rien


# ── Lecture des montants ────────────────────────────────────────────────────

def parse_montant_qif(s: str) -> Optional[float]:
    """Lit un montant QIF, quel que soit le pays d'origine du fichier.

    Le QIF ne dit nulle part quel séparateur décimal il emploie : un Money
    américain écrit « -1,234.56 » et un Money français « -1.234,56 ». Trois
    règles suffisent à trancher :

      - si le texte contient les DEUX séparateurs, le dernier des deux est
        le séparateur décimal (« 1.234,56 » → 1234,56) ;
      - s'il n'en contient qu'un, suivi d'exactement trois chiffres, c'est
        un séparateur de milliers (« 1,234 » → 1234) : aucun relevé
        bancaire n'affiche trois décimales ;
      - sinon c'est le séparateur décimal (« 45,30 » → 45,30).

    Les montants entre parenthèses sont négatifs (convention comptable
    qu'emploient certains exports). Retourne None si c'est illisible."""
    if s is None:
        return None
    t = s.strip().replace(" ", "").replace("\xa0", "").replace("€", "")
    if not t:
        return None
    negatif = t.startswith("-") or (t.startswith("(") and t.endswith(")"))
    t = t.strip("()").lstrip("+-").strip()
    if not t:
        return None

    dernier_point = t.rfind(".")
    derniere_virgule = t.rfind(",")
    sep = max(dernier_point, derniere_virgule)
    if sep >= 0 and (dernier_point < 0 or derniere_virgule < 0):
        # Un seul type de séparateur : trois chiffres derrière = milliers.
        if len(t) - sep - 1 == 3:
            sep = -1

    if sep >= 0:
        entier = re.sub(r"[.,]", "", t[:sep])
        decimales = t[sep + 1:]
    else:
        entier = re.sub(r"[.,]", "", t)
        decimales = ""
    if (entier and not entier.isdigit()) or (decimales and not decimales.isdigit()):
        return None
    valeur = float(f"{entier or '0'}.{decimales or '0'}")
    return -valeur if negatif else valeur


# ── Lecture des dates ───────────────────────────────────────────────────────

_RE_DATE = re.compile(r"^(\d{1,2})[/\-.](\d{1,2})([/\-.'])(\d{2,4})$")
_RE_DATE_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")


def _composantes_date(s: str):
    """Découpe une date QIF sans encore décider de l'ordre jour/mois.

    Retourne (a, b, année, ambigu) où a et b sont les deux premiers nombres
    dans l'ordre du fichier, ou None si la date est illisible. « ambigu »
    est faux pour les dates déjà sans équivoque (format ISO)."""
    t = (s or "").replace(" ", "")
    m = _RE_DATE_ISO.match(t)
    if m:
        return int(m.group(3)), int(m.group(2)), int(m.group(1)), False
    m = _RE_DATE.match(t)
    if not m:
        return None
    a, b, sep, an = int(m.group(1)), int(m.group(2)), m.group(3), m.group(4)
    annee = int(an)
    if len(an) <= 2:
        # L'apostrophe de Quicken/Money marque les années 2000 (« 12/08'26 ») ;
        # sinon, convention habituelle : 00-69 → 2000+, 70-99 → 1900+.
        annee = 2000 + annee if (sep == "'" or annee < 70) else 1900 + annee
    return a, b, annee, True


def jour_en_premier(composantes: list) -> bool:
    """Le fichier écrit-il jour/mois (Europe) ou mois/jour (États-Unis) ?

    On ne le devine pas ligne par ligne mais sur TOUT le fichier : il suffit
    d'une seule date dont le premier nombre dépasse 12 pour être sûr qu'il
    s'agit d'un jour. À défaut d'indice — un relevé de janvier où tous les
    jours valent 12 ou moins —, on retient jour/mois, l'usage français."""
    for a, b, _annee, ambigu in composantes:
        if ambigu and a > 12:
            return True
    for a, b, _annee, ambigu in composantes:
        if ambigu and b > 12:
            return False
    return True


def _date_francaise(comp, jour_d_abord: bool) -> Optional[str]:
    """Met une date découpée à la forme jj/mm/aaaa attendue par l'import
    CSV. Retourne None si le calendrier la refuse (31 février…)."""
    a, b, annee, ambigu = comp
    # Une date non ambiguë (ISO) est déjà rangée jour puis mois.
    jour, mois = (a, b) if (jour_d_abord or not ambigu) else (b, a)
    try:
        date(annee, mois, jour)
    except ValueError:
        return None
    return f"{jour:02d}/{mois:02d}/{annee:04d}"


# ── Lecture du fichier ──────────────────────────────────────────────────────

def _categorie_et_sous(valeur: str) -> tuple[str, str, str]:
    """Décompose le champ « L » du QIF en (catégorie, sous-catégorie, note).

    Trois formes possibles :
      - « Alimentation:Supermarché » → catégorie et sous-catégorie ;
      - « Alimentation/Vacances »    → la partie après « / » est une
        « classe » Quicken, sans équivalent dans Pécule : écartée ;
      - « [Livret A] »               → ce n'est pas une catégorie mais un
        virement vers un autre compte ; on le signale en note plutôt que
        d'inventer une catégorie qui fausserait le budget."""
    v = (valeur or "").strip()
    if not v:
        return "", "", ""
    if v.startswith("["):
        return "", "", f"Virement : {v.strip('[]')}"
    v = v.split("/", 1)[0].strip()      # on laisse tomber la classe Quicken
    if ":" in v:
        cat, sous = v.split(":", 1)
        return cat.strip(), sous.strip(), ""
    return v, "", ""


def lire_qif(text: str) -> tuple[list[OperationQif], list[str], int]:
    """Lit le contenu d'un fichier QIF.

    Retourne (opérations, comptes rencontrés, nombre d'opérations écartées).
    Une opération est écartée quand sa date ou son montant sont illisibles :
    mieux vaut la signaler que l'enregistrer avec une valeur fausse."""
    brutes = []            # champs bruts, l'ordre jour/mois n'est pas tranché
    comptes = []           # comptes portant réellement des opérations
    dans_comptes = False   # sommes-nous dans un bloc « !Account » ?
    dans_operations = False
    compte_courant = ""
    champs: dict[str, str] = {}

    for ligne in text.splitlines():
        ligne = ligne.strip()
        if not ligne:
            continue

        if ligne.startswith("!"):
            entete = ligne[1:].strip().lower()
            if entete.startswith("account"):
                dans_comptes, dans_operations = True, False
            elif entete.startswith("type:"):
                dans_comptes = False
                dans_operations = entete[5:].strip() in TYPES_OPERATIONS
            # Les autres en-têtes (!Option:AutoSwitch, !Clear:AutoSwitch)
            # n'annoncent aucun contenu : rien à faire.
            champs = {}
            continue

        code, valeur = ligne[0], ligne[1:].strip()

        if code == "^":                     # fin d'enregistrement
            if dans_comptes:
                compte_courant = champs.get("N", "").strip()
            elif dans_operations and champs:
                brutes.append((compte_courant, champs))
                if compte_courant and compte_courant not in comptes:
                    comptes.append(compte_courant)
            champs = {}
            continue

        if code == "M" and "M" in champs:
            champs["M"] += " " + valeur     # mémo écrit sur plusieurs lignes
        elif code not in champs:
            # Première valeur seulement : une opération ventilée sur
            # plusieurs catégories (lignes « S », « E », « $ ») est ramenée
            # à son montant total et à sa première catégorie, Pécule ne
            # sachant pas découper une opération.
            champs[code] = valeur

    # L'ordre jour/mois se décide sur l'ensemble du fichier, pas ligne à ligne.
    composantes = [_composantes_date(c.get("D", "")) for _cpt, c in brutes]
    jour_d_abord = jour_en_premier([c for c in composantes if c])

    operations = []
    illisibles = 0
    for (compte, champs), comp in zip(brutes, composantes):
        d_fr = _date_francaise(comp, jour_d_abord) if comp else None
        # « T » est le montant ; « U » est son doublon dans certains exports.
        montant = parse_montant_qif(champs.get("T") or champs.get("U") or "")
        if d_fr is None or montant is None:
            illisibles += 1
            continue
        cat, sous, note = _categorie_et_sous(champs.get("L", ""))
        memo = champs.get("M", "").strip()
        libelle = (champs.get("P", "").strip() or memo
                   or cat or "(sans libellé)")
        # La note de virement complète le mémo sans l'écraser.
        infos = " — ".join(x for x in (memo, note) if x)
        operations.append(OperationQif(
            date=d_fr,
            montant=montant,
            libelle=libelle,
            memo=infos,
            reference=champs.get("N", "").strip(),
            categorie=cat,
            sous_cat=sous,
            # « * » et « c » = pointé, « X » et « R » = rapproché : dans les
            # deux cas la banque a confirmé l'opération.
            pointee=champs.get("C", "").strip().lower() in ("*", "c", "x", "r"),
            compte=compte,
        ))
    return operations, comptes, illisibles


# ── Traduction en relevé et import ──────────────────────────────────────────

# En-têtes attendus par l'import CSV : ce sont eux qui lui permettent de
# reconnaître chaque colonne par son nom (cf. find_col dans csv_import).
EN_TETES = ["Date", "Date de valeur", "Libelle simplifie", "Montant",
            "Categorie", "Sous categorie", "Reference", "Informations",
            "Type operation", "Pointage operation"]


def qif_vers_csv(operations: list[OperationQif]) -> str:
    """Écrit les opérations QIF sous la forme d'un relevé CSV en mémoire.

    Passer par le CSV plutôt que d'insérer directement en base n'est pas un
    détour inutile : c'est ce qui permet au QIF de bénéficier sans effort de
    toute la mécanique d'import déjà éprouvée."""
    tampon = io.StringIO()
    ecrivain = csv.writer(tampon, delimiter=";", lineterminator="\n")
    ecrivain.writerow(EN_TETES)
    for op in operations:
        ecrivain.writerow([
            op.date,
            op.date,                       # le QIF n'a pas de date de valeur
            op.libelle,
            f"{op.montant:.2f}",
            op.categorie,
            op.sous_cat,
            op.reference,
            op.memo,
            "",                            # le QIF n'a pas de type d'opération
            "x" if op.pointee else "",
        ])
    return tampon.getvalue()


def import_qif(path: str, db: Database) -> ResultatImport:
    """Lit un fichier QIF et insère les opérations. Même compte rendu que
    l'import CSV (cf. ResultatImport)."""
    with open(path, "rb") as f:
        return import_qif_text(_decode_csv(f.read()), db)


def import_qif_text(text: str, db: Database) -> ResultatImport:
    """Cœur de l'import QIF, séparé pour pouvoir être testé sans fichier."""
    operations, comptes, illisibles = lire_qif(text)

    # Pécule suit UN compte par base de données (la table des opérations n'a
    # pas de colonne « compte »). Mélanger deux comptes dans la même base
    # fausserait le solde, le budget et le prévisionnel : mieux vaut refuser
    # franchement que produire des chiffres faux.
    if len(comptes) > 1:
        raise ValueError(
            "ce fichier contient plusieurs comptes (" + ", ".join(comptes)
            + "). Pécule suit un seul compte par base de données : "
            "réexportez un compte à la fois depuis votre logiciel.")
    if not operations:
        raise ValueError(
            "aucune opération lisible dans ce fichier QIF. Vérifiez qu'il "
            "s'agit bien d'un export de compte (« !Type:Bank ») et non "
            "d'une liste de catégories ou de titres.")

    resultat = import_csv_text(qif_vers_csv(operations), db)
    # Les opérations QIF écartées faute de date ou de montant s'ajoutent à
    # celles que l'import CSV a lui-même refusées.
    return resultat._replace(illisibles=resultat.illisibles + illisibles)
