from __future__ import annotations

import typing as typ

import os

_CORES = os.sched_getaffinity(0)  # AMD fix
import pygame
import pygame.constants as pgmc

os.sched_setaffinity(0, _CORES)  # AMD fix

import logging
import numpy as np

from functools import partial

from rich.panel import Panel
from rich.live import Live
from rich.logging import RichHandler

from scxconf.pyrokeys import VAMPIRES

from swmain.redis import get_values
from swmain.network.pyroclient import connect

from .pygame_viewer_frontend import PygameViewerFrontend
from ..viewertools.generic_viewer_backend import GenericViewerBackend

from . import utils_backend as buts
from . import utils_frontend as futs
from .plugin_arch import BasePlugin, OnOffPlugin
from .image_stacking_plugins import DarkAcquirePlugin
from .plugins import PupilMode, CrossHairPlugin, BullseyePlugin

logger = logging.getLogger()


class DeviceMixin:
    """
    Simply connects to a pyro device using a class property
    """
    DEVICE_NAME = ""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.device = connect(self.DEVICE_NAME)


class MaskWheelPlugin(DeviceMixin, BasePlugin):

    DEVICE_NAME = VAMPIRES.MASK

    def __init__(self, frontend_obj: PygameViewerFrontend) -> None:
        super().__init__(frontend_obj)
        zoom = self.frontend_obj.fonts_zoom
        font = pygame.font.SysFont("default", 20 * zoom)
        self.enabled = True
        # Ideally you'd instantiate the label in the frontend, cuz different viewers could be wanting the same info
        # displayed at different locations.
        self.label = futs.LabelMessage(
                "%s", font, fg_col=futs.Colors.GREEN, bg_col=None,
                topleft=(10 * zoom,
                         self.frontend_obj.data_disp_size[1] - 20 * zoom))
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
            buts.Shortcut(pgmc.K_7, pgmc.KMOD_LCTRL | pgmc.KMOD_LSHIFT): partial(self.change_wheel, 13),
            buts.Shortcut(pgmc.K_8, pgmc.KMOD_LCTRL | pgmc.KMOD_LSHIFT): partial(self.change_wheel, 14),
            # buts.Shortcut(pgmc.K_9, pgmc.KMOD_LCTRL | pgmc.KMOD_LSHIFT): partial(self.change_wheel, 15),
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
        self.device.move_relative__oneway(substage, nudge_value)

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
        self.device.move_relative__oneway("theta", nudge_value)

    def change_wheel(self, index: int):
        name = None
        for config in self.device.get_configurations():
            if config["idx"] == index:
                name = config["name"]
                break
        self.backend_obj.logger.info(
                f"Moving wheel to configuration {index}: {name}")
        self.device.move_configuration_idx__oneway(index)
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
        self.device.save_configuration(index=index)
        self.device.update_keys()

    def frontend_action(self) -> None:
        if not self.enabled:
            return
        self.label.render(self.status,
                          blit_onto=self.frontend_obj.pg_datasurface)
        self.frontend_obj.pg_updated_rects.append(self.label.rectangle)

    def backend_action(self) -> None:
        # Warning: this is called every time the window refreshes, i.e. ~20Hz.
        try:
            name = get_values(("U_MASK", ))["U_MASK"]
            self.status = name
        except:
            pass
        if not self.enabled:
            return


class FilterWheelPlugin(DeviceMixin, BasePlugin):

    DEVICE_NAME = VAMPIRES.FILT

    def __init__(self, frontend_obj: PygameViewerFrontend) -> None:
        super().__init__(frontend_obj)
        zoom = self.frontend_obj.fonts_zoom
        font = pygame.font.SysFont("default", 15 * zoom)
        self.enabled = True
        # Ideally you'd instantiate the label in the frontend, cuz different viewers could be wanting the same info
        # displayed at different locations.
        r = 7 * zoom
        self.label = futs.LabelMessage(
                "%8s", font, fg_col=futs.Colors.GREEN, bg_col=None,
                topright=(self.frontend_obj.data_disp_size[0] - 30 * zoom, r))

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
        _, filt = self.device.get_configuration(index)
        self.backend_obj.logger.info(
                f"Moving filter to position {index}: {filt}")
        self.device.move_configuration_idx__oneway(index)

    def frontend_action(self) -> None:
        if not self.enabled:
            return
        if self.label:
            self.label.blit(self.frontend_obj.pg_datasurface)
            self.frontend_obj.pg_updated_rects.append(self.label.rectangle)

    def backend_action(self) -> None:
        if not self.enabled:
            return
        # Warning: this is called every time the window refreshes, i.e. ~20Hz.
        try:
            filter_dict = get_values(("U_FILTER", ))
            if self.label:
                self.label.render(f"{filter_dict['U_FILTER'].upper():>7s}")
        except:
            pass


