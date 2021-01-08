#!/usr/bin/python
# This file's encoding: UTF-8, so that non-ASCII characters can be used in strings.

							# ------------------------------------------------------------------- #
						   # ~ ~      Written by DRGN of SmashBoards (Daniel R. Cappel)        ~ ~ #
							#     -     -     -     -   [ Feb., 2015 ]   -     -     -     -      #
							 #     -     -    [ Python v2.7.12 and Tkinter 8.5 ]    -     -      #
							  # --------------------------------------------------------------- #

from ScrolledText import ScrolledText
import hsdStructures
import Tkinter as Tk
import math
import ttk

version = 1.1


def uHex( integer ): # Quick conversion to have a hex function which shows uppercase characters.
	return '0x' + hex( integer )[2:].upper()

def humansize(nbytes): # Used for converting file sizes, in terms of human readability.
	suffixes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']

	if nbytes == 0: return '0 B'
	i = 0
	while nbytes >= 1024 and i < len(suffixes)-1:
		nbytes /= 1024.
		i += 1
	f = ('%.2f' % nbytes).rstrip('0').rstrip('.')
	return '%s %s' % (f, suffixes[i])

def getWindowGeometry( topLevelWindow ): 

	""" Analyzes a Tkinter.Toplevel window to get size and location info, relative to the screen.
		Returns a tuple of ( width, height, distanceFromScreenLeft, distanceFromScreenTop ) """

	try:
		dimensions, topDistance, leftDistance = topLevelWindow.geometry().split( '+' )
		width, height = dimensions.split( 'x' )
		geometry = ( int(width), int(height), int(topDistance), int(leftDistance) ) # faster than above line
	except:
		raise ValueError( "Failed to parse window geometry string: " + topLevelWindow.geometry() )

	return geometry


class basicWindow( object ): # Could have done this ages ago. todo: expand on this and use it for other windows

	""" Basic user window setup. Provides a title, a window with small border framing, size/position 
		configuration, a mainFrame frame widget for attaching contents to, and a built-in close method. 

			'dimensions' are window dimentions, which can be supplied as a tuple of (width, height)
			'offsets' relate to window spawning position, which is relative to the main program window,
				and can be supplied as a tuple of (leftOffset, topOffset). """

	def __init__( self, topLevel, windowTitle='', dimensions='auto', offsets='auto', resizable=False, topMost=True, minsize=(-1, -1) ):
		self.window = Tk.Toplevel( topLevel )
		self.window.title( windowTitle )
		self.window.attributes( '-toolwindow', 1 ) # Makes window framing small, like a toolbox/widget.
		self.window.resizable( width=resizable, height=resizable )
		if topMost:
			self.window.wm_attributes( '-topmost', 1 )

		rootDistanceFromScreenLeft, rootDistanceFromScreenTop = getWindowGeometry( topLevel )[2:]

		# Set the spawning position of the new window (usually such that it's over the program)
		if offsets == 'auto':
			topOffset = rootDistanceFromScreenTop + 180
			leftOffset = rootDistanceFromScreenLeft + 180
		else:
			leftOffset, topOffset = offsets
			topOffset += rootDistanceFromScreenTop
			leftOffset += rootDistanceFromScreenLeft

		# Set/apply the window width/height and spawning position
		if dimensions == 'auto':
			self.window.geometry( '+{}+{}'.format(leftOffset, topOffset) )
		else:
			width, height = dimensions
			self.window.geometry( '{}x{}+{}+{}'.format(width, height, leftOffset, topOffset) )
		self.window.focus()

		# Apply minimum window sizes, if provided
		if minsize[0] != -1:
			self.window.minsize( width=minsize[0], height=minsize[1] )

		self.mainFrame = ttk.Frame( self.window, padding=4 ) # todo: depricate this? just attach to self.window
		self.mainFrame.pack( fill='both', expand=True )

		self.window.protocol( 'WM_DELETE_WINDOW', self.close ) # Overrides the 'X' close button.

	def close( self ):
		self.window.destroy()


