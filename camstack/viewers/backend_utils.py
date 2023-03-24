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

    def check_valid(self, key: int, mask: int):
        return key == self.key and mask == self.modifier_mask

    def __hash__(self) -> int:
        # I want to be able to dictionary them :D
        return (self.key, self.modifier_mask).__hash__()


def encode_shortcuts(shortcut_string: str):
    '''
    Process a shortcut string into a pygame value

    Accepted format:

    mods-<key(s)>

    Mods is a concatenation of (case insensitive)
    lC, lW, lA, lS, rC, rM, rA

    key is any upper or lower single letter
    '''

    # If an int is passed, we know what we're doing.
    if type(shortcut_string) is int:
        return (0, shortcut_string)

    lowercase = shortcut_string.lower()
    if '-' in lowercase:
        modifiers, letter = lowercase.split('-')
    else:  # expect lenght 1, ord() wil raise the error, no modifiers
        modifiers, letter = '', lowercase

    # Values are the KMOD_* from pygame
    # But we don't want to import pygame in this file!
    mods = (('ls' in modifiers) * 0x001) | \
           (('rs' in modifiers) * 0x002) | \
           (('lc' in modifiers) * 0x040) | \
           (('rc' in modifiers) * 0x080) | \
           (('la' in modifiers) * 0x100) | \
           (('ra' in modifiers) * 0x200) | \
           (('lw' in modifiers) * 0x400)

    # Now parse the keys into integers.
    # TODO what about arrow keys?
    # TODO what about multi-shortcuts that would call the same function?
    let_int = ord(letter)

    return (mods, let_int)
