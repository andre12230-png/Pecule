"""Textes et formats (relecture de design du 30/09/2026, points de détail).

Chacun de ces tests a été écrit avant la correction et vu en échec.
"""
import ast
from datetime import date
from pathlib import Path

import pytest
from PySide6.QtCore import Qt

import comptesbudget
from comptesbudget.database import Database

RACINE = Path(comptesbudget.__file__).parent


def _tx(**kw):
    base = {"id": "x", "date": "2026-06-01", "date_valeur": "2026-06-01",
            "libelle": "OP", "libelle_op": "OP", "reference": "", "type": "",
            "categorie": "Non classé", "sous_cat": "", "info": "",
            "montant": -10.0, "pointee": 1}
    base.update(kw)
    return base


@pytest.fixture
def db(tmp_path):
    d = Database(str(tmp_path / "textes.db"))
    d.set_setting("initial_balance", "1000")
    d.set_setting("initial_date", "2020-01-01")
    jour = date.today().replace(day=1).isoformat()
    d.insert_tx(_tx(id="rev", date=jour, date_valeur=jour, categorie="Revenus",
                    libelle="Salaire", montant=2000.0))
    d.insert_tx(_tx(id="dep", date=jour, date_valeur=jour, categorie="Alimentation",
                    libelle="Courses", montant=-178.0))
    d.set_budget("Alimentation", 200.0)
    d.insert_rule({"id": "r1", "pattern": "courses", "amount": None,
                   "categorie": "Alimentation", "sous_cat": "", "no_overwrite": 0,
                   "created_at": "2026-01-31"})
    d.insert_recurring({"id": "rec1", "libelle": "Loyer", "montant": -800.0,
                        "categorie": "Logement - maison", "sous_cat": "",
                        "type": "Prélèvement", "frequency": "monthly",
                        "day_of_month": 5, "start_date": "2026-01-05",
                        "end_date": None, "actif": 1})
    return d


def _couleur_du_montant(tuile) -> str:
    style = tuile._value.styleSheet().upper()
    return style.split("COLOR:")[1].split(";")[0].strip()


def test_montant_nul_sans_couleur(qapp, tmp_path):
    """Un bilan nul s'écrit « 0,00 », sans signe ni couleur (charte) : sur
    une base neuve, les tuiles du Bilan s'affichaient en vert."""
    from comptesbudget.ui.views.bilan import BilanView
    vue = BilanView(Database(str(tmp_path / "vide.db")))
    vue.refresh()
    for cle in ("solde", "net", "pointe", "epargne"):
        assert _couleur_du_montant(vue.kpis[cle]) not in ("#18733A", "#C0392B", "#16A085"), cle


def test_taux_d_epargne_lisible(qapp, db):
    """Le taux d'épargne s'écrivait en #16A085 : 3,09 pour 1 sur l'ivoire."""
    from comptesbudget.ui.views.bilan import BilanView
    vue = BilanView(db)
    vue.period = date.today().strftime("%Y-%m")
    vue.refresh()
    assert _couleur_du_montant(vue.kpis["epargne"]) == "#18733A"


def test_verdict_ne_laisse_pas_croire_a_un_decouvert(qapp, db):
    """« reste positif jusqu'au 14/11 » laissait croire à un découvert le
    15/11 : le 14/11 n'est que la limite du calcul."""
    from comptesbudget.ui.views.bilan import BilanView
    vue = BilanView(db)
    vue.refresh()
    texte = vue.verdict_banner.text()
    assert "reste positif jusqu" not in texte
    assert "aucun découvert prévu d'ici le" in texte


def test_regles_datees_a_la_francaise(qapp, db):
    """« Créée le » s'écrivait 2026-01-31, partout ailleurs 31/01/2026."""
    from comptesbudget.ui.views.rules_view import RulesView
    vue = RulesView(db)
    vue.refresh()
    textes = [vue.model.item(0, c).text() for c in range(vue.model.columnCount())]
    assert "31/01/2026" in textes
    assert "2026-01-31" not in textes


def test_pourcentage_du_budget_espace(qapp, db):
    """« 89% » collé dans le Budget, « 29,8 % » partout ailleurs."""
    from PySide6.QtWidgets import QProgressBar
    from comptesbudget.ui.views.budget import BudgetView
    vue = BudgetView(db)
    vue.period = date.today().strftime("%Y-%m")
    vue.refresh()
    formats = [b.format() for b in vue.findChildren(QProgressBar)]
    assert "89\xa0%" in formats, formats


