; Inno Setup skript pre Zanshin
; Preklad:  build_all.ps1  (alebo rucne:  ISCC.exe Dandurf.iss)
;
; Pozn.: AppId sa NIKDY nemeni - podla neho Windows spozna, ze ide o
; aktualizaciu uz nainstalovanej verzie a nie o druhu paralelnu instalaciu.
;
; INSTALACIA BEZ ADMIN PRAV (PrivilegesRequired=lowest): instaluje sa do
; profilu pouzivatela ({autopf} = %LOCALAPPDATA%\Programs\Zanshin),
; nie do Program Files, a nepyta si UAC. Dovody (viz SAFETY.md):
;   * elevovany proces + overlay nad hrou je presne profil, ktory
;     anti-cheaty (Vanguard, EAC, VAC) hodnotia najprisnejsie; menej prav =
;     menej dovodov na podozrenie (globalne hooky appka nema),
;   * "Error 707" pri instalacii vznikal z vyzadovania elevacie - bez nej
;     zmizne.
; Skorsi pokus o admin instalaciu do Program Files bol reakciou na Smart App
; Control (chyba 4551); spravna cesta k reputacii je podpis .exe, nie
; elevacia. Pouzivatelske data (nastavenia, nahravky, TTS cache) idu do
; %APPDATA%\Zanshin bez ohladu na instalacnu zlozku - viz paths.py.
;
; JAZYKY: instalator hovori vsetkymi 11 jazykmi appky (sk, en, ja, zh, ru,
; es, de, fr, pt, cs, bg). Predvoleny je ANGLICKY - prvy v [Languages] a
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
#define MyAppVersion "0.2.1"
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
; Verzia v Podrobnostiach samotneho setup.exe - bez nej tam Inno Setup
; napise 0.0.0.0. Chybajuce cisla doplni nulami, takze "0.2.1" da 0.2.1.0
; (to iste ako filevers vo version_info.txt) a verzia sa nedrzi na dvoch
; miestach. VersionInfoProductVersion ma Inno predvolene rovnaku.
VersionInfoVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; "lowest" = ziadne UAC, instalacia do profilu pouzivatela ({autopf} sa
; vtedy sam prepne na %LOCALAPPDATA%\Programs). Zhodne s uac_admin=False
; v Dandurf.spec - viz komentar hore.
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
; cestina a bulharcina (0.2) - obe su sucastou instalacie Inno Setup 6
Name: "czech"; MessagesFile: "compiler:Languages\Czech.isl"
Name: "bulgarian"; MessagesFile: "compiler:Languages\Bulgarian.isl"

[CustomMessages]
; Vlastne texty, ktore Inno Setup sam neprelozi. CreateDesktopIcon,
; AdditionalIcons a LaunchProgram su standardne v kazdom .isl, tie
; netreba. Otazka pri odinstalovani je zamerne formulovana tak, aby
; predvolene (prve) tlacidlo DATA ZACHOVALO - omylom sa tak neda prist
; o sloty, historiu tepu, nahravky ani vygenerovane hlasky. Historia tepu
; (hr_sessions.json, hr_windows.json, hr_events.jsonl, hr_insights.json aj
; ich zalohy) lezi v tom istom priecinku, takze ju otazka musi menovat -
; inak by pri "Ano" ostala zdravotna historia bez toho, aby o tom clovek
; vedel.
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
; Subory, ktore nainstalovala 0.1 a 0.2 ich uz nema. Aktualizacia cez
; [Files] len prepisuje a pridava, takze by inak ostali lezat v {app}.
; PyInstaller 6 v onedir builde dava data do _internal\ (contents_directory
; v Dandurf.spec nemenime), preto _internal\assets\... Maze sa LEN v {app} -
; pouzivatelske data v %APPDATA%\Zanshin (nastavenia, historia tepu,
; nahravky, hlasky) sa tu nikdy nemazu.
Type: files; Name: "{app}\_internal\assets\images\dojo_band.jpg"
Type: files; Name: "{app}\_internal\assets\guides\README.txt"
Type: dirifempty; Name: "{app}\_internal\assets\guides"

[Files]
; Onedir build (Dandurf.spec) - cely priecinok dist\Zanshin\
; (exe + kniznice) sa skopiruje do {app}\, poduprecinky vratane.
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Licencia a dusa appky vedla Zanshin.exe. LICENSE doteraz v instalatore
; chybal (spec ho do dist\ nebali) - GPLv3 chce text licencie pri kazdej
; kopii programu. SOUL.md je v 0.2 verejny (rozhodnutie autora). K nim
; LICENSE-DESIGN.md (ikona a obrazok dojo su autorove; upravena verzia sa
; nesmie vydavat za oficialny Zanshin) a ZDROJE.md (cely zoznam zdrojov) - rozhodnutie autora 24. 9. Vsetky
; cesty su relativne k tomuto .iss, cize z korena repozitara.
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
// Pri odinstalovani sa pytame, ci data ponechat. Text je v jazyku, ktory
// si pouzivatel zvolil pri instalacii (Inno si ho pamata).
//
// Okrem {userappdata}\Zanshin su tu aj STARE priecinky z cias, ked sa appka
// volala "Zanshin DojoSync" a "Dandurf" (paths.LEGACY_APP_NAMES). Appka z
// nich pri prvom starte data len KOPIROVALA, takze v nich ostala kopia
// historie tepu. Pri "Nie" sa zmazu aj ony - inak by po odinstalovani
// ostala zdravotna historia natrvalo. Dialog vypise kazdy priecinok, ktory
// zmaze.
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
