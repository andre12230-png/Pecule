"""Import des relevés bancaires au format OFX (Open Financial Exchange).

L'OFX est le format que proposent aujourd'hui la plupart des banques
françaises à côté du CSV — et parfois à sa place. C'est le même contenu
qu'un relevé CSV, mais rangé dans des balises plutôt qu'en colonnes :

    <STMTTRN>
    <TRNTYPE>DEBIT
    <DTPOSTED>20260831
    <TRNAMT>-34.99
    <FITID>2101260002
    <NAME>BOUYGUES TELECOM
    <MEMO>PRLV Bouygues Telecom 2623984G10152224
    </STMTTRN>

Deux versions coexistent. La 1.x est écrite en SGML : les balises simples
n'y sont pas refermées, comme ci-dessus. La 2.x est du vrai XML, où tout
est refermé. Le lecteur ci-dessous accepte les deux, car il ne se fie
jamais à la présence d'une balise fermante pour lire une valeur.

Comme pour le QIF (qif_import.py), ce module ne refait pas le travail
d'import : il TRADUIT l'OFX en lignes de relevé, puis confie le résultat à
l'import CSV. Détection des doublons, application des règles, pointage
automatique, rattachement des échéances saisies d'avance : tout est
partagé, et l'OFX profite des corrections passées et futures.

Deux relevés différents peuvent arriver au format OFX :

  - le relevé du COMPTE (<STMTRS>), qui porte les prélèvements, virements
    et frais, plus une ligne récapitulative pour le débit différé de la
    carte — écartée à l'import, les achats étant détaillés par ailleurs ;
  - le relevé de la CARTE à débit différé (<CCSTMTRS>), qui porte les
    achats un par un. Ceux-là ne sont pas débités le jour de l'achat mais
    tous ensemble le 4 du mois suivant : c'est cette date-là qui devient
    leur date de valeur, sans quoi ils pèseraient trop tôt sur le solde.
"""
import csv
import io
import re
from typing import NamedTuple, Optional

# L'import CSV fournit le décodage de fichier (UTF-8 / Windows-1252) et le
# moteur d'import proprement dit : l'OFX s'appuie sur les deux.
from .csv_import import ResultatImport, _decode_csv, import_csv_text
from .database import Database
from .utils import date_debit_differe, deaccent


class OperationOfx(NamedTuple):
    """Une opération lue dans le fichier OFX, avant traduction en relevé."""
    date: str          # jj/mm/aaaa
    date_valeur: str   # jj/mm/aaaa — date à laquelle le compte est débité
    montant: float
    libelle: str
    info: str
    reference: str
    type: str


# ── Lecture des valeurs élémentaires ────────────────────────────────────────

def parse_montant_ofx(s: str) -> Optional[float]:
    """Lit un montant OFX. Retourne None s'il est illisible.

    Contrairement au QIF, l'OFX n'est pas ambigu : la norme interdit le
    séparateur de milliers et accepte le point comme la virgule pour les
    décimales. « -34.99 », « +52,51 » et « 1234.56 » sont donc les seules
    formes à prévoir."""
    if s is None:
        return None
    t = s.strip().replace(" ", "").replace("\xa0", "").replace(",", ".")
    if t.startswith("+"):
        t = t[1:]
    try:
        return float(t)
    except ValueError:
        return None


def parse_date_ofx(s: str) -> Optional[str]:
    """Lit une date OFX et la rend à la forme jj/mm/aaaa attendue par
    l'import CSV. Retourne None si elle est illisible.

    La norme écrit AAAAMMJJ, éventuellement suivi de l'heure et du fuseau
    (« 20260831 », « 20260831120000 », « 20260831120000.000[+1:CET] ») :
    les huit premiers chiffres suffisent."""
    t = (s or "").strip()
    if len(t) < 8 or not t[:8].isdigit():
        return None
    annee, mois, jour = int(t[:4]), int(t[4:6]), int(t[6:8])
    if not (1 <= mois <= 12 and 1 <= jour <= 31 and annee >= 1900):
        return None
    return f"{jour:02d}/{mois:02d}/{annee:04d}"


