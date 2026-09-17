"""Garde-fou du sens de saisie : une recette enregistrée en dépense.

Incident du 17/09/2026 : un virement reçu de 80 € saisi à la main en dépense.
Le solde du compte était alors faux de DEUX fois 80 €, sans que rien ne le
signale à la saisie.
"""
from comptesbudget.utils import alerte_sens_saisie


def test_recette_saisie_en_depense_est_signalee():
    # Le cas vécu : type « Virement recu », rangé dans Revenus, mais en débit
    msg = alerte_sens_saisie("Virement recu", "Revenus", -80.0)
    assert msg and "recette" in msg.lower()
    # Le type seul suffit, même sans la catégorie Revenus
    assert alerte_sens_saisie("Virement recu", "Non classé", -80.0)
    assert alerte_sens_saisie("Depot d'especes", "", -20.0)
    # La catégorie seule suffit aussi (type laissé vide)
    assert alerte_sens_saisie("", "Revenus", -1500.0)


def test_saisie_coherente_ne_dit_rien():
    # Les mêmes opérations dans le bon sens : aucun avertissement
    assert alerte_sens_saisie("Virement recu", "Revenus", 80.0) is None
    assert alerte_sens_saisie("", "Revenus", 1500.0) is None
    # Une dépense ordinaire
    assert alerte_sens_saisie("Carte bancaire", "Alimentation", -42.5) is None
    assert alerte_sens_saisie("Prelevement", "Abonnements", -9.99) is None


def test_cas_legitimes_laisses_tranquilles():
    """On n'avertit QUE dans le sens qui a provoqué l'incident.

    Un remboursement porte un type de dépense avec un montant positif (avoir
    sur une carte, prélèvement rejeté) : c'est courant et légitime — avertir
    là ferait crier au loup.
    """
    assert alerte_sens_saisie("Carte bancaire", "Alimentation", 42.5) is None
    assert alerte_sens_saisie("Prelevement", "Santé", 27.32) is None
    # Un virement émis (type ambigu « Virement ») reste libre dans les deux sens
    assert alerte_sens_saisie("Virement", "Virements internes", -250.0) is None
    assert alerte_sens_saisie("Virement", "Virements internes", 250.0) is None
    # Une opération sortie du calcul du solde n'a pas de sens à respecter
    assert alerte_sens_saisie("Virement recu", "Transaction exclue", -80.0) is None
    # Montant nul : le formulaire a son propre contrôle, rien à dire ici
    assert alerte_sens_saisie("Virement recu", "Revenus", 0.0) is None


def test_le_formulaire_demande_confirmation(qapp, monkeypatch):
    """Le formulaire ne se ferme pas tant que la question n'a pas reçu « Oui ».

    Reproduit la saisie du 17/09/2026 : virement reçu de 80 €, sens « Débit ».
    """
    from PySide6.QtWidgets import QMessageBox
    from comptesbudget.ui.dialogs import TxDialog

    dlg = TxDialog(None, None, ["Revenus"], [])
    dlg.libelle.setText("CABINET MARTIN CONSEIL")
    dlg.type_combo.setCurrentText("Virement recu")
    dlg.cat.setCurrentText("Revenus")
    dlg.montant.setValue(80.0)
    dlg.rb_debit.setChecked(True)

    posees = []

    def _question(parent, titre, texte, *a, **kw):
        posees.append(texte)
        return QMessageBox.No

    monkeypatch.setattr(QMessageBox, "question", staticmethod(_question))
    dlg._validate_and_accept()
    assert posees, "aucune question posée sur le sens de l'opération"
    assert dlg.result() == 0, "le formulaire s'est fermé malgré le « Non »"

    # Le même enregistrement en recette part sans rien demander.
    posees.clear()
    dlg.rb_credit.setChecked(True)
    dlg._validate_and_accept()
    assert not posees
    assert dlg.values()["montant"] == 80.0
