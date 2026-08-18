#define AppName "Leave Planner"
#ifndef AppVersion
  #define AppVersion "0.2.0"
#endif
#ifndef AppFileVersion
  #define AppFileVersion "0.2.0.0"
#endif
#define AppExecutable "Leave Planner.exe"

[Setup]
AppId={{67D450D5-8E38-4D17-B7F3-C3E4483AC14C}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}

DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
UsePreviousAppDir=yes

OutputDir=..\dist\installer
OutputBaseFilename=Leave-Planner-Setup-{#AppVersion}
SetupIconFile=..\backend\src\desktop_shell\assets\leave-planner.ico
UninstallDisplayIcon={app}\{#AppExecutable}
UninstallDisplayName={#AppName}

VersionInfoVersion={#AppFileVersion}
VersionInfoProductName={#AppName}
VersionInfoDescription={#AppName} Installer

PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes

CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[InstallDelete]
; Remove obsolete bundled runtime files during an upgrade.
; User data is never stored under this directory.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\Leave Planner\*"; \
    DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

Source: "prerequisites\MicrosoftEdgeWebview2Setup.exe"; \
    DestDir: "{tmp}"; \
    Flags: deleteafterinstall

[Icons]
Name: "{autoprograms}\{#AppName}"; \
    Filename: "{app}\{#AppExecutable}"; \
    WorkingDir: "{app}"

[Run]
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; \
    Parameters: "/silent /install"; \
    StatusMsg: "Installing the Microsoft Edge WebView2 Runtime..."; \
    Flags: waituntilterminated; \
    Check: not WebView2RuntimeInstalled

Filename: "{app}\{#AppExecutable}"; \
    Description: "Launch {#AppName}"; \
    Flags: nowait postinstall skipifsilent

[Code]
const
  WebView2ClientKey =
    'SOFTWARE\Microsoft\EdgeUpdate\Clients\' +
    '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

function HasWebView2Version(RootKey: Integer): Boolean;
var
  Version: String;
begin
  Result :=
    RegQueryStringValue(
      RootKey,
      WebView2ClientKey,
      'pv',
      Version
    )
    and (Version <> '')
    and (CompareText(Version, '0.0.0.0') <> 0);
end;

function WebView2RuntimeInstalled: Boolean;
begin
  Result :=
    HasWebView2Version(HKLM32)
    or HasWebView2Version(HKCU);
end;