class CopyableMessageWindow( basicWindow ):

	""" Creates a modeless (non-modal) message window that allows the user to copy the presented text. """

	def __init__( self, topLevel, message, title, align, buttons, makeModal ):
		self.guiRoot = topLevel

		basicWindow.__init__( self, topLevel, title, resizable=True, topMost=False )

		linesInMessage = len( message.splitlines() )
		if linesInMessage > 17: height = 22
		else: height = linesInMessage + 5

		self.messageText = ScrolledText( self.mainFrame, relief='groove', wrap='word', height=height )
		self.messageText.insert( '1.0', '\n' + message )
		self.messageText.tag_add( 'All', '1.0', 'end' )
		self.messageText.tag_config( 'All', justify=align )
		self.messageText.pack( fill='both', expand=1 )

		# Add the buttons
		self.buttonsFrame = Tk.Frame(self.mainFrame)
		ttk.Button( self.buttonsFrame, text='Close', command=self.close ).pack( side='right', padx=5 )
		if buttons:
			for button in buttons:
				buttonText, buttonCommand = button
				ttk.Button( self.buttonsFrame, text=buttonText, command=buttonCommand ).pack( side='right', padx=5 )
		ttk.Button( self.buttonsFrame, text='Copy text to Clipboard', command=self.copyText ).pack( side='right', padx=5 )
		self.buttonsFrame.pack( pady=3 )

		if makeModal:
			self.window.grab_set()
			self.guiRoot.wait_window( self.window )

	# Button functions
	def copyText( self ):
		self.guiRoot.clipboard_clear()
		self.guiRoot.clipboard_append( self.messageText.get('1.0', 'end').strip() )


class PopupEntryWindow( basicWindow ):

	""" Provides a very basic window for just text entry and Ok/Cancel buttons. """

	def __init__( self, master, message='', defaultText='', title='', width=100 ):
		basicWindow.__init__( self, master, title )

		# Add the Entry widget for user input
		self.label = ttk.Label( self.window, text=message )
		self.label.pack( pady=5 )
		self.entry = ttk.Entry( self.window, width=width )
		self.entry.insert( 'end', defaultText )
		self.entry.pack( padx=5 )
		self.entry.bind( '<Return>', self.cleanup )

		# Add the buttons
		buttonsFrame = ttk.Frame( self.window )
		self.okButton = ttk.Button( buttonsFrame, text='Ok', command=self.cleanup )
		self.okButton.pack( side='left', padx=10 )
		ttk.Button( buttonsFrame, text='Cancel', command=self.cancel ).pack( side='left', padx=10 )
		self.window.protocol( 'WM_DELETE_WINDOW', self.cancel ) # Overrides the 'X' close button.
		buttonsFrame.pack( pady=5 )
		self.entryText = ''

		# Move focus to this window (for keyboard control), and pause execution of the calling function until this window is closed.
		self.entry.focus_set()
		master.wait_window( self.window ) # Pauses execution of the calling function until this window is closed.

	def cleanup( self, event='' ):
		self.entryText = self.entry.get()
		self.window.destroy()

	def cancel( self, event='' ):
		self.entryText = ''
		self.window.destroy()


class HexEditEntry( Tk.Entry ):

	""" Used for struct hex/value display and editing. 
		"dataOffsets" will typically be a single int value, but can be a list of offsets. """

	def __init__( self, parent, dataOffsets, byteLength, formatting, updateName ):
		Tk.Entry.__init__( self, parent,
			width=byteLength*2+2, 
			justify='center', 
			relief='flat', 
			highlightbackground='#b7becc', 	# Border color when not focused
			borderwidth=1, 
			highlightthickness=1, 
			highlightcolor='#0099f0' )

		self.offsets 	= dataOffsets		# May be a single file offset (int), or a list of them
		self.byteLength = byteLength
		self.formatting = formatting
		self.updateName = updateName


