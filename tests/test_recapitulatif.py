"""Tests du récapitulatif « Tous les comptes ».

Une exigence tient tout le reste : un compte doit afficher dans le
récapitulatif EXACTEMENT le solde de son Bilan. Deux chiffres différents pour
un même compte, et l'on ne sait plus lequel croire.
"""
from datetime import date, timedelta

import pytest

from comptesbudget.database import Database


def _tx(id_, montant, jour, pointee=1, **kw):
    base = {
        "id": id_, "date": jour, "date_valeur": jour,
        "libelle": "OP", "libelle_op": "OP", "reference": "", "type": "",
        "categorie": "Non classé", "sous_cat": "", "info": "",
        "montant": montant, "pointee": pointee,
    }
    base.update(kw)
    return base


@pytest.fixture
def db(tmp_path):
    """Deux comptes : un courant bien garni et un livret."""
    d = Database(str(tmp_path / "recap.db"))
    d.set_solde_initial(1000.0, "2026-01-01")
    courant = d.compte_id
    d.insert_tx(_tx("c1", -200.0, "2026-02-10"))                 # pointée
    d.insert_tx(_tx("c2", 1500.0, "2026-03-01"))                 # pointée
    d.insert_tx(_tx("c3", -80.0, "2026-03-05", pointee=0))       # en attente
    d.insert_tx(_tx("c4", -999.0, "2026-03-06",                  # exclue
                    categorie="Transaction exclue"))
    d.insert_tx(_tx("c5", -50.0, "2025-12-20"))                  # avant départ
    d.insert_tx(_tx("c6", -40.0, "2099-01-01", pointee=0))       # à venir
    # Achat carte à débit différé : passé, mais débité dans le futur.
    d.insert_tx(_tx("c7", -30.0, "2026-03-07", date_valeur="2099-02-04"))

    livret = d.add_compte("Livret", 500.0, "2026-01-01")
    d.insert_tx(_tx("l1", 100.0, "2026-02-01", compte_id=livret))
    d.insert_tx(_tx("l2", -700.0, "2026-02-02", compte_id=livret))

    d.set_compte_courant(courant)
    d._ids = {"courant": courant, "livret": livret}
    return d


def test_soldes_suivent_les_regles_du_bilan(db):
    s = db.soldes_compte(db._ids["courant"], "2026-09-11")
    # 1000 − 200 + 1500 : l'exclue, l'opération d'avant la date de départ,
    # l'opération à venir et l'achat carte pas encore débité ne comptent pas.
    assert s["banque"] == 2300.0
    assert s["attente"] == -80.0
    assert s["nb_attente"] == 1
    assert s["comptable"] == 2220.0
    assert s["derniere_pointee"] == "2026-03-01"

    livret = db.soldes_compte(db._ids["livret"], "2026-09-11")
    assert livret["banque"] == -100.0
    assert livret["comptable"] == -100.0
    assert livret["nb_attente"] == 0


def test_soldes_ne_changent_pas_le_compte_affiche(db):
    avant = db.compte_id
    db.soldes_compte(db._ids["livret"], "2026-09-11")
    assert db.compte_id == avant


def test_archiver_ne_change_pas_le_solde(tmp_path):
    # Base à part : sans opération antérieure à la date de départ, dont
    # l'archivage déplace le solde — dans le Bilan comme ici (voir JOURNAL,
    # 11/09/2026).
    d = Database(str(tmp_path / "archives.db"))
    d.set_solde_initial(1000.0, "2026-01-01")
    d.insert_tx(_tx("a", -200.0, "2026-02-10"))
    d.insert_tx(_tx("b", 1500.0, "2026-03-01"))
    d.insert_tx(_tx("c", -80.0, "2026-02-15", pointee=0))
    avant = d.soldes_compte(d.compte_id, "2026-09-11")
    d.archiver("2026-02-28", d.compte_id)
    apres = d.soldes_compte(d.compte_id, "2026-09-11")
    assert apres["banque"] == avant["banque"] == 2300.0
    # Une non pointée archivée sort du solde comptable, comme du Bilan :
    # l'archive ne garde que ce que la banque a vraiment passé.
    assert apres["comptable"] == 2300.0


def test_recap_egal_au_bilan_de_chaque_compte(qapp, tmp_path):
    """Le chiffre « En banque » de chaque compte = le KPI du Bilan, avec des
    dates relatives à aujourd'hui (le Bilan se cale sur la vraie date)."""
    from comptesbudget.ui.views.bilan import BilanView
    from comptesbudget.utils import fmt_euro

    d = Database(str(tmp_path / "bilan.db"))
    auj = date.today()
    j = lambda n: (auj - timedelta(days=n)).isoformat()
    d.set_solde_initial(250.0, j(100))
    courant = d.compte_id
    d.insert_tx(_tx("a", -40.0, j(30)))
    d.insert_tx(_tx("b", 900.0, j(20)))
    d.insert_tx(_tx("c", -15.0, j(5), pointee=0))
    livret = d.add_compte("Livret", 3000.0, j(100))
    d.insert_tx(_tx("d", -120.0, j(10), compte_id=livret))
    d.archiver(j(25), livret)      # une archive, pour corser

    vue = BilanView(d)
    for cid in (courant, livret):
        d.set_compte_courant(cid)
        vue.refresh()
        s = d.soldes_compte(cid, auj.isoformat())
        assert vue.kpis["solde"]._value.text() == fmt_euro(s["banque"])


def test_dialogue_une_ligne_par_compte_et_un_total(qapp, db):
    from comptesbudget.ui.recapitulatif import RecapComptesDialog
    from comptesbudget.utils import fmt_euro

    dlg = RecapComptesDialog(db, aujourdhui="2026-09-11")
    t = dlg.table
    assert t.rowCount() == 3                      # 2 comptes + total
    assert t.item(2, 0).text() == "Total"
    assert t.item(2, 1).text() == fmt_euro(2300.0 - 100.0)
    assert t.item(2, 3).text() == fmt_euro(2220.0 - 100.0)

    # Double-clic sur le livret : c'est lui qu'il faudra afficher.
    ligne_livret = next(l for l in range(2)
                        if t.item(l, 0).text().startswith("Livret"))
    dlg._afficher_ligne(ligne_livret)
    assert dlg.compte_choisi == db._ids["livret"]


def test_double_clic_sur_le_total_ne_fait_rien(qapp, db):
    from comptesbudget.ui.recapitulatif import RecapComptesDialog

    dlg = RecapComptesDialog(db, aujourdhui="2026-09-11")
    dlg._afficher_ligne(2)
    assert dlg.compte_choisi is None


def test_bouton_visible_seulement_avec_plusieurs_comptes(qapp, tmp_path):
    from comptesbudget.ui.main_window import MainWindow

    d = Database(str(tmp_path / "un.db"))
    d.set_solde_initial(0.0, "2026-01-01")        # pas d'invite au lancement
    fenetre = MainWindow(d)
    assert fenetre.btn_recap.isHidden()

    d.add_compte("Livret", 0.0, "2026-01-01")
    fenetre.refresh_all()
    assert not fenetre.btn_recap.isHidden()
    fenetre.close()
