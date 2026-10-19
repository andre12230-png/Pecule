"""Impression de la liste des opérations (demande d'un utilisateur, 19/10/2026).

Il voulait imprimer ses opérations « par année, par mois, ou bien les
opérations non pointées ». L'écran Opérations sait déjà les choisir (période
en haut, filtre « Pointage ») : l'impression reprend exactement ce qu'il
affiche, dans le même ordre, et dit sur la feuille quels critères ont servi.
"""
import pytest

from comptesbudget.database import Database


def _op(i, d, montant, pointee=0, libelle="ACHAT", categorie="Alimentation"):
    return {"id": f"op{i}", "date": d, "date_valeur": d, "libelle": libelle,
            "libelle_op": "", "reference": "", "type": "Prelevement",
            "categorie": categorie, "sous_cat": "", "info": "",
            "montant": montant, "pointee": pointee}


@pytest.fixture
def fenetre(qapp, tmp_path):
    """Fenêtre principale sur une base inventée de cinq opérations."""
    from comptesbudget.ui.main_window import MainWindow
    db = Database(str(tmp_path / "t.db"))
    db.set_solde_initial(0.0, "2024-01-01")
    for op in (_op(1, "2025-12-20", -40.0, pointee=1),
               _op(2, "2026-01-10", -25.0, pointee=1),
               _op(3, "2026-02-05", 1000.0, pointee=1, libelle="SALAIRE",
                   categorie="Salaire"),
               _op(4, "2026-02-12", -60.0, libelle="B&C"),
               _op(5, "2025-07-03", -15.0)):
        db.insert_tx(op)
    w = MainWindow(db)
    w.ops_view.reload_from_db()
    return w


def _apercu(w):
    from comptesbudget.ui.impression import ApercuOperations
    return ApercuOperations(w, w.db, w.ops_view)


def _texte(w):
    return _apercu(w).browser.toPlainText()


def test_par_annee(fenetre):
    fenetre.ops_view.period = "2026"
    fenetre.ops_view.refresh()
    texte = _texte(fenetre)
    assert "Année 2026" in texte
    assert "SALAIRE" in texte and "B&C" in texte
    assert "20/12/2025" not in texte and "03/07/2025" not in texte
    assert "3 opérations" in texte


def test_par_mois(fenetre):
    fenetre.ops_view.period = "2026-02"
    fenetre.ops_view.refresh()
    texte = _texte(fenetre)
    assert "Février 2026" in texte
    assert "05/02/2026" in texte and "12/02/2026" in texte
    assert "10/01/2026" not in texte


def test_non_pointees_sur_toute_la_periode(fenetre):
    """Comme à l'écran : « Non pointées » ne s'arrête pas au mois affiché."""
    vue = fenetre.ops_view
    vue.period = "2026-02"
    vue.pt_filter.setCurrentText("Non pointées")
    texte = _texte(fenetre)
    assert "Non pointées" in texte
    assert "Toute la période" in texte
    assert "B&C" in texte and "03/07/2025" in texte
    assert "SALAIRE" not in texte
    assert "2 opérations" in texte


def test_ordre_de_l_ecran_et_signes(fenetre):
    """Même ordre que le tableau ; un débit garde son signe « - » et une
    opération pointée sa coche : rien ne repose sur la couleur seule, pour
    les imprimantes noir et blanc."""
    from comptesbudget.ui.impression import lignes_affichees
    vue = fenetre.ops_view
    vue.period = "all"
    vue.refresh()
    dates = [t["date"] for t in lignes_affichees(vue)]
    assert dates == sorted(dates, reverse=True)
    # L'aperçu rend les espaces insécables en espaces ordinaires.
    texte = _texte(fenetre).replace("\xa0", " ")
    assert "-60,00" in texte
    assert "✔" in texte
    # Totaux du bas : débits, crédits et mouvement.
    assert "-140,00" in texte          # 40 + 25 + 60 + 15
    assert "+1 000,00" in texte
    assert "+860,00" in texte


def test_html_echappe_les_libelles():
    """« B&C » ne doit pas casser la mise en page."""
    from comptesbudget.ui.impression import html_operations
    html = html_operations([_op(1, "2026-01-01", -5.0, libelle="B&C <x>")],
                           ["Période : Janvier 2026"], "operation")
    assert "B&amp;C &lt;x&gt;" in html


def test_menu_imprimer_propose_les_deux_impressions(fenetre):
    textes = [a.text() for a in fenetre.menu_imprimer.actions()]
    assert textes == ["📄 Rapport du mois", "📋 Opérations affichées"]
    assert fenetre.btn_imprimer.text() == "🖨 Imprimer…"


def test_rien_a_imprimer(fenetre, monkeypatch):
    """Aucune opération affichée : un message, pas une feuille vide."""
    from PySide6.QtWidgets import QMessageBox
    vu = []
    monkeypatch.setattr(QMessageBox, "information",
                        lambda *a, **k: vu.append(a[2]))
    vue = fenetre.ops_view
    vue.period = "2026"
    vue.search.setText("introuvable")
    fenetre.action_imprimer_operations()
    assert vu and "Aucune opération" in vu[0]
