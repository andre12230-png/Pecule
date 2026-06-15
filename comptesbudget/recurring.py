"""Opérations récurrentes : génération d'occurrences et détection automatique."""
import re
from calendar import monthrange
from collections import Counter, defaultdict
from datetime import date, timedelta
from statistics import median

from .utils import deaccent

def next_occurrence(rec: dict, current: date) -> date:
    """Date suivant `current` selon la fréquence."""
    freq = rec.get("frequency", "monthly")
    ref_day = rec.get("day_of_month") or current.day
    if freq == "weekly":
        return current + timedelta(days=7)
    if freq == "biweekly":
        return current + timedelta(days=14)
    if freq == "monthly":
        y = current.year + (1 if current.month == 12 else 0)
        m = 1 if current.month == 12 else current.month + 1
        d = min(ref_day, monthrange(y, m)[1])
        return date(y, m, d)
    if freq == "quarterly":
        m = current.month + 3
        y = current.year
        while m > 12:
            m -= 12; y += 1
        d = min(ref_day, monthrange(y, m)[1])
        return date(y, m, d)
    if freq == "yearly":
        try:
            return date(current.year + 1, current.month, current.day)
        except ValueError:
            return date(current.year + 1, current.month, 28)
    return current


def generate_occurrences(rec: dict, until: date) -> list[date]:
    """Toutes les occurrences depuis start_date jusqu'à `until` (incluse)."""
    if not rec.get("actif"):
        return []
    sd_str = rec.get("start_date")
    if not sd_str:
        return []
    cur = date.fromisoformat(sd_str)
    end = date.fromisoformat(rec["end_date"]) if rec.get("end_date") else None
    out = []
    while cur <= until:
        if end and cur > end:
            break
        out.append(cur)
        nxt = next_occurrence(rec, cur)
        if nxt <= cur:  # sécurité anti-boucle infinie
            break
        cur = nxt
    return out


def _recurring_norm_label(libelle: str) -> str:
    """Normalise un libellé pour regrouper les occurrences d'une même
    opération récurrente : sans accents, sans dates ni numéros de référence,
    on ne conserve que les 4 premiers mots significatifs."""
    s = deaccent(libelle)
    s = re.sub(r"\d{2}[/.]\d{2}([/.]\d{2,4})?", " ", s)   # dates jj/mm[/aa]
    s = re.sub(r"\d{4,}", " ", s)                          # longues références
    s = re.sub(r"[^a-z ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    toks = [t for t in s.split() if len(t) > 2][:4]
    return " ".join(toks)


def _recurring_aligned_start(freq: str, day_of_month: int, today: date) -> date:
    """Première occurrence à venir (>= aujourd'hui) alignée sur le jour
    du mois détecté, pour les fréquences mensuelle et plus longues."""
    if freq in ("monthly", "quarterly", "yearly"):
        y, m = today.year, today.month
        d = min(day_of_month, monthrange(y, m)[1])
        cand = date(y, m, d)
        if cand < today:
            m += 1
            if m > 12:
                m = 1; y += 1
            d = min(day_of_month, monthrange(y, m)[1])
            cand = date(y, m, d)
        return cand
    return today


def detect_recurring_candidates(txs: list[dict], min_months: int = 4) -> list[dict]:
    """Analyse les opérations passées et propose des opérations récurrentes.

    Regroupe par libellé normalisé, ne retient que les groupes présents sur
    au moins `min_months` mois distincts et de signe cohérent, puis déduit
    fréquence, jour du mois, montant médian, catégorie et type.

    Chaque candidat porte des métadonnées (préfixées « _ ») pour l'aperçu :
    nombre de mois, fourchette de montants, stabilité et pré-sélection.
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for t in txs:
        key = _recurring_norm_label(t.get("libelle", ""))
        if not key:
            continue
        if not t.get("date"):
            continue
        groups[key].append(t)

    # Catégories à ne jamais pré-cocher (mais on les montre quand même)
    SKIP_DEFAULT_CATS = {"Virements internes", "Transaction exclue", "Non classé"}

    cands: list[dict] = []
    for key, items in groups.items():
        amounts_all = [float(t.get("montant", 0)) for t in items]
        pos = [a for a in amounts_all if a > 0]
        neg = [a for a in amounts_all if a < 0]
        # Signe cohérent exigé : on ne garde que le sens dominant et on ignore
        # le groupe si les deux sens sont fortement représentés (remboursements).
        if pos and neg:
            minor = min(len(pos), len(neg))
            if minor > 0.2 * len(amounts_all):
                continue
            keep_pos = len(pos) >= len(neg)
            items = [t for t in items if (float(t.get("montant", 0)) > 0) == keep_pos]

        months = sorted({t["date"][:7] for t in items})
        if len(months) < min_months:
            continue

        amounts = [float(t.get("montant", 0)) for t in items]
        med = round(median(amounts), 2)
        dates = sorted(date.fromisoformat(t["date"]) for t in items)
        gaps = [(dates[i + 1] - dates[i]).days
                for i in range(len(dates) - 1)
                if (dates[i + 1] - dates[i]).days > 0]
        mg = median(gaps) if gaps else 30
        if mg <= 10:
            freq = "weekly"
        elif mg <= 20:
            freq = "biweekly"
        elif mg <= 45:
            freq = "monthly"
        elif mg <= 135:
            freq = "quarterly"
        else:
            freq = "yearly"
        dom = int(median([d.day for d in dates]))

        cat = Counter(t.get("categorie", "") for t in items).most_common(1)[0][0]
        sub = Counter((t.get("sous_cat") or "") for t in items).most_common(1)[0][0]
        typ = Counter((t.get("type") or "") for t in items).most_common(1)[0][0]

        spread = max(amounts) - min(amounts)
        stable = abs(spread) <= max(2.0, 0.15 * abs(med)) if med else False

        cands.append({
            "libelle":      key.title(),
            "montant":      med,
            "categorie":    cat or "Non classé",
            "sous_cat":     sub,
            "type":         typ,
            "frequency":    freq,
            "day_of_month": dom,
            "_months":      len(months),
            "_count":       len(items),
            "_min":         round(min(amounts), 2),
            "_max":         round(max(amounts), 2),
            "_stable":      stable,
            "_default":     stable and (cat not in SKIP_DEFAULT_CATS)
                            and freq in ("monthly", "quarterly", "yearly"),
        })

    cands.sort(key=lambda c: (-c["_months"], -abs(c["montant"])))
    return cands
