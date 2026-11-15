; Inno Setup script for Zanshin
; Compile:  build_all.ps1  (or by hand:  ISCC.exe Dandurf.iss)
;
; Note: the AppId NEVER changes - it is how Windows recognises that this is
; an update of the installed version and not a second, parallel installation.
;
; INSTALLING WITHOUT ADMIN RIGHTS (PrivilegesRequired=lowest): it installs into
; the user's profile ({autopf} = %LOCALAPPDATA%\Programs\Zanshin),
; not into Program Files, and doesn't ask for UAC. Reasons (see SAFETY.md):
;   * an elevated process + an overlay over a game is exactly the profile that
;     anti-cheats (Vanguard, EAC, VAC) judge most strictly; fewer rights =
;     fewer reasons for suspicion (the app has no global hooks),
;   * "Error 707" during installation came from requiring elevation - without
;     it, it goes away.
; The earlier attempt at an admin install into Program Files was a reaction to
; Smart App Control (error 4551); the right way to reputation is signing the
; .exe, not elevation. User data (settings, recordings, TTS cache) goes to
; %APPDATA%\Zanshin whatever the install folder is - see paths.py.
;
; LANGUAGES: the installer speaks all 11 languages of the app (sk, en, ja, zh,
; ru, es, de, fr, pt, cs, bg). The default is ENGLISH - first in [Languages] and
; LanguageDetectionMethod=none, so the language selection dialog always
; defaults to English whatever the Windows language is (anyone can switch).
; If the installer should rather guess the language from Windows, change it to
; LanguageDetectionMethod=uilanguage.
; Chinese is not part of the Inno Setup 6 installation - its translation is in
; installer_lang\ChineseSimplified.isl (UTF-8 with BOM); the compiler fills in
; the messages missing from it from Default.isl.
;
; We deliberately don't split entries over several lines: every entry in a
; section must be on one line.

#define MyAppName "Zanshin"
#define MyAppVersion "0.3"
#define MyAppPublisher "Dandurfin"
#define MyAppExeName "Zanshin.exe"
; Where to take the onedir build from; it can be overridden on the command line
; (ISCC /DDistDir=dist_v1\Zanshin Dandurf.iss), e.g. when the running app holds
; the old dist\ and PyInstaller can't overwrite it.
#ifndef DistDir
#define DistDir "dist\Zanshin"
#endif

