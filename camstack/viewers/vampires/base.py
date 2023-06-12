from typing import Optional as Op, Optional, Tuple
from camstack.viewers.generic_viewer_backend import GenericViewerBackend
from camstack.viewers.generic_viewer_frontend import GenericViewerFrontend
from swmain.network.pyroclient import connect
from camstack.viewers import backend_utils as buts
from camstack.viewers import frontend_utils as futs
from camstack.viewers.plugin_arch import BasePlugin
from camstack.viewers.plugins import PupilMode
import pygame.constants as pgmc
from functools import partial
import pygame
import logging
from swmain.redis import RDB
from rich.panel import Panel
from rich.live import Live
from rich.logging import RichHandler

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


class VAMPIRESBaseViewerFrontend(GenericViewerFrontend):
    WINDOW_NAME = "VCAM"
