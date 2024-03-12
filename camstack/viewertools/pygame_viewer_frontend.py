from __future__ import annotations  # For TYPE_CHECKING

import typing as typ
if typ.TYPE_CHECKING:  # this type hint would cause an unecessary import.
    from .generic_viewer_backend import GenericViewerBackend
    from .plugin_arch import BasePlugin

import os, sys

# Affinity fix for pygame messing up
_CORES = os.sched_getaffinity(0)
import pygame
import pygame.constants as pgmc

os.sched_setaffinity(0, _CORES)

from . import utils_frontend as futs
from . import plugins, image_stacking_plugins

import numpy as np
from PIL import Image


class PygameViewerFrontend:

    # A couple numeric constants, can be overriden by subclasses
    BOTTOM_PX_PAD = 100

    WINDOW_NAME = 'Generic viewer'

    HELP_MSG = """
    """

    CARTOON_FILE: str | None = None

    FONTSIZE_OVERRIDE = None  # For overriding the fontbook initialization in subclasses.

    def __init__(self, system_zoom: int, fps: int,
                 display_base_size: tuple[int, int],
                 fonts_zoom: int | None = None) -> None:

        self.has_backend = False
        self.backend_obj: GenericViewerBackend | None = None

        self.system_zoom = system_zoom  # Former z1
        self.fonts_zoom = self.system_zoom if fonts_zoom is None else fonts_zoom

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

        # Cap the fps at 256*256*30 pixels/sec
        self.fps_val = min(
                fps, 256 * 256 * 30 / self.data_disp_size[0] /
                self.data_disp_size[1])

        self.data_blit_staging = np.zeros((*self.data_disp_size, 3),
                                          dtype=np.uint8)
        # Total window size
        self.pygame_win_size = (self.data_disp_size[0], self.data_disp_size[1] +
                                self.BOTTOM_PX_PAD * self.fonts_zoom)

        #####
        # Prep plugins
        #####
        # Probs don't do this? Cuz inheritance problems?
        self.plugins: list[BasePlugin] = []

        #####
        # Prepare the pygame stuff (prefix pygame objects with "pg_")
        #####
        self.pg_clock = pygame.time.Clock()

        pygame.display.init()
        pygame.font.init()

        # Prep the fonts.
        self.fonts = futs.FontBook(self.fonts_zoom, self.FONTSIZE_OVERRIDE)

        self.pg_screen = pygame.display.set_mode(self.pygame_win_size,
                                                 flags=0x0, depth=16)
        pygame.display.set_caption(self.WINDOW_NAME)

        self.pg_background = pygame.surface.Surface(self.pg_screen.get_size(),
                                                    pygame.SRCALPHA)
        # Good to "convert" once-per-surface: converts data type to final one
        self.pg_background = self.pg_background.convert()
        self.pg_background_rect = self.pg_background.get_rect()

        self.pg_datasurface = pygame.surface.Surface(self.data_disp_size)
        self.pg_datasurface.convert()

        self.pg_data_rect = self.pg_datasurface.get_rect()
        self.pg_data_rect.topleft = (0, 0)

        self.pg_updated_rects: list[pygame.rect.Rect] = [
        ]  # For processing in the loop

        #####
        # Mouse
        #####

        self.pos_mouse = (0.0, 0.0)
        self.value_mouse = -1.0

        #####
        # Labels
        #####
        self._init_labels()

        self._init_cartoon()

        #####
        # OnOff states
        #####
        # Generic syntax?
        # {Attribute: callback} dictionary?
        self._init_onoff_modes()

        # TODO class variable

        pygame.mouse.set_cursor(pygame.cursors.broken_x)
        pygame.display.update()

    def _init_labels(self) -> int:

        sz = self.system_zoom  # Shorthandy
        r = self.data_disp_size[1] + 3 * sz
        c = 10 * sz

        # Generic camera viewer
        self.lbl_title = futs.LabelMessage(self.WINDOW_NAME,
                                           self.fonts.DEFAULT_25, topleft=(c,
                                                                           r))
        self.lbl_title.blit(self.pg_screen)
        r += int(1.2 * self.lbl_title.em_size)

        # For help press [h]
        self.lbl_help = futs.LabelMessage("Help press [h], quit [x]",
                                          self.fonts.DEFAULT_25, topleft=(c * 2,
                                                                          r))
        self.lbl_help.blit(self.pg_screen)
        r += int(1.2 * self.lbl_help.em_size)

        # x0,y0 = {or}, {or} - sx,sy = {size}, {size}
        self.lbl_cropzone = futs.LabelMessage("crop = [%4d %4d %4d %4d]",
                                              self.fonts.MONO, topleft=(c, r))
        r += int(self.lbl_cropzone.em_size)

        # t = {t} us - FPS = {fps} - NDR = {NDR}
        self.lbl_times = futs.LabelMessage("t=%6dus - fps %4.0f - NDR=%3d",
                                           self.fonts.MONO, topleft=(c, r))
        r += int(self.lbl_times.em_size)

        # T = {t*NDR} ms - min, max = {} {}
        self.lbl_t_minmax = futs.LabelMessage("T=%3.1fms - m,M=%5.0f,%8.0f",
                                              self.fonts.MONO, topleft=(c, r))
        r += int(self.lbl_times.em_size)

        # mouse = {},{} - flux = {}
        # Not writing X and Y - we don't have them in data coords at this point.
        self.lbl_mouse = futs.LabelMessage("mouse (%4d, %4d) = %6d",
                                           self.fonts.MONO, topleft=(c, r))
        r += int(self.lbl_mouse.em_size)

        # Backend report (bias, ref, zscale, av, freeze)
        self.lbl_backend = futs.LabelMessage("%-32s", self.fonts.MONO,
                                             topleft=(c, r))
        r += int(self.lbl_backend.em_size)

        # {scaling type} - {has bias sub}

        # {Status message [sat, acquiring dark, acquiring ref...]}
        # At the bottom right.
        self.lbl_status = futs.LabelMessage(
                '%s', self.fonts.DEFAULT_16,
                topleft=(8 * self.fonts_zoom,
                         self.pygame_win_size[1] - 20 * self.system_zoom))

        return r

    def _init_cartoon(self) -> None:
        if self.CARTOON_FILE is None:
            return

        # FIXME $CAMSTACK_ROOT instead of $HOME/src/camstack
        path_cartoon = os.environ['HOME'] +\
            f"/src/camstack/conf/{self.CARTOON_FILE}"
        cartoon_img = pygame.image.load(path_cartoon).convert_alpha()

        w, h = cartoon_img.get_size()

        self.cartoon_img_scaled = pygame.transform.scale(
                cartoon_img, (w * self.system_zoom, h * self.system_zoom))

        # Move to bottom right, blit once.
        self.pg_cartoon_rect = self.cartoon_img_scaled.get_rect()
        self.pg_cartoon_rect.bottomright = self.pygame_win_size

        self.pg_screen.blit(self.cartoon_img_scaled, self.pg_cartoon_rect)

    def _init_onoff_modes(self) -> None:
        # That, or an inherited class variable dict?
        # Why a dict actually?
        self.plugins = [
                plugins.CrossHairPlugin(self, pgmc.K_c),
                plugins.CenteredCrossHairPlugin(self, pgmc.K_c,
                                                pgmc.KMOD_LSHIFT),
                image_stacking_plugins.RefImageAcquirePlugin(
                        self, pgmc.K_r, pgmc.KMOD_LCTRL,
                        textbox=self.lbl_status)
        ]

    def _inloop_update_labels(self) -> None:
        assert self.backend_obj

        fps = self.backend_obj.input_shm.get_fps()
        tint = self.backend_obj.input_shm.get_expt()  # seconds
        tint_us = tint * 1e6
        tint_ms = tint * 1e3
        ndr = self.backend_obj.input_shm.get_ndr()

        self.lbl_cropzone.render(tuple(self.backend_obj.input_shm.get_crop()),
                                 blit_onto=self.pg_screen)
        self.lbl_times.render((tint_us, fps, ndr), blit_onto=self.pg_screen)
        self.lbl_t_minmax.render((tint_ms * ndr, self.backend_obj.data_min,
                                  self.backend_obj.data_max),
                                 blit_onto=self.pg_screen)
        self.lbl_mouse.render((
                *self.pos_mouse,
                self.value_mouse,
        ), blit_onto=self.pg_screen)
        self.lbl_backend.render((self.backend_obj.str_status_report(), ),
                                blit_onto=self.pg_screen)

        self.pg_updated_rects += [
                self.lbl_cropzone.rectangle,
                self.lbl_times.rectangle,
                self.lbl_t_minmax.rectangle,
                self.lbl_mouse.rectangle,
                self.lbl_backend.rectangle,
        ]
        #import pdb; pdb.set_trace()

    def _inloop_plugin_modes(self) -> None:
        for plugin in self.plugins:
            plugin.frontend_action()

    def register_backend(self, backend: GenericViewerBackend) -> None:

        self.backend_obj = backend
        self.has_backend = True

        self.backend_obj.cross_register_plugins(self.plugins)

    def run(self) -> None:
        '''
        Post-init loop entry point

        - Calls self.loop_iter()
        - Updates display
        - Calls self.process_pygame_events and propagates quitting.
        - Timer click
        '''
        try:
            while True:
                self.loop_iter()
                pygame.display.update(self.pg_updated_rects)  # type: ignore
                if self.process_pygame_events():
                    break
                self.pg_clock.tick(self.fps_val)
        except KeyboardInterrupt:
            pygame.quit()
            print('Abort loop on KeyboardInterrupt')

    def process_pygame_events(self) -> bool:
        '''
        Process pygame events (mostly keyboard shortcuts)

        Returns True if and only if quitting
        '''
        assert self.backend_obj

        for event in pygame.event.get():
            modifiers = pygame.key.get_mods()

            if (event.type == pgmc.QUIT or
                (event.type == pgmc.KEYDOWN and
                 event.key in [pgmc.K_ESCAPE, pgmc.K_x])):
                pygame.quit()
                return True

            elif event.type == pgmc.KEYDOWN:
                self.backend_obj.process_shortcut(modifiers, event.key)

        return False

    def loop_iter(self) -> None:
        assert self.backend_obj

        self.pg_updated_rects = []
        '''
        Call the backend loop iteration and get RGB data.
        '''
        self.backend_obj.data_iter()

        data_output = self.backend_obj.data_rgbimg
        assert data_output is not None  # backend is init, data_output is not None
        '''
        Resize the data, possibly using black edge padding.
        '''
        img = Image.fromarray(data_output)
        data_size_T = (self.data_disp_size[1], self.data_disp_size[0])

        # Rescale and pad if necessary - using PIL is much faster than scipy.ndimage
        # Embedding the system zoom through PIL is also more efficient than doing it in numpy

        # Offset coordinate of the plotted array vs the data_disp region
        # We'll need them for the mouse.

        if data_output.shape[:2] != self.data_disp_basesize:
            row_fac = data_output.shape[0] / self.data_disp_basesize[0]
            col_fac = data_output.shape[1] / self.data_disp_basesize[1]

            if abs(row_fac / col_fac - 1) < 0.05:

                # Rescale both to size, no pad, even if that means a little distortion
                # Not self.data_blit_staging - this is a disposable PIL array.
                data_to_blit = np.asarray(img.resize(data_size_T,
                                                     Image.NEAREST))
                self.last_transform = futs.DrawingTransform(
                        0, self.system_zoom / row_fac, 0,
                        self.system_zoom / col_fac)

            elif row_fac > col_fac:

                # Rescale based on rows, pad columns
                csize = self.system_zoom *\
                                int(round(data_output.shape[1] / row_fac))
                cskip = (self.data_disp_size[1] - csize) // 2
                self.data_blit_staging[:, cskip:-cskip, :] = \
                    np.asarray(img.resize((csize, self.data_disp_size[0]),
                                    Image.NEAREST))
                self.data_blit_staging[:, :cskip, :] = 0
                # This is gonna be trouble with odd sizes, but we should be OK.
                self.data_blit_staging[:, -cskip:, :] = 0

                self.last_transform = futs.DrawingTransform(
                        0, self.system_zoom / row_fac, cskip,
                        self.system_zoom / row_fac)

                data_to_blit = self.data_blit_staging  # Pointer to the internal buffer

            elif col_fac >= row_fac:

                # Rescale based on columns, pad rows
                rsize = self.system_zoom *\
                    int(round(data_output.shape[0] / col_fac))
                rskip = (self.data_disp_size[0] - rsize) // 2
                self.data_blit_staging[rskip:-rskip, :, :] = \
                    np.asarray(img.resize((self.data_disp_size[1], rsize),
                                   Image.NEAREST))
                self.data_blit_staging[:rskip, :, :] = 0
                self.data_blit_staging[-rskip:, :, :] = 0

                self.last_transform = futs.DrawingTransform(
                        rskip, self.system_zoom / col_fac, 0,
                        self.system_zoom / col_fac)

                data_to_blit = self.data_blit_staging  # Pointer to the internal buffer

            else:
                raise ValueError("row_fac / col_fac calculation messed up.")

        else:  # Data is the native display size. One would wonder why we resize at all?
            data_to_blit = np.asarray(img.resize(data_size_T, Image.NEAREST))
            self.last_transform = futs.DrawingTransform(0, self.system_zoom, 0,
                                                        self.system_zoom)

        pygame.surfarray.blit_array(self.pg_datasurface, data_to_blit)
        '''
        Process the mouse
        '''
        self._process_mouse_position()
        '''
        Blit background and cute image
        '''
        self.pg_background.fill(futs.Colors.CLEAR)
        self.pg_background.set_alpha(255)
        self.pg_screen.blit(self.pg_background, self.pg_background_rect,
                            special_flags=(pygame.BLEND_RGBA_ADD))
        self.pg_updated_rects.append(self.pg_background_rect)
        if self.CARTOON_FILE is not None:
            self.pg_screen.blit(self.cartoon_img_scaled, self.pg_cartoon_rect)
            self.pg_updated_rects.append(self.pg_cartoon_rect)
        '''
        Plugins
        '''
        self._inloop_plugin_modes()
        '''
        Labels
        '''
        self._inloop_update_labels()
        '''
        Finish it all.
        '''
        self.pg_screen.blit(self.pg_datasurface, self.pg_data_rect)
        self.pg_updated_rects += [self.pg_data_rect]

    def _process_mouse_position(self) -> None:
        '''
        There is actually a more generic case of coordinate conversion...

        - We get the position of the mouse within data_blit_staging.
        - Convert it to coords in the data_crop of the backend
        - Convert it to coords in the data_raw_uncrop of the backend

        This function ought to set self.pos_mouse and self.value_mouse
        '''
        pos_mouse = pygame.mouse.get_pos()

        # Check the cursor is within the data area.
        # We still assert here the data area starts at the top left corner.
        if not (pos_mouse[0] < self.data_blit_staging.shape[0] and
                pos_mouse[1] < self.data_blit_staging.shape[1]):
            self.value_mouse = -1
            return

        lt = self.last_transform

        # Convert coords to the data_output of the backend.
        row_crop = (pos_mouse[0] - lt.r_offset) / lt.r_scale
        col_crop = (pos_mouse[1] - lt.c_offset) / lt.c_scale

        # Ask backend for a conversion into the uncropped
        assert self.backend_obj is not None
        row_uncrop, col_uncrop = self.backend_obj.uncrop_coordinates(
                row_crop, col_crop)

        self.pos_mouse = (row_uncrop, col_uncrop)
        # print(self.last_transform)
        # print(pos_mouse, self.pos_mouse)

        r_uc, c_uc = int(row_uncrop), int(col_uncrop)
        if (r_uc >= 0 and r_uc < self.backend_obj.shm_shape[0] and c_uc >= 0 and
                    c_uc < self.backend_obj.shm_shape[1]):
            self.value_mouse = self.backend_obj.data_debias_uncrop[r_uc, c_uc]


if __name__ == "__main__":

    from camstack.viewertools.generic_viewer_backend import GenericViewerBackend
    backend = GenericViewerBackend('prout')
    #backend.assign_shortcuts should have been called?

    frontend = PygameViewerFrontend(int(sys.argv[1]), 20, backend.shm_shape)
    frontend.register_backend(backend)
    frontend.run()
