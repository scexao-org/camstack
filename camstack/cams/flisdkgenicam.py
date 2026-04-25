from __future__ import annotations
import typing as typ

import os
import logging as logg

from camstack.cams.params_shm_backend import ParamsSHMCamera, CommandTransport
from camstack.core import utilities as util

from camstack.scxkw import MAGIC_BOOL_STR

from enum import IntEnum

from hwmain.andor import flisdk_for_andorcb2 as sdk

CB2_API_KeyT: typ.TypeAlias = str | sdk.Prop


class CommandTransportForGenicam(CommandTransport[CB2_API_KeyT]):
    '''
    How to pass Genicam commands through an SHM transport?

    Based off work done for Andor CB2 w/ FliSDK_V2

    The "function information" that needs to pass:
    <list of functions>

	def GetBooleanFeature(self, context, feature):
	def GetIntegerFeature(self, context, feature):
	def GetDoubleFeature(self, context, feature):
    def GetStringFeature(self, context, feature):

	def SetBooleanFeature(self, context, feature, val):
	def SetIntegerFeature(self, context, feature, val):
	def SetDoubleFeature(self, context, feature, val):
	def SetStringFeature(self, context, feature, val):

	def ExecuteFeature(self, context, feature):

	def GetDoubleMinFeature(self, context, feature):
	def GetDoubleMaxFeature(self, context, feature):
	def GetIntegerMinFeature(self, context, feature):
	def GetIntegerMaxFeature(self, context, feature):
	def GetDoubleIncrementFeature(self, context, feature):
	def GetIntegerIncrementFeature(self, context, feature):

	def GetPollingInterval(self, context, feature): ????

    The arguments: bool, float, int, str

    The container:
    16 bytes for key, 16 bytes for value, 80 bytes for comment

    AND we need unique keywords. No forgetti.
    '''

    if typ.TYPE_CHECKING:
        from pyMilk.interfacing.shm import KWType

    def getter_prop_mod_to_request(self, prop: sdk.Prop,
                                   modifier: str) -> sdk.REQUEST:
        if prop.type == int:
            return {
                    'val': sdk.REQUEST.GET_INT,
                    'min': sdk.REQUEST.GET_INTMIN,
                    'max': sdk.REQUEST.GET_INTMAX,
                    'inc': sdk.REQUEST.GET_INTINCR,
            }[modifier]
        if prop.type == float:
            return {
                    'val': sdk.REQUEST.GET_DOUBLE,
                    'min': sdk.REQUEST.GET_DOUBLEMIN,
                    'max': sdk.REQUEST.GET_DOUBLEMAX,
                    'inc': sdk.REQUEST.GET_DOUBLEINCR,
            }[modifier]

        if modifier != 'val':
            raise ValueError(
                    f'property {prop.name} of type {prop.type} with modifier {modifier}: not allowed.'
            )

        if prop.type == bool:
            return sdk.REQUEST.GET_BOOL
        if prop.type == str or issubclass(prop.type, sdk.StrEnum):
            return sdk.REQUEST.GET_STRING

        raise NotImplementedError('Unknown prop.type for CB2 getter?')

    def setter_prop_to_request(self, prop: sdk.Prop) -> sdk.REQUEST:
        if prop.type == int:
            return sdk.REQUEST.SET_INT
        if prop.type == float:
            return sdk.REQUEST.SET_DOUBLE
        if prop.type == bool:
            return sdk.REQUEST.SET_BOOL
        if prop.type == str or issubclass(prop.type, sdk.StrEnum):
            return sdk.REQUEST.SET_STRING

        if prop.type == sdk.Command:
            return sdk.REQUEST.EXEC

        raise NotImplementedError('Unknown prop.type for CB2 getter?')

    def getter_request_to_k_v_c(self, api_key: CB2_API_KeyT
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

        if prop.type == int:
            v = 123
        elif prop.type == float:
            v = 0.123
        elif prop.type == bool:
            v = MAGIC_BOOL_STR.FALSE
        else:
            v = 'plholder'

        c = prop.name

        return k, v, c

    def setter_request_to_k_v_c(self, api_key: CB2_API_KeyT,
                                value: typ.Any) -> tuple[str, KWType, str]:
        if isinstance(api_key, sdk.Prop):
            prop = api_key
        else:
            prop = sdk.PROP_DICT[api_key]

        request = self.setter_prop_to_request(prop)

        k = f'{((prop.unique_id << 4) | request):08x}'

        if prop.type in [int, float]:
            assert isinstance(value, prop.type)
            return k, value, prop.name  # type: ignore

        if prop.type == bool:
            assert isinstance(value, bool)
            return k, MAGIC_BOOL_STR.TUPLE[value], prop.name

        if prop.type == sdk.Command:
            assert value is None
            return k, 'plholder', prop.name

        if prop.type == str:
            # We put the value in the comment section... not enough chars in the value section !
            assert isinstance(value, str)
            return k, 'plholder', prop.name + '#' + value

        if issubclass(prop.type, sdk.StrEnum):
            if isinstance(value, str):
                value = prop.type(value)
            assert isinstance(value, prop.type)
            return k, 'plholder', prop.name + '#' + value  # value is a StrEnum and devolves to str concatenation

        raise NotImplementedError(f'Unreachable? Prop {prop}, value {value}.')

    if typ.TYPE_CHECKING:
        from ..core.utilities import Typ_shm_kw

    def kvc_to_transport_return_vals(self, kw_key: str, value: KWType,
                                     comment: str) -> Typ_shm_kw:
        # This really specifies how the other side of the transport is expected to answer
        # bool -> in the value field as #TRUE# or #FALSE#
        # int, float -> in the value field
        # string: concatenaded in the comment field (more room)

        if '#' in comment:  # It was a string or StrEnum request
            return comment.split('#')[1]
        if value == MAGIC_BOOL_STR.TRUE:
            return True
        if value == MAGIC_BOOL_STR.FALSE:
            return False
        return value

    def to_fits_val(self, api_key: CB2_API_KeyT, value: Typ_shm_kw):
        # Return from kvc_to_transport_return_vals(self, kw_key: str, value: KWType)
        # is mostly acceptable already.
        # Except that we may have to truncate the string for FITS and SHMs
        if isinstance(value, str):
            return value[:15]
        else:
            return value

    def to_format_val(self, api_key: CB2_API_KeyT, value: Typ_shm_kw):
        if isinstance(api_key, str):
            prop = sdk.PROP_DICT[api_key.split('#')[0]]
        else:
            prop = api_key
        if issubclass(prop.type, sdk.StrEnum):
            return prop.type(value)
        else:
            return value


class FliSdkGenicam(ParamsSHMCamera):

    INTERACTIVE_SHELL_METHODS = [] + ParamsSHMCamera.INTERACTIVE_SHELL_METHODS

    MODES = {}

    KEYWORDS = {}
    KEYWORDS.update(ParamsSHMCamera.KEYWORDS)

    CLS_SHM_COMMUNICATOR = CommandTransportForGenicam

    IS_WATER_COOLED = False  # Amend in subclasses.

    def __init__(
            self,
            name: str,
            stream_name: str,
            mode_id: util.Typ_mode_id_or_heightwidth,
            flisdk_index: int,
            no_start: bool = False,
            taker_cset_prio: util.Typ_tuple_cset_prio = ("system", None),
            dependent_processes: list[util.DependentProcess] = [],
    ) -> None:
        self.cam_index = flisdk_index
        super().__init__(
                name,
                stream_name,
                mode_id,
                no_start=no_start,
                taker_cset_prio=taker_cset_prio,
                dependent_processes=dependent_processes,
        )

    def prepare_camera_for_size(
            self,
            mode_id: None | util.Typ_mode_id = None,
            params_injection: None | dict[CB2_API_KeyT, typ.Any] = None,
    ) -> None:
        logg.debug("prepare_camera_for_size @ FliSdkGenicam")
        super().prepare_camera_for_size(mode_id=mode_id)

        x0, x1 = self.current_mode.x0, self.current_mode.x1
        y0, y1 = self.current_mode.y0, self.current_mode.y1

        # yapf: disable
        params: dict[CB2_API_KeyT, typ.Any] = {
                sdk.OffsetX: x0,
                sdk.OffsetY: y0,
                sdk.Width:   x1 - x0 + 1,
                sdk.Height:  y1 - y0 + 1,
                # Trigger defaults: free-running
                # TODO: TriggerSelector must be set to FrameStart on the C side
                sdk.TriggerSelector: sdk.TriggerSelectorEnum.FrameStart,
                sdk.TriggerMode: sdk.TriggerModeEnum.Off,
                sdk.TriggerActivation: sdk.TriggerActivationEnum.RisingEdge,
                # Other misc initializers:
                sdk.DeviceTemperatureSelector: sdk.DeviceTemperatureSelectorEnum.Sensor
        }
        # yapf: enable

        if params_injection is not None:
            params.update(params_injection)

        if self.current_mode.tint is not None:
            params[sdk.ExposureTime] = self.current_mode.tint * 1e6

        api_keys = list(params.keys())
        values = list(params.values())
        self.ctrl_transport.setmulti_nofeedback_nosync(values, api_keys)

    def abort_exposure(self, injected_tint: float = 0.001) -> None:
        with self.ctrl_transport.control_shm_lock:
            self._kill_taker_no_dependents()
            self.prepare_camera_for_size(
                    self.current_mode_id,
                    params_injection={sdk.ExposureTime: injected_tint})
            self._start_taker_no_dependents(reuse_shm=True)

    def _prepare_backend_cmdline(self, reuse_shm: bool = False) -> None:
        exec_path = os.environ["SCEXAO_HW"] + "/bin/hwacq-flitake"
        self.taker_tmux_command = (f"{exec_path} -s {self.STREAMNAME} "
                                   f"-u {self.cam_index} -l 0 -N 4")
        if reuse_shm:
            self.taker_tmux_command += " -R"  # Do not overwrite the SHM.


class AndorCB2_7_1(FliSdkGenicam):

    INTERACTIVE_SHELL_METHODS = [
            "set_tint",
            "get_tint",
            "get_temperature",
            "get_fps",
            "set_fps",
            "get_maxfps",
            "set_readout_mode",
            "get_readout_mode",
            "get_external_trigger",
            "set_external_trigger",
    ] + FliSdkGenicam.INTERACTIVE_SHELL_METHODS

    FULL = 'FULL'

    # yapf: disable
    MODES = {
            FULL: util.CameraMode(x0=0, x1=3215, y0=0, y1=2207, tint=0.001),
    }
    # yapf: enable

    KEYWORDS = {}
    KEYWORDS.update(FliSdkGenicam.KEYWORDS)

    IS_WATER_COOLED = False  # Amend in subclasses.

    def __init__(
            self,
            name: str,
            stream_name: str,
            mode_id: util.Typ_mode_id_or_heightwidth,
            flisdk_index: int,
            no_start: bool = False,
            taker_cset_prio: util.Typ_tuple_cset_prio = ("system", None),
            dependent_processes: list[util.DependentProcess] = [],
    ) -> None:
        super().__init__(
                name,
                stream_name,
                mode_id,
                flisdk_index,
                no_start=no_start,
                taker_cset_prio=taker_cset_prio,
                dependent_processes=dependent_processes,
        )

    def _fill_keywords(self) -> None:
        super()._fill_keywords()
        self._set_formatted_keyword("DETECTOR", "Andor CB2 7.1")
        self._set_formatted_keyword("CROPPED", self.current_mode_id
                                    != self.FULL)
        self._set_formatted_keyword("DETPXSZ1", 0.0045)
        self._set_formatted_keyword("DETPXSZ2", 0.0045)

        # TODO probably these should be initialized?
        self._set_formatted_keyword('GAIN', \
                self.ctrl_transport.get(sdk.Gain)[1])
        self._set_formatted_keyword('DETBIAS', \
                self.ctrl_transport.get(sdk.BlackLevel)[1])

    def poll_camera_for_keywords(self) -> None:
        self.get_temperature()

    def get_temperature(self) -> float:
        temp_C, _ = self.ctrl_transport.get(sdk.DeviceTemperature)
        temp_K = temp_C + 273.15
        self._set_formatted_keyword("DET-TMP", temp_K)
        logg.info(f"get_temperature {temp_K} K")
        return temp_K

    def get_tint(self) -> float:
        val, val_fits = self.ctrl_transport.get(sdk.ExposureTime)
        self._set_formatted_keyword("EXPTIME", val_fits)
        logg.info(f"get_tint {val}")
        return val

    def set_tint(self, tint: float) -> float:
        tint, tint_fits = self.ctrl_transport.set(tint, sdk.ExposureTime)
        self._set_formatted_keyword("EXPTIME", tint_fits)
        self.get_fps()
        return tint

    def get_fps(self) -> float:
        fps, fps_fits = self.ctrl_transport.get(sdk.AcquisitionFrameRate)
        self._set_formatted_keyword("FRATE", fps_fits)
        logg.info(f"get_fps {fps}")
        return fps

    def set_fps(self, fps: float) -> float:
        fps, fps_fits = self.ctrl_transport.set(fps, sdk.AcquisitionFrameRate)
        self._set_formatted_keyword("FRATE", fps_fits)
        return fps

    def get_maxfps(self) -> float:
        fps, _ = self.ctrl_transport.get(
                sdk.MaximumExternalAcquisitionFrameRate)
        logg.info(f"get_maxfps {fps}")
        return fps

    def get_conversion_efficiency(self) -> str:
        mode, _ = self.ctrl_transport.get(sdk.ConversionEfficiency)
        # TODO there should be a SHM keyword here?
        return mode

    def set_conversion_efficiency(self, mode: str) -> None:
        logg.debug("set_readout_mode @ AndorCB2_7_1")
        mode = mode.upper()
        if mode == self.get_conversion_efficiency():
            logg.debug(f"Already in readout mode {mode}; doing nothing")
            return
        if mode == "LOW":
            val = sdk.ConversionEfficiencyEnum.Low
        elif mode == "HIGH":
            val = sdk.ConversionEfficiencyEnum.High
        else:
            raise ValueError(f"Unrecognized readout mode: {mode}")
        self.ctrl_transport.set(sdk.ConversionEfficiency, val)

    def get_external_trigger(self) -> bool:
        # Todo TriggerSelector ?
        mode, _ = self.ctrl_transport.get(sdk.TriggerMode)
        val = (mode == sdk.TriggerModeEnum.On)
        self._set_formatted_keyword("EXTTRIG", val)
        return val

    def set_external_trigger(self, enable: bool) -> bool:
        # Todo TriggerSelector and define what you actually want to do...
        # Todo triggerdelays, etc etc.
        trigger_mode = (sdk.TriggerModeEnum.On
                        if enable else sdk.TriggerModeEnum.Off)
        result, _ = self.ctrl_transport.set(trigger_mode, sdk.TriggerMode)
        ext_trig = (result == sdk.TriggerModeEnum.On)
        self._set_formatted_keyword("EXTTRIG", ext_trig)
        self.get_fps()
        return ext_trig
