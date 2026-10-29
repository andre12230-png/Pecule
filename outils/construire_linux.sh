#!/usr/bin/env bash
# ==========================================================================
#  Construit la version Linux de Pécule : un fichier AppImage.
#
#  Préparation du 29/10/2026 : cette version n'est PAS publiée. Le fichier
#  produit reste sur le PC, dans dist-linux/.
#
#  À lancer DANS WSL (Ubuntu), pas dans Windows :
#      bash /mnt/f/Projets/Comptes-Budget/outils/construire_linux.sh
#
#  Ce que fait le script, dans l'ordre :
#    1. installe les paquets Ubuntu dont Qt a besoin (demande le mot de
#       passe d'Ubuntu, une seule fois) ;
#    2. copie le code dans un dossier Linux (~/pecule-linux) : construire
#       directement sur F: depuis WSL est très lent ;
#    3. crée un environnement Python à part et y installe PySide6,
#       PyInstaller et pytest ;
#    4. lance tous les tests : s'il y en a un qui échoue, on s'arrête ;
#    5. construit le programme avec PyInstaller (même réglage que
#       Construire-Exe.bat : un dossier autonome, sans console) ;
#    6. l'emballe en un seul fichier AppImage avec appimagetool
#       (téléchargé une fois depuis le dépôt officiel AppImage sur GitHub) ;
#    7. recopie le résultat dans F:\Projets\Comptes-Budget\dist-linux\.
#
#  Rien ne touche aux données : la version Linux range les siennes dans
#  ~/.local/share/Pecule, à l'intérieur de WSL.
# ==========================================================================
set -euo pipefail

# Dossier du projet vu depuis WSL (le script est dans outils/).
PROJET="$(cd "$(dirname "$0")/.." && pwd)"
TRAVAIL="$HOME/pecule-linux"
OUTILS="$HOME/.cache/pecule-outils"
SORTIE="$PROJET/dist-linux"

