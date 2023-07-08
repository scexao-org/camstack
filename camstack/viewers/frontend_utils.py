# Will this remain useful??

import os
from typing import Tuple, Any, Optional as Op

_CORES = os.sched_getaffinity(0)  # AMD fix
import pygame.event
import pygame.font

import pygame.constants as pgm_ct

os.sched_setaffinity(0, _CORES)  # AMD fix

# COLORS

RGBType = Tuple[int, int, int]


class Colors:
    WHITE = (255, 255, 255)
    GREEN = (56, 199, 105)
    BLUE = (0, 0, 255)
    RED = (246, 133, 101)  #(185,  95, 196)
    VERY_RED = (255, 0, 0)
    BLACK = (0, 0, 0)
    CYAN = (0, 255, 255)
    CLEAR = (0, 0, 0, 0)


COLOR_FOREGROUND = Colors.WHITE  # foreground color (text)
COLOR_SATURATION = Colors.VERY_RED  # saturation color (text)
COLOR_BACKGROUND = Colors.BLACK  # background color
COLOR_BUTTON = Colors.BLUE  # button color


# Dynamic generation of fonts with the system zoom
class Fonts:
    # Cannot initialize from the get go, cause we need pygame to be initialized.
    DEFAULT_25 = None
    DEFAULT_16 = None
    MONO_5 = None
    MONO = None
    MONOBOLD = None

    @classmethod
    def init_zoomed_fonts(cls, system_zoom: int) -> None:

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

    def __init__(self, template_str: str, font: pygame.font.Font,
                 topleft: Op[Tuple[int, int]] = None,
                 topright: Op[Tuple[int, int]] = None,
                 center: Op[Tuple[int,
                                  int]] = None, fg_col: RGBType = Colors.WHITE,
                 bg_col: RGBType = COLOR_BACKGROUND) -> None:

        self.template_str = template_str
        self.n_args = self.template_str.count('%')

        self.last_rendered = ''

        self.font = font
        self.em_size = font.size('0')[1]

        self.fg_col = fg_col
        self.bg_col = bg_col

        self.rectangle = None
        self.label: Op[pygame.surface.Surface] = None
        self.render(tuple(0 for _ in range(self.n_args)))

        assert self.label  # mypy happy - self.label assigned inside self.render.
        self.rectangle: pygame.Rect = self.label.get_rect()

        if topleft is not None:
            self.rectangle.topleft = topleft
        elif center is not None:
            self.rectangle.center = center
        elif topright is not None:
            self.rectangle.topright = topright
        else:
            raise AssertionError(
                    'Either of topleft, center, topright required.')

    def render(self, format_args: Tuple[Any, ...], fg_col: Op[RGBType] = None,
               bg_col: Op[RGBType] = None,
               blit_onto: Op[pygame.surface.Surface] = None) -> None:

        fg_col = self.fg_col if fg_col is None else fg_col
        bg_col = self.bg_col if bg_col is None else bg_col

        self.last_rendered = self.template_str % format_args
        self.label = self.font.render(self.last_rendered, True, fg_col, bg_col)

        if blit_onto is not None:
            self.blit(blit_onto)

    def render_whitespace(self,
                          blit_onto: Op[pygame.surface.Surface] = None) -> None:
        # Because not all our fonts are monospaced:
        how_big_last_rendered = sum([
                c[-1] for c in self.font.metrics(self.last_rendered)
        ])
        space_width = self.font.metrics(' ')[0][-1]
        n_char = how_big_last_rendered // space_width + 1
        self.last_rendered = ''
        self.label = self.font.render(' ' * n_char, True, self.fg_col,
                                      self.bg_col)

        if blit_onto is not None:
            self.blit(blit_onto)

    def blit(self, pg_screen: pygame.surface.Surface) -> None:
        assert self.label  # mypy happy, label initialized.

        pg_screen.blit(self.label, self.rectangle)
