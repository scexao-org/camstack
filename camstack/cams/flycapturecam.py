import os
import time
import logging as logg

from typing import Union, Tuple, List, Any

from camstack.cams.base import BaseCamera
from camstack.core.utilities import CameraMode

import numpy as np

import PyCapture2 as PC2
from PyCapture2 import PIXEL_FORMAT, PROPERTY_TYPE as PROPS


def pretty_print_prop(cam: PC2.Camera, property_type: PC2.PROPERTY_TYPE):
    ''' PC2.PROPERTY_TYPE MEMBERS
        BRIGHTNESS
        AUTO_EXPOSURE
        SHARPNESS
        WHITE_BALANCE
        HUE
        SATURATION
        GAMMA
        IRIS
        FOCUS
        ZOOM
        PAN
        TILT
        SHUTTER
        GAIN
        TRIGGER_MODE
        TRIGGER_DELAY
        FRAME_RATE
        TEMPERATURE
        UNSPECIFIED_PROPERTY_TYPE
    '''
    prop = cam.getProperty(property_type)
    info = cam.getPropertyInfo(property_type)

    print(
            f'=== PROP ===\n',
            f'abs Ctrl: {prop.absControl}\n',
            f'abs Val:  {prop.absValue}\n',
            f'autoMan:  {prop.autoManualMode}\n',
            f'onePush:  {prop.onePush}\n',
            f'onOff:    {prop.onOff}\n',
            f'present:  {prop.present}\n',
            f'type:     {prop.type}\n',
            f'valA:     {prop.valueA}\n',
            f'valB:     {prop.valueB}',
    )
    print(f'=== INFO ===\n', f'abs max: {info.absMax}\n',
          f'abs min: {info.absMin}\n', f'can abs:  {info.absValSupported}\n',
          f'can auto: {info.autoSupported}\n',
          f'can manu: {info.manualSupported}\n', f'max: {info.max}\n',
          f'min: {info.min}\n', f'can onepush: {info.onePushSupported}\n',
          f'can onoff:   {info.onOffSupported}\n',
          f'present:     {info.present}\n',
          f'can readout: {info.readOutSupported}\n', f'type:     {info.type}\n',
          f'unitabbr: {info.unitAbbr}\n', f'unit:     {info.units}')


