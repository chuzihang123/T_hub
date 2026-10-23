#define AppName "T Hub"
#define AppVersion "1.1.0"
#define AppExe "MchoseWidget.exe"
#define AppPublisher "chuzihang123"

[Setup]
AppId={{A7C1E4B2-6F3D-4B8E-9C21-5D8A0F7E3B64}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\T Hub
DefaultGroupName=T Hub
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=T-Hub-v1.1.0-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
CloseApplications=yes
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
VersionInfoVersion=1.1.0.0
VersionInfoDescription=T Hub installer
VersionInfoProductName={#AppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "autostart"; Description: "Start T Hub automatically when Windows starts (开机自动启动)"; GroupDescription: "Additional tasks / 附加任务:"; Flags: checkedonce
Name: "desktopicon"; Description: "Create a desktop shortcut (创建桌面快捷方式)"; GroupDescription: "Additional tasks / 附加任务:"; Flags: checkedonce

[Files]
Source: "..\build\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\docs\all-devices.png"; DestDir: "{app}\docs"; Flags: ignoreversion

[Icons]
Name: "{group}\T Hub"; Filename: "{app}\{#AppExe}"
Name: "{group}\Uninstall T Hub"; Filename: "{uninstallexe}"
Name: "{autodesktop}\T Hub"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; \
    ValueName: "MCHOSE Widget"; ValueData: """{app}\{#AppExe}"""; \
    Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch T Hub now (立即运行)"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/c taskkill /im {#AppExe} /f"; Flags: runhidden; RunOnceId: "KillApp"
