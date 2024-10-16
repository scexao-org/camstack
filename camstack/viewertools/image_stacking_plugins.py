from __future__ import annotations

from typing import Dict, Callable, Optional as Op, TYPE_CHECKING
if TYPE_CHECKING:
    from .pygame_viewer_frontend import PygameViewerFrontend
    from .generic_viewer_backend import GenericViewerBackend

from abc import abstractmethod
import os, time
import re

_CORES = os.sched_getaffinity(0)  # AMD fix
import pygame.constants as pgmc

os.sched_setaffinity(0, _CORES)  # AMD fix

from . import utils_backend as buts
from . import utils_frontend as futs

from .plugin_arch import OneShotActionPlugin

import numpy as np


class RefImageAcquirePlugin(OneShotActionPlugin):
    HELP_MSG = """:
"""

    def __init__(self, frontend_obj: PygameViewerFrontend,
                 key_onoff: int = pgmc.K_r, modifier_and: int = pgmc.KMOD_LCTRL,
                 textbox: Op[futs.LabelMessage] = None):

        super().__init__(frontend_obj, key_onoff, modifier_and)

        if textbox:
            assert re.match('%.*s', textbox.template_str)
        self.textbox = textbox

        self.start_time = 0.0
        self.averaging_counter = 0

        self.averaged_data: Op[np.ndarray] = None

    def register_backend(self,
                         backend_obj: GenericViewerBackend) -> None:  # Override
        super().register_backend(backend_obj)

        assert self.backend_obj is not None  # assigned in supercall

        self.averaged_data = np.zeros(self.backend_obj.shm_shape, np.float32)

    def do_action(self) -> None:  # abstract impl
        assert self.averaged_data is not None

        if self.textbox:
            self.textbox.render(f"{'ACQUIRING REF IMG':^28s}",
                                bg_col=futs.Colors.BLUE,
                                fg_col=futs.Colors.WHITE)

        self.averaged_data *= 0
        self.averaging_counter = 0
        self.start_time = time.time()

    def is_running(self) -> bool:  # abstract impl
        # Run for 10 seconds from the starting point.
        return time.time() - self.start_time <= 10.0

    def _complete_action(self) -> None:
        assert self.backend_obj is not None
        assert self.averaged_data is not None
        self.averaged_data /= self.averaging_counter

        self.backend_obj.data_for_sub_ref = self.averaged_data
        self.averaging_counter = 0  # Mark for reset.

        if self.textbox:
            self.textbox.render_whitespace()
            self.textbox.blit(self.frontend_obj.pg_screen)
            self.frontend_obj.pg_updated_rects.append(self.textbox.rectangle)

    def frontend_action(self) -> None:  # abstract impl
        if self.is_running() and self.textbox:
            self.textbox.blit(self.frontend_obj.pg_screen)
            self.frontend_obj.pg_updated_rects.append(self.textbox.rectangle)

    def backend_action(self) -> None:  # abstract impl
        assert self.backend_obj  # ...

        # Trigger the finalization
        if not self.is_running():
            if self.averaging_counter > 0:
                self._complete_action()
            return

        # Don't use backend_obj.data_raw_uncrop cause it is subject to averaging/freezing.
        # But we kinda want the ref to be what we're seeing??
        self.averaged_data += self.backend_obj.data_raw_uncrop
        #self.averaged_data += self.backend_obj.input_shm.get_data(False)
        self.averaging_counter += 1


# Warning - abstract
class DarkAcquirePlugin(RefImageAcquirePlugin):

    HELP_MSG = """Dark acquisition:
--- abstract class ---
"""

    def __init__(self, frontend_obj: PygameViewerFrontend,
                 key_onoff: int = pgmc.K_b, modifier_and: int = pgmc.KMOD_LCTRL,
                 modifier_no_block: int | None = None, **kwargs):

        super().__init__(frontend_obj, key_onoff, modifier_and, **kwargs)

        self.modifier_no_block = modifier_no_block
        self.block_was_moved_for_action: bool = False

        if modifier_no_block is not None:
            from functools import partial
            self.shortcut_map[buts.Shortcut(key_onoff, modifier_no_block)] = \
                partial(self.do_action, False)

    def do_action(self, move_block: bool = True) -> None:  # abstract impl
        super().do_action()

        # Override the text box
        if self.textbox:
            text = f"{'ACQUIRING DARK':^28s}" if move_block else f"{'ACQ. DARK (NO MOVE BLOCK)':^28s}"
            self.textbox.render((text, ), bg_col=futs.Colors.BLUE,
                                fg_col=futs.Colors.WHITE)

        if move_block:
            self.block_was_moved_for_action = True
        else:
            self.move_appropriate_block(True)
            self.block_was_moved_for_action = False

    def _complete_action(
            self) -> None:  # Override because we want to write in bias_image
        assert self.backend_obj
        assert self.averaged_data is not None

        if self.block_was_moved_for_action:
            self.move_appropriate_block(False)

        self.averaged_data /= self.averaging_counter

        self.backend_obj.data_for_sub_dark = self.averaged_data  # FIXME reference_image exists?
        self.averaging_counter = 0  # Mark for reset.

        if self.textbox:
            self.textbox.render_whitespace()
            self.textbox.blit(self.frontend_obj.pg_screen)
            self.frontend_obj.pg_updated_rects.append(self.textbox.rectangle)

    @abstractmethod
    def move_appropriate_block(self, in_true: bool) -> None:
        pass


class PueoDarkAcquirePlugin(DarkAcquirePlugin):

    HELP_MSG = """Dark acquisition:
using     pywfs_fcs_pickoff
    """

    def move_appropriate_block(self, in_true: bool) -> None:
        # FIXME
        os.system('ssh sc2 pywfs_fcs_pickoff')


class KiwikiuDarkAcquirePlugin(DarkAcquirePlugin):

    HELP_MSG = """Dark acquisition:
using     lowfs_block
    """

    def move_appropriate_block(self, in_true: bool) -> None:
        # FIXME
        os.system('ssh sc2 lowfs_pickoff')


class ApapanePalilaDarkAcquirePlugin(DarkAcquirePlugin):

    HELP_MSG = """Dark acquisition:
using     ircam_block
"""

    def move_appropriate_block(self, in_true: bool) -> None:
        # FIXME
        os.system('ssh sc2 ircam_block')


class IiwiDarkAcquirePlugin(DarkAcquirePlugin):

    HELP_MSG = """Dark acquisition:
using   irwfs_pickoff (in|out)
"""

    def move_appropriate_block(self, in_true: bool) -> None:
        # Block in == pickoff out
        in_out = 'out' if in_true else 'in'
        os.system(f'ssh aorts irwfs_pickoff {in_out}')

    def _complete_action(self) -> None:
        super()._complete_action()

        from pyMilk.interfacing.shm import SHM

        SHM('iiwi_dark').set_data(self.averaged_data)
        SHM('aol3_wfsdark').set_data(self.averaged_data)
