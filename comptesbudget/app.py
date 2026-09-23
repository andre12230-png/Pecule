"""Point d'entrée de l'application."""
import os
import sys

from PySide6.QtCore import QLibraryInfo, QLockFile, QTranslator
from PySide6.QtGui import QColor, QIcon, QPalette
from PySide6.QtWidgets import QApplication, QMessageBox

from .utils import _app_dir, _data_dir, backup_db, SauvegardeImpossible
from .database import Database
from .labels import charger_alias
from .ui.main_window import MainWindow

def installer_traduction_qt(app) -> bool:
    """Passe en français les boutons et messages fournis par Qt lui-même.

    Les boutons « OK / Cancel » des boîtes de dialogue, les « Yes / No » des
    questions, les intitulés des fenêtres de choix de fichier ne viennent pas
    de notre code : Qt les fabrique. Sans cette traduction, une application
    entièrement française affiche « Cancel » sous le nez de l'utilisateur.

    Qt livre ses propres traductions (`qtbase_fr.qm`). On les charge plutôt que
    de renommer les boutons un par un : cela couvre d'un coup tous les
    dialogues, y compris ceux qu'on n'écrit pas nous-mêmes.

    Le traducteur doit rester référencé aussi longtemps que l'application, d'où
    son rangement sur l'objet `app` : un traducteur ramassé par le garbage
    collector cesse silencieusement de traduire.

    Retourne True si la traduction a été chargée. En cas d'échec (fichier
    absent d'une installation), l'application démarre quand même — en anglais
    pour ces quelques mots, ce qui vaut mieux que de ne pas démarrer.
    """
    chemins = [QLibraryInfo.path(QLibraryInfo.TranslationsPath)]
    # Second recours : le dossier livré avec PySide6. PyInstaller le recopie
    # tel quel dans `_internal/PySide6/translations/` — vérifié dans l'exe —,
    # si bien que ce chemin vaut aussi bien en développement qu'une fois gelé.
    try:
        import PySide6
        chemins.append(os.path.join(os.path.dirname(PySide6.__file__),
                                    "translations"))
    except Exception:
        pass
    chemins.append(os.path.join(_app_dir(), "translations"))
    for dossier in chemins:
        if not dossier or not os.path.isdir(dossier):
            continue
        tr = QTranslator(app)
        if tr.load("qtbase_fr", dossier):
            app.installTranslator(tr)
            app._traducteur_qt = tr          # garde une référence vivante
            return True
    return False


class DossierDonneesInutilisable(OSError):
    """Le verrou n'a pas pu être posé parce que le dossier des données est
    introuvable ou protégé en écriture — et non parce qu'une autre fenêtre
    le tient."""


def verrouiller_instance(dossier: str):
    """Réserve la base pour cette fenêtre. Retourne le verrou, ou None si une
    autre fenêtre l'a déjà. Lève DossierDonneesInutilisable si le dossier ne
    permet pas de poser le verrou : on annonçait alors « déjà ouvert », et
    l'on renvoyait vers une fenêtre qui n'existait pas (audit du 23/09/2026).

    Deux fenêtres ouvertes sur le même fichier se marchent dessus sans rien
    dire : chacune garde en mémoire ce qu'elle a lu, la dernière écriture
    gagne, et un import — une longue transaction — peut échouer sur
    « database is locked ». Rien n'empêchait de lancer l'application deux
    fois, ce qui arrive vite en double-cliquant sur son icône.

    Qt fait le reste du travail : le fichier de verrou porte le numéro du
    processus, et si celui-ci n'existe plus (plantage, coupure de courant),
    le verrou est repris automatiquement au lancement suivant."""
    verrou = QLockFile(os.path.join(dossier, "pecule.lock"))
    # Sur cette machine, c'est le numéro de processus qui tranche : un verrou
    # tenu par une fenêtre ouverte n'est jamais volé, quel que soit son âge
    # (vérifié par un test). Le délai ci-dessous ne sert qu'au cas où Qt ne
    # PEUT pas savoir — un fichier de verrou venu d'un autre ordinateur,
    # recopié avec le dossier lors d'une mise à jour ou depuis une clé USB.
    # Sans lui, un tel fichier interdirait le démarrage pour toujours.
    verrou.setStaleLockTime(30_000)      # 30 s
    if not verrou.tryLock(200):
        if verrou.error() == QLockFile.LockFailedError:
            return None                  # une autre fenêtre le tient
        raise DossierDonneesInutilisable(dossier)
    return verrou


# ──────────────── Thème clair, quel que soit le réglage de Windows ─────────
# Pécule s'affiche TOUJOURS en thème clair : c'est un choix, pas un oubli.
# Attention au piège corrigé le 16/09/2026 : la palette était construite à
# partir de celle du système (`app.palette()`), et l'on n'y remplaçait que les
# FONDS. Sur un poste réglé en « mode sombre », Qt fournit une palette dont les
# TEXTES sont blancs : ceux-ci se retrouvaient sur le fond crème imposé ici,
# donc invisibles — la boîte « Bienvenue dans Pécule » apparaissait vide.
# La palette est désormais construite entièrement, textes compris, sans rien
# emprunter au système.

