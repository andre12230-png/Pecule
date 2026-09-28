"""« Annuler » après une suppression dans la liste des Opérations.

Avant, une suppression confirmée par erreur ne se rattrapait qu'en
reprenant une sauvegarde : tout le travail fait depuis était perdu."""
from PySide6.QtWidgets import QMessageBox

from comptesbudget.database import Database


def _tx(**kw):
    base = {"id": "x", "date": "2026-06-01", "date_valeur": "2026-06-03",
            "libelle": "OP", "libelle_op": "OP", "reference": "REF-1",
            "type": "Carte bancaire", "categorie": "Loisirs", "sous_cat": "Cinéma",
            "info": "une note", "montant": -12.5, "pointee": 1}
    base.update(kw)
    return base


def _base(tmp_path):
    db = Database(str(tmp_path / "annuler.db"))
    db.set_setting("initial_balance", "0")
    for i in range(3):
        db.insert_tx(_tx(id=f"a{i}", date=f"2026-06-0{i + 1}"))
    return db


def _ligne(db, tx_id):
    return next((dict(t) for t in db.list_tx() if dict(t)["id"] == tx_id), None)


def test_restaurer_rend_l_operation_telle_quelle(tmp_path):
    """Tous les champs reviennent, et la trace de la suppression (gardée
    pour la fusion des exports JSON) est effacée : sinon une fusion
    supprimerait de nouveau l'opération."""
    db = _base(tmp_path)
    avant = _ligne(db, "a0")
    db.delete_tx("a0")
    assert ("transactions", "a0") in db.deletion_map()

    db.restaurer_tx([avant])
    apres = _ligne(db, "a0")
    for champ in ("date", "date_valeur", "libelle", "reference", "type",
                  "categorie", "sous_cat", "info", "montant", "pointee",
                  "compte_id"):
        assert apres[champ] == avant[champ], champ
    assert ("transactions", "a0") not in db.deletion_map()


def test_bandeau_annuler_apres_suppression(qapp, tmp_path, monkeypatch):
    from comptesbudget.ui.views.operations import OperationsView

    db = _base(tmp_path)
    vue = OperationsView(db)
    vue.period = "all"
    vue.reload_from_db()
    assert not vue.bandeau_annuler.isVisibleTo(vue)

    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.Yes)
    from PySide6.QtCore import QItemSelectionModel
    vue.table.selectRow(0)
    vue.table.selectionModel().select(
        vue.model.index(1, 0),
        QItemSelectionModel.Select | QItemSelectionModel.Rows)
    vue.delete_selected()
    assert len(db.list_tx()) == 1
    assert vue.bandeau_annuler.isVisibleTo(vue)
    assert "2 opérations supprimées" in vue.lbl_annuler.text()

    vue.annuler_suppression()
    assert len(db.list_tx()) == 3
    assert not vue.bandeau_annuler.isVisibleTo(vue)


def test_le_bandeau_disparait_en_changeant_de_compte(qapp, tmp_path, monkeypatch):
    """Sur un autre compte, « Annuler » ne voudrait plus rien dire à l'écran."""
    from comptesbudget.ui.views.operations import OperationsView

    db = _base(tmp_path)
    vue = OperationsView(db)
    vue.period = "all"
    vue.reload_from_db()
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.Yes)
    vue.table.selectRow(0)
    vue.delete_selected()
    assert vue.bandeau_annuler.isVisibleTo(vue)

    db.set_compte_courant(db.add_compte("Second compte"))
    vue.reload_from_db()
    assert not vue.bandeau_annuler.isVisibleTo(vue)


def test_le_bandeau_reste_apres_un_rafraichissement(qapp, tmp_path, monkeypatch):
    """La fenêtre rafraîchit tous les onglets après chaque suppression : le
    bandeau ne doit pas disparaître aussitôt apparu."""
    from comptesbudget.ui.views.operations import OperationsView

    db = _base(tmp_path)
    vue = OperationsView(db)
    vue.period = "all"
    vue.reload_from_db()
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.Yes)
    vue.table.selectRow(0)
    vue.delete_selected()
    vue.reload_from_db()
    assert vue.bandeau_annuler.isVisibleTo(vue)
