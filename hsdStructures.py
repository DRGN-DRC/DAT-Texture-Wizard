#!/usr/bin/python
# This file's encoding: UTF-8, so that non-ASCII characters can be used in strings.

				# ======================================== #
			   # | ~ - [  Written by Durgan (DRGN)   ]- ~ | #
				# \        Feb, 2019; Version 2.4        / #
				   # ================================== #

# DTW's Structural Analysis tab or the following thread/post are useful for more details on structures:
# 		https://smashboards.com/threads/melee-dat-format.292603/post-21913374

import struct
import inspect
import os, sys
import time, math
import tkMessageBox

from sets import Set
from collections import OrderedDict
from itertools import izip, izip_longest

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


					# = ---------------------------------------------- = #
					#  [   HSD Internal File Structure Base Classes   ]  #
					# = ---------------------------------------------- = #

class structBase( object ):

	""" Represents an abstract structure within a HAL DAT file. 

		Each structure keeps a reference to its host dat file, 
		referring to it for information on itself and other structs. """

	# __slots__ = ( 'dat', 'offset', 'data', 'name', 'label', 'fields', 'length', 'entryCount', 'formatting',
	# 			  'parents', 'siblings', 'children', 'values', 'branchSize', 'childClassIdentities',
	# 			  '_parentsChecked', '_siblingsChecked', '_childrenChecked', '_branchInitialized' )

	def __init__( self, datSource, dataSectionOffset, parentOffset=-1, structDepth=None ):

		self.dat 			= datSource					# Host DAT File object
		self.offset 		= dataSectionOffset
		self.data			= None
		self.name 			= 'Struct ' + uHex( 0x20 + dataSectionOffset )
		self.label 			= datSource.getStructLabel( dataSectionOffset ) # From the DAT's string table
		self.fields			= ()
		self.length			= -1
		self.entryCount 	= -1					# Used with array and table structures
		self.formatting		= ''
		self.parents 		= Set()					# Set of integers (offsets of other structs)
		self.siblings 		= [] 					# List of integers (offsets of other structs)
		self.children 		= [] 					# List of integers (offsets of other structs)
		self.values 		= () 					# Actual decoded values (ints/floats/etc) of the struct's data
		self.branchSize 	= -1
		self.childClassIdentities = {}

		self._parentsChecked = False
		self._siblingsChecked = False
		self._childrenChecked = False
		self._branchInitialized = False
		#self.changesNeedSaving = False				# Indicates that some of the decoded values have been changed

		# Determine the structure's file depth (x, y) tuple, if possible. 
		#		x = how "deep" into the file (the file header is first, at 0), 
		# 		y = sibling index
		self.structDepthQuickCheck( parentOffset, structDepth ) # Also sets parents

	def validated( self, provideChildHints=True, deducedStructLength=-1 ):

		""" This method attempts to test sequential data against the format of a known 
			structure, validating whether or not it is actually the expected struct. 
			Primarily, it checks that the struct sizes are not too mismatched (there may be 
			padding thrown in, making a struct appear larger than it is), and validates pointers. 

			This function will also read and save the data (unpacking it to 'values') to the 
			struct object and set the following struct attributes: data, values, padding """

		if not self.fields: return False
		skipValuesValidation = False

		if deducedStructLength == -1:
			deducedStructLength = self.dat.getStructLength( self.offset ) # This length will include any padding too

		# Make sure this proposed struct has enough data (is long enough that it could match)
		if deducedStructLength < self.length or deducedStructLength > self.length + 0x20: # Expecting that there is never more that 0x20 bytes of padding
			return False

		# Separate the actual struct data from any padding, and perform some basic validation
		structData = self.dat.getData( self.offset, deducedStructLength )
		paddingData = structData[ self.offset + self.length:]
		structData = structData[:self.length] # Trim off the padding
		if not any( structData ):
			# Check if there's a class hint for this struct
			existingEntity = self.dat.structs.get( self.offset, None )

			if existingEntity == self: # Presumably, this has already been validated; continue with the rest of this method just in case anything needs updating
				skipValuesValidation = True
			elif isinstance( existingEntity, str ) and existingEntity == self.__class__.__name__:
				# If there's a class hint that matches this struct class, assume this is correct (since we can't use the values to determine it).
				skipValuesValidation = True
			else:
				return False # Assume it's an unknown structure
		if any( paddingData ): return False # If values are found in the padding, it's probably not padding (and thus it's an unknown structure)

		# Invalidate based on the expectation of children
		if not self.childClassIdentities and self.hasChildren():
			print 'Invalidating Struct ', hex(0x20+self.offset), 'as', self.__class__, 'since it has children'
			return False

		try:
			isValid = True
			fieldOffset = self.offset
			self.nullPointers = []
			fieldValues = struct.unpack( self.formatting, structData )

			# See if a sibling can be initialized with the same class. Check for a 'Next_' field marker, indicating a sibling struct pointer
			# for siblingFieldIndex, field in enumerate( self.fields ):
			# 	if field.startswith( 'Next_' ):
			# 		if self.valueIndexToOffset( siblingFieldIndex ) in self.dat.pointerOffsets: # Valid pointer
			# 			if not self.dat.initSpecificStruct( self.__class__, fieldValues[siblingFieldIndex], printWarnings=True ):
			# 				return False
			# 		break
			# else: # Loop didn't break; 'Next_' field not found
			# 	self._siblingsChecked = True

			if not skipValuesValidation:
				# Name pointers are always null (except with some custom structs :/)
				# if self.fields[0] == 'Name_Pointer' and fieldValues[0] != 0: 
				# 	#print 'disqualifying', self.name, 'as', self.__class__.__name__, 'due to populated Name_Pointer'
				# 	return False

				# Validate specific fields based on the expected type of data
				for i, fieldFormat in enumerate( self.formatting[1:] ): # Skips the endianess indicator

					if self.fields[i] == 'Padding' and fieldValues[i] != 0:
						print 'Disqualifying {} as {} due to non-empty padding at {}: {}'.format( self.name, self.__class__.__name__, self.valueIndexToOffset(i), hex(fieldValues[i]) )
						isValid = False
						break

					elif fieldFormat == '?': # Bools
						if fieldValues[i] not in ( 0, 1 ): # Should only be a 1 or 0
							isValid = False
							break

						fieldOffset += 1

					elif fieldFormat == 'b': # Signed Character (1 byte)
						fieldOffset += 1

					elif fieldFormat == 'B': # Unsigned Character (1 byte)
						fieldOffset += 1

					elif fieldFormat == 'h': # Signed Short (halfword)
						fieldOffset += 2

					elif fieldFormat == 'H': # Unsigned Short (halfword)
						fieldOffset += 2

					elif fieldFormat == 'i': # Signed Int
						fieldOffset += 4

					elif fieldFormat == 'I': # Unsigned Int
						# If the class for this struct identifies this value as a pointer, 
						# then it should be 0 or a valid starting offset of another struct.
						fileSaysItsAPointer = ( fieldOffset in self.dat.pointerOffsets ) # RT may include pointers of value 0
						classSaysItsAPointer = self.fields[i].endswith( '_Pointer' )

						if fileSaysItsAPointer:
							if not classSaysItsAPointer:
								isValid = False
								break
						elif classSaysItsAPointer:
							if fieldValues[i] == 0:
								self.nullPointers.append( i ) # Don't want to add a class hint for these!
							elif self.fields[i] != 'Name_Pointer': # Some custom structures may have improperly modified the name pointer. :/ Ignore those.
								isValid = False
								break

						fieldOffset += 4

					elif fieldFormat == 'f': # Signed Float
						fieldOffset += 4

					else:
						raise ValueError( 'Unrecognized field formatting: ' + fieldFormat )

		except Exception as err:
			print err
			return False

		if isValid:
			self.data = structData
			self.values = fieldValues
			self.padding = deducedStructLength - self.length

			if provideChildHints: # This should be false by all 'super().validation' calls, so we don't add hints prematurely
				self.provideChildHints()

		return isValid

	def provideChildHints( self ):
		# Add hints for what this structure's child structs are
		for valueIndex, classIdentity in self.childClassIdentities.items():
			if valueIndex in self.nullPointers: continue
			childStructOffset = self.values[valueIndex]

			if childStructOffset not in self.dat.structs:
				self.dat.structs[childStructOffset] = classIdentity

	def getValues( self, specificValue='' ):

		""" Unpacks the data for this structure, according to the struct's formatting.
			Only unpacks on the first call (returns the same data after that). Returns a tuple. """

		if not self.values:
			self.values = struct.unpack( self.formatting, self.data[:self.length] )

		if not specificValue:
			return self.values

		# Perform some validation on the input
		elif not self.fields:
			print 'Unable to get a specific value; struct lacks known fields.'
			return None
		elif specificValue not in self.fields:
			print 'Unable to get a specific value; field name not found.'
			return None

		# Get a specific value by field name
		else: 
			fieldIndex = self.fields.index( specificValue )
			return self.values[fieldIndex]

	def getAnyDataSectionParent( self ):

		""" Only looks for one arbitrary parent offset, so this can be faster than getParents(). """

		if self.parents:
			# Remove references of the root or reference node tables, and get an arbitrary item from the set
			dataSectionSectionParents = self.parents.difference( [self.dat.headerInfo['rtEnd'], self.dat.headerInfo['rootNodesEnd']] ) # Won't modify .parents

			if dataSectionSectionParents:
				return next( iter(dataSectionSectionParents) )

		# Couldn't find a suitable existing parent above, so perform a new check on the data section pointers directly
		parents = Set()
		for pointerOffset, pointerValue in self.dat.pointers:
			# Look for any pointers that point to this structure
			if pointerValue == self.offset:
				assert pointerOffset < self.dat.headerInfo['rtStart'], 'Unable to find any data section parent for ' + self.name

				# Pointer found; get the structure that owns this pointer
				parentOffset = self.dat.getPointerOwner( pointerOffset, offsetOnly=True )

				if self.isSibling( parentOffset ):
					parentStruct = self.dat.getStruct( parentOffset )
					grandparentStructOffsets = parentStruct.getParents()

					while True:
						# May have multiple parents; check if any of them are a sibling (want to follow that path)
						for grandparentOffset in grandparentStructOffsets:
							if parentStruct.isSibling( grandparentOffset ):
								parentStruct = self.dat.structs[grandparentOffset]
								grandparentStructOffsets = parentStruct.getParents()
								break
						else: # Above loop didn't break; no more siblings found
							break # Out of the while loop

					parents.add( next(iter( grandparentStructOffsets )) )

				else:
					parents.add( parentOffset )

				break
		
		# Remove references of the root or reference node tables, and get an arbitrary item from the set
		dataSectionSectionParents = parents.difference( [self.dat.headerInfo['rtEnd'], self.dat.headerInfo['rootNodesEnd']] )
		assert dataSectionSectionParents, 'The only parent(s) found for {} were root/ref nodes: {}'.format( self.name, [hex(0x20+o) for o in parents] )

		return next( iter(dataSectionSectionParents) )

	def getParents( self, includeNodeTables=False ):

		""" Finds the offsets of all [non-sibling] structures that point to this structure.
			May include root and reference node table offsets. """

		if not self._parentsChecked:
			self.parents = Set()

			for pointerOffset, pointerValue in self.dat.pointers:

				# Look for any pointers that point to this structure
				if pointerValue == self.offset:
					# Pointer found; get the structure that owns this pointer
					parentOffset = self.dat.getPointerOwner( pointerOffset, offsetOnly=True )

					if self.isSibling( parentOffset ):
						parentStruct = self.dat.getStruct( parentOffset )
						grandparentStructOffsets = parentStruct.getParents()

						# Make sure this isn't a sibling; seek through references until the actual parent is found
						foundAnotherSibling = True
						while foundAnotherSibling:
							# May have multiple parents; check if any of them are a sibling
							for grandparentOffset in grandparentStructOffsets:
								if parentStruct.isSibling( grandparentOffset ):
									parentStruct = self.dat.structs[grandparentOffset]
									grandparentStructOffsets = parentStruct.getParents()
									break
							else: # Above loop didn't break; no more siblings found
								foundAnotherSibling = False

						self.parents.update( grandparentStructOffsets )

					else:
						self.parents.add( parentOffset )

			self._parentsChecked = True

		if includeNodeTables:
			return self.parents

		else: # Remove references to the Root/Ref Node tables (returns new set; will not update original parents set)
			return self.parents.difference( [self.dat.headerInfo['rtEnd'], self.dat.headerInfo['rootNodesEnd']] )

	def isSibling( self, structOffset ):

		""" Checks if the given structure is a parent/sibling to this structure. This is only designed 
			to work with an immediate parent/sibling relationship; if you need to check a 
			relationship that is separated by other siblings, call getSiblings() first. """

		# Sibling determination not possible without knowing the structure.
		if self.__class__ == structBase:
		 	return False

		# Check if siblings have already been determined
		if self._siblingsChecked:
			return ( structOffset in self.siblings )

		# Preliminary check; no siblings for these potential structs: file header, node tables, string table
		elif structOffset in ( -32, self.dat.headerInfo['rtStart'], self.dat.headerInfo['rtEnd'], 
								self.dat.headerInfo['rootNodesEnd'], self.dat.headerInfo['stringTableStart'] ):
			return False

		# Attempt to initialize the struct relative (could be a parent or sibling)
		potentialParentStruct = self.dat.initSpecificStruct( self.__class__, structOffset, printWarnings=False )
		if not potentialParentStruct or not potentialParentStruct.fields:
			return False # Sibling determination not possible without knowing the structure.

		# Look for a 'Next_' field, and check if it's a pointer to this struct
		for i, field in enumerate( potentialParentStruct.fields ):
			if field.startswith( 'Next_' ):
				siblingPointerValue = potentialParentStruct.getValues()[i]
				return ( siblingPointerValue == self.offset )
		else: # Loop above didn't break or return; no 'Next_' field
			return False

	def getFirstSibling( self ):

		""" Returns the offset of the first sibling in this structure's group (even if it's this structure). 
			Returns -1 if there are no siblings. """

		if not self._siblingsChecked:
			self.getSiblings()

		if not self.siblings:
			return -1
		
		# Check if this structure is actually the first (structures in the siblings list doesn't include itself)
		firstSiblingOffset = self.siblings[0].offset
		if self.offset < firstSiblingOffset:
			return self.offset
		else:
			return firstSiblingOffset

	def getSiblings( self, nextOnly=False ):

		""" Recursively gets all sibling structure offsets of the current struct, for each "Next_" field.
			If nextOnly is True, only the first sibling is retrieved, but one is still returned for each field. 
			self.siblings is only set if nextOnly=False and the entire list is gathered. 

			This also initializes all sibling structs. """

		if self._siblingsChecked:
			return self.siblings

		self.siblings = []
		sibs = []

		# Sibling determination not possible without knowing the structure.
		if not self.fields:
			self._siblingsChecked = True
			return self.siblings

		# Check for the 'Next_' field marker, indicating a sibling struct pointer
		for siblingFieldIndex, field in enumerate( self.fields ):
			if field.startswith( 'Next_' ): break
		else: # Loop didn't break; 'Next_' field not found
			self._siblingsChecked = True
			return self.siblings

		# tic = time.clock()

		if not nextOnly: # Look for previous siblings which point to this struct
			allSiblingStructs = [] # List of actual structure objects, used to share the final siblings list to all structs
			parentOffsets = self.getParents()
			currentStruct = self

			while parentOffsets:
				for offset in parentOffsets:
					if offset == currentStruct.offset: continue

					# Check if the higher-level parent struct is actually a sibling of the current struct
					elif currentStruct.isSibling( offset ): # Basically checks if a 'Next_' field was referenced to point to this struct
						sibs.insert( 0, offset )

						# Change to the previous sibling, and then check that structure too (do this recursively to the first sibling)
						currentStruct = self.dat.structs[ offset ]
						allSiblingStructs.insert( 0, currentStruct ) # Prepends instead of adding to the end

						parentOffsets = currentStruct.getParents()
						break

				else: # Above loop didn't break; none of the current parents are a sibling
					parentOffsets = None

			allSiblingStructs.append( self )
			sibs.append( self.offset )

		# Look for next siblings which this struct points to
		nextStruct = self
		while nextStruct:
			siblingPointerOffset = nextStruct.offset + struct.calcsize( nextStruct.formatting[1:siblingFieldIndex+1] ) # +1 due to endianness marker

			if siblingPointerOffset in self.dat.pointerOffsets: # Found a valid sibling pointer
				siblingOffset = nextStruct.getValues()[siblingFieldIndex]
				
				sibs.append( siblingOffset )

				if nextOnly: return sibs # No need to continue and update other structures
					
				# Check for the next sibling's sibling (init a structure that's the same kind as the current struct)
				nextStruct = self.dat.initSpecificStruct( self.__class__, siblingOffset, printWarnings=False )

				if nextStruct:
					allSiblingStructs.append( nextStruct )
				else:
					nextStruct = None
					print 'Unable to init sibling of {}; failed at sibling offset 0x{:X}'.format( self.name, 0x20+siblingOffset )

					# Structure series invalidated. Re-initialize all structures encountered for this sibling set
					for structure in allSiblingStructs:
						self.dat.structs[structure.offset] = self.dat.initGenericStruct( structure.offset )
					return []
			else:
				nextStruct = None

		if not nextOnly:
			if len( allSiblingStructs ) == 1: # Only dealing with this (self) struct
				if self.structDepth:
					self.structDepth = ( self.structDepth[0], 0 )
				self.siblings = []
				self._siblingsChecked = True

			else: # Multiple structs need updating with the siblings list gathered above
				if self.structDepth:
					fileDepth = self.structDepth[0] # Avoiding multiple look-ups from the loop below
				else:
					fileDepth = None

				# Now that the full set is known, share it to all of the sibling structs (so they don't need to make the same determination)
				for siblingId, structure in enumerate( allSiblingStructs ):
					structure.siblings = list( sibs ) # Create a copy of the list, so we don't edit the original in the step below
					structure.siblings.remove( structure.offset ) # Removes the reference to a struct's own offset
					structure._siblingsChecked = True

					if fileDepth:
						structure.structDepth = ( fileDepth, siblingId )
					else:
						structure.structDepth = ( -1, siblingId )

		# toc = time.clock()
		# print 'time to get siblings:', toc - tic

		return self.siblings

	def hasChildren( self ):

		""" Checks only whether the structure has ANY children at all. A bit more 
			efficient than calling getChildren and checking how many were returned. """

		# Might already know the answer
		if self._childrenChecked:
			return bool( self.children )

		# Need to determine this based on the pointers in the data section
		structEndingOffset = self.offset + self.length
		for pointerOffset in self.dat.pointerOffsets:
			if pointerOffset >= self.offset and pointerOffset < structEndingOffset: # Pointer found in data block
				return True

		# No children. We can set the children list and children-checked flag
		self._childrenChecked = True
		self.children = []

		return False

	def getChildren( self, includeSiblings=False ):

		""" Searches for pointers to other structures within this structure. Returns a list of struct offsets.
			If siblings are requested as well, do not use the saved list from previous look-ups. """

		if self._childrenChecked and not includeSiblings:
			return self.children

		self.children = []

		# Look for pointers to other structures within this structure
		if self.fields and not includeSiblings: # If wanting to include siblings, the other method is more efficient
			# Check for sibling offsets that should be ignored
			if not includeSiblings:
				siblingPointerOffsets = []
				for i, fieldName in enumerate( self.fields ):
					if fieldName.startswith( 'Next_' ):
						relativeOffset = struct.calcsize( self.formatting[1:i+1] ) # +1 due to endianness marker
						siblingPointerOffsets.append( self.offset + relativeOffset )
						break # Not expecting multiple of these atm

			# Iterate over all pointers in the data section, looking for those that are within the offset range of this structure
			for pointerOffset, pointerValue in self.dat.pointers:
				# Ensure we're only looking in range of this struct
				if pointerOffset < self.offset: continue
				elif pointerOffset >= self.offset + self.length: break

				if not includeSiblings and pointerOffset in siblingPointerOffsets: continue

				self.children.append( pointerValue )
		else:
			# Iterate over all pointers in the data section, looking for those that are within the offset range of this structure
			for pointerOffset, pointerValue in self.dat.pointers:
				# Ensure we're only looking in range of this struct
				if pointerOffset < self.offset: continue
				elif pointerOffset >= self.offset + self.length: break

				self.children.append( pointerValue )

		# If siblings were not included, remember this list for future queries
		if includeSiblings:
			self._childrenChecked = False
		else:
			self._childrenChecked = True

		return self.children

	def initDescendants( self, override=False ):

		""" Recursively initializes structures for an entire branch within the data section. """

		# Prevent redundant passes over this branch of the tree (can happen if multiple structures point to the same structure)
		if self._branchInitialized and not override: # Checking self.dat.structs to see if this struct exists isn't enough
			return

		# Initialize children
		for childStructOffset in self.getChildren( includeSiblings=True ):
			if childStructOffset == self.offset: continue # Prevents infinite recursion, in cases where a struct points to itself

			# Check if the target child struct has already been initialized (only occurs when multiple structs point to one struct)
			childStruct = self.dat.structs.get( childStructOffset, None )

			if childStruct and not childStruct.__class__ == str:
				# This struct/branch has already been created. So just update the target structure's parent structs list with this item.
				childStruct.parents.add( self.offset )

			else: # Create the new struct
				childStruct = self.dat.getStruct( childStructOffset, self.offset )

			childStruct.initDescendants()

		self._branchInitialized = True

	def getBranchSize( self ):

		if self.branchSize != -1:
			return self.branchSize

		# tic = time.clock()

		structsCounted = [ self.offset ]
		totalSize = self.length + self.padding

		def checkChildren( structure, totalSize ):
			for childStructOffset in structure.getChildren( includeSiblings=True ):
				if childStructOffset in structsCounted: # Prevents redundancy as well as infinite recursion, in cases where a struct points to itself
					continue # Already added the size for this one

				# Get the target struct if it has already been initialized
				childStruct = self.dat.getStruct( childStructOffset )

				totalSize += childStruct.length + childStruct.padding
				structsCounted.append( childStructOffset )
				
				totalSize = checkChildren( childStruct, totalSize )

			return totalSize

		self.branchSize = checkChildren( self, totalSize )

		# toc = time.clock()
		# print 'getBranchSize time:', toc-tic

		return self.branchSize

	def structDepthQuickCheck( self, parentOffset, structDepth ):

		""" This is just a quick check for the struct depth, getting it if it was
			provided by default or by checking a parent structure, if one was provided. """

		if structDepth:
			self.structDepth = structDepth

			if parentOffset != -1:
				self.parents = Set( [parentOffset] )

		# Struct depth not provided, but if a parent was, try to determine it from that
		elif parentOffset != -1:
			self.parents = Set( [parentOffset] )	# Set of integers (offsets of other structs)

			self.structDepth = None

		# No struct depth or parent
		else:
			self.structDepth = None

	def getStructDepth( self ):

		""" More intensive check for structure depth than the above method. 
			Will recursively check parent structures (and parents of parents)
			until a depth is found or until reaching the root/ref nodes. """

		if self.structDepth and self.structDepth[0] != -1: # -1 is a file depth placeholder, in case siblings/siblingID have been checked
			return self.structDepth

		parents = self.getParents( includeNodeTables=True )

		# Remove self-references, if present
		parents.difference_update( (self.offset,) )

		# Check if this is a root structure (first-level struct out of the root or reference node tables)
		if len( parents ) == 1 and ( self.dat.headerInfo['rtEnd'] in parents or self.dat.headerInfo['rootNodesEnd'] in parents ):
			self.structDepth = ( 2, 0 )
			return self.structDepth

		# Remove root/ref node labels
		parents.difference_update( (self.dat.headerInfo['rtEnd'], self.dat.headerInfo['rootNodesEnd']) )

		# Iterate over mid-file level parents. Do this recursively until a parent has been found with a struct depth
		for parentOffset in parents:
			parentStruct = self.dat.getStruct( parentOffset )

			if parentStruct.getStructDepth():
				if self.structDepth: # Sibling ID must already be set
					siblingId = self.structDepth[1]

					# The only reason we're still in this method is to get the file depth
					self.structDepth = ( parentStruct.structDepth[0] + 1, siblingId )
				else:
					self.structDepth = ( parentStruct.structDepth[0] + 1, 0 )

					# Update the sibling ID portion of the struct depth by calling getSiblings
					self.getSiblings()

				break

		if not self.structDepth:
			print 'unable to get a struct depth for', self.name

		return self.structDepth

	def setValue( self, index, value ):

		""" Updates the value of a specific field of data, using the field name or an index. """

		if not self.values:
			self.getValues()

		if type( index ) == str: # The index is a field name
			if index not in self.fields:
				raise Exception( 'Invalid field name, "{}", for {}'.format(index, self.name) )
			index = self.fields.index( index )

		valuesList = list( self.values )
		valuesList[index] = value
		self.values = tuple( valuesList )
		#changesNeedSaving = True # Both the self.data and self.dat.data need updating

	def setFlag( self, valueIndex, bitNumber ):

		""" Sets a flag/bit in a sequence of structure flags.
				- valueIndex is the index of the flags field/value
				- bitNumber is the bit to be set """

		# Get the full flags value
		structValues = self.getValues()
		flagsValue = structValues[valueIndex]

		# Check the current value; if the flag is already set, we're done
		if flagsValue & (1 << bitNumber): return

		# Set the flag
		flagsValue = flagsValue | (1 << bitNumber) # OR the current bits with the new bit to be set

		# Put the flags value back in with the rest of the struct values
		valuesList = list( structValues )
		valuesList[valueIndex] = flagsValue
		self.values = tuple( valuesList )

	def clearFlag( self, valueIndex, bitNumber ):

		""" Clears a flag/bit in a sequence of structure flags.
				- valueIndex is the index of the flags field/value
				- bitNumber is the bit to be cleared """

		# Get the full flags value
		structValues = self.getValues()
		flagsValue = structValues[valueIndex]

		# Check the current value; if the flag is already cleared, we're done
		if not flagsValue & (1 << bitNumber): return

		# Set the flag
		flagsValue = flagsValue & ~(1 << bitNumber) # '~' operation inverts bits

		# Put the flags value back in with the rest of the struct values
		valuesList = list( structValues )
		valuesList[valueIndex] = flagsValue
		self.values = tuple( valuesList )

	def valueIndexToOffset( self, valueIndex ):

		""" Converts an index into the field/value arrays into a file data section offset for that item. 
			For example, for the third value (index 2) in a structure with the formatting "HHII", the offset
			returned should be 4. """

		return self.offset + struct.calcsize( self.formatting[1:valueIndex+1] ) # +1 due to endianness marker


