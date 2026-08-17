; Hotel Face-ID — standalone installer
; Compile with Inno Setup 6:  ISCC.exe hotel-faceid.iss

#define MyAppName "Hotel Face-ID"
#define MyAppVersion "1.0.0"
#define MyAppExeWeb "start.bat"

[Setup]
AppId={{8D6E7A31-5C0E-4E9B-9F3A-HotelFaceID}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\Hotel FaceID
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\web\dist\favicon.ico
Compression=lzma2/ultra
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
OutputDir=installer
OutputBaseFilename=HotelFaceID-Setup
SetupIconFile=web\dist\favicon.ico
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "app\*"; DestDir: "{app}\app"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "faceservice\*"; DestDir: "{app}\faceservice"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "web\dist\*"; DestDir: "{app}\web\dist"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "fonts\*"; DestDir: "{app}\fonts"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "runtime\*"; DestDir: "{app}\runtime"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
Source: "models\*"; DestDir: "{app}\models"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: ".env"; DestDir: "{app}"; Flags: ignoreversion
Source: "start.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "stop.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "test-standalone.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "test-face.jpg"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeWeb}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeWeb}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeWeb}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent