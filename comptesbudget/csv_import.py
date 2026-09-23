"""Import des relevés bancaires au format CSV (BPCE / CM / CA)."""
import csv
import io
import json
import re
from calendar import monthrange
from collections import Counter
from datetime import date, timedelta
from typing import NamedTuple, Optional

from .utils import (canonical_cat, deaccent, est_paiement_carte,
                    suggest_category)
from .labels import build_libelle_profiles, clean_libelle
from .recurring import _meme_operation, _recurring_norm_label
from .rules import apply_rules_to_tx
from .database import Database


class ResultatImport(NamedTuple):
    """Compte rendu d'un import, pour le message affiché à l'utilisateur."""
    importees: int      # nouvelles lignes enregistrées
    doublons: int       # lignes du relevé déjà présentes, ignorées
    illisibles: int     # lignes écartées : montant impossible à lire
    pointees: int       # opérations déjà en base pointées d'après le relevé
    recaps: int         # récapitulatifs de débit différé écartés
    rapprochees: int    # échéances prévues rattachées à leur ligne réelle

def _parse_amount_checked(s: str) -> tuple[float, bool]:
    """Analyse un montant « à la française ». Renvoie (montant, lisible) :
    un champ vide est lisible (montant 0) ; un texte non vide impossible à
    interpréter renvoie (0.0, False), pour que l'appelant puisse le signaler
    au lieu d'enregistrer silencieusement 0 €."""
    if not s or not s.strip():
        return 0.0, True
    t = s.strip().replace(" ", "").replace("\xa0", "").replace(",", ".")
    if t.startswith("+"):
        t = t[1:]
    try:
        return float(t), True
    except ValueError:
        return 0.0, False


def parse_french_amount(s: str) -> float:
    return _parse_amount_checked(s)[0]


def parse_french_date(s: str) -> Optional[str]:
    if not s:
        return None
    s = s.strip()
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", s)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return None


def _tx_identity(date_iso: str, montant, reference: str, libelle: str) -> str:
    """Clé d'identité stable d'une opération, **indépendante de sa position**
    dans le fichier : référence bancaire si présente, sinon libellé normalisé.
    Sert de base à l'ID. ATTENTION : pour DÉTECTER les doublons, cette clé ne
    suffit pas (cf. _identity_libelle) — une opération saisie à la main n'a
    pas de référence alors que le relevé en a une."""
    ident = (reference or "").strip() or clean_libelle(libelle)
    return f"{date_iso}|{float(montant or 0):.2f}|{ident}"


def _identity_libelle(date_iso: str, montant, libelle: str) -> str:
    """Clé d'identité par libellé nettoyé — calculable pour TOUTE opération,
    qu'elle vienne d'un relevé (libellé brut « CAISSE COMP ») ou d'une saisie
    manuelle / harmonisation (« Caisse Comp ») : clean_libelle unifie les deux."""
    return f"{date_iso}|{float(montant or 0):.2f}|{clean_libelle(libelle)}"


# Décalage toléré, en jours, entre une échéance saisie d'avance et son passage
# réel en banque : un prélèvement annoncé le 10 peut tomber le 12 (week-end,
# jour férié, délais interbancaires).
JOURS_TOLERANCE_ECHEANCE = 7


def _ecart_jours(a_iso: str, b_iso: str) -> Optional[int]:
    """Nombre de jours entre deux dates ISO, ou None si l'une est illisible."""
    try:
        return abs((date.fromisoformat(a_iso[:10])
                    - date.fromisoformat(b_iso[:10])).days)
    except (TypeError, ValueError):
        return None


def trouver_echeance_prevue(prevues: list[dict], d_iso: str, montant: float,
                            libelle: str,
                            tolerance: int = JOURS_TOLERANCE_ECHEANCE) -> Optional[dict]:
    """Échéance saisie d'avance que cette ligne du relevé vient confirmer.

    Deux façons de se reconnaître, la première étant prioritaire :

      1. **même montant** au centime près, à quelques jours près — le libellé
         de la banque est souvent méconnaissable (« PRETIS » arrive en
         « PRLV SEPA PRETIS 1234567 ») ;
      2. **libellé compatible** et même sens, à quelques jours près — pour les
         échéances dont le montant varie d'un mois à l'autre (électricité,
         téléphone).

    À égalité, la plus proche en date l'emporte. Retourne None si rien ne
    correspond : mieux vaut un doublon visible qu'une dépense avalée."""
    cle_csv = _recurring_norm_label(libelle)
    candidates = []
    for p in prevues:
        if p.get("_consommee"):
            continue
        ecart = _ecart_jours(d_iso, p.get("date", ""))
        if ecart is None or ecart > tolerance:
            continue
        m_prev = float(p.get("montant", 0) or 0)
        if abs(m_prev - float(montant or 0)) < 0.005:
            rang = 0
        elif ((m_prev >= 0) == (float(montant or 0) >= 0) and cle_csv
              and _meme_operation(_recurring_norm_label(p.get("libelle", "")),
                                  cle_csv)):
            rang = 1
        else:
            continue
        candidates.append((rang, ecart, p))
    if not candidates:
        return None
    candidates.sort(key=lambda c: (c[0], c[1]))
    return candidates[0][2]


