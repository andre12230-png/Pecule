"""Vérifie que le code reste compatible avec la version minimale de Python.

Le README annonce Python >= 3.9. Or la notation « dict | None » dans une
annotation (PEP 604) n'existe qu'à partir de Python 3.10 : sur 3.9, elle
lève une TypeError dès l'import du module, et l'application ne démarre pas.

Ce test relit le code source plutôt que de l'exécuter : il tourne donc sur
n'importe quelle version de Python, y compris celles où le problème ne se
voit pas. Un fichier qui commence par « from __future__ import annotations »
est dispensé : cette ligne suffit à rendre la notation acceptable en 3.9.
"""
import ast
import os

RACINE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "comptesbudget")


def _fichiers_python():
    """Tous les .py du paquet, y compris ceux des sous-dossiers."""
    for dossier, _, fichiers in os.walk(RACINE):
        if "__pycache__" in dossier:
            continue
        for nom in sorted(fichiers):
            if nom.endswith(".py"):
                yield os.path.join(dossier, nom)


def _annotations(arbre):
    """Les morceaux d'AST qui servent d'annotation : arguments, valeurs de
    retour et variables annotées."""
    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = noeud.args
            tous = args.args + args.kwonlyargs + args.posonlyargs
            for a in tous + [args.vararg, args.kwarg]:
                if a is not None and a.annotation is not None:
                    yield noeud.lineno, a.annotation
            if noeud.returns is not None:
                yield noeud.lineno, noeud.returns
        elif isinstance(noeud, ast.AnnAssign):
            yield noeud.lineno, noeud.annotation


def _futur_active(arbre):
    """Le fichier commence-t-il par « from __future__ import annotations » ?"""
    for noeud in arbre.body:
        if isinstance(noeud, ast.ImportFrom) and noeud.module == "__future__":
            if any(alias.name == "annotations" for alias in noeud.names):
                return True
    return False


def test_pas_de_union_pep604_dans_les_annotations():
    """Aucune annotation ne doit utiliser « X | Y » : ce serait exiger 3.10."""
    fautifs = []
    for chemin in _fichiers_python():
        with open(chemin, encoding="utf-8") as f:
            arbre = ast.parse(f.read(), filename=chemin)
        if _futur_active(arbre):
            continue
        for ligne, annotation in _annotations(arbre):
            for morceau in ast.walk(annotation):
                if isinstance(morceau, ast.BinOp) and isinstance(morceau.op, ast.BitOr):
                    court = os.path.relpath(chemin, os.path.dirname(RACINE))
                    fautifs.append(court + ":" + str(ligne))
    assert not fautifs, (
        "Annotations « X | Y » (Python 3.10+) alors que le README annonce "
        "Python >= 3.9 : " + ", ".join(fautifs) +
        ". Utiliser Optional[...] / Union[...], ou ajouter "
        "« from __future__ import annotations » en tête du fichier."
    )
