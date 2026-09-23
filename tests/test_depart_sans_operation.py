"""Compte neuf : Paramètres propose la date du jour, pas le 1er janvier.

Le piège (audit du 23/09/2026) : le nouvel utilisateur clique « Démarrer à
neuf ». Paramètres s'ouvre avec la date de départ du 1er janvier ; il y tape
le solde qu'il lit aujourd'hui sur le site de sa banque, puis importe son
relevé d'août. Toutes les opérations tombent APRÈS le 1er janvier : elles
s'ajoutent au solde du jour, qui les contenait déjà. Le Bilan affichait
3 800,00 € au lieu de 1 234,56 €, sans le moindre bandeau.

Tant que le compte n'a ni opération ni solde de départ, Paramètres propose
donc la date du jour. Le relevé importé ensuite tombe avant cette date, et
le rattrapage existant (« Reculer la date », cf. test_recul_depart.py)
calcule le bon solde de départ.
"""
from datetime import date, timedelta

from comptesbudget.database import Database


def _jour(ecart: int) -> date:
    return date.today() + timedelta(days=ecart)


def _releve(tmp_path):
    """Relevé des trois dernières semaines, total +2 595,36 €. Les dates
    suivent le jour du test : sinon, passé le 1er janvier suivant, le relevé
    tomberait de lui-même avant la date proposée et le test ne prouverait
    plus rien."""
    lignes = [
        (_jour(-20), "VIREMENT SALAIRE", "2800,00"),
        (_jour(-15), "PRLV LOYER", "-150,00"),
        (_jour(-9), "CB SUPERMARCHE", "-42,14"),
        (_jour(-3), "CB PHARMACIE", "-12,50"),
    ]
    texte = "Date;Libelle;Montant\n" + "".join(
        f"{d.strftime('%d/%m/%Y')};{lib};{m}\n" for d, lib, m in lignes)
    chemin = tmp_path / "releve.csv"
    chemin.write_text(texte, encoding="utf-8")
    return str(chemin)


class _FauxParametres:
    """Remplace la fenêtre Paramètres : retient la date proposée, et
    l'utilisateur y valide son solde du jour sans toucher à la date."""
    propositions = []
    solde_saisi = 1234.56

    def __init__(self, parent, initial_date, initial_balance, nom_compte,
                 avance=False):
        self.action_avancee = None
        self._date = initial_date
        _FauxParametres.propositions.append(initial_date)

    def exec(self):
        from PySide6.QtWidgets import QDialog
        return QDialog.Accepted

    def values(self):
        return self._date, _FauxParametres.solde_saisi


def _fenetre(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from comptesbudget.ui import main_window
    _FauxParametres.propositions = []
    monkeypatch.setattr(main_window, "SettingsDialog", _FauxParametres)
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: None))
    db = Database(str(tmp_path / "neuve.db"))
    return db, main_window.MainWindow(db)


def test_parametres_propose_aujourdhui_sur_un_compte_neuf(qapp, tmp_path,
                                                         monkeypatch):
    db, fenetre = _fenetre(tmp_path, monkeypatch)
    fenetre.action_settings()
    assert _FauxParametres.propositions == [date.today().isoformat()]
    assert db.get_setting("initial_date") == date.today().isoformat()


def test_solde_du_jour_puis_releve_donne_le_bon_solde(qapp, tmp_path,
                                                     monkeypatch):
    """Le parcours complet de l'audit : « Démarrer à neuf », solde du jour
    dans Paramètres, import, « Reculer la date »."""
    from comptesbudget.ui.main_window import MainWindow
    db, fenetre = _fenetre(tmp_path, monkeypatch)
    monkeypatch.setattr(MainWindow, "_demander_recul_depart",
                        lambda self, prop: "reculer")

    fenetre.action_settings()
    fenetre._import_files([_releve(tmp_path)])

    aujourdhui = date.today().isoformat()
    assert db.soldes_compte(db.compte_id, aujourdhui)["banque"] == 1234.56
    assert db.get_setting("initial_date") == _jour(-20).isoformat()


def test_compte_deja_regle_garde_sa_date(qapp, tmp_path, monkeypatch):
    """Un solde déjà saisi n'est jamais déplacé : Paramètres montre la date
    enregistrée, même si le compte n'a pas encore d'opération."""
    db, fenetre = _fenetre(tmp_path, monkeypatch)
    db.set_setting("initial_balance", "500")
    db.set_setting("initial_date", "2026-03-01")
    fenetre.action_settings()
    assert _FauxParametres.propositions == ["2026-03-01"]


def test_compte_avec_operations_garde_sa_date(qapp, tmp_path, monkeypatch):
    """Des opérations déjà là (relevé importé, solde jamais donné) : ce
    n'est plus le cas du compte neuf, la date n'est pas remplacée ici."""
    db, fenetre = _fenetre(tmp_path, monkeypatch)
    depart = db.get_setting("initial_date")
    fenetre._import_files([_releve(tmp_path)])
    fenetre.action_settings()
    assert _FauxParametres.propositions == [depart]
