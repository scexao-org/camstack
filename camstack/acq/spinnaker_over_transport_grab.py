#!/usr/bin/env python
'''
    Spinnaker camera framegrabber - works in conjunction with camera class
    at camstack.cams.spinnaker_over_transport.
    Validated with USB3 and GigE spinnaker cameras of BlackFly/BlackFly S family.

    Exclusive access to camera in this process.

    Communication with the control shell is done with a transport: commands-over-SHM-keywords.

    Usage:
        spinnaker_over_transport_grab [options]

    Options:
        -s <stream_name> SHM name
        -u <unit>        Number of the camera for the Spinnaker API [default: 0]
        -l <loops>       Number of images to take (0 for free run) [default: 0]
        -R               Attempt SHM reuse if possible
        -B               List cameras
'''
from __future__ import annotations
import typing as typ

# Consider running this directly in mamba
# mamba run -n py38 python -m camstack.acq.spinnaker_over_transport_grab [options]

import PySpin
from pyMilk.interfacing.shm import SHM
if typ.TYPE_CHECKING:
    from pyMilk.interfacing.shm import KWCommentDict
from camstack.scxkw import MAGIC_BOOL_STR
import numpy as np

import time

from hwmain.spinnaker import sdk
from camstack.scxkw import MAGIC_BOOL_STR


def _params_parse_and_set(spinn_cam: typ.Any, kws: KWCommentDict,
                          fatal: bool) -> KWCommentDict:
    """
    Parse the transport SHM keyword list, apply SET operations to the camera via
    the PySpin node map, and write back current (post-set) values as GET feedback.

    Encoding (matches CommandTransportForGenicam):
      keyword name  : 8-char hex, bits [7:4] = prop.unique_id, bits [3:0] = REQUEST (always 0)
      keyword value : typed placeholder  -> GET only
                      actual value       -> SET then GET
      keyword comment: feature_name, or feature_name#string_value for str setters
    """
    kws = kws.copy()
    updates: dict[str, tuple] = {
    }  # accumulated write-backs {name: (value, comment)}

    for kw_name, (value, comment) in kws.items():
        prop_string = comment.split('#')[0]
        try:
            key_int = int(kw_name, 16)
        except ValueError:
            continue
        request = sdk.REQUEST(key_int & 0x0F)

        try:
            spinn_cam_prop = getattr(spinn_cam, prop_string)
        except:
            print(f'  {prop_string}: unknown, skipping')
            continue

        print(f'  kw[{kw_name}]: prop={spinn_cam_prop.GetName()} feature={comment} val={value!r}'
              )

        ok = True
        # TODO better errors so that the return value is correct...
        # TODO consider some min-max clamping
        try:
            if request == sdk.REQUEST.GETORCALL:
                x = spinn_cam_prop()
                if x is None:
                    updates[kw_name] = ('plholder', comment)
                else:
                    updates[kw_name] = (x, comment)
                print(updates[kw_name])
            elif request == sdk.REQUEST.GETMIN:
                updates[kw_name] = (spinn_cam_prop.GetMin(), comment)
            elif request == sdk.REQUEST.GETMAX:
                updates[kw_name] = (spinn_cam_prop.GetMax(), comment)
            elif request == sdk.REQUEST.SETVALUE:
                if '#' in comment:  # strings
                    spinn_cam_prop.SetValue(comment.split('#')[1])
                    updates[kw_name] = 'plholder', prop_string + '#' + spinn_cam_prop(
                    )
                    print(
                            comment.split('#')[1],
                            updates[kw_name][1].split('#')[1])
                elif value == MAGIC_BOOL_STR.TRUE:  # bool true
                    spinn_cam_prop.SetValue(True)
                    updates[kw_name] = MAGIC_BOOL_STR.TUPLE[
                            spinn_cam_prop()], comment
                    print(True, updates[kw_name][0])
                elif value == MAGIC_BOOL_STR.FALSE:  # bool false
                    spinn_cam_prop.SetValue(False)
                    updates[kw_name] = MAGIC_BOOL_STR.TUPLE[
                            spinn_cam_prop()], comment
                    print(False, updates[kw_name][0])
                else:  # int, floats, enums
                    spinn_cam_prop.SetValue(value)
                    updates[kw_name] = spinn_cam_prop(), comment
                    print(value, updates[kw_name][0])
        except Exception as exc:
            ok = False
            msg = f'  kw[{kw_name}] feature={prop_string!r}: {exc!r}'
            if fatal:
                raise RuntimeError(msg) from exc
            else:
                print(msg)

        print(f'  -> {"OK" if ok else "FAIL"}')

    # Write back all updated values and comments in one shot
    if updates:
        kws.update(updates)
    return kws


