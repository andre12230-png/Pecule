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
    dans le fichier. On privilégie la référence bancaire (souvent unique et non
    modifiée par l'utilisateur) ; à défaut, le libellé normalisé. Deux relevés
    qui se chevauchent produisent ainsi la même clé pour une même opération,
    ce qui permet de la dédoublonner correctement."""
    ident = (reference or "").strip() or clean_libelle(libelle)
    return f"{date_iso}|{float(montant or 0):.2f}|{ident}"


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


def import_csv(path: str, db: Database) -> tuple[int, int, int]:
    """Lit un CSV bancaire français et insère les transactions.
    Retourne (importées, doublons ignorés, lignes au montant illisible)."""
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

    rules = [dict(r) for r in db.list_rules()]
    existing_tx = [dict(r) for r in db.list_tx()]
    # Multiplicité des opérations déjà en base, indexée sur la clé d'identité
    # stable (_tx_identity). Recalculée depuis les champs stockés : valable même
    # pour les opérations importées par une version antérieure (id ancien format).
    existing_key_counts = Counter(
        _tx_identity(t.get("date", ""), t.get("montant", 0),
                     t.get("reference", ""), t.get("libelle", ""))
        for t in existing_tx)
    # Profils habituels par libellé (indexés sur la forme nettoyée), pour
    # hériter de la catégorie/sous-catégorie d'un libellé déjà connu.
    profiles = build_libelle_profiles(existing_tx, key_fn=clean_libelle)

    seen: Counter = Counter()
    imported = 0
    skipped = 0
    illisibles = 0   # lignes écartées : montant présent mais impossible à lire
    for cols in rows[1:]:
        if not cols or iDate < 0 or iDate >= len(cols):
            continue
        d_iso = parse_french_date(cols[iDate])
        if not d_iso:
            continue
        dv_iso = parse_french_date(cols[iDateVal]) if iDateVal >= 0 and iDateVal < len(cols) else None
        libelle = cols[iLib].strip() if iLib >= 0 and iLib < len(cols) else ""
        ref = cols[iRef].strip() if iRef >= 0 and iRef < len(cols) else ""
        info = cols[iInfo].strip() if iInfo >= 0 and iInfo < len(cols) else ""
        tp = cols[iType].strip() if iType >= 0 and iType < len(cols) else ""
        cat = cols[iCat].strip() if iCat >= 0 and iCat < len(cols) else ""
        sub = cols[iSub].strip() if iSub >= 0 and iSub < len(cols) else ""

        # Normalisation catégorie
        cat = canonical_cat(cat) or cat or "Non classé"

        # Montant : soit colonne unique, soit débit/crédit séparés
        if iMontant >= 0 and iMontant < len(cols):
            montant, lisible = _parse_amount_checked(cols[iMontant])
        else:
            d, ok_d = _parse_amount_checked(cols[iDebit]) if 0 <= iDebit < len(cols) else (0.0, True)
            c, ok_c = _parse_amount_checked(cols[iCredit]) if 0 <= iCredit < len(cols) else (0.0, True)
            # Le débit est souvent saisi négatif
            if d > 0:
                d = -d
            montant = d + c
            lisible = ok_d and ok_c
        if not lisible:
            # On n'importe PAS la ligne avec 0 € (donnée fausse invisible) :
            # elle est comptée et signalée à l'utilisateur en fin d'import.
            illisibles += 1
            continue

        # ID stable, indépendant de la position dans le fichier : deux relevés
        # qui se chevauchent dédoublonnent correctement. Le suffixe d'occurrence
        # distingue d'éventuelles opérations réellement identiques le même jour.
        ident = _tx_identity(d_iso, montant, ref, libelle)
        occ = seen[ident]
        seen[ident] += 1
        tx_id = f"{ident}#{occ}"
        if occ < existing_key_counts[ident]:
            skipped += 1
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
            "pointee": 0,
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

    return imported, skipped, illisibles
