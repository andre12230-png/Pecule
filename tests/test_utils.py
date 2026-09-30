"""Tests des utilitaires (formatage, normalisation, périodes)."""
import os
from datetime import date

from comptesbudget.utils import (
    MOIS_TOUS, annee_de_periode, annees_disponibles, canonical_cat, cat_color,
    date_debit_differe, deaccent, fmt_date_fr, fmt_euro, in_period,
    list_periods, mois_disponibles, nom_mois_fr, numero_cheque, period_label,
    periode_voisine, suggest_category,
)


def test_numero_cheque():
    # Saisi dans le formulaire (ou venu d'un QIF) : la référence fait foi
    assert numero_cheque({"type": "Cheque", "reference": "1234567",
                          "libelle_op": "CHEQUE N° ...0132"}) == "1234567"
    # Importé : la banque l'écrit dans son libellé, parfois tronqué — et avec
    # un « ° » abîmé par l'encodage, comme dans les vraies données
    assert numero_cheque({"type": "Cheque", "reference": "",
                          "libelle_op": "CHEQUE N� ...0132"}) == "...0132"
    assert numero_cheque({"type": "Cheque",
                          "libelle_op": "CHQ 0001234"}) == "0001234"
    # Chèque saisi sans numéro
    assert numero_cheque({"type": "Cheque", "libelle_op": "XAV SERVICE"}) == ""
    # Pas un chèque : la référence est un identifiant de la banque
    assert numero_cheque({"type": "Prelevement",
                          "reference": "2624684G11282383"}) == ""
    assert numero_cheque({"type": "", "libelle_op": "REM CHEQUE 123456"}) == ""


def test_fmt_euro_francais():
    # Espaces insécables (\xa0), entre les milliers et devant le « € » : un
    # montant ne se coupe jamais en fin de ligne. Le bandeau Encours carte
    # affichait « il reste 9 » puis « 474,37 € » à la ligne (relecture du
    # 30/09/2026).
    assert fmt_euro(1234.56) == "1\xa0234,56\xa0€"
    assert fmt_euro(1234567.8) == "1\xa0234\xa0567,80\xa0€"
    assert fmt_euro(0) == "0,00\xa0€"
    assert fmt_euro(-5) == "-5,00\xa0€"
    assert " " not in fmt_euro(-98765.43)


def test_fmt_date_fr():
    assert fmt_date_fr("2026-06-23") == "23/06/2026"
    assert fmt_date_fr("") == ""
    assert fmt_date_fr("court") == "court"   # non parsable → tel quel


def test_deaccent():
    assert deaccent("Épargne") == "epargne"
    assert deaccent("Crédit Agricole") == "credit agricole"
    assert deaccent("") == ""


def test_canonical_cat():
    assert canonical_cat("ALIMENTATION") == "Alimentation"
    assert canonical_cat("salaire") == "Revenus"
    assert canonical_cat("inconnu") is None
    assert canonical_cat("") is None


def test_cat_color_fallback():
    assert cat_color("Alimentation") == "#E67E22"
    assert cat_color("Salaire") == "#27AE60"        # via forme canonique Revenus
    assert cat_color("Catégorie inconnue") == "#8A877F"


def test_in_period():
    assert in_period("2026-06-23", "all") is True
    assert in_period("2026-06-23", "2026") is True
    assert in_period("2026-06-23", "2026-06") is True
    assert in_period("2026-06-23", "2026-05") is False
    assert in_period("", "2026") is False


def test_period_label():
    assert period_label("all") == "Toutes périodes"
    assert period_label("2026") == "Année 2026"
    assert period_label("2026-06") == "Juin 2026"
    assert period_label("2026-13") == "2026-13"      # mois invalide → tel quel


def test_list_periods():
    txs = [{"date": "2026-06-23"}, {"date": "2026-05-01"}, {"date": "2025-12-31"}]
    out = list_periods(txs)
    assert out[0] == "all"
    assert "2026" in out and "2025" in out
    assert "2026-06" in out and "2025-12" in out
    # Années avant les mois, ordre décroissant
    assert out.index("2026") < out.index("2026-06")


