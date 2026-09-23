"""Solde de départ jamais donné, opérations déjà là (audit du 23/09/2026).

Deux pièges du premier mois :

- La question « Solde de votre compte », posée après le premier relevé,
  acceptait 0 € validé par réflexe (touche Entrée) : le bandeau orange
  disparaissait et le solde restait faux pour toujours. Paramètres, lui,
  demandait déjà confirmation d'un zéro.
- Question refermée sans répondre : le bandeau orange, puis l'invite du
  lancement suivant, renvoyaient vers Paramètres et le 1er janvier. Le solde
  du jour tapé là s'ajoutait au relevé, qu'il contenait déjà. Le bon
  repère est le jour de la dernière opération du relevé : c'est la question
  du premier import, qu'on repose désormais partout.
"""
from comptesbudget.database import Database
from comptesbudget.utils import fmt_date_fr


# Relevé La Banque Postale, total +2 595,36 €. Libellés et montants inventés.
RELEVE = (
    "Date;Libelle;Montant\n"
    "25/08/2026;VIREMENT SALAIRE;2800,00\n"
    "01/09/2026;PRLV LOYER;-150,00\n"
    "12/09/2026;CB SUPERMARCHE;-42,14\n"
    "22/09/2026;CB PHARMACIE;-12,50\n"
)
DERNIERE = "2026-09-22"


def _releve(tmp_path):
    chemin = tmp_path / "releve.csv"
    chemin.write_text(RELEVE, encoding="utf-8")
    return str(chemin)


class _Parametres:
    """Fenêtre Paramètres factice : on retient seulement qu'elle a été
    ouverte, et l'utilisateur la referme."""
    ouvertures = 0

    def __init__(self, *a, **k):
        self.action_avancee = None
        _Parametres.ouvertures += 1

    def exec(self):
        return 0


def _fenetre(tmp_path, monkeypatch, reponses):
    """Fenêtre sur une base neuve. `reponses` : les montants donnés
    successivement à la question du solde (None = boîte refermée)."""
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    from comptesbudget.ui import main_window
    from comptesbudget.ui.main_window import MainWindow
    _Parametres.ouvertures = 0
    monkeypatch.setattr(main_window, "SettingsDialog", _Parametres)
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: None))
    chemin = _releve(tmp_path)
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: (chemin, "")))
    questions = []
    file = list(reponses)
    monkeypatch.setattr(
        MainWindow, "_demander_solde_releve",
        lambda self, premiere, derniere, nb:
            questions.append(derniere) or file.pop(0))
    db = Database(str(tmp_path / "neuve.db"))
    return db, MainWindow(db), questions


def _banque(db):
    return db.soldes_compte(db.compte_id, DERNIERE)["banque"]


# ── Point 2 : un zéro validé par réflexe ────────────────────────────

def test_zero_demande_confirmation_et_peut_etre_refuse(qapp, tmp_path,
                                                      monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    db, fenetre, _ = _fenetre(tmp_path, monkeypatch, [0.0])
    confirmations = []
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: confirmations.append(a) or QMessageBox.No))
    assert fenetre.action_premier_releve() is True
    assert len(confirmations) == 1
    # Refusé : rien n'est enregistré, le bandeau orange reste là.
    assert db.get_setting("initial_balance") == ""
    fenetre.refresh_all()
    assert not fenetre.bilan_view.solde_depart_alert.isHidden()


def test_zero_confirme_est_enregistre(qapp, tmp_path, monkeypatch):
    """Un compte réellement à zéro ce jour-là reste possible."""
    from PySide6.QtWidgets import QMessageBox
    db, fenetre, _ = _fenetre(tmp_path, monkeypatch, [0.0])
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.Yes))
    fenetre.action_premier_releve()
    assert _banque(db) == 0.0
    fenetre.refresh_all()
    assert fenetre.bilan_view.solde_depart_alert.isHidden()


def test_solde_non_nul_sans_confirmation(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    db, fenetre, _ = _fenetre(tmp_path, monkeypatch, [1234.56])
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: 1 / 0))   # jamais posée
    fenetre.action_premier_releve()
    assert _banque(db) == 1234.56


# ── Point 3 : question refermée, le bandeau et le lancement suivant ─

def test_bandeau_indique_le_jour_de_la_derniere_operation(qapp, tmp_path,
                                                         monkeypatch):
    db, fenetre, _ = _fenetre(tmp_path, monkeypatch, [None])
    fenetre.action_premier_releve()
    fenetre.refresh_all()
    texte = fenetre.bilan_view.solde_depart_alert.text()
    assert fmt_date_fr(DERNIERE) in texte
    # Plus de renvoi vers le 1er janvier, qui donnait un solde faux.
    assert fmt_date_fr(db.date_initiale()) not in texte


def test_lien_du_bandeau_pose_la_question_du_releve(qapp, tmp_path,
                                                   monkeypatch):
    db, fenetre, questions = _fenetre(tmp_path, monkeypatch,
                                      [None, 1234.56])
    fenetre.action_premier_releve()
    fenetre.bilan_view.goto_parametres.emit()
    assert questions == [DERNIERE, DERNIERE]
    assert _Parametres.ouvertures == 0
    assert _banque(db) == 1234.56


def test_lancement_suivant_pose_la_question_du_releve(qapp, tmp_path,
                                                     monkeypatch):
    db, fenetre, questions = _fenetre(tmp_path, monkeypatch,
                                      [None, 1234.56])
    fenetre.action_premier_releve()
    assert fenetre._maybe_prompt_initial_setup() is True
    assert questions == [DERNIERE, DERNIERE]
    assert _Parametres.ouvertures == 0
    assert _banque(db) == 1234.56


def test_import_ordinaire_sans_solde_pose_la_question(qapp, tmp_path,
                                                     monkeypatch):
    """« Démarrer à neuf », Paramètres refermé, puis « Importer un relevé »
    du menu : la question vient aussi, une seule fois."""
    db, fenetre, questions = _fenetre(tmp_path, monkeypatch, [1234.56])
    fenetre._import_files([_releve(tmp_path)])
    assert questions == [DERNIERE]
    assert _banque(db) == 1234.56


def test_compte_vide_ouvre_toujours_parametres(qapp, tmp_path, monkeypatch):
    """Sans opération, rien à demander sur un relevé : Paramètres s'ouvre,
    avec la date du jour (cf. test_depart_sans_operation.py)."""
    db, fenetre, questions = _fenetre(tmp_path, monkeypatch, [])
    fenetre.bilan_view.goto_parametres.emit()
    assert _Parametres.ouvertures == 1
    assert questions == []
