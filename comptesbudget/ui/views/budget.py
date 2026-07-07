"""Vue Budget (barres de progression)."""


from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QColor, QStandardItemModel, QStandardItem, QBrush,
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTableView, QAbstractItemView,
    QProgressBar, QInputDialog,
)

from ...utils import (
    cat_color, fmt_euro, in_period,
)
from ...database import Database

class BudgetView(QWidget):
    budget_changed = Signal()

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.period = "all"
        v = QVBoxLayout(self); v.setContentsMargins(8, 8, 8, 8)

        info = QLabel(
            "Définissez un budget mensuel par catégorie. La barre de progression montre le pourcentage "
            "dépensé pour la période sélectionnée (rapporté au nombre de mois)."
        )
        info.setWordWrap(True); info.setStyleSheet("color:#555; padding:6px")
        v.addWidget(info)

        self.table = QTableView()
        self.model = QStandardItemModel(0, 5, self)
        self.model.setHorizontalHeaderLabels(
            ["Catégorie", "Budget mensuel", "Dépensé", "Progression", "Reste / Dépassement"])
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self._edit_budget)
        v.addWidget(self.table)

        h = QHBoxLayout()
        self.btn_edit = QPushButton("✏️ Définir / modifier le budget")
        self.btn_edit.clicked.connect(self._edit_budget)
        h.addWidget(self.btn_edit)
        h.addStretch()
        v.addLayout(h)

    def _month_count(self) -> int:
        """Nombre de mois couverts par la période (pour rapporter le budget
        mensuel). Pour une année — même l'année en cours — on compte les mois
        qui ont réellement des opérations : en juillet, le budget annuel vaut
        7 mois de budget, pas 12."""
        if self.period == "all" or len(self.period) == 4:
            txs = [dict(r) for r in self.db.list_tx()]
            months = {t["date"][:7] for t in txs
                      if t.get("date") and in_period(t["date"], self.period)}
            return max(1, len(months))
        return 1

    def refresh(self):
        budgets = self.db.list_budgets()
        txs = [dict(r) for r in self.db.list_tx()]
        active = [t for t in txs
                  if t.get("categorie") != "Transaction exclue"
                  and in_period(t.get("date", ""), self.period)
                  and t.get("montant", 0) < 0]
        # Dépensé par catégorie
        spent = {}
        for t in active:
            c = t.get("categorie", "Non classé")
            spent[c] = spent.get(c, 0) + abs(t["montant"])

        cats = sorted(set(list(budgets.keys()) + list(spent.keys())))
        n_months = self._month_count()

        self.model.setRowCount(0)
        for i, cat in enumerate(cats):
            budget = budgets.get(cat, 0)
            dep = spent.get(cat, 0)
            budget_periode = budget * n_months  # cumulé
            ratio = (dep / budget_periode * 100) if budget_periode > 0 else 0
            reste = budget_periode - dep

            it_cat = QStandardItem(cat)
            it_cat.setForeground(QBrush(QColor(cat_color(cat))))
            it_cat.setData(cat, Qt.UserRole)

            it_bud = QStandardItem(fmt_euro(budget) if budget else "—")
            it_bud.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            it_dep = QStandardItem(fmt_euro(dep))
            it_dep.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            it_prog = QStandardItem("")
            it_prog.setData(ratio, Qt.UserRole)

            it_reste = QStandardItem(fmt_euro(reste) if budget else "—")
            it_reste.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if budget:
                if reste < 0:
                    it_reste.setForeground(QBrush(QColor("#C0392B")))
                else:
                    it_reste.setForeground(QBrush(QColor("#229954")))

            self.model.appendRow([it_cat, it_bud, it_dep, it_prog, it_reste])

            # Barre de progression dans la cellule
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(min(int(ratio), 100) if budget > 0 else 0)
            bar.setFormat(f"{ratio:.0f}%" if budget else "—")
            color = "#27AE60" if ratio < 80 else ("#E67E22" if ratio < 100 else "#C0392B")
            bar.setStyleSheet(f"""
                QProgressBar {{ border:1px solid #BBB; border-radius:3px; text-align:center; background:#F5F5F5; }}
                QProgressBar::chunk {{ background:{color}; }}
            """)
            self.table.setIndexWidget(self.model.index(i, 3), bar)

        # Largeurs
        self.table.setColumnWidth(0, 220)
        self.table.setColumnWidth(1, 130)
        self.table.setColumnWidth(2, 130)
        self.table.setColumnWidth(3, 240)
        self.table.setColumnWidth(4, 160)

    def _edit_budget(self):
        idx = self.table.currentIndex()
        if not idx.isValid():
            return
        cat = self.model.item(idx.row(), 0).data(Qt.UserRole)
        if not cat:
            return
        current = self.db.list_budgets().get(cat, 0)
        v, ok = QInputDialog.getDouble(
            self, "Budget mensuel",
            f"Budget mensuel pour « {cat} » (en €) :",
            current, 0.0, 1_000_000.0, 2)
        if not ok:
            return
        self.db.set_budget(cat, v)
        self.refresh()
        self.budget_changed.emit()
