; ==========================================================================
;  Recette de l'installeur Windows de Pécule (Inno Setup 6).
;
;  Ne pas compiler ce fichier directement : lancer
;      py outils/faire_installeur.py
;  qui vérifie le dossier construit, fournit le numéro de version et
;  produit dist\Pecule-Setup.exe.
;
;  Règle d'or : l'installeur ne livre QUE le programme. Les données
;  (comptes.db, sauvegardes\) vivent dans %LOCALAPPDATA%\Pecule — voir
;  _data_dir() dans comptesbudget/constants.py. Ni l'installation, ni la
;  mise à jour, ni la désinstallation n'y touchent.
; ==========================================================================

#ifndef AppVersion
  #error Lancer outils/faire_installeur.py : il fournit le numéro de version.
#endif

; Dossiers du projet, calculés depuis l'emplacement de ce fichier (outils\).
#define Racine AddBackslash(SourcePath) + "..\"
#define Construit Racine + "dist\Pecule"

[Setup]
; Identifiant permanent de l'application : c'est lui qui permet à une
; nouvelle version de reconnaître et de remplacer l'ancienne. NE JAMAIS LE
; CHANGER, sinon Windows verrait deux logiciels distincts.
AppId={{8C2F4E1A-6B3D-4F7A-9E25-3D1C7B9A5F40}
AppName=Pécule
AppVersion={#AppVersion}
AppVerName=Pécule {#AppVersion}
AppPublisher=andre12230-png
AppPublisherURL=https://andre12230-png.github.io/Pecule/
AppSupportURL=https://github.com/andre12230-png/Pecule/issues
AppUpdatesURL=https://github.com/andre12230-png/Pecule/releases/latest
AppCopyright=Licence MIT

; Installation pour l'utilisateur seul, sans mot de passe administrateur :
; dans %LOCALAPPDATA%\Programs\Pecule, comme beaucoup de logiciels récents.
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\Pecule
DefaultGroupName=Pécule
DisableProgramGroupPage=yes
; Une mise à jour réutilise le dossier déjà choisi, sans reposer la question.
UsePreviousAppDir=yes
DisableDirPage=auto

; Programme 64 bits uniquement.
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Pécule ne doit pas être fermé de force par l'installeur : il écrit sa
; sauvegarde du jour en se fermant. Si des fichiers sont occupés, Inno Setup
; demande simplement de fermer l'application puis de réessayer.
CloseApplications=no

OutputDir={#Racine}dist
; Nom SANS numéro de version : le site pointe vers
; .../releases/latest/download/Pecule-Setup.exe, qui mène ainsi toujours à
; la dernière version. Le numéro reste visible dans l'assistant, dans
; « Applications » et dans les propriétés du fichier.
OutputBaseFilename=Pecule-Setup
SetupIconFile={#Racine}Budget.ico
UninstallDisplayIcon={app}\Pecule.exe
UninstallDisplayName=Pécule
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes

; Informations affichées dans les propriétés du fichier Setup.exe.
VersionInfoVersion={#AppVersion}
VersionInfoProductName=Pécule
VersionInfoDescription=Installation de Pécule
VersionInfoCompany=andre12230-png

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "bureau"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"; Flags: unchecked

[InstallDelete]
; Mise à jour : on vide d'abord le moteur du programme, pour qu'aucune
; bibliothèque d'une ancienne version ne traîne. Seulement _internal :
; rien d'autre dans le dossier n'est effacé.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
; Le dossier construit par PyInstaller (Pecule.exe + _internal\), complété
; par Lisez-moi.txt et Budget.ico. Par sécurité, une base ou un verrou
; oubliés là ne sont JAMAIS livrés.
Source: "{#Construit}\*"; DestDir: "{app}"; Excludes: "comptes.db,pecule.lock,sauvegardes"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Racine}LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion

[Icons]
Name: "{group}\Pécule"; Filename: "{app}\Pecule.exe"; WorkingDir: "{app}"
Name: "{group}\Lisez-moi"; Filename: "{app}\Lisez-moi.txt"
Name: "{autodesktop}\Pécule"; Filename: "{app}\Pecule.exe"; WorkingDir: "{app}"; Tasks: bureau

[Run]
Filename: "{app}\Pecule.exe"; Description: "Lancer Pécule"; Flags: nowait postinstall skipifsilent

[Code]
{ Pécule ouvert pendant une mise à jour ou une désinstallation : ses fichiers
  sont occupés et le remplacement échouerait à moitié. On ne le ferme pas de
  force (il écrit sa sauvegarde du jour en se fermant) : on demande à
  l'utilisateur de le faire, et on s'arrête proprement s'il renonce. }

function PeculeEstOuvert(): Boolean;
var
  Wmi, Resultats: Variant;
begin
  Result := False;
  try
    Wmi := CreateOleObject('WbemScripting.SWbemLocator');
    Resultats := Wmi.ConnectServer('.', 'root\CIMV2').ExecQuery(
      'SELECT ProcessId FROM Win32_Process WHERE Name = ''Pecule.exe''');
    Result := Resultats.Count > 0;
  except
    { Si Windows ne sait pas répondre, on continue : au pire, Inno Setup
      signalera lui-même un fichier occupé. }
  end;
end;

function AttendreFermeture(): Boolean;
begin
  Result := True;
  while PeculeEstOuvert() do
    { En mode silencieux, la réponse par défaut est « Annuler » : pas de
      boucle sans fin. }
    if SuppressibleMsgBox('Pécule est ouvert.' + #13#10 + #13#10 +
        'Fermez-le (il enregistre sa sauvegarde du jour en se fermant), ' +
        'puis cliquez sur OK.', mbError, MB_OKCANCEL, IDCANCEL) = IDCANCEL then
    begin
      Result := False;
      Exit;
    end;
end;

function InitializeSetup(): Boolean;
begin
  Result := AttendreFermeture();
end;

function InitializeUninstall(): Boolean;
begin
  Result := AttendreFermeture();
end;
