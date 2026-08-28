"""Accès à la base de données SQLite."""
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from .constants import DB_PATH
from .utils import _now_iso

class Database:
    def __init__(self, path: str = DB_PATH, compte_id: str = None):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._in_batch = False
        # Compte de travail. Depuis la 1.24.0 l'application gère plusieurs
        # comptes bancaires : les opérations, budgets et récurrences lus ou
        # écrits ici ne concernent QUE ce compte. Les règles automatiques,
        # les catégories et les libellés restent communs à tous les comptes.
        self.compte_id = None
        self._init_schema()
        self._select_compte_initial(compte_id)
        self._init_defaults()

    # ── Transaction groupée ─────────────────────────────────────────
    @contextmanager
    def batch(self):
        """Groupe plusieurs écritures en UNE seule transaction.

        Sans cela, chaque insertion/mise à jour écrit physiquement sur le
        disque (commit) : un import de 300 lignes = 300 écritures, d'où la
        lenteur des opérations en masse. À l'intérieur d'un `with db.batch():`,
        les commits intermédiaires sont suspendus ; tout est validé d'un coup
        à la sortie — et rien n'est enregistré si une erreur survient
        (tout-ou-rien). Les appels imbriqués sont tolérés (sans effet)."""
        if self._in_batch:
            yield
            return
        self._in_batch = True
        try:
            yield
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise
        finally:
            self._in_batch = False

    def _commit(self):
        """Commit immédiat, sauf à l'intérieur d'un batch()."""
        if not self._in_batch:
            self.conn.commit()

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
        -- Comptes bancaires suivis (multicomptes depuis la 1.24.0).
        -- Le solde et la date de départ sont propres à chaque compte.
        CREATE TABLE IF NOT EXISTS comptes (
            id            TEXT PRIMARY KEY,
            nom           TEXT NOT NULL,
            -- NULL = solde de départ jamais renseigné (à ne pas confondre
            -- avec un solde de zéro : l'invite du premier lancement s'appuie
            -- sur cette distinction).
            solde_initial REAL,
            date_initiale TEXT NOT NULL DEFAULT '2025-01-01',
            ordre         INTEGER NOT NULL DEFAULT 0,
            updated_at    TEXT
        );

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
            pointee       INTEGER NOT NULL DEFAULT 0,
            -- Échéance saisie d'avance (« Générer les échéances du mois ») :
            -- attendue mais pas encore passée en banque. Sert à la rattacher
            -- à la ligne du relevé lors de l'import, même si la banque la
            -- passe un autre jour. Repasse à 0 dès qu'elle est rapprochée.
            prevue        INTEGER NOT NULL DEFAULT 0
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
        self._migrate_prevue()
        self._migrate_comptes()

    def _migrate_prevue(self):
        """Ajoute la colonne « prevue » aux bases antérieures à la v1.21.

        ALTER TABLE ... ADD COLUMN ne touche pas aux lignes existantes : elles
        prennent la valeur 0 (opération ordinaire), donc rien ne change pour
        les données déjà enregistrées."""
        cols = [r[1] for r in self.conn.execute("PRAGMA table_info(transactions)")]
        if "prevue" not in cols:
            self.conn.execute("ALTER TABLE transactions "
                              "ADD COLUMN prevue INTEGER NOT NULL DEFAULT 0")
            self.conn.commit()

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

    # ── Comptes ─────────────────────────────────────────────────────
    DEFAULT_COMPTE_ID = "compte-1"
    DEFAULT_COMPTE_NOM = "Compte courant"

    def _migrate_comptes(self):
        """Passage au multicomptes (1.24.0), sans rien perdre.

        Les bases d'avant ne connaissaient qu'un seul compte. Toutes leurs
        données sont rattachées ici à un compte « Compte courant », qui
        hérite du solde et de la date de départ enregistrés dans les
        réglages. Pour qui utilisait déjà le logiciel, rien ne change à
        l'écran : il retrouve ses opérations, ses budgets et son solde."""
        # 1. Créer le compte par défaut si la base n'en a aucun.
        if not self.conn.execute("SELECT COUNT(*) FROM comptes").fetchone()[0]:
            brut = self.get_setting("initial_balance", "")
            try:
                solde = float(brut) if brut else None
            except ValueError:
                solde = None
            self.conn.execute(
                "INSERT INTO comptes (id, nom, solde_initial, date_initiale, "
                "ordre, updated_at) VALUES (?, ?, ?, ?, 0, ?)",
                (self.DEFAULT_COMPTE_ID, self.DEFAULT_COMPTE_NOM, solde,
                 self.get_setting("initial_date", "") or "2025-01-01",
                 _now_iso()))

        # Compte auquel rattacher les données déjà présentes : le premier.
        cible = self.conn.execute(
            "SELECT id FROM comptes ORDER BY ordre, nom").fetchone()[0]

        # 2. Colonne compte_id sur les tables qui suivent le compte.
        #    ALTER TABLE ... ADD COLUMN laisse les lignes existantes intactes :
        #    le UPDATE qui suit leur donne le compte par défaut.
        for table in ("transactions", "recurring"):
            cols = [r[1] for r in self.conn.execute(
                f"PRAGMA table_info({table})")]
            if "compte_id" not in cols:
                self.conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN compte_id TEXT")
            self.conn.execute(
                f"UPDATE {table} SET compte_id = ? "
                f"WHERE compte_id IS NULL OR compte_id = ''", (cible,))
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_tx_compte "
                          "ON transactions(compte_id, date)")

        # 3. Budgets : la clé primaire passe de (categorie) à
        #    (compte_id, categorie), pour qu'un même poste puisse avoir un
        #    budget différent sur chaque compte. SQLite ne sait pas modifier
        #    une clé primaire : on recrée la table et on recopie les lignes.
        bcols = [r[1] for r in self.conn.execute("PRAGMA table_info(budgets)")]
        if "compte_id" not in bcols:
            self.conn.execute("""
                CREATE TABLE budgets_nouveau (
                    compte_id TEXT NOT NULL,
                    categorie TEXT NOT NULL,
                    montant   REAL NOT NULL,
                    PRIMARY KEY (compte_id, categorie)
                )""")
            self.conn.execute(
                "INSERT INTO budgets_nouveau (compte_id, categorie, montant) "
                "SELECT ?, categorie, montant FROM budgets", (cible,))
            self.conn.execute("DROP TABLE budgets")
            self.conn.execute("ALTER TABLE budgets_nouveau RENAME TO budgets")
        self.conn.commit()

    def _select_compte_initial(self, compte_id: str = None):
        """Choisit le compte de travail au démarrage : celui demandé, sinon
        le dernier utilisé, sinon le premier de la liste."""
        connus = [r["id"] for r in self.list_comptes()]
        for candidat in (compte_id, self.get_setting("compte_courant", "")):
            if candidat and candidat in connus:
                self.compte_id = candidat
                return
        self.compte_id = connus[0] if connus else None

    def list_comptes(self) -> list[sqlite3.Row]:
        return list(self.conn.execute(
            "SELECT * FROM comptes ORDER BY ordre, nom"))

    def get_compte(self, compte_id: str = None) -> sqlite3.Row:
        return self.conn.execute(
            "SELECT * FROM comptes WHERE id = ?",
            (compte_id or self.compte_id,)).fetchone()

    def nb_operations(self, compte_id: str = None) -> int:
        """Nombre d'opérations enregistrées sur un compte."""
        return self.conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE compte_id = ?",
            (compte_id or self.compte_id,)).fetchone()[0]

    def nom_compte(self, compte_id: str = None) -> str:
        r = self.get_compte(compte_id)
        return r["nom"] if r else ""

    def set_compte_courant(self, compte_id: str):
        """Change le compte de travail, et s'en souvient au prochain lancement."""
        self.compte_id = compte_id
        self.set_setting("compte_courant", compte_id)

    def add_compte(self, nom: str, solde_initial: float = None,
                   date_initiale: str = "2025-01-01") -> str:
        cid = str(uuid.uuid4())
        ordre = self.conn.execute(
            "SELECT COALESCE(MAX(ordre), -1) + 1 FROM comptes").fetchone()[0]
        self.conn.execute(
            "INSERT INTO comptes (id, nom, solde_initial, date_initiale, "
            "ordre, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (cid, nom, None if solde_initial is None else float(solde_initial),
             date_initiale, ordre, _now_iso()))
        self._commit()
        return cid

    def update_compte(self, compte_id: str, fields: dict):
        fields = {**fields, "updated_at": _now_iso()}
        sets = ", ".join(f"{k} = :{k}" for k in fields)
        fields["id"] = compte_id
        self.conn.execute(f"UPDATE comptes SET {sets} WHERE id = :id", fields)
        self._commit()

    def delete_compte(self, compte_id: str):
        """Supprime un compte ET tout ce qu'il contient (opérations, budgets,
        récurrences). Le dernier compte ne peut pas être supprimé :
        l'application a besoin d'au moins un compte pour fonctionner."""
        if len(self.list_comptes()) <= 1:
            raise ValueError("Impossible de supprimer le dernier compte.")
        with self.batch():
            for table in ("transactions", "recurring"):
                for row in self.conn.execute(
                        f"SELECT id FROM {table} WHERE compte_id = ?",
                        (compte_id,)).fetchall():
                    self._record_deletion(table, row[0])
                self.conn.execute(
                    f"DELETE FROM {table} WHERE compte_id = ?", (compte_id,))
            self.conn.execute(
                "DELETE FROM budgets WHERE compte_id = ?", (compte_id,))
            self.conn.execute("DELETE FROM comptes WHERE id = ?", (compte_id,))
        if self.compte_id == compte_id:
            self._select_compte_initial()

    # Solde et date de départ : propres à chaque compte (ils étaient dans les
    # réglages généraux avant la 1.24.0).
    def solde_initial(self) -> float:
        """Solde de départ du compte de travail (0 s'il n'est pas renseigné)."""
        r = self.get_compte()
        if not r or r["solde_initial"] is None:
            return 0.0
        return float(r["solde_initial"])

    def date_initiale(self) -> str:
        r = self.get_compte()
        return r["date_initiale"] if r else "2025-01-01"

    def set_solde_initial(self, solde: float, date_iso: str):
        self.update_compte(self.compte_id, {"solde_initial": float(solde),
                                            "date_initiale": date_iso})

    # ── Transactions ────────────────────────────────────────────────
    def list_tx(self) -> list[sqlite3.Row]:
        """Opérations du compte de travail, de la plus récente à la plus ancienne."""
        return list(self.conn.execute(
            "SELECT * FROM transactions WHERE compte_id = ? ORDER BY date DESC",
            (self.compte_id,)))

    def insert_tx(self, tx: dict):
        # « prevue » est facultative pour l'appelant : une opération ordinaire
        # n'a pas à s'en préoccuper.
        tx = {**tx, "updated_at": tx.get("updated_at") or _now_iso(),
              "prevue": 1 if tx.get("prevue") else 0,
              "compte_id": tx.get("compte_id") or self.compte_id}
        self.conn.execute("""
            INSERT INTO transactions (id, compte_id, date, date_valeur, libelle,
                libelle_op, reference, type, categorie, sous_cat, info, montant,
                pointee, prevue, updated_at)
            VALUES (:id, :compte_id, :date, :date_valeur, :libelle,
                :libelle_op, :reference, :type, :categorie, :sous_cat, :info,
                :montant, :pointee, :prevue, :updated_at)
        """, tx)
        self._clear_deletion("transactions", tx["id"])
        self._commit()

    def update_tx(self, tx_id: str, fields: dict):
        fields = {**fields, "updated_at": fields.get("updated_at") or _now_iso()}
        sets = ", ".join(f"{k} = :{k}" for k in fields)
        fields["id"] = tx_id
        self.conn.execute(f"UPDATE transactions SET {sets} WHERE id = :id", fields)
        self._commit()

    def delete_tx(self, tx_id: str):
        self._record_deletion("transactions", tx_id)
        self.conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
        self._commit()

    def toggle_pointee(self, tx_id: str):
        self.conn.execute(
            "UPDATE transactions SET pointee = 1 - pointee, updated_at = ? "
            "WHERE id = ?", (_now_iso(), tx_id))
        self._commit()

    def all_categories_used(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT categorie FROM transactions WHERE compte_id = ? "
            "ORDER BY categorie", (self.compte_id,))
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
        self._commit()

    def update_rule(self, rule_id: str, fields: dict):
        fields = {**fields, "updated_at": fields.get("updated_at") or _now_iso()}
        sets = ", ".join(f"{k} = :{k}" for k in fields)
        fields["id"] = rule_id
        self.conn.execute(f"UPDATE rules SET {sets} WHERE id = :id", fields)
        self._commit()

    def delete_rule(self, rule_id: str):
        self._record_deletion("rules", rule_id)
        self.conn.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
        self._commit()

    # ── Budgets ─────────────────────────────────────────────────────
    def list_budgets(self) -> dict[str, float]:
        """Budgets du compte de travail (chaque compte a les siens)."""
        return {r[0]: r[1] for r in self.conn.execute(
            "SELECT categorie, montant FROM budgets WHERE compte_id = ?",
            (self.compte_id,))}

    def set_budget(self, categorie: str, montant: float):
        self.conn.execute("""
            INSERT INTO budgets (compte_id, categorie, montant) VALUES (?, ?, ?)
            ON CONFLICT(compte_id, categorie)
                DO UPDATE SET montant = excluded.montant
        """, (self.compte_id, categorie, montant))
        self._commit()
        self.set_setting("_meta_budgets_updated_at", _now_iso())

    # ── Récurrent ───────────────────────────────────────────────────
    def list_recurring(self) -> list[sqlite3.Row]:
        """Récurrences du compte de travail."""
        return list(self.conn.execute(
            "SELECT * FROM recurring WHERE compte_id = ? ORDER BY libelle",
            (self.compte_id,)))

    def insert_recurring(self, rec: dict):
        rec = {**rec, "updated_at": rec.get("updated_at") or _now_iso(),
               "compte_id": rec.get("compte_id") or self.compte_id}
        self.conn.execute("""
            INSERT INTO recurring (id, compte_id, libelle, montant, categorie,
                sous_cat, type, frequency, day_of_month, start_date, end_date,
                actif, updated_at)
            VALUES (:id, :compte_id, :libelle, :montant, :categorie,
                :sous_cat, :type, :frequency, :day_of_month, :start_date,
                :end_date, :actif, :updated_at)
        """, rec)
        self._clear_deletion("recurring", rec["id"])
        self._commit()

    def update_recurring(self, rec_id: str, fields: dict):
        fields = {**fields, "updated_at": fields.get("updated_at") or _now_iso()}
        sets = ", ".join(f"{k} = :{k}" for k in fields)
        fields["id"] = rec_id
        self.conn.execute(f"UPDATE recurring SET {sets} WHERE id = :id", fields)
        self._commit()

    def delete_recurring(self, rec_id: str):
        self._record_deletion("recurring", rec_id)
        self.conn.execute("DELETE FROM recurring WHERE id = ?", (rec_id,))
        self._commit()

    # ── Settings ────────────────────────────────────────────────────
    # Le solde et la date de départ appartiennent au COMPTE depuis la 1.24.0.
    # Ils restent lisibles et modifiables sous leurs anciens noms de réglage :
    # tout le code qui s'en sert continue de fonctionner sans changement, et
    # s'applique automatiquement au compte de travail.
    COMPTE_SETTINGS = {"initial_balance": "solde_initial",
                       "initial_date": "date_initiale"}

    def get_setting(self, key: str, default: str = "") -> str:
        if key in self.COMPTE_SETTINGS and self.compte_id:
            r = self.get_compte()
            v = r[self.COMPTE_SETTINGS[key]] if r else None
            if v is None or v == "":
                return default
            if isinstance(v, float):
                # 1500.0 doit se relire « 1500 », comme avant.
                return str(int(v)) if v == int(v) else str(v)
            return str(v)
        r = self.conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return r[0] if r else default

    def set_setting(self, key: str, value: str):
        if key in self.COMPTE_SETTINGS and self.compte_id:
            champ = self.COMPTE_SETTINGS[key]
            if champ == "solde_initial":
                try:
                    value = float(value) if value != "" else None
                except (TypeError, ValueError):
                    value = None
            self.conn.execute(
                f"UPDATE comptes SET {champ} = ?, updated_at = ? WHERE id = ?",
                (value, _now_iso(), self.compte_id))
        else:
            self.conn.execute("""
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (key, value))
        self._commit()
        # Les clés méta-sync ne déclenchent pas d'horodatage récursif.
        if not key.startswith("_meta_"):
            self.conn.execute("""
                INSERT INTO settings (key, value) VALUES ('_meta_settings_updated_at', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (_now_iso(),))
            self._commit()

    # ── Correspondances de libellés ─────────────────────────────────
    def get_alias_libelles(self) -> dict:
        """Correspondances « libellé du relevé → nom voulu », rangées en JSON
        dans les réglages. Elles restent dans la base : ce sont des données
        personnelles, elles n'ont pas leur place dans le code."""
        brut = self.get_setting("alias_libelles", "")
        if not brut:
            return {}
        try:
            data = json.loads(brut)
        except ValueError:
            return {}                  # réglage illisible : on l'ignore
        if not isinstance(data, dict):
            return {}
        return {str(k): str(v) for k, v in data.items()}

    def set_alias_libelles(self, alias: dict):
        self.set_setting("alias_libelles",
                         json.dumps(alias or {}, ensure_ascii=False))

    # ── Lecture tous comptes (export / sauvegarde) ──────────────────
    # Les méthodes ci-dessus ne montrent que le compte de travail, ce qui est
    # le bon comportement à l'écran. Une sauvegarde, elle, doit tout emporter.
    def list_tx_all(self) -> list[sqlite3.Row]:
        return list(self.conn.execute(
            "SELECT * FROM transactions ORDER BY date DESC"))

    def list_recurring_all(self) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM recurring ORDER BY libelle"))

    def list_budgets_all(self) -> dict[str, dict[str, float]]:
        """{ compte_id : { catégorie : montant } }"""
        res = {}
        for r in self.conn.execute(
                "SELECT compte_id, categorie, montant FROM budgets"):
            res.setdefault(r[0], {})[r[1]] = r[2]
        return res

    def upsert_compte(self, rec: dict):
        """Crée ou met à jour un compte venu d'un fichier d'échange, en
        gardant son identifiant : c'est lui qui relie les opérations."""
        self.conn.execute("""
            INSERT INTO comptes (id, nom, solde_initial, date_initiale, ordre,
                                 updated_at)
            VALUES (:id, :nom, :solde_initial, :date_initiale, :ordre,
                    :updated_at)
            ON CONFLICT(id) DO UPDATE SET
                nom = excluded.nom,
                solde_initial = excluded.solde_initial,
                date_initiale = excluded.date_initiale,
                ordre = excluded.ordre,
                updated_at = excluded.updated_at
        """, {
            "id": rec.get("id"),
            "nom": rec.get("nom") or "Compte",
            "solde_initial": rec.get("solde_initial"),
            "date_initiale": rec.get("date_initiale") or "2025-01-01",
            "ordre": rec.get("ordre") or 0,
            "updated_at": rec.get("updated_at") or _now_iso(),
        })
        self._commit()

    def set_budgets_compte(self, compte_id: str, budgets: dict):
        """Remplace les budgets d'un compte précis (restauration)."""
        self.conn.execute("DELETE FROM budgets WHERE compte_id = ?", (compte_id,))
        for cat, montant in (budgets or {}).items():
            self.conn.execute(
                "INSERT INTO budgets (compte_id, categorie, montant) "
                "VALUES (?, ?, ?)", (compte_id, cat, float(montant)))
        self._commit()

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
            "transactions": ["id", "compte_id", "date", "date_valeur",
                             "libelle", "libelle_op", "reference", "type",
                             "categorie", "sous_cat", "info", "montant",
                             "pointee", "prevue", "updated_at"],
            "rules": ["id", "pattern", "amount", "categorie", "sous_cat",
                      "no_overwrite", "created_at", "updated_at", "sens"],
            "recurring": ["id", "compte_id", "libelle", "montant", "categorie",
                          "sous_cat", "type", "frequency", "day_of_month",
                          "start_date", "end_date", "actif", "updated_at"],
        }[entity]
        vals = {c: rec.get(c) for c in cols}
        if "compte_id" in cols and not vals.get("compte_id"):
            # Fichier d'échange écrit par une version d'avant le multicomptes :
            # ses enregistrements rejoignent le compte de travail.
            vals["compte_id"] = self.compte_id
        if entity == "transactions":
            # Un fichier d'échange écrit par une version antérieure ne connaît
            # pas « prevue » : sans cela on insérerait NULL dans une colonne
            # déclarée NOT NULL.
            vals["prevue"] = 1 if vals.get("prevue") else 0
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
        self.conn.execute("DELETE FROM budgets WHERE compte_id = ?",
                          (self.compte_id,))
        for cat, montant in budgets.items():
            self.conn.execute(
                "INSERT INTO budgets (compte_id, categorie, montant) "
                "VALUES (?, ?, ?)", (self.compte_id, cat, float(montant)))
        self.conn.execute("""
            INSERT INTO settings (key, value) VALUES ('_meta_budgets_updated_at', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (updated_at,))
        self._commit()

    # Réglages partagés (solde / date initiale) : application sans ré-horodater.
    SYNCED_SETTINGS = ("initial_balance", "initial_date")

    def apply_settings_synced(self, settings: dict, updated_at: str):
        for k in self.SYNCED_SETTINGS:
            v = settings.get(k)
            if v is None:
                continue
            # Passe par set_setting : ces deux clés appartiennent au compte.
            self.set_setting(k, str(v))
        self.conn.execute("""
            INSERT INTO settings (key, value) VALUES ('_meta_settings_updated_at', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (updated_at,))
        self._commit()
