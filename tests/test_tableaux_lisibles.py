"""Tableaux lisibles : catégories et chiffres (relecture du 30/09/2026).

1. Les noms de catégories étaient écrits dans la couleur de leur catégorie :
   13 couleurs sur 17 passaient sous le contraste minimal de 4,5 pour 1
   (« Virements internes » 1,78 sur blanc, « Shopping » 2,41). Le nom s'écrit
   désormais lisiblement, et la couleur passe sur une pastille posée devant.
2. À 1280 px de large, des colonnes de chiffres étaient plus étroites que leur
   contenu : total coupé dans Catégories (« -16 »), date de valeur réduite à
   « ⏱ … » dans Opérations et Recherche, fourchette coupée dans Pré-remplir.
   Une colonne de montant ou de date prend désormais la largeur de son
   contenu ; c'est le libellé qui cède la place.

Les largeurs se comparent ici au contenu, jamais à un nombre de pixels : sous
QT_QPA_PLATFORM=offscreen, les polices ne sont pas celles de Windows.
"""
from datetime import date, timedelta

import pytest
from PySide6.QtCore import Qt

from comptesbudget.constants import CATEGORY_COLORS
from comptesbudget.database import Database
from comptesbudget.utils import date_debit_differe

# Fond le plus sombre d'une ligne de tableau (une ligne sur deux).
FOND_LIGNE_ALTERNEE = "#F5F5F0"


def _luminance(hexa: str) -> float:
    def canal(v: int) -> float:
        x = v / 255
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hexa[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b)


def _contraste(a: str, b: str) -> float:
    la, lb = _luminance(a), _luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _tx(**kw):
    base = {"id": "x", "date": "2026-06-01", "date_valeur": "2026-06-01",
            "libelle": "OP", "libelle_op": "OP", "reference": "", "type": "",
            "categorie": "Non classé", "sous_cat": "", "info": "",
            "montant": -10.0, "pointee": 1}
    base.update(kw)
    return base


@pytest.fixture
def db(tmp_path):
    """Une opération par catégorie livrée, chaque mois depuis quatre mois (de
    quoi nourrir la détection des récurrences), dont un achat carte à débit
    différé pour la colonne « Date valeur »."""
    d = Database(str(tmp_path / "lisible.db"))
    d.set_setting("initial_balance", "1000")
    d.set_setting("initial_date", "2020-01-01")
    aujourdhui = date.today()
    n = 0
    for recul in range(4):
        jour = (aujourdhui.replace(day=1) - timedelta(days=31 * recul)).replace(day=3)
        for cat in CATEGORY_COLORS:
            n += 1
            montant = 1234.56 if cat == "Revenus" else -1234.56
            d.insert_tx(_tx(id=f"t{n}", date=jour.isoformat(),
                            date_valeur=jour.isoformat(),
                            libelle=f"Commerce {cat}", libelle_op=f"COMMERCE {cat}",
                            type="Prélèvement", categorie=cat,
                            sous_cat=f"Détail {cat}", montant=montant))
    achat = aujourdhui.replace(day=2).isoformat()
    d.insert_tx(_tx(id="carte", date=achat, date_valeur=date_debit_differe(achat),
                    libelle="Achat carte", type="Carte bancaire",
                    categorie="Shopping", montant=-45.30, pointee=0))
    d.insert_recurring({"id": "rec1", "libelle": "Abonnement", "montant": -9.99,
                        "categorie": "Shopping", "sous_cat": "", "type": "Prélèvement",
                        "frequency": "monthly", "day_of_month": 5,
                        "start_date": "2026-01-05", "end_date": None, "actif": 1})
    for cat in CATEGORY_COLORS:
        d.set_budget(cat, 100.0)
    return d


def _tables(widget):
    from PySide6.QtWidgets import QTableView
    return widget.findChildren(QTableView)


def _cellules_de_categorie(widget):
    """(tableau, cellule) de chaque cellule dont le texte est un nom de
    catégorie, dans tous les tableaux du widget."""
    from PySide6.QtGui import QStandardItemModel
    for table in _tables(widget):
        modele = table.model()
        if not isinstance(modele, QStandardItemModel):
            continue
        for r in range(modele.rowCount()):
            for c in range(modele.columnCount()):
                it = modele.item(r, c)
                if it is not None and it.text() in CATEGORY_COLORS:
                    yield table, it


