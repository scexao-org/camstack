from typing import Union, Tuple, List, Any, Optional as Op, Dict

import os
import logging as logg

from camstack.cams.params_shm_backend import ParamsSHMCamera
from camstack.core import utilities as util

from hwmain.dcam import dcamprop

from pyMilk.interfacing.shm import SHM
import numpy as np

import time
import threading
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
            mode_id: util.ModeIDorHWType,
            dcam_number: int,
            no_start: bool = False,
            taker_cset_prio: util.CsetPrioType = ("system", None),
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
            mode_id: Op[util.ModeIDType] = None,
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

    def abort_exposure(self) -> None:
        # Basically restart the stack. Hacky way to abort a very long exposure.
        # This will kill the fgrab process, and re-init
        # We're reinjecting a short exposure time to reset a potentially very long exposure mode.

        # This is a faster version of the intended:
        # self.set_camera_mode(self.current_mode_id)

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

    INTERACTIVE_SHELL_METHODS = [
            "FIRST",
            "FULL",
            "FIRSTPL",
            "set_tint",
            "get_tint",
            "get_temperature",
            "set_readout_mode",
            "set_external_trigger",
    ] + DCAMCamera.INTERACTIVE_SHELL_METHODS

    FIRST, FULL, FIRSTPL, DICHROIC = 'FIRST', 'FULL', 'FIRSTPL', 'DICHROIC'
    # yapf: disable
    MODES = {
            FIRST: util.CameraMode(x0=0, x1=4095, y0=1004, y1=2303, tint=0.001),
            FULL: util.CameraMode(x0=0, x1=4095, y0=0, y1=2103, tint=0.001),
            FIRSTPL: util.CameraMode(x0=1500, x1=3395, y0=1580, y1=1983, tint=0.001),
            0: util.CameraMode(x0=0, x1=4095, y0=0, y1=2303, tint=0.001),  # Also full
            1: util.CameraMode(x0=1580, x1=2639, y0=1088, y1=1247, tint=0.001),    # Kyohoon is Using for WFS mode
            2: util.CameraMode(x0=800, x1=3295, y0=876, y1=1531, tint=0.001),      # Kyohoon is Using for WFS align
            3: util.CameraMode(x0=1924, x1=2723, y0=1244, y1=1443, tint=0.001),
            4: util.CameraMode(x0=2140, x1=2395, y0=832, y1=1087, tint=0.000001),    # Jen is using for focal plane mode
            DICHROIC: util.CameraMode(x0=2336, x1=3135, y0=0, y1=2303, tint=0.01), # Dichroic stack mode
    }
    # yapf: enable

    KEYWORDS = {}
    KEYWORDS.update(DCAMCamera.KEYWORDS)

    IS_WATER_COOLED = False

    def __init__(
            self,
            name: str,
            stream_name: str,
            mode_id: util.ModeIDorHWType,
            dcam_number: int,
            no_start: bool = False,
            taker_cset_prio: util.CsetPrioType = ("system", None),
            dependent_processes: List[util.DependentProcess] = [],
    ) -> None:

        self.readout_mode = "FAST"
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
        self._set_formatted_keyword("CROPPED",
                                    self.current_mode_id != self.FULL)
        # Detector specs from instruction manual
        self._prm_getvalue("GAIN", dcamprop.EProp.CONVERSIONFACTOR_COEFF)
        self._prm_getvalue("BIAS", dcamprop.EProp.CONVERSIONFACTOR_OFFSET)

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

    def get_maxfps(self) -> float:
        fps = 1 / self._prm_getvalue(None, dcamprop.EProp.TIMING_READOUTTIME)
        logg.info(f"get_fps {fps}")
        return fps

    def set_readout_mode(self, mode: str) -> None:
        logg.debug("set_readout_mode @ OrcaQuest")

        mode = mode.upper()
        # if we're already in that read mode, don't do anything!
        if mode == self.readout_mode:
            logg.debug(f"Already using readout mode {mode}; doing nothing")
            return

        if mode == "SLOW":
            readmode = dcamprop.EReadoutSpeed.READOUT_ULTRAQUIET
        elif mode == "FAST":
            readmode = dcamprop.EReadoutSpeed.READOUT_FAST
        else:
            raise ValueError(f"Unrecognized readout mode: {mode}")

        self.readout_mode = mode

        # preserve trigger mode
        self._kill_taker_no_dependents()
        self.prepare_camera_for_size(params_injection={
                dcamprop.EProp.READOUTSPEED: readmode,
        })

        self._start_taker_no_dependents(reuse_shm=True)
        # Are those two necessary in this context??? reuse_shm should cover.
        self.grab_shm_fill_keywords()
        self.prepare_camera_finalize()

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


