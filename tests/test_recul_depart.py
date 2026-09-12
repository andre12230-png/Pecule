"""Reculer la date de départ sans changer le solde du jour (1.37.0).

Le cas vécu (12/09/2026, un nouvel utilisateur) : au premier lancement,
Pécule demande le solde de départ AVANT tout import. On y met naturellement
le solde du jour, daté du jour. Puis on importe un an de relevé CSV : les
350 opérations tombent toutes avant la date de départ, et sortent du calcul
du solde. Le bandeau disait « reculez la date », sans dire quel solde mettre
en face.

Pécule propose désormais de reculer la date à la plus ancienne opération en
calculant lui-même le nouveau solde de départ, de sorte que le solde
d'aujourd'hui reste exactement celui que l'utilisateur a saisi.
"""
from comptesbudget.database import Database


AUJOURDHUI = "2026-09-12"


def _tx(id_, date, montant, pointee=1, **kw):
    base = {
        "id": id_, "date": date, "date_valeur": date,
        "libelle": "TEST", "libelle_op": "TEST", "reference": "", "type": "",
        "categorie": "Non classé", "sous_cat": "", "info": "",
        "montant": montant, "pointee": pointee,
    }
    base.update(kw)
    return base


def _banque(db):
    """Le « Solde bancaire réel », calculé par Pécule lui-même (même
    fonction que le récapitulatif, mêmes règles que le Bilan)."""
    return db.soldes_compte(db.compte_id, AUJOURDHUI)["banque"]


def _base_historique(tmp_path):
    """Solde du jour saisi au 11/09, puis un historique importé après coup."""
    db = Database(str(tmp_path / "t.db"))
    db.set_setting("initial_balance", "2000")
    db.set_setting("initial_date", "2026-09-11")
    db.insert_tx(_tx("a", "2025-09-15", 1500.0))
    db.insert_tx(_tx("b", "2026-03-02", -600.0))
    db.insert_tx(_tx("c", "2026-09-08", -100.0))
    return db


def test_le_solde_du_jour_ne_bouge_pas(tmp_path):
    db = _base_historique(tmp_path)
    assert _banque(db) == 2000.0            # l'historique ne compte pas

    prop = db.proposition_recul_depart()
    assert prop is not None
    assert prop["nb"] == 3
    assert prop["date"] == "2025-09-15"     # la plus ancienne opération
    assert prop["solde"] == 1200.0          # 2 000 − (1 500 − 600 − 100)

    db.reculer_depart(prop)
    assert db.get_setting("initial_date") == "2025-09-15"
    assert _banque(db) == 2000.0            # toujours le solde saisi
    assert db.proposition_recul_depart() is None   # plus rien avant le départ


def test_operation_non_pointee_hors_du_calcul(tmp_path):
    """Une opération non pointée n'entre pas dans le solde bancaire : elle
    ne doit pas non plus entrer dans le calcul du nouveau solde de départ."""
    db = _base_historique(tmp_path)
    db.insert_tx(_tx("np", "2026-01-10", -50.0, pointee=0))
    prop = db.proposition_recul_depart()
    assert prop["nb"] == 4
    assert prop["nb_non_pointees"] == 1
    assert prop["solde"] == 1200.0

    db.reculer_depart(prop)
    assert _banque(db) == 2000.0


def test_transaction_exclue_ignoree(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.set_setting("initial_balance", "500")
    db.set_setting("initial_date", "2026-09-01")
    db.insert_tx(_tx("x", "2026-05-01", -99.0, categorie="Transaction exclue"))
    assert db.proposition_recul_depart() is None


def test_rien_avant_le_depart(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.set_setting("initial_balance", "500")
    db.set_setting("initial_date", "2026-01-01")
    db.insert_tx(_tx("r", "2026-02-01", -10.0))
    assert db.proposition_recul_depart() is None


def test_carte_a_debit_differe_deja_dans_le_solde(tmp_path):
    """Achat du 28/08 débité le 04/09 : sa date de valeur suit le départ,
    il compte déjà — rien à proposer."""
    db = Database(str(tmp_path / "t.db"))
    db.set_setting("initial_balance", "500")
    db.set_setting("initial_date", "2026-09-01")
    db.insert_tx(_tx("cb", "2026-08-28", -30.0, date_valeur="2026-09-04"))
    assert db.proposition_recul_depart() is None


def test_solde_de_depart_jamais_saisi(tmp_path):
    """Sans solde de départ, il n'y a pas de « solde du jour » à préserver :
    le calcul n'aurait pas de sens, on ne propose rien."""
    db = Database(str(tmp_path / "t.db"))
    db.set_setting("initial_date", "2026-09-01")
    db.insert_tx(_tx("a", "2026-05-01", -10.0))
    assert db.proposition_recul_depart() is None


def test_lien_du_bandeau(qapp, tmp_path, monkeypatch):
    """Le lien du bandeau orange pose la question ; « Reculer la date »
    applique la proposition et fait disparaître le bandeau."""
    from comptesbudget.ui.main_window import MainWindow
    db = _base_historique(tmp_path)
    fenetre = MainWindow(db)
    fenetre.refresh_all()
    assert not fenetre.bilan_view.hors_solde_alert.isHidden()

    monkeypatch.setattr(MainWindow, "_demander_recul_depart",
                        lambda self, prop: "reculer")
    fenetre.bilan_view.goto_recul_depart.emit()
    assert db.get_setting("initial_date") == "2025-09-15"
    assert _banque(db) == 2000.0
    assert fenetre.bilan_view.hors_solde_alert.isHidden()


def test_apres_import_laisser_tel_quel(qapp, tmp_path, monkeypatch):
    """Après un import, la question est posée ; « Laisser tel quel » ne
    change rien."""
    from PySide6.QtWidgets import QMessageBox
    from comptesbudget.ui import main_window as mw
    db = _base_historique(tmp_path)
    fenetre = mw.MainWindow(db)
    monkeypatch.setattr(mw, "import_csv", lambda p, d: (3, 0, 0, 0, 0, 0))
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: None))
    questions = []
    monkeypatch.setattr(mw.MainWindow, "_demander_recul_depart",
                        lambda self, prop: questions.append(prop) or "rien")
    fenetre._import_files(["releve.csv"])
    assert len(questions) == 1
    assert db.get_setting("initial_date") == "2026-09-11"
    assert _banque(db) == 2000.0


def test_pas_de_proposition_avec_des_archives(tmp_path):
    """Avec une coupure d'archivage, le départ effectif est recalculé à
    partir des archives : on laisse l'utilisateur régler lui-même."""
    db = _base_historique(tmp_path)
    db.insert_tx(_tx("vieux", "2024-01-01", -5.0))
    db.archiver("2024-06-30")
    assert db.proposition_recul_depart() is None
