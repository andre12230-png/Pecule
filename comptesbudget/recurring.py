"""Opérations récurrentes : génération d'occurrences et détection automatique."""
import re
from calendar import monthrange
from collections import Counter, defaultdict
from datetime import date, timedelta
from statistics import median

from .utils import deaccent, est_paiement_carte

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
        # Une carte à DÉBIT DIFFÉRÉ fausse ce raisonnement : sa date de valeur
        # est celle du prélèvement groupé du mois suivant, pas le décalage de
        # quelques jours d'un prélèvement présenté en fin de mois. Elle ne dit
        # rien du mois auquel l'achat se rattache — retenue, elle ferait solder
        # l'échéance d'octobre par l'achat de septembre, et cette échéance ne
        # serait jamais proposée. Pour ces opérations, seule la date d'achat
        # compte.
        dates = ([d_op] if est_paiement_carte(t.get("type", ""))
                 else [d for d in (d_op, d_val) if d])
        if not any(debut <= d <= fin for d in dates):
            continue
        cle = _recurring_norm_label(t.get("libelle", ""))
        if not cle:
            continue
        dispo.append({"cle": cle,
                      "dates": dates,
                      "montant": float(t.get("montant", 0) or 0),
                      "sous_cat": t.get("sous_cat", "") or "",
                      "credit": float(t.get("montant", 0) or 0) >= 0,
                      "pris": False})

    # Toutes les occurrences attendues, AVANT rapprochement : il faut les
    # connaître toutes pour attribuer chaque opération à la bonne (cf. les
    # trois passes ci-dessous). Les récurrences sont prises de la plus précise
    # à la plus vague — « ALPHATEL MOBILE » doit se servir avant « ALPHATEL ».
    #
    # On y ajoute les occurrences VOISINES, celles des mois d'à côté qui
    # tombent dans la marge de tolérance : elles se servent en premier (ordre
    # des dates) sans être rendues. Sans elles, chaque mois rapproché pour
    # lui seul prenait le même débit que son voisin : une échéance du 31/10
    # débitée le 02/11 payait aussi celle du 30/11 (audit du 23/09/2026).
    occurrences: list[dict] = []
    for r in sorted(recs, key=lambda r: -len(
            _recurring_norm_label(r.get("libelle", "")).split())):
        if not r.get("actif"):
            continue
        montant = float(r.get("montant", 0) or 0)
        cle_rec = _recurring_norm_label(r.get("libelle", ""))
        for d in generate_occurrences(r, date.fromisoformat(fin)):
            if d.isoformat() >= debut:
                occurrences.append({"rec": r, "date": d, "montant": montant,
                                    "cle": cle_rec, "couverte": False,
                                    "sous_cat": r.get("sous_cat", "") or "",
                                    "voisine": not premier <= d <= dernier})

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
        if occ["voisine"]:
            continue              # appartient au mois d'à côté
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


# Au-delà de ce délai sans passage (en jours, compté depuis la dernière
# opération de l'historique), une opération est réputée arrêtée : contrat
# résilié, crédit remboursé, abonnement stoppé. Un peu plus d'une période,
# pour tolérer un passage en retard ou un relevé pas encore importé.
_FRAICHEUR_MAX = {"weekly": 30, "biweekly": 45, "monthly": 62,
                  "quarterly": 135, "yearly": 400}

# Écart normal entre deux passages, en jours, pour chaque fréquence : une
# opération n'est pré-cochée que si ses derniers passages le respectent tous.
_ECART_REGULIER = {"weekly": (5, 10), "biweekly": (11, 20),
                   "monthly": (20, 45), "quarterly": (70, 110),
                   "yearly": (330, 400)}

# Nombre de passages récents qui servent à estimer le montant et le jour.
# Les plus anciens décrivent souvent un état révolu (pension revalorisée,
# échéance déplacée) : la médiane sur des années garderait l'ancien chiffre.
_PASSAGES_RECENTS = 3


def _frequence(ecarts: list[int]) -> str:
    """Fréquence déduite de l'écart médian entre deux passages."""
    mg = median(ecarts) if ecarts else 30
    if mg <= 10:
        return "weekly"
    if mg <= 20:
        return "biweekly"
    if mg <= 45:
        return "monthly"
    if mg <= 135:
        return "quarterly"
    return "yearly"


