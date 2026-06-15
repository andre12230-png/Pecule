"""Lanceur de l'application « Comptes et Budget ».

Tout le code est désormais organisé dans le package ``comptesbudget/``.
Ce fichier reste le point d'entrée historique : il est utilisé tel quel par
les scripts ``.bat`` (Lancer-Comptes-Budget.bat) et par PyInstaller
(Construire-Exe.bat), qui n'ont donc pas besoin d'être modifiés.

Lancement :  python comptes_budget.py
"""
from comptesbudget.app import main

if __name__ == "__main__":
    main()
