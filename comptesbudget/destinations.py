"""Où un export a le droit d'écrire (audit du 14/10/2026, constat A01).

Les fenêtres « Enregistrer sous » acceptent n'importe quel fichier, même
quand on leur indique « *.csv » : choisir par erreur comptes.db comme
destination remplaçait le fichier de comptes par l'export, et la base
devenait illisible. Avant d'écrire, chaque export passe donc par
destination_refusee(). Ce module ne dépend pas de Qt.
"""
import os
from typing import Optional

# Un fichier de comptes de Pécule (ou d'un autre logiciel SQLite) et ses
# fichiers compagnons : jamais une destination d'export.
EXTENSIONS_DE_BASE = (".db", ".db-wal", ".db-shm", ".db-journal",
                      ".sqlite", ".sqlite3")


def _meme_fichier(a: str, b: str) -> bool:
    """Vrai si les deux chemins désignent le même fichier (casse, barres
    obliques et raccourcis « .. » compris)."""
    try:
        if os.path.exists(a) and os.path.exists(b):
            return os.path.samefile(a, b)
    except OSError:
        pass
    return (os.path.normcase(os.path.abspath(a))
            == os.path.normcase(os.path.abspath(b)))


def destination_refusee(chemin: str, base: str) -> Optional[str]:
    """Raison du refus, en clair, ou None si l'export peut écrire là.

    `base` : le fichier de comptes ouvert."""
    if _meme_fichier(chemin, base):
        return ("Ce fichier est celui de vos comptes : l'export le "
                "remplacerait et vos comptes seraient perdus. Choisissez un "
                "autre nom.")
    if chemin.lower().endswith(EXTENSIONS_DE_BASE):
        return ("Ce nom est celui d'un fichier de comptes (.db). Pour ne "
                "jamais en écraser un, l'export refuse ce type de fichier. "
                "Choisissez un autre nom.")
    return None


def avec_extension(chemin: str, extension: str) -> str:
    """Ajoute l'extension attendue (« .csv », « .json », « .pdf ») si le nom
    choisi ne l'a pas déjà, quelle que soit la casse."""
    if chemin.lower().endswith(extension.lower()):
        return chemin
    return chemin + extension
