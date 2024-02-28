from __future__ import annotations

import typing as typ

import os

import enum
from dataclasses import dataclass

_CORES = os.sched_getaffinity(0)  # AMD fix
import pygame.constants as pgmc

os.sched_setaffinity(0, _CORES)  # AMD fix


class ZScaleEnum(enum.IntEnum):
    LIN = 0
    ROOT3 = 1
    LOG = 2


NUMKEYS_0_9 = [
        pgmc.K_0, pgmc.K_1, pgmc.K_2, pgmc.K_3, pgmc.K_4, pgmc.K_5, pgmc.K_6,
        pgmc.K_7, pgmc.K_8, pgmc.K_9
]


@dataclass(frozen=True)
class Shortcut:
    '''
    Barely more than a named tuple [int, int]
    '''
    key: int
    modifier_mask: int

    def check_valid(self, key: int, mask: int) -> bool:
        return key == self.key and mask == self.modifier_mask


if typ.TYPE_CHECKING:
    T_PgCallback: typ.TypeAlias = typ.Callable[[], typ.Any]
    T_ShortcutCbMap: typ.TypeAlias = dict[Shortcut, T_PgCallback]
    T_JoystickUDLR: typ.TypeAlias = tuple[int, int, int, int]


class JoyKeys:
    ARROWS: T_JoystickUDLR = (pgmc.K_UP, pgmc.K_DOWN, pgmc.K_LEFT, pgmc.K_RIGHT)
    IJKL: T_JoystickUDLR = (pgmc.K_i, pgmc.K_k, pgmc.K_j, pgmc.K_l)
    WASD: T_JoystickUDLR = (pgmc.K_w, pgmc.K_s, pgmc.K_a, pgmc.K_d)


class JoyKeyDirEnum(enum.Enum):
    UP = 0
    DOWN = 1
    LEFT = 2
    RIGHT = 3


class BackForthDirEnum(enum.Enum):
    LEFT = 0
    RIGHT = 0
