"""Mode sombre, étape 2 : chaque écran prend ses couleurs dans le thème.

Les écrans convertis n'écrivent plus aucune couleur en dur : elles viennent
de comptesbudget/theme.py (T["debit"], T["fond_page"]…). Ces tests le
vérifient fichier par fichier, et regardent le menu de gauche et le tableau
des opérations construits en sombre. La liste ECRANS_CONVERTIS s'allonge à
chaque écran converti. Données inventées.
"""
import io
import re
import tokenize
from pathlib import Path

import pytest

import comptesbudget
from comptesbudget import theme
from comptesbudget.theme import CLAIR, SOMBRE
from test_theme_sombre import contraste

UI = Path(comptesbudget.__file__).parent / "ui"

ECRANS_CONVERTIS = [
    # Étape 2, premier lot (14/10/2026) : le menu de gauche et les tableaux.
    "main_window.py",
    "models.py",
    "recapitulatif.py",
    "search.py",
    "views/budget.py",
    "views/categories.py",
    "views/operations.py",
    "views/previsionnel.py",
    "views/rules_view.py",
    "views/subcategories.py",
    # Deuxième lot : le Bilan et ses graphiques.
    "views/bilan.py",
    # Troisième lot : les fenêtres de saisie.
    "dialogs.py",
    # Quatrième lot : les assistants (doublons, harmonisation, prévisionnel).
    "assistants.py",
    # Cinquième lot : la Notice et le Glossaire.
    "views/notice.py",
    # Sixième lot : « Votre avis » et « Mise à jour ».
    "avis.py",
    "mise_a_jour.py",
]

HEXA = re.compile(r"(?<![&\w])#(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})(?![0-9A-Fa-f])")


def _chaines(fichier: Path):
    """Les chaînes du code (pas les commentaires)."""
    source = fichier.read_text(encoding="utf-8")
    types = {tokenize.STRING}
    if hasattr(tokenize, "FSTRING_MIDDLE"):
        types.add(tokenize.FSTRING_MIDDLE)
    for jeton in tokenize.generate_tokens(io.StringIO(source).readline):
        if jeton.type in types:
            yield jeton.start[0], jeton.string


@pytest.mark.parametrize("nom", ECRANS_CONVERTIS)
def test_aucune_couleur_ecrite_en_dur(nom):
    en_dur = [f"{nom}:{ligne} {m}"
              for ligne, texte in _chaines(UI / nom)
              for m in HEXA.findall(texte)]
    assert not en_dur, "Couleurs à prendre dans le thème :\n" + "\n".join(en_dur)


@pytest.mark.parametrize("palette", [CLAIR, SOMBRE], ids=["clair", "sombre"])
def test_barres_du_budget_lisibles(palette):
    """Le pourcentage s'écrit sur la barre et sur sa piste : il doit se lire
    sur les deux (4,5 pour 1), et une barre partielle se détacher de sa
    piste (3 pour 1). La barre rouge est toujours pleine : pas de piste."""
    p = palette
    assert contraste(p["budget_encre"], p["budget_piste"]) >= 4.5
    for barre in ("budget_ok", "budget_proche"):
        assert contraste(p["budget_encre"], p[barre]) >= 4.5, barre
        # Le clair, inchangé, en reste à 2,6 pour la verte : le pourcentage
        # écrit dessus porte l'information (charte, exception #27AE60).
        if palette is SOMBRE:
            assert contraste(p[barre], p["budget_piste"]) >= 3.0, barre
    assert contraste(p["budget_encre_depasse"], p["budget_depasse"]) >= 4.5


@pytest.fixture
def sombre():
    theme.choisir_theme("sombre")
    yield
    theme.choisir_theme("clair")


def _tx(**kw):
    base = {"id": "x", "date": "2026-06-01", "date_valeur": "2026-06-01",
            "libelle": "OP", "libelle_op": "OP", "reference": "", "type": "",
            "categorie": "Non classé", "sous_cat": "", "info": "",
            "montant": -10.0, "pointee": 1}
    base.update(kw)
    return base


