"""Débit différé : reconnu et daté d'après le compte, pas d'après celui de
l'auteur (lot « autres utilisateurs », 26/09/2026).

- Une carte à débit IMMÉDIAT voit souvent ses achats valorisés un à trois
  jours plus tard (week-end) : un seul de ces décalages suffisait à faire
  passer le compte en « débit différé ».
- Le jour du prélèvement était figé au 4 du mois suivant. Au Crédit Agricole,
  par exemple, les achats du 20 au 19 partent le dernier jour ouvré du mois :
  un achat du 10 part le 30 du MÊME mois.
"""
from comptesbudget.utils import carte_a_debit_differe, regle_debit_differe


def _achat(d, dv, montant=-20.0, **extra):
    return {"date": d, "date_valeur": dv, "type": "Carte bancaire",
            "montant": montant, **extra}


# ── Reconnaître le débit différé ────────────────────────────────────────────

def test_carte_immediate_valorisee_un_a_trois_jours_plus_tard():
    ops = [_achat("2026-09-04", "2026-09-07"),      # vendredi → lundi
           _achat("2026-09-10", "2026-09-11"),
           _achat("2026-09-15", "2026-09-15"),
           _achat("2026-09-18", "2026-09-21")]
    assert not carte_a_debit_differe(ops)


def test_carte_differee_reconnue():
    ops = [_achat("2026-08-10", "2026-09-04"), _achat("2026-08-25", "2026-09-04"),
           _achat("2026-09-02", "2026-10-04")]
    assert carte_a_debit_differe(ops)


def test_un_jour_ferie_isole_ne_suffit_pas():
    # Achat du 24/12 valorisé le 02/01 sur une carte immédiate : une fois.
    ops = [_achat(f"2026-12-{j:02d}", f"2026-12-{j:02d}") for j in (1, 5, 9, 14)]
    ops.append(_achat("2026-12-24", "2027-01-02"))
    assert not carte_a_debit_differe(ops)


def test_passage_recent_au_differe_reconnu():
    anciens = [_achat(f"2025-0{m}-10", f"2025-0{m}-10") for m in range(1, 10)] * 4
    recents = [_achat(f"2026-0{m}-10", f"2026-0{m + 1}-04") for m in range(1, 9)] * 4
    assert carte_a_debit_differe(anciens + recents)


def test_les_echeances_prevues_ne_comptent_pas():
    # Une échéance générée par Pécule n'est pas une trace laissée par la banque.
    ops = [_achat("2026-09-01", "2026-10-04", prevue=1)]
    assert not carte_a_debit_differe(ops)


# ── Dater un achat ──────────────────────────────────────────────────────────

def test_sans_historique_le_4_du_mois_suivant():
    regle = regle_debit_differe([])
    assert regle("2026-09-15") == "2026-10-04"
    assert regle("2026-12-31") == "2027-01-04"


def test_historique_au_4_inchange():
    ops = [_achat("2026-08-10", "2026-09-04"), _achat("2026-08-26", "2026-09-04"),
           _achat("2026-09-03", "2026-10-04")]
    regle = regle_debit_differe(ops)
    assert regle("2026-09-15") == "2026-10-04"
    assert regle("2026-09-02") == "2026-10-04"


def test_fin_de_mois_du_credit_agricole():
    # Achats du 20 au 19, prélevés le dernier jour ouvré.
    ops = [_achat("2026-06-10", "2026-06-30"), _achat("2026-06-25", "2026-07-31"),
           _achat("2026-07-13", "2026-07-31"), _achat("2026-07-22", "2026-08-31")]
    regle = regle_debit_differe(ops)
    assert regle("2026-09-11") == "2026-09-30"           # même mois
    assert regle("2026-09-24").startswith("2026-10-")    # mois suivant
    assert regle("2026-02-10") == "2026-02-28"           # février borné


def test_les_exceptions_ne_font_pas_la_regle():
    # Un lot repoussé au lundi par un week-end, un achat décalé d'un lot à la
    # main : l'habitude du compte l'emporte (constaté sur une vraie base).
    ops = [_achat("2026-05-12", "2026-06-04"), _achat("2026-06-12", "2026-07-04"),
           _achat("2026-07-12", "2026-08-05"),       # week-end
           _achat("2026-08-12", "2026-10-04")]       # décalé à la main
    assert regle_debit_differe(ops)("2026-09-12") == "2026-10-04"


def test_fin_de_cycle_avant_la_fin_du_mois():
    # Carte dont le cycle se ferme vers le 28 : les achats des derniers jours
    # partent au lot du mois d'après.
    ops = [_achat("2026-06-10", "2026-07-04"), _achat("2026-06-30", "2026-08-04"),
           _achat("2026-07-11", "2026-08-04"), _achat("2026-07-30", "2026-09-04")]
    regle = regle_debit_differe(ops)
    assert regle("2026-09-10") == "2026-10-04"
    assert regle("2026-09-30") == "2026-11-04"
