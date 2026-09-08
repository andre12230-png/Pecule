"""Smoke tests de la couche UI.

On construit chaque vue, fenêtre et dialogue avec une base en mémoire peuplée,
puis on déclenche le rafraîchissement. But : attraper les plantages et les
erreurs de câblage (imports, signaux, calculs au refresh) sans simuler
d'interaction — rapide, headless, peu fragile.
"""
import importlib
import os
from calendar import monthrange
from datetime import date, timedelta

import pytest

from comptesbudget.constants import CATEGORIES_DEFAUT
from comptesbudget.database import Database
from comptesbudget.utils import (
    date_debit_differe, fmt_date_fr, fmt_euro, period_label,
)


def _tx(**kw):
    base = {
        "id": "x", "date": "2026-06-01", "date_valeur": "2026-06-01",
        "libelle": "OP", "libelle_op": "OP", "reference": "", "type": "",
        "categorie": "Non classé", "sous_cat": "", "info": "",
        "montant": -10.0, "pointee": 0,
    }
    base.update(kw)
    return base


def _euros(texte: str) -> float:
    """Relit un montant affiché (« -1 234,56 € ») pour pouvoir le comparer.

    Comparer les textes ne suffit pas : un bandeau additionne tout ce qui
    tombe dans sa fenêtre, donc son total dépend du reste du jeu d'essai.
    """
    return float(texte.replace("€", "").replace(" ", "")
                      .replace(" ", "").replace(",", ".").strip())


def _fige_aujourdhui(monkeypatch, jour: date):
    """Fige la date du jour vue par le Bilan.

    Ses bandeaux se calent sur « aujourd'hui » : les 15 prochains jours d'un
    côté, le mois en cours de l'autre. Un test écrit pour « le 5 du mois »
    échouait donc les derniers jours du mois, quand l'échéance du mois
    SUIVANT entre à son tour dans la fenêtre des 15 jours — ce que Pécule a
    raison d'annoncer, mais que le test ne prévoyait pas.
    """
    from comptesbudget.ui.views import bilan

    class _Fige(date):
        @classmethod
        def today(cls):
            return jour

    monkeypatch.setattr(bilan, "date", _Fige)


@pytest.fixture
def db(tmp_path):
    """Base peuplée pour exercer les calculs (soldes, encours CB, alerte
    budget dépassé, graphiques, règles, récurrences)."""
    d = Database(str(tmp_path / "ui.db"))
    d.set_setting("initial_balance", "1000")     # → pas d'invite au 1er lancement
    d.set_setting("initial_date", "2026-01-01")

    today = date.today()
    first = today.replace(day=1).isoformat()
    todays = today.isoformat()
    future = (today + timedelta(days=20)).isoformat()

    d.insert_tx(_tx(id="t-sal", date=first, date_valeur=first, libelle="SALAIRE",
                    libelle_op="SALAIRE", type="Virement", categorie="Revenus",
                    montant=2000.0, pointee=1))
    d.insert_tx(_tx(id="t-cou", date=todays, date_valeur=todays, libelle="HYPERMARCHE",
                    libelle_op="HYPERMARCHE", type="Carte bancaire",
                    categorie="Alimentation", montant=-45.30, pointee=1))
    d.insert_tx(_tx(id="t-big", date=todays, date_valeur=todays, libelle="COURSES",
                    libelle_op="COURSES", type="Carte bancaire",
                    categorie="Alimentation", montant=-380.0, pointee=1))  # budget dépassé
    d.insert_tx(_tx(id="t-cb", date=todays, date_valeur=future, libelle="OMNISHOP",
                    libelle_op="OMNISHOP", type="Carte bancaire",
                    categorie="Loisirs", montant=-60.0, pointee=0))        # encours CB
    d.set_budget("Alimentation", 400.0)
    d.insert_rule({"id": "r1", "pattern": "omnishop", "amount": None,
                   "categorie": "Shopping", "sous_cat": "", "no_overwrite": 0,
                   "created_at": "2026-01-01"})
    d.insert_recurring({"id": "rec1", "libelle": "Loyer", "montant": -800.0,
                        "categorie": "Logement - maison", "sous_cat": "",
                        "type": "Prelevement", "frequency": "monthly",
                        "day_of_month": 5, "start_date": "2026-01-05",
                        "end_date": None, "actif": 1})
    return d


def test_main_window_construit(qapp, db):
    from comptesbudget.ui.main_window import MainWindow
    w = MainWindow(db)               # construit et appelle refresh_all()
    assert w.tabs.count() == 7   # la Notice n'est plus un onglet (menu de gauche)
    w.refresh_all()                  # second passage : ne doit pas lever


def test_reste_carte_suit_une_depense_saisie(qapp, tmp_path):
    """Bout en bout : une dépense enregistrée depuis l'onglet Opérations
    remonte jusqu'au bandeau, sans rien rafraîchir à la main. C'est le signal
    `tx_changed` qui porte l'information."""
    from comptesbudget.ui.main_window import MainWindow

    d = Database(str(tmp_path / "interactif.db"))
    d.set_setting("initial_balance", "1000")
    d.set_setting("initial_date", "2020-01-01")
    today = date.today().isoformat()
    d.insert_tx(_tx(id="cb1", date=today, date_valeur=date_debit_differe(today),
                    libelle="HYPERMARCHE", type="Carte bancaire",
                    montant=-200.0, pointee=1))
    w = MainWindow(d)
    assert "il reste " + fmt_euro(800.0) in w.bilan_view.cb_detail.text()

    d.insert_tx(_tx(id="cb2", date=today, date_valeur=date_debit_differe(today),
                    libelle="OMNISHOP", type="Carte bancaire",
                    montant=-62.0, pointee=0))
    w.ops_view.tx_changed.emit()          # ce que fait toute saisie
    assert "il reste " + fmt_euro(738.0) in w.bilan_view.cb_detail.text()


def test_bandeau_carte_suit_la_periode_choisie(qapp, tmp_path):
    """Bout en bout : changer la période dans la barre du haut emmène le
    bandeau sur le mois consulté."""
    from comptesbudget.ui.main_window import MainWindow

    d = Database(str(tmp_path / "periode.db"))
    d.set_setting("initial_balance", "1000")
    d.set_setting("initial_date", "2020-01-01")
    today = date.today()
    mois_dernier = today.replace(day=1) - timedelta(days=1)
    d.insert_tx(_tx(id="cb-avant", date=mois_dernier.isoformat(),
                    date_valeur=date_debit_differe(mois_dernier.isoformat()),
                    libelle="HYPERMARCHE", type="Carte bancaire",
                    montant=-600.0, pointee=1))
    d.insert_tx(_tx(id="cb-ce-mois", date=today.isoformat(),
                    date_valeur=date_debit_differe(today.isoformat()),
                    libelle="OMNISHOP", type="Carte bancaire",
                    montant=-100.0, pointee=0))
    # Un prélèvement du mois dernier, sans différé : sans lui, ce mois
    # n'existerait pas dans le menu en « date de valeur », les achats carte
    # y étant datés du 4 du mois suivant.
    d.insert_tx(_tx(id="prel-avant", date=mois_dernier.isoformat(),
                    date_valeur=mois_dernier.isoformat(),
                    libelle="SAUR", type="Prélèvement",
                    montant=-30.0, pointee=1))
    w = MainWindow(d)
    # 1 000 - 30 de prélèvement - 600 de lot carte prélevé le 4 = 370 au
    # compte, moins 100 déjà passés à la carte ce mois-ci.
    assert "il reste " + fmt_euro(270.0) in w.bilan_view.cb_detail.text()

    w.period_bar._appliquer(mois_dernier.strftime("%Y-%m"))
    # 970 - 600
    assert "il restait " + fmt_euro(370.0) in w.bilan_view.cb_detail.text()
    assert period_label(mois_dernier.strftime("%Y-%m")).upper() in \
        w.bilan_view.cb_title.text()


# (module, classe, méthode de rafraîchissement)
VIEW_SPECS = [
    ("bilan", "BilanView", "refresh"),
    ("budget", "BudgetView", "refresh"),
    ("categories", "CategoriesView", "refresh"),
    ("subcategories", "SubcategoriesView", "refresh"),
    ("operations", "OperationsView", "reload_from_db"),
    ("previsionnel", "PrevisionnelView", "refresh"),
    ("rules_view", "RulesView", "refresh"),
]


@pytest.mark.parametrize("module, cls, method", VIEW_SPECS)
def test_view_se_rafraichit(qapp, db, module, cls, method):
    mod = importlib.import_module(f"comptesbudget.ui.views.{module}")
    view = getattr(mod, cls)(db)
    getattr(view, method)()          # rafraîchissement initial — ne doit pas lever


def _barre_periodes(qapp):
    """Une PeriodBar remplie avec trois annees : l'annee en cours (mars,
    avril et le mois courant) et les deux precedentes."""
    from comptesbudget.ui.widgets import PeriodBar
    an = date.today().year
    mois_courant = date.today().strftime("%Y-%m")
    txs = [{"date": f"{an}-03-01", "date_valeur": f"{an}-03-01"},
           {"date": f"{an}-04-01", "date_valeur": f"{an}-04-01"},
           {"date": f"{mois_courant}-01", "date_valeur": f"{mois_courant}-01"},
           {"date": f"{an - 1}-05-01", "date_valeur": f"{an - 1}-05-01"},
           {"date": f"{an - 2}-07-01", "date_valeur": f"{an - 2}-07-01"}]
    barre = PeriodBar()
    barre.update_periods(txs)
    return barre, an


def _donnees(combo):
    return [combo.itemData(i) for i in range(combo.count())]


def test_periodes_deux_menus_annee_puis_mois(qapp):
    """Le selecteur est coupe en deux : le menu de gauche ne porte que les
    annees, celui de droite les mois de l'annee choisie. Une seule liste
    melangeait les deux et s'allongeait d'une ligne chaque mois."""
    barre, an = _barre_periodes(qapp)
    annees = _donnees(barre.annee_combo)
    assert annees == ["all", str(an), str(an - 1), str(an - 2)]
    # Ouverture sur le mois en cours : le menu des mois montre ceux de
    # l'annee en cours, et aucun mois d'une autre annee.
    mois = _donnees(barre.mois_combo)
    assert f"{an}-03" in mois and f"{an}-04" in mois
    assert f"{an - 1}-05" not in mois


def test_periodes_ouvre_sur_le_mois_en_cours(qapp):
    """L'application s'ouvre sur le mois en cours, jamais sur une periode
    memorisee : de vieux chiffres passeraient pour ceux du mois courant."""
    barre, _ = _barre_periodes(qapp)
    assert barre.current_period() == date.today().strftime("%Y-%m")


def test_periodes_mois_en_cours_vide_replie_sur_tout(qapp):
    """Mois en cours sans aucune operation : on montre tout l'historique
    plutot qu'un ecran vide qui ne dit pas pourquoi."""
    from comptesbudget.ui.widgets import PeriodBar
    barre = PeriodBar()
    barre.update_periods([{"date": "2020-05-01", "date_valeur": "2020-05-01"}])
    assert barre.current_period() == "all"
    # Le menu des mois n'a pas de sens sur « toutes periodes » : il est grise.
    assert not barre.mois_combo.isEnabled()


