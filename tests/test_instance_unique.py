"""Une seule fenêtre à la fois sur une même base de données."""
import os

from comptesbudget.app import verrouiller_instance


def test_deuxieme_lancement_refuse(tmp_path):
    """Deux fenêtres ouvertes sur la même base se marchent dessus : la
    dernière écriture gagne, et un import peut échouer sur « database is
    locked ». Le second lancement doit donc être écarté."""
    dossier = str(tmp_path)
    premier = verrouiller_instance(dossier)
    assert premier is not None
    assert os.path.exists(os.path.join(dossier, "pecule.lock"))

    second = verrouiller_instance(dossier)
    assert second is None

    # Le verrou libéré, un nouveau lancement redevient possible.
    premier.unlock()
    troisieme = verrouiller_instance(dossier)
    assert troisieme is not None
    troisieme.unlock()


def test_verrou_repris_si_le_fichier_est_ancien_et_orphelin(tmp_path):
    """Un `pecule.lock` copié avec le dossier (mise à jour, clé USB, dossier
    synchronisé) ne doit pas condamner l'application : Qt reprend un verrou
    qu'il juge périmé. Mais tant que le processus qui le tient est vivant,
    l'âge du fichier ne change rien — c'est le numéro de processus qui
    tranche."""
    import time

    from PySide6.QtCore import QLockFile

    chemin = str(tmp_path / "pecule.lock")
    tenu = QLockFile(chemin)
    tenu.setStaleLockTime(500)          # 0,5 s, pour ne pas allonger les tests
    assert tenu.tryLock(200)
    time.sleep(0.8)                     # le fichier est maintenant « vieux »

    concurrent = QLockFile(chemin)
    concurrent.setStaleLockTime(500)
    assert not concurrent.tryLock(100), (
        "le verrou d'un processus vivant a été volé à cause de son âge")
    tenu.unlock()