class DataBlock( structBase ):

	""" A specialized class for raw blocks of data, to mimic and behave as other structures. """

	def validated( self, *args, **kwargs ): return True
	def getSiblings( self, nextOnly=False ): return []
	def isSibling( self, offset ): return False
	def getChildren( self, includeSiblings=True ): return []
	def initDescendants( self ): return
	def getAttributes( self ): # Gets the properties of this block from a parent image/palette/other data header
		aParentOffset = self.getAnyDataSectionParent()
		return self.dat.getStruct( aParentOffset ).getValues()


class ImageDataBlock( DataBlock ):

	def __init__( self, *args, **kwargs ):
		DataBlock.__init__( self, *args, **kwargs )

		self.name = 'Image Data Block ' + uHex( 0x20 + args[1] )

	@staticmethod
	def getDataLength( width, height, imageType ):

		""" This method differs from that of datObj.getStructLength in that it guarantees no padding is included, since 
			image data always comes in 0x20 byte chunks. Arguments should each be ints. The result is an int, in bytes. """

		byteMultiplier = { # Defines the bytes required per pixel for each image type.
			0: .5, 1: 1, 2: 1, 3: 2, 4: 2, 5: 2, 6: 4, 8: .5, 9: 1, 10: 2, 14: .5 }
		blockDimensions = { # Defines the block width and height for each image type.
			0: (8,8), 1: (8,4), 2: (8,4), 3: (4,4), 4: (4,4), 5: (4,4), 6: (4,4), 8: (8,8), 9: (8,4), 10: (4,4), 14: (8,8) }

		# Calculate based on all encoded pixels (including those in unused block areas), not just the visible ones of the given dimensions.
		blockWidth, blockHeight = blockDimensions[imageType]
		trueWidth = math.ceil( float(width) / blockWidth ) * blockWidth
		trueHeight = math.ceil( float(height) / blockHeight ) * blockHeight

		return int( trueWidth * trueHeight * byteMultiplier[imageType] )

	def getAttributes( self ):

		""" Overidden to be more specific with struct initialization (avoiding structure factory for efficiency). """

		aHeaderOffset = self.getAnyDataSectionParent()
		return self.dat.initSpecificStruct( ImageObjDesc, aHeaderOffset ).getValues()


