"""Vue Sous-catégories (tri, fusion, renommage)."""

import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QColor, QStandardItemModel, QStandardItem, QBrush,
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QComboBox, QTableView, QAbstractItemView,
    QMessageBox, QInputDialog,
)

from ...utils import (
    deaccent, cat_color, fmt_euro,
)
from ...database import Database

class SubcategoriesView(QWidget):
    """Gestion des sous-catégories utilisées dans les opérations.

    - Tri alphabétique par défaut, filtrage par catégorie parente et recherche.
    - Renommage / fusion (1 ou plusieurs lignes → un seul libellé).
    - Suppression (vidage du champ sous-catégorie sur les opérations choisies).
    - Nettoyage automatique des variantes proches (casse, accents, espaces).
    """

    sub_changed = Signal()

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db

        v = QVBoxLayout(self); v.setContentsMargins(8, 8, 8, 8)

        help_lbl = QLabel(
            "Tri, fusion et nettoyage des sous-catégories. Sélectionnez "
            "une ou plusieurs lignes pour les renommer, les fusionner ou les vider."
        )
        help_lbl.setWordWrap(True)
        help_lbl.setStyleSheet(
            "background:#FFF9E6; border:1px solid #E6D38A; "
            "border-radius:4px; padding:6px 8px; color:#5B4900;"
        )
        v.addWidget(help_lbl)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Catégorie :"))
        self.cat_filter = QComboBox()
        self.cat_filter.setMinimumWidth(200)
        self.cat_filter.currentTextChanged.connect(lambda _t: self._render())
        filter_row.addWidget(self.cat_filter)

        filter_row.addSpacing(12)
        filter_row.addWidget(QLabel("Recherche :"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filtrer par nom…")
        self.search.setMaximumWidth(220)
        self.search.textChanged.connect(lambda _t: self._render())
        filter_row.addWidget(self.search)

        filter_row.addStretch()

        self.btn_clean = QPushButton("🧹 Nettoyer les doublons proches…")
        self.btn_clean.setToolTip(
            "Détecte les variantes (casse, accents, espaces) au sein d'une même "
            "catégorie et propose une forme unique pour chaque groupe."
        )
        self.btn_clean.clicked.connect(self._clean_duplicates)
        filter_row.addWidget(self.btn_clean)
        v.addLayout(filter_row)

        self.model = QStandardItemModel(0, 4, self)
        self.model.setHorizontalHeaderLabels(
            ["Sous-catégorie", "Catégorie", "Nb opérations", "Total"]
        )
        self.model.setSortRole(Qt.UserRole + 1)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(lambda _i: self._rename_or_merge())
        v.addWidget(self.table, 1)

        action_row = QHBoxLayout()
        self.lbl_count = QLabel("")
        self.lbl_count.setStyleSheet("color:#666")
        action_row.addWidget(self.lbl_count)
        action_row.addStretch()

        self.btn_rename = QPushButton("✏️ Renommer / Fusionner…")
        self.btn_rename.setToolTip(
            "Renomme la sous-catégorie sélectionnée. Si plusieurs lignes sont "
            "cochées ou si le nouveau nom existe déjà, les opérations sont "
            "fusionnées sous un seul libellé."
        )
        self.btn_rename.clicked.connect(self._rename_or_merge)
        action_row.addWidget(self.btn_rename)

        self.btn_clear = QPushButton("🗑️ Supprimer (vider)")
        self.btn_clear.setToolTip(
            "Vide la sous-catégorie sur les opérations concernées. Les "
            "opérations elles-mêmes ne sont pas supprimées."
        )
        self.btn_clear.clicked.connect(self._clear_subcat)
        action_row.addWidget(self.btn_clear)
        v.addLayout(action_row)

        # Index courant : { (cat, sub): [tx_id, ...] }
        self._index: dict[tuple[str, str], list[str]] = {}
        # Totaux par paire : { (cat, sub): float }
        self._totals: dict[tuple[str, str], float] = {}
        # Catégories rencontrées (pour le filtre)
        self._cats_seen: list[str] = []

    # ──────────────────────────────────────────────────────────────────
    def refresh(self):
        self._index.clear()
        self._totals.clear()
        cats_seen: set[str] = set()
        for r in self.db.list_tx():
            d = dict(r)
            cat = (d.get("categorie") or "").strip() or "Non classé"
            sub = (d.get("sous_cat") or "").strip()
            cats_seen.add(cat)
            if not sub:
                continue
            key = (cat, sub)
            self._index.setdefault(key, []).append(d["id"])
            self._totals[key] = self._totals.get(key, 0.0) + float(d.get("montant", 0))
        self._cats_seen = sorted(cats_seen)

        current_filter = self.cat_filter.currentText()
        self.cat_filter.blockSignals(True)
        self.cat_filter.clear()
        self.cat_filter.addItem("— Toutes —")
        for c in self._cats_seen:
            self.cat_filter.addItem(c)
        idx = self.cat_filter.findText(current_filter)
        self.cat_filter.setCurrentIndex(idx if idx >= 0 else 0)
        self.cat_filter.blockSignals(False)

        self._render()

    def _render(self):
        f_cat = self.cat_filter.currentText().strip()
        if f_cat in ("", "— Toutes —"):
            f_cat = None
        f_text = deaccent(self.search.text() or "")

        self.table.setSortingEnabled(False)
        self.model.setRowCount(0)

        rows = []
        for (cat, sub), tx_ids in self._index.items():
            if f_cat and cat != f_cat:
                continue
            if f_text and f_text not in deaccent(sub):
                continue
            rows.append((cat, sub, len(tx_ids), self._totals[(cat, sub)]))

        # Tri alphabétique par défaut (sous-catégorie puis catégorie)
        rows.sort(key=lambda r: (deaccent(r[1]), deaccent(r[0])))

        for cat, sub, n, total in rows:
            it_sub = QStandardItem(sub)
            it_sub.setData((cat, sub), Qt.UserRole)
            it_sub.setData(deaccent(sub), Qt.UserRole + 1)

            it_cat = QStandardItem(cat)
            it_cat.setForeground(QBrush(QColor(cat_color(cat))))
            it_cat.setData(deaccent(cat), Qt.UserRole + 1)

            it_n = QStandardItem(str(n))
            it_n.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_n.setData(n, Qt.UserRole + 1)

            it_t = QStandardItem(fmt_euro(total))
            it_t.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_t.setForeground(QBrush(QColor("#C0392B" if total < 0 else "#229954")))
            it_t.setData(total, Qt.UserRole + 1)

            self.model.appendRow([it_sub, it_cat, it_n, it_t])

        self.table.setSortingEnabled(True)
        self.table.setColumnWidth(0, 260)
        self.table.setColumnWidth(1, 200)
        self.table.setColumnWidth(2, 110)
        self.table.setColumnWidth(3, 130)

        total_tx = sum(len(ids) for ids in self._index.values())
        self.lbl_count.setText(
            f"{self.model.rowCount()} affichée(s) — "
            f"{len(self._index)} sous-catégorie(s) au total — "
            f"{total_tx} opération(s) concernée(s)"
        )

    # ──────────────────────────────────────────────────────────────────
    def _selected_keys(self) -> list[tuple[str, str]]:
        keys: list[tuple[str, str]] = []
        for idx in self.table.selectionModel().selectedRows(0):
            it = self.model.itemFromIndex(idx)
            if it is None:
                continue
            data = it.data(Qt.UserRole)
            if isinstance(data, tuple) and len(data) == 2:
                keys.append(data)
        return keys

    def _rename_or_merge(self):
        keys = self._selected_keys()
        if not keys:
            QMessageBox.information(
                self, "Sélection vide",
                "Sélectionnez au moins une sous-catégorie dans la liste."
            )
            return

        first_cat, first_sub = keys[0]
        if len(keys) == 1:
            title = "Renommer la sous-catégorie"
            prompt = (
                f"Renommer « {first_sub} » (catégorie « {first_cat} ») en :\n\n"
                "Si le nouveau nom existe déjà, les opérations sont fusionnées."
            )
        else:
            preview = ", ".join(f"« {s} »" for (_c, s) in keys[:6])
            if len(keys) > 6:
                preview += f", … (+{len(keys) - 6})"
            title = "Fusionner des sous-catégories"
            prompt = (
                f"Fusionner {len(keys)} sous-catégories ({preview}) "
                "sous un même libellé :"
            )

        new_name, ok = QInputDialog.getText(
            self, title, prompt, QLineEdit.Normal, first_sub
        )
        if not ok:
            return
        new_name = (new_name or "").strip()
        if not new_name:
            QMessageBox.warning(
                self, "Nom vide",
                "Pour vider une sous-catégorie, utilisez le bouton "
                "« 🗑️ Supprimer (vider) »."
            )
            return

        tx_ids: list[str] = []
        for k in keys:
            tx_ids.extend(self._index.get(k, []))
        tx_ids = list(dict.fromkeys(tx_ids))
        if not tx_ids:
            return

        if QMessageBox.question(
                self, "Confirmer",
                f"Appliquer le libellé « {new_name} » à "
                f"{len(tx_ids)} opération(s) ?"
        ) != QMessageBox.Yes:
            return

        with self.db.batch():
            for tx_id in tx_ids:
                self.db.update_tx(tx_id, {"sous_cat": new_name})
        self.refresh()
        self.sub_changed.emit()

    def _clear_subcat(self):
        keys = self._selected_keys()
        if not keys:
            QMessageBox.information(
                self, "Sélection vide",
                "Sélectionnez au moins une sous-catégorie à vider."
            )
            return
        tx_ids: list[str] = []
        for k in keys:
            tx_ids.extend(self._index.get(k, []))
        tx_ids = list(dict.fromkeys(tx_ids))
        if not tx_ids:
            return
        preview = ", ".join(f"« {s} »" for (_c, s) in keys[:6])
        if len(keys) > 6:
            preview += f", … (+{len(keys) - 6})"
        if QMessageBox.question(
                self, "Confirmer la suppression",
                f"Vider la sous-catégorie ({preview}) sur "
                f"{len(tx_ids)} opération(s) ?\n\n"
                "Les opérations ne sont pas supprimées : seul le champ "
                "« sous-catégorie » est mis à blanc."
        ) != QMessageBox.Yes:
            return
        with self.db.batch():
            for tx_id in tx_ids:
                self.db.update_tx(tx_id, {"sous_cat": ""})
        self.refresh()
        self.sub_changed.emit()

    def _clean_duplicates(self):
        """Détecte les variantes (casse / accents / espaces multiples) d'un
        même libellé au sein d'une même catégorie et propose la forme la
        plus utilisée comme cible."""
        groups: dict[tuple[str, str], list[tuple[str, int]]] = {}
        for (cat, sub), tx_ids in self._index.items():
            norm = deaccent(re.sub(r"\s+", " ", sub).strip())
            groups.setdefault((cat, norm), []).append((sub, len(tx_ids)))

        plans: list[tuple[str, str, list[tuple[str, int]]]] = []
        for (cat, _norm), variants in groups.items():
            if len({v for v, _ in variants}) < 2:
                continue
            # Cible = forme la plus utilisée ; à égalité, ordre alphabétique
            target = sorted(variants, key=lambda x: (-x[1], x[0]))[0][0]
            plans.append((cat, target, variants))

        if not plans:
            QMessageBox.information(
                self, "Rien à nettoyer",
                "Aucune variante détectée : vos sous-catégories sont déjà "
                "normalisées (casse, accents et espaces identiques)."
            )
            return

        lines: list[str] = []
        total_tx = 0
        for cat, target, variants in plans:
            for v, n in variants:
                if v == target:
                    continue
                lines.append(f"  • [{cat}] « {v} »  →  « {target} »   ({n} op.)")
                total_tx += n
        msg = (
            f"Le nettoyage normalisera {len(plans)} groupe(s) de variantes, "
            f"affectant {total_tx} opération(s) :\n\n"
            + "\n".join(lines[:30])
            + ("\n  …" if len(lines) > 30 else "")
            + "\n\nAppliquer ces changements ?"
        )
        if QMessageBox.question(self, "Nettoyer les doublons", msg) != QMessageBox.Yes:
            return

        n_updated = 0
        with self.db.batch():
            for cat, target, variants in plans:
                for v, _n in variants:
                    if v == target:
                        continue
                    for tx_id in self._index.get((cat, v), []):
                        self.db.update_tx(tx_id, {"sous_cat": target})
                        n_updated += 1
        QMessageBox.information(
            self, "Nettoyage terminé",
            f"{n_updated} opération(s) mise(s) à jour."
        )
        self.refresh()
        self.sub_changed.emit()
