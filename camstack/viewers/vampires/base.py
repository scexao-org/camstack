from typing import Optional as Op, Tuple
from camstack.viewers.generic_viewer_frontend import GenericViewerFrontend
from swmain.network.pyroclient import connect
from camstack.viewers import GenericViewerBackend, GenericViewerFrontend
from camstack.viewers import backend_utils as buts
from camstack.viewers import frontend_utils as futs
from camstack.viewers.plugin_arch import BasePlugin
import pygame.constants as pgmc
from functools import partial
import pygame
import logging
from swmain.redis import RDB
from rich.panel import Panel
from rich.live import Live
from rich.logging import RichHandler


class MaskStatusPlugin(BasePlugin):
    def __init__(self, frontend_obj: GenericViewerFrontend) -> None:
        super().__init__(frontend_obj)
        zoom = self.frontend_obj.system_zoom
        font = pygame.font.SysFont("default", 50 * zoom)
        self.enabled = True
        self.label = futs.LabelMessage(
            "%s",
            font,
            fg_col="#4AC985",
            bg_col=None,
            topright=(
                self.frontend_obj.data_disp_size[0] - 200 * zoom,
                self.frontend_obj.data_disp_size[1] - 50 * zoom,
            ),
        )
        self.label.blit(self.frontend_obj.pg_datasurface)

    def frontend_action(self) -> None:
        self.label.render(self.status, blit_onto=self.frontend_obj.pg_datasurface)
        # self.frontend_obj.pg_updated_rects.append(self.label.rectangle)

    def backend_action(self) -> None:
        name = RDB.hget("U_MASK", "value")
        self.status = name
