from __future__ import annotations

from ..viewertools import utils_frontend as futs
from ..viewertools.generic_viewer_backend import GenericViewerBackend
from ..viewertools.pygame_viewer_frontend import PygameViewerFrontend


class PueoViewerFrontend(PygameViewerFrontend):

    BOTTOM_PX_PAD = 140

    WINDOW_NAME = 'Pueo PyWFS'

    HELP_MSG = """
    """

    CARTOON_FILE = 'Pueo2.png'

    def _init_labels(self) -> int:

        sz = self.system_zoom  # Shorthandy
        r = self.data_disp_size[1] + 3 * sz
        c = 10 * sz  # Offset from the left margin

        # Generic camera viewer
        self.lbl_title = futs.LabelMessage(self.WINDOW_NAME,
                                           self.fonts.DEFAULT_25, topleft=(c,
                                                                           r))
        self.lbl_title.blit(self.pg_screen)
        r += int(self.lbl_title.em_size)

        # For help press [h]
        self.lbl_help = futs.LabelMessage("Help [h], Quit [x]", self.fonts.MONO,
                                          topleft=(c, r))
        self.lbl_help.blit(self.pg_screen)
        r += int(self.lbl_help.em_size)

        # {Status message [sat, acquiring dark, acquiring ref...]}
        # At the bottom right.
        self.lbl_status = futs.LabelMessage(
                '%s', self.fonts.DEFAULT_16,
                topleft=(8 * self.system_zoom,
                         self.pygame_win_size[1] - 20 * self.system_zoom))
        r += int(1.2 * self.lbl_status.em_size)

        self.lbl_saturation = futs.LabelMessage("%28s", self.fonts.MONO,
                                                topleft=(c, r))
        r += int(1.2 * self.lbl_saturation.em_size)

        return r

    def _inloop_update_labels(self) -> None:
        assert self.backend_obj

        fps = self.backend_obj.input_shm.get_fps()
        tint = self.backend_obj.input_shm.get_expt()  # seconds
        tint_us = tint * 1e6
        tint_ms = tint * 1e3
        ndr = self.backend_obj.input_shm.get_ndr()

        self.pg_updated_rects += []


class PueoViewerBackend(GenericViewerBackend):
    pass