class BaseVCAM(OrcaQuest):
    PLATE_SCALE = (-1.6717718901193757e-6, 1.6717718901193757e-6)  # deg / px
    PA_OFFSET = -41.323163723676146  # deg
    HOTSPOTS: Dict[str, Tuple[float, float]] = {}

    ## camera keywords
    KEYWORDS: Dict[str, Tuple[util.KWType, str, str, str]] = {
            # Format is name:
            #   (value,
            #    description,
            #    formatter,
            #    redis partial push key [5 chars] for per-camera KW)
            # ALSO SHM caps at 16 chars for strings. The %s formats here are (some) shorter than official ones.
            ## camera info and modes
            "U_CAMERA": (-1, "VAMPIRES camera number (1 or 2)", "%1d", "CAM"),
            "U_DETMOD": ("", "VAMPIRES detector readout mode (Fast/Slow)",
                         "%-16s", "DETMD"),
            ## Filters
            "FILTER01": ("", "Primary filter name", "%-16s", "FILT01"),
            "FILTER02": ("", "Secondary filter name", "%-16s", "FILT02"),
            ## QWP terms managed by QWP daemon
            "U_QWP1": (-1, "[deg] VAMPIRES QWP 1 polarization angle", "%16.3f",
                       "QWP1"),
            "U_QWP1": (-1, "[deg] VAMPIRES QWP 1 polarization angle", "%16.3f",
                       "QWP1"),
            "U_QWP1TH":
                    (-1, "[deg] VAMPIRES QWP 1 wheel theta", "%16.3f", "QWP1T"),
            "U_QWP2": (-1, "[deg] VAMPIRES QWP 1 polarization angle", "%16.3f",
                       "QWP2"),
            "U_QWP2TH":
                    (-1, "[deg] VAMPIRES QWP 2 wheel theta", "%16.3f", "QWP2T"),
            ## polarization terms managed by HWP daemon
            "RET-ANG1": (-1, "[deg] Polarization angle of first retarder plate",
                         "%20.2f", "RTAN1"),
            "RET-ANG2":
                    (-1, "[deg] Polarization angle of second retarder plate",
                     "%20.2f", "RTAN2"),
            "RET-POS1": (-1, "[deg] Stage angle of first retarder plate",
                         "%20.2f", "RTPS1"),
            "RET-POS2": (-1, "[deg] Stage angle of second retarder plate",
                         "%20.2f", "RTPS2"),
    }
    KEYWORDS.update(OrcaQuest.KEYWORDS)
    N_WCS = 4
    ## camera modes
    FULL, STANDARD, MBI, MBI_REDUCED, PUPIL = "FULL", "STANDARD", "MBI", "MBI_REDUCED", "PUPIL"
    MODES = {
            FULL: util.CameraMode(x0=0, x1=4095, y0=0, y1=2303, tint=0.001),
    }

    IS_WATER_COOLED = True  # Results in prepare_camera_for_size setting cooler to MAX.

    def set_readout_mode(self, mode: str) -> None:
        super().set_readout_mode(mode)
        self._set_formatted_keyword("U_DETMOD", mode.title())

    def _fill_keywords(self) -> None:
        super()._fill_keywords()
        self._set_formatted_keyword("U_DETMOD", self.readout_mode.title())
        cropped = self.current_mode_id != self.FULL
        self._set_formatted_keyword("CROPPED", cropped)
        self.get_fps()
        self.get_tint()

    def poll_camera_for_keywords(self) -> None:
        super().poll_camera_for_keywords()

        # Defaults
        filter01 = bs = "Unknown"
        dfl1 = dfl2 = "Open"
        hwp_stage = 0
        try:
            with self.RDB.pipeline() as pipe:
                pipe.hget('U_FILTER', 'value')
                pipe.hget('U_BS', 'value')
                pipe.hget('P_STGPS1', 'value')
                pipe.hget('P_STGPS2', 'value')
                pipe.hget('X_POLAR', 'value')
                pipe.hget('U_DIFFL1', 'value')
                pipe.hget('U_DIFFL2', 'value')
                filter01, bs, lp_stage, hwp_stage, scex_lp, dfl1, dfl2 = pipe.execute(
                )
        except:
            logg.error('REDIS unavailable @ _fill_keywords @ VCAM')

        self._set_formatted_keyword('FILTER01', filter01)

        ## determine observing mode from the following logic
        # if the PBS is in and the HWP is running, we're doing polarimetry
        polarimetry = bs.upper() == "PBS" and \
                      (np.abs(hwp_stage - 56) < 1 or \
                       np.abs(lp_stage - 55.2) < 1 or \
                       np.abs(lp_stage - 90) < 1 or
                       scex_lp.strip().upper() == "IN")
        base_mode = "IPOL" if polarimetry else "IMAG"
        # Determine whether in standard mode, SDI mode, or MBI/r mode
        nonsdi_flts = ("UNKNOWN", "OPEN")
        sdi = dfl1.upper() not in nonsdi_flts and dfl2.upper() not in nonsdi_flts
        if sdi:
            obs_mod = f"{base_mode}_SDI"
        elif self.current_mode_id == "MBI":
            obs_mod = f"{base_mode}_MBI"
        elif self.current_mode_id == "MBI_REDUCED":
            obs_mod = f"{base_mode}_MBIR"
        elif self.current_mode_id == "PUPIL":
            obs_mod = f"{base_mode}_PUP"
        else:
            obs_mod = base_mode

        self._set_formatted_keyword('OBS-MOD', obs_mod)
        self._fill_wcs_keywords(obs_mod)

    def _fill_wcs_keywords(self, obs_mod):
        # Hotspot of physical detector in the current crop coordinates.
        # Could be beyond the sensor if the crop does not include the detector center.

        # All of that almost never changes, but since there is a possibility that we move the
        # Wollaston in and out without re-firing a set_camera_mode, we don't have a choice but to
        # do it every single time in the polling thread.
        xfull2 = (self.current_mode.x1 - self.current_mode.x0 + 1) / 2.
        yfull2 = (self.current_mode.y1 - self.current_mode.y0 + 1) / 2.
        frame_center = xfull2, yfull2
        # Create and update WCS keywords

        if "MBI" in obs_mod:
            # 4 WCS
            wcs_dicts = []
            for i, field in enumerate(("770", "720", "670", "610")):
                if field == "610" and obs_mod.endswith("MBIR"):
                    name = "NA"
                else:
                    name = f"F{field}"
                hx, hy = self.HOTSPOTS[field]
                wcs_dict = wcs_dict_init(i, pix=(hx + 0.5, hy + 0.5),
                                         delt_val=self.PLATE_SCALE,
                                         cd_rot_rad=self.PA_OFFSET, name=name,
                                         double_with_subaru_fake_standard=False)
                wcs_dicts.append(wcs_dict)
        else:
            # 1 WCS, Central column
            wcs_dicts = [
                    wcs_dict_init(0, pix=frame_center,
                                  delt_val=self.PLATE_SCALE,
                                  cd_rot_rad=self.PA_OFFSET, name="PRIMARY",
                                  double_with_subaru_fake_standard=False)
            ]
            for i in range(1, 4):
                wcs_dicts.append(
                        wcs_dict_init(i, pix=frame_center,
                                      delt_val=self.PLATE_SCALE,
                                      cd_rot_rad=self.PA_OFFSET,
                                      double_with_subaru_fake_standard=False,
                                      name="NA"))

        # push keys to SHM
        for wcs_dict in wcs_dicts:
            for key, values in wcs_dict.items():
                self._set_formatted_keyword(key, values[0])


