"""Tests de la couche d'accès SQLite (CRUD, réglages, budgets, tombstones)."""
from comptesbudget.database import Database


def _tx(**kw):
    base = {
        "id": "tx1", "date": "2026-06-23", "date_valeur": "2026-06-23",
        "libelle": "TEST", "libelle_op": "TEST", "reference": "", "type": "",
        "categorie": "Non classé", "sous_cat": "", "info": "",
        "montant": -10.0, "pointee": 0,
    }
    base.update(kw)
    return base


def test_insert_list_update_tx(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.insert_tx(_tx())
    rows = [dict(r) for r in db.list_tx()]
    assert len(rows) == 1
    assert rows[0]["updated_at"]   # horodatage posé automatiquement

    db.update_tx("tx1", {"categorie": "Alimentation"})
    assert [dict(r) for r in db.list_tx()][0]["categorie"] == "Alimentation"


def test_toggle_pointee(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.insert_tx(_tx(pointee=0))
    db.toggle_pointee("tx1")
    assert [dict(r) for r in db.list_tx()][0]["pointee"] == 1


def test_delete_tx_pose_tombstone(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.insert_tx(_tx())
    db.delete_tx("tx1")
    assert list(db.list_tx()) == []
    dels = db.list_deletions()
    assert any(d["entity"] == "transactions" and d["id"] == "tx1" for d in dels)


def test_settings(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    assert db.get_setting("inexistant", "defaut") == "defaut"
    db.set_setting("initial_balance", "1500")
    assert db.get_setting("initial_balance") == "1500"


def test_budgets(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.set_budget("Alimentation", 400.0)
    db.set_budget("Alimentation", 450.0)   # upsert
    assert db.list_budgets() == {"Alimentation": 450.0}


def test_batch_groupe_les_ecritures(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    with db.batch():
        db.insert_tx(_tx(id="a"))
        db.insert_tx(_tx(id="b"))
    assert len(list(db.list_tx())) == 2


def test_batch_annule_tout_en_cas_d_erreur(tmp_path):
    # Tout-ou-rien : une erreur au milieu d'un batch ne laisse rien derrière.
    db = Database(str(tmp_path / "t.db"))
    db.insert_tx(_tx(id="avant"))
    try:
        with db.batch():
            db.insert_tx(_tx(id="pendant"))
            raise RuntimeError("boum")
    except RuntimeError:
        pass
    ids = {dict(r)["id"] for r in db.list_tx()}
    assert ids == {"avant"}


def test_batch_imbrique_tolere(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    with db.batch():
        with db.batch():   # imbriqué : sans effet, pas d'erreur
            db.insert_tx(_tx(id="x"))
    assert len(list(db.list_tx())) == 1


def test_migration_colonne_prevue_sur_base_ancienne(tmp_path):
    """Une base créée avant la v1.21 (sans colonne « prevue ») doit s'ouvrir
    sans rien perdre : la colonne est ajoutée et vaut 0 partout."""
    import sqlite3

    chemin = str(tmp_path / "ancienne.db")
    conn = sqlite3.connect(chemin)
    conn.executescript("""
        CREATE TABLE transactions (
            id TEXT PRIMARY KEY, date TEXT NOT NULL, date_valeur TEXT,
            libelle TEXT NOT NULL DEFAULT '', libelle_op TEXT NOT NULL DEFAULT '',
            reference TEXT NOT NULL DEFAULT '', type TEXT NOT NULL DEFAULT '',
            categorie TEXT NOT NULL DEFAULT 'Non classé',
            sous_cat TEXT NOT NULL DEFAULT '', info TEXT NOT NULL DEFAULT '',
            montant REAL NOT NULL, pointee INTEGER NOT NULL DEFAULT 0);
        INSERT INTO transactions (id, date, libelle, montant, pointee)
            VALUES ('vieux-1', '2026-01-15', 'ANCIENNE OPERATION', -42.5, 1);
    """)
    conn.commit()
    conn.close()

    db = Database(chemin)                       # ouverture = migration
    lignes = [dict(t) for t in db.list_tx()]
    assert len(lignes) == 1                     # la donnée est intacte
    assert lignes[0]["libelle"] == "ANCIENNE OPERATION"
    assert lignes[0]["montant"] == -42.5
    assert lignes[0]["pointee"] == 1
    assert lignes[0]["prevue"] == 0             # valeur par défaut

    # Et la nouvelle colonne est utilisable
    db.insert_tx({"id": "neuf", "date": "2026-08-10", "date_valeur": "2026-08-10",
                  "libelle": "PRETIS", "libelle_op": "PRETIS", "reference": "",
                  "type": "", "categorie": "Non classé", "sous_cat": "", "info": "",
                  "montant": -600.00, "pointee": 0, "prevue": 1})
    assert [t["prevue"] for t in db.list_tx() if t["id"] == "neuf"] == [1]
