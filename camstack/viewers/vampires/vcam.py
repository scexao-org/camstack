from typing import Optional as Op, Tuple
from camstack.viewers.generic_viewer_backend import GenericViewerBackend
from camstack.viewers.generic_viewer_frontend import GenericViewerFrontend
from swmain.network.pyroclient import connect
from camstack.viewers import backend_utils as buts
import pygame.constants as pgmc
from functools import partial
import logging
from rich.live import Live
from rich.logging import RichHandler
from skimage.transform import downscale_local_mean
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
CTRL  + e        : Enable external trigger
SHIFT + e        : Disable external trigger
CTRL  + r        : Switch to FAST readout mode
SHIFT + r        : Switch to SLOW readout mode
CTRL  + m        : TODO Switch to STANDARD mode
SHIFT + m        : TODO Switch to MBI mode
CTRL + SHIFT + m : TODO Switch to MBI-REDUCED mode

Display controls:
--------------------------------------------------
c : display crosses
p : TODO display compass
l : linear/non-linear display
m : cycle colormaps
o : TODO bullseye on the PSF
v : start/stop accumulating and averaging frames
z : zoom/unzoom on the center of the image

Pupil mode:
--------------------------------------------------
CTRL  + p : enable pupil lens
SHIFT + p : disable pupil lens

MBI wheel controls:
--------------------------------------------------
CTRL  + []         : Nudge wheel 0.1 deg CCW / CW
CTRL  + SHIFT + [] : Nudge wheel 1 deg CCW / CW
CTRL  + b          : Insert MBI dichroics
SHIFT + b          : Remove MBI dichroics
ALT   + b          : Save current angle to last configuration

Filter controls:
--------------------------------------------------
CTRL + 1 : Open
CTRL + 2 : 625-50
CTRL + 3 : 675-60
CTRL + 4 : 725-50
CTRL + 5 : 750-50
CTRL + 6 : 775-50

