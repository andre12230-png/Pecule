"""Le thème clair ne doit pas dépendre du réglage d'affichage de Windows.

Sur un poste réglé en mode sombre, Qt fournit une palette dont les TEXTES sont
blancs. Pécule n'imposait que les FONDS (crème, blanc) en partant de cette
palette système : le texte blanc se retrouvait sur du crème, illisible.
Constaté le 16/09/2026 sur le poste d'un autre utilisateur — la boîte
« Bienvenue dans Pécule » était vide à l'écran.

Voir la règle : toutes les applis en thème clair, et jamais moins de 4,5 pour 1
de contraste."""
from PySide6.QtGui import QColor, QPalette

from comptesbudget.app import appliquer_theme_clair, palette_claire


def _luminance(c: QColor) -> float:
    """Luminance relative d'une couleur, au sens des règles d'accessibilité."""
    def canal(v: int) -> float:
        x = v / 255
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    return (0.2126 * canal(c.red()) + 0.7152 * canal(c.green())
            + 0.0722 * canal(c.blue()))


def contraste(a: QColor, b: QColor) -> float:
    """Rapport de contraste entre deux couleurs (de 1 à 21)."""
    la, lb = _luminance(a), _luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _palette_de_poste_sombre() -> QPalette:
    """Ce que Qt renvoie sur un poste Windows réglé en « mode sombre »."""
    p = QPalette()
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText,
                 QPalette.ToolTipText, QPalette.PlaceholderText,
                 QPalette.BrightText):
        p.setColor(role, QColor("#FFFFFF"))
    for role in (QPalette.Window, QPalette.Base, QPalette.Button,
                 QPalette.AlternateBase, QPalette.ToolTipBase):
        p.setColor(role, QColor("#1F1F1F"))
    return p


# Les couples fond / texte que l'œil rencontre réellement dans l'application.
COUPLES = [
    ("fenêtre",        QPalette.Window,        QPalette.WindowText),
    ("champs, listes", QPalette.Base,          QPalette.Text),
    ("boutons",        QPalette.Button,        QPalette.ButtonText),
    ("info-bulles",    QPalette.ToolTipBase,   QPalette.ToolTipText),
    ("ligne sur deux", QPalette.AlternateBase, QPalette.Text),
    ("sélection",      QPalette.Highlight,     QPalette.HighlightedText),
]


def test_palette_claire_lisible_partout():
    """Chaque texte se détache de son fond d'au moins 4,5 pour 1."""
    pal = palette_claire()
    for nom, fond, texte in COUPLES:
        ratio = contraste(pal.color(fond), pal.color(texte))
        assert ratio >= 4.5, f"{nom} : contraste de {ratio:.1f} pour 1"


def test_palette_claire_est_bien_claire():
    """Fond clair, texte sombre — et pas l'inverse, qu'un simple calcul de
    contraste laisserait passer."""
    pal = palette_claire()
    for nom, fond, texte in COUPLES:
        if fond == QPalette.Highlight:
            continue        # la sélection est volontairement sombre sur clair
        assert _luminance(pal.color(fond)) > _luminance(pal.color(texte)), nom


def test_le_theme_clair_ignore_le_mode_sombre_de_windows(qapp):
    """Le cas du 16/09/2026 : même partie d'une palette système sombre,
    l'application reste lisible."""
    avant = qapp.palette()
    try:
        qapp.setPalette(_palette_de_poste_sombre())   # poste en mode sombre
        appliquer_theme_clair(qapp)
        pal = qapp.palette()
        for nom, fond, texte in COUPLES:
            ratio = contraste(pal.color(fond), pal.color(texte))
            assert ratio >= 4.5, f"{nom} : contraste de {ratio:.1f} pour 1"
    finally:
        qapp.setPalette(avant)


def test_texte_grise_reste_visible():
    """Le texte d'invite (« Rechercher… ») et les libellés désactivés doivent
    rester lisibles : pâles, mais pas effacés."""
    pal = palette_claire()
    fond = pal.color(QPalette.Base)
    invite = pal.color(QPalette.PlaceholderText)
    assert contraste(fond, invite) >= 3.0
    desactive = pal.color(QPalette.Disabled, QPalette.WindowText)
    assert contraste(pal.color(QPalette.Window), desactive) >= 3.0


def test_vert_de_confirmation_commun_aux_trois_applis(qapp):
    """29/09/2026 : les confirmations de « Votre avis » et « Mise à jour »
    étaient écrites en #2E7D32, les deux autres applis en #18733A, le vert de
    texte de la palette commune (règle : les trois applis ont exactement les
    mêmes couleurs)."""
    from comptesbudget.ui.avis import AvisDialog
    from comptesbudget.ui.mise_a_jour import MiseAJourDialog

    for fenetre in (AvisDialog(), MiseAJourDialog()):
        style = fenetre.confirmation.styleSheet().upper()
        assert "#18733A" in style, type(fenetre).__name__
