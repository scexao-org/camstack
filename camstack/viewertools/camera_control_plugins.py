from __future__ import annotations

import typing as typ

import os
from functools import partial

_CORES = os.sched_getaffinity(0)  # AMD fix
import pygame.constants as pgmc

os.sched_setaffinity(0, _CORES)  # AMD fix

if typ.TYPE_CHECKING:
    from .pygame_viewer_frontend import PygameViewerFrontend

from .plugin_arch import BasePlugin
from . import utils_backend as buts

Sc = buts.Shortcut

from swmain.network.pyroclient import connect


class PyroProxyControl(BasePlugin):

    def __init__(self, frontend_obj: PygameViewerFrontend,
                 pyro_key: str) -> None:
        super().__init__(frontend_obj)

        self.pyro_key = pyro_key
        self.pyro_proxy = connect(pyro_key)

    def frontend_action(self) -> None:
        '''
            Implement abstract method of super.
            There is no inloop action for this pure-control plugin.
        '''
        pass

    def backend_action(self) -> None:
        '''
            Implement abstract method of super.
            There is no inloop action for this pure-control plugin.
        '''
        pass


class IiwiProxyControl(PyroProxyControl):
    HELP_MSG = '''
Pueo control:
--------------------------------------------------
CTRL + t       : Toggle trigger on
CTRL + ALT + t : Toggle trigger off
CTRL + g       : decrease EM gain [1, 2, 4, 8, 16, 32, 64, 121]
CTRL + SH + g  : increase EM gain
CTRL + l       : Decrease FPS [125, 250, 500, 1000, 2000]
CTRL + o       : Increase FPS
    '''

    MAX_GAIN = 600
    SHORT_GAINS = [1, 2, 4, 8, 16, 32, 64, 121]
    SHORT_FPS = [125, 250, 500, 1000, 2000]

    def __init__(self, frontend_obj: PygameViewerFrontend) -> None:
        super().__init__(frontend_obj, 'IIWI')

        if typ.TYPE_CHECKING:
            from ..cams.ocam import OCAM2K
            self.pyro_proxy: OCAM2K

        this_shortcuts: buts.T_ShortcutCbMap = {
                # Ctrl + T          Set extrig ON
                Sc(pgmc.K_t, pgmc.KMOD_LCTRL):
                        partial(self.pyro_proxy.set_synchro, True),
                # Ctrl + Alt + T    Set extrig OFF
                Sc(pgmc.K_t, pgmc.KMOD_LCTRL | pgmc.KMOD_LALT):
                        partial(self.pyro_proxy.set_synchro, False),
                # Ctrl + g: decrease gain
                Sc(pgmc.K_g, pgmc.KMOD_LCTRL):
                        self.decrease_gain,
                # Ctrl + Shift + G: increase gain
                Sc(pgmc.K_g, pgmc.KMOD_LCTRL | pgmc.KMOD_LSHIFT):
                        self.increase_gain,
                # Ctrl + l: decrease fps
                Sc(pgmc.K_l, pgmc.KMOD_LCTRL):
                        self.decrease_fps,
                # Ctrl + o: increase fps
                Sc(pgmc.K_o, pgmc.KMOD_LCTRL):
                        self.increase_fps,
        }

        # That's all we need for Iiwi for now...

        self._append_shortcuts(this_shortcuts)

    def increase_gain(self):
        gain = self.pyro_proxy.get_gain()
        # Find and set first index > gain
        for g in self.SHORT_GAINS:
            if g > gain:
                self.pyro_proxy.set_gain(g)
                break

    def decrease_gain(self):
        gain = self.pyro_proxy.get_gain()
        # Find and set last index < gain
        for g in self.SHORT_GAINS[::-1]:
            if g < gain:
                self.pyro_proxy.set_gain(g)
                break

    def increase_fps(self):
        fps = self.pyro_proxy.get_fps()
        # Find and set first index > 1.05 * fps (avoid roundoff problems)
        for f in self.SHORT_FPS:
            if f > 1.05 * fps:
                self.pyro_proxy.set_fps(f)
                break

    def decrease_fps(self):
        fps = self.pyro_proxy.get_fps()
        # Find and set last index < 0.95 * fps
        for f in self.SHORT_FPS[::-1]:
            if f < 0.95 * fps:
                self.pyro_proxy.set_fps(f)
                break


