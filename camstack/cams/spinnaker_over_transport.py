from __future__ import annotations
import typing as typ

import time
import logging as logg

from typing import Any

from camstack.cams.base import BaseCamera
from camstack.core.utilities import CameraMode, Typ_mode_id, Typ_mode_id_or_heightwidth

from camstack.scxkw import MAGIC_BOOL_STR

from hwmain.spinnaker import sdk

from camstack.cams.params_shm_backend import ParamsSHMCamera, CommandTransport

SPINNAKER_API_KEY_T: typ.TypeAlias = str | sdk.Prop


class CommandTransportForSpinnaker(CommandTransport[SPINNAKER_API_KEY_T]):
    if typ.TYPE_CHECKING:
        from pyMilk.interfacing.shm import KWType

    def getter_prop_mod_to_request(self, prop: sdk.Prop,
                                   modifier: str = 'val') -> sdk.REQUEST:
        if prop.type in (int, float):
            if modifier == 'min':
                return sdk.REQUEST.GETMIN
            elif modifier == 'max':
                return sdk.REQUEST.GETMAX

        if modifier != 'val':
            raise ValueError(
                    f'property {prop.name} of type {prop.type} with modifier {modifier}: not allowed.'
            )

        return sdk.REQUEST.GETORCALL

    def setter_prop_to_request(self, prop: sdk.Prop) -> sdk.REQUEST:

        if prop.type == sdk.T_Command:
            return sdk.REQUEST.GETORCALL
        else:
            return sdk.REQUEST.SETVALUE

        raise NotImplementedError('Unknown prop.type for CB2 getter?')

    def getter_request_to_k_v_c(self, api_key: SPINNAKER_API_KEY_T
                                ) -> tuple[str, KWType, str]:
        # What is API key here ???
        # PropName[#(min|max|inc|val)]
        if isinstance(api_key, sdk.Prop):
            prop, modifier = api_key, 'val'
        elif not '#' in api_key:
            prop, modifier = sdk.PROP_DICT[api_key], 'val'
        else:
            prop_name, modifier = api_key.split('#')
            prop = sdk.PROP_DICT[prop_name]

        request = self.getter_prop_mod_to_request(prop, modifier)

        k = f'{((prop.unique_id << 4) | request):08x}'

        if prop.type == int or issubclass(prop.type, sdk.IntEnum):
            v = 123
        elif prop.type == float:
            v = 0.123
        elif prop.type == bool:
            v = MAGIC_BOOL_STR.FALSE
        else:
            v = 'plholder'

        c = prop.name

        return k, v, c

    def setter_request_to_k_v_c(self, api_key: SPINNAKER_API_KEY_T,
                                value: typ.Any) -> tuple[str, KWType, str]:
        if isinstance(api_key, sdk.Prop):
            prop = api_key
        else:
            prop = sdk.PROP_DICT[api_key]

        request = self.setter_prop_to_request(prop)

        k = f'{((prop.unique_id << 4) | request):08x}'

        if prop.type == bool:
            assert isinstance(value, bool)
            return k, MAGIC_BOOL_STR.TUPLE[value], prop.name

        if prop.type == int or issubclass(prop.type, sdk.IntEnum):
            assert isinstance(value, (int, bool))
            return k, int(value), prop.name  # type: ignore

        if prop.type == float:
            assert isinstance(value, (int, bool, float))
            return k, float(value), prop.name  # type: ignore

        if prop.type == sdk.T_Command:
            assert value is None
            return k, 'plholder', prop.name

        if prop.type == str:
            # We put the value in the comment section... not enough chars in the value section !
            assert isinstance(value, str)
            return k, 'plholder', prop.name + '#' + value

        raise NotImplementedError(f'Unreachable? Prop {prop}, value {value}.')

    if typ.TYPE_CHECKING:
        from ..core.utilities import Typ_shm_kw

    def kvc_to_transport_return_vals(self, kw_key: str, value: KWType,
                                     comment: str) -> Typ_shm_kw:

        if '#' in comment:  # It was a string or StrEnum request
            return comment.split('#')[1]
        if value == MAGIC_BOOL_STR.TRUE:
            return True
        if value == MAGIC_BOOL_STR.FALSE:
            return False
        return value

    def to_fits_val(self, api_key: SPINNAKER_API_KEY_T, value: Typ_shm_kw):
        if isinstance(value, str):
            return value[:15]
        else:
            return value

    def to_format_val(self, api_key: SPINNAKER_API_KEY_T, value: Typ_shm_kw):
        if isinstance(api_key, str):
            prop = sdk.PROP_DICT[api_key.split('#')[0]]
        else:
            prop = api_key
        if issubclass(prop.type, sdk.IntEnum):
            return prop.type(value)
        else:
            return value


