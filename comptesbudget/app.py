"""Point d'entrée de l'application."""
import os
import sqlite3
import sys

from PySide6.QtCore import QLibraryInfo, QLockFile, Qt, QTranslator, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QPalette, QPen
from PySide6.QtWidgets import (
    QApplication, QMessageBox, QProxyStyle, QStyle, QStyleFactory, QToolTip,
)

from .erreurs import erreur_en_clair
from .utils import (_app_dir, _data_dir, backup_db, BaseAbimee,
                    SauvegardeImpossible)
from .database import Database
from .labels import charger_alias
from . import premier_theme
from .constants import DB_PATH
from .theme import CLAIR, SOMBRE, T, choisir_theme, lire_theme
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


# ──────────────── Thème clair ou sombre, jamais celui de Windows ───────────
# Pécule s'affiche dans le thème choisi dans ⚙️ Paramètres (clair par
# défaut), quel que soit le réglage de Windows : c'est un choix, pas un oubli.
# Attention au piège corrigé le 16/09/2026 : la palette était construite à
# partir de celle du système (`app.palette()`), et l'on n'y remplaçait que les
# FONDS. Sur un poste réglé en « mode sombre », Qt fournit une palette dont les
# TEXTES sont blancs : ceux-ci se retrouvaient sur le fond crème imposé ici,
# donc invisibles — la boîte « Bienvenue dans Pécule » apparaissait vide.
# La palette est désormais construite entièrement, textes compris, sans rien
# emprunter au système. Ses couleurs viennent de comptesbudget/theme.py.

# Gardé pour les tests qui le vérifient sur le crème.
_GRIS_PALE = CLAIR["texte_discret"]

# Reliefs que Fusion dessine avec Light, Mid, Dark… (cadres, onglets,
# séparateurs). Laissés à leur valeur par défaut — claire —, ils
# formaient des traits blancs sur le fond sombre. Le clair garde les
# valeurs de Qt, inchangées depuis toujours.
_RELIEFS_SOMBRES = {
    QPalette.Light: "#45443E",
    QPalette.Midlight: "#3A3934",
    QPalette.Mid: "#2E2D29",
    QPalette.Dark: "#141310",
    QPalette.Shadow: "#0A0A08",
}


def palette_pour(t: dict) -> QPalette:
    """La palette Qt d'un thème, construite de zéro — fonds ET textes.

    Ne prend rien à la palette du système : c'est ce qui garantit la même
    apparence sur un poste réglé en clair et sur un poste réglé en sombre."""
    pal = QPalette()
    for role, cle in (
            (QPalette.Window, "fond_page"), (QPalette.WindowText, "texte"),
            (QPalette.Base, "saisie"), (QPalette.Text, "texte"),
            (QPalette.AlternateBase, "ligne_paire"),
            (QPalette.Button, "bouton_qt"), (QPalette.ButtonText, "texte"),
            (QPalette.ToolTipBase, "bulle_fond"),
            (QPalette.ToolTipText, "bulle_texte"),
            (QPalette.Highlight, "selection"),
            (QPalette.HighlightedText, "texte_selection"),
            (QPalette.PlaceholderText, "texte_discret"),
            (QPalette.BrightText, "texte_selection"),
            (QPalette.Link, "lien"), (QPalette.LinkVisited, "lien_vu")):
        pal.setColor(role, QColor(t[cle]))
    # Ce qui est désactivé s'efface, sans disparaître pour autant.
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, QColor(t["texte_desactive"]))
    if t is SOMBRE:
        for role, couleur in _RELIEFS_SOMBRES.items():
            pal.setColor(role, QColor(couleur))
    return pal


def palette_claire() -> QPalette:
    """La palette du thème clair, celui de référence."""
    return palette_pour(CLAIR)


def palette_sombre() -> QPalette:
    """La palette du thème sombre (charte commune du 12/10/2026)."""
    return palette_pour(SOMBRE)


class StyleClair(QProxyStyle):
    """Le style « Fusion », plus un contour lisible aux cases à cocher et aux
    boutons radio.

    Avec la palette claire, Fusion ne leur donnait qu'un contour pâle : une
    case décochée disparaissait dans les listes des assistants. La charte
    veut 3 pour 1 pour ce qu'on clique : contour T["contour"] (relecture
    du 30/09/2026), éclairci en thème sombre."""

    def __init__(self):
        super().__init__(QStyleFactory.create("Fusion"))

    @staticmethod
    def contour() -> QColor:
        """Le contour du thème de la session, lu au moment de dessiner."""
        return QColor(T["contour"])

    def drawPrimitive(self, element, option, painter, widget=None):
        super().drawPrimitive(element, option, painter, widget)
        if element in (QStyle.PE_IndicatorCheckBox,
                       QStyle.PE_IndicatorItemViewItemCheck,
                       QStyle.PE_IndicatorRadioButton):
            painter.save()
            painter.setRenderHint(painter.RenderHint.Antialiasing,
                                  element == QStyle.PE_IndicatorRadioButton)
            painter.setPen(QPen(self.contour(), 1))
            painter.setBrush(Qt.NoBrush)
            cadre = option.rect.adjusted(0, 0, -1, -1)
            if element == QStyle.PE_IndicatorRadioButton:
                painter.drawEllipse(cadre)
            else:
                painter.drawRect(cadre)
            painter.restore()


