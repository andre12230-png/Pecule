"""Modèle de table des transactions."""


from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor, QStandardItemModel, QStandardItem, QBrush,
)

from ..utils import (
    cat_color, fmt_euro, fmt_date_fr,
)

class TxTableModel(QStandardItemModel):
    """Modèle des opérations. Colonnes : P, Date, Libellé, Catégorie, Sous-cat,
    Type, Débit, Crédit."""

    HEADERS = ["P", "Date opér.", "Date valeur", "Libellé", "Catégorie",
               "Sous-catégorie", "Type", "Débit", "Crédit"]

    def __init__(self, parent=None):
        super().__init__(0, len(self.HEADERS), parent)
        self.setHorizontalHeaderLabels(self.HEADERS)
        self.tx_data = []  # liste des dicts en parallèle

    def load(self, transactions: list[dict]):
        self.tx_data = transactions
        self.setRowCount(0)
        for tx in transactions:
            self._append_row(tx)

    def _append_row(self, tx: dict):
        pointee = bool(tx.get("pointee"))
        date_op = tx.get("date", "")
        date_val = tx.get("date_valeur") or date_op
        is_deferred = date_val and date_val != date_op
        items = [
            QStandardItem("✔" if pointee else "○"),
            QStandardItem(fmt_date_fr(date_op)),
            QStandardItem(("⏱ " if is_deferred else "") + fmt_date_fr(date_val)),
            QStandardItem(tx.get("libelle", "")),
            QStandardItem(tx.get("categorie", "")),
            QStandardItem(tx.get("sous_cat", "")),
            QStandardItem(tx.get("type", "")),
            QStandardItem(fmt_euro(tx["montant"]) if tx.get("montant", 0) < 0 else ""),
            QStandardItem(fmt_euro(tx["montant"]) if tx.get("montant", 0) > 0 else ""),
        ]
        for it in items:
            it.setEditable(False)
            it.setData(tx["id"], Qt.UserRole)
            if pointee:
                it.setForeground(QBrush(QColor("#888")))

        # Couleur P
        if pointee:
            items[0].setForeground(QBrush(QColor("#1A7A3A")))
            items[0].setBackground(QBrush(QColor("#D6F0DC")))
        else:
            items[0].setForeground(QBrush(QColor("#CCC")))
        items[0].setTextAlignment(Qt.AlignCenter)

        # Date valeur en orange si différée (débit différé)
        if is_deferred:
            items[2].setForeground(QBrush(QColor("#E67E22")))
            items[2].setToolTip("Débit différé : la banque débitera à cette date")
        else:
            items[2].setForeground(QBrush(QColor("#999")))

        # Pastille de catégorie : couleur de catégorie
        items[4].setForeground(QBrush(QColor(cat_color(tx.get("categorie", "")))))

        # Alignement des montants à droite
        items[7].setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        items[8].setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        items[7].setForeground(QBrush(QColor("#C0392B")))
        items[8].setForeground(QBrush(QColor("#229954")))

        self.appendRow(items)
