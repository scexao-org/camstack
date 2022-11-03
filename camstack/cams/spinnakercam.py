import os
import time

from typing import Union, Tuple, List, Any

from camstack.cams.base import BaseCamera
from camstack.core.utilities import CameraMode

from pyMilk.interfacing.shm import SHM
import numpy as np

import PySpin
'''
#Test block for shell:
import PySpin
spinn_system = PySpin.System.GetInstance()
cam_list = spinn_system.GetCameras()
spinn_number = 0
spinn_cam = cam_list[spinn_number]
cam_list.Clear()
spinn_cam.Init()
spinn_cam.AcquisitionMode.SetValue(PySpin.AcquisitionMode_Continuous)
'''


class SpinnakerUSBCamera(BaseCamera):

    INTERACTIVE_SHELL_METHODS = [] + \
        BaseCamera.INTERACTIVE_SHELL_METHODS

    MODES = {}

    KEYWORDS = {}
    KEYWORDS.update(BaseCamera.KEYWORDS)

    def __init__(self, name: str, stream_name: str, mode_id: Union[CameraMode,
                                                                   Tuple[int,
                                                                         int]],
                 spinnaker_number: int, no_start: bool = False,
                 taker_cset_prio: Union[str, int] = ('system', None),
                 dependent_processes: List[Any] = []):

        # Do basic stuff
        self.spinn_number = spinnaker_number
        # Initialized in init_framegrab_backend
        self.spinn_system = None
        self.spinn_cam = None

        BaseCamera.__init__(self, name, stream_name, mode_id,
                            no_start=no_start, taker_cset_prio=taker_cset_prio,
                            dependent_processes=dependent_processes)

        # The int values of the enumerations took a little digging...
        # This is best achieved by
        # 1/ Looking into SpinViewQt for what works for your camera
        # 2/ calling e.g. [l.GetName() for l in spinn_cam.PixelFormat.GetEntries()]

        # We're gonna have a divergence here between the first U3 generation cameras
        # and the Blackfly S...


    def init_framegrab_backend(self):
        logg.debug('init_framegrab_backend @ SpinnakerUSBCamera')

        if self.is_taker_running():
            msg = 'Cannot change camera config while camera is running'
            logg.error(msg)
            raise AssertionError()

        if self.spinn_system is None:
            self.spinn_system = PySpin.System.GetInstance()

        if self.spinn_cam is None:
            cam_list = self.spinn_system.GetCameras()
            self.spinn_cam = cam_list[self.spinn_number]
            cam_list.Clear()

            self.spinn_cam.Init()

        # Continuous acquisition
        self.spinn_cam.AcquisitionMode.SetValue(
                PySpin.AcquisitionMode_Continuous)

        self._spinnaker_subtypes_constructor_finalizer()

    def prepare_camera_for_size(self, mode_id=None):
        logg.debug('prepare_camera_for_size @ SpinnakerUSBCamera')

        BaseCamera.prepare_camera_for_size(self)

        # Here too we gonna have a divergence here between the first U3 generation cameras
        # and the Blackfly S...
        # Blackfly is OK with cam.BinningHorizontal.SetValue
        # U3s (Flea, Grasshopper) want "format7" stuff

        # So we must subclass... again.
        pass

    def prepare_camera_finalize(self, mode_id=None):
        # Only the stuff that is mode dependent
        # And/or should be called after each mode change.
        # And is camera-genre specific
        
        logg.debug('prepare_camera_finalize @ SpinnakerUSBCamera')

        # Set fps max
        max_fps = self.spinn_cam.AcquisitionFrameRate.GetMax()
        self.set_fps(max_fps)
        # Expo max
        max_expo_this_fps = min(self.spinn_cam.ExposureTime.GetMax() * 1e-6, 1 / max_fps)
        self.set_tint(max_expo_this_fps)

        # Lower fps, tint if necessary
        if self.current_mode.tint is not None:
            self.set_tint(self.current_mode.tint)

        if self.current_mode.fps is not None:
            self.set_fps(self.current_mode.fps)

    def release(self):
        BaseCamera.release(self)

        logg.info('spinn_cam.DeInit()')
        self.spinn_cam.DeInit()
        del self.spinn_cam
        logg.info('spinn_system.ReleaseInstance()')
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
        # But it IS slow...
        time.sleep(5.0)

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
        try:
            fps = self.spinn_cam.AcquisitionResultingFrameRate()
        except:
            fps = self.spinn_cam.AcquisitionFrameRate()
        self.camera_shm.update_keyword('FRATE', fps)
        logg.info(f'get_fps: {fps}')
        return fps

    def set_fps(self, fps: float):
        try:
            self.spinn_cam.AcquisitionResultingFrameRate.SetValue(fps)
        except:
            self.spinn_cam.AcquisitionFrameRate.SetValue(fps)
        return self.get_fps()

    def get_tint(self):
        tint = self.spinn_cam.ExposureTime() * 1e-6
        self.camera_shm.update_keyword('EXPTIME', tint)
        logg.info(f'get_tint: {tint}')
        return tint

    def set_tint(self, tint: float):
        self.spinn_cam.ExposureTime.SetValue(tint * 1e6)
        return self.get_tint()

    def get_gain(self):
        gain = self.spinn_cam.Gain()
        self.camera_shm.update_keyword('DETGAIN', gain)
        logg.info(f'get_gain: {gain}')
        return gain

    def set_gain(self, gain: float):
        self.spinn_cam.Gain.SetValue(gain)
        return self.get_gain()

    def get_temperature(self):
        temp = self.spinn_cam.DeviceTemperature() + 273.15
        self.camera_shm.update_keyword('DET-TMP', temp)
        logg.info(f'get_temperature: {temp}')
        return temp


