# Created by Daniel R. Cappel ("DRGN")
# Script version: 2.1

programName = "DAT Texture Wizard"
programVersion = '6.1.1'
#filesToUpdate = ( 'DAT Texture Wizard.py', 'GuiSubComponents.py', 'hsdFiles.py', 'hsdStructures.py', 'RenderEngine.py', 'tplCodec.py' )

import shutil
import sys, os
from cx_Freeze import setup, Executable

# Determine whether the host environment is 64 or 32 bit.
if sys.maxsize > 2**32: environIs64bit = True
else: environIs64bit = False

# Copy required script files to the compilation folder
# try:
# 	print 'Updating required scripts...:', filesToUpdate
# 	print ''
# 	compilationFolder = os.path.abspath( os.path.dirname(sys.argv[0]) )
# 	mainScriptsFolder = os.path.dirname( compilationFolder ) # Expecting it to be one folder up
# 	for script in filesToUpdate:
# 		sourcePath = os.path.join( mainScriptsFolder, script )
# 		destination = os.path.join( compilationFolder, script )
# 		shutil.copy2( sourcePath, destination )
# except Exception as err:
# 	print 'Error encountered while gathering required scripts:'
# 	print err
# 	exit( 1 )

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

sys.argv = sys.argv[:2] # Strip off extra arguments, because setup isn't expecting them.

setup(
	name=programName,
	version = programVersion,
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

# Get the name of the new program folder that will be created in '\build\'
scriptHomeFolder = os.path.abspath( os.path.dirname(sys.argv[0]) )
programFolder = ''
for directory in os.listdir( scriptHomeFolder + '\\build' ):
	if directory.startswith( 'exe.' ):
		programFolder = directory
		break

# Rename the new program folder
if not programFolder: print 'Unable to locate the new program folder!'
else:
	newFolderName = programName + ' - v' + programVersion

	if environIs64bit:
		newFolderName += ' (x64)'
	else:
		newFolderName += ' (x86)'
	oldFolderPath = os.path.join( scriptHomeFolder, 'build', programFolder )
	newFolderPath = os.path.join( scriptHomeFolder, 'build', newFolderName )

	os.rename( oldFolderPath, newFolderPath )
	print 'New program folder successfully created and renamed to "' + newFolderName + '".'

	# Open the new folder
	os.startfile( newFolderPath )