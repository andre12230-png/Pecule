"""Refabrique les images de couverture de docs/media/.

Deux formats, deux usages :

  * **promo_cover_630x500.png** — couverture de plateforme de téléchargement.
    Rien ne l'utilise aujourd'hui, mais elle est prête si le besoin revient.
  * **promo_share_1200x630.png** — image de partage (`og:image`). C'est elle
    qui s'affiche quand on colle le lien du site dans un message, un réseau
    social ou un forum. Le rapport 1,91:1 est celui qu'attendent ces sites :
    avec un autre, l'image est recadrée sur les côtés ou rétrogradée en petite
    vignette. Avant, ce rôle était tenu par la capture du Bilan — illisible une
    fois réduite, et le nom du logiciel n'y apparaissait pas.

Pourquoi ce script : la couverture précédente avait été composée à la main et
portait encore « Comptes et Budget », l'ancien nom, un mois après le renommage,
avec un sac d'argent frappé d'un dollar alors que le logiciel ne connaît que
l'euro. Personne ne l'avait vue. Un fichier qu'on ne sait pas refabriquer
vieillit en silence.

Lancement (depuis n'importe où) :

    py outils/couverture.py              → écrase docs/media/
    py outils/couverture.py mon_dossier  → écrit ailleurs, pour voir

Ne pas poser QT_QPA_PLATFORM=offscreen : Qt ne trouverait plus aucune police et
tout le texte sortirait en carrés vides.
"""
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from PySide6.QtCore import QRectF, Qt                               # noqa: E402
from PySide6.QtGui import (QColor, QFont, QImage, QLinearGradient,  # noqa: E402
                           QPainter)
from PySide6.QtWidgets import QApplication                          # noqa: E402

# Le fond : un bleu marine profond, volontairement plus sombre que le logo.
# Le lien du sac est un #2d4fb3 presque identique au #2B4EAE utilisé ici
# auparavant — 1,03 de rapport de contraste, autant dire invisible : le haut du
# sac se fondait dans le fond. Ces deux bleus-ci le détachent nettement (2,15 et
# 2,38) sans toucher au logo, et font mieux ressortir le texte blanc.
BLEU_FONCE = QColor("#0A1740")
BLEU_MOYEN = QColor("#0F2050")
BLANC = QColor("#FFFFFF")
BLEU_PALE = QColor("#C7D8FA")

TITRE = "Pécule"
SOUS_TITRE = "Gérez vos comptes et votre budget personnels"
ARGUMENTS = "Gratuit  ·  Français  ·  Windows 10/11  ·  Open source"

# (fichier, largeur, hauteur, côté du logo, y du logo, tailles et y des textes)
FORMATS = [
    {"nom": "promo_cover_630x500.png", "l": 630, "h": 500,
     "logo": 190, "logo_y": 62,
     "titre": (44, 272), "sous": (15, 356), "args": (12, 418)},
    # Format large : le logo rétrécit et les textes se resserrent — 630 pixels
    # de haut au lieu de 500 pour une largeur presque double. Le bloc est posé
    # un peu au-dessus du centre géométrique : l'œil place le milieu plus haut
    # qu'il n'est, une composition centrée à la règle paraît tomber.
    {"nom": "promo_share_1200x630.png", "l": 1200, "h": 630,
     "logo": 180, "logo_y": 104,
     "titre": (58, 304), "sous": (20, 402), "args": (15, 474)},
]


def dessiner(fmt: dict, chemin_logo: str) -> QImage:
    largeur, hauteur = fmt["l"], fmt["h"]
    img = QImage(largeur, hauteur, QImage.Format_ARGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.setRenderHint(QPainter.TextAntialiasing)

    # Fond : dégradé en diagonale, du bleu moyen en haut au bleu foncé en bas.
    degrade = QLinearGradient(0, 0, largeur, hauteur)
    degrade.setColorAt(0.0, BLEU_MOYEN)
    degrade.setColorAt(1.0, BLEU_FONCE)
    p.fillRect(0, 0, largeur, hauteur, degrade)

    # Le logo du projet — un sac d'argent frappé d'un €.
    logo = QImage(chemin_logo)
    if logo.isNull():
        p.end()
        raise SystemExit(f"Logo introuvable ou illisible : {chemin_logo}")
    cote = fmt["logo"]
    logo = logo.scaled(cote, cote, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    p.drawImage((largeur - logo.width()) // 2, fmt["logo_y"], logo)

    def texte(contenu, taille, y, couleur, gras=False, espacement=0.0):
        f = QFont("Segoe UI", taille)
        f.setBold(gras)
        if espacement:
            f.setLetterSpacing(QFont.PercentageSpacing, 100 + espacement)
        p.setFont(f)
        p.setPen(couleur)
        p.drawText(QRectF(0, y, largeur, taille * 2.2),
                   Qt.AlignHCenter | Qt.AlignTop, contenu)

    texte(TITRE, *fmt["titre"], BLANC, gras=True)
    texte(SOUS_TITRE, *fmt["sous"], BLEU_PALE)
    texte(ARGUMENTS, *fmt["args"], BLANC, gras=True, espacement=4)

    p.end()
    return img


def main():
    dossier = (sys.argv[1] if len(sys.argv) > 1
               else os.path.join(RACINE, "docs", "media"))
    os.makedirs(dossier, exist_ok=True)
    app = QApplication.instance() or QApplication([])   # noqa: F841
    logo = os.path.join(RACINE, "docs", "media", "logo.png")
    for fmt in FORMATS:
        img = dessiner(fmt, logo)
        chemin = os.path.join(dossier, fmt["nom"])
        if not img.save(chemin):
            raise SystemExit(f"Écriture impossible : {chemin}")
        print(f"  {fmt['nom']}  ({img.width()} x {img.height()})")
    print(f"Écrites dans {dossier}")


if __name__ == "__main__":
    main()
