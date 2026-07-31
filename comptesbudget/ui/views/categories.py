"""Vue Catégories (drill-down)."""

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QColor, QStandardItemModel, QStandardItem, QBrush,
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTableView, QAbstractItemView,
    QDialog, QMessageBox, QSplitter,
    QInputDialog,
)

from ...constants import (
    CATEGORIES_DEFAUT,
)
from ...utils import (
    cat_color, deaccent, fmt_euro, in_period, period_label,
)
from ...database import Database

from ..models import SORT_ROLE, TxTableModel, charger_en_conservant_le_tri
from ..dialogs import TxDialog

class CategoriesView(QWidget):
    cat_changed = Signal()

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.period = "all"
        self.date_mode = "valeur"   # suit le sélecteur « Date » de la barre du haut
        self.current_cat: Optional[str] = None

        v = QVBoxLayout(self); v.setContentsMargins(8, 8, 8, 8)

        splitter = QSplitter(Qt.Horizontal)

        # Panneau gauche : liste des catégories
        left = QWidget(); lv = QVBoxLayout(left); lv.setContentsMargins(0, 0, 0, 0)
        lv.addWidget(QLabel("Catégories — cliquez pour voir les opérations"))
        self.cats_model = QStandardItemModel(0, 3, self)
        self.cats_model.setHorizontalHeaderLabels(["Catégorie", "Nb", "Total"])
        self.cats_table = QTableView()
        self.cats_table.setModel(self.cats_model)
        self.cats_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.cats_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.cats_table.verticalHeader().setVisible(False)
        self.cats_table.clicked.connect(self._on_cat_clicked)
        # Tri par clic : par nom, par nombre d'opérations ou par total
        self.cats_model.setSortRole(SORT_ROLE)
        self.cats_table.setSortingEnabled(True)
        self.cats_table.horizontalHeader().setSortIndicatorShown(True)
        lv.addWidget(self.cats_table)
        splitter.addWidget(left)

        # Panneau droit : transactions de la catégorie sélectionnée
        right = QWidget(); rv = QVBoxLayout(right); rv.setContentsMargins(0, 0, 0, 0)
        self.cat_title = QLabel("Sélectionnez une catégorie")
        self.cat_title.setStyleSheet("font-weight:bold; font-size:11pt; padding:4px")
        rv.addWidget(self.cat_title)

        action_row = QHBoxLayout()
        self.btn_recat = QPushButton("🏷️ Recatégoriser toutes ces opérations…")
        self.btn_recat.clicked.connect(self._recategorize)
        self.btn_recat.setEnabled(False)
        action_row.addWidget(self.btn_recat)
        action_row.addStretch()
        rv.addLayout(action_row)

        self.tx_model = TxTableModel()
        self.tx_table = QTableView()
        self.tx_table.setModel(self.tx_model)
        self.tx_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tx_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tx_table.verticalHeader().setVisible(False)
        self.tx_table.doubleClicked.connect(self._edit_tx)
        for i, w in enumerate([32, 90, 280, 160, 140, 120, 100, 100]):
            self.tx_table.setColumnWidth(i, w)
        self.tx_table.setSortingEnabled(True)
        self.tx_table.horizontalHeader().setSortIndicatorShown(True)
        self.tx_table.sortByColumn(TxTableModel.COL_DATE_VALEUR, Qt.DescendingOrder)
        rv.addWidget(self.tx_table)

        splitter.addWidget(right)
        splitter.setSizes([320, 700])
        v.addWidget(splitter)

    def _eff_date(self, t: dict) -> str:
        """Date utilisée pour la période affichée : elle suit le sélecteur
        « Date » de la barre du haut, comme le Bilan et les Opérations."""
        if self.date_mode == "valeur":
            return t.get("date_valeur") or t.get("date", "")
        return t.get("date", "")

    def refresh(self):
        txs = [t for t in (dict(r) for r in self.db.list_tx())
               if in_period(self._eff_date(t), self.period)]
        by_cat = {}
        for t in txs:
            c = t.get("categorie", "Non classé")
            by_cat.setdefault(c, []).append(t)

        self.cats_table.setSortingEnabled(False)   # rétabli après remplissage
        self.cats_model.setRowCount(0)
        for c in sorted(by_cat.keys()):
            n = len(by_cat[c])
            tot = sum(t["montant"] for t in by_cat[c])
            it_c = QStandardItem(c)
            it_c.setForeground(QBrush(QColor(cat_color(c))))
            it_c.setData(c, Qt.UserRole)
            it_c.setData(deaccent(c), SORT_ROLE)
            it_n = QStandardItem(str(n)); it_n.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_n.setData(n, SORT_ROLE)          # trier sur le nombre, pas « 10 » < « 9 »
            it_t = QStandardItem(fmt_euro(tot)); it_t.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_t.setForeground(QBrush(QColor("#C0392B" if tot < 0 else "#229954")))
            it_t.setData(tot, SORT_ROLE)
            self.cats_model.appendRow([it_c, it_n, it_t])
        self.cats_table.setSortingEnabled(True)

        self.cats_table.setColumnWidth(0, 200)
        self.cats_table.setColumnWidth(1, 50)
        self.cats_table.setColumnWidth(2, 110)

        # Re-rendu du panneau de droite avec la catégorie actuelle
        if self.current_cat and self.current_cat in by_cat:
            self._show_cat(self.current_cat, by_cat[self.current_cat])
        else:
            self.current_cat = None
            self.tx_model.setRowCount(0)
            self.cat_title.setText("Sélectionnez une catégorie")
            self.btn_recat.setEnabled(False)

    def _on_cat_clicked(self, index):
        cat = self.cats_model.item(index.row(), 0).data(Qt.UserRole)
        if not cat:
            return
        self.current_cat = cat
        txs = [t for t in (dict(r) for r in self.db.list_tx())
               if t.get("categorie") == cat
               and in_period(self._eff_date(t), self.period)]
        self._show_cat(cat, txs)

    def _show_cat(self, cat: str, txs: list[dict]):
        txs = sorted(txs, key=self._eff_date, reverse=True)
        charger_en_conservant_le_tri(self.tx_table, self.tx_model, txs)
        total = sum(t["montant"] for t in txs)
        self.cat_title.setText(f"« {cat} » — {len(txs)} opération(s)  —  {fmt_euro(total)}")
        self.btn_recat.setEnabled(True)

    def _edit_tx(self, index):
        if not index.isValid():
            return
        tx_id = self.tx_model.item(index.row(), 0).data(Qt.UserRole)
        if not tx_id:
            return
        row = next((dict(r) for r in self.db.list_tx() if r["id"] == tx_id), None)
        if not row:
            return
        cats = self.db.all_categories_used()
        all_tx = [dict(r) for r in self.db.list_tx()]
        dlg = TxDialog(self, row, cats, all_tx)
        if dlg.exec() != QDialog.Accepted:
            return
        v = dlg.values()
        v_db = {k: v[k] for k in v if not k.startswith("_")}
        self.db.update_tx(tx_id, v_db)
        self.refresh()
        self.cat_changed.emit()

    def _recategorize(self):
        if not self.current_cat:
            return
        cats = sorted(set(self.db.all_categories_used() + CATEGORIES_DEFAUT))
        new_cat, ok = QInputDialog.getItem(
            self, "Recatégoriser",
            f"Déplacer toutes les opérations de « {self.current_cat} » vers :",
            cats, 0, True)
        if not ok or not new_cat.strip() or new_cat == self.current_cat:
            return
        # Le bouton agit sur ce que l'écran montre : la catégorie POUR LA
        # PÉRIODE affichée. Auparavant il déplaçait toute la base, y compris
        # des opérations invisibles à l'écran.
        affected = [t for t in (dict(r) for r in self.db.list_tx())
                    if t["categorie"] == self.current_cat
                    and in_period(self._eff_date(t), self.period)]
        if not affected:
            return
        portee = ("toutes périodes confondues" if self.period == "all"
                  else f"sur la période affichée ({period_label(self.period)})")
        if QMessageBox.question(
                self, "Confirmer",
                f"Déplacer {len(affected)} opération(s) de « {self.current_cat} » "
                f"vers « {new_cat} » ?\n\n"
                f"Seules les opérations {portee} sont concernées."
        ) != QMessageBox.Yes:
            return
        with self.db.batch():
            for t in affected:
                self.db.update_tx(t["id"], {"categorie": new_cat.strip()})
        self.current_cat = new_cat.strip()
        self.refresh()
        self.cat_changed.emit()
