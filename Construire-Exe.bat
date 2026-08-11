@echo off
rem ==========================================================================
rem  Construit un executable autonome de l'application, puis (au choix) met
rem  a jour votre installation sans jamais toucher a vos donnees.
rem
rem  Resultat : dist\Pecule\ (dossier autonome --onedir)
rem
rem  IMPORTANT : ne recopiez JAMAIS le dossier dist\ entier par-dessus une
rem  installation existante. Si vous avez lance l'application depuis dist\,
rem  une comptes.db VIDE y a ete creee, et elle ecraserait vos operations.
rem  L'etape 4 de ce script fait la mise a jour correctement : elle ne copie
rem  que le programme (Pecule.exe et _internal\).
rem ==========================================================================

setlocal
cd /d "%~dp0"

rem --------------------------------------------------------------------------
rem  Dossier ou l'application est installee : celui qui contient VOTRE
rem  comptes.db. Modifiez cette ligne si vous deplacez l'application.
rem --------------------------------------------------------------------------
set "INSTALL_DIR=F:\budget-app\Pecule"

rem --------------------------------------------------------------------------
rem  Python utilise pour construire. On prend celui du systeme ; pour en
rem  imposer un autre, definissez la variable PYTHON avant de lancer ce
rem  script (exemple :  set PYTHON=D:\Python\Python313\python.exe ).
rem --------------------------------------------------------------------------
if not defined PYTHON set "PYTHON=python"
"%PYTHON%" --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERREUR : Python est introuvable ^(commande "%PYTHON%"^).
    echo Installez Python, ou definissez la variable PYTHON vers votre python.exe.
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('"%PYTHON%" --version') do set "PYVER=%%v"

rem --------------------------------------------------------------------------
echo.
echo === 1/4 : Verification des outils ===
echo Python : %PYVER%

rem  PySide6 n'est JAMAIS mis a jour automatiquement : une nouvelle version
rem  peut changer le comportement de l'interface. On verifie seulement qu'il
rem  est present. Pour le mettre a jour, faites-le volontairement a la main.
"%PYTHON%" -c "import PySide6" >nul 2>&1
if errorlevel 1 (
    echo PySide6 est absent : installation...
    "%PYTHON%" -m pip install --quiet PySide6
    if errorlevel 1 (
        echo ERREUR : impossible d'installer PySide6.
        pause
        exit /b 1
    )
)
"%PYTHON%" -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo PyInstaller est absent : installation...
    "%PYTHON%" -m pip install --quiet pyinstaller
    if errorlevel 1 (
        echo ERREUR : impossible d'installer PyInstaller.
        pause
        exit /b 1
    )
)
rem  Versions affichees par un appel direct : dans un for /f, cmd coupe la
rem  commande sur les guillemets internes ("python" -c "import ...").
"%PYTHON%" -c "import PySide6, PyInstaller; print('PySide6     :', PySide6.__version__); print('PyInstaller :', PyInstaller.__version__)"

rem --------------------------------------------------------------------------
echo.
echo === 2/4 : Construction de l'executable ===
rem  Informations d'identite du .exe (nom, version, copyright). Sans elles,
rem  Windows affiche << Editeur inconnu >> et un panneau vide dans
rem  l'avertissement SmartScreen. Regenerees a chaque fois depuis APP_VERSION.
"%PYTHON%" "%~dp0outils\version_exe.py" "%~dp0build\version-exe.txt"
if errorlevel 1 (
    echo ERREUR : impossible de generer les informations de version.
    pause
    exit /b 1
)
"%PYTHON%" -m PyInstaller ^
    --noconfirm ^
    --onedir ^
    --windowed ^
    --name "Pecule" ^
    --icon "%~dp0Budget.ico" ^
    --version-file "%~dp0build\version-exe.txt" ^
    --add-data "%~dp0Budget.ico;." ^
    --distpath "%~dp0dist" ^
    --workpath "%~dp0build" ^
    --specpath "%~dp0build" ^
    pecule.py
if errorlevel 1 (
    echo ERREUR : la construction a echoue.
    pause
    exit /b 1
)
if not exist "%~dp0dist\Pecule\Pecule.exe" (
    echo ERREUR : l'executable n'a pas ete produit.
    pause
    exit /b 1
)

rem --------------------------------------------------------------------------
echo.
echo === 3/4 : Nettoyage du dossier de construction ===
rem  Si l'executable a deja ete lance depuis dist\, il y a cree une base
rem  VIDE. On la supprime : ainsi le dossier dist\ ne contient que le
rem  programme, et une copie malencontreuse ne peut plus ecraser de donnees.
if exist "%~dp0dist\Pecule\comptes.db" (
    del /q "%~dp0dist\Pecule\comptes.db"
    echo Base de test supprimee de dist\ ^(elle etait vide^).
) else (
    echo Rien a nettoyer.
)

rem --------------------------------------------------------------------------
echo.
echo === 4/4 : Mise a jour de votre installation ===
if not exist "%INSTALL_DIR%\Pecule.exe" (
    echo Aucune installation trouvee dans :
    echo    %INSTALL_DIR%
    echo Etape ignoree. Pour une PREMIERE installation, copiez le dossier
    echo    %~dp0dist\Pecule\
    echo la ou vous voulez : il est autonome.
    goto :fin
)

echo Installation detectee : %INSTALL_DIR%
if exist "%INSTALL_DIR%\comptes.db" (
    for %%f in ("%INSTALL_DIR%\comptes.db") do echo Vos donnees : comptes.db ^(%%~zf octets^) - NE SERA PAS TOUCHEE.
)
echo Seront remplaces : Pecule.exe et le dossier _internal\
echo.

rem  L'application doit etre fermee, sinon la copie echoue a moitie.
tasklist /fi "imagename eq Pecule.exe" 2>nul | find /i "Pecule.exe" >nul
if not errorlevel 1 (
    echo ERREUR : l'application est en cours d'execution.
    echo Fermez-la, puis relancez ce script.
    pause
    exit /b 1
)

choice /c ON /n /m "Mettre a jour cette installation ? [O = oui, N = non] "
if errorlevel 2 (
    echo Mise a jour annulee. L'executable reste disponible dans dist\.
    goto :fin
)

echo.
echo Copie du programme...
copy /y "%~dp0dist\Pecule\Pecule.exe" "%INSTALL_DIR%\Pecule.exe" >nul
if errorlevel 1 (
    echo ERREUR : copie de l'executable impossible.
    pause
    exit /b 1
)
rem  /MIR ne s'applique qu'au sous-dossier _internal (uniquement du
rem  programme) : ni comptes.db ni sauvegardes\ ne sont concernes.
robocopy "%~dp0dist\Pecule\_internal" "%INSTALL_DIR%\_internal" /MIR /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (
    echo ERREUR : copie des bibliotheques impossible.
    pause
    exit /b 1
)
echo Mise a jour terminee.
if exist "%INSTALL_DIR%\comptes.db" (
    for %%f in ("%INSTALL_DIR%\comptes.db") do echo Verification : comptes.db toujours la ^(%%~zf octets^).
)

:fin
echo.
echo ==========================================================================
echo  Termine.
echo    Executable construit : %~dp0dist\Pecule\Pecule.exe
if exist "%INSTALL_DIR%\Pecule.exe" echo    Installation         : %INSTALL_DIR%\Pecule.exe
echo ==========================================================================
echo.
pause
