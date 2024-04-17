from __future__ import annotations

import typing as typ

import os

_CORES = os.sched_getaffinity(0)  # AMD fix
import pygame.event
import pygame.font

os.sched_setaffinity(0, _CORES)  # AMD fix

from dataclasses import dataclass

# COLORS
if typ.TYPE_CHECKING:
    RGBType = tuple[int, int, int]
    T_t5i = tuple[int, int, int, int, int]


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


class FontBook:

    def __init__(self, system_zoom: int,
                 override_fontsize: T_t5i | None = None) -> None:

        if override_fontsize is None:
            override_fontsize = (20, 10, 5, 8, 7)
        a, b, c, d, e = override_fontsize

        self.DEFAULT_25 = \
            pygame.font.SysFont("default", a * system_zoom)
        self.DEFAULT_16 = \
            pygame.font.SysFont("default", b * system_zoom)
        self.MONO_5 = \
            pygame.font.SysFont("monospace", c * system_zoom)
        self.MONO = \
            pygame.font.SysFont("monospace", d * system_zoom)
        self.MONOBOLD = \
            pygame.font.SysFont("monospace", e * system_zoom, bold=True)


class LabelMessage:

    def __init__(self, template_str: str, font: pygame.font.Font,
                 topleft: tuple[int, int] | None = None,
                 topright: tuple[int, int] | None = None,
                 center: tuple[int, int] | None = None,
                 fg_col: RGBType = Colors.WHITE,
                 bg_col: RGBType = COLOR_BACKGROUND) -> None:

        self.template_str = template_str
        self.n_args = self.template_str.count('%')

        self.last_rendered = ''

        self.font = font
        self.em_size = font.size('0')[1]

        self.fg_col = fg_col
        self.bg_col = bg_col

        if topleft is not None:
            self.rect_alignment = 'topleft'
            self.rect_align_point = topleft
        elif center is not None:
            self.rect_alignment = 'center'
            self.rect_align_point = center
        elif topright is not None:
            self.rect_alignment = 'topright'
            self.rect_align_point = topright
        else:
            raise AssertionError(
                    'Either of topleft, center, topright required.')

        self.label: pygame.surface.Surface | None = None
        self.rectangle: pygame.Rect | None = None

        self.render(tuple(0 for _ in range(self.n_args)))

    def render(self, format_args: tuple[typ.Any, ...],
               fg_col: RGBType | None = None, bg_col: RGBType | None = None,
               blit_onto: pygame.surface.Surface | None = None) -> None:

        fg_col = self.fg_col if fg_col is None else fg_col
        bg_col = self.bg_col if bg_col is None else bg_col

        self.last_rendered = self.template_str % format_args
        self.label = self.font.render(self.last_rendered, True, fg_col, bg_col)

        # Good time to check if the new rectangle is smaller than the old one.

        # Realign in case the width changed or something.
        if self.rectangle is None:
            self.rectangle = self.label.get_rect()

        # Will perform the actual move of the rectangle top-left point in case the
        # Rectangle has changed width and is anchored by the right side.
        nu_r = self.label.get_rect()
        self.rectangle.update(nu_r.left, nu_r.top, nu_r.width, nu_r.height)

        setattr(self.rectangle, self.rect_alignment, self.rect_align_point)

        if blit_onto is not None:
            self.blit(blit_onto)

    def render_whitespace(self, blit_onto: pygame.surface.Surface | None = None
                          ) -> None:
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


@dataclass
class DrawingTransform:
    r_offset: float
    r_scale: float
    c_offset: float
    c_scale: float
