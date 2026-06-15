@echo off
rem ==========================================================================
rem  Construit un executable autonome de l'application
rem  Resultat : dist\Comptes-Budget.exe (~100 Mo, demarre en double-clic)
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
    --onefile ^
    --windowed ^
    --name "Comptes-Budget" ^
    --icon "%~dp0Budget.ico" ^
    --add-data "%~dp0Budget.ico;." ^
    --distpath "%~dp0." ^
    --workpath "%~dp0build" ^
    --specpath "%~dp0build" ^
    --collect-submodules PySide6 ^
    comptes_budget.py
if errorlevel 1 (
    echo ERREUR : la construction a echoue.
    pause
    exit /b 1
)

echo.
echo === 3/3 : Termine ===
echo Executable cree : %~dp0Comptes-Budget.exe
echo (il est dans le meme dossier que comptes.db, tout fonctionne directement)
echo.
echo Vous pouvez :
echo   - Double-cliquer dessus pour lancer l'application
echo   - Le copier ou vous voulez (il est autonome)
echo   - Creer un raccourci bureau (clic droit ^> Envoyer vers ^> Bureau)
echo.
pause