class FlyCaptureUSBCamera(BaseCamera):

    INTERACTIVE_SHELL_METHODS = ['get_fps', 'set_fps', 'get_tint',
    'set_tint', 'get_gain', 'set_gain', 'get_temperature'] + \
        BaseCamera.INTERACTIVE_SHELL_METHODS

    FULL_GS = 'FULL_GS'
    FULL_FL = 'FULL_FL'
    MODES = {
            FULL_GS: CameraMode(x0=0, x1=1919, y0=0, y1=1199),
            FULL_FL: CameraMode(x0=0, x1=1327, y0=0, y1=1047),
    }

    KEYWORDS = {}
    KEYWORDS.update(BaseCamera.KEYWORDS)

    MAX_GAIN = 0.

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

        BaseCamera.__init__(self, name, stream_name, mode_id, no_start=no_start,
                            taker_cset_prio=taker_cset_prio,
                            dependent_processes=dependent_processes)

        # Constructor finalizers were put init init_framegrab_backend

    def init_framegrab_backend(self):
        logg.debug('init_framegrab_backend @ FlyCaptureUSBCamera')

        if self.is_taker_running():
            msg = 'Cannot change camera config while camera is running'
            logg.error(msg)
            raise AssertionError(msg)

        if self.fly_bus is None:
            self.fly_bus = PC2.BusManager()

        if self.fly_cam is None:
            num_cams = self.fly_bus.getNumOfCameras()
            fly_serials = [
                    self.fly_bus.getCameraSerialNumberFromIndex(ii)
                    for ii in range(num_cams)
            ]

            # Will raise a bus master failure Fc2Error if camera doesn't exist
            if self.fly_number in fly_serials:  # It's a serial number
                uid = self.fly_bus.getCameraFromSerialNumber(self.fly_number)
            else:  # It's a list number
                uid = self.fly_bus.getCameraFromIndex(self.fly_number)

            self.fly_cam = PC2.Camera()
            self.fly_cam.connect(uid)

        self.fly_cam.setConfiguration(numBuffers=10,
                                      grabMode=PC2.GRAB_MODE.DROP_FRAMES,
                                      grabTimeout=1100)

        self.fly_cam.setProperty(type=PROPS.BRIGHTNESS, autoManualMode=False,
                                 onOff=True, absValue=0.0)
        self.fly_cam.setProperty(type=PROPS.AUTO_EXPOSURE, autoManualMode=False,
                                 onOff=False)
        self.fly_cam.setProperty(type=PROPS.SHARPNESS, autoManualMode=False,
                                 onOff=False)
        self.fly_cam.setProperty(type=PROPS.FRAME_RATE, autoManualMode=False,
                                 onOff=True, absControl=True)
        self.fly_cam.setProperty(type=PROPS.SHUTTER, autoManualMode=False,
                                 onOff=True, absControl=True)

        maxGain = self.fly_cam.getPropertyInfo(PROPS.GAIN).absMax
        self.fly_cam.setProperty(type=PROPS.GAIN, autoManualMode=False,
                                 onOff=True, absValue=maxGain, absControl=True)
        self.fly_cam.setProperty(type=PROPS.GAMMA, autoManualMode=False,
                                 onOff=False, absValue=1.0)

    def prepare_camera_for_size(self, mode_id=None):
        logg.debug('prepare_camera_for_size @ FlyCaptureUSBCamera')
        BaseCamera.prepare_camera_for_size(self)

        x0, x1 = self.current_mode.x0, self.current_mode.x1
        y0, y1 = self.current_mode.y0, self.current_mode.y1

        fmt7_info, _ = self.fly_cam.getFormat7Info(0)

        # Set camera to format7 video mode
        print('FlyCaptureUSBCamera.prepare_camera_for_size...')
        print('Max image pixels: ({}, {})'.format(fmt7_info.maxWidth,
                                                  fmt7_info.maxHeight))
        print('Image unit size: ({}, {})'.format(fmt7_info.imageHStepSize,
                                                 fmt7_info.imageVStepSize))
        print('Offset unit size: ({}, {})'.format(fmt7_info.offsetHStepSize,
                                                  fmt7_info.offsetVStepSize))
        print('Pixel format bitfield: 0x{}'.format(
                fmt7_info.pixelFormatBitField))

        # Preferred: Mono12, Mono16, Mono8
        if (fmt7_info.pixelFormatBitField & PC2.PIXEL_FORMAT.MONO12) > 0:
            logg.info('pixel format Mono12')
            px_fmt = PC2.PIXEL_FORMAT.MONO12
        elif (fmt7_info.pixelFormatBitField & PC2.PIXEL_FORMAT.MONO16) > 0:
            logg.info('pixel format Mono16')
            px_fmt = PC2.PIXEL_FORMAT.MONO16
        elif (fmt7_info.pixelFormatBitField & PC2.PIXEL_FORMAT.MONO8) > 0:
            logg.info('pixel format Mono8')
            px_fmt = PC2.PIXEL_FORMAT.MONO8

        fmt7_set = PC2.Format7ImageSettings(PC2.MODE.MODE_0, x0, y0,
                                            x1 - x0 + 1, y1 - y0 + 1,
                                            PC2.PIXEL_FORMAT.MONO12)
        fmt7_pkt_inf, is_valid = self.fly_cam.validateFormat7Settings(fmt7_set)
        self.fly_cam.setFormat7ConfigurationPacket(
                fmt7_pkt_inf.recommendedBytesPerPacket, fmt7_set)

        #TODO binning?

    def prepare_camera_finalize(self):
        logg.debug('prepare_camera_finalize @ FlyCaptureUSBCamera')

        BaseCamera.prepare_camera_finalize(self)

        # Set fps max
        fps_max = self.fly_cam.getPropertyInfo(PROPS.FRAME_RATE).absMax
        self.set_fps(fps_max)

        # Expo max
        tint_max = self.fly_cam.getPropertyInfo(PROPS.SHUTTER).absMax
        self.set_tint(tint_max)

        # Lower fps, tint if necessary
        if self.current_mode.tint is not None:
            self.set_fps(1. / self.current_mode.fps)
            self.set_tint(self.current_mode.tint)

        if self.current_mode.fps is not None:
            self.set_fps(self.current_mode.fps)

    def release(self):
        BaseCamera.release(self)

        logg.info('fly_cam.disconnect()')
        self.fly_cam.disconnect()
        del self.fly_cam

    def _prepare_backend_cmdline(self, reuse_shm: bool = False):

        # Prepare the cmdline for starting up!
        exec_path = "python -m camstack.acq.flycapture_usbtake"
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
        fps = self.fly_cam.getProperty(PROPS.FRAME_RATE).absValue
        self._set_formatted_keyword('FRATE', fps)
        logg.info(f'get_fps: {fps}')
        return fps

    def set_fps(self, fps: float):
        self.fly_cam.setProperty(type=PROPS.FRAME_RATE, absValue=fps)
        return self.get_fps()

    def get_tint(self):
        tint = self.fly_cam.getProperty(PROPS.SHUTTER).absValue / 1000.
        self._set_formatted_keyword('EXPTIME', tint)
        logg.info(f'get_fps: {tint}')
        return tint

    def set_tint(self, tint: float):
        self.fly_cam.setProperty(type=PROPS.SHUTTER, absValue=tint * 1000.)
        return self.get_tint()

    def get_gain(self):
        gain = self.fly_cam.getProperty(PROPS.GAIN).absValue
        self._set_formatted_keyword('DETGAIN', gain)
        logg.info(f'get_gain: {gain}')
        return gain

    def set_gain(self, gain: float):
        self.fly_cam.setProperty(type=PROPS.GAIN, absValue=gain)
        return self.get_gain()

    def get_temperature(self):
        # FIXME it doesn't change much at all. I think it's lying.
        temp = self.fly_cam.getProperty(PROPS.TEMPERATURE).absValue + 273.15
        self._set_formatted_keyword('DET-TMP', temp)
        logg.info(f'get_temperature: {temp}')
        return temp


