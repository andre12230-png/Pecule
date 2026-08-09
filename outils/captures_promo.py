"""Refabrique les captures d'écran de la page de présentation (docs/media/).

Pourquoi ce script : les images de la vitrine doivent être refaites à chaque
fois que l'interface change, et il ne faut JAMAIS y montrer de vraies
opérations. Tout ce qui apparaît sur les captures est inventé ici même, dans
une base temporaire effacée à la fin. Votre comptes.db n'est jamais ouverte.

Lancement (depuis n'importe où) :

    python outils/captures_promo.py              → écrase docs/media/
    python outils/captures_promo.py mon_dossier  → écrit ailleurs, pour voir

Les données sont tirées avec une graine fixe : deux exécutions le même jour
donnent les mêmes images. Le mois affiché est toujours le mois en cours.
"""
import os
import random
import shutil
import sys
import tempfile
import time
from calendar import monthrange
from datetime import date

# Permet de lancer le script depuis n'importe quel dossier : on ajoute la
# racine du dépôt au chemin d'import avant de charger l'application.
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from PySide6.QtGui import QColor, QPalette                # noqa: E402
from PySide6.QtWidgets import QApplication                # noqa: E402

from comptesbudget.database import Database               # noqa: E402
from comptesbudget.ui.main_window import MainWindow       # noqa: E402

AUJOURDHUI = date.today()
LARGEUR, HAUTEUR = 1668, 913          # taille demandée ; la fenêtre peut être
                                      # un peu plus grande (taille minimale)
GRAINE = 20260809                     # captures reproductibles

# ── Le jeu de données inventé ────────────────────────────────────────────────
# (libellé, catégorie, sous-catégorie, montant, jour du mois, type)
MENSUELLES = [
    ("VIR SEPA SALAIRE",     "Revenus",              "Salaire",     2380.00,  1, "Virement"),
    ("Loyer Appartement",    "Logement - maison",    "Loyer",       -720.00,  3, "Prelevement"),
    ("EDF Electricite",      "Logement - maison",    "Energie",      -84.50,  5, "Prelevement"),
    ("Orange Fibre",         "Logement - maison",    "Internet",     -39.99,  8, "Prelevement"),
    ("Assurance Habitation", "Banque et assurances", "Habitation",   -26.20, 10, "Prelevement"),
    ("Assurance Auto",       "Banque et assurances", "Auto",         -20.00, 10, "Prelevement"),
    ("Mutuelle Sante",       "Santé",                "Mutuelle",     -17.60, 12, "Prelevement"),
    ("Netflix",              "Abonnements",          "",             -13.49, 15, "Carte bancaire"),
]

# Dépenses courantes, tirées au sort dans le mois (montant de référence)
COURANTES = [
    ("Carrefour Market",    "Alimentation", "Courses",     -95.00, "Carte bancaire"),
    ("Intermarche",         "Alimentation", "Courses",     -62.00, "Carte bancaire"),
    ("Lidl",                "Alimentation", "Courses",     -48.00, "Carte bancaire"),
    ("Boulangerie Dupont",  "Alimentation", "Boulangerie",  -8.50, "Carte bancaire"),
    ("Station Total",       "Transports",   "Carburant",   -65.00, "Carte bancaire"),
    ("SNCF",                "Transports",   "Train",       -34.00, "Carte bancaire"),
    ("Restaurant Chez Lea", "Loisirs",      "Restaurant",  -52.00, "Carte bancaire"),
    ("Cinema Le Palace",    "Loisirs",      "Sorties",     -22.00, "Carte bancaire"),
    ("Pharmacie du Centre", "Santé",        "Pharmacie",   -18.40, "Carte bancaire"),
    ("Fnac",                "Shopping",     "",            -45.90, "Carte bancaire"),
]

BUDGETS = {
    "Alimentation": 320.0, "Transports": 150.0, "Logement - maison": 900.0,
    "Loisirs": 110.0, "Shopping": 100.0, "Santé": 60.0,
    "Banque et assurances": 50.0, "Impôts et taxes": 45.0,
}

REGLES = (("carrefour", "Alimentation"), ("station total", "Transports"),
          ("netflix", "Abonnements"))


def _tx(id_, d, libelle, cat, sous, montant, type_, pointee=1, date_val=None):
    """Une ligne d'opération au format attendu par la base."""
    return {"id": id_, "date": d.isoformat(),
            "date_valeur": (date_val or d).isoformat(),
            "libelle": libelle, "libelle_op": libelle.upper(), "reference": "",
            "type": type_, "categorie": cat, "sous_cat": sous, "info": "",
            "montant": round(montant, 2), "pointee": pointee}


