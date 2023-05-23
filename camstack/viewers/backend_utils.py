from typing import List

import enum
from dataclasses import dataclass

import pygame.constants as pgm_ct


class ZScaleEnum(enum.IntEnum):
    LIN = 0
    ROOT3 = 1
    LOG = 2


@dataclass
class Shortcut:
    '''
    Barely more than a named tuple [int, int]
    '''
    key: int
    modifier_mask: int

    def check_valid(self, key: int, mask: int) -> bool:
        return key == self.key and mask == self.modifier_mask

    def __hash__(self) -> int:
        # I want to be able to dictionary them :D
        return (self.key, self.modifier_mask).__hash__()
