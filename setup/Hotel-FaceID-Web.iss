; Hotel Face-ID — small (download-on-install) package
;
; Carries the application only. The Python runtime and the recognition models
; are fetched by scripts\fetch-payload.ps1 on first run, in 64 MB parts that
; resume after a dropped connection.
;
; Use Hotel-FaceID-Setup (the full one) where the machine has no internet.
;
; Requires Inno Setup 6.3+

#define MyAppName "Hotel Face-ID"
#define MyAppVersion "1.4.0"
#define MyAppPublisher "Hotel Face-ID"
#define MyAppExeName "start-install.ps1"
#define Root "D:\code\ocr"
; Prebuilt Python runtime + InsightFace models, assembled by setup\build.ps1.
#define Payload Root + "\setup\payload"

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
OutputBaseFilename=Hotel-FaceID-Setup-Web-{#MyAppVersion}
SetupIconFile={#Root}\setup\app.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\app.ico
CloseApplications=no

[Messages]
WelcomeLabel2=این نسخه پس از نصب، اجزای لازم (موتور اجرا و مدل‌های تشخیص چهره، حدود ۴۸۰ مگابایت) را یک‌بار از اینترنت دریافت می‌کند.%n%nاگر این کامپیوتر اینترنت ندارد، به‌جای این فایل از نسخهٔ کامل استفاده کنید.

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "ساخت میان‌بر روی دسکتاپ"; GroupDescription: "میان‌برها:"
Name: "autostart"; Description: "اجرای خودکار سامانه هنگام روشن شدن ویندوز"; GroupDescription: "میان‌برها:"

[Files]
; ---- source of every service (kept on disk for debugging) ----
Source: "{#Root}\.env.example"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Root}\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Root}\todo.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Root}\db\init\*"; DestDir: "{app}\db\init"; Flags: ignoreversion recursesubdirs
Source: "{#Root}\setup\VERSION"; DestDir: "{app}"; Flags: ignoreversion
; The analytics module catalogue the panel reads, plus any pack shipped with it.
Source: "{#Root}\modules\*"; DestDir: "{app}\modules"; Flags: ignoreversion recursesubdirs createallsubdirs

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
Source: "{#Root}\services\face-service\app\analytics\*.py"; DestDir: "{app}\services\face-service\app\analytics"; Flags: ignoreversion
Source: "{#Root}\services\face-service\tests\*.py"; DestDir: "{app}\services\face-service\tests"; Flags: ignoreversion

; ---- no runtime, no models: they are downloaded on first run ----
; Carrying them makes a 400 MB file, which is both slow to hand round and,
; on a poor line, hard to download in one piece. scripts\fetch-payload.ps1
; pulls them in 64 MB parts instead, and resumes where it left off.
Source: "{#Root}\setup\payload-manifest.json"; DestDir: "{app}"; Flags: ignoreversion

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
; The everyday button: starts the system if it is not running and opens the panel.
Name: "{autoprograms}\{#MyAppName}\شروع سامانه"; Filename: "{app}\scripts\run-start.cmd"; WorkingDir: "{app}"; IconFilename: "{app}\app.ico"
Name: "{autoprograms}\{#MyAppName}\توقف سامانه"; Filename: "{app}\scripts\run-stop.cmd"; WorkingDir: "{app}"; IconFilename: "{app}\app.ico"
Name: "{autoprograms}\{#MyAppName}\وضعیت سامانه"; Filename: "{app}\scripts\run-status.cmd"; WorkingDir: "{app}"; IconFilename: "{app}\app.ico"
Name: "{autoprograms}\{#MyAppName}\گزارش خطا برای پشتیبانی"; Filename: "{app}\scripts\run-debug.cmd"; WorkingDir: "{app}"; IconFilename: "{app}\app.ico"
Name: "{autoprograms}\{#MyAppName}\راهنما"; Filename: "{app}\scripts\README-install.md"
; {autodesktop}, not {commondesktop}: Setup runs unelevated, and writing to the
; all-users desktop needs administrator rights — it fails with "access denied"
; at the very end of an otherwise successful installation.
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\scripts\run-start.cmd"; WorkingDir: "{app}"; IconFilename: "{app}\app.ico"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\scripts\run-start-quiet.cmd"; WorkingDir: "{app}"; IconFilename: "{app}\app.ico"; Tasks: autostart

[Run]
Filename: "{app}\scripts\run-install.cmd"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent; Description: "راه‌اندازی و اجرای سامانه"

[UninstallDelete]
; Generated at runtime, so Setup does not know about them. Everything listed
; here was either installed by Setup or produced by running it — the guest
; database, face images and .env are deliberately left behind.
Type: filesandordirs; Name: "{app}\data\logs"
Type: filesandordirs; Name: "{app}\data\run"
Type: filesandordirs; Name: "{app}\runtime"
Type: filesandordirs; Name: "{app}\models"
Type: filesandordirs; Name: "{app}\services"
Type: filesandordirs; Name: "{app}\web"
Type: filesandordirs; Name: "{app}\scripts"
Type: filesandordirs; Name: "{app}\db"
Type: filesandordirs; Name: "{app}\debug"

[Code]
// Nothing to check before installing: Python, every package and the
// recognition models travel inside this package.

