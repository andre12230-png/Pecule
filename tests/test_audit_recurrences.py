"""Outil d'audit des récurrences (outils/audit_recurrences.py).

Incident du 23/09/2026 : deux récurrences réglées au 7 du mois alors que les
versements arrivaient le 3 depuis quatre mois n'ont pas été signalées. L'outil
prenait la médiane du jour sur douze mois, qui restait au 7. Même défaut pour
un montant revalorisé : la médiane garde l'ancien. Montant et jour se jugent
sur les DERNIERS passages.
"""
from datetime import date

from comptesbudget.database import Database
from outils.audit_recurrences import auditer


def _il_y_a(n: int, jour: int) -> str:
    """Le `jour` du n-ième mois avant le mois en cours (n >= 1)."""
    auj = date.today()
    m = auj.month - 1 - n
    return date(auj.year + m // 12, m % 12 + 1, jour).isoformat()


def _base(tmp_path, recurrence: dict, operations: list[tuple]):
    """operations : (date, libellé, montant, sous-catégorie)."""
    db = Database(str(tmp_path / "t.db"))
    db.insert_recurring({
        "id": "r1", "categorie": "Revenus", "sous_cat": "", "type": "",
        "frequency": "monthly", "start_date": _il_y_a(12, 1),
        "end_date": None, "actif": 1, **recurrence})
    for i, (d, lib, m, sc) in enumerate(operations):
        db.insert_tx({
            "id": f"op{i}", "date": d, "date_valeur": d, "libelle": lib,
            "libelle_op": "", "reference": "", "type": "Virement recu",
            "categorie": "Revenus", "sous_cat": sc, "info": "",
            "montant": m, "pointee": 1})
    db.conn.close()
    return str(tmp_path / "t.db")


def _ligne(capsys, libelle: str) -> str:
    """La ligne du rapport consacrée à cette récurrence."""
    sortie = capsys.readouterr().out
    return next(l for l in sortie.splitlines() if l.startswith(libelle))


def test_jour_qui_a_glisse_recemment_est_signale(tmp_path, capsys):
    # Huit mois le 7, puis les quatre derniers le 3 : la médiane sur douze
    # mois reste au 7 et masquait le glissement.
    ops = ([(_il_y_a(n, 7), "PENSION", 800.0, "") for n in range(12, 4, -1)]
           + [(_il_y_a(n, 3), "PENSION", 800.0, "") for n in range(4, 0, -1)])
    auditer(_base(tmp_path, {"libelle": "PENSION", "montant": 800.0,
                             "day_of_month": 7}, ops))
    assert "JOUR prévu le 7" in _ligne(capsys, "PENSION")


def test_montant_revalorise_au_dernier_passage_est_signale(tmp_path, capsys):
    ops = ([(_il_y_a(n, 10), "ASSURANCE", -100.0, "") for n in range(12, 1, -1)]
           + [(_il_y_a(1, 10), "ASSURANCE", -108.0, "")])
    auditer(_base(tmp_path, {"libelle": "ASSURANCE", "montant": -100.0,
                             "day_of_month": 10, "categorie": "Banque"}, ops))
    ligne = _ligne(capsys, "ASSURANCE")
    assert "MONTANT" in ligne and "-108.00" in ligne


def test_recurrence_juste_reste_ok(tmp_path, capsys):
    ops = [(_il_y_a(n, 3), "PENSION", 800.0, "") for n in range(12, 0, -1)]
    auditer(_base(tmp_path, {"libelle": "PENSION", "montant": 800.0,
                             "day_of_month": 3}, ops))
    assert _ligne(capsys, "PENSION").rstrip().endswith("ok")


def test_petit_versement_du_meme_nom_ignore(tmp_path, capsys):
    # Un petit complément versé sous le même libellé, en fin de mois, ne doit
    # fausser ni le montant ni le jour : on garde, chaque mois, le passage le
    # plus proche du montant prévu.
    ops = [(_il_y_a(n, 3), "PENSION", 800.0, "") for n in range(12, 0, -1)]
    ops += [(_il_y_a(n, 25), "PENSION", 12.0, "") for n in (3, 2, 1)]
    auditer(_base(tmp_path, {"libelle": "PENSION", "montant": 800.0,
                             "day_of_month": 3}, ops))
    assert _ligne(capsys, "PENSION").rstrip().endswith("ok")


def test_la_sous_categorie_separe_deux_contrats(tmp_path, capsys):
    # Un assureur prélève deux contrats sous le même libellé : la récurrence
    # de l'habitation ne doit être jugée que sur l'habitation.
    ops = [(_il_y_a(n, 10), "ASSUREUR", -20.0, "Habitation") for n in range(12, 0, -1)]
    ops += [(_il_y_a(n, 4), "ASSUREUR", -45.0, "Auto") for n in range(12, 0, -1)]
    auditer(_base(tmp_path, {"libelle": "ASSUREUR", "montant": -20.0,
                             "day_of_month": 10, "sous_cat": "Habitation",
                             "categorie": "Banque"}, ops))
    assert _ligne(capsys, "ASSUREUR").rstrip().endswith("ok")


def test_jour_change_il_y_a_deux_mois_sans_fausse_alerte(tmp_path, capsys):
    # Échéance déplacée du 28 au 10 depuis deux mois, récurrence déjà mise à
    # jour : sur quatre passages (28, 28, 10, 10), la médiane tomberait au
    # 19, un jour qui n'existe pas. Trois passages tranchent.
    ops = ([(_il_y_a(n, 28), "CREDIT", -500.0, "") for n in range(12, 2, -1)]
           + [(_il_y_a(n, 10), "CREDIT", -500.0, "") for n in (2, 1)])
    auditer(_base(tmp_path, {"libelle": "CREDIT", "montant": -500.0,
                             "day_of_month": 10, "categorie": "Crédits"}, ops))
    assert _ligne(capsys, "CREDIT").rstrip().endswith("ok")


def test_tranche_future_annoncee_sans_alerte(tmp_path, capsys):
    # Une tranche qui ne commence que dans plusieurs années (dernière
    # mensualité d'un prêt, au montant différent) n'a rien à comparer au
    # présent (piège n° 4).
    ops = [(_il_y_a(n, 10), "PRET", -300.0, "") for n in range(12, 0, -1)]
    auditer(_base(tmp_path, {"libelle": "PRET", "montant": -310.0,
                             "day_of_month": 10, "categorie": "Crédits",
                             "start_date": "2040-01-10"}, ops))
    ligne = _ligne(capsys, "PRET")
    assert "tranche à venir" in ligne and "MONTANT" not in ligne
