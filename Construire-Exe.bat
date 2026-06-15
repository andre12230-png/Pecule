@echo off
rem ==========================================================================
rem  Construit un executable autonome de l'application
rem  Resultat : dist\Comptes-Budget\ (dossier autonome --onedir, demarrage rapide)
rem ==========================================================================

setlocal
cd /d "%~dp0"

set PYTHON=D:\Python\Python313\python.exe
if not exist "%PYTHON%" set PYTHON=python

echo.
echo === 1/3 : Installation de PyInstaller (si necessaire) ===
"%PYTHON%" -m pip install --quiet --upgrade pyinstaller pyside6
if errorlevel 1 (
    echo ERREUR : impossible d'installer PyInstaller.
    pause
    exit /b 1
)

echo.
echo === 2/3 : Construction de l'executable ===
"%PYTHON%" -m PyInstaller ^
    --noconfirm ^
    --onedir ^
    --windowed ^
    --name "Comptes-Budget" ^
    --icon "%~dp0Budget.ico" ^
    --add-data "%~dp0Budget.ico;." ^
    --distpath "%~dp0dist" ^
    --workpath "%~dp0build" ^
    --specpath "%~dp0build" ^
    comptes_budget.py
if errorlevel 1 (
    echo ERREUR : la construction a echoue.
    pause
    exit /b 1
)

echo.
echo === 3/3 : Termine ===
echo Application creee : %~dp0dist\Comptes-Budget\Comptes-Budget.exe
echo (la base comptes.db sera creee a cote du .exe, dans ce dossier)
echo.
echo Vous pouvez :
echo   - Double-cliquer sur Comptes-Budget.exe pour lancer l'application
echo   - Copier TOUT le dossier Comptes-Budget\ ou vous voulez (il est autonome)
echo   - Creer un raccourci vers le .exe (clic droit ^> Envoyer vers ^> Bureau)
echo.
pause
