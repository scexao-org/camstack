from __future__ import annotations

import typing as typ

import os

_CORES = os.sched_getaffinity(0)  # AMD fix
import pygame
import pygame.constants as pgmc

os.sched_setaffinity(0, _CORES)  # AMD fix

import numpy as np

from swmain import redis

if typ.TYPE_CHECKING:
    from .pygame_viewer_frontend import PygameViewerFrontend

from . import backend_utils as buts
from . import frontend_utils as futs

from .plugin_arch import OnOffPlugin, JoystickActionPlugin


class PyWFSFluxPlugin(OnOffPlugin):

    def __init__(self, frontend_obj: PygameViewerFrontend,
                 key_onoff: int = pgmc.K_f, modifier_and: int = 0x0) -> None:
        super().__init__(frontend_obj, key_onoff, modifier_and)

    def frontend_action(self) -> None:

        assert self.backend_obj  # mypy happy

        if not self.enabled:  # OK maybe this responsibility could be handled to the caller.
            return

        zoom = self.frontend_obj.system_zoom
        draw_surf = self.frontend_obj.pg_datasurface

        # Compute arrow lengths,
        abs_root = lambda x: x**0.5 if x >= 0 else -((-x)**.5)
        cx = self.frontend_obj.data_disp_size[0] / 2.
        cy = self.frontend_obj.data_disp_size[1] / 2.
        scaling_factor = min(cx, cy) / 1.414 * zoom
        # Center, which is also where to clip

        diff14_fe = abs_root(self.diff14) * scaling_factor
        diff23_fe = abs_root(self.diff23) * scaling_factor
        diffx_fe = self.diffr**.5 * (self.diffx / self.diffr) * scaling_factor
        diffy_fe = self.diffr**.5 * (self.diffy / self.diffr) * scaling_factor

        pygame.draw.line(draw_surf, futs.Colors.CYAN, (cx, cy),
                         (cx + diff14_fe, cy + diff14_fe), 2)
        pygame.draw.circle(draw_surf, futs.Colors.CYAN,
                           (int(cx + diff14_fe), int(cy + diff14_fe)), 2 * zoom,
                           2)

        pygame.draw.line(draw_surf, futs.Colors.CYAN, (cx, cy),
                         (cx - diff23_fe, cy + diff23_fe), 2)
        pygame.draw.circle(draw_surf, futs.Colors.CYAN,
                           (int(cx - diff23_fe), int(cy + diff23_fe)), 2 * zoom,
                           2)

        pygame.draw.line(draw_surf, futs.Colors.RED, (cx, cy),
                         (cx + diffx_fe, cy + diffy_fe), 2)
        pygame.draw.circle(draw_surf, futs.Colors.RED,
                           (int(cx + diffx_fe), int(cy + diffy_fe)), 2 * zoom,
                           2)

    def backend_action(self) -> None:

        if not self.enabled:
            return

        # Do the effing math
        # Size
        x_be, y_be = self.backend_obj.input_shm.shape
        # Half-cen
        xh_be, yh_be = x_be // 2, y_be // 2

        # Clip to avoid negative noise and division by zero
        flux1 = max(1e-3,
                    np.sum(self.backend_obj.data_debias_uncrop[:xh_be, :yh_be]))
        flux2 = max(1e-3,
                    np.sum(self.backend_obj.data_debias_uncrop[xh_be:, :yh_be]))
        flux3 = max(1e-3,
                    np.sum(self.backend_obj.data_debias_uncrop[:xh_be, yh_be:]))
        flux4 = max(1e-3,
                    np.sum(self.backend_obj.data_debias_uncrop[xh_be:, yh_be:]))

        flux14 = flux1 + flux4
        flux23 = flux2 + flux3

        fluxtot = flux14 + flux23

        self.diff14 = (flux4 - flux1) / flux14
        self.diff23 = (flux3 - flux2) / flux23

        self.diffx = (flux4 + flux2 - flux1 - flux3) / fluxtot
        self.diffy = (flux3 + flux4 - flux2 - flux1) / fluxtot

        self.diffr = max(1e-3, (self.diffx**2 + self.diffy**2)**.5)


class VisPyWFSTipTiltPlugin(JoystickActionPlugin):

    def dispatch_modlevel(self, dir: buts.JoyKeyDirEnum,
                          mod_index: int) -> None:

        tt_push = [0.05, 0.2, 0.5][mod_index]

        push_xy = {
                buts.JoyKeyDirEnum.UP: (-.707, .707),
                buts.JoyKeyDirEnum.DOWN: (.707, -.707),
                buts.JoyKeyDirEnum.LEFT: (-.707, -.707),
                buts.JoyKeyDirEnum.RIGHT: (.707, .707),
        }[dir]

        val_cd = redis.get_values(['X_ANALGC', 'X_ANALGD'])

        new_c = val_cd[0] + push_xy[0] * tt_push
        new_d = val_cd[1] + push_xy[1] * tt_push
        # BLEUARGH - whatever works yo.
        os.system(f'ssh sc2 "analog_output.py voltage C {new_c}"')
        # No detach the first one - they'll collide and one will be ignored.
        os.system(f'ssh sc2 "analog_output.py voltage D {new_d}" &')

    def frontend_action(self):
        pass

    def backend_action(self):
        pass


class VisPyWFSPupilSteerPlugin(JoystickActionPlugin):

    def dispatch_modlevel(self, dir: buts.JoyKeyDirEnum,
                          mod_index: int) -> None:
        pup_push = [500, 3000, 10000][mod_index]

        push_xy = {
                buts.JoyKeyDirEnum.UP: (0.0, 1.0),
                buts.JoyKeyDirEnum.DOWN: (0.0, -1.0),
                buts.JoyKeyDirEnum.LEFT: (-1.0, 0.0),
                buts.JoyKeyDirEnum.RIGHT: (1.0, 0.0),
        }[dir]

        val_cd = redis.get_values(['X_PYWPPX', 'X_PYWPPY'])

        new_c = int(round(val_cd[0] + push_xy[0] * pup_push))
        new_d = int(round(val_cd[1] + push_xy[1] * pup_push))
        # BLEUARGH - whatever works yo.
        # Technically since the axes are decoupled we only need to fire one of these.
        os.system(f'ssh sc2 "pywfs_pup x goto {new_c}"')
        os.system(f'ssh sc2 "pywfs_pup y goto {new_d}"')

    def frontend_action(self):
        pass

    def backend_action(self):
        pass
