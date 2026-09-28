"""Export des opérations affichées vers un fichier CSV lisible par Excel."""
import csv

from comptesbudget.export_csv import ecrire_csv_operations


def _lire(chemin):
    with open(chemin, encoding="utf-8-sig", newline="") as f:
        return list(csv.reader(f, delimiter=";"))


def _op(**kw):
    base = {"id": "x", "date": "2026-06-05", "date_valeur": "2026-06-07",
            "libelle": "MAGASIN", "categorie": "Alimentation", "sous_cat": "",
            "type": "Carte bancaire", "reference": "", "info": "",
            "montant": -45.3, "pointee": 1}
    base.update(kw)
    return base


def test_colonnes_et_montants_a_la_francaise(tmp_path):
    """Dates JJ/MM/AAAA et virgule décimale, sans espace ni « € » : Excel
    reconnaît ainsi des dates et des nombres qu'on peut additionner."""
    chemin = tmp_path / "ops.csv"
    n = ecrire_csv_operations(str(chemin), [
        _op(),
        _op(id="y", libelle="SALAIRE", categorie="Revenus", type="Virement recu",
            montant=1234.5, pointee=0, date_valeur=""),
    ])
    assert n == 2
    lignes = _lire(chemin)
    assert lignes[0] == ["Date opération", "Date valeur", "Libellé", "Catégorie",
                         "Sous-catégorie", "Type", "Référence", "Note",
                         "Débit", "Crédit", "Pointée"]
    assert lignes[1] == ["05/06/2026", "07/06/2026", "MAGASIN", "Alimentation",
                         "", "Carte bancaire", "", "", "-45,30", "", "oui"]
    # Sans date de valeur, on reprend la date d'opération, comme à l'écran.
    assert lignes[2][1] == "05/06/2026"
    assert lignes[2][8:] == ["", "1234,50", "non"]


def test_accents_et_point_virgule_dans_un_libelle(tmp_path):
    """Le fichier commence par la marque UTF-8 qu'Excel attend pour lire les
    accents ; un « ; » dans un libellé ne décale pas les colonnes."""
    chemin = tmp_path / "ops.csv"
    ecrire_csv_operations(str(chemin), [_op(libelle="CAFÉ ; TERRASSE")])
    assert chemin.read_bytes().startswith(b"\xef\xbb\xbf")
    assert _lire(chemin)[1][2] == "CAFÉ ; TERRASSE"


def test_un_libelle_ne_devient_pas_une_formule(tmp_path):
    """Un texte commençant par « = », « + », « - » ou « @ » serait exécuté
    comme une formule par Excel : il est précédé d'une apostrophe."""
    chemin = tmp_path / "ops.csv"
    ecrire_csv_operations(str(chemin), [_op(libelle="=1+1", info="@note")])
    ligne = _lire(chemin)[1]
    assert ligne[2] == "'=1+1"
    assert ligne[7] == "'@note"


def test_liste_vide(tmp_path):
    chemin = tmp_path / "ops.csv"
    assert ecrire_csv_operations(str(chemin), []) == 0
    assert len(_lire(chemin)) == 1  # la ligne d'en-tête seule


def test_l_ecran_exporte_ce_qu_il_affiche(qapp, tmp_path, monkeypatch):
    """Le bouton « Exporter » reprend les lignes visibles — filtre et ordre
    du tableau compris — et rien d'autre."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    from comptesbudget.database import Database
    from comptesbudget.ui.views.operations import OperationsView

    db = Database(str(tmp_path / "export.db"))
    for i, (lib, m) in enumerate([("BOULANGERIE", -5.0), ("SALAIRE", 2000.0),
                                  ("BOULANGERIE", -7.5)]):
        db.insert_tx(_op(id=f"e{i}", date=f"2026-06-0{i + 1}",
                         date_valeur=f"2026-06-0{i + 1}", libelle=lib,
                         libelle_op=lib, montant=m))
    vue = OperationsView(db)
    vue.period = "all"
    vue.reload_from_db()
    vue.search.setText("boulangerie")
    # Tri du plus ancien au plus récent : l'export doit suivre cet ordre.
    vue.table.sortByColumn(vue.model.COL_DATE_VALEUR, Qt.AscendingOrder)

    chemin = tmp_path / "sortie.csv"
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        lambda *a, **k: (str(chemin), ""))
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.Close)
    vue.exporter_csv()

    lignes = _lire(chemin)
    assert [l[2] for l in lignes[1:]] == ["BOULANGERIE", "BOULANGERIE"]
    assert [l[0] for l in lignes[1:]] == ["01/06/2026", "03/06/2026"]


def test_export_refuse_proprement_un_fichier_ouvert(qapp, tmp_path, monkeypatch):
    """Fichier déjà ouvert dans Excel (Windows refuse l'écriture) : un
    message en français, pas de plantage."""
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    from comptesbudget.database import Database
    from comptesbudget.ui.views import operations
    from comptesbudget.ui.views.operations import OperationsView

    db = Database(str(tmp_path / "export.db"))
    db.insert_tx(_op(libelle_op="MAGASIN"))
    vue = OperationsView(db)
    vue.period = "all"
    vue.reload_from_db()

    def refuse(*a, **k):
        raise PermissionError(13, "Permission denied")
    monkeypatch.setattr(operations, "ecrire_csv_operations", refuse)
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        lambda *a, **k: (str(tmp_path / "x.csv"), ""))
    messages = []
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda parent, titre, texte, *a: messages.append(texte))
    vue.exporter_csv()
    assert messages and "Permission denied" not in messages[0]
