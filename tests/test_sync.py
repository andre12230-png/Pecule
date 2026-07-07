"""Tests du moteur de fusion (utilisé par « ♻️ Restaurer (JSON) »)."""
from comptesbudget.database import Database
from comptesbudget.sync import db_snapshot, merge_remote_into_db


def _tx(**kw):
    base = {
        "id": "tx1", "date": "2026-06-23", "date_valeur": "2026-06-23",
        "libelle": "TEST", "libelle_op": "TEST", "reference": "", "type": "",
        "categorie": "Non classé", "sous_cat": "", "info": "",
        "montant": -10.0, "pointee": 0,
    }
    base.update(kw)
    return base


def test_fusion_le_plus_recent_gagne(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.insert_tx(_tx(id="a", categorie="Non classé",
                     updated_at="2026-01-01T00:00:00Z"))
    remote = {
        "synced_at": "2026-02-01T00:00:00Z",
        "transactions": [_tx(id="a", categorie="Alimentation",
                             updated_at="2026-02-01T00:00:00Z")],
    }
    stats = merge_remote_into_db(db, remote)
    assert stats["applied"] == 1
    assert dict(db.list_tx()[0])["categorie"] == "Alimentation"


def test_fusion_n_ecrase_pas_plus_recent(tmp_path):
    # Restaurer un VIEUX fichier ne doit pas faire reculer les données locales.
    db = Database(str(tmp_path / "t.db"))
    db.insert_tx(_tx(id="a", categorie="Santé",
                     updated_at="2026-03-01T00:00:00Z"))
    remote = {
        "synced_at": "2026-01-01T00:00:00Z",
        "transactions": [_tx(id="a", categorie="Loisirs",
                             updated_at="2026-01-01T00:00:00Z")],
    }
    stats = merge_remote_into_db(db, remote)
    assert stats["applied"] == 0
    assert dict(db.list_tx()[0])["categorie"] == "Santé"


def test_fusion_propage_les_suppressions(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.insert_tx(_tx(id="a", updated_at="2026-01-01T00:00:00Z"))
    remote = {
        "synced_at": "2026-02-01T00:00:00Z",
        "deletions": [{"entity": "transactions", "id": "a",
                       "deleted_at": "2026-02-01T00:00:00Z"}],
    }
    stats = merge_remote_into_db(db, remote)
    assert stats["deleted"] == 1
    assert list(db.list_tx()) == []


def test_export_puis_fusion_sur_soi_meme_est_neutre(tmp_path):
    # Réimporter son propre export ne doit rien changer (idempotence).
    db = Database(str(tmp_path / "t.db"))
    db.insert_tx(_tx(id="a"))
    db.set_budget("Alimentation", 400.0)
    snap = db_snapshot(db)
    stats = merge_remote_into_db(db, snap)
    assert stats["applied"] == 0
    assert stats["deleted"] == 0
    assert len(list(db.list_tx())) == 1
    assert db.list_budgets() == {"Alimentation": 400.0}


def test_export_restaure_sur_base_vierge(tmp_path):
    # Le duo export → restauration reconstruit les données sur une base neuve.
    db1 = Database(str(tmp_path / "a.db"))
    db1.insert_tx(_tx(id="a", libelle="LOYER", montant=-800.0))
    db1.set_budget("Logement - maison", 900.0)
    db1.set_setting("initial_balance", "1500")
    snap = db_snapshot(db1)

    db2 = Database(str(tmp_path / "b.db"))
    stats = merge_remote_into_db(db2, snap)
    assert stats["applied"] >= 1
    assert dict(db2.list_tx()[0])["libelle"] == "LOYER"
    assert db2.list_budgets() == {"Logement - maison": 900.0}
    assert db2.get_setting("initial_balance") == "1500"
