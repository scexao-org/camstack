from typing import Optional as Op, Tuple
from camstack.viewers.generic_viewer_frontend import GenericViewerFrontend
from swmain.network.pyroclient import connect
from camstack.viewers.generic_viewer_backend import GenericViewerBackend
from camstack.viewers import backend_utils as buts
from camstack.viewers import frontend_utils as futs
from camstack.viewers.plugin_arch import BasePlugin
import pygame.constants as pgmc
from functools import partial
import pygame
import logging
from swmain.redis import RDB
from rich.panel import Panel
from rich.live import Live
from rich.logging import RichHandler

logger = logging.getLogger("vpupcam")
stream_handler = RichHandler(level=logging.INFO, show_level=False,
                             show_path=False, log_time_format="%H:%M:%S")
logger.addHandler(stream_handler)


class VAMPIRESPupilCamViewerFrontend(GenericViewerFrontend):
    WINDOW_NAME = "VPUPCAM"


class VAMPIRESPupilCamViewerBackend(GenericViewerBackend):
    HELP_MSG = """VPUPCAM controls
---------------
h           : display this message
x, ESC      : quit vpupcam

pupil wheel controls:
---------------------
CTRL+ -- :  change filter wheel slot
        1:  Open (0 deg)
        2:  SAM-7
        3:  SAM-9
        4:  SAM-18
        5:  SAM-18-Nudged
        6:  SAM-Ann-Nudged
        7:  Mirror
        8:  SAM-Ann
        9:  LyotStop
        0:  Open (218 deg)
        -:  ND10
        =:  ND25
CTRL+ARROW :  Nudge wheel 0.01 mm in x (left/right) and y (up/down)
SHIFT+ARROW:  Move wheel 1 mm in x (left/right) and y (up/down)
CTRL+[]    :  Nudge wheel 0.1 deg in theta (ccw/cw)
SHIFT+[]   :  Nudge wheel 1 deg in theta (ccw/cw)
    """

    # CTRL+S:  Save current position to preset
    # CTRL+F:  Change preset file
    # add additional shortcuts

    def __init__(self, name_shm=None):
        if name_shm is None:
            name_shm = "vpupcam"
        super().__init__(name_shm=name_shm)
        self.wheel = connect("VAMPIRES_MASK")