# GIGE 16048585

class SpinnakerTransportedCamera(ParamsSHMCamera):

    INTERACTIVE_SHELL_METHODS = [] + \
        BaseCamera.INTERACTIVE_SHELL_METHODS

    MODES = {}

    KEYWORDS = {
            # DETGAIN is NOT a kw from the base class.
            'DETGAIN': (0, 'Amplifier gain [dB]', '%16d', 'GAIN'),
    }
    KEYWORDS.update(BaseCamera.KEYWORDS)

    CLS_SHM_COMMUNICATOR = CommandTransportForSpinnaker
    ctrl_transport: CommandTransport[SPINNAKER_API_KEY_T] # helpful for the type checker.

    def __init__(self, name: str, stream_name: str,
                 mode_id: Typ_mode_id_or_heightwidth, spinnaker_number: int,
                 no_start: bool = False,
                 taker_cset_prio: tuple[str, int | None] = ('system', None),
                 dependent_processes: list[Any] = []):

        # Do basic stuff
        self.spinn_number = spinnaker_number
        # Initialized in init_framegrab_backend
        self.spinn_system = None
        self.spinn_cam = None

        BaseCamera.__init__(self, name, stream_name, mode_id, no_start=no_start,
                            taker_cset_prio=taker_cset_prio,
                            dependent_processes=dependent_processes)

        self._spinnaker_subtypes_constructor_finalizer()

    def _spinnaker_subtypes_constructor_finalizer(self):
        raise NotImplementedError(
                '_spinnaker_subtypes_constructor_finalizer @ SpinnakerTransportedCamera'
        )

    def prepare_camera_for_size(
            self,
            mode_id: None | Typ_mode_id = None,
            params_injection: None | dict[SPINNAKER_API_KEY_T, typ.Any] = None,
    ) -> None:

        logg.debug('prepare_camera_for_size @ SpinnakerTransportedCamera')
        super().prepare_camera_for_size()

        mode = self.current_mode

        x0, x1 = mode.x0, mode.x1
        y0, y1 = mode.y0, mode.y1

        # yapf: disable
        params: dict[SPINNAKER_API_KEY_T, typ.Any] = {
                sdk.OffsetX: x0,
                sdk.OffsetY: y0,
                sdk.BinningHorizontal: mode.binx,
                sdk.BinningVertical: mode.biny,
                sdk.Width:   x1 - x0 + 1,
                sdk.Height:  y1 - y0 + 1,
                # Trigger defaults: free-running
                sdk.TriggerMode: sdk.TriggerModeEnum.Off,
                sdk.PixelFormat: sdk.PixelFormatEnum.Mono12Packed,
                sdk.AcquisitionMode: sdk.AcquisitionModeEnum.Continuous,
                #sdk.TriggerSelector: sdk.TriggerSelectorEnum.FrameStart,
                #sdk.TriggerActivation: sdk.TriggerActivationEnum.RisingEdge,
                # Other misc initializers:
        }
        # yapf: enable

        if params_injection is not None:
            params.update(params_injection)

        if self.current_mode.tint is not None:
            params[sdk.ExposureTime] = self.current_mode.tint * 1e6

        api_keys = list(params.keys())
        values = list(params.values())
        self.ctrl_transport.setmulti_nofeedback_nosync(values, api_keys)


    def prepare_camera_finalize(self, mode_id=None):
        # Only the stuff that is mode dependent
        # And/or should be called after each mode change.
        # And is camera-genre specific

        logg.debug('prepare_camera_finalize @ SpinnakerTransportedCamera')

        # Set fps max
        max_fps = self.ctrl_transport.get(sdk.AcquisitionFrameRate.max)[0]  # Hz
        self.set_fps(max_fps)
        # Expo max
        # Dont do this in triggermode, since the max expo is essentially veryyyyy long?
        max_expo_this_fps = min(
                self.ctrl_transport.get(sdk.ExposureTime.max)[0] * 1e-6,
                1 / max_fps)
        self.set_tint(max_expo_this_fps)

        # Lower fps, tint if necessary
        if self.current_mode.tint is not None:
            self.set_tint(self.current_mode.tint)

        if self.current_mode.fps is not None:
            self.set_fps(self.current_mode.fps)

    def _prepare_backend_cmdline(self, reuse_shm: bool = False,
                                 env_launcher: str = ''):

        # Prepare the cmdline for starting up!
        exec_path = env_launcher + "hwacq-spintransporttake"
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

        self._set_formatted_keyword('DETECTOR', 'FLIR Spinnaker')

        self.poll_camera_for_keywords()

    def poll_camera_for_keywords(self):
        self.get_temperature()

    def get_fps(self):
        fpsval, fpsfits = self.ctrl_transport.get(sdk.AcquisitionFrameRate)
        self._set_formatted_keyword('FRATE', fpsfits)
        logg.info(f'get_fps: {fpsval}')
        return fpsval

    def set_fps(self, fps: float):
        self.ctrl_transport.set(fps, sdk.AcquisitionFrameRate)
        return self.get_fps()

    def get_tint(self):
        tintval, tintfits = self.ctrl_transport.get(sdk.ExposureTime)
        self._set_formatted_keyword('EXPTIME', tintfits / 1e6)
        logg.info(f'get_tint: {tintval / 1e6}')
        return tintval / 1e6

    def set_tint(self, tint: float):
        self.ctrl_transport.set(tint * 1e6, sdk.ExposureTime)
        return self.get_tint()

    def get_gain(self):
        gainval, gainfits = self.ctrl_transport.get(sdk.Gain)
        self._set_formatted_keyword(
                'DETGAIN', gainfits)  # DETGAIN is NOT a kw from the base class.
        logg.info(f'get_gain: {gainval}')
        return gainval

    def set_gain(self, gain: float):
        self.ctrl_transport.set(gain, sdk.Gain)
        return self.get_gain()

    def get_temperature(self):
        tempval = self.ctrl_transport.get(sdk.DeviceTemperature)[0] + 273.15
        self._set_formatted_keyword('DET-TMP', tempval)
        logg.info(f'get_temperature: {tempval}')
        return tempval


