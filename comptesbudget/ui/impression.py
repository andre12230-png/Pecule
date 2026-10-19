"""Impression : la fenêtre d'aperçu commune (PDF, imprimante) et la liste
des opérations.

Plan retenu le 15/10/2026 et avancé à la sortie du 01/11/2026 : une entrée
« 🖨 Imprimer… » au menu de gauche, qui demande quoi imprimer puis montre un
aperçu. Toujours sur fond clair, comme le papier, même en mode sombre ; rien
ne repose sur la couleur seule (signe « - », coche ✔ écrite), pour les
imprimantes noir et blanc.
"""

from html import escape as _esc   # « B&C » → « B&amp;C » : sinon le & casse le HTML

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QMessageBox, QPushButton, QTextBrowser,
    QVBoxLayout,
)

from ..accords import pluriel
from ..constants import type_affiche
from ..destinations import avec_extension, destination_refusee
from ..theme import CLAIR
from ..utils import fmt_date_fr, fmt_euro, fmt_euro_signe, period_label

ROUGE, VERT, FOND_ENTETE = "#BC3729", "#18733A", "#E8EEF7"


class FenetreApercu(QDialog):
    """Aperçu avant impression, avec « Enregistrer en PDF… », « Imprimer… »
    et « Fermer ». Les sous-classes remplissent `self.browser` et peuvent
    ajouter des réglages en haut (`self.disposition.insertWidget(0, …)`)."""

    def __init__(self, parent, db, titre: str):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle(titre)
        self.resize(760, 640)

        self.disposition = QVBoxLayout(self)
        self.browser = QTextBrowser()
        self.browser.setStyleSheet("QTextBrowser { background:#FAF8F1; padding:10px }")
        # L'aperçu reste clair, comme le papier où il s'imprime : son HTML
        # ne fixe pas la couleur du texte, qui viendrait sinon du thème (blanc
        # cassé en sombre, illisible sur l'ivoire ; vu le 14/10/2026).
        clair = self.browser.palette()
        for role, cle in ((QPalette.Text, "texte"), (QPalette.Base, "carte"),
                          (QPalette.Link, "lien"),
                          (QPalette.LinkVisited, "lien_vu")):
            clair.setColor(role, QColor(CLAIR[cle]))
        self.browser.setPalette(clair)
        self.disposition.addWidget(self.browser, 1)

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
        self.disposition.addLayout(btns)

    def nom_pdf(self) -> str:
        """Nom proposé pour le fichier PDF (sans dossier)."""
        return "impression.pdf"

    def _save_pdf(self):
        from PySide6.QtPrintSupport import QPrinter
        titre = self.windowTitle()
        path, _ = QFileDialog.getSaveFileName(
            self, f"Enregistrer — {titre}", self.nom_pdf(), "PDF (*.pdf)")
        if not path:
            return
        # Jamais par-dessus le fichier de comptes (audit du 14/10/2026, A01).
        raison = destination_refusee(path, self.db.path)
        path = avec_extension(path, ".pdf")
        raison = raison or destination_refusee(path, self.db.path)
        if raison:
            QMessageBox.warning(self, titre, raison)
            return
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(path)
        self.browser.document().print_(printer)
        QMessageBox.information(self, titre, f"PDF enregistré :\n{path}")

    def _print(self):
        from PySide6.QtPrintSupport import QPrinter, QPrintDialog
        printer = QPrinter(QPrinter.HighResolution)
        dlg = QPrintDialog(printer, self)
        if dlg.exec() == QDialog.Accepted:
            self.browser.document().print_(printer)


# ── Liste des opérations ────────────────────────────────────────────────────

def lignes_affichees(vue) -> list[dict]:
    """Les opérations de l'onglet Opérations, dans l'ordre où le tableau les
    montre (tri par clic sur un en-tête compris)."""
    par_id = {t["id"]: t for t in vue.filtered}
    modele = vue.model
    lignes = []
    for r in range(modele.rowCount()):
        t = par_id.get(modele.item(r, 0).data(Qt.UserRole))
        if t is not None:
            lignes.append(t)
    return lignes


