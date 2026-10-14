"""Audit du 14/10/2026, lot 1 : protéger les fichiers de comptes.

A01 — un export (CSV, JSON, PDF) pouvait écraser la base de comptes choisie
      par erreur comme destination ;
A02 — une fusion d'export pouvait modifier les comptes avant d'échouer, et
      acceptait un fichier qui n'était pas un export de Pécule ;
A07 — la construction effaçait sans vérifier une base laissée dans dist\\ ;
A08 — l'outil d'archive échouait sous Windows en effaçant une base qu'il
      gardait ouverte ;
R01 — l'archive publiée emportait tout fichier laissé dans dist\\Pecule.
Données inventées.
"""
import hashlib
import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

from comptesbudget.database import Database

RACINE = Path(__file__).resolve().parent.parent


def _op(**kw):
    base = {"id": "x", "date": "2026-06-01", "date_valeur": "2026-06-01",
            "libelle": "OP", "libelle_op": "OP", "reference": "", "type": "",
            "categorie": "Non classé", "sous_cat": "", "info": "",
            "montant": -10.0, "pointee": 1}
    base.update(kw)
    return base


def _empreinte(chemin) -> str:
    return hashlib.sha256(Path(chemin).read_bytes()).hexdigest()


@pytest.fixture
def base(tmp_path):
    db = Database(str(tmp_path / "comptes.db"))
    db.set_setting("initial_date", "2026-01-01")
    db.set_setting("initial_balance", "100.0")
    db.insert_tx(_op(id="a", libelle_op="MAGASIN"))
    return db


def _base_intacte(db):
    """La base se lit encore, avec son opération."""
    conn = sqlite3.connect(db.path)
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("SELECT count(*) FROM transactions").fetchone()[0] == 1
    finally:
        conn.close()


# ─────────────────────────── A01 : destinations des exports ────────────────

def test_destination_refusee():
    from comptesbudget.destinations import destination_refusee
    base = "C:/Pecule/comptes.db"
    assert destination_refusee("C:/Pecule/comptes.db", base)
    assert destination_refusee("D:/ailleurs/vieux-comptes.db", base)
    assert destination_refusee("D:/ailleurs/comptes.db-wal", base)
    assert destination_refusee("D:/ailleurs/notes.sqlite", base)
    assert destination_refusee("D:/Documents/export.csv", base) is None


def test_avec_extension():
    from comptesbudget.destinations import avec_extension
    assert avec_extension("D:/x/export", ".csv") == "D:/x/export.csv"
    assert avec_extension("D:/x/export.CSV", ".csv") == "D:/x/export.CSV"
    assert avec_extension("D:/x/comptes.db", ".csv") == "D:/x/comptes.db.csv"


def test_export_csv_refuse_la_base(qapp, base, monkeypatch):
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    from comptesbudget.ui.views.operations import OperationsView
    vue = OperationsView(base)
    vue.period = "all"
    vue.reload_from_db()
    avant = _empreinte(base.path)
    messages = []
    # Le chemin exact de la base, extension .csv refusée par l'utilisateur :
    # c'est le cas de l'audit (filtre « *.csv » ignoré).
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        lambda *a, **k: (base.path, ""))
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda parent, titre, texte, *a: messages.append(texte))
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.Close)
    vue.exporter_csv()
    assert _empreinte(base.path) == avant
    _base_intacte(base)
    assert not Path(base.path + ".csv").exists() or messages


def test_export_csv_ajoute_son_extension(qapp, base, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    from comptesbudget.ui.views.operations import OperationsView
    vue = OperationsView(base)
    vue.period = "all"
    vue.reload_from_db()
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        lambda *a, **k: (str(tmp_path / "sortie"), ""))
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.Close)
    vue.exporter_csv()
    assert (tmp_path / "sortie.csv").exists()


def test_export_json_refuse_la_base(qapp, base, monkeypatch):
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    from comptesbudget.ui.main_window import MainWindow
    fenetre = MainWindow(base)
    avant = _empreinte(base.path)
    messages = []
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        lambda *a, **k: (base.path, ""))
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda parent, titre, texte, *a: messages.append(texte))
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    fenetre.action_export()
    assert messages
    assert _empreinte(base.path) == avant
    _base_intacte(base)


def test_export_json_dit_son_echec(qapp, base, tmp_path, monkeypatch):
    """R02 : un export qui échoue le dit en clair, au lieu de planter."""
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    from comptesbudget.ui import main_window
    fenetre = main_window.MainWindow(base)
    messages = []

    def refuse(*a, **k):
        raise PermissionError(13, "Permission denied")
    monkeypatch.setattr(main_window, "write_sync_file", refuse)
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        lambda *a, **k: (str(tmp_path / "x.json"), ""))
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda parent, titre, texte, *a: messages.append(texte))
    fenetre.action_export()
    assert messages and "Permission denied" not in messages[0]


def test_rapport_pdf_refuse_la_base(qapp, base, monkeypatch):
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    from comptesbudget.ui.report import MonthlyReportDialog
    rapport = MonthlyReportDialog(None, base)
    avant = _empreinte(base.path)
    messages = []
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        lambda *a, **k: (base.path, ""))
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda parent, titre, texte, *a: messages.append(texte))
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    rapport._save_pdf()
    assert messages
    assert _empreinte(base.path) == avant
    _base_intacte(base)


# ─────────────────────────── A02 : fusion d'un export ──────────────────────

def _export_valide(db) -> dict:
    from comptesbudget.sync import db_snapshot
    return db_snapshot(db)


