"""Nettoyage et profilage des libellés de transactions."""
import re
from collections import Counter
from statistics import median

from .utils import deaccent

# Mots passe-partout des relevés bancaires : seuls, ils ne désignent aucun
# commerçant. Un libellé qui se réduit à cela après nettoyage a perdu sa seule
# information distinctive (cf. clean_libelle).
MOTS_PASSE_PARTOUT = {
    "vir", "virement", "prlv", "prelevement", "prelvt", "prel", "cb", "carte",
    "paiement", "pmt", "achat", "retrait", "depot", "dab", "facture", "fact",
    "ech", "echeance", "remise", "cheque", "chq", "sepa", "avoir", "frais",
    "operation", "op", "de", "du", "des", "la", "le", "les", "vers", "pour",
    "par", "sur", "et", "a", "au", "aux", "en",
}

# Sigles à conserver en majuscules lors de la normalisation des libellés.
LIBELLE_ACRONYMS = {
    "BPCE", "SFR", "EDF", "GDF", "FDJ", "DGFIP", "CPAM", "ACM", "IARD",
    "BTP", "SAS", "SARL", "SNCF", "RATP", "CAF", "CIC", "LCL", "BNP", "SG",
    "GMF", "MAAF", "MAIF", "AXA", "CB", "DAB", "SIV", "QPF", "BDA", "TI",
    "GC", "RE", "EI", "KFC", "TGV", "VTC", "SAV", "RSI", "URSSAF", "CMU",
    "RIB", "CCP", "SAUR", "APRR", "EI", "SA",
}


def _smart_titlecase(s: str) -> str:
    """Met un libellé en casse « propre » (Titre) tout en conservant les
    sigles connus ou les courtes suites de consonnes (SFR, EDF, BPCE…)."""
    out = []
    for w in s.split():
        wu = w.upper()
        core = re.sub(r"[^A-Za-zÀ-ÿ]", "", w)
        if wu in LIBELLE_ACRONYMS:
            out.append(wu)
        elif w.isupper() and len(core) <= 3 and not re.search(r"[AEIOUYaeiouy]", core):
            out.append(wu)
        else:
            out.append(w[:1].upper() + w[1:].lower())
    return " ".join(out)


def clean_libelle(raw: str) -> str:
    """Forme canonique d'un libellé : retire dates, numéros de magasin /
    références et suffixes web (.fr/.com), puis normalise la casse.

    Déterministe : deux variantes du même commerçant (« SUPERETTE 3193 » et
    « superette 3852 ») produisent le même résultat (« Superette ») et fusionnent."""
    s = raw or ""
    s = re.sub(r"\.(fr|com|net|org|eu)\b", " ", s, flags=re.IGNORECASE)  # web
    s = re.sub(r"\S*\d\S*", " ", s)            # tout token contenant un chiffre
    s = re.sub(r"[°ºªN]{0,1}[°º]", " ", s)     # symboles ° résiduels
    s = re.sub(r"[^\wÀ-ÿ&'\-]", " ", s)        # ponctuation → espace (garde & ' -)
    # Retire les tokens de bruit isolés (n°, no, restes d'une lettre)
    toks = [t for t in s.split() if t.lower() not in {"n", "no", "°"}]
    s = " ".join(toks)
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return (raw or "").strip()             # ne jamais vider un libellé
    # Si le nettoyage ne laisse que des mots passe-partout (« VIR 123456 » →
    # « Vir »), le numéro retiré était la seule chose qui distinguait cette
    # opération : deux virements sans rapport porteraient le même libellé et
    # seraient pris l'un pour l'autre — y compris par la détection de
    # doublons à l'import. On conserve alors le libellé d'origine.
    if all(deaccent(t) in MOTS_PASSE_PARTOUT for t in s.split()):
        return _smart_titlecase((raw or "").strip())
    return _smart_titlecase(s)


def build_libelle_profiles(txs: list[dict], key_fn=None) -> dict[str, dict]:
    """Construit, pour chaque libellé déjà saisi, son profil le plus probable :
    catégorie, sous-catégorie et type les plus fréquents, montant médian et
    signe dominant. Sert au pré-remplissage automatique des formulaires.

    `key_fn` permet d'indexer sur une forme normalisée du libellé (ex.
    `clean_libelle`) pour rapprocher des variantes brutes à l'import."""
    norm = key_fn or (lambda s: (s or "").strip())
    data: dict[str, dict] = {}
    for t in txs:
        lbl = (t.get("libelle") or "").strip()
        if not lbl:
            continue
        key = norm(lbl)
        if not key:
            continue
        d = data.setdefault(key, {
            "cat": Counter(), "sub": Counter(), "type": Counter(), "amounts": [],
        })
        if t.get("categorie"):
            d["cat"][t["categorie"]] += 1
        d["sub"][(t.get("sous_cat") or "")] += 1
        if t.get("type"):
            d["type"][t["type"]] += 1
        d["amounts"].append(float(t.get("montant", 0)))

    profiles: dict[str, dict] = {}
    for lbl, d in data.items():
        amounts = d["amounts"]
        med = round(median(amounts), 2) if amounts else 0.0
        profiles[lbl] = {
            "categorie": d["cat"].most_common(1)[0][0] if d["cat"] else "",
            "sous_cat":  d["sub"].most_common(1)[0][0] if d["sub"] else "",
            "type":      d["type"].most_common(1)[0][0] if d["type"] else "",
            "montant":   med,
        }
    return profiles
