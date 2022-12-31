# Will this remain useful??

import os
from typing import Tuple, Any

_CORES = os.sched_getaffinity(0)  # AMD fix
import pygame.event
import pygame.font

import pygame.constants as pgm_ct

os.sched_setaffinity(0, _CORES)  # AMD fix


# COLORS
class Colors:
    WHITE = (255, 255, 255)
    GREEN = (147, 181, 44)
    BLUE = (0, 0, 255)
    RED = (246, 133, 101)  #(185,  95, 196)
    VERY_RED = (255, 0, 0)
    BLACK = (0, 0, 0)
    CYAN = (0, 255, 255)


COLOR_FOREGROUND = Colors.WHITE  # foreground color (text)
COLOR_SATURATION = Colors.VERY_RED  # saturation color (text)
COLOR_BACKGROUND = Colors.BLACK  # background color
COLOR_BUTTON = Colors.BLUE  # button color


# Dynamic generation of fonts with the system zoom
class Fonts:
    DEFAULT_25 = None
    DEFAULT_16 = None
    MONO_5 = None
    MONO = None
    MONOBOLD = None

    def init_zoomed_fonts(system_zoom: int):

        Fonts.DEFAULT_25 = \
            pygame.font.SysFont("default", 20 * system_zoom)
        Fonts.DEFAULT_16 = \
            pygame.font.SysFont("default", 10 * system_zoom)
        Fonts.MONO_5 = \
            pygame.font.SysFont("monospace", 5 * system_zoom)
        Fonts.MONO = \
            pygame.font.SysFont("monospace", 8 * system_zoom)
        Fonts.MONOBOLD = \
            pygame.font.SysFont("monospace", 7 * system_zoom, bold=True)


class LabelMessage:

    def __init__(self, template_str: str, font, topleft: Tuple[int,
                                                               int] = None,
                 center: Tuple[int, int] = None, fg_col=Colors.WHITE,
                 bg_col=COLOR_BACKGROUND):

        self.template_str = template_str
        self.n_args = self.template_str.count('%')

        self.font = font
        self.em_size = font.size('0')[1]

        self.fg_col = fg_col
        self.bg_col = bg_col

        self.label = None
        self.render(tuple(0 for _ in range(self.n_args)))

        self.rectangle = self.label.get_rect()

        if topleft is not None:
            self.rectangle.topleft = topleft
        else:
            self.rectangle.center = center

    def render(self, format_args: Tuple[Any, ...], fg_col=None, bg_col=None,
               blit_onto=None):
        fg_col = self.fg_col if fg_col is None else fg_col
        bg_col = self.bg_col if bg_col is None else bg_col

        self.label = self.font.render(self.template_str % format_args, True,
                                      fg_col, bg_col)

        if blit_onto is not None:
            self.blit(blit_onto)

    def blit(self, pg_screen):
        pg_screen.blit(self.label, self.rectangle)
