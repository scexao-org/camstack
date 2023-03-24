from __future__ import annotations

from typing import Dict, Callable, Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from .generic_viewer_frontend import GenericViewerFrontend
    from .generic_viewer_backend import GenericViewerBackend

from abc import abstractmethod
import os, time

_CORES = os.sched_getaffinity(0)  # AMD fix
import pygame.constants as pgmc

os.sched_setaffinity(0, _CORES)  # AMD fix

from . import backend_utils as buts
from . import frontend_utils as futs

from .plugin_arch import OneShotActionPlugin

import numpy as np


class RefImageAcquirePlugin(OneShotActionPlugin):

    def __init__(self, frontend_obj: GenericViewerFrontend,
                 key_onoff: int = pgmc.K_r,
                 modifier_and: int = pgmc.KMOD_LCTRL & pgmc.KMOD_LSHIFT,
                 textbox: Optional[futs.LabelMessage] = None):

        super().__init__(frontend_obj, key_onoff, modifier_and)

        if textbox:
            assert textbox.template_str == '%s'
        self.textbox = textbox

        self.averaged_data: np.ndarray = None

    def register_backend(self,
                         backend_obj: GenericViewerBackend) -> None:  # Override
        super().register_backend(backend_obj)

        self.averaged_data = np.zeros(self.backend_obj.shm_shape, np.float64)

    def do_action(self) -> None:  # abstract impl
        if self.textbox:
            self.textbox.render(('ACQUIRING REF IMG.', ),
                                fg_col=futs.Colors.RED)

        self.averaged_data *= 0
        self.averaging_counter = 0
        self.start_time = time.time()

    def is_running(self) -> bool:  # abstract impl
        # Run for 10 seconds from the starting point.
        return time.time() - self.start_time <= 10.0

    def _complete_action(self):
        self.backend_obj.reference_image = self.averaged_data / self.averaging_counter  # FIXME reference_image exists?
        self.averaging_counter = 0  # Mark for reset.

    def frontend_action(self) -> None:  # abstract impl
        if self.is_running() and self.textbox:
            self.frontend_obj.pg_updated_rects.append(self.textbox)

    def backend_action(self) -> None:  # abstract impl
        if not self.is_running():
            if self.averaging_counter > 0:
                self._complete_action()
            return

        # Don't use backend_obj.data_raw_uncrop cause it is subject to 'v' flag averaging.
        self.averaged_data += self.backend_obj.input_shm.get_data(False)
        self.averaging_counter += 1


# Warning - abstract
class DarkAcquirePlugin(RefImageAcquirePlugin):

    def do_action(self) -> None:  # abstract impl
        super().do_action()

        # Override the text box
        if self.textbox:
            self.textbox.render(('ACQUIRING DARK.', ), fg_col=futs.Colors.RED)

        self.move_appropriate_block(True)

    def _complete_action(self):  # Override
        return super()._complete_action()

    @abstractmethod
    def move_appropriate_block(self, in_true: bool):
        self.backend_obj.bias_image = self.averaged_data / self.averaging_counter  # FIXME reference_image exists?
        self.averaging_counter = 0  # Mark for reset.


class PueoDarkAcquirePlugin(DarkAcquirePlugin):

    def move_appropriate_block(self, in_true: bool):
        # FIXME
        os.system('ssh sc2 pywfs_fcs_pickoff')


class ApapanePalilaDarkAcquirePlugin(DarkAcquirePlugin):

    def move_appropriate_block(self, in_true: bool):
        # FIXME
        os.system('ssh sc2 ircam_block')
