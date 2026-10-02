"""Retire le damier presque invisible de l'icône et du logo de Pécule.

Pourquoi ce script : Budget.ico et docs/media/logo.png portent un damier
presque transparent, reste du fond « transparent » de l'outil qui a dessiné le
logo. Invisible sur fond blanc, il ressort sur un fond sombre (barre des
tâches en mode sombre, images de partage du site) — constat du 02/10/2026.

Chaque taille de l'icône (16 à 256 pixels) est nettoyée séparément, avec la
règle de outils/couverture.py : les pixels presque transparents deviennent
transparents, les autres reprennent la plus proche des trois couleurs du logo.

Lancement (depuis n'importe où) :

    py outils/nettoyer_icone.py              → écrase Budget.ico et logo.png
    py outils/nettoyer_icone.py mon_dossier  → écrit ailleurs, pour voir
"""
import os
import struct
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.join(RACINE, "outils"))

from PySide6.QtCore import QBuffer, QByteArray, QIODevice   # noqa: E402
from PySide6.QtGui import QImage                            # noqa: E402
from PySide6.QtWidgets import QApplication                  # noqa: E402

from couverture import nettoyer_logo                        # noqa: E402


def lire_ico(chemin: str) -> list[bytes]:
    """Les images d'un .ico, dans l'ordre, chacune en PNG (c'est le cas de
    Budget.ico pour ses sept tailles)."""
    d = open(chemin, "rb").read()
    _, type_, nombre = struct.unpack("<HHH", d[:6])
    if type_ != 1:
        raise SystemExit(f"{chemin} n'est pas une icône")
    images = []
    for k in range(nombre):
        *_, taille, debut = struct.unpack("<BBBBHHII", d[6 + 16 * k:22 + 16 * k])
        bloc = d[debut:debut + taille]
        if not bloc.startswith(b"\x89PNG"):
            raise SystemExit("Image d'icône au format BMP : non prévu ici")
        images.append(bloc)
    return images


def en_png(img: QImage) -> bytes:
    tampon = QByteArray()
    flux = QBuffer(tampon)
    flux.open(QIODevice.WriteOnly)
    img.save(flux, "PNG")
    return bytes(tampon.data())


def ecrire_ico(chemin: str, pngs: list[tuple[int, bytes]]):
    """Écrit un .ico dont chaque taille est un PNG (Windows Vista et après)."""
    entete = struct.pack("<HHH", 0, 1, len(pngs))
    repertoire, donnees = b"", b""
    debut = 6 + 16 * len(pngs)
    for cote, png in pngs:
        c = 0 if cote >= 256 else cote        # 0 veut dire 256 dans un .ico
        repertoire += struct.pack("<BBBBHHII", c, c, 0, 0, 1, 32, len(png),
                                  debut + len(donnees))
        donnees += png
    with open(chemin, "wb") as f:
        f.write(entete + repertoire + donnees)


def main():
    app = QApplication.instance() or QApplication([])   # noqa: F841
    sortie = sys.argv[1] if len(sys.argv) > 1 else None
    ico = os.path.join(RACINE, "Budget.ico")
    logo = os.path.join(RACINE, "docs", "media", "logo.png")

    propres = []
    for bloc in lire_ico(ico):
        img = nettoyer_logo(QImage.fromData(bloc))
        propres.append((img.width(), en_png(img)))
        print(f"  icône {img.width()} x {img.height()} nettoyée")
    logo_propre = nettoyer_logo(QImage(logo))

    if sortie:
        os.makedirs(sortie, exist_ok=True)
        ico = os.path.join(sortie, "Budget.ico")
        logo = os.path.join(sortie, "logo.png")
    ecrire_ico(ico, propres)
    if not logo_propre.save(logo):
        raise SystemExit(f"Écriture impossible : {logo}")
    print(f"Écrits : {ico}\n         {logo}")


if __name__ == "__main__":
    main()
