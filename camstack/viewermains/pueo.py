from __future__ import annotations

import os

import click

_CORES = os.sched_getaffinity(0)  # AMD fix
import pygame.constants as pgmc

os.sched_setaffinity(0, _CORES)  # AMD fix

from ..viewerclasses.pueo import PueoViewerFrontend, PueoViewerBackend

from ..viewertools.plugins import SaturationPlugin
from ..viewertools.image_stacking_plugins import PueoDarkAcquirePlugin
from ..viewertools import camera_control_plugins as cplugs
from ..viewertools import pywfs_plugins as pplugs
from ..viewertools import backend_utils as buts


@click.command("pueo")
@click.option("-z", "--zoom", type=int, default=1,
              help="Graphics window zoom factor", show_default=True)
@click.option("-b", "--bin", "binn", type=int, default=1,
              help="SHM binning factor", show_default=True)
def main(zoom: int, binn: int):
    backend = PueoViewerBackend("ocam2d")

    # Native is 160x160. Giving ourselves 1.5 over
    binned_backend_shape = (240 // binn, 240 // binn)

    frontend = PueoViewerFrontend(zoom, 20, binned_backend_shape,
                                  fonts_zoom=2 * zoom // binn)
    plugins = (
            # TODO: help messages
            SaturationPlugin(frontend, sat_value=40_000,
                             textbox=frontend.lbl_saturation),
            PueoDarkAcquirePlugin(frontend),
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

    frontend.plugins.extend(plugins)
    frontend.register_backend(backend)
    backend.register_frontend(frontend)
    frontend.run()


if __name__ == "__main__":
    main()
