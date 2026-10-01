"""Comportements (relecture de design du 30/09/2026).

Chacun de ces tests a été écrit avant la correction et vu en échec.
"""
from datetime import date

import pytest
from PySide6.QtCore import Qt

from comptesbudget.database import Database


def _tx(**kw):
    base = {"id": "x", "date": "2026-06-01", "date_valeur": "2026-06-01",
            "libelle": "OP", "libelle_op": "OP", "reference": "", "type": "",
            "categorie": "Non classé", "sous_cat": "", "info": "",
            "montant": -10.0, "pointee": 1}
    base.update(kw)
    return base


@pytest.fixture
def db(tmp_path):
    d = Database(str(tmp_path / "comportements.db"))
    d.set_setting("initial_balance", "1000")
    d.set_setting("initial_date", "2020-01-01")
    jour = date.today().replace(day=1).isoformat()
    d.insert_tx(_tx(id="a", date=jour, date_valeur=jour, categorie="Alimentation",
                    sous_cat="Courses", libelle="Courses", montant=-50.0))
    return d


# ── Sélecteur de période ────────────────────────────────────────────────

SANS_PERIODE = ("subs_view", "rules_view", "prev_view")


def test_periode_grisee_la_ou_elle_ne_sert_pas(qapp, db):
    """Charte : « Un onglet où la période n'a pas de sens grise le sélecteur
    avec une infobulle qui le dit. » Sous-catégories affichait les totaux de
    tout l'historique sous « Septembre 2026 »."""
    from comptesbudget.ui.main_window import MainWindow
    w = MainWindow(db)
    barre = w.period_bar
    for nom in SANS_PERIODE:
        w.tabs.setCurrentWidget(getattr(w, nom))
        assert not barre.annee_combo.isEnabled(), nom
        assert not barre.prev_btn.isEnabled(), nom
        assert "pas d'effet" in barre.annee_combo.toolTip(), nom
        # Les raccourcis ne changent pas la période en douce.
        avant = barre.current_period()
        barre._decaler(-1)
        assert barre.current_period() == avant, nom
    w.tabs.setCurrentWidget(w.ops_view)
    assert barre.annee_combo.isEnabled()
    assert "pas d'effet" not in barre.annee_combo.toolTip()


def test_choix_de_la_date_grise_sur_le_budget(qapp, db):
    """Le Budget compte toujours à la date d'achat : le menu « Date » n'y a
    pas d'effet, il le dit."""
    from comptesbudget.ui.main_window import MainWindow
    w = MainWindow(db)
    w.tabs.setCurrentWidget(w.budget_view)
    assert w.period_bar.annee_combo.isEnabled()
    assert not w.period_bar.date_mode_combo.isEnabled()
    assert "date d'achat" in w.period_bar.date_mode_combo.toolTip()
    w.tabs.setCurrentWidget(w.bilan_view)
    assert w.period_bar.date_mode_combo.isEnabled()


# ── États vides ─────────────────────────────────────────────────────────

def _phrases_visibles(vue):
    from PySide6.QtWidgets import QLabel
    return [lbl.text() for lbl in vue.findChildren(QLabel, "etatVide")
            if not lbl.isHidden() and lbl.text()]


def _vues_rafraichies(base):
    from comptesbudget.ui.views.bilan import BilanView
    from comptesbudget.ui.views.budget import BudgetView
    from comptesbudget.ui.views.categories import CategoriesView
    from comptesbudget.ui.views.operations import OperationsView
    from comptesbudget.ui.views.previsionnel import PrevisionnelView
    from comptesbudget.ui.views.rules_view import RulesView
    from comptesbudget.ui.views.subcategories import SubcategoriesView
    vues = {"Bilan": BilanView(base), "Opérations": OperationsView(base),
            "Budget": BudgetView(base), "Catégories": CategoriesView(base),
            "Sous-catégories": SubcategoriesView(base),
            "Règles auto": RulesView(base), "Prévisionnel": PrevisionnelView(base)}
    for vue in vues.values():
        (vue.reload_from_db if hasattr(vue, "reload_from_db") else vue.refresh)()
    return vues