class DiffFilterWheelPlugin(DeviceMixin, BasePlugin):

    DEVICE_NAME = VAMPIRES.DIFF

    def __init__(self, frontend_obj: PygameViewerFrontend) -> None:
        super().__init__(frontend_obj)
        zoom = self.frontend_obj.fonts_zoom
        font = pygame.font.SysFont("default", 10 * zoom)
        self.enabled = True
        # Ideally you'd instantiate the label in the frontend, cuz different viewers could be wanting the same info
        # displayed at different locations.
        r = 20 * zoom
        self.label = futs.LabelMessage(
                "%8s", font, fg_col=futs.Colors.GREEN, bg_col=None,
                topright=(self.frontend_obj.data_disp_size[0] - 35 * zoom, r))
        self.label.blit(self.frontend_obj.pg_datasurface)

        # yapf: disable
        self.shortcut_map = {
                buts.Shortcut(pgmc.K_7, pgmc.KMOD_LCTRL | pgmc.KMOD_LSHIFT):
                        partial(self.change_diff_filter, 1),
                buts.Shortcut(pgmc.K_8, pgmc.KMOD_LCTRL | pgmc.KMOD_LSHIFT):
                        partial(self.change_diff_filter, 2),
                buts.Shortcut(pgmc.K_9, pgmc.KMOD_LCTRL | pgmc.KMOD_LSHIFT):
                        partial(self.change_diff_filter, 3),
                buts.Shortcut(pgmc.K_0, pgmc.KMOD_LCTRL | pgmc.KMOD_LSHIFT):
                        partial(self.change_diff_filter, 4),
                buts.Shortcut(pgmc.K_MINUS, pgmc.KMOD_LCTRL | pgmc.KMOD_LSHIFT):
                        partial(self.change_diff_filter, 5),
                buts.Shortcut(pgmc.K_EQUALS, pgmc.KMOD_LCTRL | pgmc.KMOD_LSHIFT):
                        partial(self.change_diff_filter, 6),
            }
        # yapf: enable

    def change_diff_filter(self, index: int):
        for config in self.device.get_configurations():
            if config["idx"] == index:
                name = config["name"]
                break
        else:
            name = "Unknown"
        self.backend_obj.logger.info(
                f"Moving differential filter to position {index}: {name}")
        self.device.move_configuration_idx__oneway(index)

    def frontend_action(self) -> None:
        if not self.enabled:
            return
        if self.label:
            self.label.blit(self.frontend_obj.pg_datasurface)
            self.frontend_obj.pg_updated_rects.append(self.label.rectangle)

    def backend_action(self) -> None:
        if not self.enabled:
            return
        # Warning: this is called every time the window refreshes, i.e. ~20Hz.
        diff_key = f"U_DIFFL{self.backend_obj.cam_num}"
        try:
            diff_filt = get_values((diff_key, ))[diff_key]

            if self.label:
                if diff_filt.upper() == "OPEN":
                    self.label.render_whitespace()
                else:
                    self.label.render(f"{diff_filt.upper():>7s}")
        except:
            pass


