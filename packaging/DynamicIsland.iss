; Inno Setup script for Dynamic Island. Built by build.ps1 / GitHub Actions.
; Installs per-user (no admin prompt) into %LOCALAPPDATA%\Programs\Dynamic Island.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6E3C2B8A-5D1F-4C2E-9B7A-DA1A5E1A9D01}
AppName=Dynamic Island
AppVersion={#AppVersion}
AppVerName=Dynamic Island {#AppVersion}
AppPublisher=Quosai Alqreini
AppPublisherURL=https://github.com/QuosaiAlqreini/DynamicIsland
AppSupportURL=https://github.com/QuosaiAlqreini/DynamicIsland/issues
DefaultDirName={autopf}\Dynamic Island
DefaultGroupName=Dynamic Island
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\installer_output
OutputBaseFilename=DynamicIsland-{#AppVersion}-Setup
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\DynamicIsland.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "autostart"; Description: "Start Dynamic Island when I sign in to Windows"; GroupDescription: "Startup:"

[Files]
Source: "..\dist\DynamicIsland\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Dynamic Island"; Filename: "{app}\DynamicIsland.exe"
Name: "{group}\Uninstall Dynamic Island"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Dynamic Island"; Filename: "{app}\DynamicIsland.exe"; Tasks: desktopicon

[Registry]
; Same value the in-app "Start with Windows" switch uses, so the two stay in sync
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "DynamicIsland"; ValueData: """{app}\DynamicIsland.exe"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\DynamicIsland.exe"; Description: "Launch Dynamic Island now"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /IM DynamicIsland.exe /F"; Flags: runhidden; RunOnceId: "KillApp"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
