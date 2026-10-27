; ============================================================
;  校园通知智能待办 - 安装程序脚本（CI 版）
;  与本地版的区别：全部用相对路径，输出到 dist\
; ============================================================

; 版本号：优先取环境变量 APP_VERSION，取不到就用默认值 1.0.0
#define MyAppVersion GetEnv("APP_VERSION")
#if MyAppVersion == ""
  #define MyAppVersion "1.0.0"
#endif

#define MyAppName "校园通知智能待办"
#define LaunchVbs "tools\launch.vbs"

[Setup]
PrivilegesRequired=lowest
DefaultDirName={localappdata}\CampusTodo
DefaultGroupName=校园待办
DisableProgramGroupPage=yes
UsePreviousAppDir=no

AppId={{8F3A9C21-4B7D-4E5A-9C1F-2D6B8E4A7F30}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=Campus Todo
VersionInfoVersion={#MyAppVersion}
VersionInfoProductName={#MyAppName}
VersionInfoDescription={#MyAppName} 安装程序

OutputDir=..\dist
OutputBaseFilename=CampusTodo-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=force
RestartApplications=no
UninstallDisplayName={#MyAppName}

[Languages]
Name: "cn"; MessagesFile: "ChineseSimplified.isl"

[Files]
Source: "..\_build\CampusTodo\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userdesktop}\校园待办"; Filename: "{sys}\wscript.exe"; Parameters: """{app}\{#LaunchVbs}"""; WorkingDir: "{app}"; Comment: "校园通知智能待办"
Name: "{group}\校园待办"; Filename: "{sys}\wscript.exe"; Parameters: """{app}\{#LaunchVbs}"""; WorkingDir: "{app}"
Name: "{group}\使用说明"; Filename: "{app}\使用说明.txt"
Name: "{group}\卸载校园待办"; Filename: "{uninstallexe}"

[Run]
Filename: "{sys}\wscript.exe"; Parameters: """{app}\{#LaunchVbs}"""; Description: "立即启动校园待办"; Flags: postinstall nowait shellexec

[UninstallDelete]
Type: filesandordirs; Name: "{app}\data"
Type: files; Name: "{app}\NapCat\uin.txt"
Type: files; Name: "{app}\NapCat\config\onebot11_*.json"
Type: files; Name: "{app}\NapCat\config\napcat_*.json"
Type: files; Name: "{app}\NapCat\config\napcat_protocol_*.json"
Type: filesandordirs; Name: "{app}\NapCat\cache"
