from typing import Optional as Op, Tuple
from camstack.viewertools.generic_viewer_backend import GenericViewerBackend
from camstack.viewertools.generic_viewer_frontend import GenericViewerFrontend
from swmain.network.pyroclient import connect
from camstack.viewertools import backend_utils as buts
import camstack.viewertools.frontend_utils as futs
import pygame.constants as pgmc
from functools import partial
import logging
from rich.live import Live
from rich.logging import RichHandler
from skimage.transform import rescale
import numpy as np
from camstack.cams.vampires import VCAM1, VCAM2
from swmain.redis import RDB, get_values

stream_handler = RichHandler(level=logging.INFO, show_level=False,
                             show_path=False, log_time_format="%H:%M:%S")


class VAMPIRESBaseViewerBackend(GenericViewerBackend):
    HELP_MSG = """
VAMPIRES Camera Viewer
==================================================
h           : display this message
x, ESC      : quit viewer

Camera controls:
(Note: these get applied to both cameras.
 if you press ALT, will only apply to one camera)
--------------------------------------------------
CTRL  + j         : Increase exposure time
CTRL  + k         : Decrease exposure time
CTRL  + e         : Enable hardware trigger
SHIFT + e         : Disable hardware trigger
CTRL  + t         : Enable micro-controller trigger
SHIFT + t         : Disable micro-controller trigger
CTRL  + f         : Switch to SLOW readout mode
SHIFT + f         : Switch to FAST readout mode

Display controls:
--------------------------------------------------
c         : display cross
SHIFT + c : display centered cross
d         : subtract dark frame
CTRL + d  : take dark frame
r         : subtract reference frame
CTRL + r  : take reference frame
p         : display compass
i         : display scale bar
l         : linear/non-linear display
m         : cycle colormaps
v         : start/stop accumulating and averaging frames
z         : zoom/unzoom on the center of the image
SHIFT + z : unzoom image (cycle backwards)
ARROW     : steer crop
CTRL + z  : reset zoom and crop

Pupil mode:
--------------------------------------------------
CTRL  + p : toggle pupil lens

Focus controls:
--------------------------------------------------
CTRL  + u          : Nudge focus by  0.005 mm
CTRL  + i          : Nudge focus by -0.005 mm
SHIFT + u          : Nudge focus by  0.1 mm
SHIFT + i          : Nudge focus by -0.1 mm

Cam focus controls:
--------------------------------------------------
CTRL  + l          : Nudge cam focus by  0.01 mm
CTRL  + ;          : Nudge cam focus by -0.01mm
SHIFT + l          : Nudge cam focus by  0.1 mm
SHIFT + ;          : Nudge cam focus by -0.1 mm

MBI wheel controls:
--------------------------------------------------
CTRL  + []         : Nudge wheel 0.005 deg CCW / CW
SHIFT + []         : Nudge wheel 0.2 deg CCW / CW
CTRL  + m          : Insert MBI dichroics
SHIFT + m          : Remove MBI dichroics
ALT   + m          : Save current angle to last configuration

Filter controls:
--------------------------------------------------
CTRL + 1 : Open
CTRL + 2 : 625-50
CTRL + 3 : 675-60
CTRL + 4 : 725-50
CTRL + 5 : 750-50
CTRL + 6 : 775-50

Diff Filter controls:
--------------------------------------------------
CTRL + SHIFT + 7 : Open / Open
CTRL + SHIFT + 8 : SII-Cont / SII
CTRL + SHIFT + 9 : Ha-Cont / Halpha
CTRL + SHIFT + 0 : Open / Open
CTRL + SHIFT + - : SII / SII-Cont
CTRL + SHIFT + = : Halpha / Ha-Cont

Field stop controls:
--------------------------------------------------
CTRL  + 7     : Fieldstop
CTRL  + 8     : CLC-2
CTRL  + 9     : CLC-3
CTRL  + 0     : CLC-5
CTRL  + -     : CLC-7
CTRL  + =     : DGVVC
CTRL  + ARROW : Nudge 0.001 mm in x (left/right) and y (up/down)
SHIFT + ARROW : Nudge 0.05 mm in x (left/right) and y (up/down)
CTRL  + .     : Nudge -0.01 mm in focus
CTRL  + ;     : Nudge 0.01 mm in focus
CTRL  + o     : Offset fieldstop 0.5 mm; press again to return
CTRL  + s     : Save current position to last configuration"""

    # CTRL+S:  Save current position to preset
    # CTRL+F:  Change preset file
    # add additional shortcuts
    def __init__(self, cam_num, name_shm, cam_name=None):
        if cam_name is None:
            cam_name = f"VCAM{cam_num}"
        self.cam_name = cam_name
        self.cam_num = cam_num
        self.other_cam_num = (cam_num % 2) + 1
        self.other_cam_name = f"VCAM{self.other_cam_num}"
        self.cam = connect(self.cam_name)
        self.other_cam = connect(self.other_cam_name)

        self.live = Live()
        self.logger = logging.getLogger(name_shm)
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(stream_handler)
        super().__init__(name_shm=name_shm)

        self.SHORTCUTS.update({
                buts.Shortcut(pgmc.K_f, pgmc.KMOD_LCTRL):
                        partial(self.set_readout_mode, mode="SLOW", both=True),
                buts.Shortcut(pgmc.K_f, pgmc.KMOD_LCTRL | pgmc.KMOD_LALT):
                        partial(self.set_readout_mode, mode="SLOW"),
                buts.Shortcut(pgmc.K_f, pgmc.KMOD_LSHIFT):
                        partial(self.set_readout_mode, mode="FAST", both=True),
                buts.Shortcut(pgmc.K_f, pgmc.KMOD_LSHIFT | pgmc.KMOD_LALT):
                        partial(self.set_readout_mode, mode="FAST"),
                buts.Shortcut(pgmc.K_j, pgmc.KMOD_LCTRL):
                        partial(self.increase_exposure_time, both=True),
                buts.Shortcut(pgmc.K_j, pgmc.KMOD_LCTRL | pgmc.KMOD_LALT):
                        partial(self.increase_exposure_time, both=False),
                buts.Shortcut(pgmc.K_k, pgmc.KMOD_LCTRL):
                        partial(self.decrease_exposure_time, both=True),
                buts.Shortcut(pgmc.K_k, pgmc.KMOD_LCTRL | pgmc.KMOD_LALT):
                        partial(self.decrease_exposure_time, both=False),
        })
        # flip steering direction on cam2 to compensate
        if self.cam_num == 2:
            self.SHORTCUTS.update({
                    buts.Shortcut(pgmc.K_UP, 0x0):
                            partial(self.steer_crop, pgmc.K_DOWN),
                    buts.Shortcut(pgmc.K_DOWN, 0x0):
                            partial(self.steer_crop, pgmc.K_UP),
            })

        # variables to carry state
        self.hwtrig_enabled = None

    def set_readout_mode(self, mode: str, both: bool = False):
        self.logger.info(
                f"Changing to {mode.upper()} readout mode for {self.cam_name}.")
        self.cam.set_readout_mode(mode)
        self.logger.info(f"Now using {mode.upper()} readout mode.")
        if both:
            self.logger.info(
                    f"Changing to {mode.upper()} readout mode for {self.other_cam_name}."
            )
            self.other_cam.set_readout_mode(mode)
            self.logger.info(f"Now using {mode.upper()} readout mode.")

    def set_camera_mode(self, mode: str, both: bool = False):
        self.logger.info(
                f"Changing to {mode.upper()} camera mode for {self.cam_name}.")
        self.cam.set_camera_mode(mode)
        self.logger.info(f"Now using {mode.upper()} camera mode.")
        if both:
            self.logger.info(
                    f"Changing to {mode.upper()} camera mode for {self.other_cam_name}."
            )
            self.other_cam.set_camera_mode(mode)
            self.logger.info(f"Now using {mode.upper()} camera mode.")

    def increase_exposure_time(self, both: bool = False):
        tint = self.cam.get_tint() * 1.5
        self.logger.info(f"Increasing exposure time to {tint:8.04f} s")
        self.cam.set_tint(tint)
        if both:
            self.other_cam.set_tint(tint)

    def decrease_exposure_time(self, both: bool = False):
        tint = self.cam.get_tint() * 0.75
        self.logger.info(f"Decreasing exposure time to {tint:8.04f} s")
        self.cam.set_tint(tint)
        if both:
            self.other_cam.set_tint(tint)

    def _get_crop_slice(self, center, shape):
        cr, cc = center
        halfside = (shape[0] / 2**(self.crop_lvl_id + 1),
                    shape[1] / 2**(self.crop_lvl_id + 1))
        # Adjust, in case we've just zoomed-out from a crop spot that's too close to the edge!
        cr_temp = min(max(cr, halfside[0]), self.shm_shape[0] - halfside[0])
        cc_temp = min(max(cc, halfside[1]), self.shm_shape[1] - halfside[1])

        cr_low = int(cr_temp - halfside[0])
        cc_low = int(cc_temp - halfside[1])
        cr_high = cr_low + int(2 * halfside[0])
        cc_high = cc_low + int(2 * halfside[1])
        crop_slice = np.s_[cr_low:cr_high, cc_low:cc_high]
        return crop_slice

    def toggle_crop(self, *args, **kwargs) -> None:
        super().toggle_crop(*args, **kwargs)

        # calculate crops for each window
        if self.cam_num == 1:
            hotspots = VCAM1.HOTSPOTS
        elif self.cam_num == 2:
            hotspots = VCAM2.HOTSPOTS
        else:
            raise ValueError(f"Unknown camera number {self.cam_num}")

        _mbi_shape = 520, 520
        mbi_centers = {}
        mbir_centers = {}
        for key, hotspot in hotspots.items():
            cr = hotspot[0] + self.crop_offset[0]
            cc = hotspot[1] + self.crop_offset[1]
            mbi_centers[key] = cr, cc
            # reduced mode
            if cr >= self.shm_shape[0]:
                cr -= 520
            if cc >= self.shm_shape[1]:
                cc -= 520
            mbir_centers[key] = cr, cc
        self.mbi_slices = (
                self._get_crop_slice(center=mbi_centers["760"],
                                     shape=_mbi_shape),
                self._get_crop_slice(center=mbi_centers["720"],
                                     shape=_mbi_shape),
                self._get_crop_slice(center=mbi_centers["670"],
                                     shape=_mbi_shape),
                self._get_crop_slice(center=mbi_centers["610"],
                                     shape=_mbi_shape),
        )
        self.mbir_slices = (
                self._get_crop_slice(center=mbir_centers["760"],
                                     shape=_mbi_shape),
                self._get_crop_slice(center=mbir_centers["720"],
                                     shape=_mbi_shape),
                self._get_crop_slice(center=mbir_centers["670"],
                                     shape=_mbi_shape),
                self._get_crop_slice(center=mbir_centers["610"],
                                     shape=_mbi_shape),
        )

    def _data_crop(self) -> None:
        """
        SHM -> self.data_debias_uncrop -> self.data_debias

        Crop, but also compute some uncropped stats
        that will be useful further down the pipeline
        """
        assert self.data_raw_uncrop is not None
        assert self.data_debias_uncrop is not None

        # get image statistics for full data frame
        self.data_min = np.min(self.data_raw_uncrop)
        self.data_max = np.max(self.data_raw_uncrop)
        self.data_mean = np.mean(self.data_raw_uncrop)

        ## determine our camera mode from the data size
        Nx, Ny = self.data_debias_uncrop.shape
        if Nx > 800 and Ny > 800:
            self.mode = "MBI"
            slices = self.mbi_slices
        elif Nx > 800:
            self.mode = "MBI_REDUCED"
            slices = self.mbir_slices
        elif Nx > 536 and Ny > 536:
            self.mode = "PUPIL"
        else:
            self.mode = "STANDARD"

        if self.mode.startswith("MBI"):
            field_775 = self.data_debias_uncrop[slices[0]]
            field_725 = self.data_debias_uncrop[slices[1]]
            field_675 = self.data_debias_uncrop[slices[2]]
            # MBI-reduced mode
            if self.mode.endswith("REDUCED"):
                field_625 = np.full_like(field_675, np.nan)
            else:
                field_625 = self.data_debias_uncrop[slices[3]]
            fields = [[field_625, field_725], [field_675, field_775]]
            if self.cam_num == 2:
                fields = [[np.fliplr(field_625),
                           np.fliplr(field_725)],
                          [np.fliplr(field_675),
                           np.fliplr(field_775)]]
            self.data_debias = np.block(fields)
        else:
            self.data_debias = self.data_debias_uncrop[self.crop_slice]

            ## flip camera 2 on y-axis
            if self.cam_num == 2:
                self.data_debias = np.fliplr(self.data_debias)


