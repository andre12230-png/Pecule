"""Fenêtre principale de l'application."""

import os
import shutil
import sqlite3
from datetime import date

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import (
    QIcon, QKeySequence, QShortcut,
)
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QStatusBar, QDialog, QMessageBox, QFileDialog,
    QLabel, QComboBox, QScrollArea, QFrame,
)

from ..constants import (
    APP_VERSION, _app_dir,
)
from ..utils import (
    canonical_cat, fmt_euro, fmt_date_fr,
    suggest_category,
)
from ..database import Database
from ..labels import charger_alias, clean_libelle
from ..csv_import import diagnostiquer_fichier, import_csv
from ..ofx_import import import_ofx
from ..qif_import import import_qif
from ..sync import write_sync_file, read_sync_file, merge_remote_into_db

from .widgets import PeriodBar
from .dialogs import SettingsDialog, ComptesDialog, ArchivesDialog
from .assistants import HarmonizeDialog, HarmonizeLabelsDialog, DuplicatesDialog
from .report import MonthlyReportDialog
from .search import GlobalSearchDialog
from .views.operations import OperationsView
from .views.bilan import BilanView
from .views.budget import BudgetView
from .views.categories import CategoriesView
from .views.subcategories import SubcategoriesView
from .views.previsionnel import PrevisionnelView
from .views.rules_view import RulesView
from .views.notice import NoticeView
from .avis import AvisDialog, noter_premiere_utilisation, doit_inviter, inviter
from .recapitulatif import RecapComptesDialog
from .mise_a_jour import MiseAJourDialog

