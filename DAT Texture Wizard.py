#!/usr/bin/python
# This file's encoding: UTF-8, so that non-ASCII characters can be used in strings.

							# ------------------------------------------------------------------- #
						   # ~ ~      Written by DRGN of SmashBoards (Daniel R. Cappel)        ~ ~ #
							#     -     -     -     -   [ Feb., 2015 ]   -     -     -     -      #
							 #     -     -    [ Python v2.7.12 and Tkinter 8.5 ]    -     -      #
							  # --------------------------------------------------------------- #

programVersion = '6.1.2'
# Find the official thread here: http://smashboards.com/threads/new-tools-for-texture-hacking.373777/

# Primary logic
import os 			# Various file and folder operations
import io
import sys
import png			# Only used for png.Reader(), for reading PNG files
import psutil 		# For checking running processes (checking whether temp files are in use)
import shutil			# For file copying
import subprocess		# Subprocess for communication with command line
import xxhash, array	# Both used for generating texture file names using Dolphin's naming convention
import random, struct
import multiprocessing
import math, errno, tempfile
import hsdFiles, hsdStructures
from sets import Set
from threading import Thread
from binascii import hexlify, unhexlify 	# Convert from bytearrays to strings (and vice verca via unhexlify)
from string import hexdigits 				# For checking that a string only consists of hexadecimal characters
from datetime import datetime 				# For keeping track of the recently opened files.
from tplCodec import codecBase, tplDecoder, tplEncoder, missingType, noPalette
from collections import OrderedDict

# GUI dependencies
import time 			# Used for time.sleep() (for waits) and performance testing
import tkFont
import webbrowser 		# Used to open a web page.
import RenderEngine
import Tkinter as Tk
import ttk, tkMessageBox, tkFileDialog
from Tkinter import TclError
from ctypes import c_ubyte # For image data memory management
from ScrolledText import ScrolledText
from tkColorChooser import askcolor
from PIL import Image, ImageOps, ImageTk, ImageDraw
from GuiSubComponents import (
		getWindowGeometry,
		basicWindow,
		PopupEntryWindow,
		CopyableMessageWindow,
		DisguisedEntry,
		VerticalScrolledFrame,
		ToolTip,
		HexEditEntry,
		HexEditDropdown,
		ImageDataLengthCalculator
	)

try: from cStringIO import StringIO # Preferred for performance.
except: from StringIO import StringIO

# Extras for drag-and-drop and sound effects.
from sys import argv as programArgs # Access files given (drag-and-dropped) to the program icon.
from newTkDnD import TkDND # Access files given (drag-and-dropped) onto the running program GUI.

# Output errors to an error log, since the console likely won't be available
if programArgs[0][-4:] == '.exe': # If this code has been compiled....
	sys.stderr = open( 'Error Log.txt', 'a' )
	sys.stderr.write( '\n\n:: {} :: Program Version: {} ::\n'.format(datetime.today(), programVersion) )

# Load modules for hash generation
scriptHomeFolder = os.path.abspath( os.path.dirname(programArgs[0]) ) # Can't use __file__ after freeze
sys.path.append( scriptHomeFolder + '\\bin' ) # So we can use executables from there

# For performance testing
#import timeit

# User defined settings / persistent memory.
import ConfigParser
settings = ConfigParser.SafeConfigParser()
settings.optionxform = str # Tells the settings parser to preserve case sensitivity (for camelCase).

# Define some necessary file paths
imagesFolder = scriptHomeFolder + '\\imgs'
texDumpsFolder = scriptHomeFolder + "\\Texture dumps"
settingsFile = scriptHomeFolder + '\\settings.ini'
pathToPngquant = scriptHomeFolder + '\\bin\\pngquant.exe' # For palette generation

# Supplemental Necessities
wimgtPath = scriptHomeFolder + '\\bin\\wimgt\\wimgt.exe' # For encoding type _14 textures only
if not os.path.exists( wimgtPath ): # If wimgt isn't found in the above directory, fall back to assuming that wimgt is installed to the system.
	wimgtPath = 'wimgt'

# Globals
globalDiscDetails = { #todo create a proper disc class
	'isoFilePath': '', 
	'isMelee': '', # Will be '00' '01', '02', or 'pal' if the disc's DOL is a revision of Melee
	'is20XX': '', # Empty if not 20XX; populated by the check20xxVersion function
	'gameId': '',
	'rebuildRequired': False
	}
globalDatFile = None
globalBannerFile = None

scanningDat = False
stopAndScanNewDat = False
updatingBannerFileInfo = False
stopAndReloadBannerFileInfo = False
programClosing = False
unsavedDiscChanges = []
editedDatEntries = []
editedBannerEntries = []

# Values for live updating of settings while program is running.
generalBoolSettings = {}
imageFilters = {}

# Default settings for persisent memory (saved in settings.ini file)
generalSettingsDefaults = {
	'defaultSearchDirectory': os.path.expanduser('~'),
	'hexEditorPath': '',
	'emulatorPath': '',
	'maxFilesToRemember': '6',
	'globalFontSize': '-13',
	'paddingBetweenFiles': '0x40',
	'downscalingFilter': 'lanczos', # all options: nearest, lanczos, bilinear, bicubic
	'textureExportFormat': 'png',
	'altFontColor': '#d1cede' # A shade of silver; useful for high-contrast system themes
	} # Once initialized by loadSettings, these are referenced by settings.get( 'General Settings', [settingName] )

generalBoolSettingsDefaults = { # To add more options, simply add the key to here, and create an option in the main menus for it.
	'dumpPNGs': '0',
	'deleteImageDumpsOnExit': '1',
	'autoUpdateHeaders': '1',
	'backupOnRebuild': '1',
	'showCanvasGrid': '1',
	'showTextureBoundary': '0',
	'avoidRebuildingIso': '1',
	'regenInvalidPalettes': '0',
	'useDiscConvenienceFolders': '1',
	'autoGenerateCSPTrimColors': '0',
	'cascadeMipmapChanges': '1',
	'useDolphinNaming': '0',
	'useAltFontColor': '0'
	} # Once initialized by loadSettings, these are referenced by generalBoolSettings[setting].get()

imageFiltersDefaults = {
	'widthFilter': '=|',
	'heightFilter': '=|',
	'aspectRatioFilter': '=|',
	'imageTypeFilter': '=|',
	'offsetFilter': '=|'
	}


# Lookup tables:

imageFormats = { 0:'I4', 1:'I8', 2:'IA4', 3:'IA8', 4:'RGB565', 5:'RGB5A3', 6:'RGBA8', 8:'CI4', 9:'CI8', 10:'CI14x2', 14:'CMPR' }
userFriendlyFormatList = [ '_0 (I4)', '_1 (I8)', '_2 (IA4)', '_3 (IA8)', '_4 (RGB565)', '_5 (RGB5A3)', '_6 (RGBA8)', '_8 (CI4)', '_9 (CI8)', '_10 (CI14x2)', '_14 (CMPR)' ]


# SSBM Disc tree filename lookup.

audioNameLookup = { # .sem, .hps, and .ssm files
	'opening':		"The game's Opening Movie audio",
	'smash2':		'Audio Scripts And Sound Effect Info',
	'swm_15min': 	"'Special Movie 2' audio"
}

movieNameLookup = { # Video files only (.mth); no audio with these.
	'MvHowto':		'The "How to Play" video',
	'MvOmake15':	'The 15-Minute "Special Movie"',
	'MvOpen': 		"The game's Opening Movie"
}

charNameLookup = {
	'Bo': '[Boy] Male Wireframe',
	'Ca': 'Captain Falcon',
	'Ch': 'Crazy Hand',
	'Cl': 'Child/Young Link',
	'Co': 'Common to the cast',
	'Dk': 'Donkey Kong',
	'Dr': 'Dr. Mario',
	'Fc': 'Falco',
	'Fe': '[Fire Emblem] Roy',
	'Fx': 'Fox',
	'Gk': '[GigaKoopa] GigaBowser',
	'Gl': '[Girl] Female Wireframe',
	'Gn': 'Ganondorf',
	'Gw': "Game 'n Watch",
	'Ic': 'Ice Climbers',
	'Kb': 'Kirby',
	'Kp': '[Koopa] Bowser',
	'Lg': 'Luigi',
	'Lk': 'Link',
	'Mh': 'Master Hand',
	'Mn': 'Menus Data',
	'Mr': 'Mario',
	'Ms': '[Mars] Marth',
	'Mt': 'Mewtwo',
	'Nn': '[Nana] Ice Climbers',
	'Ns': 'Ness',
	'Pc': 'Pichu',
	'Pe': 'Peach',
	'Pk': 'Pikachu',
	'Pn': '[Popo/Nana] Ice Climbers',
	'Pp': '[Popo] Ice Climbers',
	'Pr': '[Purin] Jigglypuff',
	'Sb': 'SandBag',
	'Sk': 'Sheik',
	'Ss': 'Samus',
	'Wf': 'Wolf',
	'Ys': 'Yoshi',
	'Zd': 'Zelda'
}

charColorLookup = {
	'Aq': 'aqua',
	'Bk': 'black',
	'Br': 'brown', # Unique to m-ex; not found in vanilla melee
	'Bu': 'blue',
	'Gr': 'green',
	'Gy': 'gray',
	'La': 'lavender',
	'Nr': 'neutral',
	'Or': 'orange',
	'Pi': 'pink',
	'Rd': 'red', # Unique to 20XX 4.0+ for Falcon's .usd variation
	'Re': 'red',
	'Rl': 'red', # Unique to 20XX 4.0+ for Falcon's .usd variation (red 'L')
	'Rr': 'red', # Unique to 20XX 4.0+ for Falcon's .usd variation (red 'R')
	'Wh': 'white',
	'Ye': 'yellow'
}

stageNameLookup = { # Keys should be 3 characters long.
	'Bb.': 'Big Blue',
	'Cn.': 'Corneria',
	'Cs.': "Princess Peach's Castle",
	'EF1': 'Goomba Trophy Stage',
	'EF2': 'Entei Trophy Stage',
	'EF3': 'Majora Trophy Stage',
	'Fs.': 'Fourside',
	'Fz.': 'Flat Zone',
	'Gb.': 'Great Bay',
	'Gd.': 'Jungle Japes [Garden]',
	'Gr.': 'Green Greens',
	'He.': 'All-Star Rest Area [Heal]',
	'Hr.': 'Homerun Contest',
	'I1.': 'Mushroom Kingdom',
	'I2.': 'Mushroom Kingdom II (Subcon)',
	'TIc': 'Icetop (unused stage)',
	'Im.': 'Icicle Mountain',
	'Iz.': 'Fountain of Dreams [Izumi]',
	'Kg.': 'Kongo Jungle',
	'Kr.': 'Brinstar Depths [Kraid]',
	'Mc.': 'Mute City',
	'NBa': 'Battlefield',
	'NBr': 'F-Zero Grand Prix',
	'NFg': 'Trophy Collector [Figure Get]',
	'NKr': 'Mushroom Kingdom Adventure',
	'NLa': 'Final Destination',
	'NPo': 'Pushon?',
	'NSr': 'Hyrule Maze',
	'NZr': 'Brinstar Escape Shaft [Zebes]',
	'Ok.': 'Kongo Jungle (N64)',
	'Op.': 'Dream Land (N64)',
	'Ot.': 'Onett',
	'Oy.': "Yoshi's Island (N64)",
	'Ps.': 'Pokemon Stadium',
	'Ps1': 'Pokemon Stadium - Fire Form',
	'Ps2': 'Pokemon Stadium - Grass Form',
	'Ps3': 'Pokemon Stadium - Water Form',
	'Ps4': 'Pokemon Stadium - Rock Form',
	'Pu.': 'Poke Floats [Pura]',
	'Rc.': 'Rainbow Cruise',
	'Sh.': 'Hyrule Temple [Shrine]',
	'St.': "Yoshi's Story",
	'Te.': '"TEST" (a.k.a. The Coffee Shop)',
	'Ve.': 'Venom',
	'Yt.': "Yoshi's Island",
	'Ze.': 'Brinstar [Zebes]'
}

onePlayerStages = ( 'EF1', 'EF2', 'EF3', 'He.', 'Hr.', 'NBr', 'NFg', 'NKr', 'NSr', 'NZr', 'Te.' )

specialStagesIn20XX = { # Key = file name string beginning after 'Gr'
	'C0.usd': 'Sector Z',									# 20XXHP 5.0+
	'Cs.0at': "Omega Peach's Castle",						# 20XXHP 5.0+
	'Fs.1at': 'Smashville Fourside',
	'Fs.2at': 'Moonside',									# 20XXHP 5.0+
	'Gb.0at': 'Turtle Stage',								# 20XXHP 5.0+
	'Gb.1at': 'Great Bay, Beach',							# 20XXHP 5.0+
	'Gb.hat': 'Great Bay, Hacked',
	'Gd.1at': 'Jungle Japes, Hacked (w/platform)',
	'Gd.2at': 'Jungle Japes, Omega',
	'Gr.1at': 'Green Greens, Hacked',
	'He.0at': 'Walk-Off Heal',								# 20XXHP 5.0+
	'I1.0at': "Milun's Mushroom Kingdom",					# 20XXHP 5.0+
	'I1.1at': "Porygon",									# 20XXHP 5.0+
	'I1.2at': "Shiny Porygon",								# 20XXHP 5.0+
	'Iz.gat': 'Cave of Dreams',								# 20XXHP 5.0+
	'Kg.hat': 'Kongo Jungle, Hacked',
	'NBa.2at': 'Ancient Battlefield',
	'NBa.3at': 'Battlefield Plaza',
	'NBa.4at': 'Matrix Battlefield', 						# Old 20XX
	'NBa.bat': 'Battlefield Plaza',
	'NBa.gat': 'Brawl Battlefield - Day',					# 20XXHP 5.0+
	'NBa.hat': 'Brawl Battlefield - Day (w/Castle)',		# 20XXHP 5.0+
	'NBa.iat': 'Brawl Battlefield - Void',					# 20XXHP 5.0+
	'NBa.lat': 'Brawl Battlefield',
	'NFg.0at': 'Trophy Collector (Two platforms)',
	'NFg.1at': 'Trophy Collector (Three platforms)',
	'NFg.2at': 'Trophy Collector, Omega',
	'NKr.1at': 'Mushroom Kingdom Adventure, Hacked',
	'NKr.2at': 'Mushroom Kingdom Adventure, Omega',
	'NLa.0at': 'Final Destination',
	'NLa.2at': 'Wii-U Final Destination', 					# Old 20XX
	'NLa.gat': 'Wii-U Final Destination', 					# 20XXHP 5.0+
	'NLa.hat': 'zankyou FD', 								# 20XXHP 5.0+
	'NSr.1at': 'Hyrule Maze, Hacked',
	'Ok.0at': 'Monster Island',								# 20XXHP 5.0+
	'Op.gat': 'Halberd Land',								# 20XXHP 5.0+
	'Op.kat': 'KirbyWare, Inc.',
	'Op.rat': 'Return to Dream Land',
	'Oy.hat': "Yoshi's Island (N64), Milun Hack",
	'Oy.wat': 'WarioWare, Inc.',
	'Pb.usd': 'Pokemon Stadium (Blue, No transforms)', 		# Old 20XX
	'Pg.usd': 'Indigo Stadium',								# 20XXHP 5.0+
	'Pn.usd': 'Pokemon Stadium (Blue, No transforms)',		# 20XXHP 5.0+
	'Sh.sat': 'Skyrule (Redux)',
	'Sh.0at': "Dark Temple",								# 20XXHP 5.0+
	'St.gat': "Peach's Story",								# 20XXHP 5.0+
	'TCa.gat': 'Silph Co. (Saffron City)',					# 20XXHP 5.0+
	'TCl.bat': 'Smash 4 Battlefield',
	'TCl.gat': 'Brawl Battlefield - Dusk',					# 20XXHP 5.0+
	'TCl.sat': 'Suzaku Castle',
	'TDk.0at': 'Meta Mine',									# 20XXHP 5.0+
	'TDr.0at': 'Training Room',								# 20XXHP 5.0+
	'TFe.kat': 'Kalos Pokémon League',
	'TFx.0at': 'The Plain',									# 20XXHP 5.0+
	'TGn.0at': '75m',										# 20XXHP 5.0+
	'TKb.gat': 'Miiverse (variation 1)',
	'TKb.hat': 'Miiverse (variation 2)',
	'TKb.iat': 'Miiverse (variation 3)',
	'TKb.jat': 'Miiverse (variation 4)',
	'TKp.mat': 'Metroid Lab',
	'TLg.1at': 'Giant GameCube',
	'TLg.mat': 'Metal Cavern M',
	'TLk.0at': 'Lylat Cruise',								# 20XXHP 5.0+
	'TMs.0at': 'Toy Time',									# 20XXHP 5.0+
	'TNs.0at': 'Throne Room (Wario Land)',					# 20XXHP 5.0+
	'TPe.hat': 'Hyrule Castle (N64)',
	'TSk.0at': 'Meta Crystal',								# 20XXHP 5.0+
	#'TSk.1at': 'The North Palace',							# 20XXHP 5.0+
	'Yt.1at': "Yoshi's Island, Hacked",
	'Yt.2at': "Milun's Island - Form A",					# 20XXHP 5.0+
	'Yt.3at': "Milun's Island - Form B",					# 20XXHP 5.0+
	'Yt.4at': "Milun's Island - Form C"						# 20XXHP 5.0+
}

miscNameLookup = {
	'GmGover':	'1P Mode: Game Over Screen',
	'GmPause':	'Pause Screen',
	'GmRst':	'Results Screen',
	'GmStRoll':	'Credits Screen/Minigame',
	'GmTitle':	'Title Screen',
	'GmTou1p':	'Tournament Mode, File 1',
	'GmTou2p':	'Tournament Mode, File 2',
	'GmTou3p':	'Tournament Mode, File 3',
	'GmTou4p':	'Tournament Mode, File 4',
	'GmTrain':	'Training Mode',
	'GmTtAll':	'Title Screen',
	'IfComS0':	'Dual 1v1 Infographic',
	'IfComS1':	'Chess Melee Infographic',
	'IfComS2':	'Dodgeball Infographic',
	'IfComS3':	'NBA Jam Infographic',
	'IfComS4':	'SD Remix Infographic',
	'IfComS5':	'SSBM Teir List',
	'IfHrNoCn':	'Home Run Contest, File 1',
	'IfHrReco':	'Home Run Contest, File 2',
	'IfPrize':	'Special Achievement Messages',
	'IfVsCam':	'Special Melee: Camera Mode',
	'IrAls':	'1P Mode: "VS." Intro Screens',
	'ItCo':		'Items',
	'LbMcGame':	'Memory card banners and icon',
	'LbMcSnap':	'Memory card snapshot banner/icon',
	'MnExtAll':	'Extra menu graphics for the CSS',
	'MnMaAll':	'Main menu graphics file',
	'MnSlChr':	'Character Select Screen',
	'MnSlMap':	'Stage Select Screen',
	'NtAppro':	"'New Challenger' Screens",
	'opening':	'Game banner, title, and description texts',
	'PlCo':		'Textures common to the cast',
	'SdMenu':	'Special menu characters'
}


# The following offsets are for the Character Color Converter. They are file offsets (meaning they include the 0x20 file header size).
# These represent comparable blocks of data. Blocks that should represent the same textures across differing character files.
# The ranges exclude the palette data pointers, but not the rest of the palette headers.
CCC = {
	'dataStorage': {'sourceFile': '', 'destFile': ''}, # Will also be filled with other data by prepareColorConversion().
	'Captain': { 'fullName': 'Captain Falcon', 'universe': 'F-Zero',
		'Bu': ( (0x21040, 0x7ec40), ), # All type _14
		'Gr': ( (0x21020, 0x7ec20), ),
		'Gy': ( (0x21000, 0x7ec00), ),
		'Nr': ( (0x21060, 0x7ec60), ),
		'Re': ( (0x21040, 0x7ec40), ),
		#'Re': ( (0x21040, 0x7ec40), ), # Hell Hawk texture at (0x7ec40, 0x86c40); no equivalent in other files.
		'Wh': ( (0x21120, 0x7ed20), )
		},
	'Clink': { 'fullName': 'Young Link', 'universe': 'The Legend of Zelda',
		'Bk': ( (0x1f040, 0x29940), (0x29940, 0x2db40), (0x2db44, 0x31d60), (0x31d64, 0x42c00),												# Body / equipment
				(0x43760, 0x57760),	(0x58200, 0x6c200),																						# Eyes - image data
				(0x57760, 0x57960), (0x57964, 0x57b80),	(0x57b84, 0x57da0), (0x57da4, 0x57fc0), (0x57fc4, 0x581e0), (0x581e4, 0x58200),		# Eyes - palettes & palette headers
				(0x6c200, 0x6c400),	(0x6c404, 0x6c620), (0x6c624, 0x6c840), (0x6c844, 0x6ca60), (0x6ca64, 0x6cc80), (0x6cc84, 0x6cca0) ),	# Eyes - palettes & palette headers
		'Bu': ( (0x1f040, 0x29940), (0x29940, 0x2db40), (0x2db44, 0x31d60), (0x31d64, 0x42c00),
				(0x43760, 0x57760),	(0x58200, 0x6c200),
				(0x57760, 0x57960), (0x57964, 0x57b80),	(0x57b84, 0x57da0), (0x57da4, 0x57fc0), (0x57fc4, 0x581e0), (0x581e4, 0x58200),
				(0x6c200, 0x6c400),	(0x6c404, 0x6c620), (0x6c624, 0x6c840), (0x6c844, 0x6ca60), (0x6ca64, 0x6cc80), (0x6cc84, 0x6cca0) ),
		'Nr': ( (0x1f040, 0x29940), (0x29940, 0x2db40), (0x2db44, 0x31d60), (0x31d64, 0x42c00),
				(0x43760, 0x57760),	(0x58200, 0x6c200),
				(0x57760, 0x57960), (0x57964, 0x57b80),	(0x57b84, 0x57da0), (0x57da4, 0x57fc0), (0x57fc4, 0x581e0), (0x581e4, 0x58200),
				(0x6c200, 0x6c400),	(0x6c404, 0x6c620), (0x6c624, 0x6c840), (0x6c844, 0x6ca60), (0x6ca64, 0x6cc80), (0x6cc84, 0x6cca0) ),
		'Re': ( (0x1f040, 0x29940), (0x29940, 0x2db40), (0x2db44, 0x31d60), (0x31d64, 0x42c00),
				(0x43760, 0x57760),	(0x58200, 0x6c200),
				(0x57760, 0x57960), (0x57964, 0x57b80),	(0x57b84, 0x57da0), (0x57da4, 0x57fc0), (0x57fc4, 0x581e0), (0x581e4, 0x58200),
				(0x6c200, 0x6c400),	(0x6c404, 0x6c620), (0x6c624, 0x6c840), (0x6c844, 0x6ca60), (0x6ca64, 0x6cc80), (0x6cc84, 0x6cca0) ),
		'Wh': ( (0x1f040, 0x29940), (0x29940, 0x2db40), (0x2db44, 0x31d60), (0x31d64, 0x42c00),
				(0x43760, 0x57760),	(0x58200, 0x6c200),
				(0x57760, 0x57960), (0x57964, 0x57b80),	(0x57b84, 0x57da0), (0x57da4, 0x57fc0), (0x57fc4, 0x581e0), (0x581e4, 0x58200),
				(0x6c200, 0x6c400),	(0x6c404, 0x6c620), (0x6c624, 0x6c840), (0x6c844, 0x6ca60), (0x6ca64, 0x6cc80), (0x6cc84, 0x6cca0) )
		},
	'Donkey': { 'fullName': 'Donkey Kong', 'universe': 'Donkey Kong',
		'Bk': ( (0x1d6a0, 0x5b8a0), (0x5b8a4, 0x5fac0), (0x5fac4, 0x7e240), (0x7ea80, 0x8ca80), (0x8cb40, 0x8cd40),
				(0x8cd44, 0x8cf60), (0x8cf64, 0x9af80), (0x9b040, 0x9b240), (0x9b244, 0x9b460), (0x9b464, 0x9b480) ),
		'Bu': ( (0x1d6a0, 0x5b8a0), (0x5b8a4, 0x5fac0), (0x5fac4, 0x7e240), (0x7ea80, 0x8ca80), (0x8cb40, 0x8cd40),
				(0x8cd44, 0x8cf60), (0x8cf64, 0x9af80), (0x9b040, 0x9b240), (0x9b244, 0x9b460), (0x9b464, 0x9b480) ),
		'Gr': ( (0x1d6a0, 0x5b8a0), (0x5b8a4, 0x5fac0), (0x5fac4, 0x7e240), (0x7ea80, 0x8ca80), (0x8cb40, 0x8cd40),
				(0x8cd44, 0x8cf60), (0x8cf64, 0x9af80), (0x9b040, 0x9b240), (0x9b244, 0x9b460), (0x9b464, 0x9b480) ),
		'Nr': ( (0x1d6a0, 0x5b8a0), (0x5b8a4, 0x5fac0), (0x5fac4, 0x7e240), (0x7ea80, 0x8ca80), (0x8cb40, 0x8cd40),
				(0x8cd44, 0x8cf60), (0x8cf64, 0x9af80), (0x9b040, 0x9b240), (0x9b244, 0x9b460), (0x9b464, 0x9b480) ),
		'Re': ( (0x1d6a0, 0x5b8a0), (0x5b8a4, 0x5fac0), (0x5fac4, 0x7e240), (0x7ea80, 0x8ca80), (0x8cb40, 0x8cd40),
				(0x8cd44, 0x8cf60), (0x8cf64, 0x9af80), (0x9b040, 0x9b240), (0x9b244, 0x9b460), (0x9b464, 0x9b480) )
		},
	'Drmario': { 'fullName': 'Dr. Mario', 'universe': 'Mario',
		'Bk': ( (0x1b760, 0x32ee0), (0x32ee4, 0x46200), (0x46c20, 0x73c20), (0x73c20, 0x73e20), (0x73e24, 0x74040),
				(0x74044, 0x74260), (0x74264, 0x74480), (0x74480, 0x746a0), (0x746a4, 0x746c0) ),
		'Bu': ( (0x1b760, 0x32ee0), (0x32ee4, 0x46200), (0x46c20, 0x73c20), (0x73c20, 0x73e20), (0x73e24, 0x74040),
				(0x74044, 0x74260), (0x74264, 0x74480), (0x74480, 0x746a0), (0x746a4, 0x746c0) ),
		'Gr': ( (0x1b760, 0x32ee0), (0x32ee4, 0x46200), (0x46c20, 0x73c20), (0x73c20, 0x73e20), (0x73e24, 0x74040),
				(0x74044, 0x74260), (0x74264, 0x74480), (0x74480, 0x746a0), (0x746a4, 0x746c0) ),
		'Nr': ( (0x1b760, 0x32ee0), (0x32ee4, 0x46200), (0x46c20, 0x73c20), (0x73c20, 0x73e20), (0x73e24, 0x74040),
				(0x74044, 0x74260), (0x74264, 0x74480), (0x74480, 0x746a0), (0x746a4, 0x746c0) ),
		'Re': ( (0x1b760, 0x32ee0), (0x32ee4, 0x46200), (0x46c20, 0x73c20), (0x73c20, 0x73e20), (0x73e24, 0x74040),
				(0x74044, 0x74260), (0x74264, 0x74480), (0x74480, 0x746a0), (0x746a4, 0x746c0) )
		},
	'Falco': { 'fullName': 'Falco', 'universe': 'Star Fox',
		'Bu': ( (0x18ae0, 0x358e0), (0x360c0, 0x3a0c0) ),
		'Gr': ( (0x18ae0, 0x358e0), (0x360c0, 0x3a0c0) ),
		'Nr': ( (0x18ae0, 0x358e0), (0x360c0, 0x3a0c0) ),
		'Re': ( (0x18ae0, 0x358e0), (0x360c0, 0x3a0c0) )
		},
	'Emblem': { 'fullName': 'Roy', 'universe': 'Fire Emblem',
		'Bu': ( (0x22300, 0x7be00), (0x7ca40, 0x9f180) ),
		'Gr': ( (0x22300, 0x7be00), (0x7ca40, 0x9f180) ),
		'Nr': ( (0x22300, 0x7be00), (0x7ca40, 0x9f180) ),
		'Re': ( (0x22300, 0x7be00), (0x7ca40, 0x9f180) ),
		'Ye': ( (0x22300, 0x7be00), (0x7ca40, 0x9f180) )
		},
	'Fox': { 'fullName': 'Fox', 'universe': 'Star Fox',
		'Gr': ( (0x1e500, 0x52420), (0x52da0, 0x56da0) ),
		'La': ( (0x1e500, 0x52420), (0x52da0, 0x56da0) ),
		'Nr': ( (0x1e500, 0x52420), (0x52da0, 0x56da0) ),
		'Or': ( (0x1e500, 0x52420), (0x52da0, 0x56da0) )
		},
	'Ganon': { 'fullName': 'Ganondorf', 'universe': 'The Legend of Zelda',
		'Bu': ( (0x1fbc0, 0x5d1c0), ),
		'Gr': ( (0x1fbc0, 0x5d1c0), ),
		'La': ( (0x1fbc0, 0x5d1c0), ),
		'Nr': ( (0x1fbc0, 0x5d1c0), ),
		'Re': ( (0x1fbc0, 0x5d1c0), )
		},
	'Kirby': { 'fullName': 'Kirby', 'universe': 'Kirby', # Ignores eye textures
		'Bu': ( (0x1fca0, 0x23ea0), (0x23ea4, 0x25840), (0x25844, 0x31b40) ),
		'Gr': ( (0x1fca0, 0x23ea0), (0x23ea4, 0x25840), (0x25844, 0x31b40) ),
		'Nr': ( (0x1fca0, 0x23ea0), (0x23ea4, 0x25840), (0x25844, 0x31b40) ),
		'Re': ( (0x1fca0, 0x23ea0), (0x23ea4, 0x25840), (0x25844, 0x31b40) ),
		'Wh': ( (0x1fca0, 0x23ea0), (0x23ea4, 0x25840), (0x25844, 0x31b40) ),
		'Ye': ( (0x1fca0, 0x23ea0), (0x23ea4, 0x25840), (0x25844, 0x31b40) )
		},
	'Koopa': { 'fullName': 'Bowser', 'universe': 'Mario',
		'Bk': ( (0x2a720, 0x61520), (0x61520, 0x626c0), (0x626c4, 0x6de00), (0x6de00, 0x6fe00), (0x70b20, 0x75d20),
				(0x75d24, 0x75f00), (0x75f04, 0x76120), (0x76124, 0x76340), (0x76344, 0x76560), (0x76564, 0x76580) ),
		'Bu': ( (0x2a720, 0x61520), (0x61520, 0x626c0), (0x626c4, 0x6de00), (0x6de00, 0x6fe00), (0x70b20, 0x75d20),
				(0x75d24, 0x75f40), (0x75f44, 0x76160), (0x76164, 0x76380), (0x76384, 0x765a0), (0x765a4, 0x765a0) ),
		'Nr': ( (0x2a720, 0x61520), (0x61520, 0x626c0), (0x626c4, 0x6de00), (0x6de00, 0x75e00), (0x76b20, 0x7bd20),
				(0x7bd24, 0x7bf40), (0x7bf44, 0x7c160), (0x7c164, 0x7c380), (0x7c384, 0x7c5a0), (0x7c5a4, 0x7c5c0) ),
		'Re': ( (0x2a720, 0x61520), (0x61520, 0x62720), (0x62724, 0x6de60), (0x6de60, 0x6fe60), (0x70b80, 0x75d80),
				(0x75d84, 0x75ee0), (0x75ee4, 0x760e0), (0x760e4, 0x76300), (0x76304, 0x76520), (0x76524, 0x76540) )
		},
	'Luigi': { 'fullName': 'Luigi', 'universe': 'Mario',
		'Aq': ( (0x1b2c0, 0x2c740), (0x2c740, 0x30f40), (0x30f40, 0x42be0), (0x43400, 0x59c00) ),
		'Nr': ( (0x1b2c0, 0x2c740), (0x2c740, 0x30f40), (0x30f40, 0x42be0), (0x43400, 0x59c00) ),
		'Pi': ( (0x1b2c0, 0x2c740), (0x2c740, 0x30f40), (0x30f40, 0x42be0), (0x43400, 0x59c00) ),
		'Wh': ( (0x1b2c0, 0x2c740), (0x2c740, 0x35960), (0x35960, 0x47600), (0x47ea0, 0x75940) )
		},
	'Link': { 'fullName': 'Link', 'universe': 'The Legend of Zelda',
		'Bk': ( (0x20a60, 0x25560), (0x25564, 0x29780), (0x29784, 0x2ccc0), (0x2ccc4, 0x3aee0), (0x3aee4, 0x3f100),
				(0x3f104, 0x4c220), (0x4ce00, 0x61000), (0x61004, 0x61220), (0x61224, 0x61440), (0x61444, 0x61660),
				(0x61664, 0x61880), (0x61884, 0x75aa0), (0x75aa4, 0x75cc0), (0x75cc4, 0x75ee0), (0x75ee4, 0x76100),
				(0x76104, 0x76320), (0x76324, 0x76340) ),
		'Bu': ( (0x20a60, 0x25560), (0x25564, 0x29780), (0x29784, 0x2ccc0), (0x2ccc4, 0x3aee0), (0x3aee4, 0x3f100),
				(0x3f104, 0x4c220), (0x4ce00, 0x61000), (0x61004, 0x61220), (0x61224, 0x61440), (0x61444, 0x61660),
				(0x61664, 0x61880), (0x61884, 0x75aa0), (0x75aa4, 0x75cc0), (0x75cc4, 0x75ee0), (0x75ee4, 0x76100),
				(0x76104, 0x76320), (0x76324, 0x76340) ),
		'Nr': ( (0x20a60, 0x25560), (0x25564, 0x29780), (0x29784, 0x2ccc0), (0x2ccc4, 0x3aee0), (0x3aee4, 0x3f100),
				(0x3f104, 0x4c220), (0x4ce00, 0x61000), (0x61004, 0x61220), (0x61224, 0x61440), (0x61444, 0x61660),
				(0x61664, 0x61880), (0x61884, 0x75aa0), (0x75aa4, 0x75cc0), (0x75cc4, 0x75ee0), (0x75ee4, 0x76100),
				(0x76104, 0x76320), (0x76324, 0x76340) ),
		'Re': ( (0x20a60, 0x25560), (0x25564, 0x29780), (0x29784, 0x2ccc0), (0x2ccc4, 0x3aee0), (0x3aee4, 0x3f100),
				(0x3f104, 0x4c220), (0x4ce00, 0x61000), (0x61004, 0x61220), (0x61224, 0x61440), (0x61444, 0x61660),
				(0x61664, 0x61880), (0x61884, 0x75aa0), (0x75aa4, 0x75cc0), (0x75cc4, 0x75ee0), (0x75ee4, 0x76100),
				(0x76104, 0x76320), (0x76324, 0x76340) ),
		'Wh': ( (0x20a60, 0x25560), (0x25564, 0x29780), (0x29784, 0x2ccc0), (0x2ccc4, 0x3aee0), (0x3aee4, 0x3f100),
				(0x3f104, 0x4c220), (0x4ce00, 0x61000), (0x61004, 0x61220), (0x61224, 0x61440), (0x61444, 0x61660),
				(0x61664, 0x61880), (0x61884, 0x75aa0), (0x75aa4, 0x75cc0), (0x75cc4, 0x75ee0), (0x75ee4, 0x76100),
				(0x76104, 0x76320), (0x76324, 0x76340) )
		},
	'Mario': { 'fullName': 'Mario', 'universe': 'Mario',
		'Bk': ( (0x1ad60, 0x35be0), (0x35be4, 0x43fa0), (0x448a0, 0x71aa0), (0x71aa4, 0x71cc0), (0x71cc4, 0x71ee0),
				(0x71ee4, 0x72100), (0x72104, 0x72320), (0x72324, 0x72340) ),
		'Bu': ( (0x1ad60, 0x35be0), (0x35be4, 0x43fa0), (0x448a0, 0x71aa0), (0x71aa4, 0x71cc0), (0x71cc4, 0x71ee0),
				(0x71ee4, 0x72100), (0x72104, 0x72320), (0x72324, 0x72340) ),
		'Gr': ( (0x1ad60, 0x35be0), (0x35be4, 0x43fa0), (0x448a0, 0x71aa0), (0x71aa4, 0x71cc0), (0x71cc4, 0x71ee0),
				(0x71ee4, 0x72100), (0x72104, 0x72320), (0x72324, 0x72340) ),
		'Nr': ( (0x1ad60, 0x35be0), (0x35be4, 0x43fa0), (0x448a0, 0x71aa0), (0x71aa4, 0x71cc0), (0x71cc4, 0x71ee0),
				(0x71ee4, 0x72100), (0x72104, 0x72320), (0x72324, 0x72340) ),
		'Ye': ( (0x1ad60, 0x35be0), (0x35be4, 0x43fa0), (0x448a0, 0x71aa0), (0x71aa4, 0x71cc0), (0x71cc4, 0x71ee0),
				(0x71ee4, 0x72100), (0x72104, 0x72320), (0x72324, 0x72340) )
		},
	'Mars': { 'fullName': 'Marth', 'universe': 'Fire Emblem',
		'Bk': ( (0x21d80, 0x40080), (0x40084, 0x442a0), (0x442a4, 0x454c0), (0x454c4, 0x4a6e0), (0x4a6e4, 0x4e900),
				(0x4e904, 0x65320), (0x65f20, 0x7a120), (0x7a124, 0x7a340), (0x7a344, 0x7a560), (0x7a564, 0x7a780),
				(0x7a784, 0x7a9a0), (0x7a9a4, 0x7a9c0), (0x7a9c0, 0x8ebc0), (0x8ebc4, 0x8ede0), (0x8ede4, 0x8f000),
				(0x8f004, 0x8f220), (0x8f224, 0x8f440), (0x8f444, 0x8f460) ),
		'Gr': ( (0x21d80, 0x40080), (0x40084, 0x442a0), (0x442a4, 0x454c0), (0x454c4, 0x4a6e0), (0x4a6e4, 0x4e900),
				(0x4e904, 0x65320), (0x65f20, 0x7a120), (0x7a124, 0x7a340), (0x7a344, 0x7a560), (0x7a564, 0x7a780),
				(0x7a784, 0x7a9a0), (0x7a9a4, 0x7a9c0), (0x7a9c0, 0x8ebc0), (0x8ebc4, 0x8ede0), (0x8ede4, 0x8f000),
				(0x8f004, 0x8f220), (0x8f224, 0x8f440), (0x8f444, 0x8f460) ),
		'Nr': ( (0x21d80, 0x40080), (0x40084, 0x442a0), (0x442a4, 0x454c0), (0x454c4, 0x4a6e0), (0x4a6e4, 0x4e900),
				(0x4e904, 0x65320), (0x65f20, 0x7a120), (0x7a124, 0x7a340), (0x7a344, 0x7a560), (0x7a564, 0x7a780),
				(0x7a784, 0x7a9a0), (0x7a9a4, 0x7a9c0), (0x7a9c0, 0x8ebc0), (0x8ebc4, 0x8ede0), (0x8ede4, 0x8f000),
				(0x8f004, 0x8f220), (0x8f224, 0x8f440), (0x8f444, 0x8f460) ),
		'Re': ( (0x21d80, 0x40080), (0x40084, 0x442a0), (0x442a4, 0x454c0), (0x454c4, 0x4a6e0), (0x4a6e4, 0x4e900),
				(0x4e904, 0x65320), (0x65f20, 0x7a120), (0x7a124, 0x7a340), (0x7a344, 0x7a560), (0x7a564, 0x7a780),
				(0x7a784, 0x7a9a0), (0x7a9a4, 0x7a9c0), (0x7a9c0, 0x8ebc0), (0x8ebc4, 0x8ede0), (0x8ede4, 0x8f000),
				(0x8f004, 0x8f220), (0x8f224, 0x8f440), (0x8f444, 0x8f460) ),
		'Wh': ( (0x21d80, 0x40080), (0x40084, 0x442a0), (0x442a4, 0x454c0), (0x454c4, 0x4a6e0), (0x4a6e4, 0x4e900),
				(0x4e904, 0x65320), (0x65f20, 0x7a120), (0x7a124, 0x7a340), (0x7a344, 0x7a560), (0x7a564, 0x7a780),
				(0x7a784, 0x7a9a0), (0x7a9a4, 0x7a9c0), (0x7a9c0, 0x8ebc0), (0x8ebc4, 0x8ede0), (0x8ede4, 0x8f000),
				(0x8f004, 0x8f220), (0x8f224, 0x8f440), (0x8f444, 0x8f460) )
		},
	'Mewtwo': { 'fullName': 'Mewtwo', 'universe': 'Pokemon',
		'Bu': ( (0x19540, 0x2eb40), (0x2f440, 0x3d440) ),
		'Gr': ( (0x19540, 0x2eb40), (0x2f440, 0x3d440) ),
		'Nr': ( (0x19540, 0x2eb40), (0x31440, 0x3f440) ), # Also contains an additional eye texture, at (0x2f440, 0x31440), not present in the other color files.
		'Re': ( (0x19540, 0x2eb40), (0x2f440, 0x3d440) )
		},
	'Nana': { 'fullName': 'Nana (Ice Climbers)', 'universe': 'Ice Climber',
		'Aq': ( (0x107c0, 0x3c4c0), (0x3cb40, 0x54b40) ),
		'Nr': ( (0x10800, 0x3c500), (0x3cb80, 0x54b80) ),
		'Wh': ( (0x107c0, 0x3c4c0), (0x3cb40, 0x54b40) ),
		'Ye': ( (0x107e0, 0x3c4e0), (0x3cb60, 0x54b60) )
		},
	'Ness': { 'fullName': 'Ness', 'universe': 'EarthBound',
		'Bu': ( (0x1d220, 0x51a20), (0x52300, 0x5a300) ),
		'Gr': ( (0x1d220, 0x51a20), (0x52300, 0x5a300) ),
		'Nr': ( (0x1cae0, 0x512e0), (0x51b80, 0x59b80) ),
		'Ye': ( (0x1d200, 0x51a00), (0x522e0, 0x5a2e0) ),
		},
	'Pichu': { 'fullName': 'Pichu', 'universe': 'Pokemon',
		'Bu': ( (0x1e800, 0x1f020), (0x1f020, 0x28820), (0x28c20, 0x2ac20), (0x2b320, 0x37320) ),
		'Gr': ( (0x16b00, 0x17320), (0x2c320, 0x35b20), (0x3db20, 0x3fb20), (0x40240, 0x4c240) ),
		'Nr': ( (0x101c0, 0x109e0), (0x109e0, 0x1a1e0), (0x1a1e0, 0x1c1e0), (0x1c7e0, 0x287e0) ),
		'Re': ( (0x151e0, 0x15a00), (0x15a00, 0x1f200), (0x1f200, 0x21200), (0x25840, 0x31840) )
		},
	'Peach': { 'fullName': 'Peach', 'universe': 'Mario',
		'Bu': ( (0x221c0, 0x263c0), (0x263c4, 0x294e0), (0x294e0, 0x29ac0), (0x29ac4, 0x2a080), (0x2a084, 0x2a0a0),
				(0x2a0a0, 0x2b8c0), (0x2b8c0, 0x2ce20), (0x2ce24, 0x2de40), (0x2de40, 0x2e7c0), (0x2e7c4, 0x329e0),
				(0x329e4, 0x3ec00), (0x3ec04, 0x42e20), (0x42e24, 0x4c740), (0x4c740, 0x4ec40), (0x4ec44, 0x55860),
				(0x55864, 0x5d380), (0x5d384, 0x680a0), (0x680a4, 0x6a4c0), (0x6b160, 0xc3160) ),
		'Gr': ( (0x221c0, 0x263c0), (0x263c4, 0x294e0), (0x294e0, 0x29ac0), (0x29ac4, 0x2a080), (0x2a084, 0x2a0a0),
				(0x2a0a0, 0x2b8c0), (0x2b8c0, 0x2ce20), (0x2ce24, 0x2de40), (0x2de40, 0x2e720), (0x2e724, 0x32940),
				(0x32944, 0x3eb60), (0x3eb64, 0x42d80), (0x42d84, 0x4c6a0), (0x4c6a0, 0x4ebc0), (0x4ec44, 0x557e0),
				(0x557e4, 0x5d300), (0x5d304, 0x68020), (0x68024, 0x6a440), (0x6b0e0, 0xc30e0) ),
		'Nr': ( (0x221c0, 0x263c0), (0x263c4, 0x294e0), (0x294e0, 0x29ae0), (0x29ae4, 0x2a100), (0x2a104, 0x2a120),
				(0x2a120, 0x2b940), (0x2b940, 0x2d780), (0x2d784, 0x2e7a0), (0x2e7a0, 0x2f1a0), (0x2f1a4, 0x333c0),
				(0x333c4, 0x3f5e0), (0x3f5e4, 0x43800), (0x43804, 0x4d120), (0x4d120, 0x4f720), (0x4f724, 0x56340),
				(0x56344, 0x5de60), (0x5de64, 0x68b80), (0x68b84, 0x6afa0), (0x6bc40, 0xc3c40) ),
		'Wh': ( (0x221c0, 0x263c0), (0x263c4, 0x294e0), (0x294e0, 0x29a00), (0x29a04, 0x29fc0), (0x29fc4, 0x29fe0),
				(0x29fe0, 0x2b800), (0x2b800, 0x2ce00), (0x2ce04, 0x2de20), (0x2de20, 0x2e700), (0x2e704, 0x32920),
				(0x32924, 0x3eb40), (0x3eb44, 0x42d60), (0x42d64, 0x4eb80), (0x4eb80, 0x4eb80), (0x4eb84, 0x557a0),
				(0x557a4, 0x5d2c0), (0x5d2c4, 0x67fe0), (0x67fe4, 0x6a400), (0x6b0a0, 0xc30a0) )
		#'Ye': (  ) Too many changes from above to track. Will need to be manually converted.
		},
	'Pikachu': { 'fullName': 'Pikachu', 'universe': 'Pokemon',
		'Bu': ( (0x15840, 0x15860), (0x19860, 0x1d360), (0x1d9c0, 0x256c0) ),
		'Gr': ( (0x15f40, 0x15f60), (0x19f60, 0x1da60), (0x1e0c0, 0x25dc0) ),
		'Nr': ( (0x14160, 0x14180), (0x14180, 0x17c80), (0x182a0, 0x1ffa0) ),
		'Re': ( (0x15280, 0x152a0), (0x1baa0, 0x1f5a0), (0x1fc20, 0x27920) )
		},
	'Popo': { 'fullName': 'Popo (Ice Climbers)', 'universe': 'Ice Climber',
		'Gr': ( (0x10780, 0x3c480), (0x3cb00, 0x54b00) ),
		'Nr': ( (0x10780, 0x3c480), (0x3cb00, 0x54b00) ),
		'Or': ( (0x10780, 0x3c480), (0x3cb00, 0x54b00) ),
		'Re': ( (0x107e0, 0x3c4e0), (0x3cb60, 0x54b60) )
		},
	'Purin': { 'fullName': 'Jigglypuff', 'universe': 'Pokemon',
		'Bu': ( (0x11b80, 0x13ba0), (0x13ba0, 0x17ce0), (0x17ce4, 0x19900),
				(0x19ea0, 0x2dfe0), (0x2dfe4, 0x2e120), (0x2e124, 0x2e2a0), (0x2e2a4, 0x2e400), (0x2e404, 0x2e560),
				(0x2e564, 0x3a6c0), (0x3a6c4, 0x3a800), (0x3a804, 0x3a980), (0x3a984, 0x3a9a0) ),
		'Gr': ( (0x11b80, 0x13ba0), (0x13ba0, 0x17ce0), (0x17ce4, 0x19900),
				(0x19ea0, 0x2dfe0), (0x2dfe4, 0x2e120), (0x2e124, 0x2e2a0), (0x2e2a4, 0x2e400), (0x2e404, 0x2e560),
				(0x2e564, 0x3a6c0), (0x3a6c4, 0x3a800), (0x3a804, 0x3a980), (0x3a984, 0x3a9a0) ),
		'Nr': ( (0x11b80, 0x13ba0), (0x13ba0, 0x17da0), (0x17dc0, 0x199c0),
				(0x19f60, 0x2e160), (0x2e164, 0x2e380), (0x2e384, 0x2e5a0), (0x2e5a4, 0x2e7c0), (0x2e7c4, 0x2e9e0),
				(0x2e9e4, 0x3ac00), (0x3ac04, 0x3ae20), (0x3ae24, 0x3b040), (0x3b044, 0x3b060) ),
		'Re': ( (0x11b80, 0x13ba0), (0x13ba0, 0x17ce0), (0x17ce4, 0x19900),
				(0x19ea0, 0x2dfe0), (0x2dfe4, 0x2e120), (0x2e124, 0x2e2a0), (0x2e2a4, 0x2e400), (0x2e404, 0x2e560),
				(0x2e564, 0x3a6c0), (0x3a6c4, 0x3a800), (0x3a804, 0x3a980), (0x3a984, 0x3a9a0) ),
		'Ye': ( (0x11b80, 0x13ba0), (0x13ba0, 0x17ce0), (0x17ce4, 0x19900),
				(0x19ea0, 0x2dfe0), (0x2dfe4, 0x2e120), (0x2e124, 0x2e2a0), (0x2e2a4, 0x2e400), (0x2e404, 0x2e560),
				(0x2e564, 0x3a6c0), (0x3a6c4, 0x3a800), (0x3a804, 0x3a980), (0x3a984, 0x3a9a0) )
		},
	'Seak': { 'fullName': 'Sheik', 'universe': 'The Legend of Zelda',
		'Bu': ( (0x1c5e0, 0x2c700), (0x2c700, 0x34900), (0x34904, 0x38b20), (0x38b24, 0x3cd40), (0x3cd44, 0x43100),
				(0x43a20, 0x4f020), (0x4f024, 0x4f240), (0x4f244, 0x4f460), (0x4f464, 0x4f680), (0x4f684, 0x4f8a0),
				(0x4f8a4, 0x5aec0), (0x5aec4, 0x5b0e0), (0x5b0e4, 0x5b300), (0x5b304, 0x5b520), (0x5b524, 0x5b740), (0x5b744, 0x5b760) ),
		'Gr': ( (0x1c5e0, 0x2c700), (0x2c700, 0x348a0), (0x348a4, 0x38ac0), (0x38ac4, 0x3cce0), (0x3cce4, 0x430a0),
				(0x439c0, 0x4efc0), (0x4efc4, 0x4f1e0), (0x4f1e4, 0x4f400), (0x4f404, 0x4f620), (0x4f624, 0x4f840),
				(0x4f844, 0x5ae60), (0x5ae64, 0x5b080), (0x5b084, 0x5b2a0), (0x5b2a4, 0x5b4c0), (0x5b4c4, 0x5b6e0), (0x5b6e4, 0x5b700) ),
		'Nr': ( (0x1c5e0, 0x2c700), (0x2c700, 0x34900), (0x34904, 0x38b20), (0x38b24, 0x3cd40), (0x3cd44, 0x43100),
				(0x43a20, 0x4f020), (0x4f024, 0x4f240), (0x4f244, 0x4f460), (0x4f464, 0x4f680), (0x4f684, 0x4f8a0),
				(0x4f8a4, 0x5aec0), (0x5aec4, 0x5b0e0), (0x5b0e4, 0x5b300), (0x5b304, 0x5b520), (0x5b524, 0x5b740), (0x5b744, 0x5b760) ),
		'Re': ( (0x1c5e0, 0x2c700), (0x2c700, 0x34860), (0x34864, 0x38a80), (0x38a84, 0x3cca0), (0x3cca4, 0x43060),
				(0x43980, 0x4ef80), (0x4ef84, 0x4f1a0), (0x4f1a4, 0x4f3c0), (0x4f3c4, 0x4f5e0), (0x4f5e4, 0x4f800),
				(0x4f804, 0x4ae20), (0x4ae24, 0x5b040), (0x5b044, 0x5b260), (0x5b264, 0x5b480), (0x5b484, 0x5b6a0), (0x5b6a4, 0x5b6c0) ),
		'Wh': ( (0x1c5e0, 0x2c700), (0x2c700, 0x34900), (0x34904, 0x38b20), (0x38b24, 0x3cd40), (0x3cd44, 0x43100),
				(0x43a20, 0x4f020), (0x4f024, 0x4f240), (0x4f244, 0x4f460), (0x4f464, 0x4f680), (0x4f684, 0x4f8a0),
				(0x4f8a4, 0x5aec0), (0x5aec4, 0x5b0e0), (0x5b0e4, 0x5b300), (0x5b304, 0x5b520), (0x5b524, 0x5b740), (0x5b744, 0x5b760) )
		},
	'Samus': { 'fullName': 'Samus', 'universe': 'Metroid',
		'Bk': ( (0x29b20, 0x2dd20), (0x2dd20, 0x2e520), (0x2e520, 0x3b420), (0x3b420, 0x3bc20), (0x3bc20, 0x608a0) ),
		'Gr': ( (0x29b20, 0x2dd20), (0x2dd20, 0x2fd20), (0x2fd20, 0x3cc20), (0x3cc20, 0x3d420), (0x3d420, 0x620a0) ),
		'La': ( (0x29b20, 0x2dd20), (0x2dd20, 0x2e520), (0x2e520, 0x3b420), (0x3b420, 0x3bc20), (0x3bc20, 0x608a0) ),
		'Nr': ( (0x29b20, 0x2dd20), (0x2dd20, 0x2e520), (0x2e520, 0x3b420), (0x3b420, 0x3bc20), (0x3bc20, 0x608a0) ),
		'Pi': ( (0x29b20, 0x2dd20), (0x2dd20, 0x2e520), (0x2e520, 0x3b420), (0x3b420, 0x3d420), (0x3d420, 0x620a0) )
		},
	'Yoshi': { 'fullName': 'Yoshi', 'universe': 'Yoshi',
		'Aq': ( (0x23fe0, 0x25fe0), (0x25fe0, 0x2a060), (0x2a064, 0x2a080), (0x2a080, 0x2e080), (0x2e080, 0x30080), (0x30080, 0x32080),
				(0x32080, 0x35de0), (0x35de0, 0x37ac0), (0x37ac4, 0x37ae0), (0x37ae0, 0x38d20), (0x38d24, 0x38d40), (0x38d40, 0x3c6e0), (0x3c6e4, 0x3c700), (0x3c700, 0x3cc00), (0x3cc00, 0x3dc00),
				(0x3dc00, 0x3ec20), (0x3ec24, 0x3ec40), (0x3ec40, 0x40d20), (0x40d24, 0x40d40), (0x40d40, 0x41d00), (0x42580, 0x46580) ),
		'Bu': ( (0x2ed40, 0x30d40), (0x30d40, 0x34dc0), (0x34dc4, 0x34de0), (0x25fe0, 0x29fe0), (0x34de0, 0x36de0), (0x23fe0, 0x25fe0),
				(0x29fe0, 0x2dd40), (0x36de0, 0x38a80), (0x38a84, 0x38aa0), (0x38aa0, 0x39cc0), (0x39cc4, 0x39ce0), (0x39ce0, 0x3d680), (0x3d684, 0x3d6a0), (0x3d6a0, 0x3dba0), (0x2dd40, 0x2ed40),
				(0x3dba0, 0x3ebc0), (0x3ebc4, 0x3ebe0), (0x3ebe0, 0x40c40), (0x40c44, 0x40c60), (0x40c60, 0x41c20), (0x424a0, 0x464a0) ),
		'Nr': ( (0x23fc0, 0x25fc0), (0x25fc0, 0x2a040), (0x2a044, 0x2a060), (0x2a060, 0x2e060), (0x2e060, 0x30060), (0x30060, 0x32060),
				(0x32060, 0x35dc0), (0x35dc0, 0x37a40), (0x37a44, 0x37a60), (0x37a60, 0x38c80), (0x38c84, 0x38ca0), (0x38ca0, 0x3c640), (0x3c644, 0x3c660), (0x3c660, 0x3cb60), (0x3cb60, 0x3db60),
				(0x3db60, 0x3eb80), (0x3eb84, 0x3eba0), (0x3eba0, 0x40be0), (0x40be4, 0x40c00), (0x40c00, 0x41bc0), (0x42440, 0x46440) ),
		'Pi': ( (0x23fe0, 0x25fe0), (0x25fe0, 0x2a060), (0x2a064, 0x2a080), (0x2a080, 0x2e080), (0x2e080, 0x30080), (0x30080, 0x32080),
				(0x32080, 0x35de0), (0x35de0, 0x37ae0), (0x37ae4, 0x37b00), (0x37b00, 0x38d20), (0x38d24, 0x38d40), (0x38d40, 0x3c6e0), (0x3c6e4, 0x3c700), (0x3c700, 0x3cc00), (0x3cc00, 0x3dc00),
				(0x3dc00, 0x3ec20), (0x3ec24, 0x3ec40), (0x3ec40, 0x40d20), (0x40d24, 0x40d40), (0x40d60, 0x41d20), (0x425a0, 0x465a0) ),
		'Re': ( (0x30d00, 0x32d00), (0x32d00, 0x36d80), (0x36d84, 0x36da0), (0x25fa0, 0x29fa0), (0x23fa0, 0x25fa0), (0x29fa0, 0x2bfa0),
				(0x2bfa0, 0x2fd00), (0x36da0, 0x38aa0), (0x38aa4, 0x38ac0), (0x38ac0, 0x39ce0), (0x39ce4, 0x39d00), (0x39d00, 0x3d6a0), (0x3d6a4, 0x3d6c0), (0x3d6c0, 0x3dbc0), (0x2fd00, 0x30d00),
				(0x3dbc0, 0x3ebe0), (0x3ebe4, 0x3ec00), (0x3ec00, 0x40d80), (0x40d84, 0x40da0), (0x40da0, 0x41d60), (0x425e0, 0x465e0) ),
		'Ye': ( (0x2fd40, 0x31d40), (0x3cca0, 0x40d20), (0x40d24, 0x40d40), (0x25fe0, 0x29fe0), (0x23fe0, 0x25fe0), (0x29fe0, 0x2bfe0),
				(0x2bfe0, 0x2fd40), (0x31d40, 0x33a20), (0x33a24, 0x33a40), (0x33a40, 0x34c60), (0x34c64, 0x34c80), (0x34c80, 0x38620), (0x38624, 0x38640), (0x38640, 0x38b40), (0x38b40, 0x39b40),
				(0x39b40, 0x3ab60), (0x3ab64, 0x3ab80), (0x3ab80, 0x3cc80), (0x3cc84, 0x3cca0), (0x40d40, 0x41d00), (0x42580, 0x46580) )
		},
	'Zelda': { 'fullName': 'Zelda', 'universe': 'The Legend of Zelda',
		'Bu': ( (0x1db60, 0x235a0), (0x235a0, 0x23ea0), (0x23ea0, 0x24ea0), (0x24ea0, 0x25fa0), (0x25fa4, 0x25fc), (0x25fc0, 0x39940),
				(0x39940, 0x3a940), (0x3a940, 0x41ee0), (0x429c0, 0x529c0) ),
		'Gr': ( (0x1db60, 0x235a0), (0x235a0, 0x23ea0), (0x23ea0, 0x24ea0), (0x24ea0, 0x25fa0), (0x25fa4, 0x25fc), (0x25fc0, 0x39940),
				(0x39940, 0x3a940), (0x3a940, 0x41ee0), (0x429c0, 0x529c0) ),
		'Nr': ( (0x1db60, 0x235a0), (0x235a0, 0x23ea0), (0x23ea0, 0x24ea0), (0x24ea0, 0x260a0), (0x260a4, 0x260c0), (0x260c0, 0x39a40),
				(0x39a40, 0x3bba0), (0x3bba0, 0x43140), (0x43c20, 0x53c20) ),
		'Re': ( (0x1db60, 0x235a0), (0x235a0, 0x23ea0), (0x23ea0, 0x24ea0), (0x24ea0, 0x25fa0), (0x25fa4, 0x25fc), (0x25fc0, 0x39940),
				(0x39940, 0x3a940), (0x3a940, 0x41ee0), (0x429c0, 0x529c0) ),
		'Wh': ( (0x1db60, 0x235a0), (0x235a0, 0x24da0), (0x24da0, 0x25da0), (0x25da0, 0x26ea0), (0x26ea4, 0x26ec0), (0x26ec0, 0x3a840),
				(0x3a840, 0x3b840), (0x3b840, 0x42de0), (0x438c0, 0x538c0) )
		}
	}

																				#===========================#
																				# ~ ~ General Functions ~ ~ #
																				#===========================#

def isNaN( var ): # Test if a variable 'is Not a Number'
	try:
		float( var )
		return False
	except ValueError:
		return True

def roundTo32( x, base=32 ): # Rounds up to nearest increment of 32.
	return int( base * math.ceil(float(x) / base) )

# def CRC32_from_file( filename ):
# 	buf = open( filename, 'rb').read()
# 	buf = (binascii.crc32( buf ) & 0xFFFFFFFF)
# 	return "%08X" % buf

def uHex( integer ): # Quick conversion to have a hex function which shows uppercase characters.
	return '0x' + hex( integer )[2:].upper() # Twice as fast as .format

# def float_to_hex( floatValue ):

# 	""" Converts a float to its hex representation, padded to 8 characters. """

# 	return '{0:0{1}X}'.format( struct.unpack('<I', struct.pack( '<f', floatValue ))[0], 8 )

def toInt( input ): # Converts a 1, 2, or 4 bytes object or bytearray to an integer.
	try:
		byteLength = len( input )
		if ( byteLength == 1 ): return struct.unpack( '>B', input )[0] 		# big-endian unsigned char (1 byte)
		elif ( byteLength == 2 ): return struct.unpack( '>H', input )[0] 	# big-endian unsigned short (2 bytes)
		else: return struct.unpack( '>I', input )[0] 						# big-endian unsigned int (4 bytes)
	except:
		raise Exception( '\ntoInt was not able to convert the ' + str(type(input))+' type' )

def toBytes( input, byteLength=4, cType='' ): # Converts an int to a bytes object

	if not cType: # Assume a big-endian unsigned value of some byte length
		if byteLength == 1: cType = '>B'		# big-endian unsigned char (1 byte)
		elif byteLength == 2: cType = '>H'		# big-endian unsigned short (2 bytes)
		elif byteLength == 4: cType = '>I'		# big-endian unsigned int (4 bytes)
		else:
			raise Exception( '\ntoBytes was not able to convert the ' + str(type(input))+' type' )

	return struct.pack( cType, input )

# Conversion solutions:
# 		int 			-> 		bytes objects 		struct.pack( )
# 		byte string 	-> 		int:				struct.unpack( )
# 		byte string 	-> 		hex string 			.encode( 'hex' )
# 		bytearray 		-> 		hex string:			hexlify( input )
# 		hex string 		-> 		bytearray: 			bytearray.fromhex( input )
# 		text string 	-> 		bytearray			init bytearray, then use .extend( string ) method on it

# 		Note that a file object's .read() method returns a byte-string of unknown encoding, which will be 
# 		locally interpreted as it's displayed. It should be properly decoded to a standard to be operated on.
#
# 		Note 2: In python 2, bytes objects are an alias for str objects; they are not like bytearrays.

def validOffset( offset ): # Accepts a string.
	offset = offset.replace( '0x', '' )
	if offset == '': return False
	return all(char in hexdigits for char in offset) # Returns Boolean

def grammarfyList( theList ): # For example, the list [apple, pear, banana, melon] becomes the string 'apple, pear, banana, and melon'.
	if len(theList) == 1: return str(theList[0])
	elif len(theList) == 2: return str(theList[0]) + ' and ' + str(theList[1])
	else:
		string = ', '.join( theList )
		indexOfLastComma = string.rfind(',')
		return string[:indexOfLastComma] + ', and ' + string[indexOfLastComma + 2:]

def msg( *args ):
	if len(args) > 1: tkMessageBox.showinfo( message=args[0], title=args[-1] )
	else: tkMessageBox.showinfo( message=args[0] )

def copyToClipboard( text ):
	Gui.root.clipboard_clear()
	Gui.root.clipboard_append( text )

def humansize(nbytes): # Used for converting file sizes, in terms of human readability.
	suffixes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']

	if nbytes == 0: return '0 B'
	i = 0
	while nbytes >= 1024 and i < len(suffixes)-1:
		nbytes /= 1024.
		i += 1
	f = ('%.2f' % nbytes).rstrip('0').rstrip('.')
	return '%s %s' % (f, suffixes[i])

def createFolders( folderPath ):
	try:
		os.makedirs( folderPath )

		# Primitive failsafe to prevent race condition
		attempt = 0
		while not os.path.exists( folderPath ):
			time.sleep( .3 )
			if attempt > 10:
				raise Exception( 'Unable to create folder: ' + folderPath )
			attempt += 1
	except OSError as error: # Python >2.5
		if error.errno == errno.EEXIST and os.path.isdir( folderPath ):
			pass
		else: raise

def validHex( offset ): # Accepts a string.
	offset = offset.replace( '0x', '' )
	if offset == '': return False
	return all( char in hexdigits for char in offset ) # Returns Boolean

def rgb2hex( color ): # Input can be RGB or RGBA, but output will still be RGB
	return '#{:02x}{:02x}{:02x}'.format( color[0], color[1], color[2]) 

def rgb2hsv( color ):
	r, g, b, _ = color
	r, g, b = r/255.0, g/255.0, b/255.0
	mx = max(r, g, b)
	mn = min(r, g, b)
	df = mx-mn
	if mx == mn: h = 0
	elif mx == r: h = (60 * ((g-b)/df) + 360) % 360
	elif mx == g: h = (60 * ((b-r)/df) + 120) % 360
	elif mx == b: h = (60 * ((r-g)/df) + 240) % 360
	if mx == 0: s = 0
	else: s = df/mx
	v = mx
	return ( h, s, v )

def hex2rgb( inputStr ): # Expects RRGGBBAA

	""" Returns a 4 color channel iterable of (r,g,b,a) """

	inputStr = inputStr.replace( '#', '' )
	channelsList = []
	parsingError = False

	if len( inputStr ) % 2 != 0: # Checks whether the string is an odd number of characters
		parsingError = True
	else:
		for i in xrange( 0, len(inputStr), 2 ): # Iterate by 2 over the length of the input string
			try:
				byte = inputStr[i:i+2]
				newInt = int( byte, 16 )
				if newInt > -1 and newInt < 256: channelsList.append( newInt )
			except: 
				parsingError = True
				break
		else: # Got through the above loop with no break. Still got one more check.
			#if len( channelsList ) == 3: channelsList.append( 255 ) # assume the entries are RGB, and add alpha
			if len( channelsList ) != 4: parsingError = True

	return ( tuple(channelsList), parsingError )

def getLuminance( hexColor ):
	r, g, b, a = hex2rgb( hexColor )[0]
	return ( r*0.299 + g*0.587 + b*0.114 ) * a/255
	#return ( r+r + g+g+g + b )/6 * a/255 # a quicker but less accurate calculation
	#return math.sqrt( .299 * r**2 + .587 * g**2 + .114 * b**2 ) *a/255 / 255

def findBytes( bytesRange, target ): # Searches a bytearray for a given (target) set of bytes, and returns the location (index)
	targetLength = len( target )

	for index, _ in enumerate( bytesRange ):
		if bytesRange[index:index+targetLength] == target: return index
	else: return -1

def cmdChannel( command, standardInput=None, shell=True ):
	
	""" IPC (Inter-Process Communication) to command line. 
		shell=True gives access to all shell features/commands, such dir or copy. 
		creationFlags=0x08000000 prevents creation of a console for the process. """

	process = subprocess.Popen( command, shell=shell, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=0x08000000 )
	stdoutData, stderrData = process.communicate( input=standardInput )

	if process.returncode == 0:
		return ( process.returncode, stdoutData )
	else:
		print 'IPC error (exit code {}):'.format( process.returncode )
		print stderrData
		return ( process.returncode, stderrData )

def replaceHex( hexData, offset, newHex ): # Input takes a string, int, and string, respectively. todo: finish depricating this
	offset = offset * 2 # Doubled to count by nibbles rather than bytes, since the data is just a string.
	codeEndPoint = offset + len(newHex)
	return hexData[:offset] + newHex + hexData[codeEndPoint:]

																				#=============================#
																				# ~ ~ Opening & Importing ~ ~ #
																				#=============================#

def openFolder( folderPath ):
	normedPath = os.path.abspath( folderPath ) # Turns relative to absolute paths, and normalizes them (switches / for \, etc.)

	if os.path.exists( normedPath ):
		os.startfile( normedPath )
	else: 
		msg( 'Could not find this folder: \n\n' + normedPath )


def loadSettings():
	# Check for user defined settings / persistent memory.
	if os.path.exists( settingsFile ): settings.read( settingsFile )

	# Create the individual sections if they don't already exist.
	if not settings.has_section('General Settings'): settings.add_section('General Settings')
	if not settings.has_section('Texture Search Filters'): settings.add_section('Texture Search Filters')

	# Set default settings if they were not loaded from the settings file, and validate the rest
	for settingName in generalSettingsDefaults:
		# If a default setting was not found in the settings file, set it to its default value
		if not settings.has_option( 'General Settings', settingName ): 
			settings.set( 'General Settings', settingName, generalSettingsDefaults[settingName] )

		# If the setting is present and should be a number, validate it.
		elif settingName == 'maxFilesToRemember' or settingName == 'globalFontSize' or settingName == 'paddingBetweenFiles':
			value = settings.get( 'General Settings', settingName )

			if settingName == 'maxFilesToRemember' or settingName == 'globalFontSize':
				if isNaN( value ):
					msg( 'The value for the saved setting "' + settingName + '" does not appear to be a number. '
						 'The default value of ' + generalSettingsDefaults[settingName] + ' will be used instead.', 
						 'Error Loading Settings' )
					settings.set( 'General Settings', settingName, generalSettingsDefaults[settingName] )

			elif settingName == 'paddingBetweenFiles' and value.lower() != 'auto':
				try: int( value, 16 )
				except:
					msg( 'The value for the saved setting "paddingBetweenFiles" is invalid. '
						'The value should be a hexadecimal number, or "auto". The default value '
						'of ' + generalSettingsDefaults[settingName] + ' will be used instead.', 
						'Error Loading Settings' )
					settings.set( 'General Settings', settingName, generalSettingsDefaults[settingName] )

		# Convert the filter string to its numeral representation.
		if settingName == 'downscalingFilter':
			validFilters = ( 'nearest', 'lanczos', 'bilinear', 'bicubic' )
			currentFilter = settings.get( 'General Settings', 'downscalingFilter' )

			if not currentFilter in validFilters: # Filter string unrecognized
				msg( "The given downscaling filter is invalid; valid options are 'nearest', 'lanczos', 'bilinear', or 'bicubic'. "
					 'The default value of ' + generalSettingsDefaults[settingName] + ' will be used instead.', 'Error Loading Settings' )
				settings.set( 'General Settings', settingName, generalSettingsDefaults[settingName] )

	for settingName in imageFiltersDefaults:
		if not settings.has_option('Texture Search Filters', settingName): 
			settings.set( 'Texture Search Filters', settingName, imageFiltersDefaults[settingName] )
		else:
			# Perform some validation on the setting's value (by making sure there is a comparator and separator)
			value = settings.get( 'Texture Search Filters', settingName )
			if '|' not in value or len( value.split('|')[0] ) > 2:
				msg( 'A problem was detected for the texture search filter setting, "' + settingName + '". The '
					 'default value of ' + generalSettingsDefaults[settingName] + ' will be used instead.', 'Error Loading Settings' )
				settings.set( 'Texture Search Filters', settingName, imageFiltersDefaults[settingName] )

	global generalBoolSettings
	for settingName in generalBoolSettingsDefaults:
		if not settings.has_option( 'General Settings', settingName ): 
			settings.set( 'General Settings', settingName, generalBoolSettingsDefaults[settingName] )

		if settingName not in generalBoolSettings: generalBoolSettings[ settingName ] = Tk.BooleanVar() # Should only occur on initial program start

		# These are a special set of control variables, BooleanVars(), which must be created separately/anew from the settings in the configParser settings object
		generalBoolSettings[settingName].set( settings.getboolean('General Settings', settingName) )

	# These values will have some post-processing done; so they will be initialized here so that the post-processing is done just once.
	global imageFilters
	for settingName in imageFiltersDefaults:
		if settingName == 'imageTypeFilter': charToReplace = '_'
		else: charToReplace = ','
		imageFilters[settingName] = tuple( settings.get( 'Texture Search Filters', settingName ).replace( charToReplace, '' ).split( '|' ) )


def getRecentFilesLists(): # Returns two lists of tuples (ISOs & DATs), where each tuple is a ( filepath, dateTimeObject )
	# Collect the current [separate] lists of recent ISOs, and recent DAT (or other) files.
	ISOs = []
	DATs = [] 
	
	if settings.has_section('Recent Files'):
		recentFiles = settings.options('Recent Files')
		for filepath in recentFiles:
			try:
				newDatetimeObject = datetime.strptime( settings.get('Recent Files', filepath), "%Y-%m-%d %H:%M:%S.%f" )
				optionTuple = ( filepath, newDatetimeObject ) # Tuple of ( normalizedPath, dateTimeObject ).

				ext = os.path.splitext( filepath )[1].lower()
				if ext == '.iso' or ext == '.gcm' or isRootFolder( filepath.replace('|', ':'), showError=False )[0]: 
					ISOs.append( optionTuple )
				else: DATs.append( optionTuple )
			except:
				removeEntry = tkMessageBox.askyesno( 'Error Parsing Settings File', 'The timestamp for one of the recently opened files, "' + filepath.replace('|', ':') + '", could not be read. '
													 'The settings file, or just this entry within it, seems to be corrupted.'
													 '\n\nDo you want to remove this item from the list of recently opened files?' )
				if removeEntry: settings.remove_option( 'Recent Files', filepath )
	return ISOs, DATs


def promptToOpenFile( typeToOpen ):

	""" This is primarily a wrapper for the 'Open Disc' and 'Open DAT' options in the main menu. """

	if typeToOpen == 'iso':
		titleString = "Choose an ISO or GCM file to open."
		filetypes = [('Disc image files', '*.iso *.gcm'), ('All files', '*.*')]
	else:
		titleString = "Choose a texture data file to open."
		filetypes = [('Texture data files', '*.dat *.usd *.lat *.rat'), ('All files', '*.*')]

	filepath = tkFileDialog.askopenfilename(
		title=titleString, 
		initialdir=settings.get( 'General Settings', 'defaultSearchDirectory' ),
		filetypes=filetypes
		)
	
	fileHandler( [filepath] ) # Will handle validation of the filepath.


def openDatDestination( event ):

	""" This is only called by pressing Enter/Return on the top file path display/entry of
		the DAT Texture Tree tab. Verifies given the path and loads the file for viewing. """

	filepath = Gui.datDestination.get().replace( '"', '' )

	if pathIsFromDisc( Gui.datDestination ):
		iid = filepath.lower()
		loadFileWithinDisc( iid )
	else:
		fileHandler( [filepath] )


def openIsoDestination( event ):

	""" This is only called by pressing Enter/Return on the top file path display/entry of
		the Disc Details tab. Verifies the given path and loads the file for viewing. """

	filepath = Gui.isoDestination.get().replace( '"', '' )

	if pathIsFromDisc( Gui.isoDestination ):
		iid = filepath.lower()
		loadFileWithinDisc( iid )
	else:
		fileHandler( [filepath] )


def rememberFile( filepath, updateDefaultDirectory=True ):

	""" Checks for the settings file and creates it as well as the 'Recent Files' section if they don't exist.
		Then saves the given filepath so it can be recalled later from the 'Open Recent' menu. """

	extension = os.path.splitext( filepath )[1].lower()
	filepath = os.path.normpath( filepath ) # Normalizes it to prevent duplicate entries
	timeStamp = str( datetime.today() )
	
	# If the settings file exists, and has more than max entries for the current file type, remove the extras
	if settings.has_section('Recent Files'):
		# Collect the current [separate] lists of recent ISOs, and recent DAT (or other) files.
		maxFiles = int( settings.get('General Settings', 'maxFilesToRemember') )
		ISOs, DATs = getRecentFilesLists()

		# For the current filetype, sort the list so that the oldest file is first
		if extension == '.iso' or extension == '.gcm' or isRootFolder( filepath )[0]: targetList = ISOs
		else: targetList = DATs
		targetList.sort( key=lambda recentInfo: recentInfo[1] )

		# Remove the oldest file(s) from the settings file until the specified max number of files to remember is reached.
		while len( targetList ) > maxFiles - 1: 
			settings.remove_option( 'Recent Files', targetList[0][0] )
			targetList.pop( 0 )

	# Update the default search directory.
	if updateDefaultDirectory:
		dirPath = os.path.dirname( filepath )
		settings.set( 'General Settings', 'defaultSearchDirectory', dirPath )

	if not settings.has_section('Recent Files'): settings.add_section('Recent Files')
	settings.set( 'Recent Files', filepath.replace(':', '|'), timeStamp ) # Colon is replaced because it confuses the settings parser.

	# Save the current program settings to the file
	with open( settingsFile, 'w') as theSettingsFile: settings.write( theSettingsFile )


def fileHandler( filepaths, dropTarget='', updateDefaultDirectory=True, updateDetailsTab=True ):

	""" All opened standalone ISO & DAT files should pass through this (regardless of whether it was from dra-and-drop,
		file menu, or other methods), with the exception of files viewed with the 'prev/next DAT' buttons. """

	if filepaths == [] or filepaths == ['']: return

	elif len( filepaths ) == 1:
		extension = os.path.splitext( filepaths[0] )[1].lower()
		mostOccuringTypes = [extension]

	else:
		# Figure out the most common type of file among the filepaths (which should be a list) to determine how the group should be processed.
		typeCounts = {}
		for filepath in filepaths:
			ext = os.path.splitext( filepath )[1].lower()
			if ext in typeCounts: typeCounts[ext] += 1
			else: typeCounts[ext] = 1
		maxUniqueOccurances = max( typeCounts.values() )
		mostOccuringTypes = [ x for x, y in typeCounts.items() if y == maxUniqueOccurances ]

	# Normalize the paths (prevents discrepancies between paths with forward vs. back slashes, etc.) and remove files that cannot be found.
	filepaths = [ os.path.normpath( filepath ) for filepath in filepaths ]
	verifiedPaths = []
	unverifiedPaths = []
	for filepath in filepaths:
		if os.path.exists( filepath ): verifiedPaths.append( filepath )
		else: unverifiedPaths.append( filepath )

	# Alert the user of any files that could not be found.
	if unverifiedPaths: 
		if len(unverifiedPaths) == 1:
			msg( 'Unable to find "' + unverifiedPaths[0] + '".', 'Error: Unverifiable Path' )
		else: msg( 'Unable to find these files:\n\n' + '\n'.join( unverifiedPaths ), 'Error: Unverifiable Paths' )
	if verifiedPaths == []: return

	global globalDatFile, globalBannerFile
	currentTab = Gui.root.nametowidget( Gui.mainTabFrame.select() )

	# If there's only one file and it's a disc image (ISO or GCM), process it without regard for which tab is currently active.
	if len( verifiedPaths ) == 1 and ( extension == '.iso' or extension == '.gcm' ):
		# Check whether there are changes that the user wants to save
		if globalBannerFile and not globalBannerFile.noChangesToBeSaved( programClosing ): return
		elif not noDiscChangesToBeSaved(): return

		# Clear old DAT data if it's from a previously loaded disc
		elif globalDatFile and globalDatFile.source == 'disc':
			if not globalDatFile.noChangesToBeSaved( programClosing ): return
			else: # No changes that the user wants to save; OK to clear the DAT file.
				restoreEditedEntries( editedDatEntries )
				clearDatTab( True )
				clearStructuralAnalysisTab( True )
				globalDatFile = None
				Gui.datDestination.set('')

		# Clear old banner file
		globalBannerFile = None
		restoreEditedEntries( editedBannerEntries )

		rememberFile( verifiedPaths[0], updateDefaultDirectory )
		globalDiscDetails['isoFilePath'] = verifiedPaths[0]

		scanDisc( updateDetailsTab=updateDetailsTab )

	elif '.iso' in mostOccuringTypes or '.gcm' in mostOccuringTypes:
		msg('Please only provide one disc image (ISO or GCM file) at a time.')
		
	# If there's only one path and it's not an image/texture file
	elif len( verifiedPaths ) == 1 and extension != '.png' and extension != '.tpl':
		thisFile = verifiedPaths[0]

		# Check if it's a disc root directory.
		if os.path.isdir( thisFile ):
			if isRootFolder( thisFile, showError=False )[0]:
				rememberFile( thisFile, updateDefaultDirectory )
				globalDiscDetails['isoFilePath'] = thisFile
				scanRoot( updateDetailsTab=updateDetailsTab )
			else:
				msg( 'Only extracted root directories are able to opened in this way.' )
				return

		elif extension == '.bnr' : # A banner was given. Switch to the Disc Details tab and load it.
			if not globalBannerFile or (globalBannerFile and globalBannerFile.noChangesToBeSaved( programClosing ) ): # i.e. no file has been loaded, or it's OK to overwrite
				restoreEditedEntries( editedBannerEntries )
				rememberFile( thisFile, updateDefaultDirectory )

				loadStandaloneFile( thisFile )

		# Assume it's some form of DAT
		elif not globalDatFile or (globalDatFile and globalDatFile.noChangesToBeSaved( programClosing ) ): # i.e. no file has been loaded, or it's OK to overwrite

			# Perform some rudimentary validation; if it passes, remember it and load it
			if os.path.getsize( thisFile ) > 20971520: # i.e. 20 MB
				msg("The recieved file doesn't appear to be a DAT or other type of texture file, as it's larger than 20 MB. "
					"If this is actually supposed to be a disc image, rename the file with an extension of '.ISO' or '.GCM'.")
			else:
				restoreEditedEntries( editedDatEntries )
				rememberFile( thisFile, updateDefaultDirectory )

				#if dropTarget == '': # Called from a menu, or drag-n-dropped onto the program icon; not dropped onto the GUI.

				if currentTab == Gui.savTab:
					loadStandaloneFile( thisFile, toAnalyze=True, changeTab=False )

				# elif currentTab == Gui.cccTab and dropTarget == '': # Case where the 'Open Converted File' button on the CCC tab is used.
				# 	loadStandaloneFile( thisFile, tabToChangeTo=Gui.datTab )

				elif dropTarget.startswith('cccTab'):
					# Get the DAT data and relocation table from the target file.
					with open( thisFile, 'rb') as binaryFile:
						datHex = binaryFile.read().encode( 'hex' )

					prepareColorConversion( thisFile, datHex, dropTarget[6:].lower() )

				else:
					loadStandaloneFile( thisFile )

	# Process images.
	elif len( verifiedPaths ) == 1 and ( extension == '.png' or extension == '.tpl' ): processTextureImports( verifiedPaths, currentTab )
	elif '.png' in mostOccuringTypes or '.tpl' in mostOccuringTypes: processTextureImports( verifiedPaths, currentTab )
	else:
		msg('Please only provide one data file (DAT, USD, etc.) or root folder at a time. \n\nFor textures, only PNG and TPL file formats are supported.')


def importImageFiles( event=None ):
	currentlySelectedTab = Gui.root.nametowidget( Gui.mainTabFrame.select() )

	if currentlySelectedTab == Gui.discTab or currentlySelectedTab == Gui.mtrTab: 
		title = "Choose one or more texture files to import (PNG or TPL)."
		selectMultiple = True

	elif currentlySelectedTab == Gui.discDetailsTab:
		# Preliminary check that there's a banner file loaded.
		if not globalBannerFile:
			msg( 'No banner file or disc appears to be loaded.', 'Cannot Import Banner Image' )
			return

		title = "Choose a 96x32 banner image to import (PNG or TPL)."
		selectMultiple = False

	elif currentlySelectedTab == Gui.datTab:
		if Gui.datTextureTree.selection() == '': 
			msg( 'You must select one or more textures to replace when importing textures with this tab.' + \
				 "\n\nIf you'd like to use the filename to automatically dictate where this texture will go, change to the 'Disc File Tree' tab " + \
				 'and try this operation again.', 'No Texture Selected. Cannot import texture.' )
			return

		title = "Choose a texture file to import (PNG or TPL)."
		selectMultiple = False

	else: 
		msg( 'You may only import textures while using the Disc File Tree tab, DAT Texture Tree tab, '
			 'or the Manual Replacement tab.' )
		return

	# Prompt to select the file to import.
	textureFilepaths = tkFileDialog.askopenfilename( # Will return a unicode string (if one file selected), or a tuple
		title=title, 
		initialdir=settings.get( 'General Settings', 'defaultSearchDirectory' ),
		filetypes=[ ('PNG files', '*.png'), ('TPL files', '*.tpl'), ('All files', '*.*') ],
		multiple=selectMultiple
		)

	if textureFilepaths:
		# Normalize the input into list form
		if not isinstance( textureFilepaths, list ) and not isinstance( textureFilepaths, tuple ): 
			textureFilepaths = [textureFilepaths]

		# Update the default directory to start in when opening or exporting files.
		settings.set( 'General Settings', 'defaultSearchDirectory', os.path.dirname(textureFilepaths[0]) )
		with open( settingsFile, 'w') as theSettingsFile: settings.write( theSettingsFile )

		processTextureImports( textureFilepaths, currentlySelectedTab )


def processTextureImports( textureFilepaths, currentlySelectedTab, warnAboutPaletteRegen=True ):
	global unsavedDiscChanges

	unconventionalNames = []
	filesNotFoundInDisc = []
	formatUnsupported = []
	imageHeaderNotFound = []
	imageTypeNotFound = []
	invalidDimensions = []
	invalidMipmapDims = []
	invalidImageProperties = []
	invalidPaletteProperties = []
	notEnoughSpace = []
	paletteRegenerated = []
	paletteTooLarge = []
	paletteNotFound = []
	unknownErrors = []

	successfulImports = 0
	failedImports = 0

	# Determine import behavior by checking what tab is selected.
	if currentlySelectedTab == Gui.discTab:
		if globalDiscDetails['isoFilePath'] == '': 
			msg( 'No disc image has been loaded.' )
			return
		else:
			datIidToReload = ''
			workingFile = 1
			gameId = globalDiscDetails['gameId'].lower()

			for textureFilepath in textureFilepaths:
				# Update the GUI status feedback.
				updateProgramStatus( 'Processing File ' + str(workingFile) + '....' )
				Gui.programStatusLabel.update()
				workingFile += 1

				# Validate the filename; confirm that it's of the standard naming convention and parse it for info.
				imageType, imageDataOffset, sourceFile = codecBase.parseFilename( os.path.basename( textureFilepath ) )
				iid = ( gameId + '/' + sourceFile.replace( '-', '/' ) ).lower()

				if imageType == -1 or imageDataOffset == -1 or sourceFile == '': 
					unconventionalNames.append( textureFilepath )
					failedImports += 1
				elif not Gui.isoFileTree.exists( iid ):
					filesNotFoundInDisc.append( (textureFilepath, sourceFile.replace( '-', '/' )) )
					failedImports += 1
				else:
					# Get info on the target file and load it
					_, entity, isoOffset, fileSize, isoPath, _, _ = Gui.isoFileTree.item( iid, 'values' )
					try:
						thisDat = hsdFiles.datFileObj( source='disc' )
						thisDat.load( iid, fileData=getFileDataFromDiscTreeAsBytes( iid=iid ), fileName=os.path.basename( isoPath ) )
					except:
						unknownErrors.append( (textureFilepath, 'fileLoadError') )
						continue

					# Write the image data into the target file
					status, return2, return3 = writeTextureToDat( thisDat, textureFilepath, imageDataOffset - 0x20, False )

					if status == 'dataObtained' or status == 'dataWithAdHocPalette' or status == 'paletteRegenerated': # or status == 'invalidDimensions'
						# The write operation was a success. Save the new file data
						newFileData = hexlify( thisDat.getFullData() )
						Gui.isoFileTree.item( iid, values=('Includes updated textures', entity, isoOffset, fileSize, isoPath, 'ram', newFileData), tags='changed' )

						# Check if the dat currently loaded in the DAT Texture Tree tab has been updated with a new texture, and queue it for reloading if it has
						if not datIidToReload and globalDatFile and globalDatFile.source == 'disc' and globalDatFile.path.lower() == iid: 
							datIidToReload = iid

						# Remember notices to the user, to present once the import loop is finished.
						if status == 'paletteRegenerated' or status == 'dataWithAdHocPalette':
							paletteRegenerated.append( textureFilepath ) # Successful, but had to create a new palette / image colors
						successfulImports += 1

					else:
						# Remember errors to the user, to present once the import loop is finished.
						imageDataOffset = uHex( imageDataOffset ) # This already includes 0x20 header offset
						if status == 'formatUnsupported': formatUnsupported.append( textureFilepath )
						elif status == 'imageHeaderNotFound': imageHeaderNotFound.append( (textureFilepath, imageDataOffset) )
						elif status == 'imageTypeNotFound': imageTypeNotFound.append( textureFilepath )
						elif status == 'invalidDimensions': invalidDimensions.append( (textureFilepath, False) )
						elif status == 'invalidMipmapDims': invalidMipmapDims.append( textureFilepath )
						elif status == 'invalidImageProperties': invalidImageProperties.append( (textureFilepath, imageDataOffset, return2, return3) )
						elif status == 'invalidPaletteProperties': invalidPaletteProperties.append( (textureFilepath, imageDataOffset, return2, return3) )
						elif status == 'notEnoughSpace': notEnoughSpace.append( (textureFilepath, imageDataOffset) )
						elif status == 'paletteTooLarge': paletteTooLarge.append( (textureFilepath, imageDataOffset, return2, return3) )
						elif status == 'paletteNotFound': paletteNotFound.append( textureFilepath )
						else: unknownErrors.append( (textureFilepath, status) )
						failedImports += 1

			# Finished iterating over the imported texture filepaths.

			# Record that textures were updated for the current disc
			if successfulImports > 0:
				if successfulImports == 1: unsavedDiscChanges.append( '1 texture imported via Disc Import Method.' )
				else: unsavedDiscChanges.append( str(successfulImports) + ' textures imported via Disc Import Method.' )

			# Reload the DAT currently loaded in the DAT Texture Tree tab if it has had any of it's textures changed by this import method.
			if datIidToReload and Gui.datTextureTree.get_children():
				if globalDatFile.unsavedChanges:
					warning = ( '"' + globalDatFile.path.split('/')[-1] + '" has been updated in the disc, however, the copy of it in the DAT Texture Tree '
								'tab still has unsaved changes. Do you want to discard these changes and load the new file?' )
					if tkMessageBox.askyesno( 'Unsaved Changes', warning ):
						globalDatFile.unsavedChanges = []
						loadFileWithinDisc( datIidToReload, changeTab=False )
				else: 
					loadFileWithinDisc( datIidToReload, changeTab=False )

	elif currentlySelectedTab == Gui.discDetailsTab: # For banners
		if len( textureFilepaths ) > 1: 
			msg( "You may only import one banner at a time.", 'Too Many Files Imported' )
		else:
			textureFilepath = textureFilepaths[0]

			if not globalBannerFile or not globalBannerFile.data:
				msg( 'No banner file or disc appears to be loaded.', 'Cannot Import Banner Image' )
			else:
				status, return2, return3 = writeTextureToDat( globalBannerFile, textureFilepath, 0x20, False )

				if status == 'dataObtained' or status == 'dataWithAdHocPalette' or status == 'paletteRegenerated':
					if globalBannerFile.source == 'disc':
						bannerIid = globalBannerFile.path
						newBannerData = hexlify( globalBannerFile.data )
						_, entity, isoOffset, fileSize, isoPath, _, _ = Gui.isoFileTree.item( bannerIid, 'values' )
						Gui.isoFileTree.item( bannerIid, values=('Banner replaced', entity, isoOffset, fileSize, isoPath, 'ram', newBannerData), tags='changed' )
						unsavedDiscChanges.append( 'Game banner image updated' )
					else: # source = 'file'; i.e. it's a standalone file not from a disc
						globalBannerFile.unsavedChanges.append( 'Game banner image updated' )

					# Remember notices to the user, to present once the import loop is finished.
					if status == 'paletteRegenerated' or status == 'dataWithAdHocPalette': 
						paletteRegenerated.append( textureFilepath ) # Successful, but had to create a new palette / image colors

					successfulImports += 1

					# Update the GUI wth the new image
					updateBannerFileInfo( updateTextEntries=False ) # First arg: don't want to clear any other user data that might have been modified.
				else:
					# Remember errors to the user, to present once the import loop is finished.
					if status == 'formatUnsupported': formatUnsupported.append( textureFilepath )
					elif status == 'imageHeaderNotFound': imageHeaderNotFound.append( (textureFilepath, '0x20') )
					elif status == 'imageTypeNotFound': imageTypeNotFound.append( textureFilepath )
					elif status == 'invalidDimensions': invalidDimensions.append( (textureFilepath, True) )
					elif status == 'notEnoughSpace': notEnoughSpace.append( (textureFilepath, '0x20') )
					elif status == 'paletteTooLarge': paletteTooLarge.append( (textureFilepath, '0x20', return2, return3) )
					elif status == 'paletteNotFound': paletteNotFound.append( textureFilepath )
					else: unknownErrors.append( (textureFilepath, status) )
					failedImports += 1

	elif currentlySelectedTab == Gui.datTab: # DAT Texture Tree direct imports
		iidSelectionsTuple = Gui.datTextureTree.selection()

		# Compose an error message if the inputs are invalid.
		inputErrorMsg = ''
		if not iidSelectionsTuple: 
			# This check is repeated from importImageFiles() because there are other ways files may be given to this function.
			inputErrorMsg = 'You must select one or more textures to replace when importing textures on this tab.'
			title = 'No Textures Selected'
		elif len( textureFilepaths ) > 1: # isinstance( textureFilepaths, list) and 
			inputErrorMsg = "You may only import one texture at a time using this tab."
			title = 'Too Many Files Imported'

		if inputErrorMsg:
			inputErrorMsg += "\n\nIf you'd like to import multiple textures to a standalone file (one not in a disc), then you can use the 'Manual Placement' tab. " + \
				"Or, if you'd like to import one or more textures straight into a disc (using the filename to automatically dictate where each will go), " + \
				"select the 'Disc File Tree' tab and try this operation again."
			msg( inputErrorMsg, title )
		else:
			textureFilepath = textureFilepaths[0]
			
			# Update the textures in the treeview (preview/full images, info, and data in the globalDatFile object)
			for iid in iidSelectionsTuple: # Import the given texture (should only be one being imported in this case) to replace all selected textures. (int(iid)=imageDataOffset)
				imageDataOffset = int( iid )
				status, return2, return3 = writeTextureToDat( globalDatFile, textureFilepath, imageDataOffset, True )
				print 'texture-write operation status:', status

				if status == 'dataObtained' or status == 'dataWithAdHocPalette' or status == 'paletteRegenerated': # Success
					# Remember notices to the user, to present once the import loop is finished.
					if status == 'paletteRegenerated' or status == 'dataWithAdHocPalette': 
						paletteRegenerated.append( textureFilepath ) # Successful, but had to create a new palette / image colors
					successfulImports += 1

					# Refresh the GUI (the texture display and all datTab tabs) if this is the currently displayed texture (last item in selection).
					if iid == iidSelectionsTuple[-1]: onTextureTreeSelect( '', iid=iidSelectionsTuple )

				else:
					# Remember errors to the user, to present once the import loop is finished.
					compensatedImageDataOffset = uHex( 0x20 + imageDataOffset )
					if status == 'formatUnsupported': formatUnsupported.append( textureFilepath )
					elif status == 'imageHeaderNotFound': imageHeaderNotFound.append( (textureFilepath, compensatedImageDataOffset) )
					elif status == 'imageTypeNotFound': imageTypeNotFound.append( textureFilepath )
					elif status == 'invalidDimensions': invalidDimensions.append( (textureFilepath, False) )
					elif status == 'invalidMipmapDims': invalidMipmapDims.append( textureFilepath )
					elif status == 'invalidImageProperties': invalidImageProperties.append( (textureFilepath, compensatedImageDataOffset, return2, return3) )
					elif status == 'invalidPaletteProperties': invalidPaletteProperties.append( (textureFilepath, compensatedImageDataOffset, return2, return3) )
					elif status == 'notEnoughSpace': notEnoughSpace.append( (textureFilepath, compensatedImageDataOffset) )
					elif status == 'paletteTooLarge': paletteTooLarge.append( (textureFilepath, compensatedImageDataOffset, return2, return3) )
					elif status == 'paletteNotFound': paletteNotFound.append( textureFilepath )
					else: unknownErrors.append( (textureFilepath, status) )
					failedImports += 1

	elif currentlySelectedTab == Gui.mtrTab: showSelectedPaths( textureFilepaths )
	elif currentlySelectedTab == Gui.cccTab: msg( 'Only character texture files are accepted here\n(e.g. .DAT, .USD, .LAT, etc.)' )
	
	# Prepare an error message for any errors observed.
	correctDimensions = 'The dimensions for a game banner should be 96 x 32. The width and height for standard textures should each not exceed 1024, and should be a multiple of 2. '
	if failedImports > 0:
		compoundImportErrorsMessage = ''

		if len( textureFilepaths ) == 1: updateProgramStatus( 'Import Failed' )
		else:
			if successfulImports == 0:
				updateProgramStatus( 'Imports Failed' )
				compoundImportErrorsMessage = 'No textures could be imported. '
			else: # Some were successful, while some failed. Get counts of each
				updateProgramStatus( 'Some Imports Failed' )
				if successfulImports == 1: compoundImportErrorsMessage = '1 texture was successfully imported. '
				else: compoundImportErrorsMessage = str(successfulImports) + ' textures were successfully imported. '

				if failedImports == 1: compoundImportErrorsMessage += 'However, 1 import failed.'
				else: compoundImportErrorsMessage += 'However, ' + str(failedImports) + ' imports failed.'

		if unconventionalNames:
			if len( unconventionalNames ) == 1: compoundImportErrorsMessage += ( '\n\n"' + os.path.basename( unconventionalNames[0] ) + '" could not be processed by '
				"this import method because it doesn't appear to be using the standard naming convention. Ignoring extension, the standard naming convention is "
				""""[sourceFile]_[textureOffset]_[textureType]". For example, "MnMaAll.usd_0x70580_0" or even "[your notes]_MnMaAll.usd_0x70580_0". As an alternative to renaming it, """
				"you can import it using the DAT File Tree tab, which doesn't care about the image file's name." )
			else: compoundImportErrorsMessage += ( "\n\nThe files below could not be processed by this import method because they don't "
				"""appear to be using the standard naming convention. Ignoring extension, the standard naming convention is "[sourceFile]_[textureOffset]_[textureType]". """ 
				"""For example, "MnMaAll.usd_0x70580_0" or even "[your notes]_MnMaAll.usd_0x70580_0". As an alternative to renaming them, """
				"you can individually import them using the DAT File Tree tab, which doesn't care about the image files' names.\n\n" + '\n'.join(unconventionalNames) )

		if filesNotFoundInDisc:
			if len( filesNotFoundInDisc ) == 1: compoundImportErrorsMessage += '\n\n"' + os.path.basename( filesNotFoundInDisc[0][0] ) + \
									' could not be imported because the game file "' + filesNotFoundInDisc[0][1] + '" was not found in the disc.'
			else: compoundImportErrorsMessage += "\n\nSome textures couldn't be imported because the following game files were not found in the disc:\n\n" + \
									'\n'.join( [failedImport[1] for failedImport in filesNotFoundInDisc] )
		if formatUnsupported:
			if len( formatUnsupported ) == 1: compoundImportErrorsMessage += ( '\n\n"' + os.path.basename( formatUnsupported[0] ) + """" couldn't be imported because something """ + \
									"indicates that it's not actually a TPL or PNG file (you might want to double-check the file extension, or try getting a new copy of the texture)." )
			else: compoundImportErrorsMessage += ( """\n\nThe following files couldn't be imported because something indicates that they're not in TPL or PNG format """ + \
									"(you might want to double-check the file extensions, or try getting a new copy of the textures):\n\n" + '\n'.join(formatUnsupported) )
		if imageHeaderNotFound:
			if len( imageHeaderNotFound ) == 1: compoundImportErrorsMessage += ( '\n\n"' + os.path.basename( imageHeaderNotFound[0][0] ) + '" could not be imported because the offset '
									'appears to be incorrect. No image data headers could be found for the data at its assigned destination (at ' + imageHeaderNotFound[0][1] + ")." )
			else: compoundImportErrorsMessage += ( '\n\nThe following files could not be imported because their offsets appear to be incorrect (no image data headers '
									"could be found for them at their assigned destination):\n\n" + '\n'.join([failedImport[0] for failedImport in imageHeaderNotFound]) )
		if imageTypeNotFound: # Is this case possible (should be irrelevant or caught by unconventionalNames)?
			if len( imageTypeNotFound ) == 1: compoundImportErrorsMessage += ( '\n\nA texture type or palette type could not be determined for "' + os.path.basename( imageTypeNotFound[0] ) + '".' )
			else: compoundImportErrorsMessage += ( '\n\nThe following files could not be imported because a texture type or palette type could not be determined:\n\n' + '\n'.join(imageTypeNotFound) )
		if invalidDimensions:
			if invalidDimensions[0][1]: correctDimensions = 'The dimensions for a game banner should be 96x32 pixels. ' # Checks bool packaged with texture path to see if it's a banner (import on disc details tab)
			else: correctDimensions = 'The width and height for standard textures should not exceed 1024, and should be a multiple of 2. '
			if len( invalidDimensions ) == 1: compoundImportErrorsMessage += ( '\n\n"' + os.path.basename( invalidDimensions[0][0] ) + '" has invalid image dimensions. ' + correctDimensions )
			else: compoundImportErrorsMessage += ( '\n\nThe textures below do not have valid dimensions. ' + correctDimensions + '\n\n' + '\n'.join([failedImport[0] for failedImport in invalidDimensions]) )
		if invalidMipmapDims:
			if len( invalidMipmapDims ) == 1: compoundImportErrorsMessage += ( '\n\n"' + os.path.basename( invalidMipmapDims[0] ) + '" could not be imported because its dimensions '
																					"don't match the mipmap level you are trying to replace." )
			else: compoundImportErrorsMessage += ( "\n\nThe following textures could not be imported because their dimensions don't match the mipmap levels they are assigned to replace." + \
														'\n\n' + '\n'.join( invalidMipmapDims ) )
		if invalidImageProperties:
			if len( invalidImageProperties ) == 1:
				filePath, imageDataOffset, origWidthHeight, origImageType = invalidImageProperties[0]
				origWidth, origHeight = origWidthHeight
				compoundImportErrorsMessage += ( '\n\n"' + os.path.basename( filePath ) + '" could not be imported to replace the texture at ' + imageDataOffset + \
												 ' because it has invalid properties (width, height, or image type). Because there is no image data header in the DAT file '
												 'for this texture, the new texture to replace it must be {}x{}, with an image type of _{}'.format(origWidth, origHeight, origImageType) )
			else: compoundImportErrorsMessage += ( "\n\nThe following textures could not be imported because they have invalid properties (width, height, or image type) for the "
									'specific textures they are meant to replace (they must match the original texture):\n\n' + '\n'.join([failedImport[0] for failedImport in invalidImageProperties]) )
		if invalidPaletteProperties:
			if len( invalidPaletteProperties ) == 1:
				filePath, imageDataOffset, origPaletteType, newPaletteType = invalidPaletteProperties[0]
				compoundImportErrorsMessage += ( '\n\n"' + os.path.basename( filePath ) + '" could not be imported to replace the texture at ' + imageDataOffset + \
												 ' because it has an invalid palette type. Because there is no image data header in the DAT file '
												 'for this texture, the new texture to replace it must have an image type of {}, however it had a palette type of {}.'.format(origPaletteType, newPaletteType) )
			else: compoundImportErrorsMessage += ( "\n\nThe following textures could not be imported because they have invalid palette types for the "
									'specific textures they are meant to replace (they must match the original texture):\n\n' + '\n'.join([failedImport[0] for failedImport in invalidPaletteProperties]) )
		if notEnoughSpace:
			if len( notEnoughSpace ) == 1: compoundImportErrorsMessage += ( '\n\nAfter conversion, the data for "' + os.path.basename( notEnoughSpace[0][0] ) + '" was too large to '
									'replace the texture at ' + notEnoughSpace[0][1] + ". The cause could be the image type (which may be "
									'specified in the file name; e.g. the "_3" in "MnSlChr.dat_0x51c0_3"), or that the image has the wrong dimensions.' )
			else: compoundImportErrorsMessage += ( '\n\nThe following files could not be imported because, after conversion, their data was larger than that of the textures they '
									'are assigned to replace. The cause could be the image type (which may be specified in the file name; e.g. the "_3" in "MnSlChr.dat_0x51c0_3"), '
									'or that the images have the wrong dimensions.\n\n' + '\n'.join([failedImport[0] for failedImport in notEnoughSpace]) )
		if paletteRegenerated and warnAboutPaletteRegen:
			if len( paletteRegenerated ) == 1: compoundImportErrorsMessage += ( '\n\nThe original color palette in "' + os.path.basename( paletteRegenerated[0] ) + """" was too large for the texture it """ +
							"was assigned to replace. So a new palette was generated for it, and the texture was successfully imported. However, this may have slightly altered the texture's colors. "
							"(If you'd like to avoid this, create a palette for the texture yourself that does not exceed the max number of colors for this texture.)" )
			else: compoundImportErrorsMessage += ( '\n\nThe original color palettes in the files below were too large for the textures they were assigned to replace. So new palettes were '
							"generated for them, and they were successfully imported. However, this may have slightly altered the textures' colors. If you'd like to avoid this, create palettes "
							"for the textures yourself that do not exceed the max number of colors for each respective texture.)\n\n" + '\n'.join(paletteRegenerated) )
		if paletteTooLarge:
			if len( paletteTooLarge ) == 1:
				filepath, imageDataOffset, curPaletteColorCount, newPaletteColorCount = paletteTooLarge[0]
				compoundImportErrorsMessage += ( '\n\nThe color palette in "' + os.path.basename( filepath ) + '" is too large for '
												 'the texture at "' + imageDataOffset + ". The new texture has " + newPaletteColorCount + " colors in its palette, "
												 "while the destination file only has space for " + curPaletteColorCount + " colors." )
			else: compoundImportErrorsMessage += (  '\n\nThe following files could not be imported because their color palettes are larger than those of the textures '
													'they are assigned to replace:\n\n' + '\n'.join([failedImport[0] for failedImport in paletteTooLarge]) )
		if paletteNotFound:
			if len( paletteNotFound ) == 1: compoundImportErrorsMessage += ( '\n\n"' + os.path.basename( paletteNotFound[0] ) + '" could not be imported because '
										'the location of the color palette in the destination file could not be found.' )
			else: compoundImportErrorsMessage += ( '\n\nThe following files could not be imported because the locations of their color palettes in the destination '
										'file(s) could not be found:\n\n' + '\n'.join(paletteNotFound) )
		if unknownErrors:
			if len( unknownErrors ) == 1: 
				compoundImportErrorsMessage += ( '\n\n"' + os.path.basename( unknownErrors[0][0] ) + '" could not be imported due to an unknown error.\n\nStatus Code: ' + unknownErrors[0][1] )
			else: compoundImportErrorsMessage += ( '\n\nThe following files could not be imported due to unknown errors:\n\n' + '\n'.join([failedImport[0] for failedImport in unknownErrors]) )

		# Display the completed error message summary, and prompt to regenerate any invalid palettes.
		regeneratePalettes = False
		if paletteTooLarge and len( textureFilepaths ) == 1: # This was the only texture that was imported.
			if tkMessageBox.askyesno( 'Re-generate Palette?', compoundImportErrorsMessage.lstrip() + '\n\nWould you like to enable the option "Regenerate Invalid Palettes" and attempt to re-import it?' ):
				regeneratePalettes = True
		else:
			cmsg( compoundImportErrorsMessage.lstrip(), 'Import Errors', makeModal=True ) # lstrip will trim leading whitespace if there is any

			if paletteTooLarge and tkMessageBox.askyesno( 'Re-generate Palettes?', 'For the texture imports that failed due to invalid palette sizes (having a palette with too many colors), '\
				'would you like to enable the option "Regenerate Invalid Palettes" and attempt to re-import them?' ): regeneratePalettes = True

		if regeneratePalettes:
			global generalBoolSettings
			# Turn on the setting to regenerate invalid palettes, and save it (must be saved now, 
			# because the settings in the menu are refreshed from the file each time the menu is opened)
			generalBoolSettings['regenInvalidPalettes'].set( True )
			saveSettingsToFile()

			# Run the failed imports (those due to their palettes) back through the import functions.
			processTextureImports( [failedImport[0] for failedImport in paletteTooLarge], currentlySelectedTab, warnAboutPaletteRegen=False )

	else: # All imports successful
		if successfulImports == 1: updateProgramStatus( 'Import Successful' )
		elif successfulImports > 1: updateProgramStatus( 'Imports Successful' )

		warnings = ''
		if invalidDimensions:
			#if invalidDimensions[0][1]: correctDimensions = 'The dimensions for a game banner should be 96 x 32. '
			#else: correctDimensions = 'The width and height for standard textures should not exceed 1024. '

			if len( invalidDimensions ) == 1: warnings += ( os.path.basename( invalidDimensions[0][0] ) + '" may have invalid image dimensions. ' + correctDimensions + \
															'The texture was still imported successfully, but it might cause problems in-game.' )
			else: warnings += ( 'The textures below might not have valid dimensions. ' + correctDimensions + 'The textures were still imported successfully, but ' + 
								'they might cause problems in-game.\n\n' + '\n'.join([failedImport[0] for failedImport in invalidDimensions]) )

		if paletteRegenerated and warnAboutPaletteRegen:
			if len( paletteRegenerated ) == 1: warnings += ( '\n\nThe original color palette in "' + os.path.basename( paletteRegenerated[0] ) + """" was too large for the texture it """ +
							"was assigned to replace. So a new palette was generated for it, which may have slightly altered the texture's colors. (If you'd like to avoid this, create a palette "
							'for the texture yourself that does not exceed the max number of colors for this texture.)', 'Palettes Regenerated' )
			else: warnings += ( '\n\nThe original color palettes in the files below were too large for the textures they were assigned to replace. So new palettes were '
							"generated for them, which may have slightly altered the textures' colors. (If you'd like to avoid this, create palettes for the textures "
							'yourself that do not exceed the max number of colors for each respective texture.)\n\n' + '\n'.join(paletteRegenerated), 'Palettes Regenerated' )

		if not warnAboutPaletteRegen: # This means that failed imports due to palette size were re-attempted and [since executing here] successful. Notify that it worked, but others were not re-attempted.
			warnings += ( '\n\nThe palette regeneration and texture import was successful. (Any other textures that may have failed the previous import were not re-attempted.)' )

		if warnings: cmsg( warnings.lstrip(), 'Warning' ) #todo; the invalidDimensions status on a particular texture will override the paletteRegenerated status; this should be fixed. make status a list?


																				#============================#
																				# ~ ~ Saving & Exporting ~ ~ #
																				#============================#
																				
def saveDiscAs():

	""" Called by the 'Save Disc As...' option. Prompts the user for a filename and location to save a new disc image. """

	discFilePath = globalDiscDetails['isoFilePath']
	discFileName = os.path.basename( discFilePath )
	ext = os.path.splitext( discFilePath )[1].replace('.', '')

	# Prompt for a place to save the file.
	savePath = tkFileDialog.asksaveasfilename(
		title="Where would you like to export the disc file?", 
		initialdir=settings.get( 'General Settings', 'defaultSearchDirectory' ),
		initialfile=discFileName,
		defaultextension=ext,
		filetypes=[('Standard disc image', '*.iso'), ('GameCube disc image', '*.gcm'), ("All files", "*.*")]
	)

	if savePath:
		# Update the default directory to start in when opening or exporting files.
		dirPath = os.path.dirname( savePath )
		settings.set( 'General Settings', 'defaultSearchDirectory', dirPath )
		with open( settingsFile, 'w') as theSettingsFile: settings.write( theSettingsFile )

		saveChanges( newDiscPath=savePath )


def saveChanges( newDiscPath='' ):

	""" Saves unsaved changes to the currently loaded DAT or banner file, and/or the disc. 
	
		If the DAT or banner is a standalone file (not loaded from a disc), it will only
		be saved if the user is currently on that tab (DAT Texture Tree tab or Disc Details
		tab, respectively), in which case the disc will not be affected/saved. The disc 
		will be saved in all other cases (i.e. no DAT/banner has changes, or they do have 
		changes and the file resides in the disc). """

	global unsavedDiscChanges
	saveSuceeded = False
	currentTab = Gui.root.nametowidget( Gui.mainTabFrame.select() )

	# Save the currently loaded DAT's changes first (in case it needs to go into a disc that's waiting to save changes)
	if globalDatFile and globalDatFile.unsavedChanges:
		filepath = globalDatFile.path

		if globalDatFile.source == 'disc': # The file was loaded from the currently loaded disc image.
			iid = filepath.lower()
			_, entity, isoOffset, fileSize, isoPath, _, _ = Gui.isoFileTree.item( iid, 'values' )
			Gui.isoFileTree.item( iid, values=('Updated from DAT tab', entity, isoOffset, fileSize, isoPath, 'ram', hexlify(globalDatFile.getFullData())), tags='changed' )
			unsavedDiscChanges.append( 'Updated data for file ' + isoPath.split('/')[-1] + '.' )
			# saveSuceeded will be dependent on the iso saving step after this in this case, and the program status be updated then as well.

		elif os.path.exists( filepath ):
			if currentTab == Gui.datTab or currentTab == Gui.savTab or currentTab == Gui.mtrTab: # If not on one of these tabs, just go on to saving the banner file and/or disc
				# The DAT is loaded from a standalone file; overwrite that nuhkka!
				saveSuceeded = writeDatFile( filepath, globalDatFile.getFullData(), 'Save', globalDatFile ) # Will handle updating the program status
				return saveSuceeded # Avoiding saving disc too

		else:
			updateProgramStatus( 'Unable to Save' )
			msg( "Unable to find the original DAT file. Be sure that the file path is correct and that the file has not been moved.", 'Unable to Save' )

	# Save the currently loaded banner file's changes
	if globalBannerFile and globalBannerFile.unsavedChanges:
		filepath = globalBannerFile.path

		if globalBannerFile.source == 'disc': # The file was loaded from the currently loaded disc image.
			iid = filepath.lower()
			_, entity, isoOffset, fileSize, isoPath, _, _ = Gui.isoFileTree.item( iid, 'values' )
			Gui.isoFileTree.item( iid, values=('Updated from Disc Details tab', entity, isoOffset, fileSize, isoPath, 'ram', hexlify(globalBannerFile.data)), tags='changed' )
			unsavedDiscChanges.append( 'Updated data for file ' + isoPath.split('/')[-1] + '.' )
			# saveSuceeded will be dependent on the iso saving step after this in this case, and the program status be updated then as well.

		elif os.path.exists( filepath ):
			if currentTab == Gui.discDetailsTab: # If not on this tab, just go on to saving the disc
				# The file is loaded from a standalone file; overwrite that nuhkka!
				saveSuceeded = writeDatFile( filepath, globalBannerFile.data, 'Save', globalBannerFile ) # Will handle updating the program status
				return saveSuceeded # Avoiding saving disc too

		else:
			updateProgramStatus( 'Unable to Save' )
			msg( "Unable to find the original banner file. Be sure that the file path is correct and that the file has not been moved.", 'Unable to Save' )

	# Save the ISO's changes
	if unsavedDiscChanges or os.path.isdir( globalDiscDetails['isoFilePath'] ):
		saveSuceeded = saveDiscChanges( newDiscPath )[0]

	return saveSuceeded


def checkIfDiscNeedsRebuilding( gameId ):

	""" While there are multiple operations which may result in the disc needing to be rebuilt, this one 
		scans the files in the Disc File Tree to see if there are any new files, or any modified files 
		that are now too big to simply be replaced in the disc's data without needing to move other files.

		It also checks paths to standalone/external files that may be set for importing, 
		and alerts the user if there are any that can't be found. """

	needsRebuilding = globalDiscDetails['rebuildRequired']

	# Check if there's no FST in the disc (not expected, but you never know)
	if not Gui.isoFileTree.exists( gameId + '/game.toc' ):
		print 'No FST found! The disc will be rebuilt to create it.'
		needsRebuilding = True

	# Get a list of all files to go into the disc
	isoFilesList = getFileTreeFiles()[0] # Returns a list populated by tuples of ( description, entity, isoOffset, fileSize, isoPath, source, data )
	filesToReplace = [] # Only ends up being used if the disc will not be rebuilt
	missingFiles = []

	if needsRebuilding: # No rebuild determination needed. Just check whether external files needed for importing can be found
		# Make sure all external files can be found.
		for iidValues in isoFilesList:
			_, _, isoOffset, fileSize, isoPath, source, data = iidValues
			if source == 'path' and not os.path.exists( data ): missingFiles.append( data )

	else:
		# Order the list of files from the treeview by their offset
		isoFilesList.sort( key=lambda iidValues: int(iidValues[2], 16) )

		# Check through the files to validate any external file paths, and check whether there is natively enough space for larger files
		for i, iidValues in enumerate( isoFilesList ):
			_, _, isoOffset, fileSize, isoPath, source, data = iidValues
			if source == 'iso': continue # No changes occurring with this file.

			# Get the file size for new or modified files, and check filepaths for external files
			elif source == 'path': # This file is scheduled to be replaced by an external/standalone file
				if not os.path.exists( data ): # 'data' in this case will actually be a filepath to a standalone (external) file
					missingFiles.append( data )
					continue
				elif not needsRebuilding:
					newFileSize = int( os.path.getsize( data ) )
			elif not needsRebuilding: # source == 'ram'; rebuild status still undetermined
				newFileSize = len( data ) / 2

			if needsRebuilding: continue # External path checked; nothing else to determine for this file.
			elif isoOffset == '0' and i > 0: # Files beyond the first which have an offset of 0 are new external files being added to the disc
				needsRebuilding = True # No original file in the disc, so a lot of extra space will need to be added
				continue

			# Collect location & size info on the original file to be replaced.
			targetFileOffset = int( isoOffset, 16 )
			originalFileSize = int( fileSize )

			filesToReplace.append( (targetFileOffset, originalFileSize, isoPath, source, data) )

			# Use the above info on this file to decide if rebuilding the ISO is necessary
			if newFileSize != originalFileSize:
				# The user may opt to avoid rebuilding the disc, which can ensure there is always a certain amount of padding between files
				if not generalBoolSettings['avoidRebuildingIso'].get(): 
					needsRebuilding = True # Guess there's no avoiding it....

				else: # User wishes to avoid rebuilding. Let's see if that can be arranged.
					if newFileSize > originalFileSize and i + 1 != len( isoFilesList ):
						# Check whether there is currently enough space for the new file anyway, thanks to padding.
						if isoPath.split('/')[-1].lower() == 'start.dol':
							# Special case; will be considered together with the FST (since the latter must immediately follow the DOL, yet is itself movable)
							nextEntryOffset = int( isoFilesList[ i + 2 ][2], 16 ) # Offset of the file following the FST
							newFileSize += int( isoFilesList[ i + 1 ][3] ) # Should be the FST's file size
							#print 'considering DOL import. nextEntryOffset:', hex(nextEntryOffset), 'combined file size:', hex(newFileSize)
						else:
							nextEntryOffset = int( isoFilesList[ i + 1 ][2], 16 )

						if nextEntryOffset == 0: # Makes sure the next file to pull an offset from isn't a new file
							needsRebuilding = True
						else:
							spareSpaceAfterImport = nextEntryOffset - targetFileOffset - newFileSize
							#print 'spare space between files (with new file):', hex( spareSpaceAfterImport )
							if spareSpaceAfterImport < 0: needsRebuilding = True

	if missingFiles:
		cmsg( 'These files could not be located for importing:\n\n' + '\n'.join( missingFiles ) )

	globalDiscDetails['rebuildRequired'] = needsRebuilding

	return needsRebuilding, filesToReplace


def saveDiscChanges( newDiscPath='' ):

	""" Saves all changed files in an ISO to disc; either by replacing each file in-place
		(and updating the FST) or rebuilding the whole disc. """

	global unsavedDiscChanges
	discFilePath = os.path.normpath( globalDiscDetails['isoFilePath'] )
	fileWriteSuccessful = False
	filesReplaced = [] # The following three lists will be of iids
	filesAdded = []
	filesUpdated = []

	# Verify the path to the disc.
	if not os.path.exists( discFilePath ): 
		updateProgramStatus( 'Disc Not Found' )
		msg( 'There was a problem attemtping to save the disc changes. Possibly due to the file being deleted or moved.', 'Disc Not Found' )
		return False, 0, 0

	if isRootFolder( discFilePath )[0]: buildingFromRootFolder = True
	else: buildingFromRootFolder = False

	discExtOriginal = os.path.splitext( discFilePath )[1] # Inlucdes dot ('.')
	discExt = discExtOriginal[1:].upper() # Removes the '.' as well
	gameId = globalDiscDetails['gameId'].lower()

	needsRebuilding, filesToReplace = checkIfDiscNeedsRebuilding( gameId )

	# Ensure there is work to be done
	if not needsRebuilding and not filesToReplace:
		# If this occurs, there are probably external files to be imported that are missing (in which case the user has been notified)
		cmsg( 'The following changes are still present and have not been saved to the disc:\n\n' + '\n'.join(unsavedDiscChanges) )
		return False, [], []

	elif needsRebuilding and 'Offset' in Gui.isoFileTree.heading( '#0', 'text' ):
		msg( 'The disc cannot be rebuilt while\nthe files are sorted in this way.' )
		return False, [], []

	chunkSize = 4194304 # 4 MB. This is the chunk size that will be copied from ISO to ISO during the rebuild process.
	guiUpdateInterval = 8388608 # 8 MB. Once this many bytes or more have been copied to the new disc, the gui should update the progress display
	originalIsoBinary = None
	backupFile = None

	def getInChunks( sourceFile, offset, fileSize, chunkSize ):
		""" Generator to get a file (from a specific offset) piece by piece. (Saves greatly on memory usage) """

		sourceFile.seek( offset )
		bytesCopied = 0
		while True:
			if bytesCopied + chunkSize >= fileSize:
				remainingDataLength = fileSize - bytesCopied
				yield sourceFile.read( remainingDataLength )
				break # Ends this generator (conveys that it is exhausted).
			else:
				bytesCopied += chunkSize
				yield sourceFile.read( chunkSize ) # Come back to this function for the next chunk of data after this.

	# Check whether all system files are present and accounted for, and what boot file nomenclature/division is used
	gcrSystemFiles = False
	missingSystemFiles = False
	for systemFile in [ '/boot.bin', '/bi2.bin', '/apploader.ldr', '/start.dol' ]:
		systemFileIid = gameId + systemFile
		if not Gui.isoFileTree.exists( systemFileIid ) and systemFile.endswith( '.bin' ):
			if Gui.isoFileTree.exists( gameId + '/iso.hdr' ): # It's ok if boot.bin & bi2.bin don't exist if iso.hdr is available in their place
				gcrSystemFiles = True
				continue
			missingSystemFiles = True
			break

	# Verify all required system files are present and accounted for before continuing.
	if needsRebuilding and missingSystemFiles:
		msg( 'A system file, ' + systemFileIid + ', could not be found. Cannot rebuild the ' + discExt + '.' )
		return False, 0, 0

	# Determine the location of the FST from the header file loaded in the GUI (may be new and not yet match the disc)
	if gcrSystemFiles: headerFileData = getFileDataFromDiscTreeAsBytes( gameId + '/iso.hdr' )
	else: headerFileData = getFileDataFromDiscTreeAsBytes( gameId + '/boot.bin' )
	dolOffset = toInt( headerFileData[0x420:0x424] )
	dolFileSize = getFileSizeFromDiscTree( gameId + '/start.dol' )
	if dolFileSize == 0: return # Failsafe (DOL could have been external, and moved by user)
	fstOffset = dolOffset + dolFileSize

	# Write the file(s) to the ISO.
	if not needsRebuilding:

		def updateFstEntry( entries, targetFileOffset, newFileSize ):
			for i, entry in enumerate( entries ):
				if entry[:2] == '01': continue # Checks the directory flag to skip folders
				entryOffset = int( entry[8:16], 16 )

				# Update this entry with the new file length
				if entryOffset == targetFileOffset:
					entries[i] = entries[i][:-8] + "{0:0{1}X}".format( int(newFileSize), 8 )
					break

		systemFiles = [ 'boot.bin', 'bi2.bin', 'apploader.ldr', 'game.toc', 'iso.hdr', 'start.dol' ]
		fstContentsUpdated = False
		fstLocationUpdated = False

		# Retrieve and parse the existing FST/TOC (File System Table/Table of Contents).
		fstData = getFileDataFromDiscTree( gameId + '/game.toc' )
		_, entries, strings = readFST( fstData ) # Returns an int and two lists

		# Create a copy of the file and operate on that instead if using the 'Save Disc As' option
		if newDiscPath:
			try:
				origFileSize = int( os.path.getsize(discFilePath) )
				dataCopiedSinceLastUpdate = 0
				with open( newDiscPath, 'wb' ) as newFile:
					with open( discFilePath, 'rb' ) as originalFile:
						for dataChunk in getInChunks( originalFile, 0, origFileSize, chunkSize ):
							newFile.write( dataChunk )
							dataCopiedSinceLastUpdate += len( dataChunk )
							if dataCopiedSinceLastUpdate > guiUpdateInterval:
								updateProgramStatus( 'Copying ' + discExt + ' (' + str( round( (float(newFile.tell()) / origFileSize) * 100, 1 ) ) + '%)' )
								Gui.programStatusLabel.update()
								dataCopiedSinceLastUpdate = 0

				discFilePath = newDiscPath
			except:
				msg( 'The file to replace could not be overwritten.\n\n'
					 "This can happen if the file is locked for editing (for example, if it's open in another program)." )
				return False, 0, 0

		# Save each file to the ISO directly, modifying the FST if required. Only FST file lengths may need to be updated.
		try:
			with open( discFilePath, 'r+b') as isoBinary:
				importIndex = 1

				for targetFileOffset, originalFileSize, isoPath, source, data in filesToReplace:
					thisFileName = isoPath.split('/')[-1].lower()
					padding = ''

					# Update the GUI's progress display.
					if len( filesToReplace ) > 1:
						updateProgramStatus( 'Importing file ' + str(importIndex) + ' of ' + str(len( filesToReplace )) )
						Gui.programStatusLabel.update()
						importIndex += 1

					# Collect location & size info on the original file to be replaced.
					if source == 'path': newFileSize = int( os.path.getsize(data) )
					else: newFileSize = len( data ) / 2 # source = 'ram'; there cannot be cases of source='iso' here

					# Update this file entry's size value in the FST if it's different.
					if newFileSize != originalFileSize:
						if thisFileName in systemFiles: # This file isn't in the FST. A value in the disc's header may need to be updated.
							if thisFileName == 'start.dol':
								# Move the FST. It must directly follow the DOL as its offset is the only indicator of the DOL file's size
								isoBinary.seek( 0x424 )
								isoBinary.write( toBytes( fstOffset ) )
								fstLocationUpdated = True

							# If this file is the FST, its size also needs to be updated in boot.bin
							elif thisFileName == 'game.toc':
								isoBinary.seek( 0x428 )
								newFstSizeByteArray = toBytes( newFileSize )
								isoBinary.write( newFstSizeByteArray ) # Writes the value for FST size
								isoBinary.write( newFstSizeByteArray ) # Writes the value for max FST size (differs from above for multi-disc games?)

							if thisFileName == 'start.dol' or thisFileName == 'game.toc':
								# Remember that the header file was updated
								if gcrSystemFiles: filesUpdated.append( gameId + '/iso.hdr' )
								else: filesUpdated.append( gameId + '/boot.bin' )

						else: # The file's size value needs to be updated in the FST
							updateFstEntry( entries, targetFileOffset, newFileSize )
							fstContentsUpdated = True

							# Prepare some padding of zeros to go after the file, to remove any traces of the old file.
							if newFileSize < originalFileSize:
								padding = '00' * (originalFileSize - newFileSize)

					# Write the new file (and trailing padding if needed) to the ISO
					isoBinary.seek( targetFileOffset )
					if source == 'ram':
						isoBinary.write( bytearray.fromhex(data) )
					else:
						with open( data, 'rb' ) as externalFile: # fileData is actually a file path in this case.
							for dataChunk in getInChunks( externalFile, 0, newFileSize, chunkSize ):
								isoBinary.write( dataChunk )
					isoBinary.write( bytearray.fromhex(padding) )
					filesReplaced.append( isoPath.lower() )

				if fstLocationUpdated or fstContentsUpdated:
					# Reassemble the FST and write it back into the game
					updatedFstData = ''.join( entries ) + '\x00'.join( strings ).encode('hex')
					isoBinary.seek( fstOffset )
					isoBinary.write( bytearray.fromhex(updatedFstData) )

					if fstContentsUpdated: filesUpdated.append( gameId + '/game.toc' )

			fileWriteSuccessful = True
		except Exception as e:
			print 'Error saving changes to disc (rebuild required = False);', e 

	else: # Build a new image, based on the folders and files in the GUI.
		dataCopiedSinceLastUpdate = 0
		#tic = time.clock() # for performance testing

		# Generate a new FST based on the files shown in the GUI
		newFstData = generateFST()
		newNumberOfEntries, newEntries, newStrings = readFST( newFstData ) # Returns an int and two lists

		try:
			if buildingFromRootFolder: # This is a root folder that needs to be built into a disc image
				# Try to get the shortTitle, for use as a default file name
				if globalBannerFile:
					if Gui.countryCode.get() == 'us': encoding = 'latin_1' # Decode assuming English or other European countries
					else: encoding = 'shift_jis' # The country code is 'jp', for Japanese.

					defaultDiscName = globalBannerFile.data[0x1820:(0x1820 + 0x20)].decode(encoding) + '.iso'
				else: 
					defaultDiscName = gameId.upper() + '.iso'
				
				# Prompt for a place to save the file, and a filename.
				savePath = tkFileDialog.asksaveasfilename(
					title="Choose a destination and file name to save these files as a new disc image.", 
					initialdir=settings.get( 'General Settings', 'defaultSearchDirectory' ),
					initialfile=defaultDiscName,
					defaultextension='.iso',
					filetypes=[('Standard disc image', '*.iso'), ('GameCube disc image', '*.gcm'), ("All files", "*.*")])

				if not savePath: return False, 0, 0

			else: originalIsoBinary = open( discFilePath, 'rb' ) # Will only be reference when rebuilding an existing disc image.

			def updateProgressDisplay( dataCopiedSinceLastUpdate ):
				if dataCopiedSinceLastUpdate > guiUpdateInterval:
					updateProgramStatus( 'Rebuilding ' + discExt + ' (' + str( round( (float(newIsoBinary.tell()) / projectedDiscSize) * 100, 1 ) ) + '%)' )
					Gui.programStatusLabel.update()
					return 0
				else: return dataCopiedSinceLastUpdate

			# Determine how much padding to add between files
			fstFileSize = len( newFstData )/2
			spaceForHeaderAndSystemFiles = fstOffset + roundTo32( fstFileSize, base=4 )
			totalNonSystemFiles = 0
			totalNonSystemFileSpace = 0
			for entry in newEntries:
				if entry[:2] == '00': # Means it's a file
					totalNonSystemFiles += 1
					thisEntryFileSize = int( entry[16:24], 16 )
					totalNonSystemFileSpace += roundTo32( thisEntryFileSize, base=4 )
			interFilePaddingLength = getInterFilePaddingLength( totalNonSystemFiles, spaceForHeaderAndSystemFiles + totalNonSystemFileSpace )
			paddingSettingsValue = settings.get( 'General Settings', 'paddingBetweenFiles' ).lower()

			# Create a new file to begin writing the new disc to, and calculate the size it will be expected to reach
			backupFile = tempfile.NamedTemporaryFile( dir=os.path.dirname(discFilePath), suffix='.tmp', delete=False )
			if buildingFromRootFolder and paddingSettingsValue == 'auto': projectedDiscSize = 1459978240
			else: projectedDiscSize = spaceForHeaderAndSystemFiles + totalNonSystemFileSpace + totalNonSystemFiles * interFilePaddingLength

			with open( backupFile.name, 'r+b' ) as newIsoBinary: # File opened in read/write binary mode

				# Write the new ISO's system files
				for systemFile in [ '/boot.bin', '/bi2.bin', '/apploader.ldr', '/start.dol' ]:
					if gcrSystemFiles and systemFile == '/boot.bin': continue # Skip this and the next file in trade for iso.hdr if it is present.
					elif gcrSystemFiles and systemFile == '/bi2.bin': systemFile = '/iso.hdr'

					# Gather info on the source and destination for this file
					iid = gameId + systemFile
					description, entity, isoOffset, origFileSize, isoPath, source, data = Gui.isoFileTree.item( iid, 'values' )
					thisFileOffset = int( isoOffset, 16 )

					# Add padding prior to the file, if needed (likely shouldn't be though), to preserve offsets
					currentFilePosition = newIsoBinary.tell()
					if currentFilePosition < thisFileOffset:
						sysFilePadding = '00' * ( thisFileOffset - currentFilePosition )
						newIsoBinary.write( bytearray.fromhex(sysFilePadding) )

					# Determine if this is a file being imported, or if it will be copied from the original ISO
					if source == 'path': # In this case, the source is an external file.
						newFileSize = os.path.getsize( data ) # data is a file path in this case
						with open( data, 'rb' ) as newSystemFile:
							# Write the file to the ISO in chunks (and update the status display)
							for dataChunk in getInChunks( newSystemFile, 0, newFileSize, chunkSize ):
								newIsoBinary.write( dataChunk )
								dataCopiedSinceLastUpdate += len( dataChunk )

								# This may take a while. Update the GUI's progress display.
								dataCopiedSinceLastUpdate = updateProgressDisplay( dataCopiedSinceLastUpdate )

					elif source == 'ram': # The data for this file is already loaded in the data variable, as a hex string
						dataChunk = bytearray.fromhex( data )
						newIsoBinary.write( dataChunk )
						dataCopiedSinceLastUpdate += len( dataChunk )

						# This may take a while. Update the GUI's progress display.
						dataCopiedSinceLastUpdate = updateProgressDisplay( dataCopiedSinceLastUpdate )

					else: # This file was not found in the files being imported (source == 'iso'). Use the system file from the original ISO.
						originalIsoBinary.seek( thisFileOffset )
						dataChunk = originalIsoBinary.read( int(origFileSize) )

						newIsoBinary.write( dataChunk )
						dataCopiedSinceLastUpdate += len( dataChunk )

						# This may take a while. Update the GUI's progress display.
						dataCopiedSinceLastUpdate = updateProgressDisplay( dataCopiedSinceLastUpdate )

					if source != 'iso':
						filesReplaced.append( isoPath.lower() )

				# Prepare space for the FST. Add padding between it and the DOL (last file above) if needed, and create space where the full FST will later be placed.
				currentFilePosition = newIsoBinary.tell()
				fstPlaceholderPadding = '00' * ( fstOffset + fstFileSize - currentFilePosition )
				newIsoBinary.write( bytearray.fromhex(fstPlaceholderPadding) )
				
				# Write the new ISO's main file structure						# Entry composition in the following loop, for both files and folders: 	
				lowercaseIsoPath = gameId # gameId already lower case			directoryFlag (1 byte) + stringTableOffset + hierarchicalOffset + length
				dirEndIndexes = [newNumberOfEntries]
				for index, entry in enumerate( newEntries[1:], start=1 ): # skips the root entry

					# If the last directory being added to has been finished, remove the last directory from lowercaseIsoPath
					while index == dirEndIndexes[-1]:
						lowercaseIsoPath = '/'.join( lowercaseIsoPath.split('/')[:-1] )
						dirEndIndexes.pop()

					if entry[:2] == '01': # This entry is a folder (== 00 for a file)
						lowercaseIsoPath += '/' + newStrings[ index - 1 ].lower()

						# Remember how many entries are in this folder, so when that number is reached, that dirictory can be removed from lowercaseIsoPath
						entryLength = int( entry[16:24], 16 )
						dirEndIndexes.append( entryLength )
					else:
						# Add padding before this file, while ensuring that the file will be aligned to 4 bytes.
						currentFilePosition = newIsoBinary.tell()
						alignmentAdjustment = roundTo32( currentFilePosition, base=4 ) - currentFilePosition # i.e. how many bytes away from being aligned.
						interFilePadding = '00' * ( alignmentAdjustment + interFilePaddingLength )
						newIsoBinary.write( bytearray.fromhex(interFilePadding) )

						#newEntries[ index ] = entry[:8] + "{0:0{1}X}".format( newIsoBinary.tell(), 8 ) + entry[16:24]
						newEntryOffset = "{0:0{1}X}".format( newIsoBinary.tell(), 8 )

						# Check if this file is to be copied to the new ISO from the original disc (when rebuilding an existing image), or will be replaced by one of the new files.
						iid = lowercaseIsoPath + '/' + newStrings[ index - 1 ].lower()
						description, entity, isoOffset, origFileSize, isoPath, source, data = Gui.isoFileTree.item( iid, 'values' )

						if source == 'path': # The data variable is a file path in this case.
							fileSize = os.path.getsize( data )

							# Write the file to the new ISO (copying in chunks if it's a large file).
							with open( data, 'rb' ) as externalFile:
								for dataChunk in getInChunks( externalFile, 0, fileSize, chunkSize ):
									newIsoBinary.write( dataChunk )
									dataCopiedSinceLastUpdate += len( dataChunk )

									# Update the GUI's progress display.
									dataCopiedSinceLastUpdate = updateProgressDisplay( dataCopiedSinceLastUpdate )

							# Update this entry with its new offset and size
							newEntries[ index ] = entry[:8] + newEntryOffset + "{0:0{1}X}".format( fileSize, 8 )

						elif source == 'ram': # The data variable is file data (a hex string) in this case.
							fileSize = len( data )/2

							# Write the file to the new ISO
							newIsoBinary.write( bytearray.fromhex(data) )
							dataCopiedSinceLastUpdate += fileSize

							# Update the GUI's progress display.
							dataCopiedSinceLastUpdate = updateProgressDisplay( dataCopiedSinceLastUpdate )

							# Update this entry with its new offset and size
							newEntries[ index ] = entry[:8] + newEntryOffset + "{0:0{1}X}".format( fileSize, 8 )

						else: # The file for this entry will be from the original ISO (source == 'iso').
							origFileOffset = int( entry[8:16], 16 )
							fileSize = int( entry[16:24], 16 )

							# Write the file to the new ISO (copying in chunks if it's a large file).
							#print 'writing internal file', iid, 'to', hex( newIsoBinary.tell() )
							for dataChunk in getInChunks( originalIsoBinary, origFileOffset, fileSize, chunkSize ):
								newIsoBinary.write( dataChunk )
								dataCopiedSinceLastUpdate += len( dataChunk )

								# Update the GUI's progress display.
								dataCopiedSinceLastUpdate = updateProgressDisplay( dataCopiedSinceLastUpdate )

							# Update this entry with its new offset
							newEntries[ index ] = entry[:8] + newEntryOffset + entry[16:24]

						if source != 'iso':
							if isoOffset == '0': filesAdded.append( isoPath.lower() )
							else: filesReplaced.append( isoPath.lower() )

				# If auto padding was used, there should be a bit of padding left over to bring the file up to the standard GameCube disc size.
				if buildingFromRootFolder and paddingSettingsValue == 'auto':
					finalPadding = '00' * ( 1459978240 - int(newIsoBinary.tell()) )
					newIsoBinary.write( bytearray.fromhex(finalPadding) )

				# Ensure the final file has padding rounded up to nearest 0x20 bytes (the file cannot be loaded without this!)
				lastFilePadding = roundTo32( int(newIsoBinary.tell()) - newEntryOffset ) - fileSize
				if lastFilePadding > 0 and lastFilePadding < 0x20:
					newIsoBinary.write( bytearray(lastFilePadding) )

				# Now that all files have been written and evaluated, the new FST is ready to be assembled and written into the ISO.
				updatedFstData = ''.join( newEntries ) + '\x00'.join( newStrings ).encode('hex')
				newIsoBinary.seek( fstOffset )
				newIsoBinary.write( bytearray.fromhex(updatedFstData) )
				filesUpdated.append( gameId + '/game.toc' )

				# Update the offset and size of the DOL and FST in boot.bin/iso.hdr
				newIsoBinary.seek( 0x424 )
				#newIsoBinary.write( toBytes( dolOffset ) ) # old slower method: bytearray.fromhex( "{0:0{1}X}".format(dolOffset, 8) )
				newIsoBinary.write( toBytes( fstOffset ) )
				newFstSizeBytes = toBytes( len(updatedFstData)/2 )
				newIsoBinary.write( newFstSizeBytes ) # Writes the value for FST size
				newIsoBinary.write( newFstSizeBytes ) # Writes the value for max FST size (the Apploader will be displeased if this is less than FST size)

				# Remember that this file was updated
				if gcrSystemFiles: filesUpdated.append( gameId + '/iso.hdr' )
				else: filesUpdated.append( gameId + '/boot.bin' )

			Gui.programStatusLabel.update() # Should show that sweet '100%' completion for a moment.
			fileWriteSuccessful = True

		except Exception as e:
			print 'Error saving changes to disc (rebuild required = True);', e
		
		# toc = time.clock()
		# print 'Time to rebuild disc:', toc-tic

	# Close files that may have been opened
	if backupFile: backupFile.close()
	if originalIsoBinary: originalIsoBinary.close() # not buildingFromRootFolder and 

	if not fileWriteSuccessful:
		updateProgramStatus( 'Disc Save Error' )

		if backupFile and os.path.exists( backupFile.name ): os.remove( backupFile.name ) # Delete the back-up file.

		if buildingFromRootFolder: message = "Unable to build the disc."
		else: message = "Unable to save or import into the " + discExt + ". \n\nBe sure that it is not being used by another \nprogram (like Dolphin :P)."
		if tkMessageBox.askretrycancel( 'Problem While Saving', message ):
			fileWriteSuccessful, filesReplaced, filesAdded = saveDiscChanges( newDiscPath )

	else: # Save was successful
		# Update the program status
		updateStatus = False # Prevents the status from changing when the disc is reloaded, except in a special case below.
		unsavedDiscChanges = []
		if globalDatFile: globalDatFile.unsavedChanges = []
		updateProgramStatus( 'Save Successful' )

		# Change the background color of any edited entry widgets back to white. (Image Data Headers, Texture Struct properties, etc.) back to white.
		if globalBannerFile and globalBannerFile.source == 'disc':
			restoreEditedEntries( editedBannerEntries )
		if globalDatFile and globalDatFile.source == 'disc':
			restoreEditedEntries( editedDatEntries )

		# If the disc needed to be rebuilt, there are new disc files that need to be renamed
		if needsRebuilding:
			if buildingFromRootFolder:
				# Rename the backup file to the selected name (removing/replacing any existing file by that name).
				try:
					if os.path.exists( savePath ):
						os.remove( savePath )
				except:
					msg( 'The file to replace could not be overwritten.\n\n'
						"This can happen if the file is locked for editing (for example, if it's open in another program)." )
					return False, 0, 0

				os.rename( backupFile.name, savePath )
				discFilePath = savePath

			# If using the 'Save Disc As...' option
			elif newDiscPath:
				# Set the new disc path, and delete any existing file
				try:
					if os.path.exists( newDiscPath ):
						os.remove( newDiscPath )
				except:
					msg( 'The file to replace could not be overwritten.\n\n'
						"This can happen if the file is locked for editing (for example, if it's open in another program)." )
					return False, 0, 0

				# Move/rename the new (temp) file to the specified directory/name
				os.rename( backupFile.name, newDiscPath )
				discFilePath = newDiscPath

			elif generalBoolSettings['backupOnRebuild'].get():
				# Create a new, unique file name for the backup, with a version number based on the source file. e.g. '[original filename] - Rebuilt, v1.iso'
				discFileName = os.path.basename( discFilePath )
				if 'Rebuilt, v' in discFileName:
					newIsoFilepath = discFilePath
				else:
					newIsoFilepath = discFilePath[:-4] + ' - Rebuilt, v1' + discExtOriginal

				# Make sure this is a unique (new) file path
				if os.path.exists( newIsoFilepath ):
					nameBase, _, version = newIsoFilepath[:-4].rpartition( 'v' ) # Splits on last instance of the delimiter (once)

					if '.' in version: # e.g. "1.3"
						# Get the most minor number in the version
						versionBase, _, _ = version.rpartition( '.' )
						newIsoFilepath = '{}v{}.1{}'.format( nameBase, versionBase, discExtOriginal )

						newMinorVersion = 2
						while os.path.exists( newIsoFilepath ):
							newIsoFilepath = '{}v{}.{}{}'.format( nameBase, versionBase, newMinorVersion, discExtOriginal )
							newMinorVersion += 1

					else: # Single number version
						newIsoFilepath = '{}v1{}'.format( nameBase, discExtOriginal )
						newMajorVersion = 2
						while os.path.exists( newIsoFilepath ):
							newIsoFilepath = '{}v{}{}'.format( nameBase, newMajorVersion, discExtOriginal )
							newMajorVersion += 1
				
				# Rename the backup file to the above name.
				os.rename( backupFile.name, newIsoFilepath )

				# Inform the user that a backup was created, and prompt if they'd like to switch to it.
				if tkMessageBox.askyesno( 'Load Back-up?', 'The rebuilt disc was saved as a back-up. Would you like to load it now?' ):
					updateStatus = True
					discFilePath = newIsoFilepath

			# Performing a basic save (no back-ups)
			else:
				# Rename the original file, rename the back-up to the original file's name. Then, if successful, delete the original file.
				try:
					os.rename( discFilePath, discFilePath + '.bak' ) # Change the name of the original file so the new file can be named to it. Not deleted first in case the op below fails.
					os.rename( backupFile.name, discFilePath ) # Rename the new 'back-up' file to the original file's name.

					os.remove( discFilePath + '.bak' ) # Delete the original file.
				except:
					msg('A back-up file was successfully created, however there was an error while attempting to rename the files and remove the original.\n\n'
						"This can happen if the original file is locked for editing (for example, if it's open in another program).")
					return False, 0, 0

		if fileWriteSuccessful:
			# Reload the file to get the new properties, such as file offsets and sizes, and to reset descriptions and source info.
			if buildingFromRootFolder: updatedFiles = None # No reason to highlight all the files; it's implied they're all "new/updated" since it's a new disc.
			else: updatedFiles = filesReplaced + filesAdded + filesUpdated

			rememberFile( discFilePath, False )
			globalDiscDetails['isoFilePath'] = discFilePath

			scanDisc( updateStatus, preserveTreeState=True, switchTab=False, updatedFiles=updatedFiles )

			# Warn the user if an ISO is too large for certain loaders
			isoByteSize = os.path.getsize( discFilePath )
			if isoByteSize > 1459978240: # This is the default/standard size for GameCube discs.
				msg( 'The disc is larger than the standard size for GameCube discs (which is ~1.36 GB, or 1,459,978,240 bytes). This will be a problem for Nintendont, but discs up to 4 GB '
					 'should still work fine for both Dolphin and DIOS MIOS. (Dolphin may still play discs larger than 4 GB, but some features may not work.)', 'Standard Disc Size Exceeded' )

	return fileWriteSuccessful, filesReplaced, filesAdded # files replaced will always count the FST if a rebuild was required


def saveDatAs(): # Will overwrite an existing file, or create a new file if one does not exist.
	if not globalDatFile:
		msg( "This operation is for a DAT file that has already been loaded in the DAT Texture Tree tab. "
			 "If you'd like to save a file that's in a disc to a standalone file, use the 'Export' feature." )
	else:
		# Prompt for a place to save the new DAT file.
		saveDataToFileAs( globalDatFile.getFullData(), globalDatFile )


def saveBannerAs(): # Will overwrite an existing file, or create a new file if one does not exist.
	if not globalBannerFile:
		msg( "This operation is for a banner file that has already been loaded in the Disc Details tab. "
			 "If you'd like to save a file that's in a disc to a standalone file, use the 'Export' feature." )
	else:
		# Prompt for a place to save the new banner file.
		saveDataToFileAs( globalBannerFile.data, globalBannerFile )


def saveDataToFileAs( datData, datFile ):
	# Prompt for a place to save the file.
	ext = os.path.splitext( datFile.fileName )[1].replace('.', '')
	savePath = tkFileDialog.asksaveasfilename(
		title="Where would you like to export the file?",
		initialdir=settings.get( 'General Settings', 'defaultSearchDirectory' ),
		initialfile=datFile.fileName,
		defaultextension=ext,
		filetypes=[( ext.upper() + " files", '*.' + ext.lower() ), ( "All files", "*.*" )] ) #confirmoverwrite ?

	if savePath:
		# Update the default directory to start in when opening or exporting files.
		dirPath = os.path.dirname( savePath )
		settings.set( 'General Settings', 'defaultSearchDirectory', dirPath )
		with open( settingsFile, 'w') as theSettingsFile: settings.write( theSettingsFile )

		saveSuceeded = writeDatFile( savePath, datData, 'Save', datFile )

		# If the operation was a success, update the filepaths to the newly created file
		if saveSuceeded:
			origFileName = datFile.fileName
			newFileName = os.path.basename( savePath )

			# Update internal class references
			datFile.path = savePath
			datFile.source = 'file'
			datFile.fileName = newFileName

			# Update external references (shown on the GUI)
			Gui.datDestination.set( savePath )
			if len( newFileName ) > 30: newFileName = newFileName[:27] + '...'
			Gui.fileStructureTree.heading( '#0', anchor='center', text=newFileName ) # SA tab

			# If the new file's name is displayed in the SA tab's property pane, update that too
			structPropertiesChildren = Gui.structurePropertiesFrame.interior.winfo_children()
			if structPropertiesChildren:
				labelWidget = structPropertiesChildren[0]
				if labelWidget.winfo_class() == 'TLabel' and labelWidget['text'] == origFileName:
					labelWidget['text'] = newFileName

			# Add the new file to the recent files menu
			#rememberFile( savePath )


def getDiscPath( iid, isoPath='', includeRoot=True ):

	""" Builds a disc path, like isoPath, but includes convenience folders if they are turned on. """

	if not isoPath:
		isoPath = Gui.isoFileTree.item( iid, 'values' )[-3]

	if generalBoolSettings['useDiscConvenienceFolders'].get():
		# Scan for 'convenience folders' (those not actually in the disc), and add them to the path; they won't exist in isoPath
		root = globalDiscDetails['gameId'].lower()
		isoParts = isoPath.split( '/' )
		pathParts = [ isoParts[-1] ] # A list, starting with just the filename
		parentIid = Gui.isoFileTree.parent( iid )

		while parentIid != root:
			parentFolderText = Gui.isoFileTree.item( parentIid, 'text' ).strip()

			for character in ( '\\', '/', ':', '*', '?', '"', '<', '>', '|' ): # Remove illegal characters
				parentFolderText = parentFolderText.replace( character, '-' )
			pathParts.insert( 0, parentFolderText )

			parentIid = Gui.isoFileTree.parent( parentIid )

		if includeRoot:
			pathParts.insert( 0, isoParts[0] )

		return '/'.join( pathParts )

	elif not includeRoot:
		return '/'.join( isoPath.split('/')[1:] ) # Removes the GameID

	else:
		return isoPath


def exportItemsInSelection( selection, iidSelectionsTuple, isoBinary, directoryPath, exported, failedExports ):

	""" Basically just a recursive helper function to exportIsoFiles(). """

	for iid in selection:
		# Prevent files from being exported twice depending on user selection
		if (selection != iidSelectionsTuple) and iid in iidSelectionsTuple:
			continue

		#if initialSelection or iid not in iidSelectionsTuple: 
		_, entity, isoOffset, fileSize, isoPath, source, data = Gui.isoFileTree.item( iid, 'values' )

		if entity == 'file':
			Gui.programStatus.set( 'Exporting File ' + str(exported + failedExports + 1) + '....' )
			Gui.programStatusLabel.update()

			try:
				# Retrieve the file data.
				if source == 'iso':
					isoBinary.seek( int(isoOffset, 16) )
					datData = bytearray( isoBinary.read( int(fileSize) ) )

				elif source == 'ram':
					datData = bytearray.fromhex( data )

				else: # source == 'path', meaning data is a filepath to an external file
					with open( data, 'rb') as externalFile:
						datData = bytearray( externalFile.read() )

				# Construct a file path for saving, and destination folders if they don't exist
				savePath = directoryPath + '/' + getDiscPath( iid, isoPath, includeRoot=False )
				createFolders( os.path.split(savePath)[0] )

				# Save the data to a new file.
				with open( savePath, 'wb' ) as newFile:
					newFile.write( datData )
				exported += 1

			except:
				failedExports += 1

		else: # Item is a folder.
			exported, failedExports = exportItemsInSelection( Gui.isoFileTree.get_children(iid), iidSelectionsTuple, isoBinary, directoryPath, exported, failedExports )

	return exported, failedExports


def exportIsoFiles():
	if not discDetected(): return
	
	iidSelectionsTuple = Gui.isoFileTree.selection()
	if not iidSelectionsTuple:
		updateProgramStatus( 'Eh?' )
		msg( 'Please first select a file or folder to export.' )
		return

	elif globalDiscDetails['isoFilePath'] == '' or not os.path.exists( globalDiscDetails['isoFilePath'] ):
		updateProgramStatus( 'Export Error' )
		msg( "Unable to find the disc image. Be sure that the file path is correct and that the file has not been moved or deleted.", 'Disc Not Found' )
		return

	_, entity, isoOffset, fileSize, isoPath, source, data = Gui.isoFileTree.item( iidSelectionsTuple[0], 'values' )

	# Check the selection to determine if a single or multiple files need to be exported
	if len( iidSelectionsTuple ) == 1 and entity == 'file':
		# Prompt for a place to save the file.
		fileName = '-'.join( isoPath.split('/')[1:] ) # Removes the GameID, and separates directories with dashes
		ext = os.path.splitext( fileName )[1].replace('.', '')
		savePath = tkFileDialog.asksaveasfilename(
			title="Where would you like to export the file?", 
			initialdir=settings.get( 'General Settings', 'defaultSearchDirectory' ),
			#initialfile=filenameWithNoExt + ' (from ' + isoFilenameWithNoExt + ')',
			initialfile=fileName,
			defaultextension=ext,
			filetypes=[( ext.upper() + " files", '*.' + ext.lower() ), ( "All files", "*.*" )] ) #confirmoverwrite ?

		# If the above wasn't canceled and returned a path, use that to save the file
		if savePath:
			directoryPath = os.path.dirname( savePath ) # Used at the end of this function

			# Get the file's data and write it to an external file
			datData = getFileDataFromDiscTreeAsBytes( iidValues=(entity, isoOffset, fileSize, source, data) )
			writeDatFile( savePath, datData, 'Export' )
		else: directoryPath = ''

	else: # Multiple files selected to be exported. Prompt for a directory to save them to.
		directoryPath = tkFileDialog.askdirectory(
			title='Where would you like to save these files?',
			initialdir=settings.get( 'General Settings', 'defaultSearchDirectory' ),
			parent=Gui.root,
			mustexist=True )

		if directoryPath != '':
			exported = 0
			failedExports = 0

			with open( globalDiscDetails['isoFilePath'], 'rb') as isoBinary:
				exported, failedExports = exportItemsInSelection( iidSelectionsTuple, iidSelectionsTuple, isoBinary, directoryPath, exported, failedExports )

			if failedExports == 0: updateProgramStatus( 'Export Successful' )
			else:
				updateProgramStatus( 'Failed Exports' ) # writeDatFile will otherwise update this with success.
				if exported > 0:
					msg( str(exported) + ' files exported successfully. However, ' + str(failedExports) + ' files failed to export.' )
				else: msg( 'Unable to export.' )

	if directoryPath:
		# Update the default directory to start in when opening or exporting files.
		settings.set( 'General Settings', 'defaultSearchDirectory', directoryPath )
		with open( settingsFile, 'w') as theSettingsFile: settings.write( theSettingsFile )


def exportTexturesInSelection( selection, iidSelectionsTuple, isoBinary, chosenSaveDirectory, exported, failedExports, exportFormat ):

	""" Basically just a recursive helper function to exportSelectedFileTextures(). """

	for iid in selection:
		# Prevent files from being exported twice depending on user selection
		if (selection != iidSelectionsTuple) and iid in iidSelectionsTuple:
			continue

		_, entity, _, _, isoPath, _, _ = Gui.isoFileTree.item( iid, 'values' )

		if entity == 'file':
			Gui.programStatus.set( 'Exporting from file ' + str(exported + len(failedExports) + 1) + '....' )
			Gui.programStatusLabel.update()

			try:
				# Initialize the file and collect textures from it
				fileData = getFileDataFromDiscTreeAsBytes( iid )
				datFile = hsdFiles.datFileObj( source='disc' )
				datFile.load( iid, fileData, os.path.basename(isoPath) )

				# Skip unrecognized files (or those appearing to have unreasonable basic features)
				if datFile.headerInfo['rootNodeCount'] > 300 or datFile.headerInfo['referenceNodeCount'] > 300 or datFile.headerInfo['rtEntryCount'] > 45000:
					print 'Skipping texture export from', iid + '; unreasonable file'
					failedExports.append( isoPath.split('/')[-1] )
					continue
				elif len( datFile.rtData ) > 200000:
					print 'Skipping texture export from', iid + '; unrecognized file'
					failedExports.append( isoPath.split('/')[-1] )
					continue

				# Construct the file path and create any folders needed
				saveDirectory = chosenSaveDirectory + '/' + getDiscPath( iid, isoPath, includeRoot=False )
				createFolders( saveDirectory )

				# Export all textures that can be found in this file
				for imageDataOffset, _, _, _, width, height, imageType, _ in identifyTextures( datFile ):
					# Get the image data
					imageDataLength = hsdStructures.ImageDataBlock.getDataLength( width, height, imageType )
					imageData = datFile.getData( imageDataOffset, imageDataLength )

					# Add the texture file name to the save path
					textureDetails = ( imageDataOffset, imageDataLength, width, height, imageType )
					savePath = saveDirectory + '/' + constructTextureFilename( datFile, iid, textureDetails=textureDetails ) + '.' + exportFormat

					# Collect any palette data
					if imageType == 8 or imageType == 9 or imageType == 10:
						paletteData, paletteType = getPaletteData( datFile, imageDataOffset, imageData=imageData, imageType=imageType )
						if not paletteData:
							print 'Skipping', iid + '; a color palette could not be found'
							continue
					else:
						paletteData = ''
						paletteType = None

					# Save the image to file
					if exportFormat == 'tpl':
						tplImage = tplEncoder( imageDimensions=(width, height), imageType=imageType, paletteType=paletteType )
						tplImage.encodedImageData = imageData
						tplImage.encodedPaletteData = paletteData
						tplImage.createTplFile( savePath )

					elif exportFormat == 'png': # Decode the image data
						pngImage = tplDecoder( '', (width, height), imageType, paletteType, imageData, paletteData )
						pngImage.deblockify()
						pngImage.createPngFile( savePath, creator='DTW - v' + programVersion )

				exported += 1

			except Exception as err:
				print 'Failed exporting textures from', iid
				print err
				failedExports.append( isoPath.split('/')[-1] )

		else: # Item is a folder.
			exported, failedExports = exportTexturesInSelection( Gui.isoFileTree.get_children(iid), iidSelectionsTuple, isoBinary, chosenSaveDirectory, exported, failedExports, exportFormat )
	
	return exported, failedExports


def exportSelectedFileTextures():

	""" Exports all textures within all selected files/folders in the Disc File Tree. """

	if not discDetected(): return
	
	# Get and validate the export format to be used.
	exportFormat = settings.get( 'General Settings', 'textureExportFormat' ).lower().replace( '.', '' )
	if exportFormat != 'png' and exportFormat != 'tpl':
		msg( 'The default export format setting (textureExportFormat) is invalid! The format must be PNG or TPL.' )
		return
	
	iidSelectionsTuple = Gui.isoFileTree.selection()
	if not iidSelectionsTuple:
		updateProgramStatus( 'Eh?' )
		msg( 'Please first select a file or folder to export.' )
		return

	elif globalDiscDetails['isoFilePath'] == '' or not os.path.exists( globalDiscDetails['isoFilePath'] ):
		updateProgramStatus( 'Export Error' )
		msg( "Unable to find the disc image. Be sure that the file path is correct and that the file has not been moved or deleted.", 'Disc Not Found' )
		return

	# Prompt for a directory to save them to.
	chosenSaveDirectory = tkFileDialog.askdirectory(
		title='Where would you like to save these textures?',
		initialdir=settings.get( 'General Settings', 'defaultSearchDirectory' ),
		parent=Gui.root,
		mustexist=True )

	if chosenSaveDirectory != '':
		exported = 0
		failedExports = []

		with open( globalDiscDetails['isoFilePath'], 'rb') as isoBinary:
			exported, failedExports = exportTexturesInSelection( iidSelectionsTuple, iidSelectionsTuple, isoBinary, chosenSaveDirectory, exported, failedExports, exportFormat )

		if len( failedExports ) == 0: 
			updateProgramStatus( 'Export Successful' )
		else:
			updateProgramStatus( 'Failed Exports' ) # writeDatFile will otherwise update this with success.
			if exported > 0:
				msg( str(exported) + ' files exported their textures successfully. However, these files failed their export:\n\n' + '\n'.join(failedExports) )
			else: msg( 'Unable to export.' )

		# Update the default directory to start in when opening or exporting files.
		settings.set( 'General Settings', 'defaultSearchDirectory', chosenSaveDirectory )
		with open( settingsFile, 'w') as theSettingsFile: settings.write( theSettingsFile )


def writeDatFile( savePath, datData, operation, datFileObj=None ):

	# Do da ting.
	try:
		with open( savePath, 'wb') as newFile:
			newFile.write( datData )

		if datFileObj:
			# Record that the changes have been saved.
			datFileObj.unsavedChanges = []
			if savePath.lower().endswith( '.bnr' ):
				restoreEditedEntries( editedBannerEntries )
			else:
				restoreEditedEntries( editedDatEntries )

		# Update the program status.
		updateProgramStatus( operation + ' Successful' )
		successStatus = True
	except:
		updateProgramStatus( operation + ' Error' )
		fileExt = os.path.splitext( savePath )[1].upper()
		msg( "There was an unknown problem while creating the {} file.".format(fileExt) )
		successStatus = False

	return successStatus


def constructTextureFilename( datFile, iid='', filepath='', textureDetails=(), forceDolphinHash=False ):

	""" Generates a file name for textures exported from DAT files (not used for banners). 
		The file extension is not included. """

	# Validate the input
	if not iid and not filepath:
		msg( 'constructTextureFilename requires an iid or filepath!' )
		return ''

	# Get or unpack information on the texture
	if not textureDetails: textureDetails = parseTextureDetails( iid )
	imageDataOffset, imageDataLength, width, height, imageType = textureDetails

	if not forceDolphinHash and not generalBoolSettings['useDolphinNaming'].get(): # Use DTW's standard naming convention
		filename = '{}_0x{:X}_{}'.format( datFile.fileName, 0x20+imageDataOffset, imageType )

	else: # Use Dolphin's file naming convention
		mipmapLevel = getMipmapLevel( iid )

		# Generate a hash on the encoded texture data
		imageData = datFile.getData( imageDataOffset, imageDataLength )
		tex_hash = xxhash.xxh64( bytes(imageData) ).hexdigest() # Requires a byte string; can't use bytearray

		# Generate a hash on the encoded palette data, if it exists
		if imageType == 8 or imageType == 9 or imageType == 10:
			# Get the palette data, and generate a hash from it
			paletteData = getPaletteData( datFile, imageDataOffset, imageData=imageData, imageType=imageType )[0]
			tlut_hash = '_' + xxhash.xxh64( bytes(paletteData) ).hexdigest() # Requires a byte string; can't use bytearray
		else:
			tlut_hash = ''

		# Format mipmap flags
		if mipmapLevel == -1: # Not a mipmaped texture
			# Assemble the finished filename, without file extension
			filename = 'tex1_' + str(width) + 'x' + str(height) + '_' + tex_hash + tlut_hash + '_' + str(imageType)
		else:
			if mipmapLevel > 0:
				mipLevel = '_mip' + str( mipmapLevel )
			else: mipLevel = ''

			# Assemble the finished filename, without file extension
			filename = 'tex1_' + str(width) + 'x' + str(height) + '_m_' + tex_hash + tlut_hash + '_' + str(imageType) + mipLevel

	return filename


def exportTextures( exportAll=False ):

	""" Exports some (what's selected) or all textures from the DAT Texture Tree. """

	# Get a list of the items in the treeview to export
	if exportAll:
		iidSelectionsTuple = Gui.datTextureTree.get_children()
	else: iidSelectionsTuple = Gui.datTextureTree.selection()

	# Make sure there are textures selected to export, and a file loaded to export from
	if not iidSelectionsTuple or not globalDatFile: 
		msg( 'No texture is selected.' )
		return

	# Get and validate the export format to be used.
	exportFormat = settings.get( 'General Settings', 'textureExportFormat' ).lower().replace( '.', '' )
	if exportFormat != 'png' and exportFormat != 'tpl':
		msg( 'The default export format setting (textureExportFormat) is invalid! The format must be PNG or TPL.' )
		return

	directoryPath = ''
	textureFilename = ''
	problemFiles = []
	workingFile = 1

	if len( iidSelectionsTuple ) == 1:
		defaultFilename = constructTextureFilename( globalDatFile, iidSelectionsTuple[0] )
		if exportFormat == 'png': filetypes = [('PNG files', '*.png'), ('TPL files', '*.tpl'), ("All files", "*.*")]
		else: filetypes = [('TPL files', '*.tpl'), ('PNG files', '*.png'), ("All files", "*.*")]

		validExt = False
		while not validExt:
			# Prompt for a filename, and a place to save the file.
			savePath = tkFileDialog.asksaveasfilename(
				title="Where would you like to export the file?", 
				initialdir=settings.get( 'General Settings', 'defaultSearchDirectory' ),
				initialfile=defaultFilename,
				defaultextension='.' + exportFormat,
				filetypes=filetypes)

			# Check the extension to see if it's valid (or just exit the loop if cancel was pressed).
			exportFormat = savePath[-3:].lower()
			if exportFormat == 'png' or exportFormat == 'tpl' or savePath == '': validExt = True
			else: msg( 'Textures may only be exported in PNG or TPL format.' )

		# If a path was given, get the directory chosen for the file
		if savePath: 
			directoryPath = os.path.dirname( savePath )
			textureFilename = os.path.basename( savePath )

	else: # Multiple textures selected for export
		directoryPath = tkFileDialog.askdirectory( # Instead of having the user choose a file name and save location, have them choose just the save location.
			title='Where would you like to save these textures?',
			initialdir=settings.get( 'General Settings', 'defaultSearchDirectory' ),
			parent=Gui.root,
			mustexist=True)

	if not directoryPath: # The dialog box was canceled
		return

	for iid in iidSelectionsTuple:
		# Set us up the GUI
		Gui.programStatus.set( 'Exporting Texture ' + str(workingFile) + '....' )
		Gui.programStatusLabel.update()
		workingFile += 1

		# Collect data/info on this texture
		textureDetails = imageDataOffset, imageDataLength, width, height, imageType = parseTextureDetails( iid )
		imageData = globalDatFile.getData( imageDataOffset, imageDataLength )

		# Construct a filepath/location to save the image to
		if textureFilename:  # May be a custom name from the user if only one texture is being exported.
			savePath = directoryPath + '/' + textureFilename
		else:
			savePath = directoryPath + '/' + constructTextureFilename( globalDatFile, iid, textureDetails=textureDetails ) + '.' + exportFormat

		# Collect the palette data, if needed
		if imageType == 8 or imageType == 9 or imageType == 10:
			paletteData, paletteType = getPaletteData( globalDatFile, imageDataOffset, imageData=imageData, imageType=imageType )
			if not paletteData:
				msg( 'A color palette could not be found for the texture at offset ' + uHex(0x20+imageDataOffset) + '. This texture will be skipped.' )
				continue
		else:
			paletteData = ''
			paletteType = None

		try: # Save the file to be exported
			if exportFormat == 'tpl':
				tplImage = tplEncoder( imageDimensions=(width, height), imageType=imageType, paletteType=paletteType )
				tplImage.encodedImageData = imageData
				tplImage.encodedPaletteData = paletteData
				tplImage.createTplFile( savePath )

			elif exportFormat == 'png': # Decode the image data
				pngImage = tplDecoder( '', (width, height), imageType, paletteType, imageData, paletteData )
				pngImage.deblockify()
				pngImage.createPngFile( savePath, creator='DTW - v' + programVersion )

		except: problemFiles.append( os.path.basename(savePath) )

	# Finished with file export/creation loop.

	# Update the default directory to start in when opening or exporting files.
	settings.set( 'General Settings', 'defaultSearchDirectory', os.path.dirname(savePath) )
	with open( settingsFile, 'w') as theSettingsFile: settings.write( theSettingsFile )

	# Give an error message for any problems encountered.
	if problemFiles: 
		msg( "There was an unknown problem while exporting these files:\n\n" + '\n'.join(problemFiles) )
		updateProgramStatus( 'Export Error' )
	else: updateProgramStatus( 'Export Successful' )


def exportBanner( event ):
	if not globalBannerFile or not globalBannerFile.data: 
		msg( 'No banner file or disc appears to be loaded.', 'Cannot Export Banner Image' )
		return

	defaultFilename = globalBannerFile.fileName + '_0x20_5'

	# Prompt for a place to save the file
	validExt = False
	while not validExt:
		# Prompt for a filename, and a place to save the file.
		savePath = tkFileDialog.asksaveasfilename(
			title="Where would you like to export the file?", 
			initialdir=settings.get( 'General Settings', 'defaultSearchDirectory' ),
			initialfile=defaultFilename,
			defaultextension='.png',
			filetypes=[('PNG files', '*.png'), ('TPL files', '*.tpl'), ("All files", "*.*")])

		# Check the extension to see if it's valid (or just exit the loop if cancel was pressed).
		fileType = savePath[-3:].lower()
		if fileType == 'png' or fileType == 'tpl' or savePath == '': validExt = True
		else: msg( 'The banner may only be exported in PNG or TPL format.' )

	if not savePath:
		return # No actions beyond this point if no path was chosen above (i.e. the dialog box was canceled)

	# Collect more info on the texture and then create a file out of it.
	imageData = hexlify( globalBannerFile.data[0x20:0x1820] )

	try: # do da ting.
		success = True
		if fileType == 'tpl': 
			tplImage = tplEncoder( imageDimensions=(96, 32), imageType=5 )
			tplImage.encodedImageData = imageData
			tplImage.encodedPaletteData = ''
			tplImage.createTplFile( savePath )

		else: # png
			pngImage = tplDecoder( imageDimensions=(96, 32), imageType=5, encodedImageData=imageData )
			pngImage.deblockify()
			pngImage.createPngFile( savePath, creator='DTW - v' + programVersion )

	except: success = False

	# Update the default directory to start in when opening or exporting files.
	settings.set( 'General Settings', 'defaultSearchDirectory', os.path.dirname(savePath) )
	with open( settingsFile, 'w') as theSettingsFile: settings.write( theSettingsFile )

	# Give an error message for any problems encountered.
	if not success: 
		msg( "There was an unknown problem while exporting the banner." )
		updateProgramStatus( 'Export Error' )
	else: updateProgramStatus( 'Export Successful' )


def noDiscChangesToBeSaved(): # Asks the user if they would like to forget any unsaved disc changes in order to close the program or load a new file.
	# Check that there aren't any unsaved changes with the currently selected ISO (if there is one).
	global unsavedDiscChanges
	youShallPass = True

	if unsavedDiscChanges != []:
		if programClosing: warning = "The changes below haven't been saved to disc. Are you sure you \nwant to close?\n\n" + '\n'.join( unsavedDiscChanges )
		else: warning = 'The changes below will be forgotten if you change or reload the disc before saving. Are you sure you want to do this?\n\n' + '\n'.join( unsavedDiscChanges )
		youShallPass = tkMessageBox.askyesno( 'Unsaved Changes', warning )

	if youShallPass:
		unsavedDiscChanges = [] # Forgets the past changes.
		#restoreEditedEntries()

	return youShallPass


def getHexEditorPath():
	# Check/ask for a specified hex editor to open files in.
	if not os.path.exists( settings.get( 'General Settings', 'hexEditorPath' ) ):
		popupWindow = PopupEntryWindow( Gui.root, message='Please specify the full path to your hex editor. '
			'(Specifying this path only needs to\nbe done once, and can be changed at any time in the settings.ini file.\nIf you have already set this, '
			"the path seems to have broken.)\n\nNote that this feature only shows you a copy of the data;\nany changes made will not be saved to the file or disc."
			'\n\nPro-tip: In Windows, if you hold Shift while right-clicking on a file, there appears a context menu \n'
			"""option called "Copy as path". This will copy the file's full path into your clipboard. Or if it's\na shortcut, """
			"""you can quickly get the full file path by right-clicking on the icon and going to Properties.""", title='Set hex editor path' )
		hexEditorPath = popupWindow.entryText.replace( '"', '' )

		if hexEditorPath != '':
			# Update the path in the settings file and global variable.
			settings.set( 'General Settings', 'hexEditorPath', hexEditorPath )
			with open( settingsFile, 'w') as theSettingsFile: settings.write( theSettingsFile ) # Updates a pre-existing settings file entry, or just creates a new file.

	else: hexEditorPath = settings.get( 'General Settings', 'hexEditorPath' )

	return hexEditorPath


def viewFileHexFromFileTree():

	""" Gets and displays hex data for a file within a disc in the user's hex editor of choice. 
		Used by the ISO File Tree's context menu. """

	if not discDetected(): return
	
	iidSelectionsTuple = Gui.isoFileTree.selection()

	if iidSelectionsTuple == '': 
		msg( 'No file is selected.' )
		return
	elif len( iidSelectionsTuple ) > 1:
		msg( 'Please choose only one file for this operation.' )
		return

	entity, isoOffset, fileSize, isoPath, source, data = Gui.isoFileTree.item( iidSelectionsTuple[0], 'values' )[1:] # Excluding description

	if len( iidSelectionsTuple ) == 1 and entity == 'file': # Ensures there's only one selection and it's not a folder.

		hexEditorPath = getHexEditorPath()
		if not hexEditorPath: return
		
		# Create a temporary file if this is not an external file already.
		if source == 'iso':
			# Open the disc image and retrieve the binary for the target file.
			with open( globalDiscDetails['isoFilePath'], 'rb') as isoBinary:
				isoBinary.seek( int(isoOffset, 16) )
				datData = bytearray( isoBinary.read( int(fileSize) ) ) #todo: test if this conversion is even needed

		elif source == 'path': # In this case, "data" is a filepath to an external file
			with open( data, 'rb') as origFile:
				datData = bytearray( origFile.read() )

		else: datData = bytearray.fromhex( data ) # source == 'ram'

		# Create a file name with folder names included, so that multiple files of the same name (but from different folders) can be opened.
		#fileName = '-'.join( isoPath.split('/')[1:] )
		fileName = isoPath.replace( '/', '-' )
		saveAndShowTempDatData( hexEditorPath, datData, fileName )

	else: msg( 'You must select a file for this operation (not a folder).' )


def viewDatFileHex():

	""" Gets and displays hex data of a loaded DAT file in the user's hex editor of choice. 
		Used by the Structural Analysis tab. """

	if not globalDatFile:
		msg( 'No DAT file has been loaded.' )
		return

	hexEditorPath = getHexEditorPath()
	if not hexEditorPath: return

	saveAndShowTempDatData( hexEditorPath, globalDatFile.getFullData(), globalDatFile.fileName )


def saveAndShowTempDatData( hexEditorPath, datData, fileName ):
	# Save the file data to a temporary file.
	try:
		tempFilePath = scriptHomeFolder + '\\bin\\tempFiles\\' + fileName
		createFolders( os.path.split(tempFilePath)[0] )

		with open( tempFilePath, 'wb' ) as newFile:
			newFile.write( datData )
	except: # Pretty unlikely
		print 'Error creating temporary file for saveAndShowTempDatData()!'
		return

	# Open the temp file in the user's editor of choice.
	if os.path.exists( hexEditorPath ) and os.path.exists( tempFilePath ):
		command = '"' + hexEditorPath + '" "' + tempFilePath + '"'
		subprocess.Popen( command, stderr=subprocess.STDOUT, creationflags=0x08000000 )

	else: msg( "Unable to find the specified hex editor program (or new temporary file). You may want to double check the path saved in DTW's settings.ini file." )


def runInEmulator():
	# Check/ask for a specified program to open the file in.
	if not os.path.exists( settings.get( 'General Settings', 'emulatorPath' ) ):
		popupWindow = PopupEntryWindow( Gui.root, message='Please specify the full path to your emulator. '
			'(Specifying this path only needs to\nbe done once, and can be changed at any time in the settings.ini file.'
			'\nIf you have already set this, the path seems to have broken.)'
			'\n\nPro-tip: In Windows, if you hold Shift while right-clicking on a file, there appears a context \nmenu '
			"""option called "Copy as path". This will copy the file's full path into your clipboard. Or if it's a\nshortcut, """
			"""you can quickly get the full file path by right-clicking on the icon and going to Properties.""", title='Set Emulator Path' )
		emulatorPath = popupWindow.entryText.replace( '"', '' )

		if emulatorPath != '':
			# Update the path in the settings file and global variable.
			settings.set( 'General Settings', 'emulatorPath', emulatorPath )
			with open( settingsFile, 'w') as theSettingsFile: settings.write( theSettingsFile ) # Updates a pre-existing settings file entry, or just creates a new file.
	else: 
		emulatorPath = settings.get( 'General Settings', 'emulatorPath' )

	if emulatorPath:
		# Check that there's a disc loaded, and that the emulator and disc have valid paths
		if not discDetected(): return
		elif not os.path.exists( emulatorPath ):
			msg( "Unable to find the Dolphin executable. You may want to double check the path saved in DTW's settings.ini file." )
		else:
			# Send the disc filepath to Dolphin
			# Must use '--exec'. Because '/e' is incompatible with Dolphin 5+, while '-e' is incompatible with Dolphin 4.x
			# '--batch' will prevent dolphin from unnecessarily scanning game/ISO directories, and will shut down Dolphin when the game is stopped.
			command = '"{}" --batch --exec="{}"'.format( emulatorPath, globalDiscDetails['isoFilePath'] )

			process = subprocess.Popen( command, shell=True, stderr=subprocess.STDOUT, creationflags=0x08000000 ) # shell=True gives access to all shell features.


																				#=================================#
																				# ~ ~ Primary Disc Operations ~ ~ #
																				#=================================#


def initializeDiscFileTree( refreshGui ):

	""" Called when first loading a disc or root folder, to clear/update the GUI. """

	global unsavedDiscChanges
	unsavedDiscChanges = []
	Gui.isoFileTreeBg.place_forget() # Removes the background image if present

	# Delete the current items in the tree
	for item in Gui.isoFileTree.get_children(): Gui.isoFileTree.delete( item )

	# If desired, temporarily show the user that all items have been removed (Nice small indication that the iso is actually updating)
	if refreshGui: Gui.root.update()

	# Disable buttons in the iso operations panel. They're re-enabled later if all goes well
	for widget in Gui.isoOpsPanelButtons.winfo_children():
		#if widget.winfo_class() == 'TButton':
			widget.config( state='disabled' ) # Will stay disabled if there are problems loading a disc.

	# Set the GUI's other values back to default.
	Gui.isoOffsetText.set( 'Disc Offset: ' )
	Gui.internalFileSizeText.set( 'File Size: ' )
	Gui.internalFileSizeLabelSecondLine.set( '' )


def getDiscSystemFileInfo( isoPath, apploaderPath='' ):

	""" Collects basic info on system files in the disc, including file location/size for the DOL/FST, and the FST's data. 
		If apploaderPath is provided, it means a root folder is being scanned, and isoPath will instead be a file path 
		to a boot.bin or iso.hdr file. """

	# Read basic stats from the ISO directly.
	with open( isoPath, 'rb') as isoBinary:
		gameId = isoBinary.read(6).decode( 'utf-8' )
		globalDiscDetails['gameId'] = gameId

		# Get info on the DOL and the game's FST/TOC (File System Table/Table of Contents).
		isoBinary.seek( 0x420 )
		dolOffset = toInt( isoBinary.read(4) )
		fstOffset = toInt( isoBinary.read(4) )
		dolSize = fstOffset - dolOffset
		fstSize = toInt( isoBinary.read(4) )
		#maxFstSize = toInt( isoBinary.read(4) )

		# Get components to calculate the apploader size
		if apploaderPath == '': # Scanning a disc file (ISO/GCM)
			isoBinary.seek( 0x2454 )
			codeSize = toInt( isoBinary.read(4) )
			trailerSize = toInt( isoBinary.read(4) )

			# Get the FST data
			isoBinary.seek( fstOffset )
			fstData = isoBinary.read( fstSize ).encode( 'hex' )
		else:
			with open( apploaderPath, 'rb' ) as apploaderBinary:
				apploaderBinary.seek( 0x14 )
				codeSize = toInt( apploaderBinary.read(4) )
				trailerSize = toInt( apploaderBinary.read(4) )
			fstData = ''

	# Calculate the apploader's size
	apploaderSize = roundTo32( codeSize + trailerSize )

	return gameId, dolOffset, fstOffset, dolSize, fstSize, fstData, apploaderSize


def getFileDataFromDiscTree( iid='', iidValues=() ): # Returns the file data in hex-string form.
	if iid:
		if Gui.isoFileTree.exists( iid ):
			_, entity, isoOffset, fileSize, _, source, data = Gui.isoFileTree.item( iid, 'values' ) # description, entity, isoOffset, fileSize, isoPath, source, data
		else: return None
	elif iidValues: entity, isoOffset, fileSize, source, data = iidValues
	else: return None # raise IOError( 'An iid or a set of iidValues must be provided to getFileDataFromDiscTree' )

	# Enough info is available; pull the file.
	if entity == 'file':
		if source == 'iso':
			if os.path.exists( globalDiscDetails['isoFilePath'] ):
				# Open the disc image and retrieve the binary for the target file.
				with open( globalDiscDetails['isoFilePath'], 'rb') as isoBinary:
					isoBinary.seek( int(isoOffset, 16) )
					fileHex = isoBinary.read( int(fileSize) ).encode('hex')
			else: return None #msg( 'The disc that this file resided in can no longer be found (it may have been moved/renamed/deleted).' )

		elif source == 'ram':
			fileHex = data

		else: # source == 'path', meaning data is a filepath to an external file
			if os.path.exists( data ):
				with open( data, 'rb') as externalFile:
					fileHex = externalFile.read().encode( 'hex' )
			else: return None #msg( 'The externally referenced file at "' + data + '" can no longer be found (it may have been moved/renamed/deleted).' )
		return fileHex

	else: return None


def getFileDataFromDiscTreeAsBytes( iid='', iidValues=() ): # Returns the file data in bytearray form (should migrate all data manipulations to this methodology).
	if iid:
		if Gui.isoFileTree.exists( iid ): 
			_, entity, isoOffset, fileSize, _, source, data = Gui.isoFileTree.item( iid, 'values' ) # description, entity, isoOffset, fileSize, isoPath, source, data
		else: 
			print 'getFileDataFromDiscTreeAsBytes(): Could not find the given iid, {}, in the treeview.'.format( iid )
			return None
	elif iidValues: entity, isoOffset, fileSize, source, data = iidValues
	else: return None # raise IOError( 'An iid or a set of iidValues must be provided to getFileDataFromDiscTree' )
	if entity != 'file': return None

	# Enough info is available; pull the file.
	if source == 'iso':
		if os.path.exists( globalDiscDetails['isoFilePath'] ):
			# Open the disc image and retrieve the binary for the target file.
			with open( globalDiscDetails['isoFilePath'], 'rb') as isoBinary:
				isoBinary.seek( int(isoOffset, 16) )
				byteData = bytearray( isoBinary.read( int(fileSize) ) )
		else: 
			print 'getFileDataFromDiscTreeAsBytes(): Disc could not be found.'
			return None #msg( 'The disc that this file resided in can no longer be found (it may have been moved/renamed/deleted).' )

	elif source == 'ram':
		byteData = bytearray.fromhex( data ) # Exists as a hex string

	else: # source == 'path', meaning data is a filepath to an external file
		if os.path.exists( data ):
			with open( data, 'rb') as externalFile:
				byteData = bytearray( externalFile.read() )
		else: return None #msg( 'The externally referenced file at "' + data + '" can no longer be found (it may have been moved/renamed/deleted).' )
	
	return byteData


def getFileSizeFromDiscTree( iid ): # Returns an int for the file size, in bytes
	assert Gui.isoFileTree.exists( iid ), 'Nonexistant file requested for getFileSizeFromDiscTree'
	
	_, entity, _, fileSize, _, source, data = Gui.isoFileTree.item( iid, 'values' )

	if entity == 'file':
		if source == 'iso': 
			return int( fileSize )

		elif source == 'ram': 
			return len( data )/2

		else: # source == 'path', meaning data is a filepath to an external file
			if not os.path.exists( data ): # Failsafe
				msg( 'The externally referenced file at "' + data + '" can no longer be found (it may have been moved/renamed/deleted).' )
				return 0
				
			return int( os.path.getsize( data ) )
	else: 
		return 0


def updateBannerFileInfo( updateTextEntries=True, imageName='' ):
	global updatingBannerFileInfo, stopAndReloadBannerFileInfo

	# Prevent conflicts with an instance of this function that may already be running (let that instance finish its current iteration and call this function again)
	if updatingBannerFileInfo:
		stopAndReloadBannerFileInfo = True
		return
	updatingBannerFileInfo = True

	if updateTextEntries:
		# Delete existing content in the GUI
		Gui.gameName1Field['state'] = 'normal' # Must be enabled before can edit, even programmatically
		Gui.gameName1Field.delete( '1.0', 'end' )
		Gui.shortTitle.set( '' )
		Gui.shortMaker.set( '' )
		Gui.longTitle.set( '' )
		Gui.longMaker.set( '' )
		Gui.gameDescField.delete( '1.0', 'end' )

	# Determine if an animation will be used, and where, by checking if it would be visible to the user
	currentlySelectedTab = Gui.root.nametowidget( Gui.mainTabFrame.select() )
	if currentlySelectedTab == Gui.discTab: canvasToAnimate = Gui.bannerCanvas
	elif currentlySelectedTab == Gui.discDetailsTab: canvasToAnimate = Gui.bannerCanvas2
	else: canvasToAnimate = None

	if canvasToAnimate and canvasToAnimate.bannerGCstorage: # An existing banner image is currently visible
		# Remove the banner on the opposite disc tab
		if currentlySelectedTab == Gui.discTab: Gui.bannerCanvas2.delete('all')
		elif currentlySelectedTab == Gui.discDetailsTab: Gui.bannerCanvas.delete('all')

		# Remove the banner on the current disc tab using a vertical fade
		width, height = canvasToAnimate.pilImage.size
		pixels = canvasToAnimate.pilImage.load()
		bandHeight = 30
		for y in xrange( height + bandHeight ):

			if stopAndReloadBannerFileInfo:
				updatingBannerFileInfo = False
				stopAndReloadBannerFileInfo = False
				updateBannerFileInfo( updateTextEntries, imageName )
				return

			for bandSegment in xrange( bandHeight ): # This will modify the current row, and then prior rows (up to the bandHeight)
				targetRow = y - bandSegment
				if targetRow >= 0 and targetRow < height:
					for x in xrange( width ):
						initialAlpha = pixels[x, targetRow][3]
						newAlpha = int( initialAlpha - ( float(bandSegment)/bandHeight * initialAlpha ) )
						#if x == 0: print 'row', targetRow, ':', initialAlpha, 'to', newAlpha
						pixels[x, targetRow] = pixels[x, targetRow][:3] + (newAlpha,)
					canvasToAnimate.bannerGCstorage = ImageTk.PhotoImage( canvasToAnimate.pilImage )
					canvasToAnimate.itemconfig( canvasToAnimate.canvasImageItem, image=canvasToAnimate.bannerGCstorage )
					canvasToAnimate.update() # update_idletasks
					time.sleep( .0005 ) # 500 us
		canvasToAnimate.delete('all')
		time.sleep( .4 )
	else: # No banner currently visible. Clear the canvases
		Gui.bannerCanvas.delete('all')
		Gui.bannerCanvas2.delete('all')

	# Make sure there's banner file data
	if not globalBannerFile.data:
		# Delete the remainder of the content in the GUI and return
		Gui.bannerCanvas.pilImage = None
		Gui.bannerCanvas.bannerGCstorage = None
		Gui.bannerCanvas.canvasImageItem = None
		Gui.bannerCanvas2.pilImage = None
		Gui.bannerCanvas2.bannerGCstorage = None
		Gui.bannerCanvas2.canvasImageItem = None

		updatingBannerFileInfo = False
		return

	if updateTextEntries:
		if Gui.countryCode.get() == 'us': encoding = 'latin_1' # Decode assuming English or other European countries
		else: encoding = 'shift_jis' # The country code is 'jp', for Japanese.

		# Get the raw hex from the file and decode it, splitting on the first stop byte
		Gui.shortTitle.set( globalBannerFile.data[0x1820:(0x1820 + 0x20)].split('\x00')[0].decode(encoding) )
		Gui.shortMaker.set( globalBannerFile.data[0x1840:(0x1840 + 0x20)].split('\x00')[0].decode(encoding) )
		Gui.longTitle.set( globalBannerFile.data[0x1860:(0x1860 + 0x40)].split('\x00')[0].decode(encoding) )
		Gui.longMaker.set( globalBannerFile.data[0x18a0:(0x18a0 + 0x40)].split('\x00')[0].decode(encoding) ) # Can be a name or description
		Gui.gameDescField.insert( '1.0', globalBannerFile.data[0x18e0:(0x18e0 + 0x80)].split('\x00')[0].decode( encoding ) )

		if globalBannerFile.source == 'disc':
			Gui.gameIdTextEntry.enableEntry()

			# Update the gameName1Field
			# Doing this here rather than prior functions for aesthetics; here, the text will populate at the same time as the other text.
			Gui.gameName1Field.insert( '1.0', imageName )
		else:
			Gui.gameIdTextEntry.disableEntry()

			# Update the gameName1Field
			Gui.gameName1Field.insert( '1.0', "\t\t[ This isn't located in the banner file. \n\t\t  Open your disc to edit this entry. ]" )
			Gui.gameName1Field['state'] = 'disabled' # Must be disabled only after editing

	# Read and decode the banner image data
	bannerImage = tplDecoder( imageDimensions=(96, 32), imageType=5, encodedImageData=globalBannerFile.data[0x20:0x1820] )
	bannerImage.deblockify() # This decodes the image data, to create an rgbaPixelArray.
	Gui.bannerCanvas.pilImage = Image.new( 'RGBA', (96, 32) )
	Gui.bannerCanvas.pilImage.putdata( bannerImage.rgbaPixelArray )
	Gui.bannerCanvas.bannerGCstorage = ImageTk.PhotoImage( Gui.bannerCanvas.pilImage ) # To prevent garbage collection from deleting the image (including after image modification/replacement)
	Gui.bannerCanvas2.pilImage = Gui.bannerCanvas.pilImage
	Gui.bannerCanvas2.bannerGCstorage = Gui.bannerCanvas.bannerGCstorage

	if canvasToAnimate:
		# Add the banner on the opposite disc tab (instantly; no animation)
		if currentlySelectedTab == Gui.discTab:
			Gui.bannerCanvas2.canvasImageItem = Gui.bannerCanvas2.create_image( 0, 0, image=Gui.bannerCanvas2.bannerGCstorage, anchor='nw' )
		elif currentlySelectedTab == Gui.discDetailsTab:
			Gui.bannerCanvas.canvasImageItem = Gui.bannerCanvas.create_image( 0, 0, image=Gui.bannerCanvas.bannerGCstorage, anchor='nw' )

		# Add the banner on the current tab using a dissolve fade.
		# First, create a blank image on the canvas
		dissolvingImage = Image.new( 'RGBA', (96, 32), (0,0,0,0) )
		canvasToAnimate.canvasImageItem = canvasToAnimate.create_image( 0, 0, image=ImageTk.PhotoImage(dissolvingImage), anchor='nw' )
		dessolvingPixels = dissolvingImage.load()
		width, height = 96, 32

		# Display the converted image
		bannerPixels = canvasToAnimate.pilImage.load()
		pixelsToUpdatePerPass = 172
		pixelsNotShown = [ (x, y) for x in range(width) for y in range(height) ] # Creates a list of all possible pixel coordinates for the banner image
		while pixelsNotShown:

			if stopAndReloadBannerFileInfo:
				updatingBannerFileInfo = False
				stopAndReloadBannerFileInfo = False
				updateBannerFileInfo( updateTextEntries, imageName )
				return

			# Randomly pick out some pixels to show
			pixelsToShow = []
			while len( pixelsToShow ) < pixelsToUpdatePerPass and pixelsNotShown:
				randomIndex = random.randint( 0, len(pixelsNotShown) - 1 )
				pixelsToShow.append( pixelsNotShown[randomIndex] )
				del pixelsNotShown[randomIndex]
			if pixelsToUpdatePerPass > 2: pixelsToUpdatePerPass -= math.sqrt( pixelsToUpdatePerPass )/2

			# Update the chosen pixels
			for pixelCoords in pixelsToShow: dessolvingPixels[pixelCoords] = bannerPixels[pixelCoords]

			# Update the GUI
			canvasToAnimate.bannerGCstorage = ImageTk.PhotoImage( dissolvingImage )
			canvasToAnimate.itemconfig( canvasToAnimate.canvasImageItem, image=canvasToAnimate.bannerGCstorage )
			canvasToAnimate.update()
			time.sleep( .022 )

		canvasToAnimate.canvasImageItem = canvasToAnimate.create_image( 0, 0, image=canvasToAnimate.bannerGCstorage, anchor='nw' )

	else: # No animation; just add the banner to the GUI
		Gui.bannerCanvas.canvasImageItem = Gui.bannerCanvas.create_image( 0, 0, image=Gui.bannerCanvas.bannerGCstorage, anchor='nw' )
		Gui.bannerCanvas2.canvasImageItem = Gui.bannerCanvas2.create_image( 0, 0, image=Gui.bannerCanvas2.bannerGCstorage, anchor='nw' )

	updatingBannerFileInfo = False


def reloadBanner():

	""" This is solely used by the radio buttons for file encoding on the Disc Details Tab;
		selecting one of those encodings should reload the banner file with that encoding. """

	# Cancel if no banner file appears to be loaded
	if not globalBannerFile or not globalBannerFile.data: return

	# Get the gameName1Field text, which won't be changed
	discImageName = Gui.gameName1Field.get( '1.0', 'end' )[:-1] # ignores trailing line break (which the get() method seems to add)

	updateBannerFileInfo( imageName=discImageName )


def populateDiscDetails( discSize=0 ):

	""" This primarily updates the Disc Details Tab using information from boot.bin/ISO.hdr; it directly handles 
		updating the fields for disc filepath, gameID (and its breakdown), region and version, image name,
		20XX version (if applicable), and disc file size.

		The disc's country code is also found, which is used to determine the encoding of the banner file.
		A call to update the banner image and other disc details is also made in this function.

		This function also updates the disc filepath on the Disc File Tree tab (and the hover/tooltip text for it). """

	missingFiles = []

	# Update the filepath field in the GUI, and create a shorthand string that will fit nicely on the Disc File Tree tab
	Gui.isoDestination.set( globalDiscDetails['isoFilePath'] )
	frameWidth = Gui.isoOverviewFrame.winfo_width()
	accumulatingName = ''
	for character in reversed( globalDiscDetails['isoFilePath'] ):
		accumulatingName = character + accumulatingName
		Gui.isoPathShorthand.set( accumulatingName )
		if Gui.isoPathShorthandLabel.winfo_reqwidth() > frameWidth:
			# Reduce the path to the closest folder (that fits in the given space)
			normalizedPath = os.path.normpath( accumulatingName[1:] )
			if '\\' in normalizedPath: Gui.isoPathShorthand.set( '\\' + '\\'.join( normalizedPath.split('\\')[1:] ) )
			else: Gui.isoPathShorthand.set( '...' + normalizedPath[3:] ) # Filename is too long to fit; show as much as possible
			break
	ToolTip( Gui.isoPathShorthandLabel, globalDiscDetails['isoFilePath'], delay=500, wraplength=400, follow_mouse=1 )

	# Look up info within boot.bin (gameID, disc version, and disc region)
	bootBinData = getFileDataFromDiscTreeAsBytes( iid=scanDiscForFile('boot.bin') )
	if not bootBinData: 
		missingFiles.append( 'boot.bin or ISO.hdr' )
		Gui.gameIdText.set( '' )
		Gui.isoVersionText.set( '' )
		imageName = ''
	else:
		gameId = bootBinData[:6].decode( 'ascii' ) # First 6 bytes
		Gui.gameIdText.set( gameId )
		versionHex = hexlify( bootBinData[7:8] ) # Byte 7
		ntscRegions = ( 'A', 'E', 'J', 'K', 'R', 'W' )
		if gameId[3] in ntscRegions: Gui.isoVersionText.set( 'NTSC 1.' + versionHex )
		else: Gui.isoVersionText.set( 'PAL 1.' + versionHex )
		imageName = bootBinData[0x20:0x20 + 0x3e0].split('\x00')[0].decode( 'ascii' ) # Splitting on the first stop byte

	# Get Bi2.bin and check the country code (used to determine encoding for the banner file)
	bi2Iid = scanDiscForFile( 'bi2.bin' ) # This will try for 'iso.hdr' if bi2 doesn't exist
	bi2Data = getFileDataFromDiscTreeAsBytes( iid=bi2Iid )
	if not bi2Data:
		missingFiles.append( 'bi2.bin or ISO.hdr' )
	else:
		# Depending on which file is used, get the location/offset of where the country code is in the file
		if bi2Iid.endswith( 'iso.hdr' ): countryCodeOffset = 0x458 # (0x440 + 0x18)
		else: countryCodeOffset = 0x18

		# Set the country code
		if toInt( bi2Data[countryCodeOffset:countryCodeOffset+4] ) == 1: Gui.countryCode.set( 'us' )
		else: Gui.countryCode.set( 'jp' )

	# Remove the existing 20XX version label (the label displayed next to the StringVar, not the StringVar itself), if it's present.
	for widget in Gui.discDetailsTab.row2.winfo_children():
		thisWidgets = widget.grid_info()
		if thisWidgets['row'] == '1' and ( thisWidgets['column'] == '8' or thisWidgets['column'] == '9' ):
			widget.destroy()

	# Update the 20XX version label
	if globalDiscDetails['is20XX']:
		twentyxxLabel = ttk.Label( Gui.discDetailsTab.row2, text='20XX Version:' )
		twentyxxLabel.grid( column=8, row=1, sticky='e', padx=Gui.discDetailsTab.row2.padx )
		twentyxxLabel.bind( '<Enter>', lambda event: setDiscDetailsHelpText('20XX Version') )
		twentyxxLabel.bind( '<Leave>', setDiscDetailsHelpText )
		twentyxxVersionLabel = ttk.Label( Gui.discDetailsTab.row2, text=globalDiscDetails['is20XX'] )
		twentyxxVersionLabel.grid( column=9, row=1, sticky='w', padx=Gui.discDetailsTab.row2.padx )
		twentyxxVersionLabel.bind( '<Enter>', lambda event: setDiscDetailsHelpText('20XX Version') )
		twentyxxVersionLabel.bind( '<Leave>', setDiscDetailsHelpText )

	# Load the banner and other info contained within the banner file
	bannerIid = scanDiscForFile( 'opening.bnr' )
	if not bannerIid:
		missingFiles.append( 'opening.bnr' )
	else:
		global globalBannerFile
		globalBannerFile = hsdFiles.datFileObj( source='disc' )
		fileName = os.path.basename( Gui.isoFileTree.item( bannerIid, 'values' )[4] ) # Using isoPath (will probably be all lowercase anyway)
		globalBannerFile.load( bannerIid, fileData=getFileDataFromDiscTreeAsBytes( iid=bannerIid ), fileName=fileName )
		updateBannerFileInfo( imageName=imageName )

	# Get and display the disc's total file size
	if discSize: # If this was provided, it's a root folder that's been opened (and this value is a predicted one)
		isoByteSize = discSize
	else: isoByteSize = os.path.getsize( globalDiscDetails['isoFilePath'] )
	isoSize = "{:,}".format( isoByteSize )
	Gui.isoFilesizeText.set( isoSize + ' bytes' )
	Gui.isoFilesizeTextLine2.set( '(i.e.: ' + "{:,}".format(isoByteSize/1048576) + ' MB, or ' + humansize(isoByteSize) + ')' )

	# Alert the user of any problems detected
	if missingFiles: msg( 'Some details of the disc could not be determined, because the following files could not be found:\n\n' + '\n'.join(missingFiles) )


def get20xxRandomNeutralNameOffset( fullFileName ):

	""" Recognizes stages within the set of 'Random Neutrals' (The sets of 16 stages for each legal neutral stage), 
		and then returns the MnSlChr file offset of the stage name table for the stage in question, as well as the
		base stage name (e.g. a string of "Dream Land (N64)"). Returns -1 if the stage is not among the random neutrals. """

	nameOffset = -1
	baseStageName = ''
	fileName, fileExt = os.path.splitext( fullFileName )
	fileExt = fileExt.lower()

	# Convert the 20XX game version to a float
	try:
		normalizedVersion = float( ''.join([char for char in globalDiscDetails['is20XX'] if char.isdigit() or char == '.']) ) # removes non-numbers and typecasts it
	except:
		normalizedVersion = 0

	if 'BETA' not in globalDiscDetails['is20XX'] and normalizedVersion >= 4.06: # This version and up use a table in MnSlChr
		tableOffsets = { # Offsets for stage name pointer tables (accounts for file header)
				'GrNBa': 	0x3C10E0, 	# Battlefield
				'GrNLa': 	0x3C1340, 	# Final Destination
				'GrSt':		0x3C15A0, 	# Yoshi's Story
				'GrIz':		0x3C1800, 	# Fountain
				'GrOp':		0x3C1A60, 	# Dream Land
				'GrP':		0x3C1CC0 } 	# Stadium

		# Parse the file name string for the custom stage index
		if fileName.startswith( 'GrP' ) and fileName[3] in hexdigits: # For Pokemon Stadium, which follows a slighly different convention (e.g. "GrP2.usd")
			index = int( fileName[-1], 16 )
			nameOffset = tableOffsets['GrP'] + 0x50 + ( index * 0x20 )
			baseStageName = stageNameLookup['Ps.']

		elif fileName in tableOffsets and fileExt[1] in hexdigits:
			index = int( fileExt[1], 16 )
			nameOffset = tableOffsets[fileName] + 0x50 + ( index * 0x20 )
			baseStageName = stageNameLookup[fullFileName[2:5]]

	return ( nameOffset, baseStageName )


def getStageName( fullFileName, parentIid, cssData ):

	""" is20XX is a string; it's empty if we're not working with a version of 20XXHP,
		and if it is 20XX, the string can be of the form 3.03, BETA 02, 4.07++, 4.08, etc. 
		The priority for this process is:
			-> Check for 'Random Neutrals' stage names
			-> Check for any other special 20XX stage files
			-> Check if it's a Target Test stage
			-> Check other vanilla file names
			-> Assign a default 'Stage file' file name if none of the above find anything """

	stageName = ''

	if globalDiscDetails['is20XX']:
		# Try to recognize stages within the set of 'Random Neutrals' (The sets of 16 stages for each legal neutral stage)
		nameOffset, baseStageName = get20xxRandomNeutralNameOffset( fullFileName )

		if nameOffset != -1:
			# Go to the address pointed to by the table, and read the string there
			stageName = cssData[nameOffset:nameOffset+0x20].split('\x00')[0].decode( 'ascii' )

			# Check for convenience folders, to determine how to modify the stage description
			if parentIid == globalDiscDetails['gameId'].lower(): # No convenience folders
				# Get the vanilla stage name as a base for the descriptive name
				stageName = baseStageName + ', ' + stageName
			else:
				stageName = '    ' + stageName # Extra spaces added to indent the name from the stage folder name

			return stageName

		stageName = specialStagesIn20XX.get( fullFileName[2:], '' )
		if stageName:
			return stageName

	# Check for Target Test stages
	if fullFileName[2] == 'T':
		characterName = charNameLookup.get( fullFileName[3:5], '' )

		if characterName:
			if characterName.endswith( 's' ):
				stageName = characterName + "'"
			else:
				stageName = characterName + "'s"

			# Check if convenience folders are turned on. If they're not, this name should have more detail
			if not parentIid == 't': # Means convenience folders are not turned on
				stageName += " Target Test stage"

			return stageName

	# If still unable to determine, check vanilla file name lookups
	stageName = stageNameLookup.get( fullFileName[2:5], '' )
	if not stageName:
		stageName = 'Stage file'

	return stageName


def setStageDescriptions():
	cssData = getFileDataFromDiscTreeAsBytes( iid=getCssIid() )
	if not cssData: return

	# Recursively scan through all files in the treeview, and update the description/filename for stage files
	def scanFolder( parentIid='' ):
		for iid in Gui.isoFileTree.get_children( parentIid ):
			iidValues = Gui.isoFileTree.item( iid, 'values' )
			if iidValues[1] == 'file':
				fileName = iidValues[4].split( '/' )[-1] # 5th item in iidValues is isoPath
				if not fileName.startswith( 'Gr' ): continue

				newDescription = getStageName( fileName, parentIid, cssData )

				Gui.isoFileTree.item( iid, values=[newDescription] + list( iidValues[1:] ) )
			else:
				scanFolder( iid )

	scanFolder()


def addItemToDiscFileTree( isFolder, isoPath, entryName, entryOffset, entryLength, parent, source, data ):
	description = ''

	if isFolder:
		if entryName == 'audio':
			description = '\t - Music and Sound Effects -'
			iconImage = Gui.imageBank( 'audioIcon' )
		else: iconImage = Gui.imageBank( 'folderIcon' )

		Gui.isoFileTree.insert( parent, 'end', iid=isoPath.lower(), text=' ' + entryName, values=(description, 'folder', 'native', '', isoPath, source, ''), image=iconImage )

	else: # This is a file.
		filenameOnly, ext = os.path.splitext( entryName )
		ext = ext.lower()

		if not generalBoolSettings['useDiscConvenienceFolders'].get():
			# Set a description for the file
			if ext in ( '.hps', '.ssm', '.sem' ) and filenameOnly in audioNameLookup: 
				description = audioNameLookup[ filenameOnly ]
			elif entryName.startswith( 'Ef' ):
				if entryName == 'EfFxData.dat': description = 'Effects file for Fox & Falco'
				else:
					character = charNameLookup.get( entryName[2:4] )
					if character: description = 'Effects file for ' + character
					else: description = 'Effects file'
			elif entryName.startswith( 'GmRstM' ):
				character = charNameLookup.get( entryName[6:8] )
				if character: description = 'Results screen animations for ' + character
				else: description = 'Results screen animations'
			elif entryName.startswith( 'GmRegend' ): description = 'Congratulations screens'
			elif ext == '.mth':
				if entryName.startswith( 'MvEnd' ): description = '1-P Ending Movie'
				elif filenameOnly in movieNameLookup: description = movieNameLookup[filenameOnly]
			elif entryName.startswith( 'Pl' ): # Character file.
				colorKey = entryName[4:6]
				character = charNameLookup.get( entryName[2:4], 'Unknown Character' )

				if character.endswith('s'): description = character + "' "
				else: description = character + "'s "

				if colorKey == '.d': description += 'NTSC data & shared textures' # e.g. "PlCa.dat"
				elif colorKey == '.p': description += 'PAL data & shared textures'
				elif colorKey == '.s': description += 'SDR data & shared textures'
				elif colorKey == 'AJ': description += 'animation data'
				elif colorKey == 'Cp': 
					charName = charNameLookup.get( entryName[6:8] )
					if charName:
						if ']' in charName: charName = charName.split(']')[1]
						description += 'copy power (' + charName + ')'
					else:
						description += 'copy power'
				elif colorKey == 'DV': description += 'idle animation data'
				else: description += charColorLookup.get( colorKey, 'Unknown color' ) + ' costume'

				if globalDiscDetails['is20XX']:
					if ext == '.lat' or colorKey == 'Rl': description += " ('L' alt)"
					elif ext == '.rat' or colorKey == 'Rr': description += " ('R' alt)"
			elif filenameOnly in miscNameLookup:
				description = miscNameLookup[ filenameOnly ]

			# Modify file description based on the file's region.
			if ext == '.usd' and not entryName.startswith('PlCa'): description += ' (English)'

		else:
			# Set the file description, then add the file to its respective folder (creating it if it doesn't already exist).
			if parent.split('/')[-1] == 'audio' and validOffset( filenameOnly ): # These are 20XX's added custom tracks, e.g. 01.hps, 02.hps, etc.
				if not Gui.isoFileTree.exists('hextracks'): Gui.isoFileTree.insert(parent, 'end', iid='hextracks', text=' Hex Tracks', values=('\t- Extra 20XX Custom Tracks -', 'folder', 'notNative', '', isoPath+'/hextracks', source, ''), image=Gui.imageBank('musicIcon') )
				parent = 'hextracks'
			elif ( entryName.endswith( '.hps' ) or entryName.endswith( '.ssm' ) or entryName.endswith( '.sem' ) ) and filenameOnly in audioNameLookup: 
				description = audioNameLookup[ filenameOnly ]
			elif entryName.startswith( 'Ef' ): # Character Effect files.
				if not Gui.isoFileTree.exists( 'ef' ): Gui.isoFileTree.insert(parent, 'end', iid='ef', text=' Ef__Data.dat', values=('\t- Character Graphical Effects -', 'folder', 'notNative', '', isoPath+'/Ef', source, ''), image=Gui.imageBank('folderIcon') )
				parent = 'ef'
				if entryName == 'EfFxData.dat': description = 'Fox & Falco'
				else: description = charNameLookup.get( entryName[2:4], '' )
			elif entryName.startswith( 'GmRegend' ): # Congratulations Screens.
				if not Gui.isoFileTree.exists('gmregend'): Gui.isoFileTree.insert(parent, 'end', iid='gmregend', text=' GmRegend__.thp', values=("\t- 'Congratulation' Screens (1P) -", 'folder', 'notNative', '', isoPath+'/GmRegend', source, ''), image=Gui.imageBank('folderIcon') )
				parent = 'gmregend'
			elif entryName.startswith( 'GmRstM' ): # Results Screen Animations
				if not Gui.isoFileTree.exists('gmrstm'): Gui.isoFileTree.insert(parent, 'end', iid='gmrstm', text=' GmRstM__.dat', values=('\t- Results Screen Animations -', 'folder', 'notNative', '', isoPath+'/GmRstM', source, ''), image=Gui.imageBank('folderIcon') )
				parent = 'gmrstm'
				description = charNameLookup.get( entryName[6:8], '' )
			elif entryName.startswith( 'Gr' ): # Stage file.

				# Create a folder for stage files (if not already created)
				if not Gui.isoFileTree.exists( 'gr' ): 
					Gui.isoFileTree.insert(parent, 'end', iid='gr', text=' Gr__.dat', values=('\t- Stage Files -', 'folder', 'notNative', '', isoPath+'/Gr', source, ''), image=Gui.imageBank('stageIcon') )
				parent = 'gr'

				if entryName[2] == 'T' and ( ext == '.dat' or entryName == 'GrTLg.0at' ): # This is a Target Test stage. (special case for Luigi's, since his ends in 0at)
					# Create a folder for target test stage files (if not already created)
					if not Gui.isoFileTree.exists( 't' ): 
						Gui.isoFileTree.insert( parent, 'end', iid='t', text=' GrT__.dat', values=('Target Test Stages', 'folder', 'notNative', '', isoPath+'/T', source, ''), image=Gui.imageBank('folderIcon') )
					parent = 't'

				elif entryName[2:5] in onePlayerStages: # For 1-Player modes,like 'Adventure'
					if not Gui.isoFileTree.exists( '1p' ): 
						Gui.isoFileTree.insert( parent, 'end', iid='1p', text='Gr___.___', values=('1P-Mode Stages', 'folder', 'notNative', '', isoPath+'/1P', source, ''), image=Gui.imageBank('folderIcon') )
					parent = '1p'

				elif globalDiscDetails['is20XX']: 
					# Modern versions of 20XX (4.06+) have multiple variations of each neutral stage, the 'Random Neutrals' (e.g. GrSt.0at - GrSt.eat)
					longName = None
					if entryName.startswith( 'GrP' ) and entryName[3] in hexdigits: 
						shortName = 'GrP'
						longName = 'Pokemon Stadium'
					elif entryName[-3] in hexdigits:
						for shortName in ( 'GrNBa', 'GrNLa', 'GrSt', 'GrIz', 'GrOp' ):
							if entryName.startswith( shortName ): 
								longName = stageNameLookup.get( entryName[2:5], None ) # Vanilla file name lookups
								break

					if longName:
						iid = shortName.lower()

						if not Gui.isoFileTree.exists( iid ):
							if shortName == 'GrP':
								folderName = ' {}_.usd'.format( shortName )
							else: folderName = ' {}._at'.format( shortName )
							fullIsoPath = isoPath + '/' + shortName
							Gui.isoFileTree.insert( 'gr', 'end', iid=iid, text=folderName, values=(longName, 'folder', 'notNative', '', fullIsoPath, source, ''), image=Gui.imageBank('folderIcon') )
						parent = iid

			elif ext == '.mth': # a video file.
				if entryName.startswith( 'MvEnd' ): # 1-P Ending Movie.
					if not Gui.isoFileTree.exists('mvend'): Gui.isoFileTree.insert(parent, 'end', iid='mvend', text=' MvEnd__.dat', values=('\t- 1P Mode Ending Movies -', 'folder', 'notNative', '', isoPath+'/MvEnd', source, ''), image=Gui.imageBank('folderIcon') )
					parent = 'mvend'
				elif filenameOnly in movieNameLookup: description = movieNameLookup[filenameOnly]

			elif entryName.startswith('Pl') and entryName != 'PlCo.dat': # Character file.
				if not Gui.isoFileTree.exists('pl'): Gui.isoFileTree.insert(parent, 'end', iid='pl', text=' Pl__.dat', values=('\t- Character Files -', 'folder', 'notNative', '', isoPath+'/Pl', source, ''), image=Gui.imageBank('charIcon') )
				colorKey = entryName[4:6]
				character = charNameLookup.get( entryName[2:4], 'Unknown Character' )

				# Create a folder for the character (and the copy ability files if this is Kirby) if one does not already exist.
				folder = 'pl' + character.replace(' ', '').replace('[','(').replace(']',')') # Spaces or brackets can't be used in the iid.
				if not Gui.isoFileTree.exists( folder ): 
					Gui.isoFileTree.insert( 'pl', 'end', iid=folder, text=' ' + character, values=('', 'folder', 'notNative', '', isoPath+'/'+folder, source, ''), image=Gui.imageBank('folderIcon') )
				parent = folder

				# Prepare the file's description.
				if character.endswith('s'): description = character + "' "
				else: description = character + "'s "

				if colorKey == '.d': description += 'NTSC data & shared textures' # e.g. "PlCa.dat"
				elif colorKey == '.p': description += 'PAL data & shared textures'
				elif colorKey == '.s': description += 'SDR data & shared textures'
				elif colorKey == 'AJ': description += 'animation data'
				elif colorKey == 'Cp': 
					charName = charNameLookup.get( entryName[6:8], '' )
					if charName:
						if ']' in charName: charName = charName.split(']')[1]
						description += 'copy power (' + charName + ')'
					else:
						description += 'copy power'
				elif colorKey == 'DV': description += 'idle animation data'
				elif colorKey in charColorLookup: description += charColorLookup.get( colorKey, 'Unknown color' ) + ' costume'

				if globalDiscDetails['is20XX']:
					if ext == '.lat' or colorKey == 'Rl': description += " ('L' alt)"
					elif ext == '.rat' or colorKey == 'Rr': description += " ('R' alt)"

			elif entryName.startswith('Ty'): # Trophy file
				if not Gui.isoFileTree.exists('ty'): Gui.isoFileTree.insert( parent, 'end', iid='ty', text=' Ty__.dat', values=('\t- Trophies -', 'folder', 'notNative', '', isoPath+'/Ty', source, ''), image=Gui.imageBank('folderIcon') )
				parent = 'ty'

			elif filenameOnly in miscNameLookup: description = miscNameLookup[ filenameOnly ]

			# Modify file description based on the file's region.
			if ext == '.usd' and not entryName.startswith('PlCa'): description += ' (English)'

		# Add a file to the treeview (all files (not folders) besides system files should be added with the line below).
		fullPath = isoPath + '/' + entryName
		Gui.isoFileTree.insert( parent, 'end', iid=fullPath.lower(), text=' ' + entryName, values=(description, 'file', uHex(entryOffset), entryLength, fullPath, source, data) )


def scanDisc( updateStatus=True, preserveTreeState=False, updateDetailsTab=True, switchTab=True, updatedFiles=None ):
	globalDiscDetails['rebuildRequired'] = False

	if preserveTreeState:
		# Get the iids of all open folders
		openIids = []
		def getOpenFolders( openIids, parentIid='' ):
			for iid in Gui.isoFileTree.get_children( parentIid ):
				if Gui.isoFileTree.item( iid, 'values' )[1] == 'folder':
					if Gui.isoFileTree.item( iid, 'open' ): openIids.append( iid )

					openIids = getOpenFolders( openIids, iid )
			return openIids
		openFolders = getOpenFolders( openIids )

		# Remember the selection, focus, and current scroll position of the treeview
		originalGameId = Gui.isoFileTree.get_children()[0] # The gameId might have been modified. If so, the file/folder selections and focus iids below will need to be updated before restoration.
		originalTreeSelection = Gui.isoFileTree.selection()
		originalTreeFocus = Gui.isoFileTree.focus()
		originalTreeScrollPosition = Gui.isoFileScroller.get()[0] # .get() returns e.g. (0.49505277044854884, 0.6767810026385225)

	if switchTab:
		currentlySelectedTab = Gui.root.nametowidget( Gui.mainTabFrame.select() )
		if currentlySelectedTab != Gui.discTab and currentlySelectedTab != Gui.discDetailsTab: 
			Gui.mainTabFrame.select( Gui.discTab ) # Switch to the Disc File Tree tab

	initializeDiscFileTree( not preserveTreeState )

	# Get basic info on the disc
	gameId, dolOffset, fstOffset, dolSize, fstSize, fstData, apploaderSize = getDiscSystemFileInfo( globalDiscDetails['isoFilePath'] )

	# Assemble a filesystem from the FST.
	numberOfEntries, entries, strings = readFST( fstData ) # Returns an int and two lists

	# Add the root folder
	isoPath = gameId
	parent = isoPath.lower()
	source = 'iso'
																				# The 'native' value below indicates that this is a folder native to the FST
	Gui.isoFileTree.insert( '', 'end', iid=isoPath.lower(), text=' ' + gameId + '  (root)', open=True, values=('', 'folder', 'native', '', isoPath, source, ''), image=Gui.imageBank('meleeIcon') )
	
	# Add the system files
	Gui.isoFileTree.insert( isoPath.lower(), 'end', iid=parent + '/sys', text=' System files', values=('', 'folder', 'notNative', '', isoPath, source, ''), image=Gui.imageBank('folderIcon') )
	Gui.isoFileTree.insert( parent + '/sys', 'end', iid=parent + '/boot.bin', text=' Boot.bin', values=('Disc Header (.hdr), Part 1', 'file', '0', 0x440, isoPath+'/Boot.bin', source, '') )
	Gui.isoFileTree.insert( parent + '/sys', 'end', iid=parent + '/bi2.bin', text=' Bi2.bin', values=('Disc Header (.hdr), Part 2', 'file', '0x440', 0x2000, isoPath+'/Bi2.bin', source, '') )
	Gui.isoFileTree.insert( parent + '/sys', 'end', iid=parent + '/apploader.ldr', text=' AppLoader.ldr', values=('Executable bootloader', 'file', '0x2440', apploaderSize, isoPath+'/Apploader.ldr', source, '') )
	Gui.isoFileTree.insert( parent + '/sys', 'end', iid=parent + '/start.dol', text=' Start.dol', values=('Main game executable', 'file', uHex(dolOffset), dolSize, isoPath+'/Start.dol', source, '') )
	Gui.isoFileTree.insert( parent + '/sys', 'end', iid=parent + '/game.toc', text=' Game.toc', values=("The disc's file system table (FST)", 'file', uHex(fstOffset), fstSize, isoPath+'/Game.toc', source, '') )

	# Check whether the disc is SSBM and 20XX (and if so, gets their versions)
	checkMeleeVersion()
	check20xxVersion( entries, strings )

	# For each entry (subdirectory/file) in the ISO.
	i = 1
	dirEndIndexes = [numberOfEntries]
	totalFiles = 5 # Starts at 5 due to the system files above.

	for entry in entries[1:]: # Skips the first (root) entry.
		if programClosing: return
		else:
			entryOffset = int( entry[8:16], 16 )
			entryLength = int( entry[16:24], 16 )
			entryName = strings[i - 1]
			#print 'entry', str(i) + ':', entry[:8], entry[8:16], entry[16:24], '\t\t', hex(entryOffset), hex(entryLength), entryName

			# If the last directory has been exhausted, remove the last directory from the current path.
			while i == dirEndIndexes[-1]: # 'while' is used instead of 'if' in case multiple directories are ending (being backed out of) at once
				isoPath = '/'.join( isoPath.split('/')[:-1] )
				dirEndIndexes.pop()

			parent = isoPath.lower() # Differentiated here because parent may be changed for "convenience" folders (those not native to the ISO)

			# Differentiate between new subdirectory or file
			if entry[1] == '1':
				isoPath += '/' + entryName
				dirEndIndexes.append( entryLength )
			else:
				totalFiles = totalFiles + 1

			addItemToDiscFileTree( int(entry[1]), isoPath, entryName, entryOffset, entryLength, parent, source, '' )

			# The following code is ad hoc code used occasionally for some research/testing purposes

			# iid = (isoPath+'/'+entryName).lower()
			# fileData = getFileDataFromDiscTreeAsBytes( iid=iid )
			# if not fileData:
			# 	print 'skipping disc item', entryName, '(no file data)'

			# elif entryName.startswith( 'Gr' ):

			# 	datFile = hsdFiles.datFileObj( source='disc' )
			# 	datFile.load( iid, fileData=fileData, fileName=entryName )

			# 	print entryName, humansize(datFile.headerInfo['filesize']), uHex( datFile.headerInfo['filesize'] )

			# 	for structOffset, string in datFile.rootNodes:
			# 		if string == 'coll_data':
			# 			#mapHeadStruct = datFile.getStruct( structOffset )
			# 			print '\nFound coll_data for', entryName + '.   length:', uHex(datFile.getStructLength( structOffset ))
			# 			#print 'offset:', uHex(0x20+mapHeadStruct.offset), '  length:', uHex(mapHeadStruct.length)
			# 			#print mapHeadStruct.data
			# 			# if mapHeadStruct.values[8] != 0:
			# 			# 	print 'Uses Array_5', mapHeadStruct.values[9]
			# 			break

			# end of test code

		i += 1

	# Now that the CSS has been loaded in the treeview, we can use it to update the stage names
	if globalDiscDetails['isMelee']: setStageDescriptions()

	# Enable the GUI's buttons and update other labels
	for widget in Gui.isoOpsPanelButtons.winfo_children():
		widget.config( state='normal' )
	Gui.isoFileCountText.set( "{:,}".format(totalFiles) )
	if updateStatus: updateProgramStatus( 'Disc Scan Complete' )

	def updateIids( iidList ):
		updatedIidList = []
		for iid in iidList:
			if '/' in iid: updatedIidList.append( gameId + '/' + '/'.join(iid.split('/')[1:]) )
			else: updatedIidList.append( iid )
		return tuple( updatedIidList )

	# Recreate the prior state of the treeview
	gameId = gameId.lower()
	if preserveTreeState:
		# Update the file/folder selections and focus iids with the new gameId if it has changed.
		if originalGameId != gameId:
			openFolders = updateIids( openFolders )
			originalTreeSelection = updateIids( originalTreeSelection )
			if '/' in originalTreeFocus: originalTreeFocus = gameId + '/' + '/'.join(originalTreeFocus.split('/')[1:])

		# Open all folders that were previously open.
		for folder in openFolders:
			if Gui.isoFileTree.exists( folder ): Gui.isoFileTree.item( folder, open=True )

		# Set the current selections and scroll position back to what it was.
		Gui.isoFileTree.selection_set( originalTreeSelection )
		Gui.isoFileTree.focus( originalTreeFocus )
		Gui.isoFileTree.yview_moveto( originalTreeScrollPosition )

	# Highlight recently updated files in green
	if updatedFiles:
		# Update the file iids with the new gameId if it has changed.
		if originalGameId != gameId: updatedFiles = updateIids( updatedFiles )

		# Add save highlighting tags to the given items
		for iid in updatedFiles:
			if Gui.isoFileTree.exists( iid ):
				# Add a tag to highlight this item
				Gui.isoFileTree.item( iid, tags='changesSaved' )

				# Add tags to highlight the parent (folder) items
				parent = Gui.isoFileTree.parent( iid )
				while parent != gameId:
					Gui.isoFileTree.item( parent, tags='changesSaved' )
					parent = Gui.isoFileTree.parent( parent )

	# Update the treeview's header text and its function call for the next (reversed) sort.
	Gui.isoFileTree.heading( '#0', text='File     (Sorted by FST)' )
	Gui.isoFileTree.heading( '#0', command=lambda: treeview_sort_column(Gui.isoFileTree, 'file', False) )

	if updateDetailsTab: populateDiscDetails()


def promptToOpenRoot():
	# Prompt for a directory to retrieve files from.
	rootPath = tkFileDialog.askdirectory(
		title='Choose a root directory (folder of disc files).', 
		initialdir=settings.get( 'General Settings', 'defaultSearchDirectory' ),
		#parent=Gui.root,
		mustexist=True )

	if rootPath and isRootFolder( rootPath )[0]: # A path was chosen above and it's a disc root directory (isRoot includes error messages if it's not)
		rememberFile( rootPath )
		globalDiscDetails['isoFilePath'] = rootPath
		scanRoot()


def scanRoot( switchTab=True, updateDetailsTab=True ):
	rootPath = os.path.normpath( globalDiscDetails['isoFilePath'] ).replace( '\\', '/' ) # Let's not deal with escape characters in our paths, shall we?

	# Make sure this is a root folder, and get the main system files
	validRootFolder, sysFolder, gcrSystemFiles = isRootFolder( rootPath )
	if not validRootFolder: return

	# Initial error checking complete. Populate the file tree
	if switchTab:
		currentlySelectedTab = Gui.root.nametowidget( Gui.mainTabFrame.select() )
		if currentlySelectedTab != Gui.discTab and currentlySelectedTab != Gui.discDetailsTab: 
			Gui.mainTabFrame.select( Gui.discTab ) # Switch to the Disc File Tree tab

	initializeDiscFileTree( True )

	# Get basic info on the disc
	if gcrSystemFiles: bootFilePath = rootPath + '/' + sysFolder + '/iso.hdr'
	else: bootFilePath = rootPath + '/' + sysFolder + '/boot.bin'
	apploaderFilePath = rootPath + '/' + sysFolder + '/apploader.ldr'
	gameId, dolOffset, fstOffset, dolSize, _, fstData, apploaderSize = getDiscSystemFileInfo( bootFilePath, apploaderPath=apploaderFilePath )

	# Add the root folder
	isoPath = gameId
	parent = isoPath.lower()
	source = 'path'																							# The 'native' value below indicates that this is a folder native to the filesystem
	Gui.isoFileTree.insert( '', 'end', iid=parent, text=' ' + gameId + '  (root)', open=True, values=('', 'folder', 'native', '', isoPath, source, ''), image=Gui.imageBank('meleeIcon') )
	
	# Add the system files
	Gui.isoFileTree.insert( isoPath.lower(), 'end', iid=parent + '/sys', text=' System files', values=('', 'folder', 'notNative', '', isoPath, source, ''), image=Gui.imageBank('folderIcon') )
	if not gcrSystemFiles:
		Gui.isoFileTree.insert( parent + '/sys', 'end', iid=parent + '/boot.bin', text=' Boot.bin', values=('Disc Header (.hdr), Part 1', 'file', '0', 0x440, isoPath+'/Boot.bin', source, rootPath + '/' + sysFolder + '/boot.bin') )
		Gui.isoFileTree.insert( parent + '/sys', 'end', iid=parent + '/bi2.bin', text=' Bi2.bin', values=('Disc Header (.hdr), Part 2', 'file', '0x440', 0x2000, isoPath+'/Bi2.bin', source, rootPath + '/' + sysFolder + '/bi2.bin') )
		totalFiles = 4
		headerFilePath = rootPath + '/' + sysFolder + '/boot.bin'
	else:
		Gui.isoFileTree.insert( parent + '/sys', 'end', iid=parent + '/iso.hdr', text=' ISO.hdr', values=('Disc Header', 'file', '0', 0x2440, isoPath+'/ISO.hdr', source, rootPath + '/' + sysFolder + '/iso.hdr') )
		totalFiles = 3
		headerFilePath = rootPath + '/' + sysFolder + '/iso.hdr'
	Gui.isoFileTree.insert( parent + '/sys', 'end', iid=parent + '/apploader.ldr', text=' AppLoader.ldr', values=('Executable bootloader', 'file', '0x2440', apploaderSize, isoPath+'/Apploader.ldr', source, apploaderFilePath) )
	Gui.isoFileTree.insert( parent + '/sys', 'end', iid=parent + '/start.dol', text=' Start.dol', values=('Main game executable', 'file', uHex(dolOffset), dolSize, isoPath+'/Start.dol', source, rootPath + '/' + sysFolder + '/start.dol') )

	# Get the offset for the FST
	with open( headerFilePath, 'rb') as bootBinFile:
		bootBinFile.seek( 0x424 )
		fstOffset = toInt( bootBinFile.read( 4 ) )

	# Check whether the disc is SSBM and 20XX (and if so, gets their versions)
	checkMeleeVersion()
	check20xxVersion()

	entryOffset = 0 # This will be adjusted for each entry once the size of the FST is known.
	filenamesTooLong = []

	def loadItemsInDirectory( directory, totalFiles, entryOffset ):
		for entryName in os.listdir( directory ):
			if programClosing: return '', 0, 0, ''
			elif entryName == sysFolder: continue
			elif len( os.path.splitext(entryName)[0] ) >= 30: # This is the max character length for file names
				filenamesTooLong.append( directory + '/' + entryName )
				continue

			fullPath = directory + '/' + entryName

			# Get the relative difference between this these paths
			isoPath = gameId + directory.replace( rootPath, '' )

			parent = isoPath.lower()

			# Differentiate between new subdirectory or file
			if os.path.isdir( fullPath ):
				isoPath += '/' + entryName
				addItemToDiscFileTree( True, isoPath, entryName, entryOffset, '', parent, source, fullPath )
				totalFiles, entryOffset = loadItemsInDirectory( fullPath, totalFiles, entryOffset )
			else:
				# Consider alignment adjustment for the last file and padding, to be added to the offset for this file.
				alignmentAdjustment = roundTo32( entryOffset, base=4 ) - entryOffset # i.e. how many bytes away from being aligned.
				entryOffset += alignmentAdjustment
				entryLength = int( os.path.getsize(fullPath) )

				addItemToDiscFileTree( False, isoPath, entryName, entryOffset, entryLength, parent, source, fullPath )

				# Determine the offset for the next file (excluding padding).
				entryOffset += entryLength
				totalFiles += 1

		return totalFiles, entryOffset

	totalFiles, entryOffset = loadItemsInDirectory( rootPath, totalFiles, entryOffset ) # entryOffset will be the total space used by all non-system files, including alignment adjustments.

	# Now that the CSS has been loaded in the treeview, we can update the stage names using it
	if globalDiscDetails['isMelee']: setStageDescriptions()

	# Generate a new FST based on the files shown in the GUI, and determine how much space it will use
	newFstData = generateFST()
	fstFileSize = len( newFstData )/2
	alignmentAdjustment = roundTo32( fstFileSize, base=4 ) - fstFileSize # i.e. how many bytes away from being aligned.
	spaceForHeaderAndSystemFiles = fstOffset + fstFileSize + alignmentAdjustment

	# Add the FST to the file tree
	addItemToDiscFileTree( False, gameId, 'Game.toc', fstOffset, fstFileSize, gameId.lower() + '/sys', 'ram', newFstData )

	# Determine how much padding to allocate between files.
	if not gcrSystemFiles: totalNonSystemFiles = totalFiles - 4
	else: totalNonSystemFiles = totalFiles - 3
	interFilePaddingLength = getInterFilePaddingLength( totalNonSystemFiles, spaceForHeaderAndSystemFiles + entryOffset )

	# Now that the size (length) of inter-file padding and all system files are known, update the offsets of all items
	def updateEntryOffsets( parentIid, paddingDisplacement ): # Collect a list of all files in the file tree, and add up their total space used.
		if parentIid == gameId.lower() + '/sys': return 0

		for iid in Gui.isoFileTree.get_children( parentIid ):

			iidValues = Gui.isoFileTree.item( iid, 'values' )
			if iidValues[1] == 'file':
				paddingDisplacement += interFilePaddingLength # This is cumulative, for each file
				try: newOffset = int( iidValues[2], 16 ) + spaceForHeaderAndSystemFiles + paddingDisplacement
				except: newOffset = 'n/a'
				Gui.isoFileTree.item( iid, values=(iidValues[0], iidValues[1], uHex(newOffset), iidValues[3], iidValues[4], iidValues[5], iidValues[6]) )
			else: # This is a folder
				paddingDisplacement = updateEntryOffsets( iid, paddingDisplacement )

		return paddingDisplacement
	paddingDisplacement = updateEntryOffsets( '', 0 )

	globalDiscDetails['rebuildRequired'] = True

	# Update the file count display (on the disc details tab) and program status
	Gui.isoFileCountText.set( "{:,}".format(totalFiles) )
	updateProgramStatus( 'Root Scan Complete' )

	# Update the treeview's header text and its function call for the next (reversed) sort.
	Gui.isoFileTree.heading( '#0', text='File     (Sorted by FST)' )
	Gui.isoFileTree.heading( '#0', command=lambda: treeview_sort_column(Gui.isoFileTree, 'file', False) )

	if filenamesTooLong:
		msg( 'These files were excluded, because their file name is longer than 29 characters:\n\n' + '\n'.join( filenamesTooLong ) )

	if updateDetailsTab:
		predictedFinalDiscSize = spaceForHeaderAndSystemFiles + entryOffset + paddingDisplacement
		populateDiscDetails( discSize=predictedFinalDiscSize )


def readFST( fstData ):

	""" Parses a GC disc's FST/TOC (File System Table/Table of Contents), and builds a list of 
		entries (files and folders), along with their corresponding names. Input is a hex string, because this is an old function. :/ """

	numberOfEntries = int( fstData[16:24], 16 ) # An "entry" may be a file or directory. This value is taken from [0x8:0xC] of the root entry.
	lenOfEntriesSection = numberOfEntries * 0xC * 2 # Multiplied by 2 to count by nibbles in the string, rather than bytes.
	fst = fstData[:lenOfEntriesSection]
	entries = [ fst[i:i+0x18] for i in xrange(0, len(fst), 0x18) ] # Splits the FST into groups of 0xC bytes (0x18 nibbles), i.e. one entry each.
	strings = fstData[lenOfEntriesSection:].decode('hex').split('\x00')

	return ( numberOfEntries, entries, strings )


def generateFST(): # Generates and returns a new File System Table (Game.toc).
	rootIid = Gui.isoFileTree.get_children()
	gameId = globalDiscDetails['gameId'].lower()

	def childItemCount( folder, gameId ): # Recursively get the count of all items (both files and folders) in the given folder.
		itemCount = 0
		for iid in Gui.isoFileTree.get_children( folder ):
			if iid == gameId + '/sys': continue # Skip the system files

			iidValues = Gui.isoFileTree.item( iid, 'values' )
			if iidValues[1] == 'file': itemCount += 1
			else:
				# Search the inner folder, and add the totals of the children within to the current count.
				itemCount += childItemCount( iid, gameId )
				if iidValues[2] == 'native': itemCount += 1 # Counts folders only if they're originally from the ISO.
		return itemCount

	gameItemCount = childItemCount( rootIid, gameId ) + 1

	entries = [ '0100000000000000' + "{0:0{1}X}".format( gameItemCount, 8 ) ] # Starts off with the root entry included.
	stringTable = ['']
	stringTableCharLen = 0
	entryIndex = 1

	def buildEntries( parentIid, stringTableCharLen, entryIndex, gameId ):
		for iid in Gui.isoFileTree.get_children( parentIid ):
			if iid == gameId + '/sys': continue

			_, entity, isoOffset, fileSize, isoPath, _, _ = Gui.isoFileTree.item( iid, 'values' ) # description, entity, isoOffset, fileSize, isoPath, source, data

			# Get the directory flag
			if entity == 'folder':
				directoryFlag = '01'
				hierarchicalOffset = "{0:0{1}X}".format( len( iid.split('/') ) - 2, 8 ) # This is actually entryIndexOfParent #tofix
				length = "{0:0{1}X}".format( entryIndex + childItemCount( iid, gameId ) + 1, 8 ) # This will be the index of the next file that's not in this directory.
			else:
				directoryFlag = '00'
				hierarchicalOffset = "{0:0{1}X}".format( int(isoOffset, 16), 8 ) # Formats the number in hex, and pads it with zeros to 8 characters.
				length = "{0:0{1}X}".format( int(fileSize), 8 )

			if entity == 'file' or isoOffset == 'native': # Add this entry if it's a file, or if it's a folder that was originally in the ISO.
				# Get the offset for the name in the string table, and the name to add to the string table.
				stringTableOffset = "{0:0{1}X}".format( stringTableCharLen, 6 )
				name = ( isoPath.split('/')[-1] + '\x00').encode('hex')

				# Add the current entry to the entries list and string section.
				entries.append( directoryFlag + stringTableOffset + hierarchicalOffset + length )
				stringTable.append( name )
				stringTableCharLen += len( name ) / 2 # Need to count by bytes, not nibbles.
				entryIndex += 1

			# If this was a folder, build entries for the children it contains.
			if directoryFlag == '01': stringTableCharLen, entryIndex = buildEntries( iid, stringTableCharLen, entryIndex, gameId )

		return stringTableCharLen, entryIndex

	# Collect the info needed to make a FST entry of the current item.
	buildEntries( rootIid, stringTableCharLen, entryIndex, gameId )

	return ''.join( entries ) + ''.join( stringTable )


def getFileTreeFiles( parentIid='' ): # Collect a list of all files in the file tree, and add up their total space used.
	files = []
	totalFileSize = 0
	for iid in Gui.isoFileTree.get_children( parentIid ):
		iidValues = Gui.isoFileTree.item( iid, 'values' )
		if iidValues[1] == 'file':
			files.append( iidValues )
			totalFileSize += int( iidValues[3] )
		else: # This is a folder
			filesList, fileSizes = getFileTreeFiles( iid )
			files.extend( filesList )
			totalFileSize += fileSizes
	return files, totalFileSize


																				#===================================#
																				# ~ ~ Secondary Disc Operations ~ ~ #
																				#===================================#

def discDetected( throwWarnings=True ):
	if not globalDiscDetails['isoFilePath']:
		if throwWarnings: msg( 'No disc image has been loaded.' )
		return False
	elif not os.path.exists( globalDiscDetails['isoFilePath'] ):
		if throwWarnings:
			updateProgramStatus( 'Disc Not Found' )
			msg( "Unable to find the disc image. Be sure that the file path is "
				 "correct and that it hasn't been moved, renamed, or deleted.", 'Disc Not Found' )
		return False
	else: return True


def pathIsFromDisc( entryField ): # Checks if the DAT in the DAT Texture Tree tab was loaded from a disc image or is a standalone file.
	fileDest = entryField.get().replace( '"', '' )
	return ( ':' not in fileDest and Gui.isoFileTree.exists(fileDest.lower()) )


def checkMeleeVersion(): # Checks if the loaded disc is a copy of SSBM
	isMelee = ''

	if os.path.exists( globalDiscDetails['isoFilePath'] ):
		gameId = globalDiscDetails['gameId'].lower()
		dolData = getFileDataFromDiscTreeAsBytes( gameId + '/start.dol' )

		if not dolData:
			print 'The DOL file appears to be absent from the Disc File Tree!'
			globalDiscDetails['isMelee'] = ''
			return

		# Check the DOL for a string of "Super Smash Bros. Melee"
		ssbmStringBytes = bytearray()
		ssbmStringBytes.extend( "Super Smash Bros. Melee" )
		if dolData[0x3B78FB:0x3B7912] == ssbmStringBytes: isMelee = '02'   # i.e. version 1.02 (most common; so checking for it first)
		elif dolData[0x3B6C1B:0x3B6C32] == ssbmStringBytes: isMelee = '01' # i.e. version 1.01
		elif dolData[0x3B5A3B:0x3B5A52] == ssbmStringBytes: isMelee = '00' # i.e. version 1.00
		elif dolData[0x3B75E3:0x3B75FA] == ssbmStringBytes: isMelee = 'pal' # i.e. PAL

	globalDiscDetails['isMelee'] = isMelee


def check20xxVersion( fstEntries=None, fstStrings=None ):

	""" The version returned may be 3.02, 3.02.01, 3.03, BETA 01, BETA 02, BETA 03, BETA 04, 4.05, or higher future versions following the x.xx format. 
		Sets globalDiscDetails['is20XX'] to an empty string if the disc does not appear to be a version of 20XXHP. """

	# Get the MnSlChr file (either from a root folder or disc file)
	cssData = None
	if fstEntries: # Dealing with a disc image file
		i = 0
		for entry in fstEntries[1:]: # Skips the first (root) entry.
			if entry[1] == '1': # Skip folders
				i += 1
				continue

			# Check if it's the CSS file
			if fstStrings[i].startswith( 'MnSlChr.' ):
				entryOffset = int( entry[8:16], 16 )
				entryLength = int( entry[16:24], 16 )

				# CSS data located. Retrieve it
				with open( globalDiscDetails['isoFilePath'], 'rb') as isoBinary:
					isoBinary.seek( entryOffset )
					cssData = bytearray( isoBinary.read(entryLength) )
				break

			i += 1

	else: # Dealing with a root folder, need to grab the file from the OS filesystem
		# Look for the CSS file name
		for item in os.listdir( globalDiscDetails['isoFilePath'] ):
			if item.startswith( 'MnSlChr.' ):
				cssFilePath = globalDiscDetails['isoFilePath'] + '\\' + item

				with open( cssFilePath, 'rb') as cssFile:
					cssData = bytearray( cssFile.read() )

				break

	# Make sure data was found
	if not cssData: # CSS file not found
		globalDiscDetails['is20XX'] = ''
		return

	# Check the file length of MnSlChr (the CSS); if it's abnormally larger than vanilla, it's 20XX post-v3.02
	fileSize = toInt( cssData[:4] )
	if fileSize > 0x3a2849: # Comparing against the vanilla file size.
		# Isolate a region in the file that may contain the version string.
		versionStringRange = cssData[0x3a4cd0:0x3a4d00]

		# Create a bytearray representing "VERSION " to search for in the region defined above
		versionBytes = bytearray.fromhex( '56455253494f4e20' ) # the hex for "VERSION "
		versionStringPosition = findBytes( versionStringRange, versionBytes )

		if versionStringPosition != -1: # The string was found
			versionValue = versionStringRange[versionStringPosition+8:].split(b'\x00')[0].decode( 'ascii' )

			if versionValue == 'BETA': # Determine the specific beta version; 01, 02, or 03 (BETA 04 identified separately)
				firstDifferentByte = cssData[0x3a47b5]

				if firstDifferentByte == 249 and hexlify( cssData[0x3b905e:0x3b9062] ) == '434f4445': # Hex for the string "CODE"
					versionValue += ' 01'
				elif firstDifferentByte == 249: versionValue += ' 02'
				elif firstDifferentByte == 250: versionValue += ' 03'
				else: versionValue = ''

			elif versionValue == 'BETA04': versionValue = 'BETA 04'
				
			globalDiscDetails['is20XX'] = versionValue

		elif fileSize == 0x3a5301: globalDiscDetails['is20XX'] = '3.03'
		elif fileSize == 0x3a3bcd: globalDiscDetails['is20XX'] = '3.02.01' # Source: https://smashboards.com/threads/the-20xx-melee-training-hack-pack-v4-05-update-3-17-16.351221/page-68#post-18090881
		else: globalDiscDetails['is20XX'] = ''

	elif cssData[0x310f9] == 0x33: # In vanilla Melee, this value is '0x48'
		globalDiscDetails['is20XX'] = '3.02'

	else: globalDiscDetails['is20XX'] = ''


def isRootFolder( folderPath, showError=True ):

	""" Checks a given file/folder path to see if it's a disc root folder (i.e. a folder of files needed to build a disc).
		Returns 3 values: Bool on whether the folder is a disc root folder, a string for the system files folder, and 
		a Bool on whether it's in the form output/used by GCRebuilder. """

	if not os.path.isdir( folderPath ): return False, '', False

	# Confirm existance of the system files folder (and confirm its name)
	for sysFolder in [ 'System files', 'SystemFiles', '&&systemdata' ]:
		if os.path.exists( folderPath + '/' + sysFolder ): break # sysFolder will now be the name of the system files folder
	else: # loop above didn't break
		if showError: msg( 'No system files were found!\n\nThey should be in a folder called "System files" (or "&&systemdata", if the disc was extracted using GC Rebuilder).' )
		return False, '', False

	# Check that all system files are present and accounted for before continuing.
	missingSysFiles = []
	gcrSystemFiles = False # The 'format' of the extracted files; i.e. whether the root was exported via DTW or GCR
	for systemFile in [ 'boot.bin', 'bi2.bin', 'apploader.ldr', 'start.dol' ]:
		fullPath = folderPath + '/' + sysFolder + '/' + systemFile
		if not os.path.exists( fullPath ):
			if systemFile.endswith( '.bin' ) and os.path.exists( folderPath + '/' + sysFolder + '/iso.hdr' ): # It's ok if boot.bin & bi2.bin don't exist if iso.hdr is available in their place
				gcrSystemFiles = True
				continue

			missingSysFiles.append( systemFile )
	if missingSysFiles:
		if showError: msg( 'Warning! The following system files could not be found, and are necessary for building the disc:\n\n' + '\n'.join(missingSysFiles) )
		return False, '', False

	return True, sysFolder, gcrSystemFiles


def replaceFileInDisc( iid, newExternalFilePath, iidValues, orig20xxVersion, origMainBuildNumber ):
	_, entity, isoOffset, fileSize, isoPath, _, _ = iidValues # description, entity, isoOffset, fileSize, isoPath, source, data

	# Get the strings table of the original file
	originalFileData = getFileDataFromDiscTreeAsBytes( iid=iid )
	originalStringDict = parseStringTable( originalFileData )[2]

	# Get the strings table of the new file
	with open( newExternalFilePath, 'rb' ) as newFile:
		newFileData = newFile.read()
	newStringDict = parseStringTable( newFileData )[2]

	# Get just the strings, and sort them so they're in the same order (we only care that the same ones exist)
	origFileStrings = sorted( originalStringDict.values() )
	newFileStrings = sorted( newStringDict.values() )

	# Check that this is an appropriate replacement file by comparing the strings of the two files
	if not origFileStrings == newFileStrings:
		if not tkMessageBox.askyesno( 'Warning! File Mismatch', """The file you're """ + 'importing, "' + os.path.basename(newExternalFilePath) + """", does't appear """
									  'to be a valid replacement for "' + os.path.basename(isoPath) + '".\n\nAre you sure you want to do this?' ): return False

	# If the file being imported is the CSS. Check if it's for the right game version
	elif 'MnSelectChrDataTable' in newFileStrings:

		if orig20xxVersion != '':
			cssfileSize = os.path.getsize( newExternalFilePath )
			proposed20xxVersion = globalDiscDetails['is20XX']

			if proposed20xxVersion:
				if 'BETA' in proposed20xxVersion: proposedMainBuildNumber = int( proposed20xxVersion[-1] )
				else: proposedMainBuildNumber = int( proposed20xxVersion[0] )
			else: proposedMainBuildNumber = 0

			if orig20xxVersion == '3.02': pass # Probably all CSS files will work for this, even the extended 3.02.01 or 4.0x+ files

			elif cssfileSize < 0x3A3BCD: # importing a vanilla CSS over a 20XX CSS
				if not tkMessageBox.askyesno( 'Warning! 20XX File Version Mismatch', """The CSS file you're """ + 'importing, "' + os.path.basename(newExternalFilePath) + """", is for a standard """
											'copy of Melee (or a very early version of 20XX), and will not natively work for post-v3.02 versions of 20XX. Alternatively, you can extract '
											"textures from this file and import them manually if you'd like.\n\nAre you really sure you want to continue with this import?" ): return False

			elif orig20xxVersion != proposed20xxVersion and origMainBuildNumber != proposedMainBuildNumber: # These are quite different versions
					if not tkMessageBox.askyesno( 'Warning! 20XX File Version Mismatch', """The CSS file you're """ + 'importing, "' + os.path.basename(newExternalFilePath) + """", was not """
											'designed for to be used with this version of 20XX and may not work. Alternatively, you can extract '
											"textures from this file and import them manually if you'd like.\n\nAre you sure you want to continue with this import?" ): return False

	# Import the file. The original fileSize value is intentionally preserved, for later comparison during the evaluation for saving.
	Gui.isoFileTree.item( iid, values=('Ready to be replaced...', entity, isoOffset, fileSize, isoPath, 'path', newExternalFilePath), tags='changed' )

	# If this is a character file and this is 20XX beyond version 3, generate new CSP trim colors for this costume (if the option is enabled)
	filename = os.path.basename( iid ) # Checking iid because newExternalFilePath might be named something completely different than the standard naming convention
	if generalBoolSettings['autoGenerateCSPTrimColors'].get() and candidateForTrimColorUpdate( filename, orig20xxVersion, origMainBuildNumber ):
		generateTrimColors( fileIid=iid, autonomousMode=True )

	return True


def candidateForTrimColorUpdate( filename, orig20xxVersion, origMainBuildNumber ):
	# Check if this is an appropriate version of 20XX HP
	if not orig20xxVersion or not ( origMainBuildNumber > 3 or 'BETA' in orig20xxVersion ):
		return False

	# Check that it's a character file (pl = Player)
	elif filename[:2] != 'pl':
		return False

	# Check that this is a Left-alt or Right-alt file (latter condition is for Falcon's red alts)
	elif filename[-4:] not in ( '.lat', '.rat' ) and filename[-6:] not in ( 'rl.usd', 'rr.usd' ):
		return False

	# Exclude Master Hand and Crazy Hand
	elif filename[2:4] in ( 'mh', 'ch' ):
		return False

	return True


def importSingleIsoFile(): # i.e. replace an existing file in the disc
	if not discDetected(): return

	iidSelectionsTuple = Gui.isoFileTree.selection() # Will be an empty string if nothing is selected, or a tuple of iids
	
	if not iidSelectionsTuple: msg( "Please select a file to replace." ) #\n\nIf you'd like to replace multiple files, "
									#"use the 'Import Multiple Files' option in the Disc Operations menu." )

	elif len( iidSelectionsTuple ) == 1:
		iidValues = Gui.isoFileTree.item( iidSelectionsTuple[0], 'values' )
		_, entity, _, _, isoPath, _, _ = iidValues # description, entity, isoOffset, fileSize, isoPath, source, data

		if entity == 'file':
			ext = os.path.splitext( iidSelectionsTuple[0] )[1]

			# Set the default filetypes to choose from in the dialog box (the filetype dropdown)
			fileTypeOptions = [ ('Texture data files', '*.dat *.usd *.lat *.rat'), ('Audio files', '*.hps *.ssm'),
								('System files', '*.bin *.ldr *.dol *.toc'), ('Video files', '*.mth *.thp'), ('All files', '*.*') ]
			for typeTuple in fileTypeOptions:
				extensions = typeTuple[1].split()
				if '*' + ext in extensions or ( typeTuple[0] == 'Texture data files' and ext[-2:] == 'at' ):
					orderedFileTypes = [ typeTuple ]
					break
			else: orderedFileTypes = [ ('Same type', '*'+ext) ]

			# Populate the rest of the possible types to choose from in the dialog box (the filetype dropdown)
			for typeTuple in fileTypeOptions:
				if typeTuple not in orderedFileTypes: orderedFileTypes.append( typeTuple )

			# Prompt the user to choose a file to import
			filePath = tkFileDialog.askopenfilename(
				title="Choose a file to import.",
				initialdir=settings.get( 'General Settings', 'defaultSearchDirectory' ),
				filetypes=orderedFileTypes ) # Should include the appropriate default file types first

			if filePath:
				# Update the default directory to start in when opening or exporting files.
				settings.set( 'General Settings', 'defaultSearchDirectory', os.path.dirname(filePath) )
				with open( settingsFile, 'w' ) as theSettingsFile: settings.write( theSettingsFile )

				# Check if this is a version of 20XX, and if so, get its main build number
				orig20xxVersion = globalDiscDetails['is20XX']
				if orig20xxVersion:
					if 'BETA' in orig20xxVersion: origMainBuildNumber = int( orig20xxVersion[-1] )
					else: origMainBuildNumber = int( orig20xxVersion[0] )
				else: origMainBuildNumber = 0

				# Check that this is an appropriate replacement file, and if so, replace it
				fileReplaced = replaceFileInDisc( iidSelectionsTuple[0], filePath, iidValues, orig20xxVersion, origMainBuildNumber )

				if fileReplaced:
					global unsavedDiscChanges
					unsavedDiscChanges.append( '"' + isoPath.split('/')[-1] + '" to be replaced with "' + os.path.basename( filePath ) + '".' )
					updateProgramStatus( 'File Replaced. Awaiting Save' )

		else: msg( "Please choose a file to replace for this operation. If you'd like to add new files to this folder, choose 'Add File(s) to Disc'." )
	
	else: msg( "When selecting files on the Disc File Tree to replace, please only select one file. If you'd like to replace multiple files, "
			   "use the 'Import Multiple Files' option in the Disc Operations menu." )


def importMultipleIsoFiles(): # i.e. replace multiple existing files in the disc
	if not discDetected(): return

	filepaths = tkFileDialog.askopenfilename(
		title="Choose files to import.", 
		initialdir=settings.get( 'General Settings', 'defaultSearchDirectory' ),
		multiple=True,
		filetypes=[ ('Texture data files', '*.dat *.usd *.lat *.rat'), ('Audio files', '*.hps *.ssm'), 
					('System files', '*.bin *.ldr *.dol *.toc'), ('Video files', '*.mth *.thp'), ('All files', '*.*') ]
		)

	if filepaths != '':
		# Update the default directory to start in when opening or exporting files.
		settings.set( 'General Settings', 'defaultSearchDirectory', os.path.dirname(filepaths[-1]) )
		with open( settingsFile, 'w') as theSettingsFile: settings.write( theSettingsFile )

		gameId = globalDiscDetails['gameId'].lower()
		filesNotInIso = []
		filesReadyForReplacement = 0
		cspColorGenerationTempDisabled = False

		# Check if this is a version of 20XX, and if so, get its main build number
		orig20xxVersion = globalDiscDetails['is20XX']
		if orig20xxVersion:
			if 'BETA' in orig20xxVersion: origMainBuildNumber = int( orig20xxVersion[-1] )
			else: origMainBuildNumber = int( orig20xxVersion[0] )
		else: origMainBuildNumber = 0

		# Offer to temporarily disable CSP Trim color generation if importing many files
		if generalBoolSettings['autoGenerateCSPTrimColors'].get():
			# Check if there are many character files being imported that would need CSP Trim color updates
			totalTrimColorGenerations = 0
			for filepath in filepaths:
				filename = os.path.basename( filepath ).lower()

				if candidateForTrimColorUpdate( filename, orig20xxVersion, origMainBuildNumber ): 
					totalTrimColorGenerations += 1
					if totalTrimColorGenerations > 15: break # We've seen enough

			if totalTrimColorGenerations > 15:
				cspColorGenerationTempDisabled = tkMessageBox.askyesno( 'Skip CSP Trim Color Generation?', 
							"When importing many alternate character costume files, CSP Trim Color Generation for them all can take a little while. Would you like to temporarily disable "
							"""the option "Auto-Generate CSP Trim Colors" for this operation?\n\nTip: The CSP Trim color data is stored in the MnSlChr (CSS) file, from 0x3A3C90 to """
							"0x3A45E0. So if you'd like to move all of it from one game/file to another, simply open the file in a hex editor and copy that region to your new CSS file "
							"(be sure you are overwriting, rather than inserting). Alternatively, you can use the names in the data table to help you do this for only specific characters." )

				if cspColorGenerationTempDisabled: generalBoolSettings['autoGenerateCSPTrimColors'].set( False )

		# Add the files to the file tree, check for pre-existing files of the same name, and prep the files to import
		for filepath in filepaths: # Folder paths will be excluded by askopenfilename

			fileName = os.path.basename( filepath ).replace( ' ', '_' ).replace( '-', '/' )
			iid = gameId + '/' + fileName.lower()

			if not Gui.isoFileTree.exists( iid ): filesNotInIso.append( fileName )
			else:
				# Update this file's treeview values
				if replaceFileInDisc( iid, filepath, Gui.isoFileTree.item(iid, 'values'), orig20xxVersion, origMainBuildNumber ): 
					filesReadyForReplacement += 1

		if filesReadyForReplacement > 0:
			global unsavedDiscChanges
			unsavedDiscChanges.append( str( filesReadyForReplacement ) + ' files ready to be replaced.' )
			updateProgramStatus( 'Files Replaced. Awaiting Save' )

		# Restore the CSP Color Generation option if it was temporarily disabled
		if cspColorGenerationTempDisabled:
			generalBoolSettings['autoGenerateCSPTrimColors'].set( True )

		if filesNotInIso != []: cmsg( 'These files will be skipped, because they could not be found in the disc:\n\n' + '\n'.join(filesNotInIso) )


def determineNewEntryPlacement():
	# Determine the location (parent, index, and a disc path) for the new file in the treeview
	targetIid = Gui.isoFileTree.selection()

	if targetIid:
		targetIid = targetIid[-1] # Simply selects the lowest position item selected
		_, entity, isoOffset, _, isoPath, _, _ = Gui.isoFileTree.item( targetIid, 'values' ) # description, entity, isoOffset, fileSize, isoPath, source, data

		# Remove the last portion of the disc path if it's a file or Convenience Folder
		if entity == 'file' or isoOffset == 'notNative': # The latter case means it's not originally part of the disc's file structure
			isoPath = '/'.join( isoPath.split('/')[:-1] )

		parent = Gui.isoFileTree.parent( targetIid )
		index = Gui.isoFileTree.index( targetIid )
	else:
		parent = globalDiscDetails['gameId'].lower()
		index = 'end'
		isoPath = globalDiscDetails['gameId']

	return parent, index, isoPath


def addFilesToIso(): # Adds files which did not previously exist in the disc to its filesystem 
	if not discDetected(): return
	
	# Prompt for one or more files to add.
	filepaths = tkFileDialog.askopenfilename(
		title='Choose one or more files (of any format) to add to the disc image.', 
		initialdir=settings.get( 'General Settings', 'defaultSearchDirectory' ),
		multiple=True,
		filetypes=[ ('All files', '*.*'), ('Texture data files', '*.dat *.usd *.lat *.rat'), ('Audio files', '*.hps *.ssm'),
					('System files', '*.bin *.ldr *.dol *.toc'), ('Video files', '*.mth *.thp') ]
		)

	if filepaths:
		origParent, index, origIsoPath = determineNewEntryPlacement()

		if origParent == globalDiscDetails['gameId'].lower() + '/sys':
			msg( 'Directories or files cannot be added to the system files folder.' )
			return

		firstItemAdded = ''
		preexistingFiles = []
		filenamesTooLong = []

		# Add the files to the file tree, check for pre-existing files of the same name, and prep the files to import
		for filepath in filepaths: # Folder paths will be excluded by askopenfilename
			# Reset these values; they may have changed by the last file's path (for creating folders)
			parent = origParent
			isoPath = origIsoPath

			# Get the new file's name and size
			fileName = os.path.basename( filepath ).replace( ' ', '_' ).replace( '-', '/' )
			fileNameOnly = fileName.split('/')[-1] # Will be no change from the original string if '/' is not present
			fileSize = int( os.path.getsize(filepath) ) # int() required to convert the value from long to int

			# Exclude files with filenames that are too long
			if len( os.path.splitext(fileNameOnly)[0] ) >= 30:
				filenamesTooLong.append( filepath )
				continue

			# Create folders that may be suggested by the filename (if these folders don't exist, the file won't either, so the file-existance check below this wont fail)
			if '/' in fileName:
				for folderName in fileName.split('/')[:-1]: # Ignore the last part, the file name
					isoPath += '/' + folderName
					iid = isoPath.lower()
					if not Gui.isoFileTree.exists( iid ): Gui.isoFileTree.insert( parent, index, iid=iid, text=' ' + folderName, 
						values=('', 'folder', 'native', '', isoPath, 'iso', ''), image=Gui.imageBank('folderIcon') )
					parent = iid

			# Exclude files that already exist in the disc
			isoPath += '/' + fileNameOnly
			iid = isoPath.lower()
			if Gui.isoFileTree.exists( iid ): 
				preexistingFiles.append( fileName )
				continue

			# Add the file
			Gui.isoFileTree.insert( parent, index, iid=iid, text=' ' + fileNameOnly, values=('Adding to disc...', 'file', '0', fileSize, isoPath, 'path', filepath), tags='changed' )
			if firstItemAdded == '': firstItemAdded = iid

			if index != 'end': index += 1

		# Notify the user of any excluded files
		notifications = ''
		if preexistingFiles: notifications += 'These files were skipped, because they already exist in the disc:\n\n' + '\n'.join(preexistingFiles)
		if filenamesTooLong: 
			if notifications: notifications += '\n\n'
			notifications += 'These files were skipped, because their file names are longer than 29 characters:\n\n' + '\n'.join(filenamesTooLong)
		if notifications: msg( notifications )

		# If any files were added, scroll to the newly inserted item (so it's visible to the user), and update the pending changes and program status
		if firstItemAdded:
			Gui.isoFileTree.see( firstItemAdded )

			global unsavedDiscChanges
			unsavedDiscChanges.append( str( len(filepaths) - len(preexistingFiles) ) + ' file(s) added to disc.' )
			globalDiscDetails['rebuildRequired'] = True
			updateProgramStatus( 'Files Added. Awaiting Save' )


def addDirectoryOfFilesToIso():
	if not discDetected(): return
	
	# Prompt for a directory to add files from.
	directoryPath = tkFileDialog.askdirectory(
		title='Choose a folder of files to add to the disc image.', 
		initialdir=settings.get( 'General Settings', 'defaultSearchDirectory' ),
		#parent=Gui.root,
		mustexist=True )

	if directoryPath:
		parent, index, isoPath = determineNewEntryPlacement()

		if parent == globalDiscDetails['gameId'].lower() + '/sys':
			msg( 'Directories or files cannot be added to the system files folder.' )
			return

		# Make sure a folder by this name doesn't already exist
		initialDirIid = parent + '/' + os.path.basename( directoryPath ).lower()
		if Gui.isoFileTree.exists( initialDirIid ): # Once this is established, further iids attached to this will always be unique, so no further checks are required.
			msg( 'A directory by this path and name already exists in the disc.' )
			return

		rootDir = os.path.dirname( directoryPath )
		firstItemAdded = ''
		foldersAdded = 0
		filesAdded = 0
		filenamesTooLong = []

		# Recursively scan the given folder and subfolders, and add all directories and files to the file tree
		for parentDir, listOfFolders, listOfFiles in os.walk( directoryPath ):
			modifiedParentDir = parentDir.replace( '-', '_' ).replace( ' ', '_' )
			modifiedDirName = os.path.basename( modifiedParentDir )

			# Exclude folders with names that are too long (>=30 characters)
			if len( modifiedDirName ) >= 30:
				filenamesTooLong.append( parentDir )
				continue

			relHeirarchy = os.path.relpath( parentDir, start=rootDir ).replace( '\\', '/' )
			thisFolderIsoPath = parent + '/' + relHeirarchy.replace( ' ', '_' ).replace( '-', '_' )

			thisFolderParent = '/'.join( thisFolderIsoPath.split('/')[:-1] ).lower() # removes the last directory from the path
			folderIid = thisFolderIsoPath.lower()

			# Attempt to grab the folder icon image.
			Gui.isoFileTree.insert( thisFolderParent, index, iid=folderIid, text=' ' + modifiedDirName, values=('Adding to disc...', 'folder', 'native', '', thisFolderIsoPath, 'iso', ''), image=Gui.imageBank('folderIcon'), tags='changed' )
			if firstItemAdded == '': firstItemAdded = folderIid
			foldersAdded += 1
			
			# Add the files for this folder
			for fileName in listOfFiles:
				modifiedfileName = fileName.replace( '-', '_' ).replace(' ', '_')

				# Exclude files with names that are too long (>=30 characters)
				if len( os.path.splitext(fileName)[0] ) >= 30:
					filenamesTooLong.append( parentDir + '/' + fileName )
					continue

				filePath = parentDir + '/' + fileName
				fileSize = os.path.getsize( filePath )
				isoPath = thisFolderIsoPath + '/' + modifiedfileName
				Gui.isoFileTree.insert( folderIid, 'end', iid=isoPath.lower(), text=' ' + modifiedfileName, values=('Adding to disc...', 'file', '0', fileSize, isoPath, 'path', filePath), tags='changed' )
				filesAdded += 1

			if index != 0: index = 0 # This may only be non-zero for the very first root folder that is being added

		# Notify the user of any skipped items
		if filenamesTooLong: msg( 'These files were skipped, because their file names are longer than 29 characters:\n\n' + '\n'.join(filenamesTooLong) )

		Gui.isoFileTree.see( firstItemAdded ) # Scrolls to the newly inserted items, so it's visible to the user.

		global unsavedDiscChanges
		unsavedDiscChanges.append( str(foldersAdded) + ' folders and ' + str(filesAdded) + ' files added to disc, from ' + rootDir + '.')
		globalDiscDetails['rebuildRequired'] = True
		updateProgramStatus( 'Items Added. Awaiting Save' )


def createDirectoryInIso():
	if not discDetected(): return
	
	# Determine the location (parent and index) for the directory in the treeview. Also need the isoPath, which is the item's case-preserved path
	targetIid = Gui.isoFileTree.selection()
	if targetIid:
		targetIid = targetIid[-1] # Simply selects the lowest position item selected
		_, entity, _, _, isoPath, _, _ = Gui.isoFileTree.item( targetIid, 'values' ) # description, entity, isoOffset, fileSize, isoPath, source, data

		if entity == 'folder':
			parent = targetIid
			index = 0
		else:
			isoPath = '/'.join( isoPath.split('/')[:-1] ) # removes the filename portion of the path
			parent = isoPath.lower()
			index = Gui.isoFileTree.index( targetIid )

		if parent == globalDiscDetails['gameId'].lower() + '/sys':
			msg( 'Directories or files cannot be added to the system files folder.' )
			return
	else:
		isoPath = globalDiscDetails['gameId']
		parent = isoPath.lower()
		index = 'end'

		if not Gui.isoFileTree.exists( parent ):
			msg( 'Unable to determine a target location for the new directory. Please first choose an existing item as a reference point.' )
			return

	# Prompt the user to enter a name for the directory; validate it, and parse it for a full path, if given
	nameChecksOut = False
	while not nameChecksOut:
		newIsoPath = isoPath
		iid = ''
		popupWindow = PopupEntryWindow( Gui.root, message='Enter a name for the directory:\n(Both absolute and relative paths are acceptable.)', width=50 )
		dirName = popupWindow.entryText.replace( '"', '' )
		if dirName == '': break

		# If the directory appears to be a full path, re-determine the parent directory
		if '\\' in dirName: msg( 'Please only use forward slashes ("/") when supplying an absolute path.' )
		else:
			for char in [ '-', '\\', ':', '*', '?', '<', '>', '|', ' ', '\n', '\t' ]:
				if char in dirName:
					msg( 'Spaces, line breaks, and the following characters may not be included in the path name: \t - \\ : * ? < > |' )
					break
			else: # if the above loop didn't break (meaning an invalid character wasn't found)
				if '/' in dirName: 
					pathParts = dirName.split( '/' )
					newIsoPath = '/'.join( pathParts[:-1] ) # removes the last portion (the new directory name) from the path
					parent = newIsoPath.lower()
					dirName = pathParts[-1]

					if not Gui.isoFileTree.exists( parent ):
						msg( 'Unable to locate the parent folder. please double-check that the path is correct.' )
						continue

				if len( dirName ) >= 30:
					msg( 'Directory names must be less than 30 characters in length.' )
					continue
				
				newIsoPath += '/' + dirName
				iid = newIsoPath.lower()
				if Gui.isoFileTree.exists( iid ): msg( 'This directory already exists. Please enter a different name.' )
				else: nameChecksOut = True

	if iid and dirName:
		Gui.isoFileTree.insert( parent, index, iid=iid, text=' ' + dirName, values=('Adding to disc...', 'folder', 'native', '', newIsoPath, 'iso', ''), image=Gui.imageBank('folderIcon'), tags='changed' )

		Gui.isoFileTree.see( iid ) # Scrolls to the newly inserted item, so it's visible to the user.

		global unsavedDiscChanges
		unsavedDiscChanges.append( 'Folder, "' + dirName + '", added to disc.')
		globalDiscDetails['rebuildRequired'] = True
		updateProgramStatus( 'Folder Added. Awaiting Save' )


def renameItem():
	if not discDetected(): return
	
	iidSelectionsTuple = Gui.isoFileTree.selection()

	if not iidSelectionsTuple: msg( 'Please select an item to rename.' )
	elif len( iidSelectionsTuple ) > 1: msg( 'Please only select one item to rename.' )
	else:
		originalIid = iidSelectionsTuple[0]
		description, entity, isoOffset, fileSize, isoPath, source, data = Gui.isoFileTree.item( originalIid, 'values' )
		originalName = isoPath.split('/')[-1]
		parent = Gui.isoFileTree.parent( originalIid )
		index = Gui.isoFileTree.index( originalIid )

		# Make sure this isn't a system file/folder
		systemFileFolder = globalDiscDetails['gameId'].lower() + '/sys'
		if originalIid == systemFileFolder or Gui.isoFileTree.parent( originalIid ) == systemFileFolder:
			msg( 'System files and the system files folder cannot be renamed.' )
			return

		# Prompt the user to enter a new name, and validate it
		nameChecksOut = False
		while not nameChecksOut:
			newIid = ''
			popupWindow = PopupEntryWindow( Gui.root, message='Enter a new name:', defaultText=originalName, width=30 )
			newName = popupWindow.entryText.replace( '"', '' )

			if newName == '': break

			# If the directory appears to be a full path, re-determine the parent directory
			if len( newName ) > 30: msg( 'Please specify a name less than 30 characters in length.' )
			else:
				for char in [ '-', '/', '\\', ':', '*', '?', '<', '>', '|', ' ', '\n', '\t' ]:
					if char in newName:
						msg( 'Spaces, line breaks, and the following characters may not be included in the name: \t - / \\ : * ? < > |' )
						break
				else: # if the above loop didn't break (meaning an invalid character wasn't found)
					newIsoPath = '/'.join( isoPath.split('/')[:-1] ) + '/' + newName
					newIid = newIsoPath.lower()
					if Gui.isoFileTree.exists( newIid ): msg( 'This item already exists. Please enter a different name.' )
					else: nameChecksOut = True

		if newName:
			Gui.isoFileTree.delete( originalIid )
			Gui.isoFileTree.insert( parent, index, iid=newIid, text=' ' + newName, values=(description, entity, isoOffset, fileSize, newIsoPath, source, data), tags='changed' )
			Gui.isoFileTree.selection_set( newIid )
			Gui.isoFileTree.focus( newIid )

			# Create a new FST and write it into the disc
			fstIid = globalDiscDetails['gameId'].lower() + '/game.toc'
			description, entity, isoOffset, fileSize, isoPath, source, data = Gui.isoFileTree.item( fstIid, 'values' )
			Gui.isoFileTree.item( fstIid, values=('Modified with a renamed entry', entity, isoOffset, fileSize, isoPath, 'ram', generateFST()), tags='changed' ) # Just changing the last two values

			global unsavedDiscChanges
			unsavedDiscChanges.append( originalName + ' renamed to ' + newName + '.' )
			updateProgramStatus( 'Item Renamed. Awaiting Save' )


def getTotalItems( parentIid='' ): # Gets file and folder counts for items within the given parent item (recursively).
	if Gui.isoFileTree.item( parentIid, 'values' )[1] == 'file': return 1, 0
	else:
		totalFiles = 0
		totalFolders = 1
		for iid in Gui.isoFileTree.get_children( parentIid ):
			if Gui.isoFileTree.item( iid, 'values' )[1] == 'file': totalFiles += 1
			else: # This is a folder
				subfolderFiles, subfolderFolders = getTotalItems( iid )
				totalFiles += subfolderFiles
				totalFolders += subfolderFolders
		return totalFiles, totalFolders


def removeItemsFromIso():
	if not discDetected(): return

	# Remove the selected items from the file tree
	totalFilesRemoved = 0
	totalFoldersRemoved = 0
	iidSelectionsTuple = Gui.isoFileTree.selection()

	if iidSelectionsTuple:
		for iid in iidSelectionsTuple:
			# Count the items about to be removed, and then remove them from the file tree
			if Gui.isoFileTree.exists( iid ): # This double-check is in case selections overlap (e.g. a folder and items within it were selected)
				filesRemoved, foldersRemoved = getTotalItems( iid )
				totalFilesRemoved += filesRemoved
				totalFoldersRemoved += foldersRemoved

				if Gui.isoFileTree.exists( iid ): Gui.isoFileTree.delete( iid ) # May not exist if it was in a folder that has already been deleted

		global unsavedDiscChanges
		unsavedDiscChanges.append( str(totalFilesRemoved) + ' files and ' + str(totalFoldersRemoved) + ' folders removed.' )
		globalDiscDetails['rebuildRequired'] = True
		updateProgramStatus( 'Items Removed. Awaiting Save' )


def moveSelectedToDirectory():
	if not discDetected(): return
	
	iidSelectionsTuple = Gui.isoFileTree.selection()

	if iidSelectionsTuple == '':
		msg( 'There are no items selected.' )
		return

	# Make sure the system folder and/or files within it are not selected.
	systemFileFolder = globalDiscDetails['gameId'].lower() + '/sys'
	for item in iidSelectionsTuple:
		if item == systemFileFolder or Gui.isoFileTree.parent( item ) == systemFileFolder:
			msg( 'System files and the system files folder cannot be modified.' )
			return

	# Get a list of folders currently in the disc (so the user can select a destination folder)
	directoriesDict = {}
	def browseFolders( folderIid='' ):
		for item in Gui.isoFileTree.get_children( folderIid ):
			_, entity, isoOffset, _, isoPath, _, _ = Gui.isoFileTree.item( item, 'values' ) # description, entity, isoOffset, fileSize, isoPath, source, data

			if entity == 'folder' and isoOffset == 'native': # This is a folder that was originally in the disc's filesystem
				directoriesDict[ isoPath ] = item
				browseFolders( item )
	browseFolders() # starts with the root

	# Cancel if there are no valid directories to move to.
	if directoriesDict == {}: 
		msg( 'There are no folders native to the disc to move these to.' )
		return

	# Present the user with a dropdown menu to choose a directory to move the selected items to
	dropDownMessage = 'Choose a directory to move these items to:\n(Only folders native to the disc will appear here.)'
	dropdownWindow = popupDropdownWindow( Gui.root, message=dropDownMessage, title='Move Item(s)', dropdownOptions=directoriesDict.keys() )
	if dropdownWindow.dropDownValue.get(): # The dropDownValue will be an empty string if the window was canceled.
		targetDirIid = directoriesDict[ dropdownWindow.dropDownValue.get() ]

		# Move the selected items to the chosen folder
		totalFilesMoved = 0
		totalFoldersMoved = 0
		for item in iidSelectionsTuple:
			if Gui.isoFileTree.exists( item ): # This double-check is in case selections overlap (e.g. a folder and items within it were selected)
				filesRemoved, foldersRemoved = getTotalItems( item )
				totalFilesMoved += filesRemoved
				totalFoldersMoved += foldersRemoved
				Gui.isoFileTree.move( item, targetDirIid, 'end' )
				Gui.isoFileTree.item( item, tags='changed' )
		Gui.isoFileTree.item( targetDirIid, tags='changed' )

		global unsavedDiscChanges
		unsavedDiscChanges.append( str(totalFilesMoved) + ' files and ' + str(totalFoldersMoved) + ' folders moved to ' + dropdownWindow.dropDownValue.get() + '.' )
		globalDiscDetails['rebuildRequired'] = True
		updateProgramStatus( 'Items Moved. Awaiting Save' )


def getInterFilePaddingLength( totalNonSystemFiles=0, totalFileSpace=0 ): # totalFileSpace is totaled from both system and main disc files, plus alignment adjustments
	paddingSettingsValue = settings.get( 'General Settings', 'paddingBetweenFiles' ).lower()

	if paddingSettingsValue == 'auto':
		standardGameCubeDiscSize = 1459978240
		spaceToFill = standardGameCubeDiscSize - totalFileSpace
		if spaceToFill < 0: interFilePaddingLength = 0
		else: interFilePaddingLength = spaceToFill / ( totalNonSystemFiles + 1 ) # The +1 allows for one more region of padding at the end of the disc.
	else:
		try:
			if '0x' in paddingSettingsValue: interFilePaddingLength = int( paddingSettingsValue, 16 )
			else: interFilePaddingLength = int( paddingSettingsValue )
		except: interFilePaddingLength = int( generalSettingsDefaults['paddingBetweenFiles'], 16 )

	# Undercut (reduce) the padding length, if necessary, to guarantee it is aligned to 4 bytes
	interFilePaddingLength -= interFilePaddingLength - int( 4 * math.floor(float(interFilePaddingLength) / 4) )

	return interFilePaddingLength


def getCssIid():
	cssIid = ''

	if not globalDiscDetails['isMelee']:
		print '\t\tCannot get CSS iid; disc detected as not Melee.'
	else:
		cssIid = scanDiscForFile( 'MnSlChr.u' ) # May be .usd (English) or .ukd (in PAL)
		if not cssIid: cssIid = scanDiscForFile( 'MnSlChr.0' ) # For 20XXHP v4.07/07+/07++

		if not cssIid: print '\t\tMnSlChr file not found.'

	return cssIid

																				#================================#
																				# ~ ~ Primary DAT Operations ~ ~ #
																				#================================#

def parseDatHeader( fileData ): # depricated. only the function below this is still using it

	""" Reads basic stats from the DAT's header. Input should be a bytes or bytearray object,
		and may be the entire file data or just the header (first 0x20 bytes). """

	if not isinstance( fileData, bytearray ) and not isinstance( fileData, bytes ): 
		raise IOError( 'Invalid input to parseDatHeader! Should be a bytearray or bytes.' )

	headerData = {}

	headerData['filesize'] = toInt( fileData[:4] )
	headerData['rtStart'] = rtStart = toInt( fileData[4:8] ) # Size of the data block
	headerData['rtEntryCount'] = rtEntryCount = toInt( fileData[8:12] )
	headerData['rootNodeCount'] = rootNodeCount = toInt( fileData[12:16] )
	headerData['referenceNodeCount'] = referenceNodeCount = toInt( fileData[16:20] )
	headerData['rtEnd'] = rtEnd = rtStart + ( rtEntryCount * 4 )
	headerData['stringTableStart'] = rtEnd + (rootNodeCount * 8) + (referenceNodeCount * 8)

	return headerData


def parseStringTable( localDatData, sortNodes=True ): # depricated. only one function still using this
	try:
		if not isinstance( localDatData, bytearray ) and not isinstance( localDatData, bytes ): 
			raise IOError( 'Invalid input to parseStringTable! Should be a bytearray or bytes.' )

		headerInfo = parseDatHeader( localDatData )

		rootAndRefNodesTable = localDatData[0x20 + headerInfo['rtEnd']:0x20 + headerInfo['stringTableStart']]
		nodesTable = [ rootAndRefNodesTable[i:i+8] for i in xrange(0, len(rootAndRefNodesTable), 8) ] # list comprehension; separates the data into groups of 8 bytes
		stringTable = localDatData[0x20 + headerInfo['stringTableStart']:]

		stringDict = {}
		offset = 0
		strings = stringTable.split(b'\x00')[:len(nodesTable)] # Final splicing eliminates an empty string and/or extra additions at the end of the file.
		for stringBytes in strings:
			string = stringBytes.decode( 'ascii' ) # Convert from a bytearray to a string
			stringDict[offset] = string
			offset += len( string ) + 1 # +1 to account for null terminator

		rootNodes = []; referenceNodes = [] # Both of these will be a list of tuples of the form ( filePointer, string )
		for i, entry in enumerate( nodesTable ):
			stringOffset = toInt( entry[4:] ) # first 4 bytes
			filePointer = toInt( entry[:4] )  # second 4 bytes
			string = stringDict[ stringOffset ]

			if i < headerInfo['rootNodeCount']: rootNodes.append( ( filePointer, string ) )
			else: referenceNodes.append( ( filePointer, string ) )

		if sortNodes:
			rootNodes.sort()
			referenceNodes.sort()

		return rootNodes, referenceNodes, stringDict
	except:
		return [], [], {}


def updatePrevNextFileButtons( currentFile, forStandaloneFile=False ):

	""" Updates the Next/Previous DAT buttons on the DAT Texture Tree tab. Sets their target file to load,
		their tooltip/pop-up text, and the mouse cursor to appear when hovering over it. 'currentFile' will
		be a full/absolute file path if this is for a standalone file, (one not in a disc) 
		otherwise it will be an iid for the file in the Disc File Tree tab. """

	if forStandaloneFile:
		# Get a list of all DAT and/or USD files (plus whatever current file type is loaded) in the current directory.
		currentDirectory, filename = os.path.split( currentFile )
		currentExtension = filename.split('.')[-1]
		filenamesList = [ f for f in os.listdir(currentDirectory) if os.path.isfile(os.path.join(currentDirectory, f)) ] # Builds a list of files; excludes folders
		filteredFilenamesList = [ fn for fn in filenamesList if any([ fn.lower().endswith(ext) for ext in [currentExtension, '.dat', '.usd'] ]) ] # Removes files of other types.

		# Iterate the files list to find the currently loaded file
		for i, filename in enumerate( filteredFilenamesList ):
			if os.path.join( currentDirectory, filename ) == currentFile:
				# Check whether there is a previous entry.
				if i != 0:
					prevFile = filteredFilenamesList[i-1]
					Gui.previousDatText.set( prevFile )
					Gui.previousDatButton.bind( '<1>', 
						lambda event, prevPath=os.path.normpath( os.path.join(currentDirectory, prevFile) ): loadPreviousOrNextDat(prevPath) )
					Gui.previousDatButton.config( cursor='hand2' )
				else:
					Gui.previousDatText.set( 'No more!' )
					Gui.previousDatButton.unbind( '<1>' )
					Gui.previousDatButton.config( cursor='' )

				# Check whether there is a next entry.
				if i != len(filteredFilenamesList) - 1: 
					nextFile = filteredFilenamesList[i+1]
					Gui.nextDatText.set( nextFile )
					Gui.nextDatButton.bind( '<1>', 
						lambda event, nextPath=os.path.normpath( os.path.join(currentDirectory, nextFile) ): loadPreviousOrNextDat(nextPath) )
					Gui.nextDatButton.config( cursor='hand2' )
				else:
					Gui.nextDatText.set( 'No more!' )
					Gui.nextDatButton.unbind( '<1>' )
					Gui.nextDatButton.config( cursor='' )
				break

	else: # The current file is from a disc. 'currentFile' is an iid string.

		# Update the prev. file button
		prevItem = Gui.isoFileTree.prev( currentFile )
		while prevItem != '' and Gui.isoFileTree.item( prevItem, 'values' )[1] != 'file': 
			prevItem = Gui.isoFileTree.prev( prevItem ) # Skips over any folders.
		if prevItem != '':
			Gui.previousDatText.set( prevItem )
			Gui.previousDatButton.bind( '<1>', lambda event, item=prevItem: loadPreviousOrNextDat(item) )
			Gui.previousDatButton.config( cursor='hand2' )
		else:
			Gui.previousDatText.set( 'No more!' )
			Gui.previousDatButton.unbind('<1>')
			Gui.previousDatButton.config( cursor='' )

		# Update the next file button
		nextItem = Gui.isoFileTree.next( currentFile )
		while nextItem != '' and Gui.isoFileTree.item( nextItem, 'values' )[1] != 'file': 
			nextItem = Gui.isoFileTree.next( nextItem ) # Skips over any folders.
		if nextItem != '':
			Gui.nextDatText.set( nextItem )
			Gui.nextDatButton.bind( '<1>', lambda event, item=nextItem: loadPreviousOrNextDat(item) )
			Gui.nextDatButton.config( cursor='hand2' )
		else:
			Gui.nextDatText.set( 'No more!' )
			Gui.nextDatButton.unbind('<1>')
			Gui.nextDatButton.config( cursor='' )


def loadPreviousOrNextDat( newFileToLoad ):

	""" Loads the next/previous file from a disc or within a folder. Used by the Previous / Next DAT buttons on the DAT Texture Tree tab. 
		'newFileToLoad' is an iid from the Gui.isoFileTree treeview widget. """

	if Gui.datTextureTree.lastLoaded.source == 'disc':
		loadFileWithinDisc( newFileToLoad, changeTab=False ) # Includes checks on whether the user wants to save prior changes built-in

	else:
		# Make sure there aren't any changes that the user wants to save before loading in a new file
		if newFileToLoad.lower().endswith( '.bnr' ):
			if globalBannerFile and not globalBannerFile.noChangesToBeSaved( programClosing ): return
			else: restoreEditedEntries( editedBannerEntries )
		else:
			if globalDatFile and not globalDatFile.noChangesToBeSaved( programClosing ): return
			else: restoreEditedEntries( editedDatEntries )

		loadStandaloneFile( newFileToLoad, changeTab=False )


def browseTexturesFromDisc():

	""" Wrapper for the 'Browse Textures' button in the GUI (or file tree double-click) and option in the dropdown menus. """

	if not discDetected(): return

	iidSelectionsTuple = Gui.isoFileTree.selection()

	if len( iidSelectionsTuple ) == 0: msg( 'Please select a file to browse in.' )
	elif len( iidSelectionsTuple ) > 1: msg( 'Please only select one file to browse in.' )
	else:
		loadFileWithinDisc( iidSelectionsTuple[0] )


def analyzeFileFromDisc():

	""" Wrapper for the 'Analyze Structure' button in the GUI (or file tree double-click) and option in the dropdown menus. """

	if not discDetected(): return

	iidSelectionsTuple = Gui.isoFileTree.selection()

	if len( iidSelectionsTuple ) == 0: msg( 'Please select a file to analyze.' )
	elif len( iidSelectionsTuple ) > 1: msg( 'Please only select one file to analyze.' )
	else:
		loadFileWithinDisc( iidSelectionsTuple[0], toAnalyze=True )


def loadFileWithinDisc( iid, toAnalyze=False, changeTab=True ):

	""" Prepares a file in a disc for reading in the DAT Texture Tree tab. Called by the 'Browse Images' button, 
		the dropdown menus, and the loadPrevious/NextDat buttons. """

	_, entity, _, _, isoPath, _, _ = Gui.isoFileTree.item( iid, 'values' )

	if entity != 'file':
		msg( 'Please only select a file (not a folder) to browse in for textures.' )
		return

	# Set the selected item in the ISO File Tree, so that it's clear which file is being viewed in DAT Texture Tree.
	Gui.isoFileTree.selection_set( iid )
	Gui.isoFileTree.focus( iid )
	Gui.isoFileTree.see( iid ) # Scrolls to the given item to make sure it's visible in the tree

	# Ensure the disc can still be located
	if not discDetected(): return

	updatePrevNextFileButtons( iid )

	global globalBannerFile, globalDatFile
	fileExt = isoPath.split( '.' )[-1].lower()

	# Ask the user if they'd like to save any unsaved changes before forgetting the current file
	if fileExt == 'bnr':
		# Make sure there aren't any changes the user wants saved
		if globalBannerFile and not globalBannerFile.noChangesToBeSaved( programClosing ): return

		globalBannerFile = hsdFiles.datFileObj( source='disc' ) # Close enough match that that container will work well

		if not globalBannerFile.load( iid, fileData=getFileDataFromDiscTreeAsBytes( iid=iid ), fileName=os.path.basename(isoPath) ):
			updateProgramStatus( 'Banner File Could Not Be Loaded' )
			msg( 'The disc that this file resided in, or the exernal file that this referenced, can no longer be found (it may have been moved/renamed/deleted).' )

		else:
			restoreEditedEntries( editedBannerEntries )
			Gui.datTextureTree.lastLoaded = globalBannerFile
			Gui.mainTabFrame.select( Gui.discDetailsTab )

			reloadBanner()
			updateProgramStatus( 'File Scan Complete' )

	else:
		# Make sure there aren't any changes the user wants saved
		if globalDatFile and not globalDatFile.noChangesToBeSaved( programClosing ): return

		globalDatFile = hsdFiles.datFileObj( source='disc' )

		if not globalDatFile.load( iid, fileData=getFileDataFromDiscTreeAsBytes( iid=iid ), fileName=os.path.basename(isoPath) ):
			updateProgramStatus( 'DAT File Could Not Be Loaded' )
			msg( 'The disc that this file resided in, or the exernal file that this referenced, can no longer be found (it may have been moved/renamed/deleted).' )

		else:
			restoreEditedEntries( editedDatEntries )
			Gui.datDestination.set( isoPath )
			Gui.datTextureTree.lastLoaded = globalDatFile

			clearDatTab()
			clearStructuralAnalysisTab()

			# Disable the tab switch feature if it is desired but we're already on the right tab (the handler won't activate)
			currentTab = Gui.root.nametowidget( Gui.mainTabFrame.select() )
			if toAnalyze and currentTab == Gui.savTab: changeTab = False
			elif not toAnalyze and currentTab == Gui.datTab: changeTab = False

			if changeTab:
				# Switch tabs, and let the event handler bound to tab switching handle calling of the scan/analyze function.
				if toAnalyze:
					Gui.mainTabFrame.select( Gui.savTab )
				else:
					Gui.mainTabFrame.select( Gui.datTab )

			elif currentTab == Gui.savTab:
				analyzeDatStructure()
			else:
				scanDat()


def loadStandaloneFile( filepath, toAnalyze=False, changeTab=True ):

	""" This function updates the Next/Previous DAT buttons on the DAT Texture Tree tab,
		it then loads the appropriate next/previous banner or DAT file and scans it. """
		#todo perhaps move checks on whether the user wants to save unsaved changes to this function

	updatePrevNextFileButtons( filepath, forStandaloneFile=True )

	# Check if this is a banner file or a DAT
	if filepath.split( '.' )[-1].lower() == 'bnr':
		if changeTab:
			Gui.mainTabFrame.select( Gui.discDetailsTab )

		global globalBannerFile
		globalBannerFile = hsdFiles.datFileObj()
		globalBannerFile.load( filepath )

		Gui.isoDestination.set( filepath )
		Gui.datTextureTree.lastLoaded = globalBannerFile

		updateBannerFileInfo()
		updateProgramStatus( 'File Scan Complete' )

	else:
		global globalDatFile
		globalDatFile = hsdFiles.datFileObj()
		globalDatFile.load( filepath )

		Gui.datDestination.set( filepath )
		Gui.datTextureTree.lastLoaded = globalDatFile

		clearDatTab()
		clearStructuralAnalysisTab()

		# Disable the tab switch feature if it is desired but we're already on the right tab (the handler won't activate in this case)
		currentTab = Gui.root.nametowidget( Gui.mainTabFrame.select() )
		if changeTab:
			if toAnalyze and currentTab == Gui.savTab: changeTab = False
			elif not toAnalyze and currentTab == Gui.datTab: changeTab = False

		if changeTab:
			# Switch tabs, and let the event handler bound to tab switching handle calling of the scan/analyze function.
			if toAnalyze:
				Gui.mainTabFrame.select( Gui.savTab )
			else:
				Gui.mainTabFrame.select( Gui.datTab )

		elif currentTab == Gui.savTab: 
			analyzeDatStructure()
		else:
			scanDat()


def clearDatTab( restoreBackground=False ):
	# Remove any existing entries in the treeview.
	for item in Gui.datTextureTree.get_children(): Gui.datTextureTree.delete( item )

	# Reset the size of the texture display canvas, and clear its contents (besides the grid)
	Gui.textureDisplay.configure( width=Gui.textureDisplay.defaultDimensions, height=Gui.textureDisplay.defaultDimensions )
	Gui.textureDisplay.delete( Gui.textureDisplay.find_withtag('border') )
	Gui.textureDisplay.delete( Gui.textureDisplay.find_withtag('texture') )

	# Add or remove the background drag-n-drop image
	if restoreBackground:
		Gui.datTextureTreeBg.place( relx=0.5, rely=0.5, anchor='center' )
	else: # This function removes them by default
		Gui.datTextureTreeBg.place_forget()
	Gui.datTextureTreeStatusLabel.place_forget()

	# Reset the values on the Image tab.
	Gui.datFilesizeText.set( 'File Size:  ' )
	Gui.totalTextureSpaceText.set( 'Total Texture Size:  ' )
	Gui.texturesFoundText.set( 'Textures Found:  ' )
	Gui.texturesFilteredText.set( 'Filtered Out:  ' )

	# Disable some tabs by default (within the DAT Texture Tree tab), and if viewing one of them, switch to the Image tab
	if Gui.root.nametowidget( Gui.imageManipTabs.select() ) != Gui.textureTreeImagePane:
		Gui.imageManipTabs.select( Gui.textureTreeImagePane )
	Gui.imageManipTabs.tab( Gui.palettePane, state='disabled' )
	Gui.imageManipTabs.tab( Gui.modelPropertiesPane, state='disabled' )
	Gui.imageManipTabs.tab( Gui.texturePropertiesPane, state='disabled' )

	# Clear the repositories for storing image data (used to prevent garbage collected)
	Gui.datTextureTree.fullTextureRenders = {}
	Gui.datTextureTree.textureThumbnails = {}


def scanDat( priorityTargets=() ):

	""" This function is the main function to handle reading and displaying textures from a DAT file, 
		whether from a disc or a standalone file. After identifying texture locations and properties,
		rendering is performed in separate processes. These processes are started and waited for in a
		separate thread, so that this function may return and allow for GUI responsiveness. """

	if not globalDatFile: return

	# If this function is called while already processing a file, queue cancellation of the last instance of the function.
	# The last function instance will then re-call this to scan the new file.
	global scanningDat, stopAndScanNewDat
	if scanningDat:
		stopAndScanNewDat = True
		return

	# Check what kind of file this is (this is done a bit more below as well).
	elif globalDatFile.fileExt == 'dol':
		scanDol()
		updateProgramStatus( 'File Scan Complete' )

		if Gui.datTextureTree.get_children() == ():
			Gui.datTextureTreeStatusMsg.set( 'Either no textures were found, or you have them filtered out.' )
			Gui.datTextureTreeStatusLabel.place( relx=0.5, rely=0.5, anchor='center' )
		return

	# Only attempt to process DAT files (Also needs to capture 20XX extensions as well. e.g. .0at, .cat, .wat, .1sd, .2sd, etc.)
	elif not globalDatFile.fileExt.endswith( 'at' ) and not globalDatFile.fileExt.endswith( 'sd' ):# Not recognized as a DAT file
		Gui.datTextureTreeStatusMsg.set( 'This file is not recognized as a DAT file.\n\nIf you believe it is, try changing the file extension.' )
		Gui.datTextureTreeStatusLabel.place( relx=0.5, rely=0.5, anchor='center' )
		return

	# Values too large may cause the loops in the following section to fully lock up a computer, and most likely indicate a non-DAT file anyway
	hI = globalDatFile.headerInfo
	if hI['rootNodeCount'] > 300 or hI['referenceNodeCount'] > 300 or hI['rtEntryCount'] > 45000:
		updateProgramStatus( 'wut' )
		msg( 'This file has an unrecognized data structure.'
			'\n\nRoot Node count: ' + str(hI['rootNodeCount']) + 
			'\nReference Node count: ' + str(hI['referenceNodeCount']) + 
			'\nRT Entry count: ' + str(hI['rtEntryCount']) )
			
		Gui.datTextureTreeStatusMsg.set( 'Unrecognized data structure' )
		Gui.datTextureTreeStatusLabel.place( relx=0.5, rely=0.5, anchor='center' )
		return

	# Check that the RT table isn't too unwieldy
	if len( globalDatFile.rtData ) > 200000:
		updateProgramStatus( '¿Qué?' )
		msg('This file has an unrecognized data structure.'
			'\n\nRT Data Byte Length: ' + str( len(globalDatFile.rtData) ) + \
			'\nCalculated Number of RT Entries: ' + str( len(globalDatFile.rtData)/4 ) )
			
		Gui.datTextureTreeStatusMsg.set( 'Unrecognized data structure (RT too large)' )
		Gui.datTextureTreeStatusLabel.place( relx=0.5, rely=0.5, anchor='center' )
		return
	
	# Seems to be some kind of DAT. Find the textures!
	updateProgramStatus( 'Scanning File....' )
	Gui.programStatusLabel.update()

	scanningDat = True
	texturesInfo = identifyTextures( globalDatFile )
	texturesFound = texturesFiltered = totalTextureSpace = 0
	filteredTexturesInfo = []

	if rescanPending(): return

	elif texturesInfo: # i.e. textures were found
		texturesInfo.sort( key=lambda infoTuple: infoTuple[0] ) # Sorts the textures by file offset
		dumpImages = generalBoolSettings['dumpPNGs'].get()
		loadingImage = Gui.imageBank( 'loading' )
		
		for imageDataOffset, imageHeaderOffset, paletteDataOffset, paletteHeaderOffset, width, height, imageType, mipmapCount in texturesInfo:
			# Ignore textures that don't match the user's filters
			if not passesImageFilters( imageDataOffset, width, height, imageType ):
				if imageDataOffset in priorityTargets: pass # Overrides the filter
				else:
					texturesFiltered += 1
					continue

			# Initialize a structure for the image data
			imageDataLength = hsdStructures.ImageDataBlock.getDataLength( width, height, imageType ) # Returns an int (counts in bytes)
			imageDataStruct = globalDatFile.initDataBlock( hsdStructures.ImageDataBlock, imageDataOffset, imageHeaderOffset, dataLength=imageDataLength )
			imageDataStruct.imageHeaderOffset = imageHeaderOffset
			imageDataStruct.paletteDataOffset = paletteDataOffset # Ad hoc way to locate palettes in files with no palette data headers
			imageDataStruct.paletteHeaderOffset = paletteHeaderOffset
			filteredTexturesInfo.append( (imageDataOffset, width, height, imageType, imageDataLength) )

			totalTextureSpace += imageDataLength
			texturesFound += 1

			# Highlight any textures that need to stand out
			tags = []
			#if width > 1024 or width % 2 != 0 or height > 1024 or height % 2 != 0: tags.append( 'warn' )
			if mipmapCount > 0: tags.append( 'mipmap' )

			# Add this texture to the DAT Texture Tree tab, using the thumbnail generated above
			try:
				Gui.datTextureTree.insert( '', 'end', 									# '' = parent/root, 'end' = insert position
					iid=str( imageDataOffset ),
					image=loadingImage,
					values=(
						uHex(0x20 + imageDataOffset) + '\n('+uHex(imageDataLength)+')', 	# offset to image data, and data length
						(str(width)+' x '+str(height)), 								# width and height
						'_'+str(imageType)+' ('+imageFormats[imageType]+')' 			# the image type and format
					),
					tags=tags
				)
			except TclError:
				print hex(imageDataOffset), 'already exists!'
				continue
			#print uHex( 0x20+imageDataOffset ), ' | ', constructTextureFilename(globalDatFile, str(imageDataOffset))

			# Add any associated mipmap images, as treeview children
			if mipmapCount > 0:
				parent = imageDataOffset

				for i in xrange( mipmapCount ):
					# Adjust the parameters for the next mipmap image
					imageDataOffset += imageDataLength # This is of the last image, not the current imageDataLength below
					width = int( math.ceil(width / 2.0) )
					height = int( math.ceil(height / 2.0) )
					imageDataLength = getImageDataLength( width, height, imageType )

					# Add this texture to the DAT Texture Tree tab, using the thumbnail generated above
					Gui.datTextureTree.insert( parent, 'end', 									# 'end' = insertion position
						iid=str( imageDataOffset ),
						image=loadingImage, 	
						values=(
							uHex(0x20 + imageDataOffset) + '\n('+uHex(imageDataLength)+')', 	# offset to image data, and data length
							(str(width)+' x '+str(height)), 								# width and height
							'_'+str(imageType)+' ('+imageFormats[imageType]+')' 			# the image type and format
						),
						tags=tags
					)
					filteredTexturesInfo.append( (imageDataOffset, width, height, imageType, imageDataLength) )

		# Immediately decode and display any high-priority targets
		if priorityTargets:
			for textureInfo in texturesInfo:
				if textureInfo[0] not in priorityTargets: continue

				imageDataOffset, _, _, _, width, height, imageType, _ = textureInfo
				dataBlockStruct = globalDatFile.getStruct( imageDataOffset )

				renderTextureData( imageDataOffset, width, height, imageType, dataBlockStruct.length, allowImageDumping=dumpImages )

	# Update the GUI with some of the file's main info regarding textures
	Gui.datFilesizeText.set( "File Size:  {:,} bytes".format(hI['filesize']) )
	Gui.totalTextureSpaceText.set( "Total Texture Size:  {:,} b".format(totalTextureSpace) )
	Gui.texturesFoundText.set( 'Textures Found:  ' + str(texturesFound) )
	Gui.texturesFilteredText.set( 'Filtered Out:  ' + str(texturesFiltered) )

	if rescanPending(): return

	if not filteredTexturesInfo: # Done (no textures to display). Nothing else left to do here.
		scanningDat = False # Should be set to False by the GUI thumbnail update loop if the method below is used instead.
	else:
		# tic = time.clock()
		if 0: # Disabled, until this process can be made more efficient
			#print 'using multiprocessing decoding'

			# Start a loop for the GUI to watch for updates (such updates should not be done in a separate thread or process)
			Gui.thumbnailUpdateJob = Gui.root.after( Gui.thumbnailUpdateInterval, Gui.updateTextureThumbnail )

			# Start up a separate thread to handle and wait for the image rendering process
			renderingThread = Thread( target=startMultiprocessDecoding, args=(filteredTexturesInfo, globalDatFile, Gui.textureUpdateQueue, dumpImages) )
			renderingThread.daemon = True # Allows this thread to be killed automatically when the program quits
			renderingThread.start()

		else: # Perform standard single-process, single-threaded decoding
			#print 'using standard, single-process decoding'

			i = 1
			for imageDataOffset, width, height, imageType, imageDataLength in filteredTexturesInfo:
				# Skip items that should have already been processed
				if imageDataOffset in priorityTargets: continue

				# Update this item
				renderTextureData( imageDataOffset, width, height, imageType, imageDataLength, allowImageDumping=dumpImages )

				# Update the GUI to show new renders every n textures
				if i % 10 == 0:
					if rescanPending(): return
					Gui.datTextureTree.update()
				i += 1

			scanningDat = False

		# toc = time.clock()
		# print 'image rendering time:', toc - tic

	updateProgramStatus( 'File Scan Complete' )

	if Gui.datTextureTree.get_children() == (): # Display a message that no textures were found, or they were filtered out.
		Gui.datTextureTreeStatusMsg.set( 'Either no textures were found, or you have them filtered out.' )
		Gui.datTextureTreeStatusLabel.place( relx=0.5, rely=0.5, anchor='center' )


def rescanPending():
	global scanningDat, stopAndScanNewDat, programClosing

	# Allow this function instance to end gracefully if it is no longer needed (only one should ever be running)
	if stopAndScanNewDat:
		#cancelCurrentRenders() # Should be enabled if multiprocess texture decoding is enabled

		scanningDat = False
		stopAndScanNewDat = False

		# Restart the DAT/DOL file scan
		clearDatTab()
		scanDat()

		return True

	elif programClosing:
		Gui.root.destroy()
		return True

	else:
		return False


def cancelCurrentRenders():

	""" Used for multi-process texture decoding. Stops the GUI thumbnail update loop and shuts down rendering process pool. """

	# Cancel the GUI's thumbnail update loop if it's running
	if Gui.thumbnailUpdateJob:
		Gui.root.after_cancel( Gui.thumbnailUpdateJob )
		Gui.thumbnailUpdateJob = None

	# Stop currently active rendering processes
	if Gui.processRenderingPool:
		Gui.processRenderingPool.close()
		Gui.processRenderingPool.terminate()
		Gui.processRenderingPool = None

	# Empty the thumbnail update queue (this is more efficient than re-creating it)
	try:
		while True:
			Gui.textureUpdateQueue.get_nowait() # Will raise an exception and exit once the loop is empty
	except: pass


def startMultiprocessDecoding( filteredTexturesInfo, datFileObj, resultQueue, dumpImages ):

	""" Creates separate processes for decoding texture data for faster performance. This is done in a 
		separate thread in order to avoid blocking GUI updates from a function that doesn't immediately return. """

	# Create a pool of processors to perform the rendering
	processors = multiprocessing.cpu_count()
	Gui.processRenderingPool = multiprocessing.Pool( processors ) #, maxtasksperchild=1

	for textureProperties in filteredTexturesInfo:
		Gui.processRenderingPool.apply_async( decodeTextureData, args=(textureProperties, datFileObj, resultQueue, dumpImages) )

	# All the jobs have been started. Now wait for them to finish and close the pool.
	Gui.processRenderingPool.close()
	Gui.processRenderingPool.join() # Blocks until all processes are finished
	Gui.processRenderingPool = None

	global stopAndScanNewDat
	if not stopAndScanNewDat:
		Gui.textureUpdateQueue.put( (None, -1) )
	#Gui.root.event_generate( '<<message>>', when='mark' )


def isEffectsFile( datFileObj ): # Checks the Root/Reference Nodes and string table

	# Expecting just one root node, and no reference nodes
	if len( datFileObj.rootNodes ) == 1 and len( datFileObj.referenceNodes ) == 0:
		rootStructOffset, stringTableSymbol = datFileObj.rootNodes[0]

		if rootStructOffset == 0 and stringTableSymbol.startswith( 'eff' ): # Effects file confirmed
			return True

	return False


def identifyTextures( datFile ): # todo: this function should be a method on various kinds of distinct dat file objects

	""" Returns a list of tuples containing texture info. Each tuple is of the following form: 
			( imageDataOffset, imageHeaderOffset, paletteDataOffset, paletteHeaderOffset, width, height, imageType, mipmapCount ) """

	imageDataOffsetsFound = set()
	texturesInfo = []
	
	# tic = time.clock()

	try:
		# Check if this is a special file with texture data end-to-end
		if (0, 'SIS_MenuData') in datFile.rootNodes: # For alphabet textures such as Kanji; SdMenu.dat/.usd
			if datFile.fileExt not in ( 'frd', 'gmd', 'itd', 'spd', 'ukd' ): # PAL files; no textures in these, just strings
				# There are no headers for these images, but they all have the same properties.
				textureTableStart = toInt( datFile.data[:4] )
				totalTextures = ( datFile.headerInfo['rtStart'] - textureTableStart ) / 0x200 # 0x200 is the image data length

				#scanEndToEndImageData( textureTableStart, width, height, imageType, imageDataLength, totalTextures )
				for i in range( totalTextures ):
					imageDataOffset = textureTableStart + ( i * 0x200 )
					texturesInfo.append( (imageDataOffset, -1, -1, -1, 32, 32, 0, 0) )

		elif (0x1E00, 'MemSnapIconData') in datFile.rootNodes: # The file is LbMcSnap.usd or LbMcSnap.dat (Memory card banner/icon file from SSB Melee)
			# Banner details
			texturesInfo.append( (0, -1, -1, -1, 96, 32, 5, 0) )

			# Icon details
			texturesInfo.append( (0x1800, -1, 0x1C20, -1, 32, 32, 9, 0) )

		elif (0x4E00, 'MemCardIconData') in datFile.rootNodes: # The file is LbMcGame.usd or LbMcGame.dat (Memory card banner/icon file from SSB Melee)
			# Details on three banners
			for offset in ( 0, 0x1800, 0x3000 ):
				texturesInfo.append( (offset, -1, -1, -1, 96, 32, 5, 0) )

			# Icon details
			texturesInfo.append( (0x4800, -1, 0x4C20, -1, 32, 32, 9, 0) )

		else: # Standard DAT processing
			# Check if this is an Effects file. These have standard structuring as well as some unique table structuring
			if isEffectsFile( datFile ):
				# Initialize Struct 0x20 (present in all effects files)
				rootStruct = datFile.getStruct( 0 ) # 0 is the 0x20 offset relative to the data section

				# Check children of Struct 0x20 until a Joint Object is found; structs up until this may be large blocks of image data with rudimentary headers
				imageDataOffset = -1
				imageBlockOffsets = []
				for childStructOffset in rootStruct.getChildren():
					potentialJointObj = datFile.getStruct( childStructOffset )

					if potentialJointObj.validated(): break
					else:
						imageBlockOffsets.append( childStructOffset )

				for mainEffHeaderTableOffset in imageBlockOffsets:
					# Check the first two bytes; values of 0042 indicate that the header actually starts 0x8 bytes in
					if datFile.data[mainEffHeaderTableOffset+1] == 0x42:
						mainHeaderStart = mainEffHeaderTableOffset + 8
						continue # Unsure if these tables even point to textures; if they do, they seem to be in another structure format
					else: mainHeaderStart = mainEffHeaderTableOffset

					# Get the entry count of the table (number of table pointers it contains), and the entries themselves
					mainTableEntryCount = toInt( datFile.data[mainHeaderStart:mainHeaderStart+4] )
					headerTableData = datFile.data[mainHeaderStart+4:mainHeaderStart+4+(mainTableEntryCount*4)]
					headerTablePointers = struct.unpack( '>' + str(mainTableEntryCount) + 'I', headerTableData )

					for pointer in headerTablePointers:
						# Process the E2E header
						e2eHeaderOffset = mainEffHeaderTableOffset + pointer

						textureCount, imageType, _, width, height = struct.unpack( '>5I', datFile.data[e2eHeaderOffset:e2eHeaderOffset+0x14] )
						imageDataPointersStart = e2eHeaderOffset + 0x18
						imageDataPointersEnd = imageDataPointersStart + ( 4 * textureCount )
						imageDataPointerValues = struct.unpack( '>' + textureCount * 'I', datFile.data[imageDataPointersStart:imageDataPointersEnd] )

						if imageType in ( 8, 9, 10 ):
							paletteDataPointersEnd = imageDataPointersEnd + ( 4 * textureCount )
							paletteDataPointerValues = struct.unpack( '>' + textureCount * 'I', datFile.data[imageDataPointersEnd:paletteDataPointersEnd] )

						for i, offset in enumerate( imageDataPointerValues ):
							imageDataOffset = mainEffHeaderTableOffset + offset

							if imageType in ( 8, 9, 10 ):
								# Need to get the palette data's offset too. Its pointer is within a list following the image data pointer list
								paletteDataOffset = mainEffHeaderTableOffset + paletteDataPointerValues[i]
								texturesInfo.append( (imageDataOffset, -1, paletteDataOffset, -1, width, height, imageType, 0) )
							else:
								texturesInfo.append( (imageDataOffset, -1, -1, -1, width, height, imageType, 0) )

				datFile.lastEffTexture = imageDataOffset

			# If this a stage file, check for particle effect textures
			if datFile.fileName.startswith( 'Gr' ) and 'map_texg' in datFile.stringDict.values():
				for offset, string in datFile.rootNodes:
					if string == 'map_texg':
						structStart = offset
						break

				# Get the entry count of the table (number of table pointers it contains), and the entries themselves
				mainTableEntryCount = toInt( datFile.data[structStart:structStart+4] )
				headerTableData = datFile.data[structStart+4:structStart+4+(mainTableEntryCount*4)]
				headerTablePointers = struct.unpack( '>' + str(mainTableEntryCount) + 'I', headerTableData )

				for pointer in headerTablePointers: # These are all relative to the start of this structure
					# Process the E2E header
					e2eHeaderOffset = structStart + pointer

					textureCount, imageType, _, width, height = struct.unpack( '>5I', datFile.data[e2eHeaderOffset:e2eHeaderOffset+0x14] )
					imageDataPointersStart = e2eHeaderOffset + 0x18
					imageDataPointersEnd = imageDataPointersStart + ( 4 * textureCount )
					imageDataPointerValues = struct.unpack( '>' + textureCount * 'I', datFile.data[imageDataPointersStart:imageDataPointersEnd] )

					if imageType in ( 8, 9, 10 ):
						paletteDataPointersEnd = imageDataPointersEnd + ( 4 * textureCount )
						paletteDataPointerValues = struct.unpack( '>' + textureCount * 'I', datFile.data[imageDataPointersEnd:paletteDataPointersEnd] )

					for i, offset in enumerate( imageDataPointerValues ):
						imageDataOffset = structStart + offset

						if imageType in ( 8, 9, 10 ):
							# Need to get the palette data's offset too. Its pointer is within a list following the image data pointer list
							paletteDataOffset = structStart + paletteDataPointerValues[i]
							texturesInfo.append( (imageDataOffset, -1, paletteDataOffset, -1, width, height, imageType, 0) )
						else:
							texturesInfo.append( (imageDataOffset, -1, -1, -1, width, height, imageType, 0) )
				
				datFile.lastEffTexture = imageDataOffset

			# Get the data section structure offsets, and separate out main structure references
			hI = datFile.headerInfo
			dataSectionStructureOffsets = set( datFile.structureOffsets ).difference( (-0x20, hI['rtStart'], hI['rtEnd'], hI['rootNodesEnd'], hI['stringTableStart']) )

			# Scan the data section by analyzing generic structures and looking for standard image data headers
			for structureOffset in dataSectionStructureOffsets:
				if structureOffset in imageDataOffsetsFound: continue # This is a structure of raw image data, which has already been added

				# Get the image data header struct's data.
				try: # Using a try block because the last structure offsets may raise an error (unable to get 0x18 bytes) which is fine
					structData = datFile.getData( structureOffset, 0x18 )
				except:
					continue

				# Unpack the values for this structure, assuming it's an image data header
				fieldValues = struct.unpack( '>IHHIIff', structData )
				imageDataOffset, width, height, imageType, mipmapFlag, minLOD, maxLOD = fieldValues

				if imageDataOffset in imageDataOffsetsFound: continue # Already added this one
				elif imageDataOffset not in dataSectionStructureOffsets: continue # Not a valid pointer/struct offset!

				# Check specific data values for known restrictions
				if width < 1 or height < 1: continue
				elif width > 1024 or height > 1024: continue
				elif imageType not in ( 0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 14 ): continue
				elif mipmapFlag > 1: continue
				elif minLOD > 10 or maxLOD > 10: continue
				elif minLOD > maxLOD: continue

				# Check for a minimum size on the image data block. Most image types require at least 0x20 bytes for even just a 1x1 pixel image
				childStructLength = datFile.getStructLength( imageDataOffset )
				if childStructLength == -1: pass # Can't trust this; unable to calculate the length (data must be after the string table)
				elif imageType == 6 and childStructLength < 0x40: continue
				elif childStructLength < 0x20: continue

				# Check if the child (image data) has any children (which it shouldn't)
				childFound = False
				for pointerOffset in datFile.pointerOffsets:
					if pointerOffset >= imageDataOffset:
						if pointerOffset < imageDataOffset + childStructLength: # Pointer found in data block
							childFound = True
						break
				if childFound: continue

				# Finally, check that the struct length makes sense (doing this last to avoid the performance hit)
				structLength = datFile.getStructLength( structureOffset ) # This length will include any padding too
				if structLength < 0x18 or structLength > 0x38: continue # 0x18 + 0x20

				texturesInfo.append( (imageDataOffset, structureOffset, -1, -1, width, height, imageType, int(maxLOD)) ) # Palette info will be found later
				imageDataOffsetsFound.add( imageDataOffset )

	except Exception as err:
		print 'Encountered an error during texture identification:'
		print err
	
	# toc = time.clock()
	# print 'image identification time:', toc - tic

	return texturesInfo


def scanDol():
	updateProgramStatus( 'Scanning File....' )

	# Update the GUI's basic file attributes.
	if globalDatFile.source == 'disc': 
		fileSize = Gui.isoFileTree.item( globalDatFile.path, 'values' )[3]
	else: 
		fileSize = os.path.getsize( Gui.datDestination.get().replace('"', '') )
	Gui.datFilesizeText.set( 'File Size:  ' + "{:,}".format(int(fileSize)) + ' bytes' )

	# Make sure this is a DOL for SSBM, check the version, and get the starting point for the textures
	# Check the DOL for a string of "Super Smash Bros. Melee" at specific places
	ssbmStringBytes = bytearray()
	ssbmStringBytes.extend( "Super Smash Bros. Melee" )
	if globalDatFile.data[0x3B78FB:0x3B7912] == ssbmStringBytes: # NTSC 1.02
		textureTableStart = 0x409d40
		totalTextures = 287
	elif globalDatFile.data[0x3B6C1B:0x3B6C32] == ssbmStringBytes: # NTSC 1.01
		textureTableStart = 0x409060
		totalTextures = 287
	elif globalDatFile.data[0x3B5A3B:0x3B5A52] == ssbmStringBytes: # NTSC 1.00
		textureTableStart = 0x407D80
		totalTextures = 287
	elif globalDatFile.data[0x3B75E3:0x3B75FA] == ssbmStringBytes: # PAL 1.00
		textureTableStart = 0x040C4E0
		totalTextures = 146
	else: # This DOL doesn't seem to be SSBM
		print 'Non SSBM DOL recieved.'
		return

	# There are no headers for these images, but they all have the same properties.
	width = 32
	height = 32
	imageType = 0
	imageDataLength = 0x200

	scanEndToEndImageData( textureTableStart, width, height, imageType, imageDataLength, totalTextures )


def scanEndToEndImageData( textureTableStart, width, height, imageType, imageDataLength, totalTextures ):
	# If this function is called while already processing a file, cancel the last instance of the loop. (The last function instance will then re-call this to scan the new file.)
	global scanningDat, stopAndScanNewDat
	texturesFound = 0
	texturesFiltered = 0
	scanningDat = True

	for i in xrange(0, totalTextures):
		imageDataOffset = textureTableStart + (0x200 * i)

		if stopAndScanNewDat:
			scanningDat = False
			stopAndScanNewDat = False
			clearDatTab()
			scanDat()
			return
		elif programClosing: 
			Gui.root.destroy()
			return

		elif not passesImageFilters(imageDataOffset, width, height, imageType): 
			texturesFiltered += 1
		else:
			try: # To create the full image.
				imageData = globalDatFile.getData( imageDataOffset, imageDataLength )

				newImg = tplDecoder( '', (width, height), imageType, None, imageData )
				newImg.deblockify() # Decodes the image data, to create an rgbaPixelArray.

				currentTex = Image.new( 'RGBA', (width, height) )
				currentTex.putdata( newImg.rgbaPixelArray )

				# Store the full ImageTk image so it's not garbage collected
				Gui.datTextureTree.fullTextureRenders[imageDataOffset] = ImageTk.PhotoImage( currentTex )

				# Create a 64x64 thumbnail/preview image, and store it so it's not garbage collected
				currentTex.thumbnail( (64, 64), Image.ANTIALIAS )
				Gui.datTextureTree.textureThumbnails[imageDataOffset] = ImageTk.PhotoImage( currentTex )
				texturesFound += 1
			except Exception as err:
				# Store the error image so it's not garbage collected
				Gui.datTextureTree.fullTextureRenders[imageDataOffset] = Gui.imageBank( 'noImage' )
				Gui.datTextureTree.textureThumbnails[imageDataOffset] = Gui.imageBank( 'noImage' )
				print 'Failed to decode texture at 0x{:X}; {}'.format( imageDataOffset, err )

			# Add this texture to the DAT Texture Tree tab.
			Gui.datTextureTree.insert( '', 'end', 										# '' = parent = root, 'end' = insert position
				iid=imageDataOffset, 												# Becomes a string once it's assigned
				image=Gui.datTextureTree.textureThumbnails[imageDataOffset], 	
				values=(
					uHex(imageDataOffset) + '\n('+uHex(imageDataLength)+')', 	# offset to image data, and data length
					(str(width)+' x '+str(height)), 								# width and height
					'_'+str(imageType)+' ('+imageFormats[imageType]+')' 			# the image type and format
				),
				tags=()
			)

			# Update the GUI.
			if texturesFound % 5 == 0:
				Gui.texturesFoundText.set( 'Textures Found:  ' + str(texturesFound) )
				Gui.texturesFilteredText.set( 'Filtered Out:  ' + str(texturesFiltered) )
				Gui.datTextureTree.update()

	scanningDat = False
	Gui.texturesFoundText.set( 'Textures Found:  ' + str(texturesFound) )
	Gui.texturesFilteredText.set( 'Filtered Out:  ' + str(texturesFiltered) )
	Gui.totalTextureSpaceText.set( "Total Texture Size:  {:,} b".format(imageDataLength*totalTextures) )


def passesImageFilters( imageDataOffset, width, height, imageType ):

	""" Used to pass or filter out textures displayed in the DAT Texture Tree tab when loading files.
		Accessed and controled by the main menu's "Settings -> Adjust Texture Filters" option. """

	aspectRatio = float(width) / height

	def comparisonPasses( subjectValue, comparator, limitingValue ): 
		if comparator == '>' and not (subjectValue > limitingValue): return False
		if comparator == '>=' and not (subjectValue >= limitingValue): return False
		if comparator == '=' and not (subjectValue == limitingValue): return False
		if comparator == '<' and not (subjectValue < limitingValue): return False
		if comparator == '<=' and not (subjectValue <= limitingValue): return False
		return True

	# For each setting, break the value into its respective components (comparator & filter value), and then run the appropriate comparison.
	widthComparator, widthValue = imageFilters['widthFilter']
	if widthValue != '' and not isNaN(int(widthValue)): 
		if not comparisonPasses( width, widthComparator, int(widthValue) ): return False
	heightComparator, heightValue = imageFilters['heightFilter']
	if heightValue != '' and not isNaN(int(heightValue)): 
		if not comparisonPasses( height, heightComparator, int(heightValue) ): return False
	aspectRatioComparator, aspectRatioValue = imageFilters['aspectRatioFilter']
	if aspectRatioValue != '':
		if ':' in aspectRatioValue:
			numerator, denomenator = aspectRatioValue.split(':')
			aspectRatioValue = float(numerator) / float(denomenator)
		elif '/' in aspectRatioValue:
			numerator, denomenator = aspectRatioValue.split('/')
			aspectRatioValue = float(numerator) / float(denomenator)
		else: aspectRatioValue = float(aspectRatioValue)

	if not isNaN(aspectRatioValue) and not comparisonPasses( aspectRatio, aspectRatioComparator, aspectRatioValue ): return False
	imageTypeComparator, imageTypeValue = imageFilters['imageTypeFilter']
	if imageTypeValue != '' and not isNaN(int(imageTypeValue)): 
		if not comparisonPasses( imageType, imageTypeComparator, int(imageTypeValue) ): return False
	offsetComparator, offsetValue = imageFilters['offsetFilter']
	if offsetValue.startswith('0x') and offsetValue != '' and not isNaN(int(offsetValue, 16)):
			if not comparisonPasses( imageDataOffset + 0x20, offsetComparator, int(offsetValue, 16) ): return False
	elif offsetValue != '' and not isNaN(int(offsetValue)): 
			if not comparisonPasses( imageDataOffset + 0x20, offsetComparator, int(offsetValue) ): return False

	return True


def parseTextureDetails( iid ):
	imageDataDetails, dimensions, imageType = Gui.datTextureTree.item( iid, 'values' )
	imageDataOffset = int( iid )
	imageDataLength = int( imageDataDetails.split('(')[1].replace(')', ''), 16 )
	width, height = [ int( dim.strip() ) for dim in dimensions.split('x') ]
	imageType = int( imageType.split()[0].replace('_', '') )

	return imageDataOffset, imageDataLength, width, height, imageType


def getMipmapLevel( iid ):
	if Gui.datTextureTree.exists( iid ) and 'mipmap' in Gui.datTextureTree.item( iid, 'tags' ):
		mipmapLevel = 0

		if Gui.datTextureTree.parent( iid ): # This item is a child of a parent mipmap texture

			for level in Gui.datTextureTree.get_children( Gui.datTextureTree.parent(iid) ):
				mipmapLevel += 1
				if level == iid: break

	else: mipmapLevel = -1

	return mipmapLevel


def getImageDataLength( width, height, imageType ): # Arguments should each be ints.
	byteMultiplyer = { # Defines the bytes required per pixel for each image type.
		0: .5, 1: 1, 2: 1, 3: 2, 4: 2, 5: 2, 6: 4, 8: .5, 9: 1, 10: 2, 14: .5 }
	blockDimensions = { # Defines the block width and height for each image type.
		0: (8,8), 1: (8,4), 2: (8,4), 3: (4,4), 4: (4,4), 5: (4,4), 6: (4,4), 8: (8,8), 9: (8,4), 10: (4,4), 14: (8,8) }

	# Calculate based on all encoded pixels (including those in unused block areas), not just the visible ones of the given dimensions.
	blockWidth, blockHeight = blockDimensions[imageType]
	trueWidth = math.ceil( float(width) / blockWidth ) * blockWidth
	trueHeight = math.ceil( float(height) / blockHeight ) * blockHeight

	return int( trueWidth * trueHeight * byteMultiplyer[imageType] ) # Result is in bytes.


def getPaletteInfo( datFile, imageDataOffset ):

	""" Doesn't get the palette data itself, but attempts to find/return information on it. There is hardcoded information for certain files, 
		which are checked first, followed by checks for effects files. Standard DAT/USD files are then checked using two different methods, 
		by looking through the structure hierarchy from the bottom upwards. The first method looks for a path from Image Headers to Texture 
		structures, in order to get the palette header's offset and other info. The second method (if the first fails), checks for a Image 
		Data Array structure, and then the parent Texture Animation Struct. From there, the palette header array structure and respective
		palette header for the target image can be found. 
		
		This returns a tuple of info in the form ( paletteDataOffset, paletteHeaderOffset, paletteLength, paletteType, paletteColorCount ) """

	# Handle special cases for certain files
	if (0x1E00, 'MemSnapIconData') in datFile.rootNodes: # The file is LbMcSnap.usd or LbMcSnap.dat (Memory card banner/icon file from SSB Melee)
		# There's only one palette that might be desired in here (no headers available).
		return 0x1C00, -1, 0x200, 2, 256

	elif (0x4E00, 'MemCardIconData') in datFile.rootNodes: # The file is LbMcGame.usd or LbMcGame.dat (Memory card banner/icon file from SSB Melee)
		return 0x4C00, -1, 0x200, 2, 256

	elif isEffectsFile( datFile ): # These have normal structuring as well as some unique table structuring
		imageDataStruct = datFile.getStruct( imageDataOffset )

		# The unique structuring should have already saved the palette info
		if imageDataStruct and imageDataStruct.paletteDataOffset != -1 and imageDataStruct.paletteHeaderOffset == -1:
			return ( imageDataStruct.paletteDataOffset, imageDataStruct.paletteHeaderOffset, 0x200, 2, 256 )

	elif datFile.fileName.startswith( 'Gr' ) and 'map_texg' in datFile.stringDict.values(): # These have normal structuring as well as some unique table structuring
		imageDataStruct = datFile.getStruct( imageDataOffset )

		# The unique structuring should have already saved the palette info
		if imageDataStruct and imageDataStruct.paletteDataOffset != -1 and imageDataStruct.paletteHeaderOffset == -1:
			return ( imageDataStruct.paletteDataOffset, imageDataStruct.paletteHeaderOffset, 0x20, 2, 16 )

	# Proceeding to check within standard DAT/USD files
	headerOffsets = datFile.getStruct( imageDataOffset ).getParents()
	paletteHeaderStruct = None

	for imageHeaderOffset in headerOffsets:
		imageDataHeader = datFile.initSpecificStruct( hsdStructures.ImageObjDesc, imageHeaderOffset, printWarnings=False )
		if not imageDataHeader: continue

		for headerParentOffset in imageDataHeader.getParents():
			# Test for a Texture Struct
			textureStruct = datFile.initSpecificStruct( hsdStructures.TextureObjDesc, headerParentOffset, printWarnings=False )
			
			if textureStruct:
				# Texture Struct Found; initialize the child palette header structure
				paletteHeaderOffset = textureStruct.getValues()[22]
				paletteHeaderStruct = datFile.initSpecificStruct( hsdStructures.PaletteObjDesc, paletteHeaderOffset, textureStruct.offset )
				break
			else:
				# Test for an Image Data Array structure
				imageHeaderArrayStruct = datFile.initSpecificStruct( hsdStructures.ImageHeaderArray, headerParentOffset, printWarnings=False )

				if imageHeaderArrayStruct:
					# Get the parent Texture Animation Struct, to get the palette header array offset
					texAnimStructOffset = imageHeaderArrayStruct.getAnyDataSectionParent()
					texAnimStruct = datFile.initSpecificStruct( hsdStructures.TexAnimDesc, texAnimStructOffset, printWarnings=False )

					if texAnimStruct:
						paletteIndex = imageHeaderArrayStruct.getValues().index( imageHeaderOffset )

						# Make sure there is a palette header array structure (there may not be one if a palette is shared!)
						if texAnimStruct.offset + 0x10 in datFile.pointerOffsets:
							# Palette header array struct present. Get the corresponding palette header offset and structure
							paletteHeaderArrayOffset = texAnimStruct.getValues()[4]
							paletteHeaderPointerOffset = paletteHeaderArrayOffset + ( paletteIndex * 4 )
							paletteHeaderOffset = struct.unpack( '>I', datFile.getData(paletteHeaderPointerOffset, 4) )[0] # Grabbing 4 bytes and unpacking them
							paletteHeaderStruct = datFile.initSpecificStruct( hsdStructures.PaletteObjDesc, paletteHeaderOffset, paletteHeaderArrayOffset )
						elif paletteIndex == 0: # The first texture should have a normal Texture struct as well, so just move on to that.
							continue
						else: # Must share a palette with the first texture
							# Get the image data structure for the first texture in the array
							imageDataHeader = datFile.initSpecificStruct( hsdStructures.ImageObjDesc, imageHeaderArrayStruct.values[0] )
							imageDataOffset = imageDataHeader.getValues()[0]
							imageDataStruct = datFile.initDataBlock( hsdStructures.ImageDataBlock, imageDataOffset, imageDataHeader.offset )

							# Check the image data's parents to get the other image data header (the one that leads to a Texture Struct)
							for headerOffset in imageDataStruct.getParents().difference( (imageDataHeader.offset,) ): # Excluding the image data header above
								imageDataHeader = datFile.initSpecificStruct( hsdStructures.ImageObjDesc, headerOffset, printWarnings=False )
								if not imageDataHeader: continue
								
								for headerParentOffset in imageDataHeader.getParents():
									textureStruct = datFile.initSpecificStruct( hsdStructures.TextureObjDesc, headerParentOffset, printWarnings=False )
									if not textureStruct: continue
									
									# Texture Struct Found; initialize the child palette header structure
									paletteHeaderOffset = textureStruct.getValues()[22]
									paletteHeaderStruct = datFile.initSpecificStruct( hsdStructures.PaletteObjDesc, paletteHeaderOffset, textureStruct.offset )
									break
								if paletteHeaderStruct: break
						break

		if paletteHeaderStruct: break

	if paletteHeaderStruct:
		paletteDataOffset, paletteType, _, colorCount = paletteHeaderStruct.getValues()
		paletteLength = datFile.getStructLength( paletteDataOffset )
		return ( paletteDataOffset, paletteHeaderStruct.offset, paletteLength, paletteType, colorCount )
	else:
		return ( -1, -1, None, None, None )


def getPaletteData( datFileObj, imageDataOffset=-1, paletteDataOffset=-1, imageData=None, imageType=-1 ):

	""" Gets palette data from the file, looking up palette info if needed. If image data is provided, it is checked 
		to determine how many colors are actually used (colorCount from the palette data header cannot be trusted). """

	# Get the offset of the palette data, if not provided
	if paletteDataOffset == -1:
		assert imageDataOffset != -1, 'Image data offset not provided to get palette data!'
		paletteDataOffset, _, paletteLength, paletteType, colorCount = getPaletteInfo( datFileObj, imageDataOffset )
	else:
		paletteLength = datFileObj.getStructLength( paletteDataOffset )
		paletteType = -1
		colorCount = -1

	if imageData:
		if imageType == 8: # Break up every byte into two 4-bit values
			paletteIndexArray = [ x for i in imageData for x in (i>>4, i&0b1111) ]
		elif imageType == 9: # Can just use the original bytearray (each entry is 1 byte)
			paletteIndexArray = imageData
		elif imageType == 10: # Combine half-word bytes
			paletteIndexArray = struct.unpack( '>{}H'.format(len(imageData)/2), imageData )
		else:
			raise Exception( 'Invalid image type given to getPaletteData: ' + str(imageType) )

		colorCount = max( paletteIndexArray ) + 1
		paletteData = datFileObj.getData( paletteDataOffset, colorCount * 2 ) # All palette types are two bytes per color
		
	else:
		# Without the image data, we can't really trust the color count, especially for some older texture hacks
		assert paletteLength, 'Invalid palette length to get palette data: ' + str(paletteLength)
		paletteData = datFileObj.getData( paletteDataOffset, paletteLength )

	return paletteData, paletteType


def renderTextureData( imageDataOffset, width, height, imageType, imageDataLength, allowImageDumping=True ):

	""" Decodes image data from the globally loaded DAT file at a given offset and creates an image out of it. This then
		stores/updates the full image and a preview/thumbnail image (so that they're not garbage collected) and displays it in the GUI.
		The image and its info is then displayed in the DAT Texture Tree tab's treeview (does not update the Dat Texture Tree subtabs).

		allowImageDumping is False when this function is used to 're-load' image data,
		(such as after importing a new texture, or modifying the palette of an existing one), 
		so that image modifications don't overwrite texture dumps. """

	#tic = time.clock()

	problemWithImage = False

	try:
		imageData = globalDatFile.getData( imageDataOffset, imageDataLength )

		if imageType == 8 or imageType == 9 or imageType == 10: # Gather info on the palette.
			paletteData, paletteType = getPaletteData( globalDatFile, imageDataOffset )
		else:
			paletteData = ''
			paletteType = None

		newImg = tplDecoder( '', (width, height), imageType, paletteType, imageData, paletteData )
		newImg.deblockify() # This decodes the image data, creating an rgbaPixelArray.

		# Create an image with the decoded data
		textureImage = Image.new( 'RGBA', (width, height) )
		textureImage.putdata( newImg.rgbaPixelArray )

	except Exception as errMessage:
		print 'Unable to make out a texture for data at', uHex(0x20+imageDataOffset)
		print errMessage 
		problemWithImage = True

	# toc = time.clock()
	# print 'time to decode image for', hex(0x20+imageDataOffset) + ':', toc-tic

	# Store the full image (or error image) so it's not garbage collected, and generate the preview thumbnail.
	if problemWithImage:
		# The error image is 64x64, so it doesn't need to be resized for the thumbnail.
		Gui.datTextureTree.fullTextureRenders[imageDataOffset] = Gui.imageBank( 'noImage' )
		Gui.datTextureTree.textureThumbnails[imageDataOffset] = Gui.imageBank( 'noImage' )
	else:
		if allowImageDumping and generalBoolSettings['dumpPNGs'].get():
			textureImage.save( buildTextureDumpPath(globalDatFile, imageDataOffset, imageType, '.png') )

		Gui.datTextureTree.fullTextureRenders[imageDataOffset] = ImageTk.PhotoImage( textureImage )
		textureImage.thumbnail( (64, 64), Image.ANTIALIAS )
		Gui.datTextureTree.textureThumbnails[imageDataOffset] = ImageTk.PhotoImage( textureImage )

	# If this item has already been added to the treeview, update the preview thumbnail of the texture.
	iid = str( imageDataOffset )
	if Gui.datTextureTree.exists( iid ):
		Gui.datTextureTree.item( iid, image=Gui.datTextureTree.textureThumbnails[imageDataOffset] )

	if not problemWithImage: return True
	else: return False


def decodeTextureData( textureProperties, datFileObj, resultQueue, dumpImage ):

	""" Only used when multi-process texture decoding is enabled.

		Decodes texture data from the globally loaded DAT file at a given offset and creates a viewable image. The finished image 
		is placed into a queue for rendering to the GUI. This is because this function will be run in a separate process for
		performance gains, however only the main thread may be allowed to do any GUI updates (or else there may be freezes).

		The dumpImage argument should be False when this function is used to 're-load' image data,
		(such as after importing a new texture, or modifying the palette of an existing one), so that image 
		modifications don't overwrite original texture dumps. Until the next time the program is opened, anyway. """

	try:
		#print 'processing', hex(0x20+imageDataOffset), 'with', multiprocessing.current_process().name
		# tic = time.clock()

		imageDataOffset, width, height, imageType, imageDataLength = textureProperties
		imageData = datFileObj.getData( imageDataOffset, imageDataLength )

		if imageType == 8 or imageType == 9 or imageType == 10: # Gather info on the palette.
			paletteData, paletteType = getPaletteData( datFileObj, imageDataOffset )
		else:
			paletteData = ''
			paletteType = None

		# print 'time to resolve palette:', time.clock() - tic
		# tic = time.clock()
		# print '\n\tbeginning decoding', hex(len(imageData)), 'data at offset', hex(imageDataOffset)

		newImg = tplDecoder( '', (width, height), imageType, paletteType, imageData, paletteData )
		newImg.deblockify() # This decodes the image data, creating an rgbaPixelArray.

		# from v5.3
		textureImage = Image.new( 'RGBA', (width, height) )
		textureImage.putdata( newImg.rgbaPixelArray )

		#textureImage = Image.new( 'RGBA', (width, height) )
		#byteStringData = ''.join([chr(pixel[0])+chr(pixel[1])+chr(pixel[2])+chr(pixel[3]) for pixel in newImg.rgbaPixelArray])
		#rawImageData = (c_ubyte * 4 * width * height).from_buffer_copy(byteStringData)
		#textureImage = Image.frombuffer( 'RGBA', (width, height), byteStringData, 'raw', 'RGBA', 0, 1 )
		#textureImage = Image.fromarray( newImg.rgbaPixelArray, 'RGBA' )

		#textureImage = Image.frombytes( 'RGBA', (width, height), bytes(newImg.decodedImage) )

		# toc = time.clock()
		# print 'time to decode image:   ', toc-tic, '       for', hex(0x20+imageDataOffset)
		# tic = time.clock()

		if dumpImage:
			try:
				textureImage.save( buildTextureDumpPath(datFileObj, imageDataOffset, imageType, '.png') )
			except Exception as err:
				print 'Unable to create texture dump:'
				print err

		# print 'time to dump texture:', time.clock()-tic

		# Add the result into the queue
		#if not shutdownEvent.is_set():
		resultQueue.put( (textureImage, imageDataOffset) )
		#root.event_generate( '<<message>>', when='mark' )

	except Exception as err:
		print 'Failure during image decoding:'
		print err

		resultQueue.put( (None, imageDataOffset) )


def getImageFileAsPNG( filepath ): # may be depricated
	if not os.path.exists( filepath ):
		return ( 'filepath for getImageFileAsPNG not found', 'noFileFound' )

	filename = os.path.split( filepath )[1]
	fileFormat = os.path.splitext( filename )[1].lower()
	
	with open( filepath, 'rb' ) as binaryFile:
		if fileFormat == '.tpl':
			status = 'formatSupported'

		elif fileFormat == '.png':
			# Get image attributes.
			# binaryFile.seek(16)
			# width = toInt( binaryFile.read(4) )
			# height = toInt( binaryFile.read(4) )
			# bitDepth = toInt( binaryFile.read(1) )
			# colorType = toInt( binaryFile.read(1) )

			# Get the image data.
			binaryFile.seek(0)
			imageHex = hexlify( binaryFile.read() ) # This would actually be a bytes string. might need to fix that
			status = 'dataObtained'

		else:
			imageHex = ''
			status = 'formatUnsupported' # Not a PNG or TPL.
	# File is closed for reading.
	
	if status != 'formatUnsupported' and fileFormat == '.tpl': # Not performed in the if-then above so that the file can first be closed.
		## Convert the image to TPL format.
		( exitCode, outputStream ) = cmdChannel( '"' + wimgtPath + '" copy "' + filepath + '" - -x .png' )

		if exitCode == 0:
			encodedStream = hexlify( outputStream )
			startOfData = encodedStream.find('89504e470d0a1a0a') ## 16 char PNG file ID.
			imageHex = encodedStream[startOfData:]
			status = 'dataObtained'
		else:
			status = 'failed wimgt conversion'
			imageHex = outputStream

	return ( status, imageHex )


def getImageFileAsTPL( filepath, originalTextureType ):
	# Check what formatting (image type) the texture should have in-game, and the current file format
	imageType = codecBase.parseFilename( os.path.basename( filepath ) )[0]
	fileFormat = os.path.splitext( filepath )[1].lower()

	if imageType == -1: imageType = originalTextureType

	imageHeader = ''
	imageData = ''
	paletteHeader = ''
	paletteData = ''
	
	with open( filepath.replace('\\', '/') , 'rb' ) as binaryFile:
		if fileFormat == '.tpl':
			# Get image attributes.
			binaryFile.seek( 0xC )
			imageHeaderAddress = toInt( binaryFile.read(4) )
			paletteHeaderOffset = toInt( binaryFile.read(4) )
			binaryFile.seek( paletteHeaderOffset )
			paletteEntries = hexlify( binaryFile.read(2) )
			binaryFile.seek( 4, 1 ) # Seek from the current location.
			paletteType = '0000' + hexlify( binaryFile.read(2) )
			binaryFile.seek( imageHeaderAddress )
			height = hexlify( binaryFile.read(2) )
			width = hexlify( binaryFile.read(2) )
			#imageType = hexlify( binaryFile.read(4) )
			#imageDataOffset = toInt( binaryFile.read(4) )

			binaryFile.seek( 4 )
			fileBinary = hexlify( binaryFile.read() )
			status = 'dataObtained'

		elif fileFormat == '.png':
			# Get image attributes.
			binaryFile.seek(16)
			width = hexlify( binaryFile.read(4) )[4:]
			height = hexlify( binaryFile.read(4) )[4:]
			bitDepth = toInt( binaryFile.read(1) )
			colorType = toInt( binaryFile.read(1) )
			if colorType == 3: # The image is palette based.
				pngBinary = hexlify( binaryFile.read() )
			status = 'formatSupported'

		else:
			status = 'formatUnsupported'
	
	# If the file is a PNG, convert it to TPL.
	if status != 'formatUnsupported' and fileFormat == '.png':		
		## Set the appropriate encoding.
		if imageType == 0: encoding='i4'
		elif imageType == 1: encoding='i8'
		elif imageType == 2: encoding='ia4'
		elif imageType == 3: encoding='ia8'
		elif imageType == 4: encoding='rgb565'
		elif imageType == 5: encoding='rgb5a3'
		elif imageType == 6: encoding='rgba32'
		elif imageType == 8: encoding='c4'
		elif imageType == 9: encoding='c8'
		elif imageType == 10: encoding='c14x2'
		elif imageType == 14: encoding='cmpr'
		else:
			return ( 'imageTypeNotFound', '', '', '', '' )

		# If the image uses a palette, check if it contains transparency. Start by checking the colorType. 
		# Then, if an alpha channel is not found, fall back on scanning the palette for magenta. 
		# (The standard check on the PNG's colorType will not reveal whether the texture should have 
		# transparency for a particular palette index. And if a palette is present, then there cannot be 
		# an alpha channel.) Finally, if a palette is found, also check for the tRNS ancillary transparency chunk.

		dataWithAdHocPalette = False
		if imageType == 8 or imageType == 9 or imageType == 10:
			transparencyDetected = False
			if colorType == 4 or colorType == 6: ## The image has an alpha channel.
				transparencyDetected = True
				dataWithAdHocPalette = True ## Mark that the palette will be created on-the-fly.
			elif colorType == 3:
				## The image has a palette. Transparency will be evaluated by scanning for magenta.
				startOfPalette = pngBinary.find('504c5445') ## Search for palette by the Chunk Type, PLTE.
				if startOfPalette != -1:
					paletteLength = int( int(pngBinary[startOfPalette-8:startOfPalette], 16)*2 ) ## Palette length, in nibbles.
					##paletteEntries = paletteByteLength/3
					palette = pngBinary[startOfPalette+8:startOfPalette+8+paletteLength]

					## Iterate over the palette entries, looking for magenta ('ff00ff')
					for i in xrange(0, paletteLength, 6): ## Uses a step of 6, which encompasses one RGB palette entry.
						if palette[i:i+6] == 'ff00ff':
							transparencyDetected = True
							break
					if not transparencyDetected:
						## One last check for transparency....
						if pngBinary.find('74524e53') != -1: ## Search for ancillary transparency chunk (Chunk Type tRNS).
							transparencyDetected = True
				else: ## Image should have a palette, but one was not found.
					return ( 'formatUnsupported', '', '', '', '' )

			else:
				## colorType is 0 or 2 (i.e. no palette or alpha channel detected). Assume correct.
				dataWithAdHocPalette = True ## Mark that the palette will be created on-the-fly.

			if transparencyDetected: 
				encoding = encoding + '.P-RGB5A3'
				paletteType = '00000002'
			else: 
				encoding = encoding + '.P-RGB565'
				paletteType = '00000001'

		## With the collected image info, convert the image to TPL format.
		( exitCode, outputStream ) = cmdChannel( '"' + wimgtPath + '" copy "' + filepath + '" - -x tpl.' + encoding )
		if exitCode == 0:
			fileBinary = hexlify( outputStream ).split('0020af30')[1]
			if dataWithAdHocPalette: status = 'dataWithAdHocPalette'
			else: status = 'dataObtained'
		else: return ( exitCode, outputStream, '', '', '' )

	## At this point, the file's binary should be standardized as a hex array, while missing the first 4 bytes.
	if status == 'dataObtained' or status == 'dataWithAdHocPalette':
		if imageType == 8 or imageType == 9 or imageType == 10:
			## Image has a palette that needs moving.
			## Since the file identifier has been removed, 4 bytes need to be subtracted from any offset relative to the file beginning.
			## Indexing of the hex string is per nibble, not per byte, so intergers for iteration need to be doubled.
			imageHeaderOffset = int(fileBinary[16:24], 16) ## Hex string to integer conversion of 4 bytes.
			imageHeaderAddress = (imageHeaderOffset - 4)*2
			## Separate out the palette, change the magenta to transparent, and change lime green to the drop-shadow color.
			paletteData = fileBinary[56:imageHeaderAddress]
			paletteLength = len(paletteData)
			paletteEntries = paletteLength/4
			for i in xrange(paletteLength, 0, -4): ## Iterate backwards through the palette data, seeking magenta.
				if paletteData[i-4:i] == 'fc1f':
					paletteData = paletteData[:i-4] + '0000' + paletteData[i:] ## Replace magenta with full transparency.
					break
			for i in xrange(paletteLength, 0, -4): ## Iterate backwards through the palette data, seeking lime green.
				if paletteData[i-4:i] == '83e0':
					paletteData = paletteData[:i-4] + '3000' + paletteData[i:] ## Replace lime green with the drop-shadow.
					break
			imageDataOffset = int(fileBinary[imageHeaderAddress + 16:imageHeaderAddress + 24], 16)
			imageData = fileBinary[(imageDataOffset - 4)*2:] ## 0x260 = 608, 608 - the offset of 8 lost with the file identifier = 600.
			paletteHeader = paletteType + '00000000' + "{0:0{1}X}".format(paletteEntries, 4) # This is in the format that would appear in a file, but without the paletteDataOffset.
		else:
			## No palette. Return just the image data.
			imageData = fileBinary[120:] ## 0x40 -> 64. 2(64 - 4) = 120

		imageHeader = width + height + "{0:0{1}X}".format(imageType, 8) # This is in the format that would appear in a file, but without the imageDataOffset.
	
	## The returned imageData will be a bytearray, except for cases with conversion errors, in which case it will be a string.
	return (status, imageHeader, imageData, paletteHeader, paletteData) # All returned values are strings.


def buildTextureDumpPath( datFileObj, imageDataOffset, imageType, extension ):

	""" Creates a save/destination path for new image files being dumped from the program. 
		Only used for dumping images from a globally loaded DAT file (not banners). """

	sourceDatFilename = os.path.basename( datFileObj.path ).split('_')[-1]
	newFileName = sourceDatFilename + '_' + uHex(imageDataOffset + 0x20) + '_' + str(imageType)
	
	# Get the Game ID if this file was loaded from a disc.
	if datFileObj.source == 'disc' and globalDiscDetails['gameId'] != '':
		# Means an ISO has been loaded, and (looking at the file path) the current dat is not from an outside standalone file.
		gameID = globalDiscDetails['gameId']
	else: gameID = 'No Associated Disc'

	# Construct the destination file path, and create the folders if they don't already exist.
	destinationFolder = texDumpsFolder + '\\' + gameID + '\\' + sourceDatFilename + '\\'
	if not os.path.exists( destinationFolder ): os.makedirs( destinationFolder )

	return destinationFolder + newFileName + extension


def updateEntryHex( event, widget=None ):

	""" Updates hex data in a hex entry field to the currently loaded DAT file. 
		Able to update multiple locations in the file if widget.offset is a list of offsets. """

	# Get the entry widget containing details on this edit
	if not widget:
		widget = event.widget

	# Validate the input
	newHex = widget.get().zfill( widget.byteLength * 2 ).upper() # Pads the string with zeroes to the left if not enough characters
	if not validHex( newHex ):
		msg( 'The entered text is not valid hexadecimal!' )
		return

	# Confirm whether updating is necessary by checking if this is actually new data for any of the offset locations
	if type( widget.offsets ) == list:
		for offset in widget.offsets:
			currentFileHex = hexlify( globalDatFile.getData(offset, widget.byteLength) ).upper()
			if currentFileHex != newHex: # Found a difference
				break
		else: # The loop above didn't break; no change found
			return # No change to be updated
	else: # The offsets attribute is just a single value (the usual case)
		currentFileHex = hexlify( globalDatFile.getData(widget.offsets, widget.byteLength) ).upper()
		if currentFileHex == newHex:
			return # No change to be updated

	# Get the data as a bytearray, and check for other GUI compoenents that may need to be updated
	newData = bytearray.fromhex( newHex )
	valueEntryWidget = getattr( widget, 'valueEntryWidget', None )
	formatting = getattr( widget, 'formatting', None )
	decodedValue = None

	if len( newData ) != widget.byteLength: # Thanks to the zfill above, this should only happen if the hex entry is too long
		msg( 'The new value must be ' + str( widget.byteLength ) + ' characters long.' )
		return
	if valueEntryWidget and formatting:
		# Check that the appropriate value can be decoded from this hex (if formatting is available)
		try:
			decodedValue = struct.unpack( '>' + formatting, newData )
		except Exception as err:
			# Construct and display an error message for the user
			dataTypes = { 	'?': 'a boolean', 'b': 'a signed character', 'B': 'an unsigned character', 	# 1-byte
							'h': 'a signed short (halfword)', 'H': 'an unsigned short',				# 2-bytes
							'i': 'a signed integer', 'I': 'an unsigned integer', 'f': 'a float' } # 4-bytes
			if formatting in dataTypes:
				expectedLength = struct.calcsize( formatting )
				msg( 'The entered value is invalid for {} value (should be {} byte(s)).'.format( dataTypes[formatting], expectedLength ) )
			else: # I tried
				msg( 'The entered value is invalid.' )
			print err
			return

	# Change the background color of the widget, to show that changes have been made to it and are pending saving.
	widget.configure( background='#faa' )

	# If this entry has a color swatch associated with it, redraw it.
	colorSwatchWidget = getattr( widget, 'colorSwatch', None )
	if colorSwatchWidget: 
		#print 'recreating color swatch image with', newHex
		widget.colorSwatch.renderCircle( newHex )

	# Add the widget to a list, to keep track of what widgets need to have their background restored to white when saving.
	global editedDatEntries
	editedDatEntries.append( widget )

	# Update the hex shown in the widget (in case the user-entered value was zfilled; i.e. was not long enough)
	widget.delete( 0, 'end' )
	widget.insert( 0, newHex )

	# Update the data shown in the neighboring, decoded value widget
	if decodedValue:
		valueEntryWidget.delete( 0, 'end' )
		valueEntryWidget.insert( 0, decodedValue )
		valueEntryWidget.configure( background='#faa' )
		editedDatEntries.append( valueEntryWidget )

	# Replace the data in the file for each location
	updateName = widget.updateName.replace( '\n', ' ' )
	descriptionOfChange = updateName + ' modified in ' + globalDatFile.fileName
	if type( widget.offsets ) == list:
		for offset in widget.offsets:
			globalDatFile.updateData( offset, newData, descriptionOfChange )
	else: # The offsets attribute is just a single value (the usual case)
		globalDatFile.updateData( widget.offsets, newData, descriptionOfChange )

	updateProgramStatus( updateName + ' Updated' )


def updateEntryValue( event ):

	""" Formats a value in an entry field and updates it into the currently loaded DAT file. 
		Able to update multiple locations in the file if widget.offset is a list of offsets. """

	if event.__class__ == HexEditDropdown:
		widget = event
	else:
		widget = event.widget

	# Validate the entered value by making sure it can be correctly encoded
	try:
		formatting = widget.formatting

		if formatting == 'f':
			newHex = hexlify( struct.pack( '>f', float(widget.get()) ) ).upper()
		else:
			newHex = hexlify( struct.pack( '>' + formatting, int(widget.get()) ) ).upper()
	except Exception as err:
		# Construct and display an error message for the user
		dataTypes = { 	'?': 'a boolean', 'b': 'a signed character', 'B': 'an unsigned character', 	# 1-byte
						'h': 'a signed short (halfword)', 'H': 'an unsigned short',				# 2-bytes
						'i': 'a signed integer', 'I': 'an unsigned integer', 'f': 'a float' } # 4-bytes
		if formatting in dataTypes:
			msg( 'The entered value is invalid for {} value.'.format( dataTypes[formatting] ) )
		else: # I tried
			msg( 'The entered value is invalid.' )
		print err
		return

	# Confirm whether updating is necessary by checking if this is actually new data for any of the offset locations
	if type( widget.offsets ) == list:
		for offset in widget.offsets:
			currentFileHex = hexlify( globalDatFile.getData(offset, widget.byteLength) ).upper()
			if currentFileHex != newHex: # Found a difference
				break
		else: # The loop above didn't break; no change found
			return # No change to be updated
	else: # The offsets attribute is just a single value (the usual case)
		currentFileHex = hexlify( globalDatFile.getData(widget.offsets, widget.byteLength) ).upper()
		if currentFileHex == newHex:
			return # No change to be updated

	# Change the background color of the widget, to show that changes have been made to it and are pending saving.
	if event.__class__ == HexEditDropdown:
		widget.configure( style='Edited.TMenubutton' )
	else:
		widget.configure( background='#faa' )

	# Add the widget to a list, to keep track of what widgets need to have their background restored to white when saving.
	global editedDatEntries
	editedDatEntries.append( widget )

	# Update the data shown in the neiboring widget
	hexEntryWidget = getattr( widget, 'hexEntryWidget', None )
	if hexEntryWidget:
		hexEntryWidget.delete( 0, 'end' )
		hexEntryWidget.insert( 0, newHex )
		hexEntryWidget.configure( background='#faa' )
		editedDatEntries.append( hexEntryWidget )

	# Replace the data in the file for each location
	newData = bytearray.fromhex( newHex )
	updateName = widget.updateName.replace( '\n', ' ' )
	descriptionOfChange = updateName + ' modified in ' + globalDatFile.fileName
	if type( widget.offsets ) == list:
		for offset in widget.offsets:
			globalDatFile.updateData( offset, newData, descriptionOfChange )
	else: # The offsets attribute is just a single value (the usual case)
		globalDatFile.updateData( widget.offsets, newData, descriptionOfChange )

	updateProgramStatus( updateName + ' Updated' )


def updateDiscDetails( event ):
	offset = event.widget.offset # In this case, these ARE counting the file header
	maxLength = event.widget.maxByteLength
	targetFile = event.widget.targetFile # Defines the file this disc detail resides in. Will be a string of either 'opening.bnr' or 'boot.bin'

	# Return if the Shift key was held while pressing Enter (indicating the user wants a line break).
	modifierKeysState = event.state # An int. Check individual bits for mod key status'; http://infohost.nmt.edu/tcc/help/pubs/tkinter/web/event-handlers.html
	shiftDetected = (modifierKeysState & 0x1) != 0 # Checks the first bit of the modifiers
	if shiftDetected: return # Not using "break" on this one in order to allow event propagation

	# Determine what encoding to use for saving text
	if Gui.countryCode.get() == 'us': encoding = 'latin_1' # Decode assuming English or other European countries
	else: encoding = 'shift_jis' # The country code is 'jp', for Japanese.

	# Get the currently entered text as hex
	if event.widget.winfo_class() == 'TEntry' or event.widget.winfo_class() == 'Entry':
		inputBytes = event.widget.get().encode( encoding )
	else: inputBytes = event.widget.get( '1.0', 'end' )[:-1].encode( encoding ) # "[:-1]" ignores trailing line break
	newStringHex = hexlify( inputBytes )

	# Cancel if no banner file appears to be loaded (which means there's no disc with a boot.bin either).
	if not globalBannerFile: return 'break'

	# Get the data for the target file (Could be for boot.bin or opening.bnr)
	if targetFile == 'opening.bnr':
		targetFileData = globalBannerFile.data
	else: # Updating to disc.
		targetFileIid = scanDiscForFile( targetFile )
		if not targetFileIid:
			msg( targetFile + ' could not be found in the disc!' )
			return 'break'
		_, entity, isoOffset, fileSize, isoPath, _, _ = Gui.isoFileTree.item( targetFileIid, 'values' )
		targetFileData = getFileDataFromDiscTreeAsBytes( targetFileIid )

	# Get the hex string of the current value/field in the file
	currentHex = hexlify( targetFileData[offset:offset+maxLength] )

	# Pad the end of the input string with empty space (up to the max string length), to ensure any other text in the file will be erased
	newPaddedStringHex = newStringHex + ( '0' * (maxLength * 2 - len(newStringHex)) )

	# Check if the value is different from what is already saved.
	if currentHex != newPaddedStringHex:
		updateName = event.widget.updateName

		if updateName == 'Game ID' and len( newStringHex ) != maxLength * 2: 
			msg( 'The new value must be ' + str(maxLength) + ' characters long.' )
		elif len( newStringHex ) > maxLength * 2: 
			msg( 'The text must be less than ' + str(maxLength) + ' characters long.' )
		else:
			# Change the background color of the widget, to show that changes have been made to it and are pending saving.
			event.widget.configure( background="#faa" )

			# Add the widget to a list, to keep track of what widgets need to have their background restored to white when saving.
			editedBannerEntries.append( event.widget )

			if targetFile == 'opening.bnr':
				descriptionOfChange = updateName + ' modified in ' + globalBannerFile.fileName
				globalBannerFile.updateData( offset, bytearray.fromhex( newPaddedStringHex ), descriptionOfChange )
			else:
				global unsavedDiscChanges
				targetFileData[offset:offset+maxLength] = bytearray.fromhex( newPaddedStringHex )
				Gui.isoFileTree.item( targetFileIid, values=('Disc details updated', entity, isoOffset, fileSize, isoPath, 'ram', hexlify(targetFileData)), tags='changed' )
				unsavedDiscChanges.append( updateName + ' updated.' )

			updateProgramStatus( updateName + ' Updated' )

	return 'break' # Prevents the 'Return' keystroke that called this from propagating to the widget and creating a line break


def onTextureTreeSelect( event, iid='' ):
	# Ensure there is an iid, or do nothing
	if not iid: 
		iid = Gui.datTextureTree.selection()
		if not iid: return

	iid = iid[-1] # Selects the lowest position item selected in the treeview if multiple items are selected.
	currentTab = Gui.root.nametowidget( Gui.imageManipTabs.select() )

	# Update the main display with the texture's stored image.
	drawTextureToMainDisplay( iid )

	# Collect info on the texture
	imageDataOffset, imageDataLength, width, height, imageType = parseTextureDetails( iid )
	imageDataStruct = globalDatFile.structs.get( imageDataOffset )
	if imageDataStruct:
		imageDataHeaderOffsets = imageDataStruct.getParents()

	# Determine whether to enable and update the Palette tab.
	if imageType == 8 or imageType == 9 or imageType == 10:
		# Enable the palette tab and prepare the data displayed on it.
		Gui.imageManipTabs.tab( 1, state='normal' )
		populatePaletteTab( int(iid), imageDataLength, imageType )
	else:
		# No palette for this texture. Check the currently viewed tab, and if it's the Palette tab, switch to the Image tab.
		if currentTab == Gui.palettePane:
			Gui.imageManipTabs.select( Gui.textureTreeImagePane )
		Gui.imageManipTabs.tab( Gui.palettePane, state='disabled' )

	wraplength = Gui.imageManipTabs.winfo_width() - 20	
	lackOfUsefulStructsDescription = ''
	lastEffTextureOffset = getattr( globalDatFile, 'lastEffTexture', -1 ) # Only relevant with effects files and some stages

	# Check if this is a file that doesn't have image data headers :(
	if (0x1E00, 'MemSnapIconData') in globalDatFile.rootNodes: # The file is LbMcSnap.usd or LbMcSnap.dat (Memory card banner/icon file from SSB Melee)
		lackOfUsefulStructsDescription = 'This file has no known image data headers, or other structures to modify.'

	elif (0x4E00, 'MemCardIconData') in globalDatFile.rootNodes: # The file is LbMcGame.usd or LbMcGame.dat (Memory card banner/icon file from SSB Melee)
		lackOfUsefulStructsDescription = 'This file has no known image data headers, or other structures to modify.'

	elif (0, 'SIS_MenuData') in globalDatFile.rootNodes: # SdMenu.dat/.usd
		lackOfUsefulStructsDescription = 'This file has no known image data headers, or other structures to modify.'

	elif imageDataOffset <= lastEffTextureOffset:
		# e2eHeaderOffset = imageDataStruct.imageHeaderOffset
		# textureCount = struct.unpack( '>I', globalDatFile.getData(e2eHeaderOffset, 4) )[0]

		lackOfUsefulStructsDescription = ( 'Effects files and some stages have unique structuring for some textures, like this one, '
										   'which do not have a typical image data header, texture object, or other common structures.' )
		# if textureCount == 1:
		# 	lackOfUsefulStructsDescription += ' This texture is not grouped with any other textures,'
		# elif textureCount == 2:
		# 	lackOfUsefulStructsDescription += ' This texture is grouped with 1 other texture,'
		# else:
		# 	lackOfUsefulStructsDescription += ' This texture is grouped with {} other textures,'.format( textureCount )
		# lackOfUsefulStructsDescription += ' with an E2E header at 0x{:X}.'.format( 0x20+e2eHeaderOffset )

	elif not imageDataStruct: # Make sure an image data struct exists to check if this might be something like a DOL texture
		lackOfUsefulStructsDescription = (  'There are no image data headers or other structures associated '
											'with this texture. These are stored end-to-end in this file with '
											'other similar textures.' )

	elif not imageDataHeaderOffsets:
		lackOfUsefulStructsDescription = 'This file has no known image data headers, or other structures to modify.'

	Gui.texturePropertiesPane.clear()
	Gui.texturePropertiesPane.flagWidgets = [] # Useful for the Flag Decoder to more easily find widgets that need updating

	# If the following string has something, there isn't much customization to be done for this texture
	if lackOfUsefulStructsDescription:
		# Disable the model parts tab, and if on that tab, switch to the Image tab.
		if currentTab == Gui.modelPropertiesPane:
			Gui.imageManipTabs.select( Gui.textureTreeImagePane )
		Gui.imageManipTabs.tab( Gui.modelPropertiesPane, state='disabled' )
		
		# Add some info to the texture properties tab
		Gui.imageManipTabs.tab( Gui.texturePropertiesPane, state='normal' )
		ttk.Label( Gui.texturePropertiesPane.interior, text=lackOfUsefulStructsDescription, wraplength=wraplength ).pack( pady=30 )

		return # Nothing more to say about this texture

	# Enable and update the Model tab
	Gui.imageManipTabs.tab( Gui.modelPropertiesPane, state='normal' )
	populateModelTab( imageDataHeaderOffsets, wraplength )

	# Enable and update the Properties tab
	Gui.imageManipTabs.tab( Gui.texturePropertiesPane, state='normal' )
	populateTexPropertiesTab( wraplength, width, height, imageType )


def populateModelTab( imageDataHeaderOffsets, wraplength ):
	modelPane = Gui.modelPropertiesPane.interior
	vertPadding = 10

	# Clear the current contents
	Gui.modelPropertiesPane.clear()

	modelPane.imageDataHeaders = []
	modelPane.nonImageDataHeaders = [] # Not expected
	modelPane.textureStructs = [] # Direct model attachments
	modelPane.headerArrayStructs = [] # Used for animations
	modelPane.unexpectedStructs = []

	# Double-check that all of the parents are actually image data headers, and get grandparent structs
	for imageHeaderOffset in imageDataHeaderOffsets: # This should exclude any root/reference node parents (such as a label)
		headerStruct = globalDatFile.initSpecificStruct( hsdStructures.ImageObjDesc, imageHeaderOffset )

		if headerStruct:
			modelPane.imageDataHeaders.append( headerStruct )

			# Check the grandparent structs; expected to be Texture Structs or Image Data Header Arrays
			for grandparentOffset in headerStruct.getParents():
				texStruct = globalDatFile.initSpecificStruct( hsdStructures.TextureObjDesc, grandparentOffset, printWarnings=False )

				# Try getting or initializing a Texture Struct
				if texStruct:
					modelPane.textureStructs.append( texStruct )
				else:
					arrayStruct = globalDatFile.initSpecificStruct( hsdStructures.ImageHeaderArray, grandparentOffset, printWarnings=False )
				
					# Try getting or initializing an Image Header Array Struct
					if arrayStruct:
						modelPane.headerArrayStructs.append( arrayStruct )
					else:
						# Initialize a general struct
						modelPane.unexpectedStructs.append( globalDatFile.getStruct( grandparentOffset ) )
		else:
			# Attempt to initialize it in a generalized way (attempts to identify; returns a general struct if unable)
			modelPane.nonImageDataHeaders.append( globalDatFile.getStruct(imageHeaderOffset) )

	# Add a label for image data headers count
	if len( modelPane.imageDataHeaders ) == 1: # todo: make searching work for multiple offsets
		headerCountFrame = ttk.Frame( modelPane )
		ttk.Label( headerCountFrame, text='Model Attachments (Image Data Headers):  {}'.format(len(modelPane.imageDataHeaders)), wraplength=wraplength ).pack( side='left' )
		PointerLink( headerCountFrame, modelPane.imageDataHeaders[0].offset ).pack( side='right', padx=5 )
		headerCountFrame.pack( pady=(vertPadding*2, 0) )
	else:
		ttk.Label( modelPane, text='Model Attachments (Image Data Headers):  {}'.format(len(modelPane.imageDataHeaders)), wraplength=wraplength ).pack( pady=(vertPadding*2, 0) )

	# Add a notice of non image data header structs, if any.
	if modelPane.nonImageDataHeaders:
		print 'Non-Image Data Header detected as image data block parent!'
		if len( modelPane.nonImageDataHeaders ) == 1:
			nonImageDataHeadersText = '1 non-image data header detected:  ' + modelPane.nonImageDataHeaders[0].name
		else:
			structNamesString = grammarfyList( [structure.name for structure in modelPane.nonImageDataHeaders] )
			nonImageDataHeadersText = '{} non-image data headers detected:  {}'.format( len(modelPane.nonImageDataHeaders), structNamesString )
		ttk.Label( modelPane, text=nonImageDataHeadersText, wraplength=wraplength ).pack( pady=(vertPadding, 0) )

	# Add details for Texture Struct or Material Struct attachments
	if len( modelPane.textureStructs ) == 1:
		textStructsText = 'Associated with 1 Texture Struct.'
	else:
		textStructsText = 'Associated with {} Texture Structs.'.format( len(modelPane.textureStructs) )
	ttk.Label( modelPane, text=textStructsText, wraplength=wraplength ).pack( pady=(vertPadding, 0) )
	if len( modelPane.headerArrayStructs ) == 1:
		arrayStructsText = 'Associated with 1 Material Animation.'
	else:
		arrayStructsText = 'Associated with {} Material Animations.'.format( len(modelPane.headerArrayStructs) )
	ttk.Label( modelPane, text=arrayStructsText, wraplength=wraplength ).pack( pady=(vertPadding, 0) )

	if modelPane.unexpectedStructs:
		unexpectedStructsText = 'Unexpected Grandparent Structs: ' + grammarfyList( [structure.name for structure in modelPane.nonImageDataHeaders] )
		ttk.Label( modelPane, text=unexpectedStructsText, wraplength=wraplength ).pack( pady=(vertPadding, 0) )
		
	ttk.Separator( modelPane, orient='horizontal' ).pack( fill='x', padx=24, pady=(vertPadding*2, vertPadding) )

	# Get the associated material structs and display objects
	modelPane.materialStructs = []
	modelPane.displayObjects = []
	for texStruct in modelPane.textureStructs:
		for materialStructOffset in texStruct.getParents():
			materialStruct = globalDatFile.initSpecificStruct( hsdStructures.MaterialObjDesc, materialStructOffset )

			if materialStruct:
				modelPane.materialStructs.append( materialStruct )

				for displayObjOffset in materialStruct.getParents():
					displayObject = globalDatFile.initSpecificStruct( hsdStructures.DisplayObjDesc, displayObjOffset )

					if displayObject: 
						modelPane.displayObjects.append( displayObject )

	# Display controls to adjust this texture's model transparency
	# Set up the transparency control panel and initialize the control variables
	transparencyPane = ttk.Frame( modelPane )
	jointHidden = Tk.BooleanVar()
	displayListDisabled = Tk.BooleanVar() # Whether or not display list length has been set to 0

	modelPane.hideJointChkBtn = ttk.Checkbutton( transparencyPane, text='Disable Joint Rendering', variable=jointHidden, command=toggleHideJoint )
	modelPane.hideJointChkBtn.var = jointHidden
	modelPane.hideJointChkBtn.grid( column=0, row=0, sticky='w', columnspan=3 )
	modelPane.polyDisableChkBtn = ttk.Checkbutton( transparencyPane, text='Disable Polygon (Display List) Rendering', variable=displayListDisabled, command=toggleDisplayListRendering )
	modelPane.polyDisableChkBtn.var = displayListDisabled
	modelPane.polyDisableChkBtn.grid( column=0, row=1, sticky='w', columnspan=3 )
	ttk.Label( transparencyPane, text='Transparency Control:' ).grid( column=0, row=2, sticky='w', columnspan=3, padx=15, pady=(3, 4) )
	opacityValidationRegistration = Gui.root.register( opacityEntryUpdated )
	modelPane.opacityEntry = ttk.Entry( transparencyPane, width=7, justify='center', validate='key', validatecommand=(opacityValidationRegistration, '%P') )
	modelPane.opacityEntry.grid( column=0, row=3 )
	modelPane.opacityBtn = ttk.Button( transparencyPane, text='Set', command=setModelTransparencyLevel, width=4 )
	modelPane.opacityBtn.grid( column=1, row=3, padx=4 )
	modelPane.opacityScale = ttk.Scale( transparencyPane, from_=0, to=10, command=opacityScaleUpdated )
	modelPane.opacityScale.grid( column=2, row=3, sticky='we' )

	transparencyPane.pack( pady=(vertPadding, 0), expand=True, fill='x', padx=20 )

	transparencyPane.columnconfigure( 0, weight=0 )
	transparencyPane.columnconfigure( 1, weight=0 )
	transparencyPane.columnconfigure( 2, weight=1 )

	# Add a help button for texture/model disablement and transparency
	helpText = ( 'Disabling Joint Rendering will set the "Hidden" flag (bit 4) for all of the lowest-level Joint Structures '
				 "connected to the selected texture (parents to this texture's Display Object(s)). That will be just "
				 "one particular Joint Struct in most cases, however that may be the parent for multiple parts of the model. "
				 "To have finer control over which model parts are disabled, consider the Disable Polygon Rendering option."
				 "\n\nDisabling Polygon Rendering is achieved by setting the display list data stream size to 0 "
				 """(i.e. each associated Polygon Objects' "Display List Length"/"Display List Blocks" value). This is """
				 "done for each Polygon Object of each Display Object associated with this texture. For finer control, use "
				 'the Structural Analysis tab. There, you can even experiment with reducing the length of the list '
				 'to some other value between 0 and the original value, to render or hide different polygon groups.'
				 '\n\nTransparency Control makes the entire model part that this texture is attached to partially transparent. '
				 'This uses the value found in the Material Colors Struct by the same name, while setting multiple flags '
				 "within parenting structures. The flags set are 'Render No Z-Update' and 'Render XLU' of the Material Structs "
				 "(bits 29 and 30, respectfully), as well as 'XLU' and 'Root XLU' of the Joint Struct (bits 19 and 29). " )
	helpBtn = ttk.Label( transparencyPane, text='?', foreground='#445', cursor='hand2' )
	helpBtn.place( relx=1, x=-17, y=0 )
	helpBtn.bind( '<1>', lambda e, message=helpText: msg(message, 'Disabling Rendering and Transparency') )

	# Add widgets for Material Color editing
	ttk.Separator( modelPane, orient='horizontal' ).pack( fill='x', padx=24, pady=(vertPadding*2, vertPadding) )
	ttk.Label( modelPane, text='Material Colors:' ).pack( pady=(vertPadding, 0) )

	colorsPane = ttk.Frame( modelPane )

	# Row 1; Diffusion and Ambience
	ttk.Label( colorsPane, text='Diffusion:' ).grid( column=0, row=0, sticky='e' )
	diffusionEntry = HexEditEntry( colorsPane, -1, 4, 'I', 'Diffusion' ) # Data offset (the -1) will be updated below
	diffusionEntry.grid( column=1, row=0, padx=6 )
	ttk.Label( colorsPane, text='Ambience:' ).grid( column=3, row=0, sticky='e' )
	ambienceEntry = HexEditEntry( colorsPane, -1, 4, 'I', 'Ambience' ) # Data offset (the -1) will be updated below
	ambienceEntry.grid( column=4, row=0, padx=6 )

	# Row 2; Specular Highlights and Shininess
	ttk.Label( colorsPane, text='Highlights:' ).grid( column=0, row=1, sticky='e', padx=(12, 0) )
	highlightsEntry = HexEditEntry( colorsPane, -1, 4, 'I', 'Specular Highlights' ) # Data offset (the -1) will be updated below
	highlightsEntry.grid( column=1, row=1, padx=6 )
	ttk.Label( colorsPane, text='Shininess:' ).grid( column=3, row=1, sticky='e', padx=(12, 0) )
	shininessEntry = HexEditEntry( colorsPane, -1, 4, 'f', 'Shininess' ) # Data offset (the -1) will be updated below
	shininessEntry.grid( column=4, row=1, padx=6 )

	colorsPane.pack( pady=(vertPadding, 0), expand=True, fill='x', padx=20 )
	
	# print 'material structs:', [hex(0x20+obj.offset) for obj in modelPane.materialStructs]
	# print 'displayObj structs:', [hex(0x20+obj.offset) for obj in modelPane.displayObjects]

	# Set initial values for the transparency controls and material colors above, or disable them
	if modelPane.displayObjects:
		firstDisplayObj = modelPane.displayObjects[0]

		# Get a parent Joint Object, and see if its hidden flag is set
		for structureOffset in firstDisplayObj.getParents():
			jointStruct = globalDatFile.initSpecificStruct( hsdStructures.JointObjDesc, structureOffset )
			if jointStruct:
				jointFlags = jointStruct.getValues( specificValue='Joint_Flags' )
				jointHidden.set( jointFlags & 0b10000 ) # Checking bit 4
				break
		else: # The loop above didn't break; no joint struct parent found
			modelPane.hideJointChkBtn.configure( state='disabled' )
			ToolTip( modelPane.hideJointChkBtn, '(No parent Joint Object found.)', wraplength=400 )

		# Check the current state of this model part's rendering; get the first Polygon Object, and see if its Display List Blocks/Length attribute is 0
		polygonObjOffset = firstDisplayObj.getValues( specificValue='Polygon_Object_Pointer' )
		polygonObj = globalDatFile.initSpecificStruct( hsdStructures.PolygonObjDesc, polygonObjOffset, firstDisplayObj.offset )

		if polygonObj:
			displayListBlocks = polygonObj.getValues( 'Display_List_Length' )
			displayListDisabled.set( not bool(displayListBlocks) ) # Resolves to True if the value is 0, False for anything else
		else:
			displayListDisabled.set( False )
			modelPane.polyDisableChkBtn.configure( state='disabled' )

		# If we found display objects, we must have also found material structs; get its values
		materialStruct = modelPane.materialStructs[0]
		matColorsOffset = materialStruct.getValues()[3]
		matColorsStruct = globalDatFile.initSpecificStruct( hsdStructures.MaterialColorObjDesc, matColorsOffset, materialStruct.offset )
		diffusion, ambience, specularHighlights, transparency, shininess = matColorsStruct.getValues()

		# Get all of the offsets that would be required to update the material color values
		diffusionHexOffsets = []
		ambienceHexOffsets = []
		highlightsHexOffsets = []
		shininessHexOffsets = []
		for materialStruct in modelPane.materialStructs:
			matColorsStructOffset = materialStruct.getValues( 'Material_Colors_Pointer' )
			diffusionHexOffsets.append( matColorsStructOffset )
			ambienceHexOffsets.append( matColorsStructOffset + 4 )
			highlightsHexOffsets.append( matColorsStructOffset + 8 )
			shininessHexOffsets.append( matColorsStructOffset + 0x10 )

		# Set the transparency slider's value (which will also update the Entry widget's value)
		modelPane.opacityScale.set( transparency * 10 ) # Multiplied by 10 because the slider's range is 0 to 10 (to compensate for trough-click behavior)

		# Add an event handler to forces focus to go to the slider when it's clicked on (dunno why it doesn't do this already).
		# This is necessary for the opacityScaleUpdated function to work properly
		modelPane.opacityScale.bind( '<Button-1>', lambda event: modelPane.opacityScale.focus() )

		# Add these values and color swatches to the GUI
		diffusionHexString = '{0:0{1}X}'.format( diffusion, 8 ) # Avoids the '0x' and 'L' appendages brought on by the hex() function. pads to 8 characters
		ambienceHexString = '{0:0{1}X}'.format( ambience, 8 ) # Avoids the '0x' and 'L' appendages brought on by the hex() function. pads to 8 characters
		highlightsHexString = '{0:0{1}X}'.format( specularHighlights, 8 ) # Avoids the '0x' and 'L' appendages brought on by the hex() function. pads to 8 characters

		diffusionEntry.insert( 0, diffusionHexString )
		diffusionEntry.offsets = diffusionHexOffsets
		diffusionEntry.colorSwatch = ColorSwatch( colorsPane, diffusionHexString, diffusionEntry )
		diffusionEntry.colorSwatch.grid( column=2, row=0, padx=(0,2) )
		
		ambienceEntry.insert( 0, ambienceHexString )
		ambienceEntry.offsets = ambienceHexOffsets
		ambienceEntry.colorSwatch = ColorSwatch( colorsPane, ambienceHexString, ambienceEntry )
		ambienceEntry.colorSwatch.grid( column=5, row=0, padx=(0,2) )
		
		highlightsEntry.insert( 0, highlightsHexString )
		highlightsEntry.offsets = highlightsHexOffsets
		highlightsEntry.colorSwatch = ColorSwatch( colorsPane, highlightsHexString, highlightsEntry )
		highlightsEntry.colorSwatch.grid( column=2, row=1, padx=(0,2) )
		
		shininessEntry.insert( 0, shininess )
		shininessEntry.offsets = shininessHexOffsets

		# Add bindings for input submission
		diffusionEntry.bind( '<Return>', updateEntryHex )
		ambienceEntry.bind( '<Return>', updateEntryHex )
		highlightsEntry.bind( '<Return>', updateEntryHex )
		shininessEntry.bind( '<Return>', updateEntryHex )
	else:
		# Disable the render checkbuttons and transparency controls
		modelPane.hideJointChkBtn.configure( state='disabled' )
		modelPane.polyDisableChkBtn.configure( state='disabled' )
		modelPane.opacityEntry.configure( state='disabled' )
		modelPane.opacityBtn.configure( state='disabled' )

		# Disable the Material Color inputs
		diffusionEntry.configure( state='disabled' )
		ambienceEntry.configure( state='disabled' )
		highlightsEntry.configure( state='disabled' )
		shininessEntry.configure( state='disabled' )

		# Add a label explaining why these are disabled
		disabledControlsText = ('These controls are disabled because no Display Objects or Material Structs directly associated with this texture. '
								'If this is part of a texture animation, find the default texture for it and adjust that instead.' )
		ttk.Label( modelPane, text=disabledControlsText, wraplength=wraplength ).pack( pady=(vertPadding, 0) )


def toggleHideJoint():

	""" Toggles the bit flag for 'Hidden' for each parent Joint Struct of the texture currently selected 
		in the DAT Texture Tree tab (last item in the selection if multiple items are selected). """

	hideJoint = Gui.modelPropertiesPane.interior.hideJointChkBtn.var.get()

	modifiedJoints = [] # Tracks which joint flags we've already updated, to reduce redundancy

	# Iterate over the display objects of this texture, get their parent joint objects, and modify their flag
	for displayObj in Gui.modelPropertiesPane.interior.displayObjects:
		parentJointOffsets = displayObj.getParents()

		for parentStructOffset in parentJointOffsets:
			jointStruct = globalDatFile.initSpecificStruct( hsdStructures.JointObjDesc, parentStructOffset )
			if jointStruct and parentStructOffset not in modifiedJoints:
				# Change the bit within the struct values and file data, and record that the change was made
				globalDatFile.updateFlag( jointStruct, 1, 4, hideJoint )
				
				modifiedJoints.append( parentStructOffset )

	updateProgramStatus( 'Joint Flag Updated' )


def toggleDisplayListRendering():

	""" Toggles the defined length of the display lists associated with the currently texture currently selected 
		in the DAT Texture Tree tab (last item in the selection if multiple items are selected). """

	clearDisplayList = Gui.modelPropertiesPane.interior.polyDisableChkBtn.var.get()

	for displayObj in Gui.modelPropertiesPane.interior.displayObjects:
		# Get the polygon object of this display object, as well as its siblings
		polygonObjOffset = displayObj.getValues( 'Polygon_Object_Pointer' )
		polygonObj = globalDatFile.initSpecificStruct( hsdStructures.PolygonObjDesc, polygonObjOffset, displayObj.offset )
		polygonSiblingObjs = [globalDatFile.structs[o] for o in polygonObj.getSiblings()] # These should all be initialized through the .getSiblings method

		# Process this object and its siblings
		for polygonStruct in [polygonObj] + polygonSiblingObjs:
			# Get info on this polygon object's display list
			displayListLength, displayListPointer = polygonStruct.getValues()[4:6]
			determinedListLength = globalDatFile.getStructLength( displayListPointer ) / 0x20

			# Check the current display list length (when disabling) to make sure the value can be properly switched back
			if clearDisplayList and displayListLength != determinedListLength:
				msg( 'Warning! The display list length of ' + polygonStruct.name + ' was not the expected calculated value; '
					'The current value is {}, while it was expected to be {}. '.format( displayListLength, determinedListLength ) + \
					"This means if you want to be able to restore this value later, you'll need to write the current value "
					'down, so you can restore it manually in the Structural Analysis tab.', 'Unexpected Display List Length' )

			if clearDisplayList:
				globalDatFile.updateStructValue( polygonStruct, 4, 0 )
			else:
				globalDatFile.updateStructValue( polygonStruct, 4, determinedListLength )

	updateProgramStatus( 'Polygon Structs Updated' )


def opacityEntryUpdated( newValue ):

	""" Handles events from the transparency Entry widget, when its value is changed. 
		This just validates the input, and updates the value on the slider. 
		newValue will initially be a string of a float. """

	# Validate the input and convert it from a string to a decimal integer
	try:
		newValue = float( newValue.replace( '%', '' ) )
	except:
		if newValue == '':
			newValue = 0
		else:
			return False
	if newValue < 0 or newValue > 100:
		return False

	# Set the slider to the current value
	newValue = newValue / 10
	Gui.modelPropertiesPane.interior.opacityScale.set( newValue )

	return True


def opacityScaleUpdated( newValue ):

	""" Handles events from the transparency Slider widget, when its value is changed. The slider value ranges between 0 and 10,
		(so that it's intervals when clicking in the trough jump a decent amount). The purpose of this function is just to
		update the value in the Entry widget. 'newValue' will initially be a string of a float. """

	newValue = round( float(newValue), 2 )

	# If this is not the Entry widget causing a change in the value, update it too
	if Gui.root.focus_get() != Gui.modelPropertiesPane.interior.opacityEntry:
		# Set the entry widget to the current value (temporarily disable the validation function, so it's not called)
		Gui.modelPropertiesPane.interior.opacityEntry.configure( validate='none')
		Gui.modelPropertiesPane.interior.opacityEntry.delete( 0, 'end' )
		Gui.modelPropertiesPane.interior.opacityEntry.insert( 0, str(newValue*10) + '%' )
		Gui.modelPropertiesPane.interior.opacityEntry.configure( validate='key')


def setModelTransparencyLevel():

	""" Calling function of the "Set" button under the Model tab's Transparency Control. """

	opacityValue = Gui.modelPropertiesPane.interior.opacityScale.get() / 10

	# Update the transparency value, and set required flags for this in the Material Struct
	for materialStruct in Gui.modelPropertiesPane.interior.materialStructs:
		matColorsOffset = materialStruct.getValues( 'Material_Colors_Pointer' )
		matColorsStruct = globalDatFile.initSpecificStruct( hsdStructures.MaterialColorObjDesc, matColorsOffset, materialStruct.offset )

		if matColorsStruct: # If the Material Struct doesn't have its colors struct, we probably don't need to worry about modifying it
			# Change the transparency value within the struct values and file data, and record that the change was made
			globalDatFile.updateStructValue( matColorsStruct, -2, opacityValue )

			if opacityValue < 1.0: # Set the required flags (RENDER_NO_ZUPDATE and RENDER_XLU; i.e. bits 29 and 30)
				globalDatFile.updateFlag( materialStruct, 1, 29, True ) # RENDER_NO_ZUPDATE
				globalDatFile.updateFlag( materialStruct, 1, 30, True ) # RENDER_XLU
			# else:
			# 	globalDatFile.updateFlag( materialStruct, 1, 29, False )
			# 	globalDatFile.updateFlag( materialStruct, 1, 30, False )

	if opacityValue < 1.0: # Set flags required for this in the Joint Struct(s)
		modifiedJoints = [] # Tracks which joint flags we've already updated, to reduce redundancy

		# Iterate over the display objects of this texture, get their parent joint objects, and modify their flag
		for displayObj in Gui.modelPropertiesPane.interior.displayObjects:
			parentJointOffsets = displayObj.getParents()

			for parentStructOffset in parentJointOffsets:
				jointStruct = globalDatFile.initSpecificStruct( hsdStructures.JointObjDesc, parentStructOffset )
				if jointStruct and parentStructOffset not in modifiedJoints:
					# Change the bit within the struct values and file data, and record that the change was made
					globalDatFile.updateFlag( jointStruct, 1, 19, True ) # XLU
					#globalDatFile.updateFlag( jointStruct, 1, 28, True ) # ROOT_OPA
					globalDatFile.updateFlag( jointStruct, 1, 29, True ) # ROOT_XLU
					
					modifiedJoints.append( parentStructOffset )
	
	updateProgramStatus( 'Transparency Updated' )


class EnumOptionMenu( ttk.OptionMenu ):

	def __init__( self, parent, structures, fieldIndex ):
		self.structures = structures
		self.fieldIndex = fieldIndex
		if type( structures ) == list:
			structure = structures[0]
		else: # It's just one structure object
			structure = structures

		# Get the current value of the enumeration
		self.currentEnum = structure.getValues()[fieldIndex]
		self.fieldName = structure.fields[fieldIndex]

		# Enumerations must be provided by the structure class
		self.enumerations = structure.enums[self.fieldName] # Retrieves a dictionary of the form key=enumInt, value=enumNameString
		self.optionNames = self.enumerations.values()
		defaultOption = self.enumerations[self.currentEnum]
		textVar = Tk.StringVar() # Required to init the optionmenu

		ttk.OptionMenu.__init__( self, parent, textVar, defaultOption, *self.optionNames, command=self.optionSelected )

	def optionSelected( self, newOption ):
		# Convert the option name to the enumeration value
		newEnum = self.optionNames.index( newOption )

		if newEnum == self.currentEnum:
			return # Nothing to do here

		# Replace the data in the file and structure for each one
		updateName = self.fieldName.replace( '\n', ' ' )
		descriptionOfChange = updateName + ' modified in ' + globalDatFile.fileName
		if type( self.structures ) == list:
			for structure in self.structures:
				globalDatFile.updateStructValue( structure, self.fieldIndex, newEnum, descriptionOfChange )
		else: # The offsets attribute is just a single struct (the usual case)
			globalDatFile.updateStructValue( self.structures, self.fieldIndex, newEnum, descriptionOfChange )

		updateProgramStatus( updateName + ' Updated' )


def populateTexPropertiesTab( wraplength, width, height, thisImageType ):

	""" Populates the Properties tab of the DAT Texture Tree interface. At this point, the pane has already been cleared. """

	propertiesPane = Gui.texturePropertiesPane.interior
	texStructs = Gui.modelPropertiesPane.interior.textureStructs
	matStructs = Gui.modelPropertiesPane.interior.materialStructs
	pixStructs = [] # Pixel Processing structures
	vertPadding = 10

	# Make sure there are Texture Structs to edit
	if not texStructs:
		noTexStructText = ( 'No Texture Structs found; there are no editable properties. If this texture is part of '
							'a material animation, find the default texture for that animation and edit that instead.' )
		ttk.Label( propertiesPane, text=noTexStructText, wraplength=wraplength ).pack( pady=vertPadding*2 )
		return

	# Collect offsets that we'll need for the HexEditEntries.
	# Also, get the flags data, and check if they're the same across all tex structs for this texture.
	matFlagOffsets = [ matStruct.offset+4 for matStruct in matStructs ]
	texFlagFieldOffsets = []
	pixelProcFlagOffsets = []
	blendingOffsets = []
	wrapModeSoffsets = []
	wrapModeToffsets = []
	reapeatSoffsets = []
	reapeatToffsets = []
	matFlagsData = set()
	texFlagsData = set()
	pixFlagsData = set()
	blendingData = set()
	wrapSData = set()
	wrapTData = set()
	repeatSData = set()
	repeatTData = set()

	# Populate the above lists with the actual hex data from the file
	for texStruct in texStructs:
		texFlagFieldOffsets.append( texStruct.offset + 0x40 )
		wrapModeSoffsets.append( texStruct.offset + 0x34 )
		wrapModeToffsets.append( texStruct.offset + 0x38 )
		reapeatSoffsets.append( texStruct.offset + 0x3C )
		reapeatToffsets.append( texStruct.offset + 0x3D )

		texFlagsData.add( hexlify(texStruct.data[0x40:0x44]) )
		wrapSData.add( hexlify(texStruct.data[0x34:0x38]) )
		wrapTData.add( hexlify(texStruct.data[0x38:0x3C]) )
		repeatSData.add( hexlify(texStruct.data[0x3C:0x3D]) )
		repeatTData.add( hexlify(texStruct.data[0x3D:0x3E]) )
	for matStructure in matStructs:
		matFlagsData.add( hexlify(matStructure.data[0x4:0x8]) )

		# Check if there's a valid pointer to a Pixel Proc. structure, and get flags from it if there is
		if matStructure.offset + 0x14 in globalDatFile.pointerOffsets:
			pixelProcStructOffset = matStructure.getValues()[-1]
			pixProcStruct = globalDatFile.initSpecificStruct( hsdStructures.PixelProcObjDesc, pixelProcStructOffset, matStructure.offset )

			if pixProcStruct:
				pixStructs.append( pixProcStruct )
				pixelProcFlagOffsets.append( pixelProcStructOffset )
				pixFlagsData.add( hexlify(globalDatFile.getData(pixelProcStructOffset, 1)) )

				blendingOffsets.append( pixelProcStructOffset + 4 )
				blendingData.add( ord(globalDatFile.getData(pixelProcStructOffset+4, 1)) )
	displayDifferingDataWarning = False

	# Describe the number of Texture Structs found
	if len( texStructs ) == 1:
		texCountLabel = ttk.Label( propertiesPane, text='These controls will edit 1 set of structures.', wraplength=wraplength )
	else:
		texCountLabelText = 'These controls will edit {} sets of structures.\nTo edit individual structs, use the Structural Analysis tab.'.format( len(texStructs) )
		texCountLabel = ttk.Label( propertiesPane, text=texCountLabelText, wraplength=wraplength )
	texCountLabel.pack( pady=(vertPadding*2, 0) )

	ttk.Separator( propertiesPane, orient='horizontal' ).pack( fill='x', padx=24, pady=(vertPadding*2, 0) )
	flagsFrame = Tk.Frame( propertiesPane )
	
	if len( pixFlagsData ) > 0:
		# Add blending options
		ttk.Label( flagsFrame, text='Blending Mode:' ).grid( column=0, row=0, sticky='e' )
		if len( blendingData ) > 1: # Add a 2 px border around the widget using a Frame (the widget itself doesn't support a border)
			optionMenuBorderFrame = Tk.Frame( flagsFrame, background='orange' )
			blendingMenu = EnumOptionMenu( optionMenuBorderFrame, pixStructs, 4 )
			blendingMenu.pack( padx=2, pady=2 )
			optionMenuBorderFrame.grid( column=1, row=0, columnspan=2, padx=7 )
			displayDifferingDataWarning = True
		else:
			blendingMenu = EnumOptionMenu( flagsFrame, pixStructs[0], 4 )
			blendingMenu.grid( column=1, row=0, columnspan=2, padx=7 )

		# Add widgets for the Pixel Processing Flags label, hex edit Entry, and Flags 'Decode' button
		ttk.Label( flagsFrame, text='Pixel Processing Flags:' ).grid( column=0, row=1, sticky='e' )
		hexEntry = HexEditEntry( flagsFrame, pixelProcFlagOffsets, 1, 'B', 'Pixel Processing Flags' )
		hexEntry.insert( 0, next(iter(pixFlagsData)).upper() )
		hexEntry.bind( '<Return>', updateEntryHex )
		hexEntry.grid( column=1, row=1, padx=7, pady=1 )
		Gui.texturePropertiesPane.flagWidgets.append( hexEntry )
		if len( pixFlagsData ) > 1:
			hexEntry['highlightbackground'] = 'orange'
			hexEntry['highlightthickness'] = 2
			displayDifferingDataWarning = True
		flagsLabel = ttk.Label( flagsFrame, text='Decode', foreground='#00F', cursor='hand2' )
		flagsLabel.grid( column=2, row=1, pady=0 )
		flagsLabel.bind( '<1>', lambda e, s=pixStructs[0], fO=pixelProcFlagOffsets: FlagDecoder(s, fO, 0) )
	else:
		ttk.Label( flagsFrame, text='Pixel Processing is not used on this texture.', wraplength=wraplength ).grid( column=0, row=0, columnspan=3, pady=(0, vertPadding) )

	# Add widgets for the Render Mode Flags label, hex edit Entry, and Flags 'Decode' button
	ttk.Label( flagsFrame, text='Render Mode Flags:' ).grid( column=0, row=2, sticky='e' )
	hexEntry = HexEditEntry( flagsFrame, matFlagOffsets, 4, 'I', 'Render Mode Flags' )
	hexEntry.grid( column=1, row=2, padx=7, pady=1 )
	Gui.texturePropertiesPane.flagWidgets.append( hexEntry )
	if len( matFlagsData ) == 0:
		hexEntry['state'] = 'disabled'
	else:
		hexEntry.insert( 0, next(iter(matFlagsData)).upper() )
		hexEntry.bind( '<Return>', updateEntryHex )
		flagsLabel = ttk.Label( flagsFrame, text='Decode', foreground='#00F', cursor='hand2' )
		flagsLabel.grid( column=2, row=2, pady=0 )
		flagsLabel.bind( '<1>', lambda e, s=matStructs[0], fO=matFlagOffsets: FlagDecoder(s, fO, 1) )
	if len( matFlagsData ) > 1:
		hexEntry['highlightbackground'] = 'orange'
		hexEntry['highlightthickness'] = 2
		displayDifferingDataWarning = True

	# Add widgets for the Texture Flags label, hex edit Entry, and Flags 'Decode' button
	ttk.Label( flagsFrame, text='Texture Flags:' ).grid( column=0, row=3, sticky='e' )
	hexEntry = HexEditEntry( flagsFrame, texFlagFieldOffsets, 4, 'I', 'Texture Flags' )
	hexEntry.grid( column=1, row=3, padx=7, pady=1 )
	Gui.texturePropertiesPane.flagWidgets.append( hexEntry )
	if len( texFlagsData ) == 0:
		hexEntry['state'] = 'disabled'
	else:
		hexEntry.insert( 0, next(iter(texFlagsData)).upper() )
		hexEntry.bind( '<Return>', updateEntryHex )
		flagsLabel = ttk.Label( flagsFrame, text='Decode', foreground='#00F', cursor='hand2' )
		flagsLabel.grid( column=2, row=3 )
		flagsLabel.bind( '<1>', lambda e, s=texStructs[0], fO=texFlagFieldOffsets: FlagDecoder(s, fO, 18) )
	if len( texFlagsData ) > 1:
		hexEntry['highlightbackground'] = 'orange'
		hexEntry['highlightthickness'] = 2
		displayDifferingDataWarning = True

	flagsFrame.pack( pady=(vertPadding*2, 0) )

	# Add Wrap Mode and Repeat Mode
	modesFrame = Tk.Frame( propertiesPane )
	wrapOptions = OrderedDict( [('Clamp', 0), ('Repeat', 1), ('Mirrored', 2), ('Reserved', 3)] )

	# Wrap Mode S
	ttk.Label( modesFrame, text='Wrap Mode S:' ).grid( column=0, row=0, sticky='e' )
	defaultWrapS = int( next(iter(wrapSData)), 16 ) # Gets one of the hex values collected from the struct(s), and then converts it to an int
	if len( wrapSData ) > 1:
		frameBorder = Tk.Frame( modesFrame, background='orange' ) # The optionmenu widget doesn't actually support a border :/
		dropdown = HexEditDropdown( frameBorder, wrapModeSoffsets, 4, 'I', 'Wrap Mode S', wrapOptions, defaultWrapS, command=updateEntryValue )
		dropdown.pack( padx=2, pady=2 )
		frameBorder.grid( column=1, row=0, padx=7, pady=1 )
	 	displayDifferingDataWarning = True
	else:
		dropdown = HexEditDropdown( modesFrame, wrapModeSoffsets, 4, 'I', 'Wrap Mode S', wrapOptions, defaultWrapS, command=updateEntryValue )
		dropdown.grid( column=1, row=0, padx=7, pady=1 )

	# Wrap Mode T
	ttk.Label( modesFrame, text='Wrap Mode T:' ).grid( column=0, row=1, sticky='e' )
	defaultWrapT = int( next(iter(wrapTData)), 16 ) # Gets one of the hex values collected from the struct(s), and then converts it to an int
	if len( wrapTData ) > 1:
		frameBorder = Tk.Frame( modesFrame, background='orange' ) # The optionmenu widget doesn't actually support a border :/
		dropdown = HexEditDropdown( frameBorder, wrapModeToffsets, 4, 'I', 'Wrap Mode T', wrapOptions, defaultWrapT, command=updateEntryValue )
		dropdown.pack( padx=2, pady=2 )
		frameBorder.grid( column=1, row=1, padx=7, pady=1 )
	 	displayDifferingDataWarning = True
	else:
		dropdown = HexEditDropdown( modesFrame, wrapModeToffsets, 4, 'I', 'Wrap Mode T', wrapOptions, defaultWrapT, command=updateEntryValue )
		dropdown.grid( column=1, row=1, padx=7, pady=1 )

	# Repeat Mode S
	ttk.Label( modesFrame, text='Repeat Mode S:' ).grid( column=2, row=0, sticky='e', padx=(7, 0) )
	hexEntry = HexEditEntry( modesFrame, reapeatSoffsets, 1, '?', 'Repeat Mode S' )
	hexEntry.insert( 0, next(iter(repeatSData)).upper() )
	hexEntry.bind( '<Return>', updateEntryHex )
	hexEntry.grid( column=3, row=0, padx=7, pady=1 )
	if len( repeatSData ) > 1:
		hexEntry['highlightbackground'] = 'orange'
		hexEntry['highlightthickness'] = 2
		displayDifferingDataWarning = True

	# Repeat Mode T
	ttk.Label( modesFrame, text='Repeat Mode T:' ).grid( column=2, row=1, sticky='e', padx=(7, 0) )
	hexEntry = HexEditEntry( modesFrame, reapeatToffsets, 1, '?', 'Repeat Mode T' )
	hexEntry.insert( 0, next(iter(repeatTData)).upper() )
	hexEntry.bind( '<Return>', updateEntryHex )
	hexEntry.grid( column=3, row=1, padx=7, pady=1 )
	if len( repeatTData ) > 1:
		hexEntry['highlightbackground'] = 'orange'
		hexEntry['highlightthickness'] = 2
		displayDifferingDataWarning = True

	modesFrame.pack( pady=(vertPadding, 0) )

	if displayDifferingDataWarning:
		differingDataLabelText = (  'Warning! Values with an orange border are different across the multiple structures '
									'that these controls will modify; you may want to exercise caution when changing them '
									'here, which would make them all the same.' )
		differingDataLabel = ttk.Label( propertiesPane, text=differingDataLabelText, wraplength=wraplength )
		differingDataLabel.pack( pady=(vertPadding*2, 0) )

	# Add alternative texture sizes
	ttk.Separator( propertiesPane, orient='horizontal' ).pack( fill='x', padx=24, pady=(vertPadding*2, 0) )
	ttk.Label( propertiesPane, text='Alternative Texture Sizes:' ).pack( pady=(vertPadding*2, 0) )
	altImageSizesFrame = Tk.Frame( propertiesPane )
	sizesDict = OrderedDict()
	for i, imageType in enumerate( ( 0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 14 ) ):
	 	thisSize = hsdStructures.ImageDataBlock.getDataLength( width, height, imageType )
	 	if imageType == thisImageType: continue

		if not thisSize in sizesDict:
			sizesDict[thisSize] = [userFriendlyFormatList[i]]
		else:
			sizesDict[thisSize].append( userFriendlyFormatList[i] )
	row = 0
	for size, formatList in sizesDict.items():
		ttk.Label( altImageSizesFrame, text='  /  '.join( formatList ) ).grid( column=0, row=row, sticky='w' )
		ttk.Label( altImageSizesFrame, text=uHex( size ) ).grid( column=1, row=row, sticky='w', padx=(12, 0) )
	 	row += 1
	altImageSizesFrame.pack()


class PointerLink( ttk.Label ):

	""" Simple label widget to provide an arrow button, which when clicked, searches for a structure in the SA tab. """

	def __init__( self, parent, structOffset ):
		self.offset = structOffset

		# Create the label, bind a click event handler to it, and add a tooltip message
		ttk.Label.__init__( self, parent, text='-->', foreground='#00F', cursor='hand2' )
		self.bind( '<1>', self.clicked )
		ToolTip( self, text='Show', delay=500 )

	def clicked( self, event ):
		showStructInStructuralAnalysis( self.offset )
		
		# Switch to the SA tab
		Gui.mainTabFrame.select( Gui.savTab )


def determineMaxPaletteColors( imageType, paletteStructLength ):

	""" Determines the maximum number of colors that are suppored by a palette. Image type and palette 
		data struct length are both considered, going with the lower limit between the two. """

	if imageType == 8: 		# 4-bit
		maxColors = 16
	elif imageType == 9:	# 8-bit
		maxColors = 256
	elif imageType == 10:	# 14-bit
		maxColors = 16384
	else:
		print 'Invalid image type given to determineMaxPaletteColors():', imageType
		return 0

	# The actual structure length available overrides the image's type limitation
	maxColorsBySpace = paletteStructLength / 2

	if maxColorsBySpace < maxColors:
		maxColors = maxColorsBySpace

	return maxColors


def populatePaletteTab( imageDataOffset, imageDataLength, imageType ):
	# If a palette entry was previously highlighted/selected, keep it that way
	previouslySelectedEntryOffset = -1
	selectedEntries = Gui.paletteCanvas.find_withtag( 'selected' )
	if selectedEntries:
		tags = Gui.paletteCanvas.gettags( selectedEntries[0] )

		# Get the other tag, which will be the entry's file offset
		for tag in tags:
			if tag != 'selected':
				previouslySelectedEntryOffset = int( tag.replace('t', '') ) # 't' included in the first place because the tag cannot be purely a number
				break

	Gui.paletteCanvas.delete( 'all' )
	Gui.paletteCanvas.paletteEntries = [] # Storage for the palette square images, so they're not garbage collected. (Using images for their canvas-alpha support.)
	Gui.paletteCanvas.itemColors = {} # For remembering the associated color within the images (rather than looking up pixel data within the image) and other info, to be passed on to the color picker

	# Try to get info on the palette palette
	paletteDataOffset, paletteHeaderOffset, paletteLength, paletteType, colorCount = getPaletteInfo( globalDatFile, imageDataOffset )

	if paletteDataOffset == -1: # Couldn't find the data. Set all values to 'not available (n/a)'
		Gui.paletteDataText.set( 'Data Offset:\nN/A' )
		Gui.paletteHeaderText.set( 'Header Offset:\nN/A' )
		Gui.paletteTypeText.set( 'Palette Type:\nN/A' )
		Gui.paletteMaxColorsText.set( 'Max Colors:\nN/A' )
		Gui.paletteStatedColorsText.set( 'Stated Colors:\nN/A' )
		#Gui.paletteActualColorsText.set( 'Actual Colors:\nN/A' )
		return

	# Get the image and palette data
	imageData = globalDatFile.getData( imageDataOffset, imageDataLength )
	paletteData = hexlify( getPaletteData(globalDatFile, paletteDataOffset=paletteDataOffset, imageData=imageData, imageType=imageType)[0] )

	# Update all fields and the palette canvas (to display the color entries).
	Gui.paletteDataText.set( 'Data Offset:\n' + uHex(paletteDataOffset + 0x20) )
	if paletteHeaderOffset == -1: Gui.paletteHeaderText.set( 'Header Offset:\nNone' )
	else: Gui.paletteHeaderText.set( 'Header Offset:\n' + uHex(paletteHeaderOffset + 0x20) )

	if paletteType == 0: Gui.paletteTypeText.set( 'Palette Type:\n0 (IA8)' )
	if paletteType == 1: Gui.paletteTypeText.set( 'Palette Type:\n1 (RGB565)' )
	if paletteType == 2: Gui.paletteTypeText.set( 'Palette Type:\n2 (RGB5A3)' )
	Gui.paletteMaxColorsText.set( 'Max Colors:\n' + str(determineMaxPaletteColors( imageType, paletteLength )) )
	Gui.paletteStatedColorsText.set( 'Stated Colors:\n' + str(colorCount) )
	#Gui.paletteActualColorsText.set( 'Actual Colors:\n' + str(len(paletteData)/4) )

	# Create the initial/top offset indicator.
	x = 7
	y = 11
	Gui.paletteCanvas.create_line( 105, y-3, 120, y-3, 130, y+4, 175, y+4, tags='descriptors' ) # x1, y1, x2, y2, etc....
	Gui.paletteCanvas.create_text( 154, y + 12, text=uHex(paletteDataOffset + 0x20), tags='descriptors' )

	# Populate the canvas with the palette entries.
	for i in xrange( 0, len(paletteData), 4 ): # For each palette entry....
		paletteEntry = paletteData[i:i+4]
		entryNum = i/4
		paletteEntryOffset = paletteDataOffset + i/2
		x = x + 12
		rgbaColor = tplDecoder.decodeColor( paletteType, paletteEntry, decodeForPalette=True ) # rgbaColor = ( r, g, b, a )
		
		# Prepare and store an image object for the entry (since .create_rectangle doesn't support transparency)
		paletteSwatch = Image.new( 'RGBA', (8, 8), rgbaColor )
		Gui.paletteCanvas.paletteEntries.append( ImageTk.PhotoImage(paletteSwatch) )

		# Draw a rectangle for a border; start by checking whether this is a currently selected entry
		if paletteEntryOffset == previouslySelectedEntryOffset: 
			borderColor = Gui.paletteCanvas.entryBorderColor
			tags = ('selected', 't'+str(paletteEntryOffset) )
		else: 
			borderColor = 'black'
			tags = 't'+str(paletteEntryOffset)
		Gui.paletteCanvas.create_line( x-1, y-1, x+8, y-1, x+8, y+8, x-1, y+8, x-1, y-1, fill=borderColor, tags=tags )

		# Draw the image onto the canvas.
		itemId = Gui.paletteCanvas.create_image( x, y, image=Gui.paletteCanvas.paletteEntries[entryNum], anchor='nw', tags='entries' )
		Gui.paletteCanvas.itemColors[itemId] = ( rgbaColor, paletteEntry, paletteEntryOffset, imageDataOffset )

		if x >= 103: # End of the row (of 8 entries); start a new row.
			x = 7
			y = y + 11
			i = i / 4 + 1

			# Check if the current palette entry is a multiple of 32 (4 lines)
			if float( i/float(32) ).is_integer() and i < len( paletteData )/4: # (second check prevents execution after last chunk of 0x40)
				y = y + 6
				Gui.paletteCanvas.create_line( 105, y-3, 117, y-3, 130, y+4, 176, y+4, tags='descriptors' ) # x1, y1, x2, y2, etc....
				Gui.paletteCanvas.create_text( 154, y + 12, text=uHex(paletteDataOffset + 0x20 + i*2), tags='descriptors' )

	def onColorClick( event ):
		# Determine which canvas item was clicked on, and use that to look up all entry info
		itemId = event.widget.find_closest( event.x, event.y )[0]
		if itemId not in Gui.paletteCanvas.itemColors: return # Abort. Probably clicked on a border.
		canvasItemInfo = Gui.paletteCanvas.itemColors[itemId]
		initialHexColor = ''.join( [ "{0:0{1}X}".format( channel, 2 ) for channel in canvasItemInfo[0] ] )

		MeleeColorPicker( 'Change Palette Color', initialHexColor, paletteType, windowId=itemId, datDataOffsets=canvasItemInfo )

	def onMouseEnter(e): Gui.paletteCanvas['cursor']='hand2'
	def onMouseLeave(e): Gui.paletteCanvas['cursor']=''

	Gui.paletteCanvas.tag_bind( 'entries', '<1>', onColorClick )
	Gui.paletteCanvas.tag_bind( 'entries', '<Enter>', onMouseEnter )
	Gui.paletteCanvas.tag_bind( 'entries', '<Leave>', onMouseLeave )


def writeTextureToDat( datFile, imageFilepath, imageDataOffset, updateGui, subsequentMipmapPass=False ):

	""" Collects information on the image being imported, encodes it as raw TPL data, and writes it into the DAT's file data.
		Returns the success/fail status of the operation, and some information on the palette, if one failed to import.
		
		"status" may be one of the following strings: 
			dataObtained				operation (image encoding and import) successful
			paletteRegenerated			[for paletted textures] operation successful, and a new palette was generated
			dataWithAdHocPalette		depricated; shouldn't be possible anymore. same as above, except the encoding and palette generation was done by wimgt 
			formatUnsupported			unable to encode/import, likely because the image was not a PNG or TPL file
			imageHeaderNotFound			couldn't find headers for image data located at imageDataOffset. the offset is likely wrong, or the header was modified
			invalidMipmapDims
			imageTypeNotFound
			notEnoughSpace
			or an exit code (of failed conversion) """

	# Collect info on this image
	newImagePath = imageFilepath # Temp filepath for mipmap textures; subsequent mipmap levels will be downsized from the original image file
	iid = str( imageDataOffset ) # For the datTextureTree treeview, an iid is the image data offset.
	updateDataHeaders = generalBoolSettings['autoUpdateHeaders'].get()
	headersAvailable = True
	lastEffTextureOffset = getattr( globalDatFile, 'lastEffTexture', -1 ) # Only relevant with effects files and some stages
	
	# Treat this as a DOL file if this is for special alphabet character textures in SdMenu.dat/.usd (these have no headers)
	if datFile.rootNodes != [] and datFile.rootNodes[0] == (0, 'SIS_MenuData'):
		targetFileExt = 'dol'
	else:
		targetFileExt = datFile.path.split( '.' )[-1].lower()

	mipmapLevel = getMipmapLevel( iid )

	if targetFileExt == 'dol': # Special processing for DOLs, since they have no image data headers.
		origWidth = 32; origHeight = 32; origImageType = 0
		origImageDataLength = 0x200
		headersAvailable = False

	elif targetFileExt == 'bnr': # Special processing for Banners, since they have no image data headers.
		origWidth = 96; origHeight = 32; origImageType = 5
		origImageDataLength = 0x1800
		headersAvailable = False

	elif mipmapLevel > -1: # Special processing for mipmap images
		imageDataOffset, origImageDataLength, origWidth, origHeight, origImageType = parseTextureDetails( iid )

		# Create a temp file name and save location.
		sourceDatFilename = os.path.basename( datFile.path ).split('_')[-1]
		newFileName = sourceDatFilename + '_' + uHex(imageDataOffset + 0x20) + '_' + str(origImageType)

		# Get the Game ID if this file was loaded from a disc.
		if datFile.source == 'disc' and globalDiscDetails['gameId'] != '': # Means an ISO has been loaded, and (using the file path) the current dat is not from an outside standalone file.
			gameID = globalDiscDetails['gameId']
		else: gameID = 'No Associated Disc'

		# Construct the destination file path, and create the folders if they don't already exist.
		destinationFolder = texDumpsFolder + '\\' + gameID + '\\' + sourceDatFilename + '\\'
		if not os.path.exists(destinationFolder): os.makedirs(destinationFolder)

		# If the imported file is in TPL format, convert it to PNG
		if imageFilepath[-4:] == '.tpl':
			newImage = tplDecoder( imageFilepath, (origWidth, origHeight), origImageType )
			imageFilepath = destinationFolder + newFileName + '.tpl'
			newImage.createPngFile( imageFilepath, creator='DTW - v' + programVersion )

		# Open the image that will be used as a base for all mipmap levels
		mipmapImage = Image.open( imageFilepath )

		# Validate the image's dimensions, and resize it if needed
		if mipmapImage.size != (origWidth, origHeight):
			if not subsequentMipmapPass: return ( 'invalidMipmapDims', '', '' )
			else:
				# Downscale the original texture to the current mipmap level's size.
				filters = { 'nearest': 0, 'lanczos': 1, 'bilinear': 2, 'bicubic': 3 }
				filterId = filters[settings.get( 'General Settings', 'downscalingFilter' )]
				mipmapImage = mipmapImage.resize( (origWidth, origHeight), resample=filterId )

				# Save the image data to a memory buffer so it can be sent to the encoder without creating a file (needed for wimgt).
				#imageBuffer = StringIO()
				#mipmapImage.save( imageBuffer, 'png' )
				#newImagePath = imageBuffer.getvalue()
				#newImagePath = imageBuffer

				# Save the image data to a new file (#todo: once wimgt is no longer needed, use above method to prevent needing to create a file)
				newImagePath = destinationFolder + newFileName + '.png'
				mipmapImage.save( newImagePath, 'png' )

	elif (0x1E00, 'MemSnapIconData') in datFile.rootNodes: # The file is LbMcSnap.usd or LbMcSnap.dat (Memory card banner/icon file from SSB Melee)
		headersAvailable = False

		if imageDataOffset == 0:
			origWidth = 96; origHeight = 32
			origImageType = 5
			origImageDataLength = 0x1800
		else: # There are only two images in this file
			origWidth = 32; origHeight = 32
			origImageType = 9
			origImageDataLength = 0x400

	elif (0x4E00, 'MemCardIconData') in datFile.rootNodes: # The file is LbMcGame.usd or LbMcGame.dat (Memory card banner/icon file from SSB Melee)
		headersAvailable = False

		if imageDataOffset < 0x4800:
			origWidth = 96; origHeight = 32
			origImageType = 5
			origImageDataLength = 0x1800
		else:
			origWidth = 32; origHeight = 32
			origImageType = 9
			origImageDataLength = 0x400

	elif imageDataOffset <= lastEffTextureOffset:
		headersAvailable = False # Some image data headers are shared in this file, so they can't be changed (unless all are changed)
		_, origImageDataLength, origWidth, origHeight, origImageType = parseTextureDetails( iid ) # todo: fix this; it won't work with disc import method

	else:
		# Validate the given image data offset
		if imageDataOffset not in datFile.structureOffsets:
			msg( 'Invalid Texture offset detected: ' + hex(0x20+imageDataOffset) + '; unable to write texture into DAT.' )
			return ( 'invalidTextureOffset', '', '' ) # todo; this is not yet specifically handled in the texture import function

		# Gather info on the texture currently in the DAT/USD.
		imageDataStruct = datFile.initDataBlock( hsdStructures.ImageDataBlock, imageDataOffset )
		_, origWidth, origHeight, origImageType, _, _, _ = imageDataStruct.getAttributes()
		origImageDataLength = getImageDataLength( origWidth, origHeight, origImageType )

	# Gather palette information on the texture currently in the DAT.
	if origImageType == 8 or origImageType == 9 or origImageType == 10:
		# Find information on the associated palette (if unable to, return).
		paletteDataOffset, paletteHeaderOffset, paletteLength, origPaletteType, origPaletteColorCount = getPaletteInfo( datFile, imageDataOffset )
		if paletteDataOffset == -1: return ( 'paletteNotFound', '', '' )

		# If not updating data headers, assume the current palette format must be preserved, and prevent the tplCodec from choosing one (if it creates a palette)
		# In other words, if there are data headers, leave this unspecified so that the codec may intelligently choose the best palette type.
		if updateDataHeaders and headersAvailable:
			origPaletteType = None # No known value descriptiong for palette type in effects files

		maxPaletteColorCount = paletteLength / 2
	else:
		origPaletteType = None
		origPaletteColorCount = 255
		maxPaletteColorCount = 255

	# Encode the image data into TPL format
	try:
		newImage = tplEncoder( newImagePath, imageType=origImageType, paletteType=origPaletteType, maxPaletteColors=maxPaletteColorCount )
		newImageData = newImage.encodedImageData
		newPaletteData = newImage.encodedPaletteData
		newImageType = newImage.imageType
		newImageHeader = "{0:0{1}X}".format( newImage.width, 4 ) + "{0:0{1}X}".format( newImage.height, 4 ) + "{0:0{1}X}".format(newImageType, 8)
		status = 'dataObtained'
	except TypeError: # For CMPR (_14) textures.
		(status, newImageHeader, newImageData, _, newPaletteData) = getImageFileAsTPL( newImagePath, origImageType )
		newImageData = bytearray.fromhex( newImageData )
		newPaletteData = bytearray.fromhex( newPaletteData )
		newImageType = int( newImageHeader[-2:], 16 )
		# If this codec is attempted, none of the exceptions below will be triggered; status will come from getImageFileAsTPL above.
	except IOError:
		status = 'formatUnsupported'
	except missingType:
		status = 'imageTypeNotFound'
	except Exception as error:
		print 'Encoding fail error:', error
		status = 'failedEncoding'

	#if mipmapData: imageBuffer.close()

	# Validate banner dimensions before importing it to the DAT file
	if targetFileExt == 'bnr' and ( newImage.width != 96 or newImage.height != 32):
		return ( 'invalidDimensions', '', '' )

	# Texture info collected and texture data encoded. 
	if status != 'dataObtained' and status != 'dataWithAdHocPalette':
		return ( status, '', '' )
	else:
		newImageDataLength = len( newImageData )

		# Image properly imported to program's memory. Check that it will fit in the alloted space and whether a palette also needs to be replaced.
		if newImageDataLength > origImageDataLength: return ( 'notEnoughSpace', '', '' )
		else:
			# If this is not a DOL file, then add 0x20 bytes to account for a DAT's file header.
			adjustedImageDataOffset = imageDataOffset
			if not targetFileExt == 'dol': adjustedImageDataOffset += 0x20

			if newImageType == 8 or newImageType == 9 or newImageType == 10:
				# Check if a new palette was generated, and whether it's currently permitted to use a new one
				if newImage.paletteRegenerated and not generalBoolSettings['regenInvalidPalettes'].get(): 
					unpermittedPaletteRegen = True
				else: unpermittedPaletteRegen = False

				# Make sure there is space for the new palette, and update the dat's data with it.
				newPaletteColorCount = len( newPaletteData ) / 2 # All of the palette types (IA8, RGB565, and RGB5A3) are 2 bytes per color entry
				if newPaletteColorCount <= maxPaletteColorCount and not unpermittedPaletteRegen:
					entriesToFill = origPaletteColorCount - newPaletteColorCount
					nullData = '8000' * entriesToFill # 8000 typically seen as null entry data for palettes
					nullBytes = bytearray.fromhex( nullData )

					# Update the palette data header (if there is one)
					if origPaletteType != newImage.paletteType:
						if not headersAvailable:
							return ( 'invalidPaletteProperties', origPaletteType, newImage.paletteType )

						elif updateDataHeaders:
							descriptionOfChange = 'Palette type updated in header'
							datFile.updateData( paletteHeaderOffset+7, newImage.paletteType, descriptionOfChange ) # sets the palette type
						else:
							msg('Warning: The texture imported to ' + uHex( adjustedImageDataOffset ) + ' has a different palette type than the current '
								'one, and automatic updating of data headers is disabled. This could lead '
								"to undesired effects or crashes.\n\nIf you know what you're doing, so be it. If not, you can re-enable Auto-Update Headers "
								"in the Settings menu and re-import this texture to solve this, or manually edit the header(s) in the Structural Analysis tab.", 
								'Different Palette Type Detected')

					# Update the palette data
					datFile.updateData( paletteDataOffset, newPaletteData + nullBytes, 'Palette data updated' )
				
					if newImage.paletteRegenerated: status = 'paletteRegenerated'

				else:
					return ( 'paletteTooLarge', str(maxPaletteColorCount), str(newImage.originalPaletteColorCount) )

			# Look at the image data headers to see whether the current ones should be updated.
			currentHeader = "{0:0{1}X}".format(origWidth, 4) + "{0:0{1}X}".format(origHeight, 4) + "{0:0{1}X}".format(origImageType, 8) # 8 bytes total
			if currentHeader.lower() != newImageHeader.lower():
				if not headersAvailable:
					return ( 'invalidImageProperties', (origWidth, origHeight), origImageType )

				# If the auto-update is enabled, update each image data header to match the new texture's properties. Otherwise, warn the user of the difference.
				elif updateDataHeaders:
					headerOffsets = datFile.structs[imageDataOffset].getParents()
					for offset in headerOffsets:
						datFile.updateData( offset+4, bytearray.fromhex(newImageHeader), 'Image type updated in header' )
				else:
					msg('Warning: The texture imported to ' + uHex( adjustedImageDataOffset ) + ' has different properties than the current '
						'one (width, height, or texture type), and automatic updating of data headers is disabled. This could lead '
						"to undesired effects or crashes.\n\nIf you know what you're doing, so be it. If not, you can re-enable Auto-Update Headers "
						"in the Settings menu and re-import this texture to solve this, or manually edit the header(s) in the Structural Analysis tab.", 
						'Different Image Data Properties Detected')

			# If the new texture is smaller than the original, fill the extra space with zeroes
			if newImageDataLength < origImageDataLength:
				newImageData.extend( bytearray(origImageDataLength - newImageDataLength) ) # Adds n bytes of null data

			# Update the texture image data in the file
			datFile.updateData( imageDataOffset, newImageData, 'Image data updated' )

			# Check for potentially invalid image dimensions
			# Parse the newImageHeader for the new dimensions (can't use newImage.width because a newImage might not have been created)
			width = int( newImageHeader[:4], 16 )
			height = int( newImageHeader[4:8], 16 )
			# if width > 1024 or width % 2 != 0 or height > 1024 or height % 2 != 0:
			# 	status = 'invalidDimensions'
			# 	tags = list( Gui.datTextureTree.item( iid, 'tags' ) )
			# 	if 'warn' not in tags: 
			# 		tags.append( 'warn' )
			# 		Gui.datTextureTree.item( iid, tags=tags )

			if updateGui: # Update the image displayed in the GUI on the DAT Texture Tree tab
				renderTextureData( imageDataOffset, width, height, newImageType, newImageDataLength, allowImageDumping=False )

				# Update the GUI/treeview's values for the texture.
				newValues = (
						uHex(adjustedImageDataOffset) + '\n(' + uHex(newImageDataLength) + ')', 	# offset to image data, and data length
						( str(width) + ' x ' + str(height) ), 								# width and height
						'_' + str(newImageType) + ' (' + imageFormats[newImageType] + ')' 		# the image type and format
					)
				Gui.datTextureTree.item( iid, values=newValues )

			# Replace child mipmap textures if there are any
			if mipmapLevel > -1 and generalBoolSettings['cascadeMipmapChanges'].get() and ( width > 1 and height > 1 ):
				Gui.root.update() # Updates the GUI, so that the above texture replacement can be seen before moving on to the next texture
				status = writeTextureToDat( datFile, imageFilepath, imageDataOffset + origImageDataLength, updateGui, True )[0]

			return ( status, '', '' )


def blankTextures( cascadingMipmapChange=False, iidSelectionsTuple=() ):
	if not iidSelectionsTuple: iidSelectionsTuple = Gui.datTextureTree.selection()

	if len( iidSelectionsTuple ) == 0: msg( 'No textures are selected.' )
	else:

		for iid in iidSelectionsTuple:
			# Collect info on the selected texture.
			imageDataOffset, imageDataLength, width, height, imageType = parseTextureDetails( iid )

			# Fill the texture data area with zeros.
			emptyBytes = bytearray( imageDataLength ) # bytearray intialized with n bytes of 0
			globalDatFile.updateData( imageDataOffset, emptyBytes, 'Texture zeroed out' )

			# If it's a paletted image, fill the palette data region with zeros as well.
			if imageType == 8 or imageType == 9 or imageType == 10:
				paletteDataOffset, paletteHeaderOffset, paletteLength, paletteType, paletteColorCount = getPaletteInfo( globalDatFile, imageDataOffset )
				if paletteDataOffset == -1: continue

				emptyPaletteData = '8000' * ( paletteLength / 2 ) # '8000' is two bytes, so the palette length variable is halved
				globalDatFile.updateData( paletteDataOffset, bytearray.fromhex(emptyPaletteData), 'Palette zeroed out' )

				# Update the palette tab if this is the currently selected texture.
				if iid == Gui.datTextureTree.selection()[-1]: populatePaletteTab( int(iid), imageDataLength, imageType )

			# Load the texture and a thumbnail image of it into memory
			renderTextureData( imageDataOffset, width, height, imageType, imageDataLength, allowImageDumping=False )

			# Remember this change (per initially selected texture(s), but not for lower cascaded mipmap levels)
			# if not cascadingMipmapChange:
			# 	# If this is not a DOL file, then add 0x20 bytes to account for a DAT's file header.
			# 	filename = os.path.basename( globalDatFile.path )
			# 	adjustedImageDataOffset = imageDataOffset
			# 	if not filename[-4:].lower() == '.dol': adjustedImageDataOffset += 0x20

			# 	globalDatFile.unsavedChanges.append( 'Texture erased at ' + uHex(adjustedImageDataOffset) + ' in ' + filename + '.' )

			# Update subsequent mipmap levels
			if generalBoolSettings['cascadeMipmapChanges'].get() and 'mipmap' in Gui.datTextureTree.item( iid, 'tags' ):
				# Check if this is the 'parent' mipmap
				if Gui.datTextureTree.parent( iid ) == '': # root item; get iid of first child
					nextMipmapLevel = Gui.datTextureTree.get_children( iid )[0]
				else:
					nextMipmapLevel = Gui.datTextureTree.next( iid )

				if nextMipmapLevel: # This will be an empty string if this is the last level (1x1)
					blankTextures( cascadingMipmapChange=True, iidSelectionsTuple=tuple([nextMipmapLevel]) )
		
		# Update the program status
		if not cascadingMipmapChange: # (only want to do this on the initial run of this function)
			if len( iidSelectionsTuple ) == 1: updateProgramStatus( 'Texture Blanked' )
			else: updateProgramStatus( 'Textures Blanked' )


# def disableTextures(): # Unused
# 	iidSelectionsTuple = Gui.datTextureTree.selection()

# 	if len(iidSelectionsTuple) == 0: msg('No textures are selected.')
# 	else: 
# 		global datData, unsavedDatChanges

# 		for iid in iidSelectionsTuple:
# 			# Collect info on the selected texture.
# 			#imageDataDetails, dimensions, imageType = Gui.datTextureTree.item( iid, 'values' )
# 			imageDataOffset = int( iid ) #int( imageDataDetails.split()[0], 16 ) - 0x20

# 			for headerInfo in getImageDataHeaders( datFile, imageDataOffset ): # Gets a list of the headers that point to this texture.

# 				# Get the offset of the pointer (to the image data header) in the Texture Structure.
# 				parentPointerOffsets = getParentPointerOffsets( datFile, headerInfo[0] )

# 				if parentPointerOffsets == []:
# 					msg( 'No parent structures found!' )
# 				elif len(parentPointerOffsets) > 1:
# 					print 'multiple parent pointers found!'
# 				# 	#ttk.Label( textureStructureProperties, text='Pointer offsets found in multiple Texture Structures (' + str(len(parentPointerOffsets)) + ' total): ' ).pack(pady=pady)
# 				# 	for i in xrange( len(parentPointerOffsets) ):
# 				# 		ttk.Label(textureStructureProperties, text=uHex(parentPointerOffsets[i] + 0x20)).pack(pady=pady)
# 				else: # Only one offset found.
# 					for parentPointerOffset in parentPointerOffsets:

# 						# Confirm this is a pointer by checking for it in the RT Table.?

# 						# Zero out the Texture Struct's pointer to the Image Data Header.
# 						print 'Image Header Pointer Offset: ' + uHex( parentPointerOffset + 0x20 )
# 						datData = replaceHex( datData, parentPointerOffset, '00000000')
# 						globalDatFile.unsavedChanges.append( 'Texture disabled at ' + uHex(imageDataOffset + 0x20) + ' in ' + os.path.basename( globalDatFile.path ) + '.' )

# 		updateProgramStatus( 'Texture(s) Disabled' )


def extendTextureSpace( offset, diff ): # test args: 0x3BF40, 0xC800 (Closed port texture in MnSlChr, at 0x2F760)

	""" This function will expand the data area at the given offset, starting at the first argument. The second argument is the amount 
		to increase by. All pointers occurring after the sum of the two arguments will be recalculated. Example usage would have the 
		first argument as the end point of a texture, and the second argument as the amount to increase the space by. """

	if diff == 0: return
	offset -= 0x20 # To account for the file header, which is not included in datData

	datDataBytes = globalDatFile.data
	rtDataBytes = globalDatFile.rtData
	offsetBytes = toBytes( offset )
	headerInfo = globalDatFile.headerInfo

	# Update the file header with the new file size and start of the relocation table.
	newFileSize = headerInfo['filesize'] + diff
	newRtStart = headerInfo['rtStart'] + diff
	globalDatFile.headerData[:8] = toBytes( newFileSize ) + toBytes( newRtStart )

	# For each entry in the relocation table, update the address it points to, and the value of the pointer there, if they point to locations beyond the extended space.
	entriesUpdated = 0
	pointersUpdated = 0

	for rtByteOffset in xrange( 0, len(rtDataBytes), 4 ):
		# If the pointer appears after the change, update its address in the relocation table accordingly.
		rtEntryBytes = rtDataBytes[rtByteOffset:rtByteOffset+4]
		rtEntryInt = toInt( rtEntryBytes )
		if rtEntryBytes >= offsetBytes:
			rtDataBytes[rtByteOffset:rtByteOffset+4] = toBytes( rtEntryInt + diff )
			entriesUpdated += 1

		# If the place that the pointer points to is after the space change, update its value accordingly.
		dataPointer = datDataBytes[rtEntryInt:rtEntryInt+4]
		if dataPointer >= offsetBytes:
			datDataBytes[rtEntryInt:rtEntryInt+4] = toBytes( toInt(dataPointer) + diff )
			pointersUpdated += 1
	
	print 'length of defined section:', headerInfo['rtEnd'] - headerInfo['rtStart'], '  lenght of actual section:', len(rtDataBytes)
	datDataBytes[headerInfo['rtStart']:headerInfo['rtEnd']] = rtDataBytes # rtData (the global variable isn't later merged. so we need to do this here)

	# Update offsets in the root/reference node tables
	rootAndRefNodesTable = datDataBytes[headerInfo['rtEnd']:headerInfo['stringTableStart']]
	for nodeByteOffset in xrange( 0, len(rootAndRefNodesTable), 8 ): # 8 bytes = 1 table entry
		filePointer = rootAndRefNodesTable[nodeByteOffset:nodeByteOffset+4]

		if filePointer >= offsetBytes:
			newNodePointer = toInt( filePointer ) + diff
			if newNodePointer - roundTo32( newNodePointer ) != 0: print 'Warning, root/ref node pointers must be aligned to 0x20 bytes!'
			rootAndRefNodesTable[nodeByteOffset:nodeByteOffset+4] = toBytes( newNodePointer )
			pointersUpdated += 1
	datDataBytes[headerInfo['rtEnd']:headerInfo['stringTableStart']] = rootAndRefNodesTable

	if diff < 0: # Remove bytes from the latter section
		datDataBytes = datDataBytes[:offset] + datDataBytes[offset+diff:] 
	else: # Fill the newly extended space with zeros.
		datDataBytes = datDataBytes[:offset] + bytearray( diff ) + datDataBytes[offset:]

	globalDatFile.data = datDataBytes
	globalDatFile.rtData = rtDataBytes

	msg('RT Entries updated: ' + str(entriesUpdated) + '\nPointers updated: ' + str(pointersUpdated))
	globalDatFile.unsavedChanges.append( uHex(diff) + ' of space added to file at offset ' + uHex(offset + 0x20) + '.' )
	updateProgramStatus( 'Space Extension Complete' )


def generateTrimColors( fileIid, autonomousMode=False ):
	#tic = time.clock()

	# Get the file's data and parse the file for basic info
	theDatFile = hsdFiles.datFileObj( source='disc' )
	theDatFile.load( fileIid, fileData=getFileDataFromDiscTreeAsBytes( iid=fileIid ) )
	hInfo = theDatFile.headerInfo

	# Quick failsafe to make sure the file is recognizable, avoiding large processing time
	if hInfo['rootNodeCount'] > 300 or hInfo['referenceNodeCount'] > 300 or hInfo['rtEntryCount'] > 45000 or len( theDatFile.rtData ) > 200000: 
		msg( 'The file structure of ' + fileIid + ' could not be analyzed for trim color generation.' )
		return

	updateProgramStatus( 'Generating CSP Trim Colors....' )
	Gui.programStatusLabel.update()

	# Collect the textures in the file
	textures = {} # keys: imageDataOffset, values: pil images
	totalWidth = 0
	totalHeight = 0

	for imageDataOffset, imageHeaderOffset, _, _, width, height, imageType, _ in identifyTextures( theDatFile ):

		# Skip this texture if it's a shading layer, by checking the flags of the Texture Struct that this texture is attached to
		imageDataHeader = theDatFile.initSpecificStruct( hsdStructures.ImageObjDesc, imageHeaderOffset )
		if not imageDataHeader: continue
		for headerParentOffset in imageDataHeader.getParents():
			# Test for a Texture Struct
			textureStruct = theDatFile.initSpecificStruct( hsdStructures.TextureObjDesc, headerParentOffset, printWarnings=False )
			if textureStruct: break
		else: continue # Above loop didn't break; no texture struct found (must be part of an animation such as an eye)
		if textureStruct.getValues( 'GXTexGenSrc' ) != 4: # Checking layer flags
			#print 'Skipping texture', uHex( 0x20+imageDataOffset ), 'for trim color generation, as it appears to be a shading layer'
			continue

		try:
			imageDataLength = hsdStructures.ImageDataBlock.getDataLength( width, height, imageType )
			imageData = theDatFile.getData( imageDataOffset, imageDataLength )

			# Skip this texture if its data has been "blanked"
			if not any( imageData ): continue

			if imageType == 8 or imageType == 9 or imageType == 10:
				paletteData, paletteType = getPaletteData( theDatFile, imageDataOffset )
			else: 
				paletteData = ''
				paletteType = None

			# Decode the texture data
			newImg = tplDecoder( '', (width, height), imageType, paletteType, imageData, paletteData )
			newImg.deblockify() # This decodes the image data, to create an rgbaPixelArray.

			textures[imageDataOffset] = Image.new( 'RGBA', (width, height) )
			textures[imageDataOffset].putdata( newImg.rgbaPixelArray )

			# Update the cumulative dimensions of the new super image
			if width > totalWidth: 
				totalWidth = width
			totalHeight += height

		except: 
			print 'Failed to decode texture at', uHex(0x20+imageDataOffset), 'for trim color generation'

	# Combine the images collected above into one super image
	yOffset = 0
	superImage = Image.new( 'RGBA', (totalWidth, totalHeight) )
	for texture in textures.values():
		superImage.paste( texture, (0, yOffset) )
		yOffset += texture.size[1]

	# Save the image data to a memory buffer so it can be sent to the color quantizer without creating a file.
	superImageBuffer = StringIO()
	superImage.save( superImageBuffer, 'png' )

	# Create a palette for the super image
	exitCode, outputStream = cmdChannel( '"' + pathToPngquant + '" --speed 3 13 - ', standardInput=superImageBuffer.getvalue() )
	superImageBuffer.close()
	if exitCode != 0:
		print 'Error while generating super image palette; exit code:', exitCode
		print outputStream
		msg( 'There was an error during color generation. Error code: '+str(exitCode) + '\n\nDetails:\n' + outputStream, 'Error Generating CSP Trim Colors.' )
		updateProgramStatus( 'Error Generating CSP Trim Colors.' )
		return

	# Get the palette generated for the super image
	palettedFileBuffer = StringIO( outputStream )
	pngImage = png.Reader( palettedFileBuffer )
	pngImage.read() # Needed for pulling the palette; its return value might be useful to print
	generatedPalette = pngImage.palette( alpha='force' )
	palettedFileBuffer.close()

	# Filter out the palette entry relating to the extra empty space in the super image (alpha of 0)
	generatedPalette = [ entry for entry in generatedPalette if entry[3] != 0 ]
	baseColor = generatedPalette[0]

	# Get a value to determine whether the base color is light or dark (value/brightness)
	baseColorValue = rgb2hsv( baseColor )[2]

	# Convert the colors to HSV format (excluding the base color)
	hsvList = [ rgb2hsv(color) for color in generatedPalette[1:] ]

	# Go through the colors and look for the highest combination of luminance and saturation in order to pick an accent color
	highestSatLum = 0
	highestSatLumColorIndex = 0
	for i, color in enumerate( hsvList ):
		_, saturation, value = color # first value is hue
		if baseColorValue >= .5: # Place higher weight on darker colors (values) instead
			satLum = saturation + 1 - value
		else: satLum = saturation + value

		if satLum > highestSatLum: 
			highestSatLum = satLum
			highestSatLumColorIndex = i

	accentColor = generatedPalette[1:][highestSatLumColorIndex]

	filename = os.path.basename( fileIid )
	if autonomousMode: 
		updateTrimColors( filename, colors=(rgb2hex(baseColor).replace('#', ''), rgb2hex(accentColor).replace('#', '')) )
	else: # Show the user some options for the accent color, and let them decide whether to add these colors to their game.
		updateProgramStatus( 'CSP Trim Colors Generated' )
		showColorSwatches( colors=generatedPalette, chosenColors=(baseColor, accentColor), filename=filename )


def updateTrimColors( filename, colors=() ):
	tableOffset = 0x3a3c90

	characterTableOffsets = { # First value is the start of that character's section (to the character name), relative to the start of the table
		'ca': ( 0, 'gy', 're', 'wh', 'gr', 'bu' ),		# Falcon
		'dk': ( 0x70, 'bk', 're', 'bu', 'gr' ),			# DK
		'fx': ( 0xD0, 'or', 'la', 'gr' ),				# Fox
		'kb': ( 0x170, 'ye', 'bu', 're', 'gr', 'wh' ),	# Kirby
		'kp': ( 0x1E0, 're', 'bu', 'bk' ),				# Bowser
		'lk': ( 0x230, 're', 'bu', 'bk', 'wh' ),		# Link
		'lg': ( 0x290, 'wh', 'bu', 'pi' ),				# Luigi
		'mr': ( 0x2E0, 'ye', 'bk', 'bu', 'gr' ),		# Mario
		'ms': ( 0x340, 're', 'gr', 'bk', 'wh' ),		# Marth
		'mt': ( 0x3A0, 're', 'bu', 'gr' ),				# Mewtwo
		'ns': ( 0x3F0, 'ye', 'bu', 'gr' ),				# Ness
		'pe': ( 0x440, 'ye', 'wh', 'bu', 'gr' ),		# Peach
		'pk': ( 0x4A0, 're', 'bu', 'gr' ),				# Pika
		'nn': ( 0x4F0, 'ye', 'aq', 'wh' ),				# Nana (updating either IC changes the colors for both)
		'pp': ( 0x4F0, 'gr', 'or', 're' ),				# Popo
		'pr': ( 0x540, 're', 'bu', 'gr', 'ye' ),		# Jiggs
		'ss': ( 0x5A0, 'pi', 'bk', 'gr', 'la' ),		# Samus
		'ys': ( 0x600, 're', 'bu', 'ye', 'pi', 'aq' ),	# Yoshi
		'sk': ( 0x670, 're', 'bu', 'gr', 'wh' ),		# Sheik (updating either Sheik/Zelda changes the colors for both)
		'zd': ( 0x670, 're', 'bu', 'gr', 'wh' ),		# Zelda
		'fc': ( 0x6D0, 're', 'bu', 'gr' ),				# Falco
		'cl': ( 0x720, 're', 'bu', 'wh', 'bk' ),		# Y. Link
		'dr': ( 0x780, 're', 'bu', 'gr', 'bk' ),		# Dr. Mario
		'fe': ( 0x7E0, 're', 'bu', 'gr', 'ye' ),		# Roy
		'pc': ( 0x840, 're', 'bu', 'gr' ),				# Pichu
		'gn': ( 0x890, 're', 'bu', 'gr', 'la' ),		# Ganon
		'bo': ( 0x8F0, ),		# M. Wireframe
		'gl': ( 0x910, ),		# F. Wireframe
		'gk': ( 0x930, )		# Giga Bowser
	}

	# Parse the filename and make sure table location information for it is available
	char = filename[2:4]
	color = filename[4:6]
	if char not in characterTableOffsets or ( color not in characterTableOffsets[char] and color != 'nr' and color != 'rl' and color != 'rr' ): # Last two are for Falcon's Red alt
		print 'Unable to process CSP trim colors for', filename, 'due to an invalid filename.'
		return False

	# Calculate the offset of the color to be changed
	if color == 'nr': rowNumber = 1
	elif len( characterTableOffsets[char] ) == 1: rowNumber = 1 # These characters only have one set of alts
	elif color == 'rl' or color == 'rr': rowNumber = 3 # Both are Falcon's red costume
	else:
		for i, colorCode in enumerate( characterTableOffsets[char] ):
			if color == colorCode:
				rowNumber = i + 1 # +1 accounts for the missing 'nr' (for the Neutral costume) in the tuple
				break
		else: # loop above didn't break; coloCode not found (shouldn't happen due to previous validation)
			print 'Unable to process CSP trim colors for', filename, 'due to an invalid filename.'
			return False
	fileOffset = tableOffset + characterTableOffsets[char][0] + rowNumber * 0x10
	if filename[-4:] == '.rat': fileOffset += 8
	elif filename[-4:] == '.usd' and color == 'rr': fileOffset += 8 # For Falcon's Red Right alt
	print 'CSP Trim colors generated for', filename + ':', colors, '| Being placed at offset:', uHex(fileOffset)

	# Validate the colors
	if len( colors[0] ) != 6 or not validHex( colors[0] ):
		print 'Invalid Base Color value.'
		return False
	elif len( colors[1] ) != 6 or not validHex( colors[1] ):
		print 'Invalid Accent Color value.'
		return False

	# Find the CSS file iid
	postV407 = False # Refers to the version of 20XXHP (versions later than 4.06 use .0sd & .1sd rather than .usd)
	cssIid = scanDiscForFile( 'MnSlChr.u' )
	if not cssIid: 
		cssIid = scanDiscForFile( 'MnSlChr.0' )
		if cssIid: postV407 = True
	if not cssIid:
		print 'Unable to find the CSS file in the disc.'
		return False

	# Get the CSS's file information and data
	description, entity, isoOffset, fileSize, isoPath, source, data = Gui.isoFileTree.item( cssIid, 'values' )
	cssData = getFileDataFromDiscTree( iidValues=(entity, isoOffset, fileSize, source, data) )
	if not cssData: return False

	# Replace the color data at the specified offset
	cssData = replaceHex( cssData, fileOffset, colors[0] )
	cssData = replaceHex( cssData, fileOffset + 4, colors[1] )
	Gui.isoFileTree.item( cssIid, values=('CSP Trim Colors Updated', entity, isoOffset, fileSize, isoPath, 'ram', cssData), tags='changed' )

	global unsavedDiscChanges
	updateString = isoPath.split('/')[-1] + ' updated with new CSP Trim colors.'
	if not updateString in unsavedDiscChanges: unsavedDiscChanges.append( updateString )

	# Update the second CSS file as well if this is 20XXHP v2.07+
	if postV407:
		nextCssIid = scanDiscForFile( 'MnSlChr.1' )
		# Get the CSS's file information and data
		description, entity, isoOffset, fileSize, isoPath, source, data = Gui.isoFileTree.item( nextCssIid, 'values' )
		cssData = getFileDataFromDiscTree( iidValues=(entity, isoOffset, fileSize, source, data) )
		if not cssData: return False

		# Replace the color data at the specified offset
		cssData = replaceHex( cssData, fileOffset, colors[0] )
		cssData = replaceHex( cssData, fileOffset + 4, colors[1] )
		Gui.isoFileTree.item( nextCssIid, values=('CSP Trim Colors Updated', entity, isoOffset, fileSize, isoPath, 'ram', cssData), tags='changed' )

		updateString = isoPath.split('/')[-1] + ' updated with new CSP Trim colors.'
		if not updateString in unsavedDiscChanges: unsavedDiscChanges.append( updateString )

	updateProgramStatus( 'CSP Trim Colors Updated' )


class showColorSwatches( object ):

	""" Creates a non-modal window to present the user with options on pre-generated colors 
		generated for a character's CSP trim colors (for left/right alt costumes). """

	window = None

	def __init__( self, colors=[], chosenColors=(), filename='' ):
		self.colors = colors
		self.chosenColors = chosenColors
		self.filename = filename

		if showColorSwatches.window: showColorSwatches.window.destroy()

		self.showWindow()

	def showWindow( self ):
		# Define the window.
		showColorSwatches.window = Tk.Toplevel( Gui.root )
		showColorSwatches.window.title( 'CSP Trim Color Generator' )
		showColorSwatches.window.attributes('-toolwindow', 1) # Makes window framing small, like a toolbox/widget.
		showColorSwatches.window.resizable( width=True, height=True )
		#self.window.wm_attributes('-topmost', 1) # Makes the window always on top
		showColorSwatches.window.protocol( 'WM_DELETE_WINDOW', self.close ) # Overrides the 'X' close button.

		# Calculate the spawning position of the new window
		rootDistanceFromScreenLeft, rootDistanceFromScreenTop = getWindowGeometry( Gui.root )[2:]
		showColorSwatches.window.geometry( '+' + str(rootDistanceFromScreenLeft + 180) + '+' + str(rootDistanceFromScreenTop + 180) )

		# Populate the window
		self.mainFrame = Tk.Frame( showColorSwatches.window )

		# Show the generated palette colors
		if self.colors:
			def onColorClick( event ):
				widget = event.widget.find_closest(event.x, event.y)
				targetColor = self.colorsCanvas.itemcget( widget, 'fill' ).replace('#', '')
				self.color2Swatch['bg'] = '#' + targetColor
				self.color2Entry.delete( 0, 'end' )
				self.color2Entry.insert( 'end', targetColor + '00' )

			ttk.Label( self.mainFrame, wraplength=230, text='These are the colors generated for "' + self.filename + '". The Base Color should be the most prominent color '
				'for the costume. But you might try tweaking the Accent Color below.' ).pack( padx=16, pady=4 )
			self.colorsCanvas = Tk.Canvas( self.mainFrame, borderwidth=2, relief='ridge', background='white', width=197, height=19 )
			self.colorsCanvas.pack( pady=4 )

			x = 10
			y = 10

			for colorTuple in self.colors: # For each palette entry....
				colorHex = rgb2hex( colorTuple )
				self.colorsCanvas.create_rectangle( x, y, x + 8, y+8, width=1, fill=colorHex, tags='entries' )
				x += 16
			self.colorsCanvas.tag_bind( 'entries', '<1>', onColorClick )
			def onMouseEnter(e): self.colorsCanvas['cursor']='hand2'
			def onMouseLeave(e): self.colorsCanvas['cursor']=''
			self.colorsCanvas.tag_bind( 'entries', '<Enter>', onMouseEnter )
			self.colorsCanvas.tag_bind( 'entries', '<Leave>', onMouseLeave )

		chosenColorsFrame = Tk.Frame( self.mainFrame )
		baseColor = rgb2hex( self.chosenColors[0] )
		accentColor = rgb2hex( self.chosenColors[1] )
		# Color 1 / Base Color
		ttk.Label( chosenColorsFrame, text='Base Color' ).grid( column=0, row=0, padx=8, pady=3 )
		self.color1Swatch = Tk.Frame( chosenColorsFrame, bg=baseColor, width=60, height=25 )
		self.color1Swatch.grid( column=0, row=1, padx=8, pady=3 )
		self.color1Swatch.grid_propagate( False )
		self.color1Entry = ttk.Entry( chosenColorsFrame, text=baseColor + '00', width=9 )
		self.color1Entry.delete( 0, 'end' )
		self.color1Entry.insert( 'end', baseColor.replace('#', '') + '00' )
		self.color1Entry.grid( column=0, row=2, padx=8, pady=3 )
		# Color 2 / Accent Color
		ttk.Label( chosenColorsFrame, text='Accent Color' ).grid( column=1, row=0, padx=8, pady=3 )
		self.color2Swatch = Tk.Frame( chosenColorsFrame, bg=accentColor, width=60, height=25 )
		self.color2Swatch.grid( column=1, row=1, padx=8, pady=3 )
		self.color2Swatch.grid_propagate( False )
		self.color2Entry = ttk.Entry( chosenColorsFrame, text=accentColor + '00', width=9 )
		self.color2Entry.delete( 0, 'end' )
		self.color2Entry.insert( 'end', accentColor.replace('#', '') + '00' )
		self.color2Entry.grid( column=1, row=2, padx=8, pady=3 )

		chosenColorsFrame.pack( pady=3 )

		ttk.Button( self.mainFrame, text='Update in Game (MnSlChr Table)', command=self.sendTrimColors ).pack( ipadx=10, pady=7 )

		self.mainFrame.pack( fill='both', expand=1 )

	def sendTrimColors( self ):
		baseColor = self.color1Entry.get()[:6].replace('#', '')
		accentColor = self.color2Entry.get()[:6].replace('#', '')

		updateTrimColors( self.filename, colors=(baseColor, accentColor) )
		self.close()

	def close( self ):
		showColorSwatches.window.destroy()
		showColorSwatches.window = None


																				#=================================#
																				# ~ ~ Structural Analysis tab ~ ~ #
																				#=================================#

def getTreeviewDepth( treeviewWidget, iid ):
	depth = 0
	while 1:
		parent = treeviewWidget.parent( iid )
		if not parent: break

		iid = parent
		depth += 1

	return depth


def getStructureIids( targetOffsets ):

	""" Finds all instances of a structure or list of structures in the treeview (those that end with the target offsets). """

	parentIids = []

	for iid in Gui.fileStructureTree.allIids:
		if int( iid.split( '/' )[-1] ) in targetOffsets: parentIids.append( iid )
	
	return tuple( parentIids )


def adjustSavColumnWidth( treeItem, currentViewingWidth=None ):

	""" Expands the width of the Structural Analysis Tree's structure name column, 
		if the given treeview item is estimated to require more space. """

	# Check the current amount of space available, and the estimated space needed for the new item
	if not currentViewingWidth:
		currentViewingWidth = Gui.fileStructureTree.column( '#0', 'width' ) # Excludes the Offset column
	newStructureIndentation = 20 * getTreeviewDepth( Gui.fileStructureTree, treeItem ) + 20 # From the left-side of the treeview
	structureTextLength = len( Gui.fileStructureTree.item(treeItem, 'text') ) * 7 # Assuming ~7px per character; todo: make dynamic for scaling
	requiredWidth = 5 + newStructureIndentation + structureTextLength + 7 # 5 and 7 are to account for before/after the '+' sign, respectively

	# Expand the size of the treeview column, if more space is needed
	if requiredWidth > currentViewingWidth: # Expand the column width, and scroll all the way to the right
		Gui.fileStructureTree.column( '#0', width=requiredWidth )
		Gui.fileStructureTree.update() # Need the GUI to update the widget's new width
		Gui.fileStructureTree.xview_moveto( 1 )


def addHelpBtn( helpText ):
	helpLabel = ttk.Label( Gui.structurePropertiesFrame.interior, text='?', foreground='#445', cursor='hand2' )
	helpLabel.place( relx=1, x=-17, y=4 )
	helpLabel.bind( '<1>', lambda e, message=helpText: msg(message, 'Good to Know') )


def showFileProperties():
	# Set the top-most file name label
	ttk.Label( Gui.structurePropertiesFrame.interior, text=globalDatFile.fileName, font="-weight bold" ).pack( pady=12 )

	# Add a help button
	helpText = ( '"Total Structures" counts structures in the data section of the file, as well as 4 to 5 other basic DAT file structures, '
				 'which are: the file header, relocation table, string table, and the root/reference node tables.' )
	addHelpBtn( helpText )

	# Add file details; need to encapsulate the file details text in a Frame so that pack and grid don't conflict
	emptyWidget = Tk.Frame( relief='flat' ) # This is used as a simple workaround for the labelframe, so we can have no text label with no label gap.
	basicDetailsFrame = ttk.Labelframe( Gui.structurePropertiesFrame.interior, labelwidget=emptyWidget, padding=(20, 4) )

	# Construct the strings to be displayed
	fileSizeText = 'File Size:  0x{0:X}  ({0:,} bytes)'.format( globalDatFile.headerInfo['filesize'] )
	pointersCountText = 'Total Pointers:  {:,}'.format( len(globalDatFile.pointerOffsets) )
	structCountText = 'Total Structures:  {:,}'.format( len(globalDatFile.structureOffsets) )
	rootNodesText = 'Root Nodes:  {:,}'.format( len(globalDatFile.rootNodes) )
	refNodesText = 'Reference Nodes:  {:,}'.format( len(globalDatFile.referenceNodes) )

	# Add the above stings to the GUI using a table grid
	ttk.Label( basicDetailsFrame, text=fileSizeText, wraplength=Gui.structPropFrameWrapLength ).grid( column=0, row=0, columnspan=2 )
	ttk.Label( basicDetailsFrame, text=pointersCountText, wraplength=Gui.structPropFrameWrapLength ).grid( column=0, row=1, sticky='w', padx=11, pady=(4,0) )
	ttk.Label( basicDetailsFrame, text=structCountText, wraplength=Gui.structPropFrameWrapLength ).grid( column=0, row=2, sticky='w', padx=11 )
	ttk.Label( basicDetailsFrame, text=rootNodesText, wraplength=Gui.structPropFrameWrapLength ).grid( column=1, row=1, sticky='w', padx=11 )
	ttk.Label( basicDetailsFrame, text=refNodesText, wraplength=Gui.structPropFrameWrapLength ).grid( column=1, row=2, sticky='w', padx=11 )

	basicDetailsFrame.pack( pady=0 )

	# Add file operation buttons
	buttonFrame = ttk.Frame( Gui.structurePropertiesFrame.interior )
	buttonFrame.pack( pady=(12, 0) ) # Need to attach this before performing a deep dive
	ttk.Button( buttonFrame, text='View Hex', command=viewDatFileHex ).pack( side='left', padx=10 )
	if globalDatFile.deepDiveStats:
		ttk.Button( buttonFrame, text='Deep Dive', command=performDeepDive, state='disabled' ).pack( side='left', padx=10 )
		performDeepDive() # In this case, this'll skip the actual dive process and just display the data
	else:
		ttk.Button( buttonFrame, text='Deep Dive', command=performDeepDive ).pack( side='left', padx=10 )


def showRelocationTableInfo():
	# Set the top-most file structure name label
	ttk.Label( Gui.structurePropertiesFrame.interior, text='Relocation Table', font="-weight bold" ).pack( pady=12 )

	# Add info; need to encapsulate the file details text in a Frame so that pack and grid don't conflict
	emptyWidget = Tk.Frame( relief='flat' ) # This is used as a simple workaround for the labelframe, so we can have no text label with no label gap.
	basicDetailsFrame = ttk.Labelframe( Gui.structurePropertiesFrame.interior, labelwidget=emptyWidget, padding=(20, 4) )

	# Construct the strings to be displayed
	locationText = 'Location:  0x{:X} - 0x{:X}'.format( 0x20+globalDatFile.headerInfo['rtStart'], 0x20+globalDatFile.headerInfo['rtEnd'] )
	fileSizeText = 'Size:  0x{0:X}  ({0:,} bytes)'.format( globalDatFile.headerInfo['rtEnd'] - globalDatFile.headerInfo['rtStart'] )
	entriesCountText = 'Total Entries:  {:,}'.format( globalDatFile.headerInfo['rtEntryCount'] )

	# Add the above stings to the GUI using a table grid
	ttk.Label( basicDetailsFrame, text=locationText, wraplength=Gui.structPropFrameWrapLength ).grid( column=0, row=0, columnspan=2 )
	ttk.Label( basicDetailsFrame, text=fileSizeText, wraplength=Gui.structPropFrameWrapLength ).grid( column=0, row=1, columnspan=2 )
	ttk.Label( basicDetailsFrame, text=entriesCountText, wraplength=Gui.structPropFrameWrapLength ).grid( column=0, row=2, columnspan=2 )

	basicDetailsFrame.pack( pady=0 )


def showNodeTableInfo( name ): # For root and reference node tables
	if name.startswith( 'Root' ):
		totalEntries = globalDatFile.headerInfo['rootNodeCount']
		rootStructCount = len( globalDatFile.rootStructNodes )
		labelCount = len( globalDatFile.rootLabelNodes )
		start = 0x20 + globalDatFile.headerInfo['rtEnd']
		end = 0x20 + globalDatFile.headerInfo['rootNodesEnd']
		nodeDetails = [ '\tNode ' + str(i+1) + ', @ ' + uHex(node[0] + 0x20) + ' - - ' + node[1] for i, node in enumerate( globalDatFile.rootNodes ) ]

	else: # The reference nodes table
		totalEntries = globalDatFile.headerInfo['referenceNodeCount']
		rootStructCount = len( globalDatFile.refStructNodes )
		labelCount = len( globalDatFile.refLabelNodes )
		start = 0x20 + globalDatFile.headerInfo['rootNodesEnd']
		end = 0x20 + globalDatFile.headerInfo['stringTableStart']
		nodeDetails = [ '\tNode ' + str(i+1) + ', @ ' + uHex(node[0] + 0x20) + ' - - ' + node[1] for i, node in enumerate( globalDatFile.referenceNodes ) ]

	# Add the title
	ttk.Label( Gui.structurePropertiesFrame.interior, text=name, font="-weight bold" ).pack( pady=(12, 0) )

	# Add basic info
	emptyWidget = Tk.Frame( relief='flat' ) # This is used as a simple workaround for the labelframe, so we can have no text label with no label gap.
	basicDetailsFrame = ttk.Labelframe( Gui.structurePropertiesFrame.interior, labelwidget=emptyWidget, padding=(20, 4) )

	basicInfo = 'Location:  0x{:X} - 0x{:X}\nTotal Entries: {}\n\nRoot Structures: {}\nLabels: {}'.format( start, end, totalEntries, rootStructCount, labelCount )
	ttk.Label( basicDetailsFrame, text=basicInfo, wraplength=Gui.structPropFrameWrapLength ).pack( pady=(12, 0) )

	basicDetailsFrame.pack()

	# Add the label/button to show all nodes info
	nodeName = name.split()[0]
	def displayNodeInfo( event ): cmsg( '\n'.join(nodeDetails), title=nodeName + ' Table Nodes', align='left' )
	label = ttk.Label( Gui.structurePropertiesFrame.interior, text='View Nodes', wraplength=Gui.structPropFrameWrapLength, cursor='hand2', foreground='#00F' )
	label.bind( '<1>', displayNodeInfo )
	label.pack( pady=(12, 0) )


def showStringTableInfo():
	# Gather data and build a few strings for the GUI
	stringTableSize = globalDatFile.getStringTableSize()
	stringTableEnd = 0x20 + globalDatFile.headerInfo['stringTableStart'] + stringTableSize
	locationText = 'Location:  0x{:X} - 0x{:X}'.format( 0x20+globalDatFile.headerInfo['stringTableStart'], stringTableEnd )
	fileSizeText = 'Size:  0x{0:X}  ({0:,} bytes)'.format( stringTableSize )
	entriesCountText = 'Total Entries:  {}'.format( len(globalDatFile.rootNodes) + len(globalDatFile.referenceNodes) )

	# Check if there's any data beyond the reported end of the file
	totalFileSize = 0x20 + globalDatFile.headerInfo['stringTableStart'] + stringTableSize
	if totalFileSize == globalDatFile.headerInfo['filesize']:
		locationText += ' (file end)'

	ttk.Label( Gui.structurePropertiesFrame.interior, text='String Table', font="-weight bold" ).pack( pady=12 )

	# Add info; need to encapsulate the file details text in a Frame so that pack and grid don't conflict
	emptyWidget = Tk.Frame( relief='flat' ) # This is used as a simple workaround for the labelframe, so we can have no text label with no label gap.
	basicDetailsFrame = ttk.Labelframe( Gui.structurePropertiesFrame.interior, labelwidget=emptyWidget, padding=(20, 4) )

	ttk.Label( basicDetailsFrame, text=locationText, wraplength=Gui.structPropFrameWrapLength ).grid( column=0, row=0, columnspan=2 )
	ttk.Label( basicDetailsFrame, text=fileSizeText, wraplength=Gui.structPropFrameWrapLength ).grid( column=0, row=1, columnspan=2 )
	ttk.Label( basicDetailsFrame, text=entriesCountText, wraplength=Gui.structPropFrameWrapLength ).grid( column=0, row=2, columnspan=2 )

	basicDetailsFrame.pack( pady=0 )


def showSwordSwingInfo():

	""" Treat the Sword Swing Colors struct like a regular struct, and show fields for all of the actual values. """

	# Gather data and build a few strings for the GUI
	structOffset = globalDatFile.headerInfo['stringTableStart'] + globalDatFile.getStringTableSize() # Relative to data section start
	hexData = hexlify( globalDatFile.tailData[:0xC] ).upper()
	locationText = 'Location:  0x{:X}'.format( 0x20 + structOffset )
	fileSizeText = 'Size:  0xC  (12 bytes)'

	ttk.Label( Gui.structurePropertiesFrame.interior, text='Sword Swing Colors Struct', font="-weight bold" ).pack( pady=12 )

	# Add info; need to encapsulate the file details text in a Frame so that pack and grid don't conflict
	emptyWidget = Tk.Frame( relief='flat' ) # This is used as a simple workaround for the labelframe, so we can have no text label with no label gap.
	basicDetailsFrame = ttk.Labelframe( Gui.structurePropertiesFrame.interior, labelwidget=emptyWidget, padding=(20, 4) )
	
	ttk.Label( basicDetailsFrame, text=locationText, wraplength=Gui.structPropFrameWrapLength ).grid( column=0, row=0, columnspan=2 )
	ttk.Label( basicDetailsFrame, text=fileSizeText, wraplength=Gui.structPropFrameWrapLength ).grid( column=0, row=1, columnspan=2 )

	basicDetailsFrame.pack( pady=0 )

	# Create a new frame for displaying field names and hex values
	hexDisplayFrame = ttk.Frame( Gui.structurePropertiesFrame.interior, padding='0 12 0 12' ) # Left, Top, Right, Bottom.

	# Create the first column
	ttk.Label( hexDisplayFrame, text='Identifier:' ).grid( column=0, row=0, padx=(0, 7), pady=0, sticky='e' )
	ttk.Label( hexDisplayFrame, text='Ending Alpha:' ).grid( column=0, row=1, padx=(0, 7), pady=0, sticky='e' )
	ttk.Label( hexDisplayFrame, text='Starting Alpha:' ).grid( column=0, row=2, padx=(0, 7), pady=0, sticky='e' )
	ttk.Label( hexDisplayFrame, text='Edge Red Channel:' ).grid( column=0, row=3, padx=(0, 7), pady=0, sticky='e' )
	ttk.Label( hexDisplayFrame, text='Edge Green Channel:' ).grid( column=0, row=4, padx=(0, 7), pady=0, sticky='e' )
	ttk.Label( hexDisplayFrame, text='Edge Blue Channel:' ).grid( column=0, row=5, padx=(0, 7), pady=0, sticky='e' )
	ttk.Label( hexDisplayFrame, text='Center Red Channel:' ).grid( column=0, row=6, padx=(0, 7), pady=0, sticky='e' )
	ttk.Label( hexDisplayFrame, text='Center Green Channel:' ).grid( column=0, row=7, padx=(0, 7), pady=0, sticky='e' )
	ttk.Label( hexDisplayFrame, text='Center Blue Channel:' ).grid( column=0, row=8, padx=(0, 7), pady=0, sticky='e' )

	# Add an editable field for the raw hex data 						# highlightbackground is the BORDER color when not focused!
	hexEntry = Tk.Entry( hexDisplayFrame, width=10, justify='center', 
						relief='flat', highlightbackground='#b7becc', borderwidth=1, highlightthickness=1, highlightcolor='#0099f0' )
	hexEntry.insert( 0, hexData[:8] )
	hexEntry['state'] = 'disabled'
	hexEntry.grid( column=1, row=0, pady=0, padx=(0,2) )

	hexEntry = HexEditEntry( hexDisplayFrame, structOffset+8, 1, 'B', 'Ending Alpha' )
	hexEntry.insert( 0, hexData[8:10] )
	hexEntry.grid( column=1, row=1, pady=0, padx=(0,2) )
	hexEntry = HexEditEntry( hexDisplayFrame, structOffset+9, 1, 'B', 'Starting Alpha' )
	hexEntry.insert( 0, hexData[10:12] )
	hexEntry.grid( column=1, row=2, pady=0, padx=(0,2) )
	hexEntry = HexEditEntry( hexDisplayFrame, structOffset+0xA, 1, 'B', 'Edge Color Red Channel' )
	hexEntry.insert( 0, hexData[12:14] )
	hexEntry.grid( column=1, row=3, pady=0, padx=(0,2) )
	hexEntry = HexEditEntry( hexDisplayFrame, structOffset+0xB, 1, 'B', 'Edge Color Green Channel' )
	hexEntry.insert( 0, hexData[14:16] )
	hexEntry.grid( column=1, row=4, pady=0, padx=(0,2) )
	hexEntry = HexEditEntry( hexDisplayFrame, structOffset+0xC, 1, 'B', 'Edge Color Blue Channel' )
	hexEntry.insert( 0, hexData[16:18] )
	hexEntry.grid( column=1, row=5, pady=0, padx=(0,2) )
	hexEntry = HexEditEntry( hexDisplayFrame, structOffset+0xD, 1, 'B', 'Center Color Red Channel' )
	hexEntry.insert( 0, hexData[18:20] )
	hexEntry.grid( column=1, row=6, pady=0, padx=(0,2) )
	hexEntry = HexEditEntry( hexDisplayFrame, structOffset+0xE, 1, 'B', 'Center Color Green Channel' )
	hexEntry.insert( 0, hexData[20:22] )
	hexEntry.grid( column=1, row=7, pady=0, padx=(0,2) )
	hexEntry = HexEditEntry( hexDisplayFrame, structOffset+0xF, 1, 'B', 'Center Color Blue Channel' )
	hexEntry.insert( 0, hexData[22:24] )
	hexEntry.grid( column=1, row=8, pady=0, padx=(0,2) )

	hexDisplayFrame.pack()


def show20XXsupplementalData():
	# Gather data and build a few strings for the GUI
	structOffset = globalDatFile.headerInfo['stringTableStart'] + globalDatFile.getStringTableSize() # Relative to data section start
	locationText = 'Location:  0x{:X}'.format( 0x20 + structOffset )
	fileSizeText = 'Size:  0x{:X}'.format( globalDatFile.headerInfo['filesize'] - structOffset )

	ttk.Label( Gui.structurePropertiesFrame.interior, text='20XX HP Supplemental Data', font="-weight bold" ).pack( pady=12 )

	# Add info; need to encapsulate the file details text in a Frame so that pack and grid don't conflict
	emptyWidget = Tk.Frame( relief='flat' ) # This is used as a simple workaround for the labelframe, so we can have no text label with no label gap.
	basicDetailsFrame = ttk.Labelframe( Gui.structurePropertiesFrame.interior, labelwidget=emptyWidget, padding=(20, 4) )
	
	ttk.Label( basicDetailsFrame, text=locationText, wraplength=Gui.structPropFrameWrapLength ).grid( column=0, row=0, columnspan=2 )
	ttk.Label( basicDetailsFrame, text=fileSizeText, wraplength=Gui.structPropFrameWrapLength ).grid( column=0, row=1, columnspan=2 )

	basicDetailsFrame.pack( pady=0 )


def showKnownStructProperties( structure, guiFrame ):
	# tic = time.clock()

	structValues = structure.getValues()
	relativeFieldOffset = 0
	absoluteFieldOffset = structure.offset
	if structure.entryCount > 1:
		entrySize = structure.length / structure.entryCount
	else: entrySize = 0

	for i, field in enumerate( structure.fields ):
		# Collect info on this field
		propertyName = field.replace( '_', ' ' )
		fieldFormatting = structure.formatting[i+1]
		fieldByteLength = struct.calcsize( fieldFormatting )
		fieldValue = structValues[i]

		# If this is an array or table structure, add a little bit of spacing before each group of field entries
		if entrySize and ( relativeFieldOffset % entrySize == 0 ) and i > 0:
			verticalPadding = ( 10, 0 )
			firstOfNextEntry = True
		else:
			verticalPadding = ( 0, 0 )
			firstOfNextEntry = False

		# Add the property/field name, and a tooltip for its struct & file offsets
		if field: # May be an empty string if this field is unknown
			if firstOfNextEntry and entrySize > 4:
				fieldLabel = ttk.Label( guiFrame, text='{} -   {}:'.format((relativeFieldOffset/entrySize)+1, propertyName), wraplength=200 )
			else:
				fieldLabel = ttk.Label( guiFrame, text=propertyName + ':', wraplength=200 )
			fieldLabel.grid( column=0, row=i, padx=(0, 7), sticky='e', pady=verticalPadding )
			ToolTip( fieldLabel, text='Offset in struct: 0x{:X}\nOffset in file: 0x{:X}'.format(relativeFieldOffset, 0x20+absoluteFieldOffset), delay=300 )
		else:
			fieldLabel = ttk.Label( guiFrame, text=uHex( relativeFieldOffset ) + ':', wraplength=200 )
			fieldLabel.grid( column=0, row=i, padx=(0, 7), sticky='e', pady=verticalPadding )
			ToolTip( fieldLabel, text='Offset in file: 0x{:X}'.format(0x20+absoluteFieldOffset), delay=300 )

		# Add an editable field for the raw hex data
		hexEntry = HexEditEntry( guiFrame, absoluteFieldOffset, fieldByteLength, fieldFormatting, propertyName )
		hexEntry.insert( 0, hexlify(structure.data[relativeFieldOffset:relativeFieldOffset+fieldByteLength]).upper() )
		hexEntry.bind( '<Return>', updateEntryHex )
		hexEntry.grid( column=1, row=i, padx=(0,2), pady=verticalPadding )

		# Add something for the decoded value column
		if absoluteFieldOffset in globalDatFile.pointerOffsets: # It's a pointer
			PointerLink( guiFrame, fieldValue ).grid( column=2, row=i, pady=verticalPadding )

		elif 'Flags' in field:
			# Add the flag "Decode" button label, and the window creator handler
			flagsLabel = ttk.Label( guiFrame, text='Decode', foreground='#00F', cursor='hand2' )
			flagsLabel.grid( column=2, row=i, pady=verticalPadding )
			flagsLabel.bind( '<1>', lambda e, s=structure, fO=absoluteFieldOffset, vI=i: FlagDecoder(s, fO, vI) )

		# Add a color swatch if it's an RGBA color (this shows the color and makes for easy editing)
		elif field.startswith( 'RGBA' ):
			# Get the individual RGBA values from the field's value
			fieldValueHexString = '{0:0{1}X}'.format( fieldValue, 8 ) # Avoids the '0x' and 'L' appendages brought on by the hex() function. pads to 8 characters
			hexEntry.colorSwatch = ColorSwatch( guiFrame, fieldValueHexString, hexEntry )
			hexEntry.colorSwatch.grid( column=2, row=i, pady=verticalPadding )

		else:
			# Add an editable field for this field's actual decoded value (and attach the hex edit widget for later auto-updating)
			valueEntry = HexEditEntry( guiFrame, absoluteFieldOffset, fieldByteLength, fieldFormatting, propertyName )
			valueEntry.insert( 0, fieldValue )
			valueEntry.hexEntryWidget = hexEntry
			hexEntry.valueEntryWidget = valueEntry

			# Bind an event handler (pressing 'Enter' to save)
			valueEntry.bind( '<Return>', updateEntryValue )
			valueEntry.grid( column=2, row=i, pady=verticalPadding )

		relativeFieldOffset += fieldByteLength
		absoluteFieldOffset += fieldByteLength

	# toc = time.clock()
	# print 'time to draw known struct properties:', toc - tic


def showUnknownStructProperties( structure, guiFrame ):
	fieldOffset = 0
	tableRow = 0

	for i in range( len(structure.data) / 4 ):
		# Check if this is a pointer, and construct the field name for this property
		absoluteFieldOffset = structure.offset + fieldOffset
		if absoluteFieldOffset in globalDatFile.pointerOffsets:
			hexString = uHex( fieldOffset )
			numberOfSpaces = 5 - len( hexString )
			fieldName = hexString + numberOfSpaces * ' ' + ' (Pointer):'
		else:
			fieldName = uHex( fieldOffset ) + ':'

		# Add the property/field name, and a tooltip for its file offset
		fieldLabel = ttk.Label( guiFrame, text=fieldName )
		fieldLabel.grid( column=0, row=tableRow, padx=(0, 7), pady=0, sticky='w' )
		ToolTip( fieldLabel, text='Offset in file: 0x{:X}'.format(0x20+structure.offset+fieldOffset), delay=300 )

		# Add an editable field for the raw hex data
		hexEntry = HexEditEntry( guiFrame, absoluteFieldOffset, 4, None, structure.name )
		hexEntry.insert( 0, hexlify(structure.data[fieldOffset:fieldOffset+4]).upper() )
		hexEntry.bind( '<Return>', updateEntryHex )
		hexEntry.grid( column=1, row=tableRow, pady=0 )

		fieldOffset += 4
		tableRow += 1

		if absoluteFieldOffset in globalDatFile.pointerOffsets: # It's a pointer
			fieldValue = structure.getValues()[i]
			PointerLink( guiFrame, fieldValue ).grid( column=2, row=i, pady=0, padx=7 )


def showFrameDataStringParsing( frameObjString, structTable, infoPaneInterior ):
	# Get some info from the parent struct (a FObjDesc)
	parentOffset = frameObjString.getAnyDataSectionParent()
	parentStruct = globalDatFile.getStruct( parentOffset )
	_, _, startFrame, _, dataTypeAndScale, slopeDataTypeAndScale, _, _ = parentStruct.getValues()

	# Create a new frame to attach basic info to (since we want to use grid without interfering with pack)
	frameDetailsGrid = ttk.Frame( infoPaneInterior )

	ttk.Label( frameDetailsGrid, text='General Track Type:' ).grid( column=0, row=0, sticky='e', padx=(0, 10) )
	ttk.Label( frameDetailsGrid, text='Specific Track Type:' ).grid( column=0, row=1, sticky='e', padx=(0, 10) )

	# Add the general (and specific) track type
	trackNames = frameObjString.identifyTrack()
	ttk.Label( frameDetailsGrid, text=trackNames[0] ).grid( column=1, row=0, sticky='w' )
	ttk.Label( frameDetailsGrid, text=trackNames[1] ).grid( column=1, row=1, sticky='w' )

	# Parse the FObjString
	interpolationID, arrayCount, keyFrames = frameObjString.parse()

	# Display the opcode's interpolation type and array/keyframe count
	ttk.Label( frameDetailsGrid, text='Interpolation:' ).grid( column=0, row=2, sticky='e', padx=(0, 10) )
	ttk.Label( frameDetailsGrid, text='Keyframe Count:' ).grid( column=0, row=3, sticky='e', padx=(0, 10) )
	ttk.Label( frameDetailsGrid, text=frameObjString.interpolationTypes[interpolationID] ).grid( column=1, row=2, sticky='w' )
	ttk.Label( frameDetailsGrid, text=arrayCount ).grid( column=1, row=3, sticky='w' )

	# Display the data types used in the string
	ttk.Label( frameDetailsGrid, text='Data Type:' ).grid( column=0, row=4, sticky='e', padx=(0, 10) )
	ttk.Label( frameDetailsGrid, text='Data Scale:' ).grid( column=0, row=5, sticky='e', padx=(0, 10) )
	if interpolationID == 0 or interpolationID == 5:
		ttk.Label( frameDetailsGrid, text='Not Used' ).grid( column=1, row=4, sticky='w' )
		ttk.Label( frameDetailsGrid, text='Not Used' ).grid( column=1, row=5, sticky='w' )
	else:
		dataType = dataTypeAndScale >> 5 		# Use the first (left-most) 3 bits
		dataScale = 1 << ( dataTypeAndScale & 0b11111 ) 	# Use the last 5 bits
		ttk.Label( frameDetailsGrid, text=parentStruct.dataTypes[dataType][0] + 's' ).grid( column=1, row=4, sticky='w' )
		ttk.Label( frameDetailsGrid, text='1 / {} ({})'.format(dataScale, 1.0/dataScale) ).grid( column=1, row=5, sticky='w' )

	# Display the slope/tangent data types used in the string
	ttk.Label( frameDetailsGrid, text='Slope Data Type:' ).grid( column=0, row=6, sticky='e', padx=(0, 10) )
	ttk.Label( frameDetailsGrid, text='Slope Data Scale:' ).grid( column=0, row=7, sticky='e', padx=(0, 10) )
	if interpolationID == 4 or interpolationID == 5:
		slopeDataType = slopeDataTypeAndScale >> 5 			# Use the first (left-most) 3 bits
		slopeDataScale = 1 << ( slopeDataTypeAndScale & 0b11111 ) 	# Use the last 5 bits
		ttk.Label( frameDetailsGrid, text=parentStruct.dataTypes[slopeDataType][0] + 's' ).grid( column=1, row=6, sticky='w' )
		ttk.Label( frameDetailsGrid, text='1 / {} ({})'.format(slopeDataScale, 1.0/slopeDataScale) ).grid( column=1, row=7, sticky='w' )
	else:
		ttk.Label( frameDetailsGrid, text='Not Used' ).grid( column=1, row=6, sticky='w' )
		ttk.Label( frameDetailsGrid, text='Not Used' ).grid( column=1, row=7, sticky='w' )

	frameDetailsGrid.pack( pady=(14, 0) )

	# Start a new frame for the keyframe data, and create a table header
	if len( keyFrames ) < 40: # Avoid loading up the GUI too much; could bog it down. Needs testing
		keyFramesFrame = ttk.Frame( infoPaneInterior )
		ttk.Label( keyFramesFrame, text='Keyframes / States', font="-weight bold" ).grid( column=0, row=0, columnspan=2 )
		ttk.Label( keyFramesFrame, text='Start Frame:' ).grid( column=2, row=1, padx=3 )
		ttk.Label( keyFramesFrame, text=startFrame ).grid( column=3, row=1, padx=3 )
		ttk.Label( keyFramesFrame, text='Keyframe:' ).grid( column=0, row=2, padx=3 )
		ttk.Label( keyFramesFrame, text='Data Value:' ).grid( column=1, row=2, padx=3 )
		ttk.Label( keyFramesFrame, text='Slope Value:' ).grid( column=2, row=2, padx=3 )
		ttk.Label( keyFramesFrame, text='Target Frame:' ).grid( column=3, row=2, padx=3 )

		# Display the keyframe data
		frameCount = startFrame
		csvFormatText = []
		row = 3
		for dataValue, tangent, frameWait in keyFrames:
			ttk.Label( keyFramesFrame, text=row - 2 ).grid( column=0, row=row )
			ttk.Label( keyFramesFrame, text=dataValue ).grid( column=1, row=row )
			ttk.Label( keyFramesFrame, text=tangent ).grid( column=2, row=row )
			ttk.Label( keyFramesFrame, text=frameCount ).grid( column=3, row=row )
			csvFormatText.append( '{}, {}, {}'.format(dataValue, tangent, frameCount) )

			frameCount += frameWait
			row += 1

		# Set the end frame, taken from the grandparent Animation Object
		animParentOffset = parentStruct.getAnyDataSectionParent()
		animParentStruct = globalDatFile.getStruct( animParentOffset )
		endFrame = animParentStruct.getValues( 'End_Frame' )
		ttk.Label( keyFramesFrame, text='End Frame:' ).grid( column=2, row=row )
		ttk.Label( keyFramesFrame, text=endFrame ).grid( column=3, row=row )

		keyFramesFrame.pack( pady=(14, 0) )
	else:
		ttk.Label( infoPaneInterior, text='Avoiding Full Analysis;\nlarge array length detected.' ).pack( pady=(14, 0) )
		csvFormatText = []
		for dataValue, tangent, frameWait in keyFrames:
			csvFormatText.append( '{}, {}, {}'.format(dataValue, tangent, startFrame) )

	# Repackage the data so that it can be collected and used by the user in other ways
	csvFormatText = '\n'.join( csvFormatText )
	label = ttk.Label( infoPaneInterior, text='Show Keyframes in CSV Format', foreground='#00F', cursor='hand2' )
	label.pack( pady=(9, 0) )
	label.bind( '<1>', lambda event, message=csvFormatText, title=frameObjString.name + ' Keyframes': cmsg(message, title) )
	label = ttk.Label( infoPaneInterior, text='Show Keyframes in TSV Format', foreground='#00F', cursor='hand2' )
	label.pack( pady=(3, 0) )
	label.bind( '<1>', lambda event, message=csvFormatText.replace(', ', '\t'), title=frameObjString.name + ' Keyframes': cmsg(message, title) )


def onStructureTreeSelect( event ):

	""" This is called upon a structure in the Structure Tree being selected.
		This will populate the right-hand panel with the structure's name and basic 
		information (including handlers for clicking on some of them), and will then kick 
		off a separate function for displaying the structure's values and their offsets. """

	# Destroy the existing widgets in the properties frame
	Gui.structurePropertiesFrame.clear()

	iid = str( Gui.fileStructureTree.selection()[0] )
	itemName = Gui.fileStructureTree.item( iid, 'text' )
	Gui.structurePropertiesFrame.structTable = None

	if itemName == 'File Header':
		showFileProperties()
		return
	elif itemName == 'Relocation Table':
		showRelocationTableInfo()
		return
	elif itemName == 'Root Nodes Table':
		showNodeTableInfo( itemName )
		return
	elif itemName == 'Reference Nodes Table':
		showNodeTableInfo( itemName )
		return
	elif itemName == 'String Table':
		showStringTableInfo()
		return
	elif itemName == 'Sword Swing Colors':
		showSwordSwingInfo()
		return
	elif itemName == '20XX HP Supplemental Data':
		show20XXsupplementalData()
		return
	elif itemName == 'Orphan Structures':
		orphanNotes = ( 'Orphan structures are not attached to the file structure tree in the usual way (i.e. having '
						'parents that lead all the way up to the root/reference node tables).' )
		ttk.Label( Gui.structurePropertiesFrame.interior, text=orphanNotes, wraplength=Gui.structPropFrameWrapLength ).pack( pady=(36,0) )
		return

	# Get the struct offset and the initialized struct object itself
	structOffset = int( iid.split( '/' )[-1] )
	structure = globalDatFile.structs[structOffset]

	# Display the structure's name and label
	ttk.Label( Gui.structurePropertiesFrame.interior, text=structure.name, font="-weight bold" ).pack( pady=(12,0) )
	if structure.label:
		ttk.Label( Gui.structurePropertiesFrame.interior, text=structure.label, font="-weight bold" ).pack( pady=(3, 0) )

	# Add a "button" for help text
	helpText = ( 'Offsets shown on the left (for unknown structs) are absolute file offsets. However, keep in mind that pointers '
				 "shown on the right, the actual values in the file, are relative to the file's data section (meaning they do not "
				 'account for the 0x20 file header, and will be that much smaller than the actual file offset).\n\n'

				 'If a structure has multiple parents, it may appear under multiple branches, thus the addition of all branch'
				 'sizes will be larger than the total file size.' )
	addHelpBtn( helpText )
	
	# Gather struct info
	structParents = structure.getParents( includeNodeTables=True )
	structSiblings = structure.getSiblings()
	structChildren = structure.getChildren()

	# Add general struct info; need to encapsulate these in a Frame so that pack and grid don't conflict
	emptyWidget = Tk.Frame( relief='flat' ) # This is used as a simple workaround for the labelframe, so we can have no text label with no label gap.
	basicDetailsFrame = ttk.Labelframe( Gui.structurePropertiesFrame.interior, labelwidget=emptyWidget, padding=(20, 4) )

	# Get the structure depth
	if iid.startswith( 'orphans' ):
		structDepthText = 'N/A'
	else:
		depth = structure.getStructDepth()
		if depth:
			fileDepth, siblingIndex = depth
			structDepthText = '{}, {}'.format( fileDepth, siblingIndex )
		else: # Failsafe; not expected
			structDepthText = str(getTreeviewDepth( Gui.fileStructureTree, iid )) + ', n/a'

		# General Struct Info, column 1 (parents/sibs/children text)
	ttk.Label( basicDetailsFrame, text='Parents:' ).grid( column=0, row=0, sticky='e', padx=(0, 5) )
	ttk.Label( basicDetailsFrame, text='Siblings:' ).grid( column=0, row=1, sticky='e', padx=(0, 5) )
	ttk.Label( basicDetailsFrame, text='Children:' ).grid( column=0, row=2, sticky='e', padx=(0, 5) )

		# General Struct Info, column 2 (parents/sibs/children info/links)
	if structParents:
		structParentsString = ', '.join([ uHex(0x20+offset) for offset in structParents ])
		parentsCountLabel = ttk.Label( basicDetailsFrame, text=len(structParents), foreground='#00F', cursor='hand2' )
		#showBtn = ( 'Show', showStructInStructuralAnalysis(targetStructOffset) )
		parentsCountLabel.bind( '<1>', lambda event, message=structParentsString, title=structure.name + ' Parents': cmsg(message, title) )
	else:
		parentsCountLabel = ttk.Label( basicDetailsFrame, text='0' )
	if structSiblings:
		structSiblingsString = ', '.join([ uHex(0x20+offset) for offset in structSiblings ])
		siblingsCountLabel = ttk.Label( basicDetailsFrame, text=len(structSiblings), foreground='#00F', cursor='hand2' )
		siblingsCountLabel.bind( '<1>', lambda event, message=structSiblingsString, title=structure.name + ' Siblings': cmsg(message, title) )
	else:
		siblingsCountLabel = ttk.Label( basicDetailsFrame, text='0' )
	if structChildren:
		structChildrenString = ', '.join([ uHex(0x20+offset) for offset in structChildren ])
		childrenCountLabel = ttk.Label( basicDetailsFrame, text=len(structChildren), foreground='#00F', cursor='hand2' )
		childrenCountLabel.bind( '<1>', lambda event, message=structChildrenString, title=structure.name + ' Children': cmsg(message, title) )
	else:
		childrenCountLabel = ttk.Label( basicDetailsFrame, text='0' )
	parentsCountLabel.grid( column=1, row=0, sticky='w' )
	siblingsCountLabel.grid( column=1, row=1, sticky='w' )
	childrenCountLabel.grid( column=1, row=2, sticky='w' )

		# General Struct Info, column 3 (size/position text)
	ttk.Label( basicDetailsFrame, text='Length:' ).grid( column=2, row=0, sticky='e', padx=(20,5) )
	ttk.Label( basicDetailsFrame, text='Struct Depth:' ).grid( column=2, row=1, sticky='e', padx=(20,5) )
	if structChildren:
		ttk.Label( basicDetailsFrame, text='Branch Size:' ).grid( column=2, row=2, sticky='e', padx=(20,5) )

		# General Struct Info, column 4 (size/position info)
	structLengthText = uHex( structure.length ) if structure.length != -1 else 'Unknown'
	ttk.Label( basicDetailsFrame, text=structLengthText ).grid( column=3, row=0, sticky='w' )
	ttk.Label( basicDetailsFrame, text=structDepthText ).grid( column=3, row=1, sticky='w' )

		# Branch Size Info
	if structChildren:
		if structure.branchSize == -1: # Not yet known; leave it up to the user to begin calculation
			def calculateBranchSize( event ): # This can take some time (5-10 seconds), so lets not make it happen automatically
				branchSize = uHex( structure.getBranchSize() )
				branchSizeValueLabel['text'] = branchSize
				branchSizeValueLabel['foreground'] = Gui.globalFontColor
				branchSizeValueLabel['cursor'] = ''

			branchSizeValueLabel = ttk.Label( basicDetailsFrame, text='[Calculate]', foreground='#00F', cursor='hand2' )
			branchSizeValueLabel.grid( column=3, row=2, sticky='w' )
			branchSizeValueLabel.bind( '<1>', calculateBranchSize )
		else:
			ttk.Label( basicDetailsFrame, text=uHex(structure.branchSize) ).grid( column=3, row=2, sticky='w' )

	if structure.entryCount != -1:
		paddingNotice = ttk.Label( basicDetailsFrame, text='Entry Count:       {}'.format(structure.entryCount) )
		paddingNotice.grid( column=0, row=3, columnspan=4, pady=(0, 0) )

	if structure.padding:
		paddingNotice = ttk.Label( basicDetailsFrame, text='Trailing Padding:  0x{:X}'.format(structure.padding) )
		paddingNotice.grid( column=0, row=4, columnspan=4, pady=(0, 0) )

	basicDetailsFrame.pack( pady=(16, 0) )

	# Nothing else to show for raw image and palette data blocks
	if issubclass( structure.__class__, hsdStructures.DataBlock ) and not structure.__class__ == hsdStructures.FrameDataBlock:
		return
	elif structure.length > 0x1000:
		print 'struct is > 0x1000 bytes. skipping struct unpacking.' # This would be slow
		return

	# Build a table showing the fields and values in this structure
	Gui.structurePropertiesFrame.structTable = structTable = ttk.Frame( Gui.structurePropertiesFrame.interior, padding='0 12 0 12' ) # Left, Top, Right, Bottom.

	if structure.__class__ == hsdStructures.FrameDataBlock:
		showFrameDataStringParsing( structure, structTable, Gui.structurePropertiesFrame.interior )

	elif structure.fields:
		showKnownStructProperties( structure, structTable )

	else:
		if structure.padding != 0:
			print 'Non-0 padding for unknown struct; {}. Something may have initialized improperly.'.format( structure.padding )

		showUnknownStructProperties( structure, structTable )

	structTable.pack()


def addSingleStructure( structure, structIid, parentIid, makeExpanded=False ):
	# Add this struct if it hasn't already been added
	if not Gui.fileStructureTree.exists( structIid ):
		# Check if this is a stage file General Point, to modify the name shown
		structName = ''
		fileDepth, siblingId = structure.getStructDepth()
		if fileDepth == 4 or fileDepth == 5:
			iidParts = structIid.split( '/' )
			if len( iidParts ) > 3: # Failsafe
				potentialGeneralPointArrayOffset = int( iidParts[3] )
				potentialGeneralPointArray = globalDatFile.getStruct( potentialGeneralPointArrayOffset )
				if potentialGeneralPointArray.__class__ == hsdStructures.MapGeneralPointsArray:
					if fileDepth == 4 and structure.__class__ == hsdStructures.JointObjDesc:
						structName = 'General Points'
					elif fileDepth == 5:
						structName = structure.getGeneralPointType()
						if not structName:
							structName = 'General Point'

		# Formulate the struct name
		if not structName:
			if structure.label:
				structName = structure.label
			else:
				structName = ' '.join( structure.name.split()[:-1] ) # Removes just the offset from the name (it's already in the GUI and thus redundant here)
				if siblingId != 0:
					structName += ' ' + str( siblingId + 1 )

		Gui.fileStructureTree.insert( parentIid, 'end', iid=structIid, text=structName, values=uHex(0x20 + structure.offset), open=makeExpanded )
		Gui.fileStructureTree.allIids.append( structIid )

	elif makeExpanded: # The item has already been added; make sure it's open
		Gui.fileStructureTree.item( structIid, open=True )


def addSiblingStructures( structure, parentIid ):
	for sibOffset in structure.getSiblings():
		sibStruct = globalDatFile.getStruct( sibOffset )
		sibIid = parentIid + '/' + str( sibOffset )

		addSingleStructure( sibStruct, sibIid, parentIid )


def addChildStructures( structure, parentIid ):
	for childOffset in structure.getChildren():
		childStruct = globalDatFile.getStruct( childOffset, structure.offset )
		childIid = parentIid + '/' + str( childOffset )

		addSingleStructure( childStruct, childIid, parentIid )


def addTreeFragment( parentIid, structure=None, structOffset=-1, parentOffset=-1, structDepth=None ):

	""" Adds part of a family or local node group to the treeview, including the initial item or structure given. 
		If the target struct will be visible, this also adds the target structure's siblings and children.
		If a structure is not provided, structOffset is required. """

	if not structure:
		structure = globalDatFile.getStruct( structOffset, parentOffset, structDepth )
		#print 'adding struct', structure.name, '  parents:', structure.getParents(), hex(0x20+parentOffset)
		assert structure, 'Unable to create or get a structure for ' + uHex(0x20+structOffset)

	# Add the target struct
	newStructIid = parentIid + '/' + str( structure.offset )
	addSingleStructure( structure, newStructIid, parentIid )

	# If this item will be visible (i.e. the parent item is open), its siblings and children should be present
	if Gui.fileStructureTree.item( parentIid, 'open' ):
		addSiblingStructures( structure, parentIid )
		addChildStructures( structure, newStructIid )


def growStructuralAnalysisTree( event, iid=None ):

	""" This function initializes and adds lower-level structures to an already existing item in 
		the Structural Analysis treeview. The item given or clicked on to trigger this is expected 
		to already have its children created (but not necessarily the childrent's siblings, to 
		improve performance), which means this will mostly just be adding its grandchildren. """

	if not iid:
		iid = str( Gui.fileStructureTree.selection()[0] )
	if iid == '-32': return # The header was clicked on; everything at this level has already been added

	# Add all siblings for the children of the item that was clicked on
	for childIid in Gui.fileStructureTree.get_children( iid ):
		childOffset = int( childIid.split( '/' )[-1] )
		childStruct = globalDatFile.structs[childOffset]
		addSiblingStructures( childStruct, iid )

	# Re-iterate over the treeview children, which will now include siblings
	for childIid in Gui.fileStructureTree.get_children( iid ):
		childOffset = int( childIid.split( '/' )[-1] )
		childStruct = globalDatFile.structs[childOffset]

		# Add the children of the current child (grandchildren to item clicked on),
		# so that the current child will show a '+' icon and can subsequently be browsed.
		addChildStructures( childStruct, childIid )

	adjustSavColumnWidth( iid )


def addParentStructures( structOffset, parentOffset=-1, structDepth=None, initialCall=False ):

	""" Recursively identifies parent structures, and adds them to the treeview, until the target struct can be added. 
		This works by working its way up the file structure tree towards the root/ref node tables, and then processing 
		those higher-level structures first. This ensures higher confidence in identifying lower branches. """

	# Prevent a ton of redundant tree attachments
	existingEntity = globalDatFile.structs.get( structOffset )
	if isinstance( existingEntity, hsdStructures.EnvelopeObjDesc ):
		return

	# Get the closest upward relative (parent or sibling) to this structure; either from an existing struct, or by scanning the file's pointers.
	if existingEntity and not isinstance( existingEntity, (str, hsdStructures.structBase) ): # Found a known struct, not a hint or generic struct
		parentStructOffsets = Set( existingEntity.getParents(True) ) # Need to make a copy of this set, since we don't want to modify the original
	else:
		parentStructOffsets = Set()

		for pointerOffset, pointerValue in globalDatFile.pointers:
			if pointerValue == structOffset:
				offset = globalDatFile.getPointerOwner( pointerOffset, offsetOnly=True )
				parentStructOffsets.add( offset )

	# Ensure there's something to add (and it's not recursive)
	if not parentStructOffsets or parentStructOffsets == [structOffset]:
		# Add the Orphan root element in the treeview if it doesn't already exist
		if not Gui.fileStructureTree.exists( 'orphans' ):
			Gui.fileStructureTree.insert( '', 'end', iid='orphans', text='Orphan Structures', values='' )

		print 'Skipped adding branch to struct', uHex(0x20+structOffset), 'because it seems to be an orphan'
		return

	# Remove key structure offsets from the set, to avoid recursively adding this struct to itself, 
	# or to the root/ref node tables (those structs will already be added, or it's a label reference)
	parentStructOffsets.difference_update( [structOffset, globalDatFile.headerInfo['rtEnd'], globalDatFile.headerInfo['rootNodesEnd']] )
	if not parentStructOffsets: return

	# Enter a recursive loop to add all parent structs, all the way up to the root or reference nodes tables (this could be a unique branch)
	for offset in parentStructOffsets:
		addParentStructures( offset )

	# At this point on, we are executing for the highest level parent (1st-level/root structs) first, so we can actually initialize the structures now
	structure = globalDatFile.getStruct( structOffset, parentOffset, structDepth )
	if not initialCall:
		if isinstance( structure, hsdStructures.EnvelopeObjDesc ):
			#print 'Found inf. matrix array; canceling AFTER addParentStructures call'
			return

	# Find all instances of this structure's parents in the treeview, and add the new structure to each of them
	for parentIid in getStructureIids( parentStructOffsets ):
		# Check if this parent is a sibling of the current struct, to know whether to open it and add more structs
		thisParentOffset = int( parentIid.split( '/' )[-1] )
		parentIsSibling = structure.isSibling( thisParentOffset )
		
		# The current structure will have been added by the true parent's 'grow' call, so we can skip siblings
		if not parentIsSibling:
			Gui.fileStructureTree.item( parentIid, open=True )
			growStructuralAnalysisTree( None, parentIid )


def clearStructuralAnalysisTab( restoreBackground=False ):
	# Add or remove the background drag-n-drop image
	if restoreBackground:
		Gui.fileStructureTreeBg.place( relx=0.5, rely=0.5, anchor='center' )
	else: # This function removes them by default
		Gui.fileStructureTreeBg.place_forget()

	# Clear the Structural Analysis tab.
	for item in Gui.fileStructureTree.get_children(): Gui.fileStructureTree.delete( item )
	Gui.structurePropertiesFrame.clear()

	Gui.fileStructureTree.allIids = [] # Used for searching for structs


def analyzeDatStructure():
	try:
		tic = time.clock()

		# Reset the column widths and horizontal scrollbar
		structureTreeWidth = Gui.fileStructureTree.winfo_width()
		if structureTreeWidth > 10: # If the Gui hasn't finished rendering, this width should be 1 (so the resize should be avoided)
			offsetColumnWidth = Gui.fileStructureTree.column( 'offset' )['width']
			newMainColumnWidth = structureTreeWidth - offsetColumnWidth - 2
			Gui.fileStructureTree.column( '#0', width=newMainColumnWidth )

		# Get the file name and check that it's one that can be processed
		fileName = globalDatFile.fileName
		if fileName.lower().endswith( 'aj.dat' ): # Unsupported atm; no relocation tables
			print "Animation files are not yet supported. Lmk if you'd like to see them."
			ttk.Label( Gui.structurePropertiesFrame.interior, text='Animation files are not yet supported.', wraplength=Gui.structPropFrameWrapLength ).pack( pady=(12,0) )
			ttk.Label( Gui.structurePropertiesFrame.interior, text="Let me know if you'd like to see them.", wraplength=Gui.structPropFrameWrapLength ).pack( pady=(12,0) )
			return

		hI = globalDatFile.headerInfo
		rootNodesTableStart = hI['rtEnd']
		refNodesTableStart = hI['rootNodesEnd']
		stringTableOffset = hI['stringTableStart']

		# Set the filename atop the filetree
		if len( fileName ) > 35: fileName = fileName[:32] + '...'
		Gui.fileStructureTree.heading( '#0', anchor='center', text=fileName )

		# Add the file header and relocation table
		Gui.fileStructureTree.insert( '', 'end', iid='-32', text='File Header', values='0', open=True )
		rtIid = '-32/' + str( hI['rtStart'] )
		Gui.fileStructureTree.insert( '-32', 'end', iid=rtIid, text='Relocation Table', values=uHex(0x20+hI['rtStart']), open=True )
		Gui.fileStructureTree.allIids = [ '-32', rtIid ]

		# Add the root node table and its decendants
		if globalDatFile.rootStructNodes:
			nodesTableIid = '-32/' + str( rootNodesTableStart )
			Gui.fileStructureTree.insert( '-32', 'end', iid=nodesTableIid, text='Root Nodes Table', values=uHex(0x20+rootNodesTableStart), open=True )
			Gui.fileStructureTree.allIids.append( nodesTableIid )

			# Add the root node table's decendants
			for node in globalDatFile.rootStructNodes: # Each node is a tuple of (structureOffset, string)
				addTreeFragment( nodesTableIid, structOffset=node[0], parentOffset=rootNodesTableStart, structDepth=(2, 0) )

		# Add the reference node table and its decendants
		if globalDatFile.refStructNodes:
			nodesTableIid = '-32/' + str( refNodesTableStart )
			Gui.fileStructureTree.insert( '-32', 'end', iid=nodesTableIid, text='Reference Nodes Table', values=uHex(0x20+refNodesTableStart), open=True )
			Gui.fileStructureTree.allIids.append( nodesTableIid )

			# Add the reference node table's decendants
			for node in globalDatFile.refStructNodes: # Each node is a tuple of (structureOffset, string)
				addTreeFragment( nodesTableIid, structOffset=node[0], parentOffset=refNodesTableStart, structDepth=(2, 0) )

		# Add the string table
		stringTableIid = '-32/' + str( stringTableOffset )
		Gui.fileStructureTree.insert( '-32', 'end', iid=stringTableIid, text='String Table', values=uHex(0x20+stringTableOffset) )
		Gui.fileStructureTree.allIids.append( stringTableIid )

		# Check for and add tail data (that appearing after the normal end of the file)
		if globalDatFile.tailData:
			addTailData()

		# Display the default panel
		showFileProperties()

		toc = time.clock()
		print 'structural analysis time for', fileName + ':', toc - tic

	except Exception as err:
		ttk.Label( Gui.structurePropertiesFrame.interior,
			text="The structure of this file could not be determined.", 
			wraplength=Gui.structPropFrameWrapLength ).pack( pady=16 )
		print err

	updateProgramStatus( 'Analysis Complete' )


def addTailData():
	dataStart = 0x20 + globalDatFile.headerInfo['stringTableStart'] + globalDatFile.getStringTableSize()

	# Determine what it is and add it to the SA tab
	if len( globalDatFile.tailData ) == 0xC and globalDatFile.tailData[:4] == bytearray( b'\x53\x52\x47\x42' ): # Looking for the hex "SRGB"
		# Found Sword Swing Color data
		Gui.fileStructureTree.insert( '', 'end', iid=str(dataStart), text='Sword Swing Colors', values=uHex(0x20+dataStart) )
		Gui.fileStructureTree.allIids.append( str(dataStart) )

	elif globalDatFile.rootNodes == [ (0, 'MnSelectChrDataTable') ]:
		Gui.fileStructureTree.insert( '', 'end', iid=str(dataStart), text='20XX HP Supplemental Data', values=uHex(0x20+dataStart) )
		Gui.fileStructureTree.allIids.append( str(dataStart) )


def performDeepDive():
	
	""" This fully instantiates all structures within the file, looking for orphan structs,
		and counts instances of all identified structures. """

	# Determine the number of structs in only the data section of the file (remove 1 for header, RT, root/ref nodes, and string table)
	if globalDatFile.headerInfo['rootNodesEnd'] == globalDatFile.headerInfo['stringTableStart']: # Has no reference nodes table
		nonDataSectionStructs = 4
	else: nonDataSectionStructs = 5
	dataSectionStructsCount = len( globalDatFile.structureOffsets ) - nonDataSectionStructs

	# Check if this operation has already been perfomed on this file
	if not globalDatFile.deepDiveStats:
		# Disable the deep dive button
		buttonsFrame = Gui.structurePropertiesFrame.interior.winfo_children()[-1]
		deepDiveBtn = buttonsFrame.winfo_children()[-1]
		deepDiveBtn['state'] = 'disabled'

		# If this may be slow, show a 'please wait' message to show that something is happening
		if dataSectionStructsCount < 2000:
			plsWaitMessage = ''
		elif dataSectionStructsCount < 5000:
			plsWaitMessage = 'Performing Deep-Dive....'
		else:
			plsWaitMessage = 'Performing Deep-Dive. Please wait; this may take a few moments....'

		if plsWaitMessage:
			plsWaitLabel = ttk.Label( Gui.structurePropertiesFrame.interior, text=plsWaitMessage, wraplength=Gui.structPropFrameWrapLength )
			plsWaitLabel.pack( pady=12 )
			plsWaitLabel.update() # So it will be shown before the process below begins

		# Parse the data section of the file (avoided during initial file loading to save on time)
		print '\nBeginning deep-dive'
		tic = time.clock()
		globalDatFile.parseDataSection()
		toc = time.clock()
		print 'time to fully parse data section', toc - tic, '\n'
		print len(globalDatFile.structureOffsets), 'total file structures identified by primary methods'
		print len(globalDatFile.structs), 'total structs initialized from data section (not counting header, RT, root/ref node tables, string table)'

		# Remove the please wait message, if used
		if plsWaitMessage:
			plsWaitLabel.destroy()

		# Count instances of each kind of structure
		for structure in globalDatFile.structs.values():
			structClass = structure.__class__.__name__

			if structClass == 'str': structClass = 'structBase' # todo: needs a proper fix; string hints should be resolved to actual structures by now

			if structClass not in globalDatFile.deepDiveStats:
				globalDatFile.deepDiveStats[structClass] = 1
			else:
				globalDatFile.deepDiveStats[structClass] += 1

	unidentifiedStructs = globalDatFile.deepDiveStats.get( 'structBase', 0 )
	structsIdentified = dataSectionStructsCount - unidentifiedStructs

	# Display the counts for each structure found
	ttk.Label( Gui.structurePropertiesFrame.interior, text='Total Structs Identified:   {} of {}'.format(structsIdentified, dataSectionStructsCount) ).pack( pady=(12, 0) )
	ttk.Label( Gui.structurePropertiesFrame.interior, text='Total Identification Rate:    {}'.format(format( float(structsIdentified) / dataSectionStructsCount, '.2%' )) ).pack( pady=(0, 12))
	print 'structs identified:', structsIdentified, 'of', dataSectionStructsCount
	print 'total identification rate: ' + str( round(( float(structsIdentified) / dataSectionStructsCount * 100 ), 2) ) + '%'

	classCountFrame = ttk.Frame( Gui.structurePropertiesFrame.interior )
	row = 0
	padx = 5
	for className, classCount in sorted( globalDatFile.deepDiveStats.items() ):
		if className == 'structBase': continue # Skip it, so we can be sure to add it last
		ttk.Label( classCountFrame, text=className + ':' ).grid( column=0, row=row, padx=padx )
		ttk.Label( classCountFrame, text=classCount ).grid( column=1, row=row, padx=padx )
		ttk.Label( classCountFrame, text=format( float(classCount) / dataSectionStructsCount, '.3%' ) ).grid( column=2, row=row, padx=padx )
		row += 1

	ttk.Label( classCountFrame, text='Unidentified Structs:' ).grid( column=0, row=row, padx=padx )
	ttk.Label( classCountFrame, text=unidentifiedStructs ).grid( column=1, row=row, padx=padx )
	ttk.Label( classCountFrame, text=format( float(unidentifiedStructs) / dataSectionStructsCount, '.3%' ) ).grid( column=2, row=row, padx=padx )
	classCountFrame.pack()

	# Determine existance of orphan structures
	if not globalDatFile.orphanStructures:
		ttk.Label( Gui.structurePropertiesFrame.interior, text='All Structures Initialized' ).pack( pady=(12, 0) )

	elif len( globalDatFile.structs ) == dataSectionStructsCount:
		orphansText = '{} structures identified but not initialized. May be orphans or children of orphans.'.format( len(globalDatFile.orphanStructures) )
		ttk.Label( Gui.structurePropertiesFrame.interior, text=orphansText, wraplength=Gui.structPropFrameWrapLength ).pack( pady=(12, 0) )

		orphansToAdd = []
		for orphanStructOffset in globalDatFile.orphanStructures:

			# Initialize or get a structure object
			orphanStruct = globalDatFile.getStruct( orphanStructOffset )
			if not orphanStruct: continue

			# Check if it's really on its own (may have parents, just not grandparents or great grandparents, etc)
			orphanParents = orphanStruct.getParents( includeNodeTables=True )
			#print 'orphan', orphanStruct.name ,'parent(s):', [hex(o+0x20) for o in orphanParents]

			if len( orphanParents ) == 0:
				#print 'orphan struct has 0 parents;', orphanStruct.name
				pass

			elif len( orphanParents ) == 1 and orphanStruct.offset in orphanParents:
				# orphanIid = 'orphans/' + str( orphanStruct.offset )
				# addTreeFragment( 'orphans', structure=orphanStruct )
				#print 'orphan struct has 1 parents: itself;', orphanStruct.name
				pass

			else: # Not a true orphan itself
				#print 'non-true orphan:', orphanStruct.name
				continue

			orphansToAdd.append( orphanStruct )

		if orphansToAdd:
			orphansText2 = 'Found {} top-level orphans (displayed in structure tree).'.format( len(orphansToAdd) )
			ttk.Label( Gui.structurePropertiesFrame.interior, text=orphansText2, wraplength=Gui.structPropFrameWrapLength ).pack( pady=(12, 0) )

			# Add the Orphan root element in the treeview if it doesn't already exist
			if not Gui.fileStructureTree.exists( 'orphans' ):
				Gui.fileStructureTree.insert( '', 'end', iid='orphans', text='Orphan Structures', values='', open=False )

			for orphanStruct in orphansToAdd:
				#orphanIid = 'orphans/' + str( orphanStruct.offset )
				addTreeFragment( 'orphans', structure=orphanStruct )
		else:
			ttk.Label( Gui.structurePropertiesFrame.interior, text='No top-level orphans found.' ).pack( pady=(12, 0) )

	else:
		failedInitNotice = '{} data section structs could not be initialized.'.format( dataSectionStructsCount - len( globalDatFile.structs ) )
		ttk.Label( Gui.structurePropertiesFrame.interior, text=failedInitNotice, wraplength=Gui.structPropFrameWrapLength ).pack( pady=(12, 0) )


class structSearchWindow( basicWindow ):

	def __init__( self ):
		basicWindow.__init__( self, Gui.root, 'Structure Search', dimensions=(280, 200) )

		ttk.Label( self.mainFrame, text="Enter an offset and press Enter to search for a structure "
										"at that offset, or for the structure that contains it.", wraplength=260 ).pack( pady=4 )
		self.offsetEntry = ttk.Entry( self.mainFrame, width=8, justify='center' )
		self.offsetEntry.pack( padx=5, pady=2 )
		self.offsetEntry.bind( '<Return>', self.searchForStruct )
		self.offsetEntry.focus()

		# Set up a space for results
		self.resultsFrame = ttk.Frame( self.mainFrame )
		self.resultsFrame.pack()

	def searchForStruct( self, event ):
		if not globalDatFile:
			msg( 'No DAT file has been loaded.' )
			return

		# Remove current information/results displayed for the structure
		for child in self.resultsFrame.winfo_children(): child.destroy()

		enteredString = self.offsetEntry.get()

		# Get the entered value and validate it
		if not enteredString or not ',' in enteredString:
			# Looking for one value
			try:
				targetOffsets = [ int(enteredString, 16) - 0x20 ] # Subtracting 0x20 to make this relative to the data section.
				if targetOffsets[0] < -0x20: raise ValueError() # C'mon, man
			except:
				msg( 'Invalid offset given. Please enter a positive hex value.' )
				return

		else: # User likely wants to find multiple structures
			try:
				targetOffsets = [ int(subString, 16) - 0x20 for subString in enteredString.split(',') ]
				for offset in targetOffsets:
					if offset < -0x20: raise ValueError() # C'mon, man
			except:
				msg( 'Invalid offset given. Please enter positive hex values.' )
				return

		# Define a few things to prepare for validation
		rtEnd = globalDatFile.headerInfo['rtEnd']
		filesize = globalDatFile.headerInfo['filesize']
		dataSectionEnd = globalDatFile.headerInfo['rtStart']
		stringTableStart = globalDatFile.headerInfo['stringTableStart']

		# Validate the input
		for offset in targetOffsets:
			if len( targetOffsets ) == 1: messageStart = 'This offset'
			else: messageStart = 'The offset ' + uHex( 0x20 + offset ) # Multiple given; need to be specific
			errorMessage = ''

			if offset < 0: # This is within the file header
				Gui.fileStructureTree.see( '' )
				errorMessage = '{} is within the file header.'.format( messageStart )

			elif offset >= dataSectionEnd:
				if offset < rtEnd:
					errorMessage = '{} is within the Relocation Table, which extends from {:X} to {:X}.'.format( messageStart, 0x20+dataSectionEnd, 0x20+rtEnd )
				elif offset < stringTableStart:
					errorMessage = '{} is within the Root/Reference Node Tables, which extend from {:X} to {:X}.'.format( messageStart, 0x20+rtEnd, 0x20+stringTableStart )
				elif offset + 0x20 < filesize:
					errorMessage = '{} is within the String Table, which extends from {:X} to {:X}.'.format( messageStart, 0x20+stringTableStart, filesize )
				else:
					errorMessage = '{0} is beyond the bounds of the file, which is 0x{1:X} long ({1:,} bytes).'.format( messageStart, filesize )
				
			if errorMessage:
				ttk.Label( self.resultsFrame, text=errorMessage, wraplength=260 ).pack()
				return

		targetOffset = targetOffsets[0] #todo: finish adding support for searching for multiple structures

		# Get the offset of the start of the structure that contains the given offset
		if targetOffset in globalDatFile.structureOffsets: # ez; This is already the start of a struct
			structStartOffset = targetOffset
			prelimLocationText = '0x{0:X} is the starting offset of a structure.'.format( 0x20+structStartOffset )
		else:
			# Figure out what structure this offset belongs to
			structStartOffset = globalDatFile.getPointerOwner( targetOffset, offsetOnly=True )
			prelimLocationText = '0x{0:X} is within Struct 0x{1:X}.'.format( 0x20+targetOffset, 0x20+structStartOffset )

		# Display results in the search window.
		ttk.Label( self.resultsFrame, text=prelimLocationText, wraplength=260 ).pack()

		# Add the structure and any parents required for it to the treeview
		operationResultsText = showStructInStructuralAnalysis( structStartOffset )
		ttk.Label( self.resultsFrame, text=operationResultsText, wraplength=260 ).pack( pady=4 )

		# Switch to the SA tab, just in case we're not there
		Gui.mainTabFrame.select( Gui.savTab )


class FlagDecoder( basicWindow ):

	""" Used to view and modify DAT file structure flags, and the individual bits associated to them. """

	existingWindows = {} # todo; bring to focus existing windows rather than creating new ones

	def __init__( self, structure, fieldOffsets, fieldAndValueIndex ):
		# Store the given arguments
		self.structure = structure
		self.fieldOffsets = fieldOffsets # Relative to data section, not struct start (may be a list, if multiple locations should be edited)
		self.fieldAndValueIndex = fieldAndValueIndex

		# Collect info on these flags
		fieldName = structure.fields[fieldAndValueIndex]
		structFlagsDict = getattr( structure, 'flags', {} ) # Returns an empty dict if one is not found.
		self.individualFlagNames = structFlagsDict.get( fieldName ) # Will be 'None' if these flags aren't defined in the structure's class
		self.flagFieldLength = struct.calcsize( structure.formatting[fieldAndValueIndex+1] )

		# Create a string for iterating bits
		self.allFlagsValue = structure.getValues()[fieldAndValueIndex] # Single value representing all of the flags
		self.bitString = format( self.allFlagsValue, 'b' ).zfill( self.flagFieldLength * 8 ) # Adds padding to the left to fill out to n*8 bits

		# Determine the window spawn position (if this will be a long list, spawn the window right at the top of the main GUI)
		if self.individualFlagNames and len( self.individualFlagNames ) > 16: spawnHeight = 0
		elif not self.individualFlagNames and len( self.bitString ) > 16: spawnHeight = 0
		else: spawnHeight = 180

		# Determine the window name
		if isinstance( fieldOffsets, list ):
			shortName = structure.name.split( '0x' )[0].rstrip()
			if len( fieldOffsets ) > 3:
				offsetsString = '({} total)'.format( len(fieldOffsets) )
			else:
				relStructOffset = structure.valueIndexToOffset( fieldAndValueIndex ) - structure.offset
				offsetsString = '/'.join( [uHex(o+0x20-relStructOffset) for o in fieldOffsets] )
			windowName = 'Flag Decoder  -  {} {}, {}'.format( shortName, offsetsString, fieldName.replace( '_', ' ' ) )
		else:
			windowName = 'Flag Decoder  -  {}, {}'.format( structure.name, fieldName.replace( '_', ' ' ) )

		# Generate the basic window
		basicWindow.__init__( self, Gui.root, windowName, offsets=(180, spawnHeight) )

		# Define some fonts to use
		self.fontNormal = tkFont.Font( size=11 )
		self.boldFontLarge = tkFont.Font( weight='bold', size=14 )
		self.boldFontNormal = tkFont.Font( weight='bold', size=12 )

		self.drawWindowContents()

	def drawWindowContents( self ):
		# Display a break-down of all of the actual bits from the flag value
		self.bitsGrid = ttk.Frame( self.mainFrame )
		byteStringsList = [ self.bitString[i:i+8] for i in xrange(0, len(self.bitString), 8) ] # A list, where each entry is a string of 8 bits
		for i, byteString in enumerate( byteStringsList ): # Add the current byte as both hex and binary
			ttk.Label( self.bitsGrid, text='{0:02X}'.format(int( byteString, 2 )), font=self.boldFontLarge ).grid( column=i, row=0, ipadx=4 )
			ttk.Label( self.bitsGrid, text=byteString, font=self.boldFontLarge ).grid( column=i, row=1, ipadx=4 )
		ttk.Label( self.bitsGrid, text=' ^ bit {}'.format(len(self.bitString) - 1), font=self.fontNormal ).grid( column=0, row=2, sticky='w', ipadx=4 )
		ttk.Label( self.bitsGrid, text='bit 0 ^ ', font=self.fontNormal ).grid( column=len(byteStringsList)-1, row=2, sticky='e', ipadx=4 )
		self.bitsGrid.pack( pady=(10, 0), padx=10 )

		# Iterate over the bits or flag enumerations and show the status of each one
		self.flagTable = ttk.Frame( self.mainFrame )
		row = 0
		if self.individualFlagNames: # This will be a definition (ordered dictionary) from the structure's class.
			for bitMapString, bitName in self.individualFlagNames.items():
				baseValue, shiftAmount = bitMapString.split( '<<' )
				shiftAmount = int( shiftAmount )

				# Mask out the bits unrelated to this property
				bitMask = int( baseValue ) << shiftAmount

				ttk.Label( self.flagTable, text=bitMapString, font=self.fontNormal ).grid( column=0, row=row )

				# Set up the checkbox variable, and add the flag name to the GUI
				var = Tk.IntVar()
				if self.flagsAreSet( bitMask, shiftAmount ):
					var.set( 1 )
					ttk.Label( self.flagTable, text=bitName, font=self.boldFontNormal ).grid( column=1, row=row, padx=14 )
				else:
					var.set( 0 )
					ttk.Label( self.flagTable, text=bitName, font=self.fontNormal ).grid( column=1, row=row, padx=14 )

				chkBtn = ttk.Checkbutton( self.flagTable, variable=var )
				chkBtn.var = var
				chkBtn.row = row
				chkBtn.bitMask = bitMask
				chkBtn.shiftAmount = shiftAmount
				chkBtn.grid( column=2, row=row )
				chkBtn.bind( '<1>', self.toggleBits ) # Using this instead of the checkbtn's 'command' argument so we get an event (and widget reference) passed

				row += 1

		else: # Undefined bits/properties
			for i, bit in enumerate( reversed(self.bitString) ):
				# Add the bit number and it's value
				ttk.Label( self.flagTable, text='Bit {}:'.format(i), font=self.fontNormal ).grid( column=0, row=row )

				# Add the flag(s) name and value
				var = Tk.IntVar()
				if bit == '1':
					var.set( 1 )
				 	ttk.Label( self.flagTable, text='Set', font=self.boldFontNormal ).grid( column=1, row=row, padx=6 )
				else:
					var.set( 0 )
				 	ttk.Label( self.flagTable, text='Not Set', font=self.fontNormal ).grid( column=1, row=row, padx=6 )

				chkBtn = ttk.Checkbutton( self.flagTable, variable=var )
				chkBtn.var = var
				chkBtn.row = row
				chkBtn.bitMask = 1 << i
				chkBtn.shiftAmount = i
				chkBtn.grid( column=2, row=row )
				chkBtn.bind( '<1>', self.toggleBits ) # Using this instead of the checkbtn's 'command' argument so we get an event (and widget reference) passed

				row += 1

		self.flagTable.pack( pady=10, padx=10 )

	def flagsAreSet( self, bitMask, bitNumber ):

		""" Can check a mask of one or multiple bits (i.e. 0x1000 or 0x1100 ), except 
			when checking for a bitMask of 0, which only checks one specific bit. """

		if bitMask == 0: # In this case, this flag will be considered 'True' or 'On' if the bit is 0
			return not ( 1 << bitNumber ) & self.allFlagsValue
		else:
			return ( bitMask & self.allFlagsValue ) == bitMask

	def toggleBits( self, event ):
		# Get the widget's current value and invert it (since this method is called before the widget can update its value on its own)
		flagIsToBeSet = not event.widget.var.get()

		# For flags whose 'True' or 'On' case is met when the bit value is 0, invert whether the flags should be set to 1 or 0
		bitMask = event.widget.bitMask
		if bitMask == 0:
			flagIsToBeSet = not flagIsToBeSet
			bitMask = 1 << event.widget.shiftAmount

		# Set or unset all of the bits for this flag
		if flagIsToBeSet:
			self.allFlagsValue = self.allFlagsValue | bitMask # Sets all of the masked bits in the final value to 1
		else:
			self.allFlagsValue = self.allFlagsValue & ~bitMask # Sets all of the masked bits in the final value to 0 (~ operation inverts bits)

		# Rebuild the bit string and update the window contents
		self.updateBitBreakdown()
		self.updateFlagRows()

		# Change the flag value in the file
		self.updateFlagsInFile()

		return 'break' # Prevents propagation of this event (the checkbutton's own event handler won't even fire)

	def updateBitBreakdown( self ):

		""" Updates the flag strings of hex and binary, and then redraws them in the GUI. """

		# Update the internal strings
		self.bitString = format( self.allFlagsValue, 'b' ).zfill( self.flagFieldLength * 8 ) # Adds padding to the left to fill out to n*8 bits
		byteStringsList = [ self.bitString[i:i+8] for i in xrange(0, len(self.bitString), 8) ] # A list, where each entry is a string of 8 bits

		# Update the GUI
		for i, byteString in enumerate( byteStringsList ):
			# Update the hex display for this byte
			hexDisplayLabel = self.bitsGrid.grid_slaves( column=i, row=0 )[0]
			hexDisplayLabel['text'] = '{0:02X}'.format(int( byteString, 2 ))

			# Update the binary display for this byte
			binaryDisplayLabel = self.bitsGrid.grid_slaves( column=i, row=1 )[0]
			binaryDisplayLabel['text'] = byteString

	def updateFlagRows( self ):

		""" Checks all flags/rows to see if the flag needs to be updated. All of 
			them need to be checked because some flags can affect other flag rows. """

		for checkboxWidget in self.flagTable.grid_slaves( column=2 ):
			flagNameLabel = self.flagTable.grid_slaves( column=1, row=checkboxWidget.row )[0]

			# Set the boldness of the font, and the state of the checkbox
			if self.flagsAreSet( checkboxWidget.bitMask, checkboxWidget.shiftAmount ):
				flagNameLabel['font'] = self.boldFontNormal
				checkboxWidget.var.set( 1 )
			else:
				flagNameLabel['font'] = self.fontNormal
				checkboxWidget.var.set( 0 )

	def updateFlagsInFile( self ):

		""" Updates the combined value of the currently set flags in the file's data and in entry fields in the main program window. 
			This [unfortunately] needs to rely on a search methodology to target entry field widgets that need updating, 
			because they can be destroyed and re-created (thus, early references to existing widgets can't be trusted). """

		# Convert the value to a bytearray and create a list
		newHex = '{0:0{1}X}'.format( self.allFlagsValue, self.flagFieldLength*2 ) # Formats as hex; pads up to n zeroes (second arg)

		# Update the field entry widgets in the Structural Analysis tab, if it's currently showing this set of flags
		structTable = getattr( Gui.structurePropertiesFrame, 'structTable', None )
		if structTable:
			# Get the offset of the structure shown in the panel (offset of the first field entry), to see if it's the same as the one we're editing
			firstFieldOffsets = structTable.grid_slaves( column=1, row=0 )[0].offsets # Should never be a list when generated here
			if firstFieldOffsets == self.structure.offset:
				# Set the value of the entry widget, and trigger its bound update function (which will handle everything from validation through data-saving)
				hexEntryWidget = structTable.grid_slaves( column=1, row=self.fieldAndValueIndex )[0]
				self.updateWidget( hexEntryWidget, newHex )

		# Update the field entry widgets in the Texture Tree's Properties tab, if it's currently showing this set of flags
		flagWidgets = Gui.texturePropertiesPane.flagWidgets
		if self.structure.length == 0xC: # Pixel Proc. struct
			structOffset = 0
		elif self.structure.length == 0x18: # Material struct
			structOffset = 4
		elif self.structure.length == 0x5C: # Texture struct
			structOffset = 0x40
		else: # Allow this method to fail silently
			print 'Unexpected structure length for the Flag Decoder update method:', hex( self.structure.length )
			structOffset = 0
		for widget in flagWidgets:
			# Attempt to match this widget's flag offsets to the start of this window's structure offset
			if self.structure.offset in ( offset - structOffset for offset in widget.offsets ): # Makes a tuple of potential structure start offsets
				# Avoid updating this widget if this window is from the SA tab and there's more than one set of flags being represented by the target widget
				if not isinstance( self.fieldOffsets, list ) and len( widget.offsets ) > 1:
					# Do however update the widget to show that some of the structs it refers to have different values than others
					widget['highlightbackground'] = 'orange'
					widget['highlightthickness'] = 2
				else:
					self.updateWidget( widget, newHex )
				break

		# Update the actual data in the file for each offset
		updateName = self.structure.fields[self.fieldAndValueIndex].replace( '_', ' ' ).replace( '\n', ' ' )
		# Update the value in the file containing the modified flag(s)
		descriptionOfChange = updateName + ' modified in ' + globalDatFile.fileName
		newData = bytearray.fromhex( newHex )
		if type( self.fieldOffsets ) == list: # This is expected to be for an entry on the Texture Tree tab's Properties tab
			for offset in self.fieldOffsets:
				globalDatFile.updateData( offset, newData, descriptionOfChange )
		else: # This is expected to be for an entry on the Structural Analysis tab
			globalDatFile.updateData( self.fieldOffsets, newData, descriptionOfChange )

		updateProgramStatus( updateName + ' Updated' )

	def updateWidget( self, widget, newHex ):
		
		""" Just handles some cosmetic changes for the widget. Actual saving 
			of the data is handled by the updateFlagsInFile method. """

		# Update the values shown
		widget.delete( 0, 'end' )
		widget.insert( 0, newHex )

		# Change the background color of the widget, to show that changes have been made to it and are pending saving
		widget.configure( background='#faa' )

		# Add the widget to a list to keep track of what widgets need to have their background restored to white when saving
		global editedDatEntries
		editedDatEntries.append( widget )


def showStructInStructuralAnalysis( structOffset ):
	# Ensure the SA tab has been populated with the base structures (header/RT/root&reference nodes/etc)
	if not Gui.fileStructureTree.get_children(): # SAV tab hasn't been populated yet. Perform analysis.
		analyzeDatStructure()

	# Add the structure and any parents required for it to the treeview
	tic = time.clock()
	addParentStructures( structOffset, initialCall=True )
	toc = time.clock()
	print 'time to add parents:', toc-tic

	# Get the iids of all of the struct instances that are in the treeview
	targetStructIids = getStructureIids( (structOffset,) )

	if not targetStructIids:
		# Unable to add the structure; it may be an orphan
		operationResultsText = 'Unable to add this to the treeview, which means that it may be an orphan, or a decendant of one.'

	else:
		Gui.fileStructureTree.focus( targetStructIids[0] ) # Set a keyboard focus to the first item
		Gui.fileStructureTree.see( targetStructIids[0] ) # Scroll to the first item, so it's visible (folders should already be expanded)

		Gui.fileStructureTree.selection_set( targetStructIids )

		if len( targetStructIids ) == 1:
			operationResultsText = '1 instance of this structure was found.'
		else:
			operationResultsText = '{} instances of this structure were found.'.format( len(targetStructIids) )

		# Expand the size of the treeview column, if needed.
		currentViewingWidth = Gui.fileStructureTree.column( '#0', 'width' ) # Excludes the Offset column
		for item in targetStructIids:
			adjustSavColumnWidth( item, currentViewingWidth )

	print operationResultsText

	return operationResultsText


class ColorSwatch( ttk.Label ):

	""" Creates a circular image (on a label widget), to show a color example and allow for editing it.
		hexColor should be an 8 character hex string of RRGGBBAA """

	# Not using the imageBank in this case to avoid ImageTk.PhotoImage
	colorMask = Image.open( imagesFolder + "\\colorChooserMask.png" )

	def __init__( self, parent, hexColor, entryWidget=None ):
		# Create the label itself and bind the click even handler to it
		ttk.Label.__init__( self, parent, cursor='hand2' )
		if entryWidget:
			self.entryWidget = entryWidget
			self.bind( '<1>', self.editColor )

		# Create the image swatch that will be displayed, and attach it to self to prevent garbage collection
		self.renderCircle( hexColor )

	def renderCircle( self, hexColor ):
		# Convert the hex string provided to an RGBA values list
		fillColor = hex2rgb( hexColor )[0]

		# Create a new, 160x160 px, blank image
		swatchImage = Image.new( 'RGBA', (160, 160), (0, 0, 0, 0) )

		# Draw a circle of the given color on the new image
		drawable = ImageDraw.Draw( swatchImage )
		drawable.ellipse( (10, 10, 150, 150), fill=fillColor )

		# Scale down the image. It's created larger, and then scaled down to 
		# create anti-aliased edges (it would just be a hexagon otherwise).
		swatchImage.thumbnail( (16, 16), Image.ANTIALIAS )

		# Overlay the highlight/shadow mask on top of the above color (for a depth effect)
		swatchImage.paste( self.colorMask, (0, 0), self.colorMask )

		self.swatchImage = ImageTk.PhotoImage( swatchImage )
		self.configure( image=self.swatchImage )
		
	def editColor( self, event ):
		# Create a window where the user can choose a new color
		colorPicker = MeleeColorPicker( 'Modifying ' + self.entryWidget.updateName, initialColor=self.entryWidget.get() )
		Gui.root.wait_window( colorPicker.window ) # Wait for the above window to close before proceeding

		# Get the new color hex and make sure it's new (if it's not, the operation was canceled, or there's nothing to be done anyway)
		if colorPicker.initialColor != colorPicker.currentHexColor:
			if len( colorPicker.currentHexColor ) != self.entryWidget.byteLength * 2:
				msg( 'The value generated from the color picker (' + colorPicker.currentHexColor + ') does not match the byte length requirement of the destination.' )
			else:
				# Replace the text in the entry widget
				self.entryWidget.delete( 0, 'end' )
				self.entryWidget.insert( 0, colorPicker.currentHexColor )
				
				# Update the data in the file with the entry's data, and redraw the color swatch
				updateEntryHex( '', widget=self.entryWidget )


# def modifyFolders( parentIid, openFolders ): # Collapses or expands all folder items in a treeview (of level parentIid or lower).
# 	for item in Gui.fileStructureTree.get_children( parentIid ): 
# 		if len( Gui.fileStructureTree.get_children(item) ) != 0: # Item is a folder.
# 			Gui.fileStructureTree.item( item, open=openFolders )
# 			modifyFolders( item, openFolders )


# def expandSAV( tags ):
# 	if tags == '':
# 		modifyFolders( '', True )
# 	else:
# 		# First, collapse all items.
# 		modifyFolders( '', False )

# 		# Expand items, down to the level specified.
# 		targetItems = Gui.fileStructureTree.tag_has( tags )

# 		for iid in targetItems:
# 			Gui.fileStructureTree.item( iid, open=True )
# 			parent = Gui.fileStructureTree.parent( iid )
# 			while parent != '':
# 				Gui.fileStructureTree.item( parent, open=True )
# 				parent = Gui.fileStructureTree.parent( parent )


# def collapseSAV( tags ):
# 	# First, collapse all items.
# 	modifyFolders( '', False )

# 	targetItems = Gui.fileStructureTree.tag_has( tags )

# 	for iid in targetItems:
# 		parent = Gui.fileStructureTree.parent( iid )
# 		while parent != '':
# 			Gui.fileStructureTree.item( parent, open=True )
# 			parent = Gui.fileStructureTree.parent( parent )


# def highlightSAV( tag, highlightColor ):
# 	Gui.fileStructureTree.tag_configure( tag, background=highlightColor )


# def setSAVlineHighlights(): # Adds/removes line highlighting on the Structural Analysis tab.
# 	for tag, color, variable in Gui.savHighlightColors:
# 		if variable.get(): Gui.fileStructureTree.tag_configure( tag, background=color )
# 		else: Gui.fileStructureTree.tag_configure( tag, background='' )


# def removeAllSAVlineHighlighting():
# 	for tag, color, variable in Gui.savHighlightColors:
# 		Gui.fileStructureTree.tag_configure( tag, background='' )
# 		variable.set( False )

																				#===============================#
																				# ~ ~ Manual Placements tab ~ ~ #
																				#===============================#

def scanFolderStructure():
	# Prompt the user to choose a folder to look for textures in
	parentFolder = tkFileDialog.askdirectory(
		title="Choose a folder. All PNGs and TPLs in the chosen folder, and in all subfolders, will be selected.", 
		initialdir=settings.get( 'General Settings', 'defaultSearchDirectory' ),
		mustexist=True)

	if parentFolder != '':
		# Update the default directory to start in when opening or exporting files.
		with open( settingsFile, 'w') as theSettingsFile:
			settings.set( 'General Settings', 'defaultSearchDirectory', parentFolder )
			settings.write( theSettingsFile )

		# Get the image files in the parent folder.
		imageFilesArr = []
		for filename in os.listdir( parentFolder ):
			if filename.lower().endswith('.tpl') or filename.lower().endswith('.png'):
				imageFilesArr.append( parentFolder + '\\' + filename )

		# Get the image files in each subfolder.
		for dirList in os.walk( parentFolder ):
			for subfolder in dirList[1]:
				if subfolder != '':
					subfolderPath = dirList[0] + '\\' + subfolder
					try:
						for filename in os.listdir(subfolderPath):
							if filename.lower().endswith('.tpl') or filename.lower().endswith('.png'):
								imageFilesArr.append( subfolderPath + '\\' + filename )
					except WindowsError:
						# (Some items may be inaccessible\hidden.)
						#msg('There was an error while attempting to gather the file names.')
						pass
		showSelectedPaths( imageFilesArr )


def showSelectedPaths( imageFiles ):
	# Add new files to the text area, increasing horizontal space if needed.
	missingTexTypes = ''

	nonImages = []
	for i in xrange( len(imageFiles) ):
		imagePath = imageFiles[i]
		fileExt = os.path.splitext( imagePath )[1].lower()
		if fileExt == '.png' or fileExt == '.tpl':
			imageType, offset, sourceFile = codecBase.parseFilename( os.path.basename( imagePath ) )
			if imageType == -1: 
				missingTexTypes += '\n' + imagePath
				continue
			
			# Write the file path and offset (if available) to the appropriate text field.
			if offset != -1 and validOffset( str(offset) ): offset = uHex( offset )
			else: offset = ''

			standardizedPath = imagePath.replace('/', '\\') + '  -->  ' + offset
			arrowPosFromEnd = len( offset ) + 6
			adjustTextAreaWidth( standardizedPath, Gui.imageTextArea )

			if i == 0 and len( recallFilepaths() ) == 0: ## i.e. first entry of the text field. (i==0 probably isn't necessary, but short-circuits for efficiency.)
				Gui.imageTextArea.insert( 'end', standardizedPath )
			else: Gui.imageTextArea.insert( 'end', "\n" + standardizedPath )

			# Color the arrow.
			Gui.imageTextArea.tag_add('offsetArrow', 'end - ' + str( arrowPosFromEnd ) + ' chars', 'end - ' + str( arrowPosFromEnd - 3 ) + ' chars')
		else:
			nonImages.append( imagePath )
	
	# If there was exactly one non-image file included, give it the benefit of the doubt that it is a DAT of some kind, and set it as such.
	if len(nonImages) == 1: fileHandler( nonImages )
	elif len(nonImages) > 1: msg( 'Multiple non-PNG/TPL files were given, which were discarded.' )

	# Update the GUI on total textures gathered.
	Gui.sourceTexturesText.set( "Texture(s):\n  (" + str(len( recallFilepaths() )) + " total)" )

	if missingTexTypes != '':
		#updateProgramStatus( 'Missing Types!' )
		msg("A texture type wasn't found for the following textures (the " + \
			'type should appear at the end of the file name, e.g. the "_9" in ' + \
			'"IfAll.usd_0x76280_9.png"):\n\n' + missingTexTypes)


def adjustTextAreaWidth( newestPath, targetWidget ):
	if len(newestPath) > targetWidget.cget("width"):
		targetWidget.config( width=len(newestPath) + 3 )
		Gui.mtrTabRow2.update()
		Gui.root.geometry( str(Gui.mtrTabRow2.winfo_reqwidth()) + 'x' + str(Gui.root.winfo_height()) )


def recallFilepaths():
	filepaths = []
	for i in xrange( int(Gui.imageTextArea.index('end-1c').split('.')[0]) ):
		line = Gui.imageTextArea.get(str(i+1)+'.0', str(i+2)+'.0-1c').replace( '"', '' )
		if line != '': filepaths.append( line )
	return filepaths


def onTextAreaKeyUp(event):
	# Expand the area for text fields if there is not enough space.
	targetWidget = event.widget
	lineIndex = targetWidget.index('insert').split(".")[0]
	newestPath = targetWidget.get(lineIndex+'.0', str(int(lineIndex)+1)+'.0-1c')
	adjustTextAreaWidth(newestPath, targetWidget)
		
	# Color the arrow which points out the offset, if available.
	arrowPos = newestPath.find('-->')
	if arrowPos != -1:
		targetWidget.tag_add('offsetArrow', lineIndex + '.' + str(arrowPos), lineIndex + '.' + str(arrowPos + 3))

	# Update the GUI on total textures gathered.
	Gui.sourceTexturesText.set("Texture(s):\n  (" + str(len(recallFilepaths())) + " total)")


def overwriteImagesManually():
	datFilePath = Gui.datDestination.get().replace('"', '')

	# Start with a preliminary check that something is given for a DAT filepath and that DAT file can be found.
	if datFilePath == '': msg( 'No DAT or USD file has been set.' )
	elif not os.path.exists( datFilePath ): 
		msg( 'The destination file (DAT/USD) could not be found.\n\n(This import method currently only supports standalone files, i.e. those not in a disc.)' )
	else:
		## Check that something is given for the texture filepaths.
		imagePathsAndOffsets = recallFilepaths()
		if imagePathsAndOffsets == []: msg( 'No texture(s) selected.' ) #infoText.set('You must add textures above.')
		else:
			imagesNotFound = ''
			offsetsNotFound = ''
			unsupportedFiles = ''
			missingTypes = ''
			generalFailures = ''
			datFileToOpen = datFilePath
			datFilename, datFileExt = os.path.splitext( os.path.basename(datFileToOpen) )
			newDatFilepath = ''

			if Gui.mtrSaveBackup.get():
				datFileDir = os.path.split( datFilePath )[0]
				if '[the hack. v' in datFilename: 
					nameStartPoint = datFilename.index(']_')

					# Separate out the last decimal part from the version number.
					version = datFilename[:nameStartPoint].split('v')[1]

					if '.' in version: baseVer = datFilename[:nameStartPoint].rsplit('.')[0]
					else: baseVer = version
					newDatFilepath = datFileDir + '\\[the hack. v' + baseVer + '.' + '1' + datFilename[nameStartPoint:] + datFileExt

					fileVersionCount = 1
					while os.path.exists( newDatFilepath ):
						fileVersionCount += 1
						newDatFilepath = datFileDir + '\\[the hack. v' + baseVer + '.' + str(fileVersionCount) + datFilename[nameStartPoint:] + datFileExt

				else:
					newDatFilepath = datFileDir + '\\[the hack. v1]_' + datFilename + datFileExt

					fileVersionCount = 1
					while os.path.exists( newDatFilepath ):
						fileVersionCount += 1
						newDatFilepath = datFileDir + '\\[the hack. v' + str(fileVersionCount) + ']_' + datFilename + datFileExt

				# Filepath determined. Try to create the back-up.
				try:
					shutil.copy(datFilePath, newDatFilepath)
					datFileToOpen = newDatFilepath
				except:
					if not tkMessageBox.askyesno('Proceed without backup?', 'A backup of the ' + datFileExt.upper() + ' file could not be created. \n'
						'(You may want to check if the file is read or write\nprotected, or copy the file manually.) \n\n'
						'Do you want to proceed with the overwrite anyway?'):
						return ## Exit this function without performing any image overwriting.
					newDatFilepath = '' # Cleared since a back-up won't be created.
			clearHighlighting()
			imagesOverwritten = 0
			imagesNotOverwritten = 0
			palettesCreated = 0
			showPaletteWarning = False
			with open(datFileToOpen, 'r+b') as datBinary:
				## For each image...
				for currentLine, imagePathAndOffset in enumerate(imagePathsAndOffsets):
					## enumerate starts at 0, but tkinter starts line counts at 1, so increase the enumerated value to match.
					currentLine = currentLine + 1
					## Check that there is an offset provided for this image.
					if '-->' in imagePathAndOffset:
						(imageFilepath, offsets) = imagePathAndOffset.split('-->')
						## Remove leading and/or trailing whitespace from the variables.
						imageFilepath = imageFilepath.strip()
						for imageOffset in offsets.split(','):
							imageOffset = imageOffset.strip().replace('0x', '').replace('0X', '')
							separatedPalette = False
							if ':' in imageOffset:
								(imageOffset, paletteOffset) = imageOffset.split(':')
								imageOffset = imageOffset.strip()
								paletteOffset = paletteOffset.strip()
								separatedPalette = True

							## Confirm that the offsets exists and are each a hexadecimal number.
							if validOffset(imageOffset) and (not separatedPalette or validOffset(paletteOffset)): # Third condition only evaluated if separatedPalette = True.
								## Check that the current image file can be found.
								if os.path.exists( imageFilepath ):

									try:
										newImage = tplEncoder( imageFilepath, imageType=codecBase.parseFilename( os.path.basename( imageFilepath ) )[0] )
										imageData = newImage.encodedImageData
										paletteData = newImage.encodedPaletteData
										status = 'dataObtained'
									except TypeError: # For CMPR (_14) textures; uses wimgt
										status, _, imageData, _, paletteData = getImageFileAsTPL( imageFilepath, '' )
									except IOError: status = 'formatUnsupported'
									except missingType: status = 'imageTypeNotFound'
									except: status = 'encodingError'

									if status == 'dataObtained' or status == 'dataWithAdHocPalette':
										if separatedPalette:
											## Convert the offset to base 16 and then use that to seek to the texture location.
											datBinary.seek( int(imageOffset, 16) )
											datBinary.write( bytearray.fromhex(imageData) )
											## Convert the offset to base 16 and then use that to seek to the palette location.
											datBinary.seek( int(paletteOffset, 16) )
											datBinary.write( bytearray.fromhex(paletteData) )
										else:
											if paletteData != '':
												imageData = imageData + paletteData
											## Convert the offset to base 16 and then use that to seek to the texture location.
											datBinary.seek( int(imageOffset, 16) )
											datBinary.write( bytearray.fromhex(imageData) )

										# Perform line highlighting
										if status == 'dataObtained':
											Gui.imageTextArea.tag_add( 'successfulOverwrite', str(currentLine)+'.0', str(currentLine+1)+'.0-1c' )
										else:
											Gui.imageTextArea.tag_add( 'warningOverwrite', str(currentLine)+'.0', str(currentLine+1)+'.0-1c' )
											palettesCreated = palettesCreated + 1
											showPaletteWarning = True
										imagesOverwritten += 1
									elif status == 'formatUnsupported':
										unsupportedFiles = unsupportedFiles + imageFilepath + '\n'
										Gui.imageTextArea.tag_add( 'failedOverwrite', str(currentLine)+'.0', str(currentLine+1)+'.0-1c' )
										imagesNotOverwritten += 1
									elif status == 'imageTypeNotFound':
										missingTypes = missingTypes + imageFilepath + '\n'
										Gui.imageTextArea.tag_add( 'failedOverwrite', str(currentLine)+'.0', str(currentLine+1)+'.0-1c' )
										imagesNotOverwritten += 1
									else:
										generalFailures = generalFailures + imageFilepath + '\n'
										Gui.imageTextArea.tag_add( 'failedOverwrite', str(currentLine)+'.0', str(currentLine+1)+'.0-1c' )
										imagesNotOverwritten += 1
								else:
									imagesNotFound = imagesNotFound + imageFilepath + '\n'
									Gui.imageTextArea.tag_add( 'failedOverwrite', str(currentLine)+'.0', str(currentLine+1)+'.0-1c' )
									break
							else:
								if separatedPalette:
									offsetsNotFound = offsetsNotFound + imageFilepath + ' with ' + imageOffset + ':' + paletteOffset + '\n'
									Gui.imageTextArea.tag_add( 'failedOverwrite', str(currentLine)+'.0', str(currentLine+1)+'.0-1c' )
								else:
									offsetsNotFound = offsetsNotFound + imageFilepath + ' with ' + imageOffset + '\n'
									Gui.imageTextArea.tag_add( 'failedOverwrite', str(currentLine)+'.0', str(currentLine+1)+'.0-1c' )
					else:
						offsetsNotFound = offsetsNotFound + imagePathAndOffset + '\n'
						Gui.imageTextArea.tag_add('failedOverwrite', str(currentLine)+'.0', str(currentLine+1)+'.0-1c')

			## This point is after the image file injection loop and closure of the DAT/USD file.
			## If a back-up was created, but no changes were made from the original file, don't keep the new copy.
			if imagesOverwritten == 0 and newDatFilepath != '':
				try: os.remove( newDatFilepath )
				except: pass

			if showPaletteWarning == True:
				if palettesCreated == 1: 
					msg('No palette was detected for the texture marked in yellow. It was given one and succefully ' # infoText.set
					'written into the ' + datFileExt.replace('.','').upper() + ', however, you will achieve better image quality '
					'if you give the texture a palette in your image editor beforehand.')
				else:
					msg('No palette was detected for the textures marked in yellow. They were given one and succefully '
					'written into the ' + datFileExt.replace('.','').upper() + ', however, you will achieve better image quality '
					'if you give the textures a palette in your image editor beforehand.') # infoText.set

			## Begin creating a completion message of what was done.
			if imagesOverwritten == 1: 
				completionMessage = 'Procedure complete!  1 image in the ' + datFileExt.upper() + ' was overwritten.'
			elif imagesOverwritten > 1:
				completionMessage = 'Procedure complete!  ' + str(imagesOverwritten) + ' images in the ' + datFileExt.upper() + ' were overwritten.'
			else:
				completionMessage = ''
				
			## Append notification of unprocessed image files (due to no offset info, or unsupported types).
			if completionMessage == '' and offsetsNotFound != '':
				## (No images were overwritten).
				completionMessage = completionMessage + \
				'The following images were not processed because proper offsets \n' + \
				'were not given or not found:\n\n' + offsetsNotFound
			elif offsetsNotFound != '':
				## Notification of at least some images being overwritten was appended to the completion message.
				completionMessage = completionMessage + \
				'\n\nHowever, the following images were not processed because \n' + \
				'proper offsets were not given or not found:\n\n' + offsetsNotFound
				
			## Append notification of image files not found.
			if imagesOverwritten == 0 and offsetsNotFound == '' and imagesNotFound != '':
				## No previous messages have been appended to the completion message (no images were overwritten, yet offsets were given).
				completionMessage = completionMessage + 'The image files were not found.'
			elif imagesOverwritten > 0 and offsetsNotFound == '' and imagesNotFound != '':
				completionMessage = completionMessage + '\n\nHowever, the following image files were not found:\n\n' + imagesNotFound
			elif offsetsNotFound != '' and imagesNotFound != '':
				completionMessage = completionMessage + \
				'\n\nAlso, the following image files were not found:\n\n' + imagesNotFound
			
			## Append notification of images not processed due to unsupported file types or image formats.
			if unsupportedFiles != '':
				completionMessage = completionMessage + \
				"\n\nThe following images were not written in because the image doesn't\n" + \
				"have correct formatting for a .TPL or .PNG (you might want to\n" + \
				"try getting a new copy of the image):\n\n" + unsupportedFiles

			if missingTypes != '':
				completionMessage = completionMessage + \
				"\n\nAn image type wasn't found for the following images\n" + \
				'(the type should appear at the end of the file name, e.g. the "_2" in' + \
				'"MnSlMap.usd_0x38840_2.png"):\n\n' + missingTypes
				updateProgramStatus( 'Missing Types!' )

			if generalFailures != '':
				completionMessage = completionMessage + \
				"\n\nThe following images failed to import due to an encoding error:\n\n" + generalFailures
				updateProgramStatus( 'Failed Imports!' )

			if imagesNotOverwritten > 0: updateProgramStatus( 'Failed Imports' )
			else: updateProgramStatus( 'Import Successful' )
			msg(completionMessage)


def clearHighlighting():
	Gui.imageTextArea.tag_remove('successfulOverwrite', '1.0', 'end')
	Gui.imageTextArea.tag_remove('warningOverwrite', '1.0', 'end')
	Gui.imageTextArea.tag_remove('failedOverwrite', '1.0', 'end')


																				#===================================#
																				# ~ ~ Character Color Converter ~ ~ #
																				#===================================#

def cccSelectStandalone( role ):
	filepath = tkFileDialog.askopenfilename(
		title="Choose a character texture file.", 
		initialdir=settings.get( 'General Settings', 'defaultSearchDirectory' ),
		filetypes=[ ('Texture data files', '*.dat *.usd *.lat *.rat'), ('All files', '*.*') ]
		)

	if filepath != '' and os.path.exists( filepath ):
		# Get the DAT data and relocation table from the target file.
		with open( filepath , 'rb') as binaryFile:
			datHex = binaryFile.read().encode( 'hex' )

		prepareColorConversion( filepath, datHex, role )


def cccPointToDiscTab():
	Gui.mainTabFrame.select( Gui.discTab )
	if globalDiscDetails['isoFilePath'] == '': promptToOpenFile( 'iso' )
	else: scrollToSection( 'Characters' )


def prepareColorConversion( filepath, datHex, role ): # datHex includes the file header
	rtStart = int( datHex[8:16], 16 ) # Size of the data block
	rtEntryCount = int( datHex[16:24], 16 )
	rootNodeCount = int( datHex[24:32], 16 )
	referenceNodeCount = int( datHex[32:40], 16 )
	rtEnd = rtStart + (rtEntryCount * 4)
	rootNodesEnd = rtEnd + (rootNodeCount*8)

	tempFileHeader = datHex[:64]
	datHex = datHex[64:] # Removes the header

	stringTable = datHex[rootNodesEnd*2 + (referenceNodeCount *16):]
	firstString = stringTable.decode('hex').split('\x00')[0] # Strings separated by stop byte, '\x00'

	# Validate the parsing, and therefore also the file.
	if not firstString[:3] == 'Ply': msg( "This file doesn't appear to be a character costume!" )
	elif '5K' not in firstString: 
		if 'Kirby' in firstString: msg( "Only Kirby's base color files are supported (e.g. 'PlKbBu'). "
			"You'll have to modify this one manually. Luckily, none of his files have many textures." )
		else: # If here, this must be Master/Crazy Hand, or one of the Fighting Wire Frames.
			msg( "This character doesn't have multiple color files. \nThere is nothing to convert." )
	else:
		# Parse string....
		charKey, colorKey = firstString[3:].split( '5K' )
		if colorKey.startswith('_'): colorKey = 'Nr'
		else: colorKey = colorKey.split('_')[0]

		# Check if the filepath is actually a path to a file, or is actually the iid for a file in a disc.
		if not Gui.isoFileTree.exists( filepath ):
			# Update the default search directory.
			dirPath = os.path.dirname( filepath )
			with open( settingsFile, 'w') as theSettingsFile:
				#if not settings.has_section('General Settings'): settings.add_section('General Settings')
				settings.set( 'General Settings', 'defaultSearchDirectory', dirPath )
				settings.write( theSettingsFile ) # Updates a pre-existing settings file entry, or just creates a new file.

		if charKey == 'Gamewatch': msg( 'Game & Watch has no textures to swap!' )
		if charKey == 'Gkoopa': msg( 'Giga Bowser only has one color file! \nThere is nothing to convert.' )
		elif charKey == 'Peach' and colorKey == 'Ye':
			msg("Peach's yellow costume has too many differences from the other colors to map. You'll need to convert this costume manually. (Using the DAT Texture Tree tab to "
				"dump all textures from the source file, and then you can use those to replace the textures in the destination file. Although there are likely textures "
				"that do not have equivalents.) Sorry about that; this is actually the only character & color combination not supported by this tool.")
		elif charKey not in CCC or colorKey not in CCC[charKey]: 
			# Failsafe scenario. Shouldn't actually be able to get here now that everything besides yellow Peach (handled above) should be mapped.
			msg( 'This character or color is not supported. \n\nID (first root node string): ' + firstString + \
				 '\n\nCharacter key found: ' + str(charKey in CCC) + '\nColor key found: ' + str(colorKey in charColorLookup) )
		else:
			# Get an image that is greyscale with alpha
			insigniaPath = imagesFolder + "\\universe insignias\\" + CCC[charKey]['universe'] + ".png"
			greyscaleInsignia = Image.open( insigniaPath ).convert('L')

			# Look up the color to use for the insignia
			insigniaColor = charColorLookup.get( colorKey, 'white' )
			if insigniaColor == 'neutral': insigniaColor = ( 210, 210, 210, 255 )

			# Create a blank canvas, and combine the other images onto it
			blankImage = Image.new( 'RGBA', greyscaleInsignia.size, (0, 0, 0, 0) )
			colorScreen = Image.new( 'RGBA', greyscaleInsignia.size, insigniaColor ) #(0, 0, 255, 255)
			completedInsignia = ImageTk.PhotoImage( Image.composite( blankImage, colorScreen, greyscaleInsignia) )

			if role == 'source':
				Gui.cccSourceCanvas.delete('all')
				Gui.cccSourceCanvas.insigniaImage = completedInsignia

				# Attache the images to the canvas
				Gui.cccSourceCanvas.create_image( 0, 0, image=Gui.cccSourceCanvas.insigniaImage, anchor='nw' )

				#font=tkFont.Font(family='TkDefaultFont', size=9, weight='bold') 
				Gui.cccSourceCanvas.create_text( Gui.cccIdentifiersXPos, 20, anchor='w', fill=Gui.globalFontColor, font="-weight bold -size 10", text='Character: ' + CCC[charKey]['fullName']) 
				Gui.cccSourceCanvas.create_text( Gui.cccIdentifiersXPos, 44, anchor='w', fill=Gui.globalFontColor, font="-weight bold -size 10", text='Costume Color: ' + charColorLookup.get(colorKey,'Unknown').capitalize())

				CCC['dataStorage']['sourceFile'] = filepath
				CCC['dataStorage']['sourceFileChar'] = charKey
				CCC['dataStorage']['sourceFileColor'] = colorKey
				CCC['dataStorage']['sourceFileHeader'] = tempFileHeader
				CCC['dataStorage']['sourceFileData'] = datHex
			else:
				Gui.cccDestCanvas.delete('all')
				Gui.cccDestCanvas.insigniaImage = completedInsignia

				# Attache the images to the canvas
				Gui.cccDestCanvas.create_image( 0, 0, image=Gui.cccDestCanvas.insigniaImage, anchor='nw' )

				#font=tkFont.Font(family='TkDefaultFont', size=9, weight='bold') 
				Gui.cccDestCanvas.create_text( Gui.cccIdentifiersXPos, 20, anchor='w', fill=Gui.globalFontColor, font="-weight bold -size 10", text='Character: ' + CCC[charKey]['fullName']) 
				Gui.cccDestCanvas.create_text( Gui.cccIdentifiersXPos, 44, anchor='w', fill=Gui.globalFontColor, font="-weight bold -size 10", text='Costume Color: ' + charColorLookup.get(colorKey,'Unknown').capitalize())

				CCC['dataStorage']['destFile'] = filepath
				CCC['dataStorage']['destFileChar'] = charKey
				CCC['dataStorage']['destFileColor'] = colorKey
				CCC['dataStorage']['destFileHeader'] = tempFileHeader
				CCC['dataStorage']['destFileData'] = datHex


def convertCharacterColor():
	# Make sure there's data collected on the source and destination files.
	sourceFilepath = CCC['dataStorage']['sourceFile']
	destFilepath = CCC['dataStorage']['destFile']

	if sourceFilepath == '' or destFilepath == '': msg( 'You must provide both a source and destination file.' )
	else:
		# Collect the rest of the stored data on the source and destination files.
		sourceCharKey = CCC['dataStorage']['sourceFileChar']
		sourceColorKey = CCC['dataStorage']['sourceFileColor']
		sourceDatHex = CCC['dataStorage']['sourceFileData']

		destCharKey = CCC['dataStorage']['destFileChar']
		destColorKey = CCC['dataStorage']['destFileColor']
		destFileHeader = CCC['dataStorage']['destFileHeader']
		destDatHex = CCC['dataStorage']['destFileData']

		if not sourceCharKey == destCharKey: msg( 'Both files must be for the same character.', '''"I can't let you do that, Star Fox!"''' )
		elif sourceColorKey == destColorKey: msg( 'These character costumes are for the same color!\n There is nothing to convert.' )
		else:
			sourceBlocks = CCC[sourceCharKey][sourceColorKey]
			destBlocks = CCC[destCharKey][destColorKey]

			# For each mapped block of texture data for the character files, replace the data block in the destination file with the data block from the source file.
			skipNextBlock = False
			unmodifiedBlocks = []
			for blockIteration in xrange( len(sourceBlocks) ):
				sourceBlockStart, sourceBlockEnd = sourceBlocks[blockIteration]
				sourceBlockStart -= 0x20 # For file header compensation.
				sourceBlockEnd -= 0x20
				sourceBlockLength = sourceBlockEnd - sourceBlockStart

				destBlockStart, destBlockEnd = destBlocks[blockIteration]
				destBlockStart -= 0x20 # For file header compensation.
				destBlockEnd -= 0x20
				destBlockLength = destBlockEnd - destBlockStart

				# Skip copying palette headers if the previous block (probably a block of texture and/or palette data) was skipped.
				if skipNextBlock:
					skipNextBlock = False

					if destBlockLength == 0x1C:
						print 'block skipped:', uHex(sourceBlockStart + 0x20)
						continue

				# Skip any untranslatable blocks of data, but notify the user that they were not changed.
				if sourceBlockLength == destBlockLength:

					# Replace the data blocks.
					destDatHex = replaceHex( destDatHex, destBlockStart, sourceDatHex[sourceBlockStart*2:sourceBlockEnd*2] )
				
				elif destBlockLength > 0x1C: # Excludes reporting of palette header blocks.
					unmodifiedBlocks.append( destBlocks[blockIteration] )
					print 'block', uHex(destBlocks[blockIteration][0]) + ', ' + uHex(destBlocks[blockIteration][1]), 'queuing skip'
					skipNextBlock = True

			# Conversion has completed. Check whether the destination file is from a disc or a standalone file, and save the new file data accordingly.
			if Gui.isoFileTree.exists( destFilepath ): # 'destFilepath' will actually be an iid in this case.
				_, entity, isoOffset, fileSize, isoPath, _, _ = Gui.isoFileTree.item( destFilepath, 'values' ) # description, entity, isoOffset, fileSize, isoPath, source, data
				Gui.isoFileTree.item( destFilepath, values=('Converted and ready to be replaced...', entity, isoOffset, fileSize, isoPath, 'ram', destFileHeader + destDatHex), tags='changed' )
				#Gui.mainTabFrame.select( Gui.discTab )
				global unsavedDiscChanges
				unsavedDiscChanges.append( os.path.basename(sourceFilepath) + ' converted and ready for import.' )
			else:
				writeDatFile( destFilepath, bytearray.fromhex(destFileHeader + destDatHex), 'Conversion' )

			Gui.cccOpenConvertedFileButton['state'] = 'normal'
			updateProgramStatus( 'Conversion Complete' )

			# Alert the user of any areas that still need to be manually replaced.
			if unmodifiedBlocks != []:
				cmsg("Some textures could not be replaced, due to differences in the textures' properties between the two files (such as having different resolutions or " \
					'differently sized palettes). Textures that were able to be copied over have been transferred. However, the textures in the following ranges will still need ' \
					'to be replaced. (You can click on the "Offset (len)" column header on the DAT Texture Tree tab to view textures in the order that they appear in the file.):\n\n' + \
					'\n'.join( [uHex(block[0]) + ' to ' + uHex(block[1]) for block in unmodifiedBlocks] ), 'Some Manual Transfers Required' )

			# Contingency messages.
			if sourceCharKey == 'Kirby':
				cmsg("Most textures have been copied over, however his eye textures will need to be done manually.")
			elif sourceCharKey == 'Mewtwo' and sourceColorKey == 'Nr':
				cmsg("The source textures have been copied over. However, note that Mewtwo's Neutral costume has an extra eye texture (at 0x2f440 to 0x31440) that " \
					"doesn't exist or have an equivalent in the other colors. So it will not be included in the destination file/costume.")
			elif destCharKey == 'Mewtwo' and destColorKey == 'Nr': 
				cmsg("Mewtwo's Neutral costume has an extra eye texture (at 0x2f440 to 0x31440), which doesn't exist or have an equivalent in the other colors. So " \
					"although the rest of the textures have been copied, you'll need to replace this texture manually (you can try using one of the other eye textures, " \
					"or create a new one).")

			elif destCharKey == 'Pichu' and destColorKey == 'Bu':
				cmsg("Pichu's body and eye textures have been transferred over. However, Pichu's alternate colors each have an extra part to its model, which each " \
					"have unique textures (i.e. no equivalents in the other costume files). For its Blue alt, this would be its goggles, whose textures " \
					"extend from 0x16800 to 0x1E800 (7 textures), and 0x28820 and 0x28C20 (1 texture). You'll need to update these manually if you want to change them.")
			elif destCharKey == 'Pichu' and destColorKey == 'Gr':
				cmsg("Pichu's body and eye textures have been transferred over. However, Pichu's alternate colors each have an extra part to its model, which each " \
					"have unique textures (i.e. no equivalents in the other costume files). For its Green alt, this would be its backpack, whose textures " \
					"extend from 0x17320 to 0x2C320 (13 textures), and 0x35B20 to 0x3DB20 (1 texture). You'll need to update these manually if you want to change them.")
			# elif destCharKey == 'Pichu' and destColorKey == 'Nr':
			# 	cmsg("Pichu's body (and eye) textures have been transferred over. However, Pichu's alternate colors each have an extra part to its model, which each " \
			# 		"have unique textures (i.e. no equivalents in the other costume files). Thus, these textures won't be touched.")
			elif destCharKey == 'Pichu' and destColorKey == 'Re':
				cmsg("Pichu's body and eye textures have been transferred over. However, Pichu's alternate colors each have an extra part to its model, which each " \
					"have unique textures (i.e. no equivalents in the other costume files). For its Red alt, this would be its scarf, whose textures " \
					"extend from 0x21200 to 0x25200 (2 textures). You'll need to update these manually if you want to change them.")

			elif destCharKey == 'Pikachu' and destColorKey == 'Bu':
				cmsg("Pikachu's body and eye textures have been transferred over. However, due to variations among its hats, you'll need to update the textures " \
					"for those manually if you want to change them. For Pikachu's Blue alt, this would be its magician's hat, whose textures " \
					"extend from 0x15860 to 0x19860 (2 textures).")
			elif destCharKey == 'Pikachu' and destColorKey == 'Gr':
				cmsg("Pikachu's body and eye textures have been transferred over. However, due to variations among its hats, you'll need to update the textures " \
					"for those manually if you want to change them. For Pikachu's Green alt, this would be its fedora, whose textures " \
					"extend from 0x15f60 to 0x19f60 (2 textures).")
			elif destCharKey == 'Pikachu' and destColorKey == 'Re':
				cmsg("Pikachu's body and eye textures have been transferred over. However, due to variations among its hats, you'll need to update the textures " \
					"for those manually if you want to change them. For Pikachu's Red alt, this would be Red's hat, whose textures " \
					"extend from 0x152a0 to 0x1baa00 (3 textures).")

			elif destCharKey == 'Purin' and destColorKey == 'Bu':
				cmsg("Jigglypuff's body and eye textures have been transferred over. However, due to variations among its head pieces, you'll need to update the textures " \
					"for those manually if you want to change them. For Jigglypuff's Blue alt, this would be the bow, whose textures " \
					"extend from 0x3e2e0 to 0x3e320 (2 textures).")
			elif destCharKey == 'Purin' and destColorKey == 'Gr':
				cmsg("Jigglypuff's body and eye textures have been transferred over. However, due to variations among its head pieces, you'll need to update the textures " \
					"for those manually if you want to change them. For Jigglypuff's Green alt, this would be the bandana, whose textures " \
					"extend from 0x3caa0 to 0x3dac0 (3 textures).")
			elif destCharKey == 'Purin' and destColorKey == 'Re':
				cmsg("Jigglypuff's body and eye textures have been transferred over. However, due to variations among its head pieces, you'll need to update the textures " \
					"for those manually if you want to change them. For Jigglypuff's Red alt, this would be the flower, whose textures " \
					"extend from 0x3b760 to 0x3d760 (1 texture).")
			elif destCharKey == 'Purin' and destColorKey == 'Ye':
				cmsg("Jigglypuff's body and eye textures have been transferred over. However, due to variations among its head pieces, you'll need to update the textures " \
					"for those manually if you want to change them. For Jigglypuff's Yellow alt, this would be the crown, whose textures " \
					"extend from 0x3b420 to 0x3fc20 (5 textures).")


def openConvertedCharacterFile():

	""" This function is used by the Character Color Converter (CCC) tab, for opening a finished/converted costume file in 
		the DAT Texture Tree tab. This is useful for making sure the conversion was successful and the new textures are intact. """

	destFilepath = CCC['dataStorage']['destFile']

	if Gui.isoFileTree.exists( destFilepath ): 
		loadFileWithinDisc( destFilepath ) # 'destFilepath' will actually be an iid in this case.
	else: 
		fileHandler( [destFilepath] )


																				#======================#
																				# ~ ~ Tool Modules ~ ~ #
																				#======================#

class MeleeColorPicker( object ):

	windows = {} # Used to track multiple windows for multiple palette entries. New windows will be added with a windowId = palette entry's canvas ID
	recentColors = [] # Colors stored as tuples of (r, g, b, a)
	windowSpawnOffset = 0

	def __init__( self, title='Color Converter', initialColor='ACACAC7F', defaultTplFormat=5, windowId='', datDataOffsets=() ):
		self.title = title
		self.initialColor = initialColor.upper()
		self.currentHexColor = self.initialColor
		self.currentRGBA = hex2rgb( self.initialColor )[0]
		self.tplHex = tplEncoder.encodeColor( defaultTplFormat, self.currentRGBA )
		self.windowId = windowId
		self.datDataOffsets = datDataOffsets  # ( rgbaColor, paletteEntry, paletteEntryOffset, imageDataOffset ) | paletteEntry is the original palette color hex
		self.lastUpdatedColor = ''	# Used to prevent unncessary/redundant calls to update the displayed texture

		if self.windowId in self.windows: pass #MeleeColorPicker.windows[self.windowId].window.deiconify()
		else:
			self.createWindow( defaultTplFormat )

			# If windowId, remember it so it can be referenced later (by deiconify)
			if self.windowId: self.windows[self.windowId] = self

		self.window.deiconify()

	def createWindow( self, defaultTplFormat ):
		self.window = Tk.Toplevel( Gui.root )
		self.window.title( self.title )
		self.window.attributes( '-toolwindow', 1 ) # Makes window framing small, like a toolbox/widget.
		self.window.resizable( width=False, height=False )
		self.window.wm_attributes( '-topmost', 1 )
		self.window.protocol( 'WM_DELETE_WINDOW', self.cancel ) # Overrides the 'X' close button.

		# Calculate the spawning position of the new window
		rootDistanceFromScreenLeft, rootDistanceFromScreenTop = getWindowGeometry( Gui.root )[2:]
		newWindowX = rootDistanceFromScreenLeft + 180 + self.windowSpawnOffset
		newWindowY = rootDistanceFromScreenTop + 180 + self.windowSpawnOffset
		self.window.geometry( '+' + str(newWindowX) + '+' + str(newWindowY) )
		self.windowSpawnOffset += 30
		if self.windowSpawnOffset > 150: self.windowSpawnOffset = 15

		# Populate the window
		mainFrame = Tk.Frame( self.window )

		# Show any remembered colors
		if self.recentColors:
			self.recentColorImages = []
			self.itemColors = {}
			if len( self.recentColors ) < 13: canvasHeight = 19
			else: canvasHeight = 38

			ttk.Label( mainFrame, text='Recent Colors:' ).pack( anchor='w', padx=16, pady=4 )
			self.colorsCanvas = Tk.Canvas( mainFrame, borderwidth=2, relief='ridge', background='white', width=197, height=canvasHeight )
			self.colorsCanvas.pack( pady=4 )

			x = 10
			y = 9
			for i, rgbaColor in enumerate( reversed(self.recentColors) ):
				# Prepare and store an image object for the color
				colorSwatchImage = Image.new( 'RGBA', (8, 8), rgbaColor )
				colorSwatchWithBorder = ImageOps.expand( colorSwatchImage, border=1, fill='black' )
				self.recentColorImages.append( ImageTk.PhotoImage(colorSwatchWithBorder) )

				# Draw the image onto the canvas.
				itemId = self.colorsCanvas.create_image( x, y, image=self.recentColorImages[i], anchor='nw', tags='swatches' )
				self.itemColors[itemId] = rgbaColor

				x += 16
				if i == 11: # Start a new line
					x = 10
					y += 16

			self.colorsCanvas.tag_bind( 'swatches', '<1>', self.restoreColor )
			def onMouseEnter(e): self.colorsCanvas['cursor']='hand2'
			def onMouseLeave(e): self.colorsCanvas['cursor']=''
			self.colorsCanvas.tag_bind( 'swatches', '<Enter>', onMouseEnter )
			self.colorsCanvas.tag_bind( 'swatches', '<Leave>', onMouseLeave )

		# RGB Channels
		ttk.Label( mainFrame, text='Choose the RGB Channel values:' ).pack( anchor='w', padx=16, pady=4 )
		curtainFrame = Tk.Frame( mainFrame, borderwidth=2, relief='ridge', width=250, height=50, cursor='hand2' )
		whiteCurtain = Tk.Frame( curtainFrame, bg='white', width=25, height=50 )
		whiteCurtain.pack( side='left' )

		focusColorsFrame = Tk.Frame( curtainFrame, width=200, height=50 )
		# Combine the initial color with the defalt background color, to simulate alpha on the colored frame (since Frames don't support alpha)
		bgColor16Bit = Gui.root.winfo_rgb( focusColorsFrame['bg'] )
		self.nativeBgColor = ( bgColor16Bit[0]/256, bgColor16Bit[1]/256, bgColor16Bit[2]/256 ) # Reduce it to an 8-bit colorspace
		newColors = []
		alphaBlending = round( self.currentRGBA[-1] / 255.0, 2 )
		for i, colorChannel in enumerate( self.nativeBgColor ):
			newColors.append( int(round( (alphaBlending * self.currentRGBA[i]) + (1-alphaBlending) * colorChannel )) )
		originalColorBg = rgb2hex( newColors )
		if getLuminance( originalColorBg + 'ff' ) > 127: fontColor = 'black'
		else: fontColor = 'white'
		self.originalColor = Tk.Frame( focusColorsFrame, bg=originalColorBg, width=200, height=25 )
		Tk.Label( self.originalColor, text='Original Color', bg=originalColorBg, foreground=fontColor ).pack()
		self.currentRgbDisplay = Tk.Frame( focusColorsFrame, width=200, height=25 ) # , bg='#ACACAC'
		Tk.Label( self.currentRgbDisplay, text='New Color' ).pack()
		focusColorsFrame.pack( side='left' )
		for frame in [ self.originalColor, self.currentRgbDisplay ]:
			frame.pack()
			frame.pack_propagate( False )
			frame.bind( '<1>', self.pickRGB )
			frame.winfo_children()[0].bind( '<1>', self.pickRGB )

		blackCurtain = Tk.Frame( curtainFrame, bg='black', width=25, height=50 )
		blackCurtain.pack( side='left' )
		curtainFrame.pack( padx=5, pady=4 )
		curtainFrame.pack_propagate( False )
		for frame in curtainFrame.winfo_children(): frame.pack_propagate( False )

		# Alpha Channel
		ttk.Label( mainFrame, text='Choose the Alpha Channel value:' ).pack( anchor='w', padx=16, pady=4 )
		alphaRowFrame = Tk.Frame( mainFrame )
		self.alphaEntry = ttk.Entry( alphaRowFrame, width=3 )
		self.alphaEntry.pack( side='left', padx=4 )
		self.alphaEntry.bind( '<KeyRelease>', self.alphaUpdated )
		self.alphaSlider = ttk.Scale( alphaRowFrame, orient='horizontal', from_=0, to=255, length=260, command=self.alphaUpdated )
		self.alphaSlider.pack( side='left' , padx=4 )
		alphaRowFrame.pack( padx=5, pady=4 )

		# Color Value Conversions
		ttk.Label( mainFrame, text='Color Space Comparisons:' ).pack( anchor='w', padx=16, pady=4 )
		colorEntryFieldsFrame = Tk.Frame( mainFrame )

		# RGBA (decimal and hex forms)
		ttk.Label( colorEntryFieldsFrame, text='RGBA:' ).grid( column=0, row=0, padx=5 )
		self.rgbaStringVar = Tk.StringVar()
		self.rgbaEntry = ttk.Entry( colorEntryFieldsFrame, textvariable=self.rgbaStringVar, width=16, justify='center' )		
		self.rgbaEntry.grid( column=1, row=0, padx=5 )
		self.rgbaEntry.bind( '<KeyRelease>', self.rgbaEntryUpdated )
		ttk.Label( colorEntryFieldsFrame, text='RGBA Hex:' ).grid( column=2, row=0, padx=5, pady=5 )
		self.hexColorStringVar = Tk.StringVar()
		self.rgbaHexEntry = ttk.Entry( colorEntryFieldsFrame, textvariable=self.hexColorStringVar, width=10, justify='center' )
		self.rgbaHexEntry.grid( column=3, row=0, padx=5 )
		self.rgbaHexEntry.bind( '<KeyRelease>', self.hexEntryUpdated )

		# TPL Formats
		ttk.Label( colorEntryFieldsFrame, text='TPL Format:' ).grid( column=0, row=1, padx=5 )
		self.tplFormat = Tk.StringVar()
		if 'Palette' in self.title: # Limit the selection of formats to just those used for palettes.
			formatList = userFriendlyFormatList[3:-4]
		else: formatList = userFriendlyFormatList[:-4]

		self.tplFormat.set( formatList[defaultTplFormat] )
		self.tplFormatOptionMenu = ttk.OptionMenu( colorEntryFieldsFrame, self.tplFormat, formatList[defaultTplFormat], *formatList, command=self.updateColorDisplays )
		self.tplFormatOptionMenu.grid( column=1, row=1, padx=5, pady=5 )
		if 'Palette' in self.title: self.tplFormatOptionMenu['state'] = 'disabled'

		self.tplFormatStringVar = Tk.StringVar()
		self.tplFormatEntry = ttk.Entry( colorEntryFieldsFrame, textvariable=self.tplFormatStringVar, width=13, justify='center' )
		self.tplFormatEntry.grid( column=2, columnspan=2, row=1, padx=5, sticky='w' )
		self.tplFormatEntry.bind( '<KeyRelease>', self.tplEntryUpdated )

		colorEntryFieldsFrame.pack( padx=5, pady=4 )

		self.updateColorDisplays( updateImage=False )
		#self.alphaSlider.set( self.currentRGBA[-1] )

		# Buttons! For use when this isn't just a comparison tool, but being used as a color picker to replace a value in a game/file
		if self.title != 'Color Converter':
			buttonsFrame = Tk.Frame( mainFrame )
			ttk.Button( buttonsFrame, text='Submit', command=self.submit ).pack( side='left', ipadx=4, padx=20 )
			ttk.Button( buttonsFrame, text='Cancel', command=self.cancel ).pack( side='left', ipadx=4, padx=20 )
			buttonsFrame.pack( pady=8 )

		mainFrame.pack()

		self.updateEntryBorders( None )
		self.window.bind( '<FocusIn>', self.updateEntryBorders ) # Allows for switching between multiple open windows to move the highlighting around

	def updateEntryBorders( self, event ): # Updates the border color of palette entries to indicate whether they're selected
		if 'Palette' in self.title:
			# If any items are currently selected, change their border color back to normal
			for item in Gui.paletteCanvas.find_withtag( 'selected' ):
				Gui.paletteCanvas.itemconfig( item, fill='black' )
				Gui.paletteCanvas.dtag( item, 'selected' ) # Removes this tag from the canvas item

			# Use the paletteEntryOffset tag to locate the border item (getting its canvas ID)
			if self.datDataOffsets != ():
				borderIids = Gui.paletteCanvas.find_withtag( 't'+str(self.datDataOffsets[2]) )
				if borderIids:
					Gui.paletteCanvas.itemconfig( borderIids[0], fill=Gui.paletteCanvas.entryBorderColor, tags=('selected', 't'+str(self.datDataOffsets[2])) )

	def updateColorDisplays( self, updateImage=True, setAlphaEntry=True ): # Updates the visual representation, alpha value/slider, and colorspace Entry values
		currentTplFormat = int( self.tplFormat.get().split()[0][1:] )
		if currentTplFormat in [ 0, 1, 4 ]: alphaSupported = False
		else: alphaSupported = True

		# Combine the newly selected color with the default background color, to simulate alpha on the colored frame (since Frames don't support transparency)
		newColors = []
		alphaBlending = round( self.currentRGBA[-1] / 255.0, 2 )
		for i, color in enumerate( self.nativeBgColor ):
			newColors.append( int(round( (alphaBlending * self.currentRGBA[i]) + (1-alphaBlending) * color )) )
		currentColorLabel = self.currentRgbDisplay.winfo_children()[0]
		currentColorBg = rgb2hex( newColors )
		self.currentRgbDisplay['bg'] = currentColorBg
		currentColorLabel['bg'] = currentColorBg
		if getLuminance( currentColorBg + 'ff' ) > 127: currentColorLabel['fg'] = 'black'
		else: currentColorLabel['fg'] = 'white'

		# Set the alpha components of the GUI
		self.preventNextSliderCallback = True # Prevents an infinite loop where the programmatic setting of the slider causes another update for this function
		self.alphaEntry['state'] = 'normal'
		self.alphaSlider.state(['!disabled'])
		currentAlphaLevel = self.currentRGBA[-1]

		if not alphaSupported: # These formats do not support alpha; max the alpha channel display and disable the widgets
			self.alphaEntry.delete( 0, 'end' )
			self.alphaEntry.insert( 0, '255' )
			self.alphaSlider.set( 255 )
			self.alphaEntry['state'] = 'disabled'
			self.alphaSlider.state(['disabled'])
		elif setAlphaEntry: # Prevents moving the cursor position if the user is typing into this field
			self.alphaEntry.delete( 0, 'end' )
			self.alphaEntry.insert( 0, str(currentAlphaLevel) ) #.lstrip('0')
			self.alphaSlider.set( currentAlphaLevel )
		else: self.alphaSlider.set( currentAlphaLevel ) # User entered a value into the alphaEntry; don't modify that

		# Set the RGBA fields
		if alphaSupported:
			self.rgbaStringVar.set( ', '.join([ str(channel) for channel in self.currentRGBA ]) )
			self.hexColorStringVar.set( self.currentHexColor )
		else:
			self.rgbaStringVar.set( ', '.join([ str(channel) for channel in self.currentRGBA[:-1] ]) )
			self.hexColorStringVar.set( self.currentHexColor[:-2] )

		# Set the TPL Entry field
		self.tplHex = tplEncoder.encodeColor( currentTplFormat, self.currentRGBA )
		if currentTplFormat < 6:
			self.tplFormatStringVar.set( self.tplHex.upper() )
		elif currentTplFormat == 6: # In this case, the value will actually be a tuple of the color parts
			self.tplFormatStringVar.set( self.tplHex[0].upper() + ' | ' + self.tplHex[1].upper() )
		else: self.tplFormatStringVar.set( 'N/A' )

		if 'Palette' in self.title and updateImage: 
			# Validate the encoded color
			if len( self.tplHex ) != 4 or not validHex( self.tplHex ):
				msg( 'The newly generated color was not two bytes!' )

			else:
				self.updateTexture( self.tplHex )

	def pickRGB( self, event ):
		try: rgbValues, hexColor = askcolor( initialcolor='#'+self.currentHexColor[:-2], parent=self.window )
		except: rgbValues, hexColor = '', ''

		if rgbValues:
			# Get the current alpha value, and combine it with the colors chosen above.
			currentAlphaLevel = int( round(self.alphaSlider.get()) )

			self.currentRGBA = ( rgbValues[0], rgbValues[1], rgbValues[2], currentAlphaLevel )
			self.currentHexColor = hexColor.replace('#', '').upper() + "{0:0{1}X}".format( currentAlphaLevel, 2 )
			self.updateColorDisplays()

	def alphaUpdated( self, event ):
		if self.preventNextSliderCallback:
			self.preventNextSliderCallback = False
			return
		
		if isinstance( event, str ): # Means this was updated from the slider widget
			newAlphaValue = int( float(event) )
			setAlphaEntry = True
		else: # Updated from the Entry widget
			newAlphaValue = int( round(float( event.widget.get() )) )
			setAlphaEntry = False

		self.currentRGBA = self.currentRGBA[:-1] + ( newAlphaValue, )
		self.currentHexColor = self.currentHexColor[:-2] + "{0:0{1}X}".format( newAlphaValue, 2 )
		self.updateColorDisplays( setAlphaEntry=setAlphaEntry )

	def rgbaEntryUpdated( self, event ):
		# Parse and validate the input
		channels = event.widget.get().split(',')
		channelsList = []
		parsingError = False

		for channelValue in channels:
			try:
				newInt = int( float(channelValue) )
				if newInt > -1 and newInt < 256: channelsList.append( newInt )
			except: 
				parsingError = True
				break
		else: # Got through the above loop with no break. Still got one more check.
			if len( channelsList ) != 4:
				parsingError = True

		if parsingError:
			if event.keysym  == 'Return': # User hit the "Enter" key in a confused attempt to force an update
				msg( 'The input should be in the form, "r, g, b, a", where each value is within the range of 0 - 255.', 'Invalid input or formatting.' )

		else: # Everything checks out, update the color and GUI
			self.currentRGBA = tuple( channelsList )
			self.currentHexColor = ''.join( [ "{0:0{1}X}".format( channel, 2 ) for channel in self.currentRGBA ] )
			self.updateColorDisplays()

	def hexEntryUpdated( self, event ):
		# Parse and validate the input
		inputStr = event.widget.get()
		channelsList, parsingError = hex2rgb( inputStr )

		if parsingError:
			if event.keysym  == 'Return': # User hit the "Enter" key in a confused attempt to force an update
				msg( 'The input should be in the form, "RRGGBBAA", where each value is within the hexadecimal range of 00 - FF.', 'Invalid input or formatting.' )

		else: # Everything checks out, update the color and GUI
			self.currentRGBA = tuple( channelsList )
			self.currentHexColor = ''.join( [ "{0:0{1}X}".format( channel, 2 ) for channel in self.currentRGBA ] )
			self.updateColorDisplays()

	def tplEntryUpdated( self, event ):
		tplHex = self.tplFormatStringVar.get().replace('0x', '').replace('|', '')
		nibbleCount = { 0:1, 1:2, 2:2, 3:4, 4:4, 5:4, 6:8, 8:1, 9:2, 10:4, 14:1 } # How many characters should be present in the string
		currentTplFormat = int( self.tplFormat.get().split()[0][1:] )

		if len( tplHex ) == nibbleCount[currentTplFormat] and validHex( tplHex ):
			self.currentRGBA = tplDecoder.decodeColor( currentTplFormat, tplHex )
			self.currentHexColor = ''.join( [ "{0:0{1}X}".format( channel, 2 ) for channel in self.currentRGBA ] )
			self.updateColorDisplays()

	def restoreColor( self, event ):
		item = event.widget.find_closest( event.x, event.y )[0]
		self.currentRGBA = self.itemColors[item]
		self.currentHexColor = ''.join( [ "{0:0{1}X}".format( channel, 2 ) for channel in self.currentRGBA ] )
		self.updateColorDisplays()

	def updateRecentColors( self ):
		# If the current color is already in the list, remove it, and add the color to the start of the list.
		for i, colorTuple in enumerate( self.recentColors ):
			if colorTuple == self.currentRGBA:
				self.recentColors.pop( i )
				break
		self.recentColors.append( self.currentRGBA )

		# Keep the list under a certain size
		while len( self.recentColors ) > 24:
			self.recentColors.pop( 0 )

	def updateTexture( self, paletteEntryHex ): # This function only used when updating palette colors
		if self.datDataOffsets != ():
			if paletteEntryHex == self.lastUpdatedColor:
				return

			# Replace the color in the image or palette data
			_, _, paletteEntryOffset, imageDataOffset = self.datDataOffsets
			globalDatFile.updateData( paletteEntryOffset, bytearray.fromhex(paletteEntryHex), 'Palette entry modified', trackChange=False )
			
			# Load the new data for the updated texture and display it
			width, height, imageType = globalDatFile.structs[imageDataOffset].getAttributes()[1:4]
			imageDataLength = getImageDataLength( width, height, imageType )
			loadSuccessful = renderTextureData( imageDataOffset, width, height, imageType, imageDataLength, allowImageDumping=False )
			if not loadSuccessful:
				msg( 'There was an error rendering the new texture data.' )
				return

			drawTextureToMainDisplay( imageDataOffset )

			populatePaletteTab( imageDataOffset, imageDataLength, imageType )

			self.lastUpdatedColor = paletteEntryHex
			updateProgramStatus( 'Palette Color Updated' )

	def submit( self ):
		self.updateRecentColors()
		if 'Palette' in self.title:
			globalDatFile.unsavedChanges.append( 'Palette color ' + self.initialColor + ' changed to ' + self.currentHexColor + '.' )
		self.close()

	def cancel( self ):
		# If the window was being used to update a palette color, revert the color back to the original
		if 'Palette' in self.title: 
			self.updateTexture( self.datDataOffsets[1] )
		self.currentHexColor = self.initialColor
		self.close()

	def close( self ):
		self.window.destroy()
		if self.windowId: 
			del self.windows[self.windowId]

																				#================================#
																				# ~ ~ GUI Specific Functions ~ ~ #
																				#================================#


def cmsg( message, title='', align='center', buttons=None, makeModal=False ):
	CopyableMessageWindow( Gui.root, message, title, align, buttons, makeModal )


def onFileTreeDoubleClick( event ):
	clickedRegion = Gui.isoFileTree.identify_region( event.x, event.y ) # Possible returns: 'heading', 'tree', 'cell', 'nothing'

	if clickedRegion == 'tree' or clickedRegion == 'cell': # 'tree' = the first default/navigation column, 'cell' should be any standard column/row
		iid = Gui.isoFileTree.identify( 'item', event.x, event.y )
		entity = Gui.isoFileTree.item( iid, 'values' )[1]

		if entity == 'folder': # Toggle the folder open or closed
			Gui.isoFileTree.item( iid, open=not Gui.isoFileTree.item( iid, 'open' ) )

		else: loadFileWithinDisc( iid )

	return 'break' # Returning 'break' is necessary to prevent any further propagation of the click event within the GUI


# def onStructureTreeDoubleClick( event ):
# 	clickedRegion = Gui.fileStructureTree.identify_region( event.x, event.y ) # Possible returns: 'heading', 'tree', 'cell', 'nothing'

# 	if clickedRegion == 'tree' or clickedRegion == 'cell': # 'tree' = the first default/navigation column, 'cell' should be any standard column/row
# 		iid = Gui.fileStructureTree.identify( 'item', event.x, event.y )
		
# 		# If the struct has children, toggle the 'folder' view open or closed
# 		if Gui.fileStructureTree.get_children():
# 			print 'toggling', iid
# 			Gui.fileStructureTree.item( iid, open=not Gui.fileStructureTree.item( iid, 'open' ) )

# 	return 'break' # Returning 'break' is necessary to prevent any further propagation of the click event within the GUI


class DataSpaceModifierWindow( object ):

	def __init__( self, master, mode ):
		window = self.window = Tk.Toplevel( master )
		window.title( 'Data Space Modifier' )
		window.resizable( width=False, height=False )
		window.attributes( '-toolwindow', 1 ) # Makes window framing small, like a toolbox widget.
		window.wm_attributes( '-topmost', 1 ) # Makes window stay topmost to other program windows.

		# Calculate the spawning position of the new window
		rootDistanceFromScreenLeft, rootDistanceFromScreenTop = getWindowGeometry( Gui.root )[2:]
		window.geometry( '+' + str(rootDistanceFromScreenLeft + 200) + '+' + str(rootDistanceFromScreenTop + 140) )

		if mode == 'collapse':
			usageText = ( 'This feature will remove/delete data from the file, starting at the given offset. '
						  'This includes removal of pointers within, or pointing to, the affected area. As well as removal of '
						  'root/reference nodes, and strings within the string table, if associated with the affected area. ' )
		else:
			usageText = ( 'This feature will increase the amount of file/data space at the given offset. '
						  'This does not create a new structure; the existing structure at the given offset is merely extended. ' )

		usageText += 'This feature may adjust the amount, in order to preserve alignment for other file structures. '
		usageText += '\n\nPlease note that this is an experimental feature. It is advised to make a back-up copy of your files before use.'

		ttk.Label( window, text=usageText, wraplength=400 ).pack( padx=15, pady=5 )
		
		entryFrame = ttk.Frame( window )
		ttk.Label( entryFrame, text='Offset:' ).grid( column=0, row=0, padx=7, pady=5 )
		self.offsetEntry = ttk.Entry( entryFrame, width=9 )
		self.offsetEntry.grid( column=1, row=0, padx=7, pady=5 )
		ttk.Label( entryFrame, text='Amount:' ).grid( column=0, row=1, padx=7, pady=5 )
		self.amountEntry = ttk.Entry( entryFrame, width=9 )
		self.amountEntry.grid( column=1, row=1, padx=7, pady=5 )
		entryFrame.pack( pady=5 )

		# Add the Submit/Cancel buttons
		buttonsFrame = ttk.Frame( window )
		self.okButton = ttk.Button( buttonsFrame, text='Submit', command=self.submit )
		self.okButton.pack( side='left', padx=10 )
		ttk.Button( buttonsFrame, text='Cancel', command=self.cancel ).pack( side='left', padx=10 )
		window.protocol( 'WM_DELETE_WINDOW', self.cancel ) # Overrides the 'X' close button.
		buttonsFrame.pack( pady=7 )

		# Move focus to this window (for keyboard control), and pause execution of the main window/thread until this window is closed.
		self.offsetEntry.focus_set()
		master.wait_window( window ) # Pauses execution of the calling function until this window is closed.

	def submit( self, event='' ):
		self.offset = self.offsetEntry.get().strip()
		self.amount = self.amountEntry.get().strip()
		self.window.destroy()

	def cancel( self, event='' ):
		self.offset = ''
		self.amount = ''
		self.window.destroy()


class popupDropdownWindow( object ): # todo: move to standardized common modules file

	def __init__( self, master, message='', title='', dropdownOptions=[], width=100 ):
		top = self.top = Tk.Toplevel( master )
		top.title( title )
		top.resizable( width=False, height=False )
		top.attributes( '-toolwindow', 1 ) # Makes window framing small, like a toolbox widget.
		top.wm_attributes( '-topmost', 1 ) # Makes window stay topmost to other program windows.

		# Calculate the spawning position of the new window
		rootDistanceFromScreenLeft, rootDistanceFromScreenTop = getWindowGeometry( Gui.root )[2:]
		top.geometry( '+' + str(rootDistanceFromScreenLeft + 200) + '+' + str(rootDistanceFromScreenTop + 140) )

		# Add a message for the user and the Drop-down widget for user input
		ttk.Label( top, text=message ).pack( pady=5 )
		self.dropDownValue = Tk.StringVar()
		self.dropdown = ttk.OptionMenu( top, self.dropDownValue, dropdownOptions[0], *dropdownOptions )
		self.dropdown.pack( padx=5, pady=6 )

		# Add the OK/Cancel buttons
		buttonsFrame = ttk.Frame( top )
		self.okButton = ttk.Button( buttonsFrame, text='Ok', command=self.cleanup )
		self.okButton.pack( side='left', padx=10 )
		ttk.Button( buttonsFrame, text='Cancel', command=self.cancel ).pack( side='left', padx=10 )
		top.protocol( 'WM_DELETE_WINDOW', self.cancel ) # Overrides the 'X' close button.
		buttonsFrame.pack( pady=7 )

		# Move focus to this window (for keyboard control), and pause execution of the main window/thread until this window is closed.
		self.dropdown.focus_set()
		master.wait_window( top ) # Pauses execution of the calling function until this window is closed.

	def cleanup( self, event='' ):
		self.top.destroy()

	def cancel( self, event='' ):
		self.dropDownValue.set( '' )
		self.top.destroy()


def selectAll( event ): # Adds bindings for normal CTRL-A functionality.
	if event.widget.winfo_class() == 'Text': event.widget.tag_add('sel', '1.0', 'end')
	elif event.widget.winfo_class() == 'TEntry': event.widget.selection_range(0, 'end')


def restoreEditedEntries( editedEntries ):

	# Change the background color of any edited entry widgets (Image Data Headers, Texture Struct properties, etc.) back to white.
	for widget in editedEntries:
		if widget.winfo_exists():
			if widget.__class__ == HexEditDropdown: # This is a ttk widget, which changes background color using a style
				widget.configure( style='TMenubutton' )
			else:
				defaultSystemBgColor = getattr( widget, 'defaultSystemBgColor', None )
				if defaultSystemBgColor: # If it has this property, it's a DisguisedEntry (used for the Game ID entry field)
					widget.configure( background=defaultSystemBgColor )
				else: widget.configure( background="white" )
	editedEntries = []


def onProgramClose():
	global programClosing

	# Make sure there aren't any changes pending to be saved (warns user if there are).
	if globalDatFile and not globalDatFile.noChangesToBeSaved( programClosing ): return
	elif globalBannerFile and not globalBannerFile.noChangesToBeSaved( programClosing ): return
	elif not noDiscChangesToBeSaved(): return

	programClosing = True
	Gui.root.aboutWindow = None # Ends the infinite loop the aboutWindow generates.

	# Shut down other decoding processes or threads that may be running
	#cancelCurrentRenders() # Should be enabled if multiprocessing is enabled

	# Check if the texture dumps should be deleted.
	if generalBoolSettings['deleteImageDumpsOnExit'].get() and os.path.exists( texDumpsFolder ):
		for the_file in os.listdir(texDumpsFolder):
			file_path = os.path.join(texDumpsFolder, the_file)
			try:
				if os.path.isfile(file_path): os.remove(file_path)
				elif os.path.isdir(file_path): shutil.rmtree(file_path)
			except Exception as e: msg( e )

	# Delete any temporary files that may be left over, only if they are not in use (may be used by a hex editor if it's open)!
	try: # Precaution. Really don't want this function to fail!
		hexEditorPath = settings.get('General Settings', 'hexEditorPath')
		tempFolder = scriptHomeFolder + '\\bin\\tempFiles\\'

		if programClosing and hexEditorPath and os.path.exists( tempFolder ):
			hexProgramName = os.path.basename( hexEditorPath )

			for process in psutil.process_iter():
				if process.name().lower() == hexProgramName.lower(): break
			else: # Loop above didn't break; the hex editor doesn't appear to be running
				try: shutil.rmtree( tempFolder )
				except: print 'Unable to delete the hex temp folder for an unknown reason.'
	except: print 'unexplained error while checking processes for a running hex editor'

	# Close the program.
	if programClosing: # If a DAT is being scanned, let that loop finish its current iteration and then close the program, to avoid errors.
		Gui.root.destroy() # Stops the GUI's mainloop and destroys all widgets: https://stackoverflow.com/a/42928131/8481154


def setImageFilters(): #todo should be a class
	if Gui.root.imageFiltersWindow != None: Gui.root.imageFiltersWindow.deiconify()
	else:
		loadSettings() # Persistent storage from settings.ini

		imageFiltersWindow = Tk.Toplevel()
		imageFiltersWindow.title('Texture Filters')
		imageFiltersWindow.attributes('-toolwindow', 1) # Makes window framing small, like a toolbox/widget.

		# Calculate the spawning position of the new window
		rootDistanceFromScreenLeft, rootDistanceFromScreenTop = getWindowGeometry( Gui.root )[2:]
		imageFiltersWindow.geometry( '+' + str(rootDistanceFromScreenLeft + 70) + '+' + str(rootDistanceFromScreenTop + 70) )
		Gui.root.imageFiltersWindow = imageFiltersWindow

		mainFrame = Tk.Frame(imageFiltersWindow)
		ttk.Label(mainFrame, text='Only show textures that meet this criteria:').pack(padx=10, pady=4)

		widthTuple = imageFilters['widthFilter']
		row1 = Tk.Frame(mainFrame)
		ttk.Label(row1, text='Width: ').pack(side='left')
		widthComparator = Tk.StringVar()
		widthComparator.set( widthTuple[0] )
		Tk.OptionMenu(row1, widthComparator, '<', '<=', '=', '>', '>=').pack(side='left')
		widthValue = Tk.StringVar()
		widthValue.set( widthTuple[1] )
		Tk.Entry(row1, textvariable=widthValue, width=6).pack(side='left')
		row1.pack(padx=10, pady=4)

		heightTuple = imageFilters['heightFilter']
		row2 = Tk.Frame(mainFrame)
		ttk.Label(row2, text='Height: ').pack(side='left')
		heightComparator = Tk.StringVar()
		heightComparator.set( heightTuple[0] )
		Tk.OptionMenu(row2, heightComparator, '<', '<=', '=', '>', '>=').pack(side='left')
		heightValue = Tk.StringVar()
		heightValue.set( heightTuple[1] )
		Tk.Entry(row2, textvariable=heightValue, width=6).pack(side='left')
		row2.pack(padx=10, pady=4)

		aspectRatioTuple = imageFilters['aspectRatioFilter']
		row3 = Tk.Frame(mainFrame)
		ttk.Label(row3, text='Aspect Ratio: ').pack(side='left')
		aspectRatioComparator = Tk.StringVar()
		aspectRatioComparator.set( aspectRatioTuple[0] )
		Tk.OptionMenu(row3, aspectRatioComparator, '<', '<=', '=', '>', '>=').pack(side='left')
		aspectRatioValue = Tk.StringVar()
		aspectRatioValue.set( aspectRatioTuple[1] )
		Tk.Entry(row3, textvariable=aspectRatioValue, width=6).pack(side='left')
		row3.pack(padx=10, pady=4)

		imageTypeTuple = imageFilters['imageTypeFilter']
		row4 = Tk.Frame(mainFrame)
		ttk.Label(row4, text='Texture Type: ').pack(side='left')
		imageTypeComparator = Tk.StringVar()
		imageTypeComparator.set( imageTypeTuple[0] )
		Tk.OptionMenu(row4, imageTypeComparator, '<', '<=', '=', '>', '>=').pack(side='left')
		imageTypeValue = Tk.StringVar()
		imageTypeValue.set( imageTypeTuple[1] )
		Tk.Entry(row4, textvariable=imageTypeValue, width=6).pack(side='left')
		row4.pack(padx=10, pady=4)

		offsetTuple = imageFilters['offsetFilter']
		row5 = Tk.Frame(mainFrame)
		ttk.Label(row5, text='Offset (location in file): ').pack(side='left')
		offsetComparator = Tk.StringVar()
		offsetComparator.set( offsetTuple[0] )
		Tk.OptionMenu(row5, offsetComparator, '<', '<=', '=', '>', '>=').pack(side='left')
		offsetValue = Tk.StringVar()
		offsetValue.set( offsetTuple[1] )
		Tk.Entry(row5, textvariable=offsetValue, width=10).pack(side='left')
		row5.pack(padx=10, pady=4)

		# Button functions
		def close(): 
			Gui.root.imageFiltersWindow.destroy()
			Gui.root.imageFiltersWindow = None
		imageFiltersWindow.protocol('WM_DELETE_WINDOW', close) # Overrides the 'X' close button.

		def save():
			if not os.path.exists( settingsFile ): 
				msg( 'Unable to find the settings file. Reloading this window should recreate it.' )
				return False

			unsavedSettings = []

			with open( settingsFile, 'w') as theSettingsFile:
				# For each setting, if the value is a number or blank, update the value and its comparitor in the program and settings file.
				width = widthValue.get().replace(',', '')
				if not isNaN(width) or width == '': 
					imageFilters['widthFilter'] = ( widthComparator.get(), width )
					settings.set( 'Texture Search Filters', 'widthFilter', widthComparator.get() + '|' + width )
				else: unsavedSettings.append( 'width' )
				height = heightValue.get().replace(',', '')
				if not isNaN(height) or height == '': 
					imageFilters['heightFilter'] = ( heightComparator.get(), height )
					settings.set( 'Texture Search Filters', 'heightFilter', heightComparator.get() + '|' + height )
				else: unsavedSettings.append( 'height' )

				aspectRatio = aspectRatioValue.get()
				try:
					# Make sure that the aspect ratio can be converted to a number.
					if ':' in aspectRatio:
						numerator, denomenator = aspectRatio.split(':')
						convertedAspectRatio = float(numerator) / float(denomenator)
					elif '/' in aspectRatio:
						numerator, denomenator = aspectRatio.split('/')
						convertedAspectRatio = float(numerator) / float(denomenator)
					elif aspectRatio != '': convertedAspectRatio = float(aspectRatio)

					if aspectRatio == '' or not isNaN( convertedAspectRatio ):	
						imageFilters['aspectRatioFilter'] = ( aspectRatioComparator.get(), aspectRatio )
						settings.set( 'Texture Search Filters', 'aspectRatioFilter', aspectRatioComparator.get() + '|' + aspectRatio )
					else: unsavedSettings.append( 'aspect ratio' )
				except:
					unsavedSettings.append( 'aspect ratio' )

				imageType = imageTypeValue.get().replace('_', '')
				if not isNaN(imageType) or imageType == '': 
					imageFilters['imageTypeFilter'] = ( imageTypeComparator.get(), imageType ) # str(int()) is in case the value was in hex
					settings.set( 'Texture Search Filters', 'imageTypeFilter', imageTypeComparator.get() + '|' + imageType )
				else: unsavedSettings.append( 'texture type' )
				offset = offsetValue.get().replace(',', '')
				if (validOffset(offset) and not isNaN(int(offset,16))) or offset == '':
					imageFilters['offsetFilter'] = ( offsetComparator.get(), offset )
					settings.set( 'Texture Search Filters', 'offsetFilter', offsetComparator.get() + '|' + offset )
				else: unsavedSettings.append( 'offset' )
				settings.write( theSettingsFile )

			if unsavedSettings != []:
				msg('The filters for ' + grammarfyList( unsavedSettings ) + ' could not saved. The entries must be a number or left blank, with the '
					'exception of aspect ratio (which may be a number, fraction, float (decimal), or a ratio like "4:3").')
				imageFiltersWindow.lift()
				return False
			else: return True

		def saveNclose():
			successfullySaved = save()

			# If saving doesn't work or the settings file wasn't found, don't close the window, so the settings aren't lost.
			if successfullySaved: close()

		def saveNreload():
			success = save()

			if success: # If the settings file wasn't found, don't close the window, so the settings aren't lost.
				close()

				clearDatTab()
				scanDat()

				# Switch to the DAT Texture Tree tab
				Gui.mainTabFrame.select( Gui.datTab ) # scanDat will now be called by the onMainTabChanged event handler

		def clear(): # Set all values back to default.
			widthComparator.set( '=' )
			widthValue.set( '' )
			heightComparator.set( '=' )
			heightValue.set( '' )
			aspectRatioComparator.set( '=' )
			aspectRatioValue.set( '' )
			imageTypeComparator.set( '=' )
			imageTypeValue.set( '' )
			offsetComparator.set( '=' )
			offsetValue.set( '' )

		# The buttons.
		row6 = Tk.Frame( mainFrame, width=200 )
		btnFrame = Tk.Frame(row6)
		ttk.Button( btnFrame, text='Clear',command=clear ).pack( side='left', padx=5 )
		ttk.Button( btnFrame, text='Save', command=saveNclose ).pack( side='right', padx=5 )
		btnFrame.pack()
		ttk.Button( row6, text='Save and Rescan Textures', command=saveNreload ).pack( fill='x', padx=5, pady=4 )
		row6.pack( pady=4 )

		mainFrame.pack()


def showHelpWindow():
	if Gui.root.helpWindow != None: Gui.root.helpWindow.deiconify()
	else:
		loadSettings() # Persistent storage from settings.ini

		# Define the window
		helpWindow = Tk.Toplevel()
		helpWindow.title('Help')
		helpWindow.attributes('-toolwindow', 1) # Makes window framing small, like a toolbox/widget.
		helpWindow.resizable(width=False, height=False)
		helpWindow.wm_attributes('-topmost', 1) # Makes window stay topmost (main program still usable).
		Gui.root.helpWindow = helpWindow

		# Calculate the spawning position of the new window
		rootDistanceFromScreenLeft, rootDistanceFromScreenTop = getWindowGeometry( Gui.root )[2:]
		helpWindow.geometry( '+' + str(rootDistanceFromScreenLeft + 180) + '+' + str(rootDistanceFromScreenTop + 140) )
		helpWindow.focus()

		mainFrame = Tk.Frame(helpWindow)

		# Button functions
		def close():
			Gui.root.helpWindow.destroy()
			Gui.root.helpWindow = None
		helpWindow.protocol('WM_DELETE_WINDOW', close) # Overrides the 'X' close button.

		def gotoWorkshop( event ): webbrowser.open( 'http://smashboards.com/forums/melee-workshop.271/' )
		def gotoOfficialThread( event ): webbrowser.open( 'http://smashboards.com/threads/new-tools-for-texture-hacking.373777/' )
		def gotoHowToHackAnyTexture( event ): webbrowser.open( 'http://smashboards.com/threads/how-to-hack-any-texture.388956/' )
		def gotoMeleeHacksAndYou( event ): webbrowser.open( 'http://smashboards.com/threads/melee-hacks-and-you-updated-5-21-2015.247119/#post-4917885' )

		label = ttk.Label( mainFrame, text='- =  The Melee Workshop  = -', foreground='#00F', cursor='hand2' )
		label.bind( '<1>', gotoWorkshop )
		label.pack(pady=4)

		gridSection = Tk.Frame( mainFrame ) # These contents are grouped together so they can use the grid geometry manager rather than .pack()
		ttk.Label( gridSection, image=Gui.imageBank('helpWindowDivider') ).grid( column=0, row=0, columnspan=2 )
		label = ttk.Label( gridSection, text='Read Up on Program Usage', foreground='#00F', cursor='hand2' )
		label.bind( '<1>', showReadMeFile )
		label.grid( column=0, row=1 )
		ttk.Label( gridSection, text='For documentation on this program').grid( column=1, row=1 )

		ttk.Label( gridSection, image=Gui.imageBank('helpWindowDivider') ).grid( column=0, row=2, columnspan=2 )
		label = ttk.Label( gridSection, text="DTW's Official Thread", foreground='#00F', cursor='hand2' )
		label.bind('<1>', gotoOfficialThread)
		label.grid( column=0, row=3 )
		ttk.Label( gridSection, text='Questions, feature requests, and other discussion on '
			'this program can be posted here').grid( column=1, row=3 )

		ttk.Label( gridSection, image=Gui.imageBank('helpWindowDivider') ).grid( column=0, row=4, columnspan=2 )
		label = ttk.Label( gridSection, text='How to Hack Any Texture', foreground='#00F', cursor='hand2' )
		label.bind('<1>', gotoHowToHackAnyTexture)
		label.grid( column=0, row=5 )
		ttk.Label( gridSection, text="If for some reason your texture doesn't "
			"appear in this program, then you can fall back onto this thread").grid( column=1, row=5 )

		ttk.Label( gridSection, image=Gui.imageBank('helpWindowDivider') ).grid( column=0, row=6, columnspan=2 )
		label = ttk.Label( gridSection, text='OP of Melee Hacks and You', foreground='#00F', cursor='hand2' )
		label.bind('<1>', gotoMeleeHacksAndYou)
		label.grid( column=0, row=7 )
		ttk.Label( gridSection, text='The first post in this thread contains many '
			'resources on all subjects to help you get started').grid( column=1, row=7 )

		ttk.Label( gridSection, image=Gui.imageBank('helpWindowDivider') ).grid( column=0, row=8, columnspan=2 )

		for label in gridSection.grid_slaves( column=1 ):
			label.config( wraplength=220 )

		for label in gridSection.winfo_children():
			label.grid_configure( ipady=4, padx=7 )

		gridSection.pack( padx=4 )

		ttk.Label( mainFrame, text='Random Pro-tip: ' + proTips[random.randint( 1, len(proTips) )], wraplength=380 ).pack( padx=4, pady=12 )

		mainFrame.pack()


proTips = {
	1: ( "Did you know that you can drag-and-drop files directly onto "
		 "the program icon (the .exe file) or the GUI to open them?" ),

	2: ( "There are multiple useful behaviors you can call upon when importing textures:"
		 "\n- When viewing the contents of a disc on the 'Disc File Tree' tab. The imported "
		 "texture's destination will be determined by the file's name. For example, "
		 'the file "MnSlMap.usd_0x38840_2.png" would be imported into the disc in the file "MnSlMap.usd" '
		 "at offset 0x38840. This can be very useful for bulk importing many textures at once."
		 "\n- Navigate to a specific texture in the 'DAT Texture Tree' tab, select a texture, and you "
		 'can import a texture to replace it with without concern for how the file is named.' ),

	3: ( 'The color of the status message ("File Scan Complete", etc.) is purely used to indicate '
		  "whether or not there are changes that have yet to be saved. Green means everything has "
		  "been saved to disc/file. Red means there are changes that have not yet been saved." ),

	4: ( "For CSPs (Character Select Portraits), if you're trying to mimic "
		 "the game's original CSP shadows, they are 10px down and 10px to the left." ),

	5: ( "Use the boost to chase!" ),

	6: ( "When working in GIMP and opting to use a palette, it's important that you delete "
		 "ALL hidden and unused layers BEFORE generating a palette for your texture. "
		 "This is because if other layers are present, even if not visible, GIMP "
		 "will take their colors into account to generate a palette. (If you have a lot of "
		 "layers, an easier method may be to create a 'New from Visible' layer, and then copy that "
		 "to a new, blank project.)" ),

	7: ( "Did you know that if you hold SHIFT while right-clicking "
		 "on a file in Windows, there appears a context menu option called "
		 "'Copy as path'? This will copy the file's full path into your clipboard, "
		 "so you can then easily paste it into one of this program's text fields." ),

	8: ( 'A quick and easy way to view file structures relating to a given texture is to use '
		 'the "Show in Structural Analysis" feature, found by right-clicking on a texture.' ),

	9: ( "You don't have to close this program in order to run your disc in Dolphin "
		 '(though you do need to stop emulation if you want to save changes to the disc).' ),

	10: ( "DODONGO DISLIKES SMOKE." ),

	11: ( "Have you ever noticed those dotted lines at the top of the 'Open Recent' "
		  "and 'Texture Operations' menus? Try clicking on one sometime! It will turn the menu into a window for fast-access." ),

	12: ( "If you click on one of the 'Disc Shortcuts' before loading a disc, DTW will load the "
		  "last disc that you've used, and then jump to the appropriate section. They're two shortcuts in one!" ),

	13: ( "When DTW builds a disc from a root folder of files, it can build a ISO that's a good amount smaller than the "
		  "standard disc size of ~1.35 GB (1,459,978,240 bytes). Useful if you want to add more or larger files." ),

	14: ( 'You can actually modify the amount of empty space, or "padding", present between files in your ISO. A small '
		  'amount of padding allows for more files or total data in the same size ISO. While more padding allows you to '
		  'replace/import larger files without having to rebuild the disc.' ),

	15: ( "Did you notice the cheese in the toilet? It's in every level." ),

	16: ( "This program has a lot of lesser-known but very useful features, some of which aren't easily found "
		  "by browsing the GUI. Check out the Program Usage.txt to find them all." ),

	#17: ( '' ),
	#18: ( '' ),
	#19: ( '' ),
	#20: ( "IT'S A SECRET TO EVERYBODY." ),

}


def showReadMeFile( event=None ): # May take a click event from the help window click binding
	try:
		os.startfile( scriptHomeFolder + '\\Program Usage.txt' )
	except:
		msg( "Couldn't find the 'Program Usage.txt' file!" )


def showSupportWindow():
	# Define the window
	helpWindow = Tk.Toplevel( Gui.root )
	helpWindow.title( 'Support DTW' )
	helpWindow.attributes( '-toolwindow', 1 ) # Makes window framing small, like a toolbox/widget.
	helpWindow.resizable( width=False, height=False )
	helpWindow.wm_attributes( '-topmost', 1 ) # Makes window stay topmost (main program still usable).

	# Calculate the spawning position of the new window
	rootDistanceFromScreenLeft, rootDistanceFromScreenTop = getWindowGeometry( Gui.root )[2:]
	helpWindow.geometry( '+' + str(rootDistanceFromScreenLeft + 120) + '+' + str(rootDistanceFromScreenTop + 100) )
	helpWindow.focus()

	mainCanvas = Tk.Canvas( helpWindow, bg='#101010', width=640, height=394, borderwidth=0, highlightthickness=0 )

	# Create and attach the background
	mainCanvas.create_image( 0, 0, image=Gui.imageBank('supportDTW'), anchor='nw' )

	# Create rectangles over the image to use as buttons
	mainCanvas.create_rectangle( 288, 224, 357, 245, outline="", tags=('paypalLink', 'link') )
	mainCanvas.create_rectangle( 350, 292, 432, 310, outline="", tags=('patreonLink', 'link') )

	# Bind a click event on the buttons to hyperlinks
	def gotoPaypal( event ): webbrowser.open( r'https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=K95AJCMZDR7CG&lc=US&item_name=Melee%20Modding&item_number=DTW&currency_code=USD&bn=PP%2dDonationsBF%3abtn_donate_SM%2egif%3aNonHosted' )
	def gotoPatreon( event ): webbrowser.open( r'https://www.patreon.com/drgn' )
	mainCanvas.tag_bind( 'paypalLink', '<1>', gotoPaypal )
	mainCanvas.tag_bind( 'patreonLink', '<1>', gotoPatreon )

	# Bind mouse hover events for buttons, for the cursor
	def changeCursorToHand( event ): helpWindow.config( cursor='hand2' )
	def changeCursorToArrow( event ): helpWindow.config( cursor='' )
	mainCanvas.tag_bind( 'link', '<Enter>', changeCursorToHand )
	mainCanvas.tag_bind( 'link', '<Leave>', changeCursorToArrow )

	mainCanvas.pack( pady=0, padx=0 )


def showAboutWindow(): # todo: should be a class based off of basicWindow
	if Gui.root.aboutWindow != None: Gui.root.aboutWindow.deiconify()
	else:
		# Define the window
		aboutWindow = Tk.Toplevel( Gui.root )
		aboutWindow.title( 'DAT Texture Wizard' )
		aboutWindow.attributes( '-toolwindow', 1 ) # Makes window framing small, like a toolbox/widget.
		aboutWindow.resizable( width=False, height=False )
		aboutWindow.wm_attributes( '-topmost', 1 )
		Gui.root.aboutWindow = aboutWindow

		# lulz
		Gui.root.aboutWindow.originalProgramStatus = Gui.programStatus.get()
		updateProgramStatus( 'Too good!' )

		# Calculate the spawning position of the new window
		rootDistanceFromScreenLeft, rootDistanceFromScreenTop = getWindowGeometry( Gui.root )[2:]
		aboutWindow.geometry( '+' + str(rootDistanceFromScreenLeft + 240) + '+' + str(rootDistanceFromScreenTop + 170) )
		aboutWindow.focus()

		# Button functions
		def close():
			updateProgramStatus( Gui.root.aboutWindow.originalProgramStatus )
			Gui.root.aboutWindow.destroy()
			Gui.root.aboutWindow = None
		aboutWindow.protocol( 'WM_DELETE_WINDOW', close ) # Overrides the 'X' close button.

		# Create the canvas
		aboutCanvas = Tk.Canvas( aboutWindow, bg='#101010', width=350, height=247 )
		aboutCanvas.pack()

		# Define a few images
		aboutCanvas.bannerImage = Gui.imageBank( 'pannerBanner' ) # 604x126
		aboutCanvas.hoverOverlayImage = Gui.imageBank('hoverOverlay')
		aboutCanvas.blankBoxImage = ImageTk.PhotoImage( Image.new('RGBA', (182,60)) ) # Sits behind the main background (same size/position as bgbg).

		# Attach the images to the canvas
		aboutCanvas.create_image( 88, 98, image=Gui.imageBank('bgbg'), anchor='nw' ) # Sits behind the main background (182x60).
		aboutCanvas.create_image( 10, 123, image=aboutCanvas.bannerImage, anchor='w', tags='r2lBanners' )
		aboutCanvas.create_image( 340, 123, image=aboutCanvas.bannerImage, anchor='e', tags='l2rBanners' )
		foregroundObject = aboutCanvas.create_image( 2, 2, image=Gui.imageBank('bg'), anchor='nw' ) # The main background, the mask (350x247).

		# Define and attach the text to the canvas
		windowFont = tkFont.Font(family='MS Serif', size=11, weight='normal')
		aboutCanvas.create_text( 207, 77, text='C r e a t e d   b y', fill='#d4d4ef', font=windowFont )
		aboutCanvas.create_text( 207, 174, text='Version ' + programVersion, fill='#d4d4ef', font=windowFont )
		aboutCanvas.create_text( 207, 204, text='Written in Python v' + sys.version.split()[0] + '\nand tKinter v' + str( Tk.TkVersion ), 
											justify='center', fill='#d4d4ef', font=windowFont )

		# Create a "button", and bind events for the mouse pointer, and for going to my profile page on click.
		aboutCanvas.create_image( 82, 98, image=aboutCanvas.blankBoxImage, activeimage=aboutCanvas.hoverOverlayImage, anchor='nw', tags='profileLink' ) # 88 in v4.3
		def gotoProfile( event ): webbrowser.open( 'http://smashboards.com/members/drgn.21936/' )
		def changeCursorToHand( event ): aboutWindow.config( cursor='hand2' )
		def changeCursorToArrow( event ): aboutWindow.config( cursor='' )
		aboutCanvas.tag_bind( 'profileLink', '<1>', gotoProfile )
		aboutCanvas.tag_bind( 'profileLink', '<Enter>', changeCursorToHand )
		aboutCanvas.tag_bind( 'profileLink', '<Leave>', changeCursorToArrow )

		# v Creates an infinite "revolving" image between the two background elements.
		i = 0
		while Gui.root.aboutWindow != None:
			if i == 0: 
				aboutCanvas.create_image( 614, 123, image=aboutCanvas.bannerImage, anchor='w', tags='r2lBanners' )
				aboutCanvas.create_image( 340 - 604, 123, image=aboutCanvas.bannerImage, anchor='e', tags='l2rBanners' )
				aboutCanvas.tag_lower( 'r2lBanners', foregroundObject ) # Update the layer order to keep the foreground on top.
				aboutCanvas.tag_lower( 'l2rBanners', foregroundObject ) # Update the layer order to keep the foreground on top.
			i += 1
			aboutCanvas.move( 'r2lBanners', -1, 0 )
			aboutCanvas.move( 'l2rBanners', 1, 0 )
			time.sleep( .13 ) # Value in seconds
			aboutCanvas.update()

			if i == 604: # Delete the first banner, so the canvas isn't infinitely long
				aboutCanvas.delete( aboutCanvas.find_withtag('r2lBanners')[0] )
				aboutCanvas.delete( aboutCanvas.find_withtag('l2rBanners')[0] )
				i = 0


def treeview_sort_column( treeview, col, reverse ):
	# Create a list of the items, as tuples of (statOfInterest, iid), and sort them.
	if col == 'file':
		if os.path.exists( globalDiscDetails['isoFilePath'] ): # Means that a disc has been loaded.
			# Make sure the disc doesn't have any changes that need saving first
			if unsavedDiscChanges and not globalDiscDetails['rebuildRequired']:
				okToSave = tkMessageBox.askyesno( 'OK to save disc changes?',
					'Changes to the disc must be saved before sorting its files.\n\nWould you like to save changes to the disc now?' )

				# Attempt to save, and exit this function if there was a problem.
				if not okToSave or not saveChanges(): return

			if not reverse:  # The default upon starting the program.
				rootIid = Gui.isoFileTree.get_children()[0]

				rowsList = []
				foldersToDelete = []
				def sortChildren( parent ):
					for iid in treeview.get_children( parent ):
						description, entity, isoOffset, fileSize, isoPath, source, data = treeview.item( iid, 'values' )

						if entity == 'folder':
							# Organize the contents of the folder first (so that the first file's offset, to use for this folder, will be the first of the set).
							sortChildren( iid )

							foldersToDelete.append( iid )
						else: 
							# Add this file to the sorting list.
							rowsList.append( (int(isoOffset, 16), iid) )

				sortChildren( rootIid )

				# Sort the items in the treeview.
				rowsList.sort( reverse=reverse )
				for index, ( columnValue, iid ) in enumerate( rowsList ): treeview.move( iid, rootIid, index )

				# Remove the folders from the treeview.
				for folder in foldersToDelete: treeview.delete( folder )

				# Update the treeview's header text and its function call for the next (reversed) sort.
				treeview.heading( '#0', text='File     (Sorted by Offset)' )
				treeview.heading( '#0', command=lambda: treeview_sort_column(treeview, col, True) )
			else:
				if isRootFolder( globalDiscDetails['isoFilePath'], showError=False )[0]: scanRoot()
				else: scanDisc()
	else:
		if col == 'texture': rowsList = [( int(treeview.set(iid, col).split()[0],16), iid ) for iid in treeview.get_children('')]
		elif col == 'dimensions': rowsList = [( int(treeview.set(iid, col).split(' x ')[0]) * int(treeview.set(iid, col).split(' x ')[1]), iid ) for iid in treeview.get_children('')]
		elif col == 'type': rowsList = [( treeview.set(iid, col).replace('_', ''), iid ) for iid in treeview.get_children('')]

		# Sort the rows and rearrange the treeview based on the newly sorted list.
		rowsList.sort(reverse=reverse)
		for index, ( columnValue, iid ) in enumerate( rowsList ): treeview.move( iid, '', index )

		# Set the function call for the next (reversed) sort.
		treeview.heading(col, command=lambda: treeview_sort_column( treeview, col, not reverse ))


def scanDiscItemForStats( iidSelectionsTuple, folder ):

	""" This is simply a helper function to recursively get the file size of all files in a given folder, 
		as well as total file count. """

	totalFileSize = 0 # Out of scope of the original declaration; need to recreate it.
	fileCount = 0

	for iid in folder:
		if iid not in iidSelectionsTuple: # Check that nothing is counted twice.
			_, entity, _, fileSize, _, _, _ = Gui.isoFileTree.item( iid, 'values' ) # description, entity, isoOffset, fileSize, isoPath, source, data
			if entity == 'file':
				totalFileSize += int( fileSize )
				fileCount += 1
			else:
				# Search the inner folder, and add the totals of the children within to the current count.
				folderSize, folderFileCount = scanDiscItemForStats( iidSelectionsTuple, Gui.isoFileTree.get_children(iid) )
				totalFileSize += folderSize
				fileCount += folderFileCount

	return totalFileSize, fileCount


def onFileTreeSelect( event ):
	iidSelectionsTuple = Gui.isoFileTree.selection()

	if len( iidSelectionsTuple ) != 0:
		# Get the collective size of all items currently selected
		totalFileSize = 0
		fileCount = 0
		for iid in iidSelectionsTuple:
			_, entity, isoOffset, fileSize, isoPath, _, _ = Gui.isoFileTree.item( iid, 'values' ) # description, entity, isoOffset, fileSize, isoPath, source, data

			if entity == 'file':
				totalFileSize += int( fileSize )
				fileCount += 1
			else:
				folderSize, folderFileCount = scanDiscItemForStats( iidSelectionsTuple, Gui.isoFileTree.get_children(iid) )
				totalFileSize += folderSize
				fileCount += folderFileCount

		# Update the Offset and File Size values in the GUI.
		if len( iidSelectionsTuple ) == 1 and entity == 'file': # If there's only one selection and it's a file.
			fileName = isoPath.split('/')[-1].lower()
			if isoOffset == '0' and fileName != 'boot.bin' and fileName != 'iso.hdr': isoOffset = 'N/A (External)' # Must be an external file.
			Gui.isoOffsetText.set( 'Disc Offset:  ' + isoOffset )
			Gui.internalFileSizeText.set( 'File Size:  {0:,} bytes'.format(totalFileSize) ) # Formatting in decimal with thousands delimiter commas
			Gui.internalFileSizeLabelSecondLine.set( '' )

		else: # A folder or multiple selections
			Gui.isoOffsetText.set( 'Disc Offset:  N/A' )
			Gui.internalFileSizeText.set( 'File Size:  {0:,} bytes'.format(totalFileSize) ) # Formatting in decimal with thousands delimiter commas
			Gui.internalFileSizeLabelSecondLine.set( '    (Totaled from {0:,} files)'.format(fileCount) )


def drawTextureToMainDisplay( iid ):

	""" Updates the main display area (the Image tab of the DAT Texture Tree tab) with a 
		texture's stored full-render image, if it has been rendered. """

	# Get the texture data if available, and pull info on the texture.
	textureImage = Gui.datTextureTree.fullTextureRenders.get( int(iid) )
	if not textureImage: 
		print 'did not get a texture image'
		return # May not have been rendered yet
	imageDataOffset, imageDataLength, textureWidth, textureHeight, imageType = parseTextureDetails( iid )

	# Get the current dimensions of the program.
	Gui.textureDisplay.update() # Ensures the info gathered below is accurate
	programWidth = Gui.root.winfo_width()
	programHeight = Gui.root.winfo_height()
	canvasWidth = Gui.textureDisplay.winfo_width()
	canvasHeight = Gui.textureDisplay.winfo_height()

	# Get the total width/height used by everything other than the canvas.
	baseW = Gui.defaultWindowWidth - canvasWidth
	baseH = programHeight - canvasHeight

	# Set the new program and canvas widths. (The +2 allows space for a texture border.)
	if textureWidth > canvasWidth: 
		newProgramWidth = baseW + textureWidth + 2
		newCanvasWidth = textureWidth + 2
	else:
		newProgramWidth = programWidth
		newCanvasWidth = canvasWidth

	# Set the new program and canvas heights. (The +2 allows space for a texture border.)
	if textureHeight > canvasHeight: 
		newProgramHeight = baseH + textureHeight + 2
		newCanvasHeight = textureHeight + 2
	else:
		newProgramHeight = programHeight
		newCanvasHeight = canvasHeight

	# Apply the new sizes for the canvas and root window.
	Gui.textureDisplay.configure( width=newCanvasWidth, height=newCanvasHeight ) # Adjusts the canvas size to match the texture.
	Gui.root.geometry( str(newProgramWidth) + 'x' + str(newProgramHeight) )

	# Delete current contents of the canvas, and redraw the grid if it's enabled
	Gui.textureDisplay.delete( 'all' )
	Gui.updateCanvasGrid( saveChange=False )

	# Add the texture image to the canvas, and draw the texture boundary if it's enabled
	Gui.textureDisplay.create_image(newCanvasWidth/2, newCanvasHeight/2, anchor='center', image=textureImage, tags='texture')
	updateCanvasTextureBoundary( saveChange=False )


def updateCanvasTextureBoundary( saveChange=True ): # Show/hide the border around textures.
	if generalBoolSettings['showTextureBoundary'].get():
		coords = Gui.textureDisplay.bbox('texture') # "bounding box" gets the coordinates of the item(s).

		if coords != None:
			x1, y1, x2, y2 = coords
			Gui.textureDisplay.create_rectangle( x1 - 1, y1 - 1, x2, y2, outline='blue', tags='border' ) # Expands the north/west borders by 1px, so they're not over the image.
		else:
			Gui.textureDisplay.delete( Gui.textureDisplay.find_withtag('border') )
	else:
		Gui.textureDisplay.delete( Gui.textureDisplay.find_withtag('border') )

	if saveChange:
		# Update the current selections in the settings file.
		with open( settingsFile, 'w') as theSettingsFile:
			settings.set( 'General Settings', 'showTextureBoundary', str(generalBoolSettings['showTextureBoundary'].get()) )
			settings.write( theSettingsFile )


def dndHandler( event, dropTarget ):
	# The paths that this event recieves are in one string, each enclosed in {} brackets (if they contain a space) and separated by a space. Turn this into a list.
	paths = event.data.replace('{', '').replace('}', '')
	drive = paths[:2]

	filepaths = [drive + path.strip() for path in paths.split(drive) if path != '']

	Gui.root.deiconify() # Brings the main program window to the front (application z-order).
	fileHandler( filepaths, dropTarget=dropTarget )


def onMouseWheelScroll( event ):

	""" Checks the widget under the mouse when a scroll event occurs, and then looks through the GUI geometry
		for parent widgets that may have scroll wheel support. """

	# Cross-platform resources on scrolling:
		# - http://stackoverflow.com/questions/17355902/python-tkinter-binding-mousewheel-to-scrollbar
		# - https://www.daniweb.com/programming/software-development/code/217059/using-the-mouse-wheel-with-tkinter-python

	# Get the widget currently under the mouse
	widget = Gui.root.winfo_containing( event.x_root, event.y_root )

	# Traverse upwards through the parent widgets, looking for a scrollable widget
	while widget:
		# Check for a scrollable frame (winfo_class sees this as a regular Frame)
		if widget.__class__.__name__ == 'VerticalScrolledFrame':
			widget = widget.canvas
			break

		elif widget.winfo_class() in ( 'Text', 'Treeview' ):
			break

		widget = widget.master

	# If the above loop didn't break (no scrollable found), "widget" will reach the top level item and become 'None'.
	if widget:
		widget.yview_scroll( -1*(event.delta/30), "units" )


def saveSettingsToFile(): # Update a pre-existing settings file (or create a new file if one does not exist) with the program's current settings.
	# Convert the program's BooleanVars to strings and update them in the settings object
	for setting in generalBoolSettingsDefaults:
		settings.set( 'General Settings', setting, str( generalBoolSettings[setting].get() ) )

	# Save the current settings
	with open( settingsFile, 'w') as theSettingsFile: settings.write( theSettingsFile )


def showUnsavedChanges():
	changesPending = False

	if globalDatFile and globalDatFile.unsavedChanges:
		unsavedChangesMessage = 'These DAT changes have not yet been saved:\n\n' + '\n'.join(globalDatFile.unsavedChanges)
		changesPending = True
	else: unsavedChangesMessage = 'No DAT changes are waiting to be saved.'

	if globalBannerFile and globalBannerFile.unsavedChanges:
		unsavedChangesMessage += '\n\nThese banner file changes have not yet been saved:\n\n' + '\n'.join(globalBannerFile.unsavedChanges)
		changesPending = True
	else: unsavedChangesMessage += '\n\nNo banner file changes are waiting to be saved.'

	if unsavedDiscChanges:
		unsavedChangesMessage += '\n\nThese disc changes have not yet been saved:\n\n' + '\n'.join(unsavedDiscChanges)
		changesPending = True
	else: unsavedChangesMessage += '\n\nNo disc changes are waiting to be saved.'

	if changesPending:
		cmsg( unsavedChangesMessage )
	else: 
		msg( 'No changes are waiting to be saved.' )


def updateProgramStatus( newStatus ):
	if newStatus == '' or newStatus.split()[0] != 'dontUpdate':
		# Determine the color to use for the status message, based on current pending changes
		if unsavedDiscChanges: 
			statusColor = '#a34343' # red; some change(s) not yet saved.
		elif globalDatFile and globalDatFile.unsavedChanges:
			statusColor = '#a34343' # red; some change(s) not yet saved.
		elif globalBannerFile and globalBannerFile.unsavedChanges:
			statusColor = '#a34343' # red; some change(s) not yet saved.
		else: # No changes pending save
			statusColor = '#292' # A green color, indicating no changes awaiting save.

		# Update the program status' color and message
		Gui.programStatusLabel['fg'] = statusColor
		Gui.programStatus.set( newStatus )


def togglePaletteCanvasColor( event ):
	if Gui.paletteCanvas["background"] == 'white': Gui.paletteCanvas.configure(background='#7F7F7F')
	elif Gui.paletteCanvas["background"] == '#7F7F7F': 
		Gui.paletteCanvas.configure(background='black')
		for item in Gui.paletteCanvas.find_withtag( 'descriptors' ): Gui.paletteCanvas.itemconfig( item, fill='white' )
	else: 
		Gui.paletteCanvas.configure(background='white')
		for item in Gui.paletteCanvas.find_withtag( 'descriptors' ): Gui.paletteCanvas.itemconfig( item, fill='black' )


def scanDiscForFile( searchString,  parentToSearch='' ): # Recursively searches the given string in all file name portions of iids in the file tree
	foundIid = ''
	for iid in Gui.isoFileTree.get_children( parentToSearch ):
		if iid.split('/')[-1].startswith( searchString.lower() ): return iid
		else: 
			foundIid = scanDiscForFile( searchString, iid ) # This might be a folder, try scanning its children
			if foundIid: break

	# If looking for one of the header files, but it wasn't found, try for "ISO.hdr" instead (used in place of boot.bin/bi2.bin by discs built by GCRebuilder)
	if not foundIid and ( searchString == 'boot.bin' or searchString == 'bi2.bin' ):
		foundIid = scanDiscForFile( 'iso.hdr' )

	return foundIid


def discFileTreeQuickLinks( event ):

	""" Scrolls the treeview in the Disc File Tree tab directly to a specific section.
		If a disc is not already loaded, the most recent disc that has been loaded in
		the program is loaded, and then scrolled to the respective section. """

	discNewlyLoaded = False

	# Check whether a disc is loaded.
	if globalDiscDetails['isoFilePath'] == '':
		# Check that there are any recently loaded discs (in the settings file).
		recentISOs = getRecentFilesLists()[0] # The resulting list is a list of tuples, of the form (path, dateLoaded)

		if not recentISOs:
			# No recent discs found. Prompt to open one.
			promptToOpenFile( 'iso' )
			discNewlyLoaded = True

		else: # ISOs found. Load the most recently used one
			recentISOs.sort( key=lambda recentInfo: recentInfo[1], reverse=True )
			pathToMostRecentISO = recentISOs[0][0].replace('|', ':')

			# Confirm the file still exists in the same place
			if os.path.exists( pathToMostRecentISO ):
				# Path validated. Load it. Don't update the details tab yet, since that will incur waiting for the banner animation
				fileHandler( [pathToMostRecentISO], updateDefaultDirectory=False, updateDetailsTab=False )
				discNewlyLoaded = True

			else: # If the file wasn't found above, prompt if they'd like to remove it from the remembered files list.
				if tkMessageBox.askyesno( 'Remove Broken Path?', 'The following file could not be found:\n"' + pathToMostRecentISO + '" .\n\nWould you like to remove it from the list of recent files?' ):
					# Update the list of recent ISOs in the settings object and settings file.
					settings.remove_option( 'Recent Files', pathToMostRecentISO.replace(':', '|') )
					with open( settingsFile, 'w') as theSettingsFile: settings.write( theSettingsFile )
				return

	# Scroll to the appropriate section, if any link besides 'Last Disc' was used
	target = event.widget['text']
	scrollToSection( target )

	# If the disc was just now loaded, the banner and disc details will still need to be updated.
	# The function to scan the ISO will have deliberately skipped this step during the loading above,
	# so that scrolling will happen without having to wait on the banner animation.
	if discNewlyLoaded:
		Gui.isoFileTree.update() # Updates the GUI first so that the scroll position is instanly reflected
		populateDiscDetails()


def scrollToSection( target ):
	isoFileTreeChildren = Gui.isoFileTree.get_children()
	if not isoFileTreeChildren: return

	gameId = globalDiscDetails['gameId'].lower()
	rootItem = isoFileTreeChildren[0]
	Gui.isoFileTree.see( rootItem )
	Gui.root.update()
	iid = ''
	indexOffset = 19

	# Determine the iid of the file to move the scroll position to
	if target == 'System':
		Gui.isoFileTree.yview_moveto( 0 )
		iid = scanDiscForFile( 'Start.dol' )

	elif target == 'Characters':
		if Gui.isoFileTree.exists( 'pl' ): # Check for the complimentary folder
			iidTuple = Gui.isoFileTree.get_children( 'pl' )
			if len( iidTuple ) > 0: 
				iid = iidTuple[0]
		else: 
			iid = scanDiscForFile( 'pl' ) # previously: 'plgk.dat'

	elif target == 'Menus (CSS/SSS)':
		iid = scanDiscForFile( 'mnmaall.' )
		indexOffset = 14

	elif target == 'Stages':
		if Gui.isoFileTree.exists( 'gr' ): # Check for the complimentary folder
			iidTuple = Gui.isoFileTree.get_children( 'gr' )
			if len( iidTuple ) > 0: iid = iidTuple[0]
		else: 
			iid = scanDiscForFile( 'grbb.dat' )
			if not iid: iid = scanDiscForFile( 'grcn.dat' )

	if iid:
		targetItemIndex = Gui.isoFileTree.index( iid ) + indexOffset # Offset applied so that the target doesn't actually end up exactly in the center

		# Target the parent folder if it's in one
		if Gui.isoFileTree.parent( iid ) == gameId: # Means the target file is in root, not in a folder
			iidToSelect = iid
		else: iidToSelect = Gui.isoFileTree.parent( iid )

		# Set the current selection and keyboard focus
		Gui.isoFileTree.selection_set( iidToSelect )
		Gui.isoFileTree.focus( iidToSelect )
		targetItemSiblings = Gui.isoFileTree.get_children( Gui.isoFileTree.parent( iid ) )

		# Scroll to the target section (folders will be opened as necessary for visibility)
		if targetItemIndex > len( targetItemSiblings ): Gui.isoFileTree.see( targetItemSiblings[-1] )
		else: Gui.isoFileTree.see( targetItemSiblings[targetItemIndex] )


def disallowLineBreaks( event ): return 'break'
	# print 'adding line break'
	# #if event.widget.winfo_class() == 'TEntry' or event.widget.winfo_class() == 'Entry': currentString = event.widget.get()
	# #else: currentString = 
	# event.widget.insert( 'insert', '\n' ) # For Text widgets


def setDiscDetailsHelpText( updateName='' ):
	Gui.discDetailsTab.helpTextLabel['justify'] = 'center' # The default. But changed for some cases

	if updateName == 'Game ID': helpText = ( "The game's primary identification code; this is what most applications and databases "
							"use to determine what game the disc is. It is composed of the 4 parts shown to the right of the value. "
							"You can change the Game ID for your own purposes, but note that many applications will no longer "
							"recognize it as the original game. [Contained in boot.bin at 0x0]" )

	elif updateName == 'Console ID': 
		Gui.discDetailsTab.helpTextLabel['justify'] = 'left'
		helpText = ( '\t\tG: GameCube (standard)\n\t\tD: used by The Legend of Zelda: Ocarina of Time (Master Quest); \n\t\t   (Might be '
		'an indicator for emulated/ported/promotional titles.)\n\t\tU: Used by GBA-Player Boot CD' )
	elif updateName == 'Game Code': helpText = ( 'An ID/serial specific to just the game itself.' )
	elif updateName == 'Region Code': 
		Gui.discDetailsTab.helpTextLabel['justify'] = 'left'
		helpText = ( 'A: All,\tE: USA,\tJ: Japan,\tK: Korea,\tR: Russia,\tW: Taiwan\n'
		'D: ?,\tF: France,\tH: ?,\tI: ?,\tP: Europe\n'
		'U: Used by EU TLoZ:OoT(MQ)\tX: France/Germany?,\tY: ?,\tZ: ?\n'
		'\tFirst line = NTSC,\tSecond and third lines = PAL' )
	elif updateName == 'Maker Code': 
		Gui.discDetailsTab.helpTextLabel['justify'] = 'left'
		helpText = ( 'i.e. The publisher...:\t\t01: Nintendo, 08: Capcom, 41: Ubisoft, 4F: Eidos, '
												'51: Acclaim, 52: Activision, 5D: Midway, 5G: Hudson, 64: Lucas Arts, '
												'69: Electronic Arts, 6S: TDK Mediactive, 8P: Sega, A4: Mirage Studios, AF: Namco, '
												'B2: Bandai, DA: Tomy, EM: Konami, WR: Warner Bros.' )

	elif updateName == 'Disc Revision': helpText = ( 'Sometimes games recieve some minor changes, such as bug fixes, throughout the time of their release. This number helps to keep track of those revisions.' )
	elif updateName == '20XX Version': helpText = ( 'This can also be determined in-game in the Debug Menu, or [beginning with v4.05] in the upper-right of the CSS.' )
	elif updateName == 'Total File Count': helpText = ( "The number of files in the disc's filesystem (excludes folders)." )
	elif updateName == 'Disc Size': helpText = ( 'Full file size of the GCM/ISO disc image. This differs from clicking on the root item in the Disc File Tree tab because the latter '
												'does not include inter-file padding.\nThe standard for GameCube discs is ~1.36 GB, or 1,459,978,240 bytes.' )

	elif updateName == 'Image Name': helpText = ( 'Disc/Image Name. This is what Nintendont uses to populate its game list.\n'
				'There is also a lot of free space here for a description or other notes. \n[Contained in boot.bin at 0x20.]' )
	elif updateName == 'Short Title': helpText = ( "The game's name. \n[Contained in opening.bnr at 0x1820.]" )
	elif updateName == 'Short Maker': helpText = ( 'The company/developer, game producer, and/or production date. \n[Contained in opening.bnr at 0x1840.]' )
	elif updateName == 'Long Title': helpText = ( "The game's full name. This is what Dolphin uses to display in its games list for the Title field. "
				"Remember to delete the cache file under '\\Dolphin Emulator\\Cache' to get this to update, or use the menu option in View -> Purge Game List Cache.\n[Contained in opening.bnr at 0x1860.]" )
	elif updateName == 'Long Maker': helpText = ( 'The company/developer, game producer, and/or production date. This is what Dolphin uses to display in its games list for the Maker field. '
				"Remember to delete the cache file under '\\Dolphin Emulator\\Cache' to get this to update, or use the menu option in View -> Purge Game List Cache.\n[Contained in opening.bnr at 0x18A0.]" )
	elif updateName == 'Comment': helpText = ( 'Known as "Description" in GCR, and simply "comment" in official Nintendo documentation. Originally, this was used to appear in the '
				"GameCube's BIOS (i.e. the IPL Main Menu; the menu you would see when booting the system while holding 'A'), as a short description before booting the game. \n[Contained in opening.bnr at 0x18E0.]" )
	else: helpText = "Hover over an item to view information on it.\nPress 'Enter' to submit changes in a text input field before saving."

	Gui.discDetailsTabHelpText.set( helpText )


																				#==============================#
																				# ~ ~ Main / Context Menus ~ ~ #
																				#==============================#
def createFileTreeContextMenu( event ):
	if discDetected( throwWarnings=False ): # No useful options if there is no disc to operate on
		contextMenu = isoMenuOptions( Gui.root, tearoff=False )
		contextMenu.repopulate()
		contextMenu.post( event.x_root, event.y_root )


def createTextureTreeContextMenu( event ):
	if globalDatFile: # No useful options if there is no file to operate on
		contextMenu = textureMenuOptions( Gui.root, tearoff=False )
		contextMenu.repopulate()
		contextMenu.post( event.x_root, event.y_root )


def createStructureTreeContextMenu( event ):
	if globalDatFile: # No useful options if there is no file to operate on
		contextMenu = structureMenuOptions( Gui.root, tearoff=False )
		contextMenu.repopulate()
		contextMenu.post( event.x_root, event.y_root )


class fileMenu( Tk.Menu, object ):

	def __init__( self, parent, tearoff=True, *args, **kwargs ):
		super( fileMenu, self ).__init__( parent, tearoff=tearoff, *args, **kwargs )
		self.open = False
		self.populated = False
		self.recentFilesMenu = Tk.Menu( self, tearoff=True ) # tearoff is the ability to turn the menu into a 'tools window'

		self.add_cascade( label="Open Recent", menu=self.recentFilesMenu )
		self.add_command( label='Open Last Used Directory', underline=5, command=self.openLastUsedDir ) 				# L
		self.add_command( label='Open Disc (ISO/GCM)', underline=11, command=lambda: promptToOpenFile( 'iso' ) ) 		# I
		self.add_command( label='Open Root (Disc Directory)', underline=6, command=promptToOpenRoot )					# O
		self.add_command( label='Open DAT (or USD, etc.)', underline=5, command=lambda: promptToOpenFile( 'dat' ) )		# D
		self.add_separator()
		self.add_command( label='View Unsaved Changes', underline=0, command=showUnsavedChanges )						# V
		self.add_command( label='Save  (CTRL-S)', underline=0, command=saveChanges )									# S
		self.add_command( label='Save Disc As...', underline=3, command=saveDiscAs )									# E
		self.add_command( label='Save DAT As...', underline=9, command=saveDatAs )										# A
		self.add_command( label='Save Banner As...', underline=5, command=saveBannerAs )								# B
		self.add_command( label='Run in Emulator  (CTRL-R)', underline=0, command=runInEmulator )						# R
		self.add_command( label='Close', underline=0, command=onProgramClose )											# C

	@staticmethod
	def loadRecentFile( filepath ):
		""" This is the callback for clicking on a recent file to load from the recent files menu. 
			Verifies files exist before loading. If they don't, ask to remove them from the list. """

		if os.path.exists( filepath ): 
			fileHandler( [filepath], updateDefaultDirectory=False ) # fileHandler expects a list.

		else: # If the file wasn't found above, prompt if they'd like to remove it from the remembered files list.
			if tkMessageBox.askyesno( 'Remove Broken Path?', 'The following file could not be '
										'found:\n"' + filepath + '" .\n\nWould you like to remove it from the list of recent files?' ):
				# Update the list of recent ISOs in the settings object and settings file.
				settings.remove_option( 'Recent Files', filepath.replace(':', '|') )
				with open( settingsFile, 'w') as theSettingsFile: settings.write( theSettingsFile )

	def repopulate( self ):

		""" This will refresh the 'Open Recent' files menu. """

		# Depopulate the whole recent files menu
		self.recentFilesMenu.delete( 0, 'last' )

		# Collect the current [separate] lists of recent ISOs, and recent DAT (or other) files, and sort their contents in order of newest to oldest.
		ISOs, DATs = getRecentFilesLists() # Returns two lists of tuples (ISOs & DATs), where each tuple is a ( filepath, dateTimeObject )
		ISOs.sort( key=lambda recentInfo: recentInfo[1], reverse=True )
		DATs.sort( key=lambda recentInfo: recentInfo[1], reverse=True )

		# Add the recent ISOs to the dropdown menu.
		self.recentFilesMenu.add_command( label='   -   Disc Images and Root Folders:', background='#d0e0ff', activeforeground='#000000', activebackground='#d0e0ff' ) # default color: 'SystemMenu'
		for isosPath in ISOs:
			filepath = isosPath[0].replace( '|', ':' )
			parentDirPlusFilename = '\\' + os.path.split( os.path.dirname( filepath ) )[-1] + '\\' + os.path.basename( filepath )
			self.recentFilesMenu.add_command( label=parentDirPlusFilename, command=lambda pathToLoad=filepath: self.loadRecentFile(pathToLoad) )

		self.recentFilesMenu.add_separator()

		# Add the recent DATs to the dropdown menu.
		self.recentFilesMenu.add_command( label='   -   DATs and Other Texture Data Files:', background='#d0e0ff', activeforeground='#000000', activebackground='#d0e0ff' )
		for datsPath in DATs:
			filepath = datsPath[0].replace( '|', ':' )
			parentDirPlusFilename = '\\' + os.path.split( os.path.dirname( filepath ) )[-1] + '\\' + os.path.basename( filepath )
			self.recentFilesMenu.add_command( label=parentDirPlusFilename, command=lambda pathToLoad=filepath: self.loadRecentFile(pathToLoad) )

	def openLastUsedDir( self ):
		openFolder(settings.get( 'General Settings', 'defaultSearchDirectory' ))


class settingsMenu( Tk.Menu, object ):

	""" Once the checkbuttons have been created, they will stay updated in real time, since they're set using BoolVars. """

	def __init__( self, parent, tearoff=True, *args, **kwargs ): # Create the menu and its contents
		super( settingsMenu, self ).__init__( parent, tearoff=tearoff, *args, **kwargs )
		self.open = False

		self.add_command( label='Adjust Texture Filters', underline=15, command=setImageFilters )								# F
		
		# Add disc related options
		self.add_separator()		
		# self.add_command(label='Set General Preferences', command=setPreferences)
		self.add_checkbutton( label='Use Disc Convenience Folders', underline=9, 												# C
											variable=generalBoolSettings['useDiscConvenienceFolders'], command=saveSettingsToFile )
		self.add_checkbutton( label='Avoid Rebuilding Disc', underline=0, 														# A
											variable=generalBoolSettings['avoidRebuildingIso'], command=saveSettingsToFile )
		self.add_checkbutton( label='Back-up Disc When Rebuilding', underline=0, 												# B
											variable=generalBoolSettings['backupOnRebuild'], command=saveSettingsToFile )
		self.add_checkbutton( label='Auto-Generate CSP Trim Colors', underline=5, 												# G
											variable=generalBoolSettings['autoGenerateCSPTrimColors'], command=saveSettingsToFile )
		
		# Add image-editing related options
		self.add_separator()
		# self.add_checkbutton( label='Dump Viewed PNGs', underline=0, 
		#									variable=generalBoolSettings['dumpPNGs'], command=saveSettingsToFile )							# D
		# self.add_checkbutton( label='Delete Image Dumps on Exit', underline=1, 
		#									variable=generalBoolSettings['deleteImageDumpsOnExit'], command=saveSettingsToFile )			# E
		self.add_checkbutton( label='Auto-Update Headers', underline=5, 
											variable=generalBoolSettings['autoUpdateHeaders'], command=saveSettingsToFile )					# U
		self.add_checkbutton( label='Regenerate Invalid Palettes', underline=0, 
											variable=generalBoolSettings['regenInvalidPalettes'], command=saveSettingsToFile )				# R
		self.add_checkbutton( label='Cascade Mipmap Changes', underline=8, 
											variable=generalBoolSettings['cascadeMipmapChanges'], command=saveSettingsToFile )				# M
		self.add_checkbutton( label="Export Textures using Dolphin's Naming Convention", underline=32, 
											variable=generalBoolSettings['useDolphinNaming'], command=saveSettingsToFile )					# N

	def repopulate( self ):
		# Check the settings file, in case anything has been changed manually/externally.
		# Any changes from within the program will have updated these here as well.
		loadSettings()


class isoMenuOptions( Tk.Menu, object ):

	def __init__( self, parent, tearoff=True, *args, **kwargs ):
		super( isoMenuOptions, self ).__init__( parent, tearoff=tearoff, *args, **kwargs )
		self.open = False

	def repopulate( self ):

		""" This method will be called every time the submenu is displayed. """

		# Clear all current population
		self.delete( 0, 'last' )

		# Determine the kind of file(s)/folder(s) we're working with, to determine menu options
		self.iidSelectionsTuple = Gui.isoFileTree.selection()
		self.selectionCount = len( self.iidSelectionsTuple )
		if self.selectionCount == 1:
			self.entity = Gui.isoFileTree.item( self.iidSelectionsTuple[0], 'values' )[1]
			self.filename = os.path.basename( self.iidSelectionsTuple[0] ) # All iids are lowercase
		else:
			self.entity = ''
			self.filename = ''
		lastSeperatorAdded = False

		# Check if this is a version of 20XX, and if so, get its main build number
		self.orig20xxVersion = globalDiscDetails['is20XX'] # This is an empty string if the version is not detected or it's not 20XX

		# Add main import/export options																				# Keyboard shortcuts:
		if self.iidSelectionsTuple:
			self.add_command( label='Export File(s)', underline=0, command=exportIsoFiles )												# E
			self.add_command( label='Export Textures From Selected', underline=1, command=exportSelectedFileTextures )					# X
			self.add_command( label='Import File', underline=0, command=importSingleIsoFile )											# I
		self.add_command( label='Import Multiple Files', underline=7, command=importMultipleIsoFiles )									# M
		self.add_separator()

		# Add supplemental disc functions
		self.add_command( label='Add File(s) to Disc', underline=4, command=addFilesToIso )												# F
		self.add_command( label='Add Directory of File(s) to Disc', underline=4, command=addDirectoryOfFilesToIso )						# D
		self.add_command( label='Create Directory', underline=0, command=createDirectoryInIso )											# C
		if self.iidSelectionsTuple:
			if self.selectionCount == 1:
				if self.entity == 'file':
					self.add_command( label='Rename Selected File', underline=2, command=renameItem )									# N
				else:
					self.add_command( label='Rename Selected Folder', underline=2, command=renameItem )									# N
			if globalDiscDetails['is20XX'] and self.entity == 'file' and self.filename.startswith( 'gr' ): # A single stage file is chosen
				# Get the full case-sensitive file name
				iidValues = Gui.isoFileTree.item( self.iidSelectionsTuple[0], 'values' )
				fullFileName = iidValues[4].split( '/' )[-1] # 5th item in iidValues is isoPath
				if get20xxRandomNeutralNameOffset( fullFileName )[0] != -1:
					self.add_command( label='Rename Random Neutral Nickname', underline=16, command=self.renameRandomNeutralStage )		# U
			self.add_command( label='Remove Selected Item(s)', underline=0, command=removeItemsFromIso )								# R
			self.add_command( label='Move Selected to Directory', underline=1, command=moveSelectedToDirectory )						# O

		# Add file operations
		if self.selectionCount == 1 and self.entity == 'file':
			self.add_separator()
			self.add_command( label='View Hex', underline=5, command=viewFileHexFromFileTree )											# H
			self.add_command( label='Copy Offset to Clipboard', underline=2, command=self.copyFileOffsetToClipboard )					# P
			self.add_command( label='Browse Textures', underline=0, command=browseTexturesFromDisc )									# B
			self.add_command( label='Analyze Structure', underline=0, command=analyzeFileFromDisc )										# A
		elif self.selectionCount > 1:
			# Check if all of the items are files
			for iid in self.iidSelectionsTuple:
				if Gui.isoFileTree.item( self.iidSelectionsTuple[0], 'values' )[1] != 'file': break
			else: # The loop above didn't break; only files here
				self.add_separator()
				self.add_command( label='Copy Offsets to Clipboard', underline=2, command=self.copyFileOffsetToClipboard )				# P

		# Add an option for CSP Trim Colors, if it's appropriate
		if self.iidSelectionsTuple and self.orig20xxVersion:
			if 'BETA' in self.orig20xxVersion:
				majorBuildNumber = int( self.orig20xxVersion[-1] )
			else: majorBuildNumber = int( self.orig20xxVersion[0] )

			# Check if any of the selected files are an appropriate character alt costume file
			for iid in self.iidSelectionsTuple:
				filename = os.path.basename( iid )
				thisEntity = Gui.isoFileTree.item( iid, 'values' )[1] # Will be a string of 'file' or 'folder'

				if thisEntity == 'file' and candidateForTrimColorUpdate( filename, self.orig20xxVersion, majorBuildNumber ):
					if not lastSeperatorAdded:
						self.add_separator()
						lastSeperatorAdded = True
					self.add_command( label='Generate CSP Trim Colors', underline=0, command=self.prepareForTrimColorGeneration )		# G
					break

		if self.entity == 'file' and self.filename.startswith( 'pl' ):
			if not lastSeperatorAdded:
				self.add_separator()
				lastSeperatorAdded = True

			self.add_command( label='Set as CCC Source File', underline=11, command=lambda: self.cccSelectFromDisc( 'source' ) )		# S
			self.add_command( label='Set as CCC Destination File', underline=11, command=lambda: self.cccSelectFromDisc( 'dest' ) )		# D

	def prepareForTrimColorGeneration( self ):

		""" One of the primary methods for generating CSP Trim Colors.

			If only one file is being operated on, the user will be given a prompt to make the final color selection.
			If multiple files are selected, the colors will be generated and selected autonomously, with no user prompts. """

		# Make sure that the disc file can still be located
		if not discDetected(): return

		if self.selectionCount == 1:
			generateTrimColors( self.iidSelectionsTuple[0] )

		else: # Filter the selected files and operate on all alt costume files only, in autonomous mode
			for iid in self.iidSelectionsTuple:
				filename = os.path.basename( iid )
				thisEntity = Gui.isoFileTree.item( iid, 'values' )[1] # Will be a string of 'file' or 'folder'

				if 'BETA' in self.orig20xxVersion: origMainBuildNumber = int( self.orig20xxVersion[-1] )
				else: origMainBuildNumber = int( self.orig20xxVersion[0] )

				if thisEntity == 'file' and candidateForTrimColorUpdate( filename, self.orig20xxVersion, origMainBuildNumber ):
					generateTrimColors( iid, True ) # autonomousMode=True means it will not prompt the user to confirm its main color choices

	def cccSelectFromDisc( self, role ): # Select a file in a disc as input to the Character Color Converter
		# Double-check that the disc file can still be located
		if not discDetected(): return

		# Disc verified; proceed
		datHex = getFileDataFromDiscTree( iid=self.iidSelectionsTuple[0] )

		if datHex:
			prepareColorConversion( self.iidSelectionsTuple[0], datHex, role )

			# Switch to the CCC tab if both source and destination files have been provided.
			if CCC['dataStorage']['sourceFile'] != '' and CCC['dataStorage']['destFile'] != '': Gui.mainTabFrame.select( Gui.cccTab )

	def copyFileOffsetToClipboard( self ):
		Gui.isoFileTree.selection_set( self.iidSelectionsTuple ) 	# Highlights the item(s)
		Gui.isoFileTree.focus( self.iidSelectionsTuple[0] ) 		# Sets keyboard focus to the first item

		# Get the hashes of all of the items selected
		offsets = []
		for iid in self.iidSelectionsTuple:
			isoOffset = Gui.isoFileTree.item( iid, 'values' )[2]
			offsets.append( isoOffset )

		copyToClipboard( ', '.join(offsets) )

	def renameRandomNeutralStage( self ):
		# Get the full case-sensitive file name
		iidValues = Gui.isoFileTree.item( self.iidSelectionsTuple[0], 'values' )
		fullFileName = iidValues[4].split( '/' )[-1] # 5th item in iidValues is isoPath

		# Get the current name
		cssData0Iid = scanDiscForFile( 'MnSlChr.0' )
		cssData1Iid = scanDiscForFile( 'MnSlChr.1' )
		cssData0 = getFileDataFromDiscTreeAsBytes( iid=cssData0Iid )
		nameOffset = get20xxRandomNeutralNameOffset( fullFileName )[0]
		originalName = cssData0[nameOffset:nameOffset+0x20].split('\x00')[0].decode( 'ascii' )

		# Prompt the user to enter a new name, and validate it
		nameChecksOut = False
		while not nameChecksOut:
			popupWindow = PopupEntryWindow( Gui.root, message='Enter a new stage nickname:', defaultText=originalName, width=40 )
			newName = popupWindow.entryText.replace( '"', '' ).strip()

			if newName == '': break # User canceled the above window prompt; exit the loop

			# Validate the name length
			if len( newName ) > 31:
				msg( 'Please specify a name less than 31 characters in length.' )
				continue
			
			# Exclude some special characters
			for char in ( '\n', '\t' ):
				if char in newName:
					msg( 'Line breaks or tab characters may not be included in the name.' )
					break
			else: # The above loop didn't break (meaning an invalid character wasn't found)
				# Convert the name to bytes and validate the length
				try:
					nameBytes = bytearray()
					nameBytes.extend( newName )
					nameBytesLength = len( nameBytes )

					if nameBytesLength <= 0x1F:
						# Add padding to make sure any old text is overwritten. Must end with at least one null byte
						nameBytes.extend( (0x20 - nameBytesLength) * b'\00' )
						nameChecksOut = True
					else:
						msg( 'Unable to encode the new name into 31 bytes. Try shortening the name.' )
				except:
					msg( 'Unable to encode the new name into 31 bytes. There may be an invalid character.' )

		if not newName: # User canceled above name input window
			return

		# Write the new name's bytes into both CSS files at the appropriate location
		cssData1 = getFileDataFromDiscTreeAsBytes( iid=cssData1Iid )
		cssData0[nameOffset:nameOffset+nameBytesLength] = nameBytes
		cssData1[nameOffset:nameOffset+nameBytesLength] = nameBytes

		# Save the new CSS file data to disc
		_, _, isoOffset, fileSize, isoPath, _, _ = Gui.isoFileTree.item( cssData0Iid, 'values' )
		Gui.isoFileTree.item( cssData0Iid, values=('Stage name updated', 'file', isoOffset, fileSize, isoPath, 'ram', hexlify(cssData0)), tags='changed' )
		_, _, isoOffset, fileSize, isoPath, _, _ = Gui.isoFileTree.item( cssData1Iid, 'values' )
		Gui.isoFileTree.item( cssData1Iid, values=('Stage name updated', 'file', isoOffset, fileSize, isoPath, 'ram', hexlify(cssData1)), tags='changed' )

		# Update the name shown for the stage in question
		Gui.isoFileTree.item( self.iidSelectionsTuple[0], values=('    '+newName,)+iidValues[1:] ) # Extra spaces added to indent the name from the stage folder name

		# Remember these changes, and update the program status
		unsavedDiscChanges.append( 'Random Neutral stage name updated.' )
		updateProgramStatus( 'Stage Name Updated' )


class textureMenuOptions( Tk.Menu, object ):

	def __init__( self, parent, tearoff=True, *args, **kwargs ):
		super( textureMenuOptions, self ).__init__( parent, tearoff=tearoff, *args, **kwargs )
		self.open = False

	def repopulate( self ):

		""" This method will be called every time the submenu is displayed. """

		# Clear all current population
		self.delete( 0, 'last' )
		self.lastItem = ''

		# Check if anything is currently selected
		self.iids = Gui.datTextureTree.selection() # Returns a tuple of iids, or an empty string if nothing is selected.
		self.selectionCount = len( self.iids )

		if self.iids:																								# Keyboard shortcuts:
			self.lastItem = self.iids[-1] # Selects the lowest position item selected in the treeview.
			self.add_command( label='Export Selected Texture(s)', underline=0, command=exportTextures )								# E
			self.add_command( label='Export All', underline=7, command=self.exportAllTextures )										# A
			self.add_command( label='Import Texture(s)', underline=0, command=importImageFiles )									# I
			self.add_separator()
			self.add_command( label='Blank Texture (Zero-out)', underline=0, command=blankTextures )								# B
			#self.add_command(label='Disable (Prevents Rendering)', underline=0, command=disableTextures )
			if self.selectionCount > 1:
				self.add_command( label='Copy Offsets to Clipboard', underline=0, command=self.textureOffsetToClipboard )			# C
				self.add_command( label='Copy Dolphin Hashes to Clipboard', underline=13, command=self.dolphinHashToClipboard )		# H
			else:
				self.add_command( label='Show in Structural Analysis', underline=0, command=self.showTextureInStructAnalysisTab )	# S
				self.add_command( label='Copy Offset to Clipboard', underline=0, command=self.textureOffsetToClipboard )			# C
				self.add_command( label='Copy Dolphin Hash to Clipboard', underline=13, command=self.dolphinHashToClipboard )		# H
		else:
			self.add_command( label='Export All', underline=7, command=self.exportAllTextures )										# A

	def exportAllTextures( self ):
		if len( Gui.datTextureTree.get_children() ) == 0: 
			msg( 'You need to first open a file that you would like to export textures from.'
				 '\n\n(If you have loaded a file, either there were no textures found, or '
				 'you have texture filters blocking your results.)' )
		else: 
			exportTextures( exportAll=True )

	def showTextureInStructAnalysisTab( self ):
		# Set the selected item in DAT Texture Tree, so that it's clear which image is being operated on
		Gui.datTextureTree.selection_set( self.lastItem )
		Gui.datTextureTree.focus( self.lastItem )

		# Make sure the current iid is the start of a structure (may not be in the case of particle effects)
		structOffset = int( self.lastItem )
		if not self.lastItem in globalDatFile.structureOffsets:
			structOffset = globalDatFile.getPointerOwner( structOffset, True )

		# Add the texture's data block instances to the tree and show them
		showStructInStructuralAnalysis( structOffset )
		
		# Switch to the SA tab
		Gui.mainTabFrame.select( Gui.savTab )

	def textureOffsetToClipboard( self ):
		Gui.datTextureTree.selection_set( self.iids ) 	# Highlights the item(s)
		Gui.datTextureTree.focus( self.iids[0] ) 		# Sets keyboard focus to the first item

		# Get the offsets of all of the items selected
		offsets = []
		for iid in self.iids:
			imageDataDetails = Gui.datTextureTree.item( iid, 'values' )[0]
			offsets.append( imageDataDetails.split()[0] )

		copyToClipboard( ', '.join(offsets) )

	def dolphinHashToClipboard( self ):
		Gui.datTextureTree.selection_set( self.iids ) 	# Highlights the item(s)
		Gui.datTextureTree.focus( self.iids[0] ) 		# Sets keyboard focus to the first item

		# Get the hashes of all of the items selected
		hashedFileNames = []
		for iid in self.iids:
			hashedFileNames.append( constructTextureFilename( globalDatFile, iid, forceDolphinHash=True ) )

		copyToClipboard( ', '.join(hashedFileNames) )


class structureMenuOptions( Tk.Menu, object ):

	def __init__( self, parent, tearoff=True, *args, **kwargs ):
		super( structureMenuOptions, self ).__init__( parent, tearoff=tearoff, *args, **kwargs )
		self.open = False

	def repopulate( self ):

		""" This method will be called every time the submenu is displayed. """

		# Clear all current population
		self.delete( 0, 'last' )

		# Determine the kind of structure(s) we're working with, to determine menu options
		self.iids = Gui.fileStructureTree.selection()
		self.selectionCount = len( self.iids )

		if self.selectionCount == 1:																			# Keyboard shortcuts:
			itemName = Gui.fileStructureTree.item( self.iids[0], 'text' )
			
			if itemName == 'coll_data':
				#collDataOffset = int( self.iids[0].split('/')[-1] )
				self.add_command( label='Render', underline=0, command=self.renderCollisions )
			self.add_command( label='Copy Offset to Clipboard', underline=0, command=self.offsetToClipboard )				# C

			# Check the kind of structure clicked on
			structOffset = int( self.iids[0].split('/')[-1] )
			structure = globalDatFile.getStruct( structOffset )

			if structure.__class__ in ( hsdStructures.ImageObjDesc, hsdStructures.TextureObjDesc, hsdStructures.ImageDataBlock ):
				self.add_command( label='Show in DAT Texture Tree', underline=0, command=self.showInDatTextureTree )		# S

			# Check if the currently selected item is 'marked'
			currentTags = Gui.fileStructureTree.item( self.iids[0], 'tags' )
			if 'marked' in currentTags:
				self.add_command( label='Unmark Selected Struct', underline=0, command=self.unmarkSelectedStructs )			# U
			else:
				self.add_command( label='Mark Selected Struct', underline=0, command=self.markSelectedStructs )				# M
			self.add_separator()

		elif self.selectionCount > 1:
			self.add_command( label='Copy Offsets to Clipboard', underline=0, command=self.offsetToClipboard )				# C

			# Check if there are more marked or unmarked items selected
			markedItems = 0
			unmarkedItems = 0
			for iid in self.iids:
				if 'marked' in Gui.fileStructureTree.item( iid, 'tags' ): markedItems += 1
				else: unmarkedItems += 1
			if markedItems >= unmarkedItems:
				self.add_command( label='Unmark Selected Structs', underline=0, command=self.unmarkSelectedStructs )		# U
			else:
				self.add_command( label='Mark Selected Structs', underline=0, command=self.markSelectedStructs )			# M
			self.add_separator()

		self.add_command( label='Collapse Data Space', underline=1, command=self.collapseDataSpace )						# O
		self.add_command( label='Extend Data Space', underline=0, command=self.extendDataSpace )							# E

	def offsetToClipboard( self ):
		Gui.fileStructureTree.selection_set( self.iids ) # Highlights the item(s)
		Gui.fileStructureTree.focus( self.iids[0] ) # Sets keyboard focus to the first item

		# Get the offsets of all of the items selected
		offsets = []
		for iid in self.iids:
			offset = int( iid.split('/')[-1] )
			offsets.append( uHex(0x20+offset) )

		copyToClipboard( ', '.join(offsets) )

	def showInDatTextureTree( self ):
		# Check the kind of structure clicked on
		structOffset = int( self.iids[0].split('/')[-1] )
		structure = globalDatFile.getStruct( structOffset )

		# Get the image data offset (whether from the TObj or another lower structure)
		if structure.__class__ == hsdStructures.TextureObjDesc:
			imageHeaderOffset = structure.getValues( 'Image_Header_Pointer' )
			imageHeader = globalDatFile.getStruct( imageHeaderOffset )
			imageDataOffset = imageHeader.getValues()[0]

		elif structure.__class__ == hsdStructures.ImageObjDesc:
			imageDataOffset = structure.getValues()[0]

		else: # Should be an ImageDataBlock
			imageDataOffset = structure.offset

		targetIid = str( imageDataOffset )

		# Make sure the DAT Texture Tree tab has been populated
		if not Gui.datTextureTree.get_children() or not Gui.datTextureTree.exists( targetIid ):
			clearDatTab()
			scanDat( priorityTargets=(imageDataOffset,) )

		# Look for this texture in the DAT Texture Tree tab
		if Gui.datTextureTree.exists( targetIid ):
			# Switch tabs, and select the target texture
			Gui.mainTabFrame.select( Gui.datTab )
			Gui.datTextureTree.selection_set( targetIid )
			Gui.datTextureTree.see( targetIid )

		else: # ¿Qué?
			print 'Unable to find {} (0x{:X}) in the DAT Texture Tree tab.'.format( targetIid, 0x20+int(targetIid) )
			msg( 'The image for ' + structure.name + ' could not\nbe found in the DAT Texture Tree tab!', '¿Qué?' )

	def markSelectedStructs( self ):
		# Add tags to the selected items
		for iid in self.iids:
			currentTags = Gui.fileStructureTree.item( iid, 'tags' )

			if not currentTags:
				Gui.fileStructureTree.item( iid, tags='marked' )

			elif 'marked' not in currentTags:
				currentTags.append( 'marked' )
				Gui.fileStructureTree.item( iid, tags=currentTags )

	def unmarkSelectedStructs( self ):
		# Add tags to the selected items
		for iid in self.iids:
			try:
				currentTags = list( Gui.fileStructureTree.item( iid, 'tags' ) )
				currentTags.remove( 'marked' )
				Gui.fileStructureTree.item( iid, tags=currentTags )
			except Exception as e:
				print "Unable to remove 'marked' selection status from", iid
				print e

	def collapseDataSpace( self ):
		modifierWindow = DataSpaceModifierWindow( Gui.root, 'collapse' )

		if modifierWindow.offset and modifierWindow.amount:
			# Perform some basic validation and typcasting
			try:
				offset = int( modifierWindow.offset, 16 ) - 0x20
				amount = int( modifierWindow.amount, 16 )
			except Exception as err:
				print err
				msg( 'Invalid input values.' )
				return
			globalDatFile.collapseDataSpace( offset, amount )

		# Need to reinitialize file structures
		clearStructuralAnalysisTab()
		analyzeDatStructure()

		updateProgramStatus( 'File Data Collapsed' )

	def extendDataSpace( self ):
		modifierWindow = DataSpaceModifierWindow( Gui.root, 'extend' )

		if modifierWindow.offset and modifierWindow.amount:
			# Perform some basic validation and typcasting
			try:
				offset = int( modifierWindow.offset, 16 ) - 0x20
				amount = int( modifierWindow.amount, 16 )
			except Exception as err:
				print err
				msg( 'Invalid input values.' )
				return
			globalDatFile.extendDataSpace( offset, amount )

		# Need to reinitialize file structures
		clearStructuralAnalysisTab()
		analyzeDatStructure()

		updateProgramStatus( 'File Data Extended' )

	def renderCollisions( self ):
		CollisionsEditor( int(self.iids[0].split('/')[-1]) )


class CollisionsEditor( basicWindow ):

	def __init__( self, collStructOffset ):
		basicWindow.__init__( self, Gui.root, 'Collision Data for ' + globalDatFile.fileName, offsets=(0, 30), topMost=False, resizable=True, minsize=(600, 350) )
		self.highlightedLabels = []
		self.highlightedId = None

		# Get the structures defining the stage's spot, links, and areas (they should already be initialized)
		self.collStruct = globalDatFile.structs[ collStructOffset ]
		spotTableOffset, linkTableOffset, areaTableOffset = self.collStruct.getChildren()
		self.spotTable = globalDatFile.structs[ spotTableOffset ]
		self.linkTable = globalDatFile.structs[ linkTableOffset ]
		self.areaTable = globalDatFile.structs[ areaTableOffset ]

		self.vertices = self.spotTable.getVertices()
		self.collisionLinks = self.linkTable.getFaces()
		self.areas = self.areaTable.getAreas()
		
		self.showAreas = Tk.BooleanVar( value=False )
		self.showBasicLinks = Tk.BooleanVar( value=True )
		# self.showPreLinks = Tk.BooleanVar( value=False )
		# self.showPostLinks = Tk.BooleanVar( value=False )

		# Get reference counts for spots, and set render status
		spotRefCounts = {}
		for link in self.collisionLinks:
			for index in link.allSpotIndices:
				if index == -1: continue

				elif index in spotRefCounts:
					spotRefCounts[index] += 1
				else:
					spotRefCounts[index] = 1

			# if link.type == 'pre': link.render = self.showPreLinks.get()
			# elif link.type == 'post': link.render = self.showPostLinks.get()
			# else: 
			link.render = self.showBasicLinks.get() # Basic links

		# Convert the 2D collision lines to 3D collision surfaces
		self.extrudeCollisionLinks()

		# Create vertices from the areas, and add them to the vertices list (replacing orig values with indices in collision object)
		self.areaVertices = []
		areaVerticesIndex = len( self.vertices ) + len( self.collVertices )
		for i, area in enumerate( self.areas, start=1 ):
			area.number = i
			area.origPoints = botLeftX, botLeftY, topRightX, topRightY = area.points
			self.areaVertices.append( RenderEngine.Vertex(( botLeftX, botLeftY, 0 )) )
			self.areaVertices.append( RenderEngine.Vertex(( botLeftX, topRightY, 0 )) )
			self.areaVertices.append( RenderEngine.Vertex(( topRightX, topRightY, 0 )) )
			self.areaVertices.append( RenderEngine.Vertex(( topRightX, botLeftY, 0 )) )
			area.points = ( areaVerticesIndex, areaVerticesIndex+1, areaVerticesIndex+2, areaVerticesIndex+3 )
			area.render = self.showAreas.get()
			areaVerticesIndex += 4
		
		#vertices = [[-1,-1,-1],[-1,-1,1],[-1,1,1],[-1,1,-1],[1,-1,-1],[1,-1,1],[1,1,1],[1,1,-1]] # cube points
		#collisionLinks = [[0,1,2],[0,2,3],[2,3,7],[2,7,6],[1,2,5],[2,5,6],[0,1,4],[1,4,5],[4,5,6],[4,6,7],[3,7,4],[4,3,0]] # cube point indices
		#collisionLinks = [ (0,3), (3,7), (7,4), (4,0) ] # one cube face (lines)
		#vertices.extend( [[-1,-1,-1], [-1,1,-1], [1,1,-1], [1,-1,-1]] )
		# vertices.extend( [[-10,-10,-10], [-10,10,-10], [10,10,-10], [10,-10,-10]] )
		# collisionLinks.extend( [ (-4,-3), (-3,-2), (-2,-1), (-1,-4) ] )

		allVertices = self.vertices + self.collVertices + self.areaVertices

		self.renderPlane = RenderEngine.Engine3D( self.mainFrame, allVertices, self.collisionLinks + self.areas, width=800, height=600, background='black' )

		self.renderPlane.grid( column=0, row=0, sticky='nsew' )
		self.renderPlane.focus_set()

		# Bind event handlers
		self.renderPlane.tag_bind( 'CollissionSurface', '<Enter>', self.collSurfaceHovered )
		self.renderPlane.tag_bind( 'CollissionSurface', '<Leave>', self.linkTabLinkUnhovered )
		# self.renderPlane.tag_bind( 'ColCalcArea', '<Enter>', self.areaHovered )
		# self.renderPlane.tag_bind( 'ColCalcArea', '<Leave>', self.areaUnhovered )

		# Build out the panels on the right-hand side
		self.structuresPanel = ttk.Notebook( self.mainFrame )
		self.populateSpotsTab( spotRefCounts )
		self.linksTab = ttk.Frame( self.structuresPanel )
		self.structuresPanel.add( self.linksTab, text=' Links ' )
		self.linksInnerFrame = VerticalScrolledFrame( self.linksTab )
		self.populateLinksTab()
		self.populateAreasTab()
		self.populateRenderingTab()
		self.structuresPanel.grid( column=1, row=0, sticky='nsew' )

		# Enable resizing of the grid cells
		self.mainFrame.grid_columnconfigure( 0, weight=3 )
		self.mainFrame.grid_columnconfigure( 1, weight=1, minsize=250 )
		
		self.mainFrame.grid_rowconfigure( 0, weight=1 )

	def extrudeCollisionLinks( self ):

		""" Extrudes each collision link (which are initially 2D lines), turning them into 3D faces. """

		self.collVertices = []
		collFaceThickness = 7
		origVerticesLength = len( self.vertices )

		for link in self.collisionLinks:
			# Perform some validation
			link.validIndices = True
			if link.points[0] < 0 or link.points[0] >= origVerticesLength: link.validIndices = False
			if link.points[1] < 0 or link.points[1] >= origVerticesLength: link.validIndices = False
			for pointIndex in link.allSpotIndices[2:]:
				if pointIndex < -1 or pointIndex >= origVerticesLength:
					print 'link', link.index, 'refereneces a non-existant point (index', str(pointIndex) + ')'
					break
			link.origPoints = link.points
			if not link.validIndices: continue

			# Create two new vertices for spot 1
			originalVertex = self.vertices[ link.points[0] ]
			newCoords = ( originalVertex.x, originalVertex.y, collFaceThickness )
			if newCoords not in self.collVertices:
				self.collVertices.append( newCoords )
			pointIndex1 = origVerticesLength + self.collVertices.index( newCoords )
			newCoords = ( originalVertex.x, originalVertex.y, -collFaceThickness )
			if newCoords not in self.collVertices:
				self.collVertices.append( newCoords )
			pointIndex2 = origVerticesLength + self.collVertices.index( newCoords )

			# Create two new vertices for spot 2
			originalVertex = self.vertices[ link.points[1] ]
			newCoords = ( originalVertex.x, originalVertex.y, collFaceThickness )
			if newCoords not in self.collVertices:
				self.collVertices.append( newCoords )
			pointIndex3 = origVerticesLength + self.collVertices.index( newCoords )
			newCoords = ( originalVertex.x, originalVertex.y, -collFaceThickness )
			if newCoords not in self.collVertices:
				self.collVertices.append( newCoords )
			pointIndex4 = origVerticesLength + self.collVertices.index( newCoords )

			# Save the new link indices
			link.points = ( pointIndex1, pointIndex3, pointIndex4, pointIndex2 )

		# Create new vertices for the new points, and store them with the rest of the vertices list
		for i, coords in enumerate( self.collVertices ):
			self.collVertices[i] = RenderEngine.Vertex( coords )

	def populateSpotsTab( self, spotRefCounts ):
		self.spotsTab = ttk.Frame( self.structuresPanel )
		self.structuresPanel.add( self.spotsTab, text=' Spots ' )
		spotsInnerFrame = VerticalScrolledFrame( self.spotsTab )

		Tk.Label( spotsInnerFrame.interior, text='X/Y Coords:' ).grid( column=0, row=0, padx=50, sticky='w' )
		Tk.Label( spotsInnerFrame.interior, text='Reference Count:' ).grid( column=1, row=0, columnspan=2, sticky='e', padx=20 )
		spotOffset = 0x20 + self.spotTable.offset
		row = 1
		for vertex in self.vertices:
			spotLabel = Tk.Label( spotsInnerFrame.interior, text='{}:  ({}, {})'.format(row-1, vertex.x, vertex.y * -1) ) # Y values inverted
			spotLabel.grid( column=0, row=row, columnspan=2, padx=(15,0), sticky='w' )
			referenceCount = spotRefCounts.get( row-1, 0 )
			Tk.Label( spotsInnerFrame.interior, text=str( referenceCount ) ).grid( column=2, row=row, sticky='e', padx=(15,15) )
			ToolTip( spotLabel, 'File Offset: 0x{:X}'.format(spotOffset) )
			spotOffset += 8
			row += 1
		spotsInnerFrame.pack( fill='both', expand=True )

	def populateLinksTab( self ):
		origVerticesLength = len( self.vertices )

		Tk.Label( self.linksInnerFrame.interior, text='Spot 1 & 2 References:' ).grid( column=0, row=0, padx=50, sticky='w' )
		linkOffset = 0x20 + self.linkTable.offset
		row = 1
		for link in self.collisionLinks:
			#if not link.type == 'basic': continue # Skip pre/post/virtual links
			fontColor = 'black'
			if link.origPoints[0] < 0 or link.origPoints[0] >= origVerticesLength:
				pointText0 = 'Invalid'
				fontColor = 'red'
			else:
				pointText0 = link.origPoints[0]
			if link.origPoints[1] < 0 or link.origPoints[1] >= origVerticesLength:
				pointText1 = 'Invalid'
				fontColor = 'red'
			else:
				pointText1 = link.origPoints[1]

			# Add the label
			label = Tk.Label( self.linksInnerFrame.interior, text='{}, 0x{:X}:  ({}, {})'.format(row, linkOffset, pointText0, pointText1), fg=fontColor )
			label.grid( column=0, row=row, ipadx=15, padx=15 )
			label.link = link
			if fontColor != 'red':
				label.bind( '<Enter>', self.linkTabLinkHovered )
				label.bind( '<Leave>', self.linkTabLinkUnhovered )
			#ToolTip( label, 'File Offset: 0x{:X}'.format(linkOffset) )

			# Add delete button
			# deleteLabel = ttk.Button( self.linksInnerFrame.interior, text='Delete' )
			# deleteLabel.configure( command=lambda linkIndex=link.index: self.deleteLink(linkIndex) )
			# deleteLabel.grid( column=1, row=row, padx=15 )
			# deleteLabel.bind( '<Enter>', self.linkTabLinkHovered )
			# deleteLabel.bind( '<Leave>', self.linkTabLinkUnhovered )

			linkOffset += 0x10
			row += 1
		self.linksInnerFrame.pack( fill='both', expand=True )
		
	def populateAreasTab( self ):
		self.areasTab = ttk.Frame( self.structuresPanel )
		self.structuresPanel.add( self.areasTab, text=' Areas ' )
		areasInnerFrame = VerticalScrolledFrame( self.areasTab )

		areaOffset = 0x20 + self.areaTable.offset
		row = 1
		for area in self.areas:
			areaHeader = Tk.Label( areasInnerFrame.interior, text='\tArea {}:'.format(row/3+1) )
			areaHeader.grid( column=0, row=row, padx=15, sticky='w' )
			Tk.Label( areasInnerFrame.interior, text='Bottom-left coords:  ({}, {})'.format(area.origPoints[0], area.origPoints[1]) ).grid( column=0, row=row+1, padx=15, sticky='w' )
			Tk.Label( areasInnerFrame.interior, text='Top-Right coords:    ({}, {})'.format(area.origPoints[2], area.origPoints[3]) ).grid( column=0, row=row+2, padx=15, sticky='w' )
			ToolTip( areaHeader, 'File Offset: 0x{:X}'.format(areaOffset) )
			areaOffset += 0x28
			row += 3
		areasInnerFrame.pack( fill='both', expand=True )

	def populateRenderingTab( self ): # i.e. Settings
		self.renderingTab = ttk.Frame( self.structuresPanel )
		self.structuresPanel.add( self.renderingTab, text=' Rendering ' )

		ttk.Checkbutton( self.renderingTab, text='Show Areas', variable=self.showAreas, command=self.updateAreaVisibility ).pack( pady=(40, 10) )
		ttk.Checkbutton( self.renderingTab, text='Show Links', variable=self.showBasicLinks, command=self.toggleBasicLinkVisibility ).pack( pady=10 )
		# ttk.Checkbutton( self.renderingTab, text='Show Pre Links', variable=self.showPreLinks, command=self.togglePreLinkVisibility ).pack( pady=10 )
		# ttk.Checkbutton( self.renderingTab, text='Show Post Links', variable=self.showPostLinks, command=self.togglePostLinkVisibility ).pack( pady=10 )

	def linkTabLinkHovered( self, event ):

		""" Event handler for hovering over a link in the Links tab, which highlights the specific link in the canvas. """

		hoverColor = '#e0e0a0' # Light yellow

		if event.widget.winfo_class() == 'TButton':
			lastWidget = None
			for widget in self.linksInnerFrame.interior.winfo_children():
				if widget == event.widget:
					labelWidget = lastWidget
					break
				lastWidget = widget
		else:
			labelWidget = event.widget

		# Change the background color of the highlighted widget
		labelWidget['bg'] = hoverColor
		self.highlightedLabels.append( labelWidget )

		# Change the background color of the face in the canvas
		collisionLink = labelWidget.link
		self.renderPlane.itemconfigure( collisionLink.id, fill=hoverColor, outline=hoverColor )
		self.highlightedId = collisionLink.id

	def linkTabLinkUnhovered( self, event ):

		""" Event handler for unhovering over a collision link in the canvas, or a link in the Links tab, 
			which unhighlights the specific link in the canvas. """

		# Change the background color of the previously highlighted widget(s) back to normal
		while self.highlightedLabels:
			try: # These labels may no longer exist (if Delete button was used)
				self.highlightedLabels.pop()['bg'] = 'SystemButtonFace' # The default
			except: pass

		# # Change the background color of the face in the canvas
		if self.highlightedId:
			for link in self.collisionLinks:
				linkId = getattr( link, 'id', None )
				if not linkId: continue # Some links may not be rendered
				
				elif link.id == self.highlightedId:
					self.renderPlane.itemconfigure( self.highlightedId, fill=link.fill, outline=link.outline )
					self.highlightedId = None
					break

	def collSurfaceHovered( self, event ):
		""" Event handler for hovering over a link in the canvas, which highlights the specific link in the Links tab (if visible). """
		hoverColor = '#e0e0a0' # Light yellow
		currentTab = self.window.nametowidget( self.structuresPanel.select() )
		if currentTab not in ( self.spotsTab, self.linksTab ): return

		# Get the label widget and link object
		linkId = self.renderPlane.find_withtag( 'current' )[0]
		for widget in self.linksInnerFrame.interior.grid_slaves( column=0 ):
			# Get the link object; skipping those without it
			collisionLink = getattr( widget, 'link', None )
			if not collisionLink: continue
			elif collisionLink.id == linkId: break # Found it
		else: # Above loop didn't break; no matching collision link found
			return

		# Color the selected surface on the canvas
		linkId = self.renderPlane.find_withtag( 'current' )[0]
		self.renderPlane.itemconfig( linkId, fill=hoverColor, outline=hoverColor )
		self.highlightedId = linkId

		if currentTab == self.spotsTab:
			spotsInnerFrame = self.spotsTab.winfo_children()[0]
			spotLabels = spotsInnerFrame.interior.grid_slaves( column=0 )[:-1] # Excludes header label
			spotLabels.reverse()
			firstLabel = spotLabels[collisionLink.origPoints[0]]
			secondLabel = spotLabels[collisionLink.origPoints[1]]

			# Adjust the colors of the labels
			firstLabel['bg'] = hoverColor
			secondLabel['bg'] = hoverColor
			self.highlightedLabels.extend( [firstLabel, secondLabel] )

			# Scroll to the position of the first label
			canvasHeight = spotsInnerFrame.canvas.bbox( 'all' )[-1]
			scrollPosition = (firstLabel.winfo_y() - 40) / float( canvasHeight ) # Slight offset (-40), so the link is not at the absolute top
			spotsInnerFrame.canvas.yview_moveto( scrollPosition )

		else: # On the links tab
			# Change the background color of the highlighted widget
			widget['bg'] = hoverColor
			self.highlightedLabels.append( widget )

			# Scroll to the target link, so it's visible
			canvasHeight = self.linksInnerFrame.canvas.bbox( 'all' )[-1]
			scrollPosition = (widget.winfo_y() - 40) / float( canvasHeight ) # Slight offset (-40), so the link is not at the absolute top
			self.linksInnerFrame.canvas.yview_moveto( scrollPosition )

	def updateAreaVisibility( self ):
		""" Shows or hides collision areas in the canvas. """
		# Set render visibility
		newVisibility = self.showAreas.get()
		for area in self.areas:
			area.render = newVisibility
		
		# Re-draw the canvas display
		self.renderPlane.delete( 'all' )
		self.renderPlane.render()

	def toggleBasicLinkVisibility( self ):
		show = self.showBasicLinks.get()

		for link in self.collisionLinks:
			link.render = show

		# Re-draw the canvas display
		self.renderPlane.delete( 'all' )
		self.renderPlane.render()

	# def areaHovered( self, event ):
	# 	print 'area hovered'

	# def areaUnhovered( self, event ):
	# 	print 'area unhovered'

	# def deleteLink( self, linkIndex ):
	# 	print 'removing link', linkIndex

	# 	# Decrement the Link_Table_Entry_Count value in the coll_data structure
	# 	newCollLinksCount = self.collStruct.getValues()[3] - 1
	# 	globalDatFile.updateStructValue( self.collStruct, 3, newCollLinksCount )
	# 	print 'coll count changed to', newCollLinksCount
		
	# 	# deducedStructLength = globalDatFile.getStructLength( self.linkTable.offset )
	# 	# collLinksLength = ( newCollLinksCount * 0x10 )
	# 	# padding = deducedStructLength - ( newCollLinksCount * 0x10 )
	# 	# globalDatFile.collapseDataSpace( self.linkTable.offset + collLinksLength, padding )

	# 	# Remove the data for this link from the structure and file
	# 	# linkDataStart = linkIndex * 0x10
	# 	# self.linkTable.data = self.linkTable.data[:linkDataStart] + self.linkTable.data[linkDataStart+0x10:]
	# 	# self.linkTable.length = len( self.linkTable.data )
	# 	# self.linkTable.entryCount -= 1
	# 	self.linkTable.removeEntry( linkIndex )
	# 	print 'new struct data len:', hex( self.linkTable.length )

	# 	# Check how much space is available and needed for this new struct data, and whether the space should be shrunk
	# 	# deducedStructLength = globalDatFile.getStructLength( self.linkTable.offset )
	# 	# self.linkTable.padding = deducedStructLength - self.linkTable.length
	# 	# globalDatFile.collapseDataSpace( self.linkTable.offset + self.linkTable.length, self.linkTable.padding )
	# 	# globalDatFile.setData( self.linkTable.offset, self.linkTable.data )

	# 	# Remove this link from the collisions list and drawing canvas
	# 	#targetLink = self.collisionLinks.pop( linkIndex )
	# 	newCollLinks = []
	# 	for link in self.collisionLinks:
	# 		if link.index == linkIndex:
	# 			canvasId = getattr( link, 'id', None )
	# 			if canvasId: 
	# 				print 'deleting canvas id', canvasId
	# 				self.renderPlane.delete( canvasId )
	# 		else:
	# 			newCollLinks.append( link )
	# 	self.collisionLinks = newCollLinks
	# 	self.renderPlane.shapes = self.collisionLinks + self.areas

	# 	# Reload the links tab to remove the link from the GUI
	# 	self.linksInnerFrame.clear()
	# 	self.populateLinksTab()
		
	# 	# Need to reinitialize file structures; reload the SA tab
	# 	clearStructuralAnalysisTab()
	# 	analyzeDatStructure()

																				#=============#
																				# ~ ~ GUI ~ ~ #
																				#=============#
class MainGui( Tk.Frame, object ):

	def __init__( self ): # Build the interface

		self.root = Tk.Tk()
		self.root.withdraw() # Keeps the GUI minimized until it is fully generated
		self._imageBank = {} # Repository for all GUI related images

		self.root.tk.call( 'wm', 'iconphoto', self.root._w, self.imageBank('appIcon') )
		self.defaultWindowWidth = 860
		self.defaultWindowHeight = 640
		self.root.geometry( str(self.defaultWindowWidth) + 'x' + str(self.defaultWindowHeight) + '+100+50' )
		self.root.title( "DAT Texture Wizard - v" + programVersion )
		self.root.minsize( width=370, height=416 )
		self.dnd = TkDND( self.root ) # Set-up for drag-and-drop functionality
		self.root.protocol( 'WM_DELETE_WINDOW', onProgramClose ) # Overrides the standard window close button.

		# Used for other TopWindow creations.
		self.root.imageFiltersWindow = None
		self.root.helpWindow = None
		self.root.aboutWindow = None

		# Loads settings from persistent storage (settings.ini). Must be done before configuring the Settings menu
		loadSettings()

		# Set the default font size and color.
		globalFontSize = int( settings.get( 'General Settings', 'globalFontSize' ) )
		if generalBoolSettings['useAltFontColor'].get():
			# User wants to use their own color
			self.globalFontColor = settings.get( 'General Settings', 'altFontColor' )

			try: # Make sure it's a valid color
				self.root.winfo_rgb( self.globalFontColor ) # Returns an RGB tuple if successful
			except:
				msg( 'The alternate color, "' + self.globalFontColor + '", is not a valid color. The string should be written as #RRGGBB, '
					 'or a basic color such as, "blue", "teal", "orange", etc. The default font color will be used instead.' )
				self.globalFontColor = '#071240'

		else: self.globalFontColor = '#071240' # Default
		for font in tkFont.names():
			tkFont.nametofont( font ).configure( size=globalFontSize )
		self.defaultSystemBgColor = self.root.cget( 'background' )

		#self.root.option_add("*Font", "TkDefaultFont") # Changes all of the various used fonts to the default font.

		# Apply the font color to the default font style class.
		style = ttk.Style()
		style.configure( '.', font="TkDefaultFont", foreground=self.globalFontColor )
		style.configure( "Treeview.Heading", font="TkDefaultFont", foreground=self.globalFontColor )
		style.configure( 'TLabel', justify='center' )
		style.configure( 'Edited.TMenubutton', background='#faa' ) # For OptionMenu widgets (dunno why the name is so different :/)

																									# - Main Menu Bar & Context Menus.
		self.menubar = Tk.Menu( self.root )
																																	# Keyboard shortcut:
		self.menubar.add_cascade( label='File', menu=fileMenu( self.menubar ), underline=0 )							# File 					[F]
		self.menubar.add_cascade( label='Settings', menu=settingsMenu( self.menubar ), underline=0 )					# Settings 				[S]
		self.menubar.add_cascade( label='Disc Operations', menu=isoMenuOptions( self.menubar ), underline=0 )			# Disc Operations 		[D]
		self.menubar.add_cascade( label='Texture Operations', menu=textureMenuOptions( self.menubar ), underline=0 )	# Texture Operations 	[T]

		toolsDropdown = Tk.Menu( self.menubar, tearoff=False )																		# Tools 	[T]
		self.menubar.add_cascade( menu=toolsDropdown, label='Tools', underline=0 )
		toolsDropdown.add_command( label='Color Converter', underline=0, command=MeleeColorPicker )												# C
		toolsDropdown.add_command( label='Image Data Length Calculator', underline=6, command=lambda: ImageDataLengthCalculator(Gui.root) )		# D

		helpDropdown = Tk.Menu( self.menubar, tearoff=False )																		# Help 		[H]
		self.menubar.add_cascade( menu=helpDropdown, label='Help', underline=0 )
		helpDropdown.add_command( label='General Help', underline=0, command=showHelpWindow )													# H
		helpDropdown.add_command( label='View Program Usage', underline=5, command=showReadMeFile )												# R
		helpDropdown.add_command( label='Support DTW', underline=0, command=showSupportWindow )													# S
		helpDropdown.add_command( label='About DAT Texture Wizard', underline=0, command=showAboutWindow )										# A

		self.root.config( menu=self.menubar )
		self.menubar.bind( "<<MenuSelect>>", self.updateMainMenuOptions )

																									# - Main Tab Interface.

		self.mainTabFrame = ttk.Notebook( self.root )

																									# Tab 1 | Disc File Tree

		self.discTab = ttk.Frame( self.mainTabFrame )
		self.mainTabFrame.add( self.discTab, text=' Disc File Tree ' )
		self.dnd.bindtarget( self.discTab, lambda event: dndHandler( event, 'discTab' ), 'text/uri-list' )

		# Frame for the File Tree tab
		isoFrameRow1 = ttk.Frame( self.discTab, padding="11 0 0 11" ) # Padding order: Left, Top, Right, Bottom.
		isoFrameRow1.pack( fill='both', expand=1 )

		# Disc shortcut links
		fileTreeColumn = Tk.Frame( isoFrameRow1 )
		isoQuickLinks = Tk.Frame( fileTreeColumn )
		ttk.Label( isoQuickLinks, text='Disc Shortcuts:' ).pack( side='left', padx=4 )
		ttk.Label( isoQuickLinks, text='System', foreground='#00F', cursor='hand2' ).pack( side='left', padx=4 )
		ttk.Label( isoQuickLinks, text='|' ).pack( side='left', padx=4 )
		ttk.Label( isoQuickLinks, text='Characters', foreground='#00F', cursor='hand2' ).pack( side='left', padx=4 )
		ttk.Label( isoQuickLinks, text='|' ).pack( side='left', padx=4 )
		ttk.Label( isoQuickLinks, text='Menus (CSS/SSS)', foreground='#00F', cursor='hand2' ).pack( side='left', padx=4 )
		ttk.Label( isoQuickLinks, text='|' ).pack( side='left', padx=4 )
		ttk.Label( isoQuickLinks, text='Stages', foreground='#00F', cursor='hand2' ).pack( side='left', padx=4 )
		for label in isoQuickLinks.winfo_children():
			if label['text'] != '|': label.bind( '<1>', discFileTreeQuickLinks )
		isoQuickLinks.pack( pady=1 )

		# File Tree start
		isoFileTreeWrapper = Tk.Frame( fileTreeColumn ) # Contains just the ISO treeview and its scroller (since they need a different packing than the above links).
		self.isoFileScroller = Tk.Scrollbar( isoFileTreeWrapper )
		self.isoFileTree = ttk.Treeview( isoFileTreeWrapper, columns=('description'), yscrollcommand=self.isoFileScroller.set )
		self.isoFileTree.heading( '#0', anchor='center', text='File     (Sorted by FST)', command=lambda: treeview_sort_column(self.isoFileTree, 'file', False) ) # , command=function
		self.isoFileTree.column( '#0', anchor='center', minwidth=180, stretch=1, width=230 ) # "#0" is implicit in the columns definition above.
		self.isoFileTree.heading( 'description', anchor='center', text='Description' )
		self.isoFileTree.column( 'description', anchor='w', minwidth=180, stretch=1, width=312 )
		self.isoFileTree.tag_configure( 'changed', foreground='red' )
		self.isoFileTree.tag_configure( 'changesSaved', foreground='#292' ) # The 'save'-green color
		self.isoFileTree.pack( side='left', fill='both', expand=1 )
		self.isoFileScroller.config( command=self.isoFileTree.yview )
		self.isoFileScroller.pack( side='left', fill='y' )

		# Add treeview event handlers
		self.isoFileTree.bind( '<<TreeviewSelect>>', onFileTreeSelect )
		self.isoFileTree.bind( '<Double-1>', onFileTreeDoubleClick )
		self.isoFileTree.bind( "<3>", createFileTreeContextMenu ) # Right-click

		isoFileTreeWrapper.pack( fill='both', expand=1 )
		fileTreeColumn.pack( side='left', fill='both', expand=1 )

		# Add the background image to the file tree
		self.isoFileTreeBg = Tk.Label( self.isoFileTree, image=self.imageBank('dndTarget'), borderwidth=0, highlightthickness=0 )
		self.isoFileTreeBg.place( relx=0.5, rely=0.5, anchor='center' )

		# ISO File Tree end / ISO Information panel begin

		isoOpsPanel = ttk.Frame( isoFrameRow1, padding='0 9 0 0' ) # Padding order: Left, Top, Right, Bottom.

		self.isoOverviewFrame = Tk.Frame( isoOpsPanel )
		self.gameIdText = Tk.StringVar()
		ttk.Label( self.isoOverviewFrame, textvariable=self.gameIdText, font="-weight bold" ).grid( column=0, row=0, padx=2 )
		self.bannerCanvas = Tk.Canvas( self.isoOverviewFrame, width=96, height=32, borderwidth=0, highlightthickness=0 )
		self.bannerCanvas.grid( column=1, row=0, padx=2 ) #, borderwidth=0, highlightthickness=0
		self.bannerCanvas.pilImage = None
		self.bannerCanvas.bannerGCstorage = None
		self.bannerCanvas.canvasImageItem = None
		self.isoOverviewFrame.columnconfigure( 0, weight=1 )
		self.isoOverviewFrame.columnconfigure( 1, weight=1 )
		self.isoOverviewFrame.pack( fill='x', padx=6, pady=11 )

		self.isoPathShorthand = Tk.StringVar()
		self.isoPathShorthandLabel = ttk.Label( isoOpsPanel, textvariable=self.isoPathShorthand )
		self.isoPathShorthandLabel.pack()

		internalFileDetails = ttk.Labelframe( isoOpsPanel, text='  File Details  ', labelanchor='n' )
		self.isoOffsetText = Tk.StringVar()
		self.isoOffsetText.set( 'Disc Offset: ' )
		ttk.Label( internalFileDetails, textvariable=self.isoOffsetText, width=27, anchor='w' ).pack( padx=15, pady=4 )
		self.internalFileSizeText = Tk.StringVar()
		self.internalFileSizeText.set( 'File Size: ' ) # The line break preserves space for the next line, which is used with multiple file (or folder) selections.
		ttk.Label( internalFileDetails, textvariable=self.internalFileSizeText, width=27, anchor='w' ).pack( padx=15, pady=0 )
		self.internalFileSizeLabelSecondLine = Tk.StringVar()
		self.internalFileSizeLabelSecondLine.set( '' )
		ttk.Label( internalFileDetails, textvariable=self.internalFileSizeLabelSecondLine, width=27, anchor='w' ).pack( padx=15, pady=0 )
		internalFileDetails.pack( padx=15, pady=16, ipady=4 )

		self.isoOpsPanelButtons = Tk.Frame( isoOpsPanel )
		ttk.Button( self.isoOpsPanelButtons, text="Export", command=exportIsoFiles, state='disabled' ).grid( row=0, column=0, padx=7 )
		ttk.Button( self.isoOpsPanelButtons, text="Import", command=importSingleIsoFile, state='disabled' ).grid( row=0, column=1, padx=7 )
		ttk.Button( self.isoOpsPanelButtons, text="Browse Textures", command=browseTexturesFromDisc, state='disabled', width=18 ).grid( row=1, column=0, columnspan=2, pady=(7,0) )
		ttk.Button( self.isoOpsPanelButtons, text="Analyze Structure", command=analyzeFileFromDisc, state='disabled', width=18 ).grid( row=2, column=0, columnspan=2, pady=(7,0) )
		self.isoOpsPanelButtons.pack( pady=2 )

		# Add the Magikoopa image
		kamekFrame = Tk.Frame( isoOpsPanel )
		ttk.Label( kamekFrame, image=self.imageBank('magikoopa') ).place( relx=0.5, rely=0.5, anchor='center' )
		kamekFrame.pack( fill='both', expand=1 )

		isoOpsPanel.pack( side='left', fill='both', expand=1 )

																									# Tab 2 | Disc Details

		self.discDetailsTab = ttk.Frame( self.mainTabFrame )
		self.mainTabFrame.add( self.discDetailsTab, text=' Disc Details ' )
		self.dnd.bindtarget( self.discDetailsTab, lambda event: dndHandler( event, 'discTab' ), 'text/uri-list' ) # Drag-and-drop functionality treats this as the discTab

				# The start of row 1
		self.discDetailsTab.row1 = ttk.Frame( self.discDetailsTab, padding=12 )
		ttk.Label( self.discDetailsTab.row1, text=" ISO / GCM:" ).pack( side='left' )
		self.isoDestination = Tk.StringVar()
		isoDestEntry = ttk.Entry( self.discDetailsTab.row1, textvariable=self.isoDestination, takefocus=False )
		isoDestEntry.pack( side='left', fill='x', expand=1, padx=12 )
		isoDestEntry.bind( '<Return>', openIsoDestination )
		self.discDetailsTab.row1.pack( fill='x' )

				# The start of row 2
		self.discDetailsTab.row2 = ttk.Frame( self.discDetailsTab, padding=0 ) # Padding order: Left, Top, Right, Bottom.
		self.discDetailsTab.row2.padx = 5
		self.discDetailsTab.row2.gameIdLabel = ttk.Label( self.discDetailsTab.row2, text='Game ID:' )
		self.discDetailsTab.row2.gameIdLabel.grid( column=0, row=0, rowspan=4, padx=self.discDetailsTab.row2.padx )
		self.gameIdTextEntry = DisguisedEntry( self.discDetailsTab.row2, respectiveLabel=self.discDetailsTab.row2.gameIdLabel, 
												background=self.defaultSystemBgColor, textvariable=self.gameIdText, width=8 )
		self.gameIdTextEntry.grid( column=1, row=0, rowspan=4, padx=self.discDetailsTab.row2.padx )
		self.gameIdTextEntry.offset = 0
		self.gameIdTextEntry.maxByteLength = 6
		self.gameIdTextEntry.updateName = 'Game ID'
		self.gameIdTextEntry.targetFile = 'boot.bin'
		self.gameIdTextEntry.bind( '<Return>', updateDiscDetails )

		ttk.Label( self.discDetailsTab.row2, image=self.imageBank('gameIdBreakdownImage') ).grid( column=2, row=0, rowspan=4, padx=self.discDetailsTab.row2.padx )

		consoleIdText = Tk.StringVar()
		gameCodeText = Tk.StringVar()
		regionCodeText = Tk.StringVar()
		makerCodeText = Tk.StringVar()
		ttk.Label( self.discDetailsTab.row2, text='Console ID:' ).grid( column=3, row=0, sticky='e', padx=self.discDetailsTab.row2.padx )
		ttk.Label( self.discDetailsTab.row2, textvariable=consoleIdText, width=3 ).grid( column=4, row=0, sticky='w', padx=self.discDetailsTab.row2.padx )
		ttk.Label( self.discDetailsTab.row2, text='Game Code:' ).grid( column=3, row=1, sticky='e', padx=self.discDetailsTab.row2.padx )
		ttk.Label( self.discDetailsTab.row2, textvariable=gameCodeText, width=3 ).grid( column=4, row=1, sticky='w', padx=self.discDetailsTab.row2.padx )
		ttk.Label( self.discDetailsTab.row2, text='Region Code:' ).grid( column=3, row=2, sticky='e', padx=self.discDetailsTab.row2.padx )
		ttk.Label( self.discDetailsTab.row2, textvariable=regionCodeText, width=3 ).grid( column=4, row=2, sticky='w', padx=self.discDetailsTab.row2.padx )
		ttk.Label( self.discDetailsTab.row2, text='Maker Code:' ).grid( column=3, row=3, sticky='e', padx=self.discDetailsTab.row2.padx )
		ttk.Label( self.discDetailsTab.row2, textvariable=makerCodeText, width=3 ).grid( column=4, row=3, sticky='w', padx=self.discDetailsTab.row2.padx )

		ttk.Separator( self.discDetailsTab.row2, orient='vertical' ).grid( column=5, row=0, sticky='ns', rowspan=4, padx=self.discDetailsTab.row2.padx, pady=6 )

		self.bannerCanvas2 = Tk.Canvas( self.discDetailsTab.row2, width=96, height=32, borderwidth=0, highlightthickness=0 )
		self.bannerCanvas2.grid( column=6, row=1, rowspan=2, padx=self.discDetailsTab.row2.padx )
		self.bannerCanvas2.pilImage = None
		self.bannerCanvas2.bannerGCstorage = None
		self.bannerCanvas2.canvasImageItem = None

		bannerImportExportFrame = ttk.Frame( self.discDetailsTab.row2 )
		bannerExportLabel = ttk.Label( bannerImportExportFrame, text='Export', foreground='#00F', cursor='hand2' )
		bannerExportLabel.bind( '<1>', exportBanner )
		bannerExportLabel.pack( side='left' )
		ttk.Label( bannerImportExportFrame, text=' | ' ).pack( side='left' )
		bannerImportLabel = ttk.Label( bannerImportExportFrame, text='Import', foreground='#00F', cursor='hand2' )
		bannerImportLabel.bind( '<1>', importImageFiles )
		bannerImportLabel.pack( side='left' )
		bannerImportExportFrame.grid( column=6, row=3, padx=self.discDetailsTab.row2.padx )

		ttk.Separator( self.discDetailsTab.row2, orient='vertical' ).grid( column=7, row=0, sticky='ns', rowspan=4, padx=self.discDetailsTab.row2.padx, pady=6 )

		self.isoVersionText = Tk.StringVar()
		self.isoFileCountText = Tk.StringVar()
		self.isoFilesizeText = Tk.StringVar()
		self.isoFilesizeTextLine2 = Tk.StringVar()
		ttk.Label( self.discDetailsTab.row2, text='Disc Revision:' ).grid( column=8, row=0, sticky='e', padx=self.discDetailsTab.row2.padx )
		ttk.Label( self.discDetailsTab.row2, textvariable=self.isoVersionText ).grid( column=9, row=0, sticky='w', padx=self.discDetailsTab.row2.padx )
		# The 20XX Version label will be here, at column 8/9, row 1, if the disc is 20XX
		ttk.Label( self.discDetailsTab.row2, text='Total File Count:' ).grid( column=8, row=2, sticky='e', padx=self.discDetailsTab.row2.padx )
		ttk.Label( self.discDetailsTab.row2, textvariable=self.isoFileCountText ).grid( column=9, row=2, sticky='w', padx=self.discDetailsTab.row2.padx )
		ttk.Label( self.discDetailsTab.row2, text='Disc Size:' ).grid( column=8, row=3, sticky='e', padx=self.discDetailsTab.row2.padx )
		ttk.Label( self.discDetailsTab.row2, textvariable=self.isoFilesizeText ).grid( column=9, row=3, sticky='w', padx=self.discDetailsTab.row2.padx )
		ttk.Label( self.discDetailsTab.row2, textvariable=self.isoFilesizeTextLine2 ).grid( column=8, row=4, columnspan=2, sticky='e', padx=self.discDetailsTab.row2.padx )

		# Set cursor hover bindings for the help text
		previousLabelWidget = ( None, '' )
		for widget in self.discDetailsTab.row2.winfo_children(): # Widgets will be listed in the order that they were added to the parent

			if widget.winfo_class() == 'TLabel' and ':' in widget['text']: # Bindings for the preceding Label
				updateName = widget['text'].replace(':', '')
				widget.bind( '<Enter>', lambda event, helpTextName=updateName: setDiscDetailsHelpText(helpTextName) )
				widget.bind( '<Leave>', setDiscDetailsHelpText )
				previousLabelWidget = ( widget, updateName )

			elif previousLabelWidget[0]: # Bindings for the labels displaying the value/info
				widget.bind( '<Enter>', lambda event, helpTextName=previousLabelWidget[1]: setDiscDetailsHelpText(helpTextName) )
				widget.bind( '<Leave>', setDiscDetailsHelpText )
				previousLabelWidget = ( None, '' )

			elif widget.grid_info()['row'] == '4': # For the second label for isoFilesize
				widget.bind( '<Enter>', lambda event: setDiscDetailsHelpText('Disc Size') )
				widget.bind( '<Leave>', setDiscDetailsHelpText )

		self.discDetailsTab.row2.pack( padx=15, pady=0, expand=1 )
		self.discDetailsTab.row2.columnconfigure( 2, weight=0 ) # Allows the middle column (the actual text input fields) to stretch with the window
		self.discDetailsTab.row2.columnconfigure( 4, weight=1 )
		self.discDetailsTab.row2.columnconfigure( 5, weight=0 )
		self.discDetailsTab.row2.columnconfigure( 6, weight=1 )
		self.discDetailsTab.row2.columnconfigure( 7, weight=0 )
		self.discDetailsTab.row2.columnconfigure( 8, weight=1 )
		virtualLabel = ttk.Label( self.discDetailsTab, text='0,000,000,000 bytes' ) # Used to figure out how much space various fonts/sizes will require
		predictedComfortableWidth = int( virtualLabel.winfo_reqwidth() * 1.2 ) # This should be plenty of space for the total disc size value.
		self.discDetailsTab.row2.columnconfigure( 9, weight=1, minsize=predictedComfortableWidth )

				# The start of row 3
		self.discDetailsTab.row3 = Tk.Frame( self.discDetailsTab ) # Uses a grid layout for its children
		self.shortTitle = Tk.StringVar()
		self.shortMaker = Tk.StringVar()
		self.longTitle = Tk.StringVar()
		self.longMaker = Tk.StringVar()

		borderColor1 = '#b7becc'; borderColor2 = '#0099f0'
		ttk.Label( self.discDetailsTab.row3, text='Image Name:' ).grid( column=0, row=0, sticky='e' )
		self.gameName1Field = Tk.Text( self.discDetailsTab.row3, height=3, highlightbackground=borderColor1, highlightcolor=borderColor2, highlightthickness=1, borderwidth=0 )
		gameName1FieldScrollbar = Tk.Scrollbar( self.discDetailsTab.row3, command=self.gameName1Field.yview ) # This is used instead of just a ScrolledText widget because .getattr() won't work on the latter
		self.gameName1Field['yscrollcommand'] = gameName1FieldScrollbar.set
		self.gameName1Field.grid( column=1, row=0, columnspan=2, sticky='ew' )
		gameName1FieldScrollbar.grid( column=3, row=0 )
		self.gameName1Field.offset = 0x20; self.gameName1Field.maxByteLength = 992; self.gameName1Field.updateName = 'Image Name'; self.gameName1Field.targetFile = 'boot.bin'
		ttk.Label( self.discDetailsTab.row3, text='992' ).grid( column=4, row=0 )
		textWidgetFont = self.gameName1Field['font']

		ttk.Label( self.discDetailsTab.row3, text='Short Title:' ).grid( column=0, row=1, sticky='e' )
		gameName2Field = Tk.Entry( self.discDetailsTab.row3, width=32, textvariable=self.shortTitle, highlightbackground=borderColor1, highlightcolor=borderColor2, highlightthickness=1, borderwidth=0, font=textWidgetFont )
		gameName2Field.grid( column=1, row=1, columnspan=2, sticky='w' )
		gameName2Field.offset = 0x1820; gameName2Field.maxByteLength = 32; gameName2Field.updateName = 'Short Title'; gameName2Field.targetFile = 'opening.bnr'
		ttk.Label( self.discDetailsTab.row3, text='32' ).grid( column=4, row=1 )

		ttk.Label( self.discDetailsTab.row3, text='Short Maker:' ).grid( column=0, row=2, sticky='e' )
		developerField = Tk.Entry( self.discDetailsTab.row3, width=32, textvariable=self.shortMaker, highlightbackground=borderColor1, highlightcolor=borderColor2, highlightthickness=1, borderwidth=0, font=textWidgetFont )
		developerField.grid( column=1, row=2, columnspan=2, sticky='w' )
		developerField.offset = 0x1840; developerField.maxByteLength = 32; developerField.updateName = 'Short Maker'; developerField.targetFile = 'opening.bnr'
		ttk.Label( self.discDetailsTab.row3, text='32' ).grid( column=4, row=2 )

		ttk.Label( self.discDetailsTab.row3, text='Long Title:' ).grid( column=0, row=3, sticky='e' )
		fullGameTitleField = Tk.Entry( self.discDetailsTab.row3, width=64, textvariable=self.longTitle, highlightbackground=borderColor1, highlightcolor=borderColor2, highlightthickness=1, borderwidth=0, font=textWidgetFont )
		fullGameTitleField.grid( column=1, row=3, columnspan=2, sticky='w' )
		fullGameTitleField.offset = 0x1860; fullGameTitleField.maxByteLength = 64; fullGameTitleField.updateName = 'Long Title'; fullGameTitleField.targetFile = 'opening.bnr'
		ttk.Label( self.discDetailsTab.row3, text='64' ).grid( column=4, row=3 )

		ttk.Label( self.discDetailsTab.row3, text='Long Maker:' ).grid( column=0, row=4, sticky='e' )
		devOrDescField = Tk.Entry( self.discDetailsTab.row3, width=64, textvariable=self.longMaker, highlightbackground=borderColor1, highlightcolor=borderColor2, highlightthickness=1, borderwidth=0, font=textWidgetFont )
		devOrDescField.grid( column=1, row=4, columnspan=2, sticky='w' )
		devOrDescField.offset = 0x18a0; devOrDescField.maxByteLength = 64; devOrDescField.updateName = 'Long Maker'; devOrDescField.targetFile = 'opening.bnr'
		ttk.Label( self.discDetailsTab.row3, text='64' ).grid( column=4, row=4 )

		ttk.Label( self.discDetailsTab.row3, text='Comment:' ).grid( column=0, row=5, sticky='e' )
		self.gameDescField = Tk.Text( self.discDetailsTab.row3, height=2, highlightbackground=borderColor1, highlightcolor=borderColor2, highlightthickness=1, borderwidth=0 )
		self.gameDescField.grid( column=1, row=5, columnspan=2, sticky='ew' )
		self.gameDescField.offset = 0x18e0; self.gameDescField.maxByteLength = 128; self.gameDescField.updateName = 'Comment'; self.gameDescField.targetFile = 'opening.bnr'
		self.gameDescField.bind( '<Shift-Return>', disallowLineBreaks )
		ttk.Label( self.discDetailsTab.row3, text='128' ).grid( column=4, row=5 )

		ttk.Label( self.discDetailsTab.row3, text='Encoding:' ).grid( column=0, row=6, sticky='e' )
		self.discDetailsTab.encodingFrame = ttk.Frame( self.discDetailsTab.row3 )
		self.countryCode = Tk.StringVar()
		self.countryCode.set( 'us' ) # This is just a default. Officially set when a disc is loaded.
		Tk.Radiobutton( self.discDetailsTab.encodingFrame, text='English/EU (Latin_1)', variable=self.countryCode, value='us', command=reloadBanner ).pack( side='left', padx=(9,6) )
		Tk.Radiobutton( self.discDetailsTab.encodingFrame, text='Japanese (Shift_JIS)', variable=self.countryCode, value='jp', command=reloadBanner ).pack( side='left', padx=6 )
		self.discDetailsTab.encodingFrame.grid( column=1, row=6, sticky='w' )
		ttk.Label( self.discDetailsTab.row3, text='Max Characters/Bytes ^  ' ).grid( column=2, row=6, columnspan=3, sticky='e' )

		# Add event handlers for the updating function and help/hover text (also sets x/y padding)
		children = self.discDetailsTab.row3.winfo_children()
		previousWidget = children[0]
		for widget in children: 
			widget.grid_configure( padx=4, pady=3 )
			updateName = getattr( widget, 'updateName', None )

			if updateName:
				# Cursor hover bindings for the preceding Label
				previousWidget.bind( '<Enter>', lambda event, helpTextName=updateName: setDiscDetailsHelpText(helpTextName) )
				previousWidget.bind( '<Leave>', setDiscDetailsHelpText )

				# Data entry (pressing 'Enter') and cursor hover bindings for the text entry field
				widget.bind( '<Return>', updateDiscDetails )
				widget.bind( '<Enter>', lambda event, helpTextName=updateName: setDiscDetailsHelpText(helpTextName) )
				widget.bind( '<Leave>', setDiscDetailsHelpText )
			previousWidget = widget

		self.discDetailsTab.row3.columnconfigure( 1, weight=1 ) # Allows the middle column (the actual text input fields) to stretch with the window
		self.discDetailsTab.row3.pack( fill='both', expand=1, padx=15, pady=4 )

				# The start of row 4
		self.discDetailsTab.textHeightAssementWidget = ttk.Label( self.root, text=' \n \n \n ' )
		self.discDetailsTab.textHeightAssementWidget.pack( side='bottom' )
		self.discDetailsTab.textHeightAssementWidget.update()
		theHeightOf4Lines = self.discDetailsTab.textHeightAssementWidget.winfo_height() # A dynamic value for differing system/user font sizes
		self.discDetailsTab.textHeightAssementWidget.destroy() # The above widget won't even be visible for a moment, because the application is minimized until drawing is complete.

		ttk.Separator( self.discDetailsTab, orient='horizontal' ).pack( fill='x', expand=1, padx=30 )
		self.discDetailsTab.row4 = ttk.Frame( self.discDetailsTab, height=theHeightOf4Lines, padding='0 0 0 12' ) # Padding order: Left, Top, Right, Bottom.
		self.discDetailsTabHelpText = Tk.StringVar()
		self.discDetailsTabHelpText.set( "Hover over an item to view information on it.\nPress 'Enter' to submit changes in a text input field before saving." )
		self.discDetailsTab.helpTextLabel = ttk.Label( self.discDetailsTab.row4, textvariable=self.discDetailsTabHelpText, wraplength=680 ) #, background='white'
		self.discDetailsTab.helpTextLabel.pack( expand=1, pady=0 )
		self.discDetailsTab.row4.pack( expand=1, fill='both' )
		self.discDetailsTab.row4.pack_propagate( False )

		# Establish character length validation, and updates between GameID labels
		def validateDiscDetailLen( stringVar, maxCharacters ):
			enteredValue = stringVar.get()
			if len( enteredValue ) > maxCharacters: stringVar.set( enteredValue[:maxCharacters] )
			elif maxCharacters < 10: # i.e. the gameIdText
				if stringVar == self.gameIdText:
					consoleIdText.set( '' )
					gameCodeText.set( '' )
					regionCodeText.set( '' )
					makerCodeText.set( '' )
					if len(enteredValue) > 0: consoleIdText.set( enteredValue[0] )
					if len(enteredValue) > 1: gameCodeText.set( enteredValue[1:3] )
					if len(enteredValue) > 3: regionCodeText.set( enteredValue[3] )
					if len(enteredValue) > 4: makerCodeText.set( enteredValue[4:7] )

		self.gameIdText.trace( 'w', lambda nm, idx, mode, var=self.gameIdText: validateDiscDetailLen(var, 6) )
		self.shortTitle.trace( 'w', lambda nm, idx, mode, var=self.shortTitle: validateDiscDetailLen(var, 32) )
		self.shortMaker.trace( 'w', lambda nm, idx, mode, var=self.shortMaker: validateDiscDetailLen(var, 32) )
		self.longTitle.trace( 'w', lambda nm, idx, mode, var=self.longTitle: validateDiscDetailLen(var, 64) )
		self.longMaker.trace( 'w', lambda nm, idx, mode, var=self.longMaker: validateDiscDetailLen(var, 64) )

																									# Tab 3 | DAT Texture Tree tab
		self.datTab = ttk.Frame( self.mainTabFrame )
		self.mainTabFrame.add( self.datTab, text=' DAT Texture Tree ' )
		self.dnd.bindtarget( self.datTab, lambda event: dndHandler( event, 'datTab' ), 'text/uri-list' )

		# DAT tab, row 1

		datTabRow1 = ttk.Frame( self.datTab, padding="12 12 12 12" ) # Padding order: Left, Top, Right, Bottom.
		ttk.Label( datTabRow1, text=" DAT / USD:" ).pack( side='left' )
		self.datDestination = Tk.StringVar()
		datDestinationLabel1 = ttk.Entry( datTabRow1, textvariable=self.datDestination )
		datDestinationLabel1.pack( side='left', fill='x', expand=1, padx=12 )
		datDestinationLabel1.bind( '<Return>', openDatDestination )
		datTabRow1.pack( fill='x', side='top' )

		# DAT tab, row 2 | Frame for the image tree and info pane

		datTabRow2 = ttk.Frame( self.datTab, padding="12 0 12 12" ) # Contains the tree and the info pane. Padding order: Left, Top, Right, Bottom.

		# File Tree start
		datTreeScroller = Tk.Scrollbar( datTabRow2 )
		self.datTextureTree = ttk.Treeview( datTabRow2, columns=('texture', 'dimensions', 'type'), yscrollcommand=datTreeScroller.set )
		self.datTextureTree.heading('#0', anchor='center', text='Preview')
		self.datTextureTree.column('#0', anchor='center', minwidth=104, stretch=0, width=104) # "#0" is implicit in columns definition above.
		self.datTextureTree.heading('texture', anchor='center', text='Offset  (len)', command=lambda: treeview_sort_column( self.datTextureTree, 'texture', False ))
		self.datTextureTree.column('texture', anchor='center', minwidth=80, stretch=0, width=100)
		self.datTextureTree.heading('dimensions', anchor='center', text='Dimensions', command=lambda: treeview_sort_column( self.datTextureTree, 'dimensions', False ))
		self.datTextureTree.column('dimensions', anchor='center', minwidth=80, stretch=0, width=100)
		self.datTextureTree.heading('type', anchor='center', text='Texture Type', command=lambda: treeview_sort_column( self.datTextureTree, 'type', False ))
		self.datTextureTree.column('type', anchor='center', minwidth=75, stretch=0, width=100)
		self.datTextureTree.pack( fill='both', side='left' )
		datTreeScroller.config( command=self.datTextureTree.yview )
		datTreeScroller.pack( side='left', fill='y' )
		self.datTextureTree.lastLoaded = None # Used by the 'Prev./Next' file loading buttons on the DAT Texture Tree tab
		self.datTextureTree.bind( '<<TreeviewSelect>>', onTextureTreeSelect )
		self.datTextureTree.bind( "<3>", createTextureTreeContextMenu ) # Summons the right-click context menu.

		# Create repositories to store image data (these are used to prevent garbage collected)
		self.datTextureTree.fullTextureRenders = {}
		self.datTextureTree.textureThumbnails = {}

		# Background widgets
		self.datTextureTreeBg = Tk.Label( self.datTextureTree, image=self.imageBank('dndTarget'), borderwidth=0, highlightthickness=0 )
		self.datTextureTreeBg.place(relx=0.5, rely=0.5, anchor='center')
		self.datTextureTreeStatusMsg = Tk.StringVar()
		self.datTextureTreeStatusLabel = ttk.Label( self.datTextureTree, textvariable=self.datTextureTreeStatusMsg, background='white' )

		# Item highlighting. The order of the configs below reflects (but does not dictate) the priority of their application
		self.datTextureTree.tag_configure( 'warn', background='#f6c6d7' ) # light red
		self.datTextureTree.tag_configure( 'mipmap', background='#d7e1ff' ) # light blue; same as SA tab 'marked' items

		# File Tree end

		defaultCanvasDimensions = 258 # Default size for the height and width of the texture viewing canvas. 256 + 1px border

		self.imageManipTabs = ttk.Notebook(datTabRow2)#, width=330

		self.textureTreeImagePane = Tk.Frame(self.imageManipTabs)
		self.imageManipTabs.add( self.textureTreeImagePane, text=' Image ', sticky='nsew' )

		canvasOptionsPane = ttk.Frame(self.textureTreeImagePane, padding='0 15 0 0')
		ttk.Checkbutton( canvasOptionsPane, command=self.updateCanvasGrid, text='Show Grid', variable=generalBoolSettings['showCanvasGrid'] ).pack(side='left', padx=7)
		ttk.Checkbutton( canvasOptionsPane, command=updateCanvasTextureBoundary, text='Show Texture Boundary', variable=generalBoolSettings['showTextureBoundary'] ).pack(side='left', padx=7)
		canvasOptionsPane.pack()

		self.textureDisplayFrame = Tk.Frame(self.textureTreeImagePane) # The border and highlightthickness for the canvas below must be set to 0, so that the canvas has a proper origin of (0, 0).
		self.textureDisplay = Tk.Canvas(self.textureDisplayFrame, width=defaultCanvasDimensions, height=defaultCanvasDimensions, borderwidth=0, highlightthickness=0) #, background='blue'
		# alternate dynamic imaging technique: http://stackoverflow.com/questions/3482081/tkinter-label-widget-with-image-update
		self.textureDisplay.pack( expand=1 ) # fill='both', padx=10, pady=10

		self.updateCanvasGrid()

		self.textureDisplay.defaultDimensions = defaultCanvasDimensions
		self.textureDisplayFrame.pack( expand=1 )

		datPreviewPaneBottomRow = Tk.Frame(self.textureTreeImagePane) # This object uses grid alignment for its children so that they're centered and equally spaced amongst each other.

		self.previousDatButton = ttk.Label( datPreviewPaneBottomRow, image=self.imageBank('previousDatButton') )
		self.previousDatButton.grid( column=0, row=0, ipadx=5, pady=(10, 0), sticky='e' )
		self.previousDatText = Tk.StringVar()
		ToolTip( self.previousDatButton, textvariable=self.previousDatText, delay=300, location='n' )

		datFileDetails = ttk.Labelframe( datPreviewPaneBottomRow, text='  File Details  ', labelanchor='n' )
		self.datFilesizeText = Tk.StringVar()
		self.datFilesizeText.set('File Size:  ')
		ttk.Label(datFileDetails, textvariable=self.datFilesizeText, width=23)
		self.totalTextureSpaceText = Tk.StringVar()
		self.totalTextureSpaceText.set('Total Texture Size:  ')
		ttk.Label(datFileDetails, textvariable=self.totalTextureSpaceText)
		self.texturesFoundText = Tk.StringVar()
		self.texturesFoundText.set('Textures Found:  ')
		ttk.Label(datFileDetails, textvariable=self.texturesFoundText)
		self.texturesFilteredText = Tk.StringVar()
		self.texturesFilteredText.set('Filtered Out:  ')
		ttk.Label(datFileDetails, textvariable=self.texturesFilteredText)

		for widget in datFileDetails.winfo_children():
			widget.pack( padx=20, pady=0, anchor='w' )

		datFileDetails.grid( column=1, row=0 )

		self.nextDatButton = ttk.Label( datPreviewPaneBottomRow, image=self.imageBank('nextDatButton') )
		self.nextDatButton.grid( column=2, row=0, ipadx=5, pady=(10, 0), sticky='w' )
		self.nextDatText = Tk.StringVar()
		ToolTip( self.nextDatButton, textvariable=self.nextDatText, delay=300, location='n' )

		datPreviewPaneBottomRow.columnconfigure(0, weight=1)
		datPreviewPaneBottomRow.columnconfigure(1, weight=1)
		datPreviewPaneBottomRow.columnconfigure(2, weight=1)
		datPreviewPaneBottomRow.rowconfigure(0, weight=1)

		datPreviewPaneBottomRow.pack(side='bottom', pady=7, fill='x')

		# Palette tab
		self.palettePane = ttk.Frame( self.imageManipTabs, padding='16 0 0 0' )
		self.imageManipTabs.add( self.palettePane, text=' Palette ', state='disabled' )
		self.imageManipTabs.bind( '<<NotebookTabChanged>>', self.imageManipTabChanged )

		# Left-side column (canvas and bg color changer button)
		paletteTabLeftSide = Tk.Frame(self.palettePane)
		self.paletteCanvas = Tk.Canvas( paletteTabLeftSide, borderwidth=3, relief='ridge', background='white', width=187, height=405 ) #old height:373
		paletteBgColorChanger = ttk.Label( paletteTabLeftSide, text='Change Background Color', foreground='#00F', cursor='hand2' )
		self.paletteCanvas.paletteEntries = []
		self.paletteCanvas.itemColors = {}
		paletteBgColorChanger.bind( '<1>', togglePaletteCanvasColor )
		self.paletteCanvas.pack( pady=11, padx=0 )
		self.paletteCanvas.entryBorderColor = '#3399ff' # This is the same blue as used for treeview selection highlighting
		paletteBgColorChanger.pack()
		paletteTabLeftSide.grid( column=0, row=0 )

		# Right-side column (palette info)
		paletteDetailsFrame = Tk.Frame(self.palettePane)
		self.paletteDataText = Tk.StringVar( value='Data Offset:' )
		ttk.Label( paletteDetailsFrame, textvariable=self.paletteDataText ).pack(pady=3)
		self.paletteHeaderText = Tk.StringVar( value='Header Offset:' )
		ttk.Label( paletteDetailsFrame, textvariable=self.paletteHeaderText ).pack(pady=3)
		self.paletteTypeText = Tk.StringVar( value='Palette Type:' )
		ttk.Label( paletteDetailsFrame, textvariable=self.paletteTypeText ).pack(pady=3)
		self.paletteMaxColorsText = Tk.StringVar( value='Max Colors:')
		ttk.Label( paletteDetailsFrame, textvariable=self.paletteMaxColorsText ).pack(pady=3)
		self.paletteStatedColorsText = Tk.StringVar( value='Stated Colors:' )
		ttk.Label( paletteDetailsFrame, textvariable=self.paletteStatedColorsText ).pack(pady=3)
		#self.paletteActualColorsText = Tk.StringVar( value='Actual Colors:' ) # todo:reinstate?
		#ttk.Label( paletteDetailsFrame, textvariable=self.paletteActualColorsText ).pack(pady=3)
		paletteDetailsFrame.grid( column=1, row=0, pady=60, sticky='n' )

		self.palettePane.columnconfigure( 0, weight=1 )
		self.palettePane.columnconfigure( 1, weight=2 )
		
		# Add a help button to explain the above
		helpText = ( 'Max Colors is the maximum number of colors this texture has space for with its current texture format.\n\n'
					 'Stated Colors is the number of colors that the palette claims are actually used by the texture (described by the palette data header).\n\n'
					 'The number of colors actually used may still differ from both of these numbers, especially for very old texture hacks.' )
		helpBtn = ttk.Label( self.palettePane, text='?', foreground='#445', cursor='hand2' )
		helpBtn.place( relx=1, x=-17, y=18 )
		helpBtn.bind( '<1>', lambda e, message=helpText: msg(message, 'Palette Properties') )

		# Model parts tab
		self.modelPropertiesPane = VerticalScrolledFrame( self.imageManipTabs )
		self.imageManipTabs.add( self.modelPropertiesPane, text='Model', state='disabled' )
		self.modelPropertiesPane.interior.imageDataHeaders = []
		self.modelPropertiesPane.interior.nonImageDataHeaders = [] # Not expected
		self.modelPropertiesPane.interior.textureStructs = [] # Direct model attachments
		self.modelPropertiesPane.interior.headerArrayStructs = [] # Used for animations
		self.modelPropertiesPane.interior.unexpectedStructs = []
		self.modelPropertiesPane.interior.materialStructs = []
		self.modelPropertiesPane.interior.displayObjects = []
		self.modelPropertiesPane.interior.hideJointChkBtn = None
		self.modelPropertiesPane.interior.polyDisableChkBtn = None
		self.modelPropertiesPane.interior.opacityEntry = None
		self.modelPropertiesPane.interior.opacityBtn = None
		self.modelPropertiesPane.interior.opacityScale = None

		# Texture properties tab
		self.texturePropertiesPane = VerticalScrolledFrame( self.imageManipTabs )
		self.texturePropertiesPane.flagWidgets = [] # Useful for the Flag Decoder to more easily find widgets that need updating
		self.imageManipTabs.add( self.texturePropertiesPane, text='Properties', state='disabled' )

		self.imageManipTabs.pack( fill='both', expand=1 )

		datTabRow2.pack(fill='both', expand=1)
		# End of DAT tab row 2, the image tree and info pane.

																									# Tab 4 | Structural Analysis

		self.savTab = ttk.Frame( self.mainTabFrame ) # SAV = Structural Analysis View
		self.mainTabFrame.add( self.savTab, text=' Structural Analysis ' )
		self.dnd.bindtarget( self.savTab, lambda event: dndHandler( event, 'savTab' ), 'text/uri-list' )

		# Create the treeview on the left where structures will be browsed
		yScroller = Tk.Scrollbar( self.savTab )
		xScroller = Tk.Scrollbar( self.savTab, orient='horizontal' )
		self.fileStructureTree = ttk.Treeview( self.savTab, columns='offset', yscrollcommand=yScroller.set, xscrollcommand=xScroller.set, selectmode='extended' )
		self.fileStructureTree.heading( '#0', anchor='center' ) # , command=function
		self.fileStructureTree.column( '#0', anchor='center', minwidth=200, stretch=True, width=180 ) # "#0" is implicit in the columns definition above.
		self.fileStructureTree.heading( 'offset', anchor='center', text='Offset' )
		self.fileStructureTree.column( 'offset', anchor='e', minwidth=60, stretch=False, width=76 )
		self.fileStructureTree.grid( column=0, row=0, sticky="nsew" )

		self.fileStructureTree.tag_configure( 'marked', background='#d7e1ff' ) # light blue; same as mipmap highlight color

		# Configure and attach the scrollbars
		yScroller.config( command=self.fileStructureTree.yview )
		xScroller.config( command=self.fileStructureTree.xview )
		yScroller.grid( column=1, row=0, sticky="nsew" )
		xScroller.grid( column=0, row=1, columnspan=2, sticky="nsew" )
		self.fileStructureTree.yScroller = yScroller
		self.fileStructureTree.xScroller = xScroller

		# Add treeview event handlers
		self.fileStructureTree.bind( '<<TreeviewSelect>>', onStructureTreeSelect )
		self.fileStructureTree.bind( '<<TreeviewOpen>>', growStructuralAnalysisTree ) # Occurs when expanding items with children
		#self.fileStructureTree.bind( '<Double-1>', onStructureTreeDoubleClick ) # todo: find workaround. some kind of conflict prevents this from working
		self.fileStructureTree.bind( "<3>", createStructureTreeContextMenu ) # Right-click

		# Create the frame on the right where structure properties will be populated
		self.structurePropertiesFrame = VerticalScrolledFrame( self.savTab, width=378 )
		self.structurePropertiesFrame.grid( column=2, row=0, sticky="nsew" )

		# Configure sizing/resizing behavior of the grid cells
		self.savTab.grid_columnconfigure( 0, weight=5 )
		self.savTab.grid_columnconfigure( 1, weight=0 )
		self.savTab.grid_columnconfigure( 2, weight=1, minsize=378 )
		self.savTab.grid_rowconfigure( 0, weight=1 )

		# Place the DnD background texture
		self.fileStructureTreeBg = Tk.Label( self.fileStructureTree, image=self.imageBank('dndTarget'), borderwidth=0, highlightthickness=0 )
		self.fileStructureTreeBg.place( relx=0.5, rely=0.5, anchor='center' )
		self.fileStructureTree.allIids = []

		# Place the search button (and its hover cursor & text)
		self.fileStructureTree.searchBtn = Tk.Label( self.fileStructureTree, image=self.imageBank('searchIcon'), bg='white', borderwidth=0, highlightthickness=0 )
		self.fileStructureTree.searchBtn.place( rely=1, x=3, y=-6, anchor='sw' )
		self.fileStructureTree.searchBtn.bind( '<1>', lambda event: structSearchWindow() )
		self.fileStructureTree.searchBtn.config( cursor='hand2' )
		ToolTip( self.fileStructureTree.searchBtn, text='Structure Search (CTRL-F)', delay=500 )

		self.structPropFrameWrapLength = 300 # The Label wrap length for text inside the structurePropertiesFrame.

																									# Tab 5 | Manual Texture Replacement

		self.mtrTab = ttk.Frame( self.mainTabFrame )
		self.mainTabFrame.add( self.mtrTab, text=' Manual Placement ' )
		self.dnd.bindtarget( self.mtrTab, lambda event: dndHandler( event, 'mtrTab' ), 'text/uri-list' )

		# MTR tab, row 1
		mtrTabRow1 = ttk.Frame( self.mtrTab, padding="12 12 12 0" ) # Left, Top, Right, Bottom

		ttk.Label( mtrTabRow1, text=" DAT / USD:" ).pack( side='left' )
		datDestinationLabel2 = ttk.Entry( mtrTabRow1, textvariable=self.datDestination ) #, font='TkTextFont'
		datDestinationLabel2.pack( side='left', fill='x', expand=1, padx=12 )

		mtrTabRow1.pack(fill='x', side='top')

		# MTR tab, row 2 | Directions
		ttk.Label( self.mtrTab, text="This tab gives you the freedom to write a texture into any exact location."
							"\nThat even includes any textures that don't normally appear in the DAT Texture Tree."
							"\nYou can riffle through the 'Program Usage.txt' file for information on how to use this." ).pack(pady=9)

		# MTR tab, row 3 | Texture input
		self.mtrTabRow2 = ttk.Frame(self.mtrTab, padding="12 6 0 0") # Left, Top, Right, Bottom

		self.sourceTexturesText = Tk.StringVar()
		self.sourceTexturesText.set("Texture(s):\n  (0 total)")
		ttk.Label(self.mtrTabRow2, textvariable=self.sourceTexturesText).pack(side='left') #.grid(column=1, row=1, sticky='ne')

		self.imageTextArea = ScrolledText(self.mtrTabRow2, width=74, height=14, wrap='word', font='TkTextFont')
		self.imageTextArea.pack(side='left', fill='x', expand=1, padx=12)
		self.imageTextArea.bind('<KeyRelease>', onTextAreaKeyUp)
		arrowFont = tkFont.Font(family='Courier', size='8', weight='bold')
		##self.imageTextArea.tag_config('offsetArrow', foreground='#0066FF', font=arrowFont)
		self.imageTextArea.tag_config('offsetArrow', foreground='#119922', font=arrowFont)
		self.imageTextArea.tag_config('successfulOverwrite', background='#99FF99', font='TkTextFont')
		self.imageTextArea.tag_config('warningOverwrite', background='#FFFF99', font='TkTextFont')
		self.imageTextArea.tag_config('failedOverwrite', background='#FF9999', font='TkTextFont')

		mtrBtnFrame = ttk.Frame(self.mtrTabRow2, padding=12)
		ttk.Button(mtrBtnFrame, text=" Select Textures ", command=importImageFiles).pack(pady=3)
		ttk.Button(mtrBtnFrame, text=" Scan folder \n   structure", command=scanFolderStructure).pack(pady=3)
		ttk.Button(mtrBtnFrame, text=" Clear Highlighting ", command=clearHighlighting).pack(pady=3)
		ttk.Separator(mtrBtnFrame, orient='horizontal').pack(fill='x', padx=6, pady=7)
		ttk.Button(mtrBtnFrame, text="Write textures into DAT", command=overwriteImagesManually, width=23).pack(pady=3)
		self.mtrSaveBackup = Tk.BooleanVar()
		self.mtrSaveBackup.set(1)
		ttk.Checkbutton( mtrBtnFrame, text='  Keep a backup of \n  the original DAT', variable=self.mtrSaveBackup ).pack()
		mtrBtnFrame.pack(side='right')

		self.mtrTabRow2.pack(fill='x', anchor='n')

		battleFrame = Tk.Frame( self.mtrTab )
		ttk.Label( battleFrame, image=self.imageBank('cathedralBattle') ).place( relx=0.5, rely=0.5, anchor='center' )
		battleFrame.pack( fill='both', expand=1 )

																									# Tab 6 | Character Color Converter (CCC)
		self.cccTab = ttk.Frame(self.mainTabFrame)
		self.mainTabFrame.add(self.cccTab, text='  CCC  ')

		ttk.Label(self.cccTab, text=' Character Color Converter ', font="-weight bold").pack(pady=23)

		cccFileSelectionRow = Tk.Frame(self.cccTab)
		ttk.Label(cccFileSelectionRow, text="Step 1 | Choose the source file you'd like to convert." \
			"\n\n(If you're on the Disc File Tree, you can right-click \non the file and select 'Set as CCC Source File'.)", wraplength=350).grid(column=0, row=0, padx=15, pady=25)
		cccTabRow2RightCell = Tk.Frame(cccFileSelectionRow)

		ttk.Button(cccTabRow2RightCell, text=' Within a Disc ', command=cccPointToDiscTab).grid(column=0, row=0)
		ttk.Button(cccTabRow2RightCell, text=' Standalone File ', command=lambda: cccSelectStandalone('source')).grid(column=1, row=0)
		self.cccSourceCanvas = Tk.Canvas(cccTabRow2RightCell, width=290, height=64, borderwidth=0, highlightthickness=0)
		self.cccIdentifiersXPos = 90
		self.cccSourceCanvas.create_text( self.cccIdentifiersXPos, 20, anchor='w', font="-weight bold -size 10", fill=self.globalFontColor, text='Character: ') 
		self.cccSourceCanvas.create_text( self.cccIdentifiersXPos, 44, anchor='w', font="-weight bold -size 10", fill=self.globalFontColor, text='Costume Color: ')
		self.cccSourceCanvas.insigniaImage = None
		self.cccSourceCanvas.grid(column=0, row=1, columnspan=2, pady=7)

		cccTabRow2RightCell.grid(column=1, row=0)

		ttk.Label(cccFileSelectionRow, text='Step 2 | Choose a "destination" file of the desired color (and same character). This file will have its texture data replaced with the textures ' \
			"from the file above.\nSo make sure you have a back-up of this if you'd like to use it again later.", wraplength=350).grid(column=0, row=1, padx=15, pady=25)
		cccTabRow4RightCell = Tk.Frame(cccFileSelectionRow)

		ttk.Button( cccTabRow4RightCell, text=' Within a Disc ', command=cccPointToDiscTab ).grid( column=0, row=0 )
		ttk.Button( cccTabRow4RightCell, text=' Standalone File ', command=lambda: cccSelectStandalone('dest') ).grid( column=1, row=0 )
		self.cccDestCanvas = Tk.Canvas( cccTabRow4RightCell, width=290, height=64, borderwidth=0, highlightthickness=0 ) #, background='blue'
		self.cccDestCanvas.create_text( self.cccIdentifiersXPos, 20, anchor='w', font="-weight bold -size 10", fill=self.globalFontColor, text='Character: ' )
		self.cccDestCanvas.create_text( self.cccIdentifiersXPos, 44, anchor='w', font="-weight bold -size 10", fill=self.globalFontColor, text='Costume Color: ' )
		self.cccDestCanvas.insigniaImage = None
		self.cccDestCanvas.grid( column=0, row=1, columnspan=2, pady=7 )

		cccTabRow4RightCell.grid( column=1, row=1 )
		cccFileSelectionRow.pack( pady=0 )

		finalButtonsFrame = Tk.Frame( self.cccTab )
		ttk.Button( finalButtonsFrame, text='    Step 3 | Convert!    ', command=convertCharacterColor ).pack( side='left', padx=25 )
		self.cccOpenConvertedFileButton = ttk.Button( finalButtonsFrame, text='    Open Converted File    ', command=openConvertedCharacterFile, state='disabled' )
		self.cccOpenConvertedFileButton.pack( side='left', padx=25 )
		finalButtonsFrame.pack( pady=12 )

		cccBannerFrame = Tk.Frame(self.cccTab)
		ttk.Label( cccBannerFrame, image=self.imageBank('cccBanner') ).place(relx=0.5, rely=0.5, anchor='center')
		cccBannerFrame.pack( fill='both', expand=1 )

		# Set up the Drag-n-drop event handlers.
		for widget in cccFileSelectionRow.grid_slaves(row=0): self.dnd.bindtarget(widget, lambda event: dndHandler( event, 'cccTabSource' ), 'text/uri-list')
		for widget in cccFileSelectionRow.grid_slaves(row=1): self.dnd.bindtarget(widget, lambda event: dndHandler( event, 'cccTabDest' ), 'text/uri-list')

																									# Tab 5 | Character Select Screen (CSS)
		# cssTab = ttk.Frame(self.mainTabFrame)
		# self.mainTabFrame.add(cssTab, text='  CSS  ')

		# cssEmulator = Tk.Canvas(cssTab, width=320, height=240, borderwidth=0, highlightthickness=0, bg='blue')
		# cssEmulator.pack()

																									# Tab 6 | Texture Search
		# searchTab = ttk.Frame( self.mainTabFrame )
		# self.mainTabFrame.add( searchTab, text=' Search ' )


		self.mainTabFrame.pack( fill='both', expand=1 )
		self.mainTabFrame.bind( '<<NotebookTabChanged>>', self.onMainTabChanged )

		self.programStatus = Tk.StringVar()
		self.programStatus.set( '' ) # for testing position -> | xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx |
		self.programStatusLabel = Tk.Label( self.root, textvariable=self.programStatus, fg='#000000', anchor='center' )
		self.programStatusLabel.place( x=708, anchor='n' )

						# End of tabbed interface area
						# GUI Rendering complete. Initialize program.

		self.root.deiconify() # GUI has been minimized until rendering was complete. This brings it to the foreground

		# Bind keyboard shortcuts and the scroll handler
		self.root.bind( "<Control-f>", self.searchHandler )
		self.root.bind( "<Control-F>", self.searchHandler )
		self.root.bind( '<Control-r>', lambda event: runInEmulator() )
		self.root.bind( '<Control-R>', lambda event: runInEmulator() )
		self.root.bind( '<Control-s>', lambda event: saveChanges() )
		self.root.bind( '<Control-S>', lambda event: saveChanges() )
		self.root.bind_class( "Text", "<Control-a>", selectAll )
		self.root.bind_class( "TEntry", "<Control-a>", selectAll )

		# Set up the scroll handler. Unbinding native scroll functionality on some classes to prevent problems when scrolling on top of other widgets
		self.root.unbind_class( 'Text', '<MouseWheel>' ) # Allows onMouseWheelScroll below to handle this
		self.root.unbind_class( 'Treeview', '<MouseWheel>' ) # Allows onMouseWheelScroll below to handle this
		self.root.bind_all( "<MouseWheel>", onMouseWheelScroll )

		# The following 4 lines set up an update methodology for updating tkinter GUI elements that's triggered from other processes
		self.textureUpdateQueue = None
		self.processRenderingPool = None
		#self.root.bind( '<<message>>', self.updateTextureThumbnail )
		self.thumbnailUpdateJob = None
		self.thumbnailUpdateInterval = 300

		# The following is used to tell various aspects of the program that it's closing.   todo: perhaps better to use this instead of the global variable
		#self.shutdownEvent = multiprocessing.Event() # Use multiprocessing.Manager().Queue to reach into separate processes

	def searchHandler( self, event ):
		# Check the currently selected tab to determine what to do with CTRL-F presses
		currentTab = self.root.nametowidget( self.mainTabFrame.select() )
		if currentTab == self.savTab: structSearchWindow()

	def imageBank( self, imageName ):

		""" Loads and stores images required by the GUI. This allows all of the images to be 
			stored together in a similar manner, and ensures references to all of the loaded 
			images are stored, which prevents them from being garbage collected (which would 
			otherwise cause them to disappear from the GUI after rendering is complete). The
			images are only loaded when first requested, and then kept for future reference. """

		image = self._imageBank.get( imageName, None )

		if not image: # Hasn't yet been loaded
			imagePath = imagesFolder + "\\" + imageName + ".png"
			try:
				image = self._imageBank[imageName] = ImageTk.PhotoImage( Image.open( imagePath ) )
			except:
				msg( 'Unable to load the image, "' + imagePath + '".' )

		return image

	def updateMainMenuOptions( self, event ):

		""" This method is used as an efficiency improvement over using the Menu postcommand argument.

			Normally, all postcommand callbacks for all submenus that have one are called when the 
			user clicks to expand any one submenu, or even if they only click on the menubar itself,
			when no submenu even needs to be displayed. So this method works to call the callback
			of only one specific submenu when it needs to be displayed. Details here:
			https://stackoverflow.com/questions/55753828/how-can-i-execute-different-callbacks-for-different-tkinter-sub-menus

			Note that event.widget is a tk/tcl path string in this case, rather than a widget instance. """

		activeMenuIndex = self.root.call( event.widget, "index", "active" )

		if isinstance( activeMenuIndex, int ):
			activeMenu = self.menubar.winfo_children()[activeMenuIndex]

			# Check if this menu has a repopulate method (in which case it will also have an open attribute), and call it if the menu is open
			if getattr( activeMenu, 'repopulate', None ) and not activeMenu.open:
				# Repopulate the menu's contents
				activeMenu.repopulate()
				activeMenu.open = True

		else: # The active menu index is 'none'; all menus are closed, so reset the open state for all of them
			for menuWidget in self.menubar.winfo_children():
				menuWidget.open = False

	def updateCanvasGrid( self, saveChange=True ):

		"""	Shows/hides the grid behind textures displayed in the DAT Texture Tree's 'Image' tab. """

		if generalBoolSettings['showCanvasGrid'].get():
			self.textureDisplayFrame.config( highlightbackground='#c0c0c0', highlightcolor='#c0c0c0', highlightthickness=1, borderwidth=0, relief='flat' )

			canvasWidth = int( self.textureDisplay['width'] )
			canvasHeight = int( self.textureDisplay['height'] )
			gridImage = self.imageBank( 'canvasGrid' )

			# Tile the image across the canvas
			for y in xrange(0, canvasHeight + 20, 20): # start, stop, step
				for x in xrange(0, canvasWidth + 20, 20):
					self.textureDisplay.create_image( x, y, image=gridImage, tags='grid' )
			
			# Make sure any texture present stays above the grid
			if len( self.textureDisplay.find_withtag('texture') ) != 0: 
				self.textureDisplay.tag_lower('grid', 'texture')

		else:
			# Remove the grid
			for item in self.textureDisplay.find_withtag('grid'):
				self.textureDisplay.delete( item )
			self.textureDisplayFrame.config(highlightbackground='#c0c0c0', highlightcolor='#c0c0c0', highlightthickness=0, borderwidth=0, relief='flat')

		if saveChange: # Update the current selection in the settings file.
			with open( settingsFile, 'w') as theSettingsFile:
				settings.set( 'General Settings', 'showCanvasGrid', str(generalBoolSettings['showCanvasGrid'].get()) )
				settings.write( theSettingsFile )

	def updateTextureThumbnail( self ):

		""" Only used when multiprocess texture decoding is enabled.

			Updates thumbnail images on the DAT Texture Tree tab once their rendering jobs are completed.
			Rendering is done in separate processes to improve performance, however, GUI updates must all
			be handled by this same thread. The full image data and its thumbnail must be stored (not 
			simply attached to the treeview item) to prevent being garbage-collected. """

		textureUnavailableImage = self.imageBank( 'noImage' )
		currentSelection = Gui.datTextureTree.selection()
		global scanningDat, stopAndScanNewDat

		while not self.textureUpdateQueue.empty():
			textureImage, imageDataOffset = self.textureUpdateQueue.get( block=False )

			if rescanPending(): break
			elif imageDataOffset == -1 and not stopAndScanNewDat: # Indicates that there are no more textures. Can end the update loop for now
				self.thumbnailUpdateJob = None
				scanningDat = False
				updateProgramStatus( 'File Scan Complete' )
				#updateGuiOnRenderCompletion()   <- This'll be cleaner if I end up needing more here
			else:
				if textureImage:
					# Store the full texture image, and create a 64x64 thumbnail for it
					try:
						self.datTextureTree.fullTextureRenders[imageDataOffset] = ImageTk.PhotoImage( textureImage )

						textureImage.thumbnail( (64, 64), Image.ANTIALIAS )
						self.datTextureTree.textureThumbnails[imageDataOffset] = ImageTk.PhotoImage( textureImage )

					except: # Problem creating a thumbnail
						self.datTextureTree.fullTextureRenders[imageDataOffset] = textureUnavailableImage
						self.datTextureTree.textureThumbnails[imageDataOffset] = textureUnavailableImage
						print 'Unable to create a thumbnail image for', uHex( 0x20+imageDataOffset )

				else: # Problem during decoding
					self.datTextureTree.fullTextureRenders[imageDataOffset] = textureUnavailableImage
					self.datTextureTree.textureThumbnails[imageDataOffset] = textureUnavailableImage

				# Replace the 'loading...' image in the GUI with the new thumbnail image
				iid = str( imageDataOffset )
				if self.thumbnailUpdateJob and self.datTextureTree.exists( iid ): # Make sure the update loop is still running too
					self.datTextureTree.item( iid, image=self.datTextureTree.textureThumbnails[imageDataOffset] )

					# If the texture being updated is supposed to be displayed in the main display area, update that too
					if currentSelection and currentSelection[-1] == iid: # Only the last item selected is usually displayed
						drawTextureToMainDisplay( iid )

		# Continue the GUI thumbnail update loop by re-queuing this method
		if self.thumbnailUpdateJob:
			self.thumbnailUpdateJob = self.root.after( self.thumbnailUpdateInterval, self.updateTextureThumbnail )

	def onMainTabChanged( self, event ): 

		""" This function adjusts the height of rows in the treeview widgets, since the two treeviews can't be individually configured.
			It also starts DAT file structural analysis or image searching when switching to the SA tab or DAT File Tree tab if a DAT file is loaded. 
			If an attempt is made to switch to a tab that is already the current tab, this function will not be called. """

		global globalDatFile

		currentTab = self.root.nametowidget( self.mainTabFrame.select() )
		currentTab.focus() # Don't want keyboard/widget focus at any particular place yet

		if currentTab == self.datTab:
			ttk.Style().configure( 'Treeview', rowheight=76 )

			if globalDatFile and not self.datTextureTree.get_children():
				# May not have been scanned for textures yet (or none were found).
				scanDat()

		else: 
			ttk.Style().configure( 'Treeview', rowheight=20 )

			if globalDatFile and currentTab == self.savTab and not self.fileStructureTree.get_children():
				# SAV tab hasn't been populated yet. Perform analysis.
				analyzeDatStructure()

	def imageManipTabChanged( self, event ):

		""" Called when the tabs within the DAT Texture Tree tab ('Image', 'Palette', etc.) are changed.
			Main purpose is simply to prevent the first widget from gaining immediate focus. """

		currentTab = self.root.nametowidget( event.widget.select() )
		currentTab.focus() # Don't want keyboard/widget focus at any particular place yet

# Function & class definitions complete
if __name__ == '__main__':
	#multiprocessing.freeze_support() # Needed in order to compile the program with multiprocessor support

	# Initialize the GUI
	Gui = MainGui()
	#Gui.textureUpdateQueue = multiprocessing.Manager().Queue() # Needs to be enabled if multiprocessor texture decoding is enabled

	# Process any files drag-and-dropped onto the program's .exe file.
	if len( programArgs ) > 1:
		# Filter out texture files.
		Gui.root.update()
		filepaths = [filepath for filepath in programArgs if not filepath.lower().endswith('.png') and not filepath.lower().endswith('.tpl')]
		fileHandler( filepaths[1:] ) # First item is the main program script or executable (.py/.exe)

	# Start the GUI's mainloop (blocks until the GUI is taken down by .destroy or .quit)
	Gui.root.mainloop()