def test_periodes_fleche_recule_dun_mois(qapp):
    """La fleche gauche recule d'un cran a echelle constante, et traverse
    les annees : depuis janvier, elle mene a decembre precedent."""
    from comptesbudget.ui.widgets import PeriodBar
    barre = PeriodBar()
    barre.update_periods([{"date": "2025-12-10", "date_valeur": "2025-12-10"},
                          {"date": "2026-01-10", "date_valeur": "2026-01-10"}])
    barre._appliquer("2026-01")
    barre._decaler(-1)
    assert barre.current_period() == "2025-12"
    # Plus rien avant : la fleche se grise au lieu de rester sans effet.
    barre._decaler(-1)
    assert barre.current_period() == "2025-12"
    assert not barre.prev_btn.isEnabled()


def test_periodes_changer_dannee_garde_le_mois(qapp):
    """Changer d'annee garde le mois affiche s'il existe la-bas — c'est ce
    qu'on veut pour comparer un mois d'une annee sur l'autre."""
    from comptesbudget.ui.widgets import PeriodBar
    barre = PeriodBar()
    barre.update_periods([{"date": "2025-05-10", "date_valeur": "2025-05-10"},
                          {"date": "2026-05-10", "date_valeur": "2026-05-10"},
                          {"date": "2026-08-10", "date_valeur": "2026-08-10"}])
    barre._appliquer("2026-05")
    barre.annee_combo.setCurrentIndex(barre.annee_combo.findData("2025"))
    assert barre.current_period() == "2025-05"
    # Mois absent de l'autre annee : on montre l'annee entiere.
    barre._appliquer("2026-08")
    barre.annee_combo.setCurrentIndex(barre.annee_combo.findData("2025"))
    assert barre.current_period() == "2025"


def test_notice_view(qapp):
    from comptesbudget.ui.views.notice import NoticeView
    NoticeView()                     # vue statique : construction seule


def test_dialogs_creation_et_values(qapp, db):
    from comptesbudget.ui.dialogs import (
        RecurringDialog, RuleDialog, SettingsDialog, TxDialog,
    )
    txs = [dict(r) for r in db.list_tx()]
    cats = CATEGORIES_DEFAUT

    tx_dlg = TxDialog(None, None, categories=cats, all_transactions=txs)
    assert "montant" in tx_dlg.values()
    # Mode édition : exerce la branche de pré-remplissage
    TxDialog(None, txs[0], categories=cats, all_transactions=txs)

    # Les Paramètres se réduisent à la date et au solde de départ : le plafond
    # d'encours carte a été retiré le 07/09/2026, le Bilan calculant désormais
    # ce qui reste d'après les mouvements réels du mois.
    assert SettingsDialog(None, "2026-01-01", 1000.0).values() == ("2026-01-01", 1000.0)
    assert SettingsDialog(None, "2026-01-01", 1000.0, "Compte courant").values() \
        == ("2026-01-01", 1000.0)
    assert "pattern" in RuleDialog(None, None, categories=cats).values()
    assert "frequency" in RecurringDialog(None, None, categories=cats, all_tx=txs).values()


def test_bilan_solde_ignore_encours_carte(qapp, db):
    """Le solde bancaire réel ne doit PAS compter un achat carte déjà pointé
    mais pas encore prélevé (débit différé) — y compris quand l'affichage est
    en « date d'opération »."""
    from comptesbudget.ui.views.bilan import BilanView

    today = date.today()
    future = (today + timedelta(days=20)).isoformat()
    db.insert_tx(_tx(id="t-cb-pointe", date=today.isoformat(), date_valeur=future,
                     libelle="LIVRESTORE", libelle_op="LIVRESTORE", type="Carte bancaire",
                     categorie="Loisirs", montant=-100.0, pointee=1))

    view = BilanView(db)
    view.date_mode = "valeur"
    view.refresh()
    solde_valeur = view.kpis["solde"]._value.text()
    view.date_mode = "operation"
    view.refresh()
    assert view.kpis["solde"]._value.text() == solde_valeur


def test_txdialog_date_valeur_carte_differee(qapp, db):
    """Formulaire d'opération : le type « Carte bancaire » place la date de
    valeur au 4 du mois suivant, sauf si l'utilisateur la saisit lui-même."""
    from PySide6.QtCore import QDate

    from comptesbudget.ui.dialogs import TxDialog

    txs = [dict(r) for r in db.list_tx()]
    dlg = TxDialog(None, None, categories=CATEGORIES_DEFAUT, all_transactions=txs)

    dlg.date_edit.setDate(QDate(2026, 7, 15))
    dlg.type_combo.setCurrentText("Carte bancaire")
    assert dlg.values()["date_valeur"] == "2026-08-04"

    # Type sans débit différé : la date de valeur revient sur la date d'opération
    dlg.type_combo.setCurrentText("Virement")
    assert dlg.values()["date_valeur"] == "2026-07-15"

    # Date de valeur saisie à la main → la date d'opération ne la bouge plus
    dlg.date_val.setDate(QDate(2026, 7, 20))
    dlg.date_edit.setDate(QDate(2026, 7, 16))
    assert dlg.values()["date_valeur"] == "2026-07-20"

    # ...mais changer le TYPE relance le calcul (correction du 05/08/2026) :
    # l'ancienne date découlait d'un type qui n'est plus celui de l'opération.
    dlg.type_combo.setCurrentText("Carte bancaire")
    assert dlg.values()["date_valeur"] == "2026-08-04"

    # Modification d'une opération existante : sa date de valeur est conservée
    existante = next(t for t in txs if t["type"] == "Carte bancaire"
                     and t["date_valeur"] != t["date"])
    edit = TxDialog(None, existante, categories=CATEGORIES_DEFAUT, all_transactions=txs)
    assert edit.values()["date_valeur"] == existante["date_valeur"]


def test_rapport_et_recherche(qapp, db):
    from comptesbudget.ui.report import (
        MonthlyReportDialog, build_monthly_report_html,
    )
    from comptesbudget.ui.search import GlobalSearchDialog

    month = date.today().strftime("%Y-%m")
    html = build_monthly_report_html(db, month)
    assert "<" in html and len(html) > 50

    MonthlyReportDialog(None, db)    # construction (aperçu QTextBrowser)
    GlobalSearchDialog(None, db)     # construit + indexe + recherche initiale


def test_bilan_et_categories_suivent_le_mode_date(qapp, tmp_path):
    """Bilan et Catégories comptent les mêmes opérations pour une période
    donnée : un achat carte du 28/07 débité le 04/08 appartient à août en mode
    « date de valeur » et à juillet en mode « date d'opération ». Les deux vues
    doivent être d'accord, sinon les chiffres se contredisent d'un onglet à
    l'autre.

    Le Budget, lui, ne suit PAS le sélecteur : il compte toujours à la date
    d'achat (voir test_budget_ignore_le_debit_differe)."""
    from comptesbudget.ui.views.bilan import BilanView
    from comptesbudget.ui.views.budget import BudgetView
    from comptesbudget.ui.views.categories import CategoriesView

    d = Database(str(tmp_path / "mode.db"))
    d.set_setting("initial_balance", "0")
    d.set_setting("initial_date", "2026-01-01")
    d.insert_tx(_tx(id="cb", date="2026-07-28", date_valeur="2026-08-04",
                    libelle="ACHAT CB", type="Carte bancaire",
                    categorie="Shopping", montant=-100.0))

    def depenses(vue_cls, periode, mode):
        v = vue_cls(d)
        v.period = periode
        v.date_mode = mode
        v.refresh()
        return v

    # Juillet en date de valeur : l'opération n'y est pour aucune des deux vues.
    # Le montant des dépenses se lit dans le mouvement du mois : la tuile
    # « Dépenses » a fusionné avec lui le 07/09/2026.
    assert depenses(BilanView, "2026-07", "valeur").kpis["net"]._value.text()         == fmt_euro(0)
    assert depenses(CategoriesView, "2026-07", "valeur").cats_model.rowCount() == 0

    # Août en date de valeur : les deux vues la voient.
    assert depenses(BilanView, "2026-08", "valeur").kpis["net"]._value.text()         == fmt_euro(-100.0)
    assert depenses(CategoriesView, "2026-08", "valeur").cats_model.rowCount() == 1

    # Mode « date d'opération » : tout bascule sur juillet, pour les deux.
    assert depenses(BilanView, "2026-07", "operation").kpis["net"]._value.text()         == fmt_euro(-100.0)
    assert depenses(CategoriesView, "2026-07", "operation").cats_model.rowCount() == 1

    # Le Budget reste sur juillet — le mois de l'achat — dans les deux modes.
    for mode in ("valeur", "operation"):
        assert depenses(BudgetView, "2026-07", mode).model.rowCount() == 1
        assert depenses(BudgetView, "2026-08", mode).model.rowCount() == 0


def test_budget_ignore_le_debit_differe(qapp, tmp_path, monkeypatch):
    """Le Budget compte un achat sur sa DATE D'ACHAT, jamais sur sa date de
    valeur — même quand la barre du haut est sur « Date de valeur ».

    Sinon le lot de la carte à débit différé, débité le 4, faisait déborder
    les budgets du mois suivant : le 07/09/2026, le bandeau du Bilan annonçait
    « Restaurants & Sorties 147 % » pour un mois où André n'avait rien dépensé
    au restaurant — c'étaient ses additions d'août.
    """
    from comptesbudget.ui.views.bilan import BilanView
    from comptesbudget.ui.views.budget import BudgetView

    _fige_aujourdhui(monkeypatch, date(2026, 9, 7))

    d = Database(str(tmp_path / "differe.db"))
    d.set_setting("initial_balance", "1000")
    d.set_setting("initial_date", "2026-01-01")
    # Achat carte du 20 août, débité le 4 septembre avec tout le lot.
    d.insert_tx(_tx(id="cb", date="2026-08-20", date_valeur="2026-09-04",
                    libelle="RESTAURANT", type="Carte bancaire",
                    categorie="Restaurants & Sorties", montant=-100.0,
                    pointee=1))
    # Un vrai prélèvement de septembre, lui, doit bien compter.
    d.insert_tx(_tx(id="pr", date="2026-09-05", date_valeur="2026-09-05",
                    libelle="SAUR", type="Prélèvement",
                    categorie="Logement - maison", montant=-90.0, pointee=1))
    d.set_budget("Restaurants & Sorties", 80.0)
    d.set_budget("Logement - maison", 80.0)

    v = BilanView(d)
    v.date_mode = "valeur"
    v.refresh()
    texte = v.budget_alert.text()
    assert v.budget_alert.isVisibleTo(v)            # le vrai dépassement reste
    assert "Logement - maison" in texte
    # (le bandeau échappe le HTML : « & » y devient « &amp; », d'où « Restaurants » seul)
    assert "Restaurants" not in texte               # l'addition d'août n'est pas de septembre

    # Même règle dans l'onglet Budget, vers lequel le bandeau renvoie :
    # l'achat compte en août, pas en septembre.
    def depense(periode: str) -> float:
        b = BudgetView(d)
        b.period = periode
        b.date_mode = "valeur"
        b.refresh()
        lignes = {b.model.item(i, 0).text(): b.model.item(i, 2).text()
                  for i in range(b.model.rowCount())}
        return _euros(lignes.get("Restaurants & Sorties", "0"))

    assert depense("2026-09") == 0.0
    assert depense("2026-08") == 100.0