def detect_recurring_candidates(txs: list[dict], min_months: int = 4) -> list[dict]:
    """Analyse les opérations passées et propose des opérations récurrentes.

    Regroupe par libellé normalisé, ne retient que les groupes présents sur
    au moins `min_months` mois distincts et de signe cohérent, puis déduit
    fréquence, jour du mois, montant, catégorie et type.

    Seules comptent les opérations qui passent ENCORE : un groupe dont le
    dernier passage est trop ancien (cf. _FRAICHEUR_MAX) est écarté. Le délai
    se mesure depuis la dernière opération de l'historique, pas depuis
    aujourd'hui, pour ne rien perdre chez qui n'a pas importé depuis
    longtemps. Montant, jour et fréquence viennent des derniers passages.
    Les échéances générées d'avance (prevue=1) ne sont pas des passages.

    Chaque candidat porte des métadonnées (préfixées « _ ») pour l'aperçu :
    nombre de mois, fourchette de montants, stabilité et pré-sélection.
    """
    txs = [t for t in txs if t.get("date") and not t.get("prevue")]
    if not txs:
        return []
    reference = max(date.fromisoformat(t["date"][:10]) for t in txs)

    groups: dict[str, list[dict]] = defaultdict(list)
    for t in txs:
        key = _recurring_norm_label(t.get("libelle", ""))
        if not key:
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

        # Du plus ancien au plus récent
        items = sorted(items, key=lambda t: t["date"])
        dates = [date.fromisoformat(t["date"][:10]) for t in items]
        gaps = [(dates[i + 1] - dates[i]).days
                for i in range(len(dates) - 1)
                if (dates[i + 1] - dates[i]).days > 0]
        # Fréquence d'après les derniers écarts, pas d'après des années
        freq = _frequence(gaps[-6:])

        # Plus de passage depuis trop longtemps : l'opération est arrêtée
        if (reference - dates[-1]).days > _FRAICHEUR_MAX[freq]:
            continue

        recents = items[-_PASSAGES_RECENTS:]
        med = round(median(float(t.get("montant", 0)) for t in recents), 2)
        dom = int(median(d.day for d in dates[-_PASSAGES_RECENTS:]))

        cat = Counter(t.get("categorie", "") for t in items).most_common(1)[0][0]
        sub = Counter((t.get("sous_cat") or "") for t in items).most_common(1)[0][0]
        typ = Counter((t.get("type") or "") for t in items).most_common(1)[0][0]

        # Stabilité et fourchette jugées sur les six derniers passages
        amounts = [float(t.get("montant", 0)) for t in items[-6:]]
        spread = max(amounts) - min(amounts)
        stable = abs(spread) <= max(2.0, 0.15 * abs(med)) if med else False

        # Régularité : les trois derniers écarts tombent tous dans la plage
        # normale de la fréquence. Une dépense occasionnelle au même montant
        # (un jeu, un achat ponctuel) reste montrée, mais n'est pas pré-cochée.
        lo, hi = _ECART_REGULIER[freq]
        regulier = len(gaps) >= 3 and all(lo <= g <= hi for g in gaps[-3:])

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
            "_default":     stable and regulier
                            and (cat not in SKIP_DEFAULT_CATS)
                            and freq in ("monthly", "quarterly", "yearly"),
        })

    cands.sort(key=lambda c: (-c["_months"], -abs(c["montant"])))
    return cands


def candidats_non_couverts(cands: list[dict], recs: list) -> list[dict]:
    """Retire des candidats ce qu'une récurrence existante couvre déjà.

    Une récurrence (active ou non : la désactiver est un choix) couvre un
    candidat quand :
      * leurs libellés désignent la même opération (_meme_operation : l'un est
        le début de l'autre — « Caisse » et « Caisse Retraite ») ;
      * ou, sous des noms différents, même sens, même montant à quelques
        centimes près et même jour à trois jours près : c'est l'ancien nom
        d'une récurrence dont la banque a changé le libellé.
    """
    existantes = [(_recurring_norm_label(r["libelle"]), float(r["montant"]),
                   r["day_of_month"]) for r in recs]
    garde = []
    for c in cands:
        cle = _recurring_norm_label(c["libelle"])
        m = float(c["montant"])
        couvert = False
        for cle_r, m_r, jour_r in existantes:
            meme_nom = _meme_operation(cle, cle_r)
            meme_sens = (m > 0) == (m_r > 0)
            meme_montant = abs(abs(m) - abs(m_r)) <= max(0.5, 0.02 * abs(m_r))
            meme_jour = (jour_r is not None
                         and abs(int(jour_r) - int(c["day_of_month"])) <= 3)
            if meme_nom or (meme_sens and meme_montant and meme_jour):
                couvert = True
                break
        if not couvert:
            garde.append(c)
    return garde