class FieldstopPlugin(DeviceMixin, BasePlugin):

    DEVICE_NAME = VAMPIRES.FIELDSTOP

    def __init__(self, frontend_obj: PygameViewerFrontend) -> None:
        super().__init__(frontend_obj)
        zoom = self.frontend_obj.fonts_zoom
        font = pygame.font.SysFont("default", 15 * zoom)
        self.enabled = True
        self.is_offset = False
        # Ideally you'd instantiate the label in the frontend, cuz different viewers could be wanting the same info
        # displayed at different locations.
        self.label = futs.LabelMessage(
                "%s", font, fg_col=futs.Colors.GREEN, bg_col=None,
                topright=(self.frontend_obj.data_disp_size[0] - 60 * zoom,
                          self.frontend_obj.data_disp_size[1] - 15 * zoom))
        self.label.blit(self.frontend_obj.pg_datasurface)
        self.current_index = None

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
            buts.Shortcut(pgmc.K_7, pgmc.KMOD_LCTRL):
                    partial(self.change_fieldstop, 1),
            buts.Shortcut(pgmc.K_8, pgmc.KMOD_LCTRL):
                    partial(self.change_fieldstop, 2),
            buts.Shortcut(pgmc.K_9, pgmc.KMOD_LCTRL):
                    partial(self.change_fieldstop, 3),
            buts.Shortcut(pgmc.K_0, pgmc.KMOD_LCTRL):
                    partial(self.change_fieldstop, 4),
            buts.Shortcut(pgmc.K_MINUS, pgmc.KMOD_LCTRL):
                    partial(self.change_fieldstop, 5),
            buts.Shortcut(pgmc.K_EQUALS, pgmc.KMOD_LCTRL):
                    partial(self.change_fieldstop, 6),
            buts.Shortcut(pgmc.K_PERIOD, pgmc.KMOD_LCTRL):
                    partial(self.nudge_focus, pgmc.K_PERIOD),
            buts.Shortcut(pgmc.K_COMMA, pgmc.KMOD_LCTRL):
                    partial(self.nudge_focus, pgmc.K_COMMA),
            buts.Shortcut(pgmc.K_s, pgmc.KMOD_LCTRL): self.save_config,
            buts.Shortcut(pgmc.K_o, pgmc.KMOD_LCTRL): self.offset_fieldstop
        }
        # yapf: enable

    def nudge_fieldstop(self, key, fine=True):
        sign = 1
        if key == pgmc.K_LEFT:
            substage = "y"
            sign = 1
        elif key == pgmc.K_RIGHT:
            substage = "y"
            sign = -1
        elif key == pgmc.K_UP:
            substage = "x"
            sign = 1
        elif key == pgmc.K_DOWN:
            substage = "x"
            sign = -1

        if fine:
            nudge_value = sign * 0.001
        else:
            nudge_value = sign * 0.05
        self.backend_obj.logger.info(f"Moving {substage} by {nudge_value} mm")
        self.device.move_relative__oneway(substage, nudge_value)

    def nudge_focus(self, key, value=0.05):
        substage = "f"
        if key == pgmc.K_COMMA:
            sign = -1
        elif key == pgmc.K_PERIOD:
            sign = 1
        nudge_value = sign * value
        self.backend_obj.logger.info(f"Moving {substage} by {nudge_value} mm")
        self.device.move_relative__oneway(substage, nudge_value)

    def offset_fieldstop(self, move_out=None):
        if move_out is None:
            move_out = not self.is_offset
        nudge_value = 0.5  # mm
        if not move_out:
            nudge_value *= -1
        self.backend_obj.logger.info(f"Nudging x + y by {nudge_value} mm")
        self.device.move_relative__oneway("x", nudge_value)
        self.device.move_relative__oneway("y", nudge_value)
        self.is_offset = move_out

    def change_fieldstop(self, index: int):
        name = None
        for config in self.device.get_configurations():
            if config["idx"] == index:
                name = config["name"]
                break
        self.backend_obj.logger.info(
                f"Moving field stop to configuration {index}: {name}")
        self.device.move_configuration_idx__oneway(index)
        self.current_index = index

    def save_config(self):
        if self.current_index is None:
            self.backend_obj.logger.info(
                    "Must have selected a mask before saving its configuration")
            return
        else:
            index = self.current_index
        name = None
        for config in self.device.get_configurations():
            if config["idx"] == index:
                name = config["name"]
                break
        self.backend_obj.logger.info(
                f"Saving position for configuration {index}: {name}")
        self.device.save_configuration(index=index)
        self.device.update_keys()

    def frontend_action(self) -> None:
        self.label.render(self.status,
                          blit_onto=self.frontend_obj.pg_datasurface)

    def backend_action(self) -> None:
        # Warning: this is called every time the window refreshes, i.e. ~20Hz.
        if self.is_offset:
            self.status = "OFFSET"
            return
        try:
            name = get_values(("U_FLDSTP", ))["U_FLDSTP"]
            self.status = f"{name.upper():>9s}"
        except:
            pass


