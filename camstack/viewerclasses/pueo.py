from __future__ import annotations

from ..viewertools import frontend_utils as futs
from ..viewertools.generic_viewer_backend import GenericViewerBackend
from ..viewertools.pygame_viewer_frontend import PygameViewerFrontend


class PueoViewerFrontend(PygameViewerFrontend):

    def _init_labels(self) -> int:
        r = super()._init_labels()

        sz = self.system_zoom  # Shorthandy
        c = 10 * sz  # Offset from the left margin

        self.lbl_saturation = futs.LabelMessage("%28s", self.fonts.MONO,
                                                topleft=(c, r))
        r += int(1.2 * self.lbl_saturation.em_size)


class PueoViewerBackend(GenericViewerBackend):
    pass
