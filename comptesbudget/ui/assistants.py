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
from ..accords import accorde, nombre, pluriel
from ..utils import (
    fmt_euro, fmt_date_fr, period_label,
)
from .models import (
    case_a_cocher, cellule_categorie, cocher_tout, colonnes_sans_coupure,
    est_cochee,
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
        v.addWidget(self.table)

        for tx, suggested in suggestions:
            it_check = case_a_cocher(True)
            it_check.setTextAlignment(Qt.AlignCenter)
            it_check.setForeground(QBrush(QColor("#18733A")))
            row = [
                it_check,
                QStandardItem(fmt_date_fr(tx["date"])),
                QStandardItem(tx.get("libelle", "")),
                cellule_categorie(tx.get("categorie", "")),
                cellule_categorie(suggested),
            ]
            row[0].setData(tx["id"], Qt.UserRole)
            self.model.appendRow(row)

        btn_row = QHBoxLayout()
        self.lbl_summary = QLabel(pluriel(len(suggestions), "suggestion"))
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

    def _set_all(self, val: bool):
        cocher_tout(self.model, val)

    def selected(self) -> list[tuple[str, str]]:
        """Retourne la liste (tx_id, new_cat) des lignes cochées."""
        out = []
        for r in range(self.model.rowCount()):
            it = self.model.item(r, 0)
            if est_cochee(it):
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
        # Vraies cases : Qt les coche au clic et à la barre d'espace.
        self.model.itemChanged.connect(lambda *_: self._update_summary())
        v.addWidget(self.table)

        for t in dups:
            it_check = case_a_cocher(True)
            it_check.setData(t["id"], Qt.UserRole)
            it_check.setTextAlignment(Qt.AlignCenter)
            it_check.setForeground(QBrush(QColor("#C0392B")))

            it_montant = QStandardItem(fmt_euro(t.get("montant", 0)))
            it_montant.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_montant.setForeground(
                QBrush(QColor("#C0392B" if t.get("montant", 0) < 0 else "#18733A")))

            it_cat = cellule_categorie(t.get("categorie", ""))

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

    def _set_all(self, val: bool):
        cocher_tout(self.model, val)

    def _update_summary(self):
        n = sum(1 for r in range(self.model.rowCount())
                if est_cochee(self.model.item(r, 0)))
        total = self.model.rowCount()
        self.lbl_summary.setText(
            f"{nombre(n)} à supprimer sur {nombre(total)} "
            f"{accorde(total, 'détectée')}")

    def selected(self) -> list[str]:
        """Ids des opérations cochées (à supprimer)."""
        return [self.model.item(r, 0).data(Qt.UserRole)
                for r in range(self.model.rowCount())
                if est_cochee(self.model.item(r, 0))]


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
        # 1 000 px : la fourchette entière (« 2 380,00 € … 2 380,00 € ») et
        # un libellé lisible tiennent côte à côte.
        self.resize(1000, 560)
        self.candidates = candidates

        v = QVBoxLayout(self)
        info = QLabel(
            "💡 Opérations qui reviennent dans vos opérations passées et "
            "passent encore aujourd'hui. Celles qui reviennent à date et à "
            "montant réguliers sont pré-cochées. Décochez celles à ignorer, "
            "puis cliquez « Ajouter au prévisionnel ». Le montant et le jour "
            "sont ceux des derniers passages."
        )
        info.setWordWrap(True)
        info.setStyleSheet("padding:8px; background:#FFFBE6; border:1px solid #E8D77B")
        v.addWidget(info)

        self.model = QStandardItemModel(0, 8, self)
        self.model.setHorizontalHeaderLabels(
            ["✓", "Libellé", "Catégorie", "Montant",
             "Fréquence", "Jour", "Nb mois", "Fourchette"])
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        # Vraies cases : Qt les coche au clic et à la barre d'espace.
        self.model.itemChanged.connect(lambda *_: self._update_summary())
        # Chiffres et fréquence à la largeur de leur contenu, le libellé prend
        # le reste : la fourchette était coupée à 900 px.
        colonnes_sans_coupure(self.table, au_contenu=(3, 4, 5, 6, 7),
                              etirable=1, largeurs={0: 34, 2: 190})
        v.addWidget(self.table)

        for c in candidates:
            checked = bool(c["_default"])
            it_check = case_a_cocher(checked)
            it_check.setData(c, Qt.UserRole)
            it_check.setTextAlignment(Qt.AlignCenter)
            it_check.setForeground(QBrush(QColor("#18733A")))

            it_montant = QStandardItem(fmt_euro(c["montant"]))
            it_montant.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_montant.setForeground(
                QBrush(QColor("#C0392B" if c["montant"] < 0 else "#18733A")))

            it_cat = cellule_categorie(c["categorie"])

            it_range = QStandardItem(f"{fmt_euro(c['_min'])} … {fmt_euro(c['_max'])}")
            it_range.setForeground(QBrush(QColor("#5A5A5A")))
            if not c["_stable"]:
                it_range.setForeground(QBrush(QColor("#7E5109")))

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

    def _set_all(self, val: bool):
        cocher_tout(self.model, val)

    def _update_summary(self):
        n = sum(1 for r in range(self.model.rowCount())
                if est_cochee(self.model.item(r, 0)))
        total = self.model.rowCount()
        self.lbl_summary.setText(
            f"{nombre(n)} {accorde(n, 'sélectionnée', 'sélectionnées')} sur "
            f"{nombre(total)} {accorde(total, 'détectée', 'détectées')}")

    def selected(self) -> list[dict]:
        """Liste des candidats cochés (dicts de détection)."""
        out = []
        for r in range(self.model.rowCount()):
            it = self.model.item(r, 0)
            if est_cochee(it):
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
        # Vraies cases : Qt les coche au clic et à la barre d'espace.
        self.model.itemChanged.connect(lambda *_: self._update_summary())
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

            # Déjà enregistrée : case grisée, qu'on ne peut pas cocher.
            it_check = case_a_cocher(checked, verrouillee=verrou)
            it_check.setData(e, Qt.UserRole)
            it_check.setData(verrou, self.VERROU)
            it_check.setTextAlignment(Qt.AlignCenter)
            it_check.setForeground(QBrush(QColor("#18733A")))

            it_montant = QStandardItem(fmt_euro(e["montant"]))
            it_montant.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_montant.setForeground(
                QBrush(QColor("#C0392B" if e["montant"] < 0 else "#18733A")))

            it_cat = cellule_categorie(e["categorie"])

            if verrou:
                etat, couleur = "✔ déjà enregistrée", "#5A5A5A"
            elif e["_passee"]:
                etat, couleur = "⚠ date déjà passée", "#7E5109"
            else:
                etat, couleur = "à créer", "#18733A"
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
                    it.setForeground(QBrush(QColor("#5A5A5A")))
            self.model.appendRow(row)
        self._update_summary()

    # ── Cases à cocher ─────────────────────────────────────────────
    def _set_all(self, val: bool):
        cocher_tout(self.model, val)

    def _update_summary(self):
        choisies = self.selected()
        sorties = sum(e["montant"] for e in choisies if e["montant"] < 0)
        entrees = sum(e["montant"] for e in choisies if e["montant"] > 0)
        deja = sum(1 for r in range(self.model.rowCount())
                   if self.model.item(r, 0).data(self.VERROU))
        txt = (f"{pluriel(len(choisies), 'opération', 'opérations')} à créer sur "
               f"{pluriel(self.model.rowCount(), 'échéance', 'échéances')} du mois")
        if deja:
            txt += f" ({nombre(deja)} déjà {accorde(deja, 'enregistrée', 'enregistrées')})"
        if choisies:
            txt += (f"  —  sorties : {fmt_euro(sorties)}"
                    f"  ·  entrées : {fmt_euro(entrees)}")
        self.lbl_summary.setText(txt)

    def selected(self) -> list[dict]:
        """Échéances cochées (dicts issus de echeances_du_mois)."""
        return [self.model.item(r, 0).data(Qt.UserRole)
                for r in range(self.model.rowCount())
                if est_cochee(self.model.item(r, 0))
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
        # Vraies cases : Qt les coche au clic et à la barre d'espace.
        self.model.itemChanged.connect(lambda *_: self._update_summary())
        for i, w in enumerate([34, 330, 50, 360]):
            self.table.setColumnWidth(i, w)
        v.addWidget(self.table)

        for row in rows:
            it_check = case_a_cocher(True)
            it_check.setData(row, Qt.UserRole)
            it_check.setTextAlignment(Qt.AlignCenter)
            it_check.setForeground(QBrush(QColor("#18733A")))
            it_check.setEditable(False)

            it_old = QStandardItem(row["old"])
            it_old.setEditable(False)
            it_old.setForeground(QBrush(QColor("#5A5A5A")))

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

    def _set_all(self, val: bool):
        cocher_tout(self.model, val)

    def _update_summary(self):
        n = sum(1 for r in range(self.model.rowCount())
                if est_cochee(self.model.item(r, 0)))
        self.lbl_summary.setText(
            pluriel(n, "libellé", "libellés") + f" à harmoniser sur {self.model.rowCount()}")

    def selected(self) -> list[dict]:
        """Lignes cochées avec la cible éventuellement éditée :
        liste de dicts {old, new, tx_ids, rec_ids}."""
        out = []
        for r in range(self.model.rowCount()):
            it = self.model.item(r, 0)
            if not est_cochee(it):
                continue
            row = dict(it.data(Qt.UserRole))
            new_text = self.model.item(r, 3).text().strip()
            if not new_text or new_text == row["old"]:
                continue
            row["new"] = new_text
            out.append(row)
        return out
