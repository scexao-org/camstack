import numpy as np
import astropy.io.fits as pf

'''
What format do we want ?
We want to generate 32bit maps (fits) that indicate how to demangle the ocam files.

We have two size we need to handle
Full 240x240
  Camera output is 1056 x 121 8bit
  We EXPECT 528 x 121 16bit here (FG code must cast char* into a half-sized short*)

Full 120x120
  Camera output is 1056 x 62 8bit
  We EXPECT 528 x 62 16bit here

There are two maps for each size for two different modes:
    Forward lookup (matrox legacy)
        FG-sized maps, each pixel is the address in the final-sized image
        This allows a sliced, online rebuild
    Reverse lookup
        Final-size maps, each pixel is the address in the FG-sized image
        This is faster (if not online), because in binning, final size is significantly smaller.
'''

def maps_mode1():
    # Full (ocam mode 1)

    # Generate the ordering in FG space

    # Numbered array of all the pixels PER AMPLIFIER
    arange = np.arange(121*66, dtype=np.int32)
    # Gen the global numbering for all 8 amplifiers
    amps = [8 * arange.reshape(121,66) + i for i in range(8)]

    # Crop the prescans: first line, six first pixels
    amps = [a[1:,6:] for a in amps]

    # Gen the sensor map with readout order - this is the reverse map
    sensor = np.r_[np.c_[amps[0][:,::-1], amps[1],
                        amps[2][:,::-1], amps[3]],
                np.c_[amps[7][:,::-1], amps[6],
                        amps[5][:,::-1], amps[4]][::-1]
                ]
    pf.writeto('ocam2kpixi_1_REV.fits', sensor, overwrite=True)

    # Check
    print("240x240?", sensor.shape)

    # Invert the map
    buff = np.zeros((121*528), dtype=np.int32)
    for k,v in enumerate(sensor.flatten()):
        buff[v] = k
    buff = buff.reshape(121, 528)

    pf.writeto('ocam2kpixi_1.fits', buff, overwrite=True)

    return sensor, buff

def maps_mode3():
    # Binned (ocam mode 3)

    arange = np.arange(62*66, dtype=np.int32)
    amps = [8 * arange.reshape(62,66) + i for i in range(8)]

    # Crop the prescans
    amps = [a[1:-1,6:] for a in amps]
    # Remove the duplicate readouts
    amps = [a[:,::2] for a in amps]

    # Gen the sensor map with readout order
    sensor = np.r_[np.c_[amps[0][:,::-1], amps[1],
                        amps[2][:,::-1], amps[3]],
                np.c_[amps[7][:,::-1], amps[6],
                        amps[5][:,::-1], amps[4]][::-1]
                ]
    print("120x120?", sensor.shape)

    pf.writeto('ocam2kpixi_3_REV.fits', sensor, overwrite=True)

    buff = np.zeros((62*528), dtype=np.int32)
    for k,v in enumerate(sensor.flatten()):
        buff[v] = k
    buff = buff.reshape(62, 528)

    pf.writeto('ocam2kpixi_3.fits', buff, overwrite=True)

    return sensor, buff

if __name__ == "__main__":
    r1, f1 = maps_mode1()
    r3, f3 = maps_mode3()

