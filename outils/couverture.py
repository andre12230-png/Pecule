"""Refabrique l'image de couverture (docs/media/promo_cover_630x500.png).

Pourquoi ce script : la couverture précédente avait été composée à la main et
portait encore « Comptes et Budget », l'ancien nom du logiciel, un an après le
renommage — sans que personne s'en aperçoive, car elle n'est référencée nulle
part. Un fichier qu'on ne sait pas refabriquer vieillit en silence.

Format 630 x 500 : celui des couvertures de plateformes de téléchargement. Rien
ne l'utilise aujourd'hui, mais l'image est prête si le besoin revient.

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

from PySide6.QtCore import QRectF, Qt                              # noqa: E402
from PySide6.QtGui import (QColor, QFont, QImage, QLinearGradient,  # noqa: E402
                           QPainter)
from PySide6.QtWidgets import QApplication                         # noqa: E402

LARGEUR, HAUTEUR = 630, 500

# Les deux bleus du logo : le foncé du lien du sac, le clair de sa panse.
BLEU_FONCE = QColor("#1E3A8A")
BLEU_MOYEN = QColor("#2B4EAE")
BLANC = QColor("#FFFFFF")
BLEU_PALE = QColor("#C7D8FA")

TITRE = "Pécule"
SOUS_TITRE = "Gérez vos comptes et votre budget personnels"
ARGUMENTS = "Gratuit  ·  Français  ·  Windows 10/11  ·  Open source"


def dessiner(chemin_logo: str) -> QImage:
    img = QImage(LARGEUR, HAUTEUR, QImage.Format_ARGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.setRenderHint(QPainter.TextAntialiasing)

    # Fond : dégradé en diagonale, du bleu moyen en haut au bleu foncé en bas.
    degrade = QLinearGradient(0, 0, LARGEUR, HAUTEUR)
    degrade.setColorAt(0.0, BLEU_MOYEN)
    degrade.setColorAt(1.0, BLEU_FONCE)
    p.fillRect(0, 0, LARGEUR, HAUTEUR, degrade)

    # Le logo du projet — un sac d'argent frappé d'un €. L'ancienne couverture
    # montrait un $ : le logiciel ne connaît que l'euro.
    logo = QImage(chemin_logo)
    if logo.isNull():
        p.end()
        raise SystemExit(f"Logo introuvable ou illisible : {chemin_logo}")
    cote = 190
    logo = logo.scaled(cote, cote, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    p.drawImage((LARGEUR - logo.width()) // 2, 62, logo)

    def texte(contenu, y, taille, couleur, gras=False, espacement=0.0):
        f = QFont("Segoe UI", taille)
        f.setBold(gras)
        if espacement:
            f.setLetterSpacing(QFont.PercentageSpacing, 100 + espacement)
        p.setFont(f)
        p.setPen(couleur)
        p.drawText(QRectF(0, y, LARGEUR, taille * 2.2),
                   Qt.AlignHCenter | Qt.AlignTop, contenu)

    texte(TITRE, 272, 44, BLANC, gras=True)
    texte(SOUS_TITRE, 356, 15, BLEU_PALE)
    texte(ARGUMENTS, 418, 12, BLANC, gras=True, espacement=4)

    p.end()
    return img


def main():
    dossier = sys.argv[1] if len(sys.argv) > 1 else os.path.join(RACINE, "docs", "media")
    os.makedirs(dossier, exist_ok=True)
    app = QApplication.instance() or QApplication([])   # noqa: F841
    img = dessiner(os.path.join(RACINE, "docs", "media", "logo.png"))
    chemin = os.path.join(dossier, "promo_cover_630x500.png")
    if not img.save(chemin):
        raise SystemExit(f"Écriture impossible : {chemin}")
    print(f"Couverture écrite : {chemin}")
    print(f"  {img.width()} x {img.height()}")


if __name__ == "__main__":
    main()