class MaskStatusPlugin(BasePlugin):

    def __init__(self, frontend_obj: GenericViewerFrontend) -> None:
        super().__init__(frontend_obj)
        zoom = self.frontend_obj.system_zoom
        font = pygame.font.SysFont("default", 40 * zoom)
        self.enabled = True
        # Ideally you'd instantiate the label in the frontend, cuz different viewers could be wanting the same info
        # displayed at different locations.
        self.label = futs.LabelMessage(
                "%s", font, fg_col="#4AC985", bg_col=None,
                topleft=(20 * zoom,
                         self.frontend_obj.data_disp_size[1] - 40 * zoom))
        self.label.blit(self.frontend_obj.pg_datasurface)
        self.current_index = None

        # yapf: disable
        self.shortcut_map = {
            buts.Shortcut(pgmc.K_LEFT, pgmc.KMOD_LCTRL): partial(self.nudge_wheel, pgmc.K_LEFT, fine=True),
            buts.Shortcut(pgmc.K_LEFT, pgmc.KMOD_LSHIFT): partial(self.nudge_wheel, pgmc.K_LEFT, fine=False),
            buts.Shortcut(pgmc.K_RIGHT, pgmc.KMOD_LCTRL): partial(self.nudge_wheel, pgmc.K_RIGHT, fine=True),
            buts.Shortcut(pgmc.K_RIGHT, pgmc.KMOD_LSHIFT): partial(self.nudge_wheel, pgmc.K_RIGHT, fine=False),
            buts.Shortcut(pgmc.K_UP, pgmc.KMOD_LCTRL): partial(self.nudge_wheel, pgmc.K_UP, fine=True),
            buts.Shortcut(pgmc.K_UP, pgmc.KMOD_LSHIFT): partial(self.nudge_wheel, pgmc.K_UP, fine=False),
            buts.Shortcut(pgmc.K_DOWN, pgmc.KMOD_LCTRL): partial(self.nudge_wheel, pgmc.K_DOWN, fine=True),
            buts.Shortcut(pgmc.K_DOWN, pgmc.KMOD_LSHIFT): partial(self.nudge_wheel, pgmc.K_DOWN, fine=False),
            buts.Shortcut(pgmc.K_LEFTBRACKET, pgmc.KMOD_LCTRL): partial(self.rotate_wheel, pgmc.K_LEFTBRACKET, fine=True),
            buts.Shortcut(pgmc.K_LEFTBRACKET, pgmc.KMOD_LSHIFT): partial(self.rotate_wheel, pgmc.K_LEFTBRACKET, fine=False),
            buts.Shortcut(pgmc.K_RIGHTBRACKET, pgmc.KMOD_LCTRL): partial(self.rotate_wheel, pgmc.K_RIGHTBRACKET, fine=True),
            buts.Shortcut(pgmc.K_RIGHTBRACKET, pgmc.KMOD_LSHIFT): partial(self.rotate_wheel, pgmc.K_RIGHTBRACKET, fine=False),
            buts.Shortcut(pgmc.K_1, pgmc.KMOD_LCTRL): partial(self.change_wheel, 1),
            buts.Shortcut(pgmc.K_2, pgmc.KMOD_LCTRL): partial(self.change_wheel, 2),
            buts.Shortcut(pgmc.K_3, pgmc.KMOD_LCTRL): partial(self.change_wheel, 3),
            buts.Shortcut(pgmc.K_4, pgmc.KMOD_LCTRL): partial(self.change_wheel, 4),
            buts.Shortcut(pgmc.K_5, pgmc.KMOD_LCTRL): partial(self.change_wheel, 5),
            buts.Shortcut(pgmc.K_6, pgmc.KMOD_LCTRL): partial(self.change_wheel, 6),
            buts.Shortcut(pgmc.K_7, pgmc.KMOD_LCTRL): partial(self.change_wheel, 7),
            buts.Shortcut(pgmc.K_8, pgmc.KMOD_LCTRL): partial(self.change_wheel, 8),
            buts.Shortcut(pgmc.K_9, pgmc.KMOD_LCTRL): partial(self.change_wheel, 9),
            buts.Shortcut(pgmc.K_0, pgmc.KMOD_LCTRL): partial(self.change_wheel, 10),
            buts.Shortcut(pgmc.K_MINUS, pgmc.KMOD_LCTRL): partial(self.change_wheel, 11),
            buts.Shortcut(pgmc.K_EQUALS, pgmc.KMOD_LCTRL): partial(self.change_wheel, 12),
            buts.Shortcut(pgmc.K_s, pgmc.KMOD_LCTRL): self.save_config,
            }
        # yapf: enable

    def nudge_wheel(self, key, fine=True):
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
            nudge_value = sign * 0.02
        else:
            nudge_value = sign * 1
        logger.info(f"Moving {substage} by {nudge_value} mm")
        self.backend_obj.wheel.move_relative__oneway(substage, nudge_value)

    def rotate_wheel(self, key, fine=True):
        # CCW
        sign = 1
        if key == pgmc.K_LEFTBRACKET:
            sign = -1
        # CW
        elif key == pgmc.K_RIGHTBRACKET:
            sign = 1
        if fine:
            nudge_value = sign * 0.1
        else:
            nudge_value = sign * 1
        logger.info(f"Rotating theta by {nudge_value} deg")
        self.backend_obj.wheel.move_relative__oneway("theta", nudge_value)

    def change_wheel(self, index: int):
        logger.info(f"Moving wheel to configuration {index}")
        self.backend_obj.wheel.move_configuration_idx__oneway(index)
        self.current_index = index

    def save_config(self):
        if self.current_index is None:
            logger.info(
                    "Must have selected a mask before saving its configuration")
            return
        else:
            index = self.current_index
        logger.info(f"Saving position for configuration {index}")
        self.backend_obj.wheel.save_configuration(index=index)
        self.backend_obj.wheel.update_keys()

    def frontend_action(self) -> None:
        self.label.render(self.status,
                          blit_onto=self.frontend_obj.pg_datasurface)
        # self.frontend_obj.pg_updated_rects.append(self.label.rectangle)

    def backend_action(self) -> None:
        # Warning: this is called every time the window refreshes, i.e. ~20Hz.
        name = RDB.hget("U_MASK", "value")
        self.status = name