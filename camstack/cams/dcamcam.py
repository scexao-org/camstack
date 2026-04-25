from __future__ import annotations
import typing as typ

import os
import logging as logg

from camstack.cams.params_shm_backend import ParamsSHMCamera, CommandTransport
from camstack.core import utilities as util

from hwmain.dcam import dcamprop

from camstack.core.wcs import wcs_dict_init


class CommandTransportForDCAM(CommandTransport[int]):

    # Params SHM key mask to define get vs. set
    # Need to check the selected mask has no conflict with any parameter key
    PARAMS_SHM_GET_MAGIC = 0x8000_0000
    # Arbitrary MAGIC number
    # encodes a "Invalid property" returned from the framegrab process
    PARAMS_SHM_INVALID_MAGIC = -8.0085

    # def to_fits_val(self, api_key: int, value: float):
    # Unecessary: happy with the superclass.

    def to_format_val(self, api_key: int, value: float):
        '''
        Bind the returned raw floats into dcamprop enums if possible
        '''

        if (api_key in dcamprop.PROP_ENUM_MAP and value is not None and
                    value != self.PARAMS_SHM_INVALID_MAGIC):
            # Response type of requested prop is described by a proper enumeration.
            # Instantiate the Enum class for the return value.
            return dcamprop.PROP_ENUM_MAP[api_key](value)  # type: ignore

        return value

    if typ.TYPE_CHECKING:
        from pyMilk.interfacing.shm import KWType

    def getter_request_to_k_v_c(self, api_key: int) -> tuple[str, KWType, str]:
        return f"{api_key | self.PARAMS_SHM_GET_MAGIC:08x}", 0.0, ''

    def setter_request_to_k_v_c(self, api_key: int,
                                value: typ.Any) -> tuple[str, KWType, str]:
        return f"{api_key:08x}", float(value), ''

    def kvc_to_transport_return_vals(self, kw_key: str, value: KWType,
                                     comment: str) -> float:
        # For this transport, we ENFORCE kwtype is always a float.
        return value  # type: ignore