def champ(bloc: str, nom: str) -> str:
    """Valeur d'une balise dans un fragment d'OFX, quelle que soit la
    version du format : on lit tout ce qui suit la balise ouvrante jusqu'au
    prochain « < » ou à la fin de la ligne. La balise fermante du XML (2.x)
    s'arrête donc au bon endroit, et son absence en SGML (1.x) aussi."""
    m = re.search("<" + nom + r">([^<\r\n]*)", bloc, re.I)
    return m.group(1).strip() if m else ""


# ── Type d'opération ────────────────────────────────────────────────────────

# Le <TRNTYPE> de l'OFX est trop grossier pour Pécule : sur un relevé de
# compte BPCE, il ne vaut jamais que DEBIT ou CREDIT. La nature réelle de
# l'opération, elle, est annoncée en toutes lettres au début du libellé ou
# du mémo — « PRLV », « VIR SEPA », « ECH PRET » — exactement comme dans la
# colonne « Type operation » du CSV. C'est donc là qu'on va la chercher.
#
# L'ordre compte, le premier motif trouvé l'emportant : « FRAIS BANCAIRES »
# passe avant « CB » parce que le mémo d'une commission de carte contient
# les deux (« COM CB INT ANTHROPIC CLAU »).
#
# Les motifs sont cherchés comme des MOTS ENTIERS. Sans cela, « retrait »
# reconnaîtrait « ASSURANCE RETRAITE » et la pension de la Carsat arriverait
# en retrait d'espèces.
TYPES_PAR_MOTIF = [
    ("Frais bancaires",   ("frais bancaires", "cotisations bancaires",
                           "com cb", "commission", "agios")),
    ("Pret",              ("ech pret", "echeance de credit",
                           "echeance pret", "remb pret")),
    ("Prelevement",       ("prlv", "prelevement")),
    ("Cheque",            ("cheque", "chq")),
    ("Retrait d'especes", ("retrait", "dab")),
    ("Depot d'especes",   ("depot especes", "versement especes",
                           "remise especes")),
    ("Carte bancaire",    ("cb", "carte", "paiement carte")),
    ("Virement",          ("vir", "virement")),
]

# Correspondance de secours, quand aucun mot du libellé ne renseigne : les
# codes <TRNTYPE> de la norme OFX. DEBIT et CREDIT n'y sont volontairement
# pas — ils ne disent que le sens, que le montant dit déjà.
TYPES_PAR_TRNTYPE = {
    "check": "Cheque",
    "atm": "Retrait d'especes",
    "cash": "Retrait d'especes",
    "pos": "Carte bancaire",
    "xfer": "Virement",
    "directdebit": "Prelevement",
    "repeatpmt": "Prelevement",
    "payment": "Prelevement",
    "directdep": "Virement recu",
    "dep": "Depot d'especes",
    "fee": "Frais bancaires",
    "srvchg": "Frais bancaires",
}


def type_operation(libelle: str, memo: str, trntype: str, montant: float,
                   releve_carte: bool = False) -> str:
    """Type d'opération Pécule (cf. TYPES_OPERATION) déduit du relevé.

    Sur un relevé de CARTE, toutes les lignes sont des paiements par carte,
    y compris un éventuel remboursement de commerçant : c'est ce type qui
    fait porter la dépense à la date du débit groupé, il ne faut pas le
    perdre. Sur un relevé de COMPTE au contraire, une somme reçue n'est
    jamais un paiement par carte — un « CB AMAZON » créditeur est un
    remboursement, que l'usage d'André range en virement reçu."""
    if releve_carte:
        return "Carte bancaire"

    texte = deaccent(libelle + " " + memo)
    trouve = ""
    for type_pecule, motifs in TYPES_PAR_MOTIF:
        if any(re.search(r"\b" + re.escape(m) + r"\b", texte) for m in motifs):
            trouve = type_pecule
            break
    if not trouve:
        trouve = TYPES_PAR_TRNTYPE.get(deaccent(trntype).strip(), "")

    if montant > 0:
        if trouve == "Virement":
            return "Virement recu"
        if trouve == "Carte bancaire":
            return "Virement recu"
    return trouve


