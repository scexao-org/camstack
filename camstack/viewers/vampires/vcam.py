from typing import Optional as Op, Tuple
from camstack.viewers.generic_viewer_backend import GenericViewerBackend
from camstack.viewers.generic_viewer_frontend import GenericViewerFrontend
from swmain.network.pyroclient import connect
from camstack.viewers import backend_utils as buts
import camstack.viewers.frontend_utils as futs
import pygame.constants as pgmc
from functools import partial
import logging
from rich.live import Live
from rich.logging import RichHandler
from skimage.transform import rescale
import numpy as np

stream_handler = RichHandler(level=logging.INFO, show_level=False,
                             show_path=False, log_time_format="%H:%M:%S")


class VAMPIRESBaseViewerBackend(GenericViewerBackend):
    HELP_MSG = """
h           : display this message
x, ESC      : quit viewer

Camera controls:
(Note: these get applied to both cameras.
 if you press ALT, will only apply to one camera)
--------------------------------------------------
CTRL  + e         : Enable hardware trigger
SHIFT + e         : Disable hardware trigger
CTRL  + t         : Enable micro-controller trigger
SHIFT + t         : Disable micro-controller trigger
CTRL  + f         : Switch to FAST readout mode
SHIFT + f         : Switch to SLOW readout mode

Display controls:
--------------------------------------------------
c         : display cross
SHIFT + c : display centered cross
d         : subtract dark frame
CTRL + d  : take dark frame
r         : subtract reference frame
CTRL + r  : take reference frame
p         : TODO display compass
l         : linear/non-linear display
m         : cycle colormaps
o         : TODO bullseye on the PSF
v         : start/stop accumulating and averaging frames
z         : zoom/unzoom on the center of the image

Pupil mode:
--------------------------------------------------
CTRL  + p : toggle pupil lens

MBI wheel controls:
--------------------------------------------------
CTRL  + []         : Nudge wheel 0.005 deg CCW / CW
CTRL  + SHIFT + [] : Nudge wheel 0.2 deg CCW / CW
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
CTRL  + ARROW : Nudge 0.005 mm in x (left/right) and y (up/down)
SHIFT + ARROW : Nudge 0.1 mm in x (left/right) and y (up/down)
CTRL  + s     : Save current position to last configuration"""

    # CTRL+S:  Save current position to preset
    # CTRL+F:  Change preset file
    # add additional shortcuts
    def __init__(self, cam_num, name_shm=None, cam_name=None):
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
                        partial(self.set_readout_mode, mode="FAST", both=True),
                buts.Shortcut(pgmc.K_f, pgmc.KMOD_LCTRL | pgmc.KMOD_LALT):
                        partial(self.set_readout_mode, mode="FAST"),
                buts.Shortcut(pgmc.K_f, pgmc.KMOD_LSHIFT):
                        partial(self.set_readout_mode, mode="SLOW", both=True),
                buts.Shortcut(pgmc.K_f, pgmc.KMOD_LSHIFT | pgmc.KMOD_LALT):
                        partial(self.set_readout_mode, mode="SLOW"),
                # buts.Shortcut(pgmc.K_m, pgmc.KMOD_LCTRL):
                #         partial(self.set_camera_mode, mode="STANDARD",
                #                 both=True),
                # buts.Shortcut(pgmc.K_m, pgmc.KMOD_LCTRL | pgmc.KMOD_LALT):
                #         partial(self.set_camera_mode, mode="STANDARD"),
                # buts.Shortcut(pgmc.K_m, pgmc.KMOD_LSHIFT):
                #         partial(self.set_camera_mode, mode="MBI", both=True),
                # buts.Shortcut(pgmc.K_m, pgmc.KMOD_LSHIFT | pgmc.KMOD_LALT):
                #         partial(self.set_camera_mode, mode="MBI"),
                # buts.Shortcut(pgmc.K_m, pgmc.KMOD_LCTRL | pgmc.KMOD_LSHIFT):
                #         partial(self.set_camera_mode, mode="MBI_REDUCED",
                #                 both=True),
                # buts.Shortcut(
                #         pgmc.K_m,
                #         pgmc.KMOD_LCTRL | pgmc.KMOD_LSHIFT | pgmc.KMOD_LALT):
                #         partial(self.set_camera_mode, mode="MBI_REDUCED"),
        })
        if self.cam_num == 2:
            self.SHORTCUTS.update({
                    buts.Shortcut(pgmc.K_UP, 0x0):
                            partial(self.steer_crop, pgmc.K_DOWN),
                    buts.Shortcut(pgmc.K_DOWN, 0x0):
                            partial(self.steer_crop, pgmc.K_UP),
                    buts.Shortcut(pgmc.K_LEFT, 0x0):
                            partial(self.steer_crop, pgmc.K_LEFT),
                    buts.Shortcut(pgmc.K_RIGHT, 0x0):
                            partial(self.steer_crop, pgmc.K_RIGHT),
            })

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

    def _get_crop_slice(self, center, shape):
        assert self.crop_offset

        cr, cc = center
        halfside = (shape[0] / 2**(self.crop_lvl_id + 1),
                    shape[1] / 2**(self.crop_lvl_id + 1))
        # Adjust, in case we've just zoomed-out from a crop spot that's too close to the edge!
        # cr_temp = min(max(cr, halfside[0]), shape[0] - halfside[0])
        # cc_temp = min(max(cc, halfside[1]), shape[1] - halfside[1])

        cr_low = int(cr - halfside[0])
        cc_low = int(cc - halfside[1])
        cr_high = cr_low + int(2 * halfside[0])
        cc_high = cc_low + int(2 * halfside[1])
        crop_slice = np.s_[cr_low:cr_high, cc_low:cc_high]
        return crop_slice

    def toggle_crop(self, *args, **kwargs) -> None:
        super().toggle_crop(*args, **kwargs)

        hotspots_cam1 = {
                "770": (1961.4, 812.2),  # x, y on detector
                "720": (839.4, 829.7),
                "670": (276.7, 832.6),
                "620": (268.5, 273.4)
        }
        hotspots_cam2 = {
                "770": (1970.0, 327.1),
                "720": (849.7, 283.0),
                "670": (287.1, 267.1),
                "620": (268.5, 829.1)
        }

        # calculate crops for each window
        if self.cam_num == 1:
            hotspots = hotspots_cam1
        elif self.cam_num == 2:
            hotspots = hotspots_cam2
        _mbi_shape = 520, 520
        centers = {
                k: (v[0] + self.crop_offset[0], v[1] + self.crop_offset[1])
                for k, v in hotspots.items()
        }
        self.mbi_slices = (
                self._get_crop_slice(center=centers["770"], shape=_mbi_shape),
                self._get_crop_slice(center=centers["720"], shape=_mbi_shape),
                self._get_crop_slice(center=centers["670"], shape=_mbi_shape),
                self._get_crop_slice(center=centers["620"], shape=_mbi_shape),
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
        if Nx > 536 and Ny > 536:
            self.mode = "MBI"
        elif Nx > 536:
            self.mode = "MBI_REDUCED"
        else:
            self.mode = "STANDARD"

        if self.mode.startswith("MBI"):
            field_775 = self.data_debias_uncrop[self.mbi_slices[0]]
            field_725 = self.data_debias_uncrop[self.mbi_slices[1]]
            field_675 = self.data_debias_uncrop[self.mbi_slices[2]]
            # MBI-reduced mode
            if self.mode.endswith("REDUCED"):
                field_625 = np.full_like(field_675, np.nan)
            else:
                field_625 = self.data_debias_uncrop[self.mbi_slices[3]]
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
    BOTTOM_PX_PAD = 155

    def __init__(self, cam_num, *args, **kwargs) -> None:
        self.cam_num = cam_num
        self.WINDOW_NAME = f"VCAM{self.cam_num}"
        if self.cam_num == 2:
            self.CARTOON_FILE = "opeapea1-flipped.png"
        super().__init__(*args, **kwargs)

    def _init_labels(self) -> int:
        r = self.data_disp_size[1] + 3 * self.system_zoom
        c = 10 * self.system_zoom

        # Generic camera viewer
        self.lbl_title = futs.LabelMessage(self.WINDOW_NAME,
                                           futs.Fonts.DEFAULT_25, topleft=(c,
                                                                           r))
        self.lbl_title.blit(self.pg_screen)
        r += int(self.lbl_title.em_size)

        self.lbl_help = futs.LabelMessage("For help press [h], quit [x]",
                                          futs.Fonts.MONO, topleft=(c, r))
        self.lbl_help.blit(self.pg_screen)
        r += int(self.lbl_help.em_size)

        self.lbl_cropzone = futs.LabelMessage("crop = [%4d %4d %4d %4d]",
                                              futs.Fonts.MONO, topleft=(c, r))
        self.lbl_cropzone.blit(self.pg_screen)
        r += int(self.lbl_cropzone.em_size)

        self.lbl_times = futs.LabelMessage("t=%10.3f ms - fps= %4.0f",
                                           futs.Fonts.MONO, topleft=(c, r))
        self.lbl_times.blit(self.pg_screen)
        r += int(self.lbl_times.em_size)

        self.lbl_data_val = futs.LabelMessage("m,M=(%5.0f, %5.0f) mu=%5.0f",
                                              futs.Fonts.MONO, topleft=(c, r))
        self.lbl_data_val.blit(self.pg_screen)
        r += int(1.2 * self.lbl_data_val.em_size)

        # {Status message [sat, acquiring dark, acquiring ref...]}
        # At the bottom right.
        self.lbl_saturation = futs.LabelMessage("%28s", futs.Fonts.MONO,
                                                topleft=(c, r))
        r += int(1.2 * self.lbl_saturation.em_size)
        self.lbl_status = futs.LabelMessage("%28s", futs.Fonts.MONO,
                                            topleft=(c, r))
        r += int(self.lbl_status.em_size)
        return r

    def _inloop_update_labels(self) -> None:
        assert self.backend_obj

        tint = self.backend_obj.input_shm.get_expt()  # seconds
        fps = self.backend_obj.input_shm.get_fps()
        tint_ms = tint * 1e3

        self.lbl_cropzone.render(tuple(self.backend_obj.input_shm.get_crop()),
                                 blit_onto=self.pg_screen)
        self.lbl_times.render((tint_ms, fps), blit_onto=self.pg_screen)
        self.lbl_data_val.render(
                (self.backend_obj.data_min, self.backend_obj.data_max,
                 self.backend_obj.data_mean), blit_onto=self.pg_screen)

        self.pg_updated_rects.extend((
                self.lbl_cropzone.rectangle,
                self.lbl_times.rectangle,
                self.lbl_data_val.rectangle,
        ))
