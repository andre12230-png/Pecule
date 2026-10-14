"""Les couleurs de Pécule, en clair et en sombre, rangées par rôle.

Toute couleur de l'interface vient d'ici : un écran ne doit plus écrire
« #ECE9D8 » mais T["fond_page"]. C'est ce qui permet d'avoir deux thèmes
sans oublier un coin d'écran (décision de l'auteur du 12/10/2026 : un mode
sombre dans les trois applis, demandé par un utilisateur de Pécule).

Les deux palettes sont celles de la charte commune aux trois applis
(Pécule, Photovoltaïque, Recharges VE). Chaque clé de SOMBRE est la jumelle
de la même clé de CLAIR ; tests/test_theme_sombre.py vérifie qu'elles ont
les mêmes clés et que chaque texte se lit sur son fond (4,5 pour 1).

Le thème se choisit dans ⚙️ Paramètres et s'applique au PROCHAIN
démarrage : les couleurs sont lues à la construction des fenêtres, une
bascule à chaud obligerait à tout redessiner (c'est là que se cachent les
oublis). Le choix est gardé dans les préférences de Windows (QSettings),
jamais dans comptes.db : le thème doit être connu avant d'ouvrir la base,
et ce n'est pas une donnée des comptes.
"""

# ─────────────────────────── Thème clair (référence) ───────────────────────
CLAIR = {
    # Fonds
    "fond_page": "#ECE9D8",        # crème : fenêtres, pages, bandeau de gauche
    "carte": "#FAF8F1",            # ivoire : cartes, tuiles, notice, graphiques
    "lisere": "#BEC7D4",           # bord des cartes et des tuiles
    "saisie": "#FFFFFF",           # tableaux, cases de saisie, listes
    "ligne_paire": "#F5F5F0",      # une ligne sur deux dans les tableaux
    # En-tête bleuté des cartes
    "entete_haut": "#E8EEF7",
    "entete_bas": "#C9D6E8",
    "entete_texte": "#1F3A6B",
    "entete_filet": "#B0BFD3",
    # Textes
    "texte": "#000000",            # texte principal
    "texte_libelle": "#222222",    # libellés des listes, corps de la notice
    "texte_secondaire": "#555555",
    "texte_discret": "#666666",    # aussi : texte d'invite, compteurs
    "texte_grise": "#5A5A5A",      # titres de section, opération pointée
    "texte_desactive": "#666666",
    "filet": "#A9A9A9",            # filets sous les titres, bord des barres
    # Sélection
    "selection": "#316AC5",
    "texte_selection": "#FFFFFF",
    # Boutons du bandeau de gauche
    "bouton_fond": "#FCFCFC",
    "bouton_contour": "#808080",
    "bouton_texte": "#222222",
    "bouton_survol": "#EAF2FB",
    "bouton_survol_contour": "#316AC5",
    "bouton_actif": "#D8E7F7",
    "bouton_qt": "#ECE9D8",        # boutons ordinaires de Qt (palette Button)
    # Contrôles
    "contour": "#6F7885",          # cases à cocher, boutons radio (3 pour 1)
    "grille": "#E2E8F0",           # grille des graphiques
    # Couleurs qui ont un sens
    "bleu_nuit": "#1F3A6B",        # marque, titres forts, solde
    "credit": "#18733A",           # montant positif
    "debit": "#BC3729",            # montant négatif
    "avertissement": "#7E5109",    # texte d'avertissement discret
    "lien": "#0B5AA8",
    "lien_vu": "#6A3FA0",
    # Bandeaux
    "alerte_fond": "#FEF5E7",      # orange : à faire bientôt
    "alerte_cadre": "#E67E22",
    "alerte_texte": "#7E5109",
    "info_fond": "#FFFBE6",        # jaune : remarque sans urgence
    "info_cadre": "#E8D77B",
    "erreur_fond": "#FDEDEB",      # rouge : erreur, découvert, dépassement
    "erreur_cadre": "#E74C3C",
    "erreur_texte": "#7B241C",
    "favorable_fond": "#EAF6EC",   # vert : le compte tient
    "favorable_cadre": "#229954",
    "favorable_texte": "#1A5E32",
    # Infobulles
    "bulle_fond": "#FFFFDC",
    "bulle_texte": "#000000",
    "bulle_cadre": "#808080",
    # Propres à Pécule
    "pointe_fond": "#D6F0DC",      # case P d'une opération pointée
    "barre_revenus": "#229954",    # barres « Revenus » du Bilan (pas du texte)
    "barre_depenses": "#BC3729",   # barres « Dépenses » du Bilan
    "budget_ok": "#27AE60",        # barre d'un budget sous 80 %
    "budget_proche": "#E67E22",    # barre d'un budget entre 80 et 100 %
    "budget_depasse": "#BC3729",   # barre d'un budget dépassé
    "budget_piste": "#F5F5F0",     # fond d'une barre de budget
    "budget_encre": "#000000",     # chiffre d'une barre de budget
    "budget_encre_depasse": "#FFFFFF",  # chiffre d'une barre pleine et rouge
}

