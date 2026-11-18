#ifndef PackageDir
  #error Pass /DPackageDir with the full path to the extracted Windows package.
#endif
#ifndef OutputDir
  #error Pass /DOutputDir with the installer output directory.
#endif
#ifndef AppVersion
  #error Pass /DAppVersion with the version number, for example 1.2.1.
#endif

[Setup]
AppId={{6DD0DA4A-DC89-40F9-B40E-4AB9289A6A8B}
AppName=Traffic Light Camera
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\TrafficLightCamera
DisableProgramGroupPage=yes
UninstallDisplayName=Traffic Light Camera
PrivilegesRequired=lowest
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
OutputDir={#OutputDir}
OutputBaseFilename=TrafficLight-Camera-windows-x64-setup
Compression=lzma2
SolidCompression=yes

[Files]
Source: "{#PackageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Traffic Light Camera"; Filename: "{app}\Start.cmd"; WorkingDir: "{app}"

[Run]
Filename: "{app}\Start.cmd"; Description: "Launch Traffic Light Camera"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent unchecked