class Grasshopper3(FlyCaptureUSBCamera):

    INTERACTIVE_SHELL_METHODS = FlyCaptureUSBCamera.INTERACTIVE_SHELL_METHODS

    FULL = 'FULL'

    MODES = {
            FULL: CameraMode(x0=0, x1=1919, y0=0, y1=1199),
            # Centercrop half-size, adjusted for granularity?
            1: CameraMode(x0=480, x1=1439, y0=300, y1=899),
    }
    MODES.update(FlyCaptureUSBCamera.MODES)

    KEYWORDS = {}
    KEYWORDS.update(FlyCaptureUSBCamera.KEYWORDS)

    def _fill_keywords(self):

        FlyCaptureUSBCamera._fill_keywords(self)
        self._set_formatted_keyword('CROPPED', self.current_mode_id
                                    != self.FULL)
        self._set_formatted_keyword('DETECTOR', 'FLIR GS3')
        self._set_formatted_keyword("DETPXSZ1", 0.00586)
        self._set_formatted_keyword("DETPXSZ2", 0.00586)


class Flea3(FlyCaptureUSBCamera):

    INTERACTIVE_SHELL_METHODS = FlyCaptureUSBCamera.INTERACTIVE_SHELL_METHODS

    FULL = 'FULL'

    MODES = {
            FULL: CameraMode(x0=0, x1=1327, y0=0, y1=1047),
            # Centercrop half-size, adjusted for granularity?
            1: CameraMode(x0=332, x1=995, y0=262, y1=785),
    }
    MODES.update(FlyCaptureUSBCamera.MODES)

    KEYWORDS = {}
    KEYWORDS.update(FlyCaptureUSBCamera.KEYWORDS)

    def _fill_keywords(self):

        FlyCaptureUSBCamera._fill_keywords(self)
        self._set_formatted_keyword('CROPPED', self.current_mode_id
                                    != self.FULL)
        self._set_formatted_keyword('DETECTOR', 'FLIR Flea3')
        self._set_formatted_keyword("DETPXSZ1", 0.00363)
        self._set_formatted_keyword("DETPXSZ2", 0.00363)


class VampiresPupilFlea(Flea3):

    MODES = {
            'CROP_VPUP':
                    CameraMode(x0=444, x1=955, y0=310, y1=821, fps=30,
                               tint=0.03),
    }
    MODES.update(Flea3.MODES)

    def _fill_keywords(self):
        Flea3._fill_keywords(self)
        self._set_formatted_keyword('DETECTOR', 'VAMPIRES PUPCAM')


class FirstPupilFlea(Flea3):

    def _fill_keywords(self):
        Flea3._fill_keywords(self)
        self._set_formatted_keyword('DETECTOR', 'FIRST PUPCAM')