# ─────────────────────────── Thème sombre ──────────────────────────────────
# Un sombre chaud (brun très foncé), transposition du crème et de l'ivoire,
# validé par l'auteur sur maquette le 12/10/2026. En sombre, l'« encre »
# d'une couleur vive s'obtient en l'éclaircissant (en clair, on l'assombrit).
SOMBRE = {
    "fond_page": "#1C1B18",
    "carte": "#262521",
    "lisere": "#55565B",
    "saisie": "#302F2B",           # un cran plus clair que la carte
    "ligne_paire": "#2A2925",
    "entete_haut": "#2E3B52",
    "entete_bas": "#27344A",
    "entete_texte": "#CFDCF3",
    "entete_filet": "#41557A",
    "texte": "#EDEAE2",            # blanc cassé, jamais blanc pur
    "texte_libelle": "#EDEAE2",
    "texte_secondaire": "#C9C6BD",
    "texte_discret": "#ADAAA1",
    "texte_grise": "#ADAAA1",
    "texte_desactive": "#ADAAA1",
    "filet": "#5E5C56",
    "selection": "#316AC5",
    "texte_selection": "#FFFFFF",
    "bouton_fond": "#2B2A26",
    "bouton_contour": "#8A8780",
    "bouton_texte": "#E6E3DA",
    "bouton_survol": "#24334A",
    "bouton_survol_contour": "#6FA0E8",
    "bouton_actif": "#2A3F5F",
    "bouton_qt": "#2B2A26",        # un cran plus clair que la page
    "contour": "#8A919C",
    "grille": "#4A4944",
    "bleu_nuit": "#A9C2EC",
    "credit": "#5CC281",
    "debit": "#F2806F",
    "avertissement": "#F0B866",
    "lien": "#82B6F5",
    "lien_vu": "#BBA2EA",
    "alerte_fond": "#3A2D16",
    "alerte_cadre": "#E67E22",
    "alerte_texte": "#F3C783",
    "info_fond": "#35321C",
    "info_cadre": "#8F7F33",
    "erreur_fond": "#3E201D",
    "erreur_cadre": "#E74C3C",
    "erreur_texte": "#F6B3AA",
    "favorable_fond": "#1B3324",
    "favorable_cadre": "#229954",
    "favorable_texte": "#A2DDB4",
    "bulle_fond": "#3B3826",
    "bulle_texte": "#F2EFE6",
    "bulle_cadre": "#8A8780",
    "pointe_fond": "#1B3324",
    "barre_revenus": "#229954",
    "barre_depenses": "#F2806F",
    # Barres du Budget : le chiffre clair s'écrit sur la barre ET sur sa
    # piste. Des barres foncées (4,5 pour 1 sous le chiffre) sur une piste
    # plus foncée encore, où elles se détachent (3 pour 1 ; la rouge,
    # toujours pleine, n'a pas de piste visible).
    "budget_ok": "#1C7642",
    "budget_proche": "#A0560F",
    "budget_depasse": "#A93226",
    "budget_piste": "#1C1B18",
    "budget_encre": "#EDEAE2",
    "budget_encre_depasse": "#EDEAE2",
}

THEMES = {"clair": CLAIR, "sombre": SOMBRE}

# Les couleurs de la session. C'est un dictionnaire rempli SUR PLACE par
# choisir_theme() : un module qui a fait « from ..theme import T » voit
# donc toujours les bonnes couleurs. Clair tant que rien n'est choisi
# (c'est aussi le thème des tests).
T = dict(CLAIR)
_nom_actif = "clair"


def choisir_theme(nom: str) -> str:
    """Fixe le thème de la session (« clair » ou « sombre ») et rend son nom.
    Un nom inconnu donne le clair, le thème de référence.

    À appeler au démarrage, avant de construire la moindre fenêtre."""
    global _nom_actif
    _nom_actif = nom if nom in THEMES else "clair"
    T.clear()
    T.update(THEMES[_nom_actif])
    return _nom_actif


def theme_actif() -> str:
    """« clair » ou « sombre »."""
    return _nom_actif


def est_sombre() -> bool:
    return _nom_actif == "sombre"


# ─────────────────────────── Le réglage, dans les préférences ──────────────
CLE_THEME = "apparence/theme"


def preferences():
    """Les préférences de Pécule dans Windows (registre de l'utilisateur).
    Import local : ce module reste lisible sans Qt."""
    from PySide6.QtCore import QSettings
    return QSettings("Pecule", "Pecule")


def lire_theme(reglages=None) -> str:
    """Le thème enregistré : « clair » ou « sombre ». Absent, inconnu ou
    abîmé, c'est le clair.

    Une préférence abîmée peut revenir sous forme de liste : le
    Photovoltaïque ne démarrait plus dans ce cas (audit du 13/10/2026)."""
    reglages = reglages if reglages is not None else preferences()
    valeur = reglages.value(CLE_THEME)
    if not isinstance(valeur, str) or valeur not in THEMES:
        return "clair"
    return valeur


def enregistrer_theme(nom: str, reglages=None) -> bool:
    """Enregistre le thème choisi. Rend False si l'écriture a échoué :
    on n'annonce jamais « enregistré » sans l'avoir vérifié (défaut vu
    dans le Photovoltaïque, audit du 13/10/2026)."""
    from PySide6.QtCore import QSettings
    if nom not in THEMES:
        return False
    reglages = reglages if reglages is not None else preferences()
    reglages.setValue(CLE_THEME, nom)
    reglages.sync()
    return (reglages.status() == QSettings.NoError
            and reglages.value(CLE_THEME) == nom)
