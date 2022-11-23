import os, sys
from typing import Tuple

# X forwarding hijack of libGL.so
# Goal is to supersede the system's libGL.so by a Mesa libGL and avoid
# conflicts between nvidia and non-nvidia machines over x forwarding
# the underlying is equivalent to changing the LD_LIBRARY_PATH at runtime.
# https://stackoverflow.com/questions/1178094/change-current-process-environments-ld-library-path
# Only if X forwarding. Detecting "localhost" in $DISPLAY
if 'localhost:' in os.environ.get('DISPLAY', ''):
    import ctypes
    ctypes.cdll.LoadLibrary(os.environ["HOME"] +
                            "/src/camstack/lib/libGL.so.1")
    print('Activated libGL.so.1 hijack.')

# Affinity fix for pygame messing up
_CORES = os.sched_getaffinity(0)
import pygame
import pygame.constants as pgm_ct

os.sched_setaffinity(0, _CORES)

from camstack.viewers import frontend_utils as futs

import numpy as np
from PIL import Image


class GenericViewerFrontend:

    def __init__(self, system_zoom: int, fps: float,
                 display_base_size: Tuple[int, int]):

        self.has_backend = False

        self.fps_val = fps
        self.system_zoom = system_zoom  # Former z1
        # Data area width x height, before window scale
        self.data_disp_basesize = display_base_size
        self.data_blit_base_staging = np.zeros((*self.data_disp_basesize, 3),
                                               dtype=np.uint8)

        #####
        # Prep geometry
        #####
        # Data area width x height, after window scale
        self.data_disp_size = (self.data_disp_basesize[0] * self.system_zoom,
                               self.data_disp_basesize[1] * self.system_zoom)
        self.data_blit_staging = np.zeros((*self.data_disp_size, 3),
                                          dtype=np.uint8)
        # Total window size
        self.pygame_win_size = (self.data_disp_size[0] * self.system_zoom,
                                self.data_disp_size[1] +
                                100 * self.system_zoom)

        #####
        # Prepare the pygame
        #####
        self.fps_clock = pygame.time.Clock()

        pygame.display.init()
        pygame.font.init()

        # Prefix pygame objects with "pg_"
        self.pg_fonts = futs.gen_zoomed_fonts(self.system_zoom)

        self.pg_screen = pygame.display.set_mode(self.data_disp_size,
                                                 flags=0x0, depth=16)
        pygame.display.set_caption('GenericViewer')

        # Is this useful?
        self.pg_background = pygame.Surface(self.pg_screen.get_size())
        self.pg_background = self.pg_background.convert()  # Is this useful?

        self.pg_datasurface = pygame.surface.Surface(self.data_disp_size)
        self.pg_data_rect = self.pg_datasurface.get_rect()
        self.pg_data_rect.topleft = (0, 0)

        self.pg_updated_rects = []

        pygame.mouse.set_cursor(*pygame.cursors.broken_x)
        pygame.display.update()

    def register_backend(self, backend):

        self.backend_obj = backend
        self.has_backend = True

    def run(self):
        '''
        Post-init loop entry point

        - Calls self.loop_iter()
        - Updates display
        - Calls self.process_pygame_events and propagates quitting.
        - Timer click
        '''
        import time
        try:
            while True:
                self.loop_iter()
                pygame.display.update(self.pg_updated_rects)
                if self.process_pygame_events():
                    break
                self.fps_clock.tick(self.fps_val)
        except KeyboardInterrupt:
            pygame.quit()
            print('Abort loop on KeyboardInterrupt')

    def process_pygame_events(self):
        '''
        Process pygame events (mostly keyboard shortcuts)

        Returns True if and only if quitting
        '''
        for event in pygame.event.get():
            modifiers = pygame.key.get_mods()

            if (event.type == pgm_ct.QUIT or
                (event.type == pgm_ct.KEYDOWN and
                 event.key in [pgm_ct.K_ESCAPE, pgm_ct.K_x])):
                pygame.quit()
                return True

            elif event.type == pgm_ct.KEYDOWN:
                self.backend_obj.process_shortcut(modifiers, event.key)

        return False

    def loop_iter(self):

        self.pg_updated_rects = []

        import numpy as np

        self.backend_obj.data_iter()

        data_output = self.backend_obj.data_rgbimg
        img = Image.fromarray(data_output)

        # Rescale and pad if necessary - using PIL is much faster than scipy.ndimage
        # Embedding the system zoom through PIL is also more efficient than doing it in numpy
        if data_output.shape[:2] != self.data_disp_basesize:
            row_fac = data_output.shape[0] / self.data_disp_basesize[0]
            col_fac = data_output.shape[1] / self.data_disp_basesize[1]

            if abs(row_fac / col_fac - 1) < 0.05:
                # Rescale both to size, no pad, even if that means a little distortion
                self.data_blit_staging = np.asarray(
                        img.resize(self.data_disp_size[::-1], Image.NEAREST))

            elif row_fac > col_fac:
                # Rescale based on rows, pad columns
                csize = self.system_zoom * int(
                        round(data_output.shape[1] / row_fac))
                cskip = (self.data_disp_size[1] - csize) // 2
                self.data_blit_staging[:, cskip:-cskip, :] = np.asarray(
                        img.resize((self.data_disp_size[0], csize),
                                   Image.NEAREST))
                self.data_blit_staging[:, :cskip, :] = 0
                self.data_blit_staging[:,
                                       -cskip:, :] = 0  # This is gonna be trouble with odd sizes, but we should be OK.
            elif col_fac >= row_fac:
                # Rescale based on columns, pad rows
                rsize = self.system_zoom * int(
                        round(data_output.shape[0] / col_fac))
                rskip = (self.data_disp_size[0] - rsize) // 2
                self.data_blit_staging[rskip:-rskip, :, :] = np.asarray(
                        img.resize((rsize, self.data_disp_size[1]),
                                   Image.NEAREST))
                self.data_blit_staging[:rskip, :, :] = 0
                self.data_blit_staging[-rskip:, :, :] = 0
            else:
                raise ValueError

        else:
            self.data_blit_staging = np.asarray(
                    img.resize((self.data_disp_size[::-1]), Image.NEAREST))

        pygame.surfarray.blit_array(self.pg_datasurface,
                                    self.data_blit_staging)
        self.pg_screen.blit(self.pg_datasurface, self.pg_data_rect)
        self.pg_updated_rects += [self.pg_data_rect]

        # NOW.... how to process the graphical callbacks from the backend ???
        # Arrows, text, etc ???


if __name__ == "__main__":

    from camstack.viewers.generic_viewer_backend import GenericViewerBackend
    backend = GenericViewerBackend('prout')
    #backend.assign_shortcuts should have been called?

    frontend = GenericViewerFrontend(int(sys.argv[1]), 20, backend.shm_shape)
    frontend.register_backend(backend)
    frontend.run()
