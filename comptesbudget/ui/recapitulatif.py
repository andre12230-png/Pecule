"""« Tous les comptes » : les soldes de chaque compte côte à côte, et leur
total.

Pécule affiche un compte à la fois. Pour savoir où l'on en est « en tout »,
il fallait passer d'un compte à l'autre et additionner de tête. Cette fenêtre
fait l'addition. Idée venue d'un utilisateur, via le questionnaire « Votre
avis » (septembre 2026).

Les chiffres sont ceux du Bilan de chaque compte (voir
Database.soldes_compte) : un compte ne doit pas afficher ici un autre solde
que dans son Bilan.
"""

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QHeaderView, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from ..utils import fmt_date_fr, fmt_euro

ROUGE = "#C0392B"
VERT = "#229954"

# Titres courts : « Dernière opération pointée » coupait la colonne.
COLONNES = ["Compte", "En banque", "Non pointé", "Solde comptable",
            "Dernier pointage"]


class RecapComptesDialog(QDialog):
    """Une ligne par compte, une ligne de total. Un double-clic sur un compte
    l'affiche dans la fenêtre principale : l'appelant lit `compte_choisi`."""

    def __init__(self, db, parent=None, aujourdhui: str = None):
        super().__init__(parent)
        self.db = db
        self.aujourdhui = aujourdhui or date.today().isoformat()
        # Compte à afficher en quittant (None : ne rien changer).
        self.compte_choisi = None
        self.setWindowTitle("Tous mes comptes")
        self.setMinimumWidth(640)

        lay = QVBoxLayout(self)

        intro = QLabel(
            f"Soldes au <b>{fmt_date_fr(self.aujourdhui)}</b>, calculés comme "
            "le Bilan de chaque compte. Double-cliquez sur un compte pour "
            "l'afficher.")
        intro.setWordWrap(True)
        lay.addWidget(intro)

        self.table = QTableWidget(0, len(COLONNES))
        self.table.setHorizontalHeaderLabels(COLONNES)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        # Chaque colonne prend la largeur de son contenu, la dernière comble
        # le reste : étirer la colonne des noms les tronquait (« Compte … »).
        entete = self.table.horizontalHeader()
        for col in range(len(COLONNES)):
            entete.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        entete.setStretchLastSection(True)
        self.table.cellDoubleClicked.connect(self._afficher_ligne)
        lay.addWidget(self.table)

        # Ce que veulent dire les colonnes, en clair : c'est la question
        # qu'on se pose devant deux soldes différents pour un même compte.
        note = QLabel(
            "<b>En banque</b> : le solde de départ et les opérations pointées "
            "(vérifiées sur le relevé), à leur date de valeur — le chiffre que "
            "donne la banque.<br>"
            "<b>Solde comptable</b> : le même, plus les opérations saisies mais "
            "pas encore pointées.<br>"
            "Les virements entre vos comptes s'annulent dans le total quand "
            "ils sont saisis des deux côtés.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#555; padding:6px; background:#F6F7F9; "
                           "border:1px solid #DCDCDC")
        lay.addWidget(note)
        # L'espace en trop va en bas, pas entre le texte et le tableau.
        lay.addStretch(1)

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        self.btn_afficher = QPushButton("Afficher ce compte")
        self.btn_afficher.clicked.connect(self._afficher_selection)
        btns.addButton(self.btn_afficher, QDialogButtonBox.ActionRole)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

        self.remplir()

    # ── Contenu ──────────────────────────────────────────────────────
    def remplir(self):
        comptes = self.db.list_comptes()
        self.table.setRowCount(len(comptes) + 1)
        total_banque = total_attente = total_comptable = 0.0

        for ligne, compte in enumerate(comptes):
            s = self.db.soldes_compte(compte["id"], self.aujourdhui)
            total_banque += s["banque"]
            total_attente += s["attente"]
            total_comptable += s["comptable"]

            nom = compte["nom"]
            if compte["id"] == self.db.compte_id:
                nom += "  (affiché)"
            cellule_nom = QTableWidgetItem(nom)
            # L'identifiant voyage avec la ligne, pour le double-clic.
            cellule_nom.setData(Qt.UserRole, compte["id"])
            self.table.setItem(ligne, 0, cellule_nom)
            self.table.setItem(ligne, 1, self._montant(s["banque"]))
            attente = self._montant(s["attente"], colorer=False)
            if s["nb_attente"]:
                attente.setToolTip(f"{s['nb_attente']} opération(s)")
            self.table.setItem(ligne, 2, attente)
            self.table.setItem(ligne, 3, self._montant(s["comptable"]))
            jour = (fmt_date_fr(s["derniere_pointee"])
                    if s["derniere_pointee"] else "—")
            cellule_jour = QTableWidgetItem(jour)
            cellule_jour.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(ligne, 4, cellule_jour)

        # Ligne de total, en gras sur fond gris : on ne la confond pas avec
        # un compte, et elle ne s'affiche pas au double-clic.
        ligne = len(comptes)
        gras = QFont()
        gras.setBold(True)
        fond = QBrush(QColor("#ECEEF2"))
        cellules = [
            QTableWidgetItem("Total"),
            self._montant(round(total_banque, 2)),
            self._montant(round(total_attente, 2), colorer=False),
            self._montant(round(total_comptable, 2)),
            QTableWidgetItem(""),
        ]
        for col, cellule in enumerate(cellules):
            cellule.setFont(gras)
            cellule.setBackground(fond)
            self.table.setItem(ligne, col, cellule)

        # Sélectionne le compte affiché, pour que « Afficher ce compte »
        # ait toujours une cible.
        for l in range(len(comptes)):
            if self.table.item(l, 0).data(Qt.UserRole) == self.db.compte_id:
                self.table.selectRow(l)
                break

        # Le tableau prend juste la hauteur de ses lignes : sans cela, deux
        # comptes laissaient un grand vide blanc au-dessous.
        self.table.resizeRowsToContents()
        # sizeHint et non height() : avant l'affichage, l'en-tête n'a pas
        # encore reçu sa vraie hauteur.
        hauteur = (self.table.horizontalHeader().sizeHint().height()
                   + sum(self.table.rowHeight(l)
                         for l in range(self.table.rowCount()))
                   + 2 * self.table.frameWidth())
        self.table.setFixedHeight(hauteur)
        # Et au moins la largeur de ses colonnes : la fenêtre s'élargit avec
        # un nom de compte long plutôt que de couper la dernière colonne.
        self.table.resizeColumnsToContents()
        self.table.setMinimumWidth(self.table.horizontalHeader().length()
                                   + 2 * self.table.frameWidth())

    @staticmethod
    def _montant(valeur: float, colorer: bool = True) -> QTableWidgetItem:
        """Cellule d'un montant : alignée à droite, en rouge si négative."""
        cellule = QTableWidgetItem(fmt_euro(valeur))
        cellule.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if colorer:
            cellule.setForeground(QBrush(QColor(ROUGE if valeur < 0 else VERT)))
        return cellule

    # ── Actions ──────────────────────────────────────────────────────
    def _afficher_ligne(self, ligne: int, _colonne: int = 0):
        cellule = self.table.item(ligne, 0)
        cid = cellule.data(Qt.UserRole) if cellule else None
        if cid:     # la ligne de total n'en porte pas
            self.compte_choisi = cid
            self.accept()

    def _afficher_selection(self):
        self._afficher_ligne(self.table.currentRow())
