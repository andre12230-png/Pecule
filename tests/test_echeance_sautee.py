"""Échéance sautée : « pas ce mois-ci » (20-10-2026).

Une échéance mensuelle à montant variable (un péage) n'a rien prélevé en
octobre. L'utilisateur a supprimé sa ligne prévue dans les Opérations, mais le
Prévisionnel ne voyait plus d'opération qui la couvre : il la recréait dans ses
calculs. Le bandeau annonçait -80 € de sorties à venir au lieu de -30 €,
et la ligne fautive n'apparaissait nulle part (datée d'avant aujourd'hui, elle
était exclue des « Prochaines échéances »).

Désormais chaque récurrence retient les dates qu'elle doit sauter.
"""
import sqlite3
from datetime import date

from comptesbudget.database import Database
from comptesbudget.recurring import (
    echeances_du_mois, echeances_decouvertes, generate_occurrences,
)

AUJ = date(2026, 10, 20)


def _rec(**kw):
    base = {"id": "peage", "libelle": "PEAGE AUTOROUTE", "montant": -50.0,
            "categorie": "Transports", "sous_cat": "Péage", "type": "Prelevement",
            "frequency": "monthly", "day_of_month": 15,
            "start_date": "2026-08-15", "end_date": None, "actif": 1}
    base.update(kw)
    return base


def _tx(**kw):
    base = {"id": "t1", "date": "2026-10-15", "date_valeur": "2026-10-15",
            "libelle": "PEAGE AUTOROUTE", "libelle_op": "PEAGE AUTOROUTE",
            "reference": "", "type": "Prelevement", "categorie": "Transports",
            "sous_cat": "Péage", "info": "", "montant": -50.0, "pointee": 0,
            "prevue": 1}
    base.update(kw)
    return base


# ── Le calcul ────────────────────────────────────────────────────────────

def test_sans_operation_l_echeance_reste_attendue():
    """Le comportement d'avant, qui reste juste quand rien n'est sauté : une
    échéance en retard est toujours attendue."""
    ech = echeances_du_mois([_rec()], [], 2026, 10, aujourdhui=AUJ)
    assert [(e["date"], e["_deja"]) for e in ech] == [("2026-10-15", False)]


def test_echeance_sautee_n_est_plus_attendue():
    ech = echeances_du_mois([_rec(sautees="2026-10-15")], [], 2026, 10,
                            aujourdhui=AUJ)
    assert ech == []


def test_seul_le_mois_saute_disparait():
    rec = _rec(sautees="2026-10-15")
    dates = [d.isoformat() for d in generate_occurrences(rec, date(2026, 12, 31))]
    assert dates == ["2026-08-15", "2026-09-15", "2026-11-15", "2026-12-15"]


def test_sautees_abimees_ne_bloquent_rien():
    """Une valeur illisible (base modifiée à la main) ne saute rien et ne
    plante pas."""
    rec = _rec(sautees="n'importe quoi,,2026-13-45")
    assert len(generate_occurrences(rec, date(2026, 10, 31))) == 3


def test_echeances_decouvertes_par_une_suppression():
    """Supprimer l'opération prévue découvre l'échéance qu'elle couvrait :
    c'est celle-là qu'on propose de sauter."""
    recs = [_rec(), _rec(id="autre", libelle="ASSURANCE AUTO", montant=-30.0,
                         day_of_month=5, sous_cat="Assurance")]
    avant = [_tx(), _tx(id="t2", date="2026-10-05", date_valeur="2026-10-05",
                        libelle="ASSURANCE AUTO", sous_cat="Assurance",
                        montant=-30.0, pointee=1, prevue=0)]
    apres = avant[1:]
    assert echeances_decouvertes(recs, avant, apres, ["2026-10-15"]) == [
        {"rec_id": "peage", "libelle": "PEAGE AUTOROUTE",
         "date": "2026-10-15", "montant": -50.0}]


def test_supprimer_une_operation_ordinaire_ne_decouvre_rien():
    recs = [_rec()]
    avant = [_tx(), _tx(id="t9", libelle="BOULANGERIE", montant=-3.0,
                        prevue=0)]
    assert echeances_decouvertes(recs, avant, avant[:1], ["2026-10-15"]) == []


