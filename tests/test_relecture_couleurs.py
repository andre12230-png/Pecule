"""Couleurs de l'interface : palette de la charte et contrastes (relecture
de design du 30/09/2026).

La charte des applis dit : « Une couleur absente de ce tableau est une
couleur à justifier », et « Tout texte : au moins 4,5 pour 1 ». La relecture
a trouvé des textes à 2,68 (orange des dates différées), 3,09 (taux
d'épargne), 3,35 (échéances prévues), et une dizaine de fonds de bandeaux
inventés à côté de la palette. Ces tests lisent le code de l'interface.
"""
import io
import re
import tokenize
from pathlib import Path

import comptesbudget

UI = Path(comptesbudget.__file__).parent / "ui"

# Palette de la charte (skill charte-applis, section 1).
PALETTE = {
    "#ECE9D8", "#FAF8F1", "#BEC7D4", "#E8EEF7", "#C9D6E8", "#1F3A6B", "#B0BFD3",
    "#FFFFFF", "#F5F5F0", "#000000", "#555555", "#666666", "#6B6B6B", "#5A5A5A",
    "#A9A9A9", "#316AC5", "#FCFCFC", "#808080", "#222222", "#EAF2FB", "#D8E7F7",
    "#6F7885", "#18733A", "#C0392B", "#FEF5E7", "#E67E22", "#7E5109", "#FFFBE6",
    "#E8D77B", "#FDEDEB", "#E74C3C", "#7B241C", "#0B5AA8", "#6A3FA0", "#FFFFDC",
    # Bandeau favorable (vert) de Pécule, ajouté à la charte le 30/09/2026.
    "#EAF6EC", "#229954", "#1A5E32",
}

# Exceptions justifiées, propres à Pécule — jamais du texte.
EXCEPTIONS = {
    "#D6F0DC": "fond de la case P d'une opération pointée (le ✔ vert y tient 4,6)",
    "#27AE60": "barre du Budget sous 80 % (le chiffre s'y écrit en noir : 7,3)",
    "#B9551A": "barres « Dépenses » du Bilan (orange foncé, 4,5 sur l'ivoire ; "
               "#E67E22 n'y faisait que 2,68)",
}

# Fond le plus sombre sur lequel un texte coloré se pose dans un tableau.
FOND = "#F5F5F0"


def _luminance(hexa: str) -> float:
    def canal(v: int) -> float:
        x = v / 255
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hexa[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b)


def _contraste(a: str, b: str) -> float:
    la, lb = _luminance(a), _luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _norme(hexa: str) -> str:
    hexa = hexa.upper()
    if len(hexa) == 4:                      # #555 → #555555
        hexa = "#" + "".join(c * 2 for c in hexa[1:])
    return hexa


HEXA = re.compile(r"(?<![&\w])#(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})(?![0-9A-Fa-f])")


def _textes_du_code(fichier: Path):
    """Les chaînes de caractères du fichier (pas les commentaires)."""
    source = fichier.read_text(encoding="utf-8")
    types = {tokenize.STRING}
    if hasattr(tokenize, "FSTRING_MIDDLE"):
        types.add(tokenize.FSTRING_MIDDLE)
    for jeton in tokenize.generate_tokens(io.StringIO(source).readline):
        if jeton.type in types:
            yield jeton.start[0], jeton.string


def test_toute_couleur_vient_de_la_palette():
    hors_palette = []
    for fichier in sorted(UI.rglob("*.py")):
        for ligne, texte in _textes_du_code(fichier):
            for trouve in HEXA.findall(texte):
                c = _norme(trouve)
                if c not in PALETTE and c not in EXCEPTIONS:
                    hors_palette.append(f"{fichier.relative_to(UI)}:{ligne} {c}")
    assert not hors_palette, "Couleurs hors de la charte :\n" + "\n".join(hors_palette)


TEXTE_COLORE = [
    re.compile(r'setForeground\(QBrush\(QColor\("(#[0-9A-Fa-f]{3,6})"\)\)\)'),
    re.compile(r'(?<![-\w])color\s*:\s*(#[0-9A-Fa-f]{3,6})\b'),
    re.compile(r'<font color="(#[0-9A-Fa-f]{3,6})"'),
    re.compile(r'etat, couleur = "[^"]*", "(#[0-9A-Fa-f]{6})"'),
]
BLANC_SUR_APLAT = {"#FFFFFF"}      # texte blanc posé sur une barre foncée


def test_tout_texte_colore_est_lisible():
    """Chaque couleur de TEXTE tient 4,5 pour 1 sur une ligne de tableau."""
    trop_pales = []
    for fichier in sorted(UI.rglob("*.py")):
        source = fichier.read_text(encoding="utf-8")
        for motif in TEXTE_COLORE:
            for m in motif.finditer(source):
                c = _norme(m.group(1))
                if c in BLANC_SUR_APLAT:
                    continue
                # Un filet de séparation (QFrame.HLine) prend sa couleur par
                # « color » : c'est un trait, pas un texte (seuil 1,4).
                if "HLine" in source[max(0, m.start() - 200):m.start()]:
                    continue
                ratio = _contraste(c, FOND)
                if ratio < 4.5:
                    ligne = source[:m.start()].count("\n") + 1
                    trop_pales.append(f"{fichier.relative_to(UI)}:{ligne} {c} : {ratio:.2f}")
    assert not trop_pales, "Textes trop pâles :\n" + "\n".join(trop_pales)


def test_les_exceptions_sont_utilisees():
    """Une exception qui ne sert plus sort de la liste."""
    tout = "".join(t for f in UI.rglob("*.py") for _l, t in _textes_du_code(f)).upper()
    for c in EXCEPTIONS:
        assert c in tout, f"{c} n'est plus employée : la retirer des exceptions"