# Libellés des lignes RÉCAPITULATIVES du débit différé de la carte. Le jour du
# prélèvement, la banque ajoute au relevé du compte une ligne qui totalise tous
# les achats carte du mois (« DEBIT DIFFERE N° ...1234 » / « CUMUL DES DEBITS
# DIFFERES ») — alors que ces mêmes achats y figurent déjà un par un. L'importer
# ferait compter deux fois les mêmes dépenses : ces lignes sont écartées dès la
# lecture du fichier (demande de l'utilisateur du 05/08/2026).
MOTIFS_RECAP_DEBIT_DIFFERE = ("debit differe", "debits differes",
                              "depenses carte")

# Ces mots-là désignent un FRAIS de la banque, jamais un récapitulatif. La
# cotisation annuelle de la carte s'intitule « Fourniture d'une carte de débit
# International à débit différé » : elle contient donc, par accident, un motif
# de la liste ci-dessus. Sans cette exception, ce vrai débit disparaissait du
# relevé (la cotisation perdue sur un relevé Crédit Agricole, le 16/09/2026).
MOTIFS_JAMAIS_RECAP = ("cotisation", "fourniture")


def est_recap_debit_differe(libelle: str) -> bool:
    """Vrai si ce libellé de relevé est un récapitulatif de débit différé
    (cf. le commentaire ci-dessus). Comparaison sans accents ni majuscules,
    pour reconnaître aussi bien « DEBIT DIFFERE » que « Débit différé »."""
    lb = deaccent(libelle or "")
    if any(m in lb for m in MOTIFS_JAMAIS_RECAP):
        return False
    return any(m in lb for m in MOTIFS_RECAP_DEBIT_DIFFERE)


def _aplatir(cellule: str) -> str:
    """Ramène une cellule sur UNE seule ligne : retours à la ligne et suites
    d'espaces deviennent un espace simple."""
    return re.sub(r"\s+", " ", cellule or "").strip()


# Combien des lignes d'un libellé multiligne portent le SENS de l'opération.
# Le Crédit Agricole écrit d'abord la nature (« Prélèvement »), puis le tiers
# (« SFR - SFR - SFR Prlvt SEPA… ») ; les lignes suivantes ne sont que des
# références SEPA (identifiant du créancier, numéro de mandat) — à conserver,
# mais illisibles au milieu d'une liste d'opérations.
LIGNES_UTILES_LIBELLE = 2


def _decouper_libelle(brut: str) -> tuple[str, str]:
    """Sépare un libellé de relevé en (libellé lisible, références).

    La plupart des banques tiennent sur une seule ligne : le libellé revient
    tel quel et les références sont vides. Le Crédit Agricole, lui, écrit son
    libellé sur plusieurs lignes entre guillemets."""
    morceaux = [m for m in (brut or "").splitlines() if m.strip()]
    if not morceaux:
        return "", ""
    libelle = _aplatir(" ".join(morceaux[:LIGNES_UTILES_LIBELLE]))
    return libelle, _aplatir(" ".join(morceaux[LIGNES_UTILES_LIBELLE:]))


# ── Crédit Agricole : les achats carte et le lot annoncé ──────────────────
#
# Le bas du relevé détaille les achats carte, lot par lot, chaque lot sous une
# ligne « Encours débité le 31 août 2026 ». Ces achats n'ont pas de colonne
# Type : sans ce repère, rien ne dit que ce sont des paiements par carte, ni
# quand la banque les a prélevés. Le haut du relevé annonce le lot suivant
# (« Encours sur 1 carte(s) débité(s) en septembre; 764,10 € »), sans en
# donner le détail.

TYPE_CARTE = "Carte bancaire"

MOIS_FR = {"janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5,
           "juin": 6, "juillet": 7, "aout": 8, "septembre": 9,
           "octobre": 10, "novembre": 11, "decembre": 12}

