from __future__ import annotations  # For type hints that would otherwise induce circular imports.

from typing import (Tuple, Dict, List, Optional as Op, Callable,
                    TYPE_CHECKING)  # For type hints

if TYPE_CHECKING:  # this type hint would cause a circular import
    from .generic_viewer_frontend import GenericViewerFrontend
    from .plugin_arch import BasePlugin

import os

_CORES = os.sched_getaffinity(0)  # AMD fix
import pygame.constants as pgmc

os.sched_setaffinity(0, _CORES)  # AMD fix

from astropy.io import fits
from pyMilk.interfacing.shm import SHM

from . import backend_utils as buts

from astropy.io import fits
from pyMilk.interfacing.shm import SHM

import numpy as np
from matplotlib import cm
from functools import partial

# class BasicCamViewer:
# More basic, with less text lines at the bottom.

# TODO: a batched Redis query.


class GenericViewerBackend:
    HELP_MSG = """
    """

    COLORMAPS_A = [cm.gray, cm.inferno, cm.magma, cm.viridis]
    COLORMAPS_B = [cm.gray, cm.seismic, cm.Spectral]

    COLORMAPS = COLORMAPS_A

    CROP_CENTER_SPOT: Op[Tuple[float, float]] = None
    MAX_ZOOM_LEVEL = 5  # Power of 2, 4 is 16x, 3 is 8x

    SHORTCUTS: Dict[buts.Shortcut,
                    Callable] = {}  # Do not subclass this, see constructor

    def __init__(self, name_shm: str) -> None:

        self.has_frontend = False

        ### SHM
        self.input_shm = SHM(name_shm, symcode=0)

        ### DATA Pipeline
        # yapf: disable
        self.data_raw_uncrop: Op[np.ndarray] = None  # Fresh out of SHM
        self.data_debias_uncrop: Op[np.ndarray] = None  # Debiased (ref, bias, badpix)
        self.data_debias: Op[np.ndarray] = None  # Cropped
        self.data_zmapped: Op[np.ndarray] = None  # Apply Z scaling
        self.data_rgbimg: Op[np.ndarray] = None  # Apply colormap / convert to RGB
        self.data_output: Op[np.ndarray] = None  # Interpolate to frontend display size

        self.data_for_sub_dark: Op[np.ndarray] = None
        self.data_for_sub_ref: Op[np.ndarray] = None
        #yapf: enable

        ### Clipping for pipeline
        self.low_clip: Op[float] = None
        self.high_clip: Op[float] = None

        ### Various flags
        self.flag_subref_on: bool = False
        self.flag_subdark_on: bool = False
        self.flag_data_init: bool = False
        self.flag_averaging: bool = False
        self.flag_non_linear: int = 0

        ### COLORING
        self.cmap_id = 1
        self.toggle_cmap(self.cmap_id)  # Select startup CM

        ### SIZING
        self.shm_shape = self.input_shm.shape
        self.crop_lvl_id = 0
        if self.CROP_CENTER_SPOT is None:
            self.CROP_CENTER_SPOT = self.shm_shape[0] / 2., self.shm_shape[1] / 2.
        self.crop_offset = 0, 0
        self.toggle_crop(self.crop_lvl_id)

        ### Colors

        # yapf: disable
        this_shortcuts: Dict[buts.Shortcut, Callable] = {
                buts.Shortcut(pgmc.K_h, 0x0): self.print_help,
                buts.Shortcut(pgmc.K_m, 0x0): self.toggle_cmap,
                buts.Shortcut(pgmc.K_l, 0x0): self.toggle_scaling,
                buts.Shortcut(pgmc.K_z, 0x0): partial(self.toggle_crop, incr=1),
                buts.Shortcut(pgmc.K_z, pgmc.KMOD_LSHIFT): partial(self.toggle_crop, incr=-1),
                buts.Shortcut(pgmc.K_z, pgmc.KMOD_LCTRL): self.reset_crop,
                buts.Shortcut(pgmc.K_v, 0x0): self.toggle_averaging,
                buts.Shortcut(pgmc.K_UP, 0x0): partial(self.steer_crop, pgmc.K_UP),
                buts.Shortcut(pgmc.K_DOWN, 0x0): partial(self.steer_crop, pgmc.K_DOWN),
                buts.Shortcut(pgmc.K_LEFT, 0x0): partial(self.steer_crop, pgmc.K_LEFT),
                buts.Shortcut(pgmc.K_RIGHT, 0x0): partial(self.steer_crop, pgmc.K_RIGHT),
                buts.Shortcut(pgmc.K_d, 0x0): self.toggle_sub_dark,
                buts.Shortcut(pgmc.K_r, 0x0): self.toggle_sub_ref,
        }
        # yapf: enable
        # Note escape and X are reserved for quitting

        self.SHORTCUTS.update(this_shortcuts)

    def print_help(self):
        if self.frontend_obj:
            print(self.frontend_obj.HELP_MSG)
        print(self.HELP_MSG)

    def register_frontend(self, frontend: GenericViewerFrontend) -> None:

        self.frontend_obj = frontend
        self.has_frontend = True
        # Now there's the problem of the reverse-bind of text boxes to mode objects

    def cross_register_plugins(self, plugins: List[BasePlugin]) -> None:
        self.plugin_objs = plugins

        key_set = set(self.SHORTCUTS.keys())

        for plugin in self.plugin_objs:
            plugin.register_backend(self)

            plugin_keys = set(plugin.shortcut_map.keys())

            if key_set.intersection(plugin_keys):
                raise AssertionError(
                        f'Shortcut collision with {type(plugin)} {plugin}.')

            key_set = key_set.union(plugin_keys)
            self.SHORTCUTS.update(plugin.shortcut_map)

    def _inloop_plugin_action(self) -> None:
        for plugin in self.plugin_objs:
            plugin.backend_action()

    def toggle_cmap(self, which: Op[int] = None) -> None:
        if which is None:
            self.cmap_id = (self.cmap_id + 1) % len(self.COLORMAPS)
        else:
            self.cmap_id = which
        self.cmap = self.COLORMAPS[self.cmap_id]

    def toggle_sub_dark(self, state: Op[bool] = None):
        if state is None:
            state = not self.flag_subdark_on
        if state and self.data_for_sub_dark is not None:
            self.flag_subdark_on = True
            self.flag_subref_on = False
        if not state:
            self.flag_subdark_on = False

    def toggle_sub_ref(self, state: Op[bool] = None):
        if state is None:
            state = not self.flag_subref_on
        if state and self.data_for_sub_ref is not None:
            self.flag_subref_on = True
            self.flag_subdark_on = False
        if not state:
            self.flag_subref_on = False

    def toggle_scaling(self, value: Op[int] = None) -> None:
        if value is None:
            self.flag_non_linear = (self.flag_non_linear + 1) % 3
        else:
            self.flag_non_linear = value

    def toggle_crop(self, which: Op[int] = None, incr: int = 1) -> None:
        if which is None:
            self.crop_lvl_id = (self.crop_lvl_id + incr) % \
                        (self.MAX_ZOOM_LEVEL)
        else:
            self.crop_lvl_id = which

        # Could define explicit slices using a self.CROPSLICE. Could be great for apapane PDI.
        assert self.CROP_CENTER_SPOT
        if self.crop_lvl_id > 0:
            self.crop_slice = self._get_crop_slice(self.CROP_CENTER_SPOT,
                                                   self.shm_shape)
        else:
            self.crop_slice = np.s_[:, :]

    def reset_crop(self) -> None:
        self.crop_lvl_id = -1
        self.CROP_CENTER_SPOT = self.shm_shape[0] / 2, self.shm_shape[1] / 2
        self.toggle_crop()

    def _get_crop_slice(self, center, shape):
        cr, cc = center
        halfside = (shape[0] / 2**(self.crop_lvl_id + 1),
                    shape[1] / 2**(self.crop_lvl_id + 1))
        # Adjust, in case we've just zoomed-out from a crop spot that's too close to the edge!
        cr_temp = min(max(cr, halfside[0]), shape[0] - halfside[0])
        cc_temp = min(max(cc, halfside[1]), shape[1] - halfside[1])
        crop_slice = np.s_[
                int(round(cr_temp -
                          halfside[0])):int(round(cr_temp + halfside[0])),
                int(round(cc_temp -
                          halfside[1])):int(round(cc_temp + halfside[1]))]
        return crop_slice

    def steer_crop(self, direction: int) -> None:
        assert self.CROP_CENTER_SPOT
        assert self.crop_offset

        # Move by 1 pixel at max zoom
        move_how_much = 2**(self.MAX_ZOOM_LEVEL - self.crop_lvl_id)
        cr, cc = self.CROP_CENTER_SPOT
        if direction == pgmc.K_UP:
            cc -= move_how_much
        elif direction == pgmc.K_DOWN:
            cc += move_how_much
        elif direction == pgmc.K_LEFT:
            cr -= move_how_much
        elif direction == pgmc.K_RIGHT:
            cr += move_how_much

        halfside = (self.shm_shape[0] / 2**(self.crop_lvl_id + 1),
                    self.shm_shape[1] / 2**(self.crop_lvl_id + 1))
        # Prevent overflows
        cr = min(max(cr, halfside[0]), self.shm_shape[0] - halfside[0])
        cc = min(max(cc, halfside[1]), self.shm_shape[1] - halfside[1])

        #logg.debugprint(cr, cc, cr - halfside[0], cr + halfside[0], cc - halfside[1],
        #      cc + halfside[1])
        self.CROP_CENTER_SPOT = cr, cc
        og_ctr = self.shm_shape[0] / 2, self.shm_shape[1] / 2
        self.crop_offset = cr - og_ctr[0], cc - og_ctr[1]
        self.toggle_crop(which=self.crop_lvl_id)

    def toggle_averaging(self) -> None:
        self.flag_averaging = not self.flag_averaging
        self.count_averaging = 0

    def set_clipping_values(self, low: float, high: float) -> None:
        self.low_clip = low
        self.high_clip = high

    def data_iter(self) -> None:
        self._data_grab()
        self._data_referencing()
        self._data_crop()
        self._data_zscaling()
        self._data_coloring()

        self._inloop_plugin_action()

        self.flag_data_init = True  # Data is now initialized!

    def _data_grab(self) -> None:
        '''
        SHM -> self.data_raw_uncrop
        '''
        if self.flag_averaging and self.flag_data_init:
            assert self.data_raw_uncrop is not None  # from self.flag_data_init

            nn = self.count_averaging
            self.data_raw_uncrop = self.data_raw_uncrop * (
                    nn / (nn + 1)) + self.input_shm.get_data() / (nn + 1)
            self.count_averaging += 1
        else:
            self.data_raw_uncrop = self.input_shm.get_data().astype(np.float32)

    def _data_referencing(self) -> None:
        '''
        self.data_raw_uncropped -> self.data_debias_uncrop

        Subtract dark, ref, etc
        '''
        assert self.data_raw_uncrop is not None

        if self.flag_subref_on:
            self.data_debias_uncrop = self.data_raw_uncrop - self.data_for_sub_ref
        elif self.flag_subdark_on:
            self.data_debias_uncrop = self.data_raw_uncrop - self.data_for_sub_dark
        else:
            self.data_debias_uncrop = self.data_raw_uncrop

    def _data_crop(self) -> None:
        '''
        SHM -> self.data_debias_uncrop -> self.data_debias

        Crop, but also compute some uncropped stats
        that will be useful further down the pipeline
        '''
        assert self.data_raw_uncrop is not None
        assert self.data_debias_uncrop is not None

        self.data_min = self.data_raw_uncrop[1:, 1:].min()
        self.data_max = self.data_raw_uncrop[1:, 1:].max()
        self.data_mean = np.mean(self.data_raw_uncrop[1:])

        self.data_debias = self.data_debias_uncrop[self.crop_slice]

    def _data_zscaling(self) -> None:
        '''
        self.data_debias -> self.data_zmapped
        '''
        assert self.data_debias is not None

        self.data_plot_min = np.nanmin(self.data_debias[1:, 1:])
        self.data_plot_max = np.nanmax(self.data_debias[1:, 1:])

        # Temp variables to distinguish per-frame autoclip (nonlinear modes)
        # Against persistent, user-set clipping
        low_clip, high_clip = self.low_clip, self.high_clip

        if low_clip is None and self.flag_non_linear != buts.ZScaleEnum.LIN:
            # Clip to the 80-th percentile (for log modes by default
            low_clip = np.nanpercentile(self.data_debias[1:, 1:], 0.8)

        if low_clip:
            m = low_clip
        else:
            m = self.data_plot_min

        if high_clip:
            M = high_clip
        else:
            M = self.data_plot_max

        if low_clip or high_clip:
            data = np.clip(self.data_debias, m, M)
        else:
            data = self.data_debias.copy()

        if self.flag_non_linear == buts.ZScaleEnum.LIN:  # linear
            op = lambda x: x
        elif self.flag_non_linear == buts.ZScaleEnum.ROOT3:  # pow .33
            op = lambda x: (x - m)**0.3
        elif self.flag_non_linear == buts.ZScaleEnum.LOG:  # log
            op = lambda x: np.log10(x - m + 1)
        else:
            raise AssertionError(
                    f"self.flag_non_linear {self.flag_non_linear} is invalid")

        data = op(data)
        m, M = op(m), op(M)

        self.data_zmapped = (data - m) / (M - m)

    def _data_coloring(self) -> None:
        '''
        self.data_zmapped -> self.data_rgbimg
        '''
        # Coloring with cmap, 0-255 uint8, discard alpha channel
        self.data_rgbimg = self.cmap(self.data_zmapped, bytes=True)[:, :, :-1]

    def process_shortcut(self, mods: int, key: int) -> None:
        '''
            Called from the frontend with the pygame modifiers and the key
            We built self.SHORTCUTS as a (mods, key) using pygame hex values, so
            should be OK.
            Or we can import pygame constants...
        '''

        # Willfully ignore numlock
        mods = mods & (~pgmc.KMOD_NUM)

        this_shortcut = buts.Shortcut(key=key, modifier_mask=mods)

        if this_shortcut in self.SHORTCUTS:
            # Call the mapped callable
            self.SHORTCUTS[this_shortcut]()
