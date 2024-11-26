from __future__ import annotations

import typing as typ

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

import PyQt5.QtCore as qtc
import PyQt5.QtWidgets as qtw
import PyQt5.QtGui as qtg


def make_palette() -> qtg.QPalette:
    palette = qtg.QPalette()
    palette.setColor(qtg.QPalette.Window, qtg.QColor(*COLOR_BACKGROUND))
    palette.setColor(qtg.QPalette.WindowText, qtc.Qt.white)
    palette.setColor(qtg.QPalette.Base, qtg.QColor(25, 25, 25))
    palette.setColor(qtg.QPalette.AlternateBase, qtg.QColor(53, 53, 53))
    palette.setColor(qtg.QPalette.ToolTipBase, qtc.Qt.black)
    palette.setColor(qtg.QPalette.ToolTipText, qtc.Qt.white)
    palette.setColor(qtg.QPalette.Text, qtc.Qt.white)
    palette.setColor(qtg.QPalette.Button, qtg.QColor(53, 53, 53))
    palette.setColor(qtg.QPalette.ButtonText, qtc.Qt.white)
    palette.setColor(qtg.QPalette.BrightText, qtc.Qt.red)
    palette.setColor(qtg.QPalette.Link, qtg.QColor(42, 130, 218))
    palette.setColor(qtg.QPalette.Highlight, qtg.QColor(42, 130, 218))
    palette.setColor(qtg.QPalette.HighlightedText, qtc.Qt.black)

    return palette


class FontBookQt:

    def __init__(self, system_zoom: int,
                 override_fontsize: T_t5i | None = None) -> None:
        if override_fontsize is None:
            override_fontsize = (11, 9, 5, 7, 7)

        a, b, c, d, e = override_fontsize

        self.DEFAULT_25 = FontBookQt.makefont(system_zoom, bold=True, weight=50,
                                              size=a, mono=False)

        self.DEFAULT_16 = FontBookQt.makefont(system_zoom, bold=False,
                                              weight=50, size=b, mono=False)
        self.MONO_5 = FontBookQt.makefont(system_zoom, bold=False, size=c,
                                          mono=True)
        self.MONO = FontBookQt.makefont(system_zoom, bold=False, size=d,
                                        mono=True)
        self.MONOBOLD = FontBookQt.makefont(system_zoom, bold=True, size=e,
                                            mono=True)

    @staticmethod
    def makefont(font_zoom: int = 1, *, bold: bool = False, weight: int |
                 None = None, size: int = 12, mono: bool = False) -> qtg.QFont:
        font = qtg.QFont()
        if mono:
            font.setFamily('monospace')
            font.setStyleHint(qtg.QFont.TypeWriter)

        font.setPointSize(font_zoom * size)
        if weight:
            font.setWeight(weight)

        return font


class QLabelWrap(qtw.QLabel):

    def __init__(self, text: str, font: qtg.QFont, max_width: int | None = None,
                 align: qtc.Qt.AlignmentFlag = qtc.Qt.AlignLeft) -> None:
        qtw.QLabel.__init__(self, text)
        self.setFont(font)
        self.setContentsMargins(0, 0, 0, 0)

        if max_width is not None:
            self.setMaximumWidth(70)

        self.setAlignment(align)


class LabelMessageQt:

    def __init__(self, template_str: str, font: qtg.QFont,
                 fg_col: RGBType = Colors.WHITE,
                 bg_col: RGBType = COLOR_BACKGROUND,
                 align: qtc.Qt.AlignmentFlag = qtc.Qt.AlignLeft) -> None:

        self.template_str = template_str
        self.n_args = self.template_str.count('%')

        self.last_rendered = ''

        self.font = qtg.QFont(font)
        self.em_size = qtg.QFontMetrics(self.font).height()

        self.fg_col = fg_col
        self.bg_col = bg_col
        self.align = align

        self.qlabel: QLabelWrap = None  # type: ignore

        self.render(tuple(0 for _ in range(self.n_args)))

    def render(self, format_args: tuple[typ.Any,
                                        ...], fg_col: RGBType | None = None,
               bg_col: RGBType | None = None) -> None:

        fg_col = self.fg_col if fg_col is None else fg_col
        bg_col = self.bg_col if bg_col is None else bg_col

        self.last_rendered = self.template_str % format_args

        if self.qlabel is None:
            self.qlabel = QLabelWrap(self.last_rendered, self.font,
                                     align=self.align)

        self.qlabel.setText(self.last_rendered)
        self.qlabel.setStyleSheet(("color:rgb(%d,%d,%d); " % (fg_col)) +
                                  ("background-color:rgb(%d,%d,%d)" % (bg_col)))
        self.qlabel.setFont(self.font)

    def render_whitespace(self) -> None:
        assert self.qlabel is not None
        self.qlabel.setText('')


#### HARDCORE

from .utils_backend import Shortcut as Sc


def QKeySequencify(sc: Sc) -> qtg.QKeySequence:
    import os
    _CORES = os.sched_getaffinity(0)  # AMD fix
    import pygame.constants as pgmc
    os.sched_setaffinity(0, _CORES)  # AMD fix

    LIST_K_ATTRS = [k for k in pgmc.__dict__ if k.startswith('K_')]
    DICT_REV_K_ATTRS: dict[int, list[str]] = {}

    for kname in LIST_K_ATTRS:
        keyvalue = getattr(pgmc, kname)
        if keyvalue not in DICT_REV_K_ATTRS:
            DICT_REV_K_ATTRS[keyvalue] = []

        DICT_REV_K_ATTRS[keyvalue] += [kname]
