"""Une fenêtre ne survit pas à son test, ni ses appels programmés.

Le 30/09/2026, la suite de tests s'est bloquée : un test faisait tourner la
boucle d'événements, et réveillait les invites de premier lancement que les
fenêtres principales d'AUTRES tests avaient programmées
(QTimer.singleShot sans fenêtre de rattachement) ; une boîte modale attendait
un clic. Charte des applis : « QTimer.singleShot(délai, fenêtre, fonction) :
passer la fenêtre en 2e argument », et « un test qui ouvre une fenêtre doit la
détruire ».

Les deux tests de ce fichier s'enchaînent dans cet ordre.
"""
from PySide6.QtCore import QCoreApplication, QEvent

from comptesbudget.database import Database


def test_invite_de_premier_lancement_meurt_avec_la_fenetre(qapp, tmp_path,
                                                           monkeypatch):
    from comptesbudget.ui.main_window import MainWindow
    appels = []
    monkeypatch.setattr(MainWindow, "_premier_lancement",
                        lambda self: appels.append("invite"))
    fenetre = MainWindow(Database(str(tmp_path / "invite.db")))
    fenetre.close()
    fenetre.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    qapp.processEvents()
    assert appels == [], "l'invite s'est déclenchée après la fin de sa fenêtre"


def test_invite_de_premier_lancement_toujours_posee(qapp, tmp_path, monkeypatch):
    """Tant que la fenêtre vit, l'invite se déclenche bien, au premier tour
    de la boucle d'événements."""
    from comptesbudget.ui.main_window import MainWindow
    appels = []
    monkeypatch.setattr(MainWindow, "_premier_lancement",
                        lambda self: appels.append("invite"))
    fenetre = MainWindow(Database(str(tmp_path / "vivante.db")))
    qapp.processEvents()
    assert appels == ["invite"]
    assert fenetre is not None


def test_une_fenetre_laissee_ouverte(qapp, tmp_path, monkeypatch):
    """Ouvre une fenêtre principale sans la fermer : le ménage d'après-test
    (conftest) doit la détruire."""
    from comptesbudget.ui.main_window import MainWindow
    monkeypatch.setattr(MainWindow, "_premier_lancement", lambda self: None)
    MainWindow(Database(str(tmp_path / "oubliee.db")))


def test_aucune_fenetre_ne_survit_au_test_precedent(qapp):
    from comptesbudget.ui.main_window import MainWindow
    survivantes = [w for w in qapp.topLevelWidgets() if isinstance(w, MainWindow)]
    assert not survivantes, f"{len(survivantes)} fenêtre(s) principale(s) encore en vie"
