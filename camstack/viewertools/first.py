from typing import Tuple
from camstack.viewertools.generic_viewer_backend import GenericViewerBackend
from camstack.viewertools.pygame_viewer_frontend import PygameViewerFrontend


class FirstViewerBackend(GenericViewerBackend):
    pass


class FirstViewerFrontend(PygameViewerFrontend):

    WINDOW_NAME = "`Io camera viewer"
    CARTOON_FILE = 'io.png'

    def __init__(self, system_zoom: int, fps: int,
                 display_base_size: Tuple[int, int]) -> None:

        # Hack the arguments BEFORE
        PygameViewerFrontend.__init__(self, system_zoom, fps, display_base_size)

        # Finalize some specifics AFTER