def construire_base(chemin):
    """Crée la base de démonstration : du 1er janvier à aujourd'hui."""
    db = Database(chemin)
    db.set_setting("initial_balance", "1850")
    db.set_setting("initial_date", f"{AUJOURDHUI.year}-01-01")

    alea = random.Random(GRAINE)
    n = 0
    with db.batch():
        for mois in range(1, AUJOURDHUI.month + 1):
            dernier = monthrange(AUJOURDHUI.year, mois)[1]

            for libelle, cat, sous, base, jour, type_ in MENSUELLES:
                d = date(AUJOURDHUI.year, mois, min(jour, dernier))
                if d > AUJOURDHUI:
                    continue
                # Seule la facture d'électricité varie d'un mois à l'autre :
                # c'est ce qui rend visible la tolérance du rapprochement.
                montant = (base * (1 + alea.uniform(-0.12, 0.12))
                           if "Electricite" in libelle else base)
                n += 1
                db.insert_tx(_tx(f"m{n}", d, libelle, cat, sous, montant, type_))

            for libelle, cat, sous, base, type_ in COURANTES:
                for _ in range(alea.choice((1, 1, 2))):
                    d = date(AUJOURDHUI.year, mois, alea.randint(2, dernier))
                    if d > AUJOURDHUI:
                        continue
                    # Achat par carte : la banque le prélève le 4 du mois
                    # suivant. Tant que ce jour n'est pas venu, l'opération
                    # reste non pointée — c'est l'encours de la carte.
                    m2 = 1 if mois == 12 else mois + 1
                    a2 = AUJOURDHUI.year + 1 if mois == 12 else AUJOURDHUI.year
                    dv = date(a2, m2, 4)
                    pointee = 0 if dv > AUJOURDHUI else 1
                    n += 1
                    db.insert_tx(_tx(f"c{n}", d, libelle, cat, sous,
                                     base * (1 + alea.uniform(-0.30, 0.30)),
                                     type_, pointee=pointee, date_val=dv))

        # Une taxe foncière, pour que « Impôts et taxes » ne reste pas vide
        taxe = date(AUJOURDHUI.year, max(1, AUJOURDHUI.month - 1), 10)
        db.insert_tx(_tx("tf1", taxe, "DGFIP Taxe Fonciere", "Impôts et taxes",
                         "", -120.00, "Prelevement"))

        for cat, montant in BUDGETS.items():
            db.set_budget(cat, montant)

        # Les récurrences alimentent l'onglet Prévisionnel
        for i, (libelle, cat, sous, montant, jour, type_) in enumerate(MENSUELLES):
            db.insert_recurring({
                "id": f"r{i}", "libelle": libelle, "montant": montant,
                "categorie": cat, "sous_cat": sous, "type": type_,
                "frequency": "monthly", "day_of_month": jour,
                "start_date": f"{AUJOURDHUI.year}-01-{jour:02d}",
                "end_date": None, "actif": 1})

        for i, (motif, cat) in enumerate(REGLES):
            db.insert_rule({"id": f"g{i}", "pattern": motif, "amount": None,
                            "categorie": cat, "sous_cat": "", "no_overwrite": 0,
                            "created_at": f"{AUJOURDHUI.year}-01-01"})
    return db


def _laisser_dessiner(app, secondes):
    """Fait tourner la boucle d'événements de Qt.

    Sans cette pause, la photo attrape les graphiques (camembert,
    histogramme) alors qu'ils ne sont pas encore dessinés.
    """
    fin = time.time() + secondes
    while time.time() < fin:
        app.processEvents()
        time.sleep(0.02)


def photographier(db, dossier):
    """Ouvre la fenêtre et enregistre un PNG par onglet de la vitrine."""
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    # Même palette que l'application (cf. comptesbudget/app.py) : sans elle,
    # les captures n'auraient pas les couleurs que voit l'utilisateur.
    pal = app.palette()
    pal.setColor(QPalette.Window, QColor("#ECE9D8"))
    pal.setColor(QPalette.Base, QColor("#FFFFFF"))
    pal.setColor(QPalette.AlternateBase, QColor("#F5F5F0"))
    pal.setColor(QPalette.Highlight, QColor("#316AC5"))
    pal.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(pal)

    w = MainWindow(db)
    w.resize(LARGEUR, HAUTEUR)
    w.statusBar().showMessage("Base : demo.db   —   données de démonstration")
    w.show()
    _laisser_dessiner(app, 1.5)

    vues = [("promo_1_bilan", w.bilan_view), ("promo_2_operations", w.ops_view),
            ("promo_3_budget", w.budget_view), ("promo_4_previsionnel", w.prev_view)]
    os.makedirs(dossier, exist_ok=True)
    for nom, vue in vues:
        w.tabs.setCurrentWidget(vue)
        for methode in ("refresh", "reload_from_db"):
            if hasattr(vue, methode):
                getattr(vue, methode)()
                break
        _laisser_dessiner(app, 1.5)
        chemin = os.path.join(dossier, nom + ".png")
        w.grab().save(chemin)
        print(f"  {nom}.png")
    w.close()


def main():
    sortie = sys.argv[1] if len(sys.argv) > 1 else os.path.join(RACINE, "docs", "media")
    temporaire = tempfile.mkdtemp(prefix="captures-promo-")
    try:
        print(f"Base de démonstration : {temporaire}")
        db = construire_base(os.path.join(temporaire, "demo.db"))
        print(f"Captures dans {sortie} :")
        photographier(db, sortie)
    finally:
        # La base inventée n'a aucune raison de survivre à la session.
        shutil.rmtree(temporaire, ignore_errors=True)
    print("Terminé.")


if __name__ == "__main__":
    main()
