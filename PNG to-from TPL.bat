@echo off
cls
echo.

echo Script created by DRGN (Durgan) of Smashboards.
echo Running version 2.4, from this location:
echo %~dp0
echo.

:: Find the discussion and usage thread here: 
:: http://smashboards.com/threads/new-tools-for-texture-hacking.373777/
::
:: This script converts images between TPL and PNG file formats, using 
:: Wiimms SZS Tool's "wimgt" (v1.35, revision 5394), found here:
:: http://szs.wiimm.de/download.html#os-cygwin
:: 
:: To use this script, select the files you wish to convert, and then 
:: drag them onto this file. If they are PNG format, they will be 
:: converted to the appropriate TPL format (assuming the _x.png naming 
:: convention for the image type is intact). If they are in TPL format, 
:: they will be converted to PNG. 
::
:: By default, this process will not overwrite existing images (you'll 
:: have to delete or rename the existing destination file(s) before you 
:: drag-and-drop). To change this so that it does overwrite, change the 
:: value below to yes.
::
set overwrite=no
::
:: For converting PNG textures with palettes (i.e. texture types _8, _9,
:: _10, and _a), in order to set the type of palette formatting, it 
:: needs to be known whether the original texture contains transparency 
:: or not. If the PNG you're trying to convert has transparency, set the 
:: value below to yes (the default, since it's common and used for CSPs),
:: otherwise set it to no.
::
set sourceHasTransparency=yes
::
:: If you'd like this script to wait before exiting, so you can see the 
:: processing taking place (or any errors), change the value below to yes.
::
set waitToExit=no
::
:: You may opt to install Wiimm's Tools, in which case you would no 
:: longer need to keep this script in the same directory as the Wiimms 
:: Files folder. In fact, after installation, you could delete the folder 
:: if you'd like. To install Wiimm's Tools, run the "windows-install.exe" 
:: file found in the Wiimms Files folder, and then restart your computer.
::


:: - Program Start -

:: If this script was run with no files, skip to 
:: the error & usage message, and then exit.

if [%1]==[] goto :UsageNotes

if %overwrite%==n set overwriteOption=
if %overwrite%==no set overwriteOption=
if %overwrite%==y set overwriteOption= --overwrite
if %overwrite%==yes set overwriteOption= --overwrite

:: Check if the Wiimms Files folder is present. If it
:: isn't, the script will assume wimgt is installed
:: on the system.

set wimgtPath=wimgt
if exist "%~dp0\bin\wimgt" set wimgtPath="%~dp0\bin\wimgt\wimgt.exe"

:: Iterate through the loop below for each file 
:: given to (dragged onto) this script.

:loop
echo.

:: If the current file is a PNG, convert it to a 
:: TPL. If it's a TPL, convert it to PNG. If it's
:: not recognized as either, skip it.

if /I [%~x1]==[.PNG] goto :convertToTPL
:: else is TPL or something else

if /I [%~x1]==[.TPL] goto :convertToPNG
:: else is not TPL (or PNG for that matter)

echo.
echo The following input file doesn't appear 
echo to be PNG or TPL:
echo.
echo %~nx1
echo.
echo Skipping...
echo.
pause

goto :iterationEnd


:convertToPNG

%wimgtPath% copy %1 "%~dpn1.png"%overwriteOption%

goto :iterationEnd


:convertToTPL

set "filename=%~n1"**

set encoding=notSet

if %filename:~-3,1%==_ goto :DoubleDigitTypes

set imageType=%filename:~-2%

if %imageType%==_0 set encoding=i4

if %imageType%==_1 set encoding=i8

if %imageType%==_2 set encoding=ia4

if %imageType%==_3 set encoding=ia8

if %imageType%==_4 set encoding=rgb565

if %imageType%==_5 set encoding=rgb5a3

if %imageType%==_6 set encoding=rgba32

if %imageType%==_8 (
	set encoding=c4
	goto :IncludePaletteEncoding
)

if %imageType%==_9 (
	set encoding=c8
	goto :IncludePaletteEncoding
)

if %imageType%==_a (
	set encoding=c14x2
	goto :IncludePaletteEncoding
)

if %imageType%==_e set encoding=cmpr

goto :EncodingSet


:DoubleDigitTypes

set imageType=%filename:~-3%

if %imageType%==_10 (
	set encoding=c14x2
	goto :IncludePaletteEncoding
)

if %imageType%==_14 set encoding=cmpr

goto :EncodingSet


:IncludePaletteEncoding

if %sourceHasTransparency%==n set encoding=%encoding%.P-RGB565
if %sourceHasTransparency%==no set encoding=%encoding%.P-RGB565
if %sourceHasTransparency%==y set encoding=%encoding%.P-RGB5A3
if %sourceHasTransparency%==yes set encoding=%encoding%.P-RGB5A3


:EncodingSet

if %encoding%==notSet goto :NoImageTypeFound

%wimgtPath% copy %1 "%~dpn1.tpl"%overwriteOption% -x tpl.%encoding%

goto :iterationEnd


:: Skip PNGs with missing image types....
:NoImageTypeFound

echo.
echo An image type wasn't found for the following input file:
echo.
echo %~nx1
echo.
echo The type should be shown in the filename, just before the extension. 
echo For example, for "GALE01_58408ead_3.png", the image type would be 
echo "_3". If you want to rename your images, it is best to only change 
echo or add to the portion of the name that says "GALE01" in the example
echo above.
echo.
echo Skipping this file...
echo.
pause

:: Advance to the next file in the arguments list
:: and start the next iteration if more are present.
:iterationEnd

shift
if not [%1]==[] goto loop


if %waitToExit%==no goto :eof

echo.
echo Press any key to exit . . .
pause > nul

goto :eof


:: Display the following if the script was run without arguments/files.
:UsageNotes

echo.
echo To use this script, select the files you wish to convert and then drag 
echo them onto the icon for this file (not into this window). If they are 
echo PNG format, they will be converted to the appropriate TPL format 
echo (assuming the _x.png naming convention is intact). If they are in 
echo TPL format, they will be converted to PNG.
echo.
echo Edit this file to see more info and other options.
echo.
echo For converting PNG textures with palettes, i.e. texture types _8, _9, 
echo _10, and _a, this script needs to know whether the original texture 
echo contains transparency or not. By default, the script assumes they do 
echo (because that type is more common, and are used for CSPs). To change this, 
echo edit this file and look for the "sourceHasTransparency" option, found 
echo near the beginning of the file.
echo.
echo Press any key to exit . . .

pause > nul