def test_alerte_budget_suit_la_periode(qapp, tmp_path, monkeypatch):
    """Le bandeau d'alerte suit la période choisie en haut, comme le bandeau
    Encours carte : sélectionner « Août 2026 » montre les budgets dépassés en
    août. Une année ou « Toutes périodes » ne désignent aucun mois — un budget
    mensuel ne se juge qu'au mois — et le bandeau revient au mois en cours."""
    from comptesbudget.ui.views.bilan import BilanView

    _fige_aujourdhui(monkeypatch, date(2026, 9, 7))

    d = Database(str(tmp_path / "periode.db"))
    d.set_setting("initial_balance", "1000")
    d.set_setting("initial_date", "2026-01-01")
    d.insert_tx(_tx(id="a", date="2026-08-12", date_valeur="2026-08-12",
                    libelle="GARAGE", type="Prélèvement",
                    categorie="Transports", montant=-150.0, pointee=1))
    d.set_budget("Transports", 100.0)

    def bandeau(periode: str) -> str:
        v = BilanView(d)
        v.period = periode
        v.refresh()
        return v.budget_alert.text() if v.budget_alert.isVisibleTo(v) else ""

    # Septembre (mois en cours) : rien de dépassé, le bandeau s'efface.
    assert bandeau("2026-09") == ""
    # Août : le dépassement est là, et le bandeau dit de quel mois il parle.
    aout = bandeau("2026-08")
    assert "Transports" in aout and "150 %" in aout
    assert "août 2026" in aout and "ce mois-ci" not in aout
    # Une année ou toutes périodes ramènent au mois en cours.
    assert bandeau("2026") == ""
    assert bandeau("all") == ""


def _bilan_trois_mois(tmp_path, monkeypatch):
    """Bilan figé au 07/09/2026 sur un jeu simple : août est clos, septembre
    court, octobre n'a qu'une échéance à venir.

    Août : 1 000 € au départ, −200 € le 5, +500 € le 20 → fini à 1 300 €,
    au plus bas 800 € le 5.
    """
    from comptesbudget.ui.views.bilan import BilanView

    _fige_aujourdhui(monkeypatch, date(2026, 9, 7))
    d = Database(str(tmp_path / "mois.db"))
    d.set_setting("initial_balance", "1000")
    d.set_setting("initial_date", "2026-01-01")
    d.insert_tx(_tx(id="a1", date="2026-08-05", date_valeur="2026-08-05",
                    libelle="SAUR", type="Prélèvement",
                    categorie="Logement - maison", montant=-200.0, pointee=1))
    d.insert_tx(_tx(id="a2", date="2026-08-20", date_valeur="2026-08-20",
                    libelle="PENSION", type="Virement", categorie="Revenus",
                    montant=500.0, pointee=1))
    d.insert_tx(_tx(id="s1", date="2026-09-03", date_valeur="2026-09-03",
                    libelle="EDF", type="Prélèvement",
                    categorie="Logement - maison", montant=-50.0, pointee=1))
    d.insert_tx(_tx(id="o1", date="2026-10-15", date_valeur="2026-10-15",
                    libelle="IMPOTS", type="Prélèvement",
                    categorie="Impôts et taxes", montant=-60.0, pointee=0))
    return BilanView, d


def test_verdict_suit_la_periode(qapp, tmp_path, monkeypatch):
    """Le verdict parle du mois choisi : au passé pour un mois clos (« a fini
    le mois »), au présent pour le mois en cours."""
    BilanView, d = _bilan_trois_mois(tmp_path, monkeypatch)

    def verdict(periode: str) -> str:
        v = BilanView(d); v.period = periode; v.refresh()
        return v.verdict_banner.text()

    aout = verdict("2026-08")
    assert "Août 2026" in aout and "a fini le mois" in aout
    assert fmt_euro(1300.0) in aout          # solde constaté au 31/08
    assert fmt_euro(800.0) in aout           # le plus bas du mois
    assert "05/08/2026" in aout

    # Mois en cours : la phrase reste au présent, tournée vers ce qui vient.
    septembre = verdict("2026-09")
    assert "Septembre 2026" in septembre and "finit le mois" in septembre

    # Une année ne désigne aucun mois : retour au mois en cours.
    assert verdict("2026") == septembre


def test_bandeau_du_mois_suit_la_periode(qapp, tmp_path, monkeypatch):
    """Le bandeau vert suit lui aussi la période : « ce qui est passé » pour
    un mois clos, « reste à passer » pour le mois en cours."""
    BilanView, d = _bilan_trois_mois(tmp_path, monkeypatch)

    def bandeau(periode: str):
        v = BilanView(d); v.period = periode; v.refresh()
        return v

    v = bandeau("2026-08")
    assert "AOÛT 2026" in v.mois_title.text()
    assert "est passé" in v.mois_title.text()
    assert _euros(v.mois_sorties.text()) == -200.0
    assert _euros(v.mois_entrees.text()) == 500.0
    assert _euros(v.mois_solde.text()) == 1300.0
    assert "31/08/2026" in v.mois_solde_lbl.text()

    # Mois en cours : le bandeau garde son titre et son sens d'origine.
    v = bandeau("2026-09")
    assert "CE MOIS-CI" in v.mois_title.text()
    assert "reste à passer" in v.mois_title.text()

    # Mois à venir : ce qui est prévu d'ici la fin de ce mois-là.
    v = bandeau("2026-10")
    assert "OCTOBRE 2026" in v.mois_title.text()
    assert _euros(v.mois_sorties.text()) == -60.0


def test_titre_du_mouvement_suit_la_periode(qapp, tmp_path, monkeypatch):
    """La tuile « Mouvement » dit de quoi elle parle : du mois, de l'année ou
    de tout l'historique. Elle s'appelait « Mouvement du mois » même sur une
    année entière, ce que son propre sous-titre démentait."""
    BilanView, d = _bilan_trois_mois(tmp_path, monkeypatch)

    def titre(periode: str) -> str:
        v = BilanView(d); v.period = periode; v.refresh()
        return v.kpis["net"]._label.text()

    assert titre("2026-08") == "Mouvement du mois"
    assert titre("2026") == "Mouvement de l'année"
    assert titre("all") == "Mouvement — toutes périodes"


def test_mouvement_pointe_se_lit_en_face_du_mouvement(qapp, tmp_path, monkeypatch):
    """La tuile « Mouvement pointé » additionne les opérations pointées de la
    période — et rien d'autre. Sur un mois entièrement pointé elle affiche le
    même chiffre que « Mouvement du mois » ; l'écart, sinon, est ce qui n'est
    pas encore passé en banque."""
    BilanView, d = _bilan_trois_mois(tmp_path, monkeypatch)
    # Une échéance de septembre encore en attente : elle ne doit pas y entrer.
    d.insert_tx(_tx(id="s2", date="2026-09-20", date_valeur="2026-09-20",
                    libelle="ASSURANCE", type="Prélèvement",
                    categorie="Banque et assurances", montant=-30.0, pointee=0))

    v = BilanView(d); v.period = "2026-08"; v.refresh()
    assert v.kpis["pointe"]._label.text() == "✔ Mouvement pointé"
    # Août est entièrement pointé : les deux tuiles disent la même chose.
    assert _euros(v.kpis["pointe"]._value.text()) == 300.0     # -200 + 500
    assert v.kpis["pointe"]._value.text() == v.kpis["net"]._value.text()
    assert "Août 2026" in v.kpis["pointe"]._sub.text()

    # Septembre : l'échéance en attente creuse l'écart entre les deux.
    v = BilanView(d); v.period = "2026-09"; v.refresh()
    assert _euros(v.kpis["pointe"]._value.text()) == -50.0     # la seule pointée
    assert _euros(v.kpis["net"]._value.text()) == -80.0        # avec l'échéance


def test_categories_dit_a_quelle_date_elle_compte(qapp, tmp_path):
    """L'onglet Catégories suit le sélecteur « Date » et peut donc afficher
    d'autres totaux que le Budget, qui compte à la date d'achat. Il doit le
    dire : 248,93 € d'un côté et 0 € de l'autre, sans explication, ne peut que
    dérouter.

    Sur un compte SANS débit différé, les deux dates se confondent : la
    comparaison avec le Budget n'a pas lieu d'être et n'est pas affichée."""
    from comptesbudget.ui.views.categories import CategoriesView

    d = Database(str(tmp_path / "cats.db"))
    d.set_setting("initial_balance", "0")
    d.set_setting("initial_date", "2026-01-01")
    d.insert_tx(_tx(id="cb", date="2026-08-28", date_valeur="2026-09-04",
                    libelle="ACHAT CB", type="Carte bancaire",
                    categorie="Shopping", montant=-100.0, pointee=1))

    v = CategoriesView(d); v.period = "2026-09"; v.date_mode = "valeur"; v.refresh()
    txt = v.info_date.text()
    assert "date de valeur" in txt and "diffèrent" in txt
    assert v.info_date.isVisibleTo(v)

    # En date d'opération, les deux onglets comptent pareil : plus rien à dire
    # sinon quelle date est utilisée.
    v.date_mode = "operation"; v.refresh()
    assert "date d'opération" in v.info_date.text()
    assert "comme l'onglet Budget" in v.info_date.text()
    assert "diffèrent" not in v.info_date.text()

    # Compte à débit immédiat : pas de décalage possible, pas d'avertissement.
    d2 = Database(str(tmp_path / "cats2.db"))
    d2.set_setting("initial_balance", "0")
    d2.insert_tx(_tx(id="cb2", date="2026-09-03", date_valeur="2026-09-03",
                     libelle="ACHAT CB", type="Carte bancaire",
                     categorie="Shopping", montant=-100.0, pointee=1))
    v2 = CategoriesView(d2); v2.period = "2026-09"; v2.date_mode = "valeur"
    v2.refresh()
    assert "date de valeur" in v2.info_date.text()
    assert "diffèrent" not in v2.info_date.text()


def test_encours_carte_reprend_les_deux_chiffres_de_la_banque(qapp, tmp_path):
    """La banque affiche « Débit différé au JJ/MM » (achats qu'elle a intégrés
    au prochain prélèvement = pointés) et un encours incluant les achats
    encore « en cours » (non pointés). Le bandeau doit donner ces deux
    chiffres et leur somme."""
    from comptesbudget.ui.views.bilan import BilanView

    d = Database(str(tmp_path / "cb.db"))
    d.set_setting("initial_balance", "0")
    d.set_setting("initial_date", "2026-01-01")
    today = date.today()
    prochain = (today.replace(day=1) + timedelta(days=32)).replace(day=4).isoformat()

    # Deux achats au prochain prélèvement : un intégré par la banque, un en cours
    d.insert_tx(_tx(id="cb-ok", date=today.isoformat(), date_valeur=prochain,
                    libelle="HYPERMARCHE", type="Carte bancaire",
                    montant=-100.0, pointee=1))
    d.insert_tx(_tx(id="cb-cours", date=today.isoformat(), date_valeur=prochain,
                    libelle="OMNISHOP", type="Carte bancaire",
                    montant=-40.00, pointee=0))
    # Le prélèvement du relevé lui-même ne doit jamais être compté deux fois
    d.insert_tx(_tx(id="dd", date=today.isoformat(), date_valeur=prochain,
                    libelle="DEBIT DIFFERE N 1234", type="Carte bancaire",
                    categorie="Transaction exclue", montant=-140.00, pointee=1))

    v = BilanView(d)
    v.refresh()
    assert v.cb_courant.text() == fmt_euro(-100.0)      # confirmé par la banque
    assert v.cb_precedent.text() == fmt_euro(-40.00)    # encore en cours
    assert v.cb_total.text() == fmt_euro(-140.00)       # encours total
    assert v.cb_banner.isVisibleTo(v)


