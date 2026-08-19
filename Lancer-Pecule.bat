@echo off
rem ==========================================================================
rem  Lance Pecule (application Python PySide6)
rem
rem  Mode d'emploi :
rem  1. Placez ce fichier dans le MEME dossier que pecule.py
rem  2. Double-cliquez dessus pour lancer
rem  3. Pour creer un raccourci bureau : clic droit > Envoyer vers > Bureau
rem ==========================================================================

setlocal

rem  On lance avec "pyw", le Python Launcher officiel de Windows (installe
rem  dans C:\Windows avec Python). Deux raisons :
rem   - c est cette installation-la qui a PySide6 sur ce PC ; "python" du
rem     PATH est une AUTRE installation, aux bibliotheques differentes ;
rem   - la version "w" du lanceur n ouvre pas de fenetre console noire
rem     derriere l application.
where pyw >nul 2>&1
if %ERRORLEVEL%==0 (
    start "" pyw "%~dp0pecule.py"
    exit /b
)

rem  Secours : "py" fait la meme chose, mais laisse une console ouverte.
where py >nul 2>&1
if %ERRORLEVEL%==0 (
    echo pyw.exe introuvable : lancement avec py, une console va rester ouverte.
    py "%~dp0pecule.py"
    pause
    exit /b
)

echo.
echo ERREUR : le Python Launcher ^(py.exe^) est introuvable.
echo Installez Python 3 depuis python.org en cochant
echo "Install launcher for all users".
echo.
pause
exit /b 1
