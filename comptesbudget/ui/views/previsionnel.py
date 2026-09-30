"""Vue Prévisionnel (opérations récurrentes)."""

import uuid
from calendar import monthrange
from datetime import date
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
from ...accords import accorde, pluriel
from ...utils import (
    carte_a_debit_differe, est_paiement_carte, fmt_euro,
    fmt_date_fr, period_label, regle_debit_differe,
)
from ...database import Database
from ...recurring import (
    generate_occurrences, detect_recurring_candidates, echeances_du_mois,
    candidats_non_couverts, _recurring_aligned_start,
)

from ..models import SORT_ROLE, cellule_categorie
from ..dialogs import LIBELLE_RECURRENCE_MANQUANT, RecurringDialog
from ..assistants import GenererEcheancesDialog, PrefillRecurringDialog
from ..widgets import confirmer

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
            ["Libellé", "Montant", "Catégorie", "Type", "Fréquence", "Période", "Actif"])
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
        # Tri de départ : de la plus proche échéance à la plus lointaine.
        # L'indicateur de Qt est décroissant par défaut : la liste commençait
        # dans un an. Un tri choisi ensuite d'un clic sur l'en-tête est gardé.
        self.forecast_table.horizontalHeader().setSortIndicator(0, Qt.AscendingOrder)
        self.forecast_table.setSortingEnabled(True)
        self.forecast_table.horizontalHeader().setSortIndicatorShown(True)
        blay.addWidget(self.forecast_table)

        self.summary = QLabel("")
        self.summary.setStyleSheet("padding:6px; background:#FFFBE6; border:1px solid #E8D77B")
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
                cellule_categorie(r["categorie"]),
                QStandardItem(r["type"] or ""),
                QStandardItem(freq_lbl.get(r["frequency"], r["frequency"])),
                # « du … au … » plutôt qu'une flèche (charte, 30/09/2026).
                QStandardItem(
                    f"du {fmt_date_fr(r['start_date'])} au {fmt_date_fr(r['end_date'])}"
                    if r["end_date"] else f"depuis le {fmt_date_fr(r['start_date'])}"),
                QStandardItem("✔" if r["actif"] else ""),
            ]
            row[1].setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row[1].setForeground(QBrush(QColor("#C0392B" if r["montant"] < 0 else "#18733A")))
            row[6].setTextAlignment(Qt.AlignCenter)
            tris = [r["libelle"].lower(), r["montant"], r["categorie"].lower(),
                    (r["type"] or "").lower(), r["frequency"], r["start_date"],
                    1 if r["actif"] else 0]
            for it, tri in zip(row, tris):
                it.setData(r["id"], Qt.UserRole)
                it.setData(tri, SORT_ROLE)
            self.model.appendRow(row)

        self.table.setSortingEnabled(True)

        # Prévisions : la fin du mois en cours, puis 12 mois pleins. Le calcul
        # s'arrêtait à la fin du mois PRÉCÉDENT l'an prochain (le 31/08/2027
        # un 23/09/2026) : il manquait presque un mois (audit du 23/09/2026).
        auj = date.today()
        until = date(auj.year + 1, auj.month,
                     monthrange(auj.year + 1, auj.month)[1])
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
                cellule_categorie(r["categorie"]),
            ]
            row[2].setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row[2].setForeground(QBrush(QColor("#C0392B" if r["montant"] < 0 else "#18733A")))
            for it, tri in zip(row, [d.isoformat(), r["libelle"].lower(),
                                     r["montant"], r["categorie"].lower()]):
                it.setData(tri, SORT_ROLE)
            self.forecast_model.appendRow(row)

        self.forecast_table.setSortingEnabled(True)

        n = len(events)
        self.summary.setText(
            f"📊 {pluriel(n, 'occurrence', 'occurrences')} "
            f"{accorde(n, 'prévue', 'prévues')} jusqu'au {fmt_date_fr(until.isoformat())}  —  "
            f"Recettes : {fmt_euro(total_pos)}  •  Dépenses : {fmt_euro(total_neg)}  •  "
            f"Net : {fmt_euro(total_pos + total_neg)}"
        )

    def _selected_id(self) -> Optional[str]:
        idx = self.table.currentIndex()
        if not idx.isValid():
            return None
        return self.model.item(idx.row(), 0).data(Qt.UserRole)

    def _new(self):
        cats = self.db.categories_proposees()
        all_tx = [dict(r) for r in self.db.list_tx()]
        dlg = RecurringDialog(self, None, cats, all_tx)
        if dlg.exec() != QDialog.Accepted:
            return
        v = dlg.values()
        if not v["libelle"]:
            QMessageBox.warning(self, "Libellé manquant", LIBELLE_RECURRENCE_MANQUANT)
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
        cats = self.db.categories_proposees()
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
        rec = next((dict(r) for r in self.db.list_recurring() if r["id"] == rid), None)
        if not rec:
            return
        if not confirmer(
                self, "Supprimer l'opération récurrente",
                f"Supprimer l'opération récurrente « {rec['libelle']} » "
                f"({fmt_euro(rec['montant'])}) ?\n\n"
                "Elle disparaît du prévisionnel. Les opérations déjà "
                "enregistrées ne sont pas touchées.",
                action="Supprimer", garder="Garder", danger=True):
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
        # Seule une carte à DÉBIT DIFFÉRÉ reporte l'échéance ; sur une carte à
        # débit immédiat, elle sort le jour même (même règle que le Bilan).
        txs = [dict(r) for r in self.db.list_tx()]
        differe = carte_a_debit_differe(txs)
        dater_carte = regle_debit_differe(txs)
        with self.db.batch():
            for e in echeances:
                # Une échéance payée par carte à débit différé n'atteint le
                # compte qu'au prélèvement groupé du mois suivant
                # (cf. date_debit_differe).
                est_carte = differe and est_paiement_carte(e["type"])
                self.db.insert_tx({
                    "id":          str(uuid.uuid4()),
                    "date":        e["date"],
                    "date_valeur": dater_carte(e["date"]) if est_carte
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
            f"{pluriel(n, 'opération', 'opérations')} "
            f"{accorde(n, 'créée', 'créées')} pour {period_label(mois_iso)}, "
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

        # Évite de re-proposer ce qui existe déjà, y compris sous un ancien
        # nom (même montant, même jour) : cf. incident du 23/09/2026.
        candidates = candidats_non_couverts(
            candidates, [dict(r) for r in self.db.list_recurring()])

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
            f"{pluriel(n, 'opération', 'opérations')} "
            f"{accorde(n, 'récurrente', 'récurrentes')} "
            f"{accorde(n, 'ajoutée', 'ajoutées')} au prévisionnel.")
        self.refresh()
        self.changed.emit()
