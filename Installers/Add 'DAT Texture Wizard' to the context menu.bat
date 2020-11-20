@echo off
title PNG to-from TPL Converter Installation
cls
echo.

	:: Check for the location of the Send To folder.

set sendToFolder="%SystemDrive%%HOMEPATH%\AppData\Roaming\Microsoft\Windows\SendTo"
set subfolder=shortcuts\7

if exist %sendToFolder% goto :FoundSendToFolder :: OS is Windows 7, 8, or 8.1

set sendToFolder="%userprofile%\SendTo"
set subfolder=shortcuts\xp

if exist %sendToFolder% goto :FoundSendToFolder :: OS is Windows XP

echo.
echo Could not find the 'Send To' folder.

echo. && echo Press any key to exit. . . && pause > nul && exit 1


:FoundSendToFolder

	:: Copy the script shortcut (.lnk) file to the system's 'Send To' folder.

xcopy "%subfolder%\DAT Texture Wizard.lnk" %sendToFolder% /y > nul
echo.
if "%ErrorLevel%"=="0" goto :ShortcutCopied
echo There was a problem adding the shortcut file to the 'Send To' folder (xcopy error code %ErrorLevel%).
echo. && echo Press any key to exit. . . && pause > nul && exit 2


:ShortcutCopied

	:: Create a [hidden] redirection script for the shortcut to point to.
	:: A shortcut (.lnk) file is used so that a file extension isn't shown
	:: in the context menu. And a .bat is used so that a dynamic path to
	:: the converter script can be created and added into it. (Shortcuts 
	:: themselves cannot easily be dynamically created or edited from a batch 
	:: script such as this, especially without the use of vbscript and/or cscript.)
	:: For DAT Texture Wizard, the shortcut should be configured to start the
	:: batch file minimized. And the command is "start" rather than "call", so
	:: that the batch file ends immediately after execution (since it's not needed.)

set thisDir=%~dp0
cd /d "%thisDir%.."
set scriptDir=%cd%
cd /d %sendToFolder%

if exist OverwriterRedirection.bat del OverwriterRedirection.bat /ah

echo start "" "%scriptDir%\DAT Texture Wizard.exe" %%* > OverwriterRedirection.bat

if exist OverwriterRedirection.bat goto :RedirectionScriptCreated
echo There was a problem creating the redirection script in the 'Send To' folder.
echo. && echo Press any key to exit. . . && pause > nul && exit 3


:RedirectionScriptCreated

:: Make the redirection script hidden so it doesn't show in the context menu.

attrib OverwriterRedirection.bat +h

echo 'Send To' context menu shortcut added.
echo.
echo.
echo Installation complete!
echo.
echo. && echo Press any key to exit. . . && pause > nul && exit 0