class FLIR_U3_Camera(SpinnakerUSBCamera):
    '''
        Appropriate class for Grasshopper and Flea U3 cameras
        e.g. Vampires pupil cam, FIRST pupil cam, Coro plane imager,

        Coro spy cam: GS3-U3-23S6M 1920x1200
        FIRST and Vampires pups: FL3-U3-13S2M 1328x1048

        Why are they different? They're prev. generations and are
        compatible with spinnaker but carried a lot of quirks of
        how they worked with PyCapture.

        #TODO This is not a very working class, use flycapturecam for the USB3 cameras
        #TODO instead
    '''

    INTERACTIVE_SHELL_METHODS = SpinnakerUSBCamera.INTERACTIVE_SHELL_METHODS
    FULL_GS = 'FULL_GS'
    FULL_FL = 'FULL_FL'

    MODES = {
            FULL_GS: CameraMode(x0=0, x1=1919, y0=0, y1=1199),
            FULL_FL: CameraMode(x0=0, x1=1327, y0=0, y1=1047),
    }

    KEYWORDS = {}
    KEYWORDS.update(SpinnakerUSBCamera.KEYWORDS)

    def _spinnaker_subtypes_constructor_finalizer(self):
        logg.debug('_spinnaker_subtypes_constructor_finalizer @ FLIR_U3_Camera')

        # Disable autoexp
        self.spinn_cam.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
        # Disable autogain
        self.spinn_cam.GainAuto.SetValue(PySpin.GainAuto_Off)
        # Set gamma to 1 - will only work if Gamma is enabled, so all good
        try:
            self.spinn_cam.Gamma.SetValue(1.0)
        except PySpin.SpinnakerException:
            logg.warning('Cannot set Gamma to 1.0 for this camera.')
            pass
        # BlackLevel 0. - May have to add some bias back
        self.spinn_cam.BlackLevel.SetValue(0)

        # Crank the gain to the max. Haven't figured out many things just yet.
        self.spinn_cam.Gain.SetValue(self.spinn_cam.Gain.GetMax())

    def _fill_keywords(self):

        SpinnakerUSBCamera._fill_keywords(self)
        self.camera_shm.update_keyword(
                'CROPPED', self.current_mode_id
                not in (self.FULL_GS, self.FULL_FL))
        self.camera_shm.update_keyword('DETECTOR', 'FLIR GS3 or FL3')

    def prepare_camera_for_size(self, mode_id=None):
        logg.debug('prepare_camera_for_size @ FLIR_U3_Camera')

        SpinnakerUSBCamera.prepare_camera_for_size(self, mode_id)

        if mode_id is None:
            mode = self.current_mode
        else:
            mode = self.MODES[mode_id]

        x0, x1 = mode.x0, mode.x1
        y0, y1 = mode.y0, mode.y1

        # Reset offsets
        self.spinn_cam.OffsetX.SetValue(0)
        self.spinn_cam.OffsetY.SetValue(0)

        # h, w
        self.spinn_cam.Width.SetValue(x1 - x0 + 1)
        self.spinn_cam.Height.SetValue(y1 - y0 + 1)

        # offsets
        self.spinn_cam.OffsetX.SetValue(x0)
        self.spinn_cam.OffsetY.SetValue(y0)

    def prepare_camera_finalize(self, mode_id=None):
        logg.debug('prepare_camera_finalize @ FLIR_U3_Camera')
        
        # Something that we feel is GS3/FL3 specific but not Spinnaker generic
        SpinnakerUSBCamera.prepare_camera_finalize(self, mode_id)


