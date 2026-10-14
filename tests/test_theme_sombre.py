"""Le mode sombre : deux palettes jumelles, lisibles toutes les deux.

Décision de l'auteur du 12/10/2026 : un mode sombre dans les trois applis,
au choix dans ⚙️ Paramètres, appliqué au prochain démarrage. Les couleurs
sont celles de la charte commune (comptesbudget/theme.py). Ces tests
vérifient chaque texte sur chacun de ses fonds, dans les deux thèmes, et
que le réglage ne touche jamais aux vraies préférences de l'utilisateur
(fichier .ini temporaire)."""
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor, QPalette

from comptesbudget import theme
from comptesbudget.theme import CLAIR, SOMBRE, T


def _luminance(couleur: str) -> float:
    c = QColor(couleur)

    def canal(v: int) -> float:
        x = v / 255
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    return (0.2126 * canal(c.red()) + 0.7152 * canal(c.green())
            + 0.0722 * canal(c.blue()))


def contraste(a: str, b: str) -> float:
    la, lb = _luminance(a), _luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


FONDS_COURANTS = ("fond_page", "carte", "saisie", "ligne_paire")

# (couleur du texte, fonds sur lesquels il est écrit) : 4,5 pour 1.
TEXTES = [
    ("texte", FONDS_COURANTS + ("info_fond",)),
    ("texte_libelle", FONDS_COURANTS),
    ("texte_secondaire", FONDS_COURANTS + ("info_fond",)),
    ("texte_discret", FONDS_COURANTS),
    ("texte_grise", FONDS_COURANTS),
    ("bleu_nuit", FONDS_COURANTS),
    ("credit", FONDS_COURANTS + ("pointe_fond",)),
    ("debit", FONDS_COURANTS),
    ("avertissement", FONDS_COURANTS),
    ("lien", FONDS_COURANTS),
    ("lien_vu", FONDS_COURANTS),
    ("entete_texte", ("entete_haut", "entete_bas")),
    ("bouton_texte", ("bouton_fond", "bouton_survol", "bouton_actif")),
    ("texte", ("bouton_qt",)),
    ("alerte_texte", ("alerte_fond",)),
    ("erreur_texte", ("erreur_fond",)),
    ("favorable_texte", ("favorable_fond",)),
    ("bulle_texte", ("bulle_fond",)),
    ("texte_selection", ("selection",)),
]

# Ce qu'on clique, et ce qui porte une information sans être du texte :
# 3 pour 1. Le liseré d'une carte sur la page : 1,4 pour 1.
REPERES = [
    ("contour", FONDS_COURANTS, 3.0),
    ("bouton_contour", ("fond_page",), 3.0),
    ("barre_revenus", ("carte",), 3.0),
    ("barre_depenses", ("carte",), 3.0),
    # 1,39 et non 1,4 : #BEC7D4 sur le crème fait 1,3996, « juste 1,40 »
    # selon la charte, qui l'a validé ainsi.
    ("lisere", ("fond_page",), 1.39),
]


@pytest.mark.parametrize("palette", [CLAIR, SOMBRE], ids=["clair", "sombre"])
def test_chaque_texte_se_lit_sur_ses_fonds(palette):
    trop_pales = [
        f"{texte} sur {fond} : {contraste(palette[texte], palette[fond]):.2f}"
        for texte, fonds in TEXTES for fond in fonds
        if contraste(palette[texte], palette[fond]) < 4.5]
    assert not trop_pales


@pytest.mark.parametrize("palette", [CLAIR, SOMBRE], ids=["clair", "sombre"])
def test_reperes_et_contours_se_voient(palette):
    trop_pales = [
        f"{cle} sur {fond} : {contraste(palette[cle], palette[fond]):.2f}"
        for cle, fonds, seuil in REPERES for fond in fonds
        if contraste(palette[cle], palette[fond]) < seuil]
    assert not trop_pales


def test_les_deux_palettes_sont_jumelles():
    """Une couleur ajoutée à un thème sans l'autre laisserait un trou."""
    assert set(CLAIR) == set(SOMBRE)


def test_le_sombre_est_bien_sombre():
    for fond in FONDS_COURANTS:
        assert _luminance(SOMBRE[fond]) < _luminance(SOMBRE["texte"])
        assert _luminance(CLAIR[fond]) > _luminance(CLAIR["texte"])


def test_choisir_theme_remplit_T_sur_place():
    """Un module qui a importé T avant le choix voit le bon thème."""
    deja_importe = T
    assert theme.choisir_theme("sombre") == "sombre"
    assert deja_importe["fond_page"] == SOMBRE["fond_page"]
    assert theme.est_sombre()
    assert theme.choisir_theme("n'importe quoi") == "clair"
    assert deja_importe["fond_page"] == CLAIR["fond_page"]


# ─────────────────────────── Le réglage ────────────────────────────────────

@pytest.fixture
def reglages(tmp_path):
    """Des préférences dans un fichier temporaire, jamais le registre."""
    return QSettings(str(tmp_path / "preferences.ini"), QSettings.IniFormat)


def test_sans_reglage_c_est_le_clair(reglages):
    assert theme.lire_theme(reglages) == "clair"


def test_le_choix_est_enregistre_puis_relu(reglages):
    assert theme.enregistrer_theme("sombre", reglages)
    assert theme.lire_theme(reglages) == "sombre"


def test_un_reglage_abime_donne_le_clair(reglages):
    reglages.setValue(theme.CLE_THEME, ["clair", "sombre"])
    assert theme.lire_theme(reglages) == "clair"
    reglages.setValue(theme.CLE_THEME, "violet")
    assert theme.lire_theme(reglages) == "clair"


