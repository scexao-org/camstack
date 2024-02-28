from __future__ import annotations

import typing as typ

from camstack.viewertools.pygame_viewer_frontend import PygameViewerFrontend
if typ.TYPE_CHECKING:
    from .pygame_viewer_frontend import PygameViewerFrontend
    from .generic_viewer_backend import GenericViewerBackend

from . import backend_utils as buts
from . import frontend_utils as futs

from abc import ABC, abstractmethod
import os

from functools import partial

_CORES = os.sched_getaffinity(0)  # AMD fix
import pygame.constants as pgmc

os.sched_setaffinity(0, _CORES)  # AMD fix


class BasePlugin(ABC):

    def __init__(self, frontend_obj: PygameViewerFrontend) -> None:

        # The enabled flag is stored internally but not used internally
        # It's for the sake of the frontend & backend to know what to call.
        self.enabled: bool = False

        self.frontend_obj: PygameViewerFrontend = frontend_obj

        self.backend_obj: GenericViewerBackend | None = None
        self.has_backend: bool = False

        self.shortcut_map: buts.T_ShortcutCbMap = {}

    def register_backend(self, backend_obj: GenericViewerBackend) -> None:

        self.has_backend = True
        self.backend_obj = backend_obj

    def _append_shortcuts(self,
                          subclass_shortcuts: buts.T_ShortcutCbMap) -> None:
        '''
        don't subclass this. We're actually gonna be checking that subclass shortcuts don't collide
        with superclass shortcuts.
        '''
        key_set = set(self.shortcut_map.keys())
        extended_key_set = set(subclass_shortcuts.keys())

        if key_set.intersection(extended_key_set):
            raise AssertionError('Shortcut collision.')

        self.shortcut_map.update(subclass_shortcuts)

    @abstractmethod
    def frontend_action(self) -> None:
        '''
            Do computations for this onoff mode
        '''
        pass

    @abstractmethod
    def backend_action(self) -> None:
        '''
            Do the proper graphical stuff in the frontend.
            I kinda don't like that this is in yet-another pygame file, but heck.
        '''
        pass


# Warning: abstract
class OneAxisBackForthPlugin(BasePlugin):

    def __init__(self, frontend_obj: PygameViewerFrontend, left: int,
                 right: int, modlevels: list[int]) -> None:

        super().__init__(frontend_obj)

        self.left, self.right = left, right
        self.mod_levels = modlevels

        this_shortcuts: buts.T_ShortcutCbMap = {}

        Sc = buts.Shortcut
        for kk, mod_keys in enumerate(self.mod_levels):
            this_shortcuts[Sc(self.left, mod_keys)] =\
                partial(self.dispatch_modlevel, buts.BackForthDirEnum.LEFT, kk)
            this_shortcuts[Sc(self.right, mod_keys)] =\
                partial(self.dispatch_modlevel, buts.BackForthDirEnum.RIGHT, kk)

        self._append_shortcuts(this_shortcuts)

    @abstractmethod
    def dispatch_modlevel(self, dir: buts.BackForthDirEnum,
                          mod_index: int) -> None:
        '''
            Dispatch depending on key direction and modlevel.
            One approach would be to pass the dir to various funcs depending on the mod_level
            to functions with signature Callable[[buts.JoyKeyDirEnum], None]
        '''
        pass


# Warning: abstract
class JoystickActionPlugin(BasePlugin):

    def __init__(self, frontend_obj: PygameViewerFrontend,
                 joystick_udlr: buts.T_JoystickUDLR,
                 modlevels: list[int]) -> None:

        super().__init__(frontend_obj)

        self.joystick_udlr = joystick_udlr
        self.joy_up, self.joy_down, self.joy_left, self.joy_right = self.joystick_udlr
        self.mod_levels = modlevels

        this_shortcuts: buts.T_ShortcutCbMap = {}

        Sc = buts.Shortcut
        for kk, mod_keys in enumerate(self.mod_levels):
            this_shortcuts[Sc(self.joy_up, mod_keys)] =\
                partial(self.dispatch_modlevel, buts.JoyKeyDirEnum.UP, kk)
            this_shortcuts[Sc(self.joy_down, mod_keys)] =\
                partial(self.dispatch_modlevel, buts.JoyKeyDirEnum.DOWN, kk)
            this_shortcuts[Sc(self.joy_left, mod_keys)] =\
                partial(self.dispatch_modlevel, buts.JoyKeyDirEnum.LEFT, kk)
            this_shortcuts[Sc(self.joy_right, mod_keys)] =\
                partial(self.dispatch_modlevel, buts.JoyKeyDirEnum.RIGHT, kk)

        self._append_shortcuts(this_shortcuts)

    @abstractmethod
    def dispatch_modlevel(self, dir: buts.JoyKeyDirEnum,
                          mod_index: int) -> None:
        '''
            Dispatch depending on key direction and modlevel.
            One approach would be to pass the dir to various funcs depending on the mod_level
            to functions with signature Callable[[buts.JoyKeyDirEnum], None]
        '''
        pass


# Warning: abstract
class OneShotActionPlugin(BasePlugin):

    def __init__(self, frontend_obj: PygameViewerFrontend, key_action: int,
                 modifier_and: int = 0x0) -> None:
        super().__init__(frontend_obj)

        self.shortcut_action = buts.Shortcut(key_action, modifier_and)

        this_shortcuts = {self.shortcut_action: self.try_action}

        self._append_shortcuts(this_shortcuts)

    def try_action(self) -> None:
        if self.is_running():
            print(f'Cannot run {self} - running already')

        self.do_action()

    @abstractmethod
    def do_action(self) -> None:
        pass

    @abstractmethod
    def is_running(self) -> bool:
        '''
        Warning - this is gonna get called maybe a lot... so we don't
        necessarily want to perform a resource intensive/agressive check.
        Like: I have counted to 1000 frames yet is OK
        But: Has my stage moved? and now? and now? probably isn't
        '''
        pass


class OnOffPlugin(BasePlugin):

    def __init__(self, frontend_obj: PygameViewerFrontend, key_onoff: int,
                 modifier_and: int = 0x0) -> None:

        super().__init__(frontend_obj)

        self.shortcut_onoff = buts.Shortcut(key_onoff, modifier_and)

        this_shortcuts = {self.shortcut_onoff: self.toggle}

        self._append_shortcuts(this_shortcuts)

        self.enabled = False

    def enable(self) -> None:
        self.enabled = True

    def disable(self) -> None:
        self.enabled = False

    def toggle(self) -> None:
        if self.enabled:
            self.disable()
        else:
            self.enable()