class MBIWheelPlugin(DeviceMixin, BasePlugin):

    DEVICE_NAME = VAMPIRES.MBI
    FIELDS = "F610", "F720", "F670", "F760"

    def __init__(self, frontend_obj: PygameViewerFrontend) -> None:
        super().__init__(frontend_obj)
        self.status = None
        self.current_index = None
        self.enabled = True
        # yapf: disable
        self.shortcut_map = {
            buts.Shortcut(pgmc.K_LEFTBRACKET, pgmc.KMOD_LCTRL): partial(self.rotate_wheel, pgmc.K_LEFTBRACKET, fine=True),
            buts.Shortcut(pgmc.K_LEFTBRACKET, pgmc.KMOD_LSHIFT): partial(self.rotate_wheel, pgmc.K_LEFTBRACKET, fine=False),
            buts.Shortcut(pgmc.K_RIGHTBRACKET, pgmc.KMOD_LCTRL): partial(self.rotate_wheel, pgmc.K_RIGHTBRACKET, fine=True),
            buts.Shortcut(pgmc.K_RIGHTBRACKET, pgmc.KMOD_LSHIFT): partial(self.rotate_wheel, pgmc.K_RIGHTBRACKET, fine=False),
            buts.Shortcut(pgmc.K_m, pgmc.KMOD_LCTRL): self.enable,
            buts.Shortcut(pgmc.K_m, pgmc.KMOD_LSHIFT): self.disable,
            buts.Shortcut(pgmc.K_m, pgmc.KMOD_LALT): self.save_configuration,
        }
        # yapf: enable
        zoom = self.frontend_obj.fonts_zoom
        font = pygame.font.SysFont("monospace", 7 * zoom)
        # Ideally you'd instantiate the label in the frontend, cuz different viewers could be wanting the same info
        # displayed at different locations.
        self.field_labels = (
                futs.LabelMessage("%s", font, fg_col=futs.Colors.WHITE,
                                  bg_col=futs.Colors.BLACK, topleft=(0, 0)),
                futs.LabelMessage(
                        "%s", font, fg_col=futs.Colors.WHITE,
                        bg_col=futs.Colors.BLACK,
                        topleft=(0,
                                 self.frontend_obj.data_disp_size[1] / 2 + 2)),
                futs.LabelMessage(
                        "%s", font, fg_col=futs.Colors.WHITE,
                        bg_col=futs.Colors.BLACK,
                        topleft=(self.frontend_obj.data_disp_size[0] / 2 + 2,
                                 0)),
                futs.LabelMessage(
                        "%s", font, fg_col=futs.Colors.WHITE,
                        bg_col=futs.Colors.BLACK,
                        topleft=(self.frontend_obj.data_disp_size[0] / 2 + 2,
                                 self.frontend_obj.data_disp_size[1] / 2 + 2)),
        )

    def rotate_wheel(self, key, fine=True):
        # CCW
        sign = 1
        if key == pgmc.K_LEFTBRACKET:
            sign = 1
        # CW
        elif key == pgmc.K_RIGHTBRACKET:
            sign = -1
        if fine:
            nudge_value = sign * 0.005
        else:
            nudge_value = sign * 0.2
        self.backend_obj.logger.info(f"Rotating MBI wheel by {nudge_value} deg")
        self.device.move_relative__oneway(nudge_value)

    def enable(self):
        self.enabled = True
        self.backend_obj.logger.info(f"Inserting MBI dichroics")
        self.device.move_configuration_name__oneway("dichroics")
        self.current_index, _ = self.device.get_configuration()

    def disable(self):
        self.enabled = False
        self.backend_obj.logger.info(f"Removing MBI dichroics")
        self.device.move_configuration_name__oneway("mirror")
        self.current_index, _ = self.device.get_configuration()

    def save_configuration(self):
        if self.current_index is None:
            self.backend_obj.logger.warn(
                    "Cannot save until a configuration has been selected")
        self.device.save_configuration(index=self.current_index)

    def frontend_action(self) -> None:
        if not self.enabled:
            return
        # we know that if the backend is in MBI mode that we need to label
        # the four frames
        if self.backend_obj.mode.startswith("MBI"):
            for name, label in zip(self.FIELDS[1:], self.field_labels[1:]):
                label.render(f"{name:^6s}",
                             blit_onto=self.frontend_obj.pg_datasurface)

            if self.backend_obj.mode.endswith("REDUCED"):
                self.field_labels[0].render(
                        f"{'NA':^6s}",
                        blit_onto=self.frontend_obj.pg_datasurface)
            else:
                self.field_labels[0].render(
                        f"{self.FIELDS[0]:^6s}",
                        blit_onto=self.frontend_obj.pg_datasurface)

    def backend_action(self) -> None:
        if not self.enabled:
            return
        try:
            name = get_values(("U_MBI", ))["U_MBI"]
            self.status = name.upper()
        except:
            pass


