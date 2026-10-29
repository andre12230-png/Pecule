"""Préparation de la version Linux de Pécule (29/10/2026).

Pécule tourne sous Windows ; ces tests vérifient, depuis Windows, ce qui doit
se comporter autrement sous Linux, en faisant croire au code qu'il y tourne
(sys.platform = "linux"). Rien ne change pour Windows : chaque test vérifie
aussi le comportement Windows d'origine.

    py -m pytest tests/test_linux.py
"""
from __future__ import annotations

import errno
import os
import sys

from comptesbudget import constants
from comptesbudget.erreurs import erreur_en_clair


# --- Dossier des données ---------------------------------------------------

def _sans_base_portable(monkeypatch, tmp_path):
    """Programme rangé dans un dossier vide : pas de comptes.db « portable »
    à côté de lui, donc les données vont dans le dossier de l'utilisateur."""
    programme = tmp_path / "programme"
    programme.mkdir()
    monkeypatch.setattr(constants, "_app_dir", lambda: str(programme))


def test_linux_donnees_dans_le_dossier_habituel(monkeypatch, tmp_path):
    """Sous Linux, l'endroit habituel est ~/.local/share (ou $XDG_DATA_HOME),
    pas un dossier « Pecule » posé au milieu du dossier personnel."""
    _sans_base_portable(monkeypatch, tmp_path)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
    assert constants._data_dir() == os.path.join(str(tmp_path / "share"),
                                                 "Pecule")


def test_linux_sans_xdg_data_home(monkeypatch, tmp_path):
    _sans_base_portable(monkeypatch, tmp_path)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setattr(os.path, "expanduser",
                        lambda p: p.replace("~", str(tmp_path / "maison")))
    attendu = os.path.join(str(tmp_path / "maison"), ".local", "share",
                           "Pecule")
    assert constants._data_dir() == attendu


def test_windows_inchange(monkeypatch, tmp_path):
    """Sous Windows, toujours %LOCALAPPDATA%\\Pecule : les bases existantes
    restent trouvées."""
    _sans_base_portable(monkeypatch, tmp_path)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    assert constants._data_dir() == os.path.join(str(tmp_path / "local"),
                                                 "Pecule")


# --- Noms de fichiers dans les messages d'erreur ---------------------------

def test_nom_de_fichier_a_la_linux():
    texte = erreur_en_clair(FileNotFoundError(
        errno.ENOENT, "No such file or directory", "/home/x/export.xlsx"))
    assert "« export.xlsx » introuvable" in texte


def test_nom_de_fichier_a_la_windows_sous_linux(monkeypatch):
    """Sous Linux, Path("C:\\x\\export.xlsx").name renvoie le chemin entier :
    l'antislash n'y est pas un séparateur. Le message doit quand même ne
    nommer que le fichier."""
    from comptesbudget import erreurs
    assert erreurs._nom_de_fichier(r"C:\x\export.xlsx") == "export.xlsx"
    assert erreurs._nom_de_fichier("/home/x/export.xlsx") == "export.xlsx"


# --- Bouton « Mise à jour » ------------------------------------------------

def test_mise_a_jour_propose_l_appimage_sous_linux(qapp, monkeypatch):
    from comptesbudget.ui.mise_a_jour import MiseAJourDialog
    monkeypatch.setattr(sys, "platform", "linux")
    fenetre = MiseAJourDialog()
    assert "AppImage" in fenetre.btn_installeur.text()
    assert fenetre.adresse_installeur == constants.APPIMAGE_URL
    assert "installeur" not in fenetre.btn_installeur.text()


def test_mise_a_jour_inchangee_sous_windows(qapp, monkeypatch):
    from comptesbudget.ui.mise_a_jour import MiseAJourDialog
    monkeypatch.setattr(sys, "platform", "win32")
    fenetre = MiseAJourDialog()
    assert fenetre.btn_installeur.text() == "⬇ Télécharger l'installeur"
    assert fenetre.adresse_installeur == constants.INSTALLEUR_URL


# --- Montants et dates à la française ---------------------------------------

def test_montants_a_la_francaise_quelle_que_soit_la_langue(qapp):
    """Essai sous Linux du 29/10/2026 : un système réglé en anglais, ou en
    langue « C » (cas de WSL), faisait écrire « 1,850.00 » dans les cases de
    montant. Pécule impose le français au démarrage."""
    from PySide6.QtCore import QLocale
    from comptesbudget.app import imposer_format_francais
    QLocale.setDefault(QLocale(QLocale.English, QLocale.UnitedStates))
    try:
        imposer_format_francais()
        assert QLocale().language() == QLocale.French
        assert QLocale().decimalPoint() == ","
    finally:
        QLocale.setDefault(QLocale(QLocale.French, QLocale.France))
