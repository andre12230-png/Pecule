"""Dialogues assistants (harmonisation, pré-remplissage)."""


from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor, QStandardItemModel, QStandardItem, QBrush,
)
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTableView, QAbstractItemView,
    QComboBox, QDialog,
)

from ..constants import (
    FREQUENCIES,
)
from ..utils import (
    cat_color, fmt_euro, fmt_date_fr, period_label,
)

class HarmonizeDialog(QDialog):
    """Affiche un aperçu des changements suggérés et applique sur sélection."""

    def __init__(self, parent, suggestions: list[tuple[dict, str]]):
        super().__init__(parent)
        self.setWindowTitle("Harmoniser les catégories")
        self.resize(720, 480)
        self.suggestions = suggestions

        v = QVBoxLayout(self)
        info = QLabel(
            "💡 Analyse des libellés. Décochez les lignes que vous ne souhaitez pas modifier, "
            "puis cliquez « Appliquer »."
        )
        info.setWordWrap(True)
        info.setStyleSheet("padding:8px; background:#FFFBE6; border:1px solid #E8D77B")
        v.addWidget(info)

        self.model = QStandardItemModel(0, 5, self)
        self.model.setHorizontalHeaderLabels(
            ["✓", "Date", "Libellé", "Catégorie actuelle", "→ Suggérée"])
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        for i, w in enumerate([34, 90, 280, 160, 160]):
            self.table.setColumnWidth(i, w)
        # On utilise un clic pour basculer la check
        self.table.clicked.connect(self._toggle)
        v.addWidget(self.table)

        for tx, suggested in suggestions:
            it_check = QStandardItem("✔")
            it_check.setData(True, Qt.UserRole + 1)
            it_check.setTextAlignment(Qt.AlignCenter)
            it_check.setForeground(QBrush(QColor("#1A7A3A")))
            row = [
                it_check,
                QStandardItem(fmt_date_fr(tx["date"])),
                QStandardItem(tx.get("libelle", "")),
                QStandardItem(tx.get("categorie", "")),
                QStandardItem(suggested),
            ]
            row[3].setForeground(QBrush(QColor(cat_color(tx.get("categorie", "")))))
            row[4].setForeground(QBrush(QColor(cat_color(suggested))))
            row[0].setData(tx["id"], Qt.UserRole)
            self.model.appendRow(row)

        btn_row = QHBoxLayout()
        self.lbl_summary = QLabel(f"{len(suggestions)} suggestion(s)")
        btn_row.addWidget(self.lbl_summary)
        btn_row.addStretch()
        self.btn_none = QPushButton("Tout décocher")
        self.btn_none.clicked.connect(lambda: self._set_all(False))
        btn_row.addWidget(self.btn_none)
        self.btn_all = QPushButton("Tout cocher")
        self.btn_all.clicked.connect(lambda: self._set_all(True))
        btn_row.addWidget(self.btn_all)
        self.btn_apply = QPushButton("✓ Appliquer")
        self.btn_apply.setDefault(True)
        self.btn_apply.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_apply)
        self.btn_cancel = QPushButton("Annuler")
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)
        v.addLayout(btn_row)

    def _toggle(self, index):
        if index.column() != 0:
            return
        it = self.model.item(index.row(), 0)
        checked = not bool(it.data(Qt.UserRole + 1))
        it.setData(checked, Qt.UserRole + 1)
        it.setText("✔" if checked else "")

    def _set_all(self, val: bool):
        for r in range(self.model.rowCount()):
            it = self.model.item(r, 0)
            it.setData(val, Qt.UserRole + 1)
            it.setText("✔" if val else "")

    def selected(self) -> list[tuple[str, str]]:
        """Retourne la liste (tx_id, new_cat) des lignes cochées."""
        out = []
        for r in range(self.model.rowCount()):
            it = self.model.item(r, 0)
            if it.data(Qt.UserRole + 1):
                out.append((it.data(Qt.UserRole),
                            self.model.item(r, 4).text()))
        return out


# ─────────────────────────────────────────────────────────────────────────────
# Dialogue de vérification des doublons avant suppression
# ─────────────────────────────────────────────────────────────────────────────