def test_list_periods_groupe_les_mois_sous_leur_annee():
    """Chaque annee est suivie de ses propres mois, du plus recent au plus
    ancien. Toutes les annees d'abord, puis tous les mois, donnait une liste
    illisible des qu'on suivait plusieurs annees."""
    txs = [{"date": "2026-06-01"}, {"date": "2026-01-15"},
           {"date": "2025-12-31"}, {"date": "2025-03-02"}]
    assert list_periods(txs) == ["all",
                                 "2026", "2026-06", "2026-01",
                                 "2025", "2025-12", "2025-03"]


def test_list_periods_suit_le_mode_date():
    # Achat carte du 28/07 débité le 04/08 : en mode « date de valeur », le
    # mois d'août doit être proposé — sinon l'opération n'est visible dans
    # aucun mois. En mode « date d'opération », c'est juillet qui compte.
    txs = [{"date": "2026-07-28", "date_valeur": "2026-08-04"}]
    op = list_periods(txs, "operation")
    val = list_periods(txs, "valeur")
    assert "2026-07" in op and "2026-08" not in op
    assert "2026-08" in val and "2026-07" not in val


# ── Sélecteur de période en deux menus ──────────────────────────────────────

def test_nom_mois_fr():
    # Le menu des mois ne répète pas l'année : elle est dans le menu d'à côté.
    assert nom_mois_fr("2026-09") == "Septembre"
    assert nom_mois_fr("2026") == "2026"          # pas un mois → tel quel


def test_annee_de_periode():
    assert annee_de_periode("2026-09") == "2026"
    assert annee_de_periode("2026") == "2026"
    assert annee_de_periode("all") is None        # à cheval sur toutes


def test_annees_disponibles_contient_toujours_lannee_en_cours():
    """Sans cette garantie, l'application ne pourrait pas s'ouvrir sur
    l'année en cours tant qu'aucune opération n'y figure."""
    txs = [{"date": "2024-05-01"}, {"date": "2025-03-01"}]
    out = annees_disponibles(txs)
    an = date.today().strftime("%Y")
    assert out[0] == "all"
    assert out[1:] == sorted({"2024", "2025", an}, reverse=True)


def test_mois_disponibles_dune_annee():
    txs = [{"date": "2025-03-01"}, {"date": "2025-08-15"}, {"date": "2024-12-01"}]
    assert mois_disponibles(txs, "2025") == [MOIS_TOUS, "2025-08", "2025-03"]


def test_mois_disponibles_propose_toujours_le_mois_en_cours():
    courant = date.today().strftime("%Y-%m")
    out = mois_disponibles([], courant[:4])
    assert out == [MOIS_TOUS, courant]


def test_periode_voisine_traverse_les_annees():
    """Les flèches se déplacent à échelle constante — un mois reste un mois —
    et passent d'une année à l'autre : de janvier à décembre précédent."""
    txs = [{"date": "2025-12-10"}, {"date": "2026-01-10"}, {"date": "2026-02-10"}]
    assert periode_voisine(txs, "2026-01", -1) == "2025-12"
    assert periode_voisine(txs, "2026-01", +1) == "2026-02"
    assert periode_voisine(txs, "2025-12", -1) is None      # plus rien avant
    # Sur une année, on se déplace d'année en année.
    assert periode_voisine(txs, "2026", -1) == "2025"
    # « Toutes périodes » n'a ni précédent ni suivant : les deux flèches
    # se grisent.
    assert periode_voisine(txs, "all", -1) is None
    assert periode_voisine(txs, "all", +1) is None


def test_periode_voisine_suit_le_mode_date():
    # Achat carte du 28/07 débité le 04/08 : en « date de valeur », le mois
    # voisin de juin est août, pas juillet.
    txs = [{"date": "2026-06-10", "date_valeur": "2026-07-04"},
           {"date": "2026-07-28", "date_valeur": "2026-08-04"}]
    assert periode_voisine(txs, "2026-06", +1, "operation") == "2026-07"
    assert periode_voisine(txs, "2026-07", +1, "valeur") == "2026-08"


