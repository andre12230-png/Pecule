"""Tests des opérations récurrentes (occurrences et détection)."""
from datetime import date

from comptesbudget.recurring import (
    _recurring_norm_label, detect_recurring_candidates, echeances_du_mois,
    generate_occurrences, next_occurrence,
)


def test_next_monthly():
    rec = {"frequency": "monthly", "day_of_month": 15}
    assert next_occurrence(rec, date(2026, 1, 15)) == date(2026, 2, 15)


def test_next_monthly_clamp_fin_de_mois():
    rec = {"frequency": "monthly", "day_of_month": 31}
    assert next_occurrence(rec, date(2026, 1, 31)) == date(2026, 2, 28)


def test_next_monthly_passage_decembre():
    rec = {"frequency": "monthly", "day_of_month": 15}
    assert next_occurrence(rec, date(2026, 12, 15)) == date(2027, 1, 15)


def test_next_weekly_biweekly():
    assert next_occurrence({"frequency": "weekly"}, date(2026, 6, 1)) == date(2026, 6, 8)
    assert next_occurrence({"frequency": "biweekly"}, date(2026, 6, 1)) == date(2026, 6, 15)


def test_next_quarterly_passe_annee():
    rec = {"frequency": "quarterly", "day_of_month": 15}
    assert next_occurrence(rec, date(2026, 11, 15)) == date(2027, 2, 15)


def test_next_yearly_bissextile():
    rec = {"frequency": "yearly"}
    # 29/02 → l'année suivante n'est pas bissextile → repli au 28
    assert next_occurrence(rec, date(2024, 2, 29)) == date(2025, 2, 28)


def test_generate_occurrences_bornes():
    rec = {"actif": 1, "frequency": "monthly", "day_of_month": 15,
           "start_date": "2026-01-15"}
    occ = generate_occurrences(rec, date(2026, 4, 30))
    assert occ == [date(2026, 1, 15), date(2026, 2, 15),
                   date(2026, 3, 15), date(2026, 4, 15)]


def test_generate_occurrences_inactif_ou_vide():
    assert generate_occurrences({"actif": 0, "start_date": "2026-01-01"}, date(2026, 6, 1)) == []
    assert generate_occurrences({"actif": 1, "start_date": None}, date(2026, 6, 1)) == []


def test_norm_label_retire_dates():
    assert _recurring_norm_label("ELECTRICITE Facture 12/03/2026") == "electricite facture"


def test_detect_candidate_mensuel():
    txs = [{"date": f"2026-0{m}-05", "libelle": "Loyer",
            "montant": -800.0, "categorie": "Logement - maison", "type": "Prelevement"}
           for m in range(1, 6)]   # 5 mois consécutifs
    cands = detect_recurring_candidates(txs, min_months=4)
    assert len(cands) == 1
    c = cands[0]
    assert c["libelle"] == "Loyer"
    assert c["frequency"] == "monthly"
    assert c["montant"] == -800.0
    assert c["categorie"] == "Logement - maison"


def test_detect_ignore_trop_court():
    txs = [{"date": f"2026-0{m}-05", "libelle": "Test", "montant": -10.0}
           for m in range(1, 3)]   # 2 mois < min_months
    assert detect_recurring_candidates(txs, min_months=4) == []


def test_next_occurrence_ne_derive_pas_apres_un_mois_court():
    # Sans jour de référence, une échéance au 31 restait bloquée au 28 après
    # février : 31/01 → 28/02 → 28/03… Elle doit revenir au 31.
    rec = {"frequency": "monthly", "day_of_month": None}
    occ = generate_occurrences(
        {**rec, "actif": 1, "start_date": "2026-01-31"}, date(2026, 5, 31))
    assert [d.isoformat() for d in occ] == [
        "2026-01-31", "2026-02-28", "2026-03-31", "2026-04-30", "2026-05-31"]


def test_next_occurrence_annuelle_respecte_le_jour_du_mois():
    # La fréquence annuelle ignorait day_of_month.
    rec = {"frequency": "yearly", "day_of_month": 5}
    assert next_occurrence(rec, date(2026, 3, 20)).isoformat() == "2027-03-05"
    # 29 février → 28 février les années non bissextiles
    bis = {"frequency": "yearly", "day_of_month": 29}
    assert next_occurrence(bis, date(2028, 2, 29)).isoformat() == "2029-02-28"