class FocusPlugin(DeviceMixin, BasePlugin):

    DEVICE_NAME = VAMPIRES.FOCUS

    def __init__(self, frontend_obj: PygameViewerFrontend) -> None:
        super().__init__(frontend_obj)
        self.status = None
        self.current_index = None
        self.enabled = True
        # yapf: disable
        self.shortcut_map = {
            buts.Shortcut(pgmc.K_u, pgmc.KMOD_LCTRL): partial(self.nudge_focus, pgmc.K_u, fine=True),
            buts.Shortcut(pgmc.K_u, pgmc.KMOD_LSHIFT): partial(self.nudge_focus, pgmc.K_u, fine=False),
            buts.Shortcut(pgmc.K_i, pgmc.KMOD_LCTRL): partial(self.nudge_focus, pgmc.K_i, fine=True),
            buts.Shortcut(pgmc.K_i, pgmc.KMOD_LSHIFT): partial(self.nudge_focus, pgmc.K_i, fine=False),
        }

    def nudge_focus(self, key, fine=True):
        if key == pgmc.K_u:
            sign = 1
        elif key == pgmc.K_i:
            sign = -1
        else:
            sign = 0

        if fine:
            nudge_value = sign * 0.005
        else:
            # big step
            nudge_value = sign * 0.1
        self.backend_obj.logger.info(f"Nudging focus by {nudge_value} mm")
        self.device.move_relative__oneway(nudge_value)

    def frontend_action(self) -> None:
        pass

    def backend_action(self) -> None:
        pass

class CamFocusPlugin(DeviceMixin, BasePlugin):

    DEVICE_NAME = VAMPIRES.CAMFCS

    def __init__(self, frontend_obj: PygameViewerFrontend) -> None:
        super().__init__(frontend_obj)
        self.status = None
        self.current_index = None
        self.enabled = True
        # yapf: disable
        self.shortcut_map = {
            buts.Shortcut(pgmc.K_l, pgmc.KMOD_LCTRL): partial(self.nudge_focus, pgmc.K_l, fine=True),
            buts.Shortcut(pgmc.K_l, pgmc.KMOD_LSHIFT): partial(self.nudge_focus, pgmc.K_l, fine=False),
            buts.Shortcut(pgmc.K_SEMICOLON, pgmc.KMOD_LCTRL): partial(self.nudge_focus, pgmc.K_SEMICOLON, fine=True),
            buts.Shortcut(pgmc.K_SEMICOLON, pgmc.KMOD_LSHIFT): partial(self.nudge_focus, pgmc.K_SEMICOLON, fine=False),
        }

    def nudge_focus(self, key, fine=True):
        # CCW
        sign = 1
        if key == pgmc.K_l:
            sign = 1
        # CW
        elif key == pgmc.K_SEMICOLON:
            sign = -1
        if fine:
            nudge_value = sign * 0.005
        else:
            # big step
            nudge_value = sign * 0.1
        self.backend_obj.logger.info(f"Nudging cam focus by {nudge_value} mm")
        self.device.move_relative__oneway(nudge_value)

    def frontend_action(self) -> None:
        pass

    def backend_action(self) -> None:
        pass
class VAMPIRESPupilMode(DeviceMixin, PupilMode):

    DEVICE_NAME = VAMPIRES.PUPIL

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        zoom = self.frontend_obj.fonts_zoom
        font = pygame.font.SysFont("default", 15 * zoom)
        self.label = futs.LabelMessage("%s", font, fg_col=futs.Colors.GREEN,
                                       bg_col=None, topleft=(10 * zoom,
                                                             10 * zoom))
        self.status_label = futs.LabelMessage(
                "%s", font, fg_col=futs.Colors.GREEN, bg_col=None,
                topleft=(20 * zoom,
                         self.frontend_obj.data_disp_size[1] - 15 * zoom))
        self.label.blit(self.frontend_obj.pg_datasurface)

    def frontend_action(self) -> None:
        if self.status == "OUT":
            return
        self.label.render("PUPIL", blit_onto=self.frontend_obj.pg_datasurface)
        self.status_label.render(self.mask_name,
                                 blit_onto=self.frontend_obj.pg_datasurface)
        if not self.enabled:
            return

    def backend_action(self) -> None:
        try:
            status_dict = get_values(("U_PUPST", "U_MASK"))
            self.status = status_dict["U_PUPST"].upper()
            self.mask_name = status_dict["U_MASK"].upper()
        except:
            pass
        if not self.enabled:
            return

    def enable(self) -> None:  # Override
        super().enable()

        # SEND COMMAND TO SWITCH TO PUPIL MODE
        # Can be async, we don't care. Or do we?
        # Could be pyro, could be os.system...
        self.backend_obj.logger.info("Inserting pupil lens")
        self.device.move_configuration_name__oneway("in")

    def disable(self) -> None:  # Override
        super().disable()

        # SEND COMMAND TO SWITCH OUT OF PUPIL MODE
        # Could be pyro, could be os.system...
        self.backend_obj.logger.info("Removing pupil lens")
        self.device.move_configuration_name__oneway("out")