class HexEditDropdown( ttk.OptionMenu ):

	""" Used for struct data display and editing, using a predefined set of choices. Similar to the 
		HexEditEntry class, except that the widget's contents/values must be given during initialization. 
		"options" should be a dictionary, where each key is a string to display as an option in this
		widget, and the corresponding values are the data values to edit/update in the target file.
		"dataOffsets" will typically be a single int value, but can be a list of offsets. """

	def __init__( self, parent, dataOffsets, byteLength, formatting, updateName, options, defaultOption=None, **kwargs ):

		if defaultOption:
			# If the default option given is a value (or non-string), translate it to the string
			if type( defaultOption ) != str:
				for key, value in options.items():
					if value == defaultOption:
						defaultOption = key
						break
				else: # Above loop didn't break; couldn't find the provided value
					raise IOError( 'Invalid default option value for a HexEditDropdown: ' + str(defaultOption) )
		else:
			defaultOption = options.keys()[0]

		# Replace the command, if provided, with a lambda function, so its callback behaves like an Entry widget's
		callBack = kwargs.get( 'command', None )
		if callBack:
			kwargs['command'] = lambda currentString: callBack( self )

		# Create the widget
		self.selectedString = Tk.StringVar()
		ttk.OptionMenu.__init__( self, parent, self.selectedString, defaultOption, *options, **kwargs )

		self.offsets 	= dataOffsets		# May be a single file offset (int), or a list of them
		self.byteLength = byteLength
		self.formatting = formatting
		self.updateName = updateName

		self.options = options				# Dict of the form, key=stringToDisplay, value=dataToSave

	def get( self ): # Overriding the original get method, which would get the string, not the associated value
		return self.options[self.selectedString.get()]


class ImageDataLengthCalculator( basicWindow ):

	def __init__( self, root ):
		basicWindow.__init__( self, root, 'Image Data Length Calculator' )

		# Set up the input elements
		# Width
		ttk.Label( self.mainFrame, text='Width:' ).grid( column=0, row=0, padx=5, pady=2, sticky='e' )
		self.widthEntry = ttk.Entry( self.mainFrame, width=5, justify='center' )
		self.widthEntry.grid( column=1, row=0, padx=5, pady=2 )
		# Height
		ttk.Label( self.mainFrame, text='Height:' ).grid( column=0, row=1, padx=5, pady=2, sticky='e' )
		self.heightEntry = ttk.Entry( self.mainFrame, width=5, justify='center' )
		self.heightEntry.grid( column=1, row=1, padx=5, pady=2 )
		# Input Type
		ttk.Label( self.mainFrame, text='Image Type:' ).grid( column=0, row=2, padx=5, pady=2, sticky='e' )
		self.typeEntry = ttk.Entry( self.mainFrame, width=5, justify='center' )
		self.typeEntry.grid( column=1, row=2, padx=5, pady=2 )
		# Result Multiplier
		ttk.Label( self.mainFrame, text='Result Multiplier:' ).grid( column=0, row=3, padx=5, pady=2, sticky='e' )
		self.multiplierEntry = ttk.Entry( self.mainFrame, width=5, justify='center' )
		self.multiplierEntry.insert( 0, '1' ) # Default
		self.multiplierEntry.grid( column=1, row=3, padx=5, pady=2 )

		# Bind the event listeners for calculating the result
		for inputWidget in [ self.widthEntry, self.heightEntry, self.typeEntry, self.multiplierEntry ]:
			inputWidget.bind( '<KeyRelease>', self.calculateResult )

		# Set the output elements
		ttk.Label( self.mainFrame, text='Required File or RAM space:' ).grid( column=0, row=4, columnspan=2, padx=20, pady=5 )
		# In hex bytes
		self.resultEntryHex = ttk.Entry( self.mainFrame, width=20, justify='center' )
		self.resultEntryHex.grid( column=0, row=5, padx=5, pady=5 )
		ttk.Label( self.mainFrame, text='bytes (hex)' ).grid( column=1, row=5, padx=5, pady=5 )
		# In decimal bytes
		self.resultEntryDec = ttk.Entry( self.mainFrame, width=20, justify='center' )
		self.resultEntryDec.grid( column=0, row=6, padx=5, pady=5 )
		ttk.Label( self.mainFrame, text='(decimal)' ).grid( column=1, row=6, padx=5, pady=5 )

	def calculateResult( self, event ):
		try: 
			widthValue = self.widthEntry.get()
			if not widthValue: return
			elif '0x' in widthValue: width = int( widthValue, 16 )
			else: width = int( widthValue )

			heightValue = self.heightEntry.get()
			if not heightValue: return
			elif '0x' in heightValue: height = int( heightValue, 16 )
			else: height = int( heightValue )

			typeValue = self.typeEntry.get()
			if not typeValue: return
			elif '0x' in typeValue: _type = int( typeValue, 16 )
			else: _type = int( typeValue )

			multiplierValue = self.multiplierEntry.get()
			if not multiplierValue: return
			elif '0x' in multiplierValue: multiplier = int( multiplierValue, 16 )
			else: multiplier = float( multiplierValue )

			# Calculate the final amount of space required.
			imageDataLength = hsdStructures.ImageDataBlock.getDataLength( width, height, _type )
			finalSize = int( math.ceil(imageDataLength * multiplier) ) # Can't have fractional bytes, so we're rounding up

			self.resultEntryHex.delete( 0, 'end' )
			self.resultEntryHex.insert( 0, uHex(finalSize) )
			self.resultEntryDec.delete( 0, 'end' )
			self.resultEntryDec.insert( 0, humansize(finalSize) )
		except:
			self.resultEntryHex.delete( 0, 'end' )
			self.resultEntryHex.insert( 0, 'Invalid Input' )
			self.resultEntryDec.delete( 0, 'end' )


