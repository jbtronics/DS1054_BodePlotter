from jds6600 import *

import numpy as np
import time
from ds1054z import DS1054Z
import argparse

import matplotlib.pyplot as plt

import scipy.signal

parser = argparse.ArgumentParser(description="This program plots Bode Diagrams of a DUT using an JDS6600 and Rigol DS1054Z")

parser.add_argument('MIN_FREQ', metavar='min', type=float, help="The minimum frequency for which should be tested")
parser.add_argument('MAX_FREQ', metavar='max', type=float, help="The maximum frequency for which should be tested")
parser.add_argument('COUNT', metavar='N', nargs="?", default=50, type=int, help='The number of frequencies for which should be probed')
parser.add_argument("--awg_port", dest="AWG_PORT", default="COM3", help="The serial port where the JDS6600 is connected to")
parser.add_argument("--ds_ip", default="auto", dest="OSC_IP", help="The IP address of the DS1054Z. Set to auto, to auto discover the oscilloscope via Zeroconf")
parser.add_argument("--linear", dest="LINEAR", action="store_true", help="Set this flag to use a linear scale")
parser.add_argument("--awg_voltage", dest="VOLTAGE", default=5, type=float, help="The amplitude of the signal used for the generator")
parser.add_argument("--step_time", dest="TIMEOUT", default=0.00, type=float, help="The pause between to measurements in ms.")
parser.add_argument("--phase", dest="PHASE", action="store_true", help="Set this flag if you want to plot the Phase diagram too")
parser.add_argument("--no_smoothing", dest="SMOOTH", action="store_false", help="Set this to disable the smoothing of the data with a Savitzky–Golay filter")
parser.add_argument("--use_manual_settings", dest="MANUAL_SETTINGS", action="store_true", help="When this option is set, the options on the oscilloscope for voltage and time base are not changed by this program.")
parser.add_argument("--output", dest="file", type=argparse.FileType("w"), help="Write the measured data to the given CSV file.")


args = parser.parse_args()

if args.OSC_IP == "auto":
    import ds1054z.discovery
    results = ds1054z.discovery.discover_devices()
    if not results:
        print("No Devices found! Try specifying the IP Address manually.")
        exit()
    OSC_IP = results[0].ip
    print("Found Oscilloscope! Using IP Address " + OSC_IP)
else:
    OSC_IP = args.OSC_IP

DEFAULT_PORT = args.AWG_PORT
MIN_FREQ = args.MIN_FREQ
MAX_FREQ = args.MAX_FREQ
STEP_COUNT = args.COUNT

# Do some validity checs
if MIN_FREQ < 0 or MAX_FREQ < 0:
    exit("Frequencies has to be greater 0!")

if MIN_FREQ >= MAX_FREQ:
    exit("MAX_FREQ has to be greater then min frequency")

if STEP_COUNT <= 0:
    exit("The step count has to be positive")

TIMEOUT = args.TIMEOUT

AWG_CHANNEL = 1
AWG_VOLT = args.VOLTAGE

print("Init AWG")

awg = jds6600(DEFAULT_PORT)

AWG_MAX_FREQ = awg.getinfo_devicetype()
print("Maximum Generator Frequency: %d MHz"% AWG_MAX_FREQ)
if MAX_FREQ > AWG_MAX_FREQ * 1e6:
    exit("Your MAX_FREQ is higher than your AWG can achieve!")

# We use sine for sweep
awg.setwaveform(AWG_CHANNEL, "sine")

# Init scope
scope = DS1054Z(OSC_IP)

# Set some options for the oscilloscope

if not args.MANUAL_SETTINGS:
    # Center vertically
    scope.set_channel_offset(1, 0)
    scope.set_channel_offset(2, 0)

    # Set the sensitivity according to the selected voltage
    scope.set_channel_scale(1, args.VOLTAGE / 3, use_closest_match=True)
    # Be a bit more pessimistic for the default voltage, because we run into problems if it is too confident
    scope.set_channel_scale(2, args.VOLTAGE / 2, use_closest_match=True) 

freqs = np.linspace(MIN_FREQ, MAX_FREQ, num=STEP_COUNT)

if not args.LINEAR:
    freqs = np.logspace(np.log10(MIN_FREQ), np.log10(MAX_FREQ), num=STEP_COUNT)
else:
    freqs = np.linspace(MIN_FREQ, MAX_FREQ, num=STEP_COUNT)

# Set amplitude
awg.setamplitude(AWG_CHANNEL, AWG_VOLT)

volts = list()
phases = list()

# We have to wait a bit before we measure the first value
awg.setfrequency(AWG_CHANNEL, float(freqs[0]))
time.sleep(0.05)

for freq in freqs:
    awg.setfrequency(AWG_CHANNEL, float(freq))
    time.sleep(TIMEOUT)
    volt = scope.get_channel_measurement(2, 'vpp')
    volts.append(volt)

    # Use a better timebase
    if not args.MANUAL_SETTINGS:
        # Display one period in 3 divs
        period = (1/freq) / 3
        scope.timebase_scale = period

        # Use better voltage scale for next time
        if volt:
            scope.set_channel_scale(2, volt / 2, use_closest_match=True)

    # Measure phase
    if args.PHASE:
        phase = scope.get_channel_measurement('CHAN1, CHAN2', 'rphase')
        if phase:
            phase = -phase
        phases.append(phase)

    print(freq)

# Write data to file if needed
if args.file:

    if args.PHASE:
        args.file.write("Frequency in Hz; Amplitude in V; Phase in Degree\n")
    else:
        args.file.write("Frequency in Hz; Amplitude in V\n")

    for n in range(1, len(freqs) -1):
        if volts[n]:
            volt = volts[n]
        else:
            volt = float("nan")
        
        if args.PHASE:
            if phases[n]:
                phase = phases[n]
            else:
                phase = phases[n]
            args.file.write("%f;%f;%f \n"%(freqs[n], volt, phase))
        else:
            args.file.write("%f;%f \n"%(freqs[n], volt))
      
    args.file.close()

# Plot graphics

plt.plot(freqs, volts, label="Measured data")
if args.SMOOTH:
    try:
        yhat = scipy.signal.savgol_filter(volts, 9, 3) # window size 51, polynomial order 3
        plt.plot(freqs, yhat, "--", color="red", label="Smoothed data")
    except:
        print("Error during smoothing amplitude data")

plt.title("Amplitude diagram (N=%d)"%STEP_COUNT)
plt.xlabel("Frequency [Hz]")
plt.ylabel("Voltage Peak-Peak [V]")
plt.legend()

# Set log x axis
if not args.LINEAR:
    plt.xscale("log")

plt.show()

if args.PHASE:
    plt.plot(freqs, phases)
    plt.title("Phase diagram (N=%d)"%STEP_COUNT)
    plt.ylabel("Phase [°]")
    plt.xlabel("Frequency [Hz]")

    if args.SMOOTH:
        try:
            yhat = scipy.signal.savgol_filter(phases, 9, 3) # window size 51, polynomial order 3
            plt.plot(freqs, yhat, "--", color="red", label="Smoothed data")
        except:
            print("Error during smoothing phase data")
        

    # Set log x axis
    if not args.LINEAR:
        plt.xscale("log")

    plt.show()