class DiffWheelBlockPlugin(DeviceMixin, OnOffPlugin):
    DEVICE_NAME = VAMPIRES.DIFF

    def __init__(self, *args, key_onoff=pgmc.K_d,
                 modifier_and=pgmc.K_LCTRL | pgmc.K_LSHIFT, **kwargs) -> None:
        super().__init__(*args, key_onoff=key_onoff, modifier_and=modifier_and,
                         **kwargs)
        self.curr_posn = None

    def enable(self) -> None:
        super().enable()
        self.curr_posn = self.device.get_position()
        self.device.move_configuration(7)

    def disable(self) -> None:
        super().disable()
        if self.curr_posn is not None:
            self.device.move_absolute(self.curr_posn)

    def frontend_action(self) -> None:
        return super().frontend_action()

    def backend_action(self) -> None:
        return super().backend_action()


class VCAMDarkAcquirePlugin(DeviceMixin, DarkAcquirePlugin):
    DEVICE_NAME = VAMPIRES.DIFF

    def move_appropriate_block(self, in_true: bool) -> None:
        if in_true:
            # don't use __oneway because we don't want to start taking darks
            # until block is fully in
            self.cur_posn = self.device.get_position()
            self.device.move_configuration(7)
        else:
            self.device.move_absolute(self.cur_posn)