def test_date_debit_differe():
    # Achats du mois M → prélevés le 4 du mois M+1
    assert date_debit_differe("2026-07-15") == "2026-08-04"
    assert date_debit_differe("2026-07-01") == "2026-08-04"
    assert date_debit_differe("2026-08-02") == "2026-09-04"   # début de mois : M+1, pas le 04/08
    assert date_debit_differe("2026-12-20") == "2027-01-04"   # passage d'année
    # Jour personnalisé, y compris au-delà du dernier jour du mois
    assert date_debit_differe("2026-01-10", jour=6) == "2026-02-06"
    assert date_debit_differe("2026-01-10", jour=31) == "2026-02-28"
    # Entrée illisible → renvoyée telle quelle, jamais d'exception
    assert date_debit_differe("") == ""
    assert date_debit_differe("pas une date") == "pas une date"


def test_suggest_category():
    assert suggest_category("EDF facture electricite") == "Logement - maison"
    assert suggest_category("CARREFOUR MARKET") == "Alimentation"
    assert suggest_category("libellé sans motif connu") is None


def test_suggest_category_motifs_ambigus():
    # Corrections des motifs qui se chevauchaient (audit du 31/07/2026)
    assert suggest_category("TOTALENERGIES SA") == "Logement - maison"
    assert suggest_category("TOTAL ACCESS") == "Transports"
    # TotalEnergies vend l'électricité ET l'essence (audit du 23/09/2026) :
    # la facture se reconnaît au prélèvement ou à ses mots, la station au
    # reste — un plein partait en Logement.
    assert suggest_category("PRLV SEPA TOTALENERGIES ELECTRICITE ET GAZ FRANCE") == "Logement - maison"
    assert suggest_category("PRLV SEPA TotalEnergies Clients") == "Logement - maison"
    assert suggest_category("PRELEVEMENT TOTALENERGIES") == "Logement - maison"
    assert suggest_category("TOTAL DIRECT ENERGIE") == "Logement - maison"
    assert suggest_category("CARTE X1234 01/09 TOTALENERGIES") == "Transports"
    assert suggest_category("CB TOTALENERGIES 12/09") == "Transports"
    assert suggest_category("RELAIS TOTAL ENERGIES A7") == "Transports"
    assert suggest_category("BOULANGERIE DUPONT") == "Alimentation"
    assert suggest_category("BOULANGER 4521") == "Shopping"   # l'enseigne
    # « remboursement » ne bascule plus en Revenus : la convention est de le
    # classer dans la catégorie de la dépense d'origine.
    assert suggest_category("REMBOURSEMENT SAMSE") is None
    # « BP » (2 lettres) n'attrape plus la Banque Populaire
    assert suggest_category("BANQUE BP") is None


def test_rotation_ne_touche_pas_aux_sauvegardes_manuelles(tmp_path, monkeypatch):
    """La rotation ne doit compter et supprimer que les sauvegardes
    AUTOMATIQUES (« comptes-AAAA-MM-JJ.db »).

    Le tri est lexicographique : « comptes-avant-truc.db » passe APRÈS
    « comptes-2026-09-08.db » (a > 2). Dix copies manuelles dans le dossier
    suffisaient donc à faire supprimer, à chaque lancement, la sauvegarde du
    jour qui venait d'être créée — le filet de sécurité disparaissait sans
    rien dire.
    """
    import comptesbudget.utils as u

    # backup_db range TOUJOURS ses copies dans _data_dir() — pas à côté du
    # fichier qu'on lui passe. Sans cette redirection, le test écrirait dans
    # le dossier « sauvegardes » du projet.
    monkeypatch.setattr(u, "_data_dir", lambda: str(tmp_path))
    backup_db = u.backup_db

    base = tmp_path / "comptes.db"
    base.write_bytes(b"donnees")
    dossier = tmp_path / "sauvegardes"
    dossier.mkdir()
    manuelles = [f"comptes-avant-essai-{i}.db" for i in range(10)]
    for nom in manuelles:
        (dossier / nom).write_bytes(b"copie manuelle")

    dest = backup_db(str(base), keep=10)
    assert dest is not None
    restants = sorted(p.name for p in dossier.iterdir())
    # La sauvegarde du jour est là...
    assert os.path.basename(dest) in restants
    # ...et aucune copie manuelle n'a été emportée.
    for nom in manuelles:
        assert nom in restants


