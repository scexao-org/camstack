import os

from typing import Union, Tuple, List, Any

from camstack.cams.base import BaseCamera
#from camstack.core import dcamprop
from camstack.core.utilities import CameraMode

from pyMilk.interfacing.shm import SHM
import numpy as np

import PySpin


class SpinnakerUSBCamera(BaseCamera):

    INTERACTIVE_SHELL_METHODS = [] + \
        BaseCamera.INTERACTIVE_SHELL_METHODS

    MODES = {}

    KEYWORDS = {}
    KEYWORDS.update(BaseCamera.KEYWORDS)

    def __init__(self,
                 name: str,
                 stream_name: str,
                 mode_id: Union[CameraMode, Tuple[int, int]],
                 spinnaker_number: int,
                 no_start: bool = False,
                 taker_cset_prio: Union[str, int] = ('system', None),
                 dependent_processes: List[Any] = []):

        # Do basic stuff
        self.spinn_number = spinnaker_number
        # Initialized in init_framegrab_backend
        self.spinn_system = None
        self.spinn_cam = None

        BaseCamera.__init__(self,
                            name,
                            stream_name,
                            mode_id,
                            no_start=no_start,
                            taker_cset_prio=taker_cset_prio,
                            dependent_processes=dependent_processes)

        # The int values of the enumerations took a little digging...
        # This is best achieved by
        # 1/ Looking into SpinViewQt for what works for your camera
        # 2/ calling e.g. [l.GetName() for l in spinn_cam.PixelFormat.GetEntries()]

        # Disable LED
        self.spinn_cam.DeviceIndicatorMode.SetValue(0)
        # Always max speed given exposure time
        self.spinn_cam.AcquisitionFrameRateEnable.SetValue(False)
        # Disable autoexp
        self.spinn_cam.ExposureAuto.SetValue(0)
        # Disable autogain
        self.spinn_cam.GainAuto.SetValue(0)
        # Disable gamma
        self.spinn_cam.GammaEnable.SetValue(False)
        

    def init_framegrab_backend(self):

        if self.is_taker_running():
            raise AssertionError('Cannot change camera config while camera is running')

        if self.spinn_system is None:
            self.spinn_system = PySpin.System.GetInstance()
        
        if self.spinn_cam is None:
            cam_list = self.spinn_system.GetCameras()
            self.spinn_cam = cam_list[self.spinn_number]
            cam_list.Clear()

            self.spinn_cam.Init()

        # Continuous acquisition
        self.spinn_cam.AcquisitionMode.SetValue(0)

    def prepare_camera_for_size(self, mode_id=None):

        BaseCamera.prepare_camera_for_size(self)

        x0, x1 = self.current_mode.x0, self.current_mode.x1
        y0, y1 = self.current_mode.y0, self.current_mode.y1

        # Reset offsets
        self.spinn_cam.OffsetX.SetValue(0)
        self.spinn_cam.OffsetY.SetValue(0)

        # Bin
        self.spinn_cam.BinningHorizontal.SetValue(self.current_mode.biny)
        self.spinn_cam.BinningVertical.SetValue(self.current_mode.binx)

        # h, w
        self.spinn_cam.Width.SetValue(x1-x0+1)
        self.spinn_cam.Height.SetValue(y1-y0+1)

        # offsets
        self.spinn_cam.OffsetX.SetValue(x0)
        self.spinn_cam.OffsetY.SetValue(y0)

        # Set ADC to 12 bit
        self.spinn_cam.AdcBitDepth.SetValue(2)
        # Set pixel format to Mono12p
        self.spinn_cam.PixelFormat.SetValue(29)

    def prepare_camera_finalize(self, mode_id=None):
        # Only the stuff that is mode dependent
        # And/or should be called after each mode change.
        # And is camera specific
        pass


    def release(self):
        BaseCamera.release(self)

        cam.DeInit()
        del self.spinn_cam
        self.spinn_system.ReleaseInstance()


    def _prepare_backend_cmdline(self, reuse_shm: bool = False):

        # Prepare the cmdline for starting up!
        exec_path = os.environ['HOME'] + '/src/camstack/src/spinnaker_usbtake'
        self.taker_tmux_command = (f'{exec_path} -s {self.STREAMNAME} '
                                   f'-u {self.spinn_number} -l 0')
        if reuse_shm:
            self.taker_tmux_command += ' -R'  # Do not overwrite the SHM.

    def _ensure_backend_restarted(self):
        # Plenty simple enough for spinnaker
        time.sleep(1.0)

    def _fill_keywords(self):
        
        BaseCamera._fill_keywords(self)

        self.get_fps()
        self.get_tint()
        self.get_gain()

        self.camera_shm.update_keyword('DETECTOR', 'FLIR Spinnaker')

        self.poll_camera_for_keywords()

    def poll_camera_for_keywords(self):
        self.get_temperature()

    def get_fps(self):
        fps = self.spinn_cam.AcquisitionResultingFrameRate()
        self.camera_shm.update_keyword('FRATE', fps)
        return fps

    def set_fps(self, fps: float):
        self.spinn_cam.AcquisitionResultingFrameRate.SetValue(fps)
        return self.get_fps()
    
    def get_tint(self):
        tint = self.spinn_cam.ExposureTime()
        self.camera_shm.update_keyword('EXPTIME', tint)
        return tint

    def set_tint(self, tint: float):
        self.spinn_cam.ExposureTime.SetValue(tint)
        return self.get_tint()

    def get_gain(self):
        gain = self.spinn_cam.Gain()
        self.camera_shm.update_keyword('DETGAIN', gain)
        return gain

    def set_gain(self, gain: float):
        self.spinn_cam.Gain.SetValue(gain)
        return self.get_gain()

    def get_temperature(self):
        temp = self.spinn_cam.DeviceTemperature()
        self.camera_shm.update_keyword('DET-TMP', temp + 273.15)
        return temp