# Numéro de version lu dans le code : une seule source, constants.py.
VERSION="$(grep -m1 '^APP_VERSION' "$PROJET/comptesbudget/constants.py" \
           | sed -E 's/.*"([^"]+)".*/\1/')"
echo "=== Pécule $VERSION pour Linux ==="

echo
echo "=== 1/7 : Paquets Ubuntu ==="
# python3-venv : environnement Python à part.  Les bibliothèques lib* sont
# celles que Qt réclame pour ouvrir une fenêtre.  fonts-noto-color-emoji :
# les pictogrammes du menu (💾, 🔄, 💬).  file : utilisé par appimagetool.
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python3-venv python3-pip rsync file wget \
    libegl1 libgl1 libxkbcommon-x11-0 libxcb-cursor0 libxcb-icccm4 \
    libxcb-keysyms1 libxcb-shape0 libxcb-xinerama0 libxcb-randr0 \
    libxcb-render-util0 libxcb-image0 libfontconfig1 libdbus-1-3 \
    fonts-noto-color-emoji

echo
echo "=== 2/7 : Copie du code dans $TRAVAIL ==="
# Ni l'historique git, ni les constructions Windows, ni aucune base de
# comptes : seulement le code et ce qui est livré avec lui.
mkdir -p "$TRAVAIL"
rsync -a --delete \
    --exclude '.git/' --exclude 'build/' --exclude 'dist/' \
    --exclude 'dist-linux/' --exclude '__pycache__/' --exclude '.venv/' \
    --exclude '*.db' --exclude '*.db-*' --exclude 'sauvegardes/' \
    "$PROJET/" "$TRAVAIL/src/"

echo
echo "=== 3/7 : Environnement Python ==="
if [ ! -d "$TRAVAIL/venv" ]; then
    python3 -m venv "$TRAVAIL/venv"
fi
PY="$TRAVAIL/venv/bin/python"
"$PY" -m pip install --quiet --upgrade pip
"$PY" -m pip install --quiet -r "$TRAVAIL/src/requirements-dev.txt"
"$PY" -c "import PySide6, PyInstaller, sys; print('Python      :', sys.version.split()[0]); print('PySide6     :', PySide6.__version__); print('PyInstaller :', PyInstaller.__version__)"

echo
echo "=== 4/7 : Tests ==="
# QT_QPA_PLATFORM=offscreen : les tests d'écran tournent sans ouvrir de
# fenêtre.
( cd "$TRAVAIL/src" && QT_QPA_PLATFORM=offscreen "$PY" -m pytest -q )

echo
echo "=== 5/7 : Construction du programme ==="
cd "$TRAVAIL"
rm -rf build dist
# Sous Linux, --add-data sépare la source et la destination par « : »
# (et non « ; » comme sous Windows).
"$PY" -m PyInstaller \
    --noconfirm \
    --onedir \
    --windowed \
    --name "Pecule" \
    --add-data "src/Budget.ico:." \
    --distpath "$TRAVAIL/dist" \
    --workpath "$TRAVAIL/build" \
    --specpath "$TRAVAIL/build" \
    "src/pecule.py"
if [ ! -x "$TRAVAIL/dist/Pecule/Pecule" ]; then
    echo "ERREUR : le programme n'a pas été produit."
    exit 1
fi
# L'appli cherche son icône à côté du programme (_app_dir) : on l'y met.
cp "$TRAVAIL/src/Budget.ico" "$TRAVAIL/dist/Pecule/Budget.ico"

echo
echo "=== 6/7 : Emballage en AppImage ==="
APPDIR="$TRAVAIL/Pecule.AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/lib"
cp -a "$TRAVAIL/dist/Pecule" "$APPDIR/usr/lib/Pecule"

# Icône en PNG (une AppImage n'accepte pas le .ico), tirée de Budget.ico
# par Qt lui-même.
QT_QPA_PLATFORM=offscreen "$PY" - "$TRAVAIL/src/Budget.ico" "$APPDIR/pecule.png" <<'FIN_PY'
import sys
from PySide6.QtGui import QGuiApplication, QIcon
app = QGuiApplication([])
pixmap = QIcon(sys.argv[1]).pixmap(256, 256)
if pixmap.isNull() or not pixmap.save(sys.argv[2], "PNG"):
    sys.exit("ERREUR : icône PNG impossible à produire.")
FIN_PY

# Fiche qui présente l'appli au bureau Linux (menu, nom, icône).
cat > "$APPDIR/pecule.desktop" <<FIN_DESKTOP
[Desktop Entry]
Type=Application
Name=Pécule
Comment=Comptes et budget personnels, 100 % hors ligne
Exec=Pecule
Icon=pecule
Categories=Office;Finance;
Terminal=false
X-AppImage-Version=$VERSION
FIN_DESKTOP

# Point d'entrée de l'AppImage : lance le programme construit.
cat > "$APPDIR/AppRun" <<'FIN_APPRUN'
#!/bin/sh
ICI="$(dirname "$(readlink -f "$0")")"
exec "$ICI/usr/lib/Pecule/Pecule" "$@"
FIN_APPRUN
chmod +x "$APPDIR/AppRun"

# appimagetool : l'outil officiel qui fabrique le fichier AppImage.
mkdir -p "$OUTILS"
OUTIL="$OUTILS/appimagetool-x86_64.AppImage"
if [ ! -x "$OUTIL" ]; then
    wget -q -O "$OUTIL" \
        "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x "$OUTIL"
fi
# --appimage-extract-and-run : évite d'avoir à installer FUSE dans WSL.
ARCH=x86_64 "$OUTIL" --appimage-extract-and-run --no-appstream \
    "$APPDIR" "$TRAVAIL/Pecule-x86_64.AppImage"

echo
echo "=== 7/7 : Recopie dans dist-linux ==="
mkdir -p "$SORTIE"
cp "$TRAVAIL/Pecule-x86_64.AppImage" "$SORTIE/Pecule-$VERSION-x86_64.AppImage"
ls -lh "$SORTIE/Pecule-$VERSION-x86_64.AppImage"

echo
echo "=========================================================================="
echo " Terminé (version NON publiée)."
echo "   Fichier : $SORTIE/Pecule-$VERSION-x86_64.AppImage"
echo "   Pour l'essayer dans WSL :"
echo "     \"$TRAVAIL/Pecule-x86_64.AppImage\" --appimage-extract-and-run"
echo "=========================================================================="
