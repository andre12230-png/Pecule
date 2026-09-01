"""Tests de l'import des fichiers OFX (lecture + bout en bout)."""
import pytest

from comptesbudget.database import Database
from comptesbudget.ofx_import import (
    champ, import_ofx, import_ofx_text, lire_ofx, parse_date_ofx,
    parse_montant_ofx, type_operation,
)


# Relevé de COMPTE, format 1.x (SGML) tel que l'exportent les banques
# françaises : les balises simples n'y sont pas refermées.
_OFX_COMPTE = """OFXHEADER:100
DATA:OFXSGML
VERSION:102
<OFX>
<BANKMSGSRSV1>
<STMTRS>
<CURDEF>EUR
<BANKACCTFROM>
<ACCTID>04210755852</ACCTID>
</BANKACCTFROM>
<BANKTRANLIST>
<DTSTART>20260801
<DTEND>20260831
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260831
<TRNAMT>-34.99
<FITID>2101260002
<CHECKNUM>2623984G1015
<NAME>BOUYGUES TELECOM
<MEMO>PRLV Bouygues Telecom 2623984G10152224
</STMTTRN>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20260807
<TRNAMT>+1160.16
<FITID>2084568278
<CHECKNUM>REFERENCE
<NAME>CARSAT SUD EST
<MEMO>VIR SEPA CARSAT SUD EST ASSURANCE RETRAITE 12426971
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260804
<TRNAMT>-1016.31
<FITID>2081133335
<NAME>DEBIT DIFFERE N 7209
<MEMO>CUMUL DES DEBITS DIFFERES
</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL>
<BALAMT>+398.15
<DTASOF>20260901
</LEDGERBAL>
</STMTRS>
</BANKMSGSRSV1>
</OFX>
"""

# Relevé de CARTE à débit différé : les achats sont prélevés ensemble le 4 du
# mois qui suit la fin du relevé.
_OFX_CARTE = """OFXHEADER:100
<OFX>
<CREDITCARDMSGSRSV1>
<CCSTMTRS>
<CCACCTFROM>
<ACCTID>142650060004210755852</ACCTID>
</CCACCTFROM>
<BANKTRANLIST>
<DTSTART>20260801
<DTEND>20260831
<STMTTRN>
<TRNTYPE>POS
<DTPOSTED>20260825
<TRNAMT>-27.07
<FITID>202609041
<CHECKNUM>REFERENCE
<NAME>CENTRE LECLERC
<MEMO>E LECLERC WEB FR ST ETIENNE D
</STMTTRN>
</BANKTRANLIST>
</CCSTMTRS>
</CREDITCARDMSGSRSV1>
</OFX>
"""


# ── Montants ────────────────────────────────────────────────────────────────

def test_montant_point_ou_virgule():
    assert parse_montant_ofx("-34.99") == -34.99
    assert parse_montant_ofx("+52,51") == 52.51
    assert parse_montant_ofx("1160.16") == 1160.16


def test_montant_illisible():
    assert parse_montant_ofx("") is None
    assert parse_montant_ofx("abc") is None
    assert parse_montant_ofx(None) is None


# ── Dates ───────────────────────────────────────────────────────────────────

def test_date_simple():
    assert parse_date_ofx("20260831") == "31/08/2026"


def test_date_avec_heure_et_fuseau():
    # La norme autorise l'heure et le fuseau derrière la date : on n'en tient
    # pas compte, seul le jour compte pour un relevé.
    assert parse_date_ofx("20260831120000") == "31/08/2026"
    assert parse_date_ofx("20260831120000.000[+1:CET]") == "31/08/2026"


def test_date_illisible():
    assert parse_date_ofx("") is None
    assert parse_date_ofx("2026") is None
    assert parse_date_ofx("20261331") is None      # treizième mois


# ── Lecture des balises, versions 1.x et 2.x ────────────────────────────────

def test_champ_balise_non_refermee_sgml():
    assert champ("<TRNAMT>-34.99\n<FITID>21012\n", "TRNAMT") == "-34.99"