def test_generate_occurrences_date_illisible_ne_plante_pas():
    # Une date abîmée (base modifiée à la main, JSON restauré) ne doit pas
    # empêcher l'application de s'ouvrir.
    assert generate_occurrences(
        {"actif": 1, "start_date": "bidon", "frequency": "monthly"},
        date(2026, 12, 31)) == []
    assert generate_occurrences(
        {"actif": 1, "start_date": "2026-01-01", "end_date": "n'importe quoi",
         "frequency": "yearly"}, date(2026, 12, 31)) == [date(2026, 1, 1)]


# ── Échéances du mois (« ce qui doit être débité ») ──────────────────────────

def _rec(**kw):
    base = {"id": "r", "libelle": "PRETIS", "montant": -600.00,
            "categorie": "Crédits & emprunts", "sous_cat": "", "type": "Prelevement",
            "frequency": "monthly", "day_of_month": 10,
            "start_date": "2026-01-10", "end_date": None, "actif": 1}
    base.update(kw)
    return base


def _op(**kw):
    base = {"id": "t", "date": "2026-08-10", "date_valeur": "2026-08-10",
            "libelle": "PRETIS", "montant": -600.00, "pointee": 1}
    base.update(kw)
    return base


def test_echeances_du_mois_liste_les_occurrences():
    ech = echeances_du_mois([_rec()], [], 2026, 8, aujourdhui=date(2026, 8, 1))
    assert len(ech) == 1
    assert ech[0]["date"] == "2026-08-10"
    assert ech[0]["montant"] == -600.00
    assert ech[0]["categorie"] == "Crédits & emprunts"
    assert ech[0]["_default"] is True and ech[0]["_deja"] is False


def test_echeances_du_mois_ignore_les_recurrences_inactives():
    assert echeances_du_mois([_rec(actif=0)], [], 2026, 8,
                             aujourdhui=date(2026, 8, 1)) == []


def test_echeances_du_mois_marque_ce_qui_est_deja_enregistre():
    ech = echeances_du_mois([_rec()], [_op()], 2026, 8, aujourdhui=date(2026, 8, 1))
    assert ech[0]["_deja"] is True and ech[0]["_default"] is False


def test_echeances_du_mois_tolere_un_decalage_de_quelques_jours():
    # Échéance du 10 passée le 12 (jour férié / week-end) : déjà couverte.
    ech = echeances_du_mois([_rec()], [_op(date="2026-08-12", date_valeur="2026-08-12")],
                            2026, 8, aujourdhui=date(2026, 8, 1))
    assert ech[0]["_deja"] is True
    # Et même débordement sur le mois précédent (échéance du 1er payée le 30).
    ech = echeances_du_mois([_rec(day_of_month=1, start_date="2026-01-01")],
                            [_op(date="2026-07-30", date_valeur="2026-07-30")],
                            2026, 8, aujourdhui=date(2026, 8, 1))
    assert ech[0]["_deja"] is True


def test_echeances_du_mois_libelle_bancaire_different():
    # La banque écrit « PRETIS 1234567 » : le rapprochement doit tenir.
    ech = echeances_du_mois([_rec()], [_op(libelle="PRETIS 1234567")], 2026, 8,
                            aujourdhui=date(2026, 8, 1))
    assert ech[0]["_deja"] is True


def test_echeances_du_mois_ne_confond_pas_les_sens():
    # Un remboursement du même nom ne solde pas un prélèvement attendu.
    ech = echeances_du_mois([_rec()], [_op(montant=800.00)], 2026, 8,
                            aujourdhui=date(2026, 8, 1))
    assert ech[0]["_deja"] is False


def test_echeances_du_mois_date_passee_non_precochee():
    ech = echeances_du_mois([_rec()], [], 2026, 8, aujourdhui=date(2026, 8, 20))
    assert ech[0]["_passee"] is True and ech[0]["_default"] is False


def test_echeances_du_mois_hebdomadaire_compte_les_occurrences():
    # 4 occurrences attendues, 1 seule déjà passée → 3 restent à créer.
    rec = _rec(frequency="weekly", start_date="2026-08-03", libelle="COURSES")
    ech = echeances_du_mois([rec], [_op(libelle="COURSES", date="2026-08-03",
                                        date_valeur="2026-08-03")],
                            2026, 8, aujourdhui=date(2026, 8, 1))
    assert [e["_deja"] for e in ech] == [True, False, False, False, False]


