from __future__ import annotations

import os

import click

_CORES = os.sched_getaffinity(0)  # AMD fix
import pygame.constants as pgmc

os.sched_setaffinity(0, _CORES)  # AMD fix

from ..viewerclasses.iiwi import IiwiViewerFrontend, IiwiViewerBackend

from ..viewertools.plugins import SaturationPlugin
from ..viewertools.image_stacking_plugins import IiwiDarkAcquirePlugin
from ..viewertools import camera_control_plugins as cplugs
from ..viewertools import pywfs_plugins as pplugs
from ..viewertools import utils_backend as buts


@click.command("iiwi")
@click.option("-z", "--zoom", type=int, default=1,
              help="Graphics window zoom factor", show_default=True)
@click.option("-b", "--bin", "binn", type=int, default=1,
              help="SHM binning factor", show_default=True)
def main(zoom: int, binn: int):
    backend = IiwiViewerBackend("iiwi")

    # Native is 120x120. Giving ourselves 2x
    binned_backend_shape = (240 // binn, 240 // binn)

    frontend = IiwiViewerFrontend(zoom, 20, binned_backend_shape,
                                  fonts_zoom=zoom // binn)
    plugins = (
            # TODO: x,y position of tip-tilt - modulation amplitude
            # TODO: x,y position of PIL
            # TODO: which filter
            # TODO: which pickoff
            # TODO: fcs pickoff as block
            SaturationPlugin(frontend, sat_value=40_000, nonlin_value=30_000,
                             textbox=frontend.lbl_saturation),
            # Normal dark taking with the pickoff moving
            IiwiDarkAcquirePlugin(frontend, textbox=frontend.lbl_status,
                                  modifier_and=pgmc.KMOD_LCTRL | pgmc.KMOD_LALT,
                                  modifier_no_block=pgmc.KMOD_LCTRL),
            # Dumb dark taking AND post to SHM
            cplugs.IiwiProxyControl(frontend),
            pplugs.PyWFSFluxPlugin(frontend),
    )

    frontend.HELP_MSG += cplugs.IiwiProxyControl.HELP_MSG

    frontend.plugins.extend(plugins)
    frontend.register_backend(backend)
    backend.register_frontend(frontend)
    frontend.run()


if __name__ == "__main__":
    main()