# Couleurs de l'application. Chaque texte a été vérifié contre son fond :
# au moins 4,5 pour 1 de contraste (cf. tests/test_theme_clair.py).
_CREME       = "#ECE9D8"   # fond des fenêtres
_BLANC       = "#FFFFFF"   # fond des champs et des listes
_LIGNE_PAIRE = "#F5F5F0"   # une ligne sur deux dans les tableaux
_ENCRE       = "#000000"   # tous les textes
_SELECTION   = "#316AC5"   # fond de la ligne sélectionnée
_BULLE       = "#FFFFDC"   # fond des info-bulles
_GRIS_PALE   = "#6B6B6B"   # texte d'invite et libellés désactivés
_LIEN        = "#0B5AA8"
_LIEN_VU     = "#6A3FA0"


def palette_claire() -> QPalette:
    """La palette de Pécule, construite de zéro — fonds ET textes.

    Ne prend rien à la palette du système : c'est ce qui garantit la même
    apparence sur un poste réglé en clair et sur un poste réglé en sombre."""
    pal = QPalette()
    pal.setColor(QPalette.Window,          QColor(_CREME))
    pal.setColor(QPalette.WindowText,      QColor(_ENCRE))
    pal.setColor(QPalette.Base,            QColor(_BLANC))
    pal.setColor(QPalette.Text,            QColor(_ENCRE))
    pal.setColor(QPalette.AlternateBase,   QColor(_LIGNE_PAIRE))
    pal.setColor(QPalette.Button,          QColor(_CREME))
    pal.setColor(QPalette.ButtonText,      QColor(_ENCRE))
    pal.setColor(QPalette.ToolTipBase,     QColor(_BULLE))
    pal.setColor(QPalette.ToolTipText,     QColor(_ENCRE))
    pal.setColor(QPalette.Highlight,       QColor(_SELECTION))
    pal.setColor(QPalette.HighlightedText, QColor(_BLANC))
    pal.setColor(QPalette.PlaceholderText, QColor(_GRIS_PALE))
    pal.setColor(QPalette.BrightText,      QColor(_BLANC))
    pal.setColor(QPalette.Link,            QColor(_LIEN))
    pal.setColor(QPalette.LinkVisited,     QColor(_LIEN_VU))
    # Ce qui est désactivé s'efface, sans disparaître pour autant.
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, QColor(_GRIS_PALE))
    return pal


def appliquer_theme_clair(app: QApplication) -> None:
    """Impose à l'application son apparence claire.

    Le style « Fusion » est indispensable : les styles natifs de Windows
    peignent certains textes eux-mêmes, sans consulter la palette."""
    app.setStyle("Fusion")
    app.setPalette(palette_claire())


def main():
    app = QApplication(sys.argv)
    appliquer_theme_clair(app)
    installer_traduction_qt(app)

    # Icône d'application (visible dans la barre des tâches Windows)
    ico_path = os.path.join(_app_dir(), "Budget.ico")
    if os.path.exists(ico_path):
        app.setWindowIcon(QIcon(ico_path))
        # Sous Windows : associer l'AppUserModelID pour que l'icône
        # de la barre des tâches soit celle de l'app, pas de Python
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "andre.Pecule.1.0")
        except Exception:
            pass

    # Une seule fenêtre à la fois sur une même base (cf. verrouiller_instance).
    try:
        verrou = verrouiller_instance(_data_dir())
    except DossierDonneesInutilisable:
        QMessageBox.critical(
            None, "Pécule ne peut pas démarrer",
            "Pécule ne peut pas écrire dans le dossier de ses données :\n"
            f"{_data_dir()}\n\n"
            "Vérifiez que ce dossier existe et n'est pas en lecture seule "
            "(clé USB protégée, par exemple). Si la Sécurité Windows protège "
            "vos dossiers contre les rançongiciels (« Accès contrôlé aux "
            "dossiers »), autorisez-y Pecule.exe.")
        return
    if verrou is None:
        QMessageBox.warning(
            None, "Pécule est déjà ouvert",
            "Une fenêtre de Pécule utilise déjà vos données.\n\n"
            "Deux fenêtres ouvertes en même temps se contrediraient : "
            "l'une écraserait les saisies de l'autre. Retrouvez la fenêtre "
            "déjà ouverte dans la barre des tâches.")
        return
    app._verrou_instance = verrou    # à garder vivant tant que l'appli tourne

    # Sauvegarde quotidienne AVANT d'ouvrir la base. Un échec ne bloque pas
    # l'ouverture, mais il se dit : il passait inaperçu, et l'on croyait
    # avoir une copie de la veille (audit du 23/09/2026).
    try:
        bak = backup_db()
    except SauvegardeImpossible as e:
        bak = None
        QMessageBox.warning(
            None, "Sauvegarde automatique",
            "La copie de sécurité du jour n'a pas pu être faite :\n"
            f"{e}\n\n"
            "Pécule s'ouvre quand même, mais vos données ne sont pas "
            "sauvegardées aujourd'hui. Vérifiez la place libre sur le disque, "
            "ou faites une « 💾 Sauvegarde externe » depuis le menu de gauche.")

    db = Database()
    # Correspondances de libellés propres à cette base (« raison sociale du
    # relevé » → « enseigne »), utilisées par tout le nettoyage de libellés.
    charger_alias(db.get_alias_libelles())
    w = MainWindow(db)
    if bak:
        w.statusBar().showMessage(
            f"Base : {db.path}   —   💾 Sauvegarde du jour : {bak}")
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
