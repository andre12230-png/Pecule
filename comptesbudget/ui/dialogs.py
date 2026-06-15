"""Dialogues d'édition (transaction, réglages, règle, récurrence)."""

from typing import Optional

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout,
    QLabel, QLineEdit, QComboBox, QDialog, QFormLayout, QDateEdit, QDoubleSpinBox, QCheckBox,
    QDialogButtonBox, QFrame, QRadioButton, QSpinBox, QCompleter,
)

from ..constants import (
    CATEGORIES_DEFAUT, TYPES_OPERATION, FREQUENCIES,
)
from ..utils import (
    fmt_euro,
)
from ..labels import build_libelle_profiles

class TxDialog(QDialog):
    """Boîte de dialogue d'ajout / modification d'opération."""

    def __init__(self, parent=None, tx: Optional[dict] = None,
                 categories: list[str] = None,
                 all_transactions: list[dict] = None):
        super().__init__(parent)
        self.setWindowTitle("Modifier l'opération" if tx else "Nouvelle opération")
        self.tx = tx
        self.all_tx = all_transactions or []
        self.setMinimumWidth(480)

        layout = QFormLayout(self)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        layout.addRow("Date :", self.date_edit)

        self.date_val = QDateEdit()
        self.date_val.setCalendarPopup(True)
        self.date_val.setDisplayFormat("dd/MM/yyyy")
        layout.addRow("Date valeur :", self.date_val)

        sens_row = QHBoxLayout()
        self.rb_debit = QRadioButton("Débit (sortie)")
        self.rb_credit = QRadioButton("Crédit (entrée)")
        self.rb_debit.setChecked(True)
        sens_row.addWidget(self.rb_debit)
        sens_row.addWidget(self.rb_credit)
        sens_row.addStretch()
        sens_wrap = QWidget(); sens_wrap.setLayout(sens_row)
        layout.addRow("Sens :", sens_wrap)

        self.montant = QDoubleSpinBox()
        self.montant.setRange(0.0, 1_000_000.0)
        self.montant.setDecimals(2)
        self.montant.setSuffix(" €")
        self.montant.setSingleStep(1.0)
        layout.addRow("Montant :", self.montant)

        self.libelle = QLineEdit()
        self.libelle.setMaxLength(120)
        # Autocomplétion : propose les libellés déjà enregistrés.
        # Tri par fréquence décroissante puis alphabétique, recherche
        # insensible à la casse et par sous-chaîne (« contient »).
        lib_counts: dict[str, int] = {}
        for t in self.all_tx:
            lbl = (t.get("libelle") or "").strip()
            if lbl:
                lib_counts[lbl] = lib_counts.get(lbl, 0) + 1
        libelles = sorted(lib_counts, key=lambda l: (-lib_counts[l], l.lower()))
        self._lib_completer = QCompleter(libelles, self)
        self._lib_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._lib_completer.setFilterMode(Qt.MatchContains)
        self._lib_completer.setCompletionMode(QCompleter.PopupCompletion)
        self._lib_completer.setMaxVisibleItems(12)
        self.libelle.setCompleter(self._lib_completer)
        # Pré-remplissage intelligent : profil habituel par libellé
        self._lib_profiles = build_libelle_profiles(self.all_tx)
        self._lib_completer.activated[str].connect(self._apply_libelle_profile)
        layout.addRow("Libellé :", self.libelle)

        self.type_combo = QComboBox()
        self.type_combo.addItems(TYPES_OPERATION)
        layout.addRow("Type :", self.type_combo)

        self.cat = QComboBox()
        self.cat.setEditable(True)
        all_cats = sorted(set((categories or []) + CATEGORIES_DEFAUT))
        self.cat.addItems(all_cats)
        layout.addRow("Catégorie :", self.cat)

        # Sous-catégorie : combobox éditable avec autocomplétion
        # filtrée par la catégorie sélectionnée
        self.sous_cat = QComboBox()
        self.sous_cat.setEditable(True)
        self.sous_cat.lineEdit().setMaxLength(80)
        self.sous_cat.setInsertPolicy(QComboBox.NoInsert)  # pas d'ajout auto à la liste
        # Index { categorie: [sous_cats] } construit depuis toutes les transactions
        self._subcat_by_cat: dict[str, list[str]] = {}
        for t in self.all_tx:
            c = (t.get("categorie") or "").strip()
            sc = (t.get("sous_cat") or "").strip()
            if c and sc:
                self._subcat_by_cat.setdefault(c, [])
                if sc not in self._subcat_by_cat[c]:
                    self._subcat_by_cat[c].append(sc)
        # Liste complète (toutes catégories) pour fallback
        self._all_subcats = sorted({sc for lst in self._subcat_by_cat.values() for sc in lst})
        layout.addRow("Sous-catégorie :", self.sous_cat)

        # Mettre à jour la liste à chaque changement de catégorie
        self.cat.currentTextChanged.connect(self._update_subcat_list)
        self._update_subcat_list(self.cat.currentText())

        self.note = QLineEdit()
        self.note.setMaxLength(200)
        layout.addRow("Note :", self.note)

        self.pointee = QCheckBox("Pointée — vérifiée sur le relevé bancaire")
        layout.addRow("", self.pointee)

        # ── Section « Mémoriser » (création de règle inline) ──────────
        sep = QFrame(); sep.setFrameShape(QFrame.HLine); sep.setStyleSheet("color:#CCC")
        layout.addRow(sep)

        self.create_rule = QCheckBox("🧠 Mémoriser : créer une règle de catégorisation à partir de cette opération")
        layout.addRow("", self.create_rule)

        # Bloc qui apparaît quand « Mémoriser » est coché
        self.rule_pattern_lbl = QLabel("Motif :")
        self.rule_pattern = QLineEdit()
        self.rule_pattern.setPlaceholderText("Texte qui doit figurer dans le libellé (auto : le libellé entier)")
        self.rule_match_info = QLabel("")
        self.rule_match_info.setStyleSheet("color:#666; font-size:10pt")

        self.rule_use_amount = QCheckBox("🎯 Affiner par montant — ne s'applique qu'à ce montant exact")
        self.rule_no_overwrite = QCheckBox("🔒 Ne pas écraser les catégories déjà saisies")

        # Rangées (cachées par défaut)
        self._rule_rows = []
        for lbl, w in [
            (self.rule_pattern_lbl, self.rule_pattern),
            (QLabel(""), self.rule_match_info),
            (QLabel(""), self.rule_use_amount),
            (QLabel(""), self.rule_no_overwrite),
        ]:
            layout.addRow(lbl, w)
            self._rule_rows.append((lbl, w))
        self._set_rule_rows_visible(False)

        # Câblage
        self.create_rule.toggled.connect(self._on_create_rule_toggled)
        self.rule_pattern.textChanged.connect(self._update_match_info)
        self.rule_use_amount.toggled.connect(self._update_match_info)
        self.montant.valueChanged.connect(self._update_match_info)
        self.rb_credit.toggled.connect(self._update_match_info)
        self.libelle.textChanged.connect(self._maybe_update_pattern_default)
        self._pattern_user_edited = False
        self.rule_pattern.textEdited.connect(lambda _: setattr(self, "_pattern_user_edited", True))

        # ── Section « Opération récurrente » ─────────────────────────
        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine); sep2.setStyleSheet("color:#CCC")
        layout.addRow(sep2)

        self.create_recurring = QCheckBox(
            "🔮 Opération récurrente : générer automatiquement les prochaines occurrences")
        layout.addRow("", self.create_recurring)

        self.rec_freq_lbl = QLabel("Fréquence :")
        self.rec_freq = QComboBox()
        for code, label in FREQUENCIES:
            self.rec_freq.addItem(label, code)
        # Mensuelle par défaut
        idx_m = self.rec_freq.findData("monthly")
        if idx_m >= 0:
            self.rec_freq.setCurrentIndex(idx_m)

        self.rec_day_lbl = QLabel("Jour du mois :")
        self.rec_day = QSpinBox()
        self.rec_day.setRange(1, 31); self.rec_day.setValue(1)

        self.rec_end_lbl = QLabel("Date de fin :")
        self.rec_end = QDateEdit(); self.rec_end.setCalendarPopup(True)
        self.rec_end.setDisplayFormat("dd/MM/yyyy")
        self.rec_end.setSpecialValueText("(aucune)")
        self.rec_end.setMinimumDate(QDate(1900, 1, 1))
        self.rec_end.setDate(QDate(1900, 1, 1))

        self._rec_rows = []
        for lbl, w in [
            (self.rec_freq_lbl, self.rec_freq),
            (self.rec_day_lbl, self.rec_day),
            (self.rec_end_lbl, self.rec_end),
        ]:
            layout.addRow(lbl, w)
            self._rec_rows.append((lbl, w))
        self._set_rec_rows_visible(False)
        self.create_recurring.toggled.connect(self._on_create_rec_toggled)

        self.btns = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.btns.accepted.connect(self.accept)
        self.btns.rejected.connect(self.reject)
        layout.addRow(self.btns)

        # Pré-remplissage
        if tx:
            d = QDate.fromString(tx["date"], "yyyy-MM-dd")
            self.date_edit.setDate(d)
            dv = tx.get("date_valeur") or tx["date"]
            self.date_val.setDate(QDate.fromString(dv, "yyyy-MM-dd"))
            self.montant.setValue(abs(tx.get("montant", 0)))
            if tx.get("montant", 0) >= 0:
                self.rb_credit.setChecked(True)
            self.libelle.setText(tx.get("libelle", ""))
            idx = self.type_combo.findText(tx.get("type", ""))
            if idx >= 0:
                self.type_combo.setCurrentIndex(idx)
            self.cat.setCurrentText(tx.get("categorie", ""))
            self.sous_cat.setCurrentText(tx.get("sous_cat", ""))
            self.note.setText(tx.get("info", ""))
            self.pointee.setChecked(bool(tx.get("pointee")))
        else:
            self.date_edit.setDate(QDate.currentDate())
            self.date_val.setDate(QDate.currentDate())

        # Initialisation du motif par défaut = libellé
        self.rule_pattern.setText(self.libelle.text())

    def _update_subcat_list(self, categorie: str):
        """Repeuple la liste des sous-catégories proposées en fonction
        de la catégorie sélectionnée. Préserve la valeur saisie par l'utilisateur."""
        current_text = self.sous_cat.currentText()
        cat = (categorie or "").strip()
        items = list(self._subcat_by_cat.get(cat, []))
        items.sort()
        # Si la catégorie est inconnue, on propose toutes les sous-catégories
        if not items:
            items = list(self._all_subcats)
        self.sous_cat.blockSignals(True)
        self.sous_cat.clear()
        self.sous_cat.addItems(items)
        # Restaurer la saisie courante (texte libre permis)
        self.sous_cat.setCurrentText(current_text)
        self.sous_cat.blockSignals(False)

    def _apply_libelle_profile(self, libelle: str):
        """Quand un libellé connu est choisi dans l'autocomplétion, pré-remplit
        catégorie, sous-catégorie et type d'après l'historique, et le montant
        si aucun n'a encore été saisi."""
        prof = self._lib_profiles.get((libelle or "").strip())
        if not prof:
            return
        if prof["categorie"]:
            self.cat.setCurrentText(prof["categorie"])   # déclenche le filtre sous-cat
        if prof["sous_cat"]:
            self.sous_cat.setCurrentText(prof["sous_cat"])
        if prof["type"]:
            idx = self.type_combo.findText(prof["type"])
            if idx >= 0:
                self.type_combo.setCurrentIndex(idx)
        # Montant : seulement si l'utilisateur n'a rien saisi (toujours à 0)
        if self.montant.value() == 0 and prof["montant"]:
            self.montant.setValue(abs(prof["montant"]))
            (self.rb_credit if prof["montant"] >= 0 else self.rb_debit).setChecked(True)

    def _set_rule_rows_visible(self, visible: bool):
        for lbl, w in self._rule_rows:
            lbl.setVisible(visible)
            w.setVisible(visible)

    def _set_rec_rows_visible(self, visible: bool):
        for lbl, w in self._rec_rows:
            lbl.setVisible(visible)
            w.setVisible(visible)

    def _on_create_rec_toggled(self, checked: bool):
        self._set_rec_rows_visible(checked)
        if checked:
            # Pré-remplir le jour du mois avec celui de la date d'opération
            try:
                day = self.date_edit.date().day()
                self.rec_day.setValue(day)
            except Exception:
                pass
            self.adjustSize()

    def _on_create_rule_toggled(self, checked: bool):
        self._set_rule_rows_visible(checked)
        if checked:
            # Si l'utilisateur n'a pas modifié le motif, on le remet à jour
            if not self._pattern_user_edited:
                self.rule_pattern.setText(self.libelle.text())
            self._update_match_info()
            self.adjustSize()

    def _maybe_update_pattern_default(self, txt: str):
        if not self._pattern_user_edited:
            self.rule_pattern.setText(txt)

    def _update_match_info(self):
        if not self.create_rule.isChecked():
            self.rule_match_info.setText("")
            return
        pat = self.rule_pattern.text().strip().lower()
        if not pat:
            self.rule_match_info.setText("")
            return
        use_amt = self.rule_use_amount.isChecked()
        amt = self.montant.value() if use_amt else None
        want_credit = self.rb_credit.isChecked()   # la règle suivra ce sens

        matches = []
        for t in self.all_tx:
            lib = f"{t.get('libelle','')} {t.get('libelle_op','')} {t.get('reference','')}".lower()
            if pat not in lib:
                continue
            m_tx = t.get("montant", 0)
            if (m_tx > 0) != want_credit:
                continue
            if amt is not None and abs(abs(m_tx) - amt) > 0.005:
                continue
            matches.append(t)

        if not matches:
            self.rule_match_info.setText("Aucune autre opération ne correspond pour l'instant.")
            self.rule_match_info.setStyleSheet("color:#666; font-size:10pt")
            return

        suffix = f" au montant exact de {fmt_euro(amt)}" if amt is not None else ""
        cats = sorted({t.get("categorie", "") for t in matches})
        already_classed = [c for c in cats if c not in ("", "Non classé")]
        msg = f"{len(matches)} opération(s) correspondante(s){suffix}."
        if len(cats) > 1 and already_classed:
            msg += f" ⚠️ Catégories existantes : {', '.join(f'« {c} »' for c in already_classed)}."
            self.rule_match_info.setStyleSheet("color:#C0392B; font-size:10pt; font-weight:600")
        else:
            self.rule_match_info.setStyleSheet("color:#229954; font-size:10pt")
        self.rule_match_info.setText(msg)

    def values(self) -> dict:
        montant = self.montant.value()
        if self.rb_debit.isChecked():
            montant = -montant
        d = self.date_edit.date().toString("yyyy-MM-dd")
        dv = self.date_val.date().toString("yyyy-MM-dd")
        # Champs récurrent
        rec_end = self.rec_end.date()
        rec_end_str = rec_end.toString("yyyy-MM-dd") if rec_end > QDate(1900, 1, 1) else None
        return {
            "date":        d,
            "date_valeur": dv,
            "libelle":     self.libelle.text().strip(),
            "libelle_op":  self.libelle.text().strip(),
            "type":        self.type_combo.currentText(),
            "categorie":   self.cat.currentText().strip() or "Non classé",
            "sous_cat":    self.sous_cat.currentText().strip(),
            "info":        self.note.text().strip(),
            "montant":     montant,
            "pointee":     1 if self.pointee.isChecked() else 0,
            "_create_rule": self.create_rule.isChecked(),
            "_rule": {
                "pattern":      self.rule_pattern.text().strip() or self.libelle.text().strip(),
                "amount":       (self.montant.value() if self.rule_use_amount.isChecked() else None),
                "no_overwrite": 1 if self.rule_no_overwrite.isChecked() else 0,
            },
            "_create_recurring": self.create_recurring.isChecked(),
            "_recurring": {
                "frequency":    self.rec_freq.currentData(),
                "day_of_month": self.rec_day.value(),
                "start_date":   d,
                "end_date":     rec_end_str,
                "actif":        1,
            },
        }