def test_etats_vides_disent_pourquoi_et_comment_commencer(qapp, tmp_path):
    """Charte : « un tableau ou une page sans données affiche une phrase
    centrée, en gris discret, qui dit pourquoi » ; le plugin Design ajoute :
    et comment commencer. Les onglets montraient des grilles vides et des
    graphiques aux axes « … »."""
    vues = _vues_rafraichies(Database(str(tmp_path / "vide.db")))
    for nom, vue in vues.items():
        assert _phrases_visibles(vue), f"{nom} : grille vide sans phrase"
    assert any("Importez" in p for p in _phrases_visibles(vues["Opérations"]))
    assert any("Pré-remplir" in p for p in _phrases_visibles(vues["Prévisionnel"]))


def test_etats_vides_disparaissent_avec_les_donnees(qapp, db):
    vues = _vues_rafraichies(db)
    for nom in ("Opérations", "Sous-catégories"):
        assert not _phrases_visibles(vues[nom]), nom


# ── Cases à cocher des assistants ───────────────────────────────────────

def _assistants(db):
    from comptesbudget.ui.assistants import (
        DuplicatesDialog, GenererEcheancesDialog, HarmonizeDialog,
        HarmonizeLabelsDialog, PrefillRecurringDialog,
    )
    txs = [dict(r) for r in db.list_tx()]
    candidat = {"libelle": "Loyer", "categorie": "Logement - maison",
                "montant": -800.0, "frequency": "monthly", "day_of_month": 5,
                "_months": 6, "_min": -800.0, "_max": -800.0, "_stable": True,
                "_default": True, "sous_cat": "", "type": ""}
    echeance = {"date": date.today().isoformat(), "libelle": "Loyer",
                "montant": -800.0, "categorie": "Logement - maison",
                "sous_cat": "", "type": "", "_deja": False, "_default": True,
                "_passee": False}
    libelle = {"old": "COURSES 123", "new": "Courses", "n": 1,
               "tx_ids": ["a"], "rec_ids": []}
    mois = date.today().strftime("%Y-%m")
    return {
        "Suggérer catégories": HarmonizeDialog(None, [(txs[0], "Shopping")]),
        "Doublons": DuplicatesDialog(None, txs),
        "Pré-remplir": PrefillRecurringDialog(None, [candidat]),
        "Échéances": GenererEcheancesDialog(None, lambda _m: [echeance], mois, [mois]),
        "Harmoniser libellés": HarmonizeLabelsDialog(None, [libelle]),
    }


def test_assistants_ont_de_vraies_cases_a_cocher(qapp, db):
    """Un ✔ écrit dans une cellule, et une cellule vide une fois décochée :
    rien ne montrait qu'on pouvait cliquer, et le clavier ne cochait rien.
    Ce sont maintenant des cases de Qt (clic, barre d'espace)."""
    from PySide6.QtTest import QTest
    for nom, dlg in _assistants(db).items():
        it = dlg.model.item(0, 0)
        assert it.isCheckable(), nom
        assert it.text() != "✔", nom
        assert it.checkState() == Qt.Checked, nom
        assert dlg.selected(), nom
        # Au clavier : la barre d'espace décoche la ligne courante.
        dlg.table.setCurrentIndex(dlg.model.index(0, 0))
        QTest.keyClick(dlg.table, Qt.Key_Space)
        assert it.checkState() == Qt.Unchecked, f"{nom} : Espace sans effet"
        assert not dlg.selected(), nom
        dlg._set_all(True)
        assert dlg.selected(), nom


def _pixels_de_contour(widget) -> int:
    """Nombre de pixels de la couleur de contour de la charte (#6F7885)
    dans le rendu du widget."""
    from PySide6.QtGui import QColor
    img = widget.grab().toImage()
    cible = QColor("#6F7885")
    n = 0
    for x in range(img.width()):
        for y in range(img.height()):
            c = img.pixelColor(x, y)
            if (abs(c.red() - cible.red()) < 12 and abs(c.green() - cible.green()) < 12
                    and abs(c.blue() - cible.blue()) < 12):
                n += 1
    return n


def test_case_decochee_a_un_contour_visible(qapp):
    """Sous le style Fusion, une case décochée n'avait qu'un contour pâle,
    invisible dans les listes. Charte : ce qu'on clique tient 3 pour 1 —
    contour #6F7885."""
    from PySide6.QtWidgets import QCheckBox, QRadioButton
    from comptesbudget.app import appliquer_theme_clair
    appliquer_theme_clair(qapp)
    for widget in (QCheckBox(), QRadioButton()):
        widget.resize(20, 20)
        assert _pixels_de_contour(widget) >= 12, type(widget).__name__


