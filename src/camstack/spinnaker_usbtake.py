#!/usr/bin/env python
'''
    spinnaker USB3 camera framegrabber

    Usage:
        spinnaker_usbtake [options]

    Options:
        -s <stream_name> SHM name
        -u <unit>        Number of the camera for the Spinnaker API [default: 0]
        -l <loops>       Number of images to take (0 for free run) [default: 0]
        -R               Attempt SHM reuse if possible
'''

import PySpin
from pyMilk.interfacing.shm import SHM

import time


def main_acquire_spinnaker(api_cam_num: int, stream_name: str, n_loops: int,
                           attempt_shm_reuse: bool = True):

    spinn_system = None
    spinn_cam = None
    spinn_image = None

    #if True:
    try:  # Except Keyboard Interrupt or any error

        spinn_system = PySpin.System.GetInstance()
        cam_list = spinn_system.GetCameras()
        spinn_cam = cam_list[api_cam_num]
        cam_list.Clear()

        spinn_cam.Init()

        spinn_cam.BeginAcquisition()
        spinn_image = spinn_cam.GetNextImage(1000)  # 1 sec timeout

        print('OK')
        # We need to convert - not native 8 or 16 ! 10 or 12 bit packed probs.
        # So we convert to Mono16.
        need_convert_16 = spinn_image.GetBitsPerPixel() not in [8, 16]

        if need_convert_16:
            conv_image = spinn_image.Convert(PySpin.PixelFormat_Mono16,
                                             PySpin.HQ_LINEAR)
        else:
            conv_image = spinn_image

        data_arr = conv_image.GetNDArray()
        spinn_image.Release()

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

            try:
                spinn_image = spinn_cam.GetNextImage(1000)  # 1 sec timeout
            except PySpin.SpinnakerException:
                print('GetNextImage timeout.')
                continue

            if spinn_image.IsIncomplete():
                print('Image incomplete - status %d ...' %
                      spinn_image.GetImageStatus())
                continue

            if need_convert_16:
                conv_image = spinn_image.Convert(PySpin.PixelFormat_Mono16,
                                                 PySpin.HQ_LINEAR)
            else:
                conv_image = spinn_image

            data_arr = conv_image.GetNDArray()

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
    except KeyboardInterrupt:
        print('Keyboard interrupt!')
    finally:
        # Graceful cleanup?
        # How much do we have to clean?
        # Spinnaker seems **very** resilient to botched pkills, so not to worry too much
        try:
            if spinn_image is not None:
                spinn_image.Release()
        except PySpin.SpinnakerException as ex:
            print('Error A: %s' % ex)
        try:
            if spinn_cam is not None:
                spinn_cam.EndAcquisition()
        except PySpin.SpinnakerException as ex:
            print('Error B: %s' % ex)
        try:
            if spinn_cam is not None:
                spinn_cam.DeInit()
                del spinn_cam
        except PySpin.SpinnakerException as ex:
            print('Error C: %s' % ex)
        try:
            if spinn_system is not None:
                spinn_system.ReleaseInstance()
        except PySpin.SpinnakerException as ex:
            print('Error D: %s' % ex)

def main():
    import docopt

    args = docopt.docopt(__doc__)

    arg_cam_number = int(args["-u"])
    if args["-s"] is None:
        arg_stream_name = f'spinncam_{arg_cam_number}'
    else:
        arg_stream_name = args["-s"]

    arg_n_loops = int(args["-l"])

    arg_attempt_reuse = args["-R"]

    main_acquire_spinnaker(arg_cam_number, arg_stream_name, arg_n_loops,
                           arg_attempt_reuse)

if __name__ == "__main__":
    main()
