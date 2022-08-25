def encode_shortcuts(shortcut_string: str):
    '''
    Process a shortcut string into a pygame value

    Accepted format:

    mods-<key>

    Mods is a concatenation of (case insensitive)
    lC, lW, lA, lS, rC, rM, rA

    key is any upper or lower single letter
    '''
    lowercase = shortcut_string.lower()
    if '-' in lowercase:
        letter = lowercase.split('-')[1]
    else:  # expect lenght 1, ord() wil raise the error, no modifiers
        letter = lowercase

    # Values are the KMOD_* from pygame
    # But we don't want to import pygame in this file!
    mods = (('ls' in lowercase) * 0x001) | \
           (('rs' in lowercase) * 0x002) | \
           (('lc' in lowercase) * 0x040) | \
           (('rc' in lowercase) * 0x080) | \
           (('la' in lowercase) * 0x100) | \
           (('ra' in lowercase) * 0x200) | \
           (('lw' in lowercase) * 0x400)

    let_int = ord(letter)

    return (mods, let_int)