def _bilan_carte(tmp_path, achats, initial: float = 1000.0,
                 autres=(), nom: str = "carte.db"):
    """Bilan avec un solde de départ et des achats par carte.

    `achats` : liste de (date ISO, montant). Chaque achat reçoit sa date de
    valeur au 4 du mois suivant, comme la vraie carte à débit différé.
    `autres` : opérations hors carte, en (date ISO, montant), passées telles
    quelles — ce sont elles qui font entrer ou sortir l'argent du mois.
    """
    from comptesbudget.ui.views.bilan import BilanView

    d = Database(str(tmp_path / nom))
    d.set_setting("initial_balance", str(initial))
    d.set_setting("initial_date", "2020-01-01")
    for i, (jour, montant) in enumerate(achats):
        d.insert_tx(_tx(id=f"cb{i}", date=jour,
                        date_valeur=date_debit_differe(jour),
                        libelle="HYPERMARCHE", type="Carte bancaire",
                        montant=montant, pointee=1))
    for i, (jour, montant) in enumerate(autres):
        d.insert_tx(_tx(id=f"op{i}", date=jour, date_valeur=jour,
                        libelle="PENSION" if montant > 0 else "SAUR",
                        type="Virement" if montant > 0 else "Prélèvement",
                        categorie="Revenus" if montant > 0 else "Logement - maison",
                        montant=montant, pointee=1))
    v = BilanView(d)
    v.refresh()
    return v


def test_encours_carte_reste_ce_que_le_compte_laisse(qapp, tmp_path):
    """Ce que le mois laisse pour la carte = le solde que le compte aura en
    fin de mois, tout payé, moins ce qui est déjà engagé sur la carte. Le
    chiffre n'a plus de bloc à lui depuis le 08/09/2026 : il se lit dans la
    phrase du détail."""
    v = _bilan_carte(tmp_path, [(date.today().isoformat(), -200.0)])
    # 1 000 € au compte, aucune autre échéance, 200 € déjà passés à la carte.
    assert "il reste " + fmt_euro(800.0) in v.cb_detail.text()
    # Et plus aucun bloc « Reste pour la carte » dans le bandeau.
    assert not hasattr(v, "cb_dispo")


def test_encours_carte_reste_ne_descend_pas_sous_zero(qapp, tmp_path):
    """Quand les achats dépassent ce que le compte laisse, le détail annonce
    ce qui MANQUE. C'est la seule lecture honnête : un mois qui finit dans le
    rouge ne laisse rien pour aucune dépense."""
    v = _bilan_carte(tmp_path, [(date.today().isoformat(), -1200.0)])
    assert "il MANQUE " + fmt_euro(200.0) in v.cb_detail.text()
    assert "il reste " not in v.cb_detail.text()


def test_encours_carte_reste_tient_compte_des_echeances_a_venir(qapp, tmp_path):
    """Une charge qui doit encore passer d'ici la fin du mois réduit d'autant
    ce qui reste pour la carte : c'est là que l'ancien plafond mentait."""
    today = date.today()
    fin_mois = today.replace(
        day=monthrange(today.year, today.month)[1]).isoformat()
    v = _bilan_carte(tmp_path, [(today.isoformat(), -200.0)],
                     autres=[(fin_mois, -500.0)], nom="echeance.db")
    # 1 000 - 500 d'échéance à venir = 500 en fin de mois, moins 200 de carte.
    assert "il reste " + fmt_euro(300.0) in v.cb_detail.text()


def test_encours_carte_reste_suit_une_nouvelle_depense(qapp, tmp_path):
    """Une dépense enregistrée, et le chiffre baisse d'autant au
    rafraîchissement suivant : c'est ce qui le rend utilisable."""
    v = _bilan_carte(tmp_path, [(date.today().isoformat(), -200.0)])
    assert "il reste " + fmt_euro(800.0) in v.cb_detail.text()
    jour = date.today().isoformat()
    v.db.insert_tx(_tx(id="cb2", date=jour, date_valeur=date_debit_differe(jour),
                       libelle="OMNISHOP", type="Carte bancaire",
                       montant=-62.0, pointee=0))
    v.refresh()
    assert "il reste " + fmt_euro(738.0) in v.cb_detail.text()


def _bilan_deux_mois(tmp_path):
    """Bilan avec un achat carte le mois dernier et un ce mois-ci, sur un
    compte parti de 1 000 €."""
    today = date.today()
    mois_dernier = today.replace(day=1) - timedelta(days=1)
    v = _bilan_carte(tmp_path,
                     [(mois_dernier.isoformat(), -600.0),
                      (today.isoformat(), -100.0)],
                     nom="consult.db")
    return v, today, mois_dernier


def test_encours_carte_suit_le_mois_consulte(qapp, tmp_path):
    """Choisir un mois passé fait parler le bandeau de CE mois-là : ses
    achats, ce qu'il restait, sa date de prélèvement."""
    v, today, mois_dernier = _bilan_deux_mois(tmp_path)
    # Le lot du mois dernier (600 €) a été prélevé le 4 : le compte est à
    # 400 €, moins les 100 € déjà passés à la carte ce mois-ci.
    assert "il reste " + fmt_euro(300.0) in v.cb_detail.text()
    assert v.cb_bloc1.isVisibleTo(v)

    v.period = mois_dernier.strftime("%Y-%m")
    v.refresh()
    assert v.cb_total.text() == fmt_euro(-600.0)       # les achats du mois passé
    # Fin du mois dernier, le compte était encore à 1 000 € : les 600 € de
    # carte n'en sortent que le 4 du mois suivant.
    assert "il restait " + fmt_euro(400.0) in v.cb_detail.text()
    assert period_label(v.period).upper() in v.cb_title.text()
    assert fmt_date_fr(date_debit_differe(mois_dernier.isoformat())) in v.cb_title.text()
    assert "Consultation" in v.cb_detail.text()
    # Les deux chiffres du prochain prélèvement n'ont aucun sens sur un mois
    # passé, où plus rien n'est en attente : ils s'effacent.
    assert not v.cb_bloc1.isVisibleTo(v)
    assert not v.cb_bloc2.isVisibleTo(v)


def test_encours_carte_annee_reste_sur_le_mois_en_cours(qapp, tmp_path):
    """Une année ne désigne aucun mois : le bandeau garde le mois en cours
    plutôt que de cumuler douze mois."""
    v, today, _ = _bilan_deux_mois(tmp_path)
    v.period = today.strftime("%Y")
    v.refresh()
    assert "il reste " + fmt_euro(300.0) in v.cb_detail.text()
    assert v.cb_bloc1.isVisibleTo(v)


def test_encours_carte_mois_sans_achat_masque_le_bandeau(qapp, tmp_path):
    """Un mois consulté sans un seul achat par carte n'a rien à montrer."""
    v, _, _ = _bilan_deux_mois(tmp_path)
    v.period = "2021-03"
    v.refresh()
    assert not v.cb_banner.isVisibleTo(v)


def test_encours_carte_verdict_du_mois_precedent(qapp, tmp_path):
    """Le mois fini, le bandeau dit ce qu'il a laissé — sans qu'on ait à
    changer de période pour aller le chercher."""
    v, today, mois_dernier = _bilan_deux_mois(tmp_path)
    assert "Mois précédent" in v.cb_detail.text()
    assert period_label(mois_dernier.strftime("%Y-%m")).lower() in v.cb_detail.text()
    assert fmt_euro(600.0) in v.cb_detail.text()      # dépensé à la carte
    assert fmt_euro(400.0) in v.cb_detail.text()      # ce qu'il restait
    assert "il restait" in v.cb_detail.text()


def test_encours_carte_verdict_mois_ou_il_a_manque(qapp, tmp_path):
    """Un mois dont les achats dépassent ce que le compte laissait est annoncé
    comme tel, avec le montant qui a manqué."""
    today = date.today()
    mois_dernier = today.replace(day=1) - timedelta(days=1)
    v = _bilan_carte(tmp_path, [(mois_dernier.isoformat(), -1300.0)],
                     nom="manque.db")
    assert "il a MANQUÉ" in v.cb_detail.text()
    assert fmt_euro(300.0) in v.cb_detail.text()      # 1 300 - 1 000


def test_encours_carte_tendance_de_fin_de_mois(qapp, tmp_path, monkeypatch):
    """À partir du 10, le bandeau annonce où finira le mois au rythme actuel.
    Avant, il se tait : une grosse course en début de mois ferait dire
    n'importe quoi."""
    from comptesbudget.ui.views import bilan as mod

    _fige_aujourdhui(monkeypatch, date(2026, 6, 20))
    d = Database(str(tmp_path / "tendance.db"))
    d.set_setting("initial_balance", "1000")
    d.set_setting("initial_date", "2020-01-01")
    d.insert_tx(_tx(id="cb", date="2026-06-05", date_valeur="2026-07-04",
                    libelle="HYPERMARCHE", type="Carte bancaire",
                    montant=-300.0, pointee=1))
    v = mod.BilanView(d)
    v.refresh()
    # 300 € en 20 jours sur un mois de 30 → environ 450 € en fin de mois,
    # sur 1 000 € au compte : il resterait 550 €.
    assert "À ce rythme" in v.cb_detail.text()
    assert fmt_euro(450.0) in v.cb_detail.text()
    assert "il resterait" in v.cb_detail.text()

    _fige_aujourdhui(monkeypatch, date(2026, 6, 3))   # trop tôt : il se tait
    v.refresh()
    assert "À ce rythme" not in v.cb_detail.text()


# ── Cartes SANS débit différé ───────────────────────────────────────────────
# Tout le bandeau Encours suppose une carte à débit différé : des achats faits
# ce mois-ci et prélevés en une fois le mois suivant. Beaucoup de cartes sont
# à débit immédiat — l'achat sort du compte le jour même. Pécule doit rester
# juste pour ces comptes-là.

def _bilan_debit_immediat(tmp_path, nom="immediat.db"):
    """Deux achats par carte débités le jour même, sur un compte de 1 000 €."""
    from comptesbudget.ui.views.bilan import BilanView

    d = Database(str(tmp_path / nom))
    d.set_setting("initial_balance", "1000")
    d.set_setting("initial_date", "2020-01-01")
    today = date.today()
    for i, (recul, montant) in enumerate([(0, -200.0), (3, -50.0)]):
        jour = (today - timedelta(days=recul)).isoformat()
        d.insert_tx(_tx(id=f"ci{i}", date=jour, date_valeur=jour,
                        libelle="HYPERMARCHE", type="Carte bancaire",
                        categorie="Alimentation", montant=montant, pointee=1))
    v = BilanView(d)
    v.refresh()
    return v


