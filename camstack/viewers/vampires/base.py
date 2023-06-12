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
x, ESC      : quit vcam viewer

camera controls:
----------------
CTRL + e  : Enable external trigger
SHIFT + e : Disable external trigger
CTRL + r  : Switch to FAST readout mode
SHIFT + r : Switch to SLOW readout mode
CTRL + m  : TODO Switch to STANDARD mode (will move MBI wheel)
SHIFT + m : TODO Switch to MBI mode (will move MBI wheel)
ALT + m   : TODO Switch to MBI-REDUCED mode (will move MBI wheel)


display controls:
-----------------
c         : display crosses
p         : TODO display compass
l         : linear/non-linear display
m         : cycle colormaps
o         : TODO bullseye on the PSF
v         : start/stop accumulating and averaging frames
z         : zoom/unzoom on the center of the image


pupil mode:
-----------
CTRL + p: enable pupil lens
SHIFT + p: disable pupil lens

MBI wheel controls:
-------------------
CTRL + [    : Move wheel 0.1 deg CCW
CTRL + ]    : Move wheel 0.1 deg CW

filter controls:
----------------
CTRL+ -- :  change filter wheel slot
       1 :  Open
       2 :  625-50
       3 :  675-60
       4 :  725-50
       5 :  750-50
       6 :  775-50

field stop controls:
---------------------
CTRL + 8     : Field stop
CTRL + 9     : CLC-2
CTRL + 0     : CLC-3
CTRL + -     : CLC-5
CTRL + =     : CLC-7
CTRL + ARROW : Nudge FPM 0.01 mm in x (left/right) and y (up/down)
SHIFT + ARROW:  Move FPM 0.5 mm in x (left/right) and y (up/down)"""

    # CTRL+S:  Save current position to preset
    # CTRL+F:  Change preset file
    # add additional shortcuts
    def __init__(self, cam_num, name_shm=None, cam_name=None):
        if cam_name is None:
            cam_name = f"VCAM{cam_num}"
        self.cam_name = cam_name
        self.cam_num = cam_num
        self.cam = connect(cam_name)

        self.SHORTCUTS = {
                buts.Shortcut(pgmc.K_e, pgmc.KMOD_LCTRL):
                        partial(self.set_external_trigger, enable=True),
                buts.Shortcut(pgmc.K_e, pgmc.KMOD_LSHIFT):
                        partial(self.set_external_trigger, enable=False),
                buts.Shortcut(pgmc.K_r, pgmc.KMOD_LCTRL):
                        partial(self.set_readout_mode, mode="FAST"),
                buts.Shortcut(pgmc.K_r, pgmc.KMOD_LSHIFT):
                        partial(self.set_readout_mode, mode="SLOW"),
                buts.Shortcut(pgmc.K_LEFT, pgmc.KMOD_LCTRL):
                        partial(self.nudge_fieldstop, pgmc.K_LEFT, fine=True),
                buts.Shortcut(pgmc.K_LEFT, pgmc.KMOD_LSHIFT):
                        partial(self.nudge_fieldstop, pgmc.K_LEFT, fine=False),
                buts.Shortcut(pgmc.K_RIGHT, pgmc.KMOD_LCTRL):
                        partial(self.nudge_fieldstop, pgmc.K_RIGHT, fine=True),
                buts.Shortcut(pgmc.K_RIGHT, pgmc.KMOD_LSHIFT):
                        partial(self.nudge_fieldstop, pgmc.K_RIGHT, fine=False),
                buts.Shortcut(pgmc.K_UP, pgmc.KMOD_LCTRL):
                        partial(self.nudge_fieldstop, pgmc.K_UP, fine=True),
                buts.Shortcut(pgmc.K_UP, pgmc.KMOD_LSHIFT):
                        partial(self.nudge_fieldstop, pgmc.K_UP, fine=False),
                buts.Shortcut(pgmc.K_DOWN, pgmc.KMOD_LCTRL):
                        partial(self.nudge_fieldstop, pgmc.K_DOWN, fine=True),
                buts.Shortcut(pgmc.K_DOWN, pgmc.KMOD_LSHIFT):
                        partial(self.nudge_fieldstop, pgmc.K_DOWN, fine=False),
                buts.Shortcut(pgmc.K_8, pgmc.KMOD_LCTRL):
                        partial(self.change_fieldstop, 1),
                buts.Shortcut(pgmc.K_9, pgmc.KMOD_LCTRL):
                        partial(self.change_fieldstop, 2),
                buts.Shortcut(pgmc.K_0, pgmc.KMOD_LCTRL):
                        partial(self.change_fieldstop, 3),
                buts.Shortcut(pgmc.K_MINUS, pgmc.KMOD_LCTRL):
                        partial(self.change_fieldstop, 4),
                buts.Shortcut(pgmc.K_EQUALS, pgmc.KMOD_LCTRL):
                        partial(self.change_fieldstop, 5),
        }
        self.live = Live()
        self.logger = logging.getLogger(name_shm)
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(stream_handler)
        return super().__init__(name_shm=name_shm)

    def set_external_trigger(self, enable: bool):
        word = "Enabling" if enable else "Disabling"
        self.logger.info(f"{word} external trigger for {self.cam_name}.")
        self.cam.set_external_trigger(enable)
        word = "enabled" if enable else "disabled"
        self.logger.info(f"External trigger has been {word}.")

    def set_readout_mode(self, mode: str):
        self.logger.info(f"Changing to {mode.upper()} readout mode.")
        self.cam.set_readout_mode(mode)
        self.logger.info(f"Now using {mode.upper()} readout mode.")

    def nudge_fieldstop(self, key, fine=True):
        sign = 1
        if key == pgmc.K_LEFT:
            substage = "x"
            sign = 1
        elif key == pgmc.K_RIGHT:
            substage = "x"
            sign = -1
        elif key == pgmc.K_UP:
            substage = "y"
            sign = 1
        elif key == pgmc.K_DOWN:
            substage = "y"
            sign = -1

        if fine:
            nudge_value = sign * 0.01
        else:
            nudge_value = sign * 0.5
        self.logger.info(f"Moving {substage} by {nudge_value} mm")
        self.fieldstop.move_relative__oneway(substage, nudge_value)

    def change_fieldstop(self, index: int):
        self.logger.info(f"Moving fieldstop to configuration {index}")
        # self.fieldstop.move_configuration_idx__oneway(index)


class VAMPIRESBaseViewerFrontend(GenericViewerFrontend):
    WINDOW_NAME = "VCAM"