def test_notice_limitee_a_110_signes_par_ligne(qapp):
    """Charte : un long texte ne dépasse pas ~110 signes par ligne (780 px).
    La notice en faisait ~150 dans sa fenêtre de 900 px."""
    from PySide6.QtWidgets import QTextBrowser, QTextEdit
    from comptesbudget.ui.views.notice import NoticeView
    vue = NoticeView()
    for texte in vue.findChildren(QTextBrowser):
        assert texte.lineWrapMode() == QTextEdit.FixedPixelWidth
        assert texte.lineWrapColumnOrWidth() <= 780


def test_pre_remplir_garde_accents_et_sigles():
    """Pré-remplir affichait « Edf Electricite » et « Sncf » : le libellé
    était refait depuis une forme sans accents ni majuscules."""
    from comptesbudget.recurring import detect_recurring_candidates
    ops = []
    for i, mois in enumerate(range(1, 7)):
        jour = f"2026-{mois:02d}-05"
        ops.append(_tx(id=f"e{i}", date=jour, date_valeur=jour,
                       libelle="EDF ÉLECTRICITÉ", montant=-84.0))
    libelles = [c["libelle"] for c in detect_recurring_candidates(ops, min_months=3)]
    assert libelles == ["EDF Électricité"], libelles


# ── Menu de gauche et bandeau Encours carte (choix de l'auteur, 01/10) ──

def test_mettre_au_propre_tient_dans_un_bouton(qapp, db):
    """Quatre boutons d'affilée faisaient déborder le menu sur un portable :
    un seul bouton « Mettre au propre… » ouvre les quatre outils."""
    from PySide6.QtWidgets import QPushButton, QScrollArea
    from comptesbudget.ui.main_window import MainWindow
    w = MainWindow(db)
    menu = w.centralWidget().findChild(QScrollArea).widget()
    textes = [b.text() for b in menu.findChildren(QPushButton)]
    assert "🧹 Mettre au propre…" in textes
    for ancien in ("🧹 Nettoyer catégories", "🔧 Suggérer catégories",
                   "🔠 Harmoniser libellés", "🔍 Chercher doublons"):
        assert ancien not in textes, ancien
    bouton = next(b for b in menu.findChildren(QPushButton)
                  if b.text() == "🧹 Mettre au propre…")
    actions = [a.text() for a in bouton.menu().actions()]
    assert actions == ["🧹 Nettoyer catégories", "🔧 Suggérer catégories",
                       "🔠 Harmoniser libellés", "🔍 Chercher doublons"]


def test_choix_du_compte_au_bout_des_onglets(qapp, db):
    """Le choix du compte prenait trois lignes du menu : il passe au bout de
    la rangée d'onglets, et ne s'y montre qu'avec plusieurs comptes."""
    from PySide6.QtWidgets import QScrollArea
    from comptesbudget.ui.main_window import MainWindow
    w = MainWindow(db)
    menu = w.centralWidget().findChild(QScrollArea).widget()
    coin = w.tabs.cornerWidget(Qt.TopRightCorner)
    assert coin is not None and coin.isAncestorOf(w.compte_combo)
    assert not menu.isAncestorOf(w.compte_combo)
    assert coin.isHidden()                       # un seul compte
    db.add_compte("Livret", 0.0, "2026-01-01")
    w.refresh_all()
    assert not coin.isHidden()


def test_bandeau_carte_allege(qapp, tmp_path):
    """Le bandeau Encours carte alignait cinq lignes de détail : il garde la
    phrase « il reste… » ; le reste passe au survol."""
    from comptesbudget.ui.views.bilan import BilanView
    from comptesbudget.utils import date_debit_differe
    d = Database(str(tmp_path / "carte.db"))
    d.set_setting("initial_balance", "1000")
    d.set_setting("initial_date", "2020-01-01")
    jour = date.today().isoformat()
    d.insert_tx(_tx(id="cb", date=jour, date_valeur=date_debit_differe(jour),
                    type="Carte bancaire", libelle="Achat", montant=-200.0,
                    pointee=0))
    vue = BilanView(d)
    vue.refresh()
    visible = vue.cb_detail.text()
    assert "il reste" in visible or "il MANQUE" in visible
    assert "Mois précédent" not in visible
    assert "survol" in visible
    assert "Mois précédent" in vue.cb_banner.toolTip()


# ── Haut du Bilan allégé (relecture de design du 01/10/2026) ────────────

