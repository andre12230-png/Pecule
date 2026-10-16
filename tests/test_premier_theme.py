"""Choix Clair / Sombre au tout premier lancement (demande de l'auteur,
16/10/2026, comme dans les deux autres applications).

Le mode sombre ne se trouvait que dans Paramètres › Apparence : un nouvel
utilisateur ne savait pas qu'il existait. Au premier lancement, avant
d'ouvrir la fenêtre, Pécule demande maintenant « Clair ou Sombre ? ».
Jamais à quelqu'un qui a déjà un comptes.db (mise à jour) ni qui a déjà
choisi.
"""
import inspect

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMessageBox

from comptesbudget import premier_theme, theme


def _reglages(tmp_path):
    """Des préférences jetables, jamais le registre de l'utilisateur."""
    return QSettings(str(tmp_path / "prefs.ini"), QSettings.IniFormat)


def test_sans_base_et_sans_choix_c_est_un_premier_lancement(tmp_path):
    assert premier_theme.est_premier_lancement(
        _reglages(tmp_path), str(tmp_path / "comptes.db"))


def test_deja_une_base_on_ne_demande_rien(tmp_path):
    """Une mise à jour : l'utilisateur a déjà ses comptes."""
    base = tmp_path / "comptes.db"
    base.write_bytes(b"")
    assert not premier_theme.est_premier_lancement(_reglages(tmp_path),
                                                   str(base))


def test_theme_deja_choisi_on_ne_demande_rien(tmp_path):
    reglages = _reglages(tmp_path)
    theme.enregistrer_theme("clair", reglages)
    assert not premier_theme.est_premier_lancement(
        reglages, str(tmp_path / "comptes.db"))


def test_preference_abimee_traitee_comme_absente(tmp_path):
    reglages = _reglages(tmp_path)
    reglages.setValue(theme.CLE_THEME, ["clair", "sombre"])
    assert premier_theme.est_premier_lancement(
        reglages, str(tmp_path / "comptes.db"))


def test_le_choix_sombre_est_retenu(tmp_path):
    reglages = _reglages(tmp_path)
    nom = premier_theme.demander_au_premier_lancement(
        reglages, str(tmp_path / "comptes.db"), demander=lambda: "sombre")
    assert nom == "sombre"
    assert theme.lire_theme(reglages) == "sombre"


def test_le_choix_est_retenu_pour_ne_plus_redemander(tmp_path):
    reglages, base = _reglages(tmp_path), str(tmp_path / "comptes.db")
    premier_theme.demander_au_premier_lancement(
        reglages, base, demander=lambda: "clair")
    assert not premier_theme.est_premier_lancement(reglages, base)


def test_pas_de_question_hors_premier_lancement(tmp_path):
    base = tmp_path / "comptes.db"
    base.write_bytes(b"")

    def demander():
        raise AssertionError("la question n'aurait pas dû être posée")
    assert premier_theme.demander_au_premier_lancement(
        _reglages(tmp_path), str(base), demander=demander) is None


def test_la_boite_propose_clair_et_sombre_clair_par_defaut(qapp):
    boite, clair, sombre = premier_theme.boite_du_choix()
    assert isinstance(boite, QMessageBox)
    assert clair.text() == "Clair"
    assert sombre.text() == "Sombre"
    assert boite.defaultButton() is clair
    assert boite.escapeButton() is clair
    assert "Paramètres › Apparence" in boite.text()


def test_le_demarrage_demande_apres_le_verrou_et_avant_la_base():
    """Pas de question si Pécule est déjà ouvert ; et la réponse est
    connue avant la sauvegarde du jour, qui crée déjà des fichiers, et
    avant la fenêtre."""
    from comptesbudget import app
    source = inspect.getsource(app.main)
    position = source.index("demander_au_premier_lancement")
    assert source.index("verrouiller_instance(") < position
    assert position < source.index("backup_db()")
    assert position < source.index("MainWindow(")
