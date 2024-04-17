from __future__ import annotations

import time
from math import nan
from swmain import redis

from ..viewertools import utils_frontend as futs
from ..viewertools.generic_viewer_backend import GenericViewerBackend
from ..viewertools.pygame_viewer_frontend import PygameViewerFrontend


class PueoViewerFrontend(PygameViewerFrontend):

    BOTTOM_PX_PAD = 120

    WINDOW_NAME = 'Pueo PyWFS'

    HELP_MSG: str = """
PUEO Camera Viewer
=======================================
h           : display this help message
x, ESC      : quit viewer

Display controls:
--------------------------------------------------
c         : display cross
k         : display camera SHM keywords
d         : subtract dark frame
CTRL + b  : acquire dark frame (uses pywfs_fcs_pickoff)
r         : subtract reference frame
CTRL + r  : acquire reference frame
l         : cycle scaling (lin, root, log)
m         : cycle colormaps
v         : start/stop averaging frames
SPACE     : freeze frame
z         : zoom on the center of the image
SHIFT + z : unzoom image (cycle backwards)
CTRL + z  : reset zoom and crop
ARROWS    : steer crop
f         : Show flux balance arrows

Pywfs specials:
--------------------------------------------------
LCTRL + ARROWS      : steer piezo tip-tilt centers
LCTRL + LSHIFT + ARROWS : same, but larger
LCTRL + LALT + ARROWS   : same, but smaller
RCTRL + ARROWS      : steer pupils on detector
RCTRL + RSHIFT + ARROWS : same, but larger
RCTRL + RALT + ARROWS   : same, but smaller
    """

    CARTOON_FILE = 'Pueo2.png'

    FONTSIZE_OVERRIDE = (20, 15, 5, 10, 10)

    def _init_labels(self) -> int:
        '''
        # So, now we have a problem: there are some labels from the superclass that we don't want.
        # Option 1: rewrite all of _init_labels to avoid calling super()
        # Option 2: set the labels we don't want to black on black, and put our own labels on top of it.
        # Demonstrate option 2 here:

        self.lbl_cropzone.fg_col = self.lbl_cropzone.bg_col
        self.lbl_gain_mfrate = futs.LabelMessage("EMGain = %3d - Mfps = % 4.2f", self.fonts.MONO,
                                                topleft=self.lbl_cropzone.rectangle.topleft)
        '''

        sz = self.system_zoom  # Shorthandy

        self.lbl_block = futs.LabelMessage(
                "%s", self.fonts.DEFAULT_25, fg_col=futs.Colors.RED,
                bg_col=futs.Colors.BLACK,
                center=(int(self.pygame_win_size[0] // 2), 7 * sz))

        self.lbl_whatfilt = futs.LabelMessage(
                "%s", self.fonts.DEFAULT_16, fg_col=futs.Colors.BLUE,
                bg_col=None, center=(int(self.pygame_win_size[0] * 3 // 4),
                                     self.data_disp_size[1] - 7 * sz))
        self.lbl_whatpickoff = futs.LabelMessage(
                "%s", self.fonts.DEFAULT_16, fg_col=futs.Colors.GREEN,
                bg_col=None, center=(int(self.pygame_win_size[0] * 1 // 4),
                                     self.data_disp_size[1] - 7 * sz))

        # r, c used to count line increments in bottom region
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

        # Gain and MFRATE
        self.lbl_gain_mfrate = futs.LabelMessage("EMGain = %3d - Mfps = % 4.2f",
                                                 self.fonts.MONOBOLD,
                                                 topleft=(c, r))
        r += int(1.2 * self.lbl_gain_mfrate.em_size)

        # XxY - m,M = {} {}
        self.lbl_size_minmax = futs.LabelMessage("%dx%d - m,M = %4.0f,%5.0f ",
                                                 self.fonts.MONOBOLD,
                                                 topleft=(c, r))
        r += int(self.lbl_size_minmax.em_size)

        # mouse = {},{} - flux = {}
        # Not writing X and Y - we don't have them in data coords at this point.
        self.lbl_mouse = futs.LabelMessage("mouse (%4d, %4d) = %6d",
                                           self.fonts.MONOBOLD, topleft=(c, r))
        r += int(self.lbl_mouse.em_size)

        # Backend report (bias, ref, zscale, av, freeze)
        self.lbl_backend = futs.LabelMessage("%-32s", self.fonts.MONOBOLD,
                                             topleft=(c, r))
        r += int(self.lbl_backend.em_size)

        # {scaling type} - {has bias sub}
        self.lbl_saturation = futs.LabelMessage("%28s", self.fonts.MONOBOLD,
                                                topleft=(c, r))
        r += int(1.2 * self.lbl_saturation.em_size)

        # tip-tilt + PIL
        self.lbl_tt = futs.LabelMessage("TT[%.2f, %.2f]", self.fonts.MONO,
                                        topleft=(c, r))
        r += int(1.2 * self.lbl_tt.em_size)
        self.lbl_pil = futs.LabelMessage("PIL[%6d, %6d]", self.fonts.MONO,
                                         topleft=(c, r))
        r += int(1. * self.lbl_pil.em_size)

        # Warning at top: NO REDIS
        self.lbl_no_redis = futs.LabelMessage("%8s", self.fonts.DEFAULT_25,
                                              fg_col=futs.Colors.WHITE,
                                              bg_col=futs.Colors.RED,
                                              topleft=(3 * sz, 3 * sz))

        # {Status message [sat, acquiring dark, acquiring ref...]}
        # At the bottom right.
        self.lbl_status = futs.LabelMessage(
                '%s', self.fonts.DEFAULT_16,
                topright=(self.pygame_win_size[0] - 3 * self.system_zoom,
                          self.pygame_win_size[1] - 10 * self.system_zoom))

        return r

    def _inloop_update_labels(self) -> None:
        assert self.backend_obj

        kws = self.backend_obj.input_shm.get_keywords()
        gain = kws['DETGAIN'] if 'DETGAIN' in kws else -1
        mfrate = kws['MFRATE'] if 'MFRATE' in kws else -1
        size = self.backend_obj.shm_shape

        self.lbl_gain_mfrate.render((gain, mfrate), blit_onto=self.pg_screen)
        self.lbl_size_minmax.render(
                (*size, self.backend_obj.data_min, self.backend_obj.data_max),
                blit_onto=self.pg_screen)
        self.lbl_mouse.render((
                *self.pos_mouse,
                self.value_mouse,
        ), blit_onto=self.pg_screen)
        self.lbl_backend.render((self.backend_obj.str_status_report(), ),
                                blit_onto=self.pg_screen)

        if self.backend_obj.redis_status:
            rd = self.backend_obj.redis_dict
            self.lbl_tt.render((rd['X_ANALGC'], rd['X_ANALGD']),
                               blit_onto=self.pg_screen)
            self.lbl_pil.render((rd['X_PYWPPX'], rd['X_PYWPPY']),
                                blit_onto=self.pg_screen)
            if rd['X_PYWFPK'] == 'IN':
                self.lbl_block.render(('BLOCK', ),
                                      blit_onto=self.pg_datasurface)
            self.lbl_whatfilt.render((rd['X_PYWFLT'], ),
                                     blit_onto=self.pg_datasurface)
            self.lbl_whatpickoff.render((rd['X_PYWPKO'], ),
                                        blit_onto=self.pg_datasurface)
        else:
            self.lbl_tt.render((nan, nan), blit_onto=self.pg_screen)
            self.lbl_pil.render((-1, -1), blit_onto=self.pg_screen)
            self.lbl_no_redis.render(('NO REDIS', ),
                                     blit_onto=self.pg_datasurface)

        self.pg_updated_rects += [
                getattr(obj, 'rectangle') for obj in [
                        self.lbl_gain_mfrate, self.lbl_size_minmax,
                        self.lbl_mouse, self.lbl_backend, self.lbl_tt,
                        self.lbl_pil, self.lbl_no_redis, self.lbl_block,
                        self.lbl_whatfilt, self.lbl_whatpickoff
                ]
        ]


class PueoViewerBackend(GenericViewerBackend):

    def __init__(self, name_shm: str) -> None:
        super().__init__(name_shm)

        self.redis_status: bool = False
        self.redis_dict: dict[str, redis.ScxkwValueType] = {}
        self.redis_last_time: float = time.time()

    def redis_fetch(self) -> None:
        try:
            self.redis_dict = redis.get_values([
                    'X_ANALGC', 'X_ANALGD', 'X_PYWPPX', 'X_PYWPPY', 'X_PYWFPK',
                    'X_PYWPKO', 'X_PYWFLT'
            ])
            self.redis_status = True
        except:
            self.redis_status = False
        self.redis_last_time = time.time()

    def data_iter(self) -> None:
        if time.time() - self.redis_last_time > 0.5:
            self.redis_fetch()

        return super().data_iter()
