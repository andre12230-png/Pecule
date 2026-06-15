"""Rapport mensuel (aperçu, PDF, impression)."""

from calendar import monthrange
from datetime import date

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QDialog, QMessageBox, QFileDialog, QTextBrowser,
)

from ..utils import (
    cat_color, fmt_euro, fmt_date_fr,
)
from ..database import Database

MOIS_FR = ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet",
           "Août", "Septembre", "Octobre", "Novembre", "Décembre"]


def build_monthly_report_html(db: "Database", month: str) -> str:
    """Construit le rapport du mois `month` (AAAA-MM) en HTML compatible
    QTextDocument (sous-ensemble limité : tableaux simples, couleurs)."""
    txs = [dict(r) for r in db.list_tx()]
    eff = lambda t: t.get("date_valeur") or t.get("date") or ""
    act = [t for t in txs if t.get("categorie") != "Transaction exclue"
           and (t.get("date") or "").startswith(month)]

    revenus = sum(t["montant"] for t in act if t["montant"] > 0)
    depenses = sum(t["montant"] for t in act if t["montant"] < 0)
    net = revenus + depenses
    taux = (net / revenus * 100) if revenus > 0 else 0.0

    # Solde bancaire réel (pointé) à la fin du mois
    initial_date = db.get_setting("initial_date", "2025-01-01")
    try:
        initial_balance = float(db.get_setting("initial_balance", "0"))
    except ValueError:
        initial_balance = 0.0
    y, m = int(month[:4]), int(month[5:7])
    month_end = f"{month}-{monthrange(y, m)[1]:02d}"
    solde_fin = initial_balance + sum(
        t["montant"] for t in txs
        if t.get("categorie") != "Transaction exclue" and t.get("pointee")
        and initial_date <= eff(t) <= month_end)

    # Dépenses par catégorie + comparaison budget
    budgets = db.list_budgets()
    spent: dict[str, float] = {}
    for t in act:
        if t["montant"] < 0:
            c = t.get("categorie", "Non classé")
            spent[c] = spent.get(c, 0) + abs(t["montant"])
    total_dep = sum(spent.values()) or 1.0

    def euro(v):  # € insécable pour QTextDocument
        return fmt_euro(v).replace(" ", "&nbsp;")

    H = []
    H.append(f"<h1>📒 Comptes &amp; Budget — Rapport {MOIS_FR[m]} {y}</h1>")
    H.append(f"<p><i>Généré le {fmt_date_fr(date.today().isoformat())} — "
             f"{len(act)} opération(s) sur le mois.</i></p><hr>")

    # — KPI —
    H.append("<h2>Synthèse</h2>")
    H.append('<table cellpadding="6" cellspacing="0" width="100%">')
    kpis = [
        ("Revenus", euro(revenus), "#229954"),
        ("Dépenses", euro(depenses), "#C0392B"),
        ("Mouvement net", euro(net), "#229954" if net >= 0 else "#C0392B"),
        ("Taux d'épargne", f"{taux:.1f}&nbsp;%", "#16A085" if taux >= 0 else "#C0392B"),
        (f"Solde bancaire réel au {fmt_date_fr(month_end)}", euro(solde_fin),
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
                 '<tr bgcolor="#DCE6F1"><td><b>Catégorie</b></td>'
                 '<td align="right"><b>Budget</b></td>'
                 '<td align="right"><b>Dépensé</b></td>'
                 '<td align="right"><b>%</b></td>'
                 '<td align="right"><b>Reste</b></td></tr>')
        rows = sorted(((spent.get(c, 0) / b * 100 if b > 0 else 0), c, b)
                      for c, b in budgets.items() if b > 0)
        for ratio, cat, b in reversed(rows):
            dep = spent.get(cat, 0)
            reste = b - dep
            col = "#C0392B" if ratio >= 100 else ("#E67E22" if ratio >= 85 else "#229954")
            bg = ' bgcolor="#FDEDEB"' if ratio >= 100 else ""
            H.append(f'<tr{bg}><td>{cat}</td>'
                     f'<td align="right">{euro(b)}</td>'
                     f'<td align="right">{euro(dep)}</td>'
                     f'<td align="right"><font color="{col}"><b>{ratio:.0f}&nbsp;%</b></font></td>'
                     f'<td align="right"><font color="{"#C0392B" if reste < 0 else "#229954"}">'
                     f'{euro(reste)}</font></td></tr>')
        H.append("</table>")

    # — Dépenses par catégorie —
    H.append("<h2>Dépenses par catégorie</h2>")
    H.append('<table cellpadding="5" cellspacing="0" width="100%">'
             '<tr bgcolor="#DCE6F1"><td><b>Catégorie</b></td>'
             '<td align="right"><b>Montant</b></td>'
             '<td align="right"><b>Part</b></td></tr>')
    for cat, dep in sorted(spent.items(), key=lambda x: -x[1]):
        H.append(f'<tr><td><font color="{cat_color(cat)}">⬤</font> {cat}</td>'
                 f'<td align="right">{euro(-dep)}</td>'
                 f'<td align="right">{dep / total_dep * 100:.0f}&nbsp;%</td></tr>')
    H.append("</table>")

    # — Plus grosses dépenses —
    top = sorted((t for t in act if t["montant"] < 0), key=lambda t: t["montant"])[:10]
    if top:
        H.append("<h2>Plus grosses dépenses</h2>")
        H.append('<table cellpadding="5" cellspacing="0" width="100%">'
                 '<tr bgcolor="#DCE6F1"><td><b>Date</b></td><td><b>Libellé</b></td>'
                 '<td><b>Catégorie</b></td><td align="right"><b>Montant</b></td></tr>')
        for t in top:
            H.append(f'<tr><td>{fmt_date_fr(t["date"])}</td>'
                     f'<td>{t.get("libelle", "")}</td>'
                     f'<td>{t.get("categorie", "")}</td>'
                     f'<td align="right"><font color="#C0392B">{euro(t["montant"])}</font></td></tr>')
        H.append("</table>")

    return "\n".join(H)


class MonthlyReportDialog(QDialog):
    """Aperçu du rapport mensuel, avec export PDF et impression."""

    def __init__(self, parent, db: Database):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Rapport mensuel")
        self.resize(760, 640)

        v = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Mois :"))
        self.month_combo = QComboBox()
        months = sorted({(r["date"] or "")[:7] for r in db.list_tx()
                         if r["date"]}, reverse=True)
        cur = date.today().strftime("%Y-%m")
        for mo in months:
            y, m = int(mo[:4]), int(mo[5:7])
            self.month_combo.addItem(f"{MOIS_FR[m]} {y}", mo)
        idx = self.month_combo.findData(cur)
        if idx >= 0:
            self.month_combo.setCurrentIndex(idx)
        self.month_combo.currentIndexChanged.connect(self._rebuild)
        top.addWidget(self.month_combo)
        top.addStretch()
        v.addLayout(top)

        self.browser = QTextBrowser()
        self.browser.setStyleSheet("QTextBrowser { background:#FFF; padding:10px }")
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
        return self.month_combo.currentData() or date.today().strftime("%Y-%m")

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
