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

    CROP_CENTER_SPOT = None
    MAX_ZOOM_LEVEL = 4  # Power of 2, 4 is 16x, 3 is 8x

    SHORTCUTS = {}  # Do not subclass this, see constructor

    def __init__(self, name_shm):

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

        prep_shortcuts = {
            'm': self.toggle_cmap,
            'l': self.toggle_scaling,
            'z': self.toggle_crop,
            'v': self.toggle_averaging,
        }
        # Note escape and X are reserved for quitting

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
        self.flag_non_linear = (self.flag_non_linear + 1) % 3

    def toggle_crop(self, which=None):
        if which is None:
            self.crop_lvl_id = (self.crop_lvl_id + 1) % (self.MAX_ZOOM_LEVEL +
                                                         1)
        else:
            self.crop_lvl_id = which

        halfside = (self.shm_shape[0] / 2**(self.crop_lvl_id+1),
                self.shm_shape[1] / 2**(self.crop_lvl_id+1))
        # Could define explicit slices using a self.CROPSLICE. Could be great for buffy PDI.
        cr, cc = self.CROP_CENTER_SPOT
        self.crop_slice = np.s_[int(round(cr -
                                          halfside[0])):int(round(cr + halfside[0])),
                                int(round(cc -
                                          halfside[1])):int(round(cc + halfside[1]))]

        print(self.shm_shape, self.crop_lvl_id, self.crop_slice)

    def toggle_averaging(self):
        self.flag_averaging = not self.flag_averaging

    def data_iter(self):
        self._data_grab()
        self._data_referencing()
        self._data_crop()
        self._data_zscaling()
        self._data_coloring()

        self.flag_data_init = True

    def _data_grab(self):
        '''
        SHM -> self.data_raw_uncrop
        '''
        if self.flag_averaging and self.flag_data_init:
            # 5 sec running average - cast to float32 is implicit
            self.data_raw_uncrop = 0.99 * self.data_raw + 0.01 * self.input_shm.get_data(
            )
        else:
            self.data_raw_uncrop = self.input_shm.get_data().astype(np.float32)

    def _data_referencing(self):
        '''
        self.data_raw_uncropped -> self.data_debias_uncrop

        Subtract dark, ref, etc
        '''
        self.data_debias_uncrop = self.data_raw_uncrop

    def _data_crop(self):
        '''
        SHM -> self.data_debias_uncrop -> self.data_debias

        Crop, but also compute some uncropped stats
        that will be useful further down the pipeline
        '''
        self.data_min = self.data_raw_uncrop[1:].min()
        self.data_max = self.data_raw_uncrop[1:].max()
        self.data_mean = np.mean(self.data_raw_uncrop[1:])

        self.data_debias = self.data_debias_uncrop[self.crop_slice]

    def _data_zscaling(self):
        '''
        self.data_debias -> self.data_zmapped
        '''
        self.data_plot_min = self.data_debias[1:].min()
        self.data_plot_max = self.data_debias[1:].max()

        if self.flag_non_linear == 0: # linear
            data = self.data_debias.copy()
        elif self.flag_non_linear == 1:  # pow .33
            # Clip to the 80-th percentile
            data = self.data_debias - np.percentile(self.data_debias, 80)
            data = np.clip(self.data_debias, 0.0, None)
            data = data**0.3
        elif self.flag_non_linear == 2:  # log
            data = self.data_debias - np.percentile(self.data_debias, 80)
            data = np.clip(self.data_debias, 0.0, None)
            data = np.log10(data + 1)

        m, M = data.min(), data.max()
        self.data_zmapped = (data - m) / (M - m)

    def _data_coloring(self):
        '''
        self.data_zmapped -> self.data_rgbimg
        '''
        # Coloring with cmap, 0-255 uint8, discard alpha channel
        self.data_rgbimg = self.cmap(self.data_zmapped, bytes=True)[:, :, :-1]

    def process_shortcut(self, mods, key):
        '''
            Called from the frontend with the pygame modifiers and the key
            We built self.SHORTCUTS as a (mods, key) using pygame hex values, so
            should be OK.
        '''
        if (mods, key) in self.SHORTCUTS:
            # Call the mapped callable
            self.SHORTCUTS[(mods, key)]()