def _bilan_du_mois(tmp_path):
    """Un compte avec une échéance encore à passer ce mois-ci : le bandeau
    « Ce mois-ci » a donc quelque chose à dire."""
    from comptesbudget.ui.views.bilan import BilanView
    d = Database(str(tmp_path / "mois.db"))
    d.set_setting("initial_balance", "1000")
    d.set_setting("initial_date", "2020-01-01")
    jour = date.today().isoformat()
    d.insert_tx(_tx(id="edf", date=jour, date_valeur=jour, type="Prelevement",
                    libelle="EDF", montant=-80.0, pointee=0))
    vue = BilanView(d)
    vue.refresh()
    return vue


def _textes_visibles(cadre, sauf=None):
    """Le texte de chaque étiquette visible d'un cadre, sans mise en forme."""
    import re
    from PySide6.QtWidgets import QLabel
    return [re.sub("<[^>]+>", "", l.text()) for l in cadre.findChildren(QLabel)
            if l is not sauf and l.isVisibleTo(cadre)]


def test_verdict_dans_le_bandeau_du_mois(qapp, tmp_path):
    """Le verdict et le bandeau « Ce mois-ci » parlaient du même mois en
    deux bandeaux verts superposés : un seul bandeau les porte."""
    vue = _bilan_du_mois(tmp_path)
    assert vue.mois_banner.isAncestorOf(vue.verdict_banner)
    assert vue.verdict_banner.isVisibleTo(vue)


def test_solde_de_fin_de_mois_dit_une_seule_fois(qapp, tmp_path):
    """« Solde au 31/10 » répétait le chiffre que le verdict donne en gras
    juste au-dessus (charte : un chiffre ne se répète pas)."""
    from comptesbudget.utils import fmt_euro
    vue = _bilan_du_mois(tmp_path)
    fin = fmt_euro(920.0)                      # 1 000 − 80
    assert fin in vue.verdict_banner.text()
    autres = _textes_visibles(vue.mois_banner, sauf=vue.verdict_banner)
    assert not any(fin in t for t in autres), autres


def test_detail_du_mois_au_survol(qapp, tmp_path):
    """Le détail du bandeau « Ce mois-ci » tenait quatre lignes en petits
    caractères : la phrase utile reste, le reste passe au survol, comme
    pour l'Encours carte."""
    vue = _bilan_du_mois(tmp_path)
    visible = vue.mois_detail.text()
    assert "Prochaines" in visible
    assert "survol" in visible
    assert "Solde en banque aujourd'hui" not in visible   # déjà dans la tuile
    assert "Solde en banque aujourd'hui" in vue.mois_detail_complet
    assert "Solde en banque aujourd'hui" in vue.mois_banner.toolTip()


def test_encours_carte_sans_moins_zero(qapp, tmp_path):
    """« Solde prévu fin de mois X moins 0,00 € déjà passés à la carte — il
    reste X » : une soustraction de zéro qui ne dit rien."""
    from datetime import timedelta
    from comptesbudget.ui.views.bilan import BilanView
    from comptesbudget.utils import fmt_euro
    d = Database(str(tmp_path / "carte0.db"))
    d.set_setting("initial_balance", "1000")
    d.set_setting("initial_date", "2020-01-01")
    # Un achat du mois dernier, pas encore prélevé ; rien ce mois-ci.
    achat = (date.today().replace(day=1) - timedelta(days=5)).isoformat()
    prelevement = (date.today() + timedelta(days=3)).isoformat()
    d.insert_tx(_tx(id="cb", date=achat, date_valeur=prelevement,
                    type="Carte bancaire", libelle="Achat", montant=-200.0,
                    pointee=0))
    vue = BilanView(d)
    vue.refresh()
    assert vue.cb_banner.isVisibleTo(vue)
    visible = vue.cb_detail.text()
    assert "moins " + fmt_euro(0) not in visible
    assert "il reste" in visible


# ── Un nom par chose────────────────────────────────────────────────────

def test_operations_parlent_de_mouvement_pas_de_solde(qapp, db):
    """Le compteur des Opérations appelait « solde » la somme des opérations
    affichées, que le Bilan appelle « mouvement »."""
    from comptesbudget.ui.views.operations import OperationsView
    vue = OperationsView(db)
    vue.reload_from_db()
    texte = vue.lbl_count.text()
    assert "solde" not in texte.lower(), texte
    assert "mouvement" in texte.lower(), texte