# ── La base ──────────────────────────────────────────────────────────────

def test_sauter_puis_retablir(tmp_path):
    db = Database(str(tmp_path / "s.db"))
    db.insert_recurring(_rec())
    db.sauter_echeance("peage", "2026-10-15")
    db.sauter_echeance("peage", "2026-10-15")          # pas de doublon
    db.sauter_echeance("peage", "2026-12-15")
    rec = dict(db.list_recurring()[0])
    assert rec["sautees"] == "2026-10-15,2026-12-15"
    db.retablir_echeance("peage", "2026-10-15")
    assert dict(db.list_recurring()[0])["sautees"] == "2026-12-15"


def test_modifier_la_recurrence_garde_les_dates_sautees(tmp_path):
    db = Database(str(tmp_path / "s.db"))
    db.insert_recurring(_rec())
    db.sauter_echeance("peage", "2026-10-15")
    db.update_recurring("peage", {"montant": -60.0})
    assert dict(db.list_recurring()[0])["sautees"] == "2026-10-15"


def test_ancienne_base_recoit_la_colonne_sans_perte(tmp_path):
    """Une base d'avant la 1.41.26 s'ouvre : ses récurrences restent intactes
    et n'ont rien de sauté."""
    chemin = str(tmp_path / "ancienne.db")
    db = Database(chemin)
    db.insert_recurring(_rec())
    db.conn.close()
    # On retire la colonne pour simuler une base écrite par l'ancienne version.
    c = sqlite3.connect(chemin)
    c.execute("ALTER TABLE recurring DROP COLUMN sautees")
    c.commit(); c.close()

    db = Database(chemin)
    rec = dict(db.list_recurring()[0])
    assert rec["libelle"] == "PEAGE AUTOROUTE" and rec["sautees"] == ""


def test_fusion_d_un_export_ancien_sans_sautees(tmp_path):
    """Un export JSON d'une version précédente ne connaît pas « sautees » :
    sans précaution on insérerait NULL dans une colonne NOT NULL."""
    db = Database(str(tmp_path / "f.db"))
    db.upsert_synced("recurring", {**_rec(), "updated_at": "2026-10-01T00:00:00Z"})
    assert dict(db.list_recurring()[0])["sautees"] == ""


def test_l_export_json_transporte_les_dates_sautees(tmp_path):
    from comptesbudget.sync import db_snapshot, merge_remote_into_db
    src = Database(str(tmp_path / "a.db"))
    src.insert_recurring(_rec())
    src.sauter_echeance("peage", "2026-10-15")
    dst = Database(str(tmp_path / "b.db"))
    merge_remote_into_db(dst, db_snapshot(src))
    assert dict(dst.list_recurring()[0])["sautees"] == "2026-10-15"


# ── Le bandeau ───────────────────────────────────────────────────────────

def test_bandeau_ne_compte_plus_l_echeance_sautee(qapp, tmp_path):
    """Le cas d'origine : deux échéances en octobre, l'une sautée. Les
    sorties à venir ne comptent plus que l'autre."""
    from comptesbudget.ui.views.bilan import BilanView
    db = Database(str(tmp_path / "b.db"))
    db.insert_recurring(_rec())
    db.insert_recurring(_rec(id="box", libelle="BOX INTERNET", montant=-30.0,
                             day_of_month=30, sous_cat="Internet"))
    vue = BilanView(db)
    lignes, _ = vue._lignes_a_venir([], date(2026, 10, 1), date(2026, 10, 31))
    assert round(sum(m for _d, _l, m, _c in lignes), 2) == -80.0

    db.sauter_echeance("peage", "2026-10-15")
    lignes, _ = vue._lignes_a_venir([], date(2026, 10, 1), date(2026, 10, 31))
    assert [(d, m) for d, _l, m, _c in lignes] == [("2026-10-30", -30.0)]


def test_prochaines_echeances_nomment_celles_en_retard():
    """Le total et la liste ne doivent plus se contredire : une échéance en
    retard, comptée dans « Sorties à venir », est nommée elle aussi."""
    from comptesbudget.ui.views.bilan import prochaines_echeances
    lignes = [("2026-10-30", "BOX INTERNET", -30.0, False),
              ("2026-10-15", "PEAGE AUTOROUTE", -50.0, False),
              ("2026-11-02", "ACHAT CARTE", -20.0, True)]
    assert prochaines_echeances(lignes, "2026-10-20") == [
        ("2026-10-15", "PEAGE AUTOROUTE", -50.0, True),
        ("2026-10-30", "BOX INTERNET", -30.0, False)]


