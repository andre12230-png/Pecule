"""Vue Bilan (tableau de bord)."""

from calendar import monthrange
from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QColor, QPainter,
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame,
)
from PySide6.QtCharts import (
    QChart, QChartView, QPieSeries, QBarSeries, QBarSet,
    QBarCategoryAxis, QValueAxis,
)

from ...utils import (
    cat_color, fmt_euro, fmt_date_fr,
    in_period, period_label,
)
from ...database import Database

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
            lbl.setStyleSheet("color:#222")
            row.addWidget(lbl, 1)
            if sub:
                s = QLabel(sub); s.setStyleSheet("color:#888; font-size:9pt")
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
    return f


class BilanView(QWidget):
    goto_budget = Signal()   # clic sur l'alerte budget → ouvrir l'onglet Budget

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.period = "all"
        self.date_mode = "valeur"
        self.setStyleSheet("BilanView { background: #ECEEF2; }")

        main = QVBoxLayout(self)
        main.setContentsMargins(10, 10, 10, 10)
        main.setSpacing(10)

        # ── Ligne 1 : 6 cartes KPI ────────────────────────────────────
        kpi_row = QHBoxLayout(); kpi_row.setSpacing(8)
        self.kpis = {}
        defs = [
            ("solde",    "💼 Solde bancaire réel (pointé)", "#1F3A6B"),
            ("net",      "Mouvement net",                  "#34495E"),
            ("revenus",  "Revenus",                        "#229954"),
            ("depenses", "Dépenses",                       "#C0392B"),
            ("epargne",  "Taux d'épargne",                 "#16A085"),
            ("pointe",   "✔ Solde pointé",                 "#1A7A3A"),
        ]
        for key, label, color in defs:
            card = self._make_kpi(label, "—", color)
            self.kpis[key] = card
            kpi_row.addWidget(card, 1)
        main.addLayout(kpi_row)

        # ── Bandeau Encours Carte Bancaire ────────────────────────────
        self.cb_banner = QFrame()
        self.cb_banner.setStyleSheet("""
            QFrame { background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #FFF8E1, stop:1 #FFECB3);
                     border: 1px solid #E8C77B; border-radius: 4px; }
        """)
        cb_lay = QHBoxLayout(self.cb_banner)
        cb_lay.setContentsMargins(14, 8, 14, 8); cb_lay.setSpacing(20)

        self.cb_title = QLabel("💳 ENCOURS CARTE BANCAIRE")
        self.cb_title.setStyleSheet("font-weight:bold; color:#7E5A18; font-size:9pt")
        cb_lay.addWidget(self.cb_title)
        cb_lay.addSpacing(10)

        # 3 mini-blocs : mois en cours / mois précédent en attente / total
        def _mini(label_txt):
            w = QWidget(); l = QVBoxLayout(w); l.setContentsMargins(0,0,0,0); l.setSpacing(0)
            lbl = QLabel(label_txt); lbl.setStyleSheet("color:#7E5A18; font-size:8pt")
            val = QLabel("—"); val.setStyleSheet("color:#5A2D00; font-size:13pt; font-weight:bold")
            l.addWidget(lbl); l.addWidget(val)
            return w, val

        w1, self.cb_courant = _mini("Mois en cours (à débiter)")
        w2, self.cb_precedent = _mini("Mois précédent (non débité)")
        w3, self.cb_total = _mini("Total à débiter prochainement")
        cb_lay.addWidget(w1); cb_lay.addWidget(w2); cb_lay.addWidget(w3)
        cb_lay.addStretch()
        self.cb_detail = QLabel("")
        self.cb_detail.setStyleSheet("color:#7E5A18; font-size:9pt")
        cb_lay.addWidget(self.cb_detail)
        main.addWidget(self.cb_banner)

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
        bar_view.setMinimumHeight(280)
        mid_row.addWidget(_make_panel("Évolution mensuelle", bar_view), 2)

        # Camembert
        self.pie_chart = QChart()
        self.pie_chart.setBackgroundVisible(False)
        self.pie_chart.legend().setAlignment(Qt.AlignRight)
        self.pie_chart.setAnimationOptions(QChart.SeriesAnimations)
        pie_view = QChartView(self.pie_chart)
        pie_view.setRenderHint(QPainter.Antialiasing)
        pie_view.setMinimumHeight(280)
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
        l_value = QLabel(value)
        l_value.setStyleSheet(f"color:{color}; font-size:16pt; font-weight:bold")
        l_sub = QLabel("")
        l_sub.setStyleSheet("color:#999; font-size:8pt")
        l_sub.setWordWrap(True)
        lay.addWidget(l_label); lay.addWidget(l_value); lay.addWidget(l_sub)
        f._value = l_value
        f._sub = l_sub
        return f

    def _eff_date(self, t: dict) -> str:
        if self.date_mode == "valeur":
            return t.get("date_valeur") or t.get("date", "")
        return t.get("date", "")

    def _refresh_cb_banner(self, txs: list[dict]):
        """Calcule les encours CB par mois (achats CB pas encore débités).
        Une opération CB est 'pas encore débitée' quand sa date_valeur > aujourd'hui."""
        today = date.today()
        today_iso = today.isoformat()
        cur_month = today.strftime("%Y-%m")
        # Mois précédent
        if today.month == 1:
            prev_month = f"{today.year - 1}-12"
        else:
            prev_month = f"{today.year}-{today.month - 1:02d}"

        # CB = opérations dont type contient "carte" (insensible à la casse)
        def is_cb(t: dict) -> bool:
            return "carte" in (t.get("type") or "").lower()

        # CB du mois en cours (par date d'opération), montant total
        cb_courant = [t for t in txs
                      if is_cb(t)
                      and t.get("date", "").startswith(cur_month)
                      and t.get("categorie") != "Transaction exclue"]
        # Mois en cours « à débiter » = total des opérations CB du mois en cours
        # qui ont été POINTÉES (vérifiées sur le relevé).
        en_attente_courant = sum(t["montant"] for t in cb_courant if t.get("pointee"))

        # CB du mois précédent NON encore débitées (date_valeur > today)
        cb_prec_pending = [t for t in txs
                           if is_cb(t)
                           and t.get("date", "").startswith(prev_month)
                           and t.get("categorie") != "Transaction exclue"
                           and (t.get("date_valeur") or t["date"]) > today_iso]
        somme_prec = sum(t["montant"] for t in cb_prec_pending)

        # Total à débiter prochainement = le PROCHAIN prélèvement uniquement.
        # En débit différé, les achats sont prélevés par lot une fois par mois.
        # On prend donc les opérations CB non encore débitées dont la date de
        # valeur tombe dans le mois de la plus proche échéance à venir (les
        # échéances plus lointaines, ex. mois suivant, ne sont pas comptées ici).
        cb_pending = [t for t in txs
                      if is_cb(t)
                      and t.get("categorie") != "Transaction exclue"
                      and (t.get("date_valeur") or t["date"]) > today_iso]
        if cb_pending:
            next_vd_month = min((t.get("date_valeur") or t["date"]) for t in cb_pending)[:7]
            cb_pending_total = [t for t in cb_pending
                                if (t.get("date_valeur") or t["date"]).startswith(next_vd_month)]
        else:
            cb_pending_total = []
        total_pending = sum(t["montant"] for t in cb_pending_total)

        # Affichage
        mois_court = ["", "janvier", "février", "mars", "avril", "mai", "juin",
                      "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
        nom_cur = mois_court[today.month]
        nom_prev = mois_court[12 if today.month == 1 else today.month - 1]

        self.cb_courant.setText(fmt_euro(en_attente_courant))
        self.cb_precedent.setText(fmt_euro(somme_prec))
        self.cb_total.setText(fmt_euro(total_pending))

        self.cb_title.setText(f"💳 ENCOURS CARTE BANCAIRE — au {fmt_date_fr(today_iso)}")

        n_cur = sum(1 for t in cb_courant if t.get("pointee"))
        n_prev = len(cb_prec_pending)
        n_tot = len(cb_pending_total)
        self.cb_detail.setText(
            f"{n_cur} op. {nom_cur}  •  {n_prev} op. {nom_prev}  •  {n_tot} au prochain prélèvement"
        )

        # Masquer le bandeau s'il n'y a rien à montrer
        self.cb_banner.setVisible(n_tot > 0 or en_attente_courant != 0 or somme_prec != 0)

    def _period_end(self) -> str:
        """Dernier jour (YYYY-MM-DD inclus) de la période en cours."""
        if self.period == "all":
            return "9999-12-31"
        if len(self.period) == 4:           # YYYY
            return f"{self.period}-12-31"
        if len(self.period) == 7:           # YYYY-MM
            y, m = int(self.period[:4]), int(self.period[5:7])
            return f"{self.period}-{monthrange(y, m)[1]:02d}"
        return "9999-12-31"

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
            if (t.get("categorie") == "Transaction exclue"
                    or t.get("montant", 0) >= 0
                    or not (t.get("date") or "").startswith(month)):
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
                f"<b>{cat}</b> {ratio:.0f} % ({fmt_euro(dep)} / {fmt_euro(budget)})"
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

        # ── Encours Carte Bancaire (indépendant de la période) ──────
        self._refresh_cb_banner(txs)

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
        # affichée) : initial + opérations pointées dont la date effective est
        # déjà passée (≤ aujourd'hui). Les non pointées sont ignorées : elles
        # ne sont pas encore débitées et leur date peut changer.
        today_iso = date.today().isoformat()
        up_to_end = [t for t in all_active
                     if initial_date <= self._eff_date(t) <= today_iso]
        pointees_up = [t for t in up_to_end if t.get("pointee")]
        non_pointees_up = [t for t in up_to_end if not t.get("pointee")]
        solde_compte = initial_balance + sum(t["montant"] for t in pointees_up)
        # Solde engagé (informatif) = réel + opérations non pointées
        montant_en_attente = sum(t["montant"] for t in non_pointees_up)
        solde_engage = solde_compte + montant_en_attente

        n_rev = sum(1 for t in active if t["montant"] > 0)
        n_dep = sum(1 for t in active if t["montant"] < 0)
        n_pt  = sum(1 for t in active if t.get("pointee"))

        mode_lbl = "valeur (banque)" if self.date_mode == "valeur" else "opération"
        self.kpis["solde"]._value.setText(fmt_euro(solde_compte))
        col_solde = "#229954" if solde_compte >= 0 else "#C0392B"
        self.kpis["solde"]._value.setStyleSheet(
            f"color:{col_solde}; font-size:16pt; font-weight:bold")
        sub = (f"Au {fmt_date_fr(today_iso)} — initial {fmt_euro(initial_balance)} + "
               f"{len(pointees_up)} opér. pointée(s) — date {mode_lbl}")
        if non_pointees_up:
            sub += (f"  •  {len(non_pointees_up)} non pointée(s) ignorée(s) "
                    f"({fmt_euro(montant_en_attente)}) — engagé : {fmt_euro(solde_engage)}")
        self.kpis["solde"]._sub.setText(sub)

        net = net_periode
        self.kpis["net"]._value.setText(fmt_euro(net))
        self.kpis["net"]._sub.setText(f"{period_label(self.period)} — date {mode_lbl}")
        # Couleur dynamique pour mouvement net
        col_net = "#229954" if net >= 0 else "#C0392B"
        self.kpis["net"]._value.setStyleSheet(f"color:{col_net}; font-size:16pt; font-weight:bold")

        self.kpis["revenus"]._value.setText(fmt_euro(revenus))
        self.kpis["revenus"]._sub.setText(f"{n_rev} entrée(s)")

        self.kpis["depenses"]._value.setText(fmt_euro(depenses))
        self.kpis["depenses"]._sub.setText(f"{n_dep} sortie(s)")

        self.kpis["epargne"]._value.setText(f"{tx_epargne:.1f} %")
        col_ep = "#16A085" if tx_epargne >= 0 else "#C0392B"
        self.kpis["epargne"]._value.setStyleSheet(
            f"color:{col_ep}; font-size:16pt; font-weight:bold")
        self.kpis["epargne"]._sub.setText(
            "part des revenus mis de côté" if tx_epargne >= 0
            else "dépenses supérieures aux revenus")

        self.kpis["pointe"]._value.setText(fmt_euro(solde_p_periode))
        self.kpis["pointe"]._sub.setText(f"{n_pt} opération(s) pointée(s)")

        # ── Graphique en barres : 12 derniers mois ────────────────────
        self._refresh_bar_chart(active)

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

    def _refresh_bar_chart(self, active: list[dict]):
        """Barres mensuelles revenus / dépenses sur les 12 derniers mois présents,
        en utilisant la date effective (opération ou valeur)."""
        months = sorted({self._eff_date(t)[:7] for t in active if self._eff_date(t)})
        months = months[-12:]
        if not months:
            self.bar_chart.removeAllSeries()
            return

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
            bar_rev.append(rev_by_month[m])
            bar_dep.append(dep_by_month[m])

        series = QBarSeries()
        series.append(bar_rev); series.append(bar_dep)
        self.bar_chart.addSeries(series)

        # Axe X : libellés courts "Jan 26"
        mois_court = ["", "Jan", "Fév", "Mar", "Avr", "Mai", "Jun",
                      "Jul", "Aoû", "Sep", "Oct", "Nov", "Déc"]
        labels = []
        for m in months:
            try:
                yy = m[2:4]; mm = int(m[5:7])
                labels.append(f"{mois_court[mm]} {yy}")
            except (ValueError, IndexError):
                labels.append(m)
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
