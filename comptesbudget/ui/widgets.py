"""Widgets partagés (sélecteur de période)."""

from datetime import date

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout,
    QLabel, QComboBox,
)

from ..utils import (
    list_periods, period_label,
)

class PeriodBar(QWidget):
    period_changed = Signal(str)
    date_mode_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        h = QHBoxLayout(self); h.setContentsMargins(8, 4, 8, 4)

        h.addWidget(QLabel("Période :"))
        self.combo = QComboBox()
        self.combo.setMinimumWidth(220)
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
        for p in list_periods(transactions):
            self.combo.addItem(period_label(p), p)
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

    def current_period(self) -> str:
        return self.combo.currentData() or "all"

    def current_date_mode(self) -> str:
        return self.date_mode_combo.currentData() or "operation"
