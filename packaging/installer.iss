#ifndef PluginVersion
  #define PluginVersion "0.2.0"
#endif
#define ProjectRoot AddBackslash(SourcePath) + ".."
#define Payload ProjectRoot + "\dist\obs-ntsc-rs"

[Setup]
#ifdef TestInstall
AppId=NTSC-RS-OBS-Packaging-Test
DefaultDirName={tmp}\NTSC-RS-OBS-Packaging-Test
PrivilegesRequired=lowest
CreateUninstallRegKey=no
OutputDir={#ProjectRoot}\test-output\packaging
OutputBaseFilename=installer-test
#else
AppId={{F9207DA1-D87E-4A46-B48C-E548AA7C6102}
DefaultDirName={commonappdata}\obs-studio\plugins\obs-ntsc-rs
PrivilegesRequired=admin
OutputDir={#ProjectRoot}\dist\releases
OutputBaseFilename=NTSC-RS-OBS-{#PluginVersion}-Windows-Setup
#endif
AppName=NTSC-RS for OBS
AppVersion={#PluginVersion}
AppPublisher=NTSC-RS for OBS
DisableDirPage=yes
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
LicenseFile={#Payload}\LICENSE-GPL-2.0.txt
InfoBeforeFile={#SourcePath}\DISCLAIMER.txt
CloseApplications=no
RestartApplications=no
UninstallDisplayName=NTSC-RS for OBS
UninstallFilesDir={app}\uninstall
SetupLogging=yes
VersionInfoDescription=NTSC-RS for OBS installer

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Dirs]
Name: "{app}\data"

[Files]
Source: "{#Payload}\bin\64bit\obs-ntsc-rs.dll"; DestDir: "{app}\bin\64bit"; Flags: ignoreversion
Source: "{#Payload}\README.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Payload}\LICENSE-GPL-2.0.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Payload}\LICENSE-ntsc-rs-MIT.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Payload}\THIRD-PARTY.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Payload}\data\README.txt"; DestDir: "{app}\data"; Flags: ignoreversion

[Code]
function OBSIsRunning: Boolean;
var
  Locator, Services, Processes: Variant;
begin
  { Read only. Do not stop processes or interact with a user's OBS configuration. }
  Locator := CreateOleObject('WbemScripting.SWbemLocator');
  Services := Locator.ConnectServer('', 'root\CIMV2');
  Processes := Services.ExecQuery('SELECT ProcessId FROM Win32_Process WHERE Name = ''obs64.exe''');
  Result := Processes.Count > 0;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ExistingDLL, Marker: String;
begin
  Result := '';
#ifdef TestInstall
  { The test writes only a fresh isolated directory, not any OBS search path.
    Production always checks OBS, even for silent installs. }
  Log('Isolated packaging test: bypassing OBS process check.');
#else
  try
    if OBSIsRunning then
    begin
      Result := 'Close OBS yourself before installing. Setup will not close it for you.';
      Exit;
    end;
  except
    Result := 'Could not check whether OBS is running (Windows WMI). Nothing has been installed.';
    Exit;
  end;
#endif
  ExistingDLL := ExpandConstant('{app}\bin\64bit\obs-ntsc-rs.dll');
  Marker := ExpandConstant('{app}\uninstall\unins000.dat');
  if FileExists(ExistingDLL) and not FileExists(Marker) then
    if GetSHA256OfFile(ExistingDLL) <> '{#GetSHA256OfFile(Payload + "\bin\64bit\obs-ntsc-rs.dll")}' then
      Result := 'A different manually installed plugin exists. Back it up and remove only that DLL before running Setup.';
end;

function InitializeUninstall: Boolean;
begin
#ifdef TestInstall
  Result := True;
#else
  Result := False;
  try
    if OBSIsRunning then
      MsgBox('Close OBS yourself before uninstalling. No application will be closed automatically.', mbError, MB_OK)
    else
      Result := True;
  except
    MsgBox('Could not check whether OBS is running (Windows WMI). Uninstall cancelled.', mbError, MB_OK);
  end;
#endif
end;
