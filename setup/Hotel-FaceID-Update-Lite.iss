; Hotel Face-ID — small update package
;
; Carries only the application code, the built panel and the scripts. The
; Python runtime and the recognition models are already present on any machine
; that has the system installed, and pushing 700 MB down a hotel's connection
; to replace files that did not change helps nobody.
;
; Use Hotel-FaceID-Setup on a machine with no installation, or when the
; runtime itself needs replacing.
;
; What makes this an *update* rather than a reinstall is where it lands and
; what it leaves alone: it finds the existing folder, keeps data\ and .env,
; and hands over to scripts\update.ps1 for the migration.

#define MyAppName "Hotel Face-ID"
#define MyAppVersion "1.4.0"
#define MyAppPublisher "Hotel Face-ID"
#define Root "D:\code\ocr"
#define Payload Root + "\setup\payload"

[Setup]
; Same AppId as the full installer, so Windows treats this as the same product.
AppId={{7F3C2D18-5E1A-4B6F-9C21-4D3E8A2B6F11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
; Points at whatever installation is already on the machine. Inno lets /DIR=
; override this, which is what keeps unattended upgrades scriptable.
DefaultDirName={code:ExistingInstallation}
DisableProgramGroupPage=yes
DisableDirPage=no
PrivilegesRequired=lowest
OutputDir={#Root}\setup\dist
OutputBaseFilename=Hotel-FaceID-Update-Lite-{#MyAppVersion}
SetupIconFile={#Root}\setup\app.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\app.ico
; The services are stopped by update.ps1, which knows how to find them.
CloseApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
WelcomeLabel2=این بسته سامانهٔ نصب‌شده را به نسخهٔ {#MyAppVersion} به‌روز می‌کند.%n%nاطلاعات مهمانان، تصاویر و تنظیمات شما حفظ می‌شود و پیش از تغییر، از پایگاه داده نسخهٔ پشتیبان گرفته می‌شود.%n%nموتور اجرا و مدل‌های تشخیص چهره که از قبل روی این سیستم هستند دست‌نخورده می‌مانند.%n%nمسیر نصب فعلی را در صفحهٔ بعد تأیید کنید.

[Files]
; ---- application code ----
Source: "{#Root}\.env.example"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Root}\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Root}\todo.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Root}\db\init\*"; DestDir: "{app}\db\init"; Flags: ignoreversion recursesubdirs
Source: "{#Root}\setup\VERSION"; DestDir: "{app}"; Flags: ignoreversion
; The analytics module catalogue the panel reads, plus any pack shipped with it.
Source: "{#Root}\modules\*"; DestDir: "{app}\modules"; Flags: ignoreversion recursesubdirs createallsubdirs

Source: "{#Root}\services\api\requirements.txt"; DestDir: "{app}\services\api"; Flags: ignoreversion
Source: "{#Root}\services\api\app\*.py"; DestDir: "{app}\services\api\app"; Flags: ignoreversion
Source: "{#Root}\services\api\app\routers\*.py"; DestDir: "{app}\services\api\app\routers"; Flags: ignoreversion
Source: "{#Root}\services\api\app\services\*.py"; DestDir: "{app}\services\api\app\services"; Flags: ignoreversion
Source: "{#Root}\services\api\fonts\*"; DestDir: "{app}\services\api\fonts"; Flags: ignoreversion

Source: "{#Root}\services\face-service\requirements.txt"; DestDir: "{app}\services\face-service"; Flags: ignoreversion
Source: "{#Root}\services\face-service\app\*.py"; DestDir: "{app}\services\face-service\app"; Flags: ignoreversion
Source: "{#Root}\services\face-service\app\cameras\*.py"; DestDir: "{app}\services\face-service\app\cameras"; Flags: ignoreversion
Source: "{#Root}\services\face-service\app\analytics\*.py"; DestDir: "{app}\services\face-service\app\analytics"; Flags: ignoreversion
; Lets fetch-payload.ps1 repair a runtime that has gone missing.
Source: "{#Root}\setup\payload-manifest.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Root}\services\face-service\tests\*.py"; DestDir: "{app}\services\face-service\tests"; Flags: ignoreversion

; ---- no runtime, no models ----
; Both are left exactly as the installed system already has them.

; ---- panel ----
Source: "{#Root}\web\dist\*"; DestDir: "{app}\web\dist"; Flags: ignoreversion recursesubdirs createallsubdirs
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

; ---- scripts + icon ----
Source: "{#Root}\setup\scripts\*.ps1"; DestDir: "{app}\scripts"; Flags: ignoreversion
Source: "{#Root}\setup\scripts\*.cmd"; DestDir: "{app}\scripts"; Flags: ignoreversion
Source: "{#Root}\setup\README.md"; DestDir: "{app}\scripts"; DestName: "README-install.md"; Flags: ignoreversion
Source: "{#Root}\setup\app.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}\شروع سامانه"; Filename: "{app}\scripts\run-start.cmd"; WorkingDir: "{app}"; IconFilename: "{app}\app.ico"
Name: "{autoprograms}\{#MyAppName}\توقف سامانه"; Filename: "{app}\scripts\run-stop.cmd"; WorkingDir: "{app}"; IconFilename: "{app}\app.ico"
Name: "{autoprograms}\{#MyAppName}\وضعیت سامانه"; Filename: "{app}\scripts\run-status.cmd"; WorkingDir: "{app}"; IconFilename: "{app}\app.ico"
Name: "{autoprograms}\{#MyAppName}\گزارش خطا برای پشتیبانی"; Filename: "{app}\scripts\run-debug.cmd"; WorkingDir: "{app}"; IconFilename: "{app}\app.ico"
Name: "{autoprograms}\{#MyAppName}\راهنما"; Filename: "{app}\scripts\README-install.md"

[Run]
Filename: "{app}\scripts\run-update.cmd"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent; Description: "اعمال به‌روزرسانی و راه‌اندازی سامانه"

[Code]
{ Where the earlier releases put themselves, newest layout first. Used as the
  default directory, so a /DIR= on the command line still takes precedence. }
function ExistingInstallation(Param: String): String;
var
  candidates: array[0..3] of String;
  i: Integer;
begin
  candidates[0] := 'C:\HotelFaceID';
  candidates[1] := ExpandConstant('{localappdata}\Programs\Hotel FaceID');
  candidates[2] := ExpandConstant('{pf}\Hotel FaceID');
  candidates[3] := ExpandConstant('{commonpf}\Hotel FaceID');

  for i := 0 to 3 do
    { A database or a settings file marks a real installation, as opposed to
      an empty folder somebody happened to create. }
    if FileExists(candidates[i] + '\data\hotel_faceid.db') or
       FileExists(candidates[i] + '\.env') then
    begin
      Result := candidates[i];
      exit;
    end;

  Result := 'C:\HotelFaceID';
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  if WizardSilent() then
    exit;

  if ExistingInstallation('') = 'C:\HotelFaceID' then
    if not FileExists('C:\HotelFaceID\.env') then
      MsgBox('نصب قبلی سامانه به‌طور خودکار پیدا نشد.' + #13#10 +
             'اگر سامانه در مسیر دیگری نصب است، در صفحهٔ انتخاب مسیر همان پوشه را بدهید.' + #13#10 +
             'اگر سامانه اصلاً نصب نیست، به‌جای این فایل از نصب‌کنندهٔ کامل استفاده کنید.',
             mbInformation, MB_OK);
end;
