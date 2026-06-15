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
    cat_color, fmt_euro, in_period,
)
from ...database import Database

from ..models import TxTableModel
from ..dialogs import TxDialog

class CategoriesView(QWidget):
    cat_changed = Signal()

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.period = "all"
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
        rv.addWidget(self.tx_table)

        splitter.addWidget(right)
        splitter.setSizes([320, 700])
        v.addWidget(splitter)

    def refresh(self):
        txs = [dict(r) for r in self.db.list_tx()
               if in_period(dict(r).get("date", ""), self.period)]
        by_cat = {}
        for t in txs:
            c = t.get("categorie", "Non classé")
            by_cat.setdefault(c, []).append(t)

        self.cats_model.setRowCount(0)
        for c in sorted(by_cat.keys()):
            n = len(by_cat[c])
            tot = sum(t["montant"] for t in by_cat[c])
            it_c = QStandardItem(c)
            it_c.setForeground(QBrush(QColor(cat_color(c))))
            it_c.setData(c, Qt.UserRole)
            it_n = QStandardItem(str(n)); it_n.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_t = QStandardItem(fmt_euro(tot)); it_t.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_t.setForeground(QBrush(QColor("#C0392B" if tot < 0 else "#229954")))
            self.cats_model.appendRow([it_c, it_n, it_t])

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
        txs = [dict(r) for r in self.db.list_tx()
               if dict(r).get("categorie") == cat
               and in_period(dict(r).get("date", ""), self.period)]
        self._show_cat(cat, txs)

    def _show_cat(self, cat: str, txs: list[dict]):
        txs = sorted(txs, key=lambda t: t.get("date", ""), reverse=True)
        self.tx_model.load(txs)
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
        affected = [dict(r) for r in self.db.list_tx()
                    if r["categorie"] == self.current_cat]
        if QMessageBox.question(
                self, "Confirmer",
                f"Déplacer {len(affected)} opération(s) vers « {new_cat} » ?") != QMessageBox.Yes:
            return
        for t in affected:
            self.db.update_tx(t["id"], {"categorie": new_cat.strip()})
        self.current_cat = new_cat.strip()
        self.refresh()
        self.cat_changed.emit()
