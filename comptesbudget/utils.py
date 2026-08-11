"""Utilitaires : horodatage, sauvegarde, formatage et normalisation."""
import os
import shutil
import unicodedata
from calendar import monthrange
from datetime import date, datetime, timezone
from typing import Optional

from .constants import (
    _app_dir,     # réexporté : app.py l'importe depuis ce module (icône)
    _data_dir,
    DB_PATH,
    CANONICAL_CATS,
    CATEGORY_COLORS,
    _HARMONIZE_COMPILED,
)

def _now_iso() -> str:
    """Horodatage UTC ISO 8601 (comparable lexicalement)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def backup_db(path: str = DB_PATH, keep: int = 10) -> Optional[str]:
    """Copie de sécurité QUOTIDIENNE de la base dans « sauvegardes/ ».

    Appelée au lancement, AVANT l'ouverture de la base : même une migration
    ratée ne peut donc pas abîmer la copie. Une seule copie par jour (les
    relances du même jour ne réécrivent pas), rotation sur les `keep` plus
    récentes. Retourne le chemin de la sauvegarde du jour, ou None."""
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
        # Rotation : noms triables lexicalement (comptes-AAAA-MM-JJ.db)
        baks = sorted(f for f in os.listdir(bdir)
                      if f.startswith("comptes-") and f.endswith(".db"))
        for old in baks[:-keep]:
            try:
                os.remove(os.path.join(bdir, old))
            except OSError:
                pass
        return dest
    except OSError:
        return None   # disque plein / droits : ne jamais bloquer le lancement


def suggest_category(libelle: str, sous_cat: str = "") -> Optional[str]:
    """Retourne la catégorie suggérée d'après libellé/sous-cat, ou None."""
    blob = deaccent(f"{libelle} {sous_cat}")
    for rx, cat in _HARMONIZE_COMPILED:
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
    """Retourne la liste triée des périodes (mois + années) présentes.

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
    out += sorted(years, reverse=True)
    out += sorted(months, reverse=True)
    return out


def period_label(p: str) -> str:
    if p == "all":
        return "Toutes périodes"
    if len(p) == 4:
        return f"Année {p}"
    if len(p) == 7:
        mois = ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
        try:
            return f"{mois[int(p[5:7])]} {p[:4]}"
        except (ValueError, IndexError):
            return p
    return p


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