def test_bandeau_carte_masque_sans_debit_differe(qapp, tmp_path):
    """Sans débit différé, le bandeau n'a rien à dire : ses trois chiffres
    valent zéro (rien n'est « à débiter »), et « ce qui reste » ferait double
    emploi avec le solde prévu du bandeau « Ce mois-ci »."""
    v = _bilan_debit_immediat(tmp_path)
    assert not v.cb_banner.isVisibleTo(v)


def test_reste_carte_ne_compte_pas_deux_fois_en_debit_immediat(qapp, tmp_path):
    """Le piège : un achat débité le jour même est DÉJÀ sorti du compte. Le
    retrancher une seconde fois du solde de fin de mois annonçait 500 € là où
    il en restait 750."""
    v = _bilan_debit_immediat(tmp_path, nom="immediat2.db")
    txs = [dict(r) for r in v.db.list_tx()]
    mois = date.today().strftime("%Y-%m")
    assert v._solde_fin_de_mois(txs, mois, 750.0) == 750.0
    # Le bandeau étant masqué, aucun chiffre erroné n'est affiché.
    assert not v.cb_banner.isVisibleTo(v)


def test_debit_differe_reconnu_des_quune_operation_le_montre(qapp, tmp_path):
    """Une seule opération carte dont la date de valeur dépasse la date
    d'achat suffit à reconnaître le différé : c'est la banque qui décide, pas
    un réglage à saisir."""
    v = _bilan_debit_immediat(tmp_path, nom="mixte.db")
    jour = date.today().isoformat()
    v.db.insert_tx(_tx(id="cd", date=jour, date_valeur=date_debit_differe(jour),
                       libelle="OMNISHOP", type="Carte bancaire",
                       montant=-30.0, pointee=1))
    v.refresh()
    assert v.cb_banner.isVisibleTo(v)


# ── Le jour où le compte passe sous zéro ────────────────────────────────────

def _bilan_projection(tmp_path, mouvements, initial: float = 100.0,
                      nom: str = "decouvert.db"):
    """Bilan avec un solde de départ et des mouvements À VENIR.

    `mouvements` : liste de (jours à partir d'aujourd'hui, montant). Ils sont
    enregistrés non pointés, donc encore attendus sur le compte."""
    from comptesbudget.ui.views.bilan import BilanView

    d = Database(str(tmp_path / nom))
    d.set_setting("initial_balance", str(initial))
    d.set_setting("initial_date", "2020-01-01")
    today = date.today()
    for i, (jours, montant) in enumerate(mouvements):
        jour = (today + timedelta(days=jours)).isoformat()
        d.insert_tx(_tx(id=f"m{i}", date=jour, date_valeur=jour,
                        libelle="EDF" if montant < 0 else "PENSION",
                        type="Prélèvement" if montant < 0 else "Virement",
                        categorie="Logement - maison" if montant < 0 else "Revenus",
                        montant=montant, pointee=0))
    v = BilanView(d)
    v.refresh()
    return v


def _texte(label):
    """Le texte d'un bandeau, débarrassé de sa mise en forme HTML."""
    import re
    return re.sub("<[^>]+>", "", label.text())


def test_decouvert_annonce_le_jour_et_lorigine(qapp, tmp_path):
    """Un total de fin de mois ne dit pas QUAND le compte plonge. Le bandeau
    donne le jour, le montant, et l'opération qui fait basculer."""
    today = date.today()
    v = _bilan_projection(tmp_path, [(5, -150.0)])
    texte = _texte(v.verdict_banner)
    assert v.verdict_banner.isVisibleTo(v)
    assert fmt_date_fr((today + timedelta(days=5)).isoformat()) in texte
    assert fmt_euro(-50.0) in texte           # 100 - 150
    assert "EDF" in texte                     # l'opération qui fait basculer
    assert "#E74C3C" in v.verdict_banner.styleSheet()      # bordure rouge


def test_decouvert_trouve_le_point_le_plus_bas(qapp, tmp_path):
    """Le creux peut arriver APRÈS une remontée : c'est lui qu'il faut voir,
    pas seulement le premier jour négatif."""
    today = date.today()
    v = _bilan_projection(tmp_path, [(5, -150.0), (10, 500.0), (20, -600.0)],
                          nom="creux.db")
    texte = _texte(v.verdict_banner)
    # 100 → -50 (J+5) → 450 (J+10) → -150 (J+20)
    assert fmt_euro(-150.0) in texte
    assert fmt_date_fr((today + timedelta(days=20)).isoformat()) in texte


def test_decouvert_solde_qui_tient(qapp, tmp_path):
    """Quand le compte tient, le bandeau le dit en vert plutôt que de
    disparaître : une absence de message se lirait comme un calcul oublié."""
    v = _bilan_projection(tmp_path, [(5, -50.0), (10, 200.0)], nom="tient.db")
    texte = _texte(v.verdict_banner)
    assert "reste positif" in texte
    assert fmt_euro(50.0) in texte             # au plus bas : 100 - 50
    assert "#229954" in v.verdict_banner.styleSheet()      # bordure verte


def test_decouvert_deja_a_decouvert_aujourdhui(qapp, tmp_path):
    """Compte déjà négatif : inutile d'annoncer une date future."""
    v = _bilan_projection(tmp_path, [], initial=-80.0, nom="deja.db")
    texte = _texte(v.verdict_banner)
    assert "aujourd'hui" in texte
    assert fmt_euro(-80.0) in texte


def test_decouvert_ignore_ce_qui_est_au_dela_de_lhorizon(qapp, tmp_path):
    """L'horizon est de 45 jours : il couvre toujours le prélèvement carte du
    4 du mois suivant et la remontée des pensions, sans aller deviner plus
    loin que le Prévisionnel ne sait le faire."""
    from comptesbudget.ui.views.bilan import HORIZON_DECOUVERT

    assert HORIZON_DECOUVERT == 45
    v = _bilan_projection(tmp_path, [(HORIZON_DECOUVERT + 10, -500.0)],
                          nom="horizon.db")
    assert "reste positif" in _texte(v.verdict_banner)


def test_encours_carte_avec_remboursement_en_cours(qapp, tmp_path):
    """Un REMBOURSEMENT par carte est porté directement au compte courant : il
    ne vient JAMAIS en déduction de l'encours de la carte. Il reste pourtant
    « en cours » tant que la banque ne l'a pas passé — sa date de valeur est
    immédiate, contrairement à un achat qui attend le prélèvement groupé."""
    from comptesbudget.ui.views.bilan import BilanView

    d = Database(str(tmp_path / "remb.db"))
    d.set_setting("initial_balance", "0")
    d.set_setting("initial_date", "2026-01-01")
    today = date.today()
    prochain = (today.replace(day=1) + timedelta(days=32)).replace(day=4).isoformat()

    # Un achat déjà intégré au prélèvement (date de valeur au 4 du mois suivant)
    d.insert_tx(_tx(id="cb-dep", date=today.isoformat(), date_valeur=prochain,
                    libelle="ACHAT", type="Carte bancaire",
                    montant=-100.0, pointee=1))
    # Un remboursement : date de valeur immédiate, pas encore passé
    d.insert_tx(_tx(id="cb-remb", date=today.isoformat(),
                    date_valeur=today.isoformat(),
                    libelle="OMNISHOP", type="Carte bancaire",
                    montant=15.00, pointee=0))

    v = BilanView(d)
    v.refresh()
    assert v.cb_courant.text() == fmt_euro(-100.0)     # sera prélevé tel quel
    assert v.cb_precedent.text() == fmt_euro(15.00)    # crédit encore en cours
    assert v.cb_total.text() == fmt_euro(-100.0)       # inchangé par le remboursement
    # Le solde du compte (0 €) plus les opérations en cours
    assert "Solde incluant les opérations carte en cours : " + fmt_euro(15.00) \
        in v.cb_detail.text()


def test_bandeau_ce_mois_ci(qapp, tmp_path, monkeypatch):
    """Projection du mois : les opérations déjà enregistrées dont le débit est
    à venir (encours carte) PLUS les échéances du Prévisionnel, sans double
    compte quand l'opération réelle existe déjà.

    La date est figée au 5 : les échéances de ce test sont placées quelques
    jours plus loin, et déborderaient du mois en fin de mois."""
    from comptesbudget.ui.views.bilan import BilanView

    _fige_aujourdhui(monkeypatch, date(2026, 6, 5))
    d = Database(str(tmp_path / "prev.db"))
    d.set_setting("initial_balance", "1000")
    d.set_setting("initial_date", "2026-01-01")
    today = date(2026, 6, 5)          # la date que voit la vue
    dans_5j = (today + timedelta(days=5)).isoformat()

    # Solde du jour : 1000 € (une opération pointée déjà débitée à 0)
    # Débit carte à venir dans 5 jours
    d.insert_tx(_tx(id="cb", date=today.isoformat(), date_valeur=dans_5j,
                    libelle="ACHATS CARTE", type="Carte bancaire",
                    montant=-200.0, pointee=1))
    # Une échéance du Prévisionnel à venir dans 5 jours
    d.insert_recurring({"id": "r-loyer", "libelle": "Loyer", "montant": -750.0,
                        "categorie": "Logement - maison", "sous_cat": "",
                        "type": "Prelevement", "frequency": "monthly",
                        "day_of_month": (today + timedelta(days=5)).day,
                        "start_date": "2026-01-01", "end_date": None, "actif": 1})
    # Une rentrée récurrente
    d.insert_recurring({"id": "r-pension", "libelle": "Pension", "montant": 1500.0,
                        "categorie": "Revenus", "sous_cat": "", "type": "Virement",
                        "frequency": "monthly",
                        "day_of_month": (today + timedelta(days=6)).day,
                        "start_date": "2026-01-01", "end_date": None, "actif": 1})

    v = BilanView(d)
    v.refresh()
    assert v.kpis["solde"]._value.text() == fmt_euro(1000.0)   # carte non débitée
    assert v.mois_sorties.text() == fmt_euro(-750.0)           # hors carte
    assert v.mois_entrees.text() == fmt_euro(1500.0)
    # 1000 − 200 (carte) − 750 (loyer) + 1500 (pension)
    assert v.mois_solde.text() == fmt_euro(1550.0)
    assert "débit carte" in v.mois_detail.text()
    # Les prochaines échéances nommées, reprises du bandeau des 15 jours.
    assert "Prochaines : " in v.mois_detail.text()


def test_bandeau_mois_ne_compte_pas_deux_fois(qapp, tmp_path, monkeypatch):
    """Si l'opération réelle est déjà enregistrée pour une échéance à venir,
    la récurrence correspondante ne doit pas s'y ajouter."""
    from comptesbudget.ui.views.bilan import BilanView

    _fige_aujourdhui(monkeypatch, date(2026, 6, 5))
    d = Database(str(tmp_path / "prev2.db"))
    d.set_setting("initial_balance", "0")
    d.set_setting("initial_date", "2026-01-01")
    today = date(2026, 6, 5)          # la date que voit la vue
    dans_3j = (today + timedelta(days=3)).isoformat()

    d.insert_tx(_tx(id="loyer-reel", date=dans_3j, date_valeur=dans_3j,
                    libelle="Loyer", type="Prelevement",
                    categorie="Logement - maison", montant=-750.0, pointee=0))
    d.insert_recurring({"id": "r-loyer", "libelle": "Loyer", "montant": -750.0,
                        "categorie": "Logement - maison", "sous_cat": "",
                        "type": "Prelevement", "frequency": "monthly",
                        "day_of_month": (today + timedelta(days=3)).day,
                        "start_date": "2026-01-01", "end_date": None, "actif": 1})

    v = BilanView(d)
    v.refresh()
    assert v.mois_sorties.text() == fmt_euro(-750.0)   # une seule fois


