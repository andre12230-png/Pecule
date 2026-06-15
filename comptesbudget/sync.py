"""Moteur de fusion par enregistrement (LWW) — DORMANT depuis la v1.9.5.

Non câblé à l'interface (l'app HTML et sa synchronisation ont été retirées) ;
conservé pour pouvoir fusionner/restaurer un fichier d'échange JSON si besoin.
"""
import json
import os
from typing import TYPE_CHECKING, Optional

from .constants import SYNC_PATH, SYNC_VERSION
from .utils import _now_iso

if TYPE_CHECKING:
    from .database import Database

def db_snapshot(db: "Database") -> dict:
    """État complet de la base pour le fichier de synchronisation."""
    return {
        "version": SYNC_VERSION,
        "app": "comptes_budget.py",
        "synced_at": _now_iso(),
        "transactions": [dict(r) for r in db.list_tx()],
        "rules":        [dict(r) for r in db.list_rules()],
        "recurring":    [dict(r) for r in db.list_recurring()],
        "budgets":      db.list_budgets(),
        "budgets_updated_at": db.get_setting("_meta_budgets_updated_at", ""),
        "settings": {
            "initial_balance": db.get_setting("initial_balance", ""),
            "initial_date":    db.get_setting("initial_date", ""),
        },
        "settings_updated_at": db.get_setting("_meta_settings_updated_at", ""),
        "deletions":    db.list_deletions(),
    }


def write_sync_file(db: "Database", path: str = SYNC_PATH) -> str:
    """Écrit le snapshot de façon atomique. Retourne le synced_at écrit."""
    snap = db_snapshot(db)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=1, default=str)
    os.replace(tmp, path)
    return snap["synced_at"]


def read_sync_file(path: str = SYNC_PATH) -> Optional[dict]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _eff_ts(rec: dict, fallback: str) -> str:
    """Horodatage effectif d'un enregistrement distant : son updated_at, sinon
    le synced_at du fichier (compatibilité avec un export sans horodatage)."""
    return rec.get("updated_at") or fallback or "1970-01-01T00:00:00Z"


def merge_remote_into_db(db: "Database", remote: Optional[dict]) -> dict:
    """Fusionne un snapshot distant dans la base : pour chaque enregistrement,
    la version au updated_at le plus récent gagne ; les pierres tombales
    suppriment si elles sont plus récentes que la version locale."""
    stats = {"applied": 0, "deleted": 0}
    if not remote:
        return stats
    fallback = remote.get("synced_at") or ""

    local = {
        "transactions": {r["id"]: dict(r) for r in db.list_tx()},
        "rules":        {r["id"]: dict(r) for r in db.list_rules()},
        "recurring":    {r["id"]: dict(r) for r in db.list_recurring()},
    }
    del_map = db.deletion_map()

    # 1) Enregistrements distants → upsert si plus récents
    for entity in ("transactions", "rules", "recurring"):
        for rec in remote.get(entity, []) or []:
            rid = rec.get("id")
            if not rid:
                continue
            ts = _eff_ts(rec, fallback)
            del_ts = del_map.get((entity, rid))
            if del_ts and del_ts >= ts:
                continue  # suppression locale plus récente
            cur = local[entity].get(rid)
            if cur is None or (cur.get("updated_at") or "") < ts:
                db.upsert_synced(entity, {**rec, "updated_at": ts})
                stats["applied"] += 1

    # 2) Pierres tombales distantes
    for d in remote.get("deletions", []) or []:
        entity = d.get("entity")
        rid = d.get("id")
        dts = d.get("deleted_at") or fallback
        if entity not in local or not rid:
            continue
        cur = local[entity].get(rid)
        if cur is not None and (cur.get("updated_at") or "") < dts:
            db.delete_synced(entity, rid, dts)
            stats["deleted"] += 1
        elif cur is None and dts > del_map.get((entity, rid), ""):
            db._record_deletion(entity, rid, dts)

    # 3) Budgets : objet entier, le plus récent l'emporte
    r_bud_ts = remote.get("budgets_updated_at") or fallback
    l_bud_ts = db.get_setting("_meta_budgets_updated_at", "")
    if "budgets" in remote and r_bud_ts and r_bud_ts > l_bud_ts:
        db.replace_budgets(remote.get("budgets") or {}, r_bud_ts)

    # 4) Réglages partagés (solde / date initiale) : le plus récent l'emporte
    r_set_ts = remote.get("settings_updated_at") or ""
    l_set_ts = db.get_setting("_meta_settings_updated_at", "")
    rset = remote.get("settings") or {}
    if rset and r_set_ts and r_set_ts > l_set_ts:
        db.apply_settings_synced(rset, r_set_ts)
        stats["applied"] += 1

    db.conn.commit()
    return stats
