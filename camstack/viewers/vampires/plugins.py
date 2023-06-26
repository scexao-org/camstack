from typing import Optional as Op, Optional, Tuple
from camstack.viewers.generic_viewer_frontend import GenericViewerFrontend
from swmain.network.pyroclient import connect
from camstack.viewers.generic_viewer_backend import GenericViewerBackend
from camstack.viewers import backend_utils as buts
from camstack.viewers import frontend_utils as futs
from camstack.viewers.plugin_arch import BasePlugin
from camstack.viewers.image_stacking_plugins import DarkAcquirePlugin
from camstack.viewers.plugins import PupilMode, CrossHairPlugin, BullseyePlugin
import pygame.constants as pgmc
from functools import partial
import pygame
import logging
from swmain.redis import get_values, RDB
from rich.panel import Panel
from rich.live import Live
from rich.logging import RichHandler

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
        self.backend_obj.logger.info(f"Moving wheel to configuration {index}")
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
        name = RDB.hget("U_MASK", "value")
        self.status = name


class FilterWheelPlugin(DeviceMixin, BasePlugin):

    DEVICE_NAME = "VAMPIRES_FILT"

    def __init__(self, frontend_obj: GenericViewerFrontend) -> None:
        super().__init__(frontend_obj)
        zoom = self.frontend_obj.system_zoom
        font = pygame.font.SysFont("default", 30 * zoom)
        self.enabled = True
        # Ideally you'd instantiate the label in the frontend, cuz different viewers could be wanting the same info
        # displayed at different locations.
        r = 20 * zoom
        self.label = futs.LabelMessage(
                "%7s", font, fg_col="#4AC985", bg_col=None,
                topright=(self.frontend_obj.data_disp_size[0] - 100 * zoom, r))
        r += int(1.5 * self.label.em_size)
        self.diff_label = futs.LabelMessage(
                "%7s", font, fg_col="#4AC985", bg_col=None,
                topright=(self.frontend_obj.data_disp_size[0] - 100 * zoom, r))
        self.label.blit(self.frontend_obj.pg_datasurface)

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

        if self.diff_label:
            self.diff_label.blit(self.frontend_obj.pg_datasurface)
            self.frontend_obj.pg_updated_rects.append(self.diff_label.rectangle)

    def backend_action(self) -> None:
        if not self.enabled:
            return
        # Warning: this is called every time the window refreshes, i.e. ~20Hz.
        diff_key = f"U_DIFFL{self.backend_obj.cam_num}"
        filter_dict = get_values(("U_FILTER", diff_key))
        if self.label:
            self.label.render(f"{filter_dict['U_FILTER'].upper():>7s}")
        if self.diff_label:
            if filter_dict[diff_key].upper() == "OPEN":
                self.diff_label.render_whitespace()
            else:
                self.diff_label.render(f"{filter_dict[diff_key].upper():>7s}")


class FieldstopPlugin(DeviceMixin, BasePlugin):

    DEVICE_NAME = "VAMPIRES_FIELDSTOP"

    def __init__(self, frontend_obj: GenericViewerFrontend) -> None:
        super().__init__(frontend_obj)
        zoom = self.frontend_obj.system_zoom
        font = pygame.font.SysFont("default", 30 * zoom)
        self.enabled = True
        # Ideally you'd instantiate the label in the frontend, cuz different viewers could be wanting the same info
        # displayed at different locations.
        self.label = futs.LabelMessage(
                "%s", font, fg_col="#4AC985", bg_col=None,
                topright=(self.frontend_obj.data_disp_size[0] - 120 * zoom,
                          self.frontend_obj.data_disp_size[1] - 30 * zoom))
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
            nudge_value = sign * 0.005
        else:
            nudge_value = sign * 0.1
        self.backend_obj.logger.info(f"Moving {substage} by {nudge_value} mm")
        self.device.move_relative__oneway(substage, nudge_value)

    def change_fieldstop(self, index: int):
        self.backend_obj.logger.info(
                f"Moving fieldstop to configuration {index}")
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
        self.label.render(self.status,
                          blit_onto=self.frontend_obj.pg_datasurface)

    def backend_action(self) -> None:
        # Warning: this is called every time the window refreshes, i.e. ~20Hz.
        name = RDB.hget("U_FLDSTP", "value")
        self.status = f"{name.upper():>9s}"


class MBIWheelPlugin(DeviceMixin, BasePlugin):

    DEVICE_NAME = "VAMPIRES_MBI"
    FIELDS = "F620", "F720", "F670", "F770"

    def __init__(self, frontend_obj: GenericViewerFrontend) -> None:
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
        zoom = self.frontend_obj.system_zoom
        font = pygame.font.SysFont("monospace", 15 * zoom)
        # Ideally you'd instantiate the label in the frontend, cuz different viewers could be wanting the same info
        # displayed at different locations.
        self.field_labels = (
                futs.LabelMessage("%s", font, fg_col=futs.Colors.WHITE,
                                  bg_col=futs.Colors.BLACK, topleft=(5, 5)),
                futs.LabelMessage(
                        "%s", font, fg_col=futs.Colors.WHITE,
                        bg_col=futs.Colors.BLACK,
                        topleft=(5,
                                 self.frontend_obj.data_disp_size[1] / 2 + 5)),
                futs.LabelMessage(
                        "%s", font, fg_col=futs.Colors.WHITE,
                        bg_col=futs.Colors.BLACK,
                        topleft=(self.frontend_obj.data_disp_size[0] / 2 + 5,
                                 5)),
                futs.LabelMessage(
                        "%s", font, fg_col=futs.Colors.WHITE,
                        bg_col=futs.Colors.BLACK,
                        topleft=(self.frontend_obj.data_disp_size[0] / 2 + 5,
                                 self.frontend_obj.data_disp_size[1] / 2 + 5)),
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
        name = RDB.hget("U_MBI", "value")
        self.status = name.upper()


class VAMPIRESPupilMode(DeviceMixin, PupilMode):

    DEVICE_NAME = "VAMPIRES_PUPIL"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        zoom = self.frontend_obj.system_zoom
        font = pygame.font.SysFont("default", 30 * zoom)
        self.label = futs.LabelMessage("%s", font, fg_col="#4AC985",
                                       bg_col=None, topleft=(20 * zoom,
                                                             20 * zoom))
        self.status_label = futs.LabelMessage(
                "%s", font, fg_col="#4AC985", bg_col=None,
                topleft=(20 * zoom,
                         self.frontend_obj.data_disp_size[1] - 30 * zoom))
        self.label.blit(self.frontend_obj.pg_datasurface)

    def frontend_action(self) -> None:
        if self.enabled:
            self.label.render("PUPIL",
                              blit_onto=self.frontend_obj.pg_datasurface)
            self.status_label.render(self.status,
                                     blit_onto=self.frontend_obj.pg_datasurface)

    def backend_action(self) -> None:
        name = RDB.hget("U_MASK", "value")
        self.status = name.upper()

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


class VCAMDarkAcquirePlugin(DeviceMixin, DarkAcquirePlugin):
    DEVICE_NAME = "VAMPIRES_DIFF"

    def move_appropriate_block(self, in_true: bool) -> None:
        if in_true:
            # don't use __oneway because we don't want to start taking darks
            # until block is fully in
            self.device.move_relative(30)
        else:
            self.device.move_relative__oneway(-30)


class MBICrosshairPlugin(CrossHairPlugin):
    pass


class MBIBullseyePlugin(BullseyePlugin):
    pass