class VCAMTriggerPlugin(DeviceMixin, BasePlugin):
    DEVICE_NAME = "VAMPIRES_TRIG"

    HELP_MSG = """trigger control
    ---------------------
    CTRL + e         : Enable external trigger for cameras
    CTRL + ALT + e   : Enable external trigger for this camera only
    SHIFT + e        : Disable external trigger for cameras
    SHIFT + ALT + e  : Enable external trigger for this camera only
    CTRL  + t        : Enable micro-controller trigger
    SHIFT + t        : Disable micro-controller trigger"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.shortcut_map = {
                buts.Shortcut(pgmc.K_e, pgmc.KMOD_LCTRL):
                        partial(self.enable_external_trigger, both=True),
                buts.Shortcut(pgmc.K_e, pgmc.KMOD_LCTRL | pgmc.KMOD_LALT):
                        partial(self.enable_external_trigger, both=False),
                buts.Shortcut(pgmc.K_e, pgmc.KMOD_LSHIFT):
                        partial(self.disable_external_trigger, both=True),
                buts.Shortcut(pgmc.K_e, pgmc.KMOD_LSHIFT | pgmc.KMOD_LALT):
                        partial(self.disable_external_trigger, both=False),
                buts.Shortcut(pgmc.K_t, pgmc.KMOD_LCTRL):
                        self.enable_trigger,
                buts.Shortcut(pgmc.K_t, pgmc.KMOD_LSHIFT):
                        self.disable_trigger,
        }

    def enable_external_trigger(self, both=False):
        self.backend_obj.logger.info(
                f"Enabling external trigger for {self.backend_obj.cam_name}.")
        self.backend_obj.cam.set_external_trigger(True)
        if both:
            self.backend_obj.logger.info(
                    f"Enabling external trigger for {self.backend_obj.other_cam_name}."
            )
            self.backend_obj.other_cam.set_external_trigger(True)

    def disable_external_trigger(self, both=False):
        self.backend_obj.logger.info(
                f"Disabling external trigger for {self.backend_obj.cam_name}.")
        self.backend_obj.cam.set_external_trigger(False)
        if both:
            self.backend_obj.logger.info(
                    f"Disabling external trigger for {self.backend_obj.other_cam_name}."
            )
            self.backend_obj.other_cam.set_external_trigger(False)

    def enable_trigger(self):
        self.backend_obj.logger.info("Enabling hardware trigger")
        self.device.enable()

    def disable_trigger(self):
        self.backend_obj.logger.info("Disabling hardware trigger")
        self.device.disable()

    def frontend_action(self) -> None:
        if not self.enabled:
            return

    def backend_action(self) -> None:
        if not self.enabled:
            return


class MBICrosshairPlugin(CrossHairPlugin):
    pass


class MBIBullseyePlugin(BullseyePlugin):
    pass


class VCAMCompassPlugin(OnOffPlugin):

    def __init__(self, frontend_obj: PygameViewerFrontend,
                 key_onoff: int = pgmc.K_p, modifier_and: int = 0,
                 color=futs.Colors.GREEN, color2=futs.Colors.CYAN, flip_y: bool = False) -> None:
        super().__init__(frontend_obj, key_onoff, modifier_and)
        self.color = color
        self.color2 = color2
        self.imrpap = 0
        self.imrpad = 0
        self.enabled = False
        self.imrpad = None
        self.surface = self.frontend_obj.pg_datasurface
        self.zoom = self.frontend_obj.fonts_zoom
        self.flip_y = flip_y
        font = pygame.font.SysFont("monospace", 4 * (self.zoom + 1))
        self.text_X = font.render("X", True, self.color)
        self.text_X_rect = self.text_X.get_rect()
        self.text_Y = font.render("Y", True, self.color)
        self.text_Y_rect = self.text_Y.get_rect()
        self.text_N = font.render("N", True, self.color2)
        self.text_N_rect = self.text_N.get_rect()
        self.text_E = font.render("E", True, self.color2)
        self.text_E_rect = self.text_E.get_rect()
        self.text_El = font.render("El", True, futs.Colors.RED)
        self.text_El_rect = self.text_El.get_rect()
        self.text_Az = font.render("Az", True, futs.Colors.RED)
        self.text_Az_rect = self.text_Az.get_rect()

    def frontend_action(self) -> None:
        assert self.backend_obj  # mypy happy

        if not self.enabled:  # OK maybe this responsibility could be handled to the caller.
            return

        ## Plot X/Y arrows
        xtot_fe, ytot_fe = self.frontend_obj.data_disp_size
        xc = xtot_fe - 35 * self.zoom
        yc = ytot_fe - 40 * self.zoom
        ctr = np.array((xc, yc))
        length = 12 * self.zoom
        lbl_length = 17 * self.zoom

        # X
        pygame.draw.line(self.surface, self.color, ctr, (xc + length, yc), 2)
        self.text_X_rect.center = xc + lbl_length, yc
        self.surface.blit(self.text_X, self.text_X_rect)
        # Y
        if self.flip_y:
            pygame.draw.line(self.surface, self.color, ctr, (xc, yc + length), 2)
            self.text_Y_rect.center = xc, yc + lbl_length
        else:
            pygame.draw.line(self.surface, self.color, ctr, (xc, yc - length), 2)
            self.text_Y_rect.center = xc, yc - lbl_length

        self.surface.blit(self.text_Y, self.text_Y_rect)
        self.frontend_obj.pg_updated_rects.extend(
                (self.text_X_rect, self.text_Y_rect))

        ## Plot El/Az arrows
        rot_mat = rotation_matrix(self.imrpap)

        # El
        offset_El = rot_mat @ np.array((length, 0)) + ctr
        pygame.draw.line(self.surface, futs.Colors.RED, ctr, offset_El, 2)
        self.text_El_rect.center = rot_mat @ np.array((lbl_length, 0)) + ctr
        self.surface.blit(self.text_El, self.text_El_rect)
        # Az
        offset_Az = rot_mat @ np.array((0, length)) + ctr
        pygame.draw.line(self.surface, futs.Colors.RED, ctr, offset_Az, 2)
        self.text_Az_rect.center = rot_mat @ np.array((0, lbl_length)) + ctr
        self.surface.blit(self.text_Az, self.text_Az_rect)
        self.frontend_obj.pg_updated_rects.extend(
                (self.text_El_rect, self.text_Az_rect))

        ## Plot N/E arrows
        rot_mat = rotation_matrix(self.imrpad)

        # N
        offset_N = rot_mat @ np.array((0, -length)) + ctr
        pygame.draw.line(self.surface, self.color2, ctr, offset_N, 2)
        self.text_N_rect.center = rot_mat @ np.array((0, -lbl_length)) + ctr
        self.surface.blit(self.text_N, self.text_N_rect)
        # E
        offset_E = rot_mat @ np.array((-length, 0)) + ctr
        pygame.draw.line(self.surface, self.color2, ctr, offset_E, 2)
        self.text_E_rect.center = rot_mat @ np.array((-lbl_length, 0)) + ctr
        self.surface.blit(self.text_E, self.text_E_rect)
        self.frontend_obj.pg_updated_rects.extend(
                (self.text_N_rect, self.text_E_rect))

    def backend_action(self) -> None:
        if not self.enabled:
            return
        inst_pa = self.backend_obj.input_shm.get_keywords()["INST-PA"]
        try:
            redis_values = get_values(
                    ("D_IMRPAD", "D_IMRPAP", "ALTITUDE", "AZIMUTH"))
            self.imrpad = redis_values["D_IMRPAD"] + inst_pa
            self.imrpap = redis_values["D_IMRPAP"] + inst_pa
        except:
            pass


def rotation_matrix(angle: float):
    "get 2x2 rotation matrix given angle in degrees"
    theta = np.deg2rad(angle)
    cost = np.cos(theta)
    sint = np.sin(theta)
    R = np.array(((cost, -sint), (sint, cost)))
    return R


class VCAMScalePlugin(OnOffPlugin):

    def __init__(self, frontend_obj: PygameViewerFrontend,
                 key_onoff: int = pgmc.K_i, modifier_and: int = 0,
                 color: str = futs.Colors.GREEN) -> None:
        super().__init__(frontend_obj, key_onoff, modifier_and)
        self.color = color
        self.surface = self.frontend_obj.pg_datasurface
        self.zoom = self.frontend_obj.fonts_zoom
        font = pygame.font.SysFont("monospace", 5 * (self.zoom + 1), bold=True)
        self.platescale = self.eff_plate_scale = (0, 0)  # mas / px
        xtot_fe, ytot_fe = self.frontend_obj.data_disp_size
        self.length = 0.38 * xtot_fe
        self.xc = 7 * self.zoom
        self.yc = ytot_fe - 7 * self.zoom
        self.lbl_y = futs.LabelMessage(
                "%3.01f\"", font, fg_col=self.color, bg_col=None,
                center=(self.xc + 8 * self.zoom,
                        self.yc - self.length - 8 * self.zoom))
        self.lbl_x = futs.LabelMessage(
                "%3.01f\"", font, fg_col=self.color, bg_col=None,
                center=(self.xc + self.length + 15 * self.zoom,
                        self.yc - 2.5 * self.zoom))

    def frontend_action(self) -> None:
        assert self.backend_obj  # mypy happy

        if not self.enabled:  # OK maybe this responsibility could be handled to the caller.
            return

        self.lbl_y.render(self.eff_plate_scale[1] * self.length / 1e3,
                          blit_onto=self.surface)
        self.lbl_x.render(self.eff_plate_scale[0] * self.length / 1e3,
                          blit_onto=self.surface)
        self.frontend_obj.pg_updated_rects.extend(
                (self.lbl_y.rectangle, self.lbl_x.rectangle))

        # Main axis lines
        pygame.draw.line(self.surface, self.color, (self.xc, self.yc),
                         (self.xc, self.yc - self.length), 2)
        pygame.draw.line(self.surface, self.color, (self.xc, self.yc),
                         (self.xc + self.length, self.yc), 2)

        # Tickpoints
        N = 5
        div = self.length / N
        width = 7
        for i in range(N):
            offset = div * (i + 1)
            # y axis
            pygame.draw.line(self.surface, self.color,
                             (self.xc, self.yc - offset),
                             (self.xc + width, self.yc - offset), 2)
            # x axis
            pygame.draw.line(self.surface, self.color,
                             (self.xc + offset, self.yc),
                             (self.xc + offset, self.yc - width), 2)

    def backend_action(self) -> None:
        if not self.enabled:
            return
        cam_kwds = self.backend_obj.input_shm.get_keywords()
        pxscale = np.array((cam_kwds["CDELT1"], cam_kwds["CDELT2"])) * 3.6e6 # deg -> mas
        self.platescale = np.abs(pxscale)
        self.eff_plate_scale = self.platescale / 2**self.backend_obj.crop_lvl_id
        if "MBI" in self.backend_obj.mode:
            self.eff_plate_scale *= 2