class DuplicatesDialog(QDialog):
    """Aperçu à cocher des doublons potentiels AVANT toute suppression.

    Chaque ligne est une COPIE détectée (la première occurrence, conservée,
    n'apparaît pas). Attention : deux opérations réellement identiques le
    même jour (ex. deux achats identiques chez le même commerçant) sont
    aussi détectées — c'est à l'utilisateur de les décocher."""

    def __init__(self, parent, dups: list[dict]):
        super().__init__(parent)
        self.setWindowTitle("Doublons potentiels")
        self.resize(760, 480)

        v = QVBoxLayout(self)
        info = QLabel(
            "⚠️ Les lignes cochées seront <b>supprimées</b>. Même date, même "
            "montant et même libellé ne garantissent pas un doublon : deux "
            "achats identiques le même jour sont légitimes — décochez-les "
            "avant de valider."
        )
        info.setWordWrap(True)
        info.setStyleSheet("padding:8px; background:#FDEDEB; border:1px solid #E74C3C")
        v.addWidget(info)

        self.model = QStandardItemModel(0, 5, self)
        self.model.setHorizontalHeaderLabels(
            ["✓", "Date", "Libellé", "Montant", "Catégorie"])
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        for i, w in enumerate([34, 90, 300, 110, 160]):
            self.table.setColumnWidth(i, w)
        self.table.clicked.connect(self._toggle)
        v.addWidget(self.table)

        for t in dups:
            it_check = QStandardItem("✔")
            it_check.setData(True, Qt.UserRole + 1)
            it_check.setData(t["id"], Qt.UserRole)
            it_check.setTextAlignment(Qt.AlignCenter)
            it_check.setForeground(QBrush(QColor("#C0392B")))

            it_montant = QStandardItem(fmt_euro(t.get("montant", 0)))
            it_montant.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_montant.setForeground(
                QBrush(QColor("#C0392B" if t.get("montant", 0) < 0 else "#229954")))

            it_cat = QStandardItem(t.get("categorie", ""))
            it_cat.setForeground(QBrush(QColor(cat_color(t.get("categorie", "")))))

            self.model.appendRow([
                it_check,
                QStandardItem(fmt_date_fr(t.get("date", ""))),
                QStandardItem(t.get("libelle", "")),
                it_montant,
                it_cat,
            ])

        btn_row = QHBoxLayout()
        self.lbl_summary = QLabel()
        btn_row.addWidget(self.lbl_summary)
        btn_row.addStretch()
        self.btn_none = QPushButton("Tout décocher")
        self.btn_none.clicked.connect(lambda: self._set_all(False))
        btn_row.addWidget(self.btn_none)
        self.btn_all = QPushButton("Tout cocher")
        self.btn_all.clicked.connect(lambda: self._set_all(True))
        btn_row.addWidget(self.btn_all)
        self.btn_apply = QPushButton("🗑 Supprimer la sélection")
        self.btn_apply.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_apply)
        self.btn_cancel = QPushButton("Annuler")
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)
        # Entrée ne doit PAS déclencher la suppression par accident :
        # aucun bouton par défaut, il faut cliquer.
        for b in (self.btn_none, self.btn_all, self.btn_apply, self.btn_cancel):
            b.setAutoDefault(False); b.setDefault(False)
        v.addLayout(btn_row)

        self._update_summary()

    def _toggle(self, index):
        if index.column() != 0:
            return
        it = self.model.item(index.row(), 0)
        checked = not bool(it.data(Qt.UserRole + 1))
        it.setData(checked, Qt.UserRole + 1)
        it.setText("✔" if checked else "")
        self._update_summary()

    def _set_all(self, val: bool):
        for r in range(self.model.rowCount()):
            it = self.model.item(r, 0)
            it.setData(val, Qt.UserRole + 1)
            it.setText("✔" if val else "")
        self._update_summary()

    def _update_summary(self):
        n = sum(1 for r in range(self.model.rowCount())
                if self.model.item(r, 0).data(Qt.UserRole + 1))
        self.lbl_summary.setText(
            f"{n} à supprimer sur {self.model.rowCount()} détectée(s)")

    def selected(self) -> list[str]:
        """Ids des opérations cochées (à supprimer)."""
        return [self.model.item(r, 0).data(Qt.UserRole)
                for r in range(self.model.rowCount())
                if self.model.item(r, 0).data(Qt.UserRole + 1)]