def test_debit_carte_ignore_les_operations_en_cours(qapp, tmp_path, monkeypatch):
    """Le débit annoncé pour le prochain prélèvement ne compte QUE les
    opérations que la banque y a rattachées (les pointées). Un remboursement
    carte encore « en cours » ne réduit pas ce prélèvement-là : il partira au
    suivant. Sinon le montant annoncé ne correspond pas au relevé."""
    from comptesbudget.ui.views.bilan import BilanView

    _fige_aujourdhui(monkeypatch, date(2026, 6, 5))
    d = Database(str(tmp_path / "cb-prev.db"))
    d.set_setting("initial_balance", "0")
    d.set_setting("initial_date", "2026-01-01")
    today = date(2026, 6, 5)          # la date que voit la vue
    dans_4j = (today + timedelta(days=4)).isoformat()

    d.insert_tx(_tx(id="cb-conf", date=today.isoformat(), date_valeur=dans_4j,
                    libelle="ACHATS", type="Carte bancaire",
                    montant=-120.00, pointee=1))
    d.insert_tx(_tx(id="cb-remb", date=today.isoformat(), date_valeur=dans_4j,
                    libelle="OMNISHOP", type="Carte bancaire",
                    montant=15.00, pointee=0))

    v = BilanView(d)
    v.refresh()
    # Le débit annoncé est celui du relevé, sans le remboursement en cours
    assert "débit carte " + fmt_euro(-120.00) in v.mois_detail.text()
    assert "au prélèvement suivant" in v.mois_detail.text()
    assert v.mois_solde.text() == fmt_euro(-120.00)
    # Le bandeau carte, lui, continue d'afficher les deux chiffres
    assert v.cb_courant.text() == fmt_euro(-120.00)
    assert v.cb_precedent.text() == fmt_euro(15.00)


def test_txdialog_remboursement_carte_sans_debit_differe(qapp, db):
    """Un remboursement par carte (crédit) est porté directement au compte :
    pas de débit différé. Le formulaire ne doit donc PAS proposer le 4 du mois
    suivant, contrairement à un achat."""
    from PySide6.QtCore import QDate

    from comptesbudget.ui.dialogs import TxDialog

    txs = [dict(r) for r in db.list_tx()]
    dlg = TxDialog(None, None, categories=CATEGORIES_DEFAUT, all_transactions=txs)
    dlg.date_edit.setDate(QDate(2026, 7, 15))
    dlg.type_combo.setCurrentText("Carte bancaire")

    # Achat : débit différé au 4 du mois suivant
    assert dlg.values()["date_valeur"] == "2026-08-04"
    assert dlg.dv_hint.isVisibleTo(dlg)

    # Bascule en crédit : la date de valeur revient à la date d'opération
    dlg.rb_credit.setChecked(True)
    assert dlg.values()["date_valeur"] == "2026-07-15"
    assert not dlg.dv_hint.isVisibleTo(dlg)

    # Retour en débit : le débit différé revient
    dlg.rb_debit.setChecked(True)
    assert dlg.values()["date_valeur"] == "2026-08-04"


def test_tri_colonnes_dates_et_montants(qapp, tmp_path):
    """Le tri par clic doit porter sur les VALEURS, pas sur le texte affiché :
    « 09/01 » ne vient pas après « 10/01 », et « -1 000,00 € » est bien plus
    petit que « -90,00 € »."""
    from PySide6.QtCore import Qt

    from comptesbudget.ui.models import TxTableModel
    from comptesbudget.ui.views.operations import OperationsView

    d = Database(str(tmp_path / "tri.db"))
    d.set_setting("initial_balance", "0")
    d.set_setting("initial_date", "2026-01-01")
    for i, (jour, montant, lib) in enumerate([
            ("09", -90.0, "Bravo"), ("10", -1000.0, "alpha"), ("02", -5.0, "Charlie")]):
        d.insert_tx(_tx(id=f"t{i}", date=f"2026-01-{jour}",
                        date_valeur=f"2026-01-{jour}", libelle=lib, montant=montant))

    v = OperationsView(d)
    v.period = "2026-01"
    v.reload_from_db()

    # Dates : ordre chronologique, pas alphabétique
    v.table.sortByColumn(TxTableModel.COL_DATE_OP, Qt.AscendingOrder)
    assert [v.model.item(r, 1).text() for r in range(3)] == [
        "02/01/2026", "09/01/2026", "10/01/2026"]

    # Débits : ordre numérique (le plus gros d'abord en croissant)
    v.table.sortByColumn(7, Qt.AscendingOrder)
    assert [v.model.item(r, 7).text() for r in range(3)] == [
        fmt_euro(-1000.0), fmt_euro(-90.0), fmt_euro(-5.0)]

    # Libellés : insensible à la casse
    v.table.sortByColumn(3, Qt.AscendingOrder)
    assert [v.model.item(r, 3).text() for r in range(3)] == ["alpha", "Bravo", "Charlie"]

    # Le tri choisi survit à un rechargement (changement de filtre)
    v.search.setText("a")
    assert v.table.horizontalHeader().sortIndicatorSection() == 3


def test_tri_budget_conserve_les_barres(qapp, tmp_path):
    """Les barres de progression du Budget sont des widgets posés dans les
    cellules : après un tri, chaque ligne doit toujours avoir la sienne."""
    from PySide6.QtCore import Qt

    from comptesbudget.ui.views.budget import BudgetView

    d = Database(str(tmp_path / "tri-bud.db"))
    d.set_setting("initial_balance", "0")
    d.set_setting("initial_date", "2026-01-01")
    d.insert_tx(_tx(id="a", date="2026-01-05", date_valeur="2026-01-05",
                    categorie="Alimentation", montant=-300.0))
    d.insert_tx(_tx(id="b", date="2026-01-06", date_valeur="2026-01-06",
                    categorie="Loisirs", montant=-50.0))
    d.set_budget("Alimentation", 400.0)
    d.set_budget("Loisirs", 100.0)

    v = BudgetView(d)
    v.period = "2026-01"
    v.refresh()

    v.table.horizontalHeader().setSortIndicator(2, Qt.DescendingOrder)   # dépensé
    assert v.model.item(0, 0).text() == "Alimentation"      # le plus dépensé d'abord
    assert all(v.table.indexWidget(v.model.index(r, 3)) is not None
               for r in range(v.model.rowCount()))

    v.table.horizontalHeader().setSortIndicator(2, Qt.AscendingOrder)
    assert v.model.item(0, 0).text() == "Loisirs"
    assert all(v.table.indexWidget(v.model.index(r, 3)) is not None
               for r in range(v.model.rowCount()))


def test_montant_accepte_le_point_decimal(qapp):
    """Le point du pavé numérique doit valoir la virgule dans un champ de
    montant : « 12.50 » saisi donne bien 12,50 € (demande du 05/08/2026)."""
    from PySide6.QtCore import QLocale

    from comptesbudget.ui.widgets import MontantSpinBox

    QLocale.setDefault(QLocale(QLocale.French, QLocale.France))
    sb = MontantSpinBox()
    sb.setRange(0.0, 1_000_000.0)
    sb.setDecimals(2)
    sb.setSuffix(" €")
    for saisie in ("12.50", "12,50", "1234.05", "0.99"):
        sb.clear()
        sb.lineEdit().setText(saisie)
        sb.interpretText()
        attendu = float(saisie.replace(",", "."))
        assert sb.value() == attendu, f"{saisie} → {sb.value()}"


def test_changer_le_type_recale_la_date_de_valeur(qapp):
    """Corriger le type d'une opération DÉJÀ enregistrée doit recalculer sa
    date de valeur : sans cela, un prélèvement saisi par erreur en « Carte
    bancaire » gardait la date du 4 du mois suivant et sortait du solde
    bancaire réel (cas d'une prime d'assurance auto prélevée en début de
    mois)."""
    from comptesbudget.ui.dialogs import TxDialog

    tx = _tx(id="assurance", date="2026-08-05", date_valeur="2026-09-04",
             libelle="L'amandier Assurrance", type="Carte bancaire",
             categorie="Banque et assurances", montant=-35.00, pointee=1)
    dlg = TxDialog(tx=tx, categories=CATEGORIES_DEFAUT, all_transactions=[])
    # À l'ouverture, la date enregistrée est respectée telle quelle
    assert dlg.date_val.date().toString("yyyy-MM-dd") == "2026-09-04"
    # Le vrai type est « Prelevement » : la date de valeur suit
    dlg.type_combo.setCurrentText("Prelevement")
    assert dlg.date_val.date().toString("yyyy-MM-dd") == "2026-08-05"
    # ...et le retour en carte bancaire redonne le débit différé
    dlg.type_combo.setCurrentText("Carte bancaire")
    assert dlg.date_val.date().toString("yyyy-MM-dd") == "2026-09-04"


def test_pas_de_debit_differe_impose_a_la_saisie(qapp):
    """Sur un compte à débit immédiat, la date de valeur d'un achat par carte
    suit la date d'achat. Reporter d'office au 4 du mois suivant fausserait le
    solde de tous ceux qui n'ont pas de carte à débit différé."""
    from PySide6.QtCore import QDate

    from comptesbudget.ui.dialogs import TxDialog

    immediates = [_tx(id="a", date="2026-08-05", date_valeur="2026-08-05",
                      type="Carte bancaire", montant=-20.0)]
    dlg = TxDialog(categories=CATEGORIES_DEFAUT, all_transactions=immediates)
    dlg.date_edit.setDate(QDate(2026, 8, 12))
    dlg.type_combo.setCurrentText("Carte bancaire")
    dlg.rb_debit.setChecked(True)
    assert dlg.date_val.date().toString("yyyy-MM-dd") == "2026-08-12"


def test_debit_differe_repere_dans_lhistorique_est_applique(qapp):
    """Dès qu'une opération du compte montre le différé, la saisie suivante en
    profite : c'est la banque qui décide, pas un réglage à comprendre."""
    from PySide6.QtCore import QDate

    from comptesbudget.ui.dialogs import TxDialog

    differees = [_tx(id="a", date="2026-08-05", date_valeur="2026-09-04",
                     type="Carte bancaire", montant=-20.0)]
    dlg = TxDialog(categories=CATEGORIES_DEFAUT, all_transactions=differees)
    dlg.date_edit.setDate(QDate(2026, 8, 12))
    dlg.type_combo.setCurrentText("Carte bancaire")
    dlg.rb_debit.setChecked(True)
    assert dlg.date_val.date().toString("yyyy-MM-dd") == "2026-09-04"


