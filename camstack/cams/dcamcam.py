from typing import Union, Tuple, List, Any, Optional as Op, Dict

import os
import logging as logg

from camstack.cams.params_shm_backend import ParamsSHMCamera
from camstack.core import utilities as util

from hwmain.dcam import dcamprop

from pyMilk.interfacing.shm import SHM
import numpy as np

from camstack.core.wcs import wcs_dict_init


class DCAMCamera(ParamsSHMCamera):

    INTERACTIVE_SHELL_METHODS = [] + ParamsSHMCamera.INTERACTIVE_SHELL_METHODS

    MODES = {}

    KEYWORDS = {}
    KEYWORDS.update(ParamsSHMCamera.KEYWORDS)

    PARAMS_SHM_GET_MAGIC = 0x8000_0000
    PARAMS_SHM_INVALID_MAGIC = -8.0085

    IS_WATER_COOLED = False  # Amend in subclasses.

    def __init__(
            self,
            name: str,
            stream_name: str,
            mode_id: util.Typ_mode_id_or_heightwidth,
            dcam_number: int,
            no_start: bool = False,
            taker_cset_prio: util.Typ_tuple_cset_prio = ("system", None),
            dependent_processes: List[util.DependentProcess] = [],
    ) -> None:

        # Do basic stuff
        self.dcam_number = dcam_number
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
            mode_id: Op[util.Typ_mode_id] = None,
            params_injection: Op[Dict[dcamprop.EProp, Union[int,
                                                            float]]] = None,
    ) -> None:
        assert self.control_shm is not None

        logg.debug("prepare_camera_for_size @ DCAMCamera")

        super().prepare_camera_for_size(mode_id=None)

        x0, x1 = self.current_mode.x0, self.current_mode.x1
        y0, y1 = self.current_mode.y0, self.current_mode.y1

        params: Dict[dcamprop.EProp, Union[int, float]] = {
                dcamprop.EProp.SUBARRAYHPOS:
                        x0,
                dcamprop.EProp.SUBARRAYVPOS:
                        y0,
                dcamprop.EProp.SUBARRAYHSIZE:
                        x1 - x0 + 1,
                dcamprop.EProp.SUBARRAYVSIZE:
                        y1 - y0 + 1,
                dcamprop.EProp.SUBARRAYMODE:
                        dcamprop.ESubArrayMode.ON,
                # Set up some sensible triggering defaults
                dcamprop.EProp.TRIGGERACTIVE:
                        dcamprop.ETriggerActive.EDGE,
                dcamprop.EProp.TRIGGERPOLARITY:
                        dcamprop.ETriggerPolarity.POSITIVE,
                # default output trigger is channel 1
                dcamprop.EProp.OUTPUTTRIGGER_KIND:
                        dcamprop.EOutputTriggerKind.TRIGGERREADY,
                dcamprop.EProp.OUTPUTTRIGGER_POLARITY:
                        dcamprop.EOutputTriggerPolarity.POSITIVE,
        }

        if self.IS_WATER_COOLED:
            # Cooling to da max.
            # OK in water cooling
            # Send a DCAMERR Invalid Property in air cooling.
            # DCAMERRS are fatal in dcamtake.c in setup phase, nonfatal after.
            params[dcamprop.EProp.SENSORCOOLER] = dcamprop.ESensorCooler.MAX

        # Additional parameters for custom calls
        # Designed for e.g. dcamprop.EProp.READOUTSPEED
        # which requires restarting the acquisition
        # This way we can work this out without a full call to set_camera_mode in the base class
        # and avoiding restarting all dependent processes.
        if params_injection is not None:
            params.update(params_injection)

        if self.current_mode.tint is not None:
            params[dcamprop.EProp.EXPOSURETIME] = self.current_mode.tint

        # Convert int keys into hexstrings
        # dcam values require FLOATS - we'll multiply everything by 1.0

        # FIXME Why not call a set_prm_multivalue???
        # There's something with the taker not implementing the
        # triple-semaphore-click feedback at this point yet.
        dump_params = {f"{k:08x}": 1.0 * params[k] for k in params}

        self.control_shm.reset_keywords(dump_params)
        self.control_shm.set_data(self.control_shm.get_data() * 0 + len(params))
        while self.control_shm.check_sem_trywait(
        ):  # semflush the post we just made.
            pass

    def abort_exposure(self) -> None:
        # Basically restart the stack. Hacky way to abort a very long exposure.
        # This will kill the fgrab process, and re-init
        # We're reinjecting a short exposure time to reset a potentially very long exposure mode.

        # This is a faster version of the intended:
        # self.set_camera_mode(self.current_mode_id)

        with self.control_shm_lock:
            self._kill_taker_no_dependents()
            self.prepare_camera_for_size(
                    self.current_mode_id,
                    params_injection={dcamprop.EProp.EXPOSURETIME: 0.1})
            self._start_taker_no_dependents(reuse_shm=True)

    def _prepare_backend_cmdline(self, reuse_shm: bool = False) -> None:

        # Prepare the cmdline for starting up!
        exec_path = os.environ["SCEXAO_HW"] + "/bin/hwacq-dcamtake"
        self.taker_tmux_command = (f"{exec_path} -s {self.STREAMNAME} "
                                   f"-u {self.dcam_number} -l 0 -N 4")
        if reuse_shm:
            self.taker_tmux_command += " -R"  # Do not overwrite the SHM.

    # def _params_shm_return_raw_to_fits_val(self, api_key: int, value: float):
    # Unecessary: happy with the superclass.

    def _params_shm_return_raw_to_format_val(self, dcam_key: int, value: float):
        if (dcam_key in dcamprop.PROP_ENUM_MAP and value is not None and
                    value != self.PARAMS_SHM_INVALID_MAGIC):
            # Response type of requested prop is described by a proper enumeration.
            # Instantiate the Enum class for the return value.
            new_value = dcamprop.PROP_ENUM_MAP[dcam_key](value)
        else:
            new_value = value
        return new_value


