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

# set up logging
from camstack.viewers.vampires.base import VAMPIRESBaseViewerBackend, VAMPIRESBaseViewerFrontend