def test_rapport_dit_a_quelle_date_il_compte(qapp, db):
    """Le Rapport compte à la date d'achat, le Bilan à la date de valeur :
    deux « mouvements » différents pour le même mois, sans explication."""
    from comptesbudget.ui.report import build_monthly_report_html
    html = build_monthly_report_html(db, date.today().strftime("%Y-%m"))
    assert "date d'achat" in html
    assert "Mouvement du mois" in html
    assert "Mouvement net" not in html


# ── Tris et catégorie par défaut (relecture de design du 01/10/2026) ────

def _base_a_trier(tmp_path):
    """Deux catégories, deux sous-catégories et deux récurrences, insérées de
    Z à A pour que l'ordre d'insertion ne fasse pas le tri à leur place."""
    d = Database(str(tmp_path / "tris.db"))
    d.set_setting("initial_balance", "1000")
    d.set_setting("initial_date", "2020-01-01")
    jour = date.today().replace(day=1).isoformat()
    d.insert_tx(_tx(id="t", date=jour, date_valeur=jour, categorie="Transports",
                    sous_cat="Train", libelle="SNCF", montant=-30.0))
    d.insert_tx(_tx(id="a", date=jour, date_valeur=jour, categorie="Alimentation",
                    sous_cat="Courses", libelle="Marché", montant=-20.0))
    for i, libelle in enumerate(("Zinc", "Assurance")):
        d.insert_recurring({
            "id": f"r{i}", "libelle": libelle, "montant": -10.0,
            "categorie": "Alimentation", "sous_cat": "", "type": "",
            "frequency": "monthly", "day_of_month": 5,
            "start_date": jour, "end_date": None, "actif": 1})
    return d


def test_tableaux_ouverts_de_a_a_z(qapp, tmp_path):
    """Catégories, Sous-catégories et les récurrences du Prévisionnel
    s'ouvraient triés de Z à A : l'indicateur de tri de Qt est décroissant
    tant qu'on ne lui dit rien. Budget, lui, partait de A."""
    from comptesbudget.ui.views.categories import CategoriesView
    from comptesbudget.ui.views.previsionnel import PrevisionnelView
    from comptesbudget.ui.views.subcategories import SubcategoriesView
    d = _base_a_trier(tmp_path)

    cats = CategoriesView(d); cats.refresh()
    sous = SubcategoriesView(d); sous.refresh()
    prev = PrevisionnelView(d); prev.refresh()
    premiers = {
        "catégories": cats.cats_table.model().index(0, 0).data(),
        "sous-catégories": sous.table.model().index(0, 0).data(),
        "récurrences": prev.table.model().index(0, 0).data(),
    }
    assert premiers == {"catégories": "Alimentation",
                        "sous-catégories": "Courses",
                        "récurrences": "Assurance"}
    for table in (cats.cats_table, sous.table, prev.table):
        assert table.horizontalHeader().sortIndicatorOrder() == Qt.AscendingOrder


CATEGORIES = ["Abonnements", "Alimentation", "Transports"]


def test_nouvelle_saisie_sans_categorie_imposee(qapp):
    """« Nouvelle opération », « Nouvelle règle » et « Nouvelle opération
    récurrente » proposaient « Abonnements », la première de la liste : une
    saisie validée sans y toucher était classée là sans raison."""
    from comptesbudget.ui.dialogs import RecurringDialog, RuleDialog, TxDialog
    for dlg in (TxDialog(None, None, CATEGORIES, []),
                RuleDialog(None, None, CATEGORIES),
                RecurringDialog(None, None, CATEGORIES, [])):
        assert dlg.cat.currentText() == "", type(dlg).__name__
        assert dlg.cat.count() == len(CATEGORIES)     # la liste reste là
        dlg.deleteLater()


def test_modifier_garde_sa_categorie(qapp):
    """Une modification, elle, rouvre sur la catégorie enregistrée."""
    from comptesbudget.ui.dialogs import RuleDialog
    dlg = RuleDialog(None, {"pattern": "sncf", "categorie": "Transports"},
                     CATEGORIES)
    assert dlg.cat.currentText() == "Transports"
    dlg.deleteLater()


