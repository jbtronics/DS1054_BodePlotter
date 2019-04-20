# DS1054Z_BodePlotter
A Python program that plots Bode diagrams of a component using a Rigol DS1054Z Oscilloscope and a JDS6600 DDS Generator.

# Requirements
DS1054Z_BodePlotter needs a numpy/scipy/matplotlib environment. Under Linux Distros you can install these via package manager ([See here](https://www.scipy.org/install.html) for more informations).
Under Windows you can use [Anaconda](https://www.anaconda.com/).

Further you will need to install pyserial, DS1054Z, and (optional) zeroconf. You can do this via pip:
``` pip install pyserial ds1054z zeroconf ```

# Hardware setup
Connect your JDS6600 via USB with you computer and connect the DS1054Z to network (via Ethernet port).

Connect the Channel 1 output of the JDS6600 to CH1 of the DS1054Z and to the input of the component you want to test (DUT = Device under test). Connect CH2 of the DS1054Z to the output of the DUT.

# Usage
The basic syntax is `python bode.py MIN_FREQ MAX_FREQ [FREQ_COUNT]`, so if you, for example, want to test your DUT between 1kHz and 2.2Mhz, with 100 steps (default is 50),
you can do it like this: `python bode.py 1e3 2.2e6 100`.

If you have installed zeroconf, the program will try to find your Oscilloscope automatically, if not you will have to specify the IP via the `--ds_ip` option. Mostl likely you will also have to specify the serial port of the JDS6600, you can do this with `--awg-port`.

By default only the Amplitude diagram is measured and plotted. If you also want to get the Phase diagram, you will have to specify the `--phase` flag.

If you want to use the measured data in another software like OriginLab or Matlab, you can export it to a semicolon-seperated CSV file with the `--output` option.

So a typical command line would like this: ```python bode.py 1e3 2.2e6 100 --ds_ip 192.168.1.108 --awg_port /dev/ttyUSB0 --phase --output out.csv```

# Output examples
Here are some measurements of a parallel LC circuit:
![Amplitude Diagram](https://github.com/jbtronics/DS1054_BodePlotter/raw/master/examples/LC_Amplitude.png)
![Phase Diagram](https://github.com/jbtronics/DS1054_BodePlotter/raw/master/examples/LC_PHASE.png)