_RE_LOT_DEBITE = re.compile(r"encours debite le (\d{1,2}) (\w+) (\d{4})")
_RE_LOT_ANNONCE = re.compile(
    r"encours sur \d+ carte\(s\) debite\(s\) en (\w+)\s*;\s*([-\d\s.,]+)")
_RE_DATE_RELEVE = re.compile(r"(?:solde au|telechargement du) (\d{2}/\d{2}/\d{4})")


def _date_lot_debite(cellule: str) -> Optional[str]:
    """« Encours débité le 31 août 2026 » → « 2026-08-31 », sinon None."""
    m = _RE_LOT_DEBITE.search(deaccent(_aplatir(cellule)))
    if not m or m.group(2) not in MOIS_FR:
        return None
    try:
        return date(int(m.group(3)), MOIS_FR[m.group(2)],
                    int(m.group(1))).isoformat()
    except ValueError:
        return None


def _dernier_jour_ouvre(an: int, mois: int) -> date:
    """Dernier jour du mois qui ne tombe ni un samedi ni un dimanche : c'est
    le jour où le Crédit Agricole prélève le lot (vu sur huit mois de relevé :
    le 27/02/2026 et le 29/05/2026 étaient des vendredis)."""
    j = date(an, mois, monthrange(an, mois)[1])
    while j.weekday() >= 5:
        j -= timedelta(days=1)
    return j


def lire_lot_annonce(texte: str) -> Optional[dict]:
    """Lot carte annoncé en tête d'un relevé Crédit Agricole, ou None.

    Retourne {"montant": -764.10, "debit": "2026-09-30",
    "releve": "2026-09-15"} : le montant en négatif (c'est une dépense), le
    jour probable du prélèvement, et la date du relevé."""
    plat = deaccent(texte or "")
    m = _RE_LOT_ANNONCE.search(plat)
    d = _RE_DATE_RELEVE.search(plat)
    if not m or not d or m.group(1) not in MOIS_FR:
        return None
    montant, lisible = _parse_amount_checked(m.group(2))
    releve = parse_french_date(d.group(1))
    if not lisible or not releve:
        return None
    an, mois_releve = int(releve[:4]), int(releve[5:7])
    mois = MOIS_FR[m.group(1)]
    if mois < mois_releve:          # « débité en janvier » sur un relevé de décembre
        an += 1
    return {"montant": -abs(round(montant, 2)),
            "debit": _dernier_jour_ouvre(an, mois).isoformat(),
            "releve": releve}


def _cle_lot_annonce(db: Database) -> str:
    # Le lot appartient à un compte : un réglage par compte.
    return f"encours_carte_annonce|{db.compte_id}"


def encours_carte_annonce(db: Database) -> Optional[dict]:
    """Lot carte annoncé par la banque au dernier import de ce compte, ou None."""
    brut = db.get_setting(_cle_lot_annonce(db), "")
    try:
        lot = json.loads(brut) if brut else None
    except ValueError:
        return None
    return lot if isinstance(lot, dict) and "montant" in lot else None


def _decode_csv(raw: bytes) -> str:
    """Décode un relevé bancaire. L'UTF-8 est essayé d'abord : un fichier
    Windows-1252 contenant des accents n'est pratiquement jamais de l'UTF-8
    valide, donc si le décodage réussit c'est bien de l'UTF-8 (ou de l'ASCII
    pur, identique dans les deux cas). Sinon, Windows-1252 — l'encodage
    habituel des banques françaises — puis latin-1 en dernier recours
    (celui-ci ne peut pas échouer)."""
    try:
        return raw.decode("utf-8-sig")   # « -sig » : ignore un éventuel BOM
    except UnicodeDecodeError:
        pass
    try:
        return raw.decode("cp1252")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


# ──────────── Pourquoi ce relevé n'a-t-il rien donné ? ────────────
# Un import qui échoue vient presque toujours de la FORME du fichier, pas de
# son contenu. Plutôt qu'un « En-tête CSV introuvable » sec, on dit à
# l'utilisateur ce qu'il doit corriger. Les mêmes explications figurent sur
# la page « Mon relevé ne s'importe pas » du site.

AIDE_ENTETE = (
    "Ajoutez (ou renommez) la première ligne du fichier pour qu'elle nomme "
    "les colonnes ; le minimum tient en trois mots :\n\n"
    "    Date;Libelle;Montant\n\n"
    "Les accents et les majuscules n'ont pas d'importance, et vous pouvez "
    "garder vos autres colonnes.")


