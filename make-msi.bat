@echo off
setlocal EnableExtensions DisableDelayedExpansion
rem Put beside the built Lumen VPN.exe. Requires WiX v4 or newer on PATH.
rem Optional first argument: MSI version (default 1.0.0).
set "ROOT=%~dp0"
set "EXE=%ROOT%Lumen VPN.exe"
if not exist "%EXE%" set "EXE=%ROOT%LumenVPN.exe"
if not exist "%EXE%" (
    echo Build Lumen VPN.exe first, then put this script beside it.
    exit /b 1
)
where wix >nul 2>nul
if errorlevel 1 (
    echo WiX v4 or newer was not found on PATH. Install WiX, then run again.
    exit /b 1
)
set "VERSION=1.0.0"
if not "%~1"=="" set "VERSION=%~1"
set "LUMEN_MSI_VERSION=%VERSION%"
powershell -NoProfile -Command "$v=$env:LUMEN_MSI_VERSION; if($v -notmatch '^\d{1,3}\.\d{1,3}\.\d{1,5}$'){exit 1}; $p=$v.Split('.'); if([int]$p[0] -gt 255 -or [int]$p[1] -gt 255 -or [int]$p[2] -gt 65535){exit 1}" >nul 2>nul
if errorlevel 1 (
    echo Invalid version. Use major.minor.build, for example 1.0.1.
    exit /b 1
)
set "WORK=%TEMP%\lumen-msi-%RANDOM%-%RANDOM%"
if exist "%WORK%" (
    echo Temporary folder collision. Run again.
    exit /b 1
)
mkdir "%WORK%"
if errorlevel 1 exit /b 1
copy /b /y "%EXE%" "%WORK%\Lumen VPN.exe" >nul
if errorlevel 1 goto failed
>"%WORK%\installer.wxs" (
    echo ^<Wix xmlns="http://wixtoolset.org/schemas/v4/wxs"^>
    echo   ^<Package Name="Lumen VPN" Manufacturer="Lumen VPN" Version="$^(var.LumenVersion^)" UpgradeCode="4BD473A6-1F16-4CCB-A11C-01B784115EC5" Scope="perMachine" Compressed="yes"^>
    echo     ^<MajorUpgrade DowngradeErrorMessage="A newer version of Lumen VPN is already installed." /^>
    echo     ^<MediaTemplate EmbedCab="yes" /^>
    echo     ^<Icon Id="LumenIcon.exe" SourceFile="Lumen VPN.exe" /^>
    echo     ^<Property Id="ARPPRODUCTICON" Value="LumenIcon.exe" /^>
    echo     ^<StandardDirectory Id="ProgramMenuFolder" /^>
    echo     ^<StandardDirectory Id="ProgramFiles64Folder"^>
    echo       ^<Directory Id="INSTALLFOLDER" Name="Lumen VPN"^>
    echo         ^<Component Id="LumenExecutable" Guid="*"^>
    echo           ^<File Id="LumenExecutableFile" Source="Lumen VPN.exe" KeyPath="yes"^>
    echo             ^<Shortcut Id="LumenStartMenuShortcut" Directory="ProgramMenuFolder" Name="Lumen VPN" Advertise="yes" WorkingDirectory="INSTALLFOLDER" Icon="LumenIcon.exe" /^>
    echo           ^</File^>
    echo         ^</Component^>
    echo       ^</Directory^>
    echo     ^</StandardDirectory^>
    echo     ^<Feature Id="MainFeature" Title="Lumen VPN" Level="1"^>
    echo       ^<ComponentRef Id="LumenExecutable" /^>
    echo     ^</Feature^>
    echo   ^</Package^>
    echo ^</Wix^>
)
if errorlevel 1 goto failed
wix build -arch x64 -bindpath "%WORK%" -d "LumenVersion=%VERSION%" "%WORK%\installer.wxs" -o "%WORK%\Lumen VPN.msi"
if errorlevel 1 goto failed
if not exist "%WORK%\Lumen VPN.msi" goto failed
move /y "%WORK%\Lumen VPN.msi" "%ROOT%Lumen VPN.msi" >nul
if errorlevel 1 goto failed
rmdir /s /q "%WORK%"
echo Built: "%ROOT%Lumen VPN.msi"
echo To sign it: powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%sign.ps1" -FilePath "Lumen VPN.msi"
exit /b 0
:failed
rmdir /s /q "%WORK%"
echo MSI build failed. Any previous Lumen VPN.msi was kept.
exit /b 1
