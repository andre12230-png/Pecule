"""Rapport mensuel (aperçu, PDF, impression)."""

from calendar import monthrange
from datetime import date
from html import escape as _esc   # « B&C » → « B&amp;C » : sinon le & casse le HTML

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout,
    QPushButton, QDialog, QMessageBox, QFileDialog, QTextBrowser,
)

from ..accords import pluriel
from ..utils import (
    cat_color, depense_nette_par_categorie, fmt_euro, fmt_date_fr,
)
from ..database import Database
from .widgets import PeriodBar

MOIS_FR = ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet",
           "Août", "Septembre", "Octobre", "Novembre", "Décembre"]


def build_monthly_report_html(db: "Database", month: str) -> str:
    """Construit le rapport du mois `month` (AAAA-MM) en HTML compatible
    QTextDocument (sous-ensemble limité : tableaux simples, couleurs)."""
    txs = [dict(r) for r in db.list_tx()]
    eff = lambda t: t.get("date_valeur") or t.get("date") or ""
    act = [t for t in txs if t.get("categorie") != "Transaction exclue"
           and (t.get("date") or "").startswith(month)]

    # « Épargne » (virement vers le livret…) n'est ni un revenu ni une
    # dépense : c'est de l'argent mis de côté, montré à part. Il faisait
    # BAISSER le taux d'épargne (choix d'André après l'audit du 23/09/2026).
    analyse = [t for t in act if t.get("categorie") != "Épargne"]
    mis_de_cote = sum(t["montant"] for t in act
                      if t.get("categorie") == "Épargne")
    revenus = sum(t["montant"] for t in analyse if t["montant"] > 0)
    depenses = sum(t["montant"] for t in analyse if t["montant"] < 0)
    net = revenus + depenses + mis_de_cote     # tout ce qui a bougé
    taux = ((revenus + depenses) / revenus * 100) if revenus > 0 else 0.0

    # Solde bancaire réel (pointé) à la fin du mois
    initial_date = db.get_setting("initial_date", "2025-01-01")
    try:
        initial_balance = float(db.get_setting("initial_balance", "0"))
    except ValueError:
        initial_balance = 0.0
    y, m = int(month[:4]), int(month[5:7])
    month_end = f"{month}-{monthrange(y, m)[1]:02d}"
    # Pour le mois EN COURS, on s'arrête à aujourd'hui : compter jusqu'au 31
    # ferait entrer des opérations à venir (un achat carte débité le 4 du mois
    # prochain, par exemple) et le rapport annoncerait un solde différent de
    # celui du Bilan, sans que rien ne l'explique.
    arret = min(month_end, date.today().isoformat())
    solde_fin = initial_balance + sum(
        t["montant"] for t in txs
        if t.get("categorie") != "Transaction exclue" and t.get("pointee")
        and initial_date <= eff(t) <= arret)

    # Dépenses par catégorie + comparaison budget
    budgets = db.list_budgets()
    # Budgets : achats moins remboursements, comme l'onglet Budget.
    spent_budget = depense_nette_par_categorie(act)
    # Dépenses par catégorie : les achats du mois, hors épargne.
    spent: dict[str, float] = {}
    for t in analyse:
        if t["montant"] < 0:
            c = t.get("categorie", "Non classé")
            spent[c] = spent.get(c, 0) + abs(t["montant"])
    total_dep = sum(spent.values()) or 1.0

    def euro(v):  # € insécable pour QTextDocument
        return fmt_euro(v).replace(" ", "&nbsp;")

    H = []
    # Le nom du compte n'apparait que s'il y en a plusieurs : sur un rapport
    # imprime, savoir de quel compte il s'agit evite toute confusion.
    suffixe = ""
    if len(db.list_comptes()) > 1:
        suffixe = f" — {db.nom_compte()}"
    H.append(f"<h1>📒 Pécule — Rapport {MOIS_FR[m]} {y}{suffixe}</h1>")
    # La date utilisée est dite : le Bilan compte par défaut à la date de
    # valeur, et ses chiffres du même mois diffèrent (relecture du 30/09/2026).
    H.append(f"<p><i>Généré le {fmt_date_fr(date.today().isoformat())} — "
             f"{pluriel(len(act), 'opération', 'opérations')} sur le mois, "
             "comptées à la date d'achat, comme l'onglet Budget : un achat par "
             "carte compte dans le mois où il a été fait.</i></p><hr>")

    # — KPI —
    H.append("<h2>Synthèse</h2>")
    H.append('<table cellpadding="6" cellspacing="0" width="100%">')
    kpis = [
        ("Revenus", euro(revenus), "#18733A"),
        ("Dépenses", euro(depenses), "#C0392B"),
    ]
    if mis_de_cote:
        kpis.append(("Mis de côté (Épargne)", euro(mis_de_cote), "#18733A"))
    kpis += [
        ("Mouvement du mois", euro(net), "#18733A" if net >= 0 else "#C0392B"),
        # Virgule décimale, comme le Bilan (« 53,9 % », pas « 53.9 % »).
        ("Taux d'épargne", f"{taux:.1f}".replace(".", ",") + "&nbsp;%",
         "#18733A" if taux >= 0 else "#C0392B"),
        (f"Solde bancaire réel au {fmt_date_fr(arret)}", euro(solde_fin),
         "#1F3A6B" if solde_fin >= 0 else "#C0392B"),
    ]
    for lbl, val, col in kpis:
        H.append(f'<tr><td width="55%">{lbl}</td>'
                 f'<td align="right"><b><font color="{col}">{val}</font></b></td></tr>')
    H.append("</table>")

    # — Budgets du mois —
    if budgets:
        H.append("<h2>Budgets du mois</h2>")
        H.append('<table cellpadding="5" cellspacing="0" width="100%">'
                 '<tr bgcolor="#E8EEF7"><td><b>Catégorie</b></td>'
                 '<td align="right"><b>Budget</b></td>'
                 '<td align="right"><b>Dépensé</b></td>'
                 '<td align="right"><b>%</b></td>'
                 '<td align="right"><b>Reste</b></td></tr>')
        rows = sorted(((spent_budget.get(c, 0) / b * 100 if b > 0 else 0), c, b)
                      for c, b in budgets.items() if b > 0)
        for ratio, cat, b in reversed(rows):
            dep = spent_budget.get(cat, 0)
            reste = b - dep
            col = "#C0392B" if ratio >= 100 else ("#7E5109" if ratio >= 85 else "#18733A")
            bg = ' bgcolor="#FDEDEB"' if ratio >= 100 else ""
            H.append(f'<tr{bg}><td>{_esc(cat)}</td>'
                     f'<td align="right">{euro(b)}</td>'
                     f'<td align="right">{euro(dep)}</td>'
                     f'<td align="right"><font color="{col}"><b>{ratio:.0f}&nbsp;%</b></font></td>'
                     f'<td align="right"><font color="{"#C0392B" if reste < 0 else "#18733A"}">'
                     f'{euro(reste)}</font></td></tr>')
        H.append("</table>")

    # — Dépenses par catégorie —
    H.append("<h2>Dépenses par catégorie</h2>")
    H.append('<table cellpadding="5" cellspacing="0" width="100%">'
             '<tr bgcolor="#E8EEF7"><td><b>Catégorie</b></td>'
             '<td align="right"><b>Montant</b></td>'
             '<td align="right"><b>Part</b></td></tr>')
    for cat, dep in sorted(spent.items(), key=lambda x: -x[1]):
        H.append(f'<tr><td><font color="{cat_color(cat)}">⬤</font> {_esc(cat)}</td>'
                 f'<td align="right">{euro(-dep)}</td>'
                 f'<td align="right">{dep / total_dep * 100:.0f}&nbsp;%</td></tr>')
    H.append("</table>")

    # — Plus grosses dépenses —
    top = sorted((t for t in analyse if t["montant"] < 0), key=lambda t: t["montant"])[:10]
    if top:
        H.append("<h2>Plus grosses dépenses</h2>")
        H.append('<table cellpadding="5" cellspacing="0" width="100%">'
                 '<tr bgcolor="#E8EEF7"><td><b>Date</b></td><td><b>Libellé</b></td>'
                 '<td><b>Catégorie</b></td><td align="right"><b>Montant</b></td></tr>')
        for t in top:
            H.append(f'<tr><td>{fmt_date_fr(t["date"])}</td>'
                     f'<td>{_esc(t.get("libelle", ""))}</td>'
                     f'<td>{_esc(t.get("categorie", ""))}</td>'
                     f'<td align="right"><font color="#C0392B">{euro(t["montant"])}</font></td></tr>')
        H.append("</table>")

    return "\n".join(H)


