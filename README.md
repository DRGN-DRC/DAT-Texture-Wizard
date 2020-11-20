# DAT-Texture-Wizard (DTW)
This program allows for disc (ISO/GCM) management of GameCube games, as well as texture exporting and importing, particularly for Super Smash Bros. Melee and 20XXHP. The internal file structure of HAL DAT files can also be analyzed and edited.

Disc management features include adding/replacing/deleting files and/or folders (including replacing files that are larger than the original), building a disc from root files, editing the game names (short/long titles, descriptions, etc.), replacing the disc banner, and more.

You can find the official thread here: [DAT Texture Wizard on SmashBoards.com](https://smashboards.com/threads/dat-texture-wizard-current-version-6-1.373777/)

# Installation & Setup
In order to run or compile this program, you'll need to install Python 2 and a few modules. Any version of python between 2.7.12 up to the latest 2.7 should work.

After installing Python, the following Python modules need to be installed:

    psutil
    Pillow      (internally referred to as PIL)
    cx-Freeze   (if you want to compile)

The easiest way to install these is with pip, which comes with Python by default. It's found in C:\Python27\Scripts; which you'll need to navigate to if you didn't install Python to your PATH variable (which is an option when you install it). Once you're ready to run pip commands, you can install the above modules by running 'pip install [moduleName]' for each one. All other dependancies are included in the repo.

cx-Freeze will need to be less than version 6 for compatibility with Python 2.7. I recommend v5.1.1, as that's what I've been using. To install this specific version, you can use "pip install cx-Freeze==5.1.1"

# Compilation
This program uses cx-Freeze to compile, using the setup.py file.

To compile the program, you just need to run the "Build Executable.bat" batch script, which is a simple wrapper for setup.py.

The batch script will ask if you'd like to preserve console display for the finished executable; if enabled (preserved), a console window will be opened alongside the GUI when running the program, which will contain simple messages for some features, as well as error messages. If disabled, errors will still be logged in a generated "Error log.txt" file in the program's root.

Once compiled, the program will be found in the 'build' folder, and will be renamed to 'DAT Texture Wizard - v[version] ([x86|x64])'.