def test_un_nom_inconnu_n_est_pas_enregistre(reglages):
    assert not theme.enregistrer_theme("violet", reglages)
    assert theme.lire_theme(reglages) == "clair"


# ─────────────────────────── La palette de Qt ──────────────────────────────

COUPLES_QT = [
    (QPalette.Window, QPalette.WindowText),
    (QPalette.Base, QPalette.Text),
    (QPalette.AlternateBase, QPalette.Text),
    (QPalette.Button, QPalette.ButtonText),
    (QPalette.ToolTipBase, QPalette.ToolTipText),
    (QPalette.Highlight, QPalette.HighlightedText),
]


def test_palette_sombre_de_qt_lisible_partout(qapp):
    from comptesbudget.app import palette_sombre
    pal = palette_sombre()
    for fond, texte in COUPLES_QT:
        assert contraste(pal.color(fond).name(), pal.color(texte).name()) >= 4.5
    # Le texte d'invite et le texte désactivé restent visibles (3 pour 1).
    assert contraste(pal.color(QPalette.PlaceholderText).name(),
                     pal.color(QPalette.Base).name()) >= 3
    assert contraste(
        pal.color(QPalette.Disabled, QPalette.WindowText).name(),
        pal.color(QPalette.Window).name()) >= 3


def test_palette_sombre_ne_garde_aucun_relief_clair(qapp):
    """Fusion dessine cadres et onglets avec Light, Mid, Dark… : laissés
    à leur valeur par défaut, ils resteraient clairs sur un fond sombre."""
    from comptesbudget.app import palette_sombre
    pal = palette_sombre()
    for role in (QPalette.Light, QPalette.Midlight, QPalette.Mid,
                 QPalette.Dark, QPalette.Shadow):
        assert _luminance(pal.color(role).name()) < 0.2


def test_appliquer_theme_suit_le_choix(qapp):
    from comptesbudget.app import appliquer_theme, appliquer_theme_clair
    from PySide6.QtWidgets import QToolTip
    theme.choisir_theme("sombre")
    appliquer_theme(qapp)
    try:
        assert qapp.palette().color(QPalette.Window).name().upper() == \
            SOMBRE["fond_page"]
        assert QToolTip.palette().color(QPalette.ToolTipBase).name().upper() \
            == SOMBRE["bulle_fond"]
    finally:
        theme.choisir_theme("clair")
        appliquer_theme_clair(qapp)


def test_contour_des_cases_suit_le_theme(qapp):
    from comptesbudget.app import StyleClair
    theme.choisir_theme("sombre")
    assert StyleClair().contour().name().upper() == SOMBRE["contour"]
    theme.choisir_theme("clair")
    assert StyleClair().contour().name().upper() == CLAIR["contour"]


# ─────────────────────────── La fenêtre ⚙️ Paramètres ──────────────────────

def test_parametres_coche_le_theme_enregistre(qapp):
    from comptesbudget.ui.dialogs import SettingsDialog
    dlg = SettingsDialog(None, "2026-01-01", 100.0, "Compte courant",
                         theme_actuel="sombre")
    assert dlg.radio_sombre.isChecked() and not dlg.radio_clair.isChecked()
    assert dlg.theme_choisi() == "sombre"
    # Sans indication, c'est le clair.
    assert SettingsDialog(None, "2026-01-01", 100.0).theme_choisi() == "clair"


def test_changer_de_theme_compte_comme_une_saisie(qapp):
    """Changé puis abandonné par Annuler, le thème ne se perd pas sans un
    mot (charte, « Saisie non enregistrée »)."""
    from comptesbudget.ui.dialogs import SettingsDialog
    dlg = SettingsDialog(None, "2026-01-01", 100.0, "Compte courant")
    avant = dlg._etat_saisie()
    dlg.radio_sombre.setChecked(True)
    assert dlg._etat_saisie() != avant


def _fenetre_avec_parametres(tmp_path, monkeypatch, coche):
    """La fenêtre principale, dont les Paramètres sont validés avec le
    thème `coche` et le solde laissé tel quel."""
    from PySide6.QtWidgets import QDialog, QMessageBox
    from comptesbudget.database import Database
    from comptesbudget.ui import dialogs, main_window
    messages = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(
        lambda parent, titre, texte: messages.append((titre, texte))))
    monkeypatch.setattr(dialogs.SettingsDialog, "exec",
                        lambda self: (getattr(self, f"radio_{coche}")
                                      .setChecked(True), QDialog.Accepted)[1])
    db = Database(str(tmp_path / "comptes.db"))
    db.set_setting("initial_date", "2026-01-01")
    db.set_setting("initial_balance", "100.0")
    return db, main_window.MainWindow(db), messages


def test_choisir_sombre_l_enregistre_et_le_dit(qapp, tmp_path, monkeypatch):
    db, fenetre, messages = _fenetre_avec_parametres(
        tmp_path, monkeypatch, "sombre")
    fenetre.action_settings()
    assert theme.lire_theme() == "sombre"
    assert messages == [("Apparence enregistrée",
                         "Pécule s'affichera en thème sombre au prochain "
                         "démarrage.")]
    # Le thème de la session ne change pas : il s'applique au redémarrage.
    assert theme.theme_actif() == "clair"


def test_valider_sans_changer_de_theme_ne_l_ecrit_pas(qapp, tmp_path,
                                                      monkeypatch):
    db, fenetre, messages = _fenetre_avec_parametres(
        tmp_path, monkeypatch, "clair")
    fenetre.action_settings()
    assert theme.preferences().value(theme.CLE_THEME) is None
    assert [t for t, _ in messages] == ["Solde de départ enregistré"]