class MainWindow(QMainWindow):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.setWindowTitle(f"Pécule — v{APP_VERSION}")
        self.resize(1280, 800)

        # Icône de la fenêtre (Budget.ico à côté du .py/.exe)
        ico = os.path.join(_app_dir(), "Budget.ico")
        if os.path.exists(ico):
            self.setWindowIcon(QIcon(ico))

        # Glisser-déposer de fichiers CSV
        self.setAcceptDrops(True)

        # ── Menu d'actions vertical (à gauche) ──
        # (Auparavant une barre d'outils horizontale ; déplacé à gauche pour
        #  s'aligner sur les interfaces native et Qt.)
        # Les actions sont rangées par intention — saisir, consulter, mettre
        # au propre, gérer ses données, régler — chaque groupe annoncé par un
        # intitulé. Quinze boutons d'affilée ne se lisaient pas.
        menu = QWidget()
        menu.setFixedWidth(184)
        mv = QVBoxLayout(menu)
        mv.setContentsMargins(8, 8, 8, 8)
        mv.setSpacing(4)

        STYLE_BOUTON = (
            "QPushButton {"
            "  text-align:left; padding-left:8px;"
            "  border:1px solid #DCDCDC; border-radius:4px;"
            "  background:#FCFCFC; color:#222 }"
            "QPushButton:hover {"
            "  background:#EAF2FB; border-color:#9CC0E8 }"
            "QPushButton:pressed { background:#D8E7F7 }")

        # Le trait de separation est porte par le titre lui-meme : un
        # QFrame d'un pixel de haut ne se peint pas de facon fiable, alors
        # qu'une bordure de QLabel s'affiche toujours.
        STYLE_TITRE = (
            "color:#6E6E6E; font-size:8pt; font-weight:700;"
            "letter-spacing:1px; padding:0 0 3px 3px;"
            "border-bottom:1px solid #A9A9A9")

        def add_btn(text, slot, tip=""):
            b = QPushButton(text)
            b.setMinimumHeight(30)
            b.setStyleSheet(STYLE_BOUTON)
            b.setCursor(Qt.PointingHandCursor)
            if tip:
                b.setToolTip(tip)
            b.clicked.connect(slot)
            mv.addWidget(b)
            return b

        def add_section(titre):
            """Intitulé de groupe : un peu d'air, un mot en petites capitales,
            un filet. Renvoie ses widgets, pour pouvoir masquer le groupe."""
            espace = QWidget()
            espace.setFixedHeight(11 if mv.count() else 0)
            mv.addWidget(espace)
            lbl = QLabel(titre.upper())
            lbl.setStyleSheet(STYLE_TITRE)
            mv.addWidget(lbl)
            mv.addSpacing(2)
            return espace, lbl

        # ── Compte affiché ──
        # Le compte choisi ici commande TOUT l'écran : bilan, opérations,
        # budget, prévisionnel. Le groupe entier disparaît quand il n'y a
        # qu'un seul compte : rien d'inutile à l'écran.
        self.compte_espace, self.compte_label = add_section("Compte")
        self.compte_combo = QComboBox()
        self.compte_combo.setMinimumHeight(26)
        self.compte_combo.setToolTip(
            "Compte bancaire affiché. Chaque compte a ses propres "
            "opérations, budgets et prévisionnel.")
        self.compte_combo.currentIndexChanged.connect(self.on_compte_changed)
        mv.addWidget(self.compte_combo)
        # Les soldes de tous les comptes et leur total : caché lui aussi
        # quand il n'y a qu'un compte.
        self.btn_recap = add_btn(
            "📊 Tous les comptes", self.action_recap_comptes,
            "Soldes de tous vos comptes côte à côte, et leur total")

        add_section("Saisie")
        add_btn("➕ Nouvelle opération", self.action_new_tx)
        add_btn("📥 Importer un relevé", self.action_import,
                "Relevé bancaire CSV ou OFX téléchargé chez votre banque, ou "
                "fichier QIF exporté depuis un autre logiciel de comptes "
                "(Money, Quicken…)")

        add_section("Consulter")
        add_btn("🔎 Rechercher", self.action_search,
                "Recherche dans tout l'historique (Ctrl+F) : "
                "libellé, note, catégorie, montant, date")
        add_btn("🖨 Rapport mensuel", self.action_monthly_report,
                "Bilan du mois : synthèse, budgets, dépenses — aperçu, PDF ou impression")

        add_section("Mettre au propre")
        add_btn("🧹 Nettoyer catégories", self.action_clean_cats)
        add_btn("🔧 Harmoniser", self.action_harmonize,
                "Suggère une catégorie d'après le libellé (motifs prédéfinis)")
        add_btn("🔠 Harmoniser libellés", self.action_harmonize_labels,
                "Normalise la casse et regroupe les variantes des libellés "
                "(opérations et récurrences)")
        add_btn("🔍 Doublons", self.action_find_duplicates)

        add_section("Mes données")
        add_btn("📦 Archiver", self.action_archives,
                "Met de côté les opérations anciennes : elles sortent des "
                "listes sans être supprimées")
        add_btn("💾 Exporter (JSON)", self.action_export,
                "Export complet : opérations, règles, budgets, récurrences "
                "et réglages (solde/date de départ)")
        add_btn("♻️ Restaurer (JSON)", self.action_import_json,
                "Réimporte un export JSON en le fusionnant : pour chaque "
                "enregistrement, la version la plus récente est conservée")
        # Porte de secours après une mise à jour : sans elle, l'invite du
        # premier lancement est la seule occasion de retrouver son fichier.
        self.btn_reprendre = add_btn(
            "📂 Reprendre un fichier", self.action_reprendre_donnees,
            "Copie ici le comptes.db d'une ancienne installation. "
            "Possible tant que cette installation est vide.")

        add_section("Réglages")
        add_btn("🏦 Mes comptes", self.action_comptes,
                "Ajouter, renommer ou supprimer un compte bancaire")
        add_btn("⚙️ Paramètres", self.action_settings,
                "Solde et date de départ du compte affiché")

        add_section("Aide")
        add_btn("📖 Notice", self.action_notice,
                "Mode d'emploi et glossaire")
        add_btn("💬 Votre avis", self.action_avis,
                "Signaler un problème ou proposer une idée "
                "(questionnaire en ligne, dans votre navigateur)")
        # Libellé court : le menu de gauche fixe la largeur minimale de la
        # fenêtre, qui doit tenir en moitié d'écran.
        add_btn("🔄 Mise à jour", self.action_mise_a_jour,
                "Voir s'il existe une version plus récente "
                "(dans votre navigateur ; Pécule ne se connecte à rien)")
        mv.addStretch()

        # Raccourci Ctrl+F (auparavant porté par l'action de la barre d'outils).
        sc_search = QShortcut(QKeySequence("Ctrl+F"), self)
        sc_search.activated.connect(self.action_search)

        # ── Zone de droite : barre de période + onglets ──
        right = QWidget()
        cv = QVBoxLayout(right)
        cv.setContentsMargins(0, 0, 0, 0); cv.setSpacing(0)
        self.period_bar = PeriodBar()
        cv.addWidget(self.period_bar)

        # Onglets / vues
        self.tabs = QTabWidget()
        self.bilan_view = BilanView(db)
        self.ops_view = OperationsView(db)
        self.budget_view = BudgetView(db)
        self.cats_view = CategoriesView(db)
        self.subs_view = SubcategoriesView(db)
        self.rules_view = RulesView(db)
        self.prev_view = PrevisionnelView(db)

        self.tabs.addTab(self.bilan_view, "🏠 Bilan")
        self.tabs.addTab(self.ops_view, "📋 Opérations")
        self.tabs.addTab(self.budget_view, "🎯 Budget")
        self.tabs.addTab(self.cats_view, "🏷️ Catégories")
        self.tabs.addTab(self.subs_view, "🏷️ Sous-catégories")
        self.tabs.addTab(self.rules_view, "🧠 Règles auto")
        self.tabs.addTab(self.prev_view, "🔮 Prévisionnel")

        cv.addWidget(self.tabs)

        # ── Assemblage : menu à gauche, contenu à droite ──
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
        # Le menu défile si la fenêtre est trop courte pour lui. Ses seize
        # boutons empilés réclamaient 730 px de haut — mesuré — et fixaient à
        # eux seuls la hauteur minimale de la fenêtre à 754 px : trop pour un
        # portable 1366 × 768, où le bas de l'écran passait sous la barre des
        # tâches. Sur un grand écran, rien ne change : aucune barre de
        # défilement n'apparaît tant que la place suffit.
        menu_defilant = QScrollArea()
        menu_defilant.setWidget(menu)
        menu_defilant.setWidgetResizable(True)
        menu_defilant.setFrameShape(QFrame.NoFrame)
        menu_defilant.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        menu_defilant.setFixedWidth(menu.width())
        root.addWidget(menu_defilant)
        root.addWidget(right, 1)
        self.setCentralWidget(central)

        # Signaux
        self.ops_view.tx_changed.connect(self.refresh_all)
        self.rules_view.rules_changed.connect(self.refresh_all)
        self.budget_view.budget_changed.connect(self.refresh_all)
        self.cats_view.cat_changed.connect(self.refresh_all)
        self.subs_view.sub_changed.connect(self.refresh_all)
        self.prev_view.changed.connect(self.refresh_all)
        self.bilan_view.goto_budget.connect(
            lambda: self.tabs.setCurrentWidget(self.budget_view))
        # Le bandeau « solde de départ non renseigné » ouvre les Paramètres.
        self.bilan_view.goto_parametres.connect(self.action_settings)
        self.tabs.currentChanged.connect(self.refresh_current)
        self.period_bar.period_changed.connect(self.on_period_changed)
        self.period_bar.date_mode_changed.connect(self.on_date_mode_changed)
        self.period_bar.archives_toggled.connect(self.on_archives_toggled)

        # Statut
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage(f"Base : {self.db.path}")

        # Premier chargement
        self.refresh_all()

        # Départ du compte à rebours de l'invitation « Votre avis ».
        noter_premiere_utilisation(self.db, date.today())

        # Premier lancement : inviter à renseigner le solde de départ
        QTimer.singleShot(0, self._premier_lancement)

    def _period_aware_views(self):
        return [self.bilan_view, self.ops_view, self.budget_view, self.cats_view]

    def on_period_changed(self, period: str):
        for w in self._period_aware_views():
            w.period = period
        self.refresh_all()

    def on_date_mode_changed(self, mode: str):
        for w in self._period_aware_views():
            if hasattr(w, "date_mode"):
                w.date_mode = mode
        self.refresh_all()

    def refresh_all(self):
        # Liste des comptes (et visibilité du sélecteur)
        self._fill_comptes()
        # « Reprendre un fichier » ne sert qu'à une installation encore vide :
        # le bouton disparaît dès qu'il y a quelque chose à perdre.
        self.btn_reprendre.setVisible(self.db.est_vide())
        # Case « Voir les archives » : visible s'il y a des archives
        self.period_bar.set_archives_disponibles(self.db.nb_archivees())
        # Périodes disponibles
        txs = [dict(r) for r in self.db.list_tx()]
        self.period_bar.update_periods(txs)
        # Propager la période courante et le mode date
        p = self.period_bar.current_period()
        m = self.period_bar.current_date_mode()
        for w in self._period_aware_views():
            w.period = p
            if hasattr(w, "date_mode"):
                w.date_mode = m
        # Refresh
        self.bilan_view.refresh()
        self.ops_view.reload_from_db()
        self.budget_view.refresh()
        self.cats_view.refresh()
        self.subs_view.refresh()
        self.rules_view.refresh()
        self.prev_view.refresh()

    # ── Comptes ─────────────────────────────────────────────────────
    def _fill_comptes(self):
        """Remplit la liste déroulante des comptes sans rien recharger.
        Le sélecteur reste caché tant qu'il n'y a qu'un seul compte."""
        comptes = self.db.list_comptes()
        visible = len(comptes) > 1
        for w in (self.compte_espace, self.compte_label, self.compte_combo,
                  self.btn_recap):
            w.setVisible(visible)

        self.compte_combo.blockSignals(True)
        self.compte_combo.clear()
        for r in comptes:
            self.compte_combo.addItem(r["nom"], r["id"])
        idx = self.compte_combo.findData(self.db.compte_id)
        if idx >= 0:
            self.compte_combo.setCurrentIndex(idx)
        self.compte_combo.blockSignals(False)

        titre = f"Pécule — v{APP_VERSION}"
        if visible:
            titre += f" — {self.db.nom_compte()}"
        self.setWindowTitle(titre)

    def on_compte_changed(self):
        """Changement de compte : tout l'écran suit."""
        cid = self.compte_combo.currentData()
        if not cid or cid == self.db.compte_id:
            return
        self.db.set_compte_courant(cid)
        # Les périodes disponibles changent avec le compte : on repart du
        # mois en cours plutôt que de garder une période qui n'existe pas.
        self.period_bar.reset_selection()
        self.refresh_all()
        self.statusBar().showMessage(
            f"Compte affiché : {self.db.nom_compte()}", 5000)

    def on_archives_toggled(self, voir: bool):
        """Affiche ou masque les opérations archivées. Le solde de départ
        suit tout seul : il repart du début quand on montre les archives."""
        self.db.set_voir_archives(voir)
        self.period_bar.reset_selection()
        self.refresh_all()
        self.statusBar().showMessage(
            "Archives affichées" if voir else "Archives masquées", 4000)

    def action_archives(self):
        ArchivesDialog(self.db, self).exec()
        self.period_bar.reset_selection()
        self.refresh_all()

    def action_recap_comptes(self):
        """Récapitulatif de tous les comptes. Un double-clic sur un compte
        l'affiche : la liste déroulante fait le reste (on_compte_changed)."""
        dlg = RecapComptesDialog(self.db, self)
        if dlg.exec() and dlg.compte_choisi:
            idx = self.compte_combo.findData(dlg.compte_choisi)
            if idx >= 0:
                self.compte_combo.setCurrentIndex(idx)

    def action_comptes(self):
        avant = self.db.compte_id
        ComptesDialog(self.db, self).exec()
        if self.db.compte_id != avant:
            self.period_bar.reset_selection()
        self.refresh_all()

    def refresh_current(self, idx: int):
        w = self.tabs.widget(idx)
        if hasattr(w, "refresh"):
            w.refresh()
        if hasattr(w, "reload_from_db"):
            w.reload_from_db()

    # ── Actions ─────────────────────────────────────────────────────
    def action_new_tx(self):
        self.tabs.setCurrentWidget(self.ops_view)
        self.ops_view.add_tx()

    def action_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importer un relevé", "",
            "Relevés (*.csv *.txt *.ofx *.qfx *.qif);;"
            "Fichiers CSV (*.csv *.txt);;Fichiers OFX (*.ofx *.qfx);;"
            "Fichiers QIF (*.qif);;Tous (*.*)")
        if not path:
            return
        self._import_files([path])

    def _import_files(self, paths: list[str]):
        """Importe une liste de relevés (CSV, OFX ou QIF) et résume le résultat."""
        total_imp = 0
        total_skip = 0
        total_bad = 0
        total_pt = 0
        total_recap = 0
        total_rappr = 0
        errors = []
        for p in paths:
            try:
                # Un fichier = une transaction groupée : import quasi instantané
                # (une seule écriture disque) et tout-ou-rien en cas d'erreur.
                # Le format se reconnaît à l'extension ; les trois imports
                # rendent le même compte rendu.
                lecteur = import_csv
                if p.lower().endswith(".qif"):
                    lecteur = import_qif
                elif p.lower().endswith((".ofx", ".qfx")):
                    lecteur = import_ofx
                with self.db.batch():
                    imp, skip, bad, pt, recap, rappr = lecteur(p, self.db)
                total_imp += imp
                total_skip += skip
                total_bad += bad
                total_pt += pt
                total_recap += recap
                total_rappr += rappr
            except Exception as e:
                errors.append(f"{os.path.basename(p)} : {e}")
        msg = (f"{total_imp} opération(s) importée(s).\n"
               f"{total_skip} doublon(s) ignoré(s).")
        if total_recap:
            # Pas de pictogramme sur cette ligne : la carte bancaire (U+1F4B3)
            # ne fait pas partie de Segoe UI, la police des boîtes de dialogue,
            # et s'affichait comme un rectangle noir illisible. Les symboles
            # des lignes voisines (✔, ⏳, ⚠), eux, sont bien dans la police.
            msg += (f"\n{total_recap} récapitulatif(s) de débit différé "
                    "écarté(s) : les achats carte du relevé sont déjà "
                    "détaillés un par un.")
        if total_pt:
            msg += (f"\n✔ {total_pt} opération(s) déjà enregistrée(s) pointée(s) "
                    "automatiquement (confirmées par le relevé).")
        if total_rappr:
            msg += (f"\n⏳ {total_rappr} échéance(s) prévue(s) rattachée(s) à la "
                    "ligne correspondante du relevé (date et montant réels "
                    "repris) — aucun doublon créé.")
        if total_bad:
            msg += (f"\n\n⚠ {total_bad} ligne(s) NON importée(s) : montant illisible.\n"
                    "Vérifiez le fichier, ou saisissez ces opérations à la main.")
        # Rien du tout n'a été lu : annoncer « 0 opération importée » sans un
        # mot laissait l'utilisateur devant une énigme. On cherche la cause
        # dans le fichier lui-même (séparateur, noms de colonnes, dates).
        rien_lu = not any((total_imp, total_skip, total_bad,
                           total_pt, total_recap, total_rappr))
        if rien_lu and not errors:
            for p in paths:
                # Le diagnostic ne vaut que pour un CSV : appliqué à un OFX
                # ou un QIF, il dirait n'importe quoi sur leurs colonnes.
                if not p.lower().endswith((".csv", ".txt")):
                    continue
                cause = diagnostiquer_fichier(p)
                if cause:
                    msg += (f"\n\n⚠ Aucune ligne n'a pu être lue dans "
                            f"« {os.path.basename(p)} ».\n\n{cause}")
        if errors:
            msg += "\n\nErreurs :\n  • " + "\n  • ".join(errors)
        if errors or total_bad or rien_lu:
            QMessageBox.warning(self, "Import", msg)
        else:
            QMessageBox.information(self, "Import", msg)
        self.refresh_all()

    # ── Glisser-déposer de fichiers ─────────────────────────────────
    def _accepted_drop_paths(self, event) -> list[str]:
        if not event.mimeData().hasUrls():
            return []
        out = []
        for url in event.mimeData().urls():
            if not url.isLocalFile():
                continue
            p = url.toLocalFile()
            if p.lower().endswith((".csv", ".txt", ".ofx", ".qfx", ".qif")):
                out.append(p)
        return out

    # Formats souvent déposés par erreur, et ce qu'il faut en faire. Les
    # ignorer en silence donnait l'impression que le glisser-déposer était
    # cassé — or beaucoup de banques ne proposent que l'export Excel.
    CONSEILS_DEPOT = {
        (".xls", ".xlsx", ".xlsm", ".ods"):
            "Un fichier tableur n'est pas un relevé texte : Pécule ne sait "
            "pas le lire.\n\nOuvrez-le dans votre tableur, puis "
            "« Enregistrer sous » en choisissant « CSV (séparateur : "
            "point-virgule) ». Si votre banque propose le CSV ou l'OFX à "
            "l'export, prenez-le directement.",
        (".pdf",):
            "Un relevé PDF ne peut pas être importé : c'est une image de "
            "page, pas un tableau de données.\n\nSur le site de votre "
            "banque, cherchez « exporter » ou « télécharger » vos opérations "
            "au format CSV ou OFX.",
        (".json",):
            "Pour réimporter un export JSON de Pécule, passez par le bouton "
            "« Restaurer (JSON) » du menu de gauche : il fusionne vos "
            "données au lieu de les remplacer.",
    }

    def _conseil_depot(self, event) -> str:
        """Message d'aide pour un fichier déposé que l'on ne sait pas lire."""
        if not event.mimeData().hasUrls():
            return ""
        for url in event.mimeData().urls():
            nom = url.toLocalFile().lower()
            for extensions, conseil in self.CONSEILS_DEPOT.items():
                if nom.endswith(extensions):
                    return conseil
        return ""

    def dragEnterEvent(self, event):
        if self._accepted_drop_paths(event):
            event.acceptProposedAction()
            self.statusBar().showMessage(
                "📥 Relâchez pour importer le(s) relevé(s)…")
        elif self._conseil_depot(event):
            # On accepte le dépôt pour pouvoir expliquer le refus.
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self._accepted_drop_paths(event) or self._conseil_depot(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.statusBar().showMessage(f"Base : {self.db.path}")
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        paths = self._accepted_drop_paths(event)
        self.statusBar().showMessage(f"Base : {self.db.path}")
        if not paths:
            conseil = self._conseil_depot(event)
            if conseil:
                event.acceptProposedAction()
                QMessageBox.information(self, "Fichier non importable", conseil)
            else:
                event.ignore()
            return
        event.acceptProposedAction()
        self._import_files(paths)

    def action_clean_cats(self):
        txs = [dict(r) for r in self.db.list_tx()]
        changes = []
        for t in txs:
            canon = canonical_cat(t.get("categorie", ""))
            if canon and canon != t.get("categorie"):
                changes.append((t["id"], t["categorie"], canon))
        if not changes:
            QMessageBox.information(self, "Nettoyage",
                "Toutes les catégories sont déjà normalisées.")
            return
        # Récapitulatif
        groups = {}
        for _, fr, to in changes:
            groups[(fr, to)] = groups.get((fr, to), 0) + 1
        summary = "\n".join(
            f"  • « {fr} » → « {to} » ({n})"
            for (fr, to), n in sorted(groups.items(), key=lambda x: -x[1]))
        msg = f"{len(changes)} catégorie(s) à normaliser :\n\n{summary}\n\nAppliquer ?"
        if QMessageBox.question(self, "Nettoyer les catégories", msg) != QMessageBox.Yes:
            return
        with self.db.batch():
            for tx_id, _, to in changes:
                self.db.update_tx(tx_id, {"categorie": to})
        QMessageBox.information(self, "Nettoyage",
            f"{len(changes)} catégorie(s) normalisée(s).")
        self.refresh_all()

    def action_settings(self):
        d = self.db.get_setting("initial_date", "2025-01-01")
        try:
            b = float(self.db.get_setting("initial_balance", "0"))
        except ValueError:
            b = 0.0
        # « Jamais renseigné » n'est pas la même chose qu'un solde de zéro :
        # la colonne solde_initial du compte vaut NULL tant que rien n'a été
        # saisi (cf. le bandeau du Bilan).
        compte = self.db.get_compte()
        jamais_renseigne = compte is None or compte["solde_initial"] is None
        dlg = SettingsDialog(self, d, b, self.db.nom_compte())
        if dlg.exec() != QDialog.Accepted:
            return
        nd, nb = dlg.values()
        # Valider le formulaire sans y toucher enregistrait 0,00 € — et
        # l'invite du premier lancement ne revenait plus jamais, laissant un
        # solde faux pour toujours. On demande confirmation, une seule fois.
        if jamais_renseigne and abs(nb) < 0.005:
            reponse = QMessageBox.question(
                self, "Solde de départ",
                f"Vous enregistrez un solde de départ de <b>0,00 €</b> au "
                f"{fmt_date_fr(nd)}.<br><br>"
                "Ce n'est juste que si votre compte était vide à cette date. "
                "Sinon, le solde affiché par Pécule sera faux de tout ce que "
                "vous aviez en banque.<br><br>Enregistrer quand même ?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reponse != QMessageBox.Yes:
                return
        # Le plafond d'encours carte a été retiré le 07/09/2026 : le bandeau
        # du Bilan calcule maintenant ce qui reste d'après les mouvements
        # réels du mois. L'ancienne valeur dort encore dans la table
        # `settings`, inutilisée — rien n'est effacé des données.
        self.db.set_setting("initial_date", nd)
        self.db.set_setting("initial_balance", str(nb))
        QMessageBox.information(
            self, "Paramètres",
            f"« {self.db.nom_compte()} » — solde de départ : "
            f"{fmt_euro(nb)} au {fmt_date_fr(nd)}.")
        self.refresh_all()

    def _premier_lancement(self):
        """Ce qui se joue à l'ouverture, dans l'ordre : d'abord retrouver des
        données existantes, ensuite seulement demander le solde de départ —
        un fichier repris apporte le sien."""
        if self._maybe_prompt_reprise_donnees():
            return
        if self._maybe_prompt_initial_setup():
            return
        # Une seule boîte par ouverture : l'invitation à donner son avis
        # attend un lancement où rien d'autre n'a été demandé.
        if doit_inviter(self.db, date.today()):
            inviter(self, self.db, date.today())

    def _maybe_prompt_reprise_donnees(self) -> bool:
        """Base vide : dire où elle est, et proposer d'y reprendre un fichier.

        C'est le piège de la mise à jour. On télécharge la nouvelle version,
        on la décompresse dans « Téléchargements », on double-clique : comme
        il n'y a pas de comptes.db à côté de ce nouvel exécutable, Pécule
        ouvre une base NEUVE dans le dossier personnel. L'application s'ouvre
        vide et on croit avoir tout perdu, alors que le fichier dort dans
        l'ancien dossier.

        Retourne True si des données ont été reprises."""
        if not self.db.est_vide():
            return False
        boite = QMessageBox(self)
        boite.setWindowTitle("Bienvenue dans Pécule")
        boite.setTextFormat(Qt.RichText)
        boite.setText(
            "Cette installation ne contient <b>aucune donnée</b>.<br><br>"
            # Sans <code> : la police à chasse fixe rallonge le chemin, qui
            # se coupait alors au milieu (« C: » seul sur sa ligne).
            "Vos opérations seront enregistrées dans :<br>"
            f"<b>{self.db.path}</b><br><br>"
            "<b>Si vous utilisiez déjà Pécule</b> — vous venez de le mettre à "
            "jour, ou de changer d'ordinateur — vos données sont dans le "
            "fichier <code>comptes.db</code> de votre ancienne installation. "
            "Reprenez-le : il sera copié ici, et rien ne sera perdu.")
        bouton_reprendre = boite.addButton("Reprendre mes données…",
                                           QMessageBox.AcceptRole)
        boite.addButton("Démarrer à neuf", QMessageBox.RejectRole)
        boite.exec()
        if boite.clickedButton() is not bouton_reprendre:
            return False
        return self.action_reprendre_donnees()

    def action_reprendre_donnees(self) -> bool:
        """Copie un comptes.db choisi par l'utilisateur à la place de la base
        courante, puis recharge tout. Ne fait rien si la base a déjà servi."""
        chemin, _ = QFileDialog.getOpenFileName(
            self, "Reprendre un fichier de données Pécule", "",
            "Données Pécule (comptes.db *.db);;Tous (*.*)")
        if not chemin:
            return False
        if os.path.abspath(chemin) == os.path.abspath(self.db.path):
            QMessageBox.information(
                self, "Reprendre mes données",
                "C'est le fichier que Pécule utilise déjà.")
            return False
        erreur = self._verifier_base_pecule(chemin)
        if erreur:
            QMessageBox.warning(self, "Reprendre mes données", erreur)
            return False
        if not self.db.est_vide():
            # Garde-fou : on ne remplace jamais des données existantes.
            QMessageBox.warning(
                self, "Reprendre mes données",
                "Cette installation contient déjà des opérations : elles "
                "seraient perdues.\n\nPour fusionner deux fichiers, passez "
                "par « Exporter (JSON) » depuis l'autre installation, puis "
                "« Restaurer (JSON) » ici.")
            return False
        try:
            self.db.conn.close()          # Windows refuse d'écraser un fichier ouvert
            shutil.copy2(chemin, self.db.path)
            self.db.rouvrir()
        except (OSError, sqlite3.Error) as e:
            self.db.rouvrir()             # on retombe sur la base d'origine
            QMessageBox.critical(
                self, "Reprendre mes données",
                f"La copie a échoué :\n{e}\n\nRien n'a été modifié.")
            return False
        charger_alias(self.db.get_alias_libelles())
        self._fill_comptes()
        self.refresh_all()
        n = len(self.db.list_tx())
        QMessageBox.information(
            self, "Reprendre mes données",
            f"Vos données sont reprises : {n} opération(s) sur le compte "
            f"« {self.db.nom_compte()} ».\n\nL'ancien fichier n'a pas été "
            "touché — gardez-le de côté jusqu'à ce que tout vous paraisse "
            "juste. Les sauvegardes automatiques recommencent ici, à côté de "
            "la nouvelle base.")
        return True

    @staticmethod
    def _verifier_base_pecule(chemin: str) -> str:
        """Message d'erreur si ce fichier n'est pas une base Pécule, sinon ''."""
        try:
            with sqlite3.connect(f"file:{chemin}?mode=ro", uri=True) as conn:
                tables = {r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}
        except sqlite3.Error:
            return ("Ce fichier n'est pas une base de données Pécule "
                    "(il n'a pas pu être ouvert).")
        if not {"transactions", "settings"} <= tables:
            return ("Ce fichier ne ressemble pas à une base Pécule : il n'y "
                    "a ni opérations ni réglages dedans.")
        return ""

    def _maybe_prompt_initial_setup(self):
        """Premier lancement : le solde de départ n'est pas encore renseigné.
        On invite l'utilisateur à le configurer (il reste libre de l'ignorer ;
        l'invite réapparaîtra au prochain lancement tant qu'il est vide).
        Renvoie True si l'invite a été montrée."""
        if self.db.get_setting("initial_balance"):
            return False
        QMessageBox.information(
            self, "Bienvenue dans Pécule",
            "Pour bien démarrer, indiquez votre <b>solde de départ</b> : "
            "le solde de votre compte à la date de début choisie.<br><br>"
            "Vous pourrez le modifier à tout moment via le bouton "
            "« Paramètres » du menu de gauche.")
        self.action_settings()
        return True

    def action_harmonize(self):
        """Propose des recatégorisations d'après les libellés (HARMONIZE_RULES)."""
        txs = [dict(r) for r in self.db.list_tx()]
        suggestions: list[tuple[dict, str]] = []
        for t in txs:
            if t.get("categorie") == "Transaction exclue":
                continue
            suggested = suggest_category(t.get("libelle", ""), t.get("sous_cat", ""))
            if suggested and suggested != t.get("categorie"):
                suggestions.append((t, suggested))
        if not suggestions:
            QMessageBox.information(self, "Harmoniser",
                "Aucune suggestion : toutes les catégories sont déjà cohérentes.")
            return
        dlg = HarmonizeDialog(self, suggestions)
        if dlg.exec() != QDialog.Accepted:
            return
        changes = dlg.selected()
        with self.db.batch():
            for tx_id, new_cat in changes:
                self.db.update_tx(tx_id, {"categorie": new_cat})
        QMessageBox.information(self, "Harmoniser",
            f"{len(changes)} opération(s) recatégorisée(s).")
        self.refresh_all()

    def action_harmonize_labels(self):
        """Normalise et regroupe les libellés des opérations et des
        récurrences (casse propre, retrait des numéros / références)."""
        txs = [dict(r) for r in self.db.list_tx()]
        recs = [dict(r) for r in self.db.list_recurring()]

        # Agrégation par libellé d'origine → ids concernés (tx + récurrences)
        agg: dict[str, dict] = {}
        for t in txs:
            old = t.get("libelle", "") or ""
            if not old:
                continue
            agg.setdefault(old, {"old": old, "tx_ids": [], "rec_ids": []})
            agg[old]["tx_ids"].append(t["id"])
        for r in recs:
            old = r.get("libelle", "") or ""
            if not old:
                continue
            agg.setdefault(old, {"old": old, "tx_ids": [], "rec_ids": []})
            agg[old]["rec_ids"].append(r["id"])

        rows = []
        for old, d in agg.items():
            new = clean_libelle(old)
            if new == old:
                continue
            d["new"] = new
            d["n"] = len(d["tx_ids"]) + len(d["rec_ids"])
            rows.append(d)

        if not rows:
            QMessageBox.information(self, "Harmoniser les libellés",
                "Tous les libellés sont déjà harmonisés.")
            return

        rows.sort(key=lambda d: (-d["n"], d["old"].lower()))
        dlg = HarmonizeLabelsDialog(self, rows)
        if dlg.exec() != QDialog.Accepted:
            return
        chosen = dlg.selected()
        if not chosen:
            return

        n_tx = n_rec = 0
        with self.db.batch():
            for d in chosen:
                for tx_id in d["tx_ids"]:
                    self.db.update_tx(tx_id, {"libelle": d["new"]})
                    n_tx += 1
                for rec_id in d["rec_ids"]:
                    self.db.update_recurring(rec_id, {"libelle": d["new"]})
                    n_rec += 1
        QMessageBox.information(self, "Harmoniser les libellés",
            f"{len(chosen)} libellé(s) harmonisé(s) — "
            f"{n_tx} opération(s) et {n_rec} récurrence(s) mises à jour.")
        self.refresh_all()

    def action_find_duplicates(self):
        txs = [dict(r) for r in self.db.list_tx()]
        seen = {}
        dups = []
        for t in txs:
            key = (t.get("date"), round(t.get("montant", 0), 2),
                   (t.get("libelle") or "")[:20].lower())
            if key in seen:
                dups.append(t)
            else:
                seen[key] = t
        if not dups:
            QMessageBox.information(self, "Doublons", "Aucun doublon détecté.")
            return
        # Vérification ligne par ligne AVANT suppression : deux opérations
        # identiques le même jour peuvent être légitimes (deux achats
        # identiques), la fenêtre permet de les décocher.
        dlg = DuplicatesDialog(self, dups)
        if dlg.exec() != QDialog.Accepted:
            return
        ids = dlg.selected()
        if not ids:
            return
        with self.db.batch():
            for tx_id in ids:
                self.db.delete_tx(tx_id)
        QMessageBox.information(self, "Doublons",
            f"{len(ids)} opération(s) supprimée(s).")
        self.refresh_all()

    def action_export(self):
        """Export JSON COMPLET (via le snapshot de synchronisation) : inclut
        aussi les réglages (solde/date de départ) et les suppressions, pour
        pouvoir être réimporté par « Restaurer (JSON) »."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter les données", "comptes_export.json",
            "JSON (*.json)")
        if not path:
            return
        write_sync_file(self.db, path)
        QMessageBox.information(self, "Export",
            f"Données exportées : {path}\n\n"
            "L'export contient opérations, règles, budgets, récurrences et "
            "réglages. Il peut être réimporté via « ♻️ Restaurer (JSON) ».")

    def action_import_json(self):
        """Restaure/fusionne un export JSON : pour chaque enregistrement, la
        version la plus récente gagne (rien de plus récent que le fichier
        n'est écrasé) ; les suppressions plus récentes sont propagées."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Restaurer / fusionner un export JSON", "", "JSON (*.json)")
        if not path:
            return
        data = read_sync_file(path)
        if data is None:
            QMessageBox.warning(self, "Restaurer",
                "Fichier illisible : ce n'est pas un export JSON de l'application.")
            return
        if QMessageBox.question(
                self, "Restaurer / fusionner",
                "Fusionner ce fichier avec vos données ?\n\n"
                "Pour chaque opération, règle ou récurrence, la version la "
                "plus récente est conservée : rien de plus récent que le "
                "fichier ne sera écrasé.") != QMessageBox.Yes:
            return
        stats = merge_remote_into_db(self.db, data)
        QMessageBox.information(self, "Restaurer",
            f"Fusion terminée : {stats['applied']} enregistrement(s) "
            f"appliqué(s), {stats['deleted']} suppression(s) propagée(s).")
        self.refresh_all()

    def action_monthly_report(self):
        MonthlyReportDialog(self, self.db).exec()

    def action_search(self):
        dlg = GlobalSearchDialog(self, self.db)
        dlg.exec()
        if dlg.changed:
            self.refresh_all()

    def action_notice(self):
        """Ouvre la notice (mode d'emploi + glossaire) dans une fenêtre.
        Auparavant un onglet ; déplacée dans le menu de gauche."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Notice — mode d'emploi")
        dlg.resize(900, 680)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(NoticeView())
        dlg.exec()

    def action_avis(self):
        """Ouvre la fenêtre « Votre avis » (questionnaire en ligne)."""
        AvisDialog(self).exec()

    def action_mise_a_jour(self):
        """Ouvre la fenêtre « Mise à jour » : la version installée, et la
        page de la dernière version dans le navigateur, à la demande."""
        MiseAJourDialog(self).exec()