# ── Sauvegardes : plus de recul, et un échec qui se voit (audit 23/09/2026) ──

def test_rotation_garde_la_premiere_copie_de_chaque_mois():
    """Dix copies quotidiennes ne couvraient que dix jours d'ouverture :
    une erreur vue trois semaines plus tard n'avait plus de copie saine.
    On garde en plus la première copie de chacun des 12 derniers mois."""
    from comptesbudget.utils import sauvegardes_a_garder
    noms = [f"comptes-{a}-{m:02d}-{j:02d}.db"
            for a, m in [(2025, mm) for mm in range(6, 13)]
                        + [(2026, mm) for mm in range(1, 10)]
            for j in (3, 20)]
    noms += [f"comptes-2026-09-{j:02d}.db" for j in range(21, 31)]
    garder = sauvegardes_a_garder(noms, keep=10, mois=12)
    # Les dix plus récentes…
    assert set(sorted(noms)[-10:]) <= garder
    # …et la première copie de chaque mois, d'octobre 2025 à septembre 2026.
    for a, m in [(2025, 10), (2025, 11), (2025, 12)] + [(2026, mm) for mm in range(1, 10)]:
        assert f"comptes-{a}-{m:02d}-03.db" in garder
    # Rien de plus : ni les mois plus anciens, ni les copies du 20.
    assert "comptes-2025-09-03.db" not in garder
    assert "comptes-2026-05-20.db" not in garder
    assert len(garder) == 10 + 12


def test_echec_de_sauvegarde_n_est_plus_muet(tmp_path, monkeypatch):
    """Disque plein, droits refusés : la sauvegarde du jour échouait sans un
    mot. L'erreur remonte maintenant avec sa cause."""
    import pytest
    import comptesbudget.utils as u
    monkeypatch.setattr(u, "_data_dir", lambda: str(tmp_path))
    base = tmp_path / "comptes.db"
    base.write_bytes(b"donnees")

    def disque_plein(*a, **k):
        raise OSError(28, "Il n'y a plus d'espace disponible sur le disque")
    monkeypatch.setattr(u.shutil, "copy2", disque_plein)
    with pytest.raises(u.SauvegardeImpossible) as err:
        u.backup_db(str(base))
    # La cause, dite en français par erreurs.py (26/09/2026) plutôt que
    # recopiée depuis le message d'origine.
    assert "disque est plein" in str(err.value)
    # Pas encore de base (premier lancement) : rien à sauvegarder, sans erreur.
    assert u.backup_db(str(tmp_path / "absente.db")) is None


# ── Lot « autres utilisateurs » (26/09/2026) : classement trop large ──

def test_suggest_category_mots_trop_courants():
    # Ces mots se rencontrent dans des libellés sans rapport avec la catégorie.
    assert suggest_category("PAIEMENT MOBILE 12/09 LIBRAIRIE") is None
    assert suggest_category("REMBOURSEMENT TOTAL COMMANDE 4521") is None
    assert suggest_category("CHEZ LULU COIFFURE") is None
    assert suggest_category("MAISON DE LA PRESSE") is None
    # Les vrais cas restent reconnus.
    assert suggest_category("FREE MOBILE") == "Logement - maison"
    assert suggest_category("TOTAL ACCESS") == "Transports"
    assert suggest_category("MAISONS DU MONDE") == "Logement - maison"


def test_suggest_category_revenus_seulement_pour_une_rentree():
    # Un salaire versé par virement dont le libellé cite la banque partait
    # en « Banque et assurances » ; une pension VERSÉE partait en Revenus.
    assert suggest_category("VIR SEPA SALAIRE SEPTEMBRE BNP",
                            montant=1500.0) == "Revenus"
    assert suggest_category("PENSION ALIMENTAIRE", montant=-300.0) is None
    # Un virement reçu peut être un remboursement d'un proche : à trancher
    # par l'utilisateur, pas un revenu d'office.
    assert suggest_category("VIREMENT RECU DE M DUPONT", montant=50.0) is None