class PaletteDataBlock( DataBlock ):

	def __init__( self, *args, **kwargs ):
		DataBlock.__init__( self, *args, **kwargs )

		self.name = 'Palette Data Block ' + uHex( 0x20 + args[1] )

	def getAttributes( self ):

		""" Overidden to be more specific with struct initialization (avoiding structure factory for efficiency). """

		aHeaderOffset = self.getAnyDataSectionParent()
		return self.dat.initSpecificStruct( PaletteObjDesc, aHeaderOffset ).getValues()


class FrameDataBlock( DataBlock ):

	interpolationTypes = { 0: 'None', 1: 'Constant', 2: 'Linear', 3: 'Hermite Value', 4: 'Hermite Value and Curve', 5: 'Hermite Curve', 6: 'Key Data' }

	def __init__( self, *args, **kwargs ):
		DataBlock.__init__( self, *args, **kwargs )

		self.name = 'Frame Data String ' + uHex( 0x20 + args[1] )

	def identifyTrack( self ):

		""" Determine what kind of object this track is for, e.g. for a joint, material, etc. 
			Returns a tuple of two strings: ( trackCategory, specificTrackName ) """

		# Get a parent FObjDesc
		parentFrameObjOffset = self.getAnyDataSectionParent()
		parentFrameObj = self.dat.initSpecificStruct( FrameObjDesc, parentFrameObjOffset )

		# Get the next parent (grandparent struct), which should be an animation object (AObjDesc). Sibling FObjDesc ignored.
		aObjDescOffset = parentFrameObj.getAnyDataSectionParent()
		aObjDesc = self.dat.initSpecificStruct( AnimationObjectDesc, aObjDescOffset )

		# Get the next parent, which should be a [Joint/Texture/Material/etc] Animation Struct
		animationStructOffset = aObjDesc.getAnyDataSectionParent()
		animationStruct = self.dat.getStruct( animationStructOffset )

		animationTracks = getattr( animationStruct, 'animationTracks', None )
		if not animationTracks: 
			return ( 'Unknown', 'Unknown' )

		trackType = animationStruct.name.split()[0] # Returns 'Texture', 'Material', etc.
		trackId = parentFrameObj.getValues()[3]
		trackName = animationTracks.get( trackId, 'Unknown' )
		
		return ( trackType, trackName )

	def decodeUleb128( self, readPosition ):

		""" Parser for the Unsigned Little-Endian Base 128 data format. These are capped at 3 bytes in this case.
			Documentation: https://en.wikipedia.org/wiki/LEB128 
			Examples: https://smashboards.com/threads/melee-dat-format.292603/post-23487048 """

		value = 0
		shift = 0

		while shift <= 14: # Failsafe; make sure we don't go beyond 3 bytes
			# Add the first 7 bits of the current byte to the value
			byteValue = self.data[readPosition]
			value |= ( byteValue & 0b1111111 ) << shift
			readPosition += 1

			# Check bit 8 to see if we should continue to the next byte
			if byteValue & 0b10000000:
				shift += 7
			else: # bit 8 is 0; done reading this value
				break

		if shift > 14: # Error
			print 'Warning; uleb128 value found to be invalid (more than 3 bytes)'
			value = -1

		return readPosition, value

	def parse( self ):
		debugging = False

		# Get an arbitrary parent offset; shouldn't matter which
		dataHeaders = self.getParents()
		aParentOffset = next( iter(dataHeaders) )
		parentStruct = self.dat.initSpecificStruct( FrameObjDesc, aParentOffset, printWarnings=False ) # Just gets it if it's already initialized

		# Make sure there's a parent struct, and it's the correct class
		if not parentStruct or parentStruct.__class__ != FrameObjDesc: 
			print 'Unable to parse', self.name, '; unable to initialize parent as a FrameObjDesc.'
			return -1, -1, []

		_, stringLength, _, _, dataTypeAndScale, slopeDataTypeAndScale, _, _ = parentStruct.getValues()

		# Display the data type and scale
		dataType = dataTypeAndScale >> 5 		# Use the last (left-most) 3 bits
		dataScale = 1 << ( dataTypeAndScale & 0b11111 ) 	# Use the first 5 bits
		dataTypeFormatting, dataTypeByteLength = parentStruct.dataTypes[dataType][1:]
		if debugging:
			print 'dataTypeAndScale:', format( dataTypeAndScale, 'b' ).zfill( 8 )
			print 'dataType / scale:', dataType, '/', dataScale
			print 'dataType len:', dataTypeByteLength

		# Display the slope dataType and slope scale
		slopeDataType = slopeDataTypeAndScale >> 5 			# Use the last (left-most) 3 bits
		slopeDataScale = 1 << ( slopeDataTypeAndScale & 0b11111 ) 	# Use the first 5 bits
		slopeDataTypeFormatting, slopeDataTypeByteLength = parentStruct.dataTypes[slopeDataType][1:]
		if debugging:
			print 'slopeDataTypeAndScale:', format( slopeDataTypeAndScale, 'b' ).zfill( 8 )
			print 'slope dataType / scale:', slopeDataType, '/', slopeDataScale
			print 'slope dataType len:', slopeDataTypeByteLength

		# The first value in the string is a uleb128, which defines two variables: interpolationID, and an array size
		readPosition, opCodeValue = self.decodeUleb128( 0 ) # Starts with read position 0

		#  -- maybe not a uleb? always two bytes??
		# readPosition = 2
		# opCodeValue = struct.unpack( '>H', self.data[:2] )[0]
		# -- 

		interpolationID = opCodeValue & 0b1111 # First 4 bits
		arrayCount = ( opCodeValue >> 4 ) + 1 # Everything else. Seems to be 0-indexed
		if debugging:
			print 'interpolation:', interpolationID, '(' + self.interpolationTypes[interpolationID] + ')', '   arrayCount:', arrayCount
			print '\n'

		parsedValues = []

		while readPosition < stringLength:
			try:
				if debugging:
					print 'starting loop at read position', readPosition

				# Read Value
				if interpolationID == 0 or interpolationID == 5: # For 'None' and 'Hermite Curve'
					value = 0
				else:
					if debugging:
						print '\treading', dataTypeByteLength, 'bytes for value'
					dataBytes = self.data[readPosition:readPosition+dataTypeByteLength]
					value = struct.unpack( dataTypeFormatting, dataBytes )[0] / float( dataScale )
					readPosition += dataTypeByteLength

				# Read Tangent
				if interpolationID == 4 or interpolationID == 5: # For 'Hermite Value and Curve' and 'Hurmite Curve'
					if debugging:
						print '\treading', dataTypeByteLength, 'bytes for tangent value'
					dataBytes = self.data[readPosition:readPosition+slopeDataTypeByteLength]
					tangentValue = struct.unpack( slopeDataTypeFormatting, dataBytes )[0] / float( slopeDataScale )
					readPosition += slopeDataTypeByteLength
				else:
					tangentValue = 0

				# Read the next uleb
				if debugging:
					print 'reading uleb at read position', readPosition
				readPosition, ulebValue = self.decodeUleb128( readPosition )

				parsedValues.append( (value, tangentValue, ulebValue) )

			except:
				parsedValues.append( (-1, -1, -1) )
				print 'Error encountered during FObjDesc parsing,', self.name
				break

		return interpolationID, arrayCount, parsedValues


class DisplayDataBlock( DataBlock ):

	def __init__( self, *args, **kwargs ):
		DataBlock.__init__( self, *args, **kwargs )

		self.name = 'Display List Data Block ' + uHex( 0x20 + args[1] )


class VertexDataBlock( DataBlock ):

	def __init__( self, *args, **kwargs ):
		DataBlock.__init__( self, *args, **kwargs )

		self.name = 'Vertex Data Block ' + uHex( 0x20 + args[1] )


					# = --------------------------------------------------- = #
					#  [   HSD Internal File Structure Classes  (Common)   ]  #
					# = --------------------------------------------------- = #

class JointObjDesc( structBase ):

	flags = { 'Joint_Flags': OrderedDict([
				( '1<<0', 'SKELETON' ),
				( '1<<1', 'SKELETON_ROOT' ),
				( '1<<2', 'ENVELOPE_MODEL' ),
				( '1<<3', 'CLASSICAL_SCALING' ),
				( '1<<4', 'HIDDEN' ),
				( '1<<5', 'PTCL' ),
				( '1<<6', 'MTX_DIRTY' ),
				( '1<<7', 'LIGHTING' ),
				( '1<<8', 'TEXGEN' ),
				( '1<<9', 'BILLBOARD' ),
				( '2<<9', 'VBILLBOARD' ),
				( '3<<9', 'HBILLBOARD' ),
				( '4<<9', 'RBILLBOARD' ),
				( '1<<12', 'INSTANCE' ),
				( '1<<13', 'PBILLBOARD' ),
				( '1<<14', 'SPLINE' ),
				( '1<<15', 'FLIP_IK' ),
				( '1<<16', 'SPECULAR' ),
				( '1<<17', 'USE_QUATERNION' ),
				( '1<<18', 'OPA' ),
				( '1<<19', 'XLU' ),
				( '1<<20', 'TEXEDGE' ),
				( '0<<21', 'NULL' ),
				( '1<<21', 'JOINT1' ),
				( '2<<21', 'JOINT2' ),
				( '3<<21', 'EFFECTOR' ),
				( '1<<23', 'USER_DEFINED_MTX' ),
				( '1<<24', 'MTX_INDEPEND_PARENT' ),
				( '1<<25', 'MTS_INDEPEND_SRT' ),
				( '1<<28', 'ROOT_OPA' ),
				( '1<<29', 'ROOT_XLU' ),
				( '1<<30', 'ROOT_TEXEDGE' )
		]) }

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )
		
		# Attempt special name generation for stage General Points
		self.name = 'Joint Struct ' + uHex( 0x20 + args[1] )

		self.formatting = '>IIIIIfffffffffII'
		self.fields = ( 'Name_Pointer',
						'Joint_Flags',
						'Child_Pointer',
						'Next_Sibling_Pointer',
						'Display_Object_Pointer',
						'Rotation_X',
						'Rotation_Y',
						'Rotation_Z',
						'Scale_X',
						'Scale_Y',
						'Scale_Z',
						'Translation_X',
						'Translation_Y',
						'Translation_Z',
						'Inverse_Matrix_Pointer',	# Object refers to parent if this is null
						'Reference_Object_Pointer'
					)
		self.length = 0x40
		self.childClassIdentities = { 2: 'JointObjDesc', 3: 'JointObjDesc', 4: 'DisplayObjDesc', 14: 'InverseMatrixObjDesc' }

	def getGeneralPointType( self ):

		pointType = ''

		# Get the parent joint of the sibling array
		parentOffset = self.getAnyDataSectionParent()
		jointParent = self.dat.initSpecificStruct( JointObjDesc, parentOffset, printWarnings=False )

		if jointParent:
			for parentOffset in jointParent.getParents():
				generalPointsArray = self.dat.initSpecificStruct( MapGeneralPointsArray, parentOffset, printWarnings=False )
				if generalPointsArray: break

			if generalPointsArray:
				# Get the Point Types Array offset for this joint
				parentValues = generalPointsArray.getValues()
				for i, value in enumerate( parentValues ):
					if value == jointParent.offset:
						pointTypesArrayOffset = parentValues[i+1]
						break

				pointTypesArray = self.dat.initSpecificStruct( MapPointTypesArray, pointTypesArrayOffset )
				pointTypeValues = pointTypesArray.getValues()
				siblingIndex = self.getStructDepth()[1] + 1 # +1 because the point types array indices are 1-indexed

				for i, value in enumerate( pointTypeValues ):
					if value == siblingIndex:
						pointTypeValue = pointTypeValues[i+1]
						pointType = pointTypesArray.enums['Point_Type'].get( pointTypeValue, '' )
						if not pointType:
							pointType = 'Unknown Point Type ({})'.format( pointTypeValue )
						break
				else: # The loop above didn't break, meaning the current joint index wasn't found in the point types array
					pointType = 'Undefined Point Type'
					print 'General Point', uHex( 0x20 + self.offset ), 'type not defined in', pointTypesArray.name

		return pointType


