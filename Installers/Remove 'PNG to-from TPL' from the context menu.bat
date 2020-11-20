@echo off
title PNG to-from TPL Converter Uninstallation
cls
echo.

	:: Check for the location of the Send To folder.

set sendToFolder="%SystemDrive%%HOMEPATH%\AppData\Roaming\Microsoft\Windows\SendTo"

if exist %sendToFolder% goto :FoundSendToFolder :: OS is Windows 7, 8, or 8.1

set sendToFolder="%userprofile%\SendTo"

if exist %sendToFolder% goto :FoundSendToFolder :: OS is Windows XP

echo.
echo Could not find the 'Send To' folder.

echo. && echo Press any key to exit. . . && pause > nul && exit 1


:FoundSendToFolder

	:: Remove the script shortcut (.lnk) file and redirection script 
	:: from the system's 'Send To' folder.

del "%sendToFolder%\PNG to-from TPL Converter.lnk"

del "%sendToFolder%\ConverterRedirection.bat" /ah

if not exist "%sendToFolder%\PNG to-from TPL Converter.lnk" goto :ShortcutDeleted

goto :End

:ShortcutDeleted
echo.
echo 'Send To' context menu shortcut has been removed.
echo.
echo.
echo Uninstallation complete!

:End

echo.
echo. && echo Press any key to exit. . . && pause > nul && exit