def _has_setter(kws: KWCommentDict) -> bool:
    """
    Return True if any keyword in kw_items is a SET operation.
    """
    for kw_name in kws:
        try:
            key_int = int(kw_name, 16)
        except ValueError:
            continue

        request = sdk.REQUEST(key_int & 0x0F)
        if request == sdk.REQUEST.SETVALUE:
            return True
        # There's something to be said about commands...

        # We'll assume the only valid command is a software frame trigger.

    return False


def _contains_soft_trigger(kws: KWCommentDict) -> bool:
    id = sdk.TriggerSoftware.unique_id
    req = sdk.REQUEST.GETORCALL
    return f'{((id << 4) | req):08x}' in kws


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
            cam_list.Clear()  # type: ignore
        except Exception as exc:
            print('Error: %s' % exc)
        try:
            if spinn_system is not None:
                spinn_system.ReleaseInstance()
        except PySpin.SpinnakerException as ex:
            print('Error: %s' % ex)


def main_acquire_spinnaker(api_cam_num: int, stream_name: str, n_loops: int,
                           attempt_shm_reuse: bool = True) -> None:
    """
    Acquire frames from a PySpin (Spinnaker) camera into an ImageStreamIO SHM stream,
    with parameter control via the camstack params-SHM transport.

    Follows the layout and philosophy of andorcb2.cpp:
      - Opens the pre-existing _params_fb SHM written by the Python manager.
      - Applies initial params (twice, to handle offset-before-size ordering).
      - Signals readiness to the manager by posting the params SHM.
      - Main loop: non-blocking param check + direct GetNextImage() wait (no callback).
      - On param update: stop acq if needed, apply, restart, post 3x for manager feedback.
    """
    spinn_system = None
    spinn_cam = None
    spinn_image = None

    #if True:
    try:

        spinn_system = PySpin.System.GetInstance()
        cam_list = spinn_system.GetCameras()

        if api_cam_num < len(cam_list):  # treat as a list index
            spinn_cam = cam_list[api_cam_num]
            spinn_cam.Init()
        else:
            # Treat as a serial number. With GigE, the same serial may appear on
            # multiple IPs; try each index until one initialises successfully.
            _serials_to_index: dict[int, list[int]] = {}
            for kk, c in enumerate(cam_list):
                sn = int(c.GetDeviceSerialNumber())
                if sn not in _serials_to_index:
                    _serials_to_index[sn] = []
                _serials_to_index[sn] += [kk]

            last_exc: Exception = RuntimeError(
                    f'Serial {api_cam_num} not found')
            for cam_idx in _serials_to_index[api_cam_num]:
                cam = cam_list[cam_idx]
                try:
                    cam.Init()
                    spinn_cam = cam
                    break
                except PySpin.SpinnakerException as exc:
                    last_exc = exc
            else:  # for-else: else executes if the loop went to the end, never breaking.
                raise last_exc

        cam_list.Clear()

        # Open the parameter-feedback SHM (already created by the Python control session)
        params_shm = SHM(
                stream_name + '_params_fb',
                autoSqueeze=False)  # Since this is (1,), don't squeeze.

        # -- Apply initial params (mirrors the two params_parse_and_set calls in andorcb2.cpp).
        # Reset offsets first so any Width/Height + Offset combination is accepted
        # regardless of keyword ordering in the SHM.
        kws = params_shm.get_keywords(True)
        # Reset the ROI offsets and the binning to 1
        spinn_cam.OffsetX.SetValue(0)
        spinn_cam.OffsetY.SetValue(0)
        _params_parse_and_set(spinn_cam, kws, fatal=False)
        params_shm.reset_keywords(
                _params_parse_and_set(spinn_cam, kws, fatal=False))

        # Flush accumulated semaphore posts from init (mirrors ImageStreamIO_semflush)
        while params_shm.check_sem_trywait():
            pass

        # -- Read image dimensions after params have been applied --
        width = spinn_cam.Width.GetValue()
        height = spinn_cam.Height.GetValue()

        # -- Start acquisition and grab one frame to detect pixel depth --
        spinn_cam.BeginAcquisition()

        print('OK')

        width, heigth = spinn_cam.Width(), spinn_cam.Height()
        fmt = spinn_cam.PixelFormat.GetEntry(spinn_cam.PixelFormat()).GetName()
        need_conversion_to_16bit = not ('Mono8' in fmt or 'Mono16' in fmt)
        processor = PySpin.ImageProcessor()

        dtype = np.uint8 if 'Mono8' in fmt else np.uint16

        try:
            shm_output_data = SHM(stream_name)
            shm_output_data.set_data(np.zeros((height, width), dtype))
        except:
            shm_output_data = SHM(stream_name, np.zeros((height, width), dtype),
                                  nbkw=50)

        shm_output_data.set_keywords({
                'MFRATE': (0.0, 'Measured frame rate (Hz)'),
                '_MAQTIME': (int(time.time() * 1e6),
                             'Frame acq time (us, CLOCK_REALTIME)'),
                '_FGSIZE1':
                        (width, 'Size of frame grabber for the X axis (pixel)'),
                '_FGSIZE2': (height,
                             'Size of frame grabber for the Y axis (pixel)'),
        })

        print(f'Reading {n_loops} image(s) from Spinnaker camera {api_cam_num}, '
              f'width {width} height {height}')

        # -- Signal readiness to the Python manager
        # The manager's _ensure_backend_restarted waits for this post on params_shm.
        params_shm.set_data(params_shm.get_data())
        # Consume our own post to prevent a spurious self-trigger on the first loop.
        params_shm.check_sem_trywait()

        # -- Main acquisition loop --
        n_img = 0
        time_1 = time.time()
        mfrate = 0.0
        mfrate_gain = 0.01

        while True:
            is_software_trigger: bool = \
                    spinn_cam.TriggerMode() == sdk.TriggerModeEnum.On and \
                    spinn_cam.TriggerSource() == sdk.TriggerSourceEnum.Software
            received_soft_trigger = False

            if params_shm.check_sem_trywait():
                print('Touching the params!')
                kws = params_shm.get_keywords(True)
                # Some params (ROI, binning) require acquisition to be stopped.
                # Let's just assume all setters need it.
                needs_stop = _has_setter(kws)
                received_soft_trigger = _contains_soft_trigger(kws)

                if needs_stop:
                    spinn_cam.EndAcquisition()

                kws = _params_parse_and_set(spinn_cam, kws, fatal=False)
                params_shm.reset_keywords(kws)

                if needs_stop:
                    spinn_cam.BeginAcquisition()

                # Post 3 times so the manager's multi_recv_data(3, ...) unblocks.
                for _ in range(3):
                    params_shm.set_data(params_shm.get_data())
                # Flush our own semaphore to prevent re-triggering.
                while params_shm.check_sem_trywait():
                    pass

            # --- Acquire next frame (direct wait, 100 ms timeout) ---

            spinn_image = None
            if is_software_trigger and not received_soft_trigger:
                # a microsleep could be useful here...
                # save CPU cycles
                time.sleep(0.0001)
                continue

            try:
                spinn_image = spinn_cam.GetNextImage(100)
            except PySpin.SpinnakerException as exc:
                print(f'GetNextImage timeout: {exc!r}')
                continue

            if spinn_image.IsIncomplete():
                stat = spinn_image.GetImageStatus()
                descr = PySpin.Image.GetImageStatusDescription(stat)
                if len(descr) > 100:
                    descr = descr[:90] + '... [trunc]'
                print(f'Image incomplete - status {descr} [{stat}]')

                spinn_image.Release()
                spinn_image = None
                continue

            if need_conversion_to_16bit:
                conv_image = processor.Convert(spinn_image,
                                               PySpin.PixelFormat_Mono16)
            else:
                conv_image = spinn_image

            data_arr = conv_image.GetNDArray()
            spinn_image.Release()
            spinn_image = None
            if need_conversion_to_16bit:
                conv_image.Release()

            # --- Update timing keywords and post frame ---
            time_2 = time.time()
            dt = time_2 - time_1
            mfrate = (1 - mfrate_gain) * mfrate + mfrate_gain / dt
            shm_output_data.update_keyword('MFRATE', mfrate)
            shm_output_data.update_keyword('_MAQTIME', int(time_2 * 1e6))
            time_1 = time_2

            shm_output_data.set_data(data_arr)

            n_img += 1
            if n_img == n_loops:  # won't happen if n_loops == 0, which is intended.
                break

    except KeyboardInterrupt:
        print('Keyboard interrupt!')
    except Exception as ex:
        print(f'Error 0: {ex!r}')
    finally:
        # Spinnaker is resilient to botched pkills but we clean up anyway.
        try:
            if spinn_image is not None:
                spinn_image.Release()
        except PySpin.SpinnakerException as ex:
            print(f'Error A: {ex!r}')
        try:
            if spinn_cam is not None:
                spinn_cam.EndAcquisition()
        except PySpin.SpinnakerException as ex:
            print(f'Error B: {ex!r}')
        try:
            if spinn_cam is not None:
                spinn_cam.DeInit()
                del spinn_cam
        except PySpin.SpinnakerException as ex:
            print(f'Error C: {ex!r}')
        try:
            if spinn_system is not None:
                spinn_system.ReleaseInstance()
        except PySpin.SpinnakerException as ex:
            print(f'Error D: {ex!r}')


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