class PueoProxyControl(PyroProxyControl):
    HELP_MSG = '''
Pueo control:
--------------------------------------------------
CTRL + t       : Toggle trigger on
CTRL + ALT + t : Toggle trigger off
CTRL + g       : decrease EM gain
CTRL + SH + g  : increase EM gain
CTRL + ALT + g : EM gain protection reset
CTRL + l       : Decrease FPS
CTRL + o       : Increase FPS
CTRL + SHIFT + NUMBER: Set EM gain to 2**NUMBER
    '''

    MAX_GAIN = 600
    SHORT_GAINS = [1, 2, 4, 8, 16, 32, 75, 150, 300, 600]
    SHORT_FPS = [125, 250, 500, 1000, 2000, 3000, 3600]

    def __init__(self, frontend_obj: PygameViewerFrontend) -> None:
        super().__init__(frontend_obj, 'PUEO')

        if typ.TYPE_CHECKING:
            from ..cams.ocam import OCAM2K
            self.pyro_proxy: OCAM2K

        this_shortcuts: buts.T_ShortcutCbMap = {
                # Ctrl + T          Set extrig ON
                Sc(pgmc.K_t, pgmc.KMOD_LCTRL):
                        partial(self.pyro_proxy.set_synchro, True),
                # Ctrl + Alt + T    Set extrig OFF
                Sc(pgmc.K_t, pgmc.KMOD_LCTRL | pgmc.KMOD_LALT):
                        partial(self.pyro_proxy.set_synchro, False),
                # Ctrl + g: decrease gain
                Sc(pgmc.K_g, pgmc.KMOD_LCTRL):
                        self.decrease_gain,
                # Ctrl + Shift + G: increase gain
                Sc(pgmc.K_g, pgmc.KMOD_LCTRL | pgmc.KMOD_LSHIFT):
                        self.increase_gain,
                # Ctrl + Alt + g: gain reset
                Sc(pgmc.K_g, pgmc.KMOD_LCTRL | pgmc.KMOD_LALT):
                        self.pyro_proxy.gain_protection_reset,
                # Ctrl + l: decrease fps
                Sc(pgmc.K_l, pgmc.KMOD_LCTRL):
                        self.decrease_fps,
                # Ctrl + o: increase fps
                Sc(pgmc.K_o, pgmc.KMOD_LCTRL):
                        self.increase_fps,
        }

        # Ctrl + Shift + [0-9]: set direct EM gain
        for ii, key in enumerate(buts.NUMKEYS_0_9):
            this_shortcuts[Sc(key, pgmc.KMOD_LCTRL | pgmc.KMOD_LSHIFT)] =\
                partial(self.pyro_proxy.set_gain, 2**ii)

        # That's all we need for Pueo for now...

        self._append_shortcuts(this_shortcuts)

    def increase_gain(self):
        gain = self.pyro_proxy.get_gain()
        # Find and set first index > gain
        for g in self.SHORT_GAINS:
            if g > gain:
                self.pyro_proxy.set_gain(g)
                break

    def decrease_gain(self):
        gain = self.pyro_proxy.get_gain()
        # Find and set last index < gain
        for g in self.SHORT_GAINS[::-1]:
            if g < gain:
                self.pyro_proxy.set_gain(g)
                break

    def increase_fps(self):
        fps = self.pyro_proxy.get_fps()
        # Find and set first index > 1.05 * fps (avoid roundoff problems)
        for f in self.SHORT_FPS:
            if f > 1.05 * fps:
                self.pyro_proxy.set_fps(f)
                break

    def decrease_fps(self):
        fps = self.pyro_proxy.get_fps()
        # Find and set last index < 0.95 * fps
        for f in self.SHORT_FPS[::-1]:
            if f < 0.95 * fps:
                self.pyro_proxy.set_fps(f)
                break