def test_tableau_des_operations_en_sombre(qapp, sombre):
    from comptesbudget.ui.models import TxTableModel
    modele = TxTableModel()
    modele.load([_tx(id="a", pointee=1, montant=-10.0),
                 _tx(id="b", pointee=0, montant=20.0)])

    def encre(ligne, col):
        return modele.item(ligne, col).foreground().color().name().upper()

    # Opération pointée : case P verte sur son fond vert, le reste en gris.
    assert encre(0, 0) == SOMBRE["credit"]
    assert (modele.item(0, 0).background().color().name().upper()
            == SOMBRE["pointe_fond"])
    assert encre(0, 3) == SOMBRE["texte_grise"]
    # Montants : rouge et vert du sombre, éclaircis pour se lire.
    assert encre(1, 7) == SOMBRE["debit"]
    assert encre(1, 8) == SOMBRE["credit"]


def test_menu_de_gauche_en_sombre(qapp, sombre, tmp_path):
    from PySide6.QtWidgets import QPushButton
    from comptesbudget.database import Database
    from comptesbudget.ui.main_window import MainWindow
    db = Database(str(tmp_path / "comptes.db"))
    db.set_setting("initial_date", "2026-01-01")
    db.set_setting("initial_balance", "100.0")
    fenetre = MainWindow(db)
    boutons = [b for b in fenetre.findChildren(QPushButton)
               if "text-align:left" in b.styleSheet()]
    assert boutons
    for b in boutons:
        style = b.styleSheet().upper()
        assert SOMBRE["bouton_fond"] in style, b.text()
        assert CLAIR["bouton_fond"] not in style, b.text()


@pytest.mark.parametrize("palette", [CLAIR, SOMBRE], ids=["clair", "sombre"])
def test_chiffres_des_barres_du_bilan_lisibles(palette):
    """Le montant de chaque barre s'écrit dedans, près du sommet."""
    p = palette
    assert contraste(p["barre_revenus_encre"], p["barre_revenus"]) >= 4.5
    assert contraste(p["barre_depenses_encre"], p["barre_depenses"]) >= 4.5


def test_bilan_en_sombre(qapp, sombre, tmp_path):
    """Cartes, tuiles et graphiques du Bilan construits en sombre : fond de
    carte sombre, axes et légendes dans les couleurs du texte du thème."""
    from datetime import date
    from PySide6.QtGui import QColor
    from comptesbudget.database import Database
    from comptesbudget.ui.views.bilan import BilanView
    db = Database(str(tmp_path / "comptes.db"))
    db.set_setting("initial_date", "2026-01-01")
    db.set_setting("initial_balance", "100.0")
    jour = date.today().replace(day=1).isoformat()
    db.insert_tx(_tx(id="a", date=jour, date_valeur=jour, montant=500.0,
                     categorie="Revenus"))
    db.insert_tx(_tx(id="b", date=jour, date_valeur=jour, montant=-50.0,
                     categorie="Alimentation"))
    vue = BilanView(db)
    vue.refresh()
    style = vue.kpis["solde"].styleSheet().upper()
    assert SOMBRE["carte"] in style and CLAIR["carte"] not in style
    for graphique in (vue.bar_chart, vue.pie_chart, vue.solde_chart):
        assert (graphique.legend().labelColor().name().upper()
                == SOMBRE["texte"])
    for graphique in (vue.bar_chart, vue.solde_chart):
        assert graphique.axes()
        for axe in graphique.axes():
            assert axe.labelsColor() == QColor(SOMBRE["texte_secondaire"])
            assert axe.gridLineColor() == QColor(SOMBRE["grille"])


