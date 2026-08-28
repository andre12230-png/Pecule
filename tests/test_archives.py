"""Tests de l'archivage des opérations anciennes (1.25.0).

L'exigence qui tient tout le reste : **archiver ne doit pas changer le solde**.
Une opération mise de côté sort des listes, mais son montant rejoint le solde
de départ — sinon masquer reviendrait à supprimer.
"""
from comptesbudget.database import Database
from comptesbudget.sync import db_snapshot, merge_remote_into_db


def _tx(id_, date, montant, pointee=1, **kw):
    base = {
        "id": id_, "date": date, "date_valeur": date,
        "libelle": "TEST", "libelle_op": "TEST", "reference": "", "type": "",
        "categorie": "Alimentation", "sous_cat": "", "info": "",
        "montant": montant, "pointee": pointee,
    }
    base.update(kw)
    return base


def _base(tmp_path):
    """Un compte à 1 000 €, avec trois opérations anciennes et deux récentes."""
    db = Database(str(tmp_path / "t.db"))
    db.set_setting("initial_balance", "1000")
    db.set_setting("initial_date", "2020-01-01")
    db.insert_tx(_tx("v1", "2020-03-01", -100.0))
    db.insert_tx(_tx("v2", "2021-06-15", -50.0))
    db.insert_tx(_tx("v3", "2022-12-31", 25.0))
    db.insert_tx(_tx("r1", "2025-02-01", -10.0))
    db.insert_tx(_tx("r2", "2026-01-10", -5.0))
    return db


def _solde(db):
    """Le solde tel que le calcule le Bilan : départ + opérations pointées,
    hors « Transaction exclue »."""
    base = float(db.get_setting("initial_balance", "0") or 0)
    debut = db.get_setting("initial_date", "1900-01-01")
    return round(base + sum(
        t["montant"] for t in (dict(r) for r in db.list_tx())
        if t["pointee"] and t["categorie"] != "Transaction exclue"
        and (t["date_valeur"] or t["date"]) >= debut), 2)


# ── Le solde ne bouge pas ───────────────────────────────────────────

def test_archiver_ne_change_pas_le_solde(tmp_path):
    db = _base(tmp_path)
    avant = _solde(db)
    assert avant == 860.0          # 1000 - 100 - 50 + 25 - 10 - 5

    db.archiver("2022-12-31")
    assert _solde(db) == avant


def test_archiver_masque_sans_supprimer(tmp_path):
    db = _base(tmp_path)
    assert db.archiver("2022-12-31") == 3

    visibles = [r["id"] for r in db.list_tx()]
    assert sorted(visibles) == ["r1", "r2"]
    # Rien n'a quitté la base
    assert len(db.list_tx_all()) == 5
    assert db.nb_archivees() == 3


def test_solde_de_depart_se_decale_a_la_coupure(tmp_path):
    db = _base(tmp_path)
    db.archiver("2022-12-31")
    # 1000 - 100 - 50 + 25 = 875, au lendemain de la coupure
    assert db.get_setting("initial_balance") == "875"
    assert db.get_setting("initial_date") == "2023-01-01"


def test_voir_les_archives_retablit_le_point_de_depart(tmp_path):
    db = _base(tmp_path)
    db.archiver("2022-12-31")

    db.set_voir_archives(True)
    assert len(db.list_tx()) == 5
    assert db.get_setting("initial_balance") == "1000"
    assert db.get_setting("initial_date") == "2020-01-01"
    assert _solde(db) == 860.0     # le même solde, par l'autre chemin

    db.set_voir_archives(False)
    assert len(db.list_tx()) == 2
    assert _solde(db) == 860.0


def test_desarchiver_remet_tout(tmp_path):
    db = _base(tmp_path)
    db.archiver("2022-12-31")
    assert db.desarchiver() == 3

    assert len(db.list_tx()) == 5
    assert db.nb_archivees() == 0
    assert db.archive_jusqua() == ""
    assert db.get_setting("initial_balance") == "1000"
    assert _solde(db) == 860.0


# ── Détail du comportement ──────────────────────────────────────────

def test_coupure_incluse_et_memorisee(tmp_path):
    db = _base(tmp_path)
    db.archiver("2022-12-31")
    assert db.archive_jusqua() == "2022-12-31"
    # L'opération DU 31/12 est bien archivée (coupure incluse)
    db.set_voir_archives(True)
    archivees = [dict(r) for r in db.list_tx() if r["archivee"]]
    assert "v3" in [t["id"] for t in archivees]


def test_archivage_suit_la_date_de_valeur(tmp_path):
    """Un achat par carte de décembre prélevé en janvier appartient à
    janvier : c'est la date de valeur qui décide, comme sur le relevé."""
    db = Database(str(tmp_path / "t.db"))
    db.insert_tx(_tx("carte", "2022-12-28", -30.0, date_valeur="2023-01-04"))
    assert db.a_archiver("2022-12-31") == 0
    assert db.a_archiver("2023-01-31") == 1


def test_archiver_deux_fois_cumule(tmp_path):
    db = _base(tmp_path)
    db.archiver("2021-12-31")
    assert db.nb_archivees() == 2
    solde = _solde(db)
    db.archiver("2022-12-31")
    assert db.nb_archivees() == 3
    assert db.archive_jusqua() == "2022-12-31"
    assert _solde(db) == solde


def test_archivage_propre_a_chaque_compte(tmp_path):
    db = _base(tmp_path)
    c1 = db.compte_id
    c2 = db.add_compte("Second", 0.0, "2020-01-01")
    db.set_compte_courant(c2)
    db.insert_tx(_tx("s1", "2020-05-05", -20.0))

    db.set_compte_courant(c1)
    db.archiver("2022-12-31")

    db.set_compte_courant(c2)
    assert db.nb_archivees() == 0
    assert len(db.list_tx()) == 1
    assert db.archive_jusqua() == ""


def test_les_categories_suivent_le_filtre(tmp_path):
    db = _base(tmp_path)
    db.insert_tx(_tx("vieux", "2020-04-01", -8.0, categorie="Loisirs"))
    db.archiver("2022-12-31")
    assert "Loisirs" not in db.all_categories_used()
    db.set_voir_archives(True)
    assert "Loisirs" in db.all_categories_used()


# ── Export ──────────────────────────────────────────────────────────

def test_export_et_restauration_gardent_les_archives(tmp_path):
    db = _base(tmp_path)
    db.archiver("2022-12-31")
    snap = db_snapshot(db)
    assert len(snap["transactions"]) == 5     # l'export emporte tout

    neuve = Database(str(tmp_path / "neuve.db"))
    merge_remote_into_db(neuve, snap)
    neuve.set_compte_courant(db.compte_id)
    assert neuve.nb_archivees() == 3
    assert neuve.archive_jusqua() == "2022-12-31"
    assert len(neuve.list_tx()) == 2
    assert _solde(neuve) == 860.0


def test_fichier_ancien_sans_archives_reste_lisible(tmp_path):
    """Un export d'avant l'archivage n'a pas la colonne : ses opérations
    doivent arriver non archivées, pas avec un NULL interdit."""
    db = Database(str(tmp_path / "t.db"))
    ancien = {
        "version": 3, "synced_at": "2026-01-01T00:00:00Z",
        "transactions": [_tx("vieux", "2020-01-01", -5.0)],
        "rules": [], "recurring": [], "budgets": {},
        "budgets_updated_at": "", "settings": {}, "deletions": [],
    }
    merge_remote_into_db(db, ancien)
    assert [r["id"] for r in db.list_tx()] == ["vieux"]
    assert db.nb_archivees() == 0