def diagnostiquer_releve(texte: str) -> Optional[str]:
    """Explication en clair quand un relevé ne donne rien, sinon None.

    Trois causes couvrent la quasi-totalité des cas : le fichier est séparé
    par des virgules (export anglo-saxon), ses colonnes portent d'autres noms
    (« label », « description »…), ou ses dates ne sont pas au format
    JJ/MM/AAAA — auquel cas chaque ligne est écartée en silence."""
    lignes = [ln for ln in texte.splitlines() if ln.strip()]
    if not lignes:
        return "Le fichier est vide."

    entete = None
    for ln in lignes:
        bas = deaccent(ln)
        if "date" in bas and "libelle" in bas:
            entete = ln
            break

    if entete is None:
        # Séparateur : plus de virgules que de points-virgules sur l'ensemble.
        echantillon = "\n".join(lignes[:20])
        if echantillon.count(",") > echantillon.count(";"):
            return ("Les colonnes de ce fichier sont séparées par des "
                    "VIRGULES ; Pécule attend des points-virgules.\n\n"
                    "Ouvrez-le dans votre tableur, puis « Enregistrer sous » "
                    "en choisissant « CSV (séparateur : point-virgule) »."
                    "\n\n" + AIDE_ENTETE)
        return ("Aucune ligne de ce fichier ne nomme les colonnes « date » et "
                "« libellé » : Pécule ne peut pas deviner à quoi correspond "
                "chaque colonne.\n\n" + AIDE_ENTETE)

    # En-tête reconnue : reste le format des dates.
    colonnes = [deaccent(h) for h in entete.split(";")]
    i_date = next((i for i, h in enumerate(colonnes) if "date" in h), -1)
    exemples = []
    for ln in lignes[lignes.index(entete) + 1:]:
        cellules = ln.split(";")
        if 0 <= i_date < len(cellules):
            valeur = cellules[i_date].strip()
            if valeur:
                exemples.append(valeur)
        if len(exemples) >= 5:
            break
    if exemples and not any(parse_french_date(v) for v in exemples):
        return ("Les dates de ce relevé (« " + exemples[0] + " ») ne sont pas "
                "au format attendu : il faut JJ/MM/AAAA, par exemple "
                "05/01/2026 — jour et mois sur deux chiffres, année sur "
                "quatre.\n\n"
                "Chaque ligne concernée est écartée, d'où un import à zéro "
                "opération. Corrigez le format des dates dans votre tableur "
                "avant de réenregistrer le fichier en CSV.")
    return None


def diagnostiquer_fichier(path: str) -> Optional[str]:
    """Même diagnostic que `diagnostiquer_releve`, à partir d'un fichier.
    Appelé quand un import s'est terminé sans lire la moindre opération."""
    try:
        with open(path, "rb") as f:
            return diagnostiquer_releve(_decode_csv(f.read()))
    except OSError:
        return None


def import_csv(path: str, db: Database) -> ResultatImport:
    """Lit un CSV bancaire français et insère les transactions.
    Retourne un ResultatImport (cf. la description de ses six compteurs)."""
    with open(path, "rb") as f:
        return import_csv_text(_decode_csv(f.read()), db)


