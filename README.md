# DAT-Texture-Wizard (DTW)
This program allows for disc (ISO/GCM) management of GameCube games, as well as texture exporting and importing, particularly for Super Smash Bros. Melee and 20XX HP. The internal file structure of HAL DAT files (such as stage/menu/character files) can also be deeply analyzed and edited.

Disc management features include adding/replacing/deleting files and/or folders (including replacing files that are larger than the original), building a disc from root files, editing the game names (short/long titles, descriptions, etc.), replacing the disc banner, and more.

You can find the official thread here: [DAT Texture Wizard on SmashBoards.com](https://smashboards.com/threads/dat-texture-wizard-current-version-6-1.373777/)

The structure of this program's code is largely a functional style (i.e. built mostly using just strait functions). Certainly some parts would be better suited as objects, with classes and their own personal methods. And I know there are some things that could be done more efficiently. A strong factor that led to some matters such as these is the fact that this is a really old project, built when I was first learning Python. :P But going forward I'll be occasionally refactoring parts of this program, and rewriting key components of it as I incorporate them into future projects. Let me know if there's anything you'd like to see broken out into a separate project, like HSD DAT file/structure objects, the texture codec, etc.

## Installation & Setup (Windows)
In order to run or compile this program, you'll need to install Python 2 and a few modules. Any version of python between 2.7.12 up to the latest 2.7 should work.

After installing Python, the following Python modules need to be installed:

    psutil
    Pillow      (internally referred to as PIL)
    cx-Freeze   (if you want to compile)

The easiest way to install these is with pip, which comes with Python by default. It's found in C:\Python27\Scripts; which you'll need to navigate to if you didn't install Python to your PATH variable (which is an option when you install it). Once you're ready to run pip commands, you can install the above modules by running 'pip install [moduleName]' for each one. All other dependencies are included in the repo.

cx-Freeze will need to be less than version 6 for compatibility with Python 2.7. I recommend v5.1.1, as that's what I've been using. To install this specific version, you can use "pip install cx-Freeze==5.1.1"

## Building (Windows)
This program uses cx-Freeze to compile, using the setup.py file. To compile the program, you just need to run the "Build Executable.bat" batch script, which is a simple wrapper for setup.py.

The batch script will ask if you'd like to preserve console display for the finished executable; if enabled (preserved), a console window will be opened alongside the GUI when running the program, which will contain simple messages for some features, as well as error messages. If disabled, errors will still be logged in a generated "Error log.txt" file in the program's root. Most users probably won't find a lot of use in the console, but it's there anyway just in case.

Once compiled, the program will be found in the 'build' folder, and will be renamed to 'DAT Texture Wizard - v[version] ([x86|x64])'.

## Credits, Copyright and License
* **wimgt**  ( [Website](https://szs.wiimm.de/wimgt/) | [GitHub](https://github.com/Wiimm/wiimms-szs-tools) )    `- Used for CMPR (type _14) texture encoding`
    - Copyright (c) by Wiimm (2011)
    - GNU GPL v2 or later
* **pngquant** ( [Website](https://pngquant.org/) | [GitHub](https://github.com/kornelski/pngquant) )    `- Used in palette and CSP trim color generation`
    - Copyright (c) by Kornel Lesiński (2009-2018), Greg Roelofs (1997-2002), and Jef Poskanzer (1989, 1991)
    - Licensed under GPL v3 or later
* **xxHash**  ( [PyPI](https://pypi.org/project/xxhash/) | [GitHub](https://github.com/ifduyue/python-xxhash) )      `- Used for Dolphin hash generation`
    - Copyright (c) by Yue Du (2014-2020)
    - Licensed under [BSD 2-Clause License](http://opensource.org/licenses/BSD-2-Clause)
