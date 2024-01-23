from camstack.viewertools.generic_viewer_frontend import GenericViewerFrontend
from swmain.network.pyroclient import connect
from camstack.viewertools.generic_viewer_backend import GenericViewerBackend
import logging
from rich.logging import RichHandler
import camstack.viewertools.frontend_utils as futs

logger = logging.getLogger("vpupcam")
stream_handler = RichHandler(level=logging.INFO, show_level=False,
                             show_path=False, log_time_format="%H:%M:%S")
logger.addHandler(stream_handler)


class VAMPIRESPupilCamViewerFrontend(GenericViewerFrontend):
    WINDOW_NAME = "VPUPCAM"
    CARTOON_FILE = "opeapea2.png"

    def _init_labels(self) -> int:

        r = self.data_disp_size[1] + 3 * self.system_zoom
        c = 10 * self.system_zoom

        # Generic camera viewer
        self.lbl_title = futs.LabelMessage(self.WINDOW_NAME,
                                           futs.Fonts.DEFAULT_25, topleft=(c,
                                                                           r))
        self.lbl_title.blit(self.pg_screen)
        r += int(self.lbl_title.em_size)

        self.lbl_help = futs.LabelMessage("For help press [h], quit [x]",
                                          futs.Fonts.MONO, topleft=(c, r))
        self.lbl_help.blit(self.pg_screen)
        r += int(self.lbl_help.em_size)

        self.lbl_cropzone = futs.LabelMessage("crop = [%4d %4d %4d %4d]",
                                              futs.Fonts.MONO, topleft=(c, r))
        self.lbl_cropzone.blit(self.pg_screen)
        r += int(self.lbl_cropzone.em_size)

        self.lbl_times = futs.LabelMessage("t=%5.03f ms - fps= %4.0f",
                                           futs.Fonts.MONO, topleft=(c, r))
        r += int(self.lbl_times.em_size)

        self.lbl_data_val = futs.LabelMessage("m,M=(%5.0f, %5.0f) mu=%5.0f",
                                              futs.Fonts.MONO, topleft=(c, r))
        r += int(1.5 * self.lbl_data_val.em_size)

        # {Status message [sat, acquiring dark, acquiring ref...]}
        # At the bottom right.
        self.lbl_status = futs.LabelMessage("%28s", futs.Fonts.MONO,
                                            topleft=(c, r))
        r += int(self.lbl_status.em_size)
        return r

    def _inloop_update_labels(self) -> None:
        assert self.backend_obj

        fps = self.backend_obj.input_shm.get_fps()
        tint = self.backend_obj.input_shm.get_expt()  # seconds
        tint_ms = tint * 1e3

        self.lbl_cropzone.render(tuple(self.backend_obj.input_shm.get_crop()),
                                 blit_onto=self.pg_screen)
        self.lbl_times.render((tint_ms, fps), blit_onto=self.pg_screen)
        self.lbl_data_val.render(
                (self.backend_obj.data_min, self.backend_obj.data_max,
                 self.backend_obj.data_mean), blit_onto=self.pg_screen)

        self.pg_updated_rects.extend((
                self.lbl_cropzone.rectangle,
                self.lbl_times.rectangle,
                self.lbl_data_val.rectangle,
        ))


class VAMPIRESPupilCamViewerBackend(GenericViewerBackend):
    HELP_MSG = """VPUPCAM controls
=======================================
h           : display this help message
x, ESC      : quit vpupcam

pupil wheel alignment:
-----------------------------------------------------
CTRL  + ARROW : Nudge wheel 0.01 mm in x (left/right)
                                   and y (up/down)
SHIFT + ARROW : Move wheel 1 mm in x (left/right)
                               and y (up/down)
CTRL  + []    : Nudge wheel 0.1 deg in theta (ccw/cw)
SHIFT + []    : Nudge wheel 1 deg in theta (ccw/cw)
CTRL  + S     : Save position to the last configuration

pupil wheel masks:
----------------------------------
CTRL  + 1         : Open (0 deg)
CTRL  + 2         : SAM-7
CTRL  + 3         : SAM-9
CTRL  + 4         : Open (73 deg)
CTRL  + 5         : SAM-18-Nudged
CTRL  + 6         : SAM-Ann-Nudged
CTRL  + 7         : Mirror
CTRL  + 8         : Open (164 deg)
CTRL  + 9         : LyotStop
CTRL  + 0         : RAP
CTRL  + -         : ND10
CTRL  + =         : ND25
CTRL  + SHIFT + 7 : LyotOpt
CTRL  + SHIFT + 8 : PupilRef"""

    # CTRL+S:  Save current position to preset
    # CTRL+F:  Change preset file
    # add additional shortcuts

    def __init__(self, name_shm=None):
        if name_shm is None:
            name_shm = "vpupcam"
        super().__init__(name_shm=name_shm)
        self.logger = logging.getLogger(name_shm)
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(stream_handler)

    def _data_grab(self) -> None:
        ## hack this to crop the troublesome rows of the Flea3
        super()._data_grab()
        assert self.data_raw_uncrop is not None
        self.data_raw_uncrop = self.data_raw_uncrop[1:, 1:]
