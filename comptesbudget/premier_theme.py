"""Choix Clair / Sombre au tout premier lancement (16/10/2026).

Demande de l'auteur, la même dans les trois applications : le mode sombre ne
se trouvait que dans Paramètres › Apparence, où un nouvel utilisateur ne le
cherchait pas. Au premier lancement, avant d'ouvrir la fenêtre, Pécule
demande donc « Clair ou Sombre ? », et le choix s'applique tout de suite.

Elle n'est posée qu'une fois, et seulement à un vrai nouvel utilisateur :
- aucun thème encore choisi dans les préférences ;
- pas encore de comptes.db. Quelqu'un qui met à jour une ancienne version a
  déjà le sien : on ne le dérange pas, il garde le clair et peut changer
  dans Paramètres.
"""
from __future__ import annotations

import os

from PySide6.QtWidgets import QMessageBox

from . import theme


def est_premier_lancement(reglages, chemin_base: str) -> bool:
    """Vrai si aucun thème n'a encore été choisi ET si la base des comptes
    n'existe pas encore. Une préférence abîmée (revenue en liste, audit du
    13/10/2026) compte comme absente."""
    valeur = reglages.value(theme.CLE_THEME)
    if isinstance(valeur, str) and valeur in theme.THEMES:
        return False
    return not os.path.exists(chemin_base)


def boite_du_choix(parent=None):
    """La petite fenêtre de la question, et ses deux boutons.
    Rend (boite, bouton_clair, bouton_sombre)."""
    boite = QMessageBox(parent)
    boite.setWindowTitle("Pécule — Apparence")
    boite.setIcon(QMessageBox.Question)
    boite.setText(
        "Comment préférez-vous voir Pécule ?\n\n"
        "• Clair : fond crème, texte noir.\n"
        "• Sombre : fond brun très foncé, texte clair, plus reposant le "
        "soir.\n\n"
        "Vous pourrez changer d'avis à tout moment dans "
        # Espaces insécables autour de « › » : le chemin ne se coupe pas.
        "Paramètres › Apparence.")
    clair = boite.addButton("Clair", QMessageBox.AcceptRole)
    sombre = boite.addButton("Sombre", QMessageBox.AcceptRole)
    # Entrée ou la croix de fermeture : le clair, thème de référence.
    boite.setDefaultButton(clair)
    boite.setEscapeButton(clair)
    return boite, clair, sombre


def demander_a_l_ecran() -> str:
    """Montre la question et rend « clair » ou « sombre ». L'application
    porte déjà le thème clair (app.main), celui de la session tant que rien
    n'est choisi."""
    boite, _clair, sombre = boite_du_choix()
    boite.exec()
    return "sombre" if boite.clickedButton() is sombre else "clair"


def demander_au_premier_lancement(reglages, chemin_base: str,
                                  demander=demander_a_l_ecran) -> str | None:
    """Pose la question si c'est le premier lancement et retient la réponse
    dans les préférences, pour ne plus la reposer. Rend le thème choisi, ou
    None si rien n'a été demandé.

    `reglages` : None pour les préférences de Pécule (registre de
    Windows) ; `demander` : remplaçable par les tests."""
    if reglages is None:
        reglages = theme.preferences()
    if not est_premier_lancement(reglages, chemin_base):
        return None
    nom = demander()
    # Écriture vérifiée ; si elle échoue, le choix vaut quand même pour
    # cette session, et la question reviendra au prochain lancement.
    theme.enregistrer_theme(nom, reglages)
    return nom
