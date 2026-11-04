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
DisableWelcomePage=yes
DisableDirPage=yes
DisableProgramGroupPage=yes
ShowLanguageDialog=no
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
WizardSizePercent=100
CloseApplications=no
RestartApplications=no
UninstallDisplayName=NTSC-RS for OBS
UninstallFilesDir={app}\uninstall
SetupLogging=yes
VersionInfoDescription=NTSC-RS for OBS installer

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
FinishedHeadingLabel=Setup complete

[CustomMessages]
TitleNew=Install NTSC-RS for OBS
TitleUpdate=Update NTSC-RS for OBS
TitleSame=Reinstall NTSC-RS for OBS
TitleNewer=Replace NTSC-RS for OBS
Subtitle=Native NTSC/VHS filter for OBS Studio
ReadyNew=NTSC-RS for OBS %1 will be installed.%n%nClose OBS before you continue. Setup never closes OBS for you.
ReadyUpdate=Version %2 is installed and will be updated to %1.%nYour presets and OBS settings are kept.%n%nClose OBS before you continue.
ReadySame=Version %1 is already installed and will be reinstalled.%nYour presets and OBS settings are kept.%n%nClose OBS before you continue.
ReadyNewer=A newer version (%2) is installed and will be replaced with %1.%nYour presets and OBS settings are kept.%n%nClose OBS before you continue.
ButtonUpdate=&Update
ButtonReinstall=&Reinstall
ButtonReplace=&Replace
Done=NTSC-RS for OBS %1 has been installed.%n%nIn OBS: Filters > Effect Filters > + > ntsc-rs (NTSC / VHS).

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
var
  InstalledVersion: String;

function NextVersionPart(var S: String): Integer;
var
  P: Integer;
begin
  P := Pos('.', S);
  if P = 0 then
  begin
    Result := StrToIntDef(S, 0);
    S := '';
  end
  else
  begin
    Result := StrToIntDef(Copy(S, 1, P - 1), 0);
    Delete(S, 1, P);
  end;
end;

function CompareVersions(A, B: String): Integer;
var
  X, Y: Integer;
begin
  Result := 0;
  while (Result = 0) and ((A <> '') or (B <> '')) do
  begin
    X := NextVersionPart(A);
    Y := NextVersionPart(B);
    if X < Y then
      Result := -1
    else if X > Y then
      Result := 1;
  end;
end;

function ReadInstalledVersion: String;
begin
  Result := '';
#ifdef TestInstalledVersion
  { Test builds simulate an existing installation without touching the registry. }
  Result := '{#TestInstalledVersion}';
#else
  #ifndef TestInstall
  RegQueryStringValue(HKLM,
    'Software\Microsoft\Windows\CurrentVersion\Uninstall\{F9207DA1-D87E-4A46-B48C-E548AA7C6102}_is1',
    'DisplayVersion', Result);
  #endif
#endif
end;

procedure InitializeWizard;
begin
  InstalledVersion := ReadInstalledVersion;
  { WizardSizePercent cannot go below 100; the anchored layout shrinks with the form. }
  WizardForm.ClientHeight := WizardForm.ClientHeight - ScaleY(170);
  WizardForm.WizardSmallBitmapImage.Visible := False;
  WizardForm.WizardBitmapImage2.Visible := False;
end;

procedure LayoutFinishedPage;
var
  L: Integer;
begin
  { Without the side image, align the text with the first page and use the full width. }
  L := WizardForm.InnerNotebook.Left + WizardForm.ReadyLabel.Left;
  WizardForm.FinishedHeadingLabel.Left := L;
  WizardForm.FinishedHeadingLabel.Width := WizardForm.FinishedPage.ClientWidth - 2 * L;
  WizardForm.FinishedHeadingLabel.AdjustHeight;
  WizardForm.FinishedLabel.Left := L;
  WizardForm.FinishedLabel.Width := WizardForm.FinishedHeadingLabel.Width;
  WizardForm.FinishedLabel.Top := WizardForm.FinishedHeadingLabel.Top + WizardForm.FinishedHeadingLabel.Height + ScaleY(12);
  WizardForm.FinishedLabel.AdjustHeight;
end;

procedure CurPageChanged(CurPageID: Integer);
var
  Order: Integer;
begin
  if CurPageID = wpReady then
  begin
    { The ready label is sized for one line; the settings memo below it is empty here. }
    WizardForm.ReadyMemo.Visible := False;
    WizardForm.ReadyLabel.Height := WizardForm.ReadyMemo.Top + WizardForm.ReadyMemo.Height - WizardForm.ReadyLabel.Top;
    WizardForm.PageDescriptionLabel.Caption := CustomMessage('Subtitle');
    if InstalledVersion = '' then
    begin
      WizardForm.PageNameLabel.Caption := CustomMessage('TitleNew');
      WizardForm.ReadyLabel.Caption := FmtMessage(CustomMessage('ReadyNew'), ['{#PluginVersion}']);
      WizardForm.NextButton.Caption := SetupMessage(msgButtonInstall);
    end
    else
    begin
      Order := CompareVersions(InstalledVersion, '{#PluginVersion}');
      if Order < 0 then
      begin
        WizardForm.PageNameLabel.Caption := CustomMessage('TitleUpdate');
        WizardForm.ReadyLabel.Caption := FmtMessage(CustomMessage('ReadyUpdate'), ['{#PluginVersion}', InstalledVersion]);
        WizardForm.NextButton.Caption := CustomMessage('ButtonUpdate');
      end
      else if Order = 0 then
      begin
        WizardForm.PageNameLabel.Caption := CustomMessage('TitleSame');
        WizardForm.ReadyLabel.Caption := FmtMessage(CustomMessage('ReadySame'), ['{#PluginVersion}']);
        WizardForm.NextButton.Caption := CustomMessage('ButtonReinstall');
      end
      else
      begin
        WizardForm.PageNameLabel.Caption := CustomMessage('TitleNewer');
        WizardForm.ReadyLabel.Caption := FmtMessage(CustomMessage('ReadyNewer'), ['{#PluginVersion}', InstalledVersion]);
        WizardForm.NextButton.Caption := CustomMessage('ButtonReplace');
      end;
    end;
  end
  else if CurPageID = wpFinished then
  begin
    WizardForm.FinishedLabel.Caption := FmtMessage(CustomMessage('Done'), ['{#PluginVersion}']);
    LayoutFinishedPage;
  end;
end;

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
