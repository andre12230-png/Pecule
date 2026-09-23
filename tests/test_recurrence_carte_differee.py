"""Récurrence payée par carte à débit différé : dans les prévisions du Bilan,
elle sort au prélèvement groupé de la carte, pas le jour de l'achat.

Incident du 23/09/2026 : un abonnement payé chaque 1er du mois par une carte
à débit différé était retranché du solde le 01/10, comme un prélèvement. Or
l'achat du 01/10 ne part qu'avec le lot carte de début novembre ; celui du
01/09 était déjà compté dans le lot du 05/10. Le point le plus bas du bandeau
« négatif… Au plus bas » était ainsi trop bas du montant de l'abonnement.

Sur une carte à débit IMMÉDIAT (beaucoup de comptes), rien ne change : l'achat
sort le jour même.
"""
from datetime import date, timedelta

from comptesbudget.database import Database


def _mois_suivant(d: date, n: int = 1) -> date:
    """Le 1er du n-ième mois après celui de `d`."""
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


def _base(tmp_path, differe: bool, type_rec: str = "Carte bancaire"):
    db = Database(str(tmp_path / "t.db"))
    db.set_solde_initial(1000.0, "2026-01-01")
    # Un ancien achat carte : sa date de valeur dit si la carte est à débit
    # différé (valeur au 4 du mois suivant) ou immédiat (même jour).
    db.insert_tx({
        "id": "ancien", "date": "2026-01-10",
        "date_valeur": "2026-02-04" if differe else "2026-01-10",
        "libelle": "BOULANGERIE", "libelle_op": "", "reference": "",
        "type": "Carte bancaire", "categorie": "Alimentation", "sous_cat": "",
        "info": "", "montant": -5.0, "pointee": 1})
    db.insert_recurring({
        "id": "abo", "libelle": "ABONNEMENT", "montant": -20.0,
        "categorie": "Abonnements", "sous_cat": "", "type": type_rec,
        "frequency": "monthly", "day_of_month": 1,
        "start_date": date.today().replace(day=1).isoformat(),
        "end_date": None, "actif": 1})
    return db


def _lignes_abonnement(db, depuis, jusqua):
    from comptesbudget.ui.views.bilan import BilanView
    vue = BilanView(db)
    txs = [dict(t) for t in db.list_tx()]
    lignes, _ = vue._lignes_a_venir(txs, depuis, jusqua)
    return sorted((d, m, carte) for d, lib, m, carte in lignes
                  if lib == "ABONNEMENT")


def test_carte_differee_sort_au_prelevement_du_lot(qapp, tmp_path):
    db = _base(tmp_path, differe=True)
    mois = _mois_suivant(date.today(), 2)
    # Dans ce mois, seul l'achat du mois PRÉCÉDENT est débité (le 4) ;
    # l'achat du 1er partira le mois suivant.
    assert _lignes_abonnement(db, mois, mois.replace(day=28)) == [
        (mois.replace(day=4).isoformat(), -20.0, True)]


def test_carte_differee_achat_du_jour_pas_encore_debite(qapp, tmp_path):
    # Une fenêtre qui s'arrête le 3 : l'achat du 1er est fait, mais rien
    # n'est encore sorti du compte.
    db = _base(tmp_path, differe=True)
    mois = _mois_suivant(date.today(), 2)
    assert _lignes_abonnement(db, mois, mois.replace(day=3)) == []


def test_carte_immediate_inchangee(qapp, tmp_path):
    db = _base(tmp_path, differe=False)
    mois = _mois_suivant(date.today(), 2)
    assert _lignes_abonnement(db, mois, mois.replace(day=28)) == [
        (mois.isoformat(), -20.0, False)]


def test_prelevement_inchange_sur_compte_differe(qapp, tmp_path):
    db = _base(tmp_path, differe=True, type_rec="Prelevement")
    mois = _mois_suivant(date.today(), 2)
    assert _lignes_abonnement(db, mois, mois.replace(day=28)) == [
        (mois.isoformat(), -20.0, False)]


def test_achat_deja_enregistre_pas_compte_deux_fois(qapp, tmp_path):
    # L'achat du mois prochain est déjà là (importé, pointé, valeur au 4 du
    # mois d'après) : l'échéance est couverte, seul l'achat réel compte.
    db = _base(tmp_path, differe=True)
    m1 = _mois_suivant(date.today(), 1)
    m2 = _mois_suivant(date.today(), 2)
    db.insert_tx({
        "id": "reel", "date": m1.isoformat(),
        "date_valeur": m2.replace(day=4).isoformat(),
        "libelle": "ABONNEMENT", "libelle_op": "", "reference": "",
        "type": "Carte bancaire", "categorie": "Abonnements", "sous_cat": "",
        "info": "", "montant": -20.0, "pointee": 1})
    assert _lignes_abonnement(db, m2, m2.replace(day=28)) == [
        (m2.replace(day=4).isoformat(), -20.0, True)]
