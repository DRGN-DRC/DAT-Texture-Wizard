# Originally created by Henry Haefliger
# Modified and greatly expanded upon by Daniel Cappel
# Source: 	https://medium.com/quick-code/3d-graphics-using-the-python-standard-library-99914447760c
# GIT:		https://github.com/hnhaefliger/PyEngine3D

import math, copy
import Tkinter as Tk
import hsdStructures

class Engine3D( Tk.Canvas ):

	def __init__( self, parent, points, shapes, width=1000, height=700, distance=320, scale=1, background='white' ):
		self.distance = distance
		self.scale = scale

		# Define center point offsets
		self.zeros = ( width/2, height/2 )
		self.prevSize = ( width, height )

		Tk.Canvas.__init__( self, parent, width=width, height=height, bg=background, closeenough=3 )
		
		self.bind( '<1>', lambda event: self.focus_set() ) # Makes clicking on the canvas move focus to it, if it doesn't already have it
		self.__dragPrev = []
		self.__panPrev = []
		self.bind( '<B1-Motion>', self.__drag ) 	# Mouse 1 click & drag
		self.bind( '<B3-Motion>', self.__pan ) 		# Right-click & drag
		self.bind( '<ButtonRelease-1>', self.__resetDrag )
		self.bind( '<ButtonRelease-3>', self.__resetPan )
		self.bind_all( '<Key>', self.__keypress )
		self.bind( "<MouseWheel>", self.mouseWheelScrolled )
		self.bind( '<KeyPress-r>', self.resetView )
		self.bind( '<KeyPress-R>', self.resetView )

		Tk.Label( self, text='R = Reset View', fg='#ccc', bg=background ).place( relx=1.0, x=-110, rely=1.0, y=-27 )
		
		# Store coordinates and faces
		self.points = points
		cLen = 5 # Centerpoint crosshair line lengths
		self.crosshairPoints = [ Vertex((cLen, 0, 0)), Vertex((-cLen, 0, 0)), Vertex((0, cLen, 0)), Vertex((0, -cLen, 0)), Vertex((0, 0, cLen)), Vertex((0, 0, -cLen)) ]
		self.shapes = shapes

		# Create a copy of some values, so the display can be reset
		self.origDistance = distance
		self.origScale = scale
		self.origPoints = copy.deepcopy( points ) # Keeping an unmodified copy of the points
		self.origCrosshairPoints = copy.deepcopy( self.crosshairPoints ) # Keeping an unmodified copy of the points
		
		self.render()

		self.bind( '<Configure>', self.configureWindowSize )

	def drawOriginCrosshair( self ):
		color = '#ddd'

		self.create_line( self.flatten( self.crosshairPoints[0] ) + self.flatten( self.crosshairPoints[1] ), fill=color )
		self.create_line( self.flatten( self.crosshairPoints[2] ) + self.flatten( self.crosshairPoints[3] ), fill=color )
		self.create_line( self.flatten( self.crosshairPoints[4] ) + self.flatten( self.crosshairPoints[5] ), fill=color )

	def flatten( self, point ):
		#calculate 2D coordinates from 3D point. todo: write proper method to map world points into camera space
		projectedX = int(( (point.x * self.distance) / (point.z + self.distance) ) * self.scale) + self.zeros[0]
		projectedY = int(( (point.y * self.distance) / (point.z + self.distance) ) * self.scale) + self.zeros[1]

		return ( projectedX, projectedY )

	def render( self ):
		#calculate flattened coordinates (x, y)
		flattenedPoints = []
		for point in self.points:
			projectedX, projectedY = self.flatten( point )
			flattenedPoints.append( (projectedX, projectedY) )

		#get coordinates to draw shapes. this will be a multidimensional array; 
		#each flattenedPointsList in this list will contain tuples of canvas x/y coords
		shapes = []
		for shape in self.shapes:
			#if shape.__class__ == hsdStructures.ColCalcArea and not 
			if not shape.render: continue
			elif shape.__class__ == hsdStructures.CollissionSurface and not shape.validIndices: continue

			shape.avgZ = 0	#used to calculate z-order
			shape.coords = []
			for pointIndex in shape.points:
				shape.avgZ -= self.points[pointIndex].z
				shape.coords.extend( flattenedPoints[pointIndex] )

			shapes.append( shape )
			
		#sort shapes from furthest back to closest
		shapes = sorted( shapes, key=lambda obj: obj.avgZ )

		#draw shapes on screen
		for shape in shapes:
			if len( shape.coords ) == 4:
				#print 'creating line'
				shape.id = self.create_line( shape.coords, fill=shape.fill )
			else:
				#print (shape.__class__.__name__,)
				shape.id = self.create_polygon( shape.coords, fill=shape.fill, outline=shape.outline, tags=(shape.__class__.__name__,) )
				#self.create_text( shape.coords, fill )

			if shape.__class__.__name__ == 'ColCalcArea': # Coord order is bottom-left, top-left, top-right, bottom-right
				x = shape.coords[2] + 3
				y = shape.coords[3]
				self.create_text( (x, y), anchor='nw', text='A' + str(shape.number), fill='red' )

		self.drawOriginCrosshair()

	def rotate(self, axis, angle):

		angle = math.radians( angle )
		#rotate model around axis
		for point in self.points + self.crosshairPoints:
			x, y, z = point.x, point.y, point.z
			
			if axis == 'z':
				#rotate aroud Z axis
				newX = x * math.cos(angle) - y * math.sin(angle)
				newY = y * math.cos(angle) + x * math.sin(angle)
				newZ = z
			elif axis == 'x':
				#rotate around X axis
				newY = y * math.cos(angle) - z * math.sin(angle)
				newZ = z * math.cos(angle) + y * math.sin(angle)
				newX = x
			elif axis == 'y':
				#rotate around Y axis
				newX = x * math.cos(angle) - z * math.sin(angle)
				newZ = z * math.cos(angle) + x * math.sin(angle)
				
				# newX = x * math.cos(angle) + z * math.sin(angle)
				# newZ = -x * math.sin(angle) + z * math.cos(angle)
				newY = y
			else:
				raise ValueError( 'Invalid axis: ' + str(axis) )
			point.x = newX
			point.y = newY
			point.z = newZ

	def __keypress( self, event ):
		# Cancel if the canvas doesn't have focus
		if self.master.focus_get() != self:
			return

		#handler for keyboard events
		#print 'keypress:', event.keysym
		if event.keysym == 'Up':
			self.rotate('x', -2)
		elif event.keysym == 'Down':
			self.rotate('x', 2)
		elif event.keysym == 'Right':
			self.rotate('y', 2)
		elif event.keysym == 'Left':
			self.rotate('y', -2)
		elif event.keysym == 'plus' or event.keysym == 'equal':
			self.scale += .1
		elif event.keysym == 'minus' and self.scale > .1:
			self.scale -= .1
		else: # No change to be made
			return
		self.delete( 'all' )
		self.render()

	def __resetDrag( self, event ):
		#reset mouse drag handler
		self.__dragPrev = []

	def __resetPan( self, event ):
		#reset mouse drag handler
		self.__panPrev = []
	
	def __drag( self, event ):
		#handler for mouse drag event
		if self.__dragPrev:
			self.rotate('y', event.x - self.__dragPrev[0] )
			self.rotate('x', event.y - self.__dragPrev[1] )
			self.delete( 'all' )
			self.render()
		self.__dragPrev = [event.x, event.y]

	def __pan( self, event ):
		# User is Right-click panning the canvas; adjust the canvas origin offsets
		if self.__panPrev:
			canvasOrigin = self.zeros
			xMovement = event.x - self.__panPrev[0]
			yMovement = event.y - self.__panPrev[1]
			self.zeros = ( canvasOrigin[0] + xMovement, canvasOrigin[1] + yMovement )
			# self.delete( 'all' )
			# self.render()
			self.move( 'all', xMovement, yMovement )
		self.__panPrev = [event.x, event.y]

	def mouseWheelScrolled( self, event ):
		if event.delta > 0: # Orig delta is +/- 120
			self.scale += .3
		elif self.scale > .3:
			self.scale -= .3
		else:
			return
		self.delete( 'all' )
		self.render()

	def resetView( self, event ):
		self.zeros = ( int(self['width'])/2, int(self['height'])/2 )
		self.distance = self.origDistance
		self.scale = self.origScale
		self.points = copy.deepcopy( self.origPoints ) # Restore the unmodified points list
		self.crosshairPoints = copy.deepcopy( self.origCrosshairPoints )
		self.delete( 'all' )
		self.render()

	def configureWindowSize( self, event ):

		""" Called on canvas resizing. Calculates new x/y canvas offsets, and new coords for the drawn canvas items. """

	 	oldShiftX, oldShiftY = self.zeros
		newWidth, newHeight = event.width - 4, event.height - 4 # -4 gets rid of the included border thickness
		shiftX, shiftY = (newWidth - self.prevSize[0])/2, (newHeight - self.prevSize[1])/2

		self.zeros = ( oldShiftX + shiftX, oldShiftY + shiftY )

		self.move( 'all', shiftX, shiftY )
		self.prevSize = ( newWidth, newHeight )


class Vertex:
	def __init__(self, points):
		#store x, y, z coordinates
		self.x = points[0]
		self.y = points[1]
		self.z = points[2]