"""Point d'entrée de l'application."""
import os
import sys

from PySide6.QtCore import QLibraryInfo, QTranslator
from PySide6.QtGui import QColor, QIcon, QPalette
from PySide6.QtWidgets import QApplication

from .utils import _app_dir, backup_db
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


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
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

    # Palette légèrement Windows-like
    pal = app.palette()
    pal.setColor(QPalette.Window,       QColor("#ECE9D8"))
    pal.setColor(QPalette.Base,         QColor("#FFFFFF"))
    pal.setColor(QPalette.AlternateBase, QColor("#F5F5F0"))
    pal.setColor(QPalette.Highlight,    QColor("#316AC5"))
    pal.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(pal)

    # Sauvegarde quotidienne AVANT d'ouvrir la base
    bak = backup_db()

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
