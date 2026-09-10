"""« Votre avis » : le questionnaire en ligne, et l'unique invitation à le
remplir.

Les utilisateurs ne remontent pas d'eux-mêmes ce qui coince : sans compte
GitHub, ils n'avaient aucun moyen de le faire. Le questionnaire n'en demande
aucun. Pécule ne fait que l'ouvrir dans le navigateur ; ce qui est envoyé,
c'est l'utilisateur qui l'écrit et qui l'envoie.
"""

import platform
import sys
from datetime import date

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox,
)

from ..constants import (
    APP_VERSION, FORMULAIRE_AVIS_URL, TICKETS_GITHUB_URL,
    DELAI_INVITATION_AVIS,
)

# Réglages purement locaux. Le préfixe « _meta_ » les tient à l'écart de la
# synchronisation : un réglage ordinaire rajeunit l'horodatage des réglages,
# et ferait alors gagner le solde de départ de CE poste sur celui d'un autre
# lors d'une fusion — pour une simple date d'invitation.
CLE_PREMIERE_UTILISATION = "_meta_avis_premiere_utilisation"
CLE_INVITATION_FAITE = "_meta_avis_invitation"


def description_systeme() -> str:
    """Version de Pécule et de Windows, à coller dans le questionnaire : c'est
    la première chose à savoir pour comprendre un problème."""
    if sys.platform == "win32":
        systeme = f"Windows {platform.release()}"
    else:
        systeme = f"{platform.system()} {platform.release()}"
    return f"Pécule {APP_VERSION} — {systeme}"


def noter_premiere_utilisation(db, aujourdhui: date):
    """Retient le jour du premier lancement (sans l'écraser ensuite). Pour qui
    utilisait déjà Pécule, c'est le jour de la mise à jour : l'invitation
    viendra donc deux semaines après, pas le jour même."""
    if not db.get_setting(CLE_PREMIERE_UTILISATION):
        db.set_setting(CLE_PREMIERE_UTILISATION, aujourdhui.isoformat())


def doit_inviter(db, aujourdhui: date) -> bool:
    """Vrai une seule fois : après deux semaines d'usage, si l'invitation n'a
    jamais été faite et si Pécule contient des opérations — sans elles,
    l'utilisateur n'a pas encore d'avis à donner."""
    if db.get_setting(CLE_INVITATION_FAITE):
        return False
    if db.est_vide():
        return False
    try:
        debut = date.fromisoformat(db.get_setting(CLE_PREMIERE_UTILISATION))
    except ValueError:
        return False
    return (aujourdhui - debut).days >= DELAI_INVITATION_AVIS


def ouvrir_questionnaire():
    """Copie la version dans le presse-papiers, puis ouvre le questionnaire
    dans le navigateur. Renvoie le texte copié."""
    texte = description_systeme()
    QGuiApplication.clipboard().setText(texte)
    QDesktopServices.openUrl(QUrl(FORMULAIRE_AVIS_URL))
    return texte


class AvisDialog(QDialog):
    """Fenêtre ouverte par le bouton « Votre avis » du menu de gauche."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Votre avis sur Pécule")
        self.setMinimumWidth(460)
        v = QVBoxLayout(self)
        v.setSpacing(12)

        intro = QLabel(
            "Un problème à l'installation, une banque dont le relevé ne "
            "s'importe pas, une idée pour faire mieux ? Dites-le : c'est "
            "ainsi que Pécule s'améliore.<br><br>"
            "Le questionnaire s'ouvre dans votre navigateur. Il prend deux "
            "minutes et aucune réponse n'est obligatoire. "
            "<b>N'y indiquez ni numéro de compte ni montant.</b>")
        intro.setTextFormat(Qt.RichText)
        intro.setWordWrap(True)
        v.addWidget(intro)

        version = QLabel(
            f"Votre version : <b>{description_systeme()}</b><br>"
            "<span style='color:#666'>Elle sera copiée pour vous : collez-la "
            "(Ctrl+V) dans la question « Votre version de Pécule ».</span>")
        version.setTextFormat(Qt.RichText)
        version.setWordWrap(True)
        v.addWidget(version)

        # Confirmation affichée une fois le questionnaire ouvert.
        self.confirmation = QLabel("")
        self.confirmation.setStyleSheet("color:#2E7D32")
        self.confirmation.setWordWrap(True)
        self.confirmation.hide()
        v.addWidget(self.confirmation)

        github = QLabel(
            "Vous avez un compte GitHub ? Vous pouvez aussi "
            f"<a href='{TICKETS_GITHUB_URL}'>ouvrir un ticket</a>.")
        github.setTextFormat(Qt.RichText)
        github.setOpenExternalLinks(True)
        github.setStyleSheet("color:#666")
        v.addWidget(github)

        boutons = QHBoxLayout()
        boutons.addStretch()
        self.btn_ouvrir = QPushButton("💬 Ouvrir le questionnaire")
        self.btn_ouvrir.setDefault(True)
        self.btn_ouvrir.clicked.connect(self.on_ouvrir)
        boutons.addWidget(self.btn_ouvrir)
        fermer = QPushButton("Fermer")
        fermer.clicked.connect(self.accept)
        boutons.addWidget(fermer)
        v.addLayout(boutons)

    def on_ouvrir(self):
        ouvrir_questionnaire()
        self.confirmation.setText(
            "✓ Questionnaire ouvert dans votre navigateur, version copiée. "
            "Merci !")
        self.confirmation.show()


def inviter(parent, db, aujourdhui: date):
    """L'unique invitation. Elle est notée comme faite quelle que soit la
    réponse : un « Non merci » ne doit jamais revenir. Le bouton du menu
    reste là pour qui changerait d'avis."""
    db.set_setting(CLE_INVITATION_FAITE, aujourdhui.isoformat())
    boite = QMessageBox(parent)
    boite.setWindowTitle("Votre avis sur Pécule")
    boite.setTextFormat(Qt.RichText)
    boite.setText(
        "Vous utilisez Pécule depuis deux semaines.<br><br>"
        "Qu'est-ce qui marche, qu'est-ce qui coince ? Deux minutes de "
        "questionnaire aident à l'améliorer.<br><br>"
        "<span style='color:#666'>Cette question ne vous sera plus posée. "
        "Le bouton « 💬 Votre avis » du menu de gauche reste à votre "
        "disposition.</span>")
    oui = boite.addButton("Donner mon avis…", QMessageBox.AcceptRole)
    boite.addButton("Non merci", QMessageBox.RejectRole)
    boite.exec()
    if boite.clickedButton() is oui:
        AvisDialog(parent).exec()
