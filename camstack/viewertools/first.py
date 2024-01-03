from typing import Tuple
from camstack.viewertools.generic_viewer_backend import GenericViewerBackend
from camstack.viewertools.generic_viewer_frontend import GenericViewerFrontend


class FirstViewerBackend(GenericViewerBackend):
    pass


class FirstViewerFrontend(GenericViewerFrontend):

    WINDOW_NAME = 'FIRST camera'
    CARTOON_FILE = 'io.png'

    def __init__(self, system_zoom: int, fps: int,
                 display_base_size: Tuple[int, int]) -> None:

        # Hack the arguments BEFORE
        GenericViewerFrontend.__init__(self, system_zoom, fps,
                                       display_base_size)

        # Finalize some specifics AFTER