def test_champ_balise_refermee_xml():
    assert champ("<TRNAMT>-34.99</TRNAMT>", "TRNAMT") == "-34.99"


def test_champ_absent():
    assert champ("<TRNAMT>-34.99\n", "MEMO") == ""


def test_lecture_ofx_version_2_en_xml():
    """La 2.x est du XML : tout est refermé, sur une seule ligne ou non."""
    xml = ('<?xml version="1.0"?><OFX><BANKMSGSRSV1><STMTRS>'
           '<BANKACCTFROM><ACCTID>123</ACCTID></BANKACCTFROM>'
           '<BANKTRANLIST><STMTTRN><TRNTYPE>DEBIT</TRNTYPE>'
           '<DTPOSTED>20260812</DTPOSTED><TRNAMT>-113.29</TRNAMT>'
           '<FITID>abc</FITID><NAME>OCTOPUS ENERGY</NAME>'
           '</STMTTRN></BANKTRANLIST></STMTRS></BANKMSGSRSV1></OFX>')
    operations, comptes, illisibles = lire_ofx(xml)
    assert (len(operations), comptes, illisibles) == (1, ["123"], 0)
    assert operations[0].date == "12/08/2026"
    assert operations[0].montant == -113.29


# ── Type d'opération ────────────────────────────────────────────────────────

def test_type_prelevement():
    assert type_operation("BOUYGUES TELECOM", "PRLV Bouygues Telecom 26239",
                          "DEBIT", -34.99) == "Prelevement"


def test_type_virement_recu_selon_le_sens():
    assert type_operation("CPAM", "VIR SEPA CPAM ARDECHE", "CREDIT",
                          4.41) == "Virement recu"
    assert type_operation("VIREMENT VERS CPT DEPOT PART", "", "DEBIT",
                          -55.0) == "Virement"


def test_type_pret_et_frais():
    assert type_operation("ECHEANCE DE CREDIT", "ECH PRET 5600445", "DEBIT",
                          -826.96) == "Pret"
    assert type_operation("COTISATIONS BANCAIRES", " OFFRE CONFORT", "DEBIT",
                          -16.20) == "Frais bancaires"


def test_type_frais_avant_carte():
    """« COM CB INT » contient « CB » : les frais doivent l'emporter."""
    assert type_operation("FRAIS BANCAIRES", " COM CB INT ANTHROPIC CLAU",
                          "DEBIT", -1.03) == "Frais bancaires"


def test_type_retraite_n_est_pas_un_retrait():
    """Les motifs sont cherchés comme des mots entiers : sans cela, la
    pension de la Carsat (« ASSURANCE RETRAITE ») partait en retrait
    d'espèces."""
    assert type_operation("CARSAT SUD EST",
                          "VIR SEPA CARSAT SUD EST ASSURANCE RETRAITE",
                          "CREDIT", 1160.16) == "Virement recu"


def test_type_remboursement_carte_n_est_pas_un_paiement_carte():
    """Sur un relevé de COMPTE, une somme reçue n'est jamais un paiement par
    carte : « CB AMAZON » créditeur est un remboursement."""
    assert type_operation("CB AMAZON", "CB AMAZON PAYMENTS", "CREDIT",
                          22.89) == "Virement recu"


def test_type_sur_un_releve_de_carte():
    """Sur un relevé de CARTE, tout est paiement par carte — y compris un
    remboursement, qui doit être défalqué au jour du débit groupé."""
    assert type_operation("AMAZON", "AMAZON PAYMENTS", "POS", -66.90,
                          releve_carte=True) == "Carte bancaire"
    assert type_operation("AMAZON", "AMAZON PAYMENTS", "POS", 12.00,
                          releve_carte=True) == "Carte bancaire"


def test_type_deduit_du_trntype_a_defaut_de_libelle():
    assert type_operation("MONOPRIX", "MONOPRIX PARIS", "POS",
                          -12.0) == "Carte bancaire"
    assert type_operation("", "", "CHECK", -100.0) == "Cheque"
    # DEBIT et CREDIT ne disent rien de plus que le montant : pas de type.
    assert type_operation("QUELQUE CHOSE", "", "DEBIT", -10.0) == ""


