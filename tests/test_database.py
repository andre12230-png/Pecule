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
