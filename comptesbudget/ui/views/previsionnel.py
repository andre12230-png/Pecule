"""Vue Prévisionnel (opérations récurrentes)."""

import uuid
from datetime import date, timedelta
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QColor, QStandardItemModel, QStandardItem, QBrush,
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTableView, QAbstractItemView,
    QDialog, QMessageBox, QSplitter,
)

from ...constants import (
    FREQUENCIES,
)
from ...utils import (
    cat_color, fmt_euro, fmt_date_fr, date_debit_differe, period_label,
)
from ...database import Database
from ...recurring import (
    generate_occurrences, detect_recurring_candidates, echeances_du_mois,
    _recurring_norm_label, _recurring_aligned_start,
)

from ..models import SORT_ROLE
from ..dialogs import RecurringDialog
from ..assistants import GenererEcheancesDialog, PrefillRecurringDialog

class PrevisionnelView(QWidget):
    changed = Signal()

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        v = QVBoxLayout(self); v.setContentsMargins(8, 8, 8, 8)

        toolbar = QHBoxLayout()
        self.btn_new = QPushButton("➕ Nouvelle opération récurrente")
        self.btn_new.clicked.connect(self._new)
        toolbar.addWidget(self.btn_new)
        self.btn_edit = QPushButton("✏️ Modifier")
        self.btn_edit.clicked.connect(self._edit)
        toolbar.addWidget(self.btn_edit)
        self.btn_del = QPushButton("🗑 Supprimer")
        self.btn_del.clicked.connect(self._delete)
        toolbar.addWidget(self.btn_del)
        toolbar.addStretch()
        self.btn_mois = QPushButton("📅 Générer les échéances du mois")
        self.btn_mois.setToolTip(
            "Crée en une fois, dans les opérations, tout ce qui doit être "
            "débité ou encaissé pendant le mois — en non pointé, à pointer "
            "au fur et à mesure des passages en banque.")
        self.btn_mois.clicked.connect(self._generer_mois)
        toolbar.addWidget(self.btn_mois)
        self.btn_prefill = QPushButton("✨ Pré-remplir depuis l'historique")
        self.btn_prefill.setToolTip(
            "Détecte les opérations récurrentes dans vos opérations passées "
            "et propose de les ajouter au prévisionnel.")
        self.btn_prefill.clicked.connect(self._prefill)
        toolbar.addWidget(self.btn_prefill)
        v.addLayout(toolbar)

        splitter = QSplitter(Qt.Vertical)

        # Tableau des récurrents
        top = QWidget(); tlay = QVBoxLayout(top); tlay.setContentsMargins(0, 0, 0, 0)
        tlay.addWidget(QLabel("Opérations récurrentes définies :"))
        self.model = QStandardItemModel(0, 7, self)
        self.model.setHorizontalHeaderLabels(
            ["Libellé", "Montant", "Catégorie", "Type", "Fréquence", "Début → fin", "Actif"])
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self._edit)
        for i, w in enumerate([240, 110, 180, 140, 120, 180, 60]):
            self.table.setColumnWidth(i, w)
        self.model.setSortRole(SORT_ROLE)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        tlay.addWidget(self.table)
        splitter.addWidget(top)

        # Prévisions sur les 12 prochains mois
        bot = QWidget(); blay = QVBoxLayout(bot); blay.setContentsMargins(0, 0, 0, 0)
        blay.addWidget(QLabel("Prévisions des 12 prochains mois :"))
        self.forecast_model = QStandardItemModel(0, 4, self)
        self.forecast_model.setHorizontalHeaderLabels(
            ["Date prévue", "Libellé", "Montant", "Catégorie"])
        self.forecast_table = QTableView()
        self.forecast_table.setModel(self.forecast_model)
        self.forecast_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.forecast_table.verticalHeader().setVisible(False)
        self.forecast_table.setAlternatingRowColors(True)
        for i, w in enumerate([100, 280, 110, 180]):
            self.forecast_table.setColumnWidth(i, w)
        self.forecast_model.setSortRole(SORT_ROLE)
        self.forecast_table.setSortingEnabled(True)
        self.forecast_table.horizontalHeader().setSortIndicatorShown(True)
        blay.addWidget(self.forecast_table)

        self.summary = QLabel("")
        self.summary.setStyleSheet("padding:6px; background:#FFF7E6; border:1px solid #E8C77B")
        blay.addWidget(self.summary)

        splitter.addWidget(bot)
        splitter.setSizes([300, 400])
        v.addWidget(splitter)

    def refresh(self):
        recs = [dict(r) for r in self.db.list_recurring()]
        freq_lbl = dict(FREQUENCIES)

        self.table.setSortingEnabled(False)
        self.model.setRowCount(0)
        for r in recs:
            row = [
                QStandardItem(r["libelle"]),
                QStandardItem(fmt_euro(r["montant"])),
                QStandardItem(r["categorie"]),
                QStandardItem(r["type"] or ""),
                QStandardItem(freq_lbl.get(r["frequency"], r["frequency"])),
                QStandardItem(f"{fmt_date_fr(r['start_date'])} → {fmt_date_fr(r['end_date']) if r['end_date'] else '…'}"),
                QStandardItem("✔" if r["actif"] else ""),
            ]
            row[1].setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row[1].setForeground(QBrush(QColor("#C0392B" if r["montant"] < 0 else "#229954")))
            row[2].setForeground(QBrush(QColor(cat_color(r["categorie"]))))
            row[6].setTextAlignment(Qt.AlignCenter)
            tris = [r["libelle"].lower(), r["montant"], r["categorie"].lower(),
                    (r["type"] or "").lower(), r["frequency"], r["start_date"],
                    1 if r["actif"] else 0]
            for it, tri in zip(row, tris):
                it.setData(r["id"], Qt.UserRole)
                it.setData(tri, SORT_ROLE)
            self.model.appendRow(row)

        self.table.setSortingEnabled(True)

        # Forecast : 12 mois à venir
        until = date.today().replace(day=1)
        until = date(until.year + 1, until.month, until.day) - timedelta(days=1)
        events: list[tuple[date, dict]] = []
        for r in recs:
            if not r["actif"]:
                continue
            for d in generate_occurrences(r, until):
                if d >= date.today():
                    events.append((d, r))
        events.sort(key=lambda x: x[0])

        self.forecast_table.setSortingEnabled(False)
        self.forecast_model.setRowCount(0)
        total_pos = total_neg = 0.0
        for d, r in events:
            total_pos += r["montant"] if r["montant"] > 0 else 0
            total_neg += r["montant"] if r["montant"] < 0 else 0
            row = [
                QStandardItem(fmt_date_fr(d.isoformat())),
                QStandardItem(r["libelle"]),
                QStandardItem(fmt_euro(r["montant"])),
                QStandardItem(r["categorie"]),
            ]
            row[2].setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row[2].setForeground(QBrush(QColor("#C0392B" if r["montant"] < 0 else "#229954")))
            row[3].setForeground(QBrush(QColor(cat_color(r["categorie"]))))
            for it, tri in zip(row, [d.isoformat(), r["libelle"].lower(),
                                     r["montant"], r["categorie"].lower()]):
                it.setData(tri, SORT_ROLE)
            self.forecast_model.appendRow(row)

        self.forecast_table.setSortingEnabled(True)

        self.summary.setText(
            f"📊 {len(events)} occurrence(s) prévue(s) jusqu'au {fmt_date_fr(until.isoformat())}  —  "
            f"Recettes : {fmt_euro(total_pos)}  •  Dépenses : {fmt_euro(total_neg)}  •  "
            f"Net : {fmt_euro(total_pos + total_neg)}"
        )

    def _selected_id(self) -> Optional[str]:
        idx = self.table.currentIndex()
        if not idx.isValid():
            return None
        return self.model.item(idx.row(), 0).data(Qt.UserRole)

    def _new(self):
        cats = self.db.all_categories_used()
        all_tx = [dict(r) for r in self.db.list_tx()]
        dlg = RecurringDialog(self, None, cats, all_tx)
        if dlg.exec() != QDialog.Accepted:
            return
        v = dlg.values()
        if not v["libelle"]:
            QMessageBox.warning(self, "Récurrent", "Le libellé est obligatoire.")
            return
        v["id"] = str(uuid.uuid4())
        self.db.insert_recurring(v)
        self.refresh()
        self.changed.emit()

    def _edit(self):
        rid = self._selected_id()
        if not rid:
            return
        row = next((dict(r) for r in self.db.list_recurring() if r["id"] == rid), None)
        if not row:
            return
        cats = self.db.all_categories_used()
        all_tx = [dict(r) for r in self.db.list_tx()]
        dlg = RecurringDialog(self, row, cats, all_tx)
        if dlg.exec() != QDialog.Accepted:
            return
        self.db.update_recurring(rid, dlg.values())
        self.refresh()
        self.changed.emit()

    def _delete(self):
        rid = self._selected_id()
        if not rid:
            return
        if QMessageBox.question(self, "Supprimer", "Supprimer cette opération récurrente ?") != QMessageBox.Yes:
            return
        self.db.delete_recurring(rid)
        self.refresh()
        self.changed.emit()

    # ── Génération des échéances d'un mois ──────────────────────────
    def _mois_proposes(self) -> list[str]:
        """Mois en cours et les deux suivants, au format « AAAA-MM »."""
        d = date.today().replace(day=1)
        out = []
        for _ in range(3):
            out.append(d.isoformat()[:7])
            d = date(d.year + 1, 1, 1) if d.month == 12 else date(d.year, d.month + 1, 1)
        return out

    def _echeances(self, mois_iso: str) -> list[dict]:
        """Échéances attendues pour un mois, relues à chaque fois : le
        dialogue doit refléter la base même si elle a changé entre-temps."""
        recs = [dict(r) for r in self.db.list_recurring()]
        txs = [dict(r) for r in self.db.list_tx()]
        return echeances_du_mois(recs, txs, int(mois_iso[:4]), int(mois_iso[5:7]))

    def _creer_operations(self, echeances: list[dict]) -> int:
        """Enregistre les échéances retenues en opérations NON pointées.

        Le drapeau « prevue » les distingue d'une opération réellement passée
        en banque : il permet de les afficher à part (⏳) et, à l'import du
        relevé, de les compléter au lieu d'ajouter une seconde ligne."""
        with self.db.batch():
            for e in echeances:
                # Une échéance payée par carte n'atteint le compte qu'au
                # prélèvement groupé du mois suivant (cf. date_debit_differe).
                est_carte = "carte" in (e["type"] or "").lower()
                self.db.insert_tx({
                    "id":          str(uuid.uuid4()),
                    "date":        e["date"],
                    "date_valeur": date_debit_differe(e["date"]) if est_carte
                                   else e["date"],
                    "libelle":     e["libelle"],
                    "libelle_op":  e["libelle"],
                    "reference":   "",
                    "type":        e["type"],
                    "categorie":   e["categorie"],
                    "sous_cat":    e["sous_cat"],
                    "info":        "",
                    "montant":     e["montant"],
                    "pointee":     0,
                    "prevue":      1,
                })
        return len(echeances)

    def _generer_mois(self):
        """Crée en opérations non pointées ce qui doit tomber dans le mois."""
        if not self.db.list_recurring():
            QMessageBox.information(
                self, "Échéances du mois",
                "Le prévisionnel est vide : définissez d'abord vos opérations "
                "récurrentes (ou utilisez « ✨ Pré-remplir depuis l'historique »).")
            return

        mois_courant = date.today().isoformat()[:7]
        dlg = GenererEcheancesDialog(
            self, self._echeances, mois_courant, self._mois_proposes())
        if dlg.exec() != QDialog.Accepted:
            return
        choisies = dlg.selected()
        mois_iso = dlg.mois()
        if not choisies:
            QMessageBox.information(
                self, "Échéances du mois",
                "Aucune échéance cochée : rien n'a été créé.")
            return

        n = self._creer_operations(choisies)

        QMessageBox.information(
            self, "Échéances du mois",
            f"{n} opération(s) créée(s) pour {period_label(mois_iso)}, "
            "en NON pointé : elles n'entrent pas dans le solde en banque.\n\n"
            "Retrouvez-les dans l'onglet 📋 Opérations, repérées par ⏳ "
            "(filtre « Échéances prévues »).\n\n"
            "Au prochain import de relevé, chacune sera complétée avec les "
            "informations réelles de la banque et pointée automatiquement — "
            "même si la date ou le montant ne tombent pas exactement juste.")
        self.refresh()
        self.changed.emit()

    def _prefill(self):
        """Détecte les récurrences dans l'historique et propose de les ajouter."""
        txs = [dict(r) for r in self.db.list_tx()]
        if not txs:
            QMessageBox.information(
                self, "Pré-remplir",
                "Aucune opération dans l'historique : importez d'abord un relevé.")
            return

        candidates = detect_recurring_candidates(txs)

        # Évite de re-proposer ce qui existe déjà (même libellé normalisé)
        existing = {_recurring_norm_label(r["libelle"])
                    for r in self.db.list_recurring()}
        candidates = [c for c in candidates
                      if _recurring_norm_label(c["libelle"]) not in existing]

        if not candidates:
            QMessageBox.information(
                self, "Pré-remplir",
                "Aucune nouvelle opération récurrente détectée "
                "(ou elles sont déjà toutes dans le prévisionnel).")
            return

        dlg = PrefillRecurringDialog(self, candidates)
        if dlg.exec() != QDialog.Accepted:
            return
        chosen = dlg.selected()
        if not chosen:
            return

        today = date.today()
        n = 0
        with self.db.batch():
            for c in chosen:
                rec = {
                    "id":           str(uuid.uuid4()),
                    "libelle":      c["libelle"],
                    "montant":      c["montant"],
                    "categorie":    c["categorie"],
                    "sous_cat":     c.get("sous_cat", ""),
                    "type":         c.get("type", ""),
                    "frequency":    c["frequency"],
                    "day_of_month": c["day_of_month"],
                    "start_date":   _recurring_aligned_start(
                                        c["frequency"], c["day_of_month"], today
                                    ).isoformat(),
                    "end_date":     None,
                    "actif":        1,
                }
                self.db.insert_recurring(rec)
                n += 1

        QMessageBox.information(
            self, "Pré-remplir",
            f"{n} opération(s) récurrente(s) ajoutée(s) au prévisionnel.")
        self.refresh()
        self.changed.emit()