# ── Lecture d'un relevé complet ─────────────────────────────────────────────

def test_lecture_releve_de_compte():
    operations, comptes, illisibles = lire_ofx(_OFX_COMPTE)
    assert (len(operations), comptes, illisibles) == (3, ["04210755852"], 0)
    op = operations[0]
    assert op.date == "31/08/2026"
    assert op.date_valeur == "31/08/2026"      # pas de débit différé ici
    assert op.montant == -34.99
    assert op.libelle == "BOUYGUES TELECOM"
    assert op.reference == "2101260002"        # le FITID de la banque
    assert op.type == "Prelevement"
    assert op.info == "PRLV Bouygues Telecom 2623984G10152224"


def test_lecture_numero_de_reference_bidon_ecarte():
    """La BPCE écrit le mot « REFERENCE » quand elle n'en a pas : ce n'en est
    pas une, elle n'a rien à faire dans la note."""
    operations, _, _ = lire_ofx(_OFX_COMPTE)
    carsat = next(o for o in operations if o.montant == 1160.16)
    assert "REFERENCE" not in carsat.info


def test_lecture_releve_de_carte_date_du_debit_groupe():
    """Les achats d'un relevé de carte sont débités le 4 du mois qui suit la
    FIN du relevé, pas un mois après chaque achat."""
    operations, comptes, _ = lire_ofx(_OFX_CARTE)
    assert len(operations) == 1
    assert operations[0].date == "25/08/2026"
    assert operations[0].date_valeur == "04/09/2026"
    assert operations[0].type == "Carte bancaire"
    # Le numéro de la carte n'est pas un second compte bancaire.
    assert comptes == []


def test_lecture_achat_de_fin_de_mois_precedent():
    """Un achat du 31/07 que la banque n'a comptabilisé qu'en août est
    débité le 4 septembre, avec les autres achats du relevé d'août — et non
    le 4 août, comme le donnerait sa seule date d'achat."""
    carte = _OFX_CARTE.replace("<DTPOSTED>20260825", "<DTPOSTED>20260731")
    operations, _, _ = lire_ofx(carte)
    assert operations[0].date == "31/07/2026"
    assert operations[0].date_valeur == "04/09/2026"


def test_operation_illisible_comptee_et_ecartee():
    abime = _OFX_COMPTE.replace("<TRNAMT>-34.99", "<TRNAMT>abc")
    operations, _, illisibles = lire_ofx(abime)
    assert (len(operations), illisibles) == (2, 1)


# ── Import de bout en bout ──────────────────────────────────────────────────