def test_date_de_valeur_saisie_a_la_main_est_respectee(qapp):
    """Une date de valeur saisie à la main ne doit pas être écrasée tant que
    le type et le sens ne changent pas (achat carte de fin de mois débité au
    cycle suivant)."""
    from PySide6.QtCore import QDate

    from comptesbudget.ui.dialogs import TxDialog

    dlg = TxDialog(categories=CATEGORIES_DEFAUT, all_transactions=[])
    dlg.type_combo.setCurrentText("Carte bancaire")
    dlg.date_edit.setDate(QDate(2026, 7, 31))
    dlg.date_val.setDate(QDate(2026, 9, 4))      # correction volontaire
    dlg.libelle.setText("Centre Marche")
    assert dlg.date_val.date().toString("yyyy-MM-dd") == "2026-09-04"


def test_generer_echeances_du_mois(qapp, db):
    """L'assistant « Générer les échéances du mois » liste ce qui doit tomber
    dans le mois, le crée en NON pointé, et ne le recrée pas au second passage."""
    from comptesbudget.ui.assistants import GenererEcheancesDialog
    from comptesbudget.ui.views.previsionnel import PrevisionnelView

    view = PrevisionnelView(db)
    mois = date.today().isoformat()[:7]

    dlg = GenererEcheancesDialog(None, view._echeances, mois, view._mois_proposes())
    assert dlg.model.rowCount() >= 1          # le loyer mensuel de la fixture
    dlg._set_all(True)
    assert dlg.selected()
    dlg.mois_combo.setCurrentIndex(1)         # mois suivant : recalcul sans planter
    assert dlg.model.rowCount() >= 1

    echeances = view._echeances(mois)
    assert view._creer_operations(echeances) == len(echeances)
    crees = [dict(t) for t in db.list_tx() if t["prevue"]]
    assert len(crees) == len(echeances)
    assert all(t["pointee"] == 0 for t in crees)

    # Second passage : tout est désormais couvert, plus rien à créer.
    assert all(e["_deja"] for e in view._echeances(mois))


def test_bilan_ne_compte_pas_deux_fois_une_echeance_generee(qapp, db):
    """Une échéance matérialisée en opération ne doit pas s'ajouter à la
    récurrence dont elle vient : « ce qui est prévu » compterait le double."""
    from comptesbudget.ui.views.bilan import BilanView
    from comptesbudget.ui.views.previsionnel import PrevisionnelView

    bilan = BilanView(db)
    bilan.refresh()
    sans_assurance = _euros(bilan.mois_sorties.text())

    cible = date.today() + timedelta(days=3)      # dans la fenêtre du mois
    db.insert_recurring({"id": "rec-test", "libelle": "ASSURANCE TEST",
                         "montant": -123.45, "categorie": "Assurances",
                         "sous_cat": "", "type": "Prelevement",
                         "frequency": "monthly", "day_of_month": cible.day,
                         "start_date": cible.isoformat(), "end_date": None,
                         "actif": 1})

    bilan.refresh()
    avant = bilan.mois_sorties.text()
    # La récurrence est bien prévue : le total a baissé d'exactement 123,45 €.
    # On mesure l'écart, car le jeu d'essai contient d'autres échéances dont
    # la présence dans la fenêtre dépend du jour du mois.
    assert round(_euros(avant) - sans_assurance, 2) == -123.45

    prev = PrevisionnelView(db)
    mois = cible.isoformat()[:7]
    a_creer = [e for e in prev._echeances(mois) if not e["_deja"]]
    assert prev._creer_operations(a_creer) == len(a_creer)

    bilan.refresh()
    assert bilan.mois_sorties.text() == avant      # inchangé : pas de doublon


# ── Graphique « Évolution sur 12 mois » ─────────────────────────────────────

def _bilan_douze_mois(tmp_path):
    """Bilan avec une dépense et une rentrée chaque mois sur deux ans."""
    from comptesbudget.ui.views.bilan import BilanView

    d = Database(str(tmp_path / "graph.db"))
    d.set_setting("initial_balance", "0")
    d.set_setting("initial_date", "2024-01-01")
    n = 0
    for an in (2025, 2026):
        for mois in range(1, 13):
            jour = f"{an}-{mois:02d}-10"
            d.insert_tx(_tx(id=f"r{n}", date=jour, date_valeur=jour,
                            libelle="PENSION", type="Virement",
                            categorie="Revenus", montant=1000.0, pointee=1))
            d.insert_tx(_tx(id=f"d{n}", date=jour, date_valeur=jour,
                            libelle="SAUR", type="Prélèvement",
                            categorie="Logement - maison", montant=-400.0,
                            pointee=1))
            n += 1
    v = BilanView(d)
    v.refresh()
    return v


def _barres(v):
    """Les valeurs des deux séries du graphique."""
    return {bs.label(): [bs.at(i) for i in range(bs.count())]
            for s in v.bar_chart.series() for bs in s.barSets()}


def test_graphique_montre_douze_mois_meme_sur_un_mois(qapp, tmp_path):
    """Sur un mois affiché, le graphique dessinait UNE barre : un quart de
    l'écran pour un chiffre donné six fois ailleurs. Il montre désormais
    toujours douze mois, ce qui répond à « est-ce que ça se dégrade ? »."""
    v = _bilan_douze_mois(tmp_path)
    v.period = "2026-05"
    v.refresh()
    barres = _barres(v)
    assert len(barres["Revenus"]) == 12
    assert len(barres["Dépenses"]) == 12
    # Les douze mois s'achèvent sur le mois affiché, pour le situer dans son
    # histoire : juin 2025 → mai 2026.
    assert "JUN 2025" in v.bar_panel._header.text()
    assert "MAI 2026" in v.bar_panel._header.text()


def test_graphique_sur_une_annee_montre_ses_douze_mois(qapp, tmp_path):
    """Une année choisie montre janvier à décembre de cette année-là."""
    v = _bilan_douze_mois(tmp_path)
    v.period = "2025"
    v.refresh()
    assert v._mois_du_graphique([]) == [f"2025-{m:02d}" for m in range(1, 13)]
    assert "JAN 2025" in v.bar_panel._header.text()
    assert "DÉC 2025" in v.bar_panel._header.text()


def test_graphique_ignore_le_filtre_de_periode(qapp, tmp_path):
    """Les barres portent tous les mois, pas seulement les opérations de la
    période : sinon onze colonnes sur douze resteraient vides."""
    v = _bilan_douze_mois(tmp_path)
    v.period = "2026-05"
    v.refresh()
    barres = _barres(v)
    assert all(x == 1000.0 for x in barres["Revenus"])
    assert all(x == 400.0 for x in barres["Dépenses"])


def test_graphique_replie_sur_les_derniers_mois_connus(qapp, tmp_path):
    """Une base dont les données s'arrêtent il y a longtemps donnerait douze
    colonnes vides : on retombe sur les douze derniers mois qui portent
    quelque chose."""
    from comptesbudget.ui.views.bilan import BilanView

    d = Database(str(tmp_path / "vieux.db"))
    d.set_setting("initial_balance", "0")
    d.set_setting("initial_date", "2020-01-01")
    anciens = [_tx(id=f"v{m}", date=f"2021-{m:02d}-10",
                   date_valeur=f"2021-{m:02d}-10", libelle="SAUR",
                   type="Prélèvement", montant=-50.0, pointee=1)
               for m in range(1, 13)]
    for t in anciens:
        d.insert_tx(t)
    v = BilanView(d)
    v.refresh()
    assert v._mois_du_graphique(anciens)[-1] == "2021-12"


def test_bilan_bandeau_fin_de_mois(qapp, tmp_path):
    """« Ce mois-ci » : solde en banque + tout ce qui reste à passer d'ici la
    fin du mois, sans recompter ce qui est déjà pointé."""
    from calendar import monthrange

    from comptesbudget.ui.views.bilan import BilanView

    d = Database(str(tmp_path / "mois.db"))
    d.set_setting("initial_balance", "1000")
    d.set_setting("initial_date", "2026-01-01")

    today = date.today()
    premier = today.replace(day=1).isoformat()
    dernier = date(today.year, today.month,
                   monthrange(today.year, today.month)[1]).isoformat()

    # Déjà passée en banque → dans le solde, pas dans le reste à passer
    d.insert_tx(_tx(id="payee", date=premier, date_valeur=premier,
                    libelle="LOYER PAYE", type="Prelevement",
                    montant=-100.0, pointee=1))
    # Échéance du début de mois toujours pas passée : elle reste due
    d.insert_tx(_tx(id="attendue-1", date=premier, date_valeur=premier,
                    libelle="ELECTRICITE", type="Prelevement", montant=-50.0,
                    pointee=0, prevue=1))
    # Échéance de fin de mois
    d.insert_tx(_tx(id="attendue-2", date=dernier, date_valeur=dernier,
                    libelle="ASSURANCE", type="Prelevement", montant=-200.0,
                    pointee=0, prevue=1))

    vue = BilanView(d)
    vue.refresh()

    assert vue.kpis["solde"]._value.text() == fmt_euro(900.0)   # 1000 - 100
    assert vue.mois_sorties.text() == fmt_euro(-250.0)          # 50 + 200
    assert vue.mois_solde.text() == fmt_euro(650.0)             # 900 - 250
    assert "2 échéance(s) déjà saisie(s)" in vue.mois_detail.text()
    assert vue.mois_banner.isVisibleTo(vue)


def test_bilan_fin_de_mois_ignore_le_mois_suivant(qapp, tmp_path):
    """Une échéance qui tombe après le dernier jour du mois n'entre pas dans
    le solde de fin de mois."""
    from comptesbudget.ui.views.bilan import BilanView

    d = Database(str(tmp_path / "mois2.db"))
    d.set_setting("initial_balance", "1000")
    d.set_setting("initial_date", "2026-01-01")

    today = date.today()
    mois_prochain = (today.replace(day=1) + timedelta(days=40)).replace(day=3)
    d.insert_tx(_tx(id="plus-tard", date=mois_prochain.isoformat(),
                    date_valeur=mois_prochain.isoformat(), libelle="IMPOTS",
                    type="Prelevement", montant=-300.0, pointee=0, prevue=1))

    vue = BilanView(d)
    vue.refresh()
    assert vue.mois_sorties.text() == fmt_euro(0)
    assert vue.mois_solde.text() == fmt_euro(1000.0)