def import_csv_text(text: str, db: Database) -> ResultatImport:
    """Import proprement dit, à partir du CONTENU du relevé déjà décodé.

    Séparé de import_csv pour que l'import QIF (qif_import.py) réutilise
    exactement la même mécanique — doublons, règles, pointage automatique,
    rattachement des échéances prévues — après avoir traduit le fichier
    QIF en lignes de relevé."""
    lines = [l for l in text.splitlines() if l.strip()]
    # Trouver la ligne d'en-tête
    header_idx = None
    for i, line in enumerate(lines):
        low = deaccent(line)
        if "date" in low and ("libelle" in low or "libellé" in low.lower()):
            header_idx = i
            break
    if header_idx is None:
        # Le diagnostic dit la cause probable ; à défaut, l'aide générale.
        raise ValueError(diagnostiquer_releve(text)
                         or ("En-tête introuvable." + "\n\n" + AIDE_ENTETE))

    # Le lecteur reçoit un TEXTE, et non la liste des lignes : ainsi un libellé
    # écrit sur plusieurs lignes entre guillemets — le cas du Crédit Agricole —
    # garde ses retours à la ligne, au lieu d'être recollé bout à bout en un
    # seul mot (« PrelevementSFR - SFR - SFR Prlvt… »).
    reader = csv.reader(io.StringIO("\n".join(lines[header_idx:])),
                        delimiter=";")
    rows = list(reader)
    headers = [deaccent(_aplatir(h)) for h in rows[0]]

    def find_col(keywords: list[str]) -> int:
        for i, h in enumerate(headers):
            if all(k in h for k in keywords):
                return i
        return -1

    iDate = find_col(["date"])
    iDateVal = -1
    for i, h in enumerate(headers):
        if "valeur" in h:
            iDateVal = i
            break
    iLib = find_col(["libelle"])
    iMontant = find_col(["montant"])
    iDebit = find_col(["debit"])
    iCredit = find_col(["credit"])
    if iMontant < 0 and iDebit < 0 and iCredit < 0:
        # Sans colonne de montant, chaque ligne entrait à 0,00 € sans un mot
        # et le solde était faux (audit du 23/09/2026). On refuse l'import,
        # comme pour un en-tête introuvable, en citant les colonnes lues.
        trouvees = ", ".join(f"« {_aplatir(h).strip()} »"
                             for h in rows[0] if h.strip())
        raise ValueError(
            "Aucune colonne de ce relevé ne donne le montant des opérations "
            f"(colonnes trouvées : {trouvees}). Aucune opération n'a été "
            "importée.\n\n"
            "Pécule cherche une colonne nommée « Montant », ou deux colonnes "
            "« Débit » et « Crédit ». Renommez-la dans votre tableur, puis "
            "réenregistrez le fichier en CSV (séparateur : point-virgule).")
    iCat = find_col(["categorie"])
    iSub = find_col(["sous"])
    iRef = find_col(["reference"])
    iInfo = find_col(["informations"])
    iType = -1
    for i, h in enumerate(headers):
        if h in ("type", "type d'operation", "type operation"):
            iType = i
            break

    # Colonne « Pointage operation » de certaines banques (BPCE…) :
    # « x » = opération passée en banque, autre chose = en attente.
    iPtg = find_col(["pointage"])
    # La plupart des banques ne fournissent PAS cette colonne. Leur relevé ne
    # porte alors que des opérations déjà passées en banque : toutes sont donc
    # pointées, exactement comme celles venues d'un OFX. Sans cela, le « solde
    # bancaire réel » du Bilan — qui ne compte que les opérations pointées —
    # restait figé sur le solde de départ après l'import, et il fallait
    # pointer chaque ligne à la main.
    releve_sans_colonne_pointage = iPtg < 0

    def _date_et_montant(cols) -> tuple:
        """Date ISO et montant d'une ligne du relevé, sans rien enregistrer.
        Retourne (date_iso ou None, montant, lisible). Sert deux fois : au
        pré-comptage ci-dessous, puis à l'import proprement dit."""
        if not cols or iDate < 0 or iDate >= len(cols):
            return None, 0.0, True
        d_iso = parse_french_date(cols[iDate])
        if not d_iso:
            return None, 0.0, True
        if 0 <= iMontant < len(cols):
            montant, lisible = _parse_amount_checked(cols[iMontant])
        else:
            d, ok_d = _parse_amount_checked(cols[iDebit]) if 0 <= iDebit < len(cols) else (0.0, True)
            c, ok_c = _parse_amount_checked(cols[iCredit]) if 0 <= iCredit < len(cols) else (0.0, True)
            # Le débit est souvent saisi négatif
            if d > 0:
                d = -d
            montant = d + c
            lisible = ok_d and ok_c
        return d_iso, montant, lisible

    def _libelle(cols) -> str:
        """Libellé lisible d'une ligne du relevé, sans ses références."""
        return _decouper_libelle(cols[iLib] if 0 <= iLib < len(cols) else "")[0]

    # Combien de lignes du RELEVÉ portent chaque couple date+montant ? Sert à
    # désamorcer le filet « saisie manuelle » plus bas quand il y a ambiguïté.
    # Les récapitulatifs de débit différé, jamais importés, en sont exclus.
    csv_par_dm: Counter = Counter()
    for cols in rows[1:]:
        if est_recap_debit_differe(_libelle(cols)):
            continue
        d_iso, montant, lisible = _date_et_montant(cols)
        if d_iso and lisible:
            csv_par_dm[f"{d_iso}|{montant:.2f}"] += 1

    rules = [dict(r) for r in db.list_rules()]
    existing_tx = [dict(r) for r in db.list_tx()]
    # Multiplicité des opérations déjà en base, sous DEUX clés d'identité :
    # par référence bancaire (quand la ligne en a une) ET par libellé nettoyé.
    # Correspondre à l'une OU l'autre suffit pour être un doublon — sinon une
    # opération saisie à la main (sans référence) est réimportée en double
    # depuis le relevé (bug du 11/07/2026), et inversement si la banque change
    # ses références d'un export à l'autre. Recalculé depuis les champs
    # stockés : valable même pour les imports des versions antérieures.
    existing_by_ref = Counter(
        _tx_identity(t.get("date", ""), t.get("montant", 0),
                     t.get("reference", ""), t.get("libelle", ""))
        for t in existing_tx if (t.get("reference") or "").strip())
    existing_by_lbl = Counter(
        _identity_libelle(t.get("date", ""), t.get("montant", 0),
                          t.get("libelle", ""))
        for t in existing_tx)
    # Troisième filet, réservé aux SAISIES MANUELLES (id sans « | », donc
    # UUID) : même date + même montant suffisent, quel que soit le libellé.
    # L'utilisateur nomme ses saisies à sa façon (« Omnishop ») alors que la
    # banque écrit autre chose (« CREDIPLUS ») — indétectable par libellé
    # (incident du 14/07/2026). Volontairement limité aux saisies manuelles :
    # entre deux opérations importées, deux achats distincts du même jour au
    # même montant restent bien deux opérations.
    existing_by_dm = Counter(
        f"{t.get('date', '')}|{float(t.get('montant', 0) or 0):.2f}"
        for t in existing_tx if "|" not in (t.get("id") or ""))
    # Lignes existantes indexées par les mêmes clés, pour pouvoir POINTER une
    # opération déjà en base quand la banque la marque passée (« x »).
    rows_by_ref: dict[str, list[dict]] = {}
    rows_by_lbl: dict[str, list[dict]] = {}
    rows_by_dm: dict[str, list[dict]] = {}
    for t in existing_tx:
        if (t.get("reference") or "").strip():
            k = _tx_identity(t.get("date", ""), t.get("montant", 0),
                             t.get("reference", ""), t.get("libelle", ""))
            rows_by_ref.setdefault(k, []).append(t)
        k = _identity_libelle(t.get("date", ""), t.get("montant", 0),
                              t.get("libelle", ""))
        rows_by_lbl.setdefault(k, []).append(t)
        if "|" not in (t.get("id") or ""):
            k = f"{t.get('date', '')}|{float(t.get('montant', 0) or 0):.2f}"
            rows_by_dm.setdefault(k, []).append(t)

    def _premiere_non_pointee(rows):
        for r in rows or []:
            if not r.get("pointee"):
                return r
        return None

    # Échéances saisies d'avance et encore en attente : elles seront
    # rattachées à leur ligne du relevé au lieu d'être doublonnées.
    prevues = [t for t in existing_tx if t.get("prevue") and not t.get("pointee")]
    # Profils habituels par libellé (indexés sur la forme nettoyée), pour
    # hériter de la catégorie/sous-catégorie d'un libellé déjà connu.
    profiles = build_libelle_profiles(existing_tx, key_fn=clean_libelle)

    seen: Counter = Counter()       # occurrences par clé d'ID (réf. ou libellé)
    seen_lbl: Counter = Counter()   # occurrences par clé libellé (dédoublonnage)
    seen_dm: Counter = Counter()    # occurrences par clé date+montant (vs manuelles)
    imported = 0
    skipped = 0
    illisibles = 0   # lignes écartées : montant présent mais impossible à lire
    pointees = 0     # opérations existantes pointées d'après le relevé
    recaps = 0       # récapitulatifs de débit différé écartés
    rapprochees = 0  # échéances prévues rattachées à leur ligne du relevé
    # Date du prélèvement du lot carte en cours de lecture (Crédit Agricole),
    # ou "" tant qu'on est dans les opérations du compte.
    lot_debite = ""
    for cols in rows[1:]:
        # « Encours débité le 31 août 2026 » : les lignes qui suivent sont les
        # achats carte de ce lot, prélevés ce jour-là.
        if cols and _date_lot_debite(cols[0]):
            lot_debite = _date_lot_debite(cols[0])
            continue
        # Récapitulatif du débit différé : jamais importé, il ferait doublon
        # avec les achats carte détaillés (cf. MOTIFS_RECAP_DEBIT_DIFFERE).
        if est_recap_debit_differe(_libelle(cols)):
            recaps += 1
            continue
        d_iso, montant, lisible = _date_et_montant(cols)
        if not d_iso:
            continue
        dv_iso = parse_french_date(cols[iDateVal]) if iDateVal >= 0 and iDateVal < len(cols) else None
        libelle, refs_libelle = _decouper_libelle(
            cols[iLib] if 0 <= iLib < len(cols) else "")
        ref = _aplatir(cols[iRef]) if 0 <= iRef < len(cols) else ""
        info = _aplatir(cols[iInfo]) if 0 <= iInfo < len(cols) else ""
        # Références SEPA que le Crédit Agricole range dans le libellé : elles
        # rejoignent « info », à côté de celles que d'autres banques donnent
        # dans une colonne à part.
        if refs_libelle:
            info = f"{info} {refs_libelle}".strip()
        tp = _aplatir(cols[iType]) if 0 <= iType < len(cols) else ""
        if lot_debite:
            # Achat du détail d'un lot : payé par carte, et sorti du compte le
            # jour du prélèvement — c'est sa date de valeur.
            tp = tp or TYPE_CARTE
            dv_iso = dv_iso or lot_debite
        cat = _aplatir(cols[iCat]) if 0 <= iCat < len(cols) else ""
        sub = _aplatir(cols[iSub]) if 0 <= iSub < len(cols) else ""
        # « x » dans la colonne Pointage = la banque confirme le passage.
        # Faute de colonne, toute ligne du relevé est réputée passée.
        est_passee = (releve_sans_colonne_pointage
                      or (0 <= iPtg < len(cols)
                          and cols[iPtg].strip().lower() == "x"))

        # Normalisation catégorie
        cat = canonical_cat(cat) or cat or "Non classé"

        # Le montant a déjà été lu par _date_et_montant (colonne unique, ou
        # débit/crédit séparés).
        if not lisible:
            # On n'importe PAS la ligne avec 0 € (donnée fausse invisible) :
            # elle est comptée et signalée à l'utilisateur en fin d'import.
            illisibles += 1
            continue

        # ID stable, indépendant de la position dans le fichier. Le suffixe
        # d'occurrence distingue d'éventuelles opérations réellement identiques
        # le même jour. Doublon si correspondance par référence OU par libellé
        # nettoyé (voir le commentaire des compteurs plus haut).
        ident = _tx_identity(d_iso, montant, ref, libelle)
        k_lbl = _identity_libelle(d_iso, montant, libelle)
        k_dm = f"{d_iso}|{float(montant or 0):.2f}"
        occ = seen[ident]
        occ_lbl = seen_lbl[k_lbl]
        occ_dm = seen_dm[k_dm]
        seen[ident] += 1
        seen_lbl[k_lbl] += 1
        seen_dm[k_dm] += 1
        # Le compte fait partie de l'identifiant : sans lui, le même relevé
        # importé dans deux comptes différents fabriquait deux fois le même ID
        # et l'import échouait en bloc sur « UNIQUE constraint failed »
        # (incident du 16/09/2026 : un relevé importé dans le mauvais compte,
        # puis dans le bon). Deux comptes d'une même banque suffisaient à le
        # déclencher. Les opérations déjà en base gardent leur ancien ID : rien
        # n'est à migrer, la détection des doublons ne s'appuyant jamais sur
        # l'ID mais sur les clés recalculées depuis les champs stockés.
        tx_id = f"{db.compte_id}|{ident}#{occ}"
        # Le filet « saisie manuelle » (même date + même montant) ne s'applique
        # que s'il n'y a AUCUNE ambiguïté : autant de lignes du relevé à cette
        # date et ce montant que de saisies manuelles à rapprocher. Sinon, on
        # ne peut pas savoir laquelle correspond, et écarter la première venue
        # ferait disparaître une vraie dépense du relevé (incident du
        # 31/07/2026 : une saisie « Café » -4,50 € masquait la boulangerie du
        # même jour au même montant). En cas d'ambiguïté on importe tout : un
        # doublon visible se corrige avec « 🔍 Doublons », une opération perdue
        # ne se voit pas.
        filet_manuel = (occ_dm < existing_by_dm[k_dm]
                        and csv_par_dm[k_dm] <= existing_by_dm[k_dm])
        est_doublon = (occ_lbl < existing_by_lbl[k_lbl]) or (
            bool(ref.strip()) and occ < existing_by_ref[ident]) or filet_manuel
        if est_doublon:
            skipped += 1
            # On retrouve la ligne déjà en base pour la mettre à jour : la
            # banque confirme le passage (« x ») → on la pointe (jamais
            # l'inverse : un pointage manuel n'est pas retiré) ; et si c'était
            # une échéance saisie d'avance, elle cesse d'être une prévision
            # puisque le relevé la porte désormais.
            row = None
            if ref.strip():
                row = _premiere_non_pointee(rows_by_ref.get(ident))
            if row is None:
                row = _premiere_non_pointee(rows_by_lbl.get(k_lbl))
            if row is None:
                row = _premiere_non_pointee(rows_by_dm.get(k_dm))
            if row is None and lot_debite:
                # Un achat carte déjà pointé peut encore avoir besoin d'être
                # réparé (voir plus bas) : on le cherche aussi parmi ceux-là.
                row = next((r for r in (rows_by_ref.get(ident, [])
                                        + rows_by_lbl.get(k_lbl, []))
                            if not est_paiement_carte(r.get("type"))), None)
            if row is not None:
                champs = {}
                if est_passee and not row.get("pointee"):
                    champs["pointee"] = 1
                if row.get("prevue"):
                    champs["prevue"] = 0
                # Achat carte importé avant que Pécule sache lire les lots du
                # Crédit Agricole : on lui rend son type et sa date de débit.
                if lot_debite and not est_paiement_carte(row.get("type")):
                    champs["type"] = tp
                    champs["date_valeur"] = dv_iso
                if champs:
                    db.update_tx(row["id"], champs)
                    row.update(champs)   # ne pas retraiter la même ligne
                    if "pointee" in champs:
                        pointees += 1
            continue

        # Pas un doublon exact : cette ligne vient-elle confirmer une échéance
        # saisie d'avance ? Si oui, on complète celle-ci avec les informations
        # réelles de la banque au lieu d'ajouter une seconde ligne.
        attendue = trouver_echeance_prevue(prevues, d_iso, montant, libelle)
        if attendue is not None:
            champs = {
                "date":        d_iso,
                "date_valeur": dv_iso or d_iso,
                # Le libellé choisi par l'utilisateur est conservé (il est plus
                # lisible que celui de la banque) ; celui du relevé est rangé
                # dans libelle_op, qui existe pour ça.
                "libelle_op":  libelle or attendue.get("libelle", ""),
                "reference":   ref,
                "info":        info,
                "montant":     montant,
                "pointee":     1 if est_passee else 0,
                "prevue":      0,
            }
            if tp:
                champs["type"] = tp
            # La catégorie du Prévisionnel prime : c'est celle que l'utilisateur
            # a choisie. On ne prend celle du relevé que si l'échéance n'était
            # pas classée.
            if (attendue.get("categorie") or "Non classé") == "Non classé":
                champs["categorie"] = cat
                champs["sous_cat"] = sub
            db.update_tx(attendue["id"], champs)
            attendue["_consommee"] = True
            attendue.update(champs)
            rapprochees += 1
            continue

        tx = {
            "id": tx_id,
            "date": d_iso,
            "date_valeur": dv_iso or d_iso,
            "libelle": libelle,
            "libelle_op": libelle,
            "reference": ref,
            "type": tp,
            "categorie": cat,
            "sous_cat": sub,
            "info": info,
            "montant": montant,
            "pointee": 1 if est_passee else 0,
        }
        # Appliquer les règles
        modified, fields = apply_rules_to_tx(tx, rules)
        if modified:
            tx.update(fields)

        # Héritage du profil habituel du libellé (en complément des règles) :
        # ne comble que ce qui reste « Non classé », sans écraser la banque
        # ni les règles.
        prof = profiles.get(clean_libelle(libelle))
        if prof:
            if tx["categorie"] in ("", "Non classé") and prof["categorie"]:
                tx["categorie"] = prof["categorie"]
                if not tx["sous_cat"] and prof["sous_cat"]:
                    tx["sous_cat"] = prof["sous_cat"]
            elif (not tx["sous_cat"] and prof["sous_cat"]
                  and prof["categorie"] == tx["categorie"]):
                tx["sous_cat"] = prof["sous_cat"]

        # Dernier recours : les motifs intégrés (« carrefour » → Alimentation),
        # ceux-là mêmes qu'utilise le bouton « Harmoniser ». Ils ne passent
        # qu'APRÈS la catégorie de la banque, les règles de l'utilisateur et
        # l'habitude du libellé : ce qui est explicite l'emporte toujours sur
        # ce qui est deviné. Sans cela, le premier relevé d'un nouvel
        # utilisateur — sans règle ni historique — arrivait entièrement en
        # « Non classé », budgets et graphiques vides.
        if tx["categorie"] in ("", "Non classé"):
            devinee = suggest_category(libelle, tx["sous_cat"])
            if devinee:
                tx["categorie"] = devinee

        db.insert_tx(tx)
        imported += 1

    # Lot carte annoncé en tête du relevé, sans détail : retenu pour le Bilan.
    # Un relevé qui ne l'annonce pas ne touche pas au dernier connu — un
    # simple export d'une autre banque ne doit pas l'effacer.
    lot = lire_lot_annonce(text)
    if lot:
        db.set_setting(_cle_lot_annonce(db), json.dumps(lot))

    return ResultatImport(imported, skipped, illisibles, pointees, recaps,
                          rapprochees)
