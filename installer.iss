; Windows installer for the `flet pack --onedir` output (dist\Teyvault).
; Built by .github/workflows/release.yml: iscc /DVersion=x.y.z installer.iss
; Per-user install, so no admin prompt. Wish data and cookies live in %APPDATA% / the keyring
; and survive uninstall/upgrade.

#ifndef Version
  #define Version "0.0.0"
#endif
#define Exe "Teyvault.exe"

[Setup]
; Never change AppId: upgrades find the old install through it.
AppId={{0EFDA593-AF5A-47EA-855F-C92D732A70F9}
AppName=Teyvault
AppVersion={#Version}
AppPublisher=Shaiyon69
AppPublisherURL=https://github.com/Shaiyon69/teyvault
DefaultDirName={autopf}\Teyvault
DefaultGroupName=Teyvault
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=Teyvault-Setup
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#Exe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\Teyvault\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Teyvault"; Filename: "{app}\{#Exe}"
Name: "{autodesktop}\Teyvault"; Filename: "{app}\{#Exe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#Exe}"; Description: "{cm:LaunchProgram,Teyvault}"; Flags: nowait postinstall skipifsilent
