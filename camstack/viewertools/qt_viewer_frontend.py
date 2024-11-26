from __future__ import annotations  # For TYPE_CHECKING

import typing as typ
if typ.TYPE_CHECKING:  # this type hint would cause an unecessary import.
    from .generic_viewer_backend import GenericViewerBackend
    from .plugin_arch import BasePlugin

import os, sys

from . import qt_aux
from . import utils_frontend as futs
from . import plugins, image_stacking_plugins

import numpy as np
from PIL import Image

import PyQt5.QtCore as qtc
import PyQt5.QtWidgets as qtw
import PyQt5.QtGui as qtg


class QtViewerFrontend:

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
        self.total_win_size = (self.data_disp_size[0],
                               self.data_disp_size[1] + self.BOTTOM_PX_PAD
                               )  # * self.fonts_zoom)  # UNCLEAR

        #####
        # Prep plugins
        #####
        # Probs don't do this? Cuz inheritance problems?
        self.plugins: list[BasePlugin] = []

        #####
        # Prepare the pygame stuff (prefix pygame objects with "pg_")
        #####

        self.qt_app = qtw.QApplication([])

        # Force the style to be the same on all OSs:
        self.qt_app.setStyle("Fusion")
        # Now use a palette to switch to dark colors:
        self.qt_app.setPalette(qt_aux.make_palette())
        #self.qt_app.setStyleSheet("QLabel{font-size: 14pt;}")

        self.qt_mainwindow = qtw.QMainWindow()
        self.qt_mainwindow.setWindowTitle(self.WINDOW_NAME)

        _top_level_qwidget = qtw.QWidget()
        self.qt_mainwindow.setCentralWidget(_top_level_qwidget)
        self.qt_main_qvbox = qtw.QVBoxLayout(_top_level_qwidget)

        self.qt_main_qvbox.setContentsMargins(0, 0, 0, 0)

        self.qt_img_area = qtw.QLabel()
        self.qt_img_area.setFixedSize(*self.data_disp_size)
        self.qt_img_area.setMouseTracking(True)
        self.qt_img_area.mouseMoveEvent = self._mousemove_callback.__get__(
                self.qt_img_area, type(self.qt_img_area))
        self.last_mousemove_pos_mouse = (0, 0)

        # Prep the fonts.
        self.fonts = qt_aux.FontBookQt(self.fonts_zoom, self.FONTSIZE_OVERRIDE)

        self.qt_main_qvbox.addWidget(self.qt_img_area)
        self.qt_main_qvbox.setSpacing(0)

        #####
        # Mouse
        #####

        self.pos_mouse = (0.0, 0.0)
        self.value_mouse = -1.0

        #####
        # Labels
        #####
        self._init_labels()

        #TODO AM HERE
        #self._init_cartoon()

        #####
        # OnOff states
        #####
        # Generic syntax?
        # {Attribute: callback} dictionary?
        #self._init_onoff_modes()

        self.qt_main_qvbox.insertStretch(-1, 1)

        self.qt_mainwindow.resize(self.qt_img_area.size())  # FIXME base area

    def _init_labels(self) -> None:

        # Generic camera viewer
        self.lbl_title = qt_aux.LabelMessageQt(self.WINDOW_NAME,
                                               self.fonts.DEFAULT_25)
        self.qt_main_qvbox.addWidget(self.lbl_title.qlabel)
        # For help press [h]
        self.lbl_help = qt_aux.LabelMessageQt("Help press [h], quit [x]",
                                              self.fonts.DEFAULT_25,
                                              fg_col=qt_aux.Colors.GREEN,
                                              bg_col=qt_aux.Colors.VERY_RED)
        self.qt_main_qvbox.addWidget(self.lbl_help.qlabel)

        # x0,y0 = {or}, {or} - sx,sy = {size}, {size}
        self.lbl_cropzone = qt_aux.LabelMessageQt("crop = [%4d %4d %4d %4d]",
                                                  self.fonts.MONO)
        self.qt_main_qvbox.addWidget(self.lbl_cropzone.qlabel)
        # t = {t} us - FPS = {fps} - NDR = {NDR}
        self.lbl_times = qt_aux.LabelMessageQt("t=%6dus - fps %4.0f - NDR=%3d",
                                               self.fonts.MONO)
        self.qt_main_qvbox.addWidget(self.lbl_times.qlabel)

        # T = {t*NDR} ms - min, max = {} {}
        self.lbl_t_minmax = qt_aux.LabelMessageQt("T=%3.1fms - m,M=%5.0f,%8.0f",
                                                  self.fonts.MONO)
        self.qt_main_qvbox.addWidget(self.lbl_t_minmax.qlabel)

        # mouse = {},{} - flux = {}
        # Not writing X and Y - we don't have them in data coords at this point.
        self.lbl_mouse = qt_aux.LabelMessageQt("mouse (%4d, %4d) = %6d",
                                               self.fonts.MONO)
        self.qt_main_qvbox.addWidget(self.lbl_mouse.qlabel)

        # Backend report (bias, ref, zscale, av, freeze)
        self.lbl_backend = qt_aux.LabelMessageQt("%-32s", self.fonts.MONO)
        self.qt_main_qvbox.addWidget(self.lbl_backend.qlabel)

        # {scaling type} - {has bias sub}

        # {Status message [sat, acquiring dark, acquiring ref...]}
        # At the bottom right.
        self.lbl_status = qt_aux.LabelMessageQt('%s', self.fonts.DEFAULT_16,
                                                align=qtc.Qt.AlignCenter)
        self.qt_main_qvbox.addWidget(self.lbl_status.qlabel)

    def _init_cartoon(self) -> None:
        if self.CARTOON_FILE is None:
            return

        # FIXME $CAMSTACK_ROOT instead of $HOME/src/camstack
        path_cartoon = os.environ['HOME'] +\
            f"/src/camstack/conf/{self.CARTOON_FILE}"
        cartoon_img = pygame.image.load(path_cartoon).convert_alpha()

        w, h = cartoon_img.get_size()

        self.cartoon_img_scaled = pygame.transform.scale(
                cartoon_img,
                (int(w / h * self.BOTTOM_PX_PAD * self.system_zoom),
                 self.BOTTOM_PX_PAD * self.system_zoom))

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

        self.lbl_cropzone.render(tuple(self.backend_obj.input_shm.get_crop()))
        self.lbl_times.render((tint_us, fps, ndr))
        self.lbl_t_minmax.render((tint_ms * ndr, self.backend_obj.data_min,
                                  self.backend_obj.data_max))
        self.lbl_mouse.render((*self.pos_mouse, self.value_mouse))
        self.lbl_backend.render((self.backend_obj.str_status_report(), ))

    def _inloop_plugin_modes(self) -> None:
        for plugin in self.plugins:
            plugin.frontend_action()

    def register_backend(self, backend: GenericViewerBackend) -> None:

        self.backend_obj = backend
        self.has_backend = True

        self.backend_obj.cross_register_plugins(self.plugins)

    def _initialize_keyboard_shortcuts_for_qt(self):
        assert self.backend_obj is not None

        # Main frontend shortcut
        qtw.QShortcut(qtg.QKeySequence(qtc.Qt.Key_X),
                      self.qt_mainwindow).activated.connect(self.qt_app.quit)
        qtw.QShortcut(qtg.QKeySequence(qtc.Qt.Key_Escape),
                      self.qt_mainwindow).activated.connect(self.qt_app.quit)

        # yapf: disable
        be = self.backend_obj
        from functools import partial
        from . import utils_backend as buts
        from pygame import constants as pgmc
        this_shortcuts: dict[str, typ.Callable] = {
                'h': be.print_help,
                'm': be.toggle_cmap,
                'l': be.toggle_scaling,
                'z': partial(be.toggle_crop, incr=1),
                'shift+z': partial(be.toggle_crop, incr=-1),
                'ctrl+z': be.reset_crop,
                'v': be.toggle_averaging,
                'space': be.toggle_freeze,
                'up': partial(be.steer_crop, pgmc.K_UP),
                'down': partial(be.steer_crop, pgmc.K_DOWN),
                'left': partial(be.steer_crop, pgmc.K_LEFT),
                'right': partial(be.steer_crop, pgmc.K_RIGHT),
                'd': be.toggle_sub_dark,
                'r': be.toggle_sub_ref,
                'k': be.print_keywords,
        }
        # yapf: enable

        for k, call in this_shortcuts.items():
            qtw.QShortcut(qtg.QKeySequence(k),
                          self.qt_mainwindow).activated.connect(call)

    def run(self) -> None:
        '''
        Post-init loop entry point

        - Calls self.loop_iter()
        - Updates display
        - Calls self.process_pygame_events and propagates quitting.
        - Timer click
        '''

        self._initialize_keyboard_shortcuts_for_qt()

        self.qt_mainwindow.show()

        # Should I define a QThread op here?

        self.loop_iter()  # for DEBUG only

        timer = qtc.QTimer()
        timer.setInterval(int(1000. / self.fps_val))
        timer.timeout.connect(self.loop_iter)
        timer.start()

        import signal

        def sigint_handler(*args):
            timer.stop()
            self.qt_app.quit()

        signal.signal(signal.SIGINT, sigint_handler)

        self.qt_app.exec_()

    def loop_iter(self) -> None:
        assert self.backend_obj
        '''
        Call the backend loop iteration and get RGB data.
        '''
        self.backend_obj.data_iter()

        data_output = self.backend_obj.data_rgbimg
        assert data_output is not None  # backend is init, data_output is not None
        '''
        Resize the data, possibly using black edge padding.
        '''

        img = Image.fromarray(np.moveaxis(data_output, 1,
                                          0))  # transpose added for QT.
        data_size_T = self.data_disp_size

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

        qpixmap = qtg.QPixmap.fromImage(
                qtg.QImage(data_to_blit.data, data_size_T[0], data_size_T[1],
                           3 * data_size_T[0], qtg.QImage.Format_RGB888))
        self.qt_img_area.setPixmap(qpixmap)
        #self.qt_pixmap = qtg.QPixmap(*self.data_disp_size)
        '''
        Process the mouse
        '''
        self._process_mouse_position()
        '''
        Blit background and cute image
        '''
        #if self.CARTOON_FILE is not None:
        #    self.pg_screen.blit(self.cartoon_img_scaled, self.pg_cartoon_rect)
        #    self.pg_updated_rects.append(self.pg_cartoon_rect)
        '''
        Labels
        We do labels before plugins, so that
        Plugin-controlled labels render on TOP
        of Frontend-controlled labels.
        '''
        self._inloop_update_labels()
        return
        '''
        Plugins
        '''
        self._inloop_plugin_modes()
        '''
        Finish it all.
        '''
        self.pg_screen.blit(self.pg_datasurface, self.pg_data_rect)
        self.pg_updated_rects += [self.pg_data_rect]

    def _mousemove_callback(self, event) -> None:
        self.last_mousemove_pos_mouse = event.x(), event.y()

    def _process_mouse_position(self) -> None:
        '''
        There is actually a more generic case of coordinate conversion...

        - We get the position of the mouse within data_blit_staging.
        - Convert it to coords in the data_crop of the backend
        - Convert it to coords in the data_raw_uncrop of the backend

        This function ought to set self.pos_mouse and self.value_mouse
        '''
        pos_mouse = self.last_mousemove_pos_mouse

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
    backend = GenericViewerBackend('simuquest')
    #backend.assign_shortcuts should have been called?

    frontend = QtViewerFrontend(int(sys.argv[1]), 20, backend.shm_shape)
    frontend.register_backend(backend)
    backend.register_frontend(frontend)
    frontend.run()
