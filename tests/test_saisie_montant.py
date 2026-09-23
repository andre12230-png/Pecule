"""Champ de montant : ce que donne une vraie frappe au clavier.

Le piège (audit du 23/09/2026) : « 1.234,56 » tapé touche par touche
enregistrait 1,23 €. Le point, traduit en virgule dès la frappe, devenait
la virgule décimale ; le « 4 » dépassait alors les deux décimales et était
refusé, puis la vraie virgule et « 56 » aussi. Même champ pour une
opération, le solde de départ, un budget, une récurrence.
"""
import pytest


@pytest.fixture
def champ(qapp):
    from PySide6.QtCore import QLocale
    from comptesbudget.ui.widgets import MontantSpinBox
    QLocale.setDefault(QLocale(QLocale.French, QLocale.France))
    sb = MontantSpinBox()
    sb.setRange(-1_000_000.0, 1_000_000.0)
    sb.setDecimals(2)
    sb.setSuffix(" €")
    return sb


def _taper(sb, texte):
    """Efface le champ puis tape `texte` touche par touche, comme au
    clavier, et valide (Entrée)."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    sb.lineEdit().selectAll()
    QTest.keyClick(sb.lineEdit(), Qt.Key_Delete)
    QTest.keyClicks(sb.lineEdit(), texte)
    sb.interpretText()
    return sb.value()


@pytest.mark.parametrize("saisie, attendu", [
    ("1.234,56", 1234.56),        # le point des milliers
    ("-1.234,56", -1234.56),
    ("1.234", 1234.0),            # trois chiffres derrière : des milliers
    ("12.5", 12.5),               # le point du pavé numérique : décimale
    ("0.99", 0.99),
    ("1234.05", 1234.05),
    ("1234,56", 1234.56),
    ("1 234,56", 1234.56),
    ("1\xa0234,56", 1234.56),     # espace insécable (copier-coller)
    ("1 234.56", 1234.56),
    ("-50", -50.0),
])
def test_frappe_au_clavier(champ, saisie, attendu):
    assert _taper(champ, saisie) == attendu
