"""Impression du Bilan avec ses graphiques (plan du 15/10/2026, avancé à la
sortie du 01/11/2026).

La feuille reprend le Bilan de la période choisie, bloc par bloc (tuiles,
bandeaux, graphiques, listes), toujours en couleurs claires, comme le papier,
même quand l'écran est en mode sombre — sans changer l'écran.
"""
import pytest
from PySide6.QtGui import QColor

from comptesbudget import theme
from comptesbudget.database import Database


def _op(i, d, montant, categorie="Alimentation", libelle="ACHAT"):
    return {"id": f"op{i}", "date": d, "date_valeur": d, "libelle": libelle,
            "libelle_op": "", "reference": "", "type": "Prelevement",
            "categorie": categorie, "sous_cat": "", "info": "",
            "montant": montant, "pointee": 1}


@pytest.fixture
def fenetre(qapp, tmp_path):
    from comptesbudget.ui.main_window import MainWindow
    db = Database(str(tmp_path / "t.db"))
    db.set_solde_initial(1000.0, "2026-01-01")
    for i, (d, m, c) in enumerate((
            ("2026-01-02", 2000.0, "Salaire"), ("2026-01-10", -300.0, "Logement"),
            ("2026-02-02", 2000.0, "Salaire"), ("2026-02-11", -80.0, "Alimentation"),
            ("2026-02-20", -40.0, "Transport"))):
        db.insert_tx(_op(i, d, m, c))
    w = MainWindow(db)
    w.bilan_view.period = "2026-02"
    w.bilan_view.refresh()
    return w


def _apercu(w):
    from comptesbudget.ui.impression import ApercuBilan
    return ApercuBilan(w, w.db, w.bilan_view)


def test_la_feuille_reprend_les_blocs_du_bilan(fenetre):
    apercu = _apercu(fenetre)
    texte = apercu.browser.toPlainText()
    assert "Bilan" in texte and "Février 2026" in texte
    # Tuiles, bandeau du mois, deux graphiques, courbe du solde, listes.
    assert len(apercu.images) >= 5
    for image in apercu.images:
        assert not image.isNull() and image.width() > 300


def test_clair_meme_en_mode_sombre(qapp, fenetre):
    from comptesbudget.app import appliquer_theme, appliquer_theme_clair
    theme.choisir_theme("sombre")
    appliquer_theme(qapp)
    try:
        apercu = _apercu(fenetre)
        # Autour des blocs, le blanc du papier, et des cartes claires…
        image = apercu.images[0]
        assert image.pixelColor(2, 2).name().upper() == "#FFFFFF"
        milieu = image.pixelColor(image.width() // 8, image.height() // 2)
        assert milieu.lightness() > 200, milieu.name()
        # … et l'écran garde le sien.
        assert theme.est_sombre()
        assert theme.T["fond_page"] == theme.SOMBRE["fond_page"]
        assert (qapp.palette().window().color().name().upper()
                != QColor(theme.CLAIR["fond_page"]).name().upper())
    finally:
        theme.choisir_theme("clair")
        appliquer_theme_clair(qapp)


def test_menu_imprimer_propose_le_bilan(fenetre):
    textes = [a.text() for a in fenetre.menu_imprimer.actions()]
    assert textes == ["📄 Rapport du mois", "📋 Opérations affichées",
                      "🏠 Bilan avec graphiques"]