[Setup]
AppId={{30295CDB-462B-4151-B225-582E82027A33}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
; The version in the Details of setup.exe itself - without it Inno Setup
; writes 0.0.0.0 there. It pads missing numbers with zeros, so "0.3" gives
; 0.3.0.0 (the same as filevers in version_info.txt) and the version isn't kept
; in two places. Inno gives VersionInfoProductVersion the same value by default.
VersionInfoVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; "lowest" = no UAC, installs into the user's profile ({autopf} then switches
; to %LOCALAPPDATA%\Programs by itself). Matches uac_admin=False
; in Dandurf.spec - see the comment at the top.
PrivilegesRequired=lowest
OutputDir=installer
OutputBaseFilename=Zanshin-{#MyAppVersion}-setup
SetupIconFile=Dandurf.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; language selection: always show the dialog, the default is the first entry (English)
ShowLanguageDialog=yes
LanguageDetectionMethod=none

[Languages]
; The first entry = the default. The .isl names are from the Inno Setup 6.5
; installation (compiler:Languages\...), except Chinese - see the comment at the top.
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "slovak"; MessagesFile: "compiler:Languages\Slovak.isl"
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"
Name: "chinesesimplified"; MessagesFile: "installer_lang\ChineseSimplified.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
; the app uses Brazilian Portuguese ("tela", not "ecra")
Name: "portuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
; Czech and Bulgarian (0.2) - both are part of the Inno Setup 6 installation
Name: "czech"; MessagesFile: "compiler:Languages\Czech.isl"
Name: "bulgarian"; MessagesFile: "compiler:Languages\Bulgarian.isl"

[CustomMessages]
; Our own texts, which Inno Setup doesn't translate by itself. CreateDesktopIcon,
; AdditionalIcons and LaunchProgram are standard in every .isl, so they
; aren't needed here. The uninstall question is deliberately worded so that
; the default (first) button KEEPS THE DATA - so nobody loses their slots,
; heart-rate history, recordings or generated voice lines by mistake. The
; heart-rate history (hr_sessions.json, hr_windows.json, hr_events.jsonl,
; hr_insights.json and their backups) lies in the same folder, so the question
; must name it - otherwise on "Yes" the health history would stay without the
; person knowing.
english.KeepDataQuestion=Keep your settings, heart-rate history, recordings and generated voice lines?
english.KeepDataHint=Choose Yes if you plan to install %1 again some day.
slovak.KeepDataQuestion=Ponechať tvoje nastavenia, históriu tepu, nahrávky a vygenerované hlásky?
slovak.KeepDataHint=Zvoľ Áno, ak plánuješ %1 ešte niekedy nainštalovať.
japanese.KeepDataQuestion=設定、心拍の履歴、録音、生成した音声を残しますか？
japanese.KeepDataHint=%1 をいつかまたインストールする予定なら「はい」を選んでください。
chinesesimplified.KeepDataQuestion=是否保留你的设置、心率历史、录音和已生成的语音？
chinesesimplified.KeepDataHint=如果你以后还打算安装 %1，请选择“是”。
russian.KeepDataQuestion=Сохранить твои настройки, историю пульса, записи и сгенерированные фразы?
russian.KeepDataHint=Выбери «Да», если планируешь когда-нибудь снова установить %1.
spanish.KeepDataQuestion=¿Conservar tus ajustes, tu historial de frecuencia cardíaca, grabaciones y frases de voz generadas?
spanish.KeepDataHint=Elige Sí si piensas volver a instalar %1 algún día.
german.KeepDataQuestion=Deine Einstellungen, deinen Herzfrequenzverlauf, Aufnahmen und erzeugten Sprachansagen behalten?
german.KeepDataHint=Wähle Ja, wenn du %1 irgendwann wieder installieren willst.
french.KeepDataQuestion=Conserver tes réglages, ton historique de fréquence cardiaque, tes enregistrements et phrases vocales générées ?
french.KeepDataHint=Choisis Oui si tu comptes réinstaller %1 un jour.
portuguese.KeepDataQuestion=Manter suas configurações, histórico de frequência cardíaca, gravações e falas geradas?
portuguese.KeepDataHint=Escolha Sim se pretende instalar o %1 novamente algum dia.
czech.KeepDataQuestion=Ponechat tvoje nastavení, historii tepu, nahrávky a vygenerované hlášky?
czech.KeepDataHint=Zvol Ano, pokud plánuješ %1 ještě někdy nainstalovat.
bulgarian.KeepDataQuestion=Да се запазят ли настройките ти, историята на пулса, записите и генерираните гласови реплики?
bulgarian.KeepDataHint=Избери „Да“, ако смяташ някой ден пак да инсталираш %1.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; Files that 0.1 installed and 0.2 no longer has. An update through
; [Files] only overwrites and adds, so otherwise they would stay in {app}.
; PyInstaller 6 puts the data of an onedir build into _internal\ (we don't
; change contents_directory in Dandurf.spec), hence _internal\assets\... This
; deletes ONLY in {app} - user data in %APPDATA%\Zanshin (settings, heart-rate
; history, recordings, voice lines) is never deleted here.
Type: files; Name: "{app}\_internal\assets\images\dojo_band.jpg"
Type: files; Name: "{app}\_internal\assets\guides\README.txt"
Type: dirifempty; Name: "{app}\_internal\assets\guides"

[Files]
; Onedir build (Dandurf.spec) - the whole folder dist\Zanshin\
; (exe + libraries) is copied into {app}\, subfolders included.
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; The licence and the soul of the app next to Zanshin.exe. LICENSE used to be
; missing from the installer (the spec doesn't pack it into dist\) - GPLv3 wants
; the licence text with every copy of the program. SOUL.md is public in 0.2
; (the author's decision). With them LICENSE-DESIGN.md (the icon and the dojo
; image are the author's; a modified version must not be passed off as the
; official Zanshin) and ZDROJE.md (the full list of sources) - the author's
; decision of 24 Sep. All paths are relative to this .iss, i.e. to the
; repository root.
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "SOUL.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE-DESIGN.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "ZDROJE.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
// On uninstall we ask whether to keep the data. The text is in the language
// the user chose during installation (Inno remembers it).
//
// Besides {userappdata}\Zanshin, these are also the OLD folders from the time
// the app was called "Zanshin DojoSync" and "Dandurf" (paths.LEGACY_APP_NAMES).
// On its first start the app only COPIED the data from them, so a copy of the
// heart-rate history stayed in them. On "No" they are deleted too - otherwise
// the health history would stay for good after uninstalling. The dialog lists
// every folder it deletes.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Dirs: array[0..2] of String;
  Found: String;
  I: Integer;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    Dirs[0] := ExpandConstant('{userappdata}\{#MyAppName}');
    Dirs[1] := ExpandConstant('{userappdata}\Zanshin DojoSync');
    Dirs[2] := ExpandConstant('{userappdata}\Dandurf');
    Found := '';
    for I := 0 to 2 do
      if DirExists(Dirs[I]) then
        Found := Found + Dirs[I] + #13#10;
    if Found <> '' then
    begin
      if MsgBox(CustomMessage('KeepDataQuestion')
                + #13#10#13#10 + Found + #13#10
                + FmtMessage(CustomMessage('KeepDataHint'), ['{#MyAppName}']),
                mbConfirmation, MB_YESNO) = IDNO then
        for I := 0 to 2 do
          if DirExists(Dirs[I]) then
            DelTree(Dirs[I], True, True, True);
    end;
  end;
end;