class DisguisedEntry( Tk.Entry ):
	
	""" An Entry field that blends into its surroundings until hovered over. """

	def __init__( self, parent=None, respectiveLabel=None, background='SystemButtonFace', *args, **kwargs ):
		self.respectiveLabel = respectiveLabel
		self.bindingsCreated = False

		# Define some colors
		self.initialBgColor = background

		# Create the Entry widget
		Tk.Entry.__init__( self, parent, relief='flat', borderwidth=2, background=background, *args, **kwargs ) #background=self.defaultSystemBgColor,

		self.respectiveLabel.configure( cursor='' )
		self.configure( cursor='' )

	def enableBindings( self ):
		if not self.bindingsCreated:
			self.bind( '<Enter>', self.onMouseEnter, '+' )
			self.bind( '<Leave>', self.onMouseLeave, '+' )

			if self.respectiveLabel: # The + argument preserves past bindings
				self.respectiveLabel.bind( '<Enter>', self.onMouseEnter, '+' )
				self.respectiveLabel.bind( '<Leave>', self.onMouseLeave, '+' )
				self.respectiveLabel.bind( '<1>', self.focusThisWid, '+' )
			self.bindingsCreated = True

	def enableEntry( self ):
		self['state'] = 'normal'
		self.enableBindings()
		self.respectiveLabel.configure( cursor='hand2' )
		self.configure( cursor='xterm' )

	def disableEntry( self ):
		self['state'] = 'disabled'
		self.respectiveLabel.configure( cursor='' )
		self.configure( cursor='' )

	# Define the event handlers
	def onMouseEnter( self, event ):
		if self['state'] == 'normal':
			self.config( relief='sunken' )
			if not self['background'] == '#faa': # Don't change the background color if it indicates pending change saves
				self.config( background='#ffffff' )
	def onMouseLeave( self, event ):
		self.config( relief='flat' )
		if not self['background'] == '#faa': # Don't change the background color if it indicates pending change saves
			self.config( background=self.initialBgColor )
	def focusThisWid( self, event ):
		if self['state'] == 'normal': self.focus()