class USYD_VIS_PG2(SpinnakerTransportedCamera):
    '''
        Blackfly BFLY-PGE-31S4M
--------- CAMERA 1 [16048585] ----------
Point Grey Research Blackfly BFLY-PGE-31S4M [No FamilyName info] [IP: 192.168.10.2 - Mask: 255.255.255.0] [ID=16048585]
WidthMax                  2048                 [  ]   (0 -- 65535)
HeightMax                 1536                 [  ]   (0 -- 65535)
BinningHorizontal         1                    [  ]   (1 -- 2)
BinningVertical           1                    [  ]   (1 -- 2)
AcquisitionFrameRate      [Error during getvalue]
ExposureTime              17.22574234008789    [us]   (17.22574234008789 -- 11995666.50390625)
ExposureAuto              EnumEntry_ExposureAuto_Off
Gain                      0.0                  [dB]   (0.0 -- 47.994266510009766)
GainAuto                  EnumEntry_GainAuto_Off
Width                     256                  [  ]   (4 -- 936)
Height                    256                  [  ]   (2 -- 904)
OffsetX                   1112                 [  ]   (0 -- 1792)
OffsetY                   632                  [  ]   (0 -- 1280)
TriggerActivation         EnumEntry_TriggerActivation_FallingEdge
TriggerDelay              0.0                  [us]   (0.0 -- 65000000.0)
TriggerMode               EnumEntry_TriggerMode_On
TriggerSource             EnumEntry_TriggerSource_Software
TriggerSelector           EnumEntry_TriggerSelector_FrameStart
    '''

    INTERACTIVE_SHELL_METHODS = SpinnakerTransportedCamera.INTERACTIVE_SHELL_METHODS + [
            'FULL'
    ]

    FULL = 'FULL'

    MODES = {
            FULL: CameraMode(x0=0, x1=1791, y0=0, y1=1279),
            # Centercrop half-size
            1: CameraMode(x0=448, x1=1791 - 448, y0=320, y1=1279 - 320),
            # 256x256 offseted
            2: CameraMode(x0=1112, x1=1112 + 256 - 1, y0=632, y1=632 + 256 - 1)
    }

    KEYWORDS = {}
    KEYWORDS.update(SpinnakerTransportedCamera.KEYWORDS)

    def _spinnaker_subtypes_constructor_finalizer(self):
        logg.debug('_spinnaker_subtypes_constructor_finalizer @ BFLY-PGE-31S4M')

        # Disable LED
        self.ctrl_transport.set(sdk.DeviceIndicatorModeEnum.Inactive, sdk.DeviceIndicatorMode)
        # Disable autoexp
        self.ctrl_transport.set(sdk.ExposureAutoEnum.Off, sdk.ExposureAuto)
        # Disable autogain
        self.ctrl_transport.set(sdk.GainAutoEnum.Off, sdk.GainAuto)

    def _fill_keywords(self):

        SpinnakerTransportedCamera._fill_keywords(self)
        self._set_formatted_keyword('CROPPED', self.current_mode_id
                                    != self.FULL)
        self._set_formatted_keyword('DETECTOR', 'BFLY-PGE-31S4M')

        self._set_formatted_keyword('DETPXSZ1', 0.00345)
        self._set_formatted_keyword('DETPXSZ2', 0.00345)

    def prepare_camera_finalize(self, mode_id=None):
        logg.debug('prepare_camera_finalize @ BFLY-PGE-31S4M')

        # Something that we feel is BlackFly specific but not Spinnaker generic
        SpinnakerTransportedCamera.prepare_camera_finalize(self, mode_id)

    def _prepare_backend_cmdline(self, reuse_shm: bool = False,
                                 env_launcher: str = 'mamba run -n py38 '):
        return super()._prepare_backend_cmdline(reuse_shm=reuse_shm,
                                                env_launcher=env_launcher)

    def set_fps(self, fps: float) -> float:
        '''
        Override -- this camera does not support set_fps.
        '''
        return self.get_fps()

    def get_fps(self):
        max_fps = self.ctrl_transport.get(sdk.AcquisitionFrameRate.max)[0]  # Hz
        tint = self.get_tint()
        fps = min(1 / tint, max_fps)
        self._set_formatted_keyword('FRATE', fps)
        logg.info(f'get_fps: {fps}')
        return fps

    def disable_trigger(self) -> None:
        self.ctrl_transport.set(sdk.TriggerModeEnum.Off, sdk.TriggerMode)

    def enable_software_trigger(self, delay_us: float = 0) -> None:
        self._enable_trigger(sdk.TriggerSourceEnum.Software, delay_us = delay_us)

    def enable_hardware_trigger(self, delay_us: float = 0):
        self._enable_trigger(sdk.TriggerSourceEnum.Line0, delay_us = delay_us)

    def _enable_trigger(self, source: sdk.TriggerSourceEnum, delay_us: float = 0) -> None:
        # EDIT I don't believe triggerdelay is working?
        params: dict[SPINNAKER_API_KEY_T, typ.Any] = {
            sdk.TriggerMode: sdk.TriggerModeEnum.On,
            sdk.TriggerSource: source,
            sdk.TriggerActivation: sdk.TriggerActivationEnum.FallingEdge,
        }
        if delay_us > 0:
            params.update({
                sdk.TriggerDelayEnabled: True,
                sdk.TriggerDelay: delay_us,
            })
        else:
            params.update({
                sdk.TriggerDelayEnabled: False
            })
        api_keys: list[SPINNAKER_API_KEY_T] = []
        values = []
        for a,v in params.items():
            api_keys += [a]
            values += [v]
        self.ctrl_transport.setmulti(values, api_keys)

    def send_software_trigger(self):
        self.ctrl_transport.set(None, sdk.TriggerSoftware)