class DCAMCamera(ParamsSHMCamera):

    INTERACTIVE_SHELL_METHODS = [] + ParamsSHMCamera.INTERACTIVE_SHELL_METHODS

    MODES = {}

    KEYWORDS = {}
    KEYWORDS.update(ParamsSHMCamera.KEYWORDS)

    CLS_SHM_COMMUNICATOR = CommandTransportForDCAM

    IS_WATER_COOLED = False  # Amend in subclasses.

    def __init__(
            self,
            name: str,
            stream_name: str,
            mode_id: util.Typ_mode_id_or_heightwidth,
            dcam_number: int,
            no_start: bool = False,
            taker_cset_prio: util.Typ_tuple_cset_prio = ("system", None),
            dependent_processes: list[util.DependentProcess] = [],
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
            mode_id: None | util.Typ_mode_id = None,
            params_injection: None | dict[dcamprop.EProp, int | float] = None,
    ) -> None:

        logg.debug("prepare_camera_for_size @ DCAMCamera")

        super().prepare_camera_for_size(mode_id=mode_id)

        x0, x1 = self.current_mode.x0, self.current_mode.x1
        y0, y1 = self.current_mode.y0, self.current_mode.y1

        params: dict[dcamprop.EProp, int | float] = {
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

        api_keys, values = [], []
        for k, v in params.items():
            api_keys += [k]
            values += [
                    v
            ]  # force float cast -> Now impl in setter_request_to_k_v_c

        self.ctrl_transport.setmulti_nofeedback_nosync(values, api_keys)

    def abort_exposure(self, injected_tint: float = 0.1) -> None:
        # Basically restart the stack. Hacky way to abort a very long exposure.
        # This will kill the fgrab process, and re-init
        # We're reinjecting a short exposure time to reset a potentially very long exposure mode.

        # This is a faster version of the intended:
        # self.set_camera_mode(self.current_mode_id)

        with self.ctrl_transport.control_shm_lock:
            self._kill_taker_no_dependents()
            self.prepare_camera_for_size(
                    self.current_mode_id, params_injection={
                            dcamprop.EProp.EXPOSURETIME: injected_tint
                    })
            self._start_taker_no_dependents(reuse_shm=True)

    def _prepare_backend_cmdline(self, reuse_shm: bool = False) -> None:

        # Prepare the cmdline for starting up!
        exec_path = os.environ["SCEXAO_HW"] + "/bin/hwacq-dcamtake"
        self.taker_tmux_command = (f"{exec_path} -s {self.STREAMNAME} "
                                   f"-u {self.dcam_number} -l 0 -N 4")
        if reuse_shm:
            self.taker_tmux_command += " -R"  # Do not overwrite the SHM.


class OrcaQuest(DCAMCamera):

    WFS, FPWFS, JEN = 'WFS', 'FPWFS', 'JEN'
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
            WFS: util.CameraMode(x0=1592, x1=2391, y0=1060, y1=1243, tint=0.0005),      # WFSing mode for visible WFS
            FPWFS: util.CameraMode(x0=1352, x1=2127, y0=944, y1=1119, tint=0.0001),    # FPWFSing mode for visible WFS
            0: util.CameraMode(x0=0, x1=4095, y0=0, y1=2303, tint=0.001),             # Also full
            1: util.CameraMode(x0=1024, x1=3071, y0=576, y1=1727, tint=0.001),        # 1/2 of the full frame
            2: util.CameraMode(x0=1536, x1=2559, y0=864, y1=1439, tint=0.001),        # 1/4 of the full frame
            3: util.CameraMode(x0=1792, x1=2303, y0=1048, y1=1295, tint=0.001),       # 1/8 of the full frame
            JEN: util.CameraMode(x0=1804, x1=2315, y0=796, y1=1307, tint=0.001),    # Jen is using for focal plane mode
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
            dependent_processes: list[util.DependentProcess] = [],
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
        self._set_formatted_keyword(
                'GAIN',
                self.ctrl_transport.get(
                        dcamprop.EProp.CONVERSIONFACTOR_COEFF)[1])

        self._set_formatted_keyword(
                'DETBIAS',
                self.ctrl_transport.get(
                        dcamprop.EProp.CONVERSIONFACTOR_OFFSET)[1])

    def poll_camera_for_keywords(self) -> None:
        self.get_temperature()

    def get_temperature(self) -> float:
        # Let's try and play: it's readonly
        # but should trigger the cam calling back home
        temp_C, _ = self.ctrl_transport.get(dcamprop.EProp.SENSORTEMPERATURE)
        temp_K = temp_C + 273.15
        # convert celsius to kelvin
        self._set_formatted_keyword("DET-TMP", temp_K)
        logg.info(f"get_temperature {temp_K} K")
        return temp_K

    # And now we fill up... FAN, LIQUID

    def get_tint(self) -> float:
        val, val_fits = self.ctrl_transport.get(dcamprop.EProp.EXPOSURETIME)
        self._set_formatted_keyword("EXPTIME", val_fits)
        logg.info(f"get_tint {val}")
        return val

    def set_tint(self, tint: float) -> float:
        tint, tint_fits = self.ctrl_transport.set(tint,
                                                  dcamprop.EProp.EXPOSURETIME)
        self._set_formatted_keyword("EXPTIME", tint_fits)
        # update FRATE and EXPTIME
        self.get_fps()
        return tint

    def get_fps(self) -> float:
        (tint, tint_fits), (read_time,
                            _), (ext_trig, _) = self.ctrl_transport.getmulti([
                                    dcamprop.EProp.EXPOSURETIME,
                                    dcamprop.EProp.TIMING_READOUTTIME,
                                    dcamprop.EProp.TRIGGERSOURCE
                            ], )
        if ext_trig == dcamprop.ETriggerSource.INTERNAL:
            fps = 1 / max(tint, read_time)
        else:
            # Rolling shutter for the currently used trigger mode. FIXME when we deploy continuous external trigger mode.
            fps = 1 / (tint + read_time)
        self._set_formatted_keyword("EXPTIME", tint_fits)
        self._set_formatted_keyword("FRATE", fps)
        logg.info(f"get_fps {fps}")
        return fps

    def set_fps(self, fps: float) -> float:
        self.set_tint(1 / fps)
        return self.get_fps()

    def get_maxfps(self) -> float:
        fps = 1 / self.ctrl_transport.get(dcamprop.EProp.TIMING_READOUTTIME)[0]
        logg.info(f"get_maxfps {fps}")
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
        with self.ctrl_transport.control_shm_lock:
            self._kill_taker_no_dependents()
            self.prepare_camera_for_size(params_injection={
                    dcamprop.EProp.READOUTSPEED: readmode,
            })
            self._start_taker_no_dependents(reuse_shm=True)

    def get_readout_mode(self) -> str:
        readmode, _ = self.ctrl_transport.get(dcamprop.EProp.READOUTSPEED)
        if readmode == dcamprop.EReadoutSpeed.READOUT_ULTRAQUIET:
            mode = "SLOW"
        elif readmode == dcamprop.EReadoutSpeed.READOUT_FAST:
            mode = "FAST"
        else:
            # should never get here
            mode = "Unknown"
        return mode

    def get_external_trigger(self) -> bool:
        val = (self.ctrl_transport.get(dcamprop.EProp.TRIGGERSOURCE)[0] ==
               dcamprop.ETriggerSource.EXTERNAL)
        self._set_formatted_keyword("EXTTRIG", val)
        return val

    def set_external_trigger(self, enable: bool) -> bool:
        if enable:
            logg.debug(f"Enabling external trigger.")
            # Enable the internal trigger
            result = self.ctrl_transport.set(
                    dcamprop.ETriggerSource.EXTERNAL,
                    dcamprop.EProp.TRIGGERSOURCE,
            )[0]
        else:
            logg.debug("Disabling external trigger.")
            result = self.ctrl_transport.set(
                    dcamprop.ETriggerSource.INTERNAL,
                    dcamprop.EProp.TRIGGERSOURCE,
            )[0]

        ext_trig = result == dcamprop.ETriggerSource.EXTERNAL
        self._set_formatted_keyword("EXTTRIG", ext_trig)
        self.get_fps()  # fps has to be refreshed after changing trigger mode.
        return ext_trig

    def set_output_trigger_options(self, kind: str, polarity: str,
                                   num: int = 1) -> list[float]:
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

        ret = self.ctrl_transport.setmulti(
                [kind_val, pol_val],
                [
                        dcamprop.EProp.OUTPUTTRIGGER_KIND + key_offset,
                        dcamprop.EProp.OUTPUTTRIGGER_POLARITY + key_offset,
                ],
        )

        return [
                v[0] for v in ret
        ]  # extract formatted value from (formatted_value, fits_value) of ret

    def get_cooler_mode(self):
        value = self.ctrl_transport.get(dcamprop.EProp.SENSORCOOLER)
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
        self.ctrl_transport.set(prop, dcamprop.EProp.SENSORCOOLER)


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
