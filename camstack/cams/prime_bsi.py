from __future__ import annotations

import typing as typ

import os
import struct  # for pack, unpack
import logging as logg

from camstack.cams.params_shm_backend import ParamsSHMCamera
from camstack.core import utilities as util

from hwmain.teledyne import pvcam


class PVCAMCamera(ParamsSHMCamera):

    INTERACTIVE_SHELL_METHODS = [] + ParamsSHMCamera.INTERACTIVE_SHELL_METHODS

    MODES = {}

    KEYWORDS = {}
    KEYWORDS.update(ParamsSHMCamera.KEYWORDS)

    PARAMS_SHM_GET_MAGIC = 0x8000_0000
    PARAMS_SHM_INVALID_MAGIC = 123

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
        T_params_inj = typ.Optional[typ.Dict[int, typ.Union[int, float]]]

    def prepare_camera_for_size(
            self,
            mode_id: typ.Optional[util.Typ_mode_id] = None,
            params_injection: T_params_inj = None,
    ) -> None:
        # TODO
        assert self.control_shm is not None

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

        # Hex format the keys
        dump_params = {f"{k:08x}": params[k] for k in params}

        # PARAMS for PVCAM are gonna be longs, not floats
        self.control_shm.reset_keywords(dump_params)
        self.control_shm.set_data(self.control_shm.get_data() * 0 + len(params))

    def _prepare_backend_cmdline(self, reuse_shm: bool = False) -> None:

        # Prepare the cmdline for starting up!
        exec_path = os.environ["SCEXAO_HW"] + "/bin/hwacq-pvcamtake"
        self.taker_tmux_command = (f"{exec_path} -s {self.STREAMNAME} "
                                   f"-u {self.pvcam_number} -l 0 -N 4")
        if reuse_shm:
            self.taker_tmux_command += " -R"  # Do not overwrite the SHM.

    def _params_shm_return_raw_to_fits_val(self, pvcam_key: int, value: float):
        key_to_cast_from: str = 'd' if type(value) is float else 'q'
        key_to_cast_to: str = pvcam.STRUCT_KEY_DICT[pvcam.extract_type_byte(
                pvcam_key)]
        value_reinterpret = struct.unpack(key_to_cast_to,
                                          struct.pack(key_to_cast_from,
                                                      value))[0]

        return value_reinterpret

    def _params_shm_return_raw_to_format_val(self, pvcam_key: int,
                                             value: float):
        value_reinterpret = self._params_shm_return_raw_to_fits_val(
                pvcam_key, value)

        if (pvcam_key in pvcam.PROP_ENUM_MAP and
                    value_reinterpret is not None and
                    value_reinterpret != self.PARAMS_SHM_INVALID_MAGIC):
            value_return = pvcam.PROP_ENUM_MAP[pvcam_key](value_reinterpret)
        else:
            value_return = value_reinterpret

        return value_return


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
        val = self._prm_getvalue("EXPTIME", pvcam.PARAMMAGIC_EXP_TIME) / 1e6
        logg.info(f"get_tint {val}")
        return val

    def set_tint(self, tint: float) -> float:
        tint = self._prm_setvalue(int(tint * 1e6), "EXPTIME",
                                  pvcam.PARAMMAGIC_EXP_TIME) / 1e6
        # update FRATE and EXPTIME
        return tint

    def get_temperature(self) -> float:
        # Let's try and play: it's readonly
        # but should trigger the cam calling back home
        temp_C = self._prm_getvalue(None, pvcam.PARAM_TEMP) / 100.
        temp_K = temp_C + 273.15
        # convert celsius to kelvin
        self._set_formatted_keyword("DET-TMP", temp_K)
        logg.info(f"get_temperature {temp_K} K")
        return temp_K

    def get_temperature_setpoint(self) -> float:
        temp_C = self._prm_getvalue(None, pvcam.PARAM_TEMP_SETPOINT) / 100.
        return temp_C + 273.15

    def set_temperature_setpoint(self, temp_C: float) -> float:
        # Tested: -35C to +5C
        temp_C = self._prm_setvalue(int(temp_C * 100), None,
                                    pvcam.PARAM_TEMP_SETPOINT) / 100.
        return temp_C + 273.15

    def get_fan_speed(self) -> pvcam.EN_FAN_SPEED:
        return self._prm_getvalue(None, pvcam.PARAM_FAN_SPEED_SETPOINT)

    def set_fan_speed(self, speed: pvcam.EN_FAN_SPEED) -> pvcam.EN_FAN_SPEED:
        return self._prm_setvalue(speed, None, pvcam.PARAM_FAN_SPEED_SETPOINT)
