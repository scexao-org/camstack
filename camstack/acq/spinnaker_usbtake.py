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
        -B               List cameras
'''
from __future__ import annotations

# Consider running this directly in mamba
# mamba run -n py38 python -m camstack.acq.spinnaker_usbtake [options]

import PySpin
from pyMilk.interfacing.shm import SHM
import numpy as np

import time


def try_eth_info(cam) -> str:
    try:
        i = cam.GevCurrentIPAddress()
        m = cam.GevCurrentSubnetMask()
        return f'[IP: {i >> 24 & 0xFF}.{i >> 16 & 0xFF}.{i >> 8 & 0xFF}.{i & 0xFF} - Mask: {m >> 24 & 0xFF}.{m >> 16 & 0xFF}.{m >> 8 & 0xFF}.{m & 0xFF}]'
    except:
        return '[No ethernet info]'


def try_family_name(cam) -> str:
    try:
        return f'[{cam.DeviceFamilyName()}] '  # GEV cam weird about that one ?
    except:
        return '[No FamilyName info]'


PRETTY_PRINT_PROPS = [
        'WidthMax', 'HeightMax', 'BinningHorizontal', 'BinningVertical',
        'AcquisitionFrameRate', 'ExposureTime', 'ExposureAuto', 'Gain',
        'GainAuto', 'Width', 'Height', 'OffsetX', 'OffsetY',
        'TriggerActivation', 'TriggerDelay', 'TriggerMode', 'TriggerSource',
        'TriggerSelector'
]
BOOL_PROPS = []


def try_infostring_value(prop: str, p) -> str | None:
    try:
        return f'{prop:<25} {p.GetValue():<20} [{p.GetUnit():<2}]   ({p.GetMin()} -- {p.GetMax()})'
    except:
        return None


def try_infostring_enum(prop: str, p) -> str | None:
    try:
        return f'{prop:<25} {p.GetEntry(p.GetValue()).GetName()}'
    except:
        return None


def try_infostring_bool(prop: str, p) -> str | None:
    try:
        tag = ('ON', 'OFF')[p.GetValue()]
        return f'{prop:<25} {tag}'
    except:
        return None


def print_camera_info(cam) -> list[str]:
    cam_info = [cam.DeviceVendorName() + ' ' + cam.DeviceModelName() + \
                    ' ' + try_family_name(cam) + ' ' + try_eth_info(cam) + \
                    f' [ID={cam.DeviceID()}]']
    for prop in PRETTY_PRINT_PROPS:
        try:
            p = getattr(cam, prop)
            s = try_infostring_value(prop, p)
            if s is not None:
                cam_info += [s]
                continue
            s = try_infostring_enum(prop, p)
            if s is not None:
                cam_info += [s]
                continue
            s = try_infostring_bool(prop, p)
            if s is not None:
                cam_info += [s]
                continue
            cam_info += [f'{prop:<25} [Error during getvalue]']
        except:
            cam_info += [f'{prop:<25} [Error during getattr]']
    return cam_info


def main_camera_info():
    spinn_system = None
    spinn_cam = None

    try:
        spinn_system = PySpin.System.GetInstance()
        cam_list = spinn_system.GetCameras()

        for kk in range(len(cam_list)):
            spinn_cam = cam_list[kk]
            serial = 'error S/N'
            try:
                serial = spinn_cam.GetDeviceSerialNumber()
                spinn_cam.Init()
                info = print_camera_info(spinn_cam)
                print(f'--------- CAMERA {kk} [{serial}] ----------')
                print('\n'.join(info))
            except Exception as exc:
                print(f'ERROR---- CAMERA {kk} [{serial}] -------XXX')
                print(f'{repr(exc)}')
                print('(Reset the USB cameras? (~/reset_pg1.sh)')
            finally:
                spinn_cam.DeInit()
                spinn_cam = None

    finally:
        try:
            cam_list.Clear()
        except Exception as exc:
            print('Error: %s' % exc)
        try:
            if spinn_system is not None:
                spinn_system.ReleaseInstance()
        except PySpin.SpinnakerException as ex:
            print('Error: %s' % ex)


def main_acquire_spinnaker(api_cam_num: int, stream_name: str, n_loops: int,
                           attempt_shm_reuse: bool = True) -> None:

    spinn_system = None
    spinn_cam = None
    spinn_image = None

    #if True:
    try:  # Except Keyboard Interrupt or any error

        spinn_system = PySpin.System.GetInstance()
        cam_list = spinn_system.GetCameras()
        if api_cam_num < len(cam_list):  # Index
            spinn_cam = cam_list[api_cam_num]
            spinn_cam.Init()
        else:
            # With GigE cams, the same serial may appear multiple times!
            # Cam is detected correctly on one IP, and poorly on other subnet IPs
            _serials_to_index: dict[int, list[int]] = {}
            for kk, c in enumerate(cam_list):
                sn = int(c.GetDeviceSerialNumber())
                if sn not in _serials_to_index:
                    _serials_to_index[sn] = []
                _serials_to_index[sn] += [kk]

            for cam_idx in _serials_to_index[api_cam_num]:
                cam = cam_list[cam_idx]
                try:
                    cam.Init()
                    spinn_cam = cam
                    break
                except PySpin.SpinnakerException as exc:
                    cam = None
                    pass
            else:  # for-else statement only if loop as completed without finding ok serial.
                raise exc

        cam_list.Clear()

        spinn_cam.BeginAcquisition()

        initializing = True
    
        n_img = 0
        time_1 = time.time()
        mfrate = 0.0
        mfrate_gain = 0.01

        width, heigth = spinn_cam.Width(), spinn_cam.Height()
        fmt = spinn_cam.PixelFormat.GetEntry(spinn_cam.PixelFormat()).GetName()
        need_conversion_to_16bit = not ('Mono8' in fmt or 'Mono16' in fmt)
        processor = PySpin.ImageProcessor()

        dtype = np.uint8 if 'Mono8' in fmt else np.uint16

        try:
            shm = SHM(stream_name)
            shm.set_data(np.zeros((width, heigth), dtype))
        except:
            shm = SHM(stream_name, np.zeros((width, heigth), dtype), nbkw=50)

        shm.set_keywords({
                'MFRATE': (0.0, "Measured frame rate (Hz)"),
                '_MAQTIME': (int(time.time() * 1e6),
                            "Frame acq time (us, CLOCK_REALTIME)"),
                '_FGSIZE1': (width,
                            "Size of frame grabber for the X axis (pixel)"),
                '_FGSIZE2': (heigth,
                            "Size of frame grabber for the Y axis (pixel)"),
        })
    

        while True:
            try:
                spinn_image = spinn_cam.GetNextImage(1000)  # 1 sec timeout
            except PySpin.SpinnakerException as exc:
                print(f'GetNextImage timeout: {repr(exc)}')
                continue

            if spinn_image.IsIncomplete():
                print('Image incomplete - status %d ...' %
                      spinn_image.GetImageStatus())
                continue

            # We need to convert - not native 8 or 16 ! 10 or 12 bit packed probs.
            # So we convert to Mono16.
            if need_conversion_to_16bit:
                conv_image = processor.Convert(spinn_image,
                                               PySpin.PixelFormat_Mono16)
            else:
                conv_image = spinn_image

            data_arr = conv_image.GetNDArray()

            spinn_image.Release()
            if need_conversion_to_16bit:
                conv_image.Release()

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
        print(f'Error 0: {repr(ex)}')
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

    enumerate_info = args['-B']

    if enumerate_info:
        main_camera_info()
    else:
        main_acquire_spinnaker(arg_cam_number, arg_stream_name, arg_n_loops,
                               arg_attempt_reuse)


if __name__ == "__main__":
    main()
