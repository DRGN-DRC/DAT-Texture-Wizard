@echo off
cls

echo. & echo.
echo Are you sure you'd like to compile (y/n)?

set /p confirmation=
if not [%confirmation%]==[y] goto:abort

echo. & echo.
echo Preserve console display (y/n)?

set /p useConsole=

echo. & echo.
python setup.py build %useConsole%

echo. & echo.
echo Exit Code: %ERRORLEVEL%
if not [%ERRORLEVEL%]==[0] goto :error


echo.
echo      Build complete!  Press any key to exit.
pause > nul
goto: eof


:error
echo.
echo      An error has occurred. Press any key to exit.
pause > nul
goto: eof


:abort
echo.
echo      Operation aborted. Press any key to exit.
pause > nul