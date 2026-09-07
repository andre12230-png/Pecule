"""Vue Bilan (tableau de bord)."""

from calendar import monthrange
from datetime import date, timedelta
from html import escape as _esc   # noms de catégories insérés dans du HTML

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QColor, QPainter,
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QScrollArea,
)
from PySide6.QtCharts import (
    QChart, QChartView, QPieSeries, QBarSeries, QBarSet,
    QAbstractBarSeries, QBarCategoryAxis, QValueAxis,
)

from ...utils import (
    cat_color, date_debit_differe, est_paiement_carte, fmt_euro, fmt_date_fr,
    in_period, period_label,
)
from ...database import Database
from ...labels import clean_libelle
from ...recurring import echeances_du_mois

# Jour du mois à partir duquel on ose annoncer une tendance de fin de mois.
# Avant, le calcul est trompeur : une grosse course le 3 du mois annonçait
# 1 286 € pour un encours réel de 214 €.
JOUR_TENDANCE = 10

# Horizon de la recherche du prochain découvert. 45 jours plutôt que la fin du
# mois : le moment le plus risqué est le prélèvement carte du 4 du mois
# suivant, et il faut voir la remontée des pensions qui arrivent derrière.
HORIZON_DECOUVERT = 45

class CatRowsWidget(QWidget):
    """Liste de lignes : pastille colorée + libellé + (% optionnel) + montant à droite."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(8, 6, 8, 6)
        self.lay.setSpacing(4)
        self.lay.addStretch()

    def set_items(self, items: list[tuple]):
        """items = list of (label, amount, color, optional_pct_or_date)."""
        # Reset
        while self.lay.count() > 1:
            it = self.lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        if not items:
            self.lay.insertWidget(0, QLabel("— Aucune donnée —"))
            return
        for tup in items:
            label = tup[0]; amount = tup[1]; color = tup[2]
            sub = tup[3] if len(tup) > 3 else None
            row = QHBoxLayout()
            row.setSpacing(8); row.setContentsMargins(0, 0, 0, 0)
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color}; font-size: 13pt")
            dot.setFixedWidth(14)
            row.addWidget(dot)
            lbl = QLabel(label)
            lbl.setTextFormat(Qt.PlainText)   # libellé affiché tel quel (jamais interprété)
            lbl.setStyleSheet("color:#222")
            row.addWidget(lbl, 1)
            if sub:
                # Même correction de contraste que les sous-titres des tuiles :
                # ces pourcentages et ces dates se lisaient mal en gris pâle.
                s = QLabel(sub); s.setStyleSheet("color:#555; font-size:9pt")
                row.addWidget(s)
            amt = QLabel(fmt_euro(amount))
            amt.setStyleSheet(
                f"color: {'#C0392B' if amount < 0 else '#229954'}; font-weight:600")
            amt.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row.addWidget(amt)
            wrap = QWidget(); wrap.setLayout(row)
            self.lay.insertWidget(self.lay.count() - 1, wrap)


def _make_panel(title: str, body: QWidget) -> QFrame:
    """Carte stylée avec en-tête bleu + corps."""
    f = QFrame()
    f.setStyleSheet("""
        QFrame { background: white; border: 1px solid #C8D0DC; border-radius: 4px; }
    """)
    v = QVBoxLayout(f); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(0)
    header = QLabel(title.upper())
    header.setStyleSheet("""
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #E8EEF7, stop:1 #C9D6E8);
        color: #1F3A6B; font-weight: 600; font-size: 9pt;
        padding: 4px 10px; border-bottom: 1px solid #B0BFD3;
        letter-spacing: 0.5px;
    """)
    v.addWidget(header)
    v.addWidget(body, 1)
    f._header = header          # pour les panneaux dont le titre change
    return f


class BilanView(QWidget):
    goto_budget = Signal()   # clic sur l'alerte budget → ouvrir l'onglet Budget

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.period = "all"
        self.date_mode = "valeur"
        self.setStyleSheet("BilanView { background: #ECEEF2; }")

        # ── Le Bilan défile ───────────────────────────────────────────
        # Sans cela, la hauteur minimale de la FENÊTRE est celle de tout ce
        # que le Bilan empile — 986 px, et davantage à chaque bandeau
        # ajouté. En dessous, Qt comprime : les libellés des panneaux du bas
        # se chevauchent et les étiquettes des graphiques se superposent.
        # Avec un défilement, la fenêtre peut descendre où l'on veut sans
        # rien écraser, et rien ne change tant qu'elle est assez grande.
        exterieur = QVBoxLayout(self)
        exterieur.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Le fond du panneau déroulant est blanc par défaut : on lui redonne
        # le gris de la vue, sinon une bande claire apparaît sous le contenu.
        self.scroll.viewport().setStyleSheet("background: #ECEEF2;")
        exterieur.addWidget(self.scroll)
        contenu = QWidget()
        self.scroll.setWidget(contenu)

        main = QVBoxLayout(contenu)
        main.setContentsMargins(10, 10, 10, 10)
        main.setSpacing(10)

        # ── Ligne 1 : 6 cartes KPI ────────────────────────────────────
        kpi_row = QHBoxLayout(); kpi_row.setSpacing(8)
        self.kpis = {}
        # Quatre tuiles depuis le 07/09/2026. Il y en avait six : « Revenus »
        # et « Dépenses » répétaient le mouvement net, dont ils sont les deux
        # moitiés — ils sont passés en sous-titre de celui-ci, sans rien
        # perdre. Et « Solde pointé » n'était pas un solde mais la somme des
        # opérations pointées de la période : son nom le disait mal, juste à
        # côté du vrai solde et pour une valeur voisine.
        defs = [
            ("solde",    "💼 Solde bancaire réel (pointé)", "#1F3A6B"),
            ("net",      "Mouvement du mois",              "#34495E"),
            ("epargne",  "Taux d'épargne",                 "#16A085"),
            ("pointe",   "✔ Pointé sur la période",         "#1A7A3A"),
        ]
        for key, label, color in defs:
            card = self._make_kpi(label, "—", color)
            self.kpis[key] = card
            kpi_row.addWidget(card, 1)
        main.addLayout(kpi_row)

        # ── Bandeau de verdict ────────────────────────────────────────
        # La réponse, en une phrase, à la seule question qu'on se pose en
        # ouvrant l'application : « est-ce que je passe le mois ? ». Où le
        # compte finira, à partir de quand il sera négatif, et son point le
        # plus bas. Le jour compte autant que le total : le creux vient du
        # calendrier — lot carte prélevé le 4-5, pensions le 7 et le 9.
        #
        # Il parle TOUJOURS du mois en cours, même quand on consulte un mois
        # passé : c'est un verdict pour agir, pas une fiche de consultation.
        self.verdict_banner = QLabel("")
        self.verdict_banner.setWordWrap(True)
        self.verdict_banner.setVisible(False)
        main.addWidget(self.verdict_banner)

        # ── Bandeau Encours Carte Bancaire ────────────────────────────
        self.cb_banner = QFrame()
        self.cb_banner.setStyleSheet("""
            QFrame { background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #FFF8E1, stop:1 #FFECB3);
                     border: 1px solid #E8C77B; border-radius: 4px; }
        """)
        cb_lay = QHBoxLayout(self.cb_banner)
        cb_lay.setContentsMargins(12, 4, 12, 4); cb_lay.setSpacing(18)

        self.cb_title = QLabel("💳 ENCOURS CARTE BANCAIRE")
        self.cb_title.setStyleSheet("font-weight:bold; color:#7E5A18; font-size:9pt")
        # Repli sur deux lignes en fenêtre étroite (sinon le bandeau réclame
        # 1390 pixels de large et bloque le redimensionnement de la fenêtre).
        self.cb_title.setWordWrap(True)
        cb_lay.addWidget(self.cb_title)
        cb_lay.addSpacing(10)

        # 4 mini-blocs : confirmé / en cours / total à débiter / disponible
        def _mini(label_txt):
            w = QWidget(); l = QVBoxLayout(w); l.setContentsMargins(0,0,0,0); l.setSpacing(0)
            lbl = QLabel(label_txt); lbl.setStyleSheet("color:#7E5A18; font-size:8pt")
            # Repli sur deux lignes, comme le titre : à quatre blocs, des
            # libellés d'un seul tenant imposeraient une fenêtre plus large
            # que la moitié d'écran sur laquelle André travaille.
            lbl.setWordWrap(True)
            val = QLabel("—"); val.setStyleSheet("color:#5A2D00; font-size:12pt; font-weight:bold")
            # Le repli des libellés rétrécit le bloc au point de couper le
            # montant (« -241,39 » sans son €). Un chiffre tronqué est pire
            # qu'un bandeau large : on lui garantit sa place.
            val.setMinimumWidth(96)
            l.addWidget(lbl); l.addWidget(val)
            return w, val, lbl

        # Les deux premiers chiffres reprennent exactement ceux de l'espace
        # bancaire : « Débit différé au JJ/MM » (achats que la banque a déjà
        # intégrés au prochain prélèvement = pointés) et les achats « en
        # cours » qu'elle n'a pas encore intégrés. Leur somme est l'encours.
        # « Opérations » et non « Achats » : une opération carte en cours peut
        # être un REMBOURSEMENT (crédit), pas seulement une dépense.
        # Libellés courts, précisions au survol : à quatre blocs, un libellé
        # qui se replie sur trois lignes prend en hauteur ce que le graphique
        # d'en dessous perd.
        self.cb_bloc1, self.cb_courant, _ = _mini("Prochain prélèvement")
        self.cb_bloc1.setToolTip(
            "Achats que la banque a déjà rattachés au prélèvement à venir "
            "(vos opérations pointées) : son « débit différé au 4 ».")
        self.cb_bloc2, self.cb_precedent, _ = _mini("Opérations en cours")
        self.cb_bloc2.setToolTip(
            "Opérations faites mais pas encore intégrées par la banque "
            "(non pointées). Ce peut être un achat comme un remboursement.")
        self.cb_bloc3, self.cb_total, self.cb_total_lbl = _mini("Total des achats à débiter")
        # Ce qui reste vraiment pour la carte sur le mois affiché : le solde
        # que le compte aura en fin de mois, tout payé, moins les achats déjà
        # engagés. Voir _reste_du_mois.
        self.cb_bloc4, self.cb_dispo, self.cb_dispo_lbl = _mini("Reste pour la carte")
        w1, w2, w3 = self.cb_bloc1, self.cb_bloc2, self.cb_bloc3
        cb_lay.addWidget(w1); cb_lay.addWidget(w2); cb_lay.addWidget(w3)
        cb_lay.addWidget(self.cb_bloc4)
        cb_lay.addStretch()
        self.cb_detail = QLabel("")
        self.cb_detail.setStyleSheet("color:#7E5A18; font-size:9pt")
        self.cb_detail.setWordWrap(True)
        cb_lay.addWidget(self.cb_detail)
        # Une seconde ligne rappelait ce qui restait sur les six derniers
        # mois. Retirée le 07/09/2026 : le graphique « Évolution sur 12 mois »
        # montre la même tendance en mieux, et le bandeau y gagne en hauteur.
        main.addWidget(self.cb_banner)

        # Le bandeau « Ce qui est prévu » (projection à 15 jours) a été
        # retiré le 07/09/2026 : son « solde au 22/09 » était un jalon
        # arbitraire, là où le bandeau de verdict donne le PIRE moment.
        # Ce qu'il apportait d'unique — les prochaines échéances nommées et
        # les opérations carte en cours — est passé dans le bandeau vert.

        # ── Bandeau « Ce mois-ci » (reste à passer jusqu'au dernier jour) ──
        # La lecture du budget mensuel tenu sur papier : en banque aujourd'hui,
        # ce qui doit encore tomber, et le solde attendu en fin de mois.
        self.mois_banner = QFrame()
        self.mois_banner.setStyleSheet("""
            QFrame { background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #EDF7EE, stop:1 #D8ECDC);
                     border: 1px solid #A6CDAF; border-radius: 4px; }
        """)
        mo_lay = QHBoxLayout(self.mois_banner)
        mo_lay.setContentsMargins(12, 4, 12, 4); mo_lay.setSpacing(18)

        self.mois_title = QLabel("🗓 CE MOIS-CI")
        self.mois_title.setStyleSheet("font-weight:bold; color:#1A5E2A; font-size:9pt")
        self.mois_title.setWordWrap(True)
        mo_lay.addWidget(self.mois_title)
        mo_lay.addSpacing(10)

        def _mini_vert(label_txt):
            w = QWidget(); l = QVBoxLayout(w); l.setContentsMargins(0,0,0,0); l.setSpacing(0)
            lbl = QLabel(label_txt); lbl.setStyleSheet("color:#1A5E2A; font-size:8pt")
            lbl.setWordWrap(True)
            val = QLabel("—"); val.setStyleSheet("color:#0F3D1B; font-size:12pt; font-weight:bold")
            l.addWidget(lbl); l.addWidget(val)
            return w, val, lbl

        m1, self.mois_sorties, _ = _mini_vert("À débiter (hors carte)")
        m2, self.mois_entrees, _ = _mini_vert("À encaisser")
        m3, self.mois_solde, self.mois_solde_lbl = _mini_vert("Solde au terme")
        mo_lay.addWidget(m1); mo_lay.addWidget(m2); mo_lay.addWidget(m3)
        mo_lay.addStretch()
        self.mois_detail = QLabel("")
        self.mois_detail.setStyleSheet("color:#2F6B3C; font-size:9pt")
        self.mois_detail.setWordWrap(True)
        mo_lay.addWidget(self.mois_detail)
        main.addWidget(self.mois_banner)

        # ── Bandeau Alertes budget (mois en cours) ────────────────────
        # Masqué tant qu'aucune catégorie n'approche ou ne dépasse son budget.
        self.budget_alert = QLabel()
        self.budget_alert.setWordWrap(True)
        self.budget_alert.setTextFormat(Qt.RichText)
        self.budget_alert.setVisible(False)
        self.budget_alert.linkActivated.connect(lambda _l: self.goto_budget.emit())
        main.addWidget(self.budget_alert)

        # ── Ligne 2 : 2 graphiques ────────────────────────────────────
        mid_row = QHBoxLayout(); mid_row.setSpacing(8)

        # Barres mensuelles
        self.bar_chart = QChart()
        self.bar_chart.setBackgroundVisible(False)
        self.bar_chart.legend().setAlignment(Qt.AlignBottom)
        self.bar_chart.setAnimationOptions(QChart.SeriesAnimations)
        bar_view = QChartView(self.bar_chart)
        bar_view.setRenderHint(QPainter.Antialiasing)
        bar_view.setMinimumHeight(240)
        self.bar_panel = _make_panel("Évolution sur 12 mois", bar_view)
        mid_row.addWidget(self.bar_panel, 2)

        # Camembert
        self.pie_chart = QChart()
        self.pie_chart.setBackgroundVisible(False)
        self.pie_chart.legend().setAlignment(Qt.AlignRight)
        # La légende porte le nom ET le montant de chaque catégorie : un texte
        # un peu plus petit évite qu'elle soit tronquée en fenêtre étroite.
        police_legende = self.pie_chart.legend().font()
        police_legende.setPointSize(8)
        self.pie_chart.legend().setFont(police_legende)
        self.pie_chart.setAnimationOptions(QChart.SeriesAnimations)
        pie_view = QChartView(self.pie_chart)
        pie_view.setRenderHint(QPainter.Antialiasing)
        pie_view.setMinimumHeight(240)
        mid_row.addWidget(_make_panel("Répartition des dépenses", pie_view), 2)

        main.addLayout(mid_row, 1)

        # ── Ligne 3 : 3 listes ────────────────────────────────────────
        bot_row = QHBoxLayout(); bot_row.setSpacing(8)
        self.list_dep = CatRowsWidget()
        self.list_rev = CatRowsWidget()
        self.list_top = CatRowsWidget()
        bot_row.addWidget(_make_panel("Dépenses par catégorie", self.list_dep), 1)
        bot_row.addWidget(_make_panel("Sources de revenus", self.list_rev), 1)
        bot_row.addWidget(_make_panel("Plus grosses dépenses", self.list_top), 1)
        main.addLayout(bot_row, 1)

    def _make_kpi(self, label: str, value: str, color: str) -> QFrame:
        f = QFrame()
        f.setStyleSheet(f"""
            QFrame {{
                background: white; border: 1px solid #C8D0DC;
                border-top: 3px solid {color}; border-radius: 4px;
            }}
        """)
        lay = QVBoxLayout(f); lay.setContentsMargins(10, 8, 10, 8); lay.setSpacing(2)
        l_label = QLabel(label)
        l_label.setStyleSheet("color:#666; font-size:9pt; font-weight:600; text-transform:uppercase")
        # Même raison : « Solde bancaire réel (pointé) » sur une seule ligne
        # imposait 228 pixels à sa tuile, soit 940 pixels pour la rangée.
        l_label.setWordWrap(True)
        l_value = QLabel(value)
        l_value.setStyleSheet(f"color:{color}; font-size:16pt; font-weight:bold")
        l_sub = QLabel("")
        # Gris foncé, pas gris pâle : #999 sur blanc ne donne qu'un contraste
        # de 2,8 pour 1, très en dessous du minimum lisible (4,5). #555 monte
        # à 7,5 pour 1, tout en restant nettement secondaire par rapport au
        # montant. Et 9pt plutôt que 8 : ces lignes portent des chiffres.
        l_sub.setStyleSheet("color:#555; font-size:9pt")
        l_sub.setWordWrap(True)
        lay.addWidget(l_label); lay.addWidget(l_value); lay.addWidget(l_sub)
        f._value = l_value
        f._sub = l_sub
        return f

    def _colorer_kpi(self, cle: str, couleur: str):
        """Recolore une tuile : le montant ET le liseré du haut, pour qu'ils
        s'accordent toujours (vert quand c'est positif, rouge quand ça ne l'est pas)."""
        carte = self.kpis[cle]
        carte.setStyleSheet(f"""
            QFrame {{
                background: white; border: 1px solid #C8D0DC;
                border-top: 3px solid {couleur}; border-radius: 4px;
            }}
        """)
        carte._value.setStyleSheet(f"color:{couleur}; font-size:16pt; font-weight:bold")

    def _eff_date(self, t: dict) -> str:
        """Date utilisée pour les chiffres de la PÉRIODE affichée (mouvement
        net, dépenses, graphiques) : elle suit le sélecteur « Date »."""
        if self.date_mode == "valeur":
            return t.get("date_valeur") or t.get("date", "")
        return t.get("date", "")

    def _date_banque(self, t: dict) -> str:
        """Date à laquelle la banque débite ou crédite réellement le compte :
        TOUJOURS la date de valeur, quel que soit le mode d'affichage choisi.
        C'est elle qui repousse les achats par carte à débit différé au 4 du
        mois suivant — avant cette date, ils ne sont pas sur le compte."""
        return t.get("date_valeur") or t.get("date", "")

    def _solde_fin_de_mois(self, txs: list[dict], mois: str,
                           solde_compte: float) -> float:
        """Solde du compte au dernier jour du mois `mois`.

        Deux cas, qui donnent le même genre de chiffre :
          • mois DÉJÀ FINI — le solde réellement constaté ce jour-là, calculé
            comme le solde bancaire du Bilan : le solde de départ plus les
            opérations pointées dont la date de valeur est arrivée ;
          • mois EN COURS OU À VENIR — le solde prévu, c'est-à-dire le solde en
            banque d'aujourd'hui augmenté de tout ce qui doit encore passer
            d'ici là. C'est exactement le calcul du bandeau « CE MOIS-CI », et
            c'est ce qui garantit que les deux bandeaux ne se contredisent
            jamais."""
        an, m = int(mois[:4]), int(mois[5:7])
        fin = date(an, m, monthrange(an, m)[1])
        today = date.today()

        if fin < today:
            initial_date = self.db.get_setting("initial_date", "2025-01-01")
            try:
                initial = float(self.db.get_setting("initial_balance", "0"))
            except (TypeError, ValueError):
                initial = 0.0
            fin_iso = fin.isoformat()
            return initial + sum(
                t["montant"] for t in txs
                if t.get("categorie") != "Transaction exclue" and t.get("pointee")
                and initial_date <= self._date_banque(t) <= fin_iso)

        lignes, _ = self._lignes_a_venir(txs, today.replace(day=1), fin)
        return solde_compte + sum(m for _d, _l, m, _c in lignes)

    def _reste_du_mois(self, txs: list[dict], mois: str, solde_compte: float,
                       encours_mois: float) -> float:
        """Ce qui reste vraiment pour la carte sur ce mois.

        Le solde du compte à la fin du mois, une fois TOUT payé, moins les
        achats déjà passés à la carte : ceux-là ne sont pas encore sortis du
        compte — ils partiront au lot du 4 du mois suivant — mais ils sont
        engagés.

        Positif : voilà ce qu'on peut encore mettre sur la carte. Négatif :
        c'est ce qui manquera. Ce chiffre a remplacé le 07/09/2026 un plafond
        fixe saisi dans les Paramètres, qui pouvait annoncer « il reste
        247 € » pendant que le bandeau voisin prévoyait un solde négatif en
        fin de mois."""
        return self._solde_fin_de_mois(txs, mois, solde_compte) - abs(encours_mois)

    def _mois_du_bandeau(self) -> tuple[str, bool]:
        """Mois que décrit le bandeau Encours, et si c'est une consultation.

        Le bandeau suit la période choisie en haut : sélectionner « Août 2026 »
        le fait parler d'août. Une année ou « Toutes périodes » ne désignent
        aucun mois — un encours de carte ne se juge qu'au mois — et le bandeau
        reste alors sur le mois en cours.

        Retourne (« AAAA-MM », consultation) ; consultation vaut True dès que
        le mois affiché n'est pas le mois courant."""
        courant = date.today().strftime("%Y-%m")
        if len(self.period) == 7:
            return self.period, self.period != courant
        return courant, False

    @staticmethod
    def _mois_precedent(mois: str) -> str:
        """« 2026-01 » → « 2025-12 »."""
        an, m = int(mois[:4]), int(mois[5:7])
        return f"{an - 1}-12" if m == 1 else f"{an}-{m - 1:02d}"

    @staticmethod
    def _achats_du_mois(cartes: list[dict], mois: str) -> list[dict]:
        """Achats par carte d'un mois, repérés par leur DATE D'ACHAT.

        C'est le mois où l'on dépense qui est jugé, pas celui où la banque
        prélève : le lot d'août part le 4 septembre, il reste l'encours
        d'août."""
        return [t for t in cartes
                if t.get("date", "").startswith(mois) and t["montant"] < 0]

    @staticmethod
    def _carte_a_debit_differe(cartes: list[dict]) -> bool:
        """La carte de ce compte est-elle à débit différé ?

        Reconnu à la trace qu'il laisse dans les données : une opération carte
        dont la date de valeur dépasse la date d'achat. Sur une carte à débit
        immédiat, les deux dates sont toujours les mêmes.

        Aucun réglage à saisir : c'est la banque qui décide, et une seule
        opération suffit à le dire. Un compte sans la moindre opération carte
        répond « non », ce qui efface un bandeau qui n'aurait rien à montrer.
        """
        return any(t.get("date_valeur") and t.get("date")
                   and t["date_valeur"] > t["date"] for t in cartes)

    def _prochain_decouvert(self, txs: list[dict], solde_compte: float,
                            jours: int = HORIZON_DECOUVERT) -> dict:
        """Suit le solde jour après jour et dit quand il passe sous zéro.

        On part du solde en banque d'aujourd'hui et on applique, dans l'ordre
        des dates, tout ce qui doit encore passer : les opérations déjà
        enregistrées et les échéances du Prévisionnel qu'aucune n'a couvertes.

        Retourne un dictionnaire avec :
          • `bascule`  — (date, solde, libellé) du premier jour négatif, ou
                         None si le compte tient sur tout l'horizon ;
          • `creux`    — (date, solde) du point le plus bas, aujourd'hui
                         compris ;
          • `fin`      — dernier jour examiné ;
          • `deja`     — vrai si le compte est déjà négatif aujourd'hui.

        Le montant total d'un mois ne répond pas à cette question : chez
        André, le creux vient de l'ordre des dates — le lot carte prélevé le
        4-5 quand les pensions n'arrivent que le 7 et le 9."""
        today = date.today()
        fin = today + timedelta(days=jours)
        lignes, _ = self._lignes_a_venir(txs, today + timedelta(days=1), fin)

        solde = solde_compte
        bascule = None
        creux = (today.isoformat(), solde_compte)
        if solde < 0:
            bascule = (today.isoformat(), solde, "")
        for d, libelle, montant, _c in sorted(lignes, key=lambda x: x[0]):
            solde += montant
            if bascule is None and solde < 0:
                bascule = (d, solde, libelle)
            if solde < creux[1]:
                creux = (d, solde)
        return {"bascule": bascule, "creux": creux, "fin": fin.isoformat(),
                "deja": solde_compte < 0}

    def _refresh_verdict_banner(self, txs: list[dict], solde_compte: float):
        """La réponse en une phrase : où le mois finit, et quand le compte
        passe sous zéro.

        Toujours affichée, verte quand le compte tient : une absence de
        message se lirait comme un calcul qui n'a pas été fait. Elle porte
        sur le mois EN COURS quelle que soit la période consultée — c'est un
        verdict pour agir, pas une fiche de consultation."""
        mois = date.today().strftime("%Y-%m")
        solde_fin = self._solde_fin_de_mois(txs, mois, solde_compte)
        info = self._prochain_decouvert(txs, solde_compte)
        bascule, (creux_date, creux_solde) = info["bascule"], info["creux"]

        debut = (f"<b>{period_label(mois)}</b> : le compte finit le mois à "
                 f"<b>{fmt_euro(solde_fin)}</b>")

        if bascule is None:
            texte = (f"✅ {debut}, et reste positif jusqu'au "
                     f"{fmt_date_fr(info['fin'])} — au plus bas "
                     f"{fmt_euro(creux_solde)} le {fmt_date_fr(creux_date)}.")
            style = ("background:#EAF6EC; border:1px solid #229954; "
                     "color:#1A5E32;")
        else:
            jour, montant, libelle = bascule
            if info["deja"]:
                suite = "négatif <b>depuis aujourd'hui</b>"
            else:
                suite = (f"négatif <b>à partir du {fmt_date_fr(jour)}</b> "
                         f"({fmt_euro(montant)}")
                suite += (f" après « {_esc(clean_libelle(libelle))} »)"
                          if libelle else ")")
            texte = (f"🚨 {debut}, {suite}. Au plus bas : "
                     f"<b>{fmt_euro(creux_solde)}</b> "
                     f"le {fmt_date_fr(creux_date)}.")
            style = ("background:#FDEDEB; border:1px solid #E74C3C; "
                     "color:#7B241C;")

        self.verdict_banner.setStyleSheet(
            f"QLabel {{ {style} border-radius:4px; padding:6px 14px; }}")
        self.verdict_banner.setText(texte)
        self.verdict_banner.setVisible(True)

    def _refresh_cb_banner(self, txs: list[dict], solde_compte: float = None):
        """Encours de la carte à débit différé, présenté comme la banque.

        Un achat par carte n'est « pas encore débité » tant que sa date de
        valeur est à venir. Parmi ces achats, la banque distingue deux
        chiffres, repris ici tels quels :
          • ceux qu'elle a déjà intégrés au prochain prélèvement — ils sont
            pointés (convention : `pointee=1` dès que la banque les affiche
            dans le débit différé) ;
          • ceux encore « en cours », qu'elle n'a pas encore rattachés.
        Leur somme est l'encours total. Seul le PROCHAIN prélèvement est
        compté : en débit différé les achats partent par lot une fois par
        mois, les échéances plus lointaines sont annoncées à part."""
        today = date.today()
        today_iso = today.isoformat()

        def dv(t: dict) -> str:
            return t.get("date_valeur") or t.get("date", "")

        cartes = [t for t in txs
                  if est_paiement_carte(t.get("type"))
                  and t.get("categorie") != "Transaction exclue"]

        # Tout ce bandeau suppose une carte à DÉBIT DIFFÉRÉ. Sur une carte à
        # débit immédiat — le cas de beaucoup de comptes —, l'achat sort le
        # jour même : il n'y a rien « à débiter », et le retrancher du solde
        # de fin de mois le compterait deux fois, puisqu'il en est déjà
        # sorti. Le bandeau s'efface donc entièrement : le solde prévu du
        # bandeau « Ce mois-ci » répond déjà à la question.
        if not self._carte_a_debit_differe(cartes):
            self.cb_banner.setVisible(False)
            return

        # ACHATS pas encore débités : leur date de valeur est à venir (ils
        # partiront au prochain prélèvement groupé).
        pending = [t for t in cartes if dv(t) > today_iso]

        if pending:
            prochaine = min(dv(t) for t in pending)      # date du prochain débit
            lot = [t for t in pending if dv(t)[:7] == prochaine[:7]]
            plus_tard = [t for t in pending if dv(t)[:7] != prochaine[:7]]
        else:
            prochaine, lot, plus_tard = "", [], []

        confirmes = [t for t in lot if t.get("pointee")]
        # « En cours » chez la banque = opération carte qu'elle n'a pas encore
        # traitée. Un ACHAT en attente a une date de valeur future ; un
        # REMBOURSEMENT n'a pas de débit différé (il est porté directement au
        # compte, il ne réduit jamais l'encours) et sa date de valeur est donc
        # immédiate — il reste pourtant « en cours » tant qu'il n'est pas
        # passé. On le reconnaît à son absence de pointage, sur les deux
        # derniers mois pour ne pas ressortir de vieux oublis.
        limite = (today - timedelta(days=62)).isoformat()
        en_cours = [t for t in cartes
                    if not t.get("pointee")
                    and (dv(t) > today_iso or t.get("date", "") >= limite)]
        somme_confirmes = sum(t["montant"] for t in confirmes)
        somme_en_cours = sum(t["montant"] for t in en_cours)
        # Ce qui reste réellement à payer par la carte : les ACHATS non encore
        # débités, toutes échéances confondues. Les remboursements n'y entrent
        # pas — ils sont crédités sur le compte courant, ils ne viennent jamais
        # en déduction du prélèvement.
        total = sum(t["montant"] for t in pending if t["montant"] < 0)

        self.cb_courant.setText(fmt_euro(somme_confirmes))
        self.cb_precedent.setText(fmt_euro(somme_en_cours))
        self.cb_total.setText(fmt_euro(total))

        # ── Encours du mois affiché ───────────────────────────────────
        # Le bandeau suit la période choisie en haut (voir _mois_du_bandeau).
        # L'encours d'un mois, ce sont ses ACHATS, repérés par leur date
        # d'achat et non par leur date de valeur : c'est le mois où l'on
        # dépense qui est jugé, pas celui où la banque prélève. Le lot d'août
        # part le 4 septembre, il reste l'encours d'août.
        mois, consultation = self._mois_du_bandeau()
        achats_mois = self._achats_du_mois(cartes, mois)
        encours_mois = sum(t["montant"] for t in achats_mois)
        # Date à laquelle la banque prélèvera ce lot : le 4 du mois suivant.
        debit_du_mois = date_debit_differe(f"{mois}-01")

        self.cb_total.setStyleSheet(
            "color:#5A2D00; font-size:12pt; font-weight:bold")

        # ── Ce qui reste vraiment pour la carte ───────────────────────
        # Calculé sur le compte, plus sur un plafond fixe : c'est le solde de
        # fin de mois, tout payé, moins les achats carte déjà engagés. Un
        # repère figé pouvait annoncer « il reste 247 € » pendant que le
        # bandeau voisin prévoyait un solde négatif en fin de mois.
        solde_ref = solde_compte if solde_compte is not None else 0.0
        disponible = self._reste_du_mois(txs, mois, solde_ref, encours_mois)
        self.cb_dispo.setText(fmt_euro(disponible))
        self.cb_dispo.setStyleSheet(
            ("color:#C0392B" if disponible < 0 else "color:#1A7A3A")
            + "; font-size:12pt; font-weight:bold")
        self.cb_dispo_lbl.setText(
            f"Restait sur {period_label(mois).lower()}" if consultation
            else "Reste pour la carte")

        # ── Verdict du mois précédent ─────────────────────────────────
        # Le reste descend au fil du mois, mais rien ne disait ensuite si le
        # mois était passé, ni de combien il avait débordé : il fallait aller
        # le chercher en changeant de période.
        precedent = self._mois_precedent(mois)
        depense_prec = abs(sum(t["montant"]
                               for t in self._achats_du_mois(cartes, precedent)))
        reste_prec = self._reste_du_mois(txs, precedent, solde_ref, depense_prec)
        verdict = (f"\nMois précédent — {period_label(precedent).lower()} : "
                   f"{fmt_euro(depense_prec)} dépensés à la carte, "
                   + (f"il a MANQUÉ {fmt_euro(-reste_prec)}" if reste_prec < 0
                      else f"il restait {fmt_euro(reste_prec)}")
                   + " une fois tout payé")

        # ── Consultation d'un autre mois ──────────────────────────────
        # Les deux premiers chiffres décrivent le prochain prélèvement : ils
        # n'ont aucun sens sur un mois passé, où plus rien n'est en attente.
        # On les retire et le troisième annonce l'encours du mois consulté.
        self.cb_bloc1.setVisible(not consultation)
        self.cb_bloc2.setVisible(not consultation)
        if consultation:
            self.cb_total_lbl.setText("Achats de la carte sur ce mois")
            self.cb_total.setText(fmt_euro(encours_mois))
            self.cb_total.setStyleSheet(
                "color:#5A2D00; font-size:12pt; font-weight:bold")
            self.cb_title.setText(
                f"💳 ENCOURS CARTE — {period_label(mois).upper()} "
                f"(prélevé le {fmt_date_fr(debit_du_mois)})")
            detail = (f"{len(achats_mois)} achat(s) par carte sur le mois — "
                      + (f"il a MANQUÉ {fmt_euro(-disponible)}" if disponible < 0
                         else f"il restait {fmt_euro(disponible)}")
                      + " une fois tout payé")
            detail += verdict
            detail += "\nConsultation : le bandeau suit la période choisie."
            self.cb_detail.setText(detail)
            # Un mois sans un seul achat par carte n'a pas de bandeau à montrer.
            self.cb_banner.setVisible(bool(achats_mois))
            return

        self.cb_total_lbl.setText("Total des achats à débiter")
        titre = "💳 ENCOURS CARTE BANCAIRE"
        if prochaine:
            titre += f" — prochain prélèvement le {fmt_date_fr(prochaine)}"
        self.cb_title.setText(titre)

        detail = (f"{len(confirmes)} confirmée(s)  •  {len(en_cours)} en cours"
                  f"  •  {len(lot)} au total sur ce prélèvement")
        # D'où sort le chiffre « Reste pour la carte » : le solde qu'aura le
        # compte à la fin du mois une fois tout passé, moins ce qui est déjà
        # engagé sur la carte.
        solde_fin = self._solde_fin_de_mois(txs, mois, solde_ref)
        detail += (f"\nSolde prévu fin de mois {fmt_euro(solde_fin)} moins "
                   f"{fmt_euro(abs(encours_mois))} déjà passés à la carte — "
                   + (f"il MANQUE {fmt_euro(-disponible)}" if disponible < 0
                      else f"il reste {fmt_euro(disponible)}"))
        # Tendance : à ce rythme, où finira le mois ? Annoncée seulement à
        # partir du 10 — plus tôt, une seule grosse course fait dire n'importe
        # quoi — et présentée comme une estimation, jamais comme un fait.
        jours_mois = monthrange(today.year, today.month)[1]
        if today.day >= JOUR_TENDANCE and abs(encours_mois) > 0:
            fin_carte = abs(encours_mois) * jours_mois / today.day
            reste_fin = solde_fin - fin_carte
            detail += (f"\nÀ ce rythme : environ {fmt_euro(fin_carte)} à la "
                       "carte d'ici la fin du mois (estimation) — "
                       + (f"il manquerait {fmt_euro(-reste_fin)}"
                          if reste_fin < 0
                          else f"il resterait {fmt_euro(reste_fin)}"))
        detail += verdict
        if plus_tard:
            detail += (f"  •  {len(plus_tard)} opération(s) au-delà "
                       f"({fmt_euro(sum(t['montant'] for t in plus_tard))})")
        if solde_compte is not None:
            # Chiffre mis en avant par la banque sous « Opérations carte en
            # cours » : il permet de rapprocher les deux écrans d'un coup d'œil.
            detail += ("\nSolde incluant les opérations carte en cours : "
                       + fmt_euro(solde_compte + somme_en_cours))
        self.cb_detail.setText(detail)

        # Masquer le bandeau s'il n'y a rien à montrer
        self.cb_banner.setVisible(bool(pending) or bool(achats_mois))

    def _operations_a_venir(self, txs: list[dict], depuis: date,
                            jusqua: date) -> tuple[list[tuple], list[dict], set]:
        """Opérations DÉJÀ enregistrées qui doivent encore passer sur le compte
        entre `depuis` et `jusqua`.

        Retourne (lignes, opérations carte en cours, libellés couverts), chaque
        ligne étant (date, libellé, montant, est_carte)."""
        today_iso = date.today().isoformat()
        debut_iso, fin_iso = depuis.isoformat(), jusqua.isoformat()

        def dv(t: dict) -> str:
            return t.get("date_valeur") or t.get("date", "")

        actives = [t for t in txs if t.get("categorie") != "Transaction exclue"]

        # 1) Opérations déjà enregistrées dont le débit tombe dans la fenêtre.
        #    Les opérations CARTE non pointées sont écartées : la banque ne les
        #    a pas encore rattachées au prochain prélèvement, elles partiront au
        #    suivant. Les compter ici fausserait le montant du débit — un
        #    remboursement carte « en cours » ne réduit pas le prélèvement de ce
        #    mois-ci. Les opérations non-carte, elles, ne sont jamais pointées
        #    avant leur passage : on les garde toutes.
        #    Une opération pointée dont la date de valeur est déjà passée est
        #    exclue : elle compte déjà dans le solde bancaire, l'ajouter la
        #    ferait compter deux fois.
        reelles = [t for t in actives
                   if debut_iso <= dv(t) <= fin_iso
                   and not (est_paiement_carte(t.get("type")) and not t.get("pointee"))
                   and not (t.get("pointee") and dv(t) <= today_iso)]
        en_cours_carte = [t for t in actives
                          if est_paiement_carte(t.get("type")) and not t.get("pointee")
                          and dv(t) > today_iso]
        # Libellés déjà couverts : leur récurrence ne doit pas être recomptée
        deja = {clean_libelle(t.get("libelle", "")) for t in reelles
                if not est_paiement_carte(t.get("type"))}

        lignes = [(dv(t), t.get("libelle", ""), t["montant"],
                   est_paiement_carte(t.get("type")))
                  for t in reelles]
        return lignes, en_cours_carte, deja

    def _echeances_non_couvertes(self, txs: list[dict], depuis: date,
                                 jusqua: date) -> list[dict]:
        """Échéances du Prévisionnel qu'aucune opération ne couvre encore,
        entre deux dates.

        S'appuie sur le rapprochement de « Générer les échéances du mois » :
        il reconnaît une pension déjà encaissée sous un libellé un peu
        différent, là où une comparaison stricte l'annoncerait une seconde
        fois. Les deux écrans disent ainsi la même chose."""
        recs = [dict(r) for r in self.db.list_recurring()]
        debut_iso, fin_iso = depuis.isoformat(), jusqua.isoformat()
        out, vus = [], set()
        for m in (depuis, jusqua):        # une fenêtre courte couvre 1 ou 2 mois
            if (m.year, m.month) in vus:
                continue
            vus.add((m.year, m.month))
            out += [e for e in echeances_du_mois(recs, txs, m.year, m.month)
                    if not e["_deja"] and debut_iso <= e["date"] <= fin_iso]
        return out

    def _lignes_a_venir(self, txs: list[dict], depuis: date,
                        jusqua: date) -> tuple[list[tuple], list[dict]]:
        """Les opérations à venir, complétées par les échéances du
        Prévisionnel qui n'ont pas encore d'opération correspondante."""
        lignes, en_cours_carte, _deja = self._operations_a_venir(
            txs, depuis, jusqua)
        for e in self._echeances_non_couvertes(txs, depuis, jusqua):
            lignes.append((e["date"], e["libelle"], e["montant"], False))
        return lignes, en_cours_carte

    def _refresh_mois_banner(self, txs: list[dict], solde_compte: float):
        """Ce qu'il reste à passer d'ici la FIN DU MOIS en cours.

        C'est la lecture du budget mensuel tenu sur papier : le solde en banque
        d'un côté, tout ce qui doit encore tomber de l'autre, et le solde qu'on
        aura à la fin. La fenêtre part du 1er du mois : une échéance du 5
        encore en attente reste comptée.

        Depuis le 07/09/2026, ce bandeau est le seul de sa sorte : celui des
        15 jours a été retiré, et ses deux apports — les prochaines échéances
        nommées et les opérations carte en cours — ont été repris ici."""
        today = date.today()
        debut = today.replace(day=1)
        fin = date(today.year, today.month, monthrange(today.year, today.month)[1])

        lignes, en_cours_carte = self._lignes_a_venir(txs, debut, fin)

        carte = sum(m for _d, _l, m, c in lignes if c)
        sorties = sum(m for _d, _l, m, c in lignes if not c and m < 0)
        entrees = sum(m for _d, _l, m, c in lignes if not c and m > 0)
        solde_fin = solde_compte + carte + sorties + entrees

        self.mois_sorties.setText(fmt_euro(sorties))
        self.mois_entrees.setText(fmt_euro(entrees))
        self.mois_solde.setText(fmt_euro(solde_fin))
        self.mois_solde_lbl.setText(f"Solde au {fmt_date_fr(fin.isoformat())}")
        self.mois_solde.setStyleSheet(
            "font-size:12pt; font-weight:bold; color:"
            + ("#1A7A3A" if solde_fin >= 0 else "#C0392B"))

        self.mois_title.setText(
            f"🗓 CE MOIS-CI — reste à passer d'ici le {fmt_date_fr(fin.isoformat())}")

        n_sorties = sum(1 for _d, _l, m, c in lignes if not c and m < 0)
        n_entrees = sum(1 for _d, _l, m, c in lignes if not c and m > 0)
        detail = f"{n_sorties} prélèvement(s)  •  {n_entrees} rentrée(s)"
        if carte:
            prochaine_carte = min((d for d, _l, _m, c in lignes if c), default="")
            detail += (f"  •  débit carte {fmt_euro(carte)}"
                       + (f" le {fmt_date_fr(prochaine_carte)}"
                          if prochaine_carte else ""))
        if en_cours_carte:
            # Écartées du calcul : elles iront au prélèvement d'après.
            somme = sum(t["montant"] for t in en_cours_carte)
            detail += (f"  •  {len(en_cours_carte)} opération(s) carte en cours "
                       f"({fmt_euro(somme)}) au prélèvement suivant")
        # Part déjà saisie en opérations (⏳) : le reste vient du Prévisionnel
        # et n'existe pas encore dans la liste des opérations.
        debut_iso, fin_iso = debut.isoformat(), fin.isoformat()
        n_prevues = sum(
            1 for t in txs
            if t.get("prevue") and not t.get("pointee")
            and debut_iso <= (t.get("date_valeur") or t.get("date", "")) <= fin_iso)
        if n_prevues:
            detail += f"  •  dont {n_prevues} échéance(s) déjà saisie(s) ⏳"
        # Les trois prochaines échéances, pour situer. Elles venaient du
        # bandeau des 15 jours : ne comptant que ce qui est ENCORE à venir,
        # elles gardent tout leur sens dans une fenêtre qui part du 1er.
        today_iso = today.isoformat()
        suivantes = sorted((l for l in lignes if not l[3] and l[0] >= today_iso),
                           key=lambda x: x[0])[:3]
        if suivantes:
            detail += "\nProchaines : " + "  •  ".join(
                f"{fmt_date_fr(d)[:5]} {lbl[:22]} {fmt_euro(m)}"
                for d, lbl, m, _c in suivantes)
        detail += f"\nSolde en banque aujourd'hui : {fmt_euro(solde_compte)}"
        self.mois_detail.setText(detail)

        self.mois_banner.setVisible(bool(lignes))

    def _refresh_budget_alert(self, txs: list[dict]):
        """Alerte sur le MOIS EN COURS (toujours, quelle que soit la période
        affichée — c'est là qu'on peut encore agir) : catégories dont les
        dépenses dépassent le budget mensuel (rouge) ou en approchent ≥ 85 %
        (orange). Masqué si tout va bien."""
        budgets = self.db.list_budgets()
        if not budgets:
            self.budget_alert.setVisible(False)
            return
        month = date.today().strftime("%Y-%m")
        spent: dict[str, float] = {}
        for t in txs:
            # Même date que l'onglet Budget (vers lequel l'alerte renvoie) :
            # sinon les deux écrans annonceraient des dépenses différentes.
            if (t.get("categorie") == "Transaction exclue"
                    or t.get("montant", 0) >= 0
                    or not self._eff_date(t).startswith(month)):
                continue
            c = t.get("categorie", "Non classé")
            spent[c] = spent.get(c, 0) + abs(t["montant"])

        depasses, proches = [], []
        for cat, budget in budgets.items():
            if budget <= 0:
                continue
            dep = spent.get(cat, 0)
            ratio = dep / budget * 100
            if ratio >= 100:
                depasses.append((ratio, cat, dep, budget))
            elif ratio >= 85:
                proches.append((ratio, cat, dep, budget))

        if not depasses and not proches:
            self.budget_alert.setVisible(False)
            return

        def _fmt(items):
            return ", ".join(
                f"<b>{_esc(cat)}</b> {ratio:.0f} % ({fmt_euro(dep)} / {fmt_euro(budget)})"
                for ratio, cat, dep, budget in sorted(items, reverse=True))

        parts = []
        if depasses:
            parts.append("🚨 <b>Budget dépassé ce mois-ci :</b> " + _fmt(depasses))
        if proches:
            parts.append("⚠️ <b>Bientôt atteint :</b> " + _fmt(proches))
        parts.append('<a href="#budget">Voir l’onglet Budget</a>')

        if depasses:   # rouge si au moins un dépassement, sinon orange
            style = ("background:#FDEDEB; border:1px solid #E74C3C; "
                     "color:#7B241C;")
        else:
            style = ("background:#FEF5E7; border:1px solid #E67E22; "
                     "color:#7E5109;")
        self.budget_alert.setStyleSheet(
            f"QLabel {{ {style} border-radius:4px; padding:8px 14px; }}")
        self.budget_alert.setText("&nbsp;&nbsp;".join(parts))
        self.budget_alert.setVisible(True)

    # ── Rafraîchissement ─────────────────────────────────────────────
    def refresh(self):
        txs = [dict(r) for r in self.db.list_tx()]
        self._refresh_budget_alert(txs)

        # Paramètres : solde de départ
        initial_date = self.db.get_setting("initial_date", "2025-01-01")
        try:
            initial_balance = float(self.db.get_setting("initial_balance", "0"))
        except ValueError:
            initial_balance = 0.0

        # Opérations actives (hors exclues) — toutes périodes confondues
        all_active = [t for t in txs if t.get("categorie") != "Transaction exclue"]

        # Mouvement de la période
        active = [t for t in all_active if in_period(self._eff_date(t), self.period)]
        net_periode = sum(t["montant"] for t in active)
        revenus = sum(t["montant"] for t in active if t["montant"] > 0)
        depenses = sum(t["montant"] for t in active if t["montant"] < 0)
        tx_epargne = (net_periode / revenus * 100) if revenus > 0 else 0
        solde_p_periode = sum(t["montant"] for t in active if t.get("pointee"))

        # ── Solde bancaire réel = SEULES les opérations pointées ─────
        # Solde réel du compte À LA DATE DU JOUR (indépendant de la période
        # affichée ET du sélecteur « Date ») : initial + opérations pointées
        # dont la DATE DE VALEUR est déjà passée (≤ aujourd'hui). Les achats
        # par carte à débit différé n'y entrent donc que le 4 du mois suivant,
        # comme sur le relevé de la banque. Les non pointées sont ignorées :
        # elles ne sont pas encore débitées et leur date peut changer.
        today_iso = date.today().isoformat()
        up_to_end = [t for t in all_active
                     if initial_date <= self._date_banque(t) <= today_iso]
        pointees_up = [t for t in up_to_end if t.get("pointee")]
        non_pointees_up = [t for t in up_to_end if not t.get("pointee")]
        solde_compte = initial_balance + sum(t["montant"] for t in pointees_up)
        # Solde engagé (informatif) = réel + opérations non pointées
        montant_en_attente = sum(t["montant"] for t in non_pointees_up)
        solde_engage = solde_compte + montant_en_attente

        # ── Bandeaux (indépendants de la période) ────────────────────
        # Après le calcul du solde : tous deux s'en servent pour projeter.
        self._refresh_verdict_banner(txs, solde_compte)
        self._refresh_cb_banner(txs, solde_compte)
        self._refresh_mois_banner(txs, solde_compte)

        n_rev = sum(1 for t in active if t["montant"] > 0)
        n_dep = sum(1 for t in active if t["montant"] < 0)
        n_pt  = sum(1 for t in active if t.get("pointee"))

        mode_lbl = "valeur (banque)" if self.date_mode == "valeur" else "opération"
        self.kpis["solde"]._value.setText(fmt_euro(solde_compte))
        self._colorer_kpi("solde", "#229954" if solde_compte >= 0 else "#C0392B")
        sub = (f"Au {fmt_date_fr(today_iso)} — initial {fmt_euro(initial_balance)} + "
               f"{len(pointees_up)} opér. pointée(s) — toujours en date de valeur "
               "(banque), encours carte non compris")
        if non_pointees_up:
            sub += (f"  •  {len(non_pointees_up)} non pointée(s) ignorée(s) "
                    f"({fmt_euro(montant_en_attente)}) — engagé : {fmt_euro(solde_engage)}")
        self.kpis["solde"]._sub.setText(sub)

        net = net_periode
        self.kpis["net"]._value.setText(fmt_euro(net))
        # Les deux moitiés du mouvement, là où elles occupaient deux tuiles.
        self.kpis["net"]._sub.setText(
            f"{fmt_euro(revenus)} entrés ({n_rev}) − "
            f"{fmt_euro(abs(depenses))} sortis ({n_dep})\n"
            f"{period_label(self.period)} — date {mode_lbl}")
        # Couleur dynamique pour mouvement net
        self._colorer_kpi("net", "#229954" if net >= 0 else "#C0392B")

        # Virgule décimale, comme partout ailleurs dans l'application : le
        # taux d'épargne était le seul chiffre à s'écrire « -10.6 % ».
        self.kpis["epargne"]._value.setText(
            f"{tx_epargne:.1f}".replace(".", ",") + " %")
        self._colorer_kpi("epargne", "#16A085" if tx_epargne >= 0 else "#C0392B")
        self.kpis["epargne"]._sub.setText(
            "part des revenus mis de côté" if tx_epargne >= 0
            else "dépenses supérieures aux revenus")

        self.kpis["pointe"]._value.setText(fmt_euro(solde_p_periode))
        # Couleur dynamique : vert si le solde pointé est positif, rouge s'il est négatif
        self._colorer_kpi("pointe", "#1A7A3A" if solde_p_periode >= 0 else "#C0392B")
        self.kpis["pointe"]._sub.setText(f"{n_pt} opération(s) pointée(s)")

        # ── Graphique en barres : douze mois ──────────────────────────
        # Il reçoit TOUTES les opérations, pas celles de la période : sur un
        # mois affiché, il ne dessinait qu'une seule barre.
        self._refresh_bar_chart(all_active)

        # ── Camembert dépenses ────────────────────────────────────────
        by_cat: dict[str, float] = {}
        for t in active:
            if t["montant"] >= 0:
                continue
            c = t.get("categorie", "Non classé")
            by_cat[c] = by_cat.get(c, 0) + abs(t["montant"])

        self.pie_chart.removeAllSeries()
        series = QPieSeries()
        series.setHoleSize(0.0)
        for c, amt in sorted(by_cat.items(), key=lambda x: x[1], reverse=True):
            s = series.append(f"{c}", amt)
            s.setBrush(QColor(cat_color(c)))
            # Le libellé d'une part sert de texte dans la LÉGENDE : on y met le
            # nom ET le montant. Écrire en plus ces montants autour du
            # camembert ferait doublon, et les textes longs (« Logement -
            # maison — -1 234,56 € ») débordent de la zone en se faisant
            # tronquer. Les chiffres sont donc lisibles dans la légende, le
            # camembert reste net.
            s.setLabel(f"{c} — {fmt_euro(-amt)}")
            s.setLabelVisible(False)
        self.pie_chart.addSeries(series)
        self.pie_chart.setTitle("")

        # ── Liste : dépenses par catégorie (top 8) ────────────────────
        total_dep = abs(depenses) or 1
        dep_items = []
        for c, amt in sorted(by_cat.items(), key=lambda x: x[1], reverse=True)[:8]:
            pct = amt / total_dep * 100
            dep_items.append((c, -amt, cat_color(c), f"{pct:.0f}%"))
        self.list_dep.set_items(dep_items)

        # ── Liste : sources de revenus ────────────────────────────────
        by_rev: dict[str, float] = {}
        for t in active:
            if t["montant"] <= 0:
                continue
            c = t.get("categorie", "Non classé")
            by_rev[c] = by_rev.get(c, 0) + t["montant"]
        rev_items = [(c, amt, cat_color(c))
                     for c, amt in sorted(by_rev.items(), key=lambda x: x[1], reverse=True)[:8]]
        self.list_rev.set_items(rev_items)

        # ── Liste : plus grosses dépenses individuelles ───────────────
        top = sorted([t for t in active if t["montant"] < 0],
                     key=lambda t: t["montant"])[:8]
        top_items = []
        for t in top:
            sub = fmt_date_fr(t["date"])[:5]  # "JJ/MM"
            top_items.append((t.get("libelle", "—")[:40], t["montant"],
                              cat_color(t.get("categorie", "")), sub))
        self.list_top.set_items(top_items)

    def _mois_du_graphique(self, actives: list[dict]) -> list[str]:
        """Les douze mois que montre le graphique, du plus ancien au plus
        récent.

        Il ne suit PAS la période affichée mois par mois : sur un mois, il ne
        montrerait qu'une seule barre — un quart de l'écran pour un chiffre
        déjà donné six fois ailleurs. Il montre toujours douze mois, ce qui
        répond à la seule question qu'un graphique peut traiter ici : est-ce
        que ça se dégrade ?

          • un mois choisi  → les douze mois qui s'achèvent sur lui, pour le
                              situer dans sa propre histoire ;
          • une année       → ses douze mois, de janvier à décembre ;
          • toutes périodes → les douze derniers mois.
        """
        if len(self.period) == 4:
            return [f"{self.period}-{m:02d}" for m in range(1, 13)]
        fin = (self.period if len(self.period) == 7
               else date.today().strftime("%Y-%m"))
        mois, m = [], fin
        for _ in range(12):
            mois.append(m)
            m = self._mois_precedent(m)
        mois.reverse()

        # Une base dont les données s'arrêtent il y a longtemps donnerait
        # douze mois vides : on retombe alors sur les douze derniers mois qui
        # portent quelque chose, plutôt que sur un graphique blanc.
        presents = {self._eff_date(t)[:7] for t in actives if self._eff_date(t)}
        if presents and not (set(mois) & presents):
            return sorted(presents)[-12:]
        return mois

    def _refresh_bar_chart(self, actives: list[dict]):
        """Barres mensuelles revenus / dépenses sur douze mois, en utilisant
        la date effective (opération ou valeur).

        Reçoit TOUTES les opérations actives, pas seulement celles de la
        période : le graphique choisit lui-même sa fenêtre."""
        months = self._mois_du_graphique(actives)
        if not months:
            self.bar_chart.removeAllSeries()
            return
        active = actives

        rev_by_month = {m: 0.0 for m in months}
        dep_by_month = {m: 0.0 for m in months}
        for t in active:
            m = self._eff_date(t)[:7]
            if m not in rev_by_month:
                continue
            if t["montant"] >= 0:
                rev_by_month[m] += t["montant"]
            else:
                dep_by_month[m] += abs(t["montant"])

        self.bar_chart.removeAllSeries()
        # Supprime les anciens axes
        for ax in self.bar_chart.axes():
            self.bar_chart.removeAxis(ax)

        bar_rev = QBarSet("Revenus")
        bar_dep = QBarSet("Dépenses")
        bar_rev.setColor(QColor("#229954"))
        bar_dep.setColor(QColor("#E67E22"))
        bar_rev.setBorderColor(QColor("#229954"))
        bar_dep.setBorderColor(QColor("#E67E22"))
        for m in months:
            # Montants arrondis à l'euro : c'est ce que porteront les
            # étiquettes, et à cette échelle les centimes n'apportent rien.
            bar_rev.append(round(rev_by_month[m]))
            bar_dep.append(round(dep_by_month[m]))

        series = QBarSeries()
        series.append(bar_rev); series.append(bar_dep)
        # Montant écrit sur chaque barre. Sans « € » : QtCharts rend mal ce
        # symbole dans les étiquettes (il sort en « ? »). Sans décimales non
        # plus — à cette échelle les centimes n'apportent rien et allongent
        # l'étiquette. Au-delà de 6 mois affichés, les barres deviennent trop
        # étroites pour porter un nombre lisible : on n'affiche plus rien.
        if len(months) <= 6:
            series.setLabelsVisible(True)
            series.setLabelsFormat("@value")
            # La précision compte les chiffres SIGNIFICATIFS (format « g ») :
            # à 0, QtCharts écrit « 5e+03 » au lieu de « 5076 ». On en laisse
            # largement assez ; les valeurs étant entières, rien ne s'ajoute
            # après la virgule.
            series.setLabelsPrecision(9)
            # Étiquette DANS la barre, près du sommet : au-dessus (OutsideEnd),
            # celle de la barre la plus haute sort de la zone de tracé et
            # disparaît. En blanc, lisible sur le vert comme sur l'orange.
            series.setLabelsPosition(QAbstractBarSeries.LabelsInsideEnd)
            bar_rev.setLabelColor(QColor("white"))
            bar_dep.setLabelColor(QColor("white"))
        self.bar_chart.addSeries(series)

        # Axe X : le mois seul. Sur douze colonnes, « Oct 25 » ne tient pas —
        # Qt tronquait en « Oc… », et réduire la police n'y changeait rien,
        # le découpage se faisant à la largeur de la colonne. L'année est
        # donc passée dans le TITRE du panneau, où elle a toute la place.
        mois_court = ["", "Jan", "Fév", "Mar", "Avr", "Mai", "Jun",
                      "Jul", "Aoû", "Sep", "Oct", "Nov", "Déc"]

        def _court(m: str) -> str:
            try:
                return mois_court[int(m[5:7])]
            except (ValueError, IndexError):
                return m

        labels = [_court(m) for m in months]
        self.bar_panel._header.setText(
            f"ÉVOLUTION SUR 12 MOIS — {_court(months[0]).upper()} "
            f"{months[0][:4]} → {_court(months[-1]).upper()} {months[-1][:4]}")
        ax_x = QBarCategoryAxis(); ax_x.append(labels)
        self.bar_chart.addAxis(ax_x, Qt.AlignBottom)
        series.attachAxis(ax_x)

        ax_y = QValueAxis()
        max_val = max(max(rev_by_month.values(), default=0),
                      max(dep_by_month.values(), default=0))
        ax_y.setRange(0, max_val * 1.1 if max_val > 0 else 1)
        # Pas de « € » dans le format de l'axe : QtCharts le rend en « ? »
        # (le symbole € est mal géré par setLabelFormat). L'axe reste en
        # nombres simples — le contexte (revenus/dépenses) suffit.
        ax_y.setLabelFormat("%d")
        self.bar_chart.addAxis(ax_y, Qt.AlignLeft)
        series.attachAxis(ax_y)
