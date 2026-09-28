"""Sauvegarde des données sur un support externe (clé USB, disque).

Les sauvegardes automatiques (sauvegardes/) restent sur le même disque que la
base : si ce disque lâche, ou si le PC est volé, tout part ensemble. Ce
module copie la base vers un dossier choisi par l'utilisateur, dans un
sous-dossier daté, puis VÉRIFIE chaque copie octet pour octet avant
d'annoncer que c'est fait.

Même module que dans Gestion Photovoltaïque (15/09/2026), plus
instantane_sqlite() : une base ouverte ne se copie pas comme un fichier
ordinaire, voir cette fonction. Il ne dépend pas de l'interface et
n'effectue aucun accès réseau.
"""
from __future__ import annotations

import hashlib
import shutil
import sqlite3
from datetime import date, datetime
from pathlib import Path


class SauvegardeImpossible(Exception):
    """Échec expliqué en français, à montrer tel quel à l'utilisateur."""


def _empreinte(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def instantane_sqlite(connexion: sqlite3.Connection, cible: Path) -> Path:
    """Copie cohérente d'une base SQLite ouverte, dans le fichier `cible`.

    Copier comptes.db comme un fichier ordinaire pendant que Pécule s'en
    sert pourrait saisir une écriture à moitié faite. L'API de sauvegarde de
    SQLite, elle, produit toujours une base complète et cohérente. On
    vérifie ensuite son intégrité : une copie abîmée ne doit jamais partir
    sur la clé.
    """
    cible = Path(cible)
    if cible.exists():
        cible.unlink()
    dest = sqlite3.connect(cible)
    try:
        connexion.backup(dest)
        verdict = dest.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        dest.close()
    if verdict != "ok":
        raise SauvegardeImpossible(
            "La base de données n'a pas pu être copiée proprement "
            f"({verdict}). Rien n'a été écrit sur la clé.")
    return cible


def texte_lisezmoi(nom_appli: str, version: str, quand: datetime,
                   fichiers: list[str], dossier_donnees: Path) -> str:
    """Le mode d'emploi déposé à côté des copies : sans lui, une sauvegarde
    retrouvée dans deux ans sur une clé ne dit pas quoi en faire."""
    liste = "\n".join(f"  - {nom}" for nom in fichiers)
    return (
        f"Sauvegarde faite par {nom_appli} {version}\n"
        f"le {quand:%d/%m/%Y à %H:%M}.\n"
        "\n"
        "Fichiers sauvegardés :\n"
        f"{liste}\n"
        "\n"
        "POUR LA REMETTRE EN SERVICE\n"
        "\n"
        f"1. Fermez {nom_appli}.\n"
        "2. Ouvrez le dossier de vos données. Sur l'ordinateur où cette\n"
        "   sauvegarde a été faite, c'était :\n"
        f"   {dossier_donnees}\n"
        "3. Recopiez-y les fichiers ci-dessus, en acceptant de remplacer\n"
        "   ceux qui s'y trouvent.\n"
        f"4. Relancez {nom_appli}.\n"
    )


def sauvegarder(fichiers: list[Path | None], destination: Path,
                dossier_donnees: Path, nom_appli: str, version: str,
                maintenant: datetime | None = None) -> tuple[Path, list[str]]:
    """Copie les fichiers existants dans un sous-dossier daté de
    `destination`, et vérifie chaque copie.

    Renvoie le dossier créé et la liste des fichiers copiés. Lève
    SauvegardeImpossible, avec un message compréhensible, si la sauvegarde
    ne peut pas être faite ou ne peut pas être garantie.
    """
    quand = maintenant or datetime.now()
    destination = Path(destination)
    if not destination.is_dir():
        raise SauvegardeImpossible(
            "Le dossier choisi est introuvable. La clé USB a-t-elle été "
            "retirée ?")
    # Sauvegarder dans le dossier des données lui-même ne protège de rien.
    if destination.resolve().is_relative_to(Path(dossier_donnees).resolve()):
        raise SauvegardeImpossible(
            "Ce dossier est celui de vos données : une copie à cet endroit "
            "disparaîtrait avec elles. Choisissez une clé USB ou un disque "
            "externe.")

    presents = [Path(f) for f in fichiers if f and Path(f).is_file()]
    if not presents:
        raise SauvegardeImpossible(
            "Il n'y a encore aucune donnée à sauvegarder.")

    base = f"Sauvegarde {nom_appli} {quand:%Y-%m-%d %Hh%M}"
    cible = destination / base
    n = 2
    while cible.exists():            # deux sauvegardes dans la même minute
        cible = destination / f"{base} ({n})"
        n += 1

    noms = [f.name for f in presents]
    try:
        cible.mkdir(parents=True)
        for f in presents:
            shutil.copy2(f, cible / f.name)
        (cible / "LISEZMOI.txt").write_text(
            texte_lisezmoi(nom_appli, version, quand, noms, dossier_donnees),
            encoding="utf-8")
    except OSError as e:
        raise SauvegardeImpossible(
            f"La copie a échoué ({e.strerror or e}). La clé est-elle pleine, "
            "retirée ou protégée en écriture ?") from e

    # Une copie n'est une sauvegarde que si elle est identique à l'original.
    for f in presents:
        if _empreinte(f) != _empreinte(cible / f.name):
            raise SauvegardeImpossible(
                f"La copie de {f.name} ne correspond pas à l'original : ne "
                "comptez pas sur cette sauvegarde, et réessayez sur un autre "
                "support.")
    return cible, noms


# ---------- rappel de sauvegarde externe (28/09/2026) ----------
# Commun aux trois applications. Chacune retient la date de sa derniere
# sauvegarde externe reussie (dans ses propres reglages) et montre ce rappel
# sur sa page d'accueil. Le texte est le meme partout.

SEUIL_RAPPEL_JOURS = 30


def rappel_sauvegarde_externe(derniere: str | None, depuis: str | None,
                              aujourd_hui: date | None = None,
                              seuil_jours: int = SEUIL_RAPPEL_JOURS
                              ) -> str | None:
    """Une phrase a afficher quand la derniere sauvegarde externe date de
    `seuil_jours` ou plus, ou None s'il n'y a rien a dire.

    `derniere` : date (AAAA-MM-JJ) de la derniere sauvegarde externe
    reussie, None s'il n'y en a jamais eu. `depuis` : date a partir de
    laquelle compter quand il n'y en a jamais eu (premiere utilisation de
    l'application) ; sans elle, on se tait plutot que de relancer un
    utilisateur qui vient d'installer l'application."""
    aujourd_hui = aujourd_hui or date.today()
    if derniere:
        try:
            jours = (aujourd_hui - date.fromisoformat(derniere[:10])).days
        except ValueError:
            return None
        if jours < seuil_jours:
            return None
        return (f"Aucune sauvegarde externe depuis {jours} jours : le bouton "
                "« 💾 Sauvegarde externe » copie vos données sur une clé USB "
                "ou un disque, à l'abri d'une panne de cet ordinateur.")
    if not depuis:
        return None
    try:
        jours = (aujourd_hui - date.fromisoformat(depuis[:10])).days
    except ValueError:
        return None
    if jours < seuil_jours:
        return None
    return ("Vos données n'ont encore jamais été copiées hors de cet "
            "ordinateur : le bouton « 💾 Sauvegarde externe » les met sur une "
            "clé USB ou un disque, à l'abri d'une panne.")
