; ============================================================
;  Inno Setup 6 简体中文语言包（手写版）
;  覆盖安装/卸载主流程，未覆盖项自动回退英文
; ============================================================

[LangOptions]
LanguageName=简体中文
LanguageID=$0804
LanguageCodePage=936
DialogFontName=Microsoft YaHei
DialogFontSize=9
WelcomeFontName=Microsoft YaHei
WelcomeFontSize=12
TitleFontName=Microsoft YaHei
TitleFontSize=29
CopyrightFontName=Microsoft YaHei
CopyrightFontSize=8

[Messages]
; ---------- 标题 ----------
SetupAppTitle=安装程序
SetupWindowTitle=安装 - %1
UninstallAppTitle=卸载
UninstallAppFullTitle=卸载 %1
InformationTitle=提示
ConfirmTitle=确认
ErrorTitle=错误

; ---------- 按钮 ----------
ButtonBack=< 上一步(&B)
ButtonNext=下一步(&N) >
ButtonInstall=安装(&I)
ButtonFinish=完成(&F)
ButtonCancel=取消
ButtonBrowse=浏览(&R)...
ButtonWizardBrowse=浏览(&R)...
ButtonStopDownload=停止下载(&S)
ButtonStopExtraction=停止解压(&S)
BrowseDialogTitle=选择文件夹
BrowseDialogLabel=在下面的列表中选择一个文件夹，然后点击"确定"。
SelectDiskLabel2=请插入磁盘 %1 并点击"确定"。%n%n如果此磁盘中的文件在下面显示的文件夹之外，请输入正确的路径或点击"浏览"。
ButtonHelp=帮助(&H)
ButtonNewFolder=新建文件夹(&M)
ButtonYes=是(&Y)
ButtonNo=否(&N)
ButtonOK=确定
ButtonYesToAll=全部是(&A)
ButtonNoToAll=全部否(&L)

; ---------- 欢迎页 ----------
WelcomeLabel1=欢迎使用 [name] 安装向导
WelcomeLabel2=现在将安装 [name/ver] 到您的电脑。%n%n建议关闭其他正在运行的程序后继续，这样可以避免重启电脑。

; ---------- 许可协议 ----------
WizardLicense=许可协议
LicenseLabel=继续之前请阅读以下重要信息。
LicenseLabel3=请阅读以下许可协议。安装本软件前，您必须接受此协议。
LicenseAccepted=我接受此协议(&A)
LicenseNotAccepted=我不接受此协议(&D)

; ---------- 选择目标目录 ----------
WizardSelectDir=选择安装位置
SelectDirDesc=您想将 [name] 安装到哪里？
SelectDirLabel3=安装程序将把 [name] 安装到以下文件夹。
SelectDirBrowseLabel=点击"下一步"继续。如果您想选择其他文件夹，请点击"浏览"。
DiskSpaceMBLabel=至少需要 [mb] MB 的可用磁盘空间。
CannotInstallToNetworkDrive=安装程序无法安装到网络驱动器。
CannotInstallToUNCPath=安装程序无法安装到 UNC 路径。
InvalidPath=您必须输入完整的路径，包括驱动器号（例如 C:\APP）。
PathExists=文件夹"%1"已存在。是否安装到此文件夹？%n%n这样可能会覆盖已有的文件。
PathExistsOk=继续
PathDoesntExist=指定的路径"%1"不存在。
CantCreateDir=无法创建文件夹：%n%n%1
DirNameTooLong=文件夹名太长。
InvalidDirName=文件夹名无效。
BadDirName31=文件夹名中不能包含字符"\"。
BadDirName32=文件夹名中不能包含任何以下字符：%1

