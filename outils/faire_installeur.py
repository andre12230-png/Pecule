"""Fabrique l'installeur Windows de Pécule (Pecule-Setup-X.Y.Z.exe).

À lancer APRÈS Construire-Exe.bat, qui produit dist/Pecule/. Nécessite
Inno Setup 6 (gratuit) : winget install JRSoftware.InnoSetup

Ce script :

  * refait les contrôles de faire_archive.py sur le dossier construit — pas
    de base de données ni de verrou d'essai, Lisez-moi.txt et Budget.ico
    ajoutés ;
  * lance le compilateur d'Inno Setup sur outils/pecule.iss en lui passant
    le numéro de version (APP_VERSION) ;
  * affiche l'empreinte SHA-256 de l'installeur produit.

L'installeur est publié EN PLUS du .zip, pas à sa place : Scoop et Winget
téléchargent le .zip.

Lancement (depuis n'importe où) :

    py outils/faire_installeur.py
"""
import hashlib
import os
import subprocess
import sys

OUTILS = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(OUTILS)
sys.path.insert(0, RACINE)

from comptesbudget.constants import APP_VERSION      # noqa: E402
from faire_archive import (DOSSIER_BUILD, preparer,   # noqa: E402
                           retirer_le_verrou, verifier_absence_de_donnees)

RECETTE = os.path.join(OUTILS, "pecule.iss")


def trouver_iscc():
    """Cherche le compilateur d'Inno Setup aux endroits habituels.

    La variable d'environnement ISCC permet d'en imposer un autre."""
    candidats = [os.environ.get("ISCC", "")]
    for base in (os.environ.get("LOCALAPPDATA", "") + r"\Programs",
                 os.environ.get("ProgramFiles(x86)", ""),
                 os.environ.get("ProgramFiles", "")):
        candidats.append(os.path.join(base, "Inno Setup 6", "ISCC.exe"))
    for chemin in candidats:
        if chemin and os.path.isfile(chemin):
            return chemin
    raise SystemExit(
        "ARRÊT : Inno Setup 6 est introuvable.\n"
        "Installez-le avec : winget install JRSoftware.InnoSetup")


def main():
    if not os.path.isdir(DOSSIER_BUILD):
        raise SystemExit(
            f"ARRÊT : {DOSSIER_BUILD} n'existe pas.\n"
            "Lancez d'abord Construire-Exe.bat.")

    print(f"Version : {APP_VERSION}")
    verifier_absence_de_donnees(DOSSIER_BUILD)
    retirer_le_verrou(DOSSIER_BUILD)
    preparer(DOSSIER_BUILD)

    iscc = trouver_iscc()
    print(f"Inno Setup : {iscc}")
    # /Q : n'affiche que les erreurs. /D : définit AppVersion pour la recette.
    resultat = subprocess.run(
        [iscc, "/Q", f"/DAppVersion={APP_VERSION}", RECETTE])
    if resultat.returncode != 0:
        raise SystemExit("ARRÊT : la compilation de l'installeur a échoué.")

    cible = os.path.join(RACINE, "dist", f"Pecule-Setup-{APP_VERSION}.exe")
    if not os.path.isfile(cible):
        raise SystemExit(f"ARRÊT : {cible} n'a pas été produit.")
    with open(cible, "rb") as f:
        empreinte = hashlib.sha256(f.read()).hexdigest()
    print()
    print(f"Installeur : {cible}")
    print(f"Taille     : {os.path.getsize(cible)} octets")
    print(f"SHA-256    : {empreinte}")


if __name__ == "__main__":
    main()
