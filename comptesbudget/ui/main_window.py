"""Fenêtre principale de l'application."""

import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import (
    QIcon, QKeySequence, QShortcut,
)
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QFrame, QStatusBar, QDialog, QMessageBox, QFileDialog,
)

from ..constants import (
    APP_VERSION, _app_dir,
)
from ..utils import (
    canonical_cat, fmt_euro, fmt_date_fr,
    suggest_category,
)
from ..database import Database
from ..labels import clean_libelle
from ..csv_import import import_csv
from ..sync import write_sync_file, read_sync_file, merge_remote_into_db

from .widgets import PeriodBar
from .dialogs import SettingsDialog
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

class MainWindow(QMainWindow):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.setWindowTitle(f"Comptes et Budget — v{APP_VERSION}")
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
        menu = QWidget()
        menu.setFixedWidth(184)
        mv = QVBoxLayout(menu)
        mv.setContentsMargins(8, 8, 8, 8)
        mv.setSpacing(6)

        def add_btn(text, slot, tip=""):
            b = QPushButton(text)
            b.setMinimumHeight(30)
            b.setStyleSheet("text-align:left; padding-left:8px")
            b.setCursor(Qt.PointingHandCursor)
            if tip:
                b.setToolTip(tip)
            b.clicked.connect(slot)
            mv.addWidget(b)
            return b

        def add_sep():
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setFrameShadow(QFrame.Sunken)
            mv.addWidget(line)

        add_btn("➕ Nouvelle opération", self.action_new_tx)
        add_btn("📥 Importer CSV", self.action_import)
        add_sep()
        add_btn("🧹 Nettoyer catégories", self.action_clean_cats)
        add_btn("🔧 Harmoniser", self.action_harmonize,
                "Suggère une catégorie d'après le libellé (motifs prédéfinis)")
        add_btn("🔠 Harmoniser libellés", self.action_harmonize_labels,
                "Normalise la casse et regroupe les variantes des libellés "
                "(opérations et récurrences)")
        add_btn("🔍 Doublons", self.action_find_duplicates)
        add_btn("🔎 Rechercher", self.action_search,
                "Recherche dans tout l'historique (Ctrl+F) : "
                "libellé, note, catégorie, montant, date")
        add_sep()
        add_btn("💾 Exporter (JSON)", self.action_export,
                "Export complet : opérations, règles, budgets, récurrences "
                "et réglages (solde/date de départ)")
        add_btn("♻️ Restaurer (JSON)", self.action_import_json,
                "Réimporte un export JSON en le fusionnant : pour chaque "
                "enregistrement, la version la plus récente est conservée")
        add_btn("🖨 Rapport mensuel", self.action_monthly_report,
                "Bilan du mois : synthèse, budgets, dépenses — aperçu, PDF ou impression")
        add_sep()
        add_btn("⚙️ Paramètres", self.action_settings)
        add_sep()
        add_btn("📖 Notice", self.action_notice,
                "Mode d'emploi et glossaire")
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
        root.addWidget(menu)
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
        self.tabs.currentChanged.connect(self.refresh_current)
        self.period_bar.period_changed.connect(self.on_period_changed)
        self.period_bar.date_mode_changed.connect(self.on_date_mode_changed)

        # Statut
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage(f"Base : {self.db.path}")

        # Premier chargement
        self.refresh_all()

        # Premier lancement : inviter à renseigner le solde de départ
        QTimer.singleShot(0, self._maybe_prompt_initial_setup)

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
            self, "Importer un CSV bancaire", "",
            "Fichiers CSV (*.csv *.txt);;Tous (*.*)")
        if not path:
            return
        self._import_files([path])

    def _import_files(self, paths: list[str]):
        """Importe une liste de fichiers CSV et résume le résultat."""
        total_imp = 0
        total_skip = 0
        total_bad = 0
        total_pt = 0
        errors = []
        for p in paths:
            try:
                # Un fichier = une transaction groupée : import quasi instantané
                # (une seule écriture disque) et tout-ou-rien en cas d'erreur.
                with self.db.batch():
                    imp, skip, bad, pt = import_csv(p, self.db)
                total_imp += imp
                total_skip += skip
                total_bad += bad
                total_pt += pt
            except Exception as e:
                errors.append(f"{os.path.basename(p)} : {e}")
        msg = (f"{total_imp} opération(s) importée(s).\n"
               f"{total_skip} doublon(s) ignoré(s).")
        if total_pt:
            msg += (f"\n✔ {total_pt} opération(s) déjà enregistrée(s) pointée(s) "
                    "automatiquement (confirmées par le relevé).")
        if total_bad:
            msg += (f"\n\n⚠ {total_bad} ligne(s) NON importée(s) : montant illisible.\n"
                    "Vérifiez le fichier, ou saisissez ces opérations à la main.")
        if errors:
            msg += "\n\nErreurs :\n  • " + "\n  • ".join(errors)
        if errors or total_bad:
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
            if p.lower().endswith((".csv", ".txt")):
                out.append(p)
        return out

    def dragEnterEvent(self, event):
        if self._accepted_drop_paths(event):
            event.acceptProposedAction()
            self.statusBar().showMessage(
                "📥 Relâchez pour importer le(s) CSV…")
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self._accepted_drop_paths(event):
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
        dlg = SettingsDialog(self, d, b)
        if dlg.exec() != QDialog.Accepted:
            return
        nd, nb = dlg.values()
        self.db.set_setting("initial_date", nd)
        self.db.set_setting("initial_balance", str(nb))
        QMessageBox.information(self, "Paramètres",
            f"Solde de départ : {fmt_euro(nb)} au {fmt_date_fr(nd)}.")
        self.refresh_all()

    def _maybe_prompt_initial_setup(self):
        """Premier lancement : le solde de départ n'est pas encore renseigné.
        On invite l'utilisateur à le configurer (il reste libre de l'ignorer ;
        l'invite réapparaîtra au prochain lancement tant qu'il est vide)."""
        if self.db.get_setting("initial_balance"):
            return
        QMessageBox.information(
            self, "Bienvenue dans Comptes et Budget",
            "Pour bien démarrer, indiquez votre <b>solde de départ</b> : "
            "le solde de votre compte à la date de début choisie.<br><br>"
            "Vous pourrez le modifier à tout moment via le bouton "
            "« Paramètres » du menu de gauche.")
        self.action_settings()

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
