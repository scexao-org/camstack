'''
    THIS FILE DEVELOPMENT IS ABANDONED AFTER REALIZED CAMERAS
    WE HAVE CAN BE CONTROLLED WITH THE MOST RECENT SPINNAKER.

    THIS FILE IS A COPY OF THE SPINNAKER FILE
    WITH PARTIAL CONVERSION TO FLYCAPTURE ALREADY DONE.
'''

import os

from typing import Union, Tuple, List, Any

from camstack.cams.base import BaseCamera
#from camstack.core import dcamprop
from camstack.core.utilities import CameraMode

from pyMilk.interfacing.shm import SHM
import numpy as np

import PyCapture2
from PyCapture2 import PIXEL_FORMAT, PROPERTY_TYPE as PROPS


class FlyCaptureUSBCamera(BaseCamera):

    INTERACTIVE_SHELL_METHODS = [] + \
        BaseCamera.INTERACTIVE_SHELL_METHODS

    MODES = {}

    KEYWORDS = {}
    KEYWORDS.update(BaseCamera.KEYWORDS)

    def __init__(self, name: str, stream_name: str, mode_id: Union[CameraMode,
                                                                   Tuple[int,
                                                                         int]],
                 flycap_number: int, no_start: bool = False,
                 taker_cset_prio: Union[str, int] = ('system', None),
                 dependent_processes: List[Any] = []):

        # Do basic stuff
        self.fly_number = flycap_number  # Serial is allowed
        # Initialized in init_framegrab_backend
        self.fly_bus = None
        self.fly_cam = None

        BaseCamera.__init__(self, name, stream_name, mode_id,
                            no_start=no_start, taker_cset_prio=taker_cset_prio,
                            dependent_processes=dependent_processes)

        # The int values of the enumerations took a little digging...
        # This is best achieved by
        # 1/ Looking into SpinViewQt for what works for your camera
        # 2/ calling e.g. [l.GetName() for l in spinn_cam.PixelFormat.GetEntries()]

        # TODO # TODO # TODO # TODO # TODO # TODO # TODO # TODO # TODO
        # Disable LED
        self.spinn_cam.DeviceIndicatorMode.SetValue(0)
        # Always max speed given exposure time
        self.spinn_cam.AcquisitionFrameRateEnable.SetValue(False)
        # Disable autoexp
        self.spinn_cam.ExposureAuto.SetValue(0)
        # Disable autogain, set gain to max
        self.fly_cam.setProperty(type=PROPS.GAIN, absValue=30.0,
                                 autoManualMode=False)
        # Disable gamma
        self.fly_cam.setProperty(type=PROPS.GAMMA, absValue=1.0,
                                 autoManualMode=False)
        # TODO END TODO FINALIZERS

    def init_framegrab_backend(self):
        # TODO # TODO
        if self.is_taker_running():
            raise AssertionError(
                    'Cannot change camera config while camera is running')

        if self.fly_bus is None:
            self.fly_bus = PyCapture2.BusManager()

        if self.fly_cam is None:
            num_cams = fly_bus.getNumOfCameras()
            fly_serials = [
                    self.fly_bus.getCameraSerialNumberFromIndex(ii)
                    for ii in range(num_cams)
            ]

            if api_cam_num_or_serial < num_cams:  # It's an index number
                uid = fly_bus.getCameraFromIndex(api_cam_num_or_serial)
            else:  # It's a serial
                uid = fly_bus.getCameraFromSerialNumber(api_cam_num_or_serial)

            self.fly_cam = PyCapture2.Camera()
            self.fly_cam.connect(uid)

        self.fly_cam.setConfiguration(
                numBuffers=10, grabMode=PyCapture2.GRAB_MODE.DROP_FRAMES,
                grabTimeout=1000)

    def prepare_camera_for_size(self, mode_id=None):
        BaseCamera.prepare_camera_for_size(self)

        x0, x1 = self.current_mode.x0, self.current_mode.x1
        y0, y1 = self.current_mode.y0, self.current_mode.y1

        # Set ADC to 12 bit
        self.spinn_cam.AdcBitDepth.SetValue(2)
        # Set pixel format to Mono12p
        self.spinn_cam.PixelFormat.SetValue(29)

        # Reset offsets
        self.spinn_cam.OffsetX.SetValue(0)
        self.spinn_cam.OffsetY.SetValue(0)

        # Bin
        self.spinn_cam.BinningHorizontal.SetValue(self.current_mode.biny)
        self.spinn_cam.BinningVertical.SetValue(self.current_mode.binx)

        # h, w
        self.spinn_cam.Width.SetValue(x1 - x0 + 1)
        self.spinn_cam.Height.SetValue(y1 - y0 + 1)

        # offsets
        self.spinn_cam.OffsetX.SetValue(x0)
        self.spinn_cam.OffsetY.SetValue(y0)

    def prepare_camera_finalize(self, mode_id=None):
        # Only the stuff that is mode dependent
        # And/or should be called after each mode change.
        # And is camera specific
        pass

    def release(self):
        BaseCamera.release(self)

        self.fly_cam.disconnect()
        del self.fly_cam

    def _prepare_backend_cmdline(self, reuse_shm: bool = False):

        # Prepare the cmdline for starting up!
        exec_path = os.environ['HOME'] + '/src/camstack/src/flycapture_usbtake'
        self.taker_tmux_command = (f'{exec_path} -s {self.STREAMNAME} '
                                   f'-u {self.fly_number} -l 0')
        if reuse_shm:
            self.taker_tmux_command += ' -R'  # Do not overwrite the SHM.

    def _ensure_backend_restarted(self):
        # Plenty simple enough for flycapture
        time.sleep(3.0)

    def _fill_keywords(self):

        BaseCamera._fill_keywords(self)

        self.get_fps()
        self.get_tint()
        self.get_gain()

        self._set_formatted_keyword('DETECTOR', 'FLIR Flycapture')

        self.poll_camera_for_keywords()

    def poll_camera_for_keywords(self):
        self.get_temperature()

    def get_fps(self):
        # TODO
        fps = self.spinn_cam.AcquisitionResultingFrameRate()
        self._set_formatted_keyword('FRATE', fps)
        return fps

    def set_fps(self, fps: float):
        # TODO
        self.spinn_cam.AcquisitionResultingFrameRate.SetValue(fps)
        return self.get_fps()

    def get_tint(self):
        # TODO
        tint = self.spinn_cam.ExposureTime()
        self._set_formatted_keyword('EXPTIME', tint)
        return tint

    def set_tint(self, tint: float):
        # TODO
        self.spinn_cam.ExposureTime.SetValue(tint)
        return self.get_tint()

    def get_gain(self):
        # TODO
        gain = self.fly_cam.getProperty(PROPS.GAIN).absValue
        self._set_formatted_keyword('DETGAIN', gain)
        return gain

    def set_gain(self, gain: float):
        # TODO
        self.fly_cam.setProperty(type=PROPS.GAIN, absValue=gain)
        return self.get_gain()

    def get_temperature(self):
        # FIXME it says consistently 3.1916. I think it's lying.
        temp = self.fly_cam.getProperty(PROPS.TEMPERATURE).absValue
        self._set_formatted_keyword('DET-TMP', temp + 273.15)
        return temp