# ─────────────────────────────────────────────────────────────────────────────
# Dialogue de paramètres (solde initial)
# ─────────────────────────────────────────────────────────────────────────────

class SettingsDialog(QDialog):
    def __init__(self, parent=None, initial_date: str = "2025-01-01",
                 initial_balance: float = 0.0):
        super().__init__(parent)
        self.setWindowTitle("Paramètres")
        self.setMinimumWidth(440)

        layout = QFormLayout(self)

        info = QLabel(
            "Le solde de départ est utilisé pour calculer le solde réel du compte.\n"
            "Indiquez le solde de votre relevé bancaire à la date choisie."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#555; padding:6px; background:#FFFBE6; border:1px solid #E8D77B")
        layout.addRow(info)

        self.initial_date = QDateEdit()
        self.initial_date.setCalendarPopup(True)
        self.initial_date.setDisplayFormat("dd/MM/yyyy")
        try:
            self.initial_date.setDate(QDate.fromString(initial_date, "yyyy-MM-dd"))
        except Exception:
            self.initial_date.setDate(QDate(2025, 1, 1))
        layout.addRow("Date de départ :", self.initial_date)

        self.initial_balance = QDoubleSpinBox()
        self.initial_balance.setRange(-1_000_000.0, 1_000_000.0)
        self.initial_balance.setDecimals(2)
        self.initial_balance.setSuffix(" €")
        self.initial_balance.setValue(initial_balance)
        layout.addRow("Solde de départ :", self.initial_balance)

        self.btns = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.btns.accepted.connect(self.accept)
        self.btns.rejected.connect(self.reject)
        layout.addRow(self.btns)

    def values(self) -> tuple[str, float]:
        return (self.initial_date.date().toString("yyyy-MM-dd"),
                self.initial_balance.value())


# ─────────────────────────────────────────────────────────────────────────────
# Dialogue d'édition d'une règle
# ─────────────────────────────────────────────────────────────────────────────

class RuleDialog(QDialog):
    """Création / modification d'une règle de catégorisation."""

    def __init__(self, parent=None, rule: Optional[dict] = None,
                 categories: list[str] = None):
        super().__init__(parent)
        self.setWindowTitle("Modifier la règle" if rule else "Nouvelle règle")
        self.rule = rule
        self.setMinimumWidth(420)

        layout = QFormLayout(self)

        self.pattern = QLineEdit()
        self.pattern.setPlaceholderText("Texte que le libellé doit contenir")
        layout.addRow("Motif :", self.pattern)

        # Filtre par montant
        self.use_amount = QCheckBox("🎯 Filtrer par montant exact")
        layout.addRow("", self.use_amount)

        self.amount = QDoubleSpinBox()
        self.amount.setRange(0.0, 1_000_000.0)
        self.amount.setDecimals(2)
        self.amount.setSuffix(" €")
        self.amount.setEnabled(False)
        layout.addRow("Montant :", self.amount)
        self.use_amount.toggled.connect(self.amount.setEnabled)

        # Sens : ne matcher que les débits, que les crédits, ou les deux.
        self.sens = QComboBox()
        self.sens.addItem("Débit uniquement (dépenses)", "debit")
        self.sens.addItem("Crédit uniquement (entrées, remboursements)", "credit")
        self.sens.addItem("Débit et crédit (les deux)", "")
        layout.addRow("Sens :", self.sens)

        self.cat = QComboBox()
        self.cat.setEditable(True)
        all_cats = sorted(set((categories or []) + CATEGORIES_DEFAUT))
        self.cat.addItems(all_cats)
        layout.addRow("Catégorie :", self.cat)

        self.sous_cat = QLineEdit()
        layout.addRow("Sous-catégorie :", self.sous_cat)

        self.no_overwrite = QCheckBox("🔒 Ne pas remplacer la catégorie si déjà classée")
        layout.addRow("", self.no_overwrite)

        self.lbl_info = QLabel("")
        self.lbl_info.setStyleSheet("color:#666; font-size:10pt")
        layout.addRow("", self.lbl_info)

        self.btns = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.btns.accepted.connect(self.accept)
        self.btns.rejected.connect(self.reject)
        layout.addRow(self.btns)

        if rule:
            self.pattern.setText(rule.get("pattern", ""))
            if rule.get("amount") is not None:
                self.use_amount.setChecked(True)
                self.amount.setValue(rule["amount"])
            idx = self.sens.findData(rule.get("sens") or "")
            if idx >= 0:
                self.sens.setCurrentIndex(idx)
            self.cat.setCurrentText(rule.get("categorie", ""))
            self.sous_cat.setText(rule.get("sous_cat", ""))
            self.no_overwrite.setChecked(bool(rule.get("no_overwrite")))

    def values(self) -> dict:
        return {
            "pattern":      self.pattern.text().strip(),
            "amount":       self.amount.value() if self.use_amount.isChecked() else None,
            "sens":         self.sens.currentData(),
            "categorie":    self.cat.currentText().strip(),
            "sous_cat":     self.sous_cat.text().strip(),
            "no_overwrite": 1 if self.no_overwrite.isChecked() else 0,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Dialogue d'opération récurrente
# ─────────────────────────────────────────────────────────────────────────────


class RecurringDialog(QDialog):
    def __init__(self, parent=None, rec: Optional[dict] = None,
                 categories: list[str] = None, all_tx: list[dict] = None):
        super().__init__(parent)
        self.setWindowTitle("Modifier l'opération récurrente" if rec else "Nouvelle opération récurrente")
        self.setMinimumWidth(440)
        self.all_tx = all_tx or []

        layout = QFormLayout(self)

        self.libelle = QLineEdit()
        # Autocomplétion + pré-remplissage à partir des opérations passées
        lib_counts: dict[str, int] = {}
        for t in self.all_tx:
            lbl = (t.get("libelle") or "").strip()
            if lbl:
                lib_counts[lbl] = lib_counts.get(lbl, 0) + 1
        libelles = sorted(lib_counts, key=lambda l: (-lib_counts[l], l.lower()))
        self._lib_completer = QCompleter(libelles, self)
        self._lib_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._lib_completer.setFilterMode(Qt.MatchContains)
        self._lib_completer.setCompletionMode(QCompleter.PopupCompletion)
        self._lib_completer.setMaxVisibleItems(12)
        self.libelle.setCompleter(self._lib_completer)
        self._lib_profiles = build_libelle_profiles(self.all_tx)
        self._lib_completer.activated[str].connect(self._apply_libelle_profile)
        layout.addRow("Libellé :", self.libelle)

        sens_row = QHBoxLayout()
        self.rb_debit = QRadioButton("Débit")
        self.rb_credit = QRadioButton("Crédit")
        self.rb_debit.setChecked(True)
        sens_row.addWidget(self.rb_debit); sens_row.addWidget(self.rb_credit); sens_row.addStretch()
        sens_wrap = QWidget(); sens_wrap.setLayout(sens_row)
        layout.addRow("Sens :", sens_wrap)

        self.montant = QDoubleSpinBox()
        self.montant.setRange(0.0, 1_000_000.0); self.montant.setDecimals(2)
        self.montant.setSuffix(" €")
        layout.addRow("Montant :", self.montant)

        self.cat = QComboBox(); self.cat.setEditable(True)
        all_cats = sorted(set((categories or []) + CATEGORIES_DEFAUT))
        self.cat.addItems(all_cats)
        layout.addRow("Catégorie :", self.cat)

        self.sous_cat = QLineEdit()
        layout.addRow("Sous-catégorie :", self.sous_cat)

        self.type_combo = QComboBox(); self.type_combo.addItems(TYPES_OPERATION)
        layout.addRow("Type :", self.type_combo)

        self.frequency = QComboBox()
        for code, label in FREQUENCIES:
            self.frequency.addItem(label, code)
        layout.addRow("Fréquence :", self.frequency)

        self.day_of_month = QSpinBox()
        self.day_of_month.setRange(1, 31); self.day_of_month.setValue(1)
        self.day_of_month.setSuffix(" (pour mensuelle/trimestrielle)")
        layout.addRow("Jour du mois :", self.day_of_month)

        self.start_date = QDateEdit(); self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("dd/MM/yyyy")
        self.start_date.setDate(QDate.currentDate())
        layout.addRow("Date de début :", self.start_date)

        self.end_date = QDateEdit(); self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("dd/MM/yyyy")
        self.end_date.setSpecialValueText("(aucune)")
        self.end_date.setMinimumDate(QDate(1900, 1, 1))
        self.end_date.setDate(QDate(1900, 1, 1))  # → "aucune"
        layout.addRow("Date de fin :", self.end_date)

        self.actif = QCheckBox("Actif")
        self.actif.setChecked(True)
        layout.addRow("", self.actif)

        self.btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.btns.accepted.connect(self.accept); self.btns.rejected.connect(self.reject)
        layout.addRow(self.btns)

        if rec:
            self.libelle.setText(rec.get("libelle", ""))
            m = rec.get("montant", 0)
            self.montant.setValue(abs(m))
            (self.rb_credit if m >= 0 else self.rb_debit).setChecked(True)
            self.cat.setCurrentText(rec.get("categorie", ""))
            self.sous_cat.setText(rec.get("sous_cat", ""))
            idx = self.type_combo.findText(rec.get("type", ""))
            if idx >= 0: self.type_combo.setCurrentIndex(idx)
            for i in range(self.frequency.count()):
                if self.frequency.itemData(i) == rec.get("frequency"):
                    self.frequency.setCurrentIndex(i); break
            if rec.get("day_of_month"):
                self.day_of_month.setValue(rec["day_of_month"])
            sd = rec.get("start_date")
            if sd:
                self.start_date.setDate(QDate.fromString(sd, "yyyy-MM-dd"))
            ed = rec.get("end_date")
            if ed:
                self.end_date.setDate(QDate.fromString(ed, "yyyy-MM-dd"))
            self.actif.setChecked(bool(rec.get("actif", 1)))

    def _apply_libelle_profile(self, libelle: str):
        """Pré-remplit catégorie / sous-catégorie / type (et le montant s'il
        est encore à 0) d'après l'historique du libellé choisi."""
        prof = self._lib_profiles.get((libelle or "").strip())
        if not prof:
            return
        if prof["categorie"]:
            self.cat.setCurrentText(prof["categorie"])
        if prof["sous_cat"]:
            self.sous_cat.setText(prof["sous_cat"])
        if prof["type"]:
            idx = self.type_combo.findText(prof["type"])
            if idx >= 0:
                self.type_combo.setCurrentIndex(idx)
        if self.montant.value() == 0 and prof["montant"]:
            self.montant.setValue(abs(prof["montant"]))
            (self.rb_credit if prof["montant"] >= 0 else self.rb_debit).setChecked(True)

    def values(self) -> dict:
        m = self.montant.value()
        if self.rb_debit.isChecked(): m = -m
        ed_qdate = self.end_date.date()
        ed_str = ed_qdate.toString("yyyy-MM-dd") if ed_qdate > QDate(1900, 1, 1) else None
        return {
            "libelle":      self.libelle.text().strip(),
            "montant":      m,
            "categorie":    self.cat.currentText().strip() or "Non classé",
            "sous_cat":     self.sous_cat.text().strip(),
            "type":         self.type_combo.currentText(),
            "frequency":    self.frequency.currentData(),
            "day_of_month": self.day_of_month.value(),
            "start_date":   self.start_date.date().toString("yyyy-MM-dd"),
            "end_date":     ed_str,
            "actif":        1 if self.actif.isChecked() else 0,
        }
