"""Utilitaires : horodatage, sauvegarde, formatage et normalisation."""
import os
import shutil
import unicodedata
from datetime import date, datetime, timezone
from typing import Optional

from .constants import (
    _app_dir,
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
    bdir = os.path.join(_app_dir(), "sauvegardes")
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


def list_periods(transactions: list[dict]) -> list[str]:
    """Retourne la liste triée des périodes (mois + années) présentes."""
    years = set()
    months = set()
    for t in transactions:
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


def fmt_date_fr(iso: str) -> str:
    """ISO yyyy-mm-dd → jj/mm/aaaa. Retourne la chaîne telle quelle si non parsable."""
    if not iso or len(iso) < 10:
        return iso or ""
    y, m, d = iso[:4], iso[5:7], iso[8:10]
    return f"{d}/{m}/{y}"