class VerticalScrolledFrame( Tk.Frame ):

	""" Provides a simple vertical scrollable area, for space for other widgets.

		* Use the 'interior' attribute to place widgets inside the scrollable frame
		* Construct and pack/place/grid normally """

	def __init__(self, parent, *args, **kw):
		Tk.Frame.__init__(self, parent, *args, **kw)

		# create a canvas object, and a vertical scrollbar for scrolling it
		self.vscrollbar = Tk.Scrollbar( self, orient='vertical' )
		self.vscrollbar.pack( fill='y', side='right', expand=False )
		self.canvas = Tk.Canvas( self, bd=0, highlightthickness=0, yscrollcommand=self.vscrollbar.set )
		self.canvas.pack( side='left', fill='both', expand=True )
		#self.canvas.yview_scroll = self.new_yview_scroll
		self.vscrollbar.config( command=self.canvas.yview )

		# reset the view
		self.canvas.xview_moveto( 0 )
		self.canvas.yview_moveto( 0 )

		# create a frame inside the canvas which will be scrolled with it
		self.interior = Tk.Frame( self.canvas, relief='ridge' )
		self.interior_id = self.canvas.create_window( 0, 0, window=self.interior, anchor='nw' )

		# track changes to the canvas and frame width and sync them,
		# also updating the scrollbar
		self.interior.bind( '<Configure>', self._configure_interior )
		self.canvas.bind( '<Configure>', self._configure_canvas )

	def _configure_interior( self, event=None ):
		# Check if a scrollbar is necessary, and add/remove it as needed.
		if self.interior.winfo_height() > self.canvas.winfo_height():
			self.vscrollbar.pack( fill='y', side='right', expand=False )
			
			# update the scrollbars to match the size of the inner frame
			self.update_idletasks()
			interiorWidth = self.interior.winfo_reqwidth()
			# size = (interiorWidth, self.interior.winfo_reqheight())
			# self.canvas.config(scrollregion="0 0 %s %s" % size)
			self.canvas.config( scrollregion=self.canvas.bbox(self.interior_id) )
			if interiorWidth != self.canvas.winfo_width():
				# update the canvas' width to fit the inner frame
				self.canvas.config( width=interiorWidth )
		else:
			# remove the scrollbar and disable scrolling
			self.vscrollbar.pack_forget()

	def _configure_canvas( self, event=None ):
		if self.interior.winfo_reqwidth() != self.canvas.winfo_width():
			# update the inner frame's width to fill the canvas
			self.canvas.itemconfigure(self.interior_id, width=self.canvas.winfo_width())

	def yview_scroll( self, number, what ):
		# This is an override of the canvas' native yview_scroll method,
		# so that it only operates while the scrollbar is attached.
		if self.vscrollbar.winfo_manager():
			self.canvas.tk.call( self.canvas._w, 'yview', 'scroll', number, what )

		return 'break'

	def clear( self ):

		""" Clears (destroys) contents, and resets the scroll position to top. """

		for childWidget in self.interior.winfo_children():
			childWidget.destroy()

		# Reset the scrollbar (if there is one displayed) to the top.
		self.canvas.yview_moveto( 0 )