def test_bilan_ne_recompte_pas_une_echeance_deja_encaissee(qapp, tmp_path,
                                                          monkeypatch):
    """Défaut corrigé en 1.21 : une pension versée le 1er sous le libellé de
    la banque était re-annoncée comme « à venir » parce que la récurrence la
    plaçait le 9 sous un libellé légèrement différent."""
    from comptesbudget.ui.views.bilan import BilanView

    d = Database(str(tmp_path / "double.db"))
    d.set_setting("initial_balance", "0")
    d.set_setting("initial_date", "2026-01-01")

    # On se place au 5 mars : l'échéance du 9 est devant nous (donc dans la
    # fenêtre des 15 jours), et celle d'avril est bien au-delà.
    _fige_aujourdhui(monkeypatch, date(2026, 3, 5))

    # Versement déjà encaissé il y a peu, libellé « à la banque »
    deja = date(2026, 3, 1)
    d.insert_tx(_tx(id="pension", date=deja.isoformat(),
                    date_valeur=deja.isoformat(), libelle="CAISSE RETRAITE 12",
                    type="Virement", categorie="Revenus",
                    montant=900.00, pointee=1))
    # La récurrence le place quelques jours plus tard, sous son nom à lui
    plus_tard = date(2026, 3, 9)
    d.insert_recurring({"id": "rec-pension", "libelle": "Caisse Retraite",
                        "montant": 900.00, "categorie": "Revenus",
                        "sous_cat": "", "type": "Virement",
                        "frequency": "monthly", "day_of_month": plus_tard.day,
                        "start_date": plus_tard.isoformat(), "end_date": None,
                        "actif": 1})

    vue = BilanView(d)
    vue.refresh()
    assert vue.kpis["solde"]._value.text() == fmt_euro(900.00)
    # Ni le bandeau des 15 jours ni celui du mois ne doivent l'annoncer encore
    assert vue.mois_entrees.text() == fmt_euro(0)
    assert vue.mois_entrees.text() == fmt_euro(0)
    assert vue.mois_solde.text() == fmt_euro(900.00)


def test_non_pointees_ignore_la_periode(qapp, tmp_path):
    """« Non pointées » montre tout ce qui reste à pointer, y compris les mois
    qui ne sont pas affichés : sinon une opération oubliée en juillet reste
    invisible tant que l’écran est sur août."""
    from comptesbudget.ui.views.operations import OperationsView

    d = Database(str(tmp_path / "pointage.db"))
    d.set_setting("initial_balance", "0")
    d.set_setting("initial_date", "2026-01-01")
    d.insert_tx(_tx(id="a", date="2026-07-10", date_valeur="2026-07-10",
                    libelle="Juillet non pointee", montant=-10.0))
    d.insert_tx(_tx(id="b", date="2026-08-10", date_valeur="2026-08-10",
                    libelle="Aout non pointee", montant=-20.0))
    d.insert_tx(_tx(id="c", date="2026-08-11", date_valeur="2026-08-11",
                    libelle="Aout pointee", montant=-30.0, pointee=1))

    v = OperationsView(d)
    v.period = "2026-08"
    v.reload_from_db()

    # Sans filtre de pointage, le mois affiché commande
    assert sorted(t["id"] for t in v.filtered) == ["b", "c"]

    # « Non pointées » : les deux mois, et le compteur prévient
    v.pt_filter.setCurrentText("Non pointées")
    assert sorted(t["id"] for t in v.filtered) == ["a", "b"]
    assert "toutes périodes" in v.lbl_count.text()

    # Les autres choix restent bornés au mois affiché
    v.pt_filter.setCurrentText("Pointées")
    assert [t["id"] for t in v.filtered] == ["c"]
    assert "toutes périodes" not in v.lbl_count.text()

def test_traduction_qt_francaise(qapp):
    """Les boutons fournis par Qt doivent parler français.

    L'application est entièrement en français : afficher « Cancel » sous le nez
    de l'utilisateur détonnerait. Ces libellés ne viennent pas de notre code,
    c'est Qt qui les fabrique — on charge donc ses traductions.
    """
    from PySide6.QtWidgets import QDialogButtonBox
    from comptesbudget.app import installer_traduction_qt

    assert installer_traduction_qt(qapp), "traduction française de Qt introuvable"
    boite = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel
                             | QDialogButtonBox.Yes | QDialogButtonBox.No)
    libelles = [b.text().replace("&", "") for b in boite.buttons()]
    assert "Annuler" in libelles
    assert "Oui" in libelles
    assert "Non" in libelles
    assert "Cancel" not in libelles


def test_bilan_previent_si_le_solde_de_depart_manque(qapp, tmp_path):
    """Tant que le solde de départ n'a jamais été saisi, un bandeau le dit :
    l'invite du premier lancement ne revient plus une fois fermée, et le gros
    chiffre du Bilan n'additionne alors que les opérations."""
    from comptesbudget.ui.views.bilan import BilanView

    db = Database(str(tmp_path / "neuve.db"))
    vue = BilanView(db)
    vue.refresh()
    assert vue.solde_depart_alert.isVisibleTo(vue)
    assert "Solde de départ non renseigné" in vue.solde_depart_alert.text()

    # Une fois renseigné — même à zéro, si c'est un choix — le bandeau s'en va.
    db.set_setting("initial_balance", "0")
    vue.refresh()
    assert not vue.solde_depart_alert.isVisibleTo(vue)


def test_bilan_previent_si_des_operations_precedent_la_date_de_depart(qapp, tmp_path):
    """Une opération antérieure à la date de départ s'affiche dans les listes
    mais sort du solde : sans un mot, l'écart est incompréhensible."""
    from comptesbudget.ui.views.bilan import BilanView

    db = Database(str(tmp_path / "avant.db"))
    db.set_setting("initial_date", "2026-01-01")
    db.set_setting("initial_balance", "1000")
    db.insert_tx(_tx(id="vieille", date="2025-06-15", date_valeur="2025-06-15",
                     libelle="ACHAT ANCIEN", montant=-300.0, pointee=1))
    vue = BilanView(db)
    vue.refresh()
    assert vue.hors_solde_alert.isVisibleTo(vue)
    texte = vue.hors_solde_alert.text()
    assert "01/01/2026" in texte and "300" in texte

    # Reculer la date de départ les fait rentrer dans le calcul.
    db.set_setting("initial_date", "2025-01-01")
    vue.refresh()
    assert not vue.hors_solde_alert.isVisibleTo(vue)


def test_operations_pointage_en_masse(qapp, tmp_path):
    """Pointer ligne à ligne était le seul moyen : un an d'historique
    demandait plusieurs centaines de clics."""
    from comptesbudget.ui.views.operations import OperationsView

    db = Database(str(tmp_path / "masse.db"))
    db.set_setting("initial_balance", "0")
    for i in range(3):
        db.insert_tx(_tx(id=f"m{i}", date=f"2026-06-0{i + 1}",
                         date_valeur=f"2026-06-0{i + 1}", montant=-10.0 * (i + 1),
                         pointee=0))
    vue = OperationsView(db)
    vue.period = "all"
    vue.reload_from_db()
    vue.table.selectAll()
    assert len(vue.selected_tx_ids()) == 3

    vue.pointer_selection(True)
    assert all(dict(t)["pointee"] == 1 for t in db.list_tx())

    vue.table.selectAll()
    vue.pointer_selection(False)
    assert all(dict(t)["pointee"] == 0 for t in db.list_tx())


def test_operations_menu_contextuel_se_construit(qapp, tmp_path):
    """Le menu du clic droit annonce le nombre de lignes visées."""
    from comptesbudget.ui.views.operations import OperationsView

    db = Database(str(tmp_path / "menu.db"))
    for i in range(2):
        db.insert_tx(_tx(id=f"k{i}", date=f"2026-06-0{i + 1}",
                         date_valeur=f"2026-06-0{i + 1}", montant=-5.0))
    vue = OperationsView(db)
    vue.period = "all"
    vue.reload_from_db()
    vue.table.selectAll()

    intitules = [a.text() for a in vue._construire_menu().actions()]
    assert any("Pointer ces 2 opérations" in t for t in intitules)
    assert any("Supprimer ces 2 opérations" in t for t in intitules)


def test_fenetre_tient_sur_un_petit_ecran(qapp, tmp_path):
    """La fenêtre doit tenir sur un portable 1366 × 768 : une fois retirées
    la barre des tâches et la barre de titre, il reste environ 700 px. Qt ne
    descend jamais sous le minimum réclamé, et Windows laisse alors la fenêtre
    déborder — boutons du bas hors d'atteinte."""
    from comptesbudget.ui.main_window import MainWindow

    db = Database(str(tmp_path / "ecran.db"))
    db.set_setting("initial_balance", "0")
    fenetre = MainWindow(db)
    # Seule la HAUTEUR est vérifiée ici : la largeur dépend des polices, que
    # le mode « offscreen » des tests ne charge pas (elle s'y mesure à 1690 px
    # contre 1082 en vrai). Elle se contrôle à la main, écran allumé.
    mini = fenetre.minimumSizeHint()
    assert mini.height() <= 700, f"hauteur minimale : {mini.height()} px"


def test_glisser_deposer_explique_un_fichier_excel(qapp, tmp_path):
    """Un tableur déposé sur la fenêtre était ignoré sans un mot : rien ne
    distinguait « format non lu » de « glisser-déposer en panne »."""
    from PySide6.QtCore import QMimeData, QUrl
    from comptesbudget.ui.main_window import MainWindow

    db = Database(str(tmp_path / "depot.db"))
    db.set_setting("initial_balance", "0")
    fenetre = MainWindow(db)

    class _Evenement:
        def __init__(self, chemin):
            self._mime = QMimeData()
            self._mime.setUrls([QUrl.fromLocalFile(chemin)])

        def mimeData(self):
            return self._mime

    assert "tableur" in fenetre._conseil_depot(_Evenement("C:/releve.xlsx"))
    assert "PDF" in fenetre._conseil_depot(_Evenement("C:/releve.pdf"))
    assert "Restaurer (JSON)" in fenetre._conseil_depot(_Evenement("C:/sauve.json"))
    # Un vrai relevé n'a pas besoin de conseil : il s'importe.
    assert fenetre._conseil_depot(_Evenement("C:/releve.csv")) == ""


def test_reprendre_un_ancien_fichier_de_donnees(qapp, tmp_path, monkeypatch):
    """Le piège de la mise à jour : le nouvel exécutable, lancé depuis un
    autre dossier, ouvre une base vide. On doit pouvoir reprendre l'ancien
    comptes.db sans redémarrer, et sans y perdre une opération."""
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    from comptesbudget.ui.main_window import MainWindow

    ancienne = str(tmp_path / "ancienne" / "comptes.db")
    os.makedirs(os.path.dirname(ancienne))
    source = Database(ancienne)
    source.set_setting("initial_balance", "1200")
    source.set_setting("initial_date", "2026-01-01")
    for i in range(3):
        source.insert_tx(_tx(id=f"a{i}", date=f"2026-06-0{i + 1}",
                             date_valeur=f"2026-06-0{i + 1}",
                             libelle=f"ANCIENNE {i}", montant=-10.0 * (i + 1),
                             pointee=1))
    source.conn.close()

    neuve = Database(str(tmp_path / "neuve.db"))
    fenetre = MainWindow(neuve)
    assert neuve.est_vide()

    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: (ancienne, "")))
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: None))
    assert fenetre.action_reprendre_donnees() is True

    reprises = [dict(t) for t in neuve.list_tx()]
    assert len(reprises) == 3
    assert neuve.get_setting("initial_balance") == "1200"
    assert not neuve.est_vide()
    # Le fichier d'origine est laissé intact.
    temoin = Database(ancienne)
    assert len(temoin.list_tx()) == 3


def test_reprendre_refuse_un_fichier_etranger(qapp, tmp_path):
    """Un fichier qui n'est pas une base Pécule est écarté avec un motif."""
    from comptesbudget.ui.main_window import MainWindow

    intrus = tmp_path / "photo.jpg"
    intrus.write_bytes(b"\xff\xd8\xff\xe0 pas une base")
    message = MainWindow._verifier_base_pecule(str(intrus))
    assert "Pécule" in message
