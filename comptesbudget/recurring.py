"""Opérations récurrentes : génération d'occurrences et détection automatique."""
import re
from calendar import monthrange
from collections import Counter, defaultdict
from datetime import date, timedelta
from statistics import median

from .utils import deaccent

def next_occurrence(rec: dict, current: date, ref_day: int = None) -> date:
    """Date suivant `current` selon la fréquence.

    `ref_day` est le jour du mois de référence : il vient de l'échéance
    elle-même (day_of_month) ou, à défaut, du jour de la PREMIÈRE occurrence.
    Sans cette référence, une échéance au 31 dériverait définitivement après
    un mois court : 31/01 → 28/02 → 28/03 → 28/04… au lieu de revenir au 31."""
    freq = rec.get("frequency", "monthly")
    ref_day = rec.get("day_of_month") or ref_day or current.day
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
        y = current.year + 1
        # Même logique : on repart du jour de référence, ramené à la longueur
        # du mois (un 29 février retombe au 28 les années non bissextiles).
        return date(y, current.month, min(ref_day, monthrange(y, current.month)[1]))
    return current


def _date_ou_none(s) -> date:
    """Lit une date ISO ; retourne None si elle est absente ou illisible.
    Une date abîmée (base modifiée à la main, fichier JSON restauré) ne doit
    pas empêcher l'application de s'ouvrir."""
    try:
        return date.fromisoformat((s or "")[:10])
    except (TypeError, ValueError):
        return None


def generate_occurrences(rec: dict, until: date) -> list[date]:
    """Toutes les occurrences depuis start_date jusqu'à `until` (incluse)."""
    if not rec.get("actif"):
        return []
    cur = _date_ou_none(rec.get("start_date"))
    if cur is None:
        return []
    end = _date_ou_none(rec.get("end_date")) if rec.get("end_date") else None
    ref_day = cur.day          # jour de la première occurrence (cf. next_occurrence)
    out = []
    while cur <= until:
        if end and cur > end:
            break
        out.append(cur)
        nxt = next_occurrence(rec, cur, ref_day)
        if nxt <= cur:  # sécurité anti-boucle infinie
            break
        cur = nxt
    return out


def _meme_operation(cle_a: str, cle_b: str) -> bool:
    """Deux libellés normalisés désignent-ils la même opération ?

    L'égalité stricte ne suffit pas : la banque ajoute souvent une forme
    juridique ou une agence à la fin (« SECURIDOM » ↔ « SECURIDOM SAS »,
    « CAISSE RETRAITE » ↔ « CAISSE RETRAITE 447 »). On accepte donc que le plus
    court soit le DÉBUT du plus long, mot à mot — mais jamais un simple mot
    commun au milieu, qui confondrait « ASS AUTO » et « ASS HABITATION »."""
    a, b = cle_a.split(), cle_b.split()
    if not a or not b:
        return False
    court, long_ = (a, b) if len(a) <= len(b) else (b, a)
    return long_[:len(court)] == court


def _dates_compatibles(dates_op: list[str], d_occ: str, tolerance: int) -> bool:
    """Une opération peut-elle être le passage de cette échéance ?

    Oui si elle tombe dans le MÊME MOIS que l'échéance attendue (une mensuelle
    ne passe qu'une fois par mois, peu importe le jour), ou à quelques jours
    d'elle quand elle déborde sur le mois voisin (échéance du 1er payée le 30).
    Sans cette règle, un prélèvement du 31 juillet solderait l'échéance du
    31 août et celle-ci disparaîtrait du budget du mois."""
    for d in dates_op:
        if d[:7] == d_occ[:7]:
            return True
        try:
            ecart = abs((date.fromisoformat(d[:10])
                         - date.fromisoformat(d_occ[:10])).days)
        except (TypeError, ValueError):
            continue
        if ecart <= tolerance:
            return True
    return False


def _sous_cats_contradictoires(a: str, b: str) -> bool:
    """Deux sous-catégories renseignées et différentes désignent deux contrats
    distincts, même sous un libellé identique : chez le même assureur,
    « Assurance Auto » et « Assurance Habitation » sont prélevées séparément.

    Ne sert qu'en dernier recours (cf. echeances_du_mois) : la banque renomme
    parfois la sous-catégorie d'une opération (« eau » devient « Energie eau,
    gaz, electricite, fioul »), ce qui n'en fait pas une autre opération."""
    a, b = (a or "").strip().lower(), (b or "").strip().lower()
    return bool(a) and bool(b) and a != b


def _montants_voisins(a: float, b: float) -> bool:
    """Deux montants peuvent-ils être ceux de la même échéance ?

    Tolérance volontairement large : une facture d'électricité ou de téléphone
    varie d'un mois à l'autre. Il s'agit seulement de distinguer deux échéances
    de tailles très différentes qui portent le même libellé."""
    ecart = abs(abs(a) - abs(b))
    return ecart <= max(2.0, 0.15 * max(abs(a), abs(b)))


