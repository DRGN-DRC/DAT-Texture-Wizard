#!/usr/bin/python
# This file's encoding: UTF-8, so that non-ASCII characters can be used in strings.

				# ======================================== #
			   # | ~ - [  Written by Durgan (DRGN)   ]- ~ | #
				# \        Feb, 2019; Version 2.3        / #
				   # ================================== #

# DTW's Structural Analysis tab or the following thread/post are useful for more details on structures:
# 		https://smashboards.com/threads/melee-dat-format.292603/post-21913374

import struct
import os, sys
import time, math
import tkMessageBox

from sets import Set
import hsdStructures

showLogs = True


			# = --------------------------- = #
			#  [   Basic helper functions  ]  #
			# = --------------------------- = #

def uHex( integer ): # Quick conversion to have a hex function which returns uppercase characters.
	if integer > -10 and integer < 10: return str( integer ) # 0x not required
	else: return '0x' + hex( integer )[2:].upper()

def toInt( input ): # Converts 1, 2, and 4 byte bytearray values to integers.
	byteLength = len( input )
	if ( byteLength == 1 ): return struct.unpack( '>B', input )[0]		# big-endian unsigned char (1 byte)
	elif ( byteLength == 2 ): return struct.unpack( '>H', input )[0]		# big-endian unsigned short (2 bytes)
	else: return struct.unpack( '>I', input )[0]							# big-endian unsigned int (4 bytes)

def toBytes( input, byteLength=4, cType='' ): # Converts a hex string to a bytearray
	if not cType: # Assume a big-endian unsigned value of some byte length
		if byteLength == 1: cType = '>B'		# big-endian unsigned char (1 byte)
		elif byteLength == 2: cType = '>H'		# big-endian unsigned short (2 bytes)
		elif byteLength == 4: cType = '>I'		# big-endian unsigned int (4 bytes)
		else: 
			tkMessageBox.showinfo( message='toBytes was not provided the necessary byteLength or C Type' )
			return

	return struct.pack( cType, input )

def readableArray( array ):
	return [hex(0x20+o) for o in array]


					# = ---------------------- = #
					#  [   HSD File Classes   ]  #
					# = ---------------------- = #

