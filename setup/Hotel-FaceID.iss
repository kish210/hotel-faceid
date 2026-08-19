; Hotel Face-ID installer script
; Requires Inno Setup 6.3+

#define MyAppName "Hotel Face-ID"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "Hotel Face-ID"
#define MyAppExeName "start-install.ps1"
#define Root "D:\code\ocr"

[Setup]
AppId={{7F3C2D18-5E1A-4B6F-9C21-4D3E8A2B6F11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName=C:\HotelFaceID
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#Root}\setup\dist
OutputBaseFilename=Hotel-FaceID-Setup-{#MyAppVersion}
SetupIconFile={#Root}\setup\app.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\app.ico
CloseApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startup"; Description: "افزودن راه‌اندازی به منوی استارت"; GroupDescription: "مختصات اضافه:"; Flags: unchecked

[Files]
; ---- source of every service (kept on disk for debugging) ----
Source: "{#Root}\.env.example"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Root}\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Root}\todo.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Root}\db\init\*"; DestDir: "{app}\db\init"; Flags: ignoreversion recursesubdirs
Source: "{#Root}\setup\VERSION"; DestDir: "{app}"; Flags: ignoreversion

; ---- api ----
Source: "{#Root}\services\api\requirements.txt"; DestDir: "{app}\services\api"; Flags: ignoreversion
Source: "{#Root}\services\api\app\*.py"; DestDir: "{app}\services\api\app"; Flags: ignoreversion
Source: "{#Root}\services\api\app\routers\*.py"; DestDir: "{app}\services\api\app\routers"; Flags: ignoreversion
Source: "{#Root}\services\api\app\services\*.py"; DestDir: "{app}\services\api\app\services"; Flags: ignoreversion
Source: "{#Root}\services\api\fonts\*"; DestDir: "{app}\services\api\fonts"; Flags: ignoreversion

; ---- face-service ----
Source: "{#Root}\services\face-service\requirements.txt"; DestDir: "{app}\services\face-service"; Flags: ignoreversion
Source: "{#Root}\services\face-service\app\*.py"; DestDir: "{app}\services\face-service\app"; Flags: ignoreversion
Source: "{#Root}\services\face-service\app\cameras\*.py"; DestDir: "{app}\services\face-service\app\cameras"; Flags: ignoreversion
Source: "{#Root}\services\face-service\tests\*.py"; DestDir: "{app}\services\face-service\tests"; Flags: ignoreversion

; ---- web: the built panel, served by the API itself ----
; Shipping dist\ is what frees the target machine from needing Node.js.
Source: "{#Root}\web\dist\*"; DestDir: "{app}\web\dist"; Flags: ignoreversion recursesubdirs

; ---- web sources (kept on disk so the panel can be rebuilt/debugged) ----
Source: "{#Root}\web\package.json"; DestDir: "{app}\web"; Flags: ignoreversion
Source: "{#Root}\web\package-lock.json"; DestDir: "{app}\web"; Flags: ignoreversion
Source: "{#Root}\web\vite.config.js"; DestDir: "{app}\web"; Flags: ignoreversion
Source: "{#Root}\web\jsconfig.json"; DestDir: "{app}\web"; Flags: ignoreversion
Source: "{#Root}\web\components.json"; DestDir: "{app}\web"; Flags: ignoreversion
Source: "{#Root}\web\index.html"; DestDir: "{app}\web"; Flags: ignoreversion
Source: "{#Root}\web\public\fonts\*"; DestDir: "{app}\web\public\fonts"; Flags: ignoreversion
Source: "{#Root}\web\src\*.jsx"; DestDir: "{app}\web\src"; Flags: ignoreversion
Source: "{#Root}\web\src\api.js"; DestDir: "{app}\web\src"; Flags: ignoreversion
Source: "{#Root}\web\src\format.js"; DestDir: "{app}\web\src"; Flags: ignoreversion
Source: "{#Root}\web\src\globals.css"; DestDir: "{app}\web\src"; Flags: ignoreversion
Source: "{#Root}\web\src\lib\*.js"; DestDir: "{app}\web\src\lib"; Flags: ignoreversion
Source: "{#Root}\web\src\components\*.jsx"; DestDir: "{app}\web\src\components"; Flags: ignoreversion
Source: "{#Root}\web\src\components\ui\*.jsx"; DestDir: "{app}\web\src\components\ui"; Flags: ignoreversion
Source: "{#Root}\web\src\pages\*.jsx"; DestDir: "{app}\web\src\pages"; Flags: ignoreversion

; ---- installer scripts + icon ----
Source: "{#Root}\setup\scripts\*.ps1"; DestDir: "{app}\scripts"; Flags: ignoreversion
Source: "{#Root}\setup\scripts\*.cmd"; DestDir: "{app}\scripts"; Flags: ignoreversion
Source: "{#Root}\setup\README.md"; DestDir: "{app}\scripts"; DestName: "README-install.md"; Flags: ignoreversion
Source: "{#Root}\setup\app.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}\راه‌اندازی (Start)"; Filename: "{app}\scripts\run-install.cmd"; WorkingDir: "{app}"; IconFilename: "{app}\app.ico"
Name: "{autoprograms}\{#MyAppName}\شروع (Start)"; Filename: "{app}\scripts\run-start.cmd"; WorkingDir: "{app}"; IconFilename: "{app}\app.ico"
Name: "{autoprograms}\{#MyAppName}\توقف (Stop)"; Filename: "{app}\scripts\run-stop.cmd"; WorkingDir: "{app}"; IconFilename: "{app}\app.ico"
Name: "{autoprograms}\{#MyAppName}\وضعیت (Status)"; Filename: "{app}\scripts\run-status.cmd"; WorkingDir: "{app}"; IconFilename: "{app}\app.ico"
Name: "{autoprograms}\{#MyAppName}\لاگ‌ها (Logs)"; Filename: "{app}\scripts\run-logs.cmd"; WorkingDir: "{app}"; IconFilename: "{app}\app.ico"
Name: "{autoprograms}\{#MyAppName}\مستندات"; Filename: "{app}\scripts\README-install.md"
Name: "{commondesktop}\{#MyAppName} راه‌اندازی"; Filename: "{app}\scripts\run-install.cmd"; WorkingDir: "{app}"; IconFilename: "{app}\app.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\scripts\run-install.cmd"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent; Description: "راه‌اندازی سامانه پس از نصب"

[Code]
function PythonInstalled(): Boolean;
var
  path: String;
begin
  // `py.exe` ships with every python.org installer; the PATH entry is the
  // fallback for installs that skipped the launcher.
  Result := FileExists(ExpandConstant('{sys}\py.exe')) or
            RegQueryStringValue(HKCU32, 'Software\Python\PythonCore\3.11\InstallPath', '', path) or
            RegQueryStringValue(HKLM32, 'Software\Python\PythonCore\3.11\InstallPath', '', path) or
            RegQueryStringValue(HKLM64, 'Software\Python\PythonCore\3.11\InstallPath', '', path);
end;

function InitializeSetup(): Boolean;
begin
  if not PythonInstalled() then
    Result := MsgBox('Python 3.11 یافت نشد. برای اجرای سامانه لازم است (هنگام نصب گزینهٔ Add python.exe to PATH را تیک بزنید). نصب را ادامه می‌دهید؟', mbConfirmation, MB_YESNO) = IDYES
  else
    Result := True;
end;

