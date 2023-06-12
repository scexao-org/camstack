from typing import Optional as Op, Tuple
from camstack.viewers.generic_viewer_frontend import GenericViewerFrontend
from swmain.network.pyroclient import connect
from camstack.viewers.generic_viewer_backend import GenericViewerBackend
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

logger = logging.getLogger()


class MaskWheelPlugin(BasePlugin):

    DEVICE_NAME = "VAMPIRES_MASK"

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
        self.wheel = connect(self.DEVICE_NAME)
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
        self.backend_obj.logger.info(f"Moving {substage} by {nudge_value} mm")
        self.wheel.move_relative__oneway(substage, nudge_value)

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
        self.backend_obj.logger.info(f"Rotating theta by {nudge_value} deg")
        self.wheel.move_relative__oneway("theta", nudge_value)

    def change_wheel(self, index: int):
        self.backend_obj.logger.info(f"Moving wheel to configuration {index}")
        self.wheel.move_configuration_idx__oneway(index)
        self.current_index = index

    def save_config(self):
        if self.current_index is None:
            self.backend_obj.logger.info(
                    "Must have selected a mask before saving its configuration")
            return
        else:
            index = self.current_index
        self.backend_obj.logger.info(
                f"Saving position for configuration {index}")
        self.wheel.save_configuration(index=index)
        self.wheel.update_keys()

    def frontend_action(self) -> None:
        self.label.render(self.status,
                          blit_onto=self.frontend_obj.pg_datasurface)
        # self.frontend_obj.pg_updated_rects.append(self.label.rectangle)

    def backend_action(self) -> None:
        # Warning: this is called every time the window refreshes, i.e. ~20Hz.
        name = RDB.hget("U_MASK", "value")
        self.status = name


class FilterWheelPlugin(BasePlugin):

    DEVICE_NAME = "VAMPIRES_FILT"

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
        self.filt = connect(self.DEVICE_NAME)

        # yapf: disable
        self.shortcut_map = {
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
            }
        # yapf: enable

    def change_filter(self, index: int):
        _, filt = self.filt.get_configuration(index)
        self.self.backend_obj.logger.info(
                f"Moving filter to position {index}: {filt}")
        self.filt.move_configuration_idx__oneway(index)

    def frontend_action(self) -> None:
        self.label.render(self.status,
                          blit_onto=self.frontend_obj.pg_datasurface)

    def backend_action(self) -> None:
        # Warning: this is called every time the window refreshes, i.e. ~20Hz.
        name = RDB.hget("U_FILTER", "value")
        self.status = name


class FieldstopPlugin(BasePlugin):

    DEVICE_NAME = "VAMPIRES_FIELDSTOP"

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
        self.fieldstop = connect(self.DEVICE_NAME)

        # yapf: disable
        self.shortcut_map = {
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
            buts.Shortcut(pgmc.K_s, pgmc.KMOD_LCTRL): self.save_config,
        }
        # yapf: enable

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
            nudge_value = sign * 0.02
        else:
            nudge_value = sign * 1
        self.backend_obj.logger.info(f"Moving {substage} by {nudge_value} mm")
        self.fieldstop.move_relative__oneway(substage, nudge_value)

    def change_fieldstop(self, index: int):
        self.backend_obj.logger.info(
                f"Moving fieldstop to configuration {index}")
        self.fieldstop.move_configuration_idx__oneway(index)
        self.current_index = index

    def save_config(self):
        if self.current_index is None:
            self.backend_obj.logger.info(
                    "Must have selected a mask before saving its configuration")
            return
        else:
            index = self.current_index
        self.backend_obj.logger.info(
                f"Saving position for configuration {index}")
        self.fieldstop.save_configuration(index=index)
        self.fieldstop.update_keys()

    def frontend_action(self) -> None:
        self.label.render(self.status,
                          blit_onto=self.frontend_obj.pg_datasurface)
        # self.frontend_obj.pg_updated_rects.append(self.label.rectangle)

    def backend_action(self) -> None:
        # Warning: this is called every time the window refreshes, i.e. ~20Hz.
        name = RDB.hget("U_FLDSTP", "value")
        self.status = name


class MBIWheelPlugin(BasePlugin):

    DEVICE_NAME = "VAMPIRES_MBI"

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
        self.wheel = connect(self.DEVICE_NAME)

        # yapf: disable
        self.shortcut_map = {
            buts.Shortcut(pgmc.K_LEFTBRACKET, pgmc.KMOD_LCTRL): partial(self.rotate_wheel, pgmc.K_LEFTBRACKET, fine=True),
            buts.Shortcut(pgmc.K_LEFTBRACKET, pgmc.KMOD_LSHIFT): partial(self.rotate_wheel, pgmc.K_LEFTBRACKET, fine=False),
            buts.Shortcut(pgmc.K_RIGHTBRACKET, pgmc.KMOD_LCTRL): partial(self.rotate_wheel, pgmc.K_RIGHTBRACKET, fine=True),
            buts.Shortcut(pgmc.K_RIGHTBRACKET, pgmc.KMOD_LSHIFT): partial(self.rotate_wheel, pgmc.K_RIGHTBRACKET, fine=False),
        }
        # yapf: enable

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
        self.backend_obj.logger.info(f"Rotating MBI wheel by {nudge_value} deg")
        self.wheel.move_relative__oneway("theta", nudge_value)

    def frontend_action(self) -> None:
        self.label.render(self.status,
                          blit_onto=self.frontend_obj.pg_datasurface)

    def backend_action(self) -> None:
        # Warning: this is called every time the window refreshes, i.e. ~20Hz.
        name = RDB.hget("U_MBI", "value")
        self.status = name


class VAMPIRESPupilMode(PupilMode):

    DEVICE_NAME = "VAMPIRES_PUPIL"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pupil_lens = connect(self.DEVICE_NAME)

    def backend_action(self) -> None:
        name = RDB.hget("U_PUPIL", "value")
        self.status = name

    def enable(self) -> None:  # Override

        # SEND COMMAND TO SWITCH TO PUPIL MODE
        # Can be async, we don't care. Or do we?
        # Could be pyro, could be os.system...
        self.backend_obj.logger.info("Inserting pupil lens")

        if self.textbox:
            self.textbox.render(('PUPIL', ), fg_col=futs.Colors.BLACK)
        self.pupil_lens.move_configuration_name__oneway("IN")

    def disable(self) -> None:  # Override

        # SEND COMMAND TO SWITCH OUT OF PUPIL MODE
        # Could be pyro, could be os.system...

        self.backend_obj.logger.info("Removing pupil lens")
        self.pupil_lens.move_configuration_name__oneway("OUT")
