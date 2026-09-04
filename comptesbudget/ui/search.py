"""Recherche globale (Ctrl+F)."""


from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTableView, QAbstractItemView,
    QDialog,
)

from ..utils import (
    deaccent, fmt_euro, fmt_date_fr,
)
from ..database import Database

from .models import TxTableModel, charger_en_conservant_le_tri
from .dialogs import TxDialog

class GlobalSearchDialog(QDialog):
    """Recherche dans TOUT l'historique, sans tenir compte de la période
    affichée : libellé, note, référence, catégorie, sous-catégorie, type,
    date (jj/mm/aaaa) et montant (virgule ou point). Plusieurs mots = tous
    requis. Double-clic sur un résultat pour modifier l'opération."""

    def __init__(self, parent, db: Database):
        super().__init__(parent)
        self.db = db
        self.changed = False
        self.setWindowTitle("🔎 Recherche globale")
        self.resize(1000, 580)

        v = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("🔎"))
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(
            "Libellé, note, catégorie, montant (ex. 524,99), date (12/05/2026)… "
            "— plusieurs mots : tous doivent correspondre")
        self.edit.textChanged.connect(self._search)
        row.addWidget(self.edit, 1)
        v.addLayout(row)

        self.model = TxTableModel()
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self._edit_tx)
        for i, w in enumerate([32, 85, 95, 280, 150, 140, 110, 95, 95]):
            self.table.setColumnWidth(i, w)
        # Tri par clic sur les en-têtes, du plus récent au plus ancien au départ
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.sortByColumn(TxTableModel.COL_DATE_OP, Qt.DescendingOrder)
        v.addWidget(self.table, 1)

        foot = QHBoxLayout()
        self.lbl = QLabel("")
        self.lbl.setStyleSheet("color:#666")
        foot.addWidget(self.lbl)
        foot.addStretch()
        b_close = QPushButton("Fermer")
        # Entrée dans le champ de recherche NE doit PAS fermer la fenêtre
        # (par défaut, Entrée « clique » le premier bouton du dialogue).
        b_close.setAutoDefault(False)
        b_close.setDefault(False)
        b_close.clicked.connect(self.accept)
        foot.addWidget(b_close)
        v.addLayout(foot)
        self.edit.returnPressed.connect(self._search)   # Entrée = relancer

        self._reindex()
        self._search()
        self.edit.setFocus()

    @staticmethod
    def _blob(t: dict) -> str:
        m = abs(t.get("montant", 0) or 0)
        parts = [t.get("libelle", ""), t.get("libelle_op", ""),
                 t.get("reference", ""), t.get("info", ""),
                 t.get("categorie", ""), t.get("sous_cat", ""),
                 t.get("type", ""), t.get("date", ""),
                 fmt_date_fr(t.get("date", "")),
                 f"{m:.2f}", f"{m:.2f}".replace(".", ","), f"{m:g}"]
        return deaccent(" ".join(parts))

    def _reindex(self):
        self._rows = [dict(r) for r in self.db.list_tx()]
        self._blobs = [(t, self._blob(t)) for t in self._rows]

    def _search(self, *_):
        # Tolère la saisie « comme à l'écran » : « -1 234,56 € » fonctionne.
        # Le € et le signe sont ignorés (les montants sont indexés en valeur
        # absolue) ; « 1 234,56 » se découpe en mots qui doivent tous matcher.
        brut = self.edit.text().replace("€", " ")
        words = [w.lstrip("+-") for w in deaccent(brut).split()]
        words = [w for w in words if w]
        if words:
            res = [t for t, blob in self._blobs
                   if all(w in blob for w in words)]
        else:
            res = list(self._rows)
        res.sort(key=lambda t: t.get("date", ""), reverse=True)
        shown = res[:500]
        charger_en_conservant_le_tri(self.table, self.model, shown)
        total = sum(t.get("montant", 0) for t in res)
        if words:
            extra = " — affichage des 500 premières" if len(res) > 500 else ""
            self.lbl.setText(
                f"{len(res)} opération(s) trouvée(s) — total {fmt_euro(total)}{extra}")
        else:
            self.lbl.setText(
                f"{len(self._rows)} opérations dans l'historique — tapez pour filtrer")

    def _edit_tx(self, index):
        if not index.isValid():
            return
        tx_id = self.model.item(index.row(), 0).data(Qt.UserRole)
        if not tx_id:
            return
        row = next((dict(r) for r in self.db.list_tx() if r["id"] == tx_id), None)
        if not row:
            return
        cats = self.db.categories_proposees()
        all_tx = [dict(r) for r in self.db.list_tx()]
        dlg = TxDialog(self, row, cats, all_tx)
        if dlg.exec() != QDialog.Accepted:
            return
        vals = dlg.values()
        self.db.update_tx(tx_id, {k: vals[k] for k in vals if not k.startswith("_")})
        self.changed = True
        self._reindex()
        self._search()
