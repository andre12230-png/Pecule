"""Plus de boîtes « Oui / Non » (charte, audit du 08/10/2026).

Un bouton dit l'action (« Supprimer le compte »), l'autre ce qu'on garde ;
widgets.confirmer() le fait. Six boîtes posaient encore leur question en
Oui / Non. Le test lit le code de l'interface.
"""
from pathlib import Path

from comptesbudget.ui.widgets import boite_de_confirmation

UI = Path(__file__).resolve().parent.parent / "comptesbudget" / "ui"


def test_aucune_boite_oui_non():
    fautes = []
    for p in UI.rglob("*.py"):
        for i, ligne in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if "QMessageBox.Yes" in ligne and not ligne.strip().startswith("#"):
                fautes.append(f"{p.name}:{i}")
    assert not fautes, fautes


def test_action_par_defaut_quand_elle_se_defait(qapp):
    """Supprimer une opération s'annule d'un clic : l'action reste le
    bouton par défaut (choix existant). Ailleurs, c'est « garder »."""
    boite, action = boite_de_confirmation(None, "T", "Q ?", "Supprimer",
                                          action_par_defaut=True)
    assert boite.defaultButton() is action
    boite, action = boite_de_confirmation(None, "T", "Q ?", "Supprimer")
    assert boite.defaultButton() is not action
