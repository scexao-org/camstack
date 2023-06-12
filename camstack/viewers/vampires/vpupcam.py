from camstack.viewers.generic_viewer_frontend import GenericViewerFrontend
from swmain.network.pyroclient import connect
from camstack.viewers.generic_viewer_backend import GenericViewerBackend
import logging
from rich.logging import RichHandler

logger = logging.getLogger("vpupcam")
stream_handler = RichHandler(level=logging.INFO, show_level=False,
                             show_path=False, log_time_format="%H:%M:%S")
logger.addHandler(stream_handler)


class VAMPIRESPupilCamViewerFrontend(GenericViewerFrontend):
    WINDOW_NAME = "VPUPCAM"
    CARTOON_FILE = "bat.png"


class VAMPIRESPupilCamViewerBackend(GenericViewerBackend):
    HELP_MSG = """VPUPCAM controls
---------------
h           : display this message
x, ESC      : quit vpupcam

pupil wheel controls:
---------------------
CTRL+ -- :  change filter wheel slot
        1:  Open (0 deg)
        2:  SAM-7
        3:  SAM-9
        4:  SAM-18
        5:  SAM-18-Nudged
        6:  SAM-Ann-Nudged
        7:  Mirror
        8:  SAM-Ann
        9:  LyotStop
        0:  Open (218 deg)
        -:  ND10
        =:  ND25
CTRL+ARROW :  Nudge wheel 0.01 mm in x (left/right) and y (up/down)
SHIFT+ARROW:  Move wheel 1 mm in x (left/right) and y (up/down)
CTRL+[]    :  Nudge wheel 0.1 deg in theta (ccw/cw)
SHIFT+[]   :  Nudge wheel 1 deg in theta (ccw/cw)
    """

    # CTRL+S:  Save current position to preset
    # CTRL+F:  Change preset file
    # add additional shortcuts

    def __init__(self, name_shm=None):
        if name_shm is None:
            name_shm = "vpupcam"
        super().__init__(name_shm=name_shm)
        self.wheel = connect("VAMPIRES_MASK")