def test_previsionnel_du_au_et_ordre_chronologique(qapp, db):
    """« Début → fin » devient « Période » écrite « du … au … », et les
    prévisions se lisent de la plus proche à la plus lointaine (elles
    commençaient dans un an)."""
    from comptesbudget.ui.views.previsionnel import PrevisionnelView
    vue = PrevisionnelView(db)
    vue.refresh()
    entetes = [vue.model.headerData(c, Qt.Horizontal) for c in range(vue.model.columnCount())]
    assert not any("→" in e for e in entetes)
    cellules = [vue.model.item(0, c).text() for c in range(vue.model.columnCount())]
    assert any(c.startswith("depuis le 05/01/2026") for c in cellules), cellules
    fm = vue.forecast_model
    dates = [fm.item(r, 0).data(Qt.UserRole + 1) for r in range(fm.rowCount())]
    dates_affichees = [fm.item(r, 0).text() for r in range(fm.rowCount())]
    tri = [fm.item(r, 0).data(fm.sortRole()) for r in range(fm.rowCount())]
    assert tri == sorted(tri), dates_affichees[:3]
    assert dates  # au moins une échéance


def test_titres_des_graphiques_du_au(qapp, db):
    from comptesbudget.ui.views.bilan import BilanView
    vue = BilanView(db)
    vue.refresh()
    for panneau in (vue.bar_panel, vue.solde_panel):
        titre = panneau._header.text()
        assert "→" not in titre, titre
        assert " À " in titre, titre


# Formulaires qui enregistrent : leur bouton le dit.
def _formulaires(db):
    from comptesbudget.constants import CATEGORIES_DEFAUT
    from comptesbudget.ui.dialogs import (
        CategoriesMasqueesDialog, RecurringDialog, RuleDialog, SettingsDialog,
        TxDialog,
    )
    return {
        "Nouvelle opération": TxDialog(None, None, CATEGORIES_DEFAUT, []),
        "Règle": RuleDialog(None, None, CATEGORIES_DEFAUT),
        "Récurrence": RecurringDialog(None, None, CATEGORIES_DEFAUT, []),
        "Paramètres": SettingsDialog(None, "2026-01-01", 0.0, "Compte courant", avance=True),
        "Catégories proposées": CategoriesMasqueesDialog(None, db),
    }


def test_formulaires_sans_bouton_ok(qapp, db):
    """« OK » ne dit pas ce qu'il fait : le bouton qui valide dit
    « Enregistrer » (charte, « Ce qu'on dit à l'utilisateur »)."""
    from PySide6.QtWidgets import QPushButton
    for nom, dlg in _formulaires(db).items():
        textes = [b.text().replace("&", "") for b in dlg.findChildren(QPushButton)]
        assert "OK" not in textes, f"{nom} : {textes}"
        assert "Enregistrer" in textes, f"{nom} : {textes}"


TITRES_VAGUES = {"Saisie", "Récurrent", "Règle", "Confirmer", "Supprimer"}


def test_aucun_titre_de_boite_vague():
    """Un titre de boîte dit de quoi il s'agit : « Saisie », « Récurrent »
    ou « Règle » au-dessus de « Le libellé est obligatoire. » ne le disaient
    pas."""
    fautifs = []
    for fichier in RACINE.rglob("*.py"):
        for noeud in ast.walk(ast.parse(fichier.read_text(encoding="utf-8"))):
            if (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute)
                    and isinstance(noeud.func.value, ast.Name)
                    and noeud.func.value.id == "QMessageBox"
                    and len(noeud.args) >= 2
                    and isinstance(noeud.args[1], ast.Constant)
                    and noeud.args[1].value in TITRES_VAGUES):
                fautifs.append(f"{fichier.relative_to(RACINE)}:{noeud.lineno} "
                               f"« {noeud.args[1].value} »")
    assert not fautifs, ", ".join(fautifs)


def test_pas_de_jargon_json_a_l_ecran(qapp, db):
    """« Exporter (JSON)… » : le nom d'un format de fichier ne dit rien à
    l'utilisateur ; le bouton dit à quoi sert l'export."""
    from PySide6.QtWidgets import QPushButton
    dlg = _formulaires(db)["Paramètres"]
    textes = [b.text() for b in dlg.findChildren(QPushButton)]
    assert not any("JSON" in t for t in textes), textes


def test_menu_et_onglets_sans_icone_en_double(qapp, db):
    """Catégories et Sous-catégories portaient la même icône 🏷️ ; chaque
    onglet a la sienne. Les boutons du menu disent ce qu'ils font."""
    from PySide6.QtWidgets import QPushButton
    from comptesbudget.ui.main_window import MainWindow
    w = MainWindow(db)
    icones = [w.tabs.tabText(i).split(" ")[0] for i in range(w.tabs.count())]
    assert len(icones) == len(set(icones)), icones
    menu = [b.text() for b in w.findChildren(QPushButton)]
    # « Doublons » n'avait pas de verbe, « Harmoniser » pas d'objet.
    for ancien in ("🔍 Doublons", "🔧 Harmoniser"):
        assert ancien not in menu, ancien
