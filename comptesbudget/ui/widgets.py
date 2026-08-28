"""Widgets partagés (sélecteur de période, champ de montant)."""

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QDialog, QDialogButtonBox,
    QLabel, QComboBox, QDoubleSpinBox, QCheckBox,
)

from ..utils import (
    list_periods, period_label,
)


class MontantSpinBox(QDoubleSpinBox):
    """Champ de montant qui accepte le POINT autant que la virgule.

    En français, Qt n'attend que la virgule comme séparateur décimal : taper
    « 12.50 » — le point du pavé numérique — était refusé, le champ restait
    bloqué sur « 12 ». Le point est ici traduit à la volée en séparateur
    local, si bien que les deux touches donnent le même résultat."""

    def _normalise(self, texte: str) -> str:
        sep = self.locale().decimalPoint()
        if sep == ".":
            return texte or ""
        return (texte or "").replace(".", sep)

    def validate(self, texte, pos):
        # Qt réécrit le champ avec le texte renvoyé : le point saisi devient
        # donc une virgule sous les yeux de l'utilisateur.
        return super().validate(self._normalise(texte), pos)

    def valueFromText(self, texte):
        return super().valueFromText(self._normalise(texte))


def demander_montant(parent, titre: str, question: str, valeur: float = 0.0,
                     mini: float = 0.0, maxi: float = 1_000_000.0):
    """Petite boîte « saisissez un montant », équivalent de
    QInputDialog.getDouble mais bâtie sur MontantSpinBox : le point du pavé
    numérique y est accepté comme la virgule. Renvoie (montant, validé)."""
    dlg = QDialog(parent)
    dlg.setWindowTitle(titre)
    dlg.setMinimumWidth(360)
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel(question))
    champ = MontantSpinBox()
    champ.setRange(mini, maxi)
    champ.setDecimals(2)
    champ.setSuffix(" €")
    champ.setValue(valeur)
    champ.selectAll()
    lay.addWidget(champ)
    btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    btns.accepted.connect(dlg.accept)
    btns.rejected.connect(dlg.reject)
    lay.addWidget(btns)
    ok = dlg.exec() == QDialog.Accepted
    return champ.value(), ok


class PeriodBar(QWidget):
    period_changed = Signal(str)
    date_mode_changed = Signal(str)
    archives_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        h = QHBoxLayout(self); h.setContentsMargins(8, 4, 8, 4)

        h.addWidget(QLabel("Période :"))
        self.combo = QComboBox()
        self.combo.setMinimumWidth(220)
        self.combo.setToolTip(
            "Période affichée. Seule l'année en cours montre ses mois ; "
            "choisissez une autre année pour ouvrir les siens.")
        self.combo.currentIndexChanged.connect(self._emit)
        h.addWidget(self.combo)

        h.addSpacing(20)
        h.addWidget(QLabel("Date :"))
        self.date_mode_combo = QComboBox()
        self.date_mode_combo.addItem("Date d'opération (vision budget)", "operation")
        self.date_mode_combo.addItem("Date de valeur (solde banque réel)", "valeur")
        self.date_mode_combo.setToolTip(
            "Date opération = jour de l'achat, vision budget\n"
            "Date valeur = jour où la banque débite, solde réel du compte"
        )
        # Par défaut : Date de valeur (solde réel du compte).
        self.date_mode_combo.setCurrentIndex(1)
        self.date_mode_combo.currentIndexChanged.connect(self._emit_date_mode)
        h.addWidget(self.date_mode_combo)

        # Case « Voir les archives » : cachée tant que rien n'est archivé,
        # pour ne rien ajouter à l'écran de ceux qui n'archivent pas.
        h.addSpacing(16)
        self.archives_check = QCheckBox("Voir les archives")
        self.archives_check.setToolTip(
            "Réaffiche les opérations mises de côté par l'archivage")
        self.archives_check.setVisible(False)
        self.archives_check.toggled.connect(self.archives_toggled.emit)
        h.addWidget(self.archives_check)

        h.addStretch()
        self._current = "all"
        self._current_mode = "valeur"
        # Au tout premier remplissage, on présélectionne le mois en cours
        # (s'il existe dans la liste), au lieu de « Toutes périodes ».
        self._first_fill = True

    def update_periods(self, transactions: list[dict]):
        cur_data = self.combo.currentData()
        self.combo.blockSignals(True)
        self.combo.clear()
        # Les périodes proposées suivent le mode d'affichage : c'est la même
        # date qui sert à remplir cette liste et à filtrer les opérations.
        # Une année ouvre son groupe (en gras) ; ses mois sont décalés
        # dessous. Une liste déroulante Qt ne connaît pas les sous-titres :
        # le retrait et la graisse en tiennent lieu.
        #
        # Les années passées restent repliées : seule la ligne « Année … »
        # apparaît. Sont dépliées l'année en cours et celle de la période
        # choisie — choisir « Année 2024 » ouvre donc ses mois au passage.
        # Sans cela, quatre ans d'historique donnaient cinquante entrées.
        depliees = {date.today().strftime("%Y")}
        if cur_data and cur_data != "all":
            depliees.add(cur_data[:4])

        grasse = QFont()
        grasse.setBold(True)
        for p in list_periods(transactions, self.current_date_mode()):
            if len(p) == 7 and p[:4] not in depliees:
                continue
            libelle = period_label(p)
            if len(p) == 7:
                libelle = "      " + libelle
            self.combo.addItem(libelle, p)
            if len(p) == 4:
                self.combo.setItemData(self.combo.count() - 1, grasse,
                                       Qt.FontRole)
        # Premier remplissage : sélectionner le mois en cours s'il est présent.
        if self._first_fill:
            current_month = date.today().strftime("%Y-%m")
            idx = self.combo.findData(current_month)
            if idx >= 0:
                self.combo.setCurrentIndex(idx)
                self._current = current_month
            self._first_fill = False
        elif cur_data:
            idx = self.combo.findData(cur_data)
            if idx >= 0:
                self.combo.setCurrentIndex(idx)
        self.combo.blockSignals(False)
        # Changer de mode peut faire disparaître la période choisie (juillet
        # devient août pour un achat carte). On note ce qui est réellement
        # sélectionné, sinon un futur choix de cette même période serait
        # considéré comme « inchangé » et n'actualiserait rien.
        self._current = self.combo.currentData() or "all"

    def _emit(self):
        p = self.combo.currentData() or "all"
        if p != self._current:
            self._current = p
            self.period_changed.emit(p)

    def _emit_date_mode(self):
        m = self.date_mode_combo.currentData() or "operation"
        if m != self._current_mode:
            self._current_mode = m
            self.date_mode_changed.emit(m)

    def set_archives_disponibles(self, nb: int):
        """Montre la case « Voir les archives » seulement s'il y a quelque
        chose à voir, et rappelle combien."""
        self.archives_check.setVisible(bool(nb))
        if nb:
            self.archives_check.setText(f"Voir les archives ({nb})")
        if not nb and self.archives_check.isChecked():
            self.archives_check.setChecked(False)

    def reset_selection(self):
        """Repart du mois en cours au prochain remplissage. Sert quand on
        change de compte : les périodes disponibles ne sont plus les mêmes."""
        self._first_fill = True

    def current_period(self) -> str:
        return self.combo.currentData() or "all"

    def current_date_mode(self) -> str:
        return self.date_mode_combo.currentData() or "operation"