def _poser_palette(app: QApplication, palette: QPalette) -> None:
    """Style Fusion et palette complète, infobulles comprises.

    Le style « Fusion » est indispensable : les styles natifs de Windows
    peignent certains textes eux-mêmes, sans consulter la palette. Il est
    posé à travers StyleClair, qui ajoute un contour lisible aux cases."""
    app.setStyle(StyleClair())
    app.setPalette(palette)
    # Les infobulles ont leur palette à elles, prise au système, que
    # setPalette() ne touche pas : chez l'auteur, fond #3C3C3C et texte
    # #D4D4D4 au lieu du jaune pâle et du noir de la charte (01/10/2026,
    # tests/test_infobulles.py).
    QToolTip.setPalette(palette)


def appliquer_theme(app: QApplication) -> None:
    """Impose à l'application le thème de la session (voir theme.py)."""
    _poser_palette(app, palette_pour(T))


def appliquer_theme_clair(app: QApplication) -> None:
    """Impose à l'application son apparence claire, celle de référence."""
    _poser_palette(app, palette_claire())


def message_base_abimee(dossier: str) -> str:
    """Ce que dit Pécule quand sa base ne se lit pas (audit du 08/10/2026 :
    l'appli s'arrêtait sur un message technique en anglais)."""
    sauvegardes = os.path.join(dossier, "sauvegardes")
    return (
        "Le fichier de vos comptes (comptes.db) est abîmé : Pécule ne peut "
        "pas l'ouvrir. Rien n'a été modifié.\n\n"
        "Vos sauvegardes automatiques, une par jour, sont dans :\n"
        f"{sauvegardes}\n\n"
        "Pour revenir à la plus récente : fermez ce message, copiez le "
        "dernier fichier « comptes-AAAA-MM-JJ.db » dans le dossier\n"
        f"{dossier},\n"
        "puis renommez-le « comptes.db » (gardez l'ancien sous un autre nom, "
        "au cas où) et relancez Pécule.")


def _prevenir_base_abimee() -> None:
    """Le message, avec un bouton qui ouvre le dossier des sauvegardes."""
    dossier = _data_dir()
    boite = QMessageBox(QMessageBox.Critical, "Comptes illisibles",
                        message_base_abimee(dossier))
    ouvrir = boite.addButton("Ouvrir le dossier des sauvegardes",
                             QMessageBox.ActionRole)
    boite.addButton("Fermer", QMessageBox.RejectRole)
    boite.exec()
    if boite.clickedButton() is ouvrir:
        QDesktopServices.openUrl(QUrl.fromLocalFile(
            os.path.join(dossier, "sauvegardes")))


def _ouvrir_base():
    """La base, ou None après avoir prévenu si elle est abîmée."""
    try:
        return Database()
    except sqlite3.DatabaseError:
        _prevenir_base_abimee()
        return None


def main():
    # Le thème se lit avant tout le reste : la première boîte de message
    # (verrou, sauvegarde) doit déjà avoir les bonnes couleurs.
    choisir_theme(lire_theme())
    app = QApplication(sys.argv)
    appliquer_theme(app)
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

    # Tout premier lancement : demander Clair ou Sombre (16/10/2026, voir
    # premier_theme.py). Après le verrou (pas de question si Pécule est déjà
    # ouvert), avant la sauvegarde du jour et la fenêtre.
    nom = premier_theme.demander_au_premier_lancement(None, DB_PATH)
    if nom:
        choisir_theme(nom)
        appliquer_theme(app)

    # Sauvegarde quotidienne AVANT d'ouvrir la base. Un échec ne bloque pas
    # l'ouverture, mais il se dit : il passait inaperçu, et l'on croyait
    # avoir une copie de la veille (audit du 23/09/2026).
    try:
        bak = backup_db()
    except BaseAbimee:
        _prevenir_base_abimee()
        return
    except SauvegardeImpossible as e:
        bak = None
        QMessageBox.warning(
            None, "Sauvegarde automatique",
            "La copie de sécurité du jour n'a pas pu être faite :\n"
            f"{erreur_en_clair(e)}\n\n"
            "Pécule s'ouvre quand même, mais vos données ne sont pas "
            "sauvegardées aujourd'hui. Vérifiez la place libre sur le disque, "
            "ou faites une « 💾 Sauvegarde externe » depuis le menu de gauche.")

    db = _ouvrir_base()
    if db is None:
        return
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
