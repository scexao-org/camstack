from __future__ import annotations

import typing as typ

import os
import struct  # for pack, unpack
import logging as logg

from camstack.cams.params_shm_backend import ParamsSHMCamera, CommandTransport
from camstack.core import utilities as util

from hwmain.teledyne import pvcam


class CommandTransportForPVCAM(CommandTransport[int]):

    # Params SHM key mask to define get vs. set
    # Need to check the selected mask has no conflict with any parameter key
    PARAMS_SHM_GET_MAGIC = 0x8000_0000
    # Arbitrary MAGIC number
    # encodes a "Invalid property" returned from the framegrab process
    PARAMS_SHM_INVALID_MAGIC = 123

    def to_fits_val(self, api_key: int, value: int | float):
        # Performing a byte-level interpret cast
        key_to_cast_from: str = 'd' if type(value) is float else 'q'
        key_to_cast_to: str | None = pvcam.STRUCT_KEY_DICT[
                pvcam.extract_type_byte(api_key)]

        if key_to_cast_to is None:
            raise ValueError(
                    f'{key_to_cast_from=}; {key_to_cast_to=} - Illegal state.')

        value_reinterpret = struct.unpack(key_to_cast_to,\
                              struct.pack(key_to_cast_from, value))[0]

        return value_reinterpret

    def to_format_val(self, api_key: int, value: int | float):
        value_reinterpret = self.to_fits_val(api_key, value)

        if (api_key in pvcam.PROP_ENUM_MAP and value_reinterpret is not None and
                    value_reinterpret != self.PARAMS_SHM_INVALID_MAGIC):
            return pvcam.PROP_ENUM_MAP[api_key](value_reinterpret)

        return value_reinterpret

    if typ.TYPE_CHECKING:
        from pyMilk.interfacing.shm import KWType

    def getter_request_to_k_v_c(self, api_key: int) -> tuple[str, KWType, str]:
        return f"{api_key | self.PARAMS_SHM_GET_MAGIC:08x}", 0, ''

    def setter_request_to_k_v_c(self, api_key: int,
                                value: typ.Any) -> tuple[str, KWType, str]:
        # PARAMS for PVCAM are gonna be longs, not floats
        return f"{api_key:08x}", int(value), ''

    def kvc_to_transport_return_vals(self, kw_key: str, value: KWType,
                                     comment: str) -> float:
        # For this transport, we ENFORCE kwtype is always a float.
        return value  # type: ignore


class PVCAMCamera(ParamsSHMCamera):

    INTERACTIVE_SHELL_METHODS = [] + ParamsSHMCamera.INTERACTIVE_SHELL_METHODS

    MODES = {}

    KEYWORDS = {}
    KEYWORDS.update(ParamsSHMCamera.KEYWORDS)

    CLS_SHM_COMMUNICATOR = CommandTransportForPVCAM

    def __init__(
            self,
            name: str,
            stream_name: str,
            mode_id: util.Typ_mode_id_or_heightwidth,
            pvcam_number: int,
            no_start: bool = False,
            taker_cset_prio: util.Typ_tuple_cset_prio = ("system", None),
            dependent_processes: typ.List[util.DependentProcess] = [],
    ) -> None:

        # Do basic stuff
        self.pvcam_number = pvcam_number
        super().__init__(
                name,
                stream_name,
                mode_id,
                no_start=no_start,
                taker_cset_prio=taker_cset_prio,
                dependent_processes=dependent_processes,
        )

    if typ.TYPE_CHECKING:
        T_params_inj = dict[int, int]

    def prepare_camera_for_size(
            self,
            mode_id: util.Typ_mode_id | None = None,
            params_injection: T_params_inj | None = None,
    ) -> None:

        logg.debug("prepare_camera_for_size @ DCAMCamera")

        super().prepare_camera_for_size(mode_id=None)

        cm = self.current_mode
        '''
        Added parameters that are NOT SDK features
        But are considered for acquisition setup and start in pvcamtake.cpp
        pvcam.PARAMMAGIC_EXP_TIME
        pvcam.PARAMMAGIC_ROI_X0
        pvcam.PARAMMAGIC_ROI_X1
        pvcam.PARAMMAGIC_ROI_BINX
        pvcam.PARAMMAGIC_ROI_Y0
        pvcam.PARAMMAGIC_ROI_Y1
        pvcam.PARAMMAGIC_ROI_BINY
        '''

        params: typ.Dict[int, int] = {
                pvcam.PARAMMAGIC_ROI_X0: cm.x0,
                pvcam.PARAMMAGIC_ROI_X1: cm.x1,
                pvcam.PARAMMAGIC_ROI_BINX: cm.binx,
                pvcam.PARAMMAGIC_ROI_Y0: cm.y0,
                pvcam.PARAMMAGIC_ROI_Y1: cm.y1,
                pvcam.PARAMMAGIC_ROI_BINY: cm.biny,
                pvcam.PARAM_EXP_RES: pvcam.EN_EXP_RES.ONE_MICROSEC,
                pvcam.PARAM_SPDTAB_INDEX: 1,  # 100 Mhz Mode
                pvcam.PARAM_GAIN_INDEX: 1  # HDR mode
        }

        if cm.tint is not None:
            params[pvcam.PARAMMAGIC_EXP_TIME] = int(cm.tint * 1e6)

        # Additional parameters for custom calls
        # Designed for e.g. dcamprop.EProp.READOUTSPEED
        # which requires restarting the acquisition
        # This way we can work this out without a full call to set_camera_mode in the base class
        # and avoiding restarting all dependent processes.
        if params_injection is not None:
            params.update(params_injection)

        api_keys, values = [], []
        for k, v in params.items():
            api_keys += [k]
            values += [v]

        self.ctrl_transport.setmulti_nofeedback_nosync(values, api_keys)

    def _prepare_backend_cmdline(self, reuse_shm: bool = False) -> None:

        # Prepare the cmdline for starting up!
        exec_path = os.environ["SCEXAO_HW"] + "/bin/hwacq-pvcamtake"
        self.taker_tmux_command = (f"{exec_path} -s {self.STREAMNAME} "
                                   f"-u {self.pvcam_number} -l 0 -N 4")
        if reuse_shm:
            self.taker_tmux_command += " -R"  # Do not overwrite the SHM.