class DisplayObjDesc( structBase ):

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Display Object ' + uHex( 0x20 + args[1] )
		self.formatting = '>IIII'
		self.fields = ( 'Name_Pointer',					# 0x0
						'Next_Sibling_Pointer',			# 0x4
						'Material_Object_Pointer',		# 0x8
						'Polygon_Object_Pointer',		# 0xC
					)
		self.length = 0x10
		self.childClassIdentities = { 1: 'DisplayObjDesc', 2: 'MaterialObjDesc', 3: 'PolygonObjDesc' }

	def validated( self, deducedStructLength=-1 ):
		if not super( DisplayObjDesc, self ).validated( False, deducedStructLength ): 
			return False

		# At this point, we know the struct's pointers are good. Check if the Material pointer leads to a valid material struct.
		matObjOffset = self.getValues()[2]

		if matObjOffset != 0 or self.offset + 8 in self.dat.pointerOffsets:
			materialStruct = self.dat.initSpecificStruct( MaterialObjDesc, matObjOffset, self.offset, printWarnings=False )
			if not materialStruct:
				#print self.name, 'invalidated as', self.__class__.__name__, 'due to child at', hex(0x20+matObjOffset)
				return False

		self.provideChildHints()
		return True


class InverseMatrixObjDesc( structBase ):

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Inverse Bind Matrix ' + uHex( 0x20 + args[1] )
		self.formatting = '>ffffffffffff'
		self.fields = ( 'M00',
						'M01',
						'M02',
						'M03',
						'M10',
						'M11',
						'M12',
						'M13',
						'M20',
						'M21',
						'M22',
						'M23',
					)
		self.length = 0x30
		self.childClassIdentities = {}
		self._siblingsChecked = True
		self._childrenChecked = True


# class ReferenceObjDesc( structBase ):

# 	def __init__( self, *args, **kwargs ):
# 		structBase.__init__( self, *args, **kwargs )


# 		self.name = 'Inverse Bind Matrix ' + uHex( 0x20 + args[1] )
	# 	formatting = '>'
	# 	fields = (  '',
	# 				''
	# 			)
	# 	length = 
	#	childClassIdentities = { 
#		self._siblingsChecked = 


class MaterialObjDesc( structBase ):

	flags = { 'Rendering_Flags': OrderedDict([
				( '0<<0',  'RENDER_DIFFUSE_MAT0' ),
				( '1<<0',  'RENDER_DIFFUSE_MAT' ),
				( '2<<0',  'RENDER_DIFFUSE_VTX' ),
				( '3<<0',  'RENDER_DIFFUSE_BOTH' ),
				( '1<<2',  'RENDER_DIFFUSE' ),
				( '1<<3',  'RENDER_SPECULAR' ),
				( '1<<4',  'RENDER_TEX0' ),
				( '1<<5',  'RENDER_TEX1' ),
				( '1<<6',  'RENDER_TEX2' ),
				( '1<<7',  'RENDER_TEX3' ),
				( '1<<8',  'RENDER_TEX4' ),
				( '1<<9',  'RENDER_TEX5' ),
				( '1<<10', 'RENDER_TEX6' ),
				( '1<<11', 'RENDER_TEX7' ),
				( '1<<12', 'RENDER_TOON' ),				# Not used in Melee
				( '0<<13', 'RENDER_ALPHA_COMPAT' ),		# Required for alpha pixel-processing
				( '1<<13', 'RENDER_ALPHA_MAT' ),
				( '2<<13', 'RENDER_ALPHA_VTX' ),
				( '3<<13', 'RENDER_ALPHA_BOTH' ),
				( '1<<26', 'RENDER_SHADOW' ),
				( '1<<27', 'RENDER_ZMODE_ALWAYS' ),
				( '1<<28', 'RENDER_DF_NONE' ),
				( '1<<29', 'RENDER_NO_ZUPDATE' ),
				( '1<<30', 'RENDER_XLU' ),
				( '1<<31', 'RENDER_USER' )
			]) }

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Material Object ' + uHex( 0x20 + args[1] )
		self.formatting = '>IIIIII'
		self.fields = ( 'Name_Pointer',					# 0x0
						'Rendering_Flags',				# 0x4
						'Texture_Object_Pointer',		# 0x8
						'Material_Colors_Pointer',		# 0xC
						'Render_Struct_Pointer',		# 0x10
						'Pixel_Proc._Pointer' 			# 0x14
					)
		self.length = 0x18
		self.childClassIdentities = { 2: 'TextureObjDesc', 3: 'MaterialColorObjDesc', 5: 'PixelProcObjDesc' }
		self._siblingsChecked = True

	def validated( self, deducedStructLength=-1 ):
		prelimCheck = super( MaterialObjDesc, self ).validated( False, deducedStructLength )
		if not prelimCheck: return False

		# At this point, we know the struct's pointers are good. Check if the Texture Object pointer leads to a valid texture struct.
		texObjOffset = self.getValues()[2]
		if texObjOffset != 0 or self.offset + 8 in self.dat.pointerOffsets:
			texStruct = self.dat.initSpecificStruct( TextureObjDesc, texObjOffset, self.offset, printWarnings=False )
			if not texStruct: return False

		self.provideChildHints()
		return True


class PolygonObjDesc( structBase ): # A.k.a. Meshes

	flags = { 'Polygon_Flags': OrderedDict([
				( '1<<0', 'NOTINVERTED' ),
				( '1<<3', 'ANIMATED' ),
				( '1<<12', 'SHAPEANIM' ),
				( '2<<12', 'ENVELOPE' ),
				( '1<<14', 'CULLFRONT' ),
				( '1<<15', 'CULLBACK' )
			]) }

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Polygons Object ' + uHex( 0x20 + args[1] )
		self.formatting = '>IIIHHII'
		mostFields = (  'Name_Pointer',							# 0x0
						'Next_Sibling_Pointer',					# 0x4
						'Vertex_Attributes_Array_Pointer',		# 0x8
						'Polygon_Flags',						# 0xC
						'Display_List_Length',					# 0xE
						'Display_List_Data_Pointer'				# 0x10
						#'Influence_Matrix_Array_Pointer'		# 0x14
					)
		self.length = 0x18
		self.childClassIdentities = { 1: 'PolygonObjDesc', 2: 'VertexAttributesArray', 5: 'DisplayDataBlock' }

		# Check flags to determine last field name and child structure
		try: # Exercising caution here because this structure hasn't been validated yet (which also means no self.data or unpacked values)
			flagsOffset = args[1] + 0xC
			flagsValue = struct.unpack( '>H', self.dat.data[flagsOffset:flagsOffset+2] )[0]
			if flagsValue & 0x1000: # Uses ShapeAnims
				self.fields = mostFields + ( 'Shape_Set_Pointer',)
				self.childClassIdentities[6] = 'ShapeSetDesc'

			elif flagsValue & 0x2000: # Uses Envelopes
				self.fields = mostFields + ( 'Envelope_Array_Pointer',)
				self.childClassIdentities[6] = 'EnvelopeArray'

			else:
				if args[1] + 0x14 in self.dat.structureOffsets: # Not expected, but just in case....
					self.fields = mostFields + ( 'JObjDesc_Pointer',)
					print self.name, 'found a JObjDesc pointer!'
				else:
					self.fields = mostFields + ( 'Null Pointer',) # No underscore, so validation method ignores this as an actual pointer

		except Exception as err:
			print 'PolygonObjDesc initialization failure;'
			print err


class VertexAttributesArray( structBase ):

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Vertex Attributes Array ' + uHex( 0x20 + args[1] )

		# Attempt to get the length and array count of this struct
		deducedStructLength = self.dat.getStructLength( self.offset ) # This length will include any padding too
		if deducedStructLength / 0x18 == 1: # Using division rather than just '==0x18' in case there's trailing padding
			self.entryCount = 1
		else:
			# Check for a null attribute name (GX_VA_NULL; value of 0xFF)
			try:
				self.entryCount = -1
				for fieldOffset in range( self.offset, self.offset + deducedStructLength, 0x18 ):
					attributeName = self.dat.data[fieldOffset+3]

					if attributeName == 0xFF: # End of this array
						self.entryCount = ( fieldOffset - self.offset ) / 0x18 + 1
						break
			except:
				self.entryCount = -1

		# Need to set some properties at instance level, rather than usual class level, since they can change
		fields = (	'Attribute_Name',			# 0x0
					'Attribute_Type',			# 0x4
					'Component_Count',			# 0x8
					'Component_Type',			# 0xC
					'Scale',					# 0x10
					'Padding',					# 0x11
					'Stride',					# 0x12
					'Vertex_Data_Pointer' )		# 0x14
			
		# Use the above info to dynamically build this struct's properties
		self.formatting = '>' + ( 'IIIIBBHI' * self.entryCount )
		self.fields = fields * self.entryCount
		self.length = 0x18 * self.entryCount
		self.childClassIdentities = {}
		for i in range( 7, len(self.fields)+7, 8 ):
			self.childClassIdentities[i] = 'VertexDataBlock'
		self._siblingsChecked = True

	# def validated( self, deducedStructLength=-1 ):
	# 	prelimCheck = super( VertexAttributesArray, self ).validated( False, deducedStructLength )
	# 	#print 'prelim val for', self.name, 'returned', prelimCheck
	# 	if not prelimCheck: return False

	# # 	# Confirm array count by checking for a null attribute name (GX_VA_NULL; value of 0xFF)
	# # 	arrayCount = -1
	# # 	for index in range( 0, len(self.formatting)-1, 8 ):
	# # 		attributeName = self.values[index]

	# # 		if attributeName == 0xFF: # End of this array
	# # 			arrayCount = index / 8 + 1
	# # 			break
	# # 	if arrayCount != self.entryCount:
	# # 		print 'Unexpected array count for', self.name + '; expected', self.entryCount, 'but found', arrayCount
	# # 		return False

	# 	# Validation passed
	# 	self.provideChildHints()
	# 	return True


class EnvelopeArray( structBase ):

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Envelope Array ' + uHex( 0x20 + args[1] )
		self._siblingsChecked = True

		# Check the parent's array count to see how many elements should be in this structure
		self.length = self.dat.getStructLength( self.offset )
		self.entryCount = self.length / 4 - 1

		# Use the above info to dynamically build this struct's basic properties
		self.formatting = '>' + ( 'I' * self.entryCount ) + 'I'
		self.fields = ( 'Envelope_Pointer', ) * self.entryCount + ( 'Null Terminator', )
		self.childClassIdentities = {}
		for i in range( 0, self.entryCount ):
			self.childClassIdentities[i] = 'EnvelopeObjDesc'


class EnvelopeObjDesc( structBase ):

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Envelope Object ' + uHex( 0x20 + args[1] )
		self._siblingsChecked = True

		self.length = self.dat.getStructLength( self.offset ) - 8
		self.entryCount = self.length / 8
		self.padding = 8

		# Use the above info to dynamically build this struct's basic properties
		self.formatting = '>' + ( 'If' * self.entryCount )
		self.fields = ( 'Joint_Pointer', 'Weight' ) * self.entryCount
		self.childClassIdentities = {}
		for i in range( 0, self.entryCount ):
			self.childClassIdentities[i] = 'JointObjDesc'


class ShapeSetDesc( structBase ):

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Shape Set Object ' + uHex( 0x20 + args[1] )
		self.formatting = '>HHIIIIII'
		self.fields = ( 'Shape Flags',
						'Number of Shapes',
						'Number of Vertex Indices',
						'Vertex_Desc._Array_Pointer',
						'Vertex_Index_Array_Pointer',
						'Number of Normal Indices',
						'Vertex_Desc._Array_Pointer',
						'Normal_Index_Array_Pointer' )
		self.length = 0x1C
		self._siblingsChecked = True
		self.childClassIdentities = { 3: 'VertexAttributesArray', 6: 'VertexAttributesArray' }


