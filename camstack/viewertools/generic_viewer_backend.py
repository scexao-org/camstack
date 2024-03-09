from __future__ import annotations  # For type hints that would otherwise induce circular imports.

import typing as typ

if typ.TYPE_CHECKING:  # this type hint would cause a circular import
    from .pygame_viewer_frontend import PygameViewerFrontend
    from .plugin_arch import BasePlugin

import os

_CORES = os.sched_getaffinity(0)  # AMD fix
import pygame.constants as pgmc  # For shortcuts

os.sched_setaffinity(0, _CORES)  # AMD fix

from astropy.io import fits
from pyMilk.interfacing.shm import SHM

from . import utils_backend as buts
from .utils_backend import Shortcut as Sc

from astropy.io import fits
from pyMilk.interfacing.shm import SHM

import numpy as np
from matplotlib import cm
from functools import partial


class GenericViewerBackend:
    '''
    Generic Backend class

    Contains various types of functions:
        Initialization functions
        Keyboard shortcut callbacks.
        Graphicsloop
    '''

    HELP_MSG = """
Display controls:
--------------------------------------------------
c         : display cross
k         : display camera SHM keywords
d         : subtract dark frame
r         : subtract reference frame
l         : cycle scaling (lin, root, log)
m         : cycle colormaps
v         : start/stop averaging frames
SPACE     : freeze frame
z         : zoom on the center of the image
SHIFT + z : unzoom image (cycle backwards)
CTRL + z  : reset zoom and crop
ARROWS    : steer crop
    """

    COLORMAPS_A = [cm.gray, cm.inferno, cm.magma, cm.viridis]  # type: ignore
    COLORMAPS_B = [cm.gray, cm.seismic, cm.Spectral]  # type: ignore

    COLORMAPS = COLORMAPS_A

    CROP_CENTER_SPOT: tuple[float, float] | None = None
    MAX_ZOOM_LEVEL = 5  # Power of 2, 4 is 16x, 3 is 8x

    SHORTCUTS: buts.T_ShortcutCbMap = {
    }  # Do not subclass this, see constructor

    def __init__(self, name_shm: str) -> None:

        self.has_frontend = False

        ### SHM
        self.input_shm = SHM(name_shm, symcode=0)

        ### DATA Pipeline
        # yapf: disable
        self.data_raw_uncrop: np.ndarray | None = None  # Fresh out of SHM
        self.data_debias_uncrop: np.ndarray | None = None  # Debiased (ref, bias, badpix)
        self.data_debias: np.ndarray | None = None  # Cropped
        self.data_zmapped: np.ndarray | None = None  # Apply Z scaling
        self.data_rgbimg: np.ndarray | None = None  # Apply colormap / convert to RGB
        self.data_output: np.ndarray | None = None  # Interpolate to frontend display size

        self.data_for_sub_dark: np.ndarray | None = None
        self.data_for_sub_ref: np.ndarray | None = None
        #yapf: enable

        ### Clipping for pipeline
        self.low_clip: float | None = None
        self.high_clip: float | None = None

        ### Various flags
        self.flag_frozenframe: bool = False
        self.flag_subref_on: bool = False
        self.flag_subdark_on: bool = False
        self.flag_data_init: bool = False
        self.flag_averaging: bool = False
        self.idx_zscaling: int = 0

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
        this_shortcuts: buts.T_ShortcutCbMap = {
                Sc(pgmc.K_h, 0x0): self.print_help,
                Sc(pgmc.K_m, 0x0): self.toggle_cmap,
                Sc(pgmc.K_l, 0x0): self.toggle_scaling,
                Sc(pgmc.K_z, 0x0): partial(self.toggle_crop, incr=1),
                Sc(pgmc.K_z, pgmc.KMOD_LSHIFT): partial(self.toggle_crop, incr=-1),
                Sc(pgmc.K_z, pgmc.KMOD_LCTRL): self.reset_crop,
                Sc(pgmc.K_v, 0x0): self.toggle_averaging,
                Sc(pgmc.K_SPACE, 0x0): self.toggle_freeze,
                Sc(pgmc.K_UP, 0x0): partial(self.steer_crop, pgmc.K_UP),
                Sc(pgmc.K_DOWN, 0x0): partial(self.steer_crop, pgmc.K_DOWN),
                Sc(pgmc.K_LEFT, 0x0): partial(self.steer_crop, pgmc.K_LEFT),
                Sc(pgmc.K_RIGHT, 0x0): partial(self.steer_crop, pgmc.K_RIGHT),
                Sc(pgmc.K_d, 0x0): self.toggle_sub_dark,
                Sc(pgmc.K_r, 0x0): self.toggle_sub_ref,
                Sc(pgmc.K_k, 0x0): self.print_keywords,
        }
        # yapf: enable
        # Note escape and X are reserved for quitting

        self.SHORTCUTS.update(this_shortcuts)

    def str_status_report(self) -> str:
        ll: list[str] = [('lin.', '1/3', 'log.')[self.idx_zscaling]]
        if self.flag_averaging:
            ll += ['Ave.']
        if self.flag_frozenframe:
            ll += ['Frozen']
        if self.flag_subdark_on:
            ll += ['-bias']
        if self.flag_subref_on:
            ll += ['-ref']
        return ' | '.join(ll)

    def print_help(self):
        '''
        Callback function.
        Print the frontend's HELP_MSG, then self's.
        '''
        if self.frontend_obj:
            print(self.frontend_obj.HELP_MSG)
        print(self.HELP_MSG)

    def register_frontend(self, frontend: PygameViewerFrontend) -> None:
        '''
        Initialization function.
        Pair this object with a graphical frontend at runtime
        Future use: bind to a frontend object that may not be based on pygame.
        '''
        self.frontend_obj = frontend
        self.has_frontend = True
        # Now there's the problem of the reverse-bind of text boxes to mode objects

    def cross_register_plugins(self, plugins: list[BasePlugin]) -> None:
        '''
        Initialization function.
        Reveive a list of plugins, register self to each and every one.

        Check all shorcuts for redundancies.
        '''
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
        '''
        In-graphicsloop function.
        Toggle a backend (computational) action for each and every plugin.
        '''
        for plugin in self.plugin_objs:
            plugin.backend_action()

    def toggle_cmap(self, which: int | None = None) -> None:
        '''
        Callback function.
        Change colormap.
        '''
        if which is None:
            self.cmap_id = (self.cmap_id + 1) % len(self.COLORMAPS)
        else:
            self.cmap_id = which
        self.cmap = self.COLORMAPS[self.cmap_id]

    def toggle_sub_dark(self, state: bool | None = None):
        '''
        Callback function.
        Toggle dark subtraction.
        '''
        if state is None:
            state = not self.flag_subdark_on
        if state and self.data_for_sub_dark is not None:
            self.flag_subdark_on = True
            self.flag_subref_on = False
        if not state:
            self.flag_subdark_on = False

    def toggle_sub_ref(self, state: bool | None = None):
        '''
        Callback function.
        Toggle reference image subtraction.
        '''
        if state is None:
            state = not self.flag_subref_on
        if state and self.data_for_sub_ref is not None:
            self.flag_subref_on = True
            self.flag_subdark_on = False
        if not state:
            self.flag_subref_on = False

    def toggle_scaling(self, value: int | None = None) -> None:
        '''
        Callback function.
        Toggle scaling (linear -> power root -> log).
        '''
        if value is None:
            self.idx_zscaling = (self.idx_zscaling + 1) % 3
        else:
            self.idx_zscaling = value

    def toggle_crop(self, which: int | None = None, incr: int = 1) -> None:
        '''
        Callback function.
        Toggle zoomed ROI.
        '''
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
        '''
        Callback function.
        Reset croplevel to full frame
        '''
        self.crop_lvl_id = -1
        self.CROP_CENTER_SPOT = self.shm_shape[0] / 2, self.shm_shape[1] / 2
        self.toggle_crop()

    def _get_crop_slice(self, center, shape):
        '''
        Internal function.
        Compute the numpy slice that goes from raw data -> displayed data that
        is used for cropping / zooming.
        '''
        cr, cc = center
        halfside = (shape[0] / 2**(self.crop_lvl_id + 1),
                    shape[1] / 2**(self.crop_lvl_id + 1))
        # Adjust, in case we've just zoomed-out from a crop spot that's too close to the edge!
        cr_temp = min(max(cr, halfside[0]), self.shm_shape[0] - halfside[0])
        cc_temp = min(max(cc, halfside[1]), self.shm_shape[1] - halfside[1])

        cr_low = int(round(cr_temp - halfside[0]))
        cc_low = int(round(cc_temp - halfside[1]))
        cr_high = cr_low + int(2 * halfside[0])
        cc_high = cc_low + int(2 * halfside[1])

        return np.s_[cr_low:cr_high, cc_low:cc_high]

    def steer_crop(self, direction: int) -> None:
        '''
        Callback function.
        In cropped/zoomed mode, steer the center of the zoom over the data buffer.
        '''
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
        '''
        Callback function.
        Toggle continuous frame averaging for display.
        '''
        self.flag_averaging = not self.flag_averaging
        if self.flag_averaging:
            self.flag_frozenframe = False
        self.count_averaging = 0

    def toggle_freeze(self) -> None:
        '''
        Callback function.
        Toggle freeze frame
        '''
        self.flag_frozenframe = not self.flag_frozenframe
        if self.flag_frozenframe:
            self.flag_averaging = False

    def print_keywords(self) -> None:
        '''
        Callback function.
        Print all keywords from SHM to terminal
        '''
        kws = self.input_shm.get_keywords()
        nn = len(kws)
        to_print: list[str] = []
        for kk, (key, val) in enumerate(kws.items()):
            if kk < nn // 2:
                to_print += [f'| {key:<8s} = {val:<16} | ']
            else:
                to_print[kk - nn // 2] += f'{key:<8s} = {val:<16} |'

        print('╭' + '-' * 59 + '╮')
        print('\n'.join(to_print))
        print('╰' + '-' * 59 + '╯')

    def set_clipping_values(self, low: float, high: float) -> None:
        '''
        Unused?
        '''
        self.low_clip = low
        self.high_clip = high

    def data_iter(self) -> None:
        '''
        MAIN In-graphicsloop function.
        Acquires and processes the data and calls the plugin in-loop function.

        It's the GUI's framerating loop that will call this function
        in short, the frontend shall call this during its own loop_iter().
        '''
        if not self.flag_frozenframe:
            self._data_grab()
        self._data_referencing()
        self._data_crop()
        self._data_zscaling()
        self._data_coloring()

        self._inloop_plugin_action()

        self.flag_data_init = True  # Data is now initialized!

    def _data_grab(self) -> None:
        '''
        Data function.
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
        Data function.
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
        Data function.
        SHM -> self.data_debias_uncrop -> self.data_debias

        Crop, but also compute some uncropped stats.
        '''
        assert self.data_raw_uncrop is not None
        assert self.data_debias_uncrop is not None

        self.data_min = self.data_raw_uncrop[1:, 1:].min()
        self.data_max = self.data_raw_uncrop[1:, 1:].max()
        self.data_mean = np.mean(self.data_raw_uncrop[1:])

        self.data_debias = self.data_debias_uncrop[self.crop_slice]

    def _data_zscaling(self) -> None:
        '''
        Data function.

        self.data_debias -> self.data_zmapped
        '''
        assert self.data_debias is not None

        self.data_plot_min = np.nanmin(self.data_debias[1:, 1:])
        self.data_plot_max = np.nanmax(self.data_debias[1:, 1:])

        # Temp variables to distinguish per-frame autoclip (nonlinear modes)
        # Against persistent, user-set clipping
        low_clip, high_clip = self.low_clip, self.high_clip

        if low_clip is None and self.idx_zscaling != buts.ZScaleEnum.LIN:
            # Clip to the 80-th percentile (for log modes by default
            low_clip = np.nanpercentile(self.data_debias[1:, 1:], 0.8)

        if low_clip:
            low = low_clip
        else:
            low = self.data_plot_min

        if high_clip:
            high = high_clip
        else:
            high = self.data_plot_max

        if low_clip or high_clip:
            data = np.clip(self.data_debias, low, high)
        else:
            data = self.data_debias.copy()

        if self.idx_zscaling == buts.ZScaleEnum.LIN:  # linear
            op = lambda x: x
        elif self.idx_zscaling == buts.ZScaleEnum.ROOT3:  # pow .33
            op = lambda x: (x - low)**0.3
        elif self.idx_zscaling == buts.ZScaleEnum.LOG:  # log
            op = lambda x: np.log10(x - low + 1)
        else:
            raise AssertionError(
                    f"self.flag_non_linear {self.idx_zscaling} is invalid")

        data = op(data)
        low, high = op(low), op(high)

        self.data_zmapped = (data - low) / (high - low)

    def _data_coloring(self) -> None:
        '''
        Data function.

        self.data_zmapped -> self.data_rgbimg
        '''
        # Coloring with cmap, 0-255 uint8, discard alpha channel
        self.data_rgbimg = self.cmap(self.data_zmapped, bytes=True)[:, :, :-1]

    def process_shortcut(self, mods: int, key: int) -> None:
        '''
        Main callback dispatch function.

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

    def uncrop_coordinates(self, row_coord: float,
                           col_coord: float) -> tuple[float, float]:
        row_slice, col_slice = self.crop_slice

        assert row_slice.step is None and col_slice.step is None

        row_out, col_out = row_coord, col_coord

        if row_slice.start is not None:
            row_out = row_coord + row_slice.start
        if col_slice.start is not None:
            col_out = col_coord + col_slice.start

        return row_out, col_out