class OrcaQuest(DCAMCamera):

    WFS, FPWFS = 'WFS', 'FPWFS'
    FIRST, FULL, FIRSTPL, FIRSTPLSMF, DICHROIC = 'FIRST', 'FULL', 'FIRSTPL', 'FIRSTPLSMF', 'DICHROIC'

    INTERACTIVE_SHELL_METHODS = [
            FIRST,
            FULL,
            FIRSTPL,
            WFS,
            FPWFS,
            FIRSTPLSMF,
            "set_tint",
            "get_tint",
            "get_temperature",
            "set_readout_mode",
            "set_external_trigger",
    ] + DCAMCamera.INTERACTIVE_SHELL_METHODS

    # yapf: disable
    MODES = {
            FIRST: util.CameraMode(x0=0, x1=2795, y0=4, y1=1663, tint=0.001),
            FULL: util.CameraMode(x0=0, x1=4095, y0=0, y1=2103, tint=0.001),
            FIRSTPL: util.CameraMode(x0=1500, x1=3395, y0=1572, y1=1983, tint=0.001),
            FIRSTPLSMF: util.CameraMode(x0=1000, x1=2895, y0=1752, y1=1895, tint=0.001),
            0: util.CameraMode(x0=0, x1=4095, y0=0, y1=2303, tint=0.001),  # Also full
            WFS: util.CameraMode(x0=1380, x1=2079, y0=960, y1=1087, tint=0.001),    # 4 planes
            2: util.CameraMode(x0=1592, x1=1891, y0=960, y1=1087, tint=0.001),      # 2 planes
            3: util.CameraMode(x0=1924, x1=2723, y0=1244, y1=1443, tint=0.001),
            FPWFS: util.CameraMode(x0=1804, x1=2315, y0=796, y1=1307, tint=0.001),    # Jen is using for focal plane mode
    }
    # yapf: enable

    KEYWORDS = {}
    KEYWORDS.update(DCAMCamera.KEYWORDS)

    IS_WATER_COOLED = False

    def __init__(
            self,
            name: str,
            stream_name: str,
            mode_id: util.Typ_mode_id_or_heightwidth,
            dcam_number: int,
            no_start: bool = False,
            taker_cset_prio: util.Typ_tuple_cset_prio = ("system", None),
            dependent_processes: List[util.DependentProcess] = [],
    ) -> None:
        super().__init__(
                name,
                stream_name,
                mode_id,
                dcam_number,
                no_start=no_start,
                taker_cset_prio=taker_cset_prio,
                dependent_processes=dependent_processes,
        )

    def _fill_keywords(self) -> None:
        super()._fill_keywords()

        # Override detector name
        self._set_formatted_keyword("DETECTOR", "Orca Quest")
        self._set_formatted_keyword("CROPPED", self.current_mode_id
                                    != self.FULL)
        # pixel pitch is 4.6 micron
        self._set_formatted_keyword("DETPXSZ1", 0.0046)
        self._set_formatted_keyword("DETPXSZ2", 0.0046)

        # Detector specs from instruction manual
        self._prm_getvalue("GAIN", dcamprop.EProp.CONVERSIONFACTOR_COEFF)
        self._prm_getvalue("DET-BIAS", dcamprop.EProp.CONVERSIONFACTOR_OFFSET)

    def poll_camera_for_keywords(self) -> None:
        self.get_temperature()

    def get_temperature(self) -> float:
        # Let's try and play: it's readonly
        # but should trigger the cam calling back home
        temp_C = self._prm_getvalue(None, dcamprop.EProp.SENSORTEMPERATURE)
        temp_K = temp_C + 273.15
        # convert celsius to kelvin
        self._set_formatted_keyword("DET-TMP", temp_K)
        logg.info(f"get_temperature {temp_K} K")
        return temp_K

    # And now we fill up... FAN, LIQUID

    def get_tint(self) -> float:
        val = self._prm_getvalue("EXPTIME", dcamprop.EProp.EXPOSURETIME)
        logg.info(f"get_tint {val}")
        return val

    def set_tint(self, tint: float) -> float:
        tint = self._prm_setvalue(float(tint), "EXPTIME",
                                  dcamprop.EProp.EXPOSURETIME)
        # update FRATE and EXPTIME
        self.get_fps()
        return tint

    def get_fps(self) -> float:
        exp_time, read_time, ext_trig = self._prm_getmultivalue(
                ["EXPTIME", None, None],
                [
                        dcamprop.EProp.EXPOSURETIME,
                        dcamprop.EProp.TIMING_READOUTTIME,
                        dcamprop.EProp.TRIGGERSOURCE
                ],
        )
        if ext_trig == dcamprop.ETriggerSource.INTERNAL:
            fps = 1 / max(exp_time, read_time)
        else:
            fps = 1 / (
                    exp_time + read_time
            )  # Rolling shutter for the currently used trigger mode. FIXME when we deploy continuous external trigger mode.
        self._set_formatted_keyword("FRATE", fps)
        logg.info(f"get_fps {fps}")
        return fps

    def set_fps(self, fps: float) -> float:
        self.set_tint(1 / fps)
        return self.get_fps()

    def get_maxfps(self) -> float:
        fps = 1 / self._prm_getvalue(None, dcamprop.EProp.TIMING_READOUTTIME)
        logg.info(f"get_fps {fps}")
        return fps

    def set_readout_mode(self, mode: str) -> None:
        logg.debug("set_readout_mode @ OrcaQuest")
        mode = mode.upper()
        curr_mode = self.get_readout_mode().upper()
        # if we're already in that read mode, don't do anything!
        if mode == curr_mode:
            logg.debug(f"Already using readout mode {mode}; doing nothing")
            return

        if mode == "SLOW":
            readmode = dcamprop.EReadoutSpeed.READOUT_ULTRAQUIET
        elif mode == "FAST":
            readmode = dcamprop.EReadoutSpeed.READOUT_FAST
        else:
            raise ValueError(f"Unrecognized readout mode: {mode}")

        # preserve trigger mode
        with self.control_shm_lock:
            self._kill_taker_no_dependents()
            self.prepare_camera_for_size(params_injection={
                    dcamprop.EProp.READOUTSPEED: readmode,
            })
            self._start_taker_no_dependents(reuse_shm=True)

    def get_readout_mode(self) -> str:
        readmode = self._prm_getvalue(None, dcamprop.EProp.READOUTSPEED)
        if readmode == dcamprop.EReadoutSpeed.READOUT_ULTRAQUIET:
            mode = "SLOW"
        elif readmode == dcamprop.EReadoutSpeed.READOUT_FAST:
            mode = "FAST"
        else:
            # should never get here
            mode = "Unknown"
        return mode

    def get_external_trigger(self) -> bool:
        val = (self._prm_getvalue(None, dcamprop.EProp.TRIGGERSOURCE) ==
               dcamprop.ETriggerSource.EXTERNAL)
        self._set_formatted_keyword("EXTTRIG", val)
        return val

    def set_external_trigger(self, enable: bool) -> bool:
        if enable:
            logg.debug(f"Enabling external trigger.")
            # Enable the internal trigger
            result = self._prm_setvalue(
                    float(dcamprop.ETriggerSource.EXTERNAL),
                    None,
                    dcamprop.EProp.TRIGGERSOURCE,
            )
        else:
            logg.debug("Disabling external trigger.")
            result = self._prm_setvalue(
                    float(dcamprop.ETriggerSource.INTERNAL),
                    None,
                    dcamprop.EProp.TRIGGERSOURCE,
            )

        ext_trig = result == dcamprop.ETriggerSource.EXTERNAL
        self._set_formatted_keyword("EXTTRIG", ext_trig)
        self.get_fps()  # fps has to be refreshed after changing trigger mode.
        return ext_trig

    def set_output_trigger_options(self, kind: str, polarity: str,
                                   num: int = 1) -> List[float]:
        if num < 1 or num > 3:
            raise ValueError(
                    f"Output trigger number must be between 1 and 3 (got {num})"
            )

        key_offset = dcamprop.EProp._OUTPUTTRIGGER * (num - 1)

        if kind == "low":
            kind_val = dcamprop.EOutputTriggerKind.LOW
        elif kind == "high":
            kind_val = dcamprop.EOutputTriggerKind.HIGH
        elif kind == "exposure":
            kind_val = dcamprop.EOutputTriggerKind.EXPOSURE
        elif kind == "trigger":
            kind_val = dcamprop.EOutputTriggerKind.TRIGGERREADY
        elif kind == "anyexposure":
            kind_val = dcamprop.EOutputTriggerKind.ANYROWEXPOSURE
        else:
            raise ValueError("Output trigger kind not recognized.")

        if polarity == "low":
            pol_val = dcamprop.EOutputTriggerPolarity.NEGATIVE
        elif polarity == "high":
            pol_val = dcamprop.EOutputTriggerPolarity.POSITIVE
        else:
            raise ValueError("Output trigger polarity not recognized.")

        return self._prm_setmultivalue(
                list(map(float, (kind_val, pol_val))),
                [None, None],
                [
                        dcamprop.EProp.OUTPUTTRIGGER_KIND + key_offset,
                        dcamprop.EProp.OUTPUTTRIGGER_POLARITY + key_offset,
                ],
        )

    def get_cooler_mode(self):
        value = self._prm_getvalue(None, dcamprop.EProp.SENSORCOOLER)
        if value == dcamprop.ESensorCooler.OFF:
            return "OFF"
        elif value == dcamprop.ESensorCooler.ON:
            return "ON"
        elif value == dcamprop.ESensorCooler.MAX:
            return "MAX"
        else:
            return "UNKNOWN"

    def set_cooler_mode(self, mode: str):
        mode = mode.upper()
        if mode == "OFF":
            prop = dcamprop.ESensorCooler.OFF
        elif mode == "ON":
            prop = dcamprop.ESensorCooler.ON
        elif mode == "MAX":
            prop = dcamprop.ESensorCooler.MAX
        else:
            raise ValueError(f"Invalid cooling mode {mode}")

        logg.debug(f"Setting cooling mode to {mode}")
        self._prm_setvalue(float(prop), None, dcamprop.EProp.SENSORCOOLER)


class FIRSTOrcam(OrcaQuest):

    def _fill_keywords(self) -> None:
        super()._fill_keywords()

        # Override detector name
        self._set_formatted_keyword("DETECTOR", "FIRST - OrcaQ")


class AlalaOrcam(OrcaQuest):

    def _fill_keywords(self) -> None:
        super()._fill_keywords()

        # Override detector name
        self._set_formatted_keyword("DETECTOR", "ALALA - OrcaQ")
