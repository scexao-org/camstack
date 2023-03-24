from __future__ import annotations

from typing import Dict, Callable, Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from .generic_viewer_frontend import GenericViewerFrontend
    from .generic_viewer_backend import GenericViewerBackend

import os

_CORES = os.sched_getaffinity(0)  # AMD fix
import pygame
import pygame.constants as pgmc

os.sched_setaffinity(0, _CORES)  # AMD fix

from . import backend_utils as buts
from . import frontend_utils as futs

from .plugin_arch import OnOffPlugin


# Dummy template
class PupilMode(OnOffPlugin):  # Fuck I desire double inheritance now.

    def __init__(self, frontend_obj: GenericViewerFrontend,
                 key_onoff: int = pgmc.K_p, modifier_and: int = pgmc.KMOD_LCTRL,
                 textbox: Optional[futs.LabelMessage] = None) -> None:

        super().__init__(frontend_obj, key_onoff, modifier_and)

        if textbox:
            assert textbox.template_str == '%s'  # We'll take it from there

        self.textbox = textbox

    def frontend_action(self) -> None:
        # Just remind the front end to blit on top of the data.
        if self.enabled and self.textbox:
            self.frontend_obj.pg_updated_rects.append(self.textbox)

    def backend_action(self) -> None:
        # Need it, it's an abstract method
        pass

    def enable(self) -> None:  # Override

        # SEND COMMAND TO SWITCH TO PUPIL MODE
        # Can be async, we don't care. Or do we?
        # Could be pyro, could be os.system...

        if self.textbox:
            self.textbox.render(('PUPIL', ), fg_col=futs.Colors.BLACK)

        super().enable()

    def disable(self) -> None:  # Override

        # SEND COMMAND TO SWITCH OUT OF PUPIL MODE
        # Could be pyro, could be os.system...

        super().disable()


class CrossHairPlugin(OnOffPlugin):

    def __init__(self, frontend_obj: GenericViewerFrontend,
                 key_onoff: int = pgmc.K_c, modifier_and: int = 0x0,
                 color: str = '#4AC985') -> None:
        super().__init__(frontend_obj, key_onoff, modifier_and)

        self.color = color

    def frontend_action(self) -> None:

        if not self.enabled:  # OK maybe this responsibility could be handled to the caller.
            return

        # Temp default-ish: Crosshair the phys center of the camera
        xc_be = self.backend_obj.shm_shape[0] / 2 - 0.5
        yc_be = self.backend_obj.shm_shape[1] / 2 - 0.5

        xtot_fe, ytot_fe = self.frontend_obj.data_disp_size

        # Compute front-end datasurface coordinates that map to the crosshair location
        sx, sy = self.backend_obj.crop_slice

        # Handle None in slices - I hate it.
        # Put all of that into a backend_obj / frontend_obj method convert_coordinates
        if sx.start is None:
            xl_be = -0.5
        else:
            xl_be = sx.start - 0.5
        if sx.stop is None:
            xh_be = self.backend_obj.shm_shape[0] - 0.5
        else:
            xh_be = sx.stop - 0.5

        if sy.start is None:
            yl_be = -0.5
        else:
            yl_be = sy.start - 0.5
        if sy.stop is None:
            yh_be = self.backend_obj.shm_shape[1] - 0.5
        else:
            yh_be = sy.stop - 0.5

        xc_fe = xtot_fe / (xh_be - xl_be) * (xc_be - xl_be)
        yc_fe = ytot_fe / (yh_be - yl_be) * (yc_be - yl_be)

        # So actually, the crux is we probably don't want to do pygame invocations
        # But actually call back into a library... with frontend.draw_line(x,y,xx,yy)
        # Because, we can keep the idea open that we COULD switcheroo e.g. to a Qt frontend...
        # ... if you follow my drift.
        if yc_fe >= 0 and yc_fe <= ytot_fe:
            pygame.draw.line(self.frontend_obj.pg_datasurface, self.color,
                             (0, yc_fe), (xtot_fe, yc_fe), 1)

        if xc_fe >= 0 and xc_fe <= xtot_fe:
            pygame.draw.line(self.frontend_obj.pg_datasurface, self.color,
                             (xc_fe, 0), (xc_fe, ytot_fe), 1)

    def backend_action(self) -> None:
        pass
