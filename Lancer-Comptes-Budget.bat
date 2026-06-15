@echo off
rem ==========================================================================
rem  Lance Comptes et Budget (application Python PySide6)
rem
rem  Mode d'emploi :
rem  1. Placez ce fichier dans le MEME dossier que comptes_budget.py
rem  2. Double-cliquez dessus pour lancer
rem  3. Pour creer un raccourci bureau : clic droit > Envoyer vers > Bureau
rem ==========================================================================

setlocal

rem Chemin Python par defaut (modifiez si necessaire)
set PYTHONW=D:\Python\Python313\pythonw.exe
set PYTHON=D:\Python\Python313\python.exe

rem On utilise pythonw.exe : pas de fenetre console noire en arriere-plan
if exist "%PYTHONW%" (
    start "" "%PYTHONW%" "%~dp0comptes_budget.py"
    exit /b
)

rem Sinon, fallback : Python du PATH
where pythonw >nul 2>&1
if %ERRORLEVEL%==0 (
    start "" pythonw "%~dp0comptes_budget.py"
    exit /b
)

rem En dernier recours : python.exe (avec console visible)
echo pythonw.exe introuvable, lancement avec console...
"%PYTHON%" "%~dp0comptes_budget.py"
pause