# ─────────────────────────────────────────────────────────────────────────────
# Dialogue de pré-remplissage du prévisionnel depuis l'historique
# ─────────────────────────────────────────────────────────────────────────────

class PrefillRecurringDialog(QDialog):
    """Aperçu à cocher des opérations récurrentes détectées dans l'historique.

    Les candidats stables (montant régulier, fréquence mensuelle ou plus) sont
    pré-cochés ; les autres (montant variable, virements internes…) sont
    affichés mais décochés. L'utilisateur ajuste avant d'insérer."""

    FREQ_LBL = dict(FREQUENCIES)

    def __init__(self, parent, candidates: list[dict]):
        super().__init__(parent)
        self.setWindowTitle("Pré-remplir le prévisionnel depuis l'historique")
        self.resize(900, 560)
        self.candidates = candidates

        v = QVBoxLayout(self)
        info = QLabel(
            "💡 Opérations récurrentes détectées dans vos opérations passées. "
            "Les lignes au montant régulier sont pré-cochées. Décochez celles "
            "à ignorer, puis cliquez « Ajouter au prévisionnel ». "
            "Le montant affiché est la médiane observée."
        )
        info.setWordWrap(True)
        info.setStyleSheet("padding:8px; background:#FFFBE6; border:1px solid #E8D77B")
        v.addWidget(info)

        self.model = QStandardItemModel(0, 8, self)
        self.model.setHorizontalHeaderLabels(
            ["✓", "Libellé", "Catégorie", "Montant médian",
             "Fréquence", "Jour", "Nb mois", "Fourchette"])
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.clicked.connect(self._toggle)
        for i, w in enumerate([34, 230, 170, 110, 110, 50, 60, 130]):
            self.table.setColumnWidth(i, w)
        v.addWidget(self.table)

        for c in candidates:
            checked = bool(c["_default"])
            it_check = QStandardItem("✔" if checked else "")
            it_check.setData(checked, Qt.UserRole + 1)
            it_check.setData(c, Qt.UserRole)
            it_check.setTextAlignment(Qt.AlignCenter)
            it_check.setForeground(QBrush(QColor("#1A7A3A")))

            it_montant = QStandardItem(fmt_euro(c["montant"]))
            it_montant.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_montant.setForeground(
                QBrush(QColor("#C0392B" if c["montant"] < 0 else "#229954")))

            it_cat = QStandardItem(c["categorie"])
            it_cat.setForeground(QBrush(QColor(cat_color(c["categorie"]))))

            it_range = QStandardItem(f"{fmt_euro(c['_min'])} … {fmt_euro(c['_max'])}")
            it_range.setForeground(QBrush(QColor("#888")))
            if not c["_stable"]:
                it_range.setForeground(QBrush(QColor("#C77B00")))

            it_nb = QStandardItem(str(c["_months"]))
            it_nb.setTextAlignment(Qt.AlignCenter)
            it_jour = QStandardItem(str(c["day_of_month"]))
            it_jour.setTextAlignment(Qt.AlignCenter)

            self.model.appendRow([
                it_check,
                QStandardItem(c["libelle"]),
                it_cat,
                it_montant,
                QStandardItem(self.FREQ_LBL.get(c["frequency"], c["frequency"])),
                it_jour,
                it_nb,
                it_range,
            ])

        btn_row = QHBoxLayout()
        self.lbl_summary = QLabel()
        btn_row.addWidget(self.lbl_summary)
        btn_row.addStretch()
        self.btn_none = QPushButton("Tout décocher")
        self.btn_none.clicked.connect(lambda: self._set_all(False))
        btn_row.addWidget(self.btn_none)
        self.btn_all = QPushButton("Tout cocher")
        self.btn_all.clicked.connect(lambda: self._set_all(True))
        btn_row.addWidget(self.btn_all)
        self.btn_apply = QPushButton("✓ Ajouter au prévisionnel")
        self.btn_apply.setDefault(True)
        self.btn_apply.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_apply)
        self.btn_cancel = QPushButton("Annuler")
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)
        v.addLayout(btn_row)

        self._update_summary()

    def _toggle(self, index):
        if index.column() != 0:
            return
        it = self.model.item(index.row(), 0)
        checked = not bool(it.data(Qt.UserRole + 1))
        it.setData(checked, Qt.UserRole + 1)
        it.setText("✔" if checked else "")
        self._update_summary()

    def _set_all(self, val: bool):
        for r in range(self.model.rowCount()):
            it = self.model.item(r, 0)
            it.setData(val, Qt.UserRole + 1)
            it.setText("✔" if val else "")
        self._update_summary()

    def _update_summary(self):
        n = sum(1 for r in range(self.model.rowCount())
                if self.model.item(r, 0).data(Qt.UserRole + 1))
        self.lbl_summary.setText(
            f"{n} sélectionnée(s) sur {self.model.rowCount()} détectée(s)")

    def selected(self) -> list[dict]:
        """Liste des candidats cochés (dicts de détection)."""
        out = []
        for r in range(self.model.rowCount()):
            it = self.model.item(r, 0)
            if it.data(Qt.UserRole + 1):
                out.append(it.data(Qt.UserRole))
        return out