class JensPrimeBSI(PVCAMCamera):
    INTERACTIVE_SHELL_METHODS = [
            'FULL', 'HALF', 'FULLBIN', 'get_tint', 'set_tint', 'get_temperature'
    ] + PVCAMCamera.INTERACTIVE_SHELL_METHODS

    FULL, HALF, FULLBIN = 'FULL', 'HALF', 'FULLBIN'

    MODES = {
            FULL:
                    util.CameraMode(x0=0, x1=2047, y0=0, y1=2047, tint=0.01),
            HALF:
                    util.CameraMode(x0=512, x1=1535, y0=512, y1=1535,
                                    tint=0.01),
            # WARNING: x1, y1 in unbinned pixels!
            # This might be a different convention from other cams.
            FULLBIN:
                    util.CameraMode(x0=0, x1=2047, y0=0, y1=2047, binx=2,
                                    biny=2, tint=0.01),
    }

    KEYWORDS = {}
    KEYWORDS.update(PVCAMCamera.KEYWORDS)

    def _fill_keywords(self) -> None:
        super()._fill_keywords()

        # Override detector name
        self._set_formatted_keyword("DETECTOR", "Prime BSI")
        self._set_formatted_keyword(
                "CROPPED", self.current_mode_id
                not in (self.FULL, self.FULLBIN))
        self._set_formatted_keyword('DETPXSZ1', 0.0065)
        self._set_formatted_keyword('DETPXSZ2', 0.0065)

        # Detector specs from instruction manual
        # TODO GAIN?
        # TODO BIAS?

    def get_tint(self) -> float:
        val_fmt, val_fits = self.ctrl_transport.get(pvcam.PARAMMAGIC_EXP_TIME)
        self._set_formatted_keyword("EXPTIME", val_fits / 1e6)
        logg.info(f"get_tint {val_fmt / 1e6}")
        return val_fmt / 1e6

    def set_tint(self, tint: float) -> float:
        val_fmt, val_fits = self.ctrl_transport.set(int(tint * 1e6),
                                                    pvcam.PARAMMAGIC_EXP_TIME)
        self._set_formatted_keyword("EXPTIME", val_fits / 1e6)
        logg.info(f"get_tint {val_fmt / 1e6}")
        return val_fmt / 1e6

    def get_temperature(self) -> float:
        # Let's try and play: it's readonly
        # but should trigger the cam calling back home
        temp_C = self.ctrl_transport.get(pvcam.PARAM_TEMP)[0] / 100.
        temp_K = temp_C + 273.15
        # convert celsius to kelvin
        self._set_formatted_keyword("DET-TMP", temp_K)
        logg.info(f"get_temperature {temp_K} K")
        return temp_K

    def get_temperature_setpoint(self) -> float:
        temp_C = self.ctrl_transport.get(pvcam.PARAM_TEMP_SETPOINT)[0] / 100.
        return temp_C + 273.15

    def set_temperature_setpoint(self, temp_C: float) -> float:
        # Tested: -35C to +5C
        temp_C_fmt = self.ctrl_transport.set(int(
                temp_C * 100), pvcam.PARAM_TEMP_SETPOINT)[0] / 100.
        return temp_C + 273.15

    def get_fan_speed(self) -> pvcam.EN_FAN_SPEED:
        return self.ctrl_transport.get(pvcam.PARAM_FAN_SPEED_SETPOINT)[0]

    def set_fan_speed(self, speed: pvcam.EN_FAN_SPEED) -> pvcam.EN_FAN_SPEED:
        return self.ctrl_transport.set(speed, pvcam.PARAM_FAN_SPEED_SETPOINT)[0]
