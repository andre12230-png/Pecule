"""Vue Opérations."""

import uuid
from datetime import date
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QKeySequence, QShortcut,
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QComboBox, QTableView, QHeaderView, QAbstractItemView,
    QDialog, QMessageBox,
)

from ...constants import (
    FREQUENCIES,
)
from ...utils import (
    fmt_euro, in_period,
)
from ...database import Database
from ...rules import apply_rules_to_tx

from ..models import TxTableModel
from ..dialogs import TxDialog

class OperationsView(QWidget):
    tx_changed = Signal()  # émis quand une transaction est ajoutée/modifiée/supprimée

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.transactions: list[dict] = []
        self.filtered: list[dict] = []
        self.period = "all"
        self.date_mode = "valeur"  # "operation" ou "valeur"

        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)

        # Barre d'outils
        toolbar = QHBoxLayout()
        self.btn_new = QPushButton("➕ Nouvelle")
        self.btn_new.clicked.connect(self.add_tx)
        toolbar.addWidget(self.btn_new)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher dans les libellés…")
        self.search.textChanged.connect(self.refresh)
        self.search.setMaximumWidth(260)
        toolbar.addWidget(self.search)

        toolbar.addWidget(QLabel("Catégorie :"))
        self.cat_filter = QComboBox()
        self.cat_filter.currentTextChanged.connect(self.refresh)
        toolbar.addWidget(self.cat_filter)

        toolbar.addWidget(QLabel("Type :"))
        self.optype_filter = QComboBox()
        self.optype_filter.setMinimumWidth(140)
        self.optype_filter.currentTextChanged.connect(self.refresh)
        toolbar.addWidget(self.optype_filter)

        toolbar.addWidget(QLabel("Sens :"))
        self.type_filter = QComboBox()
        self.type_filter.addItems(["Tous", "Débit", "Crédit"])
        self.type_filter.currentTextChanged.connect(self.refresh)
        toolbar.addWidget(self.type_filter)

        toolbar.addWidget(QLabel("Pointage :"))
        self.pt_filter = QComboBox()
        self.pt_filter.addItems(["Toutes", "Non pointées", "Pointées"])
        self.pt_filter.currentTextChanged.connect(self.refresh)
        toolbar.addWidget(self.pt_filter)

        toolbar.addStretch()
        self.lbl_count = QLabel("0 opération")
        self.lbl_count.setStyleSheet("color: #666")
        toolbar.addWidget(self.lbl_count)

        v.addLayout(toolbar)

        # Tableau
        self.model = TxTableModel()
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.doubleClicked.connect(self.edit_selected)
        self.table.clicked.connect(self.handle_click)

        # Largeurs de colonnes : P, Date opér., Date valeur, Libellé, Catégorie,
        # Sous-cat, Type, Débit, Crédit
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.Interactive)
        h.setStretchLastSection(False)
        for i, w in enumerate([32, 90, 95, 260, 160, 140, 120, 100, 100]):
            self.table.setColumnWidth(i, w)

        v.addWidget(self.table)

        # Raccourcis
        QShortcut(QKeySequence("Delete"), self, activated=self.delete_selected)
        QShortcut(QKeySequence("Insert"), self, activated=self.add_tx)
        QShortcut(QKeySequence("Return"), self, activated=self.edit_selected)

    def reload_from_db(self):
        self.transactions = [dict(r) for r in self.db.list_tx()]
        # Catégories disponibles
        cats = sorted(set(t.get("categorie") for t in self.transactions if t.get("categorie")))
        current = self.cat_filter.currentText()
        self.cat_filter.blockSignals(True)
        self.cat_filter.clear()
        self.cat_filter.addItem("Toutes")
        self.cat_filter.addItems(cats)
        idx = self.cat_filter.findText(current)
        if idx >= 0:
            self.cat_filter.setCurrentIndex(idx)
        self.cat_filter.blockSignals(False)
        # Types d'opération disponibles (Carte bancaire, Virement, …)
        optypes = sorted(set((t.get("type") or "").strip()
                             for t in self.transactions
                             if (t.get("type") or "").strip()))
        cur_opt = self.optype_filter.currentText()
        self.optype_filter.blockSignals(True)
        self.optype_filter.clear()
        self.optype_filter.addItem("Tous")
        self.optype_filter.addItems(optypes)
        idx2 = self.optype_filter.findText(cur_opt)
        if idx2 >= 0:
            self.optype_filter.setCurrentIndex(idx2)
        self.optype_filter.blockSignals(False)
        self.refresh()

    def _eff_date(self, t: dict) -> str:
        """Date effective selon le mode choisi."""
        if self.date_mode == "valeur":
            return t.get("date_valeur") or t.get("date", "")
        return t.get("date", "")

    def refresh(self):
        q = self.search.text().strip().lower()
        cat = self.cat_filter.currentText()
        tp = self.type_filter.currentText()
        opt = self.optype_filter.currentText()
        pt = self.pt_filter.currentText()

        def keep(t: dict) -> bool:
            if not in_period(self._eff_date(t), self.period):
                return False
            if q:
                blob = f"{t.get('libelle','')} {t.get('libelle_op','')} {t.get('reference','')} {t.get('info','')}".lower()
                if q not in blob:
                    return False
            if cat and cat != "Toutes" and t.get("categorie") != cat:
                return False
            if opt and opt != "Tous" and (t.get("type") or "").strip() != opt:
                return False
            if tp == "Débit" and t.get("montant", 0) >= 0:
                return False
            if tp == "Crédit" and t.get("montant", 0) <= 0:
                return False
            if pt == "Pointées" and not t.get("pointee"):
                return False
            if pt == "Non pointées" and t.get("pointee"):
                return False
            return True

        self.filtered = [t for t in self.transactions if keep(t)]
        # Tri par la date effective
        self.filtered.sort(key=self._eff_date, reverse=True)
        self.model.load(self.filtered)

        solde = sum(t.get("montant", 0) for t in self.filtered)
        pointed = [t for t in self.filtered if t.get("pointee")]
        solde_p = sum(t.get("montant", 0) for t in pointed)
        mode_lbl = "valeur (banque)" if self.date_mode == "valeur" else "opération"
        txt = (f"{len(self.filtered)} opération{'s' if len(self.filtered)>1 else ''} "
               f"— solde {mode_lbl} : {fmt_euro(solde)}")
        if pointed:
            txt += f"   ✔ pointées : {fmt_euro(solde_p)}"
        self.lbl_count.setText(txt)

    # ── Actions ─────────────────────────────────────────────────────
    def selected_tx_id(self) -> Optional[str]:
        idx = self.table.currentIndex()
        if not idx.isValid():
            return None
        return self.model.item(idx.row(), 0).data(Qt.UserRole)

    def handle_click(self, index):
        """Clic sur la colonne P → bascule le pointage."""
        if index.column() != 0:
            return
        tx_id = self.model.item(index.row(), 0).data(Qt.UserRole)
        if not tx_id:
            return
        self.db.toggle_pointee(tx_id)
        # Mise à jour locale
        for t in self.transactions:
            if t["id"] == tx_id:
                t["pointee"] = 0 if t.get("pointee") else 1
                break
        self.refresh()
        self.tx_changed.emit()

    def _maybe_create_recurring(self, v: dict, tx_data: dict):
        """Crée une opération récurrente si la case correspondante a été cochée."""
        if not v.get("_create_recurring"):
            return
        r = v.get("_recurring") or {}
        rec = {
            "id":           str(uuid.uuid4()),
            "libelle":      tx_data.get("libelle", ""),
            "montant":      tx_data.get("montant", 0),
            "categorie":    tx_data.get("categorie", "Non classé"),
            "sous_cat":     tx_data.get("sous_cat", ""),
            "type":         tx_data.get("type", ""),
            "frequency":    r.get("frequency", "monthly"),
            "day_of_month": r.get("day_of_month", 1),
            "start_date":   r.get("start_date") or tx_data.get("date"),
            "end_date":     r.get("end_date"),
            "actif":        r.get("actif", 1),
        }
        self.db.insert_recurring(rec)
        freq_lbl = dict(FREQUENCIES).get(rec["frequency"], rec["frequency"])
        QMessageBox.information(self, "Opération récurrente",
            f"Récurrence créée : « {rec['libelle']} » — {freq_lbl}.\n"
            f"Visible dans l'onglet 🔮 Prévisionnel.")

    def _maybe_create_rule(self, v: dict):
        """Crée une règle si la case « Mémoriser » a été cochée."""
        if not v.get("_create_rule"):
            return
        r = v.get("_rule") or {}
        pattern = (r.get("pattern") or "").strip()
        if len(pattern) < 2:
            QMessageBox.warning(self, "Règle",
                "Motif trop court : la règle n'a pas été créée.")
            return
        # Si une règle au même motif (et même filtre montant) existe : on met à jour
        amt = r.get("amount")
        existing = None
        for rr in self.db.list_rules():
            if (rr["pattern"].lower() == pattern.lower()
                    and ((rr["amount"] is None and amt is None)
                         or (rr["amount"] is not None and amt is not None
                             and abs(rr["amount"] - amt) < 0.005))):
                existing = dict(rr); break
        # La règle hérite du sens de l'opération d'origine : une dépense crée
        # une règle « débit seulement » (un futur remboursement du même
        # commerçant ne sera donc pas reclassé en dépense), et inversement.
        m = v.get("montant")
        rule_data = {
            "pattern":      pattern,
            "amount":       amt,
            "sens":         "" if m is None else ("credit" if m > 0 else "debit"),
            "categorie":    v.get("categorie", ""),
            "sous_cat":     v.get("sous_cat", ""),
            "no_overwrite": r.get("no_overwrite", 0),
        }
        if existing:
            self.db.update_rule(existing["id"], rule_data)
            QMessageBox.information(self, "Règle",
                f"Règle existante mise à jour pour « {pattern} » → {v.get('categorie')}.")
        else:
            rule_data["id"] = str(uuid.uuid4())
            rule_data["created_at"] = date.today().isoformat()
            self.db.insert_rule(rule_data)
            QMessageBox.information(self, "Règle",
                f"Nouvelle règle créée : « {pattern} » → {v.get('categorie')}.")
        # Appliquer la règle à toutes les opérations correspondantes
        rules = [dict(r) for r in self.db.list_rules()]
        txs = [dict(r) for r in self.db.list_tx()]
        modified = 0
        for tx in txs:
            ok, fields = apply_rules_to_tx(tx, rules)
            if ok and (fields.get("categorie") != tx.get("categorie")
                       or fields.get("sous_cat") != tx.get("sous_cat")):
                self.db.update_tx(tx["id"], fields)
                modified += 1
        if modified:
            self.lbl_count.setText(f"{modified} opération(s) recatégorisée(s) par la règle.")

    def add_tx(self):
        cats = sorted(set(t.get("categorie") for t in self.transactions if t.get("categorie")))
        dlg = TxDialog(self, None, cats, self.transactions)
        if dlg.exec() != QDialog.Accepted:
            return
        v = dlg.values()
        if not v["libelle"]:
            QMessageBox.warning(self, "Saisie", "Le libellé est obligatoire.")
            return
        if abs(v["montant"]) < 0.005:
            QMessageBox.warning(self, "Saisie", "Le montant doit être supérieur à zéro.")
            return
        # Préserver les champs règle pour _maybe_create_rule
        rule_request = v.get("_create_rule")
        rule_info = v.get("_rule")
        v_db = {k: v[k] for k in v if not k.startswith("_")}
        v_db["id"] = str(uuid.uuid4())
        v_db["libelle_op"] = v_db["libelle"]
        v_db["reference"] = ""
        self.db.insert_tx(v_db)
        # Création éventuelle de règle
        self._maybe_create_rule({"_create_rule": rule_request, "_rule": rule_info,
                                 "categorie": v_db.get("categorie"),
                                 "sous_cat": v_db.get("sous_cat"),
                                 "montant": v_db.get("montant")})
        # Création éventuelle d'une opération récurrente
        self._maybe_create_recurring(
            {"_create_recurring": v.get("_create_recurring"),
             "_recurring": v.get("_recurring")}, v_db)
        self.reload_from_db()
        self.tx_changed.emit()

    def edit_selected(self):
        tx_id = self.selected_tx_id()
        if not tx_id:
            return
        tx = next((t for t in self.transactions if t["id"] == tx_id), None)
        if not tx:
            return
        cats = sorted(set(t.get("categorie") for t in self.transactions if t.get("categorie")))
        dlg = TxDialog(self, tx, cats, self.transactions)
        if dlg.exec() != QDialog.Accepted:
            return
        v = dlg.values()
        rule_request = v.get("_create_rule")
        rule_info = v.get("_rule")
        v_db = {k: v[k] for k in v if not k.startswith("_")}
        self.db.update_tx(tx_id, v_db)
        self._maybe_create_rule({"_create_rule": rule_request, "_rule": rule_info,
                                 "categorie": v_db.get("categorie"),
                                 "sous_cat": v_db.get("sous_cat"),
                                 "montant": v_db.get("montant")})
        self._maybe_create_recurring(
            {"_create_recurring": v.get("_create_recurring"),
             "_recurring": v.get("_recurring")}, v_db)
        self.reload_from_db()
        self.tx_changed.emit()

    def delete_selected(self):
        tx_id = self.selected_tx_id()
        if not tx_id:
            return
        if QMessageBox.question(self, "Supprimer",
                                "Supprimer cette opération ?") != QMessageBox.Yes:
            return
        self.db.delete_tx(tx_id)
        self.reload_from_db()
        self.tx_changed.emit()
