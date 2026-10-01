"""Vue Bilan (tableau de bord)."""

import math
from calendar import monthrange
from datetime import date, timedelta
from html import escape as _esc   # noms de catégories insérés dans du HTML

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QColor, QCursor, QFontMetrics, QPainter, QPen,
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QFrame, QScrollArea, QToolTip,
)
from PySide6.QtCharts import (
    QChart, QChartView, QLegend, QPieSeries, QBarSeries, QBarSet, QLineSeries,
    QAbstractBarSeries, QBarCategoryAxis, QCategoryAxis,
)

from ...accords import accorde, pluriel
from ...utils import (
    carte_a_debit_differe, cat_color, de_mois_a_mois,
    depense_nette_par_categorie, est_paiement_carte,
    fmt_euro, fmt_date_fr, in_period, period_label, regle_debit_differe,
)
from ...csv_import import TYPE_CARTE, encours_carte_annonce
from ...database import Database
from ...labels import clean_libelle
from ...recurring import echeances_du_mois
from ...sauvegarde_externe import rappel_sauvegarde_externe
from ..avis import CLE_PREMIERE_UTILISATION
from ..models import EtatVide

# Jour de la dernière sauvegarde externe réussie (AAAA-MM-JJ), pour le
# bandeau de rappel (28/09/2026). Le préfixe « _meta_ » la tient à l'écart
# de la synchronisation, comme les dates d'avis.py.
CLE_DERNIERE_SAUVEGARDE = "_meta_sauvegarde_externe_derniere"

# Jour du mois à partir duquel on ose annoncer une tendance de fin de mois.
# Avant, le calcul est trompeur : une grosse course le 3 du mois annonçait
# 1 300 € pour un encours réel de 200 €.
JOUR_TENDANCE = 10

# Horizon de la recherche du prochain découvert. 45 jours plutôt que la fin du
# mois : le moment le plus risqué est souvent un prélèvement de début de mois
# (lot carte, loyer), et il faut voir la remontée des revenus qui arrivent
# derrière.
HORIZON_DECOUVERT = 45