# ─────────────────────────────────────────────────────────────────────────────
# Dialogue de génération des échéances d'un mois
# ─────────────────────────────────────────────────────────────────────────────

class GenererEcheancesDialog(QDialog):
    """Aperçu à cocher de ce qui doit être débité (ou encaissé) dans le mois.

    Même principe que la feuille mensuelle du classeur Budget : on aligne
    d'avance toutes les échéances attendues, et on les pointe au fur et à
    mesure qu'elles passent en banque. Les lignes auxquelles une opération
    correspond déjà sont affichées en gris et ne sont pas re-créables."""

    VERROU = Qt.UserRole + 2      # ligne non cochable (déjà enregistrée)

    def __init__(self, parent, calc, mois_iso: str, choix_mois: list[str]):
        """`calc(mois_iso)` retourne les échéances du mois (cf.
        recurring.echeances_du_mois) ; `choix_mois` liste les mois proposés
        au format « AAAA-MM »."""
        super().__init__(parent)
        self.setWindowTitle("Générer les échéances du mois")
        self.resize(880, 580)
        self._calc = calc

        v = QVBoxLayout(self)
        info = QLabel(
            "💡 Échéances attendues d'après le <b>Prévisionnel</b>. Elles seront "
            "créées en opérations <b>non pointées</b> : visibles dans la liste et "
            "dans « ce qui est prévu », mais sans effet sur le solde en banque "
            "tant qu'elles ne sont pas pointées. Les lignes grisées correspondent "
            "à une opération déjà enregistrée : elles ne seront pas recréées."
        )
        info.setWordWrap(True)
        info.setStyleSheet("padding:8px; background:#FFFBE6; border:1px solid #E8D77B")
        v.addWidget(info)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Mois :"))
        self.mois_combo = QComboBox()
        for m in choix_mois:
            self.mois_combo.addItem(period_label(m), m)
        idx = self.mois_combo.findData(mois_iso)
        if idx >= 0:
            self.mois_combo.setCurrentIndex(idx)
        self.mois_combo.currentIndexChanged.connect(self._remplir)
        bar.addWidget(self.mois_combo)
        bar.addStretch()
        v.addLayout(bar)

        self.model = QStandardItemModel(0, 6, self)
        self.model.setHorizontalHeaderLabels(
            ["✓", "Date prévue", "Libellé", "Montant", "Catégorie", "État"])
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.clicked.connect(self._toggle)
        for i, w in enumerate([34, 100, 260, 110, 170, 180]):
            self.table.setColumnWidth(i, w)
        v.addWidget(self.table)

        btn_row = QHBoxLayout()
        self.lbl_summary = QLabel()
        btn_row.addWidget(self.lbl_summary)
        btn_row.addStretch()
        self.btn_none = QPushButton("Tout décocher")
        self.btn_none.clicked.connect(lambda: self._set_all(False))
        btn_row.addWidget(self.btn_none)
        self.btn_all = QPushButton("Tout cocher")
        self.btn_all.clicked.connect(lambda: self._set_all(True))
        btn_row.addWidget(self.btn_all)
        self.btn_apply = QPushButton("✓ Créer les opérations")
        self.btn_apply.setDefault(True)
        self.btn_apply.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_apply)
        self.btn_cancel = QPushButton("Annuler")
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)
        v.addLayout(btn_row)

        self._remplir()

    # ── Remplissage ────────────────────────────────────────────────
    def mois(self) -> str:
        return self.mois_combo.currentData()

    def _remplir(self):
        self.model.setRowCount(0)
        for e in self._calc(self.mois()):
            verrou = bool(e["_deja"])
            checked = bool(e["_default"])

            it_check = QStandardItem("✔" if checked else "")
            it_check.setData(checked, Qt.UserRole + 1)
            it_check.setData(e, Qt.UserRole)
            it_check.setData(verrou, self.VERROU)
            it_check.setTextAlignment(Qt.AlignCenter)
            it_check.setForeground(QBrush(QColor("#1A7A3A")))

            it_montant = QStandardItem(fmt_euro(e["montant"]))
            it_montant.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_montant.setForeground(
                QBrush(QColor("#C0392B" if e["montant"] < 0 else "#229954")))

            it_cat = QStandardItem(e["categorie"])
            it_cat.setForeground(QBrush(QColor(cat_color(e["categorie"]))))

            if verrou:
                etat, couleur = "✔ déjà enregistrée", "#888"
            elif e["_passee"]:
                etat, couleur = "⚠ date déjà passée", "#C77B00"
            else:
                etat, couleur = "à créer", "#1A7A3A"
            it_etat = QStandardItem(etat)
            it_etat.setForeground(QBrush(QColor(couleur)))

            row = [
                it_check,
                QStandardItem(fmt_date_fr(e["date"])),
                QStandardItem(e["libelle"]),
                it_montant,
                it_cat,
                it_etat,
            ]
            if verrou:
                # Ligne informative : elle montre que l'échéance est couverte,
                # mais il n'y a rien à faire dessus.
                for it in row:
                    it.setForeground(QBrush(QColor("#999")))
            self.model.appendRow(row)
        self._update_summary()

    # ── Cases à cocher ─────────────────────────────────────────────
    def _toggle(self, index):
        if index.column() != 0:
            return
        it = self.model.item(index.row(), 0)
        if it.data(self.VERROU):
            return
        checked = not bool(it.data(Qt.UserRole + 1))
        it.setData(checked, Qt.UserRole + 1)
        it.setText("✔" if checked else "")
        self._update_summary()

    def _set_all(self, val: bool):
        for r in range(self.model.rowCount()):
            it = self.model.item(r, 0)
            if it.data(self.VERROU):
                continue
            it.setData(val, Qt.UserRole + 1)
            it.setText("✔" if val else "")
        self._update_summary()

    def _update_summary(self):
        choisies = self.selected()
        sorties = sum(e["montant"] for e in choisies if e["montant"] < 0)
        entrees = sum(e["montant"] for e in choisies if e["montant"] > 0)
        deja = sum(1 for r in range(self.model.rowCount())
                   if self.model.item(r, 0).data(self.VERROU))
        txt = (f"{len(choisies)} opération(s) à créer sur "
               f"{self.model.rowCount()} échéance(s) du mois")
        if deja:
            txt += f" ({deja} déjà enregistrée(s))"
        if choisies:
            txt += (f"  —  à débiter : {fmt_euro(sorties)}"
                    f"  •  à encaisser : {fmt_euro(entrees)}")
        self.lbl_summary.setText(txt)

    def selected(self) -> list[dict]:
        """Échéances cochées (dicts issus de echeances_du_mois)."""
        return [self.model.item(r, 0).data(Qt.UserRole)
                for r in range(self.model.rowCount())
                if self.model.item(r, 0).data(Qt.UserRole + 1)
                and not self.model.item(r, 0).data(self.VERROU)]


