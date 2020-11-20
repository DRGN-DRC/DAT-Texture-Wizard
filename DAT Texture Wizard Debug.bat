:: Opens a command prompt window before running the program.
:: Otherwise, if running the python script directly, it will 
:: exit and close immediately if any errors are encountered.

@echo off

python "%~dp0DAT Texture Wizard.py" %*

if [%ERRORLEVEL%]==[0] goto eof

pause > nul & Press any key to exit. . .