# ── Les écrans ───────────────────────────────────────────────────────────

def _mois_prochain_le_10() -> date:
    auj = date.today()
    an, mo = (auj.year + 1, 1) if auj.month == 12 else (auj.year, auj.month + 1)
    return date(an, mo, 10)


def test_supprimer_l_echeance_prevue_propose_de_la_sauter(qapp, tmp_path,
                                                         monkeypatch):
    """Supprimer la ligne prévue, répondre « Sauter cette fois-ci » : la
    récurrence retient la date. « Annuler » remet la ligne ET l'attente."""
    import comptesbudget.ui.views.operations as module_operations
    from comptesbudget.ui.views.operations import OperationsView
    d = _mois_prochain_le_10()
    db = Database(str(tmp_path / "o.db"))
    db.set_setting("initial_balance", "0")
    db.insert_recurring(_rec(day_of_month=10, start_date=d.isoformat()))
    db.insert_tx(_tx(date=d.isoformat(), date_valeur=d.isoformat()))
    questions = []
    monkeypatch.setattr(module_operations, "confirmer",
                        lambda _p, titre, *a, **k: questions.append(titre) or True)
    vue = OperationsView(db)
    vue.period = "all"
    vue.reload_from_db()
    vue.table.selectRow(0)
    vue.delete_selected()

    assert questions == ["Supprimer l'opération", "Échéance prévue supprimée"]
    assert dict(db.list_recurring()[0])["sautees"] == d.isoformat()

    vue.annuler_suppression()
    assert len(db.list_tx()) == 1
    assert dict(db.list_recurring()[0])["sautees"] == ""


def test_repondre_non_garde_l_echeance_attendue(qapp, tmp_path, monkeypatch):
    import comptesbudget.ui.views.operations as module_operations
    from comptesbudget.ui.views.operations import OperationsView
    d = _mois_prochain_le_10()
    db = Database(str(tmp_path / "o.db"))
    db.set_setting("initial_balance", "0")
    db.insert_recurring(_rec(day_of_month=10, start_date=d.isoformat()))
    db.insert_tx(_tx(date=d.isoformat(), date_valeur=d.isoformat()))
    reponses = iter([True, False])        # supprimer : oui ; sauter : non
    monkeypatch.setattr(module_operations, "confirmer",
                        lambda *a, **k: next(reponses))
    vue = OperationsView(db)
    vue.period = "all"
    vue.reload_from_db()
    vue.table.selectRow(0)
    vue.delete_selected()
    assert db.list_tx() == []
    assert dict(db.list_recurring()[0])["sautees"] == ""


def test_previsionnel_sauter_puis_retablir(qapp, tmp_path):
    from comptesbudget.ui.views.previsionnel import PrevisionnelView
    d = _mois_prochain_le_10()
    db = Database(str(tmp_path / "p.db"))
    db.insert_recurring(_rec(day_of_month=10, start_date=d.isoformat(),
                             end_date=d.isoformat()))
    vue = PrevisionnelView(db)
    vue.refresh()
    assert not vue.btn_sauter.isEnabled()          # rien de choisi

    vue.forecast_table.selectRow(0)
    assert vue.btn_sauter.text() == "⏭ Sauter cette échéance"
    vue._sauter_ou_retablir()
    assert dict(db.list_recurring()[0])["sautees"] == d.isoformat()
    ligne = vue.forecast_model.item(0, 1).text()
    assert ligne.endswith("sautée cette fois-ci")
    assert "Sorties : 0,00\xa0€" in vue.summary.text()

    vue.forecast_table.selectRow(0)
    assert vue.btn_sauter.text() == "↩ Rétablir cette échéance"
    vue._sauter_ou_retablir()
    assert dict(db.list_recurring()[0])["sautees"] == ""
    assert vue.forecast_model.item(0, 1).text() == "PEAGE AUTOROUTE"
