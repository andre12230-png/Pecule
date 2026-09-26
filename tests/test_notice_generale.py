"""La notice parle à tous les utilisateurs, pas du seul compte de l'auteur.

Lot « autres utilisateurs » (26/09/2026) : la notice présentait comme une
règle générale le calendrier d'un compte précis (lot carte le 4 ou le 5,
pensions le 7 et le 9), des libellés d'une banque en ligne, et un « seul
compte par base » périmé depuis le multicomptes.
"""
from comptesbudget.ui.views.notice import GLOSSAIRE_HTML, NOTICE_HTML

TEXTE = NOTICE_HTML + GLOSSAIRE_HTML


def test_pas_de_calendrier_personnel():
    assert "le 7 et le 9" not in TEXTE
    assert "le 4 ou le 5" not in TEXTE


def test_le_glossaire_ne_contredit_pas_le_code():
    # Le code propose le 4 : le glossaire ne doit pas annoncer le 5 ou le 6.
    assert "5 ou le 6" not in TEXTE


def test_pas_de_libelle_d_une_banque_presente_comme_universel():
    assert "débit différé au 4" not in TEXTE
    assert "opérations prévues prochainement" not in TEXTE


def test_le_multicomptes_n_est_plus_nie():
    assert "un seul compte par fichier" not in TEXTE
