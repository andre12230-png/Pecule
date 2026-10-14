"""Fabrique l'archive .zip de la release, prête à être publiée.

À lancer APRÈS Construire-Exe.bat, qui produit dist/Pecule/.

Ce script fait trois choses que le .bat ne fait pas :

  * il ajoute Lisez-moi.txt et Budget.ico à la racine du dossier, comme dans
    les archives des versions précédentes ;
  * il construit le .zip sans entrée de dossier. Compress-Archive (le clic
    droit de Windows) écrit les dossiers sans le marqueur « répertoire » :
    un outil strict y voit alors un fichier vide en conflit avec le dossier
    du même nom, et refuse l'archive. C'est arrivé avec butler sur la 1.21.0,
    alors que Windows l'extrayait sans rien signaler ;
  * il affiche l'empreinte SHA-256, à reporter dans bucket/pecule.json.

Lancement (depuis n'importe où) :

    python outils/faire_archive.py              → écrit dans dist/
    python outils/faire_archive.py mon_dossier  → écrit ailleurs
"""
import hashlib
import os
import shutil
import sys
import zipfile

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from comptesbudget.constants import APP_VERSION      # noqa: E402

DOSSIER_BUILD = os.path.join(RACINE, "dist", "Pecule")
A_COPIER = ("Lisez-moi.txt", "Budget.ico")


def verifier_absence_de_donnees(dossier):
    """S'arrête si un fichier de comptes se trouve dans le dossier.

    Lancer l'exe depuis dist/ y crée une comptes.db. On ne l'efface plus,
    même « vide » : une base sans opération garde soldes, budgets, règles et
    récurrences, et l'effacer sous Windows échouait de toute façon (audit
    du 14/10/2026, A07 et A08). On s'arrête et on demande de la déplacer.
    """
    bases = sorted(f for f in os.listdir(dossier)
                   if f.lower().startswith("comptes.db"))
    if bases:
        raise SystemExit(
            "ARRÊT : un fichier de comptes se trouve dans le dossier de "
            f"construction ({', '.join(bases)}).\n"
            "Il ne doit pas partir dans l'archive et peut contenir des "
            "données. Déplacez-le ailleurs, puis relancez. Rien n'a été "
            "modifié.")


def retirer_le_verrou(dossier):
    """Supprime le `pecule.lock` qu'a pu laisser un lancement d'essai.

    Ce fichier réserve la base à une fenêtre (cf. verrouiller_instance dans
    app.py). Publié dans l'archive, il arriverait chez l'utilisateur comme le
    verrou d'un autre ordinateur — Qt le reprendrait au bout de 30 secondes,
    mais autant ne pas le livrer du tout."""
    chemin = os.path.join(dossier, "pecule.lock")
    if os.path.exists(chemin):
        os.remove(chemin)
        print("  verrou d'essai (pecule.lock) supprimé de dist/")


# Ce qu'une archive de Pécule contient, et rien d'autre (audit du
# 14/10/2026, R01) : un relevé, un export ou une base laissés par erreur dans
# dist/Pecule partaient sinon dans le .zip publié. À la racine, trois
# fichiers nommés ; dans _internal, des fichiers de programme seulement.
A_LA_RACINE = {"Pecule.exe", "Lisez-moi.txt", "Budget.ico"}
DANS_INTERNAL = {".dll", ".pyd", ".qm", ".zip", ".ico"}


def fichiers_inattendus(chemins):
    """Parmi des chemins relatifs au dossier Pecule (barres obliques), ceux
    qui ne sont pas des fichiers du programme."""
    inattendus = []
    for chemin in chemins:
        morceaux = chemin.split("/")
        if len(morceaux) == 1:
            if chemin not in A_LA_RACINE:
                inattendus.append(chemin)
        elif morceaux[0] != "_internal" or \
                os.path.splitext(chemin)[1].lower() not in DANS_INTERNAL:
            inattendus.append(chemin)
    return inattendus


def verifier_contenu(dossier):
    """S'arrête si le dossier contient autre chose que le programme."""
    chemins = []
    for courant, _, fichiers in os.walk(dossier):
        for f in fichiers:
            chemin = os.path.relpath(os.path.join(courant, f), dossier)
            chemins.append(chemin.replace(os.sep, "/"))
    inattendus = fichiers_inattendus(chemins)
    if inattendus:
        raise SystemExit(
            "ARRÊT : fichiers inattendus dans le dossier à archiver :\n  "
            + "\n  ".join(sorted(inattendus))
            + "\nUn relevé, un export ou une base ne doivent jamais être "
            "publiés. Retirez-les, puis relancez. S'il s'agit d'un nouveau "
            "fichier du programme, ajoutez son type à DANS_INTERNAL.")


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
        if "Pecule/Pecule.exe" not in noms:
            problemes.append("l'exécutable est absent")
        intrus = fichiers_inattendus(
            [x.split("/", 1)[1] if x.startswith("Pecule/") else x
             for x in noms])
        if intrus:
            problemes.append("fichiers inattendus : " + ", ".join(intrus))
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
    retirer_le_verrou(DOSSIER_BUILD)
    preparer(DOSSIER_BUILD)
    verifier_contenu(DOSSIER_BUILD)

    os.makedirs(sortie, exist_ok=True)
    cible = os.path.join(sortie, f"Pecule-{APP_VERSION}-win64.zip")
    n = archiver(DOSSIER_BUILD, cible)
    print(f"  {n} fichiers archivés")
    controler(cible)

    empreinte = hashlib.sha256(open(cible, "rb").read()).hexdigest()
    print()
    print(f"Archive : {cible}")
    print(f"Taille  : {os.path.getsize(cible)} octets")
    print(f"SHA-256 : {empreinte}")
    print()
    print("À reporter dans bucket/pecule.json (version, url, hash),")
    print("puis publier la release GitHub.")


if __name__ == "__main__":
    main()
