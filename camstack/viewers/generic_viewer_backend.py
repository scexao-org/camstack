from typing import Tuple

from astropy.io import fits
from pyMilk.interfacing.shm import SHM

from camstack.viewers import backend_utils as buts

import numpy as np

from matplotlib import cm

# class BasicCamViewer:
# More basic, with less text lines at the bottom.


class GenericViewerBackend:

    COLORMAPS_A = [cm.gray, cm.inferno, cm.magma, cm.viridis]
    COLORMAPS_B = [cm.gray, cm.seismic, cm.Spectral]

    COLORMAPS = COLORMAPS_A

    SHORTCUTS = {}  # Do not subclass this, see constructor

    def __init__(self, name_shm, size_display=None):

        self.has_frontend = False

        ### SHM
        self.input_shm = SHM(name_shm, verbose=False)

        ### DATA Pipeline
        self.data_raw = None  # Fresh out of SHM
        self.data_raw_crop = None  # Cropped to zoom
        self.data_debias = None  # After bias / ref / hotpix processing
        self.data_zmapped = None  # Apply Z scaling
        self.data_rgbimg = None  # Apply colormap / convert to RGB
        self.data_output = None  # Interpolate to frontend display size

        ### Various flags
        self.flag_data_init = False
        self.flag_averaging = False
        self.flag_non_linear = False

        ### COLORING
        self.cmap_id = 1
        self.toggle_cmap(1)  # Select startup CM

        ### SIZING
        self.shm_shape = self.input_shm.shape
        if size_display is None:
            self.size_display = self.shm_shape
        else:
            self.size_display = size_display  # TODO

        ### Colors

        prep_shortcuts = {
            'm': self.toggle_cmap,
            'l': self.toggle_scaling,
            'z': self.toggle_crop,
            'v': self.toggle_averaging,
        }

        self.SHORTCUTS.update({
            buts.encode_shortcuts(scut): prep_shortcuts[scut]
            for scut in prep_shortcuts
        })

    def register_frontend(self, frontend):

        self.frontend_obj = frontend
        self.has_frontend = True
        # Now there's the problem of the reverse-bind of text boxes to mode objects

    def toggle_cmap(self, which=None):
        if which is None:
            self.cmap_id = (self.cmap_id + 1) % len(self.COLORMAPS)
        else:
            self.cmap_id = which
        self.cmap = self.COLORMAPS[self.cmap_id]

    def toggle_scaling(self):
        self.flag_non_linear = not self.flag_non_linear

    def toggle_crop(self):
        pass

    def toggle_averaging(self):
        self.flag_averaging = not self.flag_averaging

    def data_iter(self):
        self._data_grab()
        #TODO crop
        self._data_referencing()
        self._data_zscaling()
        self._data_coloring()

        self.flag_data_init = True

    def _data_grab(self):
        '''
        SHM -> self.data_raw
        '''
        if self.flag_averaging and self.flag_data_init:
            # 5 sec running average - cast to float32 is implicit
            self.data_raw = 0.99 * self.data_raw + 0.01 * self.input_shm.get_data(
            )
        else:
            self.data_raw = self.input_shm.get_data().astype(np.float32)

    def _data_referencing(self):
        '''
        self.data_raw -> self.data_debias
        '''
        self.data_debias = self.data_raw

    def _data_zscaling(self):
        '''
        self.data_debias -> self.data_zmapped
        '''
        self.data_min = self.data_debias[1:].min()
        self.data_max = self.data_debias[1:].max()

        if self.flag_non_linear:  # linear
            # Clip to the 80-th percentile
            data = self.data_debias - np.percentile(self.data_debias, 80)
            data = np.clip(self.data_debias, 0.0, None)
            data = data ** 0.3
        else:
            data = self.data_debias.copy()

        m, M = data.min(), data.max()
        self.data_zmapped = (data - m) / (M-m)

    def _data_coloring(self):
        '''
        self.data_zmapped -> self.data_rgbimg
        '''
        self.data_rgbimg = self.cmap(self.data_zmapped)

    def process_shortcut(self, mods, key):
        '''
            Called from the frontend with the pygame modifiers and the key
            We built self.SHORTCUTS as a (mods, key) using pygame hex values, so
            should be OK.
        '''
        if (mods, key) in self.SHORTCUTS:
            # Call the mapped callable
            self.SHORTCUTS[(mods, key)]()
