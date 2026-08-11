"""Point d'entrée de l'application."""
import os
import sys

from PySide6.QtGui import QColor, QIcon, QPalette
from PySide6.QtWidgets import QApplication

from .utils import _app_dir, backup_db
from .database import Database
from .labels import charger_alias
from .ui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

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