class VCAM1(BaseVCAM):
    PLATE_SCALE = (BaseVCAM.PLATE_SCALE[0], -BaseVCAM.PLATE_SCALE[1]
                   )  # deg / px

    GAINS = {"FAST": 0.1052, "SLOW": 0.1046}
    MODES = {
            BaseVCAM.STANDARD:
                    util.CameraMode(x0=1764, x1=2299, y0=896, y1=1431,
                                    tint=1e-3),
            BaseVCAM.MBI:
                    util.CameraMode(x0=756, x1=2995, y0=632, y1=1735,
                                    tint=1e-3),
            BaseVCAM.MBI_REDUCED:
                    util.CameraMode(x0=756, x1=2995, y0=1152, y1=1735,
                                    tint=1e-3),
            BaseVCAM.PUPIL:
                    util.CameraMode(x0=1644, x1=2403, y0=784, y1=1543, tint=0.1)
    }
    MODES.update(BaseVCAM.MODES)
    HOTSPOTS = {
            "770": (1965.4, 808.2),
            "720": (843.9, 830.0),
            "670": (279.4, 833.5),
            "610": (268.7, 270.7)
    }

    def _fill_keywords(self) -> None:
        super()._fill_keywords()

        # Override detector name
        self._set_formatted_keyword("DETECTOR", "VCAM1 - OrcaQ")
        self._set_formatted_keyword("U_CAMERA", 1)

        # Override detector specs from calibration data
        self._set_formatted_keyword("GAIN",
                                    self.GAINS[self.readout_mode.upper()])

    def poll_camera_for_keywords(self) -> None:
        super().poll_camera_for_keywords()

        # Defaults
        filter02 = "Unknown"
        qwp1 = qwp1th = -1
        qwp2 = qwp2th = -1
        try:
            with self.RDB.pipeline() as pipe:
                pipe.hget("U_DIFFL1", "value")
                pipe.hget("U_QWP1", "value")
                pipe.hget("U_QWP1TH", "value")
                pipe.hget("U_QWP2", "value")
                pipe.hget("U_QWP2TH", "value")
                filter02, qwp1, qwp1th, qwp2, qwp2th = pipe.execute()
        except:
            logg.error('REDIS unavailable @ _fill_keywords @ VCAM1')

        self._set_formatted_keyword("FILTER02", filter02)
        self._set_formatted_keyword("U_QWP1", qwp1)
        self._set_formatted_keyword("U_QWP1TH", qwp1th)
        self._set_formatted_keyword("U_QWP2", qwp2)
        self._set_formatted_keyword("U_QWP2TH", qwp2th)


