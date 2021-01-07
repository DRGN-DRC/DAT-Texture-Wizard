# Created by Daniel R. Cappel ("DRGN")
# Script version: 2.3

programName = "DAT Texture Wizard"
mainScript = __import__( "DAT Texture Wizard" ) # This import method is used in order to import a file with spaces in its name.

import shutil
import sys, os
from cx_Freeze import setup, Executable

# Determine whether the host environment is 64 or 32 bit.
if sys.maxsize > 2**32: environIs64bit = True
else: environIs64bit = False

# Dependencies are typically automatically detected, but they might need fine tuning.
buildOptions = dict(
	packages = [], 
	excludes = [], 
	include_files=[
		'bin',
		'imgs',
		'Installers',
		'PNG to-from TPL.bat',
		'Program Usage.txt',
		'tk', # Includes a needed folder for drag 'n drop functionality.
	])

if sys.argv[2].startswith( 'y' ):
	base = 'Console'
else:
	base = 'Win32GUI' if sys.platform == 'win32' else None

# Strip off extra command line arguments, because setup isn't expecting them and will throw an invalid command error.
sys.argv = sys.argv[:2]

# Normalize the version string for setup ('version' below must be a string, with only numbers or dots)
simpleVersion = '.'.join( [char for char in mainScript.programVersion.split('.') if char.isdigit()] )

setup(
	name=programName,
	version = simpleVersion,
	description = 'Texture and Disc Manager for SSBM and other GC games',
	options = dict( build_exe = buildOptions ),
	executables = [
		Executable(
			"DAT Texture Wizard.py", 
			icon='appIcon5.ico', # For the executable icon. "appIcon.png" is for the running program's window icon.
			base=base)
		]
	)

# Perform file/folder renames
print '\nCompilation complete.'

# Get the name of the new program folder that was created in '\build\'
scriptHomeFolder = os.path.abspath( os.path.dirname(sys.argv[0]) )
programFolder = ''
for directory in os.listdir( scriptHomeFolder + '\\build' ):
	if directory.startswith( 'exe.' ):
		programFolder = directory
		break
else: # The above loop didn't break; program folder not found
	print 'Unable to locate the new program folder!'
	exit( 1 ) # Program exit code set to 1

# Rename the program folder
if environIs64bit:
	newFolderName = '{} - v{} (x64)'.format( programName, mainScript.programVersion )
else:
	newFolderName = '{} - v{} (x86)'.format( programName, mainScript.programVersion )
oldFolderPath = os.path.join( scriptHomeFolder, 'build', programFolder )
newFolderPath = os.path.join( scriptHomeFolder, 'build', newFolderName )
os.rename( oldFolderPath, newFolderPath )
print 'New program folder successfully created and renamed to "' + newFolderName + '".'

# Open the new folder
os.startfile( newFolderPath )