; ---------- 开始菜单 ----------
WizardSelectProgramGroup=选择开始菜单文件夹
SelectProgramGroupDesc=您想将程序的快捷方式放在哪里？
SelectProgramGroupLabel=安装程序将在以下开始菜单文件夹中创建程序的快捷方式。
SelectStartMenuFolder=开始菜单文件夹
SelectStartMenuFolderBrowseLabel=点击"下一步"继续。如果您想选择其他文件夹，请点击"浏览"。
NoProgramGroupCheck2=不创建开始菜单文件夹(&D)
ProgramGroupDesc=开始菜单文件夹

; ---------- 附加任务 ----------
WizardSelectTasks=选择附加任务
SelectTasksDesc=您想执行哪些附加任务？
SelectTasksLabel2=安装程序将在安装 [name] 时执行以下附加任务。如果您不想执行某个任务，请取消勾选。

; ---------- 准备安装 ----------
WizardReady=准备安装
ReadyLabel1=安装程序现在已准备好在您的电脑上安装 [name]。
ReadyLabel2a=点击"安装"开始安装，或者如果您想检查或更改设置，请点击"上一步"。
ReadyLabel2b=点击"安装"开始安装。
ReadyMemoDir=安装位置：
ReadyMemoGroup=开始菜单文件夹：
ReadyMemoTasks=附加任务：

; ---------- 安装中 ----------
WizardPreparing=正在准备安装
PreparingDesc=安装程序正在准备安装 [name]。
PreparingLabel=正在准备安装...
ExtractingLabel=正在解压文件...
WizardInstalling=正在安装
InstallingLabel=安装程序正在您的电脑上安装 [name]，请稍候...

; ---------- 完成 ----------
WizardFinished=安装完成
FinishedHeadingLabel=[name] 安装完成
FinishedLabel=安装程序已完成 [name] 的安装。%n%n点击"完成"退出。
FinishedLabelNoIcons=安装程序已完成 [name] 的安装。%n%n点击"完成"退出。
FinishedRestartLabel=要完成 [name] 的安装，必须重启电脑。是否现在重启？
FinishedRestartMessage=要完成 [name] 的安装，必须重启电脑。%n%n是否现在重启？
ClickFinish=点击"完成"退出安装程序。
RunEntryExec=运行 %1
RunEntryShellExec=打开 %1

; ---------- 卸载 ----------
WizardUninstalling=正在卸载
UninstallingLabel=安装程序正在从您的电脑上卸载 %1，请稍候...
UninstallStatusLabel=正在从您的电脑上删除 %1，请稍候...
StatusUninstalling=正在卸载 %1...
ConfirmUninstall=您确定要完全移除 %1 及其所有组件吗？

; ---------- 通用 ----------
SetupLdrStartupMessage=%1 将安装到您的电脑。是否继续？
SetupAlreadyRunning=安装程序已在运行。
UninstallAppRunningError=%1 正在运行。请先关闭它，然后重新卸载。
AppRunningError=%1 正在运行。请先关闭它，然后重新安装。
ExitSetupTitle=退出安装
ExitSetupMessage=安装尚未完成。如果现在退出，程序将不会被安装。%n%n确定要退出吗？
ConfirmDeleteSharedFileTitle=删除共享文件？
ConfirmDeleteSharedFile2=系统指示以下共享文件已不再被任何程序使用。是否要删除这些文件？%n%n如果有其他程序仍在使用这些文件，删除后那些程序可能会出错。如果您不确定，请选择"否"。

; ---------- 文件操作 ----------
ErrorCopying=复制文件时出错：%n%n%1%n%n点击"重试"重试，或"取消"跳过此文件。
ErrorCreatingDir=安装程序无法创建文件夹"%1"
ErrorTooManyFilesInDir=无法在文件夹"%1"中创建文件，因为其中文件过多
ErrorChangingAttr=更改文件属性时出错：%n%n%1%n%n点击"重试"重试，或"取消"跳过此文件。
ErrorCreatingTemp=安装程序无法在目标文件夹中创建文件。
ErrorReadingSource=读取文件时出错：%n%n%1%n%n点击"重试"重试，或"取消"跳过此文件。
ErrorCopyingSource=错误

