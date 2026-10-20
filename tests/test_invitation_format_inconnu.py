"""Relevé CSV non reconnu : la boîte d'import invite à envoyer la forme du
fichier (20/10/2026).

Un utilisateur dont l'import échoue écrit rarement : il désinstalle. La boîte
« Import incomplet » lui propose donc d'envoyer, par « 💬 Votre avis », le nom
de sa banque et la ligne des titres de colonnes — jamais un montant.

Fichiers fabriqués, valeurs inventées.

    py -m pytest tests/test_invitation_format_inconnu.py
"""
import pytest

from comptesbudget.database import Database


def _messages(qapp, tmp_path, monkeypatch, nom, contenu: str):
    """Importe un fichier fabriqué et renvoie le texte des boîtes affichées."""
    from PySide6.QtWidgets import QMessageBox

    from comptesbudget.ui import main_window
    vus = []
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda parent, titre, texte, *a, **k: vus.append(texte))
    monkeypatch.setattr(QMessageBox, "information",
                        lambda parent, titre, texte, *a, **k: vus.append(texte))
    # Un import réussi pose ensuite des questions (solde du relevé, date de
    # départ) : on les referme, sinon le test attend une réponse.
    monkeypatch.setattr(main_window.MainWindow, "_demander_solde_releve",
                        lambda self, *a: None)
    monkeypatch.setattr(main_window.MainWindow, "_demander_recul_depart",
                        lambda self, *a: "rien")
    db = Database(str(tmp_path / "t.db"))
    fenetre = main_window.MainWindow(db)
    p = tmp_path / nom
    p.write_bytes(contenu.encode("utf-8"))
    fenetre._import_files([str(p)])
    return "\n".join(vus)


@pytest.mark.parametrize("contenu", [
    # Séparateur virgule : en-tête introuvable, l'import lève une erreur.
    "Date,Description,Amount\n05/09/2026,LOYER,-650.00\n",
    # Dates « année d'abord » : toutes les lignes sont écartées.
    "Date;Libelle;Montant\n2026-09-05;LOYER;-650,00\n",
])
def test_csv_non_reconnu_invite_a_envoyer_les_titres(
        qapp, tmp_path, monkeypatch, contenu):
    texte = _messages(qapp, tmp_path, monkeypatch, "releve.csv", contenu)
    assert "Votre avis" in texte, texte
    assert "titres des colonnes" in texte, texte


def test_import_reussi_sans_invitation(qapp, tmp_path, monkeypatch):
    texte = _messages(qapp, tmp_path, monkeypatch, "releve.csv",
                      "Date;Libelle;Montant\n05/09/2026;LOYER;-650,00\n")
    assert "titres des colonnes" not in texte, texte
