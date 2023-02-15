from __future__ import annotations  # For type hints that would otherwise induce circular imports.

from typing import Tuple, TYPE_CHECKING  # For type hints

import os

_CORES = os.sched_getaffinity(0)  # AMD fix
import pygame.constants as pgm_ct

os.sched_setaffinity(0, _CORES)  # AMD fix

from astropy.io import fits
from pyMilk.interfacing.shm import SHM

from camstack.viewers import backend_utils as buts

if TYPE_CHECKING:  # this type hint would cause a circular import
    from camstack.viewers.generic_viewer_frontend import GenericViewerFrontend

from astropy.io import fits
from pyMilk.interfacing.shm import SHM

import numpy as np
from matplotlib import cm
from functools import partial

# class BasicCamViewer:
# More basic, with less text lines at the bottom.


class GenericViewerBackend:

    COLORMAPS_A = [cm.gray, cm.inferno, cm.magma, cm.viridis]
    COLORMAPS_B = [cm.gray, cm.seismic, cm.Spectral]

    COLORMAPS = COLORMAPS_A

    CROP_CENTER_SPOT = None
    MAX_ZOOM_LEVEL = 4  # Power of 2, 4 is 16x, 3 is 8x

    SHORTCUTS = {}  # Do not subclass this, see constructor

    def __init__(self, name_shm: str) -> None:

        self.has_frontend = False

        ### SHM
        self.input_shm = SHM(name_shm, symcode=0)

        ### DATA Pipeline
        self.data_raw_uncrop = None  # Fresh out of SHM
        self.data_debias_uncrop = None  # Debiased (ref, bias, badpix)
        self.data_debias = None  # Cropped
        self.data_zmapped = None  # Apply Z scaling
        self.data_rgbimg = None  # Apply colormap / convert to RGB
        self.data_output = None  # Interpolate to frontend display size

        ### Clipping for pipeline
        self.low_clip, self.high_clip = None, None

        ### Various flags
        self.flag_data_init = False
        self.flag_averaging = False
        self.flag_non_linear = False

        ### COLORING
        self.cmap_id = 1
        self.toggle_cmap(self.cmap_id)  # Select startup CM

        ### SIZING
        self.shm_shape = self.input_shm.shape
        self.crop_lvl_id = 0
        if self.CROP_CENTER_SPOT is None:
            self.CROP_CENTER_SPOT = self.shm_shape[0] / 2, self.shm_shape[1] / 2
        self.toggle_crop(self.crop_lvl_id)

        ### Colors

        # WIP: find a way to process modifiers.
        prep_shortcuts = {
                pgm_ct.K_m: self.toggle_cmap,
                pgm_ct.K_l: self.toggle_scaling,
                pgm_ct.K_z: self.toggle_crop,
                pgm_ct.K_v: self.toggle_averaging,
                pgm_ct.K_UP: partial(self.steer_crop, pgm_ct.K_UP),
                pgm_ct.K_DOWN: partial(self.steer_crop, pgm_ct.K_DOWN),
                pgm_ct.K_LEFT: partial(self.steer_crop, pgm_ct.K_LEFT),
                pgm_ct.K_RIGHT: partial(self.steer_crop, pgm_ct.K_RIGHT),
        }
        # Note escape and X are reserved for quitting

        self.SHORTCUTS.update({
                buts.encode_shortcuts(scut): prep_shortcuts[scut]
                for scut in prep_shortcuts
        })

    def register_frontend(self, frontend: GenericViewerFrontend) -> None:

        self.frontend_obj = frontend
        self.has_frontend = True
        # Now there's the problem of the reverse-bind of text boxes to mode objects

    def toggle_cmap(self, which: int = None) -> None:
        if which is None:
            self.cmap_id = (self.cmap_id + 1) % len(self.COLORMAPS)
        else:
            self.cmap_id = which
        self.cmap = self.COLORMAPS[self.cmap_id]

    def toggle_scaling(self, value: int = None) -> None:
        if value is None:
            self.flag_non_linear = (self.flag_non_linear + 1) % 3
        else:
            self.flag_non_linear = value

    def toggle_crop(self, which: int = None) -> None:
        if which is None:
            self.crop_lvl_id = (self.crop_lvl_id + 1) % (self.MAX_ZOOM_LEVEL +
                                                         1)
        else:
            self.crop_lvl_id = which

        halfside = (self.shm_shape[0] / 2**(self.crop_lvl_id + 1),
                    self.shm_shape[1] / 2**(self.crop_lvl_id + 1))
        # Could define explicit slices using a self.CROPSLICE. Could be great for buffy PDI.
        cr, cc = self.CROP_CENTER_SPOT

        # Adjust, in case we've just zoomed-out from a crop spot that's too close to the edge!
        cr_temp = min(max(cr, halfside[0]), self.shm_shape[0] - halfside[0])
        cc_temp = min(max(cc, halfside[1]), self.shm_shape[1] - halfside[1])

        if self.crop_lvl_id > 0:
            self.crop_slice = np.s_[
                    int(round(cr_temp -
                              halfside[0])):int(round(cr_temp + halfside[0])),
                    int(round(cc_temp -
                              halfside[1])):int(round(cc_temp + halfside[1]))]
        else:
            self.crop_slice = np.s_[:, :]

    def steer_crop(self, direction) -> None:
        # Move by 1 pixel at max zoom
        move_how_much = 2**(self.MAX_ZOOM_LEVEL - self.crop_lvl_id)
        cr, cc = self.CROP_CENTER_SPOT
        if direction == pgm_ct.K_UP:
            cc -= move_how_much
        elif direction == pgm_ct.K_DOWN:
            cc += move_how_much
        elif direction == pgm_ct.K_LEFT:
            cr -= move_how_much
        elif direction == pgm_ct.K_RIGHT:
            cr += move_how_much

        halfside = (self.shm_shape[0] / 2**(self.crop_lvl_id + 1),
                    self.shm_shape[1] / 2**(self.crop_lvl_id + 1))
        # Prevent overflows
        cr = min(max(cr, halfside[0]), self.shm_shape[0] - halfside[0])
        cc = min(max(cc, halfside[1]), self.shm_shape[1] - halfside[1])

        print(cr, cc, cr - halfside[0], cr + halfside[0], cc - halfside[1],
              cc + halfside[1])
        self.CROP_CENTER_SPOT = cr, cc

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

        self.flag_data_init = True  # Data is now initialized!

    def _data_grab(self) -> None:
        '''
        SHM -> self.data_raw_uncrop
        '''
        if self.flag_averaging and self.flag_data_init:
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
        self.data_debias_uncrop = self.data_raw_uncrop

    def _data_crop(self) -> None:
        '''
        SHM -> self.data_debias_uncrop -> self.data_debias

        Crop, but also compute some uncropped stats
        that will be useful further down the pipeline
        '''
        self.data_min = self.data_raw_uncrop[1:, 1:].min()
        self.data_max = self.data_raw_uncrop[1:, 1:].max()
        self.data_mean = np.mean(self.data_raw_uncrop[1:])

        self.data_debias = self.data_debias_uncrop[self.crop_slice]

    def _data_zscaling(self) -> None:
        '''
        self.data_debias -> self.data_zmapped
        '''
        self.data_plot_min = self.data_debias[1:, 1:].min()
        self.data_plot_max = self.data_debias[1:, 1:].max()

        # Temp variables to distinguish per-frame autoclip (nonlinear modes)
        # Against persistent, user-set clipping
        low_clip, high_clip = self.low_clip, self.high_clip

        if low_clip is None and self.flag_non_linear != 0:
            # Clip to the 80-th percentile (for log modes by default
            low_clip = np.percentile(self.data_debias[1:, 1:], 0.8)

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

        if self.flag_non_linear == 0:  # linear
            op = lambda x: x
        elif self.flag_non_linear == 1:  # pow .33
            op = lambda x: (x - m)**0.3
        elif self.flag_non_linear == 2:  # log
            op = lambda x: np.log10(x - m + 1)

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
        mods = mods & (~0x1000)

        if (mods, key) in self.SHORTCUTS:
            # Call the mapped callable
            self.SHORTCUTS[(mods, key)]()


class FirstViewerBackend(GenericViewerBackend):
    pass
