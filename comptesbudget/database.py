"""Accès à la base de données SQLite."""
import os
import sqlite3
from datetime import datetime, timezone

from .constants import DB_PATH
from .utils import _now_iso

class Database:
    def __init__(self, path: str = DB_PATH):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()
        self._init_defaults()

    def _init_defaults(self):
        """Valeurs par défaut au premier lancement.

        Le solde de départ n'est volontairement PAS pré-rempli : il est propre
        à chaque utilisateur et lui est demandé au premier lancement
        (cf. MainWindow._maybe_prompt_initial_setup). Tant qu'il n'est pas
        renseigné, il est traité comme 0 par les calculs de solde."""
        if not self.get_setting("initial_date"):
            self.set_setting("initial_date", "2025-01-01")

    def _init_schema(self):
        c = self.conn.cursor()
        c.executescript("""
        CREATE TABLE IF NOT EXISTS transactions (
            id            TEXT PRIMARY KEY,
            date          TEXT NOT NULL,        -- YYYY-MM-DD
            date_valeur   TEXT,
            libelle       TEXT NOT NULL DEFAULT '',
            libelle_op    TEXT NOT NULL DEFAULT '',
            reference     TEXT NOT NULL DEFAULT '',
            type          TEXT NOT NULL DEFAULT '',
            categorie     TEXT NOT NULL DEFAULT 'Non classé',
            sous_cat      TEXT NOT NULL DEFAULT '',
            info          TEXT NOT NULL DEFAULT '',
            montant       REAL NOT NULL,
            pointee       INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(date);
        CREATE INDEX IF NOT EXISTS idx_tx_cat  ON transactions(categorie);

        CREATE TABLE IF NOT EXISTS budgets (
            categorie TEXT PRIMARY KEY,
            montant   REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS rules (
            id            TEXT PRIMARY KEY,
            pattern       TEXT NOT NULL,
            amount        REAL,
            categorie     TEXT NOT NULL DEFAULT '',
            sous_cat      TEXT NOT NULL DEFAULT '',
            no_overwrite  INTEGER NOT NULL DEFAULT 0,
            created_at    TEXT NOT NULL DEFAULT (date('now'))
        );

        CREATE TABLE IF NOT EXISTS recurring (
            id          TEXT PRIMARY KEY,
            libelle     TEXT NOT NULL,
            montant     REAL NOT NULL,
            categorie   TEXT NOT NULL DEFAULT '',
            sous_cat    TEXT NOT NULL DEFAULT '',
            type        TEXT NOT NULL DEFAULT '',
            frequency   TEXT NOT NULL,           -- monthly / weekly / etc.
            day_of_month INTEGER,
            start_date  TEXT NOT NULL,
            end_date    TEXT,
            actif       INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        -- Pierres tombales : suppressions à propager lors de la synchronisation.
        CREATE TABLE IF NOT EXISTS deletions (
            entity     TEXT NOT NULL,   -- 'transactions' | 'rules' | 'recurring'
            id         TEXT NOT NULL,
            deleted_at TEXT NOT NULL,
            PRIMARY KEY (entity, id)
        );
        """)
        self.conn.commit()
        self._migrate_sync()

    def _migrate_sync(self):
        """Ajoute la colonne updated_at aux tables existantes si absente, et
        renseigne les valeurs nulles avec la date de dernière modif de la base."""
        try:
            backfill = datetime.fromtimestamp(
                os.path.getmtime(self.path), tz=timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
        except OSError:
            backfill = _now_iso()
        for table in ("transactions", "rules", "recurring"):
            cols = [r[1] for r in self.conn.execute(
                f"PRAGMA table_info({table})")]
            if "updated_at" not in cols:
                self.conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN updated_at TEXT")
            self.conn.execute(
                f"UPDATE {table} SET updated_at = ? WHERE updated_at IS NULL "
                f"OR updated_at = ''", (backfill,))
        # Sens des règles ('' = les deux, 'debit', 'credit') — ajouté en 1.10.0.
        # Reclassement unique des règles existantes : créées depuis des débits,
        # sauf celles qui ciblent Revenus (crédits) ; les virements internes
        # peuvent aller dans les deux sens.
        rcols = [r[1] for r in self.conn.execute("PRAGMA table_info(rules)")]
        if "sens" not in rcols:
            self.conn.execute("ALTER TABLE rules ADD COLUMN sens TEXT DEFAULT ''")
            self.conn.execute("UPDATE rules SET sens='credit' WHERE categorie='Revenus'")
            self.conn.execute(
                "UPDATE rules SET sens='debit' "
                "WHERE categorie NOT IN ('Revenus', 'Virements internes', '')")
        # Horodatages méta (budgets / réglages) : valeur de départ = date de la
        # base, pour une fusion équitable au premier échange (ne pas se laisser
        # écraser par des réglages par défaut d'un autre appareil).
        for mk in ("_meta_settings_updated_at", "_meta_budgets_updated_at"):
            self.conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (mk, backfill))
        self.conn.commit()

    # ── Transactions ────────────────────────────────────────────────
    def list_tx(self) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM transactions ORDER BY date DESC"))

    def insert_tx(self, tx: dict):
        tx = {**tx, "updated_at": tx.get("updated_at") or _now_iso()}
        self.conn.execute("""
            INSERT INTO transactions (id, date, date_valeur, libelle, libelle_op,
                reference, type, categorie, sous_cat, info, montant, pointee, updated_at)
            VALUES (:id, :date, :date_valeur, :libelle, :libelle_op,
                :reference, :type, :categorie, :sous_cat, :info, :montant, :pointee, :updated_at)
        """, tx)
        self._clear_deletion("transactions", tx["id"])
        self.conn.commit()

    def update_tx(self, tx_id: str, fields: dict):
        fields = {**fields, "updated_at": fields.get("updated_at") or _now_iso()}
        sets = ", ".join(f"{k} = :{k}" for k in fields)
        fields["id"] = tx_id
        self.conn.execute(f"UPDATE transactions SET {sets} WHERE id = :id", fields)
        self.conn.commit()

    def delete_tx(self, tx_id: str):
        self._record_deletion("transactions", tx_id)
        self.conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
        self.conn.commit()

    def toggle_pointee(self, tx_id: str):
        self.conn.execute(
            "UPDATE transactions SET pointee = 1 - pointee, updated_at = ? "
            "WHERE id = ?", (_now_iso(), tx_id))
        self.conn.commit()

    def all_categories_used(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT categorie FROM transactions ORDER BY categorie")
        return [r[0] for r in rows if r[0]]

    # ── Règles ──────────────────────────────────────────────────────
    def list_rules(self) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM rules"))

    def insert_rule(self, rule: dict):
        rule = {**rule, "updated_at": rule.get("updated_at") or _now_iso(),
                "sens": rule.get("sens") or ""}
        self.conn.execute("""
            INSERT INTO rules (id, pattern, amount, categorie, sous_cat,
                no_overwrite, created_at, updated_at, sens)
            VALUES (:id, :pattern, :amount, :categorie, :sous_cat,
                :no_overwrite, :created_at, :updated_at, :sens)
        """, rule)
        self._clear_deletion("rules", rule["id"])
        self.conn.commit()

    def update_rule(self, rule_id: str, fields: dict):
        fields = {**fields, "updated_at": fields.get("updated_at") or _now_iso()}
        sets = ", ".join(f"{k} = :{k}" for k in fields)
        fields["id"] = rule_id
        self.conn.execute(f"UPDATE rules SET {sets} WHERE id = :id", fields)
        self.conn.commit()

    def delete_rule(self, rule_id: str):
        self._record_deletion("rules", rule_id)
        self.conn.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
        self.conn.commit()

    # ── Budgets ─────────────────────────────────────────────────────
    def list_budgets(self) -> dict[str, float]:
        return {r[0]: r[1] for r in
                self.conn.execute("SELECT categorie, montant FROM budgets")}

    def set_budget(self, categorie: str, montant: float):
        self.conn.execute("""
            INSERT INTO budgets (categorie, montant) VALUES (?, ?)
            ON CONFLICT(categorie) DO UPDATE SET montant = excluded.montant
        """, (categorie, montant))
        self.conn.commit()
        self.set_setting("_meta_budgets_updated_at", _now_iso())

    # ── Récurrent ───────────────────────────────────────────────────
    def list_recurring(self) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM recurring ORDER BY libelle"))

    def insert_recurring(self, rec: dict):
        rec = {**rec, "updated_at": rec.get("updated_at") or _now_iso()}
        self.conn.execute("""
            INSERT INTO recurring (id, libelle, montant, categorie, sous_cat, type,
                frequency, day_of_month, start_date, end_date, actif, updated_at)
            VALUES (:id, :libelle, :montant, :categorie, :sous_cat, :type,
                :frequency, :day_of_month, :start_date, :end_date, :actif, :updated_at)
        """, rec)
        self._clear_deletion("recurring", rec["id"])
        self.conn.commit()

    def update_recurring(self, rec_id: str, fields: dict):
        fields = {**fields, "updated_at": fields.get("updated_at") or _now_iso()}
        sets = ", ".join(f"{k} = :{k}" for k in fields)
        fields["id"] = rec_id
        self.conn.execute(f"UPDATE recurring SET {sets} WHERE id = :id", fields)
        self.conn.commit()

    def delete_recurring(self, rec_id: str):
        self._record_deletion("recurring", rec_id)
        self.conn.execute("DELETE FROM recurring WHERE id = ?", (rec_id,))
        self.conn.commit()

    # ── Settings ────────────────────────────────────────────────────
    def get_setting(self, key: str, default: str = "") -> str:
        r = self.conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return r[0] if r else default

    def set_setting(self, key: str, value: str):
        self.conn.execute("""
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, value))
        self.conn.commit()
        # Les clés méta-sync ne déclenchent pas d'horodatage récursif.
        if not key.startswith("_meta_"):
            self.conn.execute("""
                INSERT INTO settings (key, value) VALUES ('_meta_settings_updated_at', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (_now_iso(),))
            self.conn.commit()

    # ── Synchronisation : tombstones & upserts bruts ────────────────
    def _record_deletion(self, entity: str, id_: str, deleted_at: str = None):
        self.conn.execute("""
            INSERT INTO deletions (entity, id, deleted_at) VALUES (?, ?, ?)
            ON CONFLICT(entity, id) DO UPDATE SET deleted_at = excluded.deleted_at
        """, (entity, id_, deleted_at or _now_iso()))

    def _clear_deletion(self, entity: str, id_: str):
        self.conn.execute(
            "DELETE FROM deletions WHERE entity = ? AND id = ?", (entity, id_))

    def list_deletions(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT entity, id, deleted_at FROM deletions")]

    def deletion_map(self) -> dict[tuple, str]:
        return {(r["entity"], r["id"]): r["deleted_at"]
                for r in self.conn.execute(
                    "SELECT entity, id, deleted_at FROM deletions")}

    def upsert_synced(self, entity: str, rec: dict):
        """Insère/remplace un enregistrement venu de la fusion en conservant
        son updated_at d'origine (ne pas réhorodater à « maintenant »)."""
        cols = {
            "transactions": ["id", "date", "date_valeur", "libelle", "libelle_op",
                             "reference", "type", "categorie", "sous_cat", "info",
                             "montant", "pointee", "updated_at"],
            "rules": ["id", "pattern", "amount", "categorie", "sous_cat",
                      "no_overwrite", "created_at", "updated_at", "sens"],
            "recurring": ["id", "libelle", "montant", "categorie", "sous_cat",
                          "type", "frequency", "day_of_month", "start_date",
                          "end_date", "actif", "updated_at"],
        }[entity]
        vals = {c: rec.get(c) for c in cols}
        placeholders = ", ".join(f":{c}" for c in cols)
        collist = ", ".join(cols)
        self.conn.execute(
            f"INSERT OR REPLACE INTO {entity} ({collist}) VALUES ({placeholders})",
            vals)
        self._clear_deletion(entity, rec.get("id"))

    def delete_synced(self, entity: str, id_: str, deleted_at: str):
        self.conn.execute(f"DELETE FROM {entity} WHERE id = ?", (id_,))
        self._record_deletion(entity, id_, deleted_at)

    def replace_budgets(self, budgets: dict, updated_at: str):
        self.conn.execute("DELETE FROM budgets")
        for cat, montant in budgets.items():
            self.conn.execute(
                "INSERT INTO budgets (categorie, montant) VALUES (?, ?)",
                (cat, float(montant)))
        self.conn.execute("""
            INSERT INTO settings (key, value) VALUES ('_meta_budgets_updated_at', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (updated_at,))
        self.conn.commit()

    # Réglages partagés (solde / date initiale) : application sans ré-horodater.
    SYNCED_SETTINGS = ("initial_balance", "initial_date")

    def apply_settings_synced(self, settings: dict, updated_at: str):
        for k in self.SYNCED_SETTINGS:
            v = settings.get(k)
            if v is None:
                continue
            self.conn.execute("""
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (k, str(v)))
        self.conn.execute("""
            INSERT INTO settings (key, value) VALUES ('_meta_settings_updated_at', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (updated_at,))
        self.conn.commit()
