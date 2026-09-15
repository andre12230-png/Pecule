"""Sauvegarde sur un support externe (clé USB, disque).

Ajout du 15/09/2026 : les sauvegardes automatiques restent sur le même
disque que la base, elles ne protègent donc pas d'une panne de ce disque.
"""
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from comptesbudget import sauvegarde_externe as se

QUAND = datetime(2026, 9, 15, 14, 30)


@pytest.fixture
def donnees(tmp_path):
    """Une base de données, et une « clé USB », toutes deux jetables."""
    dossier = tmp_path / "donnees"
    dossier.mkdir()
    base = dossier / "comptes.db"
    conn = sqlite3.connect(base)
    conn.execute("CREATE TABLE operations (id INTEGER PRIMARY KEY, libelle TEXT)")
    conn.executemany("INSERT INTO operations (libelle) VALUES (?)",
                     [("Loyer",), ("Courses",), ("Salaire",)])
    conn.commit()
    cle = tmp_path / "cle"
    cle.mkdir()
    yield dossier, base, conn, cle
    conn.close()


def _sauver_base(dossier, base, conn, cle, tmp_path):
    """Le chemin exact du bouton : copie cohérente, puis copie vérifiée."""
    (tmp_path / "instantane").mkdir(exist_ok=True)
    instant = se.instantane_sqlite(conn, tmp_path / "instantane" / base.name)
    return se.sauvegarder([instant], cle, dossier, "Pécule", "1.38.0", QUAND)


def test_la_base_ouverte_est_copiee_entiere(donnees, tmp_path):
    dossier, base, conn, cle = donnees
    cible, copies = _sauver_base(dossier, base, conn, cle, tmp_path)
    assert cible == cle / "Sauvegarde Pécule 2026-09-15 14h30"
    assert copies == ["comptes.db"]
    copie = sqlite3.connect(cible / "comptes.db")
    try:
        libelles = [r[0] for r in copie.execute(
            "SELECT libelle FROM operations ORDER BY id")]
    finally:
        copie.close()
    assert libelles == ["Loyer", "Courses", "Salaire"]


def test_la_base_d_origine_n_est_pas_touchee(donnees, tmp_path):
    dossier, base, conn, cle = donnees
    avant = base.read_bytes()
    _sauver_base(dossier, base, conn, cle, tmp_path)
    assert base.read_bytes() == avant
    # et elle reste utilisable par l'application
    conn.execute("INSERT INTO operations (libelle) VALUES ('Après')")
    conn.commit()


def test_un_mode_d_emploi_accompagne_la_copie(donnees, tmp_path):
    dossier, base, conn, cle = donnees
    cible, _ = _sauver_base(dossier, base, conn, cle, tmp_path)
    texte = (cible / "LISEZMOI.txt").read_text(encoding="utf-8")
    assert "Pécule 1.38.0" in texte
    assert "comptes.db" in texte
    assert "Fermez Pécule" in texte
    assert str(dossier) in texte


def test_deux_sauvegardes_dans_la_meme_minute(donnees, tmp_path):
    dossier, base, conn, cle = donnees
    premiere, _ = _sauver_base(dossier, base, conn, cle, tmp_path)
    seconde, _ = _sauver_base(dossier, base, conn, cle, tmp_path)
    assert premiere != seconde
    assert seconde.name.endswith("(2)")


def test_cle_retiree(donnees, tmp_path):
    dossier, base, _, _ = donnees
    with pytest.raises(se.SauvegardeImpossible, match="retirée"):
        se.sauvegarder([base], tmp_path / "cle-debranchee", dossier,
                       "Pécule", "1.38.0", QUAND)


def test_refuse_le_dossier_des_donnees(donnees):
    dossier, base, _, _ = donnees
    with pytest.raises(se.SauvegardeImpossible, match="clé USB"):
        se.sauvegarder([base], dossier, dossier, "Pécule", "1.38.0", QUAND)
    (dossier / "sauvegardes").mkdir()
    with pytest.raises(se.SauvegardeImpossible):
        se.sauvegarder([base], dossier / "sauvegardes", dossier,
                       "Pécule", "1.38.0", QUAND)


def test_rien_a_sauvegarder(donnees):
    dossier, _, _, cle = donnees
    with pytest.raises(se.SauvegardeImpossible, match="aucune donnée"):
        se.sauvegarder([dossier / "absent.db", None], cle, dossier,
                       "Pécule", "1.38.0", QUAND)


def test_une_copie_differente_est_denoncee(donnees, monkeypatch):
    """Une clé défectueuse qui abîme la copie ne doit pas passer pour une
    sauvegarde réussie."""
    dossier, base, _, cle = donnees

    def copie_abimee(source, dest):
        Path(dest).write_bytes(b"abime")
    monkeypatch.setattr(se.shutil, "copy2", copie_abimee)
    with pytest.raises(se.SauvegardeImpossible, match="ne correspond pas"):
        se.sauvegarder([base], cle, dossier, "Pécule", "1.38.0", QUAND)