; ---------- 其他 ----------
UninstallUnsupportedArch=安装程序无法运行，因为您的系统不支持此版本。
AboutSetupMenuItem=关于安装程序(&A)...
AboutSetupTitle=关于安装程序
AboutSetupMessage=%1 版本 %2%n%3%n%nInno Setup 主页：%4
AboutSetupNote=由 Inno Setup 制作。
TranslatorNote=简体中文语言包（手写）

; ---------- 应用占用（重装/升级时出现） ----------
ApplicationsFound=以下程序正在使用安装程序需要更新的文件。建议允许安装程序自动关闭这些程序。
ApplicationsFound2=以下程序正在使用安装程序需要更新的文件。建议允许安装程序自动关闭它们。安装完成后，安装程序会尝试重新启动这些程序。
CloseApplications=自动关闭这些程序(&A)
DontCloseApplications=不关闭这些程序(&D)
ErrorCloseApplications=安装程序无法自动关闭所有程序。建议手动关闭这些程序后再继续。
StatusRestartingApplications=正在重新启动程序...
SetupAppRunningError=检测到 %1 正在运行。%n%n请先关闭它的所有实例，然后点「确定」继续，或点「取消」退出。
YesRadio=是，现在重启电脑(&Y)
NoRadio=否，稍后我自己重启(&N)
PrepareToInstallNeedsRestart=安装程序必须重启电脑。重启后请重新运行安装程序以完成 [name] 的安装。%n%n是否现在重启？
PreviousInstallNotCompleted=之前的安装/卸载未完成，需要重启电脑才能继续。%n%n重启后请重新运行安装程序。
ErrorRestartingComputer=安装程序无法重启电脑，请手动操作。
UninstalledAndNeedsRestart=要完成 %1 的卸载，必须重启电脑。%n%n是否现在重启？
DirExistsTitle=文件夹已存在
DirExists=以下文件夹：%n%n%1%n%n已经存在。是否仍要安装到这个文件夹？
FileExists2=文件已存在。
CannotInstallToUNC=安装程序无法安装到 UNC 路径。
NotOnThisPlatform=此程序无法在 %1 上运行。
SetupFileMissing=安装文件 %1 丢失。请从原始安装程序重新安装。
SetupFileCorrupt=安装文件已损坏。
InvalidParameter=安装程序命令行参数无效：%n%n%1
WindowsVersionNotSupported=此程序不支持您当前运行的 Windows 版本。
AbortRetryIgnoreSelectAction=请选择操作
AbortRetryIgnoreRetry=重试(&T)
AbortRetryIgnoreIgnore=忽略错误并继续(&I)
AbortRetryIgnoreCancel=取消安装
FileExistsSelectAction=请选择操作
ExistingFileReadOnlyRetry=去除只读属性并重试(&R)
ExistingFileReadOnly2=现有文件为只读，无法替换。
ExistingFileNewerSelectAction=请选择操作
ExistingFileNewer2=现有文件比安装程序要复制的文件更新。%n%n保留现有文件可能更安全。
ExistingFileNewerOverwrite=替换现有文件(&O)
ExistingFileNewerKeepExisting=保留现有文件（推荐）(&K)
FileAbortRetryIgnoreIgnoreNotRecommended=忽略错误并继续（不推荐）(&I)
ErrorFileHash1=文件校验失败：%1
ErrorFileHash2=文件校验值无效：期望 %1，实际 %2
ErrorFileSize=文件大小无效：期望 %1，实际 %2
ErrorProgress=进度值无效：%1 / %2
CannotContinue=安装程序无法继续。请点「取消」退出。
StopDownload=确定要停止下载吗？
ErrorDownloadAborted=下载已中止
ErrorDownloadFailed=下载失败：%1 %2
ErrorExtractionAborted=解压已中止
ErrorExtractionFailed=解压失败：%1
ExtractionLabel=正在解压附加文件...
StopExtraction=确定要停止解压吗？