def test_echeances_du_mois_triees_par_date():
    recs = [_rec(id="a", libelle="ALPHATEL", day_of_month=25, start_date="2026-01-25"),
            _rec(id="b", libelle="PRETIS", day_of_month=10, start_date="2026-01-10")]
    ech = echeances_du_mois(recs, [], 2026, 8, aujourdhui=date(2026, 8, 1))
    assert [e["libelle"] for e in ech] == ["PRETIS", "ALPHATEL"]


def test_echeances_du_mois_suffixe_bancaire():
    # La banque ajoute la forme juridique : « SECURIDOM » ↔ « SECURIDOM SAS ».
    ech = echeances_du_mois([_rec(libelle="SECURIDOM", montant=-20.00)],
                            [_op(libelle="SECURIDOM SAS", montant=-20.00)],
                            2026, 8, aujourdhui=date(2026, 8, 1))
    assert ech[0]["_deja"] is True


def test_echeances_du_mois_ne_confond_pas_deux_libelles_voisins():
    # Un mot commun en tête ne suffit pas si la suite diffère.
    ech = echeances_du_mois([_rec(libelle="ASS HABITATION", montant=-18.00)],
                            [_op(libelle="ASS AUTO", montant=-35.00)],
                            2026, 8, aujourdhui=date(2026, 8, 1))
    assert ech[0]["_deja"] is False


def test_echeances_du_mois_la_plus_precise_se_sert_dabord():
    # « ALPHATEL MOBILE » ne doit pas se faire prendre son opération par « ALPHATEL ».
    recs = [_rec(id="a", libelle="ALPHATEL", montant=-40.00),
            _rec(id="b", libelle="ALPHATEL MOBILE", montant=-20.00)]
    ech = echeances_du_mois(
        recs, [_op(libelle="ALPHATEL MOBILE 12", montant=-20.00)],
        2026, 8, aujourdhui=date(2026, 8, 1))
    couvertes = {e["libelle"]: e["_deja"] for e in ech}
    assert couvertes == {"ALPHATEL MOBILE": True, "ALPHATEL": False}


def test_echeances_du_mois_deux_recurrences_meme_libelle():
    """Une banque libelle « Echeance De Credit » aussi bien la mensualité d'un
    prêt que la petite assurance qui l'accompagne : deux échéances portent le
    même libellé. Le prélèvement doit être rattaché à celle dont le montant
    correspond ; l'autre doit rester à créer."""
    recs = [_rec(id="petite", libelle="Echeance De Credit", montant=-15.00),
            _rec(id="grosse", libelle="Echeance De Credit", montant=-500.00)]
    ech = echeances_du_mois(recs, [_op(libelle="Echeance De Credit",
                                       montant=-500.00)],
                            2026, 8, aujourdhui=date(2026, 8, 1))
    couvertes = {e["montant"]: e["_deja"] for e in ech}
    assert couvertes == {-500.00: True, -15.00: False}


def test_echeances_du_mois_montant_variable_reste_rapproche():
    """La tolérance sur le montant ne doit pas casser le cas d'une facture qui
    varie : -110,00 € prévu, -124,00 € prélevé."""
    ech = echeances_du_mois([_rec(libelle="ENERGIA VERTE", montant=-110.00)],
                            [_op(libelle="ENERGIA VERTE", montant=-124.00)],
                            2026, 8, aujourdhui=date(2026, 8, 1))
    assert ech[0]["_deja"] is True


def test_echeances_du_mois_le_paiement_du_mois_precedent_ne_solde_pas():
    """Une échéance du 31 août ne doit pas être considérée comme payée par le
    prélèvement du 31 juillet, pourtant proche du bord de la fenêtre."""
    rec = _rec(libelle="GAMMA TELECOM", montant=-30.0, day_of_month=31,
               start_date="2026-01-31")
    ech = echeances_du_mois(rec and [rec],
                            [_op(libelle="GAMMA TELECOM", montant=-30.0,
                                 date="2026-07-31", date_valeur="2026-07-31")],
                            2026, 8, aujourdhui=date(2026, 8, 1))
    assert ech[0]["date"] == "2026-08-31"
    assert ech[0]["_deja"] is False