class TextureObjDesc( structBase ):

	flags = { 'Texture_Flags': OrderedDict([
				( '0<<0', 'COORD_UV' ),
				( '1<<0', 'COORD_REFLECTION' ),
				( '2<<0', 'COORD_HILIGHT' ),
				( '3<<0', 'COORD_SHADOW' ),
				( '4<<0', 'COORD_TOON' ),
				( '5<<0', 'COORD_GRADATION' ),
				( '1<<4', 'LIGHTMAP_DIFFUSE' ),
				( '1<<5', 'LIGHTMAP_SPECULAR' ),
				( '1<<6', 'LIGHTMAP_AMBIENT' ),
				( '1<<7', 'LIGHTMAP_EXT' ),
				( '1<<8', 'LIGHTMAP_SHADOW' ),
				( '0<<16', 'COLORMAP_NONE' ),
				( '1<<16', 'COLORMAP_ALPHA_MASK' ),
				( '2<<16', 'COLORMAP_RGB_MASK' ),
				( '3<<16', 'COLORMAP_BLEND' ),
				( '4<<16', 'COLORMAP_MODULATE' ),
				( '5<<16', 'COLORMAP_REPLACE' ),
				( '6<<16', 'COLORMAP_PASS' ),
				( '7<<16', 'COLORMAP_ADD' ),
				( '8<<16', 'COLORMAP_SUB' ),
				( '1<<20', 'ALPHAMAP_ALPHA_MASK' ),
				( '2<<20', 'ALPHAMAP_BLEND' ),
				( '3<<20', 'ALPHAMAP_MODULATE' ),
				( '4<<20', 'ALPHAMAP_REPLACE' ),
				( '5<<20', 'ALPHAMAP_PASS' ),
				( '6<<20', 'ALPHAMAP_ADD' ),
				( '7<<20', 'ALPHAMAP_SUB' ),
				( '1<<24', 'BUMP' ),
				( '1<<31', 'MTX_DIRTY' )
			]) }

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Texture Struct ' + uHex( 0x20 + args[1] )
		self.formatting = '>IIIIfffffffffII??HIfIIIII'
		self.fields = ( 'Name_Pointer',
						'Next_Sibling_Pointer',
						'GXTexMapID',
						'GXTexGenSrc', 		# Coord Gen Source Args
						'Rotation_X',
						'Rotation_Y',
						'Rotation_Z',
						'Scale_X',
						'Scale_Y',
						'Scale_Z',
						'Translation_X',
						'Translation_Y',
						'Translation_Z',
						'GXTexWrapMode_S',
						'GXTexWrapMode_T',
						'Repeat_S',
						'Repeat_T',
						'Padding',
						'Texture_Flags',
						'Blending',
						'GXTexFilter',
						'Image_Header_Pointer',
						'Palette_Header_Pointer',
						'LOD_Struct_Pointer',
						'TEV_Struct_Pointer'
					)
		self.length = 0x5C
		self.childClassIdentities = { 1: 'TextureObjDesc', 21: 'ImageObjDesc', 22: 'PaletteObjDesc', 23: 'LodObjDes', 24: 'TevObjDesc' }

	def validated( self, deducedStructLength=-1 ):
		prelimCheck = super( TextureObjDesc, self ).validated( False, deducedStructLength )
		if not prelimCheck: return False

		# Check for and initialize a TEV Struct, if present
		tevStructOffset = self.getValues()[-1]
		if tevStructOffset == 0:
			self.provideChildHints()
			return True
		else:
			if not tevStructOffset in self.dat.structs:
				self.dat.structs[tevStructOffset] = 'TevObjDesc' # Adding a hint to permit this struct to be created even if it's all null data
			tevStruct = self.dat.initSpecificStruct( TevObjDesc, tevStructOffset, self.offset, printWarnings=False )
			if not tevStruct: return False

			# Validation passed
			self.provideChildHints()
			return True


class MaterialColorObjDesc( structBase ):

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Material Colors ' + uHex( 0x20 + args[1] )
		self.formatting = '>IIIff'
		self.fields = (	'RGBA_Diffusion',
						'RGBA_Ambience',
						'RGBA_Specular_Highlights',
						'Transparency_Control',
						'Shininess'
					)
		self.length = 0x14
		self.childClassIdentities = {}
		self._siblingsChecked = True
		self._childrenChecked = True


class PixelProcObjDesc( structBase ): # Pixel Processor Struct (PEDesc)
														# [ Internal GX Notes ]
	flags = { 'Pixel Proc. Flags': OrderedDict([
				( '1<<0', 'Enable Color Updates' ),			# update_enable
				( '1<<1', 'Enable Alpha Updates' ),			# update_enable
				( '1<<2', 'Enable Destination Alpha' ),		# enable
				( '1<<3', 'Z-Buff Before Texturing' ),		# before_tex
				( '1<<4', 'Enable Z Comparisons' ),			# compare_enable
				( '1<<5', 'Enable Z Updates' ),				# update_enable
				( '1<<6', 'Enable Dithering' )				# dither
			]) }

	enums = { 'Blend Mode Type': OrderedDict([			# GXBlendMode:
				( 0, 'None' ),					# GX_BM_NONE (writes directly to EFB)
				( 1, 'Additive' ),				# GX_BM_BLEND
				( 2, 'Logical Bitwise' ),		# GX_BM_LOGIC
				( 3, 'Subtract' ),				# GX_BM_SUBTRACT
				( 4, 'Max Blend' )				# GX_MAX_BLENDMODE
			]),
			'Source Factor': OrderedDict([				# GXBlendFactor:
				( 0, 'Zero' ),					# GX_BL_ZERO			0.0
				( 1, 'One' ),					# GX_BL_ONE				1.0
				( 2, 'Destination Color' ),		# GX_BL_DSTCLR			frame buffer color
				( 3, 'Inverse Dest. Color' ),	# GX_BL_INVDSTCLR		1.0 - (frame buffer color)
				( 4, 'Source Alpha' ),			# GX_BL_SRCALPHA		source alpha
				( 5, 'Inverse Src. Alpha' ),	# GX_BL_INVSRCALPHA		1.0 - (source alpha)
				( 6, 'Destination Alpha' ),		# GX_BL_DSTALPHA		frame buffer alpha
				( 7, 'Inverse Dest. Alpha' )	# GX_BL_INVDSTALPHA		1.0 - (frame buffer alpha)
			]),
			'Destination Factor': OrderedDict([			# GXBlendFactor:
				( 0, 'Zero' ),					# GX_BL_ZERO			0.0
				( 1, 'One' ),					# GX_BL_ONE				1.0
				( 2, 'Source Color' ),			# GX_BL_SRCCLR			source color
				( 3, 'Inverse Src. Color' ),	# GX_BL_INVSRCCLR		1.0 - (source color)
				( 4, 'Source Alpha' ),			# GX_BL_SRCALPHA		source alpha
				( 5, 'Inverse Src. Alpha' ),	# GX_BL_INVSRCALPHA		1.0 - (source alpha)
				( 6, 'Destination Alpha' ),		# GX_BL_DSTALPHA		frame buffer alpha
				( 7, 'Inverse Dest. Alpha' )	# GX_BL_INVDSTALPHA		1.0 - (frame buffer alpha)
			 ]) }

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Pixel Proc. Struct ' + uHex( 0x20 + args[1] )
		self.formatting = '>BBBBBBBBBBBB'
		self.fields = (	'Pixel Proc. Flags',		#			(bitflags)
						'Reference Value 0',		#			(ref0)
						'Reference Value 1',		#			(ref1)
						'Destination Alpha',		#			(alpha)
						'Blend Mode Type',			# 0x4		(type)
						'Source Factor',			#			(src_factor )
						'Destination Factor',		#			(dst_factor )
						'Blend Operation',			#			(op)
						'Z Compare Function',		# 0x8		(func)
						'Alpha Compare 0',			#			(comp0)
						'Alpha Operation',			#			(op)
						'Alpha Compare 1'			#			(comp1)
					)
		self.length = 0xC
		self.childClassIdentities = {}
		self._siblingsChecked = True
		self._childrenChecked = True


class ImageObjDesc( structBase ):

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Image Data Header ' + uHex( 0x20 + args[1] )
		self.formatting = '>IHHIIff'
		self.fields = (	'Image_Data_Pointer',
						'Width',
						'Height',
						'Image_Type',
						'Mipmap_Flag',
						'MinLOD',
						'MaxLOD'
					)
		self.length = 0x18
		self.childClassIdentities = { 0: 'ImageDataBlock' }
		self._siblingsChecked = True

	def validated( self, deducedStructLength=-1 ):
		# Perform basic struct validation
		prelimCheck = super( ImageObjDesc, self ).validated( False, deducedStructLength )
		if not prelimCheck: return False

		# Check specific data values for known restrictions
		dataBlockOffset, width, height, imageType, mipmapFlag, minLOD, maxLOD = self.getValues()

		if width < 1 or height < 1: return False
		elif width > 1024 or height > 1024: return False
		elif imageType not in ( 0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 14 ): return False
		elif mipmapFlag > 1: return False
		elif minLOD > 10 or maxLOD > 10: return False
		elif minLOD > maxLOD: return False

		# Check for a minimum size on the image data block. Most image types require at least 0x20 bytes for even just a 1x1 pixel image
		childStructLength = self.dat.getStructLength( dataBlockOffset )
		if childStructLength == -1: pass # Can't trust this; unable to calculate the length (data must be after the string table)
		elif imageType == 6 and childStructLength < 0x40: return False
		elif childStructLength < 0x20: return False

		# Check if the child (image data) has any children (which it shouldn't)
		for pointerOffset in self.dat.pointerOffsets:
			if pointerOffset >= dataBlockOffset:
				if pointerOffset < dataBlockOffset + childStructLength: # Pointer found in data block
					return False
				break

		# Validation passed
		self.provideChildHints()
		return True


class PaletteObjDesc( structBase ):

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Palette Data Header ' + uHex( 0x20 + args[1] )
		self.formatting = '>IIIH'
		self.fields = (	'Palette_Data_Pointer',
						'Palette_Type', 		# GXTlutFmt
						'Name',
						'Color_Count'
					)
		self.length = 0xE
		self.childClassIdentities = { 0: 'PaletteDataBlock' }
		self._siblingsChecked = True

	def validated( self, deducedStructLength=-1 ):
		# Perform basic struct validation
		prelimCheck = super( PaletteObjDesc, self ).validated( False, deducedStructLength )
		if not prelimCheck: return False

		# Check specific data values for known restrictions
		dataBlockOffset, paletteType, name, colorCount = self.getValues()

		if dataBlockOffset == 0: return False
		elif paletteType > 2: return False # Should only be 0-2
		elif name != 0: return False # Always seen as 0
		elif colorCount > 16384: return False # Max is 16/256/16384 for image types 8/9/10, respectively

		# Check for a minimum size on the palette data block
		childStructLength = self.dat.getStructLength( dataBlockOffset )
		if childStructLength < 0x20: return False # Even _8 type paletted textures (CI4), the smallest type, reserve at least 0x20 bytes

		# Check if the child (palette data) has any children (which it shouldn't)
		for pointerOffset in self.dat.pointerOffsets:
			if pointerOffset >= dataBlockOffset:
				if pointerOffset < dataBlockOffset + childStructLength: # Pointer found in data block
					return False
				break
		
		# Validation passed
		self.provideChildHints()
		return True


class LodObjDes( structBase ):	# Level Of Detail

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Level of Detail Struct ' + uHex( 0x20 + args[1] )
		self.formatting = '>If??HI'
		self.fields = ( 'Min_Filter',		# GXTexFilter
						'LOD_Bias',			# Float
						'Bias_Clamp', 		# Bool
						'Edge_LOD_Enable',	# Bool
						'Padding',			# 2 bytes
						'Max_Anisotrophy'	# GXAnisotropy
					)
		self.length = 0x10
		self.childClassIdentities = {}
		self._siblingsChecked = True
		self._childrenChecked = True

	""" A few restrictions on the values of this structure
		(although probably won't bother to validate this):
			LOD Bias - should be between -4.0 to 3.99
			Edge LOD must be enabled for Max Anisotrophy
			Max Anisotrophy can be 0, 1, 2, or 4 
			(latter two values require trilinear filtering) """


class TevObjDesc( structBase ):

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Texture Environment Struct ' + uHex( 0x20 + args[1] )
		self.formatting = '>????????BBBBBBBBIIII'
		self.fields = ( 'Color_Op',
						'Alpha_Op',
						'Color_Bias',
						'Alpha_Bias',
						'Color_Scale',
						'Alpha_Scale',
						'Color_Clamp',
						'Alpha_Clamp',
						'Color_A',			# 0x8
						'Color_B',
						'Color_C',
						'Color_D',
						'Alpha_A',
						'Alpha_B',
						'Alpha_C',
						'Alpha_D',
						'RGBA_Color_1_(konst)',	# 0x10
						'RGBA_Color_2_(tev0)',
						'RGBA_Color_3_(tev1)',
						'Active'
					)
		self.length = 0x20
		self.childClassIdentities = {}
		self._siblingsChecked = True
		self._childrenChecked = True


class CameraObjDesc( structBase ): # CObjDesc

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Camera Struct ' + uHex( 0x20 + args[1] )
		self.formatting = '>IHHHHHHHHHHIIfIffffff'
		self.fields = ( 'Name_Pointer',
						'Camera_Flags',
						'Projection_Type',
						'Viewport_Left',
						'Viewport_Right',
						'Viewport_Top',
						'Viewport_Bottom',
						'Scissor_Left',
						'Scissor_Right',
						'Scissor_Top',
						'Scissor_Bottom',
						'Eye_Position_WorldObj_Pointer',
						'Interest_WorldObj_Pointer',
						'Roll',
						'UpVector_Pointer',
						'Near',
						'Far',
						'FoV_Top',
						'Aspect_Bottom',
						'Projection_Left',
						'Projection_Right'
					)
		self.length = 0x40
		self.childClassIdentities = {}
		self._siblingsChecked = True


					# = ---------------------------------------------------- = #
					#  [   HSD Internal File Structure Classes (Specific)   ]  #
					# = ---------------------------------------------------- = #

