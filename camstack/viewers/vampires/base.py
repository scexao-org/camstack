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


class FilterStatusPlugin(BasePlugin):

    def __init__(self, frontend_obj: GenericViewerFrontend) -> None:
        super().__init__(frontend_obj)
        zoom = self.frontend_obj.system_zoom
        font = pygame.font.SysFont("default", 30 * zoom)
        self.enabled = True
        self.label = futs.LabelMessage(
                "%s",
                font,
                fg_col="#4AC985",
                bg_col=None,
                topleft=(
                        20 * zoom,
                        20 * zoom,
                ),
        )
        self.label.blit(self.frontend_obj.pg_datasurface)

    def frontend_action(self) -> None:
        self.label.render(self.status,
                          blit_onto=self.frontend_obj.pg_datasurface)

    def backend_action(self) -> None:
        name = RDB.hget("U_FILTER", "value")
        self.status = name


class VAMPIRESPupilMode(PupilMode):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pupil_lens = connect("VAMPIRES_PUPIL")

    def backend_action(self) -> None:
        self.pupil_lens

    def enable(self) -> None:  # Override

        # SEND COMMAND TO SWITCH TO PUPIL MODE
        # Can be async, we don't care. Or do we?
        # Could be pyro, could be os.system...
        self.backend_obj.logger.info("Inserting pupil lens")

        if self.textbox:
            self.textbox.render(('PUPIL', ), fg_col=futs.Colors.BLACK)

        super().enable()

    def disable(self) -> None:  # Override

        # SEND COMMAND TO SWITCH OUT OF PUPIL MODE
        # Could be pyro, could be os.system...

        self.backend_obj.logger.info("Removing pupil lens")
        super().disable()


class VAMPIRESBaseViewerBackend(GenericViewerBackend):
    HELP_MSG = Panel(
            """
h           : display this message
x, ESC      : quit vcam viewer

camera controls:
----------------
CTRL + r  : Switch to FAST readout mode
SHIFT + r : Switch to SLOW readout mode
CTRL + m  : Switch to STANDARD mode (will move MBI wheel)
SHIFT + m : Switch to MBI mode (will move MBI wheel)
ALT + m   : Switch to MBI-REDUCED mode (will move MBI wheel)


display controls:
-----------------
c         : display crosses
p         : display compass
l         : linear/non-linear display
m         : cycle colormaps
o         : bullseye on the PSF
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
SHIFT + ARROW:  Move FPM 0.5 mm in x (left/right) and y (up/down)""",
            title="VCAM",
            subtitle="Help menu",
    )

    # CTRL+S:  Save current position to preset
    # CTRL+F:  Change preset file
    # add additional shortcuts
    def __init__(self, name_shm=None):
        self.SHORTCUTS = {
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
                buts.Shortcut(pgmc.K_1, pgmc.KMOD_LCTRL):
                        partial(self.change_filter, 1),
                buts.Shortcut(pgmc.K_2, pgmc.KMOD_LCTRL):
                        partial(self.change_filter, 2),
                buts.Shortcut(pgmc.K_3, pgmc.KMOD_LCTRL):
                        partial(self.change_filter, 3),
                buts.Shortcut(pgmc.K_4, pgmc.KMOD_LCTRL):
                        partial(self.change_filter, 4),
                buts.Shortcut(pgmc.K_5, pgmc.KMOD_LCTRL):
                        partial(self.change_filter, 5),
                buts.Shortcut(pgmc.K_6, pgmc.KMOD_LCTRL):
                        partial(self.change_filter, 6),
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
        # self.filt = connect("VAMPIRES_FILTER")
        # self.fieldstop = connect("VAMPIRES_FIELDSTOP")
        self.live = Live()
        self.logger = logging.getLogger(name_shm)
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(stream_handler)
        return super().__init__(name_shm=name_shm)

    def print_help(self):
        with self.live as live:
            live.console.print(VAMPIRESBaseViewerBackend.help_msg)

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

    def change_filter(self, index: int):
        self.logger.info(f"Moving filter to configuration {index}")
        self.filt.move_configuration_idx__oneway(index)

    def change_fieldstop(self, index: int):
        self.logger.info(f"Moving fieldstop to configuration {index}")
        # self.fieldstop.move_configuration_idx__oneway(index)


class VAMPIRESBaseViewerFrontend(GenericViewerFrontend):
    WINDOW_NAME = "VCAM"
