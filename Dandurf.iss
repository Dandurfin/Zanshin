; Inno Setup skript pre Zanshin
; Preklad:  build_all.ps1  (alebo rucne:  ISCC.exe Dandurf.iss)
;
; Pozn.: AppId sa NIKDY nemeni - podla neho Windows spozna, ze ide o
; aktualizaciu uz nainstalovanej verzie a nie o druhu paralelnu instalaciu.
;
; INSTALACIA BEZ ADMIN PRAV (PrivilegesRequired=lowest): instaluje sa do
; profilu pouzivatela ({autopf} = %LOCALAPPDATA%\Programs\Zanshin),
; nie do Program Files, a nepyta si UAC. Dovody (viz STEAM_BUILD.md):
;   * elevovany proces + globalne klavesove hooky + overlay nad hrou je
;     presne profil, ktory anti-cheaty (Vanguard, EAC, VAC) hodnotia
;     najprisnejsie; menej prav = menej dovodov na podozrenie,
;   * Steam elevaciu nepodporuje (rozbity overlay, UAC pri kazdom starte),
;   * "Error 707" pri instalacii vznikal z vyzadovania elevacie - bez nej
;     zmizne.
; Skorsi pokus o admin instalaciu do Program Files bol reakciou na Smart App
; Control (chyba 4551); spravna cesta k reputacii je podpis .exe, nie
; elevacia. Pouzivatelske data (nastavenia, nahravky, TTS cache) idu do
; %APPDATA%\Zanshin bez ohladu na instalacnu zlozku - viz paths.py.
;
; JAZYKY: instalator hovori vsetkymi 9 jazykmi appky (sk, en, ja, zh, ru,
; es, de, fr, pt). Predvoleny je ANGLICKY - prvy v [Languages] a
; LanguageDetectionMethod=none, takze dialog vyberu jazyka ma vzdy
; predvolenu anglictinu bez ohladu na jazyk Windows (kto chce, prepne si).
; Ak by mal instalator radsej hadat jazyk podla Windows, zmen na
; LanguageDetectionMethod=uilanguage.
; Cinstina nie je sucastou instalacie Inno Setup 6 - preklad je v
; installer_lang\ChineseSimplified.isl (UTF-8 s BOM); hlasky, ktore v nom
; chybaju, kompilator doplni z Default.isl.
;
; Poloziek zamerne nerozdelujeme na viac riadkov: kazdy zaznam v sekcii
; musi byt na jednom riadku.

#define MyAppName "Zanshin"
#define MyAppVersion "0.1"
#define MyAppPublisher "Dandurfin"
#define MyAppExeName "Zanshin.exe"
; Odkial brat onedir build; da sa prepisat z prikazoveho riadku
; (ISCC /DDistDir=dist_v1\Zanshin Dandurf.iss), napr. ked stary
; dist\ drzi beziaca appka a PyInstaller ho nevie prepisat.
#ifndef DistDir
#define DistDir "dist\Zanshin"
#endif

[Setup]
AppId={{30295CDB-462B-4151-B225-582E82027A33}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; "lowest" = ziadne UAC, instalacia do profilu pouzivatela ({autopf} sa
; vtedy sam prepne na %LOCALAPPDATA%\Programs). Zhodne s uac_admin=False
; v Dandurf.spec - viz komentar hore a STEAM_BUILD.md.
PrivilegesRequired=lowest
OutputDir=installer
OutputBaseFilename=Zanshin-{#MyAppVersion}-setup
SetupIconFile=Dandurf.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; vyber jazyka: vzdy ukaz dialog, predvolena je prva polozka (anglictina)
ShowLanguageDialog=yes
LanguageDetectionMethod=none

[Languages]
; Prva polozka = predvolena. Nazvy .isl su z instalacie Inno Setup 6.5
; (compiler:Languages\...), okrem cinstiny - viz komentar hore.
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "slovak"; MessagesFile: "compiler:Languages\Slovak.isl"
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"
Name: "chinesesimplified"; MessagesFile: "installer_lang\ChineseSimplified.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
; appka pouziva brazilsku portugalcinu ("tela", nie "ecra")
Name: "portuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[CustomMessages]
; Vlastne texty, ktore Inno Setup sam neprelozi. CreateDesktopIcon,
; AdditionalIcons a LaunchProgram su standardne v kazdom .isl, tie
; netreba. Otazka pri odinstalovani je zamerne formulovana tak, aby
; predvolene (prve) tlacidlo DATA ZACHOVALO - omylom sa tak neda prist
; o sloty, nahravky ani vygenerovane hlasky.
english.KeepDataQuestion=Keep your settings, recordings and generated voice lines?
english.KeepDataHint=Choose Yes if you plan to install %1 again some day.
slovak.KeepDataQuestion=Ponechať tvoje nastavenia, nahrávky a vygenerované hlásky?
slovak.KeepDataHint=Zvoľ Áno, ak plánuješ %1 ešte niekedy nainštalovať.
japanese.KeepDataQuestion=設定、録音、生成した音声を残しますか？
japanese.KeepDataHint=%1 をいつかまたインストールする予定なら「はい」を選んでください。
chinesesimplified.KeepDataQuestion=是否保留你的设置、录音和已生成的语音？
chinesesimplified.KeepDataHint=如果你以后还打算安装 %1，请选择“是”。
russian.KeepDataQuestion=Сохранить твои настройки, записи и сгенерированные фразы?
russian.KeepDataHint=Выбери «Да», если планируешь когда-нибудь снова установить %1.
spanish.KeepDataQuestion=¿Conservar tus ajustes, grabaciones y frases de voz generadas?
spanish.KeepDataHint=Elige Sí si piensas volver a instalar %1 algún día.
german.KeepDataQuestion=Deine Einstellungen, Aufnahmen und erzeugten Sprachansagen behalten?
german.KeepDataHint=Wähle Ja, wenn du %1 irgendwann wieder installieren willst.
french.KeepDataQuestion=Conserver tes réglages, enregistrements et phrases vocales générées ?
french.KeepDataHint=Choisis Oui si tu comptes réinstaller %1 un jour.
portuguese.KeepDataQuestion=Manter suas configurações, gravações e falas geradas?
portuguese.KeepDataHint=Escolha Sim se pretende instalar o %1 novamente algum dia.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Onedir build (Dandurf.spec) - cely priecinok dist\Zanshin\
; (exe + kniznice) sa skopiruje do {app}\, poduprecinky vratane.
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
// Pri odinstalovani sa pytame, ci data ponechat. Text je v jazyku, ktory
// si pouzivatel zvolil pri instalacii (Inno si ho pamata).
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{userappdata}\{#MyAppName}');
    if DirExists(DataDir) then
    begin
      if MsgBox(CustomMessage('KeepDataQuestion')
                + #13#10#13#10 + DataDir + #13#10#13#10
                + FmtMessage(CustomMessage('KeepDataHint'), ['{#MyAppName}']),
                mbConfirmation, MB_YESNO) = IDNO then
        DelTree(DataDir, True, True, True);
    end;
  end;
end;
