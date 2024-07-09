from __future__ import annotations

import typing as typ

import logging as logg
import numpy as np

from camstack.core import utilities as util
from camstack.core.wcs import wcs_dict_init

from .dcamcam import OrcaQuest


class BaseVCAM(OrcaQuest):
    HOTSPOTS: typ.Dict[str, typ.Tuple[float, float]] = {}
    PLATE_SCALE: tuple[float,
                       float] = (0, 0
                                 )  # deg/px, must be overridden by sub-classes
    INST_PA: float = 0  # deg, must be overridden by sub-classes

    ## camera keywords
    KEYWORDS: typ.Dict[str, typ.Tuple[util.Typ_shm_kw, str, str, str]] = {
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
    FULL, TWOARC, ONEARC, HALFARC, STANDARD, NPBS, MBI, MBI_REDUCED, PUPIL = \
        "FULL", "TWOARC", "ONEARC", "HALFARC", "STANDARD", "NPBS", "MBI", "MBI_REDUCED", "PUPIL"
    MBI_ONEHALF = "MBI_ONEHALF"
    MODES = {
            FULL:
                    util.CameraMode(x0=0, x1=4095, y0=0, y1=2303, tint=0.001),
            STANDARD:
                    util.CameraMode(x0=1780, x1=2315, y0=884, y1=1419,
                                    tint=1e-3),
            TWOARC:
                    util.CameraMode(x0=1868, x1=2227, y0=972, y1=1331,
                                    tint=1e-3),
            ONEARC:
                    util.CameraMode(x0=1956, x1=2139, y0=1060, y1=1243,
                                    tint=1e-3),
            HALFARC:
                    util.CameraMode(x0=1914, x1=2181, y0=1018, y1=1285,
                                    tint=1e-3),
    }

    # IS_WATER_COOLED = False  # Results in prepare_camera_for_size setting cooler to MAX.
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
        self._set_formatted_keyword("INST-PA", self.INST_PA)
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
        pupil_lens = "Unknown"
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
                pipe.hget("U_PUPST", "value")
                filter01, bs, lp_stage, hwp_stage, scex_lp, lp_theta, imrang, imrpad, dfl1, dfl2, qwp1, qwp1th, qwp2, qwp2th, retang1, retang2, retpos1, retpos2, pupil_lens = pipe.execute(
                )
        except Exception:
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
        nonsdi_flts = ("UNKNOWN", "OPEN", "BLOCK")
        sdi = dfl1.upper() not in nonsdi_flts and dfl2.upper() not in nonsdi_flts
        if sdi:
            obs_mod = f"{base_mode}_SDI"
        elif self.current_mode_id == "MBI":
            obs_mod = f"{base_mode}_MBI"
        elif self.current_mode_id == "MBI_REDUCED":
            obs_mod = f"{base_mode}_MBIR"
        elif pupil_lens.strip().upper() == "IN":
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
        d_imrpad = 0
        try:
            d_imrpad = self.RDB.hget('D_IMRPAD', 'value')
        except Exception:
            logg.exception(
                    'REDIS unavailable @ poll_camera_for_keywords @ BaseVCAM')

        cd_angle = np.deg2rad(self.INST_PA + d_imrpad)

        if "MBI" in obs_mod:
            # 4 WCS
            wcs_dicts = []
            for i, field in enumerate(("760", "720", "670", "610")):
                if field == "610" and obs_mod.endswith("MBIR"):
                    name = "NA"
                else:
                    name = f"F{field}"
                # hotspots are aboslute coordinates, need to subtract crop origin
                hx, hy = self.HOTSPOTS[field]
                hx -= self.current_mode.x0
                hy -= self.current_mode.y0
                wcs_dict = wcs_dict_init(i, pix=(hx + 0.5, hy + 0.5),
                                         delt_val=self.PLATE_SCALE,
                                         cd_rot_rad=cd_angle, name=name,
                                         double_with_subaru_fake_standard=False)
                wcs_dicts.append(wcs_dict)
        else:
            # 1 WCS, Central column
            wcs_dicts = [
                    wcs_dict_init(0, pix=frame_center,
                                  delt_val=self.PLATE_SCALE,
                                  cd_rot_rad=cd_angle, name="PRIMARY",
                                  double_with_subaru_fake_standard=False)
            ]
            for i in range(1, 4):
                wcs_dicts.append(
                        wcs_dict_init(i, pix=frame_center,
                                      delt_val=self.PLATE_SCALE,
                                      cd_rot_rad=cd_angle,
                                      double_with_subaru_fake_standard=False,
                                      name="NA"))

        # push keys to SHM
        for wcs_dict in wcs_dicts:
            for key, values in wcs_dict.items():
                self._set_formatted_keyword(key, values[0])


class VCAM1(BaseVCAM):
    PLATE_SCALE = (-5.908 / 3.6e6, -5.908 / 3.6e6)  # deg / px
    INST_PA = -38.90  # deg
    GAINS = {"FAST": 0.103, "SLOW": 0.105}
    MODES = {
            # BaseVCAM.STANDARD:
            #         util.CameraMode(x0=1764, x1=2299, y0=896, y1=1431,
            #                         tint=1e-3),
            BaseVCAM.MBI:
                    util.CameraMode(x0=924, x1=3151, y0=608, y1=1707,
                                    tint=1e-3),
            BaseVCAM.MBI_REDUCED:
                    util.CameraMode(x0=924, x1=3151, y0=1168, y1=1707,
                                    tint=1e-3),
            BaseVCAM.PUPIL:
                    util.CameraMode(x0=1604, x1=2491, y0=704, y1=1595,
                                    tint=0.1),
            BaseVCAM.MBI_ONEHALF:
                    util.CameraMode(x0=1124, x1=3011, y0=1328, y1=1547,
                                    tint=1e-4),
    }
    MODES.update(BaseVCAM.MODES)
    MODES[BaseVCAM.NPBS] = MODES[BaseVCAM.STANDARD]
    HOTSPOTS = {
            "760": (2881.6, 1436.9),
            "720": (1758.9, 1436.9),
            "670": (1195.6, 1438.0),
            "610": (1194.3, 878.0),
    }
    ORIGIN = {
            "MBI": (608, 924),
            "MBI_REDUCED": (1168, 924),
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
            filter02 = self.RDB.hget("U_DIFFL1", "value")
        except:
            logg.exception(
                    'REDIS unavailable @ poll_camera_for_keywords @ VCAM1')

        self._set_formatted_keyword("FILTER02", filter02)


class VCAM2(BaseVCAM):
    PLATE_SCALE = (-5.895 / 3.6e6, 5.895 / 3.6e6)  # deg / px
    INST_PA = -38.58  # deg
    MODES = {
            # BaseVCAM.STANDARD:
            #         util.CameraMode(x0=1768, x1=2303, y0=892, y1=1427,
            #                         tint=1e-3),
            BaseVCAM.NPBS:
                    util.CameraMode(x0=1700, x1=2235, y0=816, y1=1351,
                                    tint=1e-3),
            BaseVCAM.MBI:
                    util.CameraMode(x0=924, x1=3151, y0=592, y1=1695,
                                    tint=1e-3),
            BaseVCAM.MBI_REDUCED:
                    util.CameraMode(x0=928, x1=3151, y0=592, y1=1139,
                                    tint=1e-3),
            BaseVCAM.MBI_ONEHALF:
                    util.CameraMode(x0=1128, x1=3015, y0=744, y1=979,
                                    tint=1e-4),
            BaseVCAM.PUPIL:
                    util.CameraMode(x0=1648, x1=2407, y0=772, y1=1531,
                                    tint=0.1),
    }
    MODES.update(BaseVCAM.MODES)

    GAINS = {"FAST": 0.103, "SLOW": 0.105}
    HOTSPOTS = {
            "760": (2882.7, 870.2),
            "720": (1761.1, 865.5),
            "670": (1198.0, 861.9),
            "610": (1194.6, 1425.6)
    }
    ORIGIN = {
            "MBI": (592, 924),
            "MBI_REDUCED": (592, 928),
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