class BlackFly(SpinnakerUSBCamera):

    INTERACTIVE_SHELL_METHODS = BaseCamera.INTERACTIVE_SHELL_METHODS

    FULL = 'FULL'
    
    MODES = {
        FULL: CameraMode(x0=0, x1=2047, y0=0, y1=1535, tint=0.001),
        # Centercrop half-size
        1: CameraMode(x0=512, x1=1535, y0=384, y1=1151, tint=0.001),
        # Full bin 2
        #2: CameraMode(x0=)
    }

    KEYWORDS = {}
    KEYWORDS.update(SpinnakerUSBCamera.KEYWORDS)

    def __init__(self,
                 name: str,
                 stream_name: str,
                 mode_id: Union[CameraMode, Tuple[int, int]],
                 spinnaker_number: int,
                 no_start: bool = False,
                 taker_cset_prio: Union[str, int] = ('system', None),
                 dependent_processes: List[Any] = []):

        SpinnakerUSBCamera.__init__(self,
                               name,
                               stream_name,
                               mode_id,
                               spinnaker_number,
                               no_start=no_start,
                               taker_cset_prio=taker_cset_prio,
                               dependent_processes=dependent_processes)

    
    def _fill_keywords(self):

        SpinnakerUSBCamera._fill_keywords(self)
        self.camera_shm.update_keyword('CROPPED',
                                       self.current_mode_id != self.FULL)
        self.camera_shm.update_keyword('DETECTOR', 'BlackFly S')

    def prepare_camera_for_size(self, mode_id=None):
        # Something that we feel is BlackFly specific but not Spinnaker generic
        SpinnakerUSBCamera.prepare_camera_for_size(self, mode_id)


    def prepare_camera_finalize(self, mode_id=None):
        # Something that we feel is BlackFly specific but not Spinnaker generic
        SpinnakerUSBCamera.prepare_camera_finalize(self, mode_id)