Field stop controls:
--------------------------------------------------
CTRL  + 8     : Field stop
CTRL  + 9     : CLC-2
CTRL  + 0     : CLC-3
CTRL  + -     : CLC-5
CTRL  + =     : CLC-7
CTRL  + ARROW : Nudge 0.01 mm in x (left/right) and y (up/down)
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

        self.SHORTCUTS = {
                buts.Shortcut(pgmc.K_e, pgmc.KMOD_LCTRL):
                        partial(self.set_external_trigger, enable=True,
                                both=True),
                buts.Shortcut(pgmc.K_e, pgmc.KMOD_LCTRL | pgmc.KMOD_LALT):
                        partial(self.set_external_trigger, enable=True),
                buts.Shortcut(pgmc.K_e, pgmc.KMOD_LSHIFT):
                        partial(self.set_external_trigger, enable=False,
                                both=True),
                buts.Shortcut(pgmc.K_e, pgmc.KMOD_LSHIFT | pgmc.KMOD_LALT):
                        partial(self.set_external_trigger, enable=False),
                buts.Shortcut(pgmc.K_r, pgmc.KMOD_LCTRL):
                        partial(self.set_readout_mode, mode="FAST", both=True),
                buts.Shortcut(pgmc.K_r, pgmc.KMOD_LCTRL | pgmc.KMOD_LALT):
                        partial(self.set_readout_mode, mode="FAST"),
                buts.Shortcut(pgmc.K_r, pgmc.KMOD_LSHIFT):
                        partial(self.set_readout_mode, mode="SLOW", both=True),
                buts.Shortcut(pgmc.K_r, pgmc.KMOD_LSHIFT | pgmc.KMOD_LALT):
                        partial(self.set_readout_mode, mode="SLOW"),
                buts.Shortcut(pgmc.K_m, pgmc.KMOD_LCTRL):
                        partial(self.set_camera_mode, mode="STANDARD",
                                both=True),
                buts.Shortcut(pgmc.K_m, pgmc.KMOD_LCTRL | pgmc.KMOD_LALT):
                        partial(self.set_camera_mode, mode="STANDARD"),
                buts.Shortcut(pgmc.K_m, pgmc.KMOD_LSHIFT):
                        partial(self.set_camera_mode, mode="MBI", both=True),
                buts.Shortcut(pgmc.K_m, pgmc.KMOD_LSHIFT | pgmc.KMOD_LALT):
                        partial(self.set_camera_mode, mode="MBI"),
                buts.Shortcut(pgmc.K_m, pgmc.KMOD_LCTRL | pgmc.KMOD_LSHIFT):
                        partial(self.set_camera_mode, mode="MBI_REDUCED",
                                both=True),
                buts.Shortcut(
                        pgmc.K_m,
                        pgmc.KMOD_LCTRL | pgmc.KMOD_LSHIFT | pgmc.KMOD_LALT):
                        partial(self.set_camera_mode, mode="MBI_REDUCED"),
        }
        self.live = Live()
        self.logger = logging.getLogger(name_shm)
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(stream_handler)
        return super().__init__(name_shm=name_shm)

    def set_external_trigger(self, enable: bool, both: bool = False):
        word = "Enabling" if enable else "Disabling"
        self.logger.info(f"{word} external trigger for {self.cam_name}.")
        self.cam.set_external_trigger(enable)
        word = "enabled" if enable else "disabled"
        self.logger.info(f"External trigger has been {word}.")
        if both:
            word = "Enabling" if enable else "Disabling"
            self.logger.info(
                    f"{word} external trigger for {self.other_cam_name}.")
            self.other_cam.set_external_trigger(enable)
            word = "enabled" if enable else "disabled"
            self.logger.info(f"External trigger has been {word}.")

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

    def toggle_crop(self, *args, **kwargs) -> None:
        super().toggle_crop(*args, **kwargs)

        # calculate crops for each window
        _mbi_shape = 560, 560
        self.mbi_slices = (
                self._get_crop_slice(center=(279.5, 279.5),
                                     shape=_mbi_shape),  # 775
                self._get_crop_slice(center=(1395.5, 279.5),
                                     shape=_mbi_shape),  # 725
                self._get_crop_slice(center=(1959.5, 279.5),
                                     shape=_mbi_shape),  # 675
                self._get_crop_slice(center=(1959.5, 839.5),
                                     shape=_mbi_shape),  # 625
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
        if Nx > 560 and Ny > 560:
            self.mode = "MBI"
        elif Nx > 560:
            self.mode = "MBI_REDUCED"
        else:
            self.mode = "STANDARD"

        if self.mode.startswith("MBI"):
            field_775 = downscale_local_mean(
                    self.data_debias_uncrop[self.mbi_slices[0]], (2, 2))
            field_725 = downscale_local_mean(
                    self.data_debias_uncrop[self.mbi_slices[1]], (2, 2))
            field_675 = downscale_local_mean(
                    self.data_debias_uncrop[self.mbi_slices[2]], (2, 2))
            # MBI-reduced mode
            if self.mode.endswith("REDUCED"):
                field_625 = np.full_like(field_675, np.nan)
            else:
                field_625 = downscale_local_mean(
                        self.data_debias_uncrop[self.mbi_slices[3]], (2, 2))
            self.data_debias = np.block([[field_625, field_675],
                                         [field_725, field_775]])
        else:
            self.data_debias = self.data_debias_uncrop[self.crop_slice]


import camstack.viewers.frontend_utils as futs


class VAMPIRESBaseViewerFrontend(GenericViewerFrontend):
    WINDOW_NAME = "VCAM"
    CARTOON_FILE = "bat.png"

    def __init__(self, cam_num, *args, **kwargs) -> None:
        self.cam_num = cam_num
        self.WINDOW_NAME = f"VCAM{self.cam_num}"
        super().__init__(*args, **kwargs)

    def _init_labels(self) -> int:

        sz = self.system_zoom  # Shorthandy
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
        r += int(self.lbl_times.em_size)

        self.lbl_data_val = futs.LabelMessage("m,M=(%5.0f, %5.0f) mu=%5.0f",
                                              futs.Fonts.MONO, topleft=(c, r))
        r += int(1.5 * self.lbl_data_val.em_size)

        # {Status message [sat, acquiring dark, acquiring ref...]}
        # At the bottom right.
        self.lbl_status = futs.LabelMessage("%28s", futs.Fonts.MONO,
                                            topleft=(c, r))
        r += int(self.lbl_status.em_size)
        return r

    def _inloop_update_labels(self) -> None:
        assert self.backend_obj

        fps = self.backend_obj.input_shm.get_fps()
        tint = self.backend_obj.input_shm.get_expt()  # seconds
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