# ─────────────────────────────────────────────────────────────────────────────
# Dialogue d'harmonisation des libellés
# ─────────────────────────────────────────────────────────────────────────────

class HarmonizeLabelsDialog(QDialog):
    """Aperçu à cocher des libellés à harmoniser. La colonne « Harmonisé »
    est modifiable : double-cliquez pour ajuster une cible (ex. fusionner
    « E Marche » et « Centre Marche » sous « Marche »)."""

    def __init__(self, parent, rows: list[dict]):
        super().__init__(parent)
        self.setWindowTitle("Harmoniser les libellés")
        self.resize(820, 560)

        v = QVBoxLayout(self)
        info = QLabel(
            "💡 Libellés proposés à la normalisation (casse, numéros de magasin "
            "et références retirés). Les variantes d'un même commerçant sont "
            "fusionnées. La colonne « Harmonisé » est <b>modifiable</b> : "
            "double-cliquez pour corriger ou regrouper manuellement. "
            "Décochez ce que vous ne voulez pas changer."
        )
        info.setWordWrap(True)
        info.setStyleSheet("padding:8px; background:#FFFBE6; border:1px solid #E8D77B")
        v.addWidget(info)

        self.model = QStandardItemModel(0, 4, self)
        self.model.setHorizontalHeaderLabels(
            ["✓", "Libellé actuel", "Nb", "→ Harmonisé (modifiable)"])
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setEditTriggers(
            QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.clicked.connect(self._toggle)
        for i, w in enumerate([34, 330, 50, 360]):
            self.table.setColumnWidth(i, w)
        v.addWidget(self.table)

        for row in rows:
            it_check = QStandardItem("✔")
            it_check.setData(True, Qt.UserRole + 1)
            it_check.setData(row, Qt.UserRole)
            it_check.setTextAlignment(Qt.AlignCenter)
            it_check.setForeground(QBrush(QColor("#1A7A3A")))
            it_check.setEditable(False)

            it_old = QStandardItem(row["old"])
            it_old.setEditable(False)
            it_old.setForeground(QBrush(QColor("#888")))

            it_n = QStandardItem(str(row["n"]))
            it_n.setTextAlignment(Qt.AlignCenter)
            it_n.setEditable(False)

            it_new = QStandardItem(row["new"])
            it_new.setEditable(True)
            f = it_new.font(); f.setBold(True); it_new.setFont(f)

            self.model.appendRow([it_check, it_old, it_n, it_new])

        btn_row = QHBoxLayout()
        self.lbl_summary = QLabel()
        btn_row.addWidget(self.lbl_summary)
        btn_row.addStretch()
        self.btn_none = QPushButton("Tout décocher")
        self.btn_none.clicked.connect(lambda: self._set_all(False))
        btn_row.addWidget(self.btn_none)
        self.btn_all = QPushButton("Tout cocher")
        self.btn_all.clicked.connect(lambda: self._set_all(True))
        btn_row.addWidget(self.btn_all)
        self.btn_apply = QPushButton("✓ Appliquer")
        self.btn_apply.setDefault(True)
        self.btn_apply.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_apply)
        self.btn_cancel = QPushButton("Annuler")
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)
        v.addLayout(btn_row)

        self._update_summary()

    def _toggle(self, index):
        if index.column() != 0:
            return
        it = self.model.item(index.row(), 0)
        checked = not bool(it.data(Qt.UserRole + 1))
        it.setData(checked, Qt.UserRole + 1)
        it.setText("✔" if checked else "")
        self._update_summary()

    def _set_all(self, val: bool):
        for r in range(self.model.rowCount()):
            it = self.model.item(r, 0)
            it.setData(val, Qt.UserRole + 1)
            it.setText("✔" if val else "")
        self._update_summary()

    def _update_summary(self):
        n = sum(1 for r in range(self.model.rowCount())
                if self.model.item(r, 0).data(Qt.UserRole + 1))
        self.lbl_summary.setText(
            f"{n} libellé(s) à harmoniser sur {self.model.rowCount()}")

    def selected(self) -> list[dict]:
        """Lignes cochées avec la cible éventuellement éditée :
        liste de dicts {old, new, tx_ids, rec_ids}."""
        out = []
        for r in range(self.model.rowCount()):
            it = self.model.item(r, 0)
            if not it.data(Qt.UserRole + 1):
                continue
            row = dict(it.data(Qt.UserRole))
            new_text = self.model.item(r, 3).text().strip()
            if not new_text or new_text == row["old"]:
                continue
            row["new"] = new_text
            out.append(row)
        return out