class ToolTip:

	''' 
		This class provides a flexible tooltip widget for Tkinter; it is based on IDLE's ToolTip
		module which unfortunately seems to be broken (at least the version I saw).

		Original author: Michael Lange <klappnase (at) freakmail (dot) de>
		Modified slightly by Daniel R. Cappel, including these additions:
		- 'remove' method, 'location' option, multi-monitor support, live update of textvariable, and a few other changes
		The original class is no longer available online, however a simplified adaptation can be found here:
			https://github.com/wikibook/python-in-practice/blob/master/TkUtil/Tooltip.py
			
	INITIALIZATION OPTIONS:
	anchor :        where the text should be positioned inside the widget, must be one of "n", "s", "e", "w", "nw" and so on;
					default is "center"
	bd :            borderwidth of the widget; default is 1 (NOTE: don't use "borderwidth" here)
	bg :            background color to use for the widget; default is "lightyellow" (NOTE: don't use "background")
	delay :         time in ms that it takes for the widget to appear on the screen when the mouse pointer has
					entered the parent widget; default is 1500
	fg :            foreground (i.e. text) color to use; default is "black" (NOTE: don't use "foreground")
	follow_mouse :  if set to 1 the tooltip will follow the mouse pointer instead of being displayed
					outside of the parent widget; this may be useful if you want to use tooltips for
					large widgets like listboxes or canvases; default is 0
	font :          font to use for the widget; default is system specific
	justify :       how multiple lines of text will be aligned, must be "left", "right" or "center"; default is "left"
	location :      placement above or below the target (master) widget. values may be 'n' or 's' (default)
	padx :          extra space added to the left and right within the widget; default is 4
	pady :          extra space above and below the text; default is 2
	relief :        one of "flat", "ridge", "groove", "raised", "sunken" or "solid"; default is "solid"
	state :         must be "normal" or "disabled"; if set to "disabled" the tooltip will not appear; default is "normal"
	text :          the text that is displayed inside the widget
	textvariable :  if set to an instance of Tkinter.StringVar() the variable's value will be used as text for the widget
	width :         width of the widget; the default is 0, which means that "wraplength" will be used to limit the widgets width
	wraplength :    limits the number of characters in each line; default is 150

	WIDGET METHODS:
	configure(**opts) : change one or more of the widget's options as described above; the changes will take effect the
						next time the tooltip shows up; NOTE: 'follow_mouse' cannot be changed after widget initialization
	remove() :          removes the tooltip from the parent widget

	Other widget methods that might be useful if you want to subclass ToolTip:
	enter() :           callback when the mouse pointer enters the parent widget
	leave() :           called when the mouse pointer leaves the parent widget
	motion() :          is called when the mouse pointer moves inside the parent widget if 'follow_mouse' is set to 1 and 
						the tooltip has shown up to continually update the coordinates of the tooltip window
	coords() :          calculates the screen coordinates of the tooltip window
	create_contents() : creates the contents of the tooltip window (by default a Tkinter.Label)

	Ideas gleaned from PySol

	Other Notes:
		If text or textvariable are empty or not specified, the tooltip will not show. '''

	version = 1.6

	def __init__( self, master, text='Your text here', delay=1500, **opts ):
		self.master = master
		self._opts = {'anchor':'center', 'bd':1, 'bg':'lightyellow', 'delay':delay, 'fg':'black',
					  'follow_mouse':0, 'font':None, 'justify':'left', 'location':'s', 'padx':4, 'pady':2,
					  'relief':'solid', 'state':'normal', 'text':text, 'textvariable':None,
					  'width':0, 'wraplength':150}
		self.configure(**opts)
		self._tipwindow = None
		self._id = None
		self._id1 = self.master.bind("<Enter>", self.enter, '+')
		self._id2 = self.master.bind("<Leave>", self.leave, '+')
		self._id3 = self.master.bind("<ButtonPress>", self.leave, '+')
		self._follow_mouse = 0
		if self._opts['follow_mouse']:
			self._id4 = self.master.bind("<Motion>", self.motion, '+')
			self._follow_mouse = 1

		# Monitor changes to the textvariable, if one is used (for dynamic updates to the tooltip's position)
		if self._opts['textvariable']:
			self._opts['textvariable'].trace( 'w', lambda nm, idx, mode: self.update() )

	def configure(self, **opts):
		for key in opts:
			if self._opts.has_key(key):
				self._opts[key] = opts[key]
			else:
				KeyError = 'KeyError: Unknown option: "%s"' %key
				raise KeyError

	def remove(self):
		#self._tipwindow.destroy()
		self.leave()
		self.master.unbind("<Enter>", self._id1)
		self.master.unbind("<Leave>", self._id2)
		self.master.unbind("<ButtonPress>", self._id3)
		if self._follow_mouse:
			self.master.unbind("<Motion>", self._id4)

	##----these methods handle the callbacks on "<Enter>", "<Leave>" and "<Motion>"---------------##
	##----events on the parent widget; override them if you want to change the widget's behavior--##

	def enter(self, event=None):
		self._schedule()

	def leave(self, event=None):
		self._unschedule()
		self._hide()

	def motion(self, event=None):
		if self._tipwindow and self._follow_mouse:
			x, y = self.coords()
			self._tipwindow.wm_geometry("+%d+%d" % (x, y))

	def update(self, event=None):
		tw = self._tipwindow
		if not tw: return

		if self._opts['text'] == 'Your text here' and not self._opts['textvariable'].get():
			self.leave()
		else:
			tw.withdraw()
			tw.update_idletasks() # to make sure we get the correct geometry
			x, y = self.coords()
			tw.wm_geometry("+%d+%d" % (x, y))
			tw.deiconify()

	##------the methods that do the work:---------------------------------------------------------##

	def _schedule(self):
		self._unschedule()
		if self._opts['state'] == 'disabled': return
		self._id = self.master.after(self._opts['delay'], self._show)

	def _unschedule(self):
		id = self._id
		self._id = None
		if id:
			self.master.after_cancel(id)

	def _show(self):
		if self._opts['state'] == 'disabled' or \
			( self._opts['text'] == 'Your text here' and not self._opts['textvariable'].get() ):
			self._unschedule()
			return
		if not self._tipwindow:
			self._tipwindow = tw = Tk.Toplevel(self.master)
			# hide the window until we know the geometry
			tw.withdraw()
			tw.wm_overrideredirect(1)

			if tw.tk.call("tk", "windowingsystem") == 'aqua':
				tw.tk.call("::tk::unsupported::MacWindowStyle", "style", tw._w, "help", "none")

			self.create_contents()
			tw.update_idletasks()
			x, y = self.coords()
			tw.wm_geometry("+%d+%d" % (x, y))
			tw.deiconify()

	def _hide(self):
		tw = self._tipwindow
		self._tipwindow = None
		if tw:
			tw.destroy()

	##----these methods might be overridden in derived classes:----------------------------------##

	def coords(self):
		# The tip window must be completely outside the master widget;
		# otherwise when the mouse enters the tip window we get
		# a leave event and it disappears, and then we get an enter
		# event and it reappears, and so on forever :-(
		# or we take care that the mouse pointer is always outside the tipwindow :-)

		tw = self._tipwindow
		twWidth, twHeight = tw.winfo_reqwidth(), tw.winfo_reqheight()
		masterWidth, masterHeight = self.master.winfo_reqwidth(), self.master.winfo_reqheight()
		if 's' in self._opts['location'] or 'e' in self._opts['location']:
			cursorBuffer = 32 # Guestimate on cursor size, to ensure no overlap with it (or the master widget if follow_mouse=False)
		else: cursorBuffer = 2
		# if self._follow_mouse: # Tooltip needs to be well out of range of the cursor, to prevent triggering the original widget's leave event
		# 	cursorBuffer += 32

		# Establish base x/y coords
		if self._follow_mouse: # Sets to cursor coords
			x = self.master.winfo_pointerx()
			y = self.master.winfo_pointery()

		else: # Sets to widget top-left screen coords
			x = self.master.winfo_rootx()
			y = self.master.winfo_rooty()

		# Offset the tooltip location from the master (target) widget, so that it is not over the top of it
		if 'w' in self._opts['location'] or 'e' in self._opts['location']:
			if self._follow_mouse:
				if 'w' in self._opts['location']:
					x -= ( twWidth + cursorBuffer )

				else: x += cursorBuffer

				# Center y coord relative to the mouse position
				y -= ( twHeight / 2 - 8 )

			else:
				# Place the tooltip completely to the left or right of the target widget
				if 'w' in self._opts['location']:
					x -= ( twWidth + cursorBuffer )

				else: x += masterWidth + cursorBuffer

				# Vertically center tooltip relative to master widget
				y += ( masterHeight / 2 - twHeight / 2 )

		else: # No horizontal offset, so the tooltip must be placed above or below the target to prevent problems
			if 'n' in self._opts['location']: # place the tooltip above the target
				y -= ( twHeight + cursorBuffer )
				
			else:
				y += cursorBuffer

			# Horizontally center tooltip relative to master widget
			x += ( masterWidth / 2 - twWidth / 2 )

		return x, y

	def create_contents(self):
		opts = self._opts.copy()
		for opt in ('delay', 'follow_mouse', 'state', 'location'):
			del opts[opt]
		label = Tk.Label(self._tipwindow, **opts)
		label.pack()