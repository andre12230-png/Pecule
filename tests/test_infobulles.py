"""Infobulles lisibles partout (défaut vu chez l'auteur le 01/10/2026).

Deux causes, qui s'additionnaient :
- Qt dessine les infobulles avec une palette à part (QToolTip.palette()),
  prise au système : sur le PC de l'auteur, fond #3C3C3C et texte #D4D4D4,
  alors que la charte veut #FFFFDC et du noir. setPalette() de l'application
  ne la touche pas.
- une infobulle reçoit les règles de style du widget qui la montre et de ses
  parents : « QFrame#bandeauCarte QWidget { background: transparent } »
  effaçait son fond, et le texte gris clair restait sur le beige de la page.
"""
from datetime import date, timedelta

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QPushButton, QToolTip

from comptesbudget.app import appliquer_theme_clair
from comptesbudget.database import Database

BULLE = "#ffffdc"


@pytest.fixture
def bulles_de_poste_sombre(qapp):
    """Ce que Windows donnait chez l'auteur, rétabli après le test."""
    avant = QToolTip.palette()
    sombre = QPalette(avant)
    sombre.setColor(QPalette.ToolTipBase, QColor("#3C3C3C"))
    sombre.setColor(QPalette.ToolTipText, QColor("#D4D4D4"))
    QToolTip.setPalette(sombre)
    yield
    QToolTip.setPalette(avant)


def _bulle_de(qapp, widget):
    """Montre l'infobulle du widget et rend son image."""
    from PySide6.QtCore import QEvent
    # Une infobulle cachée juste avant est détruite plus tard : on la laisse
    # partir, sinon Qt réutilise une étiquette en train de disparaître.
    QToolTip.hideText()
    qapp.sendPostedEvents(None, QEvent.DeferredDelete)
    bulle = None
    for _ in range(20):
        QToolTip.showText(widget.mapToGlobal(QPoint(5, 5)), widget.toolTip(), widget)
        qapp.processEvents()
        bulle = next((w for w in qapp.topLevelWidgets()
                      if w.metaObject().className() == "QTipLabel"
                      and w.isVisible()), None)
        if bulle is not None:
            break
    assert bulle is not None, "infobulle jamais affichée"
    image = bulle.grab().toImage()
    QToolTip.hideText()
    qapp.processEvents()
    return image


def _texte_le_plus_fonce(image):
    """La composante la plus forte du pixel le plus sombre : proche de 0
    pour un texte noir."""
    plus_fonce = 255
    for x in range(image.width()):
        for y in range(image.height()):
            c = image.pixelColor(x, y)
            plus_fonce = min(plus_fonce, max(c.red(), c.green(), c.blue()))
    return plus_fonce


def _lisible(qapp, widget, nom):
    from collections import Counter
    image = _bulle_de(qapp, widget)
    # Le fond est la couleur la plus fréquente de l'image.
    fond = Counter(image.pixelColor(x, y).name()
                   for x in range(image.width())
                   for y in range(image.height())).most_common(1)[0][0]
    assert fond == BULLE, (nom, fond)
    assert _texte_le_plus_fonce(image) <= 60, nom


def test_palette_des_infobulles_suit_la_charte(qapp, bulles_de_poste_sombre):
    appliquer_theme_clair(qapp)
    pal = QToolTip.palette()
    assert pal.color(QPalette.ToolTipBase).name() == BULLE
    assert pal.color(QPalette.ToolTipText).name() == "#000000"


def test_infobulle_d_un_bouton(qapp, bulles_de_poste_sombre):
    appliquer_theme_clair(qapp)
    b = QPushButton("Essai")
    b.setToolTip("Une infobulle ordinaire")
    b.show()
    _lisible(qapp, b, "bouton")
    b.close(); b.deleteLater()


def test_infobulles_des_bandeaux_du_bilan(qapp, tmp_path, bulles_de_poste_sombre):
    from comptesbudget.ui.views.bilan import BilanView
    from comptesbudget.utils import date_debit_differe
    appliquer_theme_clair(qapp)
    d = Database(str(tmp_path / "bulles.db"))
    d.set_setting("initial_balance", "1000")
    d.set_setting("initial_date", "2020-01-01")
    jour = date.today().isoformat()
    # Un achat par carte à débit différé (bandeau Encours carte) et une
    # échéance à venir (bandeau du mois).
    d.insert_tx({"id": "cb", "date": jour, "date_valeur": date_debit_differe(jour),
                 "libelle": "Achat", "libelle_op": "ACHAT", "reference": "",
                 "type": "Carte bancaire", "categorie": "Alimentation",
                 "sous_cat": "", "info": "", "montant": -200.0, "pointee": 0})
    d.insert_tx({"id": "edf", "date": jour, "date_valeur": jour,
                 "libelle": "EDF", "libelle_op": "EDF", "reference": "",
                 "type": "Prelevement", "categorie": "Logement - maison",
                 "sous_cat": "", "info": "", "montant": -80.0, "pointee": 0})
    vue = BilanView(d)
    vue.resize(1200, 900)
    vue.show()
    vue.refresh()
    qapp.processEvents()
    for nom in ("cb_banner", "cb_bloc1", "cb_bloc2", "mois_banner"):
        widget = getattr(vue, nom)
        assert widget.toolTip(), nom
        _lisible(qapp, widget, nom)
    vue.close()


def test_toutes_les_infobulles_de_la_fenetre(qapp, tmp_path, bulles_de_poste_sombre):
    """Chaque widget de la fenêtre qui porte une infobulle, onglet par
    onglet : fond jaune pâle et texte noir, quelles que soient les règles de
    style de ses parents."""
    from PySide6.QtWidgets import QWidget
    from comptesbudget.ui.main_window import MainWindow
    appliquer_theme_clair(qapp)
    d = Database(str(tmp_path / "fenetre.db"))
    d.set_setting("initial_balance", "1000")
    d.set_setting("initial_date", "2020-01-01")
    jour = date.today().isoformat()
    d.insert_tx({"id": "edf", "date": jour, "date_valeur": jour,
                 "libelle": "EDF", "libelle_op": "EDF", "reference": "",
                 "type": "Prelevement", "categorie": "Logement - maison",
                 "sous_cat": "", "info": "", "montant": -80.0, "pointee": 0})
    w = MainWindow(d)
    w.resize(1280, 800)
    w.show()
    vus, fautes = 0, []
    for i in range(w.tabs.count()):
        w.tabs.setCurrentIndex(i)
        qapp.processEvents()
        for widget in [w] + w.findChildren(QWidget):
            try:
                if not widget.toolTip() or not widget.isVisible():
                    continue
            except RuntimeError:
                continue      # recréé entre-temps par un rafraîchissement
            vus += 1
            try:
                _lisible(qapp, widget, widget.metaObject().className())
            except AssertionError as e:
                fautes.append(f"{widget.metaObject().className()} "
                              f"« {widget.toolTip()[:40]} » : {e}")
    w.close()
    assert vus > 20                   # le test a bien trouvé des infobulles
    assert not fautes, "\n".join(sorted(set(fautes)))