# ── Lecture du fichier ──────────────────────────────────────────────────────

_RE_RELEVE_COMPTE = re.compile(r"<STMTRS>(.*?)</STMTRS>", re.S | re.I)
_RE_RELEVE_CARTE = re.compile(r"<CCSTMTRS>(.*?)</CCSTMTRS>", re.S | re.I)
_RE_OPERATION = re.compile(r"<STMTTRN>(.*?)</STMTTRN>", re.S | re.I)


def _releves(text: str) -> list[tuple[str, bool]]:
    """Découpe le fichier en relevés : (contenu, est-ce un relevé de carte).

    Un même fichier peut en contenir plusieurs — le relevé du compte et
    celui de sa carte, par exemple."""
    trouves = [(m.group(1), True) for m in _RE_RELEVE_CARTE.finditer(text)]
    trouves += [(m.group(1), False) for m in _RE_RELEVE_COMPTE.finditer(text)]
    if trouves:
        return trouves
    # Fichier réduit à une liste d'opérations, sans l'enveloppe habituelle :
    # on le traite comme un relevé de compte plutôt que de le refuser.
    return [(text, False)] if _RE_OPERATION.search(text) else []


def lire_ofx(text: str) -> tuple[list[OperationOfx], list[str], int]:
    """Lit le contenu d'un fichier OFX.

    Retourne (opérations, comptes rencontrés, nombre d'opérations écartées).
    Une opération est écartée quand sa date ou son montant sont illisibles :
    mieux vaut la signaler que l'enregistrer avec une valeur fausse."""
    operations: list[OperationOfx] = []
    comptes: list[str] = []
    illisibles = 0

    for contenu, releve_carte in _releves(text):
        numero = champ(contenu, "ACCTID")
        # Le relevé de carte porte le numéro de la carte, pas celui du
        # compte : il ne compte pas comme un second compte (en France, une
        # carte à débit différé est adossée au compte courant).
        if numero and not releve_carte and numero not in comptes:
            comptes.append(numero)

        # Toutes les opérations d'un relevé de carte sont débitées ensemble,
        # le 4 du mois qui suit la FIN du relevé. Se fier à la date de chaque
        # achat serait faux pour ceux de la fin du mois précédent, que la
        # banque n'a comptabilisés qu'après la clôture (un achat du 31/07
        # figurant au relevé d'août est débité le 4 septembre).
        fin = parse_date_ofx(champ(contenu, "DTEND"))
        debit_groupe = ""
        if releve_carte and fin:
            j, m, a = fin.split("/")
            iso = date_debit_differe(f"{a}-{m}-{j}")
            debit_groupe = f"{iso[8:10]}/{iso[5:7]}/{iso[0:4]}"

        for m in _RE_OPERATION.finditer(contenu):
            bloc = m.group(1)
            d = parse_date_ofx(champ(bloc, "DTPOSTED"))
            montant = parse_montant_ofx(champ(bloc, "TRNAMT"))
            if d is None or montant is None:
                illisibles += 1
                continue

            nom = champ(bloc, "NAME")
            memo = champ(bloc, "MEMO")
            libelle = nom or memo or "(sans libellé)"

            # Le mémo sert de note, sauf s'il ne fait que répéter le libellé.
            info = "" if deaccent(memo) == deaccent(nom) else memo
            # Le numéro de chèque (ou la référence interne de la banque)
            # complète la note quand il n'y figure pas déjà. La BPCE écrit
            # le mot « REFERENCE » quand elle n'en a pas : ce n'en est pas une.
            checknum = champ(bloc, "CHECKNUM")
            if (checknum and deaccent(checknum) != "reference"
                    and checknum not in info and checknum not in libelle):
                info = (info + " " + checknum).strip()

            # Date de valeur : celle que la banque annonce (<DTAVAIL>), sinon
            # le débit groupé de la carte, sinon le jour de l'opération.
            date_valeur = parse_date_ofx(champ(bloc, "DTAVAIL")) or debit_groupe or d

            operations.append(OperationOfx(
                date=d,
                date_valeur=date_valeur,
                montant=montant,
                libelle=libelle,
                info=info,
                # <FITID> est l'identifiant unique et stable que la banque
                # attribue à l'opération : c'est exactement ce qu'il faut
                # pour reconnaître un relevé déjà importé, même si le
                # libellé a été renommé depuis.
                reference=champ(bloc, "FITID"),
                type=type_operation(nom, memo, champ(bloc, "TRNTYPE"),
                                    montant, releve_carte),
            ))
    return operations, comptes, illisibles


