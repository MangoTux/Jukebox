#!/usr/bin/python

'''
Script to control playback of music (Using OMXPlayer wrapper) and DotStar LED strip
'''

import os
import time
import linecache
import colorsys
import colour
from bisect import bisect
import RPi.GPIO as GPIO
from random import random,randint,choice,uniform,shuffle
from pygame import mixer
from dotstar import Adafruit_DotStar

#################### GPIO  ####################
FORWARD = 1
BACK = -1

GPIO.setmode(GPIO.BCM)

pin_prev = 23
pin_play = 25
pin_fwd  = 12
time_stamp = time.time()

GPIO.setup(pin_prev, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(pin_play, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(pin_fwd,  GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

#################### LIGHT ####################
numPixels = 15 # Testing value
clockpin = 5
datapin = 4

delay = 0.03

segments = 128 # 64 iterations of phasing between colors

lightMode = [("wave", 10), ("phase", 8), ("wave_custom", 12), ("phase_two", 15), ("flash", 5), ("rave", 5), ("bounce", 10), ("bounce_custom", 10), ("rainbow", 10), ("rainbow_chase", 15)] # TODO add
currentMode = lightMode[0]

newLightIndex = [0, 2, 4, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 29, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27]

def randColor():
	h = uniform(0, 100)/100
	s = uniform(70, 100)/100
	v = uniform(70, 100)/100
	rgb = colorsys.hsv_to_rgb(h, s, v) # Format (0-1, 0-1, 0-1)
	r, g, b = int(255*rgb[0]), int(255*rgb[1]), int(255*rgb[2])
	return "0x"+("%0.2X"%r)+("%0.2X"%g)+("%0.2X"%b)
	
# Was having an issue with some pixels randomly being red;
# either due to clock being too fast, or some things not being assigned properly.
# This stores every pixel's color, and all changes to color will modify this.
stripCol = ["0x000000" for i in range(numPixels)]
phaseList = ["0x000000" for i in range(segments)]
phaseIndex = 0

def modeInit(n = -1):
	global currentMode
	# Choose a weighted random mode from the list/probability pairing above
	if n<0:
		values, weights = zip(*lightMode)
		total = 0
		cum_weights = []
		for w in weights:
			total += w
			cum_weights.append(total)
		x = random() * total
		i = bisect(cum_weights, x)
		currentMode = values[i] # Todo weighted towards some options
	else:
		currentMode = lightMode[n][0]
	print currentMode
	if (currentMode == "wave"):
		initColorWave(color=randColor())
	elif (currentMode == "phase"):
		initPhase(randColor(), randColor())
	elif (currentMode == "wave_custom"):
		initColorWave(color=randColor() if randint(1,3)==3 else None, chaseLength = randint(1,10), dir = FORWARD if randint(1,2)==1 else BACK)
	elif (currentMode == "phase_two"):
		initPhase_two(randColor(), randColor())
	elif (currentMode == "flash"):
		initFlash()
	elif (currentMode == "rave"):
		initRave()
	elif (currentMode == "bounce"):
		initBounce()
	elif (currentMode == "bounce_custom"):
		initBounce(color=randColor() if randint(1,3)==3 else None, bounceLength = randint(1, 8))
	elif (currentMode == "rainbow"):
		initRainbow()
	elif (currentMode == "rainbow_chase"):
		initRainbowChase(dir = FORWARD if randint(1, 2)==2 else BACK)
		
def mode():
	if (currentMode == "wave" or currentMode == "wave_custom"):
		colorWave()
	elif (currentMode == "phase"):
		phase()
	elif (currentMode == "phase_two"):
		phase_two()
	elif (currentMode == "flash"):
		flash()
	elif (currentMode == "rave"):
		rave()
	elif (currentMode == "bounce" or currentMode == "bounce_custom"):
		bounce()
	elif (currentMode == "rainbow"):
		rainbow()
	elif (currentMode == "rainbow_chase"):
		rainbowChase()
		
phase_colorFrom = "0x000000"
phase_colorTo = randColor()
phase_two_direction = FORWARD
phaseList_two = ["0x000000" for i in range(segments)]

def initPhase(c1, c2):
	global phaseList
	global phaseIndex
	global phase_colorFrom, phase_colorTo
	phase_colorFrom = colour.Color("#"+c1[2:])
	phase_colorTo = colour.Color("#"+c2[2:])
	phaseList = list(phase_colorFrom.range_to(phase_colorTo, segments))
	phase_colorTo = c2 # So there's a seamless flow between values
	phaseIndex = 0

def phase():
	global phaseIndex
	if phaseIndex >= segments:
		initPhase(phase_colorTo, randColor())
	for n in range(numPixels):
		rgb = phaseList[phaseIndex].rgb
		red = int(round(255*rgb[0]))
		green = int(round(255*rgb[1]))
		blue = int(round(255*rgb[2]))
		strip.setPixelColor(newLightIndex[n], red, green, blue)
	strip.show()
	time.sleep(delay)
	phaseIndex+=1
	
# Even lights go bright while odd go dim, vice-versa
def initPhase_two(c1, c2):
	global phaseList, phaseList_two
	global phaseIndex
	c1 = colour.Color("#"+c1[2:])
	c2 = colour.Color("#"+c2[2:])
	phaseList = list(c1.range_to("#000000", segments))
	phaseList_two = list(colour.Color("#000000").range_to(c2, segments))
	phaseIndex = 0
	
def phase_two():
	global phaseIndex, phase_two_direction
	global phaseList, phaseList_two
	if phaseIndex >= segments-1:
		phase_two_direction = BACK
		phaseList = list(colour.Color("#"+randColor()[2:]).range_to(colour.Color("#000000"), segments))
	elif phaseIndex <= 0:
		phase_two_direction = FORWARD
		phaseList_two = list(colour.Color("#000000").range_to(colour.Color("#"+randColor()[2:]), segments))
	for n in range(numPixels):
		if n%2==0:
			rgb = phaseList[phaseIndex].rgb
		else:
			rgb = phaseList_two[phaseIndex].rgb
		red = int(round(255*rgb[0]))
		green = int(round(255*rgb[1]))
		blue = int(round(255*rgb[2]))
		strip.setPixelColor(newLightIndex[n], red, green, blue)
	strip.show()
	time.sleep(delay)
	phaseIndex+=phase_two_direction

def shift(dir):
	global stripCol
	stripCol = stripCol[dir:]+stripCol[:dir]
	for n in range(numPixels):
		strip.setPixelColor(newLightIndex[n], int(stripCol[n], 16))
		
direction = FORWARD
# initializes the color wave with color color and length chaseLength
def initColorWave(color=None, chaseLength=10, dir=FORWARD):
	global stripCol, direction
	direction = dir
	for n in range(numPixels):
		if n < chaseLength:
			stripCol[n] = randColor() if color==None else color 
		else:
			stripCol[n] = "0x000000"

# Moves one iteration of the color wave
def colorWave():
	shift(direction)
	strip.show()
	time.sleep(delay)
	
lightIndex = 0
# Similar to the color wave, but once it reaches an end of the strip, it changes directions
def initBounce(color=None, bounceLength=5):
	global stripCol, lightIndex, direction
	direction = FORWARD
	for n in range(numPixels):
		if n < bounceLength:
			stripCol[n] = randColor() if color==None else color
		else:
			stripCol[n] = "0x000000"
	lightIndex = 0
			
def bounce():
	global stripCol, direction, lightIndex
	if direction==BACK and stripCol[numPixels-1] != "0x000000":
		direction = FORWARD
	elif direction==FORWARD and stripCol[0] != "0x000000":
		direction = BACK
	shift(direction)
	strip.show()
	time.sleep(delay)
	lightIndex+=1
	
brightness = 1
rainbowPattern = ["0x0079E5","0x0050E5","0x0027E5","0x0200E5","0x2B00E5","0x5500E6","0x7E00E6","0xA800E6","0xD200E6","0xE600D1","0xE700A8","0xE7007E","0xE70054","0xE7002B","0xE70001","0xE82800","0xE85200","0xE87C00","0xE8A600","0xE8D000","0xD7E900","0xADE900","0x83E900","0x59E900","0x2EE900","0x04EA00","0x00EA25","0x00EA50","0x00EA7A","0x00EBA5"]
def initRainbow():
	global brightness, direction
	direction = FORWARD # Ew
	for n in range(numPixels):
		strip.setPixelColor(newLightIndex[n], int(rainbowPattern[n], 16))
	strip.setBrightness(brightness)
	strip.show()
	time.sleep(.04)
	
def rainbow():
	global brightness, direction
	brightness += direction
	if brightness >= 64:
		direction = BACK
	elif brightness <= 1:
		direction = FORWARD
	strip.setBrightness(brightness)
	strip.show()
	time.sleep(.04)
	
def initRainbowChase(dir=FORWARD):
	global direction, stripCol
	direction = dir
	for n in range(numPixels):
		stripCol[n] = rainbowPattern[n]

def rainbowChase():
	shift(direction)
	strip.show()
	time.sleep(delay)
	
# Flash will alternate between on/off
def initFlash():
	global lightIndex
	lightIndex = 0
	
def flash():
	global lightIndex
	if lightIndex%50==0:
		c = randColor()
		for n in range(numPixels):
			strip.setPixelColor(newLightIndex[n], int(c, 16))
		strip.show()
	elif (lightIndex+25)%50==0:
		turnOff()
	lightIndex+=1
	time.sleep(delay)
	
def initRave():
	global stripCol
	for n in range(numPixels):
		stripCol[n] = randColor()

def rave():
	global stripCol
	choice = randint(1, 100)
	if choice in range(1, 75): # Main choice, 
		for n in range(numPixels):
			change = randint(1, 100)
			if change in range(1, 75):
				strip.setPixelColor(newLightIndex[n], int(randColor(), 16))
			elif change in range(75, 90):
				strip.setPixelColor(newLightIndex[n], 0)
		strip.show()
	elif choice in range(75, 86):
		shift(FORWARD)
		strip.show()
	elif choice in range(86, 97):
		shift(BACK)
		strip.show() # Heh, strip show
	else:
		turnOff()
	time.sleep(uniform(.04, .1))
	
def turnOff():
	for n in range(numPixels):
		strip.setPixelColor(newLightIndex[n], 0)
	strip.show()
	
def newSongWave(n=3, rewind=False):
	turnOff()
	if not rewind and songDirection == FORWARD:
		for n in range(numPixels*n):
			strip.setPixelColor(n if n<0 else newLightIndex[(n-1)%numPixels], 0)
			strip.setPixelColor(newLightIndex[n%numPixels], int("0xffffff", 16))
			strip.show()
			time.sleep(delay)
	else:
		for n in range(numPixels*n-1, -1, -1):
			strip.setPixelColor(newLightIndex[(n+1)%numPixels], 0)
			strip.setPixelColor(newLightIndex[n%numPixels], int("0xffffff", 16))
			strip.show()
			time.sleep(delay)
	turnOff()

#################### MUSIC ####################
song_location = "/mnt/usb" # TODO, change
song_name = ""# Name of the song currently playing
num_lines = 0 # Number of lines in the playlist file
songIndex = 0 # Index of song on list
songSkip = False
songDirection = FORWARD
songPosition = 0
#################### OTHER ####################

def demoMode():
	index = 0
	while True:
		modeInit(index)
		strip.setBrightness(64)
		for i in range(500): ## Issue - On rainbow mode, brightness is not returned to proper setting of 64
			mode()
		newSongWave(1)
		index += 1
		index %= len(lightMode)

def queueNext():
	global songDirection, songSkip, songIndex, song_name
	songIndex += songDirection
	strip.setBrightness(64) # Reset in case it was changed
	mixer.music.stop()
	if songIndex <= 0:
		# Shuffle the playlist
		lines = open('playlist.pls').readlines()
		shuffle(lines)
		open('playlist.pls', 'w').writelines(lines)
		songIndex = 1
		newSongWave(3, True)
	elif songIndex > num_lines: 
		# Shuffle the playlist
		lines = open('playlist.pls').readlines()
		shuffle(lines)
		open('playlist.pls', 'w').writelines(lines)
		songIndex = 1
		newSongWave(3)
	else:
		newSongWave(2)
	# Stop the previous one
	print "Queueing next, direction", songDirection
	song_name = linecache.getline('/home/pi/playlist.pls', songIndex).rstrip()
	print "Now playing: " + song_name
	try:
		mixer.music.load(song_name) # If it can't play a song e.g. Flash drive removed, 
	except:
		turnOff()
		time.sleep(3)
		demoMode()
	songDirection = FORWARD # Reset to default
	songSkip = False
	modeInit()
	play()
	
# Detects if this is the first cycle that the user paused
just_turned_off = True
state = "Playing"
# Ugly ugly ugly. Unpythonic but easier to debug for now
def play():
	global just_turned_off, state, songSkip, songDirection, songPosition
	if GPIO.input(pin_play):
		mixer.music.play()
	while mixer.music.get_busy(): 
		while (not GPIO.input(pin_play)): # While button is not set
			if just_turned_off: # The first cycle of being paused
				state = "Paused"
				mixer.music.pause()
				turnOff()
				just_turned_off = False
			if (GPIO.input(pin_fwd)):
				print "Going forward!"
				songDirection = FORWARD
				songSkip = True
				just_turned_off = True
				return
			elif (GPIO.input(pin_prev)):
				print "Going back!"
				if mixer.music.get_pos() < 10000:
					songDirection = BACK
					songSkip = True
					just_turned_off = True
					return
				else:
					mixer.music.stop()
					newSongWave(n=1, rewind=True)
					mixer.music.load(song_name)
				
		if (GPIO.input(pin_fwd)):
			print "Going forward!"
			songDirection = FORWARD
			songSkip = True
			just_turned_off = True
			return
		elif (GPIO.input(pin_prev)):
			print "Going back!"
			if mixer.music.get_pos() < 10000: # If song playback is within the first ten seconds, loop back to beginning
				songDirection = BACK
				songSkip = True
				just_turned_off = True
				return
			else:
				mixer.music.stop()
				newSongWave(n=1, rewind=True)
				mixer.music.load(song_name)
				mixer.music.play()
			
		if state == "Paused": # Resume playing state after paused
			state = "Playing"
			mixer.music.unpause()
		just_turned_off = True # Reset value
		mode()

def main():
	# Build playlist of songs
	os.system("rm -f /home/pi/playlist.pls; find " + song_location + " | grep 'flac\|ogg\|mp3' | shuf > playlist.pls")
	global num_lines
	try:
		num_lines = sum(1 for line in open('playlist.pls'))
	except:
		num_lines = 0
	turnOff()
	if num_lines == 0:
		demoMode() # No file/Empty file. Do demo mode!
	while True: # Loops continuously until unplugged
		queueNext()
		turnOff() # Currently an issue with skipping back, should be a nonissue in the future.
	if mixer.music.get_busy():
		mixer.music.stop()
	os.system('umount /mnt/usb; umount /dev/sdb1')
	turnOff()
	GPIO.cleanup()
	
def mountDevice():
	os.system('mount /dev/sdb1 /mnt/usb')
		
if __name__ == "__main__":
	# Wow this is pretty ugly - I'm in a hurry, though.
	mountDevice()
	strip = Adafruit_DotStar(numPixels, datapin, clockpin)
	strip.begin()
	strip.setBrightness(64)
	mixer.init(48000, -16, 1, 1024)
	main()