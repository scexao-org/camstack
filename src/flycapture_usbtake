#!/usr/bin/env python
'''
    spinnaker USB3 camera framegrabber

    Usage:
        spinnaker_usbtake [options]

    Options:
        -s <stream_name> SHM name
        -u <unit>        Number (index/serial) of the camera for the Spinnaker API [default: 0]
        -l <loops>       Number of images to take (0 for free run) [default: 0]
        -R               Attempt SHM reuse if possible
'''
'''
    NOTE: SERIALS
    Vampires pupil Flea3:         13380425
    FIRST pupil Flea3:            14317519
    Coro spy camera Grasshopper3: 17266134
'''

import PyCapture2 as PC2
import numpy as np
from pyMilk.interfacing.shm import SHM

import time


def nparray_from_flyimage(fly_image):
    shape_rows, shape_cols = fly_image.getRows(), fly_image.getCols()
    if fly_image.getPixelFormat() == PC2.PIXEL_FORMAT.MONO12:
        fly_image = fly_image.convert(PC2.PIXEL_FORMAT.MONO16)

    data_raw_arr = fly_image.getData()

    # Cast the array buffer
    if fly_image.getPixelFormat() == PC2.PIXEL_FORMAT.MONO16:
        data_raw_arr.dtype = np.uint16

    return data_raw_arr.reshape(shape_rows, shape_cols)


def main_acquire_flycapture(api_cam_num_or_serial: int, stream_name: str,
                            n_loops: int, attempt_shm_reuse: bool = True):

    fly_bus = None
    fly_cam = None
    fly_image = None

    try:  # Except Keyboard Interrupt or any error

        fly_bus = PC2.BusManager()
        num_cams = fly_bus.getNumOfCameras()
        fly_serials = [
                fly_bus.getCameraSerialNumberFromIndex(ii)
                for ii in range(num_cams)
        ]

        fly_cam = PC2.Camera()

        if api_cam_num_or_serial < num_cams:  # It's an index number
            uid = fly_bus.getCameraFromIndex(api_cam_num_or_serial)
        else:  # It's a serial
            uid = fly_bus.getCameraFromSerialNumber(api_cam_num_or_serial)

        fly_cam.connect(uid)
        fly_cam.setConfiguration(numBuffers=10,
                                 grabMode=PC2.GRAB_MODE.DROP_FRAMES,
                                 grabTimeout=5000)

        fly_cam.startCapture()

        # Get a test image!
        fly_image = fly_cam.retrieveBuffer()

        data_arr = nparray_from_flyimage(fly_image)

        try:
            shm = SHM(stream_name)
            shm.set_data(data_arr)
        except:
            shm = SHM(stream_name, data_arr, nbkw=50)

        shm.set_keywords({
                'MFRATE': (0.0, "Measured frame rate (Hz)"),
                '_MAQTIME': (int(time.time() * 1e6),
                             "Frame acq time (us, CLOCK_REALTIME)"),
                '_FGSIZE1': (data_arr.shape[1],
                             "Size of frame grabber for the X axis (pixel)"),
                '_FGSIZE2': (data_arr.shape[0],
                             "Size of frame grabber for the Y axis (pixel)"),
        })

        n_img = 0
        time_1 = time.time()
        mfrate = 0.0
        mfrate_gain = 0.01

        while True:
            fly_image = fly_cam.retrieveBuffer()

            data_arr = nparray_from_flyimage(fly_image)

            fly_image = None

            time_2 = time.time()
            dt = time_2 - time_1
            mfrate = (1 - mfrate_gain) * mfrate + 1 / dt * mfrate_gain
            shm.update_keyword('MFRATE', mfrate)
            shm.update_keyword('_MAQTIME', int(time_2 * 1e6))
            time_1 = time_2

            shm.set_data(data_arr)

            n_img += 1
            if n_img == n_loops:  # won't happen if n_loops = 0, which is intended.
                break

    except Exception as ex:
        print('Error 0: %s' % ex)
    finally:
        # Graceful cleanup?
        # How much do we have to clean?
        try:
            if fly_cam is not None and fly_cam.isConnected:
                fly_cam.disconnect()
                del fly_cam
        except PC2.Fc2error as ex:
            print('Error C: %s' % ex)
        print('\nGraceful cleanup successful. Maybe.\n')


if __name__ == "__main__":
    import docopt

    args = docopt.docopt(__doc__)

    arg_cam_number = int(args["-u"])
    if args["-s"] is None:
        arg_stream_name = f'flycam_{arg_cam_number}'
    else:
        arg_stream_name = args["-s"]

    arg_n_loops = int(args["-l"])

    arg_attempt_reuse = args["-R"]

    main_acquire_flycapture(arg_cam_number, arg_stream_name, arg_n_loops,
                            arg_attempt_reuse)