def test_un_export_valide_est_accepte(base):
    from comptesbudget.sync import verifier_export
    assert verifier_export(_export_valide(base)) is None


def test_un_ancien_export_reste_accepte(base):
    """Les exports d'avant le nom « Pécule » portaient « comptes_budget.py »."""
    from comptesbudget.sync import verifier_export
    ancien = _export_valide(base)
    ancien["app"] = "comptes_budget.py"
    ancien.pop("comptes")
    assert verifier_export(ancien) is None


@pytest.mark.parametrize("abime", [
    ["une", "liste"],                                   # racine non objet
    {"transactions": []},                               # sans marque ni version
    {"version": 3, "app": "autre-logiciel", "transactions": []},
    {"version": 3, "app": "pecule.py", "comptes": [{"id": "c1"}, "texte"]},
    {"version": 3, "app": "pecule.py", "transactions": "pas une liste"},
    {"version": 3, "app": "pecule.py", "transactions": [{"montant": 1}]},
])
def test_un_fichier_abime_est_refuse(abime):
    from comptesbudget.sync import verifier_export
    assert verifier_export(abime)


def test_la_fusion_est_tout_ou_rien(base, monkeypatch):
    """Une erreur au milieu de la fusion n'en laisse rien dans la base."""
    from comptesbudget import sync
    autre = Database(str(Path(base.path).with_name("autre.db")))
    autre.set_setting("initial_date", "2026-01-01")
    autre.set_setting("initial_balance", "100.0")
    for i in range(3):
        autre.insert_tx(_op(id=f"n{i}", libelle_op=f"NOUVELLE {i}"))
    donnees = sync.db_snapshot(autre)
    appels = []
    vrai = base.upsert_synced

    def casse_au_deuxieme(entity, rec):
        appels.append(rec.get("id"))
        if len(appels) == 2:
            raise RuntimeError("panne simulée")
        return vrai(entity, rec)
    monkeypatch.setattr(base, "upsert_synced", casse_au_deuxieme)
    comptes_avant = len(base.list_comptes())
    with pytest.raises(RuntimeError):
        sync.merge_remote_into_db(base, donnees)
    # Une écriture ordinaire juste après (comme l'appli en fait sans cesse)
    # ne doit pas rendre définitif un morceau de la fusion ratée.
    base.set_setting("_essai", "1")
    relue = sqlite3.connect(base.path)
    try:
        ids = [r[0] for r in relue.execute("SELECT id FROM transactions")]
        comptes = relue.execute("SELECT count(*) FROM comptes").fetchone()[0]
    finally:
        relue.close()
    assert ids == ["a"]
    assert comptes == comptes_avant


def test_fusion_d_un_fichier_abime_ne_touche_a_rien(qapp, base, tmp_path,
                                                     monkeypatch):
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    from comptesbudget.ui import main_window
    from comptesbudget.ui.main_window import MainWindow
    fenetre = MainWindow(base)
    # Pire cas : l'utilisateur confirme la fusion.
    monkeypatch.setattr(main_window, "confirmer", lambda *a, **k: True)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    fichier = tmp_path / "abime.json"
    valide = _export_valide(base)
    valide["comptes"].append("texte")
    fichier.write_text(json.dumps(valide), encoding="utf-8")
    avant = _empreinte(base.path)
    messages = []
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        lambda *a, **k: (str(fichier), ""))
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda parent, titre, texte, *a: messages.append(texte))
    fenetre.action_import_json()
    assert messages
    assert _empreinte(base.path) == avant


# ─────────────────────────── A07, A08, R01 : fabrication ───────────────────

def test_la_construction_n_efface_plus_une_base():
    texte = (RACINE / "Construire-Exe.bat").read_text(encoding="utf-8",
                                                      errors="replace")
    for ligne in texte.splitlines():
        assert not ("del " in ligne.lower() and "comptes.db" in ligne.lower()), ligne


def _faire_archive():
    spec = importlib.util.spec_from_file_location(
        "faire_archive", RACINE / "outils" / "faire_archive.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_l_archive_s_arrete_sur_une_base_meme_vide(tmp_path):
    outil = _faire_archive()
    base = tmp_path / "comptes.db"
    conn = sqlite3.connect(base)
    conn.execute("CREATE TABLE transactions (id TEXT)")
    conn.commit()
    conn.close()
    with pytest.raises(SystemExit):
        outil.verifier_absence_de_donnees(str(tmp_path))
    assert base.exists()            # rien n'est effacé


def _faux_dossier(racine: Path):
    (racine / "_internal" / "PySide6" / "translations").mkdir(parents=True)
    for nom in ("Pecule.exe", "Lisez-moi.txt", "Budget.ico",
                "_internal/python3.dll", "_internal/base_library.zip",
                "_internal/select.pyd", "_internal/Budget.ico",
                "_internal/PySide6/translations/qtbase_fr.qm"):
        (racine / nom).write_bytes(b"x")


def test_l_archive_accepte_les_fichiers_du_programme(tmp_path):
    outil = _faire_archive()
    _faux_dossier(tmp_path)
    outil.verifier_contenu(str(tmp_path))


@pytest.mark.parametrize("intrus", ["releve-fictif.csv", "export.json",
                                    "_internal/vieux.qif", "notes.pdf",
                                    "comptes.db-wal"])
def test_l_archive_refuse_un_fichier_inattendu(tmp_path, intrus):
    outil = _faire_archive()
    _faux_dossier(tmp_path)
    (tmp_path / intrus).write_bytes(b"x")
    with pytest.raises(SystemExit) as erreur:
        outil.verifier_contenu(str(tmp_path))
    assert Path(intrus).name in str(erreur.value)
