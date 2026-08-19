"""Smoke tests de la couche UI.

On construit chaque vue, fenêtre et dialogue avec une base en mémoire peuplée,
puis on déclenche le rafraîchissement. But : attraper les plantages et les
erreurs de câblage (imports, signaux, calculs au refresh) sans simuler
d'interaction — rapide, headless, peu fragile.
"""
import importlib
from datetime import date, timedelta

import pytest

from comptesbudget.constants import CATEGORIES_DEFAUT
from comptesbudget.database import Database
from comptesbudget.utils import fmt_euro


def _tx(**kw):
    base = {
        "id": "x", "date": "2026-06-01", "date_valeur": "2026-06-01",
        "libelle": "OP", "libelle_op": "OP", "reference": "", "type": "",
        "categorie": "Non classé", "sous_cat": "", "info": "",
        "montant": -10.0, "pointee": 0,
    }
    base.update(kw)
    return base


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

    assert SettingsDialog(None, "2026-01-01", 1000.0).values() == ("2026-01-01", 1000.0)
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


def test_tous_les_onglets_suivent_le_mode_date(qapp, tmp_path):
    """Bilan, Budget et Catégories doivent compter les MÊMES opérations pour
    une période donnée. Un achat carte du 28/07 débité le 04/08 appartient à
    août en mode « date de valeur » et à juillet en mode « date d'opération » :
    les trois vues doivent être d'accord, sinon les chiffres se contredisent
    d'un onglet à l'autre."""
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

    # Juillet en date de valeur : l'opération n'y est pour aucune des vues.
    assert depenses(BilanView, "2026-07", "valeur").kpis["depenses"]._value.text() \
        == fmt_euro(0)
    assert depenses(BudgetView, "2026-07", "valeur").model.rowCount() == 0
    assert depenses(CategoriesView, "2026-07", "valeur").cats_model.rowCount() == 0

    # Août en date de valeur : les trois vues la voient.
    assert depenses(BilanView, "2026-08", "valeur").kpis["depenses"]._value.text() \
        == fmt_euro(-100.0)
    assert depenses(BudgetView, "2026-08", "valeur").model.rowCount() == 1
    assert depenses(CategoriesView, "2026-08", "valeur").cats_model.rowCount() == 1

    # Mode « date d'opération » : tout bascule sur juillet, pour les trois.
    assert depenses(BilanView, "2026-07", "operation").kpis["depenses"]._value.text() \
        == fmt_euro(-100.0)
    assert depenses(BudgetView, "2026-07", "operation").model.rowCount() == 1
    assert depenses(CategoriesView, "2026-07", "operation").cats_model.rowCount() == 1


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


def test_bandeau_ce_qui_est_prevu(qapp, tmp_path):
    """Projection à 15 jours : les opérations déjà enregistrées dont le débit
    est à venir (encours carte) PLUS les échéances du Prévisionnel, sans
    double compte quand l'opération réelle existe déjà."""
    from comptesbudget.ui.views.bilan import BilanView

    d = Database(str(tmp_path / "prev.db"))
    d.set_setting("initial_balance", "1000")
    d.set_setting("initial_date", "2026-01-01")
    today = date.today()
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
    assert v.prev_sorties.text() == fmt_euro(-750.0)           # hors carte
    assert v.prev_entrees.text() == fmt_euro(1500.0)
    # 1000 − 200 (carte) − 750 (loyer) + 1500 (pension)
    assert v.prev_solde.text() == fmt_euro(1550.0)
    assert "débit carte" in v.prev_detail.text()


def test_bandeau_prevu_ne_compte_pas_deux_fois(qapp, tmp_path):
    """Si l'opération réelle est déjà enregistrée pour une échéance à venir,
    la récurrence correspondante ne doit pas s'y ajouter."""
    from comptesbudget.ui.views.bilan import BilanView

    d = Database(str(tmp_path / "prev2.db"))
    d.set_setting("initial_balance", "0")
    d.set_setting("initial_date", "2026-01-01")
    today = date.today()
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
    assert v.prev_sorties.text() == fmt_euro(-750.0)   # une seule fois


def test_prevu_debit_carte_ignore_les_operations_en_cours(qapp, tmp_path):
    """Le débit annoncé pour le prochain prélèvement ne compte QUE les
    opérations que la banque y a rattachées (les pointées). Un remboursement
    carte encore « en cours » ne réduit pas ce prélèvement-là : il partira au
    suivant. Sinon le montant annoncé ne correspond pas au relevé."""
    from comptesbudget.ui.views.bilan import BilanView

    d = Database(str(tmp_path / "cb-prev.db"))
    d.set_setting("initial_balance", "0")
    d.set_setting("initial_date", "2026-01-01")
    today = date.today()
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
    assert "débit carte " + fmt_euro(-120.00) in v.prev_detail.text()
    assert "au prélèvement suivant" in v.prev_detail.text()
    assert v.prev_solde.text() == fmt_euro(-120.00)
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

    cible = date.today() + timedelta(days=3)      # dans la fenêtre des 15 jours
    db.insert_recurring({"id": "rec-test", "libelle": "ASSURANCE TEST",
                         "montant": -123.45, "categorie": "Assurances",
                         "sous_cat": "", "type": "Prelevement",
                         "frequency": "monthly", "day_of_month": cible.day,
                         "start_date": cible.isoformat(), "end_date": None,
                         "actif": 1})

    bilan = BilanView(db)
    bilan.refresh()
    avant = bilan.prev_sorties.text()
    assert "123,45" in avant                       # la récurrence est bien prévue

    prev = PrevisionnelView(db)
    mois = cible.isoformat()[:7]
    a_creer = [e for e in prev._echeances(mois) if not e["_deja"]]
    assert prev._creer_operations(a_creer) == len(a_creer)

    bilan.refresh()
    assert bilan.prev_sorties.text() == avant      # inchangé : pas de doublon


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


def test_bilan_ne_recompte_pas_une_echeance_deja_encaissee(qapp, tmp_path):
    """Défaut corrigé en 1.21 : une pension versée le 7 sous le libellé de la
    banque était re-annoncée comme « à venir » parce que la récurrence la
    plaçait le 9 sous un libellé légèrement différent."""
    from comptesbudget.ui.views.bilan import BilanView

    d = Database(str(tmp_path / "double.db"))
    d.set_setting("initial_balance", "0")
    d.set_setting("initial_date", "2026-01-01")

    today = date.today()
    # Versement déjà encaissé il y a peu, libellé « à la banque »
    deja = today.replace(day=1)
    d.insert_tx(_tx(id="pension", date=deja.isoformat(),
                    date_valeur=deja.isoformat(), libelle="CAISSE RETRAITE 12",
                    type="Virement", categorie="Revenus",
                    montant=900.00, pointee=1))
    # La récurrence le place quelques jours plus tard, sous son nom à lui
    plus_tard = deja + timedelta(days=8)
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
    assert vue.prev_entrees.text() == fmt_euro(0)
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
