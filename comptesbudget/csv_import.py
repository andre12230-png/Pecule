"""Import des relevés bancaires au format CSV (BPCE / CM / CA)."""
import csv
import re
from collections import Counter
from typing import Optional

from .utils import canonical_cat, deaccent
from .labels import build_libelle_profiles, clean_libelle
from .rules import apply_rules_to_tx
from .database import Database

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


def import_csv(path: str, db: Database) -> tuple[int, int, int, int]:
    """Lit un CSV bancaire français et insère les transactions.
    Retourne (importées, doublons ignorés, lignes au montant illisible,
    opérations existantes pointées d'après le relevé)."""
    with open(path, "rb") as f:
        text = _decode_csv(f.read())

    lines = [l for l in text.splitlines() if l.strip()]
    # Trouver la ligne d'en-tête
    header_idx = None
    for i, line in enumerate(lines):
        low = deaccent(line)
        if "date" in low and ("libelle" in low or "libellé" in low.lower()):
            header_idx = i
            break
    if header_idx is None:
        raise ValueError("En-tête CSV introuvable")

    reader = csv.reader(lines[header_idx:], delimiter=";")
    rows = list(reader)
    headers = [deaccent(h) for h in rows[0]]

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

    # Combien de lignes du RELEVÉ portent chaque couple date+montant ? Sert à
    # désamorcer le filet « saisie manuelle » plus bas quand il y a ambiguïté.
    csv_par_dm: Counter = Counter()
    for cols in rows[1:]:
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
    for cols in rows[1:]:
        d_iso, montant, lisible = _date_et_montant(cols)
        if not d_iso:
            continue
        dv_iso = parse_french_date(cols[iDateVal]) if iDateVal >= 0 and iDateVal < len(cols) else None
        libelle = cols[iLib].strip() if iLib >= 0 and iLib < len(cols) else ""
        ref = cols[iRef].strip() if iRef >= 0 and iRef < len(cols) else ""
        info = cols[iInfo].strip() if iInfo >= 0 and iInfo < len(cols) else ""
        tp = cols[iType].strip() if iType >= 0 and iType < len(cols) else ""
        cat = cols[iCat].strip() if iCat >= 0 and iCat < len(cols) else ""
        sub = cols[iSub].strip() if iSub >= 0 and iSub < len(cols) else ""
        # « x » dans la colonne Pointage = la banque confirme le passage.
        est_passee = (0 <= iPtg < len(cols)
                      and cols[iPtg].strip().lower() == "x")

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
        tx_id = f"{ident}#{occ}"
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
            # La banque confirme le passage (« x ») : on pointe l'opération
            # existante correspondante si elle ne l'était pas déjà. Jamais
            # l'inverse — un pointage manuel n'est pas retiré.
            if est_passee:
                row = None
                if ref.strip():
                    row = _premiere_non_pointee(rows_by_ref.get(ident))
                if row is None:
                    row = _premiere_non_pointee(rows_by_lbl.get(k_lbl))
                if row is None:
                    row = _premiere_non_pointee(rows_by_dm.get(k_dm))
                if row is not None:
                    db.update_tx(row["id"], {"pointee": 1})
                    row["pointee"] = 1   # ne pas re-pointer la même ligne
                    pointees += 1
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

        db.insert_tx(tx)
        imported += 1

    return imported, skipped, illisibles, pointees
