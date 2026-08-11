"""Fabrique le fichier d'informations de version de l'exécutable Windows.

Sans lui, PyInstaller produit un .exe dont tous les champs d'identité sont
vides : Windows affiche alors « Éditeur inconnu » et rien d'utile dans le
panneau « Informations complémentaires » de l'avertissement SmartScreen.
Ce n'est pas une signature numérique et ça ne fait pas disparaître
l'avertissement — mais l'utilisateur qui clique voit enfin le nom du logiciel
et sa version au lieu du néant.

Le fichier est régénéré à chaque construction à partir d'APP_VERSION : il ne
peut donc pas se désynchroniser de la version publiée.

Lancement (fait automatiquement par Construire-Exe.bat) :

    python outils/version_exe.py [fichier_de_sortie]
"""
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from comptesbudget.constants import APP_VERSION      # noqa: E402

# Windows attend quatre nombres ; APP_VERSION en donne trois (1.22.1).
_parts = [int(p) for p in APP_VERSION.split(".")]
while len(_parts) < 4:
    _parts.append(0)
QUADRUPLET = tuple(_parts[:4])

# 0x040C = français (France) ; 1200 = jeu de caractères Unicode.
# La chaîne « 040C04B0 » est la même paire écrite en hexadécimal.
MODELE = '''# Généré par outils/version_exe.py — ne pas modifier à la main.
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={quad},
    prodvers={quad},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040C04B0',
        [StringStruct('CompanyName', 'andre12230-png'),
         StringStruct('FileDescription', 'Pécule — comptes et budget personnels'),
         StringStruct('FileVersion', '{version}'),
         StringStruct('InternalName', 'Pecule'),
         StringStruct('LegalCopyright', '© 2026 andre12230-png — licence MIT'),
         StringStruct('OriginalFilename', 'Pecule.exe'),
         StringStruct('ProductName', 'Pécule'),
         StringStruct('ProductVersion', '{version}')])
    ]),
    VarFileInfo([VarStruct('Translation', [0x040C, 1200])])
  ]
)
'''


def main():
    dest = sys.argv[1] if len(sys.argv) > 1 else os.path.join(RACINE, "build", "version-exe.txt")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    contenu = MODELE.format(quad=QUADRUPLET, version=APP_VERSION)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(contenu)
    print("Informations de version ecrites : %s" % dest)
    print("  ProductName    : Pecule")
    print("  ProductVersion : %s" % APP_VERSION)


if __name__ == "__main__":
    main()