class MapHeadObjDesc( structBase ):

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Map Head Struct ' + uHex( 0x20 + args[1] )
		self.formatting = '>IIIIIIIIIIII'		# In the context below, 'array' means multiple objects in one file structure.
		self.fields = ( 'General_Points_Array_Pointer',		# 0x0 - Points to an array of 0xC long objects
						'General_Points_Array_Count',		# 0x4 - These are all 1-indexed
						'Game_Objects_Array_Pointer',		# 0x8 - Points to an array of 0x34 long objects
						'Game_Objects_Array_Count',
						'Splines_Array_Pointer',			# 0x10 - Points to an array of 0x4 long objects (just pointers)
						'Splines_Array_Count',
						'Map_Lights_Array_Pointer',			# 0x18 - Points to an array of 0x8 long objects
						'Map_Lights_Array_Count',
						'Array_5_Pointer',					# 0x20
						'Array_5_Count',
						'Material_Shadows_Array_Pointer',	# 0x28
						'Material_Shadows_Array_Count',
					)
		self.length = 0x30
		self.childClassIdentities = { 0: 'MapGeneralPointsArray', 2: 'MapGameObjectsArray' }
		self._siblingsChecked = True


class MapGeneralPointsArray( structBase ):

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'General Points Array ' + uHex( 0x20 + args[1] )
		self._siblingsChecked = True

		# Check the parent's General_Points_Array_Count to see how many elements should be in this array structure
		parentOffset = self.getAnyDataSectionParent()
		parentStruct = self.dat.initSpecificStruct( MapHeadObjDesc, parentOffset )
		self.entryCount = parentStruct.getValues()[1]

		fields = (  'Map_Joint_Group_Parent_Pointer',	# Has a child with 'n' siblings
					'Map_Point_Types_Array_Pointer',
					'Map_Point_Types_Array_Count'		# 1-indexed
				)

		# Use the above info to dynamically rebuild this struct's properties
		self.formatting = '>' + ( 'III' * self.entryCount )
		self.fields = fields * self.entryCount
		self.length = 0xC * self.entryCount
		self.childClassIdentities = {}
		for i in range( 0, len(self.fields), 3 ):
			self.childClassIdentities[i] = 'JointObjDesc'
			self.childClassIdentities[i+1] = 'MapPointTypesArray'


class MapPointTypesArray( structBase ):

	enums = { 'Point_Type': OrderedDict([
				( 0, 'Player 1 Spawn' ), ( 1, 'Player 2 Spawn' ), ( 2, 'Player 3 Spawn' ), ( 3, 'Player 4 Spawn' ), 
				( 4, 'Player 1 Respawn' ), ( 5, 'Player 2 Respawn' ), ( 6, 'Player 3 Respawn' ), ( 7, 'Player 4 Respawn' ), 
				( 127, 'Item Spawn 1' ), ( 128, 'Item Spawn 2' ), ( 129, 'Item Spawn 3' ), ( 130, 'Item Spawn 4' ), 
				( 131, 'Item Spawn 5' ), ( 132, 'Item Spawn 6' ), ( 133, 'Item Spawn 7' ), ( 134, 'Item Spawn 8' ), 
				( 135, 'Item Spawn 9' ), ( 136, 'Item Spawn 10' ), ( 137, 'Item Spawn 11' ), ( 138, 'Item Spawn 12' ), 
				( 139, 'Item Spawn 13' ), ( 140, 'Item Spawn 14' ), ( 141, 'Item Spawn 15' ), ( 142, 'Item Spawn 16' ), 
				( 143, 'Item Spawn 17' ), ( 144, 'Item Spawn 18' ), ( 145, 'Item Spawn 19' ), ( 146, 'Item Spawn 20' ), 
				( 148, 'Delta Camera Angle' ), 
				( 149, 'Top-Left Camera Limit' ), ( 150, 'Bottom-Right Camera Limit' ), ( 151, 'Top-Left Blast-Zone' ), ( 152, 'Bottom-Right Blast-Zone' ), 
				( 153, 'Stage Clear Point' ), # Seen as exit points for stages such as All-Star Heal and F-Zero Grand Prix
				( 199, 'Target 1' ), ( 200, 'Target 2' ), ( 201, 'Target 3' ), ( 202, 'Target 4' ), ( 203, 'Target 5' ), 
				( 204, 'Target 6' ), ( 205, 'Target 7' ), ( 206, 'Target 8' ), ( 207, 'Target 9' ), ( 208, 'Target 10' )
			]) }

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Point Types Array ' + uHex( 0x20 + args[1] )
		self._siblingsChecked = True
		self._childrenChecked = True

		# Check how many elements should be in this array structure
		parentOffset = self.getAnyDataSectionParent()
		parentStruct = self.dat.initSpecificStruct( MapGeneralPointsArray, parentOffset )
		parentValues = parentStruct.getValues()
		for i, value in enumerate( parentValues ):
			if value == self.offset: 
				self.entryCount = parentValues[i+1]
				break

		# Use the above info to dynamically rebuild this struct's properties
		self.formatting = '>' + ( 'HH' * self.entryCount )
		self.fields = ( 'Joint_Object_Index', 'Point_Type' ) * self.entryCount
		self.length = 4 * self.entryCount
		self.childClassIdentities = {}


class MapGameObjectsArray( structBase ):	# Makes up an array of GOBJs (a.k.a. GroupObj/GenericObj)

	# Some details on this structure can be found here: https://smashboards.com/threads/melee-dat-format.292603/post-23774149

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Game Objects Array ' + uHex( 0x20 + args[1] )
		self._siblingsChecked = True

		# Check the parent's Game_Objects_Array_Count to see how many elements should be in this array structure
		parentOffset = self.getAnyDataSectionParent()
		parentStruct = self.dat.initSpecificStruct( MapHeadObjDesc, parentOffset )
		self.entryCount = parentStruct.getValues()[3]

		# Need to set some properties at instance level, rather than usual class level, since they can change
		fields = (	'Root_Joint_Pointer',				# 0x0
					'Joint_Anim._Struct_Array_Pointer',	# 0x4
					'Material_Anim._Joint_Pointer',		# 0x8
					'Shape_Anim._Joint_Pointer',		# 0xC
					'Camera_Pointer',					# 0x10
					'Unknown_0x14_Pointer',				# 0x14
					'Light_Pointer',					# 0x18
					'Unknown_0x1C_Pointer',				# 0x1C
					'Coll_Anim._Enable_Array_Pointer',	# 0x20		Points to a null-terminated array of 6-byte elements. Relates to moving collision links
					'Coll_Anim._Enable_Array_Count',	# 0x24
					'Anim._Loop_Enable_Array_Pointer',	# 0x28		Points to an array of 1-byte booleans, for enabling animation loops
					'Shadow_Enable_Array_Pointer',		# 0x2C		Points to a null-terminated halfword array
					'Shadow_Enable_Array_Count',		# 0x30
				)	# ^ Repeating block of 0x34 bytes

		# Use the above info to dynamically rebuild this struct's properties
		self.formatting = '>' + ( 'IIIIIIIIIIIII' * self.entryCount )
		self.fields = fields * self.entryCount
		self.length = 0x34 * self.entryCount
		self.childClassIdentities = {}
		for i in range( 0, len(self.fields), 13 ):
			self.childClassIdentities[i] = 'JointObjDesc'
			self.childClassIdentities[i+1] = 'JointAnimStructArray'
			#self.childClassIdentities[i+2] = 'MatAnimJointDesc'
			#self.childClassIdentities[i+4] = 'CameraObjDesc'
			self.childClassIdentities[i+8] = 'MapCollAnimEnableArray'
			self.childClassIdentities[i+10] = 'MapAnimLoopEnableArray'
			self.childClassIdentities[i+11] = 'MapShadowEnableArray'


class MapCollAnimEnableArray( structBase ):

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Collision Animation Enable Array ' + uHex( 0x20 + args[1] )
		self._siblingsChecked = True
		self._childrenChecked = True

		# Check how many elements should be in this array structure
		parentOffset = self.getAnyDataSectionParent()
		parentStruct = self.dat.initSpecificStruct( MapGameObjectsArray, parentOffset )
		getNextValue = False
		for parentValue in parentStruct.getValues():
			if getNextValue:
				self.entryCount = parentValue
				break
			elif parentValue == self.offset: getNextValue = True

		# Use the above info to dynamically rebuild this struct's properties
		self.formatting = '>' + ( 'HHH' * self.entryCount ) + 'H' # +1 null terminator at the end
		fields = [ 'Joint_Object_Index', '', 'Collision_Object_Index' ]
		self.fields = tuple( fields * self.entryCount + ['Null terminator'] )
		self.length = 6 * self.entryCount + 2


class MapAnimLoopEnableArray( structBase ):

	childClassIdentities = {}

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Animation Loop Enable Array ' + uHex( 0x20 + self.offset )
		self._siblingsChecked = True
		self._childrenChecked = True

		# Check how many elements should be in this array structure
		self.entryCount = self.dat.getStructLength( self.offset )

		# Use the above info to dynamically rebuild this struct's properties
		self.formatting = '>' + '?' * self.entryCount # +1 null terminator at the end?
		self.fields = ( 'JObj_Index_Anim._Enable', ) * self.entryCount	# Simply an array of bools
		self.length = self.entryCount


class MapShadowEnableArray( structBase ): # Only found in Ness' BTT stage?

	childClassIdentities = {}

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Shadow Enable Array ' + uHex( 0x20 + self.offset )
		self._siblingsChecked = True
		self._childrenChecked = True

		# Check how many elements should be in this array structure
		parentOffset = self.getAnyDataSectionParent()
		parentStruct = self.dat.initSpecificStruct( MapGameObjectsArray, parentOffset )
		getNextValue = False
		for parentValue in parentStruct.getValues():
			if getNextValue:
				self.entryCount = parentValue
				break
			elif parentValue == self.offset: getNextValue = True

		# Use the above info to dynamically rebuild this struct's properties
		self.formatting = '>' + ( 'H' * self.entryCount ) + 'H' # +1 null terminator at the end
		self.fields = tuple( ['Joint_Object_Index'] * self.entryCount + ['Null terminator'] )
		self.length = 2 * self.entryCount + 2


class MapCollisionData( structBase ):

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Collision Data Struct ' + uHex( 0x20 + args[1] )
		self.formatting = '>IIIIHHHHHHHHHHII'
		self.fields = ( 'Spot_Table_Pointer',				# 0x0  - Each entry is 8 bytes
						'Spot_Table_Entry_Count',			# 0x4
						'Link_Table_Pointer',				# 0x8  - Each entry is 0x10 bytes
						'Link_Table_Entry_Count',			# 0xC
						'First_Top_Link_Index',				# 0x10
						'Top_Links_Count',					# 0x12
						'First_Bottom_Link_Index',			# 0x14
						'Bottom_Links_Count',				# 0x16
						'First_Right_Link_Index',			# 0x18
						'Right_Links_Count',				# 0x1A
						'First_Left_Link_Index',			# 0x1C
						'Left_Links_Count',					# 0x1E
						'Dynamic_Links_Index',				# 0x20
						'Dynamic_Link_Count',				# 0x22
						'Area_Table_Pointer',				# 0x24 - Each entry is 0x28 bytes
						'Area_Table_Entry_Count'			# 0x28
				)
		self.length = 0x2C
		self.childClassIdentities = { 0: 'MapSpotTable', 2: 'MapLinkTable', 14: 'MapAreaTable' }
		self._siblingsChecked = True


class MapSpotTable( structBase ):

	childClassIdentities = {}

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Spot Table ' + uHex( 0x20 + args[1] )
		self._siblingsChecked = True
		self._childrenChecked = True

		# Check the parent's General_Points_Array_Count to see how many elements should be in this array structure
		parentOffset = self.getAnyDataSectionParent()
		parentStruct = self.dat.initSpecificStruct( MapCollisionData, parentOffset )
		self.entryCount = parentStruct.getValues()[1]

		# Use the above info to dynamically rebuild this struct's properties
		self.formatting = '>' + ( 'ff' * self.entryCount )
		self.fields = ( 'Spot_X_Coord', 'Spot_Y_Coord' ) * self.entryCount
		self.length = 8 * self.entryCount

	def getVertices( self ):

		""" Returns a list of vertex objects. """

		valueIterator = iter( self.getValues() )
		return [ Vertex((xCoord, -yCoord, 0)) for xCoord, yCoord in izip(valueIterator, valueIterator) ]