def echeances_du_mois(recs: list[dict], txs: list[dict], annee: int, mois: int,
                      aujourdhui: date = None,
                      tolerance_jours: int = 5) -> list[dict]:
    """Ce qui doit tomber sur le compte pendant le mois demandé.

    Principe du budget mensuel sur papier : en début de mois on aligne toutes
    les échéances attendues, et on les « pointe » au fur et à mesure qu'elles
    passent en banque. Chaque ligne retournée porte trois indicateurs :

      * `_deja`   : une opération lui correspond déjà (passée en banque ou
                    saisie à la main) — il ne faut PAS la recréer ;
      * `_passee` : sa date prévue est déjà derrière nous ;
      * `_default`: proposition de pré-cochage (ni déjà là, ni date passée).

    Le rapprochement se fait sur le libellé normalisé et sur le SENS de
    l'opération (un remboursement ne solde pas un prélèvement attendu), dans
    une fenêtre élargie de `tolerance_jours` avant et après le mois : une
    échéance du 1er payée le 30 du mois précédent reste reconnue.
    """
    aujourdhui = aujourdhui or date.today()
    premier = date(annee, mois, 1)
    dernier = date(annee, mois, monthrange(annee, mois)[1])
    debut = (premier - timedelta(days=tolerance_jours)).isoformat()
    fin = (dernier + timedelta(days=tolerance_jours)).isoformat()

    # Opérations déjà en base dans la fenêtre. Chacune ne peut solder qu'UNE
    # échéance : on les consomme au fur et à mesure (« pris »), sinon une
    # échéance hebdomadaire passée une fois paraîtrait couverte quatre fois.
    dispo: list[dict] = []
    for t in txs:
        d_op = t.get("date", "") or ""
        d_val = t.get("date_valeur") or d_op
        if not (debut <= d_op <= fin or debut <= d_val <= fin):
            continue
        cle = _recurring_norm_label(t.get("libelle", ""))
        if not cle:
            continue
        dispo.append({"cle": cle,
                      "dates": [d for d in (d_op, d_val) if d],
                      "montant": float(t.get("montant", 0) or 0),
                      "sous_cat": t.get("sous_cat", "") or "",
                      "credit": float(t.get("montant", 0) or 0) >= 0,
                      "pris": False})

    # Toutes les occurrences attendues, AVANT rapprochement : il faut les
    # connaître toutes pour attribuer chaque opération à la bonne (cf. les
    # trois passes ci-dessous). Les récurrences sont prises de la plus précise
    # à la plus vague — « ALPHATEL MOBILE » doit se servir avant « ALPHATEL ».
    occurrences: list[dict] = []
    for r in sorted(recs, key=lambda r: -len(
            _recurring_norm_label(r.get("libelle", "")).split())):
        if not r.get("actif"):
            continue
        montant = float(r.get("montant", 0) or 0)
        cle_rec = _recurring_norm_label(r.get("libelle", ""))
        for d in generate_occurrences(r, dernier):
            if d >= premier:
                occurrences.append({"rec": r, "date": d, "montant": montant,
                                    "cle": cle_rec, "couverte": False,
                                    "sous_cat": r.get("sous_cat", "") or ""})

    # Rapprochement en trois passes, de la plus sûre à la plus tolérante. La
    # première évite qu'une échéance prenne l'opération d'une autre du même
    # nom : une banque libelle souvent « Echeance De Credit » aussi bien la
    # mensualité d'un prêt que la petite assurance qui l'accompagne, et un
    # prélèvement du montant de la mensualité appartient évidemment au prêt.
    for passe in (1, 2, 3):
        for occ in occurrences:
            if occ["couverte"]:
                continue
            for c in dispo:
                if c["pris"] or c["credit"] != (occ["montant"] >= 0):
                    continue
                if not _dates_compatibles(c["dates"], occ["date"].isoformat(),
                                          tolerance_jours):
                    continue
                if passe == 1:
                    ok = (c["cle"] == occ["cle"]
                          and _montants_voisins(c["montant"], occ["montant"]))
                else:
                    # Passes 2 et 3 : le montant ne confirme plus rien, une
                    # sous-catégorie contradictoire suffit alors à écarter.
                    ok = (not _sous_cats_contradictoires(c["sous_cat"],
                                                         occ["sous_cat"])
                          and (c["cle"] == occ["cle"] if passe == 2
                               else _meme_operation(occ["cle"], c["cle"])))
                if ok:
                    c["pris"] = True
                    occ["couverte"] = True
                    break

    out: list[dict] = []
    for occ in occurrences:
        r, d, couverte = occ["rec"], occ["date"], occ["couverte"]
        out.append({
            "date":      d.isoformat(),
            "libelle":   r.get("libelle", ""),
            "montant":   occ["montant"],
            "categorie": r.get("categorie", "") or "Non classé",
            "sous_cat":  r.get("sous_cat", "") or "",
            "type":      r.get("type", "") or "",
            "rec_id":    r.get("id", ""),
            "_deja":     couverte,
            "_passee":   d < aujourdhui,
            "_default":  not couverte and d >= aujourdhui,
        })

    out.sort(key=lambda e: (e["date"], e["libelle"].lower()))
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
