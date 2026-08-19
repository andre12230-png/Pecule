"""Disposition « en flux » : les éléments se rangent sur une ligne, et passent
à la ligne suivante quand la largeur ne suffit plus.

Qt ne fournit pas cette disposition en standard ; ce fichier reprend
l'exemple officiel de la documentation Qt (« Flow Layout »), traduit et
commenté.

À quoi ça sert ici : la barre de filtres de l'onglet Opérations alignait
ses six contrôles sur une seule ligne, et réclamait donc 1500 pixels de
large en permanence — la fenêtre ne pouvait plus être réduite à la moitié
de l'écran. Avec cette disposition, la barre reste sur une ligne quand la
fenêtre est large (aspect inchangé) et se répartit sur deux lignes quand
la fenêtre est étroite.
"""

from PySide6.QtCore import QMargins, QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout


class FlowLayout(QLayout):
    def __init__(self, parent=None, marge=0, espacement=6):
        super().__init__(parent)
        self._elements = []
        self.setContentsMargins(QMargins(marge, marge, marge, marge))
        self.setSpacing(espacement)

    # ── Méthodes que tout QLayout doit fournir ────────────────────────
    def addItem(self, element):
        self._elements.append(element)

    def count(self):
        return len(self._elements)

    def itemAt(self, index):
        if 0 <= index < len(self._elements):
            return self._elements[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._elements):
            return self._elements.pop(index)
        return None

    # ── La hauteur dépend de la largeur disponible ────────────────────
    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, largeur):
        # Calcul « à blanc » : combien de hauteur faut-il pour cette largeur ?
        return self._placer(QRect(0, 0, largeur, 0), pour_de_vrai=False)

    def expandingDirections(self):
        # La barre ne réclame pas d'espace supplémentaire d'elle-même.
        return Qt.Orientations(Qt.Orientation(0))

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._placer(rect, pour_de_vrai=True)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        # Largeur minimale = celle du plus large des éléments (et non leur
        # somme) : c'est ce qui permet à la fenêtre de se réduire.
        taille = QSize()
        for element in self._elements:
            taille = taille.expandedTo(element.minimumSize())
        m = self.contentsMargins()
        return taille + QSize(m.left() + m.right(), m.top() + m.bottom())

    # ── Placement effectif ────────────────────────────────────────────
    def _placer(self, rect, pour_de_vrai):
        """Range les éléments de gauche à droite, en passant à la ligne dès
        que la largeur est dépassée. Renvoie la hauteur totale utilisée."""
        gauche, haut, droite, bas = self.getContentsMargins()
        zone = rect.adjusted(gauche, haut, -droite, -bas)
        x = zone.x()
        y = zone.y()
        hauteur_ligne = 0

        for element in self._elements:
            taille = element.sizeHint()
            x_suivant = x + taille.width()
            if x_suivant - zone.x() > zone.width() and hauteur_ligne > 0:
                # Plus de place sur cette ligne : on descend d'un cran.
                x = zone.x()
                y = y + hauteur_ligne + self.spacing()
                x_suivant = x + taille.width()
                hauteur_ligne = 0
            if pour_de_vrai:
                element.setGeometry(QRect(QPoint(x, y), taille))
            x = x_suivant + self.spacing()
            hauteur_ligne = max(hauteur_ligne, taille.height())

        return y + hauteur_ligne - rect.y() + bas