# ── Traduction en relevé et import ──────────────────────────────────────────

# En-têtes attendus par l'import CSV : ce sont eux qui lui permettent de
# reconnaître chaque colonne par son nom (cf. find_col dans csv_import).
EN_TETES = ["Date", "Date de valeur", "Libelle simplifie", "Montant",
            "Categorie", "Sous categorie", "Reference", "Informations",
            "Type operation", "Pointage operation"]


def ofx_vers_csv(operations: list[OperationOfx]) -> str:
    """Écrit les opérations OFX sous la forme d'un relevé CSV en mémoire.

    Passer par le CSV plutôt que d'insérer directement en base n'est pas un
    détour inutile : c'est ce qui permet à l'OFX de bénéficier sans effort
    de toute la mécanique d'import déjà éprouvée."""
    tampon = io.StringIO()
    ecrivain = csv.writer(tampon, delimiter=";", lineterminator="\n")
    ecrivain.writerow(EN_TETES)
    for op in operations:
        ecrivain.writerow([
            op.date,
            op.date_valeur,
            op.libelle,
            f"{op.montant:.2f}",
            "",                    # l'OFX ne transporte pas de catégorie
            "",
            op.reference,
            op.info,
            op.type,
            # Un relevé ne porte que des opérations déjà passées en banque :
            # toutes sont donc pointées (colonne « x » du CSV BPCE).
            "x",
        ])
    return tampon.getvalue()


def import_ofx(path: str, db: Database) -> ResultatImport:
    """Lit un fichier OFX et insère les opérations. Même compte rendu que
    l'import CSV (cf. ResultatImport)."""
    with open(path, "rb") as f:
        return import_ofx_text(_decode_csv(f.read()), db)


def import_ofx_text(text: str, db: Database) -> ResultatImport:
    """Cœur de l'import OFX, séparé pour pouvoir être testé sans fichier."""
    operations, comptes, illisibles = lire_ofx(text)

    # Chaque compte de Pécule a ses propres opérations, son solde et son
    # budget : importer deux comptes bancaires dans le compte affiché
    # fausserait les trois. Mieux vaut refuser franchement que produire des
    # chiffres faux. (La carte à débit différé, elle, appartient bien au
    # compte courant : elle n'est pas comptée comme un second compte.)
    if len(comptes) > 1:
        raise ValueError(
            "ce fichier contient plusieurs comptes (" + ", ".join(comptes)
            + "). Pécule importe dans le compte affiché : téléchargez un "
            "compte à la fois depuis le site de votre banque.")
    if not operations:
        raise ValueError(
            "aucune opération lisible dans ce fichier OFX. Vérifiez qu'il "
            "s'agit bien d'un relevé de compte ou de carte téléchargé "
            "depuis votre banque.")

    resultat = import_csv_text(ofx_vers_csv(operations), db)
    # Les opérations OFX écartées faute de date ou de montant s'ajoutent à
    # celles que l'import CSV a lui-même refusées.
    return resultat._replace(illisibles=resultat.illisibles + illisibles)