class datFileObj( object ):

	def __init__( self, source='file' ):
		# File location info
		self.path = '' 					# Absolute filepath on disc, or will be an iid if this file is loaded from a disc
		self.source = source 			# Describes where the file is from; may be 'disc', 'file', or 'ram' (data not yet saved)
		self.fileName = ''				# File name of the file, including file extension
		self.fileExt = ''				# The file extension (lower-case; excludes period)

		# File data groups
		self.headerData = bytearray()		# First 0x20 bytes of most DAT files
		self.data = bytearray()				# Of just the data section (unless a DOL or banner file)
		self.rtData = bytearray()			# Relocation Table data
		self.nodeTableData = bytearray()	# Root Nodes and Reference Nodes
		self.stringTableData = bytearray()	# String Table data
		self.tailData = bytearray()			# Extra custom/hacked data appearing after then normal end of the file

		# Parsing determinations
		self.headerInfo = {}
		self.stringDict = {}			# Populated by key=stringOffset, value=string (string offset is relative to the string table)
		self.rootNodes = []				# These node lists will contain tuples of the form ( structOffset, string )
		self.referenceNodes = []
		self.rootStructNodes = []		# These next 4 lists' contents are the above lists' entries, but separated by purpose
		self.rootLabelNodes = []		# into those that point to root structures in the data section (rootStructNodes),
		self.refStructNodes = []		# or those that are just labels to some of those structs (rootLabelNodes).
		self.refLabelNodes = []
		self.pointerOffsets = [] 		# List of file offsets of all pointers in the file, including root/ref node pointers
		self.pointerValues = [] 		# List of values found at the target locations of the above pointers
		self.pointers = []				# Sorted list of (pointerOffset, pointerValue) tuples, useful for looping both together
		self.structureOffsets = Set() 	# A set formed from the above pointerValues list, to exclude duplicate entries
		self.orphanStructures = Set()	# These are not attached to the rest of the file heirarchy/tree in the usual manner (i.e. no parents)
		self.structs = {}				# key = structOffset, value = HSD structure object
		self.deepDiveStats = {}			# After parsing the data section, this will contain pairs of key=structClassName, value=instanceCount
		
		self.unsavedChanges = []
		self.headerNeedsRebuilding = False
		self.rtNeedsRebuilding = False
		self.nodesNeedRebuilding = False
		self.stringsNeedRebuilding = False

	def load( self, filePath, fileData=None, fileName='' ):
		
		""" Reads in file data, parses it, and separates it into these sections: 
				headerData, data (the file's full data section), rtData, nodeTableData, 
				stringTableData, and tailData (extra data at the end of the file) """

		# Establish the file path, name, and extension
		self.path = filePath
		if fileName:
			self.fileName = fileName
		else: # Won't have case sensitivity if loading from a disc (in which case filePath is an iid)
			self.fileName = os.path.basename( filePath )
		self.fileExt = self.path.split( '.' )[-1].lower()

		fileDataRetrieved = False

		# Load the file's data
		try:
			if self.source == 'file':
				# Open the file and grab everything
				with open( filePath, 'rb' ) as datBinary:
					self.data = bytearray( datBinary.read() )

			elif not fileData: 
				raise IOError( 'No file data provided.' )

			else: # source = 'ram' or 'disc'
				self.data = fileData

			fileDataRetrieved = True

		except Exception as errorMessage:
			if showLogs:
				print 'Unable to load', self.fileName
				print errorMessage

		# If this is not a banner or DOL file, separate primary sections of the file and parse them
		if self.fileExt not in ( 'bnr', 'dol' ):
			# Separate out the file header and parse it
			self.headerData = self.data[:0x20]
			self.data = self.data[0x20:]
			self.parseHeader()
			stringTableStart = self.headerInfo['stringTableStart']
			
			# Other file sections can now be separated out, using information from the header
			self.rtData = self.data[ self.headerInfo['rtStart'] : self.headerInfo['rtEnd'] ]
			self.nodeTableData = self.data[ self.headerInfo['rtEnd'] : stringTableStart ]

			# Parse the RT and String Table
			self.parseRelocationTable()
			stringTableLength = self.parseStringTable()
			if stringTableLength == -1:
				print 'Unable parse string table; ceasing file parsing.'
				return fileDataRetrieved
			
			# Separate out other file sections using the info gathered above
			self.stringTableData = self.data[ stringTableStart : stringTableStart + stringTableLength ]
			self.tailData = self.data[ stringTableStart + stringTableLength : ]
			self.data = self.data[ : self.headerInfo['rtStart'] ]

			# Parse the file's root/reference node tables (must be parsed after parsing the string table)
			self.parseNodeTables()

			# Organize the information parsed above
			self.evaluateStructs()
			self.separateNodeLists()

			# Get structure class hints on root structures
			self.hintRootClasses()

		return fileDataRetrieved

	def parseHeader( self ):

		""" All of the positional values obtained here are relative to the data section (-0x20 from the actual/absolute file offset). """

		try:
			filesize, rtStart, rtEntryCount, rootNodeCount, referenceNodeCount = struct.unpack( '>5I', self.headerData[:0x14] )
			rtEnd = rtStart + ( rtEntryCount * 4 )
			rootNodesEnd = rtEnd + ( rootNodeCount * 8 ) # Each root/reference node table entry is 8 bytes

			self.headerInfo = {
				'filesize': filesize,
				'rtStart': rtStart, # Also the size of the data block
				'rtEntryCount': rtEntryCount,
				'rootNodeCount': rootNodeCount,
				'referenceNodeCount': referenceNodeCount,
				'magicNumber': self.headerData[20:24].decode( 'ascii' ),
				'rtEnd': rtEnd,
				'rootNodesEnd': rootNodesEnd,
				'stringTableStart': rootNodesEnd + ( referenceNodeCount * 8 ), # Each root/reference node table entry is 8 bytes
			}

		except Exception as errorMessage:
			if showLogs:
				print 'Unable to parse the DAT file header of', self.path
				print errorMessage

	def parseRelocationTable( self ):

		""" Create a list of all pointer locations in the file, as well as a list of the offset values pointed to by those pointers,
			as described by the relocation table. Each RT entry is a 4-byte integer. """

		try:
			# Convert all entries as 4-byte ints (unpack returns a tuple, but we need a list in order to add to it later)
			unpackFormat = '>{}I'.format( self.headerInfo['rtEntryCount'] )
			self.pointerOffsets = list( struct.unpack(unpackFormat, self.rtData) )
			self.pointerValues = bytearray() # Will only be a bytearray temporarily, during this processing

			for offset in self.pointerOffsets:
				self.pointerValues.extend( self.data[offset:offset+4] )
			self.pointerValues = list( struct.unpack(unpackFormat, self.pointerValues) )

		except Exception as errorMessage:
			self.pointerOffsets = []
			self.pointerValues = []
			if showLogs:
				print 'Unable to parse the DAT file relocation table of', self.path
				print errorMessage

	def parseStringTable( self ):

		""" Creates a dictionary for the string table, where keys=dataSectionOffsets, and values=stringLabels. """

		try:
			stringTable = self.data[self.headerInfo['stringTableStart']:] # Can't separate this out beforehand, without knowing its length
			totalStrings = self.headerInfo['rootNodeCount'] + self.headerInfo['referenceNodeCount']

			self.stringDict = {}
			stringTableLength = 0
			strings = stringTable.split( b'\x00' )[:totalStrings] # End splicing eliminates an empty string, and/or extra additions at the end of the file.

			for stringBytes in strings:
				string = stringBytes.decode( 'ascii' ) # Convert the bytearray to a text string
				self.stringDict[stringTableLength] = string
				stringTableLength += len( string ) + 1 # +1 to account for null terminator

			return stringTableLength

		except Exception as errorMessage:
			self.stringDict = {}
			if showLogs:
				print "Unable to parse the DAT's string table!:\n\t", self.path
				print errorMessage
			return -1

	def getStringTableSize( self ):

		""" Need this method (rather than just doing 'header[filesize] - totalFilesize') because 
			there may be extra custom data added after the end of the file. """

		if not self.stringsNeedRebuilding:
			return len( self.stringTableData )

		# Start the size off by accounting for 1 byte for each null-byte terminator
		size = len( self.stringDict )

		for string in self.stringDict.values():
			size += len( string ) # The string is in ascii; 1 byte per character

		return size

	def parseNodeTables( self ):

		""" Creates two lists (for root/reference nodes) to define structure locations. 
			Both are a list of tuples of the form ( structOffset, string ), 
			where the string is from the file's string table. """

		try:
			rootNodes = []; referenceNodes = []
			nodePointerOffset = self.headerInfo['rtEnd']
			nodesTable = [ self.nodeTableData[i:i+8] for i in xrange(0, len(self.nodeTableData), 8) ] # separates the data into groups of 8 bytes

			for i, entry in enumerate( nodesTable ):
				structOffset, stringOffset = struct.unpack( '>II', entry ) # Struct offset is the first 4 bytes; string offset is the second 4 bytes
				string = self.stringDict[ stringOffset ]

				# Store the node
				if i < self.headerInfo['rootNodeCount']: rootNodes.append( ( structOffset, string ) )
				else: referenceNodes.append( ( structOffset, string ) )

				# Remember the pointer and struct offsets (these aren't included in the RT!)
				self.pointerOffsets.append( nodePointerOffset ) # Absolute file offset for this node's pointer
				self.pointerValues.append( structOffset )

				nodePointerOffset += 8

			rootNodes.sort()
			referenceNodes.sort()

			self.rootNodes = rootNodes
			self.referenceNodes = referenceNodes

		except Exception as errorMessage:
			if showLogs:
				print "Unable to parse the DAT's root/reference nodes table!:\n\t", self.path
				print errorMessage

	def evaluateStructs( self ):

		""" Sorts the lists of pointer offsets and pointer values (by offset), and creates a sorted list 
			of all [unique] structure offsets in the data section, which includes offsets for the file 
			header (at -0x20), RT, root nodes table, reference nodes table (if present), and string table. """

		try:
			# Sort the lists of pointers and their values found in the RT and node tables
			self.pointers = sorted( zip(self.pointerOffsets, self.pointerValues) ) # Creates a sorted list of (pointerOffset, pointerValue) tuples

			# Create a list of unique structure offsets, sorted by file order.
			# The data section's primary assumption is that no pointer points into the middle of a struct, and thus must be to the start of one.
			self.structureOffsets = [ -0x20 ] # For the file header. Negative, not 0, because these offsets are relative to the start of the data section
			self.structureOffsets.extend( Set(self.pointerValues) ) # Using a set to eliminate redundancies
			self.structureOffsets.append( self.headerInfo['rtStart'] )
			self.structureOffsets.append( self.headerInfo['rtEnd'] ) # For the root nodes table
			if self.headerInfo['rootNodesEnd'] != self.headerInfo['stringTableStart']: # Might not have a reference nodes table
				self.structureOffsets.append( self.headerInfo['rootNodesEnd'] ) # For the reference nodes table
			self.structureOffsets.append( self.headerInfo['stringTableStart'] )
			self.structureOffsets.sort()

			# The following helps provide an efficient means for determining the structure owner of an offset (used by the .getPointerOwner() function)
			self.structStartRanges = zip( self.structureOffsets, self.structureOffsets[1:] )

		except Exception as errorMessage:
			if showLogs:
				print "Unable to evaluate the file's structs;"
				print errorMessage

	def separateNodeLists( self ):

		""" Separates the node lists into root structures (highest level entry into data section) or labels (those used just for identification). 
			This works by checking whether a structure pointed to by a root/ref node also has another pointer to it within the data section. """

		try:
			# tic = time.clock()

			# Get a list of the pointer values in the data section (structure offsets)
			self.rootStructNodes = []; self.rootLabelNodes = []; self.refStructNodes = []; self.refLabelNodes = []
			totalNodePointers = self.headerInfo['rootNodeCount'] + self.headerInfo['referenceNodeCount']
			dataSectionPointerValues = self.pointerValues[:-totalNodePointers] # Excludes pointer values from nodes table
			# todo: test performance of making above variable a set for this function

			# For each node, check if there's already a pointer value (pointing to its struct) somewhere else in the data section
			for entry in self.rootNodes: # Each entry is a ( structOffset, string ) tuple pair
				if entry[0] in dataSectionPointerValues:
					self.rootLabelNodes.append( entry )
				else:
					self.rootStructNodes.append( entry )

			for entry in self.referenceNodes:
				if entry[0] in dataSectionPointerValues:
					self.refLabelNodes.append( entry )
				else:
					self.refStructNodes.append( entry )

			# toc = time.clock()
			# print '\ttime to separate node lists:', toc-tic
			# print 'dspv:', len( dataSectionPointerValues )

		except Exception as errorMessage:
			if showLogs:
				print "Unable to separate the DAT's root/reference nodes lists!:\n\t", self.path
				print errorMessage

	def parseDataSection( self ):

		""" This method uses the root and reference nodes to identify structures 
			within the data section of the DAT file. Some root/reference nodes point
			to the start of a hierarchical branch into the file, while others simply
			serve as labels for parts of branches or for specific structures. """

		hI = self.headerInfo

		try:

			for i, ( structOffset, _ ) in enumerate( self.rootNodes + self.referenceNodes ):
				# Determine the parent root/ref node table offset
				if i < hI['rootNodeCount']: parentOffset = hI['rtEnd']
				else: parentOffset = hI['rootNodesEnd']

				# Get the target struct if it has already been initialized
				childStruct = self.structs.get( structOffset, None )

				if childStruct and not childStruct.__class__ == str:
					""" This struct/branch has already been created! Which likely means this is part of another structure 
						branch, and this root or reference node association must just be a label for the structure.
						So just update the target structure's parent structs list with this item. """
					childStruct.parents.add( parentOffset )

				else: # Create the new struct
					childStruct = self.getStruct( structOffset, parentOffset, (2, 0) ) # Using this rather than the factory so we can still process hints
				
				childStruct.initDescendants()

			# Identify and group orphan structures. (Some orphans will be recognized/added by the struct initialization functions.)
			dataSectionStructureOffsets = Set( self.structureOffsets ).difference( [-0x20, hI['rtStart'], hI['rtEnd'], hI['rootNodesEnd'], hI['stringTableStart']] )
			self.orphanStructures = dataSectionStructureOffsets.difference( self.structs.keys() )
			
		except Exception as errorMessage:
			if showLogs:
				print 'Unable to parse the DAT file data section of', self.path
				print errorMessage

	def hintRootClasses( self ):

		""" Adds class hints for structures with known root/reference node labels. This is the same hinting procedure enacted by structure
			classes' "provideChildHints" method, but done on file load in order to identify top-level structures. """

		for structOffset, string in self.rootNodes:
			specificStructClassFound = hsdStructures.SpecificStructureClasses.get( string )
			if specificStructClassFound:
				self.structs[structOffset] = specificStructClassFound.__name__

	def getStructLength( self, targetStructOffset ):

		""" The value returned is a count in bytes.
			The premise of this method is that pointers (what structureOffsets is based on) should 
			always point to the beginning of a structure, and never into the middle of one. 
			However, padding which follows the struct to preserve alignment will be included. """

		# Look for the first file offset pointer value following this struct's start offset
		for offset in self.structureOffsets:

			if offset > targetStructOffset:
				structLength = offset - targetStructOffset
				break

		else: # The loop above did not break; no struct start offsets found beyond this offset. So the struct must end at the RT
			print 'ad-hoc struct detected in tail data (after string table); unable to calculate length for struct', hex(0x20+targetStructOffset)
			structLength = self.headerInfo['filesize'] - 0x20 - targetStructOffset

		return structLength

	def getStructLabel( self, dataSectionOffset ):

		""" Returns a struct's name/label, found in the String Table. """

		for structOffset, string in self.rootNodes + self.referenceNodes:
			if structOffset == dataSectionOffset: return string
		else: # The loop above didn't return; no match was found
			return ''

	def getPointerOwner( self, pointerOffset, offsetOnly=False ):

		""" Returns the offset of the structure which owns/contains a given pointer (or a given offset).
			This includes 'structures' such as the relocation table, root/reference node tables, and the string table. 
			If offsetOnly is True, the returned item is an int, and if it's False, the returned item is a structure object. """
		
		for structOffset, nextStructOffset in self.structStartRanges:
			if pointerOffset >= structOffset and pointerOffset < nextStructOffset:
				structOwnerOffset = structOffset
				break
		else: # The above loop didn't break; the pointer is after the last structure
			structOwnerOffset = self.structureOffsets[-1]

		if offsetOnly:
			return structOwnerOffset
		else: # Get and return the structure which owns the found offset
			return self.getStruct( structOwnerOffset )

	def checkForOrphans( self, structure ):
		
		""" If a parent offset wasn't provided, check for parents. This is done so that 
			even if orphaned structs are somehow initialized, they're still found. 
			There shouldn't be any need to check initialized data blocks, which must've
			had a parent in order to have a class hint, which leads to their creation. """

		structure.getParents( True )

		if not structure.parents:
			print 'orphan found (no parents);', hex( 0x20 + structure.offset )
			self.orphanStructures.add( structure.offset )

		elif len( structure.parents ) == 1 and structure.offset in structure.parents:
			print 'orphan found (self referencing);', hex( 0x20 + structure.offset )
			self.orphanStructures.add( structure.offset )

	def getStruct( self, structOffset, parentOffset=-1, structDepth=None ):

		""" The 'lazy' method for getting a structure. Uses multiple methods, and should return 
			some kind of structure class in all cases (resorting to a generic one if need be). """

		# Attempt to get an existing struct first
		structure = self.structs.get( structOffset, None )

		# Check if the object is an instantiated object, or just a string hint (indicating what the struct should be)
		if structure and isinstance( structure, str ):
			newStructClass = getattr( sys.modules[hsdStructures.__name__], structure, None ) # Changes a string into a class by that name

			if not newStructClass: # Unable to find a structure by that name
				print 'Unable to find a structure class of', structure
				structure = None # We'll let the structure factory handle this

			elif issubclass( newStructClass, hsdStructures.DataBlock ):
				#print 'creating new data block from', structure, 'hint for Struct', hex(0x20+structOffset)
				structure = self.initDataBlock( newStructClass, structOffset, parentOffset, structDepth )

			else:
				#print 'Struct', hex(0x20+structOffset), 'insinuated to be', structure, 'attempting to init specifically'
				structure = self.initSpecificStruct( newStructClass, structOffset, parentOffset, structDepth )

		if not structure: # If there was a hint, it may have been bad (above initialization failed)
			structure = self.structureFactory( structOffset, parentOffset, structDepth )

		return structure

	def structureFactory( self, structOffset, parentOffset=-1, structDepth=None ):

		""" This is a factory method to determine what kind of structure is at a given offset, 
			and instantiate the respective class for that particular structure. 
			If a structure class/type cannot be determined, a general one will be created. 
			The resulting behavior is similar to getStruct(), while ignoring structure hints. """

		# If the requested struct has already been created, return that
		existingStruct = self.structs.get( structOffset, None )
		if existingStruct and not existingStruct.__class__ == str: # If it's a string, it's a class hint
			return existingStruct

		# Validation; make sure a struct begins at the given offset
		elif structOffset not in self.structureOffsets:
			print 'Unable to create a struct object; invalid offset given:', hex(0x20 + structOffset)
			return None

		# Get parent struct offsets, to attempt to use them to determine this struct 
		# Try to get a parent struct to help with identification
		# if parentOffset != -1:
		# 	parents = Set( [parentOffset] )
		# else:
		# 	# This is a basic methodology and will get [previous] siblings as well.
		# 	parents = Set()
		# 	for pointerOffset, pointerValue in self.pointers:
		# 		if structOffset == pointerValue:
		# 			# The matched pointerOffset points to this structure; get the structure that owns this pointer
		# 			parents.add( self.getPointerOwner(pointerOffset).offset )
		# parents.difference_update( [self.headerInfo['rtEnd'], self.headerInfo['rootNodesEnd']] ) # Remove instance of the root/reference node if present

		# Get information on this struct
		deducedStructLength = self.getStructLength( structOffset ) # May include padding
		if deducedStructLength < 0:
			print 'Unable to create a struct object; unable to get a struct length for', hex(0x20 + structOffset)
			return None

		# Look at the available structures, and determine whether this structure matches any of them
		for structClass in hsdStructures.CommonStructureClasses + hsdStructures.AnimationStructureClasses:

			newStructObject = structClass( self, structOffset, parentOffset, structDepth )

			if newStructObject.validated( deducedStructLength=deducedStructLength ): break

		else: # The loop above didn't break; no structure match found
			# Use the base arbitrary class, which will work for any struct
			newStructObject = hsdStructures.structBase( self, structOffset, parentOffset, structDepth )

			newStructObject.data = self.data[ structOffset : structOffset+deducedStructLength ]
			newStructObject.formatting = '>' + 'I' * ( deducedStructLength / 4 ) # Assume a basic formatting if this is an unknown struct
			newStructObject.fields = ()
			newStructObject.length = deducedStructLength
			newStructObject.padding = 0

		# Add this struct to the DAT's structure dictionary
		self.structs[structOffset] = newStructObject

		# Ensure that even if orphaned structs are somehow initialized, they're still found.
		if not newStructObject.parents:
			self.checkForOrphans( newStructObject )

		return newStructObject

	def initGenericStruct( self, offset, parentOffset=-1, structDepth=None, deducedStructLength=-1 ):

		if deducedStructLength == -1:
			deducedStructLength = self.getStructLength( offset ) # This length will include any padding too

		newStructObject = hsdStructures.structBase( self, offset, parentOffset, structDepth )

		newStructObject.data = self.data[ offset : offset+deducedStructLength ]
		newStructObject.formatting = '>' + 'I' * ( deducedStructLength / 4 ) # Assume a basic formatting if this is an unknown struct
		newStructObject.fields = ()
		newStructObject.length = deducedStructLength
		newStructObject.padding = 0

		# Add this struct to the DAT's structure dictionary
		self.structs[offset] = newStructObject

		# Ensure that even if orphaned structs are somehow initialized, they're still found.
		if not newStructObject.parents:
			self.checkForOrphans( newStructObject )

		return newStructObject

	def initSpecificStruct( self, newStructClass, offset, parentOffset=-1, structDepth=None, printWarnings=True ):

		""" Attempts to validate and initialize a structure as a specific class (if it doesn't already exist).
			If unable to do so, this method returns None. 
			Do not use this to initialize a generic (structBase) class. """

		# Perform some basic validation
		assert newStructClass != hsdStructures.structBase, 'Invalid "structBase" class provided for specific initialization.'
		assert offset in self.structureOffsets, 'Invalid offset given to initSpecificStruct (not in structure offsets): ' + hex(0x20+offset)

		# If the requested struct has already been created, return it
		hintPresent = False
		existingStruct = self.structs.get( offset, None )

		if existingStruct:
			if existingStruct.__class__ == str:
				hintPresent = True

			else: # A class instance was found (not a string hint)
				if existingStruct.__class__ == newStructClass:
					return existingStruct

				# If the existing struct is generic, allow it to be overridden by the new known/specific class
				elif existingStruct.__class__ == hsdStructures.structBase:
					pass
				
				else: # If the struct has already been initialized as something else, return None
					if printWarnings:
						print 'Attempted to initialize a {} for Struct 0x{:X}, but a {} already existed'.format( newStructClass.__name__, 0x20+offset, existingStruct.__class__.__name__)
					return None

		# Create the new structure
		try:
			newStructure = newStructClass( self, offset, parentOffset, structDepth )
		except Exception as err:
			print 'Unable to initSpecificStruct;', err
			return None

		# Validate it
		if not newStructure.validated():
			# Check if the hint provided actually suggested the class we just tried
			if hintPresent and existingStruct == newStructClass.__name__:
				del self.structs[offset] # Assume the hint is bad and remove it
				if printWarnings:
					print 'Failed to init hinted', newStructClass.__name__, 'for offset', hex(0x20+offset) + '; appears to have been a bad hint'
			elif printWarnings:
				print 'Failed to init', newStructure.__class__.__name__, 'for offset', hex(0x20+offset)

			return None

		# Valid struct of this class. Add it to the DAT's structure dictionary
		self.structs[offset] = newStructure

		# Ensure that even if orphaned structs are somehow initialized, they're still found.
		if not newStructure.parents:
			self.checkForOrphans( newStructure )

		return newStructure

	def initDataBlock( self, newDataClass, offset, parentOffset=-1, structDepth=None, dataLength=-1 ):

		""" Initializes a raw block of image/palette/etc. data without validation; these will have mostly 
			the same methods as a standard struct and can be handled similarly. """

		# If the requested struct has already been created, return it
		existingStruct = self.structs.get( offset, None )

		if existingStruct and not existingStruct.__class__ == str: # A class instance was found (not a string hint)
			if existingStruct.__class__ == newDataClass:
				return existingStruct

			# If the existing struct is generic, allow it to be overridden by the new known/specific class
			elif existingStruct.__class__ == hsdStructures.structBase:
				pass
			
			else: # If the struct has already been initialized as something else, return None
				print 'Attempted to initialize a {} for Struct 0x{:X}, but a {} already existed'.format( newDataClass.__name__, 0x20+offset, existingStruct.__class__.__name__)
				return None

		deducedStructLength = self.getStructLength( offset ) # This length will include any padding too
		newStructure = newDataClass( self, offset, parentOffset, structDepth )

		# Get the data length, if not provided; deterimined by a parent struct, if possible
		if dataLength == -1 and parentOffset != -1:
			if newDataClass == hsdStructures.ImageDataBlock:
				# Try to initialize an image data header, and get info from that
				imageDataHeader = self.initSpecificStruct( hsdStructures.ImageObjDesc, parentOffset )

				if imageDataHeader:
					width, height, imageType = imageDataHeader.getValues()[1:4]
					dataLength = hsdStructures.ImageDataBlock.getDataLength( width, height, imageType )

			elif newDataClass == hsdStructures.FrameDataBlock:
				# Try to initialize a parent frame object, and get info from that
				frameObj = self.initSpecificStruct( hsdStructures.FrameObjDesc, parentOffset )
				dataLength = frameObj.getValues( specificValue='Data_String_Length' )
				# print 'dataLength:', dataLength
				# print 'deducedStructLength:', deducedStructLength

		# Exact data length undetermined. Assume the full space before the next struct start.
		if dataLength == -1:
			dataLength = deducedStructLength

		# Add the final properties
		newStructure.data = self.data[ offset : offset+dataLength ]
		newStructure.formatting = '>' + 'I' * ( dataLength / 4 )
		newStructure.length = dataLength
		newStructure.padding = deducedStructLength - dataLength
		newStructure._siblingsChecked = True
		newStructure._childrenChecked = True

		# Add this struct to the DAT's structure dictionary
		self.structs[offset] = newStructure

		return newStructure

	# def findDataSectionRoot( self, offset ):

	# 	""" Seeks upwards through structures towards the first/root entry point into the data section, for the given offset. """

	# 	# Check if there's only one option
	# 	if len( self.rootStructNodes ) == 1 and len( self.refStructNodes ) == 0:
	# 		return self.rootStructNodes[0]
	# 	elif len( self.refStructNodes ) == 1 and len( self.rootStructNodes ) == 0:
	# 		return self.refStructNodes[0]

	# 	def getNextHigherRelative( offset ):
	# 		for pointerOffset, pointerValue in self.pointers:
	# 			if pointerValue == offset:
	# 				#assert pointerOffset < self.dat.headerInfo['rtEnd'], '.getImmediateParent() unable to find a data section parent for ' + hex(0x20+offset)
	# 				if pointerOffset > self.dat.headerInfo['rtEnd']

	# 				# Pointer found; get the structure that owns this pointer
	# 				parentOffset = self.dat.getPointerOwner( pointerOffset, offsetOnly=True )

	# 	# Multiple options; we'll have to walk the branches
	# 	nextParentOffset = offset
	# 	while nextParentOffset not in ( self.dat.headerInfo['rtEnd'], self.dat.headerInfo['rootNodesEnd'] ):

	# def initBranchToTrunk( self, structOffset ):

	# 	""" Initializes the structure at the given offset, as well as the entire structure branch above it. 
	# 		This is done in reverse order (highest level root structure first) so that the last structure 
	# 		can be more accurately determined. """

	# 	# Get the closest upward relative/branch offset to this structure; either from an existing struct, or by scanning the file's pointers.
	# 	existingEntity = self.structs.get( structOffset )
	# 	if existingEntity not isinstance( existingEntity, (str, hsdStructures.structBase) ): # Found a known struct, not a hint or generic struct
	# 		parentOffset = existingEntity.getParents()
	# 	else:
	# 		for pointerOffset, pointerValue in self.pointers:
	# 			if pointerValue == structOffset:
	# 				parentOffset = self.getPointerOwner( pointerOffset )
	# 				break # For once, we don't care if this is a sibling

	# 	# See if a parent structure has been initialized as a known struct, and get it if it has
	# 	if parentOffset == self.headerInfo['rtEnd'] or parentOffset == self.headerInfo['rootNodesEnd']: # Reached the base of the trunk
	# 		rootStruct = self.structureFactory( structOffset, parentOffset, (2, 0) ) # todo: fix this if label checking is removed from this method (in favor of hints)

	def getData( self, dataOffset, dataLength=1 ):

		""" Gets file data from either the data section or tail data. The offset is 
			relative to the datasection (i.e. does not account for file header). """

		if dataOffset < len( self.data ):
			assert dataOffset + dataLength < len( self.data ), 'Unable to get all of the requested data. It bleeds into the RT!'
			return self.data[ dataOffset : dataOffset+dataLength ]

		else: # Need to get it from the tail data
			tailOffset = dataOffset - len( self.data ) - len( self.rtData ) - len( self.nodeTableData ) - len( self.stringTableData )
			assert tailOffset >= 0, 'Unable to get the requested data. It falls between the data and tail sections!'
			return self.tailData[ tailOffset : tailOffset+dataLength ]

	def getFullData( self ):

		""" Assembles all of the file's data groups from internal references, to get all of the latest data for the file. """

		if self.fileExt in ( 'bnr', 'dol' ):
			return self.data
		else:
			if self.headerNeedsRebuilding:
				hI = self.headerInfo
				self.headerData[:0x14] = struct.pack( '>5I', hI['filesize'], hI['rtStart'], hI['rtEntryCount'], hI['rootNodeCount'], hI['referenceNodeCount'] )
				self.headerNeedsRebuilding = False

			if self.rtNeedsRebuilding:
				rtEntryCount = self.headerInfo['rtEntryCount']
				self.rtData = struct.pack( '>{}I'.format(rtEntryCount), *self.pointerOffsets[:rtEntryCount] )
				self.rtNeedsRebuilding = False

			if self.nodesNeedRebuilding or self.stringsNeedRebuilding:
				self.rebuildNodeAndStringTables()

			return self.headerData + self.data + self.rtData + self.nodeTableData + self.stringTableData + self.tailData

	def rebuildNodeAndStringTables( self ):

		""" Rebuilds the root nodes table, reference nodes table, and string table. """

		self.stringTableData = bytearray()
		nodeValuesList = []

		self.rootNodes.sort()
		self.referenceNodes.sort()

		for structOffset, string in self.rootNodes + self.referenceNodes:
			# Collect values for this node to be encoded in the finished table
			nodeValuesList.extend( [structOffset, len(self.stringTableData)] )

			# Add the string for this node to the string table
			self.stringTableData.extend( string.encode('ascii') )
			self.stringTableData.append( 0 ) # Add a null terminator for this string

		# Encode both node tables together
		self.nodeTableData = struct.pack( '>{}I'.format(len(nodeValuesList)), *nodeValuesList )

		# Clear the flags indicating that these needed to be rebuilt
		self.nodesNeedRebuilding = False
		self.stringsNeedRebuilding = False

	def setData( self, dataOffset, newData ):

		""" Updates (replaces) data in either the data section or tail data. """

		if type( newData ) == int: # Just a single byte/integer value (0-255)
		 	assert newData >=0 and newData < 256, 'Invalid input to datFileObj.updateData(): ' + str(newData)
		 	dataLength = -1
		else:
			dataLength = len( newData )

		if dataOffset < len( self.data ):
			if dataLength == -1:
				self.data[dataOffset] = newData
			else:
				self.data[dataOffset:dataOffset+dataLength] = newData # This will also work for bytearrays of length 1

		else:
			tailOffset = dataOffset - len( self.data ) - len( self.rtData ) - len( self.nodeTableData ) - len( self.stringTableData )
			
			if dataLength == -1:
				self.tailData[tailOffset] = newData
			else:
				self.tailData[tailOffset:tailOffset+dataLength] = newData # This will also work for bytearrays of length 1

	def updateData( self, offset, newData, description='', trackChange=True ):

		""" This is a direct change to self.data itself, rather a struct. However, it will also update 
			any structs that have already been initialized for that location in the file. This method 
			will then also keep a record that this change was made. """

		# Perform a bit of validation on the input
		if type( newData ) == int: # Just a single byte/integer value (0-255)
		 	assert newData >= 0 and newData < 256, 'Invalid input to datFileObj.updateData(): ' + str(newData)
		 	dataLength = 1
		else:
			dataLength = len( newData )
		self.setData( offset, newData )

		# If a structure has been initialized that contains the modifications, update it too
		if self.fileExt not in ( 'bnr', 'dol' ):
			targetStruct = self.getPointerOwner( offset )
			if targetStruct and not isinstance( targetStruct, str ):
				# Pull new data for the structure
				targetStruct.data = self.getData( targetStruct.offset, targetStruct.length )

				# Update its values as well, as long as it's not a block of raw data
				if not issubclass( targetStruct.__class__, hsdStructures.DataBlock ):
					targetStruct.values = ()
					targetStruct.getValues()

		if trackChange: # Record these changes
			if self.fileExt in ( 'bnr', 'dol' ):
				adjustedOffset = offset
			else:
				adjustedOffset = 0x20 + offset # For typical DAT files

			# Create a description if one isn't provided. Amend it with e.g. ' at 0x1234'
			if not description:
				if dataLength == 1:
					description = 'Single byte updated'
				else:
					description = '0x{:X} bytes of data updated'.format( dataLength )
			description += ' at 0x{:X}.'.format( adjustedOffset )

			if description not in self.unsavedChanges:
				self.unsavedChanges.append( description )

	def updateStructValue( self, structure, valueIndex, newValue, description='' ):
		
		""" Performs a similar function as the updateData method. However, this requires a known structure to exist, 
			and makes the appropriate modifications through it first before updating self.data. """

		# Change the value in the struct
		structure.setValue( valueIndex, newValue )
		
		# Update the file's data with that of the modified structure
		structure.data = struct.pack( structure.formatting, *structure.values )
		self.setData( structure.offset, structure.data )
		
		# Record these changes
		if self.fileExt in ( 'bnr', 'dol' ):
			offset = structure.valueIndexToOffset( valueIndex )
		else:
			offset = 0x20 + structure.valueIndexToOffset( valueIndex ) # Accounts for file header in typical DAT files
		if not description:
			fieldName = structure.fields[valueIndex].replace( '_', ' ' )
			description = '{} modified for {}'.format( fieldName, structure.name )
		description += ' at 0x{:X}.'.format( offset )
		if description not in self.unsavedChanges:
			self.unsavedChanges.append( description )

	def updateFlag( self, structure, valueIndex, bitNumber, flagState ):
		
		""" Performs a similar function as the updateData method. However, this requires a known structure, 
			and makes the appropriate modifications through it first before updating self.data. """

		# Check if the flag even needs updating (if it's already set as desired)
		flagsValue = structure.getValues()[valueIndex]
		if flagState:
			if flagsValue & (1 << bitNumber): 
				#print 'Bit {} of {} flags already set!'.format( bitNumber, structure.name )
				return # Flag already set as desired
		elif not flagsValue & (1 << bitNumber): 
			#print 'Bit {} of {} flags already cleared!'.format( bitNumber, structure.name )
			return # Flag already clear as desired

		# Set or clear the flag, based on the desired flag state
		if flagState:
			structure.setFlag( valueIndex, bitNumber ) # Arguments are value index and bit number
		else:
			structure.clearFlag( valueIndex, bitNumber )

		# Update the file's data with that of the modified structure
		structure.data = struct.pack( structure.formatting, *structure.values )
		self.setData( structure.offset, structure.data )

		# Record these changes
		if self.fileExt in ( 'bnr', 'dol' ):
			offset = structure.valueIndexToOffset( valueIndex )
		else:
			offset = 0x20 + structure.valueIndexToOffset( valueIndex ) # For typical DAT files
		description = 'Flag modified for {} (bit {}) at 0x{:X}.'.format( structure.name, bitNumber, offset )
		if description not in self.unsavedChanges:
			self.unsavedChanges.append( description )

	def noChangesToBeSaved( self, programClosing ):

		""" Checks and returns whether there are any unsaved changes that the user would like to save.
			If there are any unsaved changes, this prompts the user on whether they would like to keep them, 
			and if they don't, the changes are discarded and this method then returns False. """

		noChangesNeedSaving = True

		if self.unsavedChanges:
			if programClosing: warning = "The changes below haven't been saved to the currently loaded file. Are you sure you want to close?\n\n"
			else: warning = 'The changes below will be forgotten if you change or reload the currently loaded file before saving. Are you sure you want to do this?\n\n'
			warning += '\n'.join( self.unsavedChanges )

			noChangesNeedSaving = tkMessageBox.askyesno( 'Unsaved Changes', warning )

		if noChangesNeedSaving: # Forget the past changes
			self.unsavedChanges = []

		return noChangesNeedSaving

	def removePointer( self, offset ):

		""" Removes a pointer from its structure and from the Relocation Table. 
			The offset argument is relative to the start of the data section, even if it's in tail data. """

		# Make sure this is a valid pointer offset, and get the index for this pointer's location and value
		try:
			pointerValueIndex = self.pointerOffsets.index( offset )
		except ValueError:
			print 'Invalid offset given to removePointer;', hex(0x20+offset), 'is not a valid pointer offset.'
		except Exception as err:
			print err

		# Update header values
		self.headerInfo['rtEntryCount'] -= 1
		self.headerInfo['rtEnd'] -= 4
		self.headerInfo['rootNodesEnd'] -= 4
		self.headerInfo['stringTableStart'] -= 4
		self.headerNeedsRebuilding = True

		# Remove the value from the Relocation Table and the various structure/pointer lists
		self.pointerOffsets.remove( offset )
		del self.pointerValues[pointerValueIndex]
		self.evaluateStructs() # Rebuilds the pointers tuple list and the structure offsets set
		self.rtNeedsRebuilding = True

		# Null the pointer in the file/structure data and structure values
		self.setData( offset, bytearray(4) ) # Bytearray initialized with 4 null bytes
		targetStruct = self.getPointerOwner( offset )
		if targetStruct and not isinstance( targetStruct, str ):
			# Update the structure's data
			targetStruct.data = self.data[ targetStruct.offset : targetStruct.offset+targetStruct.length ]

			# Update its values as well, as long as it's not a block of raw data
			if not issubclass( targetStruct.__class__, hsdStructures.DataBlock ):
				targetStruct.values = ()
				targetStruct.getValues()

		# Record this change
		description = 'Pointer removed at 0x{:X}.'.format( 0x20 + offset )
		self.unsavedChanges.append( description )

	def collapseDataSpace( self, collapseOffset, amount ):

		""" Erases data space, starting at the given offset, including pointers and structures (and their references) in the affected area. """

		# Perform some validation on the input
		if amount == 0: return
		elif collapseOffset > len( self.data ):
			if not self.tailData:
				print 'Invalid offset provided for collapse; offset is too large'
				return

			tailDataStart = self.headerInfo['stringTableStart'] + self.getStringTableSize()
			if collapseOffset < tailDataStart:
				print 'Invalid collapse offset provided; offset falls within RT, node tables, or string table'
				return
			elif collapseOffset + amount > self.headerInfo['filesize'] - 0x20:
				amount = self.headerInfo['filesize'] - 0x20 - collapseOffset
				print 'Collapse space falls outside of the range of the file! The amount to remove is being adjusted to', hex(amount)
		elif collapseOffset < len( self.data ) and collapseOffset + amount > len( self.data ):
			amount = len( self.data ) - collapseOffset
			print 'Collapse space overlaps into the Relocation Table! The amount to remove is being adjusted to', hex(amount)
			
		# Reduce the amount, if necessary, to preserve file alignment
		if amount < 0x20:
			print 'Collapse amount should be >= 0x20 bytes, to preserve file alignment.'
			return
		elif amount % 0x20 != 0:
			adjustment = amount % 0x20
			amount -= adjustment
			print 'Collapse amount decreased by', hex(adjustment) + ', to preserve file alignment'

			if amount == 0: return

		# Make sure we're only removing space from one structure
		targetStructOffset = self.getPointerOwner( collapseOffset, offsetOnly=True )
		structSize = self.getStructLength( targetStructOffset )
		if collapseOffset + amount > targetStructOffset + structSize:
			print 'Unable to collapse file space. Amount is greater than structure size'
			return

		print 'Collapsing file data at', hex(0x20+collapseOffset), 'by', hex(amount)

		# Adjust the values in the pointer offset and structure offset lists (these changes are later saved to the Relocation table)
		rtEntryCount = self.headerInfo['rtEntryCount']
		pointersToRemove = [] # Must be removed after the following loop (since we're iterating over one of the lists these are in)
		for i, (pointerOffset, pointerValue) in enumerate( self.pointers ):
			# Reduce affected pointer offset values
			if pointerOffset >= collapseOffset and pointerOffset < collapseOffset + amount: # This falls within the space to be removed
				pointersToRemove.append( i )
				continue

			elif pointerOffset > collapseOffset: # These offsets need to be reduced
				self.pointerOffsets[i] = pointerOffset - amount

			# If the place that the pointer points to is after the space change, update the pointer value accordingly
			if pointerValue >= collapseOffset and pointerValue < collapseOffset + amount: # This points to within the space to be removed
				pointersToRemove.append( i )

				# Null the pointer value in the file and structure data
				if i < rtEntryCount: # Still within the data section; not looking at node table pointers
					print 'Nullifying pointer at', hex( 0x20+pointerOffset ), 'as it pointed into the area to be removed'
					self.setData( pointerOffset, bytearray(4) ) # Bytearray initialized with 4 null bytes

			elif pointerValue > collapseOffset:
				newPointerValue = pointerValue - amount
				self.pointerValues[i] = newPointerValue

				# Update the pointer value in the file and structure data
				if i < rtEntryCount: # Still within the data section; not looking at node table pointers
					print 'Set pointer value at', hex(0x20+pointerOffset), 'to', hex(newPointerValue)
					self.setData( pointerOffset, struct.pack('>I', newPointerValue) )

		# Remove pointers and their offsets from their respective lists, and remove structs that fall in the area to be removed
		pointersToRemove.sort( reverse=True ) # Needed so we don't start removing the wrong indices after the first
		if pointersToRemove:
			print 'Removing', len(pointersToRemove), 'pointers:'
			print [ hex(0x20+self.pointerOffsets[i]-amount) for i in pointersToRemove ]
		for pointerIndex in pointersToRemove:
			del self.pointerOffsets[pointerIndex]
			del self.pointerValues[pointerIndex]
		self.structs = {}
		self.hintRootClasses()
		self.rtNeedsRebuilding = True

		# Update root nodes
		newRootNodes = []
		nodesModified = False
		for structOffset, string in self.rootNodes:
			# Collect unaffected nodes
			if structOffset < collapseOffset:
				newRootNodes.append( (structOffset, string) )
			# Skip nodes that point to within the affected area, since they no longer point to anything
			elif structOffset >= collapseOffset and structOffset < collapseOffset + amount:
				self.stringDict = { key: val for key, val in self.stringDict.items() if val != string }
				print 'Removing root node,', string
				nodesModified = True
			else: # Struct offset is past the affected area; just needs to be reduced
				newRootNodes.append( (structOffset - amount, string) )
				nodesModified = True
		if nodesModified:
			print 'Modified root nodes'
			self.rootNodes = newRootNodes
			self.nodesNeedRebuilding = True

		# Update reference nodes
		newRefNodes = []
		nodesModified = False
		for structOffset, string in self.referenceNodes:
			# Collect unaffected nodes
			if structOffset < collapseOffset:
				newRefNodes.append( (structOffset, string) )
			# Skip nodes that point to within the affected area, since they no longer point to anything
			elif structOffset >= collapseOffset and structOffset < collapseOffset + amount:
				self.stringDict = { key: val for key, val in self.stringDict.items() if val != string }
				print 'Removing reference node,', string
				nodesModified = True
			else: # Struct offset is past the affected area; just needs to be reduced
				newRefNodes.append( (structOffset - amount, string) )
				nodesModified = True
		if nodesModified:
			print 'Modified reference nodes'
			self.referenceNodes = newRefNodes
			self.nodesNeedRebuilding = True

		# Rebuild the root/ref struct/label node lists
		if self.nodesNeedRebuilding:
			self.separateNodeLists()

		# Update header values
		rtSizeReduction = len( pointersToRemove ) * 4
		rootNodesSize = len( self.rootNodes ) * 8
		refNodesSize = len( self.referenceNodes ) * 8
		self.headerInfo['filesize'] -= ( amount + rtSizeReduction )
		self.headerInfo['rtStart'] -= amount
		self.headerInfo['rtEntryCount'] -= len( pointersToRemove )
		self.headerInfo['rootNodeCount'] = len( self.rootNodes )
		self.headerInfo['referenceNodeCount'] = len( self.referenceNodes )
		rtEnd = self.headerInfo['rtStart'] + ( self.headerInfo['rtEntryCount'] * 4 )
		self.headerInfo['rtEnd'] = rtEnd
		self.headerInfo['rootNodesEnd'] = rtEnd + rootNodesSize
		self.headerInfo['stringTableStart'] = rtEnd + rootNodesSize + refNodesSize
		self.headerNeedsRebuilding = True

		# Rebuild the and structure offsets and pointers lists
		self.evaluateStructs()

		# Remove the data
		if collapseOffset < len( self.data ):
			self.data = self.data[ :collapseOffset ] + self.data[ collapseOffset+amount: ]
		else: # Falls within tail data
			self.tailData = self.tailData[ :collapseOffset ] + self.tailData[ collapseOffset+amount: ]

		# Record this change
		description = '0x{:X} bytes of data removed at 0x{:X}.'.format( amount, 0x20 + collapseOffset )
		self.unsavedChanges.append( description )

	def extendDataSpace( self, extensionOffset, amount ):

		""" Increases the amount of file/data space at the given offset. """

		# Perform some validation on the input
		if amount == 0: return
		elif extensionOffset > len( self.data ):
			if not self.tailData:
				print 'Invalid offset provided for file extension; offset is too large'
				return

			tailDataStart = self.headerInfo['stringTableStart'] + self.getStringTableSize()
			if extensionOffset < tailDataStart:
				print 'Invalid extension offset provided; offset falls within RT, node tables, or string table'
				return

		# Adjust the amount, if necessary, to preserve file alignment (round up)
		if amount % 0x20 != 0:
			adjustment = 0x20 - ( amount % 0x20 )
			amount += adjustment
			print 'Exension amount increased by', hex(adjustment) + ', to preserve file alignment'

		# Adjust the values in the pointer offset and structure offset lists (these changes are later saved to the Relocation table)
		rtEntryCount = self.headerInfo['rtEntryCount']
		for i, (pointerOffset, pointerValue) in enumerate( self.pointers ):
			# Increase affected pointer offset values
			if pointerOffset >= extensionOffset:
				self.pointerOffsets[i] = pointerOffset + amount

			# If the place that the pointer points to is after the space change, update the pointer value accordingly
			if pointerValue >= extensionOffset:
				newPointerValue = pointerValue + amount
				self.pointerValues[i] = newPointerValue

				# Update the pointer value in the file and structure data
				if i < rtEntryCount: # Still within the data section; not looking at node table pointers
					print 'Set pointer value at', hex(0x20+pointerOffset), 'to', hex(newPointerValue)
					self.setData( pointerOffset, struct.pack('>I', newPointerValue) )
		self.structs = {}
		self.hintRootClasses()
		self.rtNeedsRebuilding = True

		# Update root nodes
		newRootNodes = []
		nodesModified = False
		for structOffset, stringOffset in self.rootNodes:
			# Collect unaffected nodes
			if structOffset < extensionOffset:
				newRootNodes.append( (structOffset, stringOffset) )
			else: # Struct offset is past the affected area; needs to be increased
				newRootNodes.append( (structOffset + amount, stringOffset) )
				nodesModified = True
		if nodesModified:
			print 'Modified root nodes'
			self.rootNodes = newRootNodes
			self.nodesNeedRebuilding = True

		# Update reference nodes
		newRefNodes = []
		nodesModified = False
		for structOffset, stringOffset in self.referenceNodes:
			# Collect unaffected nodes
			if structOffset < extensionOffset:
				newRefNodes.append( (structOffset, stringOffset) )
			else: # Struct offset is past the affected area; needs to be reduced
				newRefNodes.append( (structOffset + amount, stringOffset) )
				nodesModified = True
		if nodesModified:
			print 'Modified reference nodes'
			self.referenceNodes = newRefNodes
			self.nodesNeedRebuilding = True

		# Rebuild the root/ref struct/label node lists
		if self.nodesNeedRebuilding:
			self.separateNodeLists()

		# Update header values
		self.headerInfo['filesize'] += amount
		self.headerInfo['rtStart'] += amount
		self.headerInfo['rtEnd'] += amount
		self.headerInfo['rootNodesEnd'] += amount
		self.headerInfo['stringTableStart'] += amount
		self.headerNeedsRebuilding = True

		# Rebuild the and structure offsets and pointers lists
		self.evaluateStructs()

		# Add the data space
		newBytes = bytearray( amount )
		if extensionOffset < len( self.data ):
			self.data = self.data[ :extensionOffset ] + newBytes + self.data[ extensionOffset: ]
		else: # Falls within tail data
			self.tailData = self.tailData[ :extensionOffset ] + newBytes + self.tailData[ extensionOffset: ]

		# Record this change
		description = '0x{:X} bytes of data added at 0x{:X}.'.format( amount, 0x20 + extensionOffset )
		self.unsavedChanges.append( description )