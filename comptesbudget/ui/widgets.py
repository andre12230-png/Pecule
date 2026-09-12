"""Widgets partagés (sélecteur de période, champ de montant)."""

from datetime import date

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QDialog, QDialogButtonBox,
    QLabel, QComboBox, QDoubleSpinBox, QCheckBox, QPushButton,
)

from ..utils import (
    MOIS_TOUS, _mois_des_transactions, annee_de_periode, annees_disponibles,
    mois_disponibles, nom_mois_fr, period_label, periode_voisine,
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
    """Barre du haut : « Période : ‹ [année] [mois] › », mode de date et
    archives.

    Le sélecteur de période était une seule liste où les mois se rangeaient
    en retrait sous leur année ; pour atteindre un mois d'une année passée,
    il fallait choisir l'année, puis rouvrir la liste. Il est coupé en deux
    menus courts, encadrés de deux flèches qui reculent ou avancent d'un
    cran à échelle constante (un mois reste un mois, une année une année) —
    le même sélecteur que dans pv-dashboard et Recharges VE.

    La valeur manipulée n'a pas changé (« all », « 2026 », « 2026-09 ») :
    les vues filtrent exactement comme avant.
    """

    period_changed = Signal(str)
    date_mode_changed = Signal(str)
    archives_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        h = QHBoxLayout(self); h.setContentsMargins(8, 4, 8, 4)

        h.addWidget(QLabel("Période :"))

        # Les deux flèches font le geste le plus fréquent — « et le mois
        # d'avant ? » — en un clic, sans ouvrir de liste.
        self.prev_btn = self._fleche("‹", "Période précédente", -1)
        h.addWidget(self.prev_btn)

        self.annee_combo = QComboBox()
        self.annee_combo.setMinimumWidth(120)
        self.annee_combo.setToolTip(
            "Année affichée, ou « Toutes périodes » pour tout l'historique.")
        self.annee_combo.currentIndexChanged.connect(self._on_annee)
        h.addWidget(self.annee_combo)

        self.mois_combo = QComboBox()
        self.mois_combo.setMinimumWidth(120)
        self.mois_combo.setToolTip(
            "Mois affiché dans l'année choisie, ou l'année entière.")
        self.mois_combo.currentIndexChanged.connect(self._on_mois)
        h.addWidget(self.mois_combo)

        self.next_btn = self._fleche("›", "Période suivante", +1)
        h.addWidget(self.next_btn)

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
        self._transactions: list[dict] = []
        self._current = "all"
        self._current_mode = "valeur"
        # Au tout premier remplissage, on se place sur le mois en cours
        # (s'il porte des opérations), au lieu de « Toutes périodes ».
        self._first_fill = True
        self._peupler()

    def _fleche(self, signe: str, infobulle: str, sens: int) -> QPushButton:
        """Un des deux boutons de navigation. Grisé quand il n'y a plus rien
        de ce côté : cliquable mais sans effet, il ferait croire à une
        panne."""
        b = QPushButton(signe)
        b.setFixedWidth(26)
        # Le chevron est un caractère fin : sans mise en gras il se perd à
        # côté des deux menus.
        police = b.font()
        police.setBold(True)
        police.setPointSize(police.pointSize() + 3)
        b.setFont(police)
        b.setToolTip(infobulle)
        b.clicked.connect(lambda: self._decaler(sens))
        return b

    # ── Remplissage ─────────────────────────────────────────────────
    def update_periods(self, transactions: list[dict]):
        """Reçoit les opérations du compte affiché et remet la barre
        d'aplomb. Appelée à chaque rafraîchissement : de nouveaux mois
        peuvent être apparus, ou la période choisie avoir disparu."""
        self._transactions = list(transactions)
        mode = self.current_date_mode()

        if self._first_fill:
            # Le mois en cours est toujours proposé dans le menu, même vide ;
            # mais on n'OUVRE pas dessus s'il ne porte aucune opération, ce
            # qui donnerait un écran vide sans dire pourquoi.
            courant = date.today().strftime("%Y-%m")
            reels = _mois_des_transactions(self._transactions, mode)
            self._current = courant if courant in reels else "all"
            # Tant que le compte est vide, ce premier placement n'a pas
            # vraiment eu lieu : on l'attend pour les premières opérations.
            # Sinon, après le premier import, la barre restait sur « Toutes
            # périodes » (constaté le 12/09/2026).
            self._first_fill = not self._transactions
        elif not self._periode_valide(self._current, mode):
            # Changer de mode peut faire disparaître la période choisie
            # (juillet devient août pour un achat carte).
            self._current = "all"

        self._peupler()

    def _periode_valide(self, period: str, mode: str) -> bool:
        """La période choisie existe-t-elle encore dans les deux menus ?"""
        if period == "all":
            return True
        annee = annee_de_periode(period)
        if annee not in annees_disponibles(self._transactions, mode):
            return False
        return (len(period) == 4
                or period in mois_disponibles(self._transactions, annee, mode))

    def _peupler(self):
        """Remet les deux menus d'aplomb sur self._current.

        Les signaux sont coupés pendant l'opération : sans cela, remplir un
        menu déclencherait le changement de période qu'on est en train
        d'appliquer."""
        mode = self.current_date_mode()
        for c in (self.annee_combo, self.mois_combo):
            c.blockSignals(True)

        self.annee_combo.clear()
        for a in annees_disponibles(self._transactions, mode):
            self.annee_combo.addItem(period_label(a) if a == "all" else a, a)
        annee = annee_de_periode(self._current)
        self.annee_combo.setCurrentIndex(
            self._index_de(self.annee_combo, annee or "all"))

        # Le menu des mois n'a de sens que sous une année : « toutes
        # périodes » est à cheval sur toutes les années.
        self.mois_combo.clear()
        if annee is None:
            self.mois_combo.addItem("Toute l'année", MOIS_TOUS)
        else:
            for m in mois_disponibles(self._transactions, annee, mode):
                self.mois_combo.addItem(
                    "Toute l'année" if m == MOIS_TOUS else nom_mois_fr(m), m)
            cible = self._current if len(self._current) == 7 else MOIS_TOUS
            self.mois_combo.setCurrentIndex(
                self._index_de(self.mois_combo, cible))

        for c in (self.annee_combo, self.mois_combo):
            c.blockSignals(False)
        self._maj_etat()

    @staticmethod
    def _index_de(combo: QComboBox, valeur: str) -> int:
        """Rang de `valeur` dans un menu, 0 si elle n'y est pas."""
        return next((i for i in range(combo.count())
                     if combo.itemData(i) == valeur), 0)

    def _maj_etat(self):
        """Active ou grise le menu des mois et les deux flèches."""
        mode = self.current_date_mode()
        self.mois_combo.setEnabled(annee_de_periode(self._current) is not None)
        for bouton, sens in ((self.prev_btn, -1), (self.next_btn, +1)):
            bouton.setEnabled(periode_voisine(
                self._transactions, self._current, sens, mode) is not None)

    # ── Changements de période ──────────────────────────────────────
    def _appliquer(self, period: str):
        """Change la période affichée, remet la barre d'aplomb et prévient la
        fenêtre principale."""
        period = period or "all"
        if period == self._current:
            return
        self._current = period
        self._peupler()
        self.period_changed.emit(period)

    def _on_annee(self, idx: int):
        valeur = self.annee_combo.itemData(idx)
        if valeur is None:
            return
        # En changeant d'année on garde le mois affiché s'il existe là-bas :
        # c'est ce qu'on veut pour comparer un mois d'une année sur l'autre.
        # Sinon on montre l'année entière plutôt qu'un écran vide.
        if valeur != "all" and len(self._current) == 7:
            candidat = f"{valeur}-{self._current[5:7]}"
            if candidat in mois_disponibles(self._transactions, valeur,
                                            self.current_date_mode()):
                valeur = candidat
        self._appliquer(valeur)

    def _on_mois(self, idx: int):
        valeur = self.mois_combo.itemData(idx)
        if valeur is None:
            return
        if valeur == MOIS_TOUS:
            valeur = self.annee_combo.currentData() or "all"
        self._appliquer(valeur)

    def _decaler(self, sens: int):
        """Un cran en arrière (sens=-1) ou en avant (+1), à échelle constante :
        un mois reste un mois, une année reste une année."""
        voisine = periode_voisine(self._transactions, self._current, sens,
                                  self.current_date_mode())
        if voisine is not None:
            self._appliquer(voisine)

    # ── Le reste de la barre ────────────────────────────────────────
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
        return self._current

    def current_date_mode(self) -> str:
        return self.date_mode_combo.currentData() or "operation"