def _mois_de_depart(periode: str, mois_dispo: set, aujourdhui: date) -> str:
    """Mois sur lequel s'ouvre le rapport, d'après la période de la barre du
    haut. Retourne « » quand rien n'est imposé (le mois en cours est pris).

      • un mois (« 2026-01 ») : ce mois-là ;
      • une année (« 2025 ») : son dernier mois qui a des opérations, sans
        dépasser le mois en cours — décembre pour une année finie ;
      • « Toutes périodes » ou rien : le mois en cours, comme avant."""
    periode = periode or ""
    if len(periode) == 7:
        return periode
    if len(periode) == 4 and periode.isdigit():
        limite = aujourdhui.strftime("%Y-%m")
        dans_l_annee = [m for m in mois_dispo
                        if m.startswith(periode + "-") and m <= limite]
        return max(dans_l_annee, default="")
    return ""


class MonthlyReportDialog(QDialog):
    """Aperçu du rapport mensuel, avec export PDF et impression."""

    def __init__(self, parent, db: Database, periode: str = None):
        """`periode` : la période choisie dans la barre du haut — « AAAA-MM »,
        « AAAA » ou « all ». Le rapport s'ouvre sur ce mois-là (cf.
        _mois_de_depart) ; sans elle, sur le mois en cours."""
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Rapport mensuel")
        self.resize(760, 640)

        v = QVBoxLayout(self)
        # Le même sélecteur que la barre du haut (‹ année mois › Ce mois-ci,
        # Ctrl+← / Ctrl+→ / Ctrl+Origine), réduit aux mois : un rapport porte
        # toujours sur un mois. Il filtre, comme le rapport, sur la date
        # d'opération.
        txs = [dict(r) for r in db.list_tx()]
        months = {(t.get("date") or "")[:7] for t in txs if t.get("date")}
        cur = _mois_de_depart(periode, months, date.today())
        # Le mois demandé figure dans les menus même sans opération : sinon le
        # rapport s'ouvrirait, sans qu'on le voie, sur un autre mois. Le
        # sélecteur ne lit que les dates : une date suffit à l'y faire entrer.
        if cur and cur not in months:
            txs.append({"date": f"{cur}-01"})
        self.periode = PeriodBar(self, mois_seulement=True)
        self.periode.layout().setContentsMargins(0, 0, 0, 0)
        self.periode.update_periods(txs)
        if cur:
            self.periode.choisir_periode(cur)
        self.periode.period_changed.connect(lambda _p: self._rebuild())
        v.addWidget(self.periode)

        self.browser = QTextBrowser()
        self.browser.setStyleSheet("QTextBrowser { background:#FAF8F1; padding:10px }")
        v.addWidget(self.browser, 1)

        btns = QHBoxLayout()
        btns.addStretch()
        b_pdf = QPushButton("💾 Enregistrer en PDF…")
        b_pdf.clicked.connect(self._save_pdf)
        btns.addWidget(b_pdf)
        b_print = QPushButton("🖨 Imprimer…")
        b_print.clicked.connect(self._print)
        btns.addWidget(b_print)
        b_close = QPushButton("Fermer")
        b_close.clicked.connect(self.reject)
        btns.addWidget(b_close)
        # Entrée ne doit déclencher aucun bouton par accident
        for b in (b_pdf, b_print, b_close):
            b.setAutoDefault(False); b.setDefault(False)
        v.addLayout(btns)

        self._rebuild()

    def current_month(self) -> str:
        p = self.periode.current_period()
        return p if len(p) == 7 else date.today().strftime("%Y-%m")

    def _rebuild(self):
        self.browser.setHtml(build_monthly_report_html(self.db, self.current_month()))

    def _save_pdf(self):
        from PySide6.QtPrintSupport import QPrinter
        mo = self.current_month()
        path, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer le rapport", f"rapport-{mo}.pdf", "PDF (*.pdf)")
        if not path:
            return
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(path)
        self.browser.document().print_(printer)
        QMessageBox.information(self, "Rapport", f"PDF enregistré :\n{path}")

    def _print(self):
        from PySide6.QtPrintSupport import QPrinter, QPrintDialog
        printer = QPrinter(QPrinter.HighResolution)
        dlg = QPrintDialog(printer, self)
        if dlg.exec() == QDialog.Accepted:
            self.browser.document().print_(printer)
