"""Tests du multicomptes (1.24.0).

Deux exigences tiennent tout le reste :
  1. une base d'avant le multicomptes doit se retrouver intacte, rattachée à
     un compte « Compte courant » — personne ne doit rien perdre ;
  2. deux comptes ne doivent jamais se mélanger : opérations, budgets,
     récurrences et solde de départ sont propres à chacun, tandis que les
     règles automatiques restent communes.
"""
import sqlite3

from comptesbudget.database import Database
from comptesbudget.sync import db_snapshot, merge_remote_into_db


def _tx(id_, montant=-10.0, date="2026-06-23", **kw):
    base = {
        "id": id_, "date": date, "date_valeur": date,
        "libelle": "TEST", "libelle_op": "TEST", "reference": "", "type": "",
        "categorie": "Non classé", "sous_cat": "", "info": "",
        "montant": montant, "pointee": 0,
    }
    base.update(kw)
    return base


def _rec(id_, **kw):
    base = {
        "id": id_, "libelle": "LOYER", "montant": -500.0,
        "categorie": "Logement - maison", "sous_cat": "", "type": "",
        "frequency": "monthly", "day_of_month": 5,
        "start_date": "2026-01-01", "end_date": None, "actif": 1,
    }
    base.update(kw)
    return base


# ── Migration d'une base d'avant le multicomptes ────────────────────

def _base_ancienne(chemin):
    """Fabrique une base au schéma d'avant la 1.24.0 (sans notion de compte)."""
    conn = sqlite3.connect(chemin)
    conn.executescript("""
        CREATE TABLE transactions (
            id TEXT PRIMARY KEY, date TEXT NOT NULL, date_valeur TEXT,
            libelle TEXT NOT NULL DEFAULT '', libelle_op TEXT NOT NULL DEFAULT '',
            reference TEXT NOT NULL DEFAULT '', type TEXT NOT NULL DEFAULT '',
            categorie TEXT NOT NULL DEFAULT 'Non classé',
            sous_cat TEXT NOT NULL DEFAULT '', info TEXT NOT NULL DEFAULT '',
            montant REAL NOT NULL, pointee INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE budgets (categorie TEXT PRIMARY KEY, montant REAL NOT NULL);
        CREATE TABLE rules (id TEXT PRIMARY KEY, pattern TEXT NOT NULL,
            amount REAL, categorie TEXT NOT NULL DEFAULT '',
            sous_cat TEXT NOT NULL DEFAULT '',
            no_overwrite INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (date('now')));
        CREATE TABLE recurring (id TEXT PRIMARY KEY, libelle TEXT NOT NULL,
            montant REAL NOT NULL, categorie TEXT NOT NULL DEFAULT '',
            sous_cat TEXT NOT NULL DEFAULT '', type TEXT NOT NULL DEFAULT '',
            frequency TEXT NOT NULL, day_of_month INTEGER,
            start_date TEXT NOT NULL, end_date TEXT,
            actif INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE deletions (entity TEXT NOT NULL, id TEXT NOT NULL,
            deleted_at TEXT NOT NULL, PRIMARY KEY (entity, id));
        INSERT INTO transactions (id, date, libelle, montant, pointee)
            VALUES ('a', '2025-03-01', 'ANCIENNE', -25.5, 1),
                   ('b', '2025-04-02', 'AUTRE', 100.0, 1);
        INSERT INTO budgets VALUES ('Alimentation', 300.0);
        INSERT INTO settings VALUES ('initial_balance', '1250.5'),
                                    ('initial_date', '2025-01-01');
    """)
    conn.commit()
    conn.close()


def test_migration_conserve_tout(tmp_path):
    chemin = str(tmp_path / "ancienne.db")
    _base_ancienne(chemin)

    db = Database(chemin)

    comptes = db.list_comptes()
    assert len(comptes) == 1
    assert comptes[0]["nom"] == "Compte courant"

    # Les données d'avant sont là, rattachées à ce compte.
    assert len(db.list_tx()) == 2
    assert db.list_budgets() == {"Alimentation": 300.0}
    assert db.solde_initial() == 1250.5
    assert db.date_initiale() == "2025-01-01"
    # Plus aucune ligne orpheline
    assert db.conn.execute(
        "SELECT COUNT(*) FROM transactions WHERE compte_id IS NULL"
    ).fetchone()[0] == 0


def test_migration_ne_se_rejoue_pas(tmp_path):
    chemin = str(tmp_path / "ancienne.db")
    _base_ancienne(chemin)
    Database(chemin).conn.close()
    db = Database(chemin)
    assert len(db.list_comptes()) == 1
    assert len(db.list_tx()) == 2


def test_solde_non_renseigne_reste_vide(tmp_path):
    """Un solde à zéro n'est pas un solde absent : l'invite du premier
    lancement s'appuie sur cette différence."""
    db = Database(str(tmp_path / "neuve.db"))
    assert db.get_setting("initial_balance") == ""
    db.set_setting("initial_balance", "0")
    assert db.get_setting("initial_balance") == "0"


# ── Isolation entre comptes ─────────────────────────────────────────