def test_regle_sans_categorie_refusee(qapp, db, monkeypatch):
    """Une règle sans catégorie ne classerait rien : elle est refusée, comme
    un motif trop court."""
    from PySide6.QtWidgets import QDialog, QMessageBox
    from comptesbudget.ui import dialogs
    from comptesbudget.ui.views.rules_view import RulesView
    monkeypatch.setattr(dialogs.RuleDialog, "exec", lambda self: QDialog.Accepted)
    monkeypatch.setattr(dialogs.RuleDialog, "values", lambda self: {
        "pattern": "sncf", "amount": None, "sens": "", "categorie": "",
        "sous_cat": "", "no_overwrite": 0})
    titres = []
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda parent, titre, texte, *a: titres.append(titre))
    vue = RulesView(db)
    vue.new_rule()
    assert titres == ["Catégorie manquante"]
    assert not db.list_rules()


def test_memoriser_sans_categorie_ne_cree_pas_de_regle(qapp, db, monkeypatch):
    """La case Catégorie de la saisie s'ouvre vide : « Mémoriser » cochée sans
    catégorie aurait créé une règle qui classe en « Non classé »."""
    from PySide6.QtWidgets import QMessageBox
    from comptesbudget.ui.views.operations import OperationsView
    titres = []
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda parent, titre, texte, *a: titres.append(texte))
    # La boîte « Règle créée » attendrait un clic : on la neutralise aussi.
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    vue = OperationsView(db)
    vue._maybe_create_rule({"_create_rule": True,
                            "_rule": {"pattern": "sncf", "amount": None},
                            "montant": -30.0, "categorie": "Non classé",
                            "sous_cat": ""})
    assert not db.list_rules()
    assert titres and "bien enregistrée" in titres[0]


# ── Tableaux pleine largeur (relecture de design du 01/10/2026) ─────────

def test_tableaux_occupent_toute_la_largeur(qapp, db):
    """Budget, Sous-catégories, Règles auto et les deux tableaux du
    Prévisionnel avaient toutes leurs colonnes réglées à la main : l'en-tête
    s'arrêtait avant le bord, un bloc blanc à sa droite. Comme Opérations,
    une colonne de texte prend la place restante, et les colonnes de
    chiffres gardent la largeur de leur contenu."""
    from PySide6.QtWidgets import QHeaderView
    from comptesbudget.ui.main_window import MainWindow
    w = MainWindow(db)
    tableaux = {
        "budget": (w.budget_view.table, 3, (1, 2, 4)),   # la barre s'élargit
        "sous-catégories": (w.subs_view.table, 0, (2, 3)),
        "règles": (w.rules_view.table, 0, (1, 2, 5)),
        "récurrences": (w.prev_view.table, 0, (1, 5, 6)),
        "prévisions": (w.prev_view.forecast_table, 1, (0, 2)),
    }
    for vue in (w.budget_view, w.subs_view, w.rules_view, w.prev_view):
        vue.refresh()        # Budget et Sous-catégories réglaient au remplissage
    for nom, (table, etirable, chiffres) in tableaux.items():
        entete = table.horizontalHeader()
        assert entete.sectionResizeMode(etirable) == QHeaderView.Stretch, nom
        for col in chiffres:
            assert (entete.sectionResizeMode(col)
                    == QHeaderView.ResizeToContents), (nom, col)


def _rang_dans_la_page(vue, widget):
    """Rang, dans la colonne principale de la page, de la rangée qui contient
    le widget : plus petit = plus haut à l'écran."""
    lay = vue.layout()
    for i in range(lay.count()):
        item = lay.itemAt(i)
        if item.widget() is widget:
            return i
        if item.layout() is not None and item.layout().indexOf(widget) >= 0:
            return i
    raise AssertionError(f"{widget} absent de la page")


def test_boutons_au_dessus_du_tableau(qapp, db):
    """Les boutons étaient en haut dans Opérations et Prévisionnel, en bas
    dans Budget et Sous-catégories, des deux côtés dans Règles auto."""
    from comptesbudget.ui.main_window import MainWindow
    w = MainWindow(db)
    pages = {
        "budget": (w.budget_view, [w.budget_view.btn_edit]),
        "sous-catégories": (w.subs_view, [w.subs_view.btn_rename,
                                          w.subs_view.btn_clear,
                                          w.subs_view.btn_clean]),
        "règles": (w.rules_view, [w.rules_view.btn_new, w.rules_view.btn_edit,
                                  w.rules_view.btn_del, w.rules_view.btn_apply]),
    }
    for nom, (vue, boutons) in pages.items():
        tableau = _rang_dans_la_page(vue, vue.table)
        for b in boutons:
            assert _rang_dans_la_page(vue, b) < tableau, (nom, b.text())