def _ecrans(qapp, db):
    """Chaque écran qui affiche des catégories, rempli."""
    from comptesbudget.recurring import detect_recurring_candidates
    from comptesbudget.ui.assistants import (
        DuplicatesDialog, GenererEcheancesDialog, HarmonizeDialog,
        PrefillRecurringDialog,
    )
    from comptesbudget.ui.search import GlobalSearchDialog
    from comptesbudget.ui.views.budget import BudgetView
    from comptesbudget.ui.views.categories import CategoriesView
    from comptesbudget.ui.views.operations import OperationsView
    from comptesbudget.ui.views.previsionnel import PrevisionnelView
    from comptesbudget.ui.views.subcategories import SubcategoriesView

    txs = [dict(r) for r in db.list_tx()]
    ops = OperationsView(db); ops.reload_from_db()
    budget = BudgetView(db); budget.refresh()
    cats = CategoriesView(db); cats.refresh()
    cats._show_cat("Shopping", [t for t in txs if t["categorie"] == "Shopping"])
    sous = SubcategoriesView(db); sous.refresh()
    prev = PrevisionnelView(db); prev.refresh()
    recherche = GlobalSearchDialog(None, db); recherche.edit.setText("commerce")
    return {
        "Opérations": ops, "Budget": budget, "Catégories": cats,
        "Sous-catégories": sous, "Prévisionnel": prev, "Recherche": recherche,
        "Harmoniser": HarmonizeDialog(None, [(t, "Shopping") for t in txs[:5]]),
        "Doublons": DuplicatesDialog(None, txs[:5]),
        "Pré-remplir": PrefillRecurringDialog(None, detect_recurring_candidates(txs)),
        "Échéances": GenererEcheancesDialog(None, prev._echeances,
                                            date.today().strftime("%Y-%m"),
                                            [date.today().strftime("%Y-%m")]),
    }


def test_noms_de_categorie_lisibles_avec_leur_pastille(qapp, db):
    """Chaque nom de catégorie tient 4,5 pour 1, même sur la ligne alternée,
    et garde sa couleur sous forme de pastille."""
    defauts = []
    for ecran, widget in _ecrans(qapp, db).items():
        cellules = list(_cellules_de_categorie(widget))
        assert cellules, f"{ecran} : aucune catégorie affichée, test sans objet"
        for _table, it in cellules:
            pinceau = it.foreground()
            couleur = ("#000000" if pinceau.style() == Qt.NoBrush
                       else pinceau.color().name().upper())
            ratio = _contraste(couleur, FOND_LIGNE_ALTERNEE)
            if ratio < 4.5:
                defauts.append(f"{ecran} — {it.text()} en {couleur} : {ratio:.2f}")
            if it.icon().isNull():
                defauts.append(f"{ecran} — {it.text()} sans pastille")
    assert not defauts, "\n".join(sorted(set(defauts)))


# Colonnes de chiffres et de dates, par écran : elles ne doivent jamais être
# plus étroites que ce qu'elles affichent.
COLONNES_CHIFFREES = {
    "Opérations": {"Date opér.", "Date valeur", "Débit", "Crédit"},
    "Recherche": {"Date opér.", "Date valeur", "Débit", "Crédit"},
    "Catégories": {"Nb", "Total", "Date opér.", "Date valeur", "Débit", "Crédit"},
    "Pré-remplir": {"Montant", "Fréquence", "Jour", "Nb mois", "Fourchette"},
}


def test_colonnes_de_chiffres_jamais_coupees(qapp, db):
    """À 1280 px de large (fenêtre moins le menu de gauche), aucune colonne de
    montant, de nombre ou de date n'est plus étroite que son contenu."""
    ecrans = _ecrans(qapp, db)
    largeurs = {"Opérations": 1060, "Catégories": 1060, "Recherche": 1000,
                "Pré-remplir": 900}
    defauts = []
    for ecran, colonnes in COLONNES_CHIFFREES.items():
        widget = ecrans[ecran]
        widget.resize(largeurs[ecran], 600)
        # Pas de processEvents() : il réveillerait les invites de premier
        # lancement laissées en attente par d'autres tests, qui attendent un
        # clic. On demande directement au tableau de placer ses colonnes.
        for table in _tables(widget):
            table.doItemsLayout()
        for table in _tables(widget):
            entete = table.horizontalHeader()
            modele = table.model()
            for c in range(modele.columnCount()):
                titre = modele.headerData(c, Qt.Horizontal)
                if titre not in colonnes or modele.rowCount() == 0:
                    continue
                besoin = max(table.sizeHintForColumn(c), entete.sectionSizeHint(c))
                if entete.sectionSize(c) < besoin:
                    defauts.append(f"{ecran} — {titre} : {entete.sectionSize(c)} px "
                                   f"pour {besoin} px de contenu")
    assert not defauts, "\n".join(defauts)


def test_legende_du_camembert_garde_ses_montants(qapp, db):
    """La légende de « Répartition des dépenses » porte le nom ET le montant
    de chaque catégorie. Faute de place, Qt coupait la fin, donc le montant
    (« Logement - maison — -847,… ») : elle réserve désormais la largeur de
    son libellé le plus long."""
    from PySide6.QtGui import QFontMetrics
    from comptesbudget.ui.views.bilan import BilanView

    vue = BilanView(db)
    vue.period = "all"
    vue.refresh()
    legende = vue.pie_chart.legend()
    libelles = [m.label() for m in legende.markers()]
    assert libelles, "camembert vide : test sans objet"
    le_plus_long = max(QFontMetrics(legende.font()).horizontalAdvance(t)
                       for t in libelles)
    assert legende.minimumWidth() >= le_plus_long