class VAMPIRESBaseViewerFrontend(GenericViewerFrontend):
    WINDOW_NAME = "VCAM"
    CARTOON_FILE = "opeapea1.png"
    BOTTOM_PX_PAD = 175

    def __init__(self, cam_num, *args, **kwargs) -> None:
        self.cam_num = cam_num
        self.WINDOW_NAME = f"VCAM{self.cam_num}"
        if self.cam_num == 2:
            self.CARTOON_FILE = "opeapea1-flipped.png"
        super().__init__(*args, **kwargs)

    def _init_labels(self) -> int:
        self.fonts = futs.FontBook(self.fonts_zoom)
        r = self.data_disp_size[1] + 1.5 * self.fonts_zoom
        c = 5 * self.fonts_zoom

        # Generic camera viewer
        self.lbl_title = futs.LabelMessage(self.WINDOW_NAME,
                                           self.fonts.DEFAULT_25, topleft=(c,
                                                                           r))
        self.lbl_title.blit(self.pg_screen)
        r += int(self.lbl_title.em_size)

        self.lbl_help = futs.LabelMessage("For help press [h], quit [x]",
                                          self.fonts.MONO, topleft=(c, r))
        self.lbl_help.blit(self.pg_screen)
        r += int(self.lbl_help.em_size)

        self.lbl_cropzone = futs.LabelMessage("crop = [%4d %4d %4d %4d]",
                                              self.fonts.MONO, topleft=(c, r))
        self.lbl_cropzone.blit(self.pg_screen)
        r += int(self.lbl_cropzone.em_size)

        self.lbl_times = futs.LabelMessage("t=%10.3f ms / fps= %4.0f",
                                           self.fonts.MONO, topleft=(c, r))
        self.lbl_times.blit(self.pg_screen)
        r += int(self.lbl_times.em_size)

        self.lbl_trig = futs.LabelMessage("trigger: %3s / readout: %4s",
                                          futs.Fonts.MONO, topleft=(c, r))
        self.lbl_trig.blit(self.pg_screen)
        r += int(self.lbl_trig.em_size)

        self.lbl_data_val = futs.LabelMessage("l,h=(%5.0f, %5.0f) mu=%6.0f",
                                              self.fonts.MONO, topleft=(c, r))
        self.lbl_data_val.blit(self.pg_screen)
        r += int(1.2 * self.lbl_data_val.em_size)

        # {Status message [sat, acquiring dark, acquiring ref...]}
        # At the bottom right.
        self.lbl_saturation = futs.LabelMessage("%28s", self.fonts.MONO,
                                                topleft=(c, r))
        r += int(1.2 * self.lbl_saturation.em_size)
        self.lbl_status = futs.LabelMessage("%28s", self.fonts.MONO,
                                            topleft=(c, r))
        r += int(self.lbl_status.em_size)
        return r

    def _inloop_update_labels(self) -> None:
        assert self.backend_obj is not None

        kws = self.backend_obj.input_shm.get_keywords(
        )  # single fetch rather than pymilk functions.
        try:
            self.hwtrig_enabled = RDB.hget("U_TRIGEN", "value")
        except:
            pass
        tint: float = kws.get("EXPTIME", 0)  # seconds
        fps: float = kws.get("FRATE", 0)
        trigger: str = ""
        if "EXTTRIG" in kws:
            trigger = "EXT" if kws["EXTTRIG"] == "#TRUE#" else "INT"

        readmode: str = kws.get("U_DETMOD", "").strip().upper()
        tint_ms = tint * 1e3

        self.lbl_cropzone.render(tuple(self.backend_obj.input_shm.get_crop()),
                                 blit_onto=self.pg_screen)
        self.lbl_times.render((tint_ms, fps), blit_onto=self.pg_screen)
        # check if the external trigger is on but arduino is off- paint red
        if trigger == "EXT" and not self.hwtrig_enabled:
            self.lbl_trig.render((trigger, readmode), blit_onto=self.pg_screen,
                                 fg_col=futs.Colors.WHITE,
                                 bg_col=futs.Colors.VERY_RED)
        else:
            self.lbl_trig.render((trigger, readmode), blit_onto=self.pg_screen)
        self.lbl_data_val.render(
                (self.backend_obj.data_min, self.backend_obj.data_max,
                 self.backend_obj.data_mean), blit_onto=self.pg_screen)

        self.pg_updated_rects.extend((
                self.lbl_cropzone.rectangle,
                self.lbl_times.rectangle,
                self.lbl_data_val.rectangle,
        ))