class Grasshopper3(FlyCaptureUSBCamera):

    INTERACTIVE_SHELL_METHODS = SpinnakerUSBCamera.INTERACTIVE_SHELL_METHODS

    FULL = 'FULL'

    MODES = {
            FULL: CameraMode(x0=0, x1=1919, y0=0, y1=1199),
            # Centercrop half-size
            1: CameraMode(x0=480, x1=1439, y0=300, y1=899),
            # Full bin 2
            #2: CameraMode(x0=)
    }

    KEYWORDS = {}
    KEYWORDS.update(SpinnakerUSBCamera.KEYWORDS)

    def _fill_keywords(self):

        FlyCaptureUSBCamera._fill_keywords(self)
        self._set_formatted_keyword('CROPPED',
                                    self.current_mode_id != self.FULL)
        self._set_formatted_keyword('DETECTOR', 'FLIR Grasshopper3')

    def prepare_camera_for_size(self, mode_id=None):
        # Something that we feel is Grasshopper3 specific but not FlyCapture generic
        FlyCaptureUSBCamera.prepare_camera_for_size(self, mode_id)

    def prepare_camera_finalize(self, mode_id=None):
        # Something that we feel is Grasshopper3 specific but not FlyCapture generic
        FlyCaptureUSBCamera.prepare_camera_finalize(self, mode_id)