class MapLinkTable( structBase ):

	childClassIdentities = {}
	flags = { 'Physics_Interaction_Flags': OrderedDict([
				( '1<<0', 'Top' ),		# 1
				( '1<<1', 'Bottom' ), 	# 2
				( '1<<2', 'Right' ),	# 4
				( '1<<3', 'Left' ),		# 8
				( '1<<4', 'Disabled' )	# 16
			]),
			  'Ground_Property_Flags': OrderedDict([
			  	( '1<<0', 'Drop-through' ),
			  	( '2<<0', 'Ledge-grabbable' )
			]) }
	
	enums = { 'Material_Enum': OrderedDict([
				( 0, 'Basic' ), ( 1, 'Rock' ), ( 2, 'Grass' ),
				( 3, 'Dirt' ), ( 4, 'Wood' ), ( 5, 'LightMetal' ),
				( 6, 'HeavyMetal' ), ( 7, 'UnkFlatZone' ), ( 8, 'AlienGoop' ),
				( 9, 'Unknown9' ), ( 10, 'Water' ), ( 11, 'Unknown11' ),
				( 12, 'Glass' ), ( 13, 'GreatBay' ), ( 14, 'Unknown14' ),
				( 15, 'Unknown15' ), ( 16, 'FlatZone' ), ( 17, 'Unknown17' ),
				( 18, 'Checkered' )
			]) }

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Link Table ' + uHex( 0x20 + args[1] )
		self._siblingsChecked = True
		self._childrenChecked = True

		# Check the parent's General_Points_Array_Count to see how many elements should be in this array structure
		parentOffset = self.getAnyDataSectionParent()
		parentStruct = self.dat.initSpecificStruct( MapCollisionData, parentOffset )
		self.entryCount = parentStruct.getValues()[3]

		# Need to set some properties at instance level, rather than usual class level, since they can change
		fields = (
			'Starting_Spot_Index', 
			'Ending_Spot_Index',
			'Previous_Link_Index',		# -1 if unused
			'Next_Link_Index',			# -1 if unused
			'First_Virtual_Link_Index',
			'Second_Virtual_Link_Index',
			'Padding',
			'Physics_Interaction_Flags',
			'Ground_Property_Flags',
			'Material_Enum'
		)

		# Use the above info to dynamically rebuild this struct's properties
		self.formatting = '>' + ( 'hhhhhhBBBB' * self.entryCount )
		self.fields = fields * self.entryCount
		self.length = 0x10 * self.entryCount

	def getFaces( self ):

		""" Groups the structure's values into groups of 10, then iterates over them to build collision link objects. """

		self.getValues()
		surfaces = []
		index = 0

		iterRefs = [ iter(self.values) ] * 10 # Making multiple references to the same iterator

		for i1, i2, i3, i4, i5, i6, _, physicsFlags, propertyFlags, materialFlags in zip( *iterRefs ):
			link = ( i1, i2 )
			allSpotIndices = ( i1, i2, i3, i4, i5, i6 )
			surfaces.append( CollissionSurface( link, allSpotIndices, physicsFlags, propertyFlags, materialFlags, index ) )
			index += 1

		return surfaces


class Vertex:
	def __init__(self, points):
		#store x, y, z coordinates
		self.x = points[0]
		self.y = points[1]
		self.z = points[2]

class CollissionSurface:

	def __init__( self, vertexIndices, allSpotIndices, physicsFlags, propertyFlags, materialFlags, index, color='' ):
		self.points = vertexIndices
		self.allSpotIndices = allSpotIndices
		self.physics = physicsFlags
		self.property = propertyFlags
		self.material = MapLinkTable.enums['Material_Enum'].get( materialFlags, 'Unknown' )
		self.index = index

		if not color:
			self.colorByPhysics()
		else:
			self.fill = self.outline = color

	def colorByPhysics( self ):

		""" These are the colors used by vanilla Melee, in Debug Mode (excluding the color for "disabled"). """

		if self.physics & 1: # Top
			self.fill = self.outline = '#c0c0c0' # Gray
		elif self.physics & 2: # Bottom (Ceiling)
			self.fill = self.outline = '#c08080' # Light red
		elif self.physics & 4: # Right
			self.fill = self.outline = '#80c080' # Light green
		elif self.physics & 8: # Left
			self.fill = self.outline = '#8080c0' # Light blue
		else: # Disabled (bit 4 should be set)
			self.fill = self.outline = '#909090' # Darker Gray (arbitrary color, not from in vMelee)


class ColCalcArea: # Areas are used in the game for fast collision calculations

	def __init__( self, vertexIndices ):
		self.points = vertexIndices 	# (bottomLeftX, bottomLeftY, topRightX, topRightY)
		self.fill = ''
		self.outline = 'red'


class MapAreaTable( structBase ): # A.k.a. Line Groups

	childClassIdentities = {}

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Area Table ' + uHex( 0x20 + args[1] )
		self._siblingsChecked = True
		self._childrenChecked = True

		# Check the parent's array count to see how many elements should be in this structure
		parentOffset = self.getAnyDataSectionParent()
		parentStruct = self.dat.initSpecificStruct( MapCollisionData, parentOffset )
		self.entryCount = parentStruct.getValues()[15]
		#print 'entry count for Area Table:', hex( self.entryCount ), 'length:', hex(0x28*self.entryCount), 'apparent length:', hex(self.dat.getStructLength( self.offset ))

		# Need to set some properties at instance level, rather than usual class level, since they can change
		fields = (  'Top_Link_Index', 
					'Top_Links_Count',
					'Bottom_Link_Index', 
					'Bottom_Links_Count',
					'Right_Link_Index', 
					'Right_Links_Count',
					'Left_Link_Index', 
					'Left_Links_Count',
					'Dynamic_Link_Index?',		# <- why not -1 for non-entries?
					'Dynamic_Links_Count?',		# <- why not -1 for non-entries?
					'Bottom-left_X_Coord',
					'Bottom-left_Y_Coord',
					'Top-right_X_Coord',
					'Top-right_Y_Coord',
					'Vertex_Start',
					'Vertex_Count'
				)

		# Use the above info to dynamically rebuild this struct's properties
		self.formatting = '>' + ( 'HHHHHHHHHHffffHH' * self.entryCount )
		self.fields = fields * self.entryCount
		self.length = 0x28 * self.entryCount

	def getAreas( self ):

		""" Groups the structure's values into groups of 15, then iterates over them to build area objects. """

		self.getValues()
		areas = []

		iterRefs = [ iter(self.values) ] * 16 # Making multiple references to the same iterator

		for tLi, tLc, bLi, bLc, rLi, rLc, lLi, lLc, dLi, dLc, botLeftX, botLeftY, topRightX, topRightY, vS, vC in zip( *iterRefs ):
			areas.append( ColCalcArea(( botLeftX, -botLeftY, topRightX, -topRightY )) )

		return areas


class MapGroundParameters( structBase ): # grGroundParam

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Stage Parameters ' + uHex( 0x20 + args[1] )
		self.formatting = '>fIIIIIfffffIIIIffffffffffIHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHIIIIIIIIIII'
		self.fields = ( 'Stage_Scaling',
						'Shadow_Intensity',
						'Camera_FOV_Depth/Delta?',
						'Camera_Zoom_Distance_1',					# min zoom distance?
						'Camera_Zoom_Distance_2',			# 0x10		  max zoom?
						'Minimum_Tilt_and_Tilt_Scaling?',			# FOV_Up?
						'Roll_(Horizontal_Rotation)',				# FOV_Horizontal?
						'Pitch_(Vertical_Rotation)',				# FOV_Vertical?
						'Camera_Fixation',				# 0x20
						'Bubble_Multiplier',
						'Camera_Speed_Smoothness',					# Higher value results in tighter control
						'',
						'Pause_Minimum_Zoom',			# 0x30
						'Pause_Initial_Zoom_Level',
						'Pause_Max_Zoom',
						'Pause_Max_Angle_Up',
						'Pause_Max_Angle_Left',		# 0x40
						'Pause_Max_Angle_Right',
						'Pause_Max_Angle_Down',
						'Fixed_Camera_Mode_Bool',		# 0x4C (1=Enable, 0=Normal Camera)
						'',	'',	'',						# 0x50 (first field)
						'',	'',
						'Padding?',						# 0x64
						'',		'',		'',		'',		# 0x68 - First halfword
						'',		'',		'',		'',
						'',		'',		'',		'',
						'',		'',		'',		'',
						'',		'',		'',		'',
						'',		'',		'',		'',
						'',		'',		'',		'',
						'',		'',		'',		'',
						'',		'',		'',		'',		# Last halfword
						'Music_Table_Pointer',			# 0xB0
						'Music_Table_Entry_Count',
						'RGBA_Bubble_Top-left',			# 0xB8
						'RGBA_Bubble_Top-middle',
						'RGBA_Bubble_Top-right',
						'RGBA_Bubble_Sides-top',
						'RGBA_Bubble_Sides-middle',
						'RGBA_Bubble_Sides-bottom',
						'RGBA_Bubble_Bottom-left',
						'RGBA_Bubble_Bottom-middle',
						'RGBA_Bubble_Bottom-right'
					)
		self.length = 0xDC
		self.childClassIdentities = { 62: 'MapMusicTableEntry' }
		self._siblingsChecked = True


class MapMusicTableEntry( structBase ):

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Music Table ' + uHex( 0x20 + args[1] )
		self.formatting = '>IIiIiHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHI' 
		self.fields = ( 'Stage_ID', 
						'Background_Music_ID',
						'Alt_Background_Music_ID', 		# -1 (FFFFFFFF) if unused
						'SSD_Background_Music_ID',
						'SSD_Alt_Background_Music_ID', 	# 0x10
						'Song_Behavior',				# 0 = has no alt song, 6 = has alt song, 8 = single song
						'Alt_Music_Percent_Chance', 
						'',		'',						# 0x18 - halfwords from here on
						'',		'',
						'',		'',
						'',		'',
						'',		'',
						'',		'',
						'',		'',
						'',		'',
						'',		'',
						'',		'',
						'',		'',
						'',		'',
						'',		'',
						'',		'',
						'',		'',
						'',		'',
						'',		'',
						'',		'',
						'Padding'
					)
		self.childClassIdentities = {}
		self._siblingsChecked = True
		self._childrenChecked = True

		# Check the parent's Music_Table_Entry_Count to see how many entries should be in this table structure
		parentOffset = self.getAnyDataSectionParent()
		parentStruct = self.dat.initSpecificStruct( MapGroundParameters, parentOffset )
		self.entryCount = parentStruct.getValues()[63]
		#print 'entry count for Area Table:', hex( self.entryCount ), 'length:', hex(0x64*self.entryCount), 'apparent length:', hex(self.dat.getStructLength( self.offset ))

		# Use the above info to dynamically rebuild this struct's properties
		self.formatting = '>' + ( self.formatting[1:] * self.entryCount )
		self.fields = self.fields * self.entryCount
		self.length = 0x64 * self.entryCount


class CharSelectScreenDataTable( structBase ):

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Character Select Menu Data Table ' + uHex( 0x20 + args[1] )
		self.formatting = '>IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII'
		self.fields = (  'Unknown_Pointer',
					'Unknown_Pointer',
					'Unknown_Pointer',
					'Unknown_Pointer',
					'Background_Model_Joint_Pointer',	# 0x10
					'Background_Animation_Pointer',
					'',
					'',
					'Hand_Model_Joint_Pointer',			# 0x20
					'',
					'Hand_Material_Anim._Pointer',
					'',
					'Token_Model_Joint_Pointer',		# 0x30
					'',
					'Token_Material_Anim._Pointer',
					'',
					'Menu_Model_Joint_Pointer',			# 0x40
					'Menu_Model_Animation_Pointer',
					'Menu_Material_Anim._Pointer',
					'',
					'Press_Start_Model_Joint_Pointer',	# 0x50
					'Press_Start_Animation_Pointer',
					'Press_Start_Mat._Anim._Pointer',
					'',
					'Debug_Camera_Model_Joint_Pointer',	# 0x60
					'',
					'Debug_Camera_Mat._Anim._Pointer',
					'',
					'1P_Mode_Menu_Model_Joint_Pointer',	# 0x70
					'1P_Mode_Menu_Animation_Pointer',
					'1P_Mode_Menu_Mat._Anim._Pointer',
					'',
					'1P_Mode_Options_Model_Pointer',	# 0x80
					'',
					'',
					'',
					'CSP_Model_Joint_Pointer',			# 0x90
					'',
					'CSP_Material_Anim._Pointer',
					''
				)
		self.length = 0xA0
		self.childClassIdentities = { 4: 'JointObjDesc', 5: 'JointAnimationDesc', # Background
								8: 'JointObjDesc', 10: 'MatAnimJointDesc',  # Hand
								12: 'JointObjDesc', 14: 'MatAnimJointDesc',  # Token
								16: 'JointObjDesc', 17: 'JointAnimationDesc', 18: 'MatAnimJointDesc', # Menu Model
								20: 'JointObjDesc', 21: 'JointAnimationDesc', 22: 'MatAnimJointDesc', # 'Press Start' overlay
								24: 'JointObjDesc', 26: 'MatAnimJointDesc',  # Debug Camera
								28: 'JointObjDesc', 29: 'JointAnimationDesc', 30: 'MatAnimJointDesc', # 1P Mode Menu Model
								32: 'JointObjDesc', 		# 1P Mode Menu Options
								36: 'JointObjDesc', 38: 'MatAnimJointDesc' } # CSPs
		self._siblingsChecked = True


class JointAnimStructArray( structBase ):

	""" Null-terminated array of pointers to JointAnimationDesc structures. """

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Joint Animation Struct Array ' + uHex( 0x20 + args[1] )
		self._siblingsChecked = True

		# Check the length of the struct to see how many elements should be in this structure
		structLength = self.dat.getStructLength( self.offset )
		self.entryCount = structLength / 4

		# Use the above info to dynamically build this struct's basic properties
		self.formatting = '>' + ( 'I' * self.entryCount )
		self.fields = ( 'Joint_Anim._Struct_Pointer', ) * ( self.entryCount - 1 ) + ( 'Null Terminator', )
		self.length = structLength
		self.childClassIdentities = {}
		for i in range( 0, self.entryCount - 1 ):
			self.childClassIdentities[i] = 'JointAnimationDesc'