def _deux_comptes(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    c1 = db.compte_id
    c2 = db.add_compte("Second", 500.0, "2026-01-01")
    return db, c1, c2


def test_operations_isolees(tmp_path):
    db, c1, c2 = _deux_comptes(tmp_path)
    db.insert_tx(_tx("t1", -10.0))
    db.set_compte_courant(c2)
    db.insert_tx(_tx("t2", -20.0))
    db.insert_tx(_tx("t3", -30.0))

    assert [r["id"] for r in db.list_tx()] == ["t2", "t3"] or \
           sorted(r["id"] for r in db.list_tx()) == ["t2", "t3"]
    db.set_compte_courant(c1)
    assert [r["id"] for r in db.list_tx()] == ["t1"]
    # L'export, lui, voit tout
    assert len(db.list_tx_all()) == 3


def test_budgets_et_recurrences_isoles(tmp_path):
    db, c1, c2 = _deux_comptes(tmp_path)
    db.set_budget("Alimentation", 300.0)
    db.insert_recurring(_rec("r1"))

    db.set_compte_courant(c2)
    assert db.list_budgets() == {}
    assert list(db.list_recurring()) == []
    db.set_budget("Alimentation", 80.0)
    db.insert_recurring(_rec("r2", libelle="ASSURANCE"))

    assert db.list_budgets() == {"Alimentation": 80.0}
    db.set_compte_courant(c1)
    assert db.list_budgets() == {"Alimentation": 300.0}
    assert [r["id"] for r in db.list_recurring()] == ["r1"]


def test_regles_communes_aux_comptes(tmp_path):
    db, c1, c2 = _deux_comptes(tmp_path)
    db.insert_rule({"id": "g1", "pattern": "LIDL", "amount": None,
                    "categorie": "Alimentation", "sous_cat": "",
                    "no_overwrite": 0, "created_at": "2026-01-01"})
    db.set_compte_courant(c2)
    assert [r["id"] for r in db.list_rules()] == ["g1"]


def test_solde_de_depart_par_compte(tmp_path):
    db, c1, c2 = _deux_comptes(tmp_path)
    db.set_setting("initial_balance", "1000")
    assert db.solde_initial() == 1000.0
    db.set_compte_courant(c2)
    assert db.solde_initial() == 500.0
    assert db.get_setting("initial_balance") == "500"
    db.set_compte_courant(c1)
    assert db.solde_initial() == 1000.0


def test_compte_courant_memorise(tmp_path):
    chemin = str(tmp_path / "t.db")
    db = Database(chemin)
    c2 = db.add_compte("Second")
    db.set_compte_courant(c2)
    db.conn.close()

    db2 = Database(chemin)
    assert db2.compte_id == c2
    assert db2.nom_compte() == "Second"


# ── Suppression ─────────────────────────────────────────────────────

def test_suppression_emporte_le_contenu(tmp_path):
    db, c1, c2 = _deux_comptes(tmp_path)
    db.set_compte_courant(c2)
    db.insert_tx(_tx("t2"))
    db.set_budget("Loisirs", 50.0)
    db.insert_recurring(_rec("r2"))
    db.set_compte_courant(c1)
    db.insert_tx(_tx("t1"))

    db.delete_compte(c2)
    assert [r["id"] for r in db.list_comptes()] == [c1]
    assert len(db.list_tx_all()) == 1
    assert db.conn.execute(
        "SELECT COUNT(*) FROM budgets WHERE compte_id = ?", (c2,)
    ).fetchone()[0] == 0
    # La suppression est propagée (pierre tombale) pour la synchronisation
    assert any(d["id"] == "t2" for d in db.list_deletions())


def test_dernier_compte_non_supprimable(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    try:
        db.delete_compte(db.compte_id)
    except ValueError:
        pass
    else:
        raise AssertionError("le dernier compte ne devrait pas être supprimable")
    assert len(db.list_comptes()) == 1


def test_suppression_du_compte_affiche_bascule(tmp_path):
    db, c1, c2 = _deux_comptes(tmp_path)
    db.set_compte_courant(c2)
    db.delete_compte(c2)
    assert db.compte_id == c1


# ── Export / restauration ───────────────────────────────────────────

def test_export_puis_restauration_rend_les_deux_comptes(tmp_path):
    db, c1, c2 = _deux_comptes(tmp_path)
    db.insert_tx(_tx("t1", -10.0))
    db.set_budget("Alimentation", 300.0)
    db.set_compte_courant(c2)
    db.insert_tx(_tx("t2", -20.0))
    db.set_budget("Alimentation", 80.0)

    snap = db_snapshot(db)
    assert len(snap["comptes"]) == 2
    assert len(snap["transactions"]) == 2

    # Restauration dans une base neuve
    neuve = Database(str(tmp_path / "neuve.db"))
    merge_remote_into_db(neuve, snap)

    noms = sorted(r["nom"] for r in neuve.list_comptes())
    assert "Second" in noms
    assert len(neuve.list_tx_all()) == 2

    neuve.set_compte_courant(c2)
    assert [r["id"] for r in neuve.list_tx()] == ["t2"]
    assert neuve.list_budgets() == {"Alimentation": 80.0}
    assert neuve.solde_initial() == 500.0

    neuve.set_compte_courant(c1)
    assert [r["id"] for r in neuve.list_tx()] == ["t1"]
    assert neuve.list_budgets() == {"Alimentation": 300.0}


def test_restauration_fichier_ancien_rejoint_le_compte_affiche(tmp_path):
    """Un export écrit avant le multicomptes n'a pas de compte : ses
    opérations doivent rejoindre le compte de travail, pas se perdre."""
    db = Database(str(tmp_path / "t.db"))
    ancien = {
        "version": 2, "synced_at": "2026-01-01T00:00:00Z",
        "transactions": [_tx("vieux", -5.0)],
        "rules": [], "recurring": [], "budgets": {"Loisirs": 40.0},
        "budgets_updated_at": "2026-01-01T00:00:00Z",
        "settings": {}, "deletions": [],
    }
    merge_remote_into_db(db, ancien)
    assert [r["id"] for r in db.list_tx()] == ["vieux"]
    assert db.list_budgets() == {"Loisirs": 40.0}
