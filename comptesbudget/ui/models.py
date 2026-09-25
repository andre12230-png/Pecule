"""Modèle de table des transactions."""


from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor, QStandardItemModel, QStandardItem, QBrush,
)

from ..utils import (
    cat_color, deaccent, fmt_euro, fmt_date_fr, numero_cheque,
)

# Rôle sous lequel chaque cellule range sa valeur de TRI, distincte du texte
# affiché. Sans cela, un clic sur l'en-tête trierait sur le texte : les dates
# « 12/05/2026 » et les montants « 1 234,56 € » se rangeraient par ordre
# alphabétique, donc n'importe comment.
SORT_ROLE = Qt.UserRole + 1

# Bulle d'aide de la colonne P : un utilisateur a demandé « un raccourci pour
# pointer » alors que la barre d'espace existe depuis la 1.33.0 — on la montre
# là où l'on pointe.
AIDE_POINTAGE = (
    "Cliquer pour pointer ou dépointer.\n"
    "Raccourci : barre d'espace, sur une ou plusieurs lignes\n"
    "sélectionnées (Ctrl+clic ou Maj+clic).")


def charger_en_conservant_le_tri(table, model, transactions: list[dict]):
    """Recharge le tableau sans perdre la colonne de tri choisie.

    Remplir un modèle ne rejoue pas le tri : les nouvelles lignes arriveraient
    dans leur ordre d'insertion. Couper puis rétablir le tri le réapplique
    (setSortingEnabled relance un tri sur la colonne courante)."""
    table.setSortingEnabled(False)
    model.load(transactions)
    table.setSortingEnabled(True)


class TxTableModel(QStandardItemModel):
    """Modèle des opérations. Colonnes : P, Date, Libellé, Catégorie, Sous-cat,
    Type, Débit, Crédit."""

    HEADERS = ["P", "Date opér.", "Date valeur", "Libellé", "Catégorie",
               "Sous-catégorie", "Type", "Débit", "Crédit"]

    # Colonnes des deux dates, pour que les vues placent le tri initial sur
    # celle qui correspond au mode d'affichage choisi.
    COL_DATE_OP = 1
    COL_DATE_VALEUR = 2

    def __init__(self, parent=None):
        super().__init__(0, len(self.HEADERS), parent)
        self.setHorizontalHeaderLabels(self.HEADERS)
        self.horizontalHeaderItem(0).setToolTip(AIDE_POINTAGE)
        self.setSortRole(SORT_ROLE)
        self.tx_data = []  # liste des dicts en parallèle

    def load(self, transactions: list[dict]):
        self.tx_data = transactions
        self.setRowCount(0)
        for tx in transactions:
            self._append_row(tx)

    def _append_row(self, tx: dict):
        pointee = bool(tx.get("pointee"))
        # Échéance saisie d'avance, pas encore passée en banque : elle mérite
        # un symbole à elle, pour ne pas la confondre avec une opération réelle
        # simplement pas encore pointée.
        prevue = bool(tx.get("prevue")) and not pointee
        date_op = tx.get("date", "")
        date_val = tx.get("date_valeur") or date_op
        is_deferred = date_val and date_val != date_op
        # Le numéro d'un chèque s'affiche dans la colonne Type (« Cheque
        # n° 1234567 ») plutôt que dans une colonne à lui : une colonne de plus
        # élargirait la fenêtre, qui doit tenir en moitié d'écran.
        num = numero_cheque(tx)
        texte_type = tx.get("type", "") + (f" n° {num}" if num else "")
        items = [
            QStandardItem("✔" if pointee else ("⏳" if prevue else "○")),
            QStandardItem(fmt_date_fr(date_op)),
            QStandardItem(("⏱ " if is_deferred else "") + fmt_date_fr(date_val)),
            QStandardItem(tx.get("libelle", "")),
            QStandardItem(tx.get("categorie", "")),
            QStandardItem(tx.get("sous_cat", "")),
            QStandardItem(texte_type),
            QStandardItem(fmt_euro(tx["montant"]) if tx.get("montant", 0) < 0 else ""),
            QStandardItem(fmt_euro(tx["montant"]) if tx.get("montant", 0) > 0 else ""),
        ]
        # Valeur de tri de chaque colonne : les dates au format ISO (triables
        # tels quels), les montants en nombre, le texte sans accents ni casse.
        montant = tx.get("montant", 0) or 0
        valeurs_tri = [
            1 if pointee else 0,
            date_op,
            date_val,
            deaccent(tx.get("libelle", "")),
            deaccent(tx.get("categorie", "")),
            deaccent(tx.get("sous_cat", "")),
            deaccent(tx.get("type", "")),
            montant if montant < 0 else 0.0,   # colonne Débit
            montant if montant > 0 else 0.0,   # colonne Crédit
        ]
        for it, tri in zip(items, valeurs_tri):
            it.setEditable(False)
            it.setData(tx["id"], Qt.UserRole)
            it.setData(tri, SORT_ROLE)
            if pointee:
                # Gris foncé (#5A5A5A, contraste 7:1) et non gris pâle : une
                # opération pointée doit se distinguer des autres sans
                # devenir pénible à lire — et sur une base tenue à jour,
                # elles sont l'immense majorité des lignes.
                it.setForeground(QBrush(QColor("#5A5A5A")))

        # Couleur P
        if pointee:
            items[0].setForeground(QBrush(QColor("#18733A")))
            items[0].setBackground(QBrush(QColor("#D6F0DC")))
        elif prevue:
            items[0].setForeground(QBrush(QColor("#C77B00")))
            items[0].setToolTip(
                "Échéance prévue : pas encore passée en banque.\n"
                "Elle sera complétée automatiquement à l'import du relevé.\n\n"
                + AIDE_POINTAGE)
        else:
            items[0].setForeground(QBrush(QColor("#CCC")))
        if not prevue:
            items[0].setToolTip(AIDE_POINTAGE)
        items[0].setTextAlignment(Qt.AlignCenter)

        # Date valeur en orange si différée (débit différé)
        if is_deferred:
            items[2].setForeground(QBrush(QColor("#E67E22")))
            items[2].setToolTip("Débit différé : la banque débitera à cette date")
        else:
            # Même remarque : #999 sur blanc rendait la date de valeur
            # presque illisible, alors qu'elle sert au rapprochement.
            items[2].setForeground(QBrush(QColor("#5A5A5A")))

        # Numéro de chèque en bulle d'aide : la colonne Type est étroite et
        # peut couper un long numéro.
        if num:
            items[6].setToolTip(f"Chèque n° {num}")

        # Pastille de catégorie : couleur de catégorie
        items[4].setForeground(QBrush(QColor(cat_color(tx.get("categorie", "")))))

        # Alignement des montants à droite
        items[7].setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        items[8].setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        items[7].setForeground(QBrush(QColor("#C0392B")))
        items[8].setForeground(QBrush(QColor("#18733A")))

        self.appendRow(items)
