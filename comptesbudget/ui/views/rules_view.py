"""Vue Règles auto."""

import uuid
from datetime import date
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QColor, QStandardItemModel, QStandardItem, QKeySequence, QShortcut, QBrush,
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTableView, QAbstractItemView,
    QDialog, QMessageBox, QMenu,
)

from ...utils import (
    fmt_euro,
)
from ...database import Database
from ...rules import apply_rules_to_tx

from ..dialogs import RuleDialog

class RulesView(QWidget):
    rules_changed = Signal()

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)

        toolbar = QHBoxLayout()
        self.btn_new = QPushButton("➕ Nouvelle règle")
        self.btn_new.clicked.connect(self.new_rule)
        toolbar.addWidget(self.btn_new)
        self.btn_apply = QPushButton("🔄 Appliquer aux opérations existantes")
        self.btn_apply.clicked.connect(self.apply_all)
        toolbar.addWidget(self.btn_apply)
        toolbar.addStretch()
        v.addLayout(toolbar)

        self.model = QStandardItemModel(0, 6, self)
        self.model.setHorizontalHeaderLabels(
            ["Motif", "Montant exact", "Sens", "Catégorie", "Sous-catégorie", "Créée le"])
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self.edit_selected)
        self.table.setColumnWidth(0, 220)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 180)
        self.table.setColumnWidth(4, 180)
        self.table.setColumnWidth(5, 100)
        v.addWidget(self.table)

        btn_row = QHBoxLayout()
        self.btn_edit = QPushButton("✏️ Modifier la règle")
        self.btn_edit.clicked.connect(self.edit_selected)
        btn_row.addWidget(self.btn_edit)
        self.btn_del = QPushButton("🗑 Supprimer la règle")
        self.btn_del.clicked.connect(self.delete_selected)
        btn_row.addWidget(self.btn_del)
        btn_row.addStretch()
        v.addLayout(btn_row)

        # Raccourci clavier Suppr + menu contextuel (clic droit)
        QShortcut(QKeySequence("Delete"), self.table, activated=self.delete_selected)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

    def _show_context_menu(self, pos):
        if not self._selected_id():
            return
        menu = QMenu(self)
        act_edit = menu.addAction("✏️ Modifier la règle")
        act_del = menu.addAction("🗑 Supprimer la règle")
        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen == act_edit:
            self.edit_selected()
        elif chosen == act_del:
            self.delete_selected()

    SENS_LBL = {"": "Les deux", "debit": "− Débit", "credit": "+ Crédit", None: "Les deux"}

    def refresh(self):
        rules = [dict(r) for r in self.db.list_rules()]
        self.model.setRowCount(0)
        for r in rules:
            sens = r.get("sens") or ""
            it_sens = QStandardItem(self.SENS_LBL.get(sens, "Les deux"))
            if sens == "debit":
                it_sens.setForeground(QBrush(QColor("#C0392B")))
            elif sens == "credit":
                it_sens.setForeground(QBrush(QColor("#229954")))
            items = [
                QStandardItem(r["pattern"]),
                QStandardItem(fmt_euro(r["amount"]) if r["amount"] is not None else "—"),
                it_sens,
                QStandardItem(r["categorie"]),
                QStandardItem(r["sous_cat"]),
                QStandardItem(r["created_at"]),
            ]
            for it in items:
                it.setData(r["id"], Qt.UserRole)
            self.model.appendRow(items)

    def _selected_id(self) -> Optional[str]:
        idx = self.table.currentIndex()
        if not idx.isValid():
            return None
        return self.model.item(idx.row(), 0).data(Qt.UserRole)

    def new_rule(self):
        cats = self.db.all_categories_used()
        dlg = RuleDialog(self, None, cats)
        if dlg.exec() != QDialog.Accepted:
            return
        v = dlg.values()
        if len(v["pattern"]) < 2:
            QMessageBox.warning(self, "Règle", "Le motif doit faire au moins 2 caractères.")
            return
        v["id"] = str(uuid.uuid4())
        v["created_at"] = date.today().isoformat()
        self.db.insert_rule(v)
        self.refresh()
        self.rules_changed.emit()

    def edit_selected(self):
        rid = self._selected_id()
        if not rid:
            return
        row = next((dict(r) for r in self.db.list_rules() if r["id"] == rid), None)
        if not row:
            return
        cats = self.db.all_categories_used()
        dlg = RuleDialog(self, row, cats)
        if dlg.exec() != QDialog.Accepted:
            return
        v = dlg.values()
        if len(v["pattern"]) < 2:
            QMessageBox.warning(self, "Règle", "Le motif doit faire au moins 2 caractères.")
            return
        self.db.update_rule(rid, v)
        self.refresh()
        self.rules_changed.emit()

    def delete_selected(self):
        rid = self._selected_id()
        if not rid:
            return
        if QMessageBox.question(self, "Supprimer", "Supprimer cette règle ?") != QMessageBox.Yes:
            return
        self.db.delete_rule(rid)
        self.refresh()
        self.rules_changed.emit()

    def apply_all(self):
        rules = [dict(r) for r in self.db.list_rules()]
        if not rules:
            QMessageBox.information(self, "Règles", "Aucune règle à appliquer.")
            return
        txs = [dict(r) for r in self.db.list_tx()]
        modified = 0
        for tx in txs:
            ok, fields = apply_rules_to_tx(tx, rules)
            if ok and (fields.get("categorie") != tx.get("categorie")
                       or fields.get("sous_cat") != tx.get("sous_cat")):
                self.db.update_tx(tx["id"], fields)
                modified += 1
        QMessageBox.information(self, "Règles",
            f"{modified} opération(s) mise(s) à jour.")
        self.rules_changed.emit()