class CatRowsWidget(QWidget):
    """Liste de lignes : pastille colorée + libellé + (% ou date) + montant.

    Les lignes sont posées dans une grille commune, et non chacune dans sa
    rangée indépendante : c'est ce qui aligne les quatre colonnes d'une ligne
    à l'autre — pastilles, libellés, pourcentages (ou dates) et montants se
    retrouvent tous sous les mêmes bords.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lay = QGridLayout(self)
        self.lay.setContentsMargins(8, 6, 8, 6)
        self.lay.setHorizontalSpacing(8)
        self.lay.setVerticalSpacing(4)
        # Seule la colonne du libellé s'étire ; les trois autres prennent la
        # largeur de leur contenu le plus large, donc restent alignées.
        self.lay.setColumnStretch(1, 1)
        self.lay.setColumnMinimumWidth(0, 14)   # colonne des pastilles
        self._nb_lignes = 0   # pour annuler l'étirement de la rangée du bas

    def set_items(self, items: list[tuple]):
        """items = list of (label, amount, color, optional_pct_or_date)."""
        # Reset
        while self.lay.count():
            it = self.lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.lay.setRowStretch(self._nb_lignes, 0)
        self._nb_lignes = 0
        if not items:
            self.lay.addWidget(QLabel("— Aucune donnée —"), 0, 0, 1, 4)
            self._nb_lignes = 1
            self.lay.setRowStretch(1, 1)   # le message reste en haut du cadre
            return
        for i, tup in enumerate(items):
            label = tup[0]; amount = tup[1]; color = tup[2]
            sub = tup[3] if len(tup) > 3 else None
            # Pastille : un vrai petit disque peint, et non le caractère « ● ».
            # Le glyphe se posait sur la ligne de base de sa propre police,
            # plus grande que celle du libellé, et sortait donc toujours un
            # peu au-dessus du texte de la ligne. Un disque, lui, se centre
            # exactement sur la hauteur de la ligne.
            dot = QWidget()
            # Taille impaire (9 px) : la hauteur d'une ligne l'est aussi, et
            # un disque pair y tombait un pixel trop haut, faute de milieu.
            dot.setFixedSize(9, 9)
            dot.setStyleSheet(f"background: {color}; border-radius: 4px;")
            self.lay.addWidget(dot, i, 0, Qt.AlignHCenter | Qt.AlignVCenter)
            lbl = QLabel(label)
            lbl.setTextFormat(Qt.PlainText)   # libellé affiché tel quel (jamais interprété)
            lbl.setStyleSheet("color:#222; background: transparent")
            self.lay.addWidget(lbl, i, 1)
            if sub:
                # Même correction de contraste que les sous-titres des tuiles :
                # ces pourcentages et ces dates se lisaient mal en gris pâle.
                s = QLabel(sub); s.setStyleSheet("color:#555; font-size:9pt; background: transparent")
                self.lay.addWidget(s, i, 2, Qt.AlignRight | Qt.AlignVCenter)
            amt = QLabel(fmt_euro(amount))
            amt.setStyleSheet(
                f"color: {'#C0392B' if amount < 0 else '#18733A'}; "
                "font-weight:600; background: transparent")
            self.lay.addWidget(amt, i, 3, Qt.AlignRight | Qt.AlignVCenter)
        # Une rangée vide et extensible en dessous : sans elle, la grille
        # étirerait les lignes pour remplir la hauteur du cadre.
        self._nb_lignes = len(items)
        self.lay.setRowStretch(self._nb_lignes, 1)


_MOIS_COURTS = ["", "Jan", "Fév", "Mar", "Avr", "Mai", "Jun",
                "Jul", "Aoû", "Sep", "Oct", "Nov", "Déc"]


def graduations_euros(bas: float, haut: float) -> list[tuple[int, str]]:
    """Graduations rondes d'un axe de montants, avec leur texte en euros :
    [(0, "0 €"), (1000, "1 000 €"), …]. Pas de 1, 2 ou 5 × 10ⁿ, environ
    cinq intervalles. L'axe tombait sur 654, 1309, 1963… sans unité
    (relecture du 30/09/2026)."""
    ecart = max(haut - bas, 1.0)
    brut = ecart / 5
    puissance = 10 ** math.floor(math.log10(brut))
    pas = next(c * puissance for c in (1, 2, 5, 10) if c * puissance >= brut)
    pas = max(int(round(pas)), 1)
    debut = math.floor(bas / pas) * pas
    fin = math.ceil(haut / pas) * pas
    valeurs = range(int(debut), int(fin) + 1, pas)
    return [(v, f"{v:,}".replace(",", "\xa0") + "\xa0€") for v in valeurs]


def axe_euros(bas: float, haut: float) -> QCategoryAxis:
    """Axe vertical gradué en euros. Un QCategoryAxis, dont chaque étiquette
    est écrite telle quelle : le format d'étiquette de QtCharts rendait le
    « € » en « ? »."""
    grad = graduations_euros(bas, haut)
    axe = QCategoryAxis()
    axe.setLabelsPosition(QCategoryAxis.AxisLabelsPositionOnValue)
    debut, fin = grad[0][0], grad[-1][0]
    axe.setRange(debut, fin)
    # La première étiquette porte sur la valeur de départ elle-même : la
    # catégorie qui la précède doit commencer juste en dessous.
    axe.setStartValue(debut - 1e-6 * max(fin - debut, 1))
    for valeur, texte in grad:
        axe.append(texte, valeur)
    # Sans cela, Qt remplace les étiquettes par « … » dès que le graphique
    # manque un peu de hauteur — elles tiennent pourtant (vérifié en image).
    axe.setTruncateLabels(False)
    return axe


def _mois_court(m: str) -> str:
    """« 2026-10 » → « Oct » : le nom du mois seul, pour les axes des
    graphiques (l'année va dans le titre du panneau)."""
    try:
        return _MOIS_COURTS[int(m[5:7])]
    except (ValueError, IndexError):
        return m


def _make_panel(title: str, body: QWidget) -> QFrame:
    """Carte stylée avec en-tête bleu + corps."""
    f = QFrame()
    # Le style vise la carte par son nom, et non « tout QFrame ». Sans cela il
    # descendait sur tous les QFrame qu'elle contient — or un QLabel EST un
    # QFrame : chaque libellé, chaque pourcentage et chaque montant se
    # retrouvait entouré du liseré gris de la carte.
    f.setObjectName("carteBilan")
    f.setStyleSheet("""
        QFrame#carteBilan {
            background: #FAF8F1; border: 1px solid #BEC7D4; border-radius: 4px;
        }
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
    goto_parametres = Signal()   # clic sur le bandeau du solde de départ
    goto_recul_depart = Signal()   # clic sur le bandeau des opérations antérieures
    sauvegarde_demandee = Signal()   # clic sur le bandeau de sauvegarde externe

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.period = "all"
        self.date_mode = "valeur"
        # Fond creme, celui de la fenetre, et cartes ivoire (#FAF8F1) : le
        # gris-bleu et le blanc pur d'avant juraient avec le reste de
        # l'application (demande de l'auteur, 25/09/2026 ; memes couleurs dans le
        # Photovoltaique et Recharges VE).
        self.setStyleSheet("BilanView { background: #ECE9D8; }")

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
        # le fond de la vue, sinon une bande claire apparaît sous le contenu.
        self.scroll.viewport().setStyleSheet("background: #ECE9D8;")
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
            ("net",      "Mouvement du mois",              "#1F3A6B"),
            ("epargne",  "Taux d'épargne",                 "#18733A"),
            ("pointe",   "✔ Mouvement pointé",             "#18733A"),
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
        # calendrier — un prélèvement qui passe avant l'arrivée des revenus.
        #
        # Il parle TOUJOURS du mois en cours, même quand on consulte un mois
        # passé : c'est un verdict pour agir, pas une fiche de consultation.
        #
        # Depuis le 01/10/2026, il est la première ligne du bandeau « Ce
        # mois-ci » (construit plus bas, posé ici) : deux bandeaux verts
        # superposés parlaient du même mois, et le solde de fin de mois s'y
        # lisait deux fois (relecture de design).
        self.verdict_banner = QLabel("")
        self.verdict_banner.setWordWrap(True)
        self.verdict_banner.setVisible(False)
        self.verdict_banner.setStyleSheet("font-size:10pt")

        # ── Bandeau du mois : le verdict, puis « Ce mois-ci » ─────────
        # La lecture du budget mensuel tenu sur papier : où le mois finit
        # (le verdict), ce qui doit encore tomber, et ce qui doit rentrer.
        # Le cadre prend la couleur du verdict : vert quand le compte tient,
        # rouge sinon (voir _poser_verdict).
        self.mois_banner = QFrame()
        # Style nommé (voir _make_panel) : sans cela, chaque étiquette du
        # bandeau se retrouvait encadrée, un QLabel étant lui aussi un QFrame.
        self.mois_banner.setObjectName("bandeauMois")
        self._colorer_bandeau_mois(True)
        mo_vertical = QVBoxLayout(self.mois_banner)
        mo_vertical.setContentsMargins(14, 6, 12, 6); mo_vertical.setSpacing(4)
        mo_vertical.addWidget(self.verdict_banner)

        # Seconde ligne : ce qui reste à passer. Masquée quand le mois n'a
        # aucune opération à montrer ; le verdict, lui, reste toujours.
        self.mois_ligne = QWidget()
        mo_lay = QHBoxLayout(self.mois_ligne)
        mo_lay.setContentsMargins(0, 0, 0, 0); mo_lay.setSpacing(18)

        self.mois_title = QLabel("🗓 CE MOIS-CI")
        self.mois_title.setStyleSheet("font-weight:bold; font-size:9pt")
        self.mois_title.setWordWrap(True)
        mo_lay.addWidget(self.mois_title)
        mo_lay.addSpacing(10)

        def _mini_vert(label_txt):
            w = QWidget(); l = QVBoxLayout(w); l.setContentsMargins(0,0,0,0); l.setSpacing(0)
            lbl = QLabel(label_txt); lbl.setStyleSheet("font-size:8pt")
            lbl.setWordWrap(True)
            val = QLabel("—"); val.setStyleSheet("color:#000000; font-size:12pt; font-weight:bold")
            l.addWidget(lbl); l.addWidget(val)
            return w, val, lbl

        # « Entrées / Sorties » : les mots de l'argent qui bouge sur le compte
        # (choix de l'auteur du 01/10/2026, tests/test_vocabulaire.py). Les
        # libellés perdent « à venir » sur un mois clos.
        # Un troisième bloc, « Solde au 31/10 », a été retiré le 01/10/2026 :
        # le verdict, juste au-dessus, donne ce chiffre en gras.
        m1, self.mois_sorties, self.mois_sorties_lbl = _mini_vert("Sorties à venir (hors carte)")
        m2, self.mois_entrees, self.mois_entrees_lbl = _mini_vert("Entrées à venir")
        mo_lay.addWidget(m1); mo_lay.addWidget(m2)
        mo_lay.addStretch()
        self.mois_detail = QLabel("")
        self.mois_detail_complet = ""      # tout le détail (infobulle)
        self.mois_detail.setStyleSheet("font-size:9pt")
        self.mois_detail.setWordWrap(True)
        mo_lay.addWidget(self.mois_detail)
        mo_vertical.addWidget(self.mois_ligne)
        main.addWidget(self.mois_banner)

        # ── Bandeau Encours Carte Bancaire ────────────────────────────
        self.cb_banner = QFrame()
        # Style nommé (voir _make_panel) : sans cela, chaque étiquette du
        # bandeau se retrouvait encadrée, un QLabel étant lui aussi un QFrame.
        self.cb_banner.setObjectName("bandeauCarte")
        self.cb_banner.setStyleSheet("""
            QFrame#bandeauCarte {
                     background: #FFFBE6;
                     border: 1px solid #E8D77B; border-radius: 4px; }
            QFrame#bandeauCarte QWidget { background: transparent; }
        """)
        cb_lay = QHBoxLayout(self.cb_banner)
        cb_lay.setContentsMargins(12, 4, 12, 4); cb_lay.setSpacing(18)

        self.cb_title = QLabel("💳 ENCOURS CARTE BANCAIRE")
        self.cb_title.setStyleSheet("font-weight:bold; color:#7E5109; font-size:9pt")
        # Repli sur deux lignes en fenêtre étroite (sinon le bandeau réclame
        # 1390 pixels de large et bloque le redimensionnement de la fenêtre).
        self.cb_title.setWordWrap(True)
        cb_lay.addWidget(self.cb_title)
        cb_lay.addSpacing(10)

        # 4 mini-blocs : confirmé / en cours / total à débiter / disponible
        def _mini(label_txt):
            w = QWidget(); l = QVBoxLayout(w); l.setContentsMargins(0,0,0,0); l.setSpacing(0)
            lbl = QLabel(label_txt); lbl.setStyleSheet("color:#7E5109; font-size:8pt")
            # Repli sur deux lignes, comme le titre : à quatre blocs, des
            # libellés d'un seul tenant imposeraient une fenêtre plus large
            # que la moitié d'écran sur laquelle André travaille.
            lbl.setWordWrap(True)
            val = QLabel("—"); val.setStyleSheet("color:#000000; font-size:12pt; font-weight:bold")
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
            "(vos opérations pointées) : le montant qu'elle annonce pour "
            "le prochain prélèvement de la carte.")
        self.cb_bloc2, self.cb_precedent, _ = _mini("Opérations en cours")
        self.cb_bloc2.setToolTip(
            "Opérations faites mais pas encore intégrées par la banque "
            "(non pointées). Ce peut être un achat comme un remboursement.")
        self.cb_bloc3, self.cb_total, self.cb_total_lbl = _mini("Total des achats à débiter")
        # Un quatrième bloc, « Reste pour la carte », a été retiré le
        # 08/09/2026 : quand le mois finit dans le rouge, il ne reste rien
        # pour aucune dépense, et un chiffre plancher à 0,00 € donnait
        # l'illusion d'un budget encore disponible. Ce qui manque — ou ce
        # qui reste — se lit en toutes lettres dans le détail, à droite.
        cb_lay.addWidget(self.cb_bloc1)
        cb_lay.addWidget(self.cb_bloc2)
        cb_lay.addWidget(self.cb_bloc3)
        cb_lay.addStretch()
        self.cb_detail = QLabel("")
        self.cb_detail_complet = ""      # tout le détail (infobulle)
        self.cb_detail.setStyleSheet("color:#7E5109; font-size:9pt")
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

        # ── Bandeau Alertes budget (mois en cours) ────────────────────
        # Masqué tant qu'aucune catégorie n'approche ou ne dépasse son budget.
        self.budget_alert = QLabel()
        self.budget_alert.setWordWrap(True)
        self.budget_alert.setTextFormat(Qt.RichText)
        self.budget_alert.setVisible(False)
        self.budget_alert.linkActivated.connect(lambda _l: self.goto_budget.emit())
        main.addWidget(self.budget_alert)

        # Bandeau du solde de départ. Tant qu'il n'a jamais été renseigné, le
        # « Solde bancaire réel » ne vaut que si le compte était vide à la date
        # de départ : rien ne le disait, et l'invite du premier lancement ne
        # revient plus dès qu'on l'a fermée une fois.
        self.solde_depart_alert = QLabel()
        self.solde_depart_alert.setWordWrap(True)
        self.solde_depart_alert.setTextFormat(Qt.RichText)
        self.solde_depart_alert.setVisible(False)
        self.solde_depart_alert.setStyleSheet(
            "QLabel { background:#FEF5E7; border:1px solid #E67E22; "
            "color:#7E5109; border-radius:4px; padding:8px 14px; }")
        self.solde_depart_alert.linkActivated.connect(
            lambda _l: self.goto_parametres.emit())
        main.addWidget(self.solde_depart_alert)

        # Bandeau des opérations antérieures à la date de départ. Elles
        # figurent dans les listes et les graphiques, mais sortent du calcul
        # du solde — un écart que rien n'expliquait à l'écran.
        self.hors_solde_alert = QLabel()
        self.hors_solde_alert.setWordWrap(True)
        self.hors_solde_alert.setTextFormat(Qt.RichText)
        self.hors_solde_alert.setVisible(False)
        self.hors_solde_alert.setStyleSheet(
            "QLabel { background:#FEF5E7; border:1px solid #E67E22; "
            "color:#7E5109; border-radius:4px; padding:8px 14px; }")
        self.hors_solde_alert.linkActivated.connect(
            lambda _l: self.goto_recul_depart.emit())
        main.addWidget(self.hors_solde_alert)

        # Bandeau de rappel de sauvegarde externe (28/09/2026) : au-delà de
        # 30 jours sans copie sur clé USB. Le lien lance la sauvegarde.
        self.sauvegarde_alert = QLabel()
        self.sauvegarde_alert.setWordWrap(True)
        self.sauvegarde_alert.setTextFormat(Qt.RichText)
        self.sauvegarde_alert.setVisible(False)
        self.sauvegarde_alert.setStyleSheet(
            "QLabel { background:#FEF5E7; border:1px solid #E67E22; "
            "color:#7E5109; border-radius:4px; padding:8px 14px; }")
        self.sauvegarde_alert.linkActivated.connect(
            lambda _l: self.sauvegarde_demandee.emit())
        main.addWidget(self.sauvegarde_alert)

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
        self.etat_barres = EtatVide(
            bar_view, "Aucune opération sur ces douze mois.\nImportez un "
            "relevé (📥 Importer un relevé, à gauche) pour voir vos revenus "
            "et vos dépenses mois par mois.", suivre_modele=False)
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
        self.pie_view = pie_view
        self.etat_camembert = EtatVide(
            pie_view, "Aucune dépense sur cette période.", suivre_modele=False)

        main.addLayout(mid_row, 1)

        # ── Courbe du solde en fin de mois (28/09/2026) ──────────────
        # Sur toute la largeur, sous les deux graphiques : les mêmes douze
        # mois que les barres. Trait plein pour ce qui est constaté,
        # pointillés pour ce qui est prévu.
        self.solde_chart = QChart()
        self.solde_chart.setBackgroundVisible(False)
        self.solde_chart.legend().setAlignment(Qt.AlignBottom)
        # Légende dessinée avec le trait de chaque courbe (plein, pointillé) :
        # deux carrés de la même couleur ne se distinguaient pas.
        self.solde_chart.legend().setMarkerShape(QLegend.MarkerShapeFromSeries)
        solde_view = QChartView(self.solde_chart)
        solde_view.setRenderHint(QPainter.Antialiasing)
        solde_view.setMinimumHeight(200)
        self.solde_panel = _make_panel("Solde en fin de mois", solde_view)
        self.etat_courbe = EtatVide(
            solde_view, "La courbe du solde apparaîtra avec vos premières "
            "opérations.", suivre_modele=False)
        main.addWidget(self.solde_panel, 1)
        self.soldes_de_la_courbe: list[tuple] = []

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
        # Style nommé : sinon le liseré gris ET le trait coloré de 3 px du
        # haut se répétaient sur le libellé, le montant et le sous-titre.
        f.setObjectName("tuileKpi")
        f.setStyleSheet(f"""
            QFrame#tuileKpi {{
                background: #FAF8F1; border: 1px solid #BEC7D4;
                border-top: 3px solid {color}; border-radius: 4px;
            }}
            QFrame#tuileKpi QLabel {{ background: transparent; }}
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
        f._label = l_label          # le titre du « Mouvement » suit la période
        return f

    def _legende_sans_coupure(self):
        """Réserve à la légende du camembert la largeur de son libellé le
        plus long, marqueur compris.

        Qt coupait la fin des libellés trop longs, c'est-à-dire le montant
        (« Logement - maison — -847,… ») : c'est le camembert qui rétrécit,
        pas les chiffres (relecture du 30/09/2026)."""
        legende = self.pie_chart.legend()
        mesure = QFontMetrics(legende.font())
        libelles = [m.label() for m in legende.markers()]
        if not libelles:
            legende.setMinimumWidth(0)
            self.pie_view.setMinimumHeight(240)
            return
        # En plus du texte : le carré de couleur (de la hauteur d'une ligne),
        # l'espace qui le suit et les marges de la légende — mesuré sur
        # l'image, 32 px fixes coupaient encore « -46,2… ».
        legende.setMinimumWidth(
            max(mesure.horizontalAdvance(t) for t in libelles)
            + 2 * mesure.height() + 30)
        # Et la hauteur de toutes ses lignes : à huit catégories et plus, la
        # dernière était rognée en bas du cadre (le Bilan défile, il peut
        # grandir).
        ligne = mesure.height() + 10
        self.pie_view.setMinimumHeight(max(240, len(libelles) * ligne + 60))

    @staticmethod
    def _titre_mouvement(period: str) -> str:
        """Titre de la tuile « Mouvement », accordé à la période choisie.

        Elle s'appelait « Mouvement du mois » même sur une année entière ou
        sur tout l'historique — ce que son propre sous-titre démentait."""
        if len(period) == 7:
            return "Mouvement du mois"
        if len(period) == 4:
            return "Mouvement de l'année"
        return "Mouvement — toutes périodes"

    @staticmethod
    def _couleur_du_signe(valeur: float):
        """Vert si positif, rouge si négatif, None si nul : un bilan nul
        s'écrit « 0,00 », sans couleur (charte ; relecture du 30/09/2026)."""
        if valeur > 0.005:
            return "#18733A"
        if valeur < -0.005:
            return "#C0392B"
        return None

    def _colorer_kpi(self, cle: str, couleur):
        """Recolore une tuile : le montant ET le liseré du haut, pour qu'ils
        s'accordent toujours (vert quand c'est positif, rouge quand ça ne l'est
        pas). `couleur` None : montant nul, en noir sur un liseré gris."""
        texte, trait = (couleur, couleur) if couleur else ("#000000", "#A9A9A9")
        carte = self.kpis[cle]
        carte.setStyleSheet(f"""
            QFrame#tuileKpi {{
                background: #FAF8F1; border: 1px solid #BEC7D4;
                border-top: 3px solid {trait}; border-radius: 4px;
            }}
            QFrame#tuileKpi QLabel {{ background: transparent; }}
        """)
        carte._value.setStyleSheet(f"color:{texte}; font-size:16pt; font-weight:bold")

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
        250 € » pendant que le bandeau voisin prévoyait un solde négatif en
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
                if t.get("date", "").startswith(mois) and t["montant"] < 0
                and not t.get("_annonce")]

    @staticmethod
    def _debites_apres_le_mois(achats: list[dict], mois: str) -> float:
        """Part des achats du mois que la banque prélèvera APRÈS sa fin.

        C'est elle, et elle seule, qu'il faut retrancher du solde de fin de
        mois : un achat prélevé avant la fin y est déjà compté. Chez André
        (lot le 4 du mois suivant), c'est la totalité des achats du mois ; au
        Crédit Agricole (lot le dernier jour ouvré, achats du 20 au 19), les
        achats de la fin du mois seulement."""
        an, m = int(mois[:4]), int(mois[5:7])
        fin_iso = date(an, m, monthrange(an, m)[1]).isoformat()
        return sum(t["montant"] for t in achats
                   if (t.get("date_valeur") or t.get("date", "")) > fin_iso)

    def _lot_annonce(self, txs: list[dict]) -> list[dict]:
        """Le lot carte annoncé par la banque, sous forme d'opération à venir.

        Le relevé du Crédit Agricole donne le montant du prochain prélèvement
        carte sans en détailler les achats. Pour que le Bilan le compte — dans
        l'encours, le solde de fin de mois et le prochain découvert —, on le
        présente comme une opération carte confirmée, datée du jour du
        prélèvement. Elle n'est jamais enregistrée.

        Rien si le lot est déjà prélevé, ou si son détail a été importé depuis
        (des achats carte portent alors sa date de débit)."""
        lot = encours_carte_annonce(self.db)
        if not lot or lot.get("debit", "") < date.today().isoformat():
            return []
        if any(est_paiement_carte(t.get("type"))
               and t.get("date_valeur") == lot["debit"] for t in txs):
            return []
        return [{
            "id": "lot-carte-annonce", "date": lot.get("releve", ""),
            "date_valeur": lot["debit"],
            "libelle": "Achats carte annoncés par la banque",
            "libelle_op": "", "reference": "", "type": TYPE_CARTE,
            "categorie": "Non classé", "sous_cat": "", "info": "",
            "montant": float(lot["montant"]), "pointee": 1, "prevue": 0,
            "_annonce": True,
        }]

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

        Le montant total d'un mois ne répond pas à cette question : le creux
        vient souvent de l'ordre des dates — un prélèvement qui passe avant
        l'arrivée des revenus."""
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

    def _mouvements_du_mois(self, txs: list[dict], mois: str) -> list[tuple]:
        """Ce qui a réellement bougé sur le compte pendant un mois CLOS.

        Mêmes opérations que le solde bancaire : celles que la banque a
        confirmées (pointées), prises à leur date de valeur — le jour où elle
        débite ou crédite vraiment. Le mois est fini : plus rien n'y est « à
        venir », tout y est passé. Chaque ligne a la forme des autres bandeaux :
        (date, libellé, montant, est_carte)."""
        an, m = int(mois[:4]), int(mois[5:7])
        debut = date(an, m, 1).isoformat()
        fin = date(an, m, monthrange(an, m)[1]).isoformat()
        return [(self._date_banque(t), t.get("libelle", ""), t["montant"],
                 est_paiement_carte(t.get("type")))
                for t in txs
                if t.get("categorie") != "Transaction exclue" and t.get("pointee")
                and debut <= self._date_banque(t) <= fin]

    def _creux_du_mois(self, txs: list[dict], mois: str,
                       solde_compte: float) -> tuple[str, float]:
        """Le point le plus bas d'un mois CLOS, et le jour où il tombe.

        On repart du solde constaté à la fin du mois précédent, puis on rejoue
        les mouvements du mois dans l'ordre des dates : le total du mois ne
        dirait pas si le compte a plongé en cours de route — le creux vient
        souvent de l'ordre des dates, un prélèvement partant avant l'arrivée
        des revenus."""
        debut = date(int(mois[:4]), int(mois[5:7]), 1).isoformat()
        solde = self._solde_fin_de_mois(
            txs, self._mois_precedent(mois), solde_compte)
        creux = (debut, solde)
        for d, _lbl, montant, _c in sorted(self._mouvements_du_mois(txs, mois),
                                           key=lambda x: x[0]):
            solde += montant
            if solde < creux[1]:
                creux = (d, solde)
        return creux

    def _poser_detail_carte(self, principal: str, complet: str):
        """Détail du bandeau Encours carte : à l'écran, la phrase qui compte
        (« il reste… ») ; le reste au survol du bandeau. Cinq lignes en
        petits caractères en faisaient l'élément le plus dense de l'écran
        (choix de l'auteur du 01/10/2026). `cb_detail_complet` garde le tout."""
        self.cb_detail_complet = complet
        self.cb_detail.setText(principal + "\nDétail au survol du bandeau.")
        self.cb_banner.setToolTip(complet)
        self.cb_detail.setToolTip(complet)

    def _colorer_bandeau_mois(self, ok: bool):
        """Couleurs du bandeau du mois : vert quand le compte tient, rouge
        (bandeau de danger de la charte) sinon. Le texte des étiquettes suit
        le cadre ; les montants gardent leur noir."""
        fond, cadre, texte = (("#EAF6EC", "#229954", "#1A5E32") if ok
                              else ("#FDEDEB", "#E74C3C", "#7B241C"))
        self.mois_banner.setStyleSheet(f"""
            QFrame#bandeauMois {{
                     background: {fond};
                     border: 1px solid {cadre}; border-radius: 4px; }}
            QFrame#bandeauMois QWidget {{ background: transparent; }}
            QFrame#bandeauMois QLabel {{ color: {texte}; }}
        """)

    def _poser_verdict(self, texte: str, ok: bool):
        """Écrit le verdict et colore son bandeau : vert quand le compte
        tient."""
        self._colorer_bandeau_mois(ok)
        self.verdict_banner.setText(texte)
        self.verdict_banner.setVisible(True)

    def _poser_detail_mois(self, principal: str, complet: str):
        """Détail du bandeau du mois : à l'écran, la phrase qui compte ; le
        reste au survol du bandeau, comme pour l'Encours carte (relecture de
        design du 01/10/2026). `mois_detail_complet` garde le tout."""
        self.mois_detail_complet = complet
        texte = principal
        if complet.strip() != principal.strip():
            texte += "\nDétail au survol du bandeau."
        self.mois_detail.setText(texte)
        self.mois_banner.setToolTip(complet)
        self.mois_detail.setToolTip(complet)

    def _refresh_verdict_banner(self, txs: list[dict], solde_compte: float):
        """La réponse en une phrase : où le mois finit, et quand le compte
        passe sous zéro.

        Toujours affichée, verte quand le compte tient : une absence de
        message se lirait comme un calcul qui n'a pas été fait. Elle suit la
        période choisie (voir _mois_du_bandeau), en changeant de temps avec
        elle : un mois clos se raconte au passé — où il a fini, jusqu'où il est
        descendu — un mois à venir se dit au conditionnel, et le mois en cours
        reste un verdict pour agir, tourné vers le prochain découvert."""
        mois, _consultation = self._mois_du_bandeau()
        solde_fin = self._solde_fin_de_mois(txs, mois, solde_compte)
        an, m = int(mois[:4]), int(mois[5:7])
        fin_mois = date(an, m, monthrange(an, m)[1])
        today = date.today()

        if fin_mois < today:                      # mois clos : consultation
            creux_date, creux_solde = self._creux_du_mois(txs, mois, solde_compte)
            texte = (f"{'✅' if creux_solde >= 0 else '🚨'} "
                     f"<b>{period_label(mois)}</b> : le compte a fini le mois à "
                     f"<b>{fmt_euro(solde_fin)}</b>. Au plus bas : "
                     f"<b>{fmt_euro(creux_solde)}</b> "
                     f"le {fmt_date_fr(creux_date)}.")
            self._poser_verdict(texte, creux_solde >= 0)
            return

        if mois > today.strftime("%Y-%m"):        # mois à venir : projection
            texte = (f"{'✅' if solde_fin >= 0 else '🚨'} "
                     f"<b>{period_label(mois)}</b> : au vu de ce qui est déjà "
                     f"prévu, le compte finirait le mois à "
                     f"<b>{fmt_euro(solde_fin)}</b>.")
            self._poser_verdict(texte, solde_fin >= 0)
            return

        info = self._prochain_decouvert(txs, solde_compte)
        bascule, (creux_date, creux_solde) = info["bascule"], info["creux"]

        debut = (f"<b>{period_label(mois)}</b> : le compte finit le mois à "
                 f"<b>{fmt_euro(solde_fin)}</b>")

        if bascule is None:
            # « reste positif jusqu'au… » laissait croire à un découvert le
            # lendemain : cette date n'est que la limite du calcul.
            texte = (f"✅ {debut}, aucun découvert prévu d'ici le "
                     f"{fmt_date_fr(info['fin'])} — au plus bas "
                     f"{fmt_euro(creux_solde)} le {fmt_date_fr(creux_date)}.")
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

        self._poser_verdict(texte, bascule is None)

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
        if not carte_a_debit_differe(cartes):
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
        engage_mois = self._debites_apres_le_mois(achats_mois, mois)
        # Date(s) où la banque prélève les achats du mois : celles que portent
        # les achats eux-mêmes. Au Crédit Agricole, les achats du 20 au 19
        # partent le dernier jour ouvré : un mois se prélève donc en deux fois.
        # À défaut, le calendrier des achats carte passés du compte.
        debits = sorted({t.get("date_valeur", "") for t in achats_mois
                         if t.get("date_valeur", "") > t.get("date", "")})
        if not debits:
            debits = [regle_debit_differe(cartes)(f"{mois}-01")]

        self.cb_total.setStyleSheet(
            "color:#000000; font-size:12pt; font-weight:bold")

        # ── Ce que le mois laisse, une fois tout payé ─────────────────
        # Le solde de fin de mois moins les achats carte déjà engagés. Il n'a
        # plus de bloc à lui : il sert aux phrases du détail (« il MANQUE »,
        # « il reste ») et au verdict du mois précédent.
        solde_ref = solde_compte if solde_compte is not None else 0.0
        disponible = self._reste_du_mois(txs, mois, solde_ref, engage_mois)

        # ── Verdict du mois précédent ─────────────────────────────────
        # Le reste descend au fil du mois, mais rien ne disait ensuite si le
        # mois était passé, ni de combien il avait débordé : il fallait aller
        # le chercher en changeant de période.
        precedent = self._mois_precedent(mois)
        achats_prec = self._achats_du_mois(cartes, precedent)
        depense_prec = abs(sum(t["montant"] for t in achats_prec))
        reste_prec = self._reste_du_mois(
            txs, precedent, solde_ref,
            self._debites_apres_le_mois(achats_prec, precedent))
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
                "color:#000000; font-size:12pt; font-weight:bold")
            self.cb_title.setText(
                f"💳 ENCOURS CARTE — {period_label(mois).upper()} "
                "(prélevé le "
                + " et le ".join(fmt_date_fr(d) for d in debits) + ")")
            detail = (f"{pluriel(len(achats_mois), 'achat', 'achats')} par carte sur le mois — "
                      + (f"il a MANQUÉ {fmt_euro(-disponible)}" if disponible < 0
                         else f"il restait {fmt_euro(disponible)}")
                      + " une fois tout payé")
            principal = detail
            detail += verdict
            detail += "\nConsultation : le bandeau suit la période choisie."
            self._poser_detail_carte(principal, detail)
            # Un mois sans un seul achat par carte n'a pas de bandeau à montrer.
            self.cb_banner.setVisible(bool(achats_mois))
            return

        self.cb_total_lbl.setText("Total des achats à débiter")
        titre = "💳 ENCOURS CARTE BANCAIRE"
        if prochaine:
            titre += f" — prochain prélèvement le {fmt_date_fr(prochaine)}"
        self.cb_title.setText(titre)

        detail = (f"{pluriel(len(confirmes), 'confirmée', 'confirmées')}  •  {len(en_cours)} en cours"
                  f"  •  {len(lot)} au total sur ce prélèvement")
        # La phrase qui porte, depuis la suppression du quatrième bloc, ce
        # que le mois laisse : le solde qu'aura le compte à la fin du mois
        # une fois tout passé, moins ce qui est déjà engagé sur la carte.
        solde_fin = self._solde_fin_de_mois(txs, mois, solde_ref)
        reste = (f"il MANQUE {fmt_euro(-disponible)}" if disponible < 0
                 else f"il reste {fmt_euro(disponible)}")
        if engage_mois:
            principal = (f"Solde prévu fin de mois {fmt_euro(solde_fin)} moins "
                         f"{fmt_euro(abs(engage_mois))} déjà passés à la carte — "
                         + reste)
        else:
            # « moins 0,00 € » : une soustraction de zéro qui ne disait rien
            # (relecture de design du 01/10/2026).
            principal = f"À la fin du mois, {reste}"
        detail += "\n" + principal
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
        annonces = [t for t in lot if t.get("_annonce")]
        if annonces:
            detail += (f"\nDont {fmt_euro(annonces[0]['montant'])} annoncés par "
                       f"la banque sur le relevé du "
                       f"{fmt_date_fr(annonces[0]['date'])}, sans le détail "
                       "des achats")
        detail += verdict
        if plus_tard:
            detail += (f"  •  {pluriel(len(plus_tard), 'opération', 'opérations')} au-delà "
                       f"({fmt_euro(sum(t['montant'] for t in plus_tard))})")
        if solde_compte is not None:
            # Chiffre mis en avant par la banque sous « Opérations carte en
            # cours » : il permet de rapprocher les deux écrans d'un coup d'œil.
            detail += ("\nSolde incluant les opérations carte en cours : "
                       + fmt_euro(solde_compte + somme_en_cours))
        self._poser_detail_carte(principal, detail)

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
        # Carte à débit IMMÉDIAT : un achat carte sort le jour même, comme
        # n'importe quelle dépense. Seule une carte à débit différé met ses
        # achats de côté pour un prélèvement groupé.
        differe = carte_a_debit_differe(txs)

        def carte_differee(t: dict) -> bool:
            return differe and est_paiement_carte(t.get("type"))

        # 1) Opérations déjà enregistrées dont le débit tombe dans la fenêtre.
        #    Avec une carte à débit différé, les opérations CARTE non pointées
        #    sont écartées : la banque ne les a pas encore rattachées au
        #    prochain prélèvement, elles partiront au suivant. Les compter ici fausserait le montant du débit — un
        #    remboursement carte « en cours » ne réduit pas le prélèvement de ce
        #    mois-ci. Les opérations non-carte, elles, ne sont jamais pointées
        #    avant leur passage : on les garde toutes.
        #    Une opération pointée dont la date de valeur est déjà passée est
        #    exclue : elle compte déjà dans le solde bancaire, l'ajouter la
        #    ferait compter deux fois.
        reelles = [t for t in actives
                   if debut_iso <= dv(t) <= fin_iso
                   and not (carte_differee(t) and not t.get("pointee"))
                   and not (t.get("pointee") and dv(t) <= today_iso)]
        en_cours_carte = [t for t in actives
                          if carte_differee(t) and not t.get("pointee")
                          and dv(t) > today_iso]
        # Libellés déjà couverts : leur récurrence ne doit pas être recomptée
        deja = {clean_libelle(t.get("libelle", "")) for t in reelles
                if not carte_differee(t)}

        lignes = [(dv(t), t.get("libelle", ""), t["montant"], carte_differee(t))
                  for t in reelles]
        return lignes, en_cours_carte, deja

    def _echeances_non_couvertes(self, txs: list[dict], depuis: date,
                                 jusqua: date) -> list[dict]:
        """Échéances du Prévisionnel qu'aucune opération ne couvre encore,
        entre deux dates.

        S'appuie sur le rapprochement de « Générer les échéances du mois » :
        il reconnaît une pension déjà encaissée sous un libellé un peu
        différent, là où une comparaison stricte l'annoncerait une seconde
        fois. Les deux écrans disent ainsi la même chose.

        Chaque échéance porte `_debit`, le jour où elle sort vraiment du
        compte, et `_carte`. Une échéance payée par une carte à DÉBIT DIFFÉRÉ
        ne sort pas le jour de l'achat mais avec le lot carte du mois suivant
        (regle_debit_differe) : c'est ce jour-là qui décide si elle tombe dans
        la fenêtre. Incident du 23/09/2026 : un abonnement carte du 1er était
        retranché le 01/10 alors qu'il partait avec le lot de novembre."""
        recs = [dict(r) for r in self.db.list_recurring()]
        debut_iso, fin_iso = depuis.isoformat(), jusqua.isoformat()
        differe = carte_a_debit_differe(txs)
        dater_carte = regle_debit_differe(txs)
        out = []
        # Chaque mois de la fenêtre, du premier au dernier. Seuls ces deux-là
        # étaient consultés : passé le 17, les 45 jours du prochain découvert
        # couvrent trois mois, et les échéances du mois du milieu étaient
        # ignorées (audit du 23/09/2026). Avec une carte à débit différé, on
        # part du mois d'avant : ses achats carte sont débités dans la fenêtre.
        annee, mois = depuis.year, depuis.month
        if differe:
            annee, mois = (annee - 1, 12) if mois == 1 else (annee, mois - 1)
        while (annee, mois) <= (jusqua.year, jusqua.month):
            for e in echeances_du_mois(recs, txs, annee, mois):
                if e["_deja"]:
                    continue
                e["_carte"] = differe and est_paiement_carte(e.get("type"))
                e["_debit"] = (dater_carte(e["date"]) if e["_carte"]
                               else e["date"])
                if debut_iso <= e["_debit"] <= fin_iso:
                    out.append(e)
            annee, mois = (annee + 1, 1) if mois == 12 else (annee, mois + 1)
        return out

    def _lignes_a_venir(self, txs: list[dict], depuis: date,
                        jusqua: date) -> tuple[list[tuple], list[dict]]:
        """Les opérations à venir, complétées par les échéances du
        Prévisionnel qui n'ont pas encore d'opération correspondante."""
        lignes, en_cours_carte, _deja = self._operations_a_venir(
            txs, depuis, jusqua)
        for e in self._echeances_non_couvertes(txs, depuis, jusqua):
            lignes.append((e["_debit"], e["libelle"], e["montant"], e["_carte"]))
        return lignes, en_cours_carte

    def _refresh_mois_banner(self, txs: list[dict], solde_compte: float):
        """Le mois choisi en deux chiffres : ce qui sort et ce qui rentre. Le
        solde à la fin est donné par le verdict, en tête du même bandeau.

        C'est la lecture du budget mensuel tenu sur papier. Le bandeau suit la
        période choisie (voir _mois_du_bandeau) et change de sens avec elle :

          • mois EN COURS — ce qui reste à passer d'ici le dernier jour ; la
            fenêtre part du 1er, donc une échéance du 5 encore en attente
            reste comptée ;
          • mois CLOS — ce qui est passé, tel que la banque l'a enregistré ;
          • mois À VENIR — ce qui est déjà prévu pour ce mois-là.

        Le solde de fin du verdict et du bandeau carte vient de
        `_solde_fin_de_mois` : les deux ne peuvent pas se contredire.

        Depuis le 07/09/2026, ce bandeau est le seul de sa sorte : celui des
        15 jours a été retiré, et ses deux apports — les prochaines échéances
        nommées et les opérations carte en cours — ont été repris ici."""
        today = date.today()
        mois, _consultation = self._mois_du_bandeau()
        an, m = int(mois[:4]), int(mois[5:7])
        debut = date(an, m, 1)
        fin = date(an, m, monthrange(an, m)[1])
        clos = fin < today
        a_venir = mois > today.strftime("%Y-%m")

        if clos:
            lignes, en_cours_carte = self._mouvements_du_mois(txs, mois), []
        else:
            lignes, en_cours_carte = self._lignes_a_venir(txs, debut, fin)

        carte = sum(m_ for _d, _l, m_, c in lignes if c)
        sorties = sum(m_ for _d, _l, m_, c in lignes if not c and m_ < 0)
        entrees = sum(m_ for _d, _l, m_, c in lignes if not c and m_ > 0)

        self.mois_sorties.setText(fmt_euro(sorties))
        self.mois_entrees.setText(fmt_euro(entrees))
        # Les libellés se mettent au passé sur un mois fini.
        self.mois_sorties_lbl.setText(
            "Sorties (hors carte)" if clos else "Sorties à venir (hors carte)")
        self.mois_entrees_lbl.setText("Entrées" if clos else "Entrées à venir")

        if clos:
            self.mois_title.setText(
                f"🗓 {period_label(mois).upper()} — ce qui est passé")
        elif a_venir:
            self.mois_title.setText(
                f"🗓 {period_label(mois).upper()} — ce qui est prévu "
                f"d'ici le {fmt_date_fr(fin.isoformat())}")
        else:
            self.mois_title.setText(
                f"🗓 CE MOIS-CI — reste à passer d'ici le {fmt_date_fr(fin.isoformat())}")

        n_sorties = sum(1 for _d, _l, m_, c in lignes if not c and m_ < 0)
        n_entrees = sum(1 for _d, _l, m_, c in lignes if not c and m_ > 0)
        detail = (f"{pluriel(n_sorties, 'sortie', 'sorties') if n_sorties else 'aucune sortie'}"
                  f"  ·  {pluriel(n_entrees, 'entrée', 'entrées') if n_entrees else 'aucune entrée'}")
        if carte:
            jour_carte = min((d for d, _l, _m, c in lignes if c), default="")
            detail += (f"  ·  débit carte {fmt_euro(carte)}"
                       + (f" le {fmt_date_fr(jour_carte)}" if jour_carte else ""))
        if en_cours_carte:
            # Écartées du calcul : elles iront au prélèvement d'après.
            somme = sum(t["montant"] for t in en_cours_carte)
            detail += (f"  ·  {pluriel(len(en_cours_carte), 'opération', 'opérations')} carte en cours "
                       f"({fmt_euro(somme)}) au prélèvement suivant")
        if not clos:
            # Part déjà saisie en opérations (⏳) : le reste vient du
            # Prévisionnel et n'existe pas encore dans la liste des opérations.
            debut_iso, fin_iso = debut.isoformat(), fin.isoformat()
            n_prevues = sum(
                1 for t in txs
                if t.get("prevue") and not t.get("pointee")
                and debut_iso <= (t.get("date_valeur") or t.get("date", "")) <= fin_iso)
            if n_prevues:
                detail += (f"  ·  dont {pluriel(n_prevues, 'échéance', 'échéances')} "
                          f"déjà {accorde(n_prevues, 'saisie', 'saisies')} ⏳")
            # Les trois prochaines échéances, pour situer. Elles venaient du
            # bandeau des 15 jours : ne comptant que ce qui est ENCORE à venir,
            # elles gardent tout leur sens dans une fenêtre qui part du 1er.
            today_iso = today.isoformat()
            suivantes = sorted((l for l in lignes if not l[3] and l[0] >= today_iso),
                               key=lambda x: x[0])[:3]
            prochaines = ""
            if suivantes:
                prochaines = "Prochaines : " + "  ·  ".join(
                    f"{fmt_date_fr(d)[:5]} {lbl[:22]} {fmt_euro(m_)}"
                    for d, lbl, m_, _c in suivantes)
                detail += "\n" + prochaines
            detail += f"\nSolde en banque aujourd'hui : {fmt_euro(solde_compte)}"
            # À l'écran, ce qui arrive : les prochaines échéances. Le compte
            # des opérations et le solde du jour (déjà dans la tuile) passent
            # au survol.
            principal = prochaines or detail.split("\n")[0]
        else:
            detail += "\nConsultation : le bandeau suit la période choisie."
            principal = detail.split("\n")[0]
        self._poser_detail_mois(principal, detail)

        # Le verdict reste toujours ; seule la ligne du mois s'efface quand
        # le mois n'a aucune opération à montrer.
        self.mois_ligne.setVisible(bool(lignes))

    def _refresh_budget_alert(self, txs: list[dict]):
        """Catégories dont les dépenses dépassent le budget mensuel (rouge) ou
        en approchent ≥ 85 % (orange). Masqué si tout va bien.

        Le bandeau suit la période choisie en haut, comme celui de l'Encours
        carte (voir _mois_du_bandeau) : choisir « Août 2026 » montre ce qui a
        été dépassé en août. Une année ou « Toutes périodes » ne désignent
        aucun mois — un budget mensuel ne se juge qu'au mois — et le bandeau
        revient alors au mois en cours, le seul où l'on peut encore agir."""
        budgets = self.db.list_budgets()
        if not budgets:
            self.budget_alert.setVisible(False)
            return
        month, consultation = self._mois_du_bandeau()
        # Date d'ACHAT, comme l'onglet Budget vers lequel l'alerte renvoie
        # (voir BudgetView._eff_date) : sinon les deux écrans annonceraient
        # des dépenses différentes, et le lot de la carte à débit différé,
        # parti le 4, ferait déborder les budgets du mois suivant. Les
        # remboursements viennent en déduction, comme dans l'onglet Budget.
        spent = depense_nette_par_categorie(
            [t for t in txs if t.get("date", "").startswith(month)])

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
            # Un mois clos se raconte au passé, et il faut dire lequel : sinon
            # « ce mois-ci » ferait prendre les dépassements d'août pour ceux
            # de septembre.
            titre = (f"Budget dépassé en {period_label(month).lower()}"
                     if consultation else "Budget dépassé ce mois-ci")
            parts.append(f"🚨 <b>{titre} :</b> " + _fmt(depasses))
        if proches:
            titre = "Tout près du budget" if consultation else "Bientôt atteint"
            parts.append(f"⚠️ <b>{titre} :</b> " + _fmt(proches))
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
    def _refresh_solde_depart_alert(self):
        """Prévient tant que le solde de départ n'a jamais été enregistré.

        On distingue « jamais renseigné » d'un vrai zéro : la colonne
        `solde_initial` du compte vaut NULL dans le premier cas."""
        compte = self.db.get_compte()
        renseigne = compte is not None and compte["solde_initial"] is not None
        if renseigne:
            self.solde_depart_alert.setVisible(False)
            return
        debut = ("&#9888; <b>Solde de départ non renseigné.</b> Le solde "
                 "affiché ci-dessus n'additionne que vos opérations. ")
        bornes = self.db.bornes_operations()
        if bornes is None:
            texte = (debut + "Indiquez le solde de votre compte aujourd'hui "
                     "— <a href='#'>Paramètres</a>.")
        else:
            # Conseiller le solde « au 1er janvier » faisait taper le solde
            # du jour à une date où il ne valait pas (audit du 23/09/2026).
            # Le bon repère est la dernière opération : c'est la question
            # que pose le lien.
            texte = (debut + "Indiquez le solde de votre compte le "
                     + fmt_date_fr(bornes[1]) + ", jour de votre dernière "
                     "opération : Pécule en déduira la date et le solde de "
                     "départ — <a href='#'>Indiquer le solde</a>.")
        self.solde_depart_alert.setText(texte)
        self.solde_depart_alert.setVisible(True)

    def _refresh_hors_solde_alert(self, txs: list[dict]):
        """Signale les opérations plus anciennes que la date de départ.

        Le solde bancaire ne compte que ce qui suit cette date : le total
        d'avant est réputé compris dans le solde de départ. Qui importe son
        historique complet sans reculer la date voit donc un solde faux, sans
        rien pour le lui dire.

        On compare la DATE DE VALEUR, celle qu'utilise le calcul du solde :
        un achat par carte de décembre débité le 4 janvier compte bien dans
        un solde qui part du 1er janvier, il ne faut pas le signaler."""
        depart = self.db.get_setting("initial_date", "")
        avant = [t for t in txs
                 if t.get("categorie") != "Transaction exclue"
                 and self._date_banque(t) < depart]
        if not avant:
            self.hors_solde_alert.setVisible(False)
            return
        total = sum(t.get("montant", 0) for t in avant)
        n = len(avant)
        self.hors_solde_alert.setText(
            f"&#9888; <b>{pluriel(n, 'opération', 'opérations')} "
            f"{accorde(n, 'antérieure', 'antérieures')} au "
            f"{fmt_date_fr(depart)}</b>, la date de départ du compte : "
            f"{accorde(n, 'son montant', 'leur total')} "
            f"({fmt_euro(total)}) <b>n'entre pas</b> dans le solde "
            "ci-dessus — il est censé être déjà compris dans le solde de "
            "départ. Pour les compter sans changer le solde d'aujourd'hui : "
            "<a href='#'>reculer la date de départ</a>.")
        self.hors_solde_alert.setVisible(True)

    def _refresh_sauvegarde_alert(self):
        """Rappelle la sauvegarde externe au-delà de 30 jours (texte commun
        aux trois applications). Jamais faite : on compte depuis la première
        utilisation de Pécule."""
        texte = rappel_sauvegarde_externe(
            self.db.get_setting(CLE_DERNIERE_SAUVEGARDE) or None,
            self.db.get_setting(CLE_PREMIERE_UTILISATION) or None)
        if not texte:
            self.sauvegarde_alert.setVisible(False)
            return
        self.sauvegarde_alert.setText(
            "&#128190; " + _esc(texte)
            + " <a href='#'>Faire une sauvegarde externe</a>.")
        self.sauvegarde_alert.setVisible(True)

    def refresh(self):
        txs = [dict(r) for r in self.db.list_tx()]
        self._refresh_budget_alert(txs)
        self._refresh_solde_depart_alert()
        self._refresh_hors_solde_alert(txs)
        self._refresh_sauvegarde_alert()

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
        # Analyses (taux d'épargne, graphiques, répartition) : sans la
        # catégorie « Épargne ». Mettre de côté n'est pas dépenser : le
        # virement vers le livret faisait BAISSER le taux d'épargne (choix
        # d'André après l'audit du 23/09/2026). La tuile « Mouvement », qui
        # dit ce qui a bougé sur le compte, garde tout.
        analyse = [t for t in active if t.get("categorie") != "Épargne"]
        rev_a = sum(t["montant"] for t in analyse if t["montant"] > 0)
        dep_a = sum(t["montant"] for t in analyse if t["montant"] < 0)
        tx_epargne = ((rev_a + dep_a) / rev_a * 100) if rev_a > 0 else 0
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
        # Le lot carte annoncé par la banque (Crédit Agricole) n'entre que
        # dans ces prévisions, jamais dans les dépenses ni les graphiques.
        txs_prevus = txs + self._lot_annonce(txs)
        self._refresh_verdict_banner(txs_prevus, solde_compte)
        self._refresh_cb_banner(txs_prevus, solde_compte)
        self._refresh_mois_banner(txs_prevus, solde_compte)

        n_rev = sum(1 for t in active if t["montant"] > 0)
        n_dep = sum(1 for t in active if t["montant"] < 0)
        n_pt  = sum(1 for t in active if t.get("pointee"))

        mode_lbl = "valeur (banque)" if self.date_mode == "valeur" else "opération"
        self.kpis["solde"]._value.setText(fmt_euro(solde_compte))
        self._colorer_kpi("solde", self._couleur_du_signe(solde_compte))
        sub = (f"Au {fmt_date_fr(today_iso)} — initial {fmt_euro(initial_balance)} + "
               f"{pluriel(len(pointees_up), 'opération', 'opérations')} "
               f"{accorde(len(pointees_up), 'pointée', 'pointées')} — toujours en date de valeur "
               "(banque), encours carte non compris")
        if non_pointees_up:
            n = len(non_pointees_up)
            sub += (f"  •  {pluriel(n, 'opération', 'opérations')} non "
                    f"{accorde(n, 'pointée', 'pointées')} "
                    f"{accorde(n, 'ignorée', 'ignorées')} "
                    f"({fmt_euro(montant_en_attente)}) — engagé : {fmt_euro(solde_engage)}")
        self.kpis["solde"]._sub.setText(sub)

        net = net_periode
        self.kpis["net"]._label.setText(self._titre_mouvement(self.period))
        self.kpis["net"]._value.setText(fmt_euro(net))
        # Les deux moitiés du mouvement, là où elles occupaient deux tuiles.
        self.kpis["net"]._sub.setText(
            f"{fmt_euro(revenus)} entrés ({n_rev}) − "
            f"{fmt_euro(abs(depenses))} sortis ({n_dep})\n"
            f"{period_label(self.period)} — date {mode_lbl}")
        # Couleur dynamique pour mouvement net
        self._colorer_kpi("net", self._couleur_du_signe(net))

        # Virgule décimale, comme partout ailleurs dans l'application : le
        # taux d'épargne était le seul chiffre à s'écrire « -10.6 % ».
        self.kpis["epargne"]._value.setText(
            f"{tx_epargne:.1f}".replace(".", ",") + " %")
        # Vert d'encre commun (#18733A) : le vert-bleu #16A085 d'avant ne
        # faisait que 3,09 pour 1 sur l'ivoire de la tuile.
        self._colorer_kpi("epargne", self._couleur_du_signe(tx_epargne))
        self.kpis["epargne"]._sub.setText(
            "part des revenus mis de côté" if tx_epargne >= 0
            else "dépenses supérieures aux revenus")

        self.kpis["pointe"]._value.setText(fmt_euro(solde_p_periode))
        # Couleur dynamique : vert si le solde pointé est positif, rouge s'il est négatif
        self._colorer_kpi("pointe", self._couleur_du_signe(solde_p_periode))
        # La période est rappelée ici : le titre ne la porte plus depuis qu'il
        # dit ce qu'on additionne (« Mouvement pointé »).
        self.kpis["pointe"]._sub.setText(
            f"{pluriel(n_pt, 'opération', 'opérations')} "
            f"{accorde(n_pt, 'pointée', 'pointées')} — {period_label(self.period)}")

        # ── Graphique en barres : douze mois ──────────────────────────
        # Il reçoit TOUTES les opérations, pas celles de la période : sur un
        # mois affiché, il ne dessinait qu'une seule barre.
        self._refresh_bar_chart([t for t in all_active
                                 if t.get("categorie") != "Épargne"])
        # La courbe du solde, elle, garde l'Épargne : un virement vers le
        # livret fait bien baisser le solde du compte.
        self._refresh_courbe_solde(txs_prevus, all_active, solde_compte)

        # ── Camembert dépenses ────────────────────────────────────────
        by_cat: dict[str, float] = {}
        for t in analyse:
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
        self._legende_sans_coupure()
        # Graphiques vides : une phrase plutôt que des axes « … ».
        # Le graphique vide est masqué : ses axes passaient sous la phrase.
        self.etat_camembert.montrer(not by_cat)
        self.etat_barres.montrer(not all_active)
        self.etat_courbe.montrer(not all_active)
        self.bar_chart.setVisible(bool(all_active))
        self.solde_chart.setVisible(bool(all_active))

        # ── Liste : dépenses par catégorie (top 8) ────────────────────
        total_dep = abs(dep_a) or 1
        dep_items = []
        for c, amt in sorted(by_cat.items(), key=lambda x: x[1], reverse=True)[:8]:
            pct = amt / total_dep * 100
            dep_items.append((c, -amt, cat_color(c), f"{pct:.0f}%"))
        self.list_dep.set_items(dep_items)

        # ── Liste : sources de revenus ────────────────────────────────
        by_rev: dict[str, float] = {}
        for t in analyse:
            if t["montant"] <= 0:
                continue
            c = t.get("categorie", "Non classé")
            by_rev[c] = by_rev.get(c, 0) + t["montant"]
        rev_items = [(c, amt, cat_color(c))
                     for c, amt in sorted(by_rev.items(), key=lambda x: x[1], reverse=True)[:8]]
        self.list_rev.set_items(rev_items)

        # ── Liste : plus grosses dépenses individuelles ───────────────
        top = sorted([t for t in analyse if t["montant"] < 0],
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

    def _points_de_la_courbe(self, txs: list[dict], actives: list[dict],
                            solde_compte: float) -> list[tuple]:
        """(mois, solde, prévu) pour chacun des douze mois du graphique.

        Le solde vient de `_solde_fin_de_mois` : constaté pour un mois fini,
        prévu pour le mois en cours et les suivants — le même chiffre que le
        bandeau « Ce mois-ci ». Avant la date de départ, aucun solde n'est
        connu : le point est laissé vide (None) plutôt que de tracer un
        faux plat au niveau du solde de départ."""
        initial_date = self.db.get_setting("initial_date", "2025-01-01")
        today = date.today()
        points = []
        for mois in self._mois_du_graphique(actives):
            an, m = int(mois[:4]), int(mois[5:7])
            fin = date(an, m, monthrange(an, m)[1])
            if fin.isoformat() < initial_date:
                points.append((mois, None, False))
                continue
            solde = round(self._solde_fin_de_mois(txs, mois, solde_compte), 2)
            points.append((mois, solde, fin >= today))
        return points

    def _refresh_courbe_solde(self, txs: list[dict], actives: list[dict],
                              solde_compte: float):
        """Dessine la courbe du solde en fin de mois."""
        points = self._points_de_la_courbe(txs, actives, solde_compte)
        self.soldes_de_la_courbe = points
        self.solde_chart.removeAllSeries()
        for ax in self.solde_chart.axes():
            self.solde_chart.removeAxis(ax)
        valeurs = [s for _m, s, _p in points if s is not None]
        if not points or not valeurs:
            return

        bleu = QColor("#1F3A6B")
        constate = QLineSeries()
        constate.setName("Constaté")
        constate.setPen(QPen(bleu, 2))
        prevu = QLineSeries()
        prevu.setName("Prévu")
        prevu.setPen(QPen(bleu, 2, Qt.DashLine))
        for serie in (constate, prevu):
            serie.setPointsVisible(True)
            serie.setColor(bleu)
        dernier_constate = None
        for i, (_m, s, est_prevu) in enumerate(points):
            if s is None:
                continue
            if est_prevu:
                # La ligne pointillée part du dernier point constaté, pour
                # que la courbe ne soit pas coupée en deux.
                if dernier_constate is not None and prevu.count() == 0:
                    prevu.append(*dernier_constate)
                prevu.append(i, s)
            else:
                constate.append(i, s)
                dernier_constate = (i, s)

        ax_x = QBarCategoryAxis()
        ax_x.append([_mois_court(m) for m, _s, _p in points])
        self.solde_chart.addAxis(ax_x, Qt.AlignBottom)
        bas, haut = min(valeurs), max(valeurs)
        marge = max((haut - bas) * 0.1, 50)
        # Un solde toujours positif garde un axe qui commence à 0 au plus bas :
        # pas de faux « découvert » dessiné par la marge. Graduations rondes,
        # en euros (axe_euros).
        ax_y = axe_euros(max(bas - marge, 0) if bas >= 0 else bas - marge,
                         haut + marge)
        self.solde_chart.addAxis(ax_y, Qt.AlignLeft)

        series = [constate, prevu]
        if bas < 0:
            # Découvert au moins un mois : la ligne du zéro, en rouge, montre
            # quand la courbe passe dessous.
            zero = QLineSeries()
            zero.setPen(QPen(QColor("#C0392B"), 1))
            zero.append(0, 0)
            zero.append(len(points) - 1, 0)
            series.append(zero)
        for serie in series:
            if serie.count() == 0:
                continue
            self.solde_chart.addSeries(serie)
            serie.attachAxis(ax_x)
            serie.attachAxis(ax_y)
            serie.hovered.connect(self._infobulle_solde)
        for marqueur in self.solde_chart.legend().markers():
            # Seules « Constaté » et « Prévu » ont leur place dans la légende.
            if not marqueur.series().name():
                marqueur.setVisible(False)

        premier, dernier = points[0][0], points[-1][0]
        self.solde_panel._header.setText(
            f"SOLDE EN FIN DE MOIS — {de_mois_a_mois(premier, dernier).upper()}")

    def _infobulle_solde(self, point, survole: bool):
        """Au survol d'un point : le mois et le solde exact, en euros."""
        if not survole:
            QToolTip.hideText()
            return
        i = round(point.x())
        if 0 <= i < len(self.soldes_de_la_courbe):
            mois, solde, est_prevu = self.soldes_de_la_courbe[i]
            if solde is not None:
                QToolTip.showText(
                    QCursor.pos(),
                    f"Fin {_mois_court(mois).lower()} {mois[:4]} : "
                    f"{fmt_euro(solde)}{' (prévu)' if est_prevu else ''}")

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
        bar_dep.setColor(QColor("#B9551A"))
        bar_rev.setBorderColor(QColor("#229954"))
        bar_dep.setBorderColor(QColor("#B9551A"))
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
        _court = _mois_court
        labels = [_court(m) for m in months]
        self.bar_panel._header.setText(
            f"ÉVOLUTION SUR 12 MOIS — {de_mois_a_mois(months[0], months[-1]).upper()}")
        ax_x = QBarCategoryAxis(); ax_x.append(labels)
        # 8 pt, le minimum de la charte : à 9, « Nov », « Mar » et « Aoû »
        # se coupaient en « N… » à 1280 px de large.
        police = ax_x.labelsFont()
        police.setPointSize(8)
        ax_x.setLabelsFont(police)
        self.bar_chart.addAxis(ax_x, Qt.AlignBottom)
        series.attachAxis(ax_x)

        max_val = max(max(rev_by_month.values(), default=0),
                      max(dep_by_month.values(), default=0))
        # Au moins 100 : un axe de 0 à 1 — base vide — se lisait « 0, 0, 0,
        # 0, 1 » (audit du 23/09/2026). Graduations rondes, en euros.
        ax_y = axe_euros(0, max(max_val, 100))
        self.bar_chart.addAxis(ax_y, Qt.AlignLeft)
        series.attachAxis(ax_y)
