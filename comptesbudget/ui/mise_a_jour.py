"""« Mise à jour » : savoir s'il existe une version plus récente, sans
aucun accès réseau.

Pécule ne se connecte jamais à Internet : c'est une promesse écrite (page de
confidentialité, site « 100 % hors ligne », revue Winget). Il ne peut donc pas
découvrir lui-même qu'une nouvelle version est sortie. Ce bouton affiche la
version installée et ouvre, à la demande, la page de la dernière version dans
le navigateur : c'est l'utilisateur qui compare les numéros, et rien ne part
de Pécule.
"""

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)

from ..constants import APP_VERSION, PAGE_VERSIONS_URL, INSTALLEUR_URL


class MiseAJourDialog(QDialog):
    """Fenêtre ouverte par le bouton « Mise à jour » du menu de gauche."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Rechercher une mise à jour")
        self.setMinimumWidth(460)
        v = QVBoxLayout(self)
        v.setSpacing(12)

        self.version = QLabel(f"Vous utilisez <b>Pécule {APP_VERSION}</b>.")
        self.version.setTextFormat(Qt.RichText)
        v.addWidget(self.version)

        explication = QLabel(
            "Pécule ne se connecte jamais à Internet : il ne peut donc pas "
            "savoir tout seul qu'une nouvelle version existe.<br><br>"
            "<b>Voir les nouveautés</b> ouvre dans votre navigateur la page de "
            "la dernière version. Si son numéro est plus grand que le vôtre, "
            "une mise à jour vous attend.<br><br>"
            "<b>Télécharger l'installeur</b> récupère directement la dernière "
            "version. Fermez Pécule avant de le lancer : vos données ne sont "
            "pas touchées. Vous utilisez l'archive .zip ? Prenez-la sur la "
            "page des nouveautés.")
        explication.setTextFormat(Qt.RichText)
        explication.setWordWrap(True)
        v.addWidget(explication)

        # Confirmation affichée une fois le navigateur sollicité.
        self.confirmation = QLabel("")
        self.confirmation.setStyleSheet("color:#2E7D32")
        self.confirmation.setWordWrap(True)
        self.confirmation.hide()
        v.addWidget(self.confirmation)

        boutons = QHBoxLayout()
        boutons.addStretch()
        self.btn_nouveautes = QPushButton("🌐 Voir les nouveautés")
        self.btn_nouveautes.setDefault(True)
        self.btn_nouveautes.clicked.connect(
            lambda: self._ouvrir(PAGE_VERSIONS_URL,
                                 "✓ Page des nouveautés ouverte dans votre "
                                 "navigateur."))
        boutons.addWidget(self.btn_nouveautes)
        self.btn_installeur = QPushButton("⬇ Télécharger l'installeur")
        self.btn_installeur.clicked.connect(
            lambda: self._ouvrir(INSTALLEUR_URL,
                                 "✓ Téléchargement lancé dans votre "
                                 "navigateur. Fermez Pécule avant de lancer "
                                 "l'installeur."))
        boutons.addWidget(self.btn_installeur)
        fermer = QPushButton("Fermer")
        fermer.clicked.connect(self.accept)
        boutons.addWidget(fermer)
        v.addLayout(boutons)

    def _ouvrir(self, adresse: str, message: str):
        """Confie l'adresse au navigateur : Pécule, lui, ne télécharge rien."""
        QDesktopServices.openUrl(QUrl(adresse))
        self.confirmation.setText(message)
        self.confirmation.show()