def test_import_ofx_insere(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    # 2 importées, 0 doublon, 0 illisible, 0 pointée, 1 récapitulatif écarté.
    assert import_ofx_text(_OFX_COMPTE, db) == (2, 0, 0, 0, 1, 0)
    rows = [dict(r) for r in db.list_tx()]
    assert sorted(r["montant"] for r in rows) == [-34.99, 1160.16]
    bouygues = next(r for r in rows if r["montant"] == -34.99)
    assert bouygues["date"] == "2026-08-31"
    assert bouygues["libelle"] == "BOUYGUES TELECOM"
    assert bouygues["type"] == "Prelevement"
    # Un relevé ne porte que des opérations déjà passées en banque.
    assert bouygues["pointee"] == 1


def test_import_ofx_recapitulatif_debit_differe_ecarte(tmp_path):
    """La ligne qui totalise le débit différé ferait doublon avec les achats
    détaillés du relevé de carte : elle n'est jamais importée."""
    db = Database(str(tmp_path / "t.db"))
    import_ofx_text(_OFX_COMPTE, db)
    assert not [r for r in db.list_tx() if r["montant"] == -1016.31]


def test_import_ofx_dedup_au_reimport(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    import_ofx_text(_OFX_COMPTE, db)
    assert import_ofx_text(_OFX_COMPTE, db) == (0, 2, 0, 0, 1, 0)


def test_import_ofx_dedup_meme_apres_renommage(tmp_path):
    """L'identifiant unique de la banque (FITID) survit au renommage des
    libellés : un relevé réimporté ne crée pas de doublon."""
    db = Database(str(tmp_path / "t.db"))
    import_ofx_text(_OFX_COMPTE, db)
    ligne = next(dict(r) for r in db.list_tx() if r["montant"] == -34.99)
    db.update_tx(ligne["id"], {"libelle": "Bouygues Telecom"})
    imported, skipped, _, _, _, _ = import_ofx_text(_OFX_COMPTE, db)
    assert (imported, skipped) == (0, 2)


def test_import_ofx_dedup_avec_un_csv_deja_importe(tmp_path):
    """Une opération déjà venue du CSV ne doit pas revenir par l'OFX."""
    from comptesbudget.csv_import import import_csv_text
    db = Database(str(tmp_path / "t.db"))
    csv = ("Date;Libelle;Montant\n"
           "31/08/2026;BOUYGUES TELECOM;-34,99\n")
    assert import_csv_text(csv, db) == (1, 0, 0, 0, 0, 0)
    imported, skipped, _, _, _, _ = import_ofx_text(_OFX_COMPTE, db)
    assert (imported, skipped) == (1, 1)


def test_import_ofx_applique_les_regles(tmp_path):
    """Les règles de catégorisation valent aussi pour l'OFX : c'est tout
    l'intérêt d'avoir réutilisé la mécanique de l'import CSV."""
    db = Database(str(tmp_path / "t.db"))
    db.insert_rule({"id": "r1", "pattern": "bouygues", "amount": None,
                    "categorie": "Abonnements", "sous_cat": "Internet",
                    "no_overwrite": 0, "created_at": "2026-01-01"})
    import_ofx_text(_OFX_COMPTE, db)
    ligne = next(dict(r) for r in db.list_tx() if r["montant"] == -34.99)
    assert (ligne["categorie"], ligne["sous_cat"]) == ("Abonnements", "Internet")


def test_import_ofx_carte_date_de_valeur_conservee(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    assert import_ofx_text(_OFX_CARTE, db) == (1, 0, 0, 0, 0, 0)
    achat = next(dict(r) for r in db.list_tx())
    assert (achat["date"], achat["date_valeur"]) == ("2026-08-25", "2026-09-04")


def test_import_ofx_fichier_multi_comptes_refuse(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    deux = _OFX_COMPTE + _OFX_COMPTE.replace("04210755852", "04062692527")
    with pytest.raises(ValueError, match="plusieurs comptes"):
        import_ofx_text(deux, db)
    assert list(db.list_tx()) == []


def test_import_ofx_compte_et_sa_carte_acceptes(tmp_path):
    """Le relevé de la carte à débit différé accompagne celui du compte : la
    carte n'est pas un second compte bancaire."""
    db = Database(str(tmp_path / "t.db"))
    imported, _, _, _, _, _ = import_ofx_text(_OFX_COMPTE + _OFX_CARTE, db)
    assert imported == 3


def test_import_ofx_fichier_sans_operation_refuse(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    with pytest.raises(ValueError, match="aucune opération lisible"):
        import_ofx_text("<OFX><SIGNONMSGSRSV1></SIGNONMSGSRSV1></OFX>", db)


def test_import_ofx_depuis_un_fichier_windows_1252(tmp_path):
    """Les banques françaises annoncent CHARSET:1252 dans l'en-tête."""
    db = Database(str(tmp_path / "t.db"))
    p = tmp_path / "releve.ofx"
    p.write_bytes(_OFX_COMPTE.replace("BOUYGUES TELECOM",
                                      "SOCIÉTÉ FRANÇAISE").encode("cp1252"))
    import_ofx(str(p), db)
    assert any(r["libelle"] == "SOCIÉTÉ FRANÇAISE" for r in db.list_tx())
