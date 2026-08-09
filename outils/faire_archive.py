"""Fabrique l'archive .zip de la release, prête à être publiée.

À lancer APRÈS Construire-Exe.bat, qui produit dist/Comptes-Budget/.

Ce script fait trois choses que le .bat ne fait pas :

  * il ajoute Lisez-moi.txt et Budget.ico à la racine du dossier, comme dans
    les archives des versions précédentes ;
  * il construit le .zip sans entrée de dossier. Compress-Archive (le clic
    droit de Windows) écrit les dossiers sans le marqueur « répertoire » :
    un outil strict y voit alors un fichier vide en conflit avec le dossier
    du même nom, et refuse l'archive. C'est arrivé avec butler sur la 1.21.0,
    alors que Windows l'extrayait sans rien signaler ;
  * il affiche l'empreinte SHA-256, à reporter dans bucket/comptes-budget.json.

Lancement (depuis n'importe où) :

    python outils/faire_archive.py              → écrit dans dist/
    python outils/faire_archive.py mon_dossier  → écrit ailleurs
"""
import hashlib
import os
import shutil
import sqlite3
import sys
import zipfile

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from comptesbudget.constants import APP_VERSION      # noqa: E402

DOSSIER_BUILD = os.path.join(RACINE, "dist", "Comptes-Budget")
A_COPIER = ("Lisez-moi.txt", "Budget.ico")


def verifier_absence_de_donnees(dossier):
    """Refuse de continuer si une base contenant des opérations traîne ici.

    Lancer l'exe depuis dist/ y crée une comptes.db VIDE. On la supprime, car
    elle n'a rien à faire dans l'archive. Mais si elle contient des écritures,
    c'est qu'on ne travaille pas sur ce qu'on croit : on s'arrête.
    """
    base = os.path.join(dossier, "comptes.db")
    if not os.path.exists(base):
        return
    try:
        with sqlite3.connect(base) as conn:
            n = conn.execute("SELECT count(*) FROM transactions").fetchone()[0]
    except sqlite3.Error:
        n = -1
    if n == 0:
        os.remove(base)
        print("  base de test vide supprimée de dist/")
    else:
        raise SystemExit(
            f"ARRÊT : {base} contient {n} opération(s).\n"
            "Cette base n'est pas celle d'un dossier de construction. "
            "Vérifiez avant de continuer — rien n'a été modifié.")


def preparer(dossier):
    """Complète le dossier de construction comme dans les versions publiées."""
    for nom in A_COPIER:
        source = os.path.join(RACINE, nom)
        if not os.path.exists(source):
            raise SystemExit(f"ARRÊT : {nom} est introuvable à la racine.")
        shutil.copy2(source, os.path.join(dossier, nom))
        print(f"  {nom} ajouté")


def archiver(dossier, cible):
    """Écrit le .zip en n'y mettant QUE des fichiers (pas de dossiers)."""
    parent = os.path.dirname(dossier.rstrip(os.sep))
    if os.path.exists(cible):
        os.remove(cible)
    n = 0
    with zipfile.ZipFile(cible, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for courant, _, fichiers in os.walk(dossier):
            for f in sorted(fichiers):
                chemin = os.path.join(courant, f)
                # Dans un ZIP, les chemins s'écrivent toujours avec des
                # barres obliques, quel que soit le système.
                interne = os.path.relpath(chemin, parent).replace(os.sep, "/")
                z.write(chemin, interne)
                n += 1
    return n


def controler(cible):
    """Vérifie que l'archive est de celles qu'un outil strict accepte."""
    with zipfile.ZipFile(cible) as z:
        noms = z.namelist()
        problemes = []
        if any(i.is_dir() for i in z.infolist()):
            problemes.append("elle contient des entrées de dossier")
        if any(chr(92) in x for x in noms):
            problemes.append("des chemins utilisent des antislashs")
        if len(noms) != len(set(noms)):
            problemes.append("des noms sont en double")
        if z.testzip() is not None:
            problemes.append("des données sont corrompues")
        if "Comptes-Budget/Comptes-Budget.exe" not in noms:
            problemes.append("l'exécutable est absent")
    if problemes:
        raise SystemExit("ARCHIVE INVALIDE : " + " ; ".join(problemes))
    print(f"  contrôle : {len(noms)} fichiers, archive conforme")


def main():
    sortie = sys.argv[1] if len(sys.argv) > 1 else os.path.join(RACINE, "dist")
    if not os.path.isdir(DOSSIER_BUILD):
        raise SystemExit(
            f"ARRÊT : {DOSSIER_BUILD} n'existe pas.\n"
            "Lancez d'abord Construire-Exe.bat.")

    print(f"Version : {APP_VERSION}")
    verifier_absence_de_donnees(DOSSIER_BUILD)
    preparer(DOSSIER_BUILD)

    os.makedirs(sortie, exist_ok=True)
    cible = os.path.join(sortie, f"Comptes-Budget-{APP_VERSION}-win64.zip")
    n = archiver(DOSSIER_BUILD, cible)
    print(f"  {n} fichiers archivés")
    controler(cible)

    empreinte = hashlib.sha256(open(cible, "rb").read()).hexdigest()
    print()
    print(f"Archive : {cible}")
    print(f"Taille  : {os.path.getsize(cible)} octets")
    print(f"SHA-256 : {empreinte}")
    print()
    print("À reporter dans bucket/comptes-budget.json (version, url, hash),")
    print("puis publier la release GitHub et pousser sur itch.io avec butler.")


if __name__ == "__main__":
    main()
