"""Tests du rapport mensuel (génération HTML)."""
from comptesbudget.database import Database
from comptesbudget.ui.report import build_monthly_report_html


def _tx(**kw):
    """Transaction complète avec des valeurs par défaut surchargées par kw."""
    base = {
        "id": "t1", "date": "2026-05-03", "date_valeur": "2026-05-03",
        "libelle": "ACHAT", "libelle_op": "ACHAT", "reference": "",
        "type": "Carte bancaire", "categorie": "Shopping", "sous_cat": "",
        "info": "", "montant": -10.0, "pointee": 0,
    }
    base.update(kw)
    return base


def test_rapport_echappe_les_caracteres_html(tmp_path):
    # Régression : un libellé ou une catégorie contenant « & » ou « < »
    # (ex. « B&C ») était inséré tel quel dans le HTML du rapport.
    db = Database(str(tmp_path / "t.db"))
    db.insert_tx(_tx(id="t1", libelle="B&C <Paris>", categorie="Vet & Mode"))
    html = build_monthly_report_html(db, "2026-05")
    assert "B&amp;C &lt;Paris&gt;" in html
    assert "<Paris>" not in html
    assert "Vet &amp; Mode" in html


def test_rapport_contient_les_indicateurs(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.insert_tx(_tx(id="a", montant=-45.30))
    db.insert_tx(_tx(id="b", libelle="SALAIRE", libelle_op="SALAIRE",
                     categorie="Revenus", montant=2000.0))
    html = build_monthly_report_html(db, "2026-05")
    assert "Rapport Mai 2026" in html
    assert "Revenus" in html
    assert "Plus grosses dépenses" in html
