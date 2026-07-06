; build/installer.iss — Instalador do MarketplaceBot (Inno Setup 6)
;
; Compilar (na raiz do repo, APÓS o build do PyInstaller):
;   iscc /DMyAppVersion=1.0.0 build\installer.iss
;
; Saída: dist\installer\MarketplaceBot-Setup-1.0.0.exe
;
; Dados do usuário (%LOCALAPPDATA%\MarketplaceBot) NUNCA são tocados por
; instalação, update ou desinstalação — nada aqui referencia essa pasta.

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif

#define MyAppName "MarketplaceBot"
#define MyAppExeName "MarketplaceBot.exe"
#define MyAppPublisher "Thomas Geron"
#define MyAppURL "https://github.com/Thomas-Geron/marketplace-bot"

[Setup]
; AppId FIXO — NUNCA alterar: é o que faz o Windows tratar cada nova versão
; como update do mesmo programa, e não como um segundo programa instalado.
AppId={{0D69F8B6-B269-42D2-9001-89E42C1498E7}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=MarketplaceBot-Setup-{#MyAppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
; update in-place: fecha o app aberto antes de copiar e reabre ao final
CloseApplications=yes
RestartApplications=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; todo o conteúdo do onedir gerado pelo PyInstaller
Source: "..\dist\MarketplaceBot\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; garante o navegador: só baixa/instala o Chrome se ele não existir
; (roda elevado, dentro do contexto do instalador)
Filename: "{app}\{#MyAppExeName}"; Parameters: "--install-browser"; StatusMsg: "Verificando o navegador (primeiro uso pode demorar alguns minutos)..."; Flags: runhidden waituntilterminated
; instalação interativa: checkbox "Abrir o MarketplaceBot" no final
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent runasoriginaluser
; update silencioso disparado pelo próprio app (update.py passa /RELAUNCH=1):
; reabre o programa como o usuário original ao terminar de instalar
Filename: "{app}\{#MyAppExeName}"; Flags: nowait runasoriginaluser; Check: PrecisaReabrir

[Code]
function PrecisaReabrir: Boolean;
begin
  Result := ExpandConstant('{param:RELAUNCH|0}') = '1';
end;
