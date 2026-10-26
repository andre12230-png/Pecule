"""Lisez-moi.txt est ecrit en francais accentue (controle du 26/10/2026).

Le fichier livre dans l'archive et l'installeur etait ecrit entierement
sans accents (« NOUVEAUTES », « Parametres », « Executer quand meme »),
avec « << >> » pour guillemets et « ... » pour points de suspension.
Seule la premiere ligne garde sa forme : le controle de livraison y lit
le numero de version (« PECULE - version 1.41.28 »).
"""
import re
from pathlib import Path

LISEZ_MOI = Path(__file__).resolve().parent.parent / "Lisez-moi.txt"

# Formes sans accent relevees par le controle : aucune n'est du francais.
SANS_ACCENT = re.compile(
    r"\b(?:NOUVEAUTES|Parametres|releves?|donnees|Executer|meme|memes|"
    r"Demarrer|operations?|categories?|derniere|precedente|cote|deja|"
    r"etre|cree|creee|verifiee?|a jour|mise a jour|a la main|"
    r"Previsionnel|Presentation|probleme|numero|depart)\b")


def _texte():
    return LISEZ_MOI.read_text(encoding="utf-8")


def test_la_premiere_ligne_garde_le_numero_lu_par_le_controle():
    assert re.match(r"PECULE - version \S+", _texte())


def test_aucune_forme_sans_accent():
    fautes = []
    for numero, ligne in enumerate(_texte().splitlines()[1:], start=2):
        if "http" in ligne:
            continue
        for trouve in SANS_ACCENT.finditer(ligne):
            fautes.append(f"ligne {numero} : « {trouve.group(0)} »")
    assert not fautes, "Accents manquants :\n" + "\n".join(fautes)


def test_guillemets_et_points_de_suspension_francais():
    texte = _texte()
    assert "<<" not in texte and ">>" not in texte
    assert "..." not in texte
