"""Impression : la fenêtre d'aperçu commune (PDF, imprimante) et la liste
des opérations, puis le Bilan avec ses graphiques.

Plan retenu le 15/10/2026 et avancé à la sortie du 01/11/2026 : une entrée
« 🖨 Imprimer… » au menu de gauche, qui demande quoi imprimer puis montre un
aperçu. Toujours sur fond clair, comme le papier, même en mode sombre ; rien
ne repose sur la couleur seule (signe « - », coche ✔ écrite), pour les
imprimantes noir et blanc.
"""

from datetime import date
from html import escape as _esc   # « B&C » → « B&amp;C » : sinon le & casse le HTML

from PySide6.QtCore import QPoint, Qt, QUrl
from PySide6.QtGui import (
    QColor, QImage, QPalette, QPixmap, QRegion, QTextDocument,
)
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QMessageBox, QPushButton, QTextBrowser,
    QVBoxLayout, QWidget,
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


# ── Bilan avec ses graphiques ───────────────────────────────────────────────

# Largeur de la copie du Bilan photographiée (en pixels d'écran), puis de
# chaque bloc sur la feuille. Plus étroite que l'écran, la copie garde des
# textes lisibles une fois réduite à la largeur d'une page A4.
LARGEUR_BILAN = 960
LARGEUR_IMAGE = 640
# Netteté : chaque bloc est photographié à deux fois la résolution de l'écran.
FINESSE = 2


def _photo(widget, rect, fond: str) -> QImage:
    """Image d'une zone `rect` de `widget`, sur le fond `fond`."""
    pix = QPixmap(rect.size() * FINESSE)
    pix.setDevicePixelRatio(FINESSE)
    pix.fill(QColor(fond))
    # DrawChildren seul : sans DrawWindowBackground, Qt ne repeint pas le
    # fond de la fenêtre par-dessus `fond`.
    widget.render(pix, QPoint(0, 0), QRegion(rect),
                  QWidget.RenderFlag.DrawChildren)
    return pix.toImage()


def photos_du_bilan(db, periode: str, date_mode: str) -> list:
    """Photographie, bloc par bloc, une copie du Bilan construite hors écran
    pour la période `periode`, TOUJOURS en couleurs claires : le papier est
    blanc, même quand l'écran est en mode sombre. Un bloc par image : une
    page de la feuille ne coupe jamais un graphique en deux.

    Le Bilan prend ses couleurs dans le thème au moment où il se dessine : le
    thème clair est donc posé le temps de la copie, puis celui de l'écran est
    remis, quoi qu'il arrive."""
    from PySide6.QtCharts import QChart
    from PySide6.QtWidgets import QApplication
    from .. import theme
    from ..app import appliquer_theme, appliquer_theme_clair
    from .views.bilan import BilanView

    app = QApplication.instance()
    ancien = theme.theme_actif()
    changer = ancien != "clair"
    if changer:
        theme.choisir_theme("clair")
        appliquer_theme_clair(app)
    try:
        vue = BilanView(db)
        # Sans animation : la photo montrerait des barres à mi-hauteur.
        for graphique in (vue.bar_chart, vue.pie_chart, vue.solde_chart):
            graphique.setAnimationOptions(QChart.NoAnimation)
        vue.period = periode
        vue.date_mode = date_mode
        # Jamais à l'écran : la copie n'existe que pour être photographiée.
        vue.setAttribute(Qt.WA_DontShowOnScreen, True)
        vue.resize(LARGEUR_BILAN, 900)
        vue.show()
        vue.refresh()
        # À l'écran, les bandeaux renvoient le détail « au survol » : sur
        # le papier, rien ne se survole, il est écrit en entier.
        for etiquette, complet in ((vue.mois_detail, vue.mois_detail_complet),
                                   (vue.cb_detail, vue.cb_detail_complet)):
            if complet.strip():
                etiquette.setText(complet)
        app.processEvents()
        contenu = vue.scroll.widget()
        # Le crème de la fenêtre vient d'une règle de style posée sur la zone
        # qui défile, héritée par tout le Bilan : la copie la rend
        # transparente, le blanc du papier passe dessous.
        vue.scroll.viewport().setStyleSheet("background: transparent;")
        contenu.setAutoFillBackground(False)
        # Hauteur naturelle du contenu : plus grande, les graphiques
        # s'étireraient pour remplir la place.
        vue.resize(LARGEUR_BILAN, contenu.sizeHint().height() + 4)
        for _ in range(3):
            app.processEvents()

        def zone(*widgets):
            visibles = [w for w in widgets if w.isVisible()]
            if not visibles:
                return None
            r = visibles[0].geometry()
            for w in visibles[1:]:
                r = r.united(w.geometry())
            # Un peu d'air autour du bloc, au fond de la page.
            return r.adjusted(-6, -6, 6, 6)

        # Les rappels propres à l'écran (sauvegarde, solde de départ,
        # opérations antérieures) n'ont rien à faire sur le papier.
        blocs = [
            zone(*vue.kpis.values()),
            zone(vue.mois_banner),
            zone(vue.cb_banner),
            zone(vue.budget_alert),
            zone(vue.bar_panel, vue.pie_view.parentWidget()),
            zone(vue.solde_panel),
            zone(vue.list_dep.parentWidget(), vue.list_rev.parentWidget(),
                 vue.list_top.parentWidget()),
        ]
        # Autour des blocs, le blanc du papier plutôt que le crème de la
        # fenêtre : pas d'encre dépensée pour rien.
        images = [_photo(contenu, r, "#FFFFFF") for r in blocs if r is not None]
        vue.close()
        vue.deleteLater()
    finally:
        if changer:
            theme.choisir_theme(ancien)
            appliquer_theme(app)
    return images


class ApercuBilan(FenetreApercu):
    """Aperçu du Bilan de la période choisie, avec ses graphiques."""

    def __init__(self, parent, db, vue_bilan):
        super().__init__(parent, db, "Imprimer le Bilan")
        self.periode = vue_bilan.period
        self.images = photos_du_bilan(db, vue_bilan.period, vue_bilan.date_mode)

        compte = db.nom_compte() if len(db.list_comptes()) > 1 else ""
        suffixe = f" — {_esc(compte)}" if compte else ""
        quelle_date = ("date de valeur" if vue_bilan.date_mode == "valeur"
                       else "date d'opération")
        H = [f"<h1>📒 Pécule — Bilan{suffixe}</h1>",
             f"<p>Période : {_esc(period_label(self.periode))}<br>"
             f"<i>Opérations datées à la {quelle_date}. Généré le "
             f"{fmt_date_fr(date.today().isoformat())}.</i></p>"]
        doc = self.browser.document()
        for i, image in enumerate(self.images):
            nom = f"bilan-{i}.png"
            doc.addResource(QTextDocument.ImageResource, QUrl(nom), image)
            # Taille en points de la page : la largeur fixe, la hauteur suit.
            larg = image.width() / FINESSE
            haut = round(image.height() / FINESSE * LARGEUR_IMAGE / larg)
            H.append(f'<p><img src="{nom}" width="{LARGEUR_IMAGE}" '
                     f'height="{haut}"></p>')
        self.browser.setHtml("\n".join(H))

    def nom_pdf(self) -> str:
        return f"bilan-{'tout' if self.periode == 'all' else self.periode}.pdf"
