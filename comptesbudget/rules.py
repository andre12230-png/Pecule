"""Règles d'auto-catégorisation des transactions."""
from .utils import deaccent


def matches_rule(tx: dict, rule: dict) -> bool:
    # Comparaison sans accents ni majuscules, comme la recherche et les
    # sous-catégories : une règle « Café » doit reconnaître « CAFE DE LA
    # GARE » (les relevés bancaires sont souvent sans accents).
    lib = deaccent(" ".join([
        (tx.get("libelle") or ""),
        (tx.get("libelle_op") or ""),
        (tx.get("reference") or ""),
    ]))
    pattern = deaccent(rule.get("pattern") or "")
    if not pattern or pattern not in lib:
        return False
    # Sens : '' = les deux ; 'debit' = montants négatifs ; 'credit' = positifs.
    # Évite p. ex. qu'un REMBOURSEMENT Omnishop (+) retombe dans « Shopping ».
    sens = rule.get("sens") or ""
    m = tx.get("montant", 0)
    if sens == "debit" and m >= 0:
        return False
    if sens == "credit" and m <= 0:
        return False
    if rule.get("amount") is not None:
        if abs(abs(m) - rule["amount"]) > 0.005:
            return False
    return True


def apply_rules_to_tx(tx: dict, rules: list[dict]) -> tuple[bool, dict]:
    """Retourne (modified, updated_fields)."""
    # Priorité : règles avec montant > règles plus longues > autres
    sorted_rules = sorted(
        rules,
        key=lambda r: (r.get("amount") is not None, len(r.get("pattern", ""))),
        reverse=True,
    )
    for r in sorted_rules:
        if matches_rule(tx, r):
            if r.get("no_overwrite") and tx.get("categorie") not in ("", "Non classé"):
                return False, {}
            return True, {
                "categorie": r.get("categorie") or tx.get("categorie", "Non classé"),
                "sous_cat":  r.get("sous_cat")  or tx.get("sous_cat", ""),
            }
    return False, {}
