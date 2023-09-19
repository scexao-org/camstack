from __future__ import annotations

import typing as typ

import logging as logg
import numpy as np

from camstack.core import utilities as util
from camstack.core.wcs import wcs_dict_init

from .dcamcam import OrcaQuest


class BaseVCAM(OrcaQuest):
    PLATE_SCALE = (-1.6717718901193757e-6, 1.6717718901193757e-6)  # deg / px
    PA_OFFSET = -41.323163723676146  # deg
    HOTSPOTS: typ.Dict[str, typ.Tuple[float, float]] = {}

    ## camera keywords
    KEYWORDS: typ.Dict[str, typ.Tuple[util.KWType, str, str, str]] = {
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
            ## IMR because sometimes in cals it's a little tight
            "D_IMRANG": (-1, "[deg] IMR angle", "%16.3f", "IMRANG"),
            "D_IMRPAD": (-1, "[deg] IMR position angle of dec. axis", "%16.3f",
                         "IMRPAD"),
            ## Polarization terms from sc2
            "X_POLARP": (-1, "[deg] Polarizer angle", "%16.3f", "POLAR"),
            ## QWP terms managed by QWP daemon
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
    FULL, TWOARC, HALF, ONEARC, STANDARD, NPBS, MBI, MBI_REDUCED, PUPIL = \
        "FULL", "TWOARC", "HALF", "ONEARC", "STANDARD", "NPBS", "MBI", "MBI_REDUCED", "PUPIL"
    MODES = {
            FULL:
                    util.CameraMode(x0=0, x1=4095, y0=0, y1=2303, tint=0.001),
            STANDARD:
                    util.CameraMode(x0=1780, x1=2315, y0=884, y1=1419,
                                    tint=1e-3),
            TWOARC:
                    util.CameraMode(x0=1868, x1=2227, y0=972, y1=1331,
                                    tint=1e-3),
            HALF:
                    util.CameraMode(x0=1914, x1=2181, y0=1018, y1=1285,
                                    tint=1e-3),
            ONEARC:
                    util.CameraMode(x0=1956, x1=2139, y0=1060, y1=1243,
                                    tint=1e-3),
    }

    IS_WATER_COOLED = True  # Results in prepare_camera_for_size setting cooler to MAX.

    def set_readout_mode(self, mode: str) -> None:
        super().set_readout_mode(mode)
        self._set_formatted_keyword("U_DETMOD", mode.upper())

    def get_readout_mode(self) -> str:
        mode = super().get_readout_mode()
        self._set_formatted_keyword("U_DETMOD", mode.upper())
        return mode

    def _fill_keywords(self) -> None:
        super()._fill_keywords()
        cropped = self.current_mode_id != self.FULL
        self._set_formatted_keyword("CROPPED", cropped)

        self._set_formatted_keyword("F-RATIO", 21.3)
        self._set_formatted_keyword("INST-PA", self.PA_OFFSET)
        self._set_formatted_keyword("U_DETMOD", self.get_readout_mode().upper())

        self.get_fps()
        self.get_tint()

    def poll_camera_for_keywords(self) -> None:
        super().poll_camera_for_keywords()

        # Defaults
        filter01 = bs = "Unknown"
        dfl1 = dfl2 = "Open"
        hwp_stage = 0
        lp_stage = 0
        scex_lp = 'Unknown'
        lp_theta = imrang = imrpad = -1
        qwp1 = qwp1th = -1
        qwp2 = qwp2th = -1
        retang1 = retpos1 = -1
        retang2 = retpos2 = -1
        try:
            with self.RDB.pipeline() as pipe:
                pipe.hget('U_FILTER', 'value')
                pipe.hget('U_BS', 'value')
                pipe.hget('P_STGPS1', 'value')
                pipe.hget('P_STGPS2', 'value')
                pipe.hget('X_POLAR', 'value')
                pipe.hget('X_POLARP', 'value')
                pipe.hget('D_IMRANG', 'value')
                pipe.hget('D_IMRPAD', 'value')
                pipe.hget('U_DIFFL1', 'value')
                pipe.hget('U_DIFFL2', 'value')
                pipe.hget("U_QWP1", "value")
                pipe.hget("U_QWP1TH", "value")
                pipe.hget("U_QWP2", "value")
                pipe.hget("U_QWP2TH", "value")
                pipe.hget("RET-ANG1", "value")
                pipe.hget("RET-ANG2", "value")
                pipe.hget("RET-POS1", "value")
                pipe.hget("RET-POS2", "value")
                filter01, bs, lp_stage, hwp_stage, scex_lp, lp_theta, imrang, imrpad, dfl1, dfl2, qwp1, qwp1th, qwp2, qwp2th, retang1, retang2, retpos1, retpos2 = pipe.execute(
                )
        except:
            logg.exception(
                    'REDIS unavailable @ poll_camera_for_keywords @ BaseVCAM')

        self._set_formatted_keyword('FILTER01', filter01)
        self._set_formatted_keyword("X_POLARP", lp_theta)
        self._set_formatted_keyword("D_IMRANG", imrang)
        self._set_formatted_keyword("D_IMRPAD", imrpad)
        self._set_formatted_keyword("U_QWP1", qwp1)
        self._set_formatted_keyword("U_QWP1TH", qwp1th)
        self._set_formatted_keyword("U_QWP2", qwp2)
        self._set_formatted_keyword("U_QWP2TH", qwp2th)
        self._set_formatted_keyword("RET-ANG1", retang1)
        self._set_formatted_keyword("RET-ANG2", retang2)
        self._set_formatted_keyword("RET-POS1", retpos1)
        self._set_formatted_keyword("RET-POS2", retpos2)
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
            for i, field in enumerate(("760", "720", "670", "610")):
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

    GAINS = {"FAST": 0.103, "SLOW": 0.105}
    MODES = {
            # BaseVCAM.STANDARD:
            #         util.CameraMode(x0=1764, x1=2299, y0=896, y1=1431,
            #                         tint=1e-3),
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
    MODES[BaseVCAM.NPBS] = MODES[BaseVCAM.STANDARD]
    HOTSPOTS = {
            "760": (1965.4, 808.2),
            "720": (843.9, 830.0),
            "670": (279.4, 833.5),
            "610": (268.7, 270.7)
    }

    REDIS_PUSH_ENABLED = True
    REDIS_PREFIX = "u_V"  # LOWERCASE x to not get mixed with the SCExAO keys

    def _fill_keywords(self) -> None:
        super()._fill_keywords()

        # Override detector name
        self._set_formatted_keyword("DETECTOR", "VCAM1 - OrcaQ")
        self._set_formatted_keyword("U_CAMERA", 1)

        # Override detector specs from calibration data
        ro_mode = self.get_readout_mode()
        self._set_formatted_keyword("GAIN", self.GAINS[ro_mode])

    def poll_camera_for_keywords(self) -> None:
        super().poll_camera_for_keywords()

        # Defaults
        filter02 = "Unknown"
        try:
            with self.RDB.pipeline() as pipe:
                pipe.hget("U_DIFFL1", "value")
                filter02 = pipe.execute()
        except:
            logg.exception(
                    'REDIS unavailable @ poll_camera_for_keywords @ VCAM1')

        self._set_formatted_keyword("FILTER02", filter02)


class VCAM2(BaseVCAM):
    MODES = {
            # BaseVCAM.STANDARD:
            #         util.CameraMode(x0=1768, x1=2303, y0=892, y1=1427,
            #                         tint=1e-3),
            BaseVCAM.NPBS:
                    util.CameraMode(x0=1700, x1=2235, y0=816, y1=1351,
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

    GAINS = {"FAST": 0.103, "SLOW": 0.105}
    HOTSPOTS = {
            "760": (1970.5, 313.1),
            "720": (850.8, 279.3),
            "670": (286.4, 268.9),
            "610": (269.3, 834.4)
    }

    REDIS_PUSH_ENABLED = True
    REDIS_PREFIX = "u_W"  # LOWERCASE x to not get mixed with the SCExAO keys

    def _fill_keywords(self) -> None:
        super()._fill_keywords()

        # Override detector name
        self._set_formatted_keyword("DETECTOR", "VCAM2 - OrcaQ")
        self._set_formatted_keyword("U_CAMERA", 2)

        # Override detector specs from calibration data
        ro_mode = self.get_readout_mode()
        self._set_formatted_keyword("GAIN", self.GAINS[ro_mode])

    def poll_camera_for_keywords(self) -> None:
        super().poll_camera_for_keywords()

        # Defaults
        filter02 = "Unknown"
        try:
            filter02 = self.RDB.hget('U_DIFFL2', 'value')

        except:
            logg.exception(
                    'REDIS unavailable @ poll_camera_for_keywords @ VCAM2')

        self._set_formatted_keyword("FILTER02", filter02)