class BlackFlyS(SpinnakerUSBCamera):
    '''
        Appropriate class for the Blackfly S camera (Hilo lab?)
    '''

    INTERACTIVE_SHELL_METHODS = SpinnakerUSBCamera.INTERACTIVE_SHELL_METHODS + ['FULL']

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

    def _spinnaker_subtypes_constructor_finalizer(self):
        logg.debug('_spinnaker_subtypes_constructor_finalizer @ BlackFlyS')

        # Disable LED
        self.spinn_cam.DeviceIndicatorMode.SetValue(
                PySpin.DeviceIndicatorMode_Inactive)
        # Always max speed given exposure time
        self.spinn_cam.AcquisitionFrameRateEnable.SetValue(True)
        # Disable autoexp
        self.spinn_cam.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
        # Disable autogain
        self.spinn_cam.GainAuto.SetValue(PySpin.GainAuto_Off)
        # Disable gamma
        self.spinn_cam.GammaEnable.SetValue(False)

    def _fill_keywords(self):

        SpinnakerUSBCamera._fill_keywords(self)
        self.camera_shm.update_keyword('CROPPED',
                                       self.current_mode_id != self.FULL)
        self.camera_shm.update_keyword('DETECTOR', 'BlackFly S')

    def prepare_camera_for_size(self, mode_id=None):
        logg.debug('prepare_camera_for_size @ BlackFlyS')

        # Something that we feel is BlackFly specific but not Spinnaker generic
        SpinnakerUSBCamera.prepare_camera_for_size(self, mode_id)

        if mode_id is None:
            mode = self.current_mode
        else:
            mode = self.MODES[mode_id]

        x0, x1 = mode.x0, mode.x1
        y0, y1 = mode.y0, mode.y1

        # Reset offsets
        self.spinn_cam.OffsetX.SetValue(0)
        self.spinn_cam.OffsetY.SetValue(0)

        # Bin
        self.spinn_cam.BinningHorizontal.SetValue(mode.biny)
        self.spinn_cam.BinningVertical.SetValue(mode.binx)

        # h, w
        self.spinn_cam.Width.SetValue(x1 - x0 + 1)
        self.spinn_cam.Height.SetValue(y1 - y0 + 1)

        # offsets
        self.spinn_cam.OffsetX.SetValue(x0)
        self.spinn_cam.OffsetY.SetValue(y0)

        # Set ADC to 12 bit
        self.spinn_cam.AdcBitDepth.SetValue(PySpin.AdcBitDepth_Bit12)
        # Set pixel format to Mono12p
        self.spinn_cam.PixelFormat.SetValue(PySpin.PixelFormat_Mono12Packed)

    def prepare_camera_finalize(self, mode_id=None):
        logg.debug('prepare_camera_finalize @ BlackFlyS')

        # Something that we feel is BlackFly specific but not Spinnaker generic
        SpinnakerUSBCamera.prepare_camera_finalize(self, mode_id)


if __name__ == "__main__":
    cam = BlackFlyS('blackfly', 'alicia', mode_id=1, spinnaker_number=0)
    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())