class JointAnimationDesc( structBase ): # A.k.a. Joint Animation Joint

	animationTracks = { 
		1: 'HSD_A_J_ROTX', 2: 'HSD_A_J_ROTY', 3: 'HSD_A_J_ROTZ', 4: 'HSD_A_J_PATH', # Rotation, Path
		5: 'HSD_A_J_TRAX', 6: 'HSD_A_J_TRAY', 7: 'HSD_A_J_TRAZ', # Translation
		8: 'HSD_A_J_SCAX', 9: 'HSD_A_J_SCAY', 0xA: 'HSD_A_J_SCAZ', 0xB: 'HSD_A_J_NODE', 0xC: 'HSD_A_J_BRANCH',  # Scale, Node, Branch
		0x14: 'HSD_A_J_SETBYTE0', 0x15: 'HSD_A_J_SETBYTE1', 0x16: 'HSD_A_J_SETBYTE2', 0x17: 'HSD_A_J_SETBYTE3', 0x18: 'HSD_A_J_SETBYTE4', 
		0x19: 'HSD_A_J_SETBYTE5', 0x1A: 'HSD_A_J_SETBYTE6', 0x1B: 'HSD_A_J_SETBYTE7', 0x1C: 'HSD_A_J_SETBYTE8', 0x1D: 'HSD_A_J_SETBYTE9', 
		0x1E: 'HSD_A_J_SETFLOAT0', 0x1F: 'HSD_A_J_SETFLOAT1', 0x20: 'HSD_A_J_SETFLOAT2', 0x21: 'HSD_A_J_SETFLOAT3', 0x22: 'HSD_A_J_SETFLOAT4', 
		0x23: 'HSD_A_J_SETFLOAT5', 0x24: 'HSD_A_J_SETFLOAT6', 0x25: 'HSD_A_J_SETFLOAT7', 0x26: 'HSD_A_J_SETFLOAT8', 0x27: 'HSD_A_J_SETFLOAT9', 
	}

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Joint Animation Struct ' + uHex( 0x20 + args[1] )
		self.formatting = '>IIIII'
		self.fields = ( 'Child_Pointer',
						'Next_Sibling_Pointer',
						'Anim._Object_Pointer',
						'',
						''
					)
		self.length = 0x14
		self.childClassIdentities = { 0: 'JointAnimationDesc', 1: 'JointAnimationDesc', 2: 'AnimationObjectDesc' }

	def validated( self, deducedStructLength=-1 ):
		prelimCheck = super( JointAnimationDesc, self ).validated( False, deducedStructLength )
		if not prelimCheck: return False

		# Check for and initialize a child Animation Obj, if present
		animObjOffset = self.getValues()[2]

		if animObjOffset == 0: # Can't glean any more here (valid so far)
			self.provideChildHints()
			return True
		else:
			if not animObjOffset in self.dat.structs:
				self.dat.structs[animObjOffset] = 'AnimationObjectDesc' # Adding a hint to permit this struct to be created even if it's all null data
			animObj = self.dat.initSpecificStruct( AnimationObjectDesc, animObjOffset, self.offset, printWarnings=False )
			if not animObj: return False

			self.provideChildHints()
			return True


class MatAnimJointDesc( structBase ):

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Material Animation Joint ' + uHex( 0x20 + args[1] )
		self.formatting = '>III'
		self.fields = (  'Child_Pointer', 'Next_Sibling_Pointer', 'Mat._Anim._Struct_Pointer' )
		self.length = 0xC
		self.childClassIdentities = { 0: 'MatAnimJointDesc', 1: 'MatAnimJointDesc', 2: 'MatAnimDesc' }

	def validated( self, deducedStructLength=-1 ):
		prelimCheck = super( MatAnimJointDesc, self ).validated( False, deducedStructLength )
		if not prelimCheck: return False

		# Check for and initialize a child Animation Obj, if present
		childMatAnimOffset, _, matAnimObjOffset = self.getValues()

		if childMatAnimOffset != 0 or self.offset in self.dat.pointerOffsets:
			# Try to initialize the child for further validation
			if not childMatAnimOffset in self.dat.structs:
				self.dat.structs[childMatAnimOffset] = 'MatAnimJointDesc' # Adding a hint to permit this struct to be created even if it's all null data
			matAnimObj = self.dat.initSpecificStruct( MatAnimJointDesc, childMatAnimOffset, self.offset, printWarnings=False )
			if not matAnimObj:
				#print 'Struct', hex(0x20+self.offset) , 'invalidated as', self.__class__.__name__, 'due to child at', hex(0x20+childMatAnimOffset)
				return False

		if matAnimObjOffset != 0 or self.offset + 8 in self.dat.pointerOffsets:
			# Try to initialize the child for further validation
			if not matAnimObjOffset in self.dat.structs:
				self.dat.structs[matAnimObjOffset] = 'MatAnimDesc' # Adding a hint to permit this struct to be created even if it's all null data
			matAnimObj = self.dat.initSpecificStruct( MatAnimDesc, matAnimObjOffset, self.offset, printWarnings=False )
			if not matAnimObj:
				#print 'Struct', hex(0x20+self.offset) , 'invalidated as', self.__class__.__name__, 'due to child at', hex(0x20+matAnimObjOffset)
				return False
		
		self.provideChildHints()
		return True


class MatAnimDesc( structBase ):

	animationTracks = { 
		1: 'HSD_A_M_AMBIENT_R', 2: 'HSD_A_M_AMBIENT_G', 3: 'HSD_A_M_AMBIENT_B', # Ambience RGB
		4: 'HSD_A_M_DIFFUSE_R', 5: 'HSD_A_M_DIFFUSE_G', 6: 'HSD_A_M_DIFFUSE_B', # Diffusion RGB
		7: 'HSD_A_M_SPECULAR_R', 8: 'HSD_A_M_SPECULAR_G', 9: 'HSD_A_M_SPECULAR_B', 0xA: 'HSD_A_M_ALPHA', # Specular RGB, Transparency
	}

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Material Animation Struct ' + uHex( 0x20 + args[1] )
		self.formatting = '>IIII'
		self.fields = (  'Next_Sibling_Pointer', 'Anim._Object_Pointer', 'Texture_Anim._Pointer', 'Render_Anim._Pointer' )
		self.length = 0x10
		self.childClassIdentities = { 0: 'MatAnimDesc', 1: 'AnimationObjectDesc', 2: 'TexAnimDesc' }

	def validated( self, deducedStructLength=-1 ):
		prelimCheck = super( MatAnimDesc, self ).validated( False, deducedStructLength )
		if not prelimCheck: return False

		# Check for and initialize a child Animation Obj, if present
		animObjOffset = self.getValues()[1]

		if animObjOffset == 0: # Can't glean any more here (valid so far)
			self.provideChildHints()
			return True
		else:
			if not animObjOffset in self.dat.structs:
				self.dat.structs[animObjOffset] = 'AnimationObjectDesc' # Adding a hint to permit this struct to be created even if it's all null data
			animObj = self.dat.initSpecificStruct( AnimationObjectDesc, animObjOffset, self.offset, printWarnings=False )
			if not animObj:
				#print self.name, 'invalidated as', self.__class__.__name__, 'due to child at', hex(0x20+animObjOffset)
				return False

			self.provideChildHints()
			return True


class AnimationObjectDesc( structBase ):

	flags = { 'Animation_Flags': OrderedDict([
				( '1<<26', 'ANIM_REWINDED' ),
				( '1<<27', 'FIRST_PLAY' ),
				( '1<<28', 'NO_UPDATE' ),
				( '1<<29', 'ANIM_LOOP' ),
				( '1<<30', 'NO_ANIM' )
			]) }

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Animation Object ' + uHex( 0x20 + args[1] )
		self.formatting = '>IfII'
		self.fields = ( 'Animation_Flags', 'End_Frame', 'Frame_Object_Pointer', 'Object_ID' )
		self.length = 0x10
		self.childClassIdentities = { 2: 'FrameObjDesc' }
		self._siblingsChecked = True


class TexAnimDesc( structBase ):

	animationTracks = {
		1: 'HSD_A_T_TIMG', 2: 'HSD_A_T_TRAU', 3: 'HSD_A_T_TRAV', 4: 'HSD_A_T_SCAU', 5: 'HSD_A_T_SCAV', 
		6: 'HSD_A_T_ROTX', 7: 'HSD_A_T_ROTY', 8: 'HSD_A_T_ROTZ', 9: 'HSD_A_T_BLEND', 0xA: 'HSD_A_T_TCLT', 
	}

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Texture Animation Struct ' + uHex( 0x20 + args[1] )
		self.formatting = '>IIIIIHH'
		self.fields = ( 'Next_Sibling_Pointer', 
						'GXTexMapID', 
						'Anim._Object_Pointer',
						'Image_Header_Array_Pointer',
						'Palette_Header_Array_Pointer',
						'Image_Header_Array_Count',
						'Palette_Header_Array_Count'
					)
		self.length = 0x18
		self.childClassIdentities = { 0: 'TexAnimDesc', 2: 'AnimationObjectDesc', 3: 'ImageHeaderArray', 4: 'PaletteHeaderArray' }


class FrameObjDesc( structBase ):

	# Great detail on this structure can be found here: https://smashboards.com/threads/melee-dat-format.292603/post-23487048

	dataTypes = {   0: ( 'Float', '>f', 4 ),
					1: ( 'Signed Halfword', '<h', 2 ), # Bytes reversed (little-endian)
					2: ( 'Unsigned Halfword', '<H', 2 ), # Bytes reversed (little-endian)
					3: ( 'Signed Byte', 'b', 1 ),
					4: ( 'Unsigned Byte', 'B', 1 ) }

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Frame Object ' + uHex( 0x20 + args[1] )
		self.formatting = '>IIfBBBBI'
		self.fields = ( 'Next_Sibling_Pointer',
						'Data_String_Length',
						'Start_Frame',
						'Track_Type',
						'Data_Type_and_Scale',
						'Slope_Data_Type_and_Scale',
						'Padding',
						'Data_String_Pointer'
					)
		self.length = 0x14
		self.childClassIdentities = { 0: 'FrameObjDesc', -1: 'FrameDataBlock' }


class ImageHeaderArray( structBase ):

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Image Data Header Array ' + uHex( 0x20 + args[1] )
		self._siblingsChecked = True

		# Check the parent's array count to see how many elements should be in this structure
		parentOffset = self.getAnyDataSectionParent()
		parentStruct = self.dat.initSpecificStruct( TexAnimDesc, parentOffset )
		#assert parentOffset, 'Unable to initialize the parent struct of ' + self.name + ' (' + hex(0x20+parentOffset) + ')'
		#print 'initialized a', parentStruct.__class__.__name__, ' parent for', self.name
		self.entryCount = parentStruct.getValues()[-2]

		# Use the above info to dynamically build this struct's basic properties
		self.formatting = '>' + ( 'I' * self.entryCount )
		self.fields = ( 'Image_Header_Pointer', ) * self.entryCount
		self.length = 4 * self.entryCount
		self.childClassIdentities = {}
		for i in range( 0, self.entryCount ):
			self.childClassIdentities[i] = 'ImageObjDesc'


class PaletteHeaderArray( structBase ):

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Palette Data Header Array ' + uHex( 0x20 + args[1] )
		self._siblingsChecked = True

		# Check the parent's array count to see how many elements should be in this structure
		parentOffset = self.getAnyDataSectionParent()
		parentStruct = self.dat.initSpecificStruct( TexAnimDesc, parentOffset )
		self.entryCount = parentStruct.getValues()[-1]

		# Use the above info to dynamically build this struct's basic properties
		self.formatting = '>' + ( 'I' * self.entryCount )
		self.fields = ( 'Palette_Header_Pointer', ) * self.entryCount
		self.length = 4 * self.entryCount
		self.childClassIdentities = {}
		for i in range( 0, self.entryCount ):
			self.childClassIdentities[i] = 'PaletteObjDesc'


class SwordColorsDesc( structBase ):

	def __init__( self, *args, **kwargs ):
		structBase.__init__( self, *args, **kwargs )

		self.name = 'Sword Swing Colors ' + uHex( 0x20 + args[1] )
		self.formatting = '>IBBBBBBBB'
		self.fields = ( 'Identifier', 
						'Ending_Alpha', 
						'Starting_Alpha',
						'Edge Red Channel', 'Edge Green Channel', 'Edge Blue Channel',
						'Center Red Channel', 'Center Green Channel', 'Center Blue Channel' )
		self.length = 0xC
		self.childClassIdentities = {}
		self._siblingsChecked = True
		self._childrenChecked = True



CommonStructureClasses = ( JointObjDesc, MaterialObjDesc, DisplayObjDesc, TextureObjDesc ) # re-add ImageObjDesc?
AnimationStructureClasses = ( JointAnimationDesc, MatAnimJointDesc )
SpecificStructureClasses = { 'map_head': MapHeadObjDesc, 'coll_data': MapCollisionData, 'grGroundParam': MapGroundParameters,
							 'MnSelectChrDataTable': CharSelectScreenDataTable }


# Ensure that structure classes are set up properly; the number of 
# fields should be the same as the number of format identifiers
# if __name__ == '__main__':

# 	for module in sys.modules[__name__]:
# 		print module

# 	for structClass in CommonStructureClasses:
# 		if len( structClass.fields ) != len( structClass.formatting ) - 1: # -1 accounts for byte order indicator
# 			raise ValueError( "Struct format length does not match number of field names for {}.".format(structClass.__class__.__name__) )
# 	else:
# 		print 'Struct format lengths match.'
# 		raw_input( 'Press Enter to exit.' )

# for name, obj in inspect.getmembers( sys.modules[__name__] ):
# 	if inspect.isclass( obj ) and issubclass( obj, (structBase,) ):
# 		#print name, ':'
# 		print( obj )