; Build with Inno Setup after scripts/package.ps1. No compiler download or silent install.
[Setup]
AppId={{6D95266F-C27C-4854-BDC8-7BA7D9C8A043}
AppName=Laprak
AppVersion=0.1.0
DefaultDirName={localappdata}\Programs\Laprak
DefaultGroupName=Laprak
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\installer
OutputBaseFilename=Laprak-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "..\dist\Laprak\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Laprak"; Filename: "{app}\Laprak.exe"; Parameters: "--data-dir ""{localappdata}\Laprak"""; WorkingDir: "{app}"

[Run]
Filename: "{app}\Laprak.exe"; Parameters: "--data-dir ""{localappdata}\Laprak"""; Description: "Buka Laprak dan periksa compiler, template, serta AI"; Flags: postinstall nowait skipifsilent