class VCAM2(BaseVCAM):
    MODES = {
            BaseVCAM.STANDARD:
                    util.CameraMode(x0=1768, x1=2303, y0=892, y1=1427,
                                    tint=1e-3),
            BaseVCAM.MBI:
                    util.CameraMode(x0=756, x1=2995, y0=572, y1=1675,
                                    tint=1e-3),
            BaseVCAM.MBI_REDUCED:
                    util.CameraMode(x0=756, x1=2995, y0=572, y1=1155,
                                    tint=1e-3),
            BaseVCAM.PUPIL:
                    util.CameraMode(x0=1648, x1=2407, y0=772, y1=1531, tint=0.1)
    }
    MODES.update(BaseVCAM.MODES)

    GAINS = {"FAST": 0.1052, "SLOW": 0.1046}
    HOTSPOTS = {
            "770": (1970.5, 313.1),
            "720": (850.8, 279.3),
            "670": (286.4, 268.9),
            "610": (269.3, 834.4)
    }

    def _fill_keywords(self) -> None:
        super()._fill_keywords()

        # Override detector name
        self._set_formatted_keyword("DETECTOR", "VCAM2 - OrcaQ")
        self._set_formatted_keyword("U_CAMERA", 2)

        # Override detector specs from calibration data
        self._set_formatted_keyword("GAIN",
                                    self.GAINS[self.readout_mode.upper()])

    def poll_camera_for_keywords(self) -> None:
        super().poll_camera_for_keywords()

        # Defaults
        filter02 = "Unknown"
        try:
            filter02 = self.RDB.hget('U_DIFFL2', 'value')
        except:
            logg.error('REDIS unavailable @ _fill_keywords @ VCAM2')

        self._set_formatted_keyword("FILTER02", filter02)
