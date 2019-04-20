# DS1054Z_BodePlotter
A Python program that plots Bode diagrams of a component using a Rigol DS1054Z Oscilloscope and a JDS6600 DDS Generator.

# Requirements
DS1054Z_BodePlotter needs a numpy/scipy/matplotlib environment. Under Linux Distros you can install these via package manager ([See here](https://www.scipy.org/install.html) for more informations).
Under Windows you can use [Anaconda](https://www.anaconda.com/).

Further you will need to install pyserial, DS1054Z, and (optional) zeroconf. You can do this via pip:
``` pip install pyserial ds1054z zeroconf ```

# Usage
The basic syntax is `python bode.py MIN_FREQ MAX_FREQ [FREQ_COUNT]`, so if you, for example, want to test your DUT between 1kHz and 2.2Mhz, with 100 steps (default is 50),
you can do it like this: `python bode.py 1e3 2.2e6 100`
