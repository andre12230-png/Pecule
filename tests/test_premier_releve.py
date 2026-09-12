"""Premier lancement : importer d'abord, donner le solde ensuite (1.37.0).

Jusqu'ici, Pécule demandait le solde de départ AVANT le premier import. Le
nouvel utilisateur y mettait son solde du jour, puis importait un an de
relevé qui tombait tout entier avant la date de départ (cas vécu le
12/09/2026).

Désormais l'accueil propose « Importer mon premier relevé… » : après
l'import, une seule question — le solde du compte à la date de la DERNIÈRE
opération du relevé — et Pécule en déduit la date et le solde de départ.
"""
from comptesbudget.database import Database


# Relevé au format Crédit Agricole (colonnes Débit / Crédit, sans pointage).
# Libellés et montants inventés.
RELEVE_CA = (
    "Date;Libelle;Debit euros;Credit euros\n"
    "15/09/2025;VIREMENT SALAIRE;;1500,00\n"
    "03/03/2026;LOYER;600,00;\n"
    "08/09/2026;ASSURANCE;100,00;\n"
    "10/09/2026;ABONNEMENT;50,00;\n"
)


def _releve(tmp_path):
    chemin = tmp_path / "releve_ca.csv"
    chemin.write_text(RELEVE_CA, encoding="utf-8")
    return str(chemin)


def _tx(id_, date, montant, pointee=1, **kw):
    base = {
        "id": id_, "date": date, "date_valeur": date,
        "libelle": "TEST", "libelle_op": "TEST", "reference": "", "type": "",
        "categorie": "Non classé", "sous_cat": "", "info": "",
        "montant": montant, "pointee": pointee,
    }
    base.update(kw)
    return base


# ── Le calcul ───────────────────────────────────────────────────────

def test_bornes_des_operations(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    assert db.bornes_operations() is None
    db.insert_tx(_tx("a", "2026-03-01", -10.0))
    db.insert_tx(_tx("b", "2025-09-15", 20.0))
    db.insert_tx(_tx("x", "2024-01-01", -5.0, categorie="Transaction exclue"))
    assert db.bornes_operations() == ("2025-09-15", "2026-03-01", 2)


def test_depart_depuis_solde(tmp_path):
    """Le solde donné est celui du jour de la dernière opération : le Bilan
    doit l'afficher à cette date. Un achat carte débité plus tard (débit
    différé) et une opération non pointée n'entrent pas dans ce solde."""
    db = Database(str(tmp_path / "t.db"))
    db.insert_tx(_tx("a", "2026-06-01", 1000.0))
    db.insert_tx(_tx("np", "2026-08-20", -50.0, pointee=0))
    db.insert_tx(_tx("cb", "2026-08-28", -30.0, date_valeur="2026-09-04"))

    depart, solde = db.depart_depuis_solde(500.0, "2026-08-31")
    assert depart == "2026-06-01"
    assert solde == -500.0                      # 500 − 1 000
    assert db.get_setting("initial_date") == "2026-06-01"
    assert db.soldes_compte(db.compte_id, "2026-08-31")["banque"] == 500.0
    # Le 4 septembre, l'achat carte est débité.
    assert db.soldes_compte(db.compte_id, "2026-09-05")["banque"] == 470.0


# ── Le parcours du premier lancement ────────────────────────────────

def _fenetre_vide(tmp_path, monkeypatch, solde):
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    from comptesbudget.ui.main_window import MainWindow
    db = Database(str(tmp_path / "neuve.db"))
    fenetre = MainWindow(db)
    chemin = _releve(tmp_path)
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: (chemin, "")))
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: None))
    questions = []
    monkeypatch.setattr(
        MainWindow, "_demander_solde_releve",
        lambda self, premiere, derniere, nb:
            questions.append((premiere, derniere, nb)) or solde)
    return db, fenetre, questions


def test_premier_releve_regle_le_depart(qapp, tmp_path, monkeypatch):
    db, fenetre, questions = _fenetre_vide(tmp_path, monkeypatch, 2000.0)
    assert fenetre.action_premier_releve() is True

    # La question porte sur la date de la dernière opération du relevé.
    assert questions == [("2025-09-15", "2026-09-10", 4)]
    assert db.get_setting("initial_date") == "2025-09-15"
    # 2 000 − (1 500 − 600 − 100 − 50)
    assert db.get_setting("initial_balance") == "1250"
    assert db.soldes_compte(db.compte_id, "2026-09-10")["banque"] == 2000.0
    # Plus aucun des deux bandeaux orange.
    fenetre.refresh_all()
    assert fenetre.bilan_view.hors_solde_alert.isHidden()
    assert fenetre.bilan_view.solde_depart_alert.isHidden()


def test_premier_releve_solde_refuse(qapp, tmp_path, monkeypatch):
    """Question refermée sans répondre : les opérations sont là, le solde
    reste « non renseigné » et son bandeau le rappelle."""
    db, fenetre, _ = _fenetre_vide(tmp_path, monkeypatch, None)
    assert fenetre.action_premier_releve() is True
    assert len(db.list_tx()) == 4
    assert db.get_setting("initial_balance") == ""
    fenetre.refresh_all()
    assert not fenetre.bilan_view.solde_depart_alert.isHidden()


def test_premier_releve_aucun_fichier(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    db, fenetre, questions = _fenetre_vide(tmp_path, monkeypatch, 100.0)
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: ("", "")))
    assert fenetre.action_premier_releve() is False
    assert questions == []


def test_periode_attend_les_premieres_operations(qapp):
    """Base vide au lancement : la barre de période ne peut pas se placer
    sur le mois en cours (il n'a rien) et prend « Toutes périodes ». Au
    premier import, elle doit alors rejoindre le mois en cours — elle
    restait sur « Toutes périodes » (constaté le 12/09/2026)."""
    from datetime import date
    from comptesbudget.ui.widgets import PeriodBar
    barre = PeriodBar()
    barre.update_periods([])
    assert barre.current_period() == "all"
    jour = date.today().isoformat()
    barre.update_periods([_tx("a", jour, -10.0)])
    assert barre.current_period() == date.today().strftime("%Y-%m")
    # Ensuite, le choix de l'utilisateur est respecté : plus de saut.
    barre._appliquer("all")
    barre.update_periods([_tx("a", jour, -10.0), _tx("b", jour, -5.0)])
    assert barre.current_period() == "all"


def test_accueil_propose_d_importer(qapp, tmp_path, monkeypatch):
    """La fenêtre d'accueil d'une base vide offre le nouveau bouton."""
    from PySide6.QtWidgets import QMessageBox
    from comptesbudget.ui.main_window import MainWindow
    fenetre = MainWindow(Database(str(tmp_path / "vide.db")))
    textes = []

    def _exec(self):
        textes.extend(b.text() for b in self.buttons())
        return 0
    monkeypatch.setattr(QMessageBox, "exec", _exec)
    assert fenetre._maybe_prompt_reprise_donnees() is False
    assert "Importer mon premier relevé…" in textes
