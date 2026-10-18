"""Un nom par chose (charte des applis, section 4).

Choix de l'auteur du 01/10/2026 : l'argent qui bouge sur le compte se dit
« Entrées / Sorties » (bandeau du mois, Prévisionnel, Générer les
échéances) ; « Revenus / Dépenses » restent aux analyses (graphiques, taux
d'épargne). Avant, le même argent s'appelait selon l'écran « Recettes »,
« rentrée », « À encaisser » ou « Encaissé ».
"""
import ast
import pathlib
import re

from datetime import date, timedelta

from comptesbudget.database import Database

RACINE = pathlib.Path(__file__).resolve().parent.parent / "comptesbudget" / "ui"

# Les mots retirés, tels qu'ils s'écrivaient dans les textes affichés.
# « à débiter » n'y est pas : l'Encours carte le garde (« Total des achats à
# débiter »), c'est le mot de la banque pour le lot de la carte.
ANCIENS = re.compile(r"Recettes|[Rr]entrées?\b|[ÀàAa] encaisser|[Ee]ncaissé\b"
                     r"|\bDébité\b")


def _textes_affiches(chemin):
    """Les chaînes du fichier, sauf les docstrings (des explications pour
    qui lit le code, jamais montrées à l'écran)."""
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    docstrings = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.Module, ast.ClassDef, ast.FunctionDef,
                              ast.AsyncFunctionDef)):
            corps = noeud.body
            if (corps and isinstance(corps[0], ast.Expr)
                    and isinstance(corps[0].value, ast.Constant)):
                docstrings.add(id(corps[0].value))
    for noeud in ast.walk(arbre):
        if (isinstance(noeud, ast.Constant) and isinstance(noeud.value, str)
                and id(noeud) not in docstrings):
            yield noeud.lineno, noeud.value


def test_aucun_ancien_mot_dans_les_textes_affiches():
    fautes = []
    for chemin in sorted(RACINE.rglob("*.py")):
        for ligne, texte in _textes_affiches(chemin):
            for m in ANCIENS.finditer(texte):
                fautes.append(f"{chemin.name}:{ligne} « {m.group(0)} »")
    assert not fautes, "\n".join(fautes)


def _base(tmp_path):
    d = Database(str(tmp_path / "vocabulaire.db"))
    d.set_setting("initial_balance", "1000")
    d.set_setting("initial_date", "2020-01-01")
    jour = date.today().isoformat()
    d.insert_tx({"id": "edf", "date": jour, "date_valeur": jour,
                 "libelle": "EDF", "libelle_op": "EDF", "reference": "",
                 "type": "Prelevement", "categorie": "Logement - maison",
                 "sous_cat": "", "info": "", "montant": -80.0, "pointee": 0})
    return d


def test_bandeau_du_mois_parle_d_entrees_et_de_sorties(qapp, tmp_path):
    from comptesbudget.ui.views.bilan import BilanView
    vue = BilanView(_base(tmp_path))
    vue.refresh()
    assert vue.mois_sorties_lbl.text() == "Sorties à venir (hors carte)"
    assert vue.mois_entrees_lbl.text() == "Entrées à venir"
    assert "1 sortie" in vue.mois_detail_complet
    assert "aucune entrée" in vue.mois_detail_complet

    # Un mois clos se raconte au passé, avec les mêmes mots.
    vue.period = (date.today().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    vue.refresh()
    assert vue.mois_sorties_lbl.text() == "Sorties (hors carte)"
    assert vue.mois_entrees_lbl.text() == "Entrées"


def test_previsionnel_parle_d_entrees_et_de_sorties(qapp, tmp_path):
    from comptesbudget.ui.views.previsionnel import PrevisionnelView
    d = _base(tmp_path)
    d.insert_recurring({
        "id": "r", "libelle": "Salaire", "montant": 1500.0,
        "categorie": "Revenus", "sous_cat": "", "type": "Virement",
        "frequency": "monthly", "day_of_month": 1,
        "start_date": "2026-01-01", "end_date": None, "actif": 1})
    vue = PrevisionnelView(d)
    vue.refresh()
    texte = vue.summary.text()
    assert "Entrées :" in texte and "Sorties :" in texte


def test_toute_la_periode_porte_le_meme_nom_partout():
    """« Toute la période », comme le Photovoltaïque et Recharges VE (choix
    de l'auteur du 08/10/2026) : plus de « Toutes périodes » à l'écran."""
    fautes = [f"{chemin.name}:{ligne}"
              for chemin in sorted(RACINE.rglob("*.py"))
              for ligne, texte in _textes_affiches(chemin)
              if re.search(r"[Tt]outes périodes", texte)]
    assert not fautes, ", ".join(fautes)


def test_toute_la_periode_sans_faute_d_accord():
    """Le remplacement de « toutes périodes » par « Toute la période » (08/10)
    avait laissé « toute la période confondues » dans la Notice : un pluriel
    accroché à un singulier. Trouvé à l'audit du 18/10/2026."""
    fautes = [f"{chemin.name}:{ligne}"
              for chemin in sorted(RACINE.rglob("*.py"))
              for ligne, texte in _textes_affiches(chemin)
              if re.search(r"[Tt]oute la période,?\s+(confondu|compris)es",
                           texte)]
    assert not fautes, ", ".join(fautes)
