"""Export des opérations vers un fichier CSV que l'on ouvre dans Excel.

Pas de Qt ici : la vue Opérations choisit les lignes (celles qu'elle affiche)
et le fichier ; ce module ne fait qu'écrire.

Réglé pour un Excel français, qui ouvre le fichier d'un double-clic :
- séparateur « ; » (la virgule sert aux décimales) ;
- encodage UTF-8 précédé de sa marque (BOM), sans laquelle Excel lit mal
  les accents ;
- dates JJ/MM/AAAA et montants « 1234,56 » sans espace ni « € », pour
  qu'Excel y voie des dates et des nombres qu'on peut trier et additionner.
"""
import csv

from .utils import fmt_date_fr

ENTETES = ["Date opération", "Date valeur", "Libellé", "Catégorie",
           "Sous-catégorie", "Type", "Référence", "Note",
           "Débit", "Crédit", "Pointée"]

# Un texte qui commence par l'un de ces signes serait pris par Excel pour
# une formule, et calculé à l'ouverture. Les libellés viennent des relevés
# de la banque : on ne laisse pas un tel texte devenir une formule.
_DEBUT_DE_FORMULE = ("=", "+", "-", "@", "\t", "\r")


def _texte(valeur) -> str:
    """Texte d'une cellule, neutralisé s'il ressemble à une formule."""
    s = str(valeur or "")
    if s.startswith(_DEBUT_DE_FORMULE):
        return "'" + s
    return s


def _montant(valeur: float) -> str:
    """-45.3 → « -45,30 » : deux décimales, virgule, rien d'autre."""
    return f"{valeur:.2f}".replace(".", ",")


def ecrire_csv_operations(chemin: str, operations: list[dict]) -> int:
    """Écrit les opérations dans l'ordre reçu. Renvoie leur nombre.

    Comme à l'écran : les dépenses dans « Débit » (en négatif, comme sur un
    relevé), les rentrées dans « Crédit ». La somme des deux colonnes donne
    donc le solde des lignes exportées."""
    with open(chemin, "w", encoding="utf-8-sig", newline="") as f:
        ecrivain = csv.writer(f, delimiter=";", lineterminator="\r\n")
        ecrivain.writerow(ENTETES)
        for t in operations:
            montant = t.get("montant") or 0
            ecrivain.writerow([
                fmt_date_fr(t.get("date", "")),
                fmt_date_fr(t.get("date_valeur") or t.get("date", "")),
                _texte(t.get("libelle")),
                _texte(t.get("categorie")),
                _texte(t.get("sous_cat")),
                _texte(t.get("type")),
                _texte(t.get("reference")),
                _texte(t.get("info")),
                _montant(montant) if montant < 0 else "",
                _montant(montant) if montant > 0 else "",
                "oui" if t.get("pointee") else "non",
            ])
    return len(operations)
