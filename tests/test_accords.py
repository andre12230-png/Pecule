"""Le module d'accord (29/09/2026) : « 1 opération », « 1 614 opérations »."""
from comptesbudget.accords import accorde, nombre, pluriel


def test_zero_et_un_restent_au_singulier():
    assert pluriel(0, "ajout") == "0 ajout"
    assert pluriel(1, "opération") == "1 opération"


def test_au_dela_de_un_le_pluriel():
    assert pluriel(2, "opération") == "2 opérations"
    assert accorde(3, "importée") == "importées"
    assert accorde(1, "importée") == "importée"


def test_pluriel_irregulier():
    assert pluriel(2, "nouveau", "nouveaux") == "2 nouveaux"
    assert accorde(2, "est", "sont") == "sont"
    assert accorde(1, "est", "sont") == "est"


def test_milliers_separes_par_une_espace():
    assert nombre(1614) == "1 614"
    assert pluriel(1614, "opération") == "1 614 opérations"
