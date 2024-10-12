from __future__ import annotations

import os

import click

_CORES = os.sched_getaffinity(0)  # AMD fix
import pygame.constants as pgmc

os.sched_setaffinity(0, _CORES)  # AMD fix

from ..viewerclasses.kiwikiu import KiwikiuViewerFrontend, KiwikiuViewerBackend

from ..viewertools.plugins import SaturationPlugin
from ..viewertools.image_stacking_plugins import KiwikiuDarkAcquirePlugin
from ..viewertools import camera_control_plugins as cplugs
from ..viewertools import utils_backend as buts


@click.command("pueo")
@click.option("-z", "--zoom", type=int, default=2,
              help="Graphics window zoom factor", show_default=True)
@click.option("-b", "--bin", "binn", type=int, default=1,
              help="SHM binning factor", show_default=True)
def main(zoom: int, binn: int):
    backend = KiwikiuViewerBackend("kiwikiu")

    # Native is 120x120. Giving ourselves 2x
    binned_backend_shape = (240 // binn, 240 // binn)

    frontend = KiwikiuViewerFrontend(zoom, 20, binned_backend_shape,
                                     fonts_zoom=zoom // binn)
    plugins = (
            # TODO: x,y position of tip-tilt - modulation amplitude
            # TODO: x,y position of PIL
            # TODO: which filter
            # TODO: which pickoff
            # TODO: fcs pickoff as block
            SaturationPlugin(frontend, sat_value=12_000, nonlin_value=10_000,
                             textbox=frontend.lbl_saturation),
            KiwikiuDarkAcquirePlugin(frontend, textbox=frontend.lbl_status),
            cplugs.PueoProxyControl(frontend),
            pplugs.PyWFSFluxPlugin(frontend),
            pplugs.VisPyWFSTipTiltPlugin(frontend, buts.JoyKeys.ARROWS, [
                    pgmc.KMOD_LCTRL | pgmc.KMOD_LALT, pgmc.KMOD_LCTRL,
                    pgmc.KMOD_LCTRL | pgmc.KMOD_LSHIFT
            ]),
            pplugs.VisPyWFSPupilSteerPlugin(frontend, buts.JoyKeys.ARROWS, [
                    pgmc.KMOD_RCTRL | pgmc.KMOD_RALT, pgmc.KMOD_RCTRL,
                    pgmc.KMOD_RCTRL | pgmc.KMOD_RSHIFT
            ]),
    )

    frontend.HELP_MSG += cplugs.PueoProxyControl.HELP_MSG

    frontend.plugins.extend(plugins)
    frontend.register_backend(backend)
    backend.register_frontend(frontend)
    frontend.run()


if __name__ == "__main__":
    main()