def test_echeances_du_mois_meme_mois_suffit():
    """Dans le mois, le jour exact n'a pas d'importance : une échéance prévue
    le 17 et payée le 30 reste la même (cas BETACOM)."""
    ech = echeances_du_mois([_rec(libelle="BETACOM", montant=-8.00, day_of_month=17,
                                  start_date="2026-01-17")],
                            [_op(libelle="BETACOM", montant=-8.00,
                                 date="2026-08-30", date_valeur="2026-08-30")],
                            2026, 8, aujourdhui=date(2026, 8, 1))
    assert ech[0]["_deja"] is True


def test_echeances_du_mois_sous_categories_distinguent_deux_contrats():
    """Même assureur, même libellé, deux contrats : l'auto prélevée le 5 ne
    solde pas l'assurance habitation attendue le 10."""
    rec = _rec(libelle="L'amandier Assurrance", montant=-18.00, day_of_month=10,
               sous_cat="Assurance Habitation")
    auto = _op(libelle="L'amandier Assurrance", montant=-35.00,
               date="2026-08-05", date_valeur="2026-08-05")
    auto["sous_cat"] = "Assurance Auto"
    ech = echeances_du_mois([rec], [auto], 2026, 8, aujourdhui=date(2026, 8, 1))
    assert ech[0]["_deja"] is False


def test_echeances_du_mois_sous_categorie_renommee_par_la_banque():
    """À l'inverse, une sous-catégorie réécrite par la banque ne doit pas
    empêcher le rapprochement quand le montant, lui, concorde (cas SERVICE DES EAUX)."""
    rec = _rec(libelle="SERVICE DES EAUX", montant=-22.50, day_of_month=5, sous_cat="eau")
    op = _op(libelle="SERVICE DES EAUX", montant=-22.50, date="2026-08-05",
             date_valeur="2026-08-05")
    op["sous_cat"] = "Energie eau, gaz, electricite, fioul"
    ech = echeances_du_mois([rec], [op], 2026, 8, aujourdhui=date(2026, 8, 1))
    assert ech[0]["_deja"] is True


def test_echeances_du_mois_carte_a_debit_differe():
    """Un achat par carte du 1er septembre n'est débité que le 4 octobre.

    Cette date de valeur est celle du prélèvement groupé, pas un décalage de
    quelques jours : elle ne dit rien du mois auquel l'achat se rattache. Sans
    précaution, l'achat de septembre solderait l'échéance d'OCTOBRE, qui ne
    serait alors jamais proposée (cas « Anthropique / Claude AI »)."""
    rec = _rec(libelle="ANTHROPIQUE", montant=-21.60, type="Carte bancaire",
               day_of_month=1, start_date="2026-01-01")
    achat_septembre = _op(libelle="ANTHROPIQUE", montant=-21.60,
                          type="Carte bancaire",
                          date="2026-09-01", date_valeur="2026-10-04")

    # L'achat de septembre solde bien l'échéance de SEPTEMBRE…
    ech = echeances_du_mois([rec], [achat_septembre], 2026, 9,
                            aujourdhui=date(2026, 9, 1))
    assert ech[0]["_deja"] is True

    # … mais laisse celle d'OCTOBRE à venir.
    ech = echeances_du_mois([rec], [achat_septembre], 2026, 10,
                            aujourdhui=date(2026, 9, 1))
    assert ech[0]["date"] == "2026-10-01"
    assert ech[0]["_deja"] is False
    assert ech[0]["_default"] is True


def test_echeances_du_mois_hors_carte_garde_la_date_de_valeur():
    """Le garde-fou ne vaut que pour la carte : un prélèvement ordinaire
    présenté le 31 juillet et daté du 3 août par la banque solde bien
    l'échéance d'août."""
    rec = _rec(libelle="DELTA ASSUR", montant=-40.0, type="Prelevement",
               day_of_month=3, start_date="2026-01-03")
    op = _op(libelle="DELTA ASSUR", montant=-40.0, type="Prelevement",
             date="2026-07-31", date_valeur="2026-08-03")
    ech = echeances_du_mois([rec], [op], 2026, 8, aujourdhui=date(2026, 8, 1))
    assert ech[0]["_deja"] is True