@pytest.mark.parametrize("nom", ["clair", "sombre"])
def test_week_ends_du_calendrier_lisibles(qapp, nom):
    """Qt écrit samedis et dimanches en rouge vif, pur : 4,0 pour 1 sur
    le blanc, 3,7 sur le fond sombre, sous les 4,5 de la charte. Toutes les
    cases de date les écrivent dans le rouge des dépenses du thème."""
    from PySide6.QtCore import Qt
    from comptesbudget.ui import dialogs
    theme.choisir_theme(nom)
    try:
        palette = theme.THEMES[nom]
        cats = ["Alimentation"]
        fenetres = [
            dialogs.TxDialog(None, None, cats, []),
            dialogs.SettingsDialog(None, "2026-01-01", 100.0, "Compte"),
            dialogs.RecurringDialog(None, None, cats, []),
        ]
        cases = [c for f in fenetres
                 for c in f.findChildren(dialogs.QDateEdit)]
        assert len(cases) >= 5
        for case in cases:
            calendrier = case.calendarWidget()
            for jour in (Qt.Saturday, Qt.Sunday):
                couleur = calendrier.weekdayTextFormat(jour).foreground().color()
                assert couleur.name().upper() == palette["debit"]
                assert contraste(couleur.name(), palette["saisie"]) >= 4.5
    finally:
        theme.choisir_theme("clair")


@pytest.mark.parametrize("palette", [CLAIR, SOMBRE], ids=["clair", "sombre"])
def test_texte_de_la_notice_lisible_sur_ses_fonds(palette):
    """Le corps de la Notice s'écrit sur la carte, dans les encadrés
    « astuce » (jaune) et « attention » (rouge), dans l'en-tête des tableaux
    et sur le fond des touches et du code."""
    p = palette
    for fond in ("carte", "info_fond", "erreur_fond", "entete_haut",
                 "ligne_paire"):
        assert contraste(p["texte_libelle"], p[fond]) >= 4.5, fond
    assert contraste(p["bleu_nuit"], p["carte"]) >= 4.5


def test_notice_en_sombre(qapp, sombre):
    from comptesbudget.ui.views import notice
    for style in (notice.style_notice(), notice.style_glossaire()):
        assert SOMBRE["texte_libelle"] in style.upper()
        assert SOMBRE["bleu_nuit"] in style.upper()
        assert CLAIR["bleu_nuit"] not in style.upper()
    vue = notice.NoticeView()
    from PySide6.QtWidgets import QTextBrowser
    for texte in vue.findChildren(QTextBrowser):
        assert SOMBRE["carte"] in texte.styleSheet().upper()


def test_votre_avis_et_mise_a_jour_en_sombre(qapp, sombre):
    from comptesbudget.ui.avis import AvisDialog
    from comptesbudget.ui.mise_a_jour import MiseAJourDialog
    for fenetre in (AvisDialog(), MiseAJourDialog()):
        style = fenetre.confirmation.styleSheet().upper()
        assert SOMBRE["credit"] in style, type(fenetre).__name__


def test_rapport_mensuel_reste_clair_en_sombre(qapp, sombre, tmp_path):
    """Le rapport mensuel reste clair, comme le papier où il s'imprime. Son
    HTML ne fixe pas la couleur du texte : en sombre, l'aperçu prenait le
    blanc cassé du thème sur son fond ivoire (vu en image le 14/10/2026)."""
    from PySide6.QtGui import QPalette
    from comptesbudget.database import Database
    from comptesbudget.ui.report import MonthlyReportDialog
    db = Database(str(tmp_path / "comptes.db"))
    db.set_setting("initial_date", "2026-01-01")
    db.set_setting("initial_balance", "100.0")
    from comptesbudget.app import appliquer_theme, appliquer_theme_clair
    appliquer_theme(qapp)          # comme au démarrage en sombre
    try:
        apercu = MonthlyReportDialog(None, db).browser
        texte = apercu.palette().color(QPalette.Text).name().upper()
    finally:
        appliquer_theme_clair(qapp)
    assert texte == CLAIR["texte"]
    assert contraste(texte, CLAIR["carte"]) >= 4.5


def test_aucun_ecran_oublie():
    """Fin de l'étape 2 (14/10/2026) : tout fichier d'écran prend ses
    couleurs dans le thème. Seul le rapport mensuel garde les siennes : il
    reste clair, comme le papier où il s'imprime."""
    en_dur = []
    for fichier in sorted(UI.rglob("*.py")):
        if fichier.name == "report.py":
            continue
        en_dur += [f"{fichier.relative_to(UI)}:{ligne} {m}"
                   for ligne, texte in _chaines(fichier)
                   for m in HEXA.findall(texte)]
    assert not en_dur, "Couleurs à prendre dans le thème :\n" + "\n".join(en_dur)
