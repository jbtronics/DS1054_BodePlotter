# jds6600.py
# library to remote-control a JDS6600 signal generator

# Kristoff Bonne (c) 2018
# published under MIT license. See file "LICENSE" for full license text

# Revisions:
# Version 0.0.1: 2018/01/19: initial release, reading basic parameters
# version 0.0.2: 2018/01/28: added "measure" menu + support functions, documentation
# version 0.0.3: 2018/02/07: added "counter" and "sweep" menu
# version 0.0.4: 2018/02/14: added "pulse" and "burst" menu + code cleanup
# version 0.0.5: 2018/02/16: added system menu
# version 0.1.0: 2018/02/17: added arbitrary waveform 


import serial
import binascii


###########
#  Errors #
###########

class UnknownChannelError(ValueError):
	pass

class UnexpectedValueError(ValueError):
	pass

class UnexpectedReplyError(ValueError):
	pass

class FormatError(ValueError):
	pass

class WrongMode(RuntimeError):
	# called when commands are issued with the jds6600 not in the correct
	# mode
	pass


#################
# jds6600 class #
#################

class jds6600:
	'jds6600 top-level class'

	# serial device (opened during object init))
	ser = None

	# commands
	DEVICETYPE=0
	SERIALNUMBER=1

	CHANNELENABLE=20
	WAVEFORM1=21
	WAVEFORM2=22
	FREQUENCY1=23
	FREQUENCY2=24
	AMPLITUDE1=25
	AMPLITUDE2=26
	OFFSET1=27
	OFFSET2=28
	DUTYCYCLE1=29
	DUTYCYCLE2=30
	PHASE=31

	ACTION=32
	MODE=33

	MEASURE_COUP=36 # coupling (AC or DC)
	MEASURE_GATE=37 # gatetime
	MEASURE_MODE=38 # mode (Freq or Periode)

	COUNTER_COUPL=MEASURE_COUP
	COUNTER_RESETCOUNTER=39

	SWEEP_STARTFREQ=40
	SWEEP_ENDFREQ=41
	SWEEP_TIME=42
	SWEEP_DIRECTION=43
	SWEEP_MODE=44 # mode: linair or Log

	PULSE_PULSEWIDTH=45
	PULSE_PERIOD=46
	PULSE_OFFSET=47
	PULSE_AMPLITUDE=48

	BURST_NUMBER=49
	BURST_MODE=50
	

	SYSTEM_SOUND=51
	SYSTEM_BRIGHTNESS=52
	SYSTEM_LANGUAGE=53
	SYSTEM_SYNC=54
	SYSTEM_ARBMAXNUM=55

	PROFILE_SAVE=70
	PROFILE_LOAD=71
	PROFILE_CLEAR=72

	COUNTER_DATA_COUNTER=80

	MEASURE_DATA_FREQ_LOWRES=81 # low resolution freq counter, used for mode "frequency"
	MEASURE_DATA_FREQ_HIGHRES=82 # high resolution freq. counter, usef for mode "period". UI: valid up to 2 Khz
	MEASURE_DATA_PW1=83
	MEASURE_DATA_PW0=84
	MEASURE_DATA_PERIOD=85
	MEASURE_DATA_DUTYCYCLE=86
	MEASURE_DATA_U1=87
	MEASURE_DATA_U2=88
	MEASURE_DATA_U3=89




	# waveforms: registers 21 (ch1) and 22 (ch2))
	# 0 to 16: predefined waveforms
	__wave=("SINE","SQUARE","PULSE","TRIANGLE","PARTIALSINE","CMOS","DC","HALF-WAVE","FULL-WAVE","POS-LADDER","NEG-LADDER", "NOISE", "EXP-RIZE","EXP-DECAY","MULTI-TONE","SINC","LORENZ")
	# 101 to 160: arbitrary waveforms
	__awave=[]
	for a in range(1,10):
		__awave.append("ARBITRARY0"+str(a))
	for a in range(10,61):
		__awave.append("ARBITRARY"+str(a))
	# end for
		

	# modes: register 33
	# note: use lowest 4 bits for wrting
	# note: use highest 4 bits for reading
	__modes = ((0,"WAVE_CH1"),(0,"WAVE_CH1"),(1,"WAVE_CH2"),(1,"WAVE_CH2"),(2,"SYSTEM"),(2,"SYSTEM"),(-1,""),(-1,""),(4,"MEASURE"),(5,"COUNTER"),(6,"SWEEP_CH1"),(7,"SWEEP_CH2"),(8,"PULSE"),(9,"BURST"))

	# action: register 32
	__actionlist=(("STOP","0,0,0,0"),("COUNT","1,0,0,0"),("SWEEP","0,1,0,0"),("PULSE","1,0,1,1"),("BURST","1,0,0,1"))
	__action={}
	for (actionname,actioncode) in __actionlist:
		__action[actionname]=actioncode
	# end for

	
	# measure mode parameters
	__measure_coupling=("AC(EXT.IN)","DC(EXT.IN)")
	__measure_mode=("M.FREQ","M.PERIOD")


	# sweep parameters
	__sweep_direction=("RISE","FALL","RISE&FALL")
	__sweep_mode=("LINEAR","LOGARITHM")


	# burst parameters
	__burst_mode=["MANUAL TRIG.","CH2 TRIG.","EXT.TRIG(AC)","EXT.TRIG(DC)"]

	# frequency multiplier
	__freqmultiply=(1,1,1,1/1000,1/1000000)


	# language
	__system_language=("ENGLISH","CHINESE")

	###############
	# oonstructor #
	###############

	def __init__(self,fname):
			jds6600.ser = serial.Serial(
				port= fname,
				baudrate=115200,
				parity=serial.PARITY_NONE,
				stopbits=serial.STOPBITS_ONE,
				bytesize=serial.EIGHTBITS,
				timeout=1		)
	# end constructor



	#####################
	# support functions #
	#####################

	#####
	# low-level support function

	# parse data from read command
	def __parsedata(self,reg,data,a):
		if a not in (0,1): raise RuntimeError(a)

		try:
			(one,two)=data.split("=")
		except ValueError:
			raise FormatError("Parsing Returned data: Invalid format, missing \"=\"")
	
		two_b=two.split(".")

		# reads from register are terminated by a "."
		# reads of arbitrary waveform are not 
		if a == 0:
			if len(two_b) < 2:
				raise FormatError("Parsing Returned data: Invalid format, missing \".\"")

			if len(two_b) > 2:
				raise FormatError("Parsing Returned data: Invalid format, too many \".\"")
		# end if

		# command to look for;
		# "r" for register read, "b" for arbitrary waveform read
		c = 'r' if a == 0 else 'b'

		# check if returned data matches reg that was send
		if reg != None:
			if one != ":"+c+reg:
				errmsg="Parsing Return data: send/received reg mismatch: "+data+" / expected :"+c+reg
				raise FormatError(errmsg)
			# end if
		# end if

		# done: return data: part between "=" and ".", split on ","
		return two_b[0].split(",")
	# end __parsedata

	# command in textual form
	def __reg2txt(self,reg):
		return "0"+str(reg) if int(reg) < 10 else str(reg)
	# end reg2txt

	# send read command (for n datapoint)
	def __sendreadcmd(self,reg,n,a):
		if type(n) != int: raise TypeError(n)
		if a not in (0,1): raise ValueError(a)

		regtxt=self.__reg2txt(reg)
		if (n < 1):
			raise ValueError(n)

		if a == 0:
			# a (arbitrary waveform) is 0  -> register read
			c='r' # register
		else:
			c='b' # arbitrary waveform
			# for n to 1
			n=1
		# end else - if

		# "n" in command start with 0 for 1 read-request
		n -= 1

		if self.ser.is_open == True:
			tosend=":"+c+regtxt+"="+str(n)+"."+chr(0x0a)
			self.ser.write(tosend.encode())
	# end __sendreadcmd



	# get responds of read-request and parse ("n" reads)
	def __getrespondsandparse(self,reg, n, a):
		if type(n) != int: raise ValueError(n)
		if a not in (0,1): raise ValueError(a) # a=0-> register read, a=1 -> arbitrary waveform read

		ret=[] # return value

		c = int(reg) # counter
		c_expect=self.__reg2txt(c)
		for l in range(n):
			# get one line responds from serial device
			retserial=self.ser.readline()
			# convert bytearray into string, then strip off terminating \n and \r
			retserial=str(retserial,'utf-8').rstrip()

			# get parsed data
			# assume all data are single-value fields
			parseddata=self.__parsedata(c_expect,retserial,a)

			# we receive a list of strings, all containing numeric (integer) values

			if len(parseddata) == 1:
			# if list with one value, return that value (converted to integer)
				ret.append(int(parseddata[0]))
			else:
			# if list with multiple values, convert all strings to integers and return list
				retlist=[]
				retcount=0
				for data in parseddata:
					if data == "":
						# we should not receive empty datafields, except for after the last element of an arbitrary waveform
						if not ((a == 1) and (retcount == 2048)):
							raise UnexpectedValueError(parseddata)
					else:
						retlist.append(int(data))
					# end else - if

					retcount += 1
				# end for
				ret.append(retlist)
			# end else - if

			# increase next expected to-receive data
			c += 1
			c_expect=self.__reg2txt(c)
		# end for

		# return parsed data
		# if only one element, return that element
		# if multiple elements, return list
		return ret[0] if n == 1 else ret
	# end __get responds and parse 1


	# get data
	def __getdata(self,reg, n=1, a=0):
		if type(reg) != int: raise TypeError(reg)
		if type(n) != int: raise TypeError(n)

		# a is "arbitrary waveform or register"
		# a=0 -> register read
		# a=1 -> arbitrary waveform read

		# send "read" commandline for "n" lines 
		# copy "a" parameter from calling function
		self.__sendreadcmd(reg,n,a)

		return self.__getrespondsandparse(reg,n,a)
	# end __getdata 1

	
	# send write command and wait for "ok"
	def __sendwritecmd(self,reg, val, a=0):
		# note: a = "arbitrary waveform?": 0 = no (register write), 1 = yes (arb. waveform write)
		# add a "0" to the command if it one single character
		reg=self.__reg2txt(reg)

		# command to send: "w" for register write, "b" for arbitrary waveform write
		cmd = "w" if a == 0 else "a"

		if self.ser.is_open == True:
			if type(val) == int: val = str(val)
			if type(val) != str: raise TypeError(val)

			tosend=":"+cmd+reg+"="+val+"."+chr(0x0a)
			self.ser.write(tosend.encode())

			# wait for "ok"

			# get one line responds from serial device
			ret=self.ser.readline()
			# convert bytearray into string, then strip off terminating \n and \r
			ret=str(ret,'utf-8').rstrip()

			if ret != ":ok":
				raise UnexpectedReplyError(ret)
			# end if

		#end if
	# end __sendwritecmd


	#####
	# high-level support function

	# set action
	def __setaction(self,action):
		# type check
		if type(action) != str:
			raise TypeError(action)
		# end if

		try:
			self.__sendwritecmd(jds6600.ACTION,jds6600.__action[action])
		except KeyError:
			errmsg="Unknown Action: "+action
			raise ValueError(errmsg)
		# end try

	# end set action

	###################
	# DEBUG functions #
	###################

	def DEBUG_readregister(self,register,count):
		if self.ser.is_open == True:
			regtxt=self.__reg2txt(register)
			tosend=":r"+regtxt+"="+str(count)+"."+chr(0x0a)
			self.ser.write(tosend.encode())

			ret=self.ser.readline()
			while ret != b'':
				print(str(ret))
				ret=self.ser.readline()
			# end while 
		# end if
	# end readregister
		
	def DEBUG_writeregister(self,register,value):
		if self.ser.is_open == True:
			regtxt=self.__reg2txt(register)
			if type(value) == int:
				value=str(value)

			tosend=":w"+regtxt+"="+value+"."+chr(0x0a)
			self.ser.write(tosend.encode())

			ret=self.ser.readline()
			while ret != b'':
				print(str(ret))
				ret=self.ser.readline()
			# end while 
		# end if

	# end write register


	##############
	# PUBLIC API #
	##############

	#########################
	# Part 0: API information

	
	# API version
	def getAPIinfo_version(self):
		return 1
	# end getAPIversion

	# API release number
	def getAPIinfo_release(self):
		return "0.1.0 2018-02-17"
	# end get API release


	#############################
	# Part 1: information queries

	# list of waveforms
	def getinfo_waveformlist(self):
		waveformlist=list(enumerate(jds6600.__wave))
		for aw in (enumerate(jds6600.__awave,101)):
			waveformlist.append(aw)
		# end for

		return waveformlist
	# end get waveform list


	# get list of modes
	def getinfo_modelist(self):
		modelist=[]

		lastmode=-1

		# create list of modes, removing dups
		for (modeid,modetxt) in jds6600.__modes:
			# ignore modes with modeid < 0 (unused mode)
			if modeid < 0:
				continue
			# end if

			if modeid != lastmode:
				modelist.append((modeid,modetxt))
				lastmode = modeid
			# end if
		# end for

		return modelist
	# end getinfo modelist


	##################################
	# Part 2: reading basic parameters

	# get device type
	def getinfo_devicetype(self):
		return self.__getdata(jds6600.DEVICETYPE)
	# end get device type


	# get serial number
	def getinfo_serialnumber(self):
		return self.__getdata(jds6600.SERIALNUMBER)
	# end get serial number


	# get channel enable status
	def getchannelenable(self):
		(ch1,ch2)=self.__getdata(jds6600.CHANNELENABLE)
		try:
			return (False,True)[ch1], (False,True)[ch2]
		except IndexError:
			errmsg="Unexpected value received: {},{}".format(ch1,ch2)
			raise UnexpectedValueError(errmsg)
	# end get channel enable status

	# get waveform
	def getwaveform(self, channel):
		if type(channel) != int: raise TypeError(channel)
		if not (channel in (1,2)): raise ValueError(channel)

		#WAVEFORM for channel 2 is WAVEFORM1 + 1
		waveform=self.__getdata(jds6600.WAVEFORM1+channel-1)

		# waveform 0 to 16 are in "wave" list, 101 to 160 are in __awave
		try:
			return (waveform,jds6600.__wave[waveform])
		except IndexError:
			pass

		try:
			return (waveform,jds6600.__awave[waveform-101])
		except IndexError:
			raise UnexpectedValueError(waveform)
	# end getwaveform

	# get frequency _with multiplier
	def getfrequency_m(self,channel):
		if type(channel) != int: raise TypeError(channel)
		if not (channel in (1,2)): raise ValueError(channel)

		(f1,f2)=self.__getdata(jds6600.FREQUENCY1+channel-1)

		# parse multiplier (value after ",")
		# 0=Hz, 1=KHz,2=MHz, 3=mHz,4=uHz)
		# note f1 is frequency / 100
		try:
			return((f1/100*self.__freqmultiply[f2],f2))
		except IndexError:
			# unexptected value of frequency multiplier
			raise UnexpectedValueError(f2)
		# end elsif
	# end function getfreq

	# get frequency _no multiplier information
	def getfrequency(self,channel):
		if type(channel) != int: raise TypeError(channel)
		if not (channel in (1,2)): raise ValueError(channel)

		(f1,f2)=self.__getdata(jds6600.FREQUENCY1+channel-1)

		# parse multiplier (value after ","): 0=Hz, 1=KHz,2=MHz, 3=mHz,4=uHz)
		# note1: frequency unit is Hz / 100
		# note2: multiplier 1 (khz) and 2 (mhz) only changes the visualisation on the
		#							display of the jfs6600. The frequency itself is calculated in
		#							the same way as for multiplier 0 (Hz)
		#			mulitpliers 3 (mHZ) and 4 (uHz) do change the calculation of the frequency
		try:
			return(f1/100*self.__freqmultiply[f2])
		except IndexError:
			# unexptected value of frequency multiplier
			raise UnexpectedValueError(f2)
		# end elsif
	# end function getfreq


	# get amplitude
	def getamplitude(self, channel):
		if type(channel) != int: raise TypeError(channel)
		if not (channel in (1,2)): raise ValueError(channel)

		amplitude=self.__getdata(jds6600.AMPLITUDE1+channel-1)

		# amplitude is mV -> so divide by 1000
		return amplitude/1000
	# end getamplitude
	
	
	# get offset
	def getoffset(self, channel):
		if type(channel) != int: raise TypeError(channel)
		if not (channel in (1,2)): raise ValueError(channel)

		offset=self.__getdata(jds6600.OFFSET1+channel-1)

		# offset unit is 10 mV, and then add 1000
		return (offset-1000)/100
	# end getoffset

	# get dutcycle
	def getdutycycle(self, channel):
		if type(channel) != int: raise TypeError(channel)
		if not (channel in (1,2)): raise ValueError(channel)

		dutycycle=self.__getdata(jds6600.DUTYCYCLE1+channel-1)

		# dutycycle unit is 0.1 %, so divide by 10
		return dutycycle/10
	# end getdutycycle

	
	# get phase
	def getphase(self):
		phase=self.__getdata(jds6600.PHASE)

		# phase unit is 0.1 degrees, so divide by 10
		return phase/10
	# end getphase

	
	##################################
	# Part 3: writing basic parameters


	# set channel enable
	def setchannelenable(self,ch1,ch2):
		if type(ch1) != bool: raise TypeError(ch1)
		if type(ch2) != bool: raise TypeError(ch1)

		# channel 1
		if ch1 == True: enable = "1"
		else: enable = "0" # end else - if

		if ch2 == True: enable += ",1"
		else: enable += ",0" # end else - if

		# write command
		self.__sendwritecmd(jds6600.CHANNELENABLE,enable)
	# end set channel enable

	# set waveform
	def setwaveform(self,channel,waveform):
		if type(channel) != int: raise TypeError(channel)
		if (type(waveform) != int) and (type(waveform) != str): raise TypeError(waveform)

		if not (channel in (1,2)): raise ValueError(channel)

		# wzveform can be integer or string
		w=None

		if type(waveform) == int:
			# waveform is an integer
			if waveform < 101:
				try:
					jds6600.__wave[waveform]
				except IndexError:
					raise ValueError(waveform)
				# end try

			else:
				try:
					jds6600.__awave[waveform-101]
				except IndexError:
					raise ValueError(waveform)
				# end try
			# end if

			# ok, it exists!
			w=waveform

		else:
			# waveform is a string

			# make everything uppercase
			waveform=waveform.upper()
			# check all waveform descriptions in wave and __awave
			# w is already initialised as "none" above

			try:
				# try in "wave" list
				w=jds6600.__wave.index(waveform)
			except ValueError:
				pass

			if w == None:
				#if not found in "wave", try the "awave" list
				try:
					w=jds6600.__awave.index(waveform)+101 # arbitrary waveforms state are index 101
				except ValueError:
					pass
				# end try
			# end if

			if w == None:
				# not in "wave" and "awave" error
				errmsg="Unknown waveform "+waveform
				raise ValueError (errmsg)
			# end if

		# ens else - if


		self.__sendwritecmd(jds6600.WAVEFORM1+channel-1,w)

	# end function set waveform


	# set frequency (with multiplier)
	def setfrequency(self,channel,freq,multiplier=0):
		if type(channel) != int: raise TypeError(channel)
		if (type(freq) != int) and (type(freq) != float): raise TypeError(freq)
		if type(multiplier) != int: raise TypeError(multiplier)

		if not (channel in (1,2)): raise ValueError(channel)


		if (freq < 0):
			raise ValueError(freq)

		# do not execute set-frequency when the device is in sweepfrequency mode
		currentmode=self.getmode()

		if (channel == 1) and (currentmode[1] == "SWEEP_CH1"):
		# for channel 1
			raise WrongMode()
		elif (channel == 2) and (currentmode[1] == "SWEEP_CH2"):
		# for channel 2
			raise WrongMode()
		# end elsif - if


			
		# freqmultier should be one of the "frequency multiply" values
		try:
			self.__freqmultiply[multiplier]
		except IndexError:
			raise ValueError[multiplier]

		# frequency limit:
		#		60 Mhz for multiplier 0 (Hz), 1 (KHz) and 2 (MHz)
		#		80 Khz for multiplier 3 (mHz) 
		#		80  Hz for multiplier 4 (uHz)
		# trying to configure a higher value can result in incorrect frequencies

		if multiplier < 3:
			if freq > 60000000:
				errmsg="Maximum frequency using multiplier {} is 60 MHz.".format(multiplier)
				raise ValueError(errmsg)
			# end if
		elif multiplier == 3:
			if freq > 80000:
				errmsg="Maximum frequency using multiplier 3 is 80 KHz."
				raise ValueError(errmsg)
			# end if
		else: # multiplier == 4
			if freq > 80:
				errmsg="Maximum frequency using multiplier 4 is 80 Hz."
				raise ValueError(errmsg)
			# end if
		# end else - elsif - if

				

		# round to nearest 0.01 value
		freq=int(round(freq*100/jds6600.__freqmultiply[multiplier]))
		value=str(freq)+","+str(multiplier)

		self.__sendwritecmd(jds6600.FREQUENCY1+channel-1,value)
	# end set frequency (with multiplier)


	# set amplitude
	def setamplitude(self, channel, amplitude):
		if type(channel) != int: raise TypeError(channel)
		if (type(amplitude) != int) and (type(amplitude) != float): raise TypeError(amplitude)

		if not (channel in (1,2)): raise ValueError(channel)

		# amplitude is between 0 and 20 V
		if not (0 <= amplitude <= 20):
			raise ValueError(amplitude)

		# round to nearest 0.001 value
		amplitude=int(round(amplitude*1000))
		
		self.__sendwritecmd(jds6600.AMPLITUDE1+channel-1,amplitude)
	# end setamplitude
	
	

	# set offset
	def setoffset(self, channel, offset):
		if type(channel) != int: raise TypeError(channel)
		if (type(offset) != int) and (type(offset) != float): raise TypeError(offset)

		if not (channel in (1,2)): raise ValueError(channel)

		# offset is between -10 and +10 volt
		if not (-10 <= offset <= 10):
			raise ValueError(offset)

		# note: althou the value-range for offset is able
		# to accomodate an offset between -10 and +10 Volt
		# the actual offset seams to be lmited to -2.5 to +2.5

		# round to nearest 0.01 value
		offset=int(round(offset*100))+1000

		self.__sendwritecmd(jds6600.OFFSET1+channel-1, offset)
	# end set offset

	# set dutcycle
	def setdutycycle(self, channel, dutycycle):
		if type(channel) != int: raise TypeError(channel)
		if (type(dutycycle) != int) and (type(dutycycle) != float): raise TypeError(dutycycle)

		if not (channel in (1,2)): raise ValueError(channel)

		# dutycycle is between 0 and 100 %
		if not (0 <= dutycycle <= 100):
			raise ValueError(dutycycle)

		# round to nearest 0.1 value
		dutycycle=int(round(dutycycle*10))

		self.__sendwritecmd(jds6600.DUTYCYCLE1+channel-1,dutycycle)
	# end set dutycycle

	
	# set phase
	def setphase(self,phase):
		if (type(phase) != int) and (type(phase) != float):
			raise TypeError(phase)

		# hase is between -360 and 360
		if not (-360 <= phase <= 360):
			raise ValueError(phase)

		if phase < 0:
			phase += 3600

		# round to nearest 0.1 value
		phase=int(round(phase*10))

		self.__sendwritecmd(jds6600.PHASE,phase)
	# end getphase

	
	#######################
	# Part 4: reading / changing mode
	# get mode
	def getmode(self):
		mode=self.__getdata(jds6600.MODE)


		# mode is in the list "modes". mode-name "" means undefinded
		mode=int(mode)>>3

		try:
			(modeid,modetxt)=jds6600.__modes[mode]
		except IndexError:
			raise UnexpectedValueError(mode)

		# modeid 3 is not valid and returns an id of -1
		if modeid >= 0:
			return modeid,modetxt
		# end if


		# modeid 4
		raise UnexpectedValueError(mode)

	# end getmode


	# set mode
	def setmode(self,mode, nostop=False):
		if (type(mode) != int) and (type(mode) != str): raise TypeError(mode)


		modeid=-1
		# if mode is an integer, it should be between 0 and 9
		if type(mode) == int:
			if not (0 <= mode <= 9):
				raise ValueError(mode)
			# end if

			# modeid 3 / modetxt "" does not exist
			if mode == 3:
				raise ValueError("mode 3 does not exist")
			# end if

			
			# valid modeid
			modeid = mode

		else:
			# modeid 3 / modetxt "" does not exist
			if mode == "":
				raise ValueError("mode 3 does not exist")
			# end if

			# mode is string -> check list
			# (note: the modes-list is not enumerated like the other lists, so an "array.index("text")" search is not possible
			for mid,mtxt in jds6600.__modes:
				if mode.upper() == mtxt:
					# found it!!!
					modeid=mid
					break
				# end if
			else:
				# mode not found -> error
				raise ValueError(mode)
			# end for
		# end else - if

		# before changing mode, disable all actions (unless explicitally asked not to do)
		if nostop == False:
			self.__setaction("STOP")
		# endif

		# set mode
		self.__sendwritecmd(jds6600.MODE,modeid)

		# if new mode is "burst", reset burst counter
		if modeid == 9:
			self.burst_resetcounter()
		# end if
		
	# end setmode
	
	#######################
	# Part 5: functions common for all modes
	def stopallactions(self):
		# just send stop
		self.__setaction("STOP")
	# end stop all actions


	#######################
	# Part 6: "measure" mode

	# get coupling parameter (measure mode)
	def measure_getcoupling(self):
		coupling=self.__getdata(jds6600.MEASURE_COUP)

		try:
			return (coupling,jds6600.__measure_coupling[coupling])
		except IndexError:
			raise UnexpectedValueError(coupling)
		# end try
	# end get coupling (measure mode)

	# get gate time (measure mode)
	#  get (measure mode)
	def measure_getgate(self):
		gate=self.__getdata(jds6600.MEASURE_GATE)


		# gate unit is 0.01 seconds
		return gate / 100
	# end get gate (measure mode)


	# get Measure mode (freq or period)
	def measure_getmode(self):
		mode=self.__getdata(jds6600.MEASURE_MODE)

		try:
			return (mode,jds6600.__measure_mode[mode])
		except IndexError:
			raise UnexpectedValueError(mode)
		# end try
	# end get mode (measure)


	
	# set measure coupling
	def measure_setcoupling(self,coupling):
		# type checks
		if (type(coupling) != int) and (type(coupling) != str): raise TypeError(coupling)


		if type(coupling) == int:
			# coupling is 0 (DC) or 1 (AC)
			if not (coupling in (0,1)):
				raise ValueError(coupling)

			coupl=coupling

		else:
			# string based
			
			coupling=coupling.upper()
			# spme shortcuts:
			if coupling == "AC": coupling = "AC(EXT.IN)"
			if coupling == "DC": coupling = "DC(EXT.IN)"

			try:
				coupl=jds6600.__measure_coupling.index(coupling)
			except ValueError:
				errmsg="Unknown measure-mode coupling: "+coupling
				raise ValueError(errmsg)
			# end try
		 # end else ) if (type is int or str?)

		# set mode
		self.__sendwritecmd(jds6600.MEASURE_COUP,coupl)

	# end set measure_coupling 

	# set gate time (measure mode)
	def measure_setgate(self, gate):
		# check type
		if (type(gate) != int) and (type(gate) != float): raise TypeError(gate)

		# gate unit is 0.01 and is between 0 and 10
		if not (0 < gate <= 1000):
			raise ValueError(gate)

		gate = int(round(gate*100))

		# minimum is 0.01 second
		if gate == 0:
			gate = 0.01

		# set gate
		self.__sendwritecmd(jds6600.MEASURE_GATE,gate)
	# end get gate (measure mode)


	# set measure mode
	def measure_setmode(self,mode):
		# type checks
		if (type(mode) != int) and (type(mode) != str): raise TypeError(mode)


		if type(mode) == int:
			# mode is 0 (M.FREQ) or 1 (M.PRERIOD)
			if not (mode in (0,1)):
				raise ValueError(mode)

		else:
			# string based

			# make uppercase
			mode=mode.upper()
			
			# spme shortcuts:
			if mode== "FREQ": mode = "M.FREQ"
			if mode== "PERIOD": mode = "M.PERIOD"

			try:
				mode=jds6600.__measure_mode.index(mode)
			except ValueError:
				errmsg="Unknown measure mode: "+mode
				raise ValueError(errmsg)
			# end try

		 # end else ) if (type is int or str?)

		# set mode
		self.__sendwritecmd(jds6600.MEASURE_MODE,mode)

	# end set measure_coupling 

	# get Measure freq. (lowres / Freq-mode)
	def measure_getfreq_f(self):
		freq=self.__getdata(jds6600.MEASURE_DATA_FREQ_LOWRES)

		# unit is 0.1 Hz
		return freq/10
	# end get freq-Lowres (measure)

	# get Measure freq. (highes / Periode-mode)
	def measure_getfreq_p(self):
		freq=self.__getdata(jds6600.MEASURE_DATA_FREQ_HIGHRES)

		# unit is 0.001 Hz
		return freq/1000
	# end get freq-Lowres (measure)

	# get Measure pulsewith +
	def measure_getpw1(self):
		pw=self.__getdata(jds6600.MEASURE_DATA_PW1)

		# unit is 0.01 microsecond
		return pw/100
	# end get pulsewidth -

	# get Measure pulsewidth -
	def measure_getpw0(self):
		pw=self.__getdata(jds6600.MEASURE_DATA_PW0)

		# unit is 0.01 microsecond
		return pw/100
	# end get pulsewidth +

	# get Measure total period
	def measure_getperiod(self):
		period=self.__getdata(jds6600.MEASURE_DATA_PERIOD)

		# unit is 0.01 microsecond
		return period/100
	# end get total period

	# get Measure dutycycle
	def measure_getdutycycle(self):
		dutycycle=self.__getdata(jds6600.MEASURE_DATA_DUTYCYCLE)

		# unit is 0.1 %
		return dutycycle/10
	# end get freq-Lowres (measure)

	# get Measure unknown value 1 (related to freq, inverse-related to gatetime)
	def measure_getu1(self):
		# unit is unknown, just return it
		return self.__getdata(jds6600.MEASURE_DATA_U1)
	# end get freq-Lowres (measure)

	# get Measure unknown value 2 (inverse related to freq)
	def measure_getu2(self):
		# unit is unknown, just return it
		return self.__getdata(jds6600.MEASURE_DATA_U2)
	# end get freq-Lowres (measure)

	# get Measure unknown value 3 (nverse related to freq)
	def measure_getu3(self):
		# unit is unknown, just return it
		return self.__getdata(jds6600.MEASURE_DATA_U3)
	# end get freq-Lowres (measure)


	# get Measure all (all usefull data: freq_f, freq_p, pw1, pw0, period, dutycycle
	def measure_getall(self):

		# do query for 6 values (start with freq_q)
		(freq_f, freq_p, pw1, pw0, period, dutycycle)=self.__getdata(jds6600.MEASURE_DATA_FREQ_LOWRES,6)

		# return all
		return (freq_f / 10, freq_p / 1000, pw1/100, pw0/100, period/100, dutycycle/10)
	# end get freq-Lowres (measure)



	#######################
	# Part 7: "Counter" mode

	# counter getcoupling is the same as measure getcoupling
	def counter_getcoupling(self):
		return self.measure_getcoupling()
	# end counter get coupling

	# get counter - counter
	def counter_getcounter(self):
		# unit is  1, just return data
		return self.__getdata(jds6600.COUNTER_DATA_COUNTER)
	# end get counter - counter

	# counter setcoupling is the same as measure setcoupling
	def counter_setcoupling(self,coupling):
		self.measure_setcoupling(coupling)
	# end counter get coupling


	# counter - reset counter
	def counter_reset(self):
		# write 0 to register "COUNTER_RESETCOUNTER"
			self.__sendwritecmd(jds6600.COUNTER_RESETCOUNTER,0)
	# end counter reset counter

	# start counter mode
	def counter_start(self):
		mode=self.getmode()

		if mode[1] != "COUNTER":
			raise WrongMode()
		# end if

		# action start BURST mode
		self.__setaction("COUNT")
	# end counter_start
		

	def counter_stop(self):
		# just send stop
		self.__setaction("STOP")
	# end counter_stop
		




	#######################
	# Part 8: "Sweep" mode

	# note, there are two "setmode" commands to enter "sweep" mode: "sweep_ch1' (mode 6) and "sweep_ch2" (mode 7)

	def sweep_getstartfreq(self):
		# unit is  0.01Hz -> divide by 100
		return self.__getdata(jds6600.SWEEP_STARTFREQ)/100
	# end get sweep - startfreq

	def sweep_getendfreq(self):
		# unit is  0.01 Hz -> divide by 100
		return self.__getdata(jds6600.SWEEP_ENDFREQ)/100
	# end get sweep - startfreq

	def sweep_gettime(self):
		# unit is  0.1 sec -> divide by 10
		return self.__getdata(jds6600.SWEEP_TIME)/10
	# end get sweep - startfreq


	# get sweep direction
	def sweep_getdirection(self):
		direction=self.__getdata(jds6600.SWEEP_DIRECTION)

		try:
			return (direction,jds6600.__sweep_direction[direction])
		except IndexError:
			raise UnexpectedValueError(direction)
		# end try
	# end get direction (sweep)

	# get sweep mode
	def sweep_getmode(self):
		mode=self.__getdata(jds6600.SWEEP_MODE)

		try:
			return (mode,jds6600.__sweep_mode[mode])
		except IndexError:
			raise UnexpectedValueError(mode)
		# end try
	# end get mode (measure)

	def sweep_setstartfreq(self, frequency):
		if (type(frequency) != int) and (type(frequency) != float): raise TypeError(frequency)

		# frequency should be between 0 and 60 MHz
		if not (0 <= frequency <= 60000000):
			raise ValueError(frequency)

		# frequency unit is 0.01 Hz
		freq=int(round(frequency*100))

		self.__sendwritecmd(jds6600.SWEEP_STARTFREQ,freq)
	# end set start freq

	def sweep_setendfreq(self, frequency):
		if (type(frequency) != int) and (type(frequency) != float): raise TypeError(frequency)

		# frequency should be between 0 and 60 MHz
		if not (0 <= frequency <= 60000000):
			raise ValueError(frequency)

		# frequency unit is 0.01 Hz
		freq=int(round(frequency*100))

		self.__sendwritecmd(jds6600.SWEEP_ENDFREQ,freq)
	# end set end freq


	def sweep_settime(self, time):
		if (type(time) != int) and (type(time) != float): raise TypeError(time)

		# time should be between 0 and 999.9 seconds
		if not (0 < time <=  999.9):
			raise ValueError(time)

		# time unit is 0.1 second
		t=int(round(time*10))

		self.__sendwritecmd(jds6600.SWEEP_TIME,t)
	# end set end freq


	def sweep_setdirection(self, direction):
		if (type(direction) != int) and (type(direction) != str): raise TypeError(direction)

		if type(direction) == int:
			# mode is 0 (RISE), 1 (FALL) or 2 (RISE&FALL)
			if not (direction in (0,1,2)):
				raise ValueError(direction)

		else:
			# string based

			# make uppercase
			direction=direction.upper()
			
			# spme shortcuts:
			if direction == "RISEFALL": direction = "RISE&FALL"
			if direction == "BOTH": direction = "RISE&FALL"

			try:
				direction=jds6600.__sweep_direction.index(direction)
			except ValueError:
				errmsg="Unknown sweep direction: "+direction
				raise ValueError(errmsg)
			# end else - for
		 # end else ) if (type is int or str?)

		# set mode
		self.__sendwritecmd(jds6600.SWEEP_DIRECTION,direction)
	# end set direction (sweep)


	def sweep_setmode(self, mode):
		if (type(mode) != int) and (type(mode) != str): raise TypeError(mode)

		if type(mode) == int:
			# mode is 0 (LINEAR) or 1 (LOGARITHM)) 
			if not (mode in (0,1)):
				raise ValueError(mode)

		else:
			# string based

			# make uppercase
			mode=mode.upper()
			
			# spme shortcuts:
			if mode == "LIN": mode = "LINEAR"
			if mode == "LOG": mode = "LOGARITHM"

			try:
				mode=jds6600.__sweep_mode.index(mode)
			except ValueError:
				errmsg="Unknown sweep mode: "+mode
				raise ValueError(errmsg)
			# end else - for
		 # end else ) if (type is int or str?)

		# set mode
		self.__sendwritecmd(jds6600.SWEEP_MODE,mode)
	# end set direction (sweep)




	# get sweep channel
	def sweep_getchannel(self):
		mode=self.getmode()

		if mode[1] == "SWEEP_CH1":
			return 1
		elif mode[1] == "SWEEP_CH2":
			return 2
		# end if - elif

		# not channel 1 or channel 2, return 0
		return 0
	# end sweep get_channel

	# set sweep channel
	def sweep_setchannel(self,channel):
		if type(channel) != int: raise TypeError(channel)

		# new channel should be 1 or 2
		if not (channel in (1,2)):
			raise ValueError(channel)
		# end if

		# get current channel (1 or 2, or 0 if not in sweep mode)
		currentchannel=self.sweep_getchannel()

		# only swich if already in sweep mode
		if currentchannel == 0:
			raise WrongMode()
		#endif

		# switch if the new channel is different from current channel
		if channel != currentchannel:
			if channel == 1:
				self.setmode("SWEEP_CH1",nostop=True)
			else:
				self.setmode("SWEEP_CH2",nostop=True)
			# end else - if
		# end if
	# end sweep set channel
		

	# start sweep
	def sweep_start(self):
		mode=self.getmode()

		if (mode[1] != "SWEEP_CH1") and (mode[1] != "SWEEP_CH2"):
			raise WrongMode()
		# end if

		# action start BURST mode
		self.__setaction("SWEEP")
	# end sweep_start
		

	# stop sweep
	def sweep_stop(self):
		# just send stop
		self.__setaction("STOP")
	# end sweep_start
		


	##################################

	
	#######################
	# Part 9: PULSE


	# get pulsewidth, normalised to s
	def pulse_getpulsewidth(self):
		# pulsewith returns two datafiels, periode + multiplier
		time,multi = self.__getdata(jds6600.PULSE_PULSEWIDTH)

		if multi==0: return time / 1000000000 # ns
		elif multi == 1: return time / 1000000 # us
		else:
			UnexptectedValue(multi)
		# end else - elsif - if
	# end 

	# get pulsewidth, not normalised
	def pulse_getpulsewidth_m(self):
		# pulsewith returns two datafiels, periode + multiplier
		return self.__getdata(jds6600.PULSE_PULSEWIDTH)
	# end 


	# get period, normalised to s
	def pulse_getperiod(self):
		# period returns two datafiels, periode + multiplier
		time,multi = self.__getdata(jds6600.PULSE_PERIOD)

		if multi==0: return time / 1000000000 # ns
		elif multi == 1: return time / 1000000 # us
		else:
			UnexptectedValue(multi)
		# end else - elsif - if
	# end 


	# get period, not normalised
	def pulse_getperiod_m(self):
		# period returns two datafiels, periode + multiplier
		return self.__getdata(jds6600.PULSE_PERIOD)
	# end 

	# get offset
	def pulse_getoffset(self):
		# unit is %, just return data
		return self.__getdata(jds6600.PULSE_OFFSET)
	# end 

	# get amplitude
	def pulse_getamplitude(self):
		# unit 0.01, divide by 100
		return self.__getdata(jds6600.PULSE_AMPLITUDE)/100
	# end 

	# set pulsewith or period (backend function)
	def __pulse_setpw_period(self, var, data, multiplier, normalised):
		maxval=([4e9,4e9],(4,4000)) # maximum data value
		minval=((30,1),(30e-9,1e-6)) # minimum data value
		multi=(1e9,1e6) # unit is 1ns or 1 us
		data2reg=(jds6600.PULSE_PULSEWIDTH,jds6600.PULSE_PERIOD)
		data2txt=("pulsewidth","period")

		if (type(var) != int) or ((var != 0) and (var != 1)): raise RuntimeError("error __pulse_setpw_period: var") # var is 0 (for pulsewidth) or 1 (period)
		if (type(data) != int) and (type(data) != float): raise TypeError(period)
		if (type(normalised) != int) or not (normalised in (0,1)): raise RuntimeError("error __pulse_setpw_period: normalised")

		if type(multiplier) != int: raise TypeError(multiplier)

		# multiplier should be 0 or 1
		if not (multiplier in (0,1)):
			errmsg="multiplier must be 0 (ns) or 1 (us)"
			raise ValueError(errmsg)
		# end if

		# data must be between to allocated limits:
		# not normalised: allowed values: 30 to 400000000 (multi=0) / 1 to 4000000000 (multi=1)
		# normalised: allowed values: 30 ns to 4 sec. (multi=0) / 1 us to 4000 sec (multi=2)
		if not (minval[normalised][multiplier] <= data <= maxval[normalised][multiplier]):
			errmsg="{} must be between {} and {}".format(data2txt[var],minval[normalised][multiplier],maxval[normalised][multiplier])
			raise ValueError(errmsg)
		# end if


		# convert from s to ns/us, if needed
		if normalised == 1:
			data = str(round(data * multi[multiplier]))+","+str(multiplier)
		else:
			data = str(int(data))+","+str(multiplier)
		# end if

		# done: now write
		self.__sendwritecmd(data2reg[var],data)
	# end set pw/period, low-level function


	# set pw, normalised
	def pulse_setpulsewidth(self,pw,multiplier=0):
		# convert to low-level function
		self.__pulse_setpw_period(0,pw,multiplier,1)
	# end pulse_setpw (normalised)
	
	# set pw, not normalised
	def pulse_setpulsewidth_m(self,pw,multiplier):
		# convert to low-level function
		self.__pulse_setpw_period(0,pw,multiplier,0)
	# end pulse_setpw (normalised)
	
	# set period, normalised
	def pulse_setperiod(self,pw,multiplier=0):
		# convert to low-level function
		self.__pulse_setpw_period(1,pw,multiplier,1)
	# end pulse_setperiod (normalised)
	
	# set period, not normalised
	def pulse_setperiod_m(self,pw,multiplier):
		# convert to low-level function
		self.__pulse_setpw_period(1,pw,multiplier,0)
	# end pulse_setperiod (normalised)
	

	# set pulse offset
	def pulse_setoffset(self,offset):
		if (type(offset) != int) and (type(offset) != float): raise TypeError(offset)

		# offset is between 0 and 120 %
		if not (0 <= offset <= 120):
			errmsg="Offset must be between 0 and 120 %"
			raise ValueError(errmsg)
		# end if

		# unit = 1 -> just send
		self.__sendwritecmd(jds6600.PULSE_OFFSET,offset)
	# end off


	# set pulse amplitude
	def pulse_setamplitude(self,amplitude):
		if (type(amplitude) != int) and (type(amplitude) != float): raise TypeError(amplitude)

		# amplitude is between 0 and 10 V
		if not (0 <= amplitude <= 10):
			errmsg="Amplitude must be between 0 and 10 Volt"
			raise ValueError(errmsg)
		# end if

		# unit is 0.01V
		amplitude=int(round(amplitude*100))
		self.__sendwritecmd(jds6600.PULSE_AMPLITUDE,amplitude)
	# end off


	def pulse_start(self):
		mode=self.getmode()

		if mode[1] != "PULSE":
			raise WrongMode()
		# end if

		# action start BURST mode
		self.__setaction("PULSE")
	# end pulse_start
		

	def pulse_stop(self):
		# just send stop
		self.__setaction("STOP")
	# end pulse_stop


	#######################
	# Part 10: BURST


	def burst_getnumberofbursts(self):
		# unit is 1, just return value
		return self.__getdata(jds6600.BURST_NUMBER)
	# end burst get number of bursts

	def burst_getmode(self):
		mode = self.__getdata(jds6600.BURST_MODE)

		try:
			return(mode,jds6600.__burst_mode[mode])
		except IndexError:
			raise UnexpectedValue(mode)
			
		# end try
	# end burst get mode


	def burst_setnumberofbursts(self,burst):
		if type(burst) != int: raise TypeError(burst)

		# number of burst should be between 1 and 1048575
		if not (1 <= burst <= 1048575):
			errmsg="Number of bursts should be between 1 and 1048575"
			raise ValueError(errmsg)
		# end if

		# unit is 1, just return value
		self.__sendwritecmd(jds6600.BURST_NUMBER,burst)
	# end burst get number of bursts


	def burst_setmode(self,mode):
		if (type(mode) != int) and (type(mode) != str): raise TypeError(mode)

		if type(mode) == int:
			# mode input is an integer
			# mode should be between 0 and 3
			if not (0 <= mode <= 3):
				errmsg="Burst mode should between 0 and 3"
				raise ValueError(mode)
			# end if
		else:
			# mode input is a string

			mode=mode.upper()

			# shortcuts
			if mode == "MANUAL": mode = "MANUAL TRIG."
			if mode == "CH2": mode = "CH2 TRIG."
			if mode == "EXT.AC": mode = "EXT.TRIG(AC)"
			if mode == "EXT.DC": mode = "EXT.TRIG(DC)"

			try:
				mode=jds6600.__burst_mode.index(mode.upper())
			except ValueError:
				errmsg="Unknown burst mode: "+mode
				raise ValueError(errmsg)
			# end try

		# end else - if

		# stop if the burst-mode is running
		self.burst_stop()
	
		# write command
		self.__sendwritecmd(jds6600.BURST_MODE,mode)

	def burst_resetcounter(self):
		# reset counter: same as counter_reset_counter
		self.counter_reset()
	# end reset counter


	def burst_start(self):
		mode=self.getmode()

		if mode[1] != "BURST":
			raise WrongMode()
		# end if

		# action start BURST mode
		self.__setaction("BURST")
	# end burst_start
		

	def burst_stop(self):
		# just send stop
		self.__setaction("STOP")
	# end burst_start
		
	#######################
	# Part 11: SYSTEM

	########
	# part 11.1: system parameters

	# NOTE:	there is a strange behaviour in some jds6600 devices where that the register to
	#			read the sysem-parameters is one higher then the registernumber use to write
	#			the parameter-value.
	#			This is probably a bug. The bug-fix code to deal with this situation can be
	#			be overwriten adding a "bugfix=0" option in the system_get* API-calls

	# get sound setting
	def system_getsound(self, bugfix=True):
		if bugfix == True:
			sound=self.__getdata(jds6600.SYSTEM_SOUND+1)
		elif bugfix == False:
			sound=self.__getdata(jds6600.SYSTEM_SOUND)
		else: TypeError(bugfix)

		# we should receive a 0 or 1
		try:
			return (False,True)[sound]
		except IndexError:
			raise UnexpectedValueError(sound)
	#end system_getsound

	# get brightness setting
	def system_getbrightness(self, bugfix=True):
		if bugfix == True:
			return self.__getdata(jds6600.SYSTEM_BRIGHTNESS+1)
		elif bugfix == False:
			return self.__getdata(jds6600.SYSTEM_BRIGHTNESS)
		else: TypeError(bugfix)
	#end system_getbrightness

	# get language setting
	def system_getlanguage(self, bugfix=True):
		if bugfix == True:
			language=self.__getdata(jds6600.SYSTEM_LANGUAGE+1)
		elif bugfix == False:
			language=self.__getdata(jds6600.SYSTEM_LANGUAGE)
		else: TypeError(bugfix)

		# we should receive a 0 or a 1
		try:
			return language,jds6600.__system_language[language]
		except KeyError:
			raise UnexpectedValueError(sound)
	#end system_getlanguage

	def system_getsync(self, bugfix=True):
		if bugfix == True:
			sync=self.__getdata(jds6600.SYSTEM_SYNC+1)
		elif bugfix == False:
			sync=self.__getdata(jds6600.SYSTEM_SYNC)
		else: TypeError(bugfix)

		# returns a list of 5 fields: frequency, wave, amplitude, dutycycle and offset
		if len(sync) != 5:
			raise UnexpectedValueError(sync)
		# end if

		# return data
		ret=[]
		for s in sync:
			if s not in (0,1): raise UnexpectedValueError(sync)

			ret.append((False,True)[s])
		# end for

		# return  data
		return ret
	# end system_getsync


	# get maximum number of arbitrary waveforms
	def system_getarbmaxnum(self, bugfix=True):
		if bugfix == True:
			return self.__getdata(jds6600.SYSTEM_ARBMAXNUM+1)
		elif bugfix == False:
			return self.__getdata(jds6600.SYSTEM_ARBMAXNUM)
		else: TypeError(bugfix)
	#end system_getlanguage


	# set system sound
	def system_setsound(self,sound):
		if type(sound) != bool: raise TypeError(sound)

		if sound == True:
			self.__sendwritecmd(jds6600.SYSTEM_SOUND,1)
		else:
			self.__sendwritecmd(jds6600.SYSTEM_SOUND,0)
	# end set sound

	# set system brightness
	def system_setbrightness(self,brightness):
		if type(brightness) != int: raise TypeError(brightness)

		# should be between 1 and 12
		if not(1 <= brightness <= 12):
			raise ValueError(brightness)

		self.__sendwritecmd(jds6600.SYSTEM_BRIGHTNESS,brightness)
	# end set sound


	# set system language
	def system_setlanguage(self,language):
		if (type(language) != int) and (type(language) != str): raise TypeError(language)

		if type(language) == int:
			# integer
			if language not in (0,1): raise ValueError(sound)
		else:
			# string
			# shortcuts:
			if language == "EN": language = "ENGLISH"
			if language == "CH": language = "CHINESE"

			try:
				language=jds6600.__system_language.index(language.upper())
			except ValueError:
				errmsg="Unknown language: "+language
				raise ValueError(errmsg)
			# end try
		# end else - if

		self.__sendwritecmd(jds6600.SYSTEM_LANGUAGE,language)
		
		# reinit "mode" to refresh screen for language change to become active
		(mode,modetxt)=self.getmode()
		self.setmode(mode)
	# end set language

	# set system sync
	def system_setsync(self,freq,wave,ampl,duty,offs):

		if type(freq) != bool: raise TypeError(freq)
		if type(wave) != bool: raise TypeError(wave)
		if type(ampl) != bool: raise TypeError(ampl)
		if type(duty) != bool: raise TypeError(duty)
		if type(offs) != bool: raise TypeError(offs)

		# create command to send
		sync=[freq,wave,ampl,duty,offs]
		for i in range(5):
			sync[i] = '1' if sync[i] == True else '0'


		# merge all 5 elements in one command, seperated by ","
		self.__sendwritecmd(jds6600.SYSTEM_SYNC,",".join(sync))
	# end set sync

	# set maximum number of arbitrary waveforms
	def system_setarbmaxnum(self,arbmaxnum):
		if type(arbmaxnum) != int: raise TypeError(arbmaxnum)

		# abrmaxnum should be between 1 and 60
		if not(1 <= arbmaxnum <= 60):
			raise ValueError(arbmaxnum)

		self.__sendwritecmd(jds6600.SYSTEM_ARBMAXNUM,arbmaxnum)
	# end set arbmaxnum




	######
	# part 11.2: save / read / clear profile

	def system_saveprofile(self,profile):
		if type(profile) != int: raise TypeError(profile)

		# profile is between 0 and 99
		if not(0 <= profile <= 99): raise ValueError(errmsg)

		# write profile to "PROFILE_SAVE"
		self.__sendwritecmd(jds6600.PROFILE_SAVE,profile)
	# end profile save

	def system_loadprofile(self,profile):
		if type(profile) != int: raise TypeError(profile)

		# profile is between 0 and 99
		if not(0 <= profile <= 99): raise ValueError(errmsg)

		# write profile to "PROFILE_LOAD"
		self.__sendwritecmd(jds6600.PROFILE_LOAD,profile)
	# end profile load

	def system_clearprofile(self,profile):
		if type(profile) != int: raise TypeError(profile)

		# profile is between 0 and 99
		if not(0 <= profile <= 99): raise ValueError(errmsg)

		# write profile to "PROFILE_CLEAR"
		self.__sendwritecmd(jds6600.PROFILE_CLEAR,profile)
	# end profile clear



	#######################
	# Part 12: Arbitrary waveform operations

	def arb_getwave(self,waveid):
		if type(waveid) != int: raise TypeError(waveid)

		# waveid is between 1 and 60
		if not(1 <= waveid <= 60): raise ValueError(waveid)

		# getdata, reg=waveform id, data = 1, a=1 (register/waveform selector)
		return self.__getdata(waveid,1,a=1)
	# end get arbtrary waveform


	def arb_setwave(self,waveid,wave):
		if type(waveid) != int: raise TypeError(waveid)
		if (type(wave) != tuple) and (type(wave) != list): raise TypeError(wave)
		
		# waveid is between 1 and 60
		if not(1 <= waveid <= 60): raise ValueError(waveid)

		# wave should be a list or tuple of 2048 elements, all integers, with a value between 0 and 4095
		if len(wave) != 2048: raise ValueError(wave)

		tosend=""
		for val in wave:
			if type(val) != int: raise ValueError(wave)
			if not (0 <= val <= 4095): raise ValueError(wave)

			tosend += (str(val) if tosend=="" else ","+str(val))
		# end for
			
		# write waveform, reg=waveform id, data = waveform, a=1 (register/waveform selector)
		self.__sendwritecmd(waveid,tosend,a=1)

	# end set arbirtary waveform

	##################################

# end class jds6600