def criteres_operations(vue) -> list[str]:
    """Ce qui a choisi les opérations, écrit sur la feuille : sans cela, une
    liste imprimée ne dit pas si elle est complète."""
    pointage = vue.pt_filter.currentText()
    # « Non pointées » ne s'arrête pas au mois affiché (voir
    # OperationsView.refresh) : la feuille le dit.
    periode = ("Toute la période" if pointage == "Non pointées"
               else period_label(vue.period))
    criteres = [f"Période : {periode}"]
    if pointage not in ("", "Toutes"):
        criteres.append(f"Pointage : {pointage}")
    if vue.cat_filter.currentText() not in ("", "Toutes"):
        criteres.append(f"Catégorie : {vue.cat_filter.currentText()}")
    if vue.optype_filter.currentData() not in (None, "", "Tous"):
        criteres.append(f"Type : {vue.optype_filter.currentText()}")
    if vue.type_filter.currentText() not in ("", "Tous"):
        criteres.append(f"Sens : {vue.type_filter.currentText()}")
    if vue.search.text().strip():
        criteres.append(f"Recherche : « {vue.search.text().strip()} »")
    return criteres


def html_operations(lignes: list[dict], criteres: list[str], date_mode: str,
                    compte: str = "") -> str:
    """Feuille de la liste des opérations, en HTML compatible QTextDocument.
    `date_mode` : « valeur » ou « operation », comme le sélecteur Date."""
    en_valeur = date_mode == "valeur"

    def date_de(t):
        if en_valeur:
            return t.get("date_valeur") or t.get("date", "")
        return t.get("date", "")

    debits = sum(t.get("montant", 0) or 0 for t in lignes
                 if (t.get("montant", 0) or 0) < 0)
    credits = sum(t.get("montant", 0) or 0 for t in lignes
                  if (t.get("montant", 0) or 0) > 0)
    mouvement = debits + credits

    suffixe = f" — {_esc(compte)}" if compte else ""
    H = [f"<h1>📒 Pécule — Opérations{suffixe}</h1>"]
    H.append("<p>" + "<br>".join(_esc(c) for c in criteres) + "</p>")
    quelle_date = "date de valeur" if en_valeur else "date d'opération"
    H.append(f"<p><i>{pluriel(len(lignes), 'opération', 'opérations')}, "
             f"datées à la {quelle_date}. ✔ = opération pointée.</i></p>")

    # <thead> : Qt répète la ligne de titres en haut de chaque page.
    H.append('<table cellpadding="4" cellspacing="0" width="100%" border="0">'
             f'<thead><tr bgcolor="{FOND_ENTETE}">'
             '<td><b>P</b></td><td><b>Date</b></td><td><b>Libellé</b></td>'
             '<td><b>Catégorie</b></td><td align="right"><b>Débit</b></td>'
             '<td align="right"><b>Crédit</b></td></tr></thead>')
    for t in lignes:
        m = t.get("montant", 0) or 0
        if t.get("pointee"):
            p = "✔"
        elif t.get("prevue"):
            p = "prévue"
        else:
            p = ""
        cat = t.get("categorie", "") or ""
        if t.get("sous_cat"):
            cat += f" › {t['sous_cat']}"
        debit = (f'<font color="{ROUGE}">{fmt_euro(m)}</font>' if m < 0 else "")
        credit = (f'<font color="{VERT}">{fmt_euro(m)}</font>' if m > 0 else "")
        libelle = t.get("libelle", "") or ""
        if (t.get("type") or "").strip():
            libelle += f" ({type_affiche(t['type'].strip())})"
        H.append(f'<tr><td>{p}</td><td>{fmt_date_fr(date_de(t))}</td>'
                 f'<td>{_esc(libelle)}</td><td>{_esc(cat)}</td>'
                 f'<td align="right">{debit}</td>'
                 f'<td align="right">{credit}</td></tr>')
    H.append("</table>")

    # Totaux : signes écrits, la couleur ne porte jamais seule le sens.
    H.append('<table cellpadding="4" cellspacing="0" width="100%"><tr>'
             f'<td>Total des débits : <b>{fmt_euro_signe(debits)}</b></td>'
             f'<td>Total des crédits : <b>{fmt_euro_signe(credits)}</b></td>'
             f'<td align="right">Mouvement : <b>{fmt_euro_signe(mouvement)}</b>'
             '</td></tr></table>')
    return "\n".join(H)


class ApercuOperations(FenetreApercu):
    """Aperçu des opérations affichées dans l'onglet Opérations."""

    def __init__(self, parent, db, vue):
        super().__init__(parent, db, "Imprimer les opérations")
        self.vue = vue
        compte = db.nom_compte() if len(db.list_comptes()) > 1 else ""
        self.browser.setHtml(html_operations(
            lignes_affichees(vue), criteres_operations(vue), vue.date_mode,
            compte))

    def nom_pdf(self) -> str:
        periode = ("tout" if self.vue.period == "all" else self.vue.period)
        if self.vue.pt_filter.currentText() == "Non pointées":
            periode = "non-pointees"
        return f"operations-{periode}.pdf"
