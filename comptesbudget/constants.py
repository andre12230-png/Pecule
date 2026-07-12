"""Constantes et données de configuration (catégories, couleurs, règles)."""
import os
import re
import sys

def _app_dir() -> str:
    """Dossier de l'application : à côté du .exe en mode gelé, sinon le dossier
    racine du projet — celui du lanceur comptes_budget.py, où se trouvent
    comptes.db, Budget.ico et le dossier des sauvegardes."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    # Ce module est dans comptesbudget/ ; on remonte d'un cran vers la racine.
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_PATH = os.path.join(_app_dir(), "comptes.db")

# Fichier d'échange JSON (historique). La synchronisation automatique avec
# l'application HTML a été retirée en 1.9.5 (l'app HTML est archivée dans
# archive/) ; le moteur de fusion plus bas est conservé : il permettrait de
# réimporter/fusionner un tel fichier si besoin.
SYNC_PATH = os.path.join(_app_dir(), "comptes_sync.json")
SYNC_VERSION = 2


# Version applicative — incrémentée à chaque amélioration
# 1.8.0 : onglet Sous-catégories, pré-remplissage du prévisionnel depuis
#         l'historique, harmonisation des libellés, autocomplétion et
#         pré-remplissage intelligent des formulaires, héritage de la
#         catégorie/sous-catégorie à l'import CSV.
# 1.9.0 : synchronisation automatique via fichier partagé (OneDrive) avec
#         fusion par enregistrement (dernière modification gagne), horodatage
#         et pierres tombales pour propager les suppressions.
# 1.9.1 : le solde initial et la date initiale sont aussi synchronisés
#         (fusion par horodatage).
# 1.9.2 : (app HTML) mise en page mobile responsive — version alignée.
# 1.9.4 : sauvegarde quotidienne automatique de la base dans « sauvegardes/ »
#         (au lancement, rotation sur 10 jours).
# 1.9.5 : retrait de l'application HTML et de la synchronisation automatique
#         (app HTML archivée dans archive/ ; moteur de fusion conservé dormant).
# 1.9.6 : alertes budget sur le Bilan — bandeau rouge/orange quand une
#         catégorie dépasse (ou approche à 85 %) son budget du mois en cours.
# 1.9.7 : rapport mensuel imprimable (🖨 dans la barre d'outils) — synthèse,
#         budgets, dépenses par catégorie, top dépenses ; aperçu, PDF, papier.
# 1.9.8 : recherche globale (🔎 / Ctrl+F) dans tout l'historique — libellé,
#         note, catégorie, montant, date ; double-clic pour modifier.
# 1.9.9 : correctif — la touche Entrée ne ferme plus la recherche globale
#         (et ne déclenche plus de bouton par accident dans le rapport).
# 1.10.0 : les règles distinguent débit/crédit (champ « Sens ») — un
#          remboursement ne retombe plus dans la catégorie de dépense ;
#          règles existantes reclassées (Revenus→crédit, autres→débit),
#          « Mémoriser » hérite du sens de l'opération.
# 1.10.1 : solde de départ non pré-rempli (invite au 1er lancement) ;
#          notice intégrée mise à jour (onglet Sous-catégories, recherche
#          globale, rapport mensuel, harmonisation des libellés).
# 1.11.0 : interface — les actions passent dans un menu vertical à gauche
#          (au lieu de la barre d'outils horizontale) ; raccourci Ctrl+F
#          conservé. Aligne la disposition sur les interfaces native et Qt.
# 1.12.0 : import CSV — encodage UTF-8 reconnu, montants illisibles signalés
#          (jamais enregistrés à 0 €), écritures groupées (~70× plus rapide) ;
#          recherche des montants et dates dans l'onglet Opérations, saisie
#          « comme à l'écran » (-45,30 €) acceptée partout ; Doublons avec
#          liste de vérification à cocher avant suppression ; export JSON
#          complet (réglages inclus) + nouveau bouton « Restaurer (JSON) » ;
#          budget annuel au prorata des mois couverts ; validation aussi à
#          la modification d'une opération ; notice et glossaire à jour.
# 1.12.1 : correctif IMPORTANT de l'import CSV — les opérations saisies à la
#          main (sans référence bancaire) étaient réimportées en double
#          depuis le relevé (la détection ne comparait que la référence).
#          Doublon désormais reconnu par référence OU par libellé nettoyé.
#          Les catégories des exports BPCE (« A categoriser… », « Revenus et
#          rentrees d'argent »…) sont ramenées aux catégories de l'app.
# 1.13.0 : pointage automatique à l'import — si le relevé contient une
#          colonne « Pointage » (« x » = passée en banque, format BPCE),
#          les nouvelles opérations arrivent pointées et les opérations
#          déjà enregistrées sont confirmées (jamais dépointées). L'import
#          annonce le nombre d'opérations pointées automatiquement.
APP_VERSION = "1.13.0"

CATEGORIES_DEFAUT = [
    "Alimentation", "Transports", "Logement - maison", "Santé",
    "Loisirs", "Shopping", "Abonnements", "Banque et assurances",
    "Impôts et taxes", "Famille", "Cadeaux et dons",
    "Revenus", "Épargne", "Retraits / dépôts", "Virements internes",
    "Transaction exclue", "Non classé",
]

CATEGORY_COLORS = {
    "Alimentation":          "#E67E22",
    "Transports":            "#3498DB",
    "Logement - maison":     "#8B4513",
    "Santé":                 "#E91E63",
    "Loisirs":               "#9B59B6",
    "Shopping":              "#1ABC9C",
    "Abonnements":           "#2980B9",
    "Banque et assurances":  "#34495E",
    "Impôts et taxes":       "#7F0000",
    "Famille":               "#FF69B4",
    "Cadeaux et dons":       "#E74C3C",
    "Revenus":               "#27AE60",
    "Épargne":               "#16A085",
    "Retraits / dépôts":     "#95A5A6",
    "Virements internes":    "#BDC3C7",
    "Transaction exclue":    "#7F8C8D",
    "Non classé":            "#8A877F",
}

# Normalisation : variantes accentuées / banques → forme canonique
CANONICAL_CATS = {
    "alimentation": "Alimentation",
    "alimentation et restauration": "Alimentation",
    "transports": "Transports",
    "transport": "Transports",
    "transports et deplacements": "Transports",
    "logement": "Logement - maison",
    "logement - maison": "Logement - maison",
    "maison": "Logement - maison",
    "sante": "Santé",
    "santé": "Santé",
    "loisirs": "Loisirs",
    "loisirs et culture": "Loisirs",
    "shopping": "Shopping",
    "achats": "Shopping",
    "abonnements": "Abonnements",
    "banque": "Banque et assurances",
    "banque et assurances": "Banque et assurances",
    "assurances": "Banque et assurances",
    "impots": "Impôts et taxes",
    "impôts": "Impôts et taxes",
    "impots et taxes": "Impôts et taxes",
    "impôts et taxes": "Impôts et taxes",
    "famille": "Famille",
    "cadeaux": "Cadeaux et dons",
    "cadeaux et dons": "Cadeaux et dons",
    "revenus": "Revenus",
    "salaire": "Revenus",
    "epargne": "Épargne",
    "épargne": "Épargne",
    "retraits": "Retraits / dépôts",
    "retraits / depots": "Retraits / dépôts",
    "retraits / dépôts": "Retraits / dépôts",
    "virements internes": "Virements internes",
    "transaction exclue": "Transaction exclue",
    "non classe": "Non classé",
    "non classé": "Non classé",
    # Catégories des exports BPCE : sans correspondance, elles créaient des
    # catégories parasites (« A categoriser - sortie d'argent »…) à l'import.
    # Ramenées à « Non classé », elles laissent les règles et les profils de
    # libellés faire la catégorisation.
    "a categoriser - sortie d'argent": "Non classé",
    "a categoriser - rentree d'argent": "Non classé",
    "revenus et rentrees d'argent": "Revenus",
    "loisirs et vacances": "Loisirs",
    "shopping et services": "Shopping",
}

TYPES_OPERATION = [
    "", "Carte bancaire", "Virement", "Virement recu", "Prelevement",
    "Pret", "Cheque", "Retrait d'especes", "Depot d'especes",
    "Frais bancaires", "Autre",
]

# Règles d'harmonisation : on lit (libellé + sous-catégorie) sans accents,
# première regex qui matche → catégorie canonique.
HARMONIZE_RULES = [
    # Logement
    (r"\b(loyer|edf|engie|enedis|gdf|veolia|suez|eau|gaz|electric|chauffage|copropriete|syndic|sfr|orange|free|bouygues|telephon|internet|fibre|adsl|mobile)\b", "Logement - maison"),
    (r"\b(brico|leroy[\s-]?merlin|castorama|ikea|conforama|but|maison|ameublement|mobilier|jardin)\b", "Logement - maison"),
    # Transports
    (r"\b(carburant|station|essence|total|shell|esso|bp|avia|intermarche carburant|gazole|sp95|sp98|peage|autoroute|sncf|ratp|tcl|tan|tisseo|stationnement|parking|garage|controle technique|garagiste|entretien vehicule|reparation auto|peugeot|renault|citroen|ford|fiat|vw|volkswagen|assurance auto)\b", "Transports"),
    # Santé
    (r"\b(pharmacie|medecin|docteur|dentist|opticien|hopital|clinique|cpam|mutuelle|harmonie|mgen|laboratoire|kine|kinesi|ostheo|psychologue)\b", "Santé"),
    # Alimentation
    (r"\b(carrefour|leclerc|auchan|intermarche|lidl|aldi|casino|monoprix|super[\s-]?u|hyper[\s-]?u|coop|biocoop|naturalia|grand frais|picard|marche|boulanger\.com|boulanger|patisser|boucher|primeur)\b", "Alimentation"),
    (r"\b(mcdo|mc[\s-]?donald|kfc|burger|quick|subway|pizza|restaur|brasserie|bar|cafe|kebab|sushi|chez|brunch)\b", "Alimentation"),
    # Loisirs
    (r"\b(cinema|cine|netflix|spotify|deezer|prime video|disney|amazon prime|canal|playstation|nintendo|xbox|steam|fnac|cultura|micromania|jeu|cinema|gaumont|ugc|pathe|theatre|concert|musee)\b", "Loisirs"),
    # Shopping
    (r"\b(amazon|cdiscount|fnac|darty|boulanger|zalando|asos|kiabi|h&m|zara|uniqlo|decathlon|intersport|go sport)\b", "Shopping"),
    # Impôts
    (r"\b(dgfip|tresor public|impot|tva|taxe|cfe|tfh)\b", "Impôts et taxes"),
    # Banque / assurances
    (r"\b(bpce|cic|credit agricole|banque postale|caisse epargne|societe generale|sg|bnp|hsbc|lcl|cotisation|frais|agios|commission|maaf|matmut|maif|axa|gmf|allianz|maif|assurance habitation|assurance accident)\b", "Banque et assurances"),
    # Revenus
    (r"\b(salaire|paie|paye|caf|pole emploi|chomage|retraite|pension|remboursement|virement recu)\b", "Revenus"),
    # Épargne
    (r"\b(virement epargne|livret a|ldds|pel|cel|assurance vie|pea|opcvm)\b", "Épargne"),
]
_HARMONIZE_COMPILED = [(re.compile(p, re.IGNORECASE), c) for p, c in HARMONIZE_RULES]


FREQUENCIES = [
    ("weekly", "Hebdomadaire"),
    ("biweekly", "Bi-mensuelle (toutes les 2 semaines)"),
    ("monthly", "Mensuelle"),
    ("quarterly", "Trimestrielle"),
    ("yearly", "Annuelle"),
]
