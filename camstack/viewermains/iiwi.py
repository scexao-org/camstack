import click

from ..viewerclasses.iiwi import IiwiViewerBackend, IiwiViewerFrontend

from ..viewertools.plugins import SaturationPlugin
from ..viewertools.image_stacking_plugins import IiwiDarkAcquirePlugin
from ..viewertools import iiwi_plugins as iplugs


@click.command("iiwi.py")
@click.option("-z", "--zoom", type=int, default=1,
              help="Graphics window zoom factor", show_default=True)
@click.option("-b", "--bin", "binn", type=int, default=1,
              help="SHM binning factor", show_default=True)
def main(zoom: int, binn: int):
    backend = IiwiViewerBackend(1, "iiwi")

    # Native is 160x160. Giving ourselves 1.5 over
    binned_backend_shape = (240 // binn, 240 // binn)

    frontend = IiwiViewerFrontend(1, zoom, 20, binned_backend_shape,
                                  fonts_zoom=2 * zoom // binn)
    plugins = (
            SaturationPlugin(frontend, sat_value=40_000,
                             textbox=frontend.lbl_saturation),
            IiwiDarkAcquirePlugin(frontend),
            iiwiplugs.DAC40TTPlugin(frontend),
    )

    frontend.plugins.extend(plugins)
    frontend.register_backend(backend)
    backend.register_frontend(frontend)
    frontend.run()
