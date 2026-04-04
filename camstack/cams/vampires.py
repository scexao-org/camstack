from __future__ import annotations

import typing as typ

import logging as logg
import numpy as np

from camstack.core import utilities as util
from camstack.core.wcs import wcs_dict_init

from .dcamcam import OrcaQuest


class BaseVCAM(OrcaQuest):
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
            "U_QWP2": (-1, "[deg] VAMPIRES QWP 2 polarization angle", "%16.3f",
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
    MBI_JEWEL = "MBI_JEWEL"
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

        keyval = {
                'U_FILTER': "Unknwon",
                'U_BS': "Unknown",
                'P_STGPS1': 0,
                'P_STGPS2': 0,
                'X_POLAR': "Unknown",
                'X_POLARP': -1,
                'D_IMRANG': -1,
                'D_IMRPAD': -1,
                'U_DIFFL1': "Open",
                'U_DIFFL2': "Open",
                'U_QWP1': -1,
                'U_QWP1TH': -1,
                'U_QWP2': -1,
                'U_QWP2TH': -1,
                'RET-ANG1': -1,
                'RET-ANG2': -1,
                'RET-POS1': -1,
                'RET-POS2': -1,
                'U_PUPST': "Unknown"
        }
        try:
            assert self.RDB is not None
            keyval.update(self.RDB.redis_batched_hget(keyval))
        except Exception:
            logg.exception(
                    'REDIS unavailable @ poll_camera_for_keywords @ BaseVCAM')

        for key in {
                'X_POLARP', 'D_IMRANG', 'D_IMRPAD', 'U_QWP1', 'U_QWP1TH',
                'U_QWP2', 'U_QWP2TH', 'RET-ANG1', 'RET-ANG2', 'RET-POS1',
                'RET-POS2'
        }:
            self._set_formatted_keyword(key, keyval[key])

        # Key change from global to local naming
        self._set_formatted_keyword('FILTER01', keyval['U_FILTER'])

        ## determine observing mode from the following logic
        # if the PBS is in and the HWP is running, we're doing polarimetry
        polarimetry = keyval['U_BS'].upper() == "PBS" and \
                      (np.abs(keyval['P_STGPS2'] - 56) < 1 or \
                       np.abs(keyval['P_STGPS1'] - 55.2) < 1 or \
                       np.abs(keyval['P_STGPS1'] - 90) < 1 or
                       keyval['X_POLAR'].strip().upper() == "IN")
        base_mode = "IPOL" if polarimetry else "IMAG"
        # Determine whether in standard mode, SDI mode, or MBI/r mode
        nonsdi_flts = ("UNKNOWN", "OPEN", "BLOCK")
        sdi = keyval['U_DIFFL1'].upper() not in nonsdi_flts and \
            keyval['U_DIFFL2'].upper() not in nonsdi_flts
        if sdi:
            obs_mod = f"{base_mode}_SDI"
        elif self.current_mode_id in ("MBI", "MBI_JEWEL"):
            obs_mod = f"{base_mode}_MBI"
        elif self.current_mode_id in ("MBI_REDUCED", "MBI_ONEHALF"):
            obs_mod = f"{base_mode}_MBIR"
        elif keyval['U_PUPST'].strip().upper() == "IN":
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
                    hx, hy = 0, 0
                    # should we continue???
                else:
                    name = f"F{field}"
                    hx, hy = self.MODES["MBI"].hotspots[name]
                # hotspots are aboslute coordinates, need to subtract crop origin

                # calculate crops for each window
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
    PLATE_SCALE = (-5.952 / 3.6e6, 5.938 / 3.6e6)  # deg / px
    INST_PA = 129.44  # deg
    GAINS = {"FAST": 0.103, "SLOW": 0.105}
    MODES = {
            BaseVCAM.MBI:
                    util.CameraMode.from_file(util.MODES_DIR / "vampires" /
                                              "vcam1_mbi_crop.toml"),
            BaseVCAM.MBI_REDUCED:
                    util.CameraMode.from_file(util.MODES_DIR / "vampires" /
                                              "vcam1_mbir_crop.toml"),
            BaseVCAM.MBI_JEWEL:
                    util.CameraMode.from_file(util.MODES_DIR / "vampires" /
                                              "vcam1_mbi_jewel_crop.toml"),
            BaseVCAM.PUPIL:
                    util.CameraMode(x0=1604, x1=2491, y0=704, y1=1595,
                                    tint=0.1),
            BaseVCAM.MBI_ONEHALF:
                    util.CameraMode(x0=1124, x1=3011, y0=1328, y1=1547,
                                    tint=1e-4),
    }
    MODES.update(BaseVCAM.MODES)
    MODES[BaseVCAM.NPBS] = MODES[BaseVCAM.STANDARD]

    REDIS_PUSH_ENABLED = True
    REDIS_PREFIX = "u_V"  # LOWERCASE x to not get mixed with the SCExAO keys

    BADSYSTEMD_ENABLED = True
    BADSYSTEMD_KEY = 'V1_CAM'

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
    PLATE_SCALE = (-5.938 / 3.6e6, -5.938 / 3.6e6)  # deg / px
    INST_PA = 129.99  # deg
    MODES = {
            BaseVCAM.MBI:
                    util.CameraMode.from_file(util.MODES_DIR / "vampires" /
                                              "vcam2_mbi_crop.toml"),
            BaseVCAM.MBI_REDUCED:
                    util.CameraMode.from_file(util.MODES_DIR / "vampires" /
                                              "vcam2_mbir_crop.toml"),
            BaseVCAM.MBI_JEWEL:
                    util.CameraMode.from_file(util.MODES_DIR / "vampires" /
                                              "vcam2_mbi_jewel_crop.toml"),
            BaseVCAM.MBI_ONEHALF:
                    util.CameraMode(x0=1128, x1=3015, y0=744, y1=979,
                                    tint=1e-4),
            BaseVCAM.NPBS:
                    util.CameraMode(x0=1700, x1=2235, y0=816, y1=1351,
                                    tint=1e-3),
            BaseVCAM.PUPIL:
                    util.CameraMode(x0=1648, x1=2407, y0=772, y1=1531,
                                    tint=0.1),
            BaseVCAM.NPBS:
                    util.CameraMode(x0=1700, x1=2235, y0=816, y1=1351,
                                    tint=1e-3),
    }
    MODES.update(BaseVCAM.MODES)

    GAINS = {"FAST": 0.103, "SLOW": 0.105}

    REDIS_PUSH_ENABLED = True
    REDIS_PREFIX = "u_W"  # LOWERCASE u to not get mixed with the SCExAO keys

    BADSYSTEMD_ENABLED = True
    BADSYSTEMD_KEY = 'V2